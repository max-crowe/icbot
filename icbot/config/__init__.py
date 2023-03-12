import re
from contextlib import contextmanager
from copy import deepcopy
from functools import cached_property
from importlib import import_module
from logging import getLogger, StreamHandler
from logging.config import dictConfig
from pathlib import Path
from typing import Any, Union
from zoneinfo import ZoneInfo

from storage.base import BaseStorage, get_concrete_storage


class ConfigurationError(ValueError):
    pass

class Settings:
    def __init__(self, module_path: str):
        self._setup(module_path)

    def _apply(self, setting: str, setting_value: Any):
        if isinstance(setting_value, (dict, list)):
            setting_value = deepcopy(setting_value)
        try:
            validate_method = getattr(self, 'validate_{}'.format(setting.lower()))
        except AttributeError:
            pass
        else:
            setting_value = validate_method(setting_value)
        setattr(self, setting, setting_value)

    def _set_from_module(self, module_path: str):
        module = import_module(module_path)
        for setting in filter(lambda s: s.isupper(), dir(module)):
            if not hasattr(self, setting):
                self._apply(setting, getattr(module, setting))

    def _set_from_dict(self, settings_dict: dict[str, Any]):
        for setting, setting_value in filter(lambda pair: pair[0].isupper(), settings_dict.items()):
            self._apply(setting, setting_value)

    def _setup(self, module_path: str):
        self._set_from_module(module_path)
        self._set_from_module("icbot.config.defaults")
        dictConfig(self.LOGGING)

    def validate_blocking_filters(self, setting_value: dict[str, Any]) -> dict[str, Any]:
        for block_type, blocks in setting_value.items():
            for i, block in enumerate(blocks):
                if isinstance(blocks[i], re.Pattern):
                    continue
                try:
                    blocks[i] = re.compile(block, re.I)
                except re.error as e:
                    raise ConfigurationError(
                        f"Error parsing regular expression '{block}'"
                    ) from e
        return setting_value

    def validate_data_dir(self, setting_value: Union[str, Path]) -> Path:
        if not isinstance(setting_value, Path):
            setting_value = Path(setting_value)
        if not setting_value.is_dir():
            raise ConfigurationError(
                "The DATA_DIR setting must be a path to a directory"
            )
        return setting_value

    def validate_storage(self, setting_value: Any) -> dict[str, Any]:
        if not setting_value:
            raise ConfigurationError("The STORAGE setting is required")
        try:
            class_name = setting_value["class"]
            init_kwargs = setting_value["init_kwargs"]
        except (KeyError, TypeError):
            raise ConfigurationError(
                "The STORAGE setting must be a dict containing the keys 'class_name' "
                "and 'init_kwargs'"
            )
        return setting_value

    @contextmanager
    def override(self, overrides: dict[str, Any]):
        prev = {k: v for k, v in self.__dict__.items() if k.isupper()}
        try:
            self._set_from_dict(overrides)
            yield
        finally:
            self._set_from_dict(prev)

    def get_storage(self, interactive=True) -> "BaseStorage":
        return get_concrete_storage(
            interactive, self.STORAGE["class"], **self.STORAGE["init_kwargs"]
        )

    @staticmethod
    def disable_logging_stream_handler():
        logger = getLogger('')
        for handler in filter(
            lambda handler: isinstance(handler, StreamHandler),
            logger.handlers
        ):
            logger.removeHandler(handler)

    @cached_property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.TIME_ZONE)


settings = Settings("icbot.settings")
