# S2 同一 4B 模型 Q6_K 受控对照实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不更换模型、提示、输入和推理参数的前提下，构建一个来源可重放的 `Qwen3-4B-Instruct-2507 Q6_K` 候选，用一次有停止边界的实验判断该候选能否通过冻结质量门槛；由于旧 Q4 与新 Q6 的来源链不同，本实验不作量化位宽因果归因。

**Architecture:** 从固定的 Qwen 官方 BF16 修订生成 BF16 GGUF，再用同一固定 llama.cpp 源码构建的量化器生成 Q6_K；在第二个干净目录完整重放并核对摘要。产物通过来源审计后，测试任务按“15 题硬门槛 → 已知回归 → 新盲测与稳定性 → 40 候选性能资源 → 正式集成”的顺序独立验证，任一硬门槛失败即停止后续昂贵阶段。

**Tech Stack:** Qwen3-4B-Instruct-2507、llama.cpp、GGUF/BF16/Q6_K、Python 3.12 独立环境、SHA-256、现有 `pkb.evidence_review` 测量入口。

**Spec:** `docs/superpowers/specs/2026-10-03-s2r1-qualified-evidence-review.md` 第 7 节；来源链最低要求见 `docs/audit/S2-quantization-provenance-closeout.md`。

## Global Constraints

- 当前阶段只允许盘点和方案评审；不得下载权重或工具、执行转换、启动新模型、运行模型测试或改正式应用状态。
- 新资源实验必须先经产品与审计审查，再由总负责取得用户对下载、转换、磁盘占用和模型运行的明确批准。
- 固定模型只能是 `Qwen/Qwen3-4B-Instruct-2507`；不得自行换模型、增加第三模型或进行无边界候选搜索。
- 当前 `Q4_K_M` 的失败只能证明固定候选未达标；不能据此归因于量化精度或模型容量。Q6_K 通过或失败也只回答本受控配置，不证明一般性因果关系。
- 固定提示、JSON schema、接受门禁、候选顺序、正文预算、context 8192、temperature 0、seed 1、max_tokens 384、非思考模式和零自动重试；除模型文件、量化标识、模型摘要和相应配置签名外不得改变代码行为。
- 正式状态保持 `calibration_required`；Q6_K 通过隔离测试也不自动启用正式问答。
- 新模型摘要使旧模型输出、确认和缓存失效；旧 Q4_K_M 测试结果仅作基线，不迁移为 Q6_K 通过证据。
- 开发只构建候选、保存来源链并做静态核验；所有模型质量、稳定性、性能、资源和浏览器全链路测试由测试任务执行。

---

## 1. 决策：只推荐 Q6_K

Q6_K 是本轮唯一推荐精度。它相对当前 Q4_K_M 提供明显的位宽提升，同时预计仍能在 24 GB 统一内存机器上进行一次受控运行。Q5_K_M 的增量较小，不值得新增完整来源链与全套复验；Q8_0 和 BF16 的常驻内存预计更高，已明显增加超出既有“两模型约 4–6 GiB”目标的风险。本轮不做多精度横向搜索。

量化器帮助文本给出的 7B 参考大小为 Q4_K_M 4.58G、Q5_K_M 5.33G、Q6_K 6.14G、Q8_0 7.96G、BF16 14.00G。这些是量化器对其他架构的参考值，只用于比例估算，不能当作本模型实测大小或质量指标。

## 2. 固定来源与文件清单

### 官方模型输入

- 官方仓库：`Qwen/Qwen3-4B-Instruct-2507`。
- 固定修订：`b79a0e62a051eebdd801742a4a70bbaac6b38747`。
- 固定来源前缀：`https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/resolve/b79a0e62a051eebdd801742a4a70bbaac6b38747/`。
- 权重文件：`model-00001-of-00003.safetensors`、`model-00002-of-00003.safetensors`、`model-00003-of-00003.safetensors`、`model.safetensors.index.json`。
- 转换输入和核验文件：`config.json`、`generation_config.json`、`tokenizer.json`、`tokenizer_config.json`、`vocab.json`、`merges.txt`、`added_tokens.json`、`special_tokens_map.json`、`chat_template.jinja`、`LICENSE`、`README.md`。

模型文件的逐项字节数、Git/LFS 标识和 SHA-256 已在 `docs/development/S2-q6k-source-manifest.json` 与 `docs/audit/S2-q6k-source-review.md` 补齐。下载必须严格按15项精确路径执行，禁止通配符、`snapshot_download` 和仓库全量 clone；同修订的两片替代权重、`global_step6/`、pickle checkpoint、训练脚本及其他文件明确排除。不得用 `main`、当前最新版本或同名第三方仓库替代。

### 固定转换工具

- llama.cpp 官方仓库：`https://github.com/ggml-org/llama.cpp`。
- 固定提交：`7fe450e19305b828c199d602c23a8337aaa1f03b`。
- 使用该提交的 `convert_hf_to_gguf.py`、`gguf-py` 和本地构建的 `llama-quantize`。
- 已盘点直接依赖约束：`torch==2.11.0`、`numpy~=2.2.6`、`sentencepiece>=0.1.98,<0.3.0`、`transformers==4.57.6`、`protobuf>=4.21,<5`。转换器使用同一 llama.cpp 提交内的 `gguf-py==0.19.0` 与 `conversion` 源码，禁止安装范围式 PyPI `gguf` 替代它。`gguf-py` 还声明 `tqdm>=4.27`、`pyyaml>=5.1`、`requests>=2.25`。实际 macOS/arm64、Python 3.12 的完整传递 wheel URL、文件名、平台标签、字节数、SHA-256 和许可证必须在用户批准前锁定；“执行时生成 lock”不满足门禁。
- 构建工具链还必须固定 Python 解释器 build、CMake、Apple Clang/Xcode SDK、configure cache/flags及最终二进制/动态库摘要。未完成依赖 SBOM 与工具链锁定前，来源状态为 `approval_blocked`。
- 禁止 `--remote`、`trust_remote_code`、importance matrix、重量化、tensor override、`--allow-requantize` 和任何未记录的参数变化。

### 固定构建命令

路径在 manifest 中先解析为绝对路径。实际命令必须按 argv 数组记录，以下占位路径在批准后一次性替换，不通过 shell 插值执行：

```text
["git", "clone", "--filter=blob:none", "https://github.com/ggml-org/llama.cpp.git", "/ABS/llama.cpp"]
["git", "-C", "/ABS/llama.cpp", "checkout", "--detach", "7fe450e19305b828c199d602c23a8337aaa1f03b"]
["cmake", "-S", "/ABS/llama.cpp", "-B", "/ABS/llama.cpp/build", "-DCMAKE_BUILD_TYPE=Release"]
["cmake", "--build", "/ABS/llama.cpp/build", "--target", "llama-quantize", "-j", "4"]
["/ABS/venv/bin/python", "/ABS/llama.cpp/convert_hf_to_gguf.py", "/ABS/qwen-snapshot", "--outfile", "/ABS/run-a/qwen3-4b-instruct-2507-bf16.gguf", "--outtype", "bf16"]
["/ABS/llama.cpp/build/bin/llama-quantize", "/ABS/run-a/qwen3-4b-instruct-2507-bf16.gguf", "/ABS/run-a/qwen3-4b-instruct-2507-q6_k.gguf", "Q6_K"]
```

`run-b` 在新的干净目录使用已核验的只读输入、相同源码归档、依赖锁和相同 argv 完整重放。两次最终 GGUF 的 SHA-256 必须相同；若存在有解释的非确定字段，停止并先由审计批准规范化内容哈希或逐张量等价验证，开发不得自行降低为“文件能加载”。

## 3. 资源预算

### 已有实测

| 项目 | 实测值 | 证据边界 |
| --- | ---: | --- |
| 机器 | Apple M5 MacBook Air，24 GB 统一内存 | 仅说明当前执行主机；不含序列号等设备标识 |
| 当前可用磁盘 | 599 GiB | 2026-10-11 `df -h` 快照，后续会变化 |
| 当前 Q4_K_M GGUF | 2,497,281,120 B（2.326 GiB） | SHA-256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` |
| Q4_K_M reviewer RSS | 约 3.72 GiB | 24 问 × 6 候选局部测量，不代表 40 候选峰值 |
| embedding RSS | 约 1.16 GiB | 与 reviewer 同时常驻快照 |
| 两进程 RSS 合计 | 约 4.88 GiB | 不含全部系统共享内存和转换阶段 |
| 系统 swap | 当时约 1.49 GiB 已使用 | 缺少启动前基线，不能归因于模型 |
| Q4_K_M 延迟 | p50 3.90 s、p95 4.65 s | 24 问 × 6 候选，非 40 候选最终管线 |

### 计划估算

| 项目 | 估算 | 推导和限制 |
| --- | ---: | --- |
| Q6_K GGUF | 约 3.35 GB / 3.12 GiB | 按当前 Q4 文件乘 `6.14/4.58`；实际以构建结果为准 |
| reviewer 常驻 RSS | 约 4.5–5.0 GiB | 当前 3.72 GiB 加约 0.79 GiB 权重差及运行波动 |
| reviewer + embedding 常驻 | 约 5.7–6.3 GiB | 已接近或超过原 4–6 GiB 目标上缘 |
| 模型运行峰值 | 约 6–8 GiB | 含上下文、Metal/共享内存与波动；40 候选前无法实测确认 |
| 官方模型 allowlist | **8,060,918,389 bytes（8.061 GB / 7.51 GiB）** | 固定修订逐文件路径/bytes/SHA-256 已在 manifest 和审计表；README/License 在15项内 |
| 工具源码、Python wheels、Python/CMake/SDK | 未锁定；粗估约 2–4 GB | 审计前置阻断；必须列出每个文件 URL、bytes、SHA-256、license 和下载上限 |
| 总网络下载 | 暂估约 10–13 GB，**批准值未确定** | 只有模型 allowlist 精确；工具和依赖未锁定，不能作为用户批准请求 |
| 单次 BF16 中间 GGUF | 约 7.6–8.2 GB | 按 4B BF16 权重及 GGUF 元数据估算 |
| 两次重放峰值落盘 | 预留 40–45 GiB | 官方快照、工具/venv、两个 BF16、两个 Q6_K、日志与余量 |
| 审计关闭前永久保留 | 约 20–22 GiB | 官方输入、第一份 BF16、第一份 Q6_K、锁文件、源码归档和日志；第二份重放产物在摘要一致并经审计确认后可清理 |
| 审计后最小保留 | 约 12–13 GiB | 官方输入、最终 Q6_K、来源 manifest、工具源码归档和依赖锁；进一步删除官方输入需用户批准且会降低离线重放便利性 |
| 转换峰值内存 | 约 10–16 GiB | 无本模型本机实测；BF16 转换和量化分别测量，禁止并行运行 |

模型快照 allowlist 精确合计为 **8,060,918,389 字节（8.061 GB / 7.51 GiB）**，其中权重 8,044,982,000 字节。转换源码、Python wheels 和构建工具下载还未锁定，因此“总网络下载 10–13 GB”及 40–45 GiB 工作区只能作为粗略规划估算，不能作为用户批准范围。现有系统环境实际为 Python 3.9.6、无 `cmake`，active developer directory 为 Command Line Tools（`xcodebuild` 不可用）；Python 3.12、CMake、完整 Xcode/SDK 及其下载大小/摘要尚未准备。来源依赖和工具链清单完成前，状态为 `approval_blocked`，不请求下载批准。

内存是主要不确定项：Q6_K 很可能贴近或超过原 4–6 GiB 双模型产品目标。4–6 GiB 仍是验收目标，超过 6 GiB 一律记为未达标。8 GiB 可归因 RSS、swap 增量和系统内存压力只是设备保护停止线，绝不是放宽后的合格线。

### 停止条件

构建阶段出现以下任一情况即停止，不进入模型运行：

- 固定修订不可获取、文件清单/摘要不能在下载前补齐，或任何下载内容不在已审查白名单；
- 下载预计总量超过 13 GB，峰值工作区预计超过 45 GiB，或实际工作区剩余空间低于 80 GiB；
- 单个转换进程 RSS 超过 16 GiB、macOS 内存压力持续进入黄色或红色、转换期 swap 增量超过 4 GiB，或机器出现持续失去响应；
- 两次重放最终摘要不同且审计未批准等强度的逐张量核验；
- GGUF 架构、tokenizer、chat template、量化类型或上游张量清单静态核验不一致。

模型验证阶段的资源门禁：

- 测试前记录内存压力、swap、reviewer/embedding RSS 基线；阶段结束后记录增量，不把既有 swap 归因于新模型；
- 两模型可归因 RSS 超过 6 GiB即记为产品资源目标未达标；不得写成“资源通过”；
- 两模型可归因 RSS 超过 8 GiB、内存压力持续黄色/红色、swap 增量达到 1 GiB或前台明显失去响应，立即停止后续压力测试并交付原始证据；
- 资源停止不改变质量结论，也不触发自动换模型。

## 4. 完整验证成本与顺序

测试任务负责执行并保留原始输入、结构输出、逐题判定、延迟和资源记录。开发不代跑模型测试。

| 阶段 | 最低工作量 | 进入条件 | 停止条件 |
| --- | ---: | --- | --- |
| 来源链与静态核验 | 两次完整转换；逐文件/中间/最终摘要；GGUF 元数据和逐张量清单比较 | 用户批准资源后 | 来源、重放或元数据任一不一致 |
| 固定 15 题硬门槛 | 15 个 passage 判定 | 来源链通过 | 必须 15/15；任何一题失败即结束候选 |
| 已知回归 | 24×6 + 24×6 + 38×10 = 668 个 passage 判定，另跑现有确定性边界 | 15/15 | 已知正例、难负例、无证据或注入边界任一硬失败 |
| 新盲测 | 至少 36×10 = 360 个 passage 判定 | 已知回归全过 | 继续至少 11/12 正例、难负例零误放、无证据零误放 |
| 稳定性 | 关键边界各重复 3 次 | 新盲测通过 | 任一重复产生阻断性漂移 |
| 40 候选性能资源 | 至少 20×40 = 800 个 passage 判定，加冷启动 | 质量与稳定性通过 | p50>10 s、p95>30 s、资源安全停止条件或产品资源目标不达标 |
| 正式集成与最终验收 | 159 条历史断言映射、浏览器全链路、隐私/缓存/确认失效、安全审计 | 前述阶段全部通过且产品批准集成 | 任一正式门禁失败，保持 `calibration_required` |

在不计稳定性重复、冷启动和最终集成的情况下，模型复核最低为 1,843 个 passage 判定。墙钟时间没有 Q6_K 实测，不给出伪精确工期；测试应在每阶段报告实际总时长后再估算下一阶段。旧 Q4_K_M 的 6 候选延迟只能用作容量规划参考。

## 5. 冻结证据和角色串联

新实验首次模型启动前，测试任务必须在独立证据目录一次性写入并封存：数据集、标签、manifest、固定候选提交、模型 SHA-256、提示 SHA-256、配置签名和带时区的时间记录。文件不得覆盖修改；任何修订写入新版本目录，并在运行前重新经审计核对。该链可达到内部审计充分性，但不得声称具有外部不可抵赖时间戳。

交接顺序固定如下：

1. 产品审查本计划是否满足“同模型、单一精度、有限实验”和产品资源边界。
2. 审计核对官方固定修订逐文件来源、完整依赖 SBOM、构建工具链、双重放、证据冻结和停止条件；模型15项清单已完成，依赖与工具链仍阻断批准。
3. 总负责向用户呈现 11–13 GB 下载、40–45 GiB 峰值工作区、20–22 GiB 审计期保留、最高 16 GiB 转换进程估算及模型运行风险，取得明确批准。
4. 开发构建并冻结唯一 Q6_K 候选，只做静态来源/元数据核验，提交候选摘要和全部差异。
5. 测试按阶段执行；每个硬失败即时通知产品、开发、审计和总负责，后续昂贵阶段不再启动。
6. 产品依据证据决定关闭路线、批准正式集成，或转为一个明确的新模型候选提案。任何转向都不得由开发自行实施。

---

### Task 1: 审批前来源清单冻结

**Files:**
- Create: `docs/development/S2-q6k-source-manifest.json`
- Create: `docs/audit/S2-q6k-source-review.md`

**Interfaces:**
- Consumes: 本计划第 2 节固定修订与白名单。
- Produces: 经产品/审计接受的逐文件 URL、字节数、SHA-256、许可证和下载上限；这是用户批准请求的唯一下载范围。

- [x] **Step 1:** 用固定修订元数据补齐15项模型文件的大小和摘要，不访问 `main`。
- [x] **Step 2:** 审计逐项核对模型发布者、修订、LFS 对象、许可证，并排除两片替代权重和训练工件。
- [ ] **Step 3:** 锁定 macOS/arm64、Python 3.12 的完整传递 wheel URL、平台标签、大小、SHA-256、许可证，以及 Python/CMake/Apple Clang/Xcode SDK 构建信息。
- [ ] **Step 4:** 审计核对完整依赖 SBOM、工具源码/二进制来源与拆分后的下载上限；在此之前保持 `approval_blocked`。
- [ ] **Step 5:** 总负责取得用户对 manifest 中全部下载、45 GiB 工作区和模型运行阶段的明确批准。
- [ ] **Step 6:** 将 manifest 与审计结论单独提交；此提交不包含下载文件或模型输出。

### Task 2: 可重放 Q6_K 候选构建

**Files:**
- Create: `scripts/build_qwen3_4b_q6k.py`
- Create: `docs/development/S2-q6k-build-manifest.json`
- Modify: `pkb/evidence_review.py`（只增加由冻结 manifest 绑定的隔离候选配置，不改正式 Q4 配置）
- Modify: `THIRD_PARTY_NOTICES.md`（只有候选可能进入正式应用时）

**Interfaces:**
- Consumes: Task 1 已批准 manifest、只读官方快照、固定 llama.cpp 源码和依赖锁。
- Produces: 两次重放摘要一致的 Q6_K GGUF、第一份 BF16 中间件、构建日志和可机器校验的来源 manifest。

- [ ] **Step 1:** 在新隔离目录按白名单逐文件下载并立即核对大小和 SHA-256；任一不符即删除失败下载并停止。
- [ ] **Step 2:** 固定源码、编译器、CMake argv、Python lock、wheel 摘要和二进制摘要。
- [ ] **Step 3:** 执行 `run-a` 的 BF16 转换与 Q6_K 量化，记录各阶段耗时、峰值 RSS、swap 增量、文件大小和 SHA-256。
- [ ] **Step 4:** 在干净 `run-b` 目录完整重放并比较 BF16、Q6_K、GGUF 元数据和逐张量清单。
- [ ] **Step 5:** 新增仅测试使用、由 manifest 精确绑定 Q6 SHA/量化版本的隔离配置；任意 CLI 摘要绕过必须失败，正式 Q4 固定值和 `calibration_required` 保持不变。
- [ ] **Step 6:** 静态核验通过后冻结候选；不启动模型，不宣称质量或资源通过。
- [ ] **Step 7:** 仅提交脚本、manifest、摘要、日志和通知文本；GGUF 保存在批准的本地模型目录，不提交 Git。

### Task 3: 独立分阶段验证

**Files:**
- Create: `docs/testing/S2-q6k-controlled-comparison/`
- Modify: 测试任务自己的报告和原始证据文件；开发不写测试结论。

**Interfaces:**
- Consumes: Task 2 唯一模型 SHA-256、固定代码提交、提示摘要和配置签名。
- Produces: 每阶段可独立审计的原始结果、硬门槛判定、资源增量和未执行项。

- [ ] **Step 1:** 首次模型启动前一次性封存 15 题数据、标签、manifest 和时间记录。
- [ ] **Step 2:** 执行 15/15 门槛；失败则停止并通知所有角色。
- [ ] **Step 3:** 仅在通过后执行 668 个已知 passage 判定和确定性边界。
- [ ] **Step 4:** 仅在通过后创建并封存至少 36 题新盲测，再执行 360 个 passage 判定和关键样本 3 次稳定性。
- [ ] **Step 5:** 仅在质量与稳定性通过后执行 20 问 × 40 候选及冷启动资源测量。
- [ ] **Step 6:** 报告所有已执行与未执行阶段，不把 Q6_K 成败扩展为对量化或容量的一般性归因。

### Task 4: 正式集成或路线关闭

**Files:**
- Modify: `pkb/evidence_review.py`
- Modify: `pkb/review_measure.py`
- Modify: 正式配置、模型摘要、缓存/确认版本与 `THIRD_PARTY_NOTICES.md`
- Create: 最终测试、审计和验收证据目录

**Interfaces:**
- Consumes: Task 3 全部硬门槛通过的固定候选；产品对正式集成的单独批准。
- Produces: 正式应用保持失败关闭的 Q6_K 集成，或明确记录该路线失败并继续 `calibration_required`。

- [ ] **Step 1:** 若 Task 3 任一硬门槛失败，记录路线关闭和未执行项，不修改正式配置。
- [ ] **Step 2:** 若全部阶段通过，更新正式模型 SHA-256、量化标识、通知、版本签名和旧确认/缓存失效边界。
- [ ] **Step 3:** 由测试执行 159 条历史映射、浏览器全链路、隐私与失败关闭验证；由审计复核来源、网络和许可。
- [ ] **Step 4:** 只有最终验收通过后才由产品决定是否解除 `calibration_required`。

## 自检结论

- 规格覆盖：已覆盖单一精度、官方修订与来源、工具提交和命令、下载/磁盘/内存、停止条件、估算与实测分列、完整复验和批准边界。
- 范围控制：本计划没有下载、转换、启动模型、运行测试、改正式配置或替用户批准新资源。
- 归因边界：当前失败和未来 Q6_K 结果均不被写成量化或容量的一般性因果结论；若将来确需判断位宽因果，须另行批准同一 BF16 输入和同一量化器生成的配对 Q4/Q6 实验。
- 尚未关闭：模型15项逐文件清单已补齐；完整 wheel/SBOM、构建工具链和隔离测试摘要绑定仍是用户批准前阻断项。
