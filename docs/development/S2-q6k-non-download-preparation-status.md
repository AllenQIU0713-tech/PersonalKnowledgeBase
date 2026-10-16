# Q6_K 非下载审批材料准备状态

更新日期：2026-10-17

## 结论

Q6_K 来源状态继续为 **`approval_blocked`**。本次只做固定源码核对、构建主机信息读取和包索引元数据解析尝试；没有下载权重、wheel、源码归档或构建工具，没有构建/转换/启动模型，也没有运行模型测试。

目前不能可靠冻结完整的 macOS arm64 / Python 3.12 wheel SBOM、构建工具来源或分项下载预算。不得以现有版本范围、历史总量估算或此文档代替下载批准材料。

## 已核实的固定转换源码

固定 llama.cpp 提交仍是 `7fe450e19305b828c199d602c23a8337aaa1f03b`。该提交的官方文件显示：

- [`requirements-convert_hf_to_gguf.txt`](https://raw.githubusercontent.com/ggml-org/llama.cpp/7fe450e19305b828c199d602c23a8337aaa1f03b/requirements/requirements-convert_hf_to_gguf.txt) 使用 PyTorch CPU wheel extra index，并固定 `torch==2.11.0`。
- [`requirements-convert_legacy_llama.txt`](https://raw.githubusercontent.com/ggml-org/llama.cpp/7fe450e19305b828c199d602c23a8337aaa1f03b/requirements/requirements-convert_legacy_llama.txt) 对 NumPy、SentencePiece 和 Protobuf 保留范围约束，Transformers 固定为 `4.57.6`，并包含范围式 `gguf>=0.1.0`。
- 同一提交的 [`gguf-py/pyproject.toml`](https://raw.githubusercontent.com/ggml-org/llama.cpp/7fe450e19305b828c199d602c23a8337aaa1f03b/gguf-py/pyproject.toml) 将本地源码包版本定为 `0.19.0`，其运行依赖为 `numpy>=2.2.6`、`tqdm>=4.27`、`pyyaml>=5.1` 和 `requests>=2.25`。构建时必须使用这一固定提交中的源码，不另装 PyPI `gguf`。

以上确认了来源入口和直接约束，**不是**可安装锁文件。现有页面也没有提供目标平台上最终选中 wheel 的完整闭包和分项下载预算。

## 本机工具链快照

只读核对结果：

| 项目 | 当前值 | 审批材料缺口 |
| --- | --- | --- |
| 架构 | `arm64-apple-darwin25.6.0` | 已记录主机目标，需在构建 manifest 再次固定 |
| Apple Clang | `Apple clang 21.0.0 (clang-2100.1.1.101)` | 已安装，可固定使用 |
| Command Line Tools | `26.6.0.0.1781586589` | 已安装，可固定使用 |
| macOS SDK | `26.5` | 已安装，可固定使用 |
| Python | 系统 Python `3.9.6` | 不满足计划中的 Python 3.12；具体 arm64/universal2 发行件、URL、大小、SHA-256、许可证未锁定 |
| CMake | 未安装/不在 PATH | 需先选定兼容固定 llama.cpp 的版本及官方 macOS 发行件，并记录 URL、文件名、平台、字节、SHA-256、许可证 |
| `xcodebuild` | 完整 Xcode 未安装，当前 CLT 下不可用 | 若采用 CLT/SDK 工作流需在命令中明确；不能假称完整 Xcode 可用 |

构建产出的可执行文件和动态库摘要只能在获批构建后取得；它们应作为转换/模型启动前门槛，而不是下载批准前置条件。

## 无 wheel 下载的解析尝试

使用已安装 `uv 0.11.26`，将目标设为 Python 3.12、`aarch64-apple-darwin`，启用 `--no-build --generate-hashes`，并使用固定 requirements 中的 PyTorch CPU extra index进行依赖解析。缓存和临时输入/输出放在 `/private/tmp`，没有调用安装命令。

解析在索引访问阶段失败：DNS 无法解析 `download.pytorch.org/whl/cpu/numpy/`，重试后没有生成锁文件。此次尝试没有取得 wheel 或源码包；也没有覆盖本地 `gguf-py` 源码包，因此不构成完整解析结果。

## 尚缺材料

1. Python 3.12 / macOS arm64 的完整传递依赖锁：确定解析策略、包版本、marker 和来源索引，并纳入固定本地 `gguf-py`。
2. 对锁定闭包逐项选出目标平台实际 wheel：确切 URL/index、文件名、平台 tag、字节数、SHA-256、许可证/SPDX 标识；不能只记录 PyPI 版本或汇总所有平台文件的哈希。
3. Python 3.12 与兼容 CMake 的确切官方发行件及对应下载/安装预算。不得在构建时再使用 `latest` 或范围式安装。
4. llama.cpp 固定 commit 的来源获取方法、源码归档/传输上限及可验证摘要；清楚区分禁止克隆完整 Hugging Face 模型仓库与允许获取的固定转换工具源码。
5. 模型、工具源码、Python wheel、Python 运行时和 CMake 的逐项下载量与总预算。当前 `10–13 GB` 仍是估算，不可提交为精确批准上限。

## 下一步

在不传输包文件的前提下，先获得可用的索引元数据访问方式（PyPI 与 PyTorch CPU index，或经审计提供的等价元数据镜像），再针对固定平台执行可复现解析。对解析结果逐包查询官方发行元数据，锁定兼容 wheel 的 URL、tag、大小、摘要和许可证；再从 Python.org 与 CMake 官方发行页选择固定安装件，并为固定 llama.cpp commit 选定可审计的源码获取方案。完成后生成机器可校验的 SBOM/下载清单与分项预算，提交审计复核。上述步骤完成前不申请用户下载批准。
