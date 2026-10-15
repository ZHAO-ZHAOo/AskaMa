"""Tests for src/llm: DashScope client factory, intake prompt, validation, fallback."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.llm.client import DummyLLM, get_llm_client, resolve_base_url
from src.llm.intake import (
    build_intake_prompt,
    keyword_intake,
    llm_intake,
    parse_json,
    run_intake,
    validate_slots,
)
from src.orchestrator import SessionState, run_pipeline


@pytest.fixture(scope="module")
def config():
    return load_config(PROJECT_ROOT / "contracts")


# ---------------------------------------------------------------- resolve_base_url

def test_resolve_base_url_singapore_workspace(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_WORKSPACE_ID", "ws-abc123")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    url = resolve_base_url()
    assert url == "https://ws-abc123.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"


def test_resolve_base_url_falls_back_to_intl(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert resolve_base_url() == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def test_resolve_base_url_explicit_wins(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1/")
    url = resolve_base_url()
    assert url == "https://example.com/v1"


# ---------------------------------------------------------------- client factory

def test_get_llm_client_returns_dummy_without_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    assert get_llm_client().provider == "dummy"


def test_get_llm_client_disabled_flag(monkeypatch):
    monkeypatch.setenv("LLM_DISABLED", "1")
    assert get_llm_client().provider == "dummy"


# ---------------------------------------------------------------- prompt

def test_build_intake_prompt_contains_modules_and_slots(config):
    prompt = build_intake_prompt(config)
    for mid in config.module_ids:
        assert mid in prompt
    # 抽查关键槽位与允许值
    assert "heavy_bleeding" in prompt
    assert "flow_compared_to_usual" in prompt
    assert "much_more" in prompt
    assert "pain_severity_0_10" in prompt


# ---------------------------------------------------------------- parse_json

def test_parse_json_fenced():
    assert parse_json('```json\n{"module": "x"}\n```') == {"module": "x"}


def test_parse_json_with_surrounding_text():
    assert parse_json('好的，结果如下：{"module": "heavy_bleeding", "slots": {}} 完毕') == {
        "module": "heavy_bleeding",
        "slots": {},
    }


def test_parse_json_garbage_returns_empty():
    assert parse_json("抱歉，我无法理解") == {}


# ---------------------------------------------------------------- validate_slots

def test_validate_slots_keeps_valid_drops_invalid(config):
    payload = {
        "slots": {
            "flow_compared_to_usual": {"value": "much_more", "confidence": 0.9},  # 合法 enum
            "pain_severity_0_10": {"value": 7, "confidence": 0.8},               # 合法 int
            "pain_severity_0_10_bad": {"value": 99, "confidence": 0.8},          # 越界 int
            "fever_status": {"value": "not_a_value", "confidence": 0.5},          # 非法 enum
            "on_blood_thinner": {"value": "true"},                                # 合法 bool 字符串
            "heart_racing_or_short_of_breath": {"value": "maybe"},                # 非法 bool
            "unknown_slot_xyz": {"value": 1},                                     # 未知槽位
        }
    }
    out = validate_slots(payload, config)
    assert out["flow_compared_to_usual"]["value"] == "much_more"
    assert out["pain_severity_0_10"]["value"] == 7
    assert "pain_severity_0_10_bad" not in out
    assert "fever_status" not in out
    assert out["on_blood_thinner"]["value"] is True
    assert "heart_racing_or_short_of_breath" not in out
    assert "unknown_slot_xyz" not in out
    # 默认 confidence 规范化
    assert out["on_blood_thinner"]["confidence"] == 1.0
    assert out["flow_compared_to_usual"]["status"] == "answered"


def test_validate_slots_duration(config):
    payload = {"slots": {"pain_duration": {"value": {"value": 3, "unit": "days"}}}}
    out = validate_slots(payload, config)
    assert out["pain_duration"]["value"] == {"value": 3, "unit": "days"}

    bad = {"slots": {"pain_duration": {"value": {"value": 3, "unit": "years"}}}}
    assert validate_slots(bad, config) == {}


# ---------------------------------------------------------------- intake paths

def test_keyword_intake(config):
    result = run_intake("这次月经出血特别多，都弄到裤子上了", config, llm=None)
    assert result.source == "keyword"
    assert result.module == "heavy_bleeding"
    assert "bleeding_through_clothes_or_bedding" in result.slots
    assert "flow_compared_to_usual" in result.slots


def test_keyword_intake_recognises_intermenstrual_spotting_without_pain(config):
    result = run_intake("月经结束几天后又有一点淡红色血丝，要用护垫，但肚子不痛", config, llm=None)
    assert result.module == "irregular_or_intermenstrual_bleeding"
    assert result.slots["bleeding_present"]["value"] == "true"
    assert result.slots["pain_present"]["value"] == "false"
    assert result.slots["bleeding_between_periods"]["value"] == "true"


def test_keyword_intake_recognises_late_period_wording(config):
    result = run_intake("我月经迟了十天，最近有性生活，有点担心", config, llm=None)
    assert result.module == "late_or_missed_period"


def test_llm_intake_with_dummy(config):
    result = run_intake("这次月经出血特别多，还有点发烧", config, llm=DummyLLM())
    assert result.source == "llm"
    assert result.used_llm is True
    assert result.module == "heavy_bleeding"
    assert result.slots["flow_compared_to_usual"]["value"] == "much_more"
    assert result.slots["fever_status"]["value"] == "feels_feverish_not_measured"


def test_llm_intake_disabled_uses_keyword(config):
    result = run_intake("这次月经出血特别多", config, llm=DummyLLM(), enabled=False)
    assert result.source == "keyword"
    assert result.used_llm is False


def test_llm_intake_exception_falls_back(config):
    class BrokenLLM(DummyLLM):
        def complete(self, messages, temperature=0.2):
            raise RuntimeError("network down")

    result = run_intake("这次月经出血特别多", config, llm=BrokenLLM())
    assert result.source == "keyword"
    assert result.module == "heavy_bleeding"


def test_llm_intake_empty_output_falls_back(config):
    class EmptyLLM(DummyLLM):
        def complete(self, messages, temperature=0.2):
            return "{}"

    result = run_intake("这次月经出血特别多", config, llm=EmptyLLM())
    assert result.source == "keyword"
    assert result.module == "heavy_bleeding"


def test_llm_intake_bad_module_rejected(config):
    class BadModuleLLM(DummyLLM):
        def complete(self, messages, temperature=0.2):
            import json
            return json.dumps({"module": "not_a_module", "slots": {}})

    result = run_intake("这次月经出血特别多", config, llm=BadModuleLLM())
    # 模块非法 → keyword 兜底补模块
    assert result.module == "heavy_bleeding"


# ---------------------------------------------------------------- pipeline integration

def test_run_pipeline_with_dummy_llm(config):
    session = SessionState(session_id="t1")
    resp = run_pipeline(
        "这次月经特别多，都弄到裤子上了，还有点头晕",
        session,
        config,
        llm=DummyLLM(),
        llm_intake_enabled=True,
    )
    assert "events" in resp
    # intake 抽取的槽位进入会话
    assert session.slots.get("flow_compared_to_usual") is not None
    assert session.slots.get("dizziness_or_fainting") is not None
    assert session.active_module == "heavy_bleeding"


def test_run_pipeline_without_llm_unchanged(config):
    """不传 llm 时行为与原来一致（关键词 intake）。"""
    session = SessionState(session_id="t2")
    resp = run_pipeline(
        "月经推迟了十天，有点担心",
        session,
        config,
        llm=None,
    )
    assert session.active_module == "late_or_missed_period"
    assert "events" in resp
