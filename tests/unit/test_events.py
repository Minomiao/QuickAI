"""modules.core.events 事件协议单元测试。

验证事件常量与集合的一致性、数据契约校验逻辑，
防止事件协议被误删或改名破坏核心层/UI 层契约。

运行方式（在项目根目录执行）：
    venv\\Scripts\\python.exe -m unittest tests.unit.test_events -v
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

from modules.bootstrap import constants
from modules.core import events


class TestEventConstants(unittest.TestCase):
    """事件常量与集合一致性。"""

    def test_all_events_covers_defined_constants(self):
        # 模块内所有 EVENT_ 字符串常量都必须注册进 ALL_EVENTS
        defined = {v for k, v in vars(events).items()
                   if k.startswith("EVENT_") and isinstance(v, str)}
        self.assertEqual(defined, set(events.ALL_EVENTS),
                         "ALL_EVENTS 与模块内 EVENT_ 常量不一致")

    def test_event_names_nonempty(self):
        for event in events.ALL_EVENTS:
            self.assertTrue(event, f"事件名不能为空: {event!r}")

    def test_max_iterations_matches_bootstrap(self):
        # 迭代上限事件沿用 bootstrap 常量，避免双源头漂移
        self.assertEqual(events.EVENT_MAX_ITERATIONS_REACHED,
                         constants.EVENT_MAX_ITERATIONS_REACHED)

    def test_interactive_events_subset(self):
        self.assertLessEqual(events.INTERACTIVE_EVENTS, events.ALL_EVENTS)

    def test_data_fields_keys_known_events(self):
        self.assertLessEqual(set(events.EVENT_DATA_FIELDS), events.ALL_EVENTS,
                             "EVENT_DATA_FIELDS 中存在未注册事件")

    def test_streaming_events_have_fields(self):
        # 增量内容类事件必须声明必填字段
        for event in (events.EVENT_THINKING, events.EVENT_THINKING_CHUNK,
                      events.EVENT_RESPONSE_CHUNK):
            self.assertTrue(events.EVENT_DATA_FIELDS[event],
                           f"{event} 应有必填字段")


class TestValidateEvent(unittest.TestCase):
    """validate_event 数据契约校验。"""

    def test_valid_events_pass(self):
        cases = {
            events.EVENT_THINKING: {"content": "思考内容"},
            events.EVENT_THINKING_START: {},
            events.EVENT_THINKING_END: {},
            events.EVENT_RESPONSE_CHUNK: {"content": "回复内容"},
            events.EVENT_RESPONSE_END: {},
            events.EVENT_TOOL_START: {"name": "read_file"},
            events.EVENT_TOOL_CALLS: {"calls": [{"name": "read_file", "arguments": "{}"}]},
            events.EVENT_TOOL_RESULT: {"raw": "raw", "formatted": None},
            events.EVENT_USER_OUTPUT: {"parts": [{"text": "x"}]},
            events.EVENT_OPERATION_CANCELED: {},
            events.EVENT_OPERATION_CONFIRMED: {},
            events.EVENT_CONSOLE_OUTPUT: {"content": "信息", "level": "info"},
            events.EVENT_CONTEXT_USAGE: {"usage_ratio": 0.5, "level": "warn"},
            events.EVENT_USER_INPUT_REQUIRED: {"prompt": "请输入"},
            events.EVENT_CONFIRMATION_REQUIRED: {"action": "删除文件"},
            events.EVENT_MAX_ITERATIONS_REACHED: {"iterations": 5, "hard_limit": 100},
        }
        for event_type, data in cases.items():
            ok, missing = events.validate_event(event_type, data)
            self.assertTrue(ok, f"{event_type} 应通过校验, 缺失字段: {missing}")

    def test_missing_fields_reported(self):
        ok, missing = events.validate_event(events.EVENT_TOOL_START, {})
        self.assertFalse(ok)
        self.assertIn("name", missing)

    def test_partial_missing_fields(self):
        ok, missing = events.validate_event(
            events.EVENT_MAX_ITERATIONS_REACHED, {"iterations": 3})
        self.assertFalse(ok)
        self.assertIn("hard_limit", missing)

    def test_unknown_event_rejected(self):
        ok, _ = events.validate_event("no_such_event", {})
        self.assertFalse(ok)

    def test_none_data_for_fieldless_event(self):
        # 无必填字段的事件允许 data 为 None
        ok, _ = events.validate_event(events.EVENT_OPERATION_CANCELED, None)
        self.assertTrue(ok)

    def test_none_data_for_fielded_event(self):
        ok, missing = events.validate_event(events.EVENT_TOOL_START, None)
        self.assertFalse(ok)
        self.assertIn("name", missing)


if __name__ == "__main__":
    unittest.main()
