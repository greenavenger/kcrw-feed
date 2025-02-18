"""Utility functions"""

import fsspec
import os
import re
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse
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
