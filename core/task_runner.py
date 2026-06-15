"""
任务运行器 - 独立线程运行任务
异常兜底、超时调度、手动停止

状态流转:
    idle → validating_proxy → launching_browser → running → timeout/stopped
                                                         ↘ error

关键设计:
- 浏览器在 running 阶段不会因异常自动关闭，只有超时或手动停止才会关闭
- 所有异常都被捕获并记录，不会导致线程崩溃
- 通过 threading.Event 实现优雅停止
"""
import threading
import time
import queue
from typing import Optional, Callable

from core.browser_manager import BrowserConfig, launch_browser, close_browser
from core.proxy_manager import validate_proxy


class TaskRunner:
    """
    任务运行器，在独立线程中管理浏览器生命周期。

    Features:
        - 代理验证
        - 浏览器启动与页面导航
        - 超时自动关闭
        - 手动停止支持
        - 全程异常兜底

    使用方式:
        runner = TaskRunner(logger, on_status_change=update_ui)
        runner.start(config)
        # ... 等待任务完成或手动停止
        runner.stop()
    """

    # 所有可能的任务状态
    STATUS_IDLE = 'idle'
    STATUS_VALIDATING_PROXY = 'validating_proxy'
    STATUS_LAUNCHING_BROWSER = 'launching_browser'
    STATUS_RUNNING = 'running'
    STATUS_TIMEOUT = 'timeout'
    STATUS_STOPPED = 'stopped'
    STATUS_ERROR = 'error'

    def __init__(
        self,
        logger,
        on_status_change: Callable = None,
        on_countdown: Callable = None,
        on_bind_success: Callable = None,
        on_task_fail: Callable = None,
    ):
        """
        初始化任务运行器。

        Args:
            logger: TaskLogger 实例，用于记录日志
            on_status_change: 状态变更回调，签名: callback(status: str)
                可能的状态值: 'idle', 'validating_proxy', 'launching_browser',
                            'running', 'timeout', 'stopped', 'error'
            on_countdown: 倒计时回调，签名: callback(remaining_seconds: int)
                在 running 状态下每秒调用一次
            on_bind_success: 绑定成功时的回调，用于清理已使用的邮箱
            on_task_fail: 自动化流程失败时的回调，用于将邮箱移入失败池
        """
        self._logger = logger
        self._on_status_change = on_status_change
        self._on_countdown = on_countdown
        self._on_bind_success = on_bind_success
        self._on_task_fail = on_task_fail

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._browser = None
        self._page = None
        self._current_config = None
        self._action_queue = queue.Queue()
        self._status = self.STATUS_IDLE

    @property
    def is_running(self) -> bool:
        """任务是否正在运行（线程是否存活）。"""
        return self._thread is not None and self._thread.is_alive()

    @property
    def status(self) -> str:
        """当前任务状态。"""
        return self._status

    def _set_status(self, status: str):
        """
        更新任务状态并触发回调。

        Args:
            status: 新的状态值
        """
        self._status = status
        if self._on_status_change:
            try:
                self._on_status_change(status)
            except Exception:
                # 回调异常不应影响任务运行
                pass

    def start(self, config: BrowserConfig):
        """
        在新线程中启动任务。

        如果当前已有任务在运行，会先记录警告并拒绝启动。

        Args:
            config: BrowserConfig 浏览器配置
        """
        if self.is_running:
            self._logger.warning("任务已在运行中，请先停止当前任务")
            return

        # 重置停止信号
        self._stop_event.clear()
        self._browser = None

        # 创建并启动工作线程
        self._thread = threading.Thread(
            target=self._run,
            args=(config,),
            name="TaskRunner-Worker",
            daemon=True,  # 守护线程，主进程退出时自动终止
        )
        self._thread.start()
        self._logger.info("任务线程已启动")

    def stop(self):
        """
        发送停止信号，请求任务停止。

        设置 _stop_event，工作线程会在下一次循环检查时检测到并执行清理。
        此方法立即返回，不等待线程结束。
        """
        if not self.is_running:
            self._logger.warning("没有正在运行的任务")
            return

        self._logger.info("收到停止请求，正在停止任务...")
        self._stop_event.set()

    def bind_invite_code(self, code: str):
        """将绑定邀请码任务推入队列"""
        if not self.is_running:
            self._logger.error("请先启动任务，再填写邀请码。")
            return
        self._action_queue.put(('bind_invite', (code,)))

    def read_email(self):
        """将读取邮件任务推入队列"""
        if not self.is_running:
            self._logger.error("请先启动任务，再读取邮件。")
            return
        self._action_queue.put(('read_email', ()))

    def create_apikey(self):
        """将创建 API Key 任务推入队列"""
        if not self.is_running:
            self._logger.error("请先启动任务，再创建 API Key。")
            return
        self._action_queue.put(('create_apikey', ()))

    def _execute_automation(self, page, config: BrowserConfig):
        """执行页面自动化操作"""
        try:
            self._logger.info("等待页面加载...")
            page.wait_for_load_state("networkidle", timeout=60000)
            
            self._logger.info("点击注册选项卡...")
            page.click("#rc-tabs-0-tab-register", timeout=15000)
            
            country_box_sel = "#rc-tabs-0-panel-register > form > div.mi-select-field.mi-select-field--with-label.mi-form-field.mi-form-field--fullwidth.mi-form-field--bordered > div > div > div > div > span.ant-select-selection-item"
            # 等待国家选择框出现，针对使用代理网速较慢的情况放宽超时限制
            page.wait_for_selector(country_box_sel, state="visible", timeout=30000)
            
            self._logger.info("点击选择国家...")
            page.click(country_box_sel)
            
            self._logger.info("正在随机抽取国家并搜索...")
            
            # 预定义主流国家列表 (混合中英文以应对不同语言环境)
            country_list = [
                "United States", "United Kingdom", "Canada", "Australia", 
                "Germany", "France", "Japan", "South Korea", "Brazil", 
                "India", "Indonesia", "Mexico", "Spain", "Italy", "Netherlands",
                "Sweden", "Switzerland", "Singapore", "New Zealand", "Norway"
            ]
            import random
            random_country = random.choice(country_list)
            self._logger.info(f"随机选择了国家: {random_country}")
            
            search_input_selector = ".mi-region-field__search input"
            # 等待搜索框真正可见
            page.wait_for_selector(search_input_selector, state="visible", timeout=15000)
            
            page.click(search_input_selector)
            # 使用 type 并带有延迟，能更好地触发前端 React 的 onChange 状态更新
            page.locator(search_input_selector).type(random_country, delay=100)
            
            # 稍微等待下拉列表过滤渲染
            time.sleep(1)
            page.keyboard.press("Enter")
            
            # 等待国家下拉框消失，代表选择完成，替代硬性的 time.sleep(2)
            try:
                page.wait_for_selector(".ant-select-dropdown", state="hidden", timeout=5000)
            except:
                pass # 忽略错误，如果瞬间消失捕捉不到也没关系
            
            email_sel = "#rc-tabs-0-panel-register > form > div._-src-portals-desktop-pages-Register-Email-marginTop20.mi-text-field.mi-text-field--with-label.mi-form-field.mi-form-field--bordered > div > div > div > input"
            # 等待邮箱输入框变成可操作状态
            page.wait_for_selector(email_sel, state="visible", timeout=5000)
            
            if config.target_email:
                import string, random
                # 生成 8-16位随机密码（数字+字母组合）
                pw_len = random.randint(8, 16)
                chars = string.ascii_letters + string.digits
                password_list = [random.choice(string.ascii_letters), random.choice(string.digits)]
                password_list += [random.choice(chars) for _ in range(pw_len - 2)]
                random.shuffle(password_list)
                config.target_password = ''.join(password_list)

                self._logger.info(f"👉 当前任务邮箱: {config.target_email}")
                self._logger.info(f"👉 当前生成密码: {config.target_password}")

                def js_assign(selector, value):
                    # 通过原生 setter 绕过 React 绑定并触发事件
                    js_code = f"""() => {{
                        const el = document.querySelector('{selector}');
                        if (el) {{
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(el, '{value}');
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}"""
                    page.evaluate(js_code)

                self._logger.info("输入邮箱...")
                # 之前已经在上面定义了 email_sel，并且等它 visible 了
                js_assign(email_sel, config.target_email)
                
                self._logger.info("输入密码...")
                pw1_sel = "#rc-tabs-0-panel-register > form > div:nth-child(3) > div > div.mi-form-field__control > div > input"
                # page.click(pw1_sel)
                # page.keyboard.insert_text(config.target_password)
                js_assign(pw1_sel, config.target_password)
                
                self._logger.info("确认密码...")
                pw2_sel = "#rc-tabs-0-panel-register > form > div:nth-child(4) > div > div.mi-form-field__control > div > input"
                # page.click(pw2_sel)
                # page.keyboard.insert_text(config.target_password)
                js_assign(pw2_sel, config.target_password)
            else:
                self._logger.warning("未配置邮箱池，跳过账号密码填写。")
            
            self._logger.info("点击同意协议...")
            page.click("#rc-tabs-0-panel-register > form > div.mi-accept-terms > label > span.ant-checkbox > input", force=True)
            
            self._logger.info("等待并点击下一步...")
            # Playwright 原生的 click 会自带 actionability 检查（等待可见、可用、未被遮挡），替代 fixed sleep
            page.click("#rc-tabs-0-panel-register > form > button")
            
            # 尝试接管极验验证码
            from core.captcha import solve_geetest_slider
            
            geetest_retry = 0
            max_geetest_retry = 3
            
            solve_geetest_slider(page, self._logger)
            self._logger.success("极验探测结束，等待页面状态响应...")
            
            # 轮询检查后续状态 (等待极验飞一会或者等待网络响应)
            self._recaptcha_warned = False
            for _ in range(180): # 放宽到180次，留出充足时间给可能的人工接管
                # 检查是否出现邮箱错误（被注册或格式错误）
                if page.locator("#mi-form-error-email").is_visible():
                    self._logger.error("该邮箱已注册或无效！")
                    self._handle_automation_failure()
                    return
                    
                # 检查是否出现 Google reCAPTCHA
                if page.locator('iframe[src*="recaptcha"]').is_visible() or page.locator('iframe[title*="reCAPTCHA"]').is_visible():
                    if not self._recaptcha_warned:
                        self._logger.warning("🚨 触发高风控：检测到 Google reCAPTCHA (人机身份验证)！")
                        self._logger.warning("👉 请立即在浏览器上手动完成拼图/选图验证。程序将暂停等待你操作...")
                        self._recaptcha_warned = True
                    # 这里不用 break，继续循环等用户完成验证，完成后页面会自动跳转到验证码输入页
                    
                # 检查极验是否失败需要重试
                error_panel = page.locator("div.geetest_panel_error_content")
                if error_panel.is_visible():
                    geetest_retry += 1
                    if geetest_retry > max_geetest_retry:
                        self._logger.error("极验滑块重试次数达到上限，放弃！")
                        self._handle_automation_failure()
                        return
                    self._logger.warning(f"检测到极验滑动失败，准备第 {geetest_retry} 次重试...")
                    error_panel.click(force=True)
                    time.sleep(2) # 等待新图加载
                    solve_geetest_slider(page, self._logger)
                    self._logger.success("极验重试探测结束，等待响应...")
                    continue

                # 检查是否成功跳转到“输入邮件验证码”的页面
                # 使用更加稳固的 class 组合选择器，而不是依赖可能被框架伪装的 placeholder 属性
                verify_input = page.locator('.mi-ticket-field input').first
                if verify_input.is_visible():
                    self._logger.success("已成功跳转到验证码输入页面！开始读取邮件...")
                    
                    # 轮询读取邮件（最多尝试 10 次，每次间隔 3 秒，防止部分邮箱服务延迟严重）
                    cfg = config
                    from core.email_reader import read_latest_verification_code
                    import re
                    
                    found_code = None
                    for __ in range(10):
                        time.sleep(3)
                        self._logger.info("正在查收邮件...")
                        res = read_latest_verification_code(cfg.target_email, cfg.email_client_id, cfg.email_refresh_token, self._logger)
                        if "验证码：" in res:
                            match = re.search(r'\d{6}', res)
                            if match:
                                found_code = match.group()
                                break
                    
                    if found_code:
                        self._logger.success(f"自动填入验证码: {found_code}")
                        
                        def js_assign_local(selector, value):
                            js_code = f"""() => {{
                                const el = document.querySelector('{selector}');
                                if (el) {{
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    setter.call(el, '{value}');
                                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }}
                            }}"""
                            page.evaluate(js_code)
                            
                        js_assign_local('.mi-ticket-field input', found_code)
                        time.sleep(0.5)
                        self._logger.info("点击提交验证码...")
                        page.click("#rc-tabs-0-panel-register > form > button")
                        
                        # ================= 新增流程：后续协议与创建 API Key =================
                        self._logger.info("等待跳转进入控制台...")
                        try:
                            # 监控是否成功跳入了主控制台界面
                            page.wait_for_url("**/console/**", timeout=15000)
                            self._logger.success("注册成功！已进入主控制台。")
                            
                            # 查找并勾选“同意协议”复选框
                            agree_checkbox = page.locator("input[type='checkbox'].ant-checkbox-input")
                            if agree_checkbox.is_visible(timeout=5000):
                                self._logger.info("勾选使用协议...")
                                agree_checkbox.click(force=True)
                                
                                # 点击确定按钮
                                confirm_btn = page.locator("button.flex-1.max-w-\\[50\\%\\].bg-\\[var\\(--color-primary\\)\\]")
                                if confirm_btn.is_visible(timeout=2000):
                                    self._logger.info("点击确定按钮...")
                                    confirm_btn.click()
                                    time.sleep(1) # 等待弹窗消失
                            
                            # 填写邀请码并触发 _do_create_apikey 进行全自动收尾
                            self._logger.info("开始执行全自动 API Key 创建闭环...")
                            
                            # 1. 填写邀请码 (如果有)
                            if config.invite_code:
                                self._do_bind_invite(config.invite_code)
                                time.sleep(1)
                                
                            # 2. 创建 API Key
                            self._do_create_apikey()
                            
                            # 剔除已使用的邮箱 (触发回调刷新界面)
                            if self._on_bind_success:
                                self._logger.info("正在将当前邮箱移出队列...")
                                self._on_bind_success()
                                
                            self._logger.success("本轮账号自动化流程已彻底完结！准备执行下一轮任务。")
                            
                            # ======= 核心循环：关闭当前浏览器并停止本线程，通知 GUI 开启下一个任务 =======
                            self.stop()
                            return
                            
                        except Exception as e:
                            self._logger.error(f"后续流程执行失败或超时未跳转: {e}")
                            self._handle_automation_failure()
                            return
                            
                    else:
                        self._logger.error("多次尝试后未能读取到验证码邮件！")
                        self._handle_automation_failure()
                        return
                    break
                    
                time.sleep(1)
            
        except Exception as e:
            self._logger.error(f"自动化操作失败: {e}", exc_info=True)
            self._handle_automation_failure()

    def _handle_automation_failure(self):
        """处理自动化流程中的失败情况，将其移入失败池并终止当前任务"""
        if self._on_task_fail:
            self._logger.info("正在将当前失败的邮箱移入失败池...")
            self._on_task_fail()
        self.stop()

    def _do_bind_invite(self, code: str):
        try:
            import urllib.parse
            
            # 动态获取 api-platform_ph
            api_platform_ph = ""
            cookies = self._page.context.cookies()
            for cookie in cookies:
                if cookie['name'] == 'api-platform_ph':
                    val = cookie['value']
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]
                    api_platform_ph = urllib.parse.quote(val, safe="")
                    break
            
            if not api_platform_ph:
                self._logger.warning("未在 Cookie 中找到 api-platform_ph，将使用上次的固定值尝试")
                api_platform_ph = "uXh47o%2BU3j4bRTqwPtgSZg%3D%3D"
                
            url = f"https://platform.xiaomimimo.com/api/v1/invitation/bind?api-platform_ph={api_platform_ph}"
            
            self._logger.info(f"正在发送邀请码绑定请求: {code}")
            
            resp = self._page.context.request.post(
                url,
                headers={
                    "origin": "https://platform.xiaomimimo.com",
                    "referer": "https://platform.xiaomimimo.com/console/api-keys",
                    "x-timezone": "Asia/Shanghai",
                    "content-type": "application/json",
                    "accept": "*/*",
                    "accept-language": "zh"
                },
                data={"inviteCode": code}
            )
            
            body = resp.text()
            self._logger.success(f"绑定请求响应: {resp.status} {body}")
            if resp.status == 200 and self._on_bind_success:
                self._on_bind_success()
        except Exception as e:
            self._logger.error(f"绑定邀请码失败: {e}", exc_info=True)

    def _do_read_email(self):
        from core.email_reader import read_latest_verification_code
        cfg = self._current_config
        read_latest_verification_code(cfg.target_email, cfg.email_client_id, cfg.email_refresh_token, self._logger)

    def _do_create_apikey(self):
        try:
            import urllib.parse
            
            # 动态获取 api-platform_ph
            api_platform_ph = ""
            cookies = self._page.context.cookies()
            for cookie in cookies:
                if cookie['name'] == 'api-platform_ph':
                    val = cookie['value']
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]
                    api_platform_ph = urllib.parse.quote(val, safe="")
                    break
            
            if not api_platform_ph:
                self._logger.warning("未在 Cookie 中找到 api-platform_ph，将使用备用值尝试")
                api_platform_ph = "uXh47o%2BU3j4bRTqwPtgSZg%3D%3D"
                
            url = f"https://platform.xiaomimimo.com/api/v1/apiKeys?api-platform_ph={api_platform_ph}"
            email = self._current_config.target_email or "UnknownEmail"
            self._logger.info(f"正在发送创建 API Key 请求，名称为: {email}")
            
            resp = self._page.context.request.post(
                url,
                headers={
                    "origin": "https://platform.xiaomimimo.com",
                    "referer": "https://platform.xiaomimimo.com/console/api-keys",
                    "x-timezone": "Asia/Shanghai",
                    "content-type": "application/json",
                    "accept": "*/*",
                    "accept-language": "zh"
                },
                data={"apiKeyName": email}
            )
            
            body = resp.text()
            if resp.ok:
                resp_json = resp.json()
                self._logger.success(f"API Key 创建成功: {body}")
                
                # 提取 apiKey 并保存到 成功.txt
                api_key = resp_json.get("data", {}).get("apiKey", "")
                if api_key:
                    with open("成功.txt", "a", encoding="utf-8") as f:
                        f.write(f"{email}----{self._current_config.target_password}----{api_key}\n")
                    self._logger.success(f"已将结果保存到 成功.txt")
                else:
                    self._logger.warning("未能从响应中提取出 apiKey")
            else:
                self._logger.error(f"API Key 创建失败，状态码: {resp.status}，响应: {body}")
        except Exception as e:
            self._logger.error(f"创建 API Key 异常: {e}", exc_info=True)

    def _run(self, config: BrowserConfig):
        """
        内部工作方法：在线程中执行的实际任务逻辑。
        """
        try:
            # ---- 阶段1: 代理验证 ----
            if config.proxy:
                self._set_status(self.STATUS_VALIDATING_PROXY)
                self._logger.info(f"正在验证代理: {config.proxy}")

                success, message = validate_proxy(config.proxy)
                if success:
                    self._logger.success(f"代理验证通过: {message}")
                else:
                    self._logger.error(f"代理验证失败: {message}")
                    self._logger.warning("代理验证失败，但仍尝试继续启动浏览器...")

                # 检查是否收到停止信号
                if self._stop_event.is_set():
                    self._set_status(self.STATUS_STOPPED)
                    self._logger.info("任务在代理验证后被停止")
                    return

            # ---- 阶段2: 启动浏览器 ----
            self._set_status(self.STATUS_LAUNCHING_BROWSER)
            self._logger.info("正在启动浏览器...")

            browser, page = launch_browser(config, self._logger)

            if browser is None:
                self._logger.error("浏览器启动失败，任务终止")
                self._set_status(self.STATUS_ERROR)
                return

            self._browser = browser
            self._page = page
            self._current_config = config
            
            # 自动化操作
            self._execute_automation(self._page, self._current_config)

            # 检查是否收到停止信号
            if self._stop_event.is_set():
                self._set_status(self.STATUS_STOPPED)
                self._logger.info("任务在浏览器启动后被停止")
                close_browser(self._browser, self._logger)
                self._browser = None
                return

            # ---- 阶段3: 运行中 - 倒计时循环 ----
            self._set_status(self.STATUS_RUNNING)
            timeout_seconds = config.timeout_minutes * 60
            self._logger.info(f"任务开始运行，超时时间: {config.timeout_minutes} 分钟")

            start_time = time.time()

            while True:
                elapsed = time.time() - start_time
                remaining = max(0, int(timeout_seconds - elapsed))

                # 推送倒计时更新
                if self._on_countdown:
                    try:
                        self._on_countdown(remaining)
                    except Exception:
                        pass

                # 检查超时
                if elapsed >= timeout_seconds:
                    self._logger.warning(
                        f"任务已超时（{config.timeout_minutes} 分钟），正在关闭浏览器..."
                    )
                    self._set_status(self.STATUS_TIMEOUT)
                    close_browser(self._browser, self._logger)
                    self._browser = None
                    return

                # 检查停止信号
                if self._stop_event.is_set():
                    self._logger.info("收到停止信号，正在关闭浏览器...")
                    self._set_status(self.STATUS_STOPPED)
                    close_browser(self._browser, self._logger)
                    self._browser = None
                    return

                # 检查队列中的操作
                while not self._action_queue.empty():
                    action, args = self._action_queue.get()
                    if action == 'bind_invite':
                        self._do_bind_invite(*args)
                    elif action == 'read_email':
                        self._do_read_email()
                    elif action == 'create_apikey':
                        self._do_create_apikey()

                # 每秒检查一次
                time.sleep(1)

        except Exception as e:
            # 全局异常兜底：捕获所有未预期的异常
            self._logger.error(
                f"任务执行过程中发生未预期的异常: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            self._set_status(self.STATUS_ERROR)

            # 确保浏览器被关闭
            if self._browser:
                try:
                    close_browser(self._browser, self._logger)
                except Exception:
                    pass
                self._browser = None

        finally:
            # 最终清理：确保状态不会停留在中间态
            if self._status in (
                self.STATUS_VALIDATING_PROXY,
                self.STATUS_LAUNCHING_BROWSER,
                self.STATUS_RUNNING,
            ):
                # 如果状态还在运行中间态，说明发生了异常退出
                self._set_status(self.STATUS_ERROR)
            self._logger.info(f"任务线程结束，最终状态: {self._status}")
