import os
import platform
import subprocess
import json
from pathlib import Path
import time
import yaml
import click
from typing import Dict, Optional, List, Any

from .config import Config
from .client import HttpClient


class LocalInstanceError(Exception):
    """Exception raised for errors in the local instance operations."""

    pass


class LocalInstance:
    """
    Manages a local Cobalt instance using Docker.
    Provides functionality to install, start, stop, and configure the instance.
    """

    def __init__(self, config: Config = None):
        """
        Initialize the LocalInstance with configuration.

        Args:
            config: Config instance to use. If None, a new one will be created.
        """
        self.config = config or Config()
        self.instance_dir = self._get_instance_dir()
        self.docker_compose_path = self.instance_dir / "docker-compose.yml"
        self.cookies_path = self.instance_dir / "cookies.json"
        self.api_key = None

    @property
    def api_url(self) -> str:
        """
        Get the API URL for the local instance.

        Returns:
            The API URL as a string.
        """
        port = self.config.get_as_number("local_instance_port", 8009, "local")
        return f"http://localhost:{port}/"

    def _get_instance_dir(self) -> Path:
        """Get the directory for the local instance files."""
        config_dir = Path(self.config._get_config_path()).parent
        return config_dir / "cobalt_instance"

    def check_docker_installed(self) -> bool:
        """
        Check if Docker and Docker Compose are installed.

        Returns:
            True if Docker and Docker Compose are installed, False otherwise.
        """
        try:
            # Check Docker
            subprocess.run(
                ["docker", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Check Docker Compose
            compose_commands = [
                ["docker", "compose", "--version"],  # Docker Compose V2
                ["docker-compose", "--version"],  # Docker Compose V1
            ]

            for cmd in compose_commands:
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    return True
                except (subprocess.SubprocessError, FileNotFoundError):
                    continue

            # If we get here, Docker Compose wasn't found
            return False

        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def check_docker_permissions(self) -> bool:
        """
        Check if the current user has permissions to use Docker.

        Returns:
            True if the current user has Docker permissions, False otherwise.
        """
        try:
            subprocess.run(
                ["docker", "info"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return True
        except subprocess.SubprocessError as e:
            return False

    def _handle_docker_permission_error(self, error_text: str) -> None:
        """
        Handle Docker permission errors with helpful guidance.

        Args:
            error_text: The error text from Docker

        Raises:
            LocalInstanceError with helpful instructions
        """
        if "permission denied" in error_text and "/var/run/docker.sock" in error_text:
            message = """
Docker permission denied error detected!

This typically happens when your user doesn't have permission to access the Docker daemon.
To fix this issue:

1. Add your user to the 'docker' group:
   sudo usermod -aG docker $USER

2. Log out and log back in, or restart your system.

3. Verify it worked with:
   docker info
"""
            raise LocalInstanceError(message)
        else:
            raise LocalInstanceError(f"Docker error: {error_text}")

    def get_docker_compose_command(self) -> List[str]:
        """
        Get the appropriate Docker Compose command based on what's installed.

        Returns:
            List containing the docker compose command.
        """
        # Try Docker Compose V2
        try:
            subprocess.run(
                ["docker", "compose", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return ["docker", "compose"]
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # Try Docker Compose V1
        try:
            subprocess.run(
                ["docker-compose", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return ["docker-compose"]
        except (subprocess.SubprocessError, FileNotFoundError):
            raise LocalInstanceError("Docker Compose not found. Please install Docker Compose.")

    def create_instance_dir(self) -> None:
        """Create the directory for the local instance if it doesn't exist."""
        os.makedirs(self.instance_dir, exist_ok=True)

    def _detect_proxy(self) -> Optional[str]:
        """
        Detect system proxy settings using HttpClient.

        Returns:
            Detected proxy URL or None if not found
        """
        try:
            client = HttpClient(config=self.config, debug=False)
            return client.proxy
        except Exception as e:
            # If there's an error detecting the proxy, just return None
            return None

    def generate_docker_compose_file(self) -> None:
        """
        Generate a docker-compose.yml file based on the current configuration.
        """
        port = self.config.get_as_number("local_instance_port", 9000, "local")
        # Keep using localhost for API_URL
        api_url = f"http://localhost:{port}/"

        # Get additional settings from config
        api_auth_required = self.config.get("api_auth_required", "0", "local")
        api_key = self.config.get("api_key", "", "local")
        duration_limit = self.config.get("duration_limit", "10800", "local")
        cors_wildcard = self.config.get("cors_wildcard", "1", "local")
        disabled_services = self.config.get("disabled_services", "", "local")

        # Get proxy settings
        use_pc_proxy = self.config.get("use_pc_proxy", "False", "local")
        proxy_url = self.config.get("proxy_url", "", "local")

        # Check for proxy if enabled but not explicitly set
        if use_pc_proxy and not proxy_url:
            proxy_url = self._detect_proxy()

        # If proxy URL contains localhost, replace with host.docker.internal for container networking
        if proxy_url and ("localhost" in proxy_url or "127.0.0.1" in proxy_url):
            proxy_url = proxy_url.replace("localhost", "host.docker.internal")
            proxy_url = proxy_url.replace("127.0.0.1", "host.docker.internal")
            proxy_url = proxy_url.replace("http://", "")

        # Create a dict for the docker-compose.yml file
        compose_data = {
            "services": {
                "cobalt-api": {
                    "image": "ghcr.io/imputnet/cobalt:10",
                    "init": True,
                    "read_only": True,
                    "restart": "unless-stopped",
                    "container_name": "cobalt-api",
                    "ports": [f"{port}:{port}/tcp"],
                    "environment": {
                        "API_URL": api_url,
                        "API_PORT": port,
                    },
                    "labels": ["com.centurylinklabs.watchtower.scope=cobalt"],
                },
                "watchtower": {
                    "image": "ghcr.io/containrrr/watchtower",
                    "restart": "unless-stopped",
                    "command": "--cleanup --scope cobalt --interval 900 --include-restarting",
                    "volumes": ["/var/run/docker.sock:/var/run/docker.sock"],
                },
            }
        }

        # Add extra_hosts configuration for Linux to enable host.docker.internal
        if platform.system() == "Linux":
            compose_data["services"]["cobalt-api"]["extra_hosts"] = ["host.docker.internal:host-gateway"]

        # Add optional environment variables
        if api_auth_required == "1" and api_key:
            api_keys_file = self.instance_dir / "keys.json"
            compose_data["services"]["cobalt-api"]["environment"]["API_KEY_URL"] = "file:///keys.json"
            compose_data["services"]["cobalt-api"]["environment"]["API_AUTH_REQUIRED"] = "1"

            # Add the volume mount for the keys.json file
            if "volumes" not in compose_data["services"]["cobalt-api"]:
                compose_data["services"]["cobalt-api"]["volumes"] = []
            compose_data["services"]["cobalt-api"]["volumes"].append("./keys.json:/keys.json")

            # Create the keys.json file
            self._create_keys_file(api_key, api_keys_file)

        if duration_limit:
            compose_data["services"]["cobalt-api"]["environment"]["DURATION_LIMIT"] = duration_limit

        if cors_wildcard:
            compose_data["services"]["cobalt-api"]["environment"]["CORS_WILDCARD"] = cors_wildcard

        if disabled_services:
            compose_data["services"]["cobalt-api"]["environment"]["DISABLED_SERVICES"] = disabled_services

        # Add proxy environment variable if proxy is configured
        if proxy_url:
            compose_data["services"]["cobalt-api"]["environment"]["API_EXTERNAL_PROXY"] = proxy_url

        # Save the docker-compose.yml file
        with open(self.docker_compose_path, "w") as f:
            yaml.dump(compose_data, f, default_flow_style=False)

    def _create_keys_file(self, api_key: str, keys_file_path: Path) -> None:
        """
        Create a keys.json file with the API key.

        Args:
            api_key: The API key to use
            keys_file_path: Path to save the keys.json file
        """
        keys_data = {
            "keys": {
                "default": {
                    "key": api_key,
                    "name": "PyBalt Local Instance Key",
                    "ratelimit": 100,
                }
            }
        }

        with open(keys_file_path, "w") as f:
            json.dump(keys_data, f, indent=2)

    def create_cookies_file(self, cookies_content: str = "{}") -> None:
        """
        Create a cookies.json file for the instance.

        Args:
            cookies_content: JSON string with cookies content
        """
        try:
            # Parse the content to validate it's a proper JSON
            json_content = json.loads(cookies_content)

            # Write the content to the file
            with open(self.cookies_path, "w") as f:
                json.dump(json_content, f, indent=2)

            # Update the docker-compose file to include the cookies
            if os.path.exists(self.docker_compose_path):
                # Read the existing compose file
                with open(self.docker_compose_path, "r") as f:
                    compose_data = yaml.safe_load(f)

                # Add the cookie path environment variable
                compose_data["services"]["cobalt-api"]["environment"]["COOKIE_PATH"] = "/cookies.json"

                # Add the volume mount for the cookies.json file
                if "volumes" not in compose_data["services"]["cobalt-api"]:
                    compose_data["services"]["cobalt-api"]["volumes"] = []

                # Check if the mount already exists
                cookie_mount = "./cookies.json:/cookies.json"
                if cookie_mount not in compose_data["services"]["cobalt-api"]["volumes"]:
                    compose_data["services"]["cobalt-api"]["volumes"].append(cookie_mount)

                # Save the updated compose file
                with open(self.docker_compose_path, "w") as f:
                    yaml.dump(compose_data, f, default_flow_style=False)

        except json.JSONDecodeError:
            raise LocalInstanceError("Invalid JSON content for cookies.json")

    def start_instance(self) -> bool:
        """
        Start the local instance.

        Returns:
            True if the instance was successfully started, False otherwise.
        """
        if not os.path.exists(self.docker_compose_path):
            raise LocalInstanceError("Docker Compose file not found. Please run setup first.")

        # Check Docker permissions first on Linux
        if platform.system() == "Linux" and not self.check_docker_permissions():
            self._handle_docker_permission_error("permission denied while trying to connect to the Docker daemon socket")

        try:
            compose_cmd = self.get_docker_compose_command()
            result = subprocess.run(
                compose_cmd + ["-f", str(self.docker_compose_path), "up", "-d"],
                check=True,
                cwd=self.instance_dir,
                stderr=subprocess.PIPE,
                text=True,
            )
            return True
        except subprocess.SubprocessError as e:
            error_text = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
            if "permission denied" in error_text and "/var/run/docker.sock" in error_text:
                self._handle_docker_permission_error(error_text)
            raise LocalInstanceError(f"Failed to start instance: {e}")

    def stop_instance(self) -> bool:
        """
        Stop the local instance.

        Returns:
            True if the instance was successfully stopped, False otherwise.
        """
        if not os.path.exists(self.docker_compose_path):
            raise LocalInstanceError("Docker Compose file not found. Please run setup first.")

        try:
            compose_cmd = self.get_docker_compose_command()
            subprocess.run(
                compose_cmd + ["-f", str(self.docker_compose_path), "down"],
                check=True,
                cwd=self.instance_dir,
            )
            return True
        except subprocess.SubprocessError as e:
            raise LocalInstanceError(f"Failed to stop instance: {e}")

    def restart_instance(self) -> bool:
        """
        Restart the local instance.

        Returns:
            True if the instance was successfully restarted, False otherwise.
        """
        self.stop_instance()
        time.sleep(3)  # Give it a moment to fully shut down
        return self.start_instance()

    def get_instance_status(self) -> Dict[str, Any]:
        """
        Get the status of the local instance.

        Returns:
            Dict with status information
        """
        if not os.path.exists(self.docker_compose_path):
            return {"running": False, "message": "Instance not set up"}

        try:
            compose_cmd = self.get_docker_compose_command()
            result = subprocess.run(
                compose_cmd + ["-f", str(self.docker_compose_path), "ps", "--format", "json"],
                check=True,
                capture_output=True,
                text=True,
                cwd=self.instance_dir,
            )

            # Parse the output to determine if the container is running
            output = result.stdout.strip()
            containers = []

            try:
                # Try to parse as JSON array or object
                if output:
                    # For Docker Compose v2, output may be a JSON array
                    if output.startswith("["):
                        containers = json.loads(output)
                    # For some Docker Compose versions, output might be one JSON object per line
                    else:
                        containers = [json.loads(line) for line in output.split("\n") if line.strip()]
            except json.JSONDecodeError:
                # Fallback to non-JSON format parsing
                ps_result = subprocess.run(
                    compose_cmd + ["-f", str(self.docker_compose_path), "ps"],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=self.instance_dir,
                )
                return {
                    "running": "cobalt-api" in ps_result.stdout and "Up" in ps_result.stdout,
                    "raw_output": ps_result.stdout,
                }

            # Check if any container is the cobalt-api and is running
            for container in containers:
                if container.get("Name") == "cobalt-api" or container.get("Service") == "cobalt-api":
                    state = container.get("State", "")
                    if isinstance(state, str) and "running" in state.lower():
                        return {"running": True, "container_info": container}

            return {"running": False, "containers": containers}
        except subprocess.SubprocessError as e:
            return {"running": False, "error": str(e)}

    def setup_wizard(self) -> None:
        """
        Interactive setup wizard for the local instance.
        """
        click.echo("Setting up a local Cobalt instance...")

        # Check if Docker is installed
        if not self.check_docker_installed():
            click.echo("Docker or Docker Compose is not installed.")
            install_help = """
Please install Docker and Docker Compose before continuing:
- Windows/macOS: Install Docker Desktop from https://www.docker.com/products/docker-desktop
- Linux: Follow the instructions at https://docs.docker.com/engine/install/
"""
            click.echo(install_help)
            if not click.confirm("Continue anyway?", default=False):
                click.echo("Setup aborted.")
                return

        # Create the instance directory
        self.create_instance_dir()

        # Collect configuration
        port = click.prompt("Enter port number for the instance", default=9000, type=int)
        api_auth = click.confirm("Enable API key authentication?", default=False)
        api_key = ""
        if api_auth:
            api_key = click.prompt("Enter API key (leave empty to generate one)", default="")
            if not api_key:
                # Generate a random API key
                import uuid

                api_key = str(uuid.uuid4())
                click.echo(f"Generated API key: {api_key}")

        duration_limit = click.prompt(
            "Enter maximum duration limit in seconds (e.g., 10800 = 3 hours)",
            default=10800,
            type=int,
        )

        disabled_services = click.prompt(
            "Enter comma-separated list of services to disable (leave empty for none)",
            default="",
        )

        # Save settings to config
        self.config.set("local_instance_port", str(port), "local")
        self.config.set("api_auth_required", "1" if api_auth else "0", "local")
        if api_key:
            self.config.set("api_key", api_key, "local")
        self.config.set("duration_limit", str(duration_limit), "local")
        self.config.set("disabled_services", disabled_services, "local")

        # Ask about proxy settings
        use_pc_proxy = click.confirm("Use system proxy for the local instance?", default=False)

        proxy_url = ""
        if use_pc_proxy:
            detected_proxy = self._detect_proxy()
            if detected_proxy:
                click.echo(f"Detected system proxy: {detected_proxy}")
                use_detected = click.confirm("Use this proxy?", default=True)
                if use_detected:
                    proxy_url = detected_proxy

            if not detected_proxy or not use_detected:
                proxy_url = click.prompt("Enter proxy URL (leave empty for none)", default="")

        # Save proxy settings to config
        self.config.set("use_pc_proxy", "True" if use_pc_proxy else "False", "local")
        if proxy_url:
            self.config.set("proxy_url", proxy_url, "local")

        # Generate docker-compose.yml
        self.generate_docker_compose_file()

        # Ask about cookies
        if click.confirm("Do you want to set up cookies for authenticated services?", default=False):
            click.echo("You can paste a JSON object with cookies or provide a path to a cookies.json file.")
            cookie_source = click.prompt("Enter cookies JSON or file path (leave empty to skip)", default="")

            if cookie_source:
                if os.path.exists(cookie_source):
                    # It's a file path
                    try:
                        with open(cookie_source, "r") as f:
                            cookies_content = f.read()
                        self.create_cookies_file(cookies_content)
                        click.echo("Cookies file created from the provided file.")
                    except Exception as e:
                        click.echo(f"Error reading cookies file: {e}")
                else:
                    # It's a JSON string
                    try:
                        self.create_cookies_file(cookie_source)
                        click.echo("Cookies file created from the provided JSON.")
                    except Exception as e:
                        click.echo(f"Error creating cookies file: {e}")

        # Ask to start the instance
        if click.confirm("Start the instance now?", default=True):
            try:
                self.start_instance()
                click.echo(f"Local Cobalt instance started on http://localhost:{port}/")
                click.echo(f"Configuration directory: {self.instance_dir}")
            except LocalInstanceError as e:
                click.echo(f"Failed to start instance: {e}")
        else:
            click.echo("Setup completed. You can start the instance later.")
            click.echo(f"Configuration directory: {self.instance_dir}")


@click.group()
def cli():
    """Manage local Cobalt instance."""
    pass


@cli.command()
def setup():
    """Set up a new local Cobalt instance."""
    local_instance = LocalInstance()
    local_instance.setup_wizard()


@cli.command()
def start():
    """Start the local Cobalt instance."""
    local_instance = LocalInstance()
    try:
        if local_instance.start_instance():
            port = local_instance.config.get_as_number("local_instance_port", 9000, "local")
            click.echo(f"Local Cobalt instance started on http://localhost:{port}/")
    except LocalInstanceError as e:
        click.echo(f"Error: {e}")


@cli.command()
def stop():
    """Stop the local Cobalt instance."""
    local_instance = LocalInstance()
    try:
        if local_instance.stop_instance():
            click.echo("Local Cobalt instance stopped.")
    except LocalInstanceError as e:
        click.echo(f"Error: {e}")


@cli.command()
def restart():
    """Restart the local Cobalt instance."""
    local_instance = LocalInstance()
    try:
        if local_instance.restart_instance():
            port = local_instance.config.get_as_number("local_instance_port", 9000, "local")
            click.echo(f"Local Cobalt instance restarted on http://localhost:{port}/")
    except LocalInstanceError as e:
        click.echo(f"Error: {e}")


@cli.command()
def status():
    """Check the status of the local Cobalt instance."""
    local_instance = LocalInstance()
    status_info = local_instance.get_instance_status()

    if status_info.get("running"):
        port = local_instance.config.get_as_number("local_instance_port", 9000, "local")
        click.echo(f"Local Cobalt instance is running on http://localhost:{port}/")
    else:
        click.echo("Local Cobalt instance is not running.")
        if "message" in status_info:
            click.echo(status_info["message"])


@cli.command()
def location():
    """Show the location of the local instance files."""
    local_instance = LocalInstance()
    click.echo(f"Local instance directory: {local_instance.instance_dir}")
    click.echo(f"Docker Compose file: {local_instance.docker_compose_path}")
    if os.path.exists(local_instance.cookies_path):
        click.echo(f"Cookies file: {local_instance.cookies_path}")


@cli.command()
@click.option("--port", type=int, help="Port number for the instance")
@click.option("--auth/--no-auth", default=None, help="Enable/disable API key authentication")
@click.option("--api-key", help="API key for authentication")
@click.option("--duration-limit", type=int, help="Maximum duration limit in seconds")
@click.option("--disabled-services", help="Comma-separated list of services to disable")
@click.option("--use-proxy/--no-proxy", default=None, help="Use system proxy for the instance")
@click.option("--proxy-url", help="Proxy URL for the instance")
def config(port, auth, api_key, duration_limit, disabled_services, use_proxy, proxy_url):
    """Configure the local instance settings."""
    local_instance = LocalInstance()
    config = local_instance.config
    changed = False

    if port is not None:
        config.set("local_instance_port", str(port), "local")
        changed = True

    if auth is not None:
        config.set("api_auth_required", "1" if auth else "0", "local")
        changed = True

    if api_key is not None:
        config.set("api_key", api_key, "local")
        changed = True

    if duration_limit is not None:
        config.set("duration_limit", str(duration_limit), "local")
        changed = True

    if disabled_services is not None:
        config.set("disabled_services", disabled_services, "local")
        changed = True

    if use_proxy is not None:
        config.set("use_pc_proxy", "True" if use_proxy else "False", "local")
        changed = True

    if proxy_url is not None:
        config.set("proxy_url", proxy_url, "local")
        changed = True

    if changed:
        # Regenerate the docker-compose file with new settings
        local_instance.generate_docker_compose_file()
        click.echo("Configuration updated. You need to restart the instance for changes to take effect.")
    else:
        # Show current configuration
        click.echo("Current configuration:")
        click.echo(f"Port: {config.get_as_number('local_instance_port', 9000, 'local')}")
        click.echo(f"Auth required: {config.get('api_auth_required', '0', 'local') == '1'}")
        click.echo(f"API key: {config.get('api_key', '', 'local')}")
        click.echo(f"Duration limit: {config.get('duration_limit', '10800', 'local')} seconds")
        click.echo(f"Disabled services: {config.get('disabled_services', '', 'local')}")
        click.echo(f"Use system proxy: {config.get('use_pc_proxy', 'False', 'local') == 'True'}")
        click.echo(f"Proxy URL: {config.get('proxy_url', '', 'local')}")


@cli.command()
@click.option("--json", "json_input", is_flag=True, help="Input is JSON content")
@click.argument("source", required=False)
def cookies(json_input, source):
    """Set up cookies for authenticated services."""
    local_instance = LocalInstance()

    if not source:
        # No source provided - check if a cookies file already exists
        if os.path.exists(local_instance.cookies_path):
            click.echo(f"Cookies file exists at: {local_instance.cookies_path}")
            with open(local_instance.cookies_path, "r") as f:
                click.echo(f.read())
        else:
            click.echo("No cookies file found. Use this command with a file path or JSON content to create one.")
        return

    try:
        if json_input:
            # Source is JSON content
            local_instance.create_cookies_file(source)
        elif os.path.exists(source):
            # Source is a file path
            with open(source, "r") as f:
                cookies_content = f.read()
            local_instance.create_cookies_file(cookies_content)
        else:
            click.echo("Error: File not found. If you're providing JSON content directly, use the --json flag.")
            return

        click.echo("Cookies file created successfully.")
        click.echo("You need to restart the instance for changes to take effect.")
    except Exception as e:
        click.echo(f"Error creating cookies file: {e}")


@cli.command()
def update():
    """Update the local Cobalt instance to the latest version."""
    local_instance = LocalInstance()
    status_info = local_instance.get_instance_status()

    if not status_info.get("running"):
        click.echo("Local instance is not running. Starting it first...")
        try:
            local_instance.start_instance()
        except LocalInstanceError as e:
            click.echo(f"Error starting instance: {e}")
            return

    click.echo("Forcing update of Cobalt containers...")
    try:
        compose_cmd = local_instance.get_docker_compose_command()
        # Pull latest images
        subprocess.run(
            compose_cmd + ["-f", str(local_instance.docker_compose_path), "pull"],
            check=True,
            cwd=local_instance.instance_dir,
        )

        # Restart with new images
        subprocess.run(
            compose_cmd
            + [
                "-f",
                str(local_instance.docker_compose_path),
                "up",
                "-d",
                "--force-recreate",
            ],
            check=True,
            cwd=local_instance.instance_dir,
        )

        click.echo("Local Cobalt instance updated successfully.")
    except subprocess.SubprocessError as e:
        click.echo(f"Error updating instance: {e}")


def main():
    """Main entry point for the local instance management CLI."""
    cli()


if __name__ == "__main__":
    main()
