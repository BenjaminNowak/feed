"""MongoDB configuration classes for dependency injection."""
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class MongoDBConfig:
    """MongoDB connection configuration."""

    host: str
    port: int
    username: Optional[str]
    password: Optional[str]
    database: str
    auth_source: Optional[str]

    def get_uri(self) -> str:
        """Construct MongoDB URI from configuration."""
        if self.username and self.password:
            auth_source = self.auth_source or self.database
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?authSource={auth_source}"
        else:
            return f"mongodb://{self.host}:{self.port}/{self.database}"


class MongoDBConfigProvider(ABC):
    """Abstract base class for MongoDB configuration providers."""

    @abstractmethod
    def get_config(self) -> MongoDBConfig:
        """Get MongoDB configuration."""
        pass


class EnvironmentMongoDBConfigProvider(MongoDBConfigProvider):
    """MongoDB configuration provider that reads from environment variables."""

    def get_config(self) -> MongoDBConfig:
        """Get MongoDB configuration from environment variables."""
        host = os.getenv("MONGODB_HOST", "localhost")
        port = int(os.getenv("MONGODB_PORT", "27017"))
        username = os.getenv("MONGODB_USERNAME", "feeduser")
        password = os.getenv("MONGODB_PASSWORD", "")
        database = os.getenv("MONGODB_DATABASE", "feeddb")
        auth_source = os.getenv("MONGODB_AUTH_SOURCE", database)

        # Handle empty string as None for optional fields
        username = username if username else None
        password = password if password else None
        auth_source = auth_source if auth_source else None

        return MongoDBConfig(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            auth_source=auth_source,
        )


class StaticMongoDBConfigProvider(MongoDBConfigProvider):
    """MongoDB configuration provider for testing with explicit values."""

    def __init__(self, config: MongoDBConfig):
        """Initialize with explicit configuration."""
        self._config = config

    def get_config(self) -> MongoDBConfig:
        """Get the test MongoDB configuration."""
        return self._config
