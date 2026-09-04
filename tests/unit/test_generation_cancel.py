"""后端协作式取消协议单元测试。

覆盖 DolphinChat 的 request_cancel / _check_cancelled / _process_stream
检查点与异常归一化、_run_tool_calls 的工具取消归一化。

使用 __new__ 绕过构造函数（避免 OpenAI 客户端等重依赖），
仅注入取消机制所需的最小属性。

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_generation_cancel -v
"""
import os
import sys
import asyncio
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.core import GenerationCancelled
from modules.chater.chat import DolphinChat


def _bare_chat() -> DolphinChat:
    """构造仅含取消机制状态的 DolphinChat（绕过 __init__ 重依赖）。"""
    chat = DolphinChat.__new__(DolphinChat)
    chat._cancel_requested = False
    chat._current_stream = None
    chat._current_tool_task = None
    return chat


class FakeStream:
    """模拟 openai 流式响应：同步迭代器，可被 close 中断。"""

    def __init__(self, chunks=None, raise_on_iter=None):
        self.chunks = list(chunks or [])
        self.raise_on_iter = raise_on_iter  # 迭代到该值时抛出的异常
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.raise_on_iter is not None:
            raise self.raise_on_iter
        if not self.chunks:
            raise StopIteration
        return self.chunks.pop(0)

    def close(self):
        self.closed = True


class FakeChunk:
    """最小 chunk 形状：无 usage、无 choices。"""

    usage = None
    choices = []


class TestRequestCancel(unittest.TestCase):
    """request_cancel 的三个立即动作。"""

    def test_sets_flag(self):
        chat = _bare_chat()
        chat.request_cancel()
        self.assertTrue(chat._cancel_requested)

    def test_closes_current_stream(self):
        chat = _bare_chat()
        stream = FakeStream()
        chat._current_stream = stream
        chat.request_cancel()
        self.assertTrue(stream.closed)

    def test_cancels_running_tool_task(self):
        async def _run():
            await asyncio.sleep(10)

        async def _scenario():
            chat = _bare_chat()
            task = asyncio.ensure_future(_run())
            chat._current_tool_task = task
            chat.request_cancel()
            await asyncio.sleep(0)  # 让事件循环注入取消
            self.assertTrue(task.cancelled())
            task.cancel()  # 兜底清理

        asyncio.run(_scenario())

    def test_noop_when_no_stream_or_task(self):
        chat = _bare_chat()  # 均为 None，不应抛异常
        chat.request_cancel()


class TestCheckCancelled(unittest.TestCase):
    """检查点行为。"""

    def test_raises_when_requested(self):
        chat = _bare_chat()
        chat._cancel_requested = True
        with self.assertRaises(GenerationCancelled):
            chat._check_cancelled()

    def test_passes_when_not_requested(self):
        chat = _bare_chat()
        chat._check_cancelled()  # 不抛即通过


class TestProcessStreamCheckpoints(unittest.IsolatedAsyncioTestCase):
    """流式循环中的取消检查点与异常归一化。"""

    async def test_checkpoint_between_chunks(self):
        """取消请求后不再消费后续 chunk。"""
        chat = _bare_chat()
        stream = FakeStream(chunks=[FakeChunk(), FakeChunk()])
        chat.request_cancel()  # 首个 chunk 前已请求取消
        with self.assertRaises(GenerationCancelled):
            await chat._process_stream(stream)

    async def test_close_induced_error_normalized(self):
        """关流导致的读异常归一化为 GenerationCancelled。"""
        chat = _bare_chat()
        chat._current_stream = FakeStream()
        chat.request_cancel()
        stream = FakeStream(raise_on_iter=RuntimeError("connection closed"))
        with self.assertRaises(GenerationCancelled):
            await chat._process_stream(stream)

    async def test_ordinary_error_not_normalized(self):
        """未请求取消时的普通异常保持原样传播。"""
        chat = _bare_chat()
        stream = FakeStream(raise_on_iter=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            await chat._process_stream(stream)


class TestRunToolCallsCancellation(unittest.IsolatedAsyncioTestCase):
    """工具批执行的取消归一化。"""

    async def test_cancelled_tool_task_raises_generation_cancelled(self):
        """工具任务被取消后转为 GenerationCancelled。"""
        chat = _bare_chat()
        chat.messages = []
        chat._cancel_requested = True

        async def _tool_executor(name, args):
            await asyncio.sleep(10)

        chat._execute_tool = _tool_executor
        chat._process_tool_confirmation = lambda *a: (None, False, None)
        chat._save_now = lambda: None
        chat._call_callback = lambda *a: None

        tool_calls = [{"id": "t1", "function": {"name": "demo_tool", "arguments": "{}"}}]
        # 模拟 request_cancel 已发生：检查点应在工具启动前引爆
        with self.assertRaises(GenerationCancelled):
            await chat._run_tool_calls(tool_calls)


class TestSealInterruptedTurn(unittest.IsolatedAsyncioTestCase):
    """中断封口：保留已完成消息，仅补全未闭环结构。"""

    def _chat_with(self, messages, save_dir=None, conv=None):
        chat = _bare_chat()
        chat.messages = messages
        chat._save_dir_id = save_dir
        chat._save_conv_id = conv
        return chat

    async def test_closes_pending_tool_calls(self):
        """未闭环的 tool_calls 补空 tool 结果。"""
        chat = self._chat_with([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "t1", "function": {"name": "a", "arguments": "{}"}},
                {"id": "t2", "function": {"name": "b", "arguments": "{}"}},
            ]},
        ])
        with patch.object(chat, "_recover_stream_buffer", side_effect=lambda m, d, c: m), \
                patch.object(chat, "_clear_stream_buffer") as fake_clear:
            chat.seal_interrupted_turn()

        tool_msgs = [m for m in chat.messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 2)
        self.assertEqual({m["tool_call_id"] for m in tool_msgs}, {"t1", "t2"})
        for m in tool_msgs:
            self.assertEqual(m["content"], "")
        fake_clear.assert_called_once()

    async def test_keeps_existing_tool_results(self):
        """已闭环的结构不重复补全。"""
        chat = self._chat_with([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "t1", "function": {"name": "a", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "t1", "content": "ok"},
        ])
        with patch.object(chat, "_recover_stream_buffer", side_effect=lambda m, d, c: m), \
                patch.object(chat, "_clear_stream_buffer"):
            chat.seal_interrupted_turn()

        tool_msgs = [m for m in chat.messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertEqual(tool_msgs[0]["content"], "ok")

    async def test_no_tool_calls_noop(self):
        """无 tool_calls 时不补任何消息。"""
        chat = self._chat_with([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "partial answer"},
        ])
        with patch.object(chat, "_recover_stream_buffer", side_effect=lambda m, d, c: m), \
                patch.object(chat, "_clear_stream_buffer"):
            chat.seal_interrupted_turn()

        self.assertEqual(len(chat.messages), 2)

    async def test_recovers_stream_buffer_as_partial_assistant(self):
        """流缓冲半截内容恢复为 partial assistant 消息。"""
        chat = self._chat_with([{"role": "user", "content": "hi"}],
                               save_dir="d1", conv="c1")

        def fake_recover(messages, dir_id, conv_id):
            messages.append({"role": "assistant", "content": "半截回复"})
            return messages

        saved = []
        with patch.object(chat, "_recover_stream_buffer", side_effect=fake_recover), \
                patch.object(chat, "_clear_stream_buffer"), \
                patch("modules.chater.conversation.save_conversation",
                      side_effect=lambda m, d, c: saved.append(list(m))):
            chat.seal_interrupted_turn()

        self.assertEqual(len(chat.messages), 2)
        self.assertEqual(chat.messages[-1]["content"], "半截回复")
        self.assertEqual(saved, [chat.messages])

    async def test_without_save_target_still_closes_structure(self):
        """无保存目标时仅补全内存结构，不落盘。"""
        chat = self._chat_with([
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "t1", "function": {"name": "a", "arguments": "{}"}},
            ]},
        ])
        with patch.object(chat, "_recover_stream_buffer", side_effect=lambda m, d, c: m) as fake_recover, \
                patch.object(chat, "_clear_stream_buffer") as fake_clear:
            chat.seal_interrupted_turn()

        self.assertEqual(len(chat.messages), 2)
        fake_recover.assert_not_called()
        fake_clear.assert_called_once()


if __name__ == "__main__":
    unittest.main()
