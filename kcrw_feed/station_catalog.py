"""Central "card catalog" for shows, episodes and hosts"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
import logging
import pprint
import os
from typing import List, Dict, Any, Optional, Iterable, Callable
import uuid

from deepdiff import DeepDiff


from kcrw_feed.models import Show, Episode, Host, Resource, FilterOptions, ShowDirectory, Catalog, CatalogDiff, ModifiedEntry
from kcrw_feed.source_manager import BaseSource
from kcrw_feed.processing.resources import ResourceProcessor
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.persistence.feeds import FeedPersister
from kcrw_feed.persistence.state import StatePersister


logger = logging.getLogger("kcrw_feed")

STATE_CATALOG_FILE = "kcrw_catalog.json"


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

    def get_source(self):
        """Return the source of this catalog."""
        return self.catalog_source

    def list_resources(self, filter_opts: Optional[FilterOptions] = None) -> List[Resource]:
        """Return a list of resources, filtered if necessary."""
        return _filter_items(
            self.catalog.resources.values(),
            filter_opts,
            key=lambda r: r.url,
            date_key=lambda r: r.metadata.get("lastmod", None)
        )

    def list_shows(self, filter_opts: Optional[FilterOptions] = None) -> List[Show]:
        """Return a list of shows, filtered if necessary."""
        shows = _filter_items(
            self.catalog.shows.values(),
            filter_opts,
            key=lambda s: s.url,
            date_key=lambda s: s.last_updated
        )
        return sorted(shows)

    def list_episodes(self, filter_opts: Optional[FilterOptions] = None) -> List[Episode]:
        """Return a list of episodes, filtered if necessary."""
        return _filter_items(
            self.catalog.episodes.values(),
            filter_opts,
            key=lambda e: e.url,
            date_key=lambda e: e.last_updated  # or use e.airdate if that's more appropriate
        )

    def list_hosts(self, filter_opts: Optional[FilterOptions] = None) -> List[Host]:
        """Return a list of hosts, filtered if necessary."""
        return _filter_items(self.catalog.hosts.values(), filter_opts, key=lambda h: h.name)

    def has_show(self, show_id: uuid.UUID | str) -> bool:
        return show_id in self.catalog.shows

    def has_episode(self, episode_id: uuid.UUID | str) -> bool:
        return episode_id in self.catalog.episodes

    def get_resource(self, url: str) -> Optional[Resource]:
        return self.catalog.resources.get(url, None)

    def get_show(self, show_id: uuid.UUID | str) -> Optional[Show]:
        return self.catalog.shows.get(show_id, None)

    def add_resource(self, resource: Resource) -> None:
        """Add a resource to the catalog."""
        if not resource.url:
            raise ValueError("Resource must have a url")
        self.catalog.resources[resource.url] = resource

    def add_show(self, show: Show) -> None:
        """Add a show to the catalog."""
        if show.uuid is None:
            raise ValueError("Show must have a uuid")
        self.catalog.shows[show.uuid] = show

    def add_episode(self, episode: Episode) -> None:
        """Add an episode to the catalog."""
        if episode.uuid is None:
            raise ValueError("Episode must have a uuid")
        self.catalog.episodes[episode.uuid] = episode

    def add_host(self, host: Host) -> None:
        """Add a host to the catalog."""
        if host.uuid is None:
            raise ValueError("Host must have a uuid")
        self.catalog.hosts[host.uuid] = host

    def diff(self, other: BaseStationCatalog, filter_opts: Optional[FilterOptions] = None) -> CatalogDiff:
        """
        Compare the current state (self.catalog) with an updated catalog,
        returning a dictionary of differences.

        Returns:
            CatalogDiff object
        """
        # TODO: Generalize this so it works for all of our dataclasses.
        self_set = set(self.list_resources(filter_opts=filter_opts))
        other_set = set(other.list_resources(filter_opts=filter_opts))
        added = other_set - self_set
        removed = self_set - other_set
        intersection = self_set & other_set

        modified: List[ModifiedEntry] = []
        if intersection:
            for resource in intersection:
                url = resource.url
                current_resource = self.catalog.resources.get(url)
                other_resource = other.catalog.resources.get(url)
                # other_resource.last_updated = datetime.now()
                # other_resource.source = "foo"
                ddiff = DeepDiff(asdict(current_resource),
                                 asdict(other_resource), ignore_order=True)
                if ddiff:
                    modified.append(ModifiedEntry(
                        current_resource, other_resource, ddiff))

        return CatalogDiff(
            added=list(added),
            removed=list(removed),
            modified=modified
        )


class LocalStationCatalog(BaseStationCatalog):
    """LocalStationCatalog represents the complete collection of shows,
    episodes, and hosts from the local persisted state."""

    def __init__(self, catalog_source: str, state_file: str, feed_persister: Optional[FeedPersister]) -> None:
        self.catalog_source = catalog_source
        self.state_file = state_file
        self.state_persister = None
        self.feed_persister = feed_persister
        self.catalog = self.load()

    def load(self) -> Catalog:
        """Load data from stable storage."""
        logger.info("Loading local state")

        # Ensure catalog_source is a string for the StatePersister
        storage_root = str(self.catalog_source)
        self.state_persister = StatePersister(
            storage_root, self.state_file)

        state = self.state_persister.load()
        if isinstance(state, Catalog):
            logger.info("Loaded state as Catalog")
            return state

        # Fall back to extracting from ShowDirectory
        directory = state
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Loaded data: %s", pprint.pformat(directory))

        catalog = Catalog()
        for show in directory.shows:
            if show.uuid:
                logger.trace("Adding show to catalog: %s", show.uuid)
                catalog.shows[show.uuid] = show
            for episode in show.episodes:
                if episode.uuid:
                    logger.trace("Adding episode to catalog: %s", episode.uuid)
                    catalog.episodes[episode.uuid] = episode
                for host in episode.hosts:
                    # TODO: fix that hosts are a list of uuids here!
                    if not isinstance(host, uuid.UUID) and host.uuid:
                        logger.trace("Adding host to catalog: %s", host.uuid)
                        catalog.hosts[host.uuid] = host
                if episode.resource:
                    key = episode.resource.url
                    logger.trace("Adding resource to catalog: %s", key)
                    catalog.resources[key] = episode.resource
            # TODO: remove duplicative host population?
            for host in show.hosts:
                if host.uuid:
                    catalog.hosts[host.uuid] = host
            if show.resource:
                key = show.resource.url
                catalog.resources[key] = show.resource
        logger.info("Loaded: %d resources", len(catalog.resources))
        logger.info("Loaded: %d shows, %d episodes (+%d hosts)",
                    len(catalog.shows), len(
                        catalog.episodes), len(catalog.hosts))
        return catalog

    def save_state(self) -> None:
        """Write data to stable storage."""
        self.state_persister.save(ShowDirectory(self.list_shows()))
        self.state_persister.save(self.catalog, filename=os.path.join(
            self.catalog_source, STATE_CATALOG_FILE))

    def generate_feeds(self) -> None:
        """Write feeds to directory."""
        self.feed_persister.save(ShowDirectory(self.list_shows()))


class LiveStationCatalog(BaseStationCatalog):
    """LiveStationCatalog represents collection of shows, episodes, and hosts
    from the live state (kcrw.com)."""

    def __init__(self, catalog_source: BaseSource) -> None:
        self.catalog_source = catalog_source
        self.resource_processor = ResourceProcessor(self.catalog_source)
        self.catalog = self.load()

    def load(self) -> Catalog:
        """Load data from live site."""
        logger.info("Fetching live resources")

        # TODO: Should we be working with the full set of dataclasses or just
        # resources?
        catalog = Catalog(
            resources=self.resource_processor.fetch_resources()
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
