"""
GloBI API が各鳥でデータを返すか一括診断する。
実行: py diagnose_globi.py > globi_diag.txt
"""
import urllib.request, json, urllib.parse

birds = [
    ("シジュウカラ", "Parus minor"),
    ("スズメ", "Passer montanus"),
    ("メジロ", "Zosterops japonicus"),
    ("ヒヨドリ", "Hypsipetes amaurotis"),
    ("ウグイス", "Horornis diphone"),
    ("カワセミ", "Alcedo atthis"),
    ("コゲラ", "Dendrocopos kizuki"),
    ("オオルリ", "Cyanoptila cyanomelana"),
    ("キビタキ", "Ficedula narcissina"),
    ("ツバメ", "Hirundo rustica"),
    ("アオサギ", "Ardea cinerea"),
    ("アカゲラ", "Dendrocopos major"),
]

print("=" * 70)
print("GloBI API 動作確認 (各鳥の eats 関係)")
print("=" * 70)

for name, sci in birds:
    url = (
        "https://api.globalbioticinteractions.org/interaction"
        f"?sourceTaxon={urllib.parse.quote(sci)}"
        "&interactionType=eats"
        "&field=source_taxon_name&field=interaction_type&field=target_taxon_name"
        "&limit=10"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        rows = len(d.get("data", []))
        print(f"\n{name:10s} ({sci}): {rows}件")
        for row in d.get("data", [])[:3]:
            print(f"    {row[0]} → {row[2]}")
    except Exception as e:
        print(f"\n{name:10s} ({sci}): 失敗 {type(e).__name__}: {e}")

# preysOn も同様に
print()
print("=" * 70)
print("参考: preysOn も試す (肉食性)")
print("=" * 70)
for name, sci in [("カワセミ", "Alcedo atthis"), ("アオサギ", "Ardea cinerea")]:
    url = (
        "https://api.globalbioticinteractions.org/interaction"
        f"?sourceTaxon={urllib.parse.quote(sci)}"
        "&interactionType=preysOn"
        "&field=source_taxon_name&field=interaction_type&field=target_taxon_name"
        "&limit=10"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        rows = len(d.get("data", []))
        print(f"\n{name} ({sci}): {rows}件")
        for row in d.get("data", [])[:3]:
            print(f"    {row[0]} → {row[2]}")
    except Exception as e:
        print(f"\n{name} ({sci}): {type(e).__name__}: {e}")
