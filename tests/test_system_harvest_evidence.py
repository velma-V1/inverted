from inverted.system_harvest.evidence import make_raw_event, verify_event


def test_raw_event_preserves_payload_lineage_and_hash():
    payload = {"request": {"messages": ["a"]}, "stdout": "x\ny", "usage": {"tokens": 9}}
    event = make_raw_event(
        campaign_id="SYSTEM_HARVEST_11", system_id="Aider", example_id="E1",
        attempt_id="A1", event_type="MODEL_IO", ordinal=7, payload=payload,
        parent_ids=("parent-1",), source_version="commit:abc",
        redactions=("credential:sha256:123",),
    )
    assert event.payload == payload
    assert event.parent_ids == ("parent-1",)
    assert event.redactions == ("credential:sha256:123",)
    assert event.content_sha256
    assert event.event_id
    assert verify_event(event) is True


def test_raw_event_hash_detects_payload_mutation():
    event = make_raw_event(
        campaign_id="C", system_id="S", example_id="E", attempt_id="A1",
        event_type="TOOL_IO", ordinal=1, payload={"result": "original"},
        parent_ids=(), source_version="v1",
    )
    object.__setattr__(event, "payload", {"result": "changed"})
    assert verify_event(event) is False
