"""Module to collect the shows"""

from datetime import datetime
import logging
import pprint
from typing import Any, Dict, List, Optional
import urllib.robotparser as urobot
import uuid

from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.models import Show, Episode, Resource, ShowDirectory
from kcrw_feed.source_manager import BaseSource
from kcrw_feed.processing.resources import ResourceProcessor
# from kcrw_feed.feed_processor import FeedProcessor
from kcrw_feed.processing.station import StationProcessor
from kcrw_feed.persistence.state import StatePersister
from kcrw_feed.persistence.feeds import FeedPersister
from kcrw_feed import utils


logger = logging.getLogger("kcrw_feed")


class ShowIndex:
    def __init__(self, source: BaseSource, storage_root: str, state_file: str, feed_directory: str) -> None:
        """Parameters:
            source: The BaseSource object for the site (http or file).
            storage_root: The directory root for local storage (state, feeds).
        """
        self.source = source
        self.storage_root = storage_root
        self.state_file = state_file
        self.feed_directory = feed_directory
        # Instantiate the helper components.
        self.resource_processor = ResourceProcessor(self.source)
        self.station_processor = StationProcessor(self.source)
        # This will hold fully enriched Show objects.
        # TODO: Should I split out Shows and Episodes?
        self._entities: Dict[str | uuid.UUID, Show | Episode] = {}

    def gather(self) -> Dict[str, Any]:
        """Gather a list of raw entries from the source."""
        logger.info("Gathering entries")
        resources = self.resource_processor.fetch_resources()
        return resources

    def update(self, selection: List[str] = [],
               update_after: Optional[datetime] = None) -> int:
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
        def fetch_and_store(url: str, resource: Resource) -> None:
            relative = self.source.relative_path(url)
            entity = self.station_processor.fetch(
                relative, resource=resource)
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
            updated_resources.append(url)

        for url, resource in filtered_entries.items():
            logger.debug("Processing resource: %s", url)
            fetch_and_store(url, resource)

        # Associate episodes with shows
        self._associate()

        logger.info("Updated %d resources", len(updated_resources))

        self.save()

        return len(updated_resources)

    def _associate(self) -> None:
        """Scan all entities and ensure each Episode is associated
        with a Show."""
        for episode in self.station_processor.get_episodes():
            show = self.station_processor.get_show_by_uuid(episode.show_uuid)
            if episode.uuid not in [e.uuid for e in show.episodes]:
                show.episodes.append(episode)

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

    # def load(self) -> None:
    #     """Load data from stable storage."""
    #     logger.info("Loading entities")

    #     persister = JsonPersister(self.storage_root)
    #     directory = persister.load()
    #     if logger.isEnabledFor(TRACE_LEVEL_NUM):
    #         logger.trace("Loaded data: %s", pprint.pformat(directory))

    #     for show in directory.get_shows():
    #         self._entities[show.uuid] = show
    #         for episode in show.get_episodes():
    #             self._entities[episode.uuid] = episode

    def save(self) -> None:
        """Persist data to stable storage."""
        logger.info("Saving entities")
        persister = StatePersister(
            storage_root=self.storage_root, state_file=self.state_file)
        directory = ShowDirectory(self.station_processor.get_shows())
        persister.save(directory)
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Saved data: %s", pprint.pformat(directory))

        self.generate_feeds()

    def generate_feeds(self) -> None:
        """Generate feed files"""
        logger.info("Writing feeds")
        persister = FeedPersister(
            storage_root=self.storage_root, feed_directory=self.feed_directory)
        directory = ShowDirectory(self.station_processor.get_shows())
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
