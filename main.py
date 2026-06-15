"""
CloakBrowser 自动注册测试工具
入口文件 - 启动 GUI 应用
"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import App


def main():
    """启动应用程序"""
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
