#!/usr/bin/env python3
"""VinAI terminal client: enqueue prompts and read saved results."""
import base64
import json
import os
import platform
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import requests

OWNER = "Alvino33"
REPO = "AI-Project"
BRANCH = "feature/gpt-oss-20b-terminal"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

MODELS = {
    "gpt-oss-20b": "GPT-OSS 20B (MXFP4)",
    "qwen-3b": "Qwen2.5-Coder 3B (Q4_K_M)",
}
REASONING_LEVELS = ("low", "medium", "high")


def api(method, path, **kwargs):
    response = requests.request(
        method, API + path, headers=HEADERS, timeout=90, **kwargs
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"GitHub API {response.status_code}: {response.text[:400]}"
        )
    return response


def get_file(path):
    response = requests.get(
        API + f"/contents/{quote(path, safe='/')}",
        headers=HEADERS,
        params={"ref": BRANCH},
        timeout=60,
    )
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise RuntimeError(f"GitHub API {response.status_code}: {response.text[:300]}")
    data = response.json()
    raw = base64.b64decode(data["content"])
    return json.loads(raw.decode("utf-8")), data["sha"]


def put_file(path, content, message, sha=None):
    payload = {
        "message": message,
        "content": base64.b64encode(
            json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    api("PUT", f"/contents/{quote(path, safe='/')}", json=payload)


def enqueue(prompt, model, reasoning):
    request_id = uuid.uuid4().hex
    request = {
        "request_id": request_id,
        "prompt": prompt,
        "model": model,
        "reasoning": reasoning,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    put_file(
        f"requests/{request_id}.json",
        request,
        f"VinAI: enqueue {request_id}",
    )
    return request_id


def wait_result(request_id):
    print(f"Request masuk antrean: {request_id}")
    print("Menunggu worker. Pastikan workflow VinAI Queue Worker sedang aktif.")
    while True:
        result_file = get_file(f"results/{request_id}.json")
        if result_file:
            result, _ = result_file
            print("\nVinAI:")
            print(result.get("answer", "(hasil kosong)"))
            if result.get("status") != "completed":
                print(f"Status: {result.get('status', 'unknown')}")
            return
        time.sleep(12)


def show_help():
    print("""
Perintah VinAI:
  /help                  Tampilkan bantuan
  /exit                  Keluar
  /clear                 Bersihkan layar terminal
  /model                 Lihat model aktif
  /model gpt-oss-20b     Pilih GPT-OSS 20B
  /model qwen-3b         Pilih Qwen2.5-Coder 3B
  /reasoning             Lihat tingkat reasoning
  /reasoning low         Reasoning rendah
  /reasoning medium      Reasoning sedang
  /reasoning high        Reasoning tinggi
  /status                Lihat konfigurasi aktif

Prompt disimpan di requests/ dan jawaban di results/.
Satu workflow worker dapat memproses banyak prompt selama sesi aktif.
Model dipilih saat worker dijalankan; samakan pilihan /model dengan model worker.
""")


def main():
    model = "gpt-oss-20b"
    reasoning = "medium"

    print("VinAI Terminal — ketik /help untuk daftar perintah.")
    if not TOKEN:
        print("GITHUB_TOKEN belum disetel. Butuh izin Contents: Read and write.")
        return

    while True:
        try:
            prompt = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari VinAI.")
            break

        if not prompt:
            continue
        if prompt == "/exit":
            print("Keluar dari VinAI.")
            break
        if prompt == "/help":
            show_help()
            continue
        if prompt == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue
        if prompt == "/model":
            print(f"Model aktif di terminal: {MODELS[model]}")
            continue
        if prompt.startswith("/model "):
            choice = prompt.split(maxsplit=1)[1].strip().lower()
            if choice in MODELS:
                model = choice
                print(f"Model terminal diubah ke: {MODELS[model]}")
                print("Pastikan worker Actions dijalankan dengan model yang sama.")
            else:
                print("Pilihan: " + ", ".join(MODELS))
            continue
        if prompt == "/reasoning":
            print(f"Reasoning aktif: {reasoning}")
            continue
        if prompt.startswith("/reasoning "):
            choice = prompt.split(maxsplit=1)[1].strip().lower()
            if choice in REASONING_LEVELS:
                reasoning = choice
                print(f"Reasoning diubah ke: {reasoning}")
            else:
                print("Pilihan: low, medium, high")
            continue
        if prompt == "/status":
            print(f"Model     : {MODELS[model]}")
            print(f"Reasoning : {reasoning}")
            print(f"Branch    : {BRANCH}")
            print(f"Client    : Python {platform.python_version()}")
            continue

        try:
            request_id = enqueue(prompt, model, reasoning)
            wait_result(request_id)
        except requests.RequestException as exc:
            print(f"Koneksi gagal: {exc}")
        except (RuntimeError, ValueError, KeyError) as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
