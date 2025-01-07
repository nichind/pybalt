from pathlib import Path
from .misc import lprint
import ffmpeg


class Remuxer:
    @classmethod
    def remux(self, path: Path) -> Path:
        output = path.with_name(f"remuxed_{path.name}")
        lprint(f"Remuxing {path} to {output} ...", end="\r")
        try:
            ffmpeg.input(str(path)).output(str(output)).run(quiet=True)
        except ffmpeg.Error as e:
            lprint(f"Remuxing {path} to {output} failed: {e}")
            return path
        lprint(f"Remuxed {path} to {output}")
        return output


remux = Remuxer.remux
