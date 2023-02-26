import asyncio, logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterator, Optional, Union

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from blotter import BlotterEntry
from icbot.config import settings

logger = logging.getLogger(__name__)


class BadResponse(RuntimeError):
    def __init__(self, request_method: str, url: str, status: int):
        self.request_method = request_method
        self.url = url
        self.status = status
        super().__init__(
            f"{request_method.upper()} request to {url} failed with response {status}"
        )


class BadResponses(RuntimeError):
    def __init__(self, errors: list[BadResponse]):
        self.errors = errors
        super().__init__(
            "Failed to retrieve responses from the following URL(s): {}".format(
                ", ".join(error.url for error in errors)
            )
        )


@dataclass
class DispatchEntrySet:
    date: date
    entries: list[BlotterEntry]


class Scraper:
    def __init__(self) -> None:
        self._session = None

    @asynccontextmanager
    async def session(self):
        prev = self._session
        try:
            if prev is None:
                self._session = ClientSession()
            yield self._session
        finally:
            if prev is None:
                await self._session.close()
                self._session = None

    async def fetch_one(
        self,
        session: ClientSession,
        url: str,
        method: str = "get",
        **data: Any
    ) -> str:
        logger.debug("Issuing %s request to %s...", method.upper(), url)
        async with getattr(session, method)(url, data=data) as response:
            logger.debug("Got %s status from %s", response.status, url)
            if response.status >= 400:
                raise BadResponse(method, url, response.status)
            return await response.text()

    async def fetch_many(self, session: ClientSession, *urls: str) -> list[Union[str, Exception]]:
        return await asyncio.gather(
            *(self.fetch_one(session, url) for url in urls),
            return_exceptions=True
        )


async def fetch_dispatch_entries(
    scraper: Scraper,
    for_date: date,
    skip_ids: Optional[list[int]] = None
) -> DispatchEntrySet:
    async with scraper.session() as session:
        blotter_page = BeautifulSoup(await scraper.fetch_one(
            session,
            settings.POLICE_LOG_URL,
            activityDate=for_date.strftime(settings.POLICE_LOG_DATETIME_FORMAT)
        ), "html.parser")
        entries = BlotterEntry.from_page(blotter_page)
        filtered_entries = list(filter(
            lambda entry: not entry.exclude and not (skip_ids and entry.dispatch_number in skip_ids),
            entries
        ))
        entry_count = len(entries)
        filtered_entry_count = len(filtered_entries)
        logger.debug(
            "Excluded %s entries out of %s from initial set",
            entry_count - filtered_entry_count,
            entry_count
        )
        detail_responses = await scraper.fetch_many(
            session, *(entry.url for entry in filtered_entries)
        )
        failure_count = 0
        for i, response in enumerate(detail_responses):
            if isinstance(response, BadResponse):
                filtered_entries[i].error = response
                failure_count += 1
            elif isinstance(response, Exception):
                raise response
            else:
                logger.debug("Parsing details from response #%s...", i + 1)
                detail_page = BeautifulSoup(response, "html.parser")
                filtered_entries[i].set_details_from_page(detail_page)
        if failure_count:
            logger.debug("Encountered %s failure(s)", failure_count)
        filtered_entries = list(filter(
            lambda entry: isinstance(entry, BlotterEntry) and not entry.exclude,
            filtered_entries
        ))
        logger.debug(
            "Excluded %s entries out of %s from initial filtered set",
            filtered_entry_count - len(filtered_entries),
            filtered_entry_count
        )
        return DispatchEntrySet(date=for_date, entries=filtered_entries)


async def fetch_dispatch_entries_for_date_range(
    from_date: date,
    through_date: Optional[date] = None,
    skip_ids: Optional[list[int]] = None
) -> list[DispatchEntrySet]:
    if through_date is None:
        through_date = date.today()
    scraper = Scraper()
    entry_sets: list[DispatchEntrySet] = []
    async with scraper.session() as session:
        while from_date <= through_date:
            entry_sets.append(await fetch_dispatch_entries(scraper, from_date, skip_ids))
            from_date += timedelta(days=1)
    return entry_sets
