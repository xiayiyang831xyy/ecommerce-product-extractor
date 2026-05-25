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

def capture_screenshots(url: str) -> list[str]:
    """Return list of base64-encoded PNG screenshots at 3 scroll positions."""
    screenshots = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        total_height = page.evaluate("document.body.scrollHeight")
        positions = [0, total_height // 2, max(0, total_height - 900)]

        for pos in positions:
            page.evaluate(f"window.scrollTo(0, {pos})")
            time.sleep(0.5)
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
    return json.loads(raw.strip())


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
    """Build a Midscene YAML script in the new format (web + tasks)."""
    flow_steps = []
    if "价格与促销" in missing:
        flow_steps.append("      - ai: dismiss any popup or login dialog that may be covering the price")
        flow_steps.append("      - ai: scroll to the price section")
    if "常见问题" in missing:
        flow_steps.append("      - ai: find and expand the FAQ or 常见问题 section by clicking on it")
        flow_steps.append("      - ai: scroll down to reveal all FAQ items")
    if "售后保障" in missing:
        flow_steps.append("      - aiScroll: {direction: down, distance: 3000}")
        flow_steps.append("      - ai: scroll to the warranty and return policy section")
    flow_steps.append("      - sleep: 2000")

    steps_str = "\n".join(flow_steps)
    return f"""web:
  url: "{url}"
  viewportWidth: 1280
  viewportHeight: 900

tasks:
  - name: expand-missing-sections
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
# Terminal output
# ---------------------------------------------------------------------------

def print_result(url: str, knowledge: dict) -> None:
    sep = "=" * 40
    print(f"\n{sep}")
    print(f" 物料名：{knowledge.get('物料名', '未知')}")
    print(f" 地址：{url}")
    print(sep)
    print("\n期望学到知识：")
    print(json.dumps(knowledge, ensure_ascii=False, indent=2))
    print(sep)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(url: str) -> None:
    print(f"[1/3] 正在抓取页面截图: {url}")
    try:
        screenshots = capture_screenshots(url)
    except Exception as e:
        print(f"[错误] Playwright 截图失败: {e}")
        print("[1/3] 切换至 Midscene 全流程...")
        screenshots = midscene_fallback(url, list(FALLBACK_TRIGGERS))
        if not screenshots:
            print("[错误] Midscene 也无法获取页面内容，请检查 URL 是否有效。")
            sys.exit(1)

    print("[2/3] 正在调用 Claude API 提取商品知识...")
    knowledge = extract_knowledge(screenshots)

    missing = get_missing_fields(knowledge)
    if missing:
        print(f"[3/3] 字段缺失 {missing}，启动 Midscene 兜底...")
        fallback_shots = midscene_fallback(url, missing)
        if fallback_shots:
            supplement = extract_knowledge(fallback_shots)
            for field in missing:
                if supplement.get(field):
                    knowledge[field] = supplement[field]
    else:
        print("[3/3] 所有字段完整，跳过 Midscene 兜底")

    print_result(url, knowledge)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 extractor.py <product_url>")
        sys.exit(1)
    run(sys.argv[1])
