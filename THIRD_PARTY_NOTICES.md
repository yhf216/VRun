# Third-party notices

VRun application code is MPL-2.0. Separate third-party components retain their own licenses; calling a CLI does not remove its redistribution obligations.

| Component | Version / origin | License / source |
| --- | --- | --- |
| iOSRealRun-cli | 1710c72a60a704996bcf7d7b5e5f92f49687af39 | MPL-2.0; upstream history and LICENSE retained |
| libimobiledevice command-line tools | 1.3.0-git-cc540a2, unchanged upstream Windows binaries | GPL-2.0-or-later; source archive in SOURCE/third_party |
| libimobiledevice library | bundled with the above tools | LGPL-2.1-or-later; source archive in SOURCE/third_party |
| libusbmuxd | 2.0.2-git-2cebd28, unchanged upstream DLL | LGPL-2.1-or-later; source archive in SOURCE/third_party |
| libplist and libimobiledevice-glue | unchanged DLLs inherited at the baseline | LGPL-2.1-or-later; see upstream source locations below |
| OpenSSL | 3.0.7, unchanged upstream DLLs | Apache-2.0; license in LICENSES/OpenSSL.txt |
| PySide6 Essentials / shiboken6 | 6.12.0 | Qt LGPL-3.0/GPL/commercial licensing; applicable wheel license files copied into LICENSES |
| geopy | 2.4.1 | MIT; installed wheel license copied into LICENSES |
| geographiclib | 2.1 | MIT; installed wheel license copied into LICENSES |
| winotify | 1.1.0 | MIT; installed wheel license copied into LICENSES |
| Python | interpreter used for the build | Python license copied into LICENSES/Python.txt |

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

Inno Setup is a build tool, not an application runtime dependency. Its compiler license is retained in the build-tool installation; the application installer preserves its generated notices.
