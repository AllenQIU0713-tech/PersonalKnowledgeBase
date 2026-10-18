# S2R4 HTTP 未就绪映射：最小新候选交接

日期：2026-10-18。代码候选 **`afa5e393adf10fa03a4c1a87781557a0a20c2a06`**；基线 `391baf9db5afcffd8e2de4ba65782a05b6426a98`；产品固定契约 `787b51f` / `docs/superpowers/specs/2026-10-18-s2r4-http-readiness-contract.md`。完整 commit、规格原始 SHA-256 及17项 pkb源闭包见 `source-closure.json`。

## 唯一产品变化

`pkb/server.py` 增加 `EvidenceUnavailable` 导入，并把原 `except SemanticUnavailable` 扩为 `except (SemanticUnavailable, EvidenceUnavailable)`。位置仍在通用 ValueError/TypeError/UnicodeError 的400分支之前；沿用409 JSON结构：error与当前semantic/qa状态。

与391相比，除 server.py 外其余16项产品源码/静态文件逐字节相同。没有改异常类、校验顺序、资格、来源、threshold、pipeline、票据、UI或路由。语义浏览保持 **GET**，没有新增POST或私有HTTP端点。未启用正式QA。

## 历史证据与本次性质

只读核对 `4e8e8ca`、`9a5596e` 和 `391baf9` 的 server.py：三者都特别将 `SemanticUnavailable` 映射409、通用ValueError映射400。391的 `EvidenceUnavailable(ValueError)` 因而落入400；合法mock generate/prepare到达 `_require_qa_ready()` 时是真实拒绝，非外发/成功票据。原S2R3契约未对所有此类正式入口统一规定409，不能用语义浏览的409推定所有拒绝均409。

产品选择向前修订协议一致性，保留S2R4 v1冻结断言失败和后续not_run。本候选不是安全绕过修复、真实reviewer质量通过或旧测试改判。旧v10九项失败、391的56 deterministic以及S2R4 v1已测的真实embedding/double/browse保留各自提交/包身份，不改挂本候选。

## 精确异常到HTTP映射

| 路径/场景 | 抛出/返回 | 391实际映射 | 新候选契约 |
| --- | --- | --- | --- |
| GET `/api/semantic/status` | 正常状态字典、QA blocked | 200 | 200；qa.available=false与实际原因 |
| GET `/api/documents/semantic-search` 服务/索引故障 | SemanticUnavailable | 409 | 409，原路由/无回退保持 |
| POST `/api/answers/preview` 正常返回结构化 unavailable context | context.available=false | 200 | 200，不能把所有不可用预览改409 |
| 任意 Handler 路径逸出 SemanticUnavailable | 专门异常 | 409 | 409 |
| 任意 Handler 路径逸出 EvidenceUnavailable，例如reviewer/config失效 | 专门异常 | 400 | **409**，先于通用400捕获 |
| POST `/api/answers/generate` 合法mock请求到正式门禁 | EvidenceUnavailable | 400 | **409**；无answer、新成功记录或provider调用 |
| POST `/api/cloud/prepare` 合法请求到正式门禁 | EvidenceUnavailable | 400 | **409**；无新token/票据/外发 |
| POST `/api/cloud/confirm` 合法未过期的显式内部fixture到 `_rebuild` readiness | EvidenceUnavailable | 400 | **409**；fixture不等于真实prepare成功 |
| confirm缺失/不存在/无效/过期token；非法provider等实际普通校验 | ValueError | 400 | **400**；不得当深层readiness证据 |
| 内容/资格/索引版本变化等现有普通ValueError路径 | ValueError | 400 | 400，不统改“所有资格变化” |
| 错误请求格式/TypeError/UnicodeError | 原普通处理 | 400 | 400；鉴权/CSRF403、资料不存在404、provider错误502保持 |
| `_rebuild`、快照等私有直接调用 | Python异常 | 无HTTP状态 | 按实际异常类型/原因断言，不虚构HTTP路由 |

验证必须到达表中指定分支，不能把返回任何4xx都当通过。正常input错误仍可能按原执行顺序先被正式readiness阻断；请求错误400对照应选实际可达的普通校验，例如非法provider或缺失token，不能为强制400重排业务门禁。

## 独立复测范围与装配

沿用 `docs/development/S2R3-real-embedding-handoff-20261018/handoff.md` 的真实Handler+显式test-double装配，但源码导出、profile、source闭包、工具与外置witness均绑定本新候选。测试所有新支持模块和预期仍由测试任务创建/冻结；开发没有改其case矩阵或包。

- 按新固定契约逐场景冻结 **确切**状态、异常到达原因及完整JSON，不用“400或409均可”。保留真实普通400对照、现有browse409和结构化preview200。
- 对正式generate/prepare的409保留源状态、无成功answer/票据、provider尝试为零及相关表记录。测试新包补齐此前中断后的formal prepare、私有rebuild、可达deep confirm，分别报告，不把401/403/无效token的早期拒绝当readiness命中。
- deep confirm只能用明确登记的内部票据fixture到达门禁，不提升double资格，不造正式prepare成功链。记录预置fixture的票据基线和清理，不把“无新票据”与“从未存在fixture票据”混写。
- 这次改动只在Handler。产品明确无需重测未受影响且已确认的56 deterministic范围；旧通过归属不变。新候选所需HTTP/浏览/UI及失败关闭检查必须依其自身源码/新包执行，不拼接旧通过构成新全链通过。
- 两候选UI按各自既定范围和可用的本地浏览器连接执行；doctor无连接仍not_run，不引入云浏览器或新工具下载。不能为UI成功路径伪造qa.available或合格reviewer。
- `formally_qualified=False`、candidate_only和所有后端资格门禁未改。真实reviewer来源/answerability、完整正式提供方路径和资源仍未验证；本修订不触发Q6资源或真实DeepSeek。

## 开发检查

只做静态差异核对和 `git diff --check`；未运行测试、HTTP服务、模型或浏览器，未下载或读取正式资料。下一步由独立测试/审计核对新源码闭包、冻结新包后执行；若出现新缺陷，保留本候选证据再提交修订版本。
