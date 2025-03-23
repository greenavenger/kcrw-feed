"""Central "card catalog" for shows, episodes and hosts"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import List, Dict, Tuple, Any, Optional, Iterable, Callable
import uuid

from kcrw_feed.models import Show, Episode, Host, Resource, FilterOptions
from kcrw_feed.source_manager import BaseSource
from kcrw_feed.processing.resources import SitemapProcessor
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.persistence.manager import JsonPersister


logger = logging.getLogger("kcrw_feed")


@dataclass
class Catalog:
    """Catalog of shows, episodes, hosts"""
    shows: Dict[uuid.UUID | str, Any] = field(default_factory=dict)
    episodes: Dict[uuid.UUID | str, Any] = field(default_factory=dict)
    hosts: Dict[uuid.UUID | str, Any] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)


class BaseStationCatalog(ABC):
    """Abstract base class for catalogs. A StationCatalog represents a
    collection of shows, episodes, hosts and resources. It provides methods
    for listing and comparing (diffing) the current state with an updated
    state.
    """
    catalog_source: str | BaseSource
    catalog: Catalog

    @abstractmethod
    def load(self) -> Catalog:
        """Load the catalog."""
        pass

    def list_resources(self, filter_opts: Optional[FilterOptions] = None) -> List[Resource]:
        """Return a list of resources, filtered if necessary."""
        return _filter_items(
            self.catalog.resources.values(),
            filter_opts,
            key=lambda r: r.url,
            date_key=lambda r: r.metadata.get("lastmod", None)
        )

    def diff(self, updated_catalog: BaseStationCatalog, filter_opts: Optional[FilterOptions] = None) -> Dict[str, List[Any]]:
        """
        Compare the current state (self.catalog) with an updated catalog,
        returning a dictionary of differences.

        Returns:
            dict: with keys 'added', 'removed', and 'modified'.
        """
        current = {resource.url for resource in self.list_resources(
            filter_opts=filter_opts)}
        updated = {resource.url for resource in updated_catalog.list_resources(
            filter_opts=filter_opts)}
        added = updated - current
        removed = current - updated
        modified = set()

        return {"added": list(added), "removed": list(removed), "modified": list(modified)}


class LocalStationCatalog(BaseStationCatalog):
    """
    StationCatalog represents the complete collection of shows, episodes,
    and hosts from the local persisted state.
    """

    def __init__(self, catalog_source: str) -> None:
        self.catalog_source = catalog_source
        self.catalog = self.load()

    def load(self) -> Catalog:
        """Load data from stable storage."""
        logger.info("Loading entities")

        persister = JsonPersister(self.catalog_source)
        directory = persister.load()
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Loaded data: %s", pprint.pformat(directory))

        catalog = Catalog()
        for show in directory.shows:
            if show.uuid:
                catalog.shows[show.uuid] = show
            for episode in show.episodes:
                if episode.uuid:
                    catalog.episodes[episode.uuid] = episode
                for host in episode.hosts:
                    # TODO: fix that hosts are a list of uuids here!
                    if not isinstance(host, uuid.UUID) and host.uuid:
                        catalog.hosts[host.uuid] = host
                if episode.resource:
                    key = episode.resource.url
                    catalog.resources[key] = episode.resource
            # TODO: remove duplicative host population?
            for host in show.hosts:
                if host.uuid:
                    catalog.hosts[host.uuid] = host
            if show.resource:
                key = show.resource.url
                catalog.resources[key] = show.resource
        logger.info("Loaded: %d resources", len(catalog.resources))
        logger.info("Loaded: %d shows, %d episodes, %d, hosts",
                    len(catalog.shows), len(
                        catalog.episodes), len(catalog.hosts))
        return catalog

    def list_shows(self, filter_opts: Optional[FilterOptions] = None) -> List[Show]:
        """Return a list of shows, filtered if necessary."""
        return _filter_items(
            self.catalog.shows.values(),
            filter_opts,
            key=lambda s: s.url,
            date_key=lambda s: s.last_updated
        )

    def list_episodes(self, filter_opts: Optional[FilterOptions] = None) -> List[Episode]:
        """Return a list of episodes, filtered if necessary."""
        return _filter_items(
            self.catalog.episodes.values(),
            filter_opts,
            key=lambda e: e.url,
            date_key=lambda e: e.last_updated  # or use e.airdate if that’s more appropriate
        )

    def list_hosts(self, filter_opts: Optional[FilterOptions] = None) -> List[Host]:
        """Return a list of hosts, filtered if necessary."""
        return _filter_items(self.catalog.hosts.values(), filter_opts, key=lambda h: h.name)


class LiveStationCatalog(BaseStationCatalog):
    def __init__(self, catalog_source: BaseSource) -> None:
        self.catalog_source = catalog_source
        self.sitemap_processor = SitemapProcessor(self.catalog_source)
        self.catalog = self.load()

    def load(self) -> Catalog:
        """Load data from live site."""
        logger.info("Loading entities")

        catalog = Catalog(
            resources=self.sitemap_processor.fetch_resources()
        )
        return catalog


def _filter_items(
    items: Iterable[Any],
    filter_opts: Optional[FilterOptions] = None,
    key: Optional[Callable[[Any], str]] = None,
    date_key: Optional[Callable[[Any], Optional[datetime]]] = None
) -> List[Any]:
    """
    Filter an iterable of items based on two conditions:
      1. A compiled regex (from filter_opts.compiled_match), applied to the string
         extracted via key.
      2. A date range, using filter_opts.start_date and filter_opts.end_date, compared
         against the date returned by date_key.

    Parameters:
      items: An iterable of items.
      filter_opts: A FilterOptions instance containing filtering criteria.
      key: A callable to extract a string from an item (for regex filtering).
      date_key: A callable to extract a datetime from an item (for date range filtering).

    Returns:
      A list of items that match both criteria.
    """
    items = list(items)
    if filter_opts:
        # Apply regex filtering if a compiled regex exists.
        if filter_opts.compiled_match:
            pattern = filter_opts.compiled_match
            if key:
                items = [item for item in items if pattern.search(key(item))]
            else:
                items = [item for item in items if pattern.search(str(item))]
        # Apply date filtering if a date_key is provided.
        if date_key:
            if filter_opts.start_date:
                items = [item for item in items
                         if (date_key(item) is not None and date_key(item) >= filter_opts.start_date)]
            if filter_opts.end_date:
                items = [item for item in items
                         if (date_key(item) is not None and date_key(item) <= filter_opts.end_date)]
    return items
