CARA JALAN DI GITHUB CODESPACES GRATIS (no CC)

1. Buat repo baru di github.com/new -> nama faceless-factory (public/private bebas)
2. Upload semua file dari folder ini (drag drop atau git push)
3. Klik tombol hijau Code -> Codespaces -> Create codespace on main
4. Tunggu 1-2 menit (auto install ffmpeg + python deps + n8n)
5. Di terminal codespace:
   cp .env.example .env
   nano .env  # isi OPENAI_API_KEY + PEXELS_API_KEY
   python main.py --topic "3 kesalahan finansial anak muda"
6. Buat n8n:
   n8n start
   -> buka link port 5678 yang muncul di popup VS Code

LIMIT GRATIS:
- 60 jam/bulan utk 2-core / 15GB storage (cukup buat 2-3 video/hari)
- Codespace auto sleep setelah 30 menit idle -> buat render manual oke, buat cron 24/7 kurang cocok
- Buat production 24/7 tetep butuh VPS (CloudBaik 49rb atau Contabo 95rb)

TIP: jangan lupa stop codespace kalau gak dipake biar jam gak kepotong: Code -> Codespaces -> Stop
