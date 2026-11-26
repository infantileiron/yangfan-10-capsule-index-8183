import logging

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import select

from src.business.profile import PROFILE
from src.config.settings import Session, redis
from src.constants.workflow import Stage
from src.models.run import Run
from src.schemas.resources import run_view
from src.services import datasets
from src.services.audit import record

WAKE_KEY = "workbench:wake"
logger = logging.getLogger(__name__)


def require(db, run_id):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "计算单不存在。")
    return run


def list_runs(status: str | None = None):
    with Session() as db:
        query = select(Run).order_by(Run.created_at.desc(), Run.id.desc())
        if status:
            query = query.where(Run.status == status)
        return [run_view(run) for run in db.scalars(query)]


def queue_overview():
    with Session() as db:
        runs = db.scalars(
            select(Run)
            .where(Run.status.in_([Stage.QUEUED.value, Stage.RUNNING.value, Stage.HELD.value]))
            .order_by(Run.created_at, Run.id)
        ).all()
        held_items = []
        for run in runs:
            if run.status == Stage.HELD.value:
                for item in run.held_queue or []:
                    held_items.append({"run_id": run.id, "label": run.label, **item})
        return {
            "runs": [run_view(run) for run in runs],
            "held": held_items,
            "held_count": len(held_items),
        }


def submit(body, actor):
    control = PROFILE["parameter"]
    if not control["min"] <= body.parameter <= control["max"]:
        raise HTTPException(422, f"「{control['label']}」超出允许范围。")
    with Session.begin() as db:
        datasets.require(db, body.dataset_id)
        run = Run(dataset_id=body.dataset_id, label=body.label, parameter=body.parameter, actor=actor)
        db.add(run)
        db.flush()
        record(db, actor, "run_queued", run.id)
        response = run_view(run)
    try:
        with redis.pipeline() as commands:
            commands.lpush(WAKE_KEY, run.id)
            commands.ltrim(WAKE_KEY, 0, 99)
            commands.execute()
    except RedisError:
        logger.warning("Redis wake signal failed for %s. Worker will poll the database.", run.id)
    return response
