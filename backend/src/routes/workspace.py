from fastapi import APIRouter, Depends, HTTPException

from src.business.profile import PROFILE
from src.controllers import workspace
from src.routes.dependencies import analyst, current_account, reviewer
from src.schemas.requests import CorrectionRequest, Import, ReviewRequest, RunRequest
from src.services import audit, calibrations, datasets, exports, reviews, runs

router = APIRouter(dependencies=[Depends(current_account)])


@router.get("/profile")
def profile():
    return PROFILE


@router.get("/datasets")
def list_datasets():
    return datasets.list_datasets()


@router.post("/datasets")
def import_dataset(body: Import, account=Depends(analyst)):
    return datasets.ingest(body.name, body.csv, account.email)


router.add_api_route("/datasets/{dataset_id}", workspace.dataset_details, methods=["GET"])
router.add_api_route("/datasets/{dataset_id}/csv", workspace.dataset_csv, methods=["GET"])


@router.get("/calibrations")
def list_calibrations():
    return calibrations.list_calibrations()


for path in ("/lines", "/thresholds", "/review-lines", "/line-versions"):
    router.add_api_route(path, calibrations.list_calibrations, methods=["GET"])


@router.get("/datasets/{dataset_id}/corrections")
def list_dataset_corrections(dataset_id: str):
    return datasets.list_dataset_corrections(dataset_id)


@router.post("/datasets/{dataset_id}/corrections")
def correct_dataset(dataset_id: str, body: CorrectionRequest, account=Depends(analyst)):
    return datasets.correct_version(dataset_id, body.model_dump(exclude_none=True), account.email)


@router.post("/datasets/{dataset_id}/correct")
def correct_dataset_alias(dataset_id: str, body: CorrectionRequest, account=Depends(analyst)):
    return datasets.correct_version(dataset_id, body.model_dump(exclude_none=True), account.email)


@router.api_route("/datasets/{dataset_id}", methods=["PATCH", "PUT"])
def patch_dataset(dataset_id: str, body: CorrectionRequest, account=Depends(analyst)):
    return datasets.correct_version(dataset_id, body.model_dump(exclude_none=True), account.email)


@router.api_route("/datasets/{dataset_id}/samples/{sample_id}", methods=["PATCH", "PUT", "POST"])
def correct_sample(dataset_id: str, sample_id: str, body: CorrectionRequest, account=Depends(analyst)):
    payload = body.model_dump(exclude_none=True)
    return datasets.correct_version(dataset_id, payload, account.email, path_sample_id=sample_id)


@router.api_route("/datasets/{dataset_id}/rows/{sample_id}", methods=["PATCH", "PUT", "POST"])
def correct_row(dataset_id: str, sample_id: str, body: CorrectionRequest, account=Depends(analyst)):
    payload = body.model_dump(exclude_none=True)
    return datasets.correct_version(dataset_id, payload, account.email, path_sample_id=sample_id)


@router.post("/datasets/{dataset_id}/samples/{sample_id}/correct")
def correct_sample_alias(dataset_id: str, sample_id: str, body: CorrectionRequest, account=Depends(analyst)):
    payload = body.model_dump(exclude_none=True)
    return datasets.correct_version(dataset_id, payload, account.email, path_sample_id=sample_id)


@router.post("/datasets/{dataset_id}/rows/{sample_id}/correct")
def correct_row_alias(dataset_id: str, sample_id: str, body: CorrectionRequest, account=Depends(analyst)):
    payload = body.model_dump(exclude_none=True)
    return datasets.correct_version(dataset_id, payload, account.email, path_sample_id=sample_id)


@router.get("/corrections")
def list_corrections():
    return datasets.list_corrections()


@router.post("/corrections")
def correct_without_dataset(body: CorrectionRequest, account=Depends(analyst)):
    if not body.sample_id:
        raise HTTPException(422, "请提供数据版本 ID 或试转编号。")
    # This alias is useful to clients that include dataset_id in a generic
    # correction command.  Prefer the nested dataset route when possible.
    payload = body.model_dump(exclude_none=True)
    dataset_id = payload.pop("dataset_id", None)
    if not dataset_id:
        raise HTTPException(422, "请提供要更正的数据版本 ID。")
    return datasets.correct_version(dataset_id, payload, account.email)


@router.get("/queue")
def queue():
    return runs.queue_overview()


for path in ("/review-queue", "/recheck-queue", "/machine-queue"):
    router.add_api_route(path, runs.queue_overview, methods=["GET"])


@router.get("/runs/queue")
def run_queue():
    return runs.queue_overview()


@router.get("/runs")
def list_runs(status: str | None = None):
    return runs.list_runs(status)


@router.post("/runs", status_code=202)
def queue_run(body: RunRequest, account=Depends(analyst)):
    return runs.submit(body, account.email)


router.add_api_route("/runs/{run_id}", workspace.run_details, methods=["GET"])
router.add_api_route("/runs/{run_id}/csv", exports.download, methods=["GET"])
router.add_api_route("/runs/{run_id}/handoff.csv", exports.signed_download, methods=["GET"])


@router.post("/runs/{run_id}/review", status_code=201)
def review_run(run_id: str, body: ReviewRequest, account=Depends(reviewer)):
    return reviews.sign(run_id, body, account.email)


router.add_api_route("/reviews", reviews.list_reviews, methods=["GET"])
router.add_api_route("/audit", audit.recent, methods=["GET"])
