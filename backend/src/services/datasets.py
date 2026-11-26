import copy
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.business.algorithm import validate_rows
from src.business.profile import PROFILE
from src.config.settings import Session
from src.models.dataset import Dataset
from src.schemas.resources import dataset_view
from src.services import calibrations
from src.services.audit import record
from src.utils.csv_data import coerce, digest, parse_csv

log = logging.getLogger(__name__)


def require(db, dataset_id):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "数据版本不存在。")
    return dataset


def list_datasets():
    with Session() as db:
        return [dataset_view(row) for row in db.scalars(select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc()))]


def list_corrections():
    with Session() as db:
        rows = db.scalars(
            select(Dataset)
            .where(Dataset.parent_id.is_not(None))
            .order_by(Dataset.created_at.desc(), Dataset.id.desc())
            .limit(200)
        )
        return [dataset_view(row) for row in rows]


def list_dataset_corrections(dataset_id):
    with Session() as db:
        require(db, dataset_id)
        rows = db.scalars(
            select(Dataset)
            .where(Dataset.parent_id == dataset_id)
            .order_by(Dataset.created_at.desc(), Dataset.id.desc())
        )
        return [dataset_view(row) for row in rows]


def save_in(db, name, rows, author, audit=True):
    checksum = digest(rows)
    existing = db.scalar(select(Dataset).where(Dataset.checksum == checksum))
    if existing is not None:
        return existing, False
    item = Dataset(name=name, checksum=checksum, rows=rows, author=author)
    try:
        with db.begin_nested():
            db.add(item)
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(Dataset).where(Dataset.checksum == checksum).with_for_update())
        if existing is None:
            raise
        return existing, False
    if audit:
        record(db, author, "dataset_imported", item.id)
    return item, True


def ingest(name, contents, author):
    try:
        rows = parse_csv(contents, PROFILE["columns"])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with Session.begin() as db:
        item, created = save_in(db, name, rows, author)
        dataset_id = item.id
        payload = {**dataset_view(item), "created": created}
    if created:
        try:
            calibrations.refresh_source(dataset_id, actor=author, reason="dataset_imported")
        except Exception:
            log.exception("Could not enqueue calibration refresh for %s", dataset_id)
    return payload


def _correction_changes(body: dict, path_sample_id: str | None) -> tuple[str, dict, str | None, str | None]:
    sample_id = path_sample_id or body.get("sample_id")
    if not sample_id or not isinstance(sample_id, str):
        raise HTTPException(422, "请提供要更正的试转编号。")
    reason = body.get("reason") or body.get("note")
    if isinstance(reason, str):
        reason = reason.strip() or None
    name = body.get("name")
    changes = {}
    container_keys = (
        "values", "changes", "corrections", "corrected", "correction", "update", "updated",
        "attributes", "data", "payload", "row", "reading", "fields",
    )
    for key in container_keys:
        candidate = body.get(key)
        if isinstance(candidate, dict):
            changes.update(candidate)
        elif isinstance(candidate, list):
            for item in candidate:
                if not isinstance(item, dict):
                    continue
                field_name = item.get("field") or item.get("key") or item.get("column")
                field_value = item.get("value", item.get("new_value"))
                if field_name:
                    changes[field_name] = field_value

    field_name = body.get("field") or body.get("column") or body.get("key")
    if field_name and ("value" in body or "new_value" in body or "reading_value" in body):
        changes[field_name] = body.get("value", body.get("new_value", body.get("reading_value")))

    metadata_keys = {
        "sample_id", "dataset_id", "name", "reason", "note", "field", "column", "key",
        "value", "new_value", "reading_value", *container_keys,
    }
    for key, value in body.items():
        if key not in metadata_keys:
            changes[key] = value
    changes.pop("sample_id", None)
    changes.pop("dataset_id", None)
    if not changes:
        raise HTTPException(422, "请至少填写一个需要更正的读数字段。")
    return sample_id, changes, reason, name


def correct_version(dataset_id, body: dict, actor: str, path_sample_id: str | None = None):
    if hasattr(body, "model_dump"):
        body = body.model_dump(exclude_none=True)
    sample_id, changes, reason, new_name = _correction_changes(body, path_sample_id)
    fields = {column["key"]: column for column in PROFILE["columns"]}
    unknown = sorted(key for key in changes if key not in fields)
    if unknown:
        raise HTTPException(422, f"未知读数字段：{', '.join(unknown)}。")
    if "sample_id" in changes:
        raise HTTPException(422, "试转编号用于定位更正记录，不能在读数更正中替换。")

    with Session.begin() as db:
        source = require(db, dataset_id)
        rows = copy.deepcopy(source.rows)
        index = next((i for i, row in enumerate(rows) if row["sample_id"] == sample_id), None)
        if index is None:
            raise HTTPException(404, f"试转编号 {sample_id} 不存在于该数据版本。")
        old_row = copy.deepcopy(rows[index])
        updates = {}
        for key, raw_value in changes.items():
            if raw_value is None:
                raise HTTPException(422, f"「{fields[key]['label']}」不能为空。")
            value_text = raw_value if isinstance(raw_value, str) else str(raw_value)
            try:
                corrected_value = coerce(value_text.strip(), fields[key], index + 2)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            rows[index][key] = corrected_value
            if corrected_value != old_row.get(key):
                updates[key] = corrected_value
        if not updates:
            raise HTTPException(422, "提交的读数与原版本一致，没有需要更正的字段。")
        try:
            validate_rows(rows)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        checksum = digest(rows)
        existing = db.scalar(select(Dataset).where(Dataset.checksum == checksum))
        if existing is not None:
            return {**dataset_view(existing), "created": False, "source_dataset_id": dataset_id}

        affected = set()
        new_row = rows[index]
        if old_row.get("cohort") != "待检" or new_row.get("cohort") != "待检":
            affected.add(old_row.get("capsule_mm"))
            affected.add(new_row.get("capsule_mm"))
        affected.discard(None)

        display_name = new_name or f"{source.name} · 更正 {sample_id}"
        item = Dataset(
            name=display_name[:120],
            checksum=checksum,
            rows=rows,
            author=actor,
            parent_id=source.id,
            correction={
                "sample_id": sample_id,
                "reason": reason,
                "source_dataset_id": source.id,
                "changed_fields": sorted(updates),
                "before": {key: old_row.get(key) for key in updates},
                "after": {key: rows[index].get(key) for key in updates},
            },
        )
        try:
            with db.begin_nested():
                db.add(item)
                db.flush()
        except IntegrityError:
            existing = db.scalar(select(Dataset).where(Dataset.checksum == checksum))
            if existing is None:
                raise
            return {**dataset_view(existing), "created": False, "source_dataset_id": dataset_id}
        record(db, actor, "dataset_corrected", item.id)
        payload = {**dataset_view(item), "created": True, "source_dataset_id": dataset_id}
        new_dataset_id = item.id
        affected_calibers = sorted(affected)

    try:
        calibrations.refresh_source(
            new_dataset_id,
            calibers=affected_calibers,
            actor=actor,
            reason=f"corrected:{sample_id}",
        )
    except Exception:
        log.exception("Could not enqueue calibration refresh for %s", new_dataset_id)
    return payload


def correct(dataset_id, sample_id=None, changes=None, actor="system", reason=None, **kwargs):
    """Convenience alias for service-level callers and tests."""
    body = dict(kwargs)
    if sample_id is not None:
        body["sample_id"] = sample_id
    if reason is not None:
        body["reason"] = reason
    if changes is not None:
        body["changes"] = changes
    return correct_version(dataset_id, body, actor)


correct_reading = correct
correct_sample = correct
correct_by_sample_id = correct
