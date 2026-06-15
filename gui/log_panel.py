"""
日志面板 - 应用右侧的状态/日志显示区域
包含状态栏、实时日志、日志管理工具栏
"""
import datetime
import customtkinter as ctk
from gui.styles import COLORS, FONTS, SPACING
from core.logger import TaskLogger


# 状态 → 显示文字 & 颜色 的映射
_STATUS_MAP = {
    'idle':              ('● 空闲',       COLORS['text_dim']),
    'validating_proxy':  ('● 验证代理中', COLORS['warning']),
    'launching_browser': ('● 启动浏览器', COLORS['warning']),
    'running':           ('● 运行中',     COLORS['success']),
    'stopped':           ('● 已停止',     COLORS['text_secondary']),
    'timeout':           ('● 已超时',     COLORS['error']),
    'error':             ('● 出错',       COLORS['error']),
    'completed':         ('● 已完成',     COLORS['success']),
}

# 日志级别 → 颜色 & 标签前缀
_LEVEL_STYLE = {
    'INFO':    (COLORS['text_primary'], 'INFO'),
    'WARNING': (COLORS['warning'],      'WARN'),
    'ERROR':   (COLORS['error'],        'ERR '),
    'SUCCESS': (COLORS['success'],      ' OK '),
}

MAX_LOG_LINES = 200


class LogPanel(ctk.CTkFrame):
    """右侧日志面板，包含状态栏、日志区域和底部工具栏"""

    def __init__(self, master, on_clear_logs=None, on_fill_invite=None, on_read_email=None, on_create_apikey=None, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS['bg_card'],
            corner_radius=12,
            border_width=1,
            border_color=COLORS['border'],
            **kwargs,
        )
        self._on_clear_logs = on_clear_logs
        self._on_fill_invite = on_fill_invite
        self._on_read_email = on_read_email
        self._on_create_apikey = on_create_apikey
        self._build_ui()
        self.update_log_info()

    # ── UI 构建 ──────────────────────────────────────────────
    def _build_ui(self):
        """构建面板内所有控件"""
        self._build_status_bar()
        self._build_log_area()
        self._build_toolbar()

    def _build_status_bar(self):
        """顶部状态栏：状态指示 + 倒计时"""
        bar = ctk.CTkFrame(self, height=40, fg_color=COLORS['bg_secondary'], corner_radius=8)
        bar.pack(fill='x', padx=SPACING['pad_sm'], pady=(SPACING['pad_sm'], 0))
        bar.pack_propagate(False)

        # 状态指示
        self.status_label = ctk.CTkLabel(
            bar,
            text='● 空闲',
            font=FONTS['body'],
            text_color=COLORS['text_dim'],
            anchor='w',
        )
        self.status_label.pack(side='left', padx=SPACING['pad_md'])

        # 倒计时
        self.countdown_label = ctk.CTkLabel(
            bar,
            text='--:--',
            font=FONTS['mono'],
            text_color=COLORS['text_secondary'],
            anchor='e',
        )
        self.countdown_label.pack(side='right', padx=SPACING['pad_md'])

        timer_icon = ctk.CTkLabel(
            bar,
            text='⏱',
            font=FONTS['body'],
            text_color=COLORS['text_secondary'],
        )
        timer_icon.pack(side='right')

    def _build_log_area(self):
        """主体日志文本框"""
        self.log_text = ctk.CTkTextbox(
            self,
            font=FONTS['mono'],
            fg_color=COLORS['bg_input'],
            text_color=COLORS['text_primary'],
            border_width=1,
            border_color=COLORS['border'],
            corner_radius=8,
            wrap='word',
            state='disabled',  # 只读
        )
        self.log_text.pack(
            fill='both',
            expand=True,
            padx=SPACING['pad_sm'],
            pady=SPACING['pad_sm'],
        )

        # 注册颜色标签
        for level, (color, _prefix) in _LEVEL_STYLE.items():
            self.log_text.tag_config(level, foreground=color)
        # 时间戳标签
        self.log_text.tag_config('TIMESTAMP', foreground=COLORS['text_dim'])

        self._line_count = 0

    def _build_toolbar(self):
        """底部工具栏：功能按钮 + 清理按钮 + 日志统计"""
        toolbar = ctk.CTkFrame(self, height=36, fg_color='transparent')
        toolbar.pack(fill='x', padx=SPACING['pad_sm'], pady=(0, SPACING['pad_sm']))

        # 邀请码输入
        self.invite_entry = ctk.CTkEntry(
            toolbar,
            placeholder_text='邀请码',
            font=FONTS['mono_small'],
            width=100,
            height=30,
            corner_radius=6,
            fg_color=COLORS['bg_input'],
            text_color=COLORS['text_primary'],
            border_color=COLORS['border']
        )
        self.invite_entry.pack(side='left', padx=(0, SPACING['pad_sm']))

        # 填写按钮
        self.fill_btn = ctk.CTkButton(
            toolbar,
            text='填写',
            font=FONTS['small'],
            width=60,
            height=30,
            corner_radius=6,
            fg_color=COLORS['accent_primary'],
            hover_color=COLORS['accent_secondary'],
            command=self._handle_fill_invite,
        )
        self.fill_btn.pack(side='left', padx=(0, SPACING['pad_sm']))

        # 读取邮件按钮
        self.read_email_btn = ctk.CTkButton(
            toolbar,
            text='读取邮件',
            font=FONTS['small'],
            width=80,
            height=30,
            corner_radius=6,
            fg_color=COLORS['accent_primary'],
            hover_color=COLORS['accent_secondary'],
            command=self._handle_read_email,
        )
        self.read_email_btn.pack(side='left', padx=(0, SPACING['pad_sm']))

        # 创建 API Key 按钮
        self.create_apikey_btn = ctk.CTkButton(
            toolbar,
            text='创建',
            font=FONTS['small'],
            width=60,
            height=30,
            corner_radius=6,
            fg_color=COLORS['accent_primary'],
            hover_color=COLORS['accent_secondary'],
            command=self._handle_create_apikey,
        )
        self.create_apikey_btn.pack(side='left', padx=(0, SPACING['pad_sm']))

        # 占位推挤
        spacer = ctk.CTkFrame(toolbar, fg_color='transparent')
        spacer.pack(side='left', fill='x', expand=True)

        self.clear_btn = ctk.CTkButton(
            toolbar,
            text='🗑',
            font=FONTS['small'],
            width=30,
            height=30,
            corner_radius=6,
            fg_color=COLORS['bg_secondary'],
            hover_color=COLORS['hover'],
            text_color=COLORS['text_secondary'],
            command=self._handle_clear,
        )
        self.clear_btn.pack(side='right', padx=(SPACING['pad_sm'], 0))

        self.log_info_label = ctk.CTkLabel(
            toolbar,
            text='',
            font=FONTS['small'],
            text_color=COLORS['text_dim'],
            anchor='e',
        )
        self.log_info_label.pack(side='right')

    # ── 事件处理 ─────────────────────────────────────────────
    def _handle_clear(self):
        """转发清理日志按钮事件"""
        if self._on_clear_logs:
            self._on_clear_logs()

    def _handle_fill_invite(self):
        if self._on_fill_invite:
            code = self.invite_entry.get().strip()
            self._on_fill_invite(code)

    def _handle_read_email(self):
        if self._on_read_email:
            self._on_read_email()

    def _handle_create_apikey(self):
        if self._on_create_apikey:
            self._on_create_apikey()

    # ── 公共方法 ─────────────────────────────────────────────
    def append_log(self, level: str, message: str):
        """
        追加一条日志到文本框。

        格式: [HH:MM:SS] [LEVEL] message
        超过 MAX_LOG_LINES 时自动裁剪顶部旧行。
        自动滚动到底部。
        """
        level = level.upper()
        color, prefix = _LEVEL_STYLE.get(level, (COLORS['text_primary'], 'INFO'))
        now = datetime.datetime.now().strftime('%H:%M:%S')

        self.log_text.configure(state='normal')

        # 时间戳部分
        self.log_text.insert('end', f'[{now}] ', 'TIMESTAMP')
        # 级别标签部分
        self.log_text.insert('end', f'[{prefix}] ', level)
        # 消息正文
        self.log_text.insert('end', f'{message}\n', level)

        self._line_count += 1

        # 超出限制时裁剪旧行
        if self._line_count > MAX_LOG_LINES:
            trim = self._line_count - MAX_LOG_LINES
            self.log_text.delete('1.0', f'{trim + 1}.0')
            self._line_count = MAX_LOG_LINES

        self.log_text.configure(state='disabled')
        # 自动滚动到底部
        self.log_text.see('end')

    def update_status(self, status: str):
        """
        更新状态栏指示器。

        Args:
            status: 状态键，如 'idle', 'running', 'error' 等
        """
        text, color = _STATUS_MAP.get(status, ('● 未知', COLORS['text_dim']))
        self.status_label.configure(text=text, text_color=color)

        # 非运行状态时清除倒计时
        if status not in ('running', 'validating_proxy', 'launching_browser'):
            self.countdown_label.configure(text='--:--')

    def update_countdown(self, remaining_seconds: int):
        """
        更新倒计时显示。

        Args:
            remaining_seconds: 剩余秒数
        """
        if remaining_seconds < 0:
            remaining_seconds = 0
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        self.countdown_label.configure(text=f'{minutes:02d}:{seconds:02d}')

    def update_log_info(self):
        """刷新底部工具栏的日志文件数量和总大小"""
        try:
            files = TaskLogger.get_log_files()
            total_size = TaskLogger.get_logs_total_size()
            count = len(files)
            self.log_info_label.configure(text=f'日志文件: {count} 个 · {total_size}')
        except Exception:
            self.log_info_label.configure(text='日志文件: --')

    def clear_display(self):
        """清空日志文本框内容（不影响磁盘日志文件）"""
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')
        self._line_count = 0
