import os
import platform
import subprocess
from pathlib import Path


def open_file(file_path):
    """
    Open a file with the default associated application.
    
    Args:
        file_path: Path to the file
        
    Returns:
        bool: True if successful, False otherwise
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return False
    
    try:
        system = platform.system()
        
        if system == "Windows":
            os.startfile(file_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", str(file_path)], check=False)
        else:  # Linux and other Unix-like systems
            subprocess.run(["xdg-open", str(file_path)], check=False)
        
        return True
    except Exception as e:
        print(f"Error opening file: {e}")
        return False


def show_in_explorer(file_path):
    """
    Show a file in the system's file explorer.
    
    Args:
        file_path: Path to the file
        
    Returns:
        bool: True if successful, False otherwise
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return False
    
    try:
        system = platform.system()
        
        if system == "Windows":
            # On Windows, use explorer to select the file
            subprocess.run(["explorer", "/select,", os.path.normpath(str(file_path))], check=False)
        elif system == "Darwin":  # macOS
            # On macOS, use 'open -R' to reveal the file in Finder
            subprocess.run(["open", "-R", str(file_path)], check=False)
        else:  # Linux and other Unix-like systems
            # Try different file managers in order of preference
            file_managers = [
                ["xdg-open", os.path.dirname(str(file_path))],  # Generic, uses default file manager
                ["nautilus", str(file_path)],  # GNOME
                ["dolphin", "--select", str(file_path)],  # KDE
                ["nemo", str(file_path)],  # Cinnamon
                ["thunar", str(file_path)],  # XFCE
                ["pcmanfm", str(file_path)],  # LXDE
            ]
            
            for manager in file_managers:
                try:
                    subprocess.run(manager, check=False)
                    return True
                except FileNotFoundError:
                    continue
                
            print("Could not find a suitable file manager")
            return False
        
        return True
    except Exception as e:
        print(f"Error showing file in explorer: {e}")
        return False
