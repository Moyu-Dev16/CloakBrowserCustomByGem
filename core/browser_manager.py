"""
CloakBrowser 管理器 - 启动/关闭/配置

负责:
- 定义浏览器启动配置（BrowserConfig）
- 启动 CloakBrowser 实例并导航到目标页面
- 安全关闭浏览器实例
"""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class BrowserConfig:
    """
    浏览器启动配置。

    Attributes:
        target_url: 目标页面URL，默认为小米全球账号注册页面
        proxy: 代理URL，None 表示不使用代理
        stealth_mode: 隐身模式，启用时 headless=False 且 humanize=True
        timeout_minutes: 任务超时时间（分钟），超时后自动关闭浏览器
    """
    target_url: str = 'https://global.account.xiaomi.com/'
    proxy: Optional[str] = None
    stealth_mode: bool = True
    timeout_minutes: int = 30
    target_email: Optional[str] = None
    target_password: Optional[str] = None
    email_client_id: Optional[str] = None
    email_refresh_token: Optional[str] = None
    invite_code: Optional[str] = None


def launch_browser(config: BrowserConfig, logger=None) -> Tuple:
    """
    启动 CloakBrowser 并导航到目标页面。

    使用 cloakbrowser 库启动浏览器实例，配置代理、隐身模式等参数，
    然后创建新页面并导航到目标URL。

    Args:
        config: BrowserConfig 浏览器配置实例
        logger: TaskLogger 实例，用于记录日志（可选）

    Returns:
        (browser, page) 元组:
            - 成功时: (browser_instance, page_instance)
            - 失败时: (None, None)
    """
    browser = None
    page = None

    if logger:
        logger.info(f"正在启动 CloakBrowser...")
        logger.info(f"目标URL: {config.target_url}")
        if config.proxy:
            logger.info(f"使用代理: {config.proxy}")
        else:
            logger.info("未使用代理（直连模式）")
        logger.info(f"隐身模式: {'开启' if config.stealth_mode else '关闭'}")

    try:
        from cloakbrowser import launch
    except ImportError:
        if logger:
            logger.error("cloakbrowser 库未安装，请确认已正确安装该依赖", exc_info=True)
        return (None, None)

    try:
        # 启动浏览器
        # - proxy: 代理地址
        # - headless: 隐身模式下使用有头浏览器 (False)
        # - humanize: 隐身模式下启用人类行为模拟
        # - geoip: 使用代理时启用 GeoIP 匹配（使浏览器指纹与代理IP地理位置一致）
        browser = launch(
            proxy=config.proxy,
            headless=False,
            humanize=config.stealth_mode,
            geoip=True if config.proxy else False,
        )

        if logger:
            logger.info("CloakBrowser 启动成功")

        # 创建新页面
        page = browser.new_page()
        if logger:
            logger.info("新页面已创建")

        # 导航到目标URL，设置 60 秒超时（轮转代理可能较慢）
        page.goto(config.target_url, timeout=60000)
        if logger:
            logger.success(f"已导航到: {config.target_url}")

    except Exception as e:
        if logger:
            # 特别处理 geoip 依赖缺失的情况
            if isinstance(e, ImportError) and 'geoip2' in str(e):
                logger.error("启用代理的 GeoIP 匹配需要 geoip2 库。请执行: pip install cloakbrowser[geoip]")
            else:
                logger.error(f"启动浏览器失败: {type(e).__name__}: {str(e)}", exc_info=True)
        # 如果浏览器已启动但页面创建失败，尝试关闭浏览器
        if browser and not page:
            close_browser(browser, logger)
        return (None, None)

    return (browser, page)


def close_browser(browser, logger=None):
    """
    安全关闭浏览器实例。

    包装在 try/except 中，确保不会因为关闭操作而抛出未捕获异常。

    Args:
        browser: CloakBrowser 浏览器实例
        logger: TaskLogger 实例，用于记录日志（可选）
    """
    if browser is None:
        if logger:
            logger.warning("浏览器实例为 None，无需关闭")
        return

    try:
        if logger:
            logger.info("正在关闭浏览器...")
        browser.close()
        if logger:
            logger.success("浏览器已安全关闭")
    except Exception as e:
        if logger:
            logger.error(f"关闭浏览器时出错: {type(e).__name__}: {str(e)}", exc_info=True)
