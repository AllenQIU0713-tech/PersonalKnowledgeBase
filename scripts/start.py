"""Start only owned loopback services; Python standard library, no downloads."""
import argparse
import os
from pathlib import Path
import re
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser

REPO = Path(__file__).resolve().parents[1]
MODEL = Path.home()/'Library/Application Support/PersonalKnowledgeBase/models/Qwen3-Embedding-0.6B-Q8_0.gguf'
MODEL_SIZE = 639150592
MODEL_SHA = '06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439'
RUNTIME = Path('/opt/homebrew/Cellar/llama.cpp/0.5.0/bin/llama-server')
DATA = Path.home()/'Library/Application Support/PersonalKnowledgeBase'
PREFIX = '请用浏览器打开（一次性链接）：'


def port_in_use(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        try:
            connection.connect(('127.0.0.1', port))
        except ConnectionRefusedError:
            return False
        except OSError:
            # Unknown state is not evidence that a port is free.
            return True
        return True


def preflight(model=MODEL, runtime=RUNTIME):
    if not model.is_file() or model.stat().st_size != MODEL_SIZE:
        raise ValueError('固定向量模型缺失或文件大小不符；请核对交接文档，不自动下载。')
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        raise ValueError('既有llama-server不可执行；请核对交接文档。')
    for port in (8765, 8766):
        if port_in_use(port):
            raise ValueError('端口%d已占用或无法确认空闲，请先停止原来的自有会话；不会结束其他进程。' % port)


def startup_link(line):
    if not line.startswith(PREFIX):
        return None
    link = line[len(PREFIX):].strip()
    if not re.fullmatch(r'http://127\.0\.0\.1:8765/unlock\?token=[A-Za-z0-9_-]{1,256}', link):
        raise ValueError('应用返回的启动链接不符合本机固定入口。')
    return link


def stop_owned(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('模型健康检查不允许重定向')


def wait_model(process, timeout=120):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('向量模型启动后提前退出。')
        try:
            with opener.open('http://127.0.0.1:8766/health', timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.5)
    raise RuntimeError('向量模型在120秒内未就绪；已停止本次启动。')


def run(data_dir, no_browser=False):
    owned = []
    try:
        preflight()
        print('个人知识库 1.0 · 资料目录：'+str(data_dir))
        print('正在启动本机向量模型；按Ctrl+C可停止本次应用与模型。')
        # Model output has no bootstrap credentials. TemporaryFile is unlinked on exit.
        with tempfile.TemporaryFile() as model_log:
            model = subprocess.Popen([str(RUNTIME), '-m', str(MODEL), '--embedding',
                '--pooling', 'last', '-ub', '8192', '-c', '4096', '-np', '1',
                '--host', '127.0.0.1', '--port', '8766'], cwd=REPO,
                stdout=model_log, stderr=subprocess.STDOUT, start_new_session=True)
            owned.append(model)
            wait_model(model)
            app = subprocess.Popen([sys.executable, '-u', '-B', '-m', 'pkb.server',
                '--data-dir', str(data_dir), '--port', '8765', '--embedding-port', '8766',
                '--embedding-model', MODEL_SHA], cwd=REPO, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, start_new_session=True)
            owned.append(app)
            opened = False
            output = queue.Queue()
            def collect_output():
                try:
                    for text in app.stdout:
                        output.put(text)
                finally:
                    output.put(None)
            threading.Thread(target=collect_output, daemon=True).start()
            app_deadline = time.monotonic() + 120
            while True:
                if model.poll() is not None:
                    raise RuntimeError('向量模型意外退出，正在停止本次知识库。')
                if not opened and time.monotonic() >= app_deadline:
                    raise RuntimeError('知识库在120秒内未提供启动链接。')
                try:
                    line = output.get(timeout=.5)
                except queue.Empty:
                    continue
                if line is None:
                    break
                link = startup_link(line)
                if link:
                    print('应用已就绪。若显示安全入口，点击“继续打开本机知识库”。')
                    try:
                        browser_opened = not no_browser and not opened and webbrowser.open(link, new=2)
                    except webbrowser.Error:
                        browser_opened = False
                    if not browser_opened:
                        print(PREFIX+link, flush=True)
                    opened = True
                else:
                    print(line, end='', flush=True)
            code = app.wait()
            if code:
                raise RuntimeError('知识库服务退出，退出码%d。' % code)
            if not opened:
                raise RuntimeError('服务退出前未提供启动链接。')
    finally:
        for process in reversed(owned):
            stop_owned(process)


def main():
    parser = argparse.ArgumentParser(description='个人知识库1.0一键启动；Ctrl+C停止自有服务')
    parser.add_argument('--data-dir', type=Path, default=DATA)
    parser.add_argument('--check', action='store_true', help='仅检查，不启动服务或打开资料库')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        if args.check:
            preflight()
            print('文件/大小及端口检查通过；未重新计算模型SHA，未启动模型、应用或资料库。')
        else:
            run(args.data_dir.expanduser().resolve(), args.no_browser)
        return 0
    except KeyboardInterrupt:
        print('\n已停止本次启动的知识库与模型。')
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print('启动失败：'+str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
