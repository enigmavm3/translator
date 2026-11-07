#!/usr/bin/env python3
"""翻譯小幫手官網 SEO 頁自動檢查（只用標準函式庫）。

用法（在 repo 根目錄執行）：
  python _seo/check.py guide-xxx.html            # 檢查一頁（新頁發布前必跑，全部 PASS 才能 push）
  python _seo/check.py guide-xxx.html --guard    # 另外檢查 git 工作樹：只動了允許的檔案
  python _seo/check.py --sitemap-only            # 只檢查 sitemap.xml
  python _seo/check.py a.html b.html --legacy    # 用來掃既有頁：只回報，不要求 Article/FAQ 等新頁規格
  加 --json 輸出機器可讀結果。

結束碼：0＝全部通過；1＝有 FAIL；2＝用法錯誤。WARN 不擋發布，但要在 log 記下。
規則來源：_seo/PLAYBOOK.md「文案紅線」與「自動檢查清單」。改規則時兩邊一起改。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://triplehai.com/translator/"
CTA = "https://lin.ee/vX3Iv8U"
GA4 = "G-Z9PB2VHZMN"
AW_LISTENER = "AW-18387420345/MrKQCIS7g-YcELmJ579E"
MIN_CJK = 1200
FAQ_MIN, FAQ_MAX = 3, 5
FORBIDDEN_FILES = {"index.html", "cta-ab.js", "pricing.html", "privacy.html", "terms.html"}
MAX_TOUCHED_EXISTING = 3

# ---------------------------------------------------------------- 紅線規則
# (名稱, regex, 說明)；比對對象＝主內容可見文字＋meta＋JSON-LD（不含頁首頁尾）。
NEG = r"(?<![不沒未無免])"  # 前一字不是否定詞
NEGATABLE = {"捏造見證", "訂閱自動扣款"}  # 前 4 字內有「不是／並非／不／沒有」等否定時視為否定用法，不算命中
NEG_WINDOW = re.compile(r"不是|並非|不|非|沒有|沒|無|免|未")
REDLINES: list[tuple[str, str, str]] = [
    ("價格寫月", r"(NT\$\s?[\d,]+|[\d,]+\s*元)\s*[/／]\s*(每\s*)?月|包月|每月\s*NT\$|[/／]\s*月\b", "價格一律寫「/30 天」"),
    ("年繳說法", r"省\s*[2兩二]\s*個月|10\s*個月價", "年繳只能寫「83 折」"),
    ("訂閱自動扣款", NEG + r"(自動扣款|自動續約|自動續訂|定期定額|訂閱制)", "不可寫自動扣款／訂閱制（「不自動扣款」可以）"),
    ("三年經驗", r"三年.{0,8}(bot|機器人|翻譯)|(bot|機器人|翻譯).{0,8}三年", "不可宣稱做 bot 三年"),
    ("語言數量誇大", r"(數十|幾十|上百|一百多|百多|近百|\d{2,3}\s*[多餘+]?\s*)種\s*語|\d{2,3}\s*[多餘+]?\s*國\s*語", "只寫主力六語＋「也能翻日文、韓文等」"),
    ("絕對用語", r"最好|唯一|最佳|最強|最便宜|第一名|No\.?\s?1|最高品質|最準", "不寫最好／唯一／最佳等"),
    ("對手名稱", r"T2GO|Echonora|JFETEK|傑飛特|捷飛特|Ligo|轉譯站|翻譯麻糬|BoBi|CareLog|萬語通|譯靈|Transform", "不點名、不貶低對手"),
    ("捏造見證", r"真實案例|真實故事|用戶見證|使用者見證|好評如潮|屢獲|五星好評|準確率|滿意度", "不捏造見證或數據"),
    ("隱私細節", r"不儲存|即捨棄|自動刪除|自動清除|資料保存|加密|不會被記錄|不用於\s*AI\s*訓練", "不寫隱私細節"),
    ("技術細節", r"(?-i:(?<!Chat)GPT|API|LLM)|Gemini|Claude|OpenAI|大型語言模型|Whisper|Railway|webhook|資料庫", "只寫 capability 與 value，不寫技術細節（提到 ChatGPT 當作使用者的替代做法可以）"),
    ("禁用稱呼", r"外籍新娘|外勞仔|菲傭仔", "不用貶抑稱呼"),
]
MEDICAL = r"用藥|吃藥|藥袋|藥物|劑量|醫生|醫師|就醫|看診|回診|血壓|血糖|症狀|發燒|失智|診斷|住院"
LEGAL = r"法規|罰鍰|罰款|勞動部|就業服務法|管理辦法|第\s*\d+\s*條|1955|勞基法|勞動基準法|主管機關"
DATE_RE = r"20\d\d\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}"


# ---------------------------------------------------------------- HTML 解析
class Page(HTMLParser):
    SKIP = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.skip = 0
        self.chrome = 0  # header/footer 深度
        self.text: list[str] = []      # 主內容可見文字
        self.all_text: list[str] = []  # 含頁首頁尾
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.title = ""
        self._in_title = False
        self.h1 = 0
        self.metas: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.ldjson: list[str] = []
        self._ld = False
        self._ld_buf: list[str] = []
        self.scripts_src: list[str] = []
        self.inline_js: list[str] = []
        self._js = False
        self.html_lang = ""
        self.faq_h3: list[str] = []
        self._faq_depth = 0
        self._in_h3 = False
        self._h3_buf: list[str] = []
        self.demo_chats = 0
        self.demo_labels: list[str] = []
        self._demo_label = False
        self._demo_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.html_lang = a.get("lang", "")
        if a.get("id"):
            self.ids.add(a["id"])
        if a.get("name") and tag == "a":
            self.ids.add(a["name"])
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self.h1 += 1
        if tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.metas[key] = a.get("content", "")
        if tag == "link" and a.get("rel"):
            self.links[a["rel"]] = a.get("href", "")
        if tag == "script":
            if a.get("type") == "application/ld+json":
                self._ld, self._ld_buf = True, []
            elif a.get("src"):
                self.scripts_src.append(a["src"])
            else:
                self._js = True
        if tag in self.SKIP:
            self.skip += 1
        if tag in ("header", "footer"):
            self.chrome += 1
        cls = a.get("class", "").split()
        if "faq-item" in cls:
            self._faq_depth = 1
        elif self._faq_depth and tag == "div":
            self._faq_depth += 1
        if tag == "h3" and self._faq_depth:
            self._in_h3, self._h3_buf = True, []
        if "demo-chat" in cls:
            self.demo_chats += 1
        if "demo-label" in cls:
            self._demo_label, self._demo_buf = True, []
        if tag not in ("br", "img", "meta", "link", "input", "hr"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script":
            if self._ld:
                self.ldjson.append("".join(self._ld_buf))
                self._ld = False
            self._js = False
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        if tag in ("header", "footer"):
            self.chrome = max(0, self.chrome - 1)
        if tag == "h3" and self._in_h3:
            self.faq_h3.append("".join(self._h3_buf).strip())
            self._in_h3 = False
        if tag == "div" and self._faq_depth:
            self._faq_depth -= 1
        if tag == "div" and self._demo_label:
            self.demo_labels.append("".join(self._demo_buf))
            self._demo_label = False
        if self.stack and tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._ld:
            self._ld_buf.append(data)
            return
        if self._js:
            self.inline_js.append(data)
        if self.skip:
            return
        self.all_text.append(data)
        if not self.chrome:
            self.text.append(data)
        if self._in_h3:
            self._h3_buf.append(data)
        if self._demo_label:
            self._demo_buf.append(data)


def parse(path: Path) -> tuple[Page, str]:
    raw = path.read_text("utf-8")
    p = Page()
    p.feed(raw)
    return p, raw


def cjk_count(text: str) -> int:
    return len(re.findall(r"[㐀-䶿一-鿿豈-﫿]", text))


def norm_title(t: str) -> str:
    t = re.sub(r"\s+", "", t)
    return re.sub(r"[｜|·・]?翻譯小幫手.*$", "", t) or t


# ---------------------------------------------------------------- 結果收集
class Report:
    def __init__(self, name: str) -> None:
        self.name = name
        self.items: list[tuple[str, str, str]] = []  # (level, check, detail)

    def ok(self, check, detail=""):
        self.items.append(("PASS", check, detail))

    def fail(self, check, detail):
        self.items.append(("FAIL", check, detail))

    def warn(self, check, detail):
        self.items.append(("WARN", check, detail))

    @property
    def failed(self) -> bool:
        return any(lv == "FAIL" for lv, _, _ in self.items)


# ---------------------------------------------------------------- 個別檢查
def check_redlines(r: Report, p: Page) -> None:
    body = " ".join(p.text)
    meta = " ".join([p.title, p.metas.get("description", ""), p.metas.get("og:description", "")])
    ld = " ".join(p.ldjson)
    corpus = re.sub(r"\s+", " ", " ".join([body, meta, ld]))
    hits = 0
    for name, pattern, why in REDLINES:
        found = sorted({m.group(0) for m in re.finditer(pattern, corpus, flags=re.I)
                        if not (name in NEGATABLE and NEG_WINDOW.search(corpus[max(0, m.start() - 4): m.start()]))})
        if found:
            hits += 1
            ctx = []
            for f in found[:3]:
                i = corpus.find(f)
                ctx.append(corpus[max(0, i - 12): i + len(f) + 12].strip())
            r.fail(f"紅線：{name}", f"{why}；命中 {found[:5]}；上下文 {ctx}")
    for m in re.finditer(r"重置|重新計算|歸零", corpus):
        before = corpus[max(0, m.start() - 12): m.start()]
        if not re.search(r"不會|不再|不|沒有|無法", before):
            hits += 1
            r.fail("紅線：額度重置承諾", f"不承諾任何額度重置（只能寫「不會重置」）；上下文 {corpus[max(0, m.start() - 12): m.end() + 8]!r}")
            break
    if "年繳" in corpus and not re.search(r"83\s*折", corpus):
        hits += 1
        r.fail("紅線：年繳說法", "提到年繳就要寫「83 折」")
    if re.search(r"NT\$\s?(299|499|1,?499)", corpus) and "30 天" not in corpus and "30天" not in corpus:
        hits += 1
        r.fail("紅線：價格寫月", "有寫價格但全頁沒有「30 天」")
    if re.search(MEDICAL, corpus) and "以醫護指示為準" not in corpus:
        hits += 1
        r.fail("紅線：醫療聲明", "頁面提到用藥／就醫等醫療內容，必須有「以醫護指示為準」")
    if re.search(LEGAL, corpus):
        if "資料來源" not in corpus or not re.search(r"查證", corpus) or not re.search(DATE_RE, corpus):
            hits += 1
            r.fail("紅線：法規來源", "頁面提到法規，必須有「資料來源」＋「查證日期 YYYY-MM-DD」")
    if p.demo_chats:
        labelled = sum(1 for lab in p.demo_labels if "示範" in lab)
        if labelled < p.demo_chats:
            hits += 1
            r.fail("紅線：示範標示", f"{p.demo_chats} 個 demo-chat 只有 {labelled} 個有「示範」標籤")
    if "{{" in p.title + body + ld or "}}" in body:
        hits += 1
        r.fail("模板殘留", "還有 {{…}} 佔位沒填")
    monthly = sorted({m.group(0) for m in re.finditer(r"(?<!每)月費(?!用)|(?<!按)月繳(?!納)", corpus)})
    if monthly:
        r.warn("月費字樣", f"出現 {monthly}：若是在講翻譯小幫手的價格就違反「/30 天」紅線，必須改；"
                         "講就業安定費、仲介服務費等外部費用可保留")
    pct = re.findall(r"\d+(?:\.\d+)?\s*%", body)
    if pct:
        r.warn("數據引用", f"頁面有百分比 {pct[:5]}：確認每個都有來源，沒有就刪")
    if not hits:
        r.ok("紅線字 grep")


def check_head(r: Report, p: Page, raw: str, path: Path, legacy: bool) -> None:
    url = BASE + path.name
    problems = []
    if p.html_lang != "zh-TW":
        problems.append(f"html lang={p.html_lang!r}")
    if not p.title.strip():
        problems.append("沒有 <title>")
    if p.h1 != 1:
        problems.append(f"h1 數量 {p.h1}（應為 1）")
    if p.links.get("canonical") != url:
        problems.append(f"canonical={p.links.get('canonical')!r}，應為 {url}")
    if p.metas.get("og:url") != url:
        problems.append(f"og:url={p.metas.get('og:url')!r}")
    desc = p.metas.get("description", "")
    if not (40 <= len(desc) <= 160):
        problems.append(f"meta description 長度 {len(desc)}（建議 40–160）")
    for k in ("og:title", "og:description", "og:image", "twitter:card"):
        if not p.metas.get(k):
            problems.append(f"缺 {k}")
    if "noindex" in p.metas.get("robots", ""):
        problems.append("有 noindex")
    if GA4 not in raw:
        problems.append("缺 GA4")
    if AW_LISTENER not in raw:
        problems.append("缺 Google Ads 轉換監聽器")
    if "cta-ab.js" not in p.scripts_src:
        problems.append("缺 cta-ab.js")
    if problems:
        (r.warn if legacy else r.fail)("head／meta", "；".join(problems))
    else:
        r.ok("head／meta", url)


def check_jsonld(r: Report, p: Page, legacy: bool) -> None:
    types: dict[str, dict] = {}
    for i, block in enumerate(p.ldjson, 1):
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            r.fail("JSON-LD 解析", f"第 {i} 段無法解析：{e}")
            return
        for node in data if isinstance(data, list) else [data]:
            t = node.get("@type")
            if isinstance(t, list):
                t = t[0]
            types[t] = node
    need = ("Article", "FAQPage", "BreadcrumbList")
    missing = [t for t in need if t not in types]
    if missing:
        (r.warn if legacy else r.fail)("JSON-LD 類型", f"缺 {missing}（現有 {sorted(types)}）")
        if legacy:
            r.ok("JSON-LD 解析", f"{len(p.ldjson)} 段")
            return
    else:
        r.ok("JSON-LD 解析", f"{len(p.ldjson)} 段：{', '.join(sorted(types))}")
    if "FAQPage" in types:
        qs = types["FAQPage"].get("mainEntity", [])
        names = [q.get("name", "").strip() for q in qs]
        if not (FAQ_MIN <= len(names) <= FAQ_MAX):
            (r.warn if legacy else r.fail)("FAQ 題數", f"{len(names)} 題（應 {FAQ_MIN}–{FAQ_MAX}）")
        visible = {re.sub(r"\s+", "", h) for h in p.faq_h3}
        notshown = [n for n in names if re.sub(r"\s+", "", n) not in visible]
        if notshown:
            (r.warn if legacy else r.fail)("FAQ 一致性", f"JSON-LD 題目在頁面 .faq-item h3 找不到：{notshown}")
        elif FAQ_MIN <= len(names) <= FAQ_MAX:
            r.ok("FAQ", f"{len(names)} 題，與頁面一致")
    if "Article" in types and not legacy:
        art = types["Article"]
        if art.get("headline", "").strip() == "":
            r.fail("Article", "headline 空白")
        if not re.fullmatch(r"20\d\d-\d\d-\d\d", str(art.get("datePublished", ""))):
            r.fail("Article", f"datePublished 格式不對：{art.get('datePublished')!r}")


def local_target(href: str, page: Path) -> tuple[Path | None, str]:
    """把站內連結轉成本機檔案；不是本站 translator 頁就回 (None, '')。"""
    if href.startswith(("mailto:", "tel:", "javascript:")):
        return None, ""
    u = urlparse(href)
    frag = u.fragment
    if u.scheme in ("http", "https") or href.startswith("//"):
        full = href if u.scheme else "https:" + href
        if not full.startswith(BASE) and full.rstrip("/") + "/" != BASE:
            return None, ""
        rel = full[len(BASE):].split("#")[0].split("?")[0]
    else:
        rel = u.path
    if rel in ("", "./", "."):
        if not u.path and not u.scheme and frag:
            return page, frag
        rel = "index.html"
    if rel.endswith("/"):
        rel += "index.html"
    return (page.parent / rel).resolve(), frag


def check_links(r: Report, p: Page, page: Path) -> None:
    bad = []
    checked = 0
    cache: dict[Path, set[str]] = {page.resolve(): p.ids}
    for href in p.hrefs:
        target, frag = local_target(href, page)
        if target is None:
            continue
        checked += 1
        if not target.exists():
            bad.append(f"{href}（檔案不存在）")
            continue
        if frag:
            if target not in cache:
                if target.suffix == ".html":
                    cache[target] = parse(target)[0].ids
                else:
                    cache[target] = set()
            if frag not in cache[target]:
                bad.append(f"{href}（錨點 #{frag} 不存在）")
    if bad:
        r.fail("站內連結與錨點", "；".join(bad))
    else:
        r.ok("站內連結與錨點", f"{checked} 個站內連結")
    ext = [h for h in p.hrefs if h.startswith("https://triplehai.com/") and not h.startswith(BASE)]
    if ext:
        r.warn("跨站連結", f"{sorted(set(ext))} 不在本 repo，未檢查（love／travel 站請人工確認存在）")


def check_wordcount(r: Report, p: Page, legacy: bool) -> None:
    n = cjk_count(" ".join(p.text))
    if n >= MIN_CJK:
        r.ok("字數", f"主內容中文字 {n}（門檻 {MIN_CJK}）")
    else:
        (r.warn if legacy else r.fail)("字數", f"主內容中文字 {n}，未達 {MIN_CJK}")


def check_cta(r: Report, p: Page, legacy: bool) -> None:
    lin = [h for h in p.hrefs if "lin.ee" in h]
    ours = [h for h in lin if h.rstrip("/") == CTA]
    others = sorted({h for h in lin if h.rstrip("/") != CTA})
    if others:
        (r.warn if legacy else r.fail)("CTA 連結", f"出現其他 lin.ee 連結 {others}，官網只能用 {CTA}")
    if len(ours) >= 2:
        r.ok("CTA 連結", f"{CTA} × {len(ours)}")
    else:
        (r.warn if legacy else r.fail)("CTA 連結", f"{CTA} 只有 {len(ours)} 個（至少 2 個）")


def all_titles(exclude: Path) -> dict[str, str]:
    out = {}
    for f in sorted(ROOT.glob("*.html")):
        if f.resolve() == exclude.resolve():
            continue
        m = re.search(r"<title>(.*?)</title>", f.read_text("utf-8"), flags=re.S)
        if m:
            out[f.name] = m.group(1).strip()
    return out


def check_title_dup(r: Report, p: Page, page: Path) -> None:
    mine = norm_title(p.title)
    worst = (0.0, "", "")
    for name, t in all_titles(page).items():
        ratio = difflib.SequenceMatcher(None, mine, norm_title(t)).ratio()
        if ratio > worst[0]:
            worst = (ratio, name, t)
    ratio, name, t = worst
    if ratio >= 0.92:
        r.fail("標題不重複", f"與 {name} 標題相同或幾乎相同（{ratio:.2f}）：{t}（改寫標題，或改成「更新既有頁」）")
    elif ratio >= 0.75:
        r.warn("標題不重複", f"與 {name} 相似度 {ratio:.2f}：{t}——確認兩頁搜尋意圖不同（例如不同語言的句型頁），否則改寫")
    else:
        r.ok("標題不重複", f"最相近 {name} {ratio:.2f}")


def check_sitemap(r: Report, page: Path | None = None) -> None:
    sm = ROOT / "sitemap.xml"
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    try:
        tree = ET.parse(sm)
    except ET.ParseError as e:
        r.fail("sitemap 合法", f"XML 解析失敗：{e}")
        return
    root = tree.getroot()
    if root.tag != ns + "urlset":
        r.fail("sitemap 合法", f"根節點 {root.tag}，應為 urlset（sitemaps 0.9 namespace）")
        return
    problems, locs = [], []
    for url in root.findall(ns + "url"):
        loc = (url.findtext(ns + "loc") or "").strip()
        lastmod = (url.findtext(ns + "lastmod") or "").strip()
        locs.append(loc)
        if not loc.startswith(BASE):
            problems.append(f"{loc} 不在 {BASE}")
            continue
        rel = loc[len(BASE):] or "index.html"
        if not (ROOT / rel).exists():
            problems.append(f"{loc} 對應的檔案不存在")
        if lastmod and not re.fullmatch(r"20\d\d-\d\d-\d\d", lastmod):
            problems.append(f"{loc} lastmod 格式 {lastmod!r}")
        if rel in FORBIDDEN_FILES - {"index.html", "pricing.html", "privacy.html", "terms.html"}:
            problems.append(f"{loc} 不應出現在 sitemap")
    dups = sorted({x for x in locs if locs.count(x) > 1})
    if dups:
        problems.append(f"重複網址 {dups}")
    if page is not None:
        want = BASE + page.name
        if want not in locs:
            problems.append(f"新頁 {want} 沒有加進 sitemap")
        llms = (ROOT / "llms.txt").read_text("utf-8")
        if want not in llms:
            problems.append(f"新頁 {want} 沒有加進 llms.txt")
    if problems:
        r.fail("sitemap 合法", "；".join(problems))
    else:
        r.ok("sitemap 合法", f"{len(locs)} 個網址")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout


def check_guard(r: Report, page: Path) -> None:
    """工作樹只能有：新頁、sitemap.xml、llms.txt、_seo/**、最多 3 個既有頁的內連（只增不刪）。"""
    if (ROOT / ".nojekyll").exists():
        r.fail("防呆", ".nojekyll 存在：_seo/ 會被公開，先刪掉 .nojekyll")
    status = git("status", "--porcelain", "--untracked-files=all").splitlines()
    new_page = page.name
    problems, touched_existing = [], []
    for line in status:
        code, name = line[:2], line[3:].strip().strip('"')
        if " -> " in name:
            problems.append(f"不可改名：{name}")
            continue
        if name.startswith("_seo/"):
            continue
        if name in FORBIDDEN_FILES:
            problems.append(f"禁止修改 {name}")
            continue
        if name == new_page:
            if "D" in code:
                problems.append(f"{name} 被刪除")
            continue
        if name in ("sitemap.xml", "llms.txt") or (name.endswith(".html") and "?" not in code):
            if "D" in code:
                problems.append(f"不可刪除 {name}")
                continue
            if name.endswith(".html"):
                touched_existing.append(name)
            num = git("diff", "HEAD", "--numstat", "--", name).split()
            if num and num[1] != "0":
                problems.append(f"{name} 有刪除行（{num[1]} 行）：既有檔只能新增，不可改寫")
            if name.endswith(".html"):
                added = [ln for ln in git("diff", "HEAD", "-U0", "--", name).splitlines()
                         if ln.startswith("+") and not ln.startswith("+++")]
                if not added or not all(new_page in ln for ln in added):
                    problems.append(f"{name} 新增的每一行都必須是指向 {new_page} 的內連")
            continue
        problems.append(f"不允許的變動：{code.strip()} {name}")
    if len(touched_existing) > MAX_TOUCHED_EXISTING:
        problems.append(f"動了 {len(touched_existing)} 個既有頁（上限 {MAX_TOUCHED_EXISTING}）：{touched_existing}")
    new_html = [ln[3:].strip() for ln in status if ln.startswith("??") and ln[3:].strip().endswith(".html")
                and not ln[3:].strip().startswith("_seo/")]
    if len(new_html) > 1:
        problems.append(f"一次只能發 1 頁，工作樹有 {new_html}")
    if problems:
        r.fail("防呆（git 工作樹）", "；".join(problems))
    else:
        r.ok("防呆（git 工作樹）", f"既有頁內連 {len(touched_existing)} 個：{touched_existing}")


# ---------------------------------------------------------------- 主程式
def check_page(path: Path, legacy: bool, guard: bool) -> Report:
    r = Report(path.name)
    if not path.exists():
        r.fail("檔案", f"{path} 不存在")
        return r
    if path.resolve().parent != ROOT.resolve():
        r.fail("檔案", "新頁必須放在 repo 根目錄（與其他 guide 頁同層）")
    if path.name in FORBIDDEN_FILES:
        r.fail("檔案", f"{path.name} 是禁止修改的頁面")
    p, raw = parse(path)
    check_redlines(r, p)
    check_head(r, p, raw, path, legacy)
    check_jsonld(r, p, legacy)
    check_links(r, p, path)
    check_wordcount(r, p, legacy)
    check_cta(r, p, legacy)
    check_title_dup(r, p, path)
    if not legacy:
        check_sitemap(r, path)
    if guard:
        check_guard(r, path)
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="翻譯小幫手 SEO 頁自動檢查")
    ap.add_argument("pages", nargs="*", help="要檢查的 html（相對 repo 根目錄或絕對路徑）")
    ap.add_argument("--legacy", action="store_true", help="既有頁模式：新頁規格只給 WARN，不檢查 sitemap 收錄")
    ap.add_argument("--guard", action="store_true", help="另外檢查 git 工作樹的變動範圍")
    ap.add_argument("--sitemap-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8")
    reports: list[Report] = []
    if args.sitemap_only:
        r = Report("sitemap.xml")
        check_sitemap(r)
        reports.append(r)
    elif not args.pages:
        ap.print_usage()
        return 2
    for name in args.pages:
        path = Path(name)
        if not path.is_absolute():
            path = (Path.cwd() / path) if (Path.cwd() / path).exists() else ROOT / path
        reports.append(check_page(path, args.legacy, args.guard))
    if args.json:
        print(json.dumps([{"page": r.name, "pass": not r.failed,
                           "items": [{"level": lv, "check": c, "detail": d} for lv, c, d in r.items]}
                          for r in reports], ensure_ascii=False, indent=1))
    else:
        for r in reports:
            print(f"== {r.name} ==")
            for lv, c, d in r.items:
                print(f"  [{lv}] {c}" + (f"：{d}" if d else ""))
            print(f"  → {'FAIL' if r.failed else 'PASS'}")
    return 1 if any(r.failed for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
