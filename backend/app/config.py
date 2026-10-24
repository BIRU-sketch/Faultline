import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from backend root or parent if present
backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(backend_dir / ".env")


class Config:
    """Base application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "faultline-dev-secret-key-change-me")
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{backend_dir / 'faultline.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CORS settings
    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

    # Resource execution limits enforced by backend
    MAX_TESTS_LIMIT = int(os.getenv("MAX_TESTS_LIMIT", "20"))
    MAX_DURATION_SECONDS_LIMIT = int(os.getenv("MAX_DURATION_SECONDS_LIMIT", "180"))
    MAX_RETRIES_LIMIT = int(os.getenv("MAX_RETRIES_LIMIT", "3"))

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_ORCHESTRATOR_MODEL = os.getenv("OPENAI_ORCHESTRATOR_MODEL", "gpt-4o-mini")
    OPENAI_MAX_ORCHESTRATOR_STEPS = int(os.getenv("OPENAI_MAX_ORCHESTRATOR_STEPS", "4"))
    OPENAI_MAX_TESTS = int(os.getenv("OPENAI_MAX_TESTS", "10"))
    OPENAI_MAX_REQUESTS = int(os.getenv("OPENAI_MAX_REQUESTS", "8"))
    OPENAI_REQUEST_TIMEOUT_SECONDS = float(os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "30"))

    # Optional LLM Judge provider configuration
    LLM_JUDGE_PROVIDER = os.getenv("LLM_JUDGE_PROVIDER", "none").lower()
    LLM_JUDGE_MODEL = os.getenv("LLM_JUDGE_MODEL", "gpt-4o-mini")
    LLM_JUDGE_API_KEY = os.getenv("LLM_JUDGE_API_KEY", "")

    # Server settings
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    DATABASE_URL = "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
