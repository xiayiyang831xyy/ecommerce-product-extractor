import pytest
import base64
from extractor import capture_screenshots


def test_capture_screenshots_returns_list():
    shots = capture_screenshots("https://example.com")
    assert isinstance(shots, list)
    assert len(shots) >= 1


def test_capture_screenshots_are_valid_base64():
    shots = capture_screenshots("https://example.com")
    for shot in shots:
        decoded = base64.b64decode(shot)
        assert len(decoded) > 1000


def test_capture_screenshots_invalid_url_raises():
    with pytest.raises(Exception):
        capture_screenshots("not-a-valid-url")


# ---------------------------------------------------------------------------
# Task 4: extract_knowledge tests
# ---------------------------------------------------------------------------

import json
from unittest.mock import patch, MagicMock
from extractor import extract_knowledge

REQUIRED_FIELDS = [
    "物料名", "品牌介绍", "产品介绍", "产品分类",
    "核心卖点", "价格与促销", "目标用户", "使用场景",
    "销售话术", "常见问题", "售后保障",
]


def _mock_claude_response(json_str: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=json_str)]
    return msg


def test_extract_knowledge_returns_all_fields():
    sample_json = json.dumps({
        "物料名": "测试商品", "品牌介绍": "品牌A", "产品介绍": "好产品",
        "产品分类": "电子", "核心卖点": ["快", "好"],
        "价格与促销": {"原价": 100, "活动价": 80, "优惠规则": None},
        "目标用户": ["年轻人"], "使用场景": ["居家"], "销售话术": "超值",
        "常见问题": [{"问": "Q", "答": "A"}], "售后保障": "7天退换",
    })
    with patch("extractor.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_claude_response(sample_json)
        result = extract_knowledge(["fake_base64_screenshot"])
    assert isinstance(result, dict)
    for field in REQUIRED_FIELDS:
        assert field in result


def test_extract_knowledge_handles_null_fields():
    sample_json = json.dumps({
        "物料名": "X", "品牌介绍": None, "产品介绍": None,
        "产品分类": None, "核心卖点": [],
        "价格与促销": {"原价": None, "活动价": None, "优惠规则": None},
        "目标用户": [], "使用场景": [], "销售话术": None,
        "常见问题": [], "售后保障": None,
    })
    with patch("extractor.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_claude_response(sample_json)
        result = extract_knowledge(["fake_base64_screenshot"])
    assert result["品牌介绍"] is None
    assert result["常见问题"] == []
