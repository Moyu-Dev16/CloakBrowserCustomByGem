import re
import requests

import html

def strip_html(text: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", str(text or ""))
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", html.unescape(cleaned)).strip()

def get_access_token(client_id: str, refresh_token: str) -> str:
    """使用 refresh_token 向 Microsoft OAuth2 端点换取 access_token"""
    url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    # Outlook Management Local APP 的全局 Secret
    client_secret = "6Xr8Q~RAjun4jdToFAR7uB_GKXcL0sRw0MNa2cNP"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": "offline_access User.Read Mail.Read"
    }
    
    resp = requests.post(url, data=data, timeout=15)
    if not resp.ok:
        print("TOKEN ERROR:", resp.text)
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
        # 使用更稳健的遍历文件夹抓取方式，防止验证码落入垃圾邮件(Junk)未被查出
        def graph_get(access_token: str, url: str, params: dict = None) -> dict:
            resp = requests.get(url, params=params, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
            resp.raise_for_status()
            return resp.json()

        def fetch_graph_mail_folders(access_token: str) -> list:
            folders = []
            def walk(url: str):
                next_url = url
                while next_url:
                    payload = graph_get(access_token, next_url, params={"$top": "100", "$select": "id"})
                    for folder in payload.get("value", []):
                        folders.append(folder)
                        folder_id = folder.get("id")
                        if folder_id:
                            walk(f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/childFolders")
                    next_url = payload.get("@odata.nextLink")
            walk("https://graph.microsoft.com/v1.0/me/mailFolders")
            return folders

        messages = []
        folders = fetch_graph_mail_folders(access_token)
        for folder in folders:
            folder_id = folder.get("id")
            if not folder_id: continue
            # 过滤发件人并排序
            params = {
                "$filter": "from/emailAddress/address eq 'noreply@notice.xiaomi.com'",
                "$orderby": "receivedDateTime desc",
                "$top": 1,
                "$select": "subject,bodyPreview,body,receivedDateTime"
            }
            try:
                payload = graph_get(access_token, f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/messages", params={"$top": 5, "$select": "subject,from,receivedDateTime,bodyPreview,body"})
                for m in payload.get("value", []):
                    sender = m.get('from', {}).get('emailAddress', {}).get('address', '')
                    if logger:
                        logger.info(f"发现邮件: {sender} | {m.get('subject')}")
                    if sender == 'noreply@notice.xiaomi.com' or 'xiaomi.com' in sender:
                        messages.append(m)
            except Exception:
                continue

        if not messages:
            if logger:
                logger.warning("所有文件夹中均没有收到小米的验证邮件")
            return "没有邮件"
            
        # 按照 receivedDateTime 降序排序，取最新的一封
        messages.sort(key=lambda x: str(x.get("receivedDateTime") or ""), reverse=True)
        msg = messages[0]
        raw_body = msg.get('body', {}).get('content', '')
        content = strip_html(raw_body) + " " + msg.get('bodyPreview', '')
        
        # 提取 6位数字验证码
        match = re.search(r'\b\d{6}\b', content)
        if match:
            code = match.group()
            if logger:
                logger.success(f"成功提取验证码：{code}")
            return f"验证码：{code}"
        else:
            if logger:
                logger.warning("最新邮件中未找到6位数字验证码")
                logger.info(f"邮件内容预览: {content[:200]}")
            return "未找到验证码"
            
    except Exception as e:
        if logger:
            logger.error(f"读取邮件失败: {e}")
        return f"读取失败: {e}"
