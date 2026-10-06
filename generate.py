#!/usr/bin/env python3
"""
Stacja pogody i kalendarza dla Kindle 10. generacji (600x800).
Pobiera pogodę z Open-Meteo i wydarzenia z kalendarzy iCal,
a potem rysuje obrazek PNG w skali szarości.

Użycie:
    python generate.py --out public/stacja.png
    python generate.py --out test.png --demo     # dane przykładowe, bez internetu

Zmienne środowiskowe:
    ICAL_URLS  - jeden lub więcej linków iCal (każdy w osobnej linii)
"""

import argparse
import calendar as pycal
import math
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

# ------------------------- KONFIGURACJA -------------------------
MIASTO = "Radomsko"
LAT, LON = 51.0670, 19.4450
STREFA = ZoneInfo("Europe/Warsaw")
DNI_KALENDARZA = 21          # ile dni do przodu pokazywać wydarzenia
W, H = 600, 800              # rozdzielczość ekranu Kindle 10. gen (J9G29R)
M = 48                       # margines
# ----------------------------------------------------------------

DNI = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
DNI_KR = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]
DNI_MINI = ["Pn", "Wt", "Śr", "Cz", "Pt", "Sb", "Nd"]
MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
            "sierpnia", "września", "października", "listopada", "grudnia"]
MIESIACE_M = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec",
              "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]

CZARNY, CIEMNY, SZARY, JASNY, BIALY = 0, 70, 120, 200, 255


# ------------------------- CZCIONKI -------------------------
def _font_path(bold):
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "fonts", "Bold.ttf" if bold else "Regular.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("Brak czcionki – zainstaluj fonts-dejavu-core")


_cache = {}


def F(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(_font_path(bold), size)
    return _cache[key]


def text_w(d, txt, font):
    return d.textlength(txt, font=font)


def clean(txt):
    """Usuwa emoji i inne znaki, których czcionka nie ma."""
    return "".join(ch for ch in txt if ord(ch) <= 0xFFFF and not 0xFE00 <= ord(ch) <= 0xFE0F).strip()


def fit(d, txt, font, max_w):
    """Skraca tekst z wielokropkiem, żeby zmieścił się w max_w."""
    txt = clean(txt)
    if text_w(d, txt, font) <= max_w:
        return txt
    while txt and text_w(d, txt + "…", font) > max_w:
        txt = txt[:-1]
    return txt.rstrip() + "…"


# ------------------------- POGODA -------------------------
def wmo_info(code):
    """Zwraca (opis, typ ikony) dla kodu pogody WMO."""
    if code == 0:
        return "Bezchmurnie", "sun"
    if code == 1:
        return "Pogodnie", "sun"
    if code == 2:
        return "Słońce i chmury", "partly"
    if code == 3:
        return "Pochmurno", "cloud"
    if code in (45, 48):
        return "Mgła", "fog"
    if code in (51, 53, 55, 56, 57):
        return "Mżawka", "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Deszcz" if code not in (65, 82) else "Ulewa", "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "Śnieg", "snow"
    if code in (95, 96, 99):
        return "Burza", "storm"
    return "—", "cloud"


def fetch_weather():
    import requests
    params = {
        "latitude": LAT, "longitude": LON, "timezone": "Europe/Warsaw",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "weather_code,wind_speed_10m,is_day",
        "hourly": "temperature_2m,precipitation_probability,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,sunrise,sunset",
        "forecast_days": 6,
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def demo_weather(now):
    base = now.replace(minute=0, second=0, microsecond=0)
    hours = [base + timedelta(hours=i) for i in range(-2, 48)]
    codes = [2, 2, 3, 3, 61, 61, 80, 3, 2, 1, 0, 0] * 5
    return {
        "current": {"temperature_2m": 12.4, "apparent_temperature": 10.1,
                    "relative_humidity_2m": 78, "weather_code": 2,
                    "wind_speed_10m": 14.0, "is_day": 1},
        "hourly": {
            "time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
            "temperature_2m": [12 + 4 * math.sin(i / 4) for i in range(len(hours))],
            "precipitation_probability": [(i * 13) % 90 for i in range(len(hours))],
            "weather_code": codes[:len(hours)],
            "is_day": [1 if 6 <= h.hour < 19 else 0 for h in hours],
        },
        "daily": {
            "time": [(now.date() + timedelta(days=i)).isoformat() for i in range(6)],
            "weather_code": [2, 61, 3, 0, 71, 95],
            "temperature_2m_max": [15, 13, 11, 16, 4, 18],
            "temperature_2m_min": [7, 8, 5, 3, -2, 9],
            "precipitation_probability_max": [10, 80, 30, 0, 60, 70],
            "sunrise": [f"{now.date()}T07:02"] * 6,
            "sunset": [f"{now.date()}T18:21"] * 6,
        },
    }


# ------------------------- IKONY -------------------------
def draw_sun(d, cx, cy, r, w):
    d.ellipse([cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45], outline=CZARNY, width=w)
    for i in range(8):
        a = i * math.pi / 4
        x1, y1 = cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.62
        x2, y2 = cx + math.cos(a) * r * 0.9, cy + math.sin(a) * r * 0.9
        d.line([x1, y1, x2, y2], fill=CZARNY, width=w)


def draw_moon(d, cx, cy, r, w):
    rr = r * 0.55
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=CZARNY)
    off = rr * 0.55
    d.ellipse([cx - rr + off, cy - rr - off * 0.4, cx + rr + off, cy + rr - off * 0.4], fill=BIALY)


def draw_cloud(d, cx, cy, r, w, fill=BIALY):
    """Chmura z trzech kółek i podstawy."""
    parts = [
        (cx - r * 0.42, cy + r * 0.05, r * 0.36),
        (cx + r * 0.05, cy - r * 0.18, r * 0.48),
        (cx + r * 0.5, cy + r * 0.1, r * 0.32),
    ]
    base = [cx - r * 0.78, cy + r * 0.05, cx + r * 0.82, cy + r * 0.42]
    # obrys: najpierw grubsze czarne kształty, potem wypełnienie
    for (x, y, rr) in parts:
        d.ellipse([x - rr - w, y - rr - w, x + rr + w, y + rr + w], fill=CZARNY)
    d.rounded_rectangle([base[0] - w, base[1] - w, base[2] + w, base[3] + w], radius=r * 0.2, fill=CZARNY)
    for (x, y, rr) in parts:
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fill)
    d.rounded_rectangle(base, radius=r * 0.18, fill=fill)


def draw_icon(d, kind, cx, cy, size, night=False):
    r = size / 2
    w = max(2, int(size / 28))
    if kind == "sun":
        (draw_moon if night else draw_sun)(d, cx, cy, r, w)
    elif kind == "partly":
        sx, sy = cx - r * 0.3, cy - r * 0.3
        (draw_moon if night else draw_sun)(d, sx, sy, r * 0.75, w)
        draw_cloud(d, cx + r * 0.12, cy + r * 0.15, r * 0.8, w)
    elif kind == "cloud":
        draw_cloud(d, cx - r * 0.25, cy - r * 0.2, r * 0.6, w, fill=JASNY)
        draw_cloud(d, cx + r * 0.05, cy + r * 0.1, r * 0.85, w)
    elif kind == "fog":
        draw_cloud(d, cx, cy - r * 0.25, r * 0.75, w)
        for i, k in enumerate((0.35, 0.55, 0.75)):
            x0 = cx - r * (0.8 - i * 0.1)
            x1 = cx + r * (0.8 - i * 0.1)
            d.line([x0, cy + r * k, x1, cy + r * k], fill=CZARNY, width=w)
    elif kind in ("rain", "drizzle", "storm", "snow"):
        draw_cloud(d, cx, cy - r * 0.3, r * 0.85, w)
        y0 = cy + r * 0.3
        if kind == "snow":
            for i, x in enumerate((-0.45, 0, 0.45)):
                px, py = cx + r * x, y0 + r * (0.25 if i % 2 else 0.15)
                s = r * 0.13
                for a in range(3):
                    ang = a * math.pi / 3
                    d.line([px - math.cos(ang) * s, py - math.sin(ang) * s,
                            px + math.cos(ang) * s, py + math.sin(ang) * s], fill=CZARNY, width=w)
        elif kind == "storm":
            pts = [(cx + r * 0.05, y0), (cx - r * 0.2, y0 + r * 0.35), (cx, y0 + r * 0.35),
                   (cx - r * 0.15, y0 + r * 0.7), (cx + r * 0.25, y0 + r * 0.25),
                   (cx + r * 0.05, y0 + r * 0.25), (cx + r * 0.2, y0)]
            d.polygon(pts, fill=CZARNY)
        else:
            n = 3 if kind == "rain" else 2
            xs = (-0.45, 0, 0.45) if n == 3 else (-0.25, 0.25)
            ln = 0.4 if kind == "rain" else 0.2
            for x in xs:
                d.line([cx + r * x, y0, cx + r * (x - 0.12), y0 + r * ln], fill=CZARNY, width=w + 1)


# ------------------------- KALENDARZ -------------------------
def fetch_events(now):
    import requests
    import icalendar
    import recurring_ical_events

    urls = [u.strip() for u in os.environ.get("ICAL_URLS", "").splitlines() if u.strip()]
    start = datetime.combine(now.date(), datetime.min.time(), tzinfo=STREFA)
    end = start + timedelta(days=DNI_KALENDARZA)
    events = []
    errors = 0
    for url in urls:
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            cal = icalendar.Calendar.from_ical(r.content)
            for ev in recurring_ical_events.of(cal).between(start, end):
                s = ev.get("DTSTART").dt
                e = ev.get("DTEND").dt if ev.get("DTEND") else None
                title = str(ev.get("SUMMARY", "(bez tytułu)"))
                if isinstance(s, datetime):
                    s = s.astimezone(STREFA) if s.tzinfo else s.replace(tzinfo=STREFA)
                    events.append({"day": s.date(), "time": s.strftime("%H:%M"),
                                   "sort": s, "title": title, "allday": False})
                else:
                    # wydarzenie całodniowe, może trwać kilka dni
                    last = (e - timedelta(days=1)) if isinstance(e, date) and not isinstance(e, datetime) else s
                    day = max(s, start.date())
                    while day <= last and day < end.date():
                        events.append({"day": day, "time": "", "title": title, "allday": True,
                                       "sort": datetime.combine(day, datetime.min.time(), tzinfo=STREFA)})
                        day += timedelta(days=1)
        except Exception as ex:  # jeden zły kalendarz nie psuje reszty
            print(f"Błąd kalendarza: {ex}")
            errors += 1
    # usuń duplikaty (to samo wydarzenie w kilku kalendarzach)
    seen, unique = set(), []
    for ev in sorted(events, key=lambda x: (x["day"], not x["allday"], x["sort"])):
        k = (ev["day"], ev["time"], ev["title"])
        if k not in seen:
            seen.add(k)
            unique.append(ev)
    return unique, errors, bool(urls)


def demo_events(now):
    t = now.date()
    return [
        {"day": t, "time": "", "title": "Imieniny Franciszka", "allday": True},
        {"day": t, "time": "17:30", "title": "Basen z dziećmi", "allday": False},
        {"day": t + timedelta(days=1), "time": "08:00", "title": "Wywóz śmieci – plastik", "allday": False},
        {"day": t + timedelta(days=1), "time": "16:00", "title": "Dentysta – dr Kowalska, ul. Reymonta", "allday": False},
        {"day": t + timedelta(days=3), "time": "", "title": "Urodziny Mamy 🎂", "allday": True},
        {"day": t + timedelta(days=3), "time": "19:00", "title": "Kolacja u rodziców", "allday": False},
        {"day": t + timedelta(days=6), "time": "10:00", "title": "Przegląd samochodu", "allday": False},
        {"day": t + timedelta(days=6), "time": "18:00", "title": "Zebranie w szkole", "allday": False},
        {"day": t + timedelta(days=9), "time": "", "title": "Wycieczka w góry", "allday": True},
        {"day": t + timedelta(days=11), "time": "12:00", "title": "Obiad u teściów", "allday": False},
        {"day": t + timedelta(days=14), "time": "08:00", "title": "Wywóz śmieci – szkło", "allday": False},
    ], 0, True


# ------------------------- WYWÓZ ŚMIECI -------------------------
import re
SLOWA_SMIECI = ("wywóz", "wywoz", "śmieci", "smieci", "odpady", "odpadów", "odbiór odpadów")


def is_waste(ev):
    t = ev["title"].lower()
    return any(w in t for w in SLOWA_SMIECI)


def waste_name(title):
    """'Wywóz śmieci – plastik' -> 'plastik'"""
    t = re.sub(r"^\s*((wywóz|wywoz|odbiór|odbior|śmieci|smieci|odpady|odpadów|odpadow)[\s:–—-]*)+",
               "", title, flags=re.IGNORECASE).strip()
    return t or title


def next_waste(events, today):
    w = [e for e in events if is_waste(e) and e["day"] >= today]
    if not w:
        return None, []
    day = min(e["day"] for e in w)
    names = []
    for e in w:
        if e["day"] == day:
            n = waste_name(e["title"])
            if n.lower() not in [x.lower() for x in names]:
                names.append(n)
    return day, names


# ------------------------- RYSOWANIE -------------------------
def day_label(day, today):
    if day == today:
        return "Dziś"
    if day == today + timedelta(days=1):
        return "Jutro"
    return f"{DNI[day.weekday()]}, {day.day} {MIESIACE[day.month - 1]}"


def render(weather, events, cal_errors, cal_configured, now, out):
    """Rysuje na wirtualnym płótnie VW x VH, potem skaluje do rozdzielczości ekranu."""
    VW, VH, m = 900, 1200, 36
    img = Image.new("L", (VW, VH), BIALY)
    d = ImageDraw.Draw(img)
    today = now.date()

    # ---- NAGŁÓWEK ----
    d.text((m, 26), DNI[today.weekday()], font=F(36), fill=CIEMNY)
    d.text((m, 66), f"{today.day} {MIESIACE[today.month - 1]}", font=F(66, True), fill=CZARNY)
    d.text((VW - m, 34), MIASTO, font=F(30, True), fill=CZARNY, anchor="ra")
    d.text((VW - m, 74), f"tydzień {today.isocalendar()[1]}", font=F(24), fill=CIEMNY, anchor="ra")
    d.text((VW - m, 106), f"akt. {now:%H:%M}", font=F(22), fill=SZARY, anchor="ra")
    d.line([m, 158, VW - m, 158], fill=CZARNY, width=3)

    # ---- POGODA (kompaktowo) ----
    y = 172
    if weather:
        c, dl = weather["current"], weather["daily"]
        opis, kind = wmo_info(c["weather_code"])
        draw_icon(d, kind, m + 58, y + 62, 115, night=not c.get("is_day", 1))
        temp = f"{round(c['temperature_2m'])}°"
        d.text((m + 128, y - 2), temp, font=F(92, True), fill=CZARNY)
        tx = m + 136 + text_w(d, temp, F(92, True)) + 16
        days_x = VW - m - 3 * 96            # miejsce na 3 kolejne dni po prawej
        tw = days_x - tx - 10
        f_op = next((F(sz, True) for sz in (25, 22, 20) if text_w(d, opis, F(sz, True)) <= tw), F(20, True))
        d.text((tx, y + 10), fit(d, opis, f_op, tw), font=f_op, fill=CZARNY)
        d.text((tx, y + 46), fit(d, f"{round(dl['temperature_2m_max'][0])}° / "
                                    f"{round(dl['temperature_2m_min'][0])}°", F(24), tw), font=F(24), fill=CIEMNY)
        pr = dl["precipitation_probability_max"][0]
        if pr is not None and pr >= 20:
            d.text((tx, y + 80), fit(d, f"☂ {pr}%", F(22), tw), font=F(22), fill=SZARY)
        for k in range(1, 4):
            if k >= len(dl["time"]):
                break
            dd = date.fromisoformat(dl["time"][k])
            cx = days_x + 96 * (k - 1) + 48
            d.text((cx, y), DNI_KR[dd.weekday()], font=F(22, True), fill=CZARNY, anchor="ma")
            _, kk = wmo_info(dl["weather_code"][k])
            draw_icon(d, kk, cx, y + 54, 44)
            d.text((cx, y + 84), f"{round(dl['temperature_2m_max'][k])}°/"
                                 f"{round(dl['temperature_2m_min'][k])}°", font=F(21), fill=CIEMNY, anchor="ma")
    else:
        d.text((VW / 2, y + 55), "Brak danych pogodowych", font=F(28), fill=SZARY, anchor="mm")

    d.line([m, 300, VW - m, 300], fill=CZARNY, width=3)

    # ---- PASEK: NAJBLIŻSZY WYWÓZ ŚMIECI ----
    y0 = 318
    w_day, w_names = next_waste(events, today)
    if w_day:
        pilne = w_day <= today + timedelta(days=1)
        if w_day == today:
            kiedy = "Dziś"
        elif w_day == today + timedelta(days=1):
            kiedy = "Jutro"
        else:
            kiedy = f"{DNI_KR[w_day.weekday()]} {w_day.day}.{w_day.month:02d}"
        txt = f"♻ Wywóz {kiedy.lower() if kiedy in ('Dziś', 'Jutro') else kiedy}: {', '.join(w_names)}"
        maxw = VW - 2 * m - 32
        sz = next((z for z in (26, 23, 21) if text_w(d, txt, F(z, True)) <= maxw), 21)
        fw = F(sz, True)
        if pilne:
            d.rounded_rectangle([m, y0, VW - m, y0 + 50], radius=12, fill=CZARNY)
            d.text((m + 16, y0 + 25), fit(d, txt, fw, maxw), font=fw, fill=BIALY, anchor="lm")
        else:
            d.rounded_rectangle([m, y0, VW - m, y0 + 50], radius=12, outline=SZARY, width=2)
            d.text((m + 16, y0 + 25), fit(d, txt, F(sz), maxw), font=F(sz), fill=CIEMNY, anchor="lm")
        y0 += 68
    # śmieci nie dublujemy na liście wydarzeń
    events = [e for e in events if not is_waste(e)]

    # ---- MINI MIESIĄC (lewa kolumna, z numerami tygodni) ----
    cell = 46
    wk_w = 34                      # kolumna z numerami tygodni
    gx = m + wk_w
    d.text((m, y0), f"{MIESIACE_M[today.month - 1]}", font=F(28, True), fill=CZARNY)
    d.text((m + wk_w / 2, y0 + 48), "tydz", font=F(14), fill=JASNY, anchor="ma")
    for i, nm in enumerate(DNI_MINI):
        d.text((gx + cell * i + cell / 2, y0 + 46), nm, font=F(19, True),
               fill=SZARY if i < 5 else CZARNY, anchor="ma")
    busy = {e["day"] for e in events}
    this_week = today.isocalendar()[1]
    weeks = pycal.Calendar(firstweekday=0).monthdatescalendar(today.year, today.month)
    for r_i, week in enumerate(weeks):
        cy = y0 + 92 + r_i * 41
        wn = week[0].isocalendar()[1]
        cur = wn == this_week
        d.text((m + wk_w / 2, cy), str(wn), font=F(17, cur), fill=CZARNY if cur else SZARY, anchor="mm")
        for c_i, dd in enumerate(week):
            if dd.month != today.month:
                continue
            cx = gx + cell * c_i + cell / 2
            if dd == today:
                d.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=CZARNY)
                d.text((cx, cy), str(dd.day), font=F(22, True), fill=BIALY, anchor="mm")
            else:
                d.text((cx, cy), str(dd.day), font=F(22, dd.weekday() >= 5),
                       fill=CZARNY if dd >= today else JASNY, anchor="mm")
                if dd in busy:
                    d.ellipse([cx - 4, cy + 13, cx + 4, cy + 21], fill=CZARNY)
    grid_bottom = y0 + 92 + len(weeks) * 41

    # ---- WYDARZENIA: obok miesiąca, a pod nim na całą szerokość ----
    col_x = gx + cell * 7 + 24
    ly = y0
    max_y = VH - 72          # dół zostaje wolny na stan baterii
    fe, fb = F(25), F(25, True)

    def area(yy):
        return (col_x, VW - m - col_x) if yy < grid_bottom else (m, VW - 2 * m)

    d.text((col_x, ly), "Najbliższe", font=F(28, True), fill=CZARNY)
    ly += 46
    if not cal_configured:
        d.text((col_x, ly), fit(d, "Dodaj sekret ICAL_URLS", fe, VW - m - col_x), font=fe, fill=SZARY)
    elif not events:
        d.text((col_x, ly), fit(d, "Brak wydarzeń", fe, VW - m - col_x), font=fe, fill=SZARY)
    current_day, hidden = None, 0
    for ev in events:
        need = (42 if ev["day"] != current_day else 0) + 38
        if ly + need > max_y:
            hidden += 1
            continue
        if ev["day"] != current_day:
            current_day = ev["day"]
            if ly > y0 + 50:
                ly += 8
            lx, lw = area(ly + 36 + 34)          # nagłówek + pierwsze wydarzenie razem
            if lx == m and ly < grid_bottom:     # przeskok pod kalendarz
                ly = grid_bottom + 8
            lx, lw = area(ly)
            d.text((lx, ly), fit(d, day_label(current_day, today), fb, lw), font=fb,
                   fill=CZARNY if current_day <= today + timedelta(days=1) else CIEMNY)
            if lx == m:
                d.line([lx + text_w(d, fit(d, day_label(current_day, today), fb, lw), fb) + 12, ly + 16,
                        VW - m, ly + 16], fill=JASNY, width=2)
            ly += 36
        lx, lw = area(ly + 30)
        if lx == m and ly < grid_bottom:
            ly = grid_bottom + 8
        if ev["allday"]:
            t = fit(d, ev["title"], fe, lw - 20)
            d.rounded_rectangle([lx, ly - 2, lx + text_w(d, t, fe) + 16, ly + 32], radius=7, fill=CZARNY)
            d.text((lx + 8, ly), t, font=fe, fill=BIALY)
        else:
            d.text((lx, ly), ev["time"], font=fb, fill=CIEMNY)
            d.text((lx + 84, ly), fit(d, ev["title"], fe, lw - 84), font=fe, fill=CZARNY)
        ly += 38
    if hidden:
        d.text((VW - m, max_y + 2), f"+ {hidden} więcej", font=F(20), fill=SZARY, anchor="ra")
    if cal_errors:
        d.text((m, max_y + 2), f"Błąd {cal_errors} kalendarza", font=F(20), fill=SZARY)

    # ---- SKALOWANIE DO EKRANU ----
    img = img.resize((W, H), Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out, optimize=True)
    print(f"Zapisano {out} ({W}x{H})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="public/stacja.png")
    ap.add_argument("--demo", action="store_true", help="dane przykładowe, bez internetu")
    a = ap.parse_args()
    now = datetime.now(STREFA)

    if a.demo:
        weather = demo_weather(now)
        events, errs, conf = demo_events(now)
    else:
        try:
            weather = fetch_weather()
        except Exception as ex:
            print(f"Błąd pogody: {ex}")
            weather = None
        events, errs, conf = fetch_events(now)
    render(weather, events, errs, conf, now, a.out)


if __name__ == "__main__":
    main()
