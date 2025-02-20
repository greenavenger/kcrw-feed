"""Module to collect the shows"""

from datetime import datetime
import logging
import pprint
from typing import Dict, List, Optional, Set
import urllib.robotparser as urobot
import uuid

from kcrw_feed.persistent_logger import TRACE_LEVEL_NUM
from kcrw_feed.models import Show, Episode
from kcrw_feed.source_manager import BaseSource
from kcrw_feed.sitemap_processor import SitemapProcessor
# from kcrw_feed.feed_processor import FeedProcessor
from kcrw_feed.show_processor import ShowProcessor
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
        self.shows: Dict[str | uuid.UUID, Show] = {}

    def gather(self) -> List[str]:
        """Gather a list of raw entities from the source."""
        logger.info("Gathering entities")
        entities: List[str] = []
        if self.source.uses_sitemap:
            entities = self.sitemap_processor.gather_entries()
        else:
            # Placeholder for future feed processing.
            raise NotImplementedError
        return entities

    def update(self, selection: List[str] = [], update_after: Optional[datetime] = None,
               ) -> int:
        """Update the repository with enriched Show objects.

        Parameters:
            update_after (datetime, optional): Only update shows that have changed after this timestamp.
            selected_urls (List[str], optional): If provided, only update shows whose URL is in this list.
        """
        selected_resources: List[str] = []

        raw_resources: List[str] = self.gather()

        logger.info("Updating entities")
        if self.source.uses_sitemap:
            if logger.isEnabledFor(getattr(logging, "TRACE", TRACE_LEVEL_NUM)):
                logger.trace("raw_resources: (before) %s",
                             pprint.pformat(raw_resources))
            # Rewrite based on source semantics
            raw_resources = [self.source.rewrite_base_source(
                e) for e in raw_resources]
            if logger.isEnabledFor(getattr(logging, "TRACE", TRACE_LEVEL_NUM)):
                logger.trace("raw_resources: (after) %s",
                             pprint.pformat(raw_resources))
        else:
            # Placeholder for future feed processing.
            raise NotImplementedError

        # Filter resources
        selected_resources = self._filter_selected_by_name(
            raw_resources, selection)

        updated_resources = []
        for resource in selected_resources:
            show: Show
            # TODO: Optionally, check update_after against metadata.
            # This returns a fully enriched Show object.
            show = self.show_processor.fetch(resource)
            # Make sure the show has a unique identifier.
            assert show.uuid is not None
            self.shows[show.uuid] = show
            # if show.uuid:
            #     key = show.uuid
            # else:
            #     # If no UUID is provided, you might use the URL as a fallback key.
            #     key = show.url
            # self.shows[key] = show
            updated_resources.append(show)
        logger.info("Updated %d resources", len(updated_resources))
        return len(updated_resources)

    def _filter_selected_by_name(self, resources: List[str], selection: List[str] = []) -> List[str]:
        """Filter resources based on selected_urls if necessary."""
        logging.info("Filtering selection")
        selected: Set[str] = set(resources)
        if selection:
            # Normalize for comparison
            selection = [self.source.rewrite_base_source(
                r) for r in selection]
            logger.debug("selection match: %s",
                         pprint.pformat(selection))
            selected = set(resources) & set(selection)
            logger.debug("selected: %s", pprint.pformat(selected))
            logger.info("Selecting %d entities", len(selected))
            # TODO: Improve user experience when a bad selection is given
            assert len(selection) == len(
                selected), "Selection did not match resources!"
        return list(selected)

    # Accessor Methods

    def get_shows(self) -> List[Show]:
        """Return a list of all Show objects."""
        return list(self.shows.values())

    def get_show_by_uuid(self, uuid: str) -> Optional[Show]:
        """Return the Show with the given uuid."""
        return self.shows.get(uuid)

    def get_show_by_name(self, name: str) -> Optional[Show]:
        """Return the first Show that matches the given name (case-insensitive)."""
        for show in self.shows.values():
            if show.title.lower() == name.lower():
                return show
        return None

    def get_episodes(self) -> List[Episode]:
        """Return a combined list of episodes from all shows."""
        episodes: List[Episode] = []
        for show in self.shows.values():
            episodes.extend(show.episodes)
        return episodes

    def get_episode_by_uuid(self, uuid: str) -> Optional[Episode]:
        """Return the first Episode found with the given uuid."""
        for show in self.shows.values():
            for ep in show.episodes:
                if ep.uuid == uuid:
                    return ep
        return None
