"""Module to gather the list of shows"""

import pprint
import re
from typing import List
import urllib.robotparser as urobot
import xmltodict
import io

from kcrw_feed import utils

# Regular expression to match sitemap XML filenames.
SITEMAP_RE = re.compile(r"sitemap.*\.xml", re.IGNORECASE)
# Filter for URLs that pertain to music shows.
MUSIC_FILTER_RE = re.compile(
    r"(/sitemap-shows/music/|/music/shows/)", re.IGNORECASE)
ROBOTS_FILE = "robots.txt"


class SitemapProcessor:
    def __init__(self, source_url: str, extra_sitemaps: List[str] = None) -> None:
        """Parameters:
            source_url (str): The base URL (or local base path) for the site.
            extra_sitemaps (List[str], optional): Additional sitemap paths to include.
        """
        self.source_url = source_url
        self.extra_sitemaps = extra_sitemaps or []
        self._sitemap_entries = {}

    def gather_shows(self, source: str = "sitemap") -> List[str]:
        """Gather show URLs based on the chosen source.

        Parameters:
            source (str): Which source to use: "sitemap" (default) or "feed".

        Returns:
            List[str]: A list of show URLs."""
        if source == "sitemap":
            sitemap_urls = self.find_sitemaps()
            for sitemap in sitemap_urls:
                self.read_sitemap(sitemap)
            return sorted(list(self._sitemap_entries.keys()))
        elif source == "feed":
            # Placeholder for future feed-based gathering.
            return self.parse_feeds("path/to/feeds")
        else:
            raise ValueError("Unknown source type")

    def find_sitemaps(self) -> List[str]:
        """Reads the robots.txt file and extracts sitemap URLs.

        Returns:
            List[str]: A list of sitemap URLs."""
        # Construct the robots.txt location.
        robots_path = utils.normalize_location(self.source_url, ROBOTS_FILE)
        pprint.pprint(robots_path)
        robots_bytes = utils.get_file(robots_path)
        if not robots_bytes:
            raise FileNotFoundError(f"robots.txt not found at {robots_path}")
        robots_txt = robots_bytes.decode("utf-8")
        rp = urobot.RobotFileParser()
        rp.parse(robots_txt.splitlines())
        sitemap_urls = rp.site_maps() or []
        # Append any extra sitemaps provided.
        sitemap_urls += [utils.normalize_location(self.source_url, s)
                         for s in self.extra_sitemaps]
        # Filter to only include sitemap URLs.
        sitemap_urls = [url for url in sitemap_urls if SITEMAP_RE.search(url)]
        # Remove duplicates.
        return list(set(sitemap_urls))

    def read_sitemap(self, sitemap: str) -> List[str]:
        """Reads a sitemap XML file and extracts all URLs from <loc>
        elements recursively.

        Parameters:
            sitemap (str): The path (or URL) to the sitemap XML.

        Returns:
            List[str]: A list of URL strings."""
        sitemap_bytes = utils.get_file(sitemap)
        if not sitemap_bytes:
            return []
        sitemap_text = sitemap_bytes.decode("utf-8")
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
                # Add only entries that match the music filter
                if MUSIC_FILTER_RE.search(entry["loc"]):
                    self._sitemap_entries[entry["loc"]] = entry
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
        # Implementation to be added later.
        return []
