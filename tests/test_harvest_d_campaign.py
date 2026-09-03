import csv
import hashlib
import json
import pytest

from inverted.harvest_d.artifacts import ArtifactWriter
from inverted.harvest_d.campaign import ConfigError, HarvestDCampaign, HarvestDConfig
from inverted.harvest_d.cli import main


def test_artifact_writer_finalizes_hashes(tmp_path):
    w = ArtifactWriter(tmp_path); w.write_json('a.json', {'x': 1}); w.write_jsonl('b.jsonl', [{'y': 2}]); w.write_csv('c.csv', [{'z': 3}], fieldnames=['z']); w.write_json('00-HARVEST-D-MASTER-INDEX.json', {'status': 'DRY_RUN'}); w.finalize()
    rows = list(csv.DictReader((tmp_path/'SHA256SUMS.csv').open())); names = {r['file'] for r in rows}
    assert {'a.json','b.jsonl','c.csv','00-HARVEST-D-MASTER-INDEX.json'} <= names
    for row in rows: assert hashlib.sha256((tmp_path/row['file']).read_bytes()).hexdigest() == row['sha256']


def test_config_rejects_scope_expansion_and_call_budget_violation():
    with pytest.raises(ConfigError): HarvestDConfig(stages=('D0','D8'), call_ceilings={'D0':0,'D8':1}).validate()
    with pytest.raises(ConfigError): HarvestDConfig(stages=('D0','D1'), call_ceilings={'D0':1,'D1':0}).validate()
    with pytest.raises(ConfigError): HarvestDConfig(stages=('D2',), call_ceilings={'D2':400}).validate()


def test_dry_run_emits_required_artifacts_without_model_calls(tmp_path):
    result = HarvestDCampaign(HarvestDConfig.default()).dry_run(tmp_path); assert result['real_model_calls'] == 0
    required = {'00-HARVEST-D-MASTER-INDEX.json','EVIDENCE-PROVENANCE.json','SHA256SUMS.csv','causal_architecture_readiness_matrix.json','causal_architecture_readiness_matrix.csv','kernel_fault_matrix.csv','transaction_crash_matrix.csv','model_capability_envelope.json','system_involvement_telemetry.jsonl','minimum_required_scaffolding.json','qwen_call_policy.json','promoted_failure_knowledge.jsonl','boundary_ratchet.json','remaining_unknowns.md','test5_handoff.md'}
    assert required <= {p.name for p in tmp_path.iterdir()}
    master = json.loads((tmp_path/'00-HARVEST-D-MASTER-INDEX.json').read_text())
    assert master['mode'] == 'model-free-dry-run' and master['scope_frozen'] is True


def test_cli_dry_run_is_offline_and_successful(tmp_path):
    config = tmp_path/'config.json'; config.write_text(json.dumps(HarvestDConfig.default().to_dict())); out = tmp_path/'out'
    assert main(['--config', str(config), '--output', str(out), '--dry-run']) == 0 and (out/'SHA256SUMS.csv').exists()
