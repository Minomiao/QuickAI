"""子智能体（subagent）：把自包含的子任务委派给独立的无头 AI 工作者。

主对话通过 skill_subagent_delegate 发起委派；每次委派创建全新的
DolphinChat 会话（独立消息历史、独立上下文），跑完即弃，与主对话互不污染。

设计约束：
- 子代理默认禁用全部工具（纯推理工作者）；use_tools=true 时仅放行
  文件类基础工具——subagent 自身不在白名单内，递归被物理切断
- 子代理看不到主对话任何内容，task 必须写成独立可执行的完整任务书
- 返回给主对话的结果经过裁剪：只带结论与工具轨迹摘要，不回灌全量消息
"""
from modules.logger import get_logger

log = get_logger("Dolphin.skill.subagent")

# 结果裁剪参数
_TOOL_RESULT_PREVIEW = 80
_CONCLUSION_MAX = 4000

skill_info = {
    "name": "subagent",
    "description": "Start a subagent when the user's request contains a self-contained "
                   "subtask that is better executed in an isolated AI session, such as "
                   "summarizing several files, exploring a directory, or drafting a "
                   "standalone section. Delegate a fully self-contained task and use its "
                   "conclusion; the subagent cannot see this conversation.",
    "functions": {
        "delegate": {
            "description": (
                "委派一个自包含的子任务给独立 AI 工作者并返回其最终结论。"
                "task 必须是完整任务书：要做什么、读哪些文件、输出什么格式——"
                "子代理看不到当前对话的任何内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "完整自包含的子任务描述（目标、输入、输出格式）",
                    },
                    "use_tools": {
                        "type": "boolean",
                        "description": "是否允许子代理使用文件类基础工具（file_manager/file_reader）",
                        "default": False,
                    },
                },
                "required": ["task"],
            },
        }
    },
}


def delegate(context, task: str, use_tools: bool = False) -> dict:
    """委派子任务给无头子代理，返回裁剪后的结论与工具轨迹摘要。"""
    from modules.functions.ai_caller import chat_ai_sync

    if not task or not task.strip():
        return {"error": "task 不能为空"}

    result = chat_ai_sync(
        prompt=task,
        enable_tools=bool(use_tools),
        # 白名单只含文件类工具：subagent 自身被物理排除，递归不可能发生
        allowed_tools=["file_manager", "file_reader"] if use_tools else None,
        work_directory=context.work_directory,
        max_tool_rounds=5,
    )

    conclusion = result.get("content", "")
    if len(conclusion) > _CONCLUSION_MAX:
        conclusion = conclusion[:_CONCLUSION_MAX] + f"…（已截断，共 {len(result['content'])} 字符）"

    return {
        "success": True,
        "conclusion": conclusion,
        "truncated": result.get("truncated", False),
        "tool_summary": [
            f"{tc.get('name', '?')}: {str(tc.get('result', ''))[:_TOOL_RESULT_PREVIEW]}"
            for tc in result.get("tool_calls", [])
        ],
        "user_output": {
            "label": "subagent",
            "parts": [{"text": task.strip().splitlines()[0][:60]}],
        },
    }
