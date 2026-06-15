import time
import base64
import random
import math
import numpy as np
import cv2
from playwright.sync_api import Page
import logging

def _get_canvas_image(page: Page, selectors: list) -> np.ndarray:
    """尝试多个选择器，提取元素的截图并转换为 OpenCV 图像 (BGR)"""
    for sel in selectors:
        loc = page.locator(sel)
        if loc.count() > 0 and loc.first.is_visible():
            try:
                img_data = loc.first.screenshot(type="png", omit_background=True)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED) # 包含 Alpha 通道
                # 如果是带 Alpha 通道的，转换为 BGR，并将透明区域填黑（极验 slice 是这样的）
                if img is not None and img.shape[-1] == 4:
                    # 分离 Alpha
                    alpha = img[:, :, 3]
                    bgr = img[:, :, :3]
                    # 透明背景转黑
                    bgr[alpha == 0] = (0, 0, 0)
                    img = bgr
                return img
            except Exception as e:
                print(f"提取 {sel} 截图失败: {e}")
                
    # 如果截图失败，尝试原来的 canvas evaluate 方法
    for sel in selectors:
        script = f"""
        () => {{
            const canvas = document.querySelector('{sel}');
            if (!canvas || !canvas.toDataURL) return null;
            return canvas.toDataURL('image/png').substring(22);
        }}
        """
        try:
            b64_data = page.evaluate(script)
            if b64_data:
                img_data = base64.b64decode(b64_data)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    return img
        except Exception:
            pass
            
    return None

def _get_distance(bg_img: np.ndarray, slice_img: np.ndarray) -> int:
    """
    通过 OpenCV 计算缺口 X 轴坐标距离。
    兼容独立图片和“背景与滑块被截取在同一张图”的情况。
    """
    bg_gray = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY)
    slice_gray = cv2.cvtColor(slice_img, cv2.COLOR_BGR2GRAY)
    
    # 判断是否截取到了同一个包含了背景和滑块的父容器 (两张图完全一样)
    is_combined_image = False
    if bg_gray.shape == slice_gray.shape:
        # 如果尺寸一样，比较一下像素差异
        diff = cv2.absdiff(bg_gray, slice_gray)
        if cv2.countNonZero(diff) < 100: # 几乎没有差异
            is_combined_image = True
            
    if is_combined_image:
        # 滑块一定在图片的左侧 (x < 60)
        left_strip = bg_gray[:, :60]
        edges = cv2.Canny(left_strip, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = [c for c in contours if cv2.boundingRect(c)[2] > 20 and cv2.boundingRect(c)[3] > 20]
        if not valid_contours:
            return 0
            
        c = max(valid_contours, key=cv2.contourArea)
        sx, sy, sw, sh = cv2.boundingRect(c)
        
        # 裁剪出真实的滑块模板
        template_slice = bg_gray[sy:sy+sh, sx:sx+sw]
        y, h = sy, sh
        x, w = sx, sw
    else:
        # 原有的独立滑块提取逻辑
        _, thresh = cv2.threshold(slice_gray, 10, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return 0
            
        c = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)
        template_slice = slice_gray[y:y+h, x:x+w]

    # 用 Canny 边缘做模板匹配，排除颜色干扰
    bg_edges = cv2.Canny(bg_gray, 50, 150)
    slice_edges = cv2.Canny(template_slice, 50, 150)
    
    # 遮蔽左侧滑块初始位置，防止匹配到自己
    bg_edges[:, :x+w+10] = 0
    
    result = cv2.matchTemplate(bg_edges, slice_edges, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    # max_loc[0] 就是最佳匹配点的 X 坐标
    # 最终滑动的距离 = 目标X - 滑块初始X
    target_x = max_loc[0]
    distance = target_x - x
    
    # 防止匹配到滑块本身的初始位置 (通常目标位置在 x > 50)
    if distance < 30:
        # 尝试将左侧初始位置遮挡后再匹配
        bg_edges[:, :x+w+10] = 0
        result = cv2.matchTemplate(bg_edges, slice_edges, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(result)
        target_x = max_loc[0]
        distance = target_x - x
        
    return distance

def __ease_out_expo(sep):
    if sep == 1:
        return 1
    else:
        return 1 - math.pow(2, -10 * sep)

def _perform_bionic_drag(page: Page, start_x: float, start_y: float, distance: int):
    """
    真·丝滑分段拖动：完全抛弃 Python 内部的 for 循环与 timeout 等待，
    纯粹利用 Playwright 的 steps 参数在浏览器内核层进行插值渲染。
    完全杜绝跨进程 WebSocket 通信造成的时钟跳变和卡顿现象。
    """
    page.mouse.down()
    page.wait_for_timeout(random.randint(100, 200)) # 按下后停顿
    
    # 稍微超过目标距离，模拟人类滑过头
    overshoot = random.randint(10, 20)
    target_x = start_x + distance
    max_x = target_x + overshoot
    
    # 第一段：急速起步（跨越约 60% 的距离，仅用 15 步插值，平均速度极快）
    x1 = start_x + distance * random.uniform(0.6, 0.7)
    y1 = start_y + random.choice([-2, -1, 1, 2])
    page.mouse.move(x1, y1, steps=random.randint(15, 20))
    
    # 第二段：减速滑过头（跨越剩余距离 + overshoot，用 30 步插值，速度降为中等）
    y2 = start_y + random.choice([-1, 0, 1])
    page.mouse.move(max_x, y2, steps=random.randint(25, 35))
    
    # 第三段：缓慢回拨（往回走 overshoot 距离，用 25 步插值，速度极慢！）
    y3 = start_y + random.choice([-1, 0, 1])
    page.mouse.move(target_x, y3, steps=random.randint(20, 30))
    
    # 第四段：终点蠕动锁定（几乎不产生位移，用 10 步插值，营造迟疑感）
    page.mouse.move(target_x, start_y, steps=random.randint(10, 15))
    
    # 锁定后的最后停顿确认
    page.wait_for_timeout(random.randint(300, 500)) 
    
    page.mouse.up()

def solve_geetest_slider(page: Page, logger=None) -> bool:
    """
    主函数：自动化探测并破解极验滑块验证码。
    返回 True 表示尝试了破解（成功与否需要外部看页面是否跳转），返回 False 表示未检测到验证码。
    """
    log = logger.info if logger else print
    err = logger.error if logger else print
    
    # 等待极验窗口完全稳定
    try:
        page.wait_for_selector(".geetest_window, .geetest_panel", state="visible", timeout=5000)
    except:
        return False # 未弹出验证码，直接通过
        
    log("检测到极验滑块验证码，启动本地视觉引擎并等待加载完成...")
    
    # 获取图像（使用多重备用选择器）
    bg_selectors = [".geetest_canvas_bg", ".geetest_bg", ".geetest_item_bg"]
    slice_selectors = [".geetest_canvas_slice", ".geetest_slice_bg", ".geetest_slice"]
    
    # 动态等待 Geetest 的 loading 遮罩消失（由于挂代理网络可能很慢，最高等15秒）
    try:
        page.wait_for_selector(".geetest_panel_loading", state="hidden", timeout=15000)
        page.wait_for_selector(", ".join(bg_selectors), state="visible", timeout=10000)
    except Exception as e:
        log(f"等待极验渲染超时，可能网络卡顿: {e}")
        
    time.sleep(1) # 再预留1秒给本地浏览器渲染画布
    
    try:
        bg_img = _get_canvas_image(page, bg_selectors)
        slice_img = _get_canvas_image(page, slice_selectors)
        
        if bg_img is None or slice_img is None:
            err("无法获取极验 Canvas 图像！极验类名可能已变更，正在导出 DOM 结构以供诊断...")
            dom_html = page.evaluate("() => { const el = document.querySelector('.geetest_panel, .geetest_window'); return el ? el.innerHTML : 'Not Found'; }")
            err(f"Geetest DOM snippet: {dom_html[:1000]}...")
            return False
            
        log(f"提取成功，图片尺寸 -> 背景: {bg_img.shape}, 滑块: {slice_img.shape}")
        
        # 计算距离
        distance = _get_distance(bg_img, slice_img)
        log(f"OpenCV 计算目标缺口距离: {distance}px")
        
        # 增加一个容错循环：如果是灰块（加载中），distance会由于缺乏边缘特征而很小
        # 我们多等几秒，看看是不是网络卡顿导致图片还没加载完，而不是立马刷新
        retry_extract = 0
        while distance < 10 and retry_extract < 5:
            log("缺口距离异常，可能是图片还没加载完，等待 1.5 秒后重试提取图像...")
            time.sleep(1.5)
            bg_img = _get_canvas_image(page, bg_selectors)
            slice_img = _get_canvas_image(page, slice_selectors)
            if bg_img is not None and slice_img is not None:
                distance = _get_distance(bg_img, slice_img)
                log(f"重试提取后 OpenCV 计算距离: {distance}px")
            retry_extract += 1
        
        if distance < 10:
            err("缺口识别失败 (图片加载失败或距离异常)，尝试点击刷新按钮...")
            try:
                cv2.imwrite("debug_bg.png", bg_img)
                cv2.imwrite("debug_slice.png", slice_img)
                err("👉 已经将异常提取的图片保存到软件目录下的 debug_bg.png 和 debug_slice.png，请查看到底截出了什么鬼东西！")
            except Exception as e:
                err(f"保存调试图片失败: {e}")
                
            # 刷新按钮可能有不同类名，兼容多种情况
            try:
                page.locator(".geetest_refresh_1, .geetest_refresh").first.click(timeout=3000)
            except:
                pass
            time.sleep(2)
            return solve_geetest_slider(page, logger) # 递归重试
            
        # 获取网页中的滑块按钮
        slider = page.locator(".geetest_slider_button")
        box = slider.bounding_box()
        if not box:
            err("找不到滑块拖动按钮")
            return False
            
        # 计算拖动起点 (滑块中心偏内部一点随机位置)
        start_x = box["x"] + box["width"] / 2 + random.randint(-5, 5)
        start_y = box["y"] + box["height"] / 2 + random.randint(-5, 5)
        
        # 将鼠标移动到滑块上
        page.mouse.move(start_x, start_y)
        time.sleep(random.uniform(0.1, 0.3))
        
        log(f"开始执行原生的顺滑拖拽轨迹...")
        _perform_bionic_drag(page, start_x, start_y, distance)
        
        # 等待极验验证请求飞一会
        time.sleep(2)
        return True
        
    except Exception as e:
        err(f"极验破解模块运行异常: {e}")
        return False
