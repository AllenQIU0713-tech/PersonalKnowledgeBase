# Q6_K 新隔离环境候选路线 v4

日期：2026-10-18（Asia/Shanghai）。状态：**候选路线与审批准备材料已固定，等待独立审计；Q6_K 仍为 `approval_blocked`。** 当前没有 artifact 下载、解包、bootstrap、安装、构建、转换、模型启动或测试授权。准备材料中的命令仅为 JSON 数据，未执行。

## 产品已确定的路线

后续候选使用 **Astral python-build-standalone** 发布的 CPython 3.12.13+20260623 arm64 归档（25,003,823 B，SHA-256 `41df7d3ae4757e84b97874f76d634268456aaa271740d33f968d826374998fb7`）及干净 pip 26.1.2 wheel（1,813,144 B，SHA-256 `382ff9f685ee3bc25864f820aa50505825f10f5458ffff07e30a6d96e5715cab`）。该解释器是 Astral 发行件，不能称为 Python.org 官方二进制。

现有 Python/uv/pip 不进入后续安装或构建链，不修复或改写其文件。v3 中的 9 项 pip RECORD 差异和来源限制保留；停止无限追溯旧安装，不把其问题改判为通过。v2 提交 `83c5b5c2185f7515d85dc37ac039614827bb67a8`、v3 提交 `d9f63a01b3723d51913f3eee7645088783a3dba7`、产品候选 `391baf9db5afcffd8e2de4ba65782a05b6426a98` 及测试 oracle 均保留。

工作根固定为 `/Users/allenqiu/Documents/ChatGPT/个人知识库/.q6k-isolated-20261018`。本轮没有创建它；未来获得相应授权时，该路径必须不存在，已存在即停止，不清空重用。所有下载、缓存、工具、venv、源码、输出和日志只能在该根下按清单归属写入；不做全局安装或写旧工具目录。

本文件细化旧计划的占位路径、粗估预算及工具准备链，提出固定归档/tree 验证替代旧 clone 方案；替代方案必须先获审计接受。将无法从元数据完成的包内检查列在下载后、执行前，依据本轮产品明确要求，不是开发自行豁免。旧计划的 45 GiB 工作区、80 GiB剩余空间、16 GiB转换停止线及独立测试/质量门槛继续有效；13 GB外层传输停止线也不构成可用下载额度。

## 可审计文件入口

| 文件 | 内容 |
| --- | --- |
| `artifact-allowlist.json` | 47 项候选 artifact 的 URL、身份、字节数/上限、目标路径与未批准状态：15 项模型、28 项 wheel、Astral Python、干净 pip、CMake、固定源码归档 |
| `requirements.lock` | 原已审元数据闭包的 28 项固定版本与确切 artifact SHA；torch 只用已选 CPU 索引文件 |
| `source-identity.json`、`raw/llama-source-tree.json` | 固定源码的 commit/tree/blob 身份、数量、大小及需要审计接受的归档验证方案 |
| `command-plan.json` | run-a/run-b 共 22 个准确 argv、cwd、清空继承后的环境字典、网络禁止及阶段前置条件；不是执行器 |
| `budget.json` | artifact body、展开安装、两次构建/输出、缓存、临时文件、日志、内存和清理的数值上限及归属路径 |
| `review-gates.json` | 供总负责设计分阶段申请的范围、禁止动作、退出审计门槛；没有阶段被自动授权 |
| `host-tool-inputs.json` | 现有 Apple 系统/CLT 工具及 SDK 配置的真实路径、当前摘要快照；不声称许可或完整性已获准 |

## 固定源码：已完成的元数据与尚待接受的身份方案

新增读取了 [GitHub 固定 commit 元数据](https://api.github.com/repos/ggml-org/llama.cpp/git/commits/7fe450e19305b828c199d602c23a8337aaa1f03b)及[递归文件树](https://api.github.com/repos/ggml-org/llama.cpp/git/trees/7fe450e19305b828c199d602c23a8337aaa1f03b?recursive=1)。commit `7fe450e19305b828c199d602c23a8337aaa1f03b` 的根 tree 为 `fd570ef54b10ec5fecb739e7e04c8ce44a6f415a`。API 无截断，3,619 个 blob 合计 **172,667,756 B**；逐目录重建 Git tree 序列化和 SHA-1，375 棵树全部对应，根与 commit 元数据一致。没有 gitlink 或 symlink，也没有 .gitattributes 导出规则。

候选归档 URL 为 `https://codeload.github.com/ggml-org/llama.cpp/tar.gz/7fe450e19305b828c199d602c23a8337aaa1f03b`。HEAD 未提供长度；ETag **不**充当归档 SHA-256。压缩正文硬上限提议为 **268,435,456 B（256 MiB）**；实际归档字节数和 SHA-256 只能在另获授权的取得后记录。

**归档身份方案仍需审计明确接受，不能自行视为关闭：** 下载前固定 commit/root tree/全部 blob 标识；下载后先验证路径、类型、展开限制，再对每个 blob 计算 Git 对象摘要并要求 3,619 项精确对应，无多余/缺失文件；同时冻结实际归档 SHA-256，后续重放使用同一归档。若审计不接受这一 Git 身份方案，或仍要求发布者预先公布的归档 SHA-256，源码项继续阻断，不因本文件已有预算就申请下载。

归档树包含 19 个命名为词表的 `.gguf` fixture，合计 **77,556,152 B**，路径逐项列于 source-identity。它们是工具归档清单的一部分，不作为 Qwen 模型输入，也不加载。其实际为词表且没有未批准权重张量，必须在下载后的数据检查阶段核实；发现不符即停止，不靠文件名宣称安全。模型来源仍仅限 15 项 Qwen 白名单；不使用 HF 全仓 clone、通配下载、pickle 或 trust_remote_code。

## Bootstrap、实际命令和环境

1. 获得单独的 artifact 取得/数据检查授权后，只使用审计核准的有界下载与解包方法处理白名单。检查 tar/ZIP 路径、大小、重复/大小写冲突、链接和特殊节点；核对身份、RECORD、许可、native 加载声明。此阶段不运行下载的 Python/pip/CMake 或仓库代码。其检查器与配额/网络监督方法仍需审计核准，不能先用 shell 管道无界解包。
2. 只有新 runtime、干净 pip 及输入审计通过，另获 bootstrap/build 授权后，才使用新归档解出的 Python 创建 `--copies --without-pip` venv。不调用归档自带 pip、旧系统安装的 pip 或 uv。
3. 干净 pip wheel 由前一数据检查阶段确认只含预期 `pip/` 和 `pip-26.1.2.dist-info/` 根、内容/许可均通过后，使用已有系统 ditto 复制这两个已核验目录到新 venv。随后通过新 venv 的 `python -I -B -m pip` 调用该包，省略全局脚本安装；不获取 get-pip.py。
4. 安装原固定的 28 项 wheel 时显式 `--no-index --no-deps --no-cache-dir --only-binary=:all: --require-hashes --no-compile`，只读取白名单 wheel 缓存。保存 pip 安装报告。不得解析出新依赖、另用 PyPI gguf、访问索引或安装时回退源码包。
5. 同 commit 的 `gguf-py==0.19.0` 在每次重放的精确源码副本中，使用固定 poetry-core 后端、`--no-build-isolation --no-deps --no-index` 生成本地 wheel。记录派生产物摘要、源副本身份和安装位置；原共享源码保持只读。converter 自身添加同 commit 的 gguf-py 路径，应记录实际导入来源。
6. CMake 3.31.8 使用明确的 Apple Clang/SDK、Unix Makefiles 和 -j 4，只构建 llama-quantize。配置静态 CPU 量化工具，关闭 Metal、BLAS、OpenMP、ccache、KleidiAI、动态 backend，以及 server/UI/examples/tests/app、OpenSSL/LLGuidance和远程预制 UI。禁 CMake package registry 和 FetchContent 更新。此选择只限定量化构建工具，不更改后续 reviewer 推理或产品资源目标。具体开关有固定 CMake 源文可核对，构建兼容性尚未验证；未识别开关、意外包/工具发现均停止。
7. 构建后独立核对二进制、派生 gguf wheel、依赖库、CMakeCache、完整 argv/env 和源身份，再另获转换授权。按 command-plan 以 `-s -B`、明确 PYTHONHASHSEED=0 和离线环境转换 BF16/Q6，run-b 使用新 venv/build/output 完整重放。不含模型服务启动命令，开发不代跑测试。

每个命令 envelope 都给出绝对 argv、cwd 和完整允许的环境键，不能通过 shell 插值拼接。PATH 仅有新 venv/CMake、固定 CLT 及系统目录，环境不继承凭据、PYTHONPATH、旧工具或用户配置；不重设用户 HOME/CODEX_HOME。HF/Transformers 离线和 telemetry 开关、独立 TMPDIR/cache/clang module cache、SDKROOT、SOURCE_DATE_EPOCH、线程上限均明确。GIT_CEILING_DIRECTORIES 限在新工作根，避免归档源码/本地包错误继承外层 PKB 仓库的 commit；不读取用户 Git 配置。bootstrap/pip 用 -I；转换用 -s 配合不继承环境，以便 PYTHONHASHSEED 生效。独立网络禁止与配额监督是必需门槛，环境变量不等于网络隔离。

## 全预算的已知值与提议上限

**这些是供审计与总负责评估的上限方案，不是当前授权、实测峰值或额度申请。** 47 项中 46 项有精确已知大小，共 **8,285,497,280 B**；源码项以 256 MiB 硬上限代替未知传输大小，且身份方案未接受前仍不能下载。

| 范围 | 字节数/上限 | 含义 |
| --- | ---: | --- |
| 15 项模型 | 8,060,918,389 B | 既有固定白名单精确值 |
| 所有非模型 artifact，含源码归档上限 | 493,014,347 B | 可供总负责单独考虑工具/许可检查阶段，非实际批准 |
| 全部 artifact 正文上限 | 8,553,932,736 B | 已知大小之和 + 源码归档 256 MiB |
| 控制/元数据正文预留 | 16,777,216 B | 本轮后续阶段提议，不能自动扩为新增 artifact |
| 合并正文上限 | 8,570,709,952 B | 不包含 TLS/HTTP 协议开销；申请前须由审计核准传输监督器和 wire 计量口径 |
| 含协议开销的外层传输停止线提议 | 13,000,000,000 B | 沿旧计划13 GB保护上限；仍须同时满足更小的各项/正文上限，不得将差额用于 retry 或新 artifact；wire 监督实现待审 |
| 展开安装、两次构建、两次 BF16/Q6、缓存/临时/日志分项上限之和 | 45,379,921,856 B | 约 42.26 GiB，细分及实际目录在 budget.json |
| 全工作区上限 | 48,318,382,080 B | 45 GiB；分项外保留 2,938,460,224 B，不能随意分配给新下载 |
| 开始前/运行中剩余空间停止线 | 85,899,345,920 B | 80 GiB，沿既有计划 |

磁盘分项包含：完整模型输入、原 artifact 缓存、源码 256 MiB、runtime 256 MiB、CMake 512 MiB、pip staging 16 MiB、两份 venv 各 1 GiB、两份本地 gguf 源各 16 MiB、两份 build 各 2 GiB、两份 BF16 各 9 GiB、两份 Q6 各 4 GiB、顺序处理 scratch/local wheels 1 GiB，以及日志/control/cache 256 MiB。展开大小当前未实测，提议上限被超过时停止，不能把上限标成已验证的实际大小。审计/总负责可要求收紧或补充监督机制后再提交申请。

下载单并发、每项一次正文尝试，不自动 retry/mirror/fallback；失败的部分字节计入额度。构建/转换串行，两个重放不同时运行。bootstrap/安装进程树 RSS 提议停止线 2 GiB、量化工具构建进程树 8 GiB；转换保留原单进程 16 GiB 停止线并同时提议进程树 16 GiB 保护。持续黄/红内存压力、阶段 swap 增量超过 4 GiB 或系统失去响应即停。以上不是峰值实测；不能拿构建预算替代之后模型测试的 6 GiB 目标/8 GiB保护线。

不写全局 pip/uv/cache；只在允许路径计量和记录。下载、展开、安装、build、converter 临时文件以及两个完整输出同时存在的最坏保留均纳入预算。审计关闭前保留已取得原件、run-a/run-b 结果及所有来源/配置/日志。只有两次输出摘要核对并得到清理范围确认后，才按具体已登记路径处理 run-b 输出/build/venv、staging/scratch/失败 part；不使用跨目录通配删除，不删除既有工具、模型、正式库或测试包。

## 分阶段授权与下载后、执行前的明确检查

`review-gates.json` 提议 A 工具 artifact 取得及数据检查、B 隔离 bootstrap/量化工具构建、C 模型取得及数据检查、D 双重放转换、E 独立模型测试。实际授权如何拆分由总负责依据独立审计清单决定，没有一个阶段因前阶段完成而自动开始。

以下无法由现有元数据证明，明确保留到 **另获授权的下载后、执行前**：

- Astral runtime、pip、CMake、28 wheel 的真实包内 component/SBOM/许可证、NOTICE、vendor 清单与 SPDX 归一；逐项与发布者 artifact 身份及声明对应。漏许可证或不明二进制不能通过。
- 新 runtime/CMake 的实际 native 文件和加载路径/架构、pip 原始 RECORD 全文件、解包实际峰值、目录边界/链接/重名情况。签名不能替代 pinned artifact 身份，ad-hoc 不称发布者签名。
- 源码压缩/展开实际字节、归档 SHA-256、全部 Git blob 内容、词表 fixture 实质、源码/第三方许可。Git 身份方案是否足以取代下载前缺失的归档 SHA，须先独立审计决定。
- 配额/网络/进程停止监督器、数据检查/安全解包器及 wire 计量口径。当前文档和 JSON 不是这些监督器的实现或通过证据；不以未经审查的 shell 命令直接执行命令集。

后续构建产物另在转换前接受独立摘要/依赖/源链审查。当前不生成质量、性能、UI、正式 QA、来源或许可通过结论；不把旧安装不一致改成已修复。本轮只进行了官方元数据/声明文本/HEAD 读取、本机工具摘要及静态 JSON/Git-tree一致性整理，没有取得源码归档、模型或 wheel 正文。
