#!/usr/bin/env python3
"""VinAI terminal client: sends prompts to GitHub Actions and prints the model response."""
import io
import os
import sys
import time
import zipfile
from datetime import datetime, timezone

import requests

OWNER = "Alvino33"
REPO = "AI-Project"
WORKFLOW = "ai.yml"
BRANCH = "main"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def api(method, path, **kwargs):
    response = requests.request(method, API + path, headers=HEADERS, timeout=60, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"GitHub API {response.status_code}: {response.text[:500]}")
    return response


def ask(prompt):
    if not TOKEN:
        print("GITHUB_TOKEN belum disetel. Buat token dengan izin Actions: read/write untuk repo ini.")
        return
    started = datetime.now(timezone.utc)
    print("Mengirim pertanyaan ke GitHub Actions...")
    api("POST", f"/actions/workflows/{WORKFLOW}/dispatches",
        json={"ref": BRANCH, "inputs": {"prompt": prompt}})
    print("Runner sedang disiapkan. Ini bisa memerlukan beberapa menit...")

    run = None
    deadline = time.time() + 1800
    while time.time() < deadline:
        runs = api("GET", f"/actions/workflows/{WORKFLOW}/runs",
                   params={"event": "workflow_dispatch", "per_page": 10}).json()["workflow_runs"]
        candidates = [
            item for item in runs
            if datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")) >= started
        ]
        if candidates:
            run = candidates[0]
            if run["status"] == "completed":
                break
        time.sleep(8)

    if not run:
        print("Belum menemukan run. Cek tab Actions di GitHub.")
        return
    if run["status"] != "completed":
        print("Waktu tunggu habis. Cek tab Actions untuk status run.")
        return
    if run["conclusion"] != "success":
        print(f"Workflow gagal ({run['conclusion']}). Buka: {run['html_url']}")
        return

    artifacts = api("GET", f"/actions/runs/{run['id']}/artifacts").json()["artifacts"]
    artifact = next((a for a in artifacts if a["name"] == f"vinai-response-{run['id']}"), None)
    if not artifact:
        print("Artifact jawaban tidak ditemukan.")
        return
    archive = api("GET", f"/actions/artifacts/{artifact['id']}/zip")
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        answer = bundle.read("response.txt").decode("utf-8", errors="replace").strip()
    print("\nVinAI:")
    print(answer or "(Model tidak menghasilkan teks.)")


def main():
    print("VinAI CLI — ketik /help untuk bantuan, /exit untuk keluar.")
    while True:
        try:
            prompt = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            break
        if not prompt:
            continue
        if prompt == "/exit":
            break
        if prompt == "/help":
            print("Masukkan pertanyaan atau instruksi. Setiap pesan menjalankan satu job GitHub Actions.")
            print("Catatan: prototipe ini belum menyimpan riwayat percakapan.")
            continue
        try:
            ask(prompt)
        except requests.RequestException as exc:
            print(f"Koneksi gagal: {exc}")
        except Exception as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
