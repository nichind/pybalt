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
from .misc.tracker import get_tracker

VERSION = "2025.5.10"

# Initialize tracker
tracker = get_tracker()

# Backwards compatibility
Cobalt = wrapper.Cobalt

__all__ = [VERSION, client, local_instance, config, wrapper, manager, download, remuxer, remux, tracker, Cobalt]
