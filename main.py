# clearMem - 定时清除目录程序
# 支持：定时清除、 RDP登录自动清除、 系统托盘

import os
import sys
import json
import time
import shutil
import logging
import threading
import subprocess
from datetime import datetime, timedelta
from tkinter import *
from tkinter import messagebox, ttk
import pystray
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('clearMem.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.json'

DEFAULT_CONFIG = {
    'target_path': r'D:\cache\.ws',
    'enable_timer': False,
    'timer_type': 'interval',
    'timer_interval_minutes': 60,
    'timer_time': '03:00',
    'enable_rdp': True
}

config = DEFAULT_CONFIG.copy()

def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                config.update(loaded)
                logger.info("配置已加载")
        except Exception as e:
            logger.error(f"加载配置失败: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("配置已保存")
    except Exception as e:
        logger.error(f"保存配置失败: {e}")

def clear_directory(path):
    if not os.path.exists(path):
        logger.warning(f"目录不存在: {path}")
        return False
    
    try:
        count = 0
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    count += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    count += 1
            except Exception as e:
                logger.error(f"删除失败 {item_path}: {e}")
        
        logger.info(f"已清理目录 {path}，删除 {count} 个项目")
        return True
    except Exception as e:
        logger.error(f"清理目录失败: {e}")
        return False

class RDPMonitor:
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_logon_time = 0
    
    def check_rdp_logon(self):
        try:
            script = '''
$events = Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4624; StartTime=(Get-Date).AddMinutes(-2)} -MaxEvents 5 -ErrorAction SilentlyContinue
foreach ($e in $events) {
    $xml = [xml]$e.ToXml()
    $data = $xml.Event.EventData
    $logonType = ($data | Where-Object {$_.Name -eq 'LogonType'}).'#text'
    $time = ($data | Where-Object {$_.Name -eq 'TimeCreated'}).'#text'
    if ($logonType -eq '10') {
        Write-Output $time
    }
}
'''
            result = subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True, text=True, timeout=10
            )
            if result.stdout.strip():
                return True
        except Exception as e:
            logger.error(f"检查RDP登录失败: {e}")
        return False
    
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("RDP监控已启动")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("RDP监控已停止")
    
    def _monitor_loop(self):
        while self.running:
            try:
                if self.check_rdp_logon():
                    current_time = time.time()
                    if current_time - self.last_logon_time > 60:
                        logger.info("检测到RDP登录，清除目录")
                        clear_directory(config['target_path'])
                        self.last_logon_time = current_time
            except Exception as e:
                logger.error(f"RDP监控错误: {e}")
            time.sleep(10)

class TimerScheduler:
    def __init__(self):
        self.running = False
        self.thread = None
    
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.thread.start()
        logger.info("定时任务已启动")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("定时任务已停止")
    
    def _schedule_loop(self):
        while self.running:
            try:
                if config['enable_timer']:
                    if config['timer_type'] == 'interval':
                        interval = config.get('timer_interval_minutes', 60) * 60
                        time.sleep(interval)
                        clear_directory(config['target_path'])
                    else:
                        target_time = config.get('timer_time', '03:00')
                        now = datetime.now()
                        hour, minute = map(int, target_time.split(':'))
                        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        if target <= now:
                            target += timedelta(days=1)
                        wait_seconds = (target - now).total_seconds()
                        time.sleep(wait_seconds)
                        clear_directory(config['target_path'])
                else:
                    time.sleep(60)
            except Exception as e:
                logger.error(f"定时任务错误: {e}")
                time.sleep(60)

rdp_monitor = RDPMonitor()
timer_scheduler = TimerScheduler()

def create_tray_icon():
    image = Image.new('RGB', (64, 64), color='#2196F3')
    return image

def setup_tray():
    icon = pystray.Icon('clearMem', create_tray_icon(), 'ClearMem', menu={
        '显示': lambda _: show_window(),
        '清除缓存': lambda _: clear_directory(config['target_path']),
        '退出': lambda _: on_exit()
    })
    return icon

tray_icon = None
root = None

def show_window():
    global root
    if root:
        root.deiconify()
        root.state('normal')
        root.lift()

def hide_to_tray():
    if root:
        root.withdraw()

def on_exit():
    save_config()
    rdp_monitor.stop()
    timer_scheduler.stop()
    if tray_icon:
        tray_icon.stop()
    sys.exit()

def start_services():
    if config.get('enable_rdp', True):
        rdp_monitor.start()
    if config.get('enable_timer', False):
        timer_scheduler.start()

class App:
    def __init__(self):
        global root
        root = Tk()
        root.title('ClearMem - 定时清除目录')
        root.geometry('500x400')
        root.protocol('WM_DELETE_WINDOW', hide_to_tray)
        
        self.create_widgets()
        self.load_settings()
    
    def create_widgets(self):
        notebook = ttk.Notebook(root)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        frame_basic = ttk.Frame(notebook)
        frame_timer = ttk.Frame(notebook)
        frame_about = ttk.Frame(notebook)
        
        notebook.add(frame_basic, text='基础设置')
        notebook.add(frame_timer, text='定时设置')
        notebook.add(frame_about, text='关于')
        
        self.frame_timer = frame_timer
        
        self.create_basic_tab(frame_basic)
        self.create_timer_tab(frame_timer)
        self.create_about_tab(frame_about)
        
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill=X, padx=10, pady=5)
        
        ttk.Button(btn_frame, text='保存设置', command=self.save_settings).pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text='立即清除', command=self.immediate_clear).pack(side=RIGHT)
    
    def create_basic_tab(self, parent):
        ttk.Label(parent, text='目标目录:').grid(row=0, column=0, sticky=W, padx=10, pady=10)
        
        self.path_var = StringVar(value=config.get('target_path', ''))
        ttk.Entry(parent, textvariable=self.path_var, width=40).grid(row=0, column=1, padx=10, pady=10)
        ttk.Button(parent, text='浏览', command=self.browse_path).grid(row=0, column=2, padx=5)
        
        self.rdp_var = BooleanVar(value=config.get('enable_rdp', True))
        ttk.Checkbutton(parent, text='启用RDP登录自动清除', variable=self.rdp_var).grid(row=1, column=0, columnspan=3, sticky=W, padx=10)
    
    def create_timer_tab(self, parent):
        self.timer_enable_var = BooleanVar(value=config.get('enable_timer', False))
        ttk.Checkbutton(parent, text='启用定时清除', variable=self.timer_enable_var, command=self.toggle_timer_type).grid(row=0, column=0, columnspan=3, sticky=W, padx=10, pady=10)
        
        self.timer_type_var = StringVar(value=config.get('timer_type', 'interval'))
        ttk.Radiobutton(parent, text='间隔清除', variable=self.timer_type_var, value='interval', command=self.toggle_timer_type).grid(row=1, column=0, sticky=W, padx=20)
        
        self.interval_var = IntVar(value=config.get('timer_interval_minutes', 60))
        self.interval_spin = ttk.Spinbox(parent, from_=1, to=1440, textvariable=self.interval_var, width=10)
        self.interval_spin.grid(row=1, column=1, padx=5)
        
        ttk.Radiobutton(parent, text='指定时间清除', variable=self.timer_type_var, value='time', command=self.toggle_timer_type).grid(row=2, column=0, sticky=W, padx=20)
        
        self.time_var = StringVar(value=config.get('timer_time', '03:00'))
        self.time_entry = ttk.Entry(parent, textvariable=self.time_var, width=10)
        self.time_entry.grid(row=2, column=1, padx=5, sticky=W)
        
        self.toggle_timer_type()
    
    def create_about_tab(self, parent):
        ttk.Label(parent, text='ClearMem').pack(pady=20)
        ttk.Label(parent, text='版本: 1.0.0').pack()
        ttk.Label(parent, text='功能: 定时/RDP登录自动清除目录').pack(pady=10)
        ttk.Label(parent, text='目录: D:\\cache\\.ws').pack()
    
    def toggle_timer_type(self):
        parent = self.frame_timer
        state = 'normal' if self.timer_enable_var.get() else 'disabled'
        
        widgets_to_disable = []
        if hasattr(self, 'interval_spin'):
            widgets_to_disable.append(self.interval_spin)
        if hasattr(self, 'time_entry'):
            widgets_to_disable.append(self.time_entry)
        
        for widget in widgets_to_disable:
            try:
                widget.configure(state=state)
            except:
                pass
    
    def browse_path(self):
        from tkinter import filedialog
        path = filedialog.askdirectory()
        if path:
            self.path_var.set(path)
    
    def load_settings(self):
        self.path_var.set(config.get('target_path', ''))
        self.rdp_var.set(config.get('enable_rdp', True))
        self.timer_enable_var.set(config.get('enable_timer', False))
        self.timer_type_var.set(config.get('timer_type', 'interval'))
        self.interval_var.set(config.get('timer_interval_minutes', 60))
        self.time_var.set(config.get('timer_time', '03:00'))
        self.toggle_timer_type()
    
    def save_settings(self):
        global config
        config['target_path'] = self.path_var.get()
        config['enable_rdp'] = self.rdp_var.get()
        config['enable_timer'] = self.timer_enable_var.get()
        config['timer_type'] = self.timer_type_var.get()
        config['timer_interval_minutes'] = self.interval_var.get()
        config['timer_time'] = self.time_var.get()
        
        save_config()
        
        rdp_monitor.stop()
        timer_scheduler.stop()
        time.sleep(0.5)
        
        if config.get('enable_rdp', True):
            rdp_monitor.start()
        if config.get('enable_timer', False):
            timer_scheduler.start()
        
        messagebox.showinfo('提示', '设置已保存')
    
    def immediate_clear(self):
        if clear_directory(config['target_path']):
            messagebox.showinfo('提示', '目录已清除')
        else:
            messagebox.showerror('错误', '清除失败')

def main():
    load_config()
    
    global tray_icon
    tray_icon = setup_tray()
    
    thread = threading.Thread(target=lambda: tray_icon.run(), daemon=True)
    thread.start()
    
    start_services()
    
    app = App()
    root.mainloop()

if __name__ == '__main__':
    main()