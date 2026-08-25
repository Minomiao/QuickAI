"""chat_service.rebuild_chat_instance 单元测试。

使用假的 chat 模块与上下文对象验证重建行为：
消息保留、回调继承、思考深度与保存目标恢复。

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_chat_service -v
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.core.services import chat_service


class FakeChatInstance:
    """替代 DolphinChat 的假实例，记录关键调用。"""

    def __init__(self, model=None, max_tokens=None, callback=None):
        self.model = model
        self.max_tokens = max_tokens
        self.callback = callback
        self.messages = []
        self.effort_level = "fine"
        self.save_target = None

    def set_save_target(self, dir_id, conv_id):
        self.save_target = (dir_id, conv_id)


class FakeChatModule:
    """替代 modules.chater.chat 的假模块。"""

    def __init__(self):
        self.instances = []

    def DolphinChat(self, model=None, max_tokens=None, callback=None):
        instance = FakeChatInstance(model=model, max_tokens=max_tokens, callback=callback)
        self.instances.append(instance)
        return instance


class FakeCtx:
    """满足 chat_service 上下文协议的假上下文。"""

    def __init__(self, chat_module):
        self.chat_instance = None
        self.chat = chat_module
        self.current_config = {"model": "test-model", "max_tokens": 20000}
        self.effort_level = "high"
        self.current_dir_id = None
        self.current_conv_id = None


class TestRebuildChatInstance(unittest.TestCase):
    """重建对话实例的行为。"""

    def setUp(self):
        self.chat_module = FakeChatModule()
        self.ctx = FakeCtx(self.chat_module)

    def test_rebuild_creates_new_instance_with_config(self):
        result = chat_service.rebuild_chat_instance(self.ctx)
        self.assertTrue(result["success"])
        instance = self.chat_module.instances[0]
        self.assertIs(self.ctx.chat_instance, instance)
        self.assertEqual(instance.model, "test-model")
        self.assertEqual(instance.max_tokens, 20000)
        self.assertIs(result["instance"], instance)

    def test_rebuild_preserves_messages(self):
        old = FakeChatModule().DolphinChat()
        old.messages = [{"role": "user", "content": "hi"}]
        self.ctx.chat_instance = old
        chat_service.rebuild_chat_instance(self.ctx)
        self.assertEqual(self.ctx.chat_instance.messages, old.messages)

    def test_rebuild_inherits_callback_from_old_instance(self):
        def _cb(event_type, data):
            return None
        old = FakeChatModule().DolphinChat(callback=_cb)
        self.ctx.chat_instance = old
        chat_service.rebuild_chat_instance(self.ctx)
        self.assertIs(self.ctx.chat_instance.callback, _cb)

    def test_rebuild_explicit_callback_overrides(self):
        def _new_cb(event_type, data):
            return None
        old = FakeChatModule().DolphinChat(callback=lambda *a: None)
        self.ctx.chat_instance = old
        chat_service.rebuild_chat_instance(self.ctx, callback=_new_cb)
        self.assertIs(self.ctx.chat_instance.callback, _new_cb)

    def test_rebuild_applies_ctx_effort_level(self):
        self.ctx.effort_level = "normal"
        chat_service.rebuild_chat_instance(self.ctx)
        self.assertEqual(self.ctx.chat_instance.effort_level, "normal")

    def test_rebuild_restores_save_target(self):
        self.ctx.current_dir_id = "dir-1"
        self.ctx.current_conv_id = "conv-1"
        chat_service.rebuild_chat_instance(self.ctx)
        self.assertEqual(self.ctx.chat_instance.save_target, ("dir-1", "conv-1"))

    def test_rebuild_without_save_target(self):
        chat_service.rebuild_chat_instance(self.ctx)
        self.assertIsNone(self.ctx.chat_instance.save_target)


if __name__ == "__main__":
    unittest.main()
