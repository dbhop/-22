"""简单的串口调试助手，使用 Tkinter 实现。

特点：
    * 自动枚举串口并允许手动刷新
    * 收发数据展示并带时间戳
    * 可选日志文件记录
    * 自定义命令列表支持添加、删除与双击发送

运行前需安装 ``pyserial``：
```
pip install pyserial
```
"""
from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - 在运行前提示缺少依赖
    serial = None  # type: ignore
    list_ports = None  # type: ignore


QueueItem = Tuple[str, str]


class SerialDebuggerApp:
    """串口调试助手主界面。"""

    def __init__(self, master: tk.Tk) -> None:
        if serial is None:
            messagebox.showerror(
                "缺少依赖",
                "未检测到 pyserial，请先执行 `pip install pyserial` 后再运行。",
            )
            master.destroy()
            return

        self.master = master
        self.master.title("串口调试助手")
        self.master.geometry("820x600")
        self.master.minsize(720, 480)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="115200")
        self.status_var = tk.StringVar(value="未连接")
        self.newline_var = tk.BooleanVar(value=True)
        self.log_var = tk.BooleanVar(value=False)
        self.log_path_var = tk.StringVar(value="未选择")

        self.serial_port: Optional[serial.Serial] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        self.read_queue: "queue.Queue[QueueItem]" = queue.Queue()

        self.log_file_path: Optional[Path] = None

        self._build_widgets()
        self.refresh_ports()
        self.master.after(150, self.process_incoming)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        self.master.columnconfigure(0, weight=1)

        conn_frame = ttk.LabelFrame(self.master, text="连接设置")
        conn_frame.grid(row=0, column=0, padx=12, pady=(10, 5), sticky="nsew")
        conn_frame.columnconfigure(1, weight=1)
        conn_frame.columnconfigure(5, weight=1)

        ttk.Label(conn_frame, text="串口:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=18, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=6, pady=6, sticky="ew")

        refresh_btn = ttk.Button(conn_frame, text="刷新", command=self.refresh_ports)
        refresh_btn.grid(row=0, column=2, padx=6, pady=6)

        ttk.Label(conn_frame, text="波特率:").grid(row=0, column=3, padx=6, pady=6, sticky="e")
        baud_values = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
        self.baud_combo = ttk.Combobox(conn_frame, textvariable=self.baud_var, values=baud_values, width=10)
        self.baud_combo.grid(row=0, column=4, padx=6, pady=6, sticky="w")

        self.connect_btn = ttk.Button(conn_frame, text="打开串口", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=5, padx=6, pady=6, sticky="e")

        ttk.Label(conn_frame, textvariable=self.status_var, foreground="#2c7a7b").grid(
            row=1, column=0, columnspan=6, padx=6, pady=(0, 6), sticky="w"
        )

        log_frame = ttk.LabelFrame(self.master, text="日志设置")
        log_frame.grid(row=1, column=0, padx=12, pady=5, sticky="nsew")
        log_frame.columnconfigure(1, weight=1)

        log_check = ttk.Checkbutton(log_frame, text="启用日志记录", variable=self.log_var, command=self.toggle_logging)
        log_check.grid(row=0, column=0, padx=6, pady=6, sticky="w")

        self.log_path_label = ttk.Label(log_frame, textvariable=self.log_path_var, foreground="#4a5568")
        self.log_path_label.grid(row=0, column=1, padx=6, pady=6, sticky="w")

        choose_log_btn = ttk.Button(log_frame, text="选择日志文件", command=self.choose_log_file)
        choose_log_btn.grid(row=0, column=2, padx=6, pady=6)

        receive_frame = ttk.LabelFrame(self.master, text="接收区")
        receive_frame.grid(row=2, column=0, padx=12, pady=5, sticky="nsew")
        receive_frame.rowconfigure(1, weight=1)
        receive_frame.columnconfigure(0, weight=1)

        clear_btn = ttk.Button(receive_frame, text="清空显示", command=self.clear_receive_text)
        clear_btn.grid(row=0, column=0, padx=6, pady=(6, 0), sticky="e")

        text_container = ttk.Frame(receive_frame)
        text_container.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        text_container.columnconfigure(0, weight=1)
        text_container.rowconfigure(0, weight=1)

        self.receive_text = tk.Text(text_container, height=16, wrap="word", state="disabled", font=("Consolas", 10))
        self.receive_text.grid(row=0, column=0, sticky="nsew")

        text_scroll = ttk.Scrollbar(text_container, orient="vertical", command=self.receive_text.yview)
        text_scroll.grid(row=0, column=1, sticky="ns")
        self.receive_text.configure(yscrollcommand=text_scroll.set)

        send_frame = ttk.LabelFrame(self.master, text="发送区")
        send_frame.grid(row=3, column=0, padx=12, pady=5, sticky="ew")
        send_frame.columnconfigure(0, weight=1)

        self.send_entry = ttk.Entry(send_frame)
        self.send_entry.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        self.send_entry.bind("<Return>", lambda event: self.send_data())

        send_btn = ttk.Button(send_frame, text="发送", command=self.send_data)
        send_btn.grid(row=0, column=1, padx=6, pady=6)

        newline_check = ttk.Checkbutton(send_frame, text="自动换行 (\r\n)", variable=self.newline_var)
        newline_check.grid(row=0, column=2, padx=6, pady=6)

        cmd_frame = ttk.LabelFrame(self.master, text="命令列表")
        cmd_frame.grid(row=4, column=0, padx=12, pady=(5, 12), sticky="nsew")
        cmd_frame.columnconfigure(0, weight=1)
        cmd_frame.rowconfigure(1, weight=1)

        cmd_entry_frame = ttk.Frame(cmd_frame)
        cmd_entry_frame.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        cmd_entry_frame.columnconfigure(0, weight=1)

        self.command_entry = ttk.Entry(cmd_entry_frame)
        self.command_entry.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        self.command_entry.bind("<Return>", lambda event: self.add_command())

        add_cmd_btn = ttk.Button(cmd_entry_frame, text="添加", command=self.add_command)
        add_cmd_btn.grid(row=0, column=1, padx=6, pady=6)

        del_cmd_btn = ttk.Button(cmd_entry_frame, text="删除选中", command=self.delete_selected_command)
        del_cmd_btn.grid(row=0, column=2, padx=6, pady=6)

        list_container = ttk.Frame(cmd_frame)
        list_container.grid(row=1, column=0, padx=6, pady=(0, 6), sticky="nsew")
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        self.command_listbox = tk.Listbox(list_container, height=6, selectmode=tk.SINGLE)
        self.command_listbox.grid(row=0, column=0, sticky="nsew")
        self.command_listbox.bind("<Double-1>", self.send_command_from_list)
        self.command_listbox.bind("<Return>", self.send_command_from_list)

        cmd_scroll = ttk.Scrollbar(list_container, orient="vertical", command=self.command_listbox.yview)
        cmd_scroll.grid(row=0, column=1, sticky="ns")
        self.command_listbox.configure(yscrollcommand=cmd_scroll.set)

    # ------------------------------------------------------------------
    # 串口相关
    # ------------------------------------------------------------------
    def refresh_ports(self) -> None:
        if list_ports is None:
            self.port_combo["values"] = []
            self.status_var.set("未检测到 pyserial")
            return

        ports = [port.device for port in list_ports.comports()]
        self.port_combo["values"] = ports
        if ports:
            if self.port_var.get() not in ports:
                self.port_var.set(ports[0])
            self.status_var.set(f"可用串口: {', '.join(ports)}")
        else:
            self.port_var.set("")
            self.status_var.set("未检测到可用串口")

    def toggle_connection(self) -> None:
        if self.serial_port and self.serial_port.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self) -> None:
        if serial is None:
            messagebox.showerror("缺少依赖", "请先安装 pyserial 库")
            return

        port = self.port_var.get()
        if not port:
            messagebox.showwarning("串口选择", "请先选择要打开的串口")
            return

        try:
            baudrate = int(self.baud_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "波特率必须是数字")
            return

        try:
            self.serial_port = serial.Serial(port=port, baudrate=baudrate, timeout=0.1)
        except serial.SerialException as exc:  # type: ignore[attr-defined]
            messagebox.showerror("打开失败", f"无法打开 {port}: {exc}")
            self.serial_port = None
            return

        self.running = True
        self.reader_thread = threading.Thread(target=self.read_from_serial, daemon=True)
        self.reader_thread.start()
        self.connect_btn.configure(text="关闭串口")
        self.status_var.set(f"已连接: {port} @ {baudrate}bps")
        self.queue_message("INFO", f"串口 {port} 已打开")

    def disconnect_serial(self) -> None:
        self.running = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.5)
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except serial.SerialException:  # type: ignore[attr-defined]
                pass
        self.serial_port = None
        self.reader_thread = None
        self.connect_btn.configure(text="打开串口")
        self.status_var.set("未连接")
        self.queue_message("INFO", "串口已关闭")

    def read_from_serial(self) -> None:
        assert self.serial_port is not None
        while self.running and self.serial_port and self.serial_port.is_open:
            try:
                waiting = self.serial_port.in_waiting
                data = self.serial_port.read(waiting or 1)
            except serial.SerialException as exc:  # type: ignore[attr-defined]
                self.queue_message("INFO", f"读取错误: {exc}")
                self.running = False
                break

            if data:
                decoded = data.decode("utf-8", errors="replace")
                self.queue_message("RX", decoded.rstrip("\r"))

        # 避免线程退出后串口仍保持打开
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except serial.SerialException:  # type: ignore[attr-defined]
                pass
        self.serial_port = None

    # ------------------------------------------------------------------
    # 数据展示与日志
    # ------------------------------------------------------------------
    def queue_message(self, kind: str, message: str) -> None:
        self.read_queue.put((kind, message))

    def process_incoming(self) -> None:
        try:
            while True:
                kind, message = self.read_queue.get_nowait()
                self.append_text(kind, message)
        except queue.Empty:
            pass
        finally:
            self.master.after(120, self.process_incoming)

    def append_text(self, kind: str, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        if kind == "INFO":
            formatted = f"[{timestamp}] {message}"
        else:
            formatted = f"[{timestamp}] {kind}: {message}"

        self.receive_text.configure(state="normal")
        self.receive_text.insert(tk.END, formatted + "\n")
        self.receive_text.see(tk.END)
        self.receive_text.configure(state="disabled")

        if self.log_var.get() and self.log_file_path is not None:
            self.write_log_line(formatted)

    def clear_receive_text(self) -> None:
        self.receive_text.configure(state="normal")
        self.receive_text.delete("1.0", tk.END)
        self.receive_text.configure(state="disabled")

    def toggle_logging(self) -> None:
        if not self.log_var.get():
            self.log_path_var.set(str(self.log_file_path) if self.log_file_path else "未选择")
            return

        if self.log_file_path is None:
            chosen = self.choose_log_file()
            if not chosen:
                self.log_var.set(False)
                return
        else:
            self.log_path_var.set(str(self.log_file_path))

    def choose_log_file(self) -> bool:
        filename = filedialog.asksaveasfilename(
            title="选择日志文件",
            defaultextension=".log",
            filetypes=[("日志文件", "*.log"), ("所有文件", "*.*")],
        )
        if not filename:
            return False

        self.log_file_path = Path(filename)
        self.log_path_var.set(str(self.log_file_path))
        return True

    def write_log_line(self, text: str) -> None:
        if self.log_file_path is None:
            return
        try:
            with self.log_file_path.open("a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except OSError as exc:
            messagebox.showerror("日志错误", f"写入日志失败: {exc}")
            self.log_var.set(False)

    # ------------------------------------------------------------------
    # 发送数据与命令列表
    # ------------------------------------------------------------------
    def send_data(self) -> None:
        text = self.send_entry.get().strip()
        self.send_entry.delete(0, tk.END)
        self.send_text(text)

    def send_text(self, text: str) -> None:
        if not text:
            return
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("串口未打开", "请先打开串口后再发送数据")
            return

        payload = text
        if self.newline_var.get():
            payload += "\r\n"

        try:
            self.serial_port.write(payload.encode("utf-8"))
        except serial.SerialException as exc:  # type: ignore[attr-defined]
            messagebox.showerror("发送失败", f"写入串口失败: {exc}")
            self.disconnect_serial()
            return

        self.queue_message("TX", text)

    def add_command(self) -> None:
        command = self.command_entry.get().strip()
        if not command:
            return
        self.command_listbox.insert(tk.END, command)
        self.command_entry.delete(0, tk.END)

    def delete_selected_command(self) -> None:
        selection = self.command_listbox.curselection()
        if not selection:
            return
        self.command_listbox.delete(selection[0])

    def send_command_from_list(self, event: tk.Event) -> None:
        selection = self.command_listbox.curselection()
        if not selection:
            return
        command = self.command_listbox.get(selection[0])
        self.send_text(command)

    # ------------------------------------------------------------------
    # 退出处理
    # ------------------------------------------------------------------
    def on_close(self) -> None:
        self.disconnect_serial()
        self.master.destroy()


def main() -> None:
    if serial is None:
        sys.stderr.write("未安装 pyserial，请先执行: pip install pyserial\n")
        return

    root = tk.Tk()
    SerialDebuggerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
