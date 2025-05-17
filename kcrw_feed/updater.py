"""Module to handle updates to the local station catalog."""

import copy
import logging
import pprint
from typing import List, Optional, Set, Union

from kcrw_feed.models import Resource, Show, Episode, FilterOptions, CatalogDiff
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

    def diff(self) -> CatalogDiff:
        """Return a diff object that compares the local catalog with the
        live catalog."""
        logger.info("Calculating differences")
        self.diff = self.local_catalog.diff(
            self.live_catalog, filter_opts=self.filter_opts)
        # diff = live_catalog.diff(local_catalog, filter_opts=filter_opts)
        # diff = local_catalog.diff(local_catalog, filter_opts=filter_opts)
        return self.diff

    def update(self) -> List[Union[Show, Episode]]:
        """Update the repository with enriched objects."""
        logger.info("Updating entities")
        resources_to_enrich = self.live_catalog.list_resources(
            self.filter_opts)
        logger.info("Resources to process: %d", len(resources_to_enrich))
        self.live_station_processor = StationProcessor(self.live_catalog)

        enriched_entities = self._enrich_resources(resources_to_enrich)

        diff = self.diff()
        if self.dry_run:
            pprint.pprint(diff)
            return list(enriched_entities)

        # Perform the mutations, write state and regenerate feeds.
        self._merge(enriched_entities)
        logger.info("Saving state")
        self.local_catalog.save_state()
        logger.info("Writing feeds")
        self.local_catalog.generate_feeds()

        return list(enriched_entities)

    def _merge(self, entities: Set[Union[Show, Episode]]) -> None:
        """Merge entities into local catalog."""
        # TODO: Should we accept a CatalogDiff and apply changes that way?
        # TODO: How do we detect errors here?
        logger.info("Merging entities")
        for enriched in entities:
            # Update local catalog directly for now.
            if self.live_station_processor.is_episode_resource(enriched):
                self.local_catalog.add_episode(enriched)
            else:
                self.local_catalog.add_show(enriched)

    def _enrich_resources(self, resources: List[Resource], checkpoint: int = 6) -> Set[Union[Show, Episode]]:
        """Accept resources and return a set of Show and/or Episode objects.
        Checkpoint by writing state after every n items are enriched."""
        logger.info("Enriching resources")
        enriched_entities: Set[Union[Show, Episode]] = set()
        count = 1
        for resource in resources:
            enriched = self.live_station_processor.process_resource(resource)
            if enriched:
                enriched_entities.add(enriched)
                count += 1
            if count == checkpoint:
                if not self.dry_run:
                    self.local_catalog.save_state()
                count = 1
        enriched_entities = self._associate_episodes(enriched_entities)
        return enriched_entities

    def _associate_episodes(self, entities: Set[Union[Show, Episode]]) -> Set[Union[Show, Episode]]:
        """Make sure that all Episodes are associated with a Show."""
        logger.info("Associating parents")
        associated_entities: Set[Union[Show, Episode]] = set()
        for entity in entities:
            associated = self.live_station_processor.associate_entity(entity)
            if associated:
                associated_entities.update(associated)
        # Refresh shows to pick up new Episodes, if added
        for entity in copy.copy(associated_entities):
            if isinstance(entity, Show):
                show_id = entity.uuid
                # print(show_id)
                associated_entities.remove(entity)
                associated_entities.add(self.live_catalog.get_show(show_id))
        return associated_entities
