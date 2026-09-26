#!/usr/bin/env python3
"""Synthetischer Claude-Code-Ersatz für lokale Tests, ohne Netz und ohne Abo."""
import json
import os
from pathlib import Path
import re
import stat
import sys
import time


def test_options():
    options = {key: os.environ[key] for key in ("FAKE_CLAUDE_MODE", "FAKE_CLAUDE_HOLD_FILE") if key in os.environ}
    # serve.py vererbt ausschließlich seine feste Umgebungs-Positivliste.
    # Der optionale anonyme Testdeskriptor hält echte CLI-Flags und stdin identisch.
    for entry in Path("/dev/fd").iterdir():
        try:
            fd = int(entry.name)
            if fd < 3 or not stat.S_ISREG(os.fstat(fd).st_mode):
                continue
            raw = os.pread(fd, 65536, 0)
            prefix = b"ACADEMY_FAKE_CLAUDE\0"
            if raw.startswith(prefix):
                options.update(json.loads(raw[len(prefix):]))
                os.close(fd)
                break
        except (OSError, ValueError):
            continue
    return options


OPTIONS = {}


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def hold():
    filename = OPTIONS.get("FAKE_CLAUDE_HOLD_FILE")
    deadline = time.monotonic() + 30
    while filename and not Path(filename).exists() and time.monotonic() < deadline:
        time.sleep(0.02)


def result(is_error=False, **extra):
    hold()
    emit({"type": "result", "subtype": "success", "is_error": is_error, **extra})


def delta(text):
    emit({"type": "stream_event", "event": {"type": "content_block_delta",
                                           "delta": {"type": "text_delta", "text": text}}})


def main():
    if "--version" in sys.argv[1:]:
        print("2.1.267 (synthetischer Fake-Claude)")
        return
    global OPTIONS
    OPTIONS = test_options()
    prompt = sys.stdin.read()
    mode = OPTIONS.get("FAKE_CLAUDE_MODE", "ok")
    emit({"type": "system", "subtype": "init", "apiKeySource": "ANTHROPIC_API_KEY" if mode == "api_key" else "none", "tools": []})
    if mode == "api_key":
        result()
        return
    if mode == "rate_limit":
        emit({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": 2000000000}})
        emit({"type": "assistant", "error": "rate_limit"})
        result(True)
        return
    if mode == "auth":
        emit({"type": "assistant", "error": "authentication_failed"})
        result(True)
        return
    if mode == "hang":
        time.sleep(3600)
        return
    if mode == "eof":
        delta("Unvollständige synthetische Antwort.")
        return
    if mode == "stderr_flood":
        sys.stderr.write("x" * (2 * 1024 * 1024))
        sys.stderr.flush()
    match = re.search(r"<aktuelle_frage>(.*?)</aktuelle_frage>", prompt, re.S)
    question = match.group(1) if match else "Synthetische Testfrage"
    answer = f"Du fragst: „{question}“. Dies ist eine synthetische Testantwort. Wir betrachten zuerst ein einfaches Beispiel und prüfen dann die Regel."
    for i in range(6):
        delta(answer[len(answer) * i // 6:len(answer) * (i + 1) // 6])
        time.sleep(0.08)
    # Absichtlich wiederholt: Der Server darf nur text_delta weiterreichen.
    emit({"type": "assistant", "message": {"content": [{"type": "text", "text": answer}]}})
    result(result=answer)


if __name__ == "__main__":
    main()
