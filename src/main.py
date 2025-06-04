"""
main.py
Este módulo define la aplicación FastAPI principal y configura las rutas,
eventos y el endpoint de verificación de salud.
Clases:
    Ninguna
Funciones:
    health() -> dict:
        Endpoint para verificar el estado de salud de la aplicación.
    on_startup() -> None:
        Evento que se ejecuta al iniciar la aplicación.
    on_shutdown() -> None:
        Evento que se ejecuta al apagar la aplicación.
Atributos:
    app (FastAPI): Instancia principal de la aplicación FastAPI configurada
    con el nombre del proyecto y el prefijo de ruta raíz.
"""

from app.settings import settings 
from fastapi import FastAPI
from app.routes.call_orchestrator import router as call_orchestrator_route
from qgdiag_lib_arquitectura import LoggingMiddleware
from qgdiag_lib_arquitectura.security import authentication

app = FastAPI(title=settings.PROJECT_NAME, root_path="/qgdiag-esqueleto-python")
app.add_middleware(LoggingMiddleware)
app.include_router(call_orchestrator_route)


@app.get("/health")
async def health():
    """
    Health check endpoint para comprobar si la aplicación está en funcionamiento.
    """
    return {"message": "Fast API Skeleton is up!"}


@app.on_event("startup")
async def on_startup():    
    jwks = settings.get_jwks()    
    if not jwks:        
        jwks = await authentication.fetch_jwks(channel="1")    
    app.state.jwks_store = authentication.Authenticator(jwks)


@app.on_event("shutdown")
async def on_shutdown():
    """Evento que se ejecuta al apagar la aplicación."""
    print(f"Shutting down {settings.PROJECT_NAME}...")
