from .config import Config
from .client import HttpClient
from .local import LocalInstance
from .remux import Remuxer
from .logging_utils import get_logger
from typing import (
    TypedDict,
    Optional,
    List,
    Dict,
    Union,
    Literal,
    Unpack,
    AsyncGenerator,
    Tuple,
    Set,
)
from pathlib import Path
import logging
import asyncio
from ipaddress import ip_address
import os


logger = get_logger(__name__)


class CobaltRequestParams(TypedDict, total=False):
    """Type definition for Cobalt API request parameters."""

    url: str
    videoQuality: Literal["144", "240", "360", "480", "720", "1080", "1440", "2160", "4320", "max"]
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
    ignoredInstances: Optional[List[str]]


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
                formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)

        # Initialize from info or direct URL
        if info:
            self.info = info
            self.api_url = f"{info['protocol']}://{info['api']}"
        elif url:
            self.info = {"api": url}

            # Check if URL already has a protocol
            if "://" in url:
                self.api_url = url
            else:
                # Extract host for IP checking
                host = url.split("/")[0].split(":")[0]  # Remove any path, query or port

                # Check if host is an IP address
                try:
                    ip_address(host)
                    self.api_url = f"http://{url}"
                except (ValueError, ImportError):
                    self.api_url = f"https://{url}"
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
        elif isinstance(service_status, str) and not service_status.startswith(("error.", "i couldn't", "it seems")):
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

    @property
    def instance_id(self) -> str:
        """
        Get a unique identifier for this instance.

        Returns:
            A string that uniquely identifies this instance
        """
        return self.api_url


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
            global logger
            logger = get_logger(__name__, debug=True)

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
            url=self.config.get("fallback_instance", "https://dwnld.nichind.dev", "instances"),
            api_key=self.config.get("fallback_instance_api_key", None, "instances"),
            config=self.config,
            client=self.client,
            debug=self.debug,
        )

    @property
    def all_instances(self) -> List[Instance]:
        """_summary_

        Returns:
            List[Instance]: _description_
        """
        return (
            ([self.local_instance] if self.local_instance.get_instance_status().get("running", False) else [])
            + self.user_instances
            + self.fetched_instances
            + [self.fallback_instance]
        )

    async def fetch_instances(self, min_version: str = None, min_score: int = 0, filter_online: bool = True) -> List[Instance]:
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

        logger.debug(f"Received {len(instances_data)} raw instances")

        # Get user-defined instances with API keys
        user_instances = self.config.get_user_instances()
        user_instances_dict = {instance["url"]: instance["api_key"] for instance in user_instances}

        # Process instances
        processed_instances = []
        seen_urls = set()

        for instance_info in instances_data:
            # Skip if no API URL
            if "api" not in instance_info:
                continue

            # Create full API URL
            api_url = f"{instance_info.get('protocol', 'https')}://{instance_info['api']}"

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
            if min_version and instance_info.get("version") and instance_info.get("version") < min_version:
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

    async def get_instances(self, ignored_instances: Optional[List[str]] = None) -> List[Instance]:
        """
        Get a list of ALL available Cobalt instances including local, user_instances from the config,
        fetched instances from the list api and the fallback one, excluding any ignored instances.

        Args:
            ignored_instances: List of instance URLs to ignore

        Returns:
            List of Instance objects
        """
        # if not self.fetched_instances:
        #     await self.fetch_instances()

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
            url=self.config.get("fallback_instance", "https://dwnld.nichind.dev", "instances"),
            api_key=self.config.get("fallback_instance_api_key", None, "instances"),
            config=self.config,
            client=self.client,
            debug=self.debug,
        )

        # Filter out ignored instances if specified
        all_instances = self.all_instances
        if ignored_instances:
            all_instances = [
                instance
                for instance in all_instances
                if instance.api_url.replace("https://", "").replace("http://", "") not in ignored_instances
            ]

        logger.debug(str(all_instances))
        return all_instances

    async def first_tunnel_generator(
        self,
        urls: List[str],
        only_first: bool = False,
        close: bool = True,
        ignored_instances: Optional[List[str]] = None,
        force_instance_origin: bool = True,
        **params: Unpack[CobaltRequestParams],
    ) -> AsyncGenerator[
        Union[
            CobaltTunnelResponse,
            CobaltRedirectResponse,
            CobaltPickerResponse,
            CobaltErrorResponse,
        ],
        None,
    ]:
        # Remove ignoredInstances from params if present and merge with directly passed ignored_instances
        params_ignored = params.pop("ignoredInstances", None) or []
        all_ignored = list(set(params_ignored + (ignored_instances or [])))

        # Get instances, filtering out ignored ones
        instances = await self.get_instances(all_ignored)

        if not instances:
            logger.warning("No available instances after filtering out ignored instances")
            yield CobaltErrorResponse(status="error", error=CobaltError(code="NO_INSTANCES_AVAILABLE", context=None))
            return

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        for url in urls:
            try:
                response = await self.client.bulk_post(
                    [{"url": instance.api_url, "api_key": instance.api_key} for instance in instances],
                    data={
                        "url": url.replace("\\", ""),
                        **params,
                    },
                    headers=headers,
                    close=close,
                )
                data = await response.json()
                # Add responding instance information to the response
                responding_instance = response.url.split("/")[2] if response.url else None
                if responding_instance:
                    if "instance_info" not in data:
                        data["instance_info"] = {}
                    if data['instance_info'].get("url", None) is None:
                        data["instance_info"]["url"] = responding_instance

                if data.get("status", "") == "tunnel":
                    # Handle URL in response that might be local
                    if data.get("url", None):
                        response_url = data.get("url")
                        # Check if URL is pointing to a local resource
                        if force_instance_origin or (
                            any(local_pattern in response_url.lower() for local_pattern in ["localhost", "127.0.0.1", "::1"])
                            or any(response_url.lower().startswith(f"http://{pattern}") for pattern in ["192.168.", "10.", "172.16."])
                        ):
                            # Get the instance that responded
                            instance_url = data["instance_info"]["url"]
                            if "http" not in instance_url:
                                instance_url = f"http://{instance_url}"
                            # Extract the base URL of the instance
                            instance_base = "/".join(instance_url.split("/")[:3])  # Get protocol and host part
                            # Only replace if not using a local instance intentionally
                            if not (self.local_instance and self.local_instance.api_url in instance_url):
                                path_part = "/" + "/".join(response_url.split("/")[3:]) if len(response_url.split("/")) > 3 else ""
                                data["url"] = f"{instance_base}{path_part}"
                                logger.debug(f"Replaced local URL {response_url} with {data['url']}")

                    yield CobaltTunnelResponse(**data)
                elif data.get("status", "") == "redirect":
                    yield CobaltRedirectResponse(**data)
                elif data.get("status", "") == "picker":
                    yield CobaltPickerResponse(**data)
                # elif data.get("status", "") == "error":
                #     yield CobaltErrorResponse(**data)
                if only_first:
                    break
            except Exception as e:
                logger.debug(f"Error processing URL {url}: {e}")

    async def first_tunnel(
        self, url: str, ignored_instances: Optional[List[str]] = None, **params: Unpack[CobaltRequestParams]
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
            ignored_instances: List of instance URLs to ignore
            params: Request parameters

        Returns:
            Response from the first successful instance
        """
        generator = self.first_tunnel_generator(urls=[url], only_first=True, ignored_instances=ignored_instances, **params)
        async for response in generator:
            return response

    async def download_generator(
        self,
        url: str = None,
        urls: List[str] = None,
        ignored_instances: Optional[List[str]] = None,
        only_path: bool = True,
        remux: bool = False,
        min_file_size: int = 1024,  # Default 1KB minimum size
        max_retries: int = None,  # Prevent infinite retry loops
        **params: Unpack[CobaltRequestParams],
    ) -> AsyncGenerator[Path | List[Path] | Tuple[str, Optional[Path | List[Path]], Optional[Exception]], None]:
        """
        Download multiple files from Cobalt, yielding results as they complete.

        Args:
            url: Single URL to download (alternative to urls)
            urls: Multiple URLs to download
            ignored_instances: List of instance URLs to ignore
            only_path: If True, yield only the file path instead of the full result tuple
            remux: If True, remux the downloaded file
            min_file_size: Minimum acceptable file size in bytes (files smaller than this are considered "ghost files")
            max_retries: Maximum number of retry attempts for ghost files
            **params: Parameters for the Cobalt API request

        Yields:
            Tuples of (url, file_path, exception) where:
            - url is the original URL requested
            - file_path is the Path to the downloaded file, or if the response was a picker, a list of Paths (None if failed)
            - exception is the exception that occurred (None if successful)
        """
        # Check if bulk download is allowed in config
        urls = urls or [url]
        if not urls:
            raise ValueError("Either url or urls must be provided")

        # Check max_retries
        max_retries = max_retries or self.config.get_as_number("max_retries_tunnel", 10, section="network")

        if urls and len(urls) > 1 and not self.config.get("allow_bulk_download", True, section="misc"):
            raise ValueError("Bulk downloads are disabled in configuration")

        complete_urls = []
        for url in urls:
            complete_urls += self.client.detect_playlist(url=url)

        # Make a copy of the ignored_instances list to avoid modifying the original
        current_ignored_instances = list(ignored_instances or [])

        # Get the maximum number of concurrent downloads from config
        max_concurrent = self.config.get_as_number("max_concurrent_downloads", 6, section="network")

        # Create a semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(max_concurrent)

        # Dictionary to track active download tasks by URL
        active_downloads = {}
        # Queue of pending URLs
        pending_urls = complete_urls.copy()

        logger.debug(f"Starting download_generator with {len(complete_urls)} URLs, max_concurrent={max_concurrent}")

        # Helper function to process a single URL
        async def process_url(url):
            retry_count = 0
            while retry_count <= max_retries:
                try:
                    response = await self.first_tunnel(url, close=False, ignored_instances=current_ignored_instances, **params)
                    if response.get("status", "") == "error":
                        error = ValueError(f"Error: {response['error']['code']}")
                        return url, None, error

                    if response.get("status", "") == "tunnel" or response.get("status", "") == "redirect":
                        download_url = response.get("url")
                        filename = response.get("filename")

                        # Get the instance that responded
                        responding_instance = response.get("instance_info", {}).get("url")

                        # Create a download task using detached_download
                        download_task = await self.client.detached_download(
                            url=download_url,
                            filename=filename,
                            timeout=self.config.get("download_timeout", 60),
                            progressive_timeout=True,
                        )

                        try:
                            file_path = await download_task
                        except Exception as e:
                            logger.debug(f"Download failed for {url}: {e}")
                            if retry_count < max_retries:
                                retry_count += 1
                                logger.debug(f"Retrying download for {url}, attempt {retry_count}/{max_retries}")
                                continue
                            return url, None, e

                        # Check if file is a "ghost file" (too small)
                        if file_path and file_path.exists():
                            file_size = file_path.stat().st_size
                            if file_size < min_file_size:
                                logger.warning(f"Ghost file detected from {responding_instance}: {file_path} ({file_size} bytes)")

                                # Add responding instance to ignored list for retry
                                if responding_instance and responding_instance not in current_ignored_instances:
                                    if responding_instance not in self.fallback_instance.api_url:
                                        current_ignored_instances.append(responding_instance)

                                # Delete the ghost file
                                try:
                                    file_path.unlink()
                                except Exception as e:
                                    logger.debug(f"Failed to delete ghost file {file_path}: {e}")

                                # Retry if we haven't exceeded max retries
                                retry_count += 1
                                if retry_count <= max_retries:
                                    logger.debug(
                                        f"Retrying download for {url}, attempt {retry_count}/{max_retries}, ignored: {current_ignored_instances}"
                                    )
                                    continue
                                else:
                                    logger.warning(f"Max retries reached for {url}")
                                    return url, None, ValueError("Ghost file detected and max retries reached")

                        # Apply remuxing if requested
                        if remux and file_path:
                            try:
                                remuxed_file_path = await Remuxer().remux(file_path, keep_original=False)
                                if remuxed_file_path:
                                    file_path = remuxed_file_path
                            except Exception as e:
                                logger.debug(f"Error remuxing file {file_path}: {e}")

                        return url, file_path, None
                    elif response.get("status", "") == "picker":
                        logger.debug(f"Picker response detected for {url} with {len(response.get('picker', []))} items")
                        
                        # Get the instance that responded
                        responding_instance = response.get("instance_info", {}).get("url")
                        
                        # Handle picker response - download all items
                        picker_items = response.get("picker", [])
                        downloaded_paths = []
                        download_errors = []
                        
                        # Helper function to truncate long filenames while preserving extension
                        def safe_filename(url_str, max_length=200):
                            # Extract original filename from URL
                            basename = os.path.basename(url_str.split('?')[0])
                            
                            # Split into name and extension
                            name, ext = os.path.splitext(basename)
                            
                            # If filename is too long, truncate the name part
                            if len(basename) > max_length:
                                # Make sure we leave enough room for the extension
                                truncated_name = name[:max_length - len(ext) - 1]
                                return f"{truncated_name}{ext}"
                            return basename
                        
                        # Download each picker item
                        for idx, item in enumerate(picker_items):
                            item_url = item.get("url")
                            if not item_url:
                                continue
                                
                            # Create a descriptive filename that's not too long
                            item_type = item.get("type", "media")
                            # Generate a filename with an index to keep items in order
                            raw_filename = safe_filename(item_url)
                            item_filename = f"{url.split('/')[-1].split('?')[0][:30]}_{item_type}_{idx+1:02d}_{raw_filename[-40:]}"
                            
                            try:
                                # Create a download task for this item
                                download_task = await self.client.detached_download(
                                    url=item_url,
                                    filename=item_filename,
                                    timeout=self.config.get("download_timeout", 60),
                                    progressive_timeout=True,
                                )
                                
                                file_path = await download_task
                                
                                # Check if file is a "ghost file" (too small)
                                if file_path and file_path.exists():
                                    file_size = file_path.stat().st_size
                                    if file_size < min_file_size:
                                        logger.warning(f"Ghost file detected for picker item {idx+1}: {file_path} ({file_size} bytes)")
                                        try:
                                            file_path.unlink()
                                        except Exception as e:
                                            logger.debug(f"Failed to delete ghost file {file_path}: {e}")
                                        continue
                                
                                # Add to list of downloaded paths if successful
                                if file_path:
                                    downloaded_paths.append(file_path)
                                    logger.debug(f"Downloaded picker item {idx+1}/{len(picker_items)}: {file_path}")
                            except Exception as e:
                                logger.debug(f"Failed to download picker item {idx+1}: {e}")
                                download_errors.append(e)
                        
                        # If we downloaded at least one file, consider it a success
                        if downloaded_paths:
                            return url, downloaded_paths, None
                        else:
                            # If all downloads failed, return an error
                            error_msg = f"Failed to download any files from picker response ({len(download_errors)} errors)"
                            return url, None, ValueError(error_msg)
                    else:
                        # Handle other status types
                        error = ValueError(f"Unsupported response status: {response.get('status')}")
                        return url, None, error
                except Exception as e:
                    logger.debug(f"Error processing URL {url}: {e}")
                    return url, None, e

            # If we somehow exit the retry loop without returning
            return url, None, ValueError(f"Unknown error occurred after {max_retries} retries")

        # Process URLs with controlled concurrency
        async def download_with_semaphore(url):
            async with semaphore:
                logger.debug(f"Starting download for {url}")
                result = await process_url(url)
                logger.debug(f"Completed download for {url}")
                return result

        # Start initial batch of downloads
        tasks_to_start = min(max_concurrent, len(pending_urls))
        for _ in range(tasks_to_start):
            if pending_urls:
                url = pending_urls.pop(0)
                task = asyncio.create_task(download_with_semaphore(url))
                active_downloads[url] = task

        # Process downloads until all are complete
        while active_downloads or pending_urls:
            # If we have both active downloads and pending URLs, wait for one to complete
            if active_downloads:
                # Wait for any active download to complete
                done, pending = await asyncio.wait(active_downloads.values(), return_when=asyncio.FIRST_COMPLETED)

                # Process completed downloads
                for task in done:
                    # Find the URL for this task
                    completed_url = next(url for url, t in active_downloads.items() if t == task)
                    # Remove from active downloads
                    del active_downloads[completed_url]

                    try:
                        url, file_path, error = task.result()
                        # Yield the result
                        yield file_path if only_path else (url, file_path, error)

                        # Start a new download if any are pending
                        if pending_urls:
                            next_url = pending_urls.pop(0)
                            new_task = asyncio.create_task(download_with_semaphore(next_url))
                            active_downloads[next_url] = new_task
                    except Exception as e:
                        logger.error(f"Unexpected error in download task for {completed_url}: {e}")
                        yield None if only_path else (completed_url, None, e)

                        # Start a new download if any are pending
                        if pending_urls:
                            next_url = pending_urls.pop(0)
                            new_task = asyncio.create_task(download_with_semaphore(next_url))
                            active_downloads[next_url] = new_task

            # If no active downloads but we have pending URLs, start a batch
            elif pending_urls:
                tasks_to_start = min(max_concurrent, len(pending_urls))
                for _ in range(tasks_to_start):
                    if pending_urls:
                        url = pending_urls.pop(0)
                        task = asyncio.create_task(download_with_semaphore(url))
                        active_downloads[url] = task

            # If we somehow have no active downloads and no pending URLs, we're done
            else:
                break

    async def download(
        self,
        url: str = None,
        urls: List[str] = None,
        ignored_instances: Optional[List[str]] = None,
        only_path: bool = True,
        remux: bool = False,
        **params: Unpack[CobaltRequestParams],
    ) -> Path | List[Path] | Tuple[str, Optional[Path], Optional[Exception]] | List[Tuple[str, Optional[Path], Optional[Exception]]]:
        """
        Download one or more files from Cobalt and return the results.

        Args:
            url: Single URL to download (alternative to urls)
            urls: Multiple URLs to download
            ignored_instances: List of instance URLs to ignore
            only_path: If True, yield only the file path instead of the full result tuple
            remux: If True, remux the downloaded file
            **params: Parameters for the Cobalt API request

        Returns:
            List of tuples containing (url, file_path, exception) for each download.
            If exception is None, the download was successful.
        """
        results = []
        async for result in self.download_generator(
            url=url, urls=urls, ignored_instances=ignored_instances, only_path=only_path, remux=remux, **params
        ):
            results.append(result)
        if only_path:
            for i, result in enumerate(results):
                if isinstance(result, tuple) and len(result) > 1:
                    results[i] = result[1]
        if not results:
            return None
        if not isinstance(results, list):
            return results
        return results if len(results) > 1 else results[0]
