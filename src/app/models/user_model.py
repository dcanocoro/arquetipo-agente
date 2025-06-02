"""Modelo User para SQLAlchemy ORM."""


from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class UserTable(Base):
    """Modelo User para SQLAlchemy ORM."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
