"""subagent 技能单元测试：委派参数传递、结果裁剪、防递归白名单。"""
import asyncio
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from skills.subagent import skill as subagent


def _fake_chat_ai_sync(**kwargs):
    """捕获参数并返回可配置的假结果。"""
    subagent._last_call = kwargs
    return {
        "content": "这是子代理的结论",
        "truncated": False,
        "tool_calls": [
            {"name": "skill_file_manager_list_dir", "arguments": "{}", "result": "a.txt\nb.txt"},
        ],
    }


class _Ctx:
    work_directory = "D:/work"


class TestDelegate(unittest.TestCase):
    """delegate 的参数传递与结果裁剪。"""

    def setUp(self):
        subagent._last_call = {}

    def test_delegates_task_with_defaults(self):
        """默认禁工具（纯推理），prompt 即任务书。"""
        with patch("modules.functions.ai_caller.chat_ai_sync",
                   side_effect=_fake_chat_ai_sync):
            result = subagent.delegate(_Ctx(), "总结 D:/work 下的文件")

        self.assertTrue(result["success"])
        self.assertEqual(result["conclusion"], "这是子代理的结论")
        self.assertFalse(result["truncated"])
        call = subagent._last_call
        self.assertEqual(call["prompt"], "总结 D:/work 下的文件")
        self.assertFalse(call["enable_tools"])
        self.assertIsNone(call["allowed_tools"])

    def test_use_tools_whitelist_excludes_self(self):
        """use_tools 时白名单只含文件类工具——subagent 自身被排除（防递归）。"""
        with patch("modules.functions.ai_caller.chat_ai_sync",
                   side_effect=_fake_chat_ai_sync):
            subagent.delegate(_Ctx(), "探查目录", use_tools=True)

        allowed = subagent._last_call["allowed_tools"]
        self.assertEqual(allowed, ["file_manager", "file_reader"])
        self.assertTrue(subagent._last_call["enable_tools"])
        self.assertTrue(all("subagent" not in a for a in allowed))

    def test_work_directory_injected(self):
        """子代理工作目录来自 SkillContext。"""
        with patch("modules.functions.ai_caller.chat_ai_sync",
                   side_effect=_fake_chat_ai_sync):
            subagent.delegate(_Ctx(), "task")

        self.assertEqual(subagent._last_call["work_directory"], "D:/work")

    def test_tool_summary_truncated(self):
        """工具轨迹仅保留摘要（结果截断到 80 字符）。"""
        with patch("modules.functions.ai_caller.chat_ai_sync",
                   side_effect=_fake_chat_ai_sync):
            result = subagent.delegate(_Ctx(), "task")

        self.assertEqual(result["tool_summary"],
                         ["skill_file_manager_list_dir: a.txt\nb.txt"])

    def test_long_conclusion_truncated(self):
        """超长结论裁剪并标注。"""
        def _long(**kwargs):
            return {"content": "长" * 5000, "truncated": False, "tool_calls": []}

        with patch("modules.functions.ai_caller.chat_ai_sync", side_effect=_long):
            result = subagent.delegate(_Ctx(), "task")

        self.assertIn("已截断", result["conclusion"])
        self.assertLess(len(result["conclusion"]), 4200)

    def test_empty_task_rejected(self):
        """空任务直接拒绝，不发起子会话。"""
        with patch("modules.functions.ai_caller.chat_ai_sync",
                   side_effect=_fake_chat_ai_sync):
            result = subagent.delegate(_Ctx(), "   ")

        self.assertIn("error", result)
        self.assertEqual(subagent._last_call, {})

    def test_skill_info_registers_single_tool(self):
        """skill_info 结构：单 delegate 函数，task 必填。"""
        params = subagent.skill_info["functions"]["delegate"]["parameters"]
        self.assertEqual(params["required"], ["task"])


if __name__ == "__main__":
    unittest.main()
