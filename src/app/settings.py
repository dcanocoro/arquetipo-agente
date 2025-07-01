"""Configuración para el arquetipo"""

from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any
import yaml
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "qgdiag-microservicio-python-test"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    ARCHITECTURE_HANDLERS_SECURITY_ENABLED: bool = False
    JWKS_LOCAL: Optional[Dict[str, Any]] = None

    # Orchestrator
    ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1")
    ORCHESTRATOR_PORT: str = os.getenv("ORCHESTRATOR_PORT", "8000")

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

    @classmethod
    def load_from_yaml(cls, path: str = "config.yaml"):
        """
        Carga la configuración desde un archivo YAML.

        En este caso, dado que settings.py está en src/app y config.yaml en src,
        se calcula la ruta subiendo un nivel desde el directorio actual.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "..", path)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found at {config_path}")
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def is_local(self) -> bool:
        return self.ENVIRONMENT.lower() == "local"

    def get_jwks(self) -> Optional[Dict[str, Any]]:
        if self.is_local():
            if not self.JWKS_LOCAL:
                raise RuntimeError("JWKS_LOCAL debe estar definido en entorno local")
            return self.JWKS_LOCAL
        return None

settings = Settings.load_from_yaml()
