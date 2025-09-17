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
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - 在运行前提示缺少依赖
    serial = None  # type: ignore
    list_ports = None  # type: ignore


QueueItem = Tuple[str, str]


@dataclass
class SendRow:
    """发送区中的一行配置。"""

    frame: ttk.Frame
    index_label: ttk.Label
    select_var: tk.BooleanVar
    entry: ttk.Entry


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
        self.master.geometry("820x620")
        self.master.minsize(720, 520)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="115200")
        self.status_var = tk.StringVar(value="未连接")
        self.newline_var = tk.BooleanVar(value=True)
        self.loop_var = tk.BooleanVar(value=False)
        self.log_var = tk.BooleanVar(value=False)
        self.log_path_var = tk.StringVar(value="未选择")
        self.loop_interval_var = tk.StringVar(value="1000")

        self.serial_port: Optional[serial.Serial] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        self.read_queue: "queue.Queue[QueueItem]" = queue.Queue()

        self.log_file_path: Optional[Path] = None
        self.send_rows: List["SendRow"] = []
        self.loop_selected_rows: List["SendRow"] = []
        self.loop_job: Optional[str] = None
        self.loop_index = 0
        self.loop_running = False
        self.loop_delay_ms = 1000

        self._build_widgets()
        self.refresh_ports()
        self.master.after(150, self.process_incoming)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(2, weight=2)
        self.master.rowconfigure(3, weight=3)
        self.master.rowconfigure(4, weight=2)

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

        self.receive_text = tk.Text(text_container, height=12, wrap="word", state="disabled", font=("Consolas", 10))
        self.receive_text.grid(row=0, column=0, sticky="nsew")

        text_scroll = ttk.Scrollbar(text_container, orient="vertical", command=self.receive_text.yview)
        text_scroll.grid(row=0, column=1, sticky="ns")
        self.receive_text.configure(yscrollcommand=text_scroll.set)

        send_frame = ttk.LabelFrame(self.master, text="发送区")
        send_frame.grid(row=3, column=0, padx=12, pady=5, sticky="nsew")
        send_frame.columnconfigure(0, weight=1)
        send_frame.rowconfigure(1, weight=1)

        control_bar = ttk.Frame(send_frame)
        control_bar.grid(row=0, column=0, padx=6, pady=(6, 3), sticky="ew")
        control_bar.columnconfigure(4, weight=1)

        add_row_btn = ttk.Button(control_bar, text="添加发送行", command=self.add_send_row)
        add_row_btn.grid(row=0, column=0, padx=(0, 6))

        send_selected_btn = ttk.Button(control_bar, text="发送选中", command=self.send_selected_rows_once)
        send_selected_btn.grid(row=0, column=1, padx=(0, 6))

        loop_check = ttk.Checkbutton(control_bar, text="自动循环发送", variable=self.loop_var, command=self.toggle_loop_send)
        loop_check.grid(row=0, column=2, padx=(0, 6))

        ttk.Label(control_bar, text="间隔(ms):").grid(row=0, column=3, padx=(0, 3))
        interval_entry = ttk.Entry(control_bar, textvariable=self.loop_interval_var, width=8)
        interval_entry.grid(row=0, column=4, padx=(0, 6), sticky="w")

        self.send_rows_container = ttk.Frame(send_frame)
        self.send_rows_container.grid(row=1, column=0, padx=6, pady=3, sticky="nsew")
        self.send_rows_container.columnconfigure(0, weight=1)

        newline_check = ttk.Checkbutton(send_frame, text="自动换行 (\r\n)", variable=self.newline_var)
        newline_check.grid(row=2, column=0, padx=6, pady=(0, 6), sticky="w")

        self.add_send_row()

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
        if self.loop_running:
            self.stop_loop_send()
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
    def add_send_row(self, preset: str = "") -> None:
        row_frame = ttk.Frame(self.send_rows_container)
        row_frame.columnconfigure(2, weight=1)

        select_var = tk.BooleanVar(value=False)
        select_btn = ttk.Checkbutton(row_frame, variable=select_var)
        select_btn.grid(row=0, column=0, padx=(0, 4), pady=3)

        index_label = ttk.Label(row_frame, width=3, anchor="e")
        index_label.grid(row=0, column=1, padx=(0, 6))

        entry = ttk.Entry(row_frame)
        entry.grid(row=0, column=2, padx=(0, 6), pady=3, sticky="ew")
        if preset:
            entry.insert(0, preset)

        send_btn = ttk.Button(row_frame, text="发送")
        send_btn.grid(row=0, column=3, padx=(0, 6))

        delete_btn = ttk.Button(row_frame, text="删除")
        delete_btn.grid(row=0, column=4)

        row = SendRow(frame=row_frame, index_label=index_label, select_var=select_var, entry=entry)
        self.send_rows.append(row)

        send_btn.configure(command=lambda r=row: self.send_row_text(r))
        delete_btn.configure(command=lambda r=row: self.remove_send_row(r))
        entry.bind("<Return>", lambda event, r=row: self.send_row_text(r))

        self.update_send_rows_layout()

    def update_send_rows_layout(self) -> None:
        for idx, row in enumerate(self.send_rows, start=1):
            row.index_label.configure(text=str(idx))
            row.frame.grid(row=idx - 1, column=0, sticky="ew")

    def remove_send_row(self, row: SendRow) -> None:
        if row not in self.send_rows:
            return
        if self.loop_running:
            self.stop_loop_send()
        row.frame.destroy()
        self.send_rows.remove(row)
        if not self.send_rows:
            self.add_send_row()
        else:
            self.update_send_rows_layout()

    def send_row_text(self, row: SendRow) -> None:
        text = row.entry.get()
        if not text:
            return
        self.send_text(text)

    def send_selected_rows_once(self) -> None:
        selected = [row for row in self.send_rows if row.select_var.get()]
        if not selected:
            messagebox.showinfo("发送选中", "请先勾选需要发送的行")
            return
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("串口未打开", "请先打开串口后再发送数据")
            return
        for row in selected:
            self.send_row_text(row)

    def toggle_loop_send(self) -> None:
        if self.loop_var.get():
            self.start_loop_send()
        else:
            self.stop_loop_send()

    def start_loop_send(self) -> None:
        if self.loop_running:
            self.stop_loop_send()
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("串口未打开", "请先打开串口后再开始循环发送")
            self.loop_var.set(False)
            return

        selected = [row for row in self.send_rows if row.select_var.get()]
        if not selected:
            messagebox.showinfo("循环发送", "请至少勾选一行发送内容")
            self.loop_var.set(False)
            return

        try:
            interval = int(self.loop_interval_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "间隔必须是非负整数")
            self.loop_var.set(False)
            return

        if interval < 0:
            messagebox.showerror("参数错误", "间隔必须是非负整数")
            self.loop_var.set(False)
            return

        self.loop_delay_ms = interval
        self.loop_selected_rows = selected
        self.loop_index = 0
        self.loop_running = True
        self.perform_loop_step()

    def perform_loop_step(self) -> None:
        if not self.loop_running:
            return
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("串口未打开", "串口已关闭，停止循环发送")
            self.stop_loop_send()
            return
        if not self.loop_selected_rows:
            self.stop_loop_send()
            return

        row = self.loop_selected_rows[self.loop_index]
        self.loop_index = (self.loop_index + 1) % len(self.loop_selected_rows)
        text = row.entry.get()
        if text:
            self.send_text(text)

        delay = max(self.loop_delay_ms, 0)
        if delay == 0:
            self.loop_job = self.master.after_idle(self.perform_loop_step)
        else:
            self.loop_job = self.master.after(delay, self.perform_loop_step)

    def stop_loop_send(self) -> None:
        if self.loop_job is not None:
            try:
                self.master.after_cancel(self.loop_job)
            except ValueError:
                pass
            self.loop_job = None
        self.loop_running = False
        self.loop_selected_rows = []
        if self.loop_var.get():
            self.loop_var.set(False)

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
