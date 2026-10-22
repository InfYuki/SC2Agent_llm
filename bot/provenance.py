"""Best-effort source provenance; Git is optional when launching a match."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess


def find_git():
    # Windows CreateProcess does not resolve a bare git to a git.cmd shim.
    executable = shutil.which("git.exe" if os.name == "nt" else "git")
    if executable:
        return executable
    if os.name == "nt":
        for variable, default in (("ProgramFiles", "C:/Program Files"),
                                  ("ProgramFiles(x86)", "C:/Program Files (x86)"),
                                  ("LOCALAPPDATA", "")):
            base = os.environ.get(variable, default)
            if not base:
                continue
            for relative in ("Git/cmd/git.exe", "Git/bin/git.exe", "Git/mingw64/bin/git.exe",
                             "Programs/Git/cmd/git.exe"):
                candidate = Path(base) / relative
                if candidate.is_file():
                    return str(candidate)
        bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe"
        if bundled.is_file():
            return str(bundled)
    return None


def source_provenance(root):
    root = Path(root)
    executable = find_git()
    warnings = []

    def query(*args):
        if not executable:
            return None
        try:
            return subprocess.check_output(
                [executable, *args], cwd=root, stderr=subprocess.PIPE, timeout=15
            )
        except (OSError, subprocess.SubprocessError):
            warnings.append("Git query unavailable: " + args[0])
            return None

    names_raw = query("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    if names_raw is not None:
        names = names_raw.decode("utf-8", errors="surrogateescape").split("\0")
        mode = "git-index-and-untracked-nonignored"
    else:
        # Never recursively inspect artifacts, credentials or unrelated local data.
        names = [p.name for p in root.iterdir() if p.is_file() and p.suffix in {".py", ".cmd"}]
        for directory in ("bot", "tools", "tests"):
            names.extend(p.relative_to(root).as_posix() for p in (root / directory).rglob("*.py")
                         if "__pycache__" not in p.parts)
        mode = "fallback-python-and-launchers-only"
        warnings.append("Git unavailable; commit/diff may be unknown; source hashes cover Python sources and launchers only")
    hashes = {}
    for name in names:
        path = (root / name).resolve()
        if name and path.is_relative_to(root.resolve()) and path.is_file():
            try:
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                warnings.append("Source file unreadable: " + name)
    commit = query("rev-parse", "HEAD")
    ares = query("-C", "ares-sc2", "rev-parse", "HEAD")
    diff = query("diff", "HEAD")
    return dict(
        project_commit=commit.decode().strip() if commit else None,
        ares_commit=ares.decode().strip() if ares else None,
        dirty_diff_sha256=hashlib.sha256(diff).hexdigest() if diff is not None else None,
        source_hashes=hashes, source_hashes_mode=mode,
        provenance_warnings=warnings,
    )
