"""Modelo User para SQLAlchemy ORM."""


from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class AppTable(Base):
    """Modelo Application para SQLAlchemy ORM."""
    __tablename__ = "applications"  # Rename table to match its purpose

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, nullable=False)
