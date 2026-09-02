from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import platform, subprocess, sys
from typing import Any

from .action_harvest import generate_action_harvest_cases, planned_action_harvest_actions, run_action_harvest
from .budget import ExternalActionBudget
from .decision_harvest import evaluate_harvest_completion
from .evidence import BlackMagicEvidenceStore
from .types import json_safe


def _git_sha() -> str | None:
    try: return subprocess.check_output(["git","rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip() or None
    except Exception: return None


def run_action_from_config(config: dict[str,Any], models: list[Any], output_dir: str|Path, *, run_id: str) -> dict[str,Any]:
    if not models: raise ValueError("action harvest requires models")
    for model in models:
        if getattr(model,"capture_content",True) is not True: raise ValueError("capture_content=true required")
        if int(getattr(model,"max_retries",0) or 0)!=0: raise ValueError("adapter retries prohibited")
    root_cfg=dict(config.get("black_magic") or {}); section=dict(root_cfg.get("action_harvest") or {})
    if not section: raise ValueError("black_magic.action_harvest required")
    seed=int(root_cfg.get("seed",20260901)); case_count=int(section.get("case_count",100)); reserve=int(section.get("diagnostic_reserve",300)); arms=tuple(str(x) for x in section.get("arms",("DIRECT","CHECKED","INVERTED"))); cap=int(section.get("action_cap",1200))
    if cap>1200: raise ValueError("action cap exceeds immutable 1200")
    planned=planned_action_harvest_actions(len(models),case_count,len(arms),reserve)
    if planned>cap: raise ValueError(f"planned external actions {planned} exceed cap {cap}; refusing before first call")
    root=Path(output_dir)/"black-magic"/"action_harvest"/str(run_id); store=BlackMagicEvidenceStore(root,experiment_name="action_harvest",run_id=str(run_id)); budget=ExternalActionBudget("action_harvest",cap)
    cases=generate_action_harvest_cases(seed=seed,case_count=case_count); trials,metrics,findings=run_action_harvest(models=models,cases=cases,arms=arms,run_id=str(run_id),budget=budget,store=store); completion=evaluate_harvest_completion(findings,budget_ok=budget.used<=cap); metrics["completion"]=completion
    instrument=all(str(getattr(m,"provider",""))=="mock" for m in models)
    final=store.finalize(preregistration={"experiment":"action_harvest","status":"INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE" if instrument else "REAL-MODEL EVIDENCE HARVEST","hard_external_action_cap":1200,"configured_external_action_cap":cap,"planned_max_external_actions":planned,"diagnostic_reserve":reserve,"hidden_oracle_model_visible":False},config={"black_magic":json_safe(root_cfg),"effective_case_count":case_count,"effective_arms":list(arms)},provenance={"generated_at":datetime.now(timezone.utc).isoformat(),"git_sha":_git_sha(),"python_version":sys.version,"platform":platform.platform(),"instrument_validation":instrument,"models":[{"model":getattr(m,"model",None),"provider":getattr(m,"provider",None)} for m in models]},metrics=metrics,budget=budget.to_dict(),trials=trials,findings=findings)
    if final["integrity"]["status"]!="OK" or not completion["pass"]: raise RuntimeError({"integrity":final["integrity"],"completion":completion})
    return {"root":str(root),"budget":budget.to_dict(),"metrics":metrics,"planned_external_actions":planned,"instrument_validation":instrument}
