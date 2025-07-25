from .core import (
    local_instance,
    config,
    network,
    remux,
    wrapper,
    manager,
    download,
    remuxer,
)
from .misc.tracker import get_tracker

# pybalt version
VERSION = "2025.7.1"

# Initialize tracker
tracker = get_tracker()

# Backwards compatibility
Cobalt = wrapper.Cobalt
client = network

__all__ = ["VERSION", "network", "local_instance", "config", "wrapper", "manager", "download", "remuxer", "remux", "tracker", "Cobalt"]
