from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StringConstraints

from src.constants.workflow import Decision

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=1000)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Request):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class Import(Request):
    name: Name
    csv: Annotated[str, StringConstraints(min_length=1, max_length=1_000_000)]


class RunRequest(Request):
    dataset_id: Annotated[str, StringConstraints(min_length=36, max_length=36)]
    label: Name
    parameter: FiniteFloat


class ReviewRequest(Request):
    decision: Decision
    samples: Annotated[list[Annotated[str, StringConstraints(min_length=1, max_length=120)]], Field(max_length=500)]
    note: LongText


class CorrectionRequest(BaseModel):
    # Direct field corrections (e.g. {"current": 1.86}) are accepted in
    # addition to nested values/changes/corrections payloads.
    model_config = ConfigDict(extra="allow")

    sample_id: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    dataset_id: Annotated[str, StringConstraints(min_length=36, max_length=36)] | None = None
    name: Name | None = None
    reason: OptionalText | None = None
    note: OptionalText | None = None
    values: Any | None = None
    changes: Any | None = None
    corrections: Any | None = None
    data: Any | None = None
    payload: Any | None = None
    row: Any | None = None
    reading: Any | None = None
    fields: Any | None = None
