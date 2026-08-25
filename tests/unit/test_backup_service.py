"""backup_service 单元测试。

使用假的 BackupManager 验证服务层的转发行为：
查询待处理变更、应用与撤销全部变更。

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_backup_service -v
"""
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.core.services import backup_service


class FakeBackupManager:
    """替代 BackupManager 的假单例，记录调用并返回预设结果。"""

    def __init__(self):
        self.pending_count = 2
        self.pending_list = [
            {"action": "modify", "file": "a.py"},
            {"action": "create", "file": "b.py"},
        ]
        self.apply_result = {"success": True, "applied": 2}
        self.revert_result = {"success": True, "reverted": 2}
        self.apply_calls = 0
        self.revert_calls = 0

    def get_pending_changes_count(self):
        return self.pending_count

    def get_pending_changes_list(self):
        return self.pending_list

    def apply_all_changes(self):
        self.apply_calls += 1
        return self.apply_result

    def revert_all_changes(self):
        self.revert_calls += 1
        return self.revert_result


class TestBackupService(unittest.TestCase):
    """backup_service 对 BackupManager 的转发行为。"""

    def setUp(self):
        self.fake = FakeBackupManager()
        patcher = patch(
            "modules.core.services.backup_service.get_backup_manager",
            return_value=self.fake,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_pending_changes_returns_count_and_list(self):
        result = backup_service.get_pending_changes()
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["list"], self.fake.pending_list)

    def test_get_pending_changes_empty(self):
        self.fake.pending_count = 0
        self.fake.pending_list = []
        result = backup_service.get_pending_changes()
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["list"], [])

    def test_apply_all_changes_forwards_and_returns_result(self):
        result = backup_service.apply_all_changes()
        self.assertEqual(self.fake.apply_calls, 1)
        self.assertEqual(result, self.fake.apply_result)
        self.assertTrue(result["success"])

    def test_apply_all_changes_failure_propagates(self):
        self.fake.apply_result = {"success": False, "message": "会话上下文未设置"}
        result = backup_service.apply_all_changes()
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "会话上下文未设置")

    def test_revert_all_changes_forwards_and_returns_result(self):
        result = backup_service.revert_all_changes()
        self.assertEqual(self.fake.revert_calls, 1)
        self.assertEqual(result, self.fake.revert_result)
        self.assertTrue(result["success"])

    def test_revert_all_changes_failure_propagates(self):
        self.fake.revert_result = {"success": False, "message": "撤销失败"}
        result = backup_service.revert_all_changes()
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "撤销失败")


if __name__ == "__main__":
    unittest.main()
