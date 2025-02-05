from aiohttp import ClientSession
from dotenv import load_dotenv
from os import getenv
from typing import (
    List,
    Dict,
    Union,
    Unpack,
    TypedDict,
    Literal,
    LiteralString,
    Any,
    Coroutine,
    Callable,
    AsyncGenerator,
)
from .misc import Translator, lprint, check_updates, cfg_value, StatusParent
from .client import RequestClient, _DownloadOptions
from .constants import (
    FALLBACK_INSTANCE,
    FALLBACK_INSTANCE_API_KEY,
    DEFAULT_UA,
    DEFAULT_TIMEOUT,
)
from . import exceptions
from time import time
from pathlib import Path
from .remux import remux
from sys import platform
from subprocess import run as srun
import re


class _CobaltParameters(TypedDict, total=False):
    instance: str
    api_key: str
    user_agent: str
    timeout: int
    translator: Translator = Translator()
    proxy: str
    session: ClientSession
    headers: Dict[str, str]
    debug: bool
    updates: bool


class _CobaltBodyOptions(TypedDict, total=False):
    url: str
    videoQuality: Literal[
        "max", "144", "240", "360", "480", "720", "1080", "1440", "2160", "4320"
    ]
    audioFormat: Literal["best", "mp3", "ogg", "wav", "opus"]
    audioBitrate: Literal["320", "256", "128", "96", "64", "8"]
    filenameStyle: Literal["classic", "pretty", "basic", "nerdy"]
    downloadMode: Literal["auto", "audio", "mute"]
    youtubeVideoCodec: Literal["h264", "av1", "vp9"]
    youtubeDubLang: LiteralString
    alwaysProxy: bool
    disableMetadata: bool
    tiktokFullAudio: bool
    tiktokH265: bool
    twitterGif: bool
    youtubeHLS: bool


class _CobaltDownloadOptions(TypedDict, total=False):
    url: str
    videoQuality: Literal[
        "max", "144", "240", "360", "480", "720", "1080", "1440", "2160", "4320"
    ] = "max"
    audioFormat: Literal["best", "mp3", "ogg", "wav", "opus"] = "best"
    audioBitrate: Literal["320", "256", "128", "96", "64", "8"] = "best"
    filenameStyle: Literal["classic", "pretty", "basic", "nerdy"] = "classic"
    downloadMode: Literal["auto", "audio", "mute"] = "auto"
    youtubeVideoCodec: Literal["h264", "av1", "vp9"] = "h264"
    youtubeDubLang: LiteralString = ""
    alwaysProxy: bool = False
    disableMetadata: bool = False
    tiktokFullAudio: bool = False
    tiktokH265: bool = False
    twitterGif: bool = False
    youtubeHLS: bool = False
    folder_path: str
    filename: str
    status_callback: Callable | Coroutine
    done_callback: Callable | Coroutine
    status_parent: str
    headers: Dict[str, str]
    timeout: int
    remux: bool
    show: bool
    open: bool


class Tunnel:
    url: str
    instance: "Instance" = None
    tunnel_id: str = None
    exp: int = None
    sig: str = None
    iv: str = None
    sec: str = None
    filename: str = None
    extension: str = None

    def __init__(
        self,
        data: dict,
        instance: "Instance" = None,
        auto_download: Unpack[_CobaltDownloadOptions] = None,
    ):
        url = data.get("url", None)
        if not url:
            raise exceptions.NoUrlInTunnelResponse(
                "No url found in response data while creating tunnel instance"
            )
        self.url = url
        self.instance = instance
        self.tunnel_id = (
            re.search(r"id=([^&]+)", url).group(1) if "id=" in url else None
        )
        self.exp = (
            re.search(r"exp=([^&]+)", url).group(1)[:-3] if "exp=" in url else None
        )
        self.sig = re.search(r"sig=([^&]+)", url).group(1) if "sig=" in url else None
        self.iv = re.search(r"iv=([^&]+)", url).group(1) if "iv=" in url else None
        self.sec = re.search(r"sec=([^&]+)", url).group(1) if "sec=" in url else None
        self.filename = data.get("filename", None)
        self.extension = self.filename.split(".")[-1]

    async def download(
        self, _remux: bool = False, **body: Unpack[_DownloadOptions]
    ) -> Path:
        if "url" not in body:
            body["url"] = self.url
        if "filename" not in body:
            body["filename"] = self.filename
        file_path = await self.instance.parent.request_client.download_from_url(**body)
        if _remux:
            file_path = remux(file_path)
        if body.get("open", False):
            if platform == "win32":
                from os import startfile

                startfile(file_path)
            elif platform == "darwin":
                srun(["open", file_path])
            else:
                srun(["xdg-open", file_path])
        if body.get("show", False):
            if platform == "win32":
                srun(
                    [
                        "explorer",
                        "/select,",
                        file_path,
                    ]
                )
            elif platform == "darwin":
                srun(["open", "-R", file_path])
            else:
                srun(
                    [
                        "xdg-open",
                        file_path,
                    ]
                )
        return file_path

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({(str(self.tunnel_id) + ', ' if self.tunnel_id else '') + self.url[:24] + '...'}"
            + (
                f", expires in {int(self.exp) - int(time())} seconds)"
                if self.exp and self.exp.isdigit()
                else ")"
            )
        )


class Instance:
    version: str = None
    url: str = None
    start_time: int = None
    duration_limit: int = None
    services: List[str] = None
    git: Dict[str, str] = None
    dump: Dict = None
    parent: "Cobalt" = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.dump = kwargs
        if not self.url and kwargs.get("api", None):
            self.url = kwargs.get("api")
        if "http" not in self.url:
            self.url = f"https://{self.url}"
        if not self.parent:
            self.parent = Cobalt()

    async def get_instance_info(self, url: str = None):
        data = await self.parent.get(url or self.url)
        if not isinstance(data, dict):
            raise exceptions.FetchError(f"{self.url}: Failed to get instance data")
        _cobalt = data.get("cobalt", None)
        if isinstance(_cobalt, dict):
            self.version = _cobalt.get("version", None)
            self.url = _cobalt.get("url", None)
            self.start_time = _cobalt.get("start_time", None)
            self.duration_limit = _cobalt.get("duration_limit", None)
            self.services = _cobalt.get("services", None)
        return self

    async def get_tunnel(
        self, **body: Unpack[_CobaltBodyOptions]
    ) -> AsyncGenerator[Tunnel, None]:
        if not self.version == "unknown":
            try:
                await self.get_instance_info()
            except Exception:
                ...
        if len(re.findall("[&?]list=([^&]+)", body.get("url", ""))) > 0:
            from pytube import Playlist

            playlist = Playlist(body.get("url"))
            for i, item_url in enumerate(playlist.video_urls):
                if "music." in item_url:
                    item_url = item_url.replace("www", "music")
                body["url"] = item_url
                async for _tunnel in self.get_tunnel(**body):
                    yield _tunnel
        response = await self.parent.post(self.url, data=body)  # Pray for success!
        if not isinstance(response, dict):  # If your prayers not fulfilled
            if "<title>Just a moment...</title>" in response:
                raise exceptions.FailedToGetTunnel(
                    f"{self.url}: Cloudflare is blocking requests"
                )
            elif ">Sorry, you have been blocked</h1>" in response:
                raise exceptions.FailedToGetTunnel(
                    f"{self.url}: Site owner set that cloudflare is blocking your requests"
                )
            elif "ry again" in response:
                raise exceptions.FailedToGetTunnel(
                    f"{self.url}: Cloudflare failed to tunnel connection, try again later"
                )
            raise exceptions.FailedToGetTunnel(
                f"{self.url}: Reponse is not a dict: {response}"
            )
        if response.get("status", None) in ["error"]:
            raise exceptions.FailedToGetTunnel(
                f'{self.url}: {response.get("error", dict()).get("code", None)}'
            )
        if "url" not in response:
            raise exceptions.NoUrlInTunnelResponse(
                f"{self.url}: No url found in tunnel response: {response}"
            )
        yield Tunnel(response, instance=self)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.url}, {self.version if self.version else 'unknown'}, {len(self.services) if self.services else 0} services)"

    def __aiter__(self):
        return self


class Cobalt:
    instance: Union[Instance, str] = None
    fallback_instance: Union[Instance, str]
    api_key: str = None
    user_agent: str = None
    timeout: int = None
    translator: Translator = None
    proxy: str = None
    session: ClientSession = None
    headers: Dict[str, str] = None
    request_client: RequestClient = None
    solve_turnstile = True

    def __init__(self, **params: Unpack[_CobaltParameters]):
        self.__dict__.update(params)
        self.instances = []
        self.fallback_instance = Instance(
            url=FALLBACK_INSTANCE, api_key=FALLBACK_INSTANCE_API_KEY, parent=self
        )
        self.proxy = params.get("proxy", getenv("COBALT_PROXY", None))
        self.timeout = params.get("timeout", getenv("COBALT_TIMEOUT", DEFAULT_TIMEOUT))
        self.user_agent = params.get(
            "user_agent", getenv("COBALT_USER_AGENT", DEFAULT_UA)
        )
        self.api_key = params.get(
            "api_key", getenv("COBALT_API_KEY", FALLBACK_INSTANCE_API_KEY)
        )
        self.headers = params.get(
            "headers",
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        self.request_client = RequestClient(
            api_key=self.api_key,
            session=self.session,
            headers=self.headers,
            timeout=self.timeout,
            proxy=self.proxy,
            user_agent=self.user_agent,
        )
        self.get = self.request_client.get
        self.post = self.request_client.post
        self.debug = (
            (
                lambda *args, **kwargs: lprint(
                    *[
                        ":gray:？ " + str(arg)
                        if not isinstance(arg, Exception)
                        else ":red::warning:  " + str(arg)
                        for arg in args
                    ],
                    **kwargs,
                )
            )
            if params.get("debug", getenv("COBALT_DEBUG", False))
            else lambda *args, **kwargs: ...
        )
        self.local_instance = Instance(
            url=getenv("COBALT_LOCAL_INSTANCE", "http://127.0.0.1:9000"),
            api_key=getenv("COBALT_LOCAL_INSTANCE_API_KEY", None),
            parent=self,
        )
        self.remux = remux
        if (
            "update" in params
            or int(cfg_value().get("update_check", 0)) + 60 * 60 * 3 < time()
        ):
            self.debug("Checking for updates...", end="\r")
            check_updates()
            cfg_value("update_check", str(int(time())))

    async def fetch_instances(self) -> List[Instance]:
        try:
            instances = await self.get(
                "https://instances.cobalt.best/api/instances.json"
            )
            if not isinstance(instances, list):
                raise exceptions.FetchError("Failed to fetch instances")
            self.instances = [
                Instance(parent=self, **instance) for instance in instances
            ] + [self.fallback_instance]
            try:
                self.debug("Fetching local instance info...", end="\r")
                await self.local_instance.get_instance_info()
                self.instances = [self.local_instance] + self.instances
            except Exception:
                self.debug("Didn't find local instance, skipping")
            self.debug(f"Fetched {len(self.instances)} instances")
            return self.instances
        except Exception as exc:
            self.debug(f"Failed to fetch instances: {exc}")
            self.instances = [self.fallback_instance]
            return self.instances

    async def get_tunnel(self, url: str, **body: Unpack[_CobaltBodyOptions]) -> Tunnel:
        tunnels = []
        for instance in await self.fetch_instances():
            try:
                async for tunnel in instance.get_tunnel(
                    url=url,
                    **{
                        key: value
                        for key, value in body.items()
                        if key in _CobaltBodyOptions.__annotations__.keys()
                    },
                ):
                    tunnels += [tunnel]
                return tunnels if len(tunnels) > 1 else tunnels[0]
            except Exception as exc:
                self.debug(exc)
        raise exceptions.AllInstancesFailed(
            f"Failed to get tunnel of {url} using any of {len(self.instances)} instances. If this issue persists, you can host your own local instance, more on it here: https://github.com/imputnet/cobalt/blob/main/docs/run-an-instance.md"
        )

    async def download(
        self, url: Union[str, Tunnel], **body: Unpack[_CobaltDownloadOptions]
    ) -> Path | List[Path]:
        if isinstance(url, Tunnel):
            return await self.request_client.download_from_url(url=url, **body)
        for instance in await self.fetch_instances():
            try:
                results = []
                self.debug(
                    f"Trying to download {url} using instance: {instance.url}", end="\r"
                )
                async for tunnel in instance.get_tunnel(
                    url=url,
                    **{
                        key: value
                        for key, value in body.items()
                        if key in _CobaltBodyOptions.__annotations__.keys()
                    },
                ):
                    self.debug(
                        f"Tunnel created, instance: {instance.url}, tunnel url: {tunnel.url}"
                    )
                    results.append(
                        await tunnel.download(
                            _remux=body.get("remux", False),
                            **{
                                key: value
                                for key, value in body.items()
                                if key in _CobaltDownloadOptions.__annotations__.keys()
                            },
                        )
                    )
                return results if len(results) > 1 else results[0]
            except Exception as exc:
                self.debug(exc)
        raise exceptions.AllInstancesFailed(
            f"Failed to download {url} using any of {len(self.instances)} instances. If this issue persists, you can host your own local instance, more on it here: https://github.com/imputnet/cobalt/blob/main/docs/run-an-instance.md"
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.request_client.session and not self.request_client.session.closed:
            await self.request_client.session.close()

    def __setattr__(self, name: str, value: Any):
        if self.request_client and name in self.request_client.__dict__:
            self.request_client.__dict__[name] = value
        if isinstance(self.instance, Instance) and name in self.instance.__dict__:
            self.instance.__dict__[name] = value
        if isinstance(self.headers, dict):
            _ = ""
            for i, letter in enumerate(name):
                if _ == "" or name[i - 1] == "_":
                    _ += letter.upper()
                elif letter == "_":
                    _ += "-"
                else:
                    _ += letter
            if _ in self.headers:
                self.headers[_] = value
        self.__dict__[name] = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__})"


class Downloader:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


DefaultCobalt = Cobalt()
download = DefaultCobalt.download
get_tunnel = DefaultCobalt.get_tunnel


load_dotenv()
