from aiohttp import ClientSession
from dotenv import load_dotenv
from os import getenv
from typing import List, Dict, Union, Unpack, TypedDict, Literal, LiteralString, Self
from .misc import Translator
from .client import RequestClient
from .constants import (
    FALLBACK_INSTANCE,
    FALLBACK_INSTANCE_API_KEY,
    DEFAULT_UA,
    DEFAULT_TIMEOUT,
)
from . import exceptions
from time import time
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


class Tunnel:
    url: str
    instance: "Instance" = None
    tunnel_id: str = None
    exp: int = None
    sig: str = None
    iv: str = None
    sec: str = None

    def __init__(self, url: str, instance: "Instance" = None):
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

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self.tunnel_id}"
            + f", expires in {int(self.exp) - int(time())} seconds)"
            if self.exp and self.exp.isdigit()
            else ")"
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
            raise exceptions.FetchError("Failed to get instance data")
        _cobalt = data.get("cobalt", None)
        if isinstance(_cobalt, dict):
            self.version = _cobalt.get("version", None)
            self.url = _cobalt.get("url", None)
            self.start_time = _cobalt.get("start_time", None)
            self.duration_limit = _cobalt.get("duration_limit", None)
            self.services = _cobalt.get("services", None)
        return self

    async def get_tunnel(self, **body: Unpack[_CobaltBodyOptions]):
        response = await self.parent.post(self.url, data=body)
        if not isinstance(response, dict):
            if "<title>Just a moment...</title>" in response:
                raise exceptions.FailedToGetTunnel(
                    f"{self.url}: Cloudflare is blocking requests"
                )
            elif ">Sorry, you have been blocked</h1>" in response:
                raise exceptions.FailedToGetTunnel(
                    f"{self.url}: Site owner set that cloudflare is blocking your requests"
                )
            raise exceptions.FailedToGetTunnel(
                f"{self.url}: Reponse is not a dict: {response}"
            )
        if response.get("status", None) != "tunnel":
            raise exceptions.FailedToGetTunnel(
                f'{self.url}: Failed to get tunnel: {response.get("error", dict()).get("code", None)}'
            )
        if "url" not in response:
            raise exceptions.NoUrlInTunnelResponse(
                f"{self.url}: No url found in tunnel response: {response}"
            )
        tunnel = Tunnel(response["url"], instance=self)
        return tunnel

    def __repr__(self):
        return f"{self.__class__.__name__}({self.url}, {self.version if self.version else 'unknown'}, {len(self.services) if self.services else 0} services)"


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
        self.instance = Instance(
            url=params.get("instance", getenv("COBALT_INSTANCE", FALLBACK_INSTANCE)),
            parent=self,
        )
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

    async def fetch_instances(self) -> List[Instance]:
        try:
            instances = await self.get(
                "https://instances.cobalt.best/api/instances.json"
            )
            if not isinstance(instances, list):
                raise exceptions.FetchError("Failed to fetch instances")
            return [Instance(parent=self, **instance) for instance in instances]
        except Exception as exc:
            raise exceptions.FetchError(f"Failed to fetch instances: {exc}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.request_client.session and not self.request_client.session.closed:
            await self.request_client.session.close()

    def __setattr__(self, name, value):
        if self.request_client and name in self.request_client.__dict__:
            self.request_client.__dict__[name] = value
        if isinstance(self.instance, Instance) and name in self.instance.__dict__:
            self.instance.__dict__[name] = value
        self.__dict__[name] = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__})"


class Downloader:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


load_dotenv()
