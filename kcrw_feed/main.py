"""Main entry point for the KCRW Feed Generator."""

import argparse
import logging.config
import logging.handlers
import pprint
from typing import Any, Dict

from kcrw_feed.config import CONFIG
from kcrw_feed.persistent_logger import TRACE_LEVEL_NUM  # also: JSONFormatter
from kcrw_feed import show_index

# Logging set up: Instantiate custom logger to use in code. Configure
# handlers/filters/formatters/etc. at the root level. Depend on
# default propagation to process the log messages centrally at the root
# logger (messages from our customer logger and from 3rd party libs).
logger = logging.getLogger("kcrw_feed")


def main():
    logging.config.dictConfig(config=CONFIG["logging"])
    logger.debug("CONFIG: %s", pprint.pformat(CONFIG))

    parser = argparse.ArgumentParser(description="KCRW Feed Generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gather_parser = subparsers.add_parser("gather", help="Gather show URLs")
    gather_parser.add_argument(
        "--source", default="sitemap", choices=["sitemap", "feed"])

    update_parser = subparsers.add_parser("update", help="Update show data")
    update_parser.add_argument(
        "--source", default="sitemap", choices=["sitemap", "feed"])
    update_parser.add_argument(
        "--delay", type=float, default=5.0, help="Delay between requests")
    update_parser.add_argument(
        "--shows", nargs="*", help="List of show URLs to update")

    save_parser = subparsers.add_parser("save", help="Save the state to disk")

    args = parser.parse_args()
    logger.info("Command: %s", args.command, extra={"parsers": vars(args)})

    collection = show_index.ShowIndex(
        CONFIG["source_url"], extra_sitemaps=CONFIG["extra_sitemaps"])
    if args.command == "gather":
        urls = collection.process_sitemap(args.source or CONFIG["source"])
        if logger.isEnabledFor(TRACE_LEVEL_NUM):
            logger.trace("Gathered URLs: %s", pprint.pformat(urls))
        logger.info("Gathered %s URLs", len(urls))
    elif args.command == "update":
        updated_shows = collection.update(
            source=(args.source or CONFIG["source"]), selected_urls=args.shows)
        # Save the state or pass it to the next phase.
        logger.info("Updated %s", updated_shows)
    elif args.command == "save":
        # Call your state persistence functions.
        pass
    else:
        logger.error("Unknown command")


if __name__ == "__main__":
    main()
