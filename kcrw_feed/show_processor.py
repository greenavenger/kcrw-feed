"""Module to enrich sitemap data and populate the core model objects"""

from __future__ import annotations
import json
import pprint
# TODO: Add requests when we're ready to test things against the live site.
# import requests
from urllib.parse import urlparse, urljoin
import extruct
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional, Sequence
import uuid

from kcrw_feed.models import Show, Episode, Host
from kcrw_feed import utils


class ShowProcessor:
    """ShowProcessor fetches a show or an episode page  and extracts details
    to enrich a raw URL into a full domain model object."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        # This will hold a dict of Show objects keyed by UUID.
        self._model_cache: Dict[uuid.UUID, Show] = {}

    # Accessors
    def get_show_by_url(self, url: str) -> Optional[Show]:
        """Return a Show from the internal cache matching the given URL, if available."""
        for show in self._model_cache.values():
            if show.url == url:
                return show
        return None

    # Core methods
    def fetch(self, url: str):
        """Given a URL, decide whether it is a Show page or an Episode page
        and return the corresponding object."""
        print(f"Fetching: {url}")
        # Parse the URL to determine its structure.
        parsed = urlparse(url)
        # Remove leading/trailing slashes and split path into segments.
        path_parts = parsed.path.strip("/").split("/")
        print(f"path_parts: {path_parts}")
        # We're expecting a structure like: music/shows/<show>[/<episode>]
        try:
            music_idx = path_parts.index("music")
            shows_idx = path_parts.index("shows")
            print(f"music_idx: {music_idx}, shows_idx: {shows_idx}")
        except ValueError:
            # If the URL doesn't match our expected structure, assume it's a Show.
            return self._fetch_show(url)

        # Determine how many segments come after "shows" in the path
        after = path_parts[shows_idx+1:]
        print(f"after: {after}")
        if len(after) == 0:
            # No show identifier found; fallback.
            # return self._fetch_show(url)
            assert False, f"No show identifier found! {url}"
        elif len(after) == 1:
            print("Fetching show: ", url)
            return self._fetch_show(url)
        else:
            print("Fetching episode: ", url)
            return self._fetch_episode(url)
        # TODO: Should I return show_uuid, maybe?
        # return self._fetch_show(url)

    def _fetch_show(self, url: str) -> Show:
        """Fetch a Show page and extract basic details."""
        # TODO: remove after testing
        html = utils.get_file("./tests/data/henry-rollins/henry-rollins")
        # html = utils.get_file(url)
        # Try to extract structured data using extruct (e.g., microdata).
        data = extruct.extract(html, base_url=url, syntaxes=["microdata"])
        pprint.pprint(data)

        show: Show
        show_uuid: uuid.UUID

        show_data = None
        # Look for an object that indicates it's a radio series.
        for item in data.get("microdata", []):
            if isinstance(item, dict) and item.get("type") == "http://schema.org/RadioSeries":
                show_data = item
                break
        print("show_data:")
        pprint.pprint(show_data)

        episode_data = None
        # Look for an object that indicates it's an episode (or similar).
        for item in data.get("microdata", []):
            if isinstance(item, dict) and item.get("id", "").endswith("-episodes"):
                episode_data = item
                break
        episodes = []
        if episode_data:
            episodes.extend(self._parse_episodes(episode_data))

        if show_data:
            show_html_id: str = show_data.get("id")
            print("show_html_id:", show_html_id)
            assert show_html_id is not None, "Failed to extract UUID!"
            show_uuid = utils.extract_uuid(show_html_id)
            print("show_uuid:", show_uuid)
            if show_uuid in self._model_cache:
                # Show has already been fetched, so return cached object
                show = self._model_cache.get(show_uuid)
            else:
                show = Show(
                    title=show_data.get("name", url.split("/")[-1]),
                    url=url,
                    uuid=show_uuid,
                    description=show_data.get(
                        "properties", {}).get("description"),
                    # Host enrichment can be added later.
                    hosts=self._parse_hosts(show_data),
                    episodes=episodes,      # Episodes can be added later.
                    type=show_data.get("type"),
                    last_updated=datetime.now()  # ,  # Or parse if available.
                    # metadata=show_data
                )
                self._model_cache["uuid"] = show
        else:
            # Fallback: use BeautifulSoup to get the title.
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.text.strip() if title_tag else url.split("/")[-1]
            show = Show(
                title=title,
                url=url,
                last_updated=datetime.now(),
                metadata={}
            )
            self._model_cache["uuid"] = show
        pprint.pprint(show)
        return show

    def _parse_episodes(self, episode_data: dict) -> List[Episode]:
        """Parse episode data extracted from structured data."""
        print("episode_data:")
        pprint.pprint(episode_data)

        episode: Episode
        episode_uuid: uuid.UUID

        episodes = []
        if episode_data:
            episodes_list: list = episode_data.get(
                "properties", {}).get("itemListElement", [])
            for item in episodes_list:
                if isinstance(item, dict) and item.get("type") == "http://schema.org/ListItem":
                    url = item.get("properties", {}).get("url")
                    episode_html_id: str = item.get("id")
                    assert episode_html_id is not None, "Failed to extract episode UUID!"
                    print("episode_html_id:", episode_html_id)
                    episode_uuid = utils.extract_uuid(item.get("id"))
                    print("episode_uuid:", episode_uuid)
                    if not url and not episode_uuid:
                        print("Failed to extract episode URL!")
                        continue
                    elif url and episode_uuid:
                        episode = self._fetch_episode(url, episode_uuid)
                    else:
                        episode = self._fetch_episode(url)
                    episodes.append(episode)
        return self._dedup_by_uuid(episodes)

    def _fetch_episode(self, url: str, uuid: Optional[str] = "") -> Episode:
        """Fetch the player for the Episode and extract details."""
        if uuid and uuid in self._model_cache:
            # Episode has been fetched, so return cached object
            return self._model_cache.get(uuid)

        # TODO: remove after testing
        # "./tests/data/henry-rollins/kcrw-broadcast-825_player.json")
        local_file = "./tests/data/henry-rollins/" + \
            url.split("/")[-1] + "_player.json"
        print("local_file:", local_file)
        episode_bytes = utils.get_file(local_file)
        if episode_bytes is not None:
            try:
                episode_str = episode_bytes.decode("utf-8")
                episode_data = json.loads(episode_str)
                # TODO: Do we want to use case-insensitive matching for keys?
                # # We use case-insensitive matching for keys.
                # pre_size = len(episode_data)
                # episode_data = {k.lower(): v for k, v in episode_data.items()}
                # assert len(episode_data) == pre_size, "Duplicate keys found"
            except json.JSONDecodeError as e:
                print("Error decoding JSON:", e)
        else:
            print("Failed to retrieve file")
        # pprint.pprint(episode_data)

        if episode_data:
            episode = Episode(
                title=episode_data.get("title", ""),  # case sensitive!
                airdate=self._parse_date(episode_data.get("airdate")),
                url=episode_data.get("url"),  # episode url
                media_url=utils.strip_query_params(
                    episode_data.get("media", "")[0].get("url")),
                uuid=utils.extract_uuid(episode_data.get("uuid")),
                show_uuid=utils.extract_uuid(episode_data.get("show_uuid")),
                # Store host(s) UUID here to avoid duplicate Host objects.
                hosts=[utils.extract_uuid(item.get("uuid"))
                       for item in episode_data.get("hosts", [])],
                description=episode_data.get("html_description"),
                songlist=episode_data.get("songlist"),
                image=episode_data.get("image"),
                # should this be schemas.org compliant?
                type=episode_data.get("content_type"),
                duration=episode_data.get("duration"),
                ending=self._parse_date(episode_data.get("ending")),
                last_updated=self._parse_date(episode_data.get("modified")),
                # metadata=episode_data
            )
            if episode.uuid:
                self._model_cache[episode.uuid] = episode
        pprint.pprint(episode)
        return episode

    def _parse_hosts(self, show_data: dict) -> Optional[List[Host]]:
        """Try to parse a host object from structured data."""
        hosts: List(Host) = []

        # TODO: Is there sometimes more than one host?
        print("show_data for hosts:")
        pprint.pprint(show_data)
        if show_data:
            # pprint.pprint(show_data)
            author_data = show_data.get("properties", {}).get("author", {})
            print("author_data:", author_data)
            if not author_data:
                print("No hosts data found!")
                print("hosts:", hosts)
                return []
            author_uuid = utils.extract_uuid(author_data.get("id"))
            if author_uuid and author_uuid in self._model_cache:
                # Host has been enriched, so return cached object
                hosts = self._model_cache.get(author_uuid)
            else:
                hosts.append(Host(
                    name=author_data.get("properties", {}).get("name"),
                    uuid=author_uuid,
                    url=author_data.get("properties", {}).get("url"),
                    socials=show_data.get(
                        "properties", {}).get("sameAs", []),
                    type=author_data.get("type"),
                    # metadata=author_data
                ))
            if author_uuid:
                self._model_cache[author_uuid] = hosts
        hosts = self._dedup_by_uuid(hosts)
        print("hosts:")
        pprint.pprint(hosts)
        return hosts

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Try to parse a date string into a datetime object."""
        if date_str:
            try:
                return datetime.fromisoformat(date_str)
            except ValueError:
                return None
        return None

    def _dedup_by_uuid(self, entities: Sequence[Episode | Host]) -> list[Episode | Host]:
        """Deduplicate a list of entities based on UUID.

        Assumes that all items in the list are of the same type (either all Episode or all Host).
        Raises an AssertionError if a mixed list is provided."""
        if entities:
            first_type = type(entities[0])
            for e in entities:
                assert type(
                    e) == first_type, "Mixed types provided to _dedup_by_uuid"
        seen = {}
        deduped: list[Episode | Host] = []
        for e in entities:
            if e.uuid is None:
                deduped.append(e)
            elif e.uuid not in seen:
                seen[e.uuid] = True
                deduped.append(e)
        return deduped
