"""Main entry point for the KCRW Feed Generator."""

import argparse
import logging.config
import logging.handlers
import os.path
import pprint
import time
from typing import Any, Dict

from kcrw_feed.config import CONFIG
from kcrw_feed.persistence.logger import LOGGING_LEVEL_MAP
from kcrw_feed import show_index
from kcrw_feed.source_manager import BaseSource, HttpsSource, CacheSource


logger = logging.getLogger("kcrw_feed")


def main():
    t0 = time.time()
    parser = argparse.ArgumentParser(description="KCRW Feed Generator")
    # Global options
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Increase verbosity of returned entities")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help='Do not perform any destructive actions. (ex. "update -n" provides a diff)')
    parser.add_argument("-m", "--match", type=str,
                        help='A regex or substring to filter resource URLs (ex. "valida", "shows/valida", "valida.*-2023")')
    parser.add_argument("-s", "--since", type=str,
                        help='Reprocess since provided ISO 8601 timestamp (“YYYY-MM-DDTHH:MM:SS”)')
    parser.add_argument("-u", "--until", type=str,
                        help='Reprocess until provided ISO 8601 timestamp (“YYYY-MM-DDTHH:MM:SS”)')
    parser.add_argument("--loglevel", type=str,
                        choices=["trace", "debug", "info",
                                 "warning", "error", "critical"],
                        help="Override log level for stdout debug logging")
    parser.add_argument("-o", "--storage_root", type=str,
                        help="Specify the root data directory for state and feed files")
    parser.add_argument("-r", "--source_root", type=str,
                        help='Specify the source root (ex. "https://www.kcrw.com/", "./tests/data/")')
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True,
                                       help="Sub-commands: list, diff, update")

    list_parser = subparsers.add_parser(
        "list", help="List resources, shows, episodes, or hosts in feeds (local state)")
    list_parser.add_argument(
        "mode",
        nargs="?",
        choices=["resources", "shows", "episodes", "hosts"],  # "debug"],
        default="resources",
        help="Specify type of entity to list. Default lists resources."
    )

    diff_parser = subparsers.add_parser(
        "diff", help="Show differences between local state and live site (kcrw.com)")
    diff_parser.add_argument(
        "mode", nargs="?", choices=["resources", "shows", "episodes", "hosts"],
        default=None, help="Specify type of entity to diff. Default lists all."
    )

    subparsers.add_parser("update",
                          help="Update show data from live site (kcrw.com)")

    args = parser.parse_args()

    # If --loglevel is provided, update the stdout handler level. Leave the
    # file handler log level unchanged.
    if args.loglevel:
        stdout_override = LOGGING_LEVEL_MAP[args.loglevel.lower()]
        # Override stdout handler's level.
        CONFIG["logging"]["handlers"]["stdout"]["level"] = args.loglevel.upper()
        # The file file handler remains unchanged.
        file_level = LOGGING_LEVEL_MAP[CONFIG["logging"]
                                       ["handlers"]["file"]["level"].lower()]
        # The root logger level must be at the lowest (most detailed) of the two.
        new_root_numeric = min(stdout_override, file_level)
        new_root_str = logging.getLevelName(new_root_numeric)
        CONFIG["logging"]["loggers"]["root"]["level"] = new_root_str

    # Configure logging using the YAML-derived configuration.
    logging.config.dictConfig(CONFIG["logging"])
    logger.debug("CONFIG: %s", pprint.pformat(CONFIG))
    logger.debug("Log handler levels: %s", [(name, handler["level"])
                 for name, handler in CONFIG["logging"]["handlers"].items()])

    logger.info("Command: %s", args.command, extra={"parsers": vars(args)})

    source: BaseSource
    source_root = args.source_root or CONFIG["source_root"]
    if source_root.startswith("http"):
        source = HttpsSource(source_root)
    else:
        # Use an absolute path for the source_root so it's unambiguous.
        source_root = os.path.abspath(source_root)
        source = CacheSource(source_root)
    logger.info("Source root: %s", source_root)

    storage_root = args.storage_root or CONFIG["storage_root"]
    # Use an absolute path for the storage_root so it's unambiguous.
    storage_root = os.path.abspath(storage_root)
    logger.info("Data root: %s", storage_root)

    collection = show_index.ShowIndex(source=source, storage_root=storage_root)
    # Populate collection.shows
    collection.load()

    if args.command == "list":
        if args.mode == "resources":
            entities = collection.gather()
            if args.verbose:
                logger.info("Gathered entities: %s", pprint.pformat(entities))
            logger.info("Gathered resources: %s",
                        pprint.pformat(sorted(list(entities.keys()))))
            logger.info("Gathered %s entities", len(entities))
        elif args.mode == "shows":
            shows = collection.get_shows()
            shows = sorted(shows, key=lambda s: s.url)
            if args.verbose:
                print(pprint.pformat(shows))
            for show in shows:
                print(show.url)
        elif args.mode == "episodes":
            episodes = collection.get_episodes()
            # Sort by airdate for now
            episodes = sorted(episodes)  # , key=lambda s: s.url)
            if args.verbose:
                print(pprint.pformat(episodes))
            for ep in episodes:
                print(ep.url)
        elif args.mode == "hosts":
            raise NotImplementedError
        # elif args.mode == "debug":
        #     entities = collection.dump_all()
        #     if args.detail:
        #         pprint.pprint(entities)
        #     else:
        #         entities = sorted(list(entities.values()), key=lambda e: e.url)
        #         pprint.pprint(entities)
    elif args.command == "diff":
        raise NotImplementedError
    elif args.command == "update":
        updated_shows = collection.update(selection=args.match)
        logger.info("Updated %s", updated_shows)
    else:
        logger.error("Unknown command")

    logger.info("Elapsed time: %fs", time.time() - t0)


if __name__ == "__main__":
    main()
