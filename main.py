import json, os, re, glob, time
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://tv.cricfoot.net"
LOCAL_OFFSET = timezone(timedelta(seconds=-time.timezone if time.daylight == 0 else -time.altzone))
NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

# Get absolute path of where main.py is running
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"🚀 Script starting. Working directory: {BASE_DIR}")

# --- 2. HELPERS ---
def slugify(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def safe_write(relative_path, content):
    """Forcefully creates directories and writes files."""
    full_path = os.path.join(BASE_DIR, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Created: {relative_path}")

# --- 3. LOAD TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    t_path = os.path.join(BASE_DIR, f'{name}_template.html')
    if os.path.exists(t_path):
        with open(t_path, 'r', encoding='utf-8') as f:
            templates[name] = f.read()
            print(f"📄 Loaded {name}_template.html")
    else:
        print(f"❌ ERROR: {name}_template.html NOT FOUND at {t_path}")
        # Create a basic fallback so the script doesn't crash
        templates[name] = "<html><body>{{MATCH_LISTING}}{{BROADCAST_ROWS}}{{FAQ_COUNTRY_ROWS}}</body></html>"

# --- 4. LOAD DATA (The 'Hook or Crook' Search) ---
all_matches = []
seen_ids = set()

# Search pattern: look inside 'date' folder in the root
json_files = glob.glob(os.path.join(BASE_DIR, "date", "*.json"))

print(f"🔍 Searching for JSON in: {os.path.join(BASE_DIR, 'date')}")

if not json_files:
    print("⚠️ No files in 'date/'. Checking current directory as fallback...")
    json_files = glob.glob(os.path.join(BASE_DIR, "*.json"))

for f in json_files:
    print(f"📦 Found JSON: {os.path.basename(f)}")
    try:
        with open(f, 'r', encoding='utf-8') as j:
            data = json.load(j)
            if isinstance(data, dict): data = [data] # Handle single match files
            for m in data:
                if m.get('match_id') and m['match_id'] not in seen_ids:
                    all_matches.append(m)
                    seen_ids.add(m['match_id'])
    except Exception as e:
        print(f"❌ Error reading {f}: {e}")

print(f"⚽ TOTAL MATCHES LOADED: {len(all_matches)}")

if len(all_matches) == 0:
    print("⛔ CRITICAL FAILURE: No data loaded. Check if future_scraper.py actually saved files.")
    exit(1)

# --- 5. GENERATION LOGIC ---
channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# Generate Match Pages
for m in all_matches:
    try:
        m_dt = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_slug = slugify(m['fixture'])
        m_date_str = m_dt.strftime('%Y%m%d')
        
        # Injects content into Match Template
        rows = ""
        faq_html = ""
        for c in m.get('tv_channels', []):
            ch_list = c['channels']
            pills = "".join([f'<a href="{DOMAIN}/channel/{slugify(ch)}/" class="ch-link">{ch}</a>' for ch in ch_list])
            rows += f'<div><b>{c["country"]}</b>: {pills}</div>'
            faq_html += f'<div class="faq"><b>How to watch in {c["country"]}?</b><p>Watch on {", ".join(ch_list)}</p></div>'

        m_html = templates['match'].replace("{{FIXTURE}}", m['fixture'])
        m_html = m_html.replace("{{BROADCAST_ROWS}}", rows).replace("{{FAQ_COUNTRY_ROWS}}", faq_html)
        m_html = m_html.replace("{{LOCAL_TIME}}", m_dt.strftime("%H:%M")).replace("{{UNIX}}", str(m['kickoff']))
        m_html = m_html.replace("{{DOMAIN}}", DOMAIN)
        
        safe_write(f"match/{m_slug}/{m_date_str}/index.html", m_html)
        sitemap_urls.append(f"{DOMAIN}/match/{m_slug}/{m_date_str}/")

        # Prep Channel Data
        for c in m.get('tv_channels', []):
            for ch in c['channels']:
                if ch not in channels_data: channels_data[ch] = []
                channels_data[ch].append(m)
    except Exception as e:
        print(f"⚠️ Error processing match {m.get('fixture')}: {e}")

# Generate Daily Pages (index.html, etc.)
ALL_DATES = sorted({datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() for m in all_matches})
for day in ALL_DATES:
    f_name = "index.html" if day == TODAY_DATE else f"{day.strftime('%Y-%m-%d')}.html"
    
    match_list_html = ""
    day_m = [x for x in all_matches if datetime.fromtimestamp(int(x['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() == day]
    for dm in sorted(day_m, key=lambda x: x['kickoff']):
        dt = datetime.fromtimestamp(int(dm['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        url = f"{DOMAIN}/match/{slugify(dm['fixture'])}/{dt.strftime('%Y%m%d')}/"
        match_list_html += f'<li>{dt.strftime("%H:%M")} <a href="{url}">{dm["fixture"]}</a></li>'
    
    # Simple nav menu
    menu_html = " ".join([f'<a href="{DOMAIN}/{"index.html" if d==TODAY_DATE else d.strftime("%Y-%m-%d")+".html"}">{d.strftime("%b %d")}</a>' for d in ALL_DATES[:7]])

    h_html = templates['home'].replace("{{MATCH_LISTING}}", f"<ul>{match_list_html}</ul>").replace("{{WEEKLY_MENU}}", menu_html)
    h_html = h_html.replace("{{DOMAIN}}", DOMAIN).replace("{{PAGE_TITLE}}", f"Schedule for {day}")
    safe_write(f_name, h_html)

# Finalizing
print("🗺️ Generating Sitemap...")
sitemap = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for url in list(set(sitemap_urls)):
    sitemap += f'<url><loc>{url}</loc></url>'
sitemap += '</urlset>'
safe_write("sitemap.xml", sitemap)

print("🏁 Finished! If you don't see files, check the 'TOTAL MATCHES LOADED' log above.")
