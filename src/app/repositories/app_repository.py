"""SQL server repository. Instancia la conexión a la base de datos y
 define funciones para interactuar con ella."""

from sqlalchemy.orm import Session
from app.models.db_model import AppTable


# -----Funciones para interactuar con la bd----------------

def get_app_status(application_id: int, db: Session) -> str | None:
    """
    Devuelve el estado de una aplicación por su ID.
    """
    try:
        app = db.get(AppTable, application_id)
        return app.status if app else None
    except Exception as e:
        print(f"Error al acceder a la base de datos: {e}")
        return None
