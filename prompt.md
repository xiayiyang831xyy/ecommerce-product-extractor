# EXTRACTION_PROMPT

你是一个电商商品信息提取专家。根据提供的商品页面截图，提取以下11个维度，
输出严格符合以下 JSON schema 的结果。若某字段页面无法找到，值设为 null。

```json
{
  "物料名": "string",
  "品牌介绍": "string",
  "产品介绍": "string",
  "产品分类": "string",
  "核心卖点": ["string"],
  "价格与促销": {
    "原价": "number | null",
    "活动价": "number | null",
    "优惠规则": "string | null"
  },
  "目标用户": ["string"],
  "使用场景": ["string"],
  "销售话术": "string",
  "常见问题": [{"问": "string", "答": "string"}],
  "售后保障": "string | null"
}
```

仅返回 JSON，不要额外说明。

---

# DIALOG_PROMPT

根据以下商品知识 JSON，生成 2-3 条 Agent 对话示例。
每条示例格式：Q: <用户提问>\nA: <Agent 回答>
回答要自然、口语化，直接基于 JSON 中的数据。
仅返回对话示例，不要额外说明。

商品知识：
{knowledge_json}
