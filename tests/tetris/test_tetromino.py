"""tetromino 模块测试（实施指南 M1-S2）。

覆盖:
    - PieceType 恰好包含七种方块；
    - 每种方块出生态恰好 4 格；
    - 出生态坐标与开发文档 §6.1 逐格一致（集合比较，顺序不敏感）；
    - PieceState 为冻结数据类，修改字段抛 FrozenInstanceError。
"""

from dataclasses import FrozenInstanceError

import pytest

from eblock.tetris.sim.tetromino import SPAWN_SHAPES, Cells, PieceState, PieceType, spawn_cells

# 开发文档 §6.1 的出生态坐标（相对原点，x 向右 / y 向下）。
_DOC_SHAPES: dict[PieceType, Cells] = {
    PieceType.I: ((-1, 0), (0, 0), (1, 0), (2, 0)),
    PieceType.J: ((-1, -1), (-1, 0), (0, 0), (1, 0)),
    PieceType.L: ((1, -1), (-1, 0), (0, 0), (1, 0)),
    PieceType.O: ((0, 0), (1, 0), (0, 1), (1, 1)),
    PieceType.S: ((0, -1), (1, -1), (-1, 0), (0, 0)),
    PieceType.T: ((-1, 0), (0, -1), (0, 0), (1, 0)),
    PieceType.Z: ((-1, -1), (0, -1), (0, 0), (1, 0)),
}


def test_piece_type_has_seven_members() -> None:
    """PieceType 必须恰好包含 I/O/T/S/Z/J/L 七种方块。"""
    assert len(list(PieceType)) == 7
    assert {piece.name for piece in PieceType} == {"I", "O", "T", "S", "Z", "J", "L"}


def test_spawn_shapes_have_exactly_four_cells() -> None:
    """每种方块的出生态恰好由 4 个格子组成。"""
    for piece_type in PieceType:
        assert len(SPAWN_SHAPES[piece_type]) == 4


def test_spawn_shapes_match_documentation() -> None:
    """出生态坐标与开发文档 §6.1 逐格一致（集合比较，顺序不敏感）。"""
    for piece_type in PieceType:
        assert set(SPAWN_SHAPES[piece_type]) == set(_DOC_SHAPES[piece_type])


def test_spawn_cells_returns_documented_shape() -> None:
    """spawn_cells 公共接口返回与文档一致的出生态格子。"""
    for piece_type in PieceType:
        assert set(spawn_cells(piece_type)) == set(_DOC_SHAPES[piece_type])


def test_piece_state_is_frozen() -> None:
    """PieceState 为冻结数据类：修改字段应抛 FrozenInstanceError。"""
    state = PieceState(piece_type=PieceType.T, rotation=0, x=4, y=0)
    with pytest.raises(FrozenInstanceError):
        state.rotation = 1
