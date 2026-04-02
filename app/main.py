from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.users import router as users_router
from app.api import auth
from app.api.oab import router as oab_router
from app.database import Base, engine

app = FastAPI(
    title="LexMonitor Pro",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(users_router)
app.include_router(auth.router)
app.include_router(oab_router)

@app.get("/")
def root():
    return {"message": "LexMonitor Pro no ar"}

@app.get("/monitor")
def monitor():
    return [
        {
            "processo": "0001234-56.2024.8.13.0701",
            "cliente": "João da Silva",
            "movimento": "Prazo aberto de 15 dias",
            "data": "28/03/2026"
        },
        {
            "processo": "0009876-12.2023.8.13.0701",
            "cliente": "Empresa XPTO",
            "movimento": "Sentença publicada",
            "data": "28/03/2026"
        }
    ]