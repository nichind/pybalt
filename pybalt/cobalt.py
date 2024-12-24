from aiohttp import ClientSession
from dotenv import load_dotenv
from os import getenv, path
from typing import Literal
from asyncio import sleep


class Translator:
    language = getenv("LANG", "en")[:2]
    
    def __init__(self, language: str = None):
        self.language = language if language else self.language

    def translate(self, key: str, language: str = None) -> str:
        """Translate a key from the translation file."""
        language = language or self.language
        file = path.join(path.dirname(__file__), "locales", f"{language}.txt")
        if not path.exists(file):
            if language.upper() != "EN":
                return self.translate(key, "EN")
            return key
        with open(file) as f:
            for line in f:
                if "=" in line and line.split("=")[0].strip().upper() == key.upper():
                    return line[line.index("=") + 1 :].strip()
            if language.upper() != "EN":
                return self.translate(key, "EN")
            return key


class CobaltParameters:
    instance = getenv("COBALT_API_URL", "https://dwnld.nichind.dev") 
    api_key = getenv("COBALT_API_KEY", "b05007aa-bb63-4267-a66e-78f8e10bf9bf")
    user_agent = getenv("COBALT_USER_AGENT", "pybalt/python")
    timeout = getenv("COBALT_TIMEOUT", 12)
    translator = Translator()
    proxy = getenv("COBALT_PROXY", None)
    session = None
    headers = None
    
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Cobalt:
    instance = property(lambda self: self._instance)
    api_key = property(lambda self: self._api_key)
    user_agent = property(lambda self: self._user_agent)
    timeout = property(lambda self: self._timeout)
    translator = property(lambda self: self._translator)
    proxy = property(lambda self: self._proxy)
    session = property(lambda self: self._session)
    headers = property(lambda self: self._headers)
    
    def __init__(self, params: CobaltParameters = CobaltParameters, **kwargs):
        self.__dict__.update(kwargs)
        self.__dict__.update(params.__dict__)
        self._instance = params.instance
        self._api_key = params.api_key
        self._user_agent = params.user_agent
        self._timeout = params.timeout
        self._translator = params.translator
        self._proxy = params.proxy
        self._session = ClientSession(headers=params.headers)
        self._headers = params.headers
            
    async def request(self, url: str, request_type: Literal["get", "post"] = "get", **kwargs) -> str | dict:
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
                        timeout=kwargs.get("timeout", self.timeout),
                    )
                else:
                    response = requests.post(
                        url,
                        data=kwargs.get("data"),
                        headers=kwargs.get("headers", self.headers),
                        proxies=proxies,
                        verify=self.verify_proxy or kwargs.get("verify", False),
                        timeout=kwargs.get("timeout", self.timeout),
                    )
                if response.status_code == 429:
                    kwargs["retries"] = retries + 1
                    return await self.request(path, request_type, **kwargs)
                elif response.status_code == 404:
                    raise "404"
                elif "REMOTE_ADDR = " in response.text:
                    kwargs["retries"] = retries + 1
                    return await self.request(path, request_type, **kwargs)
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
                    session.get(url, params=kwargs.get("params"))
                    if request_type == "get"
                    else session.post(url, data=kwargs.get("data"))
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
        
    async def get(self, url: str, **kwargs):
        return await self.request(url, "get", **kwargs)
    
    async def post(self, url: str, **kwargs):
        return await self.request(url, "post", **kwargs)
        
        
        
load_dotenv()
