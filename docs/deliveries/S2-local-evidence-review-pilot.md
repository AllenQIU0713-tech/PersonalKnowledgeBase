# S2 本地证据复核试验开发交付

日期：2026-10-02。产品规格提交：`8da9461fbb8ad7dc56aa212228907a5393e2f263`。

本交付提供两个候选的固定适配器和隔离测量入口，不启用正式自然语言问答。正式页面和服务仍保持 `calibration_required`；本提交没有新复核缓存、正式确认或 DeepSeek 调用路径。

## 开发内容

- `scripts/qwen-reranker-logits.cpp` 直接使用 llama.cpp C API。它固定 Qwen causal reranker 模板，对完整 prompt 解码，只读取最后位置真实 `yes` / `no` token logits，并输出原始 logits、两类 softmax 分数和 token 数。它不使用通用 rank pooling，也不生成 yes/no 文字充当分数。
- `pkb/evidence_review.py` 在两个候选前执行统一完整业务编号门禁。问题里的全部业务编号都须在标题或正文中以 NFKC/casefold 后的完整 token 出现；纯数字、年份和日期不会成为业务编号。
- 4B 适配器只访问固定 `127.0.0.1`，禁用代理和重定向，单次请求受严格 JSON schema、大小、超时和固定参数约束。只有 `supported` 且非空引文在实际正文中逐字存在才结构性接受；任何失败都拒绝，且无修复或重试请求。
- `pkb/review_measure.py` 只读取命令行显式给出的隔离 JSON 数据集。每题最多 40 个已召回候选；结果绑定问题/证据哈希、内容/资格版本、模型摘要、量化、模板、配置和管线版本。它不打开正式 SQLite 或 `PKB_DATA_DIR`。
- 0.6B 报告有意保留 `accepted: null`，由独立测试用校准集选择阈值；开发未把 0.5 或任何其他数值固化为可答门槛。

## 固定文件与运行时

| 项目 | 固定值 |
| --- | --- |
| llama.cpp | Homebrew 0.5.0，build 11146，commit `7fe450e19305b828c199d602c23a8337aaa1f03b`，MIT |
| 0.6B 实际模型 | `Qwen3-Reranker-0.6B-Q8_0.gguf`，639,153,184 字节，SHA256 `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48` |
| 4B 实际模型 | `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`，2,497,281,120 字节，SHA256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` |
| 0.6B 模板 | `qwen3-reranker-official-answerability-v1` |
| 4B 模板 | `qwen3-instruct-evidence-json-v1` |
| 编号门禁 | `business-id-all-match-v1` |
| 管线 | `local-evidence-review-pilot-v1` |

本机核验文件位于 `~/Library/Application Support/PersonalKnowledgeBase/models/`。0.6B 适配器通过 stdin/stdout 与模型进程通信且不开放网络监听；4B 必须按 README 命令只监听 `127.0.0.1:8767`。测试仍须独立记录实际进程、监听和连接证据。

完整来源、固定修订、许可和已知转换链限制见 `docs/THIRD_PARTY_NOTICES.md`。模型文件不进入 Git。

## 已做的开发检查

- Python 3.9 bytecode compilation for `pkb/evidence_review.py` and `pkb/review_measure.py`，使用 `/private/tmp` 作为 pycache。
- `sh -n scripts/build-reranker-logits.sh`。
- AppleClang C++17 严格编译，启用 `-Wall -Wextra -Werror`，成功链接本机 `libllama.dylib` 并产出 arm64 Mach-O。
- `git diff --check`。

这些是开发静态/构建检查，不是功能测试或模型推理测试。本开发任务没有启动候选模型、读取测试答案、选择阈值、运行浏览器、请求 DeepSeek 或出具质量结论。

## 独立测试接续

测试任务须固定最终通知的提交，在隔离检出和隔离数据目录中按 README 顺序运行两个候选，并保留全部失败：

1. 核对两个实际 GGUF 摘要、运行时版本、监听地址、进程参数、文件访问和非回环连接为零；审计量化发布者未提供完整可复现转换命令这一限制。
2. 使用相同的第一阶段召回结果，保留 S1 两套已知回归；0.6B 先校准再冻结阈值，4B 固定结构规则，不得合并两候选结果。
3. 冻结后运行至少 36 题独立盲测、关键样本三次重复、真实最终 6 片段/每文档 2 片段/正文预算以及本地浏览器流程。
4. 测量 40 候选、至少 20 次热态 p50/p95、冷启动、RSS/整体内存口径、memory pressure、压缩内存和 swap；持续压力时停止并记录。
5. 验证超时、服务缺失、输出错误、编号边界、否定答案、提示注入、引文伪造、晚到旧结果、资格/隐私变化、拒绝片段不进入外发确认以及 `cloud_requests=0`。

候选比较完成后仍需产品选择、最终实现、完整测试、审计和用户验收。若两个候选都失败，正式应用继续阻断且不自动下载第三个模型。
