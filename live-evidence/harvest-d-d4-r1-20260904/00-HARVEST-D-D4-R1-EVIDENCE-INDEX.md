# HARVEST D — D4 + R1 EVIDENCE INDEX

R1 execution commit:

    cb5ca86a63eb18d46f601df773889852d0e636f6

## D4 Qwen policy campaign

Evidence state:

    RAW_PERSISTED_REAL_LOCAL_CAMPAIGN

Physical model calls:

    48

Frozen policy:

    DEFAULT

Model:

    qwen3.5:9b-q8_0

Model digest:

    441ec31e4d2aedceb97dd834b036db104d943fbe3dbc1e5c8ac95eeaa9141c77

Archive:

    D4-COMPLETE-CAMPAIGN.zip

SHA-256:

    C60FCEB876FF44803FFB5FD584BF3545EAFAE45FC1B2365A13DB1A0CD7EA044E

## R1 calibration

Evidence state:

    RAW_PERSISTED_REAL_LOCAL_CALIBRATION

Final state:

    R1_CALIBRATION_COMPLETE

Physical model calls:

    24

Qwen model digest:

    441ec31e4d2aedceb97dd834b036db104d943fbe3dbc1e5c8ac95eeaa9141c77

SMALL_A model digest:

    b19683a34698365318287452c1711a7dd94253eba73c1f834e09a09c2b8d9415

Archive:

    R1-CALIBRATION-CAMPAIGN.zip

SHA-256:

    995E7619EE4DCABFE748F50EBB11B3E389C3B8D69F15EC5EF4CA47F32A21D4D2

## Integrity

- Source evidence was validated before archiving.
- D4 and R1 Qwen model digests match exactly.
- Every committed R1 physical call has one STARTED and one COMMITTED journal event.
- Blind retries are forbidden and every committed call has attempt=1.
- Raw requests, raw responses, normalized calls, runtime telemetry, and call ledger counts agree.
- Source directories were fingerprinted before and after packaging and were not mutated.
- Packaging performs zero model inference.
