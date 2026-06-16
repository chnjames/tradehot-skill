# tradehot - 外贸 HOT Skill

`tradehot` 是一个面向外贸、跨境电商、出口企业和市场开发人员的中文情报 Skill。

它把分散的外贸信息源整理成可执行的业务简报，覆盖：

- 今日外贸 HOT 日报 / 本周周报
- 平台动态查询
- 国家 / 市场外贸简报
- HS Code / 品类机会分析
- 外贸风险雷达
- 选品机会雷达

当前版本已经形成完整闭环：

```text
RSS / 外部 JSON / 搜索结果
-> 标准化 item schema
-> 实体识别
-> 校验
-> 去重聚类
-> 热度评分
-> 用户偏好排序
-> 动态报告分组
-> Markdown 报告输出
```

## 目录结构

```text
tradehot-skill/
├── SKILL.md
├── README.md
├── sources/
│   ├── sources.zh.json
│   ├── sources.en.json
│   ├── platforms.json
│   ├── markets.json
│   ├── rss_sources.json
│   └── user_config.json
├── templates/
│   ├── daily_report.md
│   ├── platform_report.md
│   ├── market_report.md
│   ├── hs_code_report.md
│   ├── risk_report.md
│   └── product_opportunity.md
├── scripts/
│   ├── fetch_news.py
│   ├── source_connectors.py
│   ├── item_schema.py
│   ├── entity_extractor.py
│   ├── item_cluster.py
│   ├── report_sections.py
│   ├── rank_items.py
│   ├── generate_report.py
│   ├── run_pipeline.py
│   └── test_all.py
└── examples/
```

## 安装到 Codex

把整个目录复制到 Codex 用户技能目录：

```powershell
Copy-Item -Recurse -Force .\tradehot-skill C:\Users\<you>\.codex\skills\tradehot
```

重启或刷新 Codex 会话后，可用自然语言触发：

```text
今天外贸 HOT
最近 TikTok Shop 有什么新规？
查一下 HS Code 9403 的出口机会
最近外贸风险有哪些？
给我做一份德国市场开发简报
```

## 运行测试

无需第三方依赖，使用 Python 标准库即可。

```powershell
cd scripts
python test_all.py
```

期望结果：

```text
ALL TESTS PASSED
```

## 一键闭环 Pipeline

默认读取 `sources/rss_sources.json` 中启用的 RSS/Atom 源，生成 item JSON 和 Markdown 报告。

```powershell
cd scripts

python run_pipeline.py `
  --type daily `
  --config ..\sources\rss_sources.json `
  --items-output ..\examples\test_items.json `
  --report-output ..\examples\test_daily_report.md
```

支持报告类型：

```text
daily
weekly
platform
market
hs
risk
opportunity
```

示例：

```powershell
python run_pipeline.py --type platform --platform "TikTok Shop"
python run_pipeline.py --type market --market EU
python run_pipeline.py --type hs --hs-code 9403
python run_pipeline.py --type risk
python run_pipeline.py --type opportunity
```

## 单独采集 RSS

```powershell
python scripts\fetch_news.py `
  --mode rss-batch `
  --config sources\rss_sources.json `
  --output examples\rss_items.json
```

输出结构：

```json
{
  "items": [],
  "errors": [],
  "stats": {
    "sources": 0,
    "items": 0,
    "errors": 0
  }
}
```

## 外部 JSON / 搜索结果导入

支持两种格式：

```json
[
  {
    "title": "Example",
    "summary": "Example summary",
    "url": "https://example.com",
    "source": "news",
    "published_date": "2026-06-16"
  }
]
```

或：

```json
{
  "results": [
    {
      "name": "Search result title",
      "snippet": "Search result snippet",
      "link": "https://example.com"
    }
  ]
}
```

归一化：

```powershell
python scripts\fetch_news.py --mode normalize --input examples\external_items_sample.json
```

生成报告：

```powershell
python scripts\generate_report.py `
  --type daily `
  --input examples\external_items_sample.json `
  --output examples\external_daily_report.md
```

## 信息源配置

RSS/Atom 源配置位于：

```text
sources/rss_sources.json
```

示例：

```json
{
  "sources": [
    {
      "id": "tradehot_sample",
      "name": "Tradehot Sample Feed",
      "url": "../examples/rss_feed_sample.xml",
      "source_tier": "industry_media",
      "enabled": true
    }
  ]
}
```

部署时把 `url` 换成真实 RSS/Atom URL 即可。

## 用户偏好

编辑：

```text
sources/user_config.json
```

可配置：

- 关注市场
- 关注平台
- 关注品类
- 关注 HS Code
- 默认报告窗口
- 高风险提醒偏好

## 重要限制

- 本 Skill 不替代法律、税务、海关或贸易合规专业意见。
- 涉及关税、认证、制裁、出口管制、税务时，应以官方文件或专业顾问为准。
- 实时信息必须使用最新来源核实。
- RSS 和搜索结果只能作为输入来源，最终报告仍需保留来源、时间和置信度。

## 上传 GitHub 前建议

建议只提交源码、模板、配置和稳定示例。

不要提交：

- `__pycache__/`
- `_cache/`
- 临时 pipeline 输出
- 本地测试输出

`.gitignore` 已覆盖这些内容。
