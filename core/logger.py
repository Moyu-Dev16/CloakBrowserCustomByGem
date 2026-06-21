"""
双通道日志管理器
- GUI通道: 简洁格式 [HH:MM:SS] [级别] 消息, 通过回调推送
- 文件通道: 完整格式含堆栈, 保存到 logs/task_YYYYMMDD_HHMMSS.log
"""
import logging
import os
import glob
import traceback
from datetime import datetime
from pathlib import Path

# 默认日志目录: 项目根目录下的 logs/
_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs'
)


class TaskLogger:
    """
    双通道日志管理器。

    - GUI通道: 通过回调函数推送简洁格式的日志消息
    - 文件通道: 写入详细格式的日志到文件（含堆栈信息）

    使用方式:
        logger = TaskLogger(gui_callback=my_callback)
        logger.start_session()
        logger.info("任务开始")
        logger.stop_session()
    """

    # 自定义日志级别：SUCCESS (介于 INFO 和 WARNING 之间)
    SUCCESS_LEVEL = 25
    logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")

    def __init__(self, log_dir: str = None, gui_callback=None):
        """
        初始化日志管理器。

        Args:
            log_dir: 日志文件存放目录，默认为项目根目录下的 logs/
            gui_callback: GUI回调函数，签名为 callback(level: str, message: str)
        """
        self.log_dir = log_dir or _DEFAULT_LOG_DIR
        self._gui_callback = gui_callback
        self._file_handler: logging.FileHandler = None
        self._logger = logging.getLogger(f"TaskLogger_{id(self)}")
        self._logger.setLevel(logging.DEBUG)
        # 防止日志向上传播到root logger
        self._logger.propagate = False
        self._current_log_file: str = None

    def start_session(self) -> str:
        """
        创建新的日志会话。

        每次调用会创建一个新的日志文件: logs/task_YYYYMMDD_HHMMSS.log
        并设置对应的 FileHandler。

        Returns:
            当前会话的日志文件路径
        """
        # 确保日志目录存在
        os.makedirs(self.log_dir, exist_ok=True)

        # 关闭之前的会话（如果有）
        self.stop_session()

        # 生成日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"task_{timestamp}.log"
        self._current_log_file = os.path.join(self.log_dir, log_filename)

        # 创建文件处理器，使用完整格式（含时间、级别、模块、行号）
        self._file_handler = logging.FileHandler(
            self._current_log_file, encoding='utf-8'
        )
        self._file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self._file_handler.setFormatter(file_formatter)
        self._logger.addHandler(self._file_handler)

        self.info(f"日志会话已启动: {log_filename}")
        return self._current_log_file

    def stop_session(self):
        """关闭当前的文件处理器，结束日志会话。"""
        if self._file_handler:
            self.info("日志会话已关闭")
            self._file_handler.close()
            self._logger.removeHandler(self._file_handler)
            self._file_handler = None
            self._current_log_file = None

    def _emit(self, level: int, level_name: str, msg: str, exc_info=None):
        """
        内部日志发射方法。

        同时向文件通道和GUI通道推送日志。
        - 文件通道: 写入完整信息（含堆栈）
        - GUI通道: 只推送简洁消息（不含堆栈）

        Args:
            level: 日志级别数值
            level_name: 日志级别名称（用于GUI显示）
            msg: 日志消息
            exc_info: 异常信息（仅写入文件，不推送到GUI）
        """
        # 文件通道：写入完整日志（含堆栈信息）
        if exc_info:
            self._logger.log(level, msg, exc_info=exc_info)
        else:
            self._logger.log(level, msg)

        # GUI通道：推送简洁消息（不含堆栈、不含时间戳/级别前缀）
        # LogPanel.append_log 会自行添加时间戳和级别标签
        if self._gui_callback:
            try:
                self._gui_callback(level_name, msg)
            except Exception as e:
                # GUI回调异常不应影响主流程，但记录到文件以便排查
                import sys
                print(f"[TaskLogger] GUI回调异常: {type(e).__name__}: {e}", file=sys.stderr)

    def info(self, msg: str):
        """记录 INFO 级别日志。"""
        self._emit(logging.INFO, "INFO", msg)

    def warning(self, msg: str):
        """记录 WARNING 级别日志。"""
        self._emit(logging.WARNING, "WARNING", msg)

    def error(self, msg: str, exc_info=None):
        """
        记录 ERROR 级别日志。

        Args:
            msg: 错误消息
            exc_info: 异常信息，可以是 True（自动捕获当前异常）或异常元组
        """
        self._emit(logging.ERROR, "ERROR", msg, exc_info=exc_info)

    def success(self, msg: str):
        """
        记录 SUCCESS 级别日志。

        自定义级别，介于 INFO 和 WARNING 之间。
        在GUI上显示为 SUCCESS 标签，文件中记录为 SUCCESS 级别。
        """
        self._emit(self.SUCCESS_LEVEL, "SUCCESS", msg)

    def set_gui_callback(self, callback):
        """
        设置或更新 GUI 回调函数。

        Args:
            callback: 回调函数，签名为 callback(level: str, message: str)
                      传入 None 可取消回调
        """
        self._gui_callback = callback

    # ---- 静态工具方法：日志文件管理 ----

    @staticmethod
    def get_log_files(log_dir: str = None) -> list:
        """
        获取所有日志文件的信息列表。

        Args:
            log_dir: 日志目录路径，默认为项目的 logs/ 目录

        Returns:
            包含日志文件信息的字典列表，每个字典包含:
            - name: 文件名
            - path: 完整路径
            - size_bytes: 文件大小（字节）
            - date: 文件修改时间 (datetime)
        """
        log_dir = log_dir or _DEFAULT_LOG_DIR
        if not os.path.isdir(log_dir):
            return []

        log_files = []
        pattern = os.path.join(log_dir, "*.log")
        for filepath in glob.glob(pattern):
            try:
                stat = os.stat(filepath)
                log_files.append({
                    'name': os.path.basename(filepath),
                    'path': filepath,
                    'size_bytes': stat.st_size,
                    'date': datetime.fromtimestamp(stat.st_mtime),
                })
            except OSError:
                # 文件可能在遍历期间被删除，跳过
                continue

        # 按日期倒序排列（最新的在前）
        log_files.sort(key=lambda x: x['date'], reverse=True)
        return log_files

    @staticmethod
    def clear_all_logs(log_dir: str = None) -> tuple:
        """
        删除所有日志文件。

        Args:
            log_dir: 日志目录路径，默认为项目的 logs/ 目录

        Returns:
            (deleted_count, total_bytes_freed): 删除的文件数和释放的字节数
        """
        log_dir = log_dir or _DEFAULT_LOG_DIR
        if not os.path.isdir(log_dir):
            return (0, 0)

        deleted_count = 0
        total_bytes_freed = 0
        pattern = os.path.join(log_dir, "*.log")

        for filepath in glob.glob(pattern):
            try:
                size = os.path.getsize(filepath)
                os.remove(filepath)
                deleted_count += 1
                total_bytes_freed += size
            except OSError:
                # 删除失败（可能被占用），跳过
                continue

        return (deleted_count, total_bytes_freed)

    @staticmethod
    def get_logs_total_size(log_dir: str = None) -> str:
        """
        获取所有日志文件的总大小（格式化字符串）。

        Args:
            log_dir: 日志目录路径

        Returns:
            格式化的大小字符串，如 '2.3 MB'
        """
        log_dir = log_dir or _DEFAULT_LOG_DIR
        if not os.path.isdir(log_dir):
            return TaskLogger.format_size(0)

        total_size = 0
        pattern = os.path.join(log_dir, "*.log")
        for filepath in glob.glob(pattern):
            try:
                total_size += os.path.getsize(filepath)
            except OSError:
                continue

        return TaskLogger.format_size(total_size)

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """
        将字节数格式化为人类可读的字符串。

        Args:
            size_bytes: 字节数

        Returns:
            格式化字符串，如 '1.5 KB', '2.3 MB', '1.0 GB'
        """
        if size_bytes < 0:
            size_bytes = 0

        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
