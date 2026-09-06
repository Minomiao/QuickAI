"""standard_skill_loader 单元测试。

覆盖：
- call_tool 返回的 user_output 规范 parts 格式
- pack 聚合模型：合集仓库合并为单工具（skill 枚举参数），根目录单技能独立
"""
import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.loader.standard_skill_loader import StandardSkillLoader


_SKILL_MD = "---\nname: {name}\ndescription: {desc}\n---\n{body}"


def _write_skill(std_dir: Path, rel_folder: str, name: str, desc: str, body: str):
    """在标准技能目录下写入一个 SKILL.md 定义。"""
    folder = std_dir / rel_folder
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(_SKILL_MD.format(name=name, desc=desc, body=body),
                                      encoding="utf-8")


class TestStandardSkillUserOutput(unittest.TestCase):
    """call_tool 返回的 user_output 应为规范的 parts 格式。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.loader = StandardSkillLoader(skills_dir=self._tmp.name)
        self.loader.skills = {"demo": {"body": "正文", "folder": "folder"}}
        self.loader._build_packs()
        self.loader._rebuild_tool_lookup()

    def tearDown(self):
        self._tmp.cleanup()

    def test_call_tool_user_output_uses_parts(self):
        result = asyncio.run(self.loader.call_tool("stdskill_demo", {}))
        self.assertTrue(result["success"])
        self.assertEqual(result["user_output"]["label"], "skills")
        self.assertEqual(result["user_output"]["parts"], [{"text": "demo"}])
        self.assertNotIn("content", result["user_output"])


class TestStandardSkillPacks(unittest.TestCase):
    """pack 聚合模型：合集合并为单工具，根目录单技能独立。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        std_dir = Path(self._tmp.name) / "stdskills"
        _write_skill(std_dir, "pack/a", "a", "A 技能", "A 正文")
        _write_skill(std_dir, "pack/b", "b", "B 技能", "B 正文")
        _write_skill(std_dir, "solo", "solo", "独立技能", "SOLO 正文")

        self.loader = StandardSkillLoader(skills_dir=str(std_dir))

        # 隔离配置读写（get_all_tools / toggle 读取，toggle 写入）
        self._config_state = {"stdskills": {}}
        patcher_load = patch("modules.main_server.config.load_config",
                             return_value=self._config_state)
        patcher_save = patch("modules.main_server.config.save_config",
                             side_effect=lambda cfg: self._config_state.update(cfg))
        patcher_load.start()
        patcher_save.start()
        self.addCleanup(patcher_load.stop)
        self.addCleanup(patcher_save.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def test_pack_aggregation(self):
        """合集成员聚合为一个 pack，根目录单技能独立。"""
        self.assertEqual(set(self.loader.skills), {"a", "b", "solo"})
        self.assertEqual(self.loader.packs["pack"],
                         {"members": ["a", "b"], "kind": "pack"})
        self.assertEqual(self.loader.packs["solo"],
                         {"members": ["solo"], "kind": "single"})
        self.assertEqual(set(self.loader._tool_lookup),
                         {"stdskill_pack", "stdskill_solo"})

    def test_get_all_tools_pack_schema(self):
        """合集工具携带 skill 枚举参数，单技能工具无参数。"""
        tools = {t["function"]["name"]: t["function"] for t in self.loader.get_all_tools()}

        self.assertEqual(set(tools), {"stdskill_pack", "stdskill_solo"})
        pack_params = tools["stdskill_pack"]["parameters"]
        self.assertEqual(pack_params["required"], ["skill"])
        self.assertEqual(pack_params["properties"]["skill"]["enum"], ["a", "b"])
        self.assertIn("A 技能", tools["stdskill_pack"]["description"])
        self.assertEqual(tools["stdskill_solo"]["parameters"]["required"], [])

    async def test_call_tool_pack_selects_member(self):
        """pack 工具按 skill 参数返回对应子技能正文。"""
        result = await self.loader.call_tool("stdskill_pack", {"skill": "a"})
        self.assertTrue(result["success"])
        self.assertEqual(result["instructions"], "A 正文")
        self.assertEqual(result["skill"], "pack/a")
        self.assertEqual(result["user_output"]["parts"], [{"text": "pack/a"}])

    async def test_call_tool_pack_missing_skill(self):
        """pack 调用缺参：结构化错误 + 可选列表。"""
        result = await self.loader.call_tool("stdskill_pack", {})
        self.assertIn("error", result)
        self.assertEqual(result["available"], ["a", "b"])

    async def test_call_tool_pack_unknown_skill(self):
        """pack 调用未知子技能：结构化错误 + 可选列表。"""
        result = await self.loader.call_tool("stdskill_pack", {"skill": "zzz"})
        self.assertIn("error", result)
        self.assertEqual(result["available"], ["a", "b"])

    async def test_call_tool_single_unchanged(self):
        """单技能工具调用行为不变。"""
        result = await self.loader.call_tool("stdskill_solo", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["instructions"], "SOLO 正文")
        self.assertEqual(result["skill"], "solo")

    def test_toggle_pack_group_level(self):
        """合集启停为组级：禁用后整个工具不再暴露。"""
        result = self.loader.toggle_skill("stdskill-pack", False)
        self.assertTrue(result["success"])
        self.assertEqual(self._config_state["stdskills"]["pack"], False)

        names = {t["function"]["name"] for t in self.loader.get_all_tools()}
        self.assertEqual(names, {"stdskill_solo"})

    def test_toggle_single(self):
        """单技能启停键为技能名。"""
        result = self.loader.toggle_skill("stdskill-solo", False)
        self.assertTrue(result["success"])
        self.assertEqual(self._config_state["stdskills"]["solo"], False)

        names = {t["function"]["name"] for t in self.loader.get_all_tools()}
        self.assertEqual(names, {"stdskill_pack"})

    def test_list_skills_reflects_packs(self):
        """list_skills 输出 pack 条目，functions 为成员列表。"""
        entries = {s["name"]: s for s in self.loader.list_skills()}
        self.assertEqual(set(entries), {"stdskill-pack", "stdskill-solo"})
        self.assertEqual(entries["stdskill-pack"]["functions"], ["a", "b"])
        self.assertTrue(entries["stdskill-pack"]["enabled"])


class TestHotReload(unittest.TestCase):
    """原子热重载：拾取新增技能、失败保留旧状态。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.std_dir = Path(self._tmp.name) / "stdskills"
        self.loader = StandardSkillLoader(skills_dir=str(self.std_dir))
        self._config_state = {"stdskills": {}}
        patcher_load = patch("modules.main_server.config.load_config",
                             return_value=self._config_state)
        patcher_load.start()
        self.addCleanup(patcher_load.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reload_picks_up_new_skill(self):
        """安装后 reload：新技能进入 packs 与查表（热加载链路）。"""
        self.assertEqual(self.loader.packs, {})  # 初始为空

        _write_skill(self.std_dir, "late", "late", "后装技能", "LATE 正文")
        result = self.loader.reload_skills()

        self.assertTrue(result["success"])
        self.assertEqual(result["loaded_count"], 1)
        self.assertIn("stdskill_late", self.loader._tool_lookup)
        names = {t["function"]["name"] for t in self.loader.get_all_tools()}
        self.assertEqual(names, {"stdskill_late"})

    def test_reload_picks_up_new_collection(self):
        """安装合集后 reload：聚合为一个 pack 工具。"""
        _write_skill(self.std_dir, "newpack/x", "x", "X 技能", "X")
        _write_skill(self.std_dir, "newpack/y", "y", "Y 技能", "Y")
        self.loader.reload_skills()

        self.assertEqual(self.loader.packs["newpack"]["members"], ["x", "y"])
        tools = {t["function"]["name"] for t in self.loader.get_all_tools()}
        self.assertEqual(tools, {"stdskill_newpack"})

    def test_reload_failure_keeps_old_state(self):
        """扫描抛异常：返回失败且现有技能原样保留。"""
        _write_skill(self.std_dir, "keep", "keep", "保留", "K")
        self.loader.reload_skills()
        snapshot = dict(self.loader.skills)
        lookup_snapshot = dict(self.loader._tool_lookup)

        with patch.object(self.loader, "_scan_into", side_effect=OSError("disk gone")):
            result = self.loader.reload_skills()

        self.assertFalse(result["success"])
        self.assertEqual(self.loader.skills, snapshot)
        self.assertEqual(self.loader._tool_lookup, lookup_snapshot)
        # 旧工具仍然暴露
        names = {t["function"]["name"] for t in self.loader.get_all_tools()}
        self.assertEqual(names, {"stdskill_keep"})

    def test_reload_removes_deleted_skill(self):
        """reload 同步删除：磁盘上移除的技能从查表与工具中消失。"""
        _write_skill(self.std_dir, "gone", "gone", "将被删除", "G")
        self.loader.reload_skills()
        self.assertIn("stdskill_gone", self.loader._tool_lookup)

        shutil.rmtree(self.std_dir / "gone")
        self.loader.reload_skills()

        self.assertNotIn("gone", self.loader.skills)
        self.assertNotIn("stdskill_gone", self.loader._tool_lookup)


if __name__ == "__main__":
    unittest.main()
