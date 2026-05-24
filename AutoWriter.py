# AutoWriter.py
# ENERGY PRO BLE Beacon Universal Remote - Windows Desktop Version
# Windows 筆電版 BLE Beacon 遙控器
#
# 需求：
#   pip install winsdk
#
# 打包 EXE：
#   pip install pyinstaller winsdk
#   pyinstaller --onefile --windowed --name BluetoothRemotePC AutoWriter.py
#
# 注意：
#   不是每台 Windows 筆電藍牙都支援 BLE Advertising。
#   如果只能掃描不能發送，請改用支援 BLE Advertising 的藍牙晶片或 Android APK。

import json
import os
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

APP_TITLE = "ENERGY PRO 藍芽遙控器"
DATA_FILE = "remote_panels.json"

COMPANY_ID = 0x0118

DEFAULT_MAJOR = 0x5576
DEFAULT_MINOR = 0x0003
DEFAULT_CONTROL_DEVICE_CODE = 0x18
DEFAULT_PAIR_PANEL_CODE = 0x25
DEFAULT_ZONE = 0x03

COMMAND_DURATION_MS = 1200
MIN_COMMAND_INTERVAL_MS = 1300

try:
    from winsdk.windows.devices.bluetooth.advertisement import (
        BluetoothLEAdvertisement,
        BluetoothLEAdvertisementPublisher,
        BluetoothLEManufacturerData,
    )
    from winsdk.windows.storage.streams import DataWriter
    WINSDK_AVAILABLE = True
except Exception:
    WINSDK_AVAILABLE = False


class BleAdvertiser:
    def __init__(self):
        self.publisher = None

    def _make_buffer(self, data: bytes):
        writer = DataWriter()
        writer.write_bytes(data)
        return writer.detach_buffer()

    def advertise_manufacturer_data(self, company_id: int, payload: bytes, duration_ms: int):
        if not WINSDK_AVAILABLE:
            raise RuntimeError("尚未安裝 winsdk，請先執行：pip install winsdk")

        advertisement = BluetoothLEAdvertisement()

        manufacturer_data = BluetoothLEManufacturerData()
        manufacturer_data.company_id = company_id
        manufacturer_data.data = self._make_buffer(payload)

        advertisement.manufacturer_data.append(manufacturer_data)

        self.publisher = BluetoothLEAdvertisementPublisher(advertisement)
        self.publisher.start()

        time.sleep(duration_ms / 1000.0)

        self.publisher.stop()
        self.publisher = None

    def stop(self):
        try:
            if self.publisher is not None:
                self.publisher.stop()
        except Exception:
            pass
        self.publisher = None


class RemoteApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("430x760")
        self.root.minsize(390, 680)

        self.ble = BleAdvertiser()
        self.panels = self.load_panels()

        self.current_index = None
        self.sequence = 1
        self.is_sending = False
        self.last_send_time = 0

        self.brightness = 50
        self.color_temp = 50

        self.main = tk.Frame(root, bg="#dceafa")
        self.main.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="等待操作")
        self.progress_var = tk.IntVar(value=0)

        self.show_panel_list()

        self.sync_time_silent()
        self.start_auto_time_sync()

    # -----------------------------
    # Storage
    # -----------------------------

    def load_panels(self):
        if not os.path.exists(DATA_FILE):
            return []
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_panels(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.panels, f, ensure_ascii=False, indent=2)

    def make_new_panel(self):
        panel_id = random.randint(0x1000, 0xFFFF)
        return {
            "name": f"新面板 {len(self.panels) + 1}",
            "type": "調光調色感應燈具",
            "major": panel_id,
            "minor": DEFAULT_MINOR,
            "control_device_code": DEFAULT_CONTROL_DEVICE_CODE,
            "pair_panel_code": DEFAULT_PAIR_PANEL_CODE,
            "zone": DEFAULT_ZONE,
            "paired": False,
            "sleep_seconds": 50,
            "pir_seconds": 50,
        }

    # -----------------------------
    # UI helpers
    # -----------------------------

    def clear(self):
        for w in self.main.winfo_children():
            w.destroy()

    def frame_shell(self, title):
        self.clear()

        outer = tk.Frame(self.main, bg="#dceafa", padx=16, pady=16)
        outer.pack(fill="both", expand=True)

        card = tk.Frame(
            outer,
            bg="#b6cde7",
            highlightbackground="#2f5d9b",
            highlightthickness=2,
            padx=16,
            pady=14,
        )
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text=title,
            font=("Microsoft JhengHei UI", 16, "bold"),
            fg="#26384f",
            bg="#b6cde7",
        ).pack(pady=(0, 6))

        tk.Label(
            card,
            textvariable=self.status_var,
            font=("Microsoft JhengHei UI", 10),
            fg="#30425a",
            bg="#b6cde7",
        ).pack(pady=(0, 4))

        progress = ttk.Progressbar(card, maximum=100, variable=self.progress_var)
        progress.pack(fill="x", pady=(0, 10))

        return card

    def big_button(self, parent, text, command, bg="#dfe9f6", fg="#26384f", height=2):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Microsoft JhengHei UI", 13, "bold"),
            bg=bg,
            fg=fg,
            activebackground="#cbdcf1",
            activeforeground=fg,
            relief="ridge",
            bd=2,
            height=height,
        )
        btn.pack(fill="x", padx=8, pady=6)
        return btn

    def small_grid_button(self, parent, text, command, bg="#dfe9f6"):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Microsoft JhengHei UI", 10, "bold"),
            bg=bg,
            fg="#26384f",
            activebackground="#cbdcf1",
            relief="ridge",
            bd=2,
            width=10,
            height=3,
        )
        return btn

    def row(self, parent):
        f = tk.Frame(parent, bg="#b6cde7")
        f.pack(fill="x", pady=2)
        return f

    # -----------------------------
    # Page 1
    # -----------------------------

    def show_panel_list(self):
        card = self.frame_shell("遙控器面板列表")

        list_frame = tk.Frame(card, bg="#b6cde7")
        list_frame.pack(fill="both", expand=True, pady=6)

        if not self.panels:
            tk.Label(
                list_frame,
                text="尚未新增任何面板",
                font=("Microsoft JhengHei UI", 14),
                bg="#dfe9f6",
                fg="#5b6d82",
                height=8,
            ).pack(fill="x", padx=10, pady=20)
        else:
            for i, panel in enumerate(self.panels):
                text = f"{panel['name']}\n{panel['type']}\n{'已配對' if panel.get('paired') else '未配對'}"
                btn = tk.Button(
                    list_frame,
                    text=text,
                    font=("Microsoft JhengHei UI", 12, "bold"),
                    bg="#dfe9f6",
                    fg="#26384f",
                    relief="ridge",
                    bd=2,
                    height=3,
                    command=lambda idx=i: self.open_panel(idx),
                )
                btn.pack(fill="x", padx=10, pady=6)
                btn.bind("<Button-3>", lambda e, idx=i: self.show_pair_page(idx))
                btn.bind("<Double-Button-1>", lambda e, idx=i: self.show_pair_page(idx))

        action = self.row(card)

        tk.Button(
            action,
            text="增加",
            command=self.add_panel,
            font=("Microsoft JhengHei UI", 12, "bold"),
            bg="#5f8eca",
            fg="white",
            width=10,
            height=2,
        ).pack(side="left", expand=True, padx=12, pady=8)

        tk.Button(
            action,
            text="刪除",
            command=self.delete_panel,
            font=("Microsoft JhengHei UI", 12, "bold"),
            bg="#5f8eca",
            fg="white",
            width=10,
            height=2,
        ).pack(side="left", expand=True, padx=12, pady=8)

        tk.Label(
            card,
            text="短按：進入控制面板　｜　雙擊或右鍵：進入配對設定頁",
            font=("Microsoft JhengHei UI", 9),
            bg="#b6cde7",
            fg="#26384f",
        ).pack(pady=8)

    def add_panel(self):
        panel = self.make_new_panel()
        self.panels.append(panel)
        self.save_panels()
        self.current_index = len(self.panels) - 1
        self.show_pair_page(self.current_index)

    def delete_panel(self):
        if not self.panels:
            self.status_var.set("目前沒有面板可刪除")
            return

        if self.current_index is None:
            idx = len(self.panels) - 1
        else:
            idx = self.current_index

        name = self.panels[idx]["name"]
        del self.panels[idx]
        self.current_index = None
        self.save_panels()
        self.status_var.set(f"已刪除：{name}")
        self.show_panel_list()

    def open_panel(self, idx):
        self.current_index = idx
        panel = self.panels[idx]

        if not panel.get("paired", False):
            self.show_pair_page(idx)
            return

        self.show_control_page(idx)

    # -----------------------------
    # Pair page
    # -----------------------------

    def show_pair_page(self, idx):
        self.current_index = idx
        panel = self.panels[idx]
        card = self.frame_shell("配對 / 設定頁")

        tk.Label(card, text="設備名稱", font=("Microsoft JhengHei UI", 11, "bold"), bg="#b6cde7").pack()
        name_var = tk.StringVar(value=panel["name"])
        tk.Entry(
            card,
            textvariable=name_var,
            font=("Microsoft JhengHei UI", 14),
            justify="center",
            bg="#edf4fc",
            fg="#26384f",
        ).pack(fill="x", padx=14, pady=6, ipady=5)

        tk.Label(card, text="睡眠時間", font=("Microsoft JhengHei UI", 11, "bold"), bg="#b6cde7").pack(pady=(8, 0))

        sleep_var = tk.IntVar(value=int(panel.get("sleep_seconds", 50)))
        sleep_frame = self.row(card)
        tk.Button(sleep_frame, text="-", command=lambda: sleep_var.set(max(0, sleep_var.get() - 10)), width=5).pack(side="left", expand=True, padx=6)
        tk.Label(sleep_frame, textvariable=sleep_var, font=("Microsoft JhengHei UI", 14, "bold"), bg="#edf4fc", width=8).pack(side="left", expand=True, padx=6)
        tk.Button(sleep_frame, text="+", command=lambda: sleep_var.set(min(600, sleep_var.get() + 10)), width=5).pack(side="left", expand=True, padx=6)

        tk.Label(card, text="選擇面板", font=("Microsoft JhengHei UI", 11, "bold"), bg="#b6cde7").pack(pady=(8, 0))

        type_var = tk.StringVar(value=panel["type"])
        type_box = ttk.Combobox(
            card,
            textvariable=type_var,
            values=["調光調色感應燈具", "簡易調光調色燈具", "調光燈具", "智慧插座"],
            state="readonly",
            font=("Microsoft JhengHei UI", 12),
        )
        type_box.pack(fill="x", padx=14, pady=8)

        self.big_button(
            card,
            "配對",
            lambda: self.save_and_pair(idx, name_var.get(), type_var.get(), sleep_var.get()),
            bg="#5f8eca",
            fg="white",
            height=2,
        )

        self.big_button(card, "返回列表", self.show_panel_list, bg="#dfe9f6")

        tk.Label(
            card,
            text="進行配對：\n在欲配對燈具重新開機的五秒鐘內按下配對鈕。\n配對成功後會閃三下。",
            font=("Microsoft JhengHei UI", 9),
            bg="#b6cde7",
            fg="#26384f",
            justify="center",
        ).pack(pady=8)

    def save_and_pair(self, idx, name, panel_type, sleep_seconds):
        panel = self.panels[idx]
        panel["name"] = name or "未命名面板"
        panel["type"] = panel_type
        panel["sleep_seconds"] = int(sleep_seconds)
        self.apply_panel_setting(panel)
        panel["paired"] = True
        self.save_panels()

        self.send_pair_command(panel)

    # -----------------------------
    # Control pages
    # -----------------------------

    def show_control_page(self, idx):
        panel = self.panels[idx]
        panel_type = panel["type"]

        if panel_type == "調光燈具":
            self.show_dimmer_panel(idx)
        elif panel_type == "智慧插座":
            self.show_smart_plug_panel(idx)
        else:
            self.show_light_panel(idx)

    def show_light_panel(self, idx):
        panel = self.panels[idx]
        panel_type = panel["type"]
        has_pir = panel_type == "調光調色感應燈具"
        has_color = panel_type != "調光燈具"

        card = self.frame_shell(panel["name"])

        top = self.row(card)
        tk.Button(top, text="←", command=self.show_panel_list, width=5, font=("Microsoft JhengHei UI", 14, "bold")).pack(side="left", padx=4)
        tk.Label(top, text=panel["name"], bg="#b6cde7", fg="#26384f", font=("Microsoft JhengHei UI", 13, "bold")).pack(side="left", expand=True)
        tk.Button(top, text="⏰", command=lambda: self.show_schedule_page(idx), width=5, font=("Microsoft JhengHei UI", 14)).pack(side="right", padx=4)

        power_row = self.row(card)
        self.small_grid_button(power_row, "⏻\n電源", lambda: self.send_command(panel, "電源", 0x01, [0x01]), bg="#9db9e8").pack(side="left", expand=True, padx=6)
        self.small_grid_button(power_row, "☾\n夜燈", lambda: self.send_command(panel, "夜燈", 0x02, [0x01]), bg="#9db9e8").pack(side="left", expand=True, padx=6)

        self.add_slider(card, "亮度", self.brightness, lambda v: self.set_brightness(panel, v))

        if has_color:
            self.add_slider(card, "色溫", self.color_temp, lambda v: self.set_color(panel, v), warm=True)

        tk.Label(
            card,
            text="長按記憶鍵可記憶目前的亮度及色溫",
            bg="#b6cde7",
            fg="white",
            font=("Microsoft JhengHei UI", 9, "bold"),
        ).pack(pady=(4, 2))

        mem = self.row(card)
        for i in range(1, 5):
            b = self.small_grid_button(mem, f"⚙\n記憶{i}", lambda g=i: self.send_command(panel, f"記憶{g}", 0x03, [g]), bg="#7fa7d8")
            b.bind("<Button-3>", lambda e, g=i: self.save_memory(panel, g))
            b.bind("<Double-Button-1>", lambda e, g=i: self.save_memory(panel, g))
            b.pack(side="left", expand=True, padx=3)

        func = self.row(card)

        if has_pir:
            pir_btn = self.small_grid_button(func, "🏃☾\n人體感應", lambda: self.send_command(panel, "人體感應", 0x11, []), bg="#7fa7d8")
            pir_btn.bind("<Button-3>", lambda e: self.ask_delay_and_send(panel, "人體感應延遲", 0x15))
            pir_btn.bind("<Double-Button-1>", lambda e: self.ask_delay_and_send(panel, "人體感應延遲", 0x15))
            pir_btn.pack(side="left", expand=True, padx=3)

        sleep_btn = self.small_grid_button(func, "Zzz\n睡眠模式", lambda: self.send_command(panel, "睡眠模式", 0x10, []), bg="#7fa7d8")
        sleep_btn.bind("<Button-3>", lambda e: self.ask_delay_and_send(panel, "睡眠延遲", 0x16))
        sleep_btn.bind("<Double-Button-1>", lambda e: self.ask_delay_and_send(panel, "睡眠延遲", 0x16))
        sleep_btn.pack(side="left", expand=True, padx=3)

        self.small_grid_button(func, "🔔\n關閉鬧鐘", lambda: self.send_command(panel, "關閉鬧鐘", 0x09, []), bg="#7fa7d8").pack(side="left", expand=True, padx=3)
        self.small_grid_button(func, "⏱\n定時", lambda: self.show_schedule_page(idx), bg="#7fa7d8").pack(side="left", expand=True, padx=3)

        tk.Label(
            card,
            text="開啟 感應 / 睡眠：燈會閃一下\n關閉 感應 / 睡眠：燈會閃二下",
            bg="#b6cde7",
            fg="#26384f",
            font=("Microsoft JhengHei UI", 8),
        ).pack(pady=4)

    def show_dimmer_panel(self, idx):
        panel = self.panels[idx]
        card = self.frame_shell(panel["name"])

        top = self.row(card)
        tk.Button(top, text="←", command=self.show_panel_list, width=5, font=("Microsoft JhengHei UI", 14, "bold")).pack(side="left", padx=4)
        tk.Label(top, text=panel["name"], bg="#b6cde7", fg="#26384f", font=("Microsoft JhengHei UI", 13, "bold")).pack(side="left", expand=True)
        tk.Button(top, text="⏰", command=lambda: self.show_schedule_page(idx), width=5, font=("Microsoft JhengHei UI", 14)).pack(side="right", padx=4)

        power_row = self.row(card)
        self.small_grid_button(power_row, "⏻\n電源", lambda: self.send_command(panel, "電源", 0x01, [0x01]), bg="#9db9e8").pack(side="left", expand=True, padx=6)
        self.small_grid_button(power_row, "☾\n夜燈", lambda: self.send_command(panel, "夜燈", 0x02, [0x01]), bg="#9db9e8").pack(side="left", expand=True, padx=6)

        self.add_slider(card, "亮度", self.brightness, lambda v: self.set_brightness(panel, v))

        mem = self.row(card)
        for i in range(1, 5):
            b = self.small_grid_button(mem, f"⚙\n記憶{i}", lambda g=i: self.send_command(panel, f"記憶{g}", 0x03, [g]), bg="#7fa7d8")
            b.bind("<Button-3>", lambda e, g=i: self.save_memory(panel, g))
            b.bind("<Double-Button-1>", lambda e, g=i: self.save_memory(panel, g))
            b.pack(side="left", expand=True, padx=3)

        func = self.row(card)
        sleep_btn = self.small_grid_button(func, "Zzz\n睡眠模式", lambda: self.send_command(panel, "睡眠模式", 0x10, []), bg="#7fa7d8")
        sleep_btn.bind("<Button-3>", lambda e: self.ask_delay_and_send(panel, "睡眠延遲", 0x16))
        sleep_btn.bind("<Double-Button-1>", lambda e: self.ask_delay_and_send(panel, "睡眠延遲", 0x16))
        sleep_btn.pack(side="left", expand=True, padx=3)

        self.small_grid_button(func, "🔔\n關閉鬧鐘", lambda: self.send_command(panel, "關閉鬧鐘", 0x09, []), bg="#7fa7d8").pack(side="left", expand=True, padx=3)
        self.small_grid_button(func, "⏱\n定時", lambda: self.show_schedule_page(idx), bg="#7fa7d8").pack(side="left", expand=True, padx=3)

    def show_smart_plug_panel(self, idx):
        panel = self.panels[idx]
        card = self.frame_shell(panel["name"])

        top = self.row(card)
        tk.Button(top, text="←", command=self.show_panel_list, width=5, font=("Microsoft JhengHei UI", 14, "bold")).pack(side="left", padx=4)
        tk.Label(top, text=panel["name"], bg="#b6cde7", fg="#26384f", font=("Microsoft JhengHei UI", 13, "bold")).pack(side="left", expand=True)
        tk.Button(top, text="⏰", command=lambda: self.show_schedule_page(idx), width=5, font=("Microsoft JhengHei UI", 14)).pack(side="right", padx=4)

        self.big_button(card, "⏻  電源", lambda: self.send_command(panel, "電源", 0x01, [0x01]), bg="#9db9e8", height=3)

        self.add_slider(card, "亮度", self.brightness, lambda v: self.set_brightness(panel, v))
        self.add_slider(card, "色溫", self.color_temp, lambda v: self.set_color(panel, v), warm=True)

        mem = self.row(card)
        for i in range(1, 5):
            b = self.small_grid_button(mem, f"⚙\n記憶{i}", lambda g=i: self.send_command(panel, f"記憶{g}", 0x03, [g]), bg="#7fa7d8")
            b.bind("<Button-3>", lambda e, g=i: self.save_memory(panel, g))
            b.bind("<Double-Button-1>", lambda e, g=i: self.save_memory(panel, g))
            b.pack(side="left", expand=True, padx=3)

        func = self.row(card)
        manual_btn = self.small_grid_button(func, "☝\n手動開關", lambda: self.send_command(panel, "手動開關", 0x11, []), bg="#7fa7d8")
        manual_btn.pack(side="left", expand=True, padx=3)

        sleep_btn = self.small_grid_button(func, "Zzz\n睡眠模式", lambda: self.send_command(panel, "睡眠模式", 0x10, []), bg="#7fa7d8")
        sleep_btn.bind("<Button-3>", lambda e: self.ask_delay_and_send(panel, "睡眠延遲", 0x16))
        sleep_btn.bind("<Double-Button-1>", lambda e: self.ask_delay_and_send(panel, "睡眠延遲", 0x16))
        sleep_btn.pack(side="left", expand=True, padx=3)

        self.small_grid_button(func, "🔔\n關閉鬧鐘", lambda: self.send_command(panel, "關閉鬧鐘", 0x09, []), bg="#7fa7d8").pack(side="left", expand=True, padx=3)
        self.small_grid_button(func, "⏱\n定時", lambda: self.show_schedule_page(idx), bg="#7fa7d8").pack(side="left", expand=True, padx=3)

    def add_slider(self, parent, title, value, on_release, warm=False):
        label = tk.Label(
            parent,
            text=title,
            font=("Microsoft JhengHei UI", 13, "bold"),
            bg="#e1e9f4" if not warm else "#e2d798",
            fg="#26384f",
            relief="ridge",
            bd=2,
            height=2,
        )
        label.pack(fill="x", padx=8, pady=(8, 2))

        scale = tk.Scale(
            parent,
            from_=0,
            to=100,
            orient="horizontal",
            showvalue=True,
            bg="#b6cde7",
            fg="#26384f",
            highlightthickness=0,
            length=330,
        )
        scale.set(value)
        scale.pack(fill="x", padx=8)
        scale.bind("<ButtonRelease-1>", lambda e: on_release(int(scale.get())))

    # -----------------------------
    # Schedule page
    # -----------------------------

    def show_schedule_page(self, idx):
        panel = self.panels[idx]
        card = self.frame_shell("定時設定")

        top = self.row(card)
        tk.Button(top, text="←", command=lambda: self.show_control_page(idx), width=5).pack(side="left", padx=4)
        tk.Label(top, text="定時設定", bg="#b6cde7", fg="#26384f", font=("Microsoft JhengHei UI", 13, "bold")).pack(side="left", expand=True)
        tk.Button(top, text="新增", command=lambda: self.add_alarm_dialog(panel), width=6).pack(side="right", padx=4)

        for alarm in panel.get("alarms", [
            {"time": "05:25 下午", "action": "開燈", "enabled": True},
            {"time": "06:50 上午", "action": "開燈", "enabled": True},
            {"time": "07:30 上午", "action": "關燈", "enabled": False},
            {"time": "09:37 下午", "action": "關燈", "enabled": False},
        ]):
            self.alarm_card(card, panel, alarm)

        tk.Label(
            card,
            text="開燈：時間到打勾開燈\n關燈：時間到打勾關燈\n設定後會先同步時間，再送鬧鐘資料。",
            bg="#b6cde7",
            fg="#26384f",
            font=("Microsoft JhengHei UI", 9),
            justify="center",
        ).pack(pady=10)

    def alarm_card(self, parent, panel, alarm):
        f = tk.Frame(parent, bg="#edf4fc", highlightbackground="#d1deef", highlightthickness=1, padx=10, pady=8)
        f.pack(fill="x", padx=8, pady=6)

        left = tk.Frame(f, bg="#edf4fc")
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text=alarm["time"], bg="#edf4fc", fg="#25364c", font=("Microsoft JhengHei UI", 16, "bold")).pack(anchor="w")
        tk.Label(left, text=alarm["action"], bg="#edf4fc", fg="#23a45b" if alarm["action"] == "開燈" else "#d84a4a", font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
        tk.Label(left, text="週一　週二　週三　週四　週五", bg="#edf4fc", fg="#5b6d82", font=("Microsoft JhengHei UI", 8)).pack(anchor="w")

        var = tk.BooleanVar(value=alarm.get("enabled", False))
        tk.Checkbutton(
            f,
            variable=var,
            bg="#edf4fc",
            command=lambda: self.toggle_alarm(panel, alarm, var.get()),
        ).pack(side="right")

    def toggle_alarm(self, panel, alarm, enabled):
        alarm["enabled"] = bool(enabled)
        self.sync_time_silent()
        self.status_var.set("鬧鐘已更新，並同步時間")

    def add_alarm_dialog(self, panel):
        messagebox.showinfo("新增定時", "新增/編輯定時視窗下一版再細化。")

    # -----------------------------
    # Commands
    # -----------------------------

    def set_brightness(self, panel, value):
        self.brightness = int(value)
        self.send_command(panel, f"亮度 {value}%", 0x04, [int(value)])

    def set_color(self, panel, value):
        self.color_temp = int(value)
        self.send_command(panel, f"色溫 {value}%", 0x05, [int(value)])

    def save_memory(self, panel, group):
        self.send_command(panel, f"儲存記憶{group}", 0x12, [group, self.brightness, self.color_temp])
        return "break"

    def ask_delay_and_send(self, panel, label, command_code):
        seconds = simpledialog.askinteger(
            label,
            "請輸入延遲秒數 0~600",
            initialvalue=panel.get("pir_seconds" if command_code == 0x15 else "sleep_seconds", 50),
            minvalue=0,
            maxvalue=600,
        )
        if seconds is None:
            return "break"

        if command_code == 0x15:
            panel["pir_seconds"] = int(seconds)
        else:
            panel["sleep_seconds"] = int(seconds)
        self.save_panels()

        self.send_command(panel, label, command_code, [int(seconds)])
        return "break"

    def send_pair_command(self, panel):
        if not self.can_send_now("配對"):
            return

        seq = self.next_sequence()
        payload = [0xFF, 0x00, 0x0F, panel["pair_panel_code"], seq, 0x13,
                   (panel["major"] >> 8) & 0xFF, panel["major"] & 0xFF, panel["zone"]]
        payload += [0xFF] * (16 - len(payload))

        self.send_altbeacon("配對", bytes(payload), COMMAND_DURATION_MS)
        panel["paired"] = True
        self.save_panels()

    def send_command(self, panel, label, command_code, data):
        if not self.can_send_now(label):
            return

        seq = self.next_sequence()
        payload = [0xFF, 0x00, 0x0F, panel["control_device_code"], seq, command_code]
        payload += [max(0, min(255, int(x))) for x in data]
        while len(payload) < 15:
            payload.append(0xFF)
        payload.append(panel["zone"])

        self.send_altbeacon(label, bytes(payload[:16]), COMMAND_DURATION_MS)

    def sync_time_silent(self):
        if self.is_sending or self.current_index is None or self.current_index >= len(self.panels):
            return

        panel = self.panels[self.current_index]
        cal = datetime.now()
        seq = self.next_sequence()
        payload = [
            0xFF, 0x00, 0x0F,
            panel["control_device_code"],
            seq,
            0x06,
            cal.hour,
            cal.minute,
            cal.second,
            cal.isoweekday() % 7,
        ]
        while len(payload) < 15:
            payload.append(0xFF)
        payload.append(panel["zone"])

        self.send_altbeacon("背景同步時間", bytes(payload[:16]), COMMAND_DURATION_MS, silent=True)

    def start_auto_time_sync(self):
        self.root.after(10 * 60 * 1000, self.auto_sync_tick)

    def auto_sync_tick(self):
        self.sync_time_silent()
        self.start_auto_time_sync()

    def next_sequence(self):
        current = self.sequence
        self.sequence += 1
        if self.sequence > 9:
            self.sequence = 1
        return current

    def can_send_now(self, label):
        now = time.time() * 1000
        if self.is_sending or (now - self.last_send_time) < MIN_COMMAND_INTERVAL_MS:
            self.status_var.set(f"{label}：訊號發送中")
            return False
        self.last_send_time = now
        return True

    def send_altbeacon(self, label, uuid16: bytes, duration_ms: int, silent=False):
        if len(uuid16) != 16:
            if not silent:
                self.status_var.set("UUID 長度錯誤")
            return

        major = self.panels[self.current_index]["major"] if self.current_index is not None and self.current_index < len(self.panels) else DEFAULT_MAJOR
        minor = self.panels[self.current_index]["minor"] if self.current_index is not None and self.current_index < len(self.panels) else DEFAULT_MINOR

        manufacturer_payload = (
            bytes([0xBE, 0xAC])
            + uuid16
            + major.to_bytes(2, "big")
            + minor.to_bytes(2, "big")
            + bytes([0xC5, 0x00])
        )

        def worker():
            if not silent:
                self.root.after(0, lambda: self.start_send_ui(label, duration_ms))
            try:
                self.ble.advertise_manufacturer_data(COMPANY_ID, manufacturer_payload, duration_ms)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("BLE 發送失敗", str(e)))
                self.root.after(0, self.finish_send_ui)

        threading.Thread(target=worker, daemon=True).start()

    def start_send_ui(self, label, duration_ms):
        self.is_sending = True
        self.status_var.set(f"發送中：{label}")
        self.progress_var.set(0)

        start = time.time() * 1000

        def tick():
            elapsed = time.time() * 1000 - start
            p = int(min(100, elapsed * 100 / duration_ms))
            self.progress_var.set(p)
            if elapsed < duration_ms:
                self.root.after(50, tick)
            else:
                self.status_var.set(f"已送出：{label}")
                self.finish_send_ui()

        tick()

    def finish_send_ui(self):
        self.is_sending = False
        self.progress_var.set(100)

    # -----------------------------
    # Panel settings
    # -----------------------------

    def apply_panel_setting(self, panel):
        panel_type = panel["type"]
        panel["pair_panel_code"] = DEFAULT_PAIR_PANEL_CODE
        panel["control_device_code"] = DEFAULT_CONTROL_DEVICE_CODE
        panel["zone"] = DEFAULT_ZONE

    # -----------------------------
    # Utils
    # -----------------------------

    def start_auto_time_sync(self):
        self.root.after(10 * 60 * 1000, self._auto_time_sync)

    def _auto_time_sync(self):
        self.sync_time_silent()
        self.start_auto_time_sync()


if __name__ == "__main__":
    root = tk.Tk()
    app = RemoteApp(root)
    root.mainloop()
