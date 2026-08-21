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
    # 创建一个 rows × cols 的棋盘，所有格子均为 None（空格）  tuple类型
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
    cols = len(board[0])
    rows = len(board)

    # 与边界碰撞
    for dx, dy in cells:
        board_x, board_y = x + dx, y + dy

        # board_y < 0 进行下一格判定。
        if board_y < 0:
            continue
        # x轴 y轴边界碰撞
        if board_x < 0 or board_x >= cols or board_y >= rows:
            return True
        # 非None碰撞
        if board[board_y][board_x] is not None:
            return True

    return False


def place(board: Board, piece_type: PieceType, x: int, y: int, cells: Cells) -> Board:
    """把方块写入棋盘并返回新棋盘（原棋盘不变）。   方块落地后固定化

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

    抛出:
        ValueError: 任一实际格子坐标超出棋盘范围（board_x < 0、
            board_x >= cols 或 board_y >= rows）时抛出，消息包含越界坐标。
            正常调用应先通过 collides 校验，此处为防御调用方错误。
    """

    rows = len(board)
    cols = len(board[0])

    new_board_list = [list(item) for item in board]
    for dx, dy in cells:
        board_x, board_y = x + dx, y + dy
        if board_y < 0:
            continue
        # 显式越界校验：正常流程先经 collides 校验，这里防御调用方传入非法坐标。
        if board_x < 0 or board_x >= cols or board_y >= rows:
            raise ValueError(f"place 越界: 格子 ({board_x}, {board_y}) 超出 {rows}x{cols} 棋盘")
        new_board_list[board_y][board_x] = piece_type  # 类型方便指定颜色

    new_board = tuple(tuple(item) for item in new_board_list)
    return new_board


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
    cols = len(board[0])

    # 自上而下遍历各行：满行计数，未满行按原顺序收集。
    kept_rows: list[tuple[PieceType | None, ...]] = []
    cleared_count = 0
    for row in board:
        if all(cell is not None for cell in row):
            cleared_count += 1
        else:  # 如果不满行，则保留该行
            kept_rows.append(row)

    # 顶部补足与消除行数相等的空行，保证总行数不变、消除后无悬空。
    empty_row: tuple[PieceType | None, ...] = (None,) * cols
    # 创建新棋盘：顶部补足空行 + 未满行    [empty_row] * cleared_count 空行 + kept_rows 未满行
    new_board: Board = tuple([empty_row] * cleared_count + kept_rows)

    return new_board, cleared_count
