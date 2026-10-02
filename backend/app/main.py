from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

load_dotenv()

from app.auth.router import router as auth_router  # M1
from app.database.connection import DatabaseManager
from app.database.repositories.user_repository import UserRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = DatabaseManager()
    db = await manager.connect()          # fails fast if URI/DB is wrong
    await UserRepository(db).ensure_indexes()
    app.state.db_manager = manager
    yield
    await manager.close()


app = FastAPI(title="Credence API", lifespan=lifespan)

app.include_router(auth_router)  # M1


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