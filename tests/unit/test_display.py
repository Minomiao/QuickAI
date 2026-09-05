"""display 模块单元测试：skills 界面描述拍平与截断。"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.CLIserver.display import _flatten_desc, _SKILL_DESC_MAX


class TestFlattenDesc(unittest.TestCase):
    """_flatten_desc：多行拍平 + 超长截断。"""

    def test_single_line_short_kept(self):
        self.assertEqual(_flatten_desc("短描述"), "短描述")

    def test_multiline_flattened(self):
        """多行描述拍平为单行（pack 清单场景）。"""
        self.assertEqual(_flatten_desc("- a: 描述A\n- b: 描述B"), "- a: 描述A - b: 描述B")

    def test_overlong_truncated_with_ellipsis(self):
        text = "x" * (_SKILL_DESC_MAX + 10)
        result = _flatten_desc(text)
        self.assertEqual(len(result), _SKILL_DESC_MAX + 1)
        self.assertTrue(result.endswith("…"))
        self.assertEqual(result[:_SKILL_DESC_MAX], "x" * _SKILL_DESC_MAX)

    def test_exactly_max_width_not_truncated(self):
        text = "y" * _SKILL_DESC_MAX
        self.assertEqual(_flatten_desc(text), text)

    def test_empty_and_none(self):
        self.assertEqual(_flatten_desc(""), "")
        self.assertEqual(_flatten_desc(None), "")

    def test_whitespace_collapsed(self):
        self.assertEqual(_flatten_desc("a   \n\t  b"), "a b")

    def test_custom_width(self):
        self.assertEqual(_flatten_desc("abcdef", 3), "abc…")


if __name__ == "__main__":
    unittest.main()
