"""
代理管理器 - 验证、选取、模式切换
支持 HTTP/HTTPS/SOCKS5 代理
"""
import random
import requests
from typing import Optional, List, Tuple
from urllib.parse import urlparse

# 代理模式定义
PROXY_MODES = {
    'none': '无代理',
    'pool': '代理池',
    'rotating': '轮转代理',
    'api': 'API提取',
}

# 用于验证代理连通性的测试URL
_TEST_URL = "https://httpbin.org/ip"


def validate_proxy(proxy_url: str, timeout: int = 10) -> Tuple[bool, str]:
    """
    验证代理是否可用。

    通过代理访问 httpbin.org/ip 来测试连通性。
    支持 HTTP、HTTPS 和 SOCKS5 代理。

    Args:
        proxy_url: 代理URL，格式如:
            - http://host:port
            - http://user:pass@host:port
            - socks5://host:port
            - socks5://user:pass@host:port
        timeout: 超时时间（秒），默认10秒

    Returns:
        (success, message) 元组:
            - success: 代理是否可用
            - message: 成功时返回外部IP信息，失败时返回错误原因
    """
    if not proxy_url or not proxy_url.strip():
        return False, "代理地址为空"

    proxy_url = proxy_url.strip()

    try:
        # 构建代理字典
        proxies = build_requests_proxies(proxy_url)

        # 发送测试请求
        response = requests.get(
            _TEST_URL,
            proxies=proxies,
            timeout=timeout,
            verify=False,  # 部分代理可能没有有效证书
        )

        if response.status_code == 200:
            # 尝试解析返回的IP信息
            try:
                ip_info = response.json()
                origin_ip = ip_info.get('origin', '未知')
                return True, f"代理可用，出口IP: {origin_ip}"
            except (ValueError, KeyError):
                return True, "代理可用（无法解析IP信息）"
        else:
            return False, f"代理返回异常状态码: {response.status_code}"

    except requests.exceptions.ProxyError as e:
        return False, f"代理连接失败: {str(e)}"
    except requests.exceptions.ConnectTimeout:
        return False, f"代理连接超时（{timeout}秒）"
    except requests.exceptions.ReadTimeout:
        return False, f"代理读取超时（{timeout}秒）"
    except requests.exceptions.ConnectionError as e:
        return False, f"网络连接错误: {str(e)}"
    except ImportError:
        # PySocks 未安装时 SOCKS 代理会报 ImportError
        return False, "SOCKS5代理需要安装 PySocks 库: pip install pysocks"
    except Exception as e:
        return False, f"验证失败: {type(e).__name__}: {str(e)}"


def parse_proxy_list(text: str) -> List[str]:
    """
    解析多行文本为代理URL列表。

    每行一个代理地址，自动去除首尾空白字符，跳过空行和注释行（以#开头）。

    Args:
        text: 多行代理文本，格式示例:
            http://proxy1:8080
            http://user:pass@proxy2:8080
            socks5://proxy3:1080
            # 这是注释行

    Returns:
        有效代理URL列表
    """
    if not text:
        return []

    proxies = []
    for line in text.strip().splitlines():
        line = line.strip()
        # 跳过空行和注释行
        if not line or line.startswith('#'):
            continue
        proxies.append(line)

    return proxies


def get_proxy(
    mode: str,
    proxy_list: List[str] = None,
    rotating_proxy: str = None,
    api_url: str = None
) -> Optional[str]:
    """
    根据代理模式获取代理URL。

    Args:
        mode: 代理模式，可选值:
            - 'none': 不使用代理
            - 'pool': 从代理池中随机选取一个
            - 'rotating': 使用固定的轮转代理地址
            - 'api': 从提供的 API 地址获取代理
        proxy_list: 代理池列表（mode='pool' 时需要）
        rotating_proxy: 轮转代理地址（mode='rotating' 时需要）
        api_url: 代理 API 地址（mode='api' 时需要）

    Returns:
        代理URL字符串，或 None（不使用代理时）
    """
    if mode == 'none':
        return None

    elif mode == 'pool':
        if not proxy_list:
            return None
        return random.choice(proxy_list)

    elif mode == 'rotating':
        if not rotating_proxy or not rotating_proxy.strip():
            return None
        return rotating_proxy.strip()

    elif mode == 'api':
        if not api_url or not api_url.strip():
            return None
        try:
            resp = requests.get(api_url.strip(), timeout=10)
            if resp.status_code == 200:
                proxy_text = resp.text.strip()
                # 假设 API 返回的格式是 ip:port，或者有多行选第一行
                first_line = proxy_text.splitlines()[0].strip()
                if first_line:
                    # 如果没有协议头，默认加上 http://
                    if '://' not in first_line:
                        first_line = f"http://{first_line}"
                    return first_line
            else:
                import logging
                logging.getLogger(__name__).warning(
                    "代理API返回非200状态码: %d, URL: %s", resp.status_code, api_url.strip()
                )
        except requests.exceptions.Timeout:
            import logging
            logging.getLogger(__name__).warning("代理API请求超时: %s", api_url.strip())
        except requests.exceptions.ConnectionError as e:
            import logging
            logging.getLogger(__name__).warning("代理API连接失败: %s, 错误: %s", api_url.strip(), e)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("代理API请求异常: %s: %s", type(e).__name__, e)
        return None

    else:
        # 未知模式，不使用代理
        return None


def build_requests_proxies(proxy_url: str) -> dict:
    """
    根据代理URL构建 requests 库所需的 proxies 字典。

    支持的代理协议:
    - http:// → 用于 HTTP 和 HTTPS 请求
    - https:// → 用于 HTTP 和 HTTPS 请求
    - socks5:// → 用于 HTTP 和 HTTPS 请求（需要 PySocks 库）
    - socks5h:// → 同 socks5，但DNS通过代理解析

    Args:
        proxy_url: 代理URL

    Returns:
        requests 库的 proxies 参数字典，格式如:
        {'http': 'http://proxy:8080', 'https': 'http://proxy:8080'}
    """
    if not proxy_url:
        return {}

    proxy_url = proxy_url.strip()

    # 解析协议类型
    parsed = urlparse(proxy_url)
    scheme = parsed.scheme.lower()

    if scheme in ('socks5', 'socks5h'):
        # SOCKS5 代理同时代理 HTTP 和 HTTPS 流量
        return {
            'http': proxy_url,
            'https': proxy_url,
        }
    elif scheme in ('http', 'https'):
        # HTTP/HTTPS 代理同时代理 HTTP 和 HTTPS 流量
        return {
            'http': proxy_url,
            'https': proxy_url,
        }
    else:
        # 未知协议，尝试作为 HTTP 代理使用
        fallback_url = f"http://{proxy_url}" if '://' not in proxy_url else proxy_url
        return {
            'http': fallback_url,
            'https': fallback_url,
        }
