from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "segredo_super_secreto"
ALGORITHM = "HS256"

@router.post("/login")
def login(email: str, password: str):
    db: Session = SessionLocal()

    try:
        db_user = db.query(User).filter(User.email == email).first()

        if not db_user:
            raise HTTPException(status_code=400, detail="Usuário não encontrado")

        if not pwd_context.verify(password, db_user.hashed_password):
            raise HTTPException(status_code=400, detail="Credenciais inválidas")

        token_data = {
            "sub": db_user.email,
            "exp": datetime.utcnow() + timedelta(hours=2)
        }

        token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        return {
            "access_token": token,
            "token_type": "bearer"
        }
    finally:
        db.close()