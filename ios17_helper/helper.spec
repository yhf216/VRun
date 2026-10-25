# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "ios17_helper" / "main.py")], pathex=[str(root)],
    datas=collect_data_files("pytun_pmd3") + collect_data_files("developer_disk_image")
          + copy_metadata("pymobiledevice3", recursive=True),
    hiddenimports=["win32timezone", "win32security"],
    excludes=["tkinter", "PySide6", "PyQt5", "PyQt6", "numpy", "pandas",
              "scipy", "matplotlib", "IPython", "av", "fastapi", "uvicorn",
              "asgiwebdav", "pymobiledevice3.cli", "pymobiledevice3.tunneld"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="VRun-iOS17",
          console=True, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="VRun-iOS17")
