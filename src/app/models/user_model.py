"""Modelo User para SQLAlchemy ORM."""


from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class AppTable(Base):
    """Modelo User para SQLAlchemy ORM."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, nullable=False)
