from contextlib import asynccontextmanager
from dataclasses import asdict
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.process_routes import router as process_router
from app.preview import PreviewManager
from app.errors import AccessError
from app.security import COOKIE, build_runtime
from app.settings import LoginInput, ConfigInput, LdapSettings

def set_cookie(response, token, authenticated=False):
    response.set_cookie(COOKIE,token,max_age=28800 if authenticated else 600,
        secure=True,httponly=True,samesite="strict",path="/")

def clear_cookie(response):
    response.delete_cookie(COOKIE,secure=True,httponly=True,samesite="strict",path="/")

def create_app(runtime_factory=build_runtime):
    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime=runtime_factory()
        app.state.preview=PreviewManager(app.state.runtime.engine)
        yield
        app.state.runtime.engine.dispose()

    app=FastAPI(title="Invoice importer",docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return JSONResponse(status_code=422,content={"detail":"Ungültige Eingaben."})

    @app.exception_handler(AccessError)
    async def access_error(request,exc):
        response=JSONResponse(status_code=exc.status,content={"detail":exc.detail})
        if exc.status==401 and request.url.path!="/api/auth/login":
            clear_cookie(response)
        response.headers["Cache-Control"]="no-store"
        return response

    @app.middleware("http")
    async def boundary(request,call_next):
        runtime=app.state.runtime
        public={"/api/health/live","/api/health/ready","/api/auth/session","/api/auth/login"}
        try:
            if request.url.path.startswith("/api/") and request.url.path not in public:
                row,principal=await run_in_threadpool(runtime.require,request,request.url.path!="/api/auth/logout")
                request.state.principal=principal
                request.state.session=row
                if request.method not in ("GET","HEAD","OPTIONS"):
                    runtime.csrf(request,row)
                    if request.url.path!="/api/auth/logout" and principal.role!="admin":
                        raise AccessError(403,"Verwaltungsrecht erforderlich.")
            response=await call_next(request)
        except AccessError as exc:
            response=await access_error(request,exc)
        except SQLAlchemyError:
            response=JSONResponse(status_code=503,content={"detail":"Dienst vorübergehend nicht bereit."})
        response.headers["Cache-Control"]="no-store"
        return response

    @app.get("/api/health/live")
    def live():
        return {"status":"alive","mode":"journal"}

    @app.get("/api/health/ready")
    def ready():
        try:
            with app.state.runtime.engine.connect() as connection:
                marker=connection.execute(text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
                connection.execute(text("SELECT singleton FROM configuration_head WHERE singleton=1")).scalar_one()
            return {"status":"ready","mode":"journal","instance_id":marker}
        except SQLAlchemyError:
            return JSONResponse(status_code=503,content={"status":"not-ready"})

    @app.get("/api/auth/session")
    def session_state(request:Request):
        runtime=app.state.runtime
        if request.headers.get("sec-fetch-site")=="cross-site" or request.headers.get("origin",runtime.origin)!=runtime.origin:
            raise AccessError(403,"Sitzungsanforderung nicht von dieser Anwendung.")
        row=runtime.store.session(request.cookies.get(COOKIE,""))
        if row and row["guid"]:
            row,principal=runtime.require(request)
            return {"authenticated":True,"user":asdict(principal),"csrf_token":row["csrf"]}
        if row is None:
            runtime.store.throttle("session-peer",request.client.host if request.client else "unknown",60,60)
            token,csrf=runtime.store.new_session()
            response=JSONResponse({"authenticated":False,"csrf_token":csrf})
            set_cookie(response,token)
            return response
        return {"authenticated":False,"csrf_token":row["csrf"]}

    @app.post("/api/auth/login")
    def login(request:Request,credentials:LoginInput):
        token,data=app.state.runtime.login(request,credentials)
        response=JSONResponse(data)
        set_cookie(response,token,True)
        return response

    @app.post("/api/auth/logout")
    def logout(request:Request):
        app.state.runtime.store.revoke(request.cookies.get(COOKIE,""))
        response=JSONResponse({"authenticated":False})
        clear_cookie(response)
        return response

    app.include_router(process_router)

    def admin(request):
        if request.state.principal.role!="admin":
            raise AccessError(403,"Verwaltungsrecht erforderlich.")

    @app.get("/api/admin/config")
    def config_read(request:Request):
        # Both authenticated roles may read safe metadata; do not decrypt secrets.
        row=app.state.runtime.store.active()
        cfg=LdapSettings.model_validate_json(row["settings"])
        return {"version":row["id"],"settings":cfg.model_dump(),"password_set":True,
                "can_edit":request.state.principal.role=="admin"}

    @app.put("/api/admin/config")
    def config_write(request:Request,candidate:ConfigInput):
        admin(request)
        version=app.state.runtime.save_config(request.state.principal,candidate)
        response=JSONResponse({"version":version,"reauthenticate":True})
        clear_cookie(response)
        return response

    @app.get("/api/admin/audit")
    def audit_read(request:Request):
        return {"items":app.state.runtime.store.audit_rows()}

    return app

app=create_app()
