"""Module to enrich resource data and populate the core model objects"""

from __future__ import annotations
import logging
import pprint
import re
from typing import List, Optional, Set, Union
from urllib.parse import urlparse
import uuid

from kcrw_feed.models import Show, Episode, Resource
from kcrw_feed.processing.page_parser import PageDataParser
from kcrw_feed.station_catalog import BaseStationCatalog
from kcrw_feed.source_manager import strip_query_params
from kcrw_feed import utils
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM

SHOW_FILENAME = "index.html"  # Used only for CacheSource
EPISODE_FILENAME = "index.html"  # Episode data now embedded in HTML
# Match show URLs: /shows/<show> with optional trailing slash
SHOW_URL_REGEX = re.compile(r"/shows/[^/]+/?$")
# Match episode URLs: /shows/<show>/stories/<episode>
EPISODE_URL_REGEX = re.compile(r"/shows/[^/]+/stories/[^/]+")
# Extract show URL from episode URL
SHOW_FROM_EPISODE = re.compile(r'^(https?://[^/]+/shows/[^/]+)/stories/.*$')


logger = logging.getLogger("kcrw_feed")


class StationProcessor:
    """StationProcessor fetches a show or an episode page and extracts details
    to enrich a raw URL into a full domain model object."""

    def __init__(self, catalog: BaseStationCatalog):
        self.catalog = catalog
        self.source = catalog.get_source()

    def is_episode_resource(self, resource: Resource) -> bool:
        """Determine if the resource URL represents an episode (and not a show).
        A show URL should have two segments after '/music/shows/'."""
        parsed = urlparse(resource.url)
        # Use the regex on the path portion.
        return bool(EPISODE_URL_REGEX.search(parsed.path))

    def is_show_resource(self, resource: Resource) -> bool:
        """If it's not an episode, assume it's a show."""
        return not self.is_episode_resource(resource)

    def process_resource(self, resource: Resource) -> Union[Show, Episode]:
        """Determine the type of the resource (Show or Episode) and fetch and
        enrich it accordingly (treat as Show by default). If it's an Episode,
        ensure that its parent Show is also processed."""
        if self.is_episode_resource(resource):
            return self._process_episode(resource)
        return self._process_show(resource)

    def associate_entity(self, entity: Union[Show, Episode]) -> List[Union[Show, Episode]]:
        """Make sure each entity is associated with a Show. Return a list of
        entities that have been touched. If it's a Show, return that directly.
        If it's an Episode, find and associate it with the Show, and add them
        both to the list."""
        touched: Set[Union[Show, Episode]] = set()
        if isinstance(entity, Episode):
            # pprint.pprint(entity)
            assert isinstance(
                entity, Episode), "We only serve Episodes in this here bar."
            # print(f"found episode: {entity.url}")
            show_id = entity.show_uuid
            show = self.catalog.get_show(show_id)
            if not show:
                show_resource = self._resolve_parent(entity.resource)
                show = self.process_resource(show_resource)
                assert isinstance(
                    show, Show), "We got something other than a Show!?"
                touched.add(entity)
                touched.add(show)  # Also add the newly created show
            # print(f"=> episode from show: {show.url}")
            episodes = show.episodes
            if entity not in episodes:
                # print(f"adding episode to episode list")
                episodes = show.episodes
                episodes.append(entity)
                show.episodes = sorted(episodes)
        # List of entities touched
        touched.add(entity)
        assert len(touched) == 1 or len(
            touched) == 2, "Association must touch exactly 1 or 2 entities."
        return list(touched)

    def _resolve_parent(self, resource: Resource) -> Resource:
        """A show is its own parent. An episode has exactly one show as its
        parent."""
        if self.is_show_resource(resource):
            return resource
        return self._episode_to_show_resource(resource)

    def _episode_to_show_resource(self, resource: Resource) -> Optional[Resource]:
        assert self.is_episode_resource(
            resource), "Failing to find a show from a show..."
        match = SHOW_FROM_EPISODE.match(resource.url)
        if match:
            show_url = match.group(1)
            # Try to get from catalog first
            show_resource = self.catalog.get_resource(show_url)
            if show_resource:
                return show_resource
            # Create a new Resource if not in catalog (show URL may not be in sitemap)
            return Resource(
                url=show_url,
                source=self.source.reference(show_url),
                last_updated=None
            )
        return None

    def _process_show(self, resource: Resource) -> Optional[Show]:
        """Fetch a Show page and extract basic details from HTML."""

        # Check if we have an exact match in cache
        for show in self.catalog.list_shows():
            if show.resource and show.resource == resource:
                return show

        show_reference = self.source.relative_path(resource.url)
        logger.debug("show_reference: %s", show_reference)
        html = self.source.get_reference(show_reference)
        # Handle file-based fallback here: If the reference isn't being
        # served over http, manually add index filename and try again.
        if not html:
            show_reference = show_reference + "/" + SHOW_FILENAME
            html = self.source.get_reference(show_reference)
        if html is None:
            logger.debug("Failed to retrieve file: %s", show_reference)
            return None

        # Parse HTML to extract show data
        parser = PageDataParser(html)
        show_data = parser.get_show_data()

        title = show_data.get("title")
        if not title:
            # Fallback to URL slug
            title = resource.url.rstrip("/").split("/")[-1].replace("-", " ").title()

        url = show_data.get("url") or resource.url

        # Generate deterministic UUID from URL
        show_uuid = uuid.uuid5(uuid.NAMESPACE_URL, resource.url)

        # Get last_updated from resource metadata if available
        last_updated = None
        if resource.metadata:
            last_updated = resource.metadata.get("lastmod")

        try:
            show = Show(
                title=title,
                url=url,
                uuid=show_uuid,
                description=show_data.get("description"),
                image=show_data.get("image"),
                resource=resource,
                last_updated=last_updated
            )
            self.catalog.add_show(show)
            if logger.isEnabledFor(TRACE_LEVEL_NUM):
                logger.trace("Final show object: %s", pprint.pformat(show_data))
            return show
        except Exception as e:
            logger.error(
                "Error creating show object for %s: %s", resource.url, e)
            return None

    def _process_episode(self, resource: Resource) -> Optional[Episode]:
        """Fetch the Episode page and extract details from HTML."""

        # Check if we have an exact match in cache
        for episode in self.catalog.list_episodes():
            if episode.resource and episode.resource == resource:
                return episode

        # Fetch the episode page HTML
        episode_reference = self.source.relative_path(
            resource.url + "/" + EPISODE_FILENAME)
        logger.debug("episode_reference: %s", episode_reference)
        html = self.source.get_reference(episode_reference)
        if html is None:
            logger.debug("Failed to retrieve file: %s", episode_reference)
            return None

        # Parse HTML to extract episode data
        parser = PageDataParser(html)
        episode_data = parser.get_episode_data()

        # Validate required fields
        title = episode_data.get("title")
        if not title:
            logger.error("Missing title for episode %s", resource.url)
            return None

        media_url = episode_data.get("media_url")
        if not media_url:
            logger.error("Missing media URL for episode %s", resource.url)
            return None
        media_url = strip_query_params(media_url)

        airdate = utils.parse_date(episode_data.get("airdate"))
        if not airdate:
            logger.error(
                "Missing or invalid airdate for episode %s", resource.url)
            return None

        url = episode_data.get("url") or resource.url

        # Generate deterministic UUID from URL
        episode_uuid = uuid.uuid5(uuid.NAMESPACE_URL, resource.url)

        # Extract show URL to get show UUID
        show_match = SHOW_FROM_EPISODE.match(resource.url)
        show_uuid = None
        if show_match:
            show_url = show_match.group(1)
            show_uuid = uuid.uuid5(uuid.NAMESPACE_URL, show_url)

        try:
            episode = Episode(
                title=title,
                airdate=airdate,
                url=url,
                media_url=media_url,
                uuid=episode_uuid,
                show_uuid=show_uuid,
                description=episode_data.get("description"),
                image=episode_data.get("image"),
                resource=resource
            )
            self.catalog.add_episode(episode)
            if logger.isEnabledFor(TRACE_LEVEL_NUM):
                logger.trace("Final episode object: %s",
                             pprint.pformat(episode_data))
            return episode
        except Exception as e:
            logger.error(
                "Error creating episode object for %s: %s", resource.url, e)
            return None
