"""Central "card catalog" for shows, episodes and hosts"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import List, Dict, Tuple, Any, Optional
import uuid

from kcrw_feed.models import Show, Episode, ShowDirectory
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


class StationCatalog:
    """
    StationCatalog represents the complete collection of shows, episodes,
    and hosts from the local persisted state. It provides methods for
    listing and comparing (diffing) the current state with an updated state.
    """

    def __init__(self, storage_root: str) -> None:
        self.storage_root = storage_root
        self.catalog = self._load()

    def _load(self) -> Catalog:
        """Load data from stable storage."""
        logger.info("Loading entities")

        persister = JsonPersister(self.storage_root)
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
        logger.info("Loaded: %d shows, %d episodes, %d, hosts",
                    len(catalog.shows), len(
                        catalog.episodes), len(catalog.hosts))
        if len(catalog.resources):
            logger.info("Loaded: %d resources", len(catalog.resources))
        return catalog

    def list_resources(self, match: Optional[str] = None) -> List[Resource]:
        return self.catalog.resources.values()

    def list_shows(self, match: Optional[str] = None) -> List[Show]:
        """Return all shows, optionally filtering by a substring or regex match."""
        shows = self.catalog.shows.values()
        if match:
            # For simplicity, we'll do a case-insensitive substring match.
            shows = [s for s in shows if s and match.lower()
                     in s.title.lower()]
        return shows

    def list_episodes(self, match: Optional[str] = None) -> List[Episode]:
        """Return a combined list of all episodes, optionally filtered."""
        return self.catalog.episodes.values()

    def list_hosts(self, match: Optional[str] = None) -> List[Host]:
        """Return a combined list of all episodes, optionally filtered."""
        return self.catalog.hosts.values()

    def diff(self, updated: ShowDirectory) -> Dict[str, List[Any]]:
        """
        Compare the current state (self.directory) with an updated state,
        returning a dictionary of differences.

        Returns:
            dict: with keys 'added', 'removed', and 'modified'.
        """
        current = {show.uuid: show for show in self.directory.shows if show.uuid}
        new = {show.uuid: show for show in updated.shows if show.uuid}

        added = [new[uid] for uid in new if uid not in current]
        removed = [current[uid] for uid in current if uid not in new]
        modified: List[Tuple[Show, Show]] = []
        for uid in current.keys() & new.keys():
            if current[uid] != new[uid]:
                modified.append((current[uid], new[uid]))
        return {"added": added, "removed": removed, "modified": modified}
