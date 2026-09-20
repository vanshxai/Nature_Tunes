"""
NatureTunes API — Railway deployment
FastAPI backend: bird voice + MIDI → generated music
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os, uuid, json, time, threading, hashlib
import httpx
from dotenv import load_dotenv
load_dotenv()

# Register static ffmpeg binary (works on Railway without system ffmpeg)
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

app = FastAPI(title="NatureTunes API", version="1.0.0")

# When running locally: python -m uvicorn main:app --port 8765
# On Railway: PORT env var is set automatically

# ── PATHS ───────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
PROJECT     = os.path.dirname(BASE)
BIRD_DIR    = os.path.join(PROJECT, "data", "midi_library")
MIDI_DIR    = os.path.join(BASE, "ui", "midi_tracks")
OUTPUT_DIR  = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BIRD_CLEAN_DIR   = os.path.join(BASE, "ui", "bird_clean")
TUNE_PREVIEW_DIR = os.path.join(BASE, "ui", "tune_previews")
SAMPLES_DIR      = os.path.join(BASE, "ui", "samples")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── PATHS ───────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
# In-memory job store (use Redis/Supabase in production)
jobs = {}

# ── SUPABASE ─────────────────────────────────────────────────
SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

def supa_headers():
    return {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}", "Content-Type": "application/json"}

async def supa_post(table: str, data: dict):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{SUPA_URL}/rest/v1/{table}", json=data,
                         headers={**supa_headers(), "Prefer": "return=representation"})
        return r.json()

async def supa_get(table: str, params: dict):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{SUPA_URL}/rest/v1/{table}", params=params, headers=supa_headers())
        return r.json()

async def supa_patch(table: str, params: dict, data: dict):
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{SUPA_URL}/rest/v1/{table}", params=params, json=data,
                          headers={**supa_headers(), "Prefer": "return=representation"})
        return r.json()

def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()

# ── MODELS ──────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    bird_id: str
    midi_ids: list[str]
    user_id: str | None = None
    device_id: str | None = None
    device_info: str | None = None

class SignInRequest(BaseModel):
    phone: str
    pin: str

class SignUpRequest(BaseModel):
    phone: str
    pin: str

class FeedbackRequest(BaseModel):
    message: str
    user_id: str | None = None

# ── HELPERS ─────────────────────────────────────────────────
def get_available_birds():
    birds = []
    # Prefer clean isolated files; fall back to source mp3s
    clean_dir = os.path.join(BASE, "ui", "bird_clean")
    if os.path.exists(clean_dir):
        for fname in sorted(os.listdir(clean_dir)):
            if not fname.endswith(".mp3"):
                continue
            bid = fname.replace(".mp3", "")           # "hermit-thrush"
            uid = bid.replace("-", "_")               # "hermit_thrush" for generation
            name = bid.replace("-", " ").title()
            birds.append({"id": uid, "name": name, "audio_url": f"/bird-audio/{bid}"})
        return birds
    if not os.path.exists(BIRD_DIR):
        return birds
    for folder in sorted(os.listdir(BIRD_DIR)):
        mp3 = os.path.join(BIRD_DIR, folder, f"{folder}_source.mp3")
        if os.path.exists(mp3):
            birds.append({"id": folder, "name": folder.replace("_", " ").title(), "audio_url": f"/bird-audio/{folder}"})
    return birds

def get_available_midis():
    midis = []
    if not os.path.exists(MIDI_DIR):
        return midis
    for i, fname in enumerate(sorted(os.listdir(MIDI_DIR))):
        if fname.endswith(".mid"):
            name = fname.replace(".mid", "")
            midis.append({
                "id": name,
                "name": f"Tune {i+1}",
                "description": f"{name} — recorded melody"
            })
    return midis

def run_generation(job_id: str, bird_id: str, midi_ids: list[str]):
    """Run the bird-voice-through-MIDI pipeline (mido-based, no note_seq dependency)."""
    try:
        jobs[job_id]["status"] = "processing"

        import mido, librosa, numpy as np, soundfile as sf, subprocess

        SR = 44100

        # Load from bird_clean (committed in repo); fall back to raw data dir if local
        clean_id = bird_id.replace("_", "-")
        clean_path = os.path.join(BIRD_CLEAN_DIR, f"{clean_id}.mp3")
        raw_path   = os.path.join(BIRD_DIR, bird_id, f"{bird_id}_source.mp3")
        load_path  = clean_path if os.path.exists(clean_path) else raw_path
        if not os.path.exists(load_path):
            raise FileNotFoundError(f"Bird audio not found: {bird_id}")

        # Load bird audio
        y_bird, _ = librosa.load(load_path, sr=SR, duration=15.0)

        # Detect bird base pitch via pyin
        f0, voiced, _ = librosa.pyin(y_bird, fmin=150, fmax=8000, sr=SR)
        f0v = f0[voiced & ~np.isnan(f0)] if voiced is not None else np.array([])
        base_midi = int(round(12 * np.log2(float(np.median(f0v)) / 440) + 69)) if len(f0v) else 60

        # Parse MIDI notes with mido
        all_notes = []
        for mid_id in midi_ids:
            mid_path = os.path.join(MIDI_DIR, f"{mid_id}.mid")
            if not os.path.exists(mid_path):
                continue
            mid = mido.MidiFile(mid_path)
            tempo = 500000
            tpb = mid.ticks_per_beat
            cur_t = 0.0
            active = {}
            for track in mid.tracks:
                cur_t = 0.0
                for msg in track:
                    cur_t += mido.tick2second(msg.time, tpb, tempo)
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                    elif msg.type == 'note_on' and msg.velocity > 0:
                        active[msg.note] = cur_t
                    elif msg.type in ('note_off',) or (msg.type == 'note_on' and msg.velocity == 0):
                        if msg.note in active:
                            all_notes.append({'pitch': msg.note,
                                              'start': active.pop(msg.note),
                                              'end': cur_t})

        if not all_notes:
            raise ValueError("No notes found in selected MIDI files")

        all_notes.sort(key=lambda n: n['start'])
        total_dur = max(n['end'] for n in all_notes) + 1.0
        # Find the most energetic region of the bird audio (where it's actually chirping)
        # Use RMS in 50ms windows to locate active bird call segments
        hop = int(0.05 * SR)
        win = int(0.1 * SR)
        rms_frames = np.array([
            np.sqrt(np.mean(y_bird[j:j+win]**2))
            for j in range(0, len(y_bird) - win, hop)
        ])
        # Keep only frames above 40th percentile — active chirp regions
        threshold = np.percentile(rms_frames, 40)
        active_starts = [j * hop for j, r in enumerate(rms_frames) if r >= threshold and j * hop + win < len(y_bird)]
        if not active_starts:
            active_starts = list(range(0, len(y_bird) - win, hop))

        canvas = np.zeros(int(SR * total_dur) + SR)
        XFADE = int(0.025 * SR)   # 25ms crossfade

        def nearest_octave_shift(note_pitch, base):
            diff = note_pitch - base
            return diff - round(diff / 12) * 12

        for i, note in enumerate(all_notes):
            semitones = nearest_octave_shift(note['pitch'], base_midi)
            note_dur = max(0.1, note['end'] - note['start'])
            start_i = int(note['start'] * SR)
            n_samples = int(note_dur * SR)

            # Pick an active chirp region, cycling through available ones
            src_start = active_starts[i % len(active_starts)]
            src_end = src_start + n_samples + XFADE
            chunk = y_bird[src_start:min(src_end, len(y_bird))].copy()

            # Pad if bird file too short
            if len(chunk) < n_samples:
                chunk = np.pad(chunk, (0, n_samples - len(chunk)))
            chunk = chunk[:n_samples + XFADE]

            # Pitch shift (only if needed — saves quality)
            if abs(semitones) >= 0.5:
                chunk = librosa.effects.pitch_shift(chunk, sr=SR, n_steps=float(semitones))

            chunk = chunk[:n_samples]

            # Smooth amplitude envelope: attack 15ms, sustain, release 40ms
            env = np.ones(len(chunk))
            atk = min(int(0.015 * SR), len(chunk) // 6)
            rel = min(int(0.040 * SR), len(chunk) // 4)
            if atk > 0: env[:atk] = np.linspace(0, 1, atk)
            if rel > 0: env[-rel:] = np.linspace(1, 0, rel)
            chunk *= env

            # Crossfade overlap-add onto canvas
            end_i = start_i + len(chunk)
            if end_i > len(canvas):
                canvas = np.pad(canvas, (0, end_i - len(canvas)))

            xf = min(XFADE, start_i, len(chunk))
            if xf > 0:
                fade_in  = np.linspace(0, 1, xf)
                fade_out = np.linspace(1, 0, xf)
                chunk[:xf]  *= fade_in
                canvas[start_i:start_i + xf] *= fade_out

            canvas[start_i:end_i] += chunk

        # Normalise
        peak = np.max(np.abs(canvas))
        if peak > 0:
            canvas = canvas / peak * 0.85

        # Write via soundfile → ffmpeg → mp3
        tmp_wav = os.path.join(OUTPUT_DIR, f"{job_id}.wav")
        out_path = os.path.join(OUTPUT_DIR, f"{job_id}.mp3")
        sf.write(tmp_wav, canvas, SR)
        subprocess.run(["ffmpeg", "-y", "-i", tmp_wav, "-ab", "192k", out_path, "-loglevel", "quiet"], check=True)
        os.remove(tmp_wav)

        jobs[job_id]["status"] = "done"
        jobs[job_id]["audio_url"] = f"/output/{job_id}.mp3"
        jobs[job_id]["duration"] = total_dur

        # Write to Supabase
        if SUPA_URL and SUPA_KEY:
            import asyncio
            asyncio.run(supa_patch(
                "generations",
                {"job_id": f"eq.{job_id}"},
                {"status": "done", "output_url": f"/output/{job_id}.mp3", "duration_s": total_dur}
            ))

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        if SUPA_URL and SUPA_KEY:
            import asyncio
            try:
                asyncio.run(supa_patch("generations", {"job_id": f"eq.{job_id}"}, {"status": "error"}))
            except Exception:
                pass

# ── ROUTES ──────────────────────────────────────────────────
@app.get("/samples")
def list_samples():
    samples = []
    if os.path.exists(SAMPLES_DIR):
        labels = {
            "naturetunes_final_output": "Sample Tune 1",
            "wood_thrush_tune_preview": "Test · Wood Thrush",
            "indian_cuckoo_tune_preview": "Test · Indian Cuckoo",
        }
        for fname in sorted(os.listdir(SAMPLES_DIR)):
            if fname.endswith(".mp3"):
                key = fname.replace(".mp3", "")
                samples.append({
                    "id": key,
                    "name": labels.get(key, key.replace("_", " ").title()),
                    "url": f"/sample-audio/{fname}"
                })
    return {"samples": samples}

@app.get("/sample-audio/{filename}")
def sample_audio(filename: str):
    path = os.path.join(SAMPLES_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Sample not found")
    return FileResponse(path, media_type="audio/mpeg")

@app.get("/")
def root():
    return {"name": "NatureTunes API", "version": "1.0.0", "status": "ok"}

@app.get("/birds")
def list_birds():
    return {"birds": get_available_birds()}

@app.get("/midis")
def list_midis():
    return {"midis": get_available_midis()}


@app.get("/bird-audio/{bird_id}")
def bird_audio(bird_id: str):
    # Prefer noise-reduced clean version
    clean = os.path.join(BIRD_CLEAN_DIR, f"{bird_id}.mp3")
    if os.path.exists(clean):
        return FileResponse(clean, media_type="audio/mpeg")
    path = os.path.join(BIRD_DIR, bird_id, f"{bird_id}_source.mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Bird not found")
    return FileResponse(path, media_type="audio/mpeg")

@app.get("/tune-preview/{tune_num}")
def tune_preview(tune_num: int):
    path = os.path.join(TUNE_PREVIEW_DIR, f"tune_{tune_num}.mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Tune preview not found")
    return FileResponse(path, media_type="audio/mpeg")

@app.post("/auth/signup")
async def signup(req: SignUpRequest):
    existing = await supa_get("users", {"phone": f"eq.{req.phone}", "select": "id"})
    if existing:
        raise HTTPException(400, "Phone already registered")
    result = await supa_post("users", {"phone": req.phone, "pin_hash": hash_pin(req.pin)})
    if isinstance(result, list) and result:
        return {"user_id": result[0]["id"], "phone": result[0]["phone"]}
    raise HTTPException(500, "Signup failed")

@app.post("/auth/signin")
async def signin(req: SignInRequest):
    rows = await supa_get("users", {"phone": f"eq.{req.phone}", "select": "id,phone,pin_hash"})
    if not rows:
        raise HTTPException(401, "Phone not found")
    user = rows[0]
    if user["pin_hash"] != hash_pin(req.pin):
        raise HTTPException(401, "Wrong PIN")
    return {"user_id": user["id"], "phone": user["phone"]}

@app.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    data = {"message": req.message}
    if req.user_id:
        data["user_id"] = req.user_id
    await supa_post("feedback", data)
    return {"ok": True}

@app.post("/generate")
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "queued", "created_at": time.time()}
    # Record in Supabase
    if SUPA_URL and SUPA_KEY:
        gen_data = {"job_id": job_id, "bird_id": req.bird_id,
                    "midi_ids": req.midi_ids, "status": "queued"}
        if req.user_id:    gen_data["user_id"]    = req.user_id
        if req.device_id:  gen_data["device_id"]  = req.device_id
        if req.device_info: gen_data["device_info"] = req.device_info
        await supa_post("generations", gen_data)
    background_tasks.add_task(run_generation, job_id, req.bird_id, req.midi_ids)
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}")
def job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]

@app.get("/output/{filename}")
def get_output(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="audio/mpeg")

# Serve the UI
app.mount("/ui", StaticFiles(directory=os.path.join(BASE, "ui"), html=True), name="ui")
