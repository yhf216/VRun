# SPDX-License-Identifier: MPL-2.0
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def application():
    return QApplication.instance() or QApplication([])
