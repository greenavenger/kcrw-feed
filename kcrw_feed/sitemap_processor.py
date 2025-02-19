"""Module to gather the urls of shows and episodes"""

from datetime import datetime
import logging
import re
from typing import Any, Dict, List
import urllib.robotparser as urobot
import xmltodict

from kcrw_feed import source_manager
from kcrw_feed.source_manager import BaseSource, HttpsSource, CacheSource

# Regular expression to match sitemap XML filenames.
SITEMAP_RE = re.compile(r"sitemap.*\.xml", re.IGNORECASE)
# Filter for URLs that pertain to music shows.
MUSIC_FILTER_RE = re.compile(
    r"(/sitemap-shows/music/|/music/shows/)", re.IGNORECASE)
ROBOTS_FILE = "robots.txt"

logger = logging.getLogger("kcrw_feed")


class SitemapProcessor:
    def __init__(self, source: BaseSource) -> None:
        """Parameters:
            source: The base URL (or local base path) for the site.
        """
        self.source = source
        self._sitemap_entities: Dict[str, Any] = {}

    # Accessor Methods
    def get_all_entries(self) -> List[dict]:
        """
        Return all sitemap entry dictionaries.

        Returns:
            List[dict]: A list of all entries stored in the processor.
        """
        return list(self._sitemap_entities.values())

    def get_entries_after(self, dt: datetime) -> List[dict]:
        """
        Return sitemap entries with a lastmod date later than dt.

        Parameters:
            dt (datetime): The threshold datetime.

        Returns:
            List[dict]: A list of entries updated after dt.
        """
        results = []
        for entry in self._sitemap_entities.values():
            lastmod_str = entry.get("lastmod")
            if lastmod_str:
                try:
                    lastmod_dt = datetime.fromisoformat(lastmod_str)
                    if lastmod_dt > dt:
                        results.append(entry)
                except ValueError:
                    # Skip entries with an unparsable date.
                    continue
        return results

    def get_entries_between(self, start: datetime, end: datetime) -> List[dict]:
        """
        Return sitemap entries with a lastmod date between start and end (inclusive).

        Parameters:
            start (datetime): The start datetime.
            end (datetime): The end datetime.

        Returns:
            List[dict]: A list of entries with lastmod between start and end.
        """
        results = []
        for entry in self._sitemap_entities.values():
            lastmod_str = entry.get("lastmod")
            if lastmod_str:
                try:
                    lastmod_dt = datetime.fromisoformat(lastmod_str)
                    if start <= lastmod_dt <= end:
                        results.append(entry)
                except ValueError:
                    continue
        return results

    # Populate Methods
    def gather_entries(self) -> List[str]:
        """Gather show resources. Returns: List[str]: A list of show
        references."""
        sitemap_entries: List[str] = []
        logger.debug("Gathering sitemap entries from %s", self.source)
        sitemaps = self.find_sitemaps()
        for sitemap in sitemaps:
            self.read_sitemap(sitemap)
        sitemap_entries = list(self._sitemap_entities.keys())
        return sorted(sitemap_entries)

    def find_sitemaps(self) -> List[str]:
        """Reads the robots.txt file and extracts sitemap URLs.

        Returns:
            List[str]: A list of sitemap URLs."""
        root_sitemap = self._sitemap_from_robots()
        logger.debug("Found sitemap URLs: %s", sitemap_urls)
        sitemaps = [self.source.rewrite_base_source(
            url) for url in sitemap_urls]
        sitemap_urls = [url for url in sitemap_urls if SITEMAP_RE.search(url)]
        logger.debug("Rewritten sitemaps: %s", sitemaps)
        # # Append any extra sitemaps provided.
        # sitemap_urls += [source_manager.normalize_location(self.source_url, s)
        #                  for s in self.extra_sitemaps]
        # Filter to only include sitemap URLs.
        # Remove duplicates.
        unique_sitemaps = list(set(sitemap_urls))
        if logger.isEnabledFor(getattr(logging, "TRACE", 5)):
            logger.trace("Found sitemap URLs: %s", unique_sitemaps)
        return unique_sitemaps

    def _sitemap_from_robots(self):
        robots_bytes = self.source.get_resource(ROBOTS_FILE)
        if not robots_bytes:
            raise FileNotFoundError(f"robots.txt not found at {robots_path}")
        robots_txt = robots_bytes.decode("utf-8")
        rp = urobot.RobotFileParser()
        rp.parse(robots_txt.splitlines())
        sitemap_urls = rp.site_maps() or []
        return sitemap_urls

    def read_sitemap(self, sitemap: str) -> List[str]:
        """Reads a sitemap XML file and extracts all URLs from <loc>
        elements recursively.

        Parameters:
            sitemap (str): The path (or URL) to the sitemap XML.

        Returns:
            List[str]: A list of URL strings."""
        sitemap_bytes = source_manager.get_file(sitemap)
        if not sitemap_bytes:
            logger.error("Sitemap file not found: %s", sitemap)
            return []
        sitemap_text = sitemap_bytes.decode("utf-8")
        if logger.isEnabledFor(getattr(logging, "TRACE", 5)):
            logger.trace("Parsing sitemap XML from: %s", sitemap)
        parsed = xmltodict.parse(sitemap_text)
        self._extract_entries(parsed)

    def _extract_locs(self, data) -> List[str]:
        """Recursively extract all values associated with the key 'loc'.

        Parameters:
            data: The parsed XML (dict or list) from xmltodict.

        Returns:
            List[str]: A list of URL strings."""
        locs = []
        if isinstance(data, dict):
            for key, value in data.items():
                if key.lower() == "loc" and isinstance(value, str):
                    locs.append(value)
                else:
                    locs.extend(self._extract_locs(value))
        elif isinstance(data, list):
            for item in data:
                locs.extend(self._extract_locs(item))
        return locs

    def _extract_entries(self, data) -> List[dict]:
        """Recursively traverse a dictionary or list parsed by xmltodict and
        collect all sitemap entries. Each entry is a dict with at least a
        "loc" key, and optionally "lastmod", "changefreq", and "priority".

        Parameters:
            data: The parsed XML (a dict or list) from xmltodict.

        Returns:
            List[dict]: A list of sitemap entry dictionaries."""
        if isinstance(data, dict):
            # Check if this dict appears to represent a sitemap entry:
            # We use case-insensitive matching for keys.
            lower_keys = {k.lower(): k for k in data.keys()}
            if "loc" in lower_keys:
                entry = {"loc": data[lower_keys["loc"]]}
                if "lastmod" in lower_keys:
                    entry["lastmod"] = data[lower_keys["lastmod"]]
                if "changefreq" in lower_keys:
                    entry["changefreq"] = data[lower_keys["changefreq"]]
                if "priority" in lower_keys:
                    entry["priority"] = data[lower_keys["priority"]]
                # Add only entries that match the music filter.
                if MUSIC_FILTER_RE.search(entry["loc"]):
                    self._sitemap_entities[entry["loc"]] = entry
                    if logger.isEnabledFor(getattr(logging, "TRACE", 5)):
                        logger.trace("Extracted entry: %s", entry)
            else:
                # Otherwise, traverse all values.
                for value in data.values():
                    self._extract_entries(value)
        elif isinstance(data, list):
            for item in data:
                self._extract_entries(item)

    def parse_feeds(self, feed_path: str) -> List[str]:
        """Placeholder for gathering shows from RSS/Atom feeds.

        Parameters:
            feed_path (str): The directory or file containing feed data.

        Returns:
            List[str]: A list of show URLs."""
        logger.info("parse_feeds() is not yet implemented.")
        # Implementation to be added later.
        return []
