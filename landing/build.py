# -*- coding: utf-8 -*-
"""
landing/build.py — inline images into the landing page.

Reads page.html (content body with __ICON__ / __PLATE__ tokens) and produces:
  - index.html    : full standalone document (for GitHub Pages deploy)
  - artifact.html : content body only (for the Artifact preview tool)
  - CNAME         : custom domain

Images are embedded as base64 data URIs so the result is a single self-contained
file — trivial to host (one file + CNAME).
"""
import base64, os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

ICON  = os.path.join(REPO, "toris_collection", "static", "icons", "icon-512.png")
PLATE = os.path.join(REPO, "ヘッダー.png")
MEDIA = os.path.join(HERE, "media")
DOMAIN = "torriscollection.com"

def data_uri(path, mime="image/png"):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"

body = open(os.path.join(HERE, "page.html"), encoding="utf-8").read()
body = (body
        .replace("__ICON__", data_uri(ICON))
        .replace("__PLATE__", data_uri(PLATE))
        .replace("__SHOT_WELCOME__", data_uri(os.path.join(MEDIA, "shot_welcome.png")))
        .replace("__SHOT_MEETING__", data_uri(os.path.join(MEDIA, "shot_meeting.png")))
        .replace("__VIDEO__", data_uri(os.path.join(MEDIA, "showcase.mp4"), "video/mp4"))
        .replace("__AUDIO__", data_uri(os.path.join(MEDIA, "garden_radio.mp3"), "audio/mpeg")))

# artifact.html = body only (Artifact injects <head>/<body>)
open(os.path.join(HERE, "artifact.html"), "w", encoding="utf-8").write(body)

FAVICON = data_uri(ICON)
HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Toris Collection — grow a tiny ecosystem, the birds come and sing</title>
<meta name="description" content="A passive, healing bird companion. Tend a small biome in your hand; real birds arrive to sing. No rushing, no chores — just listen. Coming soon." />
<link rel="icon" href="{FAVICON}" />
<meta property="og:type" content="website" />
<meta property="og:title" content="Toris Collection" />
<meta property="og:description" content="Grow a tiny ecosystem. The birds come, and sing. A passive, healing bird companion — coming soon." />
<meta property="og:url" content="https://{DOMAIN}/" />
<meta name="twitter:card" content="summary_large_image" />
<style>html{{background:#f3f5ee}}@media(prefers-color-scheme:dark){{html{{background:#151a12}}}}</style>
</head>
<body>
"""
FOOT = "\n</body>\n</html>\n"
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(HEAD + body + FOOT)

open(os.path.join(HERE, "CNAME"), "w", encoding="utf-8", newline="").write(DOMAIN + "\n")

for f in ("index.html", "artifact.html", "CNAME"):
    p = os.path.join(HERE, f)
    print(f"  {f:14s} {os.path.getsize(p):>9,} bytes")
print("build ok")
