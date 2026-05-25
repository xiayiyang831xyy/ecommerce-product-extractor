---
name: ecommerce-product-extractor
description: Use when the user provides an e-commerce product page URL and wants to extract structured product knowledge (name, brand, features, price, target audience, use cases, sales scripts, FAQ, warranty) as JSON with Agent dialog examples. Triggers on phrases like "提取商品信息", "分析这个商品页面", "给我这个产品的结构化知识" or any e-commerce URL followed by an extraction request.
---

# Ecommerce Product Extractor

## Overview

Extracts 11 structured knowledge dimensions from any e-commerce product page URL using Claude API Vision, with Midscene fallback for dynamic/complex pages. Prints formatted JSON + Agent Q&A examples to terminal.

## Usage

When the user provides a product page URL and asks for extraction:

1. Run the extractor script via Bash tool
2. **Always paste the full output in your text response** (Bash output is not visible to the user)
3. Add a 1-2 sentence summary: what is this company/product? Keep it concise, no field breakdowns.

```bash
python3 ~/.claude/skills/ecommerce-product-extractor/extractor.py <URL>
```

## What It Extracts

| 维度 | 说明 |
|------|------|
| 物料名 | 商品名称 |
| 品牌介绍 | 品牌背景、信任背书 |
| 产品介绍 | 核心功能、产品定位 |
| 产品分类 | 所属品类、系列 |
| 核心卖点 | 3-5个差异化优势 |
| 价格与促销 | 原价、活动价、优惠规则 |
| 目标用户 | 适合哪类人群 |
| 使用场景 | 什么情况下使用 |
| 售后保障 | 退换货、质保政策 |

## Requirements

- `ANTHROPIC_API_KEY` environment variable must be set
- `playwright` Python package installed (`pip install playwright`)
- Playwright browsers installed (`python3 -m playwright install chromium`)
- `@midscene/cli` npm package installed globally (`npm install -g @midscene/cli`)

## Fallback Behavior

If key fields (常见问题, 售后保障, 价格与促销) are missing after initial extraction, Midscene CLI automatically interacts with the page (expand FAQ, scroll to bottom, dismiss popups) and re-extracts.
