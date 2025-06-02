"""
Configuración de pruebas para FastAPI.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.routes.users import _auth


@pytest.fixture(scope="session")
def client():
    """
    Cliente compartido para las pruebas.
    """
    # Disable JWT verification for the whole session
    app.dependency_overrides[_auth.authenticate_token] = lambda: None
    with TestClient(app) as c:
        yield c
