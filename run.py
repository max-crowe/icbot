#!/usr/bin/env python
import asyncio, logging
from argparse import ArgumentParser
from datetime import date, timedelta

from icbot.config import settings
from scraper import fetch_dispatch_entries, fetch_dispatch_entries_for_date_range
from storage.base import BaseStorage

logger = logging.getLogger(__name__)

def fill_through_date(through_date: date, storage: BaseStorage):
    latest_date, id_list = storage.get_latest_date_with_dispatch_ids()
    if latest_date > through_date:
        return
    entry_sets = asyncio.run(fetch_dispatch_entries_for_date_range(
        latest_date,
        through_date,
        skip_ids=id_list
    ))
    for entry_set in entry_sets:
        storage.store_entries(entry_set)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--noninteractive", action="store_true")
    parser.add_argument("--through", choices=["yesterday", "today"], default="yesterday")
    args = parser.parse_args()
    if args.noninteractive:
        settings.disable_logging_stream_handler()
    try:
        storage = settings.get_storage(not args.noninteractive)
        current_date = settings.current_date
        if args.through == "yesterday":
            current_date -= timedelta(days=1)
        fill_through_date(current_date, storage)
        storage.prune()
    except:
        logging.exception("Caught error during icbot run")
