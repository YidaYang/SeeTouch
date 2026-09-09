"""GeminiReasoner 单元测试。"""

import os

import pytest

from seetouch.reasoning.gemini import GeminiConfig


def test_config_from_env_success(monkeypatch):
    """测试从环境变量加载配置。"""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-2.5-flash")

    config = GeminiConfig.from_env()

    assert config.api_key == "test-key-123"
    assert config.model_id == "gemini-2.5-flash"


def test_config_from_env_missing_key(monkeypatch):
    """测试缺少 API key 时抛出异常。"""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("VLM_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="missing GEMINI_API_KEY"):
        GeminiConfig.from_env()


def test_config_fallback_to_vlm_key(monkeypatch):
    """测试回退到 VLM_API_KEY。"""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("VLM_API_KEY", "fallback-key")

    config = GeminiConfig.from_env()
    assert config.api_key == "fallback-key"


def test_config_default_model():
    """测试默认模型配置。"""
    config = GeminiConfig(api_key="test-key")
    assert config.model_id == "gemini-3.1-flash-lite"
    assert config.history_window == 8


def test_config_custom_params():
    """测试自定义参数配置。"""
    config = GeminiConfig(
        api_key="test-key",
        model_id="gemini-2.5-pro",
        temperature=0.8,
        top_p=0.9,
        max_tokens=1024,
        history_window=5,
    )
    assert config.model_id == "gemini-2.5-pro"
    assert config.temperature == 0.8
    assert config.top_p == 0.9
    assert config.max_tokens == 1024
    assert config.history_window == 5
