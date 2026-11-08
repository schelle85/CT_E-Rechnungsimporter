from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.database import make_engine
from app.demo import ITEMS

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = make_engine()
    yield
    app.state.engine.dispose()

app = FastAPI(title="Invoice importer – AP01 preview", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

@app.get("/api/health/live")
def live():
    return {"status": "alive", "mode": "synthetic-preview"}

@app.get("/api/health/ready")
def ready():
    try:
        with app.state.engine.connect() as connection:
            marker = connection.execute(text("SELECT instance_id FROM app_metadata WHERE singleton = 1")).scalar_one()
        return {"status": "ready", "mode": "synthetic-preview", "instance_id": marker}
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "not-ready"})

@app.get("/api/demo/processes")
def processes():
    return {"synthetic": True, "items": ITEMS}

@app.api_route("/api/admin/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def admin_denied(path: str):
    raise HTTPException(status_code=403, detail="Administration is unavailable in the synthetic preview.")
