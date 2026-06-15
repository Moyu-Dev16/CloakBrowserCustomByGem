import re
import requests

def get_access_token(client_id: str, refresh_token: str) -> str:
    """使用 refresh_token 向 Microsoft OAuth2 端点换取 access_token"""
    url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    
    resp = requests.post(url, data=data, timeout=15)
    resp.raise_for_status()
    return resp.json().get('access_token')

def read_latest_verification_code(email: str, client_id: str, refresh_token: str, logger=None) -> str:
    """读取最新的由 noreply@notice.xiaomi.com 发送的邮件并提取6位验证码"""
    if not email or not client_id or not refresh_token:
        raise ValueError("邮箱、Client ID 或 Refresh Token 缺失")

    try:
        if logger:
            logger.info("正在获取 Graph API 访问令牌...")
        access_token = get_access_token(client_id, refresh_token)
    except Exception as e:
        if logger:
            logger.error(f"获取 Access Token 失败: {e}")
        return "获取Token失败"

    try:
        if logger:
            logger.info("正在查询最新邮件...")
        # 查询 Graph API
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        # 筛选条件：发件人为 noreply@notice.xiaomi.com，按收件时间降序，只取1条
        endpoint = "https://graph.microsoft.com/v1.0/me/messages"
        params = {
            "$filter": "from/emailAddress/address eq 'noreply@notice.xiaomi.com'",
            "$orderby": "receivedDateTime desc",
            "$top": 1,
            "$select": "subject,bodyPreview,body"
        }
        
        resp = requests.get(endpoint, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        messages = resp.json().get('value', [])
        
        if not messages:
            if logger:
                logger.warning("没有邮件")
            return "没有邮件"
            
        msg = messages[0]
        content = msg.get('body', {}).get('content', '') + msg.get('bodyPreview', '')
        
        # 提取 6位数字验证码
        match = re.search(r'\b\d{6}\b', content)
        if match:
            code = match.group()
            if logger:
                logger.success(f"验证码：{code}")
            return f"验证码：{code}"
        else:
            if logger:
                logger.warning("最新邮件中未找到6位数字验证码")
            return "未找到验证码"
            
    except Exception as e:
        if logger:
            logger.error(f"读取邮件失败: {e}")
        return f"读取失败: {e}"
