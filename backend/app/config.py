# backend/app/config.py
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    # These defaults match docker-compose; .env overrides them.
    DATABASE_URL: str = "postgresql://askflow:askflow@db:5432/askflow"
    # OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    JWT_SECRET: str = ""
    class Config:
        env_file = ".env"
settings = Settings()