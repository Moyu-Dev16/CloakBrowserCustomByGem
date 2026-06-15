"""
UI 主题和样式常量
深色主题 + 蓝紫渐变高亮
"""
import customtkinter as ctk

# 颜色调色板 - 深色主题 + 蓝紫色点缀
COLORS = {
    'bg_primary': '#1a1a2e',       # 深海军蓝背景
    'bg_secondary': '#16213e',     # 稍浅海军蓝
    'bg_card': '#1f2b47',          # 卡片/面板背景
    'bg_input': '#0f1629',         # 输入框背景
    'accent_primary': '#4361ee',   # 亮蓝色点缀
    'accent_secondary': '#7209b7', # 紫色点缀
    'accent_gradient_start': '#4361ee',
    'accent_gradient_end': '#7209b7',
    'success': '#06d6a0',          # 绿色
    'warning': '#ffd166',          # 黄色
    'error': '#ef476f',            # 红粉色
    'text_primary': '#e8e8e8',     # 主要文字
    'text_secondary': '#8892b0',   # 次要文字
    'text_dim': '#5a6380',         # 暗淡文字
    'border': '#2a3456',           # 细微边框
    'hover': '#2a3a6e',            # 悬停状态
}

# 字体族定义
FONTS = {
    'title': ('Segoe UI', 18, 'bold'),
    'heading': ('Segoe UI', 14, 'bold'),
    'body': ('Segoe UI', 12),
    'small': ('Segoe UI', 10),
    'mono': ('Consolas', 11),
    'mono_small': ('Consolas', 10),
}

# 间距常量
SPACING = {
    'pad_xs': 4,
    'pad_sm': 8,
    'pad_md': 12,
    'pad_lg': 16,
    'pad_xl': 24,
}


def setup_theme():
    """配置 CustomTkinter 全局主题"""
    ctk.set_appearance_mode('dark')
    ctk.set_default_color_theme('blue')
