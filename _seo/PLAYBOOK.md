# 翻譯小幫手官網：SEO 長尾頁自動發布手冊（雲端排程 agent 用）

> 本手冊可獨立執行，不需要其他背景知識。每週一、四 10:00（台北）各執行一次，**每次只發 1 頁**。
> 網站：https://triplehai.com/translator/ ＝ repo `enigmavm3/translator` 的 `main` 分支根目錄（GitHub Pages，Jekyll legacy build）。
> **push 到 main ＝ 幾分鐘後上線**，沒有人工審核。所以檢查沒過就不能發。
> 用戶拍板（2026-11-07）：通過自動檢查就直接發布、每週 2 篇；外語句子由執行的 agent 自己做一輪母語自然度自審。

## 0. 為什麼 `_seo/` 不會被公開

repo 沒有 `.nojekyll`，GitHub Pages 會跑 Jekyll，而 Jekyll 預設不輸出底線開頭的資料夾——所以 `_seo/` 裡的佇列、手冊、log、週報都不會出現在網站上。
**絕對不要新增 `.nojekyll`**（一加，`_seo/` 就會公開）。`check.py --guard` 會擋這件事。

## 1. 檔案

| 檔案 | 用途 |
|---|---|
| `_seo/queue.json` | 主題佇列。`pages[]` 每筆有 slug、關鍵字、搜尋意圖、情境、頁型、優先序、狀態、內連目標、預計 title、為什麼有機會、備註 |
| `_seo/template.html` | 新頁模板（head 沿用 `line-translation-guide.html`：GA4、Google Ads 轉換監聽器、`cta-ab.js`、canonical、og、三段 JSON-LD；視覺同既有 guide 頁） |
| `_seo/check.py` | 自動檢查。全部 PASS 才能 push |
| `_seo/log.jsonl` | 每次執行追加一行 JSON（成功或失敗都要寫） |
| `_seo/weekly/YYYY-MM-DD.md` | 週一那次執行寫的週報 |
| `1eae4e63e5bfb9cf9ffb0e66f676f896.txt`、`.github/workflows/indexnow.yml` | IndexNow 金鑰與自動通知。**不要動** |

## 2. 不可違反（防呆）

- **一次只發 1 頁**。只能新增這一頁，外加：`sitemap.xml`（新增一筆）、`llms.txt`（新增一行）、**最多 3 個既有頁**的「延伸閱讀」區塊各加一行連結、`_seo/` 底下的檔案。
- 既有檔案**只能新增行、不能刪改任何既有行**（`dateModified`、lastmod 也不要改）。
- **絕對不能動**：`index.html`、`cta-ab.js`、`pricing.html`、`privacy.html`、`terms.html`，以及 `.github/`、IndexNow 金鑰檔、圖片。
- 不新增圖片、不新增 JS／CSS 檔；og:image 一律沿用 `images/after.png`。
- 任何一步失敗：新頁不 push。照第 6 節「失敗處理」。
- push 前一定先 `git pull --rebase`。

## 3. 每次執行的步驟

### 3-1 準備
```bash
git checkout main && git pull --rebase
git status --porcelain          # 必須乾淨；不乾淨就停下，照失敗處理（原因：工作樹不乾淨）
TODAY=$(TZ=Asia/Taipei date +%F); DOW=$(TZ=Asia/Taipei date +%u)   # DOW=1 是週一
```
同一天已經有一筆 `status=published` 的 log（`grep "\"date\": \"$TODAY\"" _seo/log.jsonl`）→ 不再發，直接結束（避免重跑多發）。

### 3-2 選題
讀 `_seo/queue.json`，取 `status == "queued"` 且 `priority` 最小的一筆。沒有 queued → 不發頁，log 記 `{"status":"empty"}`，週一照常寫週報並註明「佇列已空」。
把該筆改成 `"status": "in_progress"`（先不 commit）。

### 3-3 查證（10 分鐘內）
1. 用 WebSearch 查 `keyword.primary` 與 1–2 個 `secondary`，看第一頁現在長什麼樣。若已出現**專門回答這個問題的大站專頁**（政府、大媒體、Google 翻譯）且我方角度沒有差異 → 這題標 `skipped`（`failed_reason` 寫原因），改取下一筆，**只能換一次**。
2. 頁面有法規內容（休假、薪資明細、宿舍、健保、申訴管道等）→ 找到**主管機關原文**（勞動部、勞動力發展署、衛福部、內政部、全國法規資料庫），記下網址與今天日期當「查證日期」。找不到原文的規定**不要寫成法規**，改寫成「建議做法」。
3. 產品事實一律以 repo 內現行頁面為準：先讀 `pricing.html`、`line-translation-guide.html`、`guide-choose-line-group-translator.html`、`use-cases.html`。下面第 4 節是速查，但兩者衝突時以 repo 頁面為準。

### 3-4 寫頁
1. `cp _seo/template.html <slug>`，填完所有 `{{…}}`（`check.py` 會擋殘留）。
2. title 用佇列的 `title`（可微調，但主關鍵字要留在前段），`<title>` 結尾是「｜翻譯小幫手」；h1 只能有 1 個；meta description 70–120 字。
3. 內容規則見第 5 節。
4. 日期：`datePublished`／`dateModified`＝今天；「最後更新 YYYY 年 M 月」。
5. 「延伸閱讀」放 4–6 個連結，至少包含佇列 `internal_links` 的全部項目；只連 repo 裡存在的頁面與錨點（`use-cases.html#caregiver`、`#helper`、`#factory`、`#travel`、`#friends`；`for-factories.html#safety`、`#shift`、`#dorm`、`#contact`；`line-translation-guide.html#setup`、`#messages`、`#troubleshooting`）。可連 `https://triplehai.com/love/`、`https://triplehai.com/travel/`（不同 repo，check 只會 WARN）。

### 3-5 外語自審（每一句都要做）
對頁面上每一句外語（印尼文、越南文、泰文、菲律賓文、英文、日文）：
1. 先回譯成中文，確認意思和旁邊的中文一致，數字、時間、否定詞（「不要」「一定要」）沒有翻反。
2. 以母語者會不會這樣傳 LINE 的標準看語氣與稱謂：印尼文 Ibu／Bu、Bapak／Pak、saya；越南文 em／anh／chị／cô／bác 與句尾 ạ；泰文句尾 ครับ／ค่ะ 要和說話者性別一致；菲律賓文 po／opo；英文用簡單句。
3. 拼字與變音符號（越南文聲調、泰文字母）逐字再看一次。
4. **任何一句沒把握就刪掉**，不要硬寫；可以改成只放中文句型（使用者打中文，翻譯小幫手會翻）。句子少但正確，比多但怪好。
5. 在 log 的 `foreign_review` 記：保留幾句、刪了幾句、哪種語言最沒把握。

### 3-6 更新 sitemap、llms.txt、內連
1. `sitemap.xml`：在 `</urlset>` 前新增
   ```xml
     <url>
       <loc>https://triplehai.com/translator/<slug></loc>
       <lastmod><今天></lastmod>
       <changefreq>monthly</changefreq>
       <priority>0.7</priority>
     </url>
   ```
2. `llms.txt`：找到 `## 情境指南與教學` 段落，在段落最後新增一行 `- [<h1 或 title 主體>](https://triplehai.com/translator/<slug>)：<一句話說明>`。這個段落不存在時，在 `## 其他` 那一行**之前**新增整段（標題一行＋空行＋你的那一行＋空行）。不要改 llms.txt 其他行。
3. 內連：從下列有「延 伸 閱 讀」區塊的頁面挑**最相關的 1–3 頁**（優先佇列 `internal_links` 裡出現的頁）：
   `line-translation-guide.html`、`guide-choose-line-group-translator.html`、`phrases.html`、`phrases-vi.html`、`phrases-th.html`、`phrases-en.html`、`case-*.html`、`guide-*.html`、`tool-helper-points.html`，以及之前由本流程發布的頁面。
   在該頁 `你可能也想看</h2>` 那一行的**下一行**插入**一行**（整行，不要改到其他行）：
   ```html
   <a href="<slug>" style="display:block;padding:16px 20px;background:#ffffff;margin-bottom:8px;text-decoration:none;color:#0a0a08;font-size:18px;font-family:'Noto Sans TC', system-ui, sans-serif;border-left:4px solid #1a5c3f;transition:background 0.2s"><連結文字> →</a>
   ```
   `use-cases.html`、`for-factories.html`、`for-agencies.html` 版型不同，不要改。用 Edit 工具插入，保留原檔換行格式。

### 3-7 自動檢查（全部要過）
```bash
python3 _seo/check.py <slug> --guard
```
檢查項目：紅線字 grep、head／meta（GA4、轉換監聽器、cta-ab.js、canonical、og）、JSON-LD 能解析且有 Article／FAQPage／BreadcrumbList、FAQ 3–5 題且與頁面一致、站內連結與錨點都存在、主內容中文字 ≥1,200、`https://lin.ee/vX3Iv8U` ≥2 個且沒有其他 lin.ee、與既有頁標題不重複、sitemap 合法且已收錄新頁、llms.txt 已收錄、git 工作樹只動了允許的檔案。
- 有 FAIL：照訊息修正後重跑，**最多修 3 輪**。3 輪後仍 FAIL → 失敗處理。
- WARN 不擋發布，但要逐條判斷，並寫進 log 的 `warnings`。
- **不准為了過檢查去改 check.py**，也不准用 `--legacy`。

### 3-8 寫 log、更新佇列、commit、push
1. 佇列該筆改 `"status": "published"`、`"published_at": "<今天>"`。
2. `_seo/log.jsonl` 追加一行（單行 JSON，UTF-8，不轉義中文）：
   ```json
   {"date": "2026-11-09", "weekday": "mon", "slug": "guide-xxx.html", "status": "published", "title": "…", "url": "https://triplehai.com/translator/guide-xxx.html", "keyword": "…", "scenario": "…", "cjk_chars": 2100, "linked_from": ["line-translation-guide.html"], "sources": [{"name": "…", "url": "…", "checked_on": "2026-11-09"}], "foreign_review": {"kept": 18, "removed": 2, "least_confident": "越南文"}, "warnings": [], "notes": ""}
   ```
3. commit（只 add 這些檔）：
   ```bash
   git add <slug> sitemap.xml llms.txt _seo/queue.json _seo/log.jsonl <內連的既有頁…> [_seo/weekly/<今天>.md]
   git status --porcelain     # 確認沒有其他變動
   git commit -m "SEO 長尾頁：新增「<title 主體>」（<slug>）"
   git pull --rebase && python3 _seo/check.py <slug> && git push origin main
   ```
4. push 被拒 → `git pull --rebase` 再試一次；rebase 衝突 → `git rebase --abort`，不 push，在最後回報說明。
5. IndexNow：雲端環境連不到 api.indexnow.org 與 triplehai.com，**不要嘗試**。push 後由 GitHub Actions `.github/workflows/indexnow.yml` 自動送出（只送 sitemap 裡有的網址）。

### 3-9 週一加做：週報
`DOW=1` 時，在 commit 前寫 `_seo/weekly/<今天>.md`，內容只根據 `_seo/log.jsonl` 與 `_seo/queue.json`：
```markdown
# SEO 長尾頁週報 <今天>
- 期間：<上週一>～<昨天>
- 上週發布：N 頁
  - <title>｜<url>｜關鍵字：<keyword>｜情境：<scenario>｜中文字 <n>｜內連自 <…>
- 失敗或跳過：<slug：原因>（無則寫「無」）
- 外語自審：保留 X 句、刪除 Y 句；最沒把握：<語言>
- WARN 摘要：<…>（無則寫「無」）
- 佇列：已發布 A／24、剩 queued B 題，預計 C 週發完；下兩題：<slug>、<slug>
- 需要人處理：<例如 update_existing、產品事實待核、法規來源找不到>（無則寫「無」）
```
週報跟當天的發布同一個 commit；當天若失敗，週報跟失敗紀錄同一個 commit。

## 4. 產品事實速查（2026-11-07；與 repo 頁面衝突時以 repo 為準）

- **是什麼**：LINE 群組即時翻譯機器人。把「翻譯小幫手」加進 LINE 群組，大家各打各的母語，譯文自動出現在群組對話裡。
- **語言**：主力六語＝繁體中文、印尼語、越南語、泰語、菲律賓語（Tagalog）、英文；可寫「也能翻譯日文、韓文等語言」。**不寫總共幾種語言。**
- **用法**：加好友 → 邀請進群組 → 雙方各傳一句完整的母語訊息，語言自動認得。不用下載 App、不用註冊、不用設定；對方只要會用 LINE。LINE 社群（OpenChat）不能加機器人；貼圖、照片不翻譯。群組指令：`/stop` 暫停、`/start` 恢復、`/plan` 看方案與用量、`/lang` 改自己的語言。
- **一句中文可以同時翻成多種語言**（同群有越南、印尼、泰國籍成員時）。
- **免費**：每個群組終身共 50 則免費翻譯，**不會每日或每月重置**。
- **價格（盡量少寫，寫了就要照這個格式）**：基本 NT$299／30 天、進階 NT$499／30 天、商用 NT$1,499／30 天；單次購買、不自動扣款。年繳寫「83 折」。語音翻譯：免費體驗與進階、商用方案有，基本方案沒有。詳細一律連 `pricing.html#pricing`。
- **多群組／工廠／仲介**：一律寫「多群組使用歡迎來信 contact@triplehai.com 洽詢」，不寫任何優惠、合作方案或報價。
- **可以講的價值**：省去複製貼上、雙方用最熟悉的語言說、重要的事寫清楚少誤會、對方敢用母語發問、針對台灣照護現場用詞（排班、量血壓、藥袋、加班費）做過調校、會參考對話前後文。
- **不講**：技術（用什麼模型、怎麼做）、隱私與資料保存細節、準確率、用戶數、任何沒有出處的數字。

## 5. 內容品質與文案紅線

### 5-1 內容
- 主內容中文字 **≥1,200**（`check.py` 只數中文字；建議 1,800–2,800）。
- 先解決搜尋者的問題，再帶產品。產品段落佔全文約兩成以內，語氣是「這樣做會比較順」，不是推銷。
- 必須有：實用步驟或清單、**可直接複製的中文訊息或句型**（`msg-box`）、FAQ 3–5 題（頁面 `.faq-item` 與 FAQPage JSON-LD 題目文字完全一致，JSON-LD 答案用純文字）。
- 至少 2 個 CTA，連結一律 `https://lin.ee/vX3Iv8U`（模板已放 2 個）。
- 示範對話用模板的 `demo-chat` 區塊，每個都要有含「示範」的 `demo-label`，下方附「以上為示範對話，實際翻譯會依對話內容略有不同。」
- 價值主張一致：capability（各打各的母語、自動互譯、不用下載設定）與 value（省時間、少誤會、雙方安心），不寫技術細節或隱私細節。

### 5-2 文案紅線（`check.py` 會 grep，但人也要守）
- 價格寫「/30 天」，**不寫「/月」「月費」「每月 NT$」**；年繳寫「83 折」，不寫「省 2 個月」。
- 不寫「自動扣款」「訂閱制」「自動續約」（「不自動扣款」可以）。
- **不承諾額度重置**（只能寫「不會重置」）。
- 不寫「做 bot 三年」、「數十種」「一百多種」語言。
- 不寫「最好」「唯一」「最佳」「最強」「最準」「第一名」；建議句改用「建議」「比較好的做法是」。
- 不點名、不貶低其他翻譯機器人或 App（可以泛稱「切到翻譯 App」「其他群組翻譯機器人」，ChatGPT／Google 翻譯當作使用者的替代做法可以提）。
- 不捏造見證、案例、數據、引言；不寫「真實案例」「用戶見證」。人物一律是示範。
- 醫療相關（用藥、就醫、血壓、症狀、失智）一律寫「**以醫護指示為準**」，緊急狀況寫打 119。
- 法規相關一律附「**資料來源**（查證日期 YYYY-MM-DD）」與原文連結，並寫「以主管機關最新公告為準」。
- 不寫隱私細節（保存幾天、刪除、加密、是否用於訓練）。
- 用「看護」「移工」「新住民」「配偶」，不用貶抑稱呼。

## 6. 失敗處理

| 情況 | 處理 |
|---|---|
| `check.py` 修 3 輪仍 FAIL | 刪掉新頁、`git checkout -- sitemap.xml llms.txt <動過的既有頁>`；佇列該筆 `status: "failed"`、`failed_reason` 寫最後一輪的 FAIL 摘要；log 追加 `status: "failed"` 並附 `fails`；只 commit `_seo/queue.json`、`_seo/log.jsonl`（週一加週報），訊息 `SEO 佇列：<slug> 檢查未過，標 failed（<一句原因>）`，push。**當次不換題重來。** |
| 查證後不值得寫（3-3） | 標 `skipped`，換下一筆（只能換一次）；兩筆都不行 → 只 commit 佇列與 log |
| 工作樹一開始就不乾淨、或 rebase 衝突 | 什麼都不 commit、不 push，在最後的回覆說明狀況（下一次執行會重試） |
| 同一天已發過 | 直接結束，不寫 log |
| 佇列已空 | log `{"date":…, "status":"empty"}`，週一照寫週報，commit `_seo/` 後 push |

`failed` 的題目不會自動重試；人看過 log 後若要重排，把 status 改回 `queued`。

## 7. 給人調整用

- 改發布順序：改 `queue.json` 的 `priority`（小的先發）。
- 暫停：在 claude.ai/code/routines 停用排程，或把所有 queued 改成 `skipped`。
- 加題：照現有欄位新增一筆 `status: "queued"`；新題要先查過 Google 台灣第一頁，填 `why_opportunity` 與 `serp_checked_on`。
- `update_existing` 是「與既有頁相近、應該改既有頁」的題目，**本流程不做**，由人或互動 session 處理。
- 改紅線或檢查規則：`check.py` 與本檔第 5 節一起改。
