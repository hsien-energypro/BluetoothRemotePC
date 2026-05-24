# AutoWriter_DebugLogger.py
# PC BLE 發送資料監測版
# 用途：檢查 Windows EXE 實際送出的 BLE Manufacturer Data 是否正確
#
# 需要：
#   pip install winsdk
#
# 執行：
#   python AutoWriter_DebugLogger.py
#
# 輸出：
#   ble_send_debug_log.txt

import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

COMPANY_ID = 0x0118
MAJOR = 0x5576
MINOR = 0x0003
ZONE = 0x03
DEVICE_CODE = 0x18
PAIR_PANEL_CODE = 0x25

ADVERTISE_MS = 1200
LOG_FILE = "ble_send_debug_log.txt"

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


def hex_bytes(data: bytes) -> str:
    return data.hex().upper()


class BleSender:
    def __init__(self):
        self.publisher = None

    def _buffer(self, data: bytes):
        writer = DataWriter()
        writer.write_bytes(data)
        return writer.detach_buffer()

    def send(self, manufacturer_payload: bytes):
        if not WINSDK_AVAILABLE:
            raise RuntimeError("winsdk 尚未安裝或無法載入")

        adv = BluetoothLEAdvertisement()

        m = BluetoothLEManufacturerData()
        m.company_id = COMPANY_ID
        m.data = self._buffer(manufacturer_payload)
        adv.manufacturer_data.append(m)

        self.publisher = BluetoothLEAdvertisementPublisher(adv)
        self.publisher.start()
        time.sleep(ADVERTISE_MS / 1000.0)
        self.publisher.stop()
        self.publisher = None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("BLE 發送資料監測版")
        self.root.geometry("760x680")

        self.sequence = 1
        self.sender = BleSender()

        self.status = tk.StringVar(value="等待操作")
        self.last_uuid = tk.StringVar(value="")
        self.last_payload = tk.StringVar(value="")

        self.build_ui()
        self.log_header()

    def build_ui(self):
        main = tk.Frame(self.root, bg="#dceafa", padx=16, pady=16)
        main.pack(fill="both", expand=True)

        tk.Label(
            main,
            text="PC BLE 發送資料監測版",
            font=("Microsoft JhengHei UI", 18, "bold"),
            bg="#dceafa",
            fg="#26384f",
        ).pack(pady=8)

        tk.Label(
            main,
            textvariable=self.status,
            font=("Microsoft JhengHei UI", 12),
            bg="#dceafa",
            fg="#26384f",
        ).pack(pady=4)

        row = tk.Frame(main, bg="#dceafa")
        row.pack(fill="x", pady=8)

        buttons = [
            ("配對", lambda: self.send_pair()),
            ("Power B", lambda: self.send_cmd("Power B", 0x01, [0x01])),
            ("Power C", lambda: self.send_cmd("Power C", 0x01, [0x00])),
            ("Night B", lambda: self.send_cmd("Night B", 0x02, [0x01])),
            ("Night C", lambda: self.send_cmd("Night C", 0x02, [0x00])),
        ]

        for text, cmd in buttons:
            tk.Button(
                row,
                text=text,
                command=cmd,
                font=("Microsoft JhengHei UI", 11, "bold"),
                bg="#5f8eca",
                fg="white",
                width=10,
                height=2,
            ).pack(side="left", padx=4, expand=True)

        row2 = tk.Frame(main, bg="#dceafa")
        row2.pack(fill="x", pady=8)

        buttons2 = [
            ("亮度100", lambda: self.send_cmd("亮度100", 0x04, [100])),
            ("亮度1", lambda: self.send_cmd("亮度1", 0x04, [1])),
            ("色溫0", lambda: self.send_cmd("色溫0", 0x05, [0])),
            ("色溫100", lambda: self.send_cmd("色溫100", 0x05, [100])),
            ("睡眠", lambda: self.send_cmd("睡眠", 0x10, [])),
            ("感應", lambda: self.send_cmd("感應", 0x11, [])),
        ]

        for text, cmd in buttons2:
            tk.Button(
                row2,
                text=text,
                command=cmd,
                font=("Microsoft JhengHei UI", 10, "bold"),
                bg="#e8f0fa",
                fg="#26384f",
                width=10,
                height=2,
            ).pack(side="left", padx=4, expand=True)

        row3 = tk.Frame(main, bg="#dceafa")
        row3.pack(fill="x", pady=8)

        for i in range(1, 5):
            tk.Button(
                row3,
                text=f"記憶{i}",
                command=lambda g=i: self.send_cmd(f"記憶{g}", 0x03, [g]),
                font=("Microsoft JhengHei UI", 10, "bold"),
                bg="#e8f0fa",
                fg="#26384f",
                width=10,
                height=2,
            ).pack(side="left", padx=4, expand=True)

        row4 = tk.Frame(main, bg="#dceafa")
        row4.pack(fill="x", pady=8)

        raw_buttons = [
            ("RAW Power A", "FF000F180201FFFFFFFFFFFFFFFFFF03"),
            ("RAW Power B", "FF000F180301FFFFFFFFFFFFFFFFFF03"),
            ("RAW Night", "FF000F180902FFFFFFFFFFFFFFFFFF03"),
            ("RAW 亮度100", "FF000F18040464FFFFFFFFFFFFFFFF03"),
            ("RAW 感應", "FF000F180811FFFFFFFFFFFFFFFFFF03"),
            ("RAW 睡眠", "FF000F180910FFFFFFFFFFFFFFFFFF03"),
        ]

        for text, uuid_hex in raw_buttons:
            tk.Button(
                row4,
                text=text,
                command=lambda t=text, h=uuid_hex: self.send_raw(t, h),
                font=("Microsoft JhengHei UI", 9, "bold"),
                bg="#fff0b3",
                fg="#26384f",
                width=12,
                height=2,
            ).pack(side="left", padx=3, expand=True)

        tk.Label(
            main,
            text="UUID 16 bytes：",
            font=("Microsoft JhengHei UI", 11, "bold"),
            bg="#dceafa",
            fg="#26384f",
        ).pack(anchor="w", pady=(18, 2))

        self.uuid_box = tk.Text(main, height=3, wrap="word", font=("Consolas", 11))
        self.uuid_box.pack(fill="x")

        tk.Label(
            main,
            text="完整 Manufacturer Payload，不含 Company ID：",
            font=("Microsoft JhengHei UI", 11, "bold"),
            bg="#dceafa",
            fg="#26384f",
        ).pack(anchor="w", pady=(12, 2))

        self.payload_box = tk.Text(main, height=4, wrap="word", font=("Consolas", 11))
        self.payload_box.pack(fill="x")

        tk.Label(
            main,
            text="完整 BLE Manufacturer Data 概念：CompanyID=0118 + Payload",
            font=("Microsoft JhengHei UI", 10),
            bg="#dceafa",
            fg="#26384f",
        ).pack(anchor="w", pady=(12, 2))

        self.full_box = tk.Text(main, height=4, wrap="word", font=("Consolas", 11))
        self.full_box.pack(fill="x")

        tk.Button(
            main,
            text="開啟 log 檔位置：ble_send_debug_log.txt",
            command=self.show_log_hint,
            font=("Microsoft JhengHei UI", 10, "bold"),
            bg="#dfe9f6",
            fg="#26384f",
            height=2,
        ).pack(fill="x", pady=12)

    def show_log_hint(self):
        messagebox.showinfo("Log 檔", "log 檔會在 EXE 同資料夾：ble_send_debug_log.txt")

    def log_header(self):
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n\n")
            f.write("=" * 80 + "\n")
            f.write(f"Start Debug Session: {datetime.now()}\n")
            f.write("=" * 80 + "\n")

    def next_sequence(self):
        current = self.sequence
        self.sequence += 1
        if self.sequence > 9:
            self.sequence = 1
        return current

    def build_manufacturer_payload(self, uuid16: bytes) -> bytes:
        # Android 版等同：
        # addManufacturerData(0x0118, BE AC + UUID16 + Major + Minor + C5 00)
        return (
            bytes([0xBE, 0xAC])
            + uuid16
            + MAJOR.to_bytes(2, "big")
            + MINOR.to_bytes(2, "big")
            + bytes([0xC5, 0x00])
        )

    def update_boxes(self, label: str, uuid16: bytes, manufacturer_payload: bytes):
        uuid_hex = hex_bytes(uuid16)
        payload_hex = hex_bytes(manufacturer_payload)
        full_hex = "0118" + payload_hex

        self.uuid_box.delete("1.0", "end")
        self.uuid_box.insert("1.0", uuid_hex)

        self.payload_box.delete("1.0", "end")
        self.payload_box.insert("1.0", payload_hex)

        self.full_box.delete("1.0", "end")
        self.full_box.insert("1.0", full_hex)

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n時間: {datetime.now()}\n")
            f.write(f"功能: {label}\n")
            f.write(f"Company ID: 0x{COMPANY_ID:04X}\n")
            f.write(f"Major: 0x{MAJOR:04X}\n")
            f.write(f"Minor: 0x{MINOR:04X}\n")
            f.write(f"UUID16: {uuid_hex}\n")
            f.write(f"Manufacturer Payload(no company id): {payload_hex}\n")
            f.write(f"Full Manufacturer Data concept: {full_hex}\n")
            f.write("-" * 80 + "\n")

    def send_uuid(self, label: str, uuid16: bytes):
        if len(uuid16) != 16:
            messagebox.showerror("錯誤", f"UUID 長度錯誤：{len(uuid16)} bytes")
            return

        manufacturer_payload = self.build_manufacturer_payload(uuid16)
        self.update_boxes(label, uuid16, manufacturer_payload)

        self.status.set(f"發送中：{label}")

        try:
            self.sender.send(manufacturer_payload)
            self.status.set(f"已送出：{label}")
        except Exception as e:
            self.status.set("發送失敗")
            messagebox.showerror("BLE 發送失敗", str(e))

    def send_pair(self):
        seq = self.next_sequence()
        uuid = bytearray([0xFF, 0x00, 0x0F, PAIR_PANEL_CODE, seq, 0x13])
        uuid += bytearray([(MAJOR >> 8) & 0xFF, MAJOR & 0xFF, ZONE])
        while len(uuid) < 16:
            uuid.append(0xFF)
        self.send_uuid("配對", bytes(uuid[:16]))

    def send_cmd(self, label: str, cmd: int, data):
        seq = self.next_sequence()
        uuid = bytearray([0xFF, 0x00, 0x0F, DEVICE_CODE, seq, cmd])
        for x in data:
            uuid.append(max(0, min(255, int(x))))
        while len(uuid) < 15:
            uuid.append(0xFF)
        uuid.append(ZONE)
        self.send_uuid(label, bytes(uuid[:16]))

    def send_raw(self, label: str, uuid_hex: str):
        self.send_uuid(label, bytes.fromhex(uuid_hex))


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
