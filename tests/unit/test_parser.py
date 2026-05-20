"""parser.py 单测。"""

from __future__ import annotations

import pytest

from phone_agent.core.action import (
    ACTION_CLICK,
    ACTION_COMPLETE,
    ACTION_OPEN,
    ACTION_SCROLL,
    ACTION_TYPE,
)
from phone_agent.reasoning.parser import ParseError, parse_model_output


SCREEN = (1080, 2400)


def test_parse_plain_json_click():
    raw = '{"action":"CLICK","parameters":{"point":[500,300]}}'
    action = parse_model_output(raw, SCREEN)
    assert action.type == ACTION_CLICK
    assert action.parameters == {"point": [500, 300]}


def test_parse_with_screen_summary_fields_ignored():
    raw = (
        '{"screen_summary":"在桌面","action_summary":"点击设置",'
        '"action":"CLICK","parameters":{"point":[100,200]}}'
    )
    action = parse_model_output(raw, SCREEN)
    assert action.type == ACTION_CLICK
    assert action.parameters == {"point": [100, 200]}


def test_parse_fenced_code_block():
    raw = """这里是模型的解释
```json
{"action":"TYPE","parameters":{"text":"狂飙"}}
```
"""
    action = parse_model_output(raw, SCREEN)
    assert action.type == ACTION_TYPE
    assert action.parameters == {"text": "狂飙"}


def test_parse_open():
    raw = '{"action":"OPEN","parameters":{"app_name":"tv.danmaku.bili"}}'
    action = parse_model_output(raw, SCREEN)
    assert action.type == ACTION_OPEN
    assert action.parameters == {"app_name": "tv.danmaku.bili"}


def test_parse_scroll():
    raw = (
        '{"action":"SCROLL",'
        '"parameters":{"start_point":[500,800],"end_point":[500,200]}}'
    )
    action = parse_model_output(raw, SCREEN)
    assert action.type == ACTION_SCROLL
    assert action.parameters == {"start_point": [500, 800], "end_point": [500, 200]}


def test_parse_complete():
    raw = '{"action":"COMPLETE","parameters":{}}'
    action = parse_model_output(raw, SCREEN)
    assert action.type == ACTION_COMPLETE


def test_parse_pixel_coords_converted_to_normalized():
    # 像素 (540, 1200) on 1080x2400 -> (500, 500) normalized
    raw = '{"action":"CLICK","parameters":{"point":[540,1200]}}'
    action = parse_model_output(raw, SCREEN)
    assert action.parameters["point"] == [500, 500]


def test_parse_alias_app_field():
    raw = '{"action":"OPEN","parameters":{"app":"哔哩哔哩"}}'
    action = parse_model_output(raw, SCREEN)
    assert action.type == ACTION_OPEN
    assert action.parameters == {"app_name": "哔哩哔哩"}


def test_parse_alias_content_for_type():
    raw = '{"action":"TYPE","parameters":{"content":"hello"}}'
    action = parse_model_output(raw, SCREEN)
    assert action.parameters == {"text": "hello"}


def test_parse_simple_text_format():
    raw = "Action: CLICK: [[500, 600]]"
    action = parse_model_output(raw, SCREEN)
    assert action.type == ACTION_CLICK
    assert action.parameters == {"point": [500, 600]}


def test_parse_garbage_raises():
    with pytest.raises(ParseError):
        parse_model_output("hello world this is not json or any action", SCREEN)


def test_parse_invalid_action_type_raises():
    raw = '{"action":"CLAP","parameters":{}}'
    with pytest.raises(ParseError):
        parse_model_output(raw, SCREEN)
