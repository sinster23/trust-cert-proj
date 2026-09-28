from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request

from app.database.connection import DatabaseManager
from app.database.repositories.user_repository import UserRepository

from dotenv import load_dotenv
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = DatabaseManager()
    db = await manager.connect()          # fails fast if URI/DB is wrong
    await UserRepository(db).ensure_indexes()
    app.state.db_manager = manager
    yield
    await manager.close()


app = FastAPI(title="Credence API", lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Credence API is running"}


@app.get("/health/db")
async def health_db(request: Request):
    try:
        await request.app.state.db_manager.get_database().command("ping")
        return {"database": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")