"""Tests para app.repositories.app_repository"""

from unittest.mock import MagicMock
from app.models.db_model import AppTable
from app.repositories.app_repository import get_app_status


def test_get_app_status_not_found():
    """Devuelve None si la aplicación no existe."""
    mock_session = MagicMock()
    mock_session.get.return_value = None

    result = get_app_status(application_id=999, db=mock_session)

    mock_session.get.assert_called_once_with(AppTable, 999)
    assert result is None


# tests/test_repositories_extra.py
"""Additional tests for app.repositories helpers."""
 
import builtins
from types import SimpleNamespace
from unittest.mock import MagicMock
 
import pytest
 
from app.models.db_model import AppTable
from app.repositories import app_repository
from app.repositories import db_dependencies
from app.settings import settings
 
 
# ---------- get_app_status --------------------------------------------------
 
 
def test_get_app_status_found():
    """When the record exists, the status string is returned."""
    dummy_app = SimpleNamespace(status="running")  # cheaper than constructing AppTable
    mock_session = MagicMock()
    mock_session.get.return_value = dummy_app
 
    result = app_repository.get_app_status(42, mock_session)
 
    mock_session.get.assert_called_once_with(AppTable, 42)
    assert result == "running"
 
 
def test_get_app_status_exception(monkeypatch, capsys):
    """Any exception inside the DB call is swallowed and None is returned."""
    mock_session = MagicMock()
    mock_session.get.side_effect = RuntimeError("boom!")
 
    result = app_repository.get_app_status(1, mock_session)
 
    # it prints the error and returns None
    captured = capsys.readouterr()
    assert "Error al acceder a la base de datos" in captured.out
    assert result is None
 
 
# ---------- get_db_app ------------------------------------------------------
 
 
def test_get_db_app_builds_connection(monkeypatch):
    """
    get_db_app must instantiate SQLDatabase and call .create_connection()
    with the values pulled from settings, returning that value.
    """
    # 1️⃣  Wire fake settings quickly (we don't want to rely on .env / real values)
    monkeypatch.setattr(settings, "DB_USER", "u")
    monkeypatch.setattr(settings, "DB_PASSWORD", "p")
    monkeypatch.setattr(settings, "DB_HOST", "h")
    monkeypatch.setattr(settings, "DB_PORT", 1433)
    monkeypatch.setattr(settings, "DB_NAME", "db")
    monkeypatch.setattr(settings, "DB_DRIVER", "ODBC Driver 18")
    monkeypatch.setattr(settings, "DB_ENCRYPT", True)
    monkeypatch.setattr(settings, "DB_TRUST_SERVER_CERTIFICATE", False)
    monkeypatch.setattr(settings, "DB_SERVER_TYPE", "sqlserver")
    monkeypatch.setattr(settings, "DB_DRIVER_TYPE", "pyodbc")
 
    # 2️⃣  Fake SQLDatabase so no real connection is attempted
    mock_sql_db_cls = MagicMock(name="SQLDatabase-cls")
    mock_sql_db_inst = MagicMock(name="SQLDatabase-instance")
    mock_sql_db_cls.return_value = mock_sql_db_inst
    mock_sql_db_inst.create_connection.return_value = "mock-conn"
 
    monkeypatch.setattr(db_dependencies, "SQLDatabase", mock_sql_db_cls)
 
    # 3️⃣  Call the function under test
    conn = db_dependencies.get_db_app()
 
    # 4️⃣  Expectations
    assert conn == "mock-conn"
    mock_sql_db_cls.assert_called_once_with()
    mock_sql_db_inst.create_connection.assert_called_once_with(
        username="u",
        password="p",
        host="h",
        port=1433,
        database_name="db",
        driver="ODBC Driver 18",
        encrypt=True,
        trust_server_certificate=False,
        server_type="sqlserver",
        driver_type="pyodbc",
    )
