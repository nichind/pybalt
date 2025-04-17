from . import core
from .core import (
    client,
    local_instance,
    config,
    remux,
    wrapper,
    manager,
    download,
    remuxer,
)

VERSION = "2025.4.3"

__all__ = [
    VERSION,
    core,
    client,
    local_instance,
    config,
    wrapper,
    manager,
    download,
    remuxer,
    remux,
]
