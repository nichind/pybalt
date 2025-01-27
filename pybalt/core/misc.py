from os import path, getenv, makedirs
from typing import TypedDict, Unpack
from shutil import get_terminal_size
from requests import get
from time import time
from rich.console import Console
import re


def get_cobalt_config_dir() -> str:
    _ = path.join(path.expanduser("~"), ".config", "cobalt")
    if not path.exists(_):
        makedirs(_, exist_ok=True)
    return _


cobalt_config_dir = get_cobalt_config_dir()


class Translator:
    language = getenv("LANG", "en")[:2]

    def __init__(self, language: str = None):
        self.language = language if language else self.language

    def translate(self, key: str, language: str = None) -> str:
        """Translate a key from the translation file."""
        language = language or self.language
        file = path.join(
            path.dirname(path.dirname(__file__)), "locales", f"{language}.txt"
        )
        if not path.exists(file):
            if language.upper() != "EN":
                return self.translate(key, "EN")
            return key
        with open(file) as f:
            for line in f:
                if "=" in line and line.split("=")[0].strip().upper() == key.upper():
                    return line[line.index("=") + 1 :].strip()
            if language.upper() != "EN":
                return self.translate(key, "EN")
            return key


def install_cobalt_container() -> None:
    """
    Installs and starts a local Cobalt instance using Docker.

    This function checks if Docker is installed on the system and installs it if not.
    It handles different installation procedures for Windows, and Linux.
    After ensuring Docker is installed, it downloads a docker-compose file and
    starts the Cobalt instance.

    The function prompts the user for confirmation before proceeding with the
    installation process.

    Note: The user may need to manually install Docker on unsupported operating
    systems or distributions.

    Raises:
        subprocess.CalledProcessError: If a command execution fails.
    """

    import platform
    import subprocess

    def is_docker_installed():
        try:
            subprocess.run(["docker", "--version"], check=True, capture_output=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def install_docker_windows():
        print("Installing Docker Desktop on Windows...")
        subprocess.run(
            [
                "start",
                "",
                "/wait",
                "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe",
            ],
            shell=True,
            check=True,
        )
        print("Docker Desktop Installation complete")
        print("You might need to configure WSL2 if is not set")
        print("Please complete the setup process. Restart may be required.")

    def install_docker_macos():
        print("Installing Docker Desktop on macOS...")
        subprocess.run(
            ["open", "-W", "https://desktop.docker.com/mac/main/amd64/Docker.dmg"],
            check=True,
        )
        print("Docker Desktop Installation complete")
        print("Please complete the setup process. Restart may be required.")

    def install_docker_linux():
        print("Installing Docker Engine on Linux...")
        try:
            distro = platform.freedesktop_os_release().get("ID", None)
            if distro in ("ubuntu", "debian"):
                subprocess.run(["sudo", "apt", "update"], check=True)
                subprocess.run(
                    ["sudo", "apt", "install", "-y", "docker.io"], check=True
                )
                subprocess.run(
                    ["sudo", "systemctl", "enable", "docker", "--now"], check=True
                )
                print("Docker Engine Installation complete")
            elif distro in ("centos", "fedora", "rhel"):
                subprocess.run(["sudo", "yum", "update", "-y"], check=True)
                subprocess.run(["sudo", "yum", "install", "-y", "docker"], check=True)
                subprocess.run(
                    ["sudo", "systemctl", "enable", "docker", "--now"], check=True
                )
                print("Docker Engine Installation complete")
            elif distro in ("arch"):
                subprocess.run(["sudo", "pacman", "-Syu", "--noconfirm"], check=True)
                subprocess.run(
                    ["sudo", "pacman", "-S", "--noconfirm", "docker"], check=True
                )
                subprocess.run(
                    ["sudo", "systemctl", "enable", "docker", "--now"], check=True
                )
                print("Docker Engine Installation complete")
            else:
                print("Unsupported Linux distribution. Please install docker by hand.")
                return
        except subprocess.CalledProcessError:
            print("Error during installation on Linux. Please install docker by hand.")
            return

    while True:
        inp = str(
            input("You sure you want to install local cobalt instance? (y/n): ")
        ).lower()
        if inp == "y":
            break
        elif inp == "n":
            return

    if not is_docker_installed():
        inp = str(
            input("Docker is not installed. Do you want me to install it? (y/n): ")
        ).lower()
        if inp == "y":
            os_name = platform.system()
            if os_name == "Windows":
                install_docker_windows()
            elif os_name == "Darwin":
                install_docker_macos()
            elif os_name == "Linux":
                install_docker_linux()
            else:
                print(
                    "Unsupported operating system: " + os_name,
                    " Please install docker by hand.",
                )
            print(
                "Docker installation complete, you might need to restart your computer."
            )
        else:
            print("Please install docker by hand.")
            return

    with open(path.join(cobalt_config_dir, "docker-compose.yml"), "w+") as compose:
        compose.write(
            get(
                "https://raw.githubusercontent.com/imputnet/cobalt/refs/heads/main/docs/examples/docker-compose.example.yml"
            ).text
        )

    subprocess.run(["docker", "compose", "up", "-d"], check=True, cwd=cobalt_config_dir)
    print("Cobalt instance has been installed and started.")
    print(
        "If setup was successful, you can find the local cobalt instance at http://localhost:9000"
    )


class Terminal:
    console = Console()

    replaces = {
        ":accent:": "\033[96m",
        ":reset:": "\033[0m",
        ":end:": "\033[0m",
        ":bold:": "\033[1m",
        ":underline:": "\033[4m",
        ":italic:": "\033[3m",
        ":strikethrough:": "\033[9m",
        ":red:": "\033[31m",
        ":green:": "\033[32m",
        ":yellow:": "\033[33m",
        ":blue:": "\033[34m",
        ":magenta:": "\033[35m",
        ":cyan:": "\033[36m",
        ":purple:": "\033[35m",
        ":orange:": "\033[33m",
        ":pink:": "\033[35m",
        ":light_gray:": "\033[37m",
        ":dark_gray:": "\033[90m",
        ":lime:": "\033[92m",
        ":white:": "\033[37m",
        ":gray:": "\033[90m",
        ":bg_black:": "\033[40m",
        ":bg_red:": "\033[41m",
        ":bg_green:": "\033[42m",
        ":bg_yellow:": "\033[43m",
        ":bg_blue:": "\033[44m",
        ":bg_magenta:": "\033[45m",
        ":bg_cyan:": "\033[46m",
        ":bg_white:": "\033[47m",
    }

    pattern = re.compile(
        r"[\x1b\x9b\x9f][\[\]()\\]*[0-?]*[ -/]*[@-~]"
        r"|[\U00010000-\U0010ffff]"
        r"|[\u200d]"
        r"|[\u2640-\u2642]"
        r"|[\u2600-\u2b55]"
        r"|[\u23cf]"
        r"|[\u23e9]"
        r"|[\u231a]"
        r"|[\ufe0f]"  # dingbats
        r"|[\u3030]"
        "+",
        flags=re.UNICODE,
    )

    @classmethod
    def get_size(cls) -> tuple[int, int]:
        return get_terminal_size()

    @classmethod
    def apply_style(cls, text: str) -> str:
        for key, value in cls.replaces.items():
            text = text.replace(key, value)
        return text

    @classmethod
    def true_len(cls, text: str) -> int:
        text = cls.apply_style(text)
        _ = None
        for i, char in enumerate(text):
            if char == ":" and not _:
                _ = i
            elif char == ":" and _:
                text = text.replace(text[_ + 1 : i], "")
            elif char == " " and _:
                _ = None
        return len(
            re.sub(
                r"[\u001B\u009B][\[\]()#;?]*((([a-zA-Z\d]*(;[-a-zA-Z\d\/#&.:=?%@~_]*)*)?\u0007)|((\d{1,4}(?:;\d{0,4})*)?[\dA-PR-TZcf-ntqry=><~]))",
                "",
                text,
            )
        )

    @classmethod
    def lprint(cls, *args: str, right: bool = False, **kwargs) -> None:
        args = [
            cls.apply_style(
                str(arg) if not isinstance(arg, Exception) else ":red:" + str(arg)
            )
            for arg in args
        ]
        terminal_width = cls.get_size()[0]
        num_args = len(args)

        if "highlight" not in kwargs:
            kwargs["highlight"] = False

        if num_args == 0:
            return

        if num_args == 3:
            _center = args[1].center(terminal_width).rstrip()
            print(
                " " * (terminal_width - cls.true_len(args[2]))
                + cls.apply_style(args[2])
                + cls.apply_style(":end:"),
                end="\r",
            )
            cls.console.print(
                " " * ((len(_center) - cls.true_len(_center)) // 2)
                + _center
                + cls.apply_style(":end:"),
                end="\r",
                highlight=kwargs["highlight"],
            )
            cls.console.print(args[0], end="\r", highlight=kwargs["highlight"])
        elif num_args == 2:
            print(
                " " * (terminal_width - cls.true_len(args[1]))
                + cls.apply_style(args[1])
                + cls.apply_style(":end:"),
                end="\r",
            )
            cls.console.print(
                args[0] + cls.apply_style(":end:"),
                end="\r",
                highlight=kwargs["highlight"],
            )
        else:
            if right:
                print(
                    " " * (terminal_width - cls.true_len(args[0]))
                    + cls.apply_style(args[0])
                    + cls.apply_style(":end:"),
                    end="\r",
                )
            else:
                cls.console.print(
                    args[0].ljust(terminal_width),
                    end="\r",
                    highlight=kwargs["highlight"],
                )
        cls.console.print(cls.apply_style(":end:"), **kwargs)


lprint = Terminal.lprint
translate = Translator().translate
tl = translate


class StatusParent:
    total_size: int
    downloaded_size: int
    start_at: int
    time_passed: float
    file_path: str
    filename: str
    download_speed: int
    completed: bool

    def __init__(self) -> None:
        self.total_size = 0
        self.downloaded_size = 0
        self.start_at = 0
        self.time_passed = 0
        self.file_path = None
        self.filename = None
        self.download_speed = 0
        self.completed = False

    def __repr__(self) -> str:
        values = ", ".join(f"{key}={value!r}" for key, value in self.__dict__.items())
        return f"{self.__class__.__name__}({values})"


class _DownloadCallbackData(TypedDict):
    filename: str
    downloaded_size: int
    start_at: int
    time_passed: int | float
    file_path: str
    download_speed: int
    total_size: int
    iteration: int
    eta: int


class DefaultCallbacks:
    @classmethod
    async def status_callback(cls, **data: Unpack[_DownloadCallbackData]) -> None:
        percent_downloaded = (
            int((data.get("downloaded_size") / data.get("total_size")) * 100)
            if data.get("total_size", -1) != -1
            else -1
        )
        if percent_downloaded != -1:
            bar_length = 24
            completed_length = int(round(bar_length * percent_downloaded / float(100)))
            bar_fill = "▇" * completed_length
            bar_empty = "-" * (bar_length - completed_length)
            spinner = ["⢎⡰", "⢎⡡", "⢎⡑", "⢎⠱", "⠎⡱", "⢊⡱", "⢌⡱", "⢆⡱"]
            current_spin = spinner[data.get("iteration") % len(spinner)]
            lprint(
                f"⭳  :gray:{data.get('filename')} ",
                f":gray:[:green:{bar_fill}:gray:{bar_empty}]:end: :lime:{data.get('downloaded_size') / (1024 * 1024):.2f}:gray:/{data.get('total_size') / (1024 * 1024):.2f}MB :magenta:{data.get('download_speed') / (1024 * 1024):.2f}MB/s :cyan:{data.get('time_passed'):.2f}s :white::bold:{current_spin}",
                end="\r",
                highlight=False,
            )
        else:
            spinner = ["⢎⡰", "⢎⡡", "⢎⡑", "⢎⠱", "⠎⡱", "⢊⡱", "⢌⡱", "⢆⡱"]
            current_spin = spinner[data.get("iteration") % len(spinner)]
            lprint(
                f"⭳  :gray:{data.get('filename')} ",
                f":lime:{data.get('downloaded_size') / (1024 * 1024):.2f}MB :magenta:{data.get('download_speed') / (1024 * 1024):.2f}MB/s :cyan:{data.get('time_passed'):.2f}s :white::bold:{current_spin}",
                end="\r",
            )

    @classmethod
    async def done_callback(cls, **data: Unpack[_DownloadCallbackData]) -> None:
        file_size = path.getsize(data["file_path"]) / (1024 * 1024)
        lprint(
            f":green:✔  :white:{data['file_path']}",
            f":green:{file_size:.2f}MB :cyan:{data.get('time_passed'):.2f}s",
        )


def check_updates() -> bool:
    """
    Checks for updates of pybalt by comparing the current version to the latest version from pypi.org.

    Returns:
        bool: True if the check was successful, False otherwise.
    """
    from pkg_resources import get_distribution, DistributionNotFound
    from requests import get, exceptions

    try:
        current_version = get_distribution("pybalt").version
        response = get("https://pypi.org/pypi/pybalt/json", timeout=10)
        response.raise_for_status()
        data = response.json()
        last_version = data["info"]["version"]
        if last_version != current_version:
            lprint(
                tl("UPDATE_AVALIABLE").format(
                    last_version=last_version, current_version=current_version
                )
            )
            return False
    except DistributionNotFound:
        lprint(tl("PACKAGE_NOT_FOUND"))
    except exceptions.RequestException as e:
        lprint(tl("UPDATE_CHECK_FAIL").format(error=e))
    return True


def cfg_value(key: str = None, value: str = None) -> dict | str | None:
    cfg_path = path.join(cobalt_config_dir, "config.cfg")
    if not path.exists(cfg_path):
        with open(cfg_path, "w") as f:
            f.write("")
    if key is None:
        cfg_items = {}
        with open(cfg_path, "r") as f:
            for line in f:
                if "=" in line:
                    cfg_items[line.split("=")[0].strip()] = line.split("=")[1].strip()
        return cfg_items
    elif value is None:
        with open(cfg_path, "r") as f:
            for line in f:
                if line.startswith(key):
                    return line.split("=")[1].strip()
    else:
        cfg_content = []
        found = False
        with open(cfg_path, "r") as f:
            for line in f:
                if line.startswith(key):
                    line = f"{key}={value}\n"
                    found = True
                cfg_content.append(line)
        if not found:
            cfg_content.append(f"{key}={value}\n")
        with open(cfg_path, "w") as f:
            f.writelines(cfg_content)
