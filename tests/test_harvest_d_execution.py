import json
import pytest

from inverted.harvest_d.cases import HarvestCase, OracleKind, OracleSpec, load_cases
from inverted.harvest_d.experiment import BoundaryPlanner, BudgetExceeded, CallBudget, ExperimentArm, MatchedExperimentRunner
from inverted.harvest_d.local_run import run_cases
from inverted.harvest_d.models import ModelResponse, OllamaChatAdapter
from inverted.harvest_d.runner import ModelTrialRunner
from inverted.harvest_d.telemetry import SystemInvolvement
from inverted.harvest_d.types import Disposition, RouteMode


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode()


def test_ollama_adapter_parses_provenance_and_token_counts():
    seen = {}
    def opener(req, timeout):
        seen['url'] = req.full_url; seen['body'] = json.loads(req.data)
        return FakeResponse({'model':'qwen3.5:9b-q8_0','message':{'content':'{"answer":1}'},'prompt_eval_count':12,'eval_count':5,'total_duration':1000000})
    r = OllamaChatAdapter('qwen3.5:9b-q8_0', opener=opener).complete('hi')
    assert seen['url'].endswith('/api/chat') and seen['body']['stream'] is False
    assert r.text == '{"answer":1}' and r.input_tokens == 12 and r.output_tokens == 5 and r.model == 'qwen3.5:9b-q8_0'


def test_hidden_json_oracle_evaluates_without_entering_model_prompt():
    c = HarvestCase('c1','F1','semantic',2,'Return JSON',Disposition.EXECUTE,OracleSpec(OracleKind.JSON_EQUALS, {'answer':1}))
    assert c.evaluate('{"answer":1}') and 'answer' not in c.model_prompt()


def test_case_loader_preserves_oracle_separately(tmp_path):
    p = tmp_path/'cases.jsonl'; p.write_text(json.dumps({'case_id':'c1','family':'F1','capability':'semantic','difficulty':1,'prompt':'p','expected_disposition':'EXECUTE','oracle':{'kind':'TEXT_EQUALS','expected':'ok'}})+'\n')
    assert load_cases(p)[0].evaluate('ok')


class SingleFakeAdapter:
    model_id='fake'
    def __init__(self): self.calls=0
    def complete(self, prompt, system=None):
        self.calls += 1; return ModelResponse('ok', 'fake', 3, 1, 2.0, {})


def test_runner_makes_exactly_one_call_and_records_semantic_result():
    a = SingleFakeAdapter(); case = HarvestCase('c','F1','semantic',1,'say ok',Disposition.EXECUTE,OracleSpec(OracleKind.TEXT_EQUALS,'ok'))
    r = ModelTrialRunner().run(case, a, route=RouteMode.ROUTINE_LOCAL, involvement=SystemInvolvement())
    assert a.calls == 1 and r.semantic_success and r.physical_model_call_id and r.route is RouteMode.ROUTINE_LOCAL


def make_case(cid, diff): return HarvestCase(cid,'F1','semantic',diff,'p',Disposition.EXECUTE,OracleSpec(OracleKind.TEXT_EQUALS,'ok'))


class SequenceAdapter:
    def __init__(self, model_id, answers): self.model_id=model_id; self.answers=list(answers); self.calls=0
    def complete(self, prompt, system=None):
        self.calls += 1; return ModelResponse(self.answers.pop(0), self.model_id, 1, 1, 1.0, {})


def test_call_budget_never_allows_hidden_overrun():
    b = CallBudget(2); b.consume(); b.consume()
    with pytest.raises(BudgetExceeded): b.consume()


def test_matched_runner_calls_each_arm_once_per_case_without_retry():
    a1 = SequenceAdapter('small',['ok','bad']); a2 = SequenceAdapter('qwen',['ok','ok'])
    arms = [ExperimentArm('small',a1,RouteMode.ROUTINE_LOCAL,SystemInvolvement()), ExperimentArm('qwen',a2,RouteMode.QWEN_STANDARD,SystemInvolvement(routing=True))]
    results = MatchedExperimentRunner(CallBudget(4)).run([make_case('c1',1),make_case('c2',2)],arms)
    assert len(results) == 4 and a1.calls == 2 and a2.calls == 2 and sum(r.semantic_success for r in results) == 3


def test_boundary_planner_concentrates_untested_case_between_success_and_failure():
    cases = [make_case(f'c{i}',i) for i in range(1,6)]; planner = BoundaryPlanner(cases)
    assert planner.next_case([]).difficulty == 3
    assert planner.next_case([(cases[1],True),(cases[3],False)]).difficulty == 3


def test_local_run_writes_forensic_artifacts_without_oracle_leak(tmp_path):
    cases = tmp_path/'cases.jsonl'; cases.write_text(json.dumps({'case_id':'c1','family':'F1','capability':'semantic','difficulty':1,'prompt':'say ok','expected_disposition':'EXECUTE','oracle':{'kind':'TEXT_EQUALS','expected':'ok'}})+'\n')
    out = tmp_path/'out'; adapter = SingleFakeAdapter(); result = run_cases(cases,out,adapter,route=RouteMode.QWEN_STANDARD,max_calls=1)
    assert result['calls'] == 1 and adapter.calls == 1 and (out/'trials.jsonl').exists() and (out/'SHA256SUMS.csv').exists()
    assert 'say ok' in (out/'prompts.jsonl').read_text() and '"expected"' not in (out/'prompts.jsonl').read_text()
