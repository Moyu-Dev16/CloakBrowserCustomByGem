"""
主窗口 - 组合配置面板和日志面板
负责整合 TaskRunner、TaskLogger 与两个面板之间的交互
"""
import customtkinter as ctk
import tkinter.messagebox as messagebox

from gui.styles import setup_theme, COLORS, FONTS, SPACING
from gui.config_panel import ConfigPanel
from gui.log_panel import LogPanel
from core.logger import TaskLogger
from core.task_runner import TaskRunner
from core.browser_manager import BrowserConfig


class App(ctk.CTk):
    """CloakBrowser 主窗口"""

    def __init__(self):
        super().__init__()
        setup_theme()

        # ── 窗口基础配置 ────────────────────────────────────
        self.title('CloakBrowser 自动注册测试工具')
        self.geometry('1100x700')
        self.minsize(900, 600)
        self.configure(fg_color=COLORS['bg_primary'])

        # 居中显示窗口
        self._center_window(1100, 700)

        # ── 核心组件 ────────────────────────────────────────
        self.logger = TaskLogger()
        self.logger.set_gui_callback(self._on_log)

        self.task_runner = TaskRunner(
            logger=self.logger,
            on_status_change=self._on_status_change,
            on_countdown=self._on_countdown,
            on_bind_success=self._on_bind_success,
            on_task_fail=self._on_task_fail,
        )

        # ── 布局：左配置面板 + 右日志面板 ───────────────────
        self.config_panel = ConfigPanel(
            self,
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_test_env=self._on_test_env,
        )
        self.config_panel.pack(
            side='left',
            fill='y',
            padx=(SPACING['pad_md'], 0),
            pady=SPACING['pad_md'],
        )

        self.log_panel = LogPanel(
            self,
            on_clear_logs=self._on_clear_logs,
            on_fill_invite=self._on_fill_invite,
            on_read_email=self._on_read_email,
            on_create_apikey=self._on_create_apikey,
        )
        self.log_panel.pack(
            side='right',
            fill='both',
            expand=True,
            padx=SPACING['pad_md'],
            pady=SPACING['pad_md'],
        )

        # ── 窗口关闭处理 ────────────────────────────────────
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    # ── 工具方法 ─────────────────────────────────────────────
    def _center_window(self, width: int, height: int):
        """将窗口居中到屏幕"""
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.geometry(f'{width}x{height}+{x}+{y}')

    # ── 任务控制 ─────────────────────────────────────────────
    def _on_start(self):
        """处理启动按钮点击：读取配置并启动任务"""
        config = self.config_panel.get_config()

        # 检查目标地址
        if not config.target_url:
            messagebox.showwarning('配置错误', '请填写目标地址。')
            return

        # 检查邀请码
        invite_code = self.log_panel.invite_entry.get().strip()
        if not invite_code:
            if not messagebox.askyesno('未填写邀请码', '邀请码未填写，是否继续？'):
                return
                
        config.invite_code = invite_code

        # 直接启动任务，代理验证由 TaskRunner 内部处理
        self._do_start(config)

    def _do_start(self, config: BrowserConfig):
        """实际启动任务运行器"""
        self.config_panel.set_running_state(True)
        self.log_panel.clear_display()

        # 启动日志文件会话
        self.logger.start_session()

        self.logger.info('任务已启动')
        self.logger.info(f'目标地址: {config.target_url}')
        self.logger.info(f'隐身模式: {"开启" if config.stealth_mode else "关闭"}')
        self.logger.info(f'代理: {config.proxy or "无"}')
        self.logger.info(f'超时: {config.timeout_minutes} 分钟')
        self.task_runner.start(config)

    def _on_stop(self):
        """处理停止按钮点击"""
        if self.task_runner.is_running:
            self.logger.info('正在停止任务...')
            self._manual_stop = True # 标记为手动停止
            self.task_runner.stop()

    def _on_test_env(self):
        """处理环境测试按钮点击"""
        if self.task_runner.is_running:
            return

        config = self.config_panel.get_config()
        self.config_panel.set_running_state(True)
        self.log_panel.clear_display()
        self.logger.start_session()
        self.logger.info("启动环境测试...")
        
        def test_thread():
            import time
            from core.browser_manager import launch_browser, close_browser
            
            # 强制修改目标地址和超时
            config.target_url = "https://www.todetect.cn/"
            config.timeout_minutes = 10 
            
            browser, page = launch_browser(config, self.logger)
            if browser and page:
                self.logger.success("✅ 测试浏览器已打开！")
                self.logger.info("你可以自由查看本站点的环境伪装检测结果。")
                self.logger.warning("注意：测试窗口将在 10 分钟后自动关闭，或者你可以手动将其关闭。")
                try:
                    # 等待10分钟或直到浏览器被手动关闭
                    page.wait_for_timeout(600000)
                except Exception as e:
                    self.logger.info(f"测试浏览器等待结束: {type(e).__name__}")
                self.logger.info("正在关闭测试浏览器...")
                close_browser(browser, self.logger)
            else:
                self.logger.error("测试浏览器启动失败")
                
            self.after(0, lambda: self.config_panel.set_running_state(False))
            self.after(0, lambda: self.logger.info("环境测试结束"))
            self.after(0, self.logger.stop_session)
            
        import threading
        threading.Thread(target=test_thread, daemon=True).start()

    # ── 回调：来自 TaskLogger（可能从后台线程调用）──────────
    def _on_log(self, level: str, message: str):
        """日志回调 - 通过 after() 保证线程安全"""
        self.after(0, self.log_panel.append_log, level, message)

    # ── 回调：来自 TaskRunner（可能从后台线程调用）─────────
    def _on_status_change(self, status: str):
        """状态变更回调 - 线程安全"""
        self.after(0, self.log_panel.update_status, status)
        # 根据状态切换面板的运行状态
        running_states = ('validating_proxy', 'launching_browser', 'running')
        if status in running_states:
            self.after(0, lambda: self.config_panel.set_running_state(True))
            self._manual_stop = False # 每次运行重置标志
        else:
            self.after(0, lambda: self.config_panel.set_running_state(False))
            # 任务结束时：关闭日志会话，刷新日志统计
            self.after(0, self._on_task_finished)

    def _on_task_finished(self):
        """任务结束后的清理工作，并检查是否继续下一个任务"""
        self.logger.stop_session()
        self.log_panel.update_log_info()
        
        # 判断是否需要自动执行下一个任务
        # 我们只在正常停止（status = 'stopped'）且并非手动终止时才自动开始
        if getattr(self, '_manual_stop', False):
            self.logger.warning("任务已被手动终止，取消自动执行下一轮。")
            return
            
        config = self.config_panel.get_config()
        if config.target_email: # 说明邮箱池里还有没跑的邮箱
            self.logger.info("检测到邮箱池还有剩余账号，将在 5 秒后自动启动下一轮任务...")
            self.after(5000, self._on_start)
        else:
            self.logger.success("邮箱池已空，所有批处理任务执行完毕！")

    def _on_countdown(self, remaining: int):
        """倒计时回调 - 线程安全"""
        self.after(0, self.log_panel.update_countdown, remaining)

    # ── 日志管理 ─────────────────────────────────────────────
    def _on_clear_logs(self):
        """处理清理日志按钮：确认后删除磁盘日志文件"""
        try:
            files = TaskLogger.get_log_files()
            total_size = TaskLogger.get_logs_total_size()
        except Exception as e:
            self.logger.error(f"读取日志文件信息失败: {type(e).__name__}: {e}")
            files = []
            total_size = '0 B'

        count = len(files)
        if count == 0:
            messagebox.showinfo('清理日志', '没有可清理的日志文件。')
            return

        confirmed = messagebox.askyesno(
            '确认清理',
            f'确定要删除所有日志文件吗？\n\n'
            f'文件数量: {count} 个\n'
            f'占用空间: {total_size}\n\n'
            f'此操作不可撤销。',
        )
        if not confirmed:
            return

        try:
            deleted, freed = TaskLogger.clear_all_logs()
            freed_str = TaskLogger.format_size(freed)
            self.logger.success(f'已清理 {deleted} 个日志文件，释放 {freed_str}')
        except Exception as e:
            self.logger.error(f'清理日志失败: {e}')

        # 刷新底部统计信息
        self.log_panel.update_log_info()

    def _on_fill_invite(self, code: str):
        if self.task_runner.is_running:
            self.task_runner.bind_invite_code(code)
        else:
            self.logger.warning("任务未运行，无法填写邀请码")

    def _on_read_email(self):
        # 即使未运行浏览器，也可以在后台读取邮件（只需网络请求）
        # 这里为了保持一致，统一塞入任务队列。如果需要独立执行，可修改 TaskRunner 支持空闲状态处理。
        self.task_runner.read_email()

    def _on_create_apikey(self):
        if self.task_runner.is_running:
            self.task_runner.create_apikey()
        else:
            self.logger.warning("任务未运行，无法创建 API Key")

    def _on_bind_success(self):
        """当邀请码绑定成功时，从邮箱池中移除使用的邮箱"""
        self.after(0, self.config_panel.remove_first_email)

    def _on_task_fail(self):
        """当任务失败时，从邮箱池中移除使用的邮箱，并追加到失败记录中"""
        def update_ui():
            email_text = '' if getattr(self.config_panel, '_email_is_placeholder', True) else self.config_panel.email_pool_text.get('1.0', 'end').strip()
            if email_text:
                lines = [l.strip() for l in email_text.split('\n') if l.strip()]
                if lines:
                    failed_line = lines[0]
                    self.config_panel.append_failed_email(failed_line)
                    self.config_panel.remove_first_email()
        self.after(0, update_ui)

    # ── 窗口关闭 ─────────────────────────────────────────────
    def _on_close(self):
        """窗口关闭事件：运行中则弹出确认对话框"""
        if self.task_runner.is_running:
            if messagebox.askyesno(
                '确认退出',
                '任务正在运行中，确定要退出吗？\n浏览器将被关闭。',
            ):
                self.task_runner.stop()
                self.destroy()
        else:
            self.destroy()
