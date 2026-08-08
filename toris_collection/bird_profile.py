"""bird_profile.py - 図鑑の「プロフィール」行を組み立てる純粋関数。

図鑑に「好きなもの / 好きな場所 / こわいもの」を出すための層。Streamlit に依存しない
(= テストできる)。文言の組み立ては行わず、**構造化データ**を返す。表示側(app.py)が
t() と表示名ヘルパーで描画する — engine が日本語文を組み立てて EN 画面に漏れた
過去の監査指摘(2026-08-02)を繰り返さないため。

原則との関係:
  - 原則4(生態に誠実): 好きなもの = 実際に食べるもの(eats_plants/eats_insects)、
    好きな場所 = 実際の biome_pref、こわいもの = GloBI の実際の捕食記録。
    作り話の「かわいい豆知識」は入れない。
  - 原則2(罰しない): ここは読み物であって、ゲーム進行には一切影響しない。
"""
from __future__ import annotations

import i18n
import predators


def likes(bird: dict, plants: dict, insects: dict) -> list[dict]:
    """「好きなもの」= 実際に食べる植物・昆虫。

    Returns: [{"kind": "plant"|"insect", "id": str, "entity": dict}, ...]
             図鑑に載っていない ID は静かに除外する(データ更新への安全弁)。
    """
    out: list[dict] = []
    for pid in bird.get("eats_plants") or []:
        ent = plants.get(pid)
        if ent:
            out.append({"kind": "plant", "id": pid, "entity": ent})
    for iid in bird.get("eats_insects") or []:
        ent = insects.get(iid)
        if ent:
            out.append({"kind": "insect", "id": iid, "entity": ent})
    return out


def home(bird: dict, biomes: dict) -> list[dict]:
    """「好きな場所」= 実際に好むバイオーム。

    Returns: [{"id": str, "entity": dict}, ...]
    """
    out: list[dict] = []
    for bid in bird.get("biome_pref") or []:
        ent = biomes.get(bid)
        if ent:
            out.append({"id": bid, "entity": ent})
    return out


def fears(bird_id: str) -> dict:
    """「こわいもの」= GloBI の実際の捕食記録(分類カテゴリ)。

    Returns: {"categories": [key, ...], "genus_level": bool}
             データが無ければ categories は空(=図鑑ではこの行を出さない)。
    """
    return {
        "categories": predators.categories(bird_id),
        "genus_level": predators.is_genus_level(bird_id),
    }


def build(bird_id: str, bird: dict, plants: dict, insects: dict,
          biomes: dict) -> dict:
    """図鑑プロフィールの全項目をまとめて返す。

    Returns: {"likes": [...], "home": [...], "fears": {...}}
             各項目は空になりうる(空の行は表示側で出さない=静かなトーン)。
    """
    return {
        "likes": likes(bird, plants, insects),
        "home": home(bird, biomes),
        "fears": fears(bird_id),
    }


def _biome_disp(biome: dict) -> str:
    """バイオームの表示名。英語表示では name_en(無ければ日本語 name)。
    app.py の _biome_display_name と同じ規則(バイオームだけ english ではなく name_en)。"""
    if i18n.get_lang() == "en" and biome.get("name_en"):
        return biome["name_en"]
    return biome.get("name", "")


def rows(bird_id: str, bird: dict, plants: dict, insects: dict,
         biomes: dict) -> list[tuple[str, str, str]]:
    """図鑑プロフィールを表示用の行にする。

    Returns: [(emoji, ラベル, 値), ...] すべて現在の表示言語。
             データの無い項目は行ごと落とす(空欄を並べない=静かなトーン)。

    文言の組み立てをここに集約するのは、Streamlit 抜きでテストできるようにするため
    (EN 画面への日本語漏れを機械的に検出できる状態を保つ)。
    """
    prof = build(bird_id, bird, plants, insects, biomes)
    sep = "、" if i18n.get_lang() == "ja" else ", "
    out: list[tuple[str, str, str]] = []

    if prof["likes"]:
        out.append(("🍽", i18n.t("好きなもの"),
                    sep.join(i18n.disp(x["entity"]) for x in prof["likes"])))

    if prof["home"]:
        out.append(("🏞", i18n.t("好きな場所"),
                    sep.join(_biome_disp(x["entity"]) for x in prof["home"])))

    if prof["fears"]["categories"]:
        value = sep.join(
            i18n.t(predators.CATEGORY_LABELS[k])
            for k in prof["fears"]["categories"]
        )
        if prof["fears"]["genus_level"]:
            # 同属の近縁種の記録から採ったものは、黙って種の事実にしない(原則4)。
            # 区切りの空白も言語に合わせる(全角スペースは EN 画面に混ぜない)。
            gap = "　" if i18n.get_lang() == "ja" else " "
            value += gap + i18n.t("(近縁のなかまの記録から)")
        out.append(("😨", i18n.t("こわいもの"), value))

    return out
