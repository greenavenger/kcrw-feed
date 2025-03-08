"""Module to collect the shows"""

from datetime import datetime
import logging
import pprint
from typing import Any, Dict, List, Optional
import urllib.robotparser as urobot
import uuid

from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.models import Show, Episode, ShowDirectory
from kcrw_feed.source_manager import BaseSource
from kcrw_feed.processing.resources import SitemapProcessor
# from kcrw_feed.feed_processor import FeedProcessor
from kcrw_feed.show_processor import ShowProcessor
from kcrw_feed.persistence.manager import JsonPersister, RssPersister
from kcrw_feed import utils


logger = logging.getLogger("kcrw_feed")


class ShowIndex:
    def __init__(self, source: BaseSource) -> None:
        """Parameters:
            source (str): The base URL (or local base path) for the site.
            extra_sitemaps (List[str], optional): Additional sitemap paths to include.
        """
        self.source = source
        # Instantiate the helper components.
        self.sitemap_processor = SitemapProcessor(self.source)
        self.show_processor = ShowProcessor(self.source)
        # This will hold fully enriched Show objects.
        # TODO: Should I split out Shows and Episodes?
        self._entities: Dict[str | uuid.UUID, Show | Episode] = {}

    def gather(self) -> Dict[str, Any]:
        """Gather a list of raw entries from the source."""
        logger.info("Gathering entries")
        entries: Dict[str, Any] = {}
        if self.source.uses_sitemap:
            entries = self.sitemap_processor.gather_entries()
        else:
            # Placeholder for future feed processing.
            raise NotImplementedError
        return entries

    def update(self, selection: List[str] = [], update_after: Optional[datetime] = None,
               ) -> int:
        """Update the repository with enriched Show objects.

        Parameters:
            update_after (datetime, optional): Only update shows that have
              changed after this timestamp.
            selected_urls (List[str], optional): If provided, only update
              shows whose URL is in this list."""
        entries: Dict[str, Any] = self.gather()

        logger.info("Updating entities")

        # Filter resources
        filtered_entries = self._filter_selected_by_name(
            entries, selection)

        updated_resources: List[str] = []

        # Helper to fetch and store a resource.
        def fetch_and_store(resource: str, metadata: Any) -> None:
            relative = self.source.relative_path(resource)
            entity = self.show_processor.fetch(
                relative, source_metadata=metadata)
            if not entity:
                # Skip resource if fetch failed.
                return
            # Make sure the show has a unique identifier.
            assert entity.uuid is not None, "Fetched entity must have a UUID"
            self._entities[entity.uuid] = entity
            # if show.uuid:
            #     key = show.uuid
            # else:
            #     # If no UUID is provided, you might use the URL as a fallback key.
            #     key = show.url
            # self.shows[key] = show
            updated_resources.append(resource)

        for resource, metadata in filtered_entries.items():
            logger.debug("Processing resource: %s", resource)
            fetch_and_store(resource, metadata)

        # Associate episodes with shows
        self._associate()

        logger.info("Updated %d resources", len(updated_resources))
        return len(updated_resources)

    def _associate(self) -> None:
        """Scan all entities and ensure each Episode is associated
        with a Show."""
        for episode in self.show_processor.get_episodes():
            show = self.show_processor.get_show_by_uuid(episode.show_uuid)
            show.add_episode(episode)

    def _filter_selected_by_name(self, entities: Dict[str, Any], selection: List[str] = []) -> Dict[str, Any]:
        """Filter resources based on selected_urls if necessary."""
        logging.debug("Filtering selection")
        # If selection filter is empty, return all entities
        if not selection:
            return entities
        # Otherwise, return only matching entities
        selected: Dict[str, Any] = {}
        logger.debug("selection match: %s",
                     pprint.pformat(selection))
        for resource in selection:
            selected[resource] = entities[resource]
        logger.debug("selected: %s", list(selected.keys()))
        logger.info("Selecting %d entities", len(selected))
        # TODO: Improve user experience when a bad selection is given
        assert len(selection) == len(
            selected), "Selection did not match resources!"
        return selected

    def load(self, storage_root: str) -> None:
        """Load data from stable storage."""
        logger.info("Loading entities")

        persister = JsonPersister(storage_root)
        directory = persister.load()
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Loaded data: %s", pprint.pformat(directory))

        for show in directory.get_shows():
            self._entities[show.uuid] = show
            for episode in show.get_episodes():
                self._entities[episode.uuid] = episode

    def save(self, storage_root: str) -> None:
        """Persist data to stable storage."""
        _: int = self.update()

        logger.info("Saving entities")

        persister = JsonPersister(storage_root=storage_root)
        directory = ShowDirectory(self.show_processor.get_shows())
        persister.save(directory)
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Saved data: %s", pprint.pformat(directory))

        self.generate_feeds(storage_root)

    def generate_feeds(self, storage_root: str) -> None:
        """Generate feed files"""
        logger.info("Writing feeds")
        persister = RssPersister(storage_root=storage_root)
        directory = ShowDirectory(self.show_processor.get_shows())
        persister.save(directory)

    # Accessor Methods

    def get_shows(self) -> List[Show]:
        """Return a list of all Show objects."""
        shows = (show for show in self._entities.values()
                 if self.source.is_show(show.url))
        # logger.debug("%s", pprint.pformat(shows))
        return list(shows)

    def get_show_by_uuid(self, uuid: str) -> Optional[Show]:
        """Return the Show with the given uuid."""
        return self._entities.get(uuid)

    def get_show_by_name(self, name: str) -> Optional[Show]:
        """Return the first Show that matches the given name (case-insensitive)."""
        for show in self._entities.values():
            if show.title.lower() == name.lower():
                return show
        return None

    def get_episodes(self) -> List[Episode]:
        """Return a combined list of episodes from all shows."""
        episodes: List[Episode] = []
        for entity in self._entities.values():
            if self.source.is_episode(entity.url):
                episodes.append(entity)
            else:
                # Show objects have a list of Episodes
                episodes.extend(entity.episodes)
        episodes = utils.uniq_by_uuid(episodes)
        return episodes

    def get_episode_by_uuid(self, uuid: str) -> Optional[Episode]:
        """Return the first Episode found with the given uuid."""
        for show in self._entities.values():
            for ep in show.episodes:
                if ep.uuid == uuid:
                    return ep
        return None

    def dump_all(self):
        """Dump the values of self.shows for debugging purposes."""
        return self._entities
