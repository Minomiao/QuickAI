"""conversation_service 对话服务单元测试。

使用临时目录构造真实 .dpc 文件验证对话新建/加载/工作目录切换；
会话文件目录重定向到临时目录，不触碰真实会话数据。

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_conversation_service -v
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

from modules.chater import dpc_manager
from modules.core.services import conversation_service


class FakeChatInstance:
    """替代 DolphinChat 的假实例，记录关键调用。"""

    def __init__(self):
        self.messages = []
        self.calls = []
        self.skill_mgr = FakeSkillMgr()
        self.plugin_loader = FakeSkillMgr()

    def save_conversation(self, dir_id, conv_id):
        self.calls.append(("save", dir_id, conv_id))

    def clear_history(self):
        self.calls.append(("clear",))
        self.messages = []

    def set_save_target(self, dir_id, conv_id):
        self.calls.append(("target", dir_id, conv_id))

    def _update_tools(self):
        self.calls.append(("tools",))


class FakeSkillMgr:
    """替代技能管理器的假对象。"""

    def __init__(self):
        self.reload_calls = 0
        self.work_dirs = []

    def reload_skills(self):
        self.reload_calls += 1

    def set_work_dir(self, path):
        self.work_dirs.append(path)


class FakeLoader:
    """替代 conversation_loader 的假加载器。"""

    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def load_and_activate(self, chat_instance, dir_id, conv_id, conv_name, work_dir):
        self.calls.append((dir_id, conv_id, conv_name, work_dir))
        if not self.ok:
            return None
        return {"dir_id": dir_id, "conv_id": conv_id, "conv_name": conv_name}


class FakeConfigModule:
    """替代配置模块的假对象。"""

    def __init__(self):
        self.saved = []

    def save_config(self, config):
        self.saved.append(config)


class FakeCtx:
    """满足 conversation_service 上下文协议的假上下文。"""

    def __init__(self, work_dir, loader_ok=True):
        self.current_config = {"work_directory": work_dir}
        self.chat_instance = FakeChatInstance()
        self.config = FakeConfigModule()
        self.conversation_loader = FakeLoader(loader_ok)
        self.current_conversation = "main"
        self.current_dir_id = None
        self.current_conv_id = None


class ConversationServiceTestBase(unittest.TestCase):
    """公共环境：临时目录 + 会话文件目录重定向。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name)
        self.convs_dir = os.path.join(self.root, "conversations")
        os.makedirs(self.convs_dir)
        patcher = patch("modules.chater.conversation.CONVERSATIONS_DIR", self.convs_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _read_dpc(self, work_dir):
        with open(os.path.join(work_dir, ".dpc"), "r", encoding="utf-8") as f:
            return json.load(f)


class TestCreateConversation(ConversationServiceTestBase):
    """新建对话。"""

    def setUp(self):
        super().setUp()
        self.work_dir = os.path.join(self.root, "work")
        os.makedirs(self.work_dir)
        self.ctx = FakeCtx(self.work_dir)

    def test_create_registers_in_dpc_and_updates_ctx(self):
        result = conversation_service.create_conversation(self.ctx, "测试对话")
        self.assertTrue(result["success"])
        self.assertEqual(result["conv_name"], "测试对话")
        self.assertIsNotNone(result["dir_id"])
        self.assertIsNotNone(result["conv_id"])

        # .dpc 已登记且指向新对话
        data = self._read_dpc(self.work_dir)
        names = [c["name"] for c in data["conversations"]]
        self.assertIn("测试对话", names)
        self.assertEqual(data["current"], result["conv_id"])

        # 上下文与保存目标已更新
        self.assertEqual(self.ctx.current_conversation, "测试对话")
        self.assertEqual(self.ctx.current_conv_id, result["conv_id"])
        self.assertIn(("target", result["dir_id"], result["conv_id"]),
                      self.ctx.chat_instance.calls)

        # 会话文件已创建
        conv_file = os.path.join(self.convs_dir, result["dir_id"],
                                 result["conv_id"], f"{result['conv_id']}.json")
        self.assertTrue(os.path.exists(conv_file))

    def test_create_duplicate_rejected(self):
        conversation_service.create_conversation(self.ctx, "重复")
        result = conversation_service.create_conversation(self.ctx, "重复")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "duplicate")

    def test_existing_messages_saved_before_switch(self):
        self.ctx.chat_instance.messages = [{"role": "user", "content": "hi"}]
        self.ctx.current_dir_id = "old-dir"
        self.ctx.current_conv_id = "old-conv"
        conversation_service.create_conversation(self.ctx, "新对话")
        self.assertIn(("save", "old-dir", "old-conv"), self.ctx.chat_instance.calls)

    def test_empty_messages_not_saved(self):
        conversation_service.create_conversation(self.ctx, "无历史")
        saves = [c for c in self.ctx.chat_instance.calls if c[0] == "save"]
        self.assertEqual(saves, [])


class TestActivateConversation(ConversationServiceTestBase):
    """加载已有对话。"""

    def setUp(self):
        super().setUp()
        self.work_dir = os.path.join(self.root, "work")
        os.makedirs(self.work_dir)
        self.ctx = FakeCtx(self.work_dir)
        conversation_service.create_conversation(self.ctx, "历史对话")
        self.ctx.current_conversation = "main"
        self.ctx.current_dir_id = None
        self.ctx.current_conv_id = None

    def test_activate_by_name(self):
        result = conversation_service.activate_conversation(self.ctx, "历史对话")
        self.assertTrue(result["success"])
        self.assertEqual(result["conv_name"], "历史对话")
        self.assertEqual(self.ctx.current_conversation, "历史对话")
        self.assertIn(("target", result["dir_id"], result["conv_id"]),
                      self.ctx.chat_instance.calls)

    def test_activate_unknown_name(self):
        result = conversation_service.activate_conversation(self.ctx, "不存在")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "not_found")

    def test_activate_by_id(self):
        convs = dpc_manager.get_conversations(self.work_dir)
        target = convs[0]
        result = conversation_service.activate_conversation_by_id(
            self.ctx, target["id"], target["name"])
        self.assertTrue(result["success"])
        self.assertEqual(self.ctx.current_conv_id, target["id"])

    def test_activate_loader_failure(self):
        self.ctx.conversation_loader = FakeLoader(ok=False)
        result = conversation_service.activate_conversation(self.ctx, "历史对话")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "load_failed")


class TestOpenWorkDirectory(ConversationServiceTestBase):
    """打开/切换工作目录。"""

    def setUp(self):
        super().setUp()
        self.work_dir = os.path.join(self.root, "work")
        os.makedirs(self.work_dir)
        self.ctx = FakeCtx(self.work_dir)
        conversation_service.create_conversation(self.ctx, "已有对话")
        self.ctx.current_conversation = "main"
        self.ctx.current_dir_id = None
        self.ctx.current_conv_id = None

    def test_missing_dir_without_create_fails(self):
        result = conversation_service.open_work_directory(
            self.ctx, os.path.join(self.root, "nope"), create_if_missing=False)
        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "cancelled")

    def test_missing_dir_with_create_creates_and_inits(self):
        path = os.path.join(self.root, "fresh")
        result = conversation_service.open_work_directory(
            self.ctx, path, create_if_missing=True)
        self.assertTrue(result["success"])
        self.assertTrue(result["created_dir"])
        self.assertEqual(result["action"], "created")
        # 目录已创建
        self.assertTrue(os.path.isdir(path))
        # 以目录名新建了对话
        self.assertEqual(result["conv_name"], "fresh")
        self.assertEqual(self.ctx.current_conversation, "fresh")

    def test_same_dir_no_skill_reload(self):
        result = conversation_service.open_work_directory(self.ctx, self.work_dir)
        self.assertTrue(result["success"])
        self.assertFalse(result["skills_reloaded"])
        self.assertEqual(self.ctx.chat_instance.skill_mgr.reload_calls, 0)

    def test_changed_dir_reloads_skills_and_saves_config(self):
        other = os.path.join(self.root, "other")
        os.makedirs(other)
        result = conversation_service.open_work_directory(self.ctx, other)
        self.assertTrue(result["success"])
        self.assertTrue(result["skills_reloaded"])
        self.assertEqual(self.ctx.chat_instance.skill_mgr.reload_calls, 1)
        self.assertIn(other, self.ctx.chat_instance.skill_mgr.work_dirs)
        self.assertEqual(self.ctx.current_config["work_directory"], other)
        self.assertEqual(len(self.ctx.config.saved), 1)

    def test_current_conversation_loaded(self):
        result = conversation_service.open_work_directory(self.ctx, self.work_dir)
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "loaded")
        self.assertEqual(result["conv_name"], "已有对话")

    def test_existing_messages_saved_before_switch(self):
        self.ctx.chat_instance.messages = [{"role": "user", "content": "hi"}]
        self.ctx.current_dir_id = "old-dir"
        self.ctx.current_conv_id = "old-conv"
        other = os.path.join(self.root, "other")
        os.makedirs(other)
        conversation_service.open_work_directory(self.ctx, other)
        self.assertIn(("save", "old-dir", "old-conv"), self.ctx.chat_instance.calls)

    def test_duplicate_conv_name_gets_suffix(self):
        # fresh 目录存在同名对话时自动加后缀
        fresh = os.path.join(self.root, "fresh")
        os.makedirs(fresh)
        dpc_manager.add_conversation(fresh, "fresh")
        # current 指向不存在的对话，跳过加载分支走新建流程
        dpc_manager.set_current_by_id(fresh, "missing-conv-id")
        result = conversation_service.open_work_directory(
            self.ctx, fresh, create_if_missing=True)
        self.assertEqual(result["conv_name"], "fresh_1")


class TestResolveWorkDirectory(unittest.TestCase):
    """路径解析。"""

    def test_absolute_path_unchanged(self):
        self.assertEqual(
            conversation_service.resolve_work_directory("D:\\work"),
            "D:\\work")

    def test_relative_path_joined_with_project_root(self):
        resolved = conversation_service.resolve_work_directory("workplace")
        self.assertTrue(os.path.isabs(resolved))
        self.assertTrue(resolved.endswith("workplace"))


if __name__ == "__main__":
    unittest.main()
