"""Module to enrich resource data and populate the core model objects"""

from __future__ import annotations
from datetime import datetime
import json
import logging
import pprint
import re
from typing import List, Dict, Optional, Set, Union
from urllib.parse import urljoin, urlparse, urlunparse
import uuid
import extruct
from bs4 import BeautifulSoup

from kcrw_feed.models import Show, Episode, Host, Resource, FilterOptions
from kcrw_feed.station_catalog import BaseStationCatalog
from kcrw_feed.source_manager import BaseSource, strip_query_params
from kcrw_feed import utils
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM

SHOW_FILENAME = "index.html"  # Used only for CacheSource
EPISODE_FILENAME = "player.json"
# Match show URLs, paths that end with "/music/shows/<something>" (and an
# optional trailing slash)
SHOW_URL_REGEX = re.compile(r"/music/shows/[^/]+/?$")
# This regex matches URLs whose path contains at least two segments
# after "/music/shows/"
EPISODE_URL_REGEX = re.compile(r"/music/shows/[^/]+/[^/]+")
# This regex captures the protocol, domain, and the first segment after "/music/shows/"
SHOW_FROM_EPISODE = re.compile(r'^(https?://[^/]+/music/shows/[^/]+)(/.*)?$')


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
        enrich it accordingly (treat as Show by default). If it’s an Episode,
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
            return self.catalog.get_resource(match.group(1))
        return None

    def _process_show(self, resource: Resource) -> Optional[Show]:
        """Fetch a Show page and extract basic details."""

        # Checking by url is the best we can do here
        for show in self.catalog.list_shows():
            if resource.url == show.url:
                return show

        show_reference = self.source.relative_path(resource.url + "/")
        logger.debug("show_reference: %s", show_reference)
        html = self.source.get_reference(show_reference)
        # Handle file-based fallback here: If the reference isn't being
        # served over http, manually add index filename and try again.
        if not html:
            show_reference = show_reference + "/" + SHOW_FILENAME
            html = self.source.get_reference(show_reference)
        if html is None:
            logger.debug("Failed to retrieve file: %s", show_reference)
            return

        # Try to extract structured data using extruct (e.g., microdata).
        data = extruct.extract(
            html, base_url=resource.url, syntaxes=["microdata"])
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Extracted data: %s", pprint.pformat(data))

        show: Show
        show_uuid: uuid.UUID

        show_data = None
        # Look for an object that indicates it's a radio series.
        for item in data.get("microdata", []):
            if isinstance(item, dict) and item.get("type") == "http://schema.org/RadioSeries":
                show_data = item
                break
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("show_data: %s", pprint.pformat(show_data))

        episodes: List[Episode] = []
        episode_data = None
        # Look for an object that indicates it's an episode (or similar).
        for item in data.get("microdata", []):
            if isinstance(item, dict) and item.get("id", "").endswith("-episodes"):
                episode_data = item
                break
        if episode_data:
            episodes.extend(self._parse_show_episodes(episode_data))

        last_updated = resource.metadata.get("lastmod")
        logger.trace("last_updated: %s", last_updated)
        image_loc = resource.metadata.get(
            "image:image", {}).get("image:loc")
        assert image_loc != "DEADBEEF"
        logger.trace("image_loc: %s", image_loc)

        # Parse response to fill our our Show object
        if show_data:
            show_html_id: str = show_data.get("id")
            logger.trace("show_html_id: %s", show_html_id)
            assert show_html_id is not None, "Failed to extract UUID!"
            show_uuid = utils.extract_uuid(show_html_id)
            logger.debug("show_uuid: %s", show_uuid)

            show = Show(
                title=show_data.get("name", resource.url.split("/")[-1]),
                url=show_data.get("properties", {}).get(
                    "mainEntityOfPage"),
                image=image_loc,
                uuid=show_uuid,
                description=show_data.get(
                    "properties", {}).get("description"),
                hosts=self._process_hosts(show_data),
                episodes=episodes,
                type=show_data.get("type"),
                resource=resource,
                last_updated=last_updated
            )
        else:
            # Fallback: use BeautifulSoup to get the title.
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.text.strip(
            ) if title_tag else url.split("/")[-1]
            show = Show(
                title=title,
                url=url,
                last_updated=last_updated,
                metadata={}
            )
            raise NotImplementedError
        if show:
            self.catalog.add_show(show)
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Final show object: %s", pprint.pformat(show))
        return show

    def _parse_show_episodes(self, episode_data: dict) -> List[Episode]:
        """Parse episode data extracted from structured data."""
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("episode_data: %s", pprint.pformat(episode_data))

        episodes: List[Episode] = []
        episode_urls: Set[str] = set()
        # Grab urls for episodes listed on the show page. We do this here
        # instead of getting the full list of resources from the catalog
        # to reduce load on kcrw.com. Some shows have 4k or more episodes!
        if episode_data:
            episodes_list = episode_data.get(
                "properties", {}).get("itemListElement", [])
            for item in episodes_list:
                if isinstance(item, dict) and item.get("type") == "http://schema.org/ListItem":
                    url = item.get("properties", {}).get("url")
                    if url:
                        episode_urls.add(url)
        # Enhance episodes on the show page
        if episode_urls:
            for url in episode_urls:
                resource = self.catalog.get_resource(url)
                if resource:
                    episode = self._process_episode(resource)
                    if episode:
                        episodes.append(episode)
        return sorted(episodes)

    def _process_episode(self, resource: Resource) -> Optional[Episode]:
        """Fetch the player for the Episode and extract details."""

        # Checking by url is the best we can do here
        for episode in self.catalog.list_episodes():
            if resource.url == episode.url:
                return episode

        episode: Episode
        episode_reference = self.source.relative_path(
            resource.url + "/" + EPISODE_FILENAME)
        logger.debug("episode_reference: %s", episode_reference)
        episode_bytes = self.source.get_reference(episode_reference)
        episode_data = None
        if episode_bytes is not None:
            try:
                episode_str = episode_bytes.decode("utf-8")
                episode_data = json.loads(episode_str)
            except json.JSONDecodeError as e:
                logger.error("Error decoding JSON: %s", e)
        else:
            logger.debug("Failed to retrieve file: %s", episode_reference)
            return
        if episode_data:
            episode = Episode(
                title=episode_data.get("title", ""),
                airdate=utils.parse_date(episode_data.get("airdate")),
                url=episode_data.get("url"),
                media_url=strip_query_params(
                    episode_data.get("media", "")[0].get("url")),
                uuid=utils.extract_uuid(episode_data.get("uuid")),
                show_uuid=utils.extract_uuid(episode_data.get("show_uuid")),
                hosts=[utils.extract_uuid(item.get("uuid"))
                       for item in episode_data.get("hosts", [])],
                description=episode_data.get("html_description"),
                songlist=episode_data.get("songlist"),
                image=episode_data.get("image"),
                type=episode_data.get("content_type"),
                duration=episode_data.get("duration"),
                ending=utils.parse_date(episode_data.get("ending")),
                last_updated=utils.parse_date(episode_data.get("modified")),
                resource=resource
            )
            if episode.uuid:
                self.catalog.add_episode(episode)
        if episode:
            self.catalog.add_episode(episode)
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Final episode object: %s",
                         pprint.pformat(episode_data))
        return episode

    def _process_hosts(self, show_data: dict) -> Optional[List[Host]]:
        """Try to parse a host object from structured data."""
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("show_data for hosts: %s", pprint.pformat(show_data))
        hosts = []
        if show_data:
            author_data = show_data.get("properties", {}).get("author", {})
            if logger.isEnabledFor(TRACE_LEVEL_NUM):
                logger.trace("author_data: %s", pprint.pformat(author_data))
            if not author_data:
                logger.info("No hosts data found!")
                logger.debug("hosts: %s", hosts)
                return []
            author_uuid = utils.extract_uuid(author_data.get("id"))
            hosts.append(Host(
                name=author_data.get("properties", {}).get("name"),
                uuid=author_uuid,
                url=author_data.get("properties", {}).get("url"),
                socials=show_data.get("properties", {}).get("sameAs", []),
                type=author_data.get("type"),
            ))
        hosts = utils.uniq_by_uuid(hosts)
        for host in hosts:
            if host not in self.catalog.list_hosts():
                self.catalog.add_host(host)
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("hosts: %s", pprint.pformat(hosts))
        return hosts
