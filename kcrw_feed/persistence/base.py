"""Base module to handle state persistence"""

from abc import ABC, abstractmethod

from kcrw_feed.models import ShowDirectory


FEED_DIRECTORY: str = "feeds/"


class BasePersister(ABC):
    """Base class for persister implementations."""
    @abstractmethod
    def save(self, state: ShowDirectory, filename: str) -> None:
        pass

    @abstractmethod
    def load(self, filename: str) -> ShowDirectory:
        pass
