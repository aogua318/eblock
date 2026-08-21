"""俄罗斯方块核心状态机（M1-S7）。

本模块是 sim 层的总入口：统一接收每帧输入（action）与时间增量（dt_ms），
维护对局全部状态，并以「不可变快照 + 事件列表」的形式把结果交还给调用方。

关键设计：
  - 状态机：所有状态变更只能通过 step() 发生，渲染层不直接改游戏数据；
  - 事件：锁定、消行、升级、出生、保持、结束等关键节点以 GameEvent 通知
    调用方，事件顺序是测试与 UI 的契约（见锁定表）；
  - 纯数据：GameState 只含元组/冻结数据类等纯数据，可序列化存档，
    不含函数、pygame 对象或随机数生成器引用；
  - 依赖方向：本模块只依赖 config 与 sim 内部模块，不导入 pygame。
"""

import random
from dataclasses import dataclass
from enum import Enum, auto

from eblock.tetris.config import TetrisConfig
from eblock.tetris.sim.board import Board, clear_lines, collides, empty_board, place
from eblock.tetris.sim.randomizer import Randomizer, create_randomizer
from eblock.tetris.sim.rotation import cells_at_rotation, try_rotation
from eblock.tetris.sim.scoring import (
    gravity_interval_ms,
    hard_drop_score,
    level_after_lines,
    line_clear_score,
    soft_drop_score,
)
from eblock.tetris.sim.tetromino import Cells, PieceState, PieceType


class Action(Enum):
    """玩家/输入层可提交的动作，每帧至多一个（None 表示无动作）。"""

    MOVE_LEFT = auto()  # 左移一格
    MOVE_RIGHT = auto()  # 右移一格
    ROTATE_CW = auto()  # 顺时针旋转（含踢墙）
    ROTATE_CCW = auto()  # 逆时针旋转（含踢墙）
    SOFT_DROP_START = auto()  # 开始软降（按住下键）
    SOFT_DROP_END = auto()  # 结束软降（松开下键）
    HARD_DROP = auto()  # 硬降：瞬间落到 ghost 位置并立即锁定
    HOLD = auto()  # 保持：与 hold 槽交换当前方块


class GameEvent(Enum):
    """对局关键节点事件，step() 按发生顺序追加到事件列表。"""

    PIECE_SPAWN = auto()  # 新方块出生（含开局与每次锁定后）
    PIECE_LOCK = auto()  # 方块落定写入棋盘
    LINES_CLEARED = auto()  # 消行（同时消 1..4 行）
    LEVEL_UP = auto()  # 等级提升
    HOLD_SWAP = auto()  # 保持成功（首次存入或与当前方块交换）
    GAME_OVER = auto()  # 游戏结束（出生碰撞，整个对局仅一次）


@dataclass(frozen=True)
class GameState:
    """对局不可变快照，供渲染、测试与存档使用。

    可序列化约束：所有字段均为纯数据（元组、冻结数据类、枚举、int/bool/None），
    不得包含函数、pygame 对象或随机数生成器引用。
    """

    board: Board  # 当前棋盘（已落定方块）
    current: PieceState  # 当前活动方块（含类型、旋转、原点坐标）
    ghost_y: int  # 幽灵落点行坐标（当前方块直接硬降的落点）
    next_queue: tuple[PieceType, ...]  # 发牌器袋余量（uniform 模式为空元组）
    hold: PieceType | None  # 保持槽中的方块类型；None 表示尚未使用
    hold_used: bool  # 本「下落周期」内是否已使用过保持（锁定后复位）
    score: int  # 当前总分
    level: int  # 当前等级（≥ start_level）
    lines: int  # 累计消除行数
    game_over: bool  # 是否已结束


@dataclass(frozen=True)
class StepResult:
    """step() 的返回值：本帧事件列表 + 帧末状态快照。"""

    events: tuple[GameEvent, ...]  # 本帧发生的事件，顺序即契约
    state: GameState  # 本帧处理完成后的状态快照


class Game:
    """俄罗斯方块状态机：唯一的对局状态变更入口。

    内部字段（全部由 __init__ 初始化，其余方法只读/修改这些字段）：
        _config: TetrisConfig 配置（只读，运行期不改）。
        _board: Board 当前棋盘。
        _current: PieceState 当前活动方块。
        _randomizer: Randomizer 发牌器（由 create_randomizer 创建）。
        _rng: random.Random 出生旋转随机源（spawn_random_rotation 用）。
        _hold: PieceType | None 保持槽。
        _hold_used: bool 本下落周期是否已使用保持。
        _score: int 总分。
        _level: int 当前等级。
        _lines: int 累计消除行数。
        _game_over: bool 是否已结束。
        _gravity_accum_ms: int 重力计时累加（毫秒）。
        _soft_accum_ms: int 软降计时累加（毫秒）。
        _soft_active: bool 是否处于软降状态。
        _grounded: bool 当前方块是否已接地（下方无空格）。
        _lock_accum_ms: int 锁定计时累加（毫秒）。
        _lock_reset_count: int 接地后成功移动/旋转重置锁定计时的次数。
    """

    _config: TetrisConfig
    _board: Board
    _current: PieceState
    _randomizer: Randomizer
    _rng: random.Random
    _hold: PieceType | None
    _hold_used: bool
    _score: int
    _level: int
    _lines: int
    _game_over: bool
    _gravity_accum_ms: int
    _soft_accum_ms: int
    _soft_active: bool
    _grounded: bool
    _lock_accum_ms: int
    _lock_reset_count: int

    def __init__(self, config: TetrisConfig, seed: int | None = None) -> None:
        """初始化一局新对局。

        参数:
            config: 已通过 config.py 校验的完整对局配置。
            seed: 随机种子；None 表示不可复现的随机（发牌器与出生旋转共用）。

        返回:
            None。对局初始状态见类 docstring 中的字段说明。

        实现流程:
            1. 保存 _config；创建发牌器 _randomizer 与出生旋转随机源 _rng
               （两者使用同一 seed，保证 spawn_random_rotation 开启时可复现）。
            2. 初始化棋盘：empty_board(config.board.rows, config.board.cols)。
            3. 初始化计数：_score=0、_level=config.scoring.start_level、
               _lines=0、_hold=None、_hold_used=False、_game_over=False。
            4. 初始化计时器：_gravity_accum_ms / _soft_accum_ms /
               _lock_accum_ms 全部为 0；_soft_active=False、
               _grounded=False、_lock_reset_count=0。
            5. 出生首块（不发射任何事件；空棋盘上必然不碰撞）：
               从 _randomizer.next() 取方块，出生点
               (config.board.spawn_x, config.board.spawn_y)，
               初始旋转 = 0（固定）或随机 0..3
               （config.spawn_random_rotation=True 时）。
        """
        self._config = config
        # 出生旋转随机源：与发牌器各自独立（同 seed），保证
        # spawn_random_rotation 开启时出生方向可复现。
        self._rng = random.Random(seed)
        self._randomizer = create_randomizer(self._config.randomizer.mode, seed)
        # 空棋盘：rows 行 × cols 列，方块由锁定流程写入。
        self._board = empty_board(config.board.rows, config.board.cols)
        # 计数：分数、开局等级、累计消行、保持槽与保持使用状态。
        self._score = 0
        self._level = config.scoring.start_level
        self._lines = 0
        self._hold = None
        self._hold_used = False
        self._game_over = False
        # 计时器与状态标志：重力/软降/锁定计时、软降开关、接地、锁定重置次数。
        self._gravity_accum_ms = 0
        self._soft_accum_ms = 0
        self._lock_accum_ms = 0
        self._soft_active = False
        self._grounded = False
        self._lock_reset_count = 0
        # 出生首块：不发射事件（空棋盘上必然不碰撞），初始旋转按配置。
        first_rotation = self._rng.randrange(4) if config.spawn_random_rotation else 0
        self._current = PieceState(
            self._randomizer.next(),
            first_rotation,
            config.board.spawn_x,
            config.board.spawn_y,
        )

    def step(self, action: Action | None, dt_ms: int) -> StepResult:
        """推进一帧：处理动作与计时，返回本帧事件与状态快照。

        参数:
            action: 本帧动作；None 表示无动作（纯计时帧）。
            dt_ms: 本帧经过的毫秒数（单帧可跨多格下落，如 5000ms）。

        返回:
            StepResult：本帧事件元组（顺序见锁定表契约）+ 帧末状态快照。

            每帧处理顺序（严格按文档）:
            1. 游戏结束短路；
            2. 处理 action（动作表，内联 if/elif 逐条实现）；
            3. 软降计时（触底失败立即锁定并跳过 4、5 步）；
            4. 重力计时（仅未接地时）；
            5. 锁定计时（接地后累计，超过 lock_delay_ms 锁定）。
        """
        # 1. 游戏结束短路：不再处理任何输入与计时。
        if self._game_over:
            return StepResult((), self.to_state())

        events: list[GameEvent] = []

        # 2. 处理 action（动作表逐条实现）。
        if action is Action.MOVE_LEFT:  # 左移
            # 获取方块和它的状态
            cells = cells_at_rotation(self._current.piece_type, self._current.rotation)
            # 判断方块相对格左移一格是否碰撞
            if not collides(self._board, self._current.x - 1, self._current.y, cells):
                self._current = PieceState(
                    self._current.piece_type,
                    self._current.rotation,
                    self._current.x - 1,
                    self._current.y,
                )

                self._after_successful_move(events)
        elif action is Action.MOVE_RIGHT:  # 右移
            cells = cells_at_rotation(self._current.piece_type, self._current.rotation)
            if not collides(self._board, self._current.x + 1, self._current.y, cells):
                self._current = PieceState(
                    self._current.piece_type,
                    self._current.rotation,
                    self._current.x + 1,
                    self._current.y,
                )
                # 事件更新
                self._after_successful_move(events)
        elif action is Action.ROTATE_CW:  # 顺时针转
            rotated = try_rotation(self._current, True, self._check_collision)
            if rotated is not self._current:
                self._current = rotated
                self._after_successful_move(events)
        elif action is Action.ROTATE_CCW:  # 逆时针转
            # 返回旋转后的方块
            rotated = try_rotation(self._current, False, self._check_collision)
            # 如果旋转后不是原来的对象
            if rotated is not self._current:
                # 更改指向方块
                self._current = rotated
                # 事件更新
                self._after_successful_move(events)
        elif action is Action.SOFT_DROP_START:  # 软降
            self._soft_active = True
            # 刷新下降时间
            self._soft_accum_ms = 0
        elif action is Action.SOFT_DROP_END:  # 结束软降
            self._soft_active = False
            self._soft_accum_ms = 0
        elif action is Action.HARD_DROP:  # 硬降
            # 计算硬降格数
            distance = self._drop_distance()
            # 硬降计分：下移格数 × 每格分值，换算统一走 scoring 模块。
            self._score += hard_drop_score(distance, self._config.scoring.hard_drop_per_cell)

            # 改变方块位置
            self._current = PieceState(
                self._current.piece_type,
                self._current.rotation,
                self._current.x,
                self._current.y + distance,
            )
            self._lock(events)  # 硬降立即锁定，不走锁定延迟。
        elif action is Action.HOLD:  # 交换方块
            if not self._hold_used:  # 没有用过交换
                if self._hold is None:  # 锁定框为空
                    # 首次保持：存入当前方块，从发牌器取新块出生。
                    self._hold = self._current.piece_type
                    self._hold_used = True
                    # 添加事件
                    events.append(GameEvent.HOLD_SWAP)
                    # 生成新方块
                    self._spawn_piece(self._randomizer.next(), events)
                else:
                    # 交换：当前方块换成 hold 槽中的方块。
                    held_type = self._hold
                    self._hold = self._current.piece_type
                    self._hold_used = True
                    events.append(GameEvent.HOLD_SWAP)
                    self._spawn_piece(held_type, events)

        # 3. 软降计时：每满 soft_drop_interval_ms 下移一格；触底立即锁定并跳过第 4、5 步。
        if self._soft_active:  # 软降开
            self._soft_accum_ms += dt_ms  # 时间流逝
            interval = self._config.timing.soft_drop_interval_ms
            while self._soft_accum_ms >= interval:  # 是否大于软降时间
                self._soft_accum_ms -= interval
                cells = cells_at_rotation(  # 获取方块
                    self._current.piece_type, self._current.rotation
                )
                if not collides(  # 没有碰撞
                    self._board, self._current.x, self._current.y + 1, cells
                ):
                    self._current = PieceState(  # 移动
                        self._current.piece_type,
                        self._current.rotation,
                        self._current.x,
                        self._current.y + 1,
                    )
                    # 软降计分：每成功下移一格加一次，换算统一走 scoring 模块。
                    self._score += soft_drop_score(1, self._config.scoring.soft_drop_per_cell)
                else:  # 撞了
                    self._lock(events)  # 锁定
                    return StepResult(tuple(events), self.to_state())  # 返回帧事件

        # 4. 重力计时：仅未接地时累加，每满当前等级间隔下移一格。
        if not self._grounded:  # 没有接地
            interval = gravity_interval_ms(  # 根据等级获取下落时间间隔
                self._level,
                self._config.gravity_ms_per_level,
                self._config.max_level,
            )
            self._gravity_accum_ms += dt_ms  # 时间流逝
            while self._gravity_accum_ms >= interval:  # 是否大于重力时间
                self._gravity_accum_ms -= interval  # 减去一次花费的时间
                cells = cells_at_rotation(  # 获取方块
                    self._current.piece_type, self._current.rotation
                )
                if not collides(  # y+1 没有撞
                    self._board, self._current.x, self._current.y + 1, cells
                ):
                    self._current = PieceState(  # 更新方块
                        self._current.piece_type,
                        self._current.rotation,
                        self._current.x,
                        self._current.y + 1,
                    )
                    self._grounded = self._is_grounded()  # 判断是否触底
                else:  # y+1 撞了
                    self._grounded = True  # 触底
                    self._gravity_accum_ms = 0  # 重制重力时间
                    break  # 退出循环，执行下一步 锁定

        # 5. 锁定计时：接地后累计，达到 lock_delay_ms 执行锁定流程。
        if self._grounded:  # 接地了
            self._lock_accum_ms += dt_ms  # 时间流逝
            if self._lock_accum_ms >= self._config.timing.lock_delay_ms:  # 锁定时间到了
                self._lock(events)  # 锁定

        # 6. 返回本帧事件与帧末快照。
        return StepResult(tuple(events), self.to_state())

    # ---------- step 的私有辅助方法 ----------

    def _check_collision(self, x: int, y: int, cells: Cells) -> bool:
        """try_rotation 需要的碰撞回调：把当前棋盘绑定进固定签名。

        参数:
            x: 方块原点列坐标。
            y: 方块原点行坐标。
            cells: 方块的相对格集合。

        返回:
            True 表示该位置与当前棋盘碰撞，False 表示可放置。
        """
        return collides(self._board, x, y, cells)

    def _is_grounded(self) -> bool:
        """判断当前方块是否接地：正下方一格即碰撞。"""
        cells = cells_at_rotation(self._current.piece_type, self._current.rotation)
        return collides(self._board, self._current.x, self._current.y + 1, cells)

    def _after_successful_move(self, events: list[GameEvent]) -> None:
        """移动/旋转成功后的共同收尾（动作表中"同上"的部分）。

        参数:
            events: 本帧事件列表；可能被 _lock 追加事件。
        """
        # 判断是否接地
        self._grounded = self._is_grounded()
        if self._grounded:  # 前提：移动/旋转后仍然接地
            self._lock_accum_ms = 0  # 1、 锁定倒计时清零 → 重新获得完整的 500ms
            self._lock_reset_count += 1  # 2、 记录"续了一次命"
            if self._lock_reset_count > self._config.timing.lock_reset_limit:  # 续太多
                self._lock(events)  # 3、立即锁定，不再给机会

    def _drop_distance(self) -> int:
        """当前方块从当前位置连续下移到碰撞前的格数（硬降与 ghost 共用）。

        返回:
            可下移的格数；已在底部时为 0。
        """
        cells = cells_at_rotation(self._current.piece_type, self._current.rotation)
        distance = 0
        while not collides(self._board, self._current.x, self._current.y + distance + 1, cells):
            distance += 1
        return distance

    def _spawn_piece(self, piece_type: PieceType, events: list[GameEvent]) -> None:
        """按出生规则生成方块、重置本下落周期状态并检查出生碰撞。

        参数:
            piece_type: 要出生的方块类型（发牌器产出或 hold 槽中的方块）。
            events: 本帧事件列表；追加 PIECE_SPAWN，碰撞时追加 GAME_OVER。
        """
        # 如果打开了随机旋转，旋转值为 0..3 的随机整数（对应四个旋转状态）；否则保持 0。
        rotation = self._rng.randrange(4) if self._config.spawn_random_rotation else 0

        # 生成新方块
        self._current = PieceState(
            piece_type,
            rotation,
            self._config.board.spawn_x,
            self._config.board.spawn_y,
        )
        # 重置计时/接地/计数：新方块开始全新的下落周期。
        self._gravity_accum_ms = 0
        self._soft_accum_ms = 0
        self._lock_accum_ms = 0
        self._lock_reset_count = 0
        self._soft_active = False
        self._grounded = self._is_grounded()  # 判断刚出生时候是否接地
        # 新方块生成事件
        events.append(GameEvent.PIECE_SPAWN)
        # 出生碰撞检查：含 y>=0 的格与棋盘碰撞即结束，GAME_OVER 整个对局仅此一次。
        cells = cells_at_rotation(self._current.piece_type, self._current.rotation)
        if collides(self._board, self._current.x, self._current.y, cells):
            self._game_over = True
            # 添加游戏结束事件
            events.append(GameEvent.GAME_OVER)

    def _lock(self, events: list[GameEvent]) -> None:
        """锁定流程（锁定表）：写盘 → 消行计分升级 → 解除保持 → 生成下一块。

        参数:
            events: 本帧事件列表，按锁定表顺序追加事件。
        """
        # 获取当前方块状态
        cells = cells_at_rotation(self._current.piece_type, self._current.rotation)
        # 锁定方块
        self._board = place(
            self._board, self._current.piece_type, self._current.x, self._current.y, cells
        )
        # 添加方块锁定事件
        events.append(GameEvent.PIECE_LOCK)

        # 计算新棋盘 消除行数
        self._board, cleared = clear_lines(self._board)
        # 如果存在消除
        if cleared > 0:
            # 添加消除事件
            events.append(GameEvent.LINES_CLEARED)
            # 增加分数
            self._score += line_clear_score(cleared, self._level, self._config.scoring.line_clear)
            # 增加消除行数
            self._lines += cleared
            # 计算新等级
            new_level = level_after_lines(
                self._lines,
                self._config.scoring.lines_per_level,
                self._config.scoring.start_level,
            )
            # 判断等级是否提升
            if new_level > self._level:
                # 等级提升事件
                events.append(GameEvent.LEVEL_UP)
                self._level = new_level
        # 刷新更换次数
        self._hold_used = False
        # 生成新方块 参照next里的
        self._spawn_piece(self._randomizer.next(), events)

    def to_state(self) -> GameState:
        """生成当前对局的不可变快照。

        参数:
            无。

        返回:
            GameState：棋盘、当前方块、ghost 落点、发牌器袋余量、
            保持与分数/等级/行数/结束标志。

        实现流程:
            1. ghost_y = _current.y + 下落距离
               （下落距离 = 从当前位置连续下移直到碰撞前的步数，
               与硬降的 d 是同一套计算，可复用同一私有方法）。
            2. next_queue = _randomizer.save_queue()
               （uniform 模式恒为空元组）。
            3. 用上述字段与 _board/_current/_hold/_hold_used/_score/
               _level/_lines/_game_over 构造并返回 GameState。
        """
        return GameState(
            board=self._board,
            current=self._current,
            ghost_y=self._current.y + self._drop_distance(),
            next_queue=self._randomizer.save_queue(),
            hold=self._hold,
            hold_used=self._hold_used,
            score=self._score,
            level=self._level,
            lines=self._lines,
            game_over=self._game_over,
        )

    def load_state(self, state: GameState) -> None:
        """从快照恢复对局（存档读档），并重置全部计时器。

        参数:
            state: 之前由 to_state() 产出的快照。

        返回:
            None。

        实现流程:
            1. 恢复对局字段：_board、_current、_hold、_hold_used、
               _score、_level、_lines、_game_over 直接取自 state。
            2. 恢复发牌器：_randomizer.load_queue(state.next_queue)
               （需注意 uniform 模式只接受空队列）。
            3. 重置计时：_gravity_accum_ms / _soft_accum_ms /
               _lock_accum_ms = 0；_soft_active = False；
               _lock_reset_count = 0。
            4. 重算接地：_grounded = 当前方块「不可再下移一格」
               （即 collides(棋盘, x, y+1, 当前格子) 为 True）。
        """
        # 1. 恢复对局字段。
        self._board = state.board
        self._current = state.current
        self._hold = state.hold
        self._hold_used = state.hold_used
        self._score = state.score
        self._level = state.level
        self._lines = state.lines
        self._game_over = state.game_over
        # 2. 恢复发牌器袋余量（uniform 模式只接受空队列）。
        self._randomizer.load_queue(state.next_queue)
        # 3. 重置全部计时器与软降状态。
        self._gravity_accum_ms = 0
        self._soft_accum_ms = 0
        self._lock_accum_ms = 0
        self._lock_reset_count = 0
        self._soft_active = False
        # 4. 按恢复后的棋盘与当前方块重算接地状态。
        self._grounded = self._is_grounded()

    def restart(self) -> None:
        """重开一局：等价于用新随机种子（seed=None）重新构造本对局。

        参数:
            无。

        返回:
            None。

        实现流程:
            - 推荐：self.__init__(self._config)（seed 缺省为 None，
              新对局不可复现、与旧局完全无关）；
        """
        self.__init__(self._config)
