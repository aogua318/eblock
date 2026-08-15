"""board 模块测试（实施指南 M1-S4）。

覆盖:
    - empty_board 创建全空棋盘；
    - collides 的左/右/底部越界、叠放碰撞、y<0 视为空；
    - place 写入占位格、忽略负 y 格、不改原棋盘；
    - clear_lines 消 1/4 行、保持行顺序、返回新对象。
"""

import pytest

from eblock.tetris.sim.board import Board, clear_lines, collides, empty_board, place
from eblock.tetris.sim.tetromino import PieceType, spawn_cells


def _empty_row(cols: int) -> tuple[PieceType | None, ...]:
    """构造一行全空（None）的格子。"""
    return tuple(None for _ in range(cols))


def _full_row(piece_type: PieceType, cols: int) -> tuple[PieceType | None, ...]:
    """构造一行全部被指定方块占满的格子。"""
    return tuple(piece_type for _ in range(cols))


def test_empty_board_dimensions() -> None:
    """22×10 棋盘：22 行、每行 10 格、全部为 None。"""
    board = empty_board(rows=22, cols=10)
    assert len(board) == 22
    assert all(len(row) == 10 for row in board)
    assert all(cell is None for row in board for cell in row)


def test_collides_left_wall() -> None:
    """方块原点 x=-1：格子在左墙之外，判定碰撞。"""
    board = empty_board(rows=22, cols=10)
    assert collides(board, x=-1, y=5, cells=((0, 0),))


def test_collides_right_wall() -> None:
    """方块原点 x=10：格子在右墙之外，判定碰撞。"""
    board = empty_board(rows=22, cols=10)
    assert collides(board, x=10, y=5, cells=((0, 0),))


def test_collides_floor() -> None:
    """方块原点 y=22：格子在底部之外，判定碰撞。"""
    board = empty_board(rows=22, cols=10)
    assert collides(board, x=0, y=22, cells=((0, 0),))


def test_collides_existing_stack() -> None:
    """目标格已被占用：判定碰撞。"""
    board = empty_board(rows=22, cols=10)
    cells = spawn_cells(PieceType.T)
    board = place(board, PieceType.T, x=3, y=20, cells=cells)
    assert collides(board, x=3, y=20, cells=cells)


def test_negative_y_never_collides() -> None:
    """y<0 的格子永远视为空：不与越界或堆叠碰撞。"""
    board = empty_board(rows=22, cols=10)
    # 仅含 y<0 的格子：board_y < 0 直接判空。
    assert not collides(board, x=0, y=-1, cells=((0, 0),))
    # 混合 y<0 与 y=0 的格子：负格不影响判定，正常格在空棋盘上不碰撞。
    assert not collides(board, x=0, y=0, cells=((0, -1), (0, 0)))


def test_place_writes_occupied_cells() -> None:
    """place 把方块每个 y>=0 的相对格写入棋盘，且原棋盘不变。"""
    board = empty_board(rows=22, cols=10)
    new_board = place(board, PieceType.T, x=3, y=20, cells=spawn_cells(PieceType.T))
    # T 出生态 {(-1,0),(0,-1),(0,0),(1,0)} 在原点 (3,20) 的绝对坐标。
    assert new_board[20][2] is PieceType.T
    assert new_board[19][3] is PieceType.T
    assert new_board[20][3] is PieceType.T
    assert new_board[20][4] is PieceType.T
    # 原棋盘保持全空。
    assert board == empty_board(rows=22, cols=10)


def test_place_ignores_negative_y_cells() -> None:
    """place 忽略 y<0 的相对格（虚拟出生区不写入棋盘）。"""
    board = empty_board(rows=22, cols=10)
    # S 出生态含两个 y=-1 的格：(-1,0) 与 (0,0) 写入，两个负格被忽略。
    new_board = place(board, PieceType.S, x=4, y=0, cells=spawn_cells(PieceType.S))
    assert new_board[0][3] is PieceType.S  # 相对格 (-1,0)
    assert new_board[0][4] is PieceType.S  # 相对格 (0,0)
    assert new_board[0][5] is None  # 相对格 (1,-1) 被忽略，未写入 y=0 行
    # 原棋盘保持全空。
    assert board == empty_board(rows=22, cols=10)


def test_place_out_of_bounds_raises_valueerror() -> None:
    """place 遇到行列越界的格子抛 ValueError（防御调用方错误）。"""
    board = empty_board(rows=22, cols=10)
    # 列越界：相对格 (1,0) 在原点 x=10 处绝对列 11 >= 10。
    with pytest.raises(ValueError, match="place 越界"):
        place(board, PieceType.T, x=10, y=5, cells=((0, 0), (1, 0)))
    # 行越界：相对格 (0,1) 在原点 y=22 处绝对行 23 >= 22。
    with pytest.raises(ValueError, match="place 越界"):
        place(board, PieceType.T, x=0, y=22, cells=((0, 0), (0, 1)))


def test_clear_lines_no_clear_returns_same_shape() -> None:
    """无满行时消除数为 0，返回形状等价的棋盘。"""
    board = empty_board(rows=22, cols=10)
    board = place(board, PieceType.T, x=3, y=20, cells=spawn_cells(PieceType.T))
    new_board, cleared = clear_lines(board)
    assert cleared == 0
    assert new_board == board


def test_clear_lines_single() -> None:
    """消除 1 个满行：该行消失，上方残留整体下移，顶部补空行。"""
    cols = 10
    residual = tuple(PieceType.S if c == 0 else None for c in range(cols))
    full = _full_row(PieceType.T, cols)
    board: Board = (_empty_row(cols), residual, _empty_row(cols), full)

    new_board, cleared = clear_lines(board)
    assert cleared == 1
    assert len(new_board) == 4
    assert new_board == (
        _empty_row(cols),
        _empty_row(cols),
        residual,
        _empty_row(cols),
    )


def test_clear_lines_four() -> None:
    """同时消除 4 行（Tetris）：顶部补 4 个空行，残留行下移到底部。"""
    cols = 10
    row_a = tuple(PieceType.J if c == 0 else None for c in range(cols))
    row_b = tuple(PieceType.L if c == 1 else None for c in range(cols))
    full = _full_row(PieceType.I, cols)
    board: Board = (row_a, row_b, full, full, full, full)

    new_board, cleared = clear_lines(board)
    assert cleared == 4
    assert len(new_board) == 6
    assert new_board == (
        _empty_row(cols),
        _empty_row(cols),
        _empty_row(cols),
        _empty_row(cols),
        row_a,
        row_b,
    )


def test_clear_lines_keeps_row_order() -> None:
    """多行消除时，上方未满行整体下移且顺序不变。"""
    cols = 10
    row_a = tuple(PieceType.J if c == 0 else None for c in range(cols))
    row_b = tuple(PieceType.L if c == 1 else None for c in range(cols))
    row_c = tuple(PieceType.S if c == 2 else None for c in range(cols))
    full = _full_row(PieceType.T, cols)
    board: Board = (row_a, full, row_b, full, row_c)

    new_board, cleared = clear_lines(board)
    assert cleared == 2
    assert len(new_board) == 5
    assert new_board == (
        _empty_row(cols),
        _empty_row(cols),
        row_a,
        row_b,
        row_c,
    )


def test_clear_lines_returns_new_object() -> None:
    """clear_lines 返回新棋盘对象，原棋盘不被修改。"""
    cols = 10
    full = _full_row(PieceType.T, cols)
    board: Board = (_empty_row(cols), full)

    original = board
    new_board, cleared = clear_lines(board)
    assert cleared == 1
    assert new_board is not board
    assert board == original  # 原棋盘内容不变
    assert new_board == (_empty_row(cols), _empty_row(cols))
