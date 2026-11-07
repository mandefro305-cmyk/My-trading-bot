from backend.app.database.session import engine, Base
import backend.app.database.models  # load all 20 models

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database tables initialized successfully.")
