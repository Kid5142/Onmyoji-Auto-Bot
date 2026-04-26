import ctypes
from ctypes import wintypes
import time
import os
import sys
from PIL import Image
import cv2
import numpy as np

# Thư viện capture siêu tốc
try:
    import mss
except ImportError:
    print("Vui lòng cài đặt mss: pip install mss")
    sys.exit(1)

# DPI awareness: ensure coordinates and captures use real pixels
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Win32 imports
try:
    import win32gui
    import win32con
    import win32api
except Exception as e:
    print("pywin32 is required (win32gui/win32api/win32ui).", e)
    sys.exit(1)

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(os.path.join(TEMPLATE_DIR, 'realm_raid'), exist_ok=True)

# Helper: find game window by exact titles or by keyword
GAME_TITLES = ['陰陽師Onmyoji', '阴阳师Onmyoji']
GAME_KEYWORD = 'onmyoji'


def find_game_hwnd():
    try:
        hwnd = win32gui.FindWindow(None, '陰陽師Onmyoji')
        if hwnd:
            print(f'Found HWND via FindWindow: {hwnd}')
            return hwnd
    except Exception as e:
        print(f'FindWindow lookup failed: {e}')

    for title in GAME_TITLES:
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                print(f'Found HWND via alternative title: {title} -> {hwnd}')
                return hwnd
        except Exception:
            pass

    found = []

    def enum_cb(hwnd, lparam):
        try:
            txt = win32gui.GetWindowText(hwnd) or ''
            if GAME_KEYWORD in txt.lower():
                l, t, r, b = win32gui.GetWindowRect(hwnd)
                if (r - l) > 100 and (b - t) > 60:
                    found.append(hwnd)
        except Exception:
            pass

    try:
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        pass
    if found:
        print(f'Found HWND via EnumWindows: {found[0]}')
    return found[0] if found else None


# --- Client-only capture ---
def get_client_dimensions(hwnd):
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width = right - left
    height = bottom - top
    return (left, top, width, height)


def capture_background(hwnd):
    """Capture using MSS (Desktop coordinates) and math-pad to target size."""
    TARGET_W = 1136
    TARGET_H = 640
    if not hwnd or not win32gui.IsWindow(hwnd):
        print('STAGE 1: capture_background: invalid hwnd')
        return None

    try:
        # 1. Lấy kích thước thực tế của Client
        _, _, actual_w, actual_h = get_client_dimensions(hwnd)
        if actual_w <= 0 or actual_h <= 0:
            return None

        # 2. Quy đổi tọa độ 0,0 của Client ra màn hình thật
        client_pos = win32gui.ClientToScreen(hwnd, (0, 0))

        # 3. Chụp bằng mss đúng kích thước thực tế đó (không bị lẹm viền)
        monitor = {
            "top": client_pos[1],
            "left": client_pos[0],
            "width": actual_w,
            "height": actual_h
        }

        with mss.mss() as sct:
            sct_img = sct.grab(monitor)
            img = np.array(sct_img)
            # Bỏ kênh Alpha (BGRA -> BGR)
            img = img[:, :, :3]
            img = np.ascontiguousarray(img)

        # 4. Đắp viền đen (Padding) nếu kích thước thực tế nhỏ hơn 1136x640
        if img.shape[1] < TARGET_W or img.shape[0] < TARGET_H:
            pad_bottom = max(0, TARGET_H - img.shape[0])
            pad_right = max(0, TARGET_W - img.shape[1])
            img = cv2.copyMakeBorder(img, 0, pad_bottom, 0, pad_right, cv2.BORDER_CONSTANT, value=(0, 0, 0))

        # Nếu lỡ to hơn thì gọt đi cho chuẩn
        if img.shape[0] > TARGET_H or img.shape[1] > TARGET_W:
            img = img[0:TARGET_H, 0:TARGET_W]

        # 5. Xác nhận shape cuối cùng
        if img.shape != (TARGET_H, TARGET_W, 3):
            print(f'STAGE 2: Capture FAILED! Unexpected shape={img.shape}')
            return None

        # 6. Lưu ảnh Preview để kiểm tra
        debug_path = os.path.join(LOG_DIR, 'debug_view.png')
        cv2.imwrite(debug_path, img)

        return img

    except Exception as e:
        print('STAGE 2: Capture exception:', e)
        return None


# --- Client-only click ---
def click_bg(hwnd, x, y):
    if not hwnd or not win32gui.IsWindow(hwnd):
        print('click_bg: invalid hwnd')
        return False
    try:
        _, _, w, h = get_client_dimensions(hwnd)
        if x < 0 or y < 0 or x >= w or y >= h:
            print(f'click_bg: coords out of bounds ({x},{y}) vs ({w},{h})')
            return False

        try:
            lparam = win32api.MAKELONG(int(x), int(y))
        except Exception:
            lparam = (int(y) << 16) | (int(x) & 0xFFFF)

        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        return True
    except Exception as e:
        print('click_bg failed:', e)
        return False


# --- Resize helper ---
def force_client_size(hwnd, target_w=1136, target_h=640):
    try:
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False

        parent_hwnd = win32gui.GetParent(hwnd)
        if parent_hwnd == 0:
            parent_hwnd = hwnd

        style = win32gui.GetWindowLong(parent_hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(parent_hwnd, win32con.GWL_EXSTYLE)

        # Dùng ctypes thay vì win32gui để fix lỗi 'no attribute'
        rect = wintypes.RECT(0, 0, int(target_w), int(target_h))
        ok = ctypes.windll.user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)

        if not ok:
            print('force_client_size: AdjustWindowRectEx failed via ctypes')
            return False

        total_w = int(rect.right - rect.left)
        total_h = int(rect.bottom - rect.top)

        win32gui.SetWindowPos(
            parent_hwnd, 0, 0, 0, total_w, total_h,
            win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_ASYNCWINDOWPOS,
        )
        time.sleep(0.5)
        return True
    except Exception as e:
        print('force_client_size failed:', e)
        return False


# --- Template matching helpers ---
def load_template(name):
    path = os.path.join(TEMPLATE_DIR, name)
    if not os.path.exists(path):
        return None
    return cv2.imread(path)


def find_template_on_image(screen_img, template_img, threshold=0.7):
    if screen_img is None or template_img is None:
        return None
    try:
        sh, sw = screen_img.shape[:2]
        th, tw = template_img.shape[:2]
        if th > sh or tw > sw:
            return None
        screen_gray = cv2.cvtColor(screen_img, cv2.COLOR_BGR2GRAY)
        tpl_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(screen_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= threshold:
            cx = int(max_loc[0] + tw // 2)
            cy = int(max_loc[1] + th // 2)
            return {'x': cx, 'y': cy, 'confidence': float(max_val)}
    except Exception as e:
        print('find_template_on_image error:', e)
    return None


# --- Main loop ---
def main():
    print('Starting Onmyoji Realm Raid bot (Client-MSS Mode)')
    hwnd = find_game_hwnd()
    if not hwnd:
        print('KHÔNG TÌM THẤY GAME. Vui lòng mở Onmyoji trước khi chạy tool!')
        return

    print('Found hwnd:', hwnd)
    force_client_size(hwnd, 1136, 640)
    client = hwnd

    section_tpl = load_template(os.path.join('realm_raid', 'section.png'))
    start_tpl = load_template(os.path.join('realm_raid', 'start_button.png'))

    while True:
        try:
            root = client
            while True:
                parent = win32gui.GetParent(root)
                if parent and parent != 0:
                    root = parent
                else:
                    break
            if win32gui.IsIconic(root):
                win32gui.ShowWindow(root, win32con.SW_RESTORE)
                time.sleep(0.25)
        except Exception:
            pass

        print("--- Iteration Start ---")
        screen = capture_background(client)
        if screen is None:
            print('STAGE 2: Capture failed; retrying...')
            time.sleep(1)
            continue

        print("STAGE 3: Matching template [section]...")
        section_match = find_template_on_image(screen, section_tpl, threshold=0.72) if section_tpl is not None else None

        if section_match:
            print(
                f"RESULT: Found [section] at ({section_match['x']}, {section_match['y']}) with Confidence: {section_match['confidence']:.4f}")
            click_bg(client, section_match['x'], section_match['y'])
            print("STAGE 4: Performing Action: [Click]...")
            time.sleep(1.2)

            start_found = False
            for attempt in range(3):
                screen2 = capture_background(client)
                start_match = find_template_on_image(screen2, start_tpl,
                                                     threshold=0.65) if start_tpl is not None else None

                if start_match:
                    print(
                        f"RESULT: Found [start_button] at attempt {attempt + 1} with Confidence: {start_match['confidence']:.4f}")
                    click_bg(client, start_match['x'], start_match['y'])
                    start_found = True
                    time.sleep(2)
                    break
                else:
                    print(f"RESULT: [start_button] NOT FOUND on attempt {attempt + 1}")
                    time.sleep(0.3)

            if not start_found:
                print('Start/Attack not found after 3 attempts; saving debug image')
                screen_fail = capture_background(client)
                if screen_fail is not None:
                    dbg_path = os.path.join(LOG_DIR, 'debug_attack_not_found.png')
                    cv2.imwrite(dbg_path, screen_fail)
            time.sleep(1)
            continue

        start_match = find_template_on_image(screen, start_tpl, threshold=0.7) if start_tpl is not None else None
        if start_match:
            print(f"RESULT: Found [start_button] directly at ({start_match['x']}, {start_match['y']})")
            click_bg(client, start_match['x'], start_match['y'])
            time.sleep(1)
            continue

        print('No targets found; sleeping...')
        time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"LOI ROI {e}")
        input('Nhan Enter de thoat...')