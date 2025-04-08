from .client import HttpClient, DownloadStatus, Response
from .config import get_variable as gv
from .exceptions import RequestError
from typing import Dict, List, Any, Optional, Union, TypedDict
import os
import asyncio
import logging
from urllib.parse import urlparse
from pathlib import Path

logger = logging.getLogger(__name__)

class Instance:
    """Represents a single Cobalt API instance."""
    
    def __init__(
        self,
        api: str,
        protocol: str = "https",
        frontend: str = None,
        score: int = 0,
        trust: int = 0,
        services: Dict[str, Any] = None,
        online: Dict[str, bool] = None,
        version: str = None,
        branch: str = None,
        commit: str = None,
        cors: bool = False,
        name: str = None,
        nodomain: bool = False,
        api_key: str = None,
    ):
        self.api = api
        self.protocol = protocol
        self.frontend = frontend if frontend != "None" else None
        self.score = score
        self.trust = trust
        self.services = services or {}
        self.online = online or {"api": False, "frontend": False}
        self.version = version
        self.branch = branch
        self.commit = commit
        self.cors = cors
        self.name = name if name != "None" else None
        self.nodomain = nodomain
        self.api_key = api_key
        
    @property
    def url(self) -> str:
        """Return the full URL for the API."""
        return f"{self.protocol}://{self.api}"
    
    @property
    def is_online(self) -> bool:
        """Check if the API is online."""
        return self.online.get("api", False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Instance':
        """Create an instance from a dictionary."""
        return cls(
            api=data.get('api'),
            protocol=data.get('protocol', 'https'),
            frontend=data.get('frontend'),
            score=data.get('score', 0),
            trust=data.get('trust', 0),
            services=data.get('services', {}),
            online=data.get('online', {'api': False, 'frontend': False}),
            version=data.get('version'),
            branch=data.get('branch'),
            commit=data.get('commit'),
            cors=data.get('cors', False),
            name=data.get('name'),
            nodomain=data.get('nodomain', False),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the instance to a dictionary."""
        return {
            'api': self.api,
            'protocol': self.protocol,
            'frontend': self.frontend,
            'score': self.score,
            'trust': self.trust,
            'services': self.services,
            'online': self.online,
            'version': self.version,
            'branch': self.branch,
            'commit': self.commit,
            'cors': self.cors,
            'name': self.name,
            'nodomain': self.nodomain,
        }

    def __str__(self) -> str:
        return f"Instance({self.url}, score={self.score}, online={self.is_online})"


class InstanceManager:
    def __init__(self):
        self.client = HttpClient(headers={"User-Agent": "tool, github.com/nichind/pybalt, :)"})
        self.list_api = gv("INSTANCE_LIST_API", "https://instances.cobalt.best/api/instances.json")
        self.instances: List[Instance] = []
        
    async def fetch_instances(self) -> List[Instance]:
        """Fetch the list of instances from the instance list API."""
        response = await self.client.get(self.list_api)
        
        if response.status != 200:
            logger.error(f"Failed to fetch instances: {response.status}")
            return []
            
        try:
            # Parse the JSON response
            instances_data = await response.json()
            
            # Convert each dictionary to a Instance object
            instances = [Instance.from_dict(instance) for instance in instances_data]
            
            # Store the instances and return them
            self.instances = instances
            return instances
        except Exception as e:
            logger.error(f"Error parsing instances: {str(e)}")
            return []
            
    def add_local_instance(self, url: str, api_key: str = None) -> Instance:
        """Add a local instance to the list."""
        # Parse the URL to get the protocol and domain
        parsed = urlparse(url)
        protocol = parsed.scheme or "http"
        api = parsed.netloc or "localhost:9000"
        
        # Create the instance object
        instance = Instance(
            api=api,
            protocol=protocol,
            frontend=None,
            score=100,  # High score for local instance
            trust=2,    # High trust for local instance
            services={},
            online={"api": True, "frontend": False},
            version="local",
            api_key=api_key,
        )
        
        # Add to the beginning of the list (higher priority)
        self.instances.insert(0, instance)
        return instance
        
    def get_best_instance(self, service: str = None) -> Optional[Instance]:
        """Get the best available instance, optionally filtering by service."""
        if not self.instances:
            return None
            
        # Filter instances that are online
        online_instances = [i for i in self.instances if i.is_online]
        
        if not online_instances:
            return None
            
        # Filter by service if specified
        if service:
            service_instances = [
                i for i in online_instances 
                if service in i.services and i.services[service] is True
            ]
            
            if service_instances:
                # Sort by score (descending) and return the best one
                return sorted(service_instances, key=lambda x: x.score, reverse=True)[0]
        
        # If no service specified or no instances with the service,
        # just return the instance with the highest score
        return sorted(online_instances, key=lambda x: x.score, reverse=True)[0]


class DownloadOptions(TypedDict, total=False):
    """Options for downloading media using Cobalt."""
    url: str
    folder_path: Optional[str]
    filename: Optional[str]
    format: Optional[str]
    videoQuality: Optional[str]
    audioQuality: Optional[str]
    filenameStyle: Optional[str]
    remux: Optional[bool]
    youtubeHLS: Optional[bool]
    service: Optional[str]
    status_parent: Optional[Union[Dict, DownloadStatus]]
    status_callback: Optional[Any]
    done_callback: Optional[Any]


class Tunnel:
    def __init__(self, url: str):
        ...

class Cobalt:
    def __init__(
        self,
        debug: bool = False,
        proxy: str = None,
        user_agent: str = None,
        api_key: str = None,
        local_instance: str = None,
        timeout: int = None,
        client: HttpClient = None,
    ):
        """Initialize the Cobalt client with configurable options."""
        # Set up logging
        self.debug = debug
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            
        # Initialize the HTTP client with proxy and user agent
        self.client = client or HttpClient(
            headers={"User-Agent": user_agent or gv("USER_AGENT", "pybalt/tool")},
            proxy=proxy or os.getenv("COBALT_PROXY"),
            debug=debug,
            timeout=timeout,
        )
        
        # Initialize the instance manager
        self.instance_manager = InstanceManager()
        
        # Store API key
        self.api_key = api_key or os.getenv("COBALT_API_KEY")
        
        # Add local instance if specified
        self.local_instance = local_instance or os.getenv("COBALT_LOCAL_INSTANCE")
        self.local_instance_api_key = os.getenv("COBALT_LOCAL_INSTANCE_API_KEY")
        
        # Trigger instance fetching
        self._initialize_task = asyncio.create_task(self._initialize())
        
    async def _initialize(self):
        """Initialize by fetching instances and checking local instance."""
        if self.local_instance:
            self.instance_manager.add_local_instance(
                self.local_instance,
                self.local_instance_api_key or self.api_key
            )
            
        await self.instance_manager.fetch_instances()
        
    async def ensure_initialized(self):
        """Ensure initialization is complete."""
        try:
            await asyncio.wait_for(self._initialize_task, timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Initialization timed out, continuing with available instances")
        
    async def get_tunnel(self, url: str) -> Tunnel:
        # Ensure instances are initialized
        await self.ensure_initialized()
        
        # If no instances are available, try to fetch them again
        if not self.instance_manager.instances:
            await self.instance_manager.fetch_instances()
            
        # If still no instances, raise an error
        if not self.instance_manager.instances:
            raise RequestError("No instances available for tunneling")
        
        # Create tasks to check each instance concurrently
        tasks = []
        for instance in self.instance_manager.instances:
            if instance.is_online:
                tasks.append(self._try_instance_tunnel(instance, url))
        
        # If no tasks were created, raise an error
        if not tasks:
            raise RequestError("No online instances available for tunneling")
        
        # Wait for the first successful response or all to complete
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result:
                    return Tunnel(url=url)
            except Exception as e:
                logger.debug(f"Tunnel request failed: {str(e)}")
        
        # If no successful responses, raise an error
        raise RequestError("Failed to create tunnel - no instances responded successfully")

    async def _try_instance_tunnel(self, instance: Instance, url: str) -> bool:
        """Try to get a tunnel from the specified instance."""
        try:
            # Construct the request URL
            request_url = f"{instance.url}/"
            
            # Set up headers with API key if available
            headers = {}
            api_key = instance.api_key or self.api_key
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            headers["Accept"] = "application/json"
            
            # Make the request
            response = await self.client.post(request_url, data={"url": url}, headers=headers)
            
            # Check for successful response
            if response.status == 200:
                print(await response.text())
                try:
                    # Verify the response is valid JSON
                    await response.json()
                    return True
                except Exception:
                    logger.debug(f"Failed to parse JSON from {instance.url}")
            
            return False
        except Exception as e:
            logger.debug(f"Error with instance {instance.url}: {str(e)}")
            return False