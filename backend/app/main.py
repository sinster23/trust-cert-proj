# backend/app/main.py

from fastapi import FastAPI

app = FastAPI(title="Credence API")


@app.get("/")
def root():
    return {"message": "Credence API is running"}