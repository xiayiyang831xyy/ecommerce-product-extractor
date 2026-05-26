import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import anthropic
from playwright.sync_api import sync_playwright


FALLBACK_TRIGGERS = {"售后保障", "价格与促销"}


# ---------------------------------------------------------------------------
# Screenshot capture
# ---------------------------------------------------------------------------

def capture_screenshots(url: str, max_shots: int = 6) -> list[str]:
    """Return base64-encoded PNG screenshots covering the full page height."""
    screenshots = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        total_height = page.evaluate("document.body.scrollHeight")
        viewport_h = 900
        # Evenly distribute scroll positions across full page, always include bottom
        n = min(max_shots, max(3, total_height // viewport_h + 1))
        step = max(1, (total_height - viewport_h) // (n - 1)) if n > 1 else 0
        positions = [min(i * step, max(0, total_height - viewport_h)) for i in range(n)]
        # Deduplicate while preserving order
        seen = set()
        positions = [p for p in positions if not (p in seen or seen.add(p))]

        for pos in positions:
            page.evaluate(f"window.scrollTo(0, {pos})")
            time.sleep(0.4)
            png_bytes = page.screenshot(full_page=False)
            screenshots.append(base64.b64encode(png_bytes).decode("utf-8"))

        browser.close()
    return screenshots


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _load_prompt(section: str) -> str:
    """Load a named section from prompt.md (section header is # SECTION_NAME)."""
    prompt_path = Path(__file__).parent / "prompt.md"
    text = prompt_path.read_text(encoding="utf-8")
    parts = text.split("# ")
    for part in parts:
        if part.startswith(section):
            lines = part.split("\n", 1)
            return lines[1].strip() if len(lines) > 1 else ""
    raise ValueError(f"Section '{section}' not found in prompt.md")


# ---------------------------------------------------------------------------
# Claude API extraction
# ---------------------------------------------------------------------------

def extract_knowledge(screenshots_b64: list[str]) -> dict:
    """Call Claude API Vision with screenshots, return extracted JSON dict."""
    client = anthropic.Anthropic()
    prompt_text = _load_prompt("EXTRACTION_PROMPT")

    image_content = []
    for b64 in screenshots_b64:
        image_content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    image_content.append({"type": "text", "text": prompt_text})

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        messages=[{"role": "user", "content": image_content}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())
    # Strip any spurious keys not in the defined schema
    allowed = {"物料名", "品牌介绍", "产品介绍", "产品分类", "核心卖点",
               "价格与促销", "目标用户", "使用场景", "售后保障"}
    # Normalize 价格与促销 sub-keys to include 价格区间
    if "价格与促销" in data and isinstance(data["价格与促销"], dict):
        price = data["价格与促销"]
        data["价格与促销"] = {
            "原价": price.get("原价"),
            "活动价": price.get("活动价"),
            "价格区间": price.get("价格区间"),
            "优惠规则": price.get("优惠规则"),
        }
    return {k: v for k, v in data.items() if k in allowed}


# ---------------------------------------------------------------------------
# Missing-field detection
# ---------------------------------------------------------------------------

def get_missing_fields(data: dict) -> list[str]:
    """Return list of field names that are null, empty list, or all-null dict."""
    missing = []
    for key, val in data.items():
        if val is None:
            missing.append(key)
        elif isinstance(val, list) and len(val) == 0:
            missing.append(key)
        elif isinstance(val, dict) and all(v is None for v in val.values()):
            missing.append(key)
    return missing


# ---------------------------------------------------------------------------
# Midscene fallback
# ---------------------------------------------------------------------------

def _build_midscene_yaml(url: str, missing: list[str]) -> str:
    """Build a Midscene YAML script that does a full-page scroll scan."""
    flow_steps = []
    # Always dismiss popups first
    flow_steps.append("      - ai: dismiss any popup, cookie banner, or login dialog if present")
    # Expand interactive sections for specific missing fields
    if "常见问题" in missing:
        flow_steps.append("      - ai: find and expand the FAQ section by clicking on it")
    # Full-page scroll to expose all lazy-loaded content (price often at bottom)
    flow_steps.append("      - aiScroll: {direction: down, distance: 2000}")
    flow_steps.append("      - sleep: 800")
    flow_steps.append("      - aiScroll: {direction: down, distance: 2000}")
    flow_steps.append("      - sleep: 800")
    flow_steps.append("      - aiScroll: {direction: down, distance: 2000}")
    flow_steps.append("      - sleep: 800")
    flow_steps.append("      - aiScroll: {direction: down, distance: 2000}")
    flow_steps.append("      - sleep: 1000")

    steps_str = "\n".join(flow_steps)
    return f"""web:
  url: "{url}"
  viewportWidth: 1280
  viewportHeight: 900

tasks:
  - name: full-page-scan
    flow:
{steps_str}
"""


def midscene_fallback(url: str, missing: list[str]) -> list[str]:
    """Use Midscene CLI to interact with the page, then re-capture screenshots."""
    actionable = [f for f in missing if f in FALLBACK_TRIGGERS]
    if not actionable:
        return []

    yaml_content = _build_midscene_yaml(url, actionable)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        script_path = f.name

    try:
        result = subprocess.run(
            ["midscene", script_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"[Midscene] Warning: {result.stderr[:200]}")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[Midscene] Fallback skipped: {e}")
        return []
    finally:
        os.unlink(script_path)

    return capture_screenshots(url)


# ---------------------------------------------------------------------------
# Dialog generation
# ---------------------------------------------------------------------------

def generate_dialogs(knowledge: dict) -> str:
    """Call Claude API to generate 2-3 Agent Q&A examples from knowledge JSON."""
    client = anthropic.Anthropic()
    prompt_template = _load_prompt("DIALOG_PROMPT")
    prompt = prompt_template.replace(
        "{knowledge_json}",
        json.dumps(knowledge, ensure_ascii=False, indent=2),
    )
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------

def print_result(url: str, knowledge: dict, dialogs: str) -> None:
    sep = "=" * 40
    print(f"\n{sep}")
    print(f" 物料名：{knowledge.get('物料名', '未知')}")
    print(f" 地址：{url}")
    print(sep)
    print("\n期望学到知识：")
    print(json.dumps(knowledge, ensure_ascii=False, indent=2))
    print("\n备注（Agent 对话示例）：")
    for line in dialogs.split("\n"):
        if line.strip():
            print(f"  {line}")
    print(sep)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(url: str) -> None:
    print(f"[1/4] 正在抓取页面截图: {url}")
    try:
        screenshots = capture_screenshots(url)
    except Exception as e:
        print(f"[错误] Playwright 截图失败: {e}")
        print("[1/4] 切换至 Midscene 全流程...")
        screenshots = midscene_fallback(url, list(FALLBACK_TRIGGERS))
        if not screenshots:
            print("[错误] Midscene 也无法获取页面内容，请检查 URL 是否有效。")
            sys.exit(1)

    print("[2/4] 正在调用 Claude API 提取商品知识...")
    knowledge = extract_knowledge(screenshots)

    missing = get_missing_fields(knowledge)
    if missing:
        print(f"[3/4] 字段缺失 {missing}，启动 Midscene 兜底...")
        fallback_shots = midscene_fallback(url, missing)
        if fallback_shots:
            supplement = extract_knowledge(fallback_shots)
            for field in missing:
                if supplement.get(field):
                    knowledge[field] = supplement[field]
    else:
        print("[3/4] 所有字段完整，跳过 Midscene 兜底")

    print("[4/4] 正在生成 Agent 对话示例...")
    dialogs = generate_dialogs(knowledge)

    print_result(url, knowledge, dialogs)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 extractor.py <product_url>")
        sys.exit(1)
    run(sys.argv[1])
