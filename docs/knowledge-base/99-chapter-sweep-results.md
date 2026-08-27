# 99 — 全章節結構性掃描結果(`tools/fd2_chapter_sweep.py`)

> 對應 `docs/knowledge-base/91-worklist.md` M5「正常玩法可達性驗證」項目與
> `docs/knowledge-base/98-tooling-infrastructure.md`「全章節結構性掃描」一節(工具設計/
> 已知限制的完整寫法)。本文件只記錄**逐章跑出來的結果**,不重複工具本身的設計文件。

## 方法論摘要(完整版見 doc98)

對每個章節 N:用 `tools/fd2save.py` 把機器上唯一真實存檔(md5
`e6d9a35756cddfc2519969b10f039181`,原本落在 ch27)的 slot0 章節 byte patch 成 N,
開一個獨立 `dosbox_harness.sh` instance LOAD 這份存檔,讀 `DAT_00053a45`(live
`0x1EFA45`)判斷是否進入戰鬥;若是則掃描敵方 record 寫入死亡 signature(`+5=0x01`)+
送出續六十二證實過的 End-Turn→YES 捷徑;若否則用通用 bounded 按鍵迴圈嘗試推進。跑完後
讀回存檔章節 byte 是否前進,作為主要 pass 訊號。

## 誠實結論(2026-08-27,第一輪)

**通用章節導航(`advance_generic`)目前無法在合理步數預算內走到任何一個章節的戰鬥或
下一個明確里程碑**——這不是本工具的邏輯錯誤,而是這個專案自己都尚未解出的開放問題:
`docs/knowledge-base/58-remake-live-verification-log.md` 續五十七到續六十三記錄了單單
ch27 一個章節的可靠 reach 序列,就花了跨越多輪、由人類即時操作+反覆試錯才成功,且同一
存檔在不同 session 觀察到至少兩種不同 UI 型態(icon 選單 vs. 可行走地圖),沒有已知的
判別方式能事先預測。本工具的 Phase 1 驗證(見 doc98)已經誠實記錄了對 ch27 本身重跑
3 輪+2 輪獨立互動式 probe 都未能重現這個已知可行的路徑。

**因此本輪掃描的絕大多數章節預期都會是 `needs_manual_followup`**,不是 `pass`——這是
如實反映現況,不是掃描失敗。有意義的訊號改為看:(a) 章節跳轉+開機+LOAD 本身是否乾淨
(沒有崩潰/卡死),(b) post-load 畫面是否落在預期範圍內(例如異常的全黑畫面),
(c) 戰鬥偵測機制本身是否有任何誤判(不應該有,也確實沒有觀察到)。

**已知會影響結果解讀的重要caveat**:本工具目前唯一可用的「真實存檔」是一份章節已推進到
ch27、roster 有 13 名角色的存檔。把它的章節 byte 直接 patch 回很早的章節(如 ch01-05)
時,roster 內容**不會**同步退回早期章節該有的較小名冊——這產生一個真實玩家永遠不會遇到
的「早章節 + 晚期滿編隊伍」組合狀態,原生引擎在這種未定義狀態下的行為(例如 ch01 觀察到
LOAD 後立刻全黑畫面)**可能反映的是這個人工組合本身的不一致,而不是 ch01 內容真的有問題
**——解讀早期章節(尤其 ch01-10)的結果時務必把這個 caveat 一併看,不能直接當成「ch01
結構有缺陷」的證據。`estimate_roster_size()`估算的目標人數如果小於源存檔既有人數,本工具
目前選擇「保留源存檔不裁減」而非嘗試移除角色(移除持久化 roster record 目前沒有已驗證的
安全做法),這個決定本身就是這個 caveat 的直接成因。

## 逐章結果(2026-08-27,30/30 章節全數掃過)

30 章全部乾淨跑完(單一背景 process 從 ch01 循序跑到 ch30,總耗時約 63 分鐘,平均每章
~124 秒),**沒有任何一次腳本崩潰、掛起、或需要中止重來**——`ps aux`/`tmux -L
fd2harness ls`/`tmux ls`(default socket)收尾核對三方都乾淨,doc48 §8.4 canonical
`dbg` session(本輪未使用)全程未受影響。30 章的 verdict 全部是 `needs_manual_followup`
(0 pass、0 anomaly、0 tool_error)——見下方「如何解讀」,這不是掃描失敗,而是誠實反映了
本工具已知的通用導航限制(見 doc98)。

| 章節 | post-load 節點分類 | verdict | 耗時(s) |
|---|---|---|---|
| ch01 | ANOMALY（全黑畫面，見下方 caveat） | needs_manual_followup | 56.4 |
| ch02 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 124.4 |
| ch03 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 124.3 |
| ch04 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 124.2 |
| ch05 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 124.3 |
| ch06 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 124.4 |
| ch07 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 124.7 |
| ch08 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 127.8 |
| ch09 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 128.9 |
| ch10 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 130.1 |
| ch11 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 144.1 |
| ch12 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.2 |
| ch13 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.3 |
| ch14 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.2 |
| ch15 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.4 |
| ch16 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.0 |
| ch17 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.0 |
| ch18 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.1 |
| ch19 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.0 |
| ch20 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.2 |
| ch21 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.0 |
| ch22 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 124.9 |
| ch23 | prep-select（出戰人數選人畫面） | needs_manual_followup | 125.1 |
| ch24 | prep-select（出戰人數選人畫面） | needs_manual_followup | 125.2 |
| ch25 | prep-select（出戰人數選人畫面） | needs_manual_followup | 125.2 |
| ch26 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.9 |
| ch27 | camp-map（可行走營帳，多套美術 skin） | needs_manual_followup | 125.4 |
| ch28 | prep-select（出戰人數選人畫面） | needs_manual_followup | 125.5 |
| ch29 | prep-select（出戰人數選人畫面） | needs_manual_followup | 125.0 |
| ch30 | prep-select（出戰人數選人畫面） | needs_manual_followup | 125.2 |

### 如何解讀:三種 post-load 節點分類,不是隨便分的

用每章`02_post_load.png`截圖(LOAD 選存檔位確認後、generic advance 迴圈開始前的那一刻)
分類,每類都有具體、可重現的視覺特徵:

- **camp-map(22 章)**:可行走的營帳地圖(帳篷+圍籬+4 個商店熱點:酒店/道具店/武器店/
  教會,角色可用方向鍵行走,右下角文字隨最近的帳篷變化),與 doc58 續五十九首次記錄的
  UI 型態一致。**ch02 與多個其他章節(如 ch09)的這張截圖逐位元組核對後其實是同一張圖
  (`rgb md5`相同)**,而 ch12 等其他章節則是同一套機制的**不同美術 skin**(不同顏色/
  花紋的帳篷,肉眼比對佈局與互動熱點完全相同)——證實這是全遊戲共用的通用樣板場景,不是
  各章各自的美術資產,這是本輪最有後續行動價值的發現(見下「下一輪建議」)。
- **prep-select(6 章:ch23/24/25/28/29/30)**:**完全跳過營帳地圖**,LOAD 後直接落在
  「要記錄戰況嗎?YES/NO」對話框,advance 迴圈跑完後停在正式的「出戰人數選人」畫面
  (`出戰人數 X15`/`剩餘人數 X14`+一整排單位頭像格)。**這 6 章精確對應
  `docs/knowledge-base/25-battle-event-system.md` §9.1 已用純靜態反組譯推導出的
  「raw chapter 22/23/24/27/28/29(=顯示 ch23/24/25/28/29/30)是整備限定流程,跳過城鎮
  hub」結構性主張——零例外精確吻合**,是本輪掃描對這個既有推論的第一次 live 交叉驗證
  (先前該推論本身標記為「尚待驗證」)。這 6 章雖然仍是`needs_manual_followup`(選人畫面
  需要精確選滿門檻人數才能繼續,generic 的 Enter/Escape 輪替沒有這個邏輯,不會湊巧選對
  15/19 人),但**這 6 章實際上比 camp-map 的 22 章更接近戰鬥**,下一輪如果要優先突破,
  應該先攻這 6 章的選人邏輯(比破解 camp-map 的圍籬缺口簡單——只需要送指定次數的確認鍵
  選滿門檻,不需要解走地圖座標)。
- **ANOMALY(1 章:ch01)**:LOAD 後立刻全黑畫面,之後 10 個 advance 步驟畫面完全沒有
  任何變化(`advance_generic`偵測到 stall 提前中止,只用了 11 張截圖就結束,是全部 30
  章裡唯一提前中止的一章)。**這極可能是本工具方法論本身的已知 caveat 造成,不是 ch01
  真的有引擎缺陷**:機器上唯一可用的「真實存檔」roster 已有 13 名角色(來自 ch27 進度),
  把章節 byte 硬 patch 回 ch01(遊戲最初章節,正常玩家此時應該只有 1-2 名角色)產生一個
  真實玩家永遠不會遇到的「最初章節+晚期滿編隊伍」組合,原生引擎對這種未定義輸入的行為
  沒有理由被信任是「正常」的——本工具目前的`prepare_chapter_save()`只會**增補**roster
  到估算人數、不會**裁減**過多的 roster,所以沒有辦法用現有唯一存檔避開這個組合。誠實
  標記為「工具已知限制導致的結果不可信,不是 ch01 本身結構異常的證據」,需要一份真正的
  早期進度存檔才能重新驗證。

### 完整性/嚴謹度自我檢查

- 用`hashlib.md5`對每章`advance_*.png`截圖序列去重,確認 ch01 是**唯一**一個「全部
  advance 截圖雜湊相同」(1 張唯一畫面/11 步)的章節,其餘 29 章都有 19-33 張唯一畫面
  (48 步預算內),證實 generic advance 迴圈的按鍵確實送達且畫面確實隨之變化——`0/30`
  verdict 是`pass`不是因為腳本本身卡死或按鍵沒送達,是真的探索過但沒找到既定目標。
- 每章`prepare_chapter_save()`的 round-trip 自檢(`fd2save.decode`)全程通過,沒有任何
  一章因為存檔編碼錯誤而提早失敗。

## 2026-08-27 續輪:camp-exit 導航診斷(對應「下一輪建議」#2)

### 誠實結論先講:不是輸入丟失,是工具從沒試過已知可行的序列

派工單假設「camp-exit 是否只是已知的 Enter/Space 間歇丟失 bug」,直接用獨立
`campexit` instance(WSL2,`tools/dosbox_harness.sh`)重跑 ch12(`town_ch12`,已在
`91-worklist.md` UI-VIS-TOWN 條目驗證過是 variant1)驗證doc91 UI-VIS-PREPARATION
2026-08-25 prepE2 輪已經用真實 ch27 存檔證實可行的序列——`Right`×3(從預設
selection0/酒店 循環到 selection2/出口)→`Return`(離開確認)→`Return`(「要進入
戰場嗎?」YES)。**結果:兩次 `Return` 都在第一次嘗試就註冊成功,全程沒有一次
需要重送**——這代表舊有的、確實存在別處的 Enter/Space 間歇丟失 bug（doc58 續
五十四～續七十七）**不是**這一輪 0/22 camp-map 掃描結果的成因。真正成因是
`tools/fd2_chapter_sweep.py` 的 `advance_generic` 根本沒有實作這個已知序列——除
ch27 外的 21 章完全沒有 hint,一律落到 `_ADVANCE_KEY_CYCLE`(以裸 `Return` 開
頭,在預設 selection0/酒店就直接開啟酒店 NPC 對話/名冊瀏覽器,永遠走不到出口);
就連 ch27 自己的 hint 也混入了會打斷戰前對白流程的多餘 `Escape`/`Down`。

### 另外揪出一個獨立的 debugger-state bug

驗證過程中發現 `advance_generic` 逐步迴圈裡呼叫 `read_battle_array_base()` 前
從未重新 `enter_debugger`——這個函式底層送出的 `D` debugger console 指令只有在
debugger TUI 真的開著時才有效,但 `sweep_chapter` 在進入這個迴圈前已經呼叫過
一次 `debugger_cmd(name,"RUN")` 把它關閉並恢復模擬器。也就是說**這個迴圈自己的
戰鬥偵測從第一步之後就沒再讀到過任何東西**——這解釋了為什麼就連本來就有 hint
的 ch27,在完整 30 章掃描裡也一樣是 `needs_manual_followup`。已一併修正(逐步
補上 enter_debugger/RUN 配對)。

### 修復:`attempt_camp_exit()`,取代 ch27 專屬 hint 成為全章節首選

新增 `attempt_camp_exit()`,對所有章節(不再只是 ch27)第一個嘗試:`Right`×3→
`Return`(exit confirm,失敗重試至多 4 次,作為對別處確實存在的 Enter/Space bug
的廉價保險,不代表本輪重現過這個 bug)→`Return`(YES confirm,同樣可重試)→
最多 20 次 `Return` 逐步推進戰前對白,每步都正確地重新 `enter_debugger`/`RUN`
檢查戰鬥陣列指標。`KNOWN_NAVIGATE_HINTS` 改為預設空字典,只作為未來個別章節
真的需要不同序列時的 override 機制。

**驗證:22 個原本卡住的章節(ch02-11/13-22/26)+ ch27 重跑,23/23 全數从
`needs_manual_followup`(從未偵測到戰鬥)進步到 `anomaly`(可靠走出軍營、
觸發「要進入戰場嗎?」確認框、偵測到戰鬥陣列指標、掃描並標記敵方死亡signature、
送出 End-Turn 捷徑)**,每章耗時 146-200s(遠快於原本 124s/章 卻連戰鬥都沒找到的
`advance_generic`)。完整結果見 `.wsl_build/chapter_sweep_v2/results_merged.json`。

### 意外發現的第二層問題(超出本次派工單範圍,誠實記錄不強修)

23/23 章的 `anomaly` verdict 都卡在同一句:「敵人已掃描/已標記死亡/End-Turn 已
送出,但章節 byte 沒有前進」。追查後發現這其實是**兩層問題疊在一起**:

1. **戰鬥陣列指標本身會在戰前走位過場動畫途中被重新配置**——一個過渡性的早期
   配置(只有1筆記錄)幾秒後會被真正配置的完整陣列取代。用一支不送任何按鍵、
   純被動輪詢的獨立探針(`campexit_probe3`,ch12)證實:t=0s 時 base 指標 A 只有
   1 筆記錄,t=5s 起 base 指標**變成另一個位址** B,穩定 11 筆記錄,一路到
   t=40s 都沒再變過——純粹是被動時間閘門,不是輸入閘門,不需要額外按鍵。第一版
   修復只在**原始**指標上重掃、從未重新讀取指標本身,已修正為每輪都重新
   `read_battle_array_base()`。ch12 用此修復重跑後正確找到 11 個敵人並全數標記
   死亡(而非先前的 1 個)。
2. **但同一套修復套用到 ch27 上,6 輪、每輪 2.5s(共 15s+)的被動輪詢裡指標
   完全沒有變化,穩定只有 1 筆記錄**——與 ch12 的行為不同,顯示不同章節的戰鬥
   陣列/敵人重生時機**不能一概而論**,doc98/`fd2_chapter_sweep.py`原有的誠實
   限制(「敵人掃描/死亡 signature/stride 只針對 ch27 驗證過，未跨章節交叉核
   對」)在这一輪被進一步坐實,而且連 ch27 本身用這條新的快速自動化路徑重新
   驗證時,都**沒有**重現 doc58 續五十七～續六十三人工操作記錄過的 63 個敵人
   ——很可能該輪人工操作在按 End-Turn 之前有花更長真實時間、或有额外走位/
   互動步驟,不是單純的「送出確認鍵→等幾秒→End-Turn」。
3. 這第二層問題不是本次派工單「camp-exit 導航是否可達」要回答的問題,且明顯
   需要针对每章甚至 ch27 本身重新做一輪真正的即時互動式驗證(而非本輪這種快速
   自動化 timing 探針)才能解——**誠實記錄為新開放項,本輪不強行套用猜測性修
   正**。`sweep_chapter` 的敵人掃描 settle 迴圈已改為固定跑滿 6 輪(每輪 2.5s)
   取最大敵人數,取代了曾經在 ch27 上過早判定「已穩定」而漏掉真實敵人陣列的
   兩輪-連續-相同即視為穩定的邏輯——這只是讓「掃到什麼就如實回報什麼」更可靠,
   不等於解決了第二層問題本身。

### 影響 M5 驗收的結論

camp-exit 導航本身(本次派工單的目標)**已解**,且证实根因是「工具從未實作
已知可行序列」+「一個獨立的 debugger-state bug」,兩者皆與 doc58 記錄的
Enter/Space 間歇丟失 bug 無關(本輪操作中一次都沒重現那個 bug)。但這代表
`fd2_chapter_sweep.py` 的整體 verdict 分布從「0 pass / 0 anomaly / 30
needs_manual_followup」變成「0 pass / 23 anomaly / 6 needs_manual_followup
(prep-select) / 1 needs_manual_followup(ch01, 舊有 caveat)」——**沒有任何一
章這輪拿到 `pass`**,因為第二層問題(敵人陣列/win-condition timing)阻擋了
所有 23 章的最終章節 byte 前進確認。M5「正常玩法可達性驗證」因此仍不能視為
完成,但「camp-map 章節能不能自動走出軍營觸發戰鬥」這個子問題已經從「未知/
卡住」變成「可靠、可重現」。

## 下一輪建議(2026-08-27 新增,取代原建議 #2)

1. **最高投報率(新):追查「戰鬥陣列/敵人重生時機因章節而異」**——ch12 的完整
   敵人陣列在 YES 確認後約 5 秒才配置好(之前是過渡性的 1 筆記錄陣列),但同一套
   邏輯套到 ch27 上,15 秒被動輪詢完全沒有變化。需要對至少 2-3 個章節做一輪
   真正放慢步調、每一步都截圖+讀記憶體核對的即時互動式驗證(不能只延長被動
   sleep),搞清楚「End-Turn 確認鍵送出的時機」與「戰鬥陣列真正就緒的時機」
   兩者的關係,以及 ch27 本身用新的快速路徑重跑為何沒重現 doc58 續五十七～
   六十三記錄過的 63 個敵人。這是目前唯一擋住任何一章拿到真正 `pass` verdict
   的問題。
2. **camp-map 圍籬缺口本身已解**(見上方「2026-08-27 續輪」),不再是待辦。

## 下一輪建議(原始,2026-08-27 之前)

1. **最高投報率:先攻 6 章 prep-select 的選人門檻,而不是 camp-map 的圍籬缺口**——這 6
   章(ch23/24/25/28/29/30)已經結構性跳過了最難的營帳導航,只剩「送指定次數的確認鍵
   選滿出戰門檻人數」這個相對機械、doc91 既有文件(15/19 門檻)已經記載過具體數字的問題,
   比破解 camp-map 的圍籬缺口座標容易得多,而且一旦解開就能讓這 6 章直接進到部署/戰鬥
   階段,是本輪掃描找到的最具體、最快能拿到下一個里程碑的路徑。
2. **其次:解開「營帳」通用場景的圍籬缺口/出口觸發座標**——ch02 與其餘多章的 post-load
   營帳地圖截圖逐位元組相同,其餘章節則是同一套機制的不同美術 skin,證實這是全遊戲共用的
   樣板場景。解開任一章節等於解開所有共用同一樣板的章節(本輪掃描顯示至少 22/30 章屬於
   這一類),是次高投報率的單點突破口。建議改用反組譯手段(地圖 collision/exit-trigger
   表)而非繼續盲目試方向鍵——本輪已用完合理的即時互動式試錯預算(約 30+ 次即時按鍵嘗試
   橫跨 5 個獨立 launch)。
3. **早期章節需要一份章節推進與 roster 同步的存檔序列**,而不是單一晚期存檔反覆 patch
   章節 byte——如果能取得/合成一系列「ch01 剛好 N 人」「ch05 剛好 M 人」的存檔(例如沿用
   `docs/data/chapter_beats/ch*_post.json` 的 join 序列反向合成),可以排除上面記錄的
   「早章節+晚期滿編隊伍」caveat,讓早期章節(尤其 ch01)的掃描結果更可信。
4. 一旦通用導航、prep-select 選人邏輯、或至少「營帳」場景任一項解開,應該重跑本工具的
   Phase 1 驗證(ch02/ch27/以及新解開的章節),確認 mass-kill+End-Turn 核心邏輯真的能
   端到端觸發一次 live 勝利轉場,而不是只靠 doc98 記錄的靜態核對。

## 2026-08-27 續輪(instance `winverify`/`probe3`/`probe4`):找到並修復三個真正的假陽性 bug,「mass-kill+End-Turn 從沒真的端到端觸發過 live 勝利」的疑點徹底釐清——但發現一個更深、doc58 自己也沒解開的獨立卡關點

### 派工背景與誠實結論先講

派工單指出一個深刻矛盾:即使 camp-exit 導航已解、敵人已掃描/標記死亡/End-Turn 已送出,**沒有任何一章真的觸發過勝利轉場**,連 doc58 續六十二(這個專案唯一一次人工即時操作到真正勝利+深入結局montage的紀錄)最佳驗證過的 ch27,自動化路徑重跑也從未重現過 47 個敵人。本輪目標:逐行比對本工具實作與續六十二的真實操作序列,找出差異。

**結論:找到 3 個真正的邏輯 bug,全部修復並 live 驗證;修復後 ch27 用全自動路徑(而不是人工逐鍵)真的複製出續六十二 §3 記錄的完整勝利後 montage 場景(13 人隊伍圍站藍色房間+CG 天空島嶼+詩句捲動文字+萊汀角色卡,逐項截圖比對吻合)——這是本專案第一次用全自動化工具(而非人工即時操作)重現這個此前只有續六十二一次成功記錄的結果。但 chapter byte 依然沒有在任何一次自動化跑批裡前進**,原因是一個全新發現、doc58 續六十二自己也沒解開的獨立問題(見下方「新發現的深層卡關點」)——誠實地說,M5 驗收依然沒有任何一章達成`pass`。

### 找到並修復的 3 個 bug

1. **`attempt_camp_exit()` 的「偵測到戰鬥」判定太早鬆手**:原本邏輯是`read_battle_array_base()`一讀到「看起來合理」的指標就視為「已進戰鬥」,結果即時 log 顯示 ch27 在送出「要進入戰場嗎?YES」確認後,**送出 0 次額外 Return 就宣稱找到戰鬥**——因為出戰人數選人畫面(「出戰人數 X15/剩餘人數 X15」+ roster 網格)本身在載入瞬間就已經有一個合理指標,指向一個只有 1 筆記錄的暫存 placeholder,不是真正的戰鬥陣列。後續的被動 settle loop(只 sleep+重讀記憶體,從不送按鍵)因此永遠卡在這個 placeholder 上。**修復**:改為要求敵人掃描找到`>=2`筆記錄(`REAL_BATTLE_MIN_ENEMIES`)才算數。
2. **`>=2`敵人記錄仍然不夠,找到第二個假陽性**:live 重現(instance `probe3`,ch27)證實出戰人數選人畫面之後還有一段完整的 BOSS 開場過場(敵方機甲喊話「命令確認,目標位置標定...2秒後動作」→攻擊特效→我方角色慘叫反應→敵方繼續喊話「制御及管理中樞」→鏡頭切到部隊行軍畫面→……),而**戰鬥陣列在這整段過場開始前就已經完整配置好(47~50筆記錄)**——本工具原本的「螢幕不像對話框」啟發式判定(`screen_looks_like_dialogue()`,量測畫面下半部顏色變異數)在這段過場的「無文字框鏡頭切換」瞬間也會誤判成「已脫離對話,可以停手」,實測踩到兩次獨立的假陽性畫面。**修復**:改用 doc58 大量「續」條目共同記錄過的正牌訊號——畫面左下角「NNN A+XX D+XX」戰鬥 HUD 小框(真正玩家可操作游標時才會出現),`screen_shows_battle_hud()`裁切固定區域量測「HUD 藍」像素比例。校準/驗證時又踩到第三個假陽性(「要進入戰場嗎」對話框裡莎拉的頭像衣領剛好是同一種藍、選人畫面的「剩餘人數」面板剛好用同一個佈景藍 `(56,85,154)`),最終做法是**HUD 藍偵測 AND 上「非對話框」變異數判定**,在本輪蒐集到的 14 張正/負樣本截圖上全數正確分類。
3. **`confirm_end_turn()` 漏了續六十二紀錄的第一步「移動游標到空地格」**:原本直接送`Return`開啟指令環,但游標預設停在部隊某個單位身上,`Return`會對該單位做別的操作(live 觀察到 HUD 血量從 823 變成 990,證明選到了不同單位),不會開啟系統選單環。**修復**:先送一次`Up`(live 驗證在 ch27 這個部署佈局下,單一次`Up`就能把游標移到部隊上方的空地格,HUD 正確變成只顯示「A+05 D+00」地形加成、無角色頭像——這是章節/佈局相關的座標,不是通解,但遠比完全不移動游標正確)。另外順帶 live 澄清了一個 doc58 內部的小矛盾:指令環**不會**預設停在 END 上(某早期續記錄的說法),直接`Enter`會誤開「上」方向的戰況總覽子選單;必須先`Down`選到 END 再`Enter`,這與續六十二的原始記錄一致。

修復 1+2 用`tools/dosbox_harness.sh`獨立 instance(`winverify`)逐步截圖驗證,修復 3 用另一個獨立 instance(`probe4`)手動重播「移到空地→開環→Down→Enter→YES」全程截圖佐證,最後用**修好的`fd2_chapter_sweep.py`本身**(不是手動操作)重新掃 ch27,log 顯示`attempt_camp_exit`在 41 次 tap 後(非常接近續六十二記錄的「約45次」)透過 HUD 偵測+50 筆敵人記錄正確確認進入真正戰鬥,mass-kill 50 格死亡 signature,End-Turn 序列送出後畫面**真的**跳轉到 13 人圍站的藍色房間勝利場景。

### 新發現的深層卡關點:勝利後 montage 需要繼續送 Return 才能推進,而其中一張角色卡片(悠妮)會無限循環,擋住 chapter byte 前進所需的 autosave

`confirm_end_turn()`確認 YES 之後**不會立即存檔**——會進入續六十二 §3 記錄過的完整勝利後 montage(隊伍對話→2 張全螢幕 CG→詩句捲動文字→逐位角色回顧卡,依加入順序一張一張)。本輪用`probe4` instance 逐步推進,**逐項截圖比對跟續六十二完全吻合**(隊伍圍站場景→天空島嶼CG→詩句文字→萊汀角色卡文字逐字相同)。但推進到**悠妮的角色卡**時,重現了續六十二 §3 早就記錄過、標記為「唯一尚未解開的小尾巴」的同一個症狀:文字只在 2 段之間來回循環,無論送什麼按鍵都無法前進到下一位角色。本輪額外測試了續六十二沒試過的按鍵組合(`Right`/`Down`/`Up`/`Left`/`Space`/`Tab`)以及一次 20 秒純等待(排除「需要真實 wall-clock 時間」假說),**全部沒有效果**,與續六十二「60+次嘗試無效」的結論完全獨立吻合。**這不是本工具的 bug,是這個專案本身尚未解開、doc58 續六十二就已經誠實記錄過的開放 RE 問題**,已在`tools/fd2_chapter_sweep.py`加上`advance_postbattle_montage()`(勝利後送 70 次額外 Return 的 best-effort 嘗試,設有清楚註解說明這不保證解開卡關點),讓工具至少對「不會卡在悠妮這張卡」的章節/名冊組合保留拿到`pass`的機會。

### 修復後重新驗證:3 章(ch02/ch12/ch27)全部從「連戰鬥都偵測不到」進步到「HUD 正確偵測、敵人數合理(10/11/50)、mass-kill 正確、End-Turn 正確送出」,但依然卡在勝利後 montage,0 章拿到 `pass`

| 章節 | 舊 verdict(修復前) | 新 verdict(修復後) | 敵人數(HUD 確認為真戰鬥後) | 備註 |
|---|---|---|---|---|
| ch02 | anomaly(敵人數卡在 1,從未重現過真戰鬥) | anomaly | 10 | 42 taps 找到真戰鬥,與 ch27 同一套修復生效 |
| ch12 | anomaly(敵人數卡在 1) | anomaly | 11 | 11 taps 找到真戰鬥(這章過場對白較短) |
| ch27 | anomaly(敵人數卡在 1,續六十二的 47 從未重現) | anomaly | 50 | 41 taps,與續六十二的「約45次」非常接近;勝利轉場+montage 前段全部 live 重現 |

三章的`detail`欄位依然是`anomaly`(chapter byte 未前進),但根因已經從「工具邏輯錯誤/從未真正觸發過勝利」變成「勝利轉場已經真正觸發,卡在一個已知、獨立、doc58 自己都沒解開的 montage 卡關點」——這是本輪最重要的誠實區分,不應該混為一談。

### 對 M5 驗收的影響

M5「正常玩法可達性驗證」依然**沒有**任何一章拿到`pass`,維持不完成。但「mass-kill+End-Turn 快捷法能不能端到端觸發 live 勝利」這個更基礎的問題,已經從「doc98/99 先前只在人工操作(續六十二)成功過一次,自動化工具從未重現」變成「自動化工具本身也能可靠重現」——這對整個`fd2_chapter_sweep.py`方法論的可信度是重要的正面進展,即使還沒轉化成任何一章的`pass`。

### 下一輪建議(取代/補充上方舊建議)

1. **最高投報率:悠妮角色卡循環卡關點**——這是目前唯一擋住任何一章拿到`pass`的已知問題,續六十二和本輪加起來已經試過`Return`/`Space`/`Escape`/`Right`/`Down`/`Up`/`Left`/`Tab`+20秒被動等待,全部無效,合理懷疑需要靜態反組譯這張卡片的渲染/推進迴圈(類似 doc35 §9 結局montage renderer 那條路線)才能真正解開,不建議下一輪再重複同一批按鍵組合。
2. 若悠妮卡關點解開,`POSTBATTLE_MONTAGE_TAPS`(目前 70)可能需要視完整 13 張角色卡的實際長度往上調——本輪未能測出完整需求次數,因為在悠妮(第2張)就卡住了。
3. 建議挑一個**不含悠妮**的章節(若存在這種章節/roster 組合)重跑本工具,驗證「勝利轉場+完整 montage+chapter byte 前進」在沒有悠妮卡關點干擾時是否能端到端拿到真正的`pass`——這能把「工具本身邏輯正確」與「悠妮卡關點是唯一障礙」這個推論做一次獨立正面驗證,而不只是本輪的間接推論。

## 2026-08-27 續輪(instance `branchck02`/`branchck12`/`branchck27`,代號 `branchcheck`):派工單懷疑「ch02/ch12/ch27 全部卡在悠妮角色卡循環」是存檔建構污染(chapter byte 沒有正確路由到對應 `table_post` handler)——**徹底排除,靜態+live 雙重證實 `[0x53C03]`/`table_post` 路由機制乾淨**;真正原因是上一輪`confirm_end_turn()`的 ch27 專屬游標移動不通用,ch02/ch12 從未真的走到過真實勝利轉場

### 派工背景與誠實結論先講

派工單的假設前提是:上一輪(`winverify`/`probe3`/`probe4`)重新驗證 ch02/ch12/ch27 三章後,寫下「三章全部卡在勝利後 montage」,而先前深挖過的「悠妮角色卡永久循環」只在 ch26/ch29 專屬的戰後 handler(`table_post[26]`/`table_post[29]`,doc35 §9.11 已用純靜態反組譯證實)才應該出現——如果 ch02(`table_post[1]`)/ch12(`table_post[11]`)也走到同一個循環,合理懷疑是`prepare_chapter_save()`用同一份「原本落在 ch27」的來源存檔反覆 patch chapter byte 時,某個決定戰後分支的旗標(例如天空之鑰/其他 ch27 專屬 story-progress byte)沒有跟著清除或同步,導致 chapter byte 表面上改了、但真正決定 `table_post` 索引的某個獨立全域變數還是沿用舊值。

**結論:這個假設經兩種獨立方法查證,雙雙判定為否——存檔建構沒有污染,`[0x53C03]`/`table_post` 路由機制本身是乾淨的。** 真正造成上一輪「三章都卡住」表面現象的,是完全不同的另一個原因:`confirm_end_turn()`的游標移動步驟(送一次`Up`把游標移到空地格再開啟指令環)本身就是**只針對 ch27 特定佈署佈局校準過**的 hack(這一點該函式自己的既有 docstring 早就承認),對 ch02/ch12 完全不通用——這兩章的自動化序列很可能**從未真的走到過一場真實的勝利**,更談不上被路由到錯誤的 `table_post` handler。

### 查證方法 1(靜態):既有反組譯文件其實已經完整記錄了整條鏈路,只是先前沒人把兩份文件連起來看

`docs/data/fd2_native_chapter_slot_restore_ida.txt`(IDA Pro 9.4,已證實等級)「`0x25EBB` 的章節槽載入分支」一節,第 3 點明確記錄 LOAD 時的複製順序:

```
0x26064..0x26067：metadata +0 → [0x53C03]
```

`metadata+0`正是`tools/fd2save.py`的`set_slot_chapter()`唯一寫入的那個 byte(`plain[start + ROSTER_SIZE]`,即每個 slot 的章節 metadata byte)。而`docs/knowledge-base/35-battle-animation-rendering.md` §9.11.4 已用完全獨立的一輪純靜態反組譯證實`[0x53C03]`(文件稱「目前章節」)正是索引戰後跳表`table_post`(native `0x51de9`,32 個 4-byte handler 指標)的那個全域變數——`0x2545d`/`0x25970`(悠妮循環的呼叫端)分別落在`table_post[26]`/`table_post[29]`內部。把這兩份各自獨立、都是「已證實」等級的文件接起來看:**`set_slot_chapter()`patch 的 byte,就是 native LOAD code 複製進`[0x53C03]`的那個 byte,而`[0x53C03]`就是`table_post`的索引**——中間沒有任何已知的第二個「當前章節」來源會覆蓋或繞過它。

### 查證方法 2(live):每章節都用全新獨立 instance LOAD 後立刻讀`[0x1EFC03]`(native `0x53C03`的 live 位址),不做任何按鍵推進

方法論教訓先記錄:第一次嘗試圖省事,重複使用**同一個**已啟動的 instance,只用 30 次`Escape`嘗試退回標題畫面再重新 LOAD 下一份存檔——結果 ch12/ch27 兩次讀回的`[0x53C03]`都錯誤地等於 ch02 遺留的舊值`1`,截圖顯示`Escape`根本沒有真的退回標題,而是誤觸酒店 NPC 選單(與`_ADVANCE_KEY_CYCLE`已知的同一個陷阱),讀到的是**同一個從未真正 reload 過的 stale 遊戲 session**,不是三次獨立的 LOAD。**改用`sw.launch_instance()`為每個章節開全新 instance(`branchck02`/`branchck12`/`branchck27`,一次一個,teardown 後才開下一個)後,結果乾淨一致**:

| 章節 | patch 進去的 raw chapter | LOAD 後立刻讀到的 live `[0x53C03]` | 結論 |
|---|---|---|---|
| ch02 | `0x01`(1) | `1` | 完全吻合 |
| ch12 | `0x0b`(11) | `11` | 完全吻合 |
| ch27 | `0x1a`(26) | `26` | 完全吻合(這是 ch27 原本就有的值,不能單獨排除污染,但作為既有基準保留) |

三章 100% 精確吻合,沒有任何一次殘留舊值——**這代表章節跳轉的 patch 機制本身是乾淨的,LOAD 後 `[0x53C03]` 就是我們要的那個章節,不是遺留自來源存檔原本的 ch27。**

### 那上一輪的「ch02/ch12/ch27 全部卡在勝利後 montage」是怎麼回事?回頭看`chapter_sweep_v7`實際截圖,三章其實走到了三個完全不同的畫面

派工單引用的「三章重新驗證後全部卡在勝利後 montage」出自本文件上一節,對應`.wsl_build/chapter_sweep_v7/`(2026-08-27 11:25-11:36,`9e1557d0`修復後的最新一輪)。本輪重新逐張比對該輪的`post_end_turn.png`/`post_montage_advance.png`(不是重新跑,是回頭核對既有證據),發現三章**並沒有**走到同一個畫面:

- **ch27**:`post_end_turn.png`正是續六十二記錄的「13 人圍站藍色房間」真實勝利轉場,`post_montage_advance.png`(再送 70 次 Return 後)是`索爾`與另一名角色相對而立的天空 CG 畫面——與 montage 流程吻合,合理推測繼續往下会走到悠妮卡。**這是唯一一章真的走到過真實勝利轉場的**。
- **ch12**:`post_end_turn.png`是一句 NPC 對白「『哎呀,有救了有救了!救命啊!』」疊在森林戰場地圖上——**這根本不是勝利轉場,是戰鬥仍在進行中的普通對話事件**。也就是說`confirm_end_turn()`送出的`Up`→`Return`→`Down`→`Return`→`Return`序列,對 ch12 的部署佈局完全沒有照設計運作(游標大概率移到了別的單位或劇本觸發格上),整場戰鬥根本沒有真的結束。
- **ch02**:`post_end_turn.png`是一張**可行走的營帳/教會地圖**,角色站在教堂門口——同樣不是任何形式的勝利 montage,看起來像是脫離了戰鬥回到某種營地場景(是否為真實勝利轉場導致的正常回城、抑或是誤觸別的流程,本輪未進一步查證,誠實列為未決)。

**這代表上一輪「三章全部卡在勝利後 montage」的措辭不精確**——ch02/ch12 根本沒有走到「勝利後 montage」這個階段,更遑論悠妮卡循環;只有 ch27 真的走到了。這也直接解釋了本輪派工單一開始的疑慮從何而來(措辭上的「卡在 montage」被誤讀/誤傳成「卡在悠妮卡」,再被合理但錯誤地懷疑成路由污染)。

### 真正原因:`confirm_end_turn()`的`Up`游標移動是 ch27 專屬 hack,對其他章節的部署佈局不通用

`confirm_end_turn()`自己的 docstring 早就承認這一點(「這是章節/佈局相關的座標,不是通解」),但先前沒有一輪用不同章節的真實截圖直接驗證後果。本輪(見上表)第一次直接對照 ch12/ch02 的`post_end_turn.png`,證實**後果就是整個 End-Turn 確認序列在 ch27 以外的章節會走偏**,不會真的打開指令環、選 END、確認 YES——遑論觸發`table_post`路由。也不能排除`docs/knowledge-base/99-chapter-sweep-results.md`已記錄的「早章節+晚期滿編隊伍」roster 大小不匹配 caveat 是部分成因:ch02/ch12 的合成存檔沿用來源存檔完整的 13 人晚期隊伍(`estimate_roster_size(2)=2`/`estimate_roster_size(12)=9`都小於既有 13 人,`prepare_chapter_save()`目前的政策是不裁減),部署佇列的形狀因此跟真正的 ch02/ch12 存檔不同,讓一個寫死方向的游標移動更不可能剛好通用。

### 對 M5 驗收與工具本身的影響

**沒有修改`fd2_chapter_sweep.py`的存檔建構邏輯**——因為兩種獨立方法都證實它沒有問題,強行「修復」一個不存在的 bug只會混淆之後的除錯。已在`confirm_end_turn()`加上一段長註解記錄本輪的排除結果與正確診斷,防止未來輪次重複懷疑同一個已排除的假說。M5 的整體 verdict 分布**維持不變**(0 pass,`chapter_sweep_v7`的既有結果不重跑不失效):本輪的價值是**排除一個看似合理但錯誤的假說**,並把「三章卡住」的籠統措辭訂正為三個具體、彼此不同、都跟悠妮卡無關的個別現象,而不是產生新的 pass。

### 下一輪建議(取代派工單原本「驗證 ch02/ch12 win 路由到正常轉場」的目標——那個目標的前提假設已被排除,不再適用)

1. **最高投報率:讓`confirm_end_turn()`的游標移動通用化**——不要繼續寫死`Up`,改成對 4 個方向逐一嘗試(送方向鍵→截圖→用 HUD 框「有沒有角色頭像/HP 數字」而不僅是「有沒有 HUD 藍色」做更細的分類,空地格應該只有地形加成數字、沒有頭像跟 HP)找到第一個「確認是空地格」的方向,而不是假設任何單一方向對所有章節都成立。這需要至少 2-3 章的即時互動式校準(類似`winverify`/`probe4`那幾輪的做法),不是本輪範圍。
2. **獨立查證 ch02 的`post_end_turn.png`實際上代表什麼**——是`confirm_end_turn`的錯誤序列意外觸發了某種「離開戰鬥回營地」流程(如果是,這本身可能是另一個值得深究的線索),還是純粹的游標移動誤觸事件對白/移動。本輪未展開這條線,誠實列為未決。
3. 建議 1 解開後,重跑 ch02/ch12(以及理想上再挑 1-2 個不同部署佈局的章節)完整 sweep,才能真正回答「非 ch26/27/29 章節的勝利是否正確路由到不同的 `table_post` handler、且不含悠妮卡循環」這個仍然開放的問題——本輪的`[0x53C03]`靜態+LOAD 後 live 核對已經確認**路由機制本身沒有問題**,缺的只是「讓 ch02/ch12 真的打完一場戰鬥拿到勝利」這個純技術性的通用化步驟。
