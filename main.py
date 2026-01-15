import json, os, re, glob, time, shutil
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://yosintv.github.io/psg"
LOCAL_OFFSET = timezone(timedelta(seconds=-time.timezone if time.daylight == 0 else -time.altzone))

# Directory management
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "dist_temp")

# Clean and create temp directory for the build process
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)

NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

# --- 2. HELPERS ---
def slugify(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def force_write(relative_path, content):
    """Writes the file into the temporary directory."""
    full_path = os.path.join(TEMP_DIR, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- 3. LOAD ORIGINAL TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    t_path = os.path.join(BASE_DIR, f'{name}_template.html')
    try:
        with open(t_path, 'r', encoding='utf-8') as f:
            templates[name] = f.read()
    except FileNotFoundError:
        print(f"❌ ERROR: {t_path} not found!")
        templates[name] = "{{WEEKLY_MENU}}{{MATCH_LISTING}}{{BROADCAST_ROWS}}"

# --- 4. LOAD DATA ---
all_matches = []
seen_match_ids = set()
json_files = glob.glob(os.path.join(BASE_DIR, "date", "*.json"))

for f in json_files:
    with open(f, 'r', encoding='utf-8') as j:
        try:
            data = json.load(j)
            if isinstance(data, dict): data = [data]
            for m in data:
                mid = m.get('match_id')
                if mid and mid not in seen_match_ids:
                    all_matches.append(m)
                    seen_match_ids.add(mid)
        except: continue

print(f"⚽ Matches loaded: {len(all_matches)}")
channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# --- 5. PAGE GENERATION ---

# 5a. Match Pages
for m in all_matches:
    try:
        m_dt = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_slug = slugify(m['fixture'])
        m_date_folder = m_dt.strftime('%Y%m%d')
        
        rows = ""
        faq_html = ""
        for c in m.get('tv_channels', []):
            ch_links = [f'<a href="{DOMAIN}/channel/{slugify(ch)}/">{ch}</a>' for ch in c['channels']]
            rows += f'<div><b>{c["country"]}</b>: {" ".join(ch_links)}</div>'
            faq_html += f'<div><b>How to watch {m["fixture"]} in {c["country"]}?</b><p>Available on {", ".join(c["channels"])}</p></div>'

        m_html = templates['match'].replace("{{FIXTURE}}", m['fixture'])
        m_html = m_html.replace("{{BROADCAST_ROWS}}", rows)
        m_html = m_html.replace("{{FAQ_COUNTRY_ROWS}}", faq_html)
        m_html = m_html.replace("{{LOCAL_DATE}}", m_dt.strftime("%d %b %Y"))
        m_html = m_html.replace("{{LOCAL_TIME}}", m_dt.strftime("%H:%M"))
        m_html = m_html.replace("{{UNIX}}", str(m['kickoff']))
        m_html = m_html.replace("{{DOMAIN}}", DOMAIN)
        
        force_write(f"match/{m_slug}/{m_date_folder}/index.html", m_html)
        sitemap_urls.append(f"{DOMAIN}/match/{m_slug}/{m_date_folder}/")

        for c in m.get('tv_channels', []):
            for ch in c['channels']:
                if ch not in channels_data: channels_data[ch] = []
                channels_data[ch].append(m)
    except: continue

# 5b. Daily Pages & Home Folder
ALL_DATES = sorted({datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() for m in all_matches})

menu_html = ""
for d in ALL_DATES:
    d_str = d.strftime('%Y-%m-%d')
    menu_html += f'<a href="{DOMAIN}/home/{d_str}.html">{d.strftime("%b %d")}</a> '

for day in ALL_DATES:
    day_str = day.strftime('%Y-%m-%d')
    day_matches = sorted([m for m in all_matches if datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() == day], key=lambda x: x['kickoff'])
    
    listing_html = ""
    for m in day_matches:
        dt_m = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_url = f"{DOMAIN}/match/{slugify(m['fixture'])}/{dt_m.strftime('%Y%m%d')}/"
        listing_html += f'<li>{dt_m.strftime("%H:%M")} <a href="{m_url}">{m["fixture"]}</a></li>'

    h_output = templates['home'].replace("{{MATCH_LISTING}}", f"<ul>{listing_html}</ul>").replace("{{WEEKLY_MENU}}", menu_html)
    h_output = h_output.replace("{{DOMAIN}}", DOMAIN).replace("{{PAGE_TITLE}}", f"Schedule for {day_str}")
    
    force_write(f"home/{day_str}.html", h_output)
    sitemap_urls.append(f"{DOMAIN}/home/{day_str}.html")
    if day == TODAY_DATE:
        force_write("index.html", h_output)

# 5c. Channel Pages
for ch_name, m_list in channels_data.items():
    c_slug = slugify(ch_name)
    c_listing = ""
    for m in sorted(m_list, key=lambda x: x['kickoff']):
        dt_m = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_url = f"{DOMAIN}/match/{slugify(m['fixture'])}/{dt_m.strftime('%Y%m%d')}/"
        c_listing += f'<li>{dt_m.strftime("%d %b %H:%M")} - <a href="{m_url}">{m["fixture"]}</a></li>'
    
    c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name).replace("{{MATCH_LISTING}}", f"<ul>{c_listing}</ul>").replace("{{DOMAIN}}", DOMAIN).replace("{{WEEKLY_MENU}}", menu_html)
    force_write(f"channel/{c_slug}/index.html", c_html)
    sitemap_urls.append(f"{DOMAIN}/channel/{c_slug}/")

# 5d. Sitemap
sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for url in sorted(set(sitemap_urls)):
    sitemap += f'<url><loc>{url}</loc><lastmod>{NOW.strftime("%Y-%m-%d")}</lastmod></url>'
sitemap += '</urlset>'
force_write("sitemap.xml", sitemap)

# --- 6. DEPLOYMENT (Clean Root Move) ---
print("📦 Build complete. Moving files to root...")
for root, dirs, files in os.walk(TEMP_DIR):
    for file in files:
        src = os.path.join(root, file)
        rel_path = os.path.relpath(src, TEMP_DIR)
        dest = os.path.join(BASE_DIR, rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)

shutil.rmtree(TEMP_DIR)
print("🏁 DONE. Root updated with all folders.")
