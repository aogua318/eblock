"""定义方块类型、出生状态、放置状态"""

from dataclasses import dataclass
from enum import Enum, auto

Cells = tuple[tuple[int, int], ...]  # 相对原点的格子集合，x 向右 / y 向下


class PieceType(Enum):
    """俄罗斯方块的标准七种方块类型（Tetromino）。

    每种成员对应一种由 4 个方块组成的形状：
    I：一字长条，占 1×4 格；
    O：正方形，占 2×2 格；
    T：T 字形，一行三格加中间上方一格；
    S：S 形（上排格子靠右、下排格子靠左，即右高左低）；
    Z：Z 形（上排格子靠左、下排格子靠右，即左高右低）；
    J：J 形（底部三格、左上方多一格）；
    L：L 形（底部三格、右上方多一格）。
    """

    I = auto()  # noqa: E741
    O = auto()  # noqa: E741
    T = auto()
    S = auto()
    Z = auto()
    J = auto()
    L = auto()


# 出生态（rotation=0）坐标，逐字采用开发文档 §6.1 表格。
# 坐标原点和 y 轴方向由文档约定：x 向右，y 向下。
# 原点约定：JLSTZ 取 3×3 包围盒中心；I 取 4×4 包围盒左数第 2 格、上数第 2 格；
# O 取自身 2×2 左上角格。
SPAWN_SHAPES: dict[PieceType, Cells] = {
    PieceType.I: ((-1, 0), (0, 0), (1, 0), (2, 0)),
    PieceType.J: ((-1, -1), (-1, 0), (0, 0), (1, 0)),
    PieceType.L: ((1, -1), (-1, 0), (0, 0), (1, 0)),
    PieceType.O: ((0, 0), (1, 0), (0, 1), (1, 1)),
    PieceType.S: ((0, -1), (1, -1), (-1, 0), (0, 0)),
    PieceType.T: ((-1, 0), (0, -1), (0, 0), (1, 0)),
    PieceType.Z: ((-1, -1), (0, -1), (0, 0), (1, 0)),
}


@dataclass(frozen=True)
class PieceState:
    """方块在棋盘上的实时状态（不可变数据类）。

    记录活动方块当前的位置与旋转状态，是模拟层表示“当前下落方块”的最小单位。

    字段:
        piece_type: 方块种类（PieceType 枚举），例如 PieceType.T。
        rotation: 旋转状态，取 0..3（0=初始方向，1=顺时针 90°，2=顺时针 180°，3=顺时针 270°）。
        x: 旋转原点在棋盘上的列坐标。
        y: 旋转原点在棋盘上的行坐标。
    """

    piece_type: PieceType
    rotation: int  # 0 / 1 / 2 / 3（顺时针递增）
    x: int
    y: int


def spawn_cells(piece_type: PieceType) -> Cells:
    """返回指定方块的出生态（rotation=0）相对坐标。

    参数:
        piece_type: 方块种类（PieceType 枚举），决定出生态形状。

    返回:
        该方块出生态的相对格子集合，每个元素为 (x, y) 相对坐标；
        原点约定见 SPAWN_SHAPES 上方的注释。
    """
    return SPAWN_SHAPES[piece_type]
