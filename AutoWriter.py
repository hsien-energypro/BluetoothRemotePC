# AutoWriter.py
# ENERGY PRO BLE Remote PC - Android Reference Version
# 依照使用者上傳的 Android MainActivity_StyleBook_Page3_LightControl.kt 對照製作
#
# 重點：
# - Company ID = 0x0118
# - Major = 0x5576
# - Minor = 0x0003
# - Manufacturer payload = BE AC + UUID16 + Major + Minor + C5 00
# - 配對：FF 00 0F 25 SEQ 13 55 76 03 FF...
# - 控制：FF 00 0F 18 SEQ CMD DATA... FF... 03
# - 1200ms 發送
# - 1300ms lock
#
# 此版目的：讓 PC 與最後 Android 參考版完全對照測試。

import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

APP_TITLE = "ENERGY PRO PC 對照測試版"
DATA_FILE = "remote_panels.json"
LOG_FILE = "pc_android_reference_log.txt"

COMPANY_ID = 0x0118
MAJOR = 0x5576
MINOR = 0x0003

PAIR_PANEL_CODE = 0x25
CONTROL_DEVICE_CODE = 0x18
ZONE = 0x03

ADVERTISE_MS = 1200
LOCK_MS = 1300

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

    def _buffer(self, data: bytes):
        writer = DataWriter()
        writer.write_bytes(data)
        return writer.detach_buffer()

    def send(self, company_id: int, manufacturer_payload: bytes, duration_ms: int):
        if not WINSDK_AVAILABLE:
            raise RuntimeError("winsdk 尚未安裝或無法載入")

        adv = BluetoothLEAdvertisement()

        m = BluetoothLEManufacturerData()
        m.company_id = company_id
        m.data = self._buffer(manufacturer_payload)
        adv.manufacturer_data.append(m)

        self.publisher = BluetoothLEAdvertisementPublisher(adv)
        self.publisher.start()
        time.sleep(duration_ms / 1000.0)
        self.publisher.stop()
        self.publisher = None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("470x790")
        self.root.minsize(430, 700)

        self.ble = BleAdvertiser()

        self.sequence_code = 1
        self.last_send_time = 0
        self.is_sending = False

        self.current_brightness = 50
        self.current_color = 50
        self.current_panel_index = None
        self.current_panel_name = "調光調色感應燈具"

        self.panels = self.load_panels()

        self.status = tk.StringVar(value="等待操作")
        self.progress = tk.IntVar(value=0)
        self.uuid_text = tk.StringVar(value="")
        self.payload_text = tk.StringVar(value="")

        self.log("=== Start PC Android Reference Test ===")
        self.show_panel_list()

    # =========================================================
    # UI
    # =========================================================

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def shell(self, title):
        self.clear()

        bg = tk.Frame(self.root, bg="#dceafa")
        bg.pack(fill="both", expand=True)

        card = tk.Frame(
            bg,
            bg="#b7cfe9",
            padx=18,
            pady=14,
            highlightbackground="#2d548e",
            highlightthickness=2,
        )
        card.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(
            card,
            text=title,
            bg="#b7cfe9",
            fg="#2d3746",
            font=("Microsoft JhengHei UI", 16, "bold"),
        ).pack(pady=(0, 5))

        tk.Label(
            card,
            textvariable=self.status,
            bg="#b7cfe9",
            fg="#2d3746",
            font=("Microsoft JhengHei UI", 10),
            wraplength=390,
            justify="center",
        ).pack(pady=(0, 4))

        ttk.Progressbar(card, maximum=100, variable=self.progress).pack(fill="x", pady=(0, 8))

        return card

    def row(self, parent):
        f = tk.Frame(parent, bg="#b7cfe9")
        f.pack(fill="x", pady=2)
        return f

    def full_btn(self, parent, text, cmd, bg="#e8f0fa", fg="#26384f"):
        b = tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg=fg,
            activebackground="#cfdef2",
            relief="ridge",
            bd=2,
            font=("Microsoft JhengHei UI", 11, "bold"),
            height=2,
        )
        b.pack(fill="x", padx=8, pady=5)
        return b

    def grid_btn(self, parent, text, cmd, bg="#e8f0fa"):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg="#26384f",
            activebackground="#cfdef2",
            relief="ridge",
            bd=2,
            font=("Microsoft JhengHei UI", 9, "bold"),
            width=10,
            height=3,
        )

    # =========================================================
    # Storage
    # =========================================================

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

    def make_panel(self):
        return {
            "name": f"新面板 {len(self.panels) + 1}",
            "type": "調光調色感應燈具",
            "major": MAJOR,
            "minor": MINOR,
            "paired": False
        }

    # =========================================================
    # Pages
    # =========================================================

    def show_panel_list(self):
        f = self.shell("遙控器面板列表")

        tk.Label(
            f,
            text="Android 參考版對照：控制含 Sequence",
            bg="#b7cfe9",
            fg="#b00020",
            font=("Microsoft JhengHei UI", 10, "bold"),
        ).pack(pady=4)

        if not self.panels:
            tk.Label(
                f,
                text="尚未新增面板",
                bg="#e8f0fa",
                fg="#63758c",
                font=("Microsoft JhengHei UI", 14),
                height=8,
            ).pack(fill="x", padx=8, pady=18)
        else:
            for i, p in enumerate(self.panels):
                text = f"{p['name']}\n{p.get('type', '調光調色感應燈具')}\nMajor=5576  {'已配對' if p.get('paired') else '未配對'}"
                b = tk.Button(
                    f,
                    text=text,
                    bg="#e8f0fa",
                    fg="#26384f",
                    font=("Microsoft JhengHei UI", 11, "bold"),
                    height=4,
                    relief="ridge",
                    bd=2,
                    command=lambda idx=i: self.open_panel(idx)
                )
                b.pack(fill="x", padx=8, pady=6)
                b.bind("<Button-3>", lambda e, idx=i: self.show_pair_page(idx))
                b.bind("<Double-Button-1>", lambda e, idx=i: self.show_pair_page(idx))

        r = self.row(f)
        tk.Button(
            r,
            text="增加",
            bg="#5c87be",
            fg="white",
            font=("Microsoft JhengHei UI", 12, "bold"),
            height=2,
            command=self.add_panel,
        ).pack(side="left", fill="x", expand=True, padx=8, pady=8)

        tk.Button(
            r,
            text="刪除",
            bg="#5c87be",
            fg="white",
            font=("Microsoft JhengHei UI", 12, "bold"),
            height=2,
            command=self.delete_panel,
        ).pack(side="left", fill="x", expand=True, padx=8, pady=8)

        self.full_btn(f, "直接進控制測試", self.open_first_or_create, bg="#dfe9f6")
        self.full_btn(f, "查看最後封包", self.show_packet_page, bg="#fff0b3")

        tk.Label(
            f,
            text="短按：進控制頁；右鍵/雙擊：進配對頁",
            bg="#b7cfe9",
            fg="#26384f",
            font=("Microsoft JhengHei UI", 9),
        ).pack(pady=6)

    def add_panel(self):
        self.panels.append(self.make_panel())
        self.save_panels()
        self.current_panel_index = len(self.panels) - 1
        self.show_pair_page(self.current_panel_index)

    def delete_panel(self):
        if not self.panels:
            self.status.set("沒有可刪除面板")
            return
        idx = self.current_panel_index if self.current_panel_index is not None else len(self.panels) - 1
        del self.panels[idx]
        self.current_panel_index = None
        self.save_panels()
        self.show_panel_list()

    def open_first_or_create(self):
        if not self.panels:
            self.add_panel()
            return
        self.current_panel_index = 0
        self.show_control_page(0)

    def open_panel(self, idx):
        self.current_panel_index = idx
        if not self.panels[idx].get("paired"):
            self.show_pair_page(idx)
        else:
            self.show_control_page(idx)

    def show_pair_page(self, idx):
        self.current_panel_index = idx
        p = self.panels[idx]

        f = self.shell("配對設定")

        tk.Label(
            f,
            text="設備名稱",
            bg="#b7cfe9",
            fg="#26384f",
            font=("Microsoft JhengHei UI", 11, "bold"),
        ).pack()

        name = tk.StringVar(value=p["name"])
        tk.Entry(
            f,
            textvariable=name,
            justify="center",
            font=("Microsoft JhengHei UI", 13),
            bg="#e8f0fa",
            fg="#26384f",
        ).pack(fill="x", padx=8, pady=5, ipady=4)

        tk.Label(
            f,
            text="固定 Major=5576 / Minor=0003",
            bg="#b7cfe9",
            fg="#b00020",
            font=("Microsoft JhengHei UI", 10, "bold"),
        ).pack(pady=6)

        self.full_btn(f, "配對", lambda: self.save_pair(idx, name.get()), bg="#5c87be", fg="white")
        self.full_btn(f, "控制測試頁", lambda: self.show_control_page(idx), bg="#dfe9f6")
        self.full_btn(f, "返回列表", self.show_panel_list, bg="#dfe9f6")

        tk.Label(
            f,
            text="配對格式保留 sequence：\nFF 00 0F 25 SEQ 13 55 76 03 FF...",
            bg="#b7cfe9",
            fg="#26384f",
            font=("Microsoft JhengHei UI", 9),
            justify="center",
        ).pack(pady=8)

    def save_pair(self, idx, name):
        p = self.panels[idx]
        p["name"] = name or "未命名面板"
        p["major"] = MAJOR
        p["minor"] = MINOR
        p["paired"] = True
        self.save_panels()
        self.send_pair_command()

    def show_control_page(self, idx):
        self.current_panel_index = idx
        p = self.panels[idx]

        f = self.shell(p["name"])

        top = self.row(f)
        tk.Button(top, text="←", command=self.show_panel_list, width=6).pack(side="left", padx=4)
        tk.Label(
            top,
            text=p["name"],
            bg="#b7cfe9",
            fg="#26384f",
            font=("Microsoft JhengHei UI", 12, "bold"),
        ).pack(side="left", expand=True)
        tk.Button(top, text="封包", command=self.show_packet_page, width=6).pack(side="right", padx=4)

        tk.Label(
            f,
            text="控制格式同 Android 參考版：FF 00 0F 18 SEQ CMD DATA... 03",
            bg="#b7cfe9",
            fg="#b00020",
            font=("Microsoft JhengHei UI", 9, "bold"),
            wraplength=390,
        ).pack(pady=(6, 3))

        r1 = self.row(f)
        self.grid_btn(r1, "電源\n01 01", lambda: self.send_universal("電源 TOGGLE", 0x01, [0x01]), bg="#9db9e8").pack(side="left", expand=True, padx=4)
        self.grid_btn(r1, "夜燈\n02 01", lambda: self.send_universal("夜燈", 0x02, [0x01]), bg="#9db9e8").pack(side="left", expand=True, padx=4)

        self.add_slider(f, "亮度", self.current_brightness, lambda v: self.set_brightness(v))
        self.add_slider(f, "色溫", self.current_color, lambda v: self.set_color(v), warm=True)

        tk.Label(
            f,
            text="長按記憶鍵：儲存目前亮度/色溫",
            bg="#b7cfe9",
            fg="white",
            font=("Microsoft JhengHei UI", 9, "bold"),
        ).pack(pady=(4, 2))

        mem = self.row(f)
        for i in range(1, 5):
            b = self.grid_btn(mem, f"記憶{i}", lambda g=i: self.send_universal(f"記憶{g}", 0x03, [g]), bg="#7fa7d8")
            b.pack(side="left", expand=True, padx=3)
            b.bind("<Button-3>", lambda e, g=i: self.send_universal(f"儲存記憶{g}", 0x12, [g, self.current_brightness, self.current_color]))
            b.bind("<Double-Button-1>", lambda e, g=i: self.send_universal(f"儲存記憶{g}", 0x12, [g, self.current_brightness, self.current_color]))

        func = self.row(f)
        pir = self.grid_btn(func, "人體\n感應", lambda: self.send_universal("人體感應", 0x11, []), bg="#7fa7d8")
        pir.pack(side="left", expand=True, padx=3)
        pir.bind("<Button-3>", lambda e: self.ask_delay("人體感應延遲", 0x15))

        sleep = self.grid_btn(func, "睡眠\n模式", lambda: self.send_universal("睡眠模式", 0x10, []), bg="#7fa7d8")
        sleep.pack(side="left", expand=True, padx=3)
        sleep.bind("<Button-3>", lambda e: self.ask_delay("睡眠延遲", 0x16))

        self.grid_btn(func, "關閉\n鬧鐘", lambda: self.send_universal("關閉鬧鐘", 0x09, []), bg="#7fa7d8").pack(side="left", expand=True, padx=3)
        self.grid_btn(func, "同步\n時間", self.send_time_sync, bg="#7fa7d8").pack(side="left", expand=True, padx=3)

        tk.Label(
            f,
            textvariable=self.uuid_text,
            bg="#b7cfe9",
            fg="#26384f",
            font=("Consolas", 8),
            wraplength=390,
            justify="center",
        ).pack(pady=8)

    def add_slider(self, parent, title, value, callback, warm=False):
        color = "#e1e9f4" if not warm else "#dfd390"
        tk.Label(
            parent,
            text=title,
            bg=color,
            fg="#26384f",
            font=("Microsoft JhengHei UI", 11, "bold"),
            relief="ridge",
            bd=2,
            height=2,
        ).pack(fill="x", padx=8, pady=(8, 0))

        s = tk.Scale(
            parent,
            from_=0,
            to=100,
            orient="horizontal",
            showvalue=True,
            bg="#b7cfe9",
            fg="#26384f",
            highlightthickness=0,
        )
        s.set(value)
        s.pack(fill="x", padx=8)
        s.bind("<ButtonRelease-1>", lambda e: callback(int(s.get())))

    def set_brightness(self, value):
        self.current_brightness = value
        self.send_universal(f"亮度 {value}", 0x04, [value])

    def set_color(self, value):
        self.current_color = value
        self.send_universal(f"色溫 {value}", 0x05, [value])

    def ask_delay(self, label, cmd):
        seconds = simpledialog.askinteger(label, "請輸入 0~600 秒", initialvalue=50, minvalue=0, maxvalue=600)
        if seconds is None:
            return
        self.send_universal(label, cmd, [seconds])

    def show_packet_page(self):
        f = self.shell("最後送出封包")
        self.full_btn(f, "返回控制頁", lambda: self.show_control_page(self.current_panel_index or 0), bg="#dfe9f6")
        tk.Label(f, text="UUID16", bg="#b7cfe9", fg="#26384f", font=("Microsoft JhengHei UI", 11, "bold")).pack(anchor="w")
        tk.Message(f, textvariable=self.uuid_text, width=390, bg="#e8f0fa", fg="#26384f", font=("Consolas", 10)).pack(fill="x", padx=8, pady=4)
        tk.Label(f, text="Manufacturer Payload", bg="#b7cfe9", fg="#26384f", font=("Microsoft JhengHei UI", 11, "bold")).pack(anchor="w")
        tk.Message(f, textvariable=self.payload_text, width=390, bg="#e8f0fa", fg="#26384f", font=("Consolas", 10)).pack(fill="x", padx=8, pady=4)
        tk.Label(f, text=f"Log: {LOG_FILE}", bg="#b7cfe9", fg="#26384f", font=("Microsoft JhengHei UI", 9)).pack(pady=8)

    # =========================================================
    # Command / BLE
    # =========================================================

    def next_sequence(self):
        current = self.sequence_code
        self.sequence_code += 1
        if self.sequence_code > 9:
            self.sequence_code = 1
        return current

    def can_send(self, label):
        now = time.time() * 1000
        if self.is_sending or now - self.last_send_time < LOCK_MS:
            self.status.set(f"{label}：訊號發送中")
            return False
        self.last_send_time = now
        return True

    def build_altbeacon_data(self, uuid16: bytes) -> bytes:
        return (
            bytes([0xBE, 0xAC])
            + uuid16
            + MAJOR.to_bytes(2, "big")
            + MINOR.to_bytes(2, "big")
            + bytes([0xC5, 0x00])
        )

    def send_pair_command(self):
        if not self.can_send("配對"):
            return

        seq = self.next_sequence()

        uuid = bytearray([0xFF] * 16)
        uuid[0] = 0xFF
        uuid[1] = 0x00
        uuid[2] = 0x0F
        uuid[3] = PAIR_PANEL_CODE
        uuid[4] = seq
        uuid[5] = 0x13
        uuid[6] = (MAJOR >> 8) & 0xFF
        uuid[7] = MAJOR & 0xFF
        uuid[8] = ZONE

        self.send_beacon("配對", bytes(uuid))

    def send_universal(self, label, command_code, data):
        if not self.can_send(label):
            return

        seq = self.next_sequence()

        uuid = bytearray([0xFF] * 16)
        uuid[0] = 0xFF
        uuid[1] = 0x00
        uuid[2] = 0x0F
        uuid[3] = CONTROL_DEVICE_CODE
        uuid[4] = seq
        uuid[5] = command_code & 0xFF

        for i, x in enumerate(data):
            if 6 + i < 15:
                uuid[6 + i] = max(0, min(255, int(x)))

        uuid[15] = ZONE

        self.send_beacon(label, bytes(uuid))

    def send_time_sync(self):
        now = datetime.now()
        week = (now.isoweekday() % 7)
        self.send_universal("同步時間", 0x06, [now.hour, now.minute, now.second, week])

    def send_beacon(self, label, uuid16: bytes):
        payload = self.build_altbeacon_data(uuid16)
        uuid_hex = uuid16.hex().upper()
        payload_hex = payload.hex().upper()

        self.uuid_text.set("UUID16 = " + uuid_hex)
        self.payload_text.set("Payload = " + payload_hex)

        self.log(f"{label}\nUUID16={uuid_hex}\nPayload={payload_hex}")

        def worker():
            self.root.after(0, lambda: self.start_ui(label))
            try:
                self.ble.send(COMPANY_ID, payload, ADVERTISE_MS)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("BLE 發送失敗", str(e)))
            finally:
                self.root.after(0, lambda: self.finish_ui(label))

        threading.Thread(target=worker, daemon=True).start()

    def start_ui(self, label):
        self.is_sending = True
        self.progress.set(0)
        self.status.set(f"發送中：{label}")
        start = time.time() * 1000

        def tick():
            if not self.is_sending:
                return
            elapsed = time.time() * 1000 - start
            p = min(100, int(elapsed * 100 / ADVERTISE_MS))
            self.progress.set(p)
            if elapsed < ADVERTISE_MS:
                self.root.after(50, tick)

        tick()

    def finish_ui(self, label):
        self.progress.set(100)
        self.status.set(f"已送出：{label}")
        self.is_sending = False

    def log(self, text):
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "\n")
            f.write(text + "\n")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
