from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from scraper import DispatchEntrySet


class BaseStorage(ABC):
    @abstractmethod
    def get_latest_date_with_dispatch_ids(self) -> tuple[Optional[date], list[int]]:
        ...

    @abstractmethod
    def store_entries(self, entry_set: DispatchEntrySet):
        ...
