# VinAI

Prototipe AI terminal pribadi yang menjalankan model Qwen2.5-Coder 3B melalui CPU GitHub Actions.

## Cara kerja

1. Jalankan `vinai.py` dari Termux.
2. Script mengirim prompt ke workflow GitHub Actions.
3. Runner Ubuntu mengompilasi llama.cpp, mengunduh model GGUF, lalu menjalankan inferensi CPU.
4. Jawaban dikirim kembali sebagai GitHub Actions Artifact dan ditampilkan di terminal.

## Persiapan di Termux

Pastikan Python tersedia, lalu:

```bash
pkg update
pkg install python
pip install -r requirements.txt
```

Buat GitHub Personal Access Token (fine-grained) khusus repository ini dengan izin **Actions: Read and write** dan **Metadata: Read-only**. Jangan pernah memasukkan token ke source code, README, atau mengirimkannya ke orang lain.

Setel token hanya di sesi Termux:

```bash
export GITHUB_TOKEN="TOKEN_MILIK_LO"
python vinai.py
```

## Batasan prototipe

- Setiap pertanyaan menjalankan workflow baru.
- Runner menggunakan CPU; respons bisa lambat.
- Model diunduh dan llama.cpp dibangun ulang pada setiap job.
- Belum ada riwayat percakapan atau memori permanen.
- Workflow belum dijamin berhasil sebelum diuji end-to-end.
- Jangan kirim data pribadi, password, token, atau source code rahasia. Repository ini saat ini public.

## Model

Qwen2.5-Coder-3B-Instruct, quantization Q4_K_M, dari repositori GGUF bartowski di Hugging Face.
