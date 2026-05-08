"""診断: xeno-canto と GloBI が動くか、1発で確認"""
import sys
print("=" * 60)
print("1. xeno-canto API v3 テスト (シジュウカラ)")
print("=" * 60)
try:
    import urllib.request, json, urllib.parse
    query = urllib.parse.quote("gen:Parus sp:minor q:A")
    url = f"https://xeno-canto.org/api/2/recordings?query={query}&key=demo"
    print(f"URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "test"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    print(f"→ OK: numRecordings={data.get('numRecordings')}, 取得={len(data.get('recordings', []))}件")
    if data.get('recordings'):
        rec = data['recordings'][0]
        print(f"  例: XC{rec.get('id')} file={rec.get('file','')[:80]}")
except Exception as e:
    print(f"→ 失敗: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("2. GloBI API テスト (シジュウカラが食べるもの)")
print("=" * 60)
try:
    import urllib.request, json, urllib.parse
    url = "https://api.globalbioticinteractions.org/interaction?sourceTaxon=Parus%20minor&interactionType=eats&limit=5&type=json"
    print(f"URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "test"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    print(f"→ OK: 列数={len(data.get('columns', []))}, 行数={len(data.get('data', []))}")
except Exception as e:
    print(f"→ 失敗: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("3. ネットワーク疎通確認 (google.com で正常接続チェック)")
print("=" * 60)
try:
    import urllib.request
    with urllib.request.urlopen("https://www.google.com", timeout=10) as r:
        print(f"→ OK: status={r.status}")
except Exception as e:
    print(f"→ 失敗: {type(e).__name__}: {e}")