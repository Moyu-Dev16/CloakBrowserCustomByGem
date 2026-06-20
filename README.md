# CloakBrowser 自动注册测试工具

基于 [CloakBrowser](https://github.com/CloakHQ/CloakBrowser)（Playwright 隐身替代品）构建的自动注册测试工具，配备 CustomTkinter 现代化 GUI。

> [!WARNING]
> **免责声明**
> 本项目仅供学习、研究自动化测试与浏览器指纹技术使用。禁止将本项目用于任何非法用途（包括但不限于黑灰产、恶意注册、刷单等违规行为）。因使用本工具造成的任何直接或间接后果，由使用者自行承担，作者不负任何法律责任。

![GUI 预览界面](ui_preview.png)

## 功能特性

- 🕵️ **隐身模式**：一键开启 CloakBrowser 的隐身特性（人类模拟行为、指纹伪装）
- 🌐 **代理支持**：支持 HTTP / HTTPS / SOCKS5 代理，提供「代理池」和「轮转代理」两种模式
- ✅ **代理验证**：启动浏览器前自动检测代理可用性
- ⏱️ **超时管理**：可配置任务时长（5–120 分钟），超时自动关闭浏览器
- 🛡️ **异常安全**：浏览器运行期间任何错误不会导致浏览器关闭
- 📋 **日志系统**：GUI 简洁日志 + 完整日志文件按时间保存 + 一键清理

## 安装

```bash
pip install -r requirements.txt
```

首次运行时，CloakBrowser 会自动下载隐身 Chromium 内核（约 200MB）。

## 运行

```bash
python main.py
```

## 使用说明

1. 配置隐身模式（默认开启）
2. 选择代理模式：
   - **无代理**：使用本机网络
   - **代理池**：多行输入代理地址，每次随机选取
   - **轮转代理**：输入单个轮转代理地址
3. 设置任务超时时间（默认 30 分钟）
4. 点击「启动任务」

## 代理格式

支持以下格式：
```
http://user:pass@host:port
https://user:pass@host:port
socks5://user:pass@host:port
http://host:port
socks5://host:port
```

## 项目结构

```
├── main.py                  # 入口文件
├── gui/                     # GUI 界面层
│   ├── app.py               # 主窗口
│   ├── config_panel.py      # 配置面板
│   ├── log_panel.py         # 日志面板
│   └── styles.py            # 主题样式
├── core/                    # 核心逻辑层
│   ├── browser_manager.py   # 浏览器管理
│   ├── proxy_manager.py     # 代理管理
│   ├── task_runner.py        # 任务运行器
│   └── logger.py            # 日志管理器
├── logs/                    # 日志文件目录
└── requirements.txt         # 依赖
```

## 技术栈

- **Python 3.9+**
- **CloakBrowser** — 隐身浏览器（Playwright 替代品）
- **CustomTkinter** — 现代化 Tkinter GUI 框架
- **requests[socks]** — HTTP/SOCKS5 代理验证
