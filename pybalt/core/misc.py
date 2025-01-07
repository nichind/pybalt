from os import path, getenv
from typing import TypedDict, Unpack
from shutil import get_terminal_size
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
        file_size = path.getsize(data['file_path']) / (1024 * 1024)
        lprint(f"Downloaded {data['file_path']}, size: {file_size:.2f} MB")
