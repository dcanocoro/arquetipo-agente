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
 