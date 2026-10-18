# -*- coding: utf-8 -*-
"""校园闲置信息墙 · 后台常驻启动器

作用：
  1. 在后台启动 Flask（不占用终端窗口）
  2. 同时启动公网隧道（ssh -R），自动把公网地址写进 public_url.txt
  3. 任一进程意外退出会自动拉起

用法：
  python run_service.py        # 前台运行（可看到日志）
  start_wall.bat               # 后台静默启动（推荐）
  stop_wall.bat                # 停止服务
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
RUN_DIR = os.path.join(BASE_DIR, ".run")
PUBLIC_URL_FILE = os.path.join(BASE_DIR, "public_url.txt")
PORT = int(os.environ.get("PORT", 5000))
TUNNEL_HOST = "nokey@localhost.run"
URL_RE = re.compile(r"https://[a-z0-9-]+\.lhr\.life")
TUNNEL_KEY = os.environ.get("FLEA_TUNNEL_KEY") or os.path.join(
    os.path.expanduser("~"), ".ssh", "wall_tunnel"
)
TUNNEL_SUBDOMAIN = os.environ.get("FLEA_TUNNEL_SUBDOMAIN", "").strip()

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(RUN_DIR, exist_ok=True)

_procs = {}


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(os.path.join(LOG_DIR, "service.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def write_state():
    ids = {k: (p.pid if p and p.poll() is None else None) for k, p in _procs.items()}
    try:
        with open(os.path.join(RUN_DIR, "service.json"), "w", encoding="utf-8") as f:
            json.dump(ids, f)
    except OSError:
        pass


def start_app():
    out = open(os.path.join(LOG_DIR, "app.log"), "ab", buffering=0)
    p = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "app.py")],
        cwd=BASE_DIR,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    _procs["app"] = p
    write_state()
    log(f"Flask 已启动（pid {p.pid}）→ http://127.0.0.1:{PORT}")
    return p


def start_tunnel():
    args = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=4",
        "-o", "TCPKeepAlive=yes",
        "-o", "ExitOnForwardFailure=yes",
    ]
    # 如果已经配置了隧道专用密钥（注册 localhost.run 账号后可获得固定域名）
    if os.path.exists(TUNNEL_KEY):
        args += ["-i", TUNNEL_KEY, "-o", "IdentitiesOnly=yes"]
    remote = f"{TUNNEL_SUBDOMAIN}:80:localhost:{PORT}" if TUNNEL_SUBDOMAIN else f"80:localhost:{PORT}"
    args += ["-R", remote, TUNNEL_HOST]

    p = subprocess.Popen(
        args,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )
    _procs["tunnel"] = p
    write_state()
    log(f"公网隧道已启动（pid {p.pid}），等待分配地址…")
    return p


def watch_tunnel(proc):
    """读取隧道输出，拿到公网地址后写文件（并记录历史，方便找回新地址）"""
    try:
        for line in proc.stdout:
            m = URL_RE.search(line or "")
            if m:
                url = m.group(0)
                with open(PUBLIC_URL_FILE, "w", encoding="utf-8") as f:
                    f.write(url + "\n")
                with open(os.path.join(LOG_DIR, "url_history.log"), "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {url}\n")
                log(f"公网地址：{url}")
    except (ValueError, OSError):
        pass


def cleanup(*_args):
    log("正在停止服务…")
    for key in ("tunnel", "app"):
        p = _procs.get(key)
        if p and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass
    write_state()
    sys.exit(0)


def main():
    if "--check" in sys.argv:
        if os.path.exists(PUBLIC_URL_FILE):
            print(open(PUBLIC_URL_FILE, encoding="utf-8").read().strip())
        else:
            print("还没有分配公网地址")
        return

    lock = os.path.join(RUN_DIR, "service.json")
    if os.path.exists(lock):
        try:
            state = json.load(open(lock, encoding="utf-8"))
            for pid in state.values():
                if pid and _alive(pid):
                    print("服务已经在运行中，无需重复启动。公网地址见 public_url.txt")
                    return
        except (ValueError, OSError):
            pass

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    start_app()
    time.sleep(1.5)

    proc = start_tunnel()
    import threading
    threading.Thread(target=watch_tunnel, args=(proc,), daemon=True).start()

    log("守护中：进程掉线会自动重启（Ctrl+C 停止）")
    while True:
        time.sleep(8)
        for key, starter in (("app", start_app), ("tunnel", start_tunnel)):
            p = _procs.get(key)
            if p is None or p.poll() is not None:
                log(f"{key} 进程已退出（code {getattr(p, 'returncode', '?')}），正在重启…")
                newp = starter()
                if key == "tunnel":
                    threading.Thread(target=watch_tunnel, args=(newp,), daemon=True).start()


def _alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        return str(pid) in (out.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    main()
