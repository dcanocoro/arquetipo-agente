"""Proporciona una dependencia para la base de datos"""


from qgdiag_lib_arquitectura import SQLDatabase
from app.settings import settings

def get_db_app():
    return SQLDatabase().create_connection(
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

