"""stdskill_helper.install_skill 安装行为单元测试。

验证合集/单技能两种来源的安装布局：
- 多技能合集保留层级安装为 stdskills/<合集名>/<技能名>/（对齐 pack 聚合）
- 单技能来源扁平安装为 stdskills/<技能名>/
- 脚手架目录跳过、重名跳过、重名安装报错
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from skills.stdskill_helper import skill as helper


_SKILL_MD = "---\nname: {name}\ndescription: {desc}\n---\n{body}"


class _ContextStub:
    """install_skill 所需的最小 context（日志直落打印，记录热重载调用）。"""

    def __init__(self):
        self.reload_calls = 0

    def reload_standard_skills(self):
        self.reload_calls += 1
        return {"success": True}

    def log_info(self, msg):
        print(msg)

    def log_warning(self, msg):
        print(msg)


class TestInstallSkill(unittest.TestCase):
    """install_skill 的合集/单技能安装布局。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.std_dir = self.root / "stdskills"
        self.ctx = _ContextStub()
        patcher = patch(helper.__name__ + "._stdskills_dir", return_value=self.std_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_skill(self, base: Path, rel: str, name: str, desc: str = "", body: str = "正文"):
        folder = base / rel
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            _SKILL_MD.format(name=name, desc=desc, body=body), encoding="utf-8")
        return folder

    def test_collection_installs_under_pack_folder(self):
        """多技能合集保留层级：stdskills/<合集名>/<技能名>/。"""
        src = self.root / "taste-skill-main" / "skills"
        self._write_skill(src, "alpha", "alpha", "A")
        self._write_skill(src, "beta", "beta", "B")
        ctx = _ContextStub()

        result = helper.install_skill(ctx, str(src))

        self.assertTrue(result["success"])
        self.assertEqual(result["installed"], ["alpha", "beta"])
        self.assertEqual(result["pack"], "taste-skill")
        self.assertTrue(result["reloaded"])
        self.assertEqual(ctx.reload_calls, 1)
        self.assertIn("下一轮对话", result["note"])
        self.assertTrue((self.std_dir / "taste-skill" / "alpha" / "SKILL.md").exists())
        self.assertTrue((self.std_dir / "taste-skill" / "beta" / "SKILL.md").exists())

    def test_pack_name_strips_download_suffix(self):
        """pack 名去除 GitHub 下载包的 -main 后缀；来源为 skills/ 时取仓库根名。"""
        src = self.root / "some-repo-main" / "skills"
        self._write_skill(src, "s1", "s1", "S1")
        self._write_skill(src, "s2", "s2", "S2")

        result = helper.install_skill(self.ctx, str(src))
        self.assertEqual(result["pack"], "some-repo")

    def test_single_skill_installs_flat(self):
        """单技能来源扁平安装：stdskills/<技能名>/。"""
        src = self.root / "one-skill"
        self._write_skill(src, ".", "solo", "独立")

        result = helper.install_skill(self.ctx, str(src))

        self.assertTrue(result["success"])
        self.assertEqual(result["installed"], ["solo"])
        self.assertIsNone(result["pack"])
        self.assertTrue((self.std_dir / "solo" / "SKILL.md").exists())

    def test_scaffold_dirs_skipped(self):
        """脚手架目录（.github 等）中的定义文件被跳过。"""
        src = self.root / "repo"
        self._write_skill(src, "real", "real", "R")
        self._write_skill(src, ".github/ghost", "ghost", "G")

        result = helper.install_skill(self.ctx, str(src))

        self.assertEqual(result["installed"], ["real"])
        self.assertFalse((self.std_dir / "ghost").exists())

    def test_duplicate_name_skipped(self):
        """重名技能跳过；二进制重复安装也跳过。"""
        src = self.root / "coll"
        self._write_skill(src, "dup", "dup", "D1")
        helper.install_skill(self.ctx, str(src))

        # 二次安装同名：existing 捕获 → skipped，且不会作为合集新建
        src2 = self.root / "coll2"
        self._write_skill(src2, "dup", "dup", "D2")
        self._write_skill(src2, "fresh", "fresh", "F")
        result = helper.install_skill(self.ctx, str(src2))

        self.assertEqual(result["skipped"], ["dup"])
        self.assertEqual(result["installed"], ["fresh"])

    def test_existing_pack_target_rejected(self):
        """合集目标目录已存在且非空：报错拒绝覆盖。"""
        src = self.root / "pack-src"
        self._write_skill(src, "p1", "p1", "P1")
        self._write_skill(src, "p2", "p2", "P2")
        helper.install_skill(self.ctx, str(src))

        src2 = self.root / "pack-src2"
        self._write_skill(src2, "q1", "q1", "Q1")
        self._write_skill(src2, "q2", "q2", "Q2")
        (self.std_dir / "pack-src2").mkdir()
        (self.std_dir / "pack-src2" / "occupied.txt").write_text("x", encoding="utf-8")

        result = helper.install_skill(self.ctx, str(src2))
        self.assertFalse(result["success"])
        self.assertIn("已存在且非空", result["error"])


if __name__ == "__main__":
    unittest.main()
