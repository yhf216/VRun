# SPDX-License-Identifier: MPL-2.0
"""VRun Windows desktop entry point."""
import sys


def main():
    if "--install-drivers" in sys.argv:
        from vrun.drivers import install_main
        return install_main()
    from vrun.app import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
