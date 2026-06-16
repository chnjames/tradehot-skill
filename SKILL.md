---
name: tradehot
description: 外贸 HOT｜中文外贸/跨境电商资讯、全球贸易数据、平台动态、HS Code 机会、国家市场简报与风险雷达 Skill。当用户询问外贸、跨境电商、出口、进口、海关、关税、HS Code、国际物流、平台政策、海外市场、选品、买家开发、外贸日报、跨境电商日报、贸易风险等内容时使用。
version: 1.0.0
author: chnjames
platforms:
  - windows
  - macos
  - linux
metadata:
  short-description: 中文外贸与跨境电商情报简报 Skill
  tags:
    - foreign-trade
    - cross-border-ecommerce
    - hs-code
    - market-intelligence
    - risk-radar
  category: business
  compatibility:
    codex: true
    hermes: true
  hermes:
    command: tradehot
    category: business
    requires_toolsets:
      - terminal
    optional_toolsets:
      - web
---

# tradehot — 外贸 HOT Skill

## 目标

`tradehot` 用于把外贸与跨境电商领域的分散信息，整理成适合外贸业务员、跨境卖家、工厂老板、选品运营和市场开发人员使用的**中文可执行业务简报**。

本 Skill 兼容 Codex Skill 与 Hermes Agent Skill 的目录习惯：主入口为 `SKILL.md`，辅助资源位于 `scripts/`、`sources/`、`templates/` 和 `examples/`。在 Hermes Agent 中安装后，通常可通过 `/tradehot` slash command 触发；在 Codex 中则可通过自然语言意图触发。

每次输出都必须回答：

1. 这件事是什么。
2. 影响谁。
3. 对哪些市场、平台、品类或 HS Code 有影响。
4. 有什么机会。
5. 有什么风险。
6. 今天可以做什么。

## 何时触发

当用户表达以下任意意图时触发：

- 查询外贸、出口、进口、跨境电商、国际贸易资讯。
- 查询今日/最近一周外贸日报、跨境电商日报、外贸热点。
- 查询 Amazon、TikTok Shop、Shopee、Lazada、Temu、SHEIN、AliExpress、eBay、Walmart Marketplace、Etsy、Shopify 等平台动态。
- 查询某个国家或地区的外贸市场机会。
- 查询某个 HS Code 或品类的出口机会。
- 查询关税、海关、认证、出口退税、贸易壁垒、合规风险。
- 查询国际物流、运价、港口、供应链、汇率、收款风险。
- 查询选品、买家开发、市场调研、竞品分析、外贸客户开发。

典型触发语：

```text
今天外贸 HOT
给我今天的外贸日报
最近一周跨境电商热点
最近 Amazon 有什么政策变化
最近 TikTok Shop 有什么新规
美国市场最近有什么机会
查一下 HS Code 9403 的出口机会
帮我找宠物用品出口机会
最近外贸风险有哪些
给我做一份德国市场开发简报
```

## Agent 工作流（重要）

本 Skill 采用 **"脚本框架 + 联网填充"** 双引擎模式。Agent 应按以下流程执行：

### Step 1：生成报告骨架

运行脚本生成结构化框架：

```bash
python scripts/generate_report.py --type daily --days 1
python scripts/generate_report.py --type weekly --days 7
python scripts/generate_report.py --type platform --platform amazon
python scripts/generate_report.py --type market --market "United States"
python scripts/generate_report.py --type hs --hs-code 9403
python scripts/generate_report.py --type risk --days 7
python scripts/generate_report.py --type opportunity --days 7
```

脚本会输出：报告结构、各板块搜索关键词提示、评分排序逻辑。

也可直接生成搜索关键词列表，用于指导联网搜索：

```bash
python scripts/generate_report.py --search-queries --type daily
python scripts/generate_report.py --search-queries --type hs --hs-code 9403
```

### Step 2：联网搜索填充真实数据

针对脚本骨架中的每个板块，使用当前 Agent 环境可用的联网检索能力获取最新内容，例如 Codex 的 web 搜索/浏览能力，或 Hermes Agent 中启用的 web/search toolset。优先从 `sources/*.json` 配置的信息源核实：

| 板块 | 搜索方向 | 优先源 |
|---|---|---|
| 政策与监管 | 海关总署、商务部、税务总局最新公告 | sources.zh.json 中 priority=5 的源 |
| 平台动态 | 各平台 Seller Center 公告、行业媒体报道 | platforms.json 中对应平台 |
| 数据与市场 | UN Comtrade、ITC Trade Map、WTO 统计 | sources.en.json 中 official_data 类型 |
| 物流与供应链 | FreightWaves、The Loadstar、运价指数 | sources.en.json 中 logistics_media 类型 |
| 关税与合规 | ITC Market Access Map、目标国官方税则 | sources.en.json 中 official_data_tool 类型 |
| 选品机会 | Google Trends、平台热搜、行业报告 | 综合多源交叉验证 |
| 风险预警 | 制裁清单、贸易救济、汇率波动 | 官方源优先 |

### Step 3：分析与判断

用真实数据替换脚本占位内容，按以下要求补充每条情报的元数据：

- **类型**：政策 / 平台 / 数据 / 物流 / 关税 / 合规 / 选品 / 风险 / 宏观
- **影响对象**：工厂、贸易公司、跨境卖家、独立站、平台卖家、海外仓、物流商
- **影响市场**：国家或地区
- **影响品类**：行业词、产品词或 HS Code
- **热度分**：0-25（见评分规则）
- **风险等级**：低 / 中 / 高
- **行动建议**：今天或本周可执行的动作

### Step 4：输出最终报告

按 `templates/*.md` 中对应模板的结构输出最终报告。输出要求：

- 用中文，英文信息源需翻译并归纳。
- 不要只罗列新闻标题，必须转化为业务判断。
- 每条重要情报按以下句式展开：这件事是什么 → 影响谁 → 影响哪些品类/市场/平台 → 风险 → 机会 → 今天可以做什么。

## 核心能力（7 种报告类型）

| # | 能力 | 触发场景 | 脚本参数 | 模板文件 |
|---|---|---|---|---|
| 1 | 今日外贸 HOT 日报 | "今天外贸圈发生了什么" | `--type daily` | templates/daily_report.md |
| 2 | 本周外贸周报 | "最近一周外贸热点" | `--type weekly --days 7` | templates/daily_report.md |
| 3 | 平台动态查询 | "Amazon 有什么新政策" | `--type platform --platform <name>` | templates/platform_report.md |
| 4 | 国家/市场简报 | "德国市场有什么机会" | `--type market --market <name>` | templates/market_report.md |
| 5 | HS Code / 品类机会 | "查一下 HS Code 9403" | `--type hs --hs-code <code>` | templates/hs_code_report.md |
| 6 | 风险雷达 | "最近外贸风险有哪些" | `--type risk --days 7` | templates/risk_report.md |
| 7 | 选品机会雷达 | "有什么适合开发的产品" | `--type opportunity --days 7` | templates/product_opportunity.md |

## 热度评分规则

```text
热度分 = 时效性 + 权威性 + 业务影响 + 可操作性 + 风险程度
```

每项 0-5 分，总分 0-25 分。

| 维度 | 0 分 | 1-2 分 | 3-4 分 | 5 分 |
|---|---|---|---|---|
| 时效性 | 无时间信息 | 30 天前 | 3-7 天内 | 今天或昨天 |
| 权威性 | 社媒传言 | 普通媒体 | 行业媒体 | 官方/平台官方公告 |
| 业务影响 | 无直接影响 | 间接影响 | 影响成本/效率 | 影响订单/合规/账号 |
| 可操作性 | 仅了解 | 中长期参考 | 可纳入计划 | 今天可执行 |
| 风险程度 | 无风险 | 低风险 | 可能延误/损失 | 罚款/封号/扣货 |

排序原则：官方政策 > 平台规则 > 关税变化 > 物流/支付风险 > 市场数据 > 普通新闻。

## 信息源优先级

1. **官方政策**（priority 5）：海关总署、商务部、税务总局、贸促会、WTO、UN Comtrade、ITC、trade.gov。
2. **平台官方公告**（priority 5）：Amazon、TikTok Shop、Shopee、Lazada、Temu、SHEIN、AliExpress、eBay、Walmart、Etsy、Shopify。
3. **行业媒体**（priority 4）：亿邦动力、雨果跨境、Reuters、FreightWaves、The Loadstar。
4. **第三方数据**（priority 3）：Google Trends、Similarweb、Marketplace Pulse、物流运价指数。
5. **社媒与论坛**（priority 1-2）：仅作线索，不作为事实依据，必须明确标注来源不确定。

完整信息源配置见 `sources/*.json` 和 `platforms.json`。

## 支持平台

Amazon、TikTok Shop、Shopee、Lazada、Temu、SHEIN、AliExpress、eBay、Walmart Marketplace、Etsy、Shopify（共 11 个，详见 `sources/platforms.json`）。

## Hermes Agent 使用说明

- 推荐安装到 `~/.hermes/skills/business/tradehot`，或使用 Hermes 支持的 GitHub Skill 安装方式。
- 运行时至少启用 terminal/tool execution 能力，以便调用 `scripts/*.py`。
- 如需生成包含最新资讯的日报、周报、平台动态或风险雷达，应同时启用 web/search 能力。
- 若 Hermes 运行环境的当前工作目录不是 Skill 根目录，应先切换到本 Skill 目录，或使用脚本的绝对路径调用。
- 本 Skill 不依赖第三方 Python 包，Python 标准库即可运行测试与离线示例。

## 重要限制

- 不要把未经验证的社媒传言当作事实。
- 涉及关税、认证、制裁、出口管制、税务时，必须提示用户以官方文件或专业顾问为准。
- 对于实时新闻、平台政策、关税、法规、运价、汇率等易变化信息，必须使用最新来源核实。
- 不应承诺一定能覆盖全网信息。
- 若信息源不足，应明确说明"未找到足够权威来源"。
- 脚本输出的骨架仅作为报告结构参考，所有实质内容必须由联网搜索或用户提供数据填充。
