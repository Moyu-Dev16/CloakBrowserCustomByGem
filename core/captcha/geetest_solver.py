import time
import base64
import random
import math
import numpy as np
import cv2
from playwright.sync_api import Page
import logging

def _get_canvas_image(page: Page, class_name: str) -> np.ndarray:
    """提取画布内容的 base64 并转换为 OpenCV 图像 (BGR)"""
    script = f"""
    () => {{
        const canvas = document.querySelector('{class_name}');
        if (!canvas) return null;
        return canvas.toDataURL('image/png').substring(22);
    }}
    """
    b64_data = page.evaluate(script)
    if not b64_data:
        return None
    img_data = base64.b64decode(b64_data)
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img

def _get_distance(bg_img: np.ndarray, slice_img: np.ndarray) -> int:
    """
    通过 OpenCV 计算缺口 X 轴坐标距离。
    针对极验3，bg_img 是带缺口的背景，slice_img 是完整的滑块（通常也是同等大小，但滑块在最左侧）。
    更稳妥的通用办法：基于边缘检测找到背景中突兀的方形缺口。
    """
    # 转灰度
    bg_gray = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY)
    
    # 极验背景图中的缺口通常有明显的边缘阴影，我们可以通过阈值和边缘检测来寻找
    blurred = cv2.GaussianBlur(bg_gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 100, 200)
    
    # 也可以利用 fullbg 和 bg 的差值来找，但有时 fullbg 不一定可用。
    # 这里我们用最经典的模板匹配方法：将 slice_img 裁剪出真实滑块，去匹配 bg_img
    
    # 先把 slice_img 转为 RGBA（如果有Alpha通道）或处理它的非透明区域
    # 因为我们从 canvas 提取的是 png，如果 OpenCV 没有读取 Alpha，需要额外处理。
    # 但由于通常滑块背景是透明的（黑色），我们先找滑块在 slice_img 里的真实边界：
    slice_gray = cv2.cvtColor(slice_img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(slice_gray, 10, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return 0
        
    # 找到最大的轮廓（滑块本体）
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    
    # 裁剪出真实的滑块模板
    template = bg_gray[y:y+h, x:x+w] # 极验的 slice canvas 往往本身就在正确 Y 轴！直接用 bg_img 的同等大小去匹配，或者提取 slice 的非零部分
    template_slice = slice_gray[y:y+h, x:x+w]
    
    # 用 Canny 边缘做模板匹配，排除颜色干扰
    bg_edges = cv2.Canny(bg_gray, 100, 200)
    slice_edges = cv2.Canny(template_slice, 100, 200)
    
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

def _generate_bionic_tracks(distance: int) -> list:
    """
    生成仿生拖动轨迹（贝塞尔/加减速）。
    分为三段：加速、减速、微调回撤。
    """
    tracks = []
    current = 0
    # 稍微超过目标距离，模拟人类滑过头
    overshoot = random.randint(10, 20)
    target = distance + overshoot
    
    t = 0.2
    v = 0
    
    # 加减速模拟
    while current < target:
        # 前半段加速度大，后半段加速度小（甚至为负，减速）
        if current < target * 4 / 5:
            a = random.randint(20, 50)
        else:
            a = -random.randint(30, 50)
            
        v0 = v
        v = v0 + a * t
        move = v0 * t + 0.5 * a * (t ** 2)
        
        if move < 1:
            move = random.randint(1, 3)
            
        current += move
        if current > target:
            current = target
            
        tracks.append(round(move))
        
    # 回撤那超出的一部分
    for _ in range(overshoot):
        tracks.append(-1)
        
    # 确保最终总和绝对等于 distance
    diff = sum(tracks) - distance
    if diff > 0:
        for _ in range(diff):
            tracks.append(-1)
    elif diff < 0:
        for _ in range(abs(diff)):
            tracks.append(1)
            
    return tracks

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
        
    log("检测到极验滑块验证码，启动本地视觉引擎...")
    time.sleep(1) # 等待画布渲染
    
    try:
        # 获取图像
        bg_img = _get_canvas_image(page, ".geetest_canvas_bg")
        slice_img = _get_canvas_image(page, ".geetest_canvas_slice")
        
        if bg_img is None or slice_img is None:
            err("无法获取极验 Canvas 图像！")
            return False
            
        # 计算距离
        distance = _get_distance(bg_img, slice_img)
        log(f"OpenCV 计算目标缺口距离: {distance}px")
        
        if distance < 10:
            err("缺口识别失败 (距离异常)，尝试刷新...")
            page.click(".geetest_refresh_1")
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
        page.mouse.down()
        
        # 生成仿生轨迹并拖动
        tracks = _generate_bionic_tracks(distance)
        current_x = start_x
        current_y = start_y
        
        log(f"生成仿生轨迹点数: {len(tracks)}，开始拖拽...")
        for x_move in tracks:
            current_x += x_move
            # Y轴加入极其微弱的随机抖动
            current_y += random.choice([-1, 0, 1]) * random.random()
            page.mouse.move(current_x, current_y)
            # 极快的间隔时间模拟人手
            time.sleep(random.uniform(0.01, 0.03))
            
        # 拖拽到目标点后，停顿一下再松开（非常关键的拟人特征）
        time.sleep(random.uniform(0.4, 0.7))
        page.mouse.up()
        
        # 等待极验验证请求飞一会
        time.sleep(2)
        return True
        
    except Exception as e:
        err(f"极验破解模块运行异常: {e}")
        return False
