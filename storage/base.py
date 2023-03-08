from abc import ABC, abstractmethod
from datetime import date
from importlib import import_module
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from scraper import DispatchEntrySet


class BaseStorage(ABC):
    def __init__(self):
        self.interactive = None

    @abstractmethod
    def get_latest_date_with_dispatch_ids(self) -> tuple[Optional[date], list[int]]:
        ...

    @abstractmethod
    def store_entries(self, entry_set: "DispatchEntrySet"):
        ...


def get_concrete_storage(interactive, class_path, **init_kwargs) -> BaseStorage:
    module_path, _, class_name = class_path.partition(".")
    storage = getattr(import_module(module_path), class_name)(**init_kwargs)
    storage.interactive = interactive
    return storage
