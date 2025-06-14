"""Pytest configuration."""


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
