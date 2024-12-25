from aiohttp import ClientSession
from .misc import Translator
from typing import Literal, Union, Dict
from asyncio import sleep
from .constants import DEFAULT_TIMEOUT


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
    ) -> Union[str, Dict[str, str]]:
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
                if kwargs.get("text", False):
                    return response.text
                try:
                    return response.json()
                except Exception:
                    return response.text
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
                    try:
                        if kwargs.get("text", False):
                            return await response.text()
                        return await response.json()
                    except Exception:
                        return await response.text()
                kwargs["retries"] = retries + 1
                await sleep(1)
                return await self.request(url, request_type, **kwargs)
            finally:
                if kwargs.get("close", True):
                    await session.close()

    async def get(self, url: str, **kwargs) -> Union[str, Dict[str, str]]:
        return await self.request(url, "get", **kwargs)

    async def post(self, url: str, **kwargs) -> Union[str, Dict[str, str]]:
        return await self.request(url, "post", **kwargs)
