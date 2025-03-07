"""Main entry point for the KCRW Feed Generator."""

import argparse
import logging.config
import logging.handlers
import os.path
import pprint
import time
from typing import Any, Dict

from kcrw_feed.config import CONFIG
from kcrw_feed.persistent_logger import LOGGING_LEVEL_MAP
from kcrw_feed import show_index
from kcrw_feed.source_manager import BaseSource, HttpsSource, CacheSource

# Logging set up: Instantiate custom logger to use in code. Configure
# handlers/filters/formatters/etc. at the root level. Depend on
# default propagation to process the log messages centrally at the root
# logger (messages from our customer logger and from 3rd party libs).
logger = logging.getLogger("kcrw_feed")


def main():
    t0 = time.time()
    parser = argparse.ArgumentParser(description="KCRW Feed Generator")
    parser.add_argument(
        "--loglevel",
        type=str,
        choices=["trace", "debug", "info", "warning", "error", "critical"],
        help="Override log level for stdout logging",
    )
    parser.add_argument("-d",
                        "--data_root",
                        type=str,
                        help="Specify the root data directory for state and feed files",
                        )
    parser.add_argument("-r",
                        "--source_root",
                        type=str,
                        help='Specify the source root (e.g. "https://www.kcrw.com/", "http://localhost:8888/", "./tests/data/")',
                        )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List shows or episodes")
    list_parser.add_argument(
        "mode",
        nargs="?",
        choices=["shows", "episodes", "debug"],
        default="shows",
        help="If specified as 'episodes', list episodes instead of shows. Default lists shows."
    )
    list_parser.add_argument(
        "--shows",
        type=str,
        help="Comma-separated list of show names (or fragments) to filter by"
    )
    list_parser.add_argument(
        "--detail",
        action="store_true",
        help="Display detailed output of each Show/Episode object"
    )

    gather_parser = subparsers.add_parser("gather", help="Gather show URLs")
    gather_parser.add_argument(
        "--source", default="sitemap", choices=["sitemap", "feed"]
    )
    gather_parser.add_argument(
        "--detail", action="store_true",
        help="Print the entire gathered entities dictionary"
    )

    update_parser = subparsers.add_parser("update", help="Update show data")
    update_parser.add_argument(
        "--source", default="sitemap", choices=["sitemap", "feed"]
    )
    update_parser.add_argument(
        "--delay", type=float, default=5.0, help="Delay between requests"
    )
    update_parser.add_argument(
        "--shows", nargs="*", help="List of show URLs to update"
    )

    save_parser = subparsers.add_parser("save", help="Save the state to disk")

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

    data_root = args.data_root or CONFIG["data_root"]
    # Use an absolute path for the data_root so it's unambiguous.
    data_root = os.path.abspath(data_root)
    logger.info("Data root: %s", data_root)

    collection = show_index.ShowIndex(source=source)

    if args.command == "list":
        # Populate collection.shows
        # _ = collection.update()
        collection.load(data_root=data_root)
        # Determine whether we're listing shows (default) or episodes.
        if args.mode == "debug":
            entities = collection.dump_all()
            if args.detail:
                pprint.pprint(entities)
            else:
                entities = sorted(list(entities.values()), key=lambda e: e.url)
                pprint.pprint(entities)
        elif args.mode == "episodes":
            # For episodes: by default list all episodes; if --shows is provided, filter to episodes
            # belonging to shows whose title matches one of the provided fragments.
            episodes = collection.get_episodes()
            episodes = sorted(episodes, key=lambda s: s.url)
            if args.shows:
                filters = [f.strip().lower() for f in args.shows.split(",")]
                # Filter shows first.
                filtered_shows = [show for show in collection.get_shows()
                                  if any(f in show.title.lower() for f in filters)]
                # Then collect episodes from these shows.
                episodes = []
                for show in filtered_shows:
                    episodes.extend(show.episodes)
            if args.detail:
                print(pprint.pformat(episodes))
            else:
                for ep in episodes:
                    print(ep.url)
        else:
            # Listing shows (default).
            shows = collection.get_shows()
            shows = sorted(shows, key=lambda s: s.url)
            if args.shows:
                filters = [f.strip().lower() for f in args.shows.split(",")]
                shows = [show for show in shows if any(
                    f in show.title.lower() for f in filters)]
            if args.detail:
                print(pprint.pformat(shows))
            else:
                for show in shows:
                    print(show.url)
    elif args.command == "gather":
        entities = collection.gather()
        if args.detail:
            logger.info("Gathered entities: %s", pprint.pformat(entities))
        logger.info("Gathered resources: %s",
                    pprint.pformat(sorted(list(entities.keys()))))
        logger.info("Gathered %s entities", len(entities))
    elif args.command == "update":
        updated_shows = collection.update(selection=args.shows)
        logger.info("Updated %s", updated_shows)
    elif args.command == "save":
        collection.save(data_root=data_root)
    else:
        logger.error("Unknown command")

    logger.info("Elapsed time: %fs", time.time() - t0)


if __name__ == "__main__":
    main()
