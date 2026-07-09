"""
test_xc_client.py - xc_client の商用ライセンス判定ロジック単体テスト

is_nc_only() は「録音はあるが全てNC(非商用)のため、COMMERCIAL_ONLY時に
鳴かせられない種」を判定する純粋ロジック(NC音源「準備中」表示の分岐に使う)。
ネットワークアクセスを避けるため search_recordings をモンキーパッチして検証する
(stdlib のみ、pytest 不要でも実行可能)。

実行: python3 toris_collection/tests/test_xc_client.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import xc_client  # noqa: E402


class _CommercialOnly:
    """xc_client.COMMERCIAL_ONLY を一時的に切り替える(テスト後に必ず元へ戻す)。"""

    def __init__(self, value: bool):
        self.value = value

    def __enter__(self):
        self._orig = xc_client.COMMERCIAL_ONLY
        xc_client.COMMERCIAL_ONLY = self.value
        return self

    def __exit__(self, *exc):
        xc_client.COMMERCIAL_ONLY = self._orig
        return False


class _FakeSearch:
    """xc_client.search_recordings を一時的にモンキーパッチする(テスト後に必ず元へ戻す)。

    recordings_by_query: {(quality, sound_type): [rec, ...]} 呼び出しごとに返す録音リスト。
    指定のない (quality, sound_type) の組には空リストを返す。
    """

    def __init__(self, recordings_by_query: dict):
        self.recordings_by_query = recordings_by_query

    def __enter__(self):
        self._orig = xc_client.search_recordings

        def fake(scientific_name, quality="A", sound_type="song"):
            return self.recordings_by_query.get((quality, sound_type), [])

        xc_client.search_recordings = fake
        return self

    def __exit__(self, *exc):
        xc_client.search_recordings = self._orig
        return False


def test_is_nc_only_false_when_commercial_only_disabled():
    # COMMERCIAL_ONLY=False のときは判定不要(常に無音化しない)なので常に False
    with _CommercialOnly(False):
        with _FakeSearch({("A", "song"): [{"lic": "//creativecommons.org/licenses/by-nc/4.0/"}]}):
            assert xc_client.is_nc_only("Parus minor") is False


def test_is_nc_only_true_when_all_recordings_nc():
    # 録音はあるが全部NC → NC-only 種として判定される(ウグイス相当のケース)
    with _CommercialOnly(True):
        with _FakeSearch({
            ("A", "song"): [{"lic": "//creativecommons.org/licenses/by-nc/4.0/"}],
            ("B", "call"): [{"lic": "//creativecommons.org/licenses/by-nc-sa/4.0/"}],
        }):
            assert xc_client.is_nc_only("Horornis diphone") is True


def test_is_nc_only_false_when_commercial_recording_exists():
    # 商用可(CC BY 等)の録音が1件でもあれば NC-only ではない
    with _CommercialOnly(True):
        with _FakeSearch({("A", "song"): [{"lic": "//creativecommons.org/licenses/by/4.0/"}]}):
            assert xc_client.is_nc_only("Passer montanus") is False


def test_is_nc_only_false_when_no_recordings_at_all():
    # 録音が1件も無い種(コゲラ相当)は「NC音源のため」ではなく別の「録音なし」表示のまま
    with _CommercialOnly(True):
        with _FakeSearch({}):
            assert xc_client.is_nc_only("Dendrocopos kizuki") is False


def test_is_nc_only_false_when_xc_disabled():
    # APIキー未設定(is_enabled()=False)のときは短絡して False
    with _CommercialOnly(True):
        orig_key = xc_client._API_KEY
        xc_client._API_KEY = None
        try:
            with _FakeSearch({("A", "song"): [{"lic": "//creativecommons.org/licenses/by-nc/4.0/"}]}):
                assert xc_client.is_nc_only("Parus minor") is False
        finally:
            xc_client._API_KEY = orig_key


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
