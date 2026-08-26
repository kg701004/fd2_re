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

## 下一輪建議

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
