# Upstream attribution

VRun is derived from https://github.com/iOSRealRun/iOSRealRun-cli.

- Baseline: 1710c72a60a704996bcf7d7b5e5f92f49687af39 (docs: update links).
- Upstream Git history and MPL-2.0 LICENSE are preserved.
- The coordinate conversion in vrun/coordinates.py is adapted from tools/run.py.
- The Windows device tools and developer disk images are inherited without modification.
- HNroute.txt is an upstream route. ZJG-west.txt and ZJG-east.txt are the user's west_test.txt and east_test.txt, renamed with authorization.
- iOS 17+ reference: https://github.com/iOSRealRun/iOSRealRun-cli-17 (MPL-2.0), especially driver/connect.py, driver/location.py and main.py. The RSD / DVT location flow informed the new independent GPL-3.0-or-later helper; implementation uses pymobiledevice3 11.44.0 instead of upstream's older 2.46.1 API. No upstream iOS 17 driver binaries were imported.
- The original iOS <17 backend remains in vrun/device.py. vrun/modern.py delegates only iOS >=17 devices to the helper through JSON-line pipes; running statistics and desktop settings remain shared.
- New work: adaptive light/dark Windows themes, wheel-safe inputs, live route progress visualization, Qt desktop interface, background device workflow, explicit device targeting, cancellable location playback, closed-loop lap estimates, one-shot distance reminders, installer bootstrap, tests and packaging.
- The legacy CLI files remain in history. VRun's entry point is main.py and its active implementation is the vrun package.

Original project credits include iOSFakeRun, libimobiledevice, and Nuitka. Their contributions and original notices are not replaced by the new product name.
