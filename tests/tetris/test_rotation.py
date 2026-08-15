"""rotation 模块测试（实施指南 M1-S3）。

覆盖:
    - rotate_cells / cells_at_rotation 的旋转公式（开发文档 §6.2）；
    - O 方块任意旋转形状不变；
    - 连续顺时针旋转 4 次回到出生态；
    - try_rotation 的踢墙流程（SRS 表 §6.3）与全部失败回退。
"""

from eblock.tetris.sim.rotation import cells_at_rotation, rotate_cells, try_rotation
from eblock.tetris.sim.tetromino import Cells, PieceState, PieceType, spawn_cells


def _no_collision(x: int, y: int, cells: Cells) -> bool:
    """碰撞回调：任何位置都不碰撞（模拟开阔空间）。"""
    return False


def _always_collision(x: int, y: int, cells: Cells) -> bool:
    """碰撞回调：任何位置都碰撞（模拟全封闭场地）。"""
    return True


def test_rotate_cells_t_cw_matches_formula() -> None:
    """T 方块顺时针旋转：结果与 §6.2 公式 (x,y)->(-y,x) 一致。"""
    result = rotate_cells(PieceType.T, rotation=0, cw=True)
    assert set(result) == {(0, -1), (1, 0), (0, 0), (0, 1)}


def test_rotate_cells_t_ccw_matches_formula() -> None:
    """T 方块逆时针旋转：结果与 §6.2 公式 (x,y)->(y,-x) 一致。"""
    result = rotate_cells(PieceType.T, rotation=0, cw=False)
    assert set(result) == {(0, 1), (-1, 0), (0, 0), (0, -1)}


def test_rotate_cells_i_horizontal_to_vertical() -> None:
    """I 方块从水平旋转为垂直：4 格沿 y 轴排成竖线。"""
    result = rotate_cells(PieceType.I, rotation=0, cw=True)
    assert set(result) == {(0, -1), (0, 0), (0, 1), (0, 2)}


def test_rotate_cells_o_unchanged() -> None:
    """O 方块在任意旋转状态与方向下形状不变。"""
    for rotation in range(4):
        for cw in (True, False):
            result = rotate_cells(PieceType.O, rotation=rotation, cw=cw)
            assert set(result) == set(spawn_cells(PieceType.O))


def test_cells_at_rotation_o_unchanged() -> None:
    """cells_at_rotation 对 O 方块任意状态返回出生态。"""
    for rotation in range(4):
        assert set(cells_at_rotation(PieceType.O, rotation)) == set(
            spawn_cells(PieceType.O)
        )


def test_four_cw_rotations_return_to_original_cells() -> None:
    """连续顺时针旋转 4 次后，格子集合回到出生态。"""
    for piece_type in PieceType:
        cells = spawn_cells(piece_type)
        for rotation in range(4):
            cells = rotate_cells(piece_type, rotation=rotation, cw=True)
        assert set(cells) == set(spawn_cells(piece_type))


def test_try_rotation_succeeds_in_open_space() -> None:
    """开阔空间旋转成功：旋转状态 +1，原点位置不变。"""
    current = PieceState(piece_type=PieceType.T, rotation=0, x=5, y=5)
    result = try_rotation(current, cw=True, collides=_no_collision)
    assert result.rotation == 1
    assert result.x == 5
    assert result.y == 5
    assert result.piece_type is PieceType.T


def test_try_rotation_kick_at_left_wall() -> None:
    """贴墙旋转：原位碰撞时按踢墙表尝试 (−1,0)，原点左移 1 成功。"""
    current = PieceState(piece_type=PieceType.T, rotation=0, x=1, y=5)

    # 模拟宽度 2 的贴墙棋盘：x < 0 或 x >= 2 均视为碰撞。
    # T 0→R 旋转后最右格绝对 x=2 越界（原位失败），左移一格后落在合法区域。
    def collides(x: int, y: int, cells: Cells) -> bool:
        return any(cx < 0 or cx >= 2 for cx, cy in cells)

    result = try_rotation(current, cw=True, collides=collides)
    assert result.rotation == 1
    assert result.x == 0
    assert result.y == 5


def test_kick_y_offset_is_flipped() -> None:
    """踢墙 y 偏移符号翻转：表内 (0,-2) 应用后新 y = 旧 y + 2。"""
    current = PieceState(piece_type=PieceType.T, rotation=0, x=0, y=5)

    # 只有原点 (0, 7) 可行：前三个踢墙偏移全部失败，(0,-2) 成功。
    def collides(x: int, y: int, cells: Cells) -> bool:
        return not (x == 0 and y == 7)

    result = try_rotation(current, cw=True, collides=collides)
    assert result.rotation == 1
    assert result.x == 0
    assert result.y == 7


def test_try_rotation_all_kicks_fail_returns_same_object() -> None:
    """全部踢墙偏移失败时返回传入的原对象（is 比较）。"""
    current = PieceState(piece_type=PieceType.T, rotation=0, x=5, y=5)
    result = try_rotation(current, cw=True, collides=_always_collision)
    assert result is current
