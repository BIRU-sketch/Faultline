import pytest
from app import create_app
from app.db.session import init_db, SessionScoped, Base, _engine


@pytest.fixture(scope="function")
def app():
    """Create an isolated test application with in-memory database."""
    test_config = {
        "TESTING": True,
        "DEBUG": False,
        "DATABASE_URL": "sqlite:///:memory:",
        "MAX_TESTS_LIMIT": 10,
        "MAX_DURATION_SECONDS_LIMIT": 60,
        "MAX_RETRIES_LIMIT": 2,
        "LLM_JUDGE_PROVIDER": "none",
        "OPENAI_API_KEY": "",
    }
    app = create_app(config_name="testing", config_override=test_config)

    with app.app_context():
        yield app
        SessionScoped.remove()


@pytest.fixture(scope="function")
def client(app):
    """Test client for HTTP requests."""
    return app.test_client()


@pytest.fixture(scope="function")
def session(app):
    """Scoped SQLAlchemy session for direct DB tests."""
    with app.app_context():
        yield SessionScoped()
