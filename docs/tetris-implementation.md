# 俄罗斯方块（Tetris）实施指南

阶段 0 热身游戏的**分步实施指南**，供你照着自写代码。
规则定义见 [tetris-warmup.md](tetris-warmup.md)（开发文档）；本指南只回答“怎么做”，
不回答“是什么”。两者冲突时，以开发文档为准，并回头修订本指南。

## 当前进度（2026-08-15 更新）

| 步骤 | 内容 | 状态 | 说明 |
| --- | --- | --- | --- |
| M0 | 配置文件与测试目录 | ✅ 完成 | `config/tetris.json` 与 `tests/tetris/` 已建 |
| M1-S1 | `config.py` | ✅ 完成 | 含新增 `randomizer.mode` / `spawn_random_rotation` 校验 |
| M1-S2 | `tetromino.py` | ✅ 完成 | 代码与 `test_tetromino.py` 均存在 |
| M1-S3 | `rotation.py` | ✅ 完成 | 代码与 `test_rotation.py` 均存在 |
| M1-S4 | `board.py` | ✅ 完成 | 代码与 `test_board.py` 均存在 |
| M1-S5 | `randomizer.py` | ✅ 完成 | 三种发牌模式 + 工厂 + `test_randomizer.py` |
| M1-S6 | `scoring.py` | ⬜ 未开始 | 计分、等级、速度查表 |
| M1-S7 | `game.py` | ⬜ 未开始 | 状态机；将消费 `randomizer.mode` 与 `spawn_random_rotation` |
| M2 | `highscore.py` | ✅ 完成 | 按模式键独立计录 + `test_highscore.py` |
| M3 | UI 与装配 | ⬜ 未开始 | pygame 依赖、input、renderer、main |
| M4 | 打磨与调优 | ⬜ 未开始 | 画面完善、手感调优、最终验收 |

**维护约定**：每完成一步，把本表状态改为 ✅ 并更新日期；提交时对照各步
“完成检查清单”逐项核对。

## 下一步执行计划（2026-08-15）

按顺序执行；每步遵循 §0.1 的 TDD 流程（红灯 → 绿灯 → 四项检查全绿）。

1. **M1-S6**：`scoring.py`，四个纯函数（计分、等级、速度查表）。
2. **M1-S7**：`game.py`，状态机（用例最多的一步，约 30 个），完成 sim 层；
   构造时用 `create_randomizer(config.randomizer.mode, seed)`，出生时按
   `spawn_random_rotation` 决定初始旋转状态。
3. **M3/M4**：UI 与装配、打磨（含高分按模式键提交）。
4. **清理与提交 M1**：
   - 删除 `tests/data.py`（临时数据文件，其内容已被模块内常量取代）；
   - 重新 `git add` 本次涉及文件（此前暂存区里是旧版本），随后按 §1 的建议
     提交 `feat(sim): 俄罗斯方块核心逻辑与测试`。

**待决事项**（不阻塞上述步骤，可随时讨论）：
- `config.py` 的 `_load_gravity_ms_per_level` 要求键**严格按顺序**等于
  1..max_level，而 S1 规格只要求“连续覆盖”。当前实现更严格：若打算保留严格
  校验，应把规格同步改严；否则应放宽实现（用集合比较）。

## 0. 如何使用本指南

### 0.1 每步流程（全程 TDD）

1. 读本步“接口规格”与“边界情况”，不急着写实现。
2. 在指定测试文件里写测试（用例名照抄清单），运行 `pytest` 确认失败（红灯）。
3. 写实现直到测试通过（绿灯）。
4. 运行四项检查，全部通过。
5. 对照“完成检查清单”逐项核对。
6. 由你自己执行 git 提交（提交信息建议照抄各里程碑标题）。

### 0.2 工程纪律（每次提交前必须全绿）

```powershell
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
.venv\Scripts\mypy src
.venv\Scripts\pytest
```

如果 `ruff format --check` 报“would be reformatted”，先运行
`.venv\Scripts\ruff format .` 再复验。注意：ruff 也会格式化 Markdown 内嵌代码块，
这是预期行为。

### 0.3 分层铁律

- `src/eblock/tetris/sim/` 内任何文件**不得导入 pygame**。
- `ui` 只读状态、转发输入，不直接修改游戏数据；一切变更走 `Game.step(action, dt_ms)`。
- `save` 只依赖标准库。
- 依赖方向：sim ← ui ← app。

### 0.4 目标目录结构（完成后）

```
src/eblock/tetris/
├── __init__.py
├── config.py          # M1-S1
├── sim/
│   ├── __init__.py
│   ├── tetromino.py   # M1-S2
│   ├── rotation.py    # M1-S3
│   ├── board.py       # M1-S4
│   ├── randomizer.py  # M1-S5
│   ├── scoring.py     # M1-S6
│   └── game.py        # M1-S7
├── ui/
│   ├── __init__.py
│   ├── input.py       # M3
│   └── renderer.py    # M3
├── app/
│   ├── __init__.py
│   └── main.py        # M3
└── save/
    ├── __init__.py
    └── highscore.py   # M2
config/tetris.json     # M0
tests/tetris/          # M0 起逐步添加测试文件
```

## 1. 总览：里程碑与步骤

| 里程碑 | 内容 | 步骤 | 预计工期 |
| --- | --- | --- | --- |
| M0 | 准备：配置文件与测试目录 | 0.1 配置文件、0.2 目录清理 | 约 1 天 |
| M1 | sim 层：纯逻辑 + 测试 | S1 config → S7 game | 约 1 周 |
| M2 | 高分存档（模式独立） | highscore.py | 约 1 天 |
| M3 | UI、输入与装配 | pygame 依赖、input、renderer、main | 3～5 天 |
| M4 | 打磨与调优 | 画面完善、手感调优、最终验收 | 2～3 天 |

提交建议：M1 结束提交 `feat(sim): 俄罗斯方块核心逻辑与测试`；M2 结束提交
`feat(save): 最高分持久化`；M3 结束提交 `feat(ui): Pygame 渲染与输入`；
M4 结束提交 `feat(app): 主循环装配与打磨`。

## 2. M0 准备

### 0.1 创建 config/tetris.json

新建文件 `config/tetris.json`，内容**逐字粘贴**：

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
  "preview_count": 3
}
```

**字段含义**：

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
| `preview_count` | 右侧面板显示的下一个方块预览数量 |

### 0.2 测试目录与残留清理

1. 新建 `tests/tetris/` 目录（本步先不建 `__init__.py`，pytest 无需它）。
2. 确认 `src/eblock/` 下只有 `tetris/` 一个子包；若存在重构残留的
   `app/`、`save/`、`sim/`、`ui/` 空目录，删除它们（Git 不跟踪空目录，删除后
   `git status` 不应显示变化）。
3. 确认 `.gitignore` 已排除 `__pycache__/`（已配置，无需改动）。

完成检查清单：

- `config/tetris.json` 存在且 JSON 可解析（可用编辑器校验）。
- `src/eblock/` 下只有 `tetris/`。
- 四项检查仍全绿（现有 `tests/test_smoke.py` 通过）。

## 3. M1 sim 层（TDD，7 步）

### S1 config.py

**目标**：把 JSON 数值加载为强类型冻结数据类，加载即校验，错误带字段路径。

**新文件**：`src/eblock/tetris/config.py`

**接口规格**：

```python
class ConfigError(ValueError):
    """配置非法。消息格式：配置错误: <字段路径>: <原因>。"""


@dataclass(frozen=True)
class BoardConfig:
    cols: int
    rows: int
    visible_rows: int
    spawn_x: int
    spawn_y: int


@dataclass(frozen=True)
class ScoringConfig:
    line_clear: dict[int, int]
    soft_drop_per_cell: int
    hard_drop_per_cell: int
    lines_per_level: int
    start_level: int


@dataclass(frozen=True)
class TimingConfig:
    lock_delay_ms: int
    lock_reset_limit: int
    soft_drop_interval_ms: int


@dataclass(frozen=True)
class InputConfig:
    das_ms: int
    arr_ms: int


RandomizerMode = Literal["seven_bag", "uniform", "no_repeat"]


@dataclass(frozen=True)
class RandomizerConfig:
    mode: RandomizerMode


@dataclass(frozen=True)
class TetrisConfig:
    board: BoardConfig
    scoring: ScoringConfig
    gravity_ms_per_level: dict[int, int]
    max_level: int
    timing: TimingConfig
    input: InputConfig
    randomizer: RandomizerConfig
    spawn_random_rotation: bool
    preview_count: int


DEFAULT_CONFIG_PATH: Path = Path(__file__).resolve().parents[3] / "config" / "tetris.json"


def load_config(path: Path) -> TetrisConfig: ...
def load_default_config() -> TetrisConfig: ...
```

**校验规则**（每个失败抛 `ConfigError`，消息含字段路径）：

- `board.cols` 4–20 的整数；`board.rows` ≥ 20；`board.visible_rows` 1 ≤ v ≤ rows；
  `board.spawn_x` ∈ [0, cols)；`board.spawn_y` ∈ [0, rows)。
- `scoring.line_clear` 的键必须恰好是 1、2、3、4（JSON 中是字符串，先转 int），
  值均为正整数；`soft_drop_per_cell`、`hard_drop_per_cell`、
  `lines_per_level` 为正整数；`start_level` ∈ [1, max_level]。
- `gravity_ms_per_level` 的键转 int 后必须连续覆盖 1..max_level，值均为正数。
- `timing.lock_delay_ms` ∈ [100, 2000]；`lock_reset_limit` ≥ 0；
  `soft_drop_interval_ms` ≥ 1。
- `input.das_ms` ∈ [0, 500]；`arr_ms` ∈ [0, 200]。
- `randomizer.mode` 必须是 `seven_bag` / `uniform` / `no_repeat` 之一。
- `spawn_random_rotation` 必须是布尔值（JSON true/false；数字 0/1 拒绝）。
- `preview_count` ≥ 1。
- 缺失字段、类型错误、JSON 语法错误同样抛 `ConfigError`（JSON 语法错误路径记
  顶层 `tetris.json`）。

**边界情况**：JSON 键是字符串需要转 int；转失败要报该字段路径；字段缺失要报路径；
`load_config` 对不存在的文件直接让 `FileNotFoundError` 冒泡（不属于配置非法）。

**测试文件**：`tests/tetris/test_config.py`

- `test_load_default_config_ok`：默认配置各字段与文档一致。
- `test_load_valid_config_ok`：临时文件加载成功。
- `test_cols_out_of_range_reports_path`：cols=21 → ConfigError，消息含 `board.cols`。
- `test_rows_below_20_rejected`。
- `test_line_clear_missing_key_rejected`：缺少 "4"。
- `test_line_clear_non_positive_rejected`。
- `test_gravity_keys_not_continuous_rejected`。
- `test_lock_delay_out_of_range_rejected`。
- `test_das_out_of_range_rejected`。
- `test_randomizer_mode_invalid_rejected`：未知模式 → 消息含 `randomizer.mode`。
- `test_spawn_random_rotation_int_rejected`：1 不是布尔 → 类型错误。
- `test_preview_count_zero_rejected`。
- `test_missing_field_reports_path`。
- `test_json_syntax_error_reports_top_level`。

完成检查清单：所有用例绿；四项检查绿；`load_default_config()` 可直接运行。

### S2 tetromino.py

**目标**：定义方块类型、出生态形状、放置状态。

**新文件**：`src/eblock/tetris/sim/tetromino.py`

**接口规格**：

```python
Cells = tuple[tuple[int, int], ...]  # 相对原点的格子集合，x 向右 / y 向下


class PieceType(Enum):
    I = auto()
    O = auto()
    T = auto()
    S = auto()
    Z = auto()
    J = auto()
    L = auto()


# 出生态（rotation=0）坐标，逐字采用开发文档 §6.1 表格
SPAWN_SHAPES: dict[PieceType, Cells]


@dataclass(frozen=True)
class PieceState:
    piece_type: PieceType
    rotation: int  # 0 / 1 / 2 / 3（顺时针递增）
    x: int
    y: int


def spawn_cells(piece_type: PieceType) -> Cells: ...
```

`spawn_cells` 返回 `SPAWN_SHAPES[piece_type]`（可返回原元组，无需复制）。

**边界情况**：每种方块恰好 4 格；坐标与开发文档 §6.1 完全一致；
rotation 状态合法值 0..3（本模块只存数据，旋转计算在 rotation.py）。

**测试文件**：`tests/tetris/test_tetromino.py`

- `test_piece_type_has_seven_members`。
- `test_spawn_shapes_have_exactly_four_cells`：遍历 7 种。
- `test_spawn_shapes_match_documentation`：7 种各断言与 §6.1 表格逐格一致
  （用集合比较，顺序不敏感）。
- `test_piece_state_is_frozen`：修改字段抛异常（可选，若用 frozen dataclass 必然通过）。

完成检查清单：用例绿；四项检查绿。

### S3 rotation.py

**目标**：旋转公式 + SRS 踢墙表，用依赖注入做碰撞检测，不依赖 board。

**新文件**：`src/eblock/tetris/sim/rotation.py`

**接口规格**：

```python
from eblock.tetris.sim.tetromino import Cells, PieceState, PieceType

# 官方表 y 向上；应用时 y 取反。键为 (from_rotation, to_rotation)
KICK_TABLE: dict[tuple[int, int], tuple[tuple[int, int], ...]]


def rotate_cells(piece_type: PieceType, rotation: int, cw: bool) -> Cells:
    """返回旋转到指定状态的相对格子；O 恒等于出生态。"""


def cells_at_rotation(piece_type: PieceType, rotation: int) -> Cells:
    """返回 piece_type 在任意 rotation 0..3 下的相对格子。"""


CollisionCheck = Callable[[int, int, Cells], bool]


def try_rotation(
    current: PieceState,
    cw: bool,
    collides: CollisionCheck,
) -> PieceState:
    """尝试旋转+踢墙；成功返回新状态，全部失败返回原状态（原对象）。"""
```

行为规则：

- 新旋转 = `(current.rotation + (1 if cw else -1)) % 4`。
- 先算 `cells_at_rotation(piece_type, new_rotation)`。
- O 方块：直接尝试偏移 (0,0)，成功即返回（无踢墙表）。
- 其余方块：查 `KICK_TABLE[(old_rot, new_rot)]`，逐个偏移 `(kx, -ky)` 尝试
  `collides(x + kx, y - ky, cells)`；第一个不碰撞的偏移即成功。
- 全部失败：返回 `current` 本身（状态与位置不变）。

踢墙表数据：JLSTZ 与 I 各 8 行，**逐字采用开发文档 §6.3**（注意 O 无表）。
实现时表内偏移直接按文档写（y 向上），应用时 `y` 取反。

**边界情况**：T 顺/逆时针各转一次；I 水平↔垂直（0→1 与 1→0）；
贴左墙 0→R 用 (−1,0) 踢动成功；某偏移使 y 变化时符号正确（如 (0,−2) → 屏幕 y+2）；
连续旋转 4 次回到原格子集合；全部踢墙失败时返回原对象。

**测试文件**：`tests/tetris/test_rotation.py`

- `test_rotate_cells_t_cw_matches_formula`。
- `test_rotate_cells_t_ccw_matches_formula`。
- `test_rotate_cells_i_horizontal_to_vertical`。
- `test_rotate_cells_o_unchanged`。
- `test_four_cw_rotations_return_to_original_cells`。
- `test_try_rotation_succeeds_in_open_space`。
- `test_try_rotation_kick_at_left_wall`：collides 模拟左墙，断言位置左移 1。
- `test_kick_y_offset_is_flipped`：构造只有 (0,−2) 可行的场景，断言新 y = 旧 y + 2。
- `test_try_rotation_all_kicks_fail_returns_same_object`：断言 `is current`。

完成检查清单：用例绿；四项检查绿；本模块无 board/pygame 导入。

### S4 board.py

**目标**：棋盘存储、碰撞检测、落子、消行，全部不可变。

**新文件**：`src/eblock/tetris/sim/board.py`

**接口规格**：

```python
from eblock.tetris.sim.tetromino import Cells, PieceType

Board = tuple[tuple[PieceType | None, ...], ...]


def empty_board(rows: int, cols: int) -> Board: ...


def collides(board: Board, x: int, y: int, cells: Cells) -> bool:
    """cells 为相对格；任一格越界或占位即碰撞；y<0 的格视为空。"""


def place(board: Board, piece_type: PieceType, x: int, y: int, cells: Cells) -> Board:
    """写入全部 y>=0 的格；y<0 的格忽略。返回新棋盘。"""


def clear_lines(board: Board) -> tuple[Board, int]:
    """消除满行，返回 (新棋盘, 消除行数)。"""
```

行为规则：

- 碰撞：`board_x < 0`、`board_x >= cols`、`board_y >= rows` 或
  `board[board_y][board_x] is not None`；`board_y < 0` 永远不碰撞。
- `clear_lines`：满行 = 10 格全部非 None；自上而下保留未满行、顶部补空行；
  返回新棋盘（原棋盘不变）。

**边界情况**：左右墙与底部碰撞；叠放碰撞；y<0 视为空；
同时消 1/2/3/4 行；多行消除时上方行整体下移且顺序不变；消除后无悬空。

**测试文件**：`tests/tetris/test_board.py`

- `test_empty_board_dimensions`：22×10 全 None。
- `test_collides_left_wall` / `test_collides_right_wall` / `test_collides_floor`。
- `test_collides_existing_stack`。
- `test_negative_y_never_collides`。
- `test_place_writes_occupied_cells`。
- `test_place_ignores_negative_y_cells`。
- `test_clear_lines_no_clear_returns_same_shape`。
- `test_clear_lines_single`：构造满行，断言消除数与棋盘。
- `test_clear_lines_four`（Tetris）。
- `test_clear_lines_keeps_row_order`：上方残留行顺序不变。
- `test_clear_lines_returns_new_object`：原棋盘未被修改。

完成检查清单：用例绿；四项检查绿。

### S5 randomizer.py

**目标**：多模式发牌器（7-bag / 均匀随机 / 免连续重复），支持存档还原，
由配置 `randomizer.mode` 决定算法，`Game` 只依赖统一协议。

**新文件**：`src/eblock/tetris/sim/randomizer.py`

**接口规格**：

```python
from typing import Protocol

from eblock.tetris.config import RandomizerMode
from eblock.tetris.sim.tetromino import PieceType


class Randomizer(Protocol):
    def next(self) -> PieceType: ...
    def save_queue(self) -> tuple[PieceType, ...]: ...
    def load_queue(self, queue: tuple[PieceType, ...]) -> None: ...


class SevenBag:  # 模式 seven_bag
    def __init__(self, seed: int | None = None) -> None:
        """内部使用 random.Random(seed)；seed=None 表示随机。"""

    def next(self) -> PieceType: ...
    def save_queue(self) -> tuple[PieceType, ...]: ...
    def load_queue(self, queue: tuple[PieceType, ...]) -> None: ...


class UniformRandom:  # 模式 uniform
    def __init__(self, seed: int | None = None) -> None: ...
    def next(self) -> PieceType: ...
    def save_queue(self) -> tuple[PieceType, ...]: ...
    def load_queue(self, queue: tuple[PieceType, ...]) -> None: ...


class NoRepeat:  # 模式 no_repeat
    def __init__(self, seed: int | None = None) -> None: ...
    def next(self) -> PieceType: ...
    def save_queue(self) -> tuple[PieceType, ...]: ...
    def load_queue(self, queue: tuple[PieceType, ...]) -> None: ...


def create_randomizer(mode: RandomizerMode, seed: int | None = None) -> Randomizer: ...
```

行为规则：

- `seven_bag`：袋空时生成 `list(PieceType)` 并 `rng.shuffle`；`next()` 从袋尾
  弹出（O(1)）；每 7 个连续出块恰为全排列。
- `uniform`：每次 `rng.choice` 独立等概率抽取七种之一；不维护袋队列，
  `save_queue()` 恒返回空元组，`load_queue()` 只接受空队列（非空抛 ValueError）。
- `no_repeat`：以 7-bag 为基础，跨袋衔接时若袋首块与上一块相同则与袋内
  第二格交换，保证任意连续两次不出同一方块。
- 队列型模式（seven_bag / no_repeat）：`save_queue()` 返回当前袋余量的元组副本；
  `load_queue()` 用给定队列替换袋余量，校验无重复、长度 ≤ 7；空队列合法，
  下次 `next()` 自动补袋。no_repeat 的 `load_queue()` 清空“上一块”记忆。
- `create_randomizer` 工厂按 mode 返回对应实例；未知模式抛 ValueError
  （配置层已拦截，防御性保留）。
- 相同 seed 序列一致；`seed=None` 表示不可复现的随机源。

**边界情况**：每 7 个连续出块恰为全排列；相同 seed 序列一致；
save→load 后 `next()` 序列与未保存前一致；load 空队列后可继续发牌；
uniform 载入非空队列拒绝；no_repeat 连续 500 次无相邻重复；
队列含重复或长度 > 7 拒绝。

**测试文件**：`tests/tetris/test_randomizer.py`

- `test_every_7_draws_is_permutation`：1000 次抽样，每 7 个窗口含全部 7 种各一次。
- `test_same_seed_same_sequence`。
- `test_save_load_restores_sequence`：取 3 个后保存，load 后继续取 4 个，
  与直接取 7 个的对应片段一致。
- `test_load_queue_validates_duplicates` / `test_load_queue_too_long_rejected`。
- `test_load_empty_queue_refills`。
- `test_uniform_returns_valid_pieces` / `test_uniform_save_queue_is_empty` /
  `test_uniform_load_empty_queue_ok` / `test_uniform_load_non_empty_rejected`。
- `test_no_repeat_no_consecutive_duplicates` / `test_no_repeat_same_seed_same_sequence` /
  `test_no_repeat_save_load_restores_queue` / `test_no_repeat_load_queue_validates_duplicates`。
- `test_create_randomizer_returns_correct_instance` / `test_create_randomizer_unknown_mode_raises`。

完成检查清单：用例绿；四项检查绿。

### S6 scoring.py

**目标**：计分、等级、速度查表，全部纯函数。

**新文件**：`src/eblock/tetris/sim/scoring.py`

**接口规格**：

```python
from collections.abc import Mapping


def line_clear_score(lines_cleared: int, level: int, table: Mapping[int, int]) -> int:
    """table[lines_cleared] * level。"""


def soft_drop_score(cells: int, per_cell: int) -> int: ...
def hard_drop_score(cells: int, per_cell: int) -> int: ...


def level_after_lines(
    lines: int,
    lines_per_level: int,
    start_level: int,
) -> int:
    """start_level + lines // lines_per_level。"""


def gravity_interval_ms(
    level: int,
    table: Mapping[int, int],
    max_level: int,
) -> int:
    """table[min(level, max_level)]。"""
```

**边界情况**：lines_cleared 只可能是 1..4（调用方保证，本模块不校验）；
lines=9 → 等级不变，lines=10 → +1；level 超过 max_level 时按 max_level 查表。

**测试文件**：`tests/tetris/test_scoring.py`

- `test_line_clear_score_table`：100/300/500/800 × 1。
- `test_line_clear_multiplies_level`：level=3 时 1 行 = 300。
- `test_soft_drop_and_hard_drop_scores`。
- `test_level_progression`：0→1、9→1、10→2、19→2、20→3（start_level=1）。
- `test_gravity_interval_capped_at_max_level`：level 11 与 10 相同。

完成检查清单：用例绿；四项检查绿。

### S7 game.py

**目标**：状态机，统一每帧入口 `step(action, dt_ms)`，产出事件与不可变快照。

**新文件**：`src/eblock/tetris/sim/game.py`

**接口规格**：

```python
from eblock.tetris.config import TetrisConfig
from eblock.tetris.sim.board import Board
from eblock.tetris.sim.randomizer import Randomizer, create_randomizer
from eblock.tetris.sim.tetromino import PieceState, PieceType


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
class GameState:
    board: Board
    current: PieceState
    ghost_y: int
    next_queue: tuple[PieceType, ...]
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
    def __init__(self, config: TetrisConfig, seed: int | None = None) -> None: ...
    def step(self, action: Action | None, dt_ms: int) -> StepResult: ...
    def to_state(self) -> GameState: ...
    def load_state(self, state: GameState) -> None: ...
    def restart(self) -> None: ...
```

**内部字段**：

`_config`、`_board: Board`、`_current: PieceState`、`_randomizer: Randomizer`、
`_hold: PieceType | None`、`_hold_used: bool`、`_score: int`、`_level: int`、
`_lines: int`、`_game_over: bool`、`_gravity_accum_ms: int`、
`_soft_accum_ms: int`、`_soft_active: bool`、`_grounded: bool`、
`_lock_accum_ms: int`、`_lock_reset_count: int`。

构造时：`_randomizer = create_randomizer(config.randomizer.mode, seed)`；
出生初始旋转状态 = 0（固定方向）或 `rng.randrange(4)`（当
`config.spawn_random_rotation=true` 时随机取 0..3）。

**每帧处理顺序**（`step` 内严格按此序）：

1. 若 `_game_over`：直接返回 `StepResult((), to_state())`，不处理任何输入与计时。
2. 处理 `action`（见动作表）。
3. 软降计时：`_soft_active` 时累加 dt，每满 `soft_drop_interval_ms` 尝试下移一格；
   成功则 `_score += soft_drop_per_cell` 并继续；失败则**立即锁定**并跳过第 4、5 步。
4. 重力计时：仅 `not _grounded` 时累加 dt，每满当前等级间隔尝试下移一格；
   成功后重查是否接地；失败则 `_grounded = True`、重力累加清零。
5. 锁定计时：`_grounded` 时累加 dt，达到 `lock_delay_ms` 则锁定。
6. 锁定流程（见锁定表）。
7. 返回 `StepResult(tuple(events), to_state())`。

**动作表**：

| action | 行为 |
| --- | --- |
| MOVE_LEFT/RIGHT | 尝试 x±1；成功则更新位置、重查接地；若接地则锁定计时清零、`_lock_reset_count += 1`，超过 `lock_reset_limit` 立即锁定 |
| ROTATE_CW/CCW | `try_rotation(current, cw, collides)`；成功同上重置锁定计时并计数 |
| SOFT_DROP_START/END | 置/清 `_soft_active`；软降计时归零 |
| HARD_DROP | 计算下落距离 d（直到碰撞前），`_score += hard_drop_per_cell * d`，落到 y+d，立即锁定 |
| HOLD | `_hold_used` 时忽略；`_hold is None` 时：`_hold = current.piece_type`、从发牌器取新方块并 spawn（重置计时/接地/计数）；否则交换 current 与 `_hold`、`_hold_used = True`；两种分支都触发 HOLD_SWAP（首次为 None 时也触发）与 PIECE_SPAWN，并做出生碰撞检查 |

**锁定表**（锁定即执行，事件按此顺序追加）：

1. `place` 写入棋盘；追加 `PIECE_LOCK`。
2. `clear_lines`；若 cleared > 0：追加 `LINES_CLEARED`；
   `_score += line_clear_score(cleared, _level)`（**用旧等级**）；
   `_lines += cleared`；`new_level = level_after_lines(...)`；若升级则追加
   `LEVEL_UP` 并更新 `_level`。
3. `_hold_used = False`；清空锁定/接地/软降状态。
4. 从发牌器取下一个方块 spawn（初始旋转状态按 `spawn_random_rotation` 决定，
   见构造说明）；追加 `PIECE_SPAWN`。
5. 出生碰撞检查：若新方块（含 y≥0 的格）与棋盘碰撞 → `_game_over = True`，
   追加 `GAME_OVER`（整个对局仅此一次）。

**其他方法**：

- `to_state()`：`ghost_y = current.y + 下落距离`（下落距离 = 从当前位置连续下移
  直到碰撞前的步数）；`next_queue = _randomizer.save_queue()`（uniform 模式为空元组）。
- `load_state(state)`：恢复全部字段；`_randomizer.load_queue(state.next_queue)`；
  计时器全部清零、`_soft_active = False`、`_grounded = not 可下移`。
- `restart()`：等同于用新随机种子（seed=None）重新构造 Game。
- 初始化：空棋盘、`score=0`、`level=start_level`、`lines=0`，从发牌器 spawn 首块
  （不发射事件；空棋盘必然不碰撞）。

**可序列化约束**：`GameState` 的每个字段都是 int / str 无关的纯数据
（Board 是元组、PieceState 是冻结数据类、next_queue 是元组），不得含函数、
pygame 对象或随机数生成器引用。

**边界情况**：dt 一次跨多格（如 dt=5000 应下落 5 格）；软降与重力在同一帧互不干扰；
硬降距离 0 也锁定；HOLD 首次与交换分支的事件一致；game over 后 step 是 no-op；
load_state 后继续对局行为一致；next_queue 经 load_state 往返后发牌序列不变。

**测试文件**：`tests/tetris/test_game.py`

初始化：

- `test_initial_state`：score 0、level 1、lines 0、hold None、hold_used False、
  board 22×10 全空、current.rotation == 0、game_over False。

重力：

- `test_gravity_accumulates_by_dt`：999ms 不动、+1ms 后下移一格。
- `test_gravity_interval_uses_level_table`：level 2 用 793ms。
- `test_gravity_stops_when_grounded`：叠放后不再下落。
- `test_large_dt_moves_multiple_cells`。

移动：

- `test_move_left_right`。
- `test_move_blocked_by_wall` / `test_move_blocked_by_stack`：位置不变。
- `test_successful_move_resets_lock_timer`。
- `test_lock_reset_count_exceeding_limit_locks`：接地后第 16 次成功移动触发锁定。

旋转：

- `test_rotate_cw_updates_rotation`。
- `test_rotate_kick_at_wall`：贴墙旋转位置变化。
- `test_rotate_rejected_keeps_state`：全部踢墙失败，current 不变。

软降与硬降：

- `test_soft_drop_moves_and_scores`。
- `test_soft_drop_touch_bottom_locks_immediately`。
- `test_soft_drop_end_stops`。
- `test_hard_drop_lands_at_ghost_y`：硬降后 current.y == 之前 ghost_y。
- `test_hard_drop_scores_per_cell`。

锁定与消行：

- `test_lock_writes_board`。
- `test_lock_delay_after_grounding`：500ms 不锁、+1ms 锁。
- `test_clear_one_line_scores_100_times_level`。
- `test_clear_four_lines_scores_800_times_level`。
- `test_score_uses_old_level_before_level_up`：9 行后再四消，按旧等级计 800×1。
- `test_level_up_after_10_lines`。
- `test_lock_event_sequence`：PIECE_LOCK → LINES_CLEARED → LEVEL_UP → PIECE_SPAWN。

保持：

- `test_hold_first_time_takes_piece_and_spawns`。
- `test_hold_swap_returns_piece`。
- `test_hold_limited_once_per_drop`：锁定前第二次 HOLD 被忽略。
- `test_lock_resets_hold_used`。
- `test_hold_emits_hold_swap_and_spawn`。

结束：

- `test_game_over_when_spawn_collides`（用 load_state 构造）。
- `test_game_over_event_once`。
- `test_step_noop_after_game_over`：state 不变。

状态与事件：

- `test_to_state_load_state_roundtrip`：对局中途往返后 `to_state()` 相等。
- `test_load_state_preserves_bag_sequence`。
- `test_restart_resets_all`。
- `test_random_actions_10000_steps_no_crash`：随机动作长跑，断言不抛异常、
  分数非负、board 尺寸不变。
- `test_ghost_y_matches_hard_drop_landing`。

完成检查清单：

- 用例全绿；四项检查绿。
- `sim` 无 pygame 依赖验证：
  `Select-String -Path src\eblock\tetris\sim\*.py -Pattern 'pygame'` 无输出；
  `.venv\Scripts\python -c "import eblock.tetris.sim.game"` 正常。

## 4. M2 高分存档

**目标**：按模式键独立的最高分 JSON 持久化，损坏回退不崩溃。
模式键 = 发牌模式 + 出生旋转（`mode_key`），不同模式纪录互不影响。

**新文件**：`src/eblock/tetris/save/highscore.py`

**接口规格**：

```python
from collections.abc import Mapping
from pathlib import Path


DEFAULT_HIGHSCORE_PATH: Path  # <仓库根>/saves/highscores.json


@dataclass(frozen=True)
class HighScore:
    score: int
    level: int
    lines: int
    date: str  # ISO 格式，如 2026-08-06


def new_highscore(score: int, level: int, lines: int) -> HighScore:
    """date 取今天（datetime.date.today().isoformat()）。"""


def mode_key(randomizer_mode: str, spawn_random_rotation: bool) -> str:
    """返回 <发牌模式>_<fixed|random>，如 seven_bag_fixed。"""


def is_new_record(score: int, current: HighScore) -> bool:
    """score > current.score（严格大于）。"""


def load_highscores(path: Path) -> dict[str, HighScore]:
    """文件缺失/损坏 → 警告 + 空字典；单条非法 → 跳过并警告。"""


def save_highscores(path: Path, records: Mapping[str, HighScore]) -> None:
    """父目录不存在则创建；JSON 为 {模式键: {score, level, lines, date}}。"""


class HighscoreStore:
    def __init__(self, path: Path = DEFAULT_HIGHSCORE_PATH) -> None:
        """构造时自动加载磁盘纪录（损坏回退空记录）。"""

    def reload(self) -> None: ...
    def get_highscore(self, key: str) -> HighScore:
        """无纪录时返回 HighScore(0, 0, 0, "")。"""

    def submit(self, key: str, score: int, level: int, lines: int) -> bool:
        """破纪录则更新内存并落盘；返回是否破纪录。"""

    def save(self) -> None: ...
```

校验规则：score/level/lines 必须是非负 int（bool 不算）；date 必须是非空 str；
任一不满足即视为损坏 → 跳过该条 + 警告；整文件不是 JSON 对象 → 空记录 + 警告。

**边界情况**：文件不存在；JSON 语法损坏；字段类型错误；父目录不存在；
新纪录等于旧纪录不算破纪录（严格大于）；不同模式键纪录互不影响；
损坏只影响单条纪录时其余模式正常加载。

**测试文件**：`tests/tetris/test_highscore.py`

- `test_load_missing_file_returns_empty`。
- `test_save_and_load_roundtrip`。
- `test_load_corrupt_json_returns_empty`（写入非法 JSON，断言警告输出到 stderr）。
- `test_load_wrong_types_returns_empty` / `test_load_skips_only_invalid_record`。
- `test_new_highscore_uses_today`。
- `test_is_new_record_strict_greater`：相等不算。
- `test_save_creates_parent_directory`。
- `test_mode_key_combines_settings`。
- `test_store_submit_returns_whether_new_record`。
- `test_store_records_per_mode_independent`。
- `test_store_missing_mode_returns_default`。
- `test_store_persists_across_instances`。

完成检查清单：用例绿；四项检查绿；本模块只依赖标准库、无 pygame 导入。

## 5. M3 UI 与装配

### 5.1 引入 pygame 依赖

编辑 `pyproject.toml`，在 `[project.optional-dependencies]` 的 `dev` 组之后新增：

```toml
tetris = [
    "pygame-ce>=2.5",
]
```

然后安装：

```powershell
.venv\Scripts\python -m pip install -e ".[dev,tetris]"
```

说明：pygame-ce 是 Pygame 社区维护版，`import pygame` 用法与官方一致。
UI 层测试在无显示器环境下运行需要 `SDL_VIDEODRIVER=dummy`——在测试文件顶部、
import pygame **之前**设置：

```python
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
```

### 5.2 ui/input.py

**目标**：DAS/ARR 输入状态机，每帧至多产出一个 action。

**新文件**：`src/eblock/tetris/ui/input.py`

**接口规格**：

```python
from eblock.tetris.sim.game import Action


@dataclass(frozen=True)
class Keymap:
    left: int
    right: int
    soft_drop: int
    hard_drop: int
    rotate_cw: int
    rotate_ccw: int
    hold: int


DEFAULT_KEYMAP: Keymap  # ←/→/↓/空格/↑/Z/C，取 pygame 常量


class InputController:
    def __init__(self, das_ms: int, arr_ms: int, keymap: Keymap = DEFAULT_KEYMAP) -> None: ...

    def step(
        self,
        pressed: set[int],
        keydown: set[int],
        keyup: set[int],
    ) -> Action | None: ...
```

行为规则（按优先级从上到下，命中即返回）：

1. keydown 中的动作键，按优先级：HOLD → ROTATE_CW → ROTATE_CCW → HARD_DROP →
   SOFT_DROP_START（一次只处理一个）。
2. keyup 中的软降键 → SOFT_DROP_END。
3. 左右移动（DAS/ARR）：
   - 左右**同时按下**：本帧不返回移动、两侧计时清空。
   - 仅一侧按下：首帧返回一次移动；之后按住满 `das_ms` 起，每 `arr_ms`
     再返回一次；释放清空该侧状态。
4. 其余情况返回 None。

**边界情况**：das=0 表示无延迟立即重复；arr=0 表示每帧移动；同帧
keydown 旋转 + 按住左键 → 旋转优先；释放软降与按移动同帧 → 移动优先于 SOFT_DROP_END
（每帧至多一个 action）。

**测试文件**：`tests/tetris/test_input.py`

- `test_keydown_hold_returns_hold_action`。
- `test_keydown_rotate_priority`：同一帧 HOLD 与 ROTATE_CW → HOLD。
- `test_hard_drop_and_soft_start_priority`。
- `test_first_frame_press_moves_once`。
- `test_das_emits_after_delay`：das=170 时第 169ms 无、第 170ms 有。
- `test_arr_repeats_every_interval`。
- `test_release_resets_das`。
- `test_both_directions_pressed_no_move`。
- `test_soft_drop_edges`：keydown → START、keyup → END。
- `test_move_beats_soft_drop_end`：同帧按住左 + 松开 ↓ → MOVE_LEFT。

### 5.3 ui/renderer.py

**目标**：纯展示，接收不可变状态绘制一帧。

**新文件**：`src/eblock/tetris/ui/renderer.py`

**接口规格**：

```python
import pygame

from eblock.tetris.config import TetrisConfig
from eblock.tetris.save.highscore import HighScore
from eblock.tetris.sim.game import GameState
from eblock.tetris.sim.tetromino import PieceType

CELL_SIZE: int = 30
PIECE_COLORS: dict[PieceType, tuple[int, int, int]]  # I 青 O 黄 T 紫 S 绿 Z 红 J 蓝 L 橙
BG_COLOR: tuple[int, int, int]  # 深色背景
GRID_COLOR: tuple[int, int, int]  # 浅色网格线


class Renderer:
    def __init__(self, screen: pygame.Surface, config: TetrisConfig) -> None: ...
    def draw(
        self,
        state: GameState,
        highscore: HighScore,
        paused: bool,
        game_over: bool,
    ) -> None: ...
```

绘制职责（draw 内按此顺序）：

1. 背景与棋盘网格（只画可见区：`board[2:2+visible_rows]`，格 30px）。
2. 已锁定方块（遍历 board 可见区）。
3. Ghost：`state.current` 移到 `state.ghost_y` 的格子，半透明轮廓
   （`pygame.draw.rect(..., width=2)`，颜色为该方块色）。
4. 当前方块（按 `current` 位置实心绘制）。
5. 右侧面板：HOLD 框（`state.hold` 或空）、NEXT×`preview_count`
   （取 `state.next_queue` 前 N 个，不足 N 个也照画）、SCORE / LEVEL / LINES、
   最高分（`highscore.score`）。
6. 覆盖层：`paused` 时画“暂停，P 继续”；`game_over` 时画“游戏结束，R 重开，Esc 退出”。

窗口布局沿用开发文档 §7.1（约 560×640，棋盘区 300×600，右侧 220px 面板）。
文本用 pygame 默认字体（`pygame.font.Font(None, size)`）。

**测试文件**：`tests/tetris/test_renderer.py`

- `test_draw_does_not_raise`：dummy 驱动下创建 560×640 表面，对默认 GameState
  与构造的 HighScore 调 draw，断言不抛异常。
- `test_draw_paused_and_game_over_overlays`（同上，分别传 True）。

### 5.4 app/main.py

**目标**：装配主循环：输入 → sim → 渲染，处理暂停/重开/退出与高分保存。

**新文件**：`src/eblock/tetris/app/main.py`

**接口规格**：

```python
def main() -> int: ...


if __name__ == "__main__":
    raise SystemExit(main())
```

主循环行为：

1. `pygame.init()`，创建窗口（约 560×640，标题 “eblock - Tetris”），`pygame.time.Clock()`。
2. 加载 `load_default_config()`；`Game(config)`；`InputController(das_ms, arr_ms)`；
   `Renderer(screen, config)`；`HighscoreStore()`（构造时自动加载）。
3. 每帧：`dt_ms = clock.tick(60)`（封顶 60 FPS）。
4. 事件处理（不传给 sim 的）：QUIT → 退出；P → 切暂停（game over 时无效）；
   R → `game.restart()` 并清输入状态；Esc → 退出。
5. 未暂停且未结束：`action = input_controller.step(pressed, keydown, keyup)`；
   `result = game.step(action, dt_ms)`；若 events 含 `GAME_OVER`，用当前模式键
   `store.submit(mode_key(config.randomizer.mode, config.spawn_random_rotation),
   state.score, state.level, state.lines)` 提交（破纪录才落盘，用守卫标志保证
   一局只写一次）。
6. `renderer.draw(state, highscore, paused, game_over)`；`pygame.display.flip()`。

启动命令：`.venv\Scripts\python -m eblock.tetris.app.main`。

### 5.5 手动验收清单（M3 完成条件）

- 启动后能看到空棋盘、当前方块、Ghost、HOLD、NEXT×3、计分面板。
- 左右移动、旋转、软降、硬降、保持全部生效；按住 ← 有 DAS/ARR 重复。
- 自然落地 500ms 后锁定；硬降/软降触底立即锁定。
- 消行计分与升级正确；一局能从开始玩到 Game Over。
- 暂停（P）恢复（P）、重开（R）、退出（Esc）正常。
- 结束后高分按当前模式键写入 `saves/highscores.json`；再开一局面板显示该纪录。
- 四项检查全绿。

## 6. M4 打磨与调优

### 6.1 画面与流程完善

- 结束画面展示本局分数与最高分。
- 暂停画面明确按键提示。
- 配色微调（保持 `PIECE_COLORS` 集中在 renderer.py，不散落）。

### 6.2 手感调优流程（数据驱动）

1. 修改 `config/tetris.json`（如 das/arr/gravity/lock_delay）。
2. 运行四项检查（改配置不应当影响测试）。
3. 实际游玩 10 分钟，记录主观手感。
4. 每次只改一个参数，便于归因；改动记录可追加到开发文档 §12 决策记录。

### 6.3 最终验收（对应开发文档 §11）

工程：

- 四项检查全绿；`sim` 可脱离 pygame 运行与测试。
- `Select-String -Path src\eblock\tetris\sim\*.py -Pattern 'pygame'` 无输出。
- 配置全部外置；对 `config/tetris.json` 做一处非法修改能启动即报错并指出字段路径。

玩法：

- 完整一局从开始到结束；重开、暂停、高分持久化正常。
- 7-bag 无异常；T/I 贴墙、贴地旋转踢墙生效；hold 每落一次限一次；
  ghost 位置与硬降落点一致。
- 修改 das/arr/gravity 后实际手感生效。

## 7. 附录 A：常见坑清单

1. **SRS 踢墙 y 轴取反**：官方表 y 向上，应用偏移时是 `(x + kx, y - ky)`。
2. **O 方块**：旋转状态可变但格子集合不变，且无踢墙表。
3. **y < 0 视为空**：不碰撞、不写入棋盘；只有 y ≥ 0 的格参与存储。
4. **消行计分**：用**旧等级**，且同时消 n 行只按 n 档一次，不逐行累加。
5. **锁定重置**：只有**成功**的移动/旋转才重置锁定计时并计数；软降触底不走锁定延迟。
6. **事件顺序**：PIECE_LOCK → LINES_CLEARED → LEVEL_UP → PIECE_SPAWN →
   （可能）GAME_OVER。
7. **每帧至多一个 action**；左右同按无移动；输入状态机在 ui 层，sim 不做重复处理。
8. **GameState 可序列化**：不得含函数、pygame 对象、RNG 引用；
   next_queue 存完整袋余量以便还原发牌序列。
9. **config JSON 键是字符串**：转 int 失败要报字段路径，不要抛裸 KeyError。
10. **暂停不调 step**：暂停是 app 层职责，sim 无暂停概念。
11. **mypy strict**：先写类型再写实现；`Mapping`/`tuple` 等不可变类型优先，
    避免可序列化字段用 list。
12. **棋盘 22 行**：渲染只画可见区 `board[2:2+visible_rows]`，逻辑用完整 22 行。
13. **硬降距离 0 也锁定**；游戏结束后 step 是 no-op。

## 8. 附录 B：卡住时自查

1. 先跑该步的测试文件，看红灯是哪一条；测试名即行为规格。
2. 重读开发文档对应小节（§6.1–6.9）与本节对应步骤的“行为规则”。
3. 打印 `GameState` 检查不变式：board 尺寸、score ≥ 0、level ≥ 1、
   next_queue 无重复。
4. 检查是否违反分层铁律（sim 里搜 pygame）。
5. 检查事件顺序与文档 §7 附录一致。
6. 仍卡住时，把最小复现（一段构造状态的测试）贴到对话里讨论。

## 9. 附录 C：关键决策记录

- `config.py` 是开发文档模块清单之外新增的模块，职责为加载与校验。
- 旋转用依赖注入 `collides` 回调，rotation 不依赖 board。
- 发牌器抽象为 `Randomizer` 协议 + `create_randomizer` 工厂；`seven_bag` /
  `uniform` / `no_repeat` 三种算法支持 seed 注入与袋余量存取，保证测试可复现、
  存档可还原；`uniform` 无袋队列、不可精确还原（设计取舍）。
- `spawn_random_rotation` 是玩法开关：开启后出生旋转状态随机取 0..3，
  由 S7 game.py 消费；该开关与发牌模式共同构成高分模式键。
- 高分按模式键独立存储（`HighscoreStore`），单条损坏跳过、整文件损坏回退空记录。
- 固定语义：动作 → 软降 → 重力 → 锁定；消行先按旧等级计分再升级；
  软降触底立即锁定；成功移动/旋转才重置锁定计时；spawn 出生碰撞只触发一次
  GAME_OVER。
- 输入：`get_pressed` 负责左右 DAS/ARR，KEYDOWN/KEYUP 负责旋转/硬降/保持/软降边沿。
- `PieceState` 定义在 tetromino.py（rotation.py 与 game.py 共用），避免循环导入。
- `restart()` 用新随机种子；`load_state()` 恢复快照并清零计时器。
