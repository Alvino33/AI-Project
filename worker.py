#!/usr/bin/env python3
"""Long-running VinAI queue worker for GitHub Actions."""
import base64
import json
import os
import time
from urllib.parse import quote

import requests

TOKEN = os.environ["GITHUB_TOKEN"]
REPOSITORY = os.environ["GITHUB_REPOSITORY"]
BRANCH = os.environ.get("QUEUE_BRANCH", "feature/gpt-oss-20b-terminal")
MODEL_URL = "http://127.0.0.1:8080/v1/chat/completions"
API = f"https://api.github.com/repos/{REPOSITORY}"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}
SYSTEM_PROMPT = (
    "You are VinAI, a helpful AI assistant. Always answer in Indonesian "
    "unless the user asks for another language. Be accurate, clear, and concise."
)
STARTED = time.monotonic()
MAX_SECONDS = 345 * 60


def github(method, path, **kwargs):
    response = requests.request(
        method, API + path, headers=HEADERS, timeout=90, **kwargs
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"GitHub API {response.status_code}: {response.text[:300]}"
        )
    return response


def list_requests():
    response = requests.get(
        API + "/contents/requests",
        headers=HEADERS,
        params={"ref": BRANCH},
        timeout=60,
    )
    if response.status_code == 404:
        return []
    if response.status_code >= 400:
        raise RuntimeError(f"List queue failed: {response.status_code} {response.text[:300]}")
    return [
        item for item in response.json()
        if item.get("type") == "file" and item.get("name", "").endswith(".json")
    ]


def read_json(path):
    data = github(
        "GET", f"/contents/{quote(path, safe='/')}",
        params={"ref": BRANCH},
    ).json()
    raw = base64.b64decode(data["content"])
    return json.loads(raw.decode("utf-8"))


def result_exists(request_id):
    response = requests.get(
        API + f"/contents/results/{request_id}.json",
        headers=HEADERS,
        params={"ref": BRANCH},
        timeout=45,
    )
    if response.status_code == 404:
        return False
    if response.status_code >= 400:
        raise RuntimeError(f"Result check failed: {response.status_code}")
    return True


def save_result(request_id, result):
    path = f"results/{request_id}.json"
    content = json.dumps(result, ensure_ascii=False, indent=2)
    payload = {
        "message": f"VinAI: save result {request_id}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    response = requests.put(
        API + f"/contents/{quote(path, safe='/')}",
        headers=HEADERS,
        json=payload,
        timeout=90,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Save result failed: {response.status_code} {response.text[:300]}")


def wait_for_model():
    print("Menunggu llama-server siap...")
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        try:
            response = requests.get("http://127.0.0.1:8080/health", timeout=5)
            if response.ok:
                print("Model server siap.")
                return
        except requests.RequestException:
            pass
        time.sleep(5)
    raise RuntimeError("llama-server tidak siap dalam 15 menit.")


def infer(request):
    request_id = request["request_id"]
    prompt = request["prompt"]
    model = request.get("model", "gpt-oss-20b")
    reasoning = request.get("reasoning", "medium")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 1.0,
        "max_tokens": 512,
        "chat_template_kwargs": {"reasoning_effort": reasoning},
    }
    response = requests.post(MODEL_URL, json=payload, timeout=2400)
    response.raise_for_status()
    data = response.json()
    answer = data["choices"][0]["message"]["content"]
    return {
        "request_id": request_id,
        "status": "completed",
        "model": model,
        "reasoning": reasoning,
        "answer": answer,
        "created_at": request.get("created_at"),
    }


def main():
    wait_for_model()
    print("VinAI queue worker aktif. Polling setiap 10 detik.")
    while time.monotonic() - STARTED < MAX_SECONDS:
        try:
            pending = list_requests()
            handled = 0
            for item in pending:
                if time.monotonic() - STARTED >= MAX_SECONDS - 120:
                    break
                request_id = item["name"][:-5]
                if result_exists(request_id):
                    continue
                request = read_json(item["path"])
                if not isinstance(request.get("prompt"), str) or not request["prompt"].strip():
                    save_result(request_id, {
                        "request_id": request_id,
                        "status": "error",
                        "answer": "Prompt kosong atau format request tidak valid.",
                    })
                    continue
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
                handled += 1
                print(f"Request {request_id}: {result['status']}")
            if handled == 0:
                time.sleep(10)
        except Exception as exc:
            print(f"Worker error: {type(exc).__name__}: {exc}")
            time.sleep(15)
    print("Batas sesi worker tercapai. Jalankan workflow lagi untuk melanjutkan antrean.")


if __name__ == "__main__":
    main()
