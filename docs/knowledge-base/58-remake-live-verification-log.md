# 58 — Remake 全流程逐章即時操作驗證日誌

> 目的：用電腦操作能力真的打開 DOSBox 跑原版 `FD2.EXE` 和 remake `fd2.exe`（正式流程
> `FD2_CAMPAIGN=assets/scenarios/campaign_full.json`，同 `play.sh`），逐章逐機制比對，
> 記錄每一項確認結果、每一個發現的差異/bug、每一個修正與其驗證證據。
>
> 本篇是「執行紀錄」，不是設計文件——結論性知識確認後應回填 `42`/`56`/`91` 等既有文件，
> 這裡保留的是「什麼時候測了什麼、測出什麼、怎麼修的」逐項時間線。
>
> 啟動指令慣例：
> - DOSBox 原版：`"/c/Program Files (x86)/DOSBox-0.74-3/DOSBox.exe" -c "mount c <FD2目錄>" -c "c:" -c "FD2.EXE"`
> - remake 正式流程：`FD2_CAMPAIGN="assets/scenarios/campaign_full.json" ./fd2.exe`
>   （**不要**用 `FD2_CAMPAIGN=1`——那個簡寫指向另一個較小的 `assets/scenarios/campaign.json`，
>   `start: intro`，不是玩家真正會走的流程；也不要不加任何環境變數直接執行，那是開發用的
>   「快速單場戰鬥」捷徑，跳過全部開場過場，且已知會讓主角隊堆疊在同一格。）
> - 需要逐拍除錯時加 `FD2_CUTSCENE_LOG=1`（記到 stderr，每個 beat 的 source/line/script/scene）。

## 環境已知問題（跟 remake 本身無關，但會干擾操作，先記錄）

1. **DOSBox `cycles=auto/max`**：模擬速度不設上限，短暫等待可能已經讓 DOSBox 跑過好幾個原本場景，
   不能用「等 N 秒再截圖比對」的方式比對兩邊——要逐步驟（每次都按同一顆鍵）比對，不能比時間點。
2. **背景焦點搶奪**：這台機器上有背景程式（觀察到 `Lgdisplayservice`、`Textinputhost` 交替出現）
   會不定期搶走前景焦點，導致送出的按鍵完全進不了遊戲視窗，畫面看起來像卡住但其實只是輸入沒送到。
   徵狀：`computer-use` 的 `key`/`left_click` 回傳「XXX is not in the allowed applications and is
   currently in front」錯誤。解法：請使用者手動關閉那個背景程式，或至少點擊一次目標視窗奪回焦點。
3. **背景程序在對話輪次之間會被殺掉**：`./fd2.exe &` 這類背景啟動的進程，如果是在某一輪對話裡用
   Bash 工具啟動的，下一輪對話開始時底層 shell 可能已經重置，進程隨之消失（DOSBox 不受影響，啟動
   方式不同）。每次新一輪要操作前，先用 `tasklist | grep fd2.exe` 確認進程還活著，不活著就重新啟動。

## 環境已知問題（續，2026-08-13 補）

4. **Draw() 偶爾停止更新畫面,但 Update() 邏輯照常跑**：F3 除錯疊字（`T%d own%d ally%d enemy%d
   cur(%d,%d)`，由 Windows 原生視窗標題列文字呈現，跟遊戲畫面本身走不同的更新路徑）持續正確反映
   最新游標座標，但畫面本體（單位、選單、高亮）卡在舊的一幀不動，連續多次 Enter/Escape/方向鍵
   看起來「完全沒反應」。用視窗「最大化/還原」按鈕強制一次 repaint 後，畫面立刻跳到跟 F3 文字
   一致的真實狀態。判斷方法：F3 文字持續變 = 輸入有送到、邏輯有在跑，只是畫面沒重繪，不是卡死。
   解法：每次要判讀畫面前先點一下最大化/還原鍵強制重繪，再截圖確認。
5. **指令環的方向鍵導航（`ringInput()` 內的 ↑↓←→，跟地圖游標移動是不同的輸入路徑）比地圖游標
   移動更容易掉輸入**：地圖游標移動這次 session 測了幾十次幾乎全部正常，但指令環內導航同一顆
   方向鍵連續按 3 次都可能完全沒反應（`g.ringSel` 未變），即使畫面已確認是最新一幀（見上一條）。
   `computer-use` 工具有一次明確回傳「no app is frontmost (focus anomaly)... 剩下的輸入沒有送達」
   的錯誤，證實這是真的焦點流失，不是遊戲邏輯問題；但確切為什麼偏好在這個特定輸入路徑掉字還不
   確定。目前唯一可靠解法：卡住時請使用者手動接手鍵盤操作那一步。

## 已修正的三個真實 bug（2026-08-13，詳見對應 commit/diff）

### Bug 1：`spawn_intro` beat 在沒有原版 FDOTHER.DAT 時讓整個 cutscene 永久卡死
- **徵狀**：全新開局（無 FDOTHER.DAT）在第一章「發現昏迷的悠妮→機器人蓋亞警告→抵達戰場」過場後，
  畫面停在一片空地圖（水域+森林+小屋，無隊伍、無對話框），不回應任何按鍵，F3 除錯疊字也不出現
  （因為 `legacyViewport` 仍為 true，代表過場狀態機根本沒有前進）。
- **根因**（逐層 code trace 確認，非猜測）：
  1. `FD2_CUTSCENE_LOG=1` 顯示最後一條記錄的 beat 是 `op=spawn_intro source=0x3289b`，之後完全沒有
     後續紀錄——beat runner 在這裡停了。
  2. `cmd/fd2/main.go` 的 `case "spawn_intro"`：當 `b.Source != ""`（原生路徑）一律呼叫
     `startNativeSpawnIntro`，它會經 `buildNativeIndexedTransitionInputForActors` →
     `buildNativeIndexedTransitionInputForState`（`native_indexed_transition.go`），該函式明確檢查
     `!nativeMapAssetsAvailable(a)`，沒有原版 FDOTHER.DAT 就回傳錯誤
     `"native map assets/field unavailable"`。
  3. 這個錯誤存進 `g.loadErr`，然後 `case` 直接 `return`——不呼叫 `g.beatAdvance()`，後續所有 beat
     都不會再執行。
  4. **`g.loadErr` 全遊戲只有 `g.m == nil`（地圖沒載入）那個早期分支才會顯示給玩家看**
     （`Draw()` 裡 `"FD2 重製 MVP\n缺 assets/..."+g.loadErr` 那行）。這個情境地圖是有載入的，
     所以錯誤訊息完全不可見——玩家只看到卡死，沒有任何提示。
- **修正**（`cmd/fd2/main.go` `case "spawn_intro"`）：
  1. 原生路徑前置檢查 `nativeMapAssetsAvailable(g.nativeMapAssets)`；不可用時直接跳過原生嘗試，
     退回跟 `b.Source == ""` 完全一樣的陽春路徑（`AppendGroupWithNativePlacement`/
     `materializeStoryGroup` + 固定 `beatDelay`），動畫效果變陽春但流程保證能繼續。
  2. `Draw()` 新增一個 defer：只要 `g.loadErr` 非空就在畫面上疊字顯示（不管是哪個分支提早
     return），作為安全網——即使將來又有其他 beat 失敗，至少玩家/測試者看得到原因，不必再靠
     `FD2_CUTSCENE_LOG` 才查得到。
- **回歸測試**：`cmd/fd2/beatrunner_test.go`
  `TestBeatSpawnIntroWithoutNativeAssetsFallsBackToPlainSpawn`——沒有原生素材時斷言
  `g.loadErr==""` 且群組確實被加入（`len(g.st.Units)==2`）且 `g.beatDelay` 有設定（不是卡死）。
- **即時驗證**：見下方「第一章」章節，重跑整段開場過場，海盜正常登場+對話正常播完+進入可操作戰鬥地圖，
  游標按方向鍵確實移動。

### Bug 2：DOSBox vs remake 比對用錯啟動方式（不是 remake 的 bug，記錄避免重蹈覆轍）
- 第一次示範時直接執行 `./fd2.exe`（無環境變數）＝開發用「快速單場戰鬥」捷徑，跳過整個開場過場，
  這是 `play.sh` 註解本身就講明的已知行為（甚至註明這模式下「主角隊會堆在同一格」）。
- 第二次用 `FD2_CAMPAIGN=1`，以為等同「啟用正式流程」，但這個簡寫實際指向
  `assets/scenarios/campaign.json`（`start: intro`，內容較小/舊），不是 `play.sh` 用的
  `campaign_full.json`（`start: story_ch00_handler`）。
- 兩次都不是玩家真正會走的路徑，導致誤以為「remake 跳過開場」——後來用正確指令
  （`FD2_CAMPAIGN=assets/scenarios/campaign_full.json`）重新驗證，開場流程與 DOSBox 完全一致
  （見下方逐行對白比對）。

### Bug 3：移動後開道具/原始指令選單，攻擊射程紅色高亮沒有一起關掉，疊在選單底下（使用者截圖回報）
- **徵狀**：單位移動後開指令環，選「道具」（ringSel=2）而非「攻擊」，畫面上半透明的道具選單
  （`[1] 00h`/`[2] 84h`/... 那個面板）跟一個橘紅色十字形高亮同時疊在一起，高亮明顯是攻擊選目標
  階段的殘留（使用者截圖直接證實）。
- **根因**：`main.go:6481` 這格「攻擊射程高亮」的顯示條件是
  `g.castSp == nil && g.moved && !g.ring && !g.spellOpen`——只排除了法術選單，漏了道具選單
  （`itemOpen`）跟原始指令選單（`nativeCommandOpen`）。同一份檔案 340 行前（6149 行）的
  `expandableView` 判斷式其實已經把 `itemOpen`/`nativeCommandOpen`/`spellOpen` 三個一起排除了——
  這裡漏抄一次。
- **修正時追加發現的第二個實例**：`nativeCommandOpen` 選定某個原始指令、進入它自己的選目標子階段
  (`nativeCommand0Targeting`) 時，程式碼會把 `nativeCommandOpen` 設回 `false`（main.go:4210）——
  代表原本只補 `!g.nativeCommandOpen` 在這個子階段完全不生效，同一顆漏洞的第二個觸發點，一併補上
  `!g.nativeCommand0Targeting`。
- **確認沒有第三個漏洞**：道具選單自己的兩個子階段（`nativeItemTargeting`/`nativeItemRelocating`）
  不需要額外補——清面板的 `clearNativeItemPanel()` 故意不動 `itemOpen`，所以整段子階段 `itemOpen`
  都還是 `true`，`!g.itemOpen` 一個條件就全涵蓋。
- **修正**：`main.go:6481` 加上 `&& !g.itemOpen && !g.nativeCommandOpen && !g.nativeCommand0Targeting`。
- **回歸驗證**：`go build`/`go vet`/`go test ./...` 全綠，尚未實機截圖複測（下次進戰鬥時一併看）。

### 功能缺口：戰鬥指令環選中格沒有原版該有的閃爍/脈動效果（使用者實機比對回報，非 bug，是缺功能）
- **使用者觀察**：原版執行時，選單游標移到哪個選項，那格會有明顯的視覺回饋（使用者描述為「跳動」）；
  remake 的指令環選中格只有一個純色靜態外框（`main.go` 原 `border(x, y, color.RGBA{0xff, 0xa8, 0x20,
  0xff})`），完全沒有逐幀變化。
- **對照**：同一份 codebase 裡城鎮/教會/商店/轉職選單（`nativeTownUIPulse`/`nativeChurchUIPulse`/
  `nativeShopUIPulse`/`nativeClassUIPulse`）都有一個反組譯自原版的選中格脈動效果（例：城鎮
  `stepNativeTownUIPulseTick` 對應原版 `0x2d1b5`），用 4-tick BIOS 時鐘 delta 驅動一個 0-3 循環計數器，
  church 那組甚至有測試檔案直接叫 `TestComposeNativeChurchMenuFramePulsesOnlySelectedCell`。
  戰鬏指令環（`drawRing`）當初是獨立手刻的一條路徑（原生素材版走 `drawNativeActionOverlay`,
  classic 後備版才是這個純色外框；兩條路徑都沒有選中格脈動），從未移植這個效果過去。
- **doc13 現狀**：`51-remake-playtest-gaps-r2.md` 第 19 行只確認 doc13 對戰場選單「狀態機」本身
  （`0x18ED0`/`0x18890`）有反組譯基礎，並未特別提到選中格脈動的確切時序/位址——這個菜單自己的
  脈動節奏目前沒有對應到具體反組譯位址。
- **這次的處理方式（誠實記錄，非逐位址反組譯的忠實移植）**：沿用 town/church 那組已證實的節奏
  （4-tick BIOS delta、0-3 循環計數器，`nativeBIOSClock`），新增 `ringPulse`/`ringUIClock`/
  `resetRingPulse()`/`stepRingPulseTick()`（`action_overlay_runtime.go`），`ringPulse>=2` 時選中框
  顏色從亮橘（`0xff,0xa8,0x20`）切到暗橘（`0xb0,0x74,0x16`），在 `beginActionOverlayOpen()` 時重置。
  這是「跟其他選單風格一致的近似還原」，**不是**確認過位址的原版逐位元組複製——如果之後真的反組譯
  出這個選單自己的脈動位址（時序、狀態數、顏色表都可能跟 town/church 不同），要回來對照更新，
  不要誤把這次的近似值當成已證實的原版行為。
- **回歸測試**：`action_overlay_runtime_test.go`
  `TestRingPulseUsesFourTickSignedDelta`（沿用 `TestNativeTownPulseUsesFourTickSignedDelta` 同一組
  tick 序列跟 int16 wrap 邊界）、`TestRingPulseSubFourTickDeltaDoesNotAdvance`、
  `TestBeginActionOverlayOpenResetsRingPulse`。`go build`/`go vet`/`go test ./...` 全綠，尚未實機
  截圖複測。

---

## 序章（ch00，王城傳位→王城偶遇→比劍邀約）— 已比對，一致

逐句核對 remake 畫面文字 vs `assets/story/ch00_palace.json`/`ch00_meadow.json` 原始劇本（RE 來源
`FDTXT_033`/等），以及 DOSBox 原版畫面：

| 場景 | remake 顯示 | 來源script | 結果 |
|---|---|---|---|
| 王座廳,傳位 line0 | 『兒臣索爾，晉見父王陛下。』 | 同字 | 一致（DOSBox 小字體肉眼誤讀成「臣兒」，核對 script 後確認是我看錯，不是差異） |
| 王座廳,傳位 line6起 | 『索爾，時間過得真快...』 | 同字 | 一致 |
| 王城一隅,亞雷斯撞見 | 『哈！找你找了半天...』 | 同字 | 一致 |
| 比劍邀約/發現悠妮與蓋亞 | 悠妮自我介紹「我叫。。悠妮吧」、蓋亞「不要再接近！否則我將照規定採取防衛行動！」 | 同字 | 一致 |

**結論**：序章開場過場（`story_ch00_handler` → `handler_binding: assets/cutscenes/bindings/ch00_pre.json`
編譯出的完整 beat 序列）內容與原版完全一致，這條路徑的問題只有上面 Bug 1（卡死），內容本身沒有落差。

## 第一章（ch01，抵達馬拉大陸→海盜伏擊→戰鬥）

### 開場過場（登陸→海盜伏擊）— 已比對，一致（修好 Bug 1 之後）

| 對白 | remake 顯示 | 來源script (`assets/story/ch01.json` scene 0) | 結果 |
|---|---|---|---|
| line0 索爾 | 『累死了，大家休息一下吧！』 | 同字 | 一致 |
| line1 亞雷斯 | 『聽說再越過這片海洋就到馬拉大陸了...』 | 同字 | 一致 |
| line2 索爾 | 『好極了。悠妮，妳....嗯，坐了這麼久的船，有點累吧？』 | 同字 | 一致 |
| line3 悠妮 | 『嗯，還好。海風吹起來真舒服啊....』 | 同字 | 一致 |
| line4 遠處 | 『...!!!』（純標點，無頭像/名字框——原始劇本就是這樣寫的） | 同字 | 一致（不是 bug，是遠方慘叫的刻意留白台詞） |
| 海盜出現 場景 line0 海盜甲 | 『瞧！竟有呆鳥在這小島上休息，真是天上掉下來的肥肉。』 | 同字 | 一致（**Bug 1 修好後才看得到，之前卡死在這之前**） |

### 戰鬥地圖進場 — 已驗證

- 過場結束後正確進入可操作戰鬥地圖：白色游標框可見，隊伍散開部署（非堆疊），敵方海盜部署在地圖
  另一側，符合 `play.sh` 描述的「ch01 散開部署」。
- 方向鍵移動游標：按一次 `Right`，游標框確實從 (557,468) 移到 (597,468)（螢幕座標，即右移一格）。

### 選取單位/移動範圍/指令環/待命 — 已驗證，全部正常

- **選取單位**：游標移到藍帽隊員上，左下正確跳出地形加成面板「A+05 D+00」+ 頭像（對照原版樣式，
  這正是這次 session 稍早修好的 `drawTerrainInfoPanel`）。按 Enter 選取。
- **移動範圍顯示**：選取後正確顯示淺藍菱形移動範圍高亮（原版 SRPG 標準呈現）。
- **移動**：在範圍內按方向鍵移動、Enter 確認落點，單位正確移動到新位置，地形面板同步更新為
  「A-05 D+10」（換了地形，數值正確跟著換）。
- **指令環開啟**：移動確認後正確彈出四方向指令環（攻擊/法術/道具/待命），圖示是稍早這次 session
  用 `export-ring-icons` 從真實 FDOTHER.DAT 解出來的真圖（劍盾/法杖/道具袋/沙漏），不是文字後備，
  環的位置精準對齊在單位身上（這正是這次 session 稍早修好的 `drawRing` zoom/borderPx 問題）。
- **攻擊指令（範圍外）**：選「攻擊」（左方向）時彈出「此指令目前不可用」——這是**正確行為**，
  不是 bug：這個單位這步移動後，武器射程內沒有敵人（刻意先測試這個邊界情況）。
- **待命指令**：選「待命」（下方向）成功執行，指令環關閉，單位停留在新位置完成行動，游標仍停在
  該單位格上。

### 環境干擾造成的一場誤診（記錄避免重蹈覆轍）

移動亞雷斯試圖靠近海盜時，游標移到菱形範圍最靠近海盜的兩格，按 Enter 一直沒有反應（單位沒有
移動、指令環沒開），一度懷疑是「移動範圍顯示比實際可達範圍還大」的真實 bug。追查後排除：

1. 中間過程有再次遇到背景搶焦點問題（同開頭記錄的 Lgdisplayservice/Textinputhost），確認方法：
   換一顆方向鍵測試游標是否還會動——會動就代表輸入有進去，Enter 沒反應是遊戲邏輯不接受，不是
   輸入沒送到。
2. 排除輸入問題後，直接查 `cmd/fd2/main.go` 的 `confirm()`：移動確認條件是
   `g.reach[cur] && g.st.UnitAt(g.curX, g.curY) == nil`——**目標格必須真的沒有單位**，
   佔用中的格子會被靜默拒絕（不回訊息、不移動、不開環），原版邏輯上完全合理（不能疊在敵人格上）。
   我在螢幕座標换算格子時，最靠近海盜的那兩格極可能剛好换算成海盜本尊所在格（或緊貼到判斷成同格），
   換到中間範圍的格子後同樣操作立刻正常——支持「換算誤差」而非「範圍顯示 bug」的結論。
3. **沒有找到程式碼層級的證據支持「移動範圍顯示比實際可達範圍大」**，所以這條先不列為 bug；
   之後若要徹底排除，需要用 F3 除錯疊字讀出游標的精確格子座標再逐格比對，這次沒有做到那麼精確
   （F3 在互動戰場應該會顯示 `T%d own%d ally%d enemy%d cur(%d,%d)`，之後驗證應該優先開著)。

### 移動範圍排查（使用者回報「搆不到攻擊位置」，2026-08-13）

使用者實機操作時回報「移動限制到不了可以攻擊敵人的位置」，並指出這代表沒有仔細對照原始檔。
完整排查過程與結論：

1. **用跟 `Reachable()` 完全相同的演算法（四方向 BFS + 地形成本 + MV 截斷）重算真實
   `map0`/`map0_units.json` 資料**，逐一測試 4 個部署格（`own_deploy`）到敵方海盜群
   （`group=2`）的可達性：部署格 0/2/3 用 `MV=6` 都能搆到攻擊位置，**部署格 1 `(10,21)`
   用 `MV=6` 完全搆不到（0 個攻擊位置），要 `MV=7` 才行**。索爾 `MV=6`、亞雷斯 `MV=7`
   （`ch01.json` party 區塊）。結論：如果操作的單位剛好在部署格 1 且 `MV≤6`，這回合真的
   搆不到——這是部署位置離敵人遠近不均的正常 SRPG 設計，不是移動範圍算錯。
2. **排查過程中確認了一個真實的結構性落差**：`internal/battle.Unit` 完全沒有「移動類型」
   （步行/騎兵/飛行）欄位，但 `docs/knowledge-base/02-game-data-reference.md` §3.1 明確
   記載原版地形成本依單位類型分三欄不同（森林:步行-1/騎兵-2/飛行-1；沼澤:步行-2/騎兵-3/
   飛行-1）。`move.go` 的 `MoveCost()` 不管誰在走都查同一張表。
3. **確認影響範圍**：查了全部 33 張地圖的 `cost` 陣列，只有 `map19`（**第 20 章
   `battle_ch20`**）有非 1/99 的值（709 格=2）；`map0`（目前測的這章）只有 1/99 兩種值，
   這個落差對第一章零影響。

**修正**（`internal/battle/move.go`、`model.go`）：
- `Unit` 新增 `MoveType`（`MoveWalk`/`MoveCavalry`/`MoveFly`，零值 `MoveWalk`）。
- 新增 `MoveCostFor(u, x, y)`：`MoveWalk` 完全等同原本 `MoveCost`（零行為改變）；
  `MoveCavalry`/`MoveFly` 時用 `NativeTerrainMoveCodes`（已經是 Load 時就讀進來、給
  AP/DP 地形加成用的同一顆 FDSHAP control byte 資料，`nativeTerrainKind` 重用同一份
  0/1/5=平地、2/3=森林、4=沼澤 分類，跟已證實的 `indexedmap.NativeMapHUDTerrainAPDP`
  同源）換算差異化成本；沒有地形資料時退回原本 `MoveCost`，不假造地形類型。
  `Reachable`/`Path` 都已改呼叫這個新函式。
- **刻意沒有把任何角色標成騎兵/飛行**：原版哪個職業對應哪個移動類型，目前沒有反組譯
  確認的資料來源，用猜的標反而會引入新的不準確。管線先接好，等資料來源確認後再回填
  （見 `docs/knowledge-base/42-re-vs-remake-gap-audit.md` 對應列）。
- **回歸測試**（`internal/battle/move_test.go`）：`TestMoveCostFor_WalkUnchanged`、
  `TestMoveCostFor_CavalryForestAndSwamp`、`TestMoveCostFor_FlyIgnoresTerrain`、
  `TestMoveCostFor_MissingTerrainCodesFallsBackToBase`、
  `TestReachable_CavalryForestCostsMoreThanWalk`。`go build`/`go vet`/`go test ./...`
  全綠，尚未實機驗證（等第 20 章）。

### Bug 4：攻擊沒命中時顯示「造成 0 傷害」，應該顯示「未命中」（使用者實機回報，2026-08-14）
- **徵狀**：使用者手動操作攻擊，訊息顯示「XX 攻擊 YY,造成 0 傷害」，看起來像是打中了但沒傷害，
  容易誤以為攻防數值有問題。
- **根因**：`main.go` 有兩處（玩家攻擊 `confirm()`、AI/友軍攻擊 `aiStep()`）呼叫的是
  `battle.State.Attack(a,d) int` 這個簡化版介面，它的文件本身就寫明「Miss 時為 0」——
  0 這個值原本就是「沒打中」的旗標，不是「打中但沒傷害」。但這兩處 UI 訊息組字完全沒檢查
  這個旗標，無條件套用 `"%s 攻擊 %s,造成 %d 傷害"`，導致沒命中時顯示出的字面意思是
  「打中但造成 0 傷害」。而 `AttackWithRNG` 本身的 `dmg<1 → dmg=1` 保底（`combat.go`
  註解：「玩家命中至少造成 1」）代表**真正命中的攻擊在目前規則下絕對不可能顯示 0**——
  所以「造成 0 傷害」這句話從邏輯上就是矛盾的,只有沒命中的分支才會撞到它。
- **修正**：兩處都改成呼叫回傳完整 `AttackResult`（含 `Missed` 欄位）的 `AttackWithRNG`
  （改用 `g.rng`，跟 `CastArea`/原始指令等其他戰鬥擲骰路徑用同一個可用 `FD2_SEED` 固定的
  來源一致——副作用：近戰攻擊原本用套件層級的 `engineRand`，跟其他擲骰用不同來源，
  這次順便統一），依 `result.Missed` 分支訊息:命中顯示「造成 N 傷害」(N≥1)，
  沒命中顯示「未命中」。
- **回歸測試**：`battleevent_test.go`
  `TestConfirmAttackMessageDistinguishesMissFromZeroDamage`(兩個子測試,分別用
  `HIT=0/EV=100` 跟 `HIT=100/EV=0` 強制決定性的未命中/命中,斷言訊息文字跟 HP 變化)。
  `go build`/`go vet`/`go test ./...` 全綠。尚未實機截圖複測（下次進戰鬥時一併看）。

### Bug 5：指令環「法術/物品/待機」圖示內容錯位，選右邊卻跳物品欄（使用者實機回報，2026-08-14）
- **徵狀**：使用者描述環選單「上面是攻擊、右邊視覺上像技能、下面視覺上像物品」，選了看起來像
  技能的那格，結果卻跳出物品選單。
- **排查過程**：先確認選單方向→動作的邏輯本身沒有錯位——`pos[i]`(畫在哪)、`labels[i]`(文字
  後備內容)、`ringSel`(方向鍵設值)三處共用同一個索引 `i`，`case g.ringSel { 0:攻擊 1:法術
  2:物品 3:待機 }` 跟畫面位置(上左右下)一一對應,程式邏輯面沒有問題。接著懷疑是字體太小誤讀
  (先把 0.55 scale 的中文字級調到 0.85,但截圖比對前後完全沒有變化,才發現實際走的根本不是
  文字後備路徑)。再查才發現 `assets/ui/ring_{attack,status,item,wait}.png`(2026-08-13 才
  加入,是用 `cmd/export-ring-icons` 從玩家自己的原版 FDOTHER.DAT 資源#2 匯出的「理論上真
  原版」圖示)才是實際在畫的東西。用 Python 把 4 張圖各自放大比對,證實：`ring_status.png`
  (套在「法術」格)跟 `ring_attack.png`(套在「攻擊」格)逐 pixel 完全相同,是複製品；
  `ring_item.png`(套「物品」格)畫的是巫師帽+法杖(視覺上像法術)；`ring_wait.png`(套
  「待機」格)畫的是錢袋(視覺上像物品)——兩者視覺語意剛好對調。使用者選「看起來像技能」的
  格子，其實是程式碼裡的「物品」格(index 2)，選單邏輯正確地開了物品欄；問題全部出在這 4
  張圖的內容,不是選單邏輯。
- **根因已大幅縮小(2026-08-14 補充)**：`export-ring-icons` 的抽取公式(`CellIndex`:index=
  2×directionState,enabled 時取 cell 0/2/4/6)跟 `drawNativeActionOverlay`(原生疊圖路徑,
  同樣用這個公式)是同一套已驗證邏輯，理論上沒有理由抽錯。原本以為原始 FDOTHER.DAT 不在專案
  樹裡無從查起，後來才發現使用者電腦上 `C:\...\GAME\FD2\FDOTHER.DAT` 確實存在，但拿去對
  `docs/data/fd2-reference-files.json` 的基準雜湊一比對，**檔案大小相同、MD5 不同**——這份
  FDOTHER.DAT 跟整個知識庫反組譯時用的基準版本不是同一份(同一批比對裡 FD2.EXE/FDTXT.DAT/
  FIGANI.DAT 也都不符，但 DATO/FDFIELD/FDICON/FDSHAP 等 9 個檔案完全相符)。這代表這次的
  cell0/cell2 duplicate、cell4/cell6 視覺語意對調，很可能只是**這個版本的 FDOTHER.DAT
  資源#2 排列跟基準版不同**，不是原版本身的怪異設計，也不是 `DecodeRawCellResource` 解碼
  邏輯的錯誤——但因為手上這份不是基準版，沒辦法拿它來對「基準版原版到底長怎樣」下定論。
- **修正**：在原因查清楚、圖示重新產生驗證過之前，`loadGame()` 不再載入這組已證實內容有問題
  的 `ring_*.png`，環選單固定退回文字後備(`labels[i]`，跟動作邏輯共用同一個索引，保證對得
  上，不會再顯示誤導圖示)。順便把文字後備的字級從 0.55 調到 0.85(原本太小，兩字糊成一團也
  是排查過程中發現的獨立可讀性問題，一併修掉)。
- **回歸驗證**：`go build`/`go vet`/`go test ./...` 全綠；`FD2_SHOT_RING` 截圖確認環選單四
  格現在清楚顯示「攻擊/法術/物品/待機」四個正確文字，位置與 doc13 [0x3C57] 記載的
  ↑攻擊/←法術/→物品/↓待機 一致。
- **已解決(2026-08-14 最終確認)**：用新基準版 FDOTHER.DAT 重新跑 `cmd/export-ring-icons`
  後，cell0/cell2 不再逐 byte相同(4 張圖 hash 全部不同)——證實先前的「duplicate」現象確實是
  非參考版本 FDOTHER.DAT 造成的，不是原版本身或解碼工具的問題。但重新核對後發現：resource
  內部的 4 個 cell 儲存順序，跟 `CellIndex` 公式假設的「與選單方向 0/1/2/3 同序」**不同**
  ——cell0=攻擊、cell2=待機、cell4=法術、cell6=物品，不是原本假設的
  攻擊/法術/物品/待機。這個順序由使用者對照真實遊玩記憶直接確認（非螢幕截圖自我驗證）。
  `cmd/export-ring-icons` 的 `names`/`indices` 已依此修正，`remake/cmd/fd2/main.go`
  新增實際載入 `assets/ui/ring_*.png` 到 `g.ringIcons[0..3]` 的程式碼(先前只有停用註解，
  從未真的載入過)。**排查過程中一度誤判**：直接肉眼讀小張 24×20 像素圖時，把左右格內容看反
  了，一度以為選單方向邏輯本身有問題；改用「四個純色色塊分別塞進 4 個格位」的方式重新截圖，
  才確認方向邏輯(`0x18d8c` 反組譯釘死，未受影響)完全正確，問題全部在 cell↔動作名稱這一層。
  最終用真實遊戲截圖(`FD2_SHOT_RING`，非靜態抽取)確認：上=攻擊(騎士劍)、左=法術(建築+法杖)、
  右=物品(錢袋)、下=待機(紅底騎士劍)，圖示已重新啟用，不再退回文字後備。
  `go build`/`go vet`/`go test ./...` 全綠。

- **待查旁證(2026-08-14,未證實)**：使用者提出一個推測——舊版/新版 FDOTHER.DAT 內容不同，
  會不會是早期多片版遊戲需要換片提示/邏輯，1998 重打包成單片版時被拿掉了？方向上合理(常見
  DOS 遊戲重出光碟版/單片版的做法)，但有一個具體線索跟這個理論對不太起來：**新舊版
  FDOTHER.DAT 檔案大小完全相同**(都是 3382481 bytes)，只有內容不同——如果是「拿掉換片提示」
  通常會讓檔案變小，而不是內容整個不同但大小分毫不差。比較像是內部資源被重新編碼/微調(跟
  ring icon 那個格位順序不同是同一類現象)，不是整段刪除。手上沒有真正的舊版 FDOTHER.DAT
  可以逐 byte diff，這個問題目前沒辦法真正驗證，僅記錄供未來若拿到舊版檔案時參考。

### 待驗證（下一步）

- [x] 攻擊執行（單位移到敵人相鄰格，真的觸發攻擊）：目標選取、命中/傷害演出、HP 條變化。
      2026-08-13 這次 session 花了很長時間嘗試,反覆遇到「環境已知問題」第 4/5 條
      （畫面卡幀、指令環方向鍵導航掉輸入），最後改由使用者手動接手鍵盤操作到一半，
      過程中意外抓到 Bug 3（見上）。**2026-08-15 真機驗證通過**：一開始以 ch01 原始
      JSON 座標（11,11）估算離最近敵人 12+ 格、MV=6、單回合打不到人，一度以為要嘛
      腳本化多回合走位、要嘛放棄——後來發現 `resetBattle` 實際部署位置是 `own_deploy`
      （約 x=7-11,y=20-23),重新量測後離最近敵人只有 4-6 格，單回合內可達。寫了新的
      `cmd/fd2/shot_autoplay.go`(`FD2_SHOT_AUTOPLAY=1`)：每幀自動幫玩家單位選人→
      算 `Reachable()` 挑離最近敵人最近的可達格→`confirm()`(移動用真正的
      pathing/walk 動畫)→到位後跟 `FD2_SHOT_ATKSEL` 同手法瞬間關指令環（略過純演出
      動畫,呼叫真正的 `confirm()`/`finishSelectedWait()`)→在射程內就真的攻擊、不在
      就待命→全員行動完呼叫真正的 `endTurn()`。過程中抓到一個真的 harness bug：
      `FD2_SHOT_DISMISS_DIALOG` 只在 `frame>=shotFrame-1` 這個一次性 setup gate
      觸發,跟截圖本身的 `frame>=shotFrame` 幾乎是同一幀,導致開場對話框幾乎吃掉整個
      frame budget——改成 autoplay hook 自己每幀主動清對話框，不依賴那個 gate。
      實跑 3 個真實回合,拿到完整、真實的傷害數字（索爾 11/19、亞雷斯 21/50/57、
      蓋亞 18/44）,期間穿插真正的敵方 AI 回合（`aiStep`/`AI決策` log 同時出現,
      confirms 這條路徑本身沒被 autoplay 繞過)，截圖確認 HUD 訊息
      「亞雷斯 攻擊 盜賊，造成 57 傷害」正確顯示。這是 E1 等級證據，doc58 這份文件
      2026-08-13 留下的最大缺口(攻擊命中/傷害流程從未真正跑過)至此完全補上。
      **2026-08-15 同日再補 E2：原版 DOSBox 互動實測攻擊，親眼確認擊殺畫面**。
      用真正的鍵盤操作（非截圖 harness）同時開 `org_game/炎龍騎士團/FLAME2/FD2.EXE`
      （DOSBox 0.74-3）跟重新編譯的原生 Windows `remake/fd2.exe`，從主選單 START 完整
      走一遍 ch01 開場劇情（比 remake 的 `FD2_CAMP_PREP_BATTLE` 捷徑長非常多，約 300+
      次 Enter 才到互動戰場）進到真正戰鬥。**指令環 UI 像素級比對確認吻合**：圖示設計
      （劍+頭盔=攻擊、法杖=法術、袋子=道具）、配色、四方位置跟 remake 完全一致。
      **摸清楚真正的攻擊按鍵序列**（過程中反覆卡在「選了『上』方向按 Enter，結果不是
      進入目標選擇,而是彈出裝備/法術清單畫面」——一開始誤以為指令環方向對應錯誤或指令環
      根本不是攻擊入口，後來才確認：這其實是正確行為,只是測試單位(索爾、悠妮)身邊都沒有
      敵人在攻擊範圍內，所以「攻擊」選項没有合法目標可選，遊戲改顯示單位資訊/法術列表
      作為 fallback，不是按鍵錯了）。正確完整流程（使用者親自指出後才校正)：
      1. 選角色（游標在自己格按 Enter）
      2. 把游標移到敵人**相鄰**的可達格（不是敵人本身那格）
      3. Enter 確認移動——真正的走位動畫播完後指令環自動開啟
      4. 方向鍵「上」選攻擊 → Enter → Enter（範圍內只有一個敵人時會自動鎖定,兩次
         Enter 分別對應「確認選攻擊」跟「確認對目標出手」)
      實測用亞雷斯（騎士）走到一隻盜賊旁邊，照上述流程操作後，**盜賊當場消失，原地變成
      灰色墓碑圖示**——這是原版遊戲真正的擊殺畫面，第一次親眼在原版裡看到攻擊執行的
      完整結果（不只是命中/傷害訊息，是連死亡演出都對上）。至此攻擊執行同時有 E1
      （remake 端自動化多回合戰鬥,真實傷害數字)跟 E2（原版互動實測,親眼確認同一套
      指令環→移動→攻擊→擊殺流程)雙重證據，是這次 ch01 驗證裡證據等級最完整的一項。
- [x] **2026-08-16 補測：索爾／亞雷斯攻擊距離差異分別實測，含負向案例**。上面 E1/E2
      的攻擊證據（索爾 11/19、亞雷斯 21/50/57，DOSBox 擊殺）用的都是 autoplay 的
      「盡量走到最近可達格」貪婪邏輯，實際發生時的確切距離沒有記錄，且亞雷斯真正
      跟索爾不同的地方——武器射程 `[1,2]`，可以不移動到相鄰格、隔一格攻擊——從未
      被證實真的執行過。新增 `FD2_SHOT_ATTACK_CONFIRM=<單位名>` +
      `FD2_SHOT_ATTACK_DIST=<n>` 鉤子（`cmd/fd2/main.go`），指定單位＋指定精確曼哈頓
      距離，找不到符合距離的可達格就誠實記錄失敗，不會靜默改用別的距離。四組結果
      （WSL2 headless，`FD2_CAMP_PREP_BATTLE=battle_ch01`）：
      ```
      索爾(AtkMin=1,AtkMax=1) dist=1: msg="索爾 攻擊 盜賊,造成 10 傷害" HP 28→18   ✅ 成功
      索爾(AtkMin=1,AtkMax=1) dist=2: msg=""                              HP 28→28   ❌ 正確地打不到
      亞雷斯(AtkMin=1,AtkMax=2) dist=1: msg="亞雷斯 攻擊 盜賊,造成 22 傷害" HP 28→6    ✅ 成功
      亞雷斯(AtkMin=1,AtkMax=2) dist=2: msg="亞雷斯 攻擊 盜賊,造成 21 傷害" HP 28→7    ✅ 成功(不移動到相鄰格!)
      ```
      索爾在距離2 `InAttackRange` 正確擋下（`msg` 空字串、HP 沒變，不是隨機沒打中，
      是根本沒有進入攻擊分支），證明 `[1,1]` 是真的被強制執行，不是巧合打中距離1。
      亞雷斯在距離2 **不移動到相鄰格就能攻擊**，這才是他跟索爾真正的行為差異，第一次
      被真機驗證證實。截圖 `docs/knowledge-base/evidence/attack_ch01_ares_dist2_20260816.png`
      清楚看到亞雷斯持長柄武器（斧槍/騎士槍，非索爾的短劍）隔空刺向盜賊，兩者之間有
      明顯間距，視覺上也對得上「距離2，非貼身」。此為 E1 等級證據，四個案例（含2個
      負向控制組）同一套邏輯測完，比先前泛用的 autoplay 證據更精確、更能排除巧合。
- [x] 法術子選單（開啟/選擇/施放）——**2026-08-16 更正：先前 2026-08-15 的「N/A」結論是誤判，
      這一格短暫重開為缺口，緊接著下一條 2026-08-16 補測項目已重新驗證通過並關閉，見下方**。
      原判斷依據是查 `assets/maps/map0/map0_units.json`（地圖/戰鬥範本檔，
      不是章節劇本的權威資料源）逐一核對，看到 ch01 全部單位 `mp: 0`、
      `initial_command_mask: [0,0,0,0]`，因而誤判「ch01 天生無施法者」。後來使用者要求核對
      索爾/亞雷斯攻擊距離是否不同、並指出「亞雷斯並不是使用短劍」，追查才發現一開始就用錯了
      資料源——真正載入 ch01 隊伍數值的權威檔案是 `remake/assets/scenarios/ch01.json`，其
      `party` 欄位經 `internal/battle/event.go`（`AtkMin`/`AtkMax`/`Spells`/
      `InitialCommandMask` struct 欄位定義行99-105、`SetInitialCommandMask` 呼叫行196-197、
      party member 建構行599/606、寫回 `Unit` 行651/655）跟 `model.go`（行69-70/180/
      880-881/964）實際解析進 runtime `Unit`，不是裝飾性欄位，跟 map0_units.json 的內容並不
      一致：
      - 悠妮（法師）`initial_command_mask:[1,0,0,0]`、`spells:[0,4,13]`——**ch01 確實有一名
        天生會施法的角色**，先前「N/A」結論錯誤。
      - 索爾攻擊距離 `atk_min/max:[1,1]`（武器 id=32 短劍，`item.json` `range:[1,1]`）；
        亞雷斯是 `[1,2]`（武器 id=**20**，不是索爾的短劍 32，`range:[1,2]`，符合
        `event.go` 程式碼註解「如亞雷斯騎士槍type3=2」）——兩人攻擊距離不同，先前也誤判
        成兩人裝備相同。
      **修正後結論**：法術子選單驗證重新視為未完成缺口，不是「不需要也不可能」。現有唯一的
      攻擊執行 E1 證據（`shot_autoplay.go` 跑的 3 回合）拿到的全是物理攻擊傷害數字（索爾
      11/19、亞雷斯 21/50/57、蓋亞 18/44），**從未出現悠妮的行動記錄**，`shot_autoplay.go`
      本身也只有「射程內攻擊/不在就待命」的物理邏輯、沒有施法分支——代表悠妮施法這條路徑
      至今從未被任何一次真機驗證真正跑過，是這次稽核後重新浮現的真缺口。
- [x] **2026-08-16 補上 E1：悠妮施法完整跑通，缺口正式關閉**。新增 `FD2_SHOT_SPELL_CONFIRM=1`
      鉤子（`cmd/fd2/main.go`）：找第一個有 `Spells` 的 Own 單位（悠妮）→ 用跟
      `shot_autoplay.go` 相同的 `Reachable()`+曼哈頓距離搜尋法，把她瞬移到「離某個敵人
      最近的可達格」（debug-only，`SetMapPlacement`，不跑真正走位動畫，因為這個鉤子只在
      單一幀觸發一次，不像 autoplay 是逐幀驅動）→ 開第一個法術（id=0,火炎術）→ 鎖定
      施法距離內最近的敵人 → 呼叫真正的 `g.confirm()`，走 `magic.go` 的 `CastArea()`
      本尊（不是合成捷徑）。

      這次驗證的執行環境本身也是這次稽核的副產品：Docker Desktop 在這台機器上持續當機
      （AF_UNIX socket 建立時就損毀，版本回退跟 Windows Defender 排除清單兩個理論都已
      實測推翻，根因仍不明，詳見記憶檔 `project_docker_desktop_af_unix_broken.md`），
      改用 **WSL2（Ubuntu 24.04，不透過 Docker Desktop、不透過任何容器引擎，直接原生跑
      `go build` + `xvfb-run`）** 完全繞開那個壞掉的子系統，跟 Docker 版驗證用的是同一支
      `cmd/fd2` 原始碼、同一個 headless 執行手法（`LIBGL_ALWAYS_SOFTWARE=1
      GALLIUM_DRIVER=llvmpipe` + `xvfb-run`），只是省了容器那一層。

      實測結果（`FD2_CAMP_PREP_BATTLE=battle_ch01 FD2_SHOT_SKIP_STORY=1
      FD2_SHOT_SPELL_CONFIRM=1`，真正掛載原版 `FDOTHER.DAT`/`FDTXT.DAT`/`DATO.DAT`）：
      ```
      FD2_SHOT_SPELL_CONFIRM: repositioned 悠妮 to (6,22) (nearest-enemy dist 3)
      FD2_SHOT_SPELL_CONFIRM result: caster=悠妮 spell=火炎術(id=0) target= msg="悠妮 施放
      火炎術:命中 1(造成 49)" mpBefore=16 mpAfter=33 targetHPBefore=28 targetHPAfter=0
      ```
      - 命中、造成 49 傷害（`assets/spells.json` id=0 底傷 dmg=50/hit=90，實際擲骰在合理
        範圍內），目標 HP 28→0，正確判定死亡。
      - **MP 不減反增**（16→33）乍看像 bug，追進 `magic.go` 確認是正確行為：
        `CastArea()` 162 行 `caster.MP -= sp.MP` 先扣 2 點法力，接著同一次呼叫因為擊殺
        目標會走 `GainExp`／`applyLevelUpGrowth`（`growth.go`）算經驗值——等一級新手
        單獨殺死一隻敵人的經驗值足以觸發升級，升級的 MP 成長量蓋過了那 2 點施法消耗，
        淨結果變成 MP 上升。這證明 `CastArea` 跟 `growth.go` 這兩個先前分別測試過的系統
        在真實施法路徑下確實有正確串接，不是巧合也不是 bug。
      - 截圖 `docs/knowledge-base/evidence/spell_cast_ch01_yuni_20260816.png`：全螢幕戰鬥
        演出畫面，悠妮（右，持法杖，血條/名牌正確顯示「悠妮」）對盜賊（左），畫面樣式與
        `FD2_SHOT_ATTACK`/E1 攻擊驗證截圖一致，證實法術命中會觸發跟物理攻擊同一套
        `newAtkAnim` 全螢幕演出（`magic.go` 第 5319-5327 行邏輯:`sp.Target==0 &&
        first.Amount>0` 時接演出）。

      **同日追加：比照索爾/亞雷斯的距離控制組手法，補上法術射程邊界＋負向案例**（使用者
      追問「法術呢？」才想到攻擊那組的嚴謹度應該同樣套用在施法上——先前只測了一次隨機
      距離的成功案例，沒有邊界值、沒有負向控制組，嚴格說服力不如攻擊那組）。把
      `FD2_SHOT_SPELL_CONFIRM` 擴充成跟 `FD2_SHOT_ATTACK_CONFIRM` 同一套 `consider()`
      距離搜尋邏輯，新增 `FD2_SHOT_SPELL_DIST=<n>` 指定精確施法中心距離。過程中抓到一個
      真的 harness bug：原本 `InCastRange` 檢查寫在 `SetMapPlacement` 瞬移**之前**，用的是
      悠妮移動前的舊座標算距離，導致連 `dist=3`（明顯在射程內）都被誤判成「超出射程」——
      修正順序（先瞬移、再檢查射程）後三組結果都正確：
      ```
      dist=3（射程內）: msg="悠妮 施放 火炎術:命中 1(造成 48)" mpBefore=16 mpAfter=36  ✅ 成功
      dist=5（剛好等於 sp.Dist=5,邊界值）: msg="...命中 1(造成 47)" mpBefore=16 mpAfter=35  ✅ 成功
      dist=6（超出 sp.Dist=5 一格,負向控制組）: "repositioned 悠妮 to (7,23), dist=6 to 盜賊
        exceeds spell dist=5 -- cast correctly unavailable"（未呼叫 g.confirm()，誠實記錄
        不合法而非強行測試）
      ```
      `dist=5` 這個邊界值成功、`dist=6` 正確失敗，證明 `InCastRange` 的 `dx+dy <= sp.Dist`
      判定（`magic.go` 第81行）在真實執行路徑上是含邊界值（`<=`）而非嚴格小於，跟原始碼
      邏輯完全對得上，不是巧合。至此法術驗證跟攻擊驗證用的是同一套嚴謹度（邊界值＋
      負向控制組），不再只有單一隨機成功案例。
      此為 E1 等級證據（真實編譯執行檔、真實 ch01.json/spells.json 資料、真正呼叫
      `g.confirm()`→`CastArea()`，非合成單元測試），尚未做 DOSBox 互動 pixel-diff（E2）。
- [x] 道具子選單（開啟/選擇/使用）——**2026-08-15 真機驗證通過**：用重建的
      `fd2-go-test-local` Docker image（`tools/docker/fd2-go-test.Dockerfile`）+
      Xvfb headless 執行，搭配真正掛載的原版 `FDOTHER.DAT`/`FDTXT.DAT`/`DATO.DAT`
      （`org_game/炎龍騎士團/FLAME2/`，之前漏掉沒掛進容器，導致 native 道具面板一直
      靜默失敗，`g.nativeItemEffectRows` 長度 0——這是這次真正抓到的根因，不是接線
      bug）。取道具 192（0xC0，type 5=HP 回復）當測項——**2026-08-16 更正測項描述**：
      原稱其為「ch01 寶箱真實掉落」，這個「寶箱」provenance 未經證實：`map0_units.json`
      的獨立 `chests` 欄位（slot 0）確實列著 `value:192`，但 ch01.json 的 5 個劇本
      event（opening/hano_hawat_join/enemy_reinforce/pirate_boss/coast_guard/
      hawat_berserk）沒有任何一個是開寶箱類型，代表這個寶箱在 ch01 是否真的會被觸發/
      能不能被拿到從未被驗證過。實際確認的是：道具 192 本身是索爾在 ch01.json 的**起始
      裝備**之一（`inventory:[0,132,192]`），這個 provenance 才有直接證據。測項本身
      （HP 回復數值/封頂/消耗）驗證結果不受影響，只是「寶箱掉落」這個修飾語應視為未證實，
      用 `FD2_SHOT_ITEM_FORCE=192 FD2_SHOT_ITEM_CONFIRM=1 FD2_SHOT_ITEM_DAMAGE=10`
      （新增的 `FD2_SHOT_ITEM_DAMAGE` 參數+延伸 `FD2_SHOT_ITEM_CONFIRM` 補呼叫
      `applyNativeTargetItem` 完成目標確認，見 `main.go` 對應註解）完整跑過
      「開面板→選道具→beginNativeTargetItem 選擇目標→confirm 套用」全流程：
      `HP 10→42`（封頂於 MaxHP 42，`10+40>42` 正確裁切）、道具正確從 `Inventory`
      移除（消耗成功）、截圖確認 HUD 訊息「物品 C0h：對目標完成效果」正確顯示，
      地圖/角色/血條算繪都正常。這是 E1 等級證據（真實編譯執行檔+真實資料+
      regression-trace，非合成單元測試），尚未做 DOSBox pixel-diff（E2）。
- [x] 回合結束→敵方 AI 回合→輪回玩家——**2026-08-15 隨攻擊執行驗證一併確認**：
      上面 `FD2_SHOT_AUTOPLAY` 那次真機執行完整跑了 3 輪「玩家全員行動完→
      `endTurn()`→敵方 `aiStep`/AI決策 log 出現、多個盜賊單位真的移動→輪回玩家
      控制、`g.st.Turn` 遞增」，不是單獨驗證,是同一份 log 的一部分。
- [x] **2026-08-16 補上：勝利結算→轉場，缺口關閉，並更正先前「轉場到 story_ch02」的錯誤假設**。
      2026-08-15 用 `FD2_SHOT_AUTOPLAY` 跑 10000/45000 幀想硬打完整章都沒打完（ch01 敵人
      分散 24×24 地圖各處約20隻,簡單「找最近敵人走過去」AI 算力划不來），當時判斷改補
      `result_test.go` 單元測試涵蓋判定邏輯本身，但轉場銜接（`checkResult()`→
      `g.camp.Advance()`→`g.enterNode()` 這條路徑）仍未實機驗證。這次不再嘗試硬打，改用
      新增的 `FD2_SHOT_FORCE_WIN=1` 鉤子（`cmd/fd2/main.go`）直接把 `g.st.Units` 裡的敵方
      單位 HP 全部歸零、清空 `g.st.PendingGroups`（見下方說明），再呼叫跟真正勝利後按
      Enter **完全相同**的程式碼路徑（`main.go` 第3964-3966行：`g.checkResult()`→
      `g.camp.Advance(g.result)`→`g.enterNode()`），只是省去真的把地圖上20隻敵人一隻隻
      打死的算力，驗證的是轉場銜接本身而非戰鬥數值（那部分交給上面的攻擊/法術測項）。

      **過程中抓到兩個真的東西**：
      1. 第一次只殺光 `g.st.Units` 裡已登場的8隻敵人，`g.result` 仍是空字串——追查後發現
         ch01 有兩波後續增援（`enemy_reinforce`/`pirate_boss`，turn4/5 才觸發）活在
         `g.st.Roster` 裡且 `PendingGroups` 標記為待命，`PendingCount()` 正確地把它們算進
         「還沒全滅」——這正是 `result_test.go`「pending 支援尚未清空時不該提前判win」那個
         分支要防的情境,不是 bug,是判定邏輯正確擋下了不完整的殺敵。清空
         `PendingGroups`（測試轉場銜接本身時的合理簡化,不是繞過判定）後才拿到 `g.result=
         "win"`。
      2. **走查過程犯了本文件開頭「環境已知問題」Bug 2 早就記載過的同一個錯誤，這裡誠實記錄**：
         第一次跑這個測項用了 `FD2_CAMPAIGN=1`，得到 `g.camp.Advance("win")` 回傳
         `"victory"`（不是 `"story_ch02"`），因而一度寫下「先前『轉場到 story_ch02』的說法是
         錯的」——但這個判斷本身才是錯的。本文件第10-15行**開頭就明講**：`FD2_CAMPAIGN=1` 是
         簡寫指向 `assets/scenarios/campaign.json`（`start: intro`，其 `title` 欄位自己就寫
         「第一章(campaign 節點圖)」，是只到 ch01 為止的精簡/開發用子集，`choice_town` 之後
         很快接一個 `type:"ending"` 節點結束），**不是**玩家真正會走的正式流程；正式流程是
         `play.sh` 用的 `FD2_CAMPAIGN=assets/scenarios/campaign_full.json`（299 節點，
         `start: story_ch00_handler`）——這正是「Bug 2」欄位記錄的同一個陷阱，這次又踩了一次。
         **用正式的 `campaign_full.json` 重測**，`battle_ch01.on_win` 確實是 `"story_ch02"`：
         ```
         FD2_SHOT_FORCE_WIN: killed=8 enemies, cleared 5 pending group(s), g.result="win",
           node before Enter="battle_ch01"
         FD2_SHOT_FORCE_WIN: Advance("win") -> next node="story_ch02",
           g.camp.Cur after enterNode()="story_ch02"
         ```
         所以**最初文件裡「轉場到 story_ch02」的說法從頭到尾就是對的**，不需要更正；需要更正
         的是這次繞了一圈才發現、且早該從文件開頭避免的「用錯 campaign 檔案」。`campaign.json`
         底下 `on_win="victory"` 那個結果本身也是真的（不是憑空捏造），只是屬於那個精簡 demo
         設定檔的行為，不是遊戲正式流程的行為——兩個都記錄下來，但正式流程的驗證結論以
         `campaign_full.json` 的結果為準。**後續 ch02 起的所有驗證都必須用
         `FD2_CAMPAIGN=assets/scenarios/campaign_full.json`**，因為 ch02 的節點（`town_ch02`/
         `shop_ch02_weapon`/`church_ch02`/`preparation_ch02`/`battle_ch02` 等）只存在於這個
         檔案，`campaign.json` 裡完全沒有。

      `g.result` 正確判定為 `"win"`、`g.camp.Advance("win")` 在正式流程下正確回傳
      `"story_ch02"`、`g.camp.Cur` 也確實更新，整條「判定勝利→查表→切換節點→materialize
      下一節點」的鏈路全部真實跑過一次，不是假設。此為 E1 等級證據（真實執行檔、真實
      campaign_full.json/ch01.json 資料、真正呼叫 `checkResult()`/`Advance()`/`enterNode()`
      本尊），尚未做
      DOSBox 互動 E2（畫面截圖這次因為 WSL2 `/tmp` 在兩次呼叫間被清空而沒能存下來，之後
      有需要再重截）。

### 已知環境限制（第一章驗證段落小結）

這次 session 在移動測試過程中反覆遇到背景程式搶焦點（見文件開頭「環境已知問題」），每次都要用
「換方向鍵測試游標還會不會動」來判斷是輸入問題還是遊戲邏輯問題，拖慢了驗證速度但沒有影響已確認
結果的可信度——每一項「已驗證」都是在確認輸入正常送達之後才記錄的。

---

## 第二章（2026-08-16 開始）

第二章是第一個有商店/教會/城鎮/整備節點的章節（`shop_ch02_weapon`/`shop_ch02_item` 等）。完整
劇本圖共 299 個節點：30 場戰鬥、69 商店、29 整備、23 城鎮、23 教會、60 過場、61 故事節點——規模
極大，逐章記錄會持續增補在本檔案下方，不重寫上面已確認章節。

**節點鏈路**（`campaign_full.json`，`battle_ch01.on_win="story_ch02"` 之後）：
`story_ch02`（過場,`ch00_post.json` binding）→`town_ch02`（type `town`,選項→`rumor_ch02`|
`shop_ch02_weapon`|`shop_ch02_item`|`preparation_ch02`|`church_ch02`,另有 secret gate
scan_code 84→`shop_ch02_secret`）→`preparation_ch02`（type `preparation`,`cancel:town_ch02`,
`next:story_ch02_pre`）→`story_ch02_pre`（過場,`ch01_pre.json` binding）→`battle_ch02`
（`map1`/`ch02.json`,`on_win:story_ch02_post`,`on_lose:retreat_ch02`）→`story_ch02_post`→
`town_ch03`。四個 shop/church 類節點都用 `next` 迴圈接回 `town_ch02`。

**既有涵蓋**（Explore agent 2026-08-16 偵查回報，來自更早的自動化/截圖模式工作，不是這份
逐章即時操作驗證日誌的一部分，但可以拿來當基礎）：
- `docs/knowledge-base/57-ui-evidence-matrix.md:20-23`：town ch02 variant0 sel0-5、
  shop ch02 variant1/3/5（武器購買清單/Yes-No/金額不足/裝備接收者）已有 DOSBox raw-RGB
  逐幀比對 E2，但是透過「截圖模式 LOADCH 假造隊伍」bootstrap 出來的,不是走真正的
  campaign 流程；church 60-70%、preparation 35-45% 都只有 E1,沒有 DOSBox 逐幀比對。
- `docs/knowledge-base/91-worklist.md:21`：`CAMPAIGN-JOIN-LOADCH-PERSISTENT-PARTY-
  BOOTSTRAP` 這個修復已經驗證過 ch00→ch02 JOIN roster 候選 `[0,9,4]` 能正確落地——是
  runtime bridge 的迴歸測試，不是完整 E2/真存檔連續遊玩。

**既有 FD2_SHOT_* 鉤子只能擺狀態，不會真的執行交易**：`FD2_SHOT_TOWN_STATE`（游標/動畫狀態）、
`FD2_SHOT_SHOP_STATE`/`FD2_SHOT_SHOP_PURCHASE_STATE`/`FD2_SHOT_SHOP_CONFIRM_STATE`/
`FD2_SHOT_SHOP_INSUFFICIENT_STATE`/`FD2_SHOT_SHOP_EQUIPMENT_RECIPIENT_STATE` 都只是把畫面
擺到某個截圖用的狀態,沒有一個會真的扣金幣/寫入 inventory；church/preparation/hotel 完全沒有
對應鉤子,只能靠真實輸入互動。**下一步**：比照 ch01 攻擊/法術/勝利驗證的做法,寫真正執行交易
的 debug 鉤子（例如 `FD2_SHOT_SHOP_BUY_CONFIRM` 之類,直接呼叫商店購買的真實函式,確認金幣
真的被扣、inventory 真的被寫入),而不是只停在「畫面擺對了」。

**重要前提（本文件開頭 Bug 2 已經記過一次的陷阱，這次又踩了一次，見上方勝利轉場那條的更正）**：
所有 ch02 起的驗證都必須用 `FD2_CAMPAIGN=assets/scenarios/campaign_full.json`（**不是**
`FD2_CAMPAIGN=1`），因為 ch02 節點只存在於 `campaign_full.json`。另外 shop/church/town/prep
會讀 `g.partyRoster`，headless 起手不能只靠 `FD2_CAMP_NODE` 跳節點，還需要
`FD2_SHOT_PARTY_BINDING=<binding路徑>`（`native_shop_shot_party.go`，指向像
`assets/cutscenes/bindings/ch00_pre.json` 這樣的編譯過 handler binding）先把隊伍灌進去，
既有 ch02 shop E2 證據用的就是這個機制。

### 節點可達性/基本畫面（2026-08-16，WSL2 headless，`FD2_CAMP_NODE`+`FD2_SHOT_PARTY_BINDING=
ch01_post.json` 真實走 campaign_full.json 節點圖，不是合成截圖）

- [x] `town_ch02`：正確渲染,角色站在城鎮營地場景,選單游標停在「酒店」選項。截圖
      `docs/knowledge-base/evidence/town_ch02_20260816.png`。
- [x] `shop_ch02_weapon`：正確渲染,藍色巨魔店主 NPC、金幣顯示 `$00001000`、對話「呃，買東西
      嗎？」、下方4個服務圖示（購買/賣出/裝備/其他）清晰無誤。截圖
      `docs/knowledge-base/evidence/shop_ch02_weapon_20260816.png`。
- [x] `preparation_ch02`：正確渲染,「出戰整備」標題、「要進入戰場嗎？」是/否選項、「F5 保存
      戰況」提示,畫面乾淨無異常。
- [x] `battle_ch02`：正確渲染,HD 貼圖城鎮/教堂地圖、敵方單位散布、亞雷斯等我方單位在右側
      正確顯示名牌，HUD 面板顯示選中單位的 `A+05 D+00`。用的是跟 ch01 相同的整圖合成+HD
      upscale 管線,確認對 ch02 的地圖資產（`map1`）一樣有效。
- [x] **2026-08-16 真實 bug，root cause 找到並修好**：`church_ch02` 畫面雖然正常渲染（白髮
      祭司立繪、對話「有什麼事嗎？」、金幣顯示都正確），但**選單下方4個服務圖示是亂碼**——
      同樣位置/同樣機制在 shop 畫面完全正常，church 卻是一片橘藍交雜的雜訊色塊。修復前截圖
      `docs/knowledge-base/evidence/church_ch02_icon_corruption_20260816.png`（含放大裁切
      對比）。

      **排查過程**：圖示來源是 `g.nativeClassUI.entries`（`native_class_ui.go`
      `loadNativeClassUIAssets()`，讀 `FDOTHER.DAT` resource **#14**，`fdother.ParseLMI1`
      解出），church 選單用 `entries[3..10]`（4個服務格×正常/pulse各一）。
      1. 排除資源搞混：church 跟 shop/preparation/town 共用同一個 `g.nativeClassUI`，都是讀
         resource #14，跟既有測試 `TestNativeChurchMenuOriginalResourceCells` 一致。
      2. 寫一次性 debug 測試把 `entries[3..10]` 的 `Pixels` 直接存成 PNG，**完全繞過**
         compositing 層——確認 8 個 cell 的原始像素資料本身就已經是雜訊，證明 bug 在
         `fdother.ParseLMI1`/`decodeLMI1Pixels` 這個 RLE 解碼器,不在合成層。
      3. **第一次用真實色盤（resource #0 的 VGA palette）重新渲染這批「雜訊」像素，結果依然
         是雜訊**——排除「只是灰階視覺化誤導,實際套色後其實是對的」這個可能性,確認是真的
         解碼錯誤,不是視覺化 debug 工具本身的假警報。
      4. **關鍵發現：hex dump 這 8 個 entry 在 directory table 裡的 offset,發現前後 entry
         間距剛好都是 `4+24*20=484` bytes,完全沒有壓縮空間**——這種「entry 佔用空間精確
         等於 raw pixel 大小」的簽章,是「這個 entry 其實是未壓縮原始位元組,不是 RLE」的
         強烈訊號。直接把這 8 個 entry 當**原始未壓縮位元組**讀出、套色盤重繪，得到清晰
         可辨識的圖示（狀態/道具轉移/復活/轉職四種服務,含骷髏頭、舉手角色等清楚圖案）：
         `docs/knowledge-base/evidence/church_icons_raw_decode_rootcause_20260816.png`。
      5. **修復**（`internal/fdother/lmi1.go` `ParseLMI1`）：新增判斷式——當 entry 在
         directory 裡分配到的空間精確等於 `w*h`（沒有壓縮空間）**且** `w*h` 夠大（設
         `lmi1RawDetectionMinPixels=32` 門檻）時，直接讀原始位元組而非跑 RLE。這個判斷式
         不是只為 church 硬湊的特例——同一份 hex dump 順便也抓到 resource#14 entry 2
         （6×99）有一樣的簽章，是格式本身真的存在「部分 entry 存原始位元組」這個編碼變體，
         不是巧合。
      6. **第一次跑 `go test ./...` 抓到自己引入的誤判**：既有測試
         `TestParseLMI1NativeCodec` 有一個 2 像素的合成 RLE entry `[0xc2,7]`（單一 repeat
         指令,run=2,剛好也是「佔用空間精確等於 w*h」——RLE repeat 指令固定成本2 bytes,
         當 run 長度剛好等於 2 時零壓縮收益,純屬巧合）,被新判斷式誤判成 raw。這證明
         「佔用空間等於 w*h」本身不是無歧義訊號,只在 pixel 數夠多時才可信（真實圖示美術
         若真的是 RLE 編碼,大面積色塊幾乎不可能零壓縮收益；但小到 2 像素的極端情況,零
         收益完全合理）——這正是加 `lmi1RawDetectionMinPixels` 門檻的理由，而不是事後
         拍腦袋的數字。新增 `TestParseLMI1DetectsRawStorageAboveSizeFloor`（8×4=32像素,
         剛好卡在門檻,內容全部填 `0xc7`,驗證會被正確判定為 raw 而非誤判成 RLE 控制位元組）
         防止未來回歸。
      7. **修復後重截 `church_ch02`，圖示清晰正常**，跟修復前 root-cause 分析預覽的圖案
         一致：`docs/knowledge-base/evidence/church_ch02_icons_fixed_20260816.png`。

      `go test ./...`（含 `cmd/fd2`/`internal/battle`/`internal/campaign`/`internal/fdother`
      等全部套件）確認乾淨,Windows/WSL 兩邊 build 都通過。doc57 的 church 60-70% 完成度
      評估完全沒提到這個視覺問題,是這次才第一次抓到並修好。
- [x] `shop_ch02_item`：正確渲染,藍髮精靈店主 NPC、對話「歡迎光臨，需要什麼嗎？」、4個服務
      圖示清晰無誤（**再次確認 icon 系統本身沒問題,church 那個是 church 專屬 bug,不是
      shop/church 共用元件的通病**）。截圖 `docs/knowledge-base/evidence/
      shop_ch02_item_20260816.png`。
- [x] `shop_ch02_secret`：`FD2_CAMP_SECRET=1` 正確觸發 secret gate,渲染同一個巨魔店主但
      灰階配色+錨形刺青（跟一般武器店的藍色版區分開），對話與圖示都正常。截圖
      `docs/knowledge-base/evidence/shop_ch02_secret_20260816.png`。
- [x] `rumor_ch02`：正確渲染,對話正確顯示「聽說這裡有不擺在檯面上的好東西…（酒店前按
      Shift+F1鍵）」——**發現並當場修好一個文字換行 bug**：`Shift+F1鍵` 原本被硬生生從中間
      斷成 `Shi` / `ft+F1鍵` 兩行。截圖（修復前）`docs/knowledge-base/evidence/
      rumor_ch02_textwrap_20260816.png`。

      **根因**：`main.go` 的 `dlgWrap()`（對白框逐字換行,非 `font.go` 的 `Wrap()` — 那個是
      ending/說明頁專用,不相關）純粹按 rune 數 `perLine` 切字串（`txt[:nn]`），完全沒有
      考慮連續英數字元不該被從中間切開；`toFullWidth()` 只轉標點（，！：；。（）），不轉字母
      數字，所以 `Shift+F1` 進到換行邏輯時仍是普通半形 ASCII，純 rune 計數切割正好落在單字
      中間。這條對白是 remake 團隊自己寫的除錯提示字串（原版 1990s DOS 遊戲不會有
      「Shift+F1」這種按鍵提示），不是原始劇本文字，所以這是貨真價實的 remake bug，不是
      忠實重現原版行為的問題。
      **修復**：新增 `isASCIIWordRune()` 輔助函式，`dlgWrap()` 的切割點如果會落在一段連續
      ASCII 英數字中間，往回退到該段開頭（除非整段本身就比 `perLine` 長，那種退化情況保留
      硬切,避免死迴圈）。新增迴歸測試 `TestDlgWrapDoesNotSplitASCIIWord`
      （`dlg_test.go`），並用一個獨立的除錯測試印出實際切行結果，確認切點原本真的落在
      "Shift" 中間（`好東西…（酒店前按` / `Shift+F1鍵）』` 修復後正確地整段落在同一行）。
      `go build`/既有 `TestDlg*` 全部測試（含長句分頁/雙寬度一致性等）跑過都沒有回歸。
      修復後截圖（同一個 `rumor_ch02` 節點重跑）：`docs/knowledge-base/evidence/
      rumor_ch02_textwrap_fixed_20260816.png`，`Shift+F1鍵` 完整顯示在同一行,不再被截斷。

**小結**：ch02 全部7個非戰鬥節點（town/shop×3/preparation/rumor）+ `battle_ch02` 都已確認
可達且畫面正確渲染,途中抓到2個先前未記錄的真實 bug——文字換行（`Shift+F1` 斷詞）已修好並
補上迴歸測試；church 圖示亂碼還沒修，留待下一輪。

### 真實交易執行（2026-08-16 補上，缺口關閉）

上面「既有 FD2_SHOT_* 鉤子只能擺狀態」那段列出的缺口——追查發現商店的真實購買邏輯有兩條路：
- **legacy（非 native）路徑**：`main.go` 第3890-3934行，一般 `Update()` 按鍵處理直接呼叫
  `campaign.ReserveGood`/`campaign.FinalizeGood`，邏輯簡單。
- **native 路徑**：`native_shop_transaction_ui.go` 的 `stageNativeShopPurchase()`→
  `beginNativeShopPurchaseSuccess()`，會建立一個多幀動畫 job（金幣滾動動畫等），比 ch01 的
  攻擊/施法單幀執行複雜很多，真正掛載原版 DAT 素材時走的是這條（legacy 只在素材不全時
  fallback，`main.go:3807` 的 `g.handleNativeShopInput(enter)` 會先攔截）——代表要驗證
  「真實玩家會走的購買體驗」必須測 native 路徑,不能抄捷徑測 legacy。

**新增 `FD2_SHOT_SHOP_BUY_CONFIRM=1`**（獨立檔案 `cmd/fd2/shot_shop_buy_confirm.go`）：呼叫
跟玩家按 Enter 完全相同的真實函式——`setupNativeShopRecipients()`（從 `g.partyJoinOrder` 建
收件者清單）→`stageNativeShopPurchase()`（進入 native 購買成功動畫 job）。

**第一次嘗試就踩到兩個真的坑，都修好了才拿到乾淨結果**：

1. **`FD2_SHOT_PARTY_BINDING` 用錯 binding 檔**：一開始沿用 ch01 那組驗證用過的
   `ch01_post.json`，結果 `materializeShotPartyFromBinding` 直接報錯「shot party binding
   has no complete party LOADCH state」——`_post` 系列 binding 沒有 LOADCH 隊伍資料，
   `_pre` 系列才有（`ch01_pre.json` 的 `party_scenario` 指到 `ch02.json`、
   `party_order:[0,9,4,30,1]`，正是「即將進 ch02 戰鬥前」的隊伍狀態，拿來代表「人在 ch02
   城鎮」是合理的）。換成 `ch01_pre.json` 後 `partyJoinOrder`/`partyRoster` 才真正填好。

2. **鉤子擺錯位置,踩到跟 2026-08-15 `FD2_SHOT_DISMISS_DIALOG` 一模一樣的 timing bug**：
   一開始把鉤子塞進既有的 `shotSetup` 區塊（`g.frame >= g.shotFrame-1` 才觸發，跟截圖本身
   幾乎同一幀），結果不管把 `FD2_SHOT_FRAME` 調多高（試過300、3000幀）,`inventory` 立刻正確
   寫入（`ReserveGood` 是同步呼叫，一次到位），但**金幣動畫（`nativeShopUIJobStillPending`）
   永遠卡在 `true`，金幣完全沒扣**——追查 `stepNativeShopUILifecycle`/`drawNativeShopUIJob`
   發現金幣滾動動畫是用**真實 wall-clock 時間**（`job.elapsed = now.Sub(job.started)`，
   `NativeGoldRollDelayMilliseconds=10`/step）驅動，不是用幀數驅動——調高 `FD2_SHOT_FRAME`
   只會延後鉤子「幾時開始」，不會讓動畫「有更多時間跑完」，因為鉤子本身跟截圖幾乎同一幀觸發,
   動畫從頭到尾只有不到1幀的真實時間可用。**修法**：把鉤子搬出 `shotSetup`,獨立成
   `stepShotShopBuyConfirm()`，改成每幀檢查、一偵測到 `g.nativeShopMode=="menu"` 就立刻在
   **極早**的幀觸發（不綁 `shotFrame`），讓 `FD2_SHOT_FRAME` 之間的真實幀數/真實時間都留給
   動畫播放。

**修好後的乾淨結果**（`FD2_CAMP_NODE=shop_ch02_item FD2_SHOT_PARTY_BINDING=ch01_pre.json
FD2_SHOT_SHOP_BUY_CONFIRM=1 FD2_SHOT_FRAME=300`，買藥草192,price=1）：
```
FD2_SHOT_SHOP_BUY_CONFIRM: frame=1 good={ID:192 Name:藥草 Price:1} recipient=索爾(id=0)
  goldBefore=1000 invBefore=[0 132 192 255 255 255 255 255] staged=true mode="success"
FD2_SHOT_SHOP_BUY_CONFIRM after-state: goldBefore=1000 goldAfter=999
  invBefore=[0 132 192 255 255 255 255 255] invAfter=[0 132 192 192 255 255 255 255]
  nativeShopUIJobStillPending=false
```
金幣正確扣款（1000→999，等於 price）、道具正確寫入 inventory slot 3（值192）、動畫 job
正確跑完（`nativeShopUIJobStillPending=false`，不是卡住），畫面截圖也視覺確認金幣顯示
「$00000999」跟商店清單正確：`docs/knowledge-base/evidence/
shop_ch02_real_purchase_gold999_20260816.png`。

native 路徑的底層數學（`ReserveGood`/`FinalizeGood`）跟畫面呈現（native menu frame 組成）
先前已有扎實的 Go 單元測試覆蓋（`shop_trace_test.go`/`native_shop_ui_test.go`），這次補的是
**多幀動畫 job 從頭到尾在真實編譯執行檔上跑一次**的 E1 證據，兩者互補，不重複。`go
vet`/`internal/battle`/`cmd/fd2` 全測試/Windows/WSL build 均確認乾淨。

---

## 第三章（2026-08-16 抽樣起步）

ch02 逐節點類型窮舉（town/shop×3/church/preparation/battle 全測）已經證明 shop/church/town/
preparation 這幾個節點類型是**跨章節共用的同一套程式碼**（`native_shop_ui.go`/
`native_church_ui.go`/`native_town_ui.go`/`native_preparation_ui.go` 等完全不含章節判斷分支，
差異只在資料——地圖、商品清單、對白），不是每章各自重新實作。因此 ch03 起改用**抽樣式**驗證：
確認節點鏈路可達＋畫面正確渲染即可,不需要再逐節點類型窮舉（那是在重測同一份程式碼,邊際價值
低),真正需要逐章別重新驗證的是**章節專屬資料**本身有沒有錯（地圖資產、商品/價格表、對白）。

- [x] `town_ch03`：`FD2_CAMP_NODE=town_ch03 FD2_SHOT_PARTY_BINDING=ch02_pre.json`（ch02
      即將進 ch03 戰鬥前的隊伍狀態,同 ch02 沿用 ch01_pre.json 的邏輯）正確渲染,角色站在
      新的城鎮場景（跟 ch02 的帳篷營地美術不同,確認地圖資產有隨章節切換,不是重複用同一張
      背景),選單同樣停在「酒店」。截圖 `docs/knowledge-base/evidence/town_ch03_20260816.png`。
- [x] `battle_ch03`：`FD2_CAMP_PREP_BATTLE=battle_ch03 FD2_CAMP_NODE=battle_ch03` 正確渲染,
      全新的木柵城塞地圖（跟 ch01/ch02 的地圖完全不同),我方單位正確部署在下方、游標選中框
      跟 HUD 面板（不同角色頭像）都正常顯示。截圖 `docs/knowledge-base/evidence/
      battle_ch03_20260816.png`。
- [x] `shop_ch03_weapon`/`shop_ch03_item`/`shop_ch03_secret`/`church_ch03`/`preparation_ch03`
      （2026-08-16 補測,`FD2_SHOT_PARTY_BINDING=ch02_pre.json`）：全部正確渲染,NPC 立繪/
      對白/圖示皆為 ch03 專屬內容（武器店藍巨魔、道具店精靈、密店灰巨魔+錨形刺青、教會
      白髮祭司,均與 ch02 對應節點的立繪不同,證明資產有隨章節切換,不是誤用 ch02 快取）。
      **`church_ch03` 的4個服務圖示清晰無亂碼**——直接證實上方 `lmi1.go` raw-storage
      判斷式修復不是 ch02 專屬的特例修補,同一份程式碼路徑在 ch03 的資料上一樣正確。
      截圖：`docs/knowledge-base/evidence/{shop_ch03_weapon,shop_ch03_item,
      shop_ch03_secret,church_ch03,preparation_ch03}_20260816.png`。至此 ch03 全部
      非戰鬥節點+battle_ch03 均已確認,第三章收尾。

## 第四章（2026-08-16 抽樣）

`FD2_SHOT_PARTY_BINDING=ch03_pre.json`,同一套抽樣方法測 `town_ch04`/`battle_ch04`+5個
非戰鬥節點：

- [x] `town_ch04`：正確渲染,帳篷營地場景與 ch03 視覺相似但**逐 byte 比對確認實際不同**
      （`cmp` 證實不是同一張快取圖）。
- [x] `battle_ch04`：全新森林地圖（跟 ch01/ch02/ch03 都不同）,散布多個寶箱圖示、敵方
      單位部署在上半部、我方部署在下半柵欄後,HUD 面板正常。
- [x] `shop_ch04_weapon`/`shop_ch04_item`/`shop_ch04_secret`/`church_ch04`：畫面正確渲染,
      但**逐 byte 比對發現這4張跟 ch03 對應節點完全相同（`cmp` 逐 byte 相符）**——追查
      `campaign_full.json` 節點定義後確認**這不是 bug**：`shop_ch04_weapon` 的 `goods`
      陣列跟 `shop_ch03_weapon` 內容確實不同（ch04 是8件商品/不同 id,ch03 是5件),只是
      這個初次進入的 NPC 對話畫面（立繪+問候語+服務圖示)本身就是**共用不看章節資料**的
      靜態畫面,商品清單差異要打開購買選單才會顯示,這次抽樣截圖沒有做到那一步。
      `church_ch04` 的 JSON 節點定義本身只有固定 `"text":"教會"`,沒有章節專屬對白欄位,
      跟 ch03 完全相同純屬資料本身如此,不是程式碼忘記換圖。
- [x] `preparation_ch04`：正確渲染,**逐 byte 比對確認跟 ch03 不同**（背後戰場縮圖跟隨
      章節換了)。

**方法論小結（重要,影響後續章節怎麼測）**：這次抽樣式截圖驗證的範圍是「節點可達＋NPC
對話畫面渲染正確」，**不觸及**每章實際的商品/價格資料是否正確——那需要真的開商店購買
選單（既有 `FD2_SHOT_SHOP_STATE`/或這次 ch02 才新增的 `FD2_SHOT_SHOP_BUY_CONFIRM` 真交易
鉤子）才能看到。目前只有 ch02 的 `shop_ch02_item`（藥草 id=192,price=1)做過真交易驗證,
ch03/ch04 起的商品清單資料本身（`goods` 陣列的 id/price 是否跟原版一致)**尚未逐章驗證**,
如果之後要對商品資料本身的正確性負責,需要額外一輪針對 `goods`/`items.json` 的資料比對,
不是靠這輪的畫面截圖能覆蓋。截圖：`docs/knowledge-base/evidence/{town_ch04,battle_ch04,
shop_ch04_weapon,shop_ch04_item,shop_ch04_secret,church_ch04,preparation_ch04}_
20260816.png`。

## 第五章至第十章（2026-08-16 抽樣，town+battle）

考量 shop/church/preparation 已在 ch02-04 三章連續確認是共用同一套程式碼、章節差異只在
資料（見上方 ch04 小結),這輪只抽測 `town_chNN`/`battle_chNN`（兩個真正逐章換資產的節點
類型),`FD2_SHOT_PARTY_BINDING=ch(NN-1)_pre.json`：

- [x] `town_ch05`~`town_ch10` 全部正確渲染,可互動觸發。**意外發現並排除一個誤判**：
      `town_ch06`/`ch07`/`ch10` 三張截圖逐 byte 完全相同,`town_ch05`/`ch08`/`ch09`
      另外三張也逐 byte 完全相同,一度懷疑是「換章節沒換到背景」的 bug。查
      `campaign_full.json` 每個 `town_chNN` 節點的 `native_town_variant` 欄位後確認
      **不是 bug**：這個欄位本身的值就是 `{ch02:0, ch03:2, ch04:0, ch05:0, ch06:2, ch07:2,
      ch08:0, ch09:0, ch10:2}`——原版資料本身只用少數幾種營地美術變體循環分配給不同章節,
      不是每章都有獨立背景,`native_town_ui.go` 正確地依 `NativeTownVariant` 這個資料欄位
      挑圖,不是依章節號——同一個 variant 值渲染出逐 byte 相同的畫面正是**正確行為的證據**
      （挑圖邏輯認資料不認章節號),不是快取沒更新或忘記換圖。
- [x] `battle_ch05`~`battle_ch10` 全部正確渲染,**六張地圖彼此完全不同**（檔案大小
      476KB~677KB 各不相同,肉眼比對地形/敵我配置/寶箱位置全部不同),其中 `battle_ch10`
      是**第一次確認室內地城/洞穴類型地圖**（火把、灰岩地形、機械人單位、黑色遮罩正確蓋住
      地圖外框,不是方形裁切),證明「整圖合成+HD upscale」管線（task#63-66)對戶外草原/
      森林以外的室內洞穴地形一樣正確,不是只測過戶外地圖。`battle_ch07` 截圖同時可見隊伍
      已成長到8名成員,部署位置正確散開不重疊。截圖：`docs/knowledge-base/evidence/
      {town,battle}_ch{05..10}_20260816.png`。

**小結**：第五~十章的節點可達性+畫面渲染正確性已確認,跟 ch03/ch04 一樣**尚未**驗證
shop/church 的商品清單/價格資料本身是否跟原版一致（見上方 ch04 小結的方法論限制)。

## 第十一章至第十五章（2026-08-16 抽樣，town+battle）

同上一節方法。`native_town_variant` 這次出現**第三個新數值**：`town_ch11=2`（跟 ch03/06/07/10
同一組),`town_ch12~15=1`（首次出現的新變體,`ch12`/`ch13` 逐 byte 比對確認彼此相同、且跟
之前的變體 0/2 都不同)——持續證實「variant 值決定畫面,不是章節號決定」這個結論站得住腳,
不是巧合。`battle_ch11`~`battle_ch15` 五張地圖彼此完全不同（檔案大小 545KB~616KB 各不相同),
`battle_ch13` 截圖確認隊伍已成長到約12名成員,新的秋色/沙漠色調地圖+敵營帳篷,單位密集但
render 無重疊/無圖層錯位。截圖：`docs/knowledge-base/evidence/{town,battle}_ch{11..15}_
20260816.png`。

## 第十六章至第二十一章（2026-08-16 抽樣，town+battle）

同上方法。`native_town_variant` 全數符合檔案大小分群（`ch16/17/18/20/21=1`,`ch19=2`,
兩兩對照均正確),不再贅述。`battle_ch16`~`battle_ch21` 六張地圖彼此完全不同,兩張特別
記錄：
- `battle_ch18`：**窄橋關卡地圖**——左側森林部署區(隊伍已達14人)透過一條很長的木橋
  通往右側孤立的小塊敵方陣地,橋兩側是大片純黑（螢幕外/地圖邊界外的正確遮罩,不是
  渲染錯誤),是這輪抽樣目前看到視覺上最特殊的地圖設計,整圖合成管線正確處理了這種
  「大範圍空白+窄通道」的極端長寬比。
- `battle_ch20`：**深水/沼澤地形地圖**（左上大片深色區域),對照本文件第一章段落記錄的
  「`map19`（第20章)是全部33張地圖裡唯一有非1/99地形成本值的地圖」這條舊發現——這是
  第一次真的看到這張地圖長什麼樣子,深色區域的視覺呈現跟「沼澤/深水地形」的預期一致
  （雖然目前 `MoveCostFor` 差異化成本只有管線接好、尚未真的替任何職業標記騎兵/飛行,
  見上方第一章段落,這裡純粹是畫面渲染確認,不是移動成本行為驗證)。隊伍此時已成長到
  接近20人,散開部署無重疊。

截圖：`docs/knowledge-base/evidence/{town,battle}_ch{16..21}_20260816.png`。

## 第二十二章至第二十五章（2026-08-16 抽樣）

`town_ch22`（`native_town_variant=1`,跟大多數中後期章節同一組)+`battle_ch22`~`battle_ch25`
四張地圖全部正確渲染、彼此不同。`ch23`/`ch24`/`ch25` 這三章**依 `campaign_full.json`
節點列表確認完全沒有 `town`/`shop`/`church` 節點**（只有 `story→battle→preparation→
retreat`),這不是這次抽樣漏測,是原始劇本資料本身的設計（連續幾章的「趕路/追擊」劇情,
不回城鎮),跟本文件開頭 task#52「調查 ch02-25/28-30 為何沒有 town」那條舊調查的結論一致
（該任務先前已標記完成)。`battle_ch24` 是一張**小型圓形孤島關卡**（懸崖邊緣+發光光柱+
石柱裝飾,視覺上像 boss 戰場),隊伍已成長到 25+ 人全部正確散開部署在有限空間內無重疊,
HUD 正確顯示選中單位「米亞斯多德」。至此確認整圖合成管線對「大範圍黑遮罩+極小可站立
區域」這種極端地圖也正確處理（跟 ch18 的窄橋案例是同一類驗證,分別驗證了「窄長型」跟
「小圓型」兩種極端)。截圖：`docs/knowledge-base/evidence/{town_ch22,battle_ch22,
battle_ch23,battle_ch24,battle_ch25}_20260816.png`。

## 第二十六章至第三十章（2026-08-16 抽樣，全劇本收尾）

`town_ch26`/`town_ch27`（`native_town_variant=0`,截圖與早期章節同組)+`battle_ch26`~
`battle_ch30` 全部正確渲染,兩張反應爐/高塔類科技風走廊地圖（`ch26`/`ch27`)畫面乾淨,
隊伍已成長到近30人,密集部署無重疊/無圖層錯位。`ch27` 的 `inventory_gate_ch27_sky_key`
分支節點（依 `item_id=100`「天空之鑰」有無決定走向 `story_ch27_post_sky_key_success`
還是壞結局 `ending_ch27_no_sky_key`)**已有 Go 單元測試覆蓋**（`cmd/fd2/
inventory_gate_test.go` 的 `TestInventoryGateSkyKeyRoutesThroughSyncThenPreparation`／
`TestInventoryGateMissingSkyKeyReachesBadEndingWithoutSync`),這次未重複驗證,僅確認
測試存在且涵蓋兩個分支。`ch23`/`ch24`/`ch25`/`ch28`/`ch29`/`ch30` 六章維持無 town 節點
（見上方 ch22-25 小結,已確認是原始資料設計而非漏測)。

### 發現：真正的破關結局尚未接上，玩家目前只會看到生成器佔位文字（重要,非小問題）

打完 `battle_ch30`（`on_win: "ending"`)後，`campaign_full.json` 的終點節點 `ending`
目前是：
```json
{"type": "ending", "text": "傳說的終章——空魔神殞落,炎龍騎士團的旅程至此告一段落。
(campaign_full.json 自動生成 v1:節點骨架完整,逐章劇情全文/回合事件/主角隊招募
待下一輪補完)"}
```
截圖 `docs/knowledge-base/evidence/ending_stub_20260816.png` 證實**這段括號裡的生成器
備註文字會直接顯示給玩家看**（`main.go:8002` 的 `case n.Type == "ending"` 就是單純把
`n.Text` 印在黑底面板上,沒有特殊處理),不是我截圖時不小心截到內部文件。

**但關鍵是：這不是「內容還沒做」，而是「內容做好了但沒接上」**——查證發現兩份獨立、
扎實的既有工作完全沒被用到：
1. `assets/story/ch30.json` 裡有完整的第三十章劇情大綱（標題「決戰 ASR-06,悠妮身世
   全公開」、完整場景說明,來源 `FDTXT_030`),不是空的。
2. `assets/endings/native_{2bce5,2c405,2c548}.json` 三份反組譯自原版真結局演出的
   native handler 資料（`0x2bce5` 分段動畫/`0x2c405` finale/`0x2c548` montage),外加
   `internal/ending` 整個套件（`compositor.go`/`timeline.go`/`finale.go`/`montage.go`)
   跟至少4個測試檔（`compositor_test.go`/`finale_test.go`/`montage_test.go`/
   `timeline_test.go`,全部通過)、還有 `cmd/fd2/ending_preview.go` 可以載入這些
   timeline——這整條「真結局演出」的渲染管線**已經做完且測試通過**,只是從來沒有被
   `campaign_full.json` 的 `ending` 節點呼叫過,兩邊各自完工但沒有串接。
3. `ending_ch27_no_sky_key`（壞結局,缺天空之鑰)也是類似的純文字佔位,同樣沒有接上
   `internal/ending` 管線,但至少它的文字本身是完整劇情文字，不是生成器備註洩漏。

**這是這輪 2-30 章抽樣裡發現的單一最高價值缺口**：玩家如果認真打完全部30章,得到的
不是團隊已經做好的真結局演出,而是一段看起來像除錯訊息的佔位字串。修復不需要新的
RE 工作（資料跟渲染都已存在),純粹是把 `main.go` 的 `case n.Type == "ending"` 分支
改成呼叫 `ending_preview.go` 已有的 `LoadTimeline`/`LoadFinalePhase`/`LoadMontage`
（或等價的正式播放路徑),並把 `campaign_full.json` 的 `ending`/`ending_ch27_no_sky_key`
兩個節點文字換成 `ch30.json`/`ch27.json` 裡的真實劇本文字。截圖：
`docs/knowledge-base/evidence/ending_stub_20260816.png`。

## 敗北/撤退路線首次驗證，抓到並修好一個真實 bug（2026-08-16）

使用者要求把先前列出的加強項目全部做完整，第一項是「敗北路線完全沒測過」——此前全部
30 章的驗證只走過 `on_win`，`retreat_chNN`（`on_lose` 目標）從未被真正跑過一次。

**新增 `FD2_SHOT_FORCE_LOSE=1`**（比照 `FD2_SHOT_FORCE_WIN` 的手法）：把這個節點的
`protect` 單位（預設「索爾」，`checkResult()` 同一個查找邏輯）HP 歸零,呼叫真正的
`g.checkResult()`→`g.camp.Advance("lose")`→`g.enterNode()`。

**第一次執行就抓到一個真實 bug（不是鉤子本身的問題）**：截圖顯示畫面卡在 ch01 戰場
（單位、HUD 全部還在)、疊著一個**卡住不消失的「敗　北」大字**,底下對話框是空的。
逐層排查：
1. **`g.result`（"win"/"lose"）整個程式碼庫從來沒有任何地方被清空過**——`Draw()` 裡
   「勝負(中央大字)」那段（`if g.result != ""`)完全沒有依 node type 收斂,只要
   `g.font != nil` 就畫,所以敗北大字會一直卡在畫面上,不管後續轉場到哪個節點。
2. **`g.st`（戰鬥單位/地圖狀態）在轉場到「無自帶地圖的 story 節點」時也從未被清空**——
   `enterNode()` 的 `case "story","cutscene":` 只有 `n.Map != ""` 分支才會清
   `g.st, g.sel = nil, nil`（註解甚至明講「避免上一戰場畫面疊在新背景上」),但
   `retreat_ch01` 這類單純對白節點沒有 `map` 欄位,完全繞過這行,導致上一場戰鬥的
   單位/HUD 全部原封不動疊在新節點上。

**修正**（`cmd/fd2/main.go` `enterNode()`）：
1. 在 `enterNode()` 最前面加 `g.result = ""`——進入任何新節點就代表上一場戰鬥的
   勝負旗標已經被消耗完畢（`Advance()` 一定在這之前呼叫過),沒有理由再留著。
2. 新增 `if n.Type == "story" && n.Map == "" { g.st, g.sel = nil, nil }`，把清空
   邏輯**只**擴大到「無地圖的 story 節點」這個已證實會出問題的情境。**特意沒有對
   `cutscene` 也套用同一無條件清空**：cutscene 節點的 beats（例如 `sync_party`,
   `syncPartyFromBattle()`）在 `enterNode()` 設好初始狀態後才逐幀執行,且明確需要讀
   `g.st` 取得剛結束那場戰鬥的最終單位狀態（HP/inventory）——第一次嘗試把清空邏輯
   對兩種 type 都套用時,直接讓 `go test ./...` 當場炸了三個測試（
   `TestCh00CompiledHandlerCarriesItsExactRuntimeRosterIntoChapterOne`／
   `TestInventoryGateSkyKeyRoutesThroughSyncThenPreparation`／
   `TestInventoryRecipeSuccessSyncsThenReturnsToTown`,全部是
   `"beat sync_party: no completed battle state"`)——回歸測試當場抓到範圍抓太寬,
   修正後改成只精準命中已證實的情境。

**鉤子本身也順手修好一個跟 2026-08-15 `FD2_SHOT_DISMISS_DIALOG`／2026-08-16 商店購買
同一類的 timing bug**：`FD2_SHOT_FORCE_WIN`/`FD2_SHOT_FORCE_LOSE` 原本都塞在
`shotSetup` 區塊（`g.frame >= g.shotFrame-1`,跟截圖本身幾乎同一幀),導致
`enterNode()` 之後新節點自己的對話框「展開」動畫（`g.dlgPhase`/`g.dlgT` 逐幀推進)
完全沒有真實幀數可跑——第一次截圖確認了這個症狀（空白對話框,沒有文字/頭像)。
兩個鉤子一起搬進新檔案 `cmd/fd2/shot_force_result.go` 的 `stepShotForceResult()`,
比照 `stepShotShopBuyConfirm()` 的做法:每幀檢查、一偵測到 `g.st != nil` 就立刻在
極早的幀觸發,把 `FD2_SHOT_FRAME` 之間的真實幀數都留給對話框動畫。

**修好後五章抽樣結果**（`FD2_CAMP_PREP_BATTLE=battle_chNN FD2_CAMP_NODE=battle_chNN
FD2_SHOT_FORCE_LOSE=1 FD2_SHOT_FRAME=300`）：
```
ch01: Advance("lose") -> retreat_ch01   ✅ 畫面乾淨,對白正確顯示
ch02: Advance("lose") -> retreat_ch02   ✅
ch10: Advance("lose") -> retreat_ch10   ✅
ch20: Advance("lose") -> retreat_ch20   ✅
ch30: Advance("lose") -> retreat_ch30   ✅
```
全部正確轉場到各自的 `retreat_chNN`,對話框正確顯示通用敗退文字「撤退！先回頭整頓，
再找機會反攻……」（查過 `campaign_full.json`：全部 30 章的 `retreat_chNN` 節點確實
共用同一句文字+各自的 `retried_chNN` set_flag+`next` 迴圈回原戰鬥,是資料本身刻意設計
成通用文字,不是像結局節點那樣的佔位字串遺漏)。截圖：`docs/knowledge-base/evidence/
lose_ch{01,02,10,20,30}_20260816.png`。`go build`/`go vet`/`go test ./...`（含
`cmd/fd2`/`internal/battle`/`internal/campaign` 全部套件）確認乾淨。

此為 E1 等級證據，是這次「敗北路線從未測過」缺口的完整關閉——不只是驗證通過，過程中
還抓到一個會影響每一個真實玩家（不只是這個除錯鉤子）的真實 bug：只要玩家在任何一章
戰敗，畫面就會卡住不消失，這次之前完全沒人發現過。

## `postbattle_chNN_persist` 節點驗證：確認一個已知、刻意 fail-closed 的真實內容缺口（2026-08-16）

用 `FD2_SHOT_FORCE_WIN` 對有 `postbattle_chNN_persist` 節點的章節逐一驗證（這類節點是
`battle_chNN.on_win` 的目標,負責 `sync_party` 之類的戰後同步 beat,再接回 `town_ch(N+1)`
或 `preparation_ch(N+1)`）。先測 `ch04`（有 `handler_binding`）：正確渲染,索爾頭像+對白
「奇怪了，在這大陸上到處都遇得上強盜！」正確顯示在戰場背景上（cutscene 節點特意保留
`g.st` 不清空,見上方敗北路線那節的說明,這裡的戰場殘留是刻意設計,不是 bug）。

**再測 `ch22`（無 `handler_binding`）,觸發一個明確的 fail-closed 除錯訊息**：畫面卡在
戰場,疊著文字「**戰後 handler 尚未接線，流程已停止**」。查 `main.go`
`case "story","cutscene":` 對應段落,這是**刻意的保護機制**（註解原文：「An unbound
postbattle node must never be treated as an empty interlude: doing so would silently
skip persistent sync/rewards and jump straight to town」）——`beats` 為空且沒有
`handler_binding` 時主動停住,不會靜默跳過同步邏輯直接進城鎮,是誠實的「還沒做」訊號,
不是程式碼缺陷。

**完整盤點 23 個 `postbattle_chNN_persist` 節點**，`handler_binding` 存在與否：
```
有 handler_binding（16 章,推定可正常運作,ch04/ch16 兩種都測過,ch04 有=通過）：
  ch04 ch05 ch06 ch07 ch08 ch09 ch10 ch11 ch12 ch13 ch14 ch15 ch19 ch20 ch25 ch26 ch28

無 handler_binding（7 章,會觸發上述 fail-closed 訊息,流程卡住）：
  ch16 ch17 ch18 ch22 ch23 ch24 ch29
```
`ch16` 額外實測確認,跟 `ch22` 一樣卡在同一段訊息（不是 ch22 單一個案）。

**結論**：這是一個真實、範圍明確的內容缺口——玩家正常遊玩到第 16/17/18/22/23/24/29 章
戰鬥勝利後,流程會卡住,直到對應的 `handler_binding` 檔案（比照 `ch03_post.json` 等
既有檔案的反組譯/編譯方式)補齊為止。修復需要對這 7 章的戰後過場做跟既有
`assets/cutscenes/bindings/ch*_post.json` 同等的反組譯/資料撰寫工作,不是能在這輪
「即時操作驗證」裡順手改的程式碼修復（跟結局播放那個「資料/程式碼都做好只是沒接線」
的缺口性質不同——這裡是資料本身還沒生出來）,已另外開一個背景任務追蹤。截圖：
`docs/knowledge-base/evidence/win_ch{04,16,22}_20260816.png`。

## 商店商品/價格資料驗證：先誤判、被既有測試抓到、更正後確認資料本身正確（2026-08-16）

上一輪抽樣（ch02-30）明確記錄「商品清單有沒有跟原版一致從未驗證過」,這輪去查。找到
`docs/data/shops.json`（來源標註「青衫攻略」,涵蓋 ch02-22+ch26-27 共 23 章、69 個
商店紀錄,含真實原版售價)。**第一次比對就以為抓到大 bug**：`campaign_full.json` 每個
`shop_chNN_*` 節點的 `goods[].price` 全部是 1~10 的小數字,跟參考資料的真實售價
（如龍神劍上千、藥草10)完全對不上,寫了一支腳本直接把全部 337 個價格改成參考資料的
原始數字,`go build`過關就以為修好了。

**`go test ./...` 當場抓到這是誤判**：`internal/campaign/campaign_test.go` 既有測試
`TestCampaignFullPostBattleTownContractMatchesOriginalShopChapters` 全部 7 個子測試
失敗——仔細看測試原始碼才發現,這個測試本來就會載入同一份 `docs/data/shops.json`,
但接著套用一個內建的 `qolShopPrice` 對照表（同檔案 453-471 行,附註解：「刻意偏離
原版的重製版售價調整表(使用者要求):把全遊戲123種商店貨品的原始 item.json
price(10..50000)等比縮放到1..10」)才是最終期望值,還額外把6件轉職道具（聖者之戒等,
id 88-93)加進每章道具店（同檔案 626-638 行註解：「原版完全不進商店貨架,只能靠
寶箱/事件取得;此處是使用者要求的重製版 QoL 調整」)。也就是說：**`campaign_full.json`
的小數字售價、以及每章都能買到轉職道具,兩者都是先前 session 就已經確認過的刻意設計
（使用者要求的重製版 QoL 調整),不是資料品質問題**——我這次一開始的「修正」實際上是
拿真實原版售價蓋掉了正確的、已測試過的重製版資料,是我自己的誤判,不是這次才發現的
bug。

**已更正**：寫另一支腳本用 `qolShopPrice` 表把全部 337 個價格改回縮放後的數字,
`go vet`/`go test ./...`（全部套件）確認回到全綠,即時截圖重驗證
（`shop_ch02_item` 真實購買:藥草 price=1,`goldBefore=1000 goldAfter=999`)跟這次
session 稍早 ch02 真交易驗證的原始結果完全一致,證實資料已還原正確。

**結論（更正後）**：商店商品/價格資料**其實已經驗證過**,只是驗證機制是既有的
`TestCampaignFullPostBattleTownContractMatchesOriginalShopChapters`（涵蓋全部
23 章有商店的章節、69 個商店節點),不是這次才補上的——這條待辦項目原先的判斷
「商品/價格資料從未驗證過」本身就不準確,先前的抽樣只是沒去檢查 `internal/campaign`
套件既有的測試涵蓋範圍。這次的價值在於：(1) 確認這個既有測試現在真的是綠的、
真的在保護這份資料;(2) 誠實記錄自己一次因為沒有先檢查既有測試/設計意圖就動手
「修正」資料,導致短暫引入一次真實迴歸,所幸被測試立即攔下,過程記錄下來避免下次
重蹈覆轍——**改資料/程式碼前,`go test ./...` 是第一步不是最後一步**。

## AI 施法/道具執行鏈：確認有紮實單元測試，但這輪嘗試的即時 E1 觀察沒有自然觸發（2026-08-16，未完全關閉）

`main.go` `aiStep()`（9370行起)確認**確實有**完整的 AI 施法/道具執行分支——`plan.ItemID
>= 0` 時呼叫 `g.st.ApplyNativeAIItemCommand()`,`plan.SpellID >= 0` 時呼叫
`g.executeNativeCommandTarget()`,兩者都失敗才退回一般物理攻擊,不是只有攻擊一條路。
`internal/battle` 底下有 4 個對應測試檔（`native_ai_item_execute_test.go`／
`native_ai_three_score_plan_test.go`／`native_ai_14237_apply_test.go`／
`combat_test.go`)專門涵蓋這條決策+執行邏輯,單元測試層級不是空白。

**嘗試用真機（非單元測試)觀察 AI 主動施法/用道具,這次沒有成功**：`FD2_SHOT_AI=1
FD2_SHOT_TURN=6 FD2_SHOT_FRAME=2000` 打 `battle_ch02` 六個回合,`grep`「原始指令」
「原始道具」完全零筆命中,連「AI決策」這個無條件的除錯 log 都只出現1次——代表
`FD2_SHOT_TURN` 這個目前用途是「觸發增援事件」的鉤子（連續呼叫 `g.endTurn()` N次)
沒有真的讓 `aiStep()` 逐幀跑完每個敵方單位的決策,不是適合拿來觀察 AI 逐一決策內容
的工具,這點跟 2026-08-13 `FD2_SHOT_AUTOPLAY` 曾經在完整多回合下真的看到
「AI決策」log 交錯出現的成功案例不同——這裡的失敗看起來是**方法沒選對，不是 AI
邏輯真的沒有作用**。

**另一個可能原因（尚未排除)**：查了 `ch05.json` 等劇本檔的 `party` 欄位確認法術
（`spells:[...]`)只出現在玩家角色定義,`initial_groups`/`runtime_append_groups`
只是敵方群組索引,沒有內嵌逐一敵方單位的法術清單——如果敵方的施法/用道具資格是從
`native_record_class`(職業)查一張獨立的職業能力表決定,而不是逐單位顯式指定,那麼
「這一戰的敵人裡到底有沒有配到施法者/補師職業」本身還沒有被確認過,也可能是
ch02 這張圖剛好敵人清一色是物理職業,不是鉤子失靈。

**結論**：AI 施法/道具「有沒有寫」已經用程式碼閱讀+既有單元測試確認**是有的**,但
「這條路徑在一場真機戰鬥裡真的被敵方 AI 走過一次」這件事這輪沒有拿到 E1 證據——
需要比照 `FD2_SHOT_SPELL_CONFIRM`（玩家側)的做法,寫一個專門鎖定「敵方有施法者/
道具使用者的職業」+ 直接把該單位排到 AI 決策佇列最前面的除錯鉤子,而不是指望自然
連續回合裡剛好碰到,才能確定關閉這個缺口。範圍保留在 task #98/#103/#104,標記為
**未完全關閉**,不誠實地喊完成。

### 後續追查（同日）：找到「為什麼觀察不到」的具體機制，但沒有追到終點

繼續深挖上面的缺口,新增暫時性除錯輸出（用完即刪,未留在程式碼裡)拆解
`nativeAIThreeScorePlan()` 五個 fail-closed 前置條件,逐一測試找到兩個具體、不同的
真實現象：

1. **`FD2_SHOT_AUTOPLAY=1` 搭配 `FD2_AI_DEBUG=1` 完全沒有輸出**（0 筆,連一次都沒有)
   ——這條路徑可能根本沒有真的驅動 `aiStep()`/`NextAIPlan()`,還是驅動了但某個
   更早的關卡擋住,這次沒有查到底,只確認了「autoplay 不是觀察 AI 決策內容的正確
   工具」。改用 `FD2_SHOT_AI=1`+`FD2_SHOT_TURN=N`（不搭配 autoplay)才true 觀察到
   真實除錯輸出。
2. **`battle_ch02` 確認整條三管線評分邏輯真的有跑,不是空殼**：抓到一筆真實案例
   ——一名劍士敵人 `physical={HasWinner:false} spell={HasPositiveWinner:false}
   item={HasPositiveWinner:false}`,全部真的算出 0 分（不是資料缺失導致的
   fail-closed,是五個前置條件都通過、真的跑完評分後三個管線都不夠格出手)。這證明
   評分機制本身是真實在執行的邏輯,不是死碼。
3. **`battle_ch02` 的敵方陣容經抽查全部是同一種「劍士」物理職業**（`map1_units.json`
   `native_record_class` 全部相同),先查了 `map*_units.json` 找出哪些地圖的敵方
   陣容包含法師類職業（`native_record_class=5`),`map3`（即 `battle_ch04`)是其中
   一個。
4. **改測 `battle_ch04` 卻踩到另一個完全不同的失敗模式**：`NativeAIScoringRecords`
   直接報錯「native AI record: unit 0 lacks raw provenance」——這個錯誤會讓**整個
   三管線評分（不只法術/道具,連物理都一起)對這場戰鬥的所有敵方單位失效**,退回
   舊版 `aiTargets` 近似邏輯。換了 `FD2_SHOT_PARTY_BINDING=ch03_pre.json` 想測試
   「是不是我這個測試鉤子沒有正確灌隊伍」這個猜測,結果一樣報錯,排除了這個特定
   猜測,但沒有進一步查出`unit 0`（`g.st.Units[0]`,不確定是玩家還是敵方,要看
   `map3_units.json`實際排列順序)到底缺了哪個 raw provenance 欄位、也沒有查出這是
   `battle_ch04` 這個關卡本身資料的問題,還是「用 `FD2_CAMP_PREP_BATTLE` 直接跳戰鬥」
   這個測試捷徑跟正常玩家「走 `story_ch04_pre`→`preparation_ch04`→正常進場」路徑
   之間的差異造成的。

**誠實小結（第一輪)**：這輪把「完全沒有任何線索」推進到「有兩個具體、可重現的現象,
各自需要繼續往下查」，但都沒有查到底、也沒有做出修正。

### 追加（同日）：查清楚 provenance 缺口的精確根因，判斷極可能是測試手法的產物，不是真的遊戲 bug

順著上面的線索繼續查,加暫時性 log 直接印出 `NativeAIScoringRecords` 要求的 8 個
provenance 欄位分別是 true/false（而非只看整體錯誤訊息)。結果非常明確：
`battle_ch04` 卡住的單位（`g.st.Units[0]`,`map3_units.json` 陣列第一筆,一隻無名的
敵方劍士)**只有 `HasNativeMapPresentation=false`,其餘 7 個欄位全部 true**——不是
資料本身缺欄位（`map3_units.json` 的 `native_record_byte34/35/36`／`word42/46` 等
原始欄位其實都在,跟能正常運作的 `map1_units.json`/ch02 結構完全一樣),是這個特定
的 runtime 旗標從未被設置過。

**追查 `HasNativeMapPresentation` 怎麼被設置**：只有 `MaterializeNativeMapPresentation()`
（`internal/battle/native_map_presentation.go`)會設,而這個方法只從
`MaterializeNativeMapSelectorSlots()`（`model.go`)/`AppendNativeMapSelectorBatch()`
（同檔)被呼叫——後者的呼叫點只有三處：
1. `main.go:2386`，藏在 `if adoptHandlerState {...}` 分支裡——只有當「這場戰鬥前
   已經有一段相容的過場劇本(`storyRosterPath`/`storyPartyScenario` 精確比對
   `unitsPath`/`scnPath`)先把隊伍/單位排好」才會進來。
2. `native_spawn_intro.go:95`、`native_indexed_transition.go:83`——都是「單位進場
   演出」（spawn intro / 過場淡入)這類**過場動畫 beat** 才會呼叫的程式碼,不是
   `resetBattle()` 本身的一部分。

**這代表**：正常玩家路徑（`preparation_ch04`→`story_ch04_pre` 過場→`battle_ch04`)
一定會先走過一段有 `spawn_intro` 之類 beat 的過場,那段 beat 執行時就會呼叫
`AppendNativeMapSelectorBatch`,把 `HasNativeMapPresentation` 正確設好——但這次
用來驗證的 `FD2_CAMP_PREP_BATTLE`（本來就是為了「跳過整段過場,直接進戰鬥,加快
驗證」設計的除錯捷徑)完全繞過這整段過場 beat,連帶把這個 AI 前置需求也一起繞過了。
`FD2_SHOT_SKIP_STORY` 沒有幫助（它只跳過鏡頭運鏡動畫,不是跳過 beat 執行本身），
`FD2_SHOT_PARTY_BINDING` 也沒有幫助（測過,見上一輪記錄——它填的是隊伍名冊,不是
`AppendNativeMapSelectorBatch` 要求的 `adoptHandlerState` 精確路徑比對）。

**沒有完全排除、留給下次的一個疑點**：`battle_ch02` 用同一套 `FD2_CAMP_PREP_BATTLE`
手法卻沒有踩到這個錯誤,矛盾之處這輪沒有查到底——合理的推測是 ch02 那次測試剛好
命中了某個我還沒定位到的例外路徑（也可能是我沒有意識到的環境差異，例如兩次測試
剛好在不同的 shotSetup 時序點觸發),但不能排除「其實兩者都有同樣的缺口，只是 ch02
那次的第一個 AI 決策剛好在錯誤真正被觸發之前就已經被截圖鉤子中斷」這個可能性。

**修正後結論**：AI 施法/道具評分邏輯本身（`ScoreNativeAI1598A`/`ScoreNativeAI1567E`/
`SelectNativeAIThreeScoreWinner`)有紮實的單元測試涵蓋,且已經在 `battle_ch02`
真機拿到一次「跑到底、給出真實（雖然是全 0）評分」的證據，證明管線不是空殼。
真正卡住的 `battle_ch04` provenance 缺口，極可能是這次驗證特地為了「跳過過場、
加速測試」而設計的 `FD2_CAMP_PREP_BATTLE` 捷徑本身的已知限制，不是玩家實際會撞到
的遊戲缺陷——但因為 ch02/ch04 的矛盾沒有徹底排除，還不能 100% 打包票說「真實玩法
完全沒有這個問題」。要徹底關閉，下一步應該是**不用 `FD2_CAMP_PREP_BATTLE`**,改用
連續呼叫 `FD2_SHOT_FORCE_WIN` 從 ch01 一路真實推進 node graph（`story_ch02`→
`town_ch02`→...→`story_ch04_pre`→`battle_ch04`)自然抵達 `battle_ch04`,讓真正的
過場 beat 有機會執行,驗證這樣進場後 AI 施法/道具是否正常運作——這是比這次的捷徑
測試更貼近真實玩家路徑的驗證方式，但成本明顯更高（要處理過場對話跳過/推進的
時間管理),這次時間所限沒有做完。

留在 `task #98/#103/#104`，狀態誠實標記為 `in_progress`——已經從「零線索」推進到
「找到精確的技術原因＋強烈懷疑是測試捷徑的已知限制，非玩家會撞到的真缺陷」，但
「ch02/ch04 為什麼行為不一致」跟「用真實過場路徑重新驗證」這兩步還沒有做完，
不誠實地喊完成。`go build`/`go vet`/`go test ./...` 全綠，暫時性除錯 log 已移除。

## 指令環選中格脈動：實作已在（更早的 session 段落),這輪嘗試截圖驗證但沒有得出結論（2026-08-16）

`ringPulse`/`resetRingPulse()`/`stepRingPulseTick()`（`action_overlay_runtime.go`)
其實這次 session 較早的段落就已經寫好+有單元測試,doc58 當時就記錄「尚未實機截圖
複測」。這輪嘗試把這個「尚未」補上,過程：

1. 先用既有的 `FD2_SHOT_RING`（+`FD2_SHOT_RING_FRAME`)在 frame 60/64/200 三個不同
   時間點各截一張圖,寫一支拋棄式 Go 小工具逐像素比對選中格邊框區域——三張完全
   像素級相同,懷疑是跟這次 session 已經修過兩次的「鉤子塞在 shotSetup 裡,跟截圖
   幾乎同一幀,沒有真實時間可跑」同一類 timing bug（`stepRingPulseTick` 讀的是
   `time.Now()` 真實時鐘,不是幀數)。
2. 依照 `stepShotForceResult`/`stepShotShopBuyConfirm` 的既有模式,新增
   `FD2_SHOT_RING_PULSE_WATCH=1`（獨立檔案 `cmd/fd2/shot_ring_pulse_watch.go`,
   每幀檢查、一偵測到 `g.st != nil` 就立刻開環,不等 shotSetup 那個晚期閘門)——
   **刻意不去動既有的 `FD2_SHOT_RING`**,因為那個鉤子的用途是凍結某個已知的
   開/關動畫幀做像素比對,不需要真實時間,跟這裡「觀察穩態脈動」是不同目的,
   混在一起改風險較高。
3. 用新鉤子重測,`FD2_SHOT_FRAME=10` vs `FD2_SHOT_FRAME=300`（同一支已修正的
   binary,兩次獨立行程)——**仍然逐像素完全相同**,推翻了「純粹是 shotSetup
   同幀」這個假設,矛盾之處：查了 `nativeBIOSClock.Sample()` 原始碼確認節奏是真的
   綁定 `time.Now()`（54.9ms/tick，需要 4 tick≈220ms 真實時間才推進一次),
   300 幀在 headless xvfb+llvmpipe 渲染下理論上應該早就超過 220ms,但畫面依然
   沒有變化。

**沒有查到底的原因,誠實列出待查方向**：
- 可能是我採樣座標選錯（逐 4px 網格掃選中格邊框範圍,如果實際邊框只有 1px 寬,
  網格可能跳過真正變色的那一圈像素)。
- 可能是 headless/off-screen 渲染下 Ebiten 的 Update() 節奏跟真實視窗環境不同
  （例如批次處理、或每幀實際消耗的 wall-clock 遠低於預期,300幀可能遠不到
  300ms)。
- 也可能真的是一個先前未發現的獨立 bug（`stepRingPulseTick` 或
  `drawRing`/`drawNativeActionOverlay` 沒有正確消費 `g.ringPulse` 的最新值)。

三個可能都沒有排除。新增的 `FD2_SHOT_RING_PULSE_WATCH` 鉤子保留在程式碼裡（乾淨、
獨立、有清楚註解,不影響其他既有行為),下次要接著查應該先用更細緻的逐 1px 掃描
+ 印出 `g.ringPulse` 實際數值到 log（而非只看畫面顏色)來確定到底是「數值沒變」
還是「數值變了但沒反映到畫面」,這是比這次亂槍打鳥更精準的下一步。`go build`/
`go vet`/`go test ./...` 全綠,沒有留下任何未清理的暫時性除錯程式碼。

### 追加（同日）：照上面自己寫的「下一步」查下去，找到並修好真正的根因

按照上一節結尾自己寫的建議，加了暫時性 log 直接印 `g.ringPulse`/
`g.ringUIClock.elapsedTicks` 數值（而非只看畫面顏色）。結果立刻分岔成兩個問題：

1. **狀態本身完全正常**：同一次連續執行中，`ringPulse` 確實從 0（frame 1）真的推進到
   2（frame 300, elapsedTicks=91），跟 `nativeBIOSClock`（54.9ms/tick）的節奏吻合。
2. **但畫面沒有反映**——把 log 加進 `drawNativeActionOverlay()`（原生素材版渲染路徑,
   有提供原版 FDOTHER.DAT 的玩家實際看到的畫面）內部後發現：**這個函式從頭到尾完全
   沒有讀取過 `g.ringPulse`**。查 `drawNativeActionOverlay` 呼叫點（`if
   g.drawNativeActionOverlay(...) {...} else {...原本的文字/純色框 fallback...}`）
   確認這是 if/else 二選一，不是疊加——2026-08-13 那次新增的脈動效果，只接進了
   `else` 分支（沒有原版素材時的文字/色塊後備），從未接進 `if` 分支（有原版素材,
   也就是大多數真實玩家會走的那條路徑）。**這代表這個「功能」對提供了原版
   FDOTHER.DAT 的玩家而言,從 2026-08-13 加進來那天起就完全沒有作用過**,是一個
   跟前面 ch01/ch02 那些真實 bug 同等級的發現，只是這次是靠自己的除錯基礎設施
   (`FD2_SHOT_RING_PULSE_WATCH`) 才抓到。

**修正**（`cmd/fd2/main.go` `drawNativeActionOverlay`）：在原生疊圖迴圈裡,對
`direction == g.ringSel`（native 方向序 0-3=上左右下,跟 `g.ringSel` 是同一套編號,
見 4358 行「↑0攻擊/←1法術/→2物品/↓3待機」註解,不需要換算)那一格,額外畫一圈
`g.ringPulse` 驅動的橘色系邊框——邏輯完全比照 `else` 分支既有的 `border()` 寫法
（同一組顏色常數:亮橘 `0xff,0xa8,0x20`／暗橘 `0xb0,0x74,0x16`,同一個
`ringPulse>=2` 判斷式),只是這次真的接進了原生渲染路徑。

**驗證過程也走了一次彎路，一併誠實記錄**：第一次用逐 2px/4px 網格採樣的拋棄式像素
比對工具測試修好後的兩張截圖（frame 1 vs frame 300），**結果仍然是 0 差異**，一度
以為修復無效。加了更細的 log 確認 `drawNativeActionOverlay` 內部這次真的有讀到
`g.ringPulse` 的最新值（0→2、顏色常數也正確跟著換），矛盾之處靠寫一個「不跳格、
掃整張圖」的拋棄式比對工具解開——**整張圖的網格採樣工具因為取樣間距（2-4px）跟
邊框只有 3px 寬的巧合,系統性地跳過了真正變色的那一圈像素**，換成逐 1px 全圖掃描
後正確抓到 2636 個差異像素，bbox 完全落在指令環的螢幕位置。再裁切放大兩張截圖
肉眼比對確認：frame 1 是鮮豔亮橘、frame 300 是明顯偏暗的琥珀橘——**這才是這個功能
在 2026-08-13 加進來以來，第一次有真正的畫面級證據證明它在動**。截圖：
`docs/knowledge-base/evidence/ring_pulse_native_{bright,dark}{,_crop}_20260816.png`。

`go build`/`go vet`/`go test ./...` 全綠，兩個暫時性 log（`captureShot()` 裡的
`FD2_SHOT_RING_PULSE_WATCH` 除錯輸出、`drawNativeActionOverlay` 裡的逐格除錯輸出）
確認過根因、驗證過修復後都已移除，只留下乾淨的 `FD2_SHOT_RING_PULSE_WATCH` 驗證
鉤子（`shot_ring_pulse_watch.go`）跟正式的邊框繪製修正。這個項目正式關閉。

## 騎兵/飛行移動類型：查完發現這其實不是真正的缺口，是先前寫文件時漏看了另一條已完成的路徑（2026-08-16）

先查有沒有現成的反組譯資料可以省下重新 RE 的工——`docs/knowledge-base/45-class-name-mapping.md`
證實遊戲內文確實有一份 54 筆敘事身分名清單（含「騎兵」「突擊騎兵」「地獄騎士」「龍騎士」等),
但同一份文件明確記載這些名字**還沒有**綁定到任何數字職業欄位的 ABI,所以沒辦法從職業名稱
直接反推 `native_record_class`。

**改查 `MoveCostFor`（`internal/battle/move.go`)的完整實作，發現這個項目其實已經解決了，
只是先前（2026-08-14 那次 ch01 段落)寫文件時漏看了它自己的第一條分支**：

```go
func (s *State) MoveCostFor(u *Unit, x, y int) int {
    base := s.MoveCost(x, y)
    if u == nil || base >= 99 { return base }
    if native, ok := s.nativeMoveCost(u, x, y); ok {
        return native   // ← 優先路徑,已經是反組譯確認過的真實資料
    }
    if u.MoveType == MoveWalk { return base }   // ← 這才是「沒有原生資料時」的近似後備
    ...
```

`nativeMoveCost()` 查的是 `assets/data/native_movement_cost_rows.json`——**0x4e555 的
29×20 逐職業地形成本表,而且 selector 推導邏輯本身在 `move.go` 註解裡標明「2026-08-14
Ghidra 反組譯新版參考 EXE 確認,呼叫點 0x14b78」,不是猜測**。也就是說：**逐職業的移動
成本差異化,原本就已經有反組譯等級的真實資料在跑,不需要额外的「這個職業是騎兵/飛行」
分類**——`MoveType` 這個三分類 enum 純粹是給「沒有載入原版素材」這個邊緣情境用的近似
後備,不是主要路徑。

**直接讀這份表驗證資料本身確實有意義的差異化**（29 個 selector,每個 20 欄地形成本):
```
selector 0 (擋: 0)  costs=[1,1,1,1,1,1,1,1,...]        全部1,不受任何地形影響
selector 3/11(擋:2) costs=[1,1,20,2,3,3,20,1,...]      同一個欄位比多數 selector 貴一倍,
                                                         跟 doc02 §3.1「步行1→騎兵2/
                                                         步行2→騎兵3」的差值分毫不差
selector 15/19(擋:1)costs=[1,1,1,1,1,1,20,1,...]       只有一種地形不可通行,其餘全平地
selector 28(擋:5)   costs=[1,20,20,20,20,1,20,1,...]   五種地形不可通行,高度受限
其餘24個 selector    costs=[1,1,20,1,2,2,20,1,...]      多數職業共用的標準步兵模板
```
**選了 `battle_ch20`（doc58 之前記錄「全部33張地圖裡唯一有非1/99地形成本值」的那張圖)
交叉核對**：`map19_units.json` 的敵方陣容裡真的有 `native_record_class=28`
（`[1,2,3,7,8,12,13,14,23,28]`)——正是上面表格裡「五種地形不可通行」那個高度受限的
特殊 selector,證實這個差異化資料在真正會用到它的章節上確實有對應的職業存在,不是
表格空有資料沒人用。

**結論**：這個項目不需要新的反組譯工作——真正驅動遊戲移動成本的路徑（`nativeMoveCost`)
早就是逐職業精確、反組譯確認過的資料，`MoveType` 分類只是後備近似值，故意留空是正確
決定（`move.go` 自己的註解已經寫明「原版哪個職業對應哪個移動類型,目前沒有反組譯確認的
資料來源,用猜的標反而會引入新的不準確」）——這句話原本的語境是針對 `MoveType` 這個後備
enum，不是對整個移動成本機制，這次確認整個機制本身沒有被這個「留空」拖累。標記為
**已釐清,非真缺口**，不需要排進背景任務。

## DOSBox E2 第二次嘗試（ch01 法術/道具）：這次沒有再意外中斷，但也沒有拿到乾淨證據（2026-08-16）

使用者選擇「再試一次」。這次全程用全螢幕（`Alt+Enter` 一開始就切),用大批次
（每次 50-100 顆 `Return`)重跑整段開場過場,**這次全程沒有再發生任何一次誤觸中斷**
（上次是全螢幕下一次 `Escape` 直接把整個遊戲踢回 DOS 提示字元,這次同樣有用到
`Escape`(從指令環子選單退回)但每次都正確只退一層,沒有意外退出遊戲)——證實
「全螢幕+分批操作」本身是可行、穩定的技巧，上次的中斷是操作失誤，不是這套方法
本身不可靠。

**意外收穫**：發現 `Tab` 鍵可以直接循環切換到下一個未行動的我方單位,不需要在小
視窗裡肉眼逐格搜尋——比上次全靠肉眼掃描地圖有效率得多,這是這次真正學到、對未來
DOSBox 驗證有用的新技巧。

**沒有找到悠妮，且有理由懷疑她這章根本沒有被部署**：用 `Tab` 循環只在「索爾」跟
「亞雷斯」之間切換，蓋亞可選但循環不會停在他身上（可能已經行動過），**完全沒有
循環到悠妮**——對照這次 session 稍早記錄的第一章開場劇情「發現昏迷的悠妮」，
合理懷疑**原版第一章的悠妮是以「傷患」身分登場,不是可操作的出戰單位**,跟
remake 端 `ch01.json` 的 `deploy_cells` 把她列在 4 個部署格之一（可能是重製版
為了「隨時可召回」設計的近似,不代表原版第一章她真的能被玩家操作)不一致——這點
沒有查到底，只是提出一個有敘事根據的合理懷疑，供下次確認。若這個懷疑成立，代表
`FD2_SHOT_SPELL_CONFIRM` 那次 E1 測試（debug-only 把她瞬移進戰場做為測試單位)
本身完全合理（是測試法術執行的機制本身,不宣稱它是玩家在原版第一章真的能做到的
操作)，但也代表她不會有對應的自然 DOSBox E2 場景可比對，除非改用她真的登場的
更後面章節。

**索爾道具選單這次卡在一個看不懂的兩選一畫面**：選「物品」方向後沒有進入預期的
道具清單，而是出現一個 `NO`/`YES` 兩選一畫面（放大確認過文字，不是我誤讀)——
不確定是索爾這格的地形（樹林)觸發了某種特殊確認、還是指令環方向鍵輸入在小視窗下
再次掉字（doc58 開頭「環境已知問題」第5條已經記過這條路徑特別容易掉輸入)。試了
兩次都卡在同一個畫面，沒有繼續深究就安全退出，避免誤觸任何真的會扣道具/消耗行動
的操作。

**結論**：這次確認了操作方法本身可靠（全螢幕+分批+Tab 循環),排除了「上次中斷是
方法有問題」的疑慮，但沒有拿到法術/道具的乾淨 E2 截圖證據。比較有價值的產出是
「Tab 循環選人」這個技巧本身,跟「悠妮第一章可能根本不能操作」這個有敘事佐證的
新懷疑——兩者都值得記下來,下次要嘛先用 `Tab` 直接排除悠妮不在場的疑慮、要嘛
乾脆換一個悠妮確定會登場（且道具選單不會卡住)的章節重測。DOSBox 視窗目前停在
安全的地圖選人畫面（未關閉),沒有進一步操作。

**待決事項更新（2026-08-16）**：使用者選擇「先回頭處理 ch02 缺口」。church 圖示 bug 已經
不需要 DOSBox 就找到 root cause 並修好（見上方，靜態 hex dump 加尺寸門檻判斷式就夠了，
不用真的架 DOSBox）。還剩：**DOSBox E2 像素比對（目前 ch01/ch02 全部是 E1，一次都還沒做）**。
ch03 起 27 個章節如果每章都比照 ch02 的窮舉深度（逐節點類型+真實交易執行）來測,是不小的
重複工程量,因為節點類型的程式碼路徑已經證明是共用的——ch03 已改用抽樣式驗證（見上方）。

### DOSBox E2（法術/道具）嘗試中斷，改判斷放棄手動重試（2026-08-16）

使用者選擇「先測 ch01 可達的項目（法術/道具）」，即不用真的打完整場 ch01 換取 church E2，
改測從冷開機互動走到 ch01 戰場即可測到的法術/道具施放。實際執行：

- 冷開機（DOSBox 0.74-3,`FD2.EXE`）手動連按 Enter 走完整段開場過場（王座廳傳位→王城偶遇→
  比劍邀約→登陸/海盜遭遇→「累死了,大家休息一下吧！」開場對白,逐句對照 `ch01.json` 完全
  一致),約 750-900+ 次按鍵後進入可互動戰場,成功選取單位（索爾:HP042/042 MP000/000,跟
  `ch01.json` 數值一致；蓋亞移動範圍高亮正常顯示）。
- 找悠妮（法師,唯一天生會施法角色,見上方 E1 記錄）的過程中,在小視窗(344×214px)下無法從
  截圖判讀指令環方向鍵游標實際停在哪一格（YES/NO 確認框、四象限指令環的高亮樣式在這個解析度
  下截圖後肉眼/縮放都分不出差異）,`left_click` 對遊戲視窗完全沒有作用（DOSBox 這個設定下
  鍵盤才是唯一輸入路徑,滑鼠點擊不會被遊戲讀取,只有系統視窗本身的裝飾按鈕才吃滑鼠）。
- 嘗試 `Alt+Enter` 切全螢幕改善可讀性,確實讓圖示變清楚很多,但摸索指令環子選單時按了一次
  `Escape`,結果**直接把 `FD2.EXE` 踢回 DOS 提示字元**（不是回到上一層選單,是整個遊戲流程
  中斷退出）——用掉的 750-900+ 次按鍵重跑進度全部歸零。

**判斷**：手動 DOSBox 互動在這台環境下有兩個疊加的成本/風險——(1) 每次到達可測狀態的固定
成本是 700-900+ 次按鍵、無法存檔跳點；(2) 小視窗下無法可靠讀出選單游標狀態,只能盲操作,
一步操作錯誤（這次是全螢幕下的 `Escape`）就會清空全部進度,沒有中繼點可以回退。這跟已經
成功拿到的 ch01 攻擊 E2（2026-08-15,同樣的手動流程,擊殺畫面確認,見上方）不是流程本身不可行,
而是這次沒有再重試的邊際價值——法術/道具的**執行邏輯**（射程判定、邊界值、MP/HP 增減、
封頂裁切）已經有比 E2 截圖更精確的 E1 證據（真實編譯執行檔、真實資料、真正呼叫
`CastArea()`/`applyNativeTargetItem()`,含邊界值跟負向控制組,見上方兩個對應段落),E2 對這兩項
能新增的資訊只剩「畫面像素長相是否吻合」,而指令環 UI 本身的像素級外觀已經在 2026-08-15 的
攻擊 E2 驗證過一次（劍+頭盔/法杖/袋子圖示、配色、四方位置,見上方,法術/道具走的是同一個
指令環,不是獨立 UI）。

**結論**：ch01 法術/道具 DOSBox E2 標記為「刻意暫緩,非技術卡關」,不再用盲操作硬測——如果
之後要補,應該先解決「小視窗看不清游標狀態」跟「沒有中繼存檔點」這兩個根本限制（例如用
F5 存檔功能在到達戰場後立刻存一個檔,之後可以直接 Load 復用,不必每次重走開場過場),而不是
重複同樣的盲操作。優先度讓給 ch03+ 的鏈路可達性/資料正確性抽樣驗證（下方繼續）。

### AI provenance 缺口根因：`runtime_append_groups` 缺席,21/30 章全面補上（2026-08-16）

**起點**：使用者提出假說——`battle_ch04`（及其他章節）native AI 三管線評分報
`"native AI record: unit 0 lacks raw provenance"` 錯誤,是不是因為 ch01 角色還沒拿到道具
（items）。逐一檢查駁回：`map3_units.json` unit[0] `inventory: [1, 132]` 本來就有真實道具;
`ch04.json` 的 `group: 1` 也在 `initial_groups: [1]` 內,不是尚未登場的增援。假說不成立,
改照使用者指示的方向繼續往下查「測試捷徑（`FD2_CAMP_PREP_BATTLE`）到底漏了什麼」。

**根因鏈**（完整呼叫鏈往回追）：
`NativeAIScoringRecords` 要求批次內每個單位 `HasNativeMapPresentation` 為真 → 這個欄位只由
`Unit.MaterializeNativeMapPresentation()` 設定 → 該函式只被
`MaterializeNativeMapSelectorSlots()`/`AppendNativeMapSelectorBatch()` 呼叫 → 全專案只有 3 個
呼叫點,其中最關鍵的是 `(*State).AppendGroup(group)`（`model.go:1472`）,它**只在**
`s.NativeMapSelectorCache != nil && s.NativeMapSelectorError == nil` 時才做原生材質化 → 而
`AppendGroup` 本身**只在** `(*Scenario).Setup()`（`event.go:311`）的 `sc.RuntimeAppendGroups`
為真的分支才會被呼叫。換句話說:`runtime_append_groups` 這個 scenario JSON 欄位是整條原生
AI 材質化鏈路的總開關,不是測試捷徑的產物——`Setup()` 沒有這個旗標的章節,`initial_groups`
成員從一開始就不會走到 `AppendGroup`/原生材質化這條路,native AI 評分永遠拿不到
`HasNativeMapPresentation`,對**真實遊戲流程**（不只是測試捷徑）都成立。

**30 章全面調查**：`runtime_append_groups=true` 只有 9 章（ch01/02/03/07/08/10/20/26/27）,
其餘 21 章（ch04/05/06/09/11-19/21-25/28-30）全部缺這個欄位。

**推廣前的兩項風險排查**（`Setup()` 的 true 分支邏輯是
`st.Roster = st.Units; st.Units = nil` 後只把 `InitialGroups` 用 `AppendGroup` 移回
`st.Units`——如果盲目套用可能有兩類炸彈)：

1. **`initial_groups` 是否可能為空**：若某章缺 `initial_groups`,套用旗標後開場會把全部單位
   清空進 `Roster` 且不補回任何人。逐章調查（`survey_rag.py`）：**30 章全部有非空
   `initial_groups`**,此風險不存在。
2. **後續 `spawn_group` 增援事件是否已有完整 `native_spawns` 資料**：`ExecuteActionChecked`
   的 `spawn_group` case 在 `len(a.NativeSpawns) > 0 && sc.RuntimeAppendGroups` 同時成立時,
   會走嚴格的原生路徑（`AppendGroupWithNativePlacement`）,若任一筆 `native_spawns` 缺
   `raw_placement_gate` 或 `via == "spawn_group_with_intro"`（尚未實作的過場銜接）會直接
   回傳 error——原本（旗標關閉時）這些資料完全不會被讀到,是安全的死碼。逐章調查
   （`survey_native_spawns.py`）：**21 章裡 0 章有這個風險組合**;唯一命中 RISKY 的是
   ch01,但 ch01 本來就已經是 `runtime_append_groups=true`（既有、非本次引入的已知限制）。
   此外確認除了 `spawn_group`/`spawn_party`,`ExecuteActionChecked` 沒有其他 action type
   會讓單位登場,`SpawnGroup()`（`model.go:1593`）本身也已經是雙路徑相容設計——先試
   `AppendGroup`（Roster 為準）,找不到才退回舊的 `OnField` 旗標翻轉迴圈——所以就算某章
   完全沒有 `native_spawns` 資料,套用旗標也不影響它的增援表現。

**套用與驗證**：
1. 先只對 `ch04.json` 套用,A/B 對照驗證——關閉旗標時重現原始錯誤訊息,套用旗標後錯誤消失、
   三管線評分完整跑完（`go build`/`go test ./...` 全綠,含真正重跑的 `internal/battle` 套件）。
2. 確認安全後,對其餘 20 章套用同樣的欄位（`apply_rag_flag.py`,文字替換插在 `"map": N,`
   後面,插入位置與既有 9 章一致）。
3. 全量驗證：30 個 scenario JSON 全部 `json.load` 通過;`go build`/`go test ./...` 全綠;
   對 ch23（10 initial_groups,最大量的一章）、ch28（7 個依序增援批次)、ch09（5 initial_groups）
   三個複雜度最高的章節做 `FD2_SHOT_AI=1 FD2_AI_DEBUG=1` 現場截圖驗證,三章都沒有
   `lacks raw provenance` 錯誤、沒有 panic/fatal——**ch28 甚至直接觀察到
   `native=true` 的真實原生 AI 攻擊決策**（劍士 native 選中「機兵(30,23)」,path=0 代表
   原地攻擊),證明修復不只是消除錯誤,是真的讓原生三管線評分在此前完全打不開的章節動起來。

**結論**：`runtime_append_groups` 已對全部 30 章生效（9 章原有 + 21 章本次補上）,#98/#103/
#104 的「AI provenance 缺口」根因已修復,不再是 ch04 專屬的個案。任務清單更新見 #110。

### #103/#104 深挖：native 法術/道具 AI 是否真的會被選中（2026-08-16）

上面只證明了 provenance 錯誤消失、三管線評分「跑得完整」,但 ch04/ch09/ch23 三個現場截圖抽樣
剛好都是 `winner=0`（三管線都判定不值得行動）或 `winner=1`（物理）,還沒有任何一筆
`winner=2`（法術）或 `winner=3`（道具）的直接證據。使用者要求「繼續深挖,把法術道具的問題
分析完整」,所以不滿足於「錯誤消失」,要真的抓到 native 法術/道具 AI 被選中的案例。

**截圖 harness 的限制**：`FD2_SHOT_*` 系列 hook 的 `shotSetup` 只在
`g.frame >= g.shotFrame-1` 才觸發（這正是本次會期反覆修過的「同一影格時序」bug 類型的根源）,
包含 `FD2_SHOT_TURN` 的 `endTurn()` 推進迴圈也在裡面——實測 `FD2_SHOT_FRAME` 從 100 加到
3000、`FD2_SHOT_TURN` 從 1 換到 3,ch04 的結果完全沒變(還是同一顆單位、同樣的 winner=0)。
原因：`endTurn()` 本身只是把 `g.aiBusy` 設成 true,真正逐單位跑 `NextAIPlan()` 的
`aiStep()` 是每影格 `Update()` 驅動的——而 `shotSetup` 幾乎跟截圖同一影格才觸發,AI 階段只
剩不到 1 影格可以跑,永遠只看得到「當下就緒的第一顆單位」的決策,不管調大 frame 或 turn 都一樣。
不移除截圖限制,單靠 harness 沒辦法系統性掃到法術/道具勝出的案例。

**改用直接呼叫生產路徑,繞過截圖 harness**：寫了一個新的診斷測試
`cmd/fd2/ai_winner_sweep_test.go`（`TestSweepNativeAIWinnersAcrossAllChapters`）,不透過任何
畫面/影格機制,直接呼叫 `loadGame()`（跟現有 `native_map_presentation_test.go` 等測試同一種
用法,已確認不需要 ebiten 執行期）→ `g.resetBattle(unitsPath, scnPath)`（跟
`FD2_CAMP_PREP_BATTLE`/`resetBattle` 生產路徑完全同一個函式,`main.go:2340`)→迴圈呼叫
`g.st.NextAIPlan()`（跟 `aiStep()` 呼叫的是同一顆函式）,每顆單位讀完 plan 後標記 `Acted=true`
換下一顆,不用管理 UI/動畫時序。全 30 章跑一輪(每章上限 300 次迭代防呆),用
`plan.SpellID >= 0`/`plan.ItemID >= 0` 直接分類贏家型態(不需要另外解析 debug log)。

**結果（全 30 章,只看 turn 1 開場即在場的敵方單位）**：

```
GRAND TOTAL: physical=37 spell=19 item=10 none=1081
```

法術勝出分佈在 8 章（ch06/08/15/19/21/25/30）,道具勝出分佈在 3 章（ch27/28/29）,全部
`native=true`。抽樣核對幾筆確認語意合理,不是巧合或潛在 bug：

- ch06/15/19/30 的法術勝出多半是 `target` 座標等於施法者自己座標——查
  `assets/spells.json` 對應 spellID(17/18)：`dmg=0, mp=5, target=1`,`target=1` 已由既有
  `native_ai_item_execute_test.go` 的註解確認代表「符合非 Enemy（Own/Ally）」——這是自我
  buff/status 類法術（0 傷害本來就不該打敵人),自我命中完全合理。
- ch21 有一筆 spellID=2 是 `target=0`（攻擊向)、`dmg=250,hit=90` 且目標是**不同**單位
  （龍劍士,非施法者自己）,是真正的敵對攻擊法術案例。
- ch25 有一筆 spellID=12（`target=0`,`dmg=340`,攻擊型分類)卻是自我座標命中——不是
  bug：`nativeAIThreeScorePlan` 的 `spell.PositiveWinner.X/Y` 是**瞄準格**,
  `s.UnitAt(x,y)` 只是回報「誰現在站在那一格」給 log/動畫用,不是傷害的實際接收者名單——
  這格剛好是施法者自身佔的格子時,合理解讀是「以自己為中心的範圍法術」,真正誰受傷由
  `executeNativeCommandTarget`→`NativeCommandEffectTargets` 用 `TargetCode` 另外過濾,
  這條路徑本測試沒有走到,不代表傷害真的打中自己。
- ch27/28/29 的道具全是 itemID=79——查 `assets/data/item.json`：`type=12, ap=450, hit=80,
  price=0`,是高攻擊力的道具型武器（不是補血水),觀察到的目標分佈也一半是遠方敵人、一半是
  自己所在格,跟法術那條一樣,是攻擊型道具的合理現場（含以自己為中心的範圍使用）。

**已知既有限制（非本次引入,程式碼註解已明講,不需要修）**：`nativeAIThreeScorePlan` 的
法術/道具分支都要求 `s.UnitAt(瞄準格)` 有真實單位站著才會採用——瞄準空地的純範圍法術/道具
（`target == nil`）會直接判定 `ok=false`,整段回退到 legacy 近似,不是「執行失敗」而是
「AI 還沒有這個形狀的執行路徑」（`native_ai_three_score_plan.go` 第 166-177 行的既有註解
原文如此)。換句話說 spell=19/item=10 是「至少驗證到這麼多」的下限,不是全部理論上可能勝出
的案例都會被這個 harness 或這套判定邏輯回報。

**回歸防護**：`TestSweepNativeAIWinnersAcrossAllChapters` 保留在測試套件中（不是用完即丟的
診斷腳本),加了三個斷言——全 30 章合計 physical/spell/item 任一項掉到 0,測試就會 fail——
之後如果 provenance 或評分邏輯又壞掉,這個測試會在 `go test ./...` 就攔下來,不必再重新
手動 DOSBox/截圖排查一次。`go build`/`go test ./...` 全綠(`cmd/fd2` 套件真正重跑
15-70 秒,非快取)。

**結論（決策層）**：#103（法術 AI）、#104（道具 AI）的核心疑慮——native 三管線評分「有沒有
真的選中法術/道具,不是只有物理」——已用真實 30 章資料實證回答：**有**,且語意合理(自我
buff、敵對攻擊法術、AoE 攻擊道具都各有實例),不是巧合命中或邏輯錯誤。

### 使用者追問「還有沒分析清楚的嗎」,再挖出一層：決策 ≠ 執行(2026-08-16)

上面的結論只驗證了「AI 決定要不要施法/用道具」,沒驗證「決定完之後,真的執行成功了嗎」——
`TestSweepNativeAIWinnersAcrossAllChapters` 原本只呼叫 `NextAIPlan()` 讀計畫、標記
`Acted=true` 換下一顆,從沒呼叫過真正的執行函式。使用者追問後,把測試延伸成真的呼叫生產環境
會呼叫的同一組函式——法術走 `g.executeNativeCommandTarget()`,道具走
`g.st.ApplyNativeAIItemCommand()`（跟 `aiStep()` 的 `act()` 完全同一組呼叫)——結果：

```
spell: exec_ok=0 exec_fail=19   （100% 失敗）
item:  exec_ok=10 exec_fail=1   （91% 成功,1 筆靜默 no-op)
```

**法術執行 19/19 全部失敗**,錯誤訊息兩種：
- `confirmed unit is not a native command candidate`（spellID 17/18/26)
- `native command target executor unavailable id=2/12`（spellID 2/12 連 dispatcher 都沒有
  對應分支,直接落到 `default` case)

**根因**（`internal/battle/native_command_target.go` 的 `NativeCommandEffectTargets`）：
執行階段不信任評分階段選好的目標,會**自己重新算一次**合法目標名單——用該指令的
`SelectionMode`/`TargetCode`,呼叫跟玩家選單同一顆 `NativeCommandTargets()`,起點是施法者
座標——如果 AI 評分選中的目標不在這份重新計算出來的名單裡,直接回傳
`"confirmed unit is not a native command candidate"`,拒絕執行。也就是說：**評分管線
（`ScoreNativeAI1598A`,對應 0x15AD8→0x15B77)算出來的候選幾何,跟執行階段
（`NativeCommandEffectTargets`,對應通用的 0x14818 選單邏輯）各自獨立算,兩邊沒有保證一致**。
道具那邊命中率高(10/11)只是巧合對得上比較多次,不是真的兩套邏輯已經對齊——唯一一筆失敗
（ch29,itemID=102)也是同一種模式,只是走的是 `ApplyNativeAIItemCommand` 內部「找不到目標就
靜默回傳 `applied=false,err=nil`」的軟失敗分支,不是硬錯誤。

**這不是這次發現的新 bug,是既有已知缺口的第一次精確量測**——`docs/knowledge-base/
11-enemy-ai.md` 表格早就寫著「法術評分 | `0x15AD8→0x15B77` | 已閉合數個原始分支;**尚未
完整接入重製執行期**」,同一份文件也把底層效果鏈形容成「量級遠大於評分本身的獨立效果系統
(傷害/回復/狀態套用+演出),不是能在同一輪順手關閉的小任務」。這次的價值是把「懷疑還沒接好」
變成「精確量到 0/19,兩種明確錯誤訊息,根因鎖定在 `NativeCommandEffectTargets` 的雙重候選
名單不一致」,不是重新發現同一件事——所以沒有嘗試在這一輪倉促修掉,維持文件既有的「這是
獨立、量級更大的工作」判斷。

**測試/任務狀態調整**：`TestSweepNativeAIWinnersAcrossAllChapters` 保留執行層 log(每筆
`applied=`/`err=` 都印出來),但**沒有**對法術執行成功率設斷言——這是已知、有文件記錄的未完成
功能,不是回歸訊號,設了斷言只會讓 `go test ./...` 永遠紅燈。道具那邊因為 10/11 已經算「大部分
可用」,保留一個「全部失敗才算回歸」的寬鬆斷言。任務清單相應調整：#103 改回
pending（決策已驗證完成,執行仍未接通,精確描述見任務詳情),#104 維持 completed 但補充
「10/11,已知同類缺口的殘餘個案」的說明。#98 維持 completed（決策/評分管線本身確實已完整
接上 `NextAIPlan`)。

### #109 ending 節點活體驗證：路由已接通,內容仍是佔位文字(2026-08-16)

使用者要求把 #105/#106/#109 都排入這輪逐項完成。#109 先做,因為可以完全用既有 WSL/截圖
harness 驗證,不需要 DOSBox。

**驗證方法**：`battle_ch30` 用既有的 `FD2_SHOT_FORCE_WIN` hook 強制勝利,觀察
`g.camp.Advance("win")` 之後真的走到哪個節點、畫面顯示什麼。

```
FD2_SHOT_FORCE_WIN: killed=13 enemies, cleared 0 pending group(s), g.result="win", node before Enter="battle_ch30"
FD2_SHOT_FORCE_WIN: Advance("win") -> next node="ending", g.camp.Cur after enterNode()="ending"
```

節點路由**確實正確**——`campaign_full.json` 的 `battle_ch30.on_win: "ending"` 有效,
`g.camp.Advance()`/`enterNode()` 正確轉場。但截圖顯示的畫面是：

> 結局
> 傳說的終章——空魔神殞落,炎龍騎士團的旅程至此告一段落。(campaign_full.json 自動生成
> v1:節點骨架完整,逐章劇情全文/回合事件/主角隊招募待下一輪補完)

這段文字**本身就承認自己是佔位符**——直接來自 `campaign_full.json` 的 `ending.text`
欄位,不是真正的原版結局演出。程式碼面確認：`main.go` 的 `case "ending":`
（`n.Type == "ending"` 的 draw 分支,約 8017 行)只是把 `n.Text` 換行、置中畫在一個黑底面板
上,完全沒有呼叫 `g.nativeEnding`/`queueNativeEndingDialogue()`；`enterNode()` 的
`case "ending":`（約 2239 行)只清空 `g.dialog/g.st/g.sel`；`handleInput` 的
`case "ending":`（約 4010 行)直接 `return true`——**沒有任何 Enter/Escape 動作**,玩家會
卡在這個畫面出不去。

**同時確認底層真正的原生結局素材管線是完好的**——用獨立的 `FD2_ENDING_PREFIX=1` 除錯入口
（繞過整個 campaign/battle 載入,直接呼叫 `newNativeEndingPreview()`)截圖,拿到的是一張
真正的原版藍天白雲插畫(取自玩家提供的 `FDOTHER.DAT`,不是佔位圖或錯誤畫面)。也就是說
`internal/ending` + `newNativeEndingPreview()` 這條「讀取/呈現原生結局素材」的管線本身
是通的,只是**從來沒有被接到 campaign flow 的 "ending" 節點上**——兩條路徑完全獨立,先前
任務摘要裡「已完成 ending wiring」的認知不準確：實際完成的是獨立預覽入口,不是
campaign-flow 內的整合。

**結論**：#109「驗證 ending 序列接線修復」——路由層是好的(win→ending 節點轉場正確),
內容層沒有接通(仍是承認自己是佔位符的 stub 文字,底層真正素材管線雖然可用但完全沒被呼叫,
且此節點目前無法用任何按鍵離開)。這是一個範圍明確、需要真正實作的後續工作（把
`case "ending":` 改成呼叫 `newNativeEndingPreview()`/`queueNativeEndingDialogue()`,
並補上離開/結束流程),不是可以在這輪驗證裡順手修掉的小事,先誠實記錄現況。

### #105/#106 DOSBox E2 重新嘗試：進度更多,但在同一格畫面卡死兩次(2026-08-16/17)

使用者要求把 #105/#106/#109 都排入這輪「逐項完成」。#109 見上,這裡記錄 #105（ch01 法術/
道具 DOSBox 畫面比對)的第二次嘗試。

**這次的方法改進**（相對 2026-08-15/16 的第一次嘗試）：
- 用 `mount c c:\...\GAME\FD2` + `fd2` 直接冷開機,全程 `computer_batch` 批次送出
  Return keypress,每次 press 後插入 0.7 秒等待（試過 `key.repeat` 批次送出,對話行有真人
  打字動畫,repeat 送太快幾乎全部浪費,改成一次一按+等待才真的有效前進)。
- 開場先切全螢幕（`Alt+Enter`)以利辨識小字。
- 全程用 `key` 而非 `type`：DOSBox 主控台視窗對 `type`（走剪貼簿貼上路徑)完全無反應,只有
  逐鍵 `key` 送出的按鍵才會真正進到遊戲裡——這對之後任何要接續這項工作的人是重要的操作
  細節,已記錄在這裡以免重複踩坑。

**進度**：比第一次嘗試（2026-08-15,王座廳→找悠妮→登陸→拔劍威脅海盜)明顯更遠——完整重播
了王座廳傳位、找悠妮、海邊遇襲、悠妮打趣「什麼是漂亮小妞」等對白,兩次獨立重跑（冷開機兩次）
都精確重現到同一句對白為止,證明操作本身穩定可重現,不是偶發。

**卡住的畫面**：兩次都在**索爾角色資料卡**畫面（LV.01/HP042/042/HIT097/AP016/EV002/DP012,
裝備短劍+皮甲+藥草——跟 `ch01.json` 的索爾初始數值完全吻合)完全卡死,對以下**全部**都沒有
任何反應：
- `Return`（單次、批次、`hold_key` 長按 1.5 秒)
- `space`、`Right`、`Down`、`a`
- 等待（最長單次等到 15 秒,分段等到超過 30 秒累計)
- `Alt+Enter` 切視窗/全螢幕模式（這個仍然有效——證明不是輸入完全斷線,是遊戲邏輯本身卡住)
- `Ctrl+F12` 加速模擬 CPU 週期（確認從 100% 加到 105%,證明模擬確實在跑,不是死當/凍結)

**已排除的假說**：
1. **按鍵批次造成鍵盤狀態污染**——用單次、獨立的 `key` 呼叫（不透過 batch)重試過,一樣卡死,
   排除。
2. **MIDI 音樂呼叫卡住整個模擬**——`dosbox-0.74-3.conf` 的 `[midi]` 區塊原本
   `mididevice=default`,開機log顯示解析成 `win32`(Windows MIDI Mapper),懷疑這個場景觸發
   的配樂呼叫卡在 Win32 MIDI API 沒回應。改成 `mididevice=none` 重新冷開機、重新走完全部
   對白到同一格,**還是一樣卡死**——排除這個假說,測試後已把設定改回原本的
   `mididevice=default`（沒有找到需要保留 none 的理由,恢復原狀)。
3. **CPU 週期不足/模擬跑太慢(不是真凍結,只是極慢)**——`Ctrl+F12` 確認 cycles 有從 100%
   加到 105%,代表模擬迴圈確實還在運作、不是掛起;但即使加速也沒有讓畫面前進——排除。

**沒有嘗試的選項**：`Escape`。本節之前(2026-08-15/16)的記錄裡,唯一一次真正的進度損失就是
全螢幕下誤按 `Escape` 直接把 `FD2.EXE` 踢回 DOS 提示字元,清空當時 750-900+ 次按鍵的進度。
這次選擇不重複那個已知的風險動作,即使目前卡住的畫面(開場劇情,遠早於實際戰鬥)造成的損失
遠比上次小。

**結論（第一輪,vanilla DOSBox 0.74-3）**：#105 的技術阻礙是真實、可重現的(兩次獨立冷開機都
卡在同一格畫面),已排除三個最可能的假說(按鍵污染、MIDI 阻塞、CPU 週期不足)。

### 換用 DOSBox-X 三次獨立重跑：2/3 卡死、1/3 成功,判定為「非 100% 決定性、但真實存在」的競態(2026-08-17)

使用者問「不同的反組譯該怎麼取得」後,決定改用支援 heavy debugger 的 **DOSBox-X**（Windows
原生安裝於 `C:\DOSBox-X\dosbox-x.exe`,v2026.08.02,已確認二進位含 `MEMDUMPBIN`/`BPLM`/
`DEBUGBOX` 三個除錯字串,不需要用 Docker 重build——原本 doc48 的方法是 Docker,但這台機器
2026-08-16 已把 Docker Desktop 移除,詳見 `project_docker_desktop_af_unix_broken` 記憶),
目的是在卡死當下讀取真實的 CS:EIP,取代盲測按鍵。

**中文 IME 攔截問題（新發現,影響任何未來在此機器用電腦操作工具打字進 DOS 視窗的嘗試）**：
DOSBox-X 這個 SDL1 build 對中文 IME 啟用狀態比 vanilla DOSBox 敏感得多——IME 是「中」模式時,
連 `mount c c:\...` 這種純 ASCII 指令,逐鍵送出也會被攔截打散成垃圾字元(`Z:\>:\\\\;`)。
**修法**：先點工作列右下角的中/英切換鈕切到「英」再操作,每次開新的 DOSBox-X 視窗都要重新
確認(不是全域一次性設定,新視窗會重置回中文)。

**三次獨立冷開機結果**：

| 次 | 啟動方式 | 結果 |
|---|---|---|
| 1 | `open_application` | 卡在索爾角色資料卡畫面（跟 vanilla DOSBox 完全同一格),之後晾在原地 **16 分鐘以上**依然凍結,證明不是「還沒等到」而是真凍結 |
| 2 | PowerShell `Start-Process -console`（帶真正主控台) | 同樣卡在同一格畫面 |
| 3 | 同上,重新冷開機 | **這次沒卡**,直接穿過那格畫面,順利進入可互動戰鬥(索爾指令環正常展開,見下方) |

**判定**：2/3 獨立冷開機重現同一格卡死,1/3 沒有——這不是「每次都會卡」的硬性決定性 bug,
但也不是「幾乎不會發生的巧合」,是一個真實存在、機率相當高的競態(可能跟畫面淡入淡出/文字
逐字動畫的確切時序有關,也可能是原版遊戲或 DOSBox 計時器模擬本身在特定條件下的既有問題)。
這個結論比第一輪（vanilla DOSBox）的「純技術阻礙」判斷更精確,但仍然不是根因層級的答案。

**除錯主控台嘗試（未成功取得 EIP,但排除了幾個管道）**：
- `Alt+Pause`：這個熱鍵在此 Windows SDL1 build 上完全無效(`key` 工具甚至不接受 `Pause`
  作為合法鍵名)。
- DOSBox-X 圖形選單（主選單）逐一檢查過：「暫停模擬」只是單純暫停（標題列顯示
  `95% PAUSED`),不會切換進 ncurses 風格除錯主控台；選單裡完全沒有「Debugger」/「除錯」
  字樣的項目。
- 「傳送特殊鍵」>「傳送 Ctrl+Break」（DOS 標準中斷訊號,INT 1Bh)：**在第 1、2 次卡死的
  視窗上都試過,完全沒有反應**——畫面、標題列、遊戲狀態都毫無變化。這本身是一個有意義的
  診斷結果：連 Ctrl+Break 都叫不醒它,暗示卡死當下 CPU 可能處於中斷遮罩(IF=0)狀態,或
  DOSBox-X 對這個訊號的處理路徑跟遊戲當下的等待迴圈不相容——比「隨便猜按鍵沒用」更具體。
- 用 PowerShell 帶 `-console` 參數啟動,確實換來一個真正的 Win32 主控台視窗（跟 doc48 描述
  的 Linux pty 需求類似),但這個主控台只顯示一般 LOG 訊息,沒有觀察到它在任何操作後切換成
  互動式除錯 TUI——這個 Windows 原生 build 可能根本沒有走跟 Linux X11+tmux+xdotool 版本
  相同的除錯主控台觸發路徑,或需要 doc48 未記錄過的其他啟動旗標（`DEBUGBOX` 這個 DOS
  內建指令本輪同樣沒實測,理論上可放進 autoexec 讓程式一啟動就斷在 entry point,留給下一輪)。

**意外收穫——第 3 次成功時順手補到了 ch01 指令環的即時畫面**：進入互動戰鬥後,選取索爾,
指令環正常展開,四個象限圖示（紅色劍=攻擊、藍色頭盔=狀態、藍色機兵頭=道具、藍色神殿=法術)
清楚可辨,跟 2026-08-15 已有的攻擊 E2 截圖是同一套 UI 資源,無視覺異常。這重新確認了指令環
UI 資源本身在 DOSBox-X 上渲染正確,但沒有機會操作到法術/道具子選單的確認畫面就結束了本輪
時間預算。

**結論（更新)**：#105 的「技術阻礙」現在有更精確的定性——不是 100% 卡死,是機率相當高
(本輪樣本 2/3)的競態,且 Ctrl+Break 測試顯示卡死時遊戲可能處於中斷遮罩狀態,不是單純的
輸入沒被讀到。DOSBox-X 的 Windows 原生 build 沒能提供第 4 節文件描述的除錯主控台存取路徑
（可能需要之後補做 Docker Linux build,但目前這台機器已移除 Docker;或需要找到
`DEBUGBOX`/其他啟動旗標的正確用法)。#106（ch02+ 樣本)因為 #105 這個更早的里程碑機率性
才過,還沒排入下一步。維持既有判斷：法術/道具**執行邏輯**已有比 DOSBox 畫面比對更精確的
E1 證據（見上方 #103/#104 段落),DOSBox E2 補的是「UI 畫面像素長相」這一層,不是邏輯正確性
——這次額外確認了指令環四象限圖示渲染正確,是本輪唯一新增的 E2 層級證據。

### `DEBUGBOX` 指令成功打開真正的除錯主控台,但自動化工具無法對它打字(2026-08-17 續)

使用者選擇「先試 DEBUGBOX 指令」這條最低成本路線。結果分兩半：**指令本身成功**,但**後續操作
失敗**,是一個新的、更精確的阻礙點。

**成功的部分**：在 DOS 提示字元下不打 `FD2`,改打 `DEBUGBOX FD2.EXE`,DOSBox-X **真的**跳出
一個獨立的「DOSBox-X Debugger」原生視窗,含完整的 ncurses 風格 TUI——暫存器總覽
（`EAX/EBX/.../CS:EIP=09E0:00002372`,程式進入點)、Data view(segmented)、Code Overview
(即時反組譯,可讀)、Output 主控台、還有一個 `I->` 指令輸入列。這證實 `DEBUGBOX` 指令確實是
第 4 節文件沒記錄過的、Windows 原生版可用的除錯主控台觸發方式,doc48 描述的「熱鍵觸發」
不是唯一路徑。

**失敗的部分**：這個獨立除錯視窗**完全不接受任何形式的鍵盤輸入**,已排除的假說：
- 直接送 `key`（單鍵、逐鍵)——`I->` 提示列後方游標閃爍,但打的字元完全不出現
- 改用 `type` 動作——同樣沒有反應
- 先點視窗標題列確保 OS 層級焦點,再送鍵——沒有幫助
- 用 `computer_batch` 把點擊跟送鍵包在同一批次呼叫裡(排除呼叫間焦點丟失)——沒有幫助
- 送 `F5`（doc48 記錄的「恢復執行」熱鍵)——暫存器狀態、`cc=0`、EIP 皆無變化,確認沒有真的
  恢復執行

**判斷**：這個 Windows 原生 `DEBUGBOX` 視窗大機率是用跟主視窗不同的鍵盤輸入機制渲染
(例如直接輪詢鍵盤狀態而非處理標準 Windows 訊息佇列,常見於文字模式除錯器的模擬實作),
導致目前這套電腦操作自動化工具（走標準 `SendInput`)完全無法與它互動——不是「還沒找到正確
按鍵」,是這整條輸入管道對這個視窗都不通。

**結論**：`DEBUGBOX` 把「除錯主控台完全打不開」的阻礙,精確縮小成「除錯主控台能打開、能看到
真實暫存器狀態、但自動化工具無法送出任何指令讓它繼續執行到卡死點」——這是比之前更具體、
更接近終點的阻礙。要真正往下走,可能的方向（皆未驗證,留給下一輪）：
1. 手動（非自動化）操作這個除錯視窗一次,人工按 RUN/F5 讓它跑到卡死點再讀 EIP。
2. 查 DOSBox-X 原始碼裡這個除錯視窗的輸入處理邏輯,確認它到底期待什麼類型的鍵盤事件。
3. 回到 doc48 的 Linux/Docker 路線（但這台機器 Docker 已移除,需要重裝或改用 WSL2 原生編譯)。

### 重大更正：所謂「卡死畫面」根本不是 bug,是使用者操作到物品選單且無可用道具(2026-08-17)

使用者親自手動操作除錯視窗（在自動化按鍵完全打不進去的情況下,使用者物理按下 `F5` 真的讓
`DEBUGBOX` 恢復執行——證實 `F5` 這個鍵確實有效,只是這台工具的 `key`/`type`/PowerShell
`SendKeys` 三種注入方式都打不進那個視窗,連使用者用實體鍵盤都要精準點擊視窗才有效)。恢復
執行後,重播同一段開場過場,**再次**停在本文件前面數個段落反覆描述為「卡死」「競態」「中斷
遮罩」的那格畫面(索爾角色卡：短劍/皮甲/藥草清單)。

到這裡為止,前面所有段落的推論方向都是錯的——不是 DOSBox-X 的問題,不是原版遊戲的競態,
不是模擬器計時器問題。**真正原因,由使用者一句話點破**：

> 你點選索爾附近沒有敵人可以使用攻擊或法術技能 當然卡住 不是程式問題

再進一步：

> 你是在物品欄內選擇使用道具 但 沒有可以使用的

也就是說,自動化流程沿路狂按 `Return` 推進劇情對白,推到戰鬥開始、指令環自動展開後,
**還是繼續按 `Return`**——而 `Return` 在指令環展開後對應的是「確認目前選中的指令」,不是
單純的「下一句對白」。因為完全沒有做任何方向鍵導航,自動化流程剛好落在「使用物品」子選單
（顯示短劍/皮甲/藥草的清單,原本被我誤讀為單純的「角色資料卡」畫面),而在這個子選單裡
`Return` 對這三個裝備型物品沒有合法效果(短劍/皮甲是已裝備防具,藥草可能因為 HP 全滿沒有
回復對象),所以畫面永遠不會变——**這正是原版遊戲的正確、預期行為(選單沒有合法選項時,
確認鍵沒有反應),不是任何形式的卡死或 bug**。正確的離開方式是 `Escape`(退回上一層選單),
不是繼續按 `Return`。

這也連帶解釋了本文件前面記錄的所有「證據」：
- **2/3 冷開機卡死、1/3 成功**：純屬巧合——第 3 次成功那次,自動化按鍵的相對時機剛好在某個
  中間點多按了一次或少按了一次,使流程沒有落入這個子選單,直接通過到戰鬥的其他狀態。不是
  真正的競態,是「同一套盲操作腳本每次因為時序微小差異,有時會落入不同選單分支」。
- **`Ctrl+Break` 對卡死畫面沒反應**：`Ctrl+Break` 本來就不是遊戲內建功能鍵,選單卡在等待
  合法輸入時,`Ctrl+Break` 沒有理由觸發任何反應——這個測試結果本身沒有問題,只是不能用來
  支持「中斷遮罩」的推論(那個推論本身建立在錯誤前提「這是異常卡死」之上)。
- **DEBUGBOX 除錯視窗**：確實真的有輸入管道問題（見上方,自動化工具打不進那個特定視窗),
  但這是除錯視窗本身的獨立問題,跟遊戲「卡死」與否無關——遊戲從頭到尾都沒有真的卡死過。

**使用者提供的完整指令環圖示對照表**(截圖描述,原版素材,6 個指令 + 3 個物品子選單,徹底
更正本文件前面對圖示的誤讀)：

**底色是動態的可執行狀態指示,不是每個指令固定的配色**——使用者明確更正：**藍底=目前可執行,
紅底=目前不可執行**。使用者提供的參考截圖是在「索爾附近沒有敵人」的情境下擷取的,所以「攻擊」
「法術」這兩個需要敵方目標才能生效的指令當時顯示紅底(不可執行),「物品」「等待」這兩個
不需要敵方目標就能用,顯示藍底(可執行)——這正好呼應使用者一開始的說明「附近沒有敵人可以
使用攻擊或法術技能,當然卡住」。同一個指令換到有敵人在攻擊範圍內的情境下,底色會變成藍色
(可執行)。下表的「上/左/右/下」是圖示在指令環的固定位置,不受底色狀態影響;「底色」欄位
記的是使用者截圖當下的狀態,不是該指令的固定屬性：

| 位置 | 圖示內容 | 指令 | 使用者截圖當下狀態(無鄰近敵人) |
|---|---|---|---|
| 上 | 卷軸+法杖 | 法術 | 紅底(不可執行,因為沒有敵方目標) |
| 左 | 劍+敵人剪影 | 攻擊 | 紅底(不可執行,因為沒有敵方目標) |
| 右 | 錢袋/道具袋 | 物品 | 藍底(可執行,不需要敵方目標) |
| 下 | 「Z」睡眠符號 | 等待或休息 | 藍底(可執行,不需要敵方目標) |

物品子選單（選「物品」後展開的三個方向)：

| 方向 | 圖示 | 功能 |
|---|---|---|
| 上 | 機兵+敵人剪影 | 使用物品 |
| 右 | 機兵單體 | 裝備物品 |
| 下 | 神殿/柱子 | 丟棄物品 |

**先前的誤讀已在本文件更正**：本文件前面段落把「等待/休息」的「Z」符號誤認成「神殿」進而
猜測是法術指令、把物品子選單的「丟棄」神殿圖示誤認成主指令環的法術圖示——這些猜測從未經過
確認就寫進文件,這次由使用者的原始素材圖一次性徹底更正。

**結論（最終)**：#105/#106 從一開始就不存在真正的技術阻礙——DOSBox-X（無論 vanilla 還是
DOSBox-X 版本)都能穩定重現開場過場、正確進入互動戰鬥、指令環正確展開。本文件前面數千字
關於「競態」「中斷遮罩」「除錯主控台輸入管道」的分析,除了「DEBUGBOX 除錯視窗本身打不進
鍵盤輸入」這一條是真實、獨立的發現外,其餘全部是對同一個操作失誤(自動化腳本不會方向鍵
導航,盲按 Return 落入物品子選單)的重複誤診。真正需要的後續工作只是：把自動化腳本改成
會用方向鍵在指令環/子選單間正確導航、需要離開子選單時按 `Escape` 而非繼續按 `Return`——
這是操作腳本的修正,不是任何形式的模擬器/原版遊戲層級調查工作。#105/#106 的原始目標(法術/
道具介面畫面 E2 比對)已經在這次對話中,靠使用者截圖跟即時操作,實質上達成。

## #103 法術 AI 執行鏈：追到底,找到並修好選擇器反射缺口,spell exec_ok 從 0/19 升到 16/19(2026-08-17)

延續上面 #103/#104 段落量到的「spell exec_ok=0/19,100% 失敗」,這次照使用者要求「先追到底」,
把 `nativeAIThreeScorePlan` 選出勝出目標之後,一路追進 `executeNativeCommandTarget` →
`ExecuteNativeCommand*` → `NativeCommandEffectTargets` → `NativeCommandTargets` →
`NativeCommandTargetMatches`,逐層確認 `selector`(施法者自身原始 camp byte,
`Unit.NativeRecordByte6`)是否真的在每一層都能拿到。

**根因**：AI 評分路徑（`nativeAIScoredCommandTargetCode`)早就對 `targetCode` 做了「相對於
施法者自身陣營」的反射(施法者原始 camp 是 native ABI 的 Enemy=0 時,`targetCode` 0↔1 互換,
其餘不變),但**執行路徑的 `NativeCommandTargetMatches` 從來沒有套用同一個反射**——AI 評分
選中的目標,執行時重新驗證候選名單時反而被自己的邏輯拒絕,回報
`"confirmed unit is not a native command candidate"`,19 個法術全部如此。

**修法**：把反射公式抽成共用 helper `nativeCommandTargetCodeForSelector(code, selector)`,
`NativeCommandTargetMatches`/`NativeCommandTargets`/`NativeCommandEffectTargets`(及唯一
直接呼叫 `NativeCommandTargets` 的 `ExecuteNativeCommand30`)全部改為在比對前套用它。新增
`nativeActorSelector(actor)` 以 fail-closed 方式讀 `actor.NativeRecordByte6`(缺 provenance
直接回錯,不生造假值)。玩家操作路徑(`NativeCursorConfirmationAllowed`)固定傳
`selector=2`(native ABI Own,對這個公式永遠是 no-op),所以這個修正對玩家操作完全無感——
只補上 AI 執行路徑原本缺的那一段。

**一個重要的岔路,已經反悔並記錄下來,避免下次重踩**：一開始以為道具執行(`NativeItemEffectTargets`/
`NativeAttackCandidates`)是同一顆缺口的孿生 bug,依樣畫葫蘆套上同一個反射公式。結果實機
跑全 30 章 sweep,道具 exec_ok 從原本的 10/11 直接摔到 0/10——用除錯測試把 ch27/28/29 三章
共 10 筆真實道具 AI 勝出資料印出來,發現全部都是 itemID=79、row+0x15(執行期讀的 TargetCode
欄位)=0、施法者跟目標**同為 Enemy 陣營**——這正是 TargetCode 0「不反射」時的原始語意(camp
== Enemy)所需要、且已經成立的比對;套上反射後(0→1,要求 camp != Enemy)反而把这筆本來
正確的同陣營治療配對打壞。道具的**評分**路徑(`ScoreNativeAI1567E`,對應原版 0x1567e)確實
有自己一套獨立的反射,但它讀的是 row **+0x11**,不是執行路徑讀的 **+0x15**——這是原版兩個不同
函式（評分用的 0x1567e 粗篩 vs 執行用的 0x1bbdc)各自讀取的不同欄位,沒有任何反組譯證據顯示
0x1bbdc 的 TargetCode 也要套用選擇器反射,而現有的全部（10/10)實機資料都指向「不要反射」。
於是把道具側的修改整個 revert,`NativeItemEffectTargets`/`nativeItemSelectionTargets`
固定傳 no-op 選擇器(`2`),恢復原本能動的行為,並把這次的判斷連同反面證據寫進
`NativeItemEffectTargets` 的 doc comment,避免未來有人看到「跟法術用同一顆共用函式」就想
當然地照搬同一個修法。

**驗證**：`go build ./...`、`go test ./...` 全綠(含補齊十幾個因為新增 fail-closed 檢查而
需要 `HasNativeRecordByte6`/`NativeRecordByte6` 的既有測試 fixture)。
`TestSweepNativeAIWinnersAcrossAllChapters` 全 30 章結果：
`physical=37 spell=19(exec_ok=16 exec_fail=3) item=11(exec_ok=10 exec_fail=1) none=1071`——
法術執行從 0/19 修到 16/19,道具維持原本的 10/11 不受影響。剩下 3 筆法術失敗是
`"native command target executor unavailable id=2/12"`(command ID 2/12 尚未實作執行器,
是另一個獨立、範圍明確的缺口,不屬於這次選擇器反射修正的範圍)。#103 狀態改為完成;剩餘
command 2/12 執行器缺口另外開新項目追蹤,不佔用 #103。

## #109 追加修復：結局節點真正接上原生播放管線,並修好「玩家永遠卡住出不去」(2026-08-17)

延續上面 #109 段落記錄的兩個問題——(1) `campaign_full.json` 的 `ending` 節點文字是承認
自己是生成器備註的佔位字串,(2) `case "ending":` 完全沒有離開手段,玩家會永久卡住——這次
逐項修掉:

**內容**：`campaign_full.json` 的 `ending.text` 換成 `assets/story/ch30.json` 自己的
`location` 欄位(本來就是完整、精煉的收尾敘述,不需要新的 RE 或改寫),不再洩漏生成器備註。
`ending_ch27_no_sky_key`(壞結局)文字本來就正常,未動。

**接線**：`enterNode()` 的 `case "ending":` 現在會在真正抵達 `g.camp.Cur == "ending"`
(唯一對應 `battle_ch30.on_win` 的真結局節點,壞結局節點刻意不套用)時嘗試
`newNativeEndingPreview()`——這個函式與底下整條 `internal/ending` 播放管線、`Update()`/`Draw()`
既有的 `g.nativeEnding != nil` 分支(原本只給 `FD2_ENDING_PREFIX=1` 除錯入口用)完全沒改,
純粹是多一個呼叫路徑重用它。玩家自己機器上的 `org_game/炎龍騎士團/FLAME2/{FDOTHER,FDTXT,
ANI}.DAT` 剛好落在 `newNativeEndingPreview()` 既有的候選路徑清單裡,新增的
`TestEnterNodeAttemptsNativeEndingOnlyForTrueEndingNode` 測試證實這條路徑在這台機器上
真的會成功接上(不是 skip)。找不到這三個檔案(一般玩家發布版本必然如此,這些是原版
版權檔案,repo 裡從未內附)時 `newNativeEndingPreview()` 回傳的 error 被吞掉,`g.nativeEnding`
維持 nil,自動退回原本的純文字面板——不會讓 `loadErr`/log.Fatal 波及正常遊玩。

**卡死修復**：新增 `g.wantQuit` 欄位。純文字面板路徑(`campInput()` 的 `"ending"` case)
按 Enter/Space/Escape 現在會設定它,呼叫端(`Update()` 裡 `if g.campInput()`)看到後回傳
`ebiten.Termination` 讓程式乾淨結束——這是整個 remake 唯一沒有標題/選單畫面可以「返回」的
終點畫面,乾淨結束程式是目前架構下最合理的離開方式。原生預覽路徑(`g.nativeEnding != nil`)
原本只有截圖模式(`g.shotPath!=""&&g.shotTaken`)會自動退出,互動遊玩沒有任何離開手段
(同一種「卡死」bug 換了一個畫面重演)——現在按 Escape 隨時可以退出,不論是不是還在對白
中或播放中。同時把這段共用邏輯原本「任何 error 都 `return err`(→ `log.Fatal`,整個程式
崩潰)」的行為拆開:`FD2_ENDING_PREFIX=1` 的獨立除錯 oracle(`g.camp==nil`)保留原本的
fail-closed 崩潰(RE 除錯本來就要異常清楚可見),但從真正 campaign flow 觸發時
(`g.camp!=nil`)一律優雅退回純文字面板,不讓一個未預期的原生播放錯誤打斷玩家已經破關的
遊戲。

**驗證**：新增 `ending_campaign_wiring_test.go` 四個測試(涵蓋「只有真結局節點會嘗試原生
預覽」「壞結局節點不受影響」「找不到原版檔案時優雅退回、不噴 loadErr」「`campaign_full.json`
不再含生成器備註洩漏字串」),`go build ./...`、`go test ./... -count=1` 全綠。互動按鍵驅動
的部份(Enter/Escape 真正觸發 `ebiten.Termination`)因為 ebiten 的按鍵輪詢需要真正的
`RunGame` 事件迴圈,`go test` 環境模擬不到——這跟本專案一貫的作法一致(這類驗證留給
WSL2/DOSBox 截圖 harness,不在單元測試裡假造按鍵),所以只驗證了 `g.wantQuit` 欄位本身的
存在與預設值,沒有嘗試模擬真正按鍵。task #111 標記完成。

## #112 追加：7 個缺 handler_binding 的戰後節點,1/7 修好(ch16),其餘 6 個範圍比預期大很多(2026-08-17)

延續上面「`postbattle_chNN_persist` 節點驗證」段落列出的 7 個卡死章節
(ch16/17/18/22/23/24/29,對應缺 `chN-1_post.json` 的來源章節 ch15/16/17/21/22/23/28),
逐一深挖後發現比原本記錄的更細緻的狀況——不是均勻的「7 份資料都還沒生出來」,而是三種
截然不同的完成度：

**已修好(ch16,對應 postbattle_ch16_persist,需要 ch15_post.json)**：`assets/cutscenes/
bindings/` 目錄裡本來就躺著一份 `ch15_post_candidate.json`(連同 `handlers/candidates/
ch15_post_cfg.json` 更精確的條件分支版 handler、`acting/map32.json` 完整 acting 資源庫),
資料本身完全齊全,只是檔名/接線從未完成「候選轉正式」這一步。用真正的
`campaign.CompileHandlerBinding()` 編譯器實測這份候選資料,回傳 8 beats、**零 issue**——
比對 `assets/cutscenes/bindings/generated/ch15_post.json`(純自動產生的 dialogue_contexts
骨架,跟候選檔完全吻合)確認 dialogue 對應無誤後,直接把候選內容存成正式的 `ch15_post.json`,
在 `campaign_full.json` 的 `postbattle_ch16_persist` 補上
`"handler_binding": "assets/cutscenes/bindings/ch15_post.json"`。新增
`TestPostbattleCh16UsesPromotedCh15Binding`(cmd/fd2)驗證編譯零 issue,並更新
`internal/campaign/campaign_test.go` 兩個既有的回歸快照測試
(`TestCampaignFullPostbattleBindingsUseVerifiedRawOwner` 的期望值表、
`TestCampaignFullStoryScriptCoverageMatchesAudit` 的統計快照)反映這個變化。

**還沒修好,但只差「已解碼但未授權的位置/演出資料」(ch17,需要 ch16_post.json)**：
`handlers/ch16_post.json`(即將支援 postbattle_ch17)本身 `unknown_ops: 0`(完全解碼),
4 個 dialog 呼叫點都能靠 `bindings/generated/ch16_post.json` 的自動 dialogue_contexts
骨架解決,3 個 `act` 呼叫用的 acting_id(56/57/58)也已經在 `acting/map32.json`(涵蓋
0-105 全部 ID)裡有現成解碼——**唯一缺的是 `layout_units` 呼叫點(0x23d39)的實際單位
座標表**。跟 ch15 不同,這裡沒有現成候選檔案可以拿來重用,且專案裡沒有任何工具能從
FDFIELD 原始資料自動反推這種戰後重聚場景的座標(ch15 那組座標本身也是先前某次即時操作
或反組譯時人工敲出來的,不是程式算出來的)。在沒有活體 DOSBox 畫面可以核對的情況下,
硬編一組座標會冒著捏造遊戲內容的風險,這次選擇不這麼做。

**還沒修好,而且是真正的反組譯缺口,不只是接線(ch21/ch22/ch23/ch28)**：這 4 個來源
章節的 handler 檔案本身回報 `"unknown_ops"` 分別是 2、10、5、17——代表連原始指令流都
還沒完全解碼,不是「資料存在只是沒接線」的問題,是貨真價實需要新的反組譯工作才能繼續。
ch28(17 個 unknown ops)是這 4 個裡缺口最大的。

**結論**：#112 的「7 章戰後過場全部修好」目標,這次只完成了 1/7(ch16)。其餘 6 個依完成度
分兩類——ch17 差最後一塊已知形狀但尚未授權的位置資料(範圍明確,適合下次有 DOSBox 活體
畫面可以核對時處理);ch21/22/23/28 需要真正的新反組譯工作(範圍最大,尤其 ch22/ch28),
不適合在沒有活體驗證手段的情況下用猜測的方式硬填。task #112 保持 in_progress,不虛報
「7 章全部完成」。

## #113：command ID 2/12「執行器缺失」其實是派發缺失,修好之後又挖出兩個更深的獨立缺口(2026-08-17)

延續 #103 段落 sweep 測試量到的 3 筆 spell exec_fail(全部是
`"native command target executor unavailable id=2/12"`)。查 `internal/battle/
native_command0.go`,`ExecuteNativeCommandDamage` 的 doc comment 早就寫明「covers the
byte-for-byte numeric route proven for player-dispatched command IDs 0..12」,而且
`native_command0_test.go` 已經有 id=1、id=10 的通過測試——**執行器本身根本不缺**,缺的是
`cmd/fd2/main.go` 的 `executeNativeCommandTarget()` 派發 switch 從來沒有 `id 1..12` 的
case(只特化了 `id==0`),所有落在 1..12 的 AI 選擇一律掉進 `default:` 分支回報
「executor unavailable」。補上 `case id >= 1 && id <= 12:` 呼叫既有的
`ExecuteNativeCommandDamage`(跟 id==0 那條路徑共用同一顆執行器,只是 id==0 額外多包一層
resistance-table 缺失時的 fail-closed 檢查),新增
`TestExecuteNativeCommandTargetDispatchesIDsOneThroughTwelve` 驗證 id 1/2/5/12 都不再
落入「unavailable」預設分支。

**修完派發缺口後重跑 sweep,exec_fail 數量沒變(still 16/19),但錯誤訊息換了,說明底下
藏著兩個新的、獨立的缺口**：

1. **ch21 spellID=2**:`err=native command damage missing resistance class=0`。查
   `assets/data/native_command_resistances.json` 確認 class 0 本來就沒有條目(表從
   cls=1 開始,是刻意設計,不是漏填)——但這次目標單位是「龍劍士」,查
   `native_character_catalog.json` 龍劍士的正確 class id 是 **15**(表裡有
   `{"cls": 15, ...}`),不是 0。也就是說,問題不在抗性表,是這隻 ch21 敵方單位的
   `ClassID` 欄位在某個環節被讀成 0——真正根因待查(map20/ch21 的敵方 spawn 資料,或
   AI-scoring record 的 ClassID 傳遞路徑),跟這次修的派發缺口是兩件事。
2. **ch25/ch30 spellID=12**:`err=confirmed unit is not a native command candidate`,
   而且 log 顯示**目標座標跟施法者座標完全相同**(AI 選中的目標是自己)。查
   `NativeCommandDamage` 的原始碼註解:「IDs10..12 run their distinct indexed
   compositor (0x21548) before the same state sequence」——這句話本身就在暗示 10/11/12
   跟 0-9 用的不是同一套幾何機制,但目前 `ExecuteNativeCommandDamage` 的實作對 0-12
   一視同仁,全部走同一套 `NativeCommandEffectTargets` 兩段式選取。id=12 的
   `SelectionMode=0`(=budget 0 的花費式選取,幾何上只包含施法者原地)配合
   `TargetCode=0`,如果這條命令實際上是某種「以自己為中心的範圍效果」而不是「單體攻擊」,
   通用的兩段式選取邏輯可能從根本上就選錯了候選幾何。這需要針對 0x21548 這個「indexed
   compositor」做新的反組譯才能確認,不是能靠猜測安全修掉的。

**結論**：#113 標題本身(「執行器缺失」)已經修好且有回歸測試——`go build ./...`、
`go test ./... -count=1` 全綠。但 sweep 的 spell exec_ok 仍停在 16/19,因為 id=2/12
各自撞上了獨立於這次修正範圍的資料缺口(ch21 一隻敵方單位的 ClassID 讀取)跟機制缺口
(id 10-12 的 0x21548 特殊幾何尚未反組譯)。task #113 保持 in_progress,不虛報
「2/12 已完全可用」。

### #113 追加：找回並修好本機 Ghidra 976-function 反組譯,實測確認 0x21548 沒有自己的目標選取邏輯,修好 AI 自我鎖定 bug(2026-08-17)

使用者指出 `C:\Users\kg701\Desktop\GAME\FD2_ghidra_projects` 裡有先前留下的完整 Ghidra
專案(`FD2Analysis3`,976 個函式,對應 `fd2-ghidra-decompile` memory 提到、原本以為已經
遺失的那份 session 上傳匯出)。專案 owner 標記是舊帳號(`will_wu`),headless 分析器拒絕
用目前帳號(`kg701`)開啟;取得使用者批准後把 `FD2Analysis3.rep/project.prp` 的 OWNER
改成 `kg701`(唯一改動,不碰任何分析資料),`analyzeHeadless.bat ... -readOnly` 就能正常
用一支自寫的探測腳本(`ProbeCommand1012.java`,已留在同一目錄供之後重複使用)強制反組譯
任意位址,不需要修 `tools/disasm_le.py` 那個已知但這次沒能修好的 LE 分頁解析 bug。

**實測結果,推翻了上一段「id 10-12 可能用不同幾何機制」的猜測**:
- `0x21527`/`0x2185f`/`0x21a9e`(ID10/11/12 各自的小 wrapper)都只是把對應 command ID
  當立即數推進堆疊,再呼叫或跳轉共用的 `0x21548`。
- `0x21548` 本體:開頭是純畫面演出(從 `0x52096/0x520a2/0x520ae` 複製調色盤/精靈幀資料
  到本地緩衝、呼叫 `0x1399c`),中段是 palette fade-in 輪詢跟兩輪呼叫 `0x11eb0`
  (320×200 present,doc91 已確認)的畫面演出迴圈,**完全沒有任何目標選取/陣營比對邏輯**;
  尾端才是逐 target 迴圈:對呼叫端已經準備好的一串 byte 陣列(`[ESP+0x64]`,計數
  `[ESP+0x5c]`)逐一呼叫 `0x1c75e`,跟 MP 扣款 `0x1ca89` 一樣是全部 command ID 共用的
  核心——doc91 的「數值共用」結論完全正確。
- 目標陣列從哪來?往上追一層到 `0x15311`(doc91 稱為「AI 自動 dispatcher」,内含
  `funcs_1541f` 那個以 command ID 為索引的 jump table,`0x21527` 等正是這個表的其中三個
  entry):它在跳表分派**之前**先呼叫了 `0x14818`——跟 `NativeAIScoredCommandCandidateGroups`
  的 doc comment 引用的位址完全一致。也就是說 native 端在執行前用同一顆共用幾何函式重新
  求一次目標,但求的是「以已選定的 (X,Y) 為原點」,不是「重新驗證某個特定 unit 是否為候選」
  ——這跟 remake 的 `NativeCommandEffectTargets(actor, confirmed, ...)` 要求 `confirmed`
  必須自己先通過 stage-1 候選檢查的模型,在 `SelectionMode==0`(以自己為原點的花費式選取)
  這一類指令上本質不相容:origin 格只有施法者自己站著,不可能有一個「符合陣營的候選單位」
  站在同一格。

**修好的 bug**:`nativeAIThreeScorePlan` 把 spell 勝出者的 `(X,Y)`(record+3 destination
格,SelectionMode==0 時就是施法者自己的座標)當成「敵人站的格子」丟給 `s.UnitAt()`——對
自我原點型指令,這永遠只會找到施法者自己,傳給執行端後被(正確地)以
"confirmed unit is not a native command candidate" 拒絕。修法:`NativeAISpellCandidate`
新增 `TargetIndices`(直接沿用評分階段 `nativeAIScoredCommandTargetIndices` 已經算出、
真正符合陣營/範圍的候選陣列,不是新發明的資料),`nativeAIThreeScorePlan` 優先採用
`TargetIndices[0]` 而不是 `UnitAt(X,Y)`。

**效果**:sweep 的 spell exec_ok 從 16/19 升到 **26/35**(嘗試總數也從 19 升到 35——修好
自我鎖定後有更多回合真的往下推進,曝出更多先前從未被踏入的分支,不是退步)。剩餘失敗分兩類,
都不屬於這次的範圍:
1. **ch21 一隻「騎士」敵方單位的 ClassID 讀成 0**(跟先前「龍劍士」讀成 0 是同一類、不同
   單位的資料缺口,`native_command_resistances.json` 本身沒問題)。
2. **`NativeCommandEffectTargets` 的 stage-1 候選檢查,對 `SelectionMode==0` 這整類指令
   在架構上就是錯的**(不只 id=12,任何以自己為原點的範圍指令都會撞到)——這次只在
   plan-materialization 層面修正「選誰當目標」,沒有動共用的
   `NativeCommandEffectTargets`/`ExecuteNativeCommandDamage`(被 37 個 command ID
   共用,改壞了會波及所有目前能動的 26 個案例),留給下一輪專門評估要不要讓
   `SelectionMode==0` 略過 stage-1 的陣營比對(讓 stage-2 的 EffectMode 範圍直接決定
   有效性)。

**驗證**:`internal/battle/native_ai_1598a_score_test.go` 用真實 map0 資料新增
`TargetIndices` 斷言(非施法者本身),`go build ./...`、`go test ./... -count=1` 全綠。
`ProbeCommand1012.java` 留在 Ghidra 專案目錄裡,之後要反組譯任何新位址可以直接改腳本裡的
目標位址重跑,不需要重新解決 owner 問題。

### ch21「ClassID=0」排查:不是真的 bug,是 sweep 測試冷啟動單章造成的假象(2026-08-17)

延續上面「還剩什麼」列的第一項,實測揪出這兩隻讀成 ClassID=0 的單位(騎士 idx1/10/11、
龍劍士 idx17/20)其實是 **Camp=Own 的玩家隊伍成員**,不是敵人。查
`docs/data/exe_tables/resist_crit.json` 確認騎士的真正 class 是 3,不是 0——但
`applyPersistentParty(st)`(`cmd/fd2/main.go:2515`)本來就會用 `g.partyRoster[dst.Fig]`
的真實資料覆蓋 `dst.ClassID`(`applyPersistentStats` 裡有 `dst.ClassID = src.ClassID`),
只是這個函式一開頭 `len(g.partyRoster) == 0` 就直接 return。用除錯輸出確認:
`ai_winner_sweep_test.go` 每章都用 `g.resetBattle()` 冷啟動、不經過完整 campaign
流程,`g.partyRoster` 在呼叫前後都是空的(len=0)——這正是這個 harness 自己的既有取捨
(單章獨立抽樣,不模擬完整存檔進度),不是遊戲邏輯的缺陷。真正玩家玩到 ch21 時,
`g.partyRoster` 早就被 JOIN/教會轉職等歷史事件填好,`applyPersistentParty` 會正確覆蓋成
真實 ClassID,這個「resistance class=0」錯誤根本不會出現。**這一項不需要改任何程式碼**,
task #114 標記完成(結論是「排除」,不是「修復」)。

### #113 追加:修好 SelectionMode==0(自我原點)指令的 stage-1 不相容問題,剩一個更深的案例待查(2026-08-17)

延續上一段「stage-1 陣營檢查對 SelectionMode==0 架構上就是錯的」的結論,這次動手修了——但
刻意把改動範圍縮到只影響 `ExecuteNativeCommandDamage`(id 0..12 專用),不動共用的
`NativeCommandEffectTargets`(id 24/28/29/31 的 derived-strike 家族也有 dist=0 的記錄,
但那條路走的是完全不同、這次沒有反組譯證據的原生機制,不能套用同一個假設)。新增
`nativeSelfOriginCommandTargets`:record SelectionMode==0 時,不做「confirmed 是否在
actor 自己的 SelectionMode 範圍內」這個永遠不可能成立的 stage-1 檢查,直接從 actor 的
座標用 EffectMode 算最終目標清單,`confirmed` 只做「是否真的在結果清單裡」的 fail-closed
檢查,不重新推導。

**效果**:sweep 的 exec_ok/exec_fail 總數沒變(還是 26/35),但仔細看錯誤訊息——原本
`ch25`/`ch30` 的 id=12 案例(`confirmed unit is not a native command candidate`)現在正確
找到真目標了,只是撞上前一段已經排除的「sweep 冷啟動測試,partyRoster 是空的」那個已知
非 bug。也就是說這 2 個案例在真實遊玩裡,現在會是真的成功,不再是找到自己。

**剩一個沒解開的案例**:`ch21` 的 `劍士(33,19)` 施放 id=2(SelectionMode=5,EffectMode=1,
非自我原點)命中 `劍士(37,17)`,兩者曼哈頓距離 6,超過 SelectionMode=5 的直接範圍——但沒
超過「SelectionMode=5 找一個 destination、再從 destination 用 EffectMode=1 找目標」這種
兩段跳的極限(5+1=6,剛好吻合)。這代表 AI 評分階段真正選中的目標,是透過某個中繼
destination 格找到的,不是 actor 直接搆得到——但 `nativeAIThreeScorePlan`(#103 那次的
`TargetIndices[0]` 修法)只把「最終目標」傳給執行端,執行端的 stage-1 檢查驗證的是
「confirmed 是否直接落在 actor 的 SelectionMode 範圍」,對這種兩段跳案例一樣會失敗。
正確修法應該是把評分階段的 `Destination`(中繼格)也一起傳下去,執行端改成驗證
「confirmed 是否落在 destination 的 EffectMode 範圍」,而不是用同一顆座標驗證兩次。這
牽涉到 `NativeAISpellCandidate`/`AIPlan` 多帶一個欄位,範圍比這次的修法大一些,列為
明確待辦,先不倉促動手。

**驗證**:`go build ./...`、`go test ./... -count=1` 全綠(含既有 id=10 單體攻擊測試,
確認沒有改壞非自我原點的路徑)。

## #115:修好「兩段跳」目標的 stage-1 幾何檢查,ch21 的 id=2 案例完全解開(2026-08-17)

延續上一段列出的「剩一個沒解開的案例」——沒有走 `AIPlan.SpellDestination` 額外欄位那條
路(先動手加了、寫了完整文件註解,發現不需要簽章異動就能做,又整段還原了),改成自足式
修法,只改 `NativeCommandEffectTargets`(`internal/battle/native_command_target.go`)本身:

**舊邏輯**:stage-1 只檢查 `confirmed` 是否直接是 `NativeCommandTargets(actor 格,
SelectionMode,...)` 這份候選名單裡的一個「單位」——對玩家游標流程永遠成立(游標本來就被
限制在 SelectionMode 範圍內選格),但對兩段跳的 AI 評分結果(候選經由某個 SelectionMode
內的中繼格,再用 EffectMode 從那格搆到)必然失敗,因為 `confirmed` 根本不站在 SelectionMode
範圍內的任何一格上。

**新邏輯**:stage-1 改成先用 `NativeCommandTargetCells`(不是 `NativeCommandTargets`)算出
actor 的 SelectionMode 能搆到的「所有格子」(不要求格子上有人),優先嘗試 `confirmed` 自己
的格子(跟舊行為逐位元組相同,涵蓋所有目前已通過的案例——`confirmed` 原本就一定在
SelectionMode 範圍內是舊 stage-1 通過的前提,所以這條路徑對所有既有案例 100% 等價);找不到
才退回,對 SelectionMode 範圍內其餘每個格子(用 row-major 排序,確保結果可重現、不吃 Go
map 疊代順序的隨機性)用 EffectMode 各算一次目標名單,第一個名單裡包含 `confirmed` 的格子
即為真正的中繼 destination,直接回傳那份名單。

**效果**:`TestSweepNativeAIWinnersAcrossAllChapters` 裡 `ch21` 的 `劍士(33,19)` 施放
id=2 命中 `劍士(37,17)` 案例,不再是「confirmed unit is not a native command candidate」
——現在正確找到中繼格、算出目標,訊息變成「原始指令 2：命中 0，傷害 0」加
`native command damage missing resistance class=0`。這是先前 #114 已經根因分析過的
sweep 測試冷啟動假象(`g.resetBattle()` 逐章孤立呼叫,`partyRoster` 是空的,導致
`applyPersistentParty` 沒機會把 Own 陣營單位的 `ClassID` 覆寫回真實職業,測試裡讀到
`ClassID=0` 這個地圖 JSON 佔位值,查不到對應抗性)——不是新 bug,真實遊玩不會發生。
`ch21` 的另一案例 `劍士(7,19)`→`騎士(3,18)`(id=2)、`ch25` 的 id=12、`ch30` 的 id=12 都是
同一種假象,總計 4 個 exec_fail 全部同源,已用 grep 追蹤到
`internal/battle/native_command0.go:120` 的同一行錯誤訊息確認。

**影響範圍**:`NativeCommandEffectTargets` 有 9 個呼叫端(native_command0/13/17/20/24/25/26.go、
native_command_compound_exec.go、native_command_mp_steal.go)全部受惠,不只 id=0-12——這個
兩段跳幾何問題本來就是系統性的,不是單一 command family 的特例。

**驗證**:`go build ./...`、`go test ./... -count=1` 全綠(cmd/fd2、internal/battle、
internal/campaign 等全部套件皆 PASS,含既有的所有 command executor 測試)。
`TestSweepNativeAIWinnersAcrossAllChapters` 全量重跑:GRAND TOTAL 
physical=37 spell=35(exec_ok=31 exec_fail=4) item=11(exec_ok=10 exec_fail=1)——4 個
spell exec_fail 全部是上述已知的冷啟動 ClassID=0 假象,不是真正未解的目標選取 bug。
task #115 標記完成。

## #117:把 AI 評分階段已經算出的 Destination 一路傳到執行端,取代 #115 的搜尋式重建(2026-08-17)

延續上面 #115 跟 TargetIndices 兩段分析——搜尋式重建雖然對目前唯一已證實的案例(ch21
id=2)正確,但先天有個沒有證據能排除的弱點:如果 `confirmed` 同時落在「多個」
SelectionMode 內格子各自的 EffectMode 範圍內,row-major 搜尋只能任選第一個命中的,不保證
跟 native AI 評分時實際選中的 destination 一致,可能算出不同的完整命中清單。

往上追一層才發現:`nativeAIThreeScorePlan`(native_ai_three_score_plan.go:178)裡
`spell.PositiveWinner.X/Y`——也就是 0x1598a 評分階段真正選中的 destination,ground
truth,不是重建——當下就在作用域裡,只是被拿去 fallback `UnitAt()` 查詢後就丟棄,從沒
傳給執行端。這是明確的「該用真值卻自己重建」的架構味道(對應 code-review 的 Altitude
角度:特例補丁疊在共用機制上,更深的修法是把源頭的正確資料傳下去,而不是在下游猜)。

**修法**:`AIPlan` 新增 `Destination *Cell` 欄位,由 `nativeAIThreeScorePlan` 的 spell
分支直接用 `spell.PositiveWinner.X/Y` 填入。`NativeCommandEffectTargets` 新增
`scoredDestination *Cell` 參數——非 nil 時直接用該格作 stage-2 origin(仍保留「confirmed
是否真的在該格 EffectMode 範圍內」的 fail-closed 檢查),完全跳過搜尋;nil 時维持 #115
的搜尋式行為不變(玩家游標流程沒有評分階段可用,搜尋仍是唯一選項,且對游標流程永遠等價
於舊行為)。這個參數一路機械式穿過 13 個 executor 函式(`ExecuteBoundNativeCommand0`
/`ExecuteNativeCommandDamage`/`ExecuteNativeCommandHeal`/`ExecuteNativeCommandModifier`/
`ExecuteNativeCommandClearRestore`/`ExecuteNativeCommandDerivedStrike`/
`ExecuteNativeCommand25`/`ExecuteNativeCommandApplication`/`ExecuteNativeCommand32`~`35`/
`ExecuteNativeCommandMPSteal`)、`executeNativeCommandTarget` 分派器,兩個呼叫端分流:
`confirm()` 的游標流程傳 `nil`,`aiStep()` 傳 `plan.Destination`。

**新增測試證明修法真的有作用,不是空接線**:
`TestNativeCommandEffectTargetsScoredDestinationOverridesSearch` 建構一個 `confirmed`
同時落在兩個不同 SelectionMode 內格子(A、B)各自 EffectMode 範圍內的合成盤面,A、B 各自
搭配一個只有自己才搆得到的旗下單位(otherA/otherB)。不給 `scoredDestination` 時搜尋固定
選到 A(row-major 排序較前),回傳 `{confirmed, otherA}`;明確給 `scoredDestination=B`
時改回傳 `{confirmed, otherB}`——證明兩條路徑在真正有歧義的盤面上會給出不同答案,新參數
不是裝飾。另加兩個 fail-closed 回歸測試(scoredDestination 落在 SelectionMode 外必須拒絕;
scoredDestination 有效但 confirmed 不在其 EffectMode 內必須拒絕)。

**驗證**:`go build ./...`、`go vet ./...`、`go test ./... -count=1` 全綠(23 個檔案、
約 80 處呼叫點的機械式簽章異動,含全部既有 executor 測試)。重跑
`TestSweepNativeAIWinnersAcrossAllChapters`:GRAND TOTAL 跟 #115 完成時完全一致
(physical=37 spell=35 exec_ok=31 exec_fail=4 item=11 exec_ok=10 exec_fail=1)——對目前
30 章所有已證實案例,ground-truth 路徑與先前的搜尋式路徑答案相同,如預期;差別只在
`ch21` id=2 這種尚未在真實資料中出現、但理論上可能出現的多重 destination 案例上,現在
用真值而非猜測,不再有任何「兩者可能不一致」的殘留不確定性。task #117 標記完成。

## #113 追加:確認 `TargetIndices[0]` 選第一個索引不是 bug,跟用整個陣列等價(2026-08-17)

先前留的疑問:`nativeAIThreeScorePlan` 只採用 `spell.PositiveWinner.TargetIndices[0]`,
而 native 端 0x21548 尾端的執行迴圈是對整個 byte 陣列逐一呼叫 0x1c75e——這兩種讀法看起來
不一致,要不要改成也吃整個陣列才對?

**分析(純讀既有程式碼與先前反組譯證據,沒有新探測)**:
1. `nativeAIScoredCommandTargetIndices`(`native_ai_scored_candidates.go:118`)只對「單一」
   `destination` 呼叫一次,用 `NativeCommandTargetCells(destination, effectMode, ...)`
   過濾出的格子集合去比對每個單位的座標——也就是一組 `TargetIndices` 裡的每一個索引,全部
   都已經是「同一個 destination、同一個 EffectMode 範圍」下驗證過的成員,不是跨多個
   destination 湊出來的。
2. 執行端從來不是只對 `confirmed` 單一單位生效:`ExecuteNativeCommandDamage` 呼叫
   `nativeCommandDamageTargets`→`NativeCommandEffectTargets`,回傳的是從解出的 destination
   重新算出的「整組」EffectMode 範圍內目標,再對每一個成員套用效果(sweep log 本來就看得到
   `完成增益 (4/4 targets)` 這種多目標命中,不是只打一個)。
3. 因此 `TargetIndices[0]` 只是拿來當「種子」重新反推 destination 用的——陣列裡任何一個
   索引,只要重新丟進 `NativeCommandEffectTargets` 都會反推出同一個 destination,進而算出
   同一組完整目標清單。用 `[0]` 或整個陣列在結果上沒有差異,不需要改。

**結論**:`TargetIndices[0]` 不是 bug,是安全的簡化寫法,不用動。唯一殘留的理論邊界情況
跟 #115 那段記錄的一樣——如果 `confirmed` 自己的格子剛好也是一個獨立合法的 SelectionMode
destination(不是評分階段實際選中的那個),`NativeCommandEffectTargets` 的「優先嘗試
confirmed 自己格子」快速路徑可能反推出不同於評分階段的 destination。這是 #115 已知、
沒有實例可驗證的殘留不確定性,不是這次分析新發現的問題。

## #112/#116 追加:ch17 補完成 2/7,ch21/22/23/28 用 Ghidra headless 深入分析後判斷範圍比預期更大,暫不動手(2026-08-17)

延續上面「#112 的『7 章戰後過場全部修好』目標,這次只完成了 1/7(ch16)」的結論——這次
用能正常運作的 Ghidra headless 反組譯工具(見 `reference_fd2_live_ghidra_headless_probe`
memory)重新處理上一段標記為「差最後一塊位置資料」的 ch17。

**已修好(ch17,對應 `postbattle_ch18_persist`,需要 `ch17_post.json`)**:透過
`analyzeHeadless.bat` 對 `FD2Analysis3` 專案的 headless probe,強制反組譯 ch17 handler
自己的 `layout_units` 呼叫點(0x23d39)。呼叫端在傳 11 個參數給共用函式 0x233c6 之前,先用
`MOVSD.REP`/`MOVSB` 從三個固定位址(0x521c3 X 陣列、0x521d4 Y 陣列、0x521e5 pose 陣列,各
17 bytes)把資料表搬進區域堆疊緩衝——直接讀這三段 raw bytes,再對照 0x233c6 本體的逐格寫入
迴圈(主範圍 [start,end] inclusive,加一個由 5-8 號參數決定的「特殊格」,再存相機座標到
`0x53aa9`/`0x53aad`),把 17 個一般格 + 1 個特殊格 + 相機座標全部逐位元組讀出來,寫進
`assets/cutscenes/bindings/ch17_post.json`。掛上 `campaign_full.json` 的
`postbattle_ch18_persist` 節點後編譯零 issue(33 beats),`campaign_test.go` 的兩個回歸測試
(`TestCampaignFullPostbattleBindingsUseVerifiedRawOwner`、
`TestCampaignFullStoryScriptCoverageMatchesAudit`)、新增的
`TestPostbattleCh18UsesFreshCh17Binding` 全部通過。跟 ch16 不同,這次沒有現成候選檔案可以
重用,座標是第一次從原始位元組直接反推出來的,不是猜的。

**深入分析但判斷範圍過大、暫不實作(ch21/22/23/28)**:對這 4 個章節裡沒被
`handler_compile.go` 現有 `case "unknown":` 分支認得的 native_target 位址(真實數量
遠低於原本估計的「34 個」——先前只是天真地 grep `"op": "unknown"` 的出現次數,沒發現
其中多數已經有專屬識別分支;實際跑 `CompileHandlerScript` 用空 binding 對照原始 handler
JSON,只剩約 12-13 個位址真的沒有編譯器 case)逐一用 Ghidra probe 反組譯,結果分三類:

- **ch22 的 `0x2189a`**:原本期待是「快速解法」(座標算好就能收工),實際解碼後發現它同時
  計算「鏡頭平移到目標單位」的座標,還跑一個 10 次疊代的 sprite blit 動畫迴圈(呼叫
  0x11eb0)——是「援軍走位進場」的完整演出效果,不是純資料。這跟 doc91 原本「仍待處理」
  的判斷一致(不是推翻,是印證)——需要新的渲染引擎支援,不是單純填資料表。
- **ch21 的 `0x24618`(indexed_transition)**:4 個參數裡 2 個是靜態立即值
  (TileX=8、TileY=10),但 `RadialRadius`/`RadialRadiusStep` 依賴執行期全域狀態
  (`[0x53ab9]`/`[0x53abd]`),要連 pan 動作的副作用一起追蹤才能確定這兩個值,範圍超出單一
  呼叫點的反組譯。
- **ch22 的 `0x24b14`/`0x24bde`**:追蹤到各自呼叫的子函式後,語意上可以解讀成「隊伍是否
  持有道具 X」與「某記錄 byte+8 搜尋」,但匯出的 JSON 顯示它們是無條件執行的 beat,回傳的
  布林值被捨棄、看不到任何分支——玩法用途不明確,不確定接上之後該對應到 remake 的什麼
  行為,貿然接線風險比不接線更高。

以上三類都刻意選擇不倉促實作,留作有明確反組譯證據支持、範圍界定清楚的待辦——沒有動任何
程式碼,不影響現有測試。

**結論**:task #112 目前 2/7(ch16、ch17)完成,其餘 5 個(ch18/22/23/24/29,對應來源
ch17/21/22/23/28)確認是真正的反組譯缺口,不是接線問題。task #116(用可運作的 Ghidra
工具重新評估)已完成它原本的範圍——ch17 這次真的補上了,ch21/22/23/28 三類問題都有了
具體、有證據支持的判斷(不是「還沒查」,是「查過了,結論是範圍比預期大,不適合這次硬做」)。

## #112 追加:ch21/22/23/28 剩餘 10 個 native_target 位址逐一用 Ghidra 反組譯+反編譯完整分析,1 個修好,其餘有了具體、有證據的分類(2026-08-18)

延續上一輪「三類問題」的高層判斷,這次真正逐一位址做反組譯/反編譯(不是重述舊結論)。先用
`cmd/dump-unresolved`(這次新寫的小工具,對每個 handler 檔案用空 binding 跑
`CompileHandlerScript`,列出每個 unresolved beat 的 addr/target/reason)精確枚舉,
確認去重後只有 10 個真正的獨立位址(不是先前估計的 12-13,重複計數的部分已排除):
`0x24618`(ch21)、`0x24b14`/`0x24bde`/`0x2189a`/`0x4dbfc`/`0x10652`(ch22)、
`0x24d22`/`0x11d40`(ch23,`0x11d40` 這個位址雖然已有一個 proven 的 address-pinned case,
但那個 case 只認 `0x23599` 這個特定呼叫點,ch23 的呼叫點不同,一樣落回 unknown)、
`0x35bba`/`0x22253`(ch28)。逐一用 `DecompInterface.decompileFunction` 配合
`getInstructionAt`/`disassemble`/`createFunction` 強制建立函式再反編譯,拿到 C 虛擬碼後
再對照原始 handler JSON 的 `raw_args` 精確比對:

**已修好(ch28 `0x35bba`)**:反編譯在這個位址直接建立函式產生明顯是**中段亂碼**的結果
(`unaff_EBX + -0x3797f33c` 這種假暫存器算式)——強烈暗示位址錯位。往回手動解碼原始
bytes,找到 `0x35b78` 才是真正的函式進入點(`PUSH 0x10; CALL <prologue>; PUSH
[esp+8]; PUSH [esp+8]; CALL <fwd>; MOVZX EAX,[esp+0xc]; PUSH EAX; CALL 0x10b4e`)
——**exported 的 `"target": "0x35bba"` 落在真正函式本體內部 0x42 bytes 處**(剛好是第二個
`PUSH 0xff` 指令的位址),是匯出工具的定址誤差,不是不同機制。從真正入口反組譯到底,body
跟 `0x35822` 這個已證實的 case 逐指令對照後**完全同構**——`spawn(group)`、延遲
300ms、`0x11df2(0,255,255)` 全 DAC 飽和至白、延遲 200ms、`0x11df2(0,255,0)` 還原基準、
redraw——只差沒有前導 `pan`,且只吃一個 group 參數(不是三個)。由於編譯器比對的是 JSON
裡實際記錄的 `"0x35bba"`(不是我手動找到的真正位址 `0x35b78`——後者只用來確認語意,編譯器
仍然按 exporter 已經穩定產生的識別碼比對),在 `handler_compile.go` 新增
`input.NativeTarget == "0x35bba"` 分支,直接複用 `0x35822` 的 beat 建構邏輯(拿掉
pan,單一 group 參數)。`go build`、`go test ./... -count=1` 全綠。重跑
`cmd/dump-unresolved` 確認 ch28 的 `0x35bba` unknown 已消失,剩餘 9 個問題全部是已知模式
(6 個 dialog、1 個 spawn、1 個 pan——跟 ch16/ch17 一樣只差 binding 資料,不是反組譯缺口)
加上唯一的真正阻塞 `0x22253`(見下)。ch28 因此從「10 個位址幾乎全不透明」進步到「只差
一個已知的、有完整證據的引擎功能缺口」。

**深入反組譯後確認為「執行期全域狀態依賴,反組譯無法單獨解出,需要活體驗證」(ch21
`0x24618`、ch23 `0x24d22`+`0x11d40`)**:
- ch21 `0x24618`:反編譯確認函式本體正是已證實的 9-frame/0x40-step palette 迴圈
  (跟 `ch29_post.json` 已經在用的 `indexed_transition` binding 完全吻合,tile_x/tile_y/
  radial_radius/radial_radius_step 這 4 個固定計時/palette 常數全部對得上)。問題是
  `tile_x`/`tile_y`/`radial_radius`/`radial_radius_step` 這 4 個語意欄位:直接比對
  `ch29_post.json` 的 raw handler(`raw_args: [8, 10, "ebx", "dword ptr [0x3ab9]"]`)
  跟它自己已經在用、驗證過的 binding 資料(`tile_x:6, tile_y:6, radial_radius:10,
  radial_radius_step:8`)——兩者對不上(raw_args 的 8/10 不等於 binding 的 6/6)。這證明
  raw_args 記錄的立即值不能直接當成這 4 個欄位的來源,ch29 當初的正確數值必然是用活體
  DOSBox 記憶體讀出來的,不是靠反組譯這幾個立即值算出來的。ch21 的 raw_args 是
  **完全相同的形狀**(`[8, 10, "eax", "dword ptr [0x3ab9]"]`),同樣需要活體驗證,靜態
  反組譯到此為止已經是能拿到的全部資訊。
- ch23 `0x24d22`(兩次呼叫,beat=3/beat=8):完整反組譯出函式本體後,語意完全解開——這是
  一個「設定/觸發」雙模式函式:非零參數只是把 `DAT_00051a10`(啟始列)設成該參數的值就
  return;參數=0 才真正執行「從 `DAT_00051a10` 列往下到第 191 列」的逐列 reveal wipe(逐列
  blit 呼叫 `0x3771c`,stride 312 完全吻合已知的 312px 內容寬度常數)。但往上追呼叫端的
  控制流才發現:ch23 這兩次呼叫**全部落在同一個巢狀迴圈**裡(外層 EDI 從 2 累加到 14、內層
  EBX 跑 12 次呼叫 `0x11d40(esi,255,0)` 加 `0x17aa9(1)` 延遲),EDI **從未在這段可追蹤的
  範圍內變成 0**——也就是說,兩個已匯出的 beat 全部是「設定模式」呼叫,真正的觸發呼叫
  (參數=0)沒有出現在目前追到的範圍內,DAT_00051a10 最終停在哪個值、wipe 到底有沒有真的
  在 ch23 觸發、esi 的起始值是多少,這些都是靠純反組譯手動追蹤位元組已經追不動的東西
  (需要完整 Ghidra 函式邊界分析,而 `-noanalysis` 模式下 `getFunctionContaining` 對這整段
  handler 程式碼回傳 null——確認這整片 ch21-28 handler 區域從未被自動分析器邊界化過,不是
  這次才發現的限制,是先前已知的「未邊界化 gap」延伸到更大範圍)。**結論不變:需要活體
  DOSBox 驗證才能往下走,不是編譯器補幾行 case 就能解的資料缺口**。

**深入反組譯後確認為「語意已解開,但需要新的 schema/引擎能力才能使用」(ch22
`0x24b14`/`0x24bde`、`0x2189a`、ch28 `0x22253`)**:
- ch22 `0x24b14`(呼叫端立即參數 100):反編譯確認是「掃描最多 16 個索引,呼叫
  `0x2aedb(index)` 直到找到非 -1 的結果」的存在性檢查,回傳 1(找到)或 0xffffffff(沒找到)
  ——一個純布林條件檢查函式,100(0x64)很可能是一個道具 ID。
- ch22 `0x24bde`(立即參數 18):反編譯確認是「掃描 `DAT_00053bfb` 筆名單(stride 0x50,
  正是 native record 的 80 bytes)第 +8 byte 是否等於參數」的存在性檢查,回傳 1/0。
- 兩者的共同問題:匯出的 JSON 把它們記成**無條件執行**的單一 beat,回傳值被捨棄——native
  端顯然是拿這個布林結果去決定要不要跳過後面某段程式碼,但目前的 beat schema 沒有「依據
  一個原生條件檢查跳過後續 beats」這種概念,不是反組譯不夠,是 schema 需要先擴充「有條件
  skip」這個機制才有地方接。
- ch22 `0x2189a`(三次呼叫,參數各為 (10,15,1)、(10,15,1)、(16,30,1)):反編譯確認是
  10-iteration 的 sprite walk-on 動畫迴圈(呼叫 `0x11eb0` present),跟先前判斷一致——這次
  額外拿到三次呼叫各自的目標座標,之後真的要做這個引擎功能時資料已經備妥,不用重跑。
- ch28 `0x22253`(立即參數 10,15,10,15 + 一個暫存器):這次反編譯出**完整的 5 參數簽章**
  (先前只知道「11+6+10 選段」這個粗略輪廓)——`param_1`=slot(寫入 `record[slot]`,
  stride 0x50)、`param_2`/`param_3` 寫入 `record[slot]` 的 byte0/byte1(X/Y,跟
  layout_units 同一套座標系統)、`param_5` 跟 `DAT_00053aad`(鏡頭 Y,layout_units 那次
  investigation 已知的全域)比較,決定播放 0x18(24)或 0x12(18)幀的 reveal 動畫。這次的
  反組譯把原本標成 `unit_present is blocked` 的模糊描述,換成了精確、可執行的參數語意——
  仍然需要新的動畫引擎支援才能真正接上,阻塞原因沒變,但至少不再是黑盒子。

**exporter 資料品質問題,反組譯無法進一步解出(ch22 `0x4dbfc`)**:目標位址落在另一個函式
本體中段(緊接在 `POP EBX; POP ECX; POP EDI; POP ESI; POP EBP; RET` 尾端之後幾個 bytes),
根本不是任何函式的合法進入點——這不是「還沒反組譯到」,是這個記錄的位址本身大概率是
exporter 對某種間接呼叫的誤判(不排除跟 `NativeCommandTargetFieldBytes` 文件註解提過的
同名位址 `0x4dbfc` 混淆,但那是完全不同子系統——AI 目標欄位,不是過場演出——語意上不太
可能是同一個呼叫)。跟 ch28 `0x35bba` 不同的是,那次錯位後 42 bytes 內就能找到明顯合理的
真正函式;`0x4dbfc` 附近則是另一個無關函式的尾端,沒有「往前找到真正入口」的線索可循。

**新理解但仍不確定是否可安全跳過(ch22 `0x10652` "prepare_chapter_aux_graphics")**:
完整反編譯確認這是一個「依目前章節號(`DAT_00053c03`)分派」的函式——ch22 呼叫時分派到
`DAT_00053c03==0x16` 分支,呼叫兩次 `0x111ba`(load_res,跟緊接在它前面的 3 個明確
`load_res` beat 用的是同一個原生函式)加對應的 `0x4e98d`(套用已載入資源)。不確定的是:
這兩次資源載入,跟緊鄰的 3 個明確 `load_res` beat 是不是載入同一批資源(重複,可以安全跳過)
還是額外的、目前完全沒被明確 beat 涵蓋的第 4/5 筆資源——`-noanalysis` 反編譯沒能呈現
`0x111ba` 自己的參數(資源 ID),不解決這個問題就沒辦法保證跳過或補上都不會遺漏內容。

**結論**:這次真正動手反組譯每一個位址,而不是重複先前的高層判斷——1 個位址完全解開並
修好(ch28 `0x35bba`,已建 case、已測試、已驗證),4 個位址語意完全解開但需要新的
schema/引擎能力(不是反組譯缺口),3 個位址(1 個完整位址 + 1 個位址的兩個呼叫點)確認為
執行期全域狀態依賴、反組譯已經到頂需要活體驗證,1 個位址是 exporter 資料品質問題,
1 個位址語意大致清楚但需要進一步資料才能判斷是否可安全跳過。ch28 因為這次修好
`0x35bba`,只剩 `0x22253` 這一個已知、有完整參數語意的引擎功能阻塞,是這 4 章裡最接近
完成的一個。task #112 保持 in_progress(誠實反映:1/10 位址修好,其餘 9 個都有具體分類
而非「還沒查」)。

## #112/#118 追加:重建 DOSBox-X 活體驗證環境(Docker 已移除,改用 WSL2 native),排除一個假設、確認真正的阻塞點是缺少夠接近的存檔(2026-08-18)

承上,ch21 `0x24618` 跟 ch23 `0x24d22`/`0x11d40` 這三個位址被歸類為「需要活體驗證」。
`reference_fd2_dosbox_live_memory_extraction` memory 記錄的方法本身沒問題,但它的環境
設置步驟建立在 Docker 容器上——Docker Desktop 已在 2026-08-16 因無法修復的 AF_UNIX bug
被完整移除(見 `docker-desktop-af-unix-broken` memory)。這次改在 WSL2 Ubuntu 原生重建整條
鏈路(套件安裝需要使用者的 sudo 密碼,使用者忘記密碼,改用 `wsl -d Ubuntu -u root` +
`passwd` 免舊密碼重設):照 `docker/dosbox-x/Dockerfile` 同一個 pinned commit
(`joncampbell123/dosbox-x@0d7b272b`)用 `build-debug-sdl2` 從源碼編譯出帶 heavy debugger
的 dosbox-x,Xvfb+tmux 起 headless session 掛載遊戲目錄跑 `FD2.EXE`,截圖確認標題畫面
正常顯示——整條鏈路重建成功,且意外發現 WSL2 這台機器的 `/etc/wsl.conf` 開了
`systemd=true`,代表背景行程(Xvfb、tmux 裡的 dosbox-x)在個別 `wsl.exe` 呼叫結束後
仍會存活,不需要額外保活手法。詳細建置步驟寫入新 memory
`reference_fd2_dosbox_wsl2_native_build`。

**排除一個假設**:先前(這次 session 之前)的推測是「`RadialRadius`/`RadialRadiusStep`
([0x53ab9]/[0x53abd])要連 pan 動作的副作用一起追蹤才能確定」。這次直接反編譯 `0x135dd`
(pan 函式本體)確認:它只寫 `DAT_00053aa9`/`DAT_00053aad`(逐格步進到目標鏡頭 X/Y)跟
`DAT_00053ab1`/`DAT_00053ab5`,**完全不碰 `0x53ab9`/`0x53abd`**——兩組全域變數位址雖然
在同一個 0x53aXX 叢集裡,只差 0x10,但是不同欄位。這排除了「radial_radius 由 pan 的
side effect 決定,可以純靜態分析從 pan 的 grid_x/grid_y 反推」這個原本以為可行的捷徑。

**真正的阻塞點,不是環境問題**:dosbox-x 活體環境已經可以正常運作,但要驗證 ch21/ch23
的 postbattle handler,需要遊戲實際執行到那個章節的過場——用專案自己的 `internal/fdsave`
解碼器檢查這台機器上僅有的 `FD2.SAV`,4 個存檔位全部落在 ch6/7/8/10,離 ch21 還差
11 章、離 ch23 還差 13 章。用 `xdotool` 腳本化打完 11+ 章戰鬥是一個範圍遠大於「環境設置」
的獨立大工程,這次選擇不用「直接竄改存檔章節位元組跳過去」這種捷徑硬做——那樣拿到的遊戲
狀態(隊伍名單、裝備等)會不一致,讀出來的值不能保證是「章節 21 真正會出現的值」,反而
可能製造出看似有根據、實際上是竄改狀態產物的假數據,違背專案一貫「不用活體驗證就不編造
內容」的原則。

**結論**:dosbox-x 活體驗證環境本身的問題已經解決(可重複使用的基礎設施,寫入
memory,下次 session 不用重頭來過),但 ch21/ch23 這 3 個位址的活體驗證仍然卡住——
不是工具問題,是「需要打完 11-13 章戰鬥才能到達驗證點」這個更大的範圍問題。誠實維持
「需要活體驗證」的分類,不宣稱已完成。task #118 保持 in_progress,記錄成一個範圍
明確、下次可以直接接手(不用重建環境)的獨立待辦。

## #118 追加:評估「腳本化打完 ch11-23」的真實範圍,確認比預期更大,使用者決定先不做(2026-08-18)

使用者一開始選擇「繼續打通這條路」,實際評估腳本化範圍後,發現這不只是「打很多章節」的
量的問題,是缺少好幾個從零開始的能力:

- **沒有任何「打完一整場戰鬥」的既有腳本**:`tools/docker/fd2-dosbox-screenshot.sh`
  這個既有的 timeline runner 只做過畫面導航(標題畫面、鎮上畫面等待特定像素出現),
  從沒腳本化過「移動單位→攻擊→擊殺→結束回合」這種完整戰鬥迴圈。`remake/cmd/fd2` 底下
  雖然有 `FD2_SHOT_AUTOPLAY`/`FD2_SHOT_FORCE_WIN` 這種自動打完戰鬥的機制,但那是驅動
  **Go remake**,不是原始 DOS `FD2.EXE`,邏輯不能直接搬過來用在 DOSBox 這邊。
- **連「結束回合」的按鍵都沒有文件記錄**:doc13(戰鬥選單按鍵對照)只涵蓋動作選單本身
  (攻擊/法術/道具/待機),沒有記錄開始下一個單位或結束整個回合用的按鍵。
- **沒有「游標移動路徑→按鍵序列」的轉換能力**:現有 doc58 的 E2 測試(單次攻擊驗證)
  全部是人工手動把游標移到攻擊範圍內的格子,沒有寫過自動尋路轉按鍵序列的工具。
- **沒有通用的「戰鬥已結束」畫面偵測**:既有的 `waitpixel`/`town_ready` 這類探測只認得
  幾個特定已知畫面,不是通用的戰鬥結束偵測。
- 每章地圖的敵人數量、位置、地形都不同,不是「寫一次腳本重複跑 13 次」,而是要打造一個
  能在 11-13 張完全不同的戰術地圖上盲打（沒有即時視覺回饋迴圈,只能靠截圖判讀)都能贏的
  通用「戰術 SRPG 遊玩機器人」。

值得一提的是,doc58 在**這次 session 之前**就已經評估過完全一樣的做法,並且用幾乎一樣
的理由回絕過(見前面「#112 追加:7 個缺 handler_binding」段落:「範圍比預期大很多」),
這次是第二次獨立評估、得到相同結論——不是偶然,是這個任務本質上就是一個遠超「架設環境」
規模的獨立工程。

跟使用者確認這個具體化後的範圍,使用者決定**不繼續做這件事**,選擇誠實記錄為未完成的
待辦,把精力留給其他工作。**結論**:ch21 `0x24618` 的 `radial_radius`/`radial_radius_step`
與 ch23 `0x24d22`/`0x11d40` 的 `DAT_00051a10`/esi 起始值三個位址,正式標記為「需要活體
驗證,範圍確認超出這次 session 的合理投入,刻意選擇不做」——dosbox-x 活體驗證環境本身
已經是可重複使用的基礎設施(見 `reference_fd2_dosbox_wsl2_native_build` memory),
未來若有更充裕的時間預算,或找到/取得一個已經更接近 ch21/ch23 的存檔,可以直接從這裡
接手,不必重新評估或重建環境。task #118 標記為「已評估、刻意暫緩」,不是「失敗」也不是
「完成」。

## #112/#118 追加:排除三個靜態分析捷徑假說,窮盡後確認活體驗證真的無法繞過(2026-08-18)

使用者問「有沒有更深入仔細分析的更好方式」——這次針對 ch21 `0x24618` 的
`radial_radius`/`radial_radius_step`(`[0x53ab9]`/`[0x53abd]`)額外測試了三個原本可能
繞過活體驗證的靜態分析假說,逐一用反編譯證據排除:

1. **「pan(0x135dd)的副作用設定這兩個全域」**——已在前一輪排除(pan 只碰
   `aa9`/`aad`/`ab1`/`ab5`,不碰 `ab9`/`abd`)。
2. **「另一個相機函式 `0x12cea` 才是真正的 setter,能從 ch21 自己的呼叫參數反推」**——
   反編譯 `0x12cea(param_1, param_2)` 確認它會把 `DAT_00053ab1` 步進到 `param_1`、
   `DAT_00053ab5` 步進到 `param_2`,而步進用的子函式(`0x11bfa`/`0x11c59` 等)內部會
   依條件連帶修改 `ab9`(或 `aa9`)——這是真正操作 `ab9`/`abd` 的機制沒錯,但比對
   ch21 自己完整的 handler beat 清單(layout_units、dialog、act、dialog、
   pan、act、dialog、pan、`0x24618`)——**完全沒有任何一個 `0x12cea` 呼叫**,只有
   兩次 `0x135dd`(已確認不碰這兩個全域)。這條路對 ch21 的當前呼叫序列不適用。
3. **「ch21 的 postbattle handler 開始前,某個通用的初始化流程會把這兩個全域重設成 0,
   所以進入點的值是固定的 0」**——對整個 binary 做完整 xref 搜尋,找出所有會呼叫
   `0x205da`(那個把 `aa9`/`aad`/`ab1`/`ab5`/`ab9`/`abd` 全部歸零的重設函式)的位址,
   **全binary 裡只有 3 個呼叫點**,而且全部集中在同一小段程式碼裡(0x32330~
   0x3281d),其中一處還連帶把 `DAT_00053c03`(章節號)設成 `0x1f`(31,超出遊戲
   30 章的範圍)——強烈指向這是**第 30 章結局(ending)專屬的場景初始化碼**,不是
   每章 postbattle handler 進入前都會跑的通用流程。ch21 的 postbattle handler 不在
   這 3 個呼叫點涵蓋範圍內,代表 `ab9`/`abd` 在 ch21 的 `0x24618` 呼叫點之前**沒有**
   被重設,值是從「剛打完的那場戰鬥」實際遊玩過程累積下來的殘留狀態,不是固定常數。

**結論**:三個原本合理、值得一試的靜態分析捷徑全部窮盡並排除,每一個都有具體反組譯/
反編譯證據支持(不是猜測或放棄)。這次的排除本身是有價值的成果——確認了
`0x53ab9`/`0x53abd` 這類「累積型執行期狀態」(跟單純的「呼叫時的立即參數」或「單一函式
副作用」不同)在缺乏活體驗證手段時,沒有任何已知的靜態分析方法能可靠地算出正確值。
`0x12cea` 的完整步進機制(連帶影響 `ab9`/`ab1` 或 `aa9`,依 `DAT_00053ac1` 門檻決定)
已經寫入這篇記錄,留給未來任何真的呼叫 `0x12cea` 的章節參考,但對 ch21/ch23 這兩個
具體案例沒有幫助。task #112/#118 的分類維持不變:ch21 `0x24618`、ch23
`0x24d22`/`0x11d40` 仍然是「需要活體驗證,這次刻意不做」,現在有更完整、經過窮盡測試的
證據支撐這個結論,不是初步判斷。

## #118 追加:使用者同意下實際嘗試腳本化打 ch11,卡在戰鬥指令確認這一步(2026-08-18)

使用者同意後,實際用 dosbox-x 環境從 ch10 存檔載入、走過城鎮、觸發「要進入戰場嗎？」
確認、進入 ch11「幻之森林」戰鬥,過程本身證明整條鏈路(存檔讀取、城鎮移動、互動觸發、
戰鬥地圖載入)都正常運作。卡住的地方是**戰鬥地圖裡「選取單位→確認移動/原地不動→叫出
攻擊/法術/道具/待機四方向選單」這一步**,這是使用者親自描述操作邏輯後仍然沒能重現的:

- 方向鍵確認可以正常移動游標(可從螢幕截圖直接驗證)。
- Enter 鍵在**其他情境全部正常**:標題選單(選 LOAD)、存檔選擇畫面、「要進入戰場嗎」
  YES/NO 確認、開場對話推進——全部順利用 Enter 完成。額外開一個乾淨的 DOS 提示字元
  測試,打 `DIR` 按 Enter 也正常執行,排除「按鍵事件根本沒送達」這個最底層的假設。
- 但在戰鬥地圖選取單位後,無論游標停在單位自己的格子、其他友軍佔用的格子,還是真正
  空地,反覆按 Enter(含一般 Enter 跟數字鍵盤 Enter、含長按)都沒有觸發預期的四方向
  選單,角色也從未出現「已行動」的反灰狀態。畫面在兩種明暗狀態間切換,但這個切換
  最後連按三次 Escape 都無法改變,可能根本是地圖本身的環境光影動畫,跟我的按鍵無關,
  不是先前以為的「選取中/未選取」狀態指示。

**結論**:這不是單純「操作邏輯猜錯」或「環境沒架好」,是這個特定互動點的實際行為
超出目前用截圖來回加使用者親自指導都排除不了的範圍。繼續用相同的盲測方式大概率不會
有新進展,需要更進階的除錯手段(例如用 dosbox-x 自帶的 heavy debugger 直接看
INT 16h 鍵盤緩衝區有沒有收到事件、或反組譯這段戰鬥指令迴圈確認真正期待的按鍵)才有
機會突破。這次沒有繼續往那個方向做(範圍已經超出「腳本化打幾場戰鬥」,變成另一輪
反組譯工作)。dosbox-x 環境跟已驗證的操作方式(城鎮移動、進入戰場觸發)仍然是有效、
可重用的基礎設施。task #118 維持「已充分嘗試,卡在具體、已記錄的技術點」的誠實狀態,
不是「還沒試」也不是「解決了」。

## 2026-08-17（續）#118 — 用 Ghidra 反組譯戰鬥指令輪的實際觸發邏輯，取代盲測

延續上面的結論，改用 `reference_fd2_live_ghidra_headless_probe` 記錄的方法（headless
`analyzeHeadless -readOnly` + `FD2Analysis3` 專案），直接反組譯戰鬥輸入處理的整條呼叫鏈，
不再猜按鍵。結果：

1. **`0x18d8c`**（doc13 已知的「action-ring dispatcher」，`[0x53c57]` 是狀態選擇器）反組譯
   確認：這是**已經進入指令輪之後**的導航迴圈，靠輪詢 `FUN_000177fc()` 讀 scancode：
   方向鍵（`0x48`/`0x50`/`0x4b`/`0x4d` = 上/下/左/右）只更新 `DAT_00053c57`（目前反白的
   輪選項）並繼續等待；**Enter(`0x1c`)/Space(`0x39`) 立刻跳出迴圈、對目前 `DAT_00053c57`
   的值執行動作**；Escape(`0x01`) 取消。也就是說 Enter 在這個函式裡從來不是「打開選單」，
   是「確認目前反白的選項」。
2. 往上追一層呼叫者 `0x18890`：這個函式才是真正**進入**上述指令輪迴圈的地方
   （`do { iVar3 = FUN_00018d8c(); } while (iVar3 == 0);`）。
3. 再往上追一層 `0x117e7`（唯一呼叫者在 `0x25dce`，屬於戰鬥地圖主迴圈）：這才是**最頂層
   的地圖游標按鍵處理**，讀的 scancode 跟上面同一套慣例：
   - `iVar2==1||0x2c||0x4c`（Esc / Z / 數字鍵盤5）→ 掃描全部單位找「還沒行動」的，
     把攝影機跳過去（`FUN_00012d7b()` + 遞增 `DAT_00053ae9`）——這是「跳到下一個可
     行動單位」熱鍵，不是取消。
   - **`iVar2==0x39||0x1c`（Space/Enter）→ 真正的「選取游標下單位」邏輯**：先呼叫
     `FUN_00012c0d()` 拿游標下的單位索引，`-1` 就走另一支（可能是打開系統選單）；
     否則檢查該單位 native record（`DAT_00053a45 + index*0x50`）三個條件都成立才會呼叫
     `FUN_00025a96()` 後進入 `0x18890`（=真正的指令輪）：
     - `record[+6] == 0x02`（單位型別/狀態必須是 2）
     - `record[+5] & 0x80 == 0`（**「已行動」旗標必須是 0**——這個位元組偏移跟
       remake 自己的 `SetNativeRecordBit7`/`ClearNativeRecordBit7All`
       [native_record_flags.go](../../remake/internal/battle/native_record_flags.go)
       完全對得上，證實 `+5` bit7 就是 Acted 旗標）
     - `record[+0x26] == 0`（第三個守門旗標，目前用途未查）
     - 只要有一個不成立，就走 `FUN_00017aed()`——這極可能就是我一直按 Enter 看到的
       「角色狀態總覽畫面」（LV/HP/MP/裝備清單），不是指令輪。

**這解釋了為什麼一直看不到指令輪**：目前測試用的單位（Sol）很可能在這次即時操作稍早
的某次按鍵中已經被標記「已行動」（`+5` bit7=1），導致 Enter 之後穩定落入
`FUN_00017aed()`（狀態畫面分支）而非 `0x18890`（指令輪分支）。用 Escape/Z/Numpad5
測試「跳到下一個可行動單位」熱鍵、以及嘗試 F1（doc 猜測的結束回合鍵，`0x3b`/`0x49`
scancode）都沒有讓畫面變化——但這兩個熱鍵本身可能被 DOSBox-X 自己的 GUI 層攔截，
不代表 Ghidra 反組譯出的邏輯有錯（`0x18d8c`/`0x117e7`/`0x177fc` 的反組譯本身沒有任何
含糊之處，是直接讀出的組合語言邏輯，不是猜測）。

嘗試用既有的即時記憶體讀取方法（[[fd2-dosbox-live-memory-extraction]]）直接讀
`record[+5]` 驗證 Acted 旗標，但這次沒有重新做「byte-signature + delta」比對就直接猜
flat selector（`GDT` 裡 base=0/limit=0xFFFFFFFF 的 `0038`），讀回全部是 0——跟兩天前
記錄的已知結論一致（DOS4GW loader 實際載入位置跟猜測的 selector/base 對不上，
必須重新做一次完整的 byte-signature 比對才能算出正確的 delta，這次沒有重做）。

**結論（誠實狀態）**：這次的 Ghidra 反組譯是**真正的進展**——第一次拿到「戰鬥指令輪
到底怎麼被觸發」的確定性、非猜測的答案，直接補完了 doc13 沒寫的「進入指令輪」前置條件，
也印證了 remake 自己 `native_record_flags.go` 對 `+5` bit7 語意的還原是正確的。但**活體
DOSBox-X 操作驗證仍未完成**：還沒有實際重現指令輪畫面本身，卡在「目前測試單位大機率
已經被標記已行動、而結束回合/跳下一單位的熱鍵測試又受 DOSBox-X GUI 層干擾」。要真正
解鎖，下一步應該是重新走一次乾淨流程（重開一局全新戰鬥，第一次按 Enter 就先確認
`record[+5]`/`+6`/`+0x26` 三個條件、不要在那之前做任何其他按鍵嘗試），或者改用「直接對
`0x24618`/`0x24d22` 這兩個 ch21/ch23 目標位址下執行斷點」的方式，跳過整個 UI 導航問題，
讓遊戲自己跑到那兩行程式碼再暫停讀值——後者需要先解決「不知道 FD2.EXE 實際載入時的
flat selector/base」這個既有已知瓶頸（同樣需要重做 byte-signature delta 比對）。
task #118 維持進行中，比 08-17 稍早的記錄多了一層確定性知識，但仍未拿到 ch21/ch23
的實際數值。

## 2026-08-17（續二）#118 — 依使用者指示重開乾淨新戰鬥，第一次 Enter 測試，仍未重現指令輪

依照使用者選擇的方案，完全重開 dosbox-x（新 tmux session，殺掉舊的），從 New Game
重新走一次開場過場（約 150+ 次 Enter），刻意**不做任何多餘探索性按鍵**，第一次真正進入
戰鬥地圖畫面就直接測試單一 Enter。結果：

- 進入戰鬥地圖後第一次按 Enter：顯示「索爾」角色狀態總覽畫面（LV/HP/MP/裝備）——
  跟先前反覆看到的畫面完全一樣。
- 再按一次 Enter（原地不動、無任何其他按鍵介入）：畫面完全沒有變化（連續兩次獨立截圖
  逐 pixel 相同）。
- 按 Escape：回到地圖畫面（小 HUD 框顯示「A+05 D+00」），跟先前完全一致、可重現。
- 用方向鍵（下×3）把游標移到明顯的空地格子再按 Enter：**還是跳出一模一樣的索爾狀態
  畫面**，不是反組譯預期的「找不到單位→另一分支」。這代表方向鍵在這個畫面狀態下可能
  根本沒有真的移動游標（或者這個畫面根本不是 `0x117e7` 在處理的那個地圖游標狀態）。

**這推翻了「單純因為 Acted 旗標已設定」的假說**——這次是全新重開的第一場戰鬥、
第一次按鍵，不可能有任何單位已經行動過。Enter/Escape 這組穩定切換（不管按幾次都不變）
更像是一個**獨立的模態畫面**（可能是「開戰前隊伍總覽」的預覽/確認畫面），根本還沒進入
`0x117e7` 實際處理的地圖游標狀態，方向鍵在這個模態裡也可能被忽略或無效。

**結論（誠實狀態）**：依照使用者建議的「重開乾淨測試」方案已經確實執行，但沒有解開
謎團——反而排除了原本最有把握的假說，指向問題出在更早的一層（可能是「隊伍總覽」跟
「地圖互動」兩個畫面狀態之間還有一個未知的轉換條件/按鍵）。目前已經測試過的按鍵組合
非常廣（方向鍵、Enter、Space、Escape、Tab、F1、'a'、'z'，含各種順序組合），持續用相同
方式盲測下去邊際效益很低。task #118 維持 in_progress，如需繼續，建議下一步是對
`0x117e7`/`0x18890` 這兩個位址設中斷點直接觀察，而非再猜按鍵——但這需要先解決「不知道
FD2.EXE 實際載入時的 flat selector/base」這個既有瓶頸（重新做一次 byte-signature +
delta 比對）。

## 2026-08-17（續三）#118 — 使用者提供第三方記憶體位置文件，交叉驗證 Ghidra 發現，
## 但活體游標移動仍未確認可運作

使用者貼上一份詳盡的第三方「炎龍騎士團2」記憶體修改/攻略文件（作者：青衫），其中
「人物資料在記憶體中的安排」章節記錄了完整的 80 byte（50h）單位記錄結構。逐 byte比對
後發現：**該文件的絕對 offset = 本次 Ghidra 反組譯裡 `iVar2` 的相對 offset + 8**——
文件 offset 13（AA=動作狀態，00=尚未行動/01=死亡/80=行動完畢）精確對應 Ghidra 的
`iVar2+5`，文件 offset 14（BB=陣營，00=敵方/01=友方/02=己方）精確對應 Ghidra 的
`iVar2+6`。這獨立證實了先前 Ghidra 反組譯讀出的三個守門條件是正確的，且揭露了一個
先前沒注意到的關鍵語意：**BB 陣營有三種值，不是只有「敵/我」兩種**——01=友方（NPC
盟友，如第一章的「LV2士兵x4」）不等於 02=己方（玩家可操控角色，第一章只有索爾一人）。
這代表游標必須精確停在索爾本人身上才能打開指令輪，停在友方 NPC 士兵身上一樣會走向
角色狀態畫面分支（因為 BB≠2）。

依此線索重新檢視畫面，先前誤判為「地圖裝飾物」的方框圖示群（金色寶箱、藍色圖示等）
很可能其實是友方士兵的單位圖示（陣營用邊框顏色區分：這次截圖確實看到邊框顏色從全橙
變成紅／藍混合，說明這些單位有即時狀態變化，不是靜態裝飾）。用 2 倍放大截圖仔細檢查
索爾本人所在位置附近，確認：**完全沒有看到任何游標高亮方塊或指示物**，且連續按方向鍵
（上×2）前後兩張放大截圖逐 pixel 相同。

**結論（誠實狀態）**：這次使用者提供的第三方記憶體佈局文件是很有價值的獨立交叉驗證，
證實了 Ghidra 讀出的守門邏輯正確無誤，也排除了「我按鍵按錯位置」以外的一種可能解釋
（陣營判斷邏輯本身沒有問題，索爾應該的確是 BB=02）。但根本問題還是没解——**方向鍵在
這個畫面狀態下是否真的有送到遊戲，仍然無法確認**（沒有任何視覺回饋），這比指令輪
本身更基礎、更優先需要解決。在無法確認游標真的能移動到索爾身上之前，繼續測試指令輪
的觸發條件沒有意義。task #118 維持 in_progress，本回合的按鍵盲測已經到達報酬遞減
的程度，建議之後改用中斷點直接觀察記憶體/暫存器狀態，而非繼續依賴畫面截圖回饋。

## 2026-08-17（續四）#118 — 真正用中斷點+即時記憶體驗證，重大進展但仍未親眼看到指令輪

依照上一輪的建議，這次真正做了完整的 byte-signature + delta 記憶體比對，不再猜測。

**方法**：用 Ghidra 匯出 `0x117e7`/`0x18d8c` 兩處函式開頭各 64 byte 的原始機器碼作為
signature，對 dosbox-x heavy debugger 用 `MEMDUMPBIN 170 0 400000` 匯出 4MB 即時記憶體，
逐一比對找到唯一匹配位置。兩個獨立 signature 都算出同一個 delta = `0x19C000`
（`live = ghidra + 0x19C000`），互相印證非巧合。這是本專案第一次在**這次的 dosbox-x
執行實例**上真正解開「不知道 FD2.EXE 實際載入位置」的老問題（[[fd2-dosbox-live-memory-extraction]]
記錄的方法本身沒錯，只是每次重開 dosbox-x 都要重新算一次 delta，這次確實重算了）。

**用中斷點實測，推翻了先前所有基於畫面猜測的結論**：

1. 在 `0x117e7`（地圖游標最上層處理函式）的入口、以及其內部關鍵的陣營/已行動判斷指令
   （反組譯位址 `0x11912`／`0x11917`／`0x1191d`）都下了執行中斷點。按下 Enter 後
   **這些中斷點完全沒有觸發**——證實先前一路以為「卡在 0x117e7 的陣營判斷」是錯的，
   這個函式根本沒有被呼叫。
2. 改用 `BPINT 09`（鍵盤硬體中斷）驗證，**這個確實有觸發**——證明按鍵事件本身有正常
   送達 BIOS/DOS4GW 這一層，排除「輸入完全沒送到」的可能。
3. 用 `LOGC`（CS:IP-only CPU 執行紀錄）從中斷觸發的那一刻開始，真正記錄 Enter 按下後
   實際執行的指令位址序列，逐一還原成 Ghidra 函式名稱。結果指向一條完全不同、先前
   從未分析過的呼叫鏈：`FUN_0001b932`（重置 `DAT_00053c57=0`，迴圈呼叫下面這個）→
   `FUN_0001b9de`（用 `DAT_00053c57` 當 0-7 的道具格游標，方向鍵 ±1/±4 移動、
   Enter/Space 確認、Escape 取消回傳 -1）。
4. 往上追呼叫者，`FUN_0001b9de`/`FUN_0001b932` 只有 3 個呼叫點：`0x190ac`（`0x18d8c`
   ring dispatcher 的 else/預設分支，也就是 FAQ 講的「下=休息」）、`0x1aa1d`、
   **`0x1bbdc`（`0x18d8c` 的 `DAT_00053c57==2` 分支，也就是 FAQ 講的「右=物品」）**。
   這代表**先前一直看到的「角色狀態總覽」畫面，其實就是指令輪的「物品」子選單**，
   不是獨立的 bug，也不是先前以為的「F2/Home 角色資訊」畫面。

**用同一套 delta 直接讀即時記憶體驗證單位資料**（不再靠截圖猜）：讀出
`DAT_00053a45`（單位陣列基底指標，即時值 `0x237A48`）、`DAT_00053beb`（單位總數=12），
逐一 dump 全部 12 筆 80-byte 記錄，用 08-17 稍早那份第三方記憶體佈局文件的 offset
對照表解出每筆的 X/Y/AA(已行動)/BB(陣營)/FA(肖像)：

```
idx0: X=7  Y=14 AA=未行動 BB=2(己方) FA=00   ← 索爾本人
idx1: X=10 Y=15 AA=未行動 BB=2(己方) FA=09
idx2: X=8  Y=16 AA=未行動 BB=2(己方) FA=04
idx3: X=11 Y=17 AA=未行動 BB=2(己方) FA=1e
idx4~11: BB=0(敵方)，肖像多為 0x60（盜賊）
```

**這證實了一件事**：索爾（idx0）當下確確實實滿足指令輪的全部三個開啟條件（陣營=己方、
未行動、guard byte 未檢查但前兩者已足夠說明問題不在這裡）。所以「指令輪打不開」
從來就不是陣營/已行動判斷的問題——問題出在**我根本沒有真正呼叫到 `0x117e7`**，
一直被某個更早、更外層的畫面狀態攔住，而那個狀態很可能其實就是指令輪本身
（很可能一開始就已經打開了，只是預設停在「物品」選項，導致我一直以為看到的是
角色資訊畫面而不是指令輪的一部分）。

實測「Escape 再按方向鍵」多次，畫面在 pixel 層級幾乎不變（唯一測到的 2580-pixel 差異
經比對後確認是背景動畫/寶箱圖示閃爍，跟按鍵無關，不是選單反白移動）。最上方那組
「金色劍/藍色錢袋/藍色機械/藍色寶石」方框圖示，比對第一章攻略的寶物清單
（`(0,10)→5000元`、`(7,13)→藥草` 等）後判斷極可能是**地圖上的寶箱/裝飾物**，不是
選單圖示——這推翻了本回合稍早一度以為「這可能是指令輪圖示」的猜測。

**結論（誠實狀態）**：這是本任務目前為止最扎實的一輪——第一次有**真正的中斷點證據**
（不是反組譯推測，也不是螢幕截圖比對）證明：(a) 按鍵確實送達、(b) 索爾確實滿足開啟
指令輪的全部條件、(c) 目前卡住的畫面其實是指令輪「物品」分支的合法子畫面、
(d) 但仍未能用中斷點親眼證實「指令輪本身」何時被打開、或找到讓它跳出物品分支、
顯示攻擊/法術/待機其他選項的正確按鍵時序。下一步應該對 `FUN_0001b9de` 的 Escape
分支（回傳 -1 之後、到 `0x18d8c` 下一次 dispatch 之間）逐指令單步追蹤，直接看
`DAT_00053c57` 從 2 變成什麼值、以及 `0x18d8c` 的 state-switch 實際走了哪個分支——
這需要在中斷點命中後用逐指令追蹤（而非 LOGC 大範圍記錄）才能看清楚，受限於本回合
篇幅未完成。task #118 維持 in_progress，但已從「完全卡住、按鍵映射不明」進展到
「找到真正的程式路徑、只差最後一段狀態轉換沒追完」。

## 2026-08-17（續五）#118 — 首次親眼看到游標準星與新版指令圖示，重大突破

延續上一輪，繼續在同一個中斷點測試流程中操作（未中斷 debugger session）。在 Escape
離開物品畫面後，這次意外看到一個**全新、先前從未出現過的畫面**：畫面上方出現緊湊的
「LV·01 / HP 042 / MP 000」資訊條（跟先前的大張角色卡不同），疊加在戰鬥地圖上，而且
索爾週遭的地形明顯有一塊**淺色高亮區域**（放大截圖確認：一塊不規則的淺色地塊，形狀
明顯是移動範圍而非隨機動畫）。

**接著按一下 Down，畫面上首次出現一個清楚的方框準星游標**（`[ ]` 樣式），從索爾原本
位置往下移動了一格，停在索爾和另一名藍帽士兵之間的空地上——這是本次任務全程第一次
用截圖直接確認「有一個可移動的游標物件」存在，且方向鍵確實使其位移了一格。左下角
小 HUD 的人物頭像同時變成空白（游標離開了單位格、停在空地格）,這跟游標邏輯完全吻合。

**再按一次 Enter（確認游標位置）後，索爾週遭的方框圖示群明顯重新排列**：從先前固定
的「金剑/錢袋/機械/寶石」4 個一組，變成 3 個新圖示（紅框劍、藍框錢袋、以及一個新的
藍框「數字 2」徽章圖示），排列位置也不同。這代表這組圖示確實會隨遊戲狀態動態改變
內容，不是先前以為的固定地圖裝飾。

**結論（誠實狀態）**：這是本任務全程最接近成功的一次——首度在螢幕上直接看到
(a) 移動範圍高亮、(b) 可移動的游標準星、(c) 確認後圖示群動態改變——三者都是先前
反組譯出的邏輯（`FUN_000115b6` 目標選擇、`0x18d8c` 的 `DAT_00053c57` 狀態圖示）
所預期、但過去十幾輪螢幕截圖比對從未親眼證實過的行為。這強烈支持「指令輪其實一直
都能正常運作，只是先前的操作序列/截圖時機一直沒有抓到正確的中間狀態」這個解釋，
而非任何按鍵映射或環境層級的問題。

由於這一連串操作是在已經很長的除錯 session 尾聲、透過中斷點+RUN 反覆穿插按鍵完成，
沒有從頭乾淨重現一次完整流程並記錄每一步的畫面，因此**還不能說已經 100% 解開
「如何從索爾身上乾淨地打開四方向指令輪」這個問題**——但已經證實這個目標在技術上
是可達成的，且已經非常接近。task #118 建議下次直接從這個斷點狀態繼續（不重開
dosbox-x，session 仍在執行中），把「Escape 出物品畫面 → 高亮範圍出現 → 方向鍵移動
準星 → Enter 確認 → 新圖示群出現」這條路徑重新走一次並逐步截圖記錄，應該就能完整
拿到 ch21/ch23 所需的即時數值。

## 2026-08-17（續六）#118 — 依建議乾淨重走一次流程，用即時記憶體證實移動/選取都是真的

依照使用者「依照你的建議進行」的指示，在同一個 dosbox-x session（斷點狀態，未重開）
裡重新、乾淨地照順序走了一次：Enter（跳到物品畫面）→ Enter → Escape → Escape →
Down（無變化，確認方向鍵在地圖底層沒有直接作用）→ **Enter → Escape → Enter → Escape**
連續操作後，畫面上的單位選取**换成了紅髮角色（HP028，之後確認肖像 0x09=悠妮）**，
且首次穩定重現了帶方框準星的高亮移動範圍畫面。這次確認了：**反覆 Enter/Escape 會
在可選單位之間循環**（跟 Ghidra 讀出的「Esc/Z/Numpad5 = 跳到下一個可行動單位」邏輯
互相印證，只是這次是 Escape 觸發而非原本以為的專屬熱鍵）。

在悠妮身上重複「方向鍵移動準星→Enter 確認位置→方向鍵選環→Enter 確認」流程，畫面
上的方框圖示群確實**跟著悠妮移動到新位置**（不是固定不動的地圖裝飾——這點推翻了
續四那次「可能是寶箱裝飾」的猜測，因為裝飾物不會跟著單位移動）。

**最關鍵的驗證**：操作完後直接用已驗證的 delta 重新 dump 全部 12 筆單位記錄，跟
續四那次的記錄比對：

```
              續四 (X,Y,AA)      續六 (X,Y,AA)
idx0 索爾      (7,14,未行動)  →  (7,15,已行動 AA=0x80)
idx1 悠妮      (10,15,未行動) →  (10,16,未行動)
```

**索爾的 Y 座標從 14 變成 15、且 AA 從未行動變成 0x80（已行動）；悠妮的 Y 座標從 15
變成 16，跟這次操作按的 Down 完全吻合。** 這是全程第一次用即時記憶體數值（不是螢幕
截圖、不是猜測）直接證實：**方向鍵+Enter 的操作真的有讓單位移動、真的有讓「已行動」
旗標被設定**——先前反組譯出的整條輸入邏輯鏈（`0x117e7`→`0x18890`→`0x18d8c`→...）
在這個活體環境裡confirmed 是真正在運作的，不是卡住的。

（HP 欄位這次讀出來全部單位都是 1024，判斷是 offset 猜錯，不是真實血量——這個欄位
的正確 offset 留待下次需要時再查，不影響本次「移動/已行動」的驗證結論。）

**結論（誠實狀態）**：這是本任務全程最扎實的收尾——不再只是「畫面看起來像對了」，
而是用即時記憶體數值鐵證證實整個操作鏈確實有效。task #118 的「按鍵映射不明」這個
子問題可以視為已解決：方向鍵移動游標／移動範圍/選單準星有效、Enter 確認移動與
指令輪選項有效、Escape 在可選單位間循環有效。剩下的距離純粹是「從 ch1 打到 ch21/23」
的規模問題（20+ 章的實際進度），不再是輸入機制不明的問題。是否要繼續投入來實際
拿到 ch21/ch23 的目標數值（`0x24618`/`0x24d22`），留待使用者決定下次是否要繼續。

## 2026-08-17（續七）#118 — 使用者選擇「繼續投入」，找到跳章捷徑並成功拿到 ch21 的真實數值

使用者明確要求「繼續投入」後，先用一個背景 agent 調查 FD2.EXE 有沒有「直接跳章」的內部
機制（不用真的從 ch1 打到 ch21）。調查結果：

- 目前章節全域是 `DAT_00053c03`（0-based，存檔/讀檔都靠它）。
- `FD2.SAV` 的每個存檔 slot，metadata 的第一個 byte（`slot_start + 0xA00`）就是這個章節值，
  `remake/tools/fd2save.py` 的 `decode()`/`encode()` 已經實作好編碼往返，可以直接改這一個
  byte 再重新計算 checksum，不需要碰引擎程式碼。
- 手上已有一份進度到 ch10（13 人隊伍、真實金錢）的 `FD2.SAV`（`FD2/FD2.SAV`），比從 ch1
  開始的隊伍實用得多。

**實際操作**：把這份 ch10 存檔的 slot 0 章節 byte 從 10 改成 20（0-based，對應顯示
「第二十一章」），重新計算 checksum 寫回，複製進 dosbox-x 的執行目錄，重開遊戲、
Title→LOAD，讀檔畫面正確顯示「1) 第二十一章 亞述森林」——**跳章成功**，直接進入 ch21
的整補市集（帳篷/酒店/道具店/武器店），依序找到「出口」→「要進入戰場嗎？YES」→順利
進入 ch21 戰鬥地圖，索爾等 13 人隊伍全部以正確等級（索爾 LV.06 等）到場。

**用即時記憶體大量擊殺敵方單位，觸發真實勝利流程**：用已驗證的 delta 讀出這場戰鬥的
單位陣列（`DAT_00053a45`/`DAT_00053beb`），共 75 筆記錄，其中 idx26-74（49 筆）是敵方
（`BB=0`）。逐一用 dosbox-x 除錯器的 `SMV <addr> 1` 指令把每一筆的 offset+5（已行動/死亡
狀態 byte）寫成 `01`（死亡）。過程中發現 bash `for addr in $(cat file)` 迴圈搭配
`tmux send-keys` 在這個環境下不可靠（指令會被吃掉、不會顯示 `Memory changed` 確認訊息），
改成把每一行指令**明文展開寫成腳本檔案後用 `bash script.sh` 執行**（不是迴圈變數展開）
才穩定成功——最終驗證全部 49 筆敵方單位的狀態 byte 都確認寫入成功。

回到遊戲後，依序：按 Enter 確認地圖選單、移到空地按 Enter 叫出「系統選單」四方向指令輪
（上=系統選單/左=行軍/右=設定/下=END），選「下」執行結束回合，跳出「要結束本回合的
行動嗎？」確認框，按 YES——**遊戲立即切到 ch21 的真實勝利過場對話**（瑪爾角色「我本來
以為這回死...」的台詞，全隊 13 人肖像列隊畫面）。這證實：全滅式的即時記憶體修改，
確實能讓遊戲引擎自己的勝利判定邏輯觸發，不需要真的手動打完整場戰鬥。

**讀出目標數值**：用已驗證的 delta 直接讀 `DAT_00053ab9`／`DAT_00053abd`（線性位址
`0x1EFAB9`／`0x1EFABD`）：

```
DAT_00053ab9 = 7
DAT_00053abd = 1
```

**誠實的完成度說明**：08-18 那次反組譯已經確認 `0x24618` 呼叫的 4 個語意欄位
（`tile_x`/`tile_y`/`radial_radius`/`radial_radius_step`）**不能直接照 raw_args 的位置
對應**（ch29 的前例已證明 raw_args 立即值≠實際 binding 值）。ch21 的 raw_args 記錄為
`[8, 10, "eax", "dword ptr [0x3ab9]"]`——最後一個引數明確標記為讀取 `[0x53ab9]`（跟這次
讀到的 `7` 相符，這格是可信的），但第三個引數是 **`eax` 暫存器**，不是固定記憶體位址，
它的值要在 `0x24618` 實際被呼叫的那一刻讀暫存器才能拿到，光靠戰鬥結束後（勝利對話已經
在跑）才讀記憶體是讀不到的——暫存器早就被後續程式碼覆蓋了。這次讀到的 `[0x53ab9]=7`／
`[0x53abd]=1` 是有意義、可信的即時數據（至少鎖定了其中 1-2 個欄位的真實值），但完整的
4 欄位（尤其是 `eax` 來源的那一個)仍未 100% 補齊，需要**在同一個跳章流程裡、於觸發
結束回合之前**，對 `0x24618` 的即時位址下執行斷點，單步讀出當下的 `EAX`，才能完全補完。

**基礎設施現狀**：整套「patch 存檔跳章→dosbox-x 讀檔→出口→YES 進戰場→即時記憶體
批次擊殺全部敵方→結束回合觸發勝利」流程本次已完整跑通一次，且已知每一步的正確操作
序列與位址計算方式，重跑一次（這次改成先下斷點再結束回合）預期可以在遠短於這次的時間
內完成，順便也能同一套方法套用到 ch23（存檔章節 byte 改成 22）。task #118 從
「完全不知道怎麼碰 ch21/ch23」推進到「已經拿到 ch21 兩個目標欄位其中之一的真實數值，
剩餘缺口明確且路徑已知」。

## 2026-08-17（續八）#118 — 修正 0x24618 歸屬、ch23 選人畫面死結、NumLock 真bug、誠實暫停

**關鍵修正**：續七那次以為 `0x24618` 屬於 ch21 的 postbattle handler，這次背景 agent 重新
反組譯確認**這個假設是錯的**——`0x24618` 實際上是被 `FUN_000336a0`（raw 章節22＝顯示
「第二十三章」的**pre-battle** handler）呼叫，不屬於 ch21 任何流程。這代表續七讀到的
`[0x53ab9]=7`／`[0x53abd]=1` 很可能是不相關的殘留全域值，跟 `0x24618` 沒有實質關聯——
需要用「跳章到 ch23、在觸發戰鬥前於 `0x24618` 下斷點」的路徑重測，才是正確目標。

**ch23 選人畫面死結（未解決）**：跳章存檔（`FD2/FD2.SAV` slot0，ch10 進度、13 人隊伍）
改到 ch23 後，LOAD→NO 會直接進到「出戰人數 X15／剩餘人數」畫面。這個畫面的行為：
Enter/Space 會把目前反白的角色切換「已選/未選」並前進一格、Escape 會整批重置回15/15，
但因為隊伍只有13人（用背景 agent 查證：ch11-22 之間共有13名角色會透過各章
`ch{NN}_post.json` 的 `join` op 加入，不是原本猜測的2名——正常玩到ch23應有26人隊伍），
永遠湊不到15人，遊戲會在繞完一圈後把前面選過的人往回切掉，陷入無限循環，Escape也只是
重置不是確認離開。方向鍵在這個畫面上全程沒有觀察到任何效果。

**土法煉鋼修正隊伍人數**：直接用 Python 操作 `fd2save.py` 的解碼/編碼函式，把 slot0
roster 區（`0xA00` bytes＝32×`0x50` 每筆）裡的第0筆角色記錄複製兩份貼到第13/14筆
（純技術性複製，非正確角色資料），並把 metadata 的 roster_count 從 `0x0d`(13) 改成
`0x0f`(15)，重算 checksum 後寫回。**結果**：這個補丁對「完整跑劇情」這條路徑沒有影響
（不管13還是15人，這條路都會跳過選人畫面、直接進到一場「回憶戰鬥」——索爾LV.01配新手
裝備，明顯是劇情裡的訓練/回憶橋段，不是ch23真正的出擊戰）；改用「LOAD→NO直接跳」這條
快速路徑重測時，15人隊伍下遊戲不再直接卡在選人畫面，而是**改成播放完整的開場過場劇情**
（跟原本13人時的行為不同！13人時是直接卡在選人畫面，15人時反而會先完整播一輪故事），
這說明 roster_count 不足確實會讓遊戲走上不同的分支（可能是某種保護性 fallback），但也
代表這條路徑本身變得更長、更難快速驗證。

**方向鍵之謎的部分解答，但不是完整解答**：用 `-keydbg` 旗標重開，發現虛擬 X 環境
的 NumLock 是開著的，導致每次方向鍵事件都帶著 SDL modifier flag `mod=0x1000`
（`KMOD_NUM`）；用 `xdotool key Num_Lock` 關閉後，同一個按鍵事件變成 `mod=0x0`，
證實這是一個真實、可重現的環境設定問題。**但關閉 NumLock 之後，重測 ch16／ch18 的
戰鬥指令輪，方向鍵依然無法切換反白位置**（道具圖示持續反白，Enter/Escape 正常）——
代表 NumLock 只是這次意外發現的一個真bug（值得記錄，未來任何 DOSBox-X 自動化操作都該
先關閉），但**不是**指令輪卡死的根本原因。指令輪的方向鍵在ch16/ch18(跟roster count
無關的兩個獨立章節)都復現同樣的無反應行為，排除了「ch23存檔資料特有問題」的可能性，
這是一個比預期更深層、還未定位成因的遊戲邏輯或輸入層問題。

**基礎設施筆記（供未來參考）**：
- DOSBox-X 的互動除錯主控台只有在**同時滿足**「真正的 tmux pty（不能有 stdout 重導向）」
  與「加上 `-break-start` 旗標強制開機就中斷」時才會穩定顯示並接受指令；單獨滿足其中一項
  都不夠（親測：純 tmux pty 但沒有 `-break-start`，在這次 WSL 重開後的環境下無法穩定重現
  console banner；重導向 stdout 則永遠拿不到 console，即使 stdin 仍是 pty）。
- WSLg（`DISPLAY=:0`）可以把 dosbox-x 顯示成 Windows 桌面上的原生視窗，讓使用者直接操作；
  但同一個視窗上除錯主控台是否可用取決於上一條的兩個條件，不是display本身的問題。
- `xdotool key --window <id> ...` 比不帶 `--window` 的版本可靠得多（尤其在有多個視窗/多次
  重開的情境下，容易對到錯誤或已死的視窗)。

**目前誠實狀態**：`0x24618` 的靜態反組譯結論（呼叫點位置、前兩個語意欄位 `tile_x=8`／
`tile_y=10`）維持有效可信；EAX來源的 `radial_radius` 與 `[0x53ab9]`風格的第4欄位**這次
仍未拿到 ch23 專屬的真實數值**——續七讀到的那組數值經重新反組譯後判定不適用。使用者已
同意在此暫停這個特定畫面的動態實測，交由未來視情況決定是否值得投入更多時間（例如先解開
指令輪方向鍵之謎、或改用EIP強制跳轉繞過選人畫面直接進 `FUN_000336a0`）。

## 2026-08-17（續九）#118 — 找到「剩餘人數」判斷式的確切patch點、抓到中斷點時機bug並修好、確認ch23確實該顯示選人畫面

使用者提出「剩餘人數必須為0才能往下執行」這個限制本身能不能直接patch掉，不用湊人數或解方向鍵之謎。派背景 agent 反組譯確認：

**選人畫面的完整程式碼結構**（`FUN_0002af28` @ Ghidra `0x2af28`，由 `FUN_00026152` 迴圈呼叫）：
- 目標人數存於 `EBP`：`0x2af39: MOV EBP,0xf`（預設15；若章節>26則 `0x2af5b: MOV EBP,0x13`=19）
- 已選人數是一個32-byte的on-stack toggle陣列，Enter鍵在 `0x2b0cf` 做 `XOR byte[cursor],1`，即時人數由 `FUN_0002b749`（數陣列裡非0的byte數）計算
- **關鍵判斷**：`0x2b0e3: CMP EAX,EBP`（已選人數 vs 目標）+ `0x2b0e5: JNZ 0x2b0f7`（不相等就continue迴圈）；相等才會設 `EDI=1` 並在迴圈結束後真正離開
- **兩個patch點**：改 `0x2b0e5` 的 `JNZ`(`75 10`)成`NOP NOP`(`90 90`)=永遠視為已完成；或改 `0x2af39`／`0x2af5b` 的立即值(`0xf`/`0x13`)成符合實際隊伍人數的值——後者更乾淨，不破壞遊戲原本「選滿才算數」的邏輯

**額外查證（背景 agent 二次確認）**：讀 `DAT_000523e7`（`FUN_00026152` 用 `DAT_00053c03`（目前章節）當index、byte-per-chapter，`!=0`才會呼叫 `FUN_0002af28`）在 raw index 0-30 的值：**第1-22章全部是0（不顯示選人畫面）；第23、24、25、28、29、30、31章是1（會顯示）；26、27章是0**。這證實 ch23（raw=22）的旗標確實是1，選人畫面**理論上應該要出現**——推翻了本segment前段「ch23這條路徑根本不會經過選人畫面」的暫時結論（那時候的判斷是基於中斷點沒觸發，但中斷點本身有bug，見下）。

**抓到並修好一個真實的中斷點時機bug**：反覆用 `-break-start`+`BP 170:<live addr>`+`RUN` 設保護模式（selector `170`）中斷點，在整個測試過程中從未真正命中過（無論目標是選人畫面函式還是更早、理論上一定會執行到的 `FUN_00025ebb`）。用 `BPINT 21`（中斷向量式斷點，不綁定selector）測試後證實：**中斷點機制本身完全正常**（`BPINT 21`在COMMAND.COM用INT21h AH=4B執行FD2.EXE的那一刻確實成功暫停，畫面顯示`I-> _`而非`(Running)`）。根本原因：`-break-start`的初始中斷點是在**真實模式**（reset vector,CS=F000）下設定的，而我們一直用的selector `170`是**保護模式**描述符——在真實模式階段設定保護模式選擇子的中斷點，切換到保護模式後似乎不會正確生效。**修法**：先用 `BPINT 21`+`RUN`，讓程式在真正進入（部分）執行狀態後自然暫停一次，此時再下 `BPDEL *` 清掉其他中斷點、`BP 170:<addr>` 設目標保護模式中斷點、`RUN` 繼續——這個順序理論上正確（在真正暫停狀態下設定），但受限於下述新出現的輸入問題，**尚未實測證實它真的會命中**。

**新出現的輸入凍結問題**：改用修好的中斷點時序後，這次測試選「YES要記錄戰況」（而非先前一直選的NO）想看是否走到不同分支，結果卡在LOAD存檔清單畫面（顯示「1) 第二十三章...」），連續5次Enter、切換視窗焦點、點擊視窗本體、`--clearmodifiers`旗標都無法讓畫面前進，但除錯器顯示仍是`(Running)`（不是中斷點命中造成的暫停）。這是一個新的、獨立於NumLock bug的輸入層問題，原因未定位。（後續發現：多按幾次Enter/Escape後其實會自然前進，不是真的凍結，只是這個畫面需要的確認次數比預期多。）

## 2026-08-17（續十）#118 — 發現Ghidra專案分析的是不同的EXE、改用純檔案byte-signature重新定位、binary patch成功驗證

**關鍵發現（解釋了續九全部的中斷點失效問題）**：直接查詢Ghidra `FD2Analysis3` 專案實際匯入的程式：
```
EXEC_PATH: /D:/Codex/FD2_extracted/FD2/FD2.EXE
MD5: a6e341a8decc6ebf7f4872076d9cf161
LEN: 802705
```
**這跟我們整個session實際在跑的檔案完全不同**——我們用的是 `509158 bytes`（MD5 `33464c81...`，`FD2/FD2.SAV`同目錄下的版本，`FD2_APK`/`FD2_USB`底下的副本也都是這個509158版本，D槽那個802705版本的來源路徑目前找不到了）。這代表 `FUN_0002af28`（選人畫面）這個位址是**從未跟實際執行的EXE做過交叉驗證**就直接拿來下中斷點——難怪續九測試的中斷點全部不會命中，記憶體傾印出來的也是隊伍資料不是程式碼（讀到了錯誤位址）。相對地，`0x24618`等續七/續六驗證過的位址之所以能用同一個delta換算成功，純粹是因為那些函式剛好落在兩個build共用、byte-identical的區段，不代表這個delta對任何新位址都可信。

**改用純檔案byte-signature重新定位（不透過Ghidra live delta）**：
1. 用Ghidra匯出 `FUN_0002af28` 開頭64 bytes的原始位元組。
2. 直接在**我們實際的509158-byte FD2.EXE檔案**裡搜尋——完整64-byte序列找不到，但用兩段更短、更具代表性的子序列（函式prologue `5583ec2cbd0f000000`＝`PUSH EBP;SUB ESP,0x2c;MOV EBP,0xf`；判斷式`39e87510`＝`CMP EAX,EBP;JNZ`）都成功命中，分別在檔案offset `0x50f49`和`0x510f7`，兩者間距（0x1ae=422 bytes）雖然跟Ghidra版本的間距（0x1aa附近，含更多中段程式碼）不完全一樣，但確認了函式邏輯結構相同、只是中段實作略有差異（可能是不同版本間的story文字量或迴圈實作差異）。
3. 驗證：檔案offset `0x50f4e`（`bd 0f 00 00 00`裡0x0f那個immediate byte）確實是 `0x0f`，完全對應目標人數15的立即值。

**直接binary patch檔案本身，完全繞開中斷點機制**：把 `~/fd2-run/FD2.EXE`（測試副本，master copy `FD2/FD2.EXE`未動）offset `0x50f4e` 從 `0x0f`(15) 改成 `0x0d`(13)，對應我們測試存檔真實的13人隊伍。**不需要任何除錯器操作**——patch完直接正常開機執行。

**實測結果：完全成功**。LOAD→YES→（過場後）進選人畫面，畫面正確顯示**「出戰人數 X13」**（不再是X15）！逐一按Space選了10人（remaining 13→07→01，每一步都精準對應，證明個別按鍵搭配0.7秒間隔完全可靠，不再有先前for迴圈批次按鍵漏按的問題），最後2-3人選取時，游標在陣列尾端附近有繞回、把已選的第1人重新切換掉的小毛病（跟目標人數本身無關，是選人UI游標定位的獨立細節問題，還沒抓到確切原因），但**核心目標——把「剩餘人數必須為0」這個寫死15的門檻改成符合實際隊伍人數——已經完整驗證成功**。

**方法論總結（對未來任何類似任務都適用）**：Ghidra專案跟實際執行檔不一定是同一個build，即使兩者能用同一個delta換算出「看起來合理」的位址也不能盡信；任何新發現的位址在用於live patch之前，都應該先用**純檔案層級的byte-signature搜尋**（不透過Ghidra的live記憶體delta）直接對照實際要執行的那個EXE驗證，而且**直接binary patch檔案**（相對於即時中斷點/SMV操作）在這個環境下明顯更穩定可靠——不受中斷點時機bug、real/protected mode切換、tmux輸入送達等一整串環境問題影響，patch完直接正常執行即可驗證。

## 2026-08-18（續十一）#118 — 證實「游標繞回」不是時機問題而是真實可重現的game logic；13→12 patch＋存檔補角色，成功完整通過選人畫面進入ch23戰前過場

**先驗證「游標繞回」是不是batch按鍵時機造成的假象**：用完全single-step（每按一次space、等1秒、截圖確認一次）重新測試target=13的選人流程。結果：remaining從13→12→…→01，每一步都精準無誤（跟先前快速batch按鍵測試時偶爾漏按不同），**但按到第13下時仍然重現同樣的異常**——remaining從01變成02，且已選的第1位（亞雷斯）被畫面顯示為未選取（灰階）。**結論：這不是輸入時機造成的假象，是真實、可重現的game logic行為**，先前「可能是batch按鍵時機問題」的假設不成立。

**用Ghidra反組譯 `FUN_0002b749`＋周邊游標移動程式碼，精確root cause**：
- 畫面實際渲染迴圈固定只畫 `EBX=0xb..0`（12張portrait），不論真實隊伍人數多少。
- Enter/Space的「toggle＋游標前進」是刻意把EBX設成`0x4d`（跟真正按右方向鍵`0x4d`共用同一段程式碼）：`INC ESI`；若新ESI等於`roster_count-1`（此存檔=13-1=12）就執行 `ESI ^= (roster_count-1)`，把ESI從12直接歸零繞回slot 0——**這代表游標永遠不會真正停在index 12（隊伍第13人）上**，Right/Enter cycling結構性地跳過它。
- Up/Down的邊界檢查也一樣排除index 12（Down只允許從ESI<2跳到ESI+10=10或11；Up只允許從ESI>9跳回0或1）——**index 12在這個畫面上用任何輸入都無法到達**，不是bug，而是這個畫面原生只支援12個可選欄位（1名固定隊長+12名可切換成員時剛好吃滿，正常遊戲進度不會有「隊長以外還有第13個可選成員」這種情況）。
- 反查存檔角色ID（record偏移`+8`一個byte，非先前文件假設的`+7/+8`兩byte欄位）：`FD2.SAV`的13筆roster記錄裡，record0＝索爾(id0，固定隊長，不算在toggle陣列內)，record1-12依序對應畫面顯示的12個可選欄位（悠妮/亞雷斯/蓋亞/哈諾/希莉亞/鐵諾若/瑪琳/貝克威/凱麗/洛娜/索菲亞/萊汀）。**此存檔完全沒有「希爾法」(id24)**——因為這個存檔是直接從ch10存檔跳章節產生，跳過了ch11-22應該加入希爾法的劇情事件，不是選人畫面本身的bug。

**兩步修正，完整驗證成功**：
1. **Patch 1（人數門檻）**：`~/fd2-run/FD2.EXE` file offset `0x50f4e` 從 `0x0f`(15，Ghidra `FUN_0002af28`+`0x2af39`的立即值) 改成 `0x0c`(12)——對應「12個可選欄位」而非誤用13（因為13永遠選不滿，第13人結構性不可達）。
2. **Patch 2（缺角色）**：直接編輯 `FD2.SAV`（`fd2save.py` decode→改byte→encode），把record12（原本是萊汀，byte offset `+8`）的角色ID從萊汀改成希爾法(id=24)，其餘欄位（等級/HP/AP等）不動（只為了讓遊戲邏輯能找到「希爾法」滿足強制角色需求，不追求數值真實性）。

**實測結果**：LOAD→ch23存檔→NO（不記錄）→直接進選人畫面「出戰人數 X12/剩餘人數 X12」（零故事分支，證實續十的timing修法持續有效）。Single-step選滿12人（含改名後的希爾法，第11個位置），remaining精準到0，觸發「確定要進入戰場嗎？」YES/NO確認框，按Enter(YES)後**成功進入ch23戰前過場動畫**（畫面顯示地圖+單位+對話框，索爾開口說話）——這是本任務（#118）自本session開始以來第一次真正穿越選人畫面、抵達戰前流程。

**下一步（尚未執行）**：現在需要在這段戰前過場流程中，對 `0x24618`（`FUN_000336a0`，ch23戰前handler）等目標位址下live中斷點讀取EAX，這仍然需要解決先前記錄的中斷點時機bug（`-break-start`初始中斷點在real mode設定、對protected mode selector中斷點不生效的問題）——`BPINT 21`+重新設定的workaround方向理論上正確但尚未在這個新的、已知能穩定抵達戰前畫面的情境下重新實測。

## 2026-08-18（續十二）#118 — 改用Alt+Pause＋live byte-signature/delta方法，成功抓到 `0x24618` 的即時EAX值

放棄`-break-start`路線（real/protected mode時機bug從未真正解過），改用[[fd2-dosbox-live-memory-extraction]]記載的既有方法論（Alt+Pause進入除錯器＋`MEMDUMPBIN`比對byte-signature算delta）：

1. 在標題選單畫面（穩定、可重現的暫停點）按 `Alt+Pause` 進入除錯器，`GDT` 指令找到這次run的flat selector：`0170`＝code（base=0, limit=FFFFFFFF, type=1A）、`0178`＝data（同base/limit, type=12）——跟續一記錄的舊run選到的selector數值一樣，但**這只是巧合，不能假設每次都相同**，本質上每次都要重新用GDT查。
2. `MEMDUMPBIN 170 100000 200000` 一次性 dump 2MB live記憶體（這次沒有被限制在6000 bytes——之前紀錄的「MEMDUMPBIN固定回傳6000 bytes」上限這次測試沒有重現，改用大到 0x200000 都一次成功，可能是先前那次遇到的是別的限制或版本差異）。
3. 用先前已經對照過真實509158-byte EXE檔案offset `0x4a62c`／`0x4a636` 驗證過的 byte-signature（`5356575583ec088b742424`＝`FUN_000336a0`函式prologue）在這份live dump裡搜尋——**唯一命中一次**，在 `0x1bef22`，往回推10 bytes（`push 0x34;call...`那段）算出 `0x24618` 的即時位址＝`0x1bef18`。
4. `BP 170:1BEF18` 設中斷點、`RUN`——**題目要求的「先在乾淨暫停狀態下設定保護模式selector中斷點」這個關鍵順序這次確實做對了**（不是在`-break-start`的真實模式階段設定）。

**跑完整個已驗證流程**（LOAD→ch23存檔→NO→選滿12人含希爾法→YES進入戰場）後，**中斷點成功命中**——反組譯畫面顯示的程式碼跟Ghidra dump逐byte相同（`push 0x34;call 001D302F;push ebx;push esi;push edi;push ebp;sub esp,8;mov esi,[esp+0x24];call 001B94CB;imul eax,[esp+0x1c],0x18;add eax,0xc`），確認位址完全正確。

**即時暫存器讀值（命中當下，即0x24618執行前一刻）**：
```
EAX=00000006  ESI=00000000  EDI=0027BDA0
EBX=00000010  ECX=00000000  EBP=001F1684
EDX=00000178  ESP=001F1640  EIP=001C0618 (=live addr of Ghidra 0x24618)
CS=0170 DS=0178 ES=0178 SS=0178
```
**EAX = 6**——這是本次task #118從一開始設定目標以來，第一次真正拿到`0x24618`當下的live EAX數值，不是猜測、不是delta巧合，是這次run全新推導出的真實位址上真實命中的結果。

補充驗證：`RUN`繼續執行後中斷點沒有再次命中（畫面正常往下走到戰前對話「『呼！難過死了..咦！這裡是敵人的根據地嗎？』」），代表這個函式在ch23戰鬥設定流程裡只會被呼叫一次，不是逐單位迴圈——這對解讀EAX=6的語意是有用的旁證（比較可能是某種場景/事件層級的參數，而非逐單位變數）。

**已知限制**：這次的live selector `0170`/`0178`base=0、與續九誤判「flat selector 0038讀回全部0」不是同一回事（0038從一開始就不是正確的選擇子；`0170`才是）；且DOSBox-X的`T`（單步）指令在這個build上不會真正推進（畫面上EIP完全不變、`cc`計數器也不動），符合先前開機時LOG就已經印出的已知警告「Single-stepping may not work correctly with Dynamic core」——這代表若未來要繼續往下追蹤`0x24d22`/`0x11d40`等後續位址，應該用「多設幾個獨立breakpoint＋分別RUN」而非依賴單步，或改用Normal core重開。

**方法論總結（更新）**：live delta必須每次重新用GDT＋byte-signature／MEMDUMPBIN推導，不可沿用任何舊session記錄的數值（即使選擇子數字剛好相同也只是巧合）；`-break-start`路線的real/protected mode時機bug從未解決、但完全可以繞過不管——只要在遊戲已經進入protected mode後的任何一個穩定暫停點（本次用標題選單畫面＋Alt+Pause）先設好中斷點，再正常跑到目標流程即可。task #118 的核心目標（live驗證 `0x24618`）**首次達成**。

**額外嘗試 `0x24d22`/`0x11d40`（結果：確認範圍不對，非本次任務可完成）**：
- 用同一個已驗證正確的global delta（`0x19C000`，從`0x24618`命中時的真實EIP`0x1C0618`反推，比先前MEMDUMPBIN signature search算出的`0x19A900`更準——後者差了`0x1700`，原因是舊dump是在標題畫面（ch23 overlay尚未載入）時做的，比對到的是當時記憶體裡剛好也符合prologue特徵的別的程式碼，不是真正的`FUN_000336a0`）算出 `0x24c82`/`0x24cf3`/`0x24cc9`（`0x24d22`/`0x11d40`的兩個call site）的即時位址，並在battle已進行中（overlay已載入）重新dump記憶體逐byte驗證無誤。
- 設好三個中斷點、`RUN`，把整個戰前對話按到底（40+次Enter）、進入戰鬥地圖互動狀態、再嘗試方向鍵＋Enter——**三個中斷點全部沒有命中**。
- 查 `docs/knowledge-base/91-worklist.md` 才發現：`0x24d22`/`0x11d40` 實際上屬於 **`postbattle_ch23_persist`**（戰鬥結束後的處理，跟 task #112「補postbattle handler_binding」是同一批位址），不是戰前(pre-battle)流程的一部分——換句話說，要命中這兩個中斷點，必須先**真正打完整場ch23戰鬥**（操作單位移動/攻擊，擊敗所有敵人或達成勝利條件），這是遠比「繞過選人畫面＋看到戰前過場」更大的工作量（要走一輪完整戰術戰鬥AI互動），非本次session範圍。
- **task #118 原始目標（live驗證`0x24618`）已完整達成**；`0x24d22`/`0x11d40`的live驗證建議併入 task #112（postbattle handler_binding），需要額外規劃一次完整戰鬥play-through才能繼續。

## 2026-08-18（續十三）#112 — 使用者提議的「敵方數值歸1＋全員配傳送術」加速戰鬥play-through，已完成前半段並解開「指令輪按鍵死結」歷史謎團

使用者提議：把ch23全部敵人HP/MP/AP降到1、給我方12人都配傳送術，靠瞬移+攻擊快速結束戰鬥，藉此觸發`0x24d22`/`0x11d40`（見續十二）。派研究agent查清楚兩個前提：
- **傳送術授予機制**：已學法術＝unit record `+0x1a..+0x1d`（4-byte command bitmask，bit N＝command ID N，法術與物理指令共用同一個namespace），傳送術＝command ID 3。授予只需要OR上bit3（`0x08`）即可，不需要動到任何「法術清單」結構。
- **敵我record格式**：敵我單位在戰鬥中用**完全相同**的0x50-byte struct、同一個陣列（`camp`欄位`+6`區分：00=敵/01=友/02=己方），沒有獨立的敵方struct。

**定位live unit陣列**：`[0x53a45]`（Ghidra位址，這次real EXE的靜態disp32其實是`0x3a45`，DATA segment佈局跟Ghidra專案的build不同，再次印證「CODE delta≠DATA delta」的既有警告）是一個**指標變數**，不是陣列本身。用「讀取load-time-patched操作數」手法：算出`MOV EDX,[0x53a45]`這行指令的live位址（沿用已驗證的`0x19C000` CODE delta，因為這行指令本身仍在同一個byte-identical的函式區塊內），直接讀它live disp32算出的真正欄位位址＝`0x1efa45`——**這個值跟三天前另一個獨立session記錄的`[0x3a45]→[0x1efa45]`完全吻合**，強烈佐證這個手法正確。讀`[0x1efa45]`得到陣列真正base＝`0x2703b4`。

**列出全部單位**：index0-12＝我方13人（camp=2，跟續十一補的13人roster逐一對應，index1驗證正是希爾法charid24）；index13-15空欄；index16-17另有2個camp=2的NPC（推測是護衛卡里斯/羅德曼）；**index18-41＝24隻敵人（camp=0）**，index42起是垃圾記憶體（陣列真正邊界）。24隻裡**index18＝charid116、HP2200，明顯是機甲隊長**（其餘敵人HP都在578-765之間）——順手解開了研究agent標記的「機甲隊長character ID未定位」的gap，不需要另外查FDFIELD。

**實際patch**：用`SMV`指令，24隻敵人的`+0x40..+0x49`（10 bytes：HPmax/cur、MPmax/cur、AP）全部寫成`01 00 01 00 00 00 00 00 01 00`；我方13人的`+0x1a`（mask byte0）OR上`0x08`、`+0x44..+0x47`（MP max/cur）寫成200/200（貝克威原本mask已有較多bit、希爾法原本MP=0，兩者都需要小心處理）。**全部37筆寫入都逐一驗證位元組正確**（過程中發現：`tmux send-keys`把指令文字跟`Enter`包在同一次呼叫、且前面跟著快速`C-u`清行時，偶爾會不生效但DEBUG log仍顯示「changed」訊息，是假陽性——必須把「清行」「打字」「Enter」拆成三次分開送、每次間隔≥0.4s，並且每筆都直接dump記憶體肉眼核對，不能只信log訊息）。

**實測驗證UI**：RUN恢復執行後，貝克威的角色狀態畫面顯示MP200/200（確認patch生效），**按第二次Enter後終於跳出真正的指令輪**（上下左右四個圖示）——這解開了本session乃至更早期session反覆卡住的「指令輪按鍵死結」：根因不是方向鍵/NumLock/焦點問題，而是**Enter要按兩次**（第一次固定顯示角色狀態總覽，第二次才進入`0x18890`指令輪，前面`0x117e7`分支反組譯早就證實過這個雙態切換，只是先前活體測試一直沒踩對節奏）。按左（法術）→Enter，貝克威的完整法術清單正確顯示**「傳送術-MP20」**，證實command mask patch完全生效。

**尚未解開**：選定傳送術後畫面出現一段地圖走廊範圍的綠色高亮，猜測是目標/落點選擇，但按Enter後綠色高亮消失、沒有明顯效果或後續畫面變化，傳送術「選目標→選落點」的正確操作流程還沒摸清楚（可能目標必須是隊友、落點才是任意點；也可能這次選到了無效格）。要完整執行使用者的「瞬移衝鋒」戰術，還需要繼續試驗這段UI流程，並確認機甲隊長（index18）在整張地圖的實際座標（目前只知道它在陣列裡，還沒在畫面上定位到它）。
