"""命令服务层：从 UI 下沉的纯业务操作。

所有服务函数约定：
- 只操作传入的应用上下文（ctx，鸭子类型，各模块 docstring 定义协议，
  modules.CLIserver.state.AppState 即满足该协议）；
- 只返回结果字典（{success, ...} / {success, error}），不做任何界面渲染；
- 重模块（openai、chater 等）在函数体内延迟导入，保持启动懒加载。

UI 层负责解析结果并渲染，核心层与 UI 层由此解耦。
"""
from . import backup_service, chat_service, config_service, conversation_service
