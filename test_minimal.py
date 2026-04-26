import os
import sys
import ctypes
import win32gui

# Tạo thư mục log trước khi chạy bất cứ thứ gì
log_dir = "C:/Tool-Onmyoji/logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)


def safe_print(message):
    """Print text safely on consoles with limited encodings."""
    text = str(message)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        fallback = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(fallback + "\n")


def test():
    safe_print("--- STARTING BASIC CHECK ---")

    # 1. Kiểm tra DPI Awareness
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        safe_print("[OK] DPI awareness set")
    except Exception as e:
        safe_print(f"[ERROR] DPI awareness failed: {e}")

    # 2. Kiểm tra tìm Handle Game
    game_title = "陰陽師Onmyoji"
    hwnd = win32gui.FindWindow(None, game_title)

    if hwnd:
        safe_print(f"[OK] Found game window. HWND: {hwnd}")
        rect = win32gui.GetWindowRect(hwnd)
        safe_print(f"Window position on screen: {rect}")
    else:
        safe_print("[ERROR] Game window not found. Make sure the game is open and not running with higher admin privileges.")


if __name__ == "__main__":
    try:
        test()
    except Exception as e:
        safe_print(f"CRITICAL CRASH: {e}")
    input("\nPress Enter to exit...")