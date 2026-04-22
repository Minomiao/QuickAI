# Change Log

## Requirements

+ Review the complete logic of `d:\codes\QuickAI\skills\powershell_executor\skill.py`
+ Check the main program's design for confirmation mechanism requests
+ Determine whether user confirmation is returned to AI or to skill
+ Modify confirmation operation to return value to skill instead of AI
+ Read and modify `d:\codes\QuickAI\skills\powershell_executor\skill.py` to handle confirmation operations through the main program
+ Continue with original logic after receiving confirmation
+ Commit changes
+ Push changes to remote repository
+ Create a new tag
+ Retry pushing tag if failed
+ Check modifications between current and previous tag
+ Create a document using + (add), - (delete), / (change) format
+ Add the document to .gitignore
+ Do not use hash mark headings except for tag records in the document
+ Record the document in English
+ Use + for additions, - for deletions, / for changes
+ Organize all requirements from previous context at the top of the change log in English

## v0.2.0-alpha (2026-04-22)

+ Implement request manager for skills and plugins
+ Add file operation module for centralized file operations
+ Implement prompt manager module for centralized system prompt management
+ Implement dialog-level backup management with single backup per file per conversation
/ Update file reader and file operation to use consistent line numbering
/ Improve work directory management: temporary switching, reset on new conversation, and clear subfolder usage instructions
+ Enhance request manager with console output support
/ Update README with architecture documentation and command reference
- Remove confirm_action function from user_input plugin
- Remove package_plugin.py build script
- Remove web-related files (main_server.py and Web-electron)
- Remove unused quickai_chat.py and quickai_client.py files

**modules/request_manager.py**:
  + Create new module for managing skill and plugin requests
  + Implement console output support
  + Provide centralized request handling

**modules/file_operation.py**:
  + Create new module for centralized file operations
  + Update skills to use request manager for file operations

**modules/prompt_manager.py**:
  + Create new module for centralized system prompt management

**modules/backup_manager.py**:
  + Implement dialog-level backup management
  + Support single backup per file per conversation

**skills/file_manager/skill.py**:
  / Update to use consistent line numbering
  / Improve work directory management

**plugins/user_input_plugin/**:
  - Remove confirm_action function

**README.md**:
  / Update with architecture documentation and command reference

/ Improve system architecture with centralized management modules
/ Enhance file operation consistency across skills
/ Simplify codebase by removing unused files
/ Improve work directory management and backup organization

## v0.1.4-alpha (2026-04-12)

+ Add async callback support for better web compatibility
/ Restrict work directory to subdirectories only
+ Add colorama library for terminal output coloring
/ Improve output readability with color coding
/ Modify main program to use async main function

**modules/chat.py**:
  + Implement async callback mechanism
  + Add _call_callback method to support both sync and async callbacks
  + Modify chat and chat_stream methods to async
  + Update tool execution to use async calls

**skills/file_manager/skill.py**:
  / Restrict work directory to subdirectories only
  / Default to relative path resolution
  + Add path format hints for AI
  / Remove confirmation requirement for directory changes

**main.py**:
  + Add colorama library integration
  + Implement async main function
  / Add color coding for different output types
  + Initialize colorama for cross-platform support

**requirements.txt**:
  + Add colorama>=0.4.6 dependency

/ Improve terminal output readability with color coding
/ Enhance web compatibility with async callbacks
/ Strengthen security by restricting work directory scope

## v0.1.3-alpha (2026-04-06)

+ Add plugin skill loader functionality
+ Create user input plugin for requesting user information
/ Modify main program to support plugin skills
+ Implement manifest.json based skill information loading
+ Add prompt directory and prompts.json for skill prompts

**modules/plugin_skill_loader.py**:
  + Create new module for loading plugin skills from ZIP files
  + Implement manifest.json parsing
  + Support skill information loading from manifest.json
  + Add error handling and logging

**modules/chat.py**:
  + Integrate plugin skill loader
  + Add plugin tools to available tools list
  + Support plugin skill calls

**main.py**:
  + Add plugin skill management
  + Support enabling/disabling plugin skills
  + Display plugin skills in skill list

**plugins/user_input_plugin/**:
  + Create user input plugin
  + Implement request_user_input function
  + Implement confirm_action function
  + Add manifest.json for skill information
  + Add prompt/prompts.json for skill prompts

/ Improve plugin architecture, separate skill info from code
+ Support plugin skill discovery and loading
/ Enhance system extensibility through plugins

## v0.1.2-alpha (2026-03-30)

/ Refactor PowerShell executor confirmation mechanism to use standard confirmation flow
+ Improve skill operation guide documentation, add backup manager usage instructions
/ Optimize main program confirmation handling logic, support confirmed parameter passing

**skills/powershell_executor/skill.py**:
  + Add `confirmed` parameter to support execution after confirmation
  / Return confirmation request on first call, execute script after confirmation
  - Remove direct print() and input() calls
  + Keep complete script content in logs

**modules/chat.py**:
  + Add confirmed parameter in all three confirmation handling locations
  + Re-call skill to execute actual operation after user confirmation
  / Optimize confirmation handling process

**skills/SKILL_OPERATION_GUIDE.md**:
  + Add backup manager usage guide
  + Provide detailed code examples and usage instructions
  + Expand document structure

/ Unify confirmation mechanism design, consistent with other skills
+ Support confirmation flow for web version
/ Avoid code duplication, improve maintainability
/ Improve logging, enhance system traceability

## v0.1.1-alpha

/ Fix parameter truncation issue, increase max_tokens setting
/ Improve error handling, provide clearer error messages
/ Increase tool call iteration limit

## v0.1.0-alpha

+ Initial version release
+ Implement basic chat functionality
+ Integrate PowerShell executor skill
+ Add file management functionality
+ Implement backup mechanism