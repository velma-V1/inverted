from pathlib import Path

from inverted.test3_repo_evidence import (
    load_repo_evidence,
    repo_s0_source_specs,
    verify_repo_evidence,
)


def test_committed_empirical_sources_are_complete_and_provenanced():
    root = Path(__file__).resolve().parents[1]
    evidence = load_repo_evidence(root / "evidence")

    assert evidence["schema_version"] == 1
    assert {row["source_id"] for row in evidence["sources"]} == {
        "test1",
        "test2-tier-a",
        "test2-model-free",
    }

    errors = verify_repo_evidence(root / "evidence", verify_hashes=False)
    assert errors == []

    test1 = next(row for row in evidence["sources"] if row["source_id"] == "test1")
    test2 = next(row for row in evidence["sources"] if row["source_id"] == "test2-tier-a")
    model_free = next(row for row in evidence["sources"] if row["source_id"] == "test2-model-free")

    assert (root / test1["repo_path"] / "SHA256SUMS.csv").is_file()
    assert (root / test1["repo_path"] / "trials.csv").is_file()
    assert (root / test1["repo_path"] / "events.jsonl").is_file()
    assert (root / test2["repo_path"] / "SHA256SUMS.csv").is_file()
    assert (root / test2["repo_path"] / "model_calls.jsonl").is_file()
    assert model_free["committed"] is False
    assert model_free["regeneration"]


def test_repo_source_specs_bind_exact_frozen_sources_and_generated_model_free(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    generated = tmp_path / "test2-model-free"
    generated.mkdir()

    specs = repo_s0_source_specs(root / "evidence", generated)

    assert [spec[0] for spec in specs] == ["test1", "test2-tier-a", "test2-model-free"]
    assert [spec[1] for spec in specs] == ["test1", "test2_tier_a", "test2_model_free"]
    assert specs[0][2].name == "decisive-20260831-054125-COMPLETE-DATA-PACKET"
    assert specs[1][2].name == "test2-local-20260831-213407-93922d"
    assert specs[2][2] == generated
