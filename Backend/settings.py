from datetime import datetime, timezone
import json
import logging
from typing import Final, Type
import re
from zoneinfo import ZoneInfo


class SettingsJSON:
    SETTINGS_FILEPATH = "BackendSettings.json"

    @classmethod
    def __get_dict_from_json_file(cls) -> dict:
        result = dict()
        try:
            with open(cls.SETTINGS_FILEPATH, "r", encoding="UTF-8") as jf:
                result = dict(json.load(jf))
        except FileNotFoundError:
            with open(cls.SETTINGS_FILEPATH, "w", encoding="UTF-8") as jf:
                json.dump(result, jf, ensure_ascii=False)
        return result

    @classmethod
    def get(cls, var_name: str, required_type: Type | None = str, prompt: str | None = None):
        json_file_dict = cls.__get_dict_from_json_file()
        try:
            return required_type(json_file_dict[var_name])
        except (KeyError, TypeError):
            if not prompt:
                prompt = f"{var_name}: "
            return cls.__ask_and_append(var_name=var_name, prompt=prompt, required_type=required_type)

    @classmethod
    def get_optional(cls, var_name: str, default=None, write_default=True):
        json_file_dict = cls.__get_dict_from_json_file()
        try:
            return json_file_dict[var_name]
        except (KeyError, TypeError):
            if default is not None and write_default:
                cls.__append_to_json_file(key=var_name, value=default)
            return default

    @classmethod
    def __ask_value(cls, prompt: str, required_type: Type | None = str):
        while True:
            try:
                return required_type(input(prompt))
            except ValueError:
                print(f" >>> Value should be '{required_type}'")

    @classmethod
    def __append_to_json_file(cls, key: str, value):
        json_file_dict = cls.__get_dict_from_json_file()
        json_file_dict[key] = value
        with open(cls.SETTINGS_FILEPATH, "w", encoding="UTF-8") as jf:
            json.dump(json_file_dict, jf, ensure_ascii=False)

    @classmethod
    def __ask_and_append(cls, var_name: str, prompt: str, required_type: Type | None = str):
        value = cls.__ask_value(prompt=prompt, required_type=required_type)
        cls.__append_to_json_file(key=var_name, value=value)
        return value


BACKEND_VERSION: Final = SettingsJSON.get_optional(var_name="VERSION", default="-v0.2.0-SNAPSHOT")  # use '-vn.n.n' format, where 'n' - number
BACKEND_TIMEZONE: Final = ZoneInfo(SettingsJSON.get_optional(var_name="TIMEZONE", default="UTC"))
APP_ROOT_PATH: Final = SettingsJSON.get_optional(var_name="APP_ROOT_PATH", default="/api", write_default=False)
APP_HOST: Final = SettingsJSON.get_optional(var_name="APP_HOST", default="127.0.0.1", write_default=False)
APP_PORT: Final = int(SettingsJSON.get_optional(var_name="APP_PORT", default=8000, write_default=False))
LINK_TO_DATABASE: Final = SettingsJSON.get(var_name="LINK_TO_DATABASE", prompt=(
    "Use:\n * SQLite: '"
    "sqlite:///{path_to_db_file}"
    "'\n * PostgreSQL: '"
    "postgresql+psycopg2://{user}:{password}@{ip}:{port}/{db_name}"
    "'\nWrite link to db: "
))


logging.basicConfig(
    level=logging.WARNING, encoding="UTF-8", format=f"%(asctime)s %(levelname)s %(name)s{BACKEND_VERSION} %(message)s",
    handlers=[
        logging.FileHandler(SettingsJSON.get_optional(var_name="LOG_FILEPATH", default="TennisFansBackend.log", write_default=True)),
        logging.StreamHandler(),
    ],
)
logging.Formatter.formatTime = (
    lambda self, record, datefmt=None: (
        datetime
        .fromtimestamp(record.created, tz=timezone.utc)
        .astimezone(BACKEND_TIMEZONE)
        .isoformat(timespec='milliseconds')
    )
)


class ProjectLoggerFactory:
    PROJECT_PACKAGE = "ru.tennisfans"
    logging.getLogger(PROJECT_PACKAGE).setLevel(logging.DEBUG)

    @classmethod
    def get_for(cls, module_name: str | None = "global") -> logging.Logger:
        return logging.getLogger(cls.PROJECT_PACKAGE + "." + re.sub(r"[^a-z.]", "", module_name.lower()))
