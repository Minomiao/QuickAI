"""主命令循环：解析用户输入并分发到各子模块。"""
import sys

from colorama import Fore, Style

from modules.logger import get_logger
from . import i18n
from .state import ui, state
from .callback import chat_callback, clear_tool_pending, rollback_last_message
from .changes import handle_post_chat_changes
from .commands import get_command_keyword
from .header import print_header, print_conversation_history
from .settings import settings_mode, model_settings, toggle_tools, effort_settings
from .conversation_ops import (
    open_work_directory, new_conversation, load_conversation, select_conversation
)
from .display import show_help, show_tools, show_skills

log = get_logger("Dolphin.main_loop")

# 命令处理器返回值哨兵：主循环收到后退出
_QUIT = object()


def _pre_send_check():
    """发送消息前的必要检查。"""
    cmd = state.cmd
    missing = []
    if not state.current_config.get("api_key"):
        missing.append("API密钥")
    if not state.current_config.get("model"):
        missing.append("模型")
    return missing


def _parse_command(user_input: str, prefix: str):
    """解析命令输入为关键词与参数。

    Args:
        user_input: 用户原始输入（已 strip）
        prefix: 命令前缀

    Returns:
        (keyword, args) 元组；非命令输入返回 None。
    """
    if not user_input.startswith(prefix):
        return None
    raw = user_input[len(prefix):].strip()
    parts = raw.split(maxsplit=1)
    keyword = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return keyword, args


def _cmd_help(_args):
    """显示帮助信息。"""
    show_help()


def _cmd_clear(_args):
    """清空对话历史。"""
    state.chat_instance.clear_history()
    state.screen_refresh.refresh(
        print_header, print_conversation_history,
        i18n.t("main.history_cleared"), show_history=False
    )


def _cmd_model(_args):
    """进入模型设置。"""
    model_settings()


def _cmd_set(_args):
    """进入设置模式。"""
    settings_mode()


def _cmd_open(args):
    """打开工作目录。"""
    open_work_directory(args or None)


def _cmd_new(args):
    """开启新对话。"""
    new_conversation(args)


def _cmd_list(_args):
    """查看所有对话。"""
    select_conversation()


def _cmd_load(args):
    """加载旧对话。"""
    load_conversation(args)


def _cmd_back(_args):
    """返回（在设置模式中使用），无需额外操作。"""
    pass


def _cmd_quit(_args):
    """退出程序。"""
    log.info("用户退出程序")
    print(i18n.t("main.goodbye"))
    return _QUIT


def _cmd_tools(_args):
    """查看可用工具。"""
    show_tools()


def _cmd_skills(_args):
    """查看可用技能。"""
    show_skills()


def _cmd_changes(_args):
    """查看待处理变更。"""
    from .changes import handle_pending_changes
    handle_pending_changes()


def _cmd_showthinking(args):
    """查看或切换思考过程显示。"""
    if not args:
        status = i18n.t("main.on") if state.show_thinking else i18n.t("main.off")
        print(i18n.t("main.thinking_current", status=status))
        return
    arg = args.lower()
    if arg not in ('on', 'off'):
        print(i18n.t("main.invalid_arg", arg=arg))
        return
    target = (arg == 'on')
    if state.show_thinking == target:
        status = i18n.t("main.on") if state.show_thinking else i18n.t("main.off")
        print(i18n.t("main.thinking_already", status=status))
        return
    state.show_thinking = target
    state.current_config['show_thinking'] = target
    state.config.save_config(state.current_config)
    status = i18n.t("main.on") if state.show_thinking else i18n.t("main.off")
    state.screen_refresh.refresh(
        print_header, print_conversation_history,
        i18n.t("main.thinking_set", status=status)
    )


def _cmd_effort(args):
    """设置或选择思考强度。"""
    if not args:
        # 无参数时进入上下键选择界面
        effort_settings()
        return
    level = args.lower()
    if level in ['normal', 'fine', 'high']:
        state.effort_level = level
        state.chat_instance.effort_level = level
        state.current_config['effort_level'] = level
        state.config.save_config(state.current_config)
        print(i18n.t("main.effort_set", level=level))
    else:
        print(i18n.t("main.effort_invalid"))


def _cmd_toggle(_args):
    """切换工具启用状态。"""
    toggle_tools()


def _cmd_language(_args):
    """进入语言设置。"""
    from .language import language_settings
    language_settings()


# 命令分派表：keyword（由 get_command_keyword 动态获取）→ 处理器
_COMMAND_TABLE = {
    get_command_keyword("help"): _cmd_help,
    get_command_keyword("clear"): _cmd_clear,
    get_command_keyword("model"): _cmd_model,
    get_command_keyword("set"): _cmd_set,
    get_command_keyword("open"): _cmd_open,
    get_command_keyword("new"): _cmd_new,
    get_command_keyword("list"): _cmd_list,
    get_command_keyword("load"): _cmd_load,
    get_command_keyword("back"): _cmd_back,
    get_command_keyword("quit"): _cmd_quit,
    get_command_keyword("tools"): _cmd_tools,
    get_command_keyword("skills"): _cmd_skills,
    get_command_keyword("changes"): _cmd_changes,
    get_command_keyword("showthinking"): _cmd_showthinking,
    get_command_keyword("effort"): _cmd_effort,
    get_command_keyword("toggle"): _cmd_toggle,
    get_command_keyword("language"): _cmd_language,
}


async def main():
    """主命令循环。"""
    while True:
        try:
            ui.turn_first_output = True
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            current_prefix = state.current_config.get('command_prefix', '/')
            parsed = _parse_command(user_input, current_prefix)
            if parsed is not None:
                keyword, args = parsed
                handler = _COMMAND_TABLE.get(keyword)
                if handler is None:
                    print(i18n.t("main.unknown_command", keyword=keyword))
                    continue
                if handler(args) is _QUIT:
                    break
                continue

            # 发送消息前检查
            missing = _pre_send_check()
            if missing:
                missing_text = i18n.t("main.list_separator").join(missing)
                print(f"{Fore.RED}{i18n.t('main.missing_config', missing=missing_text, command=state.cmd.get_command('model'))}{Style.RESET_ALL}")
                log.warning(f"发送消息前检查失败: 缺少{missing_text}")
                continue

            try:
                await state.chat_instance.chat_stream(user_input)
                handle_post_chat_changes()
            except (state.AuthenticationError, state.RateLimitError,
                    state.APIConnectionError, state.APIError) as e:
                print(f"\n{Fore.RED}{i18n.t('main.api_error', error=e)}{Style.RESET_ALL}")
                log.error(f"API 错误: {e}", exc_info=True)
                rollback_last_message()
                clear_tool_pending()
            except Exception as e:
                print(f"\n{Fore.RED}{i18n.t('main.error', error=e)}{Style.RESET_ALL}")
                log.error(f"聊天错误: {e}", exc_info=True)
                clear_tool_pending()

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}{i18n.t('main.interrupted')}{Style.RESET_ALL}")
            clear_tool_pending()
            try:
                input(i18n.t("main.press_enter"))
            except (EOFError, KeyboardInterrupt):
                print(f"\n{i18n.t('main.goodbye')}")
                break
        except EOFError:
            print(f"\n{i18n.t('main.goodbye')}")
            break
        except Exception as e:
            print(f"{Fore.RED}{i18n.t('main.error', error=e)}{Style.RESET_ALL}")
            log.error(f"主循环错误: {e}", exc_info=True)
