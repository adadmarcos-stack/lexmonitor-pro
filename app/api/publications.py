from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.publication import Publication

router = APIRouter(prefix="/publications", tags=["Publications"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def list_publications(db: Session = Depends(get_db)):
    items = db.query(Publication).order_by(Publication.id.desc()).all()

    return [
        {
            "id": item.id,
            "source": item.source,
            "process_number": item.process_number,
            "publication_date": item.publication_date,
            "availability_date": item.availability_date,
            "court": item.court,
            "journal": item.journal,
            "chamber": item.chamber,
            "court_division": item.court_division,
            "page_number": item.page_number,
            "title": item.title,
            "raw_text": item.raw_text[:1000]
        }
        for item in items
    ]