"""CDP経由でWebViewのDOMを読み、flockメーターの文字を確認する(タップ不要・非侵襲)。

実機のアプリ(Capacitor WebView, remote URL)に adb forward したポート経由で接続し、
Runtime.evaluate で在籍鳥チップのメーター文字を数える。
"""
import json
import sys

import websocket

WS_URL = sys.argv[1]

JS = r"""
(function(){
  // メーターだけのspan(鳥名を含まず、▮▯●○等の記号のみ)を textContent で拾う
  // (textContent は display:none の非アクティブタブも含む)。
  var meterSpans = Array.from(document.querySelectorAll('span'))
    .map(function(s){ return (s.textContent||"").trim(); })
    .filter(function(x){ return x.length>0 && /^[●○▮▯■□���]+$/.test(x); });
  var sample = meterSpans[0] || "";
  var codes = Array.from(sample).map(function(c){ return c.codePointAt(0); });
  // 全メーターspanを連結して各記号の出現数
  var all = meterSpans.join("");
  function cnt(cp){ var n=0; for (var i=0;i<all.length;i++){ if(all.codePointAt(i)===cp) n++; } return n; }
  return JSON.stringify({
    meter_span_count: meterSpans.length,
    first_meter_codepoints: codes,          // 例: [9679,9679,9675,9675,9675]
    n_25CF_filled_dot: cnt(0x25CF),          // ●
    n_25CB_empty_dot:  cnt(0x25CB),          // ○
    n_25AE_old_filled: cnt(0x25AE),          // ▮
    n_25AF_old_empty:  cnt(0x25AF)           // ▯
  });
})()
"""


def main():
    ws = websocket.create_connection(WS_URL, timeout=15, suppress_origin=True)
    def send(i, method, params=None):
        ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == i:
                return msg
    send(1, "Runtime.enable")
    r = send(2, "Runtime.evaluate", {"expression": JS, "returnByValue": True})
    val = r.get("result", {}).get("result", {}).get("value")
    print(val if val else json.dumps(r)[:800])
    ws.close()


if __name__ == "__main__":
    main()
