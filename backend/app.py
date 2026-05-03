# app.py — CHIMERA HYBRID v1.5
# - v0.5 gritty generator, protest, risk, clusters
# - Simulated GAN fingerprinter
# - In-memory PRNU (register/match)
# - Narrative Ops (generate drafts; return posts to push)
# Run: uvicorn app:app --reload

from __future__ import annotations
import base64, hashlib, io, math, random, re, statistics, time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image, ImageOps, ImageFilter, ImageChops, ImageStat
import base64, io
# ---------- OPSEC + MISINFO ANALYZER ----------
from pydantic import BaseModel
from pathlib import Path
import json, re, uuid

FAKE_KW = [
    r"\bfake\b", r"\bhoax\b", r"deepfake", r"doctored",
    r"mass\s*casualt(y|ies)\s*unconfirmed", r"blackout\s*media",
]
OPSEC_KW = [
    r"\bconvoy\b", r"\broute\s*\d+\b", r"\btroop(s)?\b", r"\bgrid node\b",
    r"\bbridge\b", r"\bfuel depot\b", r"\bartillery\b", r"\bat dawn\b", r"\b05:00\b",
    r"\bmeet at\b", r"\bcoordinates?\b", r"\blat\s*[,:\s]\s*\d", r"\blon[g]?\s*[,:\s]\s*\d",
]

class AnalyzeItem(BaseModel):
    post_id: str
    verdict: str          # FAKE_DISINFORMATION | SENSITIVE_OPSEC | OK
    reasons: list[str] = []
    score: int = 0

class AnalyzeReq(BaseModel):
    analyst: str = "analyst"
    posts: list[dict]
    cluster_title: str | None = None
    create_dossier: bool = True
    soft_flag: bool = True



UTC = timezone.utc

def now_utc() -> datetime:
    return datetime.now(tz=UTC)

def parse_ts(ts: str) -> datetime:
    s = ts
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        # naive fallback
        dt = datetime.strptime(ts.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    if dt.tzinfo is None: dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00","Z")

def norm01(x: float, lo: float, hi: float) -> float:
    if hi <= lo: return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))

def jaccard(a: set, b: set) -> float:
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)
def _decode_image_to_pil(b64: str) -> Image.Image:
    """Decode base64 (raw or data URL) -> RGB PIL Image."""
    if not b64:
        raise ValueError("empty image b64")
    if "," in b64:
        b64 = b64.split(",", 1)[1]  # strip data URL prefix if present
    data = base64.b64decode(b64, validate=False)
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    elif img.mode == "RGBA":
        img = img.convert("RGB")
    return img

def _rms(a: Image.Image, b: Image.Image) -> float:
    """Root-mean-square difference between two same-size grayscale images, 0..1."""
    if a.size != b.size:
        b = b.resize(a.size, Image.BILINEAR)
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    # if grayscale, stat.rms is single value; if RGB, average them
    if isinstance(stat.rms, (list, tuple)):
        val = sum(stat.rms) / (len(stat.rms) * 255.0)
    else:
        val = stat.rms / 255.0
    return max(0.0, min(1.0, float(val)))


# ----------------------------
# Data & Lexicons (from v0.5)
# ----------------------------
CITIES = {
    "Mumbai": {"lat": 19.0760, "lon": 72.8777},
    "Delhi": {"lat": 28.7041, "lon": 77.1025},
    "Bangalore": {"lat": 12.9716, "lon": 77.5946},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867},
    "Chennai": {"lat": 13.0827, "lon": 80.2707},
    "Kolkata": {"lat": 22.5726, "lon": 88.3639},
    "Pune": {"lat": 18.5204, "lon": 73.8567},
    "Ahmedabad": {"lat": 23.0225, "lon": 72.5714},
    "Jaipur": {"lat": 26.9124, "lon": 75.7873},
    "Surat": {"lat": 21.1702, "lon": 72.8311}
}
AREAS = list(CITIES.keys())
VIOLENCE_KW = [
    "tear gas","clashes","barricades","molotov","stones","riot","shots","gunfire",
    "looting","arrests","baton","injured","blood","smoke","fire","police advance","water cannon"
]
CALL_KW = [
    "we will block","block the","meet at","assemble","march at","bring supplies","burn",
    "shut down","hold the line","fallback route","stay ready","join now","rt","pls share",
    "spread fast","notify press","meet 5am","at dawn","strike called","target the"
]
COORD_KW = [
    "route a","route b","fallback","squad","cell","briefing","signal","code word",
    "phase 2","phase-2","grid down","convoy delayed"
]
HASHTAGS = ["#breaking","#citywatch","#update","#civic","#ground","#alert","#live","#urgent","#witness","#justnow","#ontheroad"]
OPENERS = ["Breaking:","FYI:","Heads-up:","Local update:","Hearing:","Witness:","Thread:","Alert:","PSA:","Officials say:","Unconfirmed:"]
PERSONAL = ["I saw","my friend says","we just heard","neighbors claim","people around me say","saw with my own eyes","can't breathe","this is insane","wtf is happening","no joke","dead serious"]
RUMOR_FRAGMENTS = ["hearing arrests but no visuals","someone said shots fired??","unconfirmed tear gas","maybe fake? can't tell","rumor police moving","media blackout???","net down for some","roads sealed? unsure"]
MEDIA_VERBS = ["clip","video","image","photo","live feed","audio","bodycam","dashcam"]
REPORT_VERBS = ["crowd surging","barricades appear","police advance","tear gas in air","convoy delayed","lights out near grid","sirens everywhere","chanting grows","windows smashed","people running"]
ANGRY_LINES = ["enough is enough","this is on them","total overreach","we're not backing down","they started it","shameful","cowards","corrupt to the core"]
DEBUNK_LINES = ["stop spreading fakes","no gas here","calm down folks","media wrong again","rumor only, not confirmed","stand down","this is exaggerated"]
NATSEC_TARGETS = ["power station","bridge controls","fuel depo","city hall","metro yard","grid node"]
PLATFORMS = ["FakeTwitter","CivicForum","NewsWire","GroundEye","OpenVid"]

# ----------------------------
# Models
# ----------------------------
class UserModel(BaseModel):
    id: str
    created: str
    followers: int
    following: int
    bio_empty: bool

class GeoModel(BaseModel):
    tile: str
    lat: float
    lon: float

class PostModel(BaseModel):
    id: str
    text: str
    timestamp: str
    user: UserModel
    geo: GeoModel
    media: List[str] = Field(default_factory=list)
    source: str = "Synthetic"
    sentiment: float = 0.0

class GenReq(BaseModel):
    n: int = 120
    tile: str = "tile_77_12"
    mode: str = "escalation"  # baseline / escalation / coordination

class ProtestReq(BaseModel):
    tile: str
    start: str
    end: str
    posts: List[PostModel]
    baseline_avg_per_min: Optional[float] = None

class CoordinationReq(BaseModel):
    topic_key: str = "#policyX"
    window_start: str
    window_end: str
    posts: List[PostModel]

# Forensics
class GanImage(BaseModel):
    id: str
    b64: str

class GanReq(BaseModel):
    image: GanImage

class GanResp(BaseModel):
    score: int
    details: Dict[str, float]

class PrnuRegisterReq(BaseModel):
    camera_id: str
    images: List[GanImage]

class PrnuRegisterResp(BaseModel):
    status: str
    camera_id: str
    strength: float

class PrnuMatchReq(BaseModel):
    images: List[GanImage]
    top_k: int = 1

class PrnuMatchResp(BaseModel):
    results: List[Dict[str, Any]]

# Narrative
class NarrativeGenReq(BaseModel):
    base_text: Optional[str] = None
    post_id: Optional[str] = None
    tone: str = "Government"
    count: int = 4

class NarrativeGenResp(BaseModel):
    drafts: List[str]

# ----------------------------
# App
# ----------------------------
app = FastAPI(title="Chimera Hybrid", version="1.5")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ----------------------------
# Synthetic generation (v0.5)
# ----------------------------
def _rand_user() -> UserModel:
    uid = f"user{random.randint(1,2000)}"
    created = now_utc() - timedelta(days=random.randint(0, 365*3), hours=random.randint(0,23))
    return UserModel(
        id=uid, created=iso(created),
        followers=random.randint(0, 5000),
        following=random.randint(0, 1500),
        bio_empty=random.random() < 0.15
    )

def _sentiment_guess(text: str) -> float:
    txt = text.lower()
    score = 0.0
    score -= 0.3 * sum(1 for w in VIOLENCE_KW if w in txt)
    score -= 0.25 * sum(1 for w in ["wtf","furious","angry","shameful","cowards"] if w in txt)
    score += 0.1 * sum(1 for w in ["calm","ok","fine","peaceful"] if w in txt)
    return max(-1.0, min(1.0, score + random.uniform(-0.1, 0.1)))

def _make_post_text(area: str, mode: str) -> str:
    opener = random.choice(OPENERS)
    style = random.choice(["panic","organizer","reporter","rumor","angry","debunk"])
    media_word = random.choice(MEDIA_VERBS)
    report = random.choice(REPORT_VERBS)

    maybe_call  = random.random() < (0.45 if mode != "baseline" else 0.05)
    maybe_coord = random.random() < (0.25 if mode == "coordination" else 0.08)
    call_kw  = random.choice(CALL_KW)  if maybe_call  else None
    coord_kw = random.choice(COORD_KW) if maybe_coord else None
    tag = random.choice(HASHTAGS)

    personal = random.choice(PERSONAL)
    rumor    = random.choice(RUMOR_FRAGMENTS)
    angry    = random.choice(ANGRY_LINES)
    debunk   = random.choice(DEBUNK_LINES)
    natsec   = random.choice(NATSEC_TARGETS)

    if style == "panic":
        base = f"{opener} {personal} at {area}: {report}. {random.choice(['sirens everywhere','people screaming','streets blocked'])}."
    elif style == "organizer":
        base = f"{opener} meet at {area} — {random.choice(['stay ready','bring supplies','no backing down'])}."
    elif style == "reporter":
        base = f"{opener} Live from {area}: {report} ({media_word})."
    elif style == "rumor":
        base = f"{opener} {area}: {rumor}"
    elif style == "angry":
        base = f"{opener} {area}: {report}. {angry}."
    else:
        base = f"{opener} {area}: {debunk}."

    extras = []
    if call_kw:  extras.append(call_kw)
    if coord_kw: extras.append(coord_kw)
    if random.random() < 0.18: extras.append(f"target the {natsec}")
    if random.random() < 0.25: extras.append("pls share")
    if random.random() < 0.25: extras.append("stay ready")
    if extras: base = base + " " + "; ".join(extras) + "."

    tags = [tag]
    if random.random() < 0.3:  tags.append(random.choice(HASHTAGS))
    if random.random() < 0.15: tags.append(random.choice(HASHTAGS))

    text = f"{base} {' '.join(tags)}"
    if random.random() < 0.25: text = text.replace(":", " —")
    if random.random() < 0.2:  text += random.choice(["!!","?!","..."])
    if random.random() < 0.15: text = text.replace("  ", " ")
    return text.strip()

def synth_posts(n: int, tile: str, mode: str) -> List[PostModel]:
    posts: List[PostModel] = []
    start = now_utc() - timedelta(minutes=40)
    for i in range(n):
        area = random.choice(AREAS)
        base_geo = CITIES[area]
        jitter = random.randint(0, 2400 if mode=="baseline" else 900)
        ts = start + timedelta(seconds=jitter) + timedelta(seconds=i % 30)
        text = _make_post_text(area, mode)
        media = []
        if any(k in text for k in ["Live from", "clip", "(video)", "image", "photo"]):
            if random.random() < 0.7:
                media = [random.choice(["img.jpg","vid.mp4","clip.mp4","live.m3u8"])]
        posts.append(PostModel(
            id=f"p{i}",
            text=text,
            timestamp=iso(ts),
            user=_rand_user(),
            geo=GeoModel(tile=tile, lat=base_geo["lat"] + random.uniform(-0.02, 0.02), lon=base_geo["lon"] + random.uniform(-0.02, 0.02)),
            media=media,
            source=random.choice(PLATFORMS),
            sentiment=_sentiment_guess(text)
        ))
    if mode != "baseline" and n >= 4 and random.random() < 0.8:
        for j in random.sample(range(n), k=min(3, n)):
            area = random.choice(AREAS)
            posts[j].text = f"We will block {area} at dawn. bring supplies. hold the line. #alert"
            posts[j].sentiment = -0.9
    return posts

# ----------------------------
# Risk & Coordination & Protest (v0.5)
# ----------------------------
VIOLENCE_RE = re.compile("|".join([re.escape(w) for w in VIOLENCE_KW]), re.I)
CALL_RE     = re.compile("|".join([re.escape(w) for w in CALL_KW]), re.I)
COORD_RE    = re.compile("|".join([re.escape(w) for w in COORD_KW]), re.I)
EXPLICIT_BLOCK_RE = re.compile(r"\b(block|shut\s*down|burn|storm)\b.*\b(bridge|station|depot|hall|grid|market|road)\b", re.I)

def label_risk(posts: List[PostModel]) -> Dict[str, List[Dict[str, Any]]]:
    high, mild = [], []
    for p in posts:
        t = p.text.lower()
        reasons = []
        if EXPLICIT_BLOCK_RE.search(t): reasons.append("explicit call to block/attack infrastructure")
        if "at dawn" in t or "5am" in t or "meet" in t: reasons.append("timed call to action")
        if VIOLENCE_RE.search(t): reasons.append("violent/riot terminology")
        if CALL_RE.search(t): reasons.append("mobilization language")
        if COORD_RE.search(t): reasons.append("coordination jargon")
        if "target the" in t: reasons.append("targets national-interest asset")

        score = 0
        score += 30 if any(k in reasons for k in ["explicit call to block/attack infrastructure","targets national-interest asset"]) else 0
        score += 20 if "timed call to action" in reasons else 0
        score += 20 if "violent/riot terminology" in reasons else 0
        score += 15 if "mobilization language" in reasons else 0
        score += 10 if "coordination jargon" in reasons else 0
        score += int(10 * (1 - max(-1.0, min(1.0, p.sentiment)))/2)

        entry = {
            "id": p.id, "text": p.text, "source": p.source,
            "reason": "; ".join(reasons) if reasons else "none",
            "sentiment": round(p.sentiment, 3)
        }
        if score >= 55: high.append(entry)
        elif score >= 30: mild.append(entry)

    high.sort(key=lambda x: (len(x["reason"]), -x["sentiment"]), reverse=True)
    mild.sort(key=lambda x: (len(x["reason"]), -x["sentiment"]), reverse=True)
    return {"high": high[:40], "mild": mild[:60]}

WINDOW_MIN = 10

def _tokenize(text: str) -> set:
    t = re.sub(r"[^a-z0-9#\s]", " ", text.lower())
    return set([w for w in t.split() if len(w) >= 3])

def _bot_like(p: PostModel) -> bool:
    created_days = (now_utc() - parse_ts(p.user.created)).days
    low_follow = p.user.followers < 20 and p.user.following > 100
    many_hash = len([w for w in p.text.split() if w.startswith("#")]) >= 3
    empty_bio = p.user.bio_empty
    repetitive = len(set(p.text.lower().split()))/max(1,len(p.text.split())) < 0.45
    return (created_days <= 14 and (low_follow or empty_bio or many_hash or repetitive))

def detect_clusters(posts: List[PostModel], start: datetime, end: datetime) -> Dict[str, Any]:
    buckets: Dict[str, List[PostModel]] = {}
    for p in posts:
        ts = parse_ts(p.timestamp)
        if not (start <= ts <= end): 
            continue
        area_found = None
        lowt = p.text.lower()
        for a in AREAS:
            if a.lower() in lowt:
                area_found = a; break
        if not area_found: continue
        minute = ts.replace(second=0, microsecond=0)
        win = minute - timedelta(minutes=minute.minute % WINDOW_MIN)
        key = f"{area_found}|{iso(win)}"
        buckets.setdefault(key, []).append(p)

    clusters = []
    for key, plist in buckets.items():
        if len(plist) < 3: continue
        area, win = key.split("|", 1)
        v_count = sum(1 for p in plist if VIOLENCE_RE.search(p.text))
        cta_count = sum(1 for p in plist if CALL_RE.search(p.text))
        coord_count = sum(1 for p in plist if COORD_RE.search(p.text))
        sigs = [hashlib.md5(re.sub(r"\s+"," ", p.text.lower()).encode()).hexdigest()[:8] for p in plist]
        dup_ratio = 1 - (len(set(sigs)) / max(1, len(sigs)))
        bot_like_posts = sum(1 for p in plist if _bot_like(p))
        bot_cluster = (dup_ratio > 0.35 or bot_like_posts >= max(2, len(plist)//3))
        nat_flag = any("target the" in p.text.lower() for p in plist)
        size = len(plist)
        base = 35 * norm01(size, 3, 10) + 20 * norm01(v_count, 0, 4) + 20 * norm01(cta_count, 0, 3) + 15 * norm01(coord_count, 0, 2)
        if bot_cluster: base += 10
        if nat_flag: base += 10
        score = int(max(0, min(100, round(base))))
        clusters.append({
            "area": area,
            "window_start": win,
            "size": size,
            "member_post_ids": [p.id for p in plist],
            "coordination_score": score,
            "bot_suspected": bot_cluster,
            "national_interest_flag": nat_flag,
            "combined_reason": ("⚠ Sus bot cluster. " if bot_cluster else "") + f"{area} — {size} posts in {WINDOW_MIN}-min window; kw: violence={v_count}, calls={cta_count}, coord={coord_count}"
        })
    clusters.sort(key=lambda c: c["coordination_score"], reverse=True)
    return {"clusters": clusters}

def protest_signals(tile: str, start: datetime, end: datetime, posts: List[PostModel]) -> Dict[str, Any]:
    W = [p for p in posts if p.geo.tile == tile and start <= parse_ts(p.timestamp) <= end]
    if not W:
        return {
            "score": 0, "level": "baseline", "narrative": "No activity in window.",
            "signals": {"vol_z":0, "neg_shift":0, "violence_rate":0, "media_surge":0, "geo_density":0},
            "evidence_ids": [], "high_risk": [], "mild_risk": [], "area_scores":[]
        }
    per_min = max(1, int((end - start).total_seconds() // 60))
    vol = len(W) / per_min
    baseline = 1.0
    vol_z = (vol - baseline) / max(0.5, math.sqrt(baseline))
    sentiments = [p.sentiment for p in W]
    neg_shift = 0 - (statistics.mean(sentiments) if sentiments else 0)
    viol_cnt = sum(1 for p in W if VIOLENCE_RE.search(p.text))
    violence_rate = viol_cnt / max(1, len(W))
    media_surge = sum(1 for p in W if p.media) / max(1, len(W))
    geo_density = 0.0

    vol_comp = norm01(vol_z, 0, 3)
    neg_comp = norm01(neg_shift, 0, 0.8)
    viol_comp = norm01(violence_rate, 0, 0.35)
    media_comp = norm01(media_surge, 0, 0.6)
    score = int(100 * (0.32*vol_comp + 0.28*viol_comp + 0.22*neg_comp + 0.18*media_comp))
    level = "baseline"
    if score >= 85: level = "critical"
    elif score >= 70: level = "high"
    elif score >= 40: level = "moderate"

    evid = [p for p in W if VIOLENCE_RE.search(p.text) or CALL_RE.search(p.text)]
    evidence_ids = [p.id for p in evid][:20]
    risks = label_risk(W)

    # per-area scores
    area_scores = []
    by_area: Dict[str, List[PostModel]] = {}
    for p in W:
        found = next((a for a in AREAS if a.lower() in p.text.lower()), None)
        if not found: continue
        by_area.setdefault(found, []).append(p)

    for area in AREAS:
        plist = by_area.get(area, [])
        if not plist:
            area_scores.append({"area": area, "score": 0, "level": "baseline", "evidence_post_ids": []})
            continue
        v = sum(1 for p in plist if VIOLENCE_RE.search(p.text))
        cta = sum(1 for p in plist if CALL_RE.search(p.text))
        neg = statistics.mean([p.sentiment for p in plist]) if plist else 0
        s = int(100 * (0.45*norm01(v/len(plist), 0, 0.4) + 0.35*norm01(cta/len(plist), 0, 0.35) + 0.20*norm01(-neg, 0, 0.8)))
        lv = "baseline"
        if s >= 85: lv = "critical"
        elif s >= 70: lv = "high"
        elif s >= 40: lv = "moderate"
        ev_ids = [p.id for p in plist if VIOLENCE_RE.search(p.text) or CALL_RE.search(p.text)][:10]
        area_scores.append({"area": area, "score": s, "level": lv, "evidence_post_ids": ev_ids})
    area_scores.sort(key=lambda x: x["score"], reverse=True)

    return {
        "score": score, "level": level,
        "narrative": f"Overall: {score}/100 ({level}).",
        "signals": {
            "vol_z": round(vol_z,2), "neg_shift": round(neg_shift,2),
            "violence_rate": round(violence_rate,2), "media_surge": round(media_surge,2),
            "geo_density": round(geo_density,2)
        },
        "evidence_ids": evidence_ids,
        "high_risk": risks["high"],
        "mild_risk": risks["mild"],
        "area_scores": area_scores
    }

# ----------------------------
# Forensics (Simulated)
# ----------------------------
def _b64_stats(b64: str) -> Dict[str, float]:
    s = re.sub(r"[^A-Za-z0-9+/=]", "", b64 or "")
    n = len(s)
    if n == 0:
        return {"grid":0.0,"chan":0.0,"block":0.0}
    # cheap signals based on repeating patterns & symbol skew
    repeats = sum(1 for i in range(2, min(256, n-2)) if s[i]==s[i-2])
    skew = abs(s.count("A")/n - s.count("/")+1) / (n+1)
    blocks = sum(1 for ch in "==") / max(1,n)
    return {
        "grid": min(1.0, repeats / 200.0),
        "chan": min(1.0, skew / 10.0),
        "block": min(1.0, blocks)
    }

@app.post("/forensics/ganfinger/score", response_model=GanResp)
def gan_fingerprint_sim(req: GanReq):
    """
    Balanced simulated GAN detector (0..100).
    Signals used:
      - Edge density on 128x128 grayscale
      - Bright/Dark extreme fractions (over-contrast)
      - Channel imbalance (RGB mean spread)
      - Blockiness proxy (downscale->upscale RMS diff)
      - Size prior (very large imgs nudge upward)
    """
    try:
        img = _decode_image_to_pil(req.image.b64)
    except Exception:
        # unreadable -> low, but not zero
        return GanResp(score=12, details={"gridiness": 0.02, "channel_anomaly": 0.03, "blockiness": 0.04})

    # --- prep ---
    w, h = img.size
    px = w * h
    gray128 = ImageOps.grayscale(img.resize((128, 128), Image.BILINEAR))

    # 1) Edge density (0..1)
    edges = gray128.filter(ImageFilter.FIND_EDGES)
    edge_vals = sum(edges.getdata()) / (128 * 128 * 255.0)  # 0..1
    f_edge = max(0.0, min(1.0, (edge_vals - 0.08) / 0.35))  # normalize with gentle floor

    # 2) Bright/Dark extremes (0..1)
    hist = gray128.histogram()
    total = float(sum(hist) or 1.0)
    dark = sum(hist[:20]) / total      # very dark
    bright = sum(hist[236:]) / total   # very bright
    f_bright = max(0.0, min(1.0, (dark - 0.10) / 0.25)) + max(0.0, min(1.0, (bright - 0.08) / 0.25))
    f_bright = max(0.0, min(1.0, f_bright / 2.0))

    # 3) Channel imbalance (0..1) — mean spread across R,G,B
    r, g, b = img.split()
    stat_r = ImageStat.Stat(r).mean[0]
    stat_g = ImageStat.Stat(g).mean[0]
    stat_b = ImageStat.Stat(b).mean[0]
    mean_spread = (abs(stat_r - stat_g) + abs(stat_r - stat_b) + abs(stat_g - stat_b)) / (3 * 255.0)
    f_chan = max(0.0, min(1.0, (mean_spread - 0.02) / 0.20))

    # 4) Blockiness proxy: downscale->upscale RMS difference (0..1)
    small_w = max(8, w // 10)
    small_h = max(8, h // 10)
    down = img.resize((small_w, small_h), Image.BILINEAR)
    up = down.resize((w, h), Image.NEAREST)
    blockiness = _rms(ImageOps.grayscale(img), ImageOps.grayscale(up))  # 0..1
    f_block = max(0.0, min(1.0, (blockiness - 0.06) / 0.30))

    # 5) Size prior — >3 MP gets a small nudge
    f_size = 1.0 if px >= 3_000_000 else (0.5 if px >= 1_200_000 else 0.0)

    # Combine (balanced). Natural photos ~20–45; obvious fakes 70–95.
    base = 22.0  # natural prior
    score = (
        base
        + 30.0 * f_edge
        + 22.0 * f_bright
        + 18.0 * f_chan
        + 20.0 * f_block
        + 8.0  * f_size
    )
    score = int(max(0, min(100, round(score))))

    details = {
        "gridiness": round(f_bright, 3),          # “visual extremes”
        "channel_anomaly": round(f_chan, 3),      # RGB imbalance
        "blockiness": round(f_block, 3),          # upsampled RMS diff
    }
    return GanResp(score=score, details=details)


# PRNU memory
_PRNU_DB: Dict[str, List[int]] = {}

def _fingerprint(b64: str) -> List[int]:
    # hash to pseudo-noise vector
    h = hashlib.sha256(b64.encode()).digest()
    return [x for x in h]

@app.post("/forensics/prnu/register", response_model=PrnuRegisterResp)
def prnu_register(req: PrnuRegisterReq):
    if not req.images:
        return PrnuRegisterResp(status="no_images", camera_id=req.camera_id, strength=0.0)
    vecs = []
    for img in req.images:
        vecs.append(_fingerprint(img.b64))
    # simple average magnitude as "strength"
    strength = sum(sum(v) for v in vecs) / (len(vecs)*len(vecs[0]))
    _PRNU_DB[req.camera_id] = [sum(col)//len(vecs) for col in zip(*vecs)]
    return PrnuRegisterResp(status="ok", camera_id=req.camera_id, strength=round(float(strength), 3))

@app.post("/forensics/prnu/match", response_model=PrnuMatchResp)
def prnu_match(req: PrnuMatchReq):
    if not req.images:
        return PrnuMatchResp(results=[])
    q = _fingerprint(req.images[0].b64)
    best = None
    for cam, fp in _PRNU_DB.items():
        # correlation-like score
        score = sum(abs(a-b) for a,b in zip(q, fp))
        if best is None or score < best[1]:
            best = (cam, score)
    if best is None:
        return PrnuMatchResp(results=[{"image_id": req.images[0].id, "best_camera": None, "zncc": 0.0, "pce": 0.0}])
    # map distance to 0..1 "similarity"
    dist = best[1]
    sim = max(0.0, 1.0 - dist/10000.0)
    return PrnuMatchResp(results=[{
        "image_id": req.images[0].id,
        "best_camera": best[0],
        "zncc": round(sim, 3),
        "pce": round(sim*30, 2)
    }])

# ----------------------------
# Narrative Ops (Simulated)
# ----------------------------
TONE_MAP = {
    "Government": [
        "Official update: {point}. Please rely on verified channels.",
        "City officials are coordinating resources. {point} Stay safe and avoid rumors.",
        "We’re on-site with emergency teams. {point} Avoid the area until cleared.",
        "Clarification: {point} We’ll share more once confirmed."
    ],
    "Police": [
        "Police advisory: {point} Keep routes clear for emergency vehicles.",
        "Officers are deployed. {point} Please follow instructions on scene.",
        "Rumor control: {point} Do not share unverified content.",
        "We’re monitoring the situation. {point} Report emergencies via 112."
    ],
    "Neutral": [
        "Update: {point}",
        "Clarification: {point}",
        "Note: {point}",
        "FYI: {point}"
    ],
    "Technical": [
        "Operational note: {point} Incident command assessing.",
        "Logistics: {point} Traffic re-route in effect.",
        "Signal: {point} Communications lines tested.",
        "Ops: {point} Next bulletin in 30 minutes."
    ]
}

def _clean_point(txt: str) -> str:
    t = re.sub(r"\s+", " ", txt or "").strip()
    # keep it short-ish
    return (t[:220] + "…") if len(t) > 220 else t

@app.post("/narrative/generate", response_model=NarrativeGenResp)
def narrative_generate(req: NarrativeGenReq):
    tone = req.tone if req.tone in TONE_MAP else "Government"
    count = max(1, min(6, int(req.count or 1)))
    base = _clean_point(req.base_text or "")
    # fallback point
    if not base: base = "Unverified report circulating online. Wait for official confirmation."
    drafts = []
    templates = TONE_MAP[tone]
    for i in range(count):
        tmpl = random.choice(templates)
        drafts.append(tmpl.format(point=base))
    return NarrativeGenResp(drafts=drafts)

# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
def health():
    return {"ok": True, "version": "1.5", "stamp": iso(now_utc())}

@app.post("/synthetic/posts")
def gen_posts(req: GenReq):
    posts = synth_posts(req.n, req.tile, req.mode)
    return {"posts": [p.dict() for p in posts]}

@app.post("/detect/coordination")
def detect_coord(req: CoordinationReq):
    start = parse_ts(req.window_start)
    end   = parse_ts(req.window_end)
    return detect_clusters(req.posts, start, end)

@app.post("/detect/protest")
def detect_protest(req: ProtestReq):
    start = parse_ts(req.start)
    end   = parse_ts(req.end)
    return protest_signals(req.tile, start, end, req.posts)
@app.post("/analyze/auto")
def analyze_auto(req: AnalyzeReq):
    items: list[AnalyzeItem] = []
    for p in req.posts:
        t = (p.get("text") or "").lower()
        reasons = []
        fake_hit = any(re.search(rx, t, re.I) for rx in FAKE_KW)
        opsec_hit = any(re.search(rx, t, re.I) for rx in OPSEC_KW)

        verdict = "OK"
        score = 10
        if fake_hit:
            verdict = "FAKE_DISINFORMATION"; reasons.append("misinformation indicators")
            score = 80
        if opsec_hit:
            verdict = "SENSITIVE_OPSEC"; reasons.append("operational/security keywords")
            score = 75 if verdict == "SENSITIVE_OPSEC" else score

        items.append(AnalyzeItem(
            post_id=p.get("id",""),
            verdict=verdict,
            reasons=reasons,
            score=score
        ))

    # optional dossier file
    dossier_links = None
    if req.create_dossier:
        outdir = Path("dossiers"); outdir.mkdir(exist_ok=True)
        did = uuid.uuid4().hex[:8]
        payload = {
            "id": did,
            "title": req.cluster_title or "Auto Dossier",
            "analyst": req.analyst,
            "created_at": iso(now_utc()),
            "summary": {
                "fake_count": sum(1 for x in items if x.verdict=="FAKE_DISINFORMATION"),
                "opsec_count": sum(1 for x in items if x.verdict=="SENSITIVE_OPSEC"),
                "total": len(items),
            },
            "items": [i.dict() for i in items],
            "evidence_posts": req.posts,
        }
        json_path = outdir / f"dossier_{did}.json"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # (If you later add PDF generation, attach here)
        dossier_links = {
            "json_url": f"/dossiers/dossier_{did}.json",
            "pdf_url": None
        }

    return {
        "items": [i.dict() for i in items],
        "dossier_links": dossier_links
    }

# Static serve dossiers (so the link works)
from fastapi.staticfiles import StaticFiles
app.mount("/dossiers", StaticFiles(directory="dossiers"), name="dossiers")

@app.get("/")
def root():
    return {"message": "Chimera Hybrid v1.5. See /docs", "ok": True}
