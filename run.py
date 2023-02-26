#!/usr/bin/env python
import asyncio, logging

from icbot.config import settings
from scraper import fetch_dispatch_entries_for_date_range

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        latest_date, id_list = settings.storage.get_latest_date_with_dispatch_ids()
        entry_sets = asyncio.run(fetch_dispatch_entries_for_date_range(latest_date, skip_ids=id_list))
        for entry_set in entry_sets:
            settings.storage.store_entries(entry_set)
        settings.storage.prune()
    except:
        logging.exception("Caught error during icbot run")
