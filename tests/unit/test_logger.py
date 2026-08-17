"""logger 模块（#24）单元测试：按天滚动与显式导出。

验证：
- setup_logger 使用 TimedRotatingFileHandler（跨天自动轮转）
- 同一名称重复调用返回同一 logger，不重复添加 handler
- get_thinking_logger / log_thinking 同样使用按天轮转 handler
- modules.logger 显式导出 __all__

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_logger -v
"""
import logging
import os
import sys
import tempfile
import unittest
from logging.handlers import TimedRotatingFileHandler
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.logger import __all__, get_thinking_logger, log_thinking, setup_logger
from modules.logger import logger as logger_mod


class TestLoggerRolling(unittest.TestCase):
    """验证日志按天轮转 handler 与重复调用行为。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_dir = self._tmp.name
        self.name = "Dolphin.test_rolling"
        logger_mod._thinking_logger = None  # 重置思考 logger 单例，确保 patch 生效

    def tearDown(self):
        # 清理测试注册的 handler（须 close() 释放文件句柄，否则 Windows 上
        # TemporaryDirectory.cleanup() 会因文件被占用而失败），避免污染其他测试
        for name in (self.name, "Dolphin.thinking"):
            lg = logging.getLogger(name)
            for h in list(lg.handlers):
                lg.removeHandler(h)
                h.close()
        self._tmp.cleanup()

    def test_setup_logger_uses_timed_rotating_handler(self):
        with patch("modules.bootstrap.LOG_DIR", self.log_dir):
            logger = setup_logger(self.name)
        handler = logger.handlers[0]
        self.assertIsInstance(handler, TimedRotatingFileHandler)
        logger.info("hello")
        handler.flush()
        log_file = os.path.join(self.log_dir, "dolphin.log")
        self.assertTrue(os.path.exists(log_file))
        with open(log_file, encoding="utf-8") as f:
            self.assertIn("hello", f.read())

    def test_repeat_call_returns_same_logger(self):
        with patch("modules.bootstrap.LOG_DIR", self.log_dir):
            logger1 = setup_logger(self.name)
            logger2 = setup_logger(self.name)
        self.assertIs(logger1, logger2)
        self.assertEqual(len(logger1.handlers), 1)

    def test_thinking_logger_uses_timed_rotating_handler(self):
        with patch("modules.bootstrap.LOG_DIR", self.log_dir):
            log_thinking("思考内容")
            think = get_thinking_logger()
        self.assertIsInstance(think.handlers[0], TimedRotatingFileHandler)
        think_file = os.path.join(self.log_dir, "think.log")
        self.assertTrue(os.path.exists(think_file))

    def test_exports_all(self):
        expected = {"get_logger", "setup_logger", "get_thinking_logger", "log_thinking"}
        self.assertTrue(expected.issubset(set(__all__)))


if __name__ == "__main__":
    unittest.main()
