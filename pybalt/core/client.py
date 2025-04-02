from aiohttp import ClientSession, ClientResponse, ClientTimeout, TCPConnector
from typing import Dict, Callable, Coroutine, Literal, TypedDict, Optional, Union, Any, Unpack
from asyncio import sleep, iscoroutinefunction
from time import time
from os import path, getenv, makedirs, environ
from pathlib import Path
import logging
from aiofiles import open as aopen
import ssl
import json
import platform
import re
import subprocess
from urllib.parse import urlparse

# Constants
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_CALLBACK_RATE = 0.128

logger = logging.getLogger(__name__)


class Response:
    """Wrapper for HTTP responses, similar to aiohttp's ClientResponse."""
    
    def __init__(self, status: int = None, headers: Dict = None, text: str = None, json: Any = None):
        self.status = status
        self.headers = headers or {}
        self._text = text
        self._json = json
        self.url = None
        self.method = None
        self.request_info = None
    
    def __repr__(self) -> str:
        return f"<Response [status={self.status}]>"
    
    def __str__(self) -> str:
        return self._text if self._json is None else str(self._json)
    
    async def text(self) -> str:
        """Return response body as text, similar to aiohttp."""
        return self._text or ""
    
    async def json(self, *, content_type=None, encoding="utf-8") -> Any:
        """Return response body as JSON, similar to aiohttp."""
        if self._json is not None:
            return self._json
        if not self._text:
            return None
        try:
            import json
            return json.loads(self._text)
        except:
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


class HttpClient:
    """HTTP client for making requests and downloading files."""
    
    def __init__(
        self,
        base_url: str = None,
        headers: Dict[str, str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        proxy: str = None,
        verify_proxy: bool = False,
        session: ClientSession = None,
        debug: bool = False,
        auto_detect_proxy: bool = True,
    ):
        """Initialize the HTTP client with configurable options."""
        self.base_url = base_url
        self.headers = headers or {}
        self.timeout = timeout
        self.debug = debug
        self.verify_proxy = verify_proxy
        self.session = session
        
        # Setup proxy with auto-detection if enabled
        # Check if proxy is explicitly provided (including None)
        if 'proxy' in locals():
            self.proxy = proxy  # Use provided proxy value (even if None)
        elif auto_detect_proxy:
            self.proxy = self._detect_system_proxy()
        else:
            self.proxy = None
            
        if self.debug:
            # Set logger to debug level if debug is enabled
            logger.setLevel(logging.DEBUG)

            # Create console handler if not already present
            if not logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
            
            logger.debug(f"Initialized HttpClient with base_url={base_url}, proxy={self.proxy}, verify_proxy={verify_proxy}")
            if self.proxy:
                logger.debug(f"Using proxy: {self.proxy}")
    
    def _detect_system_proxy(self) -> Optional[str]:
        """Detect system proxy settings including Hiddify, Outline, or environment variables."""
        detected_proxy = None
        
        # 1. Check environment variables first
        for env_var in ['https_proxy', 'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY', 'all_proxy', 'ALL_PROXY']:
            if env_var in environ and environ[env_var]:
                detected_proxy = environ[env_var]
                if self.debug:
                    logger.debug(f"Detected proxy from environment variable {env_var}: {detected_proxy}")
                break
        
        if detected_proxy:
            return self._normalize_proxy_url(detected_proxy)
            
        # 2. Check for Hiddify
        hiddify_proxy = self._detect_hiddify_proxy()
        if hiddify_proxy:
            return hiddify_proxy
            
        # 3. Check for Outline
        outline_proxy = self._detect_outline_proxy()
        if outline_proxy:
            return outline_proxy
            
        # 4. Check system proxy settings based on platform
        os_name = platform.system()
        
        if os_name == "Windows":
            return self._detect_windows_proxy()
        elif os_name == "Darwin":
            return self._detect_macos_proxy()
        elif os_name == "Linux":
            return self._detect_linux_proxy()
            
        return None
        
    def _detect_hiddify_proxy(self) -> Optional[str]:
        """Detect Hiddify proxy settings."""
        try:
            # Common locations for Hiddify config
            hiddify_locations = [
                path.expanduser("~/.config/hiddify/config.json"),
                path.expanduser("~/.hiddify/config.json"),
                "/etc/hiddify/config.json",
                "C:\\Program Files\\Hiddify\\config.json",
                "C:\\Program Files (x86)\\Hiddify\\config.json",
            ]
            
            for loc in hiddify_locations:
                if path.exists(loc):
                    with open(loc, 'r') as f:
                        config = json.load(f)
                        if 'proxy' in config and config['proxy'].get('enabled', False):
                            proxy_url = config['proxy'].get('url') or config['proxy'].get('server')
                            if proxy_url:
                                if self.debug:
                                    logger.debug(f"Detected Hiddify proxy: {proxy_url}")
                                return self._normalize_proxy_url(proxy_url)
        except Exception as e:
            if self.debug:
                logger.debug(f"Error detecting Hiddify proxy: {str(e)}")
        
        return None
        
    def _detect_outline_proxy(self) -> Optional[str]:
        """Detect Outline VPN proxy settings."""
        try:
            # Common locations for Outline config
            outline_locations = [
                path.expanduser("~/.config/Outline/settings.json"),
                path.expanduser("~/Library/Application Support/Outline/settings.json"),
                path.expanduser("~\\AppData\\Roaming\\Outline\\settings.json"),
            ]
            
            for loc in outline_locations:
                if path.exists(loc):
                    with open(loc, 'r') as f:
                        config = json.load(f)
                        if 'proxies' in config and config.get('isAutoConnectOn', False):
                            active_proxy = None
                            
                            # Find the active proxy
                            for proxy in config['proxies']:
                                if proxy.get('active', False):
                                    active_proxy = proxy
                                    break
                                    
                            if active_proxy and 'proxyUrl' in active_proxy:
                                proxy_url = active_proxy['proxyUrl']
                                if self.debug:
                                    logger.debug(f"Detected Outline proxy: {proxy_url}")
                                return self._normalize_proxy_url(proxy_url)
        except Exception as e:
            if self.debug:
                logger.debug(f"Error detecting Outline proxy: {str(e)}")
        
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
                if self.debug:
                    logger.debug(f"Detected Windows system proxy: {proxy_server}")
                return self._normalize_proxy_url(proxy_server)
        except Exception as e:
            if self.debug:
                logger.debug(f"Error detecting Windows proxy: {str(e)}")
        
        return None
        
    def _detect_macos_proxy(self) -> Optional[str]:
        """Detect macOS system proxy settings."""
        try:
            # Try to get proxy settings using networksetup command
            result = subprocess.run(
                ["networksetup", "-getwebproxy", "Wi-Fi"], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                output = result.stdout
                enabled_match = re.search(r"Enabled:\s*(Yes|No)", output)
                server_match = re.search(r"Server:\s*([^\n]+)", output)
                port_match = re.search(r"Port:\s*(\d+)", output)
                
                if (enabled_match and enabled_match.group(1) == "Yes" and 
                    server_match and port_match):
                    server = server_match.group(1).strip()
                    port = port_match.group(1).strip()
                    proxy_url = f"http://{server}:{port}"
                    if self.debug:
                        logger.debug(f"Detected macOS system proxy: {proxy_url}")
                    return proxy_url
        except Exception as e:
            if self.debug:
                logger.debug(f"Error detecting macOS proxy: {str(e)}")
        
        return None
        
    def _detect_linux_proxy(self) -> Optional[str]:
        """Detect Linux system proxy settings."""
        try:
            # Try gsettings for GNOME
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.system.proxy", "mode"], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0 and "manual" in result.stdout:
                http_host = subprocess.run(
                    ["gsettings", "get", "org.gnome.system.proxy.http", "host"],
                    capture_output=True,
                    text=True
                ).stdout.strip().strip("'")
                
                http_port = subprocess.run(
                    ["gsettings", "get", "org.gnome.system.proxy.http", "port"],
                    capture_output=True,
                    text=True
                ).stdout.strip()
                
                if http_host and http_port:
                    proxy_url = f"http://{http_host}:{http_port}"
                    if self.debug:
                        logger.debug(f"Detected Linux (GNOME) system proxy: {proxy_url}")
                    return proxy_url
                    
            # Try for KDE
            kde_config = path.expanduser("~/.config/kioslaverc")
            if path.exists(kde_config):
                with open(kde_config, 'r') as f:
                    content = f.read()
                    if "ProxyType=1" in content:  # 1 means manual proxy
                        match = re.search(r"https=([^:]+):(\d+)", content)
                        if match:
                            host, port = match.groups()
                            proxy_url = f"http://{host}:{port}"
                            if self.debug:
                                logger.debug(f"Detected Linux (KDE) system proxy: {proxy_url}")
                            return proxy_url
        except Exception as e:
            if self.debug:
                logger.debug(f"Error detecting Linux proxy: {str(e)}")
        
        return None
        
    def _normalize_proxy_url(self, proxy_url: str) -> str:
        """Normalize proxy URL to a standard format."""
        # Add http:// scheme if missing
        if not re.match(r'^[a-zA-Z]+://', proxy_url):
            proxy_url = f"http://{proxy_url}"
            
        # Parse and validate the URL
        parsed = urlparse(proxy_url)
        
        # Ensure there's a hostname and port
        if not parsed.hostname:
            return None
            
        # Use default port 80 if not specified
        if not parsed.port:
            port = 80 if parsed.scheme == 'http' else 443
            proxy_url = f"{parsed.scheme}://{parsed.hostname}:{port}"
            
        return proxy_url
    
    async def _ensure_session(self, headers: Dict[str, str] = None) -> ClientSession:
        """Ensure there's an active session or create a new one."""
        session = self.session
        if not session or session.closed:
            # Create new session with merged headers only when needed
            session_headers = headers if headers is not None else self.headers
            
            # Create TCP connector with SSL verification settings
            connector = TCPConnector(ssl=None if self.verify_proxy else False)
            self.session = ClientSession(headers=session_headers, connector=connector)
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
        max_retries: int = DEFAULT_MAX_RETRIES,
        close: bool = True,
        **kwargs
    ) -> Response:
        """Make an HTTP request with support for retries."""
        if retries > max_retries:
            raise Exception(f"Maximum retry count ({max_retries}) exceeded")
        
        # Prepare URL (cached to avoid string operations on retries)
        full_url = url if url.startswith("http") else f"{self.base_url or ''}{url}"
        
        # Prepare request options (do this once to avoid repeated lookups)
        request_timeout = ClientTimeout(total=timeout or self.timeout or DEFAULT_TIMEOUT)
        request_headers = headers or self.headers
        request_proxy = proxy or self.proxy
        request_verify = self.verify_proxy if verify is None else verify
        
        # Debug logging
        if self.debug:
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
                session_kwargs = {
                    "timeout": request_timeout,
                    "ssl": ssl_context
                }
                
                # Add proxy if specified
                if request_proxy:
                    session_kwargs["proxy"] = request_proxy
                
                if method == "get":
                    session_kwargs["params"] = params
                else:
                    session_kwargs["json"] = data
                
                session_kwargs.update(kwargs)
                
                request_start_time = time()
                async with session_method(full_url, **session_kwargs) as response:
                    response_time = time() - request_start_time
                    response_obj.status = response.status
                    response_obj.headers = dict(response.headers)
                    
                    # Debug logging for response
                    if self.debug:
                        logger.debug(f"Response: {response.status} ({response_time:.2f}s)")
                        logger.debug(f"Response headers: {dict(response.headers)}")
                    
                    # Handle rate limiting
                    if response.status == 429:
                        retry_after = float(response.headers.get("Retry-After", DEFAULT_RETRY_DELAY))
                        logger.debug(f"Rate limited, retrying after {retry_after}s")
                        await sleep(retry_after)
                        return await self.request(
                            url, method, params, data, headers, timeout, proxy, verify,
                            retries + 1, max_retries, close, **kwargs
                        )
                    
                    if response.status == 404:
                        raise Exception(f"{full_url}: Page not found")
                    
                    try:
                        response_text = await response.text()
                        response_obj._text = response_text
                        if self.debug:
                            logger.debug(f"Response text (preview): {response_text[:200]}...")
                        
                        try:
                            response_obj._json = await response.json()
                        except json.JSONDecodeError:
                            response_obj._json = None
                    except Exception as e:
                        if self.debug:
                            logger.debug(f"Failed to parse response: {str(e)}")
                        response_obj._json = None
            finally:
                if close:
                    if self.debug:
                        logger.debug("Closing session")
                    await session.close()
                    
        except Exception as e:
            if self.debug:
                logger.debug(f"Request error: {str(e)}")
            else:
                logger.error(f"Request error: {str(e)}")
                
            if retries < max_retries:
                logger.debug(f"Retrying request ({retries + 1}/{max_retries})")
                await sleep(DEFAULT_RETRY_DELAY)
                return await self.request(
                    url, method, params, data, headers, timeout, proxy, verify,
                    retries + 1, max_retries, close, **kwargs
                )
            raise
            
        return response_obj
    
    async def get(
        self,
        url: str,
        params: Dict = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        **kwargs
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
        return await self.request(
            url, 
            method="get",
            params=params,
            headers=headers,
            timeout=timeout,
            **kwargs
        )
    
    async def post(
        self,
        url: str,
        data: Dict = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        **kwargs
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
        return await self.request(
            url, 
            method="post",
            data=data,
            headers=headers,
            timeout=timeout,
            **kwargs
        )
    
    async def download_file(
        self,
        **options: Unpack[DownloadOptions],
    ) -> Path:
        """Download a file with progress tracking."""
        # Extract and cache options to avoid repeated dictionary lookups
        url = options.get("url")
        if not url:
            raise ValueError("URL is required for downloading files")
        
        # Debug logging
        if self.debug:
            logger.debug(f"Starting download from: {url}")
            logger.debug(f"Download options: {options}")
            
        folder_path = options.get("folder_path", getenv("DOWNLOAD_FOLDER")) or path.join(path.expanduser("~"), "Downloads")
        if not path.exists(folder_path):
            makedirs(folder_path)
            if self.debug:
                logger.debug(f"Created download directory: {folder_path}")
            
        # Cache callback options
        status_callback = options.get("status_callback")
        done_callback = options.get("done_callback")
        status_parent = options.get("status_parent")
        callback_rate = options.get("callback_rate", DEFAULT_CALLBACK_RATE)
        max_speed = options.get("max_speed")
        request_headers = options.get("headers", self.headers)
        request_proxy = options.get("proxy", self.proxy)
        request_timeout = ClientTimeout(total=options.get("timeout", self.timeout or DEFAULT_TIMEOUT))
        should_close = options.get("close", True)
        
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
            download_kwargs = {
                "timeout": request_timeout,
                "ssl": ssl_context
            }
            
            # Add proxy if specified
            if request_proxy:
                download_kwargs["proxy"] = request_proxy
                
            if self.debug:
                logger.debug(f"Starting download request with kwargs: {download_kwargs}")
                
            async with session.get(url, **download_kwargs) as response:
                if response.status >= 400:
                    error_msg = f"Failed to download file, status code: {response.status}"
                    if self.debug:
                        logger.debug(error_msg)
                    raise Exception(error_msg)
                    
                total_size = int(response.headers.get("Content-Length", -1))
                if self.debug:
                    logger.debug(f"Content-Length: {total_size} bytes")
                
                # Determine filename (optimize the conditional logic)
                filename = options.get("filename")
                if not filename:
                    content_disposition = response.headers.get("Content-Disposition", "")
                    if 'filename="' in content_disposition:
                        filename = content_disposition.split('filename="')[1].split('"')[0]
                    else:
                        filename = url.split("/")[-1].split("?")[0]
                
                file_path = path.join(folder_path, filename)
                if self.debug:
                    logger.debug(f"Downloading to: {file_path}")
                
                # Download the file with optimized buffer handling
                buffer_size = 1024 * 1024  # 1MB buffer
                if self.debug:
                    logger.debug(f"Using buffer size: {buffer_size/1024:.0f}KB")
                    
                async with aopen(file_path, "wb") as f:
                    if self.debug:
                        logger.debug("Download started")
                        
                    while True:
                        # Optimize read logic based on content length
                        if total_size == -1:
                            chunk = await response.content.read(buffer_size)
                            if not chunk:
                                if self.debug:
                                    logger.debug("End of stream reached")
                                break
                        else:
                            # Use non-blocking read when possible
                            chunk = response.content.read_nowait(buffer_size)
                            if not chunk:
                                if downloaded_size >= total_size:
                                    if self.debug:
                                        logger.debug("Download complete")
                                    break
                                await sleep(0.01)  # Small pause to prevent CPU hogging
                                continue
                                
                        # Write chunk to file
                        await f.write(chunk)
                        chunk_size = len(chunk)
                        downloaded_size += chunk_size
                        
                        # Update progress if needed (reduce time() calls)
                        current_time = time()
                        time_since_callback = current_time - last_callback_time
                        
                        if time_since_callback >= callback_rate:
                            # Calculate download stats
                            if time_since_callback > 0:
                                download_speed = (downloaded_size - last_size) / time_since_callback
                            else:
                                download_speed = 0
                                
                            eta = (total_size - downloaded_size) / download_speed if download_speed > 0 and total_size > 0 else 0
                            time_passed = current_time - start_time
                            
                            # Debug logging for download progress
                            if self.debug:
                                percent = (downloaded_size / total_size * 100) if total_size > 0 else 0
                                logger.debug(
                                    f"Downloaded: {downloaded_size/1024/1024:.2f}MB / "
                                    f"{total_size/1024/1024:.2f}MB ({percent:.1f}%) at "
                                    f"{download_speed/1024/1024:.2f}MB/s, ETA: {eta:.0f}s"
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
                            
                            # Process callbacks and status updates
                            await self._process_download_callbacks(status_callback, status_parent, progress_data)
                            
                            # Update tracking variables
                            last_callback_time = current_time
                            last_size = downloaded_size
                            iteration += 1
                            
                        # Limit download speed if requested
                        if max_speed and download_speed > max_speed:
                            sleep_time = chunk_size / max_speed
                            if self.debug:
                                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                            await sleep(sleep_time)
                            
                        # Check if download is complete
                        if total_size != -1 and downloaded_size >= total_size:
                            if self.debug:
                                logger.debug("Download complete (size match)")
                            break
                
                # Verify download size
                if downloaded_size <= 1024:
                    error_msg = "Download failed, no data received."
                    if self.debug:
                        logger.debug(error_msg)
                    raise Exception(error_msg)
                    
                # Process completion
                if status_parent or done_callback:
                    completion_time = time()
                    time_passed = round(completion_time - start_time, 2)
                    
                    if self.debug:
                        logger.debug(f"Download completed in {time_passed}s")
                    
                    # Update status parent if provided
                    if status_parent:
                        completed_data = {
                            "downloaded_size": downloaded_size,
                            "total_size": total_size,
                            "completed": True,
                            "time_passed": time_passed,
                        }
                        
                        if self.debug:
                            logger.debug(f"Updating status parent with completion data")
                        
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
                        
                        if self.debug:
                            logger.debug(f"Calling done callback with data: {done_data}")
                        
                        if iscoroutinefunction(done_callback):
                            await done_callback(**done_data)
                        else:
                            done_callback(**done_data)
                        
        except Exception as e:
            if self.debug:
                logger.debug(f"Download error: {str(e)}")
            else:
                logger.error(f"Download error: {str(e)}")
            raise
        finally:
            if should_close:
                if self.debug:
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

    async def __aenter__(self):
        """Support for async context manager."""
        await self._ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        if self.session and not self.session.closed:
            await self.session.close()
