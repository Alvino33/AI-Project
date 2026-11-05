#!/usr/bin/env python3
"""Persistent VinAI queue worker. Git is used for queue/result sync."""
import json
import os
import subprocess
import time
from pathlib import Path

import requests

BRANCH = os.environ.get("QUEUE_BRANCH", "feature/gpt-oss-20b-terminal")
ACTIVE_MODEL = os.environ.get("MODEL", "gpt-oss-20b")
REASONING = os.environ.get("REASONING", "medium")
MODEL_URL = "http://127.0.0.1:8080/v1/chat/completions"
ROOT = Path(__file__).resolve().parent
QUEUE_DIR = ROOT / "requests"
RESULT_DIR = ROOT / "results"
STARTED = time.monotonic()
MAX_SECONDS = 320 * 60
SYSTEM_PROMPT = (
    "You are VinAI, a helpful AI assistant. Always answer in Indonesian "
    "unless the user asks for another language. Be accurate, clear, and concise."
)


def git(*args, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def refresh_branch():
    git("fetch", "origin", BRANCH)
    git("reset", "--hard", f"origin/{BRANCH}")


def wait_for_model():
    print("Menunggu llama-server siap...")
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        try:
            response = requests.get("http://127.0.0.1:8080/health", timeout=5)
            if response.ok:
                print(f"Model server siap: {ACTIVE_MODEL}")
                return
        except requests.RequestException:
            pass
        time.sleep(5)
    raise RuntimeError("llama-server tidak siap dalam 15 menit.")


def infer(request):
    request_id = request["request_id"]
    requested_model = request.get("model", ACTIVE_MODEL)
    if requested_model != ACTIVE_MODEL:
        return {
            "request_id": request_id,
            "status": "error",
            "answer": (
                f"Worker sedang memakai {ACTIVE_MODEL}; request meminta "
                f"{requested_model}. Samakan model terminal dengan model worker."
            ),
        }

    payload = {
        "model": ACTIVE_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request["prompt"]},
        ],
        "temperature": 1.0,
        "max_tokens": 512,
    }
    if ACTIVE_MODEL == "gpt-oss-20b":
        payload["chat_template_kwargs"] = {
            "reasoning_effort": request.get("reasoning", REASONING)
        }

    response = requests.post(MODEL_URL, json=payload, timeout=2400)
    response.raise_for_status()
    data = response.json()
    return {
        "request_id": request_id,
        "status": "completed",
        "model": ACTIVE_MODEL,
        "reasoning": request.get("reasoning", REASONING),
        "answer": data["choices"][0]["message"]["content"],
        "created_at": request.get("created_at"),
    }


def save_result(request_id, result):
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULT_DIR / f"{request_id}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git("config", "user.name", "VinAI Queue Worker")
    git("config", "user.email", "vinai-worker@users.noreply.github.com")
    git("add", str(path.relative_to(ROOT)))
    git("commit", "-m", f"VinAI: save result {request_id}")

    # Requests may be added through the GitHub API while inference is running.
    # Rebase the result commit onto those newer queue commits before pushing.
    for attempt in range(4):
        pushed = git("push", "origin", f"HEAD:{BRANCH}", check=False)
        if pushed.returncode == 0:
            return
        git("fetch", "origin", BRANCH)
        rebased = git("rebase", f"origin/{BRANCH}", check=False)
        if rebased.returncode != 0:
            git("rebase", "--abort", check=False)
            refresh_branch()
            raise RuntimeError("Rebase hasil gagal; request tetap ada di antrean.")
    raise RuntimeError("Push hasil gagal setelah beberapa percobaan.")


def load_pending():
    items = []
    if not QUEUE_DIR.exists():
        return items
    for path in QUEUE_DIR.glob("*.json"):
        request_id = path.stem
        result_path = RESULT_DIR / f"{request_id}.json"
        if result_path.exists():
            continue
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            request["_queue_path"] = path
            items.append(request)
        except Exception as exc:
            items.append({
                "request_id": request_id,
                "prompt": "",
                "_error": f"File request tidak valid: {exc}",
            })
    items.sort(key=lambda item: item.get("created_at", ""))
    return items


def main():
    wait_for_model()
    print(f"VinAI queue worker aktif | model: {ACTIVE_MODEL}")
    print("Antrean dipantau tiap 10 detik; hasil disimpan ke results/.")
    while time.monotonic() - STARTED < MAX_SECONDS:
        try:
            refresh_branch()
            pending = load_pending()
            if not pending:
                time.sleep(10)
                continue

            for request in pending:
                if time.monotonic() - STARTED >= MAX_SECONDS - 180:
                    break
                request_id = request.get("request_id") or request.get("_queue_path").stem
                if request.get("_error"):
                    result = {
                        "request_id": request_id,
                        "status": "error",
                        "answer": request["_error"],
                    }
                elif not isinstance(request.get("prompt"), str) or not request["prompt"].strip():
                    result = {
                        "request_id": request_id,
                        "status": "error",
                        "answer": "Prompt kosong atau format request tidak valid.",
                    }
                else:
                    print(f"Memproses request {request_id}")
                    try:
                        result = infer(request)
                    except Exception as exc:
                        result = {
                            "request_id": request_id,
                            "status": "error",
                            "answer": f"Inference gagal: {type(exc).__name__}: {str(exc)[:500]}",
                        }
                save_result(request_id, result)
                print(f"Request {request_id}: {result['status']}")

        except Exception as exc:
            print(f"Worker error: {type(exc).__name__}: {exc}")
            time.sleep(15)

    print("Batas sesi worker tercapai. Jalankan workflow lagi untuk melanjutkan antrean.")


if __name__ == "__main__":
    main()
