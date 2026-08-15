"""俄罗斯方块方块的旋转（SRS）逻辑。

提供方块相对格子的旋转计算、旋转状态校验，以及带踢墙（wall kick）的
旋转尝试（try_rotation）。属于模拟层的纯逻辑模块，不依赖渲染。
"""

from collections.abc import Callable

from eblock.tetris.sim.tetromino import Cells, PieceState, PieceType, spawn_cells

# 官方表 y 向上；应用时 y 取反。键为 (from_rotation, to_rotation)
KICK_TABLE: dict[tuple[int, int], tuple[tuple[int, int], ...]] = {
    # JLSTZ 方块的 SRS 踢墙表。
    #旋转前后状态：原点偏移序列，先尝试(0, 0)，再尝试(1, 0),再尝试(-1, 1)...
    (0, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (1, 0): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (1, 2): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (2, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (2, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    (3, 2): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (3, 0): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (0, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
}

# I 方块使用独立的 SRS 踢墙表；其偏移序列与 JLSTZ 不同。
_I_KICK_TABLE: dict[tuple[int, int], tuple[tuple[int, int], ...]] = {
    (0, 1): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (1, 0): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (1, 2): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
    (2, 1): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (2, 3): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (3, 2): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (3, 0): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (0, 3): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
}


def _validate_rotation(rotation: int) -> None:
    """校验旋转状态值是否合法。

    旋转状态必须是 0、1、2、3 之一，否则抛出 ValueError。
    该函数为内部工具函数，供本模块其余函数在计算前统一校验输入。

    参数:
        rotation: 待校验的旋转状态值（0=初始方向，1=顺时针 90°，2=顺时针 180°，3=顺时针 270°）。

    返回:
        无。仅做校验，不返回任何值。

    异常:
        ValueError: 当 rotation 不在 0..3 范围内时抛出。
    """
    if rotation not in (0, 1, 2, 3):
        raise ValueError("rotation must be one of 0, 1, 2, or 3")


def _rotate_once(cells: Cells, cw: bool) -> Cells:
    """将格子集合按屏幕坐标系旋转 90 度。

    屏幕坐标系约定 x 向右、y 向下（与数学坐标系 y 向上相反），
    因此顺时针/逆时针的坐标变换公式与数学公式的符号相反。
    该函数为内部工具函数，只旋转一次，不做多次累积旋转。

    x' = x·cos θ − y·sin θ 顺时针90度  x' = y
    y' = x·sin θ + y·cos θ 顺时针90度  y' = -x
    (x,y) 顺时针90度 = (y,-x)

    游戏里Y值增加为向下移动所以
    x' = x·cos θ + y·sin θ 顺时针90度  x' = -y
    y' = x·sin θ - y·cos θ 顺时针90度  y' = x
    (x,y) 顺时针90度 = (-y,x)

    参数:
        cells: 待旋转的格子集合，每个元素为 (x, y) 相对坐标。
        cw: True 表示顺时针旋转 90 度；False 表示逆时针旋转 90 度。

    返回:
        旋转后的新格子集合，元素仍为 (x, y) 相对坐标，顺序与入参一致。
    """
    if cw:
        return tuple((-y, x) for x, y in cells)
    return tuple((y, -x) for x, y in cells)


def rotate_cells(piece_type: PieceType, rotation: int, cw: bool) -> Cells:
    """返回将方块旋转到指定状态后的相对格子集合。

    先取方块在目标 rotation 状态下的相对格子，再按 cw 方向旋转一次得到最终格子；
    O 方块任意方向旋转后形状不变，恒等于出生态。

    参数:
        piece_type: 方块种类（PieceType 枚举），决定初始形状。
        rotation: 目标旋转状态（0..3，0=初始方向，顺时针递增）。
        cw: True 表示顺时针旋转 90 度；False 表示逆时针旋转 90 度。

    返回:
        旋转后的相对格子集合，每个元素为 (x, y) 相对坐标。

    异常:
        ValueError: 当 rotation 不在 0..3 范围内时抛出。
    """
    _validate_rotation(rotation)
    cells = cells_at_rotation(piece_type, rotation)
    if piece_type is PieceType.O:
        return cells
    return _rotate_once(cells, cw)


def cells_at_rotation(piece_type: PieceType, rotation: int) -> Cells:
    """返回方块在任意旋转状态下的相对格子集合。

    从出生态开始，按顺时针方向逐次旋转 rotation 次得到目标状态；
    O 方块形状不随旋转变化，直接返回出生态。

    参数:
        piece_type: 方块种类（PieceType 枚举），决定初始形状。
        rotation: 目标旋转状态（0..3，0=初始方向，顺时针递增）。

    返回:
        指定旋转状态下的相对格子集合，每个元素为 (x, y) 相对坐标。

    异常:
        ValueError: 当 rotation 不在 0..3 范围内时抛出。
    """
    _validate_rotation(rotation)
    cells = spawn_cells(piece_type)
    if piece_type is PieceType.O:
        return cells
    for _ in range(rotation):
        cells = _rotate_once(cells, cw=True)
    return cells


# 碰撞检测回调类型：给定方块原点棋盘坐标 (x, y) 与相对格子集合 cells，
# 返回方块放置在该位置时是否与场地边界/已堆叠方块发生碰撞。
# 定义函数类型 CollisionCheck
CollisionCheck = Callable[[int, int, Cells], bool]


def try_rotation(
    current: PieceState,
    cw: bool,
    collides: CollisionCheck,
) -> PieceState:
    """尝试旋转并执行踢墙（wall kick），返回旋转后的新状态。

    先按 cw 方向计算目标旋转状态及其相对格子，再按方块种类的 SRS 踢墙表
    依次尝试各偏移位置，找到第一个不与场地碰撞的位置即为结果；
    O 方块无踢墙逻辑，仅尝试原位。若所有偏移均发生碰撞，则旋转失败，返回原状态。

    参数:
        current: 当前方块状态（方块种类、旋转状态、原点坐标），旋转以此为基础。
        cw: True 表示顺时针旋转 90 度；False 表示逆时针旋转 90 度。
        collides: 碰撞检测回调（见 CollisionCheck 类型），签名 (x, y, cells) -> bool，
            用于判断方块原点位于 (x, y) 且格子为 cells 时是否与场地边界或堆叠方块冲突。

    返回:
        旋转成功时返回新的 PieceState（包含新旋转状态与踢墙后的原点坐标）；
        全部偏移均失败时返回传入的 current 原对象（不发生修改）。
    """
    old_rotation = current.rotation
    new_rotation = (old_rotation + (1 if cw else -1)) % 4
    #返回旋转后的新格子集合
    cells = cells_at_rotation(current.piece_type, new_rotation)

    #根据方块种类获取对应的踢墙表
    kicks: tuple[tuple[int, int], ...]
    if current.piece_type is PieceType.O:
        kicks = ((0, 0),)
    elif current.piece_type is PieceType.I:
        kicks = _I_KICK_TABLE[(old_rotation, new_rotation)]
    else:
        kicks = KICK_TABLE[(old_rotation, new_rotation)]

    for kick_x, kick_y in kicks:
        x = current.x + kick_x  #当前坐标+相对偏移
        y = current.y - kick_y  #当前坐标-相对偏移  y轴的移动与踢墙表数据相反
        if not collides(x, y, cells):
            return PieceState(current.piece_type, new_rotation, x, y)

    return current
