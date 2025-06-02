"""Modelo para validar datos de entrada y salida en la API."""


from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from typing import Optional

Base = declarative_base()


class App(BaseModel):
    """Modelo User para validar datos de entrada y salida en la API."""
    id: Optional[int] = None
    status: str

    class Config(object):
        """Configuración del modelo."""
        orm_mode = True
