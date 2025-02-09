"""Module to gather the list of shows"""

import pprint
import re
from typing import Optional, List
import urllib.robotparser as urobot
import xmltodict
import io

from kcrw_feed import utils

# Regular expression to match URLs
SITEMAP_RE = re.compile(r"sitemap.*\.xml", re.IGNORECASE)
MUSIC_SITEMAP_RE = re.compile(r"/sitemap-shows/music/", re.IGNORECASE)
MUSIC_SHOW_RE = re.compile(r"/music/shows/", re.IGNORECASE)
ROBOTS_FILE = "robots.txt"


class ShowIndex:
    def __init__(self, source_url: str, sitemap_files: List[str] = []) -> None:
        # Save the base URL and optional sitemap files.
        self.source_url = source_url
        self.sitemap_files = sitemap_files

    def gather_shows(self, source: str = "sitemap") -> List[str]:
        """Gather show URLs based on the chosen source.

        Parameters:
            source (str): Which source to use for gathering shows.
                          "sitemap" (default) uses the sitemap XML(s).
                          "feed" can be implemented later.

        Returns:
            List[str]: A list of show URLs.
        """
        if source == "sitemap":
            sitemap_urls = self.find_sitemaps()
            all_show_urls = []
            for sitemap in sitemap_urls:
                urls = self.read_sitemap(sitemap)
                urls = [
                    url for url in urls if
                    MUSIC_SITEMAP_RE.search(url) or MUSIC_SHOW_RE.search(url)]
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
            List[str]: A list of sitemap file paths or URLs.
        """
        # Use our utility to get the file (local or remote).
        robots_bytes = utils.get_file(self.source_url + ROBOTS_FILE)
        if robots_bytes is None:
            raise FileNotFoundError(
                "robots.txt not found at ./tests/data/robots.txt")
        robots_txt = robots_bytes.decode("utf-8")
        rp = urobot.RobotFileParser()
        rp.parse(robots_txt.splitlines())
        sitemap_urls = rp.site_maps() or []
        print(self.sitemap_files)
        for sitemap in self.sitemap_files:
            sitemap_urls.append(self.source_url + sitemap)
        print(sitemap_urls)
        # Filter to only include those that match our regex.
        sitemap_urls = [url for url in sitemap_urls if SITEMAP_RE.search(url)]
        sitemap_urls = [url.replace(
            "https://www.kcrw.com/", self.source_url) for url in sitemap_urls]
        sitemap_urls = list(set(sitemap_urls))
        print("Sitemap URLs:")
        pprint.pprint(sitemap_urls)
        return sitemap_urls

    def read_sitemap(self, sitemap: str) -> List[str]:
        """Reads a sitemap XML file (from a local file for development) and extracts
        all URLs from both <sitemap> and <url> tags by recursively collecting
        all <loc> element values using xmltodict.

        Parameters:
            sitemap (str): The path (or URL in production) to the sitemap XML.

        Returns:
            List[str]: A list of URLs extracted from the sitemap.
        """
        sitemap_bytes = utils.get_file(sitemap)
        if sitemap_bytes is None:
            return []
        # Decode the bytes (assuming UTF-8) and parse using xmltodict.
        sitemap_text = sitemap_bytes.decode("utf-8")
        parsed = xmltodict.parse(sitemap_text)
        # Recursively extract all 'loc' values.
        return self._extract_locs(parsed)

    def _extract_locs(self, data) -> List[str]:
        """Recursively traverse a dictionary (or list) parsed by xmltodict and collect
        all values associated with the key 'loc' (case-insensitive).

        Parameters:
            data: A dictionary or list resulting from xmltodict.parse().

        Returns:
            List[str]: A list of URL strings.
        """
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
        """
        Placeholder function for gathering shows from previously generated
        RSS/Atom feed files.

        Parameters:
            feed_path (str): The path to the directory or file containing the feeds.

        Returns:
            List[str]: A list of show URLs (not implemented yet).
        """
        # To be implemented later.
        return []
