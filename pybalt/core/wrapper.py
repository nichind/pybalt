from .config import Config
from .client import HttpClient
from .local import LocalInstance
from .remux import remux
from typing import TypedDict, Optional, List, Dict, Union, Literal, Unpack
import logging


logger = logging.getLogger(__name__)


class CobaltRequestParams(TypedDict, total=False):
    """Type definition for Cobalt API request parameters."""

    url: str
    videoQuality: Literal[
        "144", "240", "360", "480", "720", "1080", "1440", "2160", "4320", "max"
    ]
    audioFormat: Literal["best", "mp3", "ogg", "wav", "opus"]
    audioBitrate: Literal["320", "256", "128", "96", "64", "8"]
    filenameStyle: Literal["classic", "pretty", "basic", "nerdy"]
    downloadMode: Literal["auto", "audio", "mute"]
    youtubeVideoCodec: Literal["h264", "av1", "vp9"]
    youtubeDubLang: str
    alwaysProxy: bool
    disableMetadata: bool
    tiktokFullAudio: bool
    tiktokH265: bool
    twitterGif: bool
    youtubeHLS: bool


class CobaltResponse(TypedDict):
    """Base type for Cobalt API responses."""

    status: Literal["error", "picker", "redirect", "tunnel"]


class CobaltErrorContext(TypedDict, total=False):
    """Context information for Cobalt API errors."""

    service: str
    limit: int


class CobaltError(TypedDict):
    """Error information from Cobalt API."""

    code: str
    context: Optional[CobaltErrorContext]


class CobaltErrorResponse(CobaltResponse):
    """Cobalt API error response."""

    error: CobaltError


class CobaltTunnelResponse(CobaltResponse):
    """Cobalt API tunnel response."""

    url: str
    filename: str


class CobaltRedirectResponse(CobaltResponse):
    """Cobalt API redirect response."""

    url: str
    filename: str


class CobaltPickerItem(TypedDict, total=False):
    """Item in a Cobalt picker response."""

    type: Literal["photo", "video", "gif"]
    url: str
    thumb: Optional[str]


class CobaltPickerResponse(CobaltResponse):
    """Cobalt API picker response."""

    picker: List[CobaltPickerItem]
    audio: Optional[str]
    audioFilename: Optional[str]


class InstanceInfo(TypedDict, total=False):
    """Information about a Cobalt instance."""

    api: str
    frontend: str
    protocol: str
    score: int
    trust: int
    version: str
    branch: str
    commit: str
    cors: bool
    name: str
    nodomain: bool
    online: Dict[str, bool]
    services: Dict[str, Union[bool, str]]


class Instance:
    """Represents a Cobalt instance."""

    def __init__(
        self,
        info: Optional[InstanceInfo] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[Config] = None,
        client: Optional[HttpClient] = None,
        debug: bool = False,
    ):
        """
        Initialize a Cobalt instance.

        Args:
            info: Information about the instance
            url: URL of the instance (alternative to info)
            api_key: API key for authentication
            config: Configuration object
            client: HTTP client
            debug: Enable debug logging
        """
        self.config = config or Config()
        self.debug = debug or self.config.get("debug", False, "general")

        if self.debug:
            logger.setLevel(logging.DEBUG)
            if not logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)

        # Initialize from info or direct URL
        if info:
            self.info = info
            self.api_url = f"{info['protocol']}://{info['api']}"
        elif url:
            self.info = {"api": url}
            self.api_url = url if "://" in url else f"https://{url}"
        else:
            raise ValueError("Either info or url must be provided")

        # Get API key
        self.api_key = api_key

        # Initialize HTTP client
        self.client = client or HttpClient(config=self.config, debug=self.debug)

    def __repr__(self):
        """String representation of the instance."""
        return f"<Instance [url={self.api_url}, version={self.version}, score={self.score}]>"

    @property
    def version(self) -> Optional[str]:
        """Get the instance version."""
        return self.info.get("version")

    @property
    def score(self) -> int:
        """Get the instance score."""
        return self.info.get("score", 0)

    @property
    def trust(self) -> int:
        """Get the instance trust level."""
        return self.info.get("trust", 0)

    @property
    def online(self) -> bool:
        """Check if the instance is online."""
        online_info = self.info.get("online", {})
        return online_info.get("api", False)

    @property
    def services(self) -> Dict[str, Union[bool, str]]:
        """Get the services supported by the instance."""
        return self.info.get("services", {})

    def service_works(self, service: str) -> bool:
        """
        Check if a specific service works on this instance.

        Args:
            service: Service name to check

        Returns:
            True if the service works, False otherwise
        """
        if not self.online:
            return False

        service_status = self.services.get(service)
        if service_status is True:
            return True
        elif isinstance(service_status, str) and not service_status.startswith(
            ("error.", "i couldn't", "it seems")
        ):
            return True
        return False

    def get_working_services(self) -> List[str]:
        """
        Get a list of working services on this instance.

        Returns:
            List of service names that work
        """
        return [service for service in self.services if self.service_works(service)]

    async def get_info(self) -> Optional[InstanceInfo]:
        """
        Get information about the instance.

        Returns:
            InstanceInfo dictionary or None if not available
        """
        if self.info:
            return self.info

        # Fetch instance info from the API
        response = await self.client.get(self.api_url)

        if response.status >= 400:
            logger.error(f"Failed to fetch instance info: {response.status}")
            return None

        # Parse the response JSON
        self.info = await response.json()
        return self.info


class InstanceManager:
    def __init__(
        self,
        debug: bool = None,
        config: Config = None,
        client: HttpClient = HttpClient(),
    ):
        self.config = config or Config()
        self.debug = debug or self.config.get("debug", False, "general")
        if self.debug:
            import logging

            logger = logging.getLogger(__name__)
            logger.setLevel(logging.DEBUG)

            # Create console handler if not already present
            if not logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
        self.client = client
        self.local_instance = LocalInstance(config=self.config)
        self.user_instances = [
            Instance(
                url=user_instance.get("url"),
                api_key=user_instance.get("api_key", None),
                config=self.config,
                client=self.client,
                debug=self.debug,
            )
            for user_instance in self.config.get_user_instances()
        ]
        self.fetched_instances = []
        self.fallback_instance = Instance(
            url=self.config.get(
                "fallback_instance", "https://dwnld.nichind.dev", "instances"
            ),
            api_key=self.config.get("fallback_instance_api_key", None, "instances"),
            config=self.config,
            client=self.client,
            debug=self.debug,
        )

    @property
    def all_instances(self) -> List[Instance]:
        return (
            [self.local_instance]
            if self.local_instance.get_instance_status().get("running", False)
            else []
            + self.user_instances
            + self.fetched_instances
            + [self.fallback_instance]
        )

    async def fetch_instances(
        self, min_version: str = None, min_score: int = 0, filter_online: bool = True
    ) -> List[Instance]:
        """
        Get processed Cobalt instances from the public instance list api.

        Args:
            min_version: Minimum version required
            min_score: Minimum score required
            filter_online: Filter to only online instances

        Returns:
            List of processed Instance objects
        """
        logger.debug("Getting instances with params:")
        raw_instances = await self.client.get(
            self.config.get(
                "instance_list_api",
                "https://instances.cobalt.best/api/instances.json",
                "instances",
            )
        )

        if raw_instances.status >= 400:
            logger.error(f"Failed to fetch instances: {raw_instances.status}")
            return []

        # Parse the raw instances
        instances_data = await raw_instances.json()

        if self.debug:
            logger.debug(f"Received {len(instances_data)} raw instances")

        # Get user-defined instances with API keys
        user_instances = self.config.get_user_instances()
        user_instances_dict = {
            instance["url"]: instance["api_key"] for instance in user_instances
        }

        # Process instances
        processed_instances = []
        seen_urls = set()

        for instance_info in instances_data:
            # Skip if no API URL
            if "api" not in instance_info:
                continue

            # Create full API URL
            api_url = (
                f"{instance_info.get('protocol', 'https')}://{instance_info['api']}"
            )

            # Skip duplicates
            if api_url in seen_urls:
                continue
            seen_urls.add(api_url)

            # Skip offline instances if filter is enabled
            if filter_online and not instance_info.get("online", {}).get("api", False):
                continue

            # Skip instances with low score
            if instance_info.get("score", 0) < min_score:
                continue

            # Skip instances with version lower than minimum
            if (
                min_version
                and instance_info.get("version")
                and instance_info.get("version") < min_version
            ):
                continue

            # Find matching API key from user instances
            api_key = None
            for user_url, user_key in user_instances_dict.items():
                if instance_info["api"] in user_url or user_url in instance_info["api"]:
                    api_key = user_key
                    break

            # Create Instance object
            instance = Instance(
                info=instance_info,
                api_key=api_key,
                config=self.config,
                client=self.client,
                debug=self.debug,
            )
            processed_instances.append(instance)

        # Sort by score (highest first)
        processed_instances.sort(key=lambda x: x.score, reverse=True)

        self.fetched_instances = processed_instances
        return processed_instances

    async def get_instances(self) -> List[Instance]:
        """
        Get a list of ALL AVALIABLE Cobalt instances INCLUDING local, user_instances from the config, fetched instances from the list api and the fallback one.

        Returns:
            List of Instance objects
        """
        if not self.fetched_instances:
            await self.fetch_instances()

        self.local_instance = LocalInstance(config=self.config)
        self.user_instances = [
            Instance(
                url=user_instance.get("url"),
                api_key=user_instance.get("api_key", None),
                config=self.config,
                client=self.client,
                debug=self.debug,
            )
            for user_instance in self.config.get_user_instances()
        ]
        self.fallback_instance = Instance(
            url=self.config.get(
                "fallback_instance", "https://dwnld.nichind.dev", "instances"
            ),
            api_key=self.config.get("fallback_instance_api_key", None, "instances"),
            config=self.config,
            client=self.client,
            debug=self.debug,
        )

        return self.all_instances

    async def first_tunnel(
        self, url: str, **params: Unpack[CobaltRequestParams]
    ) -> Union[
        CobaltTunnelResponse,
        CobaltRedirectResponse,
        CobaltPickerResponse,
        CobaltErrorResponse,
    ]:
        """
        Sends a POST request to the all available instances and returns the first successful response.

        Args:
            url: URL to process
            params: Request parameters

        Returns:
            Response from the first successful instance
        """
        instances = await self.get_instances()
        print(f"Instances: {instances}")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        return await self.client.bulk_post(
            [
                {"url": instance.api_url, "api_key": instance.api_key}
                for instance in instances
            ],
            json={
                "url": url,
                **params,
            },
            headers=headers,
        )
