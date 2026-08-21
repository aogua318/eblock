"""game 模块测试（实施指南 M1-S7）。

覆盖:
    - 初始化：score/level/lines/hold/board/current 初始值；
    - 重力：按等级间隔下落、大 dt 跨多格、接地后停止；
    - 移动：左右移动、墙/叠放阻挡、成功移动重置锁定计时、重置次数超限锁定；
    - 旋转：顺时针更新状态、贴墙踢墙、全部踢墙失败保持原状态；
    - 软降/硬降：逐格下落计分、触底立即锁定、结束软降停止、硬降落点与计分；
    - 锁定与消行：落子写入棋盘、锁定延迟、1/4 行消行计分、旧等级计分、
      升级事件与事件顺序；
    - 保持：首次存入、交换、每下落周期限一次、锁定后复位；
    - 结束：出生碰撞判负、GAME_OVER 仅一次、结束后 step 为 no-op；
    - 状态与事件：to_state/load_state 往返一致、发牌序列还原、restart、
      随机动作长跑不崩溃。

所有场景通过构造 GameState 直接布置棋盘与当前方块，避免依赖发牌序列，
保证测试确定性。
"""

import random

from eblock.tetris.config import TetrisConfig, load_default_config
from eblock.tetris.sim.board import Board
from eblock.tetris.sim.game import Action, Game, GameEvent, GameState
from eblock.tetris.sim.tetromino import PieceState, PieceType

ROWS = 22
COLS = 10
CONFIG: TetrisConfig = load_default_config()

# 常用方块状态：T 出生态、I 垂直（旋转 1）。
_T = PieceState(piece_type=PieceType.T, rotation=0, x=4, y=0)
_I_VERTICAL = PieceState(piece_type=PieceType.I, rotation=1, x=9, y=19)


def _make_board(filled: set[tuple[int, int]]) -> Board:
    """构造 22×10 棋盘；filled 中的 (y, x) 坐标放置占位方块。"""
    return tuple(
        tuple(PieceType.T if (y, x) in filled else None for x in range(COLS)) for y in range(ROWS)
    )


def _make_state(
    *,
    current: PieceState,
    filled: set[tuple[int, int]] | None = None,
    score: int = 0,
    level: int = 1,
    lines: int = 0,
    hold: PieceType | None = None,
    hold_used: bool = False,
    next_queue: tuple[PieceType, ...] = (),
) -> GameState:
    """构造用于 load_state 的 GameState，未指定字段取初始值。"""
    return GameState(
        board=_make_board(filled or set()),
        current=current,
        ghost_y=current.y,
        next_queue=next_queue,
        hold=hold,
        hold_used=hold_used,
        score=score,
        level=level,
        lines=lines,
        game_over=False,
    )


def _new_game(state: GameState, seed: int = 0) -> Game:
    """创建 Game 并载入给定状态，便于从指定场景开始。"""
    game = Game(CONFIG, seed=seed)
    game.load_state(state)
    return game


def test_initial_state() -> None:
    """新对局：分数/等级/行数/保持/棋盘/当前方块均为初始值。"""
    game = Game(CONFIG, seed=0)
    state = game.to_state()
    assert state.score == 0
    assert state.level == 1
    assert state.lines == 0
    assert state.hold is None
    assert state.hold_used is False
    assert state.game_over is False
    assert len(state.board) == ROWS and len(state.board[0]) == COLS
    assert all(cell is None for row in state.board for cell in row)
    # spawn_random_rotation 默认 False：出生旋转固定为 0。
    assert state.current.rotation == 0
    assert state.current.x == CONFIG.board.spawn_x
    assert state.current.y == CONFIG.board.spawn_y


def test_gravity_accumulates_by_dt() -> None:
    """等级 1 下落间隔 1000ms：999ms 不动，+1ms 下移一格。"""
    game = Game(CONFIG, seed=0)
    assert game.step(None, 999).state.current.y == 0
    assert game.step(None, 1).state.current.y == 1


def test_gravity_interval_uses_level_table() -> None:
    """等级 2 使用 793ms 间隔：792ms 不动，+1ms 下移一格。"""
    game = _new_game(_make_state(current=PieceState(PieceType.T, 0, 4, 0), level=2))
    assert game.step(None, 792).state.current.y == 0
    assert game.step(None, 1).state.current.y == 1


def test_gravity_stops_when_grounded() -> None:
    """方块触底（接地）后重力不再移动，且未到锁定延迟不锁定。"""
    current = PieceState(PieceType.T, 0, 4, 21)
    game = _new_game(_make_state(current=current))
    result = game.step(None, 400)
    assert result.state.current.y == 21
    assert GameEvent.PIECE_LOCK not in result.events
    assert all(cell is None for row in result.state.board for cell in row)


def test_large_dt_moves_multiple_cells() -> None:
    """5000ms 在等级 1（1000ms/格）下一次下落 5 格。"""
    game = Game(CONFIG, seed=0)
    assert game.step(None, 5000).state.current.y == 5


def test_move_left_right() -> None:
    """左右移动各改变 1 列，旋转与 y 不变。"""
    game = Game(CONFIG, seed=0)
    assert game.step(Action.MOVE_LEFT, 0).state.current.x == 3
    assert game.step(Action.MOVE_RIGHT, 0).state.current.x == 4


def test_move_blocked_by_wall() -> None:
    """贴左墙（T 在 x=1 时最左格在 x=0）左移被挡，位置不变。"""
    current = PieceState(PieceType.T, 0, 1, 0)
    game = _new_game(_make_state(current=current))
    result = game.step(Action.MOVE_LEFT, 0)
    assert result.state.current.x == 1
    assert result.state.current.y == 0


def test_move_blocked_by_stack() -> None:
    """目标位置被已锁定方块占用时右移被挡，位置不变。"""
    filled = {(0, 6)}
    game = _new_game(_make_state(current=_T, filled=filled))
    result = game.step(Action.MOVE_RIGHT, 0)
    assert result.state.current.x == 4


def test_successful_move_resets_lock_timer() -> None:
    """接地后成功移动重置锁定计时：累计 800ms 未锁，再 100ms 才锁定。"""
    current = PieceState(PieceType.T, 0, 4, 21)
    game = _new_game(_make_state(current=current))
    game.step(None, 400)
    game.step(Action.MOVE_RIGHT, 0)
    result = game.step(None, 400)
    assert GameEvent.PIECE_LOCK not in result.events
    assert all(cell is None for row in result.state.board for cell in row)
    result = game.step(None, 100)
    assert GameEvent.PIECE_LOCK in result.events


def test_lock_reset_count_exceeding_limit_locks() -> None:
    """接地后第 16 次成功移动（超过 reset_limit=15）触发立即锁定。"""
    current = PieceState(PieceType.T, 0, 4, 21)
    game = _new_game(_make_state(current=current))
    # 左右交替移动 15 次：每次都成功，计数 1..15，未超限不锁定。
    for i in range(15):
        action = Action.MOVE_RIGHT if i % 2 == 0 else Action.MOVE_LEFT
        result = game.step(action, 0)
        assert GameEvent.PIECE_LOCK not in result.events
    # 第 16 次成功移动：计数 16 > 15，立即锁定。
    result = game.step(Action.MOVE_RIGHT, 0)
    assert GameEvent.PIECE_LOCK in result.events
    assert any(cell is not None for row in result.state.board for cell in row)


def test_rotate_cw_updates_rotation() -> None:
    """开阔空间顺时针旋转：rotation 变为 1，原点不变。"""
    current = PieceState(PieceType.T, 0, 4, 5)
    game = _new_game(_make_state(current=current))
    result = game.step(Action.ROTATE_CW, 0)
    assert result.state.current.rotation == 1
    assert result.state.current.x == 4
    assert result.state.current.y == 5


def test_rotate_kick_at_wall() -> None:
    """贴墙旋转：原位被挡时按踢墙表左移 1 格成功。"""
    current = PieceState(PieceType.T, 0, 1, 0)
    filled = {(1, 1)}  # 阻挡原位旋转落点，迫使使用 (−1,0) 踢墙。
    game = _new_game(_make_state(current=current, filled=filled))
    result = game.step(Action.ROTATE_CW, 0)
    assert result.state.current.rotation == 1
    assert result.state.current.x == 0


def test_rotate_rejected_keeps_state() -> None:
    """五个踢墙偏移全部失败时，方块状态完全不变。"""
    current = PieceState(PieceType.T, 0, 4, 5)
    # filled 集合元素为 (y, x)：依次封死 (0,0)、(−1,0)、(−1,1)、(0,−2)、(−1,−2) 五个偏移。
    filled = {(6, 4), (4, 3), (7, 3), (3, 4), (3, 3)}
    game = _new_game(_make_state(current=current, filled=filled))
    result = game.step(Action.ROTATE_CW, 0)
    assert result.state.current.rotation == 0
    assert result.state.current.x == 4
    assert result.state.current.y == 5


def test_soft_drop_moves_and_scores() -> None:
    """软降 50ms 下移一格，每格 +1 分。"""
    game = Game(CONFIG, seed=0)
    game.step(Action.SOFT_DROP_START, 0)
    result = game.step(None, 50)
    assert result.state.current.y == 1
    assert result.state.score == 1


def test_soft_drop_touch_bottom_locks_immediately() -> None:
    """软降触底：下移失败立即锁定，不走锁定延迟。"""
    current = PieceState(PieceType.T, 0, 4, 21)
    game = _new_game(_make_state(current=current))
    game.step(Action.SOFT_DROP_START, 0)
    result = game.step(None, 50)
    assert GameEvent.PIECE_LOCK in result.events
    assert result.state.board[21][3] is not None


def test_soft_drop_end_stops() -> None:
    """结束软降后不再逐格下落（50ms 内重力未到 1000ms 也不会动）。"""
    game = Game(CONFIG, seed=0)
    game.step(Action.SOFT_DROP_START, 0)
    assert game.step(None, 50).state.current.y == 1
    game.step(Action.SOFT_DROP_END, 0)
    assert game.step(None, 50).state.current.y == 1


def test_hard_drop_lands_at_ghost_y() -> None:
    """硬降后方块落在硬降前的 ghost_y 位置（通过棋盘格子验证）。"""
    current = PieceState(PieceType.T, 0, 4, 5)
    game = _new_game(_make_state(current=current))
    ghost_y = game.to_state().ghost_y
    result = game.step(Action.HARD_DROP, 0)
    # T 在 y=ghost_y 时占用 (x-1, y)、(x, y)、(x+1, y) 与 (x, y-1)。
    assert result.state.board[ghost_y][3] is not None
    assert result.state.board[ghost_y][4] is not None
    assert result.state.board[ghost_y][5] is not None


def test_hard_drop_scores_per_cell() -> None:
    """硬降计分：下移 16 格 × 每格 2 分 = 32 分。"""
    current = PieceState(PieceType.T, 0, 4, 5)
    game = _new_game(_make_state(current=current))
    result = game.step(Action.HARD_DROP, 0)
    assert result.state.score == 32


def test_lock_writes_board() -> None:
    """自然锁定后当前方块写入棋盘。"""
    current = PieceState(PieceType.T, 0, 4, 21)
    game = _new_game(_make_state(current=current))
    result = game.step(None, 500)
    assert GameEvent.PIECE_LOCK in result.events
    assert result.state.board[21][3] is not None
    assert result.state.board[20][4] is not None


def test_lock_delay_after_grounding() -> None:
    """接地后达到 500ms 锁定：499ms 不锁，+1ms 锁定。"""
    current = PieceState(PieceType.T, 0, 4, 21)
    game = _new_game(_make_state(current=current))
    result = game.step(None, 499)
    assert GameEvent.PIECE_LOCK not in result.events
    result = game.step(None, 1)
    assert GameEvent.PIECE_LOCK in result.events


def _one_line_clear_state() -> GameState:
    """构造一消场景：T 落底补满第 21 行，硬降距离为 0。"""
    current = PieceState(PieceType.T, 0, 8, 21)
    filled = {(21, col) for col in range(7)}  # 第 21 行 0..6 列已满
    return _make_state(current=current, filled=filled)


def test_clear_one_line_scores_100_times_level() -> None:
    """等级 1 消 1 行：+100 分、行数 +1。"""
    game = _new_game(_one_line_clear_state())
    result = game.step(Action.HARD_DROP, 0)
    assert result.state.score == 100
    assert result.state.lines == 1
    assert GameEvent.LINES_CLEARED in result.events


def test_clear_four_lines_scores_800_times_level() -> None:
    """等级 1 四消：+800 分、行数 +4。"""
    filled = {(row, col) for row in range(18, 22) for col in range(9)}
    game = _new_game(_make_state(current=_I_VERTICAL, filled=filled))
    result = game.step(Action.HARD_DROP, 0)
    assert result.state.score == 800
    assert result.state.lines == 4
    assert result.state.level == 1
    assert GameEvent.LINES_CLEARED in result.events


def test_score_uses_old_level_before_level_up() -> None:
    """累计 9 行时四消：按旧等级 1 计 800×1，随后升到等级 2。"""
    filled = {(row, col) for row in range(18, 22) for col in range(9)}
    state = _make_state(current=_I_VERTICAL, filled=filled, lines=9, level=1)
    game = _new_game(state)
    result = game.step(Action.HARD_DROP, 0)
    assert result.state.score == 800
    assert result.state.lines == 13
    assert result.state.level == 2


def test_level_up_after_10_lines() -> None:
    """累计 9 行时消 1 行：行数到 10，触发升级。"""
    state = _make_state(
        current=PieceState(PieceType.T, 0, 8, 21),
        filled={(21, col) for col in range(7)},
        lines=9,
        level=1,
    )
    game = _new_game(state)
    result = game.step(Action.HARD_DROP, 0)
    assert result.state.lines == 10
    assert result.state.level == 2
    assert GameEvent.LEVEL_UP in result.events


def test_lock_event_sequence() -> None:
    """锁定事件顺序：PIECE_LOCK → LINES_CLEARED → LEVEL_UP → PIECE_SPAWN。"""
    filled = {(row, col) for row in range(18, 22) for col in range(9)}
    state = _make_state(current=_I_VERTICAL, filled=filled, lines=9, level=1)
    game = _new_game(state)
    result = game.step(Action.HARD_DROP, 0)
    assert tuple(result.events) == (
        GameEvent.PIECE_LOCK,
        GameEvent.LINES_CLEARED,
        GameEvent.LEVEL_UP,
        GameEvent.PIECE_SPAWN,
    )


def test_hold_first_time_takes_piece_and_spawns() -> None:
    """首次保持：当前方块存入 hold 槽，并从发牌器取新方块出生。"""
    game = Game(CONFIG, seed=0)
    first_type = game.to_state().current.piece_type
    result = game.step(Action.HOLD, 0)
    assert result.state.hold == first_type
    assert result.state.hold_used is True
    assert result.state.current.piece_type != first_type
    assert result.state.current.y == CONFIG.board.spawn_y
    assert tuple(result.events) == (GameEvent.HOLD_SWAP, GameEvent.PIECE_SPAWN)


def test_hold_ignored_until_next_drop() -> None:
    """首次保持后本下落周期内再次 HOLD 被忽略：无事件、当前方块不变。"""
    game = Game(CONFIG, seed=0)
    game.step(Action.HOLD, 0)
    before = game.to_state()
    result = game.step(Action.HOLD, 0)
    assert result.events == ()
    assert result.state.current == before.current


def test_hold_limited_once_per_drop() -> None:
    """保持每下落周期限一次：锁定前连续 HOLD 均被忽略。"""
    game = Game(CONFIG, seed=0)
    game.step(Action.HOLD, 0)
    game.step(Action.HOLD, 0)
    before = game.to_state()
    result = game.step(Action.HOLD, 0)
    assert result.events == ()
    assert result.state.current == before.current


def test_lock_resets_hold_used() -> None:
    """锁定后 hold_used 复位：再次 HOLD 执行交换，换回最初方块。"""
    game = Game(CONFIG, seed=0)
    first_type = game.to_state().current.piece_type
    game.step(Action.HOLD, 0)
    game.step(Action.HARD_DROP, 0)  # 锁定：hold_used 复位。
    result = game.step(Action.HOLD, 0)  # 交换：hold 槽方块成为当前方块。
    assert GameEvent.HOLD_SWAP in result.events
    assert GameEvent.PIECE_SPAWN in result.events
    assert result.state.current.piece_type == first_type
    assert result.state.hold is not None
    assert result.state.hold != first_type


def test_hold_emits_hold_swap_and_spawn() -> None:
    """首次保持的事件为 HOLD_SWAP + PIECE_SPAWN。"""
    game = Game(CONFIG, seed=0)
    result = game.step(Action.HOLD, 0)
    assert GameEvent.HOLD_SWAP in result.events
    assert GameEvent.PIECE_SPAWN in result.events


def _game_over_state() -> GameState:
    """构造结束场景：T 落地后出生区仍有方块，下一块必碰撞。"""
    current = PieceState(PieceType.T, 0, 4, 0)
    filled = {(0, col) for col in (0, 1, 2, 6, 7, 8)} | {(1, col) for col in range(1, 10)}
    # 不凑满任何一行，保证锁定后不会消行。
    return _make_state(current=current, filled=filled)


def test_game_over_when_spawn_collides() -> None:
    """锁定后下一方块出生碰撞：判负并发出 GAME_OVER。"""
    game = _new_game(_game_over_state())
    result = game.step(Action.HARD_DROP, 0)
    assert tuple(result.events) == (
        GameEvent.PIECE_LOCK,
        GameEvent.PIECE_SPAWN,
        GameEvent.GAME_OVER,
    )
    assert result.state.game_over is True


def test_game_over_event_once() -> None:
    """GAME_OVER 整个对局只出现一次，后续 step 不再产生。"""
    game = _new_game(_game_over_state())
    result = game.step(Action.HARD_DROP, 0)
    assert sum(e is GameEvent.GAME_OVER for e in result.events) == 1
    assert game.step(None, 100).events == ()


def test_step_noop_after_game_over() -> None:
    """游戏结束后 step 是 no-op：状态与事件均不变。"""
    game = _new_game(_game_over_state())
    game.step(Action.HARD_DROP, 0)
    before = game.to_state()
    result = game.step(Action.MOVE_LEFT, 100)
    assert result.events == ()
    assert result.state == before


def test_to_state_load_state_roundtrip() -> None:
    """对局中途 to_state → load_state → to_state 结果相等。"""
    game = Game(CONFIG, seed=0)
    game.step(Action.MOVE_RIGHT, 0)
    game.step(Action.MOVE_RIGHT, 0)
    game.step(None, 999)
    snapshot = game.to_state()
    game.load_state(snapshot)
    assert game.to_state() == snapshot


def test_load_state_preserves_bag_sequence() -> None:
    """载入状态后，袋余量按顺序出块：两个不同 seed 的对局出块一致。"""
    next_queue = (PieceType.I, PieceType.O, PieceType.T)
    state = _make_state(current=_T, next_queue=next_queue)
    game_a = _new_game(state, seed=1)
    game_b = _new_game(state, seed=2)
    # SevenBag.next() 从袋尾弹出，因此 (I, O, T) 的出块顺序是 T、O、I。
    for expected in (PieceType.T, PieceType.O, PieceType.I):
        game_a.step(Action.HARD_DROP, 0)
        game_b.step(Action.HARD_DROP, 0)
        assert game_a.to_state().current.piece_type == expected
        assert game_b.to_state().current.piece_type == expected
    assert game_a.to_state() == game_b.to_state()


def test_restart_resets_all() -> None:
    """restart 后回到初始状态：分数/等级/棋盘/保持/结束标志全部复位。"""
    game = Game(CONFIG, seed=0)
    game.step(Action.MOVE_LEFT, 0)
    game.step(Action.HOLD, 0)
    game.step(Action.HARD_DROP, 0)
    game.restart()
    state = game.to_state()
    assert state.score == 0
    assert state.level == 1
    assert state.lines == 0
    assert state.hold is None
    assert state.hold_used is False
    assert state.game_over is False
    assert all(cell is None for row in state.board for cell in row)
    assert state.current.rotation == 0


def test_random_actions_10000_steps_no_crash() -> None:
    """随机动作长跑：不抛异常、分数非负、棋盘尺寸恒定。"""
    game = Game(CONFIG, seed=0)
    rng = random.Random(0)
    actions = [None, *Action]
    for _ in range(10000):
        game.step(rng.choice(actions), rng.randrange(0, 1001))
        state = game.to_state()
        assert state.score >= 0
        assert len(state.board) == ROWS
        assert len(state.board[0]) == COLS


def test_ghost_y_matches_hard_drop_landing() -> None:
    """ghost_y 与硬降落点一致：锁定行等于硬降前的 ghost_y。"""
    current = PieceState(PieceType.T, 0, 4, 5)
    game = _new_game(_make_state(current=current))
    ghost_y = game.to_state().ghost_y
    game.step(Action.HARD_DROP, 0)
    state = game.to_state()
    # 锁定方块占据 ghost 行：该行必存在非空格。
    assert any(cell is not None for cell in state.board[ghost_y])
