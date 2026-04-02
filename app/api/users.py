from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import User
from app.schemas import UserCreate
from app.core.security import hash_password

router = APIRouter()

@router.post("/users/create")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        new_user = User(
            name=user.name,
            email=user.email,
            hashed_password=hash_password(user.password)
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="E-mail já cadastrado"
        )