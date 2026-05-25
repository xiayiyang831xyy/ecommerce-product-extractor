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
    "核心卖点", "价格与促销", "目标用户", "使用场景", "售后保障",
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
        "目标用户": ["年轻人"], "使用场景": ["居家"], "售后保障": "7天退换",
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
        "目标用户": [], "使用场景": [], "售后保障": None,
    })
    with patch("extractor.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_claude_response(sample_json)
        result = extract_knowledge(["fake_base64_screenshot"])
    assert result["品牌介绍"] is None
    assert result.get("销售话术") is None  # field no longer extracted


# ---------------------------------------------------------------------------
# Task 5: get_missing_fields + midscene_fallback tests
# ---------------------------------------------------------------------------

from extractor import get_missing_fields, midscene_fallback


def test_get_missing_fields_detects_nulls():
    data = {
        "物料名": "X", "品牌介绍": "Y", "产品介绍": "Z",
        "产品分类": "A", "核心卖点": ["k1"],
        "价格与促销": {"原价": None, "活动价": None, "优惠规则": None},
        "目标用户": ["u1"], "使用场景": ["s1"], "售后保障": None,
    }
    missing = get_missing_fields(data)
    assert "售后保障" in missing
    assert "价格与促销" in missing


def test_get_missing_fields_returns_empty_when_complete():
    data = {
        "物料名": "X", "品牌介绍": "Y", "产品介绍": "Z",
        "产品分类": "A", "核心卖点": ["k1"],
        "价格与促销": {"原价": 100, "活动价": 80, "优惠规则": "折扣"},
        "目标用户": ["u1"], "使用场景": ["s1"], "售后保障": "7天退换",
    }
    assert get_missing_fields(data) == []


def test_midscene_fallback_returns_list():
    missing = ["常见问题", "售后保障"]
    with patch("extractor.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("extractor.capture_screenshots") as mock_cap:
            mock_cap.return_value = ["fake_b64"]
            result = midscene_fallback("https://example.com", missing)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Task 6: generate_dialogs + print_result tests
# ---------------------------------------------------------------------------

from extractor import generate_dialogs, print_result


def test_generate_dialogs_returns_string():
    knowledge = {"物料名": "测试", "核心卖点": ["快", "好"]}
    with patch("extractor.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_claude_response(
            "Q: 好用吗？\nA: 非常好用，快速又高效。"
        )
        result = generate_dialogs(knowledge)
    assert isinstance(result, str)
    assert "Q:" in result


def test_print_result_contains_all_sections(capsys):
    url = "https://example.com/product"
    knowledge = {
        "物料名": "测试商品", "品牌介绍": "品牌A", "产品介绍": "好",
        "产品分类": "电子", "核心卖点": ["快"],
        "价格与促销": {"原价": 100, "活动价": 80, "优惠规则": None},
        "目标用户": ["年轻人"], "使用场景": ["居家"], "售后保障": None,
    }
    dialogs = "Q: 好用吗？\nA: 是的。"
    print_result(url, knowledge, dialogs)
    captured = capsys.readouterr()
    assert "测试商品" in captured.out
    assert "期望学到知识" in captured.out
    assert "备注" in captured.out
    assert "Q: 好用吗" in captured.out
