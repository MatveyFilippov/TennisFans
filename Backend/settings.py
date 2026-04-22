from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any, Final, TypeVar, overload
from zoneinfo import ZoneInfo


class Settings(ABC):
    _T = TypeVar('_T')

    @overload
    @classmethod
    def ask_value(cls, prompt: str, required_type: None = None) -> str:
        ...

    @overload
    @classmethod
    def ask_value(cls, prompt: str, required_type: type[_T]) -> _T:
        ...

    @classmethod
    def ask_value(cls, prompt: str, required_type: type[_T] | None = str) -> Any:
        if required_type is None:
            required_type = str
        while True:
            try:
                return required_type(input(prompt))
            except ValueError:
                print(f" >>> Value should be '{required_type}'")

    @abstractmethod
    def _get_or_raise_key_error(self, var_name: str) -> Any:
        return NotImplemented

    @abstractmethod
    def set(self, var_name: str, value: _T) -> _T:
        return NotImplemented

    @overload
    def get(self, var_name: str, required_type: None = None, prompt_to_ask_value_if_not_exists: str = None) -> str:
        ...

    @overload
    def get(self, var_name: str, required_type: type[_T], prompt_to_ask_value_if_not_exists: str = None) -> _T:
        ...

    def get(self, var_name: str, required_type: type[_T] | None = str, prompt_to_ask_value_if_not_exists: str = None) -> Any:
        if required_type is None:
            required_type = str
        try:
            value = self._get_or_raise_key_error(var_name=var_name)
            return required_type(value)
        except (KeyError, TypeError):
            prompt = prompt_to_ask_value_if_not_exists or f"{var_name}: "
            value = self.ask_value(prompt=prompt, required_type=required_type)
            return self.set(var_name=var_name, value=value)

    @overload
    def get_optional(self, var_name: str, default_value: None = None, set_default_value_if_not_exists: bool = True) -> Any | None:
        ...

    @overload
    def get_optional(self, var_name: str, default_value: _T, set_default_value_if_not_exists: bool = True) -> _T:
        ...

    def get_optional(self, var_name: str, default_value: _T | None = None, set_default_value_if_not_exists: bool = True) -> Any:
        try:
            return self._get_or_raise_key_error(var_name=var_name)
        except KeyError:
            if default_value is not None and set_default_value_if_not_exists:
                default_value = self.set(var_name=var_name, value=default_value)
            return default_value


class SettingsJSON(Settings):
    def __init__(self, json_filepath: str):
        self.__SETTINGS_FILEPATH = json_filepath

    @property
    def filepath(self) -> str:
        return self.__SETTINGS_FILEPATH

    def __get_dict_from_json_file(self) -> dict[str, Any]:
        result = dict()
        try:
            with open(self.__SETTINGS_FILEPATH, "r", encoding="UTF-8") as jf:
                result = dict(json.load(jf))
        except FileNotFoundError:
            with open(self.__SETTINGS_FILEPATH, "w", encoding="UTF-8") as jf:
                json.dump(result, jf, ensure_ascii=False)
        return result

    def _get_or_raise_key_error(self, var_name: str) -> Any:
        json_file_dict = self.__get_dict_from_json_file()
        if var_name not in json_file_dict:
            raise KeyError(f"Var '{var_name}' not exists")
        return json_file_dict[var_name]

    def set(self, var_name: str, value: Settings._T) -> Settings._T:
        json_file_dict = self.__get_dict_from_json_file()
        json_file_dict[var_name] = value
        with open(self.__SETTINGS_FILEPATH, "w", encoding="UTF-8") as jf:
            json.dump(json_file_dict, jf, ensure_ascii=False)
        return value

    def is_exists(self, var_name: str) -> bool:
        json_file_dict = self.__get_dict_from_json_file()
        return var_name in json_file_dict


project_settings: Settings = SettingsJSON(json_filepath="BackendSettings.json")
PROJECT_VERSION: Final = project_settings.get_optional(var_name="version", default_value="-v0.2.0-SNAPSHOT")  # use '-vn.n.n' format, where 'n' - number
PROJECT_TIMEZONE: Final = ZoneInfo(project_settings.get_optional(var_name="timezone", default_value="UTC", set_default_value_if_not_exists=False))
APP_ROOT_PATH: Final = project_settings.get_optional(var_name="app.root_path", default_value="/api", set_default_value_if_not_exists=False)
APP_HOST: Final = project_settings.get_optional(var_name="app.host", default_value="127.0.0.1", set_default_value_if_not_exists=False)
APP_PORT: Final = int(project_settings.get_optional(var_name="app.port", default_value=8000, set_default_value_if_not_exists=False))
LINK_TO_DATABASE: Final = project_settings.get(var_name="database.link", prompt_to_ask_value_if_not_exists=(
    "Use:\n * SQLite: '"
    "sqlite:///{path_to_db_file}"
    "'\n * PostgreSQL: '"
    "postgresql+psycopg2://{user}:{password}@{ip}:{port}/{db_name}"
    "'\nWrite link to db: "
))
LOGGER_FILEPATH: Final = project_settings.get_optional(var_name="logger.filepath", default_value="TennisFansBackend.log", set_default_value_if_not_exists=False)
__logging_levels = logging.getLevelNamesMapping()
LOGGER_GLOBAL_LEVEL: Final = __logging_levels[project_settings.get_optional(var_name="logger.global.level", default_value=logging.getLevelName(logging.WARNING), set_default_value_if_not_exists=False).upper()]
LOGGER_PROJECT_LEVEL: Final = __logging_levels[project_settings.get_optional(var_name="logger.project.level", default_value=logging.getLevelName(logging.INFO), set_default_value_if_not_exists=False).upper()]
LOGGER_FORMAT: Final = project_settings.get_optional(var_name="logger.format", default_value="%(asctime)s %(levelname)s %(name)s %(message)s", set_default_value_if_not_exists=False)


logging.basicConfig(
    encoding="UTF-8",
    level=LOGGER_GLOBAL_LEVEL,
    format=LOGGER_FORMAT,
    handlers=[
        logging.FileHandler(LOGGER_FILEPATH),
        logging.StreamHandler(),
    ],
)
logging.Formatter.formatTime = (
    lambda self, record, datefmt=None: (
        datetime
        .fromtimestamp(record.created, tz=timezone.utc)
        .astimezone(PROJECT_TIMEZONE)
        .isoformat(timespec='milliseconds')
    )
)


class ProjectLoggerFactory:
    PROJECT_PACKAGE = "ru.tennisfans.backend"
    logging.getLogger(PROJECT_PACKAGE).setLevel(LOGGER_PROJECT_LEVEL)

    @classmethod
    def get_for(cls, module_name: str = None) -> logging.Logger:
        name = cls.PROJECT_PACKAGE
        if module_name:
            name += "." + re.sub(r"[^a-z.]", "", module_name.lower())
        name += PROJECT_VERSION
        return logging.getLogger(name)
