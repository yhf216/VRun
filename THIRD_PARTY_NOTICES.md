# Third-party notices

VRun desktop application code is MPL-2.0. The independently executable ios17_helper service is GPL-3.0-or-later (see its SPDX headers and LICENSES/GPL-3.0.txt). Separate third-party components retain their own licenses; calling a CLI does not remove its redistribution obligations.

| Component | Version / origin | License / source |
| --- | --- | --- |
| iOSRealRun-cli | 1710c72a60a704996bcf7d7b5e5f92f49687af39 | MPL-2.0; upstream history and LICENSE retained |
| iOSRealRun-cli-17 | reference implementation of RSD/DVT location flow | MPL-2.0; https://github.com/iOSRealRun/iOSRealRun-cli-17 |
| pymobiledevice3 | 11.44.0, independent iOS 17+ helper | GPL-3.0-or-later; exact source archive and license bundled |
| pmd-pytcp / pmd-net-addr / pmd-net-proto | versions in third_party/ios17-dependencies.json | GPL-3.0-or-later; exact source archives bundled |
| Additional helper dependencies | pinned in requirements-ios17.txt | original wheel notices in LICENSES; copyleft source archives in SOURCE/third_party/ios17 |
| Wintun prebuilt DLL | unchanged DLLs supplied by pytun-pmd3 3.0.3 | separate Prebuilt Binaries License, copied into LICENSES/Wintun.txt; used via its permitted API |
| libimobiledevice command-line tools | 1.3.0-git-cc540a2, unchanged upstream Windows binaries | GPL-2.0-or-later; source archive in SOURCE/third_party |
| libimobiledevice library | bundled with the above tools | LGPL-2.1-or-later; source archive in SOURCE/third_party |
| libusbmuxd | 2.0.2-git-2cebd28, unchanged upstream DLL | LGPL-2.1-or-later; source archive in SOURCE/third_party |
| libplist and libimobiledevice-glue | unchanged DLLs inherited at the baseline | LGPL-2.1-or-later; see upstream source locations below |
| OpenSSL | 3.0.7, unchanged upstream device-tool DLLs | Apache-2.0; license in LICENSES/OpenSSL.txt |
| OpenSSL runtime | 3.6.4, supplied by the validated conda Python/cryptography build | Apache-2.0; license in LICENSES/OpenSSL-runtime.txt |
| PySide6 Essentials / shiboken6 | 6.12.0 | Qt LGPL-3.0/GPL/commercial licensing; applicable wheel license files copied into LICENSES |
| geopy | 2.4.1 | MIT; installed wheel license copied into LICENSES |
| geographiclib | 2.1 | MIT; installed wheel license copied into LICENSES |
| winotify | 1.1.0 | MIT; installed wheel license copied into LICENSES |
| Python | interpreter used for the build | Python license copied into LICENSES/Python.txt |

The helper is built separately from the Qt application. It imports pymobiledevice3 in its own process and exchanges JSON-line requests over stdin/stdout. Its source, build spec, exact Python dependency snapshot, and corresponding copyleft source releases accompany the installer. Copyleft source downloads use official PyPI release metadata and verified SHA256 digests. Replacing/rebuilding the helper is permitted; VRun does not restrict debugging modified components. Wintun binaries are kept unchanged with their own license and are not relicensed as MPL or GPL. The source audit limitation below still applies to inherited native binaries.

The iOSRealRun-cli-17 project was consulted for its tunnel / RSD / DVT / LocationSimulation sequence; its old pymobiledevice3 2.46.1 API and bundled driver installer were not copied. VRun uses the pinned current API with explicit device targeting, bounded requests, userspace tunnels on iOS 17.4+, and explicit QUIC on iOS 17.0-17.3.

Device tool license headers are checked at https://github.com/libimobiledevice/libimobiledevice/tree/cc540a2.
Additional library sources:
https://github.com/libimobiledevice/libplist
https://github.com/libimobiledevice/libimobiledevice-glue
https://github.com/libimobiledevice/libusbmuxd/tree/2cebd28
https://github.com/openssl/openssl/tree/openssl-3.0.7

Qt sources and licensing:
https://download.qt.io/official_releases/QtForPython/
https://code.qt.io/cgit/pyside/pyside-setup.git/
https://www.qt.io/development/open-source-lgpl-obligations

Qt libraries remain separate, dynamically loaded files in the onedir distribution. Application source and build configuration are included so recipients can rebuild the application and replace LGPL libraries. VRun does not prohibit replacement or debugging of modified LGPL components.

Binary hashes and known source identifiers are recorded in third_party/windows-manifest.json. The original baseline did not record exact libplist/glue commits or native compiler settings; these remain a provenance limitation for public redistribution and should be resolved with reproducible native builds before a public production release. This initial local installer is a review build, not a claim that this audit is complete.

Apple components are separate proprietary software obtained from official endpoints at install time. No Apple USB driver is modified or re-signed. Existing system Apple components are not uninstalled by the VRun uninstaller.

The Simplified Chinese installer translation is adapted from the official Inno Setup source at https://github.com/jrsoftware/issrc/blob/main/Files/Languages/ChineseSimplified.isl. Original translator notices are retained in installer/ChineseSimplified.isl; unsupported newer message keys were omitted for compiler compatibility.

Inno Setup is a build tool, not an application runtime dependency. Its compiler license is retained in the build-tool installation; the application installer preserves its generated notices.
