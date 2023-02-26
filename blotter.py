from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from icbot.config import settings


class UnexpectedPageLayout(ValueError):
    pass


@dataclass
class BlotterEntry:
    dispatch_number: int
    url: str
    activity: str
    disposition: str
    has_details: bool
    details: Optional[str] = None
    error: Optional[RuntimeError] = None

    @classmethod
    def from_page(cls, page: BeautifulSoup) -> list["BlotterEntry"]:
        entries = []
        expected_headers = {
            "dispatch number",
            "address",
            "activity",
            "disposition",
            "details"
        }
        observed_headers = [None if tag.string is None else tag.string.lower() for tag in page.thead.find_all("th")]
        missing_headers = expected_headers & (expected_headers ^ set(observed_headers))
        if missing_headers:
            raise UnexpectedPageLayout(
                "Did not find following expected page header(s): {}".format(
                    ", ".join(missing_headers)
                )
            )
        header_indices = {h: i for i, h in enumerate(observed_headers)}
        for i, table_row in enumerate(page.tbody.find_all("tr")):
            cells = table_row.find_all("td")
            try:
                url = urljoin(
                    settings.POLICE_LOG_URL,
                    cells[header_indices["dispatch number"]].find("a")["href"]
                )
            except (TypeError, KeyError, IndexError):
                raise UnexpectedPageLayout(
                    f"Could not parse dispatch URL from row {i + 1}"
                )
            entries.append(cls(
                dispatch_number=int(cells[header_indices["dispatch number"]].string),
                url=url,
                activity=cells[header_indices["activity"]].string,
                disposition=cells[header_indices["disposition"]].string,
                has_details=cells[header_indices["details"]].string.strip().lower() == "y"
            ))
        return entries

    @property
    def exclude(self) -> bool:
        if not self.has_details:
            return True
        if self.has_details and self.details is not None:
            if self.details:
                # These have already been filtered by activity/disposition, no need
                # to do so again.
                return any(
                    pattern.search(self.details) for pattern in settings.BLOCKING_FILTERS["DETAILS"]
                )
            return False
        return any(
            pattern.search(self.activity or "") for pattern in settings.BLOCKING_FILTERS["ACTIVITIES"]
        ) or any(
            pattern.search(self.disposition or "") for pattern in settings.BLOCKING_FILTERS["DISPOSITIONS"]
        )

    def set_details_from_page(self, page: BeautifulSoup):
        found_details_label = False
        for element in filter(lambda node: isinstance(node, Tag), page.dl):
            if found_details_label and element.name == "dd":
                self.details = element.string.strip()
                break
            if element.name == "dt" and element.string.strip().lower() == "details":
                found_details_label = True
        if self.details is None:
            raise UnexpectedPageLayout("Could not find details on page")
