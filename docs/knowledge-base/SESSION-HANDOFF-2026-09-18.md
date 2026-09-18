# SESSION-HANDOFF 2026-09-18

> 依 `AI_Development_Standard/00_Global/Project_Continuity.md` 撰寫:明確區分完成/未完成/
> 需人決定,每一項標註**驗證等級**,不把未驗證的寫成已驗證。
> 前一份:[`SESSION-HANDOFF-2026-09-10.md`](SESSION-HANDOFF-2026-09-10.md)。

## 0. 本輪的主軸

commit 範圍 `69ba5429..3a4ba8a4`(**53 個 commit**,99 檔變動 +14995 / −420),全部已推送至
`fork remaster-local`。起點是前一份交接文件的最後一個 commit。逐 commit 的技術細節在
[`98-tooling-infrastructure.md`](98-tooling-infrastructure.md) 的 2026-09-11 續六 ~ 2026-09-18 續二十二;
本文件只做總結與交接。

使用者指示,依序(每一段都是「依照你的建議自動繼續進行」型的授權):

1. 「工具缺陷請修正」→「請解決不穩定問題」:全量突變掃描留下的工具缺陷,與突變測試本身的
   不穩定(待辦 34 ~ 37)。
2. 「還有哪些需要確認?」→「可以同步進行的請同步進行」→「優化改善後會有哪些風險或者盲點?」
   →「需要新增工具進行連動優化嗎?」→「登錄表理由主要用途?」→「改成不用人工複審」:閘門的
   盲點逐一收掉,登錄表理由機器化(待辦 38 ~ 45)。
3. 「已經完整解析了嗎?」→「955 個入口沒有機器訊號的問題,需要怎麼處理比較好?」→
   「可以建立新工具加速進行嗎?」:分母修正 + dossier 四批審閱,無訊號入口主張歸零
   (待辦 46 ~ 53)。
4. 「解析程度多少了?還差哪些?」→「怎麼做才能完全解析程式碼層?」→「只有這種方法嗎?」
   →「有幾種方法?個別優缺點及所需時間多少?」→「有更快的方式嗎?」→「commit」→
   「紀錄並歸檔」:**只有問答,沒有改檔**;內容整理在 §6,等使用者選路線。

---

## 1. 驗證等級對照

| 等級 | 意義 | 本輪用量 |
|---|---|---|
| **靜態 RE** | Ghidra/Capstone 反組譯確定,未經實機 | 勘誤 79 筆、PRIM 參數個數、`0x35b78` 語意 |
| **工具自驗** | `--selftest` 通過,且突變窮舉 0 逃逸 | 全部 63 支有突變測試的工具 |
| **產物重生** | 重跑產生器與已提交檔逐位元組比對 | chapter_beats、native_argcounts、基準線 |
| **原版實機** | DOSBox-X 跑原版 EXE 實測 | 本輪**未使用**(全部離線完成) |
| **估計** | 工時、覆蓋率的推估,沒有量測 | §6 的所有時間與百分比 |

**本輪沒有任何結論依賴 remake**;`remake/` 已於 2026-09-02 移除,其證據效力亦排除。

---

## 2. 已完成(可量測的部分)

| 指標 | 起點(`69ba5429`) | 現在(`3a4ba8a4`) |
|---|---|---|
| 全量突變掃描逃逸 | 321 | **0**(321 → 90 → 0) |
| 全量窮舉檢查點(可達 / 抓到 / 逃逸) | — | **1376 / 1265 / 0**,87 分鐘(待辦 45) |
| 等價突變登錄表 | 0 | **104 筆,每筆有機器探針 + 上下文雜湊** |
| 提交前閘門 | 逐項手跑 | 一道 `verify_selftest_discrimination.py --precommit` |
| WSL 軸工具數 | 10 | 13(三支 Windows 專用工具拆出離線核心) |
| 知識庫入口位址主張(相異 obj1 位址) | 1372 | 1113(分母修正後) |
| 其中「無訊號未登記」 | 955 | **0**(有訊號 408、勘誤 71、函式內部引用 560、審過非主張 74) |
| `known_address_errata.json` | 14 筆 | **79 筆** |
| `address_claim_reviews.json`(審過非主張) | 不存在 | **74 筆** |
| PRIM 參數個數與被呼叫端本體不一致 | 未量過 | 4 筆改正(loadch 1、play_sfx 3、load_res 3、layout_units 11),23 筆一致,1 筆刻意投影(`dialog` 2/9) |
| chapter_beats `unknown` beats | 0 | 0(`0x35b78` 改名後重生一致) |

新增工具/機制(全部有 selftest 與突變探針):

- `derive_native_argcounts.py`:**第三訊號 `callee_argc`**(被呼叫端讀 `[esp+X]`/`[ebp+X]` 的
  最高位移;支援位移追蹤、無序頭 leaf、thunk、`leave`)。PRIM 的參數個數改由被呼叫端本體裁決。
- `verify_address_claim_coverage.py`:**第四訊號**(E9 JMP 目標)、**INNER 類**(落在有訊號函式
  內部的合法指令邊界,不是入口主張)、`--dossier`(EDITION/DATA/TYPO/DOC 四假說判讀資料,
  人只讀資料下結論)、`--mark-reviewed`(審過非主張登錄)、括號/半開區間排除。
- `verify_selftest_discrimination.py`:穩定鍵抽樣、`--exhaustive`、artifacts 探針、登錄表三類
  (equivalent/cosmetic/tuning)、逾時依基準縮放 + `--confirm-timeouts`、`--changed` 含 AST
  反向相依、`--check-registry`(過期 + `scope_hash`)、`--revalidate-registry`(每筆登錄的
  `NORMAL_RUN` 探針依 kind 比對 rc/stdout/files/artifacts)、`--precommit`。
- `verify_address_citations.py --diff`:位址訂正的**源頭閘門**(待辦 31)。
- `text_proximity.py`:收斂三次各自實作的「兩段文字是否相鄰」判準(待辦 33)。
- `verify_everything.py`:wsl 軸判定改為「rc≠0 或有 SKIP 卻 0 PASS 才失敗」。
- `AGENTS.md`:推送規則改為**只推 `fork remaster-local`、不得推 `origin`**;提交前 `--precommit`。

---

## 3. 抓出的既有錯誤(全部已更正,靜態 RE)

| 錯誤 | 證據 | 處置 |
|---|---|---|
| PRIM 表 4 筆參數個數錯(loadch/play_sfx/load_res/layout_units) | 被呼叫端本體讀取的最高參數位移(`callee_argc`) | 改正並重生 native_argcounts、chapter_beats |
| `DOC_OP_NAMES` 把 `0x35b78` 叫 `give_item_to_group` | 錨在 doc25 §11 的**標題**,同節緊接著修正為「spawn_group + 兩段調色盤淡入 + 全螢幕重繪」;本體 pan → spawn → delay → 兩次 palette ramp → redraw | 改名 `pan_spawn_group`,錨在結論句 |
| 955 個「無訊號入口主張」 | 770 個是函式內部引用(分母用錯量尺),184 個不在指令邊界 | INNER 類 + JMP 訊號 → 188;dossier 四批 → 0 |
| 舊版 EXE 位址殘留 65 筆 | 分段位移常數:事件 handler 區 +0x356、delay/stack-check 區 +0x358、尾段 `0x37xxx–0x4exxx` +0x350、城鎮/教會/商店家族 `0x2c000–0x31000` **−0x6985**;沒有全域常數 | 登進勘誤表,含 13 筆新版本體語意重驗 |
| 教會/商店呼叫鏈 6 筆(`0x2e341`/`0x2f0b0`/`0x2f642`/`0x2f8ea`/`0x2ffa5`/`0x2d669`) | 新版 `0x29daa`/`0x279bc` 本體的呼叫序列與 doc50 L638、doc42 L130 逐一對應,六個位移全是 −0x6985 | 補登;`0x2e341` 先前被歸 INNER,是 **INNER 已知上限的第一個實例** |
| `0x4dbfc`/`0x4e893` 的 root_cause 寫「個別誤記」 | 第二批 dossier 找到 12 筆同位移(+0x350)配對 | root_cause 改寫,位址訂正本身自始正確 |
| `verify_address_claim_coverage` 從待辦 42 起 FAIL,三個 commit 沒人跑 | doc98 續十三提到 `delay` thunk 的本體 `0x3e01d`(只由 `jmp` 抵達,三個入口訊號都看不到) | 基準線 +1,閘門清單補上 |
| `known_address_errata.json` 存在 22 天沒有任何驗證軸讀它 | 待辦 25 | 接上 `verify_address_citations` 第十一軸 |
| `disasm_le.py refs` 只走 object 1 的 fixup | 資料段參照一律回空(待辦 26) | 修正 |
| 一筆 `confidence: verified` 的錯 | `verify_address_claim_coverage` 上線第一天抓到(待辦 29) | 訂正 |

---

## 4. 我自己犯並更正的錯(通用教訓)

1. **heredoc 三次弄壞跳脫**(吃掉 `\S`、切函式終點誤刪 `AXES`、`'\n "reviews"'` 變成真換行)。
   patch 腳本一律走 Write 工具,已寫成記憶 `feedback_patch_scripts_go_through_the_write_tool`。
2. **`callee_argc` 我改壞的公式被突變窮舉抓到**:`off > 0` + ceil 在 byte 讀取案例上差 1;改回
   `off >= 4`、`off // 4`,並釘住 byte 讀取案例。綠色的控制組不證明改寫後的公式——要突變新碼
   (`feedback_green_controls_dont_prove_a_rewritten_formula`)。
3. **`--tool` 只收最後一個值**(`action="store"`)→ `append`。
4. **`load_reviews(path=REVIEWS)` 在 def 時綁定**,selftest 換路徑無效 → 呼叫時取。
5. **wsl 軸「至少 1 個 PASS」誤判三支不印 PASS 的工具** → 改「rc≠0 或有 SKIP 卻 0 PASS」。
6. **EDITION 假說一對就採,誤提率 4/100** → ≥2 對支持 + 否決名單 `DELTA_DENY`。
7. **錨點引文取了標題而非結論句**(`0x35b78`);且跨行引文找不到 → 取單行可逐字定位的後半句。
8. **閘門清單漏了一道**(`verify_address_claim_coverage`),漏跑三個 commit → 補進清單。
9. **先修分母再審清單**:955 → 188 → 0 靠的是重新分類(INNER、JMP、dossier),不是逐一反組譯
   (`feedback_fix_the_denominator_before_working_the_list`)。

---

## 5. 未完成(離線可做,有明確形狀)

| 項目 | 現況 | 下一步 |
|---|---|---|
| 勘誤 `0x2cad7` 語意 | 呼叫點證據成立(`0x25e2a call 0x26152`),但 doc50 §3.9 記的 `byte[chapter+0x526b9]` 測試在本體與一階被呼叫者都沒找到 | 往更深層找,或標為舊版結構;`still_pending` 如實保留 |
| 舊位址字面引用未逐一改寫 | 79 筆勘誤只登記、沒有改寫每個引用點;讀者靠勘誤表換算(`query_verified_address` 會提示) | 若要改寫,走 `verify_address_citations --diff` 逐檔 |
| 對白/視窗渲染器 `0x15f84` 的 9 個參數只解了 2 個(txtptr、idx) | PRIM `dialog` 刻意投影為 2 參數 | 其餘 7 個是視窗幾何與模式,新建遊戲時每個對白框都要用到 |
| 戰鬥 AI 決策細節 | doc27 §5 列 15/20 項三方一致 | 缺經驗值公式的攻守等級因子、武器命中特效 |
| 演出時序 | `0x11d40` 60 次呼叫、9-frame palette loop 有記 | 30+ 招式逐招未釘 |
| M5 驗收(無 debug hook 全程可玩) | remake 移除後唯一驗收面是原版 DOSBox-X;chapter_sweep 做過 30 章結構掃描 | 「一路玩到底」沒做過;是否還要這條驗收線需使用者定 |
| 程式碼層命名缺口 | 見 §6 | 需使用者選路線 |

`still_pending` 欄非空的 16 筆勘誤中,2026-08 的 14 筆是舊體例把「已修正完成」註記寫在該欄,
不是待辦;真正未重驗的只有 `0x2cad7`(與 `0x4e893` 的順帶註記)。

---

## 6. 需要使用者決定:程式碼層要解析到什麼程度、走哪條路

以下是 2026-09-17/18 問答的整理。**數字是專案自己的量尺;時間與覆蓋率是估計,沒有量測。**

### 6.0 實測(2026-09-18,取代下面各節的「976 個函式」與「約 110 個有名字」)

一次性量測,腳本沒有進庫(方法寫在下面,可重做)。來源:Ghidra 匯出
`FD2_ghidra_projects/FD2_disasm_full.txt` 的函式標頭、`verify_address_claim_coverage` 的位元組訊號
(Watcom 序頭、E8 CALL 目標)、以及 PRIM / `DOC_OP_NAMES` / `ail_entry_points.json` /
`verified_addresses.json` / 勘誤 `correct_address` 五張命名表。

**Ghidra 的 976 不是分母,兩個方向都錯:**

| 項目 | 數量 |
|---|---|
| Ghidra 匯出的「函式」 | 976 |
| 其中 `.image::` 位址空間的 1-byte 佔位、本體空白 | **226**(不是函式) |
| 真正落在 obj1 程式碼的 Ghidra 函式 | **750** |
| 有 Watcom 序頭或被 CALL、卻落在**任何 Ghidra 函式之外**的入口 | **317**(226 個有序頭、91 個只有 CALL) |
| 上述 317 個裡,知識庫早已主張為入口的 | 101 |
| AIL 105 個進入點裡是 Ghidra 起點的 | 只有 44(其餘多半經指標表呼叫,沒有直接 CALL) |

226 個佔位與 226 個有序頭的空隙入口**數量相同,但沒有固定位移對應**(最常見的位移只命中 5 對),
判定為巧合,未再追。

**聯集分母與命名覆蓋率:**

| 分母 | 函式數 | 機器登錄名稱 | 其中 AIL | 其中遊戲側 | 文件記載為入口(有訊號) | 無名 |
|---|---|---|---|---|---|---|
| 強分母:Ghidra 750 + 有序頭的空隙入口 + AIL | **1037** | 234 | 105 | 129 | 263 | **540** |
| 全分母:再加只有 CALL 的空隙入口 | 1123 | 234 | 105 | 129 | 263 | 626 |

- 「機器登錄名稱」= 五張命名表任一有此起點;「文件記載為入口」= claim_coverage 的有訊號集合,
  但不在命名表裡。兩者合計 **497 / 1037 = 48%**,不是先前估的「約 110 個、七成以上沒人命名」。
  差別來自兩處:先前沒算 AIL 的 105 個;也沒算文件記載過、但沒進命名表的 263 個。
- 只看 Ghidra 的 750 個:機器登錄 139、文件記載入口 187、文件只在本體內提及 141、完全無 283。
  完全無的 283 個有 **245 個在 `0x3702f`(`__STK`)之後**,共 26373 bytes;`__STK` 之前只有 **38 個**
  (5461 bytes)。283 個全部 ≤ 1024 bytes。**訂正(同日)**:初稿把 `__STK` 之後整段叫「函式庫區」,
  說過頭了 —— 那一段除了 Watcom CRT 與 AIL,也有遊戲側的低階繪圖常式(`0x4e98d`、`0x4df4c`、`0x4e390`
  都在知識庫裡有名字;`0x4xxxx` 段另有 34 個已命名或文件記載的函式)。哪些是函式庫要靠簽名比對判定,
  不能靠位址分段。
- 以位元組計(Ghidra 750 個,共 171794 bytes):完全無的只佔 **18.5%**。沒人碰過的是小函式與函式庫。

**洩漏名稱掃描:0 個新名稱。** EXE 可列印字串 2856 段,去掉操作碼雜訊後 61 個像識別字的字串:
DOS/4GW 延伸器(`D32*`、`DOS4G_*`、`DVX_*`、`LINEXE_*`、`SEGEXE_*`)、Watcom CRT(`_C_FILE_INFO`)、
音效設定鍵(`DMA_8_bit`、`IO_ADDR`),以及遊戲側唯一的 `Get_EasyMagic`(doc13 已記載,`0x18ED0`)。
AIL 的 105 個早已由 `ail_entry_points.json` 收錄。這條路沒有可收的東西。

**對 §6.3 ~ §6.6 的影響:**
- 路 0(分母清單)的第一個工作項目確定了:**不能以 Ghidra 的函式清單當骨架**,要以位元組訊號建聯集,
  Ghidra 只當其中一個來源。這也表示 976 函式反編譯檔對那 317 個空隙入口**沒有偽碼**,
  路 2(批次反編譯 + 模型摘要)得先用 headless probe 補切函式。
- 路 4(函式庫簽名比對)的候選是 `__STK` 之後那 245 個完全沒人碰過的小函式,但其中混有遊戲側的繪圖常式,
  要靠簽名而不是位址判定。`__STK` 之前完全沒人碰過的只剩 38 個。
- 洩漏名稱那半天不用做了。

### 6.0b 工具化之後的數字(`tools/function_inventory.py`,同日)

一小時量測版升級成正式工具(selftest、突變窮舉、artifacts 棘輪),產物 `docs/data/function_inventory.json`。
骨架只用位元組訊號(Watcom 序頭、直接 CALL、AIL 進入點、入口上的 `E9` thunk 目標),Ghidra 只當對照。
與 §6.0 的差別:§6.0 的聯集分母把 Ghidra 起點也算進去;工具不算(沒有任何位元組訊號的 Ghidra 起點 29 個,
多半是 1–8 bytes 的殘段與 `_entry`),並把「只被 CALL 一次」的降為 `weak`(E8 位元組掃描會命中資料)。

| 分母 | 入口數 | 有名稱 | 文件記載為入口 | 無名 | 有名稱或記載 |
|---|---|---|---|---|---|
| `strong`(序頭 / AIL / thunk 目標 / 被 CALL ≥2 次) | **858** | 231 | 250 | **377** | 56% |
| 全部(含只被 CALL 一次的 `weak` 244 個) | 1102 | 233 | 263 | 606 | 45% |

與 Ghidra 750 個真函式對照:共有 721;只有 Ghidra 29;只有本清單 381(落在某個 Ghidra 函式內 11、
落在空隙 370,其中 `strong` 295)。每個入口附機械事實:直接呼叫端數、`span_upper`(大小上界)、
`argc`(被呼叫端本體讀到第幾個參數;1102 個裡 969 個判得出來)、`callees`、`globals`。
`--unnamed` 依呼叫端數列出無名的 `strong` 入口,並標出它呼叫了哪些已命名函式 —— 這是結構性自動命名
(§6.5 第 2 項)的輸入。

**順帶修掉一個真缺陷**:`derive_native_argcounts.callee_argc` 遇到 `sub esp, eax`(暫存器調整 ESP)會
`ValueError` 崩潰。先前只餵過章節 handler 可達的幾十個目標所以沒撞到,套到全部 1102 個入口才出現。
改成回 None(位移已不可知,不是 0),並補三個成對案例。

### 6.0c 結構性自動命名的可行性(唯讀分析,同日)

用 `function_inventory.json` 加命名表,把 377 個無名 `strong` 入口依結構分桶(一次性腳本,未進庫):

| 桶 | 數量 | 機械命名 |
|---|---|---|
| 被呼叫者全部已命名、且 ≤ 256 bytes | 57 | 可以,例如 `wrapper(sprite_walk_on, play_sfx)` |
| 入口即 `jmp` | 4 | 可以,`thunk→目標` |
| 無被呼叫者、≤ 64 bytes | 63 | 要另寫樣板辨識(讀表、設旗標) |
| 部分被呼叫者已命名 | 96 | 半自動,名字當線索 |
| 被呼叫者全部無名 | 129 | 不行 |
| 其他(大 leaf 22、只從 AIL 可達 5、無呼叫端 1) | 28 | 個案 |

- 名稱傳播(被呼叫者全部已知就能機械描述)的不動點:逐輪新增 133、15、6、1,**上限 155 / 377 = 41%**;
  嚴格只算 wrapper 與 thunk 是 61 個(16%)。§6.5 估的 20–30% 落在這個範圍內。
- `__STK` 之前的無名 `strong` 入口 217 個,其中 54 個是可機械命名的 wrapper。
- 從 main `0x25bf4` 沿直接 CALL 可達 646 個入口;從 AIL 105 個進入點可達 357 個。

### 6.0d 結構性自動命名做成工具(`function_inventory.py --structural`,同日)

產物 `docs/data/function_structural_names.json`,**152 個**,每筆標 `kind`。這些是**結構描述,不是語意**
(`wrapper(load_res)` 說的是「它只呼叫 load_res」),不得當成 verified 引用。

| kind | 數量 | 定義 |
|---|---|---|
| `wrapper` | 95 | 有被呼叫者、全部有真名、`span_upper` ≤ 256 |
| `ail_only` | 30 | 所有直接呼叫端都是 AIL 進入點或已判定的 `ail_only`(不動點) |
| `leaf_global` | 23 | 沒有被呼叫者、恰好碰一個全域、`span_upper` ≤ 64 |
| `thunk` | 4 | 入口即 `jmp` |

- 扣掉之後,`strong` 858 個裡仍然完全沒有任何描述的是 **286 個**(原 377)。
- 與 §6.0c 的估計對照:wrapper 95 高於當時的 57(當時要求「不是文件記載的入口」,工具只要求「沒有真名」);
  名稱傳播在真實資料上是 **1 輪就停**,沒有 §6.0c 估的 155 —— 那個數字把只有位址、沒有名稱字串的
  `verified_addresses`/勘誤也算成「已知」,工具不算,因為那樣產生的名字是 `wrapper(0x…)`,沒有資訊量。
- `ail_only` 的名字刻意只說工具能證明的事。抽查 `0x364d4`/`0x364fb`(24 個呼叫端全在 AIL 內):本體是
  「經函式指標配置 → 鎖定」與「解鎖 → 經函式指標釋放」,是 AIL 的記憶體輔助(靜態 RE,Capstone)。

### 6.0e 結構性命名第二版:wrapper 帶呼叫參數、leaf 依反組譯本體分類(同日)

§6.0d 的兩個弱點做掉了,產物由 152 筆變 **167 筆**,`strong` 裡完全無描述的由 286 降到 **270**。

- **wrapper 帶參數**:反組譯本體,依**呼叫順序**列出每次呼叫與 CALL 前最近 N 個 push(N = 被呼叫者的 `argc`;
  立即值照寫、非立即值 `_`、不足 `?`、`argc` 不明 `(?)`)。95 個 wrapper 有 94 個帶得出參數,例如
  `wrapper(load_res(0x1a4d, 0, 0x50))`、`wrapper(raw_result_code_0_1_2(), unit_inactive(0x32), unit_inactive(0x33))`。
  原本長得一樣的幾個 `wrapper(load_res)` 現在由資源編號區分。本體的 CALL 目標與清單 callees 不一致時退回不帶參數(1 個)。
- **leaf 改由反組譯判定**(§6.0d 的 `leaf_global` 23 個只看清單,看不到 `call [函式指標]`,其中一部分不是 leaf):
  本體須解到乾淨結尾、裡面沒有任何 call 或間接 jmp。38 個:`leaf_global` 14(`leaf_ref` 8、`leaf_get` 3、`leaf_rw` 3)、
  `leaf_ptr` 15(`get` 9、`rw` 6)、`leaf_pure` 9。全域以**指令範圍內的 fixup**判定,不靠位移大小猜。

這些仍然是結構描述不是語意。常數參數是機械讀出的事實(靜態 RE,Capstone),可以拿來當線索,例如
「哪個函式以資源編號 0x1a4d 呼叫 load_res」;但 `_` 只表示「不是立即值」,不表示參數不重要。

### 6.0f 開始人讀:函式名稱登錄表與前三批(2026-09-19)

使用者指示「依照你的建議自動繼續進行」,採 §6.4 的「求可用」路線:機械方法處理不了的函式,由呼叫端數多的開始人讀。

- **登錄表 `docs/data/function_names.json`**(手動維護,工具只讀):每筆必須帶位元組證據 —— 一串 `{"at", "insn"}`,
  `function_inventory.py --check-names` 在該位址實際反組譯、逐字比對,且位址須落在該函式範圍內。名稱錨在位元組上,
  不是錨在散文上;selftest 的真實 EXE 段每次都驗整張表。`--card ADDR` 印事實卡與反組譯供閱讀。
- **前三批共 37 筆**(全部 `static_re`,靜態反組譯、未經實機):
  BIOS/執行期(`kbd_buffer_has_key`、`kbd_flush`、`bios_tick_word`、`wait_next_tick`、`segread`、`int386`、`malloc`、`nmalloc`、
  `memmove`、`outp`、`abs`、`dpmi_lock_region`/`_range`)、繪圖(`blit_rle_image` 與鏡像版 —— PCX 式 0xC0 RLE、`blit_raw_image`、
  `blit_raw_cell`、`blit_res_cell_sprite`、`blit_res_cell_xy`、`copy_rect`、`blit_anim_frame`、`anim_step_and_draw`、`palette_cycle_tick`)、
  介面流程(`draw_dialog_cell`、`wait_key_with_marker`、`present_box_at_row`、`close_box_slide_down`、`charcard_say_and_wait`、`compare_to_glyph`)、
  遊戲資料(`prng_next`、`find_equipped_slot`、`unit_item_id`、`set_units_byte34_low_nibble`、`unit_uses_move_cost_row19`、
  `map_cell_set_bit7`、`map_collect_cells_byte1_set`)。
- **槓桿**:新名字會餵給結構性命名。光是 `memmove`(163 個呼叫端)就讓 wrapper 多解出 28 個。結構性名稱現在 238 筆,
  `strong` 裡完全無描述的降到 **212**(今天開始時 377)。
- 清單的 `callees` 現在只收落在 obj1 內的目標(E8 位元組掃描命中資料時會算出 `0x75c1f2d7` 這種假目標,讓 wrapper 判定永遠不成立)。

命名時的取捨:讀得出機制但讀不出用途的,名字只寫機制(`map_cell_set_bit7`、`set_units_byte34_low_nibble`),用途留給之後的證據。

### 6.1 解析程度(三層)

| 層 | 程度 | 依據 |
|---|---|---|
| 資料格式(地圖、精靈、動畫、文字、音效、存檔、DAT 容器) | **接近完整** | 每種格式都有解碼器、selftest、截斷韌性測試;文字可回寫,存檔可編輯;缺的只有 DAT 打包器 |
| 遊戲規則(戰鬥數值、成長、移動成本、事件系統、過場原語、AI 模式、SFX 觸發) | **高,但「證實」與「記載」要分開** | 核心公式有反組譯證據(AP/DP/MV/DX/HIT/EV、`0x1F183`);60 份 chapter_beats 重生一致;findings 17/17,但 17 是「登記過的」 |
| 程式碼層(每個函式是什麼) | **低,而且現在量得出來** | 1113 個入口位址主張全部對得上二進位;但有名字的原語只有 PRIM 26 + doc 錨定 27 + 已驗證位址 59;EXE 有 541 個 Watcom 函式、Ghidra 976 個 —— **約 110 個有名字,七成以上沒有人命名過**(問答當時的估計;§6.0 實測:分母 1037,機器登錄或文件記載 48%) |

**一句話**:資料層可以拿去用;規則層可以拿去實作但要把「記載」當假設;程式碼層若目標是修改
原版 EXE,只夠做局部 patch。

### 6.2 能不能改原版 / 新建遊戲

- 改原版:文字(`encode_text writeback`)、存檔(`fd2save`)、執行期數值(`fd2_stat_override`)、
  EXE 內數值表(`exe_tables` byte patch)今天就能做;圖像**只能拆不能裝回**(沒有 DAT 打包器);
  程式碼只能就地改已解到指令級的區域,沒有重連結器,不能加長、不能插新程式碼。
- 新建:可行度比改原版高(只需要規格,不需要二進位空間);卡點就是程式碼層未命名的部分與
  `0x15f84` 的 7 個未解參數。前提:驗收只用原版 DOSBox-X 實測,未證實的主張當假設。

### 6.3 五種方法(加一個共用前置)

| # | 方法 | 做法 | 優點 | 缺點 | 覆蓋 | 證據等級 | 時間(估) |
|---|---|---|---|---|---|---|---|
| 0 | **分母清單**(共用前置) | 四訊號 + Ghidra 建 976 函式的機械事實卡(大小、呼叫端/被呼叫者、`callee_argc`、引用字串、全域、已命名原語),標已命名/已記載/已驗證,產出 `docs/data/function_inventory.json` 進 artifacts 棘輪 | 每條路都要它;先知道真實覆蓋率(估 15–25%) | 本身不解語意 | 100% 列出 | — | **1 天** |
| 1 | **全面靜態掃描** | 依呼叫圖分層,每函式一張卡:反編譯 + 機械事實 + 人寫語意 + 證據等級;分子系統做,每子系統跑 `--precommit` 與 findings | 完整、可審、進得了 verified_addresses | 最慢;死碼與資料驅動行為仍解不到底 | ~100% | 記載 → 部分證實 | **30–40 天** |
| 2 | **批次反編譯 + 模型摘要** | Ghidra headless 一次吐 976 個偽碼,模型批次命名與一句語意 | 最快;當草稿能把路 1 的每函式時間壓一半 | 名字是推的;專案規則「填錯比留 unknown 更糟」→ 只能標 `inferred`,不能餵給 chapter_beats/verified | ~100% 有名 | 推論 | **3–5 天** |
| 3 | **動態優先** | `dosbox_exec_trace` 跑遍標題/城鎮/商店/30 章/過場,收軌跡與記憶體變化 | 證據天生最強;順便得到真實呼叫順序與時序 | 只涵蓋跑到的;每個場景要人操作或腳本驅動 | 60–70% | 證實 | **10–15 天** |
| 4 | **函式庫簽名比對** | Watcom CRT / AIL 的位元組樣式比對,一次命名 runtime 函式 | 便宜、確定、不用看語意;把分母砍掉 250–350 | 只處理非遊戲邏輯 | 25–35% | 證實(簽名相符) | **1–2 天** |
| 5 | **目標驅動局部解析** | 從「新建/改版需要什麼」反推,只解可達的那一叢,其餘標 `not_needed` | 最省;每個解出來的都用得上 | 不是「完全」;目標改了要補 | 200–300 個函式 | 記載 → 證實(配路 3) | **10–15 天** |

另有 **半天** 的免費檢查:掃 EXE 字串表找洩漏的函式名(doc13 已見過 `Get_EasyMagic`),有多少收多少。 **已做,0 個新名稱(§6.0)。**

### 6.4 三種組合與總時間(估)

- **求完整**:0 + 4 + 2(當草稿)+ 1 + 關鍵函式用 3 升級 → 約 **6–8 週**。
- **求可用(新建遊戲)**:0 + 4 + 5 + 3(當驗收)→ 約 **3–4 週**。
- **求有名字就好**:0 + 4 + 2 → 約 **1 週**,但全部是推論等級,之後每引用一個都要自己驗。

不建議單走路 2:快,但會把 976 個推論名字寫進知識庫,正是本輪清了 955 個的那種債。

### 6.5 更快的方式:三種真的縮時間的槓桿

1. **平行化**(縮牆鐘時間,不縮工作量):分母清單做完後依子系統切互不重疊的工作包(戰鬥迴圈、
   AI、事件、UI、渲染、音效),多個 agent 同時做,每包跑 `--precommit`,三道位址棘輪擋衝突。
   全面掃描 6–8 週可壓到 **2–3 週**;代價是 token 用量與審每包產出的時間。
2. **結構性自動命名**(真的省人工,證據站得住):本體只是「呼叫幾個已命名原語 + 常數」的包裝
   (如 `0x35b78` = pan+spawn+delay+palette)、thunk、只讀一個表的存取殼,機械命名成
   `wrapper(pan,spawn,…)`、`thunk→X`、`table_read(0x…)`,證據是結構本身。用現有的
   `callee_argc`/呼叫掃描就能做,估吃掉 **20–30%** 的遊戲邏輯函式,**2–3 天**。
3. **縮範圍**(路 5)。

**最快而不降級的組合,約 1 週**:分母清單(1 天)→ 函式庫簽名 + 洩漏名稱(1–2 天)→
結構性自動命名(2–3 天)→ 剩下的用模型摘要當 `inferred` 草稿(1 天)。結束時約 **50–60%**
的函式有帶證據的名字,其餘是標明推論的草稿;之後要用到哪個再升級。

### 6.6 我的建議

(2026-09-18 已先做一小時量測版,見 §6.0。)先做**路 0 + 洩漏名稱掃描**(1.5 天,不需要先選目標),把真實覆蓋率數字拿出來,再依「要完整
文件」或「要能新建遊戲」選 §6.4 的組合。使用者尚未選擇;本輪到此為止沒有動任何程式碼層
的解析工作。

---

## 7. 本輪反覆踩到、值得後人避開的坑

- **patch 腳本走 Write 工具,不用 heredoc**;Windows 主控台預設 cp950,印含 `≥` 等字元的輸出要
  `PYTHONIOENCODING=utf-8`。
- **驗證工具/突變 harness 執行中不得編輯檔案**(工作樹指紋),也不中途砍 harness;
  全量窮舉一次 87 分鐘,用 `--changed` 只跑改動 + 相依工具。
- **INNER 類有上限**:錯位址剛好落在別的函式內部的合法指令邊界時會被誤歸(`0x2e341`);
  呼叫鏈對應能抓到這種。
- **新舊版位址沒有全域常數**,分段常數見 §3;EDITION 假說要 ≥2 對支持。
- **錨點引文取結論句**,不是標題;跨行的取單行後半句。
- **提交前閘門一道 `--precommit`**,但它只管工具;文件/資料改動仍要跑 `audit_evidence_provenance --diff`、
  `verify_address_citations --diff`、`verify_address_claim_coverage`、`verify_generated_artifacts`。
- **只推 `fork remaster-local`**,不得推 `origin`。
