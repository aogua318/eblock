"""冒烟测试：验证包可导入、版本号存在。"""

from eblock import __version__


def test_version_exists() -> None:
    """包版本号必须是非空字符串。"""
    assert isinstance(__version__, str)
    assert __version__
