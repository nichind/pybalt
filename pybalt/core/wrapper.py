from .config import Config
from .client import HttpClient
from .local import LocalInstance
from .remux import remux
import logging


logger = logging.getLogger(__name__)


class InstanceManager:
    def __init__(self, debug: bool = None, config: Config = None, client: HttpClient = HttpClient()):
        self.config = config or Config()
        self.debug = debug or self.config.get("debug", False, "general")
        if self.debug:
            import logging

            logger = logging.getLogger(__name__)
            logger.setLevel(logging.DEBUG)

            # Create console handler if not already present
            if not logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
        self.client = client
        self.local_instance = LocalInstance(config=self.config)
        self.fetched_instances = []

    async def get_instances(self):
        """
        Get instances from the server
        :param kwargs: Parameters to pass to the server
        :return: List of instances
        """
        logger.debug("Getting instances with params:")
        instances = await self.client.get(self.config.get("instance_list_api", "https://instances.cobalt.best/api/instances.json", "instances"))
        logger.debug(f"Instances: {instances}")
        return instances
    