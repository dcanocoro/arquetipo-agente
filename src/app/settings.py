"""
Módulo de configuración de la aplicación.

Este módulo utiliza Pydantic Settings para definir y cargar la configuración de la aplicación
a partir de un archivo YAML. La clase Settings hereda de BaseSettings y define múltiples variables
de entorno que configuran diversos aspectos de la aplicación, como URLs y puertos de servicios.
El método classmethod load_from_yaml() calcula dinámicamente la ruta al archivo de configuración,
asegurando que al estar settings.py en src/app y config.yaml en src se pueda localizar el archivo correctamente.
Además, se incluyen métodos para determinar si el entorno es local y para obtener claves JWKS configuradas.
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any
import yaml


load_dotenv()

class Settings(BaseSettings):
    """Configuración de la aplicación."""
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "qgdiag-esqueleto-orquestador-python")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    AICORE_URL: str = os.getenv("BASE_URL", "https://aicorepru.unicajasc.corp/Monolith/api")
    ENGINE_ID: str = os.getenv("ENGINE_ID", "4ccb0725-fad1-453e-a673-c350c8fd5bc9")

    URL_LOCALHOST: str = os.getenv("URL_LOCALHOST", "http://127.0.0.1")

    URL_HIST_CONV: str = os.getenv("URL_HIST_CONV", URL_LOCALHOST)
    HIST_CONV_PORT: str = os.getenv("HIST_CONV_PORT", "8006")

    DRIVER_URL: str = os.getenv("DRIVER_URL", URL_LOCALHOST)
    DRIVER_PORT: str = os.getenv("DRIVER_PORT", "8005")

    URL_CONTROL_GASTOS: str = os.getenv("URL_CONTROL_GASTOS", URL_LOCALHOST)
    CONTROL_GASTOS_PORT: str = os.getenv("CONTROL_GASTOS_PORT", "8004")

    GESTOR_PROMPT_URL: str = os.getenv("URL_GESTOR_PROMPTS", URL_LOCALHOST)
    GESTOR_PROMPT_PORT: str = os.getenv("GESTOR_PROMPTS_PORT", "")

    GUARDRAILS_URL: str = os.getenv("GUARDRAILS_URL", URL_LOCALHOST)
    GUARDRAILS_PORT: str = os.getenv("GUARDRAILS_PORT", "8007")


    JWKS_LOCAL: Optional[Dict[str, Any]] = None

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

