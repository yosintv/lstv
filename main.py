import json, os, re, glob, time
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://tv.cricfoot.net"
# Adjust to your system/target timezone
LOCAL_OFFSET = timezone(timedelta(seconds=-time.timezone if time.daylight == 0 else -time.altzone))

NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

# The weekly menu will start 3 days ago and show 7 days total (Today in the middle)
MENU_START_DATE = TODAY_DATE - timedelta(days=3)
TOP_LEAGUE_IDS = [17, 35, 23, 7, 8, 34, 679]

ADS_CODE = '<div class="ad-container" style="margin: 20px 0; text-align: center;"></div>'

# --- 2. HELPERS ---
def slugify(t): 
    # Standard slugging: Lowercase, alphanumeric, and hyphens only
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def safe_write(path, content):
    """Writes content to a file. Automatically creates folders (match/team/date/) if they don't exist."""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- 3. LOAD TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    try:
        with open(f'{name}_template.html', 'r', encoding='utf-8') as f:
            templates[name] = f.read()
    except FileNotFoundError:
        print(f"CRITICAL: {name}_template.html is missing. Place it in the root.")

# --- 4. LOAD DATA ---
all_matches = []
seen_match_ids = set()
for f in glob.glob("date/*.json"):
    with open(f, 'r', encoding='utf-8') as j:
        try:
            data = json.load(j)
            for m in data:
                mid = m.get('match_id')
                if mid and mid not in seen_match_ids:
                    all_matches.append(m)
                    seen_match_ids.add(mid)
        except: continue

channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# --- 5. GENERATE MATCH PAGES (match/fixture/date/index.html) ---
print("Building Match Pages...")
for m in all_matches:
    m_dt_local = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
    m_slug = slugify(m['fixture'])
    m_date_folder = m_dt_local.strftime('%Y%m%d')
    
    # This creates: https://tv.cricfoot.net/match/team-vs-team/20260115/index.html
    m_path = f"match/{m_slug}/{m_date_folder}/index.html"
    sitemap_urls.append(f"{DOMAIN}/match/{m_slug}/{m_date_folder}/")

    rows = ""
    faq_html = ""
    for c in m.get('tv_channels', []):
        ch_list = c['channels']
        pills = "".join([f'<a href="{DOMAIN}/channel/{slugify(ch)}/" class="channel-link">{ch}</a>' for ch in ch_list])
        
        # Rows for the match details table
        rows += f'<div class="channel-row"><strong>{c["country"]}</strong>: {pills}</div>'
        
        # Country-specific FAQ logic
        faq_html += f'''
        <div class="faq-card">
            <p><strong>How to watch {m['fixture']} in {c["country"]}?</strong></p>
            <p>In {c["country"]}, you can stream the match live on <b>{", ".join(ch_list)}</b>.</p>
        </div>'''

    m_html = templates['match'].replace("{{FIXTURE}}", m['fixture']).replace("{{DOMAIN}}", DOMAIN)
    m_html = m_html.replace("{{BROADCAST_ROWS}}", rows).replace("{{FAQ_COUNTRY_ROWS}}", faq_html)
    m_html = m_html.replace("{{LOCAL_TIME}}", m_dt_local.strftime("%H:%M")).replace("{{UNIX}}", str(m['kickoff']))
    
    safe_write(m_path, m_html)

    # Prepare data for channel pages
    for c in m.get('tv_channels', []):
        for ch in c['channels']:
            if ch not in channels_data: channels_data[ch] = []
            channels_data[ch].append({'m': m, 'dt': m_dt_local})

# --- 6. GENERATE DAILY PAGES (2026-01-14.html) ---
print("Building Daily Listing Pages...")
ALL_DATES = sorted({datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() for m in all_matches})

for day in ALL_DATES:
    # Logic: Today is index.html, other days are YYYY-MM-DD.html
    filename = "index.html" if day == TODAY_DATE else f"{day.strftime('%Y-%m-%d')}.html"
    if day != TODAY_DATE: sitemap_urls.append(f"{DOMAIN}/{filename}")

    # Build the 7-day navigation menu
    menu_html = '<div class="weekly-menu">'
    for i in range(7):
        d = MENU_START_DATE + timedelta(days=i)
        d_filename = "index.html" if d == TODAY_DATE else f"{d.strftime('%Y-%m-%d')}.html"
        active = "active" if d == day else ""
        menu_html += f'<a href="{DOMAIN}/{d_filename}" class="btn {active}">{d.strftime("%b %d")}</a>'
    menu_html += '</div>'

    # Filter and sort matches for this specific day
    day_matches = [m for m in all_matches if datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() == day]
    day_matches.sort(key=lambda x: x['kickoff'])

    listing_html = ""
    for dm in day_matches:
        dm_dt = datetime.fromtimestamp(int(dm['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_link = f"{DOMAIN}/match/{slugify(dm['fixture'])}/{dm_dt.strftime('%Y%m%d')}/"
        listing_html += f'<a href="{m_link}" class="match-item"><b>{dm_dt.strftime("%H:%M")}</b> {dm["fixture"]}</a>'

    page_html = templates['home'].replace("{{MATCH_LISTING}}", listing_html).replace("{{WEEKLY_MENU}}", menu_html)
    page_html = page_html.replace("{{PAGE_TITLE}}", f"TV Schedule for {day.strftime('%A, %b %d')}")
    
    safe_write(filename, page_html)

# --- 7. GENERATE CHANNEL PAGES (channel/espn/index.html) ---
print("Building Channel Pages...")
for ch_name, matches in channels_data.items():
    c_slug = slugify(ch_name)
    c_path = f"channel/{c_slug}/index.html"
    sitemap_urls.append(f"{DOMAIN}/channel/{c_slug}/")

    c_list_html = ""
    for item in sorted(matches, key=lambda x: x['m']['kickoff']):
        m, dt = item['m'], item['dt']
        m_link = f"{DOMAIN}/match/{slugify(m['fixture'])}/{dt.strftime('%Y%m%d')}/"
        c_list_html += f'<a href="{m_link}">{m["fixture"]} ({dt.strftime("%d %b %H:%M")})</a>'

    c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name).replace("{{MATCH_LISTING}}", c_list_html).replace("{{DOMAIN}}", DOMAIN)
    safe_write(c_path, c_html)

# --- 8. SITEMAP ---
print("Finalizing Sitemap...")
sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for url in sorted(list(set(sitemap_urls))):
    sitemap += f'<url><loc>{url}</loc><lastmod>{NOW.strftime("%Y-%m-%d")}</lastmod></url>'
sitemap += '</urlset>'
safe_write("sitemap.xml", sitemap)

print("✅ Success! Your site structure is ready.")
