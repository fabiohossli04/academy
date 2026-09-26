#!/usr/bin/env python3
"""Lokale Academy mit zustandslosem Claude-Tutor (nur Python-Standardbibliothek)."""
from __future__ import annotations

import argparse
import html
import http.server
import json
import math
import os
from pathlib import Path
import re
import secrets
import selectors
import shutil
import signal
import socket
import stat
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parent.parent
MODELS = [{"id": "opus", "label": "Gründlich (Opus 5)"},
          {"id": "sonnet", "label": "Schnell (Sonnet 5)"}]
MODEL_IDS = {"opus": "claude-opus-5", "sonnet": "claude-sonnet-5"}
EFFORTS = {"opus": "medium", "sonnet": "low"}  # Schnell: ohne Nachdenkpause (gemessen 1,5 s statt 4,3 s bis zum ersten Wort)
ENV_KEYS = ("HOME", "USER", "LOGNAME", "PATH", "LANG", "LC_ALL", "TMPDIR", "SHELL")
MAX_BODY = 64 * 1024
MAX_LINE = 1024 * 1024
HEARTBEAT = 10.0
BODY_REJECTED = object()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def safe_file(root, relative):
    """Auch erlaubte Namen dürfen nicht durch Symlinks aus dem Repo führen."""
    try:
        path = (root / relative).resolve(strict=True)
        path.relative_to(root)
        return path if stat.S_ISREG(path.stat().st_mode) else None
    except (OSError, ValueError, RuntimeError):
        return None


def clips_of(lesson):
    return lesson.get("clips") or [lesson]


class Academy:
    def __init__(self, root):
        self.root = root.resolve()
        self.lock = threading.Lock()
        self.stamp = None
        self.lessons = {}
        self.captions = set()
        self.snapshot()

    def snapshot(self):
        with self.lock:
            path = safe_file(self.root, "data/academy.json")
            if path is None:
                raise ValueError("Academy-Daten fehlen")
            info = path.stat()
            stamp = (info.st_mtime_ns, info.st_size, info.st_ino)
            if stamp != self.stamp:
                data = json.loads(path.read_text(encoding="utf-8"))
                lessons, captions = {}, set()
                for course in data["courses"]:
                    for lesson in course["lessons"]:
                        lessons[f"{course['id']}/{lesson['nr']}"] = (course, lesson)
                        for clip in clips_of(lesson):
                            expected = f"transcripts/{course['id']}/{clip.get('opencastId', '')}.vtt"
                            if (re.fullmatch(r"transcripts/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\.vtt", expected)
                                    and clip.get("captionLocal") in (expected, "/" + expected)):
                                captions.add("/" + expected)
                self.lessons, self.captions, self.stamp = lessons, captions, stamp
            return self.lessons, self.captions


def timestamp(value):
    match = re.fullmatch(r"(?:(\d+):)?(\d{2,}):(\d{2})\.(\d{3})", value)
    if not match:
        raise ValueError("Ungültige VTT-Zeit")
    hours, minutes, seconds, millis = match.groups()
    if int(seconds) >= 60 or (hours is not None and int(minutes) >= 60):
        raise ValueError("Ungültige VTT-Zeit")
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def vtt_cues(text):
    for block in re.split(r"\n[ \t]*\n", text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")):
        lines = block.strip().splitlines()
        if not lines or re.match(r"^(WEBVTT|NOTE|STYLE|REGION)(?:\s|$)", lines[0]):
            continue
        for index, line in enumerate(lines):
            match = re.match(r"^(\S+)\s+-->\s+(\S+)(?:\s.*)?$", line)
            if match:
                try:
                    start, end = map(timestamp, match.groups())
                except ValueError:
                    break
                clean = []
                for raw in lines[index + 1:]:
                    value = html.unescape(re.sub(r"<[^>]*>", "", raw)).strip()
                    if value and (not clean or clean[-1] != value):
                        clean.append(value)
                if end > start and clean:
                    yield start, end, "\n".join(clean)
                break


def clock_text(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{seconds:02d}"


def near_excerpt(cues, position, limit=6000):
    parts, offsets, last = [], [], None
    size = 0
    for start, end, text in cues:
        lines = []
        for line in text.splitlines():
            if line != last:
                lines.append(line)
            last = line
        if lines:
            value = "\n".join(lines)
            offsets.append((start, end, size, len(value)))
            parts.append(value)
            size += len(value) + 1
    joined = "\n".join(parts)
    if len(joined) <= limit:
        return joined
    start, end, offset, length = min(offsets, key=lambda c: max(c[0] - position, position - c[1], 0))
    fraction = min(1, max(0, (position - start) / (end - start)))
    anchor = offset + int(length * fraction)
    left = max(0, min(anchor - limit * 3 // 4, len(joined) - limit))
    return joined[left:left + limit]


def context_for(academy, course, lesson, position):
    lines = [f"Kurs: {course['title']}", f"Kursangaben: {course.get('subtitle', '')}",
             f"Sprache: {course.get('lang', '')}", f"Lektion {lesson['nr']}: {lesson['title']}",
             "Themen: " + ", ".join(lesson.get("topics", []))]
    if course.get("kind") == "external":
        lines.append("Externer Kurs: Es gibt kein eingebettetes Video und keine Videoposition. Kontext nur aus Lektionsthemen.")
        return {"kind": "external", "position": None}, "\n".join(lines)
    clips = clips_of(lesson)
    total = (lesson.get("durationMs") or sum(c.get("durationMs", 0) for c in clips)) / 1000
    p = min(position if position is not None else 0, total)
    display = clock_text(p) if position is not None else None
    lines.append(f"Position: {display or 'nicht angegeben'} von {clock_text(total)}")
    low, high = max(0, p - 240), min(total, p + 30)
    _, allowed = academy.snapshot()
    cues, offset, missing = [], 0.0, False
    for clip in clips:
        duration = clip.get("durationMs", 0) / 1000
        clip_low, clip_high = max(low, offset), min(high, offset + duration)
        if clip_low < clip_high:
            local = clip.get("captionLocal")
            if local:
                route = "/" + local.lstrip("/")
                path = safe_file(academy.root, route[1:]) if route in allowed else None
                found = []
                try:
                    if path:
                        found = [(a + offset, b + offset, text) for a, b, text in
                                 vtt_cues(path.read_text(encoding="utf-8"))
                                 if b > clip_low - offset and a < clip_high - offset]
                except (OSError, UnicodeError):
                    pass
                cues.extend(found)
                missing |= not found
            else:
                missing = True
        offset += duration
    excerpt = near_excerpt(cues, p)
    if excerpt:
        kind = "transcript"
        lines.append("Untertitel-Ausschnitt (automatische Erkennung):\n" + excerpt)
        if missing:
            lines.append("Hinweis: Für Teile dieses Zeitfensters sind keine lesbaren Untertitel verfügbar.")
    elif not any(c.get("captionLocal") for c in clips) and course.get("captions") is not True:
        # academy.json lässt captions:false im bisherigen Build weg.
        kind = "no_captions"
        lines.append("Tafelvorlesung ohne Untertitel – Kontext nur aus Lektionsthemen")
    else:
        kind = "transcript_missing"
        lines.append("Untertitel fehlen, sind nicht lesbar oder enthalten in diesem Zeitfenster keine Cues. Kontext nur aus Lektionsthemen.")
    return {"kind": kind, "position": display}, "\n".join(lines)


def escape_data(value):
    return value.replace("<", "‹").replace(">", "›")


def make_prompt(context, history, question):
    turns = []
    for entry in history:
        tag = "frage" if entry["role"] == "user" else "antwort"
        turns.append(f"<{tag}>{escape_data(entry['text'])}</{tag}>")
    return (f"<kontext>{escape_data(context)}</kontext>\n"
            f"<bisheriges_gespraech>{''.join(turns)}</bisheriges_gespraech>\n"
            f"<aktuelle_frage>{escape_data(question)}</aktuelle_frage>")


def validate_request(data):
    required = {"requestId", "lessonKey", "positionSec", "model", "question", "history"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Die Anfrage muss requestId, lessonKey, positionSec, model, question und history enthalten.")
    rid = data["requestId"]
    if not isinstance(rid, str) or not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", rid):
        raise ValueError("requestId muss eine UUID sein.")
    if not isinstance(data["lessonKey"], str) or not re.fullmatch(r"[a-z0-9_-]+/[1-9][0-9]*", data["lessonKey"]):
        raise ValueError("lessonKey muss die Form kurs/nummer haben.")
    if not isinstance(data["model"], str) or data["model"] not in MODEL_IDS:
        raise ValueError("Bitte opus oder sonnet als Modell wählen.")
    pos = data["positionSec"]
    if pos is not None and (type(pos) not in (int, float) or pos < 0 or not math.isfinite(pos)):
        raise ValueError("positionSec muss endlich und mindestens 0 oder null sein.")
    question = data["question"]
    if not isinstance(question, str) or not 1 <= len(question) <= 4000:
        raise ValueError("Die Frage muss 1 bis 4000 Zeichen enthalten.")
    history = data["history"]
    if not isinstance(history, list) or len(history) > 12:
        raise ValueError("Der Verlauf darf höchstens 12 Einträge enthalten.")
    total = 0
    for entry in history:
        if (not isinstance(entry, dict) or set(entry) != {"role", "text"}
                or entry["role"] not in ("user", "assistant")
                or not isinstance(entry["text"], str) or len(entry["text"]) > 8000):
            raise ValueError("Ungültiger Verlauf: role muss user/assistant sein, text höchstens 8000 Zeichen.")
        total += len(entry["text"])
    if total > 40000:
        raise ValueError("Der Verlauf darf insgesamt höchstens 40000 Zeichen enthalten.")
    # JSON kann isolierte UTF-16-Surrogate enthalten; UTF-8 für stdin muss gültig sein.
    for value in [question, *(entry["text"] for entry in history)]:
        value.encode("utf-8")
    return str(uuid.UUID(rid))


def limit_env(name, default):
    value = float(os.environ.get(name, default))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Ungültiges Zeitlimit: {name}")
    return value


def child_environment():
    return {key: os.environ[key] for key in ENV_KEYS if key in os.environ}


def claude_argv(binary, model, system_prompt):
    return [binary, "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
            "--safe-mode", "--disable-slash-commands", "--setting-sources", "project", "--strict-mcp-config",
            "--tools", "", "--permission-mode", "dontAsk", "--no-session-persistence", "--model",
            MODEL_IDS[model], "--effort", EFFORTS[model], "--system-prompt", system_prompt]


def group_alive(proc):
    proc.poll()  # Reap a terminated leader before checking the group.
    try:
        os.killpg(proc.pid, 0)
        return True
    except ProcessLookupError:
        return False


def stop_process(proc):
    """SIGINT → 3 s → SIGTERM → 2 s → SIGKILL; auch Nachkommen aufräumen."""
    for sig, grace in ((signal.SIGINT, 3), (signal.SIGTERM, 2), (signal.SIGKILL, 0)):
        if not group_alive(proc):
            break
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline and group_alive(proc):
            time.sleep(0.03)
    proc.wait()


class TutorFailure(Exception):
    def __init__(self, kind, message, resets_at=None):
        self.payload = {"kind": kind, "message": message}
        if resets_at is not None:
            self.payload["resetsAt"] = resets_at
        super().__init__(kind)


class ClientGone(Exception):
    pass


def failure(kind, resets_at=None):
    messages = {
        "auth": "Claude läuft nicht über dein Abo oder ist nicht angemeldet. Bitte im Terminal `claude` starten und /login ausführen.",
        "rate_limit": "Dein Claude-Nutzungslimit ist erreicht. Bitte versuche es nach der Freigabe erneut.",
        "timeout": "Claude hat zu lange nicht geantwortet. Bitte versuche es erneut.",
        "cancelled": "Die Anfrage wurde abgebrochen, weil der Tutor-Server beendet wird.",
        "claude_missing": "Claude Code wurde nicht gefunden. Bitte installieren oder ACADEMY_CLAUDE_BIN setzen.",
        "internal": "Keine vollständige Antwort erhalten. Bitte versuche es erneut.",
    }
    return TutorFailure(kind, messages[kind], resets_at)


class Run:
    def __init__(self, app):
        self.app = app
        self.proc = None
        self.stop_lock = threading.Lock()
        self.stderr = bytearray()
        self.workers = []
        self.cancel = threading.Event()

    def stop(self):
        self.cancel.set()
        with self.stop_lock:
            if self.proc is not None:
                stop_process(self.proc)

    def drain_stderr(self):
        try:
            while chunk := self.proc.stderr.read(8192):
                self.stderr.extend(chunk)
                del self.stderr[:-65536]
        except (OSError, ValueError):
            pass

    def write_prompt(self, prompt):
        try:
            view = memoryview(prompt.encode("utf-8"))
            while view:
                count = self.proc.stdin.write(view)
                if not count:
                    break
                view = view[count:]
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            self.proc.stdin.close()

    def execute(self, model, prompt, emit, ping):
        try:
            return self._execute(model, prompt, emit, ping)
        finally:
            self.stop()
            for worker in self.workers:
                worker.join(timeout=1)
            if self.proc:
                for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                    pipe.close()

    def _execute(self, model, prompt, emit, ping):
        app = self.app
        if not app.found:
            raise failure("claude_missing")
        started = time.monotonic()
        with self.stop_lock:
            if self.cancel.is_set() or app.stopping.is_set():
                raise failure("cancelled")
            try:
                # Teststeuerung über einen anonymen Deskriptor nur an unseren Fake:
                # Auch dort bleiben argv, Prompt und die Umgebungs-Positivliste exakt.
                control = tempfile.TemporaryFile(dir=app.workdir) if app.fake_options is not None else None
                try:
                    if control:
                        control.write(b"ACADEMY_FAKE_CLAUDE\0" + json_bytes(app.fake_options))
                        control.flush()
                    self.proc = subprocess.Popen(claude_argv(app.binary, model, app.system_prompt),
                                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                 cwd=app.workdir, env=app.env, start_new_session=True, bufsize=0,
                                                 pass_fds=(control.fileno(),) if control else ())
                finally:
                    if control:
                        control.close()
            except FileNotFoundError:
                raise failure("claude_missing") from None
            except OSError:
                raise failure("internal") from None
        for target, args in ((self.drain_stderr, ()), (self.write_prompt, (prompt,))):
            worker = threading.Thread(target=target, args=args, daemon=True)
            self.workers.append(worker)
            worker.start()
        last_line, next_ping = started, started + HEARTBEAT
        buffer, eof, init, result = bytearray(), False, False, None
        error_kind, resets = None, None
        with selectors.DefaultSelector() as selector:
            selector.register(self.proc.stdout, selectors.EVENT_READ)
            while not eof or self.proc.poll() is None:
                now = time.monotonic()
                if self.cancel.is_set() or app.stopping.is_set():
                    raise failure("cancelled")
                if now - started >= app.total_timeout or now - last_line >= app.idle_timeout:
                    raise failure("timeout")
                if now >= next_ping:
                    ping()
                    next_ping = now + HEARTBEAT
                ready = selector.select(min(0.1, max(0, next_ping - now)))
                if not ready:
                    continue
                chunk = os.read(self.proc.stdout.fileno(), 65536)
                if chunk:
                    buffer.extend(chunk)
                else:
                    eof = True
                    selector.unregister(self.proc.stdout)
                    if buffer:
                        buffer.extend(b"\n")
                if len(buffer) > MAX_LINE:
                    raise failure("internal")
                while b"\n" in buffer:
                    raw, _, rest = buffer.partition(b"\n")
                    buffer = bytearray(rest)
                    last_line = time.monotonic()
                    if not raw.strip():
                        continue
                    try:
                        record = json.loads(raw)
                    except (ValueError, UnicodeError):
                        raise failure("internal") from None
                    if not isinstance(record, dict):
                        raise failure("internal")
                    typ, subtype = record.get("type"), record.get("subtype")
                    if typ == "system" and subtype == "init":
                        if record.get("apiKeySource") != "none":
                            raise failure("auth")
                        if record.get("tools") != []:
                            raise TutorFailure("internal", "Claude hat unerwartet Werkzeuge aktiviert. Die Anfrage wurde sicher abgebrochen.")
                        init = True
                    elif typ == "system" and subtype == "api_retry":
                        emit("status", {"kind": "retry", "message": "Claude versucht die Verbindung erneut."})
                    elif typ == "rate_limit_event":
                        info = record.get("rate_limit_info") or {}
                        if not isinstance(info, dict):
                            raise failure("internal")
                        if info.get("status") == "rejected":
                            error_kind = "rate_limit"
                            reset = info.get("resetsAt")
                            if (isinstance(reset, str) and len(reset) <= 100) or (type(reset) in (int, float) and math.isfinite(reset)):
                                resets = reset
                        elif info.get("status") == "allowed_warning":
                            emit("status", {"kind": "limit_warning", "message": "Du näherst dich deinem Claude-Nutzungslimit."})
                    elif typ == "stream_event":
                        event = record.get("event") or {}
                        delta = event.get("delta") or {}
                        if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                            if not init or result is not None:
                                raise failure("internal")
                            value = delta.get("text")
                            if not isinstance(value, str):
                                raise failure("internal")
                            emit("delta", {"text": value})
                    elif typ == "result":
                        if result is not None:
                            raise failure("internal")
                        result = record
                    # Nur klassifizieren, nie fremde Fehlertexte an Browser/Logs geben.
                    if typ in ("assistant", "result", "system"):
                        fields = {k: record.get(k) for k in ("error", "errors", "api_error_status")}
                        if typ == "result" and record.get("is_error") is True:
                            fields["result"] = record.get("result")
                        diagnostic = json.dumps(fields).lower()
                        if any(code in diagnostic for code in ("authentication_failed", "oauth_org_not_allowed", "not logged in")) or record.get("api_error_status") in (401, 403):
                            error_kind = "auth"
                        elif "rate_limit" in diagnostic or record.get("api_error_status") == 429:
                            if error_kind != "auth":
                                error_kind = "rate_limit"
        if self.cancel.is_set() or app.stopping.is_set():
            raise failure("cancelled")
        if result is None:
            raise failure("internal")
        if result.get("is_error") is not False:
            if error_kind is None and b"not logged in" in bytes(self.stderr).lower():
                error_kind = "auth"
            raise failure(error_kind or "internal", resets if error_kind == "rate_limit" else None)
        if not init or self.proc.wait() != 0:
            raise failure("internal")


class App:
    def __init__(self, root):
        self.root = root.resolve()
        self.academy = Academy(self.root)
        self.system_prompt = (self.root / "scripts/tutor_prompt.md").read_text(encoding="utf-8")
        self.token = secrets.token_hex(16)
        self.workdir = Path.home() / ".academy-tutor"
        if self.workdir.is_symlink():
            raise ValueError("Das Tutor-Arbeitsverzeichnis darf kein Symlink sein.")
        self.workdir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.workdir.chmod(0o700)
        binary = os.environ.get("ACADEMY_CLAUDE_BIN") or shutil.which("claude") or str(Path.home() / ".local/bin/claude")
        self.binary = str(Path(binary).expanduser().resolve())
        self.found = Path(self.binary).is_file() and os.access(self.binary, os.X_OK)
        self.env = child_environment()
        self.fake_options = None
        if Path(self.binary) == (self.root / "scripts/fake_claude.py").resolve():
            self.fake_options = {key: os.environ[key] for key in ("FAKE_CLAUDE_MODE", "FAKE_CLAUDE_HOLD_FILE")
                                 if key in os.environ}
        self.total_timeout = limit_env("ACADEMY_TUTOR_TOTAL_TIMEOUT", 300)
        self.idle_timeout = limit_env("ACADEMY_TUTOR_IDLE_TIMEOUT", 120)
        self.body_timeout = limit_env("ACADEMY_TUTOR_BODY_TIMEOUT", 10)
        self.lock = threading.Lock()
        self.active = {}
        self.stopping = threading.Event()
        self.version = self.get_version()

    def get_version(self):
        if not self.found:
            return None
        proc = None
        try:
            proc = subprocess.Popen([self.binary, "--version"], cwd=self.workdir, env=self.env,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
            output, _ = proc.communicate(timeout=3)
            if proc.returncode == 0:
                return "".join(c for c in output.decode("utf-8", "replace").strip() if c.isprintable())[:200] or None
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            if proc:
                stop_process(proc)
                proc.stdout.close()
        return None

    def reserve(self, key):
        with self.lock:
            if key in self.active:
                return None, 409
            if self.stopping.is_set() or len(self.active) >= 2:
                return None, 429
            run = Run(self)
            self.active[key] = run
            return run, None

    def release(self, key):
        with self.lock:
            self.active.pop(key, None)

    def stop_all(self):
        self.stopping.set()
        with self.lock:
            runs = list(self.active.values())
        for run in runs:
            run.cancel.set()
        for run in runs:
            run.stop()


class TutorServer(http.server.ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, port, app):
        self.app = app
        super().__init__(("127.0.0.1", port), Handler)

    def handle_error(self, request, client_address):
        # Keine Request-Inhalte, Header, Prompts oder stderr in Logs.
        pass


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AcademyTutor"
    sys_version = ""

    def log_message(self, *args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(self.server.app.body_timeout)

    def parse_request(self):
        if not super().parse_request():
            return False
        self.close_connection = True
        hosts = self.headers.get_all("Host", [])
        port = self.server.server_port
        if len(hosts) != 1 or hosts[0] not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.problem(403, "forbidden", "Dieser Host ist nicht erlaubt.")
            return False
        return True

    def handle_expect_100(self):
        # Kein ungeprüftes 100 Continue vor Host-/Origin-/Längenprüfung.
        return True

    def send_error(self, code, message=None, explain=None):
        self.problem(code, "bad_request", "Ungültige HTTP-Anfrage.")

    def headers_for(self, status, content_type, length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def reply(self, status, value):
        payload = json_bytes(value)
        self.headers_for(status, "application/json", len(payload))
        self.wfile.write(payload)

    def problem(self, status, kind, message):
        self.reply(status, {"error": {"kind": kind, "message": message}})

    def route(self):
        if not self.path.startswith("/") or self.path.startswith("//"):
            return ""
        return urlsplit(self.path).path

    def do_GET(self):
        route, app = self.route(), self.server.app
        if route == "/api/tutor/health":
            self.reply(200, {"ok": True, "token": app.token, "models": MODELS,
                             "claude": {"found": app.found, "version": app.version}})
            return
        types = {"/": "text/html; charset=utf-8", "/index.html": "text/html; charset=utf-8",
                 "/app.js": "text/javascript; charset=utf-8", "/styles.css": "text/css; charset=utf-8",
                 "/data/academy.json": "application/json"}
        mime = types.get(route)
        if re.fullmatch(r"/data/quiz/[a-z0-9_-]+\.json", route):
            mime = "application/json"
        if route.startswith("/transcripts/"):
            try:
                _, allowed = app.academy.snapshot()
            except (OSError, ValueError, KeyError, TypeError):
                self.problem(500, "internal", "Die Kursdaten können nicht gelesen werden.")
                return
            if route in allowed:
                mime = "text/vtt; charset=utf-8"
        path = safe_file(app.root, "index.html" if route == "/" else route[1:]) if mime else None
        if path is None:
            self.problem(404, "not_found", "Datei nicht gefunden.")
            return
        try:
            with path.open("rb") as source:
                self.headers_for(200, mime, os.fstat(source.fileno()).st_size)
                shutil.copyfileobj(source, self.wfile)
        except OSError:
            self.close_connection = True

    def read_body(self):
        if self.headers.get_all("Transfer-Encoding"):
            raise ValueError("Transfer-Encoding wird nicht unterstützt.")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]+", lengths[0]):
            raise ValueError("Content-Length fehlt oder ist ungültig.")
        if len(lengths[0]) > 10 or int(lengths[0]) > MAX_BODY:
            self.problem(413, "bad_request", "Die Anfrage darf höchstens 64 KiB groß sein.")
            return BODY_REJECTED
        length = int(lengths[0])
        if self.headers.get("Expect", "").lower() == "100-continue":
            self.send_response_only(100)
            self.end_headers()
        deadline, body = time.monotonic() + self.server.app.body_timeout, bytearray()
        try:
            while len(body) < length:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("Zeitlimit beim Lesen der Anfrage überschritten.")
                self.connection.settimeout(remaining)
                chunk = self.rfile.read1(length - len(body))
                if not chunk:
                    raise ValueError("Die Anfrage ist unvollständig.")
                body.extend(chunk)
        except (TimeoutError, OSError):
            raise ValueError("Zeitlimit beim Lesen der Anfrage überschritten.") from None
        finally:
            self.connection.settimeout(5)
        def invalid_constant(value):
            raise ValueError("JSON darf keine nicht endlichen Zahlen enthalten.")
        return json.loads(body.decode("utf-8"), parse_constant=invalid_constant)

    def emit(self, name, data):
        self.stream_write(b"event: " + name.encode("ascii") + b"\ndata: " + json_bytes(data) + b"\n\n")

    def ping(self):
        self.stream_write(b": ping\n\n")

    def stream_write(self, data):
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except OSError:
            raise ClientGone from None

    def do_POST(self):
        app = self.server.app
        if self.route() != "/api/tutor/chat":
            self.problem(404, "not_found", "Endpunkt nicht gefunden.")
            return
        port = self.server.server_port
        origins = self.headers.get_all("Origin", [])
        tokens = self.headers.get_all("X-Academy-Tutor", [])
        if (len(origins) != 1 or origins[0] not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")
                or len(tokens) != 1 or not secrets.compare_digest(tokens[0].encode("utf-8"), app.token.encode("ascii"))):
            self.problem(403, "forbidden", "Ursprung oder Tutor-Token ist ungültig.")
            return
        content_types = self.headers.get_all("Content-Type", [])
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
            self.problem(400, "bad_request", "Content-Type muss application/json sein.")
            return
        try:
            data = self.read_body()
            if data is BODY_REJECTED:
                return
            key = validate_request(data)
        except (ValueError, UnicodeError, OverflowError, RecursionError):
            self.problem(400, "bad_request", "Ungültige Anfrage: Bitte JSON, Pflichtfelder und Größenbegrenzungen prüfen.")
            return
        try:
            lessons, _ = app.academy.snapshot()
            pair = lessons.get(data["lessonKey"])
            if pair is None:
                self.problem(404, "not_found", "Diese Lektion ist nicht bekannt.")
                return
            context, text = context_for(app.academy, *pair, data["positionSec"])
            prompt = make_prompt(text, data["history"], data["question"])
        except (OSError, ValueError, KeyError, TypeError):
            self.problem(500, "internal", "Der Lektionskontext kann nicht gelesen werden.")
            return
        run, status = app.reserve(key)
        if status:
            self.problem(status, "busy", "Diese Anfrage läuft bereits." if status == 409 else "Es laufen bereits zwei Tutor-Anfragen. Bitte kurz warten.")
            return
        try:
            self.connection.settimeout(5)
            self.headers_for(200, "text/event-stream; charset=utf-8")
            self.emit("start", {"requestId": data["requestId"], "model": data["model"], "context": context})
            try:
                run.execute(data["model"], prompt, self.emit, self.ping)
            except TutorFailure as exc:
                self.emit("error", exc.payload)
            except ClientGone:
                raise
            except Exception:
                self.emit("error", failure("internal").payload)
            else:
                self.emit("done", {"requestId": data["requestId"]})
        except (ClientGone, OSError):
            pass
        finally:
            run.stop()
            app.release(key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=os.environ.get("PORT", "8777"))
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port muss zwischen 0 und 65535 liegen.")
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    try:
        app = App(ROOT)
        server = TutorServer(args.port, app)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "Tutor-Server konnte nicht starten. Kursdaten, Systemprompt, Port und Arbeitsverzeichnis prüfen.\n")
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1})
    thread.start()
    print(f"Academy-Tutor bereit auf http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        stopped.wait()
    finally:
        app.stop_all()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
