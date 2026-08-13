"""セーブコードの Python 版と Dart 版が**同じものを読み書きする**ことを機械で示す。

移行で唯一「壊したら取り返しがつかない」のがセーブコードである。個人の進行データは
サーバーに無く、この文字列としてのみユーザーの手元にある(提案書 §3
「セーブコードの互換だけは必ず守る」)。移植した/しないの申告ではなく、
**両方向で読めること**を毎回確かめられるようにする。

    py -3 tools/save_code_fixtures.py --emit     # Python が書いたコードを置く
    (dart test を走らせる)                        # Dart が読み、Dart が書いて置き返す
    py -3 tools/save_code_fixtures.py --verify   # Dart が書いたコードを Python が読む
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import save_code  # noqa: E402

FIX_DIR = os.path.join(os.path.dirname(__file__), "..", "toris_core", "test",
                       "fixtures")
FROM_PY = os.path.join(FIX_DIR, "from_python.json")
FROM_DART = os.path.join(FIX_DIR, "from_dart.json")

# set 型のキーは JSON に書けないので、ここでは並べ替えた配列で表す
# (Dart 側のテストが setKeys を見て Set に戻す)。
CASES = {
    "empty": {},
    "typical": {
        "biome": "kyoto",
        "planted": ["sakura", "himawari"],
        "planted_at_map": {"sakura": "2026-08-01T10:00:00"},
        "residents": ["eurasian_jay", "japanese_tit"],
        "discovered": ["eurasian_jay", "japanese_tit", "brown_eared_bulbul"],
        "bird_days": {"eurasian_jay": 12, "japanese_tit": 3},
        "mementos": [{"id": "feather", "at": "2026-08-02"}],
        "mementos_set": ["feather", "acorn"],
        "bird_notes": {"eurasian_jay": "枝の上でじっとしていた"},
        "observed": {"eurasian_jay": 4},
        "eco_log": [
            {"bird": "eurasian_jay", "why": "ドングリを食べに来た", "at": "2026-08-02"},
            {"bird": "japanese_tit", "why": "毛虫を探しに来た", "at": "2026-08-03"},
        ],
        "current_tester_id": "local_51c4923cd2c9",
        "saved_at": "2026-08-13T09:15:30",
    },
    # 日本語・絵文字・改行など、詰め方(ensure_ascii)の違いが出やすいもの
    "unicode": {
        "biome": "kyoto",
        "bird_notes": {"x": "ここに🐦がいた\n二行目\t\"引用符\" と \\ 記号"},
        "discovered": ["ズアオアトリ", "ヨーロッパコマドリ"],
    },
    # 数の型(int/float)と真偽値、深い入れ子
    "numbers": {
        "bird_days": {"a": 0, "b": 1000000},
        "observed": {"a": 1},
        "eco_log": [{"n": 1.5, "ok": True, "none": None, "deep": {"k": [1, 2, 3]}}],
    },
}


def emit() -> None:
    os.makedirs(FIX_DIR, exist_ok=True)
    out = []
    for name, state in CASES.items():
        # set 型に戻してからエンコードする(実際の session_state と同じ形にする)
        real = dict(state)
        expected = dict(state)
        for k in save_code.SET_KEYS:
            if k in real:
                real[k] = set(real[k])
                # 期待値は**並べ替えた後**の形にする。set は順序を持たないので、
                # 保存時に sorted() される(save_code._build_payload)。
                expected[k] = sorted(state[k])
        out.append({
            "name": name,
            "state": expected,
            "code": save_code.encode_save(real),
        })

    # 壊れたコード・旧形式・バージョン違いなど、読めない/読めるの境目
    import base64 as b64
    import zlib
    old_raw = json.dumps({"v": 1, "data": {"biome": "kyoto"}},
                         ensure_ascii=False, separators=(",", ":")).encode()
    edge = [
        {"name": "broken", "code": "!!!not base64!!!", "expect": None},
        {"name": "empty_string", "code": "", "expect": None},
        {"name": "not_json",
         "code": b64.urlsafe_b64encode(zlib.compress(b"hello", 9)).decode(),
         "expect": None},
        {"name": "wrong_version",
         "code": save_code.encode_save({}).replace("x", "x"),  # 差し替えは下で
         "expect": "skip"},
        # 圧縮前(2026-07-11 より古い)のコードも読めること
        {"name": "legacy_uncompressed",
         "code": b64.urlsafe_b64encode(old_raw).decode(),
         "expect": {"biome": "kyoto"}},
    ]
    # バージョン違いは v を変えて作る
    bad_ver = json.dumps({"v": 999, "data": {"biome": "kyoto"}},
                         separators=(",", ":")).encode()
    edge[3] = {"name": "wrong_version",
               "code": b64.urlsafe_b64encode(zlib.compress(bad_ver, 9)).decode(),
               "expect": None}

    with open(FROM_PY, "w", encoding="utf-8") as f:
        json.dump({"cases": out, "edge": edge, "set_keys": list(save_code.SET_KEYS)},
                  f, ensure_ascii=False, indent=1)
    print(f"emit: {len(out)} 件 + 境界 {len(edge)} 件 -> {os.path.abspath(FROM_PY)}")


def verify() -> int:
    """Dart が書いたコードを Python で読み、元の状態と一致するか確かめる。"""
    if not os.path.exists(FROM_DART):
        print(f"!! {FROM_DART} が無い。先に dart test を走らせること。")
        return 1
    with open(FROM_DART, encoding="utf-8") as f:
        items = json.load(f)

    bad = 0
    for it in items:
        name, code, expect = it["name"], it["code"], it["state"]
        got = save_code.decode_save(code)
        if got is None:
            print(f"  [NG] {name}: Python が読めなかった")
            bad += 1
            continue
        # 比較のため set を並べ替えた配列に戻す
        norm = {k: (sorted(v) if isinstance(v, set) else v) for k, v in got.items()}
        if norm != expect:
            print(f"  [NG] {name}: 中身が違う")
            for k in set(norm) | set(expect):
                if norm.get(k) != expect.get(k):
                    print(f"        {k}: Dart={norm.get(k)!r} 期待={expect.get(k)!r}")
            bad += 1
        else:
            print(f"  [OK] {name}: Dart が書いたコードを Python が読めた({len(code)}文字)")
    print(f"\n{'すべて一致' if not bad else f'{bad} 件が不一致'}")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--verify" in sys.argv:
        raise SystemExit(verify())
    emit()
