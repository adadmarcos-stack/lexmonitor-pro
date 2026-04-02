from sqlalchemy import Column, Integer, String, Text
from app.core.database import Base


class Publication(Base):
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)
    process_number = Column(String, nullable=True, index=True)
    publication_date = Column(String, nullable=True, index=True)
    availability_date = Column(String, nullable=True, index=True)
    court = Column(String, nullable=True)
    journal = Column(String, nullable=True)
    chamber = Column(String, nullable=True)
    court_division = Column(String, nullable=True)
    page_number = Column(String, nullable=True)
    title = Column(String, nullable=True)
    raw_text = Column(Text, nullable=False)