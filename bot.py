import os
import time
import cv2
import numpy as np
import sys
import threading
import ctypes
from ctypes import wintypes
from datetime import datetime
from PIL import Image
from tasks import tasks
import types
import mss

def get_resource_path(relative_path):
    """ Lấy đường dẫn tuyệt đối đến tài nguyên, hỗ trợ cho PyInstaller """
    try:
        # PyInstaller tạo một thư mục tạm và lưu đường dẫn trong _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Enable DPI awareness immediately so captures use true resolution on high-DPI displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    import win32gui
    import win32con
    import win32api
except Exception:
    win32gui = None
    win32con = None
    win32api = None


class OnmyojiBot:
    def __init__(self):
        self.config = {
            'scan_interval': 1.0,
            'click_delay': 0.3,
            'confidence': 0.8,
            'active': False,
            'debug': True,
            'background_click': True,
            'lock_window_size': False,
            'target_window_x': 80,
            'target_window_y': 60,
            'target_window_w': 1280,
            'target_window_h': 720,
            'desired_client_w': 1136,
            'desired_client_h': 640,
            'template_dir': 'templates/',
            'game_window_exact_titles': ['陰陽師Onmyoji', '阴阳师Onmyoji'],
            'exclude_window_keywords': ['auto bot'],
        }
        self.template_threshold_overrides = {
            'realm_raid_button': 0.7,
            'enemy_button': 0.76,
            'start_button': 0.75,
            'exit_button': 0.90,
            'victory_screen': 0.9,
            'attack_button': 0.7
        }
        self.log_dir = 'logs'
        self.log_file = os.path.join(self.log_dir, 'bot-debug.log')
        os.makedirs(self.log_dir, exist_ok=True)
        self.template_folder_candidates = {
            'souls': ['souls'],
            'exploration': ['exploration'],
            'realm_raid': ['realm_raid', 'Realm_Raid', 'Realm Raid']
        }
        self._create_template_directories()
        self.game_region = None
        self.game_state = {'screen': 'unknown', 'in_battle': False, 'auto_mode': False, 'enemies': 0}
        self.current_task = None
        self.scanning_thread = None
        self.templates = {}
        self.tasks = tasks
        self.current_window = None
        self.current_hwnd = None
        self.preferred_window_size = None
        self.last_click_target = None
        self.last_click_time = 0
        self.same_target_click_count = 0
        self.temp_target_blacklist_until = {}
        self.click_target_cooldowns = {
            'enemy_button': 1.2,
            'start_button': 1.2,
            'auto_button': 1.2,
            'reward_screen': 1.5,
            'exit_button': 3.0,
            'refresh_button': 3.0,
        }
        self.template_mapping = {
            'realm_raid': [
                'realm_raid_button', 'refresh_button', 'enemy_button',
                'start_button', 'attack_button', 'ready_button', 'battle_screen', 'auto_button',
                'victory_screen', 'reward_screen', 'exit_button', 'section', 'enemy_event', 'empty'
            ],
            'souls': [
                'start_button',
                'victory_screen', 'reward_screen',
                'plus_sign'
            ],
            'exploration': [
                'exploration_button', 'chapter_button', 'zone_button',
                'explore_button'
            ]
        }
        self.template_aliases = {
            'souls_button': ['souls_button'],
            'start_button': ['start_button', 'start'],
            'auto_button': ['auto_button', 'auto', 'full'],
            'victory_screen': ['finished1'],
            'reward_screen': ['reward_screen'],
            'empty': ['empty', 'out_of_tickets', 'finish_sign'],
            'exploration_button': ['exploration_button'],
            'chapter_button': ['chapter_button'],
            'zone_button': ['zone_button'],
            'explore_button': ['explore_button'],
            'realm_raid_button': ['realm_raid_button', 'realmRaid', 'realmraid'],
            'refresh_button': ['refresh_button', 'refresh'],
            'enemy_button': ['enemy_button', 'section', 'click'],
            'enemy_event': ['frog'],
            'attack_button': ['attack_button', 'attack', 'attack_btn'],
            'battle_screen': ['battle_screen', 'battle'],
            'exit_button': ['exit_button', 'exit']
        }
        self.friendly_names = {
            'enemy_button': 'kẻ địch',
            'start_button': 'nút Start',
            'reward_screen': 'màn hình nhận thưởng',
            'auto_button': 'chế độ tự động',
            'exit_button': 'nút thoát',
            'refresh_button': 'nút làm mới',
            'realm_raid_button': 'Realm Raid',
            'attack_button': 'nút Attack',
            'souls_button': 'Souls',
        }
        self.load_templates()
        self.last_start_error = None
        self.gui = None
        self._realm_no_target_count = 0
        self._last_refresh_time = 0
        self._refresh_cooldown = 5.0

    def _create_template_directories(self):
        os.makedirs(self.config['template_dir'], exist_ok=True)
        for candidates in self.template_folder_candidates.values():
            folder = candidates[0]
            folder_path = os.path.join(self.config['template_dir'], folder)
            os.makedirs(folder_path, exist_ok=True)

    def _get_existing_category_path(self, category):
        candidates = self.template_folder_candidates.get(category, [category])
        for folder in candidates:
            folder_path = os.path.join(self.config['template_dir'], folder)
            if os.path.isdir(folder_path):
                return folder_path
        return os.path.join(self.config['template_dir'], candidates[0])

    def _resolve_template_path(self, category_path, template_name):
        aliases = self.template_aliases.get(template_name, [template_name])
        exts = ['.png', '.PNG', '.jpg', '.JPG', '.jpeg', '.JPEG']
        for alias in aliases:
            for ext in exts:
                candidate = os.path.join(category_path, f"{alias}{ext}")
                if os.path.exists(candidate):
                    return candidate
        return None

    def load_templates(self):
        self.templates = {}
        base_path = get_resource_path("templates")
        for category, templates in self.template_mapping.items():
            # Tạo đường dẫn thư mục loại
            category_path = os.path.join(base_path, category)
            for template_name in templates:
                template_path = self._resolve_template_path(category_path, template_name)
                if template_path and os.path.exists(template_path):
                    if template_name not in self.templates:
                        self.templates[template_name] = {'region': None, 'desc': template_name}
                    # Load ảnh
                    self.templates[template_name]['image'] = cv2.imread(template_path, cv2.IMREAD_COLOR)
                    if self.config.get('debug'):
                        print(f"✅ Đã nạp: {category}/{template_name}")

    def _log_debug(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass

    def get_missing_templates_for_task(self, task_key):
        task = self.tasks.get(task_key, {})
        required_templates = []
        for step in task.get('steps', []):
            if step.get('action') not in ('find_click', 'wait_for'):
                continue
            if step.get('optional', False):
                continue
            target = step.get('target')
            if target and target not in required_templates:
                required_templates.append(target)

        if not required_templates:
            required_templates = self.template_mapping.get(task_key, [])
        return [name for name in required_templates if name not in self.templates]

    def _find_game_window_win32(self):
        if win32gui is None:
            return None
        for title in self.config.get('game_window_exact_titles', []):
            try:
                try:
                    hwnd = win32gui.FindWindow("UnityWndClass", title)
                except Exception:
                    hwnd = None
                if not hwnd:
                    hwnd = win32gui.FindWindow(None, title)
                if hwnd:
                    return hwnd
            except Exception:
                pass
        target_keyword = 'onmyoji'
        found = []

        def _enum(hwnd, lparam):
            try:
                text = win32gui.GetWindowText(hwnd) or ''
                if target_keyword in text.lower():
                    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                    w = right - left
                    h = bottom - top
                    if w > 100 and h > 60:
                        found.append(hwnd)
            except Exception:
                pass

        try:
            win32gui.EnumWindows(_enum, None)
        except Exception:
            pass
        return found[0] if found else None

    def _find_child_interaction_hwnd(self, parent_hwnd):
        if win32gui is None or not parent_hwnd:
            return parent_hwnd
        children = []

        def _enum_child(hwnd, lparam):
            try:
                cls = win32gui.GetClassName(hwnd) or ''
                text = win32gui.GetWindowText(hwnd) or ''
                if 'render' in cls.lower() or 'render' in text.lower() or cls in ('RenderWindow', 'Chrome_WidgetWin_1',
                                                                                  'UnityWndClass'):
                    children.append(hwnd)
            except Exception:
                pass

        try:
            win32gui.EnumChildWindows(parent_hwnd, _enum_child, None)
        except Exception:
            pass
        return children[0] if children else parent_hwnd

    def get_client_dimensions(self, hwnd):
        if win32gui is None:
            raise RuntimeError('win32gui not available')
        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            width = right - left
            height = bottom - top
            return (left, top, width, height)
        except Exception as e:
            self._log_debug(f"get_client_dimensions failed: {e}")
            raise

    def capture_background(self, hwnd):
        """Capture using MSS (Desktop coordinates) and math-pad to target size."""
        target_w = int(self.config.get('desired_client_w', 1136))
        target_h = int(self.config.get('desired_client_h', 640))

        if not hwnd or not win32gui.IsWindow(hwnd):
            self._log_debug('capture_background: invalid hwnd')
            return None

        try:
            _, _, actual_w, actual_h = self.get_client_dimensions(hwnd)
            if actual_w <= 0 or actual_h <= 0:
                return None

            client_pos = win32gui.ClientToScreen(hwnd, (0, 0))

            monitor = {
                "top": client_pos[1],
                "left": client_pos[0],
                "width": actual_w,
                "height": actual_h
            }

            with mss.mss() as sct:
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                img = img[:, :, :3]
                img = np.ascontiguousarray(img)

            if img.shape[1] < target_w or img.shape[0] < target_h:
                pad_bottom = max(0, target_h - img.shape[0])
                pad_right = max(0, target_w - img.shape[1])
                img = cv2.copyMakeBorder(img, 0, pad_bottom, 0, pad_right, cv2.BORDER_CONSTANT, value=(0, 0, 0))

            if img.shape[0] > target_h or img.shape[1] > target_w:
                img = img[0:target_h, 0:target_w]

            if img.shape != (target_h, target_w, 3):
                self._log_debug(f'Capture FAILED! Unexpected shape={img.shape}')
                return None

            debug_path = os.path.join(self.log_dir, 'debug_view.png')
            cv2.imwrite(debug_path, img)

            return img

        except Exception as e:
            self._log_debug(f'Capture exception: {e}')
            return None

    def click_in_game(self, hwnd, x, y):
        if win32gui is None:
            self._log_debug('pywin32 not available for click_in_game')
            return False
        if not hwnd:
            self._log_debug('No hwnd provided to click_in_game')
            return False
        try:
            try:
                lparam = win32api.MAKELONG(int(x), int(y))
            except Exception:
                lparam = (int(y) << 16) | (int(x) & 0xFFFF)

            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
            time.sleep(0.02)  # Trễ một chút để game nhận diện chuột đã di chuyển tới

            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(0.05)  # THÊM DÒNG NÀY: Giữ chuột 50ms (rất quan trọng)

            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            return True
        except Exception as e:
            self._log_debug(f"click_in_game failed: {e}")
            return False

    def capture_screen(self):
        try:
            hwnd = getattr(self, 'current_hwnd', None)
        except Exception:
            hwnd = None
        if hwnd and win32gui:
            try:
                root = hwnd
                try:
                    while True:
                        parent = win32gui.GetParent(root)
                        if parent and parent != 0:
                            root = parent
                        else:
                            break
                except Exception:
                    pass
                if win32gui.IsIconic(root):
                    try:
                        win32gui.ShowWindow(root, win32con.SW_RESTORE)
                        time.sleep(0.25)
                        self._log_debug('Restored minimized window for capture_screen')
                    except Exception:
                        pass
            except Exception:
                pass
            img = self.capture_background(hwnd)
            if img is not None:
                return img
        return None

    def find_template(self, screen_img, template_name, threshold=None):
        if threshold is None:
            threshold = self.template_threshold_overrides.get(template_name, self.config['confidence'])
        template_data = self.templates.get(template_name)
        if not template_data or 'image' not in template_data:
            if self.config['debug']:
                print(f"Template not found: {template_name}")
            return None
        template_img = template_data['image']
        if screen_img is None or getattr(screen_img, 'size', 0) == 0:
            return None
        try:
            th, tw = template_img.shape[:2]
            sh, sw = screen_img.shape[:2]
            if th > sh or tw > sw:
                self._log_debug(
                    f"Template {template_name} is larger than screen ({(th, tw)} > {(sh, sw)}); skipping match")
                return None
        except Exception:
            return None
        screen_gray = cv2.cvtColor(screen_img, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            h, w = template_img.shape[:2]
            return {'x': max_loc[0] + w // 2, 'y': max_loc[1] + h // 2, 'confidence': max_val}
        return None

    def find_all_templates(self, screen_img, template_name, threshold=None, max_results=10, min_distance=20):
        if threshold is None:
            threshold = self.template_threshold_overrides.get(template_name, self.config['confidence'])
        template_data = self.templates.get(template_name)
        if not template_data or 'image' not in template_data:
            return []
        template_img = template_data['image']
        if screen_img is None or getattr(screen_img, 'size', 0) == 0:
            return []
        try:
            th, tw = template_img.shape[:2]
            sh, sw = screen_img.shape[:2]
            if th > sh or tw > sw:
                self._log_debug(
                    f"Template {template_name} is larger than screen ({(th, tw)} > {(sh, sw)}); skipping multi-match")
                return []
        except Exception:
            return []
        screen_gray = cv2.cvtColor(screen_img, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        loc = np.where(result >= threshold)
        candidates = []
        h, w = template_img.shape[:2]
        for y, x in zip(*loc):
            conf = float(result[y, x])
            cx = int(x + w // 2)
            cy = int(y + h // 2)
            candidates.append({'x': cx, 'y': cy, 'confidence': conf})
        candidates.sort(key=lambda c: c['confidence'], reverse=True)
        selected = []
        for c in candidates:
            too_close = False
            for s in selected:
                dx = c['x'] - s['x']
                dy = c['y'] - s['y']
                if dx * dx + dy * dy <= (min_distance * min_distance):
                    too_close = True
                    break
            if not too_close:
                selected.append(c)
            if len(selected) >= max_results:
                break
        return selected

    def get_template_score(self, screen_img, template_name):
        template_data = self.templates.get(template_name)
        if not template_data or 'image' not in template_data:
            return None
        template_img = template_data['image']
        if screen_img is None or getattr(screen_img, 'size', 0) == 0:
            return None
        try:
            th, tw = template_img.shape[:2]
            sh, sw = screen_img.shape[:2]
            if th > sh or tw > sw:
                self._log_debug(
                    f"Template {template_name} is larger than screen ({(th, tw)} > {(sh, sw)}); cannot compute score without resizing template")
                return None
        except Exception:
            return None
        screen_gray = cv2.cvtColor(screen_img, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val

    def click(self, x, y, duration=0.0):
        try:
            hwnd = getattr(self, 'current_hwnd', None)
        except Exception:
            hwnd = None
        if hwnd and win32gui is not None:
            try:
                child = self._find_child_interaction_hwnd(hwnd)
                success = self.click_in_game(child, int(x), int(y))
                time.sleep(self.config.get('click_delay', 0.3))
                return success
            except Exception as e:
                self._log_debug(f"click (client) failed: {e}")
                return False
        else:
            self._log_debug('click: no client hwnd available')
            return False

    def find_and_click(self, template_name, threshold=None):
        screen_img = self.capture_screen()
        match = self.find_template(screen_img, template_name, threshold)
        if match:
            self.click(match['x'], match['y'])
            return True
        return False

    def execute_task_step(self):
        if not self.current_task:
            return False
        task = self.tasks[self.current_task]
        if self.current_task == 'realm_raid':
            return self.execute_realm_raid_logic()
        elif self.current_task == 'souls':
            return self.execute_souls_logic()
        if task.get('mode') == 'dynamic':
            return self.execute_dynamic_task_step(task)
        if task['current_step'] >= len(task['steps']):
            task['current_step'] = 0
        step = task['steps'][task['current_step']]
        action = step['action']
        self._log_debug(
            f"Task step: task={self.current_task}, step={task['current_step']}, action={action}, target={step.get('target', '-')}"
        )
        success = False
        if action == 'find_click':
            success = self.find_and_click(step['target'])
            if not success and step.get('optional', False):
                success = True
            if not success:
                friendly = self.friendly_names.get(step.get('target'), step.get('target'))
                print(f"Không tìm thấy {friendly} (target={step.get('target')})")
                score = self.get_template_score(self.capture_screen(), step['target'])
                threshold = self.template_threshold_overrides.get(step['target'], self.config['confidence'])
                self._log_debug(
                    f"Match debug: target={step['target']}, score={score}, threshold={threshold}"
                )
        elif action == 'wait_for':
            success = self.wait_for_template(step['target'], step.get('timeout', 10))
            if not success:
                if step.get('optional', False):
                    success = True
                else:
                    friendly = self.friendly_names.get(step.get('target'), step.get('target'))
                    print(f"Không tìm thấy {friendly} trong thời gian chờ (target={step.get('target')})")
        elif action == 'wait':
            time.sleep(step.get('time', 1))
            success = True
        elif action == 'repeat':
            task['current_step'] = 0
            return True
        else:
            if self.config['debug']:
                print(f"Unsupported action: {action}")
        if success:
            task['current_step'] += 1
            self._log_debug(f"Step success: task={self.current_task}, next_step={task['current_step']}")
        else:
            self._log_debug(f"Step failed: task={self.current_task}, step={task['current_step']}, action={action}")
        return success

    def execute_dynamic_task_step(self, task):
        steps = task.get('steps', [])
        screen_img = self.capture_screen()
        best_score_candidate = None
        matched_click_candidates = []
        matched_wait_candidates = []
        now = time.time()
        priority_map = {
            'reward_screen': 100,
            'exit_button': 95,
            'start_button': 90,
            'auto_button': 85,
            'enemy_button': 70,
            'refresh_button': 60,
            'realm_raid_button': 50
        }

        for idx, step in enumerate(steps):
            action = step.get('action')
            if action in ('repeat', 'wait'):
                continue
            target = step.get('target')
            if not target:
                continue

            if action == 'find_click':
                match = self.find_template(screen_img, target)
                if match:
                    blacklist_until = self.temp_target_blacklist_until.get(target, 0)
                    if now < blacklist_until:
                        continue
                    matched_click_candidates.append({
                        'idx': idx,
                        'target': target,
                        'confidence': match['confidence'],
                        'x': match['x'],
                        'y': match['y'],
                        'priority': priority_map.get(target, 10)
                    })
                score = self.get_template_score(screen_img, target)
                if score is not None and (best_score_candidate is None or score > best_score_candidate['score']):
                    best_score_candidate = {'target': target, 'score': score}
            elif action == 'wait_for':
                match = self.find_template(screen_img, target)
                if match:
                    matched_wait_candidates.append({
                        'idx': idx,
                        'target': target,
                        'confidence': match['confidence']
                    })

        if matched_click_candidates:
            matched_click_candidates.sort(key=lambda c: (c['priority'], c['confidence']), reverse=True)
            chosen = None
            for candidate in matched_click_candidates:
                cooldown = self.click_target_cooldowns.get(candidate['target'], 1.2)
                if (
                        self.last_click_target == candidate['target']
                        and (now - self.last_click_time) < cooldown
                ):
                    continue
                chosen = candidate
                break

            if chosen is None:
                chosen = matched_click_candidates[0]

            self._log_debug(
                f"Dynamic click: step={chosen['idx']}, target={chosen['target']}, "
                f"priority={chosen['priority']}, confidence={chosen['confidence']:.4f}"
            )
            self.click(chosen['x'], chosen['y'])
            if self.last_click_target == chosen['target']:
                self.same_target_click_count += 1
            else:
                self.same_target_click_count = 1
            self.last_click_target = chosen['target']
            self.last_click_time = now

            if self.same_target_click_count >= 4:
                block_seconds = 4.0 if chosen['target'] in ('enemy_button', 'exit_button') else 2.0
                self.temp_target_blacklist_until[chosen['target']] = now + block_seconds
                self._log_debug(
                    f"Anti-stuck: temporarily blacklist target={chosen['target']} for {block_seconds}s"
                )
                self.same_target_click_count = 0
            return True

        if matched_wait_candidates:
            best_wait = max(matched_wait_candidates, key=lambda c: c['confidence'])
            self._log_debug(
                f"Dynamic wait condition matched: step={best_wait['idx']}, "
                f"target={best_wait['target']}, confidence={best_wait['confidence']:.4f}"
            )
            return True

        if best_score_candidate:
            threshold = self.template_threshold_overrides.get(best_score_candidate['target'], self.config['confidence'])
            self._log_debug(
                f"Dynamic no match: best_target={best_score_candidate['target']}, score={best_score_candidate['score']:.4f}, threshold={threshold}"
            )
            if best_score_candidate['score'] < threshold:
                friendly = self.friendly_names.get(best_score_candidate['target'], best_score_candidate['target'])
                print(f"Không tìm thấy {friendly} (score={best_score_candidate['score']:.2f} < threshold={threshold})")
        else:
            self._log_debug("Dynamic no match: no valid target configured")
        return False

    def wait_for_template(self, template_name, timeout=10):
        start_time = time.time()
        while time.time() - start_time < timeout and self.config['active']:
            screen_img = self.capture_screen()
            if self.find_template(screen_img, template_name):
                return True
            time.sleep(0.3)
        return False

    def execute_realm_raid_logic(self):
        if not self.current_task:
            return False
        try:
            screen = self.capture_screen()
            if screen is None or getattr(screen, 'size', 0) == 0:
                return False

            # --- 0. CHECK ĐIỀU KIỆN KẾT THÚC (Hết vé/Hết người đánh) ---
            if self.find_template(screen, 'empty', threshold=0.9):
                print("🎉 Hoàn thành nhiệm vụ! Đang dừng tool...")
                if self.gui:
                    self.gui.update_status("HOÀN THÀNH NHIỆM VỤ!", color="orange")
                    self.gui.write_log("Đã thấy bảng Empty. Dừng bot.")
                self.stop_scanning(silent=True)
                return False

            # --- ƯU TIÊN SỐ 1: TRONG TRẬN (Battle Screen) ---
            if self.find_template(screen, 'battle_screen', threshold=0.75):
                self.game_state['screen'] = 'in_battle'
                if self.gui: self.gui.update_status("Đang trong trận...", color="blue")

                # Đợi cho đến khi màn hình Reward hiện ra (Victory tự nhảy qua nên không cần check)
                if self.wait_for_template('reward_screen', timeout=130):
                    self._log_debug("Thấy màn hình Reward. Đang chuẩn bị click thoát trận...")

                    # Nghỉ 1.5s để bảng quà hiện ra ổn định (tránh click khi nó đang bay ra)
                    time.sleep(1.5)

                    # Tìm lại tọa độ Reward để click chính xác vào hình đó
                    s_reward = self.capture_screen()
                    match_reward = self.find_template(s_reward, 'reward_screen', threshold=0.8)

                    if match_reward:
                        self._log_debug(f"Click Reward tại {match_reward['x']}, {match_reward['y']} để về Lobby.")
                        self.click(match_reward['x'], match_reward['y'])

                        if self.gui:
                            self.gui.write_log("Thắng trận! Đã nhận quà và quay về chọn địch.")
                            self.gui.increment_battle()  # Tăng bộ đếm trận thắng trên GUI
                    else:
                        # Click đại vào vùng an toàn để không bị kẹt
                        self.click(568, 100)

                return True

            # --- 2. BƯỚC ĐỆM: NÚT SẴN SÀNG (READY) ---
            # Nếu chưa vào Battle mà thấy nút Ready -> Bấm để bắt đầu đánh.
            ready_match = self.find_template(screen, 'ready_button', threshold=0.8)
            if ready_match:
                self._log_debug("👉 Thấy nút Ready. Đang chuẩn bị vào trận...")
                self.click(ready_match['x'], ready_match['y'])
                if self.gui: self.gui.write_log("Đã bấm Sẵn Sàng (Ready).")
                return True

            # --- 3. BẤM NÚT TẤN CÔNG (ATTACK) ---
            attack_match = self.find_template(screen, 'attack_button', threshold=0.75)
            if attack_match:
                self.game_state['screen'] = 'attack_window'
                self.click(attack_match['x'], attack_match['y'])
                if self.gui: self.gui.write_log("Bấm Attack.")
                return True

            # --- 4. TÌM VÀ CHỌN ĐỐI THỦ (Hỗ trợ cả Event) ---
            enemies = self.find_all_templates(screen, 'enemy_button', threshold=0.75)
            event_enemies = self.find_all_templates(screen, 'enemy_event', threshold=0.75)
            all_targets = enemies + event_enemies

            if all_targets:
                self.game_state['screen'] = 'selection'
                self._realm_no_target_count = 0
                chosen = all_targets[0]
                self._log_debug(f"Chọn đối thủ tại {chosen['x']},{chosen['y']}")
                self.click(chosen['x'], chosen['y'])
                if self.gui: self.gui.write_log("Đã chọn kẻ địch.")
                if self.wait_for_template('attack_button', timeout=3.0):
                    time.sleep(0.2)
                s_check = self.capture_screen()
                attack_match = self.find_template(s_check, 'attack_button', threshold=0.75)
                if attack_match:
                    self._log_debug("⚔️ Thấy nút Attack")
                    self.click(attack_match['x'], attack_match['y'])
                    time.sleep(1.0)
                return True

            # --- 5. XỬ LÝ KẸT TRONG LOBBY / REFRESH ---
            self._realm_no_target_count += 1
            now = time.time()
            if self._realm_no_target_count >= 3 and (now - self._last_refresh_time) > self._refresh_cooldown:
                refresh_match = self.find_template(screen, 'refresh_button')
                if refresh_match:
                    self.click(refresh_match['x'], refresh_match['y'])
                    if self.gui: self.gui.write_log("Đã bấm Làm mới danh sách.")
                self._last_refresh_time = now
                self._realm_no_target_count = 0
                return True

            return False
        except Exception as e:
            self._log_debug(f"execute_realm_raid_logic exception: {e}")
            return False

    def execute_souls_logic(self):
        if not self.current_task:
            return False

        try:
            screen = self.capture_screen()
            if screen is None or getattr(screen, 'size', 0) == 0:
                return False

            # --- 0. CHECK ĐIỀU KIỆN KẾT THÚC (Hết Sushi / Thể lực) ---
            # Chụp bảng báo hết Sushi (hoặc hình cái Sushi 0/100) lưu tên là 'no_sushi'
            if self.find_template(screen, 'no_sushi', threshold=0.85):
                self._log_debug("🛑 Hết Sushi (Thể lực)! Dừng auto.")
                if self.gui: self.gui.update_status("HOÀN THÀNH (HẾT SUSHI)!", color="orange")
                self.stop_scanning()
                return False

            # --- 1. STATE: NHẬN THƯỞNG (REWARD) ---
            reward_match = self.find_template(screen, 'reward_screen', threshold=0.8)
            if reward_match:
                self._log_debug("🎁 Đang ở màn hình nhận quà. Bấm để thoát.")
                self.click(reward_match['x'], reward_match['y'])
                time.sleep(1.0)  # Đợi chuyển cảnh về sảnh
                if self.gui: self.gui.increment_battle()
                return True

            # --- 2. STATE: TRONG TRẬN (BATTLE) ---
            if self.find_template(screen, 'battle_screen', threshold=0.75):
                self.game_state['screen'] = 'in_battle'
                if self.gui: self.gui.update_status("Đang kịch chiến Ngự Hồn...", color="blue")
                # Đợi cho đến khi màn hình Reward xuất hiện (tối đa 3-4 phút tùy team)
                self.wait_for_template('reward_screen', timeout=240)
                return True

            # --- 3. STATE: ĐỒNG Ý LỜI MỜI (Dành cho acc Clone/Member) ---
            # Chụp nút "Accept" màu xanh khi bị mời vào team
            accept_match = self.find_template(screen, 'accept_invite', threshold=0.8)
            if accept_match:
                self._log_debug("🤝 Có lời mời tổ đội! Đang Accept.")
                self.click(accept_match['x'], accept_match['y'])
                time.sleep(1.0)
                return True

            # --- 4. STATE: SẢNH CHỜ (LOBBY - Dành cho Leader) ---
            fight_match = self.find_template(screen, 'start_button', threshold=0.75)
            if fight_match:
                # Đếm số lượng dấu cộng (+)
                plus_signs = self.find_all_templates(screen, 'plus_sign', threshold=0.8)

                # Giả sử mặc định là đi team 3 người (0 dấu cộng thì mới chạy)
                if len(plus_signs) == 0:
                    self._log_debug("🔥 Đã đủ 3 người! Start game.")
                    if self.gui: self.gui.update_status("Đủ người, Bắt đầu!", color="green")
                    self.click(fight_match['x'], fight_match['y'])
                    time.sleep(1.5)  # Đợi game load vào trận
                else:
                    # Chưa đủ người, chỉ báo trạng thái chứ không click
                    self._log_debug(f"⏳ Đang đợi team... (Thiếu {len(plus_signs)} người)")
                    if self.gui: self.gui.update_status(f"Đang đợi team... ({3 - len(plus_signs)}/3)")
                return True

            return False

        except Exception as e:
            self._log_debug(f"execute_souls_logic exception: {e}")
            return False

    def start_scanning(self):
        def start_scanning(self):
            if not self.check_game_window():
                print("❌ Lỗi: Không tìm thấy cửa sổ Onmyoji!")
                self.stop_scanning(silent=True)
                return False
            self.config['active'] = True
            self.thread = threading.Thread(target=self.scanning_loop, daemon=True)
            self.thread.start()
            return True

        self.load_templates()
        self._log_debug(f"Start requested for task={self.current_task}")
        self.last_start_error = None
        missing_templates = self.get_missing_templates_for_task(self.current_task)
        if missing_templates:
            self._log_debug(f"Start blocked: missing templates={missing_templates}")
            self.last_start_error = f"Thiếu template cho task: {', '.join(missing_templates)}"
            print(f"Start blocked: missing templates: {missing_templates}")
            return False

        try:
            hwnd = self._find_game_window_win32()
        except Exception:
            hwnd = None
        if not hwnd or hwnd == 0:
            msg = 'KHÔNG TÌM THẤY GAME. Vui lòng mở Onmyoji trước khi chạy tool!'
            print(msg)
            try:
                self._log_debug(msg)
            except Exception:
                pass
            if self.gui:
                self.gui.update_status(msg)
            sys.exit(1)
            return False

        self.current_hwnd = hwnd
        try:
            self._log_debug(f"Ensuring client size for hwnd={hwnd}")
            self.force_client_size(
                hwnd,
                int(self.config.get('desired_client_w', 1136)),
                int(self.config.get('desired_client_h', 640)),
            )
            desired_w = int(self.config.get('desired_client_w', 1136))
            desired_h = int(self.config.get('desired_client_h', 640))
            try:
                l, t, w, h = self.get_client_dimensions(hwnd)
            except Exception:
                l, t, w, h = (0, 0, desired_w, desired_h)
            dw = abs(w - desired_w)
            dh = abs(h - desired_h)
            if dw <= 2 and dh <= 2:
                self.current_window = types.SimpleNamespace(_hWnd=hwnd, left=0, top=0, width=w, height=h)
                self.game_region = (0, 0, w, h)
                self._log_debug(f"Start: client region accepted within tolerance: {self.game_region}")
            else:
                try:
                    self.force_client_size(hwnd, desired_w, desired_h)
                    l, t, w, h = self.get_client_dimensions(hwnd)
                    self.current_window = types.SimpleNamespace(_hWnd=hwnd, left=0, top=0, width=w, height=h)
                    self.game_region = (0, 0, w, h)
                    self._log_debug(f"Start: client region set to {self.game_region} after enforced resize")
                except Exception as e:
                    self._log_debug(f"Failed to enforce client size on start: {e}")
                    self.current_window = types.SimpleNamespace(_hWnd=hwnd, left=0, top=0, width=w, height=h)
                    self.game_region = (0, 0, w, h)
        except Exception as e:
            self._log_debug(f"Failed to enforce client size on start: {e}")

        self.config['active'] = True
        try:
            self.scanning_thread = threading.Thread(target=self.scanning_loop)
            self.scanning_thread.daemon = True
            self.scanning_thread.start()
            self._log_debug("Scanning started")
            print("Scanning thread started")
        except Exception as e:
            self._log_debug(f"Failed to start scanning thread: {e}")
            print(f"Failed to start scanning thread: {e}")
            self.last_start_error = str(e)
            return False
        return True

    def force_client_size(self, hwnd, target_w=1136, target_h=640):
        if win32gui is None:
            self._log_debug('pywin32 not available for force_client_size')
            return False
        try:
            if not hwnd or hwnd == 0:
                self._log_debug('force_client_size called with invalid hwnd')
                return False

            try:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.2)
            except Exception:
                pass

            parent_hwnd = win32gui.GetParent(hwnd)
            if parent_hwnd == 0:
                parent_hwnd = hwnd
            style = win32gui.GetWindowLong(parent_hwnd, win32con.GWL_STYLE)
            ex_style = win32gui.GetWindowLong(parent_hwnd, win32con.GWL_EXSTYLE)
            rect = wintypes.RECT(0, 0, int(target_w), int(target_h))
            ok = ctypes.windll.user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
            if not ok:
                self._log_debug("force_client_size: AdjustWindowRectEx failed")
                return False
            total_w = int(rect.right - rect.left)
            total_h = int(rect.bottom - rect.top)
            win32gui.SetWindowPos(
                parent_hwnd,
                0,
                0,
                0,
                total_w,
                total_h,
                win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_ASYNCWINDOWPOS,
            )
            time.sleep(0.5)
            self._log_debug(
                f"force_client_size applied: hwnd={hwnd}, parent_hwnd={parent_hwnd}, client_target=({target_w},{target_h}), outer=({total_w},{total_h})"
            )
            return True
        except Exception as e:
            self._log_debug(f"force_client_size failed: {e}")
            return False

    def scanning_loop(self):
        loop_count = 0
        while self.config['active']:
            try:
                success = self.execute_task_step()
                loop_count += 1
                if loop_count % 5 == 0:
                    print(
                        f"Scanning heartbeat: loop={loop_count}, active={self.config['active']}, task={self.current_task}, last_success={success}")
                if self.gui:
                    task_name = self.tasks[self.current_task]['name'] if self.current_task else "N/A"
                    status = "Đang chạy" if success else "Đang tìm mục tiêu..."
                    self.gui.update_status(f"{status} | Nhiệm vụ: {task_name}")
                if not success and loop_count % 10 == 0:
                    print("No action performed in this loop")
                time.sleep(self.config['scan_interval'])
            except Exception as e:
                self._log_debug(f"Exception in scanning_loop: {e}")
                print(f"Exception in scanning_loop: {e}")
                time.sleep(1)

    def stop_scanning(self, silent=False):
        """Dừng vòng lặp quét"""
        self.config['active'] = False
        if not silent:
            print("\n🛑 Đã nhận lệnh dừng từ người dùng!")

        self._log_debug("Scanning stopped.")

        # Cập nhật GUI nếu có
        if self.gui:
            self.gui.start_button.config(state='normal')
            self.gui.stop_button.config(state='disabled')

    def create_template(self, template_name, category=None):
        if category is None:
            for cat, templates in self.template_mapping.items():
                if template_name in templates:
                    category = cat
                    break
            if category is None:
                category = 'souls'

        try:
            template_img = self.capture_screen()
            category_path = self._get_existing_category_path(category)
            template_path = os.path.join(category_path, f"{template_name}.png")
            cv2.imwrite(template_path, template_img)
            if self.gui:
                self.gui.update_status(f"Đã lưu ảnh mẫu thô: {category}/{template_name}.png")
            return True
        except Exception as e:
            if self.gui:
                self.gui.update_status(f"Lỗi khi tạo mẫu: {str(e)}")
            return False