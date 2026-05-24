# AutoWriter.py
# ENERGY PRO BLE Beacon Remote - Windows No-Sequence Control Version
# 重點：
# 1. 配對維持原本可成功格式
# 2. 控制指令取消 Sequence
# 3. 控制格式改為：FF000F18 + CMD + DATA + FF... + 03

import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

APP_TITLE = "ENERGY PRO BLE Remote - No Sequence Control"
DATA_FILE = "remote_panels.json"

COMPANY_ID = 0x0118
FIXED_MAJOR = 0x5576
DEFAULT_MINOR = 0x0003

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
            raise RuntimeError("winsdk 尚未安裝或無法載入。")

        adv = BluetoothLEAdvertisement()
        m = BluetoothLEManufacturerData()
        m.company_id = company_id
        m.data = self._buffer(manufacturer_payload)
        adv.manufacturer_data.append(m)

        self.publisher = BluetoothLEAdvertisementPublisher(adv)
        self.publisher.start()
        time.sleep(duration_ms / 1000)
        self.publisher.stop()
        self.publisher = None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("450x780")
        self.root.minsize(420, 700)

        self.ble = BleAdvertiser()
        self.sequence = 1
        self.last_send = 0
        self.sending = False
        self.current_index = None

        self.panels = self.load_panels()

        self.status = tk.StringVar(value="等待操作")
        self.progress = tk.IntVar(value=0)
        self.uuid_text = tk.StringVar(value="")

        self.show_home()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def shell(self, title):
        self.clear()
        bg = tk.Frame(self.root, bg="#dceafa")
        bg.pack(fill="both", expand=True)

        frame = tk.Frame(
            bg,
            bg="#b7cfe9",
            padx=18,
            pady=14,
            highlightbackground="#35669f",
            highlightthickness=2,
        )
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(
            frame,
            text=title,
            bg="#b7cfe9",
            fg="#26384f",
            font=("Microsoft JhengHei UI", 16, "bold"),
        ).pack(pady=(0, 6))

        tk.Label(
            frame,
            textvariable=self.status,
            bg="#b7cfe9",
            fg="#26384f",
            font=("Microsoft JhengHei UI", 10),
        ).pack()

        ttk.Progressbar(frame, maximum=100, variable=self.progress).pack(fill="x", pady=(4, 10))

        return frame

    def row(self, parent):
        f = tk.Frame(parent, bg="#b7cfe9")
        f.pack(fill="x", pady=2)
        return f

    def grid_btn(self, parent, text, cmd, color="#e8f0fa"):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=color,
            fg="#25364c",
            activebackground="#cfdef2",
            relief="ridge",
            bd=2,
            font=("Microsoft JhengHei UI", 9, "bold"),
            width=10,
            height=3,
        )

    def full_btn(self, parent, text, cmd, color="#e8f0fa", fg="#25364c"):
        b = tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=color,
            fg=fg,
            font=("Microsoft JhengHei UI", 11, "bold"),
            height=2,
        )
        b.pack(fill="x", padx=8, pady=5)
        return b

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

    def new_panel(self):
        return {
            "name": f"新面板 {len(self.panels) + 1}",
            "type": "調光調色感應燈具",
            "major": FIXED_MAJOR,
            "minor": DEFAULT_MINOR,
            "pair_panel_code": PAIR_PANEL_CODE,
            "control_device_code": CONTROL_DEVICE_CODE,
            "zone": ZONE,
            "paired": False,
        }

    def fix_all_panels_to_5576(self):
        for p in self.panels:
            p["major"] = FIXED_MAJOR
            p["minor"] = DEFAULT_MINOR
            p["pair_panel_code"] = PAIR_PANEL_CODE
            p["control_device_code"] = CONTROL_DEVICE_CODE
            p["zone"] = ZONE
        self.save_panels()
        self.status.set("已修正：Major 5576 / 無 Sequence 控制格式")
        self.show_home()

    def show_home(self):
        f = self.shell("遙控器面板列表")

        tk.Label(
            f,
            text="控制格式：FF000F18 + CMD + DATA，不含 Sequence",
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
                text = f"{p['name']}\n{p['type']}\nMajor=5576  {'已配對' if p.get('paired') else '未配對'}"
                b = tk.Button(
                    f,
                    text=text,
                    bg="#e8f0fa",
                    fg="#25364c",
                    font=("Microsoft JhengHei UI", 11, "bold"),
                    height=4,
                    command=lambda idx=i: self.open_panel(idx),
                )
                b.pack(fill="x", padx=8, pady=6)
                b.bind("<Double-Button-1>", lambda e, idx=i: self.show_pair(idx))
                b.bind("<Button-3>", lambda e, idx=i: self.show_pair(idx))

        r = self.row(f)

        tk.Button(
            r,
            text="增加",
            bg="#5f8eca",
            fg="white",
            height=2,
            font=("Microsoft JhengHei UI", 12, "bold"),
            command=self.add_panel,
        ).pack(side="left", fill="x", expand=True, padx=8, pady=8)

        tk.Button(
            r,
            text="刪除",
            bg="#5f8eca",
            fg="white",
            height=2,
            font=("Microsoft JhengHei UI", 12, "bold"),
            command=self.delete_panel,
        ).pack(side="left", fill="x", expand=True, padx=8, pady=8)

        self.full_btn(f, "修正現有面板為 5576", self.fix_all_panels_to_5576, color="#fff0b3")
        self.full_btn(f, "直接進控制測試", self.open_first_or_create, color="#dfe9f6")

    def open_first_or_create(self):
        if not self.panels:
            self.add_panel()
            return
        self.current_index = 0
        self.show_test(0)

    def add_panel(self):
        self.panels.append(self.new_panel())
        self.save_panels()
        self.current_index = len(self.panels) - 1
        self.show_pair(self.current_index)

    def delete_panel(self):
        if not self.panels:
            self.status.set("沒有可刪除面板")
            return
        idx = self.current_index if self.current_index is not None else len(self.panels) - 1
        del self.panels[idx]
        self.current_index = None
        self.save_panels()
        self.show_home()

    def open_panel(self, idx):
        self.current_index = idx
        if not self.panels[idx].get("paired"):
            self.show_pair(idx)
        else:
            self.show_test(idx)

    def show_pair(self, idx):
        self.current_index = idx
        p = self.panels[idx]
        p["major"] = FIXED_MAJOR
        p["minor"] = DEFAULT_MINOR

        f = self.shell("配對 / 設定")

        tk.Label(
            f,
            text="設備名稱",
            bg="#b7cfe9",
            fg="#25364f",
            font=("Microsoft JhengHei UI", 11, "bold"),
        ).pack()

        name = tk.StringVar(value=p["name"])

        tk.Entry(
            f,
            textvariable=name,
            justify="center",
            font=("Microsoft JhengHei UI", 13),
        ).pack(fill="x", padx=8, pady=5, ipady=4)

        tk.Label(
            f,
            text="固定面板 ID / Major：5576",
            bg="#b7cfe9",
            fg="#b00020",
            font=("Microsoft JhengHei UI", 10, "bold"),
        ).pack(pady=6)

        self.full_btn(f, "配對 5576", lambda: self.save_pair(idx, name.get()), color="#5f8eca", fg="white")
        self.full_btn(f, "控制測試頁", lambda: self.show_test(idx))
        self.full_btn(f, "返回列表", self.show_home)

        tk.Label(
            f,
            text="請重新配對一次：\n燈具重新上電 5 秒內按下「配對 5576」。\n再進控制測試頁。",
            bg="#b7cfe9",
            fg="#25364c",
            font=("Microsoft JhengHei UI", 9),
            justify="center",
        ).pack(pady=8)

    def save_pair(self, idx, name):
        p = self.panels[idx]
        p["name"] = name or "未命名面板"
        p["major"] = FIXED_MAJOR
        p["minor"] = DEFAULT_MINOR
        p["pair_panel_code"] = PAIR_PANEL_CODE
        p["control_device_code"] = CONTROL_DEVICE_CODE
        p["zone"] = ZONE
        p["paired"] = True
        self.save_panels()
        self.send_pair(p)

    def show_test(self, idx):
        self.current_index = idx
        p = self.panels[idx]
        p["major"] = FIXED_MAJOR
        p["minor"] = DEFAULT_MINOR

        f = self.shell(f"控制測試：{p['name']}")

        r0 = self.row(f)
        tk.Button(r0, text="← 返回", command=self.show_home, width=8).pack(side="left", padx=4)
        tk.Button(r0, text="配對頁", command=lambda: self.show_pair(idx), width=8).pack(side="right", padx=4)

        tk.Label(
            f,
            text="新版控制：無 Sequence，固定 offset",
            bg="#b7cfe9",
            fg="#b00020",
            font=("Microsoft JhengHei UI", 10, "bold"),
        ).pack(pady=(4, 0))

        tk.Label(
            f,
            text="主要控制測試",
            bg="#b7cfe9",
            fg="#25364c",
            font=("Microsoft JhengHei UI", 11, "bold"),
        ).pack(pady=(8, 0))

        r1 = self.row(f)
        self.grid_btn(r1, "Power B\n0101", lambda: self.send_control(p, "Power B", 0x01, [0x01])).pack(side="left", expand=True, padx=3)
        self.grid_btn(r1, "Power C\n0100", lambda: self.send_control(p, "Power C", 0x01, [0x00])).pack(side="left", expand=True, padx=3)
        self.grid_btn(r1, "Night B\n0201", lambda: self.send_control(p, "Night B", 0x02, [0x01])).pack(side="left", expand=True, padx=3)

        r2 = self.row(f)
        self.grid_btn(r2, "Night C\n0200", lambda: self.send_control(p, "Night C", 0x02, [0x00])).pack(side="left", expand=True, padx=3)
        self.grid_btn(r2, "亮度100\n0464", lambda: self.send_control(p, "亮度100", 0x04, [100])).pack(side="left", expand=True, padx=3)
        self.grid_btn(r2, "亮度1\n0401", lambda: self.send_control(p, "亮度1", 0x04, [1])).pack(side="left", expand=True, padx=3)

        r3 = self.row(f)
        self.grid_btn(r3, "色溫0\n0500", lambda: self.send_control(p, "色溫0", 0x05, [0])).pack(side="left", expand=True, padx=3)
        self.grid_btn(r3, "色溫100\n0564", lambda: self.send_control(p, "色溫100", 0x05, [100])).pack(side="left", expand=True, padx=3)
        self.grid_btn(r3, "睡眠\n10", lambda: self.send_control(p, "睡眠", 0x10, [])).pack(side="left", expand=True, padx=3)

        r4 = self.row(f)
        self.grid_btn(r4, "感應\n11", lambda: self.send_control(p, "感應", 0x11, [])).pack(side="left", expand=True, padx=3)
        self.grid_btn(r4, "關鬧鐘\n09", lambda: self.send_control(p, "關鬧鐘", 0x09, [])).pack(side="left", expand=True, padx=3)
        self.grid_btn(r4, "同步時間\n06", lambda: self.send_time_sync(p)).pack(side="left", expand=True, padx=3)

        r5 = self.row(f)
        for i in range(1, 5):
            self.grid_btn(r5, f"記憶{i}", lambda g=i: self.send_control(p, f"記憶{g}", 0x03, [g])).pack(side="left", expand=True, padx=2)

        tk.Label(
            f,
            text="RAW 舊封包測試",
            bg="#b7cfe9",
            fg="#25364c",
            font=("Microsoft JhengHei UI", 11, "bold"),
        ).pack(pady=(8, 0))

        r6 = self.row(f)
        self.grid_btn(r6, "RAW\nPower A", lambda: self.send_raw_uuid(p, "RAW Power A", "FF000F180201FFFFFFFFFFFFFFFFFF03")).pack(side="left", expand=True, padx=3)
        self.grid_btn(r6, "RAW\nPower B", lambda: self.send_raw_uuid(p, "RAW Power B", "FF000F180301FFFFFFFFFFFFFFFFFF03")).pack(side="left", expand=True, padx=3)
        self.grid_btn(r6, "RAW\nNight", lambda: self.send_raw_uuid(p, "RAW Night", "FF000F180902FFFFFFFFFFFFFFFFFF03")).pack(side="left", expand=True, padx=3)

        tk.Label(
            f,
            textvariable=self.uuid_text,
            bg="#b7cfe9",
            fg="#25364c",
            font=("Consolas", 9),
            wraplength=390,
            justify="center",
        ).pack(pady=8)

    def send_pair(self, panel):
        # 配對先保留 sequence，因為目前 PC 配對已確認可以
        if not self.can_send("配對"):
            return

        seq = self.next_seq()
        uuid = bytearray([0xFF, 0x00, 0x0F, PAIR_PANEL_CODE, seq, 0x13])
        uuid += bytearray([(FIXED_MAJOR >> 8) & 0xFF, FIXED_MAJOR & 0xFF, ZONE])
        while len(uuid) < 16:
            uuid.append(0xFF)

        self.send_beacon("配對", bytes(uuid[:16]))

    def send_control(self, panel, label, cmd, data):
        # 重要：控制指令無 sequence
        # 格式：FF000F18 + CMD + DATA + FF... + 03
        if not self.can_send(label):
            return

        uuid = bytearray([0xFF, 0x00, 0x0F, CONTROL_DEVICE_CODE, cmd])

        for x in data:
            uuid.append(max(0, min(255, int(x))))

        while len(uuid) < 15:
            uuid.append(0xFF)

        uuid.append(ZONE)

        self.send_beacon(label, bytes(uuid[:16]))

    def send_time_sync(self, panel):
        import datetime
        now = datetime.datetime.now()
        self.send_control(
            panel,
            "同步時間",
            0x06,
            [now.hour, now.minute, now.second, (now.isoweekday() % 7)]
        )

    def send_raw_uuid(self, panel, label, hex_uuid):
        if not self.can_send(label):
            return
        self.send_beacon(label, bytes.fromhex(hex_uuid))

    def next_seq(self):
        now = self.sequence
        self.sequence += 1
        if self.sequence > 9:
            self.sequence = 1
        return now

    def can_send(self, label):
        now = time.time() * 1000
        if self.sending or now - self.last_send < LOCK_MS:
            self.status.set(f"{label}：訊號發送中")
            return False
        self.last_send = now
        return True

    def send_beacon(self, label, uuid16):
        self.uuid_text.set("UUID16 = " + uuid16.hex().upper())

        manufacturer = (
            bytes([0xBE, 0xAC])
            + uuid16
            + FIXED_MAJOR.to_bytes(2, "big")
            + DEFAULT_MINOR.to_bytes(2, "big")
            + bytes([0xC5, 0x00])
        )

        def worker():
            self.root.after(0, lambda: self.start_ui(label))
            try:
                self.ble.send(COMPANY_ID, manufacturer, ADVERTISE_MS)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("BLE 發送失敗", str(e)))
            finally:
                self.root.after(0, lambda: self.finish_ui(label))

        threading.Thread(target=worker, daemon=True).start()

    def start_ui(self, label):
        self.sending = True
        self.status.set(f"發送中：{label}")
        self.progress.set(0)
        start = time.time() * 1000

        def tick():
            if not self.sending:
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
        self.sending = False


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
