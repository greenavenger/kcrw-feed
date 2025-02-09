"""Module to gather the list of shows"""

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


class ShowIndex:
    def __init__(self, source_url: str, extra_sitemaps: List[str] = None) -> None:
        """Parameters:
            source_url (str): The base URL (or local base path) for the site.
            extra_sitemaps (List[str], optional): Additional sitemap paths to include.
        """
        self.source_url = source_url
        self.extra_sitemaps = extra_sitemaps or []

    def gather_shows(self, source: str = "sitemap") -> List[str]:
        """Gather show URLs based on the chosen source.

        Parameters:
            source (str): Which source to use: "sitemap" (default) or "feed".

        Returns:
            List[str]: A list of show URLs."""
        if source == "sitemap":
            sitemap_urls = self.find_sitemaps()
            all_show_urls = []
            for sitemap in sitemap_urls:
                urls = self.read_sitemap(sitemap)
                # Only include URLs that match the music-related patterns.
                urls = [url for url in urls if MUSIC_FILTER_RE.search(url)]
                all_show_urls.extend(urls)
            return all_show_urls
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
        robots_path = self.source_url + ROBOTS_FILE
        robots_bytes = utils.get_file(robots_path)
        if not robots_bytes:
            raise FileNotFoundError(f"robots.txt not found at {robots_path}")
        robots_txt = robots_bytes.decode("utf-8")
        rp = urobot.RobotFileParser()
        rp.parse(robots_txt.splitlines())
        sitemap_urls = rp.site_maps() or []
        # Append any extra sitemaps provided.
        sitemap_urls += [self.source_url + s for s in self.extra_sitemaps]
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
        return self._extract_locs(parsed)

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

    def parse_feeds(self, feed_path: str) -> List[str]:
        """Placeholder for gathering shows from RSS/Atom feeds.

        Parameters:
            feed_path (str): The directory or file containing feed data.

        Returns:
            List[str]: A list of show URLs."""
        # Implementation to be added later.
        return []
