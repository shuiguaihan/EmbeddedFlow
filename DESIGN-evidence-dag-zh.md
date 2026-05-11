# EmbeddedFlow 证据-DAG 架构设计

## 1. 产品定义

EmbeddedFlow 是一个项目本地的、AI Agent 优先的嵌入式产品软件工作流 CLI 工具，面向 Linux 嵌入式产品软件。它通过**证据-DAG**（有向无环图）执行模型，将真实需求转化为可追溯的目标设备证据。

核心洞察：**需求完成 = DAG 中所有证据约束都被满足**。EmbeddedFlow 不是让你按顺序走完一个线性阶段门禁流水线，而是将工作流视为一个图上的约束满足问题。

EmbeddedFlow 不是 Codex 专属工作流。Codex、Claude Code、Gemini CLI、OpenCode、OMX 以及其他 AI 编码终端仅仅是运行时入口。稳定的工作流核心是独立的 EmbeddedFlow CLI。

真正的服务对象是嵌入式产品软件开发者：那些负责安全、可追溯地将真实需求落地到目标设备上的人。直接操作者是 AI 编码 Agent。

---

## 2. v0.1 范围

v0.1 聚焦于 Linux 嵌入式产品软件。

### v0.1 真实边界

本节取代本文其余位置当前设计中的过度承诺：v0.1 是本地 shell + manual 的 Evidence-DAG MVP，并提供模拟 EXM-K 参考。SSH 远程执行、SCP 远程产物拉取、真实 EXM-K 板/VM smoke、CANSim、target automation、`agent_task`、`python` Recipe 和 `--jobs` 都是面向未来的路线图项，不是 v0.1 就绪标准。Git status、commit 和 tag 不是产品就绪标准。

范围内：

- 项目本地工作流状态，采用只追加事件日志
- 证据-DAG 执行模型，支持增量重执行
- 需求接入与声明式证据约束
- Recipe 系统（v0.1 支持 shell 和 manual 两种类型）
- DAG 构建、拓扑排序、有效性检查
- 基于内容哈希的证据失效，支持传递性级联
- 拉取式（pull-based）AI 上下文 API（`ef context`）
- 测试设计和最终验收的人工审批门禁
- 监视文件的源码哈希计算
- 基于 Profile 的目标配置与模板变量展开
- 模拟 EXM-K 风格项目集成作为第一个参考 smoke

范围外（v0.1 不做）：

- RTOS、MCU、裸机、HIL、JTAG、烧录、上电循环等抽象
- `cansim` Recipe 类型（内置 CANSimService HTTP 执行器）
- `target_automation` Recipe 类型（内置 ZMQ 桥接）
- `agent_task` Recipe 类型（结构化 AI 提示/响应协议）
- `python` Recipe 类型（插件式 Recipe）
- 并行执行（`--jobs N`）
- 知识库提供者集成
- 全局托管工作流服务
- 自动知识库生成和维护
- CANSimService 安装或守护进程生命周期管理
- 默认生成大型流程文档

---

## 3. 设计原则

- **证据优先**：完成状态由证据约束定义，而非阶段推进。
- **DAG 优于流水线**：依赖关系是显式的有向边，不是隐式的排序。
- **增量执行**：只重新执行证据过期或缺失的 Recipe（类 Make 行为）。
- **拉取优于推送**：AI Agent 按需拉取上下文，而非接收预构造的数据包。
- **CLI 核心优先**：核心工作流是独立 CLI，不是 Codex、OMX 或 Claude 的专属功能。
- **项目本地状态**：每个产品项目在自己的目录中存储工作流数据。
- **AI 运行时无关**：AI 运行时集成是 CLI 之上的薄包装。
- **内容哈希有效性**：证据有效性由内容哈希决定，而非时间戳。
- **只追加审计轨迹**：所有证据事件不可变；状态从事件日志中推导。
- **Recipe 优于 Adapter**：简单的 YAML Recipe 定义取代沉重的 Adapter 类层次结构。
- **源码验证必需**：知识库和先前结论永远不能替代源码检查。
- **最小数据模型**：三个核心概念（需求、Recipe、证据）取代复杂的对象层次。
- **测试设计是硬依赖**：验证节点在测试设计被生成且审批通过之前不能执行。
- **Linux 嵌入式优先**：v0.1 先做好 Linux 嵌入式产品交付，再扩展到其他平台。

---

## 4. 架构

```text
AI 编码 Agent
  Codex / Claude Code / Gemini CLI / OpenCode / OMX
        |
        v
AI 运行时适配器（薄包装）
        |
        v
EmbeddedFlow CLI 核心
        |
        +--> DAG 引擎
        |      +--> DAG 构建器（需求 + Recipe → 图）
        |      +--> 拓扑排序器（Kahn 算法）
        |      +--> 有效性检查器（source_hash、recipe_hash、依赖有效性）
        |      +--> 失效级联器（传递性过期标记）
        |      +--> 执行规划器（跳过有效节点，执行过期/缺失节点）
        |
        +--> Recipe 执行器
        |      +--> Shell 执行器（本地 subprocess；远程 SSH 延后）
        |      +--> Manual 执行器（人工门禁，阻塞等待审批）
        |      +--> Cansim 执行器（v0.2：CANSimService HTTP 客户端）
        |      +--> TargetAutomation 执行器（v0.2：ZMQ 桥接）
        |      +--> AgentTask 执行器（v0.2：结构化 AI 提示/响应）
        |      +--> Python 插件执行器（v0.2：importlib 动态加载）
        |
        +--> 证据存储（只追加 JSONL 事件日志）
        |
        +--> 上下文 API（拉取式，结构化 YAML/JSON 输出）
        |
        +--> 配置加载器（ef.yaml、profile.yaml、local.env.yaml）
        |
        +--> 模板引擎（Recipe 中的 {{variable}} 展开）
        |
        +--> 源码哈希器（监视文件内容的 SHA-256）
        |
        +--> 知识库提供者（v0.2：可选，card_kb / markdown_index / none）
```

CLI 核心负责 DAG 构建、有效性检查、执行规划、证据记录和上下文生成。

AI 运行时适配器可以：

- 调用 EmbeddedFlow CLI 命令
- 通过 `ef context` 读取上下文
- 通过 `ef recipe complete` 报告证据
- 通过 `ef what-next` 查询下一步操作

AI 运行时适配器不得：

- 成为工作流的真相来源
- 存储规范证据状态
- 硬编码项目特定的目标行为
- 要求特定 AI 平台才能运行工作流

---

## 5. 核心概念

EmbeddedFlow 仅有三个核心概念。其他一切都是派生的。

### 5.1 需求（Requirement）

需求声明**完成一项工作需要什么证据**。它不描述如何产出这些证据。

下面的 YAML 是未来目标设备 EXM-K 形态，不是模拟 v0.1 基线。v0.1 已检入的参考在 `examples/exm-k`，节点为 `test_design -> build -> deploy -> human_review.final`，且没有 `remote: true`。

```yaml
# .ef/requirements/REQ-EXM-FUEL-GAUGE-001.yaml
id: REQ-EXM-FUEL-GAUGE-001
title: "燃油表 UI 响应 CAN 油量信号变化"
source: "EXM-K/TODO.md#需求-X"
scope: "EXM-K 板端验证 / 燃油表状态"

# 完成此需求必须满足的证据
evidence:
  - test_design
  - build
  - deploy
  - verify.can_stimulus
  - verify.screenshot
  - verify.comparison
  - verify.log
  - human_review.final

# 源文件：这些文件的变更会使 build 及下游证据失效
watch:
  - "EXM-K/src/UI/MainPanel/DashBoardFuelLevel.cpp"
  - "EXM-K/src/UI/MainPanel/DashBoardFuelLevel.h"
  - "EXM-K/src/UILogic/communication/CANBus/FuelLevelHandler.cpp"

tags:
  - board-verify
  - fuel-gauge
  - cansim
```

### 5.2 Recipe（配方）

Recipe 声明**如何产出**一个特定的证据节点。它指定对其他证据节点的依赖、执行方式和产出物。

下面的远程 build Recipe 是路线图设计。v0.1 使用本地 shell Recipe；`remote: true` 会被拒绝。

```yaml
# .ef/recipes/build.yaml
id: build
type: shell
description: "在构建 VM 上使用 qmake 交叉编译 EXM-K（ARM Cortex-A7）"

depends_on: []

watch:
  - "EXM-K/**/*.cpp"
  - "EXM-K/**/*.h"
  - "EXM-K/**/*.pro"
  - "EXM-K/**/*.qrc"
  - "EXM-K/**/*.ui"

target: vm
remote: true

env:
  STAGING_DIR: "{{local_env.build_env.env_exports.STAGING_DIR}}"

working_dir: "{{local_env.build_env.build_workdir_override}}"

command: |
  {{local_env.build_env.qmake_path}} ../../EXM-K.pro
  make -j4

produces:
  - artifact: "{{profile.build.artifact_path}}"
    type: arm-elf
    label: binary
  - log: build.log
    type: build_log
    capture: stdout+stderr

timeout: 300
```

### 5.3 证据（Evidence）

证据事件记录一个 Recipe 被执行了、产出了什么、是否通过。证据以只追加事件日志的形式存储。

```jsonl
{"ts":"2026-04-30T10:00:00Z","event":"produced","node":"build","req":"REQ-EXM-FUEL-GAUGE-001","run":"ef-20260430-001","recipe":"build","status":"pass","duration_s":42,"artifacts":["build.log","EXM-K/build/kilo/EXM-K"],"source_hash":"a1b2c3d4e5f6","recipe_hash":"7890abcd"}
```

---

## 6. 证据-DAG 执行模型

### 6.1 DAG 构建

当执行 `ef satisfy <req-id>` 时：

1. **加载需求**：解析 `.ef/requirements/<req-id>.yaml`，提取 `evidence` 列表
2. **加载 Recipe**：对每个证据 ID，加载 `.ef/recipes/<id>.yaml`
3. **构建图**：对每个 Recipe 的 `depends_on`，添加有向边 `依赖 → 被依赖`
4. **解析传递闭包**：如果 Recipe A 依赖 B，B 依赖 C，则即使需求未显式列出 C 也要包含
5. **验证图**：检查环（错误）、缺失 Recipe（错误）、孤立节点（警告）

示例：v0.1 模拟 `REQ-EXM-FUEL-GAUGE-001` 参考产生如下本地/manual DAG：

```text
┌──────────────┐
│ test_design  │（manual，review: required）
└──────┬───────┘
       v
┌──────────────┐
│    build     │（本地 shell）
└──────┬───────┘
       v
┌──────────────┐
│    deploy    │（本地 shell）
└──────┬───────┘
       v
┌────────────────────┐
│ human_review.final │（manual，review: required）
└────────────────────┘
```

依赖关系（边）：
- build 依赖：[test_design]
- deploy 依赖：[build]
- human_review.final 依赖：[deploy]

未来目标设备 DAG 可以在 v0.2+ 的 CANSim 和 target automation 落地后加入 `verify.can_stimulus`、`verify.screenshot`、`verify.comparison` 和 `verify.log`。

### 6.2 拓扑排序与并行检测

使用 Kahn 算法（基于 BFS）。每次迭代中入度为 0 的节点形成一个"层级"——同一层级内的节点无相互依赖，可以并行执行。

```text
Level 0：test_design
Level 1：build
Level 2：deploy
Level 3：human_review.final
```

### 6.3 有效性检查算法

对每个证据节点，判断已有证据是否仍然有效：

```python
def is_valid(node_id: str, evidence_store: EvidenceStore, recipes: dict, hasher: SourceHasher) -> bool:
    """
    一个证据节点有效，当且仅当：
    1. 它有一个 status='pass' 的 'produced' 事件，且未被 'invalidated' 事件取代
    2. 产出时的 source_hash 与当前源码哈希匹配
    3. 产出时的 recipe_hash 与当前 Recipe 哈希匹配
    4. depends_on 中的所有节点本身也有效
    """
    latest = evidence_store.latest_event(node_id)

    # 从未产出过，或已被显式失效
    if latest is None:
        return False
    if latest.event == "invalidated":
        return False
    if latest.event == "failed":
        return False
    if latest.status != "pass":
        return False

    # 检查 Recipe 是否需要审批且审批尚未通过
    recipe = recipes[node_id]
    if recipe.review == "required":
        review_event = evidence_store.latest_review(node_id)
        if review_event is None or review_event.status != "accepted":
            return False

    # 检查源码哈希（监视文件是否变更？）
    if recipe.watch:
        current_hash = hasher.compute(recipe.watch)
        if current_hash != latest.source_hash:
            return False

    # 检查 Recipe 哈希（Recipe 定义是否变更？）
    current_recipe_hash = hasher.compute_recipe(recipe)
    if current_recipe_hash != latest.recipe_hash:
        return False

    # 检查所有依赖是否有效（传递性）
    for dep_id in recipe.depends_on:
        if not is_valid(dep_id, evidence_store, recipes, hasher):
            return False

    return True
```

### 6.4 失效级联

当源文件变更时，失效沿 DAG 传递性扩散：

```text
源文件 examples/exm-k/src/fuel_gauge.txt 被修改
  -> build 监视 "src/**/*.txt" -> build 过期
    -> deploy 依赖 [build] -> deploy 过期
      -> human_review.final 依赖 [deploy] -> 过期
```

失效是惰性计算的（在 `ef status` 或 `ef satisfy` 时通过遍历 DAG 检查哈希），不是主动的（不需要文件监视守护进程）。

### 6.5 增量执行（类 Make）

`ef satisfy` 只对**无效**的节点执行 Recipe：

```text
$ ef satisfy REQ-EXM-FUEL-GAUGE-001

[skip]  test_design              review accepted
[run]   build                    stale
[run]   deploy                   depends on stale node
[run]   human_review.final       depends on stale node
[wait]  human_review.final       review required: ef review human_review.final REQ-EXM-FUEL-GAUGE-001 --accept --rationale <text>
```

如果上次成功运行后没有任何变更：

```text
$ ef satisfy REQ-EXM-FUEL-GAUGE-001

所有证据均为最新。REQ-EXM-FUEL-GAUGE-001 已满足。
```

### 6.6 部分执行与恢复

如果执行被中断（网络故障、手动中止），下次 `ef satisfy` 会从中断处恢复——已经产出的证据仍然有效（假设没有源码变更），只有剩余节点会被执行。

### 6.7 强制重新执行

```bash
ef satisfy REQ-EXM-FUEL-GAUGE-001 --force build
```

强制 `build` 节点重新执行，即使有效。所有依赖 `build` 的节点也会重新执行（因为它们的依赖现在过期了）。

---

## 7. Recipe 系统

### 7.1 Recipe 类型

| 类型 | 执行器 | v0.1 | 描述 |
|------|--------|------|------|
| `shell` | 本地 subprocess | 是 | 运行本地 shell 命令；v0.1 会拒绝 `remote: true` |
| `manual` | 阻塞，等待 `ef review` | 是 | 人工门禁 |
| `cansim` | 内置 HTTP 客户端 | v0.2 | CANSimService 激励注入 |
| `target_automation` | 内置 ZMQ 客户端 | v0.2 | 板端 UI 自动化 |
| `agent_task` | 结构化标准输出协议 | v0.2 | AI Agent 生成证据 |
| `python` | importlib 动态加载 | v0.2 | 通过 Python 插件实现复杂逻辑 |

### 7.2 Shell Recipe — 本地执行

```yaml
id: verify.comparison
type: shell
description: "逐像素比较低油位和高油位截图"
depends_on: [verify.screenshot]

command: |
  python3 scripts/compare_screenshots.py \
    {{artifacts.verify.screenshot.screenshot_fuel_low.png}} \
    {{artifacts.verify.screenshot.screenshot_fuel_high.png}} \
    --output comparison_report.json \
    --threshold 0.05

produces:
  - artifact: comparison_report.json
    type: comparison_result
  - log: comparison.log
    type: comparison_log
    capture: stdout+stderr
```

### 7.3 Shell Recipe — 未来远程执行（SSH，延后）

以下远程 Recipe 形态仅作为路线图设计保留。v0.1 中 `remote: true` 会非零退出，错误包含 `remote shell recipes are not implemented in this v0.1 slice`，且不得记录通过证据。

```yaml
id: build
type: shell
description: "在构建 VM 上通过 qmake 交叉编译 EXM-K"

depends_on: []

watch:
  - "EXM-K/**/*.cpp"
  - "EXM-K/**/*.h"
  - "EXM-K/**/*.pro"
  - "EXM-K/**/*.qrc"
  - "EXM-K/**/*.ui"
  - "EXM-K/**/*.pri"

# 在 profile 中定义的 VM 目标上远程执行
target: vm
remote: true

env:
  STAGING_DIR: "{{local_env.build_env.env_exports.STAGING_DIR}}"

working_dir: "{{local_env.build_env.build_workdir_override}}"

command: |
  {{local_env.build_env.qmake_path}} ../../EXM-K.pro
  make -j4

produces:
  - artifact: "{{profile.build.artifact_path}}"
    type: arm-elf
    label: binary
    copy_to_local: true
    local_path: ".ef/artifacts/{{req.id}}/build/EXM-K"
  - log: build.log
    type: build_log
    capture: stdout+stderr

timeout: 300
on_failure:
  capture: [stdout, stderr, make_error_log]
```

### 7.4 Shell Recipe — 未来多步骤部署（SSH/SCP，延后）

该板端部署 Recipe 仅作为路线图设计保留。它依赖 SSH 远程执行和 SCP 产物传输，两者均不属于 v0.1；v0.1 模拟 EXM-K 参考使用本地 shell copy 命令。

```yaml
id: deploy
type: shell
description: "通过 SSH 将 EXM-K 二进制部署到目标板"

depends_on: [build]

target: board
remote: true

steps:
  - name: stop_existing
    command: "killall EXM-K 2>/dev/null || true"
    post_wait_seconds: "{{profile.deploy.stop_wait_seconds}}"
    ignore_failure: true

  - name: backup_current
    command: |
      if [ -f {{profile.deploy.deploy_dir}}/EXM-K ]; then
        cp {{profile.deploy.deploy_dir}}/EXM-K {{profile.deploy.deploy_dir}}/EXM-K.bak
      fi
    ignore_failure: true

  - name: copy_binary
    type: scp
    src: "{{artifacts.build.binary}}"
    dst: "{{profile.deploy.copy_targets[0].dst}}"
    mode: "755"

  - name: start_application
    command: "{{profile.deploy.start_command}}"

  - name: health_check
    command: "{{profile.deploy.health_checks | join(' && ')}}"
    retry:
      max_attempts: 8
      interval_seconds: 5
    timeout: "{{profile.deploy.startup_timeout_seconds}}"

produces:
  - log: deploy.log
    type: deploy_log
    capture: all_steps
  - status: health_result
    type: health_check
    fields:
      process_running: bool
      log_file_exists: bool
      startup_time_seconds: float
```

### 7.5 CANSim Recipe（v0.2）

```yaml
id: verify.can_stimulus
type: cansim
description: "通过 CANSimService HTTP API 注入燃油表 CAN 信号"

depends_on: [deploy, test_design]

cansim:
  host: "{{resolved.cansim.host}}"
  port: "{{resolved.cansim.port}}"
  transport: http
  timeout_seconds: 10

  # 激励前的预检
  pre_checks:
    - endpoint: /health
      expect: {"status": "ok"}
    - endpoint: /channels
      expect_contains: "{{profile.verify.cansim_channel}}"

  # 按顺序执行的激励动作
  actions:
    - type: signals_set
      label: fuel_low
      source: "{{profile_dir}}/cansim_sequences/fuel_level_low.signals.json"
      settle_ms: 2500
      capture_trigger: true

    - type: signals_set
      label: fuel_high
      source: "{{profile_dir}}/cansim_sequences/fuel_level_high.signals.json"
      settle_ms: 2500
      capture_trigger: true

    - type: sequence_run
      label: full_sweep
      source: "{{profile_dir}}/cansim_sequences/fuel_gauge_sweep.sequence.json"
      wait_for_completion: true

  # 激励后清理
  post_cleanup:
    - endpoint: /periodic/stop
      method: POST

produces:
  - log: cansim_stimulus.log
    type: stimulus_record
    fields:
      frames_sent: int
      sequences_completed: int
      errors: list
  - artifact: stimulus_results.json
    type: stimulus_evidence
    contains: all_request_response_pairs
```

### 7.6 目标自动化 Recipe（v0.2）

```yaml
id: verify.screenshot
type: target_automation
description: "通过 TestAutomation ZMQ 桥接捕获板端截图"

depends_on: [verify.can_stimulus]

target_automation:
  board: "{{profile.targets.board}}"
  command_port: 5661
  reply_port: 7661
  topic: "/BROKER/EXM/TestAutomation/Command"
  reply_topic: "/BROKER/EXM/TestAutomation/Reply"
  timeout_ms: 5000
  ssh_tunnel: true

  actions:
    - cmd: goto_page
      args:
        page_id: main_panel
      expect_reply: true

    - cmd: wait_stable
      args:
        duration_ms: 2000
      expect_reply: false

    - cmd: capture_screenshot
      args:
        label: fuel_current_state
        format: png
      expect_reply: true
      pull_artifact: true
      remote_path: "/tmp/screenshot_*.png"

produces:
  - artifact: "screenshot_*.png"
    type: board_screenshot
    multiple: true
  - log: target_automation.log
    type: automation_log
    fields:
      commands_sent: int
      replies_received: int
      screenshots_captured: int
      errors: list
```

### 7.7 Agent Task Recipe（v0.2）

```yaml
id: test_design
type: agent_task
description: "AI Agent 为需求验证生成测试设计"

depends_on: []

review: required

agent_task:
  # Agent 应使用的上下文查询
  context_query: "ef context {{req.id}} --need test_design --format json"

  # 给 AI Agent 的指令
  instructions: |
    你正在为需求 {{req.id}}: {{req.title}} 设计测试方案。

    步骤：
    1. 阅读需求 watch 列表中的源文件
    2. 识别影响此 UI 元素的 CAN 信号
    3. 定义激励输入（CAN 帧、信号值、时序）
    4. 定义观察点（UI 元素、日志模式、截图）
    5. 定义通过/失败判定标准
    6. 定义自动化 vs 手动分工
    7. 识别已知空白和风险

    输出格式：遵循 test_design_v1 schema 的 YAML。
    源码验证：必需 - 必须对照实际源代码验证所有假设。

  # 预期输出 schema
  output_schema: test_design_v1

  # 输出写入路径
  output_path: ".ef/artifacts/{{req.id}}/test_design/test_design.yaml"

  # 源码验证策略
  source_verification: required

produces:
  - document: test_design.yaml
    type: test_design
    schema: test_design_v1
    must_contain:
      - stimulus
      - observations
      - pass_criteria
      - automation_plan
```

### 7.8 Manual Recipe（人工门禁）

```yaml
id: human_review.final
type: manual
description: "所有验证证据的人工最终验收"

depends_on:
  - verify.can_stimulus
  - verify.screenshot
  - verify.comparison
  - verify.log

manual:
  # 展示给审查者的内容
  prompt: |
    审查 {{req.id}}: {{req.title}} 的证据

    已收集的证据：
    - 构建：{{artifacts.build.log}}（{{evidence.build.status}}）
    - 部署：{{artifacts.deploy.log}}（{{evidence.deploy.status}}）
    - CAN 激励：{{artifacts.verify.can_stimulus.log}}（{{evidence.verify.can_stimulus.status}}）
    - 截图：{{artifacts.verify.screenshot.artifacts}}
    - 比对：{{artifacts.verify.comparison.artifact}}
    - 板端日志：{{artifacts.verify.log.artifact}}

    决定：接受或拒绝，并说明理由。

  # 审查者必须填写的字段
  fields:
    - name: status
      type: enum
      values: [accepted, rejected, conditional]
      required: true
    - name: reviewer
      type: string
      required: true
    - name: rationale
      type: text
      required: true
    - name: conditions
      type: text
      required_if: "status == conditional"
    - name: reviewed_at
      type: timestamp
      auto: true

  # 等待审查的超时时间
  timeout: null  # 无超时，无限等待

produces:
  - document: acceptance.yaml
    type: human_acceptance
```

### 7.9 Recipe 模板变量

Recipe 支持 Jinja2 风格的模板变量，在执行时解析：

| 变量命名空间 | 来源 | 示例 |
|---|---|---|
| `{{profile.*}}` | `.ef/profiles/<id>/profile.yaml` | `{{profile.build.artifact_path}}` |
| `{{local_env.*}}` | `.ef/profiles/<id>/local.env.yaml` | `{{local_env.targets.board.host}}` |
| `{{req.*}}` | 当前需求 | `{{req.id}}`、`{{req.title}}` |
| `{{resolved.*}}` | 运行时解析的值 | `{{resolved.cansim.host}}` |
| `{{artifacts.<node>.*}}` | 依赖节点的产物 | `{{artifacts.build.binary}}` |
| `{{evidence.<node>.*}}` | 依赖节点的证据状态 | `{{evidence.build.status}}` |
| `{{profile_dir}}` | Profile 目录路径 | `.ef/profiles/exm-k/` |
| `{{project_root}}` | 项目根目录 | `/mnt/d/Monster_Liu/code/work_code/exm-k-2024` |

---

## 8. 证据存储

### 8.1 存储格式

证据存储是位于 `.ef/evidence.jsonl` 的单个文件。每行是一个自包含的 JSON 事件。此设计支持：

- **审计轨迹**：所有证据产出和失效的完整历史
- **回放**：可以重建任意时间点的状态
- **只追加安全**：无就地修改，无数据丢失
- **简单实现**：不需要数据库，只需文件追加

### 8.2 事件 Schema

```typescript
interface EvidenceEvent {
  ts: string;           // UTC ISO-8601 时间戳
  event: "produced" | "invalidated" | "reviewed" | "failed" | "skipped";
  node: string;         // 证据节点 ID（与 Recipe ID 匹配）
  req: string;          // 需求 ID
  run: string;          // 运行标识（将一次 ef satisfy 调用的事件分组）

  // 'produced' 事件：
  recipe?: string;      // 产出它的 Recipe
  status?: "pass" | "fail" | "blocked";
  duration_s?: number;  // 执行时间
  artifacts?: string[]; // 产出文件的相对路径
  source_hash?: string; // 产出时监视源文件的 SHA-256
  recipe_hash?: string; // 产出时 Recipe 定义的 SHA-256
  depends?: string[];   // 产出时有效的 "node@hash" 依赖列表

  // 'invalidated' 事件：
  reason?: "source_changed" | "recipe_changed" | "dependency_invalidated" | "manual";
  changed_files?: string[];
  old_hash?: string;
  new_hash?: string;

  // 'reviewed' 事件：
  reviewer?: string;
  review_status?: "accepted" | "rejected" | "conditional";
  rationale?: string;
  conditions?: string;

  // 'failed' 事件：
  error?: string;
  exit_code?: number;
  stderr_tail?: string; // stderr 最后 500 字符
}
```

### 8.3 状态推导

当前状态通过扫描每个节点的事件日志推导：

```python
def current_status(node_id: str, req_id: str) -> str:
    """
    从事件日志推导当前状态。
    返回：'valid' | 'stale' | 'missing' | 'failed' | 'pending_review' | 'rejected'
    """
    events = filter(evidence_log, node=node_id, req=req_id)
    if not events:
        return 'missing'

    latest = events[-1]  # 此节点+需求的最新事件

    if latest.event == 'invalidated':
        return 'stale'
    if latest.event == 'failed':
        return 'failed'
    if latest.event == 'produced':
        if latest.status == 'pass':
            # 检查是否需要审批但尚未完成
            recipe = load_recipe(node_id)
            if recipe.review == 'required':
                review = latest_review_event(node_id, req_id, after=latest.ts)
                if review is None:
                    return 'pending_review'
                if review.review_status == 'rejected':
                    return 'rejected'
            # 检查当前哈希（惰性失效）
            if not hashes_still_match(latest, recipe):
                return 'stale'
            return 'valid'
        return 'failed'

    return 'missing'
```

### 8.4 源码哈希计算

```python
import hashlib
from pathlib import Path
from fnmatch import fnmatch

def compute_source_hash(watch_patterns: list[str], project_root: Path) -> str:
    """
    计算所有匹配监视模式文件的 SHA-256 哈希。
    文件按路径排序以保证确定性顺序。
    """
    matched_files = []
    for pattern in watch_patterns:
        for path in project_root.rglob("*"):
            if path.is_file() and fnmatch(str(path.relative_to(project_root)), pattern):
                matched_files.append(path)

    matched_files.sort()

    hasher = hashlib.sha256()
    for path in matched_files:
        # 将相对路径纳入哈希（检测重命名）
        rel = str(path.relative_to(project_root))
        hasher.update(rel.encode())
        hasher.update(path.read_bytes())

    return hasher.hexdigest()[:12]  # 12 字符前缀，便于阅读
```

### 8.5 Recipe 哈希计算

```python
def compute_recipe_hash(recipe_path: Path) -> str:
    """
    计算 Recipe YAML 内容的 SHA-256。
    忽略注释和空白规范化以保持稳定性。
    """
    import yaml
    content = yaml.safe_load(recipe_path.read_text())
    # 规范化为 canonical JSON 以保证哈希稳定性
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
```

---

## 9. CLI 命令面

### 9.1 命令参考

```bash
# 项目初始化
ef init [--profile <id>]
    创建 .ef/ 目录及默认结构。
    如指定 --profile，复制对应的起始 Profile 模板。

# 核心执行
ef satisfy <req-id> [--dry-run] [--force <node>] [--continue-on-error]
    为需求构建 DAG，执行所有过期/缺失的 Recipe。
    --dry-run：显示执行计划但不运行。
    --force <node>：强制重新执行指定节点。
    --continue-on-error：首次失败不停止。

v0.1 后延后：`--profile <id>` 执行选择和 `--jobs N` 并行执行。

# 状态与检查
ef status [<req-id>] [--all]
    显示一个或所有需求的证据状态。
    逐节点显示：valid/stale/missing/failed/pending_review。

ef dag <req-id> [--format text|dot|json]
    可视化证据 DAG。
    text：带状态颜色的 ASCII 树。
    dot：Graphviz DOT 语言输出。
    json：机器可读的图结构。

ef what-next <req-id>
    基于当前 DAG 状态建议下一步操作。
    输出：可执行的指令，包含 ef 命令。

# AI Agent 接口（拉取式上下文）
ef context <req-id> [--need <node-id>] [--format markdown|json]
    AI Agent 的拉取式上下文 API。
    不带 --need：完整需求上下文，含 DAG 状态。
    带 --need：仅返回产出特定证据所需的上下文。

# 证据管理
ef evidence list [<req-id>] [--status valid|stale|failed|all] [--node <id>]
    列出证据事件，支持过滤。

ef evidence show <node-id> <req-id>
    显示证据节点的完整详情：最新事件、产物、哈希。

ef evidence invalidate <node-id> <req-id> [--reason <text>]
    手动使一个证据节点失效。级联到下游依赖。

# Recipe 管理
ef recipe list [--type shell|manual|cansim|...]
    列出所有可用 Recipe，含类型、依赖、描述。

ef recipe run <recipe-id> <req-id> [--force]
    直接执行单个 Recipe，绕过 DAG satisfy 流程。

ef recipe complete <recipe-id> <req-id> --artifact <path> --status pass|fail
    报告外部执行的 Recipe 完成（供 AI Agent 使用）。

# 人工审批
ef review <node-id> <req-id> --accept|--reject [--reviewer <name>] [--rationale <text>]
    记录人工审批决定。

# Profile 管理
ef profile list
    列出可用 Profile。

ef profile show <profile-id>
    显示 Profile 配置，含已解析的模板变量。

# 运行历史
ef run list [--limit N]
    列出最近的 ef satisfy 运行，含时间戳和结果。

ef run show <run-id>
    显示特定运行的所有证据事件。
```

### 9.2 使用示例会话

这个 v0.1 示例使用已检入的模拟 EXM-K 参考。它只依赖本地执行：不需要 `--profile`、SSH、VM、真实板端、CANSim、target automation 或 `agent_task`。

```bash
# 查看模拟需求的 DAG
$ ef dag REQ-EXM-FUEL-GAUGE-001 --format json
{
  "levels": [
    ["test_design"],
    ["build"],
    ["deploy"],
    ["human_review.final"]
  ]
}

# 只查看计划，不产出证据
$ ef satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run
[run]   test_design              missing
[run]   build                    missing
[run]   deploy                   missing
[run]   human_review.final       missing

# 执行本地/manual Recipe
$ ef satisfy REQ-EXM-FUEL-GAUGE-001
[run]   test_design              missing
[wait]  test_design              review required: ef review test_design REQ-EXM-FUEL-GAUGE-001 --accept --rationale <text>
[run]   build                    missing
[run]   deploy                   missing
[run]   human_review.final       missing
[wait]  human_review.final       review required: ef review human_review.final REQ-EXM-FUEL-GAUGE-001 --accept --rationale <text>

# review: required 的 manual 节点必须带 rationale
$ ef review test_design REQ-EXM-FUEL-GAUGE-001 --accept --reviewer qa --rationale "simulated test design reviewed"
Recorded review for test_design REQ-EXM-FUEL-GAUGE-001: accepted

$ ef review human_review.final REQ-EXM-FUEL-GAUGE-001 --accept --reviewer qa --rationale "simulated build and deploy evidence reviewed"
Recorded review for human_review.final REQ-EXM-FUEL-GAUGE-001: accepted

$ ef status REQ-EXM-FUEL-GAUGE-001 --format json
{
  "satisfied": true,
  "nodes": {
    "test_design": {"status": "valid"},
    "build": {"status": "valid"},
    "deploy": {"status": "valid"},
    "human_review.final": {"status": "valid"}
  }
}
```

包含 VM 构建、板端部署、CANSim、target automation、截图和板端日志的真实目标示例属于 v0.2+ 路线图章节，不是 v0.1 验收示例。

---

## 10. AI Agent 接口（拉取式上下文）

### 10.1 设计哲学

与 CodexFlow 推送式数据包系统的根本区别：

| 方面 | CodexFlow（推送） | EmbeddedFlow（拉取） |
|------|------------------|---------------------|
| 上下文交付 | Agent 启动前预构造数据包 | Agent 执行期间按需查询 |
| 信息量 | 固定，可能过多或过少 | 恰好是 Agent 请求的 |
| 过时性 | 数据包在执行期间可能过时 | 查询时始终是最新的 |
| Agent 自主性 | Agent 遵循数据包指令 | Agent 自行决定查询什么 |

### 10.2 完整上下文查询

```bash
$ ef context REQ-EXM-FUEL-GAUGE-001 --format json
```

返回当前本地项目数据。v0.1 的 context 输出格式是 JSON 或 Markdown，模拟 EXM-K 参考只包含四个本地/manual 节点：

```json
{
  "artifacts_root": ".ef/artifacts/REQ-EXM-FUEL-GAUGE-001",
  "dependencies": [],
  "need": null,
  "requirement": {
    "id": "REQ-EXM-FUEL-GAUGE-001",
    "title": "Fuel gauge UI responds to CAN fuel level signal changes",
    "scope": "simulated EXM-K board verification",
    "watch": ["src/**/*.txt"],
    "evidence": ["test_design", "build", "deploy", "human_review.final"]
  },
  "nodes": {
    "test_design": {
      "recipe": {"id": "test_design", "type": "manual", "review": "required"},
      "status": {"status": "missing", "reason": "no produced evidence"}
    },
    "build": {
      "recipe": {"id": "build", "type": "shell", "depends_on": ["test_design"]},
      "status": {"status": "missing", "reason": "no produced evidence"}
    },
    "deploy": {
      "recipe": {"id": "deploy", "type": "shell", "depends_on": ["build"]},
      "status": {"status": "missing", "reason": "no produced evidence"}
    },
    "human_review.final": {
      "recipe": {"id": "human_review.final", "type": "manual", "review": "required"},
      "status": {"status": "missing", "reason": "no produced evidence"}
    }
  }
}
```

v0.1 的 context 输出不包含 SSH 凭据、板端 host、CANSim endpoint、板端部署路径或 target automation channel。

### 10.3 范围化上下文查询

```bash
$ ef context REQ-EXM-FUEL-GAUGE-001 --need build --format json
```

只返回请求节点及其依赖：

```json
{
  "need": "build",
  "dependencies": ["test_design"],
  "nodes": {
    "test_design": {
      "recipe": {
        "id": "test_design",
        "type": "manual",
        "review": "required",
        "instructions": "Record the CAN stimulus levels, expected UI states, screenshot checks, and log checks before build/deploy evidence is accepted."
      },
      "status": {"status": "missing"}
    },
    "build": {
      "recipe": {
        "id": "build",
        "type": "shell",
        "description": "Simulated EXM-K build artifact",
        "depends_on": ["test_design"],
        "command": "mkdir -p out\ncp src/fuel_gauge.txt out/EXM-K\n",
        "produces": [{"artifact": "out/EXM-K", "type": "simulated-binary", "label": "binary"}]
      },
      "status": {"status": "missing"}
    }
  }
}
```

未来如果出现包含 `type: cansim`、CANSim host/port、board host 或目标部署路径的 `verify.can_stimulus` 范围化上下文，那属于 v0.2+ 路线图行为，不是 v0.1 CLI 输出。

### 10.4 Agent 工作流模式

v0.1 的本地/manual 交互模式是：

```text
1. Agent 收到任务："满足 REQ-EXM-FUEL-GAUGE-001"
2. Agent 调用：ef what-next REQ-EXM-FUEL-GAUGE-001
3. Agent 调用：ef context REQ-EXM-FUEL-GAUGE-001 --need build --format json
4. Agent 调用：ef satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run
5. Agent 调用：ef satisfy REQ-EXM-FUEL-GAUGE-001
6. 人工或责任 reviewer 使用 --rationale 接受 required manual 节点
7. Agent 调用：ef status REQ-EXM-FUEL-GAUGE-001 --format json
```

未来由 agent task 生成测试设计、CANSim 注入激励、target automation 捕获截图、板端日志成为证据的工作流属于 v0.2+ 路线图行为。

---

## 11. 测试设计证据结构

该 schema 是未来目标设备测试设计产物形态。v0.1 中，`test_design` 是模拟 EXM-K 参考里的 manual review gate；自动 `agent_task` 产出和 CANSim 驱动的目标设备验证均已延后。

### 11.1 Schema：test_design_v1

测试设计是结构化 YAML 文档，可在 v0.1 作为 manual 证据附件，也可在未来由 `agent_task` Recipe 生成。它定义在目标设备集成存在时如何验证需求。

```yaml
schema: test_design_v1
requirement: REQ-EXM-FUEL-GAUGE-001
produced_by: agent_task
produced_at: "2026-04-30T09:30:00Z"

# 审批追踪
review:
  status: approved
  reviewer: "liu"
  reviewed_at: "2026-04-30T09:45:00Z"
  rationale: "测试方案覆盖所有油量状态"

# 注入什么 CAN 信号
stimulus:
  type: cansim_sequence
  provider: CANSimService
  channel: board_can1_rx_via_usb2
  transport: http

  sequences:
    - id: fuel_low
      description: "设置油量为 0%（空油箱）"
      source: ".ef/profiles/exm-k/cansim_sequences/fuel_level_low.signals.json"
      signals:
        - name: iFuelLevel_a
          pgn: "0x00FEF2"
          spn: 96
          value: 0
          unit: "%"
      hold_ms: 2500
      settle_ms: 2500
      expected_ui_state: "油量环最小位置，红色区域"

    - id: fuel_mid
      description: "设置油量为 50%（半满）"
      signals:
        - name: iFuelLevel_a
          value: 50
          unit: "%"
      hold_ms: 2500
      settle_ms: 2500
      expected_ui_state: "油量环中间位置，黄色区域"

    - id: fuel_high
      description: "设置油量为 100%（满油）"
      signals:
        - name: iFuelLevel_a
          value: 100
          unit: "%"
      hold_ms: 2500
      settle_ms: 2500
      expected_ui_state: "油量环最大位置，绿色区域"

    - id: fuel_invalid
      description: "设置油量为 0xFFFF（无效/超时）"
      signals:
        - name: iFuelLevel_a
          value: 0xFFFF
          unit: "raw"
      hold_ms: 2500
      settle_ms: 2500
      expected_ui_state: "油量显示 '--' 或空白"

# 在目标设备上观察什么
observations:
  - id: fuel_ring_visual
    type: visual
    target: "主面板燃油表环"
    method: board_screenshot
    page_id: main_panel
    roi: {x: 120, y: 260, width: 320, height: 220}
    description: "环形填充量和颜色应随油量变化"

  - id: fuel_numeric_display
    type: visual
    target: "油量百分比数字"
    method: board_screenshot
    page_id: main_panel
    description: "应显示 0%、50%、100% 或 '--'（无效时）"

  - id: board_log_check
    type: log
    source: "/userdata/media/EXM.log"
    method: scp_pull
    patterns:
      - pattern: "FuelLevel updated"
        expected: present_during_stimulus
      - pattern: "CAN timeout"
        expected: present_during_invalid
      - pattern: "FATAL"
        expected: absent

# 如何判定通过/失败
pass_criteria:
  - id: visual_fuel_change
    type: manual_visual
    pass_condition: |
      对比 fuel_low、fuel_mid、fuel_high 截图：
      - 环形填充量从 low → mid → high 明显增加
      - 颜色转换：红 → 黄 → 绿
    failure_signal: "不同油量级别下截图相同"

  - id: invalid_handling
    type: manual_visual
    pass_condition: "fuel_invalid 激励时，显示 '--' 而非数字"
    failure_signal: "无效信号期间显示数值"

  - id: no_fatal_errors
    type: auto
    check: pattern_absent
    pattern: "FATAL"
    failure_signal: "测试期间板端日志出现 FATAL 错误"

# 自动化 vs 手动分工
automation_plan:
  automated:
    - description: "CANSimService 激励注入"
      provider: cansim
      sequences: [fuel_low, fuel_mid, fuel_high, fuel_invalid]
    - description: "板端截图捕获"
      provider: target_automation
      actions: [goto_page main_panel, capture_screenshot]
    - description: "板端日志采集与模式检查"
      method: scp_pull

  manual:
    - description: "油量环跨状态视觉比对"
      reviewer: human
      criteria: visual_fuel_change
    - description: "无效信号处理验证"
      reviewer: human
      criteria: invalid_handling
    - description: "所有证据最终验收"
      gate: human_review.final

# 已知空白和风险
known_gaps:
  - "精确边界值（如 25%、75%）的油量未测试"
  - "波形滤波器建立时间（DashBoardFuelLevel_WaveFilterTimer）为近似值"
  - "多通道同时 CAN 信号交互未覆盖"

risks:
  - severity: medium
    description: "WSL 网关慢时 CANSimService 可能超时"
    mitigation: "预检 /health 端点；超时时重试一次"
  - severity: low
    description: "截图时可能捕获到过渡帧"
    mitigation: "使用 settle_ms > 波形滤波器周期（2500ms > 2000ms）"
```

### 11.2 测试设计如何阻塞验证

`test_design` Recipe 设置了 `review: required`。这意味着：

1. test_design 证据产出后，DAG 引擎检查是否有 `status: accepted` 的 `reviewed` 事件
2. 如果没有，所有依赖 `test_design` 的节点被视为**阻塞**
3. `ef satisfy` 将暂停并提示：`"test_design 等待人工审批"`
4. 只有在 `ef review test_design <req> --accept` 之后，下游执行才会继续

这确保了：
- 没有审批过的测试方案，验证不会发生
- CAN 激励序列在注入前已定义并审批
- 目标自动化操作在执行前已规划
- 通过/失败判定标准在评判结果前已达成一致

---

## 12. 项目布局

下面的项目布局是未来完整目标设备布局。它包含 CANSim、target automation、Python 插件、运行元数据和真实板端产物，这些均已从 v0.1 延后。v0.1 已检入参考是更小的 `examples/exm-k` 本地/manual 布局。

### 12.1 目录结构

```text
项目根目录/
  ef.yaml                                   # 主配置（提交）

  .ef/
    profiles/
      exm-k/
        profile.yaml                        # 构建/部署/目标配置（提交）
        local.env.yaml                      # 本地覆盖、密钥（gitignore）
        cansim_sequences/                   # CAN 信号定义文件（提交）
          fuel_level_low.signals.json
          fuel_level_high.signals.json
          fuel_gauge_sweep.sequence.json

    requirements/                           # 需求定义（提交）
      REQ-EXM-FUEL-GAUGE-001.yaml
      REQ-EXM-TOOL-PRESSURE-001.yaml

    recipes/                                # Recipe 定义（提交）
      build.yaml
      deploy.yaml
      test_design.yaml
      verify.can_stimulus.yaml
      verify.screenshot.yaml
      verify.comparison.yaml
      verify.log.yaml
      human_review.final.yaml

    plugins/                                # Python Recipe 插件（提交）
      __init__.py
      unlock_automation.py

    evidence.jsonl                           # 只追加事件日志（gitignore）

    artifacts/                              # 产出的证据文件（gitignore）
      REQ-EXM-FUEL-GAUGE-001/
        build/
        deploy/
        test_design/
        verify.can_stimulus/
        verify.screenshot/
        verify.comparison/
        verify.log/
        human_review.final/

    runs/                                   # 运行元数据（gitignore）

    knowledge/                              # 可选知识引用（提交）
```

### 12.2 .gitignore 条目

```gitignore
# EmbeddedFlow - 默认 gitignore
.ef/evidence.jsonl
.ef/artifacts/
.ef/runs/
.ef/profiles/*/local.env.yaml
.ef/profiles/*/local.secrets.env
```

### 12.3 主配置（`ef.yaml`）

```yaml
project:
  id: exm-k
  name: "EXM-K"
  description: "K系列挖机显示器1代项目"
  repo_root: "."
  app_root: "EXM-K"

default_profile: exm-k

recipe_defaults:
  timeout: 300
  shell: /bin/bash

knowledge:
  provider: card_kb
  path: "EXM-K/docs/ai-kb/"
  index: "EXM-K/docs/ai-kb/index/project-index.yaml"

policy:
  source_verification: required
  evidence_required: true
  test_design_review: required
  final_acceptance: required

vars:
  display_resolution: "1024x600"
  default_settle_ms: 2500
```

### 12.4 Profile 配置

该生产板 Profile 形态是延后的路线图材料。v0.1 不解析 VM、板端、CANSim、SSH 或 SCP 目标。

```yaml
# .ef/profiles/exm-k/profile.yaml
id: exm-k
name: "EXM-K Kilo 生产板"
description: "ARM RV1126 OpenWrt 板，1024x600 显示"

build:
  system: qmake
  entry: "EXM-K/EXM-K.pro"
  working_dir: "EXM-K/build/kilo"
  artifact_path: "EXM-K/build/kilo/EXM-K"
  artifact_type: arm-elf

deploy:
  target_kind: openwrt_board
  deploy_dir: "/userdata/media/custom/EXM/"
  start_command: "cd /userdata/media/custom && sh ./startApp.sh >/userdata/media/startApp_exm.log 2>&1 &"
  health_checks:
    - "pgrep EXM-K"
    - "test -f /userdata/media/EXM.log"
  stop_wait_seconds: 12
  startup_timeout_seconds: 40

targets:
  vm:
    host: "{{local_env.targets.vm.host}}"
    port: "{{local_env.targets.vm.port}}"
    user: "{{local_env.targets.vm.user}}"
  board:
    host: "{{local_env.targets.board.host}}"
    port: "{{local_env.targets.board.port}}"
    user: "{{local_env.targets.board.user}}"
  cansim:
    host: auto
    port: 18766
    transport: http
```

### 12.5 本地环境（gitignore）

该真实目标本地环境文件是未来 SSH/板端集成的延后路线图材料，v0.1 不需要。

```yaml
# .ef/profiles/exm-k/local.env.yaml
# 机器特定覆盖。绝不提交此文件。
targets:
  vm:
    host: "192.168.24.129"
    port: 22
    user: "zoomlion"
    auth_mode: "password"
    password_env: "EF_VM_PASSWORD"
  board:
    host: "192.168.0.149"
    port: 22
    user: "root"
    auth_mode: "password"
    password_env: "EF_BOARD_PASSWORD"

build_env:
  env_exports:
    STAGING_DIR: "/opt/rv1126_sdk/openwrt/staging_dir"
  qmake_path: "/opt/rv1126_sdk/openwrt/staging_dir/target-arm_cortex-a7+neon_glibc_eabi/host/bin/qmake"
  build_workdir_override: "/mnt/hgfs/code/work_code/exm-k-2024/EXM-K/build/kilo"
```

---

## 13. CANSimService 集成

### 13.1 架构角色

```text
Recipe: verify.can_stimulus（type: cansim）
  → CansimExecutor（内置，v0.2）
    → HTTP 客户端
      → CANSimService 端点（WSL 或远程）
        → CAN 硬件接口
          → 目标板 CAN 总线
```

### 13.2 主机解析

CANSimService 主机在 Recipe 执行时解析：

1. 检查 `EF_CANSIM_HOST` 环境变量覆盖
2. 如果 Profile 中 `host: auto`：
   - 解析 `/etc/resolv.conf` 中的 WSL nameserver IP
   - 或解析 `ip route show default` 中的网关 IP
   - 使用检测到的网关作为 CANSimService 主机
3. 否则使用 Profile 中的 `host` 值

### 13.3 使用的 HTTP 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/health` | GET | 预检：服务可用 |
| `/channels` | GET | 预检：所需 CAN 通道存在 |
| `/signals/set` | POST | 设置特定信号值 |
| `/sequence/run` | POST | 运行预定义信号序列 |
| `/periodic/start` | POST | 启动周期性信号流 |
| `/periodic/stop` | POST | 停止周期性流 |

### 13.4 CAN 序列文件格式

```json
{
  "id": "fuel_level_low",
  "description": "设置油量为 0%（空油箱）",
  "channel": "board_can1_rx_via_usb2",
  "signals": [
    {
      "name": "iFuelLevel_a",
      "pgn": "0x00FEF2",
      "spn": 96,
      "value": 0,
      "unit": "%"
    }
  ],
  "mode": "one_shot",
  "settle_ms": 2500
}
```

### 13.5 与测试设计的集成

test_design 证据定义了要运行哪些序列。verify.can_stimulus Recipe 读取 test_design 产物并执行指定序列：

```text
test_design.yaml → stimulus.sequences[*].source → cansim_sequences/*.json → HTTP API 调用
```

---

## 14. 目标自动化集成

### 14.1 架构角色

```text
Recipe: verify.screenshot（type: target_automation）
  → TargetAutomationExecutor（内置，v0.2）
    → SSH 隧道到板端
      → ZMQ PUB/SUB 套接字
        → 板端 ZMQBroker
          → EXM-K TestAutomation 模块
            → 页面导航、截图、状态查询
```

### 14.2 通信协议

- **传输层**：ZMQ PUB/SUB over SSH 隧道
- **命令主题**：`/BROKER/EXM/TestAutomation/Command`
- **回复主题**：`/BROKER/EXM/TestAutomation/Reply`
- **命令端口**：5661（板端）
- **回复端口**：7661（板端）
- **格式**：JSON 消息

### 14.3 可用命令

| 命令 | 描述 | 返回 |
|------|------|------|
| `goto_page` | 导航到指定 UI 页面 | 成功/失败 |
| `wait_page` | 等待页面加载 | 成功/超时 |
| `wait_stable` | 等待 UI 稳定 | 成功 |
| `capture_screenshot` | 截取当前显示 | 截图路径 |
| `get_state` | 查询应用状态 | 状态 JSON |
| `press_button` | 模拟按钮按下 | 成功/失败 |

---

## 15. 人工审批门禁

### 15.1 门禁类型

| 门禁 | 时机 | 审查内容 | 决策者 |
|------|------|---------|--------|
| test_design 审批 | 测试方案生成后 | 激励、观察、判定标准、自动化方案 | 工程师 |
| human_review.final | 所有验证完成后 | 构建/部署/验证证据、截图 | 工程师或 QA |

### 15.2 审批工作流

```text
1. Recipe 产出证据（如 test_design.yaml）
2. 引擎检测到 review: required
3. 引擎追加 'produced' 事件，status: pass
4. 引擎打印："[wait] test_design -- 等待人工审批"
5. ef satisfy 停止（不继续执行依赖节点）
6. 人工审查产物
7. 人工执行：ef review test_design REQ-xxx --accept --reviewer <name> --rationale "..."
8. 引擎追加 'reviewed' 事件，review_status: accepted
9. 下次 ef satisfy 调用看到 test_design 完全有效
10. 依赖节点（verify.*）可以执行了
```

### 15.3 拒绝和返工

```bash
$ ef review test_design REQ-EXM-FUEL-GAUGE-001 --reject --reviewer liu --rationale "缺少无效信号测试用例"
```

拒绝后：
- 节点状态变为 `rejected`
- Agent/开发者必须重新生成测试设计
- `ef recipe run test_design REQ-EXM-FUEL-GAUGE-001 --force` 重新产出
- 重新产出后需要新一轮审批

---

## 16. 知识层

### 16.1 原则

```text
知识库：可选
发现：优先（没有知识库也能工作）
提升：只提升稳定的、重复出现的、与决策相关的发现
```

### 16.2 与证据-DAG 的集成

知识辅助两个操作：
1. **ef context**：在上下文输出中包含相关知识引用
2. **测试设计生成**：AI Agent 使用知识来指导测试设计

### 16.3 知识级别

```text
Level 0：无知识库
  - Agent 使用 ef context + 源码探索
  - 适用于新项目、小项目或短期项目

Level 1：轻量知识提示
  - 小型项目地图、高风险路径、构建/部署注意事项
  - 在 ef.yaml knowledge.path 中引用

Level 2：结构化知识提供者
  - EXM-K AIKB 风格卡片（模块、流程、变更模式、影响规则）
  - 完整 card_kb 提供者，带索引路由
```

---

## 17. 从 CodexFlow 迁移

### 17.1 概念映射

| CodexFlow 概念 | Evidence-DAG 对应 |
|---|---|
| `STAGE_ORDER`（线性列表） | DAG `depends_on` 边（图） |
| `STAGE_DEPENDENCIES` 字典 | 每个 Recipe 中的 `depends_on` 字段 |
| 阶段：intake | 隐式（需求创建） |
| 阶段：solution | 隐式（实现的一部分） |
| 阶段：test_design | 证据节点：`test_design`（review: required） |
| 阶段：implement | 非 DAG 节点（实现在外部进行） |
| 阶段：build | 证据节点：`build` |
| 阶段：deploy | 证据节点：`deploy` |
| 阶段：board_verify | 证据节点：`verify.*`（多个） |
| 阶段：archive | 隐式（所有证据满足 = 关闭） |
| `manifest.yaml`（可变状态） | `evidence.jsonl`（只追加事件） |
| Adapter 类 + Registry | Recipe YAML + 可选 Python 插件 |
| `ExmKiloBuildAdapter` | Recipe：`build.yaml`（type: shell, remote: true） |
| `ExmBoardDeployAdapter` | Recipe：`deploy.yaml`（type: shell, steps） |
| `ExmBoardVerifyAdapter` | Recipe：`verify.*.yaml`（多个节点） |
| `CansimServiceHttpStimulusAdapter` | Recipe：`verify.can_stimulus.yaml`（type: cansim） |
| `WorkflowPacket`（推送给 Agent） | `ef context`（Agent 拉取） |
| `codexflow.py run init` | `ef satisfy REQ-xxx`（自动创建运行） |
| `codexflow.py stage build --execute` | `ef satisfy REQ-xxx`（自动决定执行什么） |
| `codexflow.py run close` | 隐式（所有证据满足） |
| `codexflow.py run human-acceptance` | `ef review human_review.final REQ-xxx --accept` |
| Testcase YAML | Requirement YAML 在 `.ef/requirements/` |
| CAN 序列文件 | 同文件，移到 `.ef/profiles/exm-k/cansim_sequences/` |

### 17.2 可复用内容

**直接复用（作为库代码）**：
- `codex_version/tools/lib/runner.py` — SSH/SCP 命令执行
- `codex_version/tools/lib/cansim.py` — CANSim 主机解析 + HTTP
- `codex_version/tools/lib/evidence.py` — 产物文件写入助手

**适配后复用**：
- `codex_version/tools/lib/test_design.py` — 测试设计 schema 验证逻辑
- `codex_version/tools/lib/manifest.py` — 原子文件写入模式

**不复用（被 DAG 替代）**：
- `codex_version/tools/lib/models.py` — 阶段排序、manifest 创建
- `codex_version/tools/lib/registry.py` — Adapter 注册表
- `codex_version/tools/cli/codexflow.py` — CLI 和基于阶段的工作流逻辑

### 17.3 共存期

迁移期间两个系统可以共存：
- `codex_version/` 目录保留用于进行中的工作
- `.ef/` 目录并行添加
- 相同的 Profile 数据、相同的 CAN 序列、相同的目标
- 逐步将需求从 CodexFlow 迁移到 EmbeddedFlow

---

## 18. v0.1 交付物

### 18.1 最小可行功能集

| # | 交付物 | 描述 |
|---|--------|------|
| 1 | CLI 骨架 | `ef` 命令及子命令，参数解析（click 或 argparse） |
| 2 | `ef init` | 创建 `.ef/` 目录结构 |
| 3 | 配置加载 | 解析 `ef.yaml`、`profile.yaml`、`local.env.yaml` |
| 4 | 模板引擎 | Recipe 中的 `{{variable}}` 展开 |
| 5 | 源码哈希 | 监视文件的 SHA-256 计算 |
| 6 | Recipe 哈希 | Recipe 定义的 SHA-256 计算 |
| 7 | DAG 构建器 | 从需求 + Recipe 构建图 |
| 8 | 拓扑排序 | Kahn 算法，含层级检测 |
| 9 | 有效性检查器 | `is_valid()`，含哈希比对和传递检查 |
| 10 | 失效级联 | 传递性过期标记 |
| 11 | 证据存储 | JSONL 追加/读取/查询 |
| 12 | `ef satisfy` | 完整 DAG 执行，含 shell + manual 类型 |
| 13 | Shell 执行器 | 本地 subprocess 命令执行；SSH 远程延后 |
| 14 | Manual 执行器 | 阻塞 + 提示 + `ef review` |
| 15 | `ef status` | 逐节点有效性显示 |
| 16 | `ef what-next` | 下一步操作建议 |
| 17 | `ef context` | 拉取式上下文（完整 + 范围化） |
| 18 | `ef evidence list/show/invalidate` | 证据管理 |
| 19 | `ef dag` | 文本模式 DAG 可视化 |
| 20 | `ef review` | 人工审批记录 |
| 21 | EXM-K Profile | 模拟本地参考 Profile + build/deploy Recipe |

### 18.2 v0.2 新增

- `cansim` Recipe 类型（内置 CANSimService HTTP 执行器）
- `target_automation` Recipe 类型（内置 ZMQ 桥接）
- `agent_task` Recipe 类型（结构化 Agent 协议）
- `python` Recipe 类型（插件式 Recipe）
- 并行执行（`--jobs N`）
- 知识库提供者集成（`card_kb`）
- 测试设计 schema 验证
- `ef run list/show` — 运行历史
- `ef recipe run` — 直接单 Recipe 执行

### 18.3 v0.3 新增

- `ef dag` — Graphviz DOT 输出
- 多 Profile 支持（切换目标板）
- Recipe 组合（Recipe 组、Recipe 模板、共享步骤）
- 证据导出/导入
- 报告/摘要生成（`ef render`）
- CAN 序列文件管理工具
- RequirementLedger 集成（GitHub Issues、TODO.md 同步）

### 18.4 实现阶段

```text
Phase 1：基础（2 周）
  - 项目结构（pyproject.toml、src/embeddedflow/）
  - 基于 click 的 CLI 骨架
  - ef init 命令
  - 配置加载（ef.yaml、profile、local.env）
  - 模板变量解析引擎（Jinja2-lite）
  - 证据存储（JSONL 读/写/查询）
  - 源码哈希计算（SHA-256 over 文件内容）
  - Recipe 哈希计算

Phase 2：DAG 核心（2 周）
  - 需求 YAML 加载器（含验证）
  - Recipe YAML 加载器（含验证）
  - 从 depends_on 边构建 DAG
  - 拓扑排序（Kahn 算法）
  - 有效性检查算法（is_valid）
  - 失效级联逻辑
  - ef status 命令
  - ef dag 命令（文本模式）

Phase 3：执行（2 周）
  - ef satisfy 命令（完整流程）
  - Shell Recipe 执行器（本地 subprocess）
  - v0.1 后延后：Shell Recipe 执行器（远程 SSH，复用 runner.py 模式）
  - v0.1 后延后：SCP 文件拷贝（产物拉取）
  - 多步骤 Recipe 支持（steps 数组）
  - Manual Recipe 执行器（阻塞 + 提示）
  - ef review 命令
  - ef what-next 命令
  - 产物目录管理

Phase 4：AI 接口（1 周）
  - ef context 命令（完整上下文）
  - ef context --need（范围化上下文）
  - ef recipe complete（Agent 证据报告）
  - ef evidence list/show/invalidate
  - 输出格式支持（yaml、json、markdown）

Phase 5：EXM-K 集成（1 周）
  - 编写 exm-k profile.yaml + local.env.yaml
  - 编写 build.yaml Recipe
  - 编写 deploy.yaml Recipe
  - 编写 test_design.yaml Recipe（v0.1 为手动占位）
  - 编写 human_review.final.yaml Recipe
  - v0.1 smoke：在模拟本地 build + deploy 上执行 ef satisfy dry-run
  - v0.1 后延后：在真实 VM/板端执行 build + deploy 的端到端测试
  - 增量测试：修改源码 → ef status 显示过期 → ef satisfy 只重建
  - 迁移指南文档
```

---

## 19. 关键风险与防护

| 风险 | 防护措施 |
|------|---------|
| DAG 模型对简单需求太复杂 | 只有 [build, deploy] 的需求是 2 个节点——比 8 阶段 CodexFlow 流水线简单。复杂度随需要扩展，不随仪式增加。 |
| 大代码库源码哈希计算慢 | 哈希计算是惰性的（仅在 ef status/satisfy 时）。使用增量哈希 + 缓存。Glob 展开是瓶颈——用 mtime 检查缓存文件列表。 |
| AI Agent 不理解拉取式上下文模型 | `ef what-next` 给出明确指令。`ef context --need` 给出精确所需。Agent 始终可以回退到 `ef satisfy` 全自动处理。 |
| evidence.jsonl 无限增长 | 每个节点最新有效/失效循环之外的旧事件可以安全压缩。v0.2 添加 `ef evidence compact` 命令。 |
| 测试设计审批变成橡皮图章 | `manual` 审批要求显式理由。不带 `--rationale` 的 `ef review --accept` 被拒绝。审批事件是审计轨迹的一部分。 |
| 远程 Recipe 执行（SSH）挂起或超时 | 所有 Recipe 有可配置超时。Shell 执行器使用 subprocess with timeout。SSH 命令使用 `-o ConnectTimeout=10`。健康检查有重试逻辑。 |
| EXM-K 产品细节泄漏到核心 | 所有 EXM-K 特定值在 `.ef/profiles/exm-k/` 和 `.ef/requirements/` 中。核心引擎是项目无关的——执行 Recipe 时不需要理解 CAN 信号或 UI 页面。 |
| 并发 ef satisfy 调用损坏 evidence.jsonl | 证据追加使用操作系统级文件锁（fcntl）。运行 ID 唯一（时间戳 + 随机）。v0.1 建议单操作者使用。 |

---

## 20. 决策总结

确定的方向：

- 将 EmbeddedFlow 构建为**基于 DAG 的证据约束求解器**，而非阶段门禁流水线
- 仅三个核心概念：需求、Recipe、证据
- **增量执行**（类 Make）：只重跑过期的
- **拉取式 AI 上下文**：Agent 通过 `ef context` 按需查询
- **测试设计是硬依赖**：`verify.*` 节点在审批通过的测试方案之前不能运行
- **内容哈希有效性**：不是时间戳，不是手动标记
- **只追加事件日志**：不可变审计轨迹，状态从事件推导
- **Recipe 优先的适配器模型**：简单场景用 YAML 定义，复杂场景用 Python 插件
- **Python 实现**：AI 友好，与现有 codexflow.py 一致
- **EXM-K 作为首个参考**：相同的目标、相同的 CAN 序列、相同的知识库
- v0.1 用 `shell` + `manual` Recipe 类型验证 DAG 模型，v0.2 再添加 `cansim`、`target_automation` 和 `agent_task`
