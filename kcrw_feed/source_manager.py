"""Module for managing the source of show URLs."""

import os
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Optional
import fsspec


def get_file(path: str, timeout: int = 10) -> Optional[bytes]:
    """Retrieve a file as bytes. If the location starts with 'https' it is fetched over
    HTTPS; otherwise it is opened from the local file system. Automatic decompression
    is applied if the file extension suggests compression.

    Parameters:
        path (str): A URL or local path for the sitemap.
        timeout (int): Timeout for HTTPS requests (if applicable).

    Returns:
        Optional[bytes]: The sitemap content, or None if an error occurs."""
    try:
        # fsspec.open() supports local files, HTTP, and more. Using
        # compression="infer" will automatically decompress if the file ends in .gz.
        with fsspec.open(path, "rb", timeout=timeout, compression="infer") as f:
            sitemap = f.read()
        return sitemap
    except Exception as e:
        print(f"Error: Could not read sitemap from {path}: {e}")
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
