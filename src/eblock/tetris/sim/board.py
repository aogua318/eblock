"""棋盘存储、碰撞检测、落子、消行，全部不可变。

本模块只依赖 tetromino 模块中的 Cells 与 PieceType，不依赖 pygame；
所有函数均返回新对象，不修改传入的棋盘，保证模拟层状态可预测、可序列化。
"""

from eblock.tetris.sim.tetromino import Cells, PieceType

# 棋盘类型：外层元组按行（y）索引，内层元组按列（x）索引；
# 每格为 PieceType（已落定的方块）或 None（空格）。
Board = tuple[tuple[PieceType | None, ...], ...]


def empty_board(rows: int, cols: int) -> Board:
    """创建一张全空的棋盘。

    参数:
        rows: 棋盘总行数，含顶部隐藏出生区（例如配置中 22 行）。
        cols: 棋盘列数（宽度），例如配置中 10 列。

    返回:
        一个 rows × cols 的棋盘，所有格子均为 None（空格）。
        外元组长度为 rows，内元组长度为 cols。
    """
    #写明白一点 太浓缩了看太绕
    return tuple(tuple(None for _ in range(cols)) for _ in range(rows))


def collides(board: Board, x: int, y: int, cells: Cells) -> bool:
    """判断方块相对格放在给定原点时是否与棋盘碰撞。

    参数:
        board: 目标棋盘，通过 len(board) 与 len(board[0]) 推断行数 rows 与列数 cols。
        x: 方块原点（cells 中的 (0, 0)）要放置的列坐标。
        y: 方块原点（cells 中的 (0, 0)）要放置的行坐标。
        cells: 方块的相对格集合，每个元素为 (dx, dy) 相对坐标，
            实际棋盘坐标为 (x + dx, y + dy)。

    返回:
        True 表示发生碰撞（任一相对格换算后越界或已被占用）；
        False 表示所有相对格均可放置。
        碰撞判定规则：board_x < 0、board_x >= cols、board_y >= rows 或
        board[board_y][board_x] 非 None 即碰撞；board_y < 0 永远视为空、不碰撞。
    """
    ...


def place(board: Board, piece_type: PieceType, x: int, y: int, cells: Cells) -> Board:
    """把方块写入棋盘并返回新棋盘（原棋盘不变）。

    参数:
        board: 目标棋盘，函数不会修改它。
        piece_type: 要写入的方块种类，作为格子内容写入（如 PieceType.T）。
        x: 方块原点在棋盘上的列坐标。
        y: 方块原点在棋盘上的行坐标。
        cells: 方块的相对格集合，每个元素为 (dx, dy) 相对坐标，
            实际写入坐标为 (x + dx, y + dy)。

    返回:
        写入后的新棋盘。写入规则：所有 y >= 0 的相对格（即实际行坐标
        y + dy >= 0）写入 piece_type；实际行坐标小于 0 的格子忽略不写。
    """
    ...


def clear_lines(board: Board) -> tuple[Board, int]:
    """消除所有满行并返回 (新棋盘, 消除行数)。

    参数:
        board: 待处理的棋盘，函数不会修改它。

    返回:
        二元组 (新棋盘, 消除行数)：
        - 新棋盘：消除满行后，自上而下保留所有未满行（顺序不变），
          顶部补足等量的空行，保证行数不变、消除后无悬空。
        - 消除行数：本次消除的满行数量（0 表示无满行，返回原棋盘等价形状）。
        满行判定：棋盘某一行全部格子均非 None（例如 10 列全部占满）。
    """
    ...
