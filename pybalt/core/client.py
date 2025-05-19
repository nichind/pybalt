from aiohttp import ClientSession, ClientResponse, ClientTimeout, TCPConnector
from typing import (
    Dict,
    Callable,
    Coroutine,
    Literal,
    TypedDict,
    Optional,
    Union,
    Any,
    Unpack,
    List,
    Tuple,
    AsyncGenerator,
)
from asyncio import sleep, iscoroutinefunction
from time import time
from os import path, getenv, makedirs, environ
from pathlib import Path
import logging
from aiofiles import open as aopen
import json
import platform
import re
import subprocess
from urllib.parse import urlparse
from .config import Config
import asyncio
from collections import deque
from .logging_utils import get_logger
from ..misc.tracker import get_tracker
import uuid


logger = get_logger(__name__)
tracker = get_tracker()


class Response:
    """Wrapper for HTTP responses"""

    def __init__(
        self,
        status: int = None,
        headers: Dict = None,
        text: str = None,
        json: Any = None,
    ):
        self.status = status
        self.headers = headers or {}
        self._text = text
        self._json = json
        self.url = None
        self.method = None
        self.request_info = None

    def __repr__(self) -> str:
        return f"<Response [status={self.status}, size={len(self._text) if self._text else 0}]>"

    def __str__(self) -> str:
        return self._text if self._json is None else str(self._json)

    async def text(self) -> str:
        """Return response body as text"""
        return self._text or ""

    async def json(self, *, content_type=None, encoding="utf-8") -> Any:
        """Try to return response body as JSON"""
        if self._json is not None:
            return self._json
        if not self._text:
            return None
        try:
            import json

            return json.loads(self._text)
        except Exception:
            return None

    def raise_for_status(self):
        """Raise an exception if the status is 4xx or 5xx."""
        if 400 <= self.status < 600:
            raise Exception(f"HTTP Error {self.status}: {self._text}")

    @classmethod
    def ensure_response(cls, obj):
        """Ensure the object is a Response instance."""
        if isinstance(obj, cls):
            return obj
        elif isinstance(obj, dict):
            return cls(json=obj)
        elif isinstance(obj, str):
            return cls(text=obj)
        return cls(text=str(obj))


class DownloadStatus:
    """Class to track download status."""

    def __init__(self):
        self.downloaded_size = 0
        self.total_size = 0
        self.start_at = 0
        self.time_passed = 0
        self.file_path = ""
        self.filename = ""
        self.download_speed = 0
        self.eta = 0
        self.completed = False


class DownloadOptions(TypedDict, total=False):
    """Type definition for download options."""

    url: str
    folder_path: str
    filename: Optional[str]
    status_callback: Optional[Union[Callable, Coroutine]]
    done_callback: Optional[Union[Callable, Coroutine]]
    status_parent: Optional[Union[Dict, DownloadStatus]]
    headers: Optional[Dict[str, str]]
    timeout: Optional[int]
    callback_rate: Optional[float]
    proxy: Optional[str]
    max_speed: Optional[int]
    close: Optional[bool]
    retry_count: Optional[int]
    progressive_timeout: Optional[bool]


class HttpClient:
    """HTTP client for making requests and downloading files."""

    def __init__(
        self,
        base_url: str = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        proxy: str = None,
        verify_proxy: bool = False,
        session: ClientSession = None,
        debug: bool = None,
        auto_detect_proxy: bool = None,
        config: Config = None,
    ):
        """Initialize the HTTP client with configurable options."""
        # Initialize config if not provided
        self.config = config or Config()

        # Get settings from config
        default_timeout = self.config.get_as_number("timeout", 30, section="network")
        default_use_system_proxy = self.config.get("use_system_proxy", True, section="network")
        default_debug = self.config.get("debug", False, section="general")
        default_user_agent = self.config.get("user_agent", section="general")

        self.base_url = base_url
        self.headers = headers or {}

        # Set default User-Agent if not specified in headers
        if default_user_agent and "User-Agent" not in self.headers:
            self.headers["User-Agent"] = default_user_agent

        self.timeout = timeout if timeout is not None else default_timeout
        self.debug = debug if debug is not None else default_debug
        self.verify_proxy = verify_proxy
        self.session = session

        # Setup proxy with auto-detection if enabled
        # Check if proxy is explicitly provided (including None)
        auto_detect_proxy = auto_detect_proxy if auto_detect_proxy is not None else default_use_system_proxy
        if proxy is not None:
            self.proxy = proxy  # Use provided proxy value (even if None)
        elif self.config.get("proxy", section="network"):
            self.proxy = self.config.get("proxy", section="network")
        else:
            self.proxy = None

        # Detect system proxy if auto-detect is enabled and no proxy is provided
        if auto_detect_proxy and not self.proxy:
            self.proxy = self._detect_system_proxy()

        # Set logger to debug level if debug is enabled
        logger.setLevel(logging.DEBUG)

        # Create console handler if not already present
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        logger.debug(f"Initialized HttpClient with base_url={base_url}, proxy={self.proxy}, verify_proxy={verify_proxy}")
        if self.proxy:
            logger.debug(f"Using proxy: {self.proxy}")

    def _detect_system_proxy(self) -> Optional[str]:
        """Detect system proxy settings including Hiddify, Outline, or environment variables."""
        detected_proxy = None

        # 1. Check environment variables first
        for env_var in [
            "https_proxy",
            "HTTPS_PROXY",
            "http_proxy",
            "HTTP_PROXY",
            "all_proxy",
            "ALL_PROXY",
        ]:
            if env_var in environ and environ[env_var]:
                detected_proxy = environ[env_var]
                logger.debug(f"Detected proxy from environment variable {env_var}: {detected_proxy}")
                break

        if detected_proxy:
            return self._normalize_proxy_url(detected_proxy)

        # 2. Check system proxy settings based on platform
        os_name = platform.system()

        if os_name == "Windows":
            return self._detect_windows_proxy()
        elif os_name == "Darwin":
            return self._detect_macos_proxy()
        elif os_name == "Linux":
            return self._detect_linux_proxy()

        return None

    def _detect_windows_proxy(self) -> Optional[str]:
        """Detect Windows system proxy settings."""
        try:
            import winreg

            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")

            # Check if proxy is enabled
            proxy_enabled = winreg.QueryValueEx(key, "ProxyEnable")[0]

            if proxy_enabled:
                proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
                logger.debug(f"Detected Windows system proxy: {proxy_server}")
                return self._normalize_proxy_url(proxy_server)
        except Exception as e:
            logger.debug(f"Error detecting Windows proxy: {str(e)}")

        return None

    def _detect_macos_proxy(self) -> Optional[str]:
        """Detect macOS system proxy settings."""
        try:
            # Try to get proxy settings using networksetup command
            result = subprocess.run(
                ["networksetup", "-getwebproxy", "Wi-Fi"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                output = result.stdout
                enabled_match = re.search(r"Enabled:\s*(Yes|No)", output)
                server_match = re.search(r"Server:\s*([^\n]+)", output)
                port_match = re.search(r"Port:\s*(\d+)", output)

                if enabled_match and enabled_match.group(1) == "Yes" and server_match and port_match:
                    server = server_match.group(1).strip()
                    port = port_match.group(1).strip()
                    proxy_url = f"http://{server}:{port}"
                    logger.debug(f"Detected macOS system proxy: {proxy_url}")
                    return proxy_url
        except Exception as e:
            logger.debug(f"Error detecting macOS proxy: {str(e)}")

        return None

    def _detect_linux_proxy(self) -> Optional[str]:
        """Detect Linux system proxy settings."""
        try:
            # Try gsettings for GNOME
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.system.proxy", "mode"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and "manual" in result.stdout:
                http_host = (
                    subprocess.run(
                        ["gsettings", "get", "org.gnome.system.proxy.http", "host"],
                        capture_output=True,
                        text=True,
                    )
                    .stdout.strip()
                    .strip("'")
                )

                http_port = subprocess.run(
                    ["gsettings", "get", "org.gnome.system.proxy.http", "port"],
                    capture_output=True,
                    text=True,
                ).stdout.strip()

                if http_host and http_port:
                    proxy_url = f"http://{http_host}:{http_port}"
                    logger.debug(f"Detected Linux (GNOME) system proxy: {proxy_url}")
                    return proxy_url

            # Try for KDE
            kde_config = path.expanduser("~/.config/kioslaverc")
            if path.exists(kde_config):
                with open(kde_config, "r") as f:
                    content = f.read()
                    if "ProxyType=1" in content:  # 1 means manual proxy
                        match = re.search(r"https=([^:]+):(\d+)", content)
                        if match:
                            host, port = match.groups()
                            proxy_url = f"http://{host}:{port}"
                            logger.debug(f"Detected Linux (KDE) system proxy: {proxy_url}")
                            return proxy_url
                        
            # Try for hyprland
            hyprland_config = path.expanduser("~/.config/hypr/hyprland.conf")
            if path.exists(hyprland_config):
                with open(hyprland_config, "r") as f:
                    content = f.read()
                    match = re.search(r"set\s+proxy\s*=\s*([^:]+):(\d+)", content)
                    if not match:
                        match = re.search(r"set\s+proxy\s*=\s*([^:]+)", content)
                    if match:
                        host, port = match.groups()
                        proxy_url = f"http://{host}:{port}"
                        logger.debug(f"Detected Linux (Hyprland) system proxy: {proxy_url}")
                        return proxy_url
        except Exception as e:
            logger.debug(f"Error detecting Linux proxy: {str(e)}")

        return None

    def _normalize_proxy_url(self, proxy_url: str) -> str:
        """Normalize proxy URL to a standard format."""
        # Add http:// scheme if missing
        if not re.match(r"^[a-zA-Z]+://", proxy_url):
            proxy_url = f"http://{proxy_url}"

        # Parse and validate the URL
        parsed = urlparse(proxy_url)

        # Ensure there's a hostname and port
        if not parsed.hostname:
            return None

        # Use default port 80 if not specified
        if not parsed.port:
            port = 80 if parsed.scheme == "http" else 443
            proxy_url = f"{parsed.scheme}://{parsed.hostname}:{port}"

        return proxy_url

    def _is_localhost_url(self, url: str) -> bool:
        """
        Check if a URL points to a localhost address.

        Args:
            url: The URL to check

        Returns:
            True if the URL points to a localhost address, False otherwise
        """
        if not url:
            return False

        parsed_url = urlparse(url)
        hostname = parsed_url.hostname

        if not hostname:
            return False

        # Check for common localhost hostnames
        if hostname == "localhost":
            return True

        # Check for Docker-specific hostnames
        if hostname == "host.docker.internal":
            return True

        # Check IPv4 localhost addresses
        if hostname.startswith("127."):
            return True

        # Check IPv6 localhost
        if hostname == "::1" or hostname == "[::1]":
            return True

        # Check 0.0.0.0 (any interface)
        if hostname == "0.0.0.0":
            return True

        return False

    def _get_effective_proxy(self, url: str, explicit_proxy: Optional[str] = None) -> Optional[str]:
        """
        Determine the effective proxy to use for a given URL, considering the bypass_proxy_for_localhost setting.

        Args:
            url: The URL to request
            explicit_proxy: An explicitly provided proxy that overrides the default

        Returns:
            The proxy to use, or None if no proxy should be used
        """
        # If an explicit proxy is provided, use it unless localhost bypass is enabled
        if explicit_proxy is not None:
            # Handle Docker hostnames when network_mode is "host"
            if self.config.get("network_mode", "host", section="network") == "host":
                explicit_proxy = self._replace_docker_hosts_with_localhost(explicit_proxy)

            if self.config.get("bypass_proxy_for_localhost", True, section="network") and self._is_localhost_url(url):
                logger.debug(f"Bypassing explicit proxy for localhost URL: {url}")
                return None
            return explicit_proxy

        # Otherwise use the default proxy unless localhost bypass is enabled
        proxy = self.proxy
        # Handle Docker hostnames when network_mode is "host"
        if proxy and self.config.get("network_mode", "host", section="network") == "host":
            proxy = self._replace_docker_hosts_with_localhost(proxy)

        if self.config.get("bypass_proxy_for_localhost", True, section="network") and self._is_localhost_url(url):
            logger.debug(f"Bypassing default proxy for localhost URL: {url}")
            return None

        return proxy

    def _replace_docker_hosts_with_localhost(self, url: str) -> str:
        """
        Replace Docker-specific hostnames with localhost in a URL.

        Args:
            url: The URL to process

        Returns:
            URL with Docker hostnames replaced with localhost
        """
        if not url:
            return url

        try:
            parsed = urlparse(url)
            if parsed.hostname == "host.docker.internal":
                # Get the port from the original URL or use default
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                # Replace with localhost but keep the same port and path
                new_url = f"{parsed.scheme}://localhost:{port}{parsed.path}"
                # Add query parameters if present
                if parsed.query:
                    new_url += f"?{parsed.query}"
                logger.debug(f"Replaced Docker hostname in URL: {url} -> {new_url}")
                return new_url
        except Exception as e:
            logger.debug(f"Error replacing Docker hostname in URL: {e}")

        return url

    async def _ensure_session(self, headers: Dict[str, str] = None) -> ClientSession:
        """Ensure there's an active session or create a new one."""
        session = self.session
        session_headers = headers if headers is not None else self.headers
        if not session or session.closed:
            # Create new session with merged headers only when needed

            # Create TCP connector with SSL verification settings
            connector = TCPConnector(ssl=None if self.verify_proxy else False)
            self.session = ClientSession(headers=session_headers, connector=connector)
        self.session.headers.update(session_headers)
        return self.session

    async def request(
        self,
        url: str,
        method: Literal["get", "post"] = "get",
        params: Dict = None,
        data: Dict = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        proxy: str = None,
        verify: bool = None,
        retries: int = 0,
        max_retries: int = None,
        close: bool = True,
        **kwargs,
    ) -> Response:
        """Make an HTTP request with support for retries."""
        # Get max retries from config if not provided
        max_retries = max_retries if max_retries is not None else self.config.get_as_number("max_retries", 5, section="network")

        if retries > max_retries:
            raise Exception(f"Maximum retry count ({max_retries}) exceeded")

        # Prepare URL (cached to avoid string operations on retries)
        full_url = url if url.startswith("http") else f"{self.base_url or ''}{url}"

        # Prepare request options (do this once to avoid repeated lookups)
        request_timeout = ClientTimeout(total=timeout or self.timeout or self.config.get_as_number("timeout", 30, section="network"))
        request_headers = headers or self.headers

        # Determine if proxy should be used based on URL (bypass for localhost)
        request_proxy = self._get_effective_proxy(full_url, proxy)
        request_verify = self.verify_proxy if verify is None else verify

        # Debug logging
        logger.debug(f"Request: {method.upper()} {full_url}")
        logger.debug(f"Headers: {request_headers}")
            
        if params:
            logger.debug(f"Params: {params}")
        if data:
            logger.debug(f"Data: {data}")
        logger.debug(f"Proxy: {request_proxy}, Verify: {request_verify}, Timeout: {request_timeout.total}s")

        # Create response object
        response_obj = Response()
        response_obj.method = method.upper()
        response_obj.url = full_url

        try:
            # Set up SSL verification
            ssl_context = None
            if not request_verify:
                ssl_context = False

            # Create or get session
            session = await self._ensure_session(request_headers)

            try:
                # Common request handling for both GET and POST
                session_method = session.get if method == "get" else session.post
                session_kwargs = {"timeout": request_timeout, "ssl": ssl_context}

                # Add proxy if specified
                if request_proxy:
                    session_kwargs["proxy"] = request_proxy

                if method == "get":
                    session_kwargs["params"] = params
                else:
                    session_kwargs["json"] = data or kwargs.pop("json", None)
                # exit()
                session_kwargs.update(kwargs)

                request_start_time = time()

                async with session_method(full_url, **session_kwargs) as response:
                    response_time = time() - request_start_time
                    response_obj.status = response.status
                    response_obj.headers = dict(response.headers)

                    # Debug logging for response
                    logger.debug(f"Response: {response.status} ({response_time:.2f}s)")
                    logger.debug(f"Response headers: {dict(response.headers)}")

                    # Handle rate limiting
                    if response.status == 429:
                        retry_delay = float(
                            response.headers.get(
                                "Retry-After",
                                self.config.get_as_number("retry_delay", 1.0, section="network"),
                            )
                        )
                        logger.debug(f"Rate limited, retrying after {retry_delay}s")
                        await sleep(retry_delay)
                        return await self.request(
                            url,
                            method,
                            params,
                            data,
                            headers,
                            timeout,
                            proxy,
                            verify,
                            retries + 1,
                            max_retries,
                            close,
                            **kwargs,
                        )

                    if response.status == 404:
                        raise Exception(f"{full_url}: Page not found")

                    try:
                        response_text = await response.text()
                        response_obj._text = response_text
                        logger.debug(f"Response text (preview): {response_text[:350]}...")

                        try:
                            response_obj._json = await response.json()
                        except json.JSONDecodeError:
                            response_obj._json = None
                    except Exception as e:
                        logger.debug(f"Failed to parse response as json: {str(e)}")
                        response_obj._json = None
            finally:
                if close:
                    logger.debug("Closing session")
                    await session.close()

        except Exception as e:
            logger.debug(f"Request error: {str(e)}")
            if retries < max_retries:
                logger.debug(f"Retrying request ({retries + 1}/{max_retries})")
                await sleep(self.config.get_as_number("retry_delay", 1.0, section="network"))
                return await self.request(
                    url,
                    method,
                    params,
                    data,
                    headers,
                    timeout,
                    proxy,
                    verify,
                    retries + 1,
                    max_retries,
                    close,
                    **kwargs,
                )
            raise

        return response_obj

    async def get(
        self,
        url: str,
        params: Dict = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        **kwargs,
    ) -> Response:
        """Make a GET request and return Response object.

        Args:
            url: URL to request
            params: URL parameters
            headers: Request headers
            timeout: Request timeout
            **kwargs: Additional arguments for the request

        Returns:
            Response object
        """
        return await self.request(url, method="get", params=params, headers=headers, timeout=timeout, **kwargs)

    async def post(
        self,
        url: str,
        data: Dict = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        **kwargs,
    ) -> Response:
        """Make a POST request and return Response object.

        Args:
            url: URL to request
            data: JSON data to send
            headers: Request headers
            timeout: Request timeout
            **kwargs: Additional arguments for the request

        Returns:
            Response object
        """
        return await self.request(url, method="post", data=data, headers=headers, timeout=timeout, **kwargs)

    async def _get_auth_headers_for_url(self, url: str, api_key: str = None, bearer: str = None) -> Dict[str, str]:
        """
        Get authorization headers for a URL based on provided credentials or user instances.

        Args:
            url: The URL to get headers for
            api_key: Optional API key to use (takes precedence over instance API key)
            bearer: Optional bearer token to use (takes precedence over API key)

        Returns:
            Dictionary of headers to add
        """
        headers = {}

        # If bearer token is provided, it takes precedence
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
            return headers

        # If API key is provided, use it
        if api_key:
            headers["Authorization"] = f"Api-Key {api_key}"
            return headers

        # Otherwise, check if URL matches any user instance
        user_instances = self.config.get_user_instances()
        for instance in user_instances:
            # Check if URL starts with this instance URL
            if url.startswith(instance["url"]) and instance["api_key"]:
                headers["Authorization"] = f"Api-Key {instance['api_key']}"
                return headers

        # If no match found, check for default API key in config
        default_api_key = self.config.get("api_key", "", section="instances")
        if default_api_key:
            headers["Authorization"] = f"Api-Key {default_api_key}"

        return headers

    async def bulk_request_generator(
        self,
        urls: List[Union[str, Dict[str, str]]],
        method: Literal["get", "post"] = "get",
        close: bool = True,
        **kwargs,
    ) -> AsyncGenerator[Response, None]:
        """Make concurrent requests to multiple URLs and yield responses as they come in.

        Args:
            urls: List of URLs to request (either string or dict with "url", optional "api_key" and "bearer")
            method: HTTP method to use ("get" or "post")
            **kwargs: Additional arguments for the request

        Yields:
            Response objects as they become available
        """
        # Check if bulk requests are allowed in config
        if not self.config.get("allow_bulk_download", True, section="misc"):
            raise Exception("Bulk requests are disabled in the configuration")

        if not urls:
            return

        logger.debug(f"Performing bulk {method.upper()} request to {len(urls)} URLs")

        # Store tasks to ensure proper cancellation
        tasks = []

        first_only = kwargs.pop("first_successful_only", False)

        try:
            # Ensure session exists but don't close it in the request method
            session = await self._ensure_session()

            # Define helper that returns as soon as a successful response is found
            async def safe_request(
                url_data: Union[str, Dict[str, str]],
            ) -> Tuple[bool, Response]:
                try:
                    # Process URL and credentials
                    url = url_data if isinstance(url_data, str) else url_data.get("url")
                    api_key = None if isinstance(url_data, str) else url_data.get("api_key", None)
                    bearer = None if isinstance(url_data, str) else url_data.get("bearer", None)

                    # Check if we should bypass proxy for this URL
                    request_kwargs = kwargs.copy()
                    if "proxy" not in request_kwargs:
                        request_kwargs["proxy"] = self._get_effective_proxy(url)

                    # Add authorization headers if needed
                    auth_headers = await self._get_auth_headers_for_url(url, api_key, bearer)
                    if auth_headers:
                        request_headers = (
                            request_kwargs.get("headers", {}).copy()
                            if "headers" in request_kwargs
                            else self.headers.copy()
                            if self.headers
                            else {}
                        )
                        request_headers.update(auth_headers)
                        request_kwargs["headers"] = request_headers

                    # Don't close the session in individual requests
                    response = await self.request(url, method=method, close=False, **request_kwargs)

                    # Consider 2xx and 3xx status codes as successful
                    if response.status < 400:
                        logger.debug(f"Request to {url} succeeded with status {response.status}")
                        return True, response
                    else:
                        logger.debug(f"Request to {url} failed with status {response.status}")
                        return False, response
                except Exception as e:
                    logger.debug(f"Request to {url} failed with error: {str(e)}")
                    # Create an error response
                    return False, Response(status=0, text=f"Error: {str(e)}")

            # Create tasks for all URLs
            tasks = [asyncio.create_task(safe_request(url)) for url in urls]

            # Use as_completed to get results as they finish
            for future in asyncio.as_completed(tasks):
                success, response = await future
                # Yield each response as it becomes available
                yield response

                # No need to continue if we found a successful response and just want the first one
                if success and first_only:
                    break

        except Exception as e:
            logger.debug(f"Bulk request error: {str(e)}")
            # Yield a generic error response
            yield Response(status=0, text=f"Bulk request error: {str(e)}")

        finally:
            # Cancel any remaining tasks that might still be running
            for task in tasks:
                if not task.done():
                    task.cancel()

            # Don't close the session here if close=False was specified
            if close:
                if session and not session.closed:
                    logger.debug("Closing session after bulk request")
                    await session.close()

    async def bulk_request(
        self,
        urls: List[Union[str, Dict[str, str]]],
        method: Literal["get", "post"] = "get",
        **kwargs,
    ) -> Response:
        """Make concurrent requests to multiple URLs and return the first successful response.

        Args:
            urls: List of URLs to request (either string or dict with "url", optional "api_key" and "bearer")
            method: HTTP method to use ("get" or "post")
            **kwargs: Additional arguments for the request

        Returns:
            The first successful Response object or an error Response if all requests fail
        """
        # Set flag to get only the first successful response
        kwargs["first_successful_only"] = True

        # Get the generator
        generator = self.bulk_request_generator(urls, method, **kwargs)

        # Return the first response from the generator
        async for response in generator:
            if response.status < 400 and response.status > 0:
                logger.debug(f"Successful response: {response.__dict__}")
                return response
            # Store the first error response to return if all fail
            first_error = response

        logger.debug(f"All requests failed, returning first error: {first_error}")
        # If we got here, no successful responses were found, return the first error
        return first_error

    async def bulk_get(
        self,
        urls: List[Union[str, Dict[str, str]]],
        params: Dict = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        **kwargs,
    ) -> Response:
        """Make concurrent GET requests to multiple URLs and return the first successful response.

        Args:
            urls: List of URLs to request (either string or dict with "url", optional "api_key" and "bearer")
            params: URL parameters
            headers: Request headers
            timeout: Request timeout
            **kwargs: Additional arguments for the request

        Returns:
            The first successful Response object or an error Response if all requests fail
        """
        return await self.bulk_request(
            urls,
            method="get",
            params=params,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

    async def bulk_post(
        self,
        urls: List[Union[str, Dict[str, str]]],
        data: Dict = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        **kwargs,
    ) -> Response:
        """Make concurrent POST requests to multiple URLs and return the first successful response.

        Args:
            urls: List of URLs to request (either string or dict with "url", optional "api_key" and "bearer")
            data: JSON data to send
            headers: Request headers
            timeout: Request timeout
            **kwargs: Additional arguments for the request

        Returns:
            The first successful Response object or an error Response if all requests fail
        """
        return await self.bulk_request(urls, method="post", data=data, headers=headers, timeout=timeout, **kwargs)

    async def _download_and_track(
        self, url_data: Union[str, Dict[str, str]], options: Dict
    ) -> Tuple[str, Optional[Path], Optional[Exception]]:
        """Helper method for bulk_download to handle individual downloads with error tracking."""
        try:
            # Process URL and credentials
            if isinstance(url_data, str):
                url = url_data
                download_options = options.copy()
                download_options["url"] = url
            else:
                url = url_data["url"]
                download_options = options.copy()
                download_options["url"] = url

                # Add API key and bearer if present
                if "api_key" in url_data:
                    download_options["api_key"] = url_data["api_key"]
                if "bearer" in url_data:
                    download_options["bearer"] = url_data["bearer"]

            file_path = await self.download_file(**download_options)
            return url, file_path, None
        except Exception as e:
            logger.debug(f"Download failed for {url}: {str(e)}")
            return url, None, e

    async def bulk_download_generator(
        self,
        urls: List[Union[str, Dict[str, str]]],
        folder_path: str = None,
        max_concurrent: int = None,
        **options,
    ) -> AsyncGenerator[Tuple[str, Path, Exception], None]:
        """
        Download multiple files concurrently with a limit on maximum parallel downloads.

        Args:
            urls: List of URLs to download (either string or dict with "url", optional "api_key" and "bearer")
            folder_path: Download destination folder
            max_concurrent: Maximum number of concurrent downloads
            **options: Additional options to pass to download_file

        Yields:
            Tuples containing (url, file_path, exception) for each download
            If exception is None, the download was successful
        """
        # Check if bulk downloads are allowed in config
        if not self.config.get("allow_bulk_download", True, section="misc"):
            raise Exception("Bulk downloads are disabled in configuration")

        if not urls:
            return

        # Use config for default folder path if not specified
        if not folder_path:
            folder_path = self.config.get("default_downloads_dir", str(Path.home() / "Downloads"), section="paths")

        # Use config for max_concurrent if not specified
        if max_concurrent is None:
            max_concurrent = self.config.get_as_number("max_concurrent_downloads", 3, section="network")

        logger.debug(f"Starting bulk download of {len(urls)} files, max_concurrent={max_concurrent}")

        results = []
        active_tasks = set()
        url_queue = deque(urls)

        # Process downloads until the queue is empty and all active tasks are done
        while url_queue or active_tasks:
            # Start new downloads if under the concurrent limit and URLs are available
            while len(active_tasks) < max_concurrent and url_queue:
                url_data = url_queue.popleft()

                # Set up download options
                download_options = options.copy()
                download_options["folder_path"] = folder_path

                # Use config values for defaults if not in options
                if "callback_rate" not in download_options:
                    download_options["callback_rate"] = self.config.get_as_number("callback_rate", 0.128, section="network")

                if "timeout" not in download_options:
                    download_options["timeout"] = self.config.get_as_number("timeout", 30, section="network")

                # Create task
                task = asyncio.create_task(self._download_and_track(url_data, download_options))
                active_tasks.add(task)
                # Add callback to remove the task when done
                task.add_done_callback(active_tasks.discard)

                url = url_data if isinstance(url_data, str) else url_data.get("url")
                logger.debug(f"Added download task for {url}, active tasks: {len(active_tasks)}")

            # Wait a bit if we have active tasks, otherwise we're done
            if active_tasks:
                await asyncio.sleep(0.1)  # Small sleep to prevent CPU spinning

                # Check for completed tasks and collect results
                for task in list(active_tasks):
                    if task.done():
                        try:
                            url, path, error = task.result()
                            results.append((url, path, error))
                            status = "failed" if error else "completed"
                            logger.debug(f"Download of {url} {status}")
                            yield url, path, error
                        except Exception as e:
                            # This should not happen as exceptions are handled in _download_and_track
                            logger.debug(f"Unexpected error in bulk download: {str(e)}")

    async def bulk_download(
        self,
        urls: List[Union[str, Dict[str, str]]],
        folder_path: str = None,
        max_concurrent: int = None,
        **options,
    ) -> List[Tuple[str, Path, Exception]]:
        results = await self.bulk_download_generator(urls, folder_path, max_concurrent, **options)
        return results

    async def bulk_detached_download(
        self,
        urls: List[Union[str, Dict[str, str]]],
        folder_path: str = None,
        max_concurrent: int = None,
        **options,
    ) -> asyncio.Task:
        """
        Start a bulk download operation in a detached task that runs in the background.

        Args:
            urls: List of URLs to download (either string or dict with "url", optional "api_key" and "bearer")
            folder_path: Download destination folder
            max_concurrent: Maximum number of concurrent downloads
            **options: Additional options to pass to download_file

        Returns:
            asyncio.Task: The task handling the bulk download, which can be awaited or monitored
        """
        # Check if bulk downloads are allowed in config
        if not self.config.get("allow_bulk_download", True, section="misc"):
            raise Exception("Bulk downloads are disabled in configuration")

        # Apply configuration defaults if not explicitly provided
        if folder_path is None:
            folder_path = self.config.get("default_downloads_dir", str(Path.home() / "Downloads"), section="paths")

        if max_concurrent is None:
            max_concurrent = self.config.get_as_number("max_concurrent_downloads", 3, section="network")

        # Create a task for the bulk download
        bulk_task = asyncio.create_task(
            self.bulk_download(
                urls=urls,
                folder_path=folder_path,
                max_concurrent=max_concurrent,
                **options,
            )
        )

        # Add name to the task for easier debugging
        bulk_task.set_name(f"BulkDownload_{len(urls)}_files")
        logger.debug(f"Started detached bulk download task for {len(urls)} URLs")
        return bulk_task

    async def download_file(
        self,
        **options: Unpack[DownloadOptions],
    ) -> Path:
        """Download a file with progress tracking."""
        # Extract and cache options to avoid repeated dictionary lookups
        url = options.get("url")
        if not url:
            raise ValueError("URL is required for downloading files")

        # Generate download ID for tracking
        download_id = str(uuid.uuid4())

        # Get API key and bearer token if provided
        api_key = options.get("api_key")
        bearer = options.get("bearer")

        # Get authorization headers if needed
        auth_headers = await self._get_auth_headers_for_url(url, api_key, bearer)

        # Merge authorization headers with existing headers
        if auth_headers:
            request_headers = options.get("headers", {}).copy() if "headers" in options else self.headers.copy() if self.headers else {}
            request_headers.update(auth_headers)
            options["headers"] = request_headers

        # Debug logging
        logger.debug(f"Starting download from: {url}")
        logger.debug(f"Download options: {options}")

        folder_path = options.get("folder_path", getenv("DOWNLOAD_FOLDER")) or self.config.get(
            "default_downloads_dir", str(Path.home() / "Downloads"), section="paths"
        )
        if not path.exists(folder_path):
            makedirs(folder_path)
            logger.debug(f"Created download directory: {folder_path}")

        # Cache callback options
        status_callback = options.get("status_callback")
        done_callback = options.get("done_callback")
        status_parent = options.get("status_parent")
        callback_rate = options.get(
            "callback_rate",
            self.config.get_as_number("callback_rate", 0.128, section="network"),
        )
        max_speed = options.get("max_speed")
        request_headers = options.get("headers", self.headers)
        # Determine if proxy should be used based on URL (bypass for localhost)
        request_proxy = self._get_effective_proxy(url, options.get("proxy"))

        # Use a longer timeout for downloads by default
        download_timeout = options.get("timeout")
        if download_timeout is None:
            # Use a dedicated download_timeout setting if available, otherwise fall back to regular timeout
            download_timeout = (
                self.config.get_as_number("download_timeout", 20, section="network")
                or self.config.get_as_number("timeout", 10, section="network") * 2
            )  # 2x regular timeout as fallback

        should_close = options.get("close", True)
        retry_count = options.get(
            "retry_count",
            self.config.get_as_number("download_retries", 3, section="network"),
        )
        progressive_timeout = options.get(
            "progressive_timeout",
            self.config.get("progressive_timeout", True, section="network"),
        )

        # Initialize tracking variables
        start_time = time()
        downloaded_size = 0
        download_speed = 0
        last_callback_time = start_time
        last_size = 0
        iteration = 0

        # Prepare session (reuse session for better performance)
        session = await self._ensure_session(request_headers)

        try:
            # Set up SSL verification
            ssl_context = None
            if not self.verify_proxy:
                ssl_context = False

            # Create download request with proxy and SSL settings
            download_kwargs = {"ssl": ssl_context}

            # Add proxy if specified
            if request_proxy:
                download_kwargs["proxy"] = request_proxy

            logger.debug(f"Starting download request with kwargs: {download_kwargs}")

            # Add retry loop for download
            for retry_attempt in range(retry_count + 1):
                if retry_attempt > 0:
                    logger.debug(f"Retry attempt {retry_attempt}/{retry_count} for download: {url}")
                    await sleep(self.config.get_as_number("retry_delay", 1.0, section="network") * retry_attempt)

                try:
                    async with session.get(url, **download_kwargs) as response:
                        if response.status >= 400:
                            error_msg = f"Failed to download file, status code: {response.status}"
                            logger.debug(error_msg)

                            # Only retry on certain error codes
                            if response.status in (429, 500, 502, 503, 504) and retry_attempt < retry_count:
                                continue
                            raise Exception(error_msg)

                        total_size = int(response.headers.get("Content-Length", -1))
                        logger.debug(f"Content-Length: {total_size} bytes")

                        # If progressive timeout is enabled, adjust timeout based on file size
                        if progressive_timeout and total_size > 0:
                            # Calculate appropriate timeout: base + size factor
                            # Use 30s as base + 1s per MB with a reasonable cap
                            size_mb = total_size / (1024 * 1024)
                            adjusted_timeout = min(30 + size_mb, download_timeout * 2)
                            if adjusted_timeout > download_timeout:
                                logger.debug(f"Increasing timeout to {adjusted_timeout}s based on file size ({size_mb:.1f}MB)")
                                # Create a new timeout and update the request
                                request_timeout = ClientTimeout(total=adjusted_timeout)
                                download_kwargs["timeout"] = request_timeout

                        # Determine filename (optimize the conditional logic)
                        filename = options.get("filename")
                        if not filename:
                            content_disposition = response.headers.get("Content-Disposition", "")
                            if 'filename="' in content_disposition:
                                filename = content_disposition.split('filename="')[1].split('"')[0]
                            else:
                                filename = url.split("/")[-1].split("?")[0]

                        file_path = path.join(folder_path, filename)
                        logger.debug(f"Downloading to: {file_path}")

                        # Add download to tracker - ensure tracker is initialized
                        if tracker.enabled:
                            tracker.add_download(download_id, url, filename)
                            tracker.update_download(download_id, total_size=total_size, file_path=file_path)

                        # Download the file with optimized buffer handling
                        buffer_size = self.config.get_as_number("download_buffer_size", 1024 * 1024, "network")
                        logger.debug(f"Using buffer size: {buffer_size / 1024:.0f}KB")

                        async with aopen(file_path, "wb") as f:
                            logger.debug("Download started")
                            while True:
                                try:
                                    # Use read() with a timeout to prevent hanging
                                    chunk = await asyncio.wait_for(
                                        response.content.read(buffer_size),
                                        timeout=30,  # Timeout for individual chunk reads
                                    )

                                    if not chunk:
                                        logger.debug("End of stream reached")
                                        break

                                    # Write chunk to file
                                    await f.write(chunk)
                                    chunk_size = len(chunk)
                                    downloaded_size += chunk_size

                                    # Update download tracker
                                    tracker.update_download(download_id, downloaded_size=downloaded_size)

                                    # Update progress if needed (reduce time() calls)
                                    current_time = time()
                                    time_since_callback = current_time - last_callback_time

                                    if time_since_callback >= callback_rate:
                                        # Calculate download stats
                                        if time_since_callback > 0:
                                            download_speed = (downloaded_size - last_size) / time_since_callback
                                        else:
                                            download_speed = 0

                                        eta = (
                                            (total_size - downloaded_size) / download_speed if download_speed > 0 and total_size > 0 else 0
                                        )
                                        time_passed = current_time - start_time

                                        # Debug logging for download progress
                                        percent = (downloaded_size / total_size * 100) if total_size > 0 else 0
                                        logger.debug(
                                            f"Downloaded: {downloaded_size / 1024 / 1024:.2f}MB / "
                                            f"{total_size / 1024 / 1024:.2f}MB ({percent:.1f}%) at "
                                            f"{download_speed / 1024 / 1024:.2f}MB/s, ETA: {eta:.0f}s"
                                        )

                                        # Create progress data once (avoid repeated dict creation)
                                        progress_data = {
                                            "downloaded_size": downloaded_size,
                                            "start_at": start_time,
                                            "time_passed": round(time_passed, 2),
                                            "file_path": file_path,
                                            "filename": filename,
                                            "download_speed": download_speed,
                                            "total_size": total_size,
                                            "iteration": iteration,
                                            "eta": round(eta),
                                        }

                                        # Update tracker with download speed and ETA
                                        if tracker.enabled:
                                            tracker.update_download(
                                                download_id,
                                                speed=download_speed,
                                                eta=eta if eta else 0,
                                            )

                                        # Process callbacks and status updates
                                        await self._process_download_callbacks(
                                            status_callback,
                                            status_parent,
                                            progress_data,
                                        )

                                        # Update tracking variables
                                        last_callback_time = current_time
                                        last_size = downloaded_size
                                        iteration += 1

                                    # Limit download speed if requested
                                    if max_speed and download_speed > max_speed:
                                        sleep_time = chunk_size / max_speed
                                        logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                                        await sleep(sleep_time)

                                    # Check if download is complete
                                    if total_size != -1 and downloaded_size >= total_size:
                                        logger.debug("Download complete (size match)")
                                        break

                                except asyncio.TimeoutError:
                                    logger.debug(f"Timeout while reading chunk after downloading {downloaded_size / 1024 / 1024:.2f}MB")

                                    # If we've downloaded a significant portion, try to continue
                                    if (
                                        downloaded_size > buffer_size * 5 if buffer_size * 5 < 1024 * 1024 * 100 else 1024 * 1024 * 100
                                    ):  # At least 5 times the download buffer size but not more than 100Mb
                                        logger.debug("Continuing download despite chunk timeout")
                                        await sleep(0.5)  # Small sleep to avoid busy waiting
                                        continue

                                    # Otherwise, retry the whole download
                                    if retry_attempt < retry_count:
                                        break  # Break out of chunk reading loop to retry full download
                                    else:
                                        raise Exception(
                                            f"Download timed out after multiple retries ({downloaded_size / 1024 / 1024:.2f}MB downloaded)"
                                        )

                    # If we reached here, the download was successful
                    # Verify download size
                    if downloaded_size <= 1024 and retry_attempt < retry_count:
                        # Very small file, might be an error response
                        logger.debug(f"Downloaded file is too small ({downloaded_size} bytes), retrying...")
                        continue

                    # Process completion
                    if status_parent or done_callback:
                        completion_time = time()
                        time_passed = round(completion_time - start_time, 2)

                        logger.debug(f"Download completed in {time_passed}s")

                        # Update status parent if provided
                        if status_parent:
                            completed_data = {
                                "downloaded_size": downloaded_size,
                                "total_size": total_size,
                                "completed": True,
                                "time_passed": time_passed,
                            }

                            logger.debug("Updating status parent with completion data")

                            if isinstance(status_parent, dict):
                                status_parent.update(completed_data)
                            elif hasattr(status_parent, "__dict__"):
                                for key, value in completed_data.items():
                                    setattr(status_parent, key, value)

                        # Call completion callback if provided
                        if done_callback:
                            done_data = {
                                "downloaded_size": downloaded_size,
                                "start_at": start_time,
                                "time_passed": time_passed,
                                "file_path": file_path,
                                "filename": filename,
                                "total_size": path.getsize(file_path),
                            }

                            logger.debug(f"Calling done callback with data: {done_data}")

                            if iscoroutinefunction(done_callback):
                                await done_callback(**done_data)
                            else:
                                done_callback(**done_data)

                    # Mark download as complete in tracker
                    if tracker.enabled:
                        tracker.complete_download(download_id, file_path)

                    # If successful, break out of the retry loop
                    break

                except (asyncio.TimeoutError, ConnectionError) as e:
                    # Only retry on timeouts and connection errors
                    if retry_attempt < retry_count:
                        logger.debug(f"Download error (attempt {retry_attempt + 1}/{retry_count + 1}): {str(e)}")
                    else:
                        # Last attempt failed, remove from tracker and re-raise
                        if tracker.enabled:
                            tracker.remove_download(download_id)
                        logger.error(f"Download failed after {retry_count + 1} attempts: {str(e)}")
                        raise

        except Exception as e:
            # Remove failed download from tracker
            if tracker.enabled:
                tracker.remove_download(download_id)
            logger.debug(f"Download error: {str(e)}")
            raise
        finally:
            if should_close:
                logger.debug("Closing session")
                await session.close()

        return Path(file_path)

    async def _process_download_callbacks(self, status_callback, status_parent, progress_data):
        """Helper method to process download callbacks and status updates."""
        # Call status callback if provided
        if status_callback:
            if iscoroutinefunction(status_callback):
                await status_callback(**progress_data)
            else:
                status_callback(**progress_data)

        # Update status parent if provided
        if status_parent:
            if isinstance(status_parent, dict):
                status_parent.update(progress_data)
            elif hasattr(status_parent, "__dict__"):
                for key, value in progress_data.items():
                    setattr(status_parent, key, value)
            else:
                raise TypeError("status_parent must be a dict or an object with attributes")

    async def detached_download(
        self,
        **options: Unpack[DownloadOptions],
    ) -> asyncio.Task:
        """
        Start a file download in a detached task that runs in the background.

        Args:
            **options: Same options as download_file method

        Returns:
            asyncio.Task: The task handling the download, which can be awaited or monitored
        """
        # Apply configuration defaults if not explicitly provided
        if "folder_path" not in options:
            options["folder_path"] = self.config.get("default_downloads_dir", str(Path.home() / "Downloads"), section="paths")

        if "callback_rate" not in options:
            options["callback_rate"] = self.config.get_as_number("callback_rate", 0.128, section="network")

        if "timeout" not in options:
            options["timeout"] = self.config.get_as_number("timeout", 30, section="network")

        # Create a task for the download
        download_task = asyncio.create_task(self.download_file(**options))

        # Add name to the task for better debugging
        url = options.get("url", "unknown")
        filename = url.split("/")[-1] if "/" in url else url
        download_task.set_name(f"Download_{filename[:30]}")

        logger.debug(f"Started detached download task for: {options.get('url')}")

        return download_task

    def detect_playlist(self, url: str) -> List[str]:
        """
        Checks wherever a link is a playlist and if so, returns a url list of an playlist members

        Returns:
            List[str] or None: List of URLs if a playlist is detected, otherwise list with the original URL
        """
        # YouTube playlist
        # Define a regex pattern to match all YouTube URL variations
        youtube_pattern = r"(?:https?:\/\/)?(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)(?:\/[^\s]*)?"

        # Check if the URL is a YouTube link
        if re.match(youtube_pattern, url):
            logger.debug(f"Detected YouTube URL: {url}")
            # Check if it's a playlist
            playlist_id_match = re.findall(r"[&?]list=([^&]+)", url)
            if playlist_id_match:
                logger.debug(f"Detected YouTube playlist ID: {playlist_id_match[0]}")
                try:
                    from pytube import Playlist

                    logger.debug("Extracting playlist using pytube")
                    proxies = {"https": self._get_effective_proxy(url)} if self._get_effective_proxy(url) else None
                    if proxies:
                        logger.debug(f"Using proxy for playlist extraction: {proxies}")
                    playlist = Playlist(url, proxies=proxies)
                    # Check if the playlist is empty
                    if not playlist.video_urls:
                        logger.debug("The playlist is empty.")
                        return []
                    logger.debug(f"Extracted playlist successfully. Number of videos: {len(playlist.video_urls)}")
                    if "music." in url:
                        # For YouTube Music playlists, we need to extract the video URLs and replace the domain with music.youtube.com
                        logger.debug("Detected YouTube Music playlist")
                        return [url.replace("www.", "music.") for url in playlist.video_urls]
                    return list(playlist.video_urls)
                except Exception as e:
                    logger.debug(f"Failed to extract playlist: {str(e)}")
                    return []

        return [url]

    async def __aenter__(self):
        """Async context manager entry point."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        if self.session and not self.session.closed:
            await self.session.close()
