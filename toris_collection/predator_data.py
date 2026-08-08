"""predator_data.py - 図鑑「こわいもの」の実データ(自動生成)。

GloBI (Global Biotic Interactions) の preyedUponBy 実エッジから生成。
手で編集しない。更新するときは:
    py -3 tools/globi_predator_pull.py      # GloBI から再取得
    py -3 tools/build_predator_data.py      # このファイルを再生成

level='genus' は、その種自体の記録が GloBI に無く、同属の近縁種の記録から
採ったことを示す(誇張しないため区別して持つ。表示側で断りを添える)。
"""
from __future__ import annotations

PREDATORS: dict[str, dict] = {
    'american_robin': {
        'level': 'species',
        'categories': ['raptor', 'owl', 'snake'],
        'records': {'raptor': 12, 'owl': 8, 'snake': 6},
    },
    'aoji': {
        'level': 'genus',
        'categories': ['raptor', 'crow', 'owl'],
        'records': {'raptor': 105, 'crow': 70, 'owl': 60},
    },
    'blue_jay': {
        'level': 'species',
        'categories': ['raptor', 'snake'],
        'records': {'raptor': 8, 'snake': 6},
    },
    'brown_thrasher': {
        'level': 'species',
        'categories': ['snake', 'crow', 'raptor'],
        'records': {'snake': 8, 'crow': 6, 'raptor': 4},
    },
    'carolina_chickadee': {
        'level': 'species',
        'categories': ['owl', 'raptor'],
        'records': {'owl': 4, 'raptor': 4},
    },
    'carolina_wren': {
        'level': 'species',
        'categories': ['snake'],
        'records': {'snake': 4},
    },
    'cedar_waxwing': {
        'level': 'species',
        'categories': ['owl'],
        'records': {'owl': 4},
    },
    'enaga': {
        'level': 'species',
        'categories': ['owl', 'crow', 'rodent'],
        'records': {'owl': 16, 'crow': 10, 'rodent': 8},
    },
    'hibari': {
        'level': 'species',
        'categories': ['raptor', 'falcon', 'owl'],
        'records': {'raptor': 26, 'falcon': 18, 'owl': 14},
    },
    'house_finch': {
        'level': 'species',
        'categories': ['snake', 'falcon', 'raptor'],
        'records': {'snake': 8, 'falcon': 4, 'raptor': 4},
    },
    'jou_bitaki': {
        'level': 'genus',
        'categories': ['owl', 'raptor', 'crow'],
        'records': {'owl': 36, 'raptor': 24, 'crow': 24},
    },
    'kakesu': {
        'level': 'species',
        'categories': ['raptor', 'crow', 'owl'],
        'records': {'raptor': 14, 'crow': 10, 'owl': 8},
    },
    'kawarahiwa': {
        'level': 'genus',
        'categories': ['crow', 'owl', 'raptor'],
        'records': {'crow': 27, 'owl': 18, 'raptor': 18},
    },
    'kawasemi': {
        'level': 'species',
        'categories': ['fox', 'owl'],
        'records': {'fox': 6, 'owl': 4},
    },
    'kibitaki': {
        'level': 'genus',
        'categories': ['owl', 'rodent', 'crow'],
        'records': {'owl': 54, 'rodent': 46, 'crow': 40},
    },
    'kogera': {
        'level': 'genus',
        'categories': ['owl', 'raptor', 'rodent'],
        'records': {'owl': 12, 'raptor': 8, 'rodent': 8},
    },
    'mourning_dove': {
        'level': 'species',
        'categories': ['raptor', 'snake', 'falcon'],
        'records': {'raptor': 22, 'snake': 10, 'falcon': 8},
    },
    'mozu': {
        'level': 'species',
        'categories': ['weasel'],
        'records': {'weasel': 4},
    },
    'northern_cardinal': {
        'level': 'species',
        'categories': ['snake', 'crow', 'raptor'],
        'records': {'snake': 28, 'crow': 8, 'raptor': 8},
    },
    'red_bellied_woodpecker': {
        'level': 'species',
        'categories': ['raptor', 'snake'],
        'records': {'raptor': 6, 'snake': 4},
    },
    'shijukara': {
        'level': 'genus',
        'categories': ['owl', 'raptor', 'crow'],
        'records': {'owl': 66, 'raptor': 44, 'crow': 44},
    },
    'song_sparrow': {
        'level': 'species',
        'categories': ['snake', 'falcon', 'owl'],
        'records': {'snake': 10, 'falcon': 8, 'owl': 8},
    },
    'suzume': {
        'level': 'species',
        'categories': ['raptor', 'owl', 'crow'],
        'records': {'raptor': 20, 'owl': 18, 'crow': 14},
    },
    'tsubame': {
        'level': 'species',
        'categories': ['falcon', 'snake', 'raptor'],
        'records': {'falcon': 16, 'snake': 8, 'raptor': 8},
    },
    'tufted_titmouse': {
        'level': 'species',
        'categories': ['raptor', 'owl'],
        'records': {'raptor': 6, 'owl': 4},
    },
}
