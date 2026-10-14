from pathlib import Path
import os
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "artifacts"
    output.mkdir(exist_ok=True)
    env = dict(
        os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", PYTHONNOUSERSITE="1"
    )
    with (output / "last-run.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-s", "-u", str(root / "run_local.py"), *sys.argv[1:]],
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            text=True,
        )
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            return process.wait()
        except KeyboardInterrupt:
            # Send a break to this owned child tree only; game close also works.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True
            )
            return 130


if __name__ == "__main__":
    raise SystemExit(main())
