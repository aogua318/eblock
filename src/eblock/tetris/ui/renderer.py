"""俄罗斯方块渲染器（M3，纯展示）。

职责：接收不可变 GameState 与最高分纪录，把一帧画面绘制到 pygame Surface 上。
铁律：本模块只读状态、不修改游戏数据；一切游戏变更走 Game.step()。
绘制顺序与窗口布局严格按文档 §7.1 / §7.4。
"""

import pygame

from eblock.tetris.config import TetrisConfig
from eblock.tetris.save.highscore import HighScore
from eblock.tetris.sim.game import GameState
from eblock.tetris.sim.rotation import cells_at_rotation
from eblock.tetris.sim.tetromino import PieceType, spawn_cells

# 每格像素尺寸（文档固定值）：棋盘 10×20 格 → 300×600 像素。
CELL_SIZE: int = 30

PIECE_COLORS: dict[PieceType, tuple[int, int, int]] = {
    PieceType.I: (0, 240, 240),  # 青
    PieceType.O: (240, 240, 0),  # 黄
    PieceType.T: (160, 0, 240),  # 紫
    PieceType.S: (0, 240, 0),  # 绿
    PieceType.Z: (240, 0, 0),  # 红
    PieceType.J: (0, 0, 240),  # 蓝
    PieceType.L: (240, 160, 0),  # 橙
}

BG_COLOR: tuple[int, int, int] = (18, 18, 24)  # 深色背景
GRID_COLOR: tuple[int, int, int] = (70, 70, 80)  # 浅色网格线

# 布局常量（文档 §7.1）：窗口约 560×640，棋盘区 300×600，右侧面板 220px。
_MARGIN: int = 20  # 四周留边距
_GAP: int = 20  # 棋盘区与右侧面板之间的间隙
_PANEL_WIDTH: int = 220  # 右侧面板宽度
_PREVIEW_CELL: int = 18  # 面板 HOLD/NEXT 小方块的格子尺寸
_TEXT_COLOR: tuple[int, int, int] = (230, 230, 230)  # 面板文字颜色


class Renderer:
    """把 sim 状态画到屏幕的纯展示组件。

    内部字段（由 __init__ 初始化）：
        _screen: pygame.Surface 目标表面（主窗口）。
        _config: TetrisConfig 对局配置（只读，用于棋盘尺寸与预览数量）。
        _board_origin: tuple[int, int] 棋盘可见区左上角像素坐标
            （按 §7.1 布局预留左边距与上边距）。
        _panel_origin: tuple[int, int] 右侧面板起点像素坐标
            （棋盘区 300px + 间隙后开始）。
        （可选）_font_*: pygame.font.Font 预创建的文字对象。
    """

    _screen: pygame.Surface
    _config: TetrisConfig
    _board_origin: tuple[int, int]
    _panel_origin: tuple[int, int]
    _font: pygame.font.Font
    _overlay_font: pygame.font.Font

    def __init__(self, screen: pygame.Surface, config: TetrisConfig) -> None:
        """初始化渲染器并预计算布局。

        参数:
            screen: 目标表面（主窗口）。
            config: 对局配置；棋盘尺寸、可见行数、预览数量等只读使用。

        返回:
            None。

        实现流程:
            1. 保存 screen 与 config。
            2. 预计算布局：
               - 棋盘可见区 = cols × visible_rows 格，每格 CELL_SIZE 像素；
               - 棋盘区左上角按窗口（约 560×640）与右侧 220px 面板
                 推算边距（文档 §7.1）；
               - 右侧面板内依次规划 HOLD、NEXT×preview_count、
                 SCORE / LEVEL / LINES 各区块的绘制位置。
            3. 可选：创建一次性字体对象（pygame.font.Font(None, size)），
               避免每帧创建。
        """
        self._screen = screen
        self._config = config
        # 预创建字体对象：先初始化字体模块（幂等），避免每帧创建字体。
        pygame.font.init()
        self._font = pygame.font.Font(None, 26)
        self._overlay_font = pygame.font.Font(None, 42)
        # 布局：棋盘可见区左上角与右侧面板起点（按 §7.1 推算）。
        board_px = config.board.cols * CELL_SIZE
        self._board_origin = (_MARGIN, _MARGIN)
        self._panel_origin = (_MARGIN + board_px + _GAP, _MARGIN)

    def draw(
        self,
        state: GameState,
        highscore: HighScore,
        paused: bool,
        game_over: bool,
    ) -> None:
        """绘制一帧完整画面。

        参数:
            state: 当前对局不可变快照（只读）。
            highscore: 当前模式键的最高分纪录（用于面板显示）。
            paused: 是否处于暂停状态。
            game_over: 是否已结束。

        返回:
            None。只绘制，不修改 state 与任何游戏数据。

        实现流程（严格按文档 §5.3 绘制职责顺序）:
            1. 背景与棋盘网格：只画可见区
               board[2:2 + visible_rows]（顶部 2 行隐藏出生区不画），
               每格 CELL_SIZE 像素；先铺 BG_COLOR，再画 GRID_COLOR 网格线。
            2. 已锁定方块：遍历可见区棋盘，非 None 格按 PieceType
               从 PIECE_COLORS 取色实心绘制。
            3. Ghost：把 state.current 的格子移动到 state.ghost_y，
               用该方块颜色画半透明轮廓
               （pygame.draw.rect(..., width=2)）。
            4. 当前方块：按 state.current 的位置与旋转实心绘制。
            5. 右侧面板：
               - HOLD 框：显示 state.hold 的方块（无则画空框）；
               - NEXT×preview_count：取 state.next_queue 前 N 个方块预览，
                 不足 N 个也照画；
               - SCORE / LEVEL / LINES：state.score / state.level / state.lines；
               - 最高分：highscore.score。
            6. 覆盖层：paused 时画「暂停，P 继续」；
               game_over 时画「游戏结束，R 重开，Esc 退出」。
               文本用 pygame 默认字体（pygame.font.Font(None, size)）。
        """
        board = state.board
        cols = self._config.board.cols
        visible_rows = self._config.board.visible_rows
        origin_x, origin_y = self._board_origin

        # 1. 背景与棋盘网格（只画可见区）。
        self._screen.fill(BG_COLOR)
        board_rect = pygame.Rect(
            origin_x,
            origin_y,
            cols * CELL_SIZE,
            visible_rows * CELL_SIZE,
        )
        pygame.draw.rect(self._screen, GRID_COLOR, board_rect, 1)
        for x in range(1, cols):
            px = origin_x + x * CELL_SIZE
            pygame.draw.line(
                self._screen,
                GRID_COLOR,
                (px, origin_y),
                (px, origin_y + visible_rows * CELL_SIZE),
            )
        for y in range(1, visible_rows):
            py = origin_y + y * CELL_SIZE
            pygame.draw.line(
                self._screen,
                GRID_COLOR,
                (origin_x, py),
                (origin_x + cols * CELL_SIZE, py),
            )

        # 2. 已锁定方块：遍历可见区 board[2:2+visible_rows]。
        for row in range(2, 2 + visible_rows):
            for col in range(cols):
                piece = board[row][col]
                if piece is not None:
                    self._draw_board_cell(col, row, PIECE_COLORS[piece])

        # 3. Ghost：current 移到 ghost_y 的格子，半透明轮廓。
        ghost_cells = cells_at_rotation(
            state.current.piece_type,
            state.current.rotation,
        )
        ghost_color = PIECE_COLORS[state.current.piece_type]
        for dx, dy in ghost_cells:
            self._draw_board_cell(
                state.current.x + dx,
                state.ghost_y + dy,
                ghost_color,
                width=2,
            )

        # 4. 当前方块：按 current 位置实心绘制。
        current_cells = cells_at_rotation(
            state.current.piece_type,
            state.current.rotation,
        )
        current_color = PIECE_COLORS[state.current.piece_type]
        for dx, dy in current_cells:
            self._draw_board_cell(
                state.current.x + dx,
                state.current.y + dy,
                current_color,
            )

        # 5. 右侧面板。
        self._draw_panel(state, highscore)

        # 6. 覆盖层。
        if paused:
            self._draw_overlay("暂停，P 继续")
        if game_over:
            self._draw_overlay("游戏结束，R 重开，Esc 退出")

    def _board_cell_rect(self, board_x: int, board_y: int) -> pygame.Rect:
        """把棋盘格坐标换算成屏幕像素矩形。

        参数:
            board_x: 棋盘列坐标。
            board_y: 棋盘行坐标（含顶部隐藏区，0 为第一行）。

        返回:
            该格对应的 pygame.Rect；隐藏区（board_y < 2）或可见区外的
            格子由调用方保证不会传入，本方法不做裁剪。
        """
        origin_x, origin_y = self._board_origin
        return pygame.Rect(
            origin_x + board_x * CELL_SIZE,
            origin_y + (board_y - 2) * CELL_SIZE,
            CELL_SIZE,
            CELL_SIZE,
        )

    def _draw_board_cell(
        self,
        board_x: int,
        board_y: int,
        color: tuple[int, int, int],
        *,
        width: int = 0,
    ) -> None:
        """在棋盘格坐标画一个单元格。

        参数:
            board_x: 棋盘列坐标。
            board_y: 棋盘行坐标。
            color: RGB 颜色。
            width: 0 表示实心填充；大于 0 表示边框宽度（Ghost 用）。

        返回:
            None。隐藏出生区（board_y < 2）的格子不绘制。
        """
        if board_y < 2:
            return
        rect = self._board_cell_rect(board_x, board_y)
        if width > 0:
            # 边框向内收 1px，避免盖住网格线。
            rect = rect.inflate(-2, -2)
        pygame.draw.rect(self._screen, color, rect, width)

    def _draw_preview_piece(
        self,
        center_x: int,
        center_y: int,
        piece_type: PieceType,
    ) -> None:
        """在面板指定中心点绘制小尺寸方块预览。

        参数:
            center_x: 预览区域中心像素 x。
            center_y: 预览区域中心像素 y。
            piece_type: 要预览的方块类型（用出生态绘制）。

        返回:
            None。
        """
        cells = spawn_cells(piece_type)
        min_x = min(dx for dx, _ in cells)
        max_x = max(dx for dx, _ in cells)
        min_y = min(dy for _, dy in cells)
        max_y = max(dy for _, dy in cells)
        origin_x = center_x - ((max_x - min_x + 1) * _PREVIEW_CELL) // 2
        origin_y = center_y - ((max_y - min_y + 1) * _PREVIEW_CELL) // 2
        color = PIECE_COLORS[piece_type]
        for dx, dy in cells:
            rect = pygame.Rect(
                origin_x + (dx - min_x) * _PREVIEW_CELL,
                origin_y + (dy - min_y) * _PREVIEW_CELL,
                _PREVIEW_CELL - 2,
                _PREVIEW_CELL - 2,
            )
            pygame.draw.rect(self._screen, color, rect)

    def _draw_panel(self, state: GameState, highscore: HighScore) -> None:
        """绘制右侧面板：HOLD、NEXT×preview_count、计分与最高分。

        参数:
            state: 当前对局快照（只读）。
            highscore: 当前模式键的最高分纪录。

        返回:
            None。
        """
        px, py = self._panel_origin
        # HOLD 框。
        self._screen.blit(self._font.render("HOLD", True, _TEXT_COLOR), (px, py))
        hold_box = pygame.Rect(px, py + 24, 100, 60)
        pygame.draw.rect(self._screen, GRID_COLOR, hold_box, 2)
        if state.hold is not None:
            self._draw_preview_piece(px + 50, py + 54, state.hold)

        # NEXT×preview_count：取 next_queue 前 N 个，不足 N 个也照画空框。
        next_y = py + 104
        self._screen.blit(self._font.render("NEXT", True, _TEXT_COLOR), (px, next_y))
        count = self._config.preview_count
        for i in range(count):
            box_top = next_y + 24 + i * 52
            pygame.draw.rect(
                self._screen,
                GRID_COLOR,
                pygame.Rect(px, box_top, 100, 48),
                1,
            )
            if i < len(state.next_queue):
                self._draw_preview_piece(px + 50, box_top + 24, state.next_queue[i])

        # SCORE / LEVEL / LINES / 最高分。
        text_y = next_y + 24 + count * 52 + 8
        for text in (
            f"SCORE {state.score}",
            f"LEVEL {state.level}",
            f"LINES {state.lines}",
            f"BEST {highscore.score}",
        ):
            self._screen.blit(self._font.render(text, True, _TEXT_COLOR), (px, text_y))
            text_y += 30

    def _draw_overlay(self, message: str) -> None:
        """绘制半透明覆盖层与居中提示文字。

        参数:
            message: 要显示的提示文字。

        返回:
            None。
        """
        overlay = pygame.Surface(self._screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self._screen.blit(overlay, (0, 0))
        text = self._overlay_font.render(message, True, (255, 255, 255))
        rect = text.get_rect(center=(self._screen.get_width() // 2, self._screen.get_height() // 2))
        self._screen.blit(text, rect)
