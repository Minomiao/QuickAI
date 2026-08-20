"""主命令循环（main_loop）单元测试：分派表完整性、命令解析与分发行为。"""
import unittest
from unittest.mock import patch

from modules.CLIserver import main_loop
from modules.CLIserver.commands import get_command_keyword
from modules.CLIserver.main_loop import _QUIT, _parse_command, _cmd_quit, _cmd_back
from modules.CLIserver.state import state

# 默认命令名（与 commands.py 默认表对应）
COMMAND_NAMES = [
    "help", "clear", "model", "set", "open", "new", "list", "load",
    "back", "quit", "tools", "skills", "changes", "showthinking",
    "effort", "toggle", "language",
]


class TestCommandTable(unittest.TestCase):
    """命令分派表完整性。"""

    def test_covers_all_default_commands(self):
        for name in COMMAND_NAMES:
            keyword = get_command_keyword(name)
            self.assertIn(keyword, main_loop._COMMAND_TABLE, f"缺少命令 {name}")

    def test_all_handlers_callable(self):
        for keyword, handler in main_loop._COMMAND_TABLE.items():
            self.assertTrue(callable(handler), f"{keyword} 的处理器不可调用")

    def test_keywords_non_empty(self):
        for keyword in main_loop._COMMAND_TABLE:
            self.assertTrue(keyword, "关键词不能为空")

    def test_quit_handler_returns_quit(self):
        self.assertIs(_cmd_quit(None), _QUIT)

    def test_back_handler_returns_none(self):
        self.assertIsNone(_cmd_back(None))


class TestParseCommand(unittest.TestCase):
    """命令解析逻辑。"""

    def test_non_command_returns_none(self):
        self.assertIsNone(_parse_command("hello world", "/"))

    def test_bare_keyword(self):
        self.assertEqual(_parse_command("/help", "/"), ("help", ""))

    def test_keyword_with_args(self):
        self.assertEqual(_parse_command("/open D:/codes", "/"), ("open", "D:/codes"))

    def test_multiple_spaces_between_keyword_and_args(self):
        self.assertEqual(_parse_command("/effort   high", "/"), ("effort", "high"))

    def test_case_insensitive(self):
        self.assertEqual(_parse_command("/HELP", "/"), ("help", ""))

    def test_custom_prefix(self):
        self.assertEqual(_parse_command("!help", "!"), ("help", ""))


class TestMainLoopDispatch(unittest.IsolatedAsyncioTestCase):
    """主循环分发行为（mock input 驱动）。"""

    def setUp(self):
        state.current_config = {"command_prefix": "/"}

    async def test_unknown_command_prints_and_continues(self):
        with patch("builtins.input", side_effect=["/nosuch", EOFError]), \
                patch("builtins.print") as fake_print:
            await main_loop.main()
        fake_print.assert_any_call(
            main_loop.i18n.t("main.unknown_command", keyword="nosuch"))

    async def test_quit_exits_immediately(self):
        with patch("builtins.input", side_effect=["/quit"]) as fake_input, \
                patch("builtins.print") as fake_print:
            await main_loop.main()
        fake_input.assert_called_once()
        fake_print.assert_any_call(main_loop.i18n.t("main.goodbye"))

    async def test_back_continues_loop(self):
        with patch("builtins.input", side_effect=["/back", EOFError]), \
                patch("builtins.print"):
            await main_loop.main()
        # back 无操作后继续循环，EOFError 正常退出即通过

    async def test_help_forwards_to_display(self):
        with patch("builtins.input", side_effect=["/help", EOFError]), \
                patch("modules.CLIserver.main_loop.show_help") as fake_show_help:
            await main_loop.main()
        fake_show_help.assert_called_once_with()

    async def test_changes_forwards_via_lazy_import(self):
        with patch("builtins.input", side_effect=["/changes", EOFError]), \
                patch("modules.CLIserver.changes.handle_pending_changes") as fake:
            await main_loop.main()
        fake.assert_called_once_with()

    async def test_showthinking_no_args_prints_status(self):
        state.show_thinking = True
        with patch("builtins.input", side_effect=["/showthinking", EOFError]), \
                patch("builtins.print") as fake_print:
            await main_loop.main()
        fake_print.assert_any_call(
            main_loop.i18n.t("main.thinking_current", status=main_loop.i18n.t("main.on")))

    async def test_effort_no_args_forwards_to_settings(self):
        with patch("builtins.input", side_effect=["/effort", EOFError]), \
                patch("modules.CLIserver.main_loop.effort_settings") as fake:
            await main_loop.main()
        fake.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
