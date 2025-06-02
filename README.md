# 📦 "FastAPI Microservice" - Configuración y Ejecución

Este proyecto ha sido desarrollado en Python y requiere la configuración de un entorno virtual para garantizar el aislamiento de dependencias y una correcta ejecución. A continuación, se describen los pasos necesarios para su preparación y puesta en marcha.

## ⚙️ Configuración y Ejecución

Sigue los  pasos desde la raíz del proyecto para configurar y ejecutar la aplicación:

### En Windows (cmd o PowerShell):

**Creamos el entorno virtual**
```bash
python -m venv .venv
```
**lo activamos**
```bash
.venv\Scripts\activate 
```
**agregamos la ultima version de pip**
```bash
python -m pip install --upgrade pip 
```
**instalamos los requisitos**
```bash
pip install -r requirements.txt 
```

**y para ejecutar el microservicio utilizamos el siguiente comando desde la carpeta src**

```bash
uvicorn main:app --port=8002
```
🐧 En macOS/Linux
**creamos el entorno virtual**
```bash
python3 -m venv .venv
```
**lo activamos**
```bash
source .venv/bin/activate 
```
**agregamos la ultima version de pip**
```bash
python -m pip install --upgrade pip 
```
**instalamos los requisitos**
```bash
pip install -r requirements.txt 
```
**y para ejecutar el orquestador utilizamos el siguiente comando**
```bash
uvicorn main:app --port=8001
```

Si necesitas asistencia adicional o soporte técnico, por favor contacta con el equipo de desarrollo correspondiente.
