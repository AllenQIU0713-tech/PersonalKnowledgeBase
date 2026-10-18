# 391baf9 对旧 v10 九失败的覆盖与隔离集成交接

日期：2026-10-18。固定候选：`391baf9db5afcffd8e2de4ba65782a05b6426a98`。本交接仅静态对照代码/既有报告，没有运行测试，也没有修改候选、oracle、测试 profile 或旧结果。现阶段未发现为这九项另改产品代码的结构性缺口；下述覆盖是代码路径和既有 deterministic 证据的对应，不能关闭真实 reviewer/跨版本集成验证。

## 两个版本的结果边界

旧 `4e8e8cac10452b5e0b565902bd191acba90dd26f` 的 v10 保留 QA 13/22 已测层通过、9失败；browse 13自动通过、bq10人工未执行。不能把旧失败改为通过，也不能把旧实际 embedding/cosine 证据与新候选 56/56 deterministic 拼接成完整产品通过。参考报告及原始 result.json 的 SHA 在 `source-closure.json`，本文件不编辑其内容。

现有新候选 deterministic v3 的 registry 有56项，SHA-256 `5770842da90bcca2d42048e19ef0a7510c7edeb7dd4b86e61d899467877faf47`。下表只引用其中直接相关的 case ID，省略号不代表新增测试结论。

## 九项逐条对应

| 旧 v10 失败 ID | 保留的失败事实 | 391baf9 实际路径 | 相关既有 deterministic case | 新集成需要记录 |
| --- | --- | --- | --- | --- |
| q08 | insufficient 仍暴露 preview sources | `_review_result` → `review` → `Answers.context` | `quote-reject`, `backend-rejected-minimization`, `backend-consistent-unqualified` | 实际召回 ID/cosine、double 原始拒绝输出、最终空证据/阻断 |
| q09 | 同上 | 同上 | 同上 | 同上，独立保留本题结果 |
| q10 | 同上 | 同上 | 同上 | 同上，独立保留本题结果 |
| q11 | 同上 | 同上 | 同上 | 同上，独立保留本题结果 |
| q13 | 同上 | 同上 | 同上 | 同上，独立保留本题结果 |
| q14 | 同上 | 同上 | 同上 | 同上，独立保留本题结果 |
| q18 | 同上 | 同上 | 同上 | 同上，独立保留本题结果 |
| q19 | 同上 | 同上 | 同上 | 同上，独立保留本题结果 |
| q12 | conflict 可选 sources，且无 conflicts | `_review_set` + 全 supported 分批覆盖 → `review` 清空 answer_sources → `Answers.context` conflict → prepare/generate 后端资格门禁 | `set-conflict-rank7`, `set-conflict-rank40`, `backend-conflict-one-side` | 实际召回/全部 supported/各批覆盖、验证后的冲突两侧只读引文、空可选 sources、正式状态/票据持续阻断 |

对前八题，代码不会根据题号硬编码答案。`pkb/evidence_pipeline.py:_review_result` 只接受 envelope 完全绑定且 `accepted is True`、`verdict=supported`、每条引文有效的结果；拒绝结果不进入 accepted。`review()` 的 sources 来自通过集合门禁的 selected 子集；`pkb/answers.py:context` 不再把原始余弦召回直接当成答案来源。business-ID、隐私/资格等预门禁可能使部分候选在 double 前被排除，须原样记录实际路径，不能为凑命中绕过门禁。

对 q12，只有实际被召回并通过逐片段复核的引文才进入集合检查；拟回答集合与全部剩余 supported（最多40，含第7/40名）必须完成固定覆盖。有效 conflict 返回两侧原文且 sources为空；invalid/uncertain/失败/超限也不生成答案来源。单边选择不能使 prepare/generate 成功。真实 reviewer 是否能正确判定每题，仍是独立质量问题，double 的既定输出不能证明它。

正式 server 未注入 reviewer：`Answers.context()` 直接 unavailable/空 sources；`qa_status()` 和 `_require_qa_ready()` 还要求正式合格和 verified 集合门禁。因此原失败在正式部署中应呈现明确暂停，而不是声称已回答或显示可用来源。测试 task 应对固定391自行验证这一行为；本文件没有代运行。

## 现有对象与建议装配

没有 `Config` 类。已有入口为 `pkb.config.data_directory(value)`，必须传新隔离绝对目录，不能省略参数落到正式默认库。测试 task 在自己的新冻结包中准备合成库/迁移/fixtures，并在实际测试入口标记之后创建下列对象；构造器和 worker 都算候选调用，不放在 metadata-only preflight。

- `Store(root: Path)`；只使用本次合成运行目录。
- `Embeddings(store, port=已批准现有loopback端口, model=APPROVED_MODEL_SHA256)`；固定模型 ID 为 `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`。由测试 task 管理既有模型进程，不新增下载。
- 需要打开合成索引召回路径时，用 `set_calibration(profile.threshold, frozen_profile_sha256)`，阈值必须来自独立冻结的 test-only profile，不能变更生产阈值；-1.0 不是 answerability 证明。等待完整索引 ready，而非用 sleep 假定完成。
- `EvidencePipeline(test_double)` 只在测试自己的装配模块显式创建；正常 `server.main()` 没有 reviewer CLI 或注入工厂，继续关闭正式 QA。
- `Answers(store, embeddings, cloud_provider=测试自有DeniedCloud, evidence_pipeline=pipeline)`；DeniedCloud 必须实现 name、destination、configured()、answer(payload)，禁止真实 provider/网络并保留调用记录。
- 使用现有 `Handler` 和 `ThreadingHTTPServer` 的真实 HTTP 路由/静态文件，给其 server 填入 main() 所用字段。不要复制改写 Handler 绕过鉴权，也不要改产品代码或把 test-double 注册为生产 reviewer。

下列是装配接口示意，测试 task 在自己的冻结支持模块实现和验证。调用者传入的四个运行对象、double 与 denied provider 均须先由测试 profile 绑定；该函数不启动模型或 HTTP loop，也不提供资格提升：

```python
import secrets
from http.server import ThreadingHTTPServer
from pkb.answers import Answers
from pkb.evidence_pipeline import EvidencePipeline
from pkb.server import Handler

def assemble_http(store, embeddings, extractor, reviewer_double, denied_cloud):
    pipeline = EvidencePipeline(reviewer_double)
    answers = Answers(store, embeddings, cloud_provider=denied_cloud,
                      evidence_pipeline=pipeline)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.store = store
    server.embeddings = embeddings
    server.extractor = extractor
    server.answers = answers
    server.authority = '127.0.0.1:' + str(server.server_port)
    server.origin = 'http://' + server.authority
    server.bootstrap, server.session, server.csrf = (
        secrets.token_urlsafe(32) for _ in range(3))
    return server
```

缺 reviewer 的对照装配使用同样 HTTP字段，但 `Answers(..., evidence_pipeline=None)`。不要把 `server.main()` 改成测试入口。语义浏览/精确查找使用同一 server.embeddings/store，必须在391自身验证，不复用旧4e8e8ca“通过”计数。`Extractor(store)` 是现有可用对象；若此次只用已准备好的合成文本，应保持无需 OCR/媒体编译。若要增加媒体路径，测试须另冻实际 extractor binary/source/许可和范围，不在本交接自动构建它。

测试 task 自行持有新目录 process lock、管理 serve_forever 线程和 finally 清理：停止/唤醒 extractor、停止 embeddings worker、关闭 HTTP server，回收自有模型子进程并保存 terminal/退出证据。测试工具既有 canonical-path、外置见证与 supervisor 要求继续适用。

## Test-double 协议与资格不可绕过

double 的 `configuration`/`config_signature` 为只读固定值。candidate 和 runtime 字段要明确 `test-double`，model_sha256 是已冻结 double 配置/实现身份的64位摘要，不能冒充真实模型；settings/template/pipeline/runtime/protocol 均进入 `configuration_signature(...)`。S2R3 管线要求 `result_protocol_version='s2r3-evidence-set-review-v1'`。不要直接把现有 InstructReviewer/RerankerReviewer 当作该 double：它们协议不同、没有此集合接口，也未获正式质量资格。

实现 `review(ReviewInput)` 和 `review_set(question, evidence, comparison_plan, timeout_seconds=...)`：

- 单段 envelope 绑定 question/evidence/passage/content_version/qualification_version/config/pipeline/runtime/protocol，reviewer_output 含 verdict 和精确 evidence_quotes。有效supported仍须通过连续子串、非空白、含字母/数字等代码核验。
- 集合输出绑定 question_sha256、evidence_set_sha256、comparison_plan_sha256、config_signature、result_protocol_version、按输入顺序的 source_ids、verdict、checked_pairs、conflicts。consistent 的 checked_pairs 必须精确等于计划中的两个 pair 列表串接。
- digest 是 UTF-8 canonical JSON（ensure_ascii=False、sort_keys=True、separators=(',', ':')）的 SHA-256。集合 evidence hash 对应 `{'question_sha256': ..., 'evidence': evidence, 'comparison_plan': comparison_plan}`；具体字段以固定391的 `_review_set` 为准。
- conflict 的每组为 `{'evidence': [{'source_id': ..., 'quote': ...}, ...]}`，每侧 ID 必须在本批、quote 必须等于已接受引文；不可用 title/body 猜造 quote。same reviewer 必须在给定 timeout 内返回，不能丢批或截断。

**禁止修改** `EvidencePipeline.formally_qualified=False`、`conflict_detection_state='candidate_only'`，禁止用普通配置/客户端参数、monkeypatch `Answers.qa_status` 或假资格 subclass 提升正式 readiness。内部成功 baseline 仅限既有 candidate-only preview/pipeline 控制；不能为成功生成/票据绕过生产门禁。

当 double 接受正例时，candidate-only HTTP preview 可提供受控、只读 sources，但 `available=false` 且 qa_state 仍 blocked_by_unqualified_reviewer。当 double 拒绝证据时，sources为空；当集合冲突时，返回 conflict 只读组和空 sources。不能把所有 unavailable 都当 insufficient，也不能因为正式门禁关闭而把受控正例通路一律不测。

## HTTP/UI 可执行范围与必须分层报告

正常 unlock/cookie/session/CSRF/Host/Origin 流程继续生效。使用 `/unlock?token=...` 一次性入口，取得 session 后读取 `/api/session` 的 csrf；POST 保留匹配 Origin、JSON Content-Type、X-PKB-CSRF。不得关闭这些检查以便测试。

测试 profile 至少明确 real_embedding=true、real_reviewer=false、test_double=true、formal_qa_expected=blocked、cloud_requests_allowed=false、production_data_allowed=false、answerability_claim=false、cross_version_pass_claim=false；profile/registry 的实际文件由测试 task 创建并冻结，开发不改它们。

- **真实检索接线**：在当前391、同一次新运行中保存真实 query/passage embedding、维度/归一化、独立 cosine、rank、候选/chunk/文档 ID、版本/资格/来源；追溯每条 double 输入到实际召回，保留全部 supported 与分批覆盖。不以“socket列表为空”冒充真实 embedding 成立：允许的 loopback请求必须可追溯，外部 provider 请求仍为零。
- **失败关闭**：直接 HTTP preview/prepare/generate、确认路径及 SQLite 后置计数均记录原始结果。正式资格不存在时 prepare/generate/rebuild/confirm 应始终 blocked，不能制造正式成功票据。票据内部-unit 成功 baseline 与真实 HTTP 成功路径分开报告，不能把旧56项的内部结果写成HTTP已通过。
- **实际页面**：普通页面正式 QA 状态仍 blocked，预览/模拟/云端按钮禁用；browse/精确查找可独立使用。不能为了点击按钮而伪造 qa.available=true。若要单独覆盖 candidate-only conflict renderer，可由测试支持模块明确记录受控响应的展示检查；该结果不能冒充普通用户完整问答流程。HTTP直接调用、受控renderer展示和实际用户页面操作分别计数。bq10及真实浏览UI由测试 task 独立完成，未做就保持not_run。
- **未闭合项**：这次范围没有真实 reviewer 来源、语义 answerability/冲突质量、真实 DeepSeek或资源稳定性。前八题 double拒绝与q12 double冲突只证明接口门禁行为，真实语义结论待合格 reviewer 单独验证。

真实 embedding+double 是新版本集成测试，不是把既有结果汇总。任何异常、期望不符或未到后置计数的案例保留失败/未执行，不能过滤来源、换题、调阈值或改旧报告来凑通过。发现391自身新实现缺陷时，先保留本候选与新包证据，再交开发提交新的不可变候选。

## 冻结源闭包

`source-closure.json` 列出固定391的完整17项 pkb源码/静态资产 SHA-256。测试 task 对该固定 Git blob 树导出新隔离 checkout，不能从随时变化的共享HEAD取源码。自己的装配/double/fixture/profile/registry/entry/supervisor/preflight/外置 witness 以及实际 embedding model/runtime/argv/env/解释器/依赖/平台均须进入新冻结包，原标签和旧结果不改。若使用未列的OCR/媒体脚本或二进制，应扩大源闭包并重新审计冻结，不静默引用工作区可变文件。
