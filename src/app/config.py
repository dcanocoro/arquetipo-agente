"""
    Fichero de configuración del proyecto. Empleado para cargar las
    variables de entorno y definir la configuración del proyecto.
"""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """
    Clase de configuración para la aplicación.
    """

    # General
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "FastAPI Microservice")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Orchestrator
    ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "https://orchestrator:8000")
    PROMPT_ID: str = os.getenv("PROMPT_ID", "prompt‑generate‑summary")

    # Database
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", 3306))
    DB_NAME: str = os.getenv("DB_NAME", "my_database")
    DB_DRIVER: str = os.getenv("DB_DRIVER", "mysql+asyncmy")
    DB_ENCRYPT: str = os.getenv("DB_ENCRYPT", "false")
    DB_TRUST_SERVER_CERTIFICATE: str = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "true")
    DB_SERVER_TYPE: str = os.getenv("DB_SERVER_TYPE", "mysql")
    DB_DRIVER_TYPE: str = os.getenv("DB_DRIVER_TYPE", "asyncmy")


settings = Settings()
