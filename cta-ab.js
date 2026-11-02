// 來源歸因＋LIFF A/B 分流（2026-11-02 拍板）。各頁 <head> 以同步 <script src="cta-ab.js"> 載入。
//
// 1) 來源歸因：Google Ads 點擊（gclid/gad_source/gbraid/wbraid）進站時，把 sessionStorage src 設為 gads；
//    站內換頁後仍維持。其餘訪客（src 非 gads）行為完全不變：CTA 維持官網通用連結 vX3Iv8U。
// 2) gclid：落地時從網址抓下來存 sessionStorage gclid（與 src 同一處）。每次廣告落地都會覆寫；
//    該次落地沒有 gclid（只有 gbraid/wbraid/gad_source）就清掉，避免帶到舊的 gclid。
// 3) A/B：只對 src=gads 分組。第一次隨機 50/50，組別存 localStorage cta_arm；
//    localStorage 不能用就退回 sessionStorage，都不能用就固定 A 組。
//    A 組：https://lin.ee/waihMSZ（原廣告管道連結）
//    B 組：https://liff.line.me/2012196728-wk7eK1UO?src=gads&arm=b&gclid=<gclid>（無 gclid 時省略 gclid 參數）
// 4) debug：網址加 ?arm=a 或 ?arm=b 可強制分組（只對 src=gads 生效，並寫回儲存，換頁維持）。
// 5) 供各頁 GA4 事件取用：window.thCta = { src: 'gads' | 'web', arm: 'a' | 'b' | 'none' }。
(function () {
  var ADS_A_URL = 'https://lin.ee/waihMSZ';
  var LIFF_BASE = 'https://liff.line.me/2012196728-wk7eK1UO';
  var info = { src: 'web', arm: 'none' };
  window.thCta = info;

  function store(kind) {
    try { return window[kind]; } catch (e) { return null; }
  }
  function get(kind, key) {
    try { var s = store(kind); return s ? s.getItem(key) : null; } catch (e) { return null; }
  }
  function set(kind, key, val) {
    try { var s = store(kind); if (!s) return false; s.setItem(key, val); return s.getItem(key) === val; } catch (e) { return false; }
  }
  function param(q, name) {
    var m = new RegExp('[?&]' + name + '=([^&#]*)').exec(q);
    if (!m) return null;
    try { return decodeURIComponent(m[1].replace(/\+/g, ' ')); } catch (e) { return m[1]; }
  }

  var q = location.search;
  try {
    if (/[?&](gclid|gad_source|gbraid|wbraid)=/.test(q)) {
      sessionStorage.setItem('src', 'gads');
      var g = param(q, 'gclid');
      if (g) sessionStorage.setItem('gclid', g); else sessionStorage.removeItem('gclid');
    }
    if (sessionStorage.getItem('src') !== 'gads') return;
  } catch (err) { return; }

  info.src = 'gads';

  // 分組：debug 參數 > 已存組別 > 隨機
  var forced = (param(q, 'arm') || '').toLowerCase();
  var arm = (forced === 'a' || forced === 'b') ? forced : null;
  if (!arm) {
    var saved = get('localStorage', 'cta_arm') || get('sessionStorage', 'cta_arm');
    if (saved === 'a' || saved === 'b') arm = saved;
  }
  if (!arm) arm = Math.random() < 0.5 ? 'a' : 'b';
  if (!set('localStorage', 'cta_arm', arm) && !set('sessionStorage', 'cta_arm', arm)) {
    arm = 'a'; // 兩種儲存都不能用：記不住組別，固定 A 組，避免每頁換組
  }
  info.arm = arm;

  var target = ADS_A_URL;
  if (arm === 'b') {
    var gclid = null;
    try { gclid = sessionStorage.getItem('gclid'); } catch (e) {}
    target = LIFF_BASE + '?src=gads&arm=b' + (gclid ? '&gclid=' + encodeURIComponent(gclid) : '');
  }

  var fix = function () {
    var links = document.querySelectorAll('a[href*="lin.ee/vX3Iv8U"]');
    for (var i = 0; i < links.length; i++) links[i].href = target;
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fix); else fix();
})();
