from . import client, local as local_instance, config, remux, wrapper
from ..misc.tracker import get_tracker

# Initialize config first to ensure logging is set up
_config = config.Config()

manager = wrapper.InstanceManager()
download = manager.download
detached = manager
remuxer = remux.Remuxer()
remux = remuxer.remux
tracker = get_tracker()

__all__ = ["client", "local_instance", "config", "wrapper", "manager", "download", "remuxer", "remux", "tracker", "_config"]
