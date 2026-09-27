# BUG-V11-003 离线记忆证据设计

## 目标

离线模拟回答必须同时展示 `Answers.context()` 已筛选出的资料片段和个人记忆。仅命中合格记忆时应显示该记忆；只有两类证据都为空时才显示无证据提示。

本次修复只改变 `MockProvider` 的本地文本渲染。真实云端 payload、逐次确认、隐私筛选、记忆资格规则、问答关联和外发记录结构保持不变。

## 证据输入边界

`MockProvider.answer(context)` 只使用传入的 `context['sources']` 与 `context['memories']`：

- `sources` 由 `Answers.context()` 在后端重新检索，并排除禁止外发资料。
- `memories` 由 `Memories.eligible()` 生成，只包含已确认、允许使用、无冲突、与问题匹配且关联来源仍允许使用的记忆。
- `MockProvider` 不重新查询数据库，也不复制或放宽筛选规则。
- 记忆正文和资料正文只作为文本展示，不解析 HTML，不执行其中的指令。

因此，`pending`、`conflicted`、`inactive`、`local` 或关联来源隐私已收紧的记忆不会进入离线模拟回答。

## 输出格式

所有分支以“【离线模拟，未调用模型】”开头，并保留“不是模型建议”的含义。

有资料片段时输出非空的“资料片段”区，每条使用独立编号：

```text
资料片段：
[资料 1] 资料正文
```

有个人记忆时输出非空的“个人记忆”区，每条同时显示主题：

```text
个人记忆：
[记忆 1｜蓝鹭项目会议纪要] 下一次评审时间为 2026 年 10 月 8 日上午 10 点
```

资料与记忆同时存在时依次展示两个区，编号在各自类型内从 1 开始。任一类型为空时不输出对应空标题。

两类证据都为空时输出：

```text
【离线模拟，未调用模型】没有符合当前使用条件的资料片段或个人记忆，无法生成有依据的回答；这不是模型建议。
```

该文案只说明当前问题与使用条件下没有合格证据，不暗示整个知识库不存在资料或记忆。

## 数据与网络行为

- `Answers.generate()` 继续在本机调用 `MockProvider`。
- 现有 `answer_sources` 与 `answer_memories` 关系继续记录本次实际使用的资料与记忆。
- 现有 `outbound.simulated=1` 记录语义保持不变，用于明确这是模拟记录。
- 离线模拟不调用 `DeepSeekProvider`，不写入 `cloud_requests`，不产生真实网络请求。
- 记忆修改、删除或来源隐私收紧时，既有清理逻辑继续通过 `answer_memories` 与标识关联清理旧回答和模拟记录。

## 文件范围

- `pkb/answers.py`：修改 `MockProvider.answer()`，分类型渲染已筛选证据。
- `docs/development-status.md`：记录验收暂停、根因与整改状态。
- `docs/development-testing-handoff.md`：登记固定版本的独立复测范围。
- `docs/deliveries/BUG-V11-003-development-fix.md`：记录根因、实现、安全边界与未验证项。
- 开发不修改或提交 `docs/testing/`、`docs/audit/`、`docs/acceptance/`。

## 独立复测范围

测试任务须覆盖仅记忆、仅资料、混合证据、完全无证据、所有不合格记忆类型、来源隐私收紧、主题与正文显示、模拟记录、`cloud_requests=0`，以及记忆修改或删除后的既有清理行为。测试完成后交审计复审；开发完成不代表问题关闭或恢复用户验收。
