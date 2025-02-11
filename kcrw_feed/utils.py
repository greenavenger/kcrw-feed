"""Utility functions"""

import fsspec
import os
import re
from typing import Optional
from urllib.parse import urljoin
import uuid


def extract_uuid(text: str) -> uuid.UUID | None:
    """Extracts and returns the first valid UUID found in the input text.
    The function accepts UUIDs in either the canonical dashed form
    (8-4-4-4-12) or as a 32-character hexadecimal string.

    Parameters:
        text (str): The input string that may contain a UUID.

    Returns:
        uuid.UUID: A UUID object if a valid UUID is found; otherwise, None."""
    # This regex matches either a 32-character hex string or a standard UUID with dashes.
    pattern = re.compile(
        r'([0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})'
    )
    match = pattern.search(text)
    if match:
        candidate = match.group(1)
        try:
            # If candidate is a valid UUID, return it as a uuid.UUID object.
            valid_uuid = uuid.UUID(candidate)
            return valid_uuid
        except ValueError:
            return None
    return None


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
