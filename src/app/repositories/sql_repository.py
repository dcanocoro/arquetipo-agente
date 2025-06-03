"""SQL server repository. Instancia la conexión a la base de datos y
 define funciones para interactuar con ella."""

from qgdiag_lib_arquitectura import SQLDatabase
from app.models.db_model import AppTable
from app.settings import settings

# --- Inicializa ORM -----------------------------------

sql_database = SQLDatabase()
sql_database.create_connection(
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database_name=settings.DB_NAME,
    driver=settings.DB_DRIVER,
    encrypt=settings.DB_ENCRYPT,
    trust_server_certificate=settings.DB_TRUST_SERVER_CERTIFICATE,
    server_type=settings.DB_SERVER_TYPE,
    driver_type=settings.DB_DRIVER_TYPE
)

# -----Funciones para interactuar con la bd----------------


def get_app_status(application_id: int) -> str | None:
    """
    Devuelve el estado de una aplicación por su ID.
    """
    try:
        with sql_database.session() as session:
            app = session.get(AppTable, application_id)
            return app.status if app else None  # Return the status field
    except Exception as e:
        print(f"Error al acceder a la base de datos: {e}")
        return None
