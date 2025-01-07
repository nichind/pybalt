from pathlib import Path
import ffmpeg


class Remuxer:
    @classmethod
    def remux(self, path: Path) -> Path:
        output = path.with_name(f"remuxed_{path.name}")
        if output.exists():
            output.unlink()
        print(f"Remuxing {path.name} to {output}", end="\r")
        try:
            ffmpeg.input(str(path)).output(str(output)).run(quiet=True)
        except ffmpeg.Error as e:
            print(f"Remuxing {path.name} to {output} failed: {e}")
            return path
        print(f"Remuxed {path.name} to {output}, size: {output.stat().st_size / 1024 / 1024 : .2f} MB")
        return output


remux = Remuxer.remux
