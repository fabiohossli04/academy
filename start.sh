#!/usr/bin/env bash
# Startet den lokalen Tutor-Server und öffnet die Academy im Browser.
set -euo pipefail
cd "$(dirname "$0")"
export PORT="${PORT:-8777}"

# Die Health-Antwort wird ausschließlich im Speicher geprüft; ihr Token wird
# weder ausgegeben noch in einer Datei oder URL gespeichert.
python3 - <<'PY'
import http.client
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

try:
    port = int(os.environ['PORT'])
    if not 1 <= port <= 65535:
        raise ValueError
except ValueError:
    sys.exit('PORT muss eine Zahl zwischen 1 und 65535 sein.')


def healthy():
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=0.3)
    try:
        conn.request('GET', '/api/tutor/health')
        response = conn.getresponse()
        data = json.loads(response.read(65537))
        return (response.status == 200
                and response.getheader('Content-Type') == 'application/json'
                and data.get('ok') is True
                and isinstance(data.get('token'), str)
                and re.fullmatch(r'[0-9a-f]{32}', data['token']) is not None
                and data.get('models') == [{'id': 'opus', 'label': 'Gründlich (Opus 5)'},
                                          {'id': 'sonnet', 'label': 'Schnell (Sonnet 5)'}]
                and isinstance(data.get('claude'), dict)
                and type(data['claude'].get('found')) is bool)
    except (OSError, ValueError, AttributeError, http.client.HTTPException):
        return False
    finally:
        conn.close()


def occupied():
    # Zusätzlich zu IPv4 auch einen fremden IPv6-Listener erkennen.
    for address in ('127.0.0.1', '::1'):
        try:
            with socket.create_connection((address, port), timeout=0.3):
                return True
        except OSError:
            pass
    return False

if occupied():
    if not healthy():
        sys.exit(f'Auf Port {port} läuft ein anderer Server (vermutlich der alte statische) – bitte beenden oder PORT setzen')
else:
    workdir = Path.home() / '.academy-tutor'
    if workdir.is_symlink():
        sys.exit('Das Tutor-Arbeitsverzeichnis darf kein Symlink sein.')
    workdir.mkdir(mode=0o700, parents=True, exist_ok=True)
    workdir.chmod(0o700)
    log_path = workdir / 'server.log'
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0)
    try:
        with os.fdopen(os.open(log_path, flags, 0o600), 'ab') as log:
            os.fchmod(log.fileno(), 0o600)
            process = subprocess.Popen([sys.executable, 'scripts/serve.py', '--port', str(port)],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    except OSError:
        sys.exit('Tutor-Server konnte nicht gestartet werden; Arbeitsverzeichnis und Logdatei prüfen.')
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            sys.exit('Tutor-Server konnte nicht starten. Hinweise stehen in ~/.academy-tutor/server.log.')
        if healthy():
            break
        time.sleep(0.1)
    else:
        sys.exit('Tutor-Server ist nach 10 Sekunden nicht bereit. Hinweise stehen in ~/.academy-tutor/server.log.')

print(f'Academy läuft auf http://127.0.0.1:{port}/')
PY
open "http://127.0.0.1:$PORT/"
