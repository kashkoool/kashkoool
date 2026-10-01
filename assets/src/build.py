#!/usr/bin/env python3
"""Generates the animated SVG assets used by README.md.

Run from the repo root:  python assets/src/build.py
Needs: pip install fonttools brotli pillow

GitHub renders these SVGs as <img>, so everything (fonts, screenshots, icons)
is inlined and all motion is CSS inside the SVG. Every animation is disabled
under prefers-reduced-motion and every element's resting state is its final state.
"""
import base64
import io
import math
import re
import urllib.request
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "src"
VENDOR = SRC / "vendor"
OUT = ROOT / "assets"

# Palette: navy-black ground, one gold accent.
BG = "#0B0F16"
SURFACE = "#111722"
LINE = "#232C3B"
TEXT = "#EDEFF3"
SOFT = "#C6CCD6"
MUTED = "#939DAE"
GOLD = "#F4C25B"
INK = "#1A1406"
LIGHT_TEXT = "#1F2328"
LIGHT_GOLD = "#B7791F"

EASE = "cubic-bezier(.16,1,.3,1)"

# Third-party sources, downloaded into vendor/ (gitignored) on first run.
CDN = "https://cdn.jsdelivr.net/npm"
VENDOR_URLS = {
    **{f"{n}.woff2": f"{CDN}/geist@1.7.2/dist/fonts/geist-sans/{n}.woff2"
       for n in ("Geist-Regular", "Geist-Medium", "Geist-SemiBold")},
    "GeistMono-Regular.woff2": f"{CDN}/geist@1.7.2/dist/fonts/geist-mono/GeistMono-Regular.woff2",
    **{f"si-{n}.svg": f"{CDN}/simple-icons@13/icons/{n}.svg" for n in ("linkedin", "instagram")},
    **{f"tb-{n}.svg": f"{CDN}/@tabler/icons@3/icons/outline/{n}.svg"
       for n in ("arrow-up-right", "world", "mail", "building-store", "calendar-event")},
}


def fetch_vendor():
    VENDOR.mkdir(parents=True, exist_ok=True)
    for name, url in VENDOR_URLS.items():
        if not (VENDOR / name).exists():
            urllib.request.urlretrieve(url, VENDOR / name)

# ---------------------------------------------------------------- fonts

FONT_FILES = {
    "regular": ("Geist", 400, "Geist-Regular"),
    "medium": ("Geist", 500, "Geist-Medium"),
    "semibold": ("Geist", 600, "Geist-SemiBold"),
    "mono": ("GeistMono", 400, "GeistMono-Regular"),
}
CHARSET = "".join(chr(c) for c in range(0x20, 0x7F)) + "·’"
_fonts = {}


def font(key):
    if key not in _fonts:
        path = VENDOR / f"{FONT_FILES[key][2]}.woff2"
        sub_font = TTFont(path, recalcTimestamp=False)
        opts = subset.Options()
        opts.flavor = "woff2"
        subsetter = subset.Subsetter(opts)
        subsetter.populate(text=CHARSET)
        subsetter.subset(sub_font)
        buf = io.BytesIO()
        sub_font.save(buf)
        full = TTFont(path)
        _fonts[key] = {
            "b64": base64.b64encode(buf.getvalue()).decode(),
            "cmap": full.getBestCmap(),
            "hmtx": full["hmtx"],
            "upm": full["head"].unitsPerEm,
        }
    return _fonts[key]


def measure(text, key, size):
    f = font(key)
    return sum(f["hmtx"][f["cmap"][ord(c)]][0] for c in text) * size / f["upm"]


def wrap(text, key, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, key, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def font_css(keys):
    out = []
    for k in keys:
        family, weight, _ = FONT_FILES[k]
        out.append(
            f"@font-face{{font-family:{family};font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{font(k)['b64']}) format('woff2')}}"
        )
    return "".join(out)


BASE_CSS = f"""
.sans{{font-family:Geist,'Segoe UI',-apple-system,'Helvetica Neue',Arial,sans-serif}}
.mono{{font-family:GeistMono,ui-monospace,'Cascadia Code',Consolas,monospace}}
.rise{{animation:rise .9s {EASE} backwards}}
@keyframes rise{{from{{opacity:0;transform:translateY(14px)}}}}
.fade{{animation:fade 1.2s ease-out backwards}}
@keyframes fade{{from{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""


def svg(w, h, body, fonts, css="", label=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">'
        f"<title>{escape(label)}</title>"
        f"<style><![CDATA[{font_css(fonts)}{BASE_CSS}{css}]]></style>"
        f"{body}</svg>"
    )


def text(x, y, s, size, key, fill, cls="", extra=""):
    family = "mono" if key == "mono" else "sans"
    weight = FONT_FILES[key][1]
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{family} {cls}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" {extra}>{escape(s)}</text>'
    )


def delay(seconds):
    return f'style="animation-delay:{seconds:.2f}s"'


# ---------------------------------------------------------------- icons


def icon(name, x, y, size, color):
    """Simple Icons (si-*) are filled brand marks; Tabler (tb-*) are outline UI icons."""
    raw = (VENDOR / f"{name}.svg").read_text(encoding="utf-8")
    paths = [d for d in re.findall(r'<path[^>]*?\sd="([^"]+)"', raw) if d != "M0 0h24v24H0z"]
    s = size / 24
    tf = f'transform="translate({x:.1f} {y:.1f}) scale({s:.4f})"'
    if name.startswith("si-"):
        return f'<g {tf} fill="{color}">' + "".join(f'<path d="{d}"/>' for d in paths) + "</g>"
    return (
        f'<g {tf} fill="none" stroke="{color}" stroke-width="1.75" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        + "".join(f'<path d="{d}"/>' for d in paths)
        + "</g>"
    )


# ---------------------------------------------------------------- shared pieces


def jpeg_uri(path, width):
    img = Image.open(path).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


SHEEN_DEFS = (
    '<linearGradient id="sheen" x1="0" x2="1">'
    '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
    '<stop offset=".5" stop-color="#fff" stop-opacity=".14"/>'
    '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
)


def sheen_css(travel, period=8, start=1.6):
    return (
        f".sheen{{animation:sheen {period}s {start}s ease-in-out infinite}}"
        f"@keyframes sheen{{0%{{transform:translateX(0)}}30%,100%{{transform:translateX({travel}px)}}}}"
    )


def screenshot(uri, x, y, w, h, clip_id="shot"):
    """A real screenshot, clipped to radius 12, with a light sweep crossing it."""
    return (
        f'<clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/></clipPath>'
        f'<g class="fade" {delay(.1)}>'
        f'<image href="{uri}" x="{x}" y="{y}" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMin slice" clip-path="url(#{clip_id})"/>'
        f'<g clip-path="url(#{clip_id})"><g transform="skewX(-18)">'
        f'<rect class="sheen" x="{x - 320}" y="{y - 40}" width="220" height="{h + 80}" fill="url(#sheen)"/>'
        f"</g></g>"
        f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="11.5" '
        f'fill="none" stroke="#fff" stroke-opacity=".08"/></g>'
    )


def chips(items, x, y, start_delay, gold_first=False):
    out, cx = [], x
    for i, label in enumerate(items):
        w = measure(label, "mono", 13) + 24
        gold = gold_first and i == 0
        out.append(
            f'<g class="rise" {delay(start_delay + i * .07)}>'
            f'<rect x="{cx:.1f}" y="{y}" width="{w:.1f}" height="28" rx="14" '
            f'fill="{GOLD if gold else "#fff"}" fill-opacity="{.12 if gold else .035}" '
            f'stroke="{GOLD if gold else "#fff"}" stroke-opacity="{.45 if gold else .1}"/>'
            + text(cx + 12, y + 18.5, label, 13, "mono", GOLD if gold else SOFT)
            + "</g>"
        )
        cx += w + 8
    return "".join(out)


def rounded_rect_path(x, y, w, h, r):
    return (
        f"M{x + r},{y} H{x + w - r} A{r},{r} 0 0 1 {x + w},{y + r} V{y + h - r} "
        f"A{r},{r} 0 0 1 {x + w - r},{y + h} H{x + r} A{r},{r} 0 0 1 {x},{y + h - r} "
        f"V{y + r} A{r},{r} 0 0 1 {x + r},{y} Z"
    )


def panel(w, h, r=20, beam=False):
    """Card ground. The featured card gets a gold beam travelling its border."""
    out = (
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{r}" fill="{BG}" stroke="{LINE}"/>'
    )
    css = ""
    if beam:
        per = 2 * (w - 1 + h - 1) - 8 * r + 2 * math.pi * r
        d = rounded_rect_path(.5, .5, w - 1, h - 1, r)
        tail, head = 320, 110
        out += (
            f'<path class="beamA" d="{d}" fill="none" stroke="{GOLD}" stroke-opacity=".28" '
            f'stroke-width="1.5" stroke-dasharray="{tail} {per - tail:.1f}"/>'
            f'<path class="beamB" d="{d}" fill="none" stroke="{GOLD}" stroke-width="1.5" '
            f'stroke-linecap="round" stroke-dasharray="{head} {per - head:.1f}" '
            f'stroke-dashoffset="{head - tail}"/>'
        )
        css = (
            f".beamA{{animation:beamA 10s linear infinite}}"
            f".beamB{{animation:beamB 10s linear infinite}}"
            f"@keyframes beamA{{from{{stroke-dashoffset:0}}to{{stroke-dashoffset:{-per:.1f}}}}}"
            f"@keyframes beamB{{from{{stroke-dashoffset:{head - tail}}}to{{stroke-dashoffset:{head - tail - per:.1f}}}}}"
        )
    return out, css


# ---------------------------------------------------------------- header


def build_header():
    w, h = 880, 250
    name = "Louay Kashkool"
    name_w = measure(name, "semibold", 58)
    roles = ["Full-Stack Software Engineer", "DevOps & Cloud Security", "Founding engineer at Jadwal"]
    stats = [("6", "GCC countries live"), ("2,300+", "automated tests"), ("AWS", "ECS Fargate in production")]

    role_els = "".join(
        f'<g class="role{" alt" if i else ""}" {delay(1.0 + i * 3)}>'
        + text(72, 186, r, 22, "regular", SOFT)
        + "</g>"
        for i, r in enumerate(roles)
    )
    stat_els = "".join(
        f'<g class="rise" {delay(.55 + i * .12)}>'
        + text(620, 74 + i * 62, n, 26, "semibold", TEXT)
        + text(620, 96 + i * 62, l, 14, "mono", MUTED)
        + "</g>"
        for i, (n, l) in enumerate(stats)
    )
    ground, _ = panel(w, h)
    body = (
        '<defs><radialGradient id="glow"><stop offset="0" stop-color="#F4C25B" stop-opacity=".2"/>'
        '<stop offset="1" stop-color="#F4C25B" stop-opacity="0"/></radialGradient>'
        f'<clipPath id="card"><rect width="{w}" height="{h}" rx="20"/></clipPath>'
        '<clipPath id="nameclip"><rect x="40" y="60" width="560" height="78"/></clipPath></defs>'
        + ground
        + '<g clip-path="url(#card)"><circle class="glow" cx="760" cy="10" r="260" fill="url(#glow)"/></g>'
        + '<g clip-path="url(#nameclip)"><g class="name">'
        + text(44, 120, name, 58, "semibold", TEXT, extra='letter-spacing="-1.2"')
        + "</g></g>"
        + f'<line class="underline" x1="46" y1="142" x2="{46 + name_w - 20:.1f}" y2="142" '
        f'stroke="{GOLD}" stroke-width="3" stroke-linecap="round"/>'
        + text(44, 186, "/", 22, "regular", GOLD, cls="fade", extra=delay(.8))
        + role_els
        + f'<line x1="584" y1="44" x2="584" y2="206" stroke="{LINE}"/>'
        + stat_els
    )
    line_len = name_w - 20
    css = (
        f".name{{animation:nameIn 1s {EASE} backwards}}"
        f"@keyframes nameIn{{from{{transform:translateY(80px)}}}}"
        f".underline{{stroke-dasharray:{line_len:.0f};animation:draw 1.1s .45s {EASE} backwards}}"
        f"@keyframes draw{{from{{stroke-dashoffset:{line_len:.0f}}}}}"
        ".glow{animation:drift 16s ease-in-out infinite alternate}"
        "@keyframes drift{to{transform:translate(-140px,60px)}}"
        ".alt{opacity:0}"
        ".role{animation:cycle 9s ease-in-out infinite backwards}"
        "@keyframes cycle{0%{opacity:0;transform:translateY(12px)}"
        "5%,30%{opacity:1;transform:translateY(0)}"
        "35%,100%{opacity:0;transform:translateY(-12px)}}"
    )
    label = "Louay Kashkool. Full-Stack Software Engineer, DevOps and Cloud Security."
    return svg(w, h, body, ["regular", "semibold", "mono"], css, label)


# ---------------------------------------------------------------- section titles


def build_section(title, theme):
    w, h = 880, 56
    color, accent = (TEXT, GOLD) if theme == "dark" else (LIGHT_TEXT, LIGHT_GOLD)
    tw = measure(title, "semibold", 26)
    x1 = 4 + tw + 20
    length = w - 2 - x1
    body = (
        text(2, 38, title, 26, "semibold", color, cls="rise", extra='letter-spacing="-.4"')
        + f'<line class="rule" x1="{x1:.1f}" y1="29" x2="{w - 2}" y2="29" stroke="{accent}" '
        f'stroke-opacity=".55" stroke-width="1.5" stroke-linecap="round"/>'
    )
    css = (
        f".rule{{stroke-dasharray:{length:.0f};animation:draw 1.4s .2s {EASE} backwards}}"
        f"@keyframes draw{{from{{stroke-dashoffset:{length:.0f}}}}}"
    )
    return svg(w, h, body, ["semibold"], css, title)


# ---------------------------------------------------------------- project cards


def build_featured(shot, title, role, subtitle, tags):
    w, pad = 880, 20
    img_w = w - 2 * pad
    with Image.open(shot) as im:
        img_h = round(img_w * im.height / im.width)
    ty = pad + img_h + 46
    sub_lines = wrap(subtitle, "regular", 17, img_w)
    chips_y = ty + 22 + 26 * len(sub_lines)
    h = chips_y + 28 + 24
    ground, beam_css = panel(w, h, beam=True)
    role_w = measure(role, "mono", 13) + 24
    body = (
        f"<defs>{SHEEN_DEFS}</defs>"
        + ground
        + screenshot(jpeg_uri(shot, 1400), pad, pad, img_w, img_h)
        + text(pad + 2, ty, title, 32, "semibold", TEXT, cls="rise", extra=f'letter-spacing="-.6" {delay(.25)}')
        + f'<g class="rise" {delay(.3)}>'
        f'<rect x="{w - pad - role_w:.1f}" y="{ty - 22}" width="{role_w:.1f}" height="28" rx="14" '
        f'fill="{GOLD}" fill-opacity=".12" stroke="{GOLD}" stroke-opacity=".45"/>'
        + text(w - pad - role_w + 12, ty - 3.5, role, 13, "mono", GOLD)
        + "</g>"
        + "".join(
            text(pad + 2, ty + 30 + i * 26, ln, 17, "regular", MUTED, cls="rise", extra=delay(.35))
            for i, ln in enumerate(sub_lines)
        )
        + chips(tags, pad + 2, chips_y, .45)
    )
    css = beam_css + sheen_css(img_w + 700)
    return svg(w, h, body, ["regular", "semibold", "mono"], css, f"{title}. {subtitle}")


def build_card(shot, title, lines, tags):
    w, h, pad = 880, 290, 20
    img_w, img_h = 400, 250
    tx = pad + img_w + 32
    text_w = w - tx - pad
    desc = [ln for para in lines for ln in wrap(para, "regular", 16, text_w)]
    ground, _ = panel(w, h)
    body = (
        f"<defs>{SHEEN_DEFS}</defs>"
        + ground
        + screenshot(jpeg_uri(shot, 900), pad, pad, img_w, img_h)
        + text(tx, 66, title, 26, "semibold", TEXT, cls="rise", extra=f'letter-spacing="-.4" {delay(.25)}')
        + "".join(
            text(tx, 102 + i * 25, ln, 16, "regular", MUTED, cls="rise", extra=delay(.32 + i * .05))
            for i, ln in enumerate(desc)
        )
        + chips(tags, tx, pad + img_h - 28, .45)
    )
    return svg(w, h, body, ["regular", "semibold", "mono"], sheen_css(img_w + 520), f"{title}. {' '.join(lines)}")


# ---------------------------------------------------------------- buttons and link cards


def build_button(label, primary):
    h = 44
    tw = measure(label, "medium", 15)
    w = round(22 + tw + 10 + 16 + 18)
    fill, fg, stroke = (GOLD, INK, GOLD) if primary else (SURFACE, TEXT, LINE)
    arrow = GOLD if not primary else INK
    body = (
        f'<clipPath id="pill"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="21"/></clipPath>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="21.5" fill="{fill}" stroke="{stroke}"/>'
        + text(22, 27.5, label, 15, "medium", fg)
        + f'<g class="arrow">{icon("tb-arrow-up-right", 22 + tw + 10, 14, 16, arrow)}</g>'
    )
    css = (
        ".arrow{animation:nudge 4s 1.5s ease-in-out infinite}"
        "@keyframes nudge{0%,80%,100%{transform:translate(0,0)}88%{transform:translate(2px,-2px)}}"
    )
    if primary:
        body = (
            f'<defs><linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
            f"</linearGradient></defs>"
            + body
            + f'<g clip-path="url(#pill)"><g transform="skewX(-20)">'
            f'<rect class="shine" x="-70" y="-10" width="46" height="{h + 20}" fill="url(#shine)"/></g></g>'
        )
        css += (
            ".shine{animation:shine 5s 1s ease-in-out infinite}"
            f"@keyframes shine{{0%{{transform:translateX(0)}}25%,100%{{transform:translateX({w + 140}px)}}}}"
        )
    return svg(w, h, body, ["medium"], css, label)


def build_link(label, handle, icon_name, index):
    w, h = 280, 92
    handle_size = 13.5
    while measure(handle, "regular", handle_size) > w - 84 - 20 and handle_size > 11:
        handle_size -= .5
    body = (
        f'<g class="rise" {delay(.08 * index)}>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="16" fill="{BG}" stroke="{LINE}"/>'
        f'<rect x="20" y="22" width="48" height="48" rx="12" fill="{GOLD}" fill-opacity=".1" '
        f'stroke="{GOLD}" stroke-opacity=".3"/>'
        + icon(icon_name, 32, 34, 24, GOLD)
        + text(84, 43, label, 17, "semibold", TEXT)
        + text(84, 66, handle, handle_size, "regular", MUTED)
        + f'<g class="arrow">{icon("tb-arrow-up-right", w - 34, 16, 16, MUTED)}</g>'
        + "</g>"
    )
    css = (
        f".arrow{{animation:nudge 5s {1.5 + .3 * index:.1f}s ease-in-out infinite}}"
        "@keyframes nudge{0%,80%,100%{transform:translate(0,0)}88%{transform:translate(2px,-2px)}}"
    )
    return svg(w, h, body, ["regular", "semibold"], css, f"{label}: {handle}")


# ---------------------------------------------------------------- main


def write(name, content):
    (OUT / name).write_text(content, encoding="utf-8")
    print(f"{name:32} {len(content.encode()) / 1024:7.1f} KB")


def main():
    fetch_vendor()
    write("header.svg", build_header())
    for slug, title in [("about", "About me"), ("projects", "Projects"), ("skills", "Skill stack"),
                        ("stats", "Stats"), ("links", "Links")]:
        for theme in ("dark", "light"):
            write(f"section-{slug}-{theme}.svg", build_section(title, theme))

    write("project-jadwal.svg", build_featured(
        ROOT / "jadwal-screenshot.png", "Jadwal", "Founding engineer",
        "GCC event-booking marketplace, live in Qatar, KSA, UAE, Bahrain, Oman and Kuwait.",
        ["NestJS", "Next.js", "PostgreSQL", "AWS ECS Fargate", "2,300+ tests"]))
    write("project-portfolio.svg", build_card(
        ROOT / "portfolio-screenshot.png", "Portfolio Website",
        ["My personal portfolio showcasing projects and experience."],
        ["Next.js", "three.js", "TypeScript"]))
    write("project-gold-store.svg", build_card(
        ROOT / "gold-store-screenshot.png", "Gold Store Web App",
        ["A modern store platform for managing and browsing gold products.",
         "Arabic storefront with live gold prices."],
        ["React", "Express", "MongoDB"]))

    write("btn-live-site.svg", build_button("Live site", True))
    write("btn-live-app.svg", build_button("Live app", True))
    write("btn-source.svg", build_button("Source", False))

    links = [("Portfolio", "louaykashkool-portfolio", "tb-world"),
             ("Jadwal", "jadwal.qa", "tb-calendar-event"),
             ("Gold Store", "nizarjewellery.com", "tb-building-store"),
             ("Email", "Loaekashkoool@gmail.com", "tb-mail"),
             ("LinkedIn", "louay-kashkool", "si-linkedin"),
             ("Instagram", "@l.k_2910", "si-instagram")]
    for i, (label, handle, ic) in enumerate(links):
        write(f"link-{label.lower().replace(' ', '-')}.svg", build_link(label, handle, ic, i))


if __name__ == "__main__":
    main()
