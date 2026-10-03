# S2R1 带限定信息证据复核开发候选

日期：2026-10-03。产品规格提交：`bcf1672`。基线试验提交：`e1eff9c00680b7cb92b5bd0b4f8f5781d390c5d0`。

本交付只实现产品批准的一次 4B 通用提示修订与版本追踪。它不启用正式问答，不修改模型、量化、运行参数、JSON schema、业务编号门禁、引文核验或接受逻辑。

## 完整差异

1. `SYSTEM_PROMPT` 逐字替换为产品规格第 3 节固定英文正文。静态比对确认代码字符串与规格代码块完全一致。
2. 4B 模板版本从 `qwen3-instruct-evidence-json-v1` 更新为 `qwen3-instruct-qualified-evidence-json-s2r1-v1`。
3. 仅 4B 的管线版本更新为 `qualified-evidence-review-s2r1-v1`；0.6B 继续使用 `local-evidence-review-pilot-v1`，其配置签名算法和输入不变。
4. 固定提示 SHA256 为 `331b99aab10de919d6f6bc51d34d3f9615366c84349f572e25ae913417dd5d8f`，写入 4B reviewer settings 并进入配置签名与逐条测量输出。
5. `review_measure` 顶层报告对 4B 写入新的 S2R1 管线版本；0.6B 顶层版本保持原值。

按固定模型、量化、模板、管线、编号门禁和未变运行参数计算出的 S2R1 4B 配置签名为 `b5f609deee847b68da07c5ad4ff4dcd6729106f294ec4348151b97b73b9ae122`。

没有其他业务代码变化。

## 明确保留不变

- 模型：`Qwen3-4B-Instruct-2507 Q4_K_M`，SHA256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`。
- llama.cpp：0.5.0 / build 11146 / commit `7fe450e19`。
- 参数：context 8192、temperature 0、seed 1、max_tokens 384、非思考、零自动重试。
- JSON：只有 `verdict` 与 `evidence_quotes`，verdict 枚举不变。
- 接受：只有 `supported` 且至少一条非空引文能在实际正文逐字定位才结构性接受；`uncertain` 继续拒绝。
- 完整业务编号门禁、正文/问题限制、响应大小、超时、仅回环、禁代理/重定向和失败关闭均不变。
- 没有新增下载、第三模型、题目实体词表、阈值调整或正式库接线。

## 开发检查

- Python 3.9 bytecode compilation。
- 代码中的 `SYSTEM_PROMPT` 与产品规格固定代码块逐字相等。
- `git diff --check`。

开发没有启动模型，没有运行 cq05/c05、cq06/c06 或其他质量用例，没有读取正式资料库，没有执行浏览器测试或 DeepSeek 请求。模型质量、边界、回归、性能和资源测试由独立测试任务按规格第 4 节分阶段执行；首次硬失败即停止后续昂贵阶段。

## 测试与审计接续

测试须保留 `e1eff9c` 的全部旧输出，在独立目录固定本提交、模型摘要、提示摘要、配置签名、数据摘要和实际候选数。先运行产品规定的小规模限定语对照；全部正确才继续已知回归、已暴露 38 题、新盲测、稳定性和资源阶段。

审计须核对本提交只改变上述提示与追踪字段，接受门禁没有放宽；既有量化转换来源缺口继续开放。任何通过仅属于本固定 S2R1 配置，正式状态继续 `calibration_required`。
