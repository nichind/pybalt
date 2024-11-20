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
                f"pybalt {last_version} is avaliable (current: {current_version}). Update with pip install pyeasypay -U"
            )
            return False
    except PackageNotFoundError:
        print("pybalt is not installed. Running from dev?")
    except Exception as e:
        print(f"Failed to check for updates: {e}")
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
        self.cobalt = cobalt if cobalt else Cobalt()
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
        Creates a new Cobalt object.

        Parameters:
        - api_instance (str, optional): The URL of the Cobalt API instance to use. Defaults to https://dwnld.nichind.dev.
        - api_key (str, optional): The API key to use for the Cobalt API instance. Defaults to "".
        - headers (dict, optional): The headers to use for requests to the Cobalt API instance. Defaults to a dictionary with Accept, Content-Type, and Authorization headers.

        Environment variables:
        - COBALT_API_URL: The URL of the Cobalt API instance to use.
        - COBALT_API_KEY: The API key to use for the Cobalt API instance.
        - COBALT_USER_AGENT: The User-Agent header to use for requests to the Cobalt API instance. Defaults to "pybalt/python".
        """
        load_dotenv()
        if api_instance is None:
            if getenv("COBALT_API_URL"):
                api_instance = getenv("COBALT_API_URL")
        if api_key is None:
            if getenv("COBALT_API_KEY"):
                api_key = getenv("COBALT_API_KEY")
        self.api_instance = (
            f"""{'https://' if "http" not in api_instance else ""}{api_instance}"""
            if api_instance
            else None
        )
        self.api_key = api_key if api_key else ""
        if not self.api_instance:
            print(
                "Couldn't find cobalt instance url. Your experience may/will be limited. Please set COBALT_API_URL environment variable or pass it as an argument (-i 'url') / constuctor (defers on what version you use, cli or as module)."
            )
            self.api_instance = "https://dwnld.nichind.dev"
        if self.api_instance == "https://dwnld.nichind.dev" and not self.api_key:
            self.api_key = "b05007aa-bb63-4267-a66e-78f8e10bf9bf"
        self.headers = headers
        if self.headers is None:
            self.headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Api-Key {self.api_key}" if self.api_key else "",
            }
        if "User-Agent" not in self.headers.keys():
            self.headers["User-Agent"] = (
                getenv("COBALT_USER_AGENT")
                if getenv("COBALT_USER_AGENT")
                else "pybalt/python"
            )
        if self.headers["Authorization"] == "":
            del self.headers["Authorization"]
        self.skipped_instances = []

    async def get_instance(self):
        """
        Finds a good instance of Cobalt API and changes the API instance of this object to it.

        It first gets a list of all instances, then filters out the ones with low trust or old version.
        Then it filters out the ones with too many dead services.
        It then picks the one with highest score and checks if it is already in the list of skipped instances.
        If it is, it picks the next one.
        """
        headers = self.headers
        headers["User-Agent"] = (
            "https://github.com/nichind/pybalt - Cobalt CLI & Python module. (aiohttp Client)"
        )
        async with ClientSession(headers=headers) as cs:
            async with cs.get(
                "https://instances.cobalt.best/api/instances.json"
            ) as resp:
                instances: list = await resp.json()
                good_instances = []
                for instance in instances:
                    dead_services = 0
                    if (
                        int(instance["version"].split(".")[0]) < 10
                        or instance["trust"] != 1
                    ):
                        continue
                    for service, status in instance["services"].items():
                        if not status:
                            dead_services += 1
                    if dead_services > 7:
                        continue
                    good_instances.append(instance)
                while True:
                    print(f"Found {len(good_instances)} good instances.")
                    good_instances.sort(
                        key=lambda instance: instance["score"], reverse=True
                    )
                    try:
                        async with cs.get(
                            good_instances[0]["protocol"]
                            + "://"
                            + good_instances[0]["api"]
                        ) as resp:
                            json = await resp.json()
                            if json["cobalt"]["url"] in self.skipped_instances:
                                raise exceptions.BadInstance()
                            self.api_instance = json["cobalt"]["url"]
                            break
                    except Exception:
                        good_instances.pop(0)
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
                }
                if audio_format:
                    json["audioFormat"] = audio_format
                # print(json)
                async with cs.post(self.api_instance, json=json) as resp:
                    json = await resp.json()
                    if "error" in json:
                        match json["error"]["code"].split(".")[2]:
                            case "link":
                                raise exceptions.LinkError(
                                    f'{url} is invalid - {json["error"]["code"]}'
                                )
                            case "content":
                                raise exceptions.ContentError(
                                    f'cannot get content of {url} - {json["error"]["code"]}'
                                )
                            case "invalid_body":
                                raise exceptions.InvalidBody(
                                    f'Request body is invalid - {json["error"]["code"]}'
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
                                    f'Authentication failed - {json["error"]["code"]}'
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
                                    youtube_video_codec,
                                )
                            case "fetch":
                                self.skipped_instances.append(self.api_instance)
                                print(
                                    f'Fetch {url if len(url) < 40 else url[:40] + "..."} using {self.api_instance} failed, trying next instance...\r',
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
                    f"Cannot reach instance {self.api_instance}"
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
        if playlist or len(findall("[&?]list=([^&]+)", url)) > 0:
            if type(playlist) is str:
                url = playlist

            from pytube import Playlist

            playlist = Playlist(url)
            for i, item_url in enumerate(playlist.video_urls):
                if url.split(".")[0].endswith("music"):
                    item_url.replace("www", "music")
                print(f"[{i + 1}/{len(playlist.video_urls)}] {item_url}")
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
                    async with session.get(file.tunnel) as response:
                        print(f"\033[97m{filename}\033[0m", flush=True)
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
                    elapsed_time = time() - start_time
                    info = f"[{round(total_size / 1024 / 1024, 2)}Mb \u2015 {round(elapsed_time, 2)}s] \u2713"
                    print_line = shorten(result_path, additional_len=len(info))
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
