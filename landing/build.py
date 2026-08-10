# -*- coding: utf-8 -*-
"""
landing/build.py — inline images into the landing page.

Reads page.html (content body with __ICON__ / __PLATE__ tokens) and produces:
  - index.html    : full standalone document (for GitHub Pages deploy)
  - artifact.html : content body only (for the Artifact preview tool)
  - CNAME         : custom domain

Images are embedded as base64 data URIs so the result is a single self-contained
file — trivial to host (one file + CNAME).

`app-ads.txt` はこのスクリプトが生成するものではなく、手で置いた固定ファイル。
AdMob がアプリを確認するために `https://<ドメイン>/app-ads.txt` を直接クロールするので、
サイトのルートに素のまま公開されている必要がある(ビルドで加工してはいけない)。
中身の pub-ID は AdMob アカウント固有。ドメインは Google Play の掲載情報にある
ウェブサイトと一致していなければ確認が通らない。
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
        .replace("__VIDEO__", data_uri(os.path.join(MEDIA, "showcase.mp4"), "video/mp4")))

# 「何ができるか」を見せる実画面(やること順)。ストア掲載用に実機で撮ったものを
# Web 用に 540x960 / JPEG へ落としたもの(6枚で約290KB。原寸PNGだと約2MBになる)。
for token, fname in (
    ("__S_PLANT__",   "s_plant.jpg"),
    ("__S_GARDEN__",  "s_garden.jpg"),
    ("__S_BIRD__",    "s_bird.jpg"),
    ("__S_PROFILE__", "s_profile.jpg"),
    ("__S_RADIO__",   "s_radio.jpg"),
    ("__S_NETWORK__", "s_network.jpg"),
):
    body = body.replace(token, data_uri(os.path.join(MEDIA, fname), "image/jpeg"))

# artifact.html = body only (Artifact injects <head>/<body>)
open(os.path.join(HERE, "artifact.html"), "w", encoding="utf-8").write(body)

FAVICON = data_uri(ICON)
HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Toris Collection — grow a tiny ecosystem, the birds come and sing</title>
<meta name="description" content="A free Android app about a small garden that fills with real birds. Plant a little, let time pass, and every bird you meet joins a radio of real recorded songs. No chores, no rushing." />
<link rel="icon" href="{FAVICON}" />
<meta property="og:type" content="website" />
<meta property="og:title" content="Toris Collection" />
<meta property="og:description" content="A free Android app about a small garden that fills with real birds — and their real songs." />
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
