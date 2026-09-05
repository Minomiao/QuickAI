"""backup_actions.backup_file 备份文件名毫秒精度单元测试。

验证备份文件名包含微秒时间戳（%Y%m%d_%H%M%S%f），
避免同一秒内重复备份相互覆盖。文件操作仅在临时目录内进行。

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_backup_actions -v
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.functions.backup_actions import (
    apply_all_changes,
    backup_file,
    get_pending_changes_count,
    record_change,
    revert_all_changes,
)

# 备份文件名：8 位日期 + 6 位时间 + 6 位微秒 + .bak
_BACKUP_NAME_PATTERN = re.compile(r"^\d{8}_\d{12}\.bak$")


class _BackupTestBase(unittest.TestCase):
    """公共基建：临时目录 + CONVERSATIONS_DIR 重定向。

    INITIAL_CONTENT 为 None 时文件初始不存在（族 1 场景），
    否则预写入该内容作为轮初基线（族 2 场景）。
    """

    INITIAL_CONTENT = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        patcher = patch("modules.functions.registry.CONVERSATIONS_DIR", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.work_dir = self.root / "work"
        self.work_dir.mkdir()
        self.source = self.work_dir / "target.txt"
        if self.INITIAL_CONTENT is not None:
            self.source.write_text(self.INITIAL_CONTENT, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _collect_backup_files(self):
        """收集临时根目录下所有 .bak 文件"""
        return [p for p in self.root.rglob("*.bak")]


class TestBackupFilenameMicroseconds(_BackupTestBase):
    """验证备份文件名含微秒精度时间戳。"""

    INITIAL_CONTENT = "hello"

    def test_backup_filename_has_microseconds(self):
        result = backup_file("target.txt", str(self.work_dir), "conv", "conv")
        self.assertIsNotNone(result)

        backup_files = self._collect_backup_files()
        self.assertEqual(len(backup_files), 1)
        self.assertRegex(backup_files[0].name, _BACKUP_NAME_PATTERN,
                         f"备份文件名应含微秒时间戳: {backup_files[0].name}")

    def test_create_action_skips_backup(self):
        result = backup_file("target.txt", str(self.work_dir), "conv", "conv", action="create")
        self.assertIsNone(result)
        self.assertEqual(self._collect_backup_files(), [])

    def test_nonexistent_file_skips_backup(self):
        result = backup_file("missing.txt", str(self.work_dir), "conv", "conv")
        self.assertIsNone(result)
        self.assertEqual(self._collect_backup_files(), [])


class TestPendingFoldStateChart(_BackupTestBase):
    """净操作折叠状态机：任意操作序列归约为单一净记录。

    模拟真实调用序：backup_file（改前快照）→ 文件变更 → record_change。
    dir_id 与 conv_id 同为 "conv"（与 dialog_id = conv_id 约定一致）。
    默认轮初文件不存在（族 1）；族 2 测试先调用 _make_present()。
    """

    def _make_present(self):
        """族 2 前置：轮初写入基线内容。"""
        self.source.write_text("hello", encoding="utf-8")

    # ---- 驱动与断言助手 ----

    def _op(self, action, new_content=None):
        """模拟一次工具操作：backup（改前）→ 文件变更 → record。"""
        backup_file("target.txt", str(self.work_dir), "conv", "conv", action=action)
        if action == "delete":
            self.source.unlink()
        else:
            self.source.write_text(new_content, encoding="utf-8")
        record_change(action, "target.txt", str(self.work_dir), "conv", "conv")

    def _registry_backups(self):
        from modules.functions.registry import _load_backup_registry
        return _load_backup_registry("conv", "conv")["backups"]

    def _single_record(self):
        """获取 target.txt 的唯一记录（折叠机制保证至多一条）。"""
        backups = self._registry_backups()
        self.assertEqual(len(backups), 1, f"应只有一个文件的记录: {list(backups)}")
        records = next(iter(backups.values()))["backup_files"]
        self.assertEqual(len(records), 1, f"应只有一条记录: {records}")
        return records[0]

    def _pending_count(self):
        return get_pending_changes_count("conv", "conv")

    # ---- 族 1：轮初不存在（快照永不需要，撤销 = 删文件） ----

    def test_create_delete_folds_to_canceled_ghost(self):
        """create→delete 净零：幽灵记录，不弹确认，无快照。"""
        self._op("create", "A")
        self._op("delete")

        record = self._single_record()
        self.assertTrue(record.get("canceled"))
        self.assertIsNone(record.get("backup_file"))
        self.assertEqual(self._pending_count(), 0)
        self.assertEqual(self._collect_backup_files(), [])

    def test_create_delete_modify_revives_as_create(self):
        """净零后再 modify：幽灵复活为 create（撤销 = 删文件，不建快照）。"""
        self._op("create", "A")
        self._op("delete")
        self._op("modify", "B")

        record = self._single_record()
        self.assertEqual(record.get("action"), "create")
        self.assertFalse(record.get("canceled", False))
        self.assertIsNone(record.get("backup_file"))
        self.assertEqual(self._pending_count(), 1)
        self.assertEqual(self._collect_backup_files(), [])

    def test_create_modify_delete_folds_to_canceled(self):
        """create→modify→delete 净零：中间修改不影响净结果。"""
        self._op("create", "A")
        self._op("modify", "B")
        self._op("delete")

        record = self._single_record()
        self.assertTrue(record.get("canceled"))
        self.assertEqual(self._pending_count(), 0)
        self.assertEqual(self._collect_backup_files(), [])

    def test_create_delete_oscillation_stays_single_record(self):
        """create/delete 振荡 n 次：始终单条记录，终态由奇偶性决定。"""
        self._op("create", "A")
        self._op("delete")
        self._op("create", "B")
        self._op("delete")
        self._op("create", "C")

        record = self._single_record()
        self.assertEqual(record.get("action"), "create")
        self.assertFalse(record.get("canceled", False))
        self.assertEqual(self._pending_count(), 1)

    def test_revert_skips_canceled_records(self):
        """净零后撤销：无文件动作，幽灵保留。"""
        self._op("create", "A")
        self._op("delete")

        result = revert_all_changes("conv", "conv")
        self.assertTrue(result["success"])
        self.assertEqual(result["reverted_count"], 0)
        self.assertFalse(self.source.exists())
        # 幽灵记录保留
        self.assertTrue(self._single_record().get("canceled"))

    def test_apply_skips_canceled_records(self):
        """净零后应用：applied_count 为 0。"""
        self._op("create", "A")
        self._op("delete")

        result = apply_all_changes("conv", "conv")
        self.assertTrue(result["success"])
        self.assertEqual(result["applied_count"], 0)

    def test_create_delete_modify_then_revert_deletes_file(self):
        """幽灵复活后撤销：文件应被删除（基线 = 轮初不存在）。"""
        self._op("create", "A")
        self._op("delete")
        self._op("modify", "B")

        result = revert_all_changes("conv", "conv")
        self.assertEqual(result["reverted_count"], 1)
        self.assertFalse(self.source.exists())

    # ---- 族 2：轮初存在（撤销基线恒为轮初快照） ----

    def test_modify_delete_create_folds_to_modify(self):
        """modify→delete→create 折叠为 modify，快照恒为轮初内容。"""
        self._make_present()
        self._op("modify", "A")
        self._op("delete")
        self._op("create", "B")

        record = self._single_record()
        self.assertEqual(record.get("action"), "modify")
        self.assertEqual(self._pending_count(), 1)
        # 快照内容 = 轮初 "hello"
        backup_path = Path(record["backup_file"])
        self.assertEqual(backup_path.read_text(encoding="utf-8"), "hello")
        # 只有一份快照（delete/create 复用，不新增）
        self.assertEqual(len(self._collect_backup_files()), 1)

    def test_modify_modify_keeps_single_record(self):
        """连续 modify：单条记录，快照保持轮初。"""
        self._make_present()
        self._op("modify", "A")
        self._op("modify", "B")

        record = self._single_record()
        self.assertEqual(record.get("action"), "modify")
        self.assertEqual(Path(record["backup_file"]).read_text(encoding="utf-8"), "hello")
        self.assertEqual(len(self._collect_backup_files()), 1)

    def test_delete_create_folds_to_modify(self):
        """delete→create 折叠为 modify：撤销恢复删除前内容。"""
        self._make_present()
        self._op("delete")
        self._op("create", "A")

        record = self._single_record()
        self.assertEqual(record.get("action"), "modify")
        self.assertEqual(self._pending_count(), 1)

    def test_revert_restores_initial_snapshot(self):
        """modify 后撤销：文件恢复轮初内容，快照与记录清理。"""
        self._make_present()
        self._op("modify", "A")
        backup_path = Path(self._single_record()["backup_file"])

        result = revert_all_changes("conv", "conv")
        self.assertEqual(result["reverted_count"], 1)
        self.assertEqual(self.source.read_text(encoding="utf-8"), "hello")
        self.assertFalse(backup_path.exists())
        # 记录已随撤销移除，文件条目整体清理
        backups = self._registry_backups()
        self.assertEqual(len(backups), 0)

    def test_revert_restores_deleted_file(self):
        """delete 后撤销：文件复活为轮初内容。"""
        self._make_present()
        self._op("delete")

        result = revert_all_changes("conv", "conv")
        self.assertEqual(result["reverted_count"], 1)
        self.assertEqual(self.source.read_text(encoding="utf-8"), "hello")


if __name__ == "__main__":
    unittest.main()
