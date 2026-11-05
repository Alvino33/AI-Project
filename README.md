# VinAI

Prototipe AI terminal pribadi. Client berjalan di Termux, sedangkan inferensi dijalankan oleh GitHub Actions.

## Fitur terminal

- `/help` — daftar perintah
- `/exit` — keluar
- `/clear` — bersihkan layar
- `/model` — lihat model aktif
- `/model gpt-oss-20b` — pilih GPT-OSS 20B MXFP4
- `/model qwen-3b` — pilih Qwen2.5-Coder 3B Q4_K_M
- `/reasoning low|medium|high` — atur reasoning GPT-OSS
- `/status` — lihat konfigurasi

Setiap prompt memicu satu workflow baru. Client mencocokkan workflow menggunakan request ID, lalu membaca jawaban dari log GitHub Actions langsung ke terminal. Tidak ada artifact jawaban atau file ZIP yang disimpan ke perangkat; arsip log dibaca sementara di memori.

## Setup Termux

```bash
pkg update
pkg install python
pip install -r requirements.txt
export GITHUB_TOKEN="TOKEN_MILIK_LO"
python vinai.py
```

Buat fine-grained Personal Access Token khusus repository ini dengan izin **Actions: Read and write** dan **Metadata: Read-only**. Jangan kirim token ke chat, jangan commit token ke repository, dan jangan menaruhnya di source code.

## Catatan penting untuk GPT-OSS 20B

- Model memakai file GGUF MXFP4 sekitar 12 GB.
- Workflow menggunakan runner Linux standar untuk repository publik (spesifikasi runner dapat berubah).
- Runner standar memiliki ruang disk terbatas. Walaupun RAM runner publik tercantum 16 GB, GPT-OSS 20B tetap eksperimental di runner ini: unduhan model bisa kehabisan disk, inferensi bisa kehabisan RAM, dan CPU-only bisa sangat lambat.
- Jika GPT-OSS gagal karena resource, pilih `/model qwen-3b` untuk pengujian yang lebih ringan.
- Perintah `/reasoning` diterapkan pada GPT-OSS; Qwen mengabaikannya.
- Riwayat percakapan belum disimpan. `/clear` hanya membersihkan layar terminal.
- Jawaban diambil dari log workflow. Jangan masukkan password, token, data pribadi, atau source code rahasia. Repository ini public.

## Model dan runtime

- GPT-OSS 20B GGUF MXFP4: `ggml-org/gpt-oss-20b-GGUF`
- Qwen2.5-Coder 3B GGUF Q4_K_M: `bartowski/Qwen2.5-Coder-3B-Instruct-GGUF`
- Runtime: `llama.cpp`
