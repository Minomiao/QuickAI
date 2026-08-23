"""standard_skill_loader 的 user_output 规范格式测试。

验证 call_tool 返回的 user_output 使用规范 parts 格式（而非 content 兼容变体）。
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.loader.standard_skill_loader import StandardSkillLoader


class TestStandardSkillUserOutput(unittest.TestCase):
    """call_tool 返回的 user_output 应为规范的 parts 格式。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.loader = StandardSkillLoader(skills_dir=self._tmp.name)
        self.loader.skills = {"demo": {"body": "正文", "folder": "folder"}}

    def tearDown(self):
        self._tmp.cleanup()

    def test_call_tool_user_output_uses_parts(self):
        with patch.object(self.loader, "_resolve_skill_name", return_value=("demo", None)):
            result = self.loader.call_tool("stdskill_demo", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["user_output"]["label"], "skills")
        self.assertEqual(result["user_output"]["parts"], [{"text": "demo"}])
        self.assertNotIn("content", result["user_output"])


if __name__ == "__main__":
    unittest.main()
