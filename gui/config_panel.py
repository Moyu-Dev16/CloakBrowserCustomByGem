"""
配置面板 - 应用左侧的可滚动配置区域
包含隐身模式、代理设置、目标地址、超时和操作按钮
"""
import customtkinter as ctk
from gui.styles import COLORS, FONTS, SPACING
from core.browser_manager import BrowserConfig
from core.proxy_manager import parse_proxy_list, get_proxy
from core.config_store import load_config, save_config


class ConfigPanel(ctk.CTkFrame):
    """左侧配置面板，提供所有任务参数设置"""

    PANEL_WIDTH = 380

    def __init__(self, master, on_start=None, on_stop=None, on_test_env=None, **kwargs):
        super().__init__(
            master,
            width=self.PANEL_WIDTH,
            fg_color=COLORS['bg_card'],
            corner_radius=12,
            border_width=1,
            border_color=COLORS['border'],
            **kwargs,
        )
        # 固定宽度，不随窗口伸缩
        self.pack_propagate(False)

        self._on_start = on_start
        self._on_stop = on_stop
        self._on_test_env = on_test_env
        self._is_running = False

        # 加载本地配置
        self._settings = load_config()

        self._build_ui()
        self._apply_settings()
        
        # 启动自动保存循环 (每3秒保存一次)
        self._auto_save_loop()

    def _auto_save_loop(self):
        """定期将当前配置写入文件"""
        if not self._is_running:
            # 运行中为了避免影响，可以考虑不保存或者直接保存，由于界面被禁用，值不会变
            current = self._get_settings_dict()
            if current != self._settings:
                self._settings = current
                save_config(self._settings)
        self.after(3000, self._auto_save_loop)

    def _get_settings_dict(self) -> dict:
        """从 UI 控件获取原始配置字典"""
        return {
            'stealth_mode': self.stealth_var.get(),
            'sync_proxy_locale': self.sync_locale_var.get(),
            'sync_proxy_timezone': self.sync_timezone_var.get(),
            'sync_proxy_geolocation': self.sync_geolocation_var.get(),
            'proxy_mode': self.proxy_mode_var.get(),
            'proxy_pool': '' if getattr(self, '_pool_is_placeholder', True) else self.proxy_pool_text.get('1.0', 'end').strip(),
            'rotating_proxy': self.rotating_entry.get().strip(),
            'proxy_api_url': self.api_entry.get().strip(),
            'target_url': self.target_entry.get().strip(),
            'timeout_minutes': self.timeout_var.get(),
            'email_pool': '' if getattr(self, '_email_is_placeholder', True) else self.email_pool_text.get('1.0', 'end').strip(),
            'auto_bind_create': self.auto_bind_create_var.get()
        }

    def _apply_settings(self):
        """将加载的设置应用到 UI"""
        s = self._settings
        self.stealth_var.set(s.get('stealth_mode', True))
        self.sync_locale_var.set(s.get('sync_proxy_locale', False))
        self.sync_timezone_var.set(s.get('sync_proxy_timezone', False))
        self.sync_geolocation_var.set(s.get('sync_proxy_geolocation', False))
        self.auto_bind_create_var.set(s.get('auto_bind_create', True))
        self.proxy_mode_var.set(s.get('proxy_mode', '无代理'))
        
        if s.get('proxy_pool'):
            self.proxy_pool_text.delete('1.0', 'end')
            self.proxy_pool_text.insert('1.0', s['proxy_pool'])
            self.proxy_pool_text.configure(text_color=COLORS['text_primary'])
            self._pool_is_placeholder = False
            
        if 'rotating_proxy' in self._settings:
            self.rotating_entry.delete(0, 'end')
            self.rotating_entry.insert(0, self._settings['rotating_proxy'])
            
        if 'proxy_api_url' in self._settings:
            self.api_entry.delete(0, 'end')
            self.api_entry.insert(0, self._settings['proxy_api_url'])

        # 应用代理模式，这会刷新动态区域的显示
        self._on_proxy_mode_change(s.get('proxy_mode', '无代理'))
            
        if s.get('target_url'):
            self.target_entry.delete(0, 'end')
            self.target_entry.insert(0, s['target_url'])
            
        timeout = s.get('timeout_minutes', 30)
        self.timeout_var.set(timeout)
        self.timeout_label.configure(text=f'{timeout} 分钟')
        
        if s.get('email_pool'):
            self.email_pool_text.delete('1.0', 'end')
            self.email_pool_text.insert('1.0', s['email_pool'])
            self.email_pool_text.configure(text_color=COLORS['text_primary'])
            self._email_is_placeholder = False

    # ── UI 构建 ──────────────────────────────────────────────
    def _build_ui(self):
        """构建面板内所有控件"""
        
        # ── 标题 ────────────────────────────────────────────
        self._build_header(self)

        # ── 选项卡容器 ──────────────────────────────────────
        self.tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=COLORS['accent_primary'],
            segmented_button_selected_hover_color=COLORS['accent_secondary']
        )
        self.tabview.pack(fill='both', expand=True, padx=SPACING['pad_sm'], pady=SPACING['pad_sm'])

        self.tab_base = self.tabview.add("基础设置")
        self.tab_proxy = self.tabview.add("代理配置")
        self.tab_pool = self.tabview.add("账号配置")

        # ── 基础设置页 ──────────────────────────────────────
        scroll_base = ctk.CTkScrollableFrame(self.tab_base, fg_color='transparent')
        scroll_base.pack(fill='both', expand=True)
        self._build_stealth_section(scroll_base)
        self._build_target_section(scroll_base)
        self._build_timeout_section(scroll_base)

        # ── 代理配置页 ──────────────────────────────────────
        scroll_proxy = ctk.CTkScrollableFrame(self.tab_proxy, fg_color='transparent')
        scroll_proxy.pack(fill='both', expand=True)
        self._build_proxy_section(scroll_proxy)

        # ── 账号池配置页 ────────────────────────────────────
        scroll_pool = ctk.CTkScrollableFrame(self.tab_pool, fg_color='transparent')
        scroll_pool.pack(fill='both', expand=True)
        self._build_email_pool_section(scroll_pool)
        self._build_failed_pool_section(scroll_pool)

        # ── 操作按钮 (全局底部) ──────────────────────────────
        self._build_action_button(self)

    # ── 各段构建方法 ─────────────────────────────────────────
    def _section_label(self, parent, text: str):
        """创建统一风格的小节标题"""
        lbl = ctk.CTkLabel(
            parent,
            text=text,
            font=FONTS['heading'],
            text_color=COLORS['text_primary'],
            anchor='w',
        )
        lbl.pack(fill='x', pady=(SPACING['pad_lg'], SPACING['pad_xs']))
        return lbl

    def _build_header(self, parent):
        """应用标题"""
        title = ctk.CTkLabel(
            parent,
            text='⚙  CloakBrowser',
            font=FONTS['title'],
            text_color=COLORS['accent_primary'],
            anchor='w',
        )
        title.pack(fill='x', pady=(SPACING['pad_sm'], 0))

        subtitle = ctk.CTkLabel(
            parent,
            text='自动注册测试工具 · 配置面板',
            font=FONTS['small'],
            text_color=COLORS['text_secondary'],
            anchor='w',
        )
        subtitle.pack(fill='x', pady=(0, SPACING['pad_md']))

        # 分隔线
        sep = ctk.CTkFrame(parent, height=1, fg_color=COLORS['border'])
        sep.pack(fill='x', pady=(0, SPACING['pad_sm']))

    def _build_stealth_section(self, parent):
        """隐身模式开关"""
        self._section_label(parent, '🛡  隐身模式')

        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', pady=SPACING['pad_xs'])

        self.stealth_var = ctk.BooleanVar(value=True)
        self.stealth_switch = ctk.CTkSwitch(
            row,
            text='启用浏览器指纹伪装',
            variable=self.stealth_var,
            font=FONTS['body'],
            text_color=COLORS['text_secondary'],
            progress_color=COLORS['accent_primary'],
            button_color=COLORS['accent_primary'],
            button_hover_color=COLORS['accent_secondary'],
        )
        self.stealth_switch.pack(side='left', padx=(0, 20))

        self.sync_locale_var = ctk.BooleanVar(value=False)
        self.sync_locale_switch = ctk.CTkSwitch(
            row,
            text='跟随代理设置浏览器语言 (默认中文)',
            variable=self.sync_locale_var,
            font=FONTS['body'],
            text_color=COLORS['text_secondary'],
            progress_color=COLORS['accent_primary'],
            button_color=COLORS['accent_primary'],
            button_hover_color=COLORS['accent_secondary'],
        )
        self.sync_locale_switch.pack(side='left')

        row2 = ctk.CTkFrame(parent, fg_color='transparent')
        row2.pack(fill='x', pady=SPACING['pad_xs'])

        self.sync_timezone_var = ctk.BooleanVar(value=False)
        self.sync_timezone_switch = ctk.CTkSwitch(
            row2,
            text='跟随代理设置时区',
            variable=self.sync_timezone_var,
            font=FONTS['body'],
            text_color=COLORS['text_secondary'],
            progress_color=COLORS['accent_primary'],
            button_color=COLORS['accent_primary'],
            button_hover_color=COLORS['accent_secondary'],
        )
        self.sync_timezone_switch.pack(side='left', padx=(0, 20))

        self.sync_geolocation_var = ctk.BooleanVar(value=False)
        self.sync_geolocation_switch = ctk.CTkSwitch(
            row2,
            text='跟随代理设置经纬度',
            variable=self.sync_geolocation_var,
            font=FONTS['body'],
            text_color=COLORS['text_secondary'],
            progress_color=COLORS['accent_primary'],
            button_color=COLORS['accent_primary'],
            button_hover_color=COLORS['accent_secondary'],
        )
        self.sync_geolocation_switch.pack(side='left')

        row3 = ctk.CTkFrame(parent, fg_color='transparent')
        row3.pack(fill='x', pady=SPACING['pad_xs'])

        self.auto_bind_create_var = ctk.BooleanVar(value=True)
        self.auto_bind_create_switch = ctk.CTkSwitch(
            row3,
            text='自动“绑定邀请码并创建API Key” (否则请在浏览器手动操作)',
            variable=self.auto_bind_create_var,
            font=FONTS['body'],
            text_color=COLORS['text_secondary'],
            progress_color=COLORS['accent_primary'],
            button_color=COLORS['accent_primary'],
            button_hover_color=COLORS['accent_secondary'],
        )
        self.auto_bind_create_switch.pack(side='left', padx=(0, 20))

    def _build_proxy_section(self, parent):
        """代理设置：模式选择 + 动态输入区"""
        self._section_label(parent, '🌐  代理设置')

        # 模式选择
        self.proxy_mode_var = ctk.StringVar(value='无代理')
        self.proxy_mode_seg = ctk.CTkSegmentedButton(
            parent,
            values=['无代理', '代理池', '轮转代理', 'API提取'],
            variable=self.proxy_mode_var,
            command=self._on_proxy_mode_change,
            font=FONTS['body'],
            selected_color=COLORS['accent_primary'],
            selected_hover_color=COLORS['accent_secondary'],
            unselected_color=COLORS['bg_secondary'],
            unselected_hover_color=COLORS['hover'],
            text_color=COLORS['text_primary'],
        )
        self.proxy_mode_seg.pack(fill='x', pady=SPACING['pad_sm'])

        # 动态输入区容器
        self._proxy_input_frame = ctk.CTkFrame(parent, fg_color='transparent')
        self._proxy_input_frame.pack(fill='x')

        # ── 代理池输入 ──
        self._proxy_pool_frame = ctk.CTkFrame(self._proxy_input_frame, fg_color='transparent')

        hint_pool = ctk.CTkLabel(
            self._proxy_pool_frame,
            text='每行一个代理，支持 http/https/socks5',
            font=FONTS['small'],
            text_color=COLORS['text_dim'],
            anchor='w',
        )
        hint_pool.pack(fill='x', pady=(0, SPACING['pad_xs']))

        self.proxy_pool_text = ctk.CTkTextbox(
            self._proxy_pool_frame,
            height=110,
            font=FONTS['mono_small'],
            fg_color=COLORS['bg_input'],
            text_color=COLORS['text_primary'],
            border_width=1,
            border_color=COLORS['border'],
            corner_radius=8,
        )
        self.proxy_pool_text.pack(fill='x')
        # 占位文字
        self.proxy_pool_text.insert(
            '1.0',
            'http://user:pass@host:port\nsocks5://host:port\nhttps://host:port',
        )
        self.proxy_pool_text.configure(text_color=COLORS['text_dim'])
        self.proxy_pool_text.bind('<FocusIn>', self._pool_focus_in)
        self.proxy_pool_text.bind('<FocusOut>', self._pool_focus_out)
        self._pool_is_placeholder = True

        # ── 轮转代理输入 ──
        self._rotating_frame = ctk.CTkFrame(self._proxy_input_frame, fg_color='transparent')

        hint_rot = ctk.CTkLabel(
            self._rotating_frame,
            text='输入轮转代理网关地址',
            font=FONTS['small'],
            text_color=COLORS['text_dim'],
            anchor='w',
        )
        hint_rot.pack(fill='x', pady=(0, SPACING['pad_xs']))

        self.rotating_entry = ctk.CTkEntry(
            self._rotating_frame,
            placeholder_text='http://gateway:port',
            font=FONTS['mono_small'],
            fg_color=COLORS['bg_input'],
            text_color=COLORS['text_primary'],
            border_width=1,
            border_color=COLORS['border'],
            corner_radius=8,
        )
        self.rotating_entry.pack(fill='x')

        # ── API 代理提取输入 ──
        self._api_frame = ctk.CTkFrame(self._proxy_input_frame, fg_color='transparent')

        hint_api = ctk.CTkLabel(
            self._api_frame,
            text='输入提取代理的 API 链接',
            font=FONTS['small'],
            text_color=COLORS['text_dim'],
            anchor='w',
        )
        hint_api.pack(fill='x', pady=(0, SPACING['pad_xs']))

        self.api_entry = ctk.CTkEntry(
            self._api_frame,
            placeholder_text='http://api.example.com/get?num=1',
            font=FONTS['mono_small'],
            fg_color=COLORS['bg_input'],
            text_color=COLORS['text_primary'],
            border_width=1,
            border_color=COLORS['border'],
            corner_radius=8,
        )
        self.api_entry.pack(fill='x')

        # 初始状态 - 无代理，不显示任何输入
        self._on_proxy_mode_change('无代理')

    def _build_email_pool_section(self, parent):
        """Outlook 邮箱池"""
        self._section_label(parent, '📧  Outlook 邮箱池')
        
        hint = ctk.CTkLabel(
            parent,
            text='格式: email----pass----client_id----refresh_token',
            font=FONTS['small'],
            text_color=COLORS['text_dim'],
            anchor='w',
        )
        hint.pack(fill='x', pady=(0, SPACING['pad_xs']))

        self.email_pool_text = ctk.CTkTextbox(
            parent,
            height=100,
            font=FONTS['mono_small'],
            fg_color=COLORS['bg_input'],
            text_color=COLORS['text_primary'],
            border_width=1,
            border_color=COLORS['border'],
            corner_radius=8,
        )
        self.email_pool_text.pack(fill='x')
        self.email_pool_text.insert('1.0', 'test@outlook.com----pass123----clientid----refreshtoken')
        self.email_pool_text.configure(text_color=COLORS['text_dim'])
        
        self._email_is_placeholder = True
        self.email_pool_text.bind('<FocusIn>', self._email_focus_in)
        self.email_pool_text.bind('<FocusOut>', self._email_focus_out)

    def _build_failed_pool_section(self, parent):
        """失败邮箱池展示区"""
        self._section_label(parent, '❌  失败邮箱记录')

        hint = ctk.CTkLabel(
            parent,
            text='自动化途中失败的邮箱将被放置在此处以备排查',
            font=FONTS['small'],
            text_color=COLORS['text_dim'],
            anchor='w',
        )
        hint.pack(fill='x', pady=(0, SPACING['pad_xs']))

        self.failed_pool_text = ctk.CTkTextbox(
            parent,
            height=100,
            font=FONTS['mono_small'],
            fg_color=COLORS['bg_input'],
            text_color=COLORS['error'],
            border_width=1,
            border_color=COLORS['border'],
            corner_radius=8,
        )
        self.failed_pool_text.pack(fill='x', pady=SPACING['pad_sm'])

    def _build_target_section(self, parent):
        """目标地址输入"""
        self._section_label(parent, '🎯  目标地址')

        self.target_entry = ctk.CTkEntry(
            parent,
            placeholder_text='https://example.com',
            font=FONTS['mono_small'],
            fg_color=COLORS['bg_input'],
            text_color=COLORS['text_primary'],
            border_width=1,
            border_color=COLORS['border'],
            corner_radius=8,
            height=36,
        )
        self.target_entry.insert(0, 'https://platform.xiaomimimo.com?ref=')
        self.target_entry.pack(fill='x', pady=SPACING['pad_sm'])

    def _build_timeout_section(self, parent):
        """任务超时滑块"""
        self._section_label(parent, '⏱  任务超时')

        self.timeout_var = ctk.IntVar(value=30)

        self.timeout_label = ctk.CTkLabel(
            parent,
            text='30 分钟',
            font=FONTS['body'],
            text_color=COLORS['text_secondary'],
            anchor='w',
        )
        self.timeout_label.pack(fill='x')

        self.timeout_slider = ctk.CTkSlider(
            parent,
            from_=5,
            to=120,
            number_of_steps=23,  # (120-5)/5 = 23 步, 每步5分钟
            variable=self.timeout_var,
            command=self._on_timeout_change,
            progress_color=COLORS['accent_primary'],
            button_color=COLORS['accent_primary'],
            button_hover_color=COLORS['accent_secondary'],
            fg_color=COLORS['bg_input'],
        )
        self.timeout_slider.pack(fill='x', pady=SPACING['pad_sm'])

    def _build_action_button(self, parent):
        """启动 / 停止按钮"""
        spacer = ctk.CTkFrame(parent, height=SPACING['pad_lg'], fg_color='transparent')
        spacer.pack(fill='x')

        self.action_btn = ctk.CTkButton(
            parent,
            text='▶  启动任务',
            font=FONTS['heading'],
            height=48,
            corner_radius=10,
            fg_color=COLORS['accent_primary'],
            hover_color=COLORS['accent_secondary'],
            text_color='#ffffff',
            command=self._handle_action,
        )
        self.action_btn.pack(fill='x', pady=SPACING['pad_sm'])

        self.test_btn = ctk.CTkButton(
            parent,
            text='🔍  测试浏览器环境',
            font=FONTS['body'],
            height=36,
            corner_radius=8,
            fg_color=COLORS['bg_input'],
            hover_color=COLORS['hover'],
            text_color=COLORS['text_primary'],
            border_width=1,
            border_color=COLORS['border'],
            command=self._handle_test_env,
        )
        self.test_btn.pack(fill='x', pady=(0, SPACING['pad_sm']))

    # ── 事件处理 ─────────────────────────────────────────────
    def _on_proxy_mode_change(self, mode: str):
        """切换代理模式时显示/隐藏对应的输入区域"""
        self._proxy_pool_frame.pack_forget()
        self._rotating_frame.pack_forget()
        self._api_frame.pack_forget()

        if mode == '代理池':
            self._proxy_pool_frame.pack(in_=self._proxy_input_frame, fill='x', pady=SPACING['pad_xs'])
        elif mode == '轮转代理':
            self._rotating_frame.pack(in_=self._proxy_input_frame, fill='x', pady=SPACING['pad_xs'])
        elif mode == 'API提取':
            self._api_frame.pack(in_=self._proxy_input_frame, fill='x', pady=SPACING['pad_xs'])

    def _on_timeout_change(self, value):
        """滑块值变化时更新标签"""
        minutes = int(float(value))
        self.timeout_var.set(minutes)
        self.timeout_label.configure(text=f'{minutes} 分钟')

    def _pool_focus_in(self, _event=None):
        """代理池文本框获得焦点时清除占位文字"""
        if self._pool_is_placeholder:
            self.proxy_pool_text.delete('1.0', 'end')
            self.proxy_pool_text.configure(text_color=COLORS['text_primary'])
            self._pool_is_placeholder = False

    def _pool_focus_out(self, _event=None):
        """代理池文本框失去焦点时恢复占位文字"""
        content = self.proxy_pool_text.get('1.0', 'end').strip()
        if not content:
            self.proxy_pool_text.insert(
                '1.0',
                'http://user:pass@host:port\nsocks5://host:port\nhttps://host:port',
            )
            self.proxy_pool_text.configure(text_color=COLORS['text_dim'])
            self._pool_is_placeholder = True

    def _email_focus_in(self, _event=None):
        if getattr(self, '_email_is_placeholder', True):
            self.email_pool_text.delete('1.0', 'end')
            self.email_pool_text.configure(text_color=COLORS['text_primary'])
            self._email_is_placeholder = False

    def _email_focus_out(self, _event=None):
        content = self.email_pool_text.get('1.0', 'end').strip()
        if not content:
            self.email_pool_text.insert('1.0', 'test@outlook.com----pass123----clientid----refreshtoken')
            self.email_pool_text.configure(text_color=COLORS['text_dim'])
            self._email_is_placeholder = True

    def _handle_action(self):
        """按钮点击分发：启动或停止"""
        if self._is_running:
            if self._on_stop:
                self._on_stop()
        else:
            if callable(self._on_start):
                self._on_start()
                
    def _handle_test_env(self):
        """触发环境测试事件"""
        if self._is_running:
            return
        if callable(self._on_test_env):
            self._on_test_env()

    # ── 对外接口 ─────────────────────────────────────────────
    def get_config(self) -> BrowserConfig:
        """
        读取面板中所有设置，生成 BrowserConfig。

        代理选择逻辑：
        - 无代理 → proxy=None
        - 代理池 → 从列表中随机选择一个
        - 轮转代理 → 使用填入的网关地址
        """
        mode = self.proxy_mode_var.get()
        proxy = None

        if mode == '代理池':
            raw = '' if self._pool_is_placeholder else self.proxy_pool_text.get('1.0', 'end')
            proxy_list = parse_proxy_list(raw)
            proxy = get_proxy('pool', proxy_list=proxy_list) if proxy_list else None
        elif mode == '轮转代理':
            rotating_url = self.rotating_entry.get().strip()
            proxy = get_proxy('rotating', rotating_proxy=rotating_url) if rotating_url else None
        elif mode == 'API提取':
            api_url = self.api_entry.get().strip()
            proxy = get_proxy('api', api_url=api_url) if api_url else None

        email, password, client_id, refresh_token = None, None, None, None
        email_text = '' if getattr(self, '_email_is_placeholder', True) else self.email_pool_text.get('1.0', 'end').strip()
        if email_text:
            lines = [l.strip() for l in email_text.split('\n') if l.strip()]
            
            # 读取成功列表，剔除已经成功的邮箱
            import os
            success_emails = set()
            if os.path.exists('成功.txt'):
                try:
                    with open('成功.txt', 'r', encoding='utf-8') as f:
                        for line in f:
                            parts = line.strip().split('----')
                            if parts:
                                success_emails.add(parts[0].strip())
                except Exception:
                    pass
                    
            valid_lines = []
            for line in lines:
                parts = line.split('----')
                if parts and parts[0].strip() not in success_emails:
                    valid_lines.append(line)
                    
            # 如果存在已经被剔除的邮箱，同步更新回界面
            if len(valid_lines) != len(lines):
                self.email_pool_text.delete('1.0', 'end')
                new_text = '\n'.join(valid_lines)
                if new_text:
                    self.email_pool_text.insert('1.0', new_text)
                else:
                    self._email_focus_out() # 变回占位符
                
            if valid_lines:
                parts = valid_lines[0].split('----')
                if len(parts) >= 4:
                    email, password, client_id, refresh_token = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()

        return BrowserConfig(
            target_url=self.target_entry.get().strip() or 'https://platform.xiaomimimo.com?ref=',
            proxy=proxy,
            stealth_mode=self.stealth_var.get(),
            sync_proxy_locale=self.sync_locale_var.get(),
            sync_proxy_timezone=self.sync_timezone_var.get(),
            sync_proxy_geolocation=self.sync_geolocation_var.get(),
            timeout_minutes=self.timeout_var.get(),
            target_email=email,
            target_password=password,
            email_client_id=client_id,
            email_refresh_token=refresh_token
        )

    def remove_first_email(self):
        """移除邮箱池中的第一个邮箱并保存"""
        email_text = '' if getattr(self, '_email_is_placeholder', True) else self.email_pool_text.get('1.0', 'end').strip()
        if email_text:
            lines = [l.strip() for l in email_text.split('\n') if l.strip()]
            if lines:
                lines.pop(0)
                self.email_pool_text.delete('1.0', 'end')
                new_text = '\n'.join(lines)
                if new_text:
                    self.email_pool_text.insert('1.0', new_text)
                else:
                    self._email_focus_out()

    def append_failed_email(self, email_line: str):
        """将失败的邮箱追加到失败记录框中"""
        self.failed_pool_text.insert('end', email_line + '\n')
        self.failed_pool_text.see('end')

    def set_running_state(self, is_running: bool):
        """
        切换运行状态：更新按钮文字/颜色，禁用/启用输入控件。
        """
        self._is_running = is_running
        state = 'disabled' if is_running else 'normal'

        if is_running:
            self.action_btn.configure(
                text='⏹  停止任务',
                fg_color=COLORS['error'],
                hover_color='#c0392b',
            )
        else:
            self.action_btn.configure(
                text='▶  启动任务',
                fg_color=COLORS['accent_primary'],
                hover_color=COLORS['accent_secondary'],
            )

        # 禁用/启用所有输入控件
        self.stealth_switch.configure(state=state)
        self.proxy_mode_seg.configure(state=state)
        self.proxy_pool_text.configure(state=state)
        self.rotating_entry.configure(state=state)
        self.api_entry.configure(state=state)
        self.email_pool_text.configure(state=state)
        self.target_entry.configure(state=state)
        self.timeout_slider.configure(state=state)
        self.test_btn.configure(state=state)
