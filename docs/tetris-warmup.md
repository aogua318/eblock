# 俄罗斯方块（Tetris）热身项目开发文档

阶段 0 热身游戏：用 Python + Pygame 从零实现一个完整可玩的俄罗斯方块。
本项目的最终目标不是“做出 Tetris”，而是以 Tetris 为载体训练：数据驱动、强类型、
分层解耦、测试与静态检查全绿。

## 1. 项目定位与学习目标

| 训练点 | 落地位置 |
| --- | --- |
| 主循环与帧驱动 | `eblock/tetris/app/main.py` |
| 键盘事件与输入手感（DAS/ARR） | `eblock/tetris/ui/input.py` |
| 数据驱动与配置校验 | `config/tetris.json` |
| 纯逻辑可测试 | `eblock/tetris/sim/`（board、rotation、randomizer、scoring、game） |
| 状态快照与持久化 | `eblock/tetris/save/highscore.py` |
| 分层解耦 | sim 不依赖 pygame；ui 只读状态，不直接改数据 |

## 2. 游戏规则（v1 范围）

### 2.1 棋盘

- 10 列 × 22 行；行 0–1 为隐藏出生区，行 2–21 为可见区。
- 允许方块格子位于 `y = -1`（虚拟出生区，视为空，不写入棋盘存储）。
- 出生原点固定为 `(x=4, y=0)`，所有方块出生时完全位于隐藏区。

### 2.2 方块与旋转

- 7 种方块 `I O T S Z J L`，采用标准 SRS（Super Rotation System）旋转与踢墙表。
- 旋转状态 `0 / R / 2 / L`（顺时针递增）；同时支持顺时针与逆时针旋转。
- O 方块旋转后形状不变，无踢墙表（旋转状态允许变化，但格子集合相同）。
- 出生方向：默认固定为初始方向（rotation=0）；当配置 `spawn_random_rotation=true`
  时，新方块出生时随机取 0..3 之一作为初始旋转状态。
- 出块顺序由配置 `randomizer.mode` 决定（7-bag / 纯随机 / 免连续重复，见 §6.4）。

### 2.3 操作

左/右移动、软降（↓）、硬降（空格）、顺时针旋转（↑/X）、逆时针旋转（Z/Ctrl）、
保持（C/Shift）、暂停（P）、重开（R）、退出（Esc）。

### 2.4 计分与等级

- 消行：1/2/3/4 行 = 100/300/500/800 × 当前等级。
- 软降每格 +1 分，硬降每格 +2 分。
- 每消 10 行升 1 级（从 1 级开始）；等级决定下落速度（查表，见 §3.1）。

### 2.5 结束条件

- 新方块在出生位置发生碰撞 → 游戏结束，`GAME_OVER` 事件只触发一次。

### 2.6 v1 明确不实现

T-spin 判定、Combo、Back-to-Back、5-bag、幽灵入场规则、中局存档、排行榜、音效。
以上作为后续阶段的可选项，避免热身项目过度设计。

## 3. 数据驱动设计

### 3.1 config/tetris.json

```json
{
  "board": { "cols": 10, "rows": 22, "visible_rows": 20, "spawn_x": 4, "spawn_y": 0 },
  "scoring": {
    "line_clear": { "1": 100, "2": 300, "3": 500, "4": 800 },
    "soft_drop_per_cell": 1,
    "hard_drop_per_cell": 2,
    "lines_per_level": 10,
    "start_level": 1
  },
  "gravity_ms_per_level": {
    "1": 1000, "2": 793, "3": 618, "4": 473, "5": 355,
    "6": 262, "7": 184, "8": 124, "9": 84, "10": 59
  },
  "max_level": 10,
  "timing": {
    "lock_delay_ms": 500,
    "lock_reset_limit": 15,
    "soft_drop_interval_ms": 50
  },
  "input": { "das_ms": 170, "arr_ms": 50 },
  "randomizer": { "mode": "seven_bag" },
  "spawn_random_rotation": false,
  "preview_count": 3
}
```

字段含义：

| 字段路径 | 含义 |
| --- | --- |
| `board.cols` | 棋盘列数（宽度） |
| `board.rows` | 棋盘总行数，含顶部隐藏出生区 |
| `board.visible_rows` | 玩家可见的行数（隐藏出生区之下的部分） |
| `board.spawn_x` | 方块出生原点的列坐标 |
| `board.spawn_y` | 方块出生原点的行坐标 |
| `scoring.line_clear` | 同时消 1/2/3/4 行时的基础分数（再乘当前等级） |
| `scoring.soft_drop_per_cell` | 软降每下移一格的加分 |
| `scoring.hard_drop_per_cell` | 硬降每下移一格的加分 |
| `scoring.lines_per_level` | 每消除多少行升 1 级 |
| `scoring.start_level` | 开局等级（从 1 级开始） |
| `gravity_ms_per_level` | 各等级对应的自动下落间隔（毫秒），数值越小下落越快 |
| `max_level` | 最高等级；超过后按 `max_level` 的速度下落 |
| `timing.lock_delay_ms` | 方块触底后允许继续移动/旋转的宽限时间（毫秒），超时锁定 |
| `timing.lock_reset_limit` | 触底后成功移动/旋转可重置锁定计时的累计次数上限，超过立即锁定 |
| `timing.soft_drop_interval_ms` | 按住软降键时每次下移的间隔（毫秒） |
| `input.das_ms` | 按住左/右键后开始连续移动的延迟（毫秒），0 表示无延迟 |
| `input.arr_ms` | 连续移动的重复间隔（毫秒），0 表示每帧都移动 |
| `randomizer.mode` | 发牌算法：`seven_bag`（7-bag，默认）/ `uniform`（纯随机）/ `no_repeat`（免连续重复） |
| `spawn_random_rotation` | 出生时是否随机旋转：false=固定初始方向；true=随机 0..3 方向 |
| `preview_count` | 右侧面板显示的下一个方块预览数量 |

校验规则（加载失败抛 `ConfigError` 并指出字段路径）：

- `cols` 4–20、`rows` ≥ 20 的整数。
- `line_clear` 必须恰好包含键 `1`–`4`，值均为正整数。
- `gravity_ms_per_level` 的键必须严格按顺序覆盖 `1..max_level` 连续整数，值为正数。
- `lock_delay_ms` 100–2000；`das_ms` 0–500；`arr_ms` 0–200。
- `randomizer.mode` 必须是 `seven_bag` / `uniform` / `no_repeat` 之一。
- `spawn_random_rotation` 必须是布尔值（数字 0/1 不算布尔）。
- `preview_count` ≥ 1。

### 3.2 配置与代码常量边界

- 进 config：分数、等级速度、锁定延迟、软降间隔、DAS/ARR、预览数量、棋盘尺寸。
- 进 config：发牌模式（随机算法选择）与出生随机旋转开关——它们是玩法可选项。
- 留代码：方块形状与 SRS 踢墙表——它们是游戏规则几何，不是可调参数值。
- 原则：凡是“想调难度/手感时可能改的值”进 config；凡是“改了就不是 Tetris”的规则进代码。

## 4. 架构与模块

```
src/eblock/
├── tetris/              # 俄罗斯方块独立子包
│   ├── sim/
│   │   ├── tetromino.py # PieceType、出生态形状、旋转状态
│   │   ├── board.py     # 棋盘存储、碰撞检测、消行
│   │   ├── rotation.py  # SRS 旋转公式与踢墙表
│   │   ├── randomizer.py# 7-bag
│   │   ├── scoring.py   # 计分与等级
│   │   └── game.py      # Game 状态机：step / dt / 锁定 / 结束判定
│   ├── ui/
│   │   ├── input.py     # DAS/ARR 输入处理 → Action
│   │   └── renderer.py  # 棋盘、当前方块、Ghost、Next、Hold、面板
│   ├── app/
│   │   └── main.py      # 主循环、暂停、重开、退出
│   └── save/
│       └── highscore.py # 最高分 JSON 持久化
└── coffee/              # 咖啡店主项目（阶段 1 起创建）
config/tetris.json       # 数值配置
tests/                   # 按游戏分子目录：tests/tetris/、tests/coffee/
```

组织原则：**按游戏分包，层内分层**。每个游戏在 eblock 下拥有独立子包，
子包内部再按 sim → ui → app → save 分层，互不共享命名空间。
依赖方向：`sim`（零 pygame 依赖）← `ui` ← `app`；`save` 只依赖标准库。
`ui` 通过 `Game.step(action, dt)` 驱动 sim，通过 `StepResult.state` 读取展示数据。
启动命令：`python -m eblock.tetris.app.main`。

## 5. 核心接口

```python
class Action(Enum):
    MOVE_LEFT = auto()
    MOVE_RIGHT = auto()
    ROTATE_CW = auto()
    ROTATE_CCW = auto()
    SOFT_DROP_START = auto()
    SOFT_DROP_END = auto()
    HARD_DROP = auto()
    HOLD = auto()


class GameEvent(Enum):
    PIECE_SPAWN = auto()
    PIECE_LOCK = auto()
    LINES_CLEARED = auto()
    LEVEL_UP = auto()
    HOLD_SWAP = auto()
    GAME_OVER = auto()


@dataclass(frozen=True)
class PieceState:
    piece_type: PieceType  # I / O / T / S / Z / J / L
    rotation: int  # 0 / 1 / 2 / 3
    x: int
    y: int


@dataclass(frozen=True)
class GameState:
    board: tuple[tuple[PieceType | None, ...], ...]  # 22 行 × 10 列
    current: PieceState
    ghost_y: int
    next_queue: tuple[PieceType, ...]  # 完整袋余量，可序列化
    hold: PieceType | None
    hold_used: bool
    score: int
    level: int
    lines: int
    game_over: bool


@dataclass(frozen=True)
class StepResult:
    events: tuple[GameEvent, ...]
    state: GameState


class Game:
    def step(self, action: Action | None, dt_ms: int) -> StepResult: ...
    def to_state(self) -> GameState: ...
    def load_state(self, state: GameState) -> None: ...
    def restart(self) -> None: ...
```

设计说明：

- 实时游戏与回合制不同，`step` 每帧调用一次，参数为“本帧至多一个操作 + 本帧毫秒数”。
- sim 内部对重力与锁定做时间累计，保证测试可以精确传 `dt_ms` 推进。
- 消行数不单独编码进事件，通过对比前后 `state.lines` 读取。
- 暂停是 app 层职责：暂停时主循环不调用 `step`，sim 不感知暂停。

## 6. 核心算法

### 6.1 方块定义（出生态坐标，相对原点；x 向右 / y 向下）

| 方块 | 格子坐标 |
| --- | --- |
| I | (−1,0) (0,0) (1,0) (2,0) |
| J | (−1,−1) (−1,0) (0,0) (1,0) |
| L | (1,−1) (−1,0) (0,0) (1,0) |
| O | (0,0) (1,0) (0,1) (1,1) |
| S | (0,−1) (1,−1) (−1,0) (0,0) |
| T | (−1,0) (0,−1) (0,0) (1,0) |
| Z | (−1,−1) (0,−1) (0,0) (1,0) |

原点约定：JLSTZ 取 3×3 包围盒中心；I 取 4×4 包围盒左数第 2 格、上数第 2 格；
O 取自身 2×2 左上角格。

### 6.2 旋转公式（绕原点，屏幕坐标 y 向下）

- 顺时针：`(x, y) -> (-y, x)`
- 逆时针：`(x, y) -> (y, -x)`

### 6.3 SRS 踢墙表（官方 y 向上；应用时 y 坐标取反）

JLSTZ 踢墙表：

| 转换 | 偏移序列 |
| --- | --- |
| 0→R | (0,0) (−1,0) (−1,+1) (0,−2) (−1,−2) |
| R→0 | (0,0) (+1,0) (+1,−1) (0,+2) (+1,+2) |
| R→2 | (0,0) (+1,0) (+1,−1) (0,+2) (+1,+2) |
| 2→R | (0,0) (−1,0) (−1,+1) (0,−2) (−1,−2) |
| 2→L | (0,0) (+1,0) (+1,+1) (0,−2) (+1,−2) |
| L→2 | (0,0) (−1,0) (−1,−1) (0,+2) (−1,+2) |
| L→0 | (0,0) (−1,0) (−1,−1) (0,+2) (−1,+2) |
| 0→L | (0,0) (+1,0) (+1,+1) (0,−2) (+1,−2) |

I 踢墙表：

| 转换 | 偏移序列 |
| --- | --- |
| 0→R | (0,0) (−2,0) (+1,0) (−2,−1) (+1,+2) |
| R→0 | (0,0) (+2,0) (−1,0) (+2,+1) (−1,−2) |
| R→2 | (0,0) (−1,0) (+2,0) (−1,+2) (+2,−1) |
| 2→R | (0,0) (+1,0) (−2,0) (+1,−2) (−2,+1) |
| 2→L | (0,0) (+2,0) (−1,0) (+2,+1) (−1,−2) |
| L→2 | (0,0) (−2,0) (+1,0) (−2,−1) (+1,+2) |
| L→0 | (0,0) (+1,0) (−2,0) (+1,−2) (−2,+1) |
| 0→L | (0,0) (−1,0) (+2,0) (−1,+2) (+2,−1) |

应用流程：

1. 用 §6.2 公式计算旋转后的格子集合。
2. 依次尝试表内偏移：将方块原点加上 `(kx, -ky)`（官方表 y 向上，屏幕取反）。
3. 偏移后所有格子无碰撞 → 旋转成功（状态改变 + 原点移动该偏移）。
4. 全部偏移失败 → 旋转不生效，状态与位置不变。

### 6.4 发牌器（随机算法）

发牌器统一实现 `Randomizer` 协议（`next` / `save_queue` / `load_queue`），
由配置 `randomizer.mode` 选择具体算法，`Game` 通过工厂 `create_randomizer(mode, seed)`
创建实例，不感知算法细节。三种模式：

| 模式 | 行为 | 存档语义 |
| --- | --- | --- |
| `seven_bag` | 维护洗牌后的 7 种方块列表；取空后重新洗牌；每 7 个连续出块恰好包含全部 7 种各一次 | `save_queue` 保存完整袋余量，`load_queue` 可精确还原发牌序列 |
| `uniform` | 每次独立等概率抽取七种之一（真随机，允许连续同块） | 无袋队列：`save_queue` 恒为空，不还原序列 |
| `no_repeat` | 以 7-bag 为基础，跨袋衔接时调整首块，保证任意连续两次不出同一方块 | `save_queue` 保存袋余量；`load_queue` 不恢复“上一块”记忆，仅保证免重复性质 |

- `save_queue` / `load_queue` 均校验“无重复、长度 ≤ 7”。
- 相同 `seed` 下序列可复现；`seed=None` 表示不可复现的随机源。

### 6.5 碰撞检测

- 格子 `x` 越界（<0 或 ≥ cols）、`y` 越界（≥ rows）→ 碰撞。
- `y < 0` 视为空（虚拟出生区），不碰撞。
- 目标格已占（非 None）→ 碰撞。

### 6.6 重力与锁定

- 重力：每帧累加 `dt_ms`，达到当前等级下落间隔则下落一格。
- 自然落地：下落被阻挡后启动锁定计时；玩家成功移动/旋转可重置计时，
  但累计重置次数超过 `lock_reset_limit` 后立即锁定（防无限拖延）。
- 软降：按下 ↓ 期间按 `soft_drop_interval_ms` 下落，每格 +1 分；软降触底立即锁定。
- 硬降：一次落到底部，每格 +2 分，立即锁定。
- 锁定：写入棋盘 → 触发 `PIECE_LOCK` → 消行 → 重置 `hold_used` → 生成下一个方块。

### 6.7 消行

- 扫描全部行，满行（10 格均非 None）标记为消除。
- 自上而下重建棋盘：保留未消除行，顶部补空行。
- 同时消除 n 行时，计分按 n 的档位一次计算（不逐行累加）。

### 6.8 计分与等级

- `score += line_clear[n] * level`（n = 本次消行数）。
- `lines` 每满 `lines_per_level` 格提升一级；等级参与速度查表与消行计分。
- 速度取 `gravity_ms_per_level[min(level, max_level)]`。

### 6.9 结束判定

- 锁定并消行后生成新方块；若新方块在出生位置（含 `y >= 0` 的格子）与棋盘碰撞，
  则 `game_over = True` 并触发一次 `GAME_OVER`。此后 `step` 不再处理动作。

## 7. UI 与输入

### 7.1 布局

```
+------------------+----------+
|                  |  HOLD    |
|     棋盘 10×20    |  NEXT×3  |
|    （格 30px）    |          |
|                  |  SCORE   |
|                  |  LEVEL   |
|                  |  LINES   |
+------------------+----------+
```

窗口约 560×640；棋盘区左侧 300×600，右侧 220px 面板，四周留边距。

### 7.2 按键映射

| 按键 | 动作 |
| --- | --- |
| ← / → | 左移 / 右移 |
| ↓ | 软降（按下开始、松开结束） |
| 空格 | 硬降 |
| ↑ / X | 顺时针旋转 |
| Z / Ctrl | 逆时针旋转 |
| C / Shift | 保持 |
| P | 暂停（app 层处理） |
| R | 重开（app 层重建 Game） |
| Esc | 退出 |

### 7.3 DAS/ARR 输入处理

- `eblock/tetris/ui/input.py` 每帧查询 `pygame.key.get_pressed()`，
  按配置节奏发射 `MOVE_LEFT/RIGHT`：
  按下瞬间发射一次；持续按住超过 `das_ms` 后，每 `arr_ms` 再发射一次。
- 释放按键即清除该方向状态；同一帧最多产出一个移动 action。
- 软降用按下/松开事件转换为 `SOFT_DROP_START / SOFT_DROP_END`。

### 7.4 绘制

- 每方块类型一种颜色（I 青、O 黄、T 紫、S 绿、Z 红、J 蓝、L 橙），深色背景 + 浅色网格线。
- Ghost：当前方块下落投影，画成半透明轮廓，位置取 `state.ghost_y`。
- 文本用 pygame 默认字体，不引入外部素材；暂停与结束画面显示按键提示。

## 8. 存档：高分

- 文件 `saves/highscores.json`：`{ "<模式键>": { "score": int, "level": int, "lines": int, "date": str } }`。
- **模式键** = `<发牌模式>_<出生旋转>`，例如 `seven_bag_fixed`、`uniform_random`；
  不同模式键的最高分独立记录，互不影响。
- 对局结束（GAME_OVER）时，按当前模式键提交成绩；严格高于该模式已存纪录才覆盖。
- 读取时逐条校验字段类型；整文件损坏或单条非法 → 回退/跳过并打印警告，不崩溃。
- v1 每个模式只存最高一条，不做排行榜与中局存档。

## 9. 测试计划

| 模块 | 关键用例 |
| --- | --- |
| tetromino | 7 种方块各 4 格；出生态坐标与文档一致；旋转状态转换不丢格 |
| rotation | T 顺/逆时针各转一次结果正确；I 水平↔垂直；贴墙 0→R 踢墙生效；全部偏移失败时旋转被拒绝 |
| board | 左右/下越界与重叠碰撞；空棋盘可放置；y<0 视为空 |
| board 消行 | 同时消 1/2/3/4 行棋盘重建正确；上方行正确下移；无残留悬空格 |
| randomizer | 多模式：7-bag 每 7 个一组全排列；uniform 独立等概率；no_repeat 连续两次不重复；save/load 还原与校验 |
| scoring | 各档消行 × 等级正确；软降/硬降加分正确；等级升级时机正确 |
| game | 重力按 dt 累计下落；触地锁定延迟与重置上限；软降触底立即锁定；硬降立即到底；hold 每落一次限一次；出生碰撞 → 仅一次 GAME_OVER |
| highscore | 按模式键独立记录；保存/读取往返一致；损坏文件回退默认值 |

静态检查门槛：`ruff check .`、`ruff format --check .`、`mypy src`（strict）、`pytest`，
每次提交前必须全绿。

## 10. 实施步骤与里程碑

按每周 10+ 小时估算，总工期 2～3 周：

- M1（约 1 周）sim 层全部完成：tetromino → rotation → board → randomizer → scoring →
  game，配套测试全绿；提交 `feat(sim): 俄罗斯方块核心逻辑与测试`。
- M2（约 1 天）save 高分完成；提交 `feat(save): 最高分持久化`。
- M3（3～5 天）向 pyproject 添加 pygame 依赖；ui/renderer + ui/input + app/main 装配完成，
  可完整游玩一局；提交 `feat(ui): Pygame 渲染与输入`。
- M4（2～3 天）打磨：暂停/结束画面、配色微调、按 §3.1 调整手感参数并复验；
  提交 `feat(app): 主循环装配与打磨`。

## 11. 验收标准

- 工程：四项检查全绿；`sim` 可脱离 pygame 独立运行与测试；配置全部外置且校验器覆盖错误路径。
- 玩法：完整一局从开始到结束；重开、暂停、高分持久化正常。
- 规则：发牌模式由配置决定且三种算法行为符合 §6.4 定义；T/I 贴墙、贴地旋转踢墙生效；
  hold 每落一次限一次；ghost 位置与硬降落点一致；不同模式高分独立。
- 手感：修改 `config/tetris.json` 中的 das/arr/gravity 后实际生效。

## 12. 决策记录与假设

- 采用 SRS + 7-bag + hold + ghost（标准 guideline 子集）；T-spin/combo/B2B 明确排除。
- 发牌器做成可插拔：`Randomizer` 协议 + `create_randomizer` 工厂，模式由配置决定；
  `uniform` 不持久化随机数状态，`no_repeat` 只恢复袋余量、不恢复“上一块”记忆。
- 方块形状与踢墙表是规则常量放代码；分数/速度/延迟等调参值放 config。
- 中局存档不做，只持久化最高分；暂停归 app 层，sim 不感知。
- 出生原点统一 `(4, 0)`，允许格子位于 `y = -1`，保证出生完全隐藏且逻辑统一。
- 出生方向默认固定，可配置为随机旋转；该开关是玩法选项，随模式键参与高分隔离。
- 软降触底立即锁定；自然落地走锁定延迟；O 方块无踢墙表。
- 文档与注释用中文，代码标识符用英文；颜色仅作展示，不属于游戏数值。
