# SPDX-License-Identifier: MPL-2.0
"""Installer-only Apple component bootstrap. Downloads are signature checked."""
from pathlib import Path
import base64
import hashlib
import logging
import os
import subprocess
import tempfile
import urllib.request

LOG = logging.getLogger(__name__)
APPLE_URL = "https://www.apple.com/itunes/download/win64"
USB_URL = ("https://catalog.s.download.windowsupdate.com/d/msdownload/update/driver/drvs/2023/10/"
           "5fb262ea-d52d-46a7-9361-f3260ba57a1a_3e8075a4dded0a795131f82285e2f1a06525ebc2.cab")
USB_SHA1 = "3e8075a4dded0a795131f82285e2f1a06525ebc2"


def download(url: str, target: Path):
    errors = []
    for opener in (urllib.request.build_opener(),
                   urllib.request.build_opener(urllib.request.ProxyHandler({}))):
        try:
            with opener.open(url, timeout=45) as response, target.open("wb") as output:
                # urllib validates TLS certificates for both system-proxy and direct requests.
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            return
        except Exception as error:
            errors.append(str(error))
    raise RuntimeError("下载失败，请检查网络：" + "; ".join(errors))


def signature(path: Path, signer: str):
    encoded_path = base64.b64encode(str(path).encode("utf-8")).decode("ascii")
    code = (f"$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_path}'));"
            "$s=Get-AuthenticodeSignature -LiteralPath $p;"
            f"if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notlike '*{signer}*')"
            "{exit 1};exit 0")
    encoded = base64.b64encode(code.encode("utf-16le")).decode("ascii")
    run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], timeout=60)


def run(args, timeout=180, accepted=(0,)):
    process = subprocess.run(list(map(str, args)), capture_output=True, timeout=timeout,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    LOG.info("Command %s returned %s: %s", Path(str(args[0])).name, process.returncode,
             process.stdout.decode("utf-8", errors="replace")[-2000:])
    if process.returncode not in accepted:
        raise RuntimeError(f"{Path(str(args[0])).name} 执行失败（{process.returncode}）。")
    return process.returncode


def components_present() -> bool:
    import winreg
    prefix = r"SYSTEM\CurrentControlSet\Services"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, prefix + r"\Apple Mobile Device Service"):
            pass
        for name in ("AppleKmdfFilter", "usbaapl64"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, prefix + "\\" + name):
                    return True
            except FileNotFoundError:
                continue
    except OSError:
        pass
    return False


def install() -> int:
    if components_present():
        # Keep an existing setup rather than replace a user's Apple components.
        run(["sc.exe", "start", "Apple Mobile Device Service"], accepted=(0, 1056))
        return 0
    reboot = False
    with tempfile.TemporaryDirectory(prefix="VRun-Apple-") as folder:
        temporary = Path(folder)
        installer = temporary / "iTunes64Setup.exe"
        LOG.info("Downloading Apple Mobile Device Support")
        download(APPLE_URL, installer)
        signature(installer, "O=Apple Inc.")
        run(["tar.exe", "-xf", installer, "-C", temporary, "AppleMobileDeviceSupport64.msi"])
        package = temporary / "AppleMobileDeviceSupport64.msi"
        signature(package, "O=Apple Inc.")
        log_dir = Path(os.environ.get("PROGRAMDATA", temporary)) / "VRun"
        log_dir.mkdir(parents=True, exist_ok=True)
        code = run(["msiexec.exe", "/i", package, "/qn", "/norestart", "/L*v",
                    log_dir / "apple-msi.log"], accepted=(0, 3010))
        reboot = code == 3010
        cab = temporary / "AppleUSB.cab"
        download(USB_URL, cab)
        if hashlib.sha1(cab.read_bytes()).hexdigest() != USB_SHA1:
            raise RuntimeError("Apple USB 驱动校验失败，安装已停止。")
        drivers = temporary / "drivers"
        drivers.mkdir()
        run(["expand.exe", "-F:*", cab, drivers])
        signature(drivers / "appleusb.cat", "Microsoft Windows Hardware Compatibility Publisher")
        code = run(["pnputil.exe", "/add-driver", drivers / "AppleUsb.inf", "/install"],
                   accepted=(0, 3010))
        reboot = reboot or code == 3010
        run(["sc.exe", "start", "Apple Mobile Device Service"], accepted=(0, 1056))
    return 3010 if reboot else 0


def install_main() -> int:
    import ctypes
    directory = Path(os.environ.get("PROGRAMDATA", tempfile.gettempdir())) / "VRun"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=directory / "driver-install.log", encoding="utf-8", level=logging.INFO)
        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise RuntimeError("驱动安装需要管理员权限，请重新运行 VRun 安装包。")
        return install()
    except Exception as error:
        LOG.exception("Apple component installation failed")
        ctypes.windll.user32.MessageBoxW(
            None, f"Apple 驱动准备未完成：{error}\n\n可以稍后重新运行安装包。详情见 {directory}\\driver-install.log",
            "VRun · 驱动安装", 0x10)
        return 1
