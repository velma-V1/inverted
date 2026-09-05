from __future__ import annotations

import json

from inverted.harvest_d.hd_next1_cli import main


def test_cli_defaults_to_zero_call_preregistration(tmp_path):
    rc = main(["--config", "configs/harvest-d-hd-next-1.json", "--output", str(tmp_path)])
    assert rc == 0
    auth = json.loads((tmp_path / "physical_execution_authorization.json").read_text())
    assert auth["physical_execution_authorized"] is False
    assert auth["physical_model_calls"] == 0


def test_cli_execute_requires_owner_authorization_before_preflight(tmp_path):
    rc = main(["--config", "configs/harvest-d-hd-next-1.json", "--output", str(tmp_path), "--execute"])
    assert rc == 2
