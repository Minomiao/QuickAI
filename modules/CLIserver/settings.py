"""设置模式、模型设置和工具切换界面（业务操作委托 core.services）。"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from modules.logger import get_logger
from modules.bootstrap import constants
from modules.core.services import chat_service, config_service
from . import i18n
from .state import state
from .screen_refresh import create_header_panel

log = get_logger("Dolphin.settings")
_console = Console()


def settings_mode():
    """进入设置界面（上下键选择配置项）。"""
    cmd = state.cmd
    log.info("进入设置模式")

    def _run_token():
        """修改最大 Token 数。"""
        current_max_tokens = state.current_config.get('max_tokens', 18000)
        _console.print()
        _console.print(Panel(Text(i18n.t("settings.max_tokens_panel", current=current_max_tokens)), title=i18n.t("settings.max_tokens"), border_style="cyan"))
        new_value = input(i18n.t("settings.input_max_tokens")).strip()

        if not new_value:
            return

        try:
            new_max_tokens = int(new_value)
        except ValueError:
            _console.print(f"[red]{i18n.t('settings.invalid_number')}[/red]")
            input(i18n.t("main.press_enter"))
            return

        result = config_service.set_max_tokens(state, new_max_tokens)
        if result.get('success'):
            _console.print(f"[green]{i18n.t('settings.updated', value=new_max_tokens)}[/green]")
        elif result.get('error') == 'min':
            _console.print(f"[red]{i18n.t('settings.token_min')}[/red]")
        else:
            _console.print(f"[red]{i18n.t('settings.token_max')}[/red]")
        input(i18n.t("main.press_enter"))

    def _run_prefix():
        """修改命令前缀。"""
        current_prefix = state.current_config.get('command_prefix', '/')
        _console.print()
        _console.print(Panel(Text(i18n.t("settings.prefix_panel", prefix=current_prefix)), title=i18n.t("settings.command_prefix"), border_style="cyan"))
        new_prefix = input(i18n.t("settings.input_prefix")).strip()

        if not new_prefix:
            return

        result = config_service.set_command_prefix(state, new_prefix)
        if result.get('truncated'):
            _console.print(f"[yellow]{i18n.t('settings.prefix_truncated', prefix=result['value'])}[/yellow]")
        _console.print(f"[green]{i18n.t('settings.updated', value=result['value'])}[/green]")
        input(i18n.t("main.press_enter"))

    def _render():
        from .key_nav import navigate

        def _label(item, i):
            if item["key"] == "max_tokens":
                return f"{i18n.t('settings.max_tokens')}: {state.current_config.get('max_tokens', 18000)}"
            return f"{i18n.t('settings.command_prefix')}: {state.current_config.get('command_prefix', '/')}"

        def _on_enter(item, i):
            item["action"]()
            return False  # 完成后回到导航，可继续配置其他项

        items = [
            {"key": "max_tokens", "action": _run_token},
            {"key": "command_prefix", "action": _run_prefix},
        ]
        navigate(i18n.t("settings.title"), i18n.t("settings.subtitle"), items, _label, _on_enter,
                 f"{i18n.t('settings.enter_configure')} | {i18n.t('settings.esc_back')}")
        # 重建实例使 max_tokens 等配置生效
        chat_service.rebuild_chat_instance(state)
        print("客户端已更新")

    from .screen_refresh import enter_screen
    enter_screen(_render,
                 command_input=cmd.get_command('set'),
                 command_info=f"╰─{cmd.get_command_description('set')}")


def model_settings():
    """模型设置界面（上下键导航，k/a/d 为动作键）。"""
    cmd = state.cmd
    log.info("进入模型设置")

    from modules.main_server.config import get_available_models

    def _render():
        from .key_nav import navigate

        current_model = state.current_config.get('model', constants.DEFAULT_MODEL)
        available_models = get_available_models()

        def _label(model_info, i):
            name_display = model_info['name']
            if model_info.get("custom"):
                name_display = f"* {name_display}"
            desc = model_info.get('description', '')
            marker = "✓" if model_info['name'] == current_model else ""
            line = f"{name_display}  {desc}".rstrip()
            if marker:
                line += f"  {marker}"
            return line

        def _on_enter(model_info, i):
            result = config_service.switch_model(state, model_info)
            _console.print(f"[green]{i18n.t('model.switched', name=result['value'])}[/green]")
            print("客户端已更新")
            input(i18n.t("main.press_enter"))
            return True  # 切换完成后退出模型设置

        def _extra_key(key, model_info, i):
            if key == 'k':
                # 修改 API 密钥
                _console.print()
                new_api_key = input(i18n.t("model.input_api_key")).strip()
                if new_api_key:
                    config_service.set_api_key(state, new_api_key)
                    _console.print(f"[green]{i18n.t('model.api_key_updated')}[/green]")
                    print("客户端已更新")
                    input(i18n.t("main.press_enter"))
                return True
            if key == 'a':
                # 添加自定义模型
                _add_custom_model_flow()
                return True
            if key == 'd':
                # 删除自定义模型
                if not model_info.get("custom"):
                    _console.print(f"[red]{i18n.t('model.not_custom')}[/red]")
                    input(i18n.t("main.press_enter"))
                    return True
                _delete_custom_model_flow(model_info)
                return True
            return False

        api_key = state.current_config.get('api_key', '')
        footer = (f"{i18n.t('model.api_key_label')}{'***' + api_key[-4:] if len(api_key) > 4 else ('已设置' if api_key else '未设置')}"
                  f" | {i18n.t('model.hint')}")
        navigate(i18n.t("model.title"), i18n.t("model.current", name=current_model),
                 available_models, _label, _on_enter, footer,
                 extra_key=_extra_key)

    from .screen_refresh import enter_screen
    enter_screen(_render,
                 command_input=cmd.get_command('model'),
                 command_info=f"╰─{cmd.get_command_description('model')}")


def _add_custom_model_flow():
    """自定义模型添加流程。"""
    from modules.main_server.config import add_custom_model

    _console.print()
    _console.print(create_header_panel(i18n.t("model.add_title"), i18n.t("model.add_subtitle")))

    name = input(i18n.t("model.input_name")).strip()
    if not name:
        _console.print(f"[red]{i18n.t('model.name_required')}[/red]")
        input(i18n.t("main.press_enter"))
        return

    description = input(i18n.t("model.input_description")).strip()
    if not description:
        description = name

    base_url = input(i18n.t("model.input_base_url")).strip()
    if not base_url:
        _console.print(f"[red]{i18n.t('model.base_url_required')}[/red]")
        input(i18n.t("main.press_enter"))
        return

    api_key = input(i18n.t("model.api_key_label")).strip()
    if not api_key:
        _console.print(f"[red]{i18n.t('model.api_key_required')}[/red]")
        input(i18n.t("main.press_enter"))
        return

    context_str = input(i18n.t("model.input_context")).strip()
    context_window = 128000
    if context_str:
        try:
            context_window = int(context_str)
        except ValueError:
            _console.print(f"[yellow]{i18n.t('model.invalid_context')}[/yellow]")

    success, error = add_custom_model(name, description, base_url, api_key, context_window)
    if success:
        _console.print(f"[green]{i18n.t('model.added', name=name)}[/green]")
    else:
        _console.print(f"[red]{error}[/red]")
    input(i18n.t("main.press_enter"))


def _delete_custom_model_flow(model_info):
    """删除当前选中的自定义模型。"""
    name = model_info["name"]
    _console.print()
    _console.print(create_header_panel(i18n.t("model.delete_title"), i18n.t("model.delete_subtitle")))
    confirm = input(i18n.t("model.confirm_delete", name=name)).strip().lower()
    if confirm not in ('y', 'yes'):
        return

    result = config_service.remove_custom_model(state, name)
    if result.get('success'):
        _console.print(f"[green]{i18n.t('model.deleted', name=name)}[/green]")
    else:
        _console.print(f"[red]{result.get('error')}[/red]")
    input(i18n.t("main.press_enter"))


def effort_settings():
    """思考深度设置界面（上下键导航）。"""
    cmd = state.cmd
    log.info("进入思考深度设置")

    _LEVELS = [
        ("fine", i18n.t("effort.fine")),
        ("normal", i18n.t("effort.normal")),
        ("high", i18n.t("effort.high")),
    ]

    def _render():
        from .key_nav import navigate

        def _label(level, i):
            name, desc = level
            marker = "✓" if state.effort_level == name else ""
            line = f"{name} - {desc}"
            if marker:
                line += f"  {marker}"
            return line

        def _on_enter(level, i):
            name, _ = level
            result = config_service.set_effort_level(state, name)
            _console.print(f"[green]{i18n.t('main.effort_set', level=result['value'])}[/green]")
            input(i18n.t("main.press_enter"))
            return True  # 应用后退出

        navigate(i18n.t("effort.title"), i18n.t("effort.subtitle", level=state.effort_level),
                 _LEVELS, _label, _on_enter,
                 i18n.t("effort.hint"))

    from .screen_refresh import enter_screen
    enter_screen(_render,
                 command_input=cmd.get_command('effort'),
                 command_info=f"╰─{cmd.get_command_description('effort')}")


def toggle_tools():
    """切换工具启用/禁用状态。"""
    current_status = state.chat_instance.enable_tools
    new_status = not current_status
    state.chat_instance.enable_tool(new_status)
    status_text = i18n.t("tools.enabled") if new_status else i18n.t("tools.disabled")
    log.info(f"工具状态已切换: {status_text}")
    print(i18n.t("tools.toggled", status=status_text))
