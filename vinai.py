#!/usr/bin/env python3
"""VinAI terminal client for GitHub Actions-hosted local inference."""
import io
import os
import platform
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone

import requests

OWNER = "Alvino33"
REPO = "AI-Project"
WORKFLOW = "ai.yml"
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
SYSTEM_PROMPT = (
    "You are VinAI, a helpful AI assistant. Always answer in Indonesian "
    "unless the user asks for another language. Be accurate, clear, and concise."
)


def api(method, path, **kwargs):
    response = requests.request(
        method, API + path, headers=HEADERS, timeout=120, **kwargs
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"GitHub API {response.status_code}: {response.text[:400]}"
        )
    return response


def get_run(request_id, started):
    deadline = time.time() + 2700
    expected_name = f"VinAI request {request_id}"
    while time.time() < deadline:
        data = api(
            "GET",
            f"/actions/workflows/{WORKFLOW}/runs",
            params={"event": "workflow_dispatch", "branch": BRANCH, "per_page": 30},
        ).json()
        for item in data.get("workflow_runs", []):
            if item.get("name") == expected_name:
                return item
        time.sleep(8)
    return None


def read_answer_from_logs(run_id, request_id):
    # GitHub returns a ZIP of job logs. Keep it in memory; no artifact or file download.
    archive = api("GET", f"/actions/runs/{run_id}/logs")
    begin = f"VINAI_RESULT_BEGIN:{request_id}"
    end = f"VINAI_RESULT_END:{request_id}"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        for name in bundle.namelist():
            if not name.endswith(".txt"):
                continue
            content = bundle.read(name).decode("utf-8", errors="replace")
            start_at = content.find(begin)
            if start_at == -1:
                continue
            start_at = content.find("\n", start_at)
            if start_at == -1:
                continue
            finish_at = content.find(end, start_at)
            if finish_at == -1:
                continue
            return content[start_at + 1:finish_at].strip()
    return None


def ask(prompt, model, reasoning):
    if not TOKEN:
        print("GITHUB_TOKEN belum disetel. Token perlu izin Actions: Read and write.")
        return

    request_id = uuid.uuid4().hex
    print(f"\nMengirim ke {MODELS[model]} | reasoning: {reasoning}")
    print("Menunggu runner GitHub Actions... (bisa beberapa menit)")
    started = datetime.now(timezone.utc)

    api(
        "POST",
        f"/actions/workflows/{WORKFLOW}/dispatches",
        json={
            "ref": BRANCH,
            "inputs": {
                "prompt": prompt,
                "request_id": request_id,
                "model": model,
                "reasoning": reasoning,
            },
        },
    )

    run = get_run(request_id, started)
    if not run:
        print("Run tidak ditemukan atau waktu tunggu habis. Cek tab Actions.")
        return

    print(f"Workflow: {run.get('html_url', '(URL tidak tersedia)')}")
    while run.get("status") != "completed":
        time.sleep(8)
        run = api("GET", f"/actions/runs/{run['id']}").json()

    answer = read_answer_from_logs(run["id"], request_id)
    if answer:
        print("\nVinAI:")
        print(answer)
    else:
        print("\nJawaban tidak ditemukan di log. Periksa log workflow untuk detail.")
    if run.get("conclusion") != "success":
        print(f"Workflow berakhir dengan status: {run.get('conclusion')}")


def show_help():
    print("""
Perintah VinAI:
  /help                  Tampilkan bantuan
  /exit                  Keluar
  /clear                 Bersihkan layar terminal
  /model                 Lihat model aktif
  /model gpt-oss-20b     Gunakan GPT-OSS 20B (eksperimental di runner standar)
  /model qwen-3b         Gunakan Qwen2.5-Coder 3B
  /reasoning             Lihat tingkat reasoning
  /reasoning low         Reasoning rendah
  /reasoning medium      Reasoning sedang
  /reasoning high        Reasoning tinggi
  /status                Lihat konfigurasi aktif

Setiap pesan menjalankan satu workflow baru. Riwayat chat belum disimpan.
Jawaban dibaca langsung dari log workflow; tidak ada artifact response yang diunduh.
""")


def main():
    model = "gpt-oss-20b"
    reasoning = "medium"

    print("VinAI Terminal — ketik /help untuk daftar perintah.")
    if not TOKEN:
        print("Peringatan: GITHUB_TOKEN belum disetel.")

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
            print(f"Model aktif: {MODELS[model]}")
            continue
        if prompt.startswith("/model "):
            choice = prompt.split(maxsplit=1)[1].strip().lower()
            if choice in MODELS:
                model = choice
                print(f"Model diubah ke: {MODELS[model]}")
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
            ask(prompt, model, reasoning)
        except requests.RequestException as exc:
            print(f"Koneksi gagal: {exc}")
        except (RuntimeError, zipfile.BadZipFile) as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
