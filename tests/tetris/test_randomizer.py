"""randomizer 模块测试（实施指南 M1-S5：多模式发牌）。

覆盖:
    - seven_bag：每 7 个连续出块为全排列；同 seed 序列一致；save/load 还原；
      队列校验（重复、超长）；空队列自动补袋；
    - uniform：每次抽取合法方块；同 seed 序列一致；无袋队列语义；
    - no_repeat：任意连续两次不重复；save/load 还原袋余量；
    - create_randomizer 工厂按模式返回正确实例。
"""

import pytest

from eblock.tetris.sim.randomizer import (
    NoRepeat,
    Randomizer,
    SevenBag,
    UniformRandom,
    create_randomizer,
)
from eblock.tetris.sim.tetromino import PieceType

_ALL_PIECES: list[PieceType] = list(PieceType)


def _draw_many(randomizer: Randomizer, count: int) -> list[PieceType]:
    """连续抽取 count 个方块，返回顺序列表。"""
    return [randomizer.next() for _ in range(count)]


def _assert_permutation(pieces: list[PieceType]) -> None:
    """断言一段出块恰好包含全部 7 种各一次。"""
    assert sorted(pieces) == sorted(_ALL_PIECES)


# ==================== seven_bag ====================


def test_every_7_draws_is_permutation() -> None:
    """每 7 个连续出块恰好包含全部 7 种各一次（1000 次抽样）。"""
    bag = SevenBag(seed=123)
    draws = _draw_many(bag, 1000)
    for start in range(0, len(draws), 7):
        _assert_permutation(draws[start : start + 7])


def test_same_seed_same_sequence() -> None:
    """相同 seed 的两个 7-bag 出块序列一致。"""
    first = SevenBag(seed=42)
    second = SevenBag(seed=42)
    assert _draw_many(first, 14) == _draw_many(second, 14)


def test_save_load_restores_sequence() -> None:
    """取 3 个后 save→load，继续取 4 个与未保存方对应片段一致。"""
    saved = SevenBag(seed=7)
    reference = SevenBag(seed=7)
    _draw_many(saved, 3)
    saved.load_queue(saved.save_queue())
    restored_tail = _draw_many(saved, 4)
    reference_tail = _draw_many(reference, 7)[3:]
    assert restored_tail == reference_tail


def test_load_queue_validates_duplicates() -> None:
    """载入含重复方块的队列应抛 ValueError。"""
    bag = SevenBag(seed=1)
    with pytest.raises(ValueError):
        bag.load_queue((PieceType.T, PieceType.T))


def test_load_queue_too_long_rejected() -> None:
    """载入长度超过 7 的队列应抛 ValueError。"""
    bag = SevenBag(seed=1)
    long_queue = (
        PieceType.T,
        PieceType.I,
        PieceType.O,
        PieceType.S,
        PieceType.Z,
        PieceType.J,
        PieceType.L,
        PieceType.T,
    )
    with pytest.raises(ValueError):
        bag.load_queue(long_queue)


def test_load_empty_queue_refills() -> None:
    """载入空队列后 next() 自动补袋，仍满足每 7 个一组全排列。"""
    bag = SevenBag(seed=5)
    bag.load_queue(())
    _assert_permutation(_draw_many(bag, 7))


# ==================== uniform ====================


def test_uniform_returns_valid_pieces() -> None:
    """uniform 每次返回七种方块之一。"""
    randomizer = UniformRandom(seed=11)
    draws = _draw_many(randomizer, 200)
    assert all(piece in _ALL_PIECES for piece in draws)


def test_uniform_same_seed_same_sequence() -> None:
    """相同 seed 的两个 uniform 发牌器序列一致。"""
    first = UniformRandom(seed=5)
    second = UniformRandom(seed=5)
    assert _draw_many(first, 20) == _draw_many(second, 20)


def test_uniform_save_queue_is_empty() -> None:
    """uniform 无袋队列，save_queue 恒返回空元组。"""
    randomizer = UniformRandom(seed=2)
    randomizer.next()
    assert randomizer.save_queue() == ()


def test_uniform_load_empty_queue_ok() -> None:
    """uniform 载入空队列合法，之后可继续发牌。"""
    randomizer = UniformRandom(seed=2)
    randomizer.load_queue(())
    assert randomizer.next() in _ALL_PIECES


def test_uniform_load_non_empty_rejected() -> None:
    """uniform 载入非空队列应抛 ValueError。"""
    randomizer = UniformRandom(seed=2)
    with pytest.raises(ValueError):
        randomizer.load_queue((PieceType.T,))


# ==================== no_repeat ====================


def test_no_repeat_no_consecutive_duplicates() -> None:
    """任意连续两次不出同一方块（500 次抽样）。"""
    randomizer = NoRepeat(seed=3)
    draws = _draw_many(randomizer, 500)
    assert all(left != right for left, right in zip(draws, draws[1:], strict=False))


def test_no_repeat_same_seed_same_sequence() -> None:
    """相同 seed 的两个 no_repeat 发牌器序列一致。"""
    first = NoRepeat(seed=8)
    second = NoRepeat(seed=8)
    assert _draw_many(first, 30) == _draw_many(second, 30)


def test_no_repeat_save_load_restores_queue() -> None:
    """取 3 个后 save→load，继续取 4 个与未保存方对应片段一致。"""
    saved = NoRepeat(seed=9)
    reference = NoRepeat(seed=9)
    _draw_many(saved, 3)
    saved.load_queue(saved.save_queue())
    restored_tail = _draw_many(saved, 4)
    reference_tail = _draw_many(reference, 7)[3:]
    assert restored_tail == reference_tail


def test_no_repeat_load_queue_validates_duplicates() -> None:
    """载入含重复方块的队列应抛 ValueError。"""
    randomizer = NoRepeat(seed=1)
    with pytest.raises(ValueError):
        randomizer.load_queue((PieceType.S, PieceType.S))


# ==================== 工厂 ====================


def test_create_randomizer_returns_correct_instance() -> None:
    """工厂按模式返回对应实现实例。"""
    cases: list[tuple[str, type[Randomizer]]] = [
        ("seven_bag", SevenBag),
        ("uniform", UniformRandom),
        ("no_repeat", NoRepeat),
    ]
    for mode, expected_type in cases:
        assert isinstance(create_randomizer(mode, seed=0), expected_type)


def test_create_randomizer_unknown_mode_raises() -> None:
    """未知模式应抛 ValueError（配置层本应拦截，防御性校验）。"""
    with pytest.raises(ValueError):
        create_randomizer("bogus")  # type: ignore[arg-type]
