# -*- coding: utf-8 -*-
"""停止后台服务（Flask + 公网隧道）"""
import json
import os
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE_DIR, ".run", "service.json")


def kill(pid):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        print(f"已停止进程 {pid}")
    except OSError:
        pass


def main():
    if not os.path.exists(STATE):
        print("没有找到运行状态文件，服务可能未启动。")
        return
    try:
        state = json.load(open(STATE, encoding="utf-8"))
    except (ValueError, OSError):
        print("状态文件损坏，尝试按端口清理。")
        state = {}

    for name in ("tunnel", "service", "app"):
        pid = state.get(name)
        if pid:
            kill(pid)
    print("已停止。若仍有残留，请结束占用 5000 端口的进程。")


if __name__ == "__main__":
    main()
