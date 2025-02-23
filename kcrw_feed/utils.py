"""Utility functions"""

from datetime import datetime
import logging
import re
from typing import Optional, Sequence
from urllib.parse import urljoin, urlparse, urlunparse
import uuid

from kcrw_feed.models import Episode, Host, Show

logger = logging.getLogger("kcrw_feed")


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


def uniq_by_uuid(entities: Sequence[Episode | Host | Show]) -> list[Episode | Host | Show]:
    """Deduplicate a list of entities based on UUID.

    Assumes that all items in the list are of the same type, and raises
    an AssertionError if a mixed list is provided."""
    if entities:
        first_type = type(entities[0])
        for e in entities:
            assert type(
                e) == first_type, "Mixed types provided to uniq_by_uuid"
    seen = {}
    deduped = []
    for e in entities:
        if e.uuid is None:
            deduped.append(e)
        elif e.uuid not in seen:
            seen[e.uuid] = True
            deduped.append(e)
    return deduped


def parse_date(date_str: str) -> Optional[datetime]:
    """Try to parse a date string into a datetime object."""
    if date_str:
        try:
            return datetime.fromisoformat(date_str)
        except ValueError as e:
            logger.error("Error parsing date '%s': %s", date_str, e)
            return None
    return None
