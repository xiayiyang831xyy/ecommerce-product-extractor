# Ecommerce Product Extractor

一个 Claude Code Skill，输入任意电商商品链接，自动提取结构化商品知识，并生成 Agent 对话示例。

## 效果示例

```
========================================
 物料名：Apple iPhone 15 Pro
 地址：https://www.apple.com/shop/buy-iphone/iphone-15-pro
========================================

期望学到知识：
{
  "物料名": "Apple iPhone 15 Pro",
  "品牌介绍": "Apple，全球领先的消费电子品牌...",
  "核心卖点": ["A17 Pro 芯片", "钛金属边框", "4800万像素主摄"],
  "价格与促销": { "原价": 7999, "活动价": null, "优惠规则": null },
  ...
}

备注（Agent 对话示例）：
  Q: 这款手机有什么亮点？
  A: iPhone 15 Pro 最大的亮点是搭载了 A17 Pro 芯片...
```

## 提取维度

| 维度 | 说明 |
|------|------|
| 物料名 | 商品名称 |
| 品牌介绍 | 品牌背景、信任背书 |
| 产品介绍 | 核心功能、产品定位 |
| 产品分类 | 所属品类、系列 |
| 核心卖点 | 3-5 个差异化优势 |
| 价格与促销 | 原价、活动价、优惠规则 |
| 目标用户 | 适合哪类人群 |
| 使用场景 | 什么情况下使用 |
| 售后保障 | 退换货、质保政策 |

## 安装

### 1. 安装依赖

```bash
pip install anthropic playwright
python3 -m playwright install chromium
npm install -g @midscene/cli
```

### 2. 设置 API Key

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

> 获取 API Key：https://console.anthropic.com

### 3. 安装 Skill

将本仓库克隆到 Claude Code 的 skills 目录：

```bash
git clone https://github.com/<用户名>/ecommerce-product-extractor \
  ~/.claude/skills/ecommerce-product-extractor
```

## 使用方法

### 在 Claude Code 中使用（推荐）

在对话中发送商品链接即可触发，例如：

```
帮我提取这个商品的信息：https://www.example.com/product/xxx
```

触发关键词：`提取商品信息`、`分析这个商品页面`、`给我这个产品的结构化知识`

### 直接运行脚本

```bash
python3 ~/.claude/skills/ecommerce-product-extractor/extractor.py <URL>
```

## 工作原理

1. 用 Playwright 截取商品页面三个位置的截图
2. 调用 Claude Vision API 从截图中提取结构化信息
3. 若关键字段缺失，自动用 Midscene CLI 与页面交互（展开 FAQ、滚动到底部等）后重新提取
4. 调用 Claude API 生成 Agent 对话示例

## License

MIT
