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
