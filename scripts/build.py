# SPDX-License-Identifier: MPL-2.0
"""Build the self-contained Windows application and optional Inno Setup installer."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vrun import __version__


def copy_runtime_notices(target: Path):
    import importlib.metadata as metadata
    license_root = target / "LICENSES"
    license_root.mkdir(parents=True, exist_ok=True)
    from archive_ios17 import distributions
    names = {"PySide6_Essentials", "shiboken6", "geopy", "geographiclib", "winotify", *distributions()}
    for name in sorted(names):
        distribution = metadata.distribution(name)
        for file in distribution.files or []:
            if any(part.lower() in ("licenses", "license", "copying") for part in file.parts) or file.name.lower().startswith(("license", "copying", "notice")):
                path = Path(distribution.locate_file(file))
                if path.is_file():
                    destination = license_root / name / Path(*file.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
    # Wintun retains its separate prebuilt-driver distribution license.
    import pytun_pmd3
    wintun_license = Path(pytun_pmd3.__file__).parent / "wintun" / "LICENSE.txt"
    shutil.copy2(wintun_license, license_root / "Wintun.txt")
    python_license = Path(sys.base_prefix) / "LICENSE_PYTHON.txt"
    if not python_license.is_file():
        python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, license_root / "Python.txt")


def copy_release_material(target: Path):
    for directory in ("routes", "LICENSES"):
        shutil.copytree(ROOT / directory, target / directory, dirs_exist_ok=True)
    for name in ("LICENSE", "README.md", "UPSTREAM.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, target / name)
    copy_runtime_notices(target)
    source_dir = target / "SOURCE"
    source_dir.mkdir(exist_ok=True)
    entries = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                      cwd=ROOT).decode("utf-8").split("\0")
    with zipfile.ZipFile(source_dir / f"VRun-{__version__}-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in sorted(set(entries)):
            path = ROOT / entry
            if entry and path.is_file() and not entry.startswith(("libimobiledevice/", "DeveloperDiskImage/")):
                archive.write(path, entry)
    shutil.copytree(ROOT / "third_party" / "sources", source_dir / "third_party", dirs_exist_ok=True)


def find_iscc():
    candidates = [os.environ.get("INNO_ISCC", ""), str(ROOT / "build/inno/ISCC.exe")]
    for prefix in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        for version in (6, 7):
            candidates.append(str(Path(prefix) / f"Inno Setup {version}" / "ISCC.exe"))
    return next((path for path in candidates if path and Path(path).is_file()), None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    if not args.prepare_only:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "ios17_helper/helper.spec"], check=True)
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "VRun.spec"], check=True)
    target = ROOT / "dist/VRun"
    if not (target / "VRun.exe").is_file():
        raise SystemExit("dist/VRun/VRun.exe is missing")
    helper = ROOT / "dist/VRun-iOS17"
    if not (helper / "VRun-iOS17.exe").is_file():
        raise SystemExit("dist/VRun-iOS17/VRun-iOS17.exe is missing")
    subprocess.run([str(helper / "VRun-iOS17.exe"), "--check"], check=True)
    shutil.copytree(helper, target / "_internal/ios17", dirs_exist_ok=True)
    copy_release_material(target)
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    manifest = {
        "version": __version__,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "python": sys.version,
        "platform": "Windows x64",
    }
    (release / "build-info.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.installer:
        compiler = find_iscc()
        if not compiler:
            raise SystemExit("Inno Setup 6/7 is required; set INNO_ISCC to ISCC.exe")
        subprocess.run([compiler, str(ROOT / "installer/VRun.iss")], check=True)
    artifacts = list(release.glob("*.exe"))
    (release / "SHA256SUMS.txt").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts),
        encoding="utf-8",
    )
    print(f"Application: {target / 'VRun.exe'}")
    print(f"Release: {release}")


if __name__ == "__main__":
    main()
