import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext
from datetime import datetime


class OnmyojiBotGUI:
    def __init__(self, bot):
        self.bot = bot
        self.root = tk.Tk()
        self.root.title("Onmyoji Auto - Pro Edition")
        self.root.geometry("500x650")  # Tăng kích thước để chứa Log
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Biến lưu trạng thái
        self.status_text = tk.StringVar(value="Sẵn sàng")
        self.task_var = tk.StringVar(value="")
        self.counter_var = tk.StringVar(value="Số lượt: 0")
        self.battle_count = 0

        # Khởi tạo các thành phần giao diện
        self.create_widgets()
        self.update_task_list()

    def create_widgets(self):
        """Tạo các thành phần giao diện"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Phần trạng thái & Bộ đếm ---
        status_frame = ttk.LabelFrame(main_frame, text="Bảng điều khiển trạng thái", padding="5")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        # Trạng thái với màu sắc
        self.status_label = tk.Label(status_frame, textvariable=self.status_text,
                                     font=("Segoe UI", 10, "bold"), fg="blue")
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Bộ đếm lượt đánh
        self.counter_label = tk.Label(status_frame, textvariable=self.counter_var,
                                      font=("Segoe UI", 10))
        self.counter_label.pack(side=tk.RIGHT, padx=5)

        # --- Phần chọn nhiệm vụ ---
        task_frame = ttk.LabelFrame(main_frame, text="Thiết lập nhiệm vụ", padding="5")
        task_frame.pack(fill=tk.X, padx=5, pady=5)

        self.task_combo = ttk.Combobox(task_frame, textvariable=self.task_var, state="readonly")
        self.task_combo.pack(fill=tk.X, padx=5, pady=5)
        self.task_combo.bind("<<ComboboxSelected>>", self.on_task_selected)

        # --- Phần Log (Thay thế Console khi đóng EXE) ---
        log_frame = ttk.LabelFrame(main_frame, text="Lịch sử hoạt động (Log)", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, height=12, font=("Consolas", 9), state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)

        # --- Nút điều khiển ---
        control_frame = ttk.Frame(main_frame, padding="5")
        control_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(control_frame, text="▶ BẮT ĐẦU", command=self.on_start)
        self.start_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.stop_button = ttk.Button(control_frame, text="⏹ DỪNG", command=self.on_stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # --- Phần cài đặt tinh chỉnh ---
        settings_exp = ttk.LabelFrame(main_frame, text="Cài đặt thông số", padding="5")
        settings_exp.pack(fill=tk.X, padx=5, pady=5)

        # Slider Tần suất (Ví dụ 1 cái, bạn copy tương tự cho các cái khác)
        ttk.Label(settings_exp, text="Tốc độ quét:").grid(row=0, column=0, sticky=tk.W)
        self.scan_scale = ttk.Scale(settings_exp, from_=0.1, to=3.0, value=self.bot.config['scan_interval'],
                                    command=self.on_scan_change)
        self.scan_scale.grid(row=0, column=1, sticky=tk.EW, padx=5)

    def write_log(self, message):
        """Ghi log vào ô Text Box trên GUI"""
        now = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{now}] {message}\n"

        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, full_message)
        self.log_area.see(tk.END)  # Tự động cuộn xuống dưới
        self.log_area.configure(state='disabled')

    def update_status(self, message, color="black"):
        """Cập nhật trạng thái kèm màu sắc"""
        self.status_text.set(message)
        self.status_label.config(fg=color)
        # Tự động ghi vào log luôn cho tiện
        if "Đang chạy" in message or "Thắng" in message:
            self.write_log(message)

    def on_scan_change(self, val):
        self.bot.config['scan_interval'] = float(val)

    def on_start(self):
        if not self.bot.current_task:
            self.update_status("Vui lòng chọn nhiệm vụ!")
            return

        started = self.bot.start_scanning()
        if started:
            self.update_status(f"Đang chạy: {self.task_var.get()}", color="green")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            # CHỈ cập nhật trạng thái lỗi, KHÔNG gọi hàm dừng ở đây
            self.update_status("Lỗi khởi động!", color="red")

        if self.bot.start_scanning():
            self.update_status(f"RUNNING: {self.task_var.get()}", color="green")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.write_log(f"--- BẮT ĐẦU NHIỆM VỤ: {self.task_var.get()} ---")

    def on_stop(self):
        self.bot.stop_scanning()
        self.update_status("STOPPED", color="red")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.write_log("--- ĐÃ DỪNG TOOL ---")

    def increment_battle(self):
        """Hàm để bot gọi khi kết thúc 1 trận"""
        self.battle_count += 1
        self.counter_var.set(f"Số lượt: {self.battle_count}")

    # ... Giữ lại các hàm on_close, run, update_task_list cũ của bạn ...
    def update_task_list(self):
        task_names = [task['name'] for task in self.bot.tasks.values()]
        self.task_combo['values'] = task_names
        if task_names:
            self.task_combo.current(0)
            self.on_task_selected()

    def on_task_selected(self, event=None):
        task_names = [task['name'] for task in self.bot.tasks.values()]
        selected_task = self.task_var.get()
        if selected_task in task_names:
            task_index = task_names.index(selected_task)
            self.bot.current_task = list(self.bot.tasks.keys())[task_index]

    def on_close(self):
        self.bot.stop_scanning()
        self.root.destroy()

    def run(self):
        self.root.mainloop()