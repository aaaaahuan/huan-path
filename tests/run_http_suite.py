"""Run isolated checks on 8766; never write to the real jobs library or cache."""
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REAL_JOBS = ROOT / 'jobs'
WORK = ROOT / 'work'


def snapshot():
    return {
        'directories': sorted(str(p.relative_to(REAL_JOBS)) for p in REAL_JOBS.rglob('*') if p.is_dir()),
        'files': {str(p.relative_to(REAL_JOBS)): [p.stat().st_mtime_ns, p.stat().st_size]
                  for p in sorted(REAL_JOBS.rglob('*')) if p.is_file()},
    }


def main():
    WORK.mkdir(exist_ok=True)
    before = snapshot()
    # Fail if occupied; never stop another service, including the one on 8765.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 8766))
    temporary = Path(tempfile.mkdtemp(prefix='huan-path-tests-'))
    server = None
    try:
        env = dict(os.environ, HUAN_PATH_JOBS_DIR=str(temporary), HUAN_PATH_TRACKS_DIR=str(temporary / 'tracks'))
        for source in sorted(REAL_JOBS.iterdir()):
            if source.is_dir() and (source / 'status.json').is_file() and json.loads((source / 'status.json').read_text())['status'] == 'completed':
                shutil.copytree(source, temporary / source.name, ignore=shutil.ignore_patterns('models'))
        assert any(temporary.iterdir()), '需要已有完成作品作为只读复制源'
        print(f'Temporary jobs: {temporary}', flush=True)
        with (WORK / 'isolated-server.log').open('w') as log:
            server = subprocess.Popen([sys.executable, 'server.py', '--port', '8766'], cwd=ROOT,
                                      env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError('测试服务退出，请查看 work/isolated-server.log')
                try:
                    with opener.open('http://127.0.0.1:8766/api/health', timeout=.5) as response:
                        assert response.status == 200
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise TimeoutError('测试服务未就绪')
            commands = [
                [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
                ['node', 'tests/job-ui.mjs'], ['node', 'tests/upload-ui.mjs'], ['node', 'tests/search-ui.mjs'], ['node', 'tests/roads-ui.mjs'], ['node', 'tests/places-occlusion.mjs'],
                [sys.executable, 'tests/http_checks.py', '--url', 'http://127.0.0.1:8766'],
                ['node', 'tests/workbench-browser.cjs'], ['node', 'tests/roads-browser.cjs'],
            ]
            failures = []
            for command in commands:
                print('RUN', ' '.join(command), flush=True)
                try:
                    subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=120)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                    failures.append(str(error))
            print('SKIP tests/e2e_upload.py: 实网构建可能写共享 cache/；本套件禁止修改 cache/。', flush=True)
            if failures:
                raise RuntimeError('\n'.join(failures))
    finally:
        try:
            if server is not None:
                # Only our new process group, including any pipeline subprocesses.
                try:
                    os.killpg(server.pid, signal.SIGTERM)
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGKILL)
                    server.wait()
                except ProcessLookupError:
                    pass
        finally:
            shutil.rmtree(temporary)
            try:
                after = snapshot()
                old = {**dict.fromkeys(before['directories']), **before['files']}
                new = {**dict.fromkeys(after['directories']), **after['files']}
                added = sorted(new.keys() - old.keys())
                removed = sorted(old.keys() - new.keys())
                changed = sorted(p for p in old.keys() & new.keys() if old[p] != new[p])
                print(f'真实 jobs/ 差异：added={added}, removed={removed}, changed={changed}', flush=True)
            except Exception as error:
                print(f'真实 jobs/ 差异汇总失败：{error}', file=sys.stderr)
            print('临时根已删除，测试服务已关闭。', flush=True)


if __name__ == '__main__':
    main()
