"""Base module to handle state persistence"""

from abc import ABC, abstractmethod
from typing import Union

from kcrw_feed.models import ShowDirectory, Catalog


class BasePersister(ABC):
    """Base class for persister implementations."""
    @abstractmethod
    def save(self, state: Union[ShowDirectory, Catalog], filename: str) -> None:
        pass

    @abstractmethod
    def load(self, filename: str) -> Union[ShowDirectory, Catalog]:
        pass
