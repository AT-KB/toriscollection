"""図鑑の詳細ドット絵(designbird/<種ID>_detail.png)の存在判定・パス解決。

Streamlit に依存しない純粋関数のみを置く(app.py からも tests からも import できる)。
designbird/{bird_id}_detail.png は種ごとに個別制作される高詳細ドット絵で、
既存の designbird/{bird_id}.png(簡易スプライト、SPRITE_ALIASES で流用あり)とは
同じフォルダ内だがファイル名で区別される別物(2026-07-08、CEO確定の命名規則)。
ここではエイリアス解決を一切行わない: ファイルが実在する種だけ True を返し、
無い種は常に False(呼び出し側は今まで通りの簡易スプライト表示のみを続ける)。
"""
from pathlib import Path

DETAIL_SPRITES_DIR = Path(__file__).parent / "designbird"
DETAIL_SUFFIX = "_detail"


def detail_image_path(bird_id: str, base_dir: Path | None = None) -> Path:
    """種IDに対応する詳細ドット絵のパスを返す(存在有無は問わない)。"""
    base = base_dir if base_dir is not None else DETAIL_SPRITES_DIR
    return Path(base) / f"{bird_id}{DETAIL_SUFFIX}.png"


def has_detail_image(bird_id: str, base_dir: Path | None = None) -> bool:
    """designbird/{bird_id}_detail.png が存在するか(厳密一致、エイリアスなし)。"""
    return detail_image_path(bird_id, base_dir).is_file()
