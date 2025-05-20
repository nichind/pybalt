import os
import re
import time
import shutil
import asyncio
import threading
from os import path
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict, Union, Tuple
from shutil import get_terminal_size
import sys

try:
    from rich.console import Console
except ImportError:
    # Create a basic Console class if rich isn't available
    class Console:
        def print(self, *args, **kwargs):
            end = kwargs.get("end", "\n")
            print(*args, end=end)


class Terminal:
    """A class to handle terminal output with rich styling"""

    console = Console()

    replaces = {
        ":accent:": "\033[96m",
        ":reset:": "\033[0m",
        ":end:": "\033[0m",
        ":bold:": "\033[1m",
        ":underline:": "\033[4m",
        ":italic:": "\033[3m",
        ":strikethrough:": "\033[9m",
        ":red:": "\033[31m",
        ":green:": "\033[32m",
        ":yellow:": "\033[33m",
        ":blue:": "\033[34m",
        ":magenta:": "\033[35m",
        ":cyan:": "\033[36m",
        ":purple:": "\033[35m",
        ":orange:": "\033[33m",
        ":pink:": "\033[35m",
        ":light_gray:": "\033[37m",
        ":dark_gray:": "\033[90m",
        ":lime:": "\033[92m",
        ":white:": "\033[37m",
        ":gray:": "\033[90m",
        ":bg_black:": "\033[40m",
        ":bg_red:": "\033[41m",
        ":bg_green:": "\033[42m",
        ":bg_yellow:": "\033[43m",
        ":bg_blue:": "\033[44m",
        ":bg_magenta:": "\033[45m",
        ":bg_cyan:": "\033[46m",
        ":bg_white:": "\033[47m",
    }

    # Pattern to detect ANSI escape sequences and emojis for correct length calculation
    pattern = re.compile(
        r"[\x1b\x9b\x9f][\[\]()\\]*[0-?]*[ -/]*[@-~]"
        r"|[\U00010000-\U0010ffff]"
        r"|[\u200d]"
        r"|[\u2640-\u2642]"
        r"|[\u2600-\u2b55]"
        r"|[\u23cf]"
        r"|[\u23e9]"
        r"|[\u231a]"
        r"|[\ufe0f]"  # dingbats
        r"|[\u3030]"
        "+",
        flags=re.UNICODE,
    )

    @classmethod
    def get_size(cls) -> Tuple[int, int]:
        """Get terminal size as (width, height)"""
        try:
            return get_terminal_size()
        except (AttributeError, OSError):
            return (80, 24)  # Default fallback values

    @classmethod
    def apply_style(cls, text: str) -> str:
        """Apply ANSI color styles to text markers like :red:"""
        if not isinstance(text, str):
            text = str(text)
        for key, value in cls.replaces.items():
            text = text.replace(key, value)
        return text

    @classmethod
    def true_len(cls, text: str) -> int:
        """Calculate the true length of text by removing ANSI codes and special characters"""
        text = cls.apply_style(text)
        _ = None
        for i, char in enumerate(text):
            if char == ":" and not _:
                _ = i
            elif char == ":" and _:
                text = text.replace(text[_ + 1 : i], "")
            elif char == " " and _:
                _ = None
        return len(
            re.sub(
                r"[\u001B\u009B][\[\]()#;?]*((([a-zA-Z\d]*(;[-a-zA-Z\d\/#&.:=?%@~_]*)*)?\u0007)|((\d{1,4}(?:;\d{0,4})*)?[\dA-PR-TZcf-ntqry=><~]))",
                "",
                text,
            )
        )

    @classmethod
    def lprint(cls, *args: str, right: bool = False, **kwargs) -> None:
        """Pretty print to terminal with styling and alignment options"""
        args = [cls.apply_style(str(arg) if not isinstance(arg, Exception) else ":red:" + str(arg)) for arg in args]
        terminal_width = cls.get_size()[0]
        num_args = len(args)

        if "highlight" not in kwargs:
            kwargs["highlight"] = False

        if num_args == 0:
            return

        if num_args == 3:
            _center = args[1].center(terminal_width).rstrip()
            print(
                " " * (terminal_width - cls.true_len(args[2])) + cls.apply_style(args[2]) + cls.apply_style(":end:"),
                end="\r",
            )
            cls.console.print(
                " " * ((len(_center) - cls.true_len(_center)) // 2) + _center + cls.apply_style(":end:"),
                end="\r",
                highlight=kwargs["highlight"],
            )
            cls.console.print(args[0], end="\r", highlight=kwargs["highlight"])
        elif num_args == 2:
            print(
                " " * (terminal_width - cls.true_len(args[1])) + cls.apply_style(args[1]) + cls.apply_style(":end:"),
                end="\r",
            )
            cls.console.print(
                args[0] + cls.apply_style(":end:"),
                end="\r",
                highlight=kwargs["highlight"],
            )
        else:
            if right:
                print(
                    " " * (terminal_width - cls.true_len(args[0])) + cls.apply_style(args[0]) + cls.apply_style(":end:"),
                    end="\r",
                )
            else:
                cls.console.print(
                    args[0].ljust(terminal_width),
                    end="\r",
                    highlight=kwargs["highlight"],
                )

        if "end" not in kwargs:
            cls.console.print(cls.apply_style(":end:"), **kwargs)


# Shorthand for Terminal.lprint
lprint = Terminal.lprint


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
        self.iteration = 0

    def __repr__(self) -> str:
        values = ", ".join(f"{key}={value!r}" for key, value in self.__dict__.items())
        return f"{self.__class__.__name__}({values})"


class _DownloadCallbackData(TypedDict):
    """Type definition for download callback data"""

    filename: str
    downloaded_size: int
    start_at: int
    time_passed: Union[int, float]
    file_path: str
    download_speed: int
    total_size: int
    iteration: int
    eta: int


class Tracker:
    """Enhanced tracker for download progress with better UI"""

    def __init__(self, config=None):
        # Import here to avoid circular imports
        from pybalt.core.config import Config

        # Store config instance
        self.config = config or Config()
        self.downloads: Dict[str, DownloadInfo] = {}
        self.queue: List[str] = []  # Track queued downloads
        self.lock = threading.RLock()
        self._running = False
        self._draw_thread = None
        self._visible = False
        self._last_draw_time = 0
        self._min_redraw_interval = self.config.get_as_number("min_redraw_interval", 0.1, "display")  # seconds

        # Spinner frames for animation
        self._spinning_chars = ["⢎⡰", "⢎⡡", "⢎⡑", "⢎⠱", "⠎⡱", "⢊⡱", "⢌⡱", "⢆⡱"]
        self._spin_index = 0

        # Terminal dimensions
        self._update_terminal_size()

        # Backward compatibility for old code
        self.start()

    @property
    def enabled(self):
        """Check if the tracker is enabled in config"""
        try:
            return self.config.get("enable_tracker", True, section="display")
        except Exception:
            return True

    @property
    def colors_enabled(self):
        """Check if colors are enabled in config"""
        try:
            return self.config.get("enable_colors", True, section="display")
        except Exception:
            return True

    @property
    def should_show_path(self):
        """Check if file paths should be shown"""
        try:
            return self.config.get("show_path", True, section="display")
        except Exception:
            return True

    @property
    def max_filename_length(self):
        """Get the maximum length for filenames from config"""
        try:
            return self.config.get_as_number("max_filename_length", 25, section="display")
        except Exception:
            return 25

    @property
    def progress_bar_width(self):
        """Get the progress bar width from config"""
        try:
            return self.config.get_as_number("progress_bar_width", 24, section="display")
        except Exception:
            return 24

    def _update_terminal_size(self):
        """Update stored terminal dimensions"""
        try:
            self._terminal_size = Terminal.get_size()
            self._terminal_width = self._terminal_size[0]
            self._terminal_height = self._terminal_size[1]
        except Exception:
            self._terminal_width = 80
            self._terminal_height = 24

    def _get_spinner(self) -> str:
        """Get the next spinner animation frame"""
        char = self._spinning_chars[self._spin_index]
        self._spin_index = (self._spin_index + 1) % len(self._spinning_chars)
        return char if self.colors_enabled else char

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable format"""
        if size_bytes < 0:
            return ":gray:Unknown"
        elif size_bytes < 1024:
            return f":lime:{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f":lime:{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f":lime:{size_bytes / (1024 * 1024):.2f}MB"
        else:
            return f":lime:{size_bytes / (1024 * 1024 * 1024):.2f}GB"

    def _format_speed(self, speed_bytes: float) -> str:
        """Format speed in bytes/second to human-readable format"""
        if speed_bytes < 1024:
            return f":magenta:{speed_bytes:.0f}B/s"
        elif speed_bytes < 1024 * 1024:
            return f":magenta:{speed_bytes / 1024:.1f}KB/s"
        else:
            return f":magenta:{speed_bytes / (1024 * 1024):.2f}MB/s"

    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to human-readable format"""
        if seconds < 60:
            return f":cyan:{seconds:.0f}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f":cyan:{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f":cyan:{hours}h {minutes}m"

    def _truncate_filename(self, filename: str, max_length: Optional[int] = None) -> str:
        """Truncate filename to fit display width"""
        if max_length is None:
            max_length = self.max_filename_length

        if len(filename) <= max_length:
            return filename

        # Keep extension
        name, ext = os.path.splitext(filename)
        trunc_len = max_length - len(ext) - 3  # 3 for '...'
        if trunc_len < 1:
            return filename[: max_length - 3] + "..."
        return name[:trunc_len] + "..." + ext

    def _draw_progress_bar(self, percentage: float) -> str:
        """Draw a colorful progress bar with given percentage"""
        width = self.progress_bar_width
        completed_width = int(width * percentage / 100)
        remaining_width = width - completed_width

        # Character selection based on color support
        fill_char = "▇" if self.colors_enabled else "="
        empty_char = "-" if self.colors_enabled else " "

        if self.colors_enabled:
            # Color gradient based on completion
            if percentage < 30:
                color = ":red:"
            elif percentage < 70:
                color = ":yellow:"
            else:
                color = ":green:"

            return f"[:gray:[{color}{fill_char * completed_width}:gray:{empty_char * remaining_width}]:gray:]"
        else:
            return f"[{fill_char * completed_width}{empty_char * remaining_width}]"

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

    def _clear_display(self):
        """Clear the tracker display from terminal"""
        if not self._visible:
            return

        # Clear from cursor to end of screen
        sys.stdout.write("\033[0J")
        sys.stdout.flush()
        self._visible = False

    def _draw_loop(self):
        """Main loop that updates the display"""
        while self._running:
            try:
                now = time.time()
                if now - self._last_draw_time < self._min_redraw_interval:
                    time.sleep(0.05)
                    continue

                self._last_draw_time = now

                if (self.downloads or self.queue) and self.enabled:
                    self._update_terminal_size()
                    self._update_downloads(now)
                    self._draw_downloads()
                    self._visible = True
                elif self._visible:
                    self._clear_display()
                    self._visible = False
            except Exception:
                # Silently handle drawing errors
                pass
            time.sleep(float(self.config.get("draw_interval", 0.4, "display")))

    def _update_downloads(self, now: float):
        """Update download speeds and ETAs"""
        with self.lock:
            for download_id, download in self.downloads.items():
                if not download.completed:
                    # Update iteration counter for spinner
                    download.iteration = (download.iteration + 1) % len(self._spinning_chars)

                    # Calculate speed
                    elapsed = now - download.last_update
                    if elapsed > 0:
                        download.speed = (download.downloaded_size - download.last_size) / elapsed
                        download.last_size = download.downloaded_size
                        download.last_update = now

                    # Calculate ETA if we know the total size
                    if download.total_size > 0:
                        remaining_bytes = download.total_size - download.downloaded_size
                        if download.speed > 0:
                            download.eta = remaining_bytes / download.speed
                        else:
                            download.eta = 0

    def _draw_downloads(self):
        """Draw the download status in the terminal"""
        with self.lock:
            # Get active downloads (not completed)
            active_downloads = [d for d in self.downloads.values() if not d.completed]

            if not active_downloads and not self.queue:
                return

            # Format the status line for active downloads
            if active_downloads:
                status_parts = []

                # Calculate total progress if possible
                all_known_size = all(d.total_size > 0 for d in active_downloads)
                if all_known_size:
                    total_downloaded = sum(d.downloaded_size for d in active_downloads)
                    total_size = sum(d.total_size for d in active_downloads)
                    percent = min(100, int(total_downloaded / total_size * 100))
                    progress_bar = self._draw_progress_bar(percent)

                    # Add progress info
                    status_parts.append(f"⭳ :bold:{len(active_downloads)} active downloads")
                    status_parts.append(f"{progress_bar} :white:{percent}%")
                    status_parts.append(f"{self._format_size(total_downloaded)}/{self._format_size(total_size)}")
                else:
                    # No progress bar for unknown size
                    status_parts.append(f"⭳ :bold:{len(active_downloads)} active downloads")

                # Add speed info
                total_speed = sum(d.speed for d in active_downloads)
                status_parts.append(f"{self._format_speed(total_speed)}")
                
                # Add downloaded file size info for all downloads, including finished ones
                total_downloaded = sum(d.downloaded_size for d in [d for d in self.downloads.values()])
                status_parts.append(f"{self._format_size(total_downloaded)}")

                # Add spinner
                status_parts.append(f":white::bold:{self._get_spinner()}")

                # Format status line
                status_line = " ".join(status_parts)

                # Print the status line
                lprint(Terminal.apply_style(status_line), end="\r", highlight=False)

            # Show queue status if there are queued downloads
            if self.queue:
                queue_status = f":gray:⌛ {len(self.queue)} downloads queued"
                if active_downloads:
                    # Print on a new line if we already have active downloads
                    print()
                lprint(Terminal.apply_style(queue_status), end="\r", highlight=False)

    def add_download(self, download_id: str, url: str, filename: str):
        """Add a new download to be tracked"""
        if not self.enabled:
            return

        with self.lock:
            self.downloads[download_id] = DownloadInfo(url, filename)
            if not self._running:
                self.start()

    def update_download(self, download_id: str, **kwargs):
        """Update the status of a download"""
        if not self.enabled or download_id not in self.downloads:
            return

        with self.lock:
            download = self.downloads[download_id]
            for key, value in kwargs.items():
                if hasattr(download, key):
                    setattr(download, key, value)

    def complete_download(self, download_id: str, file_path: Optional[str] = None):
        """Mark a download as completed"""
        if not self.enabled or download_id not in self.downloads:
            return

        with self.lock:
            download = self.downloads[download_id]
            download.completed = True

            if file_path:
                download.file_path = file_path

            # Calculate time taken
            time_passed = time.time() - download.start_time

            # Show completion message
            self._show_completion_message(download, time_passed)

            # Remove from tracking
            self.downloads.pop(download_id, None)

            # If no more downloads, stop tracking
            if not self.downloads and not self.queue:
                self.stop()

    def remove_download(self, download_id: str):
        """Remove a download from tracking without completion message"""
        if not self.enabled or download_id not in self.downloads:
            return

        with self.lock:
            self.downloads.pop(download_id, None)

            # If no more downloads, stop tracking
            if not self.downloads and not self.queue:
                self.stop()

    def _show_completion_message(self, download: DownloadInfo, time_passed: float):
        """Show download completion message"""
        if not download.file_path:
            return

        try:
            file_size = os.path.getsize(download.file_path) / (1024 * 1024)

            # Clear current line before printing completion message
            print("\r" + " " * self._terminal_width, end="\r")

            if self.should_show_path:
                lprint(f":green:✔  :white:{download.filename}", f":green:{file_size:.2f}MB :cyan:{time_passed:.2f}s")
            else:
                folder = os.path.dirname(download.file_path)
                lprint(f":green:✔  :white:{download.filename}", f":green:{file_size:.2f}MB :cyan:{time_passed:.2f}s")
        except (OSError, IOError):
            # Handle file access errors gracefully
            pass

    def add_to_queue(self, url: str):
        """Add a download URL to the queue"""
        with self.lock:
            self.queue.append(url)
            if not self._running:
                self.start()

    def remove_from_queue(self, url: str):
        """Remove a download URL from the queue"""
        with self.lock:
            if url in self.queue:
                self.queue.remove(url)

            # If no more downloads or queue items, stop tracking
            if not self.downloads and not self.queue:
                self.stop()


# Global tracker instance
tracker = None


def get_tracker():
    """Get the global tracker instance, initializing if needed"""
    global tracker
    if tracker is None:
        from pybalt.core.config import Config

        tracker = Tracker(Config())
    return tracker


# Initialize tracker
tracker = get_tracker()
