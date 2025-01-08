from os import path, getenv, makedirs
from typing import TypedDict, Unpack
from shutil import get_terminal_size
from requests import get
from time import time


class Translator:
    language = getenv("LANG", "en")[:2]

    def __init__(self, language: str = None):
        self.language = language if language else self.language

    def translate(self, key: str, language: str = None) -> str:
        """Translate a key from the translation file."""
        language = language or self.language
        file = path.join(path.dirname(__file__), "locales", f"{language}.txt")
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
    cobalt_config_dir = path.join(path.expanduser("~"), ".config", "cobalt")
    if not path.exists(cobalt_config_dir):
        makedirs(cobalt_config_dir, exist_ok=True)

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
    @classmethod
    def get_size(cls) -> tuple[int, int]:
        return get_terminal_size()

    @classmethod
    def lprint(cls, text: str, lend: str = "", **kwargs) -> None:
        text = str(text)
        if len(text) >= cls.get_size()[0]:
            text = (
                text[: cls.get_size()[0] - (3 + (len(lend) + 1 if lend else 0))]
                + "..."
                + (" " + lend if lend else "")
            )
        else:
            text = (
                text
                + " " * (cls.get_size()[0] - len(text) - (len(lend) + 1 if lend else 0))
                + (lend if lend else "")
            )
        print(text, **kwargs)


lprint = Terminal.lprint


class StatusParent:
    total_size: int
    downloaded_size: int
    start_at: int
    time_passed: float
    file_path: str
    filename: str
    download_speed: int


class _DownloadCallbackData(TypedDict):
    filename: str
    downloaded_size: int
    start_at: int
    time_passed: int | float
    file_path: str
    download_speed: int
    total_size: int


class DefaultCallbacks:
    @classmethod
    async def status_callback(cls, **data: Unpack[_DownloadCallbackData]) -> None:
        lprint(
            f"Downloading {data.get('filename')} | time passed: {int(time() - data.get('start_at'))}s, "
            f"{data.get('downloaded_size') / 1024 / 1024 : .2f} MB | "
            f"{data.get('download_speed') / 1024 : .2f} KB/s | "
            f"{data.get('total_size', -1) / 1024 / 1024 : .2f} MB total",
            end="\r",
        )

    @classmethod
    async def done_callback(cls, **data: Unpack[_DownloadCallbackData]) -> None:
        file_size = path.getsize(data["file_path"]) / (1024 * 1024)
        lprint(f"Downloaded {data['file_path']}, size: {file_size:.2f} MB")
