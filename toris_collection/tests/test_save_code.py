"""
test_save_code.py - セーブコード(save_code.py)の往復ロジック単体テスト

実行: python3 toris_collection/tests/test_save_code.py
依存なし(pytest 不要、stdlib のみ)。encode_save / decode_save は
Streamlit にも依存しない純粋関数。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import save_code  # noqa: E402


def _sample_state():
    return {
        "biome": "kyoto",
        "planted": ["sakura", "kaede"],
        "planted_at_map": {"sakura": "2026-06-01T08:00:00"},
        "residents": {"shijukara", "mejiro"},
        "discovered": {"shijukara", "mejiro", "suzume"},
        "bird_days": {"shijukara": {"days": 3, "last": "2026-07-01"}},
        "mementos": [{"memento_id": "feather:shijukara", "kind": "feather"}],
        "mementos_set": {"feather:shijukara"},
        "bird_notes": {"shijukara": "庭の隅で会った"},
        "observed": {"shijukara": {"count": 2, "first": "", "last": ""}},
        "eco_log": [
            {"bird_id": "shijukara", "text": "サクラの虫を求めて来た",
             "first_at": "2026-07-01T08:00:00"},
            {"bird_id": "mejiro", "text": "花の蜜を求めて来た",
             "first_at": "2026-07-02T09:00:00"},
        ],
        "current_tester_id": "local_abcdef",
        "saved_at": "2026-07-04T12:00:00",
    }


def test_round_trip_preserves_data():
    state = _sample_state()
    code = save_code.encode_save(state)
    restored = save_code.decode_save(code)
    assert restored is not None
    assert restored["biome"] == "kyoto"
    assert restored["planted"] == ["sakura", "kaede"]
    assert restored["residents"] == {"shijukara", "mejiro"}
    assert restored["discovered"] == {"shijukara", "mejiro", "suzume"}
    assert restored["bird_days"] == state["bird_days"]
    assert restored["mementos"] == state["mementos"]
    assert restored["mementos_set"] == {"feather:shijukara"}
    assert restored["bird_notes"] == state["bird_notes"]
    assert restored["observed"] == state["observed"]
    assert restored["eco_log"] == state["eco_log"]
    assert restored["saved_at"] == "2026-07-04T12:00:00"


def test_round_trip_preserves_eco_log_as_plain_list_no_set_conversion():
    # eco_log は list[dict] であり SET_KEYS には含まれない(set化は不要)。
    # 順序・中身とも完全に保持されることを確認する。
    state = {"eco_log": [
        {"bird_id": "b1", "text": "t1", "first_at": "2026-07-01T00:00:00"},
        {"bird_id": "b1", "text": "t2", "first_at": "2026-07-02T00:00:00"},
        {"bird_id": "b2", "text": "t1", "first_at": "2026-07-03T00:00:00"},
    ]}
    code = save_code.encode_save(state)
    restored = save_code.decode_save(code)
    assert isinstance(restored["eco_log"], list)
    assert restored["eco_log"] == state["eco_log"]


def test_round_trip_handles_empty_eco_log():
    state = {"eco_log": []}
    code = save_code.encode_save(state)
    restored = save_code.decode_save(code)
    assert restored["eco_log"] == []


def test_round_trip_sets_survive_json_conversion():
    # set は JSON非対応のため list を経由する。順序に依存せず内容が一致すればよい。
    state = {"residents": {"a", "b", "c"}, "discovered": set()}
    code = save_code.encode_save(state)
    restored = save_code.decode_save(code)
    assert restored["residents"] == {"a", "b", "c"}
    assert restored["discovered"] == set()
    assert isinstance(restored["residents"], set)


def test_encode_ignores_keys_outside_allowlist():
    state = _sample_state()
    state["secret_password"] = "should-not-be-saved"
    state["_internal_cache"] = object()  # JSON化できない値でも無視されるべき
    code = save_code.encode_save(state)
    restored = save_code.decode_save(code)
    assert "secret_password" not in restored
    assert "_internal_cache" not in restored


def test_decode_rejects_invalid_base64():
    assert save_code.decode_save("!!!not-base64-or-json!!!") is None


def test_decode_rejects_garbage_json():
    # base64としては正しくデコードできるが中身がJSONでない文字列
    import base64
    broken = base64.urlsafe_b64encode(b"not a json payload").decode("ascii")
    assert save_code.decode_save(broken) is None


def test_decode_rejects_truncated_valid_code():
    state = _sample_state()
    code = save_code.encode_save(state)
    truncated = code[: len(code) // 2]
    assert save_code.decode_save(truncated) is None


def test_decode_rejects_version_mismatch():
    import base64
    import json
    envelope = {"v": 999, "data": {"biome": "kyoto"}}
    raw = json.dumps(envelope).encode("utf-8")
    code = base64.urlsafe_b64encode(raw).decode("ascii")
    assert save_code.decode_save(code) is None


def test_decode_ignores_unknown_keys_in_payload():
    import base64
    import json
    envelope = {
        "v": save_code.SAVE_FORMAT_VERSION,
        "data": {"biome": "sydney", "totally_unknown_field": "hack"},
    }
    raw = json.dumps(envelope).encode("utf-8")
    code = base64.urlsafe_b64encode(raw).decode("ascii")
    restored = save_code.decode_save(code)
    assert restored is not None
    assert restored["biome"] == "sydney"
    assert "totally_unknown_field" not in restored


def test_decode_rejects_non_dict_envelope():
    import base64
    import json
    raw = json.dumps([1, 2, 3]).encode("utf-8")
    code = base64.urlsafe_b64encode(raw).decode("ascii")
    assert save_code.decode_save(code) is None


def test_decode_rejects_non_dict_data_field():
    import base64
    import json
    envelope = {"v": save_code.SAVE_FORMAT_VERSION, "data": "not-a-dict"}
    raw = json.dumps(envelope).encode("utf-8")
    code = base64.urlsafe_b64encode(raw).decode("ascii")
    assert save_code.decode_save(code) is None


def test_decode_empty_or_non_string_input():
    assert save_code.decode_save("") is None
    assert save_code.decode_save(None) is None


def test_encode_handles_empty_state():
    code = save_code.encode_save({})
    restored = save_code.decode_save(code)
    assert restored == {}


def test_build_current_snapshot_only_includes_known_keys():
    import datetime
    state = _sample_state()
    state["secret_password"] = "nope"
    snap = save_code.build_current_snapshot(
        state, now=datetime.datetime(2026, 7, 9, 10, 0, 0))
    assert "secret_password" not in snap
    assert snap["biome"] == "kyoto"
    assert snap["saved_at"] == "2026-07-09T10:00:00"


def test_build_current_snapshot_defaults_saved_at_to_now():
    snap = save_code.build_current_snapshot({"biome": "kyoto"})
    assert "saved_at" in snap and snap["saved_at"]


def test_encode_current_state_round_trips_like_encode_save():
    import datetime
    state = _sample_state()
    now = datetime.datetime(2026, 7, 9, 10, 0, 0)
    code = save_code.encode_current_state(state, now=now)
    restored = save_code.decode_save(code)
    assert restored is not None
    assert restored["biome"] == "kyoto"
    assert restored["residents"] == {"shijukara", "mejiro"}
    assert restored["saved_at"] == "2026-07-09T10:00:00"


def test_encode_current_state_supports_dict_like_session_state():
    # st.session_state は dict そのものではないが .get(key, default) を持つ。
    # ここでは通常の dict で「.get だけに依存する」実装であることを確認する。
    class FakeSessionState(dict):
        pass

    state = FakeSessionState(_sample_state())
    code = save_code.encode_current_state(state)
    restored = save_code.decode_save(code)
    assert restored is not None
    assert restored["biome"] == "kyoto"


def _large_realistic_state():
    """長時間プレイを想定した大きめの状態(圧縮効果・URL長対策の検証用)。
    モジュールdocstring記載の実測(discovered=全37種+mementos全カタログ+eco_log多数で
    約54,000文字)に近づけるため、37種分の図鑑・落とし物・生態ログ・メモを
    日本語テキストで生成する。
    """
    bird_ids = [f"bird_{i:03d}" for i in range(37)]
    discovered = set(bird_ids)
    residents = set(bird_ids[:20])
    mementos = []
    mementos_set = set()
    bird_days = {}
    bird_notes = {}
    observed = {}
    eco_log = []
    reasons = [
        "サクラの花の蜜を求めて庭に来た",
        "カエデの木に潜む虫を探しに来た",
        "冬の寒さをしのぐため餌台の周りに集まった",
        "縄張り争いの合間に水浴びをしに来た",
        "渡りの途中で羽を休めるために立ち寄った",
    ]
    for i, bird in enumerate(bird_ids):
        for kind in ("feather", "footprint", "eggshell"):
            memento_id = f"{kind}:{bird}"
            mementos.append({
                "memento_id": memento_id,
                "kind": kind,
                "bird_id": bird,
                "found_at": f"2026-0{(i % 6) + 1}-{(i % 28) + 1:02d}T08:00:00",
                "note": f"{bird}が残した{kind}。庭の隅で見つけた記録。",
            })
            mementos_set.add(memento_id)
        bird_days[bird] = {"days": (i % 30) + 1, "last": f"2026-07-{(i % 28) + 1:02d}"}
        bird_notes[bird] = f"{bird}とは庭で何度も会った。{reasons[i % len(reasons)]}。"
        observed[bird] = {"count": i + 1, "first": "2026-06-01T08:00:00",
                           "last": f"2026-07-{(i % 28) + 1:02d}T09:00:00"}
        for j in range(4):
            eco_log.append({
                "bird_id": bird,
                "text": reasons[(i + j) % len(reasons)],
                "first_at": f"2026-0{(j % 6) + 1}-{(i % 28) + 1:02d}T0{j}:00:00",
            })
    return {
        "biome": "kyoto",
        "planted": ["sakura", "kaede", "matsu", "ume", "tsubaki"],
        "planted_at_map": {p: "2026-06-01T08:00:00" for p in
                           ("sakura", "kaede", "matsu", "ume", "tsubaki")},
        "residents": residents,
        "discovered": discovered,
        "bird_days": bird_days,
        "mementos": mementos,
        "mementos_set": mementos_set,
        "bird_notes": bird_notes,
        "observed": observed,
        "eco_log": eco_log,
        "current_tester_id": "local_abcdef0123456789",
        "saved_at": "2026-07-11T12:00:00",
    }


def test_compression_shrinks_large_realistic_save_below_url_limit():
    # 圧縮なしで書き出した場合(旧実装相当)の長さを再現して比較する。
    import base64 as _b64
    import json as _json

    state = _large_realistic_state()
    payload = save_code._build_payload(state)
    envelope = {"v": save_code.SAVE_FORMAT_VERSION, "data": payload}
    raw = _json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    uncompressed_code = _b64.urlsafe_b64encode(raw).decode("ascii")

    compressed_code = save_code.encode_save(state)

    # 一般的なリバースプロキシ/WebサーバーのURL長上限の目安(8KB=8192文字)。
    URL_LIMIT_CHARS = 8192

    # 圧縮なしなら上限を大きく超える規模のサンプルであることを前提として確認する
    # (この前提が崩れたら、圧縮対策の意義を示すテストとして機能しなくなるため)。
    assert len(uncompressed_code) > URL_LIMIT_CHARS, (
        f"サンプルが小さすぎて対策の効果を検証できない: {len(uncompressed_code)}文字"
    )

    # 圧縮後は上限を十分に下回ること。
    assert len(compressed_code) < URL_LIMIT_CHARS, (
        f"圧縮後もURL長上限を超えている: {len(compressed_code)}文字"
    )

    # 圧縮率がおおむね実測(約1/16)に近い、大幅な圧縮になっていること。
    assert len(compressed_code) < len(uncompressed_code) * 0.5

    # 圧縮しても中身は完全に一致して復元できること。
    restored = save_code.decode_save(compressed_code)
    assert restored is not None
    assert restored["discovered"] == state["discovered"]
    assert restored["mementos_set"] == state["mementos_set"]
    assert len(restored["eco_log"]) == len(state["eco_log"])
    assert restored["bird_notes"] == state["bird_notes"]


def test_decode_save_reads_legacy_uncompressed_code_for_backward_compatibility():
    # 2026-07-11のzlib圧縮導入より前に書き出された「圧縮なしの生JSON」セーブコードが、
    # 導入後も引き続き読み込めることを確認する(後方互換性の要)。
    import base64 as _b64
    import json as _json

    state = _sample_state()
    payload = save_code._build_payload(state)
    envelope = {"v": save_code.SAVE_FORMAT_VERSION, "data": payload}
    raw = _json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    legacy_code = _b64.urlsafe_b64encode(raw).decode("ascii")  # zlib圧縮なし(旧形式)

    restored = save_code.decode_save(legacy_code)
    assert restored is not None
    assert restored["biome"] == "kyoto"
    assert restored["residents"] == {"shijukara", "mejiro"}
    assert restored["discovered"] == {"shijukara", "mejiro", "suzume"}
    assert restored["eco_log"] == state["eco_log"]
    assert restored["saved_at"] == "2026-07-04T12:00:00"


def test_decode_save_reads_legacy_uncompressed_empty_state():
    # 空状態の旧形式コードも例外にならず {} を返すこと。
    import base64 as _b64
    import json as _json

    envelope = {"v": save_code.SAVE_FORMAT_VERSION, "data": {}}
    raw = _json.dumps(envelope).encode("utf-8")
    legacy_code = _b64.urlsafe_b64encode(raw).decode("ascii")
    assert save_code.decode_save(legacy_code) == {}


def test_legacy_and_new_format_codes_decode_to_identical_data():
    # 同じ状態を「旧形式(圧縮なし)」「新形式(zlib圧縮)」それぞれで書き出しても、
    # decode_save の結果が完全に一致すること(利用者からは違いが見えないことの確認)。
    import base64 as _b64
    import json as _json

    state = _sample_state()
    payload = save_code._build_payload(state)
    envelope = {"v": save_code.SAVE_FORMAT_VERSION, "data": payload}
    raw = _json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    legacy_code = _b64.urlsafe_b64encode(raw).decode("ascii")

    new_code = save_code.encode_save(state)

    assert save_code.decode_save(legacy_code) == save_code.decode_save(new_code)
    # 新形式は圧縮されている分、旧形式より短くなる(この往復サンプルでも確認)。
    assert len(new_code) <= len(legacy_code)


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    _run()
