from asyncio import run
from .core.wrapper import CobaltRequestParams, InstanceManager
from .core.client import DownloadOptions
from typing import _LiteralGenericAlias, List, Optional
from os.path import exists, isfile
from time import time
import argparse
import sys
from pathlib import Path
from . import VERSION
from .core import config
from .core.remux import Remuxer

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
    download_group.add_argument("-fp", "--folder-path", type=str, help="Download folder path")
    download_group.add_argument("-t", "--timeout", type=int, help="Download timeout in seconds")
    download_group.add_argument("-pt", "--progressive-timeout", action="store_true", help="Enable progressive timeout")
    
    # Add instance management options
    instance_group = parser.add_argument_group('Instance management')
    instance_group.add_argument("-li", "--list-instances", action="store_true", help="List available instances")
    instance_group.add_argument("-ai", "--add-instance", nargs=2, metavar=('URL', 'API_KEY'), help="Add a new instance with URL and optional API key")
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
            **cobalt_params
        )
        
        if args.remux and result and isinstance(result, Path):
            # Remux the file if requested and download succeeded
            print(f"Remuxing: {result}")
            remuxed = Remuxer().remux(result, keep_original=args.keep_original)
            print(f"Remuxed to: {remuxed}")
        
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
        url, api_key = args.add_instance
        if not api_key or api_key.lower() == "none":
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
        import threading
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

async def main_async():
    parser = create_parser()
    args = parser.parse_args()
    
    # Show version information
    if args.version:
        print(f"pybalt version {VERSION}")
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
    else:
        parser.print_help()

def main():
    run(main_async())

if __name__ == "__main__":
    main()
