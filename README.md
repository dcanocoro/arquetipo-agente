# 📦 Esqueleto arquetipo microservicio python - Configuración y Ejecución

Este proyecto ha sido desarrollado en Python y requiere la configuración de un entorno virtual para garantizar el aislamiento de dependencias y una correcta ejecución.

## 📁 Estructura del Proyecto

Se asume que todas las operaciones descritas a continuación se ejecutan desde el directorio `app`, que contiene el archivo principal `main.py` y el fichero de dependencias `requirements.txt`.

## ⚙️ Configuración y Ejecución

Para configurar el entorno virtual, instalar las dependencias necesarias y ejecutar la aplicación, ejecute la siguiente secuencia de comandos desde la carpeta `app`:

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

**y para ejecutar el orquestador utilizamos el siguiente comando**

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
