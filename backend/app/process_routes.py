"""Read-only routes; authentication and current AD group checks stay in main boundary."""
from fastapi import APIRouter, Query, Request
from app.process_queries import ProcessQueries

router = APIRouter()


def queries(request):
    runtime = request.app.state.runtime
    return ProcessQueries(runtime.engine, clock=runtime.store.clock)


@router.get("/api/processes/stats")
def process_stats(request: Request, view: str = "active", search: str = Query("", max_length=200),
                  state: str | None = None, category: str | None = None, duplicate: bool | None = None,
                  received_from: str | None = None, received_to: str | None = None):
    return queries(request).stats(view=view, search=search, state=state, category=category, duplicate=duplicate,
                                  received_from=received_from, received_to=received_to)


@router.get("/api/processes")
def process_list(request: Request, view: str = "active", search: str = Query("", max_length=200),
                 state: str | None = None, category: str | None = None, duplicate: bool | None = None,
                 received_from: str | None = None, received_to: str | None = None,
                 page: int = Query(1, ge=1, le=100000), page_size: int = Query(25, ge=1, le=50)):
    return queries(request).list(view=view, search=search, state=state, category=category, duplicate=duplicate,
                                 received_from=received_from, received_to=received_to, page=page, page_size=page_size)


@router.get("/api/processes/{key}")
def process_detail(key: str, request: Request):
    return queries(request).detail(key)


@router.get("/api/unknown")
def unknown_attachments(request: Request, view: str = "active", search: str = Query("", max_length=200),
                        page: int = Query(1, ge=1, le=100000), page_size: int = Query(25, ge=1, le=50)):
    return queries(request).unknown(view=view, search=search, page=page, page_size=page_size)


# All mutations use the existing main middleware: current AD group, admin, Origin + CSRF.
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from typing import Literal
from app.processing_decisions import DecisionStore
from app.processing_state import ProcessingStore


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8,max_length=128,pattern=r"^[a-zA-Z0-9_-]+$")
    expected_revision: int = Field(ge=0,strict=True)


class ApprovalInput(DecisionInput):
    finding_revision: int = Field(ge=0,strict=True)
    finding_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["PDF","Zahlungsavis","Mahnung","ignored"]


class ProcessingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1,strict=True)
    preview_enabled: StrictBool
    retry_enabled: StrictBool


def decisions(request):
    runtime=request.app.state.runtime
    return DecisionStore(ProcessingStore(runtime.engine,clock=runtime.store.clock))


def actor(request):
    principal=request.state.principal
    return principal.username+" ("+principal.guid+")"


@router.post("/api/attachments/{key}/approve")
def approve_attachment(key: str, candidate: ApprovalInput, request: Request):
    return decisions(request).approve(key,**candidate.model_dump(),actor=actor(request))


@router.post("/api/processes/{key}/retry")
def retry_process(key: str, candidate: DecisionInput, request: Request):
    return decisions(request).retry(key,**candidate.model_dump(),actor=actor(request))


@router.get("/api/admin/processing")
def processing_settings(request: Request):
    return {**decisions(request).settings(),"can_edit":request.state.principal.role=="admin"}


@router.put("/api/admin/processing")
def processing_settings_write(candidate: ProcessingInput, request: Request):
    return {**decisions(request).save_settings(**candidate.model_dump(),actor=actor(request)),"can_edit":True}
