# S2R4 问答未就绪 HTTP 契约

日期：2026-10-18（Asia/Shanghai）。状态：产品确定最小协议一致性修订路线，交独立审计核对历史与新候选范围；开发实施在独立开发聊天完成。本契约不启用问答，不改变模型资格或本地/云端边界。

## 1. 历史与选择

S2R4 v1 固定候选 `391baf9db5afcffd8e2de4ba65782a05b6426a98` 将 `SemanticUnavailable` 映射为409，而 `EvidenceUnavailable` 继承 `ValueError`，落入400分支。正式生成/准备因未合格reviewer被明确拒绝，不是成功授权。原S2R3产品规格要求失败关闭，未统一规定这些正式入口必须409；原browse bq14的409专指语义浏览索引未就绪，不能直接推及所有拒绝。

v1 冻结断言失败与后续未执行记录保留。独立审计仍须核对原始响应、实际到达原因、记录/票据及清理证据；本文件不追溯改标，也不据状态码差异认定绕过门禁。

可选路线为保留当前400并在新包精确修订测试，或统一类型明确的未就绪异常为409。产品选择后者，保持现有语义故障409的一致处理，仅新增 `EvidenceUnavailable` 的专门异常映射。不得将全部 `ValueError` 改成409，不接受同一冻结场景“400或409均可”。

## 2. 逐端点与路径

| 端点/检查 | 冻结场景 | 确切契约 |
| --- | --- | --- |
| GET `/api/semantic/status` | 查询当前索引和QA可用性 | 200；QA未就绪时 `qa.available=false` 与实际原因，浏览状态独立 |
| GET `/api/documents/semantic-search` | embedding服务/浏览索引未就绪且抛 `SemanticUnavailable` | 409；明确故障、无关键词回退，不返回冒充有效语义结果的items |
| POST `/api/answers/preview` | 返回正常结构化context，门禁不可用 | 200；`available=false` 及对应状态/原因。候选隔离预览不赋予正式资格 |
| 任一上述或下列Handler路径 | 未捕获的 `SemanticUnavailable` 或 `EvidenceUnavailable` | 409；先于通用ValueError分支处理。不能为了强制preview200吞掉异常或伪造context |
| POST `/api/answers/generate` | 合法mock请求到达 `_require_qa_ready()`，reviewer缺失/不合格或其他正式readiness未满足 | 409；错误原因对应当前门禁，无answer/新成功记录 |
| POST `/api/cloud/prepare` | 合法请求到达正式readiness门禁，不允许准备 | 409；错误原因对应当前门禁，无confirmation_token/票据/云端请求 |
| POST `/api/cloud/confirm` | 测试中合法且未过期的显式内部票据fixture能到达 `_rebuild()`，正式readiness未满足 | 409；实际门禁原因、零provider尝试/新成功记录。fixture不是正式prepare成功 |
| POST `/api/cloud/confirm` | 缺失、无效、不存在或已过期凭据 | 按现有ValueError分支400；不计为深层readiness检查通过 |
| 请求格式、字段、provider/model或其他既有ValueError/TypeError校验 | 未抛上述专门未就绪异常 | 保持400；认证/CSRF仍按原403，资料不存在等原状态保持 |
| `_rebuild()`、快照校验等私有函数单元检查 | 无HTTP路由 | 断言实际异常类型与原因，不虚构HTTP端点或通过状态 |

路由名称以固定候选源码为准，测试打包前逐项核对，不增加新HTTP接口。资料/证据版本变化等现有普通ValueError保持其原处理，不将“所有资格拒绝”笼统改码。

## 3. 修订与验证边界

开发保留391与旧证据，另提交只涉及类型明确的Handler异常映射及必要导入的最小新候选；不得提升double资格、删门禁、放宽证据或修改冻结oracle。测试/审计先核对源码闭包和新候选，再冻结新批次，不能沿用指向391的旧见证运行新代码。

新测试包逐场景固定确切状态和实际原因，同时断言无answer、无新票据、零provider尝试及对应表记录。保留原有语义browse的409和结构化preview的200；加真实请求错误400对照，确认专门异常分支不会吞并格式/凭据错误。无效token只能证明凭据门禁；深层confirm须有可达的内部fixture并明确其有限证明范围，不能冒充合格QA的成功prepare链。

原先未执行的formal prepare、私有rebuild、深层confirm和两候选UI按各自固定版本与既定范围补测；不重复已确认且未受变更影响的56项deterministic范围。已经通过的真实embedding/double/browse结果保留所属提交和包身份，不能直接挪到新候选名下。

浏览器必须先有获准的本地连接与可观测动作；doctor没有连接不计UI失败或通过。不引入云浏览器、云登录或下载新工具。原六项UI预期、391资料标识渲染差异及旧九项QA失败继续保留，按实际结果报告。

正式QA仍 `calibration_required/blocked`；本协议一致性修订不证明真实reviewer质量、完整生成/提供方链路或性能，不授权正式资料、DeepSeek请求、Q6资源或发布。
