from __future__ import annotations

import json

# -------------------------
# Ingredient labels (normalized id -> display)
# -------------------------
INGREDIENT_LABELS = {
  "coca_cola": "Coca-Cola",
  "red_bull": "Red Bull",
  "ginger_ale": "Ginger Ale",
  "orange_juice": "Orange Juice",
  "sprite": "Sprite",
  "water": "Water",
  "lemonade": "Lemonade",
  "water": "Splash of Water",
  "sprite": "Splash of Sprite",
}

def pretty_ingredient(ing: str) -> str:
    if not ing:
        return ""
    return INGREDIENT_LABELS.get(ing, ing.replace("_"," ").title())
from collections import Counter
from pathlib import Path
from string import Template

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

from app.core.auth import current_user
from app.core.storage import ensure_drinks_file, load_drinks, load_orders, load_activity_log, push_activity_event
from app.ml.recommender import recommend_for_user

router = APIRouter()

class ActivityBody(BaseModel):
    type: str
    drinkName: str
    qty: int = 1

@router.get('/api/activity')
def api_activity_feed():
    raw = load_activity_log() or []
    items = []
    for it in raw[:12]:
        if not isinstance(it, dict):
            continue
        items.append({
            'type': 'remove' if str(it.get('type') or '').lower() == 'remove' else 'add',
            'name': str(it.get('name') or 'Drink'),
            'qty': max(1, int(it.get('qty') or 1)),
            'ts': it.get('ts'),
            'timeLabel': '',
        })
    return JSONResponse({'ok': True, 'items': items})


@router.post('/api/activity')
def api_activity_push(body: ActivityBody):
    entry = push_activity_event(body.type, body.drinkName, body.qty)
    return JSONResponse({'ok': True, 'item': {
        'type': entry.get('type'),
        'name': entry.get('name'),
        'qty': entry.get('qty'),
        'ts': entry.get('ts'),
        'timeLabel': '',
    }})


# ---- Read the SAME orders.json used by orders_routes.py ----
REPO_ROOT = Path(__file__).resolve().parents[2]  # app/routers -> app -> repo_root
DATA_DIR = REPO_ROOT / "data"
ORDERS_FILE = DATA_DIR / "orders.json"


def _load_orders_shared():
    """Load orders written by /checkout."""
    return load_orders()


STYLE = """
<style>
*{box-sizing:border-box}
body{
  margin:0; padding:0;
  font-family: "Playfair Display", serif;
  background:#000;
  background-image:url('/static/background-1.png');
  background-size:cover;
  background-position:center;
  background-repeat:no-repeat;
  background-attachment:fixed;
  color:#1f130d;
}
a{color:#f5e6d3}
.page{max-width:1100px;margin:0 auto;padding:40px 20px 60px}
h1{
  font-size:46px; letter-spacing:3px;
  text-align:center; margin:0 0 6px;
  color:#f5e6d3;
  text-shadow:0 0 10px rgba(245,230,211,.65),
             0 0 22px rgba(245,230,211,.45),
             0 0 34px rgba(255,190,130,.25);
}
.grid{display:grid;gap:14px}
.cards{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.card{
  background:rgba(0,0,0,.55);
  border:1px solid rgba(245,230,211,.25);
  border-radius:18px;
  padding:18px;
  box-shadow:0 10px 30px rgba(0,0,0,.35);
}
.card.selected{
  border-color: rgba(255,190,130,.65);
  box-shadow: 0 0 0 1px rgba(255,190,130,.25), 0 14px 36px rgba(0,0,0,.45);
}
.card h2{margin:0 0 10px;color:#f5e6d3;letter-spacing:2px}
.btnrow{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.corner-actions{position:fixed;top:24px;left:0;right:0;pointer-events:none;z-index:50}
.corner{pointer-events:auto;position:fixed;top:24px}
.corner.left{left:24px}
.corner.right{right:24px}
@media(max-width:520px){.corner.left{left:14px}.corner.right{right:14px}.corner{top:14px}}

.menu-popup{
  position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);
  min-width:min(90vw,360px);max-width:min(92vw,460px);
  padding:14px 18px;border-radius:16px;
  background:rgba(12,12,12,.92);color:#f5e6d3;
  border:1px solid rgba(245,230,211,.24);
  box-shadow:0 18px 40px rgba(0,0,0,.42);
  text-align:center;font-size:16px;font-weight:700;letter-spacing:.3px;
  opacity:0;pointer-events:none;transition:opacity .18s ease, transform .18s ease;
  z-index:9999;
}
.menu-popup.show{opacity:1;transform:translateX(-50%) translateY(0)}


button,.primary,.secondary{
  appearance:none;border:0;cursor:pointer;
  padding:12px 14px;border-radius:14px;
  font-family:inherit;
  font-weight:700;
  letter-spacing:1px;
}
button[disabled]{opacity:.45;cursor:not-allowed;filter:saturate(.6)}
.btn-active{background:#f5e6d3;color:#1f130d}
.primary{background:#f5e6d3;color:#1f130d}
.secondary{background:rgba(0,0,0,.35);color:#f5e6d3;border:1px solid rgba(245,230,211,.25);text-decoration:none;display:inline-block}
.small{color:rgba(245,230,211,.85)}
hr{border:0;border-top:1px solid rgba(245,230,211,.18);margin:14px 0}
.table{width:100%;border-collapse:collapse;margin-top:10px}
.table th,.table td{border-bottom:1px solid rgba(245,230,211,.18);padding:10px 8px;color:#f5e6d3;text-align:left}
.table th{color:rgba(245,230,211,.92)}
.pill{display:inline-block;padding:6px 10px;border-radius:999px;background:rgba(245,230,211,.12);border:1px solid rgba(245,230,211,.18);color:#f5e6d3;font-size:12px}
.qty-pill{min-width:44px;text-align:center;display:inline-flex;align-items:center;justify-content:center}
.ing{margin-top:10px;color:rgba(245,230,211,.9)}
.ing ul{margin:8px 0 0 18px;padding:0}
.ing li{margin:4px 0;color:rgba(245,230,211,.85)}

/* --- ETA live countdown bar --- */
.etaBox{
  margin-top:12px;
  padding:12px 14px;
  border:1px solid rgba(245,230,211,.25);
  border-radius:14px;
  background:rgba(0,0,0,.35);
  color:#f5e6d3;
}
.etaTop{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.etaLabel{letter-spacing:.14em;font-weight:700;font-size:12px;opacity:.9}
.etaText{font-size:14px;opacity:.95}
.etaBarBg{
  margin-top:10px;
  height:10px;
  border-radius:999px;
  background:rgba(245,230,211,.18);
  overflow:hidden;
}
.etaBarFill{
  height:100%;
  border-radius:999px;
  background:rgba(245,230,211,.85);
  transition:width .35s linear;
}



/* Queue: per-drink ETA rows */
.orderRow{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:18px;
  margin-top:14px;
}
.orderTitle{
  font-weight:700;
  font-size:22px;
  letter-spacing:.2px;
}
.orderMeta{
  opacity:.9;
  font-size:16px;
  line-height:1.35;
  margin-top:4px;
}
.orderEta{
  text-align:right;
  min-width:180px;
  font-size:18px;
  opacity:.95;
  white-space:nowrap;
}

/* Separate top-left buttons (History + Logout) */
.corner.left{left:18px;}
.corner.left2{left:138px;}


.btn.secondary{background:transparent;color:#f5e6d3;border:1px solid rgba(245,230,211,.35)}

/* ===== Mood Buttons Glow ===== */
.mood-btn{position:relative;transition:transform .12s, box-shadow .18s, border-color .18s}
.mood-btn.active{
 border-color:rgba(80,160,255,.95)!important;
 box-shadow:0 0 0 3px rgba(80,160,255,.55),0 0 18px rgba(80,160,255,.85),0 0 42px rgba(80,160,255,.55);
 transform:translateY(-1px)
}
.mood-btn:hover{transform:translateY(-1px);box-shadow:0 0 14px rgba(80,160,255,.25)}

/* ===== Checkout Button Glow ===== */
.checkout-btn{position:relative;transition:transform .12s, box-shadow .22s}
.checkout-btn:hover{
 transform:translateY(-1px);
 box-shadow:0 0 0 2px rgba(80,160,255,.35),0 0 18px rgba(80,160,255,.55),0 0 44px rgba(80,160,255,.35)
}
.checkout-btn:active{
 transform:translateY(0) scale(.98);
 box-shadow:0 0 12px rgba(80,160,255,.35)
}


/* ===== Force top-right Checkout placement ===== */
.corner{position:fixed;top:18px;z-index:9999}
.corner.right{right:18px;left:auto}
.corner.left{left:18px;right:auto}

/* ===== Checkout click feedback ===== */
.checkout-btn.loading{
  opacity:0.85;
  pointer-events:none;
  transform:translateY(0) scale(0.98);
}
.checkout-btn.loading::before{
  content:"";
  display:inline-block;
  width:10px;height:10px;
  margin-right:8px;
  border:2px solid rgba(80,160,255,.55);
  border-top-color:rgba(80,160,255,1);
  border-radius:50%;
  animation:spin .7s linear infinite;
  vertical-align:middle;
}
@keyframes spin{to{transform:rotate(360deg)}}


/* ===== Ensure Checkout always clickable & visible ===== */
.corner{position:fixed;top:18px;z-index:99999}
.corner.right{right:18px;left:auto}
.checkout-btn{cursor:pointer;pointer-events:auto}
.checkout-btn.clicked{transform:translateY(1px) scale(.97)}



.voice-panel{
  display:flex;
  align-items:center;
  gap:12px;
  flex-wrap:wrap;
  margin: 10px 0 18px 0;
}
.voice-btn{
  appearance:none;
  border:1px solid rgba(255,255,255,.20);
  background: rgba(0,0,0,.35);
  color:#f5e6d3;
  border-radius:14px;
  padding:12px 16px;
  cursor:pointer;
  font-weight:700;
  letter-spacing:.02em;
  transition:transform .12s, box-shadow .18s, border-color .18s, opacity .18s;
}
.voice-btn:hover{
  transform:translateY(-1px);
  box-shadow:0 0 14px rgba(80,160,255,.25);
  border-color:rgba(80,160,255,.55);
}
.voice-btn.active{
  border-color:rgba(80,160,255,.95)!important;
  box-shadow:0 0 0 3px rgba(80,160,255,.35),0 0 18px rgba(80,160,255,.55),0 0 44px rgba(80,160,255,.35);
}
.voice-hint{
  opacity:.86;
  max-width:740px;
}

.voice-float{
  position:fixed;
  right:18px;
  top:86px;
  z-index:100000;
  display:flex;
  align-items:center;
  gap:10px;
  flex-wrap:wrap;
  max-width:min(520px, 92vw);
}
.voice-float .voice-btn{
  background:rgba(10,18,28,.92);
  border-color:rgba(80,160,255,.85);
  box-shadow:0 0 0 2px rgba(80,160,255,.25),0 0 18px rgba(80,160,255,.28);
}
.voice-float .voice-hint{
  background:rgba(0,0,0,.58);
  border:1px solid rgba(255,255,255,.14);
  border-radius:14px;
  padding:10px 12px;
}
@media (max-width: 900px){
  .voice-float{top:74px; left:18px; right:18px}
}
.voice-badge{
  display:inline-block;
  margin-left:8px;
  padding:4px 10px;
  border-radius:999px;
  border:1px solid rgba(255,255,255,.14);
  background:rgba(255,255,255,.05);
  font-size:12px;
}
.activity-panel{
  position:fixed;
  right:18px;
  top:150px;
  z-index:99990;
  width:min(320px, 34vw);
  min-width:240px;
  background:rgba(6,12,20,.78);
  backdrop-filter:blur(10px);
  border:1px solid rgba(255,255,255,.12);
  border-radius:18px;
  padding:14px 16px;
  box-shadow:0 16px 40px rgba(0,0,0,.28);
  color:#ffffff;
}
.activity-panel, .activity-panel *{color:#ffffff}

.activity-title{font-size:13px;letter-spacing:.12em;text-transform:uppercase;opacity:.75;margin-bottom:10px;font-weight:800}
.activity-live{margin-bottom:12px;padding:12px 12px;border-radius:14px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08)}
.activity-live-label{font-size:11px;letter-spacing:.12em;text-transform:uppercase;opacity:.68;margin-bottom:6px;font-weight:800}
.activity-live-name{font-size:18px;font-weight:900;line-height:1.15}
.activity-live-meta{font-size:12px;opacity:.74;margin-top:4px}
.activity-list{display:flex;flex-direction:column;gap:8px}
.activity-item{display:flex;align-items:center;gap:10px;border-radius:12px;padding:10px 12px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)}
.activity-badge{min-width:28px;height:28px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;font-weight:900;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.10)}
.activity-item.add .activity-badge{color:#9ef0bc}
.activity-item.remove .activity-badge{color:#ffb0b0}
.activity-text{font-weight:800}
.activity-meta{font-size:12px;opacity:.7;margin-top:2px}
.activity-empty{opacity:.66;font-size:14px}
@media (max-width: 900px){
  .activity-panel{top:150px; right:16px; width:min(280px, 62vw); min-width:0}
}
@media (max-width: 700px){
  .activity-panel{left:16px; right:16px; top:auto; bottom:110px; width:auto}
}

/* --- Drink search bar --- */
.drink-search-wrap{
  display:flex;
  gap:10px;
  align-items:center;
  margin: 14px 0 18px 0;
}
#drinkSearch{
  flex:1;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.18);
  background: rgba(0,0,0,0.35);
  color: rgba(255,255,255,0.92);
  font-size: 16px;
  outline: none;
}
#drinkSearch::placeholder{ color: rgba(255,255,255,0.55); }
#drinkSearch:focus{
  border-color: rgba(255,255,255,0.35);
  box-shadow: 0 0 0 3px rgba(255,255,255,0.10);
}
#drinkSearchClear{
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.18);
  background: rgba(0,0,0,0.35);
  color: rgba(255,255,255,0.80);
  cursor: pointer;
}
#drinkSearchClear:hover{ border-color: rgba(255,255,255,0.30); }

.why{ margin-top:10px; }
.why summary{ cursor:pointer; list-style:none; }
.why summary::-webkit-details-marker{ display:none; }
.why summary:after{ content:" ▼"; opacity:0.8; }
.why[open] summary:after{ content:" ▲"; }
.why ul{ margin:6px 0 0 18px; padding:0; }


/* --- Demo readability + subtle glow --- */
#recBanner{
  color:#ffffff !important;
  font-weight:700;
  text-shadow: 0 0 6px rgba(255,255,255,0.45), 0 0 14px rgba(255,210,160,0.25);
}
details.why summary{
  color:#ffffff !important;
  font-weight:600;
  text-shadow: 0 0 4px rgba(255,255,255,0.35);
}
details.why ul li{
  color:#ffffff !important;
  opacity:1 !important;
  text-shadow: 0 0 3px rgba(255,255,255,0.25);
}


.ing-match{
  font-weight:700;
  color:#fff;
  text-shadow:0 0 6px rgba(255,255,255,.5),0 0 14px rgba(255,215,150,.25);
}
</style>
"""


def _require_user(request: Request):
    return current_user(request)


def _top_drinks_for_user(username: str, limit: int = 3):
    # IMPORTANT: use shared orders file (same one /checkout writes)
    orders = _load_orders_shared()
    c = Counter()
    for o in orders:
        if str(o.get("username")) == str(username):
            c[str(o.get("drinkName", ""))] += int(o.get("quantity", 1) or 1)
    return [name for name, _ in c.most_common(limit) if name]


def _find_drink(drink_id: str):
    ensure_drinks_file()
    for d in load_drinks():
        if d.get("id") == drink_id:
            return d
    return None




@router.get('/guest')
def guest_login(request: Request):
    # Guest session: recommendations remain default (non-personalized)
    request.session['user'] = 'guest'
    request.session['is_guest'] = True
    return RedirectResponse(url='/', status_code=302)


@router.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse("/builder" if current_user(request) else "/login", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    return HTMLResponse(f"""
    <html><head><title>Dashboard</title>{STYLE}</head>
    <body><div class='page'>
      <h1>DASHBOARD</h1>
      <div style='text-align:center; margin-bottom:14px;'>
        <span class='pill'>Welcome, {user}</span>
      </div>

      <div class='grid cards'>
        <div class='card'>
          <h2>HISTORY</h2>
          <div class='small'>See what you ordered before.</div>
          <div class='btnrow'>
            <button class='secondary' onclick="window.location.href='/history'">View History</button>
          </div>
        </div>

        <div class='card'>
          <h2>RECOMMEND</h2>
          <div class='small'>New drink suggestions.</div>
          <div class='btnrow'>
            <button class='secondary' onclick="window.location.href='/recommendations'">See Recommendations</button>
          </div>
        </div>


      </div>

      <div class='btnrow' style='margin-top:14px'>
        <button class='secondary' onclick="window.location.href='/logout'">Logout</button>
      </div>
    </div></body></html>
    """)


@router.get("/menu", response_class=HTMLResponse)
def menu_alias(request: Request):
    return RedirectResponse("/builder", status_code=302)


@router.get("/builder", response_class=HTMLResponse)
@router.get("/builder/", response_class=HTMLResponse)
def builder(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ensure_drinks_file()

    tpl = Template(r"""
<html><head><title>Builder</title>$STYLE</head>
<body><div class='page'>
  <h1>Tipsy</h1>
  <div class='card'>
    <h2>RECOMMENDED FOR YOU</h2>
    <div class='small'>What are you in the mood for?</div>
    <div class='btnrow' style='margin-top:10px'>
      <button class='secondary mood-btn' data-mood='chill' onclick="pickMood('chill')">Chill</button>
      <button class='secondary mood-btn' data-mood='energized' onclick="pickMood('energized')">Energized</button>
      <button class='secondary mood-btn' data-mood='sweet' onclick="pickMood('sweet')">Sweet</button>
      <button class='secondary mood-btn' data-mood='adventurous' onclick="pickMood('adventurous')">Adventurous</button>
      <button class='secondary mood-btn' data-mood='none' onclick="pickMood('none')">None</button>
      <span id='moodLabel' class='pill' style='margin-left:10px; opacity:.9'>Mood: none</span>
    </div>

    <div id='recBanner' class='card' style='display:none; margin-top:12px; padding:12px'></div>
    <div id='recs' class='grid cards' style='margin-top:14px'></div>
    <hr/>
    <h2>MENU</h2>

    <div class='small'>Pick drinks and quantities. </div>
    
      <div class="drink-search-wrap">
        <input id="drinkSearch" type="text" placeholder="Search drinks (name or ingredient)..." autocomplete="off" />
        <button id="drinkSearchClear" type="button" aria-label="Clear search">✕</button>
      </div>
<div id='menu' class='grid cards' style='margin-top:14px'></div>

    <hr/>
    <h2>CART</h2>
    <div id='cart' class='small'>No items yet.</div>
    <div id='status' class='small' style='margin-top:10px'></div>
    <div id='etaBox' class='etaBox' style='display:none;'>
      <div class='etaTop'>
        <div class='etaLabel'>ETA</div>
        <div id='etaText' class='etaText'>--</div>
      </div>
      <div class='etaBarBg'>
        <div id='etaBarFill' class='etaBarFill' style='width:0%'></div>
      </div>
    
    <div id='myQueueBox' class='etaBox' style='margin-top:16px;'>
      <div class='etaTop'>
        <div class='etaLabel'>Your Active Orders</div>
        <div class='etaText small' style='opacity:.8'>Live queue + ETAs (first-come, first-serve)</div>
      </div>
      <div id='myQueue' class='small' style='margin-top:10px;'>Loading…</div>
    </div>

</div>

  </div>

  <div class='corner-actions'>
    <a class='secondary corner left' href='/history'>History</a>
    <a class='secondary corner left2' href='/logout'>Logout</a>
    <button id='checkoutBtn' class='primary corner right checkout-btn' type='button'>Checkout</button>
  </div>

  <aside id='activityPanel' class='activity-panel'>
    <div class='activity-title'>BMO Activity</div>
    <div id='activityLive' class='activity-live'>
      <div class='activity-live-label'>Now making</div>
      <div id='activityNowMaking' class='activity-live-name'>No drink in progress</div>
      <div id='activityNowMakingMeta' class='activity-live-meta'>Waiting for orders.</div>
    </div>
    <div id='activityList' class='activity-list'>
      <div class='activity-empty'>No drink changes yet.</div>
    </div>
  </aside>

<script>



function normalizeVoiceText(s){
  return String(s || '')
    .toLowerCase()
    .replace(/[&]/g, ' and ')
    .replace(/[_-]/g, ' ')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\bcheck\s*out\b/g, ' checkout ')
    .replace(/\bcheck\s*it\s*out\b/g, ' checkout ')
    .replace(/\bpls\b/g, ' please ')
    .replace(/\bim\b/g, ' i am ')
    .replace(/\s+/g, ' ')
    .trim();
}

const VOICE_FILLER_WORDS = new Set([
  'hey','bmo','please','can','you','i','want','would','like','get','me','a','an','the','to',
  'order','make','give','put','in','cart','for','now','drink','one','two','three','four','five',
  'six','seven','eight','nine','ten','my','some','of'
]);

const TOKEN_CANONICAL = {
  face:'fizz', fish:'fizz', fishes:'fizz', fees:'fizz', fits:'fizz', fists:'fizz', fizzy:'fizz', fiz:'fizz', this:'fizz',
  voltige:'voltage', volta:'voltage', voltagee:'voltage'
};

function canonicalToken(tok){
  const t = String(tok || '').trim();
  if(!t) return '';
  return TOKEN_CANONICAL[t] || t;
}

function tokenizeVoice(text, dropFillers=false){
  const raw = normalizeVoiceText(text).split(' ').filter(Boolean).map(canonicalToken).filter(Boolean);
  return dropFillers ? raw.filter(t => !VOICE_FILLER_WORDS.has(t)) : raw;
}

function voiceNumberFromText(text){
  const t = normalizeVoiceText(text);
  const map = {
    'one':1,'a':1,'an':1,'two':2,'three':3,'four':4,'five':5,
    'six':6,'seven':7,'eight':8,'nine':9,'ten':10
  };
  const m = t.match(/\b(\d+|one|a|an|two|three|four|five|six|seven|eight|nine|ten)\b/);
  if(!m) return 1;
  const raw = m[1];
  return /^\d+$/.test(raw) ? Math.max(1, parseInt(raw,10)) : (map[raw] || 1);
}

function setVoiceUi(active, label){
  const btn = document.getElementById('voiceBtn');
  const badge = document.getElementById('voiceBadge');
  const hint = document.getElementById('voiceHint');
  if(btn){
    btn.classList.toggle('active', !!active);
    btn.textContent = active ? 'Stop Voice Ordering' : 'Start Voice Ordering';
  }
  if(badge) badge.textContent = label || (active ? 'Listening...' : 'Voice off');
  if(hint && label && active) hint.dataset.last = label;
}

let __speechUnlocked = false;
let __menuLastAnnouncementKey = '';
let __bmoSpeechQueue = [];
let __bmoSpeaking = false;
let __lastGestureAt = 0;

function pickBmoVoice(){
  try{
    const voices = window.speechSynthesis ? (window.speechSynthesis.getVoices() || []) : [];
    return voices.find(v => /samantha|google us english|alex|english/i.test(v.name || '')) || null;
  }catch(_e){ return null; }
}

function runBmoSpeechQueue(){
  try{
    if(__bmoSpeaking || !__bmoSpeechQueue.length || !('speechSynthesis' in window)) return;
    __bmoSpeaking = true;
    const next = String(__bmoSpeechQueue.shift() || '').trim();
    if(!next){ __bmoSpeaking = false; return; }
    try{ window.speechSynthesis.resume(); }catch(_e){}
    const u = new SpeechSynthesisUtterance(next);
    try{ window.speechSynthesis.cancel(); }catch(_e){}
    u.lang = 'en-US';
    u.rate = 1;
    u.pitch = 1.02;
    u.volume = 1;
    const preferred = pickBmoVoice();
    if(preferred) u.voice = preferred;
    u.onend = () => { __bmoSpeaking = false; setTimeout(runBmoSpeechQueue, 120); };
    u.onerror = () => { __bmoSpeaking = false; setTimeout(runBmoSpeechQueue, 120); };
    window.speechSynthesis.speak(u);
  }catch(_e){ __bmoSpeaking = false; }
}

function speakImmediately(text){
  try{
    if(!('speechSynthesis' in window)) return false;
    const msg = String(text || '').trim();
    if(!msg) return false;
    unlockBmoSpeech();
    const u = new SpeechSynthesisUtterance(msg);
    u.lang = 'en-US';
    u.rate = 1;
    u.pitch = 1.02;
    u.volume = 1;
    const preferred = pickBmoVoice();
    if(preferred) u.voice = preferred;
    try{ window.speechSynthesis.cancel(); }catch(_e){}
    try{ window.speechSynthesis.resume(); }catch(_e){}
    window.speechSynthesis.speak(u);
    return true;
  }catch(_e){
    return false;
  }
}

let __menuPopupTimer = null;

function showMenuPopup(text){
  try{
    const msg = String(text || '').trim();
    if(!msg) return;
    const el = document.getElementById('menuPopup');
    if(!el){
      window.alert(msg);
      return;
    }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(__menuPopupTimer);
    __menuPopupTimer = setTimeout(() => {
      el.classList.remove('show');
    }, 5000);
  }catch(_e){}
}

function bmoSay(text, flush=false, fromGesture=false){
  try{
    const msg = String(text || '').trim();
    if(!msg) return;
    showMenuPopup(msg);
  }catch(_e){}
}

function unlockBmoSpeech(){ return; /* disabled on menu */
  if(__speechUnlocked || !('speechSynthesis' in window)) return;
  __speechUnlocked = true;
  try{
    window.speechSynthesis.getVoices();
    window.speechSynthesis.resume();
  }catch(_e){}
}

function noteUserGesture(){}
['pointerdown','click','touchstart','keydown'].forEach(evt => {
  window.addEventListener(evt, noteUserGesture, {passive:true, capture:true});
});

function levenshteinDistance(a, b){
  a = String(a || '');
  b = String(b || '');
  if(a === b) return 0;
  if(!a.length) return b.length;
  if(!b.length) return a.length;
  const dp = Array.from({length: a.length + 1}, () => new Array(b.length + 1).fill(0));
  for(let i=0;i<=a.length;i++) dp[i][0] = i;
  for(let j=0;j<=b.length;j++) dp[0][j] = j;
  for(let i=1;i<=a.length;i++){
    for(let j=1;j<=b.length;j++){
      const cost = a[i-1] === b[j-1] ? 0 : 1;
      dp[i][j] = Math.min(dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost);
    }
  }
  return dp[a.length][b.length];
}

function normalizedSimilarity(a, b){
  a = normalizeVoiceText(a);
  b = normalizeVoiceText(b);
  if(!a || !b) return 0;
  if(a === b) return 1;
  if(a.includes(b) || b.includes(a)){
    const shorter = Math.min(a.length, b.length);
    const longer = Math.max(a.length, b.length);
    return Math.max(0.86, shorter / Math.max(1, longer));
  }
  const dist = levenshteinDistance(a, b);
  return 1 - (dist / Math.max(a.length, b.length, 1));
}

function soundexToken(token){
  const t = canonicalToken(String(token || '').toLowerCase().replace(/[^a-z]/g, ''));
  if(!t) return '';
  const map = {b:1,f:1,p:1,v:1,c:2,g:2,j:2,k:2,q:2,s:2,x:2,z:2,d:3,t:3,l:4,m:5,n:5,r:6};
  const first = t[0];
  let out = first;
  let prev = map[first] || 0;
  for(let i=1;i<t.length;i++){
    const code = map[t[i]] || 0;
    if(code && code !== prev) out += String(code);
    prev = code;
  }
  return (out + '000').slice(0,4);
}

function tokenOverlapScore(aTokens, bTokens){
  if(!aTokens.length || !bTokens.length) return 0;
  const aSet = new Set(aTokens), bSet = new Set(bTokens);
  let overlap = 0;
  aSet.forEach(tok => { if(bSet.has(tok)) overlap += 1; });
  return overlap / Math.max(aSet.size, bSet.size, 1);
}

function phoneticOverlapScore(aTokens, bTokens){
  if(!aTokens.length || !bTokens.length) return 0;
  const aCodes = aTokens.map(soundexToken).filter(Boolean);
  const bCodes = new Set(bTokens.map(soundexToken).filter(Boolean));
  let overlap = 0;
  aCodes.forEach(code => { if(bCodes.has(code)) overlap += 1; });
  return overlap / Math.max(aCodes.length, bTokens.length, 1);
}

function orderedTokenScore(aTokens, bTokens){
  if(!aTokens.length || !bTokens.length) return 0;
  let j = 0;
  for(let i=0;i<aTokens.length && j < bTokens.length;i++) if(aTokens[i] === bTokens[j]) j += 1;
  return j / Math.max(aTokens.length, bTokens.length, 1);
}

function buildDrinkVoiceAliases(drink){
  const aliases = new Set();
  const add = (v) => {
    const n = normalizeVoiceText(v);
    if(n) aliases.add(n);
  };
  const name = normalizeVoiceText(drink && (drink.name || drink.id || ''));
  const idName = normalizeVoiceText(String(drink && drink.id || '').replace(/_/g, ' '));
  if(name) add(name);
  if(idName) add(idName);
  if(name){
    [`add ${name}`, `order ${name}`, `get ${name}`, `make ${name}`, `i want ${name}`, `i would like ${name}`, `one ${name}`].forEach(add);
  }
  const words = tokenizeVoice(name, true);
  if(words.includes('fizz')) ['face','fish','fees','fits','fists','fizzy','fiz','this'].forEach(v => add(name.replace(/fizz/g, v)));
  if(words.includes('voltage')) { add(name.replace(/voltage/g, 'voltige')); add(name.replace(/voltage/g, 'volta')); }
  if((drink && drink.id) === 'sparkling_citrus_mix') ['sparkling citrus','sparkling mix','sparkle citrus mix'].forEach(add);
  if((drink && drink.id) === 'energy_sunrise') ['energy sun rise','sunrise energy'].forEach(add);
  if((drink && drink.id) === 'base_coca_cola') ['coca cola','coke'].forEach(add);
  return Array.from(aliases);
}

function scorePhraseToAlias(phrase, alias){
  const q = normalizeVoiceText(phrase);
  const a = normalizeVoiceText(alias);
  const qTokens = tokenizeVoice(q, true);
  const aTokens = tokenizeVoice(a, true);
  const qJoined = qTokens.join(' ');
  const aJoined = aTokens.join(' ');
  if(!qJoined || !aJoined) return 0;
  if(qJoined === aJoined) return 1;
  if(qJoined.includes(aJoined) || aJoined.includes(qJoined)) return 0.98;
  const sim = Math.max(normalizedSimilarity(qJoined, aJoined), normalizedSimilarity(q, a));
  const tokenScore = tokenOverlapScore(qTokens, aTokens);
  const phonetic = phoneticOverlapScore(qTokens, aTokens);
  const ordered = orderedTokenScore(qTokens, aTokens);
  return Math.max(sim * 0.62 + tokenScore * 0.20 + phonetic * 0.12 + ordered * 0.06, tokenScore * 0.72 + phonetic * 0.28, sim);
}

function bestDrinkVoiceCandidate(phrase){
  let best = null;
  let bestScore = 0;
  (drinks || []).forEach(d => {
    buildDrinkVoiceAliases(d).forEach(alias => {
      const score = scorePhraseToAlias(phrase, alias);
      if(score > bestScore){ bestScore = score; best = d; }
    });
  });
  return {drink: best, score: bestScore};
}

function showVoiceSuggestion(drink, qty, action, heardText=''){
  const status = document.getElementById('status');
  if(!status || !drink) return;
  const safeAction = action === 'remove' ? 'remove' : 'add';
  const safeQty = Math.max(1, parseInt(qty || 1, 10));
  const heard = heardText ? `<div style="margin-top:8px;opacity:.75;font-size:12px">Heard: ${String(heardText).replace(/[<>&]/g,'')}</div>` : '';
  status.innerHTML = `Did you mean <button type="button" class="secondary" style="padding:6px 10px; margin-left:6px" onclick="confirmVoiceSuggestion('${drink.id}', ${safeQty}, '${safeAction}')">${drink.name}</button>?${heard}`;
}

function confirmVoiceSuggestion(drinkId, qty, action){
  const drink = (drinks || []).find(d => d.id === drinkId);
  if(!drink) return;
  if(action === 'remove') removeDrinkByVoice(drink, qty);
  else addDrinkByVoice(drink, qty);
}
window.confirmVoiceSuggestion = confirmVoiceSuggestion;

function findDirectDrinkFromVoice(phrase){
  const q = normalizeVoiceText(phrase);
  if(!q) return null;
  let exact = null;
  let contains = null;
  let containsLen = 0;
  (drinks || []).forEach(d => {
    buildDrinkVoiceAliases(d).forEach(alias => {
      const a = normalizeVoiceText(alias);
      if(!a) return;
      if(q === a) exact = d;
      else if((q.includes(a) || a.includes(q)) && a.length > containsLen){ contains = d; containsLen = a.length; }
    });
  });
  return exact || contains || null;
}

function findDrinkFromVoice(phrase){
  const direct = findDirectDrinkFromVoice(phrase);
  if(direct) return direct;
  const match = bestDrinkVoiceCandidate(phrase);
  return match.score >= 0.58 ? match.drink : null;
}

function findDrinkSuggestion(phrase){
  const match = bestDrinkVoiceCandidate(phrase);
  if(match.score >= 0.38 && match.score < 0.58) return match.drink;
  return null;
}

function recognizeVoiceIntent(text){
  const q = normalizeVoiceText(text).replace(/^hey\s+bmo\s*/,'').replace(/^bmo\s*/,'').replace(/^please\s*/,'').trim();
  const commandAliases = {
    checkout: ['checkout','check out','check it out','place order','submit order','finish order','complete order','go to checkout','proceed to checkout','order now'],
    clear_cart: ['clear cart','empty cart','cancel order','remove all drinks','delete cart','remove everything','remove all','remove all from cart','clear everything','empty everything','delete everything'],
    history: ['history','show history','open history','go to history']
  };
  let bestCmd = null;
  let bestScore = 0;
  Object.entries(commandAliases).forEach(([cmd, aliases]) => {
    aliases.forEach(alias => {
      const score = scorePhraseToAlias(q, alias);
      if(score > bestScore){ bestScore = score; bestCmd = cmd; }
    });
  });
  return bestScore >= 0.62 ? bestCmd : null;
}

let activityLog = [];
let activityLiveSnapshot = null;
let activityLiveTimer = null;
let activityPollTimer = null;
function syncActivityToServer(type, drinkName, qty){
  try{
    fetch('/api/activity', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({type, drinkName, qty})
    }).catch(() => {});
  }catch(_e){}
}

async function loadSharedActivity(){
  try{
    const res = await fetch('/api/activity', {cache:'no-store'});
    const data = await res.json();
    if(!data || !data.ok || !Array.isArray(data.items)) return;
    activityLog = (data.items || []).slice(0, 6).map(item => ({
      type: item.type === 'remove' ? 'remove' : 'add',
      name: String(item.name || 'Drink'),
      qty: Math.max(1, parseInt(item.qty || 1, 10)),
      ts: String(item.ts || ''),
      timeLabel: String(item.timeLabel || '')
    }));
    renderActivity();
  }catch(_e){}
}

function startSharedActivityRefresh(){
  if(activityPollTimer) clearInterval(activityPollTimer);
  loadSharedActivity();
  activityPollTimer = setInterval(() => { if(document.hidden) return; loadSharedActivity(); }, 1200);
}


function renderActivityLive(){
  const nameEl = document.getElementById('activityNowMaking');
  const metaEl = document.getElementById('activityNowMakingMeta');
  if(!nameEl || !metaEl) return;
  const snap = activityLiveSnapshot || {};
  if(snap.flushing){
    nameEl.textContent = 'Flushing tube';
    metaEl.textContent = 'Cleaning in progress.';
    return;
  }
  if(snap.flushRequired){
    nameEl.textContent = 'Waiting for flush';
    metaEl.textContent = snap.lastDone && snap.lastDone.drinkName ? `${snap.lastDone.drinkName} finished. Press Flush Tube.` : 'Drink finished. Press Flush Tube.';
    return;
  }
  const current = snap.current || null;
  if(current && current.drinkName){
    const step = current.step && current.totalSteps ? `Step ${current.step}/${current.totalSteps}` : 'In progress';
    const ingredient = current.currentIngredient ? ` • ${current.currentIngredient}` : '';
    const eta = Number.isFinite(Number(current.etaThisSeconds)) ? ` • ${formatETA(Number(current.etaThisSeconds))} left` : '';
    nameEl.textContent = current.drinkName;
    metaEl.textContent = `${step}${ingredient}${eta}`;
    return;
  }
  if(snap.queue && snap.queue.length && snap.queue[0].drinkName){
    const next = snap.queue[0];
    nameEl.textContent = `Next: ${next.drinkName}`;
    metaEl.textContent = 'Queued and waiting to start.';
    return;
  }
  nameEl.textContent = 'No drink in progress';
  metaEl.textContent = 'Waiting for orders.';
}

async function loadActivityLive(){
  try{
    const prev = activityLiveSnapshot || null;
    const res = await fetch('/api/live-display', {cache:'no-store'});
    const data = await res.json();
    if(!data || !data.ok) return;
    activityLiveSnapshot = data;
    renderActivityLive();

    const nowCurrent = data.current && data.current.drinkName ? String(data.current.drinkName) : '';
    const prevCurrent = prev && prev.current && prev.current.drinkName ? String(prev.current.drinkName) : '';
    const lastDoneName = data.lastDone && data.lastDone.drinkName ? String(data.lastDone.drinkName) : '';
    const inCompletionWindow = Number((data.lastDone && data.lastDone.secondsAgo) || 999) <= 5;

    if(data.flushRequired && lastDoneName && inCompletionWindow){
      const key = `done:${lastDoneName}`;
      if(__menuLastAnnouncementKey !== key){
        __menuLastAnnouncementKey = key;
        bmoSay(`Your order has been completed. ${lastDoneName} is ready. Please flush the tube.`);
      }
    } else if(data.flushing){
      const key = 'flushing';
      if(__menuLastAnnouncementKey !== key){
        __menuLastAnnouncementKey = key;
        bmoSay('Flushing tube now.');
      }
    } else if(nowCurrent && nowCurrent !== prevCurrent){
      __menuLastAnnouncementKey = `making:${nowCurrent}`;
    } else if(!data.flushRequired && !data.flushing && !nowCurrent){
      __menuLastAnnouncementKey = '';
    }
  }catch(_e){}
}

function startActivityLiveRefresh(){
  if(activityLiveTimer) clearInterval(activityLiveTimer);
  loadActivityLive();
  activityLiveTimer = setInterval(() => {
    if(document.hidden) return;
    loadActivityLive();
  }, 1000);
}

function renderActivity(){
  const list = document.getElementById('activityList');
  if(!list) return;
  if(!activityLog.length){
    list.innerHTML = '<div class="activity-empty">No drink changes yet.</div>';
    return;
  }
  list.innerHTML = activityLog.map(item => `
    <div class="activity-item ${item.type}">
      <span class="activity-badge">${item.type === 'remove' ? '−' : '+'}</span>
      <div>
        <div class="activity-text">${item.type === 'remove' ? 'Removed' : 'Added'} ${item.qty} ${item.name}${item.qty > 1 ? 's' : ''}</div>
        <div class="activity-meta">${item.timeLabel}</div>
      </div>
    </div>
  `).join('');
}

function pushActivity(type, drinkName, qty){
  const safeQty = Math.max(1, parseInt(qty || 1, 10));
  const nowIso = new Date().toISOString();
  activityLog.unshift({
    type: type === 'remove' ? 'remove' : 'add',
    name: String(drinkName || 'Drink'),
    qty: safeQty,
    ts: nowIso,
    timeLabel: new Date().toLocaleTimeString([], {hour:'numeric', minute:'2-digit'})
  });
  activityLog = activityLog.slice(0, 6);
  renderActivity();
  syncActivityToServer(type, drinkName, safeQty);
}

function rerenderAfterVoice(){
  try{ renderCards(filterDrinks()); }catch(_e){}
  try{ renderCart(); }catch(_e){}
}

function addDrinkByVoice(drink, qty){
  qty = Math.max(1, parseInt(qty || 1, 10));
  if(!cart[drink.id]) cart[drink.id] = {drinkId:drink.id, drinkName:drink.name, quantity:0, calories: drink.calories || 0};
  cart[drink.id].quantity += qty;
  rerenderAfterVoice();
  pushActivity('add', drink.name, qty);
  const status = document.getElementById('status');
  if(status) status.innerHTML = `Added <strong>${qty} ${drink.name}${qty>1?'s':''}</strong>.<div style="margin-top:8px;opacity:.75;font-size:12px">Recent action: added ${qty} ${drink.name}${qty>1?'s':''}</div>`;
  bmoSay(`Added ${qty} ${drink.name}`, false, true);
}

function removeDrinkByVoice(drink, qty){
  qty = Math.max(1, parseInt(qty || 1, 10));
  const row = cart[drink.id];
  if(!row){
    const status = document.getElementById('status');
    if(status) status.innerText = `${drink.name} is not in the cart.`;
    bmoSay(`${drink.name} is not in the cart`);
    return;
  }
  row.quantity -= qty;
  if(row.quantity <= 0) delete cart[drink.id];
  rerenderAfterVoice();
  pushActivity('remove', drink.name, qty);
  const status = document.getElementById('status');
  if(status) status.innerHTML = `Removed <strong>${qty} ${drink.name}${qty>1?'s':''}</strong>.<div style="margin-top:8px;opacity:.75;font-size:12px">Recent action: removed ${qty} ${drink.name}${qty>1?'s':''}</div>`;
  bmoSay(`Removed ${qty} ${drink.name}`, false, true);
}

function clearCartByVoice(heardRaw=''){
  cart = {};
  rerenderAfterVoice();
  const status = document.getElementById('status');
  if(status) status.innerText = heardRaw ? `Heard: ${heardRaw} → cart cleared` : 'Cart cleared.';
  bmoSay('Removed everything from the cart');
}

function splitVoiceDrinkSegments(text){
  return String(text || '')
    .split(/\s*(?:,|\band\b|\bplus\b|\bthen\b|\balso\b)\s*/i)
    .map(part => normalizeVoiceText(part).trim())
    .filter(Boolean);
}

function extractLeadingQty(segment){
  const m = normalizeVoiceText(segment).match(/^(\d+|one|a|an|two|three|four|five|six|seven|eight|nine|ten)\b/i);
  return m ? voiceNumberFromText(m[1]) : null;
}

function stripVoiceCommandPrefix(segment){
  return normalizeVoiceText(String(segment || ''))
    .replace(/^(?:hey\s+bmo\s+|bmo\s+|please\s+)/i, '')
    .replace(/^(?:add|get|order|make|remove|delete|take away|take out|i want|i would like|can you add|can you remove)\s+/i, '')
    .trim();
}

function parseSingleVoiceSegment(segment, mode='add'){
  const cleaned = stripVoiceCommandPrefix(segment);
  if(!cleaned) return null;
  const explicitQty = extractLeadingQty(cleaned);
  const candidate = cleaned.replace(/^(\d+|one|a|an|two|three|four|five|six|seven|eight|nine|ten)\b\s*/i, '').trim() || cleaned;
  const qty = explicitQty || 1;
  const drink = findDrinkFromVoice(candidate);
  if(drink) return {kind:'match', drink, qty, text:candidate, mode};
  const suggestion = findDrinkSuggestion(candidate);
  if(suggestion) return {kind:'suggestion', drink:suggestion, qty, text:candidate, mode};
  return {kind:'unknown', qty, text:candidate, mode};
}

function parseVoiceDrinkSegments(text, mode='add'){
  const normalized = normalizeVoiceText(text);
  const body = stripVoiceCommandPrefix(normalized);
  const merged = new Map();

  function addMerged(item){
    const key = `${item.kind}:${item.drink ? item.drink.id : item.text}`;
    if(!merged.has(key)) merged.set(key, item);
    else if(item.kind === 'match' || item.kind === 'suggestion'){
      const cur = merged.get(key);
      cur.qty = Math.max(cur.qty, item.qty);
    }
  }

  const parts = splitVoiceDrinkSegments(normalized);
  if(parts.length > 1){
    parts.map(part => parseSingleVoiceSegment(part, mode)).filter(Boolean).forEach(addMerged);
    return Array.from(merged.values());
  }

  const single = parseSingleVoiceSegment(normalized, mode);
  if(single && single.kind !== 'unknown') return [single];

  let working = ` ${body} `;
  const found = new Map();
  (drinks || []).forEach(drink => {
    const aliases = buildDrinkVoiceAliases(drink).map(a => normalizeVoiceText(a)).filter(Boolean).sort((a,b)=>b.length-a.length);
    let qtyTotal = 0;
    aliases.forEach(alias => {
      const pattern = new RegExp(`(^|\b)(?:(\d+|one|a|an|two|three|four|five|six|seven|eight|nine|ten)\s+)?${escapeVoiceRegex(alias)}(?=\b|$)`, 'ig');
      working = working.replace(pattern, (m, lead, qtyWord) => {
        qtyTotal += qtyWord ? Math.max(1, voiceNumberFromText(qtyWord)) : 1;
        return ' '.repeat(m.length);
      });
    });
    if(qtyTotal > 0) found.set(drink.id, {kind:'match', drink, qty:qtyTotal, text:drink.name, mode});
  });
  if(found.size) return Array.from(found.values());
  return single ? [single] : [];
}

function summarizeVoiceActions(items){
  if(!items.length) return '';
  return items.map(item => `${item.qty} ${item.drink.name}${item.qty > 1 ? 's' : ''}`).join(', ');
}

function handleVoiceCommand(rawText){
  const heardRaw = String(rawText || '').trim();
  let text = normalizeVoiceText(heardRaw);
  if(!text) return false;
  text = text.replace(/^hey\s+bmo\s*/,'').replace(/^bmo\s*/,'').replace(/^please\s*/,'').trim();
  const status = document.getElementById('status');

  const cmd = recognizeVoiceIntent(text);
  if(cmd === 'checkout'){
    const btn = document.getElementById('checkoutBtn');
    if(btn) btn.click();
    if(status) status.innerText = `Heard: ${heardRaw} → checkout`;
    bmoSay('Checking out', true);
    return true;
  }
  if(cmd === 'clear_cart'){ clearCartByVoice(heardRaw); return true; }
  if(cmd === 'history'){ window.location.href = '/history'; return true; }
  if(/\b(remove|delete|take away)\b/.test(text) && /\b(all|everything)\b/.test(text)){ clearCartByVoice(heardRaw); return true; }

  const mode = /\b(remove|delete|take away)\b/.test(text) ? 'remove' : 'add';
  const segments = parseVoiceDrinkSegments(text, mode);
  if(!segments.length) return false;
  const matches = segments.filter(x => x.kind === 'match');
  const suggestions = segments.filter(x => x.kind === 'suggestion');
  const unknown = segments.filter(x => x.kind === 'unknown');

  if(matches.length && !suggestions.length && !unknown.length){
    matches.forEach(item => item.mode === 'remove' ? removeDrinkByVoice(item.drink, item.qty) : addDrinkByVoice(item.drink, item.qty));
    const verb = mode === 'remove' ? 'Removed' : 'Added';
    const summary = summarizeVoiceActions(matches);
    if(status) status.innerHTML = `${verb} <strong>${summary}</strong>.<div style="margin-top:8px;opacity:.75;font-size:12px">Heard: ${heardRaw}</div>`;
    bmoSay(`${verb} ${summary}`);
    return true;
  }

  if(suggestions.length){
    const first = suggestions[0];
    showVoiceSuggestion(first.drink, first.qty, first.mode, heardRaw);
    bmoSay(`Did you mean ${first.drink.name}`);
    return true;
  }

  if(status) status.innerText = `I heard: ${heardRaw}`;
  bmoSay(mode === 'remove' ? 'I could not find that drink' : 'Sorry, I did not understand');
  return false;
}

let voiceRecognition = null;
let voiceListening = false;

function setupVoiceOrdering(){
  const btn = document.getElementById('voiceBtn');
  const status = document.getElementById('status');
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  if(!btn) return;
  if(!SR){
    btn.disabled = true;
    setVoiceUi(false, 'Voice unsupported');
    if(status) status.innerText = 'Voice recognition is not supported in this browser.';
    return;
  }

  voiceRecognition = new SR();
  voiceRecognition.continuous = true;
  voiceRecognition.interimResults = false;
  voiceRecognition.lang = 'en-US';
  try{ voiceRecognition.maxAlternatives = 10; }catch(_e){}

  voiceRecognition.onstart = () => { voiceListening = true; setVoiceUi(true, 'Listening...'); };
  voiceRecognition.onend = () => {
    const shouldRestart = voiceListening;
    setVoiceUi(shouldRestart, shouldRestart ? 'Listening...' : 'Voice off');
    if(shouldRestart){ try{ voiceRecognition.start(); }catch(_e){} }
  };
  voiceRecognition.onerror = (event) => {
    if(event.error === 'not-allowed' || event.error === 'service-not-allowed'){
      voiceListening = false;
      setVoiceUi(false, 'Mic blocked');
      if(status) status.innerText = 'Microphone permission was blocked.';
      return;
    }
    if(status) status.innerText = `Voice error: ${event.error || 'unknown'}`;
  };
  voiceRecognition.onresult = (event) => {
    const result = event.results[event.results.length - 1];
    if(!result || !result.length) return;
    let handled = false;
    let heard = [];
    for(let i=0;i<result.length;i++){
      const transcript = String((result[i] && result[i].transcript) || '').trim();
      if(!transcript) continue;
      heard.push(transcript);
      handled = handleVoiceCommand(transcript) || handled;
      if(handled) break;
    }
    if(!handled && status){ status.innerText = heard.length ? `I heard: ${heard.join(' / ')}` : 'Voice command not recognized.'; }
  };

  btn.addEventListener('click', () => {
    if(!voiceRecognition) return;
    if(voiceListening){
      voiceListening = false;
      setVoiceUi(false, 'Voice off');
      try{ voiceRecognition.stop(); }catch(_e){}
      return;
    }
    unlockBmoSpeech();
    try{ voiceListening = true; voiceRecognition.start(); }
    catch(_e){ if(status) status.innerText = 'Could not start voice recognition.'; }
  });
}

function prettyStatus(s){
  if(!s) return s;
  return String(s).split('_').map(w=>w? w[0].toUpperCase()+w.slice(1):w).join(' ');
}

if(window.__sbCartEtaInit){
  // already initialized
} else {
  window.__sbCartEtaInit = true;


// -------------------------
// Multi-order ETA (per account)
// -------------------------

function __isActiveQueueOrder(o){
  const status = String(o && o.status || '').toLowerCase().replace(/\s+/g,'');
  if(['completed','complete','done','removed','cancelled','canceled'].includes(status)) return false;

  const eta = (o && (o.etaSeconds!=null || o.etaThisSeconds!=null)) ? __stableRemainSec(o) : 0;
  const ahead = (o && o.etaAheadSeconds!=null) ? __stableAheadSec(o) : 0;

  // Remove finished drinks from the ETA UI immediately, even if the backend
  // still reports the row for a moment with status "In Progress".
  if(['inprogress','preparing','processing','mixing','brewing','making'].includes(status) && eta <= 0){
    return false;
  }

  if(eta > 0 || ahead > 0) return true;
  return false;
}

function setMainEtaFromOrders(orders){
  const box = document.getElementById('etaBox');
  const bar = document.getElementById('etaBarFill');
  const txt = document.getElementById('etaText');
  if(!box || !bar || !txt) return;

  const list = (orders || []).filter(__isActiveQueueOrder).slice().sort((a,b)=>{
    return (parseInt(a.position || 999999) - parseInt(b.position || 999999));
  });

  if(__flushState && (__flushState.flushRequired || __flushState.flushing)){
    box.style.display = 'block';
    bar.style.width = __flushState.flushing ? '100%' : (__flushState.flushRequested ? '100%' : '0%');
    txt.textContent = __flushState.flushing ? 'Flushing tube...' : (__flushState.flushRequested ? 'Waiting for tube clean-up...' : 'Waiting for flush');
    window.__topDenom = null;
    window.__topEtaOrderId = null;
    return;
  }

  if(!list.length){
    box.style.display = 'none';
    bar.style.width = '0%';
    txt.textContent = '';
    window.__topDenom = null;
    window.__topEtaOrderId = null;
    try{
      localStorage.removeItem('lastOrderId');
      localStorage.removeItem('lastOrderTs');
      localStorage.removeItem('etaInitial');
      localStorage.removeItem('etaRemaining');
      localStorage.removeItem('etaUpdatedTs');
      localStorage.removeItem('etaAheadSeconds');
    }catch(e){}
    return;
  }

  const inProgress = list.find(o => String(o.status||'').toLowerCase().replace(/\s+/g,'') === 'inprogress');
  let target = null;
  if(window.__topEtaOrderId){
    target = list.find(o => __orderKey(o) === window.__topEtaOrderId) || null;
  }
  if(!target){
    target = inProgress || list[0];
  }
  const targetId = __orderKey(target);
  const targetStatus = String(target.status||'').toLowerCase().replace(/\s+/g,'');
  const targetIsInProgress = targetStatus === 'inprogress';

  let startsIn = targetIsInProgress ? 0 : __stableAheadSec(target);
  let remain = __stableRemainSec(target);

  if(remain <= 0 && startsIn <= 0){
    box.style.display = 'none';
    bar.style.width = '0%';
    txt.textContent = '';
    window.__topDenom = null;
    window.__topEtaOrderId = null;
    return;
  }

  box.style.display = 'block';

  if(!window.__topDenom || window.__topEtaOrderId !== targetId){
    window.__topDenom = Math.max(1, __stableSeedSec(target), remain || 1);
    window.__topEtaOrderId = targetId;
  } else {
    window.__topDenom = Math.max(1, window.__topDenom || 1, remain || 1);
  }

  const denom = Math.max(1, window.__topDenom || remain || 1);
  const pct = (startsIn > 0)
    ? 0
    : Math.max(0, Math.min(100, Math.round(((denom - remain)/denom)*100)));
  bar.style.width = pct + '%';

  const suffix = (startsIn > 0) ? ` (starts in ~${formatETA(startsIn)})` : ' (starts now)';
  txt.textContent = `${formatETA(remain)}${suffix}`;
}




function __renderMyQueue(box){
  const orders = (__myOrdersSnapshot || []).filter(__isActiveQueueOrder);
  if(!box) return;

  if(__flushState && (__flushState.flushRequired || __flushState.flushing)){
    const label = __flushState.flushing ? 'Flushing tube...' : (__flushState.flushRequested ? 'Waiting for tube clean-up...' : 'Drink complete. Press Flush Tube after grabbing your drink.');
    box.innerHTML = `
      <div class="orderRow">
        <div>
          <div class="orderTitle">Flush Status</div>
          <div class="small">Status: ${__flushState.flushing ? 'Flushing' : (__flushState.flushRequested ? 'Flushing Requested' : 'Waiting For Flush')}</div>
          <div class="small">${label}</div>
        </div>
        <div class="orderEta">${__flushState.flushing ? 'Flushing…' : (__flushState.flushRequested ? 'Cleaning…' : 'Waiting')}</div>
      </div>
      <div class="progress"><div class="fill" style="width:${(__flushState.flushing || __flushState.flushRequested) ? 100 : 0}%"></div></div>
    `;
    return;
  }

  if(!orders.length){
    if(window.__machineState && (window.__machineState.flushing || window.__machineState.flushRequired)){
      box.innerHTML = '<div class="small">' + (window.__machineState.flushing ? 'Flushing tube...' : 'Waiting for flush') + '</div>';
    } else {
      box.innerHTML = '<div class="small">No active orders.</div>';
    }
    return;
  }

  box.innerHTML = orders.map(o => {
    const drink = escapeHtml(o.drinkName || o.drink || 'Drink');
    const qty   = o.quantity || 1;
    const status = escapeHtml(o.status || 'Pending');
    const pos = o.position || 1;

    const aheadRaw = (o.etaAheadSeconds ?? null);
    const etaRaw   = (o.etaSeconds ?? null);
    const ahead = aheadRaw===null ? null : __stableAheadSec(o);
    const eta   = etaRaw===null   ? null : __stableRemainSec(o);

    const startsTxt = ahead===null ? '' : ` (starts in ${formatETA(ahead)})`;
    const rightTxt = (eta===null) ? '' : `${formatETA(eta)}${startsTxt}`;

    let bar = '';
    if((o.status === 'In Progress') && etaRaw!==null && eta!==null){
      const total = Math.max(1, (o.stepSeconds || etaRaw));
      const done = Math.min(1, Math.max(0, (total - eta) / total));
      const pct = Math.round(done * 100);
      bar = `<div class="progress"><div class="fill" style="width:${pct}%"></div></div>`;
    } else {
      bar = `<div class="progress"><div class="fill" style="width:0%"></div></div>`;
    }

    return `
      <div class="orderRow">
        <div>
          <div class="orderTitle">${drink} × ${qty}</div>
          <div class="small">Position: #${pos} (ahead: ${Math.max(0,(pos-1))}) • Status: ${status}</div>
          <div class="small"></div>
        </div>
        <div class="orderEta">${rightTxt}</div>
      </div>
      ${bar}
    `;
  }).join('');
}

async function loadMyQueue(){
  const box = document.getElementById('myQueue');
  if(!box) return;
  if(__queueFetchInFlight) return;
  __queueFetchInFlight = true;

  try{
    const res = await fetch('/api/my/queue', {credentials:'include', cache:'no-store'});
    const data = await res.json();
    if(!data.ok){
      box.innerHTML = '<div class="small">Queue unavailable.</div>';
      return;
    }
    const nextFlushState = {
      flushRequired: !!data.flushRequired,
      flushRequested: !!data.flushRequested,
      flushing: !!data.flushing,
      lastDoneDrinkName: data.lastDoneDrinkName || null
    };
    const nextSig = `${nextFlushState.flushRequired?1:0}|${nextFlushState.flushRequested?1:0}|${nextFlushState.flushing?1:0}`;
    if(nextSig !== __prevFlushSignature){
      __resetQueueUiState();
      __prevFlushSignature = nextSig;
    }
    __flushState = nextFlushState;
    const rawOrders = (data.orders || []);
    if(!rawOrders.length && !nextFlushState.flushRequired && !nextFlushState.flushing && !nextFlushState.flushRequested){ __clearStaleMachineState(); }
    __syncEtaAnchors(rawOrders);
    const orders = rawOrders.filter(__isActiveQueueOrder);
    __myOrdersSnapshot = orders;
    window.__myOrdersSnapshot = __myOrdersSnapshot;
    __mySnapshotTs = Date.now();
    try{ setMainEtaFromOrders(orders); }catch(e){}
    if(!orders.length && !__flushState.flushRequired && !__flushState.flushing){
      box.innerHTML = '<div class="small">No active orders.</div>';
      __myOrdersSnapshot = [];
      window.__myOrdersSnapshot = __myOrdersSnapshot;
      __mySnapshotTs = Date.now();
      try{
        localStorage.removeItem('lastOrderId');
        localStorage.removeItem('lastOrderTs');
        localStorage.removeItem('etaOrderId');
        localStorage.removeItem('etaInitial');
        localStorage.removeItem('etaRemaining');
        localStorage.removeItem('etaUpdatedTs');
        localStorage.removeItem('etaAheadSeconds');
      }catch(_e){}
      try{ setMainEtaFromOrders([]); }catch(e){}
      return;
    }

    __renderMyQueue(box);
  }catch(e){
    box.innerHTML = '<div class="small">Could not load queue.</div>';
  } finally {
    __queueFetchInFlight = false;
  }
}

let myQueueTimer = null;
let __myOrdersSnapshot = [];
let __flushState = {flushRequired:false, flushRequested:false, flushing:false, lastDoneDrinkName:null};
let __prevFlushSignature = '0|0|0';
let __queueFetchInFlight = false;
let __liveQueueFetchInFlight = false;
window.__myOrdersSnapshot = __myOrdersSnapshot;
let __mySnapshotTs = 0;
let __localTickTimer = null;
let __etaAnchors = {};

function __elapsedSec(){
  if(!__mySnapshotTs) return 0;
  return Math.floor((Date.now() - __mySnapshotTs)/1000);
}

function __orderKey(o){
  if(!o) return '';
  return String(o.orderId || o.id || [o.drinkName || o.drink || 'drink', o.position || '', o.ts || ''].join('|'));
}

function __syncEtaAnchors(orders){
  const now = Date.now();
  const next = {};
  (orders || []).forEach(o => {
    const key = __orderKey(o);
    if(!key) return;

    const prev = __etaAnchors[key] || {};
    const rawRemain = Math.max(0, parseInt((o && (o.etaThisSeconds ?? o.etaSeconds)) || 0) || 0);
    const rawAhead  = Math.max(0, parseInt((o && o.etaAheadSeconds) || 0) || 0);

    const serverRemainDueAt = now + rawRemain * 1000;
    const serverStartDueAt  = now + rawAhead * 1000;

    let remainDueAt = serverRemainDueAt;
    let startDueAt  = serverStartDueAt;

    const prevRemain = prev.remainDueAt ? Math.max(0, (prev.remainDueAt - now) / 1000) : null;
    const prevAhead  = prev.startDueAt ? Math.max(0, (prev.startDueAt - now) / 1000) : null;

    // Keep the local countdown steady unless the server is materially LOWER.
    // This avoids the visual back-and-forth caused by small polling jitter.
    if(prev.remainDueAt){
      if(rawRemain >= Math.max(0, prevRemain - 2)){
        remainDueAt = prev.remainDueAt;
      } else {
        remainDueAt = serverRemainDueAt;
      }
    }
    if(prev.startDueAt){
      if(rawAhead >= Math.max(0, prevAhead - 2)){
        startDueAt = prev.startDueAt;
      } else {
        startDueAt = serverStartDueAt;
      }
    }

    next[key] = {
      remainDueAt,
      startDueAt,
      remainSeed: Math.max(1, prev.remainSeed || rawRemain || 1),
      startSeed: Math.max(0, prev.startSeed || rawAhead || 0),
    };
  });
  __etaAnchors = next;
}

function __stableRemainSec(o){
  const a = __etaAnchors[__orderKey(o)];
  if(a && a.remainDueAt){
    return Math.max(0, Math.ceil((a.remainDueAt - Date.now()) / 1000));
  }
  return Math.max(0, Math.round(((o && (o.etaThisSeconds ?? o.etaSeconds)) || 0)));
}

function __stableAheadSec(o){
  const a = __etaAnchors[__orderKey(o)];
  if(a && a.startDueAt){
    return Math.max(0, Math.ceil((a.startDueAt - Date.now()) / 1000));
  }
  return Math.max(0, Math.round(((o && o.etaAheadSeconds) || 0)));
}

function __stableSeedSec(o){
  const a = __etaAnchors[__orderKey(o)];
  if(a && a.remainSeed){
    return Math.max(1, a.remainSeed);
  }
  return Math.max(1, parseInt((o && (o.etaThisSeconds ?? o.etaSeconds)) || 1) || 1);
}

function __adjSec(s){
  const e = __elapsedSec();
  return Math.max(0, Math.round(s - e));
}


function __clearStaleMachineState(){
  __flushState = {flushRequired:false, flushRequested:false, flushing:false, lastDoneDrinkName:null};
  try{
    localStorage.removeItem('lastOrderId');
    localStorage.removeItem('lastOrderTs');
    localStorage.removeItem('etaOrderId');
    localStorage.removeItem('etaInitial');
    localStorage.removeItem('etaRemaining');
    localStorage.removeItem('etaUpdatedTs');
    localStorage.removeItem('etaAheadSeconds');
  }catch(_e){}
}
function __resetQueueUiState(){
  __etaAnchors = {};
  __myOrdersSnapshot = [];
  window.__myOrdersSnapshot = __myOrdersSnapshot;
  __mySnapshotTs = Date.now();
  window.__topDenom = null;
  window.__topEtaOrderId = null;
  try{
    localStorage.removeItem('lastOrderId');
    localStorage.removeItem('lastOrderTs');
    localStorage.removeItem('etaOrderId');
    localStorage.removeItem('etaInitial');
    localStorage.removeItem('etaRemaining');
    localStorage.removeItem('etaUpdatedTs');
    localStorage.removeItem('etaAheadSeconds');
  }catch(_e){}
}

function startMyQueueAutoRefresh(){
  if(myQueueTimer) clearInterval(myQueueTimer);
  loadMyQueue();
  myQueueTimer = setInterval(loadMyQueue, 2000);
  if(!__localTickTimer){
    __localTickTimer = setInterval(() => {
      if(document.hidden) return;
      const box = document.getElementById('myQueue');
      if(!box) return;
      __renderMyQueue(box);
      try{ setMainEtaFromOrders(__myOrdersSnapshot); }catch(_e){}
    }, 1000);
  }
  document.addEventListener('visibilitychange', () => {
    if(document.hidden){
      if(myQueueTimer) clearInterval(myQueueTimer);
      myQueueTimer = null;
    }else{
      startMyQueueAutoRefresh();
    }
  }, {once:true});
}



// lightweight HTML escape for safe rendering
function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, m => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[m]));
}


function prettyIngredientName(s){
  if(!s) return s;
  return String(s).split('_').map(w => w ? (w[0].toUpperCase() + w.slice(1)) : w).join(' ');
}


// -----------------------------
// Menu search (client-side)
// -----------------------------
// Keep the latest query so Add/Remove doesn't reset the filter.
let menuQuery = '';


function formatSeconds(s){ s=Math.max(0,Math.floor(s||0)); const m=Math.floor(s/60), r=s%60; return m>0?`${m}m ${r}s`:`${r}s`; }

function formatETA(sec){
  try{ sec = Math.max(0, parseInt(sec)); }catch(e){ return String(sec); }
  const m = Math.floor(sec/60);
  const s = sec%60;
  return m>0 ? `${m}m ${s.toString().padStart(2,'0')}s` : `${s}s`;
}

async function loadQueue(){
  const el = document.getElementById('queue');
  if(__liveQueueFetchInFlight) return;
  __liveQueueFetchInFlight = true;
  try{
    const res = await fetch('/api/my/queue', {credentials:'include', cache:'no-store'});
    const data = await res.json();
    if(!res.ok || !data.ok){
      el.innerText = "Active queue: unavailable.";
      return;
    }
    const nextFlushState = {
      flushRequired: !!data.flushRequired,
      flushRequested: !!data.flushRequested,
      flushing: !!data.flushing,
      lastDoneDrinkName: data.lastDoneDrinkName || null
    };
    const nextSig = `${nextFlushState.flushRequired?1:0}|${nextFlushState.flushRequested?1:0}|${nextFlushState.flushing?1:0}`;
    if(nextSig !== __prevFlushSignature){
      __resetQueueUiState();
      __prevFlushSignature = nextSig;
    }
    __flushState = nextFlushState;
    const rawOrders = (data.orders || []);
    if(!rawOrders.length && !nextFlushState.flushRequired && !nextFlushState.flushing && !nextFlushState.flushRequested){ __clearStaleMachineState(); }
    __syncEtaAnchors(rawOrders);
    const orders = rawOrders.filter(__isActiveQueueOrder);
    __myOrdersSnapshot = orders;
    window.__myOrdersSnapshot = __myOrdersSnapshot;
    __mySnapshotTs = Date.now();
    try{ setMainEtaFromOrders(orders); }catch(e){}
    if(!orders.length){
      if(__flushState.flushing || __flushState.flushRequired){
        const msg = __flushState.flushing ? 'Flushing tube...' : (__flushState.flushRequested ? 'Waiting for tube clean-up...' : 'Waiting for flush');
        el.innerHTML = "<b>Active queue:</b> <span class='small'>" + msg + "</span>";
      } else {
        el.innerHTML = "<b>Active queue:</b> <span class='small'>No active orders in queue.</span>";
      }
      return;
    }
    let html = "<b>Active queue (live):</b>";
    html += '<table class="table" style="margin-top:10px"><tr><th>Order</th><th>Position</th><th>Status</th><th>Starts In</th><th>ETA</th></tr>';
    orders.forEach(o=>{
      const oid = (o.orderId||'').slice(0,8);
      const pos = o.position ?? '';
      const st  = o.status ?? '';
      const ahead = (o.etaAheadSeconds !== undefined) ? formatETA(o.etaAheadSeconds) : '...';
      const eta   = (o.etaSeconds !== undefined) ? formatETA(o.etaSeconds) : '...';
      html += `<tr><td>${oid}</td><td>${pos}</td><td>${st}</td><td>${ahead}</td><td>${eta}</td></tr>`;
    });
    html += "</table>";
    el.innerHTML = html;
  }catch(e){
    el.innerText = "Active queue error.";
  } finally {
    __liveQueueFetchInFlight = false;
  }
}


let drinks = [];
let cart = {};
let lastOrderItems = null; // persists last checkout summary

function scrollToCheckoutStatus(){
  const statusEl = document.getElementById('status');
  if(statusEl){
    statusEl.scrollIntoView({behavior:'smooth', block:'center'});
  }
}

let recs = [];
let pollTimer = null;

// Bind checkout button click
const checkoutBtn = document.getElementById('checkoutBtn');
if (checkoutBtn) {
  checkoutBtn.addEventListener('click', async (e) => {
    // pressed feedback even if request fails
    checkoutBtn.classList.add('clicked');
    setTimeout(() => checkoutBtn.classList.remove('clicked'), 160);
    await checkout(checkoutBtn);
  });
}


function formatETA(sec){
  try{ sec = Math.max(0, parseInt(sec)); }catch(e){ return String(sec); }
  const m = Math.floor(sec/60);
  const s = sec%60;
  return m>0 ? `${m}m ${s.toString().padStart(2,'0')}s` : `${s}s`;
}

function parseEtaSeconds(v){
  if(v === null || v === undefined) return null;
  if(typeof v === 'number') return isFinite(v) ? Math.max(0, Math.floor(v)) : null;
  // try plain int string
  const n = parseInt(v);
  if(!isNaN(n) && String(v).trim().match(/^\d+$/)) return Math.max(0, n);
  // try formats like "10m 06s" or "10m06s" or "1m" or "45s"
  const s = String(v);
  const mm = s.match(/(\d+)\s*m/i);
  const ss = s.match(/(\d+)\s*s/i);
  if(mm || ss){
    const m = mm ? parseInt(mm[1]) : 0;
    const sec = ss ? parseInt(ss[1]) : 0;
    return Math.max(0, m*60 + sec);
  }
  return null;
}

function setEtaFromServer(etaSeconds, etaAheadSeconds){
  const serverEtaRaw = parseEtaSeconds(etaSeconds);
  if(serverEtaRaw === null) return; // don't overwrite with invalid

  const serverEta = Math.max(0, serverEtaRaw);

  const currentOrderId = localStorage.getItem('lastOrderId');
  const etaOrderId = localStorage.getItem('etaOrderId');

  // If this is a new order (or first time we ever stored one), reset ETA state cleanly.
  if(currentOrderId && currentOrderId !== etaOrderId){
    localStorage.setItem('etaOrderId', currentOrderId);
    localStorage.removeItem('etaInitial');
    localStorage.removeItem('etaRemaining');
    localStorage.removeItem('etaUpdatedTs');
    localStorage.removeItem('etaAheadSeconds');
  }
const hasPrev = !!localStorage.getItem('etaUpdatedTs');

  // Current live remaining (based on our last tick)
  const live = getLiveEta();
  const liveRemaining = (live && live.remaining !== undefined) ? Math.max(0, live.remaining) : null;

  // Make ETA monotonic (never jump upward due to server jitter) ONLY after we have a previous sample.
  // (First sample should always be accepted; otherwise we can get stuck at 0.)
  let nextRemaining = serverEta;
  if(hasPrev && liveRemaining !== null){
    // Allow tiny upward corrections (<=2s).
    if(serverEta > liveRemaining + 2){
      nextRemaining = Math.ceil(liveRemaining);
    } else {
      nextRemaining = serverEta;
    }
  }

  // Initial baseline: set once per order.
  const prevInitial = parseInt(localStorage.getItem('etaInitial') || '0');
  if(!prevInitial){
    localStorage.setItem('etaInitial', String(Math.max(1, nextRemaining)));
  } else {
    localStorage.setItem('etaInitial', String(Math.max(1, prevInitial)));
  }

  localStorage.setItem('etaRemaining', String(Math.max(0, nextRemaining)));
  localStorage.setItem('etaUpdatedTs', String(Date.now()));

  // Smooth "starts in" (ahead) if provided
  const serverAheadRaw = parseEtaSeconds(etaAheadSeconds);
  if(serverAheadRaw !== null){
    const serverAhead = Math.max(0, serverAheadRaw);
    const prevAhead = parseInt(localStorage.getItem('etaAheadSeconds') || '0');
    // never jump upward (allow +2s) once we have a previous sample
    const nextAhead = (prevAhead && serverAhead > prevAhead + 2) ? prevAhead : serverAhead;
    localStorage.setItem('etaAheadSeconds', String(nextAhead));
  }

  const box = document.getElementById('etaBox');
  if(box) box.style.display = 'block';
}

function getLiveEta(){
  const remaining0 = parseFloat(localStorage.getItem('etaRemaining') || '0');
  const ts = parseFloat(localStorage.getItem('etaUpdatedTs') || '0');
  if(!ts) return {remaining: remaining0, initial: parseFloat(localStorage.getItem('etaInitial')||'0')};
  const elapsed = (Date.now() - ts) / 1000.0;
  const remaining = Math.max(0, remaining0 - elapsed);
  const initial = parseFloat(localStorage.getItem('etaInitial') || String(Math.max(1, remaining0)));
  return {remaining, initial};
}

function renderEtaBar(){
  const box = document.getElementById('etaBox');
  if(!box) return;

  // The per-account queue renderer owns the main ETA UI whenever it has live data.
  if(Array.isArray(window.__myOrdersSnapshot) && window.__myOrdersSnapshot.length){
    return;
  }

  const lastOrderId = localStorage.getItem('lastOrderId');
  if(!lastOrderId){
    box.style.display = 'none';
    return;
  }

  const {remaining, initial} = getLiveEta();
  const aheadStored = parseEtaSeconds(localStorage.getItem('etaAheadSeconds'));
  if((!initial || initial<=0) && aheadStored && aheadStored>0){
    box.style.display = 'block';
    const etaText = document.getElementById('etaText');
    if(etaText) etaText.innerText = `Waiting for ETA... (starts in ~${formatETA(aheadStored)})`;
    const fill = document.getElementById('etaBarFill');
    if(fill) fill.style.width = '0%';
    return;
  }

  if(!initial){
    box.style.display = 'none';
    return;
  }

  box.style.display = 'block';

  const pct = Math.max(0, Math.min(100, (1 - (remaining/initial)) * 100));
  const fill = document.getElementById('etaBarFill');
  if(fill) fill.style.width = pct.toFixed(1) + '%';

  const startsIn = localStorage.getItem('etaAheadSeconds');
  const startsTxt = (startsIn !== null && startsIn !== undefined && startsIn !== '') 
    ? ` (starts in ~${formatETA(parseInt(startsIn))})` 
    : '';

  const etaText = document.getElementById('etaText');
  if(etaText) etaText.innerText = `${formatETA(Math.ceil(remaining))}${startsTxt}`;
}

function startEtaTicker(){
  // One global ticker tied to page
  if(window.__etaTicker) clearInterval(window.__etaTicker);
  window.__etaTicker = setInterval(renderEtaBar, 500);
  renderEtaBar();
}



function ingredientsHtml(d, enableHighlight=true){
  const arr = d && d.ingredients;
  if(!arr || !Array.isArray(arr) || arr.length===0) return "";
  const hi = (enableHighlight && window.basedOnIngredients && window.basedOnIngredients.size) ? window.basedOnIngredients : new Set();
  const items = arr.map(x => {
    const key = String(x);
    const matched = enableHighlight && hi.has(key);
    // Use inline styles so it's impossible to miss in demo
    const style = matched ? "font-weight:900;color:#fff;background:rgba(255,255,255,.08);border-radius:6px;padding:2px 6px;display:inline-block;text-shadow:0 0 10px rgba(255,255,255,.7),0 0 20px rgba(255,215,150,.35);" : "";
    return `<li style="${style}">${escapeHtml(prettyIngredientName(key))}</li>`;
  }).join("");
  return `<div class='ing'><div class='small'>Ingredients:</div><ul>${items}</ul></div>`;
}


function renderRecs(){
  const el = document.getElementById('recs');
  if(!el) return;
  el.innerHTML='';
  if(!recs || recs.length===0){ el.innerHTML = "<div class='small'>No recommendations yet. Place a few orders first 🙂</div>"; return; }
  recs.forEach(d => {
    const card = document.createElement('div');
    const qty = (cart[d.id] && cart[d.id].quantity) ? cart[d.id].quantity : 0;
    card.className = qty > 0 ? 'card selected' : 'card';
    const cal = (d.calories || 0);
    card.innerHTML = `
      <h2>${d.name}</h2>
      <div class='small'>Calories: <span class='pill'>${cal} cal</span></div>
      <div class='small' style='margin-top:10px'>In cart: <span class='pill qty-pill'>${qty}</span></div>
      ${ingredientsHtml(d)}
      
      <div class='btnrow' style='margin-top:12px'>
        <button class='secondary ${qty>0 ? 'btn-active' : ''}' onclick="addToCart('${d.id}','${d.name.replace(/'/g, "\\'")}',${cal})">Add</button>
        <button class='secondary' ${qty===0 ? 'disabled' : ''} onclick="removeFromCart('${d.id}')">Remove</button>
        
      </div>
    `;
    el.appendChild(card);
  })
}

function renderMenu(query = '') {
  // Normalize query and remember it globally so the filter persists
  // across Add/Remove updates.
  menuQuery = String(query || '').trim();
  const q = menuQuery.toLowerCase();

  const el = document.getElementById('menu');
  el.innerHTML = '';
  drinks.forEach(d => {
    // Filter by drink name (and optionally ingredient keys)
    if (q) {
      const nameMatch = String(d.name || '').toLowerCase().includes(q);
      const ing = Array.isArray(d.ingredients) ? d.ingredients : [];
      const ingMatch = ing.some(x => String(x).toLowerCase().includes(q));
      if (!nameMatch && !ingMatch) return;
    }
    const card = document.createElement('div');
    const qty = (cart[d.id] && cart[d.id].quantity) ? cart[d.id].quantity : 0;
    card.className = qty > 0 ? 'card selected' : 'card';
    const cal = (d.calories || 0);
    card.innerHTML = `
      <h2>${d.name}</h2>
      <div class='small'>Calories: <span class='pill'>${cal} cal</span></div>
      <div class='small' style='margin-top:10px'>In cart: <span class='pill qty-pill'>${qty}</span></div>
      ${ingredientsHtml(d, false)}
      <div class='btnrow' style='margin-top:12px'>
        
        <button class='secondary ${qty>0 ? 'btn-active' : ''}' onclick="addToCart('${d.id}','${d.name.replace(/'/g, "\\'")}',${cal})">Add</button>
        <button class='secondary' ${qty===0 ? 'disabled' : ''} onclick="removeFromCart('${d.id}')">Remove</button>
      </div>
    `;
    el.appendChild(card);
  })
}

function renderCart(){
  const el = document.getElementById('cart');
  const keys = Object.keys(cart);

  // If cart is empty but we just checked out, show the last order summary
  if(keys.length===0){
    if(Array.isArray(lastOrderItems) && lastOrderItems.length){
      let html = "<div class='small' style='margin-bottom:8px'>Last order:</div>";
      html += '<table class="table"><tr><th>Drink</th><th>Qty</th><th>Calories</th></tr>';
      lastOrderItems.forEach(it=>{
        const nm = it.drinkName || '';
        const q  = parseInt(it.quantity || 1);
        const c  = parseInt(it.calories || 0);
        html += `<tr><td>${nm}</td><td>${q}</td><td>${c}</td></tr>`;
      });
      html += '</table>';
      el.innerHTML = html;
      return;
    }
    el.innerHTML='No items yet.';
    return;
  }
  let html = '<table class="table"><tr><th>Drink</th><th>Qty</th><th>Calories</th></tr>';
  keys.forEach(k=>{
    const it = cart[k];
    html += `<tr><td>${it.drinkName}</td><td>${it.quantity}</td><td>${it.calories}</td></tr>`;
  })
  html += '</table>';
  el.innerHTML = html;
}

function addToCart(id,name,cal){
  bmoSay(`Added 1 ${name}`, true, true);
  if(!cart[id]) cart[id] = {drinkId:id, drinkName:name, quantity:0, calories:cal};
  cart[id].quantity += 1;
  pushActivity('add', name, 1);
  renderCart();
	  renderMenu(menuQuery);
  renderRecs();
}

function removeFromCart(id){
  if(!cart[id]) return;
  const name = cart[id].drinkName;
  bmoSay(`Removed 1 ${name}`, true, true);
  cart[id].quantity -= 1;
  if(cart[id].quantity <= 0) delete cart[id];
  pushActivity('remove', name, 1);
  renderCart();
	  renderMenu(menuQuery);
  renderRecs();
}

async function checkout(btnEl) {
  console.log('[checkout] clicked');
  let cupReady = false;
  try {
    const cupRes = await fetch('/api/cup/status', {cache:'no-store', credentials:'same-origin'});
    const cupData = await cupRes.json();
    cupReady = !!(cupData && cupData.cupConfirmed);
  } catch(_e) {
    cupReady = (() => { try { return localStorage.getItem('tipsyCupReady') === 'true'; } catch(_e2) { return false; } })();
  }
  if (!cupReady) {
    bmoSay('Please confirm the cup is under the machine before ordering.', true, true);
    const statusEl = document.getElementById('status');
    if (statusEl) statusEl.innerText = 'Please confirm the cup on the live display before ordering.';
    return;
  }
  bmoSay('Order placed. Preparing your drink.', true, true);
  const btn = btnEl || document.getElementById('checkoutBtn') || document.querySelector('.checkout-btn');
  const status = document.getElementById('status');

  // Only send items with quantity > 0 (guards against stale UI state)
  const items = Object.values(cart).filter(it => it && parseInt(it.quantity || 0) > 0);

  if (items.length === 0) {
    if (status) status.innerText = 'Cart is empty.';
    // Safety: clear any stuck loading state
    if (btn) {
      btn.classList.remove('loading');
      btn.disabled = false;
      btn.innerText = btn.dataset.orig || 'Checkout';
    }
    return;
  }

// UI feedback
  let timer = null;
  if (btn) {
    btn.dataset.orig = btn.dataset.orig || btn.innerText;
    btn.classList.add('loading');
    btn.disabled = true;
    btn.innerText = 'Processing...';
    timer = setTimeout(() => {
      btn.classList.remove('loading');
      btn.disabled = false;
      btn.innerText = btn.dataset.orig || 'Checkout';
      if (status) status.innerText = 'Checkout timed out. Please try again.';
    }, 10000);
  }

  try {
    if (status) status.innerText = 'Checking out...';

    let res = await fetch('/checkout', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'same-origin',
      cache:'no-store',
      body: JSON.stringify({items, mood: (window.currentMood && window.currentMood !== 'none') ? window.currentMood : null})
    });
    if(res && res.status===404){ res = await fetch('/api/checkout', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({items, mood: (window.currentMood && window.currentMood !== 'none') ? window.currentMood : null}) }); }


    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
      await res.text();
      if(status) status.innerText = "Checkout failed. Please login again.";
      return;
    }

    const data = await res.json();
    if(data && data.ok){
      const orderId = data.orderId || data.orderID || data.id;
      if(status) status.innerText = 'Order placed!';
      scrollToCheckoutStatus();
      lastOrderItems = items;
      cart = {};
      renderCart();
      try{ await loadRecs(); }catch(e){ console.warn('[checkout] loadRecs failed after successful checkout', e); }
      try{ renderRecs(); }catch(e){ console.warn('[checkout] renderRecs failed after successful checkout', e); }
      try{ localStorage.setItem('lastOrderId', orderId || ''); localStorage.setItem('lastOrderTs', String(Date.now())); }catch(e){}
      if(data.queue){ try{ setEtaFromServer(data.queue.etaSeconds ?? data.queue.etaThisSeconds ?? 0, data.queue.etaAheadSeconds ?? 0); }catch(e){} }
      if(orderId){
        try{ startQueuePoll(orderId); }catch(e){}
        try{ startEtaTicker(); }catch(e){}
      }
      // Force the menu ETA and active-order cards to show immediately without a manual refresh
      try{ await loadMyQueue(); }catch(e){ console.warn('[checkout] loadMyQueue failed after successful checkout', e); }
      setTimeout(() => { try{ loadMyQueue(); }catch(e){} }, 700);
      // refresh ETA box if present
      try{ renderEtaBar(); }catch(e){}
    }else{
      const errMsg = (data && (data.error || data.detail || data.msg)) ? (data.error || data.detail || data.msg) : 'Checkout failed.';
      if(status) status.innerText = errMsg;
    }
  }catch(err){
    console.error('[checkout] request failed', err);
    if(status && !/order placed|queued|saved/i.test(String(status.innerText || ''))) status.innerText = 'Checkout error. Please try again.';
  }finally{
    if (btn){
      if (timer) clearTimeout(timer);
      btn.classList.remove('loading');
      btn.disabled = false;
      btn.innerText = btn.dataset.orig || 'Checkout';
    }
  }
}

// expose for inline onclick
window.checkout = checkout;


function startQueuePoll(orderId){
  if(pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async ()=>{
    try{
      const r = await fetch(`/api/queue/status?orderId=${encodeURIComponent(orderId)}`);
      const data = await r.json();
      if(data && data.ok){
        const eta = (data.etaSeconds!==undefined) ? formatETA(data.etaSeconds) : '...';
        const etaStart = (data.etaAheadSeconds!==undefined) ? formatETA(data.etaAheadSeconds) : '...';
        document.getElementById('status').innerText = `Queued! Orders ahead: ${ (typeof data.ahead==='number') ? data.ahead : (typeof data.position==='number' ? Math.max(0, data.position-1) : 0) }`;
        setEtaFromServer(data.etaSeconds, data.etaAheadSeconds);
        try{ loadMyQueue(); }catch(e){}
      } else {
        document.getElementById('status').innerText = `Order completed. `;
        clearInterval(pollTimer);
        localStorage.removeItem('lastOrderId');
        localStorage.removeItem('lastOrderTs');
        localStorage.removeItem('etaInitial');
        localStorage.removeItem('etaRemaining');
        localStorage.removeItem('etaUpdatedTs');
        localStorage.removeItem('etaAheadSeconds');
      }
    }catch(e){ /* ignore */ }
  }, 3000);
}

(async function init(){
  // Load drinks once
  const r = await fetch('/api/drinks');
  drinks = await r.json();

  // Resume queue polling if an order is still in localStorage
  const lastOrderId = localStorage.getItem('lastOrderId');
  if(lastOrderId){
    document.getElementById('status').innerText = `Resuming status for ...`;
    startQueuePoll(lastOrderId);
    startEtaTicker();
    try{ await loadMyQueue(); }catch(e){}
  }

  // Mood-based recommendations state
  window.currentMood = window.currentMood || 'none';
  let moodTimer = null;

  function setMoodLabel(){
    const el = document.getElementById('moodLabel');
    if(!el) return;
    el.textContent = `Mood: ${window.currentMood || 'none'}`;
  }

  function setMoodButtons(){
    document.querySelectorAll('.mood-btn').forEach(btn=>{
      const m = btn.dataset.mood;
      const cur = window.currentMood || 'none';
    btn.classList.toggle('active', m === cur);
    });
  }

  async function loadRecs(){
    try{
      const curMood = window.currentMood || 'none';
  const url = (curMood && curMood !== 'none')
    ? `/api/recommendations?k=3&mood=${encodeURIComponent(curMood)}`
    : '/api/recommendations?k=3';
      const rr = await fetch(url, {cache:'no-store', credentials:'same-origin'});
      const rdata = await rr.json();
      if(rdata && rdata.ok){
        recs = rdata.recommendations || [];
        // save ingredients from last ordered drink for highlighting
        try{
          const arr = rdata.based_on_ingredients || [];
          window.basedOnIngredients = new Set((Array.isArray(arr)?arr:[]).map(x=>String(x)));
        }catch(e){ window.basedOnIngredients = new Set(); }
        const banner = document.getElementById('recBanner');
        if(banner){
          const based = rdata.based_on || null;
          if(based){
            banner.style.display = 'block';
            const dbg = (rdata.based_on_ingredients||[]).map(x=>prettyIngredientName(String(x))).join(', ');
            banner.innerHTML = `Because you ordered: <strong>${escapeHtml(based)}</strong> <span class="buildtag"></span><div class="debugline">Matched ingredient keys: ${escapeHtml(dbg)}</div>`;
          }else{
            banner.style.display = 'none';
            banner.innerHTML = '';
          }
        }
      }else{
        // keep the last good recommendations instead of wiping the UI
      }
    }catch(e){
      // keep the last good recommendations instead of wiping the UI
    }
  }

  async function refreshRecsWithFade(){
    const el = document.getElementById('recs');
    if(el){
      // one-time transition setup
      if(!el.dataset.fadeInit){
        el.style.transition = 'opacity 180ms ease, transform 180ms ease';
        el.dataset.fadeInit = '1';
      }
      el.style.opacity = '0';
      el.style.transform = 'translateY(6px)';
      await new Promise(r => setTimeout(r, 180));
    }

    await loadRecs();
    renderRecs();

    if(el){
      // fade back in
      requestAnimationFrame(()=>{
        el.style.opacity = '1';
        el.style.transform = 'translateY(0)';
      });
    }
  }

  function startMoodAutoRefresh(){
    if(moodTimer){ clearInterval(moodTimer); moodTimer = null; }

    moodTimer = setInterval(async ()=>{
      if(document.hidden) return;
      await loadRecs();
      renderRecs();
    }, 6000);
  }

  document.addEventListener('visibilitychange', async ()=>{
    if(!document.hidden){
      await loadRecs();
      renderRecs();
    }
  });

  // Expose the click handler used by the mood buttons
  window.pickMood = async function(m){
    window.currentMood = (m && m !== 'none') ? m : 'none';
    setMoodLabel();
    setMoodButtons();
    await refreshRecsWithFade();
    startMoodAutoRefresh();
  };
// Initial render
  setMoodLabel();
  await loadRecs();
  renderRecs();
  startMoodAutoRefresh();
  const _search = document.getElementById('drinkSearch');
  const _clear = document.getElementById('drinkSearchClear');
  if (_search) {
    _search.addEventListener('input', () => renderMenu(_search.value));
  }
  if (_clear && _search) {
    _clear.addEventListener('click', () => { _search.value=''; renderMenu(''); _search.focus(); });
  }
  renderMenu(_search ? _search.value : '');
  renderCart();
})();

// start per-account multi-order queue polling
try { startMyQueueAutoRefresh(); } catch (e) { console.log("myQueue init failed", e); }
try { startActivityLiveRefresh(); } catch (e) { console.log("activity live init failed", e); }
try { startSharedActivityRefresh(); } catch (e) { console.log("shared activity init failed", e); }

}
</script>
<div id="menuPopup" class="menu-popup" aria-live="polite"></div>

</div></body></html>
""")

    return HTMLResponse(tpl.safe_substitute(STYLE=STYLE))


@router.get("/drink/{drink_id}", response_class=HTMLResponse)
def drink_page(request: Request, drink_id: str):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    d = _find_drink(drink_id)
    if not d:
        return HTMLResponse(
            f"<html><head><title>Not Found</title>{STYLE}</head>"
            f"<body><div class='page'><h1>NOT FOUND</h1>"
            f"<div class='card'><p class='small'>Unknown drink id: <b>{drink_id}</b></p>"
            f"<div class='btnrow'><button class='secondary' onclick=\"window.location.href='/builder'\">Back</button></div>"
            f"</div></div></body></html>",
            status_code=404
        )

    name = d.get("name", drink_id)
    cal = int(d.get("calories", 0) or 0)

    ingredients = d.get("ingredients")
    if isinstance(ingredients, list) and ingredients:
        lis = "".join([f"<li>{str(x)}</li>" for x in ingredients])
        ingredients_block = f"<div class='ing' style='margin-top:12px'><div class='small'>Ingredients:</div><ul>{lis}</ul></div>"
    else:
        ingredients_block = ""

    tpl = Template(r"""
<html><head><title>$name</title>$STYLE</head>
<body><div class='page'>
  <h1>$name_upper</h1>
  <div class='grid cards'>
    <div class='card'>
      <h2>ORDER THIS DRINK</h2>
      <div class='small'>Calories: <span class='pill'>$cal cal</span></div>
      $ingredients_block
      <hr/>
      <div class='small'>Quantity</div>
      <div class='btnrow'>
        <button class='secondary' onclick='decQty()'>-</button>
        <span id='qty' class='pill qty-pill'>1</span>
        <button class='secondary' onclick='incQty()'>+</button>
      </div>
      <div class='btnrow' style='margin-top:14px'>
        <button class='primary checkout-btn' type='button' onclick="this.classList.add('clicked'); setTimeout(()=>this.classList.remove('clicked'),160); checkout(this);">Checkout</button>
        <button class='secondary' onclick="window.location.href='/builder'">Menu</button>
      </div>
      <div id='status' class='small' style='margin-top:10px'></div>
    </div>
  </div>

<script>
let quantity = 1;
function setQty(){ document.getElementById('qty').innerText = quantity; }
function incQty(){ quantity += 1; setQty(); }
function decQty(){ quantity = Math.max(1, quantity - 1); setQty(); }

async function checkout(btnEl) {
  const status = document.getElementById('status');
  status.innerText = 'Checking out...';
  const items = [{drinkId: "$drink_id", drinkName: "$name_js", quantity: quantity, calories: $cal}];

  try {
    let res = await fetch('/checkout', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'same-origin',
      cache:'no-store',
      body: JSON.stringify({items, mood: (window.currentMood && window.currentMood !== 'none') ? window.currentMood : null})
    });
    if(res && res.status===404){
      res = await fetch('/api/checkout', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        credentials:'same-origin',
        cache:'no-store',
        body: JSON.stringify({items, mood: (window.currentMood && window.currentMood !== 'none') ? window.currentMood : null})
      });
    }

    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
      await res.text();
      status.innerText = "Checkout failed (server returned non-JSON). Please login again.";
      return;
    }

    const data = await res.json();
    if (!res.ok || !data.ok) {
      status.innerText = "Error: " + (data.error || ("HTTP " + res.status));
      return;
    }

    const q = (data.queue || {});
    if (q.position) {
      status.innerText = `Queued! Orders ahead: ${ (typeof q.ahead==='number') ? q.ahead : (typeof q.position==='number' ? Math.max(0, q.position-1) : 0) }`;
      try { startQueuePoll(data.orderId); } catch(e) {}
    } else {
      status.innerText = `Order saved.`;
    }
  } catch (err) {
    console.error('[single checkout] failed', err);
    status.innerText = 'Checkout error. Please try again.';
  }
}

setQty();
</script>
<div id="menuPopup" class="menu-popup" aria-live="polite"></div>

</div></body></html>
""")

    return HTMLResponse(tpl.safe_substitute(
        STYLE=STYLE,
        name=name,
        name_upper=name.upper(),
        name_js=name.replace('"', '\\"'),
        drink_id=drink_id,
        cal=str(cal),
        ingredients_block=ingredients_block,
    ))


@router.get("/history", response_class=HTMLResponse)
def history(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    tpl = Template(r"""
<html><head><title>History</title>$STYLE</head>
<body><div class='page'>
  <h1>ORDER HISTORY</h1>

  <div class='card'>
    <div class='small'>Logged in as: <span class='pill' id='who'>$user</span></div>
    <div id='queue' class='small' style='margin-top:12px'>Loading queue...</div>
    <div id='content' class='small' style='margin-top:16px'>Loading history...</div>

    <div class='btnrow' style='margin-top:14px'>
      <button class='secondary' onclick="window.location.href='/builder'">Back to Menu</button>
    </div>
  </div>

<script>

async function loadQueue(){
  const el = document.getElementById('queue');
  if(__liveQueueFetchInFlight) return;
  __liveQueueFetchInFlight = true;
  try{
    const res = await fetch('/api/my/queue', {credentials:'include', cache:'no-store'});
    const ct = res.headers.get("content-type") || "";
    if(!ct.includes("application/json")){
      el.innerText = "Queue failed (non-JSON). Please login again.";
      return;
    }
    const data = await res.json();
    if(!res.ok || !data.ok){
      el.innerText = "Queue error: " + (data.error || ("HTTP " + res.status));
      return;
    }

    const orders = data.orders || [];
    try{ setMainEtaFromOrders(orders); }catch(e){}
    if(orders.length === 0){
      el.innerHTML = "<span class='small'>No active queued orders.</span>";
      return;
    }

    let html = "<div class='small' style='margin-bottom:6px'>Active queue (live):</div>";
    html += "<table class='table'><tr><th>#</th><th>Status</th><th>Starts in</th><th>Complete in</th><th>Order</th></tr>";
    orders.forEach(o=>{
      const pos = o.position || "-";
      const ahead = (typeof o.etaAheadSeconds === "number") ? o.etaAheadSeconds : null;
      const eta = (typeof o.etaSeconds === "number") ? o.etaSeconds : null;

      const fmt = (s)=>{
        if(s==null) return "--";
        s = Math.max(0, Math.floor(s));
        const m = Math.floor(s/60);
        const r = s%60;
        return m>0 ? `${m}m ${r}s` : `${r}s`;
      };

      html += `<tr>
        <td>${pos}</td>
        <td>${o.status || ''}</td>
        <td>${fmt(ahead)}</td>
        <td>${fmt(eta)}</td>
        <td class='small'>${(o.orderId||'').slice(0,8)}…</td>
      </tr>`;
    });
    html += "</table>";
    el.innerHTML = html;

  }catch(e){
    el.innerText = "Queue error: " + e;
  }
}

async function loadHistory(){
  const el = document.getElementById('content');
  try{
    const res = await fetch('/api/history', {credentials:'include'});
    const ct = res.headers.get("content-type") || "";
    if(!ct.includes("application/json")){
      el.innerText = "History failed (server returned non-JSON). Please login again.";
      return;
    }
    const data = await res.json();
    if(!res.ok || !data.ok){
      el.innerText = "Error: " + (data.error || ("HTTP " + res.status));
      return;
    }

    const orders = data.orders || [];
    try{ setMainEtaFromOrders(orders); }catch(e){}
    if(orders.length === 0){
      el.innerHTML = "<p class='small'>No orders yet.</p>";
      return;
    }

    let html = '<table class="table"><tr><th>Drink</th><th>Qty</th><th>Calories</th><th>Time</th></tr>';
    orders.slice().reverse().forEach(o=>{
      html += `<tr>
        <td>${o.drinkName || ''}</td>
        <td>${o.quantity || 1}</td>
        <td>${o.calories || 0}</td>
        <td>${o.ts || ''}</td>
      </tr>`;
    });
    html += '</table>';
    el.innerHTML = html;
  }catch(e){
    el.innerText = "History error: " + e;
  }
}
loadQueue();
loadHistory();
setInterval(loadQueue, 3000);
</script>
<div id="menuPopup" class="menu-popup" aria-live="polite"></div>

</div></body></html>
""")

    return HTMLResponse(tpl.safe_substitute(STYLE=STYLE, user=user))


@router.get("/drink-links", response_class=HTMLResponse)
def drink_links_page(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ensure_drinks_file()
    drinks = load_drinks()

    rows = "".join([
        f"<tr><td>{d.get('name','')}</td>"
        f"<td><span class='pill'>{d.get('calories',0)} cal</span></td>"
        f"<td><a href='/drink/{d.get('id')}'><b>/drink/{d.get('id')}</b></a></td></tr>"
        for d in drinks
    ])

    return HTMLResponse(f"""
    <html><head><title>Drink Links</title>{STYLE}</head>
    <body><div class='page'>
      <h1>DRINK LINKS</h1>
      <div class='card'>
        <div class='small'>Copy these links into Canva using your deployed domain.</div>
        <table class='table'>
          <tr><th>Drink</th><th>Calories</th><th>Link</th></tr>
          {rows}
        </table>
        <div class='btnrow' style='margin-top:14px'>
          <button class='secondary' onclick="window.location.href='/builder'">Back to Menu</button>
        </div>
      </div>
    </div></body></html>
    """)


@router.get("/recommendations", response_class=HTMLResponse)
def recommendations_page(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    top = _top_drinks_for_user(user, limit=3)
    top_html = "<p class='small'>No orders yet.</p>" if not top else "<ul>" + "".join(
        [f"<li style='color:#f5e6d3'>{n}</li>" for n in top]
    ) + "</ul>"

    recs = recommend_for_user(user, k=3)
    if not recs:
        rec_html = "<p class='small'>No recommendations yet.</p>"
    else:
        rec_html = "<ul>" + "".join([
            f"<li style='color:#f5e6d3'><b>{d.get('name')}</b> "
            f"<span class='pill' style='margin-left:8px'>{d.get('calories',0)} cal</span></li>"
            for d in recs
        ]) + "</ul>"

    return HTMLResponse(f"""
    <html><head><title>Recommendations</title>{STYLE}</head>
    <body><div class='page'>
      <h1>RECOMMENDATIONS</h1>
      <div class='card' style='margin-top:14px'>
        <h2>MOOD-BASED SUGGESTIONS</h2>
        <div class='small'>Pick a mood and we’ll re-rank drinks using ingredient clusters + your past orders.</div>
        <div class='btnrow' style='margin-top:10px'>
          <button class='secondary mood-btn' data-mood='chill' onclick="pickMood('chill')">Chill</button>
          <button class='secondary mood-btn' data-mood='energized' onclick="pickMood('energized')">Energized</button>
          <button class='secondary mood-btn' data-mood='sweet' onclick="pickMood('sweet')">Sweet</button>
          <button class='secondary mood-btn' data-mood='adventurous' onclick="pickMood('adventurous')">Adventurous</button>
          <button class='secondary' onclick="pickMood('')">Clear</button>
        </div>
        <div id="moodStatus" class='small' style='margin-top:10px; color:rgba(245,230,211,.9)'></div>
        <div id="moodRecs" style='margin-top:10px'></div>
      </div>

      <script>
        function esc(s){{ return (''+s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'); }}

        async function pickMood(mood){{
          const status = document.getElementById('moodStatus');
          const box = document.getElementById('moodRecs');
          box.innerHTML = "<p class='small'>Loading…</p>";
          status.textContent = (mood && mood !== 'none') ? ("Mood: " + mood) : "Mood: none";

          const url = (mood && mood !== 'none') ? ("/api/recommendations?mood=" + encodeURIComponent(mood) + "&k=3") : "/api/recommendations?k=3";
          try{{
            const res = await fetch(url);
            const data = await res.json();
            if(!data.ok){{ box.innerHTML = "<p class='small'>Could not load recommendations.</p>"; return; }}

            const recs = data.recommendations || [];
            if(!recs.length){{ box.innerHTML = "<p class='small'>No recommendations yet.</p>"; return; }}

            const lis = recs.map(function(d){{
              const name = esc(d.name || d.id || "Drink");
              const cal = esc((d.calories === undefined || d.calories === null) ? 0 : d.calories);
              const ings = Array.isArray(d.ingredients) ? d.ingredients.map(function(x){{ return esc((''+x).replaceAll('_',' ')); }}).join(', ') : "";
              const ingHtml = ings ? ("<div class='small' style='margin-top:6px'>Ingredients: " + ings + "</div>") : "";
              return "<li style='color:#f5e6d3; margin:10px 0'>" +
                       "<b>" + name + "</b>" +
                       "<span class='pill' style='margin-left:8px'>" + cal + " cal</span>" +
                       ingHtml +
                     "</li>";
            }}).join("");

            box.innerHTML = "<ul style='margin:10px 0 0 18px; padding:0'>" + lis + "</ul>";
          }}catch(e){{
            box.innerHTML = "<p class='small'>Error loading recommendations.</p>";
          }}
        }}
</script>

      <div class='grid cards'>
        <div class='card'>
          <h2>NEW DRINKS FOR YOU</h2>
          <div class='small'>Based on similar users + popularity.</div>
          {rec_html}
        </div>
        <div class='card'>
          <h2>YOUR TOP DRINKS</h2>
          <div class='small'>What you order the most.</div>
          {top_html}
        </div>
      </div>
      <div class='btnrow' style='margin-top:14px'>
        <button class='secondary' onclick="window.location.href='/builder'">Back to Menu</button>
      </div>
    </div></body></html>
    """)