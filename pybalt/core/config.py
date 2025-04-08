import os
import configparser
import platform
from pathlib import Path


config_defaults = {
    "user_agent": "pybalt/tool",
    "debug": "False",
    "TIMEOUT": "30",
    "MAX_RETRIES": "5",
    "RETRY_DELAY": "1.0",
    "CALLBACK_RATE": "0.128",
    "INSTANCE_LIST_API": "https://instances.cobalt.best/api/instances.json",
}


def get_config_dir() -> Path:
    """Get the config directory based on the platform."""
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA")) / "pybalt"
    else:  # Linux, macOS, etc.
        return Path.home() / ".config" / "pybalt"


def get_config_file() -> Path:
    """Get the path to the config variables file."""
    return get_config_dir() / "config.ini"


def get_logs_dir() -> Path:
    """Get the logs directory inside the config directory."""
    ensure_config_dir()
    directory = get_config_dir() / "logs"
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def ensure_config_dir():
    """Ensure the config directory exists."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def read_config() -> configparser.ConfigParser:
    """Read the configuration variables from the file."""
    config = configparser.ConfigParser()
    config_file = get_config_file()

    if config_file.exists():
        config.read(config_file)
    return config


def write_config(config: configparser.ConfigParser):
    """Write the configuration variables to the file."""
    ensure_config_dir()
    config_file = get_config_file()

    with open(config_file, "w") as f:
        config.write(f)


def get_variable(key, default=None, section="DEFAULT") -> str:
    """Get a configuration variable."""
    config = read_config()
    try:
        return config.get(section, key)
    except (configparser.NoOptionError, configparser.NoSectionError):
        return default


def set_variable(key, value, section="DEFAULT") -> str:
    """Set a configuration variable."""
    config = read_config()
    if not config.has_section(section) and section != "DEFAULT":
        config.add_section(section)
    config[section][key] = str(value)
    write_config(config)
    return value


def get_float_value(key, default=None, section="DEFAULT") -> int:
    """Get a configuration variable as an integer."""
    value = get_variable(key, default, section)
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def set_defaults() -> None:
    """Checks if the config file exists and sets default values if it doesn't."""
    config_file = get_config_file()
    config = configparser.ConfigParser()
    config.read(config_file)
    for key, value in config_defaults.items():
        if not config.has_option("DEFAULT", key):
            config.set("DEFAULT", key, value)
    write_config(config)


set_defaults()
