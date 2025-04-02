class HttpClientError(Exception):
    """Base exception for HTTP client errors."""
    pass

class RequestError(HttpClientError):
    """Exception raised for errors during HTTP requests."""
    pass

class PageNotFound(RequestError):
    """Exception raised when a 404 response is received."""
    pass

class RateLimitExceeded(RequestError):
    """Exception raised when rate limits are exceeded."""
    pass

class DownloadError(HttpClientError):
    """Exception raised for errors during file downloads."""
    pass
