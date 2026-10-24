# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
import os
import sys


def app_dir() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_dir()))


def data_dir() -> Path:
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "VRun"
    directory.mkdir(parents=True, exist_ok=True)
    return directory
