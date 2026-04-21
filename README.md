# Dolphin

Dolphin 是一个基于大语言模型的智能助手项目，通过技能（Skills）和插件（Plugins）系统扩展 AI 的能力，支持工具调用、对话管理和用户交互。

## 核心架构

Dolphin 采用模块化设计，核心组件包括：

### 模块层 (modules/)

| 模块 | 功能 |
|------|------|
| `chat.py` | 聊天核心，处理与 AI 模型的交互、工具调用和流式响应 |
| `skill_manager.py` | 管理内置技能系统，加载和调用技能 |
| `plugin_skill_loader.py` | 插件加载器，从 ZIP 文件加载插件技能 |
| `request_manager.py` | **申请中转中心**，统一处理技能/插件与主程序的用户交互请求 |
| `config.py` | 配置管理，保存和加载用户配置 |
| `commands.py` | 命令系统，管理命令行接口 |
| `logger.py` | 日志系统 |
| `backup_manager.py` | 文件备份管理 |
| `conversation.py` | 对话历史管理 |
| `mcp_manager.py` | MCP 协议管理器 |

### 技能系统 (skills/)

内置技能位于 `skills/` 目录，每个技能是一个子目录：

- **calculator** - 数学计算
- **file_reader** - 文件读取和搜索
- **file_manager** - 文件创建、修改、删除
- **powershell_executor** - PowerShell 脚本执行
- **random_generator** - 随机数生成
- **web_search** - 网络搜索

### 插件系统 (plugins/)

插件从 ZIP 文件加载，位于 `plugins/` 目录：

- **user_input_plugin** - 用户输入和确认插件

插件支持 `manifest.json` 配置文件，定义技能元数据和入口点。

## 申请中转系统

Dolphin 的核心特性是**申请中转系统**（Request Manager），它统一处理所有技能和插件与用户交互的请求。

### 申请类型

| 类型 | 用途 | 说明 |
|------|------|------|
| `USER_INPUT` | 用户输入申请 | 请求用户输入信息 |
| `CONFIRMATION` | 操作确认申请 | 请求用户确认操作 |
| `SKILL_CONFIRMATION` | 敏感操作确认 | 确认执行敏感操作 |
| `CONSOLE_OUTPUT` | 控制台输出 | 技能/插件输出信息到控制台 |

### 工作流程

```
技能/插件 ──创建申请──> RequestManager ──回调──> 主程序 ──用户交互──> 返回结果
                                    │
                                    └── 统一控制台输出 ──>
```

### 技术优势

1. **集中管理**：所有用户交互通过统一的请求管理器处理
2. **标准化接口**：技能和插件无需关心用户交互的具体实现
3. **多端兼容**：不同前端（命令行、Web）可统一处理申请
4. **可扩展性**：易于添加新的申请类型

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

首次运行时，程序会引导你配置：
- API 密钥
- 选择模型（deepseek-chat、deepseek-coder、deepseek-reasoner 等）
- 工作目录

### 运行

```bash
python main.py
```

## 命令行命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/set` | 进入设置模式 |
| `/clear` | 清空历史记录 |
| `/new` | 创建新对话 |
| `/load [name]` | 加载对话 |
| `/saveas [name]` | 保存对话 |
| `/list` | 列出所有对话 |
| `/tools` | 显示可用工具 |
| `/skills` | 显示可用技能 |
| `/toggle` | 切换工具启用状态 |
| `/skill` | 技能管理 |
| `/quit` | 退出程序 |

## 技能开发

### 创建新技能

在 `skills/` 目录下创建新文件夹，包含 `skill.py` 文件：

```python
skill_info = {
    "name": "my_skill",
    "description": "我的技能",
    "functions": {
        "do_something": {
            "description": "执行操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "参数1"}
                },
                "required": ["param1"]
            },
            "callable": do_something  # 函数引用
        }
    }
}
```

详细说明请参考 [skills/README.md](skills/README.md)

### 使用申请中转系统

```python
from modules import request_manager

rm = request_manager.get_request_manager()

# 创建用户输入申请
rm.create_user_input_request("请输入文件名:", "text")

# 创建操作确认申请
rm.create_confirmation_request("确认删除文件?")

# 创建敏感操作确认
rm.create_skill_confirmation("确认执行 PowerShell 脚本?", "run_script")

# 创建控制台输出
rm.create_console_output("操作完成", "info")
```

## 插件开发

### manifest.json 结构

```json
{
  "main": {
    "entry_point": "skill/skill.py"
  },
  "skill_info": {
    "name": "my_plugin",
    "version": "1.0.0",
    "description": "我的插件",
    "functions": {
      "custom_function": {
        "description": "自定义函数",
        "parameters": {}
      }
    }
  }
}
```

## 配置说明

配置文件为 `config.json`，包含以下选项：

- `api_key` - API 密钥
- `base_url` - API 地址
- `model` - 模型名称
- `max_tokens` - 最大 Token 数
- `work_directory` - 工作目录
- `skills` - 技能启用状态
- `plugins` - 插件启用状态

## 项目目的

本项目探索如何通过技能和插件系统扩展大语言模型的能力，使其能够完成更多实际任务，同时保持代码的模块化和可扩展性。

## 许可证

MIT License
