class BaseException(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"{self.__class__.__name__}: {self.message}"


class FailedToGetTunnel(BaseException): ...


class NoUrlInTunnelResponse(BaseException): ...


class InvalidURL(BaseException): ...


class FetchError(BaseException): ...


class PageNotFound(BaseException): ...


class AllInstancesFailed(BaseException): ...


class DownloadError(BaseException): ...
