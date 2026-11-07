import os
import uvicorn
from backend.app.config.settings import settings

if __name__ == "__main__":
    port_env = os.environ.get("PORT")
    port = int(port_env) if port_env and port_env.isdigit() else settings.PORT
    host = os.environ.get("HOST", settings.HOST)
    print(f"Starting GoldHunter AI on {host}:{port}")
    uvicorn.run("backend.app.main:app", host=host, port=port, log_level="info")
