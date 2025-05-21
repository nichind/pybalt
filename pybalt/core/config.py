import os
import configparser
import platform
from pathlib import Path
import sys
import subprocess
from typing import Optional, Dict, Any, List, Union
from asyncio import get_event_loop, new_event_loop
from dotenv import load_dotenv

try:
    from prompt_toolkit import Application
    from prompt_toolkit.layout.containers import Window, HSplit
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.layout import Layout
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    print("Warning: prompt_toolkit is not installed. CLI config editing will not be available.")
    print("Install with: pip install prompt_toolkit")


class Config:
    """
    Configuration handler for pybalt.
    Manages settings in ~/.config/pybalt/settings.ini.
    """

    # DEFAULT configuration values organized by section
    VALUES = {
        "general": {
            "user_agent": "github.com/nichind/pybalt, tool/python-module, :)",
            "debug": "False",
        },
        "network": {
            "use_system_proxy": "True",
            "proxy": "",
            "timeout": "4",
            "download_timeout": "4",
            "max_retries": "2",
            "download_retries": "2",
            "retry_delay": "0.5",
            "callback_rate": "1.000",
            "max_concurrent_downloads": "2",
            "max_retries_tunnel": "10",
            "download_buffer_size": "1048576",  # equals to 1 Mb
            "bypass_proxy_for_localhost": "True",
            "progressive_timeout": "False",
        },
        "instances": {
            "instance_list_api": "https://instances.cobalt.best/api/instances.json",
            "fallback_instance": "https://dwnld.nichind.dev",   
            "fallback_instance_api_key": "b05007aa-bb63-4267-a66e-78f8e10bf9bf",
            "api_key": "",  # Api key to try to use on every instance
        },
        "user_instances": {
            # This section will store user-defined instances
            # Format: instance_1, instance_1_api_key, instance_2, instance_2_api_key, etc.
        },
        "paths": {
            "default_downloads_dir": str(Path.home() / "Downloads"),
        },
        "local": {
            "local_instance_port": "9000",
            "use_pc_proxy": "True",
            "network_mode": "host",
            "proxy_url": "",
        },
        "ffmpeg": {"remux_args": "-hwaccel opencl", "keep_original": "True"},
        "api": {"port": "8009", "update_period": "120"},
        "misc": {
            "last_update_check": "0",
            "update_check_interval": "86400",
            "update_check_enabled": "True",
            "allow_bulk_download": "True",
            "last_thank": "0",
        },
        "display": {
            "enable_tracker": "True",
            "show_path": "True",
            "enable_colors": "False",
            "max_filename_length": "32",
            "progress_bar_width": "20",
            "max_visible_items": "4",
            "draw_interval": "0.3",
            "min_redraw_interval": "0.1",
        },
    }

    # Settings that should be converted to numbers (int or float) when retrieved and changed in the config gui
    NUMBER_SETTINGS = {
        "timeout",
        "download_timeout",
        "max_retries",
        "download_retries",
        "retry_delay",
        "callback_rate",
        "local_instance_port",
        "max_concurrent_downloads",
        "download_buffer_size",
        "update_period",
        "max_filename_length",
        "progress_bar_width",
        "max_visible_items",
        "port",
        "last_update_check",
        "update_check_interval",
        "duration_limit",
        "draw_interval",
        "min_redraw_interval",
        "last_thank",
    }

    def __init__(self):
        # Create a mapping of unique keys to their sections
        self.key_to_section = {}
        self._build_key_section_map()

        self.config = configparser.ConfigParser()
        self.config_path = self._get_config_path()
        self._config_accessible = True  # Flag to track if config is accessible
        self.ensure_config_exists()
        self.load_config()

    def _build_key_section_map(self):
        """Build a map of keys to their sections, tracking any duplicate keys."""
        self.key_to_section = {}
        duplicate_keys = set()

        for section, options in self.VALUES.items():
            for key in options:
                if key in self.key_to_section:
                    duplicate_keys.add(key)
                else:
                    self.key_to_section[key] = section

        # Remove duplicates from the map so they won't be auto-resolved
        for key in duplicate_keys:
            if key in self.key_to_section:
                del self.key_to_section[key]

    def _get_config_dir(self) -> Path:
        """
        Get the platform-specific path to the configuration folder.

        Returns:
            Path to the configuration folder.
        """
        # Load environment variables from .env file if it exists
        load_dotenv()

        # Check for environment variable first
        # This allows for overriding the default config directory
        if os.getenv("PYBALT_CONFIG_DIR") is not None:
            config_folder_path = Path(os.getenv("PYBALT_CONFIG_DIR"))
            if config_folder_path.is_dir():
                return config_folder_path
            else:
                print(f"Warning: PYBALT_CONFIG_DIR points to a non-directory path: {config_folder_path}")

        # Determine the platform and set the base path accordingly
        system = platform.system()

        if system == "Windows":
            base_path = os.path.expandvars("%APPDATA%")
            config_dir = Path(base_path) / "pybalt"
        elif system == "Darwin":  # macOS
            config_dir = Path.home() / "Library" / "Application Support" / "pybalt"
        else:  # Linux and other Unix-like systems
            config_dir = Path.home() / ".config" / "pybalt"

        return config_dir

    def _get_config_path(self) -> Path:
        """
        Get the platform-specific path to the configuration file.

        Returns:
            Path to the configuration file.
        """
        # Check for environment variable first
        # This allows for overriding the default config file path
        if os.getenv("PYBALT_CONFIG_PATH") is not None:
            config_file_path = Path(os.getenv("PYBALT_CONFIG_PATH"))
            if config_file_path.is_file():
                return config_file_path
            else:
                print(f"Warning: PYBALT_CONFIG_PATH points to a non-file path: {config_file_path}")
        # If no environment variable is set, use the default path
        return self._get_config_dir() / "settings.ini"

    def ensure_config_exists(self) -> None:
        """Ensure the configuration file and directory exist."""
        config_dir = self.config_path.parent

        # Create directory if it doesn't exist
        try:
            if not config_dir.exists():
                os.makedirs(config_dir, exist_ok=True)

            # Create config file with default settings if it doesn't exist
            if not self.config_path.exists():
                # Create each section with its values
                for section, options in self.VALUES.items():
                    if section not in self.config:
                        self.config[section] = {}
                    self.config[section].update(options)

                self.save_config()
        except (PermissionError, OSError):
            # If we can't create the config file/directory due to permissions,
            # mark config as inaccessible but continue with defaults
            self._config_accessible = False
            print(f"Warning: Cannot create config directory or file at {self.config_path}. Using default values.")

    def load_config(self) -> None:
        """Load the configuration from the file."""
        try:
            if self.config_path.exists():
                self.config.read(self.config_path)
                self._config_accessible = True
        except (PermissionError, OSError):
            self._config_accessible = False
            print(f"Warning: Cannot read config file at {self.config_path}. Using default values.")

    def save_config(self) -> None:
        """Save the current configuration to the file."""
        if not self._config_accessible:
            print("Warning: Config file is not accessible. Changes will not be saved.")
            return

        try:
            with open(self.config_path, "w") as config_file:
                self.config.write(config_file)
        except (PermissionError, OSError):
            self._config_accessible = False
            print(f"Warning: Cannot write to config file at {self.config_path}. Changes will not be saved.")

    def _find_section_for_key(self, option: str) -> Optional[str]:
        """Find which section a key belongs to if it's unique across sections."""
        return self.key_to_section.get(option)

    def get(self, option: str, fallback: Any = None, section: Optional[str] = None) -> Union[str, float, int, bool]:
        """
        Get a configuration value, checking environment variables first.

        Args:
            option: The option name.
            fallback: Value to return if the option is not found.
            section: The configuration section. Can be None for unique keys.

        Returns:
            The option value as a string, int, float, or bool based on the setting type.
        """
        # If section is not provided, try to determine it for unique keys
        if section is None:
            section = self._find_section_for_key(option)
            if section is None:
                # If key isn't unique or doesn't exist, try misc as fallback
                section = "misc"

        # Check for environment variable override
        if section:
            env_var_name = f"PYBALT_{section.upper()}_{option.upper()}"
            env_value = os.getenv(env_var_name)
            if env_value is not None:
                # If environment variable exists, use its value
                value = env_value
                
                # Convert to number if the setting is in the NUMBER_SETTINGS list
                if option in self.NUMBER_SETTINGS:
                    try:
                        # Try to convert to int or float based on the presence of a decimal point
                        if "." in value or "," in value:
                            # Replace comma with dot for locales that use comma as decimal separator
                            numeric_value = float(value.replace(",", "."))
                        else:
                            # First try as int, if that fails try as float
                            try:
                                numeric_value = int(value)
                            except (ValueError, TypeError):
                                numeric_value = float(value)
                        return numeric_value
                    except (ValueError, TypeError):
                        print(f"Warning: Failed to convert {option} value '{value}' from environment variable to number. Using as string.")
                        return value

                # Convert string boolean values to actual boolean types
                if value.lower() in ("true", "false"):
                    return value.lower() == "true"

                return value

        value = None

        # If config is accessible, try to get the value from the file
        if self._config_accessible:
            # If no environment variable, try to get the value from the specified section
            if self.config.has_section(section) or section == "misc":
                value = self.config.get(section, option, fallback=None)

            # If value not found and we're not already in misc, try misc
            if value is None and section != "misc":
                value = self.config.get("misc", option, fallback=None)

        # If still no value, try to get the default value from VALUES
        if value is None:
            if section in self.VALUES and option in self.VALUES[section]:
                value = self.VALUES[section][option]
            # If no default in the specified section, check misc
            elif section != "misc" and "misc" in self.VALUES and option in self.VALUES["misc"]:
                value = self.VALUES["misc"][option]
            # Finally use the fallback
            else:
                value = fallback

        # Convert to number if the setting is in the NUMBER_SETTINGS list
        if option in self.NUMBER_SETTINGS and value is not None:
            try:
                # Try to convert to int or float based on the presence of a decimal point
                if isinstance(value, str) and ("." in value or "," in value):
                    # Replace comma with dot for locales that use comma as decimal separator
                    numeric_value = float(value.replace(",", "."))
                else:
                    # First try as int, if that fails try as float
                    try:
                        numeric_value = int(value)
                    except (ValueError, TypeError):
                        numeric_value = float(value)
                return numeric_value
            except (ValueError, TypeError):
                print(f"Warning: Failed to convert {option} value '{value}' to number. Using as string.")
                return value

        # Convert string boolean values to actual boolean types
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"

        return value

    def get_as_number(self, option: str, fallback: Any = None, section: Optional[str] = None) -> Union[int, float]:
        """
        Get a configuration value as a number (int or float).

        Args:
            option: The option name.
            fallback: Value to return if the option is not found or conversion fails.
            section: The configuration section. Can be None for unique keys.

        Returns:
            The option value as int or float.
        """
        value = self.get(option, fallback=None, section=section)
        try:
            # Try to convert to int first, if that fails try float
            try:
                if isinstance(value, str) and ("." in value or "," in value):
                    return float(value.replace(",", "."))
                return int(value)
            except (ValueError, TypeError):
                return float(value)
        except (ValueError, TypeError):
            # If conversion fails and this is a NUMBER_SETTING, try to get the default value
            if option in self.NUMBER_SETTINGS:
                # If section is not provided, try to determine it for unique keys
                if section is None:
                    section = self._find_section_for_key(option)
                
                # Try to get the default value from VALUES
                if section and section in self.VALUES and option in self.VALUES[section]:
                    default_str = self.VALUES[section][option]
                    try:
                        # Convert the default string value to a number
                        if "." in default_str:
                            default_value = float(default_str)
                        else:
                            default_value = int(default_str)
                        print(f"Warning: Failed to convert '{option}' value '{value}' to number. Using default: {default_value}")
                        return default_value
                    except (ValueError, TypeError):
                        print(f"Warning: Both user value '{value}' and default value '{default_str}' for '{option}' are invalid numbers.")
            
            if isinstance(fallback, (int, float)):
                print(f"Warning: Failed to convert '{option}' value '{value}' to number. Using fallback: {fallback}")
                return fallback
            print(f"Warning: Failed to convert '{option}' value '{value}' to number. Using 0.")
            return 0

    def set(self, option: str, value: str, section: Optional[str] = None) -> None:
        """
        Set a configuration value.

        Args:
            option: The option name.
            value: The value to set.
            section: The configuration section. Can be None for unique keys.
        """
        # If section is not provided, try to determine it for unique keys
        if section is None:
            section = self._find_section_for_key(option)
            if section is None:
                # If key isn't unique or doesn't exist, use misc
                section = "misc"

        if not self.config.has_section(section):
            self.config.add_section(section)

        self.config.set(section, option, value)
        self.save_config()

    def delete_option(self, option: str, section: Optional[str] = None) -> bool:
        """
        Delete an option from a section.

        Args:
            option: The option to delete.
            section: The configuration section. Can be None for unique keys.

        Returns:
            True if the option was removed, False otherwise.
        """
        # If section is not provided, try to determine it for unique keys
        if section is None:
            section = self._find_section_for_key(option)
            if section is None:
                # If key isn't unique, we can't determine which one to delete
                return False

        result = self.config.remove_option(section, option)
        if result:
            self.save_config()
        return result

    def reset_to_default(self, option: str, section: Optional[str] = None) -> bool:
        """
        Reset an option to its default value if it exists in VALUES.

        Args:
            option: The option to reset.
            section: The configuration section. Can be None for unique keys.

        Returns:
            True if the option was reset, False otherwise.
        """
        # If section is not provided, try to determine it for unique keys
        if section is None:
            section = self._find_section_for_key(option)
            if section is None:
                # If key isn't unique, we can't determine which one to reset
                return False

        # Check if the option exists in the default values for the section
        if section in self.VALUES and option in self.VALUES[section]:
            default_value = self.VALUES[section][option]
            self.set(option, default_value, section)
            return True
        return False

    def reset_all_to_defaults(self) -> None:
        """
        Reset all configuration values to defaults.
        """
        # Clear existing config and recreate with defaults
        for section in self.config.sections():
            self.config.remove_section(section)

        # Create each section with its values
        for section, options in self.VALUES.items():
            if section not in self.config:
                self.config.add_section(section)
            for option, value in options.items():
                self.config.set(section, option, value)

        self.save_config()

    def ensure_default_keys_exist(self) -> None:
        """
        Ensure all keys from VALUES exist in their respective sections.
        If any are missing, add them with their default values.
        """
        changed = False

        for section, options in self.VALUES.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                changed = True

            for option, value in options.items():
                if not self.config.has_option(section, option):
                    self.config.set(section, option, value)
                    changed = True

        if changed:
            self.save_config()

    def get_sections(self) -> List[str]:
        """
        Get all configuration sections.

        Returns:
            List of section names.
        """
        return self.config.sections()

    def get_options(self, section: str) -> List[str]:
        """
        Get all options in a section.

        Args:
            section: The section name.

        Returns:
            List of option names.
        """
        if self.config.has_section(section):
            return list(self.config[section].keys())
        return []

    def get_all_settings(self) -> Dict[str, Dict[str, str]]:
        """
        Get all configuration settings.

        Returns:
            Dictionary of all settings by section.
        """
        result = {}

        # Add all sections
        for section in self.config.sections():
            result[section] = dict(self.config[section])

        return result

    def get_user_instances(self) -> List[Dict[str, str]]:
        """
        Get all user-defined instances and their API keys.

        Returns:
            List of dictionaries containing instance URLs and API keys.
        """
        instances = []

        if not self.config.has_section("user_instances"):
            return instances

        options = self.config.options("user_instances")

        # Group options by instance number
        instance_nums = set()
        for option in options:
            if option.startswith("instance_") and "_api_key" not in option:
                try:
                    num = int(option.split("_")[1])
                    instance_nums.add(num)
                except (ValueError, IndexError):
                    pass

        # Collect instances with their API keys
        for num in sorted(instance_nums):
            instance_key = f"instance_{num}"
            api_key_key = f"instance_{num}_api_key"

            if instance_key in options:
                instance_url = self.config.get("user_instances", instance_key)
                api_key = self.config.get("user_instances", api_key_key, fallback="")

                if instance_url:
                    instances.append({"number": num, "url": instance_url, "api_key": api_key})

        return instances

    def add_user_instance(self, url: str, api_key: str = "") -> int:
        """
        Add a new user instance with an optional API key.

        Args:
            url: The instance URL.
            api_key: The API key for the instance (optional).

        Returns:
            The instance number assigned to the new instance.
        """
        if not self.config.has_section("user_instances"):
            self.config.add_section("user_instances")

        # Get existing instance numbers
        instances = self.get_user_instances()
        used_nums = {instance["number"] for instance in instances}

        # Find the next available number
        next_num = 1
        while next_num in used_nums:
            next_num += 1

        # Add the new instance
        self.config.set("user_instances", f"instance_{next_num}", url)
        if api_key:
            self.config.set("user_instances", f"instance_{next_num}_api_key", api_key)

        self.save_config()
        return next_num

    def update_user_instance(self, num: int, url: str = None, api_key: str = None) -> bool:
        """
        Update an existing user instance's URL or API key.

        Args:
            num: The instance number to update.
            url: The new URL (optional, if not changing).
            api_key: The new API key (optional, if not changing).

        Returns:
            True if the instance was updated, False if not found.
        """
        if not self.config.has_section("user_instances"):
            return False

        instance_key = f"instance_{num}"
        api_key_key = f"instance_{num}_api_key"

        if instance_key not in self.config.options("user_instances"):
            return False

        if url is not None:
            self.config.set("user_instances", instance_key, url)

        if api_key is not None:
            self.config.set("user_instances", api_key_key, api_key)

        self.save_config()
        return True

    def remove_user_instance(self, num: int) -> bool:
        """
        Remove a user instance.

        Args:
            num: The instance number to remove.

        Returns:
            True if removed, False if not found.
        """
        if not self.config.has_section("user_instances"):
            return False

        instance_key = f"instance_{num}"
        api_key_key = f"instance_{num}_api_key"

        result1 = self.config.remove_option("user_instances", instance_key)
        # Try to remove API key, but it's okay if it doesn't exist
        result2 = self.config.remove_option("user_instances", api_key_key)

        if result1 or result2:
            self.save_config()
            return True
        return False

    def get_first_user_instance(self) -> Dict[str, str]:
        """
        Get the first user instance for convenience.

        Returns:
            Dictionary with url and api_key, or empty dict if none exists.
        """
        instances = self.get_user_instances()
        if instances:
            return {"url": instances[0]["url"], "api_key": instances[0]["api_key"]}
        return {"url": "", "api_key": ""}

    def delete_section(self, section: str) -> bool:
        """
        Delete a section from the configuration.

        Args:
            section: The section to delete.

        Returns:
            True if the section was removed, False otherwise.
        """
        if self.config.has_section(section):
            self.config.remove_section(section)
            self.save_config()
            return True
        return False


def open_in_explorer(path):
    """
    Open a file or directory in the system's file explorer.

    Args:
        path: Path to the file or directory to open.

    Returns:
        True if successfully opened, False otherwise.
    """
    path_str = str(path)
    system = platform.system()

    try:
        if system == "Windows":
            # On Windows, use the 'start' command to open Explorer
            # The /select flag highlights the file in Explorer
            subprocess.run(["explorer", "/select,", os.path.normpath(path_str)], check=False)
        elif system == "Darwin":  # macOS
            # On macOS, use 'open -R' to reveal the file in Finder
            subprocess.run(["open", "-R", path_str], check=False)
        else:  # Linux and other Unix-like systems
            # Try different file managers in order of preference
            file_managers = [
                [
                    "xdg-open",
                    os.path.dirname(path_str),
                ],  # Generic, uses default file manager
                ["nautilus", path_str],  # GNOME
                ["dolphin", path_str],  # KDE
                ["nemo", path_str],  # Cinnamon
                ["thunar", path_str],  # XFCE
                ["pcmanfm", path_str],  # LXDE
            ]

            for manager in file_managers:
                try:
                    subprocess.run(manager, check=False)
                    break
                except FileNotFoundError:
                    continue

        return True
    except Exception as e:
        # print(f"Error opening file explorer: {e}")
        return False


def create_cli_app(config: Config):
    """
    Create an interactive CLI application for editing configuration settings.

    Args:
        config: The Config instance to edit.
    """
    if not HAS_PROMPT_TOOLKIT:
        print("Error: prompt_toolkit is required for the CLI. Install with pip install prompt_toolkit")
        return

    # Ensure all default keys exist
    config.ensure_default_keys_exist()

    # State management
    class AppState:
        def __init__(self):
            self.sections = config.get_sections()
            self.current_section_idx = 0
            self.current_section = self.sections[0]
            self.options = config.get_options(self.current_section)
            self.current_option_idx = 0 if self.options else -1
            self.current_option = self.options[0] if self.options else None
            self.edit_mode = False
            self.edit_value = ""
            self.message = ""
            self.confirm_reset = False  # New state for confirmation
            self.instance_mode = False  # New state for instance management
            self.instance_action = ""  # "add", "edit", "remove"
            self.instance_edit_step = 0  # 0=url, 1=api_key
            self.edit_instance_num = 0  # For editing existing instances
            self.instances = []  # Cache for user instances

    state = AppState()

    # Helper function to check if a value is a boolean
    def is_boolean_value(value):
        """Check if a value is a boolean (True/False) or boolean string ('True'/'False')."""
        if isinstance(value, bool):
            return True
        return isinstance(value, str) and value.lower() in ("true", "false")

    # Helper function to toggle a boolean value
    def toggle_boolean(value):
        """Toggle a boolean value or string between True/False or 'True'/'False'."""
        if isinstance(value, bool):
            return not value
        return "False" if value.lower() == "true" else "True"

    # Key bindings
    kb = KeyBindings()

    @kb.add("c-c", eager=True)
    @kb.add("c-q", eager=True)
    def _(event):
        """Quit the application."""
        event.app.exit()

    @kb.add("down")
    def _(event):
        if state.edit_mode:
            return

        if state.options and state.current_option_idx < len(state.options) - 1:
            state.current_option_idx += 1
            state.current_option = state.options[state.current_option_idx]
        elif state.current_section_idx < len(state.sections) - 1:
            state.current_section_idx += 1
            state.current_section = state.sections[state.current_section_idx]
            state.options = config.get_options(state.current_section)
            state.current_option_idx = 0 if state.options else -1
            state.current_option = state.options[0] if state.options else None

    @kb.add("up")
    def _(event):
        if state.edit_mode:
            return

        if state.current_option_idx > 0:
            state.current_option_idx -= 1
            state.current_option = state.options[state.current_option_idx]
        elif state.current_section_idx > 0:
            state.current_section_idx -= 1
            state.current_section = state.sections[state.current_section_idx]
            state.options = config.get_options(state.current_section)
            state.current_option_idx = len(state.options) - 1 if state.options else -1
            state.current_option = state.options[-1] if state.options else None

    @kb.add("right")
    def _(event):
        if state.edit_mode:
            return

        if state.current_section_idx < len(state.sections) - 1:
            state.current_section_idx += 1
            state.current_section = state.sections[state.current_section_idx]
            state.options = config.get_options(state.current_section)
            state.current_option_idx = 0 if state.options else -1
            state.current_option = state.options[0] if state.options else None

    @kb.add("left")
    def _(event):
        if state.edit_mode:
            return

        if state.current_section_idx > 0:
            state.current_section_idx -= 1
            state.current_section = state.sections[state.current_section_idx]
            state.options = config.get_options(state.current_section)
            state.current_option_idx = 0 if state.options else -1
            state.current_option = state.options[0] if state.options else None

    def is_valid_number(value, option):
        """Validate if a string is a valid number for a NUMBER_SETTINGS option."""
        try:
            # Try to parse as a number
            if "." in value or "," in value:
                float(value.replace(",", "."))
            else:
                int(value)
            return True
        except (ValueError, TypeError):
            return False

    @kb.add("enter")
    def _(event):
        if state.edit_mode:
            # Validate number settings before saving
            if (
                state.current_option
                and state.current_section
                and state.current_option in config.NUMBER_SETTINGS
                and not is_valid_number(state.edit_value, state.current_option)
            ):
                state.message = f"Invalid number format for {state.current_option}. Changes not saved."
            else:
                # Save and exit edit mode
                if state.current_option and state.current_section:
                    config.set(state.current_option, state.edit_value, state.current_section)
                    state.message = f"Updated {state.current_section}.{state.current_option} to '{state.edit_value}'"
            state.edit_mode = False
        else:
            # Check if selected option has a boolean value
            if state.current_option and state.current_section:
                current_value = config.get(state.current_option, section=state.current_section)

                # If it's a boolean value, toggle it
                if is_boolean_value(current_value):
                    new_value = toggle_boolean(current_value)
                    # Convert to string for storage in config
                    str_value = str(new_value)
                    config.set(state.current_option, str_value, state.current_section)
                    state.message = f"Toggled {state.current_section}.{state.current_option} to '{str_value}'"
                # Otherwise enter edit mode as usual
                else:
                    state.edit_mode = True
                    value = config.get(state.current_option, fallback="", section=state.current_section)
                    # Convert any value back to string for editing
                    state.edit_value = str(value)

    @kb.add("escape")
    def _(event):
        if state.edit_mode:
            state.edit_mode = False
            state.message = "Edit cancelled"
        elif state.confirm_reset:  # Also handle cancellation of reset confirmation
            state.confirm_reset = False
            state.message = "Reset cancelled"
        elif state.instance_mode:
            state.instance_mode = False
            state.instance_action = ""
            state.instance_edit_step = 0
            state.edit_instance_num = 0
            state.message = "Instance management cancelled"

    @kb.add("backspace")
    def _(event):
        if state.edit_mode:
            state.edit_value = state.edit_value[:-1]

    @kb.add("c-d")
    def _(event):
        if not state.edit_mode and state.current_option and state.current_section:
            if config.reset_to_default(state.current_option, section=state.current_section):
                state.message = f"Reset {state.current_section}.{state.current_option} to default value"
            else:
                state.message = f"No default value for {state.current_section}.{state.current_option}"
            # Refresh options
            state.options = config.get_options(state.current_section)

    @kb.add("c-r")
    def _(event):
        if not state.edit_mode:
            # Instead of immediately resetting, ask for confirmation
            state.confirm_reset = True
            state.message = "Reset ALL settings to defaults? Press Y to confirm, N to cancel"

    @kb.add("f2")
    def _(event):
        """Open the config file in system explorer."""
        if open_in_explorer(config.config_path):
            state.message = f"Opened {config.config_path} in file explorer"
        else:
            state.message = "Failed to open file explorer"

    @kb.add("c-t")  # Ctrl+T for Instance management
    def _(event):
        if not state.edit_mode and not state.confirm_reset:
            state.instance_mode = True
            state.instance_action = ""
            state.instances = config.get_user_instances()
            state.message = "Instance Management: (A)dd, (E)dit, (R)emove, or ESC to cancel"

    # Handle all printable characters for edit mode
    @kb.add_binding(" ")
    def handle_space(event):
        if state.edit_mode:
            state.edit_value += " "

    # Add key handlers for all alphanumeric and special characters
    for key in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_@#$%^&*()+=:;,<>/\\\"'[]{}|`~":

        @kb.add(key)
        def handle_char(event, key=key):
            if state.confirm_reset and key.lower() in ("y", "n"):
                if key.lower() == "n":
                    state.message = "Reset cancelled"
                    state.confirm_reset = False
                else:
                    config.reset_all_to_defaults()
                    state.message = "Reset all settings to default values"
                    state.options = config.get_options(state.current_section)
                    state.confirm_reset = False
            elif state.instance_mode and not state.edit_mode:
                # Handle instance management mode key presses
                if state.instance_action == "" and key.lower() in ("a", "e", "r"):
                    if key.lower() == "a":
                        state.instance_action = "add"
                        state.instance_edit_step = 0
                        state.edit_mode = True
                        state.edit_value = ""
                        state.message = "Enter instance URL (http://example.com)"
                    elif key.lower() == "e":
                        if not state.instances:
                            state.message = "No instances to edit"
                        else:
                            state.instance_action = "edit_select"
                            state.message = f"Enter instance number to edit (1-{len(state.instances)})"
                            state.edit_mode = True
                            state.edit_value = ""
                    elif key.lower() == "r":
                        if not state.instances:
                            state.message = "No instances to remove"
                        else:
                            state.instance_action = "remove"
                            state.message = f"Enter instance number to remove (1-{len(state.instances)})"
                            state.edit_mode = True
                            state.edit_value = ""
                elif state.edit_mode:
                    state.edit_value += key
            elif state.edit_mode:
                state.edit_value += key

    @kb.add("enter")
    def _(event):
        if state.instance_mode:
            if state.edit_mode:
                if state.instance_action == "add":
                    if state.instance_edit_step == 0:
                        # Save URL and move to API key
                        state.instance_url = state.edit_value
                        state.instance_edit_step = 1
                        state.edit_value = ""
                        state.message = "Enter API key (or press Enter to skip)"
                    elif state.instance_edit_step == 1:
                        # Add the instance
                        num = config.add_user_instance(state.instance_url, state.edit_value)
                        state.message = f"Added instance #{num}: {state.instance_url}"
                        state.edit_mode = False
                        state.instance_mode = False
                        state.instance_action = ""
                        state.instance_edit_step = 0
                        # Refresh instance list
                        state.instances = config.get_user_instances()

                elif state.instance_action == "edit_select":
                    try:
                        num = int(state.edit_value)
                        if 1 <= num <= len(state.instances):
                            instance = next((i for i in state.instances if i["number"] == num), None)
                            if not instance:
                                instance = state.instances[num - 1]

                            state.edit_instance_num = instance["number"]
                            state.instance_action = "edit_url"
                            state.edit_value = instance["url"]
                            state.message = f"Edit instance URL (current: {instance['url']})"
                        else:
                            state.message = f"Invalid number. Enter 1-{len(state.instances)}"
                    except ValueError:
                        state.message = "Please enter a valid number"

                elif state.instance_action == "edit_url":
                    # Save URL and move to API key
                    state.instance_url = state.edit_value
                    state.instance_action = "edit_api_key"
                    instance = next(
                        (i for i in state.instances if i["number"] == state.edit_instance_num),
                        None,
                    )
                    state.edit_value = instance["api_key"] if instance else ""
                    state.message = "Edit API key (leave empty to keep current)"

                elif state.instance_action == "edit_api_key":
                    # Update the instance
                    success = config.update_user_instance(state.edit_instance_num, state.instance_url, state.edit_value)
                    if success:
                        state.message = f"Updated instance #{state.edit_instance_num}"
                    else:
                        state.message = f"Failed to update instance #{state.edit_instance_num}"

                    state.edit_mode = False
                    state.instance_mode = False
                    state.instance_action = ""
                    # Refresh instance list
                    state.instances = config.get_user_instances()

                elif state.instance_action == "remove":
                    try:
                        num = int(state.edit_value)
                        if 1 <= num <= len(state.instances):
                            instance = next((i for i in state.instances if i["number"] == num), None)
                            if not instance:
                                instance = state.instances[num - 1]
                                num = instance["number"]
                            else:
                                num = instance["number"]

                            if config.remove_user_instance(num):
                                state.message = f"Removed instance #{num}"
                            else:
                                state.message = f"Failed to remove instance #{num}"
                        else:
                            state.message = f"Invalid number. Enter 1-{len(state.instances)}"
                    except ValueError:
                        state.message = "Please enter a valid number"

                    state.edit_mode = False
                    state.instance_mode = False
                    state.instance_action = ""
                    # Refresh instance list
                    state.instances = config.get_user_instances()

            return

        if state.edit_mode:
            # Validate number settings before saving
            if (
                state.current_option
                and state.current_section
                and state.current_option in config.NUMBER_SETTINGS
                and not is_valid_number(state.edit_value, state.current_option)
            ):
                state.message = f"Invalid number format for {state.current_option}. Changes not saved."
            else:
                # Save and exit edit mode
                if state.current_option and state.current_section:
                    config.set(state.current_option, state.edit_value, state.current_section)
                    state.message = f"Updated {state.current_section}.{state.current_option} to '{state.edit_value}'"
            state.edit_mode = False
        else:
            # Check if selected option has a boolean value
            if state.current_option and state.current_section:
                current_value = config.get(state.current_option, section=state.current_section)

                # If it's a boolean value, toggle it
                if is_boolean_value(current_value):
                    new_value = toggle_boolean(current_value)
                    # Convert to string for storage in config
                    str_value = str(new_value)
                    config.set(state.current_option, str_value, state.current_section)
                    state.message = f"Toggled {state.current_section}.{state.current_option} to '{str_value}'"
                # Otherwise enter edit mode as usual
                else:
                    state.edit_mode = True
                    value = config.get(state.current_option, fallback="", section=state.current_section)
                    # Convert any value back to string for editing
                    state.edit_value = str(value)

    # UI rendering function
    def get_formatted_text():
        result = []
        result.append(("class:title", "╔═══ github.com/nichind/pybalt ════╗\n"))

        # Show confirmation message when in confirm_reset mode
        if state.confirm_reset:
            result.append(
                (
                    "class:warning",
                    "WARNING: You are about to reset ALL settings to defaults!\n",
                )
            )
            result.append(("class:warning", "Press Y to confirm, N to cancel\n"))
            result.append(("class:footer", "╚══════════════════════════════════╝\n"))
            return result

        # Show instance management UI when in instance mode
        if state.instance_mode:
            result.append(("class:section", "=== Instance Management ===\n"))

            if state.instances:
                for idx, instance in enumerate(state.instances, 1):
                    result.append(("class:option", f"{idx}. {instance['url']}\n"))
                    if instance["api_key"]:
                        result.append(("class:value", f"   API Key: {instance['api_key']}\n"))
                    else:
                        result.append(("class:value", f"   API Key: <none>\n"))
            else:
                result.append(("class:option", "No instances configured\n"))

            result.append(("class:section", "==========================\n"))

            if not state.instance_action:
                result.append(("class:help", "Press: (A)dd, (E)dit, (R)emove, or ESC to cancel\n"))

            result.append(("class:footer", "╚══════════════════════════════════╝\n"))

            # Controls help
            result.append(("class:help", "Ctrl+C: Exit\n"))

            # Status message
            if state.message:
                result.append(("class:message", f"Status: {state.message}\n"))

            # Edit field if in edit mode
            if state.edit_mode:
                result.append(("class:edit", f"> {state.edit_value}"))
                result.append(("class:cursor", "█\n"))

            return result

        # Build sections and options
        for i, section in enumerate(state.sections):
            prefix = "→ " if i == state.current_section_idx else "  "
            style = "class:highlight" if i == state.current_section_idx else "class:section"
            result.append((style, f"{prefix}[{section}]\n"))

            if i == state.current_section_idx:
                options = config.get_options(section)

                # Special handling for user_instances section to show them in a nicer format
                if section == "user_instances":
                    instances = config.get_user_instances()
                    if instances:
                        for instance in instances:
                            result.append(
                                (
                                    "class:option",
                                    f"  Instance #{instance['number']}: {instance['url']}\n",
                                )
                            )
                            result.append(
                                (
                                    "class:value",
                                    f"    API Key: {instance['api_key'] or '<none>'}\n",
                                )
                            )
                    else:
                        result.append(("class:option", "  No instances configured\n"))

                    result.append(("class:help", "  Press Ctrl+T to manage instances\n"))
                else:
                    # Normal section display
                    for j, option in enumerate(options):
                        value = config.get(option, fallback="", section=section)
                        prefix = "→ " if j == state.current_option_idx else "  "
                        style = "class:highlight" if j == state.current_option_idx else "class:option"

                        # Add indicator for numeric options
                        option_display = f"{option} [#]" if option in config.NUMBER_SETTINGS else option

                        if state.edit_mode and i == state.current_section_idx and j == state.current_option_idx:
                            result.append((style, f"{prefix}{option_display} = "))
                            result.append(("class:edit", f"{state.edit_value}"))
                            result.append(("class:cursor", "█\n"))
                        else:
                            result.append((style, f"{prefix}{option_display} = {value}\n"))

        result.append(("class:footer", "╚══════════════════════════════════╝\n"))

        # Controls help - update to show new key bindings
        result.append(
            (
                "class:help",
                "Controls: ↑/↓: Navigate options | ←/→: Navigate sections\n"
                + "Enter: Edit/Toggle | Esc: Cancel | Ctrl+D: Reset option\n"
                + "Ctrl+R: Reset All | Ctrl+T: Manage Instances | F2: Open in Explorer | Ctrl+C: Exit\n",
            )
        )

        # Status message
        if state.message:
            result.append(("class:message", f"Status: {state.message}\n"))

        return result

    # Style definition
    style = Style.from_dict(
        {
            "title": "bg:#004400 #ffffff",
            "section": "#00ff00",
            "option": "#ffffff",
            "highlight": "bold #ffff00",
            "edit": "bg:#000088 #ffffff",
            "cursor": "#ff0000",
            "footer": "bg:#004400 #ffffff",
            "help": "#888888",
            "message": "bold #ff8800",
            "warning": "bg:#880000 #ffffff bold",  # New style for warnings
        }
    )

    # Create Layout
    layout = Layout(HSplit([Window(FormattedTextControl(get_formatted_text))]))

    # Create and run app
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=style,
        mouse_support=True,
    )

    try:
        # Check if we're in an async context with a running event loop
        loop = get_event_loop()
        if loop.is_running():
            print("Cannot run interactive CLI in an active async environment.")
            print("Use the command-line interface instead (get/set/list commands).")
            return False
        # Loop exists but isn't running, so we can use it
        return loop.run_until_complete(app.run_async())
    except RuntimeError:
        # No event loop, create one (normal synchronous context)
        loop = new_event_loop()
        return loop.run_until_complete(app.run_async())


async def async_main():
    """
    Async-compatible version of the main function for the configuration CLI utility.
    """
    config = Config()
    config.ensure_default_keys_exist()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "get" and len(sys.argv) >= 4:
            section, option = sys.argv[2:4]
            fallback = sys.argv[4] if len(sys.argv) > 4 else None
            print(config.get(option, fallback, section))

        elif cmd == "set" and len(sys.argv) == 5:
            section, option, value = sys.argv[2:5]
            config.set(option, value, section)
            print(f"Set {section}.{option} to '{value}'")

        elif cmd == "delete" and len(sys.argv) == 4:
            section, option = sys.argv[2:4]
            if config.delete_option(option, section):
                print(f"Deleted {section}.{option}")
            else:
                print(f"Option {section}.{option} not found")

        elif cmd == "delete-section" and len(sys.argv) == 3:
            section = sys.argv[2]
            if config.delete_section(section):
                print(f"Deleted section {section}")
            else:
                print(f"Section {section} not found")

        elif cmd == "list":
            settings = config.get_all_settings()
            for section, options in settings.items():
                print(f"[{section}]")
                for option, value in options.items():
                    print(f"  {option} = {value}")
                print()

        elif cmd == "edit":
            # In async context, just show message that interactive editing isn't available
            print("Interactive editing is not available in async environment.")
            print("Use the command-line interface instead (get/set/list commands).")

        else:
            print("Usage:")
            print("  pybalt config get <section> <option> [fallback]")
            print("  pybalt config set <section> <option> <value>")
            print("  pybalt config delete <section> <option>")
            print("  pybalt config delete-section <section>")
            print("  pybalt config list")
    else:
        # In async context, just show message that interactive editing isn't available
        print("Interactive editing is not available in async environment.")
        print("Use the command-line interface instead (get/set/list commands).")


def main(force_cli: bool = False):
    """
    Main entry point for the configuration CLI utility.
    """
    # Check if we're in an async context
    try:
        loop = get_event_loop()
        if loop.is_running():
            # We're in an async context with a running loop
            print("Detected async environment, using async-compatible mode")
            # Return a coroutine that can be awaited
            return async_main()
    except RuntimeError:
        # Not in an async context or no loop exists
        pass

    # Regular synchronous path
    config = Config()
    config.ensure_default_keys_exist()

    if len(sys.argv) > 1 and not force_cli:
        cmd = sys.argv[1]

        if cmd == "get" and len(sys.argv) >= 4:
            section, option = sys.argv[2:4]
            fallback = sys.argv[4] if len(sys.argv) > 4 else None
            print(config.get(option, fallback, section))

        elif cmd == "set" and len(sys.argv) == 5:
            section, option, value = sys.argv[2:5]
            config.set(option, value, section)
            print(f"Set {section}.{option} to '{value}'")

        elif cmd == "delete" and len(sys.argv) == 4:
            section, option = sys.argv[2:4]
            if config.delete_option(option, section):
                print(f"Deleted {section}.{option}")
            else:
                print(f"Option {section}.{option} not found")

        elif cmd == "delete-section" and len(sys.argv) == 3:
            section = sys.argv[2]
            if config.delete_section(section):
                print(f"Deleted section {section}")
            else:
                print(f"Section {section} not found")

        elif cmd == "list":
            settings = config.get_all_settings()
            for section, options in settings.items():
                print(f"[{section}]")
                for option, value in options.items():
                    print(f"  {option} = {value}")
                print()

        elif cmd == "edit":
            create_cli_app(config)

        else:
            print("Usage:")
            print("  pybalt config get <section> <option> [fallback]")
            print("  pybalt config set <section> <option> <value>")
            print("  pybalt config delete <section> <option>")
            print("  pybalt config delete-section <section>")
            print("  pybalt config list")
            print("  pybalt config edit")
    else:
        # Interactive mode
        create_cli_app(config)


if __name__ == "__main__":
    # Start the gui if the script was called directly
    main()
