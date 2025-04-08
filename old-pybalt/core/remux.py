from pathlib import Path
from time import time, sleep
from .misc import lprint
from subprocess import Popen
import os


class Remuxer:
    @classmethod
    def remux(cls, path: Path | str, keep_original: bool = False) -> Path:
        if isinstance(path, str):
            path = Path(path)
        start_time = time()
        output = path.with_name(f"rmx_{path.name}")
        progress_file = Path(
            os.path.join(
                os.path.expanduser("~"),
                ".config",
                "cobalt",
                f"{path.name if len(path.name) <= 20 else path.name[:8] + '...' + path.name[:8]}"
                + ".log",
            )
        )
        if progress_file.exists():
            progress_file.unlink()
        os.makedirs(progress_file.parent.resolve(), exist_ok=True)
        if output.exists():
            output.unlink()
        lprint(f"Remuxing {path.name}", end="\r")
        try:
            Popen(
                [
                    "ffmpeg",
                    "-hwaccel",
                    "opencl",
                    "-i",
                    str(path),
                    "-c",
                    "copy",
                    str(output),
                    "-progress",
                    str(progress_file),
                    "-loglevel",
                    "error",
                ],
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
                lprint(
                    f'Remuxing status: {data.get("progress", "unknown")} :cyan:speed: {data.get("speed", "0.00x")} :green:{data.get("fps", "0.00")}fps :yellow:frame {data.get("frame", "0")}',
                    end="\r",
                )
        except Exception as e:
            lprint(f":red:Remuxing {path.name} to {output} failed: {e}")
            return path
        if progress_file.exists():
            progress_file.unlink()
        if not keep_original:
            path.unlink()
            output = output.rename(path)
        lprint(
            f":green:✔:end:  Remux result: :white:{output}",
            f":green:{output.stat().st_size / 1024 / 1024:.2f}MB :cyan:{time() - start_time:.2f}s",
        )
        return output


remux = Remuxer.remux
