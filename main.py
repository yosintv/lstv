import json, os, re, glob, time
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://yosintv.github.io"
# Force UTC to avoid server-time confusion
LOCAL_OFFSET = timezone(timedelta(hours=0)) 
NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 2. HELPERS ---
def slugify(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def force_write(relative_path, content):
    """Creates the exact path and writes index.html inside it."""
    full_path = os.path.join(BASE_DIR, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    # Logging for GitHub Actions
    if "index.html" in relative_path:
        print(f"✅ Generated: {relative_path}")

# --- 3. LOAD TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    t_path = os.path.join(BASE_DIR, f'{name}_template.html')
    if os.path.exists(t_path):
        with open(t_path, 'r', encoding='utf-8') as f:
            templates[name] = f.read()
    else:
        # Emergency recovery: creates a raw functional page if template is missing
        templates[name] = "<html><body><h1>{{FIXTURE}}{{CHANNEL_NAME}}</h1>{{WEEKLY_MENU}}{{MATCH_LISTING}}{{BROADCAST_ROWS}}{{FAQ_COUNTRY_ROWS}}</body></html>"

# --- 4. LOAD JSON DATA ---
all_matches = []
seen_ids = set()
# Search for JSON in 'date/' folder
json_files = glob.glob(os.path.join(BASE_DIR, "date", "*.json"))

for f in json_files:
    try:
        with open(f, 'r', encoding='utf-8') as j:
            data = json.load(j)
            if isinstance(data, dict): data = [data]
            for m in data:
                if m.get('match_id') and m['match_id'] not in seen_ids:
                    all_matches.append(m)
                    seen_ids.add(m['match_id'])
    except: continue

print(f"⚽ Matches found in JSON: {len(all_matches)}")
if not all_matches:
    print("❌ ERROR: No data found. HTML cannot be generated.")
    exit(1)

# --- 5. PAGE GENERATION ---
channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# 5a. MATCH PAGES (match/slug/date/index.html)
for m in all_matches:
    try:
        dt = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc)
        slug = slugify(m['fixture'])
        date_folder = dt.strftime('%Y%m%d')
        
        # Build Broadcast List
        rows = ""
        faq_html = ""
        for c in m.get('tv_channels', []):
            ch_list = c['channels']
            pills = " ".join([f'<a href="{DOMAIN}/channel/{slugify(ch)}/" style="color:blue;">{ch}</a>' for ch in ch_list])
            rows += f'<div style="margin-bottom:10px;"><b>{c["country"]}</b>: {pills}</div>'
            faq_html += f'<div><b>How to watch {m["fixture"]} in {c["country"]}?</b><p>Available on {", ".join(ch_list)}</p></div>'

        # Process Template
        m_html = templates['match'].replace("{{FIXTURE}}", m['fixture'])
        m_html = m_html.replace("{{BROADCAST_ROWS}}", rows)
        m_html = m_html.replace("{{FAQ_COUNTRY_ROWS}}", faq_html)
        m_html = m_html.replace("{{LOCAL_TIME}}", dt.strftime("%H:%M"))
        m_html = m_html.replace("{{LOCAL_DATE}}", dt.strftime("%d %b %Y"))
        m_html = m_html.replace("{{UNIX}}", str(m['kickoff']))
        m_html = m_html.replace("{{DOMAIN}}", DOMAIN)
        
        # TARGET PATH: match/fixture-slug/20260115/index.html
        path = f"match/{slug}/{date_folder}/index.html"
        force_write(path, m_html)
        sitemap_urls.append(f"{DOMAIN}/match/{slug}/{date_folder}/")

        # Map Channels for later
        for c in m.get('tv_channels', []):
            for ch in c['channels']:
                if ch not in channels_data: channels_data[ch] = []
                channels_data[ch].append(m)
    except: continue

# 5b. DAILY PAGES (index.html, 2026-01-15.html)
all_days = sorted({datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).date() for m in all_matches})
for day in all_days:
    file_name = "index.html" if day == TODAY_DATE else f"{day.strftime('%Y-%m-%d')}.html"
    
    day_matches = sorted([x for x in all_matches if datetime.fromtimestamp(int(x['kickoff']), tz=timezone.utc).date() == day], key=lambda x: x['kickoff'])
    
    match_list = ""
    for dm in day_matches:
        d_dt = datetime.fromtimestamp(int(dm['kickoff']), tz=timezone.utc)
        m_url = f"{DOMAIN}/match/{slugify(dm['fixture'])}/{d_dt.strftime('%Y%m%d')}/"
        match_list += f'<li><b>{d_dt.strftime("%H:%M")}</b> <a href="{m_url}">{dm["fixture"]}</a></li>'
    
    menu = " | ".join([f'<a href="{DOMAIN}/{"index.html" if d==TODAY_DATE else d.strftime("%Y-%m-%d")+".html"}">{d.strftime("%b %d")}</a>' for d in all_days[:7]])
    
    h_html = templates['home'].replace("{{MATCH_LISTING}}", f"<ul>{match_list}</ul>").replace("{{WEEKLY_MENU}}", menu)
    h_html = h_html.replace("{{DOMAIN}}", DOMAIN).replace("{{PAGE_TITLE}}", f"Live Football TV - {day}")
    force_write(file_name, h_html)

# 5c. CHANNEL PAGES (channel/slug/index.html)
for ch_name, m_list in channels_data.items():
    c_slug = slugify(ch_name)
    c_list = ""
    for mx in sorted(m_list, key=lambda x: x['kickoff']):
        mx_dt = datetime.fromtimestamp(int(mx['kickoff']), tz=timezone.utc)
        c_list += f'<li><a href="{DOMAIN}/match/{slugify(mx["fixture"])}/{mx_dt.strftime("%Y%m%d")}/">{mx["fixture"]}</a> ({mx_dt.strftime("%d %b")})</li>'
    
    c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name).replace("{{MATCH_LISTING}}", f"<ul>{c_list}</ul>").replace("{{DOMAIN}}", DOMAIN)
    force_write(f"channel/{c_slug}/index.html", c_html)

# 5d. SITEMAP
sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for url in set(sitemap_urls):
    sitemap += f'<url><loc>{url}</loc></url>'
sitemap += '</urlset>'
force_write("sitemap.xml", sitemap)

print("🏁 ALL PAGES GENERATED SUCCESSFULLY.")
