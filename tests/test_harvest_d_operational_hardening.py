import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import inverted.harvest_d.d3_closure_cli as closure_cli
import inverted.harvest_d.d4_qwen_cli as d4_cli
from inverted.harvest_d.d3_closure_cli import load_frozen_d4_policy


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_d4_preflight_returns_exact_model_digest(monkeypatch):
    payload = {"models": [{"name": "qwen3.5:9b-q8_0", "digest": "sha-qwen"}]}
    monkeypatch.setattr(d4_cli, "urlopen", lambda request, timeout: _Response(payload))
    config = d4_cli.load_d4_config("configs/harvest-d-d4-qwen-policy.json")
    result = d4_cli._ollama_preflight(config)
    assert result["model_id"] == "qwen3.5:9b-q8_0"
    assert result["model_digest"] == "sha-qwen"


def test_closure_preflight_returns_digest_for_every_required_model(monkeypatch):
    config = closure_cli.load_closure_config("configs/harvest-d-d3-closure-v2.json")
    payload = {"models": [
        {"name": config["models"]["SMALL_A"], "digest": "sha-small"},
        {"name": config["models"]["QWEN"], "digest": "sha-qwen"},
    ]}
    monkeypatch.setattr(closure_cli, "urlopen", lambda request, timeout: _Response(payload))
    result = closure_cli._ollama_preflight(config)
    assert result["model_digests"] == {
        config["models"]["SMALL_A"]: "sha-small",
        config["models"]["QWEN"]: "sha-qwen",
    }


def test_frozen_d4_policy_rejects_same_tag_with_different_digest(tmp_path: Path):
    path = tmp_path / "d4_frozen_policy.json"
    path.write_text(json.dumps({
        "state": "FROZEN",
        "policy_id": "THINK_OFF",
        "model_id": "qwen3.5:9b-q8_0",
        "model_digest": "old-digest",
        "chat_options": {"think": False},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        load_frozen_d4_policy(
            path,
            expected_model="qwen3.5:9b-q8_0",
            expected_digest="new-digest",
        )


def test_closure_cli_returns_nonzero_for_incomplete_real_campaign(monkeypatch, tmp_path: Path):
    config_path = Path("configs/harvest-d-d3-closure-v2.json")
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({
        "state": "FROZEN", "policy_id": "DEFAULT", "model_id": "qwen3.5:9b-q8_0",
        "model_digest": "sha-qwen", "chat_options": {},
    }), encoding="utf-8")

    monkeypatch.setattr(closure_cli, "_ollama_preflight", lambda config: {
        "model_digests": {
            config["models"]["SMALL_A"]: "sha-small",
            config["models"]["QWEN"]: "sha-qwen",
        }
    })
    monkeypatch.setattr(closure_cli, "_build_adapters", lambda config: {"SMALL_A": object(), "QWEN": object()})

    class _Campaign:
        def __init__(self, output, **kwargs):
            self.output = Path(output)
            self.output.mkdir(parents=True, exist_ok=True)
        def run(self, max_calls=None):
            (self.output / "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json").write_text(
                json.dumps({"final_state": "EVIDENCE_CEILING_REACHED"}), encoding="utf-8"
            )
            return SimpleNamespace(final_state="EVIDENCE_CEILING_REACHED")

    monkeypatch.setattr(closure_cli, "D3ClosureCampaign", _Campaign)
    rc = closure_cli.main([
        "--config", str(config_path), "--output", str(tmp_path / "out"),
        "--d4-policy-file", str(policy), "--max-calls", "1",
    ])
    assert rc == 2


def test_launchers_always_revalidate_post_d3_and_flatten_test_arrays():
    d4 = Path("scripts/run-harvest-d-d4-qwen-policy.ps1").read_text(encoding="utf-8")
    closure = Path("scripts/run-harvest-d-d3-closure-v2.ps1").read_text(encoding="utf-8")
    assert "if (-not (Test-Path $GapRegistry))" not in d4
    assert "post_d3_cli" in d4
    assert "$D4Tests = @(" in closure
    assert "if (-not (Test-Path $GapRegistry))" not in closure


def test_ci_executes_both_real_powershell_launchers_in_model_free_mode():
    text = Path(".github/workflows/harvest-d-validation.yml").read_text(encoding="utf-8")
    assert "windows-launcher-model-free" in text
    assert "run-harvest-d-d4-qwen-policy.ps1" in text
    assert "run-harvest-d-d3-closure-v2.ps1" in text
    assert "-ModelFreeOnly" in text
