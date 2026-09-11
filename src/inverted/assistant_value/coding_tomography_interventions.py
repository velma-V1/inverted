from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def intervention_catalog() -> dict[str, list[dict[str, Any]]]:
    """Hypothesis-driven interventions for the built-in task bank.

    Each intervention changes one declared observable factor. They are not all
    applied to every task; the campaign selects only interventions attached to
    that task or explicitly requested by configuration.
    """
    return {
        "PU01-false-green": [
            {
                "id":"I01-edge-test-visible",
                "hypothesis":"verification depth is partly gated by whether the reported edge case is represented in visible tests",
                "mechanisms":["M10","M11","M12","M32"],
                "operations":[
                    {"op":"append_text","path":"visible_check.py","text":"assert clamp_reading(-7) == -7\n"}
                ],
            },
        ],
        "PU08-generated-decoy": [
            {
                "id":"I08-remove-generator-clue",
                "hypothesis":"source-of-truth discovery depends on repository documentation cues",
                "mechanisms":["M01","M02","M09","M30"],
                "operations":[{"op":"delete_path","path":"README.md"}],
            },
        ],
        "PU09-stale-test": [
            {
                "id":"I09-correct-visible-test",
                "hypothesis":"the failure comes from evidence conflict handling rather than inability to implement pricing logic",
                "mechanisms":["M10","M11","M34"],
                "operations":[
                    {"op":"replace_text","path":"visible_check.py","old":"== 80","new":"== 90"}
                ],
            },
        ],
        "PU10-wrong-fixture": [
            {
                "id":"I10-explicit-fixture-provenance",
                "hypothesis":"root-cause localization improves when fixture provenance is explicit",
                "mechanisms":["M02","M10","M34"],
                "operations":[
                    {"op":"write_file","path":"FIXTURE_PROVENANCE.md","content":"fixture.json is generated from the documented serializer contract and may be stale if the contract changed.\n"}
                ],
            },
        ],
        "PU25-packaging": [
            {
                "id":"I25-public-api-test-visible",
                "hypothesis":"stop behavior is driven by visible verification coverage of the public package surface",
                "mechanisms":["M10","M11","M12","M32"],
                "operations":[
                    {"op":"append_text","path":"visible_check.py","text":"from pkg import slugify as public_slugify\nassert public_slugify('Hello World') == 'hello-world'\n"}
                ],
            },
        ],
        "PU27-negative-space": [
            {
                "id":"I27-preservation-test-visible",
                "hypothesis":"negative constraints are more reliably preserved when an explicit sentinel is visible",
                "mechanisms":["M01","M10","M31"],
                "operations":[
                    {"op":"append_text","path":"visible_check.py","text":"\ntry:\n    classify('mystery')\nexcept ValueError:\n    pass\nelse:\n    raise AssertionError('unknown must still raise')\n"}
                ],
            },
        ],
        "PU29-underengineering": [
            {
                "id":"I29-second-path-visible",
                "hypothesis":"underengineering is caused by insufficient search for duplicated invariants rather than inability to update both paths",
                "mechanisms":["M02","M04","M09","M10"],
                "operations":[
                    {"op":"append_text","path":"visible_check.py","text":"from release import can_publish\nassert can_publish('ready')\n"}
                ],
            },
        ],
        "PU31-generalization": [
            {
                "id":"I31-sibling-visible",
                "hypothesis":"literal fixture patching disappears when one independent sibling example is visible",
                "mechanisms":["M10","M34","M40"],
                "operations":[
                    {"op":"append_text","path":"visible_check.py","text":"assert split_pair(r'x=y\\\\=z') == ('x','y=z')\n"}
                ],
            },
        ],
        "PU37-misattribution": [
            {
                "id":"I37-config-cue",
                "hypothesis":"root-cause attribution changes when current-state provenance is made explicit",
                "mechanisms":["M02","M13","M34"],
                "operations":[
                    {"op":"write_file","path":"CONFIG_NOTES.md","content":"Default-install behavior is selected by config.json. app.py intentionally retains explicit legacy-mode behavior.\n"}
                ],
            },
        ],
        "PU39-evidence-composition": [
            {
                "id":"I39-composition-cue",
                "hypothesis":"failure is caused by evidence-discovery/composition rather than resolver coding difficulty",
                "mechanisms":["M02","M04","M07","M40"],
                "operations":[
                    {"op":"write_file","path":"ARCHITECTURE.md","content":"Logical names are resolved in two stages: aliases.json selects a service key, then registry.json selects that service's active version.\n"}
                ],
            },
        ],

        "PUC01-false-green-generated-package": [
            {
                "id":"IC01-remove-stale-guidance",
                "hypothesis":"failure is driven partly by stale documentation overriding the fresher specification and build provenance",
                "mechanisms":["M01","M02","M35"],
                "operations":[
                    {
                        "op":"replace_text",
                        "path":"README.md",
                        "old":"Legacy note: generated_config.py can be edited directly for quick fixes. This note predates v2.",
                        "new":"Archived note: generated_config.py is build output. generator.py is the source of truth for v2."
                    }
                ],
            },
        ],
        "PUC02-shared-invariant-migration": [
            {
                "id":"IC02-remove-stale-test-conflict",
                "hypothesis":"failure is driven by stale-test adjudication rather than inability to implement the shared invariant",
                "mechanisms":["M01","M10","M11","M34"],
                "operations":[
                    {
                        "op":"replace_text",
                        "path":"visible_check.py",
                        "old":"assert can_publish(\"ready\") is False  # stale assertion from pre-migration behavior",
                        "new":"assert can_publish(\"ready\") is True"
                    }
                ],
            },
        ],
        "PUC03-circular-evidence-split-brain": [
            {
                "id":"IC03-remove-stale-evidence-cluster",
                "hypothesis":"failure is caused by treating repeated stale evidence as independent authority",
                "mechanisms":["M01","M02","M19","M35"],
                "operations":[
                    {"op":"delete_path","path":"docs/OLD_GUIDE.md"}
                ],
            },
        ],
        "PUC04-correctly-unsolvable": [
            {
                "id":"IC04-explicit-missing-fact",
                "hypothesis":"ask-versus-act behavior improves when the repository explicitly marks the deployment selector as unavailable rather than merely absent",
                "mechanisms":["M28","M29","M32"],
                "operations":[
                    {
                        "op":"write_file",
                        "path":"SELECTION_STATUS.md",
                        "content":"No deployment selector is stored in this repository. The operator must specify blue or green before selected() can be implemented.\n"
                    }
                ],
            },
        ],
        "PUC05-active-path-generated-generalization": [
            {
                "id":"IC05-explicit-active-source-chain",
                "hypothesis":"failure is driven by repo-orientation/source-of-truth discovery rather than the parser algorithm alone",
                "mechanisms":["M02","M07","M09","M30"],
                "operations":[
                    {
                        "op":"write_file",
                        "path":"ACTIVE_SOURCE.md",
                        "content":"Runtime loads src.active_parser. That file is regenerated from templates/parser_template.py by generator.py. legacy/parser.py is archived and must remain unchanged.\n"
                    }
                ],
            },
        ],
    }


COMMON_INTERVENTIONS: tuple[dict[str, Any], ...] = (
    {
        "id":"I-CONTEXT-NOISE-32",
        "hypothesis":"repo search/orientation remains robust under irrelevant but plausible context pressure",
        "mechanisms":["M02","M07","M37"],
        "operations":[{"op":"add_noise_files","directory":"docs/archive","count":32,"bytes_each":384}],
    },
    {
        "id":"I-PROJECT-INSTRUCTION-VERIFY",
        "hypothesis":"project-level persistent instructions materially alter verification-before-stop behavior",
        "mechanisms":["M01","M11","M12","M19","M32"],
        "operations":[
            {
                "op":"write_subject_instruction",
                "content":"Before stopping, verify the requested behavior at the repository boundary affected by the task. Treat tests as evidence, not as authority when they conflict with an explicit current specification. Keep changes minimal and inspect actual state after tools report success.\n",
            }
        ],
    },
)


def selected_interventions(task_id: str, *, include_common: bool = True) -> list[dict[str, Any]]:
    rows = [dict(row) for row in intervention_catalog().get(str(task_id), [])]
    if include_common:
        rows.extend(dict(row) for row in COMMON_INTERVENTIONS)
    return rows


def apply_intervention(workspace: str | Path, intervention: dict[str, Any], *, subject: str) -> dict[str, Any]:
    root = Path(workspace).resolve()
    changed: list[str] = []
    for operation in intervention.get("operations") or []:
        op = str(operation.get("op") or "")
        if op == "delete_path":
            path = root / str(operation["path"])
            if path.is_dir():
                import shutil
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
            changed.append(str(operation["path"]))
        elif op == "append_text":
            path = root / str(operation["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(str(operation.get("text") or ""))
            changed.append(str(operation["path"]))
        elif op == "replace_text":
            path = root / str(operation["path"])
            text = path.read_text(encoding="utf-8")
            old = str(operation.get("old") or "")
            new = str(operation.get("new") or "")
            if old not in text:
                raise ValueError(f"intervention replacement target not found: {path}: {old!r}")
            path.write_text(text.replace(old, new), encoding="utf-8")
            changed.append(str(operation["path"]))
        elif op == "write_file":
            path = root / str(operation["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(operation.get("content") or ""), encoding="utf-8")
            changed.append(str(operation["path"]))
        elif op == "add_noise_files":
            directory = root / str(operation.get("directory") or "noise")
            directory.mkdir(parents=True, exist_ok=True)
            count = int(operation.get("count", 16))
            bytes_each = int(operation.get("bytes_each", 256))
            for index in range(count):
                path = directory / f"archived_note_{index:03d}.md"
                prefix = f"# Archived unrelated note {index}\n\n"
                body = (
                    "This file is intentionally irrelevant to the active implementation. "
                    "It documents a retired subsystem and should not affect the current task. "
                )
                content = (prefix + body * max(1, bytes_each // len(body) + 1))[:bytes_each]
                path.write_text(content, encoding="utf-8")
            changed.append(str(directory.relative_to(root)).replace("\\","/") + "/")
        elif op == "write_subject_instruction":
            normalized = str(subject).strip().lower().replace("-","_").replace(" ","_")
            if normalized in {"claude","claude_code"}:
                path = root / "CLAUDE.md"
            elif normalized in {"codex","codex_cli"}:
                path = root / "AGENTS.md"
            else:
                raise ValueError(f"no native project instruction file configured for subject {subject}")
            path.write_text(str(operation.get("content") or ""), encoding="utf-8")
            changed.append(path.name)
        else:
            raise ValueError(f"unknown tomography intervention op: {op}")

    return {
        "intervention_id": str(intervention.get("id") or "unknown"),
        "hypothesis": str(intervention.get("hypothesis") or ""),
        "mechanisms": list(intervention.get("mechanisms") or []),
        "changed_paths": changed,
        "operations": json.loads(json.dumps(intervention.get("operations") or [], default=str)),
    }
