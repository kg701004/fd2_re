# 91 — Worklist(逐輪更新，依序執行)

> 目標:完成《炎龍騎士團2》反組譯研究，並考證當年開發工具。
> 每輪結束更新本表(打勾 / 補新項 / 調整順序)，與 `99-reflections-log.md` 互補。
> 圖例:✅ 完成 · 🟡 進行中 · ⬜ 待辦 · ❌ 放棄(註明原因)

## 第 1 輪 ✅
- [x] 素材盤點(`FD2.EXE` + 12 `.DAT` + 音效驅動)
- [x] 破解 `.DAT` 容器格式 + 寫 `tools/unpack_dat.py`
- [x] 辨識圖像/調色盤/文本/地形表 header
- [x] 攻略萃取成知識庫
- [x] 建知識庫骨架 + RE 計畫 + 反思 + README + git push

## 第 2 輪 ✅
- [x] **當年開發工具考證**(Watcom C/C++32 + DOS/4GW + Miles AIL v3 / XMIDI + AFM 動畫工具/作者 Lo Yuan Tsung)→ `04-original-toolchain.md`
- [x] 建立本 worklist
- [x] **EXE 資料表 dump**:`tools/dump_exe_tables.py`,9 表全對齊「舊版」offset,5 表 dump 並自驗全通過 → `docs/data/exe_tables/`、`03-…`
- [x] **圖像解壓**:破解 RLE(c≥0x80 literal / c<0x80 run),`tools/decode_image.py` 渲染標題+背景驗證 → `05-image-compression-format.md`
- [x] **音樂解析**:確認 XMIDI,`tools/xmi2mid.py` 轉 15 首標準 MIDI(note 平衡、tempo 直通)→ `07-music-xmidi-format.md`
- [x] **動畫機制結構**:AFM 容器 + FIGANI 幀封裝(幀數自描述 + offset 表)→ `06-animation-format.md`

## 第 3 輪 ✅(核心全完成;2 零星項 2026-07-05 核實已完成補勾)
- [x] **文本解碼**:破解 FDTXT(uint16 glyph 索引 + 控制碼 + 0xFFFF)+ 找到自製字型(FDOTHER_004,16×16 1bpp,1824 字模),**還原可讀中文** → `08-text-and-font-format.md`、`tools/decode_text.py`
- [x] **動畫逐幀拆解**:✅ **完整破解**!反組譯參數化解碼器 0x4F43D + 解出 13-byte 幀標頭(realW/H 在 +9/+11)+
      4 模式 RLE → `tools/decode_figani.py` 把 **264 動畫 2118 幀**全部解出(騎士揮劍動畫視覺驗證)← 使用者明確要求,完成
- [x] **持久素材抽取**:`tools/extract_all.py` → 本機 `extracted/`(raw/images/animations/music/fonts);**不入版控**
- [x] **劇情/對話結構解出**:[控制碼][說話者肖像ID][『][對白][』];全 35 章渲染成可讀 PNG(`extracted/story/`)→ `09-…`
- [x] **序章(FDTXT_001)逐章轉錄完成**(`extracted/story/序章_transcript.md`,本機)
- [x] **敵/我方動畫機制文件**:解碼器變體家族(全彩/remap調色/silhouette/dither)+ 陣營/面向 → `10-…`
- [x] **敵人/NPC 戰場 AI** 反組譯文件(0x15140 評分決策)→ `11-…`
- [x] **音樂播放與場景切換**機制(AIL XMIDI 序列)→ `12-…`
- [x] **戰場選單與行動系統**(行動狀態機/選單游標/Get_EasyMagic)→ `13-…`
- [x] README 知識庫總索引(可點選分類)
- [x] **glyph→Unicode 對照表完成(1824/1824,100%)** → `docs/data/glyph_map.json`(含數字/英文/漢字/標點/機器人雙字元代號)
- [x] **全 35 章劇情轉錄完成**:自動解碼成含說話者的 UTF-8 → 本機 `extracted/story/full_story_auto.md`(1450 句);序章~第3章另有人工精校
- [x] **按鍵綁定**(Enter/Space 確認、ESC 取消、方向鍵)反組譯 → `13-…`
- [x] **Get_EasyMagic** 法術面板反組譯(0x18ED0)→ `13-…`
- [x] **場景→曲號對映**:play_bgm(0x26777)+ 32 處呼叫 track 反組譯 → `12-…`
- [x] **LE fixup xref 工具**(`tools/le_xref.py`)解開 DOS4GW 重定位,可做 data xref
- [x] **控制碼語意還原**(反組譯文本渲染器 0x16D00-0x17200):FFEF/EE/ED/EC=開對話框(FFEF 帶 DATO 頭像)、
      FFFE=換行、FFFD=翻頁等鍵、FFFF=結束 → `09`;副產物確認 **DATO.DAT=人物頭像**
- [x] **劇情校對**:解碼自驗 + 上下文揪出 14 處形近字模誤判並修正
      (脅/實/黨/費/鍛/輩/辭/摸/牢/樁/紮/襲/態/責)
- [x] **陣營/狀態 remap 配色**:確認 LUT 來源=FDOTHER 資源#3(LMI1,23張256-byte LUT),dump 並套用展示(LUT0灰=已行動…)→ `10`;BB→LUT索引精確對應待續
- [x] **DATO 頭像全解**(136×4嘴型幀)→ `01`§7;**Unicode→glyph 反向表+編碼器**(round-trip 100%)→ `tools/encode_text.py`
- [x] 各 track 呼叫端對應確切遊戲狀態名(片頭/世界圖/城鎮/戰鬥/劇情)→ doc12「場景切換時的換曲」已列 5 狀態對映(2026-07-05 核實)
- [x] **FDSHAP 圖塊庫解碼**:標頭 count + u32 offset 表 + native 24×24 four-mode RLE；2026-07-26 直接掃 FDSHAP_000 的 288 tiles，mode `[0,2,3]` 全部完整解碼，撤回「僅不透明 bg-RLE」錯誤。`render_map.py` 依 `0x4deda` ABI 保留 transparent spans 為 index0；多層 foreground composition 仍不得由單張 export 推論。→ `01`§8
- [x] **全 33 張戰場地圖抽取**:FDFIELD×FDSHAP(配對 map N→FDSHAP[2N],索引驗證全通過)→ 本機 `extracted/maps/`;`tools/extract_maps.py`、`render_map.py`
- [x] **FDICON.B24** = 1680 個 24×24 **地圖單位 Q版小人 sprite**（four-mode RLE；撤回「與 FDSHAP 為不同 bg-RLE codec」，兩者共享 ABI、renderer branch 不同；每角色組12=4方向×3幀）→ `31`
- [x] **TAI.DAT** = WxH 圖像(sprite-RLE,如 155×42);多為 UI/特殊圖
- [x] 寫一篇總覽:「1995 年怎麼做出炎龍騎士團2」→ `15`
- [x] 寫一篇總覽:「1995 年台灣怎麼做遊戲 — 炎龍騎士團2 技術全紀錄」→ `docs/knowledge-base/15-how-fd2-was-made-1995.md`(2026-07-05 核實存在)

- [x] **FDFIELD 三段完整解析**:構成(地形)/控制(出場數/回合事件/寶箱/敵我roster)/出場位置;全33圖 metadata → 本機 `extracted/maps/maps_metadata.json`;`tools/parse_field.py`

## 第 4 輪以後(暫定)
- [x] 地圖格式完整解析(FDFIELD 三段)+ 渲染全 33 圖(見上)
- [ ] 反組譯戰鬥/命中/傷害/AI 演算法(Ghidra)，與攻略公式交叉驗證
- [~] **物品系統反組譯**(M1 用)→ `32`:已確認 物品表23B結構、傷害鏈(AP/DP 全域暫存 0x53c27/0x53c2b → 公式 0x15356)、roster 8裝備欄;[阻] 裝備加成精確累加點(夾攻擊大函式,表base-relative)、使用效果碼待續
- [ ] **轉職系統反組譯**(M4):轉職觸發(教會/道具)、職業數值替換、能力繼承、轉職後成長表切換 → 攻略道具表(勇者徽章→英雄…)交叉驗
- [~] **角色名對應**:補全 portrait→角色名 → `49`。核實後「12 個」已過期,實際已定案 38 組
      (0-31 共 32 + 48/66/68/96/97 共 5 + 本輪新增 126=ASR-06);其餘約 97 組多為泛用怪物/路人,
      對話走場景相依 `-19/-20`(見 `40`),**無法只靠對話反推**,需逐圖解 FDFIELD roster 才能繼續補
- [x] `FDICON.B24`=1680個24×24地圖單位sprite(sprite-RLE,見 `31`);`TAI.DAT`=WxH圖像(sprite-RLE)
- [~] `FD2.SAV` 存檔：Docker static trace 已固定 `rb/wb FD2.SAV`、全檔 `0x59cb`、四槽 record `+0x312b+i*0xa28`（`0x28` metadata + `0xa00` persistent roster）；真實 sandbox decode 與 `tools/fd2save.py` round-trip/tamper regression 已固定 `0x4dbd8` rolling-XOR、`0x4dbb9` byte-sum checksum。metadata `+0`=chapter、`0xff`=empty marker 已由 renderer `0x30437` 關閉，`+2..+5`=currency 已由 `0x2d411/0x2d528` 加減／UI render 關閉；其餘 metadata 尚待命名。不得再稱「強加密／無結構」；重製仍用自有格式，native compatibility 低優先。
- [x] **音色合成評估+MT-32實證**(SoundFont/MT-32/版本切換,munt渲染15首)→ `16`
- [x] **擴充劇本/玩法可行性評估**(戰場/對話/商店/機制)→ `17`
- [~] SoundFont/MT-32 → 見 `16`(MT-32 已渲染);SoundFont 試聽 + TIMB 配器對映待補
- [ ] 選定首個重製技術棧做「讀真資料 → 畫面」垂直切片
- [ ] 反組譯完整性盤點

## 重製前置(規劃/實作)
- [x] **音樂預錄 OGG**(MT-32 音源):15 首 → 本機 `extracted/music_ogg/`;`tools/export_music_ogg.sh`
- [x] **字型現代化規劃**(UTF-8 + TTF render)→ `18`(計畫:文字資料化 + TTF + 雙字型模式)
- [x] **劇本/關卡腳本系統設計**(可分支節點圖/敗北路線/商店/旗標)→ `19` + `docs/data/campaign_sample.json`
- [ ] 實作:`decode_story_text.py --script-json`(35 章 → UTF-8 script);重製文字層 TTF render
- [ ] 實作:從原版資料自動生成「線性 campaign.json」(parse_field + 劇情 + 商店)→ 原版模式
- [ ] 實作:引擎 ScenarioRunner 狀態機(節點/轉場/旗標)
- [x] **第一性原理可行性確認** → `20`(9 項必要能力全具備,降為工程整合)
- [x] **Go/Ebiten 重製架構規劃** → `21`(桌面/Web/手機)
- [x] **重製 MVP 垂直切片**:Ebiten 載入序章地圖+渲染+游標(方向鍵/WASD/觸控)→ `remake/`
- [x] **技術驗證報告** → `22`(桌面 ELF 10.8MB + WASM 10.5MB + 資產管線,三項全通)

---

# 重製 worklist(Go/Ebiten,本機優先;依序執行)

> **詳細工作拆解(WP/輸入/產出/驗收/衝刺)見 `30-remake-work-breakdown.md`**。本表為里程碑總覽。

> 策略:**先把本機桌面執行檔做成能完整玩,再回頭處理網頁/手機打包**(`22` 已證三平台都可建)。
> 每個里程碑 = 一個可執行、可驗收的切片。完成才往下一個。架構見 `21`,可行性見 `20`。

## M0 — 引擎骨架 ✅(已完成)
- [x] Ebiten 專案 + Docker 建置流程(`remake/`,`go.mod`/`go.sum`)
- [x] 載入地圖渲染(tileset.png + map.json,offset 表定位無漂移)
- [x] 游標移動 + 相機跟隨(方向鍵 / WASD / 觸控)
- [x] hi-res 畫布(640×400,CJK 拉畫布不縮字)
- [x] **本機桌面執行檔建成(Linux ELF)** + WASM 編譯成功 → `22`

## M1 — 戰棋核心(下一個,讓它「能玩一場戰鬥」)
> 驗收:能部署我方、選單下指令、移動(flood-fill 範圍)、攻擊結算傷害、敵方 AI 回合、判定勝敗。
- [x] 資料模型:Unit(HP/攻防/移動力/陣營/位置/alive/acted)、BattleState(回合/單位) → `remake/internal/battle/model.go`
- [x] 單位資料管線 `tools/export_units.py`(roster+座標+EXE數值→units.json)+ 引擎載入並渲染(陣營色塊+HP bar+選中資訊)+ headless test 全綠
- [x] 移動:flood-fill 可達範圍 + 高亮 + 選取/移動/待機(`move.go`);地形成本待接
- [x] **地圖單位 sprite=FDICON Q版小人**(24×24 待機動畫)→ `31`(取代誤用的 FIGANI 全身)
- [ ] 戰場選單狀態機(移動/攻擊/待機/道具/結束),對齊 `13`(游標/Enter/ESC)
- [ ] 攻擊結算:套**青衫公式**(物理/劍技/法術/恢復+命中+暴擊+經驗,doc 02 §4 = 實作依據)+ EXE 數值表(`03`)
- [~] 敵方 AI 回合:flood-fill + 評分選目標(擊殺×2),對齊 `11`(0x15140)：已補地形 AP/DP 與原版 `dmg≤2` 跳過門檻；情境加成、狀態倍率待 RE，且已證實原版 `0x157B5/0x150F1` 有 SpellID 評分／執行、`0x15B77` 依 spell family 分流目標。remake 已建立 `State.SpellBook`/`AIPlan.SpellID`、item raw K4 (`0x11`) command inventory、`AIAvailableSpells` 與 `AISpellCandidates`（攻擊／補血／增益／解毒祛麻／敵方狀態）；尚未接原版評分與實際施法行動。
- [ ] 勝敗判定 + **回合推進(回合無上限;上限只由劇本事件 turn>=N 設定,見 `27`§1)**
- [ ] headless 確定性回歸:固定種子打一場 → 結果可重現(驗演算法,不靠手玩)

## M2 — 文字 / 對話層
> 驗收:對話框能顯示 UTF-8 劇情、帶頭像、翻頁;字用 TTF render(不再靠點陣字模)。
- [ ] 工具:`decode_story_text.py --script-json`(35 章 → UTF-8 `script.json`,控制碼→結構)
- [ ] 引擎 TTF 文字渲染(接 `18` 字型現代化:資料化 + TTF + 雙字型模式)
- [x] 對話框 UI ✅(debd52d):原版框素材(LMI1 #21 310×99)+ orig 佈局(下框(5,112)@320/上框鏡射)+
      大側臉頭像(我方左面右/對方右鏡像面左,對映 0x4E8AF/0x4E8E1)+ 白字『』框內換行(≤3行);
      翻頁=campaign story 逐句 Enter。LMI1 #20=單位詳細狀態面板(待用)
- [ ] DATO 頭像接入:**4 嘴型幀 m0~m3 對話動畫(嘴開合+眨眼)**,非單張(對齊 `01`§7 / `31`§7);播放時機待反組譯 0x16D00

## M3 — 音訊層
> 驗收:戰鬥/城鎮/劇情切場景時 BGM 正確切換,用預錄 OGG(MT-32 音源)。
- [ ] OGG 串流播放(15 首,來源 `extracted/music_ogg/`)
- [ ] 場景→曲號對映(對齊 `12`,play_bgm 邏輯)
- [ ] (選配)SoundFont/MT-32 版本切換開關 → `16`
- [ ] 音效(SFX)接入

## M4 — 腳本系統 / 流程串接
> 驗收:序章→商店→分支→下一關 能一條龍跑完;戰敗走不同路線而非 game over。
- [ ] 工具:原版資料自動生成「線性 campaign.json」(parse_field + 劇情 + 商店)→ 原版模式
- [ ] 引擎 ScenarioRunner 狀態機(節點/轉場/旗標),對齊 `19` + `campaign_sample.json`
- [~] 商店節點：原版337筆商品 numeric ID／價格已驗、祕密商店與 town 回返已接、`ClassID`／item type／class equip 白名單、指定收件者與兩階段裝備 prompt 已接；賣出 UI 已接成「Tab→角色→欄位」，`SellSlot` 鎖定原價 75 折並同步移除 equipped flag；`0x1145a/0x1c142` RE 已接入 base+flag 重算與 `<0x80`/`>=0x80` 同類替換；raw `inventory_slots` 保留 source 8 bytes，Load/PartyUnits 依 `0x10f06..0x10f31` materialize 成 runtime 8 slots，內部空槽不再錯移。`0x14237→0x14818` 已鎖定 `range_min` 幾何用途；待：完整 item multiplier/效果碼。
- [~] 戰後 town/整備流程：campaign_full 的 postbattle→town、連戰 preparation 路線與 shop/rumor return 已盤點；`0x318ad` RE 已鎖定 30-byte 勾選表、一般 cap15／late cap19，remake 已接 `party_limit`、`partyDeploy`、save persistence 與可操作 preparation UI，永久 JOIN roster 不被改寫。church `0x3072f` 已證實四個入口，revive fee table、原子 `ReviveUnit`、church selector 與 class-change candidate/branch mutation 已接；尚待完整 GUI 轉職實機回歸與原版數值對照（無免費一般治療）。
- [~] 戰後 town/整備流程：preparation 與 church selector UI 已接；`docs/figures/church-selector.png` 為 xvfb 實機畫面。revive 與 class-change branch/mutation 已可保存 roster/gold；尚待完整 xvfb 轉職操作，以及原版 `+0x22/+0x23/+0x24` DX/race/multiplier 欄位資料化。
- [~] class-change church：已鎖定 `0x3151a..0x3152d` portrait→item 分支、`0x31860` inventory 掃描、`0x1b8e7` item 移除與 `0x31571..0x3157a` class/portrait 寫回；`0x526a7` mapping、`0x2a2e8` 成長重算與 editable branch 已接，待 raw race/multiplier 欄位與實機回歸。
- [~] class-change church：`class_change_targets.json` 已校正為兩層可編輯資料：current portrait 0..0x11→default/optional target（`0x526a7` 以 current portrait 索引，raw `0xff` 不產生 optional branch），以及 target portrait 0x20..0x41→class/mobility increment (`0x615fe`)；portrait 9 的 item 0x5a→target 0x34 special branch 明列。資料完整性與 mutation 已接，下一步追原版 race/multiplier 欄位。
- [~] class-change church：核心 `campaign.ApplyClassChange` 已依 `0x31602` 實作可重現 RNG（row `[min,max)`）、將新職 AP/DP/DX/MaxHP/MaxMP growth **累加**既有值、MV(+0x3b) 累加、保留 Lv、清 EXP、HP/MP 回滿與轉職道具移除；persistent party 已同步保存 MV。target 選擇與 equipment/UI 已接，仍需原版實機數值回歸。
- [~] campaign town/shop 外部交叉盤點：攻略頁明列第4、7、9、14、16、18、19、21章的武器店／道具店／教會／神秘店（來源連結已記入 handoff）；不能由攻略頁推論戰後立即順序，仍以 EXE table 與 `campaign_full.json` 的 postbattle→town/preparation 節點為準，後續測試不得把勝利直接串成下一戰。
- [x] ch02/ch03 story handler slices：ch02_pre/ch02_post 依 count-aligned scene line 範圍播放；ch03_post 接已證實的 ch04 scene3 lines0–3；ch03_pre 已由 jump-table/loadch/FDTXT_004 direct evidence 完成 binding，idx0→scene0 lines0–3、idx1→scene1 lines0–4，`story_ch04` 不再只播兩句 generic fallback。
- [x] ch04/ch05 pre-handler slice：`ch04_pre` 的 FDTXT_005 idx0/1/2 已接 `ch05.json` scene0/1（3+3+9句），map4 50-slot、pan、acting22/21 皆有 binding；`story_ch05` 已由空 cutscene 接回可編輯 handler。
- [x] ch05/ch06 pre-handler：新增 `HandlerDialog.Segments[]` 跨-scene adapter，依 FDTXT_006 #0 的 scene0→1→2→3 targets 展開 18 句；`ch05_pre` 完整 binding，`story_ch06` 已接回可編輯 handler。
- [x] ch06/ch07 pre-handler：FDTXT_007 index0/1（2+6句）與 map6/acting28/29 已接 binding，`story_ch07` 已接回 editable handler。
- [x] ch07/ch08 pre-handler：FDTXT_008 index0/1（跨 scene 15句+2句）與 map7/acting31/32 已接 binding，`story_ch08` 已接回 editable handler。
- [x] ch08/ch09 pre-handler：FDTXT_009 index0/1（2+5句）與 map8/acting35 已接 binding，`story_ch09` 已接回 editable handler。
- [x] ch09/ch10 pre-handler：FDTXT_010 index0 跨 scene0/1（6+6句）與 map9/60-slot 已接 binding，`story_ch10` 已接回 editable handler。
- [x] ch10/ch11 pre-handler：FDTXT_011 index0 跨 scene0/1/2（4+6+2句）、index1/2 scene2 延續，map10/acting38/39 已接 binding，`story_ch11` 已接回 editable handler。
- [x] ch11/ch12 pre-handler：FDTXT_012 index0 跨 scene0/1（2+9句）與 map11/acting40/41 已接 binding，`story_ch12` 已接回 editable handler。
- [x] ch12/ch13 pre-handler：FDTXT_013 index0（6句）與 map12/70-slot 已接 binding，`story_ch13` 已接回 editable handler。
- [x] ch13/ch14 pre-handler：FDTXT_014 index0（4句）與 map13/70-slot、pan 20,20 已接 binding，`story_ch14` 已接回 editable handler。
- [x] ch14/ch15 handler：Docker Capstone 已證實 pre `0x334f3..0x334f7` 的 `roster_has(12)`→FDTXT_015「有 12：0/1/2；無：3/4/5」，以及 post `0x239d1..0x239d3` 的「有：12；無：13」。pre/post 都已轉為 editable `if roster_has`；pre binding 含 map14/80-slot、pan、acting48，post 保留 dialog→sync_party→JOIN15→set_chapter15→town_ch16。runtime 只讀 permanent party roster，缺此資料 fail-closed；`story_ch15` 與 `postbattle_ch15_persist` 都已接回 handler。
- [x] ch16/ch17 pre-handler：`0x335bb` 的 `roster_has(18)` 接 `test/jne 0x3344d`；有角色18直接進 shared tail，沒有才 `spawn(group 1)`。已轉為 editable `if roster_has`，map16/60-slot/FDTXT_017 binding 接入 `story_ch17`。compiler branch 現繼承前置 LOADCH slot frontier，但 merge 後不假設分支新增 slots。
- [x] ch17 battle initial-group correction：原版 ch16 pre 只在 char18 缺席時 append group1，group3 是 ch16 post 才 spawn；`ch17.json` 不再把 1/3 固定 initial。Scenario 加入可編輯 `initial_groups_if_party_absent`，只控制戰前 `OnField` visibility；它不宣稱已還原 native append-slot identity，post handler 仍 fail-closed。
- [x] ch17/ch18 pre-handler：FDTXT_018 index0/1/2（7+4+13句）與 map17/70-slot、acting54/55 已接 binding，`story_ch18` 已接回 editable handler。
- [x] ch18/ch19 pre-handler：`ch18_pre` 實際 index0（8句）與 map18/70-slot 已接 binding，`story_ch19` 已接回 editable handler；未把未呼叫的 FDTXT_019 其他 strings 硬播。
- [x] ch19/ch20 pre-handler：FDTXT_020 index0（17句）與 map19/70-slot 已接 binding，`story_ch20` 已接回 editable handler。
- [x] ch20/ch21 pre-handler：FDTXT_021 index0（17句）與 map20/80-slot 已接 binding，`story_ch21` 已接回 editable handler。
- [~] class-change data/UI bridge：`LoadClassChangeTable`、`ClassChangeTargets`、`LoadClassChangeGrowth` 已接；church 現在先選角色再列 default/optional/special target，Enter 依 branch 消耗物品、套用 RNG stat reset、重算裝備並保存 persistent roster。runtime assets 已補入；待實機 xvfb 走完整轉職流程與校正 HIT/EV/DX synthesis。
- [~] class-change synthesis：`0x31602` 五組 `0x1e529` 先把新職成長加到 raw AP/DP/DX/MaxHP/MaxMP，隨後呼叫 `0x1b750`；該 routine 讀 raw `+0x37/+0x39/+0x3e`、item table 23-byte row 的 `+1/+3/+5/+7`，寫 derived AP/DP/HIT/EV `+0x48/+0x4a/+0x4c/+0x4e`。`RecomputeAfterClassChange` 已恢復並防止既有裝備重複計算；`+0x22/+0x23/+0x24` 是 constructor 清零後由其他 transient/effect writer 使用的旗標，class path 本身不寫入，不能臆測成 class modifiers。
- [~] headless class-change fixture：新增僅由 `FD2_CAMP_CLASS_FIXTURE=1` 啟用的 Lv20 portrait9＋item 0x58/0x5a roster，供 xvfb 依「教會→轉職→角色→target branch」操作驗證；正常遊戲不改變。實機截圖 [`church-class-targets.png`](../figures/church-class-targets.png) 已確認 default 0x29、optional 0x3b、special 0x34 三分支。
- [~] 分支與敗北路線：campaign runner 已有 on_lose→retreat 非 game-over 路徑與測試；battle Node 新增可編輯 `protect` 目標（空值沿用索爾），main 不再硬編碼唯一保護角色；待逐關核對原版保護目標與 retreat 後整備語意。
- [~] 存檔/讀檔(自有格式,非破解原版 `FD2.SAV`)：節點／旗標／金幣／道具／persistent party 已保存；2026-07-20 新增同目錄暫存檔+rename 原子寫入與清理測試，避免 town/shop/preparation 存檔被截斷。仍待完整 GUI/Xvfb 讀檔回歸。

## M5 — 內容完整化(原版可破關)
> 驗收:從序章玩到結局,全 33 戰場 + 全劇情 + 商店,正常玩法可達(無 debug hook)。
- [ ] 匯出全 33 戰場為引擎資產 + 全單位/數值表接入(對齊 EXE 表 `03`)
- [ ] 全劇情/對話接入(35 章)
- [ ] 完整性盤點:對照原版,缺漏列冊(`83` 完整性 > 投報)
- [ ] 正常玩法可達性驗證(連通/可破關鏈,參考 skill 踩雷)

## M6 — 跨平台打包(回頭做網頁/手機)
> 驗收:Windows/macOS/Linux 桌面包 + 網頁 + Android APK。
- [ ] 桌面交叉編譯 + 打包(Windows `.exe` / macOS `.app` / Linux AppImage)
- [ ] WASM 上網頁(資產載入 + `index.html` 完整化)
- [ ] Android:`ebitenmobile bind` → `.aar` → Gradle APK(觸控已支援)
- [ ] 玩家向 README(圖文並茂,突顯貢獻)+ 工程文件分離

## 擴充(M4 之後,擺脫原版固定 33 路線)
- [x] **可擴展事件系統規劃** → `29`:trigger/when/do DSL + 文本事件控制碼 `{{}}`;條件/動作 Registry 可註冊;原版 30 關可表達+自創戰役
- [ ] 實作 EventSystem(ConditionRegistry/ActionRegistry)+ DialoguePlayer 解析 `{{}}`
- [ ] 自創戰場 + 自訂劇本(用 `19`+`29` 系統)
- [ ] 多分支劇情線 / 多結局
- [ ] 編碼器回寫中文(`encode_text.py`)做在地化/二創

## 第 5 輪 ✅(開場流程反組譯 — 使用者指定)
- [x] **建反組譯器** `tools/disasm_le.py`(capstone 解 DOS4GW LE,docker)+ 確認 entry/main/狀態機
- [x] **頂層狀態機反組譯**:真 main=0x25bf4(雙層迴圈),核心狀態變數 `[0x53c03]`=章節,兩張章節跳表(0x51d71 戰前劇情 / 0x51de9 戰後)→ `23`
- [x] **標題序列**:角色立繪 5 幀(FDOTHER #0x45-0x49,320×147)垂直捲動(非旋轉)+ FLAME DRAGON logo(#7 sub0)+ 主選單;**解碼器當 oracle 解圖視覺驗證** → `23`
- [~] **主選單機制**:輸入迴圈/scancode dispatch(↑0x48/↓0x50/Enter/Space)/游標 wrap、return `0=新遊戲`、`1=0x30550` slot selector 已由 Docker Capstone 重跑；第三 return branch 直進 `0x10010`、持久資料來源未閉合。remake 現有單一 JSON save 是 fallback，不能稱原版 LOAD/CONTINUE 已還原 → `23`、`57`
- [x] **新遊戲→開場對話→自動進戰場**:[0x53c03] 章節驅動,cutscene 0x3231b(與前代主角對話)→ 戰場地圖=章節*3+2(自動串接)→ `23`
- [x] **call-graph 遞迴反組譯工具** `tools/callgraph_le.py`(可達集/callers/rpath/funcof/jtab)→ `24`
- [x] **釘死 cutscene→戰場鏈**:0x10010 真 caller=0x1a251/0x26130,路徑 main→0x25ebb→0x10010,獨立驗證章節跳表(修 data 段 fixup)→ `24`;排除偽命中 0x1b051/0x26f30
- [x] **[0x53ecc] 戰後/事件完整狀態機**:事件解譯器(0x205c9-0x20c64,28處設1/2)↔戰役迴圈(==1進世界圖/中場 0x22e5c、==2勝利→戰後跳表+結局判定+下一章)→ `24`§6
- [x] **挖完事件指令集** → `25`:第三張章節跳表 0x51b19(戰場事件,30章/18 handler)、FD2 事件=每章 C handler 非 byte-code、事件原語(0x3453e 查單位/0x205be prologue/回合數=[0x53bef])
- [x] **逐關挖 18 特殊 handler** → `26` + `tools/event_handler_dump.py` + `docs/data/battle_events.json`(30章條件→動作,供 remake 去 hardcoding)
- [x] **補完事件語意（2026-07-16 勘誤）**:`0x3453e(idx)=unit_inactive`([0x53a45]+idx*0x50+5 bit0；1=死亡/隱藏/inactive，0=active/alive)；`0x33499`=roster_has(查 [0x53bf7] 我方名冊);**handler 無動作函式**(只條件→設碼+繪圖)→ `25`/`26` 回填。舊記「使用者確認 bit0=存活」已被 constructor/death-path 反組譯推翻並撤回。
- [x] **反思日誌補第 7-10 輪** → `99`
- [x] **挖完 `[0x53bf7]` 表語意**:不是 tile,是**我方隊伍名冊**(32槽×0x50B);`0x33499(id)=roster_has(id)` 查 byte[+8]==角色ID(章16 用)→ `25`/`26` 回填;兩單位陣列釐清([0x53a45]96槽全場 / [0x53bf7]32槽名冊)
- [x] **回合計數釐清**:`[0x53bef]`=回合數(開始1/inc/cmp N),`[0x53ec8]`=累積計數(非回合)；**修正前輪把 [0x53ec8] 當回合**。byte+5 歷史判讀經 2026-07-16 完整反組譯定案為 bit0=inactive。
- [x] **戰鬥規則來源盤點 + 動態驗證清單** → `27`:青衫公式=remake 實作依據+交叉驗證;列出 10 項需 DOSBox 實機驗證(核心 #1-4=戰鬥狀態機旗標/計數語意);新增「回合無上限」需求
- [x] **動態驗證清單更新** → `27`§3:byte+5 bit0 已由反組譯定案為 inactive(1)/active(0)，bit7=已行動；回合=我方全動+敵方AI全動完;7-8用青衫攻略;9-10不需要;3([0x53ec8])低優先。舊「bit0=1 是存活」使用者記憶已撤回。
- [x] **撤回 `[0x53ad5]`=opened-treasure／unit-pointer 斷言**：`0x10322` 初始化時複製 0x20 bytes 到 `[0x53ad5]` 指向的 buffer，`0x13d00` 以 event index 寫其 byte；ch25 post `0x24f30/0x24fb1` 讀 entry #12 來選 FDTXT index（base+5/base+8）。它是 battle-local state table，但高階 event 意義未命名；`OpenedTreasure` 保留 remake-owned state，不再聲稱原版位址。
- [x] **state table entry12 writer closure**：`0x356bc..0x35821` 先 gate table[12]，成功臂以 actor class 查 item `0xd0`、`0x1b8e7` 消耗它、完成 presentation 後才設 table[12]=1，接 `spawn(1)→JOIN(31)→FDTXT #4`。因此 ch25 post 的 table[12] base+5/+8 有直接來源；尚未完成兩臂 runtime 資產，不能以 treasure／party condition 取代。
- [x] **entry12 dispatch-scope audit（official IDA 9.4）**：`sub_356B7=0x356b7..0x35822` 有八個 generic dispatcher/UI control-flow xref（`0x117e7/0x16f55/0x190ac/0x1a813/0x1aa1d/0x1d80b/0x1d8ba`）；目前沒有 map25-local caller 證據。故 item `0xd0` 分支保持 raw event capability，禁止接成「ch25 固定寶箱／座標」或 campaign 自動流程。
- [x] **撤回 ch27 `0x24618`=acting 的暗示**：official IDA 定義 `sub_24618=0x24618..0x24754`（含 post-handler `0x33af1/0x33c9d` callers）；Docker Capstone 證實它是 13×8 offscreen terrain + 固定 9-pass strip composite + 0..62 palette 收束的地圖轉場。四個參數是 tile/strip geometry/progression，不能降成 actor `act`、pan 或任意 fade；renderer adapter 待實作且維持 fail-closed。
- [x] **全 30 關卡目標表(攻略 ground truth)** → `28`:每關勝利/失敗/加入條件;**失敗條件=護衛目標**證實 unit_state 機制;加入=roster_has;ch30 魔神連鎖=回合事件;remake 關卡規格直接可用
- [x] **撤回章17 alive 誤讀**:依 `unit_inactive` 重新解讀，指定單位 inactive 才依 jcc 設碼；舊「指定單位存活→設碼」已撤回 → `25`/`26` 回填
- [~] 單位 0x50B 結構:+5(bit0=inactive/bit7=已行動)/+8角色ID/+0/+1/+2/+6/+0x31 已解;完整逐欄佈局 [阻](remake 用自有 struct,不需)
- [ ] (補)更新 doc 12:修正「main=0x10000」、補章節→BGM 表 0x51e63 精確曲號

## 第 6 輪 ✅(戰鬥全螢幕演出畫面 1:1 還原 — 使用者逐項對照;①-④ 全完成 2026-07-05)
> 目標:remake 戰鬥攻擊演出(orig_05)像素級對齊原版。方法=**密集網格疊圖 oracle**(見記憶 pixel-align)+ 反組譯確認機制,**無 dosbox debugger**(0.74 vanilla 不能 dump)。
- [x] **完整 RE 戰鬥演出繪圖機制** → `35`:演出主函式 0x28a6c、blit 0x4e63d(無縮放/無翻轉,尺寸朝向燒進素材)、固定錨點(164,157)、phase [0x540ff]、BG 多層(0x52381=BG.DAT)、戰場→BG 表 0x52363
- [x] **figure 幀/姿態**:我方亞雷斯=攻擊動作1 `FIGANI_013_f01`(組×3+1,人眼確認);幀序播放;守方不翻轉(FIGANI_288 原圖面右)
- [x] **白斬擊弧 = FIGANI 攻擊幀自帶**(燒 sprite),移除程式 vector 補弧
- [x] **[設計鐵則] 我方=背影+腳下台座 / 敵方=正面**(使用者確認,與攻守無關純陣營)→ `35`§3.2.5
- [x] **figure 位置對齊**(密集網格+程式量土台中心):我方土台中心 x≈238、敵方腳 y≈135(@320)
- [x] **狀態欄對齊**:名字放大(16px視覺)、血條加長(緊接標籤到數字)、bevel 立體框、HP/MP淺藍標籤、暗槽色暗版、上下欄位置/間隔(我方離頂、敵方離150線空隙)
- [x] **z-order RE**:演出順序狀態欄(0x28ce7/0x28d62)先、figure(0x28e76/9a/ee0)後 → figure 蓋住狀態欄;remake 改 BG→狀態欄→figure → `35`§4.-1
- [x] **狀態欄機制 RE**(agent):真繪製器 0x18c6d(非 0x29164);框=素材sprite、HP=逐欄cell(len=curHP×101/maxHP)、名=16×16點陣字、數值=6px digit cell → `35`§4
- [x] **清除錯誤斷言**:土台正名 FIGANI自帶→**TAI.DAT 台座**(0x29164 載 0x28c46);figure-X=word[unit+0x40] 誤讀;對話框開框碼 0x16F40
- [x] **① TAI.DAT 台座解碼 + remake 貼上** ✅(v23):TAI_004=154×42 綠草橢圓台座(decode_sprite 解 body[4:],index0透明17%);remake 載 tai_004.png 貼我方腳下(z:狀態欄<台座<figure);對齊 orig 取代偏灰 dither。確切 entry↔職業/地形對映待後續
- [x] **② 複查 `+0x40`／figure displacement**：**`+0x40=當前HP`**（`0x18c98` 血條 `word[+0x40]×101/word[+0x42]`=HP%）與 `+0x44/+0x46=current/max MP` 已閉合，舊「戰場格 X」已清。`0x29f72` 是 derived AP/DP/HIT/EV、HP、item、terrain/RNG 的 hit/crit/damage resolver，**不是** lunge；`+0x48/+0x4a` 亦是 derived AP/DP。`0x2935b` 直接以 `frameIndex*4+8` descriptor pointer 讀 header `u16 X/Y` 再交 `0x4e63d`，故逐幀 figure displacement 已閉合為 frame metadata；caller schedule／攻守配對仍另列待辦。
  - [x] runtime export guard：`cmd/fd2` regression 對 `meta.json` 全部 22 個 FIGANI resource、每一 frame 的 `(X,Y)` 與 player archive `FIGANI.DAT` header 比對；不再只憑 exporter 意圖宣稱 runtime 位置資料正確。
- [x] **③ 狀態欄框/HP 用真素材** ✅(v25-26):破解 FDOTHER#5 LMI1 sub-sprite codec(反組譯 0x4e916:c≤0xC0 literal/c>0xC0 run,新 codec,`tools/decode_lmi.py`);框=#22(149×42 含bevel+標籤+槽)貼 panel.png、血條 cell=#27-30;修 HP靠左(槽 x21-123)/提亮/數字對位。doc35 §4.2.5。盜賊 y 軸對齊(276→296,頭頂偏上一排)
- [x] **④ BG 草地延伸到 figure 腳下** ✅(2026-07-05 使用者確認 `docs/figures/battle_restore_grid.png` 網格對照:左原版/右 remake 兩邊草地都延伸到 figure 腳下、台座疊綠草非黑底,一致)

## 第 7 輪 ✅(戰鬥演出資料驅動 + 像素級收官,2026-07-02)
> 從「手調對齊」進化到「原版資料驅動」;README 對外展示;全部 push(commit 至 a42ee4a+)。
- [x] **[重大] FIGANI 幀標頭 +0/+2 = 每幀絕對螢幕座標 (dx,dy)@320**(修 doc06 錯誤標註「boundW/boundH」):
      f01=(141,3)/盜賊=(16,41) 與模板匹配 orig 落點完全一致 → 走位/伸擊/突刺全在資料,引擎照貼即可
- [x] **戰鬥演出資料驅動重寫**:meta.json(22 個 FIGANI 全幀 dx,dy)+ loadFigMeta;刪 lunge/錨點手調;
      FIGANI_013 15幀=f01-f10旋轉蓄力/f11黃劈擊/f12-14突刺;盜賊 4 幀待機呼吸
- [x] **打擊感**:命中=全紅剪影交替閃(redSilhouette,orig=VGA色盤閃紅)+ HP 命中窗快抽;5 階段對照 orig 全對上
- [x] **通用化**:newAtkAnim 建構器(所有角色同管線:攻=組×3+1/守=組×3;演出長度隨幀數;命中幀=倒數第4幀通用推定)
- [x] **播放速度接口**:FD2_BATTLE_FPT 環境變數(tick/幀,預設3)+ atkAnim.fpt
- [x] **像素級對齊(模板匹配法)**:三 figure+台座+狀態欄框+三處數字 全部 err=0 且 dx=dy=0;
      狀態欄=原生 149×42 blit(敵(0,154)/我(171,4))、數字=LMI1 #31-40 素材(#42-51綠/#119-128黃=滿血變色)、
      LMI1 混雙 codec(框 0x4e916/小cell 4-mode)、VGA 6-bit palette ×4(decode_lmi 修正)
- [x] **README 對外展示**:battle_restore.gif(orig|remake 同步+網格)、battle_storyboard.png(5階段分鏡)、
      battle_restore_grid.png(網格驗證);新增「戰鬥演出:像素級 1:1 還原」節
- [x] **FD2_SHOT_SERIES 逐幀截圖鉤子**(GIF/分鏡素材管線)
- [x] 名字=TTF 28px+深藍描邊(~85%,既定決策:只有狀態欄數字用點陣素材,其他文字 TTF)

## 第 8 輪 ✅(remake 玩法系統盤點與補完 — 魔法/SFX 已於第7-11輪補完,2026-07-05 核實補勾)
> 使用者指示:檢視腳本系統一路到移動/觸發戰鬥/魔法,盤點缺口逐項補。
- [x] 盤點完成(見下缺口清單)
- [x] **腳本系統 campaign(M4 骨架)** ✅(74bf386):internal/campaign(節點圖 Runner:story/battle/
      choice/event/ending + 旗標 + 敗北路線 + choice 條件選項;單測3條);引擎接線(FD2_CAMPAIGN=1、
      enterNode/campInput/drawCampaignUI、勝敗 Enter 轉場、resetBattle 重試);campaign.json 第一章示範
      (敗北→撤退設旗標→再戰)。待續:商店節點、存檔、原版 33 關自動生成 campaign
- [x] **移動動畫** ✅(74bf386):battle.Path(BFS 路徑)+ walkAnim 沿路徑逐格走(方向幀+OffX/Y 內插,
      ~4-5 tick/格,走完進攻擊/待命,期間鎖輸入);AI 移動沿用瞬移(待接同管線)
- [x] internal/battle 測試失敗已修 ✅(e09c68c):部署格斷言=舊設計殘留,對齊現行(部署格屬 spawn_party)
- [~] **魔法系統** (第7-8輪完成資料與部分 runtime,commit 3c618c4/74366fa:暫定四向 action UI+法術+MP+青衫公式;code: ringInput/castSp/spells.json)——`0x18d8c` 已證實方向 result order，但 `0x1cff0` command table、完整 native 演出仍待；
      不存在獨立 spell-id→FIGANI 特效索引（doc37）；僅已證實施法者自身 FIGANI 組動畫，其他 spell runtime 保持 partial
- [x] **音樂** ✅(e09c68c):audio.go(ebiten/audio+vorbis;忠實 play_bgm 0x26777:同曲不重播/換曲釋放/
      無限迴圈);campaign 節點 bgm 驅動;FD2_MUTE 靜默。待:非 campaign 模式場景→曲號自動對映(doc12 表)
- [x] **音效 SFX** ✅(第8-11輪完成,cmd/fd2/audio.go;commit e09c68c 音樂+SFX 收線)。資料位置 RE(doc36):`FDOTHER.DAT` 資源 #31(巢狀 `LLLLLL` 容器,14 個 8-bit
      unsigned mono raw PCM 子樣本)+ 戰鬥音效動態 index(同檔案,依攻擊資料決定 index);播放走
      `AIL_init/set_sample_address/set_sample_loop_count/start_sample`(0x26896/0x26945)。
      待:14 子樣本→UI事件對照、戰鬥動態 index 表還原、remake 端接入(SDL_mixer/ebiten audio)
- [~] **native action overlay／現行四向 approximation**：官方 IDA 9.4 `0x18d8c` 已釘死 `↑0=攻擊/←1=法術/→2=物品/↓3=待機`，而 `0x1741c` 已證實為 FDOTHER#2 四張 indexed asset 的十字 slide；battle wrapper 的 directionState 固定 `[0,1,2,3]`，因此 raw cell index=`3*availabilityWord+2*directionState` 的 enabled cells 是 `[0,2,4,6]`、disabled 是 `[3,5,7,9]`。先前誤把 `0x1728c` 巢狀 menu 的可切換 `0x12…` states 當作 battle gate 已撤回。visible cursor `column/row` framebuffer byte-address=`+0x8088+0x18*column+(0x18*0x1c8)*row` 亦已閉合；`fdother.BattleActionOverlayState`／`ActionOverlayOrigin`／`BlitActionOverlayFrame` 已把 ABI、open／close 各四幀 offset 與 index-0 transparency 接成 unit-tested primitive。remake 現在只在玩家提供 FDOTHER.DAT 時直接載入 #0 palette/#2 cells 並畫 final-open native skin，無資料時退回 PNG ring；Docker/Xvfb screenshot 已實跑證明 cell skin 出畫且不依賴中文字型。adapter 已採用 `0x1b83d` equipped/ID `<0x80` 前提和 raw command-mask 非零 gate（legacy scripts 才回退 Spells），但仍非 native gate 全等價。command22 是 `unit+0x27` 的已知 writer；仍待狀態名稱／其他 writer、open/close animation、DOSBox visual diff、attack target geometry、`0x1b8a6` 後 item selector/effect、圖示 provenance、攻防預覽。

- [~] **native command target flag bridge**：`0x14818→0x4e040` 的 raw target resolver 已有純資料層（camp predicates、cross、cardinal flood-fill，bit40 block／bit80 zero-cost）。已釘 flags 是 FDFIELD composition event word low byte（entry+2），`export_engine_assets.py` 輸出 `native_target_flags`，`battle.Load` 只在尺寸與 length 精確吻合時載入 `State.NativeTargetFlags`（否則 nil/fail-closed）；待把 verified candidate confirm/effect 接入 native UI，terrain-control byte0/cost 均不可替代。
- [x] **native command MP transaction**：官方 IDA `0x21227→0x1CA89` 已證實 generic command 在 candidate array 建立後、逐 target effect 前以 record `byte+5` 從 actor runtime `+0x44` 扣 MP，前段 selector 已 gate `currentMP >= cost`。`SpendNativeCommandMP` 以 raw 0..255 cost 實作該成功交易並在 invalid/MP不足時不變更；刻意不接受 normalized `Spell`、不搶接 legacy cast/UI。
- [x] **generic native command two-stage data contract**：`NativeCommandEffectTargets` 固定 `0x1cff0` generic path：actor/`record+3` candidate list → confirmed candidate → confirmed cell/`record+4` final-effect list；non-candidate confirmation 拒絕。它不涵蓋 `0x17/0x1e` special branches、MP/effect/renderer，且尚未接 UI。
- [x] **native command record loader**：`NativeCommandRecord` 明確表示 verified IDs 0..35 的 raw `+3/+4/+5/+6` 為 selection/effect mode、MP cost、target code；從現有 physical `spells.json` 讀取時逐 row 重解 `raw` 七 bytes，欄位不符、缺洞或非 36 rows 均拒絕，避免 normalized Spell 名稱／效果編輯污染 native ABI。
- [x] **SDD native command family matrix**：`56` 現以 IDs 0..35 的 dataflow、strict engine slice、UI/renderer gate 三欄固定已證實 family 與 fail-closed 邊界；不得以 label、raw record 或 generic dispatch 把未知 ID 借接 legacy `CastArea`。ID24 已更正為玩家 `2A6BD→276EC→1C81F` 的 derived-stat special route；AI table 的 `funcs_1541f[24]=22153` 是另一分派，不能誤接為 ID16 heal。
- [x] **commands 0..8 direct compositor + numeric route**：`0x1cff0` 對 IDs0..8 直入 `0x2a6bd`，確實不是 handler table 的 `0x21227/0x213b7` wrappers；但 direct `0x2a6bd` 的 `sub_2b659` MP event 和 final-target loop `1C75E(targetSlot, commandID)` 已重新逐行確認。故 ID0 executor／target UI 恢復為 bounded state slice，renderer/post-resolution 仍未宣稱完成。
  - [x] generic renderer schedule：`funcs_2ac25[0]=0x26152`；`0x2a6bd` 以 handler mode0 取 step count，再逐 step 走 mode2→`0x11eb0` 320×200 present→`0x17aa9(1)` tick→mode1，收尾另走 mode4/double-buffer path。`0x2b9a1` 依 descriptor frame byte+6 delay 推進 `0x540fc/0x540fd` subframe counters。這是 schedule ABI，不為 handler 視覺命名。
  - [x] generic BG selector boundary：`0x2a6bd→0x2b5e1(finalCount, finalTargetArray)` 倒序 target scan，經 `0x12e38`／`0x1f183`，只有 gate 不通或累積 selector=0 才以 control byte+2 取代 selector，再載 `BG.DAT`。`NativeCommandBackgroundSelector` unit regression 固定這條 raw ABI；command ID 只先選 generic/special presentation branch，不直接選 BG resource。selector semantic 保持 raw。
  - [x] BG archive input：`BG.DAT` #0/#1/#2 為 320×100 的 `0x4e63d` four-mode single-frame payload，新增 `fdother.DecodeArchiveSingleFrame` 與 player-archive decode regression；它只提供 indexed frame，layer selection／schedule 仍由 native caller evidence 決定。
- [x] **shared native damage route IDs0..12**：IDs0..8 經 `2A6BD→2B659/1C75E`，ID9 direct `1CA89→1C75E`；IDs10..12 的 `0x21548` 專用 compositor 尾端也直接 `1CA89→per-target 1C75E`。同樣扣 MP、逐 target numeric writer、success acted；engine bounded support 0..12，UI 仍僅 ID0。不得從 numeric 共用推論 visual equivalence。
- [~] **native command IDs13..16 healing route**：IDA `0x21AD9/0x21B99/0x2211C/0x22153→0x21B18` 已閉合 generic final target array、`0x1CA89(actor,id)` MP debit、`0x1C8ED→0x1C916` per-target HP restore 及 `+0x42` cap；其 amount 公式同 `9/10 + rand%100/1000`。`ExecuteNativeCommandHeal` 已接 strict non-UI engine slice（own record target/MP/restore/cap/actor completion，family boundary fail-closed）。專用 indexed animation、UI、SFX、message 未接，禁止誤用 IDs0..9 damage executor。
- [~] **native command ID24 player special route**：玩家 confirm 的 `0x1CFF0` 對 `0x18` 直入 `0x2A6BD→0x276EC`；`0x276EC→0x2B659` 以 `0x1CA89(actor,0x18)` 扣 record24 MP，並以 `trunc(actor derived +0x48 × 15/10) - target derived +0x4a` 呼叫 `0x1C81F`。原版為多段演出暫時復原 HP 後等份遞減，`ExecuteNativeCommand24` 已接相同 final delta 的 strict non-UI slice。`funcs_1541F[24]` 雖為 `0x22153`，但只在 AI／自動 `0x15311` dispatcher 使用，且傳 ID16 給 heal tail，不能拿來推導玩家 ID24。multi-hit／presentation/SFX/UI 未接。
- [~] **native commands28/29/31 derived-strike siblings**：同一 `0x276EC` 對玩家 ID28／29／31 分別選 20／12／18 倍率，並經 `0x2B659→0x1CA89(actor,id)` 與同一 final HP delta path；其 ordinary record geometry 可走 `NativeCommandEffectTargets`，`ExecuteNativeCommandDerivedStrike` 已接 strict state-only slice。ID30 的 special route 亦已收斂：`0x1CFF0` 先確認 record+3 candidate，`0x149F8` 從 saved pre-confirm cursor 朝 confirmed cursor 走 `record+3-0x10`（record30=4）格；X-first，僅 X 相同走 Y，selector=1 只收 enemy，然後 `0x2A6BD→0x276EC` default倍率18。`ExecuteNativeCommand30` 已接顯式 cursor state slice；不將其隱藏接入 current UI，cursor lifecycle／multi-hit／SFX／indexed renderer 仍待。32..35 走 `0x27FC9`。
- [~] **native commands32..35 `0x27FC9` compound family**：ID32 `→0x2111A→0x1C75E` numeric、ID33 先清 final target `+0x25..+0x27` 再以固定 `0x320` 走 `0x211A4→0x1C916` restore、ID34 依序 `0x22721/0x22866/0x22997`、ID35 依序用 IDs26/22/27 呼 `0x22D1B` 寫 `+0x25/+0x27/+0x26`。`0x27FC9` 的唯一 caller 是 `0x2A6BD`，它在 `0x28189` 進 `0x2B659`；該 path 唯一 `0x1CA89` site 由 FIGANI container header `byte+4==1` gate。IDs32..35 的 class19 player source 已具實證：optional class-change portrait/group4..7 與初始 group20 對應 #13/#16/#19/#22/#61，archive byte4=`2/2/2/5/5`，所以這些可達玩家 path **繞過已知 debit sink**，儘管 selector 仍以 record `+5` gate 76/52/28/36 MP。`figani.Animation.HeaderByte4` archive regression 固定原始值；不可泛化成 AI／未知 group 免費，亦不可先接 `SpendNativeCommandMP`。transaction dataflow、multi-effect ordering/rollback、UI/SFX 待 runtime／額外 evidence，engine 保持 fail-closed。
- [~] **native commands 17..19 transient modifiers**：ID17/18/19 handlers 已直接定位 `+0x22/+0x23/+0x24` nonzero gate 與 writer：17 對 derived `+0x48`、18 對 `+0x4a` 做 `__CHP(value*0.15+1)` **toward-zero** increase 並設 2..5 duration，19 對 `+0x4c/+0x4e` 各加 15 並設 duration。`0x377A4` 暫存 control word、設 RC=11b、`frndint` 後 restore，故撤回 FPU-rounded／未知 round-mode 說法。ID17/18 的 wrappers 都以 `0x1CA89(actor,0x12)` debit，且 records17/18 的 raw 7 bytes 相同；因此禁止泛化成「每 handler 必傳自身 ID」。這撤回 doc35 將 `+0x48..+0x4e` 稱作 screen coordinates 的衝突斷言；status labels、duration decrement、UI、engine integration 尚未閉合。
- [~] **native commands 20..21 flag-clear/restore route**：`0x22A85/0x22BC6→0x22AA8→0x22AF6` 分別對 `+0x25/+0x26` 做 nonzero gate；成功時以 command record 10 呼 `0x1C916` HP writer 後清 flag，零 flag 只顯示失敗。MP debit 仍以 command20/21 record。`ExecuteNativeCommandClearRestore` 已接 strict non-UI core（record10 amount、raw clear、cap-aware restore、empty gate仍 successful completion）。兩個 status 名稱與 UI 未閉合；ID22 的 `+0x27` application route 不可混入。
- [~] **native command 22 application route**：`0x22BE1→0x22CDA→0x22D1B` 在 `+0x27==0`、class `+0x20∉{0x19,0x1a}` 且 `rand()%100<50` 時，固定以 `0x1C81F(target,10)` 扣 10 HP，寫 `rand()%4+2` 至 `+0x27`；其他路徑僅失敗顯示。它已接入 `ExecuteNativeCommandApplication` 的 strict raw core；status name/tick、UI、expiry recompute integration 未閉合。
- [~] **transient command duration lifecycle**：`0x1A30B` phase driver 依 camp 呼叫 `0x1A866(camp)`；它對 active 同-camp unit 的六個 bytes `+0x22..+0x27` 逐一 decrement，歸零才發 expiry feedback 並 `0x1B750` 重算 derived stats。remake 的 `Unit.NativeTransient[6]`、bounded raw offset API 與 `TickNativeTransients(camp)` 已按同-camp/active/alive/independent-byte ABI regression；尚未將 expiry 接入 campaign equipment recompute、UI/status icon 或 native command executor，故不可稱 gameplay 完成。
- [~] **native command 23 special relocation**：`0x2218A→0x22253` 已確認先把 selected unit `+0/+1` 寫 `0xff/0xff` 以作離場演出，再直接寫 selector cursor globals `0x51CF9/0x51CFD` 進場；這是 direct coordinate relocation，非 path movement。其 `0x17` special selector 的落點合法性、camera/render/UI 和 remake integration 尚未閉合。
- [~] **native commands 25..27 closure**：ID25 `0x22C04` 以 record25 MP debit，僅在 target `+5 bit0x80` 已設時清除該 action-complete bit；`ExecuteNativeCommand25` 已接 strict non-UI engine slice（two-stage targets、MP、target clear、actor completion，invalid raw state pre-mutation reject）。ID26/27 `0x22CBF/0x22E41` 分別復用 ID22 的 application helper 到 `+0x25/+0x26`，同樣有 class/RNG gate、固定 10 HP damage 與 2..5 duration；`ExecuteNativeCommandApplication` 已以 raw duration storage 接 strict non-UI engine slice（gated target 不 mutation，但 successful handler 仍 debit MP/complete actor）。20↔26、21↔27 的 raw clear/apply pair 已閉合；UI/status labels/其餘 engine integration 待。
- [~] **native command IDs10..12 compositor family**：ID10 `0x21527`、ID11 `0x2185F`、ID12 `0x21A9E` 都會進 `0x21548` 的 320×200/640-stride indexed presentation；**修正舊斷言**：其尾端已直接定位 `1CA89→per-target 1C75E`，故 numeric state core 已由 `ExecuteNativeCommandDamage` 支援。`0x2189A/219AD` scroll/composite、專用演出/SFX/UI 仍待，不可從數值共用推論 visual equivalence。
- [x] **scenario native command-mask bridge**：`PartyMember.initial_command_mask` 已接 exact four-byte source，loader 對 malformed length fail-closed；`gen_campaign.py` 從 EXE `character_defaults.json` 依角色 index 合併至 ch01..ch30 而不覆寫既有手工 scenario 欄位。戰後 persistent snapshot 也保留完整五-byte runtime mask，level-up OR 不會跨 town/preparation 消失。ch01 悠妮 `[1,0,0,0]` 有 per-scenario materialization regression；不可由 normalized `Spells` 反造 raw bytes。待：逐章真機 availability 對照、未知 command effect／frame renderer。
- [~] **魔法系統**（資料表與基礎 Cast 已接，native command/effect 尚未閉合）:magic.go(spells.json=EXE dump 36條+normalized spell names;InCastRange/Cast
      固定表值傷害/治療capMax);悠妮火炎/電擊/治療;法術選單→射程紫高亮→施放接戰鬥演出+扣MP。
      待:AoE(range>0)、命中率、輔助系(魔刃/風行…)效果。
      ✅ 法術特效對映已 RE 定論(f8fffba 後,doc37):**不存在獨立法術id→FIGANI對映**——施法演出=施法者
      自己的組×3/×3+1(火花燒在 sprite 幀,`0x28784` 不讀 spell_id)。這僅閉合 FIGANI 手勢選擇；
      `0x2a6bd` command-specific presentation、SFX、命中與多段畫面仍待，現行角色攻擊動畫只是局部 adapter，
      不得稱完整原版一致。
- [~] **商店+祕密商店**: campaign shop 節點與真實 EXE 品項/價格、收件者相容性、兩階段裝備詢問已接線；
      待：賣出、裝備後 AP/DP/HIT/EV 重算、同類舊裝替換、原版祕密商店進入方式 RE(攻略#16 方向鍵位置)
- [x] 存檔/讀檔 ✅(e09c68c):save.go 自有 JSON(節點/旗標/金幣/道具),F5/F9,節點邊界語意

## 第 9 輪 ✅(3-subagent 成本分工;haiku=資料/sonnet=RE·套件/旗艦=架構·驗收)
> 策略(rulebook/45):簡單工作派便宜模型,旗艦只做架構與把關;每件交付先抽驗再 commit。
- [x] **商店品項表**(haiku):docs/data/shops.json 69家/23祕密(含進入方式「酒店前Shift+F1」等);campaign 換真值
- [x] **SFX 破案**(sonnet):FDOTHER#31=14×8bit PCM+AIL 鏈 → doc36;WAV 導出(export_sfx.py,11025Hz 負向證據);
      **index0=游標音確認**(5處方向鍵分支);戰鬥音效=另一獨立池([0x5411f])待導出
- [~] **法術 FIGANI 手勢邊界**：`0x28784` 不讀 spell id，沒有另一段 FIGANI 由 spell id 選擇（火花在角色幀）→ doc37；
      但 `0x2a6bd` command-specific presentation／SFX／命中分支未閉合，remake 角色動畫不可稱完整原版施法演出，
      不結案。
- [~] **歷史 legacy magic snapshot（不可作 native completion claim）**：舊條目所稱「魔法完整版」僅指
      `CastArea` AoE/命中擲骰與 normalized 輔助法術；2026-07-26 已由 SDD56/UI-03 取代為逐 command
      E0 matrix。native target/effect/transaction/presentation 未閉合者維持 fail-closed。
      (魔刃/魔鎧/風行 doc02 明文值)/毒麻封咒行動術/combo;13 單測;引擎:Buff 進 Attack、TickStatus、
      AoE 指空地、FD2_SEED。缺口列冊:風妖精 dmg=0 矛盾、劍技倍率表、傳送 UI
- [x] **全 33 戰場匯出**(haiku):remake/assets/maps/map1-32(96 檔,抽驗 3 圖合法);
      旗艦接線 loadMap(dir)+campaign battle.map 欄位(map3 實測換圖)
- [x] **AI 行走+敵攻我演出**(旗艦):NextAIPlan 決策執行分離+aiStep;atkOwn 欄位按陣營
- [x] **SFX 引擎接入**(旗艦):loadSFX/playSFX+游標/確認/命中掛點(命中暫代,待戰鬥池)
- [ ] 戰鬥音效池([0x5411f] 動態子容器)導出+逐招對照
- [ ] 非 map0 角色 sprite 組匯出(換圖後 fallback 色塊)
- [ ] 33 關 campaign 自動生成(parse_field+劇情+商店串鏈,M4 工具)
- [ ] UI 音效 index 2-0xb 語意畫面實測

## 第 10 輪 ✅(3-subagent 續批:全流程骨架/素材滿覆蓋/戰鬥音效)
- [x] **全 30 章 campaign 生成器**(sonnet):gen_campaign.py→campaign_full.json(183 節點,
      雙重驗證 python+真 campaign.Load;章→map 順序對應依據誠實);旗艦修 resetBattle fallback
      (scenario 空不再錯載 ch01 → roster 全員登場);ch02/map1 實測 33 單位 ✓
- [x] **sprite/頭像滿覆蓋**(haiku):96 組×12 幀 sprite(全 33 圖需求);旗艦補 5 敵方頭像→384 全滿;
      map3 實測全真 sprite
- [x] **戰鬥音效池 RE**(sonnet):FDOTHER #48-53/64/78/88 九候選 42 WAV(七池 sub0 相同=共用
      揮擊音,md5 抽驗 ✓);[0x5411f] 載入點 0x028110(index=招式id→byte陣列動態);
      **位址勘誤:doc36 全篇 0x11fba→0x111ba**(對齊 doc35)
- [x] **全域文字銳利化**(旗艦):font.go per-尺寸 face 快取,所有 Draw 呼叫自動銳利(糊字根因=非整數縮放)
- [x] **BGM 修正(使用者實聽 oracle)**:FDMUS_018=商店(推翻 doc12「戰鬥」推定);戰鬥曲撤下待聽辨
- [x] **派工 SOP 入 rule**:rulebook/45 新節(haiku=資料/sonnet=RE·套件/旗艦=架構·把關;prompt 要素;把關不可省)
- [ ] **每章 scenario stub**(ch2-30「能玩」關鍵):party 延續+deploy_cells+initial_groups 全開
      (gen_campaign 擴充,回合增援事件之後疊)← 下輪首位
- [ ] 戰鬥曲號聽辨(使用者)+ 各 track 逐曲實聽修正 doc12
- [ ] 戰鬥 SFX:index 陣列填值上游、#48-64 逐招對照、remake 接入(atkAnim 命中掛 battle 池)
- [ ] UI 音效 index 2-0xb 語意畫面實測

## 第 11 輪 ✅(campaign 全 30 章能玩 + SFX 收線)
- [x] **ch2-30 scenario stub**(sonnet):29 個 chNN.json(party 4 人/deploy=own_deploy 真資料
      (9 章資源瑕疵 spiral fallback)/groups 全開排除 group==255 padding);campaign_full 30/30
      掛 scenario(含修 ch01 campaign 模式沒主角隊的壞點);三層驗證+3 章實跑
      → **全 30 章一條龍可玩**(FD2_CAMPAIGN=assets/scenarios/campaign_full.json)
- [x] **戰鬥命中音接真素材**(旗艦):battle 池共用揮擊音(#48 sub0)接命中幀;loadWav/playRaw
- [x] **SFX index2 追蹤**(sonnet,部分解出誠實標記):真路徑=0x01cff0 [esp+計數+0xd0](填值待追);
      **意外收穫:0x1c269 從 unit+0x1a 起掃描 5 bytes/40 bits 並輸出 byte index；欄位語意尚未定案**；`+0x22..+0x24` 是另一路 transient modifier flags;
      battle_sfx_map.json 骨架。依「夠用就停」:+0xd0 續追降低優先(共用音已可用)
- [x] 聽辨清單(extracted/music_ogg/聽辨清單.md,待使用者逐曲填)
- [ ] 戰鬥曲/勝利曲聽辨(使用者)
- [ ] party 數值成長/招募(doc28 加入條件)、回合增援事件疊到 stub
- [ ] ch10 等圖少數 tile 雜色查因
- [x] unit+0x1a vs +0x22 offset：constructor trace 已定案為 initial command mask vs transient modifier flags（舊稱 `magic_raw` 已撤回）
- [ ] +0xd0 陣列填值(逐招音效對照,低優先)

## 第 12 輪 ✅(招募成長/劇情文本/編輯器規劃/政策更新)
- [x] **gen_campaign v3**(sonnet):26 角色 21 章招募累積(ch30 全 30 人)+ 成長(HP 真表值,
      AP/DP 近似明標);**增援誠實跳過**(battle_events.json 實為勝負 metadata、
      event_id→group 卡未反組譯 0x22e5c,經 ch01 ground truth 反測拒絕硬湊)→
      docs/data/turn_events.json 真資料 dump + doc26 防誤用註記
- [x] **story 管線**(sonnet):story_to_script.py,ch01-03 精校文本 156 句(speaker 對映 78-85%);
      引擎 story script 載入(旗艦:Node.Script+loadStoryScript,無檔 fallback)
- [x] **著作權政策更新(使用者 2026-07-03)**:FD2 版權過期,**對白文本開放入庫**
      (assets/story/ 例外;ch01.json 恢復原文);圖像/音樂/binary 仍本機
- [x] **tile 雜色結案**(sonnet):非 bug——map9 黑塊紫紋=原版地底裂谷美術;
      全 33 圖 index 零越界、匯出 vs oracle 逐像素 0 差異
- [x] **編輯器規劃**(sonnet)→ `38`:選型=獨立網頁單檔編輯器(File System Access API;
      不做 Ebiten 內建=避免編輯器複雜度混入引擎/不外包 Tiled=劇情事件無對應工具);
      MVP=戰場編輯(產物零轉換直接引擎載入);地基發現:MoveCost 未接地形、
      event.go 實作僅 doc29 願景子集(表單以實作為準+--dump-registry 同步)
- [ ] **戰場編輯器 MVP**:網頁單檔 HTML/JS,tile 繪製+單位擺放+部署格;FSA API 讀寫 assets/maps;
      驗收=引擎零轉換載入(細節 `38`)
- [ ] 劇情編輯器:對白+事件表單+商店(下拉=event.go 現行能力,`38` §3.3)
- [ ] 編輯器能力清單同步:Go --dump-registry
- [ ] campaign 節點圖編輯器(拖線/旗標/敗北路線可視化)
- [x] **地形屬性接線**:地形控制表 per-tile 確認(300~400 格不等,非固定 300;
      `tools/dump_terrain_table.py` → `docs/data/exe_tables/terrain.json`,33 tileset 全 dump)。
      移動代碼(byte1,0-5)語意用 references/text/notes.md 玩家攻略「地形移動力/攻防影響」表
      交叉驗證 AP/DP 數值全吻合(森林 code2/3 = -5%/+10%、沼澤 code4 = -5%/-5%)。
      `tools/export_engine_assets.py` 換算 per-tile 步行成本寫入 map.json `"cost"[]`;
      `battle.State.Cost` + `MoveCost` 查表(`remake/internal/battle/move.go`),`Load()` 自動讀
      units.json 同目錄 map.json 接上(main.go 未改動)。全 33 圖 + 頂層 map0 重新匯出。
      新增 6 個測試(`move_test.go`)。**限制**:僅步行成本,騎兵/飛行差異(notes.md 另有數字)
      待 Unit 加兵種欄位才能接;地形 AP/DP 戰鬥加成本輪未接。
- [ ] **0x22e5c RE**(world-map handler:event_id→group 對應)→ 接回合增援
- [ ] ch04-33 劇情文本精校(30 章,PNG 人眼轉錄;對白已可入庫)
- [ ] 視窗縮放 filter 查證(可能 linear 暈染,tile-debug 提醒)

## 第 13 輪 ✅(增援打通/地形/開場實機裁決/文本流水線)
- [x] **回合增援機制全解**(sonnet):0x51b91 58-entry 跳表(0x22e5c 排除);map0 4/4 ground truth;
      extract_event_id_groups.py;turn_events.json 補 groups
- [x] **gen v4 增援疊入**(sonnet):18 章 35 筆 spawn_group(turn 精確比對=原版語意);
      \$turn_counter 展開(3 圖核對);6 筆 \$reg_or_mem 列冊待解;ch08 T0/T4 實跑增援登場 ✓
- [x] **地形接線**(sonnet):FDSHAP 2N/2N+1 配對地形表(4B:寶箱/移動代碼/**戰鬥背景編號**
      =doc35 地形→BG 對應解!);MoveCost 查表+6 測試;main.go 零改動。騎兵/飛行差異待兵種欄位
- [x] **ch04-08 文本**(sonnet):177 句入庫;speaker 編碼文獻化(0-9,A-V→face_portrait)
- [x] **dosbox 開場實機裁決**(sonnet):logo=縮放進場(使用者記憶證實,推翻 doc23 [驗]);
      開場實為 32.3 秒多幕過場(疑 ANI.DAT 驅動,新缺口);選單座標/硬切閃光轉場
- [x] **title 修正**(旗艦):logozoom phase(紅閃→縮入→白閃)+選單實拍座標
- [x] **ANI.DAT 完整 AFM 格式 RE**(sonnet):9 資源=10-opcode 增量繪圖 VM(palette 4 op+
      framebuffer 6 op,直寫 VGA 0xA0000);173B 標頭+8B 幀記錄,289 幀全解無例外(位元組自洽);
      `tools/decode_ani.py`;9 資源逐一視覺比對 doc23 §2.4③ 分鏡全數命中(守護者/索爾/拔劍/
      騎馬夜行/明月/合照/金鎖);**「2」logo 縮放亦由 ANI.DAT(資源#1)驅動**,更正 doc23 猜測。
      見 doc39。待補:⑥浮空城/⑨惡魔臉未逐幀窮舉、轉場閃光呼叫端排程。
- [ ] 開場配樂曲號實聽驗證(容器 nosound 無法驗;使用者聽辨)
- [ ] ch21/22 \$reg_or_mem 增援 eax 來源 RE(6 筆)
- [ ] ch09-33 文本(批次進行中:09-13 執行中)

## 第 14 輪 ✅(AFM 完全破解+開場過場端到端+文本過半)
- [x] **AFM 格式完全破解**(sonnet):10-opcode 增量繪圖 VM(Lo Yuan Tsung 1993);
      派發 0x36c9e/跳表 0x5276a/framebuffer=VGA 0xA0000;289 幀(9 資源)逐位元組驗證;
      decode_ani.py;視覺全命中 dosbox 分鏡(屠龍/logo/金鎖…)→ doc39
- [x] **Go AFM VM 移植+開場接入**(旗艦):internal/afm(容器+VM);執行期解玩家 ANI.DAT
      (不夾帶版權幀);title cutscene 9 幕串接進選單;afm_test 驗幀數 96/51/35;
      無 ANI.DAT 退回 FDOTHER 捲動 fallback
- [x] **AFM 播放器排程 RE**(sonnet):play_afm(index,delayMs,skippable);毫秒校準 0x3dc9f;
      5 呼叫點釘死(開場 3/4/5/6/7/8/0/1,delay 90-15ms;idx0/2=章節過場非開場);
      title.go 換真值排程(拿掉月亮 idx2、各幕 delay、skippable 旗標)
- [x] **ch14-18 文本**(sonnet):229 句;ch01-18 累計 747 句;ch18 永久劇情死亡標記
- [x] **0x1f73f FDOTHER 靜態幕 RE**(sonnet):開場 2 幕靜態=①守護者(#100+pal#99,esi=0x1c2)
      +⑥滿月浮空城(#75+pal#76,esi=0x0a,dosbox frame168-173 逐像素吻合);機制 memset黑→
      載調色盤→blit→淡入→BIOS tick 忙等(修正原 KB「BGM/SFX」誤判);⑨惡魔臉排除是 0x1f73f(待下輪)
- [x] **開場過場插 2 靜態幕**(旗艦):cutScript AFM+static 交錯腳本;frame165 守護者/frame645 浮空城驗證
- [x] **全 33 章劇情文本完成**(sonnet 流水線 6 批):ch01-33 共 1452 句;
      speaker 場景本地表現象文獻化;身世真相(悠妮=ASR-07/大魔王=ASR-06)
- [x] **speaker→頭像機制 RE**(sonnet):0xFFEF operand→0x12C60 查[0x53A45]/[0x53BF7] byte[+7]=DATO;
      三推論裁決(①部分成立=陣列重填+雙定址②怪物表不成立③字母碼是 render_story.py operand 洩漏 bug);
      **story JSON 零修改**(現行最忠實);修 render_story.py operand-skip;doc14 修正
- [ ] **開場配樂曲號 RE**(bgm-title 執行中):play_bgm 開場鏈曲號→FDMUS 檔(取代猜測 FDMUS_004)
- [ ] 開場分鏡⑨惡魔臉來源 RE(疑另一機制或 ANI.DAT)
- [ ] ch21/22 \$reg_or_mem 增援 eax 來源 RE(6 筆)
- [ ] 待展開(位址已釘):0x3453E 額外檢查、tag==0x27 sentinel、[0x53BF7] 表用途

## ⚠ 誠實揭露:全 33 章劇情文本「轉錄完成但從未接進遊戲」(2026-07-03 使用者質疑後查證)

**症狀**:remake 每章開場只顯示 2 句佔位(「第N章:.../目標:...」),1452 句真對白全沒播。
**查證**:campaign_full.json 的 **83 個 story 節點,`script` 欄全部是空的**(0/83 接真對白檔),
而 `assets/story/ch01~33.json` 的 33 章 1452 句轉錄**全都在、全躺著沒用**。
**根因**:各自完成、接線沒人做——
- 「全 33 章文本完成」(story 流水線 6 批)✓ 真的轉錄好了
- 「全 30 章可玩 / campaign 183 節點」(gen_campaign)✓ 節點生成了
- **但 gen_campaign 生成 story 節點時從沒接 `script` 欄** → 兩者從未連起來 ✗
**教訓**:子系統各自報「完成」不等於整合完成;跨模組「接線」要獨立驗(truth-in-code,
配 rulebook/63)。使用者實玩才揭露——沒實玩/沒查,文件會一直顯示「完成」。
**修法**:story_chNN 節點加 `script:assets/story/chNN.json`;gen_campaign 修+重生成 → 全章接通。
- [x] ch01 開場三幕(王城父子/草地悠妮蓋亞/遇海盜)手動接線+轉錄 FDTXT_033/032(intro-scenes)
- [x] **ch01 開場三幕背景圖 RE+接線**(使用者實測發現對白疊在戰場地圖上,非王座廳/草地,2026-07-04):
      RE 修正 doc23 §4 誤記(「FDTXT 序幕『影像』資源」不存在,FDTXT 純文字)——真正背景是
      **暫借章節 32 時 `0x1088d` 順帶載的 FDFIELD 組32(資源96/97/98)= 18×51 複合地圖**(王座廳→長廊→
      草地),與戰場同一 tile 渲染器;已渲染驗證(`extracted/maps/map32.png`)逐像素對齊 dosbox 參考圖
      + 使用者原版錄影。序幕尾端 `[0x53c03]=0` 還原真章節,「遇海盜」對白疊在**真戰場地圖 map0**(非另一
      張圖)。remake 加 `campaign.Node.Map/CamX/CamY`(story 節點固定鏡頭背景圖)+ `main.go` `storyBG` 模式
      (鏡頭不跟游標、不畫單位/游標/HUD);`campaign_full.json` 三節點接線(palace/meadow→map32,
      pirate→map0)。截圖驗證王城幕=雙王座紅毯廳(對照 orig_02_dialog_02_king.png)。
      **教訓**:另一 agent 曾提案「背景已在 BG_BG_\*.png,只需配對」,經抽樣檢視(320×100 全景走廊,
      無王座/紅毯任何痕跡)證偽——套用前先驗證,不可盲信「已抽出」的斷言(rulebook 62)。
      另踩雷:`~/.local/share/fd2_re/assets/`(玩家/測試用資產覆蓋目錄,`assetPath()` 優先讀它)有舊版
      campaign_full.json 快取(缺 ch00_palace/meadow 分幕),測試前先同步 repo 最新版才看得到真結果
      (使用者已驗收+ commit;team-lead 另修 play.sh 每次啟動先清 XDG scenarios/story 影子,一勞永逸)。
- [x] **王座廳 NPC 擺位**(使用者驗收背景後指出「王座是空的、索爾沒出現」,2026-07-04):RE 出 FDFIELD 組32
      出場位置段(資源98)直帶場景 NPC 座標+肖像,同戰場單位 roster 格式;**國王 portrait48@(7,5)+
      王后 portrait66@(10,5)** 頭像圖核對(`DATO_048/066_m0.png`=戴冠鬍鬚男/紫髮女)完全對上
      `f_006.png` 左王/右后。索爾在該格出場位置表無對應項(原版走 0x3231b 內 `push1/3/5;call 0x10b4e`
      另一條登場路徑,未逐一 RE),故索爾位置(fig0 @(8,8) dir2)是目視 f_006 定位、非 FDFIELD 直讀,
      已在 doc23/campaign_full.json 誠實標記。remake 加 `campaign.Actor{Fig,X,Y,Dir}`+`Node.Actors`
      (story+Map 節點靜態擺位,複用 battle.Unit/drawUnitSprite 畫法、無戰鬥邏輯),`story_ch01_palace`
      接 3 actor。截圖對照 f_006 吻合(國王/王后坐正確王座、索爾紅毯中央背對鏡頭)。
      **順帶發現**(未實作,留給 ch02-33 接線時參考):同一出場位置表在草地段(row42/46/47)另有
      portrait0×2(索爾+疑似另一己方角色)+portrait4(亞雷斯)+16 個 portrait68/69 走廊守衛,
      可比照本次做法補草地/走廊 NPC。
- [x] **ch01 開戰隊形 deploy_cells 核對**(使用者指出「索爾隊伍站位都是錯的」,2026-07-04):
      格子座標本身(FDFIELD `own_deploy` 直讀)已驗證正確,問題出在**逐人分配順序**——用 fig sprite
      外觀(fig4=藍盔=亞雷斯/fig9=紅髮=悠妮/fig30=機甲=蓋亞)逐一核對 `orig_03_battle_start.png`/
      `f_029.png`,發現影片是「索爾+亞雷斯緊鄰、悠妮稍右、蓋亞最右」,但 `ch01.json` 原
      `deploy_cells` 陣列順序配上 `party` 順序會把亞雷斯/悠妮的格子配反。交換
      `deploy_cells[1]`/`[2]` 修正,隔離 Xvfb + xdotool 送 Enter 清對白後截圖(before/after 對照)
      確認吻合。**除錯插曲**:FD2_SHOT_CUR 測試一度看似「怎麼設都沒用」,查出是地圖只有 24 格高
      (576px)但視窗 400px,camY clamp 上限只有 176,導致 curY=20/21.5/23 全部 clamp 到同一個畫面
      (誤判無效);換更小的 curY(如 15)才看出真的有作用——clamp 邊界會讓「看似無效的截圖測試」
      其實只是撞到同一個 clamp 上限,不是機制真的沒用,下次遇到「怎麼測都一樣」先檢查 clamp 範圍。
      → doc44 §2.5 定案(信心分級:格子=FDFIELD 直讀高信心,逐人配對=影片外觀反推中高信心非鐵證)。
- [ ] ch02-33 全章 story 節點接 script(gen_campaign 修+重生成)— 等 ch01 落地後做
- [~] ch02-33 全章 story fallback：runtime 對精確 `story_chNN` generic node 自動掛 `assets/story/chNN.json`，讓已匯出的可編輯完整劇本取代節點短 fallback lines；named/pre/post cutscene 不套用此 heuristic，避免重播整章。ch02/03 handler 仍待逐段 beats 接線。
- 🟡 **ch01 開場 Phase 2 實作(doc46 D1-D6,2026-07-04,待使用者驗收才打勾)**:使用者三輪回報後
      team-lead 先做「原版開場逐幕時間軸」(doc46)才動手,這輪照時間軸把 D1-D6 全部實作:
      **D1/D2 背景重構**:`story_ch01_palace` 拆成 `story_ch01_palace_throne`(map32 王座廳)+
      `story_ch01_palace_path`(map32 草地小徑,原「meadow」節點誤用棚)兩幕,`story_ch01_meadow`
      **改名為 `story_ch01_forest_duel`+`story_ch01_forest_discover`,背景從 map32 改指 map31 密林**
      (先前張冠李戴的核心 bug);map31 actor 用 FDFIELD roster 直讀(索爾19,46/亞雷斯19,47/
      蓋亞5,43/悠妮5,44);`portrait75` 是商店店員 NPC，不在 00-41 可入隊角色範圍，**未擺放**。
      **D4 行軍蒙太奇**:新增 `story_ch01_march`(map0,無對白,`auto_advance`
      180 幀自動轉場,索爾走位代表隊伍,簡化版,doc 誠實標「近似非逐幀重現」)。
      **D5 分段播放(核心)**:`campaign.Node` 加 `Scene` 欄(只取 Script 檔 `scenes[]` 裡 label
      對映的那一段,不再攤平全部劇本);改「每段一個 story 節點」而非 Node 內 sub-scenes,
      保留 `FD2_CAMP_NODE` 可跳任一幕驗證。**D6 走位動畫**:`campaign.Actor` 加
      `FromX/FromY/WalkFrames`(進場走位,重用 `battle.Unit.OffX/OffY` 插值)、`Node.ExitWalk`
      (退場走位,索爾沿紅毯走下場~1.5s);新增泛用**淡出/淡入轉場**(`storyFade`,0.6s/次,
      story 節點間一律套用,不再硬切)。**除錯插曲**:forest_duel 一度以為亞雷斯(fig4)沒畫出來,
      加 debug 座標印字才確認兩個 actor 都在正確位置、只是 FDFIELD 給的座標剛好只差 1 格(y46/47)
      造成兩張 24×24 sprite 緊貼——不是 bug,是資料本身就這麼緊,已移除 debug 印字。
      驗證:每幕獨立截圖 + 相鄰幕轉場(throne→path 含退場走位+淡出淡入全程截圖)+
      discover 幕走位動畫三階段截圖(進場遠/中/抵達)+ march 幕靜默→自動轉場→抵達海島全程截圖,
      build+test 綠、gofmt 乾淨。**D8(戰前 MAP/TURN 資訊畫面+行軍確認 UI)不在本輪範圍,已登記獨立項**。
      → doc25 §7.5.1 已修正範圍(戰場進場直接定位仍成立;cutscene 幕內走位是另一機制,已推翻舊結論)。
- [~] **D8:戰前 UI**(doc46 附帶發現):Docker/Capstone 已釘 `0x1a30b` battle-entry choreography：
      `0x1f1cc(0x52)`→20ms→`0x1f30a(0x52)`、64000-byte indexed surface；`0x1f42d` 已釘為
      LMI1 entry #0x52 的雙側五幀 slide-in/restore（x=85−offset、165+offset；offset=100..0）、
      後續 `0x1a813/0x1a866` dispatch；`0x15f0e` frame ABI 亦已釘為 offset-table + RLE
      decode + stride blit；`[0x53a81]` 已由既有 loader trace 對位為 `FDOTHER.DAT#5`
      的 `LMI1`，remake `fdother.ParseLMI1`／`LMI1Entry.BlitAt`（透明 preserve + mirror）
      與 player-asset regression 已補（#0x52=72×14；directory offset 不是 RLE 結尾）。
      證實不是 `resetBattle` 直接跳過的空白階段。仍待釘死
      MAP/TURN/ENEMY/FRIEND/NPC 欄位與 YES/NO input 的資源／字串 ABI，再做 remake shell 與截圖，
      不把 resource `0x52` 或 `0x51e81` 猜成畫面名稱。

## 待辦:實測回饋(使用者 playtest,2026-07-03)
- [ ] **開場過場節奏 3x 太快 RE**(dragon-fx2 DOS 對比發現,doc39 §10.8):原版魔王立繪捲動
      (esi535→0)貫穿全開場、與各 AFM 幕交錯(暫停播幕→續捲),貢獻 ~16s 延遲;remake 把捲動
      搬到最後單播→開場 5s vs 原版 14.7s。修需先補 0x11eb0/0x1f894 逐指令(捲動如何在 AFM
      直寫 framebuffer 後接回)。使用者已 OK 開頭閃光(#9),此為獨立節奏落差,低優先
- [x] **序章劇本 staging 機制 RE**(使用者指出 #3=劇本機制沒 RE 完整,2026-07-03 反組譯+dosbox 220+ 張連拍
      複驗收尾)→ **定論:主角隊直接定位,原版無行軍動畫**。0x3231b 本體只有直接 spawn(`0x10b4e`)+
      攝影機平移 reveal(`0x13185`/`0x32999`,鏡頭動非單位動)兩種登場原語,dosbox 全程重跑序章開場
      未見任何單位行走動畫或世界地圖段落;玩家記憶「走到地圖中央」疑與攝影機平移視覺效果混淆。
      remake 現行 focusOnParty(純鏡頭對準)+ spawn_party(直接定位)已忠實,#3 非 bug,不需補行軍動畫。
      → `docs/knowledge-base/25-battle-event-system.md` §7.5.1
- [~] **playtest 8 項修正**(playfix agent 執行中,#7=我 kill 誤殺非 bug 已排除):
      #1 方向鍵按住持續移動、#2 預設沒開場動畫、#4 移動後 ESC 取消退回、
      #5 action overlay／command grid 的原版 side-by-side 視覺對照、#6 地圖狀態欄還原原版、#8 單位走完轉回正面朝向
      → **batch1 已 commit(0f32d25)**;#7 非 bug(kill 誤殺);#3 部分(鏡頭對準部隊)
- [ ] **#9 法術特效時序**(待使用者釐清):playfix 靜態審查=攻擊系法術路徑乾淨無殘留;
      真根因疑「治療系法術 target=1 無全螢幕演出(只文字)」→ 打治療咒後緊接敵方攻擊演出,
      被誤認成法術效果延遲出現。修法需先 RE 原版治療咒視覺(閃光/數字浮現/僅改血條),
      或使用者釐清實際現象,不瞎編視覺
- [x] **序章場景轉換打通**(2026-07-04,使用者驗收 OK,commit 2c5adda):王座廳/草地/遇海盜改用
      真 tile 地圖背景(map32/map0)+ 固定鏡頭,非戰鬥圖。RE 定論:0x3231b 暫借章節32 載 FDFIELD
      組32(紅毯雙王座→長廊→草地縱向拼接),與戰場共用 tile 渲染器。story.Node 加 Map+CamX/CamY,
      main.go 加 storyBG 鎖鏡頭/擋游標。→ `23-boot-title-and-scenario-flow.md` §4
- [x] **援軍 stale-cache bug 根因修復**(2026-07-04,使用者報「援軍不該一開始出現在地圖上」):
      根因非 code bug——`~/.local/share/fd2_re/assets/scenarios/ch01.json` 是舊版 `initial_groups=[1,2,10,11]`,
      XDG 快取層優先蓋掉 repo 已修正的 `[1,2]` → group 10/11 開場即 OnField=true 出現。**治本**:XDG 是給
      版權衍生素材(sprites/maps/music)+ 玩家編輯版覆蓋用,scenarios/story 是原創內容不該進 XDG;已刪 XDG
      scenarios/story 影子 + play.sh 每次啟動先清,dev 一律以 repo 為真相。→ 記憶 `fd2-intro-cutscene-bg-and-userdata-cache`
- [x] **過場腳本機制第一性原理解答(doc47)**(2026-07-04,使用者問「RE 為何沒還原 staging」,旗艦親做):
      方案 b 證偽=FDTXT 純對話碼無 staging;方案 a=序章 handler 0x3231b 逐 beat 全轉錄。
      原語翻新:0x135dd=平滑鏡頭平移、0x15f84=對白播放器(doc23 舊判「逐格貼圖」誤)、
      0x1366a=演出(acting)播放器（direct bank 格式與 106 筆資源已解出；normal=逐格搬移、
      special=原地 pose，zero-special 保留三 tick 時序）、0x112a5=入隊(0/9/4/30)。
      重大:王城→草地=同 map32 鏡頭平移轉場非淡出換景;對白與演出逐條交錯;海島幕 3 個平移點。
      → remake 修正指示 doc47 §4；尚待逐章把 direct acting 資源接入可編輯 cutscene 節點，
      並以實機截圖核對 renderer/presentation 差異（不猜測性補 handler 語意）。
- [~] **王座廳 NPC 擺位**(cutscene-bg 執行中):國王/王后坐王座 + 索爾站紅毯中央,對照 f_006.png;
      story 節點加 actor 擺位欄。RE 查 FDFIELD 組32 是否帶 NPC roster(sprite id/cell 直接來自原版)
- [x] **ch21/ch22 pre-handler**：FDTXT_022 index0（11句）與 map21/70-slot、pan(16,28)、acting67 已接 editable binding；`story_ch22` 已接回原版 pre-handler，compiler/campaign/battle regression 通過。
- [x] **外部資源／城鎮流程交叉盤點**：公開資料確認 `FDFIELD.DAT` 是可替換的外部場景層，且章節間存在 preparation、商店、教會、存讀檔流程；後續以 DAT provider + battle→town/prep graph 實作，未將網路資料當 binary 格式硬證據。
- [ ] **社群行為 oracle 對照**：逐項把 FD2.EXE 修改表中的入隊、隨時存檔、等級上限、寶箱持久化轉成可編輯規則與 regression；先挑 save/chest 兩項和目前 persistent flow 最相關者。
- [~] **ch22_pre control-flow**：固定 16-slot deactivate loop、`0x11df2` immediate `palette_update` 已 lower 並通過 regression；尚待實作 `0x24618` 的 9-frame transition/reveal renderer（非普通 fade），完成後再接 `story_ch23` binding。
- [x] **ch23/ch24 pre-handler**：FDTXT_024 index0/index1（14句）與 map23/70-slot、spawn group1、四段鏡頭已接 binding；`story_ch24` 已接回原版 pre-handler，compiler/campaign/battle regression 通過。
- [~] **ch24/ch25 pre-handler**：`0x24b4d` 四段 transition count 已 lower 為 `transition_reveal`（20/20/20/60、20ms/frame），FDOTHER#88 sub1 四次 SFX、index=-1 stop、handle release 已接，FDTXT_025 跨 scene 對白已接 `story_ch25`；尚待 indexed double-buffer visual adapter。
- [~] **ch25/ch26 pre-handler**：FDTXT_026 string0 已以 direct scene0 12-line mapping 接 binding（map25/70-slot、pan、acting76），`story_ch26` 已接回 handler；後續分支字串因 authored/raw count mismatch，需先 RE 條件控制流再接，不猜全章順序。
- [~] **ch26/ch27 pre-handler**：FDTXT_027 idx0/3/4/5/6/7 已高信心對到 ch27 scene0 全部 21 句，新增六組 editable direct overrides 並接 `story_ch27`；`0x24b14` item `0x64` gate 與 0x24618 視覺 effects 尚未接 runtime，不能視為完整章節流程完成。
- [x] **ch27 post/ch28 flow**：FDTXT_028 string7 已精確對到 ch28 scene1 lines 11–15，新增 post-handler binding 並接 `story_ch28`；sync_party/set_chapter 保留，下一節仍進可編輯 preparation_ch28。
- [x] **ch28/ch29 pre-handler**：Docker 隔離 Capstone 實際解析 `0x35822(x,y,group)` 的 pan→spawn→300ms→兩次 palette no-op／200ms→redraw choreography；compiler 已 lower，FDTXT_029 idx7/idx8、map27/pan/acting86 binding 通過 regression，`story_ch28` 已接回 editable handler。
- [~] **ch26 post item-gate branch**：`0x25186→0x24b14(0x64)` 是前 16 個 runtime slots 的 exact inventory search，無 camp/activity filter；成功臂無 `0x1b8e7`，天空之鑰不消耗，之後才 sync→chapter increment→persistent cleanup。FDTXT_027 idx8–12 / idx13–16 對應兩臂；仍需把 visual/effect calls 與缺匙 editable branch 資料化，不能只保留 generic ending。
- [x] **ch26 success palette-ramp lowering**：Docker Capstone 定義 `0x25052(start,delay)` 為 inclusive `delta=start..0` 的 `0x11df2(0,255,delta)`＋每步 delay；compiler 已 lower immediate start 0..63。synthetic descending/zero/invalid 與真實 `ch26_post.json` 六個 5/4/3/2、80ms calls 均有 regression。這是 palette ramp，不是 generic fade；`0x24618` 與其他 renderer effects 仍 fail-closed。
- [x] **撤回 `0x1f882`=vsync/sync helper**：Docker Capstone 展開 `ebx=0..63`、每次 `0x11d40(0,255,ebx)`＋2ms wait，故是 64-step native palette fade-out。compiler 現保留 exact `native_palette_fade_out(0..63,2ms)` payload；它與 `0x25052/0x11df2` 的 delta ramp 不同，runtime 在 indexed DAC adapter 未完成前有 regression-protected fail-closed。
- [x] **native palette pulse (`0x35e5a`)**：Docker Capstone 完整 body 固定 `0x11df2(0,255,delta)` 的 inclusive 0→63（8ms/step）、400ms hold、再 62→0（8ms/step）。compiler 以 exact editable `native_palette_pulse` payload 保存不對稱端點，並拒絕帶參數變體；runtime 在 indexed DAC adapter 未完成前 regression-protected fail-closed，不以 story fade／delay 偽造。官方 IDA xref export 亦已納入此 helper 與 `0x33f78` staging wrapper。
- [x] **ch29 staging wrapper (`0x33f78`)**：Capstone stack trace 與官方 IDA function/xref 共同固定 raw push-order `[y,x,slot]`→`0x12cea(slot,x)`→`0x22253(slot,x,y,x,y)`；compiler 將七個 ch29 pre call-sites 保存成 `native_staging_present`，含 source regression。因 `0x22253` 的 indexed 11+6+10 presentation adapter 未完成，runtime 明確 fail-closed，禁止誤 lower 成 spawn／position／pan。
- [~] **ch29 post staged mapping**：四組對白已精確接到 ch29/ch30 authored lines；`0x12cea` focus、`0x25089` persistent cleanup、`0x17aa9` tick、dynamic palette loop 與 terminal `loadch` 均已 lower 並各有後述 regression。`0x24618` 仍只保存 complete metadata，`0x2bce5` 仍是專用 ending renderer；兩者未完成前整支 handler 不接 campaign runtime。
- [~] **ch29 post focus lowering**：`0x12cea` 已安全 lower 成 tile-step pan(22,23) 並通過 regression；其餘 native cleanup/transition/ending 仍待 lower。
- [~] **ch29 post persistent cleanup**：`0x25089` 已 lower 為 editable `reset_persistent_roster_state`，並以 runtime/campaign regression 鎖定清 transient、回填 MaxHP/MaxMP；0x24618 transition、0x2bce5 ending renderer 仍待。
- [~] **ch29 post tick wait**：`0x17aa9(1)` 已 lower 成一個 editable delay tick 並通過 compiler regression；仍待 0x24618 indexed transition 與 0x2bce5 ending renderer。
- [~] **ch29 post dynamic palette loop**：`0x11df2(EBX,255,0)` 已依 direct 0x3e→0 loop materialize 成 63 組 palette/delay beats 並通過 regression；`load_ch_text` 的舊說法已由完整 `loadch` 取代。仍待的只有已列出的 `0x24618` indexed adapter 與專用 ending renderer。
- [~] **ch29 post terminal handler**：`0x25870 → 0x1088d` 不是純文字載入：它會載 FDTXT/FDFIELD、重建 unit buffer、從 persistent roster 複製 records、寫 map29 deployment 並 spawn groups。現已 lower 為完整 editable `loadch`（chapter30/map29/roster70/ch30 story+scenario），而非 `load_ch_text`；`0x112a5` 已證實 persistent records 依 JOIN 呼叫 append，因此正常遊戲 slot order 可用 `partyJoinOrder` 表示。layout、動態 pan、0x24618 indexed adapter、`0x2bce5` renderer 仍未完成，故整支 handler 維持 fail-closed。`0x25970 → 0x2bce5` 返回後是 self-loop，這是 internal ch29／map29 最終戰的終局路徑，**不是** map28 戰後可接 `preparation_ch30` 的 handler。現行 final battle→generic ending 暫略過它；完成後以 terminal node 接入。
- [x] **ch29 post layout data**：`0x257b4 → 0x233c6` 的 20 slots X/Y/pose 與 camera `(16,18)` 已存入 editable binding，並有 compiler regression；`0x112a5` 已補證 persistent ordinal=JOIN chronology。整支終局 handler 尚未接 campaign（0x24618/ending renderer 等仍 fail-closed），不表示終局已可播放。
- [x] **ch29 post final pan**：`0x25937 → 0x135dd(11,12)` 已依 X-first/Y-second native ABI lower 為 tile-step `(264,288)`，compiler regression 通過；終局 transition/renderer 仍待。
- [~] **0x24618 indexed transition metadata**：已保存 tile/radial-radius/frame/timing 與 32-step 全 palette brightness ramp（delta 0→62, step2）之 editable schema、binding resolver/compiler regression；descriptor/double-buffer PNG adapter 尚未完成，故仍 fail-closed。
- [x] **ch29 final 0x24618 arguments**：依 layout→focus 的 native scroll-offset writes，`0x25848` dynamic args 已定案為 tile `(6,6)`、radial radius `(10,step8)`，並寫入 binding/compiler regression；真正 indexed descriptor/double-buffer adapter 尚待，整支 handler 繼續 fail-closed。
- [~] **0x24618 pass-range metadata**：`0x22046` 的固定最後兩參數是 row range `[start_y,end_y)=[0,0xc0)`，不是 source_y 或 blit width；另保留 clip 0x138×0xc0 與 radial-radius step。仍待以 `0x53a6d` LUT bank 和 `0x219ad` row clip 建立真正 indexed adapter。
- [~] **ch29 post persistent roster cleanup**：`0x25089` 已實作獨立 `reset_persistent_roster_state` compiler/runtime beat（清 transient、MaxHP/MaxMP 回填），避免誤併入 `sync_party`；需補 binding、測試並接到正確 town/shop/preparation 節點。
- [~] **ch29 pre native unit presentation**：舊「6×(render+present+10ms)+2 ticks」結論已撤回。完整 `0x22253` trace 是前段 `0x22470` 11 次 LMI present/tick、中央 `0x22547` 6 次 10ms remap present+2 ticks、後段 `0x22656` 10 次 remap present/tick，合計 27 次 present；既有 `unit_present` metadata 不完整，維持 fail-closed。
- [x] **`0x22253` machine-readable schedule boundary**：`fdother.NativeUnitPresentSchedule` 現嚴格保存三段 11+6+10 的 27 個 present：FDOTHER#6 entries `0x72..0x7c`（各1 tick）、FDOTHER#3 entries `5..0`（各10ms，最後才2 ticks）、#3 entries `0..9`（各1 tick）。regression 拒絕舊 six-frame shortcut 或把兩 ticks 移位；這仍不是 geometry/buffer/Ebiten renderer adapter。
- [x] **`0x22470` first-phase destination ABI**：direct arithmetic 已保存為 `NativeUnitPresentByteOrigin(x,y,camX,camY)=0x8088+24*(x-camX)+24*456*(y-camY)+456`。它是 456-stride indexed work-buffer byte offset，最後 `+456` 不可漏；raw helper 保留 offscreen signed result，clip 仍屬 caller/renderer boundary。LMI decoder／unit-layer/present adapter 尚待組合。
- [x] **`0x22470→0x4e85b` LMI write primitive**：`0x4e85b` 逐像素透過 `0x4e916` decode，僅非零寫 destination，等同既有 `LMI1Entry.BlitAt` 的 preserve-zero 規則。`BlitNativeUnitPresentLMI` 已將 #6 cell 與 verified byte origin 組合，對 offscreen origin fail-closed；其後 unit redraw/present/tick 與其餘 phase 仍待 adapter。
- [x] **`0x22470` eleven-pass intro executor**：`RunNativeUnitPresentLMIIntro` 固定走 #6 entries `0x72..0x7c`，每一 entry blit 後強制要求 caller 執行一次 redraw/present/tick callback；不得折疊為一張最終畫面。short table／nil callback 均 fail-closed。尚未接 GUI renderer。
- [x] **`0x22547` LUT-contract radius helper**：`NativeUnitPresentContractRadius(raw53ABD,lut)=trunc((24*raw53ABD+15)/5)*lut`，只收 native LUT index 0..5 並 regression。`raw53ABD` 保持 native-global 名稱，不把未閉合語意猜成 tile/actor。
- [~] **ch29 post BIOS tick wait**：`0x17aa9` 已證實讀 DOS BIOS tick（約54.9ms），lower 為每 tick 3 個 remake frames 並通過 compiler regression；若要逐毫秒重現，需在 runtime 加 BIOS-tick clock adapter。
- [~] **native `0x22253` renderer adapter**：已釘死 `0x22547→0x22046` indexed off-screen blit 呼叫鏈。2026-07-26 stack-slot recheck：FDOTHER #81 的 nested `LLLLLL` allocation 只存 local、尾端 free，未傳 renderer callees，故不再叫它 frame/pixel source；`0x11eee` 只做背景/tile redraw。真正已見資料是 boot `0x111ba(FDOTHER,#3)`→descriptor base `0x53a6d`（`0x22547` 倒序 entries 5→0）與 FDOTHER#6 `LMI1` bank：230 entries，`0x22470` entries 0x72..0x7c（12×21、九個20×22、24×23），`+0x1f6`=entry0x7c。**修正舊斷言**：`0x22046` 有六個靜態 caller，不是 unit-present 專屬；它只**兩次**呼 `0x219ad`，後者逐 row 用 `sqrt(radius²-dy²)*scale/10` 求 clip span，再以 remap LUT in-place map pixels，之後 `0x22046` 自己對另一矩形範圍作同 LUT remap。`__CHP` 已釘死為 toward-zero；`fdother.ApplyRadialLUTRemap` 與 `ApplyCenteredRectLUTRemap` 都有 boundary／clip／256-byte LUT regression。**原本的中間 redraw 已證實會 mutation**：`0x127a9→0x127e0` 依 camera-relative object sprites 經 `0x4deda/0x4de56` 寫 `0x53a49`，不可合併兩 radial passes 或省略。個別 caller 視覺語意、descriptor/buffer adapter、Ebiten adapter 仍缺，`unit_present` 暫維持 fail-closed。
- [~] **chapter ending renderer (`0x2bce5`)**：已釘死 FDOTHER `#0x36`（十進位54）、320×200 雙 buffer、palette 0→63/4ms、2000ms hold、chapter26/29 分支文字與 fade-out；仍缺 ANI/FDOTHER compositing adapter，禁止把它吞成 generic ending。

- [~] **shared object redraw compositor**：`0x127a9` 的 `0x127e0` 不是單純 loop bookkeeping：active roster entry 以 camera-relative placement 選 24×24 descriptor，走 `0x4deda` raw indexed-RLE 或 `0x4de56` palette-band-RLE 寫 `0x53a49`；尾端 `0x129ec` 又在同 buffer 疊 map/object layer。`+5 bit7` clear→raw、set→band 已由 direct branch 關閉。`BlitNativeUnitLayer` 現以 raw slot／pose／movement／base-frame／active gate、camera bounds、cycles 及 pixel shift 完整表達 steady unit layer，且 preflight 失敗不寫半張 frame；它不接 GUI。`0x53a61` 是 global raw-key cache 的 pointer blocks，runtime index 是回傳 `slot×12 + pose×3 + cycle`，而非角色 group。仍待將 terrain→range→unit→foreground→HUD→viewport copy 組成 caller adapter；在此之前不得把 `0x22046` passes 或 `unit_present` 接成 native UI。
- [x] **`0x11cac` range-layer provenance**：Docker Capstone 釘住 redraw order 為 `0x11eee terrain → 0x122dc range overlay → 0x127a9 unit+foreground → 0x1acf3 HUD → 0x11eb0 viewport copy`。`0x122dc` 依 raw `[0x51a83]` mode 1..6 展開固定 offset/descriptor calls 到 `0x126f7`；後者 camera-bound 後以 `0x4deda` 直接寫 `buffer+0x8088`。range mode table／descriptor bank 尚待資料化，不能以 GUI highlight 冒充。
- [x] **`0x122dc` range call-table／asset closure**：Docker Capstone 完整直讀 modes 1..5，`fdother.NativeRangeOverlayPlacements` 保留原始 call order 的 1/1/5/13/21 個 `(x,y,descriptor)`；特別固定 mode3 centre=`#14`、mode5 的重複座標／不同 descriptor，禁止圖形化 normalize。`0x25c7d..0x25c92` 已證明 `FDOTHER#1→0x53a4d`；實檔 header 是 20-entry 24×24 four-mode-RLE bank，`0x126f7` 以 `base+6+4*descriptor` 選 #0..18 後 `0x4deda`。`DecodeNativeRangeOverlayBank`／`BlitNativeRangeOverlay` 以真實 resource regression 固定 456 stride、0x8088、camera clip 和 preflight。mode6 不呼 `0x126f7`，而是算 `4*(x+y*raw53ac1)+7` 後清 `[0x53a51]` 指向資料的一個 byte；drawable API 明確拒絕 mode6。仍待 native buffer/grid lifetime 與 runtime/Ebiten adapter。
- [x] **`0x122dc` mode6 raw-field closure**：`0x108f0..0x10932` 載 FDFIELD composition 至 `0x53a51`、讀 signed `u16 width/height`；`0x4dbfc` 由 header 後的 4-byte cells 逐筆將 byte+3 初始化為`0xff`，再對 byte+2 mask `0x1f`。所以 mode6 的 `4*(x+y*width)+7` 正是 selected cell byte+3（event-high／raw blit-mode byte），不是 overlay sprite 或抽象 grid。`ClearNativeRangeOverlayMode6FieldByte` 有 bounds/no-partial-mutation regression；不替清零後的 renderer/gameplay效果命名。
- [x] **steady native indexed map-frame scheduler**：新增 `internal/indexedmap.ComposeFrame`，強制順序 `0x11eee terrain → 0x122dc range → 0x127a9 unit → 0x129ec foreground → HUD callback → 0x11eb0` 320×192 copy。HUD callback 缺失即拒絕，private work clone 讓任一 layer/HUD 失敗不污染 caller 的 work/VGA；regression 固定 foreground 在 HUD 前、HUD byte 必進 viewport。這是純 indexed compositor，不等同 Ebiten UI／DAC／timing closure。
- [x] **native map HUD panel subpass**：`indexedmap.BlitNativeMapHUDPanel` 直接接 `0x1acf3` 已證實的雙 raw gate、FDOTHER#5 LMI1 #130（69×34）、`stride*157+anchorX`；entry geometry 不符即拒絕且不寫 destination。**撤回**把它當一般 LMI1 cell 的實作：#130/#0x83/#0x84 必走 `ParseLMI1FrameEntry→0x4e63d` four-mode `Frame`，`DecodeNativeMapHUDFrames` 已以真實 FDOTHER regression 固定。它只畫 panel，terrain/unit icon 與 AP/DP/HP digit paths 仍分離，不能把完整 HUD 標成完成。
- [x] **native HUD signed-number selector**：`indexedmap.BlitNativeMapHUDSignedNumber` 固定 `0x1aeb1` 的 raw LMI #0x83（非負 6×7）／#0x84（負值 6×5）選擇、absolute value、`origin+8` digit callback。callback 必填且 failure atomic，不把 sign 留半張；font、table value、AP/DP/HP來源與語意仍未命名。
- [x] **native HUD two-digit renderer**：`0x1aeb1→0x187d6` call-site 固定 glyph base #0x1f、width=2；`%0.5d` 被 patch 成 `%0.2d`，每位以 six-pixel advance 走 `0x16886→0x4e63d` Frame。`BlitNativeMapHUDTwoDigitNumber` 接上完整 #0x1f..#0x28（實檔 #0x20=5×8、其餘6×8）與 sign selector，超過99 fail-closed，不讓 native truncation變成可編輯資料的隱性行為。數值來源／AP/DP/HP語意仍不命名。
- [x] **native HUD terrain-icon subpass**：`0x1acf3` 在 panel 後以 `0x12e38` local word0（masked terrain descriptor）直接選 selected FDSHAP bank descriptor，`0x4deda` raw blit 到 panel `+6`。`BlitNativeMapHUDTerrainIcon` 固定此 10-bit selector／anchor並拒絕 bank 外資料；不以 PNG preview 或 terrain 名稱代替原始 source。
- [x] **native HUD unit-icon subpass**：`0x12c0d` 成功後，`0x1acf3` 以 unit+2 selector-cache slot、raw global state（3→1 alias）選 cached FDICON 12-frame block，raw blit 至 panel `stride*5+6`。`BlitNativeMapHUDUnitIcon` 有 cache/state/bounds regression；slot 不命名為角色或 portrait。
- [x] **native HUD terrain AP/DP subpass**：resolver raw control byte+1 經 `0x51a12/0x51a2a` 固定 0→(+5,0)、1/5→(0,0)、2/3→(-5,+10)、4→(-5,-5)。`NativeMapHUDTerrainAPDP`／`BlitNativeMapHUDTerrainAPDP` 用 exact AP/DP layout origin、sign和兩位 glyph renderer，invalid code／render失敗 atomic；不替 control byte 命名。
- [x] **native HUD persistent anchor branch**：Docker Capstone 實讀 `0x1ad2a..0x1ad5f`：raw `0x53abd>5 && 0x53ab9<3` 才寫 anchor `0xf2`，`0x53abd>5 && 0x53ab9>9` 才寫 `1`，其餘座標保留既有 `0x51a0c`；`indexedmap.AdvanceNativeMapHUDAnchor` 覆蓋兩臨界值與 retention，不把 globals 命名為未證實 UI 語意。
- [x] **native HUD HP subpass**：`0x1ae8e→0x1875d→0x187d6` 的 incoming stack 已逐項驗：unit unsigned `+0x40/+0x42` 傳 current/max 和 mode3；current==max 選 glyph base #0x1f，否則 #0x2a，畫 current 三位、每位 advance6；current>999 改畫 base+10。真實 #5 #0x29/#0x34 均18×8，兩 digit bank 僅 digit1=5×8。`BlitNativeMapHUDHP` 覆蓋 equal/unequal／overflow和 invalid-resource atomic，未將 unequal 命名成 damage。
- [x] **native full HUD assembly**：Docker Capstone `0x1ad72..0x1aea9` 確認順序 panel→terrain→AP→DP→optional icon→optional HP；`BlitNativeMapHUD` 以 `NativeMapHUDInput` 將所有已證實 subpass atomic 組裝。`OptionalUnit=nil` 嚴格代表 `0x12c0d` 或後續 raw unit-byte gate 的 skip，helper 不猜測 gate 角色語意；display gates 關閉時 no-op 且不要求資源。
- [x] **native HUD optional-unit gate**：`0x1ae2a..0x1ae47` 已直接固定：raw `unit+7==0x79` skip；否則僅 raw `unit+0x1f==0x0a && unit+6==1` skip。`NativeMapHUDOptionalUnitEligible` 覆蓋兩 skip 與兩放行，供 caller 正確產生 `OptionalUnit=nil`；三 byte 不命名。
- [x] **strict native indexed-frame entrypoint**：`ComposeNativeFrame` 把 `FrameInput` 與 `NativeMapHUDInput`/frame/terrain/unit/cache 綁為單一 `NativeFrameInput`，直接以 `BlitNativeMapHUD` 填滿 `0x11cac` 的 HUD slot，不再把完整 native frame 交給任意 callback。regression 驗 HUD bytes 進 work buffer 及 `0x11eb0` viewport copy；PNG/Ebiten presentation 仍是下一個獨立 asset/palette bridge。
- [x] **FDSHAP archive sprite-bank bridge**：`fdother.DecodeSpriteBankResource` 以 LLLLLL `ReadResource→fdicon.Parse` 解 FDSHAP even image resource，不混入相鄰 terrain-control resource；player-provided FDSHAP#0 regression 固定 288 個24×24 four-mode frames。這提供 native HUD terrain icon／indexed compositor 的真實 archive input，但 map↔resource pairing仍由上層明示。
- [x] **FDSHAP map resource pairing**：`DecodeMapTerrainResources(mapIndex)` 只讀已證 map N→image #`2N`、control #`2N+1`，並驗 bank frame count 不超 control-record count；FDSHAP map0 真實 regression=288 frame/1200 control bytes。明確拒絕從 tile count/cost 猜 map 資源。
- [x] **exported map-path binding**：`MapIndexFromAssetPath` 僅接受 legacy `assets`=map0 或 basename 精確 `mapN`，拒絕 suffix/負數/任意目錄；runtime 將用此 explicit N 餵 FDSHAP pair loader，不以檔名近似猜配。
- [x] **production native-map asset gate**：`Game.loadMap` 載入 HUD FDOTHER frames、明示 FDSHAP pair、FDICON.B24、VGA palette 為 all-or-nothing `nativeMapAssets`；任一缺失/解碼失敗保持既有 PNG renderer，indexed-to-Ebiten presentation 尚待下一步。
- [x] **indexed→Ebiten native HUD partial bridge**：`drawNativeMapHUD` 以 456-stride buffer→320×200 paletted image 實際呈現 panel/terrain/AP/DP；raw tile/control bounds 或任何 decoder failure 立即回 legacy UI。optional unit/HP 尚未接，因 runtime roster admission bytes 未 export，不猜測性補上。
- [x] **HUD unit-gate constructor provenance**：Docker Capstone `0x10d7f..0x10efc` 固定 runtime `+6=FDFIELD b0`、`+7/+8=FDFIELD b1`，與 editable `map_selector_key`/`battle_fig` 對齊；`+0x1f` 改由 portrait/resource branch 寫入，不能拿 portrait/class 直接代替。缺少該 resource byte 時 optional icon/HP 繼續 fail-closed。

- [x] **FDICON indexed asset primitive**：`internal/fdicon` 現直接 decode `FDICON.B24` header/offset table/24×24 four-mode RLE，保留透明與 dither spans；`Sprite.BlitAt` 是 raw `0x4deda`，`BlitPaletteBand` 是 `0x4de56` 的 `(index&7)+0x18`。**撤回 256-byte LUT 對應說法**（那是其他 renderer path）；fixture 與 player-provided 原始 1680-sprite regression 通過；仍未替代 roster/frame/timing/layer adapter。

- [x] **FDICON native selector primitive**：`Bank.SpriteFor(key,pose,cycle)` 嚴格表達已解析 B24 raw key 的 `key×12 + pose×3 + cycle` lookup（pose 0..3、cycle 0..2）並 regression；`0x127e0` 則先取 runtime `unit+2` cache slot 選對應 12-pointer block。它與 `0x287b5..0x2884c` 的 battle `unit+7 × 3` FIGANI selector 是不同 raw field；現有 exported visual id 的相等只在已驗證 roster 記錄成立，不能當 ABI alias。`NativeFrameIndex` 依 +4 movement offset 選 `0x3C0B/0x3C07`，將 global cycle 3 正規化為 1，`+0x26` 則強制 0；撤回「runtime +4 frame」說法，故沒有把它隱式接入 GUI。
  - [~] battle selector bridge：`battle_fig`→`Unit.BattleFig`→全螢幕 `newAtkAnim` 已可承載 split ABI，loader regression 固定它可與 legacy map `fig` 不同；constructor `0x10d7f..0x10efc` 已閉合 FDFIELD `b1→unit+7`，正式 exporter 已寫入該欄、舊 JSON 才 fallback。`fig` 不宣稱原版 field。
  - [~] map selector provenance audit：`0x10c50→0x11019` 是 global raw-key FDICON cache path；完整 constructor 已釘 FDFIELD `b0`（亦寫 native camp `+6`）。`0x11019` 只比對全域 key table，僅新 key 使用 caller archive pointer 建 block；player `0x10a25` 與 scripted `0x10b69` 都開啟 `FDICON.B24`。parser/exporter 現輸出 raw `map_selector_key=b0`；map0 30筆實跑為 keys `[0,1,2]` 並逐筆等於 camp raw code。`tools/sync_native_selector_fields.py --check` 現驗證全部 33 份版本化 map assets 的 `map_selector_key`／`battle_fig`，且只更新這兩個閉合欄位，避免 full exporter 覆寫既有人工校正數值。Scenario 現在以 party-first／group-order batch materialize，battle draw 只在整場成功時 slot→key；malformed editable input 會保留 legacy append 並禁用全場 native selector。撤回把角色表/DATO/素材 index 的相等值當成全域 mapping。下一步是 native indexed buffer/palette/layer composition，不得把目前 PNG/Ebiten selector adapter 寫成完整原版 renderer。
    - [x] player-party source split：`0x1088d→0x10a77` 先 copy persistent `[0x53bf7]` 0x50-byte record，再用 copied `+7` 作 `0x11019` key，回傳 slot 寫 `unit+2`。它不是 FDFIELD `b0` 路徑；slot allocation 順序必須保留這條 roster loop 的順序。
      Official IDA 9.4 address-only xref report再確認 `0x10a77` 屬於 `sub_1088d`，而 `sub_1088d` 的 callers 是 `0x205ff`、`0x25870`、`0x2c437`；不得將 selector initialization 當成只有一般 battle setup 才會做的步驟。
      `JOIN` constructor `0x112a5(join_id)` 直接寫 persistent `+7=join_id` 且 `+8=join_id`；`0x33499` 已閉合 `+8` character-ID lookup。因此 fresh player 的 map raw key=character ID，但只限這個 writer；不得回推 FDFIELD/NPC/general `fig` identity。另 `0x314a7..0x3157a` class-change flow 對 live roster `+7` 寫 UI-selected raw target，故 equality 不是 immutable；`0x11506` 的 full 0x50 runtime→persistent copy 會在任何 `sync_party` caller 保存它，唯 class-change 是否立即進這條 flow 待追。
    `fdicon.NativeSelectorCache` 已以 first-seen key→slot regression 表達 cache 部分；resource/key decoder 尚未接入 runtime。
    `KeyForSlot`／`SpriteForNativeSlot` 已閉合 slot→raw B24 key→`key×12+pose×3+cycle` 的 pointer-block lookup；runtime materialization 仍待。
    - [x] explicit raw-key materializer：`map_selector_key` 與 `battle.MaterializeNativeMapSelectorSlots` 現可按**caller supplied** native order 對單一 resource 建 first-seen slots；preflight 要求每筆有 0..255 key，missing/invalid 不改 unit/cache，絕不從 `Fig` fallback。尚未自動掛到 player/scripted construction，因其 order/resource boundary 必須先由 caller 關閉。
    - [x] player JOIN/class-change split persistence：fresh `PartyMember.Fig` 僅在 verified JOIN initialization 種入 `BattleFig`／raw key；`ApplyClassChange` 依 `0x3157a` 更新後兩者、清舊 slot，保留 stable `Fig`（native `+8` identity），跨關 persistent overlay 完整帶回 split fields。battle/campaign/cmd regression 通過；renderer 仍不由 legacy `Fig` fallback。
    - [x] state atomic construction-order seam：`State.AppendNativeMapSelectorBatch` 持有單一 global raw-key cache，只有整批 explicit key preflight 成功才 materialize+append；regression 固定 party `[9,4]`→scripted `[0,2,0]` slots `[0,1,2,3,2]` 和 failure 不污染 state/cache。33 份 map asset 已有 raw keys；Scenario 仍暫不自動呼叫，直到 mixed construction order 也有直接接線。
- [x] **FDICON native placement primitive**：`NativePlacementOffset` 逐指令重現 `0x127e0` 的 456-byte buffer stride、`0x75d8` origin、24-pixel tile 與 `unit+4 × {+0x720,-4,-0x720,+4}` direction offset；`+0x26` 才加入 native 0/1 pixel shift。它回傳 framebuffer byte offset，不把未證實的 framebuffer origin/layer/UI 自動轉成 remake screen coordinate。
- [~] **native foreground-terrain occlusion layer**：Docker trace 已把 `0x129ec` 定為 unit-sprite 後的前景補畫，但修正「每個可見 unit」的簡化說法：它先跳過 `0x1f183(slot)` true 的 raw gate（`unit+7==0x1c` 放行；其他 `unit+7` 的 class `0x13` 或 race `4/5` 跳過），再跳過 `0x3453e` inactive slot。**撤回**剛才將 `unit+7` 稱為 group 的錯誤：map sprite group 是 `unit+2`。`fdicon.NativeForegroundRedrawEligible` 以 regression 固定兩 gate，`NativeForegroundRedrawCells` 保留 eligible slot 的精確 `(x,y)`、`(x,y-1)`、移動 pose-neighbour 順序。`BlitNativeForegroundLayer` 現以 raw roster inputs 接上 steady `0x129ec→0x12ac6`：camera interval、bit7／bit8 descriptor、`index+1`、`0x8088` offset、raw/LUT-transparent branch 全部 byte-level regression；只在 supplied map 外的座標 fail-closed skip，不讀 unchecked native memory。Official IDA 9.4 再證明 `0x1366a` 的 scripted-step redraw 也做 `0x11eee` terrain→per-slot `0x127e0`→`0x129ec`，並在 `0x129ec` 後才進 `0x11eb0`／present；故不可只把 occlusion 掛在 steady `0x127a9`。range/HUD/VGA/Ebiten adapter 尚待。
- [~] **FDSHAP raw-transparency / LUT branch boundary**：four-mode decoder 保留 opacity mask，`export_engine_assets.py` 以它輸出 raw `0x4deda` preview 的 RGBA tileset（map0 alpha `(0,255)`，opaque palette index0 不被猜透明）。**撤回**「mode3 一律等價 alpha」：`0x11eee` 的 entry `+3!=0xff` 走 `0x4dcc6`，其 mode3 對既有 destination 做 LUT remap，不是 skip。exporter 已保留 event high byte `native_tile_blit_modes`，供未來 indexed adapter；完整 palette/LUT compositor 與 `0x129ec` schedule 仍 fail-closed。
- [x] **native terrain frame selector**：`0x11eee` 對 visible FDFIELD cell 取 10-bit tile ID、讀 FDSHAP terrain-control byte；priority 為 bit8→`+2*flip(0x53a40)`，否則 bit10→`+trunc(0x3c0b/2)`，否則 bit4→`+flip`，其餘 base tile，隨後才選 `0x4deda/0x4dcc6`。`fdicon.NativeTerrainFrameIndex` strict regression 覆蓋 priority/negative truncation/bounds。這是 raw animation ABI，不替 bit 命名；GUI frame scheduler 尚未接。
- [x] **native `0x4dcc6` LUT primitive**：`fdicon.Sprite.BlitLUT` 精確保留 source write→`lut[source]`、mode3→`lut[existing destination]`、mode1 dither holes 不改寫三種行為，short LUT fail-closed 並 regression。它不選 LUT／不管 map camera/layer，避免把原始 pure blitter 誤接成完整 terrain renderer。
- [x] **native single-cell terrain compositor**：`Bank.BlitNativeTerrainCell` 組合 exact frame selector 與 FDFIELD `entry+3==0xff` raw／否則 LUT branch，regression 覆蓋兩支及 mode3 destination remap。camera-visible loop、LUT phase、foreground `0x129ec` 不在此 pure adapter 範圍。
- [x] **native visible terrain pass**：`Bank.BlitNativeTerrainRegion` 以 raw FDFIELD cell、FDSHAP 4-byte control records、map origin／explicit LUT 做 `0x11eee` row-major visible region，bounds fail-closed、regression 覆蓋 raw/LUT cell order。正常 `0x11cac` ABI 已釘為 `(buffer+0x8088,456,13,8,camX,camY)`，其後 range→unit→foreground passes 仍分離。
- [x] **native indexed viewport copy**：official IDA 9.4 關閉 `0x11eb0` 為逐列 `memmove`；`0x11cac` 明確以 source `buffer+0x8088`／stride456、width320、height192 複製到 VGA `0xA0504`／stride320。`fdicon.CopyNativeIndexedRegion` regression 覆蓋 row stride、source offset 與 fail-closed bounds；尚未自動接成 Ebiten presentation。
- [~] **native terrain/unit map HUD (`0x1acf3`)**：它在 `0x11cac` 的 terrain/range/unit+foreground 後、viewport copy 前執行，且須 raw gates `0x51aab`、`0x51aac` 都非零。先以 `0x12e38(cursor)` 解 FDFIELD tile10/event-low5/FDSHAP control4，再以 `0x12c0d(cursor)` optional active-unit lookup；`NativeTerrainCursorInfoForCell` regression 固定前一 raw ABI。已釘住 control byte+1→`0x51a12/0x51a2a` 的 AP/DP 表，並由 `battle.Load` 以逐格 raw tile/control 接至戰鬥計算。layout 已收斂為 LMI1 #130（69×34）`buffer+stride*157+x`、terrain `+6`、AP `stride*8+0x2b`、DP `stride*19+0x2b`；`0x1aeb1` 依 table 值正負選 raw directory decimal #83/#84、取絕對值再走 native digits，兩 resource 的視覺語意仍不命名。`x` raw 初值1，已見條件改為0xf2或1。unit icon/HP resource、高階 global 名稱仍待。**撤回**把現行 map HUD 的 FDOTHER#5 full-screen battle frame 當 native equivalent 的說法；目前只保留可玩 approximation。
  - [x] codec boundary：#130／hex #0x83／#0x84 不走 `ParseLMI1` 的 `0x4e916` cell codec；native `0x1aeb1` 有 literal `mov ebx,0x83/0x84`，明確走 four-mode `0x4e63d`。`ParseLMI1FrameEntry`／`DecodeLMI1FrameResource` regression 驗證 geometry 69×34、6×7、6×5 及 transparent decode。撤回剛才將 hex immediate 誤改成 decimal #83/#84（44×12／45×12）的錯誤斷言。
  - [x] optional unit selector：`0x1ae4d` 以 raw `unit+2*12 + state` 選 FDICON，state=3 alias 1，並在 panel `stride*5+6` raw blit；HP `+0x40/+0x42` 經 `0x1875d` 畫至 `stride*21+9`（mode3）。`NativeMapHUDUnitFrameIndex` regression 保留 selector，不替 state 命名。
  - [x] strict compositor layout：`NativeMapHUDLayoutFor(anchor,456)` 固定 frame／terrain／AP／DP／unit／HP 的六個 byte destinations，拒絕非 native stride 與 69-pixel frame 出 320-pixel viewport 的 anchor；留給後續 indexed renderer 組裝，未宣稱已接 Ebiten。
- [x] **native terrain renderer export bridge**：`export_engine_assets.py` 在帶 FDSHAP terrain resource 時輸出完整 `native_terrain_control` raw bytes 加既有 per-cell `native_tile_blit_modes`。map0 實測為 576 cell modes、1200 control bytes；因此 region adapter 不必把 normalized `cost` 當 native renderer input。
- [x] **native terrain renderer runtime bridge**：`battle.Load` 將 exact `native_tile_blit_modes`／`native_terrain_control` 放入 `State`；dimensions/cell count/control 4-byte alignment/所有 tile 10-bit bounds 任一失敗即雙欄 nil。battle regression 覆蓋完整輸入，尚未取代 PNG renderer。
- [x] **FDOTHER#3 LUT bank loader**：`fdother.ParseLUTBank`／`DecodeLUTResource` 嚴格解析 LMI1 directory 的 23×256-byte remap tables（非 UI LMI cell），fixture 與 player-provided archive regression 通過。現可把確證 LUT 交給 `BlitLUT`；map selector、palette timing、renderer layer 仍不猜接。
- [x] **native terrain LUT phase selector**：EXE `0x51A97` 的 20 bytes 直接讀得 `0..10..1` 往返序列；`NativeTerrainLUTIndex(0..19)` 並 regression。`0x11eee` 預設取此 phase 對 FDOTHER#3 LUT；explicit override state仍只保留 raw，不命名效果。
- [~] **indexed ending compositor core**：`internal/ending.IndexedCompositor` 現提供原版尺寸的 VGA/offscreen/work buffers、透明 `fdother` in-place blit、64000B copy，以及 `0x11df2` 對 6-bit DAC 的 inclusive-range/clamp delta；合成 regression 已通過。它尚無 Ebiten presentation、schedule executor 或 ANI/DATO adapter，timeline 仍 fail-closed。
- [~] **ending compositor asset preflight**：正確圖源是 `FDOTHER_054.bin`（263655B、111-frame table），不是 `FDOTHER_036.bin`（408×138 的無關資源）；ANI #2 已可由 `internal/afm` 解出 26×320×200 frames。`internal/fdother` 已有 fail-closed raw table parser、原版透明 RLE in-place blitter，及 player-provided `FDOTHER.DAT` 的 `#0x36` archive loader；後者有與 raw #054 byte-for-byte 的 regression。下一步是已釘死的 schedule/branch adapter，未完成前禁止 generic ending fallback。
- [~] **ending `#0x36` frame decoder contract**：`0x2935b` 以 `base+8+frame*4` offset table取 descriptor；`+0/+2` 是內嵌目的地 dx/dy，`+9/+11` 是 real w/h，payload 自 `+9` 以 transparent `-1` RLE blit。玩家素材 regression 現對 #054 全111幀逐一做 320×200 in-place decode。`0x2bce5` 的 frame0、frame9、frame12..108、兩段 frame-pair composite 與 palette/delay loop 已可逐段轉錄；`0x2c39b` 的兩個文字 helper args 尚未有字串／位置語意證據，只能 opaque 保存並 fail-closed，尚缺完整 runtime bridge。
- [~] **editable ending prefix timeline**：新增 `assets/endings/native_2bce5.json`，把已證實的 #054 blit、copy、delay、palette ramps、兩段 native composite loops 存成可編輯 IR。`0x2c39b` 第二 arg 已依 `0x15f84` direct ABI 定案為 current-FDTXT string index：final route idx2..7 → `ch30.json` scene1 lines0..13；chapter26 bad ending idx17..20 → `ch27.json` appendix scene lines1..4（原始 FDTXT_027 逐 string decode 實證）。第一 arg 已依 `0x1956b → 0x111ba(0x51a70)` 與 doc14 定案為 `DATO.DAT` portrait ID，timeline 改用 `portrait_id`。`internal/ending` 仍只接受 `recovered_prefix_only_fail_closed`，絕不將它視為可播放 ending；buffer/palette helpers、ANI/戰鬥段落 bridge 仍是明確 gate。
- [x] **天空之鑰缺失對話分支**：新增 `ch27.json` 分支 scene（FDTXT_027 idx13–16 共17句）並接 `inventory_gate_ch27_sky_key → story_ch27_post_sky_key_missing → ending_ch27_no_sky_key`；視覺效果仍待 direct RE，對話本身已可編輯且有 campaign regression。
- [x] **戰後 town/shop/preparation 外部交叉盤點（2026-07-20）**：subagent 查得公開攻略逐章列出羅德鎮、塞拉村、普里茲港等戰間商店／教會／整備，並有「第2章戰後獎勵」與「第6章戰後貝克威加入」等 persistent event 證據；只作流程旁證，不取代 EXE branch 證據。後續保持 battle→postbattle→town/shop/preparation→next battle 可編輯節點，禁止把 postbattle 直接接下一場戰鬥當完成。
- [x] **戰後 town/rest 反例盤點（2026-07-20）**：GameFAQs 明載第14章途中小鎮休息，且第22章至第26章前沒有 rest/buy/sell；因此 campaign 需保留 battle→town/rest 的可編輯節點，也要允許 ch23–25 連戰區間不插 town/shop。攻略只作外部旁證，仍須以 EXE/資產驗證觸發時機。

## 對話框 / 過場打磨(2026-07-05,使用者實玩逐項校正)
- [x] **對話框文字不覆蓋頭像**:上框(頭像在右)文字右緣止於頭像左緣前(commit 57c0e30)→ doc09
- [x] **對話框上下移入畫面**:下框上移(底邊可見)、上框下移(頂邊可見)、頭像置中框內(dc5ebb1)→ doc09
- [x] **框內底色=頭像底色漸層**:框內疊 40,69,138→56,85,154 漸層消接縫色差(dc5ebb1)→ doc09
- [x] **長對白分頁不截斷**:>3 行分頁,Enter 先翻頁翻完才換句;dlgWrap/dlgPageCount/dlgAdvance + dlgPage;
      Go 測試 dlg_test.go 驗全文保全(b81268d)→ doc09
- [x] **進場走位面向修正**:走完面向 actor 目標 dir(亞雷斯走到索爾旁面向他),storyWalkJob.finalDir(aaf5020)→ doc47 §11
- [x] **對話分頁捲動動畫**(2026-07-20)：原版確認有文字往上捲；remake 已實作 10 幀上捲（舊頁上移、新頁由底部進入、框內 clip），Enter 於動畫期間不跳頁，並有 dlg regression。GUI 實機截圖待補圖形依賴容器。
      目前翻頁是「瞬間切換」;要改成**平滑往上捲動**——按 Enter 翻頁時,當前內容往上捲出、下一頁從底部捲入。
      **使用者明示:不用依賴原版機制,自己寫平滑捲動即可**(原版有此效果,但捲動速度/幀數自訂,非 RE 值)。
      實作方向:翻頁時啟一個 `dlgScrollT` 計時器(數幀),繪製時把文字整體 y 偏移從 0 平滑插到 -行高×3、
      同時畫「當前頁下移出 + 下一頁自底部進」,期間 clip 在框內矩形;捲完才定位到新頁。
      動 `cmd/fd2/main.go` 對話繪製區 + `dlgAdvance`(翻頁時觸發捲動而非瞬間 dlgPage++)。
- [ ] **⬜ 自動結束回合**(使用者要求 2026-07-05,不急):目前 remake 要**手動按 Tab** 才換回合;
      原版是**全員行動完自動結束回合**——我方(玩家操作的 + NPC/友軍)全部移動/行動完 → 自動換敵方;
      敵方全部移動完 → 自動換回我方。實作:每次單位行動後檢查該陣營是否還有「可行動」單位
      (未行動 flag,見 doc25/單位 +5 bit7=已行動),若無則自動 endTurn 換陣營;移除或保留 Tab 當「提前結束」快捷。
      需對照原版:①是否有「跳過剩餘我方單位」的手動提前結束 ②敵方 AI 動完的判定時機。動 `battle` 回合狀態機 + main.go。
- [~] **handler 後半段 beats 解碼**(sonnet subagent 執行中 acb94c2):庭院/森林段走位/對話/fade 編排,
      供重建 palace_path/forest 節點(Ares 進場對話框位置、逐段走位轉向、索爾練劍、領頭跟隨、fade 換場)

## 完成定義(反組譯研究)
全部資產格式可解(解包+解壓+轉現代格式)、核心數值表全 dump 並驗證、
主要遊戲規則演算法(戰鬥/移動/升級/AI)有反組譯依據、地圖可渲染、文本可讀可改。

## 2026-07-25 SDD gate（使用者要求先重審反組譯與 UI）

- [x] **可重現 UI/core regression container**：`fd2-go-test-local` 在 Docker build 時取得 Go modules、在 runtime 使用 `--network=none`；已實跑 `go test ./cmd/fd2 ./internal/... -count=1` exit 0。image 內含 Ebiten 所需 ALSA/X11/GL headers；這只驗 source build/test，並非原版 UI 畫面對照。
- [x] **UI-01 original title screenshot oracle**：新增隔離 `fd2-dosbox-screenshot-local` runner（SVGA/Xvfb/xdotool，原始 FLAME2 不掛載、只用 `/tmp` sandbox），連續 Escape 跳過 opening 後得到 320×200 `docs/figures/title-original-dosbox.png`。畫面證實 START／LOAD／CONTINUE 及初始 cursor；title input/save semantics 仍未關閉。
- [~] **UI-12 LOAD selector contract**：同一 runner 的 title→LOAD flow 在全空 sandbox 得到 320×200 `docs/figures/load-empty-original-dosbox.png`，鎖住四個 slot rows、空記錄文字與第一列 outline；Docker Capstone `0x30550` 另釘死 slots `0..3`、↑↓ bounded（不 wrap）、Enter/Space confirm、Esc cancel，並固定 native save boundary=`0x59cb`、record=`+0x312b+i*0xa28`（metadata=`0x28`、roster=`0xa00`）、rolling-XOR/checksum。它不是 metadata semantics/delete/overwrite/load-success 證明，remake 四槽 save UI 待建。
- [x] **UI-05 ch01 dialogue screenshot oracle**：START 分支得到 320×200 `docs/figures/ch01-dialogue-original-dosbox.png`，鎖住一種 lower/left DATO portrait、藍框、兩行文字與 page indicator；upper/right/control code/pagination 尚未由這張圖宣稱完成。
- [x] **UI-04 native command-grid remake oracle**：Docker/Xvfb 以 player-provided FDOTHER.DAT、ch01 materialized 悠妮 `initial_command_mask=[1,0,0,0]` 捕捉 [`native-command-grid-remake.png`](../figures/native-command-grid-remake.png)。畫面確證 command0 label「火炎術」與 selected-unit HUD 同時存在，故 raw mask→grid cell `(18,103)`→editable label→palette/font renderer 已接通；這是 remake runtime smoke，**不是**原版 DOSBox visual diff、full command gate 或 effect/UI 完成證明。
- [x] **FD2 remake SDD**：新增 `56-fd2-remake-sdd.md`，定義 UI contracts、battle→postbattle→town/shop/church/preparation flow、persistent party/save、native indexed renderer、E0–E3 證據分級與 milestone gates。
- [~] **SDD-1 UI evidence matrix**：以 Ghidra/IDA + Docker Capstone 重審 title/menu/action/target/HUD/dialog input dispatch；矩陣與 Capstone E0 已建立。2026-07-26 使用者合法 IDA Docker image 已實跑 `idat -A`／Hex-Rays，輸出 address-only [`fd2_xrefs.json`](../data/ida/fd2_xrefs.json)；script 已修正 IDA 9.4 移除的 xref-type API。分析 database 與 IDAPython config 均留 `/tmp`，repo 不含 license／binary／database，也絕不用 `kg_patch`。report 只補 call graph，未有資料流或 E2 不解除語意 gate。
- [x] **SDD-1 baseline matrix**：新增 `57-ui-evidence-matrix.md`，以目前 runtime 行號把 UI-01…UI-12 的 partial/missing 與下一個 E0/E1/E2 問題固定下來；這不是原版 verified。
- [x] **UI-03 action caller recheck**：Docker Capstone 重審 `0x18890`，確認它呼叫 `0x18d8c` 取得 action result 並串接 `0x13488` path-walk／`0x13a44` target path；撤回「只是繪圖」類推，`0x18d8c` 本體仍是下一個 RE gate。
- [x] **UI-03 action switch closure**：Docker Capstone 完成 `0x18d8c`：`↑0=攻擊、←1=法術、→2=物品、↓3=待機／格子互動`；同步修正 `main.go` ring mapping 與 13/14/57 文件，撤回舊 screenshot-derived mapping。
- [~] **UI-03 native command ABI**：Docker Capstone 完成 `0x1c269→0x1cff0→0x4e516`：unit `+0x1a..+0x1e` 的
      五個 bitmask 逐 bit 展開為 command ID `0..39`，再索引 `0x619fd + 7*id` 的靜態 record。現行四格 ring
      只是 partial interaction；`0x159fa` 再證實 record `+5 <= unit+0x44`（current MP）的 availability gate。
      `0x10f7f/0x11399` construction 各 copy source 的 4 bytes 到 `+0x1a..+0x1d` 並清 `+0x1e`，
      `0x1d7fb` 可按 commandID/8 OR 回 runtime bit，故 40-bit ABI 初始為 32-bit source、可動態擴充。
      官方 IDA 再釘 confirm dispatch：IDs `0..8/0x18/>=0x1c` 走 `0x2a6bd` generic pipeline，
      `0x09..0x17/0x19..0x1b` 才經 `0x1d6c8` palette flicker→`funcs_1541f[id]`；這不把 command 0
      升格成 legacy spell effect。ID0 的 `0x2a6bd` entry 也只閉合 compositor（`funcs_2ac25[0]=0x26152`），
      尚未定位 HP/status writer。`0x1b6b7→0x1aa1d` 已排除為該 writer：前者只收集符合 post-resolution
      條件的 runtime record 三-byte資料，後者處理其後續訊息／掉落／互動。
      `0x1c75e→0x1c81f` 現已釘 command0 hit/damage：record `u16+0`×target class-ID（unit`+0x20`）multiplier/10，
      `rand()%100 < record+2`，命中後以 90..99.9% base 扣 `unit+0x40` 並 clamp0（`+0x42` 是 HP cap）。
      multiplier table 已與 file `0x51d96` 的職業魔抗 `resist_raw` 對齊（base=`dmg*raw/10`）；完整 target family
      仍待，尚不可直接替換為 legacy magic formula。
      selector `0x1d51d` 已鎖每欄四列的 variable-column grid：↑/↓ linear wrap、←/→ ±4、Enter/Space 重查
      MP gate、Esc cancel；`0x1ceed` 再鎖 x/y formula 與 label index=`0x1b9+commandID`。常駐 table
      已對齊 FDTXT_000，40 個 physical label slots 已由 `tools/export_command_labels.py` 匯出為
      `docs/data/command_labels.json`；label 不等於可達／有 gameplay effect。待 command producer、完整
      renderer/effect stack 後才可重製原版 menu。2026-07-25 再釘 `0x18d8c` wrapper 的 item-side raw
      preconditions：`0x1b83d` 找八格 inventory 中 equipped(bit0x40) 且 ID<0x80 的項目，失敗寫 output+0；
      `0x1b8a6==0`（八格全 empty bit0x80）寫 output+8。它們對應哪個圖示仍未有 callee/E2，禁止猜接 UI。
      2026-07-26 再以完整 `0x18d8c` dataflow 固定四個 disabled words 的順序為 attack/native-command/item/wait，
      `0x173e7/0x177fc` 僅選值 0；`0x1c269==0` 或 `unit+0x27!=0` 都寫 native-command `+4=1`。
      remake 已以 `NativeTransient[5]` gate raw command；撤回任何「`+0x27` 就是 legacy `Sealed`」的斷言。command22
      已知寫入此 duration；status 名稱與其他 writer 仍未知。
      confirm input 同步拒絕任何 nonzero disabled word，避免僅 render 灰 cell 卻仍執行該 action。
      action chooser 本體亦已完成 E0：availability=0 才可用 ↑/←/→/↓ 選 action 0/1/2/3，Enter/Space 確認、
      Esc 取消；四張 indexed asset 自中心做 4-frame 十字 slide，72×72 backup 每幀 restore。尚缺 resource
      anchor 與畫面 oracle，故仍不可將現有文字/ring UI 當成 original renderer。resource provenance 已補：
      `[0x53a89]` = `FDOTHER.DAT#2` 的 78-cell raw offset bank，`0x4e9e4` 直接貼 index pixels（0 preserve）；
      strict decoder/regression 已加入，仍未接 runtime renderer。
- [x] **UI-03 command-record/table identity**：`0x4e516` 的 IDs 0..35 與 EXE spell table 7-byte rows
      byte-for-byte 相同，故 record `+3/+4/+5/+6` 可安全正名為 `dist/range/mp/target`；全 FDFIELD 和
      character-default initial masks 的已見 ID 範圍為 0..30。36..39 僅是 pointer 可達的相鄰 data、label
      為空／系統訊息，未被升格為 spell。
- [x] **UI-03 level-up command producer**：`0x1e292→0x1d79c` 已釘為升級習得 command；growth row 的
      `learn_idx` 經 `0x4e4a2` 查 20×12-byte、最多六組 `(required_level,command_id)` 表，命中即 OR bit
      並顯示 FDTXT_000 #587「學會了！」。已導出 `command_learn.json`，保留 FF/FF sentinel；portrait→growth
      row 是 `0x4e4d1(unit+7)=0x620a1+unit[+7]*11` direct ABI；constructor 已證實 FDFIELD `b1→unit+7`，
      `State.GainExp` 已以 injectable table 接線，
      runtime asset `assets/data/command_learn.json` 已在每個新 battle state bind，不能用 legacy `Spells`
      偽造結果。
- [x] **UI-03 raw command-mask pipeline**：FDFIELD roster `b13..b16` 已由 parser/exporter 保留為
      `initial_command_mask`；battle runtime materialize 為可持久的 5-byte `NativeCommandMask`，並有原版
      order 的 ID expansion／`0x1d7fb` bounded-OR regression。舊 `Spells` 是 normalized approximation，
      不再冒充 raw source；尚未將未知 command effect 接入。
- [x] **UI-04 target-candidate provenance**：Docker Capstone 延伸 `0x1cff0→0x149f8`，確認 local command record `+3/+4/+6`、`command=0x1e` 傳 selector14、`0x149f8` 沿格步進並輸出符合 selector 的 unit index，另有 `0x17` special geometry 與 `0x2a6bd/0x1d6c8` effect paths；不再把 `0x149f8` 誤稱成傷害／完整 spell priority。
- [~] **UI-04 range geometry**：Docker/Capstone 已直讀 `0x14818`：它以固定 `0x61646` record 0 和原始 `(x,y,mode)`
      呼叫 `0x4e040`，mode 作 seed grid byte 並經 terrain cost gate 建立／更新 target grid；後續再有
      `|x-cx|+|y-cy| < caller radius` 的 marker 層、unit active flag／
      camp selector 輸出 slot；mode>=`0x10` 有另一路十字 clear。這只證實其中的曼哈頓幾何，
      另一 caller `0x14344` 證實同 helper 會以 unit `+0x20`（fallback 0x13）的 record 和 terrain table
      作格點 gate，故 SDD 必須保留 table+terrain+marker，而不能以單一 diamond 實作。
      `0x1cff0` stack-dataflow 亦已固定參數為 `(x,y,out,mode,radius,campSelector)`：special `0x17` 用
      `record+3`/radius 1，一般 path 用 `record+4`/radius 0 並消費既有 marker。尚未將這些 producer
      同武器 `range_min/range_max` table 完整對位；record producer 已鎖為 `0x4e516(id)=0x619fd+7*id`，
      故 `+3/+4/+6` 是 command ABI raw fields，仍不改寫為「所有武器 max inclusive」或 LOS 定論。
- [~] **UI-03 battle selector input**：Docker/Capstone 重檢 `0x19953`，確認它呼叫 `0x36d98` 讀 ASCII/scancode；Enter/Space/`0xe0`/`0x52` family 走確認回傳、`0x01`/`0x53` family 走取消回傳，`0x4b`/`0x4d` 更新左右選擇狀態。這是 battle selector 的 E0 input ABI，不等於已閉合 action enable/end-turn 或 D8 行軍確認。
- [~] **SDD-2 campaign transition matrix**：已從 `campaign_full.json` 逐一展開 30 個 battle 的 `on_win`，
      明確保留 town/shop/church/preparation/inventory-gate/ending 節點與連戰例外，表格已寫入
      `56-fd2-remake-sdd.md` §5.1（E1 editable graph）。仍待逐列補原版 handler E0／DOSBox E2 證據與 save/reload regression，
      未把 authored graph 當作原版已驗證。
- [x] **UI-11 preparation split-slide primitive**：官方 IDA 確認 `0x1f42d/0x1f1cc` 使用 FDOTHER#5 LMI1 entry `0x52`，以 456-stride 在 `(85-offset,82)`／`(165+offset,81)` 執行 `100,75,50,25,0` 五步，每步 present 後 restore；新增 `NativeSplitSlideSteps`、edge-clipped cell blit 與 callback executor/regression。未命名 MAP/TURN，也未接未證實的行軍 input。
- [x] **UI-11 raw preparation record gate**：Docker Capstone 重新讀 `0x1a866`，固定 `+0x25!=0`、`+0x06==selector`、`+0x05 bit0==0` 三個 raw gate，以及 `+0x40 -= +0x42/10`、負值 clamp、global divisor write；新增 `ParseNativePreparationRecord`／`NativePreparationEligible`／`NativePreparationAdjustedWord40` 與 malformed/gate/clamp regression。未將欄位命名為 active/alive、座標或 deployment。
- [x] **UI-11 preparation dispatch table**：Docker Capstone 固定 `0x1a813` 的 `base+3*i`、16 slots、`+3/+5` gate 與 `+4` function-table index；新增 `FindNativePreparationDispatch`，保留重疊 3-byte raw layout、short-table fail-closed 與多重命中 regression，不執行未命名 callback。
- [x] **UI-11 preparation timer transition**：Docker Capstone 固定 `0x1a941` 對 0x50-byte record 的 selector/inactive gates、六個 `+0x22..+0x27` counter decrement，以及僅 1→0 才產生 `0x1e1+index` downstream source；新增 `TickNativePreparationTimers` in-place raw planner/regression，不命名狀態或效果。
- [x] **UI-11 preparation input ABI**：Docker Capstone 固定 `0x19953` 的 raw scancode branches：`E0/52/1C/39→1`、`01/53→-1`、`4B→cursor0`、`4D→cursor1`，其他輸入繼續等待；新增 `ApplyNativePreparationInput` 與 regression，不把 return 1/-1 猜成 YES/NO。
- [x] **UI-11 preparation command stream schema**：Docker Capstone 固定 `0x1ac62` 以 `base+3*i` 讀 `{kind byte, payload word}`；已保存 kind 0/1/2/3 的 observed branch boundary（selector-2、200ms/function-table、indexed resource），新增 `ParseNativePreparationCommands` 與 truncation regression，不把 raw kind 命名成事件。
- [ ] **SDD-3 UI shell vertical slice**：title→story→battle field→action menu→dialog→town/shop，加入 input trace、headless regression 與真實截圖 artifact。
- [ ] **SDD-4 native renderer re-audit**：完成 resource provenance 與 indexed buffer contract 前，不得把 finale figure-fade／ending prefix 宣稱為完成。
- [~] **RE-UNIT-STATIC-TABLES**：已新增 `tools/extract_native_unit_tables.py` 並以實際 FD2.EXE 產生/驗證 raw fixture：高 branch `b1-0x44 → 0x61af9` 68×10；lower branch `0x61da1` 32×24／`0x620a1` 68×11。尚缺 runtime branch selector 與 unit record byte-for-byte join，故 HUD optional unit/HP 仍 fail-closed；`0x619fd` 不屬於 constructor。
- [x] **INDEXED-FRAME-TEST-CONTRACT**：修正 native compositor fixture 的 `work+0x8088` 來源邊界、range descriptor bank 與 viewport copy 座標；Docker indexedmap regression 通過，未放寬 production fail-closed 條件。
- [x] **REGRESSION-BLOCKERS-2026-07-26**：Docker image 內建 Xvfb 已納入完整 regression command；ch14 final dialogue line mapping 依 FDTXT_015 count-aligned continuation 修正，ch16 conditional spawn 僅 branch-local after LOADCH。完整 suite 通過，未刪除有效 assertion 或放寬 fail-closed compiler。

## 2026-07-20 ending prefix playback slice

- [x] **0x2bce5 可播放前綴（仍 fail-closed）**：`internal/ending.Player` 現以毫秒 clock 依原序執行 frame0 transparent blit、64000-byte copy、1000ms hold、ANI #2（首幀立即、後續每100ms），以及 direct-Capstone 證實的 `0x11df2(0,255,EBX)` 63→0、每步4ms palette ramp；玩家 `FDOTHER.DAT #54` + `ANI.DAT #2` regression 已走到第一個 native text gate。遇 native text 或 composite 一律保留最後 VGA frame 並回報 `blocked`，絕不改用 generic fade／結局。
- [x] **獨立畫面 oracle**：`FD2_ENDING_PREFIX=1` 會讀玩家自備 DAT，將 indexed VGA DAC 轉為 320×200、2× 顯示於 Ebiten；它不接 campaign，故無法假裝原版終局已完成。可用 `FD2_FDOTHER=/path/FDOTHER.DAT`、`FD2_ANI=/path/ANI.DAT` 指定素材，並沿用 `FD2_SHOT` 截圖。
- [ ] **下一個 ending gate**：將已定案的 DATO/FDTXT dialogue blocks 以 native sequence 接到現有對話 UI（含 chapter26/29 branch）；之後才處理 frame12..108、640-stride composite loops 與 campaign terminal route。

### 2026-07-20 native ending dialogue bridge

- [x] **0x2c39b preview dialogue**：`internal/ending.Player.BlockedDialogue(chapter)` 僅在 `native_text_branch_opaque` 取出 chapter26 then 或 final else blocks；`FD2_ENDING_PREFIX=1` 以 `FD2_ENDING_CHAPTER=26|29` 明確選 branch，讀 editable `ch27.json`／`ch30.json` 的 exact scene,line,count，並強制每句使用 block 的 `portrait_id`（native DATO arg1），不混用 transcript speaker。它沿用 DATO 頭像與 Enter/Space 分頁阻塞；對話結束後 player 仍停在同一 native gate，後段不會被放行。
- [x] **native text gate resume**：對話所有頁／句皆完成後，preview 只可呼叫 `ResumeBlockedDialogue()` 恢復該一個 `native_text_branch_opaque` segment；任何 composite 或其他 opaque gate 都被拒絕，避免 UI 誤跳過未 RE renderer。下一段將依資料化 palette repeat / frame sequence 繼續實作。
- [x] **text 後 palette repeat**：`palette_ramp_repeat` 的 native `repeat=3`、63→0、4ms、`tail_delay_ms=200` 現由 player 展開成三組明確 `palette_ramp + delay`，不以普通 fade 代替；接續會在尚未實作的 frame12..108 sequence gate 停住。
- [x] **frame12..108 sequence**：`blit_frame_sequence` 現展開 frame12 到108 的 transparent VGA blit 與每幀20ms wait；第一段 text 後 resume 可走到第二個已知 native text gate。composite 的 string formula 改名 `first_frame_formula`，避免與 sequence integer `first_frame` 的 JSON schema 衝突。
- [x] **ending composite frame selection regression**：`0x2bf60` 與 `0x2c0c5` 的兩張角色 frame 都是 `(i%4)+1` / `(i%4)+5`，不是 `floor(i/4)+1`；timeline 與測試已鎖定。200-pass scheduler 完成後會停在 `0x2c172` 的未恢復 montage gate，不會誤報 ending complete。
- [x] **first 40-pass composite primitive**：新增 640×200 work buffer、`CopyRect`、帶 byte-origin bounds 的 `Frame.BlitAt`，並以 native primary/secondary offsets + viewport x=160 實作 `Composite40(i)`；尚待 scheduler 接線，第二 loop 的 palette helper 繼續封閉。
- [x] **first 40-pass composite scheduler**：player 現以每輪20ms 驅動 `Composite40(i=0..39)`，完成後精確落在第二段 native text gate；200-pass loop 仍因 `0x11d40` 未證實而封閉。
- [x] **second 200-pass composite scheduler**：baseline palette loop 已恢復為200×20ms（0..135 base、136..199 base−1）；其後 `0x2c172` 明確標為 unrecovered montage gate，禁止 player 回報完整 ending。
- [x] **finale 0x2c405 phase-0 map**：已確認 chapter30 text load、`0x36b00` staging/clear、`+0x12c30` text-composite destination、500×(1ms) 的 320×200 row-scroll 與 baseline palette 40→0→上升 cadence。strict FDTXT_031/#44 glyph staging 已恢復；仍只在後續 `0x2c548` montage gate 停止，禁止用 generic fade 或空白畫面替代。
- [x] **finale phase-0 editable script node**：新增 `assets/endings/native_2c405.json` 和嚴格 loader；`0x2c469` 前的 `load_ch_text(30)` 依 loader 規則選 FDTXT_031，故 `0x2c` 是其合法實體 string #44（46 strings）。內容是後日談跑馬燈前言，對位跨資源重用的 `ch32.json` scene0 line0；staging/layout/timing/palette cadence 均資料化。asset 可編輯但 `Ready()==false`，直到完整 finale montage 都恢復。
- [x] **native FDTXT/font decoder foundation**：`internal/fdtxt` 現嚴格讀原始 offset-table、保留所有 FFxx 控制字、精確解 `FDOTHER_004` 的 16×16 1bpp（MSB-left）glyph。尚未猜 palette／框／控制碼行為；下一步把已知 `0x15f84` layout 接成 compositor。
- [x] **native glyph staging primitive**：`Font.BlitGlyph` 將 FDOTHER_004 的 set bits 以明確 caller palette index 寫入 indexed buffer、zero bits 完全透明，且有 pixel regression。`0x4ea2a` 的實際色彩／layout 參數仍未假設，不能因此解除 finale gate。
- [x] **0x4ea2a glyph ABI closure**：Docker Capstone 確認 native glyph renderer 是 16×16 前景 + 左／下陰影，background 非零才清 cell；finale `0x2c469` 的 caller 展開為 stride320、foreground `0xCD`、shadow `0x4C`、background0。`BlitNativeGlyph` 已 pixel-test 這個 ABI；FFxx flow/staging backdrop 尚未完成。
- [x] **finale phase-0 raw glyph composition**：`ComposePhase0Text` 現真正把 FDTXT_031 physical #44 的121個 glyph、9個 `FFFE` soft line breaks，以 `staging+0x12c30`、16-byte advance、每行 `25×320` rows、CD/4C/transparent native style 寫入。實機資源 regression 逐 bit 驗 foreground/left/down shadow；除已證實 FFFE 外任一 FFxx 仍拒絕，整段 finale 仍 fail-closed。
- [x] **finale phase-0 scroll scheduler**：`Phase0Player` 精確執行500 passes：每輪 baseline palette→`staging+i×320` 的320×200 copy→wait1ms→i++；i=0..199 每5輪（含0）將40逐步降至0，i=301後每5輪（首個305）升回。完成只回傳 phase done，不會跨 `0x2c548` montage gate。
- [x] **FDTXT archive provenance**：Capstone 直接證實 `0x1088d(30)` 先 `inc` 再傳 `0x111ba`，所以載 archive resource31；其 bytes 已 byte-for-byte 對照 extracted `FDTXT_031.bin`。先前 resource30 mismatch（5762 vs 6756）是 off-by-one，phase preview 可安全取 resource31。
- [x] **finale phase-0 bridge**：`ending.Player.EnableRecoveredPhase0` 只在精確 `0x2c172` hand-off 執行；它取前段 `PresentANI` 已捕捉的原版 DAC baseline（無 provenance 即拒絕）、清 VGA、以 FDTXT_031/#44 與 FDOTHER#4 生成 staging，逐毫秒跑完 500-pass scroll。完成後精確停在未恢復的 `0x2c548`，不會誤宣告 ending complete；regression 覆蓋首幀、baseline 缺失拒絕與 montage gate。
- [x] **finale `0x2c548` first party-cycle map**：Docker Capstone 切出三個 native buffers（128000、64000、64000）、TAI#3 與 FDOTHER#56 backdrop；更正：TAI#3 raw 是 `10×3`、三列 `C9` 的全透明 placeholder，不能誤稱可見 platform。loop index 從 `[0x53bfb]-1` 向下，但必做 `i=0→slot1、i=1→slot0` swap，才以 unit stride80／visual group `+7` 載 `FIGANI group*3+1` 與 `group*3`。`0x29164` 後先有 `0x2b9a1` 的20×1ms loop，再跑 primary FIGANI descriptor frames。已入 `assets/endings/native_2c548.json`，但 DATO/text/input 與 dedicated indexed renderer 未解，保持 fail-closed。
- [x] **finale party portrait/text map**：DATO=`unit+7`；FDTXT_031 的 #10/#11/ending epilogue 與 FDTXT_000 的角色名／職業名，五個 destination 與 CD/4C glyph style 均已直接對齊 `0x2c7ed..0x2c967`。IDA correction 刪除錯誤的 `unit[+8]+0x0c|45` 斷言，epilogue 改為 `edi<0xdc ? unit[+8]+0x0c : 0x2d`；`Montage.PlanPortraitText` 已有 regression。DATO countdown/anchor、special slot 與 native indexed renderer 尚未可執行，仍 fail-closed。
- [x] **finale dialogue-frame layout call ABI**：IDA/`14-text-control-codes.md` 交叉確認 `[0x53a81]` 是 `FDOTHER.DAT#5`，不是 DATO；`0x2c773→0x168b6` 實參為 `(destination=C, stride=0x140, arg8=5, argC=7, arg10=5, arg14=5)`，先建立 dialogue frame/grid，後續才由 DATO `[0x53a85]` 經 `0x4e8af` 貼 portrait。已撤回 `dato_layout` 錯誤命名，schema 改為 `dialogue_frame_layout`。
- [x] **DATO indexed decoder foundation**：新增 `internal/dato`，按 `0x4e8af→0x4e916` 高值-run codec 解四個 80×80 mouth frames，零值保持 opaque（不套 transparent sprite 規則），並提供 strict bounds checked indexed blit；synthetic RLE/opaque-zero 與玩家 DATO#37 regression 已加入。`0x168b6` 的 5×7×5×5 grid 排版與 native mouth cadence 尚未接 runtime。
- [x] **dialogue-frame `0x168b6` raw grid plan**：`Montage.PlanDialogueFrameGrid()` 逐一保存 49 次 `sub_1685c` 的 `FDOTHER#5` raw resource index/destination byte（固定 12 次、兩組 3×2 loop、5×5 grid），保留 exact arithmetic；不替 cell 命名 border/portrait，也未解除 dialogue/DATO renderer gate。
- [x] **FDOTHER#5 raw-cell codec correction**：`0x1685c→0x4e9bb` 只讀 width/height 後逐 row `rep movsb`，不使用 `0x4e916` high-run；新增 `fdother.ParseLMI1RawEntry/DecodeLMI1RawEntry`，真實 #5 entry1 (`3×3`, literal `60 be bd...`) regression 固定此 path，避免把 dialogue frame bank 誤套 LMI1 RLE。
- [x] **dialogue-frame raw compositor**：`RenderDialogueFrameGrid` 依 49 個 verified placements 直接將 `FDOTHER#5` raw cells 寫入 C buffer，明確使用 opaque `rep movsb`（包含 zero bytes），不接 DATO/text/input；synthetic overlap/zero regression 通過。
- [x] **dialogue-frame resource-backed compositor**：`RenderDialogueFrameGridResource` 現實際載入玩家 `FDOTHER.DAT#5` entries 1..17，再按 native placement/overwrite order 寫入 C buffer；缺檔仍 fail-closed，asset regression 驗證非空輸出。
- [x] **DATO opaque paste primitive**：`RenderDATOFrameAt`／`dato.Frame.BlitAtOffset` 對應 `0x4e8af` 的 stride-320 opaque frame paste，destination offset 必須由 caller 明確提供（native 常見 `staging+[0x53c67]`）；不把該 global 猜成固定 anchor，也不接 mouth cadence。
- [x] **finale `0x2c548` official-IDA gate recheck (2026-07-26)**：IDA 9.4 ASM 直接確認 phase-0 的 `0x2c548` gate 先 free 500-pass staging，再配置 `0x1f400`、`0xfa00`、`0xfa00` 三塊 indexed buffer；以 `sub_111ba("TAI.DAT",3)` 與 `sub_111ba("FDOTHER.DAT",0x38)` 載入 montage inputs，FDOTHER #0x38 先以 stride `0x140`、transparent `-1` blit 到第一個 64000-byte buffer，接著由 `[0x53bfb]-1` 反向取 party record。這是專用 indexed montage 的資源/緩衝 ABI，不是 generic fade 或可直接替換的 PNG scene；DATO、FIGANI schedule、mirror branch 與 renderer 未閉合，runtime 仍 fail-closed。
- [x] **indexed FIGANI decoder foundation**：新增 `internal/figani`，直接讀 FIGANI LLLLLL resource、13-byte frame header（signed X/Y、delay、real W/H）和 4-mode RLE，透明 span 以 mask 保留而非轉 palette0；`BlitAt` 寫入 indexed surface，實機 `FIGANI.DAT` #13 regression 通過。下一步是 TAI frame 與 native 0x29164 fade/composite，不能改走 RGBA PNG。
- [x] **native FIGANI scheduler `0x2b9a1` (2026-07-26)**：官方 IDA 確認 `arg4==0` 僅清 `byte_540fc`（subframe）且不 render；非零路徑先以目前 `byte_540fd` frame 呼叫 `0x2935b`，再讀 descriptor `+6` delay，累加 subframe，達 delay 才換 frame 並於 frame count wrap。`internal/figani.NativeScheduler.Step` 已照此實作與 regression；renderer 仍由 caller 顯式提供，未猜測 `0x2935b` 的 presentation semantics。
- [x] **0x29164 first fade closure**：第一參數是 party loop unit index（讀 `[0x53a45]+unit×80+6`），不是 TAI；TAI#3 是尾端 aux argument，7-byte transparent raw 不可餵 `0x2935b`。兩條 native path 都做 `esi=8..0` 共9次 present，每次 DAC baseline delta=`esi×6`（48→0）；geometry／aux platform role 尚待拆完，故 renderer 仍不接。
- [x] **non-mirrored figure-fade schedule**：`native_2c548.json`／`Montage.PlanFigureFade(1)` 現嚴格記錄 final caller 的 `unit+6==1` branch：work stride640、320×200 left viewport、stage byte offset `8..0 ×10`、palette delta `48..0`，TAI#3@164,157 explicit transparent no-op、secondary FIGANI frame0。`unit+6==0` mirrored branch 仍拒絕，不拿非鏡像公式套用。
- [x] **non-mirrored indexed fade primitive**：`RenderFigureFadePass` 現真正執行每輪 B→A（320→640）restore、secondary FIGANI 在 `stage×10` 的 indexed blit、A left viewport→VGA 與 baseline DAC delta；TAI#3 bytes 必須是原始透明 no-op。像素 regression 鎖住 backdrop 保留、stage shift 與 48→2 palette；B→C 的 post-figure `memmove(64000)` 亦已記錄，供下一段 portrait renderer 使用。
- [x] **`0x29164` mirror-branch ABI transcription (2026-07-26)**：官方 IDA 釘出 `unit[+6]==0` 的 `0x2927e..0x29357` 路徑：仍為 `stage=8..0`、每步 palette `stage*6`，但 primary FIGANI source 是 `staging+0x140-stage*10`；只有 `arg4==0` 才額外畫 TAI#3 與 secondary FIGANI。`native_2c548.json` 已保存 `mirror_branch` editable metadata 與 loader regression；這只補齊 ABI 證據，不解除 dedicated indexed renderer gate。
- [x] **mirror fade planner**：`Montage.PlanMirrorFigureFade(unitSide,sideFlag)` 現輸出 9 個 exact stage/offset/palette pass，並明確保存 `arg4==0` 的 secondary/platform gate；純計畫器有 wrong-side 與 side-flag regression，不代表已完成 pixel renderer。
- [x] **mirror indexed fade primitive**：`RenderMirrorFigureFadePass` 依 `0x292ad` 的 caller-preseeded 640-stride right viewport，先 present `work+0x140`，再以 `staging+0x140-stage*10` 畫 primary、按 `arg4==0` 畫 secondary，最後 present 同一 viewport；TAI#3 僅做透明 raw validation。pixel regression 通過，但 DATO/完整 montage 仍 fail-closed。
- [x] **RE-UNIT-RAW-SCHEMA**：`export_units.py` 與 `battle.NativeConstructorTable` 已保存已證實 branch/index/raw records，嚴格拒絕 malformed dimensions；此項只完成資料邊界，不代表 renderer/gameplay 已接通。
- [x] **RE-HUD-RAW-CYCLE**：閉合 `sub_1297d` 的 `[0x53c0b]/[0x53c0f]` raw state 更新規則並加入 pure adapter/regression；runtime scanline source/call timing 尚未接入，禁止用 `g.frame` 替代。
- [x] **CH29-POST-FLOW-WIRING**：`postbattle_ch29_persist` 已接 recovered `ch29_post` handler→`preparation_ch30`；移除錯誤 synthetic sync/set beats，保留 native LOADCH persistent-roster boundary。`0x2bce5` renderer 未完成前仍 fail-closed。
