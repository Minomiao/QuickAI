"""核心层：UI 无关的业务逻辑与协议。

包含：
- events: UI 事件协议（事件常量、数据契约与交互事件约定）
- services: 命令服务层（配置/对话/实例重建/备份等纯业务操作）

UI 层（modules.CLIserver 及未来的 GUI 实现）只依赖本包；
核心层不反向依赖任何 UI 模块。
"""


class GenerationCancelled(Exception):
    """用户主动中断本轮生成。

    由 UI 层调用 DolphinChat.request_cancel() 触发，
    核心层在检查点抛出；UI 层捕获后执行回滚与收尾。
    """

