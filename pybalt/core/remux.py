from pathlib import Path
from time import time, sleep
from .config import Config
from subprocess import Popen
import os
from .logging_utils import get_logger

logger = get_logger(__name__)


class Remuxer:
    def __init__(self, debug: bool = None, config: Config = None):
        self.config = config if config else Config()
        self.debug = debug if debug else self.config.get("debug", False, "general")
        if self.debug:
            global logger
            logger = get_logger(__name__, debug=True)

    def remux(self, path: Path | str, keep_original: bool = None) -> Path:
        if isinstance(path, str):
            path = Path(path)
        if keep_original is None:
            keep_original = self.config.get("keep_original", True, "ffmpeg")
        start_time = time()
        output = path.with_name(f"rmx_{path.name}")
        progress_file = (
            self.config._get_config_dir() / "logs" / f"{path.name if len(path.name) <= 20 else path.name[:8] + '...' + path.name[-8:]}.log"
        )
        if progress_file.exists():
            progress_file.unlink()
        os.makedirs(progress_file.parent.resolve(), exist_ok=True)
        if output.exists():
            output.unlink()
        logger.debug(f"Remuxing {path.name}")
        try:
            Popen(
                [
                    "ffmpeg",
                    "-i",
                    str(path),
                    "-c",
                    "copy",
                    str(output),
                    "-progress",
                    str(progress_file),
                    "-loglevel",
                    "error",
                ]
                + self.config.get("remux_args", "-hwaccel opencl", "ffmpeg").split(" ")
                if self.config.get("remux_args", "-hwaccel opencl", "ffmpeg") != ""
                else [],
                stdout=None,
                stderr=None,
                stdin=None,
            )
            last_update = 0
            data = {}
            while True:
                sleep(0.5)
                if progress_file.exists() and time() - 0.5 > last_update:
                    last_update = time()
                    text = progress_file.read_text()
                    lines_reversed = text.splitlines()[::-1]
                    updated = []
                    for line in lines_reversed:
                        key, value = line.split("=")
                        if key in updated:
                            break
                        updated += [key]
                        data.update({key: value})
                if data.get("progress", "") == "end":
                    break
                logger.debug(
                    f"Remuxing status: {data.get('progress', 'unknown')} speed: {data.get('speed', '0.00x')} {data.get('fps', '0.00')}fps frame {data.get('frame', '0')}",
                )
        except Exception as e:
            logger.debug(f":Remuxing {path.name} to {output} failed: {e}")
            return path
        if progress_file.exists():
            progress_file.unlink()
        if not keep_original:
            path.unlink()
            output = output.rename(path)
        logger.debug(
            f"Remux result: {output} {output.stat().st_size / 1024 / 1024:.2f}MB {time() - start_time:.2f}s",
        )
        return output


remux = Remuxer.remux
