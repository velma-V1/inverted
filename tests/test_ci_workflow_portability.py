from pathlib import Path


WORKFLOWS = (
    Path('.github/workflows/test2-validation.yml'),
    Path('.github/workflows/test3-s0-validation.yml'),
)

POWERSHELL_EXCLUSIONS = (
    'not powershell_launcher_dry_run_executes_repo_local_module',
    'not powershell_launcher_uses_v2_default_dry_run',
)


def test_linux_full_suite_workflows_fetch_parent_commit() -> None:
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding='utf-8')
        assert 'runs-on: ubuntu' in text
        assert 'fetch-depth: 2' in text


def test_linux_full_suite_workflows_exclude_windows_only_launcher_tests() -> None:
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding='utf-8')
        assert 'python -m pytest -q -k' in text
        for exclusion in POWERSHELL_EXCLUSIONS:
            assert exclusion in text
