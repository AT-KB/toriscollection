"""
species_expand.py - GloBI をベースに種(と餌台・リス・Hawk の連鎖)を増やすための材料集め。

「なぜ来たか」の恣意ロジックは作らない。中心は GloBI の相互作用。
候補分類群について eats / eatenBy / preysOn を引き、
  - 鳥: 何を食べるか(既存 PLANTS/INSECTS に接続できるか)
  - リス等の mammal: 何を食べるか(餌台の種を共有するか) / 何に食べられるか(=Hawk を呼ぶ)
  - Hawk 等の raptor: 何を襲うか(preysOn = 警戒心の高い小鳥の到来を下げる)
を一覧化する。GloBI が通る環境(デプロイ先)で実行する前提。

このモジュールは globi_client 経由の read だけ。data は書き換えない(人がキュレーション)。
"""
from __future__ import annotations

import globi_client as gb

# ── 候補ロスター(学名, 和名, 役割) ─────────────────────────────
# 役割: bird / mammal(リス等) / raptor(Hawk等) / feature-food(餌台の中身)
CHARLOTTE_CANDIDATES = [
    ("Poecile carolinensis", "カロライナコガラ", "bird"),
    ("Spinus tristis", "アメリカゴシキヒワ", "bird"),
    ("Haemorhous mexicanus", "メキシコマシコ", "bird"),
    ("Turdus migratorius", "コマツグミ", "bird"),
    ("Melanerpes carolinus", "アカハラコゲラ", "bird"),
    ("Toxostoma rufum", "チャイロツグミモドキ", "bird"),
    ("Sciurus carolinensis", "ハイイロリス", "mammal"),
    ("Accipiter cooperii", "クーパーハイタカ", "raptor"),
    ("Buteo jamaicensis", "アカオノスリ", "raptor"),
]

KYOTO_CANDIDATES = [
    # 今回シードで追加した京都の新種(GloBI で食性を裏取りする対象)
    ("Streptopelia orientalis", "キジバト", "bird"),
    ("Alauda arvensis", "ヒバリ", "bird"),
    ("Lanius bucephalus", "モズ", "bird"),
    ("Phoenicurus auroreus", "ジョウビタキ", "bird"),
    ("Turdus pallidus", "シロハラ", "bird"),
    ("Emberiza spodocephala", "アオジ", "bird"),
    # 餌台連鎖用(将来)
    ("Sciurus lis", "ニホンリス", "mammal"),
    ("Accipiter gularis", "ツミ", "raptor"),
]

# 引く相互作用タイプ(全部 GloBI の型)
_ITYPES = ("eats", "eatenBy", "preysOn", "preyedUponBy")


def preview_taxon(scientific_name: str, limit: int = 60) -> dict:
    """1分類群について、相互作用タイプごとに相手の学名一覧を返す。"""
    out: dict[str, list[str]] = {}
    for itype in _ITYPES:
        targets = sorted({
            r.get("target_taxon_name")
            for r in gb.get_interactions(scientific_name, itype, limit=limit)
            if r.get("target_taxon_name")
        })
        if targets:
            out[itype] = targets
    return out


def preview_roster(roster: list[tuple]) -> list[dict]:
    """候補ロスター全体をプレビュー。各要素は {scientific, name, role, interactions}。"""
    rows = []
    for sci, name, role in roster:
        rows.append({
            "scientific": sci,
            "name": name,
            "role": role,
            "interactions": preview_taxon(sci),
        })
    return rows


def roster_for(biome_id: str) -> list[tuple]:
    return CHARLOTTE_CANDIDATES if biome_id == "charlotte" else KYOTO_CANDIDATES
