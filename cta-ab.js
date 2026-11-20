// 來源歸因＋廣告流量走 LIFF（2026-11-02 A/B 上線，2026-11-20 改為全部 LIFF）。各頁 <head> 以同步 <script src="cta-ab.js"> 載入。
//
// 1) 來源歸因：Google Ads 點擊（gclid/gad_source/gbraid/wbraid）進站時，把 sessionStorage src 設為 gads；
//    站內換頁後仍維持。其餘訪客（src 非 gads）行為完全不變：CTA 維持官網通用連結 vX3Iv8U。
// 2) 點擊參數 gclid/gbraid/wbraid/cmp：廣告落地時從網址抓下來，各自存 sessionStorage 同名 key。
//    每次廣告落地都會整組覆寫；該次落地沒有的參數就清掉，避免帶到前一次落地的舊值。（2026-11-08 加 gbraid/wbraid/cmp）
// 3) 廣告流量（src=gads）的 CTA 一律換成 LIFF 連結（2026-11-20 用戶拍板：A/B 結束，全部走 LIFF；
//    11/03–11/19 加好友 A 組 225、B 組 256）。原 A 組連結 https://lin.ee/waihMSZ 不再使用。
//    https://liff.line.me/2012196728-wk7eK1UO?src=gads&arm=b[&gclid=..][&gbraid=..][&wbraid=..][&cmp=..]
//    （沒有的參數就不附加；值一律 encodeURIComponent；arm 固定 b，後端只收 a 或 b）
// 4) （已移除）原 ?arm=a|b debug 強制分組。
// 5) 供各頁 GA4 事件取用：window.thCta = { src: 'gads' | 'web', arm: 'b' | 'none' }。
(function () {
  var LIFF_BASE = 'https://liff.line.me/2012196728-wk7eK1UO';
  // 帶進 B 組 LIFF 連結的點擊參數（順序即附加順序）
  var CLICK_KEYS = ['gclid', 'gbraid', 'wbraid', 'cmp'];
  var info = { src: 'web', arm: 'none' };
  window.thCta = info;

  function param(q, name) {
    var m = new RegExp('[?&]' + name + '=([^&#]*)').exec(q);
    if (!m) return null;
    try { return decodeURIComponent(m[1].replace(/\+/g, ' ')); } catch (e) { return m[1]; }
  }

  var q = location.search;
  try {
    if (/[?&](gclid|gad_source|gbraid|wbraid)=/.test(q)) {
      sessionStorage.setItem('src', 'gads');
      for (var j = 0; j < CLICK_KEYS.length; j++) {
        var v0 = param(q, CLICK_KEYS[j]);
        if (v0) sessionStorage.setItem(CLICK_KEYS[j], v0); else sessionStorage.removeItem(CLICK_KEYS[j]);
      }
    }
    if (sessionStorage.getItem('src') !== 'gads') return;
  } catch (err) { return; }

  info.src = 'gads';

  // 2026-11-20：A/B 結束，廣告流量一律走 LIFF。arm 維持 b（後端只收 a 或 b）。
  info.arm = 'b';
  var target = LIFF_BASE + '?src=gads&arm=b';
  for (var k = 0; k < CLICK_KEYS.length; k++) {
    var v = null;
    try { v = sessionStorage.getItem(CLICK_KEYS[k]); } catch (e) {}
    if (v) target += '&' + CLICK_KEYS[k] + '=' + encodeURIComponent(v);
  }

  var fix = function () {
    var links = document.querySelectorAll('a[href*="lin.ee/vX3Iv8U"]');
    for (var i = 0; i < links.length; i++) links[i].href = target;
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fix); else fix();
})();
