import hashlib
import json

from inverted.assistant_value.evidence import EvidenceStore


def test_master_index_hashes_match_finalized_nonrecursive_artifacts(tmp_path):
    root = tmp_path / "packet"
    store = EvidenceStore(root, test_name="integrity", run_id="run-index")
    store.finalize(
        preregistration={},
        config={},
        provenance={},
        metrics={},
        budget={"cap": 1, "used": 0, "remaining": 1, "reservations": []},
        trials=[],
        failures=[],
    )

    index = json.loads((root / "00-MASTER-INDEX.json").read_text(encoding="utf-8"))
    indexed_paths = {row["path"] for row in index["artifacts"]}
    assert "COMPLETE-EVIDENCE.txt" not in indexed_paths
    assert "SHA256SUMS.csv" not in indexed_paths
    assert "00-MASTER-INDEX.json" not in indexed_paths

    for row in index["artifacts"]:
        path = root / row["path"]
        assert path.stat().st_size == row["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
