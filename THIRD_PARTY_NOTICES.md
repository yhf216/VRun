# Third-party notices

VRun desktop code is MPL-2.0. The independent ios17_helper executable is GPL-3.0-or-later. Third-party components retain their original licenses.

| Component | Version / origin | License / source |
| --- | --- | --- |
| iOSRealRun-cli | 1710c72a60a704996bcf7d7b5e5f92f49687af39 | MPL-2.0; upstream history and LICENSE retained |
| iOSRealRun-cli-17 | RSD / DVT workflow reference | MPL-2.0; https://github.com/iOSRealRun/iOSRealRun-cli-17 |
| pymobiledevice3 | 11.44.0 | GPL-3.0-or-later |
| pmd-pytcp / pmd-net-addr / pmd-net-proto | third_party/ios17-dependencies.json | GPL-3.0-or-later |
| Other helper dependencies | requirements-ios17.txt | Original licenses included in the distribution |
| Wintun prebuilt DLL | Unchanged DLLs from pytun-pmd3 3.0.3 | Prebuilt Binaries License, included as LICENSES/Wintun.txt; used via the permitted API |
| libimobiledevice command-line tools | 1.3.0-git-cc540a2 | GPL-2.0-or-later |
| libimobiledevice library | Bundled with the above tools | LGPL-2.1-or-later |
| libusbmuxd | 2.0.2-git-2cebd28 | LGPL-2.1-or-later |
| libplist / libimobiledevice-glue | Inherited upstream DLLs | LGPL-2.1-or-later |
| OpenSSL | Device tools: 3.0.7; runtime: build environment version | Apache-2.0; LICENSES/OpenSSL.txt and OpenSSL-runtime.txt |
| PySide6 Essentials / shiboken6 | 6.12.0 | Qt LGPL-3.0/GPL/commercial licensing; applicable license files included |
| geopy / geographiclib | 2.4.1 / 2.1 | MIT |
| winotify | 1.1.0 | MIT |
| Python | Build interpreter version | Python license included |

## Sources and replacement

Application and helper source, build configuration, and archived copyleft dependency sources are included in the installer SOURCE directory. Python package notices are copied into LICENSES. Exact helper dependency versions and source checksums are recorded in third_party/ios17-dependencies.json.

Qt libraries remain separate, dynamically loaded files. Recipients may rebuild the application and helper, replace LGPL components and debug modified versions. Wintun binaries retain their separate license.

Native binary checksums and known source identifiers are recorded in third_party/windows-manifest.json. The upstream baseline does not identify the exact libplist/glue revisions or original native compiler flags.

Native library sources:

- https://github.com/libimobiledevice/libimobiledevice/tree/cc540a2
- https://github.com/libimobiledevice/libusbmuxd/tree/2cebd28
- https://github.com/libimobiledevice/libplist
- https://github.com/libimobiledevice/libimobiledevice-glue
- https://github.com/openssl/openssl

Qt sources and licensing:

- https://download.qt.io/official_releases/QtForPython/
- https://code.qt.io/cgit/pyside/pyside-setup.git/
- https://www.qt.io/development/open-source-lgpl-obligations

## Installer components

Apple components are proprietary software downloaded from official endpoints. Drivers are not modified or re-signed; the VRun uninstaller does not remove existing Apple components.

The Simplified Chinese installer translation is adapted from [Inno Setup](https://github.com/jrsoftware/issrc/blob/main/Files/Languages/ChineseSimplified.isl). Translator notices are retained in installer/ChineseSimplified.isl.

Inno Setup is a build tool; its generated installer notices are preserved.
