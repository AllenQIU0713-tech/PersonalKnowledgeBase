# S2 对历史 159 项断言的接口迁移建议

日期：2026-10-03。来源基线：`docs/testing/V1.1R2-6774844/regression-results.json` 的 159 项当前有效断言。本文只给独立测试确认迁移口径，不修改测试文件、不宣称新版本已通过。

## 迁移原则

- 数据安全、隐私资格、备份恢复、云端逐次确认和 provider 失败关闭属于长期产品契约，继续保留。
- 旧断言若检查“余弦阈值等于可回答性”“召回即证据”或正常业务中的旧 memory 接口，应改成 S2 等价接口，不能为了维持原名字保留错误语义。
- 已退役的旧 memory 正常业务入口只保留迁移/恢复兼容断言；不能要求 `Answers.context()` 再返回独立 memories。
- 旧计数不作为目标。测试应逐条标为 `retain`、`equivalent_update`、`scope_retired`，再加入 S2 新增断言。

## 按原结果文件的建议

| 原分组 | 数量 | 建议 |
| --- | ---: | --- |
| DeepSeek provider 边界 | 26 | 全部 `retain`。请求前授权、禁代理/重定向、超时/错误无重试、响应大小和结构限制与 S2 正交 |
| 备份边界 | 5 | 全部 `retain`。另新增 reviewer/pipeline 元数据恢复后失效，模型和复核正文不入备份 |
| 服务迁移 | 6 | 全部 `retain`。迁移 API 和源资料保留不因 S2 改变 |
| 向量与索引 | 11 | 7 项保留，4 项等价更新，见下表 |
| 云端确认 | 40 | 29 项直接保留、6 项扩展、4 项等价更新、1 项范围退役，见下表 |
| 资料/旧 memory/备份 | 35 | 日期、删除、锁、校验和隐私级联保留；旧 memory 正常资格断言改为迁移资料资格；旧格式恢复兼容继续保留 |
| 重解析 | 13 | 文件重解析、WAL 和无关回答保留；派生 memory 断言改为迁移资料/来源资格失效；旧 orphan/partial memory 仅作为兼容迁移保留 |
| 最终迁移 | 23 | 历史清理、资料/原件/片段/向量保留、幂等和旧备份处理继续保留；“personal memory”只证明旧表无损兼容与迁移，不恢复正常检索入口 |

## 需要改名或改接口的旧断言

### 向量与索引 11 项

以下继续原接口或只更新构造器参数：

- `normalization and query instruction`
- `proxy bypass`
- `reject zero`
- `reject nan`
- `reject redirect`
- `background index`
- `delete vectors cascades`

以下改为 S2 等价断言：

| 旧断言 | S2 等价断言 |
| --- | --- |
| `semantic fixture route` | 资格过滤后最多 40 条稳定候选进入选定 reviewer；只有复核通过项进入最终证据 |
| `semantic tag and date filtering` | 标签/日期过滤仍在 reviewer 前生效，被过滤正文不会进入 reviewer |
| `signature excludes old vectors` | embedding 签名排除旧向量，同时 reviewer/pipeline 签名变化使旧复核结果与确认失效 |
| `invalid service keyword fallback` | embedding 或 reviewer 缺失/超时/不兼容均失败关闭；精确查找独立可用，自然语言不回退关键词 |

旧“余弦 threshold 已设置即 ready”不是应保留的契约，应由“embedding 索引完整且最终 reviewer 已选择、校准和摘要匹配”取代。

### 云端确认 40 项

29 项核心语义直接保留：准备阶段零外发、未选中片段排除、本地资料完全排除、空历史、政策链接、取消、一次性 token、单次发送、不可重用、元数据最小化、目的地变化、过期、重启失效、失败无重试、失败 token 消耗、并发最多一次、密钥不入备份、恢复后隐私清理、删除清理、真实 DeepSeek 零调用等。

需要等价更新或扩展：

| 旧断言 | 处理 | S2 要求 |
| --- | --- | --- |
| `eligible memory included` | `scope_retired` + replacement | 正常上下文不再返回独立 memory；改验“符合资格的迁移资料可经召回和 reviewer 成为证据” |
| `source content change invalidates` | 扩展 | 同时验证完整 evidence hash、review result hash 失效 |
| `privacy tightening invalidates` | 扩展 | 收紧发生在召回后、复核中、预览后、确认前四个时点都不能外发 |
| `memory change invalidates` | `equivalent_update` | 改为迁移资料内容/来源/资格版本变化使 snapshot、复核结果与确认失效 |
| `model mutation invalidates digest` | `equivalent_update` | 改为 reviewer 模型摘要、量化、模板、配置、阈值或 pipeline 版本任一变化使确认失效 |
| `preview exposes exact request JSON and metadata` | 扩展 | 确认页只含复核通过且用户选择的片段；被拒 `related_sources` 不出现 |
| `selected source included` | 扩展 | 只有本次 snapshot 中 reviewer 通过的 ID 可选 |

原清单中与上述失效断言成对的 `... sends nothing` 断言采用相同分类：资料内容和隐私变化两项为扩展，迁移资料变化和 reviewer/pipeline 变化两项为等价更新。这样 40 项合计为 29 直接保留、6 扩展、4 等价更新、1 范围退役。

### 资料、旧 memory 与迁移断言

这些名称需按实际 S1 单一资料库接口改写，测试确认时保留原断言 ID 作为追踪字段：

- `confirmed eligible` → `confirmed migrated document eligible`。
- `history and sources retained` → `migration provenance and source lifecycle retained`。
- `source privacy cascades` 保留，目标改为迁移资料 `question_state`、向量、复核/确认失效。
- `source deletion removes memory and history` → `source deletion restricts migrated document and removes derived legacy compatibility rows`。
- `memory tombstone` → `legacy memory tombstone survives restore and cannot recreate a question-eligible document`。
- `backup memory roundtrip` / `new backup restores memory` / `legacy backup preserves memory`：作为旧格式兼容保留，不把旧表重新接入检索。
- `privacy derived memory no longer eligible` / `delete derived memory no longer eligible`：改验迁移资料及其向量、snapshot、确认失效。
- `personal memory and history preserved`：只验证无损迁移审计与兼容数据保留。

## S2 必须新增的断言族

这些不应挤占旧 159 项名称：

1. 第一阶段最多 40 条、无余弦可回答性门槛、同分稳定顺序及统一候选快照。
2. 完整业务编号 NFKC/casefold、边界、全角、大小写、多编号全匹配，纯数字/日期不误识别。
3. reviewer 真实协议：0.6B logits/冻结阈值，或 4B 严格 JSON/逐字引文；无后台修复与候选回退。
4. 正例、难负例、无证据、否定答案、不同对象、提示注入和组合问题探索。
5. 复核后最终 6 条、每文档 2 条、6000 字预算；被拒相关资料只在本地分区显示。
6. 内容/来源/隐私/资格/模型/模板/阈值/配置/管线变化，以及晚到旧结果全部失效。
7. 确认 payload 无被拒片段，`cloud_requests=0`，真实发送继续逐次确认。
8. 选定候选的冷启动、40 候选峰值、热态 p50/p95、内存压力、压缩内存和 swap。

## 请测试任务确认的三个问题

1. 是否同意把 `eligible memory included` 标为范围退役，并以“迁移资料经过 reviewer 成为证据”替代？
2. 是否同意旧 159 项保留原始断言 ID/来源文件作为追踪字段，但允许显示名称与调用接口更新？
3. 是否同意把新增 S2 断言单列，最终报告同时给出旧断言迁移矩阵和 S2 新增结果，不再以机械保持 159 为目标？
