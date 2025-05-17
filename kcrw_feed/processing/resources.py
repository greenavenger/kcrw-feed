"""Module to gather the urls of shows and episodes"""

import logging
import pprint
import re
from typing import Any, Dict, List, Set
import urllib.robotparser as urobot
import xmltodict

from kcrw_feed.models import Resource
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.source_manager import BaseSource
from kcrw_feed import utils

# Regular expression to match sitemap XML filenames.
SITEMAP_RE = re.compile(r"sitemap.*\.xml", re.IGNORECASE)
# Filter for URLs that pertain to music shows.
MUSIC_FILTER_RE = re.compile(
    r"(/sitemap-shows/music/|/music/shows/)", re.IGNORECASE)
ROBOTS_FILE = "robots.txt"

logger = logging.getLogger("kcrw_feed")


class ResourceProcessor:
    def __init__(self, source: BaseSource) -> None:
        """Parameters:
            source: The base URL (or local base path) for the site.
        """
        self.source = source
        # map: url -> Resource
        self._resources: Dict[str, Resource] = {}

    # Populate Methods
    def fetch_resources(self) -> Dict[str, Any]:
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
        return self._resources

    def _sitemaps_from_robots(self) -> List[str]:
        """Reads the robots.txt file and extracts root sitemap URLs.

        Returns:
            List[str]: The list of sitemap URLs found in robots.txt."""
        logger.info("reading robots file: %s", ROBOTS_FILE)
        robots_bytes = self.source.get_reference(ROBOTS_FILE)
        if not robots_bytes:
            raise FileNotFoundError(
                "robots.txt not found at " + self.source.base_source)
        robots_txt = robots_bytes.decode("utf-8")
        rp = urobot.RobotFileParser()
        rp.parse(robots_txt.splitlines())
        sitemap_urls = rp.site_maps() or []
        logger.debug("Sitemaps found in robots.txt: %s", sitemap_urls)
        # Rewrite base source if needed and filter for valid sitemap URLs.
        sitemap_urls = [
            self.source.relative_path(url)
            for url in sitemap_urls
            if SITEMAP_RE.search(url)
        ]
        if logger.isEnabledFor(getattr(logging, "TRACE", TRACE_LEVEL_NUM)):
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
        logger.info("reading sitemap: %s", sitemap)
        sitemap_bytes = self.source.get_reference(sitemap)
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
        if logger.isEnabledFor(getattr(logging, "TRACE", TRACE_LEVEL_NUM)):
            logger.trace("Found child_sitemaps: %s",
                         pprint.pformat(child_sitemaps))
        # Rewrite returned urls and filter for music.
        child_sitemaps = [
            self.source.relative_path(url)
            for url in child_sitemaps
            if MUSIC_FILTER_RE.search(url)
        ]
        logger.debug("Child sitemaps to read: %s", child_sitemaps)
        return child_sitemaps

    def _read_sitemap_for_entries(self, sitemap: str) -> None:
        """Reads a sitemap and extracts show references from <url>/<loc> tags,
        adding them to self._sitemap_entities."""
        sitemap_bytes = self.source.get_reference(sitemap)
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

        if logger.isEnabledFor(getattr(logging, "TRACE", TRACE_LEVEL_NUM)):
            logger.trace("Raw sitemap entries: %s", pprint.pformat(urls))

        for entry in urls:
            url = entry.get("loc").strip()
            # Keep only music shows
            if url and MUSIC_FILTER_RE.search(url):
                dt = None
                if entry.get("lastmod", None):
                    dt = utils.parse_date(entry["lastmod"])
                    entry["lastmod"] = dt
                resource = Resource(
                    url=url,
                    source=self.source.reference(url),
                    last_updated=dt,
                    metadata=entry
                )
                if logger.isEnabledFor(getattr(logging, "TRACE", TRACE_LEVEL_NUM)):
                    logger.trace(pprint.pformat(resource))
                self._resources[url] = resource
