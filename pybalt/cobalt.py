from aiohttp import ClientSession, client_exceptions
from aiofiles import open as aopen
import pybalt.exceptions as exceptions
from shutil import get_terminal_size
from os import path, makedirs, getenv
from sys import platform
from subprocess import run as srun
from os.path import expanduser
from time import time
from typing import Literal
from dotenv import load_dotenv
from re import findall
from importlib.metadata import version, PackageNotFoundError


class Translator:
    def __init__(self, language: str = "en") -> None:
        """
        Initializes a new Translator object with the specified language.

        Parameters:
        - language (str, optional): The language to use for translations. Defaults to the system language or "en".
        """
        self.language = getenv("LANG", "en")[:2] or language

    def translate(self, key: str, locale: Literal["en", "ru"] = None) -> str:
        """
        Returns the translation of the given key in the given locale.

        If the given locale does not exist, the English translation is returned.

        If the given key does not exist in the given locale, the given key is returned.

        :param key: The key to translate
        :param locale: The locale to translate into, default is "en" if not set
        :return: The translated key
        """
        locale = locale or self.language
        file = path.join(path.dirname(__file__), "locales", f"{locale}.txt")
        if not path.exists(file):
            if locale.upper() != "EN":
                return self.translate_string(key, "EN")
            return key
        with open(file) as f:
            for line in f.readlines():
                if "=" in line and line.split("=")[0].strip().upper() == key.upper():
                    translated = (
                        line[line.index("=") + 1 :]
                        .replace("\\n", "\n")
                        .replace("\\t", "\t")
                        .replace("\\r", "\r")
                        .replace("\\033", "\033")
                    )
                    while translated.endswith("\n"):
                        translated = translated[:-1]
                    return translated
            if locale.upper() != "EN":
                return self.translate_string(key, "EN")
            return key


translator = Translator()
tl = translator.translate


async def check_updates() -> bool:
    """
    Checks for updates of pybalt by comparing the current version to the latest version from pypi.org

    Returns:
        bool: True if the check was successful, False otherwise
    """
    try:
        current_version = version("pybalt")
        async with ClientSession() as session:
            async with session.get("https://pypi.org/pypi/pybalt/json") as response:
                data = await response.json()
                last_version = data["info"]["version"]
        if last_version != current_version:
            print(
                tl("UPDATE_AVALIABLE").format(
                    last_version=last_version, current_version=current_version
                )
            )
            return False
    except PackageNotFoundError:
        print(tl("PACKAGE_NOT_FOUND"))
    except Exception as e:
        print(tl("UPDATE_CHECK_FAIL").format(error=e))
    return True


class File:
    def __init__(
        self,
        cobalt=None,
        status: str = None,
        url: str = None,
        filename: str = None,
        tunnel: str = None,
    ) -> None:
        """
        Creates a new File object.

        Parameters:
        - cobalt (Cobalt): The Cobalt instance associated with this File.
        - status (str): The status of the file.
        - url (str): The URL of the file.
        - filename (str): The filename of the file.
        - tunnel (str): The tunnel URL of the file.

        Fields:
        - downloaded (bool): Whether the file has been downloaded.
        - path (str): The path where the file is saved.
        """
        self.cobalt = cobalt or Cobalt()
        self.status = status
        self.url = url
        self.tunnel = tunnel
        self.filename = filename
        self.extension = self.filename.split(".")[-1] if self.filename else None
        self.downloaded = False
        self.path = None

    async def download(self, path_folder: str = None) -> str:
        """
        Downloads the file and saves it to the specified folder.

        Parameters:
        - path_folder (str, optional): The folder path where the file should be saved. Defaults to the user's downloads folder.

        Returns:
        - str: The path to the downloaded file.
        """
        self.path = await self.cobalt.download(
            self.url, self.filename, path_folder, file=self
        )
        self.downloaded = True
        return self.path

    def __repr__(self):
        return "<Media " + (self.path if self.path else f'"{self.filename}"') + ">"


class DownloadedFile(File):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.downloaded = True

    def __repr__(self):
        return "<File " + (self.path if self.path else f'"{self.filename}"') + ">"


class Cobalt:
    def __init__(
        self, api_instance: str = None, api_key: str = None, headers: dict = None
    ) -> None:
        """
        Initializes a new Cobalt object.

        Parameters:
        - api_instance (str, optional): The URL of the Cobalt API instance to use. Defaults to https://dwnld.nichind.dev.
        - api_key (str, optional): The API key for the Cobalt API instance. Defaults to "".
        - headers (dict, optional): Custom headers for requests. Defaults to a dictionary with necessary headers.

        Environment variables:
        - COBALT_API_URL: The URL of the Cobalt API instance.
        - COBALT_API_KEY: The API key for the Cobalt API instance.
        - COBALT_USER_AGENT: The User-Agent header for requests. Defaults to "pybalt/python".
        """
        load_dotenv()

        self.api_instance = (
            api_instance or getenv("COBALT_API_URL") or "https://dwnld.nichind.dev"
        )
        self.api_key = api_key or getenv("COBALT_API_KEY") or ""

        if not self.api_key and self.api_instance == "https://dwnld.nichind.dev":
            self.api_key = "b05007aa-bb63-4267-a66e-78f8e10bf9bf"  # Default API key for dwnld.nichind.dev

        self.headers = headers or {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.api_key}" if self.api_key else "",
        }

        self.headers.setdefault(
            "User-Agent", getenv("COBALT_USER_AGENT") or "pybalt/python"
        )

        if not self.api_key:
            self.headers.pop("Authorization", None)

        self.skipped_instances = []

    def download_callback(self, *args, **kwargs):
        """You can replace this function with your own callback function, called every ~2 seconds when downloading a file."""

    async def get_instance(self):
        """
        Finds a good instance of Cobalt API and changes the API instance of this object to it.

        It first gets a list of all instances, then filters out the ones with low trust or old version.
        Then it filters out the ones with too many dead services.
        It then picks the one with highest score and checks if it is already in the list of skipped instances.
        If it is, it picks the next one.
        """
        headers = self.headers.copy()
        async with ClientSession(headers=headers) as cs:
            async with cs.get(
                "https://instances.cobalt.best/api/instances.json"
            ) as resp:
                instances = await resp.json()
                good_instances = []
                for instance in instances:
                    if (
                        "version" not in instance
                        or int(instance["version"].split(".")[0]) < 10
                    ):
                        continue
                    dead_services = sum(
                        1
                        for service, status in instance["services"].items()
                        if not status
                    )
                    if dead_services > 7:
                        continue
                    good_instances.append(instance)
                while good_instances:
                    good_instances.sort(
                        key=lambda instance: instance["score"], reverse=True
                    )
                    next_instance = good_instances.pop(0)
                    try:
                        async with cs.get(
                            next_instance["protocol"] + "://" + next_instance["api"]
                        ) as resp:
                            json = await resp.json()
                            if json["cobalt"]["url"] in self.skipped_instances:
                                raise exceptions.BadInstance()
                            self.api_instance = json["cobalt"]["url"]
                            break
                    except Exception:
                        pass
        return self.api_instance

    async def get(
        self,
        url: str,
        quality: Literal[
            "max", "3840", "2160", "1440", "1080", "720", "480", "360", "240", "144"
        ] = "1080",
        download_mode: Literal["auto", "audio", "mute"] = "auto",
        filename_style: Literal["classic", "pretty", "basic", "nerdy"] = "pretty",
        audio_format: Literal["best", "mp3", "ogg", "wav", "opus"] = None,
        youtube_video_codec: Literal["vp9", "h264"] = None,
        youtube_hls: bool = True
    ) -> File:
        """
        Retrieves a File object for the specified URL with optional quality, mode, and format settings.

        Parameters:
        - url (str): The URL of the video or media to retrieve.
        - quality (Literal['max', '3840', '2160', '1440', '1080', '720', '480', '360', '240', '144'], optional): Desired quality of the media. Defaults to '1080'.
        - download_mode (Literal['auto', 'audio', 'mute'], optional): Mode of download, affecting audio and video handling. Defaults to 'auto'.
        - filename_style (Literal['classic', 'pretty', 'basic', 'nerdy'], optional): Style of the filename. Defaults to 'pretty'.
        - audio_format (Literal['best', 'mp3', 'ogg', 'wav', 'opus'], optional): Audio format for the download if applicable.
        - youtube_video_codec (Literal['vp9', 'h264'], optional): Codec for YouTube video downloads.

        Returns:
        - File: A File object containing metadata for the download.

        Raises:
        - LinkError: If the provided URL is invalid.
        - ContentError: If the content of the URL cannot be retrieved.
        - InvalidBody: If the request body is invalid.
        - AuthError: If authentication fails.
        - UnrecognizedError: If an unrecognized error occurs.
        - BadInstance: If the Cobalt API instance cannot be reached.
        """
        async with ClientSession(headers=self.headers) as cs:
            if not self.api_instance or self.api_instance.strip().replace(
                "https://", ""
            ).replace("http://", "").lower() in ["f", "fetch", "get"]:
                print("Fetching instance...\r", end="")
                await self.get_instance()
            try:
                if quality not in [
                    "max",
                    "3840",
                    "2160",
                    "1440",
                    "1080",
                    "720",
                    "480",
                    "360",
                    "240",
                    "144",
                ]:
                    try:
                        quality = {
                            "8k": "3840",
                            "4k": "2160",
                            "2k": "1440",
                            "1080p": "1080",
                            "720p": "720",
                            "480p": "480",
                            "360p": "360",
                            "240p": "240",
                            "144p": "144",
                        }[quality]
                    except KeyError:
                        quality = "1080"
                json = {
                    "url": url.replace("'", "").replace('"', "").replace("\\", ""),
                    "videoQuality": quality,
                    "youtubeVideoCodec": youtube_video_codec
                    if youtube_video_codec
                    else "h264",
                    "filenameStyle": filename_style,
                    "youtubeHLS": youtube_hls,
                }
                if audio_format:
                    json["audioFormat"] = audio_format
                async with cs.post(
                    ("https://" if "http" not in self.api_instance else "")
                    + self.api_instance,
                    json=json, timeout=12,
                ) as resp:
                    json = await resp.json()
                    if "error" in json:
                        match json["error"]["code"].split(".")[2]:
                            case "link":
                                raise exceptions.LinkError(
                                    tl("INVALID_URL").format(
                                        error=json["error"]["code"], url=url
                                    )
                                )
                            case "content":
                                if (
                                    json["error"]["code"].split(".")[-1]
                                    == "unavailable"
                                ):
                                    await self.get_instance()
                                    return await self.get(
                                        url,
                                        quality,
                                        download_mode,
                                        filename_style,
                                        audio_format,
                                        youtube_video_codec,
                                    )
                                raise exceptions.ContentError(
                                    tl("CONTENT_GET_ERROR").format(
                                        error=json["error"]["code"], url=url
                                    )
                                )
                            case "invalid_body":
                                raise exceptions.InvalidBody(
                                    tl("INVALID_BODY").format(
                                        error=json["error"]["code"]
                                    )
                                )
                            case "auth":
                                if (
                                    json["error"]["code"].split(".")[-1] == "missing"
                                    or json["error"]["code"].split(".")[-1]
                                    == "not_found"
                                ):
                                    self.skipped_instances.append(self.api_instance)
                                    await self.get_instance()
                                    return await self.get(
                                        url,
                                        quality,
                                        download_mode,
                                        filename_style,
                                        audio_format,
                                        youtube_video_codec,
                                    )
                                raise exceptions.AuthError(
                                    tl("AUTH_ERROR").format(error=json["error"]["code"])
                                )
                            case "youtube":
                                self.skipped_instances.append(self.api_instance)
                                await self.get_instance()
                                return await self.get(
                                    url,
                                    quality,
                                    download_mode,
                                    filename_style,
                                    audio_format,
                                    # print(json)  youtube_video_codec,
                                )
                            case "fetch":
                                self.skipped_instances.append(self.api_instance)
                                print(json)
                                print(
                                    tl("FETCH_ERROR").format(
                                        url=url if len(url) < 40 else url[:40] + "...",
                                        api_instance=self.api_instance,
                                    ),
                                    end="",
                                )
                                await self.get_instance()
                                return await self.get(
                                    url,
                                    quality,
                                    download_mode,
                                    filename_style,
                                    audio_format,
                                    youtube_video_codec,
                                )
                        raise exceptions.UnrecognizedError(
                            f'{json["error"]["code"]} - {json["error"]}'
                        )
                    return File(
                        cobalt=self,
                        status=json["status"],
                        url=url.replace("'", "").replace('"', "").replace("\\", ""),
                        tunnel=json["url"],
                        filename=json["filename"],
                    )
            except client_exceptions.ClientConnectorError:
                raise exceptions.BadInstance(
                    tl("CANNOT_REACH").format(api_instance=self.api_instance)
                )

    async def download(
        self,
        url: str = None,
        quality: str = None,
        filename: str = None,
        path_folder: str = None,
        download_mode: Literal["auto", "audio", "mute"] = "auto",
        filename_style: Literal["classic", "pretty", "basic", "nerdy"] = "pretty",
        audio_format: Literal["best", "mp3", "ogg", "wav", "opus"] = None,
        youtube_video_codec: Literal["vp9", "h264"] = None,
        playlist: bool = False,
        file: File = None,
        show: bool = None,
        play: bool = None,
    ) -> str:
        """
        Downloads a file from a specified URL or playlist, saving it to a given path with optional quality, filename, and format settings.

        Parameters:
        - url (str, optional): The URL of the video or media to download.
        - quality (str, optional): The desired quality of the download.
        - filename (str, optional): The desired name for the downloaded file.
        - path_folder (str, optional): The folder path where the file should be saved.
        - download_mode (Literal['auto', 'audio', 'mute'], optional): The mode of download, affecting audio and video handling.
        - filename_style (Literal['classic', 'pretty', 'basic', 'nerdy'], optional): Style of the filename.
        - audio_format (Literal['best', 'mp3', 'ogg', 'wav', 'opus'], optional): Audio format for the download if applicable.
        - youtube_video_codec (Literal['vp9', 'h264'], optional): Codec for YouTube video downloads.
        - playlist (bool or str, optional): Whether the URL is a playlist link, you can also pass a playlist link here.
        - file (File, optional): A pre-existing File object to use for the download.

        Returns:
        - str: The path to the downloaded file.

        Raises:
        - BadInstance: If the specified instance cannot be reached.
        """
        max_print_length, _ = 0, 0
        if playlist or len(findall("[&?]list=([^&]+)", url)) > 0:
            if type(playlist) is str:
                url = playlist

            from pytube import Playlist

            playlist = Playlist(url)
            for i, item_url in enumerate(playlist.video_urls):
                if "music." in url:
                    item_url = item_url.replace("www", "music")
                print(f"[{i + 1}/{len(playlist.video_urls)}] {item_url}")
                item_url.replace("https://", "").replace("http://", "")
                item_url[: item_url.index("/")]
                await self.download(
                    item_url,
                    quality=quality,
                    filename=filename,
                    path_folder=path_folder,
                    download_mode=download_mode,
                    filename_style=filename_style,
                    audio_format=audio_format,
                    youtube_video_codec=youtube_video_codec,
                )
            return
        if file is None:
            file = await self.get(
                url,
                quality=quality,
                download_mode=download_mode,
                filename_style=filename_style,
                audio_format=audio_format,
                youtube_video_codec=youtube_video_codec,
            )
        if filename is None:
            filename = file.filename
        if path_folder and path_folder[-1] != "/":
            path_folder += "/"
        if path_folder is None:
            path_folder = path.join(expanduser("~"), "Downloads")
        if not path.exists(path_folder):
            makedirs(path_folder)

        def shorten(s: str, additional_len: int = 0) -> str:
            columns, _ = get_terminal_size()
            free_columns = columns - additional_len
            return s[: free_columns - 6] + "..." if len(s) + 3 > free_columns else s

        async with ClientSession(headers=self.headers) as session:
            async with aopen(path.join(path_folder, filename), "wb") as f:
                try:
                    progress_chars = ["⢎⡰", "⢎⡡", "⢎⡑", "⢎⠱", "⠎⡱", "⢊⡱", "⢌⡱", "⢆⡱"]
                    progress_index = 0
                    total_size = 0
                    start_time = time()
                    last_update = 0
                    last_speed_update = 0
                    downloaded_since_last = 0
                    print(f"\033[97m{filename}\033[0m", flush=True)
                    max_print_length, _ = get_terminal_size()
                    async with session.get(file.tunnel) as response:
                        result_path = path.join(path_folder, f'"{filename}"')
                        while True:
                            chunk = await response.content.read(1024 * 1024)
                            if not chunk:
                                break
                            await f.write(chunk)
                            total_size += len(chunk)
                            downloaded_since_last += len(chunk)
                            if time() - last_update > 0.2:
                                progress_index += 1
                                if progress_index > len(progress_chars) - 1:
                                    progress_index = 0
                                if last_speed_update < time() - 1:
                                    last_speed_update = time()
                                    speed = downloaded_since_last / (
                                        time() - last_update
                                    )
                                    speed_display = (
                                        f"{round(speed / 1024 / 1024, 2)}Mb/s"
                                        if speed >= 0.92 * 1024 * 1024
                                        else f"{round(speed / 1024, 2)}Kb/s"
                                    )
                                downloaded_since_last = 0
                                last_update = time()
                                info = f"[{round(total_size / 1024 / 1024, 2)}Mb \u2015 {speed_display}] {progress_chars[progress_index]}"
                                max_print_length, _ = get_terminal_size()
                                max_print_length -= 3
                                print_line = shorten(
                                    result_path, additional_len=len(info)
                                )
                                print(
                                    "\r" + print_line,
                                    " "
                                    * (max_print_length - len(print_line + " " + info)),
                                    f"\033[97m{info[:-2]}\033[94m{info[-2:]}\033[0m",
                                    end="",
                                )
                                self.download_callback(
                                    total_size=total_size,
                                    filename=filename,
                                    path_folder=path_folder,
                                    start_time=start_time,
                                    speed_display=speed,
                                )
                    elapsed_time = time() - start_time
                    info = f"[{round(total_size / 1024 / 1024, 2)}Mb \u2015 {round(elapsed_time, 2)}s] \u2713"
                    print_line = shorten(result_path, additional_len=len(info))
                    if total_size < 1024:
                        instance = await self.get_instance()
                        self.skipped_instances += [instance]
                        print(tl("ZERO_BYTE_FILE").format(instance=instance))
                        if len(self.skipped_instances) > 1 and self.skipped_instances[-1] == self.skipped_instances[-2]:
                            print(tl("ZERO_BYTE_ALL"))
                            return
                        return await download(
                            url,
                            quality,
                            filename,
                            path_folder,
                            download_mode,
                            filename_style,
                            audio_format,
                            youtube_video_codec,
                            playlist,
                            file,
                            show,
                            play,
                        )
                    print(
                        "\r",
                        print_line
                        + " " * (max_print_length - len(print_line + " " + info)),
                        f"\033[97m{info[:-1]}\033[92m{info[-1:]}\033[0m",
                    )
                    if play:
                        if platform == "win32":
                            from os import startfile

                            startfile(path.join(path_folder, filename))
                        elif platform == "darwin":
                            srun(["open", path.join(path_folder, filename)])
                        else:
                            srun(["xdg-open", path.join(path_folder, filename)])
                    if show:
                        if platform == "win32":
                            srun(
                                [
                                    "explorer",
                                    "/select,",
                                    path.join(path_folder, filename),
                                ]
                            )
                        elif platform == "darwin":
                            srun(["open", "-R", path.join(path_folder, filename)])
                        else:
                            srun(
                                [
                                    "xdg-open",
                                    path.dirname(path.join(path_folder, filename)),
                                ]
                            )
                    return path.join(path_folder, filename)
                except KeyboardInterrupt:
                    return


Pybalt = Cobalt
cobalt = Cobalt()
download = cobalt.download
get = cobalt.get
