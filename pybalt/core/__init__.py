from . import client, local as local_instance, config, remux, wrapper

manager = wrapper.InstanceManager()
download = manager.download
remuxer = remux.Remuxer()
remux = remuxer.remux

__all__ = [client, local_instance, config, wrapper, manager, download, remuxer, remux]
