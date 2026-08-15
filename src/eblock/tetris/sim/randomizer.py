"""发牌器（方块随机算法）模块：多模式、可存档还原。

提供统一的 Randomizer 协议与三种发牌算法：
- seven_bag：7-bag，每 7 个连续出块恰好包含全部 7 种各一次
  （标准 Guideline 风格，袋余量可精确存档还原）；
- uniform：每次调用独立等概率抽取七种之一（真随机，不维护袋，
  存档只保留空队列，序列不可精确还原）；
- no_repeat：保证任意连续两次不出同一方块（袋间衔接时调整首块）。

Game 只依赖 Randomizer 协议，通过 create_randomizer 工厂按配置中的
randomizer.mode 创建具体实例，不感知算法细节。
"""

import random
from typing import Protocol

from eblock.tetris.config import RandomizerMode
from eblock.tetris.sim.tetromino import PieceType

# 七种方块的有序元组，供 choice / shuffle 复用。
_ALL_PIECES: tuple[PieceType, ...] = tuple(PieceType)


class Randomizer(Protocol):
    """发牌器统一接口（协议）。

    Game 与存档逻辑只依赖本协议：
    - next 负责产出下一个方块；
    - save_queue / load_queue 负责把「尚未发出的袋余量」写入/恢复存档。

    方法:
        next: 返回下一个方块种类。
        save_queue: 返回尚未发出的袋余量元组（不含已发出的部分）。
        load_queue: 用给定队列替换袋余量，用于存档还原。
    """

    def next(self) -> PieceType:
        """返回下一个方块种类。"""

    def save_queue(self) -> tuple[PieceType, ...]:
        """返回尚未发出的袋余量元组。"""

    def load_queue(self, queue: tuple[PieceType, ...]) -> None:
        """用给定队列替换袋余量（存档还原）。"""


def _validate_queue(queue: tuple[PieceType, ...]) -> None:
    """校验存档还原用的队列：无重复、长度不超过 7。

    参数:
        queue: 待校验的袋余量元组。

    返回:
        None（校验不通过直接抛异常）。

    抛出:
        ValueError: 队列长度超过 7，或包含重复方块。
    """
    if len(queue) > 7:
        raise ValueError(f"队列长度不能超过 7，实际为 {len(queue)}")
    if len(set(queue)) != len(queue):
        raise ValueError("队列中存在重复方块")


class SevenBag:
    """7-bag 发牌器：每 7 个连续出块恰好包含全部 7 种各一次。

    内部维护一个洗牌后的袋（剩余未发部分）；袋空时用 rng 重新洗牌。
    seed 注入保证测试可复现；save_queue / load_queue 支持存档精确还原。
    """

    def __init__(self, seed: int | None = None) -> None:
        """初始化发牌器。

        参数:
            seed: 随机种子；None 表示使用系统随机源（不可复现）。
        """
        self._rng = random.Random(seed)
        self._queue: list[PieceType] = []

    def next(self) -> PieceType:
        """返回下一个方块；袋空时重新洗牌补袋，从袋尾弹出。

        返回:
            下一个方块种类（PieceType 枚举成员）。
        """
        if not self._queue:
            self._queue = list(PieceType)
            self._rng.shuffle(self._queue)
        return self._queue.pop()

    def save_queue(self) -> tuple[PieceType, ...]:
        """返回当前袋余量的元组副本（尚未发出的部分）。"""
        return tuple(self._queue)

    def load_queue(self, queue: tuple[PieceType, ...]) -> None:
        """用给定队列替换袋余量（存档还原）。

        参数:
            queue: 存档中的袋余量元组；空元组合法，下次 next() 自动补袋。

        抛出:
            ValueError: 队列含重复方块或长度超过 7（见 _validate_queue）。
        """
        _validate_queue(queue)
        self._queue = list(queue)


class UniformRandom:
    """均匀随机发牌器：每次调用独立等概率抽取七种之一。

    不维护袋队列，因此 save_queue 恒返回空元组，load_queue 只接受空队列；
    该模式不持久化随机数状态，存档还原后无法保证与还原前序列一致，
    属于「独立随机优先、放弃可复现性」的设计取舍。
    """

    def __init__(self, seed: int | None = None) -> None:
        """初始化发牌器。

        参数:
            seed: 随机种子；None 表示使用系统随机源（不可复现）。
        """
        self._rng = random.Random(seed)

    def next(self) -> PieceType:
        """返回下一个方块：七种等概率独立抽取。"""
        return self._rng.choice(_ALL_PIECES)

    def save_queue(self) -> tuple[PieceType, ...]:
        """uniform 模式无袋队列，恒返回空元组。"""
        return ()

    def load_queue(self, queue: tuple[PieceType, ...]) -> None:
        """uniform 模式不接受非空队列。

        参数:
            queue: 必须为空元组。

        抛出:
            ValueError: 队列非空（uniform 模式不保存袋余量）。
        """
        if queue:
            raise ValueError("uniform 模式不保存队列，只能载入空队列")


class NoRepeat:
    """免连续重复发牌器：任意连续两次不出同一方块。

    以 7-bag 为基础：同一袋内天然无重复；跨袋衔接时若袋首块与上一块
    相同，则与袋内第二个位置交换，保证边界也不连续重复。

    存档只恢复袋余量，不恢复「上一块」记忆；load 后仍满足免重复性质，
    但不保证与 load 前的出块序列完全一致。
    """

    def __init__(self, seed: int | None = None) -> None:
        """初始化发牌器。

        参数:
            seed: 随机种子；None 表示使用系统随机源（不可复现）。
        """
        self._rng = random.Random(seed)
        self._queue: list[PieceType] = []
        self._last: PieceType | None = None

    def _refill(self) -> None:
        """洗牌生成新袋，并保证袋首块与上一块不重复。"""
        bag = list(PieceType)
        self._rng.shuffle(bag)
        if self._last is not None and bag[0] == self._last and len(bag) > 1:
            bag[0], bag[1] = bag[1], bag[0]
        self._queue = bag

    def next(self) -> PieceType:
        """返回下一个方块，并保证与上一次返回的方块不重复。"""
        if not self._queue:
            self._refill()
        piece = self._queue.pop()
        self._last = piece
        return piece

    def save_queue(self) -> tuple[PieceType, ...]:
        """返回当前袋余量的元组副本（尚未发出的部分）。"""
        return tuple(self._queue)

    def load_queue(self, queue: tuple[PieceType, ...]) -> None:
        """用给定队列替换袋余量（存档还原），并清空上一块记忆。

        参数:
            queue: 存档中的袋余量元组；空元组合法，下次 next() 自动补袋。

        抛出:
            ValueError: 队列含重复方块或长度超过 7（见 _validate_queue）。
        """
        _validate_queue(queue)
        self._queue = list(queue)
        self._last = None


def create_randomizer(mode: RandomizerMode, seed: int | None = None) -> Randomizer:
    """按配置模式创建对应的发牌器实例（工厂）。

    参数:
        mode: 发牌算法模式，取值 seven_bag / uniform / no_repeat。
        seed: 随机种子；None 表示随机（不可复现）。

    返回:
        实现 Randomizer 协议的发牌器实例（SevenBag / UniformRandom / NoRepeat）。

    抛出:
        ValueError: mode 不在合法模式集合内（配置层已拦截，此处防御性保留）。
    """
    if mode == "seven_bag":
        return SevenBag(seed)
    if mode == "uniform":
        return UniformRandom(seed)
    if mode == "no_repeat":
        return NoRepeat(seed)
    raise ValueError(f"未知发牌模式: {mode}")
