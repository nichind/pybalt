from aiohttp import ClientSession
from dotenv import load_dotenv
from os import getenv
from typing import List, Dict, Union, Unpack, TypedDict
from .misc import Translator
from .client import RequestClient
from .constants import (
    FALLBACK_INSTANCE,
    FALLBACK_INSTANCE_API_KEY,
    DEFAULT_UA,
    DEFAULT_TIMEOUT,
)


class CobaltParameters:
    instance = getenv("COBALT_API_URL", FALLBACK_INSTANCE)
    api_key = getenv(
        "COBALT_API_KEY",
        FALLBACK_INSTANCE_API_KEY if instance == FALLBACK_INSTANCE else None,
    )
    user_agent = getenv("COBALT_USER_AGENT", DEFAULT_UA)
    timeout = getenv("COBALT_TIMEOUT", DEFAULT_TIMEOUT)
    translator = Translator()
    proxy = getenv("COBALT_PROXY", None)
    session = None
    headers = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)



class _CobaltBodyOptions(TypedDict, total=False):
    api_key: str


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
        if not self.url and kwargs.get("api", None):
            self.url = kwargs.get("api")
        if "http" not in self.url:
            self.url = f"https://{self.url}"
        if not self.parent:
            self.parent = Cobalt()

    async def get_instance_info(self, url: str = None):
        data = await self.parent.get(url or self.url)
        if not isinstance(data, dict):
            raise "Failed to get instance data"
        _cobalt = data.get("cobalt", None)
        if isinstance(_cobalt, dict):
            self.version = _cobalt.get("version", None)
            self.url = _cobalt.get("url", None)
            self.start_time = _cobalt.get("start_time", None)
            self.duration_limit = _cobalt.get("duration_limit", None)
            self.services = _cobalt.get("services", None)
        return self

    async def get_tunnel(self, url: str = None, **options: Unpack[_CobaltBodyOptions]):

    def __repr__(self):
        return f"{self.__class__.__name__}({self.url}, {self.version if self.version else 'unknown'}, {len(self.services) if self.services else 0} services)"    


class Cobalt:
    instance: Union[Instance, str] = None
    api_key: str = None
    user_agent: str = None
    timeout: int = None
    translator: Translator = None
    proxy: str = None
    session: ClientSession = None
    headers: Dict[str, str] = None
    request_client: RequestClient = None

    def __init__(self, params: CobaltParameters = CobaltParameters, **kwargs):
        self.instance = params.instance
        self.api_key = params.api_key
        self.user_agent = params.user_agent
        self.timeout = params.timeout
        self.translator = params.translator
        self.proxy = params.proxy
        self.session = params.session
        self.headers = params.headers
        self.request_client = RequestClient(
            api_key=self.api_key,
            session=self.session,
            headers=self.headers,
            timeout=self.timeout,
            proxy=self.proxy,
        )
        self.get = self.request_client.get
        self.post = self.request_client.post
        self.__dict__.update(params.__dict__)
        self.__dict__.update(kwargs)

    async def fetch_instances(self) -> List[Instance]:
        instances = await self.get("https://instances.cobalt.best/api/instances.json")
        if not isinstance(instances, list):
            raise "Failed to fetch instances"
        return [
            Instance(parent=self, **instance, dump=instance) for instance in instances
        ]

    def __setattr__(self, name, value):
        if self.request_client and name in self.request_client.__dict__:
            self.request_client.__dict__[name] = value
        self.__dict__[name] = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__})"


load_dotenv()
