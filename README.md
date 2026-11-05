# VinAI

Prototipe AI terminal pribadi. Terminal berjalan di Termux/VPS, sedangkan inferensi dijalankan oleh satu worker GitHub Actions yang memproses antrean.

## Cara kerja antrean

- Terminal menyimpan setiap prompt sebagai `requests/<request_id>.json`.
- Satu workflow **VinAI Queue Worker** memuat model sekali, lalu memantau folder antrean.
- Worker memproses request satu per satu dan menyimpan jawaban ke `results/<request_id>.json`.
- Request yang sudah punya file hasil akan dilewati saat worker dimulai ulang.
- Antrean tetap tersimpan di branch ini ketika sesi worker berakhir.

## Menjalankan worker

1. Buka tab **Actions** repository.
2. Pilih workflow **VinAI Queue Worker**.
3. Tekan **Run workflow**.
4. Pilih model dan reasoning, lalu jalankan.
5. Tunggu sampai langkah model server siap/worker aktif.
6. Jalankan terminal VinAI. Pastikan pilihan `/model` sama dengan model yang dipilih saat worker dimulai.

Worker tidak otomatis dimulai setiap kali prompt dikirim. Jalankan satu worker terlebih dahulu, lalu kirim banyak prompt selama sesi worker aktif. Saat job mencapai batas waktu, jalankan workflow lagi untuk melanjutkan antrean.

## Fitur terminal

- `/help` — daftar perintah
- `/exit` — keluar
- `/clear` — bersihkan layar
- `/model` — lihat model terminal
- `/model gpt-oss-20b` — pilih GPT-OSS 20B MXFP4
- `/model qwen-3b` — pilih Qwen2.5-Coder 3B Q4_K_M
- `/reasoning low|medium|high` — atur reasoning GPT-OSS
- `/status` — lihat konfigurasi

## Setup Termux

```bash
pkg update
pkg install python
pip install requests
export GITHUB_TOKEN="TOKEN_MILIK_LO"
python vinai.py
```

Buat fine-grained Personal Access Token khusus repository ini dengan izin **Contents: Read and write** dan **Metadata: Read-only**. Terminal tidak perlu izin Actions. Jangan kirim token ke chat, jangan commit token ke repository, dan jangan menaruhnya di source code.

## Catatan penting

- Repository dan isi folder `requests/` serta `results/` bersifat public. Jangan masukkan password, token, data pribadi, atau source code rahasia.
- Satu worker hanya memuat satu model selama sesi berjalan. Pilihan model di terminal harus sama dengan pilihan model saat worker dimulai.
- Workflow memakai runner Linux standar dan membangun `llama.cpp` serta mengunduh model satu kali pada awal sesi.
- GPT-OSS 20B MXFP4 berukuran sekitar 12 GB. Walaupun runner publik memiliki resource yang lebih besar daripada VPS kecil, inferensi tetap eksperimental: model bisa gagal dimuat karena RAM/disk atau berjalan sangat lambat di CPU.
- Jika GPT-OSS gagal dimuat, coba jalankan worker dengan Qwen2.5-Coder 3B.
- Satu job GitHub-hosted punya batas durasi. Worker berhenti sebelum batas job, dan antrean yang belum selesai bisa diproses sesi berikutnya.
- Riwayat chat tidak dikirim sebagai konteks percakapan; setiap prompt diproses secara terpisah.
- Hasil disimpan sebagai file JSON di branch ini dan menambah commit ke riwayat repository.

## Model dan runtime

- GPT-OSS 20B GGUF MXFP4: `ggml-org/gpt-oss-20b-GGUF`
- Qwen2.5-Coder 3B GGUF Q4_K_M: `bartowski/Qwen2.5-Coder-3B-Instruct-GGUF`
- Runtime: `llama.cpp`
