import os
import time
import shutil
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import contextlib
import sys

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_BLACK = "\033[40m"

class DownloadInfo:
    """Stores information about a download in progress"""
    def __init__(self, url: str, filename: str):
        self.url = url
        self.filename = filename
        self.downloaded_size = 0
        self.total_size = -1
        self.speed = 0
        self.eta = 0
        self.start_time = time.time()
        self.file_path = ""
        self.completed = False
        self.last_update = time.time()
        self.last_size = 0

class Tracker:
    """Tracks and displays download progress in the terminal"""
    def __init__(self, config=None):
        # Import here to avoid circular imports
        from pybalt.core.config import Config
        # Store config instance
        self.config = config or Config()
        self.downloads: Dict[str, DownloadInfo] = {}
        self.lock = threading.RLock()
        self._last_draw_time = 0
        self._min_redraw_interval = 0.1  # seconds
        self._is_drawing = False
        self._visible = False
        self._spinning_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self._spin_index = 0
        self._running = False
        self._draw_thread = None
        self._terminal_size = shutil.get_terminal_size()
        self._terminal_width = self._terminal_size.columns
        self._terminal_height = self._terminal_size.lines
        self._max_visible_downloads = self._get_max_visible_items()
        
    def _get_max_visible_items(self):
        """Get the maximum number of visible download items based on config or terminal height"""
        try:
            # Explicitly use display section and provide default
            config_max = self.config.get_as_number("max_visible_items", 0, section="display")
            if config_max > 0:
                return config_max
        except Exception as e:
            # Fallback if config access fails
            return max(1, int(self._terminal_height * 0.25))
        return max(1, int(self._terminal_height * 0.25))
        
    @property
    def enabled(self):
        """Check if the tracker is enabled in config"""
        try:
            return self.config.get("enable_tracker", True, section="display")
        except Exception:
            # Fallback if config access fails
            return True
    
    @property
    def colors_enabled(self):
        """Check if colors are enabled in config"""
        try:
            return self.config.get("enable_colors", True, section="display")
        except Exception:
            # Fallback if config access fails
            return True
        
    @property
    def should_show_path(self):
        """Check if the full path should be shown"""
        try:
            return self.config.get("show_path", True, section="display")
        except Exception:
            # Fallback if config access fails
            return True
    
    @property
    def max_filename_length(self):
        """Get the maximum length for displayed filenames"""
        try:
            return self.config.get_as_number("max_filename_length", 25, section="display")
        except Exception:
            # Fallback if config access fails 
            return 25
    
    @property
    def progress_bar_width(self):
        """Get the width of progress bars"""
        try:
            return self.config.get_as_number("progress_bar_width", 20, section="display")
        except Exception:
            # Fallback if config access fails
            return 20
    
    def colored(self, text, color):
        """Apply color to text if colors are enabled"""
        if not self.colors_enabled:
            return text
        return f"{color}{text}{Colors.RESET}"
    
    def start(self):
        """Start the tracker display thread"""
        if not self.enabled or self._running:
            return
            
        self._running = True
        self._draw_thread = threading.Thread(target=self._draw_loop, daemon=True)
        self._draw_thread.start()
    
    def stop(self):
        """Stop the tracker display thread"""
        self._running = False
        if self._draw_thread:
            self._draw_thread.join(timeout=1.0)
            self._draw_thread = None
        self._clear_display()
        
    def _draw_loop(self):
        """Main drawing loop that updates the display"""
        while self._running:
            try:
                if self.downloads and self.enabled:
                    self._update_terminal_size()
                    self._draw_downloads()
                    self._visible = True
                elif self._visible:
                    self._clear_display()
                    self._visible = False
            except Exception as e:
                # Silently handle errors to prevent crashes
                pass
            time.sleep(0.1)
    
    def _update_terminal_size(self):
        """Update the terminal size information"""
        try:
            self._terminal_size = shutil.get_terminal_size()
            self._terminal_width = self._terminal_size.columns
            self._terminal_height = self._terminal_size.lines
            self._max_visible_downloads = self._get_max_visible_items()
        except Exception:
            # Default values if we can't get terminal size
            self._terminal_width = 80
            self._terminal_height = 24
            self._max_visible_downloads = 5
    
    def _clear_display(self):
        """Clear the tracker display from the terminal"""
        if not self._visible:
            return
            
        # Move cursor to bottom and clear tracker area
        with self.lock:
            num_active = len([d for d in self.downloads.values() if not d.completed])
            lines_to_clear = min(num_active, self._max_visible_downloads)
            if lines_to_clear > 0:
                # ANSI escape sequences to clear lines and position cursor
                sys_write = sys.stdout.write
                sys_write("\033[0J")  # Clear from cursor to end of screen
                sys.stdout.flush()
    
    def _get_spinner(self):
        """Get the next frame of the spinner animation with color"""
        char = self._spinning_chars[self._spin_index]
        self._spin_index = (self._spin_index + 1) % len(self._spinning_chars)
        return self.colored(char, Colors.BRIGHT_CYAN)
    
    def _format_size(self, size_bytes):
        """Format size in bytes to human-readable format with color"""
        if size_bytes < 0:
            return self.colored("Unknown", Colors.BRIGHT_BLACK)
        elif size_bytes < 1024:
            return self.colored(f"{size_bytes} B", Colors.BRIGHT_WHITE)
        elif size_bytes < 1024 * 1024:
            return self.colored(f"{size_bytes/1024:.1f} KB", Colors.BRIGHT_WHITE)
        elif size_bytes < 1024 * 1024 * 1024:
            return self.colored(f"{size_bytes/(1024*1024):.1f} MB", Colors.BRIGHT_WHITE)
        else:
            return self.colored(f"{size_bytes/(1024*1024*1024):.2f} GB", Colors.BRIGHT_WHITE)
    
    def _format_speed(self, speed_bytes):
        """Format speed in bytes/second to human-readable format with color"""
        if speed_bytes < 1024:
            return self.colored(f"{speed_bytes:.0f} B/s", Colors.BRIGHT_YELLOW)
        elif speed_bytes < 1024 * 1024:
            return self.colored(f"{speed_bytes/1024:.1f} KB/s", Colors.BRIGHT_YELLOW)
        else:
            return self.colored(f"{speed_bytes/(1024*1024):.2f} MB/s", Colors.BRIGHT_YELLOW)
    
    def _format_time(self, seconds):
        """Format time in seconds to human-readable format with color"""
        if seconds < 60:
            return self.colored(f"{seconds:.0f}s", Colors.BRIGHT_MAGENTA)
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return self.colored(f"{minutes}m {secs}s", Colors.BRIGHT_MAGENTA)
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return self.colored(f"{hours}h {minutes}m", Colors.BRIGHT_MAGENTA)
    
    def _draw_progress_bar(self, percentage, width=None):
        """Draw a colorful progress bar with the given percentage"""
        if width is None:
            width = self.progress_bar_width
            
        completed_width = int(width * percentage / 100)
        remaining_width = width - completed_width
        
        # Gradient effect for progress bar based on completion percentage
        if percentage < 30:
            color = Colors.RED
        elif percentage < 70:
            color = Colors.YELLOW
        else:
            color = Colors.GREEN
        
        if self.colors_enabled:
            return f"[{color}{'━' * completed_width}{Colors.BRIGHT_BLACK}{'━' * remaining_width}{Colors.RESET}]"
        else:
            return f"[{'=' * completed_width}{' ' * remaining_width}]"
    
    def _truncate_filename(self, filename, max_length=None):
        """Truncate filename to fit in the display"""
        if max_length is None:
            max_length = self.max_filename_length
            
        if len(filename) <= max_length:
            return filename
        # Keep extension
        name, ext = os.path.splitext(filename)
        trunc_len = max_length - len(ext) - 3  # 3 for '...'
        if trunc_len < 1:
            return filename[:max_length-3] + "..."
        return name[:trunc_len] + "..." + ext
    
    def _draw_downloads(self):
        """Draw the tracker display at the bottom of the terminal"""
        now = time.time()
        if now - self._last_draw_time < self._min_redraw_interval:
            return
            
        self._last_draw_time = now
        
        with self.lock:
            # Update download speeds
            for download_id, download in self.downloads.items():
                if not download.completed:
                    elapsed = now - download.last_update
                    if elapsed > 0:
                        download.speed = (download.downloaded_size - download.last_size) / elapsed
                        download.last_size = download.downloaded_size
                        download.last_update = now
                    
                    if download.total_size > 0:
                        remaining_bytes = download.total_size - download.downloaded_size
                        if download.speed > 0:
                            download.eta = remaining_bytes / download.speed
                        else:
                            download.eta = 0
            
            # Sort downloads - active first, then by start time
            sorted_downloads = sorted(
                self.downloads.values(),
                key=lambda d: (d.completed, -d.start_time)
            )
            
            # Only show active downloads
            active_downloads = [d for d in sorted_downloads if not d.completed]
            visible_downloads = active_downloads[:self._max_visible_downloads-1]
            hidden_downloads = active_downloads[self._max_visible_downloads-1:] if len(active_downloads) > self._max_visible_downloads-1 else []
            
            # Prepare output lines
            output_lines = []
            
            # Add visible download lines
            for download in visible_downloads:
                spinner = self._get_spinner() if not download.completed else self.colored("✓", Colors.BRIGHT_GREEN)
                filename = self.colored(self._truncate_filename(download.filename), Colors.BOLD + Colors.BRIGHT_BLUE)
                
                # Format download status line
                if download.total_size > 0:
                    # Show progress bar for known size
                    percentage = min(100, int(download.downloaded_size / download.total_size * 100))
                    progress_bar = self._draw_progress_bar(percentage)
                    
                    size_info = f"{self._format_size(download.downloaded_size)}/{self._format_size(download.total_size)}"
                    eta_info = f"ETA: {self._format_time(download.eta)}" if download.eta > 0 else ""
                    percentage_str = self.colored(f"{percentage}%", Colors.BOLD)
                    
                    status_line = f"{spinner} {filename} {progress_bar} {percentage_str} {size_info} {self._format_speed(download.speed)} {eta_info}"
                else:
                    # No progress bar for unknown size
                    elapsed = time.time() - download.start_time
                    clock_emoji = self.colored("🕒", Colors.BRIGHT_CYAN) if self.colors_enabled else "🕒"
                    status_line = f"{spinner} {filename} {self._format_size(download.downloaded_size)} {clock_emoji} {self._format_time(elapsed)} {self._format_speed(download.speed)}"
                
                # Truncate to terminal width
                status_line = status_line[:self._terminal_width-1]
                output_lines.append(status_line)
            
            # Add summary line for hidden downloads if needed
            if hidden_downloads:
                total_speed = sum(d.speed for d in hidden_downloads)
                total_downloaded = sum(d.downloaded_size for d in hidden_downloads)
                plus_sign = self.colored("+", Colors.BRIGHT_GREEN)
                num_hidden = self.colored(f"{len(hidden_downloads)} more downloads:", Colors.BOLD)
                summary_line = f"{plus_sign} {num_hidden} {self._format_size(total_downloaded)} total @ {self._format_speed(total_speed)}"
                summary_line = summary_line[:self._terminal_width-1]
                output_lines.append(summary_line)
            
            # Draw to terminal
            if output_lines:
                # Save cursor position
                sys.stdout.write("\033[s")
                
                # Move cursor to the bottom of the terminal
                sys.stdout.write(f"\033[{self._terminal_height};0H")
                
                # Clear lines for the tracker
                sys.stdout.write("\033[0J")
                
                # Print output lines from bottom to top
                for i, line in enumerate(reversed(output_lines)):
                    row = self._terminal_height - i
                    sys.stdout.write(f"\033[{row};0H{line}")
                
                # Restore cursor position
                sys.stdout.write("\033[u")
                sys.stdout.flush()
                
    def add_download(self, download_id, url, filename):
        """Add a new download to be tracked"""
        if not self.enabled:
            return
            
        with self.lock:
            self.downloads[download_id] = DownloadInfo(url, filename)
            if not self._running:
                self.start()
        
    def update_download(self, download_id, **kwargs):
        """Update the status of a download"""
        if not self.enabled or download_id not in self.downloads:
            return
            
        with self.lock:
            download = self.downloads[download_id]
            for key, value in kwargs.items():
                if hasattr(download, key):
                    setattr(download, key, value)
    
    def complete_download(self, download_id, file_path=None):
        """Mark a download as completed"""
        if not self.enabled or download_id not in self.downloads:
            return
            
        with self.lock:
            download = self.downloads[download_id]
            download.completed = True
            
            if file_path:
                download.file_path = file_path
                
            # If all downloads are completed, prepare to stop tracking
            if all(d.completed for d in self.downloads.values()):
                self._cleanup_completed()
                
    def remove_download(self, download_id):
        """Remove a download from tracking"""
        if not self.enabled or download_id not in self.downloads:
            return
            
        with self.lock:
            self.downloads.pop(download_id, None)
            
            # If all downloads are completed, prepare to stop tracking
            if not self.downloads or all(d.completed for d in self.downloads.values()):
                self._cleanup_completed()
    
    def _cleanup_completed(self):
        """Clean up completed downloads and possibly stop the tracker"""
        if not self.enabled:
            return
            
        # Display the completion messages for any downloads
        completed_downloads = {}
        with self.lock:
            for download_id, download in list(self.downloads.items()):
                if download.completed:
                    completed_downloads[download_id] = download
                    
            # Print completion messages
            for download_id, download in completed_downloads.items():
                if download.file_path:
                    if self.should_show_path:
                        check = self.colored("✓", Colors.BRIGHT_GREEN)
                        filename = self.colored(download.filename, Colors.BOLD + Colors.BRIGHT_BLUE)
                        path = self.colored(download.file_path, Colors.BRIGHT_CYAN)
                        print(f"{check} Downloaded: {filename} -> {path}")
                    else:
                        folder = os.path.dirname(download.file_path)
                        check = self.colored("✓", Colors.BRIGHT_GREEN)
                        filename = self.colored(download.filename, Colors.BOLD + Colors.BRIGHT_BLUE)
                        folder_path = self.colored(folder, Colors.BRIGHT_CYAN)
                        print(f"{check} Downloaded: {filename} to {folder_path}")
                
                # Remove from tracking
                self.downloads.pop(download_id, None)
            
        # If nothing left, stop the tracker
        if not self.downloads:
            self.stop()

# Initialize global tracker instance
# Using lazy initialization to ensure config is properly loaded first
tracker = None

def get_tracker():
    """Get the global tracker instance, initializing it if needed"""
    global tracker
    if tracker is None:
        from pybalt.core.config import Config
        tracker = Tracker(Config())
    return tracker

# Initialize the tracker
tracker = get_tracker()
