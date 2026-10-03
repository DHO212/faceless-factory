import os, re, json, requests, asyncio, subprocess, textwrap, random
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import edge_tts
BASE = Path(__file__).parent
OUTPUT = BASE / "output"
ASSETS = BASE / "assets"
OUTPUT.mkdir(exist_ok=True)
PEXELS_KEY = os.getenv("PEXELS_API_KEY")
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "http://172.236.133.231:20128/v1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "claude-opus-5.5")
PROVIDERS = [
    {"base": OPENAI_BASE, "key": OPENAI_KEY, "model": OPENAI_MODEL},
    {"base": "https://api.openai.com/v1", "key": os.getenv("OPENAI_FALLBACK_KEY"), "model": "gpt-4o-mini"},
]
VOICE_EDGE = "id-ID-ArdiNeural"
def call_llm(prompt, system="Kamu scriptwriter TikTok viral, gaya bahasa Indonesia santai kayak ngobrol WA, no bullet, no dash, hook kuat 3 detik."):
    import openai
    last_err=None
    for prov in PROVIDERS:
        if not prov["key"]: continue
        try:
            client = openai.OpenAI(api_key=prov["key"], base_url=prov["base"], timeout=60)
            rr = client.chat.completions.create(model=prov["model"], messages=[{"role":"system","content":system},{"role":"user","content":prompt}], temperature=0.9, max_tokens=800)
            return rr.choices[0].message.content.strip()
        except Exception as e:
            last_err=e
            print(f"[!] {prov['base']} fail: {e} -> try next")
            continue
    raise RuntimeError(f"all providers fail: {last_err}")
def gen_script(topic, niche="finansial"):
    pr = f"Buat script TikTok/Shorts 35-45 detik tentang: {topic}\nNiche: {niche}\nAturan:\n- Hook 3 detik pertama harus ngegas, bikin penasaran, jangan generic\n- Bahasa Indonesia gaul, natural, kayak ngobrol, jangan kayak AI\n- 130-170 kata aja, 1 paragraf mengalir (gak pake bullet/dash/list)\n- Akhir kasih CTA soft: follow/comment\n- Jangan pakai emoji berlebihan, jangan pakai tanda hubung panjang\nOutput cuma script mentah, tanpa label Hook/Body/CTA."
    return call_llm(pr)
async def tts_edge(text, out_mp3):
    com = edge_tts.Communicate(text, VOICE_EDGE, rate="+5%", pitch="+0Hz")
    await com.save(str(out_mp3))
    print(f"[+] TTS saved {out_mp3} ({len(text)} chars)")
def get_duration(mp3):
    out=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(mp3)]).decode().strip()
    return float(out)
def stock_pixabay(query, per_page=3):
    try:
        r=requests.get("https://pixabay.com/api/videos/", params={"q": query, "per_page": per_page}, timeout=15)
        if r.status_code==200:
            hits=r.json().get("hits",[])
            urls=[]
            for h in hits[:per_page]:
                vids=h.get("videos",{})
                best = vids.get("medium") or vids.get("small") or vids.get("large")
                if best: urls.append(best["url"])
            if urls:
                print(f"[+] Pixabay stock {len(urls)} clips")
                return urls
        return []
    except Exception as e:
        print(f"[!] pixabay fail {e}")
        return []
def pexels_search(query, per_page=3):
    if not PEXELS_KEY or PEXELS_KEY=="YOUR_PEXELS_KEY": return []
    try:
        headers={"Authorization": PEXELS_KEY}
        rr=requests.get("https://api.pexels.com/videos/search", headers=headers, params={"query":query, "per_page":per_page, "orientation":"portrait", "size":"medium"}, timeout=30)
        rr.raise_for_status()
        vids=rr.json().get("videos",[])
        urls=[]
        for v in vids:
            files=sorted(v["video_files"], key=lambda x: x["width"], reverse=True)
            best = next((f for f in files if f["width"]==1080 or f["width"]==720), files[0])
            urls.append(best["link"])
        return urls
    except Exception as e:
        print(f"[!] pexels fail {e}")
        return []
def download(url, dest):
    print(f"[>] download {url[:90]}")
    with requests.get(url, stream=True, timeout=60) as rr:
        rr.raise_for_status()
        with open(dest,'wb') as f:
            for c in rr.iter_content(8192): f.write(c)
    return dest
def make_gradient_bg(duration, out_path, script_text):
    safe = script_text[:80].replace(":", "\\:").replace("'", "").replace('"', '')
    cmd = ["ffmpeg","-y","-f","lavfi","-i", f"color=c=0x0b1020:s=1080x1920:d={duration}:r=30","-f","lavfi","-i", f"color=c=0x1e3a5f:s=1080x1920:d={duration}:r=30","-filter_complex", f"[0][1]blend=all_mode=overlay:all_opacity=0.5,zoompan=d=1:s=1080x1920:fps=30;drawbox=x=80:y=600:w=920:h=720:color=black@0.45:t=fill,drawtext=text='{safe}':fontcolor=white:fontsize=54:box=0:x=(w-text_w)/2:y=720:line_spacing=8","-t", str(duration),"-c:v","libx264","-pix_fmt","yuv420p","-r","30",str(out_path)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except:
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i", f"color=c=0x0f172a:s=1080x1920:d={duration}:r=30","-vf","scale=1080:1920", "-t", str(duration), str(out_path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path
def assemble(video_clips, audio_mp3, out_path, script_text=""):
    dur=get_duration(audio_mp3)
    print(f"[>] audio dur {dur:.1f}s, clips {len(video_clips)}")
    list_txt = OUTPUT / "concat.txt"
    norm_clips=[]
    for i, clip in enumerate(video_clips):
        norm = OUTPUT / f"norm_{i}.mp4"
        seg = dur/len(video_clips)+0.5
        subprocess.run(["ffmpeg","-y","-i",str(clip),"-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920","-c:a","aac","-r","30","-t",str(seg), str(norm)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        norm_clips.append(norm)
    with open(list_txt,"w") as f:
        for c in norm_clips: f.write(f"file '{c}'\n")
    concat = OUTPUT / "concat.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(list_txt),"-c","copy",str(concat)], check=True)
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
    dur = get_duration(mp3)
    urls = pexels_search(query_stock, per_page=3)
    if not urls:
        urls = stock_pixabay(query_stock, per_page=3)
    clips=[]
    if urls:
        for i,u in enumerate(urls):
            try:
                pp=OUTPUT / f"clip_{i}.mp4"
                download(u,pp)
                if pp.stat().st_size < 50000:
                    pp.unlink(missing_ok=True)
                    continue
                clips.append(pp)
            except Exception as e:
                print(f"[!] clip {i} fail {e}")
                continue
    if not clips:
        print("[*] no stock -> pakai gradient background (no API key needed)")
        bg = OUTPUT / "clip_0.mp4"
        make_gradient_bg(dur+1, bg, script)
        clips=[bg]
    out = OUTPUT / f"short_{re.sub(r'[^a-z0-9]+','_',topic.lower())[:30]}.mp4"
    assemble(clips, mp3, out, script)
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
