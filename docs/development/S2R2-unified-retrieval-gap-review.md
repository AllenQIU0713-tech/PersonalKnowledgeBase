# 统一资料索引中的旧记忆语义检索差距

日期：2026-10-12。范围：只读对照提交 `f2f4c04` 与产品澄清 `docs/superpowers/specs/2026-10-11-unified-source-semantic-retrieval-clarification.md`。未修改代码、未运行测试、未读取正式资料库。

## 结论

**普通收集资料和合格旧迁移记忆目前共用同一向量索引及资格过滤，代码中没有按 `source_type` 把 `legacy_memory` 排除。** 迁移旧记忆被写成 `documents` + `chunks`，嵌入索引和语义搜索统一扫描这些 chunk；资格逻辑通过同一 `Store.question_eligible` 检查隐私、解析状态、问答状态和来源依赖。

问答召回存在一项产品可见差距：语义检索结果没有带出 `source_type`，所以回答预览和来源按钮无法区分“旧个人记忆迁移”与普通收集资料。旧记忆原表不会直接进入语义检索，因此同一 `memory_id` 不会从旧表与迁移资料双重召回。产品已确认不同 document 的正文即使相同，也应保留各自来源，不做全库正文去重；当前按 document 限制片段的行为符合该决定。

另有一个独立缺失能力：当前资料列表只有精确查找，没有本地语义查找；现有向量索引也只包含问答合格的资料，无法支持在本机浏览 `privacy=local`、待核对或停用资料。

自然语言问答仍受 S2/S2R1 复核失败影响，正式状态继续 `calibration_required`。本报告只说明召回路径实现，不将其描述为可靠答案能力已通过。

## 代码证据

| 契约环节 | 实现位置 | 只读发现 |
| --- | --- | --- |
| 迁移写入统一资料表 | `pkb/migration.py:78-125` | `_migrate_one` 以旧记忆 ID 生成稳定资料 ID，写 `documents` 与 `document_metadata.source_type='legacy_memory'`，将原正文写为一个 `chunks`，保存快照和映射。旧表 `memories` 不被搜索代码直接读取。 |
| 合格状态计算 | `pkb/migration.py:43-75` | 旧记忆只有 confirmed、无冲突、来源完整时才可成为 `ready`；隐私限制会从来源继承。未确认、inactive、冲突或来源缺失时会被限制。 |
| 问答资格统一过滤 | `pkb/store.py:181-214` | `question_eligible` 不根据 `source_type` 分支；统一检查 document privacy/status/question_state，并递归检查来源依赖。 |
| 向量索引候选 | `pkb/embedding.py:128-137` | `_eligible_chunks` 联接 `chunks/documents/document_metadata`，逐行调用 `question_eligible`。SQL 不按来源类型过滤，因此符合资格的 collected 与 legacy memory 都进入嵌入队列。 |
| 资格变化清理向量 | `pkb/embedding.py:92-107, 140-168` | 向量签名变化会重建索引；资格变化或来源失效时，索引 worker 不会保存不再合格的 chunk，下一轮 `_next_pending` 会删除失去资格的旧向量。 |
| 向量检索和余弦排序 | `pkb/embedding.py:291-395` | `retrieve` 对同一查询向量逐个比较已索引 chunk，计算归一化向量点积（即余弦相似度），并与精确特征做 0.8/0.2 RRF 排序。来源类型未参与得分，符合“不因旧记忆加权”。 |
| 每资料片段上限 | `pkb/embedding.py:385-398` | `MAX_PER_DOCUMENT=2` 防止同一资料片段挤满结果；不同 document 间相同正文没有去重。 |
| 结果来源标识 | `pkb/embedding.py:389-402`、`pkb/answers.py:160-176`、`pkb/static/app.js:29,23` | 检索结果没有选择 `source_type/legacy_id`；`Answers.context` 只传资料 ID、chunk、标题、页码、文本和版本；本地预览/确认与 `showSources` 只展示标题/页码。详情页本身可以显示 legacy 来源和历史，但用户不能从本次候选/回答来源列表直接辨认它。 |
| 本地语义查找入口 | `pkb/server.py:117-121`、`pkb/static/app.js:17`、`pkb/embedding.py:294-295` | `/api/documents` 只调用 `Store.search`，响应 `mode='exact'`；界面明确写“精确查找 · 不理解自然语言问法”。语义入口 `search_with_mode` 只委托给 `retrieve`，没有单独的本地浏览路由，也没有 local-only 结果。 |
| 当前向量索引资格范围 | `pkb/embedding.py:128-137, 140-168, 291-335` | 索引建立、清理与检索都使用 `question_eligible`。因此 `privacy=local`、待核对、停用、blocked source 等资料不入向量索引；这正确保护问答，但不足以满足本地浏览型语义查找。 |
| 搜索故障处理 | `pkb/server.py:91-95,117-121`、`pkb/static/app.js:17` | 当前语义搜索没有请求路径，因此没有明确的语义未就绪结果；现有 `/api/documents` 只返回精确查找。未来新增语义模式时必须单独返回 paused/unavailable 状态，精确查找继续走现有 API，不把其结果标为语义匹配。 |
| 浏览结果与问答隔离 | `pkb/answers.py:160-176,220-335` | 现有 `Answers.context` 自行调用 `embeddings.retrieve`，并在 prepare/confirm 重新检查后端资格；客户端传入的 selected chunk 只能从服务端当前 context 的候选集合中选择。Q6/新浏览入口不得把 browse DTO 的正文或 ID 直接作为问答上下文，QA prepare 必须重新构造合格 context。 |

## 与验收条件的对应

- 普通资料和合格旧记忆共同参加语义召回：**代码路径满足，需由测试任务用混合来源语料证明同义表达确实召回。**
- 资格、隐私与来源依赖在召回前过滤：**代码路径存在且通用；旧记忆没有更宽松分支。**
- 语义分数、排名和来源类型出现在可审查证据中：**当前 UI/Answer 结果缺 source type，测试诊断也需直接读取内部排序指标。**
- 相同旧记忆不由旧表和迁移资料重复召回：**代码路径满足，旧 `memories` 表不被 embedding/retrieve 查询，因此同一旧 memory_id 只有迁移 chunk 参加搜索。**
- 相同正文跨不同资料去重：**无需实现。产品已确认不同资料即使正文相同也保留各自来源；不得按正文哈希合并。**
- 答案与预览标注来源类型：**尚未实现；需从 `document_metadata` 带出 `source_type` 和必要的旧标识，再传到预览、确认与来源展示。**
- 本地语义查找：**尚未实现。当前索引只存问答合格向量，需扩为同一物理索引中的“已解析、未删除本地浏览视图”，同时保留问答的严格资格视图。local/pending/inactive 结果仅本机展示并标状态；source_missing/deleted 排除；删除沿用级联清理。**
- 语义查找失败关闭：**需新增显式语义模式状态和独立结果；索引/embedding 不可用时显示暂停原因，精确查找入口保持可用且不被冒充为语义结果。**
- 可靠回答和最终问题答案：**不满足启用条件；S2/S2R1 模型失败，需保持 `calibration_required`。**

## 建议的最小修复范围

开发范围应拆为两个独立交付：

1. **来源标记贯穿问答。** 从检索结果读取 `source_type`，经 `Answers.context` 传到预览、确认和引用按钮。普通资料显示“收集资料”，迁移资料显示“迁移自个人记忆”；原始旧 ID 仅详情页用户主动查看时出现。该元数据不改变资格、排序或权重。
2. **本地语义查找。** 在现有单一向量存储中维护所有“正文已解析且未删除”的本地浏览向量，并提供独立语义查找路由。结果允许 `privacy=local`、待核对和停用资料，但醒目标注只供本地查阅；source_missing、tombstone 或已删除来源不返回。浏览 DTO 与 Q&A context 必须为不同的数据结构；问答流程不得接收浏览返回的正文/ID，必须重新按问题召回并执行 `question_eligible` 后构造云端候选。新增路径不能绕过现有 prepare/confirm 重新检查。语义索引需记录足以报告相似度/排名的结果字段；语义服务未就绪时返回明确状态，不触发关键词回退。保留现有精确查找 API 和界面入口。

两者都不得新增记忆表、记忆录入页、第二个向量索引或来源加权。测试任务之后独立验证普通/旧记忆同义召回、local/pending/inactive 仅本地可见、来源失效/删除清理、预览/引用来源标签贯穿、伪造 browse chunk ID 不可进入 prepare、隐私收紧/停用/来源撤销/删除使旧确认失效，以及语义不可用时精确查找仍独立工作；问答正式状态继续失败关闭。

## 未执行

- 没有连接或读取 `knowledge.sqlite3` 等正式资料。
- 没有启动 embedding/reviewer 服务或发起 DeepSeek 请求。
- 没有运行测试，也没有修改任何应用代码。
