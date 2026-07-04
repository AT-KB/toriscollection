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
    assert restored["saved_at"] == "2026-07-04T12:00:00"


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
