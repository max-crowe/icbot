#!/usr/bin/env python
import asyncio, logging
from argparse import ArgumentParser
from datetime import date

from icbot.config import settings
from scraper import fetch_dispatch_entries, fetch_dispatch_entries_for_date_range
from storage.base import BaseStorage

logger = logging.getLogger(__name__)

def fill_through_current_date(storage: BaseStorage):
    latest_date, id_list = storage.get_latest_date_with_dispatch_ids()
    entry_sets = asyncio.run(fetch_dispatch_entries_for_date_range(latest_date, skip_ids=id_list))
    for entry_set in entry_sets:
        storage.store_entries(entry_set)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--noninteractive", action="store_true")
    args = parser.parse_args()
    try:
        storage = settings.get_storage(not args.noninteractive)
        fill_through_current_date(storage)
        storage.prune()
    except:
        logging.exception("Caught error during icbot run")
