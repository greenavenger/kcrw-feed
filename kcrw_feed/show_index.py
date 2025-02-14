"""Module to collect the shows"""

from datetime import datetime
import io
import pprint
import re
from typing import List, Optional
import urllib.robotparser as urobot
import xmltodict

from kcrw_feed.models import Show, Episode
# Handles raw sitemap parsing
from kcrw_feed.sitemap_processor import SitemapProcessor
# Handles enrichment (scraping) of Show details
from kcrw_feed.show_processor import ShowProcessor
from kcrw_feed import utils


class ShowIndex:
    def __init__(self, source_url: str, extra_sitemaps: List[str] = None) -> None:
        """Parameters:
            source_url (str): The base URL (or local base path) for the site.
            extra_sitemaps (List[str], optional): Additional sitemap paths to include.
        """
        self.source_url = source_url
        self.extra_sitemaps = extra_sitemaps or []
        # Instantiate the helper components.
        self.sitemap_processor = SitemapProcessor(source_url, extra_sitemaps)
        self.show_processor = ShowProcessor()
        # This will hold a dict keyed by URL with sitemap metadata (e.g. lastmod).
        # TODO: Maybe remove this, as it could just be wasted memory.
        self._sitemap_urls = List[str]
        # This will hold fully enriched Show objects.
        self.shows: List[Show] = {}

    def process_sitemap(self, source: str = "sitemap") -> List[str]:
        """Use SitemapProcessor to get a list of raw show URLs."""
        self._sitemap_urls = self.sitemap_processor.gather_entries(source)
        return self._sitemap_urls

    def update(self, source: str = "sitemap", update_after: Optional[datetime] = None,
               selected_urls: Optional[List[str]] = None) -> int:
        """Update the repository with enriched Show objects.

        Parameters:
            update_after (datetime, optional): Only update shows that have changed after this timestamp.
            selected_urls (List[str], optional): If provided, only update shows whose URL is in this list.
        """
        raw_urls = self.process_sitemap("sitemap")
        # TODO: remove after testing
        raw_urls = [url.replace("https://www.kcrw.com",
                                "https://www.example.com") for url in raw_urls]
        # Optionally filter raw_urls based on selected_urls.
        selected_urls = [url.rstrip("/") for url in selected_urls]  # normalize
        if selected_urls:
            raw_urls = [url for url in raw_urls if url in selected_urls]

        updated_shows = []
        for url in raw_urls:
            # TODO: Optionally, check update_after against metadata.
            # This returns a fully enriched Show object.
            show = self.show_processor.fetch(url)
            # Make sure the show has a unique identifier.
            if not show.uuid:
                # If no UUID is provided, you might use the URL as a fallback key.
                key = show.url
            else:
                key = show.uuid
            self.shows[key] = show
            updated_shows.append(show)
        return len(updated_shows)

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
        episodes = []
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
