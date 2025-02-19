"""Module to gather the urls of shows and episodes"""

from datetime import datetime
import logging
import pprint
import re
from typing import Any, Dict, List, Set
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
        """Gather show references by recursively reading sitemaps.
        Returns:
            List[str]: A sorted list of show references.
        """
        logger.debug("Gathering sitemap entries from %s", self.source)
        # Start by reading robots.txt to get the initial sitemap URLs.
        root_sitemaps = self._sitemaps_from_robots()
        # Recursively collect all sitemap URLs.
        all_sitemaps = self._collect_sitemaps(root_sitemaps)
        logger.debug("All sitemaps collected: %s", all_sitemaps)
        # TODO: We're fetching and reading the sitemaps twice. We should cache
        # to avoid excessive load.
        logger.debug("Reading sitemaps for entries")
        # Process each sitemap to extract show entries.
        for sitemap in all_sitemaps:
            self._read_sitemap_for_entries(sitemap)
        # Return the sorted keys (show URLs or IDs)
        sitemap_entries = list(self._sitemap_entities.keys())
        return sorted(sitemap_entries)

    def _sitemaps_from_robots(self) -> List[str]:
        """Reads the robots.txt file and extracts root sitemap URLs.

        Returns:
            List[str]: The list of sitemap URLs found in robots.txt."""
        robots_bytes = self.source.get_resource(ROBOTS_FILE)
        if not robots_bytes:
            raise FileNotFoundError(f"robots.txt not found at {self.source}")
        robots_txt = robots_bytes.decode("utf-8")
        rp = urobot.RobotFileParser()
        rp.parse(robots_txt.splitlines())
        sitemap_urls = rp.site_maps() or []
        logger.debug("Sitemaps found in robots.txt: %s", sitemap_urls)
        # Rewrite base source if needed and filter for valid sitemap URLs.
        sitemap_urls = [
            self.source.rewrite_base_source(url)
            for url in sitemap_urls
            if SITEMAP_RE.search(url)
        ]
        if logger.isEnabledFor(getattr(logging, "TRACE", 5)):
            logger.trace("Stripped sitemaps from robots.txt: %s", sitemap_urls)
        return list(set(sitemap_urls))

    def _collect_sitemaps(self, sitemaps: List[str]) -> Set[str]:
        """Recursively collects sitemap URLs from sitemap index files.

        Parameters:
            sitemaps: Initial list of sitemap URLs.

        Returns:
            A set of all discovered sitemap URLs."""
        collected: Set[str] = set(sitemaps)
        for sitemap in sitemaps:
            child_sitemaps = self._read_sitemap_for_child_sitemaps(sitemap)
            for child in child_sitemaps:
                if child not in collected:
                    collected.add(child)
                    # Recursively collect from child sitemap
                    collected.update(self._collect_sitemaps([child]))
        return collected

    def _read_sitemap_for_child_sitemaps(self, sitemap: str) -> List[str]:
        """Reads a sitemap XML and returns any child sitemap URLs (if this is an index file).
        Returns:
            List[str]: Child sitemap URLs, or an empty list if none are found."""
        sitemap_bytes = self.source.get_resource(sitemap)
        if not sitemap_bytes:
            logger.warning("Sitemap %s could not be retrieved", sitemap)
            return []
        try:
            sitemap_str = sitemap_bytes.decode("utf-8")
            doc = xmltodict.parse(sitemap_str)
        except Exception as e:
            logger.warning("Sitemap %s could not be parsed: %s", sitemap, e)
            return []

        # Check if this is a sitemap index
        sitemap_index = doc.get("sitemapindex")
        if not sitemap_index:
            # Not a sitemap index, so no child sitemaps.
            return []

        # The "sitemap" key may be a single dict or a list
        sitemap_entries = sitemap_index.get("sitemap")
        if not sitemap_entries:
            return []

        if isinstance(sitemap_entries, dict):
            sitemap_entries = [sitemap_entries]

        child_sitemaps = []
        for entry in sitemap_entries:
            loc = entry.get("loc")
            if loc:
                child_sitemaps.append(loc.strip())
        if logger.isEnabledFor(getattr(logging, "TRACE", 5)):
            logger.trace("Found child_sitemaps: %s",
                         pprint.pformat(child_sitemaps))
        # Rewrite returned urls and filter for music.
        child_sitemaps = [
            self.source.rewrite_base_source(url)
            for url in child_sitemaps
            if MUSIC_FILTER_RE.search(url)
        ]
        logger.debug("Child sitemaps to read: %s", child_sitemaps)
        return child_sitemaps

    def _read_sitemap_for_entries(self, sitemap: str) -> None:
        """Reads a sitemap and extracts show references from <url>/<loc> tags,
        adding them to self._sitemap_entities."""
        sitemap_bytes = self.source.get_resource(sitemap)
        if not sitemap_bytes:
            logger.warning("Sitemap %s could not be retrieved", sitemap)
            return
        try:
            sitemap_str = sitemap_bytes.decode("utf-8")
            doc = xmltodict.parse(sitemap_str)
        except Exception as e:
            logger.warning("Sitemap %s could not be parsed: %s", sitemap, e)
            return

        # Check if this is a URL sitemap (typically under the "urlset" key)
        urlset = doc.get("urlset")
        if not urlset:
            # If not, it might be a sitemap index or unexpected format; nothing to do here.
            return

        urls = urlset.get("url")
        if not urls:
            return

        # Normalize a single URL entry to a list
        if isinstance(urls, dict):
            urls = [urls]

        if logger.isEnabledFor(getattr(logging, "TRACE", 5)):
            logger.trace("Raw sitemap entries: %s", pprint.pformat(urls))

        for entry in urls:
            loc = entry.get("loc")
            # Keep only music shows
            # TODO: Should the keys be absolute or relative URLs?
            if loc and MUSIC_FILTER_RE.search(loc):
                self._sitemap_entities[loc.strip()] = {}

    def parse_feeds(self, feed_path: str) -> List[str]:
        """Placeholder for gathering shows from RSS/Atom feeds.

        Parameters:
            feed_path (str): The directory or file containing feed data.

        Returns:
            List[str]: A list of show URLs."""
        logger.info("parse_feeds() is not yet implemented.")
        # Implementation to be added later.
        return []
