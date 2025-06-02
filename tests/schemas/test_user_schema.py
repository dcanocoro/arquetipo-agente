"""Test unitario para el UserSchema"""

from app.schemas.db.user import User


def test_user_schema_from_orm():
    """Test para el UserSchema"""
    class DummyUser(object):
        """Clase ficticia para simular un objeto ORM."""
        id = 1
        email = "hello@example.com"
        full_name = "John Doe"

    dto = User.model_validate({"id": DummyUser.id, "email": DummyUser.email, "full_name": DummyUser.full_name})
    assert dto.id == 1
    assert dto.email == "hello@example.com"
    assert dto.full_name == "John Doe"
