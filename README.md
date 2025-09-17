# 串口调试助手

一个使用 Python 与 Tkinter 编写的轻量级串口调试助手，界面参考正点原子的串口助手，支持自定义命令列表与日志记录。

## 功能特点

- 自动列出当前可用串口并支持手动刷新。
- 发送/接收窗口带时间戳显示，支持一键清空。
- 可选在发送时自动添加 `\r\n` 换行。
- 自定义命令列表，支持自由添加、删除并双击发送。
- 可将所有收发内容记录到指定的日志文件。

## 快速开始

1. 安装依赖（需要 Python 3.8+）：

   ```bash
   pip install -r requirements.txt
   ```

2. 运行工具：

   ```bash
   python serial_debugger.py
   ```

3. 选择串口和波特率后点击“打开串口”，即可进行数据调试。

## 依赖

- [pyserial](https://pyserial.readthedocs.io/en/latest/)

如未安装 `pyserial`，程序会给出提示。
