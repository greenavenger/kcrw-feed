"""Module to handle updates to the local station catalog."""

import logging
import pprint
from typing import Optional

from kcrw_feed.models import FilterOptions
from kcrw_feed.processing.station import StationProcessor
from kcrw_feed.station_catalog import BaseStationCatalog

logger = logging.getLogger("kcrw_feed")


class CatalogUpdater:
    """Class that implements the station catalog updater."""

    def __init__(self, local_catalog: BaseStationCatalog, live_catalog: BaseStationCatalog, filter_opts: Optional[FilterOptions] = None) -> None:
        self.local_catalog = local_catalog
        self.live_catalog = live_catalog
        self.filter_opts = filter_opts

        # Convenience bool
        self.dry_run = False
        if filter_opts:
            self.dry_run = filter_opts.dry_run

    def update(self):
        """Update the repository with enriched objects."""
        resources_to_update = self.live_catalog.list_resources(
            self.filter_opts)
        live_station_processor = StationProcessor(self.live_catalog)
        logger.info("Updating entities")
        updated_items = []
        for resource in resources_to_update:
            enriched = live_station_processor.process_resource(resource)
            if enriched:
                # Update local catalog directly for now.
                if live_station_processor.is_episode_resource(enriched):
                    self.local_catalog.add_episode(enriched)
                else:
                    self.local_catalog.add_show(enriched)
                updated_items.append(enriched)
        # pprint.pprint(updated_items)
        if not self.dry_run:
            logger.info("Saving entities")
            self.local_catalog.save_state()
            logger.info("Writing feeds")
            self.local_catalog.generate_feeds()
        return len(updated_items)
