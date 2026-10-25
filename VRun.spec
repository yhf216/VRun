# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
root = Path(SPECPATH)
a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "libimobiledevice" / "win"), "libimobiledevice/win"),
        (str(root / "DeveloperDiskImage"), "DeveloperDiskImage"),
        (str(root / "assets"), "assets"),
    ],
    hiddenimports=["winotify"],
    hookspath=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "numpy", "pandas", "scipy", "matplotlib",
              "pymobiledevice3", "pmd_pytcp", "pmd_net_addr", "pmd_net_proto",
              "ios17_helper", "IPython", "av"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="VRun",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=str(root / "assets" / "vrun.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="VRun")
