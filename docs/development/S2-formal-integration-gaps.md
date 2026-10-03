# S2 正式检索、预览与确认集成缺口

日期：2026-10-03。基线：固定试验候选 `e1eff9c00680b7cb92b5bd0b4f8f5781d390c5d0`。本文件是可供后续获批路线复用的开发分析，不修改固定候选，不启用正式资料库。独立初筛已证明 S2 两个候选均不合格，因此本文件中的接线工作当前全部延期，不能用于主张存在可集成候选。

## 当前调用链

当前正式路径为：

`Answers.context()` → `Embeddings.retrieve()` → 最多 6 个片段 → `/api/answers/preview` → 用户勾选 → `Answers.prepare()` → 内存确认记录 → `Answers.confirm()`。

S2 试验路径 `pkb.evidence_review` 与 `pkb.review_measure` 独立存在，没有进入上述调用链。正式状态仍由 `semantic_index_config.threshold` 决定；阈值为空即 `calibration_required`。

## 阻断性缺口

| 位置 | 当前行为 | S2 所需行为 | 实施建议 |
| --- | --- | --- | --- |
| `Embeddings.status()` | `threshold is not None` 即语义就绪 | embedding、选定 reviewer、固定模型摘要、模板、配置及 reviewer 校准全部匹配才就绪 | 新建版本化 `evidence_review_config`；状态返回 `reviewer_state`、`reviewer_signature`、校准摘要，不再以余弦阈值代表可回答性 |
| `Embeddings.retrieve()` | 在第一阶段用余弦阈值过滤，随后只保留最多 6 条 | 资格先过滤，按原始余弦召回最多 40 条，不用未校准余弦门槛 | 拆为 `retrieve_candidates(question) -> RetrievalSnapshot`；保留稳定排序和精确增强，但不在复核前执行最终 6/每文档 2 限制 |
| 精确增强 | 编号特征使用查询编号与片段编号“有交集” | 明确业务编号全部完整匹配，否则候选硬拒绝 | 保留精确增强只作排序；把 `business_identifier_gate()` 放在 reviewer 前，要求查询编号集合是候选编号集合的子集 |
| `Answers.context()` | 重新 `store.get()`，截取正文后直接作为可用证据 | 每个候选先复核；只有通过者进入证据区，拒绝者只能进入本地相关资料区 | 新增 `EvidencePipeline.review(snapshot)`；使用同一行快照的完整片段，复核后才执行最多 6 条、每文档 2 条、6000 字预算 |
| 资料快照 | 召回、`store.get()`、资格复查分散进行 | 内容、来源、隐私、资格或版本变化须使进行中的结果失效 | `RetrievalSnapshot` 固定 chunk/document ID、完整正文哈希、内容/资格版本、索引 generation/revision；复核完成后在锁内批量重验 |
| reviewer 生命周期 | 只有隔离 CLI | 正式服务只能配置最终选定的一个 reviewer；缺失、超时、版本不符时失败关闭 | 为选定候选实现单并发 `EvidenceReviewer` 服务包装；server CLI 接受固定模型文件、摘要和本地进程/端口，启动时校验，不自动下载或切换候选 |
| 0.6B 接受规则 | 只输出 logits，`accepted=null` | 使用独立测试冻结的阈值和排序规则 | 阈值、报告哈希、量化、模板和 logits 语义进入 reviewer 签名；不得沿用 S1 余弦阈值字段 |
| 4B 接受规则 | 试验适配器结构性接受 | 正式路径还需保持逐字引文核验和固定非思考配置 | 复用现有严格解析；保存 verdict、引文偏移和输出摘要，不保存内部思考；不把模型自报置信度加入门槛 |
| 拒绝资料展示 | 预览只有 `sources` | 全部不通过时显示“找到相关资料，但现有内容不足”，并可展示本地相关资料 | 响应增加 `related_sources`，仅含本地展示所需字段；前端分区渲染，选择框只属于 `sources` |
| 云端准备 | `_select_sources()` 只看当前 `sources` | 被拒片段不能通过旧 ID 或重放进入确认 | 选择只接受本次 `reviewed_sources`；记录每条 evidence hash 和 reviewer result hash |
| 确认绑定 | 绑定 `signature/generation/revision/threshold` 与内容/资格版本 | 绑定整条管线，包括 reviewer 模型、量化、模板、配置、阈值及编号门禁 | 确认记录增加 `pipeline_signature`、`reviewer_signature`、`review_threshold`、`business_id_version`、每条完整 evidence hash 和 review hash |
| 确认重建 | `_rebuild()` 重新执行当前检索，再比较旧字段 | 旧确认不能因候选顺序或 reviewer 变化复用，也不应静默改用新结果 | 确认时不重新选择证据；在锁内验证原片段当前资格/版本/正文哈希及当前管线签名，再按原已审片段重建 payload 并核对 payload hash |
| 回答记录 | `answers`/`answer_sources` 不记录本地复核版本 | 回答证据须可追溯至当时固定管线 | 增加最小化 `answer_pipeline` 元数据或在 `answers` 增加管线摘要；只存摘要、模型/模板版本和片段 ID，不重复正文 |
| 并发 | 前端用 `previewRequestSequence` 防旧响应覆盖 | 服务端也需防晚到 reviewer 结果覆盖新问题/新资格状态 | pipeline 为每次请求分配 snapshot ID；响应携带 snapshot/pipeline 摘要；所有状态写入前比对版本，不共享可变“最后结果” |
| 备份恢复 | 备份理解现有语义配置和回答来源 | 新管线配置、回答元数据和失效规则需版本化 | 更新 schema/version、导出/恢复白名单与恢复后失效逻辑；模型文件、复核缓存和正文诊断不进备份 |

## 建议接口

```python
@dataclass(frozen=True)
class CandidateSnapshot:
    document_id: str
    chunk_id: str
    title: str
    text: str
    source_hash: str
    content_version: int
    qualification_version: int
    semantic_similarity: float
    fused_score: float

@dataclass(frozen=True)
class RetrievalSnapshot:
    snapshot_id: str
    question: str
    question_sha256: str
    index_signature: str
    index_generation: int
    index_revision: int
    candidates: tuple[CandidateSnapshot, ...]  # 0..40

@dataclass(frozen=True)
class ReviewedContext:
    snapshot: RetrievalSnapshot
    pipeline_signature: str
    reviewer_signature: str
    sources: tuple[dict, ...]          # 最终预算后的 0..6 条
    related_sources: tuple[dict, ...]  # 被拒资料，仅本地展示
```

建议把编排放在新模块 `pkb/evidence_pipeline.py`，让 `embedding.py` 只负责索引和召回，`evidence_review.py` 只负责单片段复核，`answers.py` 只消费 `ReviewedContext` 并管理确认。不要把 reviewer 条件继续堆进 `Embeddings.retrieve()`。

## 后续出现合格且获批候选时的实施顺序

1. 先冻结唯一 reviewer 的模型摘要、量化、模板、参数、接受规则和测试报告摘要。
2. 增加配置表与状态机，但保持 `formal_enabled=0`；旧余弦 threshold 不迁移为 reviewer threshold。
3. 拆出 40 条候选快照和复核后最终预算，补上资格/正文版本重验。
4. 接入预览的 `sources` / `related_sources`，保持拒绝资料无选择控件。
5. 扩展确认与回答管线绑定，确认旧 token 在配置变化后全部失效。
6. 更新备份/恢复与前端状态文案。
7. 由独立测试在新的固定提交执行确定性回归、真实模型全链路和浏览器验收；通过前仍保持阻断。

当前停止点：0.6B 在已知验证中正例 11/12、难负例拒绝 5/6，盲测难负例拒绝 9/12；4B 在已知校准中正例仅 10/12。两个候选均违反硬性质量要求，不执行上述正式集成。依据为 `docs/testing/S2-e1eff9c/report.md`。

## 明确不在当前并行阶段执行

- 不启动 0.6B 或 4B，不重复独立测试的模型测量。
- 不改 `e1eff9c` 代码和配置，不固化任何测试中的临时阈值。
- 不读取正式资料库，不创建正式 reviewer 缓存，不生成云端确认，不调用 DeepSeek。
- 不提前为两个候选都建设正式 UI；只在测试选型后集成一个候选。
