"""web_search skill 成功返回结构测试。

验证 search/fetch 成功路径返回统一 success: True 与规范 parts 格式 user_output。
网络请求全部 mock，不触网。
"""
import importlib.util
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from modules.bootstrap import init as bootstrap_init

bootstrap_init(PROJECT_ROOT)

_SKILL_PATH = os.path.join(PROJECT_ROOT, "skills", "web_search", "skill.py")
_spec = importlib.util.spec_from_file_location("skills.web_search.skill", _SKILL_PATH)
web_search = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(web_search)

_CTX = SimpleNamespace(constants=SimpleNamespace(
    WEB_SEARCH_DEFAULT_RESULTS=5,
    MAX_WEB_CONTENT_LENGTH=2000,
))


def _fake_resp(html):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.text = html
    return resp


class TestSearchSuccess(unittest.TestCase):
    """search 成功路径返回 success: True 与 parts 格式 user_output。"""

    def test_no_results_success(self):
        with patch.object(web_search, "_parse_bing_results", return_value=[]), \
                patch.object(web_search.requests, "get", return_value=_fake_resp("<html></html>")):
            result = web_search.search(_CTX, "python")
        self.assertTrue(result["success"])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["user_output"]["label"], "Search")
        self.assertIn("parts", result["user_output"])

    def test_with_results_success(self):
        raw = [{"title": "T", "content": "C", "url": "https://example.com"}]
        with patch.object(web_search, "_parse_bing_results", return_value=raw), \
                patch.object(web_search.requests, "get", return_value=_fake_resp("<html></html>")):
            result = web_search.search(_CTX, "python")
        self.assertTrue(result["success"])
        self.assertEqual(result["results"], raw)
        self.assertIn("parts", result["user_output"])


class TestFetchSuccess(unittest.TestCase):
    """fetch 成功路径返回 success: True 与 parts 格式 user_output。"""

    def test_fetch_success(self):
        html = "<html><head><title>示例</title></head><body><p>内容</p></body></html>"
        with patch.object(web_search.requests, "get", return_value=_fake_resp(html)):
            result = web_search.fetch(_CTX, "https://example.com")
        self.assertTrue(result["success"])
        self.assertEqual(result["title"], "示例")
        self.assertIn("parts", result["user_output"])


if __name__ == "__main__":
    unittest.main()
