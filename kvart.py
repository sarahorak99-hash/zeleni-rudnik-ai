"""Zeleni rudnik – stranica "Moj kvart" (SIMULACIJA bodova po gradskim četvrtima).

Bodovi su demo vrijednosti: nemamo stvarne podatke o odlaganju po kvartovima.
Prikaz služi kao prototip mehanike: građani skupljaju bodove za svoju četvrt,
a bodovi otključavaju zajedničke projekte (cvijeće, grm, stablo, klupica...).
"""
import base64
import json
import random
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

GEOJSON_PATH = Path(__file__).parent / "gradske_cetvrti.geojson"

# Bodovi po odloženom komadu/vrećici. Ilustrativne vrijednosti prototipa.
POINTS = {
    "plastika": ("Plastika i metalna ambalaža", "Plastic and metal packaging", 5),
    "papir": ("Papir i karton", "Paper and cardboard", 5),
    "staklo": ("Staklo", "Glass", 5),
    "biootpad": ("Biootpad", "Bio waste", 3),
    "tekstil": ("Tekstil i odjeća", "Textiles and clothes", 10),
    "elektronika": ("Elektronički otpad", "Electronic waste", 20),
    "opasni": ("Opasni otpad (lijekovi, baterije, boje)", "Hazardous waste (medicines, batteries, paint)", 30),
    "glomazni": ("Glomazni otpad", "Bulky waste", 30),
}
YARD_MULTIPLIER = 2  # odlaganje u reciklažno dvorište vrijedi dvostruko

# (ključ, ikona, HR, EN, potrebno bodova) – ilustrativni pragovi, ne stvarne cijene.
PROJECTS = [
    ("cvijece", "🌼", "Gredica cvijeća", "Flower bed", 1500),
    ("grm", "🌿", "Živica / grmlje", "Shrubs / hedge", 3000),
    ("stablo", "🌳", "Sadnica stabla", "Tree sapling", 6000),
    ("klupa", "🪑", "Nova klupica", "New bench", 10000),
    ("park", "🌳🪑", "Mini park (stablo + klupe + cvijeće)", "Pocket park (trees + benches + flowers)", 20000),
]

TEXT = {
    "hr": {
        "title": "Moj kvart",
        "sim": "SIMULACIJA: bodovi ispod su izmišljene demo vrijednosti. Nemamo stvarne podatke o odlaganju po kvartovima. Prikazujemo samo kako bi mehanika funkcionirala.",
        "intro": "Svaki put kad pravilno odložiš otpad, bodovi idu tvom kvartu. Kad kvart skupi dovoljno bodova, zajednički sadimo stabla, cvijeće i grmlje ili postavljamo klupice.",
        "pick": "Odaberi svoju gradsku četvrt",
        "pts": "bodova",
        "rank": "Mjesto na ljestvici",
        "of": "od",
        "add_h": "Odloži otpad (simulacija)",
        "what": "Što si odložila/o?",
        "qty": "Količina",
        "where": "Gdje si ga odložila/o?",
        "where_opts": {"spremnik": "U spremnik / zeleni otok", "dvoriste": f"U reciklažno dvorište (×{YARD_MULTIPLIER} bodova)"},
        "add_btn": "Dodaj bodove svom kvartu",
        "added": "Dodano {n} bodova kvartu {k}.",
        "proj_h": "Što naš kvart može posaditi i postaviti",
        "done": "Ostvareno",
        "next": "Još {n} bodova",
        "next_h": "Sljedeći cilj",
        "all_done": "Kvart je ostvario sve ciljeve.",
        "board_h": "Ljestvica gradskih četvrti",
        "map_h": "Karta bodova",
        "col_k": "Gradska četvrt",
        "col_p": "Bodovi",
        "col_n": "Ostvareni ciljevi",
        "fair": "Napomena: u stvarnoj verziji bodove treba računati po broju stanovnika kako velike četvrti ne bi automatski pobjeđivale, a odlaganje potvrđivati (npr. QR kod na dvorištu). Pragovi za projekte su ilustrativni.",
        "scene_cap": "Tako trenutno izgleda tvoj kvart u simulaciji. Svaki cilj dodaje nešto novo.",
        "nofile": "Nije pronađena datoteka s granicama četvrti (gradske_cetvrti.geojson).",
    },
    "en": {
        "title": "My neighbourhood",
        "sim": "SIMULATION: the points below are made-up demo values. We have no real disposal data per district. This only shows how the mechanic would work.",
        "intro": "Every time you sort waste correctly, the points go to your neighbourhood. When it collects enough points, we plant trees, flowers and shrubs together or install benches.",
        "pick": "Choose your city district",
        "pts": "points",
        "rank": "Leaderboard rank",
        "of": "of",
        "add_h": "Dispose of waste (simulation)",
        "what": "What did you dispose of?",
        "qty": "Quantity",
        "where": "Where did you dispose of it?",
        "where_opts": {"spremnik": "In a container / green island", "dvoriste": f"At a recycling yard (×{YARD_MULTIPLIER} points)"},
        "add_btn": "Add points to my neighbourhood",
        "added": "Added {n} points to {k}.",
        "proj_h": "What our neighbourhood can plant and install",
        "done": "Achieved",
        "next": "{n} points to go",
        "next_h": "Next goal",
        "all_done": "The neighbourhood has reached all goals.",
        "board_h": "District leaderboard",
        "map_h": "Points map",
        "col_k": "City district",
        "col_p": "Points",
        "col_n": "Goals achieved",
        "fair": "Note: in a real version points should be calculated per resident so large districts don't win automatically, and disposal should be verified (e.g. a QR code at the yard). Project thresholds are illustrative.",
        "scene_cap": "This is how your neighbourhood looks in the simulation. Every goal adds something new.",
        "nofile": "District boundary file (gradske_cetvrti.geojson) not found.",
    },
}


@st.cache_data
def load_geojson():
    if not GEOJSON_PATH.exists():
        return None
    return json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))


def demo_points(names):
    """Stalni (seedani) izmišljeni početni bodovi, da su isti kod svakog pokretanja."""
    rng = random.Random(2026)
    return {n: rng.randint(1200, 17000) for n in names}


def goals_done(points):
    return sum(1 for p in PROJECTS if points >= p[4])


def colour(value, lo, hi):
    """Svijetlo-zelena -> tamno-zelena."""
    x = 0 if hi == lo else (value - lo) / (hi - lo)
    c0, c1 = (232, 245, 233), (27, 94, 32)
    r, g, b = (round(a + (b_ - a) * x) for a, b_ in zip(c0, c1))
    return f"#{r:02x}{g:02x}{b:02x}"


def scene_svg(points):
    """Izmišljena ilustracija kvarta: elementi se pojavljuju kako se otključavaju ciljevi."""
    p = []
    p.append("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 220'>")
    p.append("<rect width='600' height='220' fill='#e3f2fd'/>")
    p.append("<circle cx='540' cy='42' r='22' fill='#ffd54f'/>")
    p.append("<rect y='150' width='600' height='70' fill='#8bc34a'/>")
    p.append("<rect y='150' width='600' height='6' fill='#7cb342'/>")
    # kuće (kvart)
    for x, c in ((14, "#ffcc80"), (62, "#ef9a9a"), (110, "#b0bec5")):
        p.append(f"<rect x='{x}' y='112' width='38' height='38' fill='{c}'/>")
        p.append(f"<polygon points='{x - 4},112 {x + 19},92 {x + 42},112' fill='#8d6e63'/>")
        p.append(f"<rect x='{x + 14}' y='128' width='10' height='22' fill='#6d4c41'/>")
    if points >= 1500:  # cvijeće
        for x, c in ((170, "#f48fb1"), (192, "#fff176"), (214, "#ce93d8"), (236, "#f48fb1")):
            p.append(f"<line x1='{x}' y1='186' x2='{x}' y2='166' stroke='#2e7d32' stroke-width='3'/>")
            p.append(f"<circle cx='{x}' cy='162' r='7' fill='{c}'/>")
            p.append(f"<circle cx='{x}' cy='162' r='2.5' fill='#f9a825'/>")
    if points >= 3000:  # grmlje
        for x in (280, 312):
            p.append(f"<ellipse cx='{x}' cy='178' rx='26' ry='17' fill='#43a047'/>")
            p.append(f"<ellipse cx='{x - 8}' cy='172' rx='14' ry='10' fill='#66bb6a'/>")
    if points >= 6000:  # stablo
        p.append("<rect x='362' y='116' width='14' height='64' fill='#6d4c41'/>")
        p.append("<circle cx='369' cy='100' r='34' fill='#2e7d32'/>")
        p.append("<circle cx='346' cy='120' r='22' fill='#388e3c'/>")
        p.append("<circle cx='392' cy='120' r='22' fill='#388e3c'/>")
    if points >= 10000:  # klupica
        p.append("<rect x='420' y='160' width='70' height='7' fill='#8d6e63'/>")
        p.append("<rect x='420' y='146' width='70' height='6' fill='#8d6e63'/>")
        p.append("<rect x='426' y='167' width='6' height='20' fill='#5d4037'/>")
        p.append("<rect x='478' y='167' width='6' height='20' fill='#5d4037'/>")
        p.append("<rect x='426' y='152' width='6' height='15' fill='#5d4037'/>")
        p.append("<rect x='478' y='152' width='6' height='15' fill='#5d4037'/>")
    if points >= 20000:  # mini park
        p.append("<ellipse cx='300' cy='205' rx='170' ry='9' fill='#d7ccc8'/>")
        p.append("<rect x='528' y='122' width='12' height='58' fill='#6d4c41'/>")
        p.append("<circle cx='534' cy='108' r='28' fill='#2e7d32'/>")
        p.append("<circle cx='516' cy='124' r='18' fill='#388e3c'/>")
        p.append("<circle cx='552' cy='124' r='18' fill='#388e3c'/>")
    p.append("</svg>")
    return "".join(p)


def show_scene(points, caption):
    b64 = base64.b64encode(scene_svg(points).encode("utf-8")).decode("ascii")
    st.markdown(
        f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;border-radius:16px;'
        f'border:1px solid #c8e6c9" alt="Kvart">',
        unsafe_allow_html=True,
    )
    st.caption(caption)


def page_kvart(lang):
    t = TEXT[lang]
    i = 0 if lang == "hr" else 1
    gj = load_geojson()
    st.header(t["title"])
    st.warning(t["sim"], icon="🧪")
    if gj is None:
        st.error(t["nofile"])
        return
    st.write(t["intro"])

    names = sorted(f["properties"]["JMS_IME"] for f in gj["features"])
    if "kvart_points" not in st.session_state:
        st.session_state.kvart_points = demo_points(names)
    pts = st.session_state.kvart_points

    mine = st.selectbox(t["pick"], names, index=names.index("Trešnjevka - jug") if "Trešnjevka - jug" in names else 0)

    board = sorted(pts.items(), key=lambda kv: -kv[1])
    rank = [k for k, _ in board].index(mine) + 1
    c1, c2 = st.columns(2)
    c1.metric(mine, f"{pts[mine]:,} {t['pts']}".replace(",", "."))
    c2.metric(t["rank"], f"{rank}. {t['of']} {len(names)}")

    show_scene(pts[mine], t["scene_cap"])

    if "kvart_msg" in st.session_state:
        st.success(st.session_state.pop("kvart_msg"))

    # --- odlaganje ---
    st.subheader(t["add_h"])
    keys = list(POINTS.keys())
    col_a, col_b, col_c = st.columns([3, 1, 3])
    what = col_a.selectbox(t["what"], keys, format_func=lambda k: f"{POINTS[k][i]} (+{POINTS[k][2]})")
    qty = col_b.number_input(t["qty"], min_value=1, max_value=50, value=1)
    where = col_c.radio(t["where"], list(t["where_opts"].keys()), format_func=lambda k: t["where_opts"][k])
    if st.button(t["add_btn"], type="primary"):
        gain = POINTS[what][2] * int(qty) * (YARD_MULTIPLIER if where == "dvoriste" else 1)
        pts[mine] += gain
        st.session_state.kvart_msg = t["added"].format(n=gain, k=mine)
        st.rerun()

    # --- ciljevi kvarta ---
    st.subheader(t["proj_h"])
    cur = pts[mine]
    for key, icon, hr, en, need in PROJECTS:
        label = hr if lang == "hr" else en
        done = cur >= need
        st.progress(min(cur / need, 1.0), text=f"{icon} {label}: " + (f"✅ {t['done']}" if done else f"{cur:,} / {need:,} ({t['next'].format(n=f'{need - cur:,}')})").replace(",", "."))

    # --- ljestvica + karta ---
    st.subheader(t["board_h"])
    df = pd.DataFrame(
        {t["col_k"]: [k for k, _ in board], t["col_p"]: [v for _, v in board], t["col_n"]: [f"{goals_done(v)}/{len(PROJECTS)}" for _, v in board]}
    )
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.subheader(t["map_h"])
    lo, hi = min(pts.values()), max(pts.values())
    for f in gj["features"]:
        f["properties"]["bodovi"] = pts[f["properties"]["JMS_IME"]]
    fmap = folium.Map(location=(45.8131, 15.9775), zoom_start=10, tiles="OpenStreetMap")
    folium.GeoJson(
        gj,
        style_function=lambda f: {
            "color": "#1b5e20" if f["properties"]["JMS_IME"] == mine else "#555",
            "weight": 4 if f["properties"]["JMS_IME"] == mine else 1,
            "fillColor": colour(f["properties"]["bodovi"], lo, hi),
            "fillOpacity": 0.65,
        },
        tooltip=folium.GeoJsonTooltip(fields=["JMS_IME", "bodovi"], aliases=[t["col_k"] + ":", t["col_p"] + ":"]),
    ).add_to(fmap)
    st_folium(fmap, height=450, use_container_width=True, returned_objects=[])

    st.caption(t["fair"])
