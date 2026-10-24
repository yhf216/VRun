# Upstream attribution

VRun is derived from https://github.com/iOSRealRun/iOSRealRun-cli.

- Baseline: 1710c72a60a704996bcf7d7b5e5f92f49687af39 (docs: update links).
- Upstream Git history and MPL-2.0 LICENSE are preserved.
- The coordinate conversion in vrun/coordinates.py is adapted from tools/run.py.
- The Windows device tools and developer disk images are inherited without modification.
- HNroute.txt is an upstream route. ZJG-west.txt and ZJG-east.txt are the user's west_test.txt and east_test.txt, renamed with authorization.
- New work: Qt desktop interface, background device workflow, explicit device targeting, cancellable location playback, closed-loop lap estimates, one-shot distance reminders, installer bootstrap, tests and packaging.
- The legacy CLI files remain in history. VRun's entry point is main.py and its active implementation is the vrun package.

Original project credits include iOSFakeRun, libimobiledevice, and Nuitka. Their contributions and original notices are not replaced by the new product name.
