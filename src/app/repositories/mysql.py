"""MySQL repository. Instancia la conexión a la base de datos y
 define funciones para interactuar con ella."""

from qgdiag_lib_arquitectura import SQLDatabase
from app.models.user_model import UserTable
from app.config import settings

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

# -----Funciones para interactuar con la bd----------------------------------------------------------


async def get_user_by_id(user_id: int) -> UserTable | None:
    """Devuelve un usuario por su ID."""
    async with sql_database.session() as session:
        return await session.get(UserTable, user_id)
