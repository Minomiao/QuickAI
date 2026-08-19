"""CommandCacheManager 单元测试。

覆盖 add/get 读取后销毁、TTL 过期、容量上限转储持久化、持久化读写、
强制/按 TTL 清理、清空、统计与惰性单例。
持久化目录 patch 到临时目录（modules.bootstrap.DATE_DIR），不触碰真实数据。

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_command_cache -v
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.functions import command_cache as cache_mod
from modules.functions.command_cache import CommandCacheManager, get_command_cache_manager


class CommandCacheManagerTestBase(unittest.TestCase):
    """公共夹具：将持久化目录重定向到临时目录，每个用例使用独立实例。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        patcher = patch("modules.bootstrap.DATE_DIR", str(self.root))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cm = CommandCacheManager()

    def tearDown(self):
        self._tmp.cleanup()

    @property
    def persist_dir(self) -> Path:
        """缓存管理器实际使用的持久化目录。"""
        return self.cm._persist_dir

    def _write_persist_file(self, command_id: str, expires_at: float) -> Path:
        """直接写入一个持久化缓存文件（指定过期时间）。"""
        path = self.persist_dir / f"{command_id}.json"
        path.write_text(json.dumps({"output": "stale", "expires_at": expires_at}),
                        encoding="utf-8")
        return path


class TestAddGet(CommandCacheManagerTestBase):
    """add/get 基础行为。"""

    def test_add_get_returns_data_without_metadata(self):
        self.cm.add("cmd_1", {"status": "done", "output": "hello"})
        result = self.cm.get("cmd_1")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["output"], "hello")
        # 元数据不应透出给调用方
        self.assertNotIn("cached_at", result)
        self.assertNotIn("expires_at", result)

    def test_get_destroys_memory_entry(self):
        """AI 读取后立即销毁，再次读取返回 None。"""
        self.cm.add("cmd_1", {"output": "hello"})
        self.assertIsNotNone(self.cm.get("cmd_1"))
        self.assertIsNone(self.cm.get("cmd_1"))
        self.assertNotIn("cmd_1", self.cm._memory_cache)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.cm.get("no_such_command"))


class TestTTLExpiry(CommandCacheManagerTestBase):
    """TTL 过期处理。"""

    def _expire_memory_entry(self, command_id: str):
        """将内存条目过期时间改为过去。"""
        self.cm._memory_cache[command_id]["expires_at"] = time.time() - 1

    def test_expired_memory_entry_returns_none_and_removed(self):
        self.cm.add("cmd_1", {"output": "old"})
        self._expire_memory_entry("cmd_1")
        self.assertIsNone(self.cm.get("cmd_1"))
        self.assertNotIn("cmd_1", self.cm._memory_cache)

    def test_expired_persist_file_returns_none_and_removed(self):
        """持久化文件过期后 get 返回 None 且文件被删除。"""
        self._write_persist_file("cmd_1", expires_at=time.time() - 1)
        self.assertIsNone(self.cm.get("cmd_1"))
        self.assertFalse((self.persist_dir / "cmd_1.json").exists())

    def test_corrupted_persist_file_returns_none(self):
        """损坏的持久化文件不崩溃，get 返回 None。"""
        (self.persist_dir / "cmd_bad.json").write_text("not-json", encoding="utf-8")
        self.assertIsNone(self.cm.get("cmd_bad"))


class TestPersistOverflow(CommandCacheManagerTestBase):
    """内存容量上限：最旧条目转储到持久化。"""

    def test_overflow_dumps_oldest_then_reads_back(self):
        # MAX_COMMAND_CACHE_SIZE = 20，第 21 个 add 触发清理最旧的
        for i in range(21):
            self.cm.add(f"cmd_{i}", {"output": f"value-{i}"})

        # 最旧条目 cmd_0 被转储到持久化：读取前文件存在
        dumped_file = self.persist_dir / "cmd_0.json"
        self.assertTrue(dumped_file.exists(), "溢出条目应先转储为持久化文件")

        # get 从持久化读回，读取后文件被销毁
        result = self.cm.get("cmd_0")
        self.assertEqual(result["output"], "value-0")
        self.assertFalse(dumped_file.exists())


class TestCleanup(CommandCacheManagerTestBase):
    """cleanup_expired_persistent / clear_all。"""

    def test_cleanup_expired_only(self):
        self._write_persist_file("expired_1", expires_at=time.time() - 10)
        self._write_persist_file("fresh_1", expires_at=time.time() + 99999)
        cleaned = self.cm.cleanup_expired_persistent()
        self.assertEqual(cleaned, 1)
        self.assertFalse((self.persist_dir / "expired_1.json").exists())
        self.assertTrue((self.persist_dir / "fresh_1.json").exists())

    def test_cleanup_force_all(self):
        self._write_persist_file("expired_1", expires_at=time.time() - 10)
        self._write_persist_file("fresh_1", expires_at=time.time() + 99999)
        cleaned = self.cm.cleanup_expired_persistent(force_all=True)
        self.assertEqual(cleaned, 2)
        self.assertEqual(list(self.persist_dir.glob("*.json")), [])

    def test_clear_all(self):
        self.cm.add("cmd_1", {"output": "hello"})
        self._write_persist_file("persisted_1", expires_at=time.time() + 99999)
        self.cm.clear_all()
        self.assertEqual(self.cm._memory_cache, {})
        self.assertEqual(list(self.persist_dir.glob("*.json")), [])


class TestGetStats(CommandCacheManagerTestBase):
    """缓存统计信息。"""

    def test_stats_initial(self):
        stats = self.cm.get_stats()
        self.assertEqual(stats["memory_cache_count"], 0)
        self.assertEqual(stats["persist_cache_count"], 0)
        self.assertEqual(stats["ttl_seconds"], 3600)
        self.assertEqual(stats["persist_ttl_seconds"], 86400)
        self.assertEqual(stats["max_memory_cache_size"], 20)

    def test_stats_after_add(self):
        self.cm.add("cmd_1", {"output": "x"})
        self.assertEqual(self.cm.get_stats()["memory_cache_count"], 1)


class TestLazySingleton(unittest.TestCase):
    """get_command_cache_manager 惰性单例。"""

    def test_singleton_returns_same_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("modules.bootstrap.DATE_DIR", tmp):
                with patch.object(cache_mod, "_cache_manager", None):
                    first = get_command_cache_manager()
                    second = get_command_cache_manager()
                    self.assertIsNotNone(first)
                    self.assertIs(first, second)
                    self.assertIsInstance(first, CommandCacheManager)


if __name__ == "__main__":
    unittest.main()
