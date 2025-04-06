"""Module to handle updates to the local station catalog."""

import copy
import logging
import pprint
from typing import List, Optional, Union

from kcrw_feed.models import Show, Episode, FilterOptions
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

    def update(self) -> List[Union[Show, Episode]]:
        """Update the repository with enriched objects."""
        resources_to_enrich = self.live_catalog.list_resources(
            self.filter_opts)
        live_station_processor = StationProcessor(self.live_catalog)

        logger.info("Enriching resources")
        enriched_entities: Set[Union[Show, Episode]] = set()
        logger.info("Resources to process: %d", len(resources_to_enrich))
        for resource in resources_to_enrich:
            enriched = live_station_processor.process_resource(resource)
            if enriched:
                enriched_entities.add(enriched)

        logger.info("Associating parents")
        for enriched in enriched_entities:
            associated = live_station_processor.associate_entity(enriched)
            if associated:
                enriched_entities.update(associated)
        # Refresh shows to pick up new Episodes, if added
        for entity in copy.copy(enriched_entities):
            if isinstance(entity, Show):
                show_id = entity.uuid
                # print(show_id)
                enriched_entities.remove(entity)
                enriched_entities.add(self.live_catalog.get_show(show_id))
        # pprint.pprint(enriched_entities)

        if not self.dry_run:
            logger.info("Updating entities")
            for enriched in enriched_entities:
                # Update local catalog directly for now.
                if live_station_processor.is_episode_resource(enriched):
                    self.local_catalog.add_episode(enriched)
                else:
                    self.local_catalog.add_show(enriched)
            logger.info("Saving state")
            self.local_catalog.save_state()
            logger.info("Writing feeds")
            self.local_catalog.generate_feeds()

        return list(enriched_entities)
