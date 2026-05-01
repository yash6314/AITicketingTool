from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.db.database import engine, Base
from app.routes import email_routes
from app.routes import ticket_routes
from app.routes import approval_routes


# 👇 import models
from app.models import email, ticket, reply

app = FastAPI()
app.include_router(email_routes.router)
app.include_router(ticket_routes.router)
app.include_router(approval_routes.router)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# optional (won’t recreate since tables already exist)
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "API Running"}


@app.get("/dashboard")
def dashboard():
    return FileResponse(static_dir / "index.html")

@app.get("/test-db")
def test_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"db_status": "connected"}
