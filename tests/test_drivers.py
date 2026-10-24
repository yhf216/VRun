# SPDX-License-Identifier: MPL-2.0
import tempfile
import pytest
from vrun import drivers


def test_existing_components_are_reused(monkeypatch):
    commands = []
    monkeypatch.setattr(drivers, "components_present", lambda: True)
    monkeypatch.setattr(drivers, "run", lambda args, **kw: commands.append(args) or 0)
    monkeypatch.setattr(drivers, "download", lambda *a: pytest.fail("Should not download for an existing setup"))
    assert drivers.install() == 0
    assert commands == [["sc.exe", "start", "Apple Mobile Device Service"]]


def test_signature_failure_prevents_msi_execution(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(drivers, "components_present", lambda: False)
    monkeypatch.setattr(drivers, "download", lambda *a: None)
    monkeypatch.setattr(drivers, "signature", lambda *a: (_ for _ in ()).throw(RuntimeError("untrusted signature")))
    monkeypatch.setattr(drivers, "run", lambda args, **kw: commands.append(args))
    with pytest.raises(RuntimeError, match="untrusted"):
        drivers.install()
    assert not commands
