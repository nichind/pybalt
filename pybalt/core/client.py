from aiohttp import ClientSession
from .misc import Translator
from typing import Literal, Union, Dict, Callable, Coroutine
from asyncio import sleep, iscoroutinefunction
from .constants import DEFAULT_TIMEOUT
from time import time
from os import path, getenv, makedirs


class Response:
    text = None
    json = None
    headers = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return self.text if not self.json else self.json

    def __str__(self):
        return self.text


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
            try:
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
                        data=kwargs.get("data"),
                        headers=kwargs.get("headers", self.headers),
                        proxies=proxies,
                        verify=self.verify_proxy or kwargs.get("verify", False),
                        timeout=kwargs.get("timeout", self.timeout or DEFAULT_TIMEOUT),
                    )
                if response.status_code == 429:
                    kwargs["retries"] = retries + 1
                    return await self.request(url, request_type, **kwargs)
                elif response.status_code == 404:
                    raise "404"
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
            except requests.exceptions.ProxyError as exc:
                raise "prx"
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
                        raise "404"
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
        url: str,
        folder_path: str = None,
        status_callback: Callable | Coroutine = None,
        done_callback: Callable | Coroutine = None,
        status_parent=None,
        **kwargs,
    ):
        start_at = time()
        total_size = 0
        destination_folder = folder_path or path.join(path.expanduser("~"), "Downloads")
        if not path.exists(destination_folder):
            makedirs(destination_folder)
        session = (
            ClientSession(
                headers=kwargs.get("headers", self.headers),
                timeout=kwargs.get("timeout", self.timeout or DEFAULT_TIMEOUT),
            )
            if not self.session or self.session.closed
            else self.session
        )
        async with session.get(url) as resp:
            while True:
                chunk = await resp.content.read(1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if status_callback:
                    if iscoroutinefunction(status_callback):
                        await status_callback(total_size, start_at, status_parent)
                    else:
                        status_callback(total_size, start_at, status_parent)
                with open(destination_folder, "ab") as f:
                    f.write(chunk)
        if done_callback:
            if iscoroutinefunction(done_callback):
                await done_callback(total_size, start_at, status_parent)
            else:
                done_callback(total_size, start_at, status_parent)

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in self.headers:
            self.headers[name] = value
