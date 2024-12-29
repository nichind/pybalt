from aiohttp import ClientSession
from .misc import Translator, DefaultCallbacks
from typing import Literal, Union, Dict, Callable, Coroutine, Unpack, TypedDict
from asyncio import sleep, iscoroutinefunction
from .constants import DEFAULT_TIMEOUT
from time import time
from os import path, getenv, makedirs
from . import exceptions
from aiofiles import open as aopen


class Response:
    text = None
    json = None
    headers = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return self.text if not self.json else self.json

    def __str__(self):
        return str(self.text)


class _DownloadOptions(TypedDict, total=False):
    url: str
    folder_path: str
    filename: str
    status_callback: Callable | Coroutine
    done_callback: Callable | Coroutine
    status_parent: str
    headers: Dict[str, str]
    timeout: int
    callback_rate: int


class RequestClient:
    api_key: str = None
    user_agent: str = None
    timeout: int = None
    translator: Translator = None
    proxy: str = None
    session: ClientSession = None
    headers: Dict[str, str] = None
    verify_proxy: bool = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    async def request(
        self, url: str, request_type: Literal["get", "post"] = "get", **kwargs
    ) -> Response:
        retries = kwargs.get("retries", 0)
        if retries > 5:
            raise ""
        if self.proxy or kwargs.get("proxy", False):
            import requests

            requests.packages.urllib3.disable_warnings()  # Disable SSL warnings on proxy

            url = (
                f"{kwargs.get('base_url', self.base_url)}{url}"
                if not url.startswith("http")
                else url
            )
            proxies = {
                "http": self.proxy or kwargs.get("proxy", False),
                "https": self.proxy or kwargs.get("proxy", False),
            }
            if request_type == "get":
                response = requests.get(
                    url,
                    params=kwargs.get("params"),
                    headers=kwargs.get("headers", self.headers),
                    proxies=proxies,
                    verify=self.verify_proxy or kwargs.get("verify", False),
                    timeout=kwargs.get("timeout", self.timeout or DEFAULT_TIMEOUT),
                )
            else:
                response = requests.post(
                    url,
                    json=kwargs.get("data"),
                    headers=kwargs.get("headers", self.headers),
                    proxies=proxies,
                    verify=self.verify_proxy or kwargs.get("verify", False),
                    timeout=kwargs.get("timeout", self.timeout or DEFAULT_TIMEOUT),
                )
            if response.status_code == 429:
                kwargs["retries"] = retries + 1
                return await self.request(url, request_type, **kwargs)
            elif response.status_code == 404:
                raise exceptions.PageNotFound(f"{url}: Page not found")
            elif "REMOTE_ADDR = " in response.text:
                kwargs["retries"] = retries + 1
                return await self.request(url, request_type, **kwargs)
            _response = Response(
                headers=response.headers,
            )
            try:
                _response.text = response.text
                _response.json = response.json()
            except Exception:
                ...
            return _response
        else:
            session = (
                ClientSession(
                    headers=kwargs.get("headers", self.headers),
                )
                if not self.session or self.session.closed
                else self.session
            )
            try:
                url = (
                    f"{kwargs.get('base_url', self.base_url)}{url}"
                    if not url.startswith("http")
                    else url
                )
                async with (
                    session.get(
                        url,
                        params=kwargs.get("params"),
                        timeout=kwargs.get("timeout", self.timeout or DEFAULT_TIMEOUT),
                    )
                    if request_type == "get"
                    else session.post(
                        url,
                        json=kwargs.get("data"),
                        timeout=kwargs.get("timeout", self.timeout or DEFAULT_TIMEOUT),
                    )
                ) as response:
                    if response.status == 429:
                        retry_after = response.headers.get("Retry-After", 1)
                        await sleep(float(retry_after))
                        kwargs["retries"] = retries + 1
                        return await self.request(url, request_type, **kwargs)
                    elif response.status == 404:
                        raise exceptions.PageNotFound(f"{url}: Page not found")
                    _response = Response(headers=response.headers)
                    try:
                        _response.text = await response.text()
                        _response.json = await response.json()
                    except Exception:
                        ...
                    return _response
                kwargs["retries"] = retries + 1
                await sleep(1)
                return await self.request(url, request_type, **kwargs)
            finally:
                if kwargs.get("close", True):
                    await session.close()

    async def get(self, url: str, **kwargs) -> Response:
        response = await self.request(url, "get", **kwargs)
        if kwargs.get("text", False) is True:
            return response.text
        return response.json if response.json else response.text

    async def post(self, url: str, **kwargs) -> Response:
        response = await self.request(url, "post", **kwargs)
        if kwargs.get("text", False) is True:
            return response.text
        return response.json if response.json else response.text

    async def download_from_url(
        self,
        **options: Unpack[_DownloadOptions],
    ) -> str:
        start_at = int(time())
        total_size = 0
        destination_folder = options.get(
            "folder_path", getenv("COBALT_DOWNLOAD_FOLDER", None)
        ) or path.join(path.expanduser("~"), "Downloads")
        if not path.exists(destination_folder):
            makedirs(destination_folder)
        if not options.get("status_callback"):
            options["status_callback"] = DefaultCallbacks.status_callback
        if not options.get("done_callback"):
            options["done_callback"] = DefaultCallbacks.done_callback
        session = (
            ClientSession(
                headers=options.get("headers", self.headers),
            )
            if not self.session or self.session.closed
            else self.session
        )
        try:
            async with session.get(
                options.get("url"),
            ) as resp:
                filename = options.get(
                    "filename",
                    (resp.headers.get("Content-Disposition"))
                    .split('filename="')[1]
                    .split('"')[0],
                )
                file_path = path.join(
                    destination_folder,
                    filename,
                )
                async with aopen(file_path, "wb") as f:
                    last_callback = 0
                    last_size = 0
                    while True:
                        chunk = await resp.content.read(1024 * 64)
                        if not chunk:
                            break
                        await f.write(chunk)
                        total_size += len(chunk)
                        if time() - last_callback >= 1:
                            download_speed = (total_size - last_size) / (time() - last_callback)
                            last_size = total_size
                            last_callback = time()
                            print(f"Downloading {filename} | time passed: {round(time() - start_at, 2)}s, {total_size / 1024 / 1024 : .2f} MB | {download_speed / 1024 : .2f} KB/s", end="\r")
                            if iscoroutinefunction(options.get("status_callback")):
                                await (options.get("status_callback"))(
                                    total_size=total_size,
                                    start_at=start_at,
                                    time_passed=round(time() - start_at, 2),
                                    file_path=file_path,
                                    filename=filename,
                                    download_speed=download_speed,
                                    )
                            else:
                                (options.get("status_callback"))(
                                    total_size=total_size,
                                    start_at=start_at,
                                    time_passed=round(time() - start_at, 2),
                                    file_path=file_path,
                                    filename=filename,
                                    download_speed=download_speed,
                                )
                            if options.get("status_parent", None):
                                options.get("status_parent").update(
                                    {
                                        "total_size": total_size,
                                        "start_at": start_at,
                                        "file_path": file_path,
                                    }
                                )
            if options.get("done_callback", None):
                if iscoroutinefunction(options.get("done_callback")):
                    await (options.get("done_callback"))(
                        total_size=total_size,
                        start_at=start_at,
                        time_passed=round(time() - start_at, 2),
                        file_path=file_path,
                        filename=filename,
                    )
                else:
                    (options.get("done_callback"))(
                        total_size=total_size,
                        start_at=start_at,
                        time_passed=round(time() - start_at, 2),
                        file_path=file_path,
                        filename=filename,
                    )
        except Exception as exc:
            raise exc
        finally:
            if options.get("close", True):
                await session.close()
        return file_path

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in self.headers:
            self.headers[name] = value
