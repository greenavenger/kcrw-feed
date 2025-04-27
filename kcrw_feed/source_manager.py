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


from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM

# Regex pattern to match the prefix of KCRW URLs (or a test URL)
REWRITE_RE = re.compile(r'^(https://www\.kcrw\.com/|http://localhost:8888/)')
# REWRITE_RE = re.compile(r'^https://www\.kcrw\.com/')
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
    _session = None

    @abstractmethod
    def get_reference(self, resource: str) -> Optional[bytes]:
        """Fetch the resource content as bytes."""
        pass

    @abstractmethod
    def relative_path(self, entity_reference: str) -> str:
        """Return the relative part of the entity path."""
        pass

    @abstractmethod
    def reference(self, entity_reference: str) -> str:
        """Return the fully qualified entity path used for access."""
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

    def _get_file(self, path: str, timeout: int = REQUEST_TIMEOUT) -> Optional[bytes]:
        """Retrieve a file as bytes.

        If the path is an HTTP URL, it is fetched using the cached session;
        if it ends with '.gz', the content is decompressed.
        For non-HTTP paths, use fsspec."""
        logger.debug("Reading: %s", path)
        if path.startswith("http://") or path.startswith("https://"):
            # Disable requests to kcrw.com for now:
            # assert not path.startswith(
            #     "https://www.kcrw.com"), "Avoid generating load"
            # Ensure a cached session exists.
            assert self._session, f"No CachedSession available!"
            headers = REQUEST_HEADERS
            try:
                if self._session.cache.contains(url=path):
                    logger.debug("Cache hit for %s", path)
                    self.cache_stats["hits"] += 1
                    cached = True
                else:
                    logger.debug("Cache miss for %s", path)
                    self.cache_stats["misses"] += 1
                    cached = False
                    # To keep load on kcrw.com reasonable, if the response was
                    # not served from cache, add a delay.
                    if path.startswith("https://www.kcrw.com"):
                        random_delay()
                # Perform the GET request.
                response = self._session.get(
                    path, timeout=timeout, headers=headers)
                # Only raise for status codes other than 404
                if response.status_code != 404:
                    response.raise_for_status()
                # Log response details for debugging
                logger.debug("Response status: %d, from_cache: %s, url: %s",
                             response.status_code,
                             getattr(response, "from_cache", False),
                             path)
                if response.status_code == 404:
                    return None
                assert cached == response.from_cache, \
                    f"Cache hit mismatch for {path}: {cached} != {response.from_cache}"
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
        # Store the original URL as the base source
        self.base_source = url
        self.url = self.base_source  # convenience reference
        # Create a single cached session that will be reused for all HTTP requests.
        self.backend = 'sqlite'        # stores data in kcrw_cache.sqlite
        # self.backend = 'filesystem'  # stores data in "./kcrw_cache"
        self._session = requests_cache.CachedSession(
            'kcrw_cache',  backend=self.backend,
            # Use Cache-Control response headers for expiration, if available
            cache_control=True,
            # Otherwise expire responses after one day
            expire_after=timedelta(days=1),
            # Cache 404 responses as a solemn reminder of our failures
            allowable_codes=[200, 404],
            stale_if_error=True,
        )
        logger.info("Cache backend: %s", self.backend)
        # Cache stats
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
        }

    def get_reference(self, url: str) -> Optional[bytes]:
        logger.debug(f"Fetching HTTP/S: {url}")

        # Rewrite URL if necessary
        full_normalized_url = self.reference(url)
        return self._get_file(full_normalized_url)

    def relative_path(self, url: str) -> str:
        """Regular expression to return the relative part of the entity
        path."""
        # Use REWRITE_RE to extract the path portion
        return REWRITE_RE.sub("/", url)

    def reference(self, url: str) -> str:
        relative_path = self.relative_path(url)
        # For HTTP URLs, use urljoin to properly handle the base URL
        if self.base_source.startswith(("http://", "https://")):
            return urljoin(self.base_source, relative_path)
        return normalize_location(self.base_source, relative_path)


class CacheSource(BaseSource):
    def __init__(self, path: str):
        self.validate_source_root(path)
        self.base_source = path
        self.path = self.base_source  # convenience reference
        self.uses_sitemap = True

    def get_reference(self, resource: str) -> Optional[bytes]:
        # Read from the local cache directory.
        logger.debug(f"Fetching file: {resource}")

        # Rewrite path if necessary
        full_normalized_path = self.reference(resource)
        return self._get_file(full_normalized_path)

    def relative_path(self, path: str) -> str:
        """Regular expression to return the relative part of the entity
        path."""
        return "./" + os.path.normpath(REWRITE_RE.sub("./", path))

    def reference(self, resource: str) -> str:
        relative_path = self.relative_path(resource)
        full_normalized_path = normalize_location(
            self.base_source, relative_path)
        return full_normalized_path


class RssFeedSource(BaseSource):
    def __init__(self, url_or_path: str):
        self.url_or_path = url_or_path
        self.uses_sitemap = False

    def get_reference(self, resource: str) -> Optional[bytes]:
        print(f"Fetching from RSS feed: {self.url_or_path}")
        return None


class AtomFeedSource(BaseSource):
    def __init__(self, url_or_path: str):
        self.url_or_path = url_or_path
        self.uses_sitemap = False

    def get_reference(self, resource: str) -> Optional[bytes]:
        print(f"Fetching from Atom feed: {self.url_or_path}")
        return None
