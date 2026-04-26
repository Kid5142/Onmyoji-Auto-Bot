import os
import sys
import time
import cv2
import numpy as np
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
# Note: screen capture in this test file is disabled to avoid full-screen grabs.
# Use the Win32-backed capture in the main bot (onmyoji_realm_raid.py or bot.py's capture_background).
import pygetwindow as gw  # Thêm thư viện này vào đầu file

class OnmyojiBot:
    def __init__(self):
        # Cấu hình cơ bản
        self.config = {
            'scan_interval': 1.0,      # Thời gian giữa các lần quét (giây)
            'click_delay': 0.3,        # Thời gian chờ giữa các lần click (giây)
            'confidence': 0.8,         # Ngưỡng độ tin cậy cho nhận diện
            'active': False,           # Trạng thái hoạt động của bot
            'debug': True,             # Chế độ debug
            'template_dir': 'templates/', # Thư mục chứa hình ảnh mẫu
        }
        
        # Đảm bảo thư mục templates tồn tại
        os.makedirs(self.config['template_dir'], exist_ok=True)
        
        # Khu vực chụp màn hình game
        self.game_region = None  # Sẽ được cập nhật khi người dùng chọn vùng
        
        # Trạng thái hiện tại của game
        self.game_state = {
            'screen': 'unknown',
            'in_battle': False,
            'auto_mode': False,
            'enemies': 0,
        }
        
        # Nhiệm vụ hiện tại
        self.current_task = None
        
        # Thread cho việc quét màn hình
        self.scanning_thread = None
        
        # Tạo từ điển các mẫu hình ảnh
        self.templates = {}
        self.load_templates()
        
        # Danh sách các nhiệm vụ
        self.tasks = {
            'souls': {
                'name': 'Farm Souls',
                'steps': [
                    {'action': 'find_click', 'target': 'souls_button', 'desc': 'Nhấn nút Souls'},
                    {'action': 'find_click', 'target': 'orochi_button', 'desc': 'Chọn Orochi'},
                    {'action': 'find_click', 'target': 'stage_button', 'desc': 'Chọn Stage'},
                    {'action': 'find_click', 'target': 'start_button', 'desc': 'Nhấn nút Start'},
                    {'action': 'wait_for', 'target': 'battle_screen', 'desc': 'Chờ vào trận', 'timeout': 10},
                    {'action': 'find_click', 'target': 'auto_button', 'desc': 'Bật chế độ tự động'},
                    {'action': 'wait_for', 'target': 'victory_screen', 'desc': 'Chờ chiến thắng', 'timeout': 120},
                    {'action': 'find_click', 'target': 'reward_button', 'desc': 'Nhận thưởng'},
                    {'action': 'wait', 'time': 2, 'desc': 'Chờ chút'},
                    {'action': 'find_click', 'target': 'again_button', 'desc': 'Nhấn nút Again', 'optional': True},
                    {'action': 'find_click', 'target': 'prepare_button', 'desc': 'Nhấn nút Prepare', 'optional': True},
                    {'action': 'repeat', 'desc': 'Lặp lại'}
                ],
                'current_step': 0
            },
            'exploration': {
                'name': 'Exploration',
                'steps': [
                    {'action': 'find_click', 'target': 'exploration_button', 'desc': 'Chọn Exploration'},
                    {'action': 'find_click', 'target': 'chapter_button', 'desc': 'Chọn Chapter'},
                    {'action': 'find_click', 'target': 'zone_button', 'desc': 'Chọn Zone'},
                    {'action': 'find_click', 'target': 'explore_button', 'desc': 'Nhấn nút Explore'},
                    {'action': 'wait_for', 'target': 'battle_screen', 'desc': 'Chờ vào trận', 'timeout': 10},
                    {'action': 'find_click', 'target': 'auto_button', 'desc': 'Bật chế độ tự động'},
                    {'action': 'wait_for', 'target': 'victory_screen', 'desc': 'Chờ chiến thắng', 'timeout': 120},
                    {'action': 'find_click', 'target': 'reward_button', 'desc': 'Nhận thưởng'},
                    {'action': 'repeat', 'desc': 'Lặp lại'}
                ],
                'current_step': 0
            },
            'evo': {
                'name': 'Evolution Materials',
                'steps': [
                    {'action': 'find_click', 'target': 'evo_button', 'desc': 'Chọn Evolution'},
                    {'action': 'find_click', 'target': 'evo_type', 'desc': 'Chọn loại vật liệu'},
                    {'action': 'find_click', 'target': 'stage_button', 'desc': 'Chọn Stage'},
                    {'action': 'find_click', 'target': 'prepare_button', 'desc': 'Nhấn nút Prepare'},
                    {'action': 'find_click', 'target': 'start_button', 'desc': 'Nhấn nút Start'},
                    {'action': 'wait_for', 'target': 'battle_screen', 'desc': 'Chờ vào trận', 'timeout': 10},
                    {'action': 'find_click', 'target': 'auto_button', 'desc': 'Bật chế độ tự động'},
                    {'action': 'wait_for', 'target': 'victory_screen', 'desc': 'Chờ chiến thắng', 'timeout': 120},
                    {'action': 'find_click', 'target': 'reward_button', 'desc': 'Nhận thưởng'},
                    {'action': 'wait', 'time': 2, 'desc': 'Chờ chút'},
                    {'action': 'find_click', 'target': 'again_button', 'desc': 'Nhấn nút Again', 'optional': True},
                    {'action': 'find_click', 'target': 'prepare_button', 'desc': 'Nhấn nút Prepare', 'optional': True},
                    {'action': 'repeat', 'desc': 'Lặp lại'}
                ],
                'current_step': 0
            },
            'realm_raid': {
                'name': 'Realm Raid',
                'steps': [
                    {'action': 'find_click', 'target': 'realm_raid_button', 'desc': 'Nhấn nút Realm Raid'},
                    {'action': 'find_click', 'target': 'refresh_button', 'desc': 'Làm mới danh sách kẻ địch', 'optional': True},
                    {'action': 'find_click', 'target': 'enemy_button', 'desc': 'Chọn kẻ địch'},
                    {'action': 'find_click', 'target': 'start_button', 'desc': 'Nhấn nút Start'},
                    {'action': 'wait_for', 'target': 'battle_screen', 'desc': 'Chờ vào trận', 'timeout': 10},
                    {'action': 'find_click', 'target': 'auto_button', 'desc': 'Bật chế độ tự động'},
                    {'action': 'wait_for', 'target': 'victory_screen', 'desc': 'Chờ chiến thắng', 'timeout': 120},
                    {'action': 'find_click', 'target': 'reward_button', 'desc': 'Nhận thưởng'},
                    {'action': 'find_click', 'target': 'exit_button', 'desc': 'Thoát màn hình kết thúc', 'optional': True},
                    {'action': 'wait', 'time': 2, 'desc': 'Chờ chút'},
                    {'action': 'repeat', 'desc': 'Lặp lại'}
                ],
                'current_step': 0
            }
        }
        
        # Khởi tạo giao diện người dùng
        self.gui = None
        self.init_gui()
    
    def load_templates(self):
        """Tải các mẫu hình ảnh từ thư mục templates"""
        # Trong ứng dụng thực tế, bạn sẽ có các hình ảnh mẫu ở đây
        # Hiện tại chỉ khai báo các mẫu để demo
        self.templates = {
            # Các nút menu chính
            'souls_button': {'region': None, 'desc': 'Nút Soul'},
            'exploration_button': {'region': None, 'desc': 'Nút Exploration'},
            'evo_button': {'region': None, 'desc': 'Nút Evolution'},
            
            # Các nút trong trận đấu
            'auto_button': {'region': None, 'desc': 'Nút Auto'},
            'prepare_button': {'region': None, 'desc': 'Nút Prepare'},
            'start_button': {'region': None, 'desc': 'Nút Start'},
            'again_button': {'region': None, 'desc': 'Nút Again'},
            
            # Màn hình nhận diện
            'battle_screen': {'region': None, 'desc': 'Màn hình trận đấu'},
            'victory_screen': {'region': None, 'desc': 'Màn hình chiến thắng'},
            'reward_button': {'region': None, 'desc': 'Nút nhận thưởng'},
            
            # Các nút khác
            'orochi_button': {'region': None, 'desc': 'Nút Orochi'},
            'stage_button': {'region': None, 'desc': 'Nút Stage'},
            'chapter_button': {'region': None, 'desc': 'Nút Chapter'},
            'zone_button': {'region': None, 'desc': 'Nút Zone'},
            'explore_button': {'region': None, 'desc': 'Nút Explore'},
            'evo_type': {'region': None, 'desc': 'Loại vật liệu'}
        }
        
        # Nếu có hình ảnh mẫu trong thư mục, tải chúng
        for template_name in self.templates:
            template_path = os.path.join(self.config['template_dir'], f"{template_name}.png")
            if os.path.exists(template_path):
                self.templates[template_name]['image'] = cv2.imread(template_path, cv2.IMREAD_COLOR)
                if self.config['debug']:
                    print(f"Đã tải mẫu hình ảnh: {template_name}")
    
    def capture_screen(self):
        """Capture disabled in tool-test. Use main bot's Win32 capture.
        Returning None to avoid full-screen grabs.
        """
        print('tool-test.capture_screen: disabled to avoid full-screen captures; use main bot')
        return None
    
    def find_template(self, screen_img, template_name, threshold=None):
        """Tìm mẫu hình ảnh trên màn hình"""
        if threshold is None:
            threshold = self.config['confidence']
            
        template_data = self.templates.get(template_name)
        if not template_data or 'image' not in template_data:
            if self.config['debug']:
                print(f"Không tìm thấy mẫu hình ảnh: {template_name}")
            return None
            
        template_img = template_data['image']
        search_region = template_data['region']
        
        # Cắt khu vực tìm kiếm nếu có
        if search_region is not None:
            rx, ry, rw, rh = search_region
            screen_region = screen_img[ry:ry+rh, rx:rx+rw]
        else:
            screen_region = screen_img
            
        # Tìm mẫu hình ảnh bằng OpenCV
        result = cv2.matchTemplate(screen_region, template_img, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= threshold:
            # Tìm thấy mẫu
            h, w = template_img.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            
            # Điều chỉnh tọa độ nếu đang tìm trong khu vực
            if search_region is not None:
                center_x += rx
                center_y += ry
                
            if self.config['debug']:
                print(f"Tìm thấy {template_name} tại ({center_x}, {center_y}) với độ tin cậy {max_val:.2f}")
                
            return {
                'x': center_x,
                'y': center_y,
                'confidence': max_val,
                'width': w,
                'height': h
            }
        else:
            if self.config['debug']:
                print(f"Không tìm thấy {template_name} (độ tin cậy tối đa: {max_val:.2f})")
            return None
    
    def click(self, x, y, duration=0.2):
        """Click disabled in tool-test. Use main bot's click_bg for client-based clicks."""
        print('tool-test.click: disabled. Use main bot for background clicks.')
        return False
    
    def find_and_click(self, template_name, threshold=None):
        """Tìm mẫu hình ảnh và click vào nó"""
        screen_img = self.capture_screen()
        match = self.find_template(screen_img, template_name, threshold)
        
        if match:
            self.click(match['x'], match['y'])
            return True
        else:
            return False
    
    def wait_for(self, template_name, timeout=30, threshold=None):
        """Đợi cho đến khi mẫu hình ảnh xuất hiện"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not self.config['active']:
                return False
                
            screen_img = self.capture_screen()
            match = self.find_template(screen_img, template_name, threshold)
            
            if match:
                return True
                
            time.sleep(0.5)
            
        return False
    
    def analyze_game_state(self):
        """Phân tích trạng thái hiện tại của game"""
        screen_img = self.capture_screen()
        
        # Kiểm tra xem có đang trong trận đấu không
        battle_match = self.find_template(screen_img, 'battle_screen', 0.7)
        self.game_state['in_battle'] = battle_match is not None
        
        # Kiểm tra xem có đang ở màn hình chiến thắng không
        victory_match = self.find_template(screen_img, 'victory_screen', 0.7)
        if victory_match:
            self.game_state['screen'] = 'victory'
        elif battle_match:
            self.game_state['screen'] = 'battle'
        else:
            self.game_state['screen'] = 'unknown'
            
        return self.game_state
    
    def execute_task_step(self):
        """Thực hiện bước hiện tại của nhiệm vụ"""
        if not self.current_task:
            return False

        task = self.tasks[self.current_task]
        if task['current_step'] >= len(task['steps']):
            task['current_step'] = 0

        step = task['steps'][task['current_step']]
        action = step['action']

        if self.config['debug']:
            print(f"Thực hiện: {step['desc']}")

        success = False

        if action == 'find_click':
            success = self.find_and_click(step['target'])
            # Nếu tùy chọn và không tìm thấy, vẫn coi là thành công
            if not success and step.get('optional', False):
                success = True

        elif action == 'wait_for':
            timeout = step.get('timeout', 30)
            success = self.wait_for(step['target'], timeout)

        elif action == 'wait':
            time.sleep(step.get('time', 1))
            success = True

        elif action == 'repeat':
            # Reset về bước đầu tiên
            task['current_step'] = 0
            return True

        # Xử lý trạng thái đặc biệt
        if not success and self.current_task == 'realm_raid':
            if step['target'] == 'enemy_button':
                # Nếu không tìm thấy kẻ địch, làm mới danh sách
                self.find_and_click('refresh_button')
            elif step['target'] == 'battle_screen':
                # Nếu không vào được trận, kiểm tra trạng thái thất bại
                if self.find_template(self.capture_screen(), 'failed.png'):
                    self.find_and_click('exit_button')

        if success:
            task['current_step'] += 1
            if self.config['debug']:
                next_step = task['current_step']
                if next_step < len(task['steps']):
                    print(f"Bước tiếp theo: {task['steps'][next_step]['desc']}")
                else:
                    print("Hoàn thành tất cả các bước, lặp lại từ đầu")
        else:
            if self.config['debug']:
                print(f"Thực hiện thất bại: {step['desc']}")

        return success
    
    def start_scanning(self):
        """Bắt đầu quét màn hình và thực hiện nhiệm vụ"""
        if self.scanning_thread and self.scanning_thread.is_alive():
            return
            
        self.config['active'] = True
        self.scanning_thread = threading.Thread(target=self.scanning_loop)
        self.scanning_thread.daemon = True
        self.scanning_thread.start()
        
        if self.gui:
            self.gui.update_status("Đang hoạt động")
    
    def stop_scanning(self):
        """Dừng quét màn hình"""
        self.config['active'] = False
        if self.scanning_thread:
            self.scanning_thread.join(timeout=1.0)
            
        if self.gui:
            self.gui.update_status("Đã dừng")
    
    def scanning_loop(self):
        """Vòng lặp quét màn hình và thực hiện nhiệm vụ"""
        while self.config['active']:
            try:
                # Phân tích trạng thái game
                game_state = self.analyze_game_state()
                
                # Cập nhật trạng thái lên giao diện
                if self.gui:
                    self.gui.update_game_state(game_state)
                    
                # Thực hiện bước tiếp theo của nhiệm vụ
                if self.current_task:
                    self.execute_task_step()
                    
            except Exception as e:
                print(f"Lỗi trong quá trình quét: {e}")
                if self.config['debug']:
                    import traceback
                    traceback.print_exc()
                    
            time.sleep(self.config['scan_interval'])
    
    def init_gui(self):
        """Khởi tạo giao diện người dùng"""
        self.gui = OnmyojiBotGUI(self)
        
    def select_game_region(self):
        """Tự động chọn khu vực màn hình game dựa trên tên cửa sổ"""
        window_name = "陰陽師Onmyoji"
        try:
            # Tìm cửa sổ theo tên
            game_window = next(win for win in gw.getWindowsWithTitle(window_name) if win.title == window_name)
            
            # Lấy tọa độ và kích thước cửa sổ
            x, y, width, height = game_window.left, game_window.top, game_window.width, game_window.height
            self.game_region = (x, y, width, height)
            
            if self.gui:
                self.gui.update_status(f"Tự động chọn khu vực: {self.game_region}")
            return True
        except StopIteration:
            if self.gui:
                self.gui.update_status(f"Không tìm thấy cửa sổ: {window_name}")
            return False
    
    def create_template(self, template_name):
        """Tạo mẫu hình ảnh mới từ vùng chọn"""
        if not template_name:
            messagebox.showwarning("Lỗi", "Vui lòng nhập tên cho mẫu hình ảnh")
            return False
            
        if template_name not in self.templates:
            self.templates[template_name] = {'region': None, 'desc': template_name}
            
        messagebox.showinfo("Chọn mẫu", f"Vui lòng chọn vùng cho mẫu '{template_name}'.\n\nNhấn Enter để xác nhận sau khi chọn.")
        
        # Chụp màn hình
        screen = self.capture_screen()
        
        # Hiển thị hình ảnh để người dùng chọn vùng
        template_region = cv2.selectROI(f"Chọn vùng cho '{template_name}'", screen, False, False)
        cv2.destroyAllWindows()
        
        if template_region[2] > 0 and template_region[3] > 0:
            # Cắt vùng được chọn
            x, y, w, h = template_region
            template_img = screen[y:y+h, x:x+w]
            
            # Lưu mẫu
            self.templates[template_name]['image'] = template_img
            self.templates[template_name]['region'] = None  # Mẫu sẽ được tìm trên toàn màn hình
            
            # Lưu hình ảnh mẫu
            template_path = os.path.join(self.config['template_dir'], f"{template_name}.png")
            cv2.imwrite(template_path, template_img)
            
            if self.gui:
                self.gui.update_status(f"Đã tạo mẫu: {template_name}")
            return True
        else:
            if self.gui:
                self.gui.update_status("Hủy tạo mẫu")
            return False
    
    def run(self):
        """Chạy ứng dụng"""
        if self.gui:
            self.gui.run()
        else:
            print("Không thể khởi tạo giao diện người dùng")


class OnmyojiBotGUI:
    def __init__(self, bot):
        self.bot = bot
        self.root = tk.Tk()
        self.root.title("Onmyoji Auto Bot")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Thêm biểu tượng nếu có
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # Biến lưu trạng thái
        self.status_text = tk.StringVar(value="Sẵn sàng")
        self.task_var = tk.StringVar(value="")  # Khởi tạo task_var trước khi gọi create_widgets
        
        # Khởi tạo các thành phần giao diện
        self.create_widgets()
        
        # Cập nhật danh sách nhiệm vụ
        self.update_task_list()
    
    def create_widgets(self):
        """Tạo các thành phần giao diện"""
        # Frame chính
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Phần thông tin trạng thái
        status_frame = ttk.LabelFrame(main_frame, text="Trạng thái", padding="5")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Sẵn sàng")
        self.status_label.pack(anchor=tk.W)
        
        self.game_state_label = ttk.Label(status_frame, text="Màn hình: Chưa xác định")
        self.game_state_label.pack(anchor=tk.W)
        
        # Phần chọn nhiệm vụ
        task_frame = ttk.LabelFrame(main_frame, text="Nhiệm vụ", padding="5")
        task_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.task_combo = ttk.Combobox(task_frame, textvariable=self.task_var, state="readonly")
        self.task_combo['values'] = [task['name'] for task in self.bot.tasks.values()]  # Populate with task names
        self.task_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.task_combo.bind("<<ComboboxSelected>>", self.on_task_selected)
        
        # Phần điều khiển
        control_frame = ttk.LabelFrame(main_frame, text="Điều khiển", padding="5")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="Bắt đầu", command=self.on_start)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Dừng", command=self.on_stop)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.config(state=tk.DISABLED)
        
        self.region_button = ttk.Button(control_frame, text="Chọn khu vực game", command=self.on_select_region)
        self.region_button.pack(side=tk.LEFT, padx=5)
        
        # Phần cài đặt
        settings_frame = ttk.LabelFrame(main_frame, text="Cài đặt", padding="5")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Tần suất quét
        ttk.Label(settings_frame, text="Tần suất quét (giây):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.scan_interval = ttk.Scale(settings_frame, from_=0.1, to=3.0, length=200, orient=tk.HORIZONTAL)
        self.scan_interval.set(self.bot.config['scan_interval'])
        self.scan_interval.grid(row=0, column=1, padx=5, pady=2)
        self.scan_interval_label = ttk.Label(settings_frame, text=str(self.bot.config['scan_interval']))
        self.scan_interval_label.grid(row=0, column=2, padx=5, pady=2)
        self.scan_interval.bind("<Motion>", lambda e: self.update_scale_label(self.scan_interval, self.scan_interval_label))
        
        # Độ trễ click
        ttk.Label(settings_frame, text="Độ trễ click (giây):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.click_delay = ttk.Scale(settings_frame, from_=0.1, to=1.0, length=200, orient=tk.HORIZONTAL)
        self.click_delay.set(self.bot.config['click_delay'])
        self.click_delay.grid(row=1, column=1, padx=5, pady=2)
        self.click_delay_label = ttk.Label(settings_frame, text=str(self.bot.config['click_delay']))
        self.click_delay_label.grid(row=1, column=2, padx=5, pady=2)
        self.click_delay.bind("<Motion>", lambda e: self.update_scale_label(self.click_delay, self.click_delay_label))
        
        # Độ tin cậy
        ttk.Label(settings_frame, text="Độ tin cậy:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.confidence = ttk.Scale(settings_frame, from_=0.5, to=1.0, length=200, orient=tk.HORIZONTAL)
        self.confidence.set(self.bot.config['confidence'])
        self.confidence.grid(row=2, column=1, padx=5, pady=2)
        self.confidence_label = ttk.Label(settings_frame, text=str(self.bot.config['confidence']))
        self.confidence_label.grid(row=2, column=2, padx=5, pady=2)
        self.confidence.bind("<Motion>", lambda e: self.update_scale_label(self.confidence, self.confidence_label))
        
        # Chế độ debug
        self.debug_var = tk.BooleanVar(value=self.bot.config['debug'])
        debug_check = ttk.Checkbutton(settings_frame, text="Chế độ debug", variable=self.debug_var, 
                                  command=self.on_debug_changed)
        debug_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        
        # Phần hướng dẫn sử dụng
        guide_frame = ttk.LabelFrame(main_frame, text="Hướng dẫn sử dụng", padding="5")
        guide_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.guide_text = tk.Text(guide_frame, wrap=tk.WORD, state=tk.DISABLED, height=10)
        self.guide_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Nút tạo mẫu
        self.create_template_button = ttk.Button(main_frame, text="Tạo mẫu hình ảnh", command=self.on_create_template)
        self.create_template_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Nút thoát
        self.exit_button = ttk.Button(main_frame, text="Thoát", command=self.on_close)
        self.exit_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Cập nhật hướng dẫn sử dụng
        self.update_guide()
    
    def update_task_list(self):
        """Cập nhật danh sách nhiệm vụ trong giao diện"""
        task_names = [task['name'] for task in self.bot.tasks.values()]
        self.task_combo['values'] = task_names
        
        if task_names:
            self.task_combo.current(0)
            self.on_task_selected()
    
    def update_scale_label(self, scale_widget, label_widget):
        """Cập nhật nhãn hiển thị giá trị của thanh trượt"""
        value = scale_widget.get()
        label_widget.config(text=f"{value:.2f}")
        
        # Cập nhật giá trị trong cấu hình
        if scale_widget == self.bot.scan_interval:
            self.bot.config['scan_interval'] = value
        elif scale_widget == self.bot.click_delay:
            self.bot.config['click_delay'] = value
        elif scale_widget == self.bot.confidence:
            self.bot.config['confidence'] = value
    
    def update_guide(self):
        """Cập nhật nội dung hướng dẫn sử dụng"""
        guide_content = (
            "Hướng dẫn sử dụng:\n"
            "1. Chọn khu vực màn hình game bằng cách nhấn nút 'Chọn khu vực game'.\n"
            "2. Tùy chỉnh các cài đặt như tần suất quét, độ trễ click, độ tin cậy.\n"
            "3. Chọn nhiệm vụ muốn thực hiện từ danh sách nhiệm vụ.\n"
            "4. Nhấn nút 'Bắt đầu' để bắt đầu quét và thực hiện nhiệm vụ.\n"
            "5. Nhấn nút 'Dừng' để dừng quét và thực hiện nhiệm vụ.\n"
            "6. Xem trạng thái và thông tin nhiệm vụ ở phần 'Trạng thái'.\n"
            "7. Để tạo mẫu hình ảnh mới, hãy chọn vùng muốn tạo mẫu trên màn hình game và nhập tên cho mẫu."
        )
        
        self.guide_text.config(state=tk.NORMAL)
        self.guide_text.delete(1.0, tk.END)
        self.guide_text.insert(tk.END, guide_content)
        self.guide_text.config(state=tk.DISABLED)
    
    def on_task_selected(self, event=None):
        """Xử lý khi người dùng chọn nhiệm vụ"""
        task_names = [task['name'] for task in self.bot.tasks.values()]
        selected_task = self.task_var.get()
        
        if selected_task in task_names:
            task_index = task_names.index(selected_task)
            self.bot.current_task = list(self.bot.tasks.keys())[task_index]
            
            # Cập nhật bước đầu tiên cho nhiệm vụ
            self.bot.tasks[self.bot.current_task]['current_step'] = 0
    
    def on_start(self):
        """Xử lý khi nhấn nút Bắt đầu"""
        self.bot.start_scanning()
        
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
    
    def on_stop(self):
        """Xử lý khi nhấn nút Dừng"""
        self.bot.stop_scanning()
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def on_select_region(self):
        """Xử lý khi nhấn nút Chọn khu vực game"""
        self.bot.select_game_region()
    
    def on_debug_changed(self):
        """Xử lý khi thay đổi chế độ debug"""
        self.bot.config['debug'] = self.debug_var.get()
    
    def on_create_template(self):
        """Xử lý khi nhấn nút Tạo mẫu hình ảnh"""
        template_name = simpledialog.askstring("Tạo mẫu hình ảnh", "Nhập tên cho mẫu hình ảnh:")
        
        if template_name:
            self.bot.create_template(template_name)
    
    def on_close(self):
        """Xử lý khi đóng cửa sổ ứng dụng"""
        self.bot.stop_scanning()
        self.root.destroy()
    
    def run(self):
        """Chạy giao diện người dùng"""
        self.root.mainloop()
    
    def update_status(self, message):
        """Cập nhật trạng thái trên giao diện"""
        self.status_label.config(text=message)
    
    def update_game_state(self, game_state):
        """Cập nhật trạng thái game trên giao diện"""
        screen = game_state['screen']
        in_battle = game_state['in_battle']
        
        self.game_state_label.config(text=f"Màn hình: {screen}, Trong trận: {in_battle}")


if __name__ == "__main__":
    bot = OnmyojiBot()
    bot.run()
