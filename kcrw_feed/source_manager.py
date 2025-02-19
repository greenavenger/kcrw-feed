"""Module for managing the source of show URLs."""

from abc import ABC, abstractmethod
import logging
import os
import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Optional
import fsspec

# Regex pattern to match the prefix of KCRW URLs
REWRITE_RE = re.compile(r'^https://www\.kcrw\.com/')
REPLACE_TEXT = ""  # ./tests/data/"

logger = logging.getLogger("kcrw_feed")


class BaseSource(ABC):
    """Abstract base class for sources."""
    base_source: str
    uses_sitemap: bool

    @abstractmethod
    def get_resource(self, resource: str) -> Optional[bytes]:
        """Fetch the resource content as bytes."""
        pass

    def rewrite_base_source(self, entity_reference: str) -> str:
        """Regular expression to rewrite entity path"""
        return REWRITE_RE.sub(REPLACE_TEXT, entity_reference)


class HttpsSource(BaseSource):
    def __init__(self, url: str, rewrite_rule: Optional[str] = None):
        self.base_source = url
        self.url = self.base_source  # convenience reference
        self.rewrite_rule = rewrite_rule
        self.uses_sitemap = True

    def get_resource(self, url: str) -> Optional[bytes]:
        # Here you'd use requests and potentially rewrite the URL according to your rule.
        # For now, we'll leave a stub.
        print(f"Fetching via HTTPS: {url}")
        # Example: If rewrite_rule is provided, use it.
        # url = self._rewrite_url(url)
        # return requests.get(url, timeout=10).content
        return None


class CacheSource(BaseSource):
    def __init__(self, path: str):
        self.base_source = path
        self.path = self.base_source  # convenience reference
        self.uses_sitemap = True

    def get_resource(self, resource: str) -> Optional[bytes]:
        # Read from the local cache directory.
        full_normalized_path = normalize_location(self.path, resource)
        return get_file(full_normalized_path)


class RssFeedSource(BaseSource):
    def __init__(self, url_or_path: str):
        self.url_or_path = url_or_path
        self.uses_sitemap = False

    def get_resource(self, resource: str) -> Optional[bytes]:
        # For RSS feeds, you might parse a feed and then retrieve a resource.
        # Placeholder implementation:
        print(f"Fetching from RSS feed: {self.url_or_path}")
        return None


class AtomFeedSource(BaseSource):
    def __init__(self, url_or_path: str):
        self.url_or_path = url_or_path
        self.uses_sitemap = False

    def get_resource(self, resource: str) -> Optional[bytes]:
        # Similar to RssFeedSource.
        print(f"Fetching from Atom feed: {self.url_or_path}")
        return None


# class SourceManager:
#     def __init__(self, source: BaseSource):
#         self.source = source

#     def get_resource(self, resource: str) -> Optional[bytes]:
#         return self.source.get_resource(resource)


def get_file(path: str, timeout: int = 10) -> Optional[bytes]:
    """Retrieve a file as bytes. If the location starts with 'https' it is fetched over
    HTTPS; otherwise it is opened from the local file system. Automatic decompression
    is applied if the file extension suggests compression.

    Parameters:
        path (str): A URL or local path for the sitemap.
        timeout (int): Timeout for HTTPS requests (if applicable).

    Returns:
        Optional[bytes]: The sitemap content, or None if an error occurs."""
    logger.debug("Reading: %s", path)
    try:
        # fsspec.open() supports local files, HTTP, and more. Using
        # compression="infer" will automatically decompress if the file ends in .gz.
        with fsspec.open(path, "rb", timeout=timeout, compression="infer") as f:
            sitemap = f.read()
        return sitemap
    except Exception as e:
        print(f"Error: Could not read data from {path}: {e}")
        return None


def normalize_location(base: str, loc: str) -> str:
    """Normalize a relative location by joining it with a base.

    If the base is an HTTP/HTTPS URL, uses urllib.parse.urljoin
    to combine the URL and loc properly (handling extra slashes).
    Otherwise, uses os.path.join and os.path.normpath for file paths.

    Parameters:
        base (str): The base URL or directory path.
        loc (str): The relative URL or filename.

    Returns:
        str: The normalized URL or file path."""
    if base.startswith("http://") or base.startswith("https://"):
        return urljoin(base, loc)
    else:
        # Force loc to be treated as relative by stripping leading slashes.
        rel = loc.lstrip(os.sep)
        return os.path.normpath(os.path.join(base, rel))


def strip_query_params(url: str) -> str:
    parsed = urlparse(url)
    # Create a new ParseResult with an empty query
    stripped = parsed._replace(query="")
    return urlunparse(stripped)
