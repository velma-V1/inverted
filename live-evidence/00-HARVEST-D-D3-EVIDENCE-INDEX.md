# HARVEST D — D3 EVIDENCE INDEX

Evidence branch:

    evidence/harvest-d-d3-20260903

Base historical commit:

    17fcdd465fc860748e945dcc03d9f4c4b75e5dce

## 1. D3 Focused Validation

Evidence state:

    FORENSIC_RECONSTRUCTION

Run window:

    2026-09-03 approximately 10:34–10:36 local time

Known validation sequence:

    Initial: 100 passed / 1 failed
    Repaired: 101 passed

Archive:

    live-evidence/harvest-d-d3-focused-validation-20260903-103611/D3-FOCUSED-101-SUITE-DATA-DUMP-20260904-081616.zip

SHA-256:

    CF505F7F999C6477FFEEEB60769F086215C397F603543854DAED93BD27702DA3

IMPORTANT:
This archive is a forensic reconstruction from surviving source,
compiled pytest artifacts, pytest state, provenance, and recovered
evidence. It must not be promoted to the same provenance class as a
fully persisted raw campaign.

## 2. D3 Zero-Call / Model-Free Gate

Evidence state:

    PERSISTED_MODEL_FREE_RUN

Timestamp:

    2026-09-03 10:36:12 local time

Archive:

    live-evidence/harvest-d-d3-model-free-gate-20260903-103612/D3-ZERO-CALL-MODEL-FREE-GATE-DATA-DUMP-20260904-081616.zip

SHA-256:

    46AC0C354BE74F531D7B3BABEA5F386C3EE4E32BE32E3CB4DF99CDFA1BACCA6F

Properties:

    Mode: MODEL_FREE
    Physical model calls: 0
    Planner candidates: 2108

## 3. D3 Real Local Campaign

Evidence state:

    RAW_PERSISTED_REAL_LOCAL_CAMPAIGN

Timestamp:

    2026-09-03 18:51:37 local time

Archive:

    live-evidence/harvest-d-d3-real-20260903-185137/D3-COMPLETE-CAMPAIGN.zip

SHA-256:

    371588D6C5616D371E7EF891E939271F0AF09AC6462A0DF00F8B1486CFC4AC2B

Properties:

    Campaign: HARVEST_D_D3_AUTOMATED_TOMOGRAPHY
    Mode: REAL_LOCAL
    Physical model calls: 632
    Planner candidates: 2108
    Audit passed: true

## Evidence precedence

The real persisted campaign outranks the model-free gate for empirical
model-behavior claims.

The persisted model-free gate is authoritative for proving the zero-call
execution path and associated deterministic artifacts.

The focused-validation archive is retained as historical forensic
evidence and must remain explicitly labeled as a reconstruction.
