import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import json

BACKUP_DIR = "date/backup"
PENDING_CHANGES_FILE = "date/pending_changes.json"

_pending_changes: List[Dict[str, Any]] = []

def get_backup_dir() -> Path:
    backup_path = Path(BACKUP_DIR)
    if not backup_path.exists():
        backup_path.mkdir(parents=True, exist_ok=True)
    return backup_path

def get_pending_changes_file() -> Path:
    return Path(PENDING_CHANGES_FILE)

def load_pending_changes() -> List[Dict[str, Any]]:
    global _pending_changes
    try:
        pending_file = get_pending_changes_file()
        if pending_file.exists():
            with open(pending_file, 'r', encoding='utf-8') as f:
                _pending_changes = json.load(f)
        else:
            _pending_changes = []
    except Exception:
        _pending_changes = []
    return _pending_changes

def save_pending_changes():
    try:
        pending_file = get_pending_changes_file()
        pending_file.parent.mkdir(parents=True, exist_ok=True)
        with open(pending_file, 'w', encoding='utf-8') as f:
            json.dump(_pending_changes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存待确认更改失败: {e}")

def backup_file(file_path: str, work_dir: str) -> Optional[str]:
    try:
        full_path = Path(work_dir) / file_path
        if not full_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.replace('/', '_').replace('\\', '_')}_{timestamp}.bak"
        backup_path = get_backup_dir() / backup_name
        
        shutil.copy2(full_path, backup_path)
        return str(backup_path)
    except Exception as e:
        print(f"备份文件失败: {e}")
        return None

def record_change(
    action: str,
    file_path: str,
    backup_path: Optional[str] = None,
    original_content: Optional[str] = None,
    new_content: Optional[str] = None,
    work_dir: str = ""
) -> Dict[str, Any]:
    global _pending_changes
    
    # 检查是否已有该文件的未确认更改
    existing_change = None
    for change in _pending_changes:
        if not change.get("confirmed", False) and change["file_path"] == file_path:
            existing_change = change
            break
    
    if existing_change:
        # 更新现有记录
        existing_change["action"] = action
        existing_change["backup_path"] = backup_path
        existing_change["timestamp"] = datetime.now().isoformat()
        save_pending_changes()
        return existing_change
    else:
        # 创建新记录
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "file_path": file_path,
            "backup_path": backup_path,
            "work_dir": work_dir,
            "applied": False,
            "confirmed": False
        }
        
        _pending_changes.append(change_record)
        save_pending_changes()
        
        return change_record

def get_pending_changes_count() -> int:
    return len([c for c in _pending_changes if not c.get("confirmed", False)])

def get_pending_changes_list() -> List[Dict[str, Any]]:
    return [c for c in _pending_changes if not c.get("confirmed", False)]

def apply_all_changes() -> Dict[str, Any]:
    global _pending_changes
    
    results = []
    for change in _pending_changes:
        if not change.get("confirmed", False):
            change["confirmed"] = True
            change["applied"] = True
            results.append({
                "file": change["file_path"],
                "action": change["action"],
                "status": "applied"
            })
    
    save_pending_changes()
    
    return {
        "success": True,
        "applied_count": len(results),
        "changes": results,
        "message": f"已应用 {len(results)} 个更改"
    }

def revert_all_changes() -> Dict[str, Any]:
    global _pending_changes
    
    results = []
    reverted_count = 0
    
    for change in reversed(_pending_changes):
        if not change.get("confirmed", False):
            backup_path = change.get("backup_path")
            file_path = change["file_path"]
            work_dir = change.get("work_dir", "workplace")
            action = change.get("action", "")
            full_path = Path(work_dir) / file_path
            
            try:
                if action == "create":
                    # 创建操作：删除文件
                    if full_path.exists():
                        full_path.unlink()
                        results.append({
                            "file": file_path,
                            "action": "create",
                            "status": "reverted (deleted)"
                        })
                        reverted_count += 1
                    else:
                        results.append({
                            "file": file_path,
                            "action": "create",
                            "status": "file not found"
                        })
                elif action == "modify":
                    # 修改操作：从备份恢复
                    if backup_path and Path(backup_path).exists():
                        shutil.copy2(backup_path, full_path)
                        Path(backup_path).unlink()
                        results.append({
                            "file": file_path,
                            "action": "modify",
                            "status": "reverted (restored from backup)"
                        })
                        reverted_count += 1
                    else:
                        results.append({
                            "file": file_path,
                            "action": "modify",
                            "status": "backup not found"
                        })
                elif action == "delete":
                    # 删除操作：从备份恢复
                    if backup_path and Path(backup_path).exists():
                        shutil.copy2(backup_path, full_path)
                        Path(backup_path).unlink()
                        results.append({
                            "file": file_path,
                            "action": "delete",
                            "status": "reverted (restored from backup)"
                        })
                        reverted_count += 1
                    else:
                        results.append({
                            "file": file_path,
                            "action": "delete",
                            "status": "backup not found"
                        })
            except Exception as e:
                results.append({
                    "file": file_path,
                    "action": action,
                    "status": "failed",
                    "error": str(e)
                })
    
    _pending_changes = [c for c in _pending_changes if c.get("confirmed", False)]
    save_pending_changes()
    
    return {
        "success": True,
        "reverted_count": reverted_count,
        "changes": results,
        "message": f"已撤销 {reverted_count} 个更改"
    }

def clear_confirmed_changes():
    global _pending_changes
    _pending_changes = [c for c in _pending_changes if not c.get("confirmed", False)]
    save_pending_changes()

def show_pending_changes() -> str:
    pending = get_pending_changes_list()
    if not pending:
        return "没有待确认的更改"
    
    lines = ["=== 待确认的更改 ==="]
    for i, change in enumerate(pending, 1):
        action_map = {
            "create": "创建",
            "modify": "修改",
            "delete": "删除"
        }
        action_text = action_map.get(change["action"], change["action"])
        lines.append(f"{i}. [{action_text}] {change['file_path']}")
        lines.append(f"   时间: {change['timestamp']}")
        if change.get("backup_path"):
            lines.append(f"   备份: {change['backup_path']}")
    
    return "\n".join(lines)

load_pending_changes()
