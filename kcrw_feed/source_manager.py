"""Module for managing the source of show URLs."""

from abc import ABC, abstractmethod
from datetime import timedelta
import logging
import gzip
import os
import re
from urllib.parse import urljoin, urlparse, urlunparse
import random
import requests_cache
import time
from typing import Dict, Optional
import fsspec


from kcrw_feed.persistent_logger import TRACE_LEVEL_NUM

# Regex pattern to match the prefix of KCRW URLs (or a test URL)
REWRITE_RE = re.compile(r'^(https://www\.kcrw\.com/|http://localhost:8888/)')
# REWRITE_RE = re.compile(r'^https://www\.kcrw\.com/')
REWRITE_RE = re.compile(r'^(https://www\.kcrw\.com/|http://localhost:8888/)')
# REWRITE_RE = re.compile(r'^(https?://)(?:www\.)?[\w.-]+(?::\d+)?/$')
# REPLACE_TEXT = ""  # ./tests/data/"

REQUEST_DELAY_MEAN: float = 5
REQUEST_DELAY_STDDEV: float = 2
REQUEST_HEADERS: Dict[str, str] = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/133.0.0.0 Safari/537.36")
}
REQUEST_TIMEOUT: int = 10

logger = logging.getLogger("kcrw_feed")


def random_delay(mean: float = REQUEST_DELAY_MEAN, stddev: float = REQUEST_DELAY_STDDEV) -> None:
    delay = random.gauss(mean, stddev)
    delay = max(0, delay)
    logger.debug("Sleeping for %.2f seconds", delay)
    time.sleep(delay)


def normalize_location(base: str, loc: str) -> str:
    """Normalize a relative location by joining it with a base.

    If the base is an HTTP/HTTPS URL, uses urllib.parse.urljoin to combine the URL and loc properly.
    Otherwise, uses os.path.join and os.path.normpath for file paths.

    Parameters:
        base (str): The base URL or directory path.
        loc (str): The relative URL or filename.

    Returns:
        str: The normalized URL or file path."""
    if base.startswith("http://") or base.startswith("https://"):
        return urljoin(base, loc)
    else:
        rel = loc.lstrip(os.sep)
        return os.path.normpath(os.path.join(base, rel))


def strip_query_params(url: str) -> str:
    parsed = urlparse(url)
    stripped = parsed._replace(query="")
    return urlunparse(stripped)


class BaseSource(ABC):
    """Abstract base class for sources."""
    base_source: str
    uses_sitemap: bool
    _session = None

    @abstractmethod
    def get_resource(self, resource: str) -> Optional[bytes]:
        """Fetch the resource content as bytes."""
        pass

    @abstractmethod
    def relative_path(self, entity_reference: str) -> str:
        """Return the relative part of the entity path."""
        pass

    def validate_source_root(self, source_root: str) -> bool:
        """Validates that source_root is either a valid http/https URL or
            a local file path.
        Raises:
            ValueError: If source_root is not valid."""
        parsed = urlparse(source_root)
        if parsed.scheme in ("http", "https"):
            return True
        elif os.path.exists(source_root):
            return True
        else:
            # TODO: Should we catch this and error more nicely? It's nice
            # and noisy right now.
            raise ValueError(
                f"Invalid source_root: {source_root}. It must be a valid "
                "HTTP URL or a valid local file path."
            )
        return False

    # TODO: Should this be here or in show_processor?
    def is_show(self, resource: str) -> bool:
        """Parse the path to determine if the resource is a show."""
        # Parse the resource to determine its structure.
        parsed = urlparse(resource)
        # Remove leading slashes and split path into segments.
        path_parts = parsed.path.strip("/").split("/")
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("path_parts: %s", path_parts)
        # We're expecting a structure like: music/shows/<show>[/<episode>]
        music_idx = path_parts.index("music")
        shows_idx = path_parts.index("shows")
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("music_idx: %d, shows_idx: %d", music_idx, shows_idx)
        # TODO: add try/except once we're more confident with our parsing
        # try:
        #     music_idx = path_parts.index("music")
        #     shows_idx = path_parts.index("shows")
        #     logger.debug("music_idx: %d, shows_idx: %d", music_idx, shows_idx)
        # except ValueError:
        #     # If the URL doesn't match our expected structure, assume it's a Show.
        #     return self._fetch_show(resource)

        # Determine how many segments come after "shows" in the path
        after = path_parts[shows_idx + 1:]
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("after: %s", after)
        if len(after) == 0:
            # No show identifier found; fallback.
            assert False, f"No show identifier found! {resource}"
        elif len(after) == 1:
            # Found show
            return True
        # Did not find show
        return False

    def is_episode(self, resource: str) -> bool:
        """If it's not a show, assume it's an episode."""
        return not self.is_show(resource)

    def _get_file(self, path: str, timeout: int = REQUEST_TIMEOUT) -> Optional[bytes]:
        """Retrieve a file as bytes.

        If the path is an HTTP URL, it is fetched using the cached session;
        if it ends with '.gz', the content is decompressed.
        For non-HTTP paths, use fsspec."""
        logger.debug("Reading: %s", path)
        if "kcrw.com" in path:
            random_delay()

        # TODO: Don't actually hit kcrw.com for now!
        assert not path.startswith("https://www.kcrw.com/")

        if path.startswith("http://") or path.startswith("https://"):
            assert self._session, f"No requests_cache.CachedSession found!"
            headers = REQUEST_HEADERS
            try:
                response = self._session.get(
                    path, timeout=timeout, headers=headers)
                response.raise_for_status()
                content = response.content
                if path.endswith(".gz"):
                    content = gzip.decompress(content)
                return content
            except Exception as e:
                logger.debug("Error: Could not read data from %s: %s", path, e)
                return None
        else:
            try:
                with fsspec.open(path, "rb", timeout=timeout, compression="infer") as f:
                    data = f.read()
                return data
            except Exception as e:
                logger.debug("Error: Could not read data from %s: %s", path, e)
                return None


class HttpsSource(BaseSource):
    def __init__(self, url: str, rewrite_rule: Optional[str] = None):
        self.validate_source_root(url)
        self.base_source = url
        self.url = self.base_source  # convenience reference
        self.rewrite_rule = rewrite_rule
        self.uses_sitemap = True
        # Create a single cached session that will be reused for all HTTP requests.
        self._session = requests_cache.CachedSession(
            'kcrw_cache', backend='sqlite',
            # Use Cache-Control response headers for expiration, if available
            cache_control=True,
            # Otherwise expire responses after one day
            expire_after=timedelta(days=1),
            # Cache 400 responses as a solemn reminder of your failures
            allowable_codes=[200, 404],

        )

    def get_resource(self, url: str) -> Optional[bytes]:
        logger.debug(f"Fetching via HTTPS: {url}")

        # Rewrite URL if necessary
        relative_path = self.relative_path(url)
        full_normalized_url = normalize_location(
            self.base_source, relative_path)
        return self._get_file(full_normalized_url)

    def relative_path(self, entity_reference: str) -> str:
        """Regular expression to return the relative part of the entity
        path."""
        # Also trim trailing slash for consistency
        updated_path = REWRITE_RE.sub("/", entity_reference).rstrip("/")
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("relative_path input url: %s", entity_reference)
            logger.trace("relative_path output url: %s", updated_path)
        return updated_path


class CacheSource(BaseSource):
    def __init__(self, path: str):
        self.validate_source_root(path)
        self.base_source = path
        self.path = self.base_source  # convenience reference
        self.uses_sitemap = True

    def get_resource(self, resource: str) -> Optional[bytes]:
        # Read from the local cache directory.

        # Rewrite path if necessary
        relative_path = self.relative_path(resource)
        full_normalized_path = normalize_location(
            self.base_source, relative_path)
        return self._get_file(full_normalized_path)

    def relative_path(self, entity_reference: str) -> str:
        """Regular expression to return the relative part of the entity
        path."""
        # Also trim trailing slash for consistency
        return "./" + REWRITE_RE.sub("./", entity_reference).rstrip("/")


class RssFeedSource(BaseSource):
    def __init__(self, url_or_path: str):
        self.url_or_path = url_or_path
        self.uses_sitemap = False

    def get_resource(self, resource: str) -> Optional[bytes]:
        print(f"Fetching from RSS feed: {self.url_or_path}")
        return None


class AtomFeedSource(BaseSource):
    def __init__(self, url_or_path: str):
        self.url_or_path = url_or_path
        self.uses_sitemap = False

    def get_resource(self, resource: str) -> Optional[bytes]:
        print(f"Fetching from Atom feed: {self.url_or_path}")
        return None
