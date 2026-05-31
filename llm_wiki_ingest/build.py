from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Any, Callable


Runner = Callable[..., subprocess.CompletedProcess[str]]


def build_wiki(wiki_dir: str | Path, runner: Runner = subprocess.run) -> dict[str, str]:
    wiki = Path(wiki_dir)
    if not wiki.exists() or not wiki.is_dir():
        raise FileNotFoundError(f"Wiki directory not found: {wiki}")
    package_json = wiki / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"Quartz package.json not found: {package_json}")

    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise FileNotFoundError("npx command not found. Install Node.js/npm and run npm install in the Quartz wiki.")
    command = [npx, "quartz", "build"]
    result = runner(command, cwd=wiki, text=True, capture_output=True)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        message = stderr or stdout or "Quartz build failed"
        raise RuntimeError(message)
    return {
        "command": "npx quartz build",
        "wiki": str(wiki),
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }
