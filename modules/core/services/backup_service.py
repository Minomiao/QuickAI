"""备份服务：待处理文件变更的查询与批处理。

无上下文依赖，直接使用 BackupManager 单例。
"""
import time

from modules.functions.backup_manager import get_backup_manager
from modules.logger import get_logger

log = get_logger("Dolphin.backup_service")


def get_pending_changes():
    """查询待确认的文件变更。

    Returns:
        {count, list}：数量与变更列表
    """
    bm = get_backup_manager()
    return {
        "count": bm.get_pending_changes_count(),
        "list": bm.get_pending_changes_list(),
    }


def apply_all_changes():
    """应用全部待处理变更。

    Returns:
        BackupManager.apply_all_changes 的结果字典
    """
    bm = get_backup_manager()
    start = time.perf_counter()
    result = bm.apply_all_changes()
    elapsed = time.perf_counter() - start
    log.info(f"应用更改完成: 耗时={elapsed:.3f}s, 成功={result.get('success', False)}")
    return result


def revert_all_changes():
    """撤销全部待处理变更。

    Returns:
        BackupManager.revert_all_changes 的结果字典
    """
    bm = get_backup_manager()
    start = time.perf_counter()
    result = bm.revert_all_changes()
    elapsed = time.perf_counter() - start
    log.info(f"撤销更改完成: 耗时={elapsed:.3f}s, 成功={result.get('success', False)}")
    return result
