"""Versioned cabinet-level calibration lines and atomic switching."""

import logging
import pickle
from datetime import timedelta

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from src.business.algorithm import validate_rows
from src.business.detector import Detector
from src.business.profile import PROFILE
from src.config.settings import ARTIFACTS, Session, redis
from src.constants.workflow import CalibrationStage, Stage
from src.models.audit import Event  # noqa: F401  # ensures metadata registration
from src.models.base import new_id, utcnow
from src.models.calibration import Calibration
from src.models.dataset import Dataset
from src.models.run import Run
from src.schemas.resources import calibration_view
from src.services.audit import record
from src.worker_wake import wake_worker

log = logging.getLogger(__name__)
LEASE = timedelta(minutes=10)
MAX_ATTEMPTS = 3


def quantile_key(quantile: float) -> int:
    """Exact integer key so MySQL FLOAT rounding cannot split one line key."""
    return int(round(float(quantile) * 10_000))


def list_calibrations():
    with Session() as db:
        rows = db.scalars(select(Calibration).order_by(Calibration.created_at.desc(), Calibration.id.desc()).limit(200))
        return [calibration_view(row) for row in rows]


def require(db, calibration_id):
    item = db.get(Calibration, calibration_id)
    if item is None:
        raise HTTPException(404, "复检线版本不存在。")
    return item


def _quantiles_for(db, calibers, quantiles):
    result = {}
    default_q = float(PROFILE["parameter"]["default"])
    for caliber in calibers:
        values = list(quantiles or [])
        if not values:
            values = list(db.scalars(
                select(Calibration.quantile).where(Calibration.caliber == caliber).distinct()
            ))
        if not values:
            values = [default_q]
        result[caliber] = sorted({float(value) for value in values})
    return result


def enqueue_source(db, dataset_id, calibers=None, quantiles=None, actor="system", reason=None):
    """Create pending recomputations for an updated source version.

    Existing active lines are deliberately left active and trusted.  They are
    marked stale, so screening can distinguish a current line from a credible
    fallback while the replacement is being calculated.
    """
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise ValueError("数据版本不存在。")
    if calibers is None:
        calibers = sorted({str(row["capsule_mm"]) for row in dataset.rows})
    queued = []
    quantile_map = _quantiles_for(db, calibers, quantiles)
    for caliber in calibers:
        for quantile in quantile_map[caliber]:
            qkey = quantile_key(quantile)
            existing_pending = db.scalar(
                select(Calibration).where(
                    Calibration.dataset_id == dataset_id,
                    Calibration.caliber == caliber,
                    Calibration.quantile_key == qkey,
                    Calibration.status.in_([CalibrationStage.PENDING.value, CalibrationStage.RUNNING.value]),
                ).limit(1)
            )
            if existing_pending is not None:
                queued.append(existing_pending)
                continue
            active_lines = db.scalars(
                select(Calibration).where(
                    Calibration.caliber == caliber,
                    Calibration.quantile_key == qkey,
                    Calibration.active.is_(True),
                ).with_for_update()
            ).all()
            supersedes_id = None
            for line in active_lines:
                line.stale = True
                supersedes_id = line.id
            calibration = Calibration(
                caliber=caliber,
                quantile=quantile,
                quantile_key=quantile_key(quantile),
                dataset_id=dataset_id,
                fit_dataset_id=dataset_id,
                threshold_dataset_id=dataset_id,
                status=CalibrationStage.PENDING.value,
                active=False,
                stale=False,
                trusted=True,
                actor=actor,
                supersedes_id=supersedes_id,
                source_versions={
                    "fit": dataset_id,
                    "threshold": dataset_id,
                    "fit_dataset_id": dataset_id,
                    "threshold_dataset_id": dataset_id,
                    "reason": reason,
                },
            )
            db.add(calibration)
            db.flush()
            record(db, actor, "calibration_queued", calibration.id)
            queued.append(calibration)
    return queued


def refresh_source(dataset_id, calibers=None, quantiles=None, actor="system", reason=None):
    with Session.begin() as db:
        items = enqueue_source(db, dataset_id, calibers, quantiles, actor, reason)
        ids = [item.id for item in items]
    if ids:
        wake_worker(ids[0])
    return ids


def claim():
    expired = utcnow() - LEASE
    stale = and_(
        Calibration.status == CalibrationStage.RUNNING.value,
        Calibration.started_at < expired,
    )
    available = or_(Calibration.status == CalibrationStage.PENDING.value, stale)
    with Session.begin() as db:
        exhausted = db.scalars(
            select(Calibration).where(stale, Calibration.attempts >= MAX_ATTEMPTS).with_for_update(skip_locked=True)
        )
        for item in exhausted:
            item.status = CalibrationStage.FAILED.value
            item.error = "复检线计算多次中断，请重新触发计算。"
            item.finished_at = utcnow()
            record(db, "worker", "calibration_failed", item.id)
        item = db.scalar(
            select(Calibration)
            .where(available, Calibration.attempts < MAX_ATTEMPTS)
            .order_by(Calibration.created_at, Calibration.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if item is None:
            return None
        item.status = CalibrationStage.RUNNING.value
        item.lease = new_id()
        item.started_at = utcnow()
        item.attempts += 1
        return item.id, item.lease


def _quality(detector: Detector) -> dict:
    return {
        "fit_rows": detector.fit_rows,
        "fit_cabinets": len(detector.fit_cabinets),
        "threshold_rows": detector.calibration_rows,
        "threshold_cabinets": len(detector.calibration_cabinets),
        "excluded_same_cabinet_rows": detector.excluded_same_cabinet_rows,
        "cabinet_scores": detector.cabinet_scores,
        "credible": detector.credible,
        "minimum_threshold_cabinets": 12,
        "machine_guideline_met": len(detector.calibration_cabinets) >= 12,
    }


def _save_model(calibration_id: str, lease: str, detector: Detector) -> str | None:
    name = f"calibration-{calibration_id}-{lease}.pkl"
    try:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        path = ARTIFACTS / name
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            pickle.dump(detector, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(path)
        return name
    except OSError:
        log.exception("Could not persist model artifact for %s", calibration_id)
        return None


def persist_detector(
    *,
    dataset_id: str,
    caliber: str,
    quantile: float,
    detector: Detector,
    actor: str = "worker",
    reason: str | None = None,
) -> str:
    """Persist and atomically activate a newly fitted model/line pair."""
    lease = new_id()
    artifact = _save_model("inline", lease, detector)
    with Session.begin() as db:
        calibration = Calibration(
            caliber=caliber,
            quantile=quantile,
            quantile_key=quantile_key(quantile),
            dataset_id=dataset_id,
            fit_dataset_id=dataset_id,
            threshold_dataset_id=dataset_id,
            status=CalibrationStage.READY.value,
            active=detector.credible,
            stale=False,
            trusted=detector.credible,
            threshold=detector.threshold,
            model_artifact=artifact,
            quality=_quality(detector),
            actor=actor,
            finished_at=utcnow(),
            source_versions={
                "fit": dataset_id,
                "threshold": dataset_id,
                "fit_dataset_id": dataset_id,
                "threshold_dataset_id": dataset_id,
                "reason": reason or "calculated_with_screening_run",
            },
        )
        db.add(calibration)
        db.flush()
        if detector.credible:
            _switch_active(db, calibration)
        record(db, actor, "calibration_activated" if detector.credible else "calibration_untrusted", calibration.id)
        return calibration.id


def _switch_active(db, calibration: Calibration):
    old_lines = db.scalars(
        select(Calibration)
        .where(
            Calibration.caliber == calibration.caliber,
            Calibration.quantile_key == calibration.quantile_key,
            Calibration.calibration_group == calibration.calibration_group,
            Calibration.id != calibration.id,
            Calibration.active.is_(True),
        )
        .with_for_update()
    ).all()
    for old in old_lines:
        old.active = False
        old.stale = False
        old.status = CalibrationStage.SUPERSEDED.value
    calibration.active = True
    calibration.stale = False
    calibration.trusted = True
    calibration.status = CalibrationStage.READY.value
    _requeue_held_runs(db, calibration.caliber, calibration.quantile)


def _requeue_held_runs(db, caliber: str, quantile: float):
    # Requeue all held runs for this quantile.  A run touching several
    # calibers will simply be held again by the executor if another line is
    # still unavailable.
    runs = db.scalars(
        select(Run).where(Run.status == Stage.HELD.value).with_for_update()
    ).all()
    for run in runs:
        if abs(float(run.parameter) - float(quantile)) > 1e-9:
            continue
        run.status = Stage.QUEUED.value
        run.lease = None
        run.started_at = None
        record(db, "worker", "run_requeued", run.id)


def execute(job):
    calibration_id, lease = job
    detector = None
    artifact = None
    error = None
    try:
        with Session() as db:
            calibration = require(db, calibration_id)
            if calibration.lease != lease:
                return
            dataset = db.get(Dataset, calibration.dataset_id)
            if dataset is None:
                raise ValueError("校准线引用的数据版本不存在。")
            caliber = calibration.caliber
            quantile = calibration.quantile
            rows = dataset.rows
        groups = validate_rows(rows)
        if caliber not in groups:
            raise ValueError(f"复检线口径 {caliber} 不在数据版本中。")
        group = groups[caliber]
        detector = Detector.train(group["参照"], group["留出"], caliber, quantile)
        artifact = _save_model(calibration_id, lease, detector)
    except ValueError as exc:
        error = str(exc)
    except Exception:
        log.exception("Calibration %s failed", calibration_id)
        error = "复检线计算失败，请检查输入数据后重试。"

    with Session.begin() as db:
        calibration = db.get(Calibration, calibration_id)
        if calibration is None or calibration.lease != lease or calibration.status != CalibrationStage.RUNNING.value:
            if artifact:
                (ARTIFACTS / artifact).unlink(missing_ok=True)
            return
        if error:
            calibration.status = CalibrationStage.FAILED.value
            calibration.error = error
            calibration.finished_at = utcnow()
            record(db, "worker", "calibration_failed", calibration.id)
            return
        calibration.threshold = detector.threshold
        calibration.model_artifact = artifact
        calibration.quality = _quality(detector)
        calibration.error = None
        calibration.finished_at = utcnow()
        calibration.source_versions = {
            **(calibration.source_versions or {}),
            "fit": calibration.fit_dataset_id or calibration.dataset_id,
            "threshold": calibration.threshold_dataset_id or calibration.dataset_id,
            "fit_dataset_id": calibration.fit_dataset_id or calibration.dataset_id,
            "threshold_dataset_id": calibration.threshold_dataset_id or calibration.dataset_id,
        }
        if detector.credible:
            _switch_active(db, calibration)
            record(db, "worker", "calibration_activated", calibration.id)
        else:
            calibration.status = CalibrationStage.READY.value
            calibration.active = False
            calibration.trusted = False
            record(db, "worker", "calibration_untrusted", calibration.id)


def resolve_line(db, caliber: str, quantile: float) -> dict:
    """Choose current line, stale-but-trusted fallback, or missing state."""
    qkey = quantile_key(quantile)
    active = db.scalar(
        select(Calibration)
        .where(
            Calibration.caliber == caliber,
            Calibration.quantile_key == qkey,
            Calibration.active.is_(True),
            Calibration.status == CalibrationStage.READY.value,
        )
        .order_by(Calibration.created_at.desc(), Calibration.id.desc())
        .limit(1)
    )
    pending = db.scalar(
        select(Calibration)
        .where(
            Calibration.caliber == caliber,
            Calibration.quantile_key == qkey,
            Calibration.status.in_([CalibrationStage.PENDING.value, CalibrationStage.RUNNING.value]),
        )
        .order_by(Calibration.created_at.desc(), Calibration.id.desc())
        .limit(1)
    )
    if active is not None and active.trusted:
        return {
            "mode": "fallback_old_line" if active.stale else "current",
            "calibration": active,
            "pending": pending,
        }
    same_caliber_lines = db.scalars(
        select(Calibration).where(
            Calibration.caliber == caliber,
            Calibration.active.is_(True),
            Calibration.trusted.is_(True),
            Calibration.status == CalibrationStage.READY.value,
        )
    ).all()
    if same_caliber_lines:
        fallback = min(
            same_caliber_lines,
            key=lambda item: (abs(float(item.quantile) - float(quantile)), -item.created_at.timestamp() if item.created_at else 0),
        )
        return {"mode": "fallback_old_line", "calibration": fallback, "pending": pending}
    return {"mode": "missing", "calibration": None, "pending": pending}


def load_detector(db, calibration: Calibration) -> Detector:
    if calibration.model_artifact:
        path = ARTIFACTS / calibration.model_artifact
        if path.is_file():
            try:
                with path.open("rb") as handle:
                    detector = pickle.load(handle)
                if isinstance(detector, Detector):
                    return detector
            except (OSError, pickle.PickleError, AttributeError, ImportError):
                log.exception("Could not load model artifact %s", calibration.model_artifact)
    dataset_id = calibration.fit_dataset_id or calibration.dataset_id
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise ValueError("拟合模型引用的数据版本不存在。")
    groups = validate_rows(dataset.rows)
    group = groups[calibration.caliber]
    detector = Detector.fit_model(group["参照"], calibration.caliber)
    quality = calibration.quality or {}
    cabinet_scores = quality.get("cabinet_scores") or {}
    return detector.with_line(
        calibration.threshold,
        quantile=calibration.quantile,
        calibration_rows=quality.get("threshold_rows", 0),
        calibration_cabinets=tuple(cabinet_scores) or tuple(range(quality.get("threshold_cabinets", 0))),
        excluded_same_cabinet_rows=quality.get("excluded_same_cabinet_rows", 0),
        credible=bool(calibration.trusted),
        cabinet_scores=cabinet_scores,
    )


def wake(calibration_id: str):
    wake_worker(calibration_id)
