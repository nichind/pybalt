from asyncio import run
from .core.wrapper import CobaltRequestParams, InstanceManager
from typing import _LiteralGenericAlias
from os.path import exists, isfile
import argparse
from pathlib import Path
from . import VERSION
from .core import config
from .core.remux import Remuxer
import threading
import subprocess
import os
import signal
import sys
import requests
import time
from .misc import api

def create_parser():
    parser = argparse.ArgumentParser(description="pybalt - Your ultimate tool & python module to download videos and audio from various platforms. Supports YouTube, Instagram, Twitter (X), Reddit, TikTok, BiliBili & More! Powered by cobalt instances")
    parser.add_argument("positional", nargs="?", type=str, help="URL to download, file path to remux, or text file with URLs")
    
    # Add arguments based on CobaltRequestParams
    for key, value in CobaltRequestParams.__annotations__.items():
        try:
            if value is bool:
                if not any(arg.startswith(f"-{key[0]}") for arg in parser._option_string_actions):
                    parser.add_argument(
                        f"-{key[0]}{''.join([x for i, x in enumerate(key) if i > 0 and x.isupper()])}",
                        f"--{key}",
                        action="store_true",
                        help=f"Enable {key} option"
                    )
                else:
                    parser.add_argument(
                        f"--{key}",
                        action="store_true",
                        help=f"Enable {key} option"
                    )
            else:
                if not any(arg.startswith(f"-{key[0]}") for arg in parser._option_string_actions):
                    parser.add_argument(
                        f"-{key[0]}{''.join([x for i, x in enumerate(key) if i > 0 and x.isupper()])}",
                        f"--{key}",
                        type=value if not isinstance(value, _LiteralGenericAlias) else str,
                        choices=None if not isinstance(value, _LiteralGenericAlias) else value.__args__,
                        help=f"Set {key} option"
                    )
                else:
                    parser.add_argument(
                        f"--{key}",
                        type=value if not isinstance(value, _LiteralGenericAlias) else str,
                        choices=None if not isinstance(value, _LiteralGenericAlias) else value.__args__,
                        help=f"Set {key} option"
                    )
        except argparse.ArgumentError:
            if value is bool:
                parser.add_argument(f"--{key}", action="store_true", help=f"Enable {key} option")
            else:
                parser.add_argument(f"--{key}", type=value, help=f"Set {key} option")
    
    # Add download specific options
    download_group = parser.add_argument_group('Download options')
    download_group.add_argument("-r", "--remux", action="store_true", help="Remux downloaded file")
    download_group.add_argument("-ko", "--keep-original", action="store_true", help="Keep original file after remuxing")
    download_group.add_argument("-o", "--open", action="store_true", help="Open file after download")
    download_group.add_argument("-s", "--show", action="store_true", help="Show file in default viewer after download")
    download_group.add_argument("-fp", "--folder-path", type=str, help="Download folder path")
    download_group.add_argument("-t", "--timeout", type=int, help="Download timeout in seconds")
    download_group.add_argument("-pt", "--progressive-timeout", action="store_true", help="Enable progressive timeout")
    
    # Add instance management options
    instance_group = parser.add_argument_group('Instance management')
    instance_group.add_argument("-li", "--list-instances", action="store_true", help="List available instances")
    instance_group.add_argument("-ai", "--add-instance", nargs='+', metavar=('URL', 'API_KEY'), help="Add a new instance with URL and optional API key")
    instance_group.add_argument("-ri", "--remove-instance", type=int, help="Remove instance by number")
    
    # Configuration commands
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument("-c", "--config", action="store_true", help="Open configuration interface")
    config_group.add_argument("-gc", "--get-config", nargs=2, metavar=('SECTION', 'OPTION'), help="Get configuration value")
    config_group.add_argument("-sc", "--set-config", nargs=3, metavar=('SECTION', 'OPTION', 'VALUE'), help="Set configuration value")
    
    # Version and info
    parser.add_argument("-v", "--version", action="store_true", help="Show version information")
    
    # Local instance management
    local_group = parser.add_argument_group('Local instance')
    local_group.add_argument("-ls", "--local-setup", action="store_true", help="Setup local instance")
    local_group.add_argument("-lstart", "--local-start", action="store_true", help="Start local instance")
    local_group.add_argument("-lstop", "--local-stop", action="store_true", help="Stop local instance")
    local_group.add_argument("-lrestart", "--local-restart", action="store_true", help="Restart local instance")
    local_group.add_argument("-lstatus", "--local-status", action="store_true", help="Check local instance status")
    
    # Add API management options
    api_group = parser.add_argument_group('API management')
    api_group.add_argument("--api-start", action="store_true", help="Start the API server in detached mode")
    api_group.add_argument("--api-stop", action="store_true", help="Stop the running API server")
    api_group.add_argument("--api-status", action="store_true", help="Check if the API server is running")
    api_group.add_argument("--api-port", type=int, help="Set the port for the API server")

    # Misc arguments
    misc_group = parser.add_argument_group('Miscellaneous')
    misc_group.add_argument("-y", "--yes", action="store_true", help="Automatically answer yes to prompts")
    
    return parser

async def download_url(url, args):
    # Remove any trailing slashes and backslashes
    url = url.strip().replace("\\", "")
    
    """Download a URL with the given arguments"""
    print(f"Downloading: {url}")
    
    # Prepare Cobalt parameters
    cobalt_params = {}
    for key in CobaltRequestParams.__annotations__:
        if hasattr(args, key) and getattr(args, key) is not None:
            cobalt_params[key] = getattr(args, key)
    
    # Prepare download options
    download_opts = {
        "remux": args.remux,
    }
    
    if args.folder_path:
        download_opts["folder_path"] = args.folder_path
    if args.timeout:
        download_opts["timeout"] = args.timeout
    if args.progressive_timeout:
        download_opts["progressive_timeout"] = args.progressive_timeout
    
    # Initialize the manager and download
    manager = InstanceManager()
    try:
        del cobalt_params["url"]
        result = await manager.download(
            url=url,
            **download_opts,
            **cobalt_params,
        )
        
        if result and isinstance(result, Path):
            if args.remux:
                # Remux the file if requested and download succeeded
                print(f"Remuxing: {result}")
                remuxed = Remuxer().remux(result, keep_original=args.keep_original)
                print(f"Remuxed to: {remuxed}")
                result = remuxed  # Update result to point to the remuxed file
            
            # Handle the open and show arguments
            if args.open:
                from .utils.file_operations import open_file
                if open_file(result):
                    print(f"Opened file: {result}")
                else:
                    print(f"Failed to open file: {result}")
            
            if args.show:
                from .utils.file_operations import show_in_explorer
                if show_in_explorer(result):
                    print(f"Showing file in explorer: {result}")
                else:
                    print(f"Failed to show file in explorer: {result}")
        
        return result
    except Exception as e:
        print(f"Error downloading {url}: {str(e)}")
        return None

async def process_input(args):
    """Process input based on positional argument type"""
    if args.positional:
        if isfile(args.positional) and args.positional.endswith('.txt'):
            # It's a text file with URLs
            with open(args.positional, 'r') as f:
                urls = [line.strip() for line in f.readlines() if line.strip()]
            
            results = []
            for url in urls:
                result = await download_url(url, args)
                if result:
                    results.append(result)
            return results
            
        elif exists(args.positional) and not args.url:
            # It's a file to remux
            # if args.remux:
            print(f"Remuxing file: {args.positional}")
            result = Remuxer().remux(args.positional, keep_original=args.keep_original)
            print(f"Remuxed to: {result}")
            
            # Handle the open and show arguments for remuxed files
            if args.open:
                from .utils.file_operations import open_file
                if open_file(result):
                    print(f"Opened file: {result}")
                else:
                    print(f"Failed to open file: {result}")
            
            if args.show:
                from .utils.file_operations import show_in_explorer
                if show_in_explorer(result):
                    print(f"Showing file in explorer: {result}")
                else:
                    print(f"Failed to show file in explorer: {result}")
                    
            return result
            # else:
            #     print("File exists but --remux not specified. Add --remux to remux the file.")
        else:
            # Treat as URL
            args.url = args.positional
            return await download_url(args.url, args)
    elif args.url:
        return await download_url(args.url, args)

async def handle_local_instance(args):
    """Handle local instance commands"""
    from .core.local import LocalInstance
    
    local = LocalInstance()
    
    if args.local_setup:
        local.setup_wizard()
    elif args.local_start:
        try:
            if local.start_instance():
                port = local.config.get_as_number("local_instance_port", 9000, "local")
                print(f"Local instance started on http://localhost:{port}/")
        except Exception as e:
            print(f"Error starting local instance: {e}")
    elif args.local_stop:
        try:
            if local.stop_instance():
                print("Local instance stopped")
        except Exception as e:
            print(f"Error stopping local instance: {e}")
    elif args.local_restart:
        try:
            if local.restart_instance():
                port = local.config.get_as_number("local_instance_port", 9000, "local")
                print(f"Local instance restarted on http://localhost:{port}/")
        except Exception as e:
            print(f"Error restarting local instance: {e}")
    elif args.local_status:
        status = local.get_instance_status()
        if status.get("running"):
            port = local.config.get_as_number("local_instance_port", 9000, "local")
            print(f"Local instance is running on http://localhost:{port}/")
        else:
            print("Local instance is not running")
            if "message" in status:
                print(status["message"])

async def handle_instance_management(args):
    """Handle instance management commands"""
    cfg = config.Config()
    
    if args.list_instances:
        instances = cfg.get_user_instances()
        print("User-defined instances:")
        
        if instances:
            for instance in instances:
                print(f"  #{instance['number']}: {instance['url']}")
                if instance['api_key']:
                    print(f"     API Key: {instance['api_key']}")
        else:
            print("  No user-defined instances")
            
    elif args.add_instance:
        url = args.add_instance[0]
        api_key = args.add_instance[1] if len(args.add_instance) > 1 else ""
        
        clean_url = url.strip().replace("http://", "").replace("https://", "")
        if clean_url in [instance.get("url", "").strip().replace("http://", "").replace("https://", "") for instance in cfg.get_user_instances()]:
            # If --yes flag is provided, skip confirmation
            if not args.yes:
                response = input("There's already an instance with the same URL in the config, still add? Skip the confirmation with --yes (Y/n): ").lower()
                if response not in ["", "y"]:  # Default to yes if empty
                    return
        
        if api_key and api_key.lower() == "none":
            api_key = ""
        
        num = cfg.add_user_instance(url, api_key)
        print(f"Added instance #{num}: {url}")
        
    elif args.remove_instance is not None:
        if cfg.remove_user_instance(args.remove_instance):
            print(f"Removed instance #{args.remove_instance}")
        else:
            print(f"No instance found with number {args.remove_instance}")

async def handle_config(args):
    """Handle configuration commands"""
    cfg = config.Config()
    
    if args.config:
        # Open configuration interface
        thread = threading.Thread(target=config.main, kwargs={"force_cli": True}, daemon=True)
        thread.start()
        thread.join()
        # config.main()
    elif args.get_config:
        section, option = args.get_config
        value = cfg.get(option, section=section)
        print(f"{section}.{option} = {value}")
    elif args.set_config:
        section, option, value = args.set_config
        cfg.set(option, value, section)
        print(f"Set {section}.{option} to '{value}'")

def get_api_pid_file():
    """Get the path to the file storing the API process ID"""
    cfg = config.Config()
    config_dir = Path(cfg._get_config_dir())
    return config_dir / "api_pid.txt"

def save_api_pid(pid, port):
    """Save the API process ID and port to a file"""
    pid_file = get_api_pid_file()
    with open(pid_file, "w") as f:
        f.write(f"{pid}:{port}")

def get_api_info():
    """Get the saved API process ID and port"""
    pid_file = get_api_pid_file()
    if not pid_file.exists():
        return None, None
    
    try:
        with open(pid_file, "r") as f:
            content = f.read().strip()
            if ":" in content:
                pid_str, port_str = content.split(":", 1)
                return int(pid_str), int(port_str)
            else:
                return int(content), None
    except (ValueError, FileNotFoundError):
        return None, None

def is_process_running(pid):
    """Check if a process with the given PID is running"""
    if pid is None:
        return False
    
    try:
        if sys.platform == "win32":
            # Windows - use tasklist
            output = subprocess.check_output(f"tasklist /FI \"PID eq {pid}\"", shell=True)
            return str(pid) in output.decode()
        else:
            # Unix-like - check /proc or send signal 0
            os.kill(pid, 0)
            return True
    except (subprocess.SubprocessError, OSError, ProcessLookupError):
        return False

async def handle_api_commands(args):
    """Handle API management commands"""
    cfg = config.Config()
    
    if args.api_port:
        # Update the API port in the config
        cfg.set("port", str(args.api_port), "api")
        print(f"API port set to {args.api_port}")
        
        # If no other API command, return after setting the port
        if not any([args.api_start, args.api_stop, args.api_status]):
            return
    
    if args.api_start:
        # Check if the API is already running
        pid, port = get_api_info()
        if pid and is_process_running(pid):
            print(f"API is already running on port {port} (PID: {pid})")
            return
        
        # Get the port to use
        port = args.api_port or cfg.get_as_number("port", 8009, "api")
        
        # Start the API in a new process
        cmd = [sys.executable, "-m", "pybalt.misc.api", str(port)]
        
        if sys.platform == "win32":
            # On Windows, use CREATE_NEW_PROCESS_GROUP flag to create a detached process
            process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
        else:
            # On Unix-like systems, use start_new_session
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
        
        # Save the PID for later use
        save_api_pid(process.pid, port)
        
        # Wait a moment for the server to start
        time.sleep(1)
        
        # Check if the process is still running (didn't immediately exit with an error)
        if is_process_running(process.pid):
            print(f"API server started on port {port} (PID: {process.pid})")
            print(f"You can access it at http://localhost:{port}")
            print(f"Web UI available at http://localhost:{port}/ui")
        else:
            # If not running, try to capture any error output
            _, stderr = process.communicate(timeout=1)
            print(f"Failed to start API server: {stderr.decode().strip()}")
    
    elif args.api_stop:
        pid, port = get_api_info()
        if not pid:
            print("No running API server found")
            return
        
        if not is_process_running(pid):
            print("API server is not running")
            # Clean up stale PID file
            if get_api_pid_file().exists():
                get_api_pid_file().unlink()
            return
        
        # Stop the process
        try:
            if sys.platform == "win32":
                # On Windows, use taskkill
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True)
            else:
                # On Unix-like systems, use kill
                os.kill(pid, signal.SIGTERM)
                # Wait a moment for graceful shutdown
                time.sleep(1)
                # Check if it's still running and force kill if needed
                if is_process_running(pid):
                    os.kill(pid, signal.SIGKILL)
            
            print(f"API server stopped (PID: {pid})")
            
            # Remove the PID file
            if get_api_pid_file().exists():
                get_api_pid_file().unlink()
        except (subprocess.SubprocessError, OSError) as e:
            print(f"Failed to stop API server: {e}")
    
    elif args.api_status:
        pid, port = get_api_info()
        if not pid:
            print("No API server information found")
            return
        
        if not is_process_running(pid):
            print("API server is not running")
            # Clean up stale PID file
            if get_api_pid_file().exists():
                get_api_pid_file().unlink()
            return
        
        # Check if the API is actually responding
        try:
            response = requests.get(f"http://localhost:{port}/", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"API server is running on port {port} (PID: {pid})")
                print(f"Version: {data.get('version', 'Unknown')}")
                print(f"Instance count: {data.get('instance_count', 'Unknown')}")
                print(f"Web UI available at http://localhost:{port}/ui")
            else:
                print(f"API server is running on port {port} (PID: {pid}) but returned status code {response.status_code}")
        except requests.RequestException:
            print(f"API server process is running (PID: {pid}) but not responding")

def check_for_updates():
    """Check for updates to pybalt on PyPI"""
    cfg = config.Config()
    
    # Skip if update checking is disabled
    if not cfg.get("update_check_enabled", True, "misc"):
        return None
    
    # Check the last update check time
    last_check = int(cfg.get("last_update_check", 0, "misc"))
    interval = int(cfg.get("update_check_interval", 86400, "misc"))
    current_time = int(time.time())
    
    # Skip if we've checked recently
    if current_time - last_check < interval:
        return None
    
    try:
        # Set a short timeout to prevent blocking the application
        response = requests.get("https://pypi.org/pypi/pybalt/json", timeout=3)
        
        # Update the last check time regardless of success
        cfg.set("last_update_check", str(current_time), "misc")
        
        if response.status_code == 200:
            data = response.json()
            latest_version = data["info"]["version"]
            
            if latest_version != VERSION:
                return latest_version
    except (requests.RequestException, KeyError, ValueError):
        # Don't bother the user if the check fails
        pass
    
    return None

def show_thank_you():
    """Show a thank you message at most once every 3 hours"""
    cfg = config.Config()
    
    # Check the last thank you time
    last_thank = int(cfg.get("last_thank", 0, "misc"))
    current_time = int(time.time())
    
    # Show message if it's been more than 3 hours (10800 seconds)
    if current_time - last_thank >= 10800:
        print("Thank you for using pybalt! 💖 If you find it useful, consider starring the repository: https://github.com/nichind/pybalt or sponsoring the developer: https://liberapay.com/nichind")
        
        # Update the last thank you time
        cfg.set("last_thank", str(current_time), "misc")

async def main_async():
    parser = create_parser()
    args = parser.parse_args()
    
    # Check for updates (max once per update_check_interval, default 24h)
    latest_version = check_for_updates()
    if latest_version:
        print(f"A new version of pybalt is available: {latest_version}")
        print(f"You're currently using version {VERSION}")
        print("Update with: pip install --upgrade pybalt")
    
    # Show version information
    if args.version:
        print(f"pybalt version {VERSION}")
        return
    
    # Handle API management
    if any([args.api_start, args.api_stop, args.api_status, args.api_port]):
        await handle_api_commands(args)
        return
    
    # Handle local instance management
    if any([args.local_setup, args.local_start, args.local_stop, args.local_restart, args.local_status]):
        await handle_local_instance(args)
        return
    
    # Handle instance management
    if any([args.list_instances, args.add_instance, args.remove_instance is not None]):
        await handle_instance_management(args)
        return
    
    # Handle configuration
    if any([args.config, args.get_config, args.set_config]):
        await handle_config(args)
        return
    
    # Handle download/remux
    if args.positional or args.url:
        await process_input(args)
        show_thank_you()
    else:
        parser.print_help()

    

def main():
    run(main_async())

if __name__ == "__main__":
    main()
