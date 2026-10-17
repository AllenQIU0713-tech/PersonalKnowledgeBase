# Q6_K 非下载元数据补齐 v2

日期：2026-10-17（Asia/Shanghai）。结论：**补齐了一组可审计的 wheel 候选闭包与 CMake 发行件元数据，整体仍为 `approval_blocked`。** 产品代码候选保持 `391baf9db5afcffd8e2de4ba65782a05b6426a98`。本轮未执行产品或模型测试，未下载 wheel、模型权重、源码归档、安装件，未安装、构建、转换或启动模型。

本记录补充旧的 `S2-q6k-non-download-preparation-status.md`，不覆盖其历史记录或任何测试/审计材料。清单与日志由开发收集，须由审计独立复核。

## 本轮新增的可核对材料

| 项目 | 完成内容 | 边界 |
| --- | --- | --- |
| wheel 候选闭包 | 28 项，合计 **119,388,505 字节**；含运行依赖和本地 `gguf-py` 的 `poetry-core==2.5.0` 构建后端 | 目标为 CPython 3.12.15、macOS 26.5 arm64 的默认 extras；是元数据候选解，尚非获准安装锁 |
| 每项 wheel 身份 | 精确 index、URL、文件名、平台 tag、字节数、SHA-256、Requires-Python、完整 Requires-Dist、激活/排除的依赖边、发布者许可声明 | 未取得 wheel 正文；未核验包内捆绑组件或 LICENSE 文件 |
| 依赖声明来源 | 28 个选定 wheel 的 PEP 658 `.whl.metadata`，逐项与官方索引发布的 metadata SHA-256 比对 | 没有用其他平台 wheel 的依赖声明替代目标 wheel |
| CMake 发行件 | `cmake-3.31.8-macos-universal.tar.gz`，**78,373,419 字节**，SHA-256 `d1449f969c54d5c00886d5b643340d493dfb3c81cb39ee29b35453395c11ebf7` | 候选工具版本；只核对最低版本元数据，未验证构建兼容性；其捆绑许可待审 |
| Python 官方来源 | 3.12.15 发布文件 API、源码 SPDX SBOM、固定版本许可文本 | 官方 3.12.15 只提供源码；尚未选定实际构建解释器 |
| 原始收集证据 | `collect_metadata.py`、stdout/stderr、113 个 wheel/index/HEAD 请求记录、9 个工具/源码元数据记录及保存的原文 | 记录的是采集器的请求政策/回执，不是独立网络取证 |

机器可校验入口为本目录 `approval-inventory.json`，wheel 明细为 `wheel-inventory.json`，原始文本/JSON 在 `raw/`。`approval-inventory.json` 同时绑定原模型 manifest、wheel 清单、采集脚本与输出摘要。

## 索引差异与明确来源策略

固定 llama.cpp commit `7fe450e19305b828c199d602c23a8337aaa1f03b` 的 converter requirements 声明 PyTorch CPU extra index；本轮对 torch 明确只选该官方 CPU index，其余包明确只选 PyPI。此源策略需审计接受，不能在后续安装时重新让多个索引竞争同名文件。

同名 `torch-2.11.0-cp312-cp312-macosx_11_0_arm64.whl` 的两个来源内容不同：

| 来源 | 字节数 | SHA-256 | 本候选清单 |
| --- | ---: | --- | --- |
| PyTorch CPU index | 80,512,593 | `43b35116802c85fb88d99f4a396b8bd4472bfca1dd82e69499e5a4f9b8b4e252` | 选定 |
| PyPI | 80,606,338 | `4b5866312ee6e52ea625cd211dcb97d6a2cdc1131a5f15cc0d87eec948f6dd34` | 明确排除；仅保存差异记录 |

CPU 文件的大小取自该 URL 的 HEAD Content-Length；其依赖取自对应的 PEP 658 sidecar，不能套用 PyPI 文件的大小、摘要或 METADATA。两者差异没有被解释为质量或安全性结论。

固定源码中的 PyPI `gguf>=0.1.0` 条目按既有产品/审计要求由同 commit 的本地 `gguf-py==0.19.0` 替代。本轮闭包合并其四项运行依赖及 `poetry-core>=1.0.0` 构建依赖；未纳入 dev pytest、GUI PySide6 或未请求的 extras。所有激活依赖在目标 marker 环境中均由清单中的固定版本满足。采集使用现有系统 pip 自带 packaging 解析器，不安装解析工具。

## 解释器与工具链仍缺什么

旧记录中的 `/usr/bin/python3` 是 3.9.6；本轮另观察到已安装工具使用 `/Users/allenqiu/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/bin/python3.12`。路径和版本本身不能证明其发行件来源与完整性，因此没有把它作为获准构建 runtime。

[Python 3.12.15 官方发布页](https://www.python.org/downloads/release/python-31215/) 说明该版本只提供源码。官方 API 固定 `Python-3.12.15.tar.xz` 为 **20,829,824 字节**，SHA-256 `c2c4321961fab0fb999d66e0cecf521c2ab3994c7992873ea99e306c1094fd5a`；这里只记录未选定源码候选，并未获取归档或批准自行构建 Python。官方源码 SBOM 不等同于某个 macOS 二进制发行件的完整工具链/依赖证明。

后续须由产品确认实际解释器来源路线，再锁定对应发行件、bootstrap/安装前端、依赖、许可和预算。不能因 3.12.10 仍有官方安装件而自行退回旧版本，也不能默认为现有 3.12.13 路径已获来源批准。CMake 的官方 Copyright 文本说明另有捆绑第三方软件，当前主许可文本不能替代全部捆绑组件的许可审计。

## 预算与剩余阻断项

已知模型白名单 8,060,918,389 字节 + wheel 候选 119,388,505 字节 + CMake 候选 78,373,419 字节，小计 **8,258,680,313 字节**。这只是已知候选组件小计，**不是完整下载预算或可批准上限**；Python 源码候选没有计入，解释器路线、llama.cpp 源码传输、安装前端和其他工具尚未闭合。

仍缺：

1. 审计复核自定义 metadata-only 候选解、目标 marker、版本选择与显式索引来源策略，并接受可复现安装锁格式。
2. 对只有旧式 License 字段/分类器的记录补标准化 SPDX 结论，核对 wheel、CMake、Python 等实际捆绑组件许可覆盖；当前保存发布者原始声明，不伪称全部完成。
3. 确定实际 Python runtime、来源/摘要/许可证及 bootstrap/构建依赖；3.12.15 当前只是依赖 marker 目标。
4. 固定 llama.cpp 源码获取边界、传输字节/归档摘要、完整构建 argv/相关环境；源码 commit 已固定，归档正文未传输。
5. 根据上述选择完成分项下载/磁盘/构建资源预算，经审计后再向用户申请具体资源授权。

未来生成的二进制/动态库摘要仍只能在另获授权的构建后取得，并在转换/启动前交审计。隔离 Q6 测试配置及量化因果结论边界仍沿原计划；本轮没有修改 `pkb/evidence_review.py` 或正式配置。

## 采集与静态核对记录

执行命令保存在 `approval-inventory.json` 的 collector 字段；stdout/stderr 原样保留。采集器仅允许 PyPI JSON/simple index、PyTorch index、PEP 658 文本侧车与 torch HEAD，不允许 GET wheel。目标平台 tag 用已有 packaging 解析器计算，排除预发行、yanked、不兼容 tag/Requires-Python 及晚于本日的发行件。源文件中的范围约束按此规则形成当前固定候选解。

工具元数据另只读取 Python.org release-file JSON/SPDX、固定源码 requirements/pyproject/LICENSE、CMake 官方 SHA-256 文本与 Copyright，并仅 HEAD CMake 归档。对应 URL、时间、正文长度/摘要及原文路径在 `tool-metadata-receipts.json`。

静态核对检查了 28 项 sidecar 摘要、目标 Requires-Python、全部激活依赖约束、wheel/model 字节加总和请求回执中的 artifact body=0。另在 `target-marker-review.json` 中将采集时描述性 `platform_version` 标签换为实际主机 Darwin 版本文本，重新核对全部 32 条激活边，结果没有变化；原采集输出保留。没有运行应用、浏览器产品测试、模型或测试 oracle。采集脚本如需重跑，必须复制到新的版本目录，保留本目录字节供审计固定。

最初 browser-use 诊断显示本地 Chrome/daemon 连接不可用；后续采用获准的官方元数据请求。没有更新 browser-harness、安装软件或启用云浏览器。

## 权威来源

- [PyTorch CPU torch index](https://download.pytorch.org/whl/cpu/torch/)，含选定 wheel 与 PEP 658 metadata SHA。
- [PyPI Simple API 规范](https://docs.pypi.org/api/index-api/)，每个包的实际索引 URL 与 sidecar 摘要在 wheel 清单及回执中。
- [CMake 3.31.8 官方校验和](https://cmake.org/files/v3.31/cmake-3.31.8-SHA-256.txt)、[固定版 Copyright](https://raw.githubusercontent.com/Kitware/CMake/v3.31.8/Copyright.txt)。
- [Python 3.12.15 官方发行文件 API](https://www.python.org/api/v2/downloads/release_file/?release=1127)、[官方源码 SBOM](https://www.python.org/ftp/python/3.12.15/Python-3.12.15.tar.xz.spdx.json)。
- [固定 gguf-py pyproject](https://raw.githubusercontent.com/ggml-org/llama.cpp/7fe450e19305b828c199d602c23a8337aaa1f03b/gguf-py/pyproject.toml)。
