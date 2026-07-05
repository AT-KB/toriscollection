// Toris Collection - 最小サービスワーカー(TWA/PWAインストール可能性のための下準備)
//
// 意図的に最小限。オフラインキャッシュ等の本格実装はしない
// (ラジオ・儀式・Sheets読み書きの挙動に一切影響させないため)。
// install/activate/fetch の3イベントに応答するだけで、
// 「有効なService Workerが存在する」という判定条件を満たす。
"use strict";

self.addEventListener("install", function (event) {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});

// fetchはネットワークにそのまま委譲する(キャッシュ書き換え・オフライン化はしない)。
self.addEventListener("fetch", function (event) {
  event.respondWith(fetch(event.request));
});
