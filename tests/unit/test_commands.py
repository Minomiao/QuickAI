"""commands 模块异常分类（#18）单元测试。

验证：
- _get_prefix 对损坏 JSON / 不存在文件安全返回默认 "/"
- _validate_commands 对损坏命令文件安全跳过（不抛异常）
- save_commands 对损坏配置文件安全降级为空 dict 并继续写前缀

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_commands -v
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.CLIserver import commands


class TestGetPrefix(unittest.TestCase):
    """_get_prefix 对不同配置文件的容错。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config_file = os.path.join(self._tmp.name, "config.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_normal_prefix(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"command_prefix": ">"}, f)
        with patch("modules.bootstrap.CONFIG_FILE", self.config_file):
            self.assertEqual(commands._get_prefix(), ">")

    def test_corrupted_json_returns_default(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        with patch("modules.bootstrap.CONFIG_FILE", self.config_file):
            self.assertEqual(commands._get_prefix(), "/")

    def test_missing_file_returns_default(self):
        with patch("modules.bootstrap.CONFIG_FILE", self.config_file):
            self.assertEqual(commands._get_prefix(), "/")


class TestValidateCommands(unittest.TestCase):
    """_validate_commands 对损坏命令文件安全跳过。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cmds_file = os.path.join(self._tmp.name, "commands.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_corrupted_file_skipped(self):
        with open(self.cmds_file, "w", encoding="utf-8") as f:
            f.write("[] not json")
        with patch("modules.bootstrap.COMMANDS_FILE", self.cmds_file):
            commands._validate_commands()  # 不应抛异常

    def test_missing_file_skipped(self):
        with patch("modules.bootstrap.COMMANDS_FILE", self.cmds_file):
            commands._validate_commands()  # 不应抛异常


class TestSaveCommands(unittest.TestCase):
    """save_commands 对损坏配置文件安全降级。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config_file = os.path.join(self._tmp.name, "config.json")
        self.cmds_file = os.path.join(self._tmp.name, "commands.json")
        self.date_dir = os.path.join(self._tmp.name, "conversations")

    def tearDown(self):
        self._tmp.cleanup()

    def test_corrupted_config_falls_back_to_empty(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write("{broken")
        with patch("modules.bootstrap.CONFIG_FILE", self.config_file), \
             patch("modules.bootstrap.COMMANDS_FILE", self.cmds_file), \
             patch("modules.bootstrap.DATE_DIR", self.date_dir):
            commands.save_commands(prefix="!")
        # 前缀应写入修复后的配置文件
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["command_prefix"], "!")


if __name__ == "__main__":
    unittest.main()
