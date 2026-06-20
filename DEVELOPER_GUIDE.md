# CloakBrowserCustomByGem 开发交接文档

## 1. 项目简介
CloakBrowserCustomByGem 是一个基于 Python 和 Playwright 的全自动浏览器指纹伪装与账号注册测试框架，主要针对“小米海外/全球账号”体系以及后续的开发者控制台 API Key 创建流程。项目采用前后端分离的架构：前端使用 `CustomTkinter` 构建现代化的图形界面，后端通过多线程调度 `Playwright` 执行无头/有头浏览器的自动化流程。

## 2. 核心技术栈
- **UI框架**: `customtkinter` (提供暗色主题、现代化的 GUI 控制面板)
- **自动化核心**: `playwright` (异步与同步混合封装)
- **指纹伪装**: `playwright-stealth` (绕过常见 WebDriver 检测)
- **图像识别**: `opencv-python` (`cv2`，用于极验滑块验证码缺口计算)
- **邮件查收**: 基于 Microsoft Graph API 的自动化邮件读取与正则提取验证码
- **并发模型**: `threading` (UI 主线程 + 自动化任务工作线程)

## 3. 项目目录结构
```text
CloakBrowserCustomByGem/
├── gui/
│   ├── main.py              # GUI 应用程序入口，组合各个 UI 组件
│   └── config_panel.py      # 配置面板 UI 实现，处理配置项的加载与保存
├── core/
│   ├── browser_manager.py   # Playwright 浏览器实例生命周期管理、代理注入、指纹伪装
│   ├── task_runner.py       # 核心业务逻辑控制器，封装了注册流程、排队执行与状态轮询
│   ├── email_reader.py      # 对接 Microsoft Graph API 收取 Hotmail/Outlook 验证邮件
│   ├── proxy_manager.py     # 代理池管理，支持 API 提取、轮转代理等
│   ├── config_store.py      # config.ini 配置文件的读写操作
│   └── logger.py            # 自定义日志模块，同时输出到终端和 GUI 界面
├── core/captcha/
│   └── geetest_solver.py    # 极验滑块验证码本地 OpenCV 识别与仿生拖拽引擎
├── config.ini               # 本地配置文件 (自动生成)
└── 成功.txt                 # 记录注册并创建成功的目标邮箱
```

## 4. 核心自动化流程 (TaskRunner)
核心流程位于 `core/task_runner.py` 中的 `_execute_automation` 方法，主要流转如下：
1. **环境准备**: 注入 Proxy，同步时区和语言，启用隐身模式 (`playwright-stealth`)。
2. **账号填入**: 读取本地邮箱池，随机生成国家并处理“下拉框遮挡”与“JS强制点击”的问题。
3. **极验破解**: 触发小米的 Geetest 验证码。调用 `geetest_solver.py` 获取 Canvas 画布图像，通过 OpenCV 算子（`Canny` 边缘检测 + `matchTemplate`）计算滑块缺口距离，最后使用贝塞尔曲线式的仿生鼠标轨迹 (`_perform_bionic_drag`) 完成拖拽。
4. **验证码查收**: 极验通过后，等待页面跳转，轮询调用 `email_reader.py` 读取 6 位数验证码并使用 JS 原生分发 (`dispatchEvent`) 强行写入前端 React 组件。
5. **创建 API Key**: 进入 Console 控制台，勾选用户协议，（如果配置）发送绑定邀请码的 API 请求，最后请求生成 API Key 并将其记录到本地文件 `成功.txt`。

## 5. 关键痛点与近期修复记录 (交接重点)
接手的 AI 请重点注意以下历史踩坑点，**千万不要回退以下逻辑**：

### 5.1 极验验证码网络容错
- **问题**: 挂载海外代理时，极验图片加载极慢，导致 `screenshot` 截出的是带有“加载中”字样的灰图。OpenCV 计算的缺口距离异常（极小值）。
- **解决**: 在 `geetest_solver.py` 中引入了 `retry_extract` 重试循环，如果缺口距离异常，则强制挂起等待网络图片加载，而不是直接点刷新。

### 5.2 国家下拉框由于 DOM 遮挡点击失效
- **问题**: 在小米注册页选择海外国家时，由于 React 框架内部虚拟 DOM 的频繁更新与遮挡，Playwright 的普通 `click()` 经常报拦截。
- **解决**: 在 `task_runner.py` 国家选择器部分，同时配置了基于可见元素的重试机制，并在常规点击失败时引入了 `page.evaluate()` 底层 JS `click()` 的强制触发兜底方案。

### 5.3 队列锁死导致 GUI 按钮失效
- **问题**: 之前设计“半自动手动测试模式”时，使用了 `while True: time.sleep(1)` 来挂起任务，导致 `TaskRunner` 的核心线程卡死，无法处理来自 GUI 发送的 `self._action_queue.get()`（即界面上的填写、查收邮件按钮无响应）。
- **解决**: 已将挂起逻辑改为直接 `return` 退出自动化方法，使控制权交还给 `TaskRunner._run` 尾部的常驻监听循环，实现了浏览器保持打开的同时，秒级响应界面 Action 队列指令。

### 5.4 验证码输入框双向绑定失效
- **问题**: Ant Design / React 组件通过属性 `value` 绑定，单纯用 Playwright 的 `.fill()` 无法触发其 onChange 事件，导致表单校验不通过。
- **解决**: `task_runner.py` 中封装了 `js_assign_local` 方法，通过劫持 `HTMLInputElement.prototype.value` 的 setter，再手动派发 `input` 和 `change` 事件强制唤醒 React 校验逻辑。

## 6. 后续开发建议
- **图形验证容错**: `geetest_solver.py` 当前对完全透明的 PNG 切图存在一些特征丢失问题，后续可优化 Alpha 通道的预处理。
- **风控日志分析**: 小米后端的注册接口如果因为 IP 过度泛滥而拉黑，会在界面弹出 Toast（诸如“当前账号存在风控限制”），`task_runner.py` 已实现了 Toast 捕获机制，接手后可依据此部分继续完善代理 IP 的自动剔除和降级策略。
- **并发规模**: 当前架构偏向单线程串行执行（测试友好型）。若需做批量高并发，需改造 `gui/main.py` 的任务分发中心，并确保 `BrowserConfig` 与各个 Worker 线程的隔离。
