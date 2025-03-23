"""Module to enrich sitemap data and populate the core model objects"""

from __future__ import annotations
from datetime import datetime
import json
import logging
import pprint
# TODO: Add requests when we're ready to test things against the live site.
# import requests
from typing import Any, List, Dict, Optional
import uuid
import extruct
from bs4 import BeautifulSoup

from kcrw_feed.models import Show, Episode, Host, Resource
from kcrw_feed.source_manager import BaseSource, strip_query_params
from kcrw_feed import utils
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM

SHOW_FILE = "/index.html"
EPISODE_FILE = "/player.json"

logger = logging.getLogger("kcrw_feed")


class ShowProcessor:
    """ShowProcessor fetches a show or an episode page and extracts details
    to enrich a raw URL into a full domain model object."""

    def __init__(self, source: BaseSource, timeout: int = 10):
        self.source = source
        self.timeout = timeout
        # This will hold a dict of Show objects keyed by UUID.
        self._model_cache: Dict[uuid.UUID, Show | Episode] = {}

    # Accessors
    def get_show_by_url(self, url: str) -> Optional[Show]:
        """Return a Show from the internal cache matching the given
        URL, if available."""
        for entity in self._model_cache.values():
            if entity.url == url:
                return entity
        return None

    def get_show_by_uuid(self, uuid: uuid.UUID) -> Optional[Show]:
        """Return a Show from the internal cache matching the given
        uuid, if available."""
        return self._model_cache.get(uuid, None)

    def get_shows(self) -> List[Show]:
        """Return a list of all Shows."""
        shows: List[Show] = []
        for entity in self._model_cache.values():
            if isinstance(entity, Show):
                shows.append(entity)
        return sorted(shows)

    def get_episodes(self) -> List[Episode]:
        """Return a list of all Episodes."""
        episodes: List[Episode] = []
        for entity in self._model_cache.values():
            if isinstance(entity, Episode):
                episodes.append(entity)
        return episodes

    # Core methods

    def fetch(self, url: str, resource: Optional[Resource]) -> Optional[Show | Episode]:
        """Dispatch show or episode processing and return the corresponding object."""
        if self.source.is_show(url):
            logger.debug("Fetching show: %s", url)
            return self._fetch_show(url, resource=resource)
        logger.debug("Fetching episode: %s", url)
        return self._fetch_episode(url, resource=resource)

    def _fetch_show(self, url: str, resource: Optional[Resource]) -> Optional[Show]:
        """Fetch a Show page and extract basic details."""
        show_file = self.source.relative_path(url + SHOW_FILE)
        logger.debug("show_file: %s", show_file)
        html = self.source.get_resource(show_file)
        if html is None:
            logger.debug("Failed to retrieve file: %s", show_file)
            return

        # Try to extract structured data using extruct (e.g., microdata).
        data = extruct.extract(html, base_url=url, syntaxes=["microdata"])
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

        # TODO: Permanently remove Episode population in the Show context
        # since we don't have a Resource here.
        # episode_data = None
        # # Look for an object that indicates it's an episode (or similar).
        # for item in data.get("microdata", []):
        #     if isinstance(item, dict) and item.get("id", "").endswith("-episodes"):
        #         episode_data = item
        #         break
        episodes = []
        # if episode_data:
        #     episodes.extend(self._parse_episodes(episode_data))

        if show_data:
            show_html_id: str = show_data.get("id")
            logger.trace("show_html_id: %s", show_html_id)
            assert show_html_id is not None, "Failed to extract UUID!"
            show_uuid = utils.extract_uuid(show_html_id)
            logger.debug("show_uuid: %s", show_uuid)

            if resource:
                last_updated = resource.metadata.get("lastmod")
            else:
                last_updated = datetime.now()
            logger.trace("last_updated: %s", last_updated)

            if show_uuid in self._model_cache:
                # Show has already been fetched, so return cached object
                show = self._model_cache.get(show_uuid)
            else:
                show = Show(
                    title=show_data.get("name", url.split("/")[-1]),
                    url=show_data.get("properties", {}).get(
                        "mainEntityOfPage"),
                    uuid=show_uuid,
                    description=show_data.get(
                        "properties", {}).get("description"),
                    hosts=self._parse_hosts(show_data),
                    episodes=episodes,      # Episodes can be added later.
                    type=show_data.get("type"),
                    resource=resource,
                    last_updated=last_updated
                )
                self._model_cache[show.uuid] = show
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
            self._model_cache[show.url] = show
            raise NotImplementedError
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Final show object: %s", pprint.pformat(show))
        return show

    def _parse_episodes(self, episode_data: dict) -> List[Episode]:
        """Parse episode data extracted from structured data."""
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("episode_data: %s", pprint.pformat(episode_data))

        episodes = []
        if episode_data:
            episodes_list: list = episode_data.get(
                "properties", {}).get("itemListElement", [])
            for item in episodes_list:
                if isinstance(item, dict) and item.get("type") == "http://schema.org/ListItem":
                    url = item.get("properties", {}).get("url")
                    episode_html_id: str = item.get("id")
                    assert episode_html_id is not None, "Failed to extract episode UUID!"
                    logger.trace("episode_html_id: %s", episode_html_id)
                    episode_uuid = utils.extract_uuid(item.get("id"))
                    logger.debug("episode_uuid: %s", episode_uuid)
                    if not url and not episode_uuid:
                        logger.error("Failed to extract episode URL!")
                        continue
                    elif url and episode_uuid:
                        # Called from _fetch_show, we don't have Episode metadata
                        episode = self._fetch_episode(
                            url, resource={}, uuid=episode_uuid)
                    else:
                        episode = self._fetch_episode(url, resource={})
                    if episode:
                        episodes.append(episode)
        return utils.uniq_by_uuid(episodes)

    def _fetch_episode(self, url: str, resource: Optional[Resource], uuid: Optional[str] = "") -> Optional[Episode]:
        """Fetch the player for the Episode and extract details."""

        episode: Episode

        if uuid and uuid in self._model_cache:
            # Episode has been fetched, so return cached object
            return self._model_cache.get(uuid)

        episode_file = self.source.relative_path(url + EPISODE_FILE)
        logger.debug("episode_file: %s", episode_file)
        episode_bytes = self.source.get_resource(episode_file)
        episode_data = None
        if episode_bytes is not None:
            try:
                episode_str = episode_bytes.decode("utf-8")
                episode_data = json.loads(episode_str)
            except json.JSONDecodeError as e:
                logger.error("Error decoding JSON: %s", e)
        else:
            logger.debug("Failed to retrieve file: %s", episode_file)
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
                self._model_cache[episode.uuid] = episode
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Final episode object: %s",
                         pprint.pformat(episode_data))
        return episode

    def _parse_hosts(self, show_data: dict) -> Optional[List[Host]]:
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
            if author_uuid and author_uuid in self._model_cache:
                hosts = self._model_cache.get(author_uuid)
            else:
                hosts.append(Host(
                    name=author_data.get("properties", {}).get("name"),
                    uuid=author_uuid,
                    url=author_data.get("properties", {}).get("url"),
                    socials=show_data.get("properties", {}).get("sameAs", []),
                    type=author_data.get("type"),
                ))
            if author_uuid:
                self._model_cache[author_uuid] = hosts
        hosts = utils.uniq_by_uuid(hosts)
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("hosts: %s", pprint.pformat(hosts))
        return hosts
