import streamlit as st
import requests
import urllib.parse
import re
from difflib import SequenceMatcher

st.set_page_config(page_title="AI News Detector", page_icon="📰", layout="wide")

# ---------- HTML HEADER (plain, no fancy fonts, no ampersand) ----------
st.markdown("""
<div style="text-align: center; margin-top: 1rem; margin-bottom: 0.5rem;">
    <h1 style="font-size: 4rem; font-weight: 900; 
               background: linear-gradient(135deg, #00d2ff, #7b2ff7, #ff6b6b); 
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;
               font-family: 'Inter', sans-serif;">
        AI News Detector
    </h1>
    <p style="color: #aaa; font-size: 1rem;">⚡ Live Wikipedia · Fake / Real / Ad · TRP Score</p>
</div>
""", unsafe_allow_html=True)

# ---------- KNOWLEDGE BASE (unchanged) ----------
WIKI_KB = {
    "2011 cricket world cup": {
        "title": "2011 ICC Cricket World Cup",
        "summary": "India won the 2011 ICC Cricket World Cup on April 2, 2011, defeating Sri Lanka by 6 wickets in the final at Wankhede Stadium, Mumbai. MS Dhoni hit the winning six.",
        "url": "https://en.wikipedia.org/wiki/2011_ICC_Cricket_World_Cup",
        "aliases": ["india won world cup", "cricket world cup 2011", "dhoni six", "wankhede final"]
    },
    "moon landing": {
        "title": "Apollo 11",
        "summary": "Apollo 11 landed the first humans on the Moon on July 20, 1969. Neil Armstrong and Buzz Aldrin walked on the lunar surface.",
        "url": "https://en.wikipedia.org/wiki/Apollo_11",
        "aliases": ["first moon landing", "neil armstrong", "1969 moon"]
    },
    "covid vaccine": {
        "title": "COVID-19 Vaccine",
        "summary": "COVID-19 vaccines from Pfizer, Moderna, AstraZeneca provide immunity against SARS-CoV-2. Approved by WHO.",
        "url": "https://en.wikipedia.org/wiki/COVID-19_vaccine",
        "aliases": ["pfizer vaccine", "moderna", "corona vaccine"]
    },
    "elon musk": {
        "title": "Elon Musk",
        "summary": "Elon Musk is CEO of Tesla and SpaceX, owner of X. No verified reports of arrest.",
        "url": "https://en.wikipedia.org/wiki/Elon_Musk",
        "aliases": ["tesla ceo", "spacex", "elon"]
    },
    "drink bleach": {
        "title": "Miracle Mineral Supplement Hoax",
        "summary": "Drinking bleach or MMS is extremely dangerous. FDA and WHO warn it causes severe burns and death.",
        "url": "https://en.wikipedia.org/wiki/Miracle_Mineral_Supplement",
        "aliases": ["bleach cure", "mms", "miracle mineral"]
    },
    "flat earth": {
        "title": "Flat Earth",
        "summary": "Earth is an oblate spheroid, proven by satellite imagery. Flat Earth is pseudoscience.",
        "url": "https://en.wikipedia.org/wiki/Flat_Earth",
        "aliases": ["earth is flat", "globe earth hoax"]
    }
}

def fuzzy_match(query, text_list):
    query_lower = query.lower()
    best = 0
    for text in text_list:
        ratio = SequenceMatcher(None, query_lower, text.lower()).ratio()
        best = max(best, ratio)
    return best

def get_wikipedia_info(query):
    query_clean = query.strip().lower()
    # Live API
    try:
        headers = {"User-Agent": "AI-News-Detector/1.0"}
        search_params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query_clean,
            "srlimit": 1
        }
        resp = requests.get("https://en.wikipedia.org/w/api.php", params=search_params, headers=headers, timeout=6)
        data = resp.json()
        if data.get("query", {}).get("search"):
            title = data["query"]["search"][0]["title"]
            encoded = urllib.parse.quote(title.replace(" ", "_"))
            summary_resp = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}", headers=headers, timeout=6)
            if summary_resp.status_code == 200:
                summ_data = summary_resp.json()
                summary = summ_data.get("extract", "No summary available.")
                if len(summary) > 800:
                    summary = summary[:800] + "..."
                return {"found": True, "title": title, "summary": summary, "url": f"https://en.wikipedia.org/wiki/{encoded}", "source": "live"}
    except:
        pass
    
    best_match = None
    best_score = 0
    for key, data in WIKI_KB.items():
        texts_to_match = [key] + data.get("aliases", [])
        score = fuzzy_match(query_clean, texts_to_match)
        if score > best_score and score > 0.5:
            best_score = score
            best_match = data
    if best_match:
        return {**best_match, "found": True, "source": "knowledge base"}
    return {"found": False}

# ---------- FAKE/REAL/AD DETECTION ----------
FAKE_W = {"shocking":3, "viral":2, "secret":3, "exposed":3, "click here":4, "you won't believe":5, "miracle cure":5, "banned":2, "share before deleted":6, "urgent":2, "doctors hate":5, "government hiding":4, "microchip":3, "chemtrails":5, "deep state":4, "drink bleach":8}
REAL_W = {"according to":3, "study shows":3, "researchers found":3, "official":3, "confirmed by":3, "reported by":2, "data shows":3, "published in":3, "university":2, "nasa":2, "bcci":3}
AD_W = {"buy now":4, "limited offer":4, "discount":3, "sale":2, "subscribe":3, "free trial":4, "sponsored":5, "advertisement":5, "shop now":4, "% off":4}

def analyze_text(text):
    t = text.lower()
    fs = sum(v for k,v in FAKE_W.items() if k in t)
    rs = sum(v for k,v in REAL_W.items() if k in t)
    ads = sum(v for k,v in AD_W.items() if k in t)
    
    if ads >= 6:
        label = "AD"
    elif fs >= 8:
        label = "FAKE"
    elif fs >= 4 and rs - fs < 0:
        label = "FAKE"
    elif rs - fs >= 8:
        label = "REAL"
    elif rs - fs >= 3:
        label = "LIKELY REAL"
    elif rs - fs <= -3:
        label = "LIKELY FAKE"
    else:
        label = "SUSPICIOUS"
    
    gap = abs(rs - fs)
    conf = 95 if gap >= 12 else 88 if gap >= 8 else 78 if gap >= 5 else 65
    trp = min(40 + len(text)//30 + ads + fs, 98)
    return label, conf, trp, fs, rs, ads

# ---------- UI ----------
st.markdown('<div style="max-width: 800px; margin: 0 auto;">', unsafe_allow_html=True)
user_input = st.text_area("📝 Enter news, headline, or ad copy", height=100,
                         placeholder="e.g., India won the 2011 Cricket World Cup final")
col1, col2, col3 = st.columns([1,2,1])
with col2:
    analyze = st.button("🔍 Analyze Now", type="primary", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

if analyze and user_input.strip():
    with st.spinner("🔎 Checking Wikipedia & analyzing..."):
        wiki = get_wikipedia_info(user_input)
        label, conf, trp, fs, rs, ads = analyze_text(user_input)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="card metric-card">', unsafe_allow_html=True)
        st.markdown('<h4 style="color:#94a3b8;">VERDICT</h4>', unsafe_allow_html=True)
        badge_class = "real" if "REAL" in label else "fake" if "FAKE" in label else "ad" if label=="AD" else "susp"
        st.markdown(f'<div class="badge {badge_class}">{label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value">{conf}%</div>', unsafe_allow_html=True)
        st.markdown('<div class="metric-label">Confidence</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with c2:
        st.markdown('<div class="card metric-card">', unsafe_allow_html=True)
        st.markdown('<h4 style="color:#94a3b8;">📺 TRP SCORE</h4>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value" style="color:#7b2ff7">{trp}%</div>', unsafe_allow_html=True)
        eng = "🔥 High" if trp>75 else "📈 Medium" if trp>50 else "📉 Low"
        st.markdown(f'<div class="metric-label">{eng} Engagement</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with c3:
        st.markdown('<div class="card metric-card">', unsafe_allow_html=True)
        st.markdown('<h4 style="color:#94a3b8;">SIGNALS</h4>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value" style="color:#ef4444">F:{fs}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value" style="color:#10b981">R:{rs}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value" style="color:#8b5cf6">A:{ads}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    if wiki["found"]:
        source = wiki.get("source", "unknown")
        st.markdown(f"""
        <div class="wiki-card" style="background:#0d1117; border-left:4px solid #00d2ff; border-radius:8px; padding:1.2rem 1.5rem; color:#ccc; margin:1rem 0;">
            <div style="font-size:1.1rem; font-weight:700; color:#00d2ff; margin-bottom:0.8rem;">✅ {source}</div>
            <div><strong>{wiki['title']}</strong><br>{wiki['summary']}</div>
            <div style="margin-top:0.8rem;">
                <a href="{wiki['url']}" target="_blank" style="color:#00d2ff; font-weight:600;">📖 Read full article on Wikipedia →</a>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="wiki-card" style="background:#0d1117; border-left:4px solid #ff6b6b; border-radius:8px; padding:1.2rem 1.5rem; color:#ccc; margin:1rem 0;">
            <div style="font-size:1.1rem; font-weight:700; color:#ff6b6b; margin-bottom:0.8rem;">⚠️ No Wikipedia Match</div>
            <div>This topic was not found in live Wikipedia or our knowledge base. Higher risk of misinformation.</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<hr style="border-color:#1f2635; margin:1.5rem 0;">', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;color:#64748b;font-size:0.85rem;">Powered by live Wikipedia API + fallback knowledge base</p>', unsafe_allow_html=True)
