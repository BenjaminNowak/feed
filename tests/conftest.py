"""Pytest configuration."""
import os
from typing import Generator

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test that requires external services",
    )
    config.addinivalue_line(
        "markers",
        "unit: mark test as a unit test that can run in isolation",
    )


@pytest.fixture(scope="function", autouse=True)
def clean_env() -> Generator[None, None, None]:
    """Clean environment variables before and after each test."""
    # Store original environment
    original_env = dict(os.environ)

    # Clean MongoDB-related env vars
    for var in [
        "MONGODB_HOST",
        "MONGODB_PORT",
        "MONGODB_USERNAME",
        "MONGODB_PASSWORD",
        "MONGODB_DATABASE",
    ]:
        os.environ.pop(var, None)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


def pytest_collection_modifyitems(config, items):
    """Handle test markers and skip logic."""
    # Skip integration tests unless explicitly requested
    run_integration = config.getoption("--integration", default=False)

    for item in items:
        # Mark all tests in test_*_integration.py as integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Skip integration tests unless explicitly requested
        if "integration" in item.keywords and not run_integration:
            item.add_marker(pytest.mark.skip(reason="need --integration option to run"))


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests",
    )
