
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
# The engine is the actual connection pool to PostgreSQL.
engine = create_engine(settings.DATABASE_URL)
# A Session is one "conversation" with the DB for a single request.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Every model class will inherit from Base.
Base = declarative_base()
# Dependency: give a fresh session to a request, then always close it.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

