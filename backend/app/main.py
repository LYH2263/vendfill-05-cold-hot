from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def ensure_schema() -> None:
    """create_all 只建新表；对历史库幂等补齐 lanes.temp_zone（未标温区按热兼容）。"""
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    if "lanes" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("lanes")}
        if "temp_zone" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE lanes ADD COLUMN temp_zone VARCHAR(8) NOT NULL DEFAULT 'hot'"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="VendFill", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
