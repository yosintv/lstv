import json, os, re, glob, time
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://tv.cricfoot.net"
LOCAL_OFFSET = timezone(timedelta(seconds=-time.timezone if time.daylight == 0 else -time.altzone))
NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()
MENU_START_DATE = TODAY_DATE - timedelta(days=3)

# Get current script directory for reliable pathing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 2. HELPERS ---
def slugify(t): 
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def safe_write(path, content):
    """Ensures directories exist and writes file."""
    full_path = os.path.join(BASE_DIR, path)
    directory = os.path.dirname(full_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- 3. LOAD TEMPLATES ---
templates = {}
template_files = ['home', 'match', 'channel']
for name in template_files:
    t_path = os.path.join(BASE_DIR, f'{name}_template.html')
    try:
        with open(t_path, 'r', encoding='utf-8') as f:
            templates[name] = f.read()
            print(f"✅ Loaded {name}_template.html")
    except FileNotFoundError:
        print(f"❌ CRITICAL: {name}_template.html missing at {t_path}")
        # Create a emergency fallback to prevent crash
        templates[name] = "<html><body><h1>Missing Template</h1>{{MATCH_LISTING}}{{BROADCAST_ROWS}}{{FAQ_COUNTRY_ROWS}}</body></html>"

# --- 4. LOAD DATA ---
all_matches = []
seen_match_ids = set()
date_path = os.path.join(BASE_DIR, "date/*.json")
json_files = glob.glob(date_path)

print(f"🔍 Searching for JSON in: {date_path}")
print(f"📂 Found {len(json_files)} JSON files.")

for f in json_files:
    with open(f, 'r', encoding='utf-8') as j:
        try:
            data = json.load(j)
            for m in data:
                mid = m.get('match_id')
                if mid and mid not in seen_match_ids:
                    all_matches.append(m)
                    seen_match_ids.add(mid)
        except Exception as e:
            print(f"⚠️ Error reading {f}: {e}")

print(f"⚽ Total Unique Matches Loaded: {len(all_matches)}")

if not all_matches:
    print("⛔ No matches found. Ending script to prevent blank pages.")
    exit()

channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# --- 5. GENERATE MATCH PAGES ---
print("🚀 Building Match Pages...")
for m in all_matches:
    m_dt_local = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
    m_slug = slugify(m['fixture'])
    m_date_folder = m_dt_local.strftime('%Y%m%d')
    
    m_path = f"match/{m_slug}/{m_date_folder}/index.html"
    sitemap_urls.append(f"{DOMAIN}/match/{m_slug}/{m_date_folder}/")

    rows = ""
    faq_html = ""
    for c in m.get('tv_channels', []):
        ch_list = c['channels']
        pills = "".join([f'<a href="{DOMAIN}/channel/{slugify(ch)}/" class="channel-link" style="margin-right:5px; color:#2563eb;">{ch}</a>' for ch in ch_list])
        rows += f'<div class="broadcast-row" style="padding:10px; border-bottom:1px solid #eee;"><b>{c["country"]}</b>: {pills}</div>'
        
        faq_html += f'''
        <div class="faq-item">
            <div class="faq-question">How to watch {m['fixture']} in {c["country"]}?</div>
            <div class="faq-answer">In {c["country"]}, you can stream {m['fixture']} live on <b>{", ".join(ch_list)}</b>.</div>
        </div>'''

    # Support all placeholders from your specific template
    m_html = templates['match'].replace("{{FIXTURE}}", m['fixture'])
    m_html = m_html.replace("{{DOMAIN}}", DOMAIN)
    m_html = m_html.replace("{{LEAGUE}}", m.get('league', 'Football'))
    m_html = m_html.replace("{{VENUE}}", m.get('venue', 'TBA'))
    m_html = m_html.replace("{{LOCAL_DATE}}", m_dt_local.strftime("%d %b %Y"))
    m_html = m_html.replace("{{LOCAL_TIME}}", m_dt_local.strftime("%H:%M"))
    m_html = m_html.replace("{{UNIX}}", str(m['kickoff']))
    m_html = m_html.replace("{{BROADCAST_ROWS}}", rows)
    m_html = m_html.replace("{{FAQ_COUNTRY_ROWS}}", faq_html)
    
    safe_write(m_path, m_html)

    for c in m.get('tv_channels', []):
        for ch in c['channels']:
            if ch not in channels_data: channels_data[ch] = []
            channels_data[ch].append({'m': m, 'dt': m_dt_local})

# --- 6. GENERATE DAILY PAGES ---
print("📅 Building Daily Listing Pages...")
ALL_DATES = sorted({datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() for m in all_matches})

for day in ALL_DATES:
    filename = "index.html" if day == TODAY_DATE else f"{day.strftime('%Y-%m-%d')}.html"
    if day != TODAY_DATE: sitemap_urls.append(f"{DOMAIN}/{filename}")

    menu_html = '<div class="weekly-menu" style="display:flex; gap:10px; overflow-x:auto; padding:10px;">'
    for i in range(7):
        d = MENU_START_DATE + timedelta(days=i)
        d_filename = "index.html" if d == TODAY_DATE else f"{d.strftime('%Y-%m-%d')}.html"
        active_style = "background:#2563eb; color:#white;" if d == day else "background:#eee;"
        menu_html += f'<a href="{DOMAIN}/{d_filename}" style="padding:10px; text-decoration:none; border-radius:5px; {active_style}">{d.strftime("%b %d")}</a>'
    menu_html += '</div>'

    day_matches = [m for m in all_matches if datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() == day]
    day_matches.sort(key=lambda x: x['kickoff'])

    listing_html = ""
    for dm in day_matches:
        dm_dt = datetime.fromtimestamp(int(dm['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_link = f"{DOMAIN}/match/{slugify(dm['fixture'])}/{dm_dt.strftime('%Y%m%d')}/"
        listing_html += f'<div style="padding:15px; border-bottom:1px solid #eee;"><a href="{m_link}" style="text-decoration:none; color:#1e293b;"><b>{dm_dt.strftime("%H:%M")}</b> {dm["fixture"]}</a></div>'

    page_html = templates['home'].replace("{{MATCH_LISTING}}", listing_html).replace("{{WEEKLY_MENU}}", menu_html)
    page_html = page_html.replace("{{PAGE_TITLE}}", f"TV Schedule - {day.strftime('%b %d')}")
    page_html = page_html.replace("{{DOMAIN}}", DOMAIN)
    
    safe_write(filename, page_html)

# --- 7. GENERATE CHANNEL PAGES ---
print("📺 Building Channel Pages...")
for ch_name, matches in channels_data.items():
    c_slug = slugify(ch_name)
    c_path = f"channel/{c_slug}/index.html"
    sitemap_urls.append(f"{DOMAIN}/channel/{c_slug}/")

    c_list_html = ""
    for item in sorted(matches, key=lambda x: x['m']['kickoff']):
        m, dt = item['m'], item['dt']
        m_link = f"{DOMAIN}/match/{slugify(m['fixture'])}/{dt.strftime('%Y%m%d')}/"
        c_list_html += f'<div style="padding:10px; border-bottom:1px solid #eee;"><a href="{m_link}">{m["fixture"]}</a> - {dt.strftime("%d %b %H:%M")}</div>'

    c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name).replace("{{MATCH_LISTING}}", c_list_html).replace("{{DOMAIN}}", DOMAIN)
    safe_write(c_path, c_html)

# --- 8. SITEMAP ---
print("🗺️ Finalizing Sitemap...")
sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for url in sorted(list(set(sitemap_urls))):
    sitemap += f'<url><loc>{url}</loc><lastmod>{NOW.strftime("%Y-%m-%d")}</lastmod></url>'
sitemap += '</urlset>'
safe_write("sitemap.xml", sitemap)

print("✅ Build Complete! Check your repo for new folders and files.")
