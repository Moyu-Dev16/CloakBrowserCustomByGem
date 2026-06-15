import os
import configparser

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')

def load_config() -> dict:
    """加载配置文件，返回字典形式的配置项"""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')
    
    settings = {}
    if 'Settings' in config:
        sec = config['Settings']
        settings['stealth_mode'] = sec.getboolean('stealth_mode', fallback=True)
        settings['proxy_mode'] = sec.get('proxy_mode', fallback='无代理')
        settings['proxy_pool'] = sec.get('proxy_pool', fallback='').replace('|#|', '\n')
        settings['rotating_proxy'] = sec.get('rotating_proxy', fallback='')
        settings['proxy_api_url'] = sec.get('proxy_api_url', fallback='')
        settings['target_url'] = sec.get('target_url', fallback='https://global.account.xiaomi.com/')
        settings['timeout_minutes'] = sec.getint('timeout_minutes', fallback=30)
        settings['email_pool'] = sec.get('email_pool', fallback='').replace('|#|', '\n')
        settings['sync_proxy_locale'] = sec.getboolean('sync_proxy_locale', fallback=False)
        settings['sync_proxy_timezone'] = sec.getboolean('sync_proxy_timezone', fallback=False)
        settings['sync_proxy_geolocation'] = sec.getboolean('sync_proxy_geolocation', fallback=False)
    else:
        # 默认值
        settings = {
            'stealth_mode': True,
            'proxy_mode': '无代理',
            'proxy_pool': '',
            'rotating_proxy': '',
            'proxy_api_url': '',
            'target_url': 'https://global.account.xiaomi.com/',
            'timeout_minutes': 30,
            'email_pool': '',
            'sync_proxy_locale': False,
            'sync_proxy_timezone': False,
            'sync_proxy_geolocation': False
        }
    return settings

def save_config(settings: dict):
    """保存配置到文件"""
    config = configparser.ConfigParser()
    config['Settings'] = {}
    sec = config['Settings']
    
    sec['stealth_mode'] = str(settings.get('stealth_mode', True))
    sec['proxy_mode'] = settings.get('proxy_mode', '无代理')
    sec['proxy_pool'] = settings.get('proxy_pool', '').replace('\n', '|#|')
    sec['rotating_proxy'] = settings.get('rotating_proxy', '')
    sec['proxy_api_url'] = settings.get('proxy_api_url', '')
    sec['target_url'] = settings.get('target_url', 'https://global.account.xiaomi.com/')
    sec['timeout_minutes'] = str(settings.get('timeout_minutes', 30))
    sec['email_pool'] = settings.get('email_pool', '').replace('\n', '|#|')
    sec['sync_proxy_locale'] = str(settings.get('sync_proxy_locale', False))
    sec['sync_proxy_timezone'] = str(settings.get('sync_proxy_timezone', False))
    sec['sync_proxy_geolocation'] = str(settings.get('sync_proxy_geolocation', False))
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)
