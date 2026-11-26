from datetime import datetime, timezone


def utc(value: datetime | None):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def dataset_view(dataset, include_rows=False):
    item = {
        "id": dataset.id, "name": dataset.name, "count": len(dataset.rows),
        "checksum": dataset.checksum, "author": dataset.author, "created_at": utc(dataset.created_at),
        "parent_id": getattr(dataset, "parent_id", None),
        "correction": getattr(dataset, "correction", None),
    }
    if include_rows:
        item["rows"] = dataset.rows
    return item


def calibration_view(calibration):
    return {
        "id": calibration.id,
        "caliber": calibration.caliber,
        "quantile": float(calibration.quantile),
        "quantile_key": getattr(calibration, "quantile_key", None),
        "dataset_id": calibration.dataset_id,
        "fit_dataset_id": calibration.fit_dataset_id or calibration.dataset_id,
        "threshold_dataset_id": calibration.threshold_dataset_id or calibration.dataset_id,
        "status": calibration.status,
        "active": bool(calibration.active),
        "stale": bool(calibration.stale),
        "invalidated": bool(calibration.stale),
        "trusted": bool(calibration.trusted),
        "usable": bool(calibration.active and calibration.trusted and calibration.status == "ready"),
        "current": bool(calibration.active and not calibration.stale and calibration.status == "ready"),
        "threshold": calibration.threshold,
        "quality": calibration.quality,
        "source_versions": calibration.source_versions,
        "error": calibration.error,
        "actor": calibration.actor,
        "created_at": utc(calibration.created_at),
        "started_at": utc(calibration.started_at),
        "finished_at": utc(calibration.finished_at),
    }


def run_view(run, include_result=False):
    item = {
        "id": run.id, "dataset_id": run.dataset_id, "label": run.label, "parameter": run.parameter,
        "status": run.status, "error": run.error, "actor": run.actor,
        "hold_reason": getattr(run, "hold_reason", None),
        "held_queue": getattr(run, "held_queue", None) or [],
        "line_versions": getattr(run, "line_versions", None) or [],
        "created_at": utc(run.created_at), "started_at": utc(run.started_at),
        "finished_at": utc(run.finished_at),
    }
    if include_result:
        item["result"] = run.result
    return item


def review_view(review):
    return {
        "id": review.id, "run_id": review.run_id, "decision": review.decision,
        "samples": review.samples, "note": review.note, "reviewer": review.reviewer,
        "created_at": utc(review.created_at),
    }


def audit_view(event):
    return {"actor": event.actor, "action": event.action, "subject": event.subject, "created_at": utc(event.created_at)}
