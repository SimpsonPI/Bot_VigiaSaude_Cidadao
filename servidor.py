"""
Gerenciador de processo do bot VigiaSaude Cidadão.
Uso: python servidor.py [start|stop|restart|status]
"""

import os
import sys
import signal
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

if sys.platform == "win32":
    _PYTHONW = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
    _PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    PYTHON = str(_PYTHONW) if _PYTHONW.exists() else (str(_PYTHON) if _PYTHON.exists() else sys.executable)
else:
    _PYTHON = BASE_DIR / ".venv" / "bin" / "python"
    PYTHON = str(_PYTHON) if _PYTHON.exists() else sys.executable

MAIN = BASE_DIR / "main.py"
PID_FILE = BASE_DIR / "servidor.pid"
LOG_FILE = BASE_DIR / "servidor.log"


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _read_pid():
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def status():
    pid = _read_pid()
    if pid and _is_running(pid):
        print(f"✅ Rodando (PID {pid})")
        return 0
    print("⛔ Parado")
    return 1


def start():
    pid = _read_pid()
    if pid and _is_running(pid):
        print(f"⚠️  Já está rodando (PID {pid})")
        return 0

    if not Path(PYTHON).exists():
        print(f"❌ Python do venv não encontrado em: {PYTHON}")
        return 1

    log = open(LOG_FILE, "a", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    if sys.platform == "win32":
        # Processo totalmente desacoplado do terminal pai
        creationflags = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_BREAKAWAY_FROM_JOB
            | subprocess.CREATE_NO_WINDOW
        )
        proc = subprocess.Popen(
            [PYTHON, "-u", str(MAIN)],
            cwd=str(BASE_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=creationflags,
            close_fds=True,
        )
    else:
        proc = subprocess.Popen(
            [PYTHON, "-u", str(MAIN)],
            cwd=str(BASE_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
            close_fds=True,
        )

    PID_FILE.write_text(str(proc.pid))

    time.sleep(2)
    if _is_running(proc.pid):
        print(f"🚀 Iniciado (PID {proc.pid})")
        print(f"📄 Log: {LOG_FILE}")
        return 0
    print("❌ Falha ao iniciar — verifique o log:")
    print(f"   {LOG_FILE}")
    return 1


def stop():
    pid = _read_pid()
    if not pid or not _is_running(pid):
        print("⛔ Não está rodando")
        if PID_FILE.exists():
            PID_FILE.unlink()
        return 0

    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                check=False,
                capture_output=True,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not _is_running(pid):
                    break
                time.sleep(0.25)
            else:
                os.kill(pid, signal.SIGKILL)
    except Exception as e:
        print(f"⚠️  Erro ao parar: {e}")

    if PID_FILE.exists():
        PID_FILE.unlink()
    print(f"🛑 Parado (PID {pid})")
    return 0


def restart():
    stop()
    time.sleep(1)
    return start()


COMMANDS = {
    "start": start,
    "stop": stop,
    "restart": restart,
    "status": status,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Uso: python servidor.py [start|stop|restart|status]")
        return 1
    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
