"""Modelo para validar datos de entrada y salida en la API."""


from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from typing import Optional

Base = declarative_base()


class User(BaseModel):
    """Modelo User para validar datos de entrada y salida en la API."""
    id: Optional[int] = None
    email: str
    full_name: Optional[str] = None

    class Config(object):
        """Configuración del modelo."""
        orm_mode = True
