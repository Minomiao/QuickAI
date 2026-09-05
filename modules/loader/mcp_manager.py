import asyncio
import re
import traceback
from typing import Dict, List, Any, Optional
from mcp.client.session import ClientSession
from modules.logger import get_logger
from modules.bootstrap import constants

log = get_logger("Dolphin.mcp_manager")

# 工具注册名只允许 OpenAI function calling 的合法字符
_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


class MCPManager:
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        # 注册名（mcp_ 前缀，加载时确定）→ (server_name, 原始工具名)
        self._tool_map: Dict[str, tuple] = {}
        # 注册名 → {description, input_schema}
        self._tool_info: Dict[str, Dict[str, Any]] = {}
        log.debug("初始化 MCPManager")

    def register_server_tools(self, server_name: str, tools: List[Dict[str, Any]]):
        """将会话建立后发现的 MCP 工具注册为统一 mcp_ 前缀的注册名。

        注册名在加载时确定并存入映射表，调用时零歧义查表；
        外部工具名中的非法字符（OpenAI 工具名仅允许字母数字与 _-）替换为下划线，
        注册名冲突在注册时报错。

        Args:
            server_name: MCP 服务器名
            tools: list_tools 返回的工具描述列表 [{name, description, input_schema}]
        """
        for tool in tools:
            raw_name = tool.get("name", "")
            registered = _SAFE_NAME_RE.sub("_", f"mcp_{server_name}_{raw_name}")
            if registered in self._tool_map:
                raise ValueError(f"MCP 工具注册名冲突: {registered}")
            self._tool_map[registered] = (server_name, raw_name)
            self._tool_info[registered] = {
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema") or {
                    "type": "object", "properties": {}, "required": []
                },
            }
        log.info(f"MCP 服务器 {server_name} 注册 {len(tools)} 个工具")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        log.info(f"调用 MCP 工具: {tool_name}, 参数: {arguments}")
        mapped = self._tool_map.get(tool_name)
        if mapped is None:
            log.error(f"未注册的 MCP 工具: {tool_name}")
            raise ValueError(f"未注册的 MCP 工具: {tool_name}")

        server_name, actual_tool_name = mapped
        if server_name not in self.sessions:
            log.error(f"MCP 服务器 {server_name} 未连接")
            raise ValueError(f"MCP 服务器 {server_name} 未连接")

        session = self.sessions[server_name]
        try:
            result = await asyncio.wait_for(
                session.call_tool(actual_tool_name, arguments),
                timeout=constants.MCP_TIMEOUT)
        except asyncio.TimeoutError:
            log.error(f"MCP 工具 {tool_name} 执行超时 ({constants.MCP_TIMEOUT}s)")
            return {"error": f"MCP 工具执行超时 ({constants.MCP_TIMEOUT}s)"}
        except Exception as e:
            log.error(f"MCP 工具 {tool_name} 执行失败: {e}\n{traceback.format_exc()}")
            return {"error": "MCP 工具执行过程中发生内部错误"}

        log.debug(f"MCP 工具执行结果: {result}")

        return result

    def get_all_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_info["description"],
                    "parameters": tool_info["input_schema"]
                }
            }
            for tool_name, tool_info in self._tool_info.items()
        ]

    def get_tool_names(self) -> List[str]:
        return list(self._tool_map.keys())


_mcp_manager = None


def get_mcp_manager() -> MCPManager:
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager
