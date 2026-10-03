import os, re, json, requests, asyncio, subprocess, textwrap, random
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import edge_tts

# ===== CONFIG =====
BASE = Path(__file__).parent
OUTPUT = BASE / "output"
ASSETS = BASE / "assets"
OUTPUT.mkdir(exist_ok=True)

PEXELS_KEY = os.getenv("PEXELS_API_KEY")
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "http://172.236.133.231:20128/v1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "claude-opus-5.5")

# cascade LLM biar gak mati di 429
PROVIDERS = [
    {"base": OPENAI_BASE, "key": OPENAI_KEY, "model": OPENAI_MODEL},
    {"base": "https://api.openai.com/v1", "key": os.getenv("OPENAI_FALLBACK_KEY"), "model": "gpt-4o-mini"},
]

VOICE_EDGE = "id-ID-ArdiNeural"  # ganti ke en-US-JennyNeural kalau konten EN
# VOICE_EDGE alternatif viral: id-ID-GadisNeural (cewek), en-US-GuyNeural

def call_llm(prompt, system="Kamu scriptwriter TikTok viral, gaya bahasa Indonesia santai kayak ngobrol WA, no bullet, no dash, hook kuat 3 detik."):
    import openai
    last_err=None
    for p in PROVIDERS:
        if not p["key"]: continue
        try:
            client = openai.OpenAI(api_key=p["key"], base_url=p["base"], timeout=60)
            r = client.chat.completions.create(
                model=p["model"],
                messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
                temperature=0.9,
                max_tokens=800
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            last_err=e
            print(f"[!] {p['base']} fail: {e} -> try next")
            continue
    raise RuntimeError(f"all providers fail: {last_err}")

def gen_script(topic, niche="finansial"):
    prompt = f"""Buat script TikTok/Shorts 35-45 detik tentang: {topic}
Niche: {niche}
Aturan:
- Hook 3 detik pertama harus ngegas, bikin penasaran, jangan generic
- Bahasa Indonesia gaul, natural, kayak ngobrol, jangan kayak AI
- 130-170 kata aja, 1 paragraf mengalir (gak pake bullet/dash/list)
- Akhir kasih CTA soft: follow/comment
- Jangan pakai emoji berlebihan, jangan pakai tanda hubung panjang —

Output cuma script mentah, tanpa label Hook/Body/CTA.
"""
    return call_llm(prompt)

async def tts_edge(text, out_mp3):
    communicate = edge_tts.Communicate(text, VOICE_EDGE, rate="+5%", pitch="+0Hz")
    await communicate.save(str(out_mp3))
    print(f"[+] TTS saved {out_mp3} ({len(text)} chars)")

def pexels_search(query, per_page=3):
    if not PEXELS_KEY or PEXELS_KEY=="YOUR_PEXELS_KEY":
        print("[!] PEXELS_API_KEY kosong, skip stock footage")
        return []
    headers={"Authorization": PEXELS_KEY}
    r=requests.get("https://api.pexels.com/videos/search", headers=headers, params={"query":query, "per_page":per_page, "orientation":"portrait", "size":"medium"}, timeout=30)
    r.raise_for_status()
    vids=r.json().get("videos",[])
    urls=[]
    for v in vids:
        # ambil file portrait terbaik
        files=sorted(v["video_files"], key=lambda x: x["width"], reverse=True)
        # prefer 1080x1920
        best = next((f for f in files if f["width"]==1080 or f["width"]==720), files[0])
        urls.append(best["link"])
    return urls

def download(url, dest):
    print(f"[>] download {url[:80]}")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest,'wb') as f:
            for c in r.iter_content(8192): f.write(c)
    return dest

def get_duration(mp3):
    out=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(mp3)]).decode().strip()
    return float(out)

def assemble(video_clips, audio_mp3, out_path, captions_text=None):
    dur=get_duration(audio_mp3)
    print(f"[>] audio dur {dur:.1f}s, clips {len(video_clips)}")
    # concat & scale to 1080x1920, loop/cut to dur
    # bikin file list untuk ffmpeg
    list_txt = OUTPUT / "concat.txt"
    # re-encode tiap clip ke 1080x1920 30fps biar mulus
    norm_clips=[]
    for i, clip in enumerate(video_clips):
        norm = OUTPUT / f"norm_{i}.mp4"
        subprocess.run(["ffmpeg","-y","-i",str(clip),"-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920","-c:a","aac","-r","30","-t",str(dur/len(video_clips)+0.5), str(norm)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        norm_clips.append(norm)
    with open(list_txt,"w") as f:
        for c in norm_clips: f.write(f"file '{c}'\n")
    concat = OUTPUT / "concat.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(list_txt),"-c","copy",str(concat)], check=True)
    # potong sesuai durasi audio + mix audio
    # tambah captions burn-in sederhana via drawtext kalau ada (tanpa whisper dulu biar cepat)
    # versi cepat: hard-cut + audio
    cmd=["ffmpeg","-y","-i",str(concat),"-i",str(audio_mp3),"-t",str(dur),"-c:v","libx264","-c:a","aac","-shortest","-vf","scale=1080:1920", str(out_path)]
    subprocess.run(cmd, check=True)
    print(f"[+] DONE {out_path}")

async def run_one(topic, niche, query_stock):
    print(f"\n=== {topic} ===")
    script = gen_script(topic, niche)
    print("[SCRIPT]", script)
    (OUTPUT/"script.txt").write_text(script, encoding="utf-8")
    mp3 = OUTPUT / "voice.mp3"
    await tts_edge(script, mp3)
    # stock
    urls = pexels_search(query_stock, per_page=3)
    clips=[]
    if urls:
        for i,u in enumerate(urls):
            p=OUTPUT / f"clip_{i}.mp4"
            download(u,p)
            clips.append(p)
    else:
        # fallback: bikin background color kalau gak ada pexels
        bg = OUTPUT / "clip_0.mp4"
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c=0x0a0a0a:s=1080x1920:d=60","-vf","scale=1080:1920",str(bg)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clips=[bg]
    out = OUTPUT / f"short_{re.sub(r'[^a-z0-9]+','_',topic.lower())[:30]}.mp4"
    assemble(clips, mp3, out)
    print(f"\n[READY] {out} -> upload ke TikTok/YT Shorts")
    return script, str(out)

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--topic", default="3 kesalahan finansial anak muda yang bikin miskin diam-diam")
    ap.add_argument("--niche", default="finansial")
    ap.add_argument("--stock", default="money business city")
    args=ap.parse_args()
    asyncio.run(run_one(args.topic, args.niche, args.stock))
