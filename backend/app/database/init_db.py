from backend.app.database.session import engine, Base
import backend.app.database.models  # load all 20 models
import logging

logger = logging.getLogger(__name__)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.warning(f"Could not initialize database tables: {e}")

if __name__ == "__main__":
    init_db()
