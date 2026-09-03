# Harvest D Implementation Contract

All production code is added under `src/inverted/harvest_d/`; tests under `tests/test_harvest_d_*.py`; config under `configs/harvest-d.json`; CI under `.github/workflows/harvest-d-validation.yml`. Frozen evidence paths are read-only. The implementation must remain model-free in normal CI and must not start Ollama/cloud inference.