"""
rebuild_site.py
Scans all PDF brochures, extracts key info, rebuilds all index.html files
and updates packages.json. Run via GitHub Actions on every push.
"""

import os
import re
import json
from datetime import datetime
import fitz  # PyMuPDF

# ── CONFIG ────────────────────────────────────────────────────────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOLDER_CONFIG = {
    "city-break": {"title": "City Breaks Packages", "breadcrumb": "City Breaks", "region": "City Break", "parent_depth": 1},
    "multi-country/italy": {"title": "Italy", "breadcrumb": "Italy", "region": "Italy", "parent_depth": 2},
    "multi-country/eastern-europe": {"title": "Eastern Europe", "breadcrumb": "Eastern Europe", "region": "Eastern Europe", "parent_depth": 2},
    "multi-country/france": {"title": "France", "breadcrumb": "France", "region": "France", "parent_depth": 2},
    "multi-country/scandinavia-iceland": {"title": "Scandinavia & Iceland", "breadcrumb": "Scandinavia & Iceland", "region": "Scandinavia & Iceland", "parent_depth": 2},
    "multi-country/spain-portugal": {"title": "Spain & Portugal", "breadcrumb": "Spain & Portugal", "region": "Spain & Portugal", "parent_depth": 2},
    "multi-country/switzerland": {"title": "Switzerland", "breadcrumb": "Switzerland", "region": "Switzerland", "parent_depth": 2},
    "multi-country/uk-ireland": {"title": "UK & Ireland", "breadcrumb": "UK & Ireland", "region": "UK & Ireland", "parent_depth": 2},
    "multi-country/western-central-europe": {"title": "Western & Central Europe", "breadcrumb": "Western & Central Europe", "region": "Western & Central Europe", "parent_depth": 2},
}

CITY_COORDS = {
    "Amsterdam": [52.3676, 4.9041], "Athens": [37.9838, 23.7275], "Barcelona": [41.3851, 2.1734],
    "Berlin": [52.5200, 13.4050], "Brussels": [50.8503, 4.3517], "Budapest": [47.4979, 19.0402],
    "Copenhagen": [55.6761, 12.5683], "Dublin": [53.3498, -6.2603], "Edinburgh": [55.9533, -3.1883],
    "Florence": [43.7696, 11.2558], "Frankfurt": [50.1109, 8.6821], "Geneva": [46.2044, 6.1432],
    "Glasgow": [55.8642, -4.2518], "Helsinki": [60.1699, 24.9384], "Innsbruck": [47.2692, 11.4041],
    "Interlaken": [46.6863, 7.8632], "Lisbon": [38.7223, -9.1393], "London": [51.5074, -0.1278],
    "Lucerne": [47.0502, 8.3093], "Madrid": [40.4168, -3.7038], "Milan": [45.4654, 9.1859],
    "Munich": [48.1351, 11.5820], "Nice": [43.7102, 7.2620], "Oslo": [59.9139, 10.7522],
    "Paris": [48.8566, 2.3522], "Prague": [50.0755, 14.4378], "Rome": [41.9028, 12.4964],
    "Salzburg": [47.8095, 13.0550], "Stockholm": [59.3293, 18.0686], "Venice": [45.4408, 12.3155],
    "Vienna": [48.2082, 16.3738], "Zurich": [47.3769, 8.5417], "Bergen": [60.3913, 5.3221],
    "Reykjavik": [64.1265, -21.8174], "Inverness": [57.4778, -4.2247], "Mykonos": [37.4467, 25.3289],
    "Santorini": [36.3932, 25.4615], "Manchester": [53.4808, -2.2426], "Fort William": [56.8198, -5.1052],
    "Limerick": [52.6638, -8.6267], "Galway": [53.2707, -9.0568], "Cork": [51.8985, -8.4756],
    "Bayeux": [49.2764, -0.7024], "Tours": [47.3941, 0.6848], "Lyon": [45.7640, 4.8357],
    "Bordeaux": [44.8378, -0.5792], "Strasbourg": [48.5734, 7.7521], "Marseille": [43.2965, 5.3698],
    "Avignon": [43.9493, 4.8055], "Montreux": [46.4312, 6.9107], "Zermatt": [46.0207, 7.7491],
    "Bern": [46.9480, 7.4474], "Naples": [40.8518, 14.2681], "Turin": [45.0703, 7.6869],
    "Bologna": [44.4949, 11.3426], "Pisa": [43.7228, 10.4017], "Siena": [43.3186, 11.3307],
    "Cagliari": [39.2238, 9.1217], "Cala Gonone": [40.2833, 9.6167], "Alghero": [40.5594, 8.3197],
    "Olbia": [40.9167, 9.5000], "Villasimius": [39.1333, 9.5167], "Bosa": [40.2981, 8.4983],
    "Ajaccio": [41.9192, 8.7386], "Corte": [42.3069, 9.1497], "Bonifacio": [41.3871, 9.1597],
    "Seville": [37.3891, -5.9845], "Granada": [37.1773, -3.5986], "Valencia": [39.4699, -0.3763],
    "Porto": [41.1579, -8.6291], "Sintra": [38.7977, -9.3877], "Coimbra": [40.2033, -8.4103],
    "Cologne": [50.9333, 6.9500], "Hamburg": [53.5753, 10.0153], "Dresden": [51.0504, 13.7373],
    "Dusseldorf": [51.2217, 6.7762], "Krakow": [50.0647, 19.9450], "Warsaw": [52.2297, 21.0122],
    "Bratislava": [48.1486, 17.1077], "Ljubljana": [46.0569, 14.5058], "Dubrovnik": [42.6507, 18.0944],
    "Bruges": [51.2093, 3.2247], "Ghent": [51.0543, 3.7174], "Rotterdam": [51.9244, 4.4777],
    "Luxembourg": [49.6117, 6.1319], "Antwerp": [51.2194, 4.4025],
}

GEO_BLOCK_SCRIPT = """<script>
(async function() {
    try {
        const r = await fetch('https://api.country.is/');
        const d = await r.json();
        if (['US','CA','AU','NZ'].includes(d.country)) {
            document.body.innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,sans-serif;background:#f5f5f5;text-align:center;padding:20px;"><h1 style="font-size:48px;margin-bottom:16px;">🌍</h1><h2 style="font-size:32px;font-weight:600;margin-bottom:12px;">Service Not Available</h2><p style="font-size:18px;color:#757575;">This site is not available in your region.</p></div>';
        }
    } catch(e) {}
})();
</script>"""

GA_SCRIPT = """<script async src="https://www.googletagmanager.com/gtag/js?id=G-04BZKH6574"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-04BZKH6574');
</script>"""

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #212121; line-height: 1.6; padding-top: 80px; }
.top-nav { position: fixed; top: 0; left: 0; right: 0; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); z-index: 1000; padding: 16px 0; }
.nav-container { max-width: 1200px; margin: 0 auto; padding: 0 24px; display: flex; align-items: center; gap: 32px; }
.logo { height: 48px; width: auto; }
.logo:hover { opacity: 0.8; }
.header-right { display: flex; align-items: center; gap: 32px; flex: 1; justify-content: flex-end; }
.site-title-group { text-align: right; }
.site-title-main { font-size: 1.1em; font-weight: 600; color: #212121; }
.site-title-sub { font-size: 0.9em; color: #757575; }
.contact-info { text-align: right; padding-left: 32px; border-left: 1px solid #e0e0e0; }
.contact-prompt { font-size: 0.85em; color: #757575; margin-bottom: 4px; }
.contact-email { font-size: 0.9em; color: #2196F3; text-decoration: none; font-weight: 500; }
.contact-email:hover { text-decoration: underline; }
.search-box { width: 100%; max-width: 350px; padding: 10px 18px; font-size: 0.95em; border: 1px solid #e0e0e0; border-radius: 24px; background: #fafafa; transition: all 0.2s; }
.search-box::placeholder { text-align: center; }
.search-box:focus { outline: none; border-color: #2196F3; background: white; box-shadow: 0 2px 8px rgba(33,150,243,0.15); }
.breadcrumb { max-width: 1200px; margin: 0 auto; padding: 24px 24px 0; font-size: 0.9em; color: #757575; }
.breadcrumb a { color: #2196F3; text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.container { max-width: 1200px; margin: 0 auto; padding: 32px 24px 48px; }
h1 { font-size: 2.2em; font-weight: 600; color: #212121; margin-bottom: 32px; letter-spacing: -0.5px; }
.brochures { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.brochure-card { background: white; border-radius: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); transition: all 0.3s cubic-bezier(0.4,0,0.2,1); text-decoration: none; color: inherit; display: flex; flex-direction: row; border: 1px solid #ebebeb; overflow: hidden; min-height: 180px; }
.brochure-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.11); border-color: #d0d0d0; }
.card-info { flex: 1; padding: 20px 20px 16px; display: flex; flex-direction: column; gap: 5px; }
.card-title { font-size: 1.0em; font-weight: 700; color: #1a1a1a; line-height: 1.3; }
.tour-type { font-size: 0.72em; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; color: #c62828; }
.card-pills { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 2px; }
.pill { font-size: 0.71em; font-weight: 600; padding: 3px 9px; border-radius: 20px; }
.pill-duration { background: #f3f3f3; color: #444; }
.pill-summer { background: #fff8e1; color: #e65100; }
.pill-winter { background: #e8f4fd; color: #0277bd; }
.pill-allyear { background: #e8f5e9; color: #2e7d32; }
.card-description { font-size: 0.8em; color: #777; font-style: italic; line-height: 1.4; }
.cities-list { font-size: 0.79em; color: #555; }
.price-tag { font-size: 0.88em; color: #2e7d32; font-weight: 700; margin-top: auto; padding-top: 6px; }
.pdf-badge { display: inline-block; font-size: 0.65em; font-weight: 700; color: #d32f2f; border: 1.5px solid #d32f2f; padding: 1px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle; }
.card-map { width: 175px; min-width: 175px; background: #dce8f5; border-left: 1px solid #ebebeb; position: relative; overflow: hidden; }
.card-map svg { width: 100%; height: 100%; }
footer { text-align: center; margin-top: 60px; padding: 32px 0; color: #9e9e9e; font-size: 0.9em; border-top: 1px solid #e8e8e8; }
@media (max-width: 900px) { .brochures { grid-template-columns: 1fr; } .card-map { width: 140px; min-width: 140px; } }
@media (max-width: 768px) { body { padding-top: 180px; } .nav-container { flex-wrap: wrap; gap: 16px; } .header-right { width: 100%; flex-direction: column; align-items: center; order: 3; gap: 16px; } .site-title-group { text-align: center; } .contact-info { text-align: center; border-left: none; border-top: 1px solid #e0e0e0; padding-left: 0; padding-top: 16px; } .search-box { max-width: 100%; } .brochure-card { flex-direction: column; } .card-map { width: 100%; min-width: 100%; height: 140px; border-left: none; border-top: 1px solid #ebebeb; } }
"""

NAV_TEMPLATE = """<nav class="top-nav">
    <div class="nav-container">
        <a href="{logo_href}"><img src="{logo_src}" alt="Europe Incoming" class="logo"></a>
        <input type="text" class="search-box" placeholder="Search packages - type city or country" id="searchBox">
        <div class="header-right">
            <div class="site-title-group">
                <div class="site-title-main">Europe Incoming</div>
                <div class="site-title-sub">FIT Packages</div>
            </div>
            <div class="contact-info">
                <div class="contact-prompt">Can't find what you're looking for? Email us at:</div>
                <a href="mailto:fitsales@europeincoming.com" class="contact-email">fitsales@europeincoming.com</a>
            </div>
        </div>
    </div>
</nav>"""

COMPOUND_NAMES = {
    'East Europe', 'Eastern Europe', 'Western Europe', 'Central Europe',
    'Western Central Europe', 'Costa Smeralda', 'Cala Gonone', 'Fort William',
    'San Sebastian', 'Czech Republic',
}

def make_title(filename):
    name = filename.replace('.pdf', '').replace('_', ' ')
    name = re.sub(r'\s+', ' ', name).strip()
    m = re.search(r'(\d+)\s*nights?,\s*(\d+)\s*days?\s+(.+)', name, re.IGNORECASE)
    if m:
        duration = f"{m.group(1)} nights, {m.group(2)} days"
        rest = m.group(3).strip()
    else:
        m2 = re.search(r'(\d+)\s*nights?\s*[/]?\s*(\d+)\s*days?', name, re.IGNORECASE)
        if m2:
            duration = f"{m2.group(1)} nights, {m2.group(2)} days"
            rest = name[m2.end():].strip()
        else:
            m3 = re.search(r'(\d+)\s*[Dd]ays?\s+(.+)', name, re.IGNORECASE)
            if m3:
                duration = f"{m3.group(1)} days"
                rest = m3.group(2).strip()
            else:
                return name
    rest = re.sub(r'\b(Private|Regular|Self.?[Dd]rive)\b', '', rest, flags=re.IGNORECASE)
    rest = re.sub(r'\d{4}-\d{2,4}', '', rest)
    rest = re.sub(r'Europe\s+Incoming', '', rest, flags=re.IGNORECASE)
    rest = re.sub(r'\s+', ' ', rest).strip().strip('-').strip()
    words = rest.split()
    if not words:
        destination = ""
    elif len(words) == 1:
        destination = words[0]
    elif len(words) == 2:
        destination = rest if rest in COMPOUND_NAMES else f"{words[0]} & {words[1]}"
    else:
        destination = ' & '.join(words)
    return f"{duration} {destination}".strip()

def detect_seasons(date_pairs):
    SUMMER = {4, 5, 6, 7, 8, 9, 10}
    WINTER = {11, 12, 1, 2, 3}
    has_summer = has_winter = False
    for s, e in date_pairs:
        try:
            sm = datetime.strptime(s, '%d.%m.%y').month
            em = datetime.strptime(e, '%d.%m.%y').month
            if sm in SUMMER or em in SUMMER: has_summer = True
            if sm in WINTER or em in WINTER: has_winter = True
        except: pass
    if has_summer and has_winter: return "all-year"
    elif has_summer: return "summer"
    elif has_winter: return "winter"
    return "all-year"

def extract_pdf_data(pdf_path, filename):
    result = {"duration": None, "tour_type": None, "cities": [], "price_twin": None, "season": "all-year", "includes": []}
    name = filename.replace('_', ' ')
    dur = re.search(r'(\d+)\s*nights?\s*/?,?\s*(\d+)\s*days?', name, re.IGNORECASE)
    if dur:
        result["duration"] = f"{dur.group(1)} nights / {dur.group(2)} days"
    else:
        days = re.search(r'(\d+)\s*days?', name, re.IGNORECASE)
        if days: result["duration"] = f"{days.group(1)} days"
    tour = re.search(r'(Self.?[Dd]rive|Private|Regular)', name)
    if tour: result["tour_type"] = tour.group(1).replace('-', ' ').title()
    try:
        doc = fitz.open(pdf_path)
        full_text = "\n".join(page.get_text() for page in doc)
        lines = [l.strip() for l in full_text.split('\n')]
        overnight = re.findall(r'Overnight in ([A-Z][a-zA-Z\s]+?)[\.\n,]', full_text)
        result["cities"] = list(dict.fromkeys([c.strip() for c in overnight]))[:6]
        date_pairs = re.findall(r'(\d{2}\.\d{2}\.\d{2})\s*\n?\s*(\d{2}\.\d{2}\.\d{2})', full_text)
        if date_pairs: result["season"] = detect_seasons(date_pairs)
        twin_idx = next((i for i, l in enumerate(lines) if 'Twin' in l and 'Do' in l), None)
        if twin_idx:
            euro_prices = []
            for l in lines[twin_idx:twin_idx+30]:
                m = re.match(r'€\s*([\d,]+)', l)
                if m: euro_prices.append(int(m.group(1).replace(',', '')))
            twins = euro_prices[1::3] if len(euro_prices) >= 3 else euro_prices[1:2] if len(euro_prices) >= 2 else []
            if twins: result["price_twin"] = min(twins)
        inc_m = re.search(r'price includes:(.*?)(?:Sample Tours|Terms|Sample Hotels)', full_text, re.DOTALL | re.IGNORECASE)
        if inc_m:
            inc_lines = [l.strip().lstrip('•').strip() for l in inc_m.group(1).split('\n') if l.strip() and not l.strip().startswith('**') and len(l.strip()) > 5]
            result["includes"] = inc_lines[:3]
    except Exception as e:
        print(f"  WARNING: {filename}: {e}")
    return result

def generate_description(cities, region, tour_type):
    if not cities:
        return f"Curated European package through {region}."
    if len(cities) == 1:
        return f"Discover the best of {cities[0]} in this curated package."
    elif len(cities) == 2:
        return f"Explore {cities[0]} and {cities[1]} on this {(tour_type or 'guided').lower()} tour."
    else:
        city_str = ', '.join(cities[:-1]) + ' & ' + cities[-1]
        return f"Journey through {city_str}."

def build_map_svg(cities):
    known = [(c, CITY_COORDS[c]) for c in cities if c in CITY_COORDS]
    if not known:
        return ""
    lats = [c[1][0] for c in known]
    lngs = [c[1][1] for c in known]
    lat_min, lat_max = min(lats), max(lats)
    lng_min, lng_max = min(lngs), max(lngs)
    lat_pad = max((lat_max - lat_min) * 0.28, 1.5)
    lng_pad = max((lng_max - lng_min) * 0.28, 1.5)
    lat_min -= lat_pad; lat_max += lat_pad
    lng_min -= lng_pad; lng_max += lng_pad
    W, H = 175, 200
    def to_xy(lat, lng):
        x = (lng - lng_min) / (lng_max - lng_min) * (W - 28) + 14
        y = (lat_max - lat) / (lat_max - lat_min) * (H - 28) + 14
        return round(x, 1), round(y, 1)
    points = [(name, to_xy(lat, lng)) for name, (lat, lng) in known]
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">',
             f'<rect width="{W}" height="{H}" fill="#dce8f5"/>']
    if len(points) > 1:
        for i in range(len(points) - 1):
            x1, y1 = points[i][1]
            x2, y2 = points[i+1][1]
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#2196F3" stroke-width="1.8" stroke-dasharray="4,2" opacity="0.75"/>')
            mx, my = round((x1+x2)/2, 1), round((y1+y2)/2, 1)
            parts.append(f'<circle cx="{mx}" cy="{my}" r="2.5" fill="#2196F3" opacity="0.6"/>')
    for i, (name, (x, y)) in enumerate(points):
        color = "#e53935" if i == 0 else ("#43a047" if i == len(points)-1 else "#1565c0")
        parts.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{color}" stroke="white" stroke-width="1.5"/>')
        anchor = "middle"
        lx, ly = x, y - 8
        if y < 22: ly = y + 15
        if x < 32: anchor, lx = "start", x + 7
        elif x > W - 32: anchor, lx = "end", x - 7
        short = name.split()[0] if len(name) > 9 else name
        parts.append(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="8" font-family="sans-serif" fill="#1a1a2e" font-weight="700" paint-order="stroke" stroke="white" stroke-width="2.5">{short}</text>')
    parts.append('</svg>')
    return '\n'.join(parts)

def make_card(pdf_filename, pdf_data, title, description):
    tour_type = pdf_data.get("tour_type", "")
    duration = pdf_data.get("duration", "")
    cities = pdf_data.get("cities", [])
    price = pdf_data.get("price_twin")
    season = pdf_data.get("season", "all-year")
    pills = ""
    if duration: pills += f'<span class="pill pill-duration">🕐 {duration}</span>'
    if season == "summer": pills += '<span class="pill pill-summer">☀️ Summer</span>'
    elif season == "winter": pills += '<span class="pill pill-winter">❄️ Winter</span>'
    else: pills += '<span class="pill pill-allyear">🌍 All Year Round</span>'
    tour_html = f'<div class="tour-type">{tour_type}</div>' if tour_type else ''
    desc_html = f'<div class="card-description">{description}</div>' if description else ''
    cities_html = f'<div class="cities-list">📍 {" · ".join(cities)}</div>' if cities else ''
    price_html = f'<div class="price-tag">From €{price:,} pp (twin)</div>' if price else ''
    map_svg = build_map_svg(cities)
    map_html = f'<div class="card-map">{map_svg}</div>' if map_svg else ''
    return f'''<a href="{pdf_filename}" class="brochure-card" target="_blank">
    <div class="card-info">
        <div class="card-title">{title} <span class="pdf-badge">PDF</span></div>
        {tour_html}
        <div class="card-pills">{pills}</div>
        {desc_html}
        {cities_html}
        {price_html}
    </div>
    {map_html}
</a>'''

def build_index_html(title, breadcrumb_html, cards_html, logo_src, logo_href, search_js_src):
    nav = NAV_TEMPLATE.format(logo_href=logo_href, logo_src=logo_src)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Europe Incoming</title>
    <style>{CSS}</style>
{GA_SCRIPT}
</head>
<body>
{GEO_BLOCK_SCRIPT}
{nav}
<div class="breadcrumb">{breadcrumb_html}</div>
<div class="container">
    <h1>{title}</h1>
    <div class="brochures" id="brochuresList">
{cards_html}
    </div>
    <footer><p>All packages are available for download in PDF format</p></footer>
</div>
<script src="{search_js_src}"></script>
</body>
</html>"""

def update_packages_json(packages_path, all_found):
    existing = {}
    if os.path.exists(packages_path):
        with open(packages_path, 'r') as f:
            data = json.load(f)
        for pkg in data.get("packages", []):
            key = pkg.get("folder", "") + "/" + pkg.get("filename", "")
            existing[key] = pkg
    new_packages = []
    for item in all_found:
        key = item["folder"] + "/" + item["filename"]
        if key in existing:
            new_packages.append(existing[key])
        else:
            pkg_id = re.sub(r'[^a-z0-9]', '-', item["filename"].lower().replace('.pdf', ''))[:30]
            pd = item["pdf_data"]
            new_packages.append({"id": pkg_id, "name": item["title"], "filename": item["filename"],
                "region": item["region"], "folder": item["folder"], "cities": pd.get("cities", []),
                "duration": pd.get("duration", ""), "type": pd.get("tour_type", ""),
                "season": pd.get("season", "all-year"), "price_twin": pd.get("price_twin"),
                "tags": pd.get("cities", [])})
    with open(packages_path, 'w') as f:
        json.dump({"packages": new_packages}, f, indent=2)
    print(f"  packages.json: {len(new_packages)} entries")

def main():
    packages_path = os.path.join(REPO_ROOT, "packages.json")
    all_found = []
    for folder_rel, config in FOLDER_CONFIG.items():
        folder_abs = os.path.join(REPO_ROOT, folder_rel)
        if not os.path.isdir(folder_abs):
            print(f"Skipping (not found): {folder_rel}")
            continue
        pdfs = sorted([f for f in os.listdir(folder_abs) if f.lower().endswith('.pdf')])
        if not pdfs:
            continue
        print(f"\n{folder_rel} — {len(pdfs)} PDFs")
        depth = config["parent_depth"]
        logo_src = "../" * depth + "logo.png"
        logo_href = "../" * depth
        search_js = "../" * depth + "global-search.js"
        if depth == 1:
            breadcrumb = f'<a href="../">Home</a> › {config["breadcrumb"]}'
        else:
            breadcrumb = f'<a href="../../">Home</a> › <a href="../">Multi-Country</a> › {config["breadcrumb"]}'
        cards = []
        for pdf in pdfs:
            print(f"  {pdf}")
            pdf_data = extract_pdf_data(os.path.join(folder_abs, pdf), pdf)
            title = make_title(pdf)
            description = generate_description(pdf_data.get("cities", []), config["region"], pdf_data.get("tour_type", ""))
            all_found.append({"filename": pdf, "title": title, "folder": folder_rel, "region": config["region"], "pdf_data": pdf_data})
            cards.append(make_card(pdf, pdf_data, title, description))
        html = build_index_html(config["title"], breadcrumb, "\n".join(cards), logo_src, logo_href, search_js)
        index_path = os.path.join(folder_abs, "index.html")
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  Rebuilt {folder_rel}/index.html")
    print(f"\nUpdating packages.json...")
    update_packages_json(packages_path, all_found)
    print("\nDone!")

if __name__ == "__main__":
    main()
