import json
import logging
import math
from datetime import timedelta

from sqlalchemy import and_, or_, select, update

from src.business.algorithm import analyze, validate_rows
from src.business.detector import Detector
from src.business.profile import PROFILE
from src.config.settings import ARTIFACTS, Session
from src.constants.workflow import Stage
from src.models.base import utcnow
from src.models.dataset import Dataset
from src.models.run import Run
from src.services import calibrations
from src.services.audit import record
from src.services.exports import result_keys
from src.utils.csv_data import render_csv

log = logging.getLogger(__name__)
LEASE = timedelta(minutes=10)
MAX_ATTEMPTS = 3


def claim():
    expired = utcnow() - LEASE
    stale = and_(Run.status == Stage.RUNNING.value, Run.started_at < expired)
    available = or_(Run.status == Stage.QUEUED.value, stale)
    with Session.begin() as db:
        exhausted = db.scalars(select(Run).where(stale, Run.attempts >= MAX_ATTEMPTS).with_for_update(skip_locked=True))
        for run in exhausted:
            run.status = Stage.FAILED.value
            run.error = "后台任务多次中断。请提交新的计算单。"
            run.finished_at = utcnow()
            record(db, "worker", "run_failed", run.id)
        run = db.scalar(
            select(Run).where(available, Run.attempts < MAX_ATTEMPTS)
            .order_by(Run.created_at, Run.id).limit(1).with_for_update(skip_locked=True)
        )
        if run is None:
            return None
        run.status = Stage.RUNNING.value
        run.lease = new_id()
        run.started_at = utcnow()
        run.attempts += 1
        dataset = db.get(Dataset, run.dataset_id)
        return run.id, run.lease, run.parameter, dataset.rows


def new_id():
    from src.models.base import new_id as _new_id
    return _new_id()


def verify_result(result):
    if not result["rows"]:
        raise ValueError("当前参数没有得到可交接的结果。请检查数据并调整参数。")
    samples = set()
    chart = PROFILE["chart"]["key"]
    for row in result["rows"]:
        if not set(result_keys()).issubset(row) or row["sample_id"] in samples:
            raise ValueError("算法结果包含重复样本或缺少导出列。")
        if not isinstance(row[chart], (float, int)) or not math.isfinite(row[chart]):
            raise ValueError("算法结果包含无效的图表数值。")
        samples.add(row["sample_id"])
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result


def _line_versions_for_calibration(calibration, run, mode):
    versions = calibration.source_versions or {}
    fit_version = versions.get("fit") or versions.get("fit_dataset_id") or calibration.fit_dataset_id or calibration.dataset_id
    threshold_version = (
        versions.get("threshold")
        or versions.get("threshold_dataset_id")
        or calibration.threshold_dataset_id
        or calibration.dataset_id
    )
    return {
        "fit_version": fit_version,
        "threshold_version": threshold_version,
        "inspection_version": run.dataset_id,
        "candidate_version": run.dataset_id,
        "calibration_id": calibration.id,
        "line_mode": mode,
    }


def prepare_screening(db, run: Run, rows: list[dict]):
    """Resolve atomic model/line pairs or identify a missing-line hold."""
    groups = validate_rows(rows)
    detectors: dict[str, Detector] = {}
    versions: dict[str, dict] = {}
    held: list[dict] = []

    for caliber, group in groups.items():
        candidates = group["待检"]
        if not candidates:
            continue
        resolution = calibrations.resolve_line(db, caliber, run.parameter)
        calibration = resolution["calibration"]
        if calibration is not None:
            detectors[caliber] = calibrations.load_detector(db, calibration)
            mode = resolution["mode"]
            if abs(float(calibration.quantile) - float(run.parameter)) > 1e-12:
                detectors[caliber] = detectors[caliber].for_quantile(float(run.parameter))
                mode = "fallback_old_line_requantiled"
            versions[caliber] = _line_versions_for_calibration(
                calibration, run, mode
            )
            continue

        pending = resolution["pending"]
        if pending is not None:
            if pending.status == Stage.RUNNING.value:
                reason = f"{caliber} mm 新复检线正在计算，且暂无仍可信的同口径旧线，已暂缓排队。"
            else:
                reason = f"{caliber} mm 新复检线等待重算，且暂无仍可信的同口径旧线，已暂缓排队。"
            held.append({
                "caliber": caliber,
                "reason": reason,
                "calibration_id": pending.id,
                "samples": [row["sample_id"] for row in candidates],
            })
            continue

        # No recomputation is already queued for this key: bootstrap the
        # atomic model/line pair in this job for backwards-compatible direct
        # service/worker usage.
        detector = Detector.train(group["参照"], group["留出"], caliber, run.parameter)
        calibration_id = calibrations.persist_detector(
            dataset_id=run.dataset_id,
            caliber=caliber,
            quantile=run.parameter,
            detector=detector,
            actor=run.actor,
            reason="screening_run_bootstrap",
        )
        detectors[caliber] = detector
        versions[caliber] = {
            "fit_version": run.dataset_id,
            "threshold_version": run.dataset_id,
            "inspection_version": run.dataset_id,
            "candidate_version": run.dataset_id,
            "calibration_id": calibration_id,
            "line_mode": "new_line_atomic_switch",
        }

    return detectors, versions, held


def _hold_run(run_id, lease, held, versions):
    queue = []
    reasons = []
    for item in held:
        reasons.append(item["reason"])
        for sample_id in item["samples"]:
            queue.append({"sample_id": sample_id, "caliber": item["caliber"], "reason": item["reason"]})
    reason = " ".join(reasons)
    with Session.begin() as db:
        change = db.execute(
            update(Run)
            .where(Run.id == run_id, Run.lease == lease, Run.status == Stage.RUNNING.value)
            .values(
                status=Stage.HELD.value,
                hold_reason=reason,
                held_queue=queue,
                line_versions=list(versions.values()),
                error=None,
            )
        )
        if change.rowcount:
            record(db, "worker", "run_held", run_id)
    return bool(change.rowcount)


def execute(job):
    run_id, lease, parameter, rows = job
    artifact = None
    result = None
    error = None
    held = False
    try:
        with Session() as db:
            run = db.get(Run, run_id)
            if run is None or run.lease != lease or run.status != Stage.RUNNING.value:
                return
            detectors, versions, held_groups = prepare_screening(db, run, rows)
        if held_groups:
            held = _hold_run(run_id, lease, held_groups, versions)
            return
        source_versions = {caliber: item for caliber, item in versions.items()}
        result = verify_result(analyze(rows, parameter, versions=source_versions, detectors=detectors))
        artifact = f"{run_id}-{lease}.csv"
        path = ARTIFACTS / artifact
        temporary = path.with_suffix(".tmp")
        temporary.write_text("\ufeff" + render_csv(result["rows"], result_keys(), protect=True), encoding="utf-8")
        temporary.replace(path)
    except ValueError as exc:
        error = str(exc)
    except Exception:
        log.exception("Run %s failed", run_id)
        error = "计算或导出失败。请检查输入并重新提交。"
    if held:
        return
    if error:
        result = None
    stage = Stage.FAILED.value if error else Stage.SUCCEEDED.value
    with Session.begin() as db:
        values = dict(
            status=stage,
            result=result,
            artifact=artifact if not error else None,
            error=error,
            finished_at=utcnow(),
        )
        if not error and result is not None:
            values["line_versions"] = result.get("source_versions")
            values["hold_reason"] = None
            values["held_queue"] = []
        change = db.execute(update(Run).where(Run.id == run_id, Run.lease == lease, Run.status == Stage.RUNNING.value).values(**values))
        if change.rowcount:
            record(db, "worker", f"run_{stage}", run_id)
    if artifact and (error or not change.rowcount):
        (ARTIFACTS / artifact).unlink(missing_ok=True)
