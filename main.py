import ctypes
# DPI awareness at script start to avoid coordinate scaling issues
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    from bot import OnmyojiBot
    from gui import OnmyojiBotGUI
except Exception as e:
    print("Missing dependencies or import error:", e)
    print("Install required packages: pip install -r requirements.txt")
    raise

if __name__ == "__main__":
    bot = OnmyojiBot()
    gui = OnmyojiBotGUI(bot)
    # Thiết lập liên kết hai chiều giữa bot và GUI
    bot.gui = gui
    gui.run()