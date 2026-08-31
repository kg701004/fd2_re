# 92 — M5 正常玩法(無 debug hook)多章節逐章驗證紀錄

> 對應 `docs/knowledge-base/91-worklist.md` M5「正常玩法可達性驗證」項目與
> `C:\Users\kg701\.claude\plans\hazy-crunching-liskov.md` Phase 4。本文件記錄**第一次
> 真正用鍵盤輸入從頭玩 remake 自己(不是 DOSBox-X 原版)、完全不掛任何
> `FD2_SHOT_*`/`FD2_CAMP_*` debug 捷徑**的驗證 session。方法論與工具沿用
> `98-tooling-infrastructure.md`「remake 側 xdotool 合成鍵盤輸入可靠性」一節的「可靠流程」。

## 方法(本輪實際操作)

- WSL2 Ubuntu,全新獨立 Xvfb `:970`(`1400x900x24`,與本專案所有其他 canonical/harness
  instance——`:99`/`dbg`/`diffharness`/`:897`/`:898`/`:955`——都不重疊)。
- `remake/fd2-linux-verify` 從當日 HEAD 重新建置(`GOOS=linux GOARCH=amd64 go build -o
  fd2-linux-verify ./cmd/fd2`),確認比對 commit hash 比 main.go 最新改動新鮮。
- 啟動指令**完全等同 `play.sh`**:只設 `FD2_CAMPAIGN=assets/scenarios/campaign_full.json`
  + `FD2_MUTE=1` + 三個 `FD2_ORIGINAL_*`(原版素材路徑),沒有任何 `FD2_SHOT_*`/
  `FD2_CAMP_PREP_BATTLE`/`FD2_CAMP_NODE`/`FD2_CAMP_CLASS_FIXTURE`。
- 每次都用 `xwininfo -root -tree` **當場重查**視窗 id(doc98 記錄的「沿用舊 id 會靜默
  吞鍵」陷阱本輪確認未再踩,全程單發按鍵+screenshot 確認再送下一鍵,批次時每鍵間隔
  0.15-0.3s)。
- 全程同一 turn 內同步輪詢,沒有背景丟給下一輪自動恢復。

## ch01(初試身手)——本輪逐章驗證的唯一一章,但過程中發現並修復一個會擋住*每一章*的真實 bug

**截圖**(`docs/figures/`,依時間順序):
`m5-play-ch01-00-title.png`(標題畫面)→
`m5-play-ch01-01-intro-dialogue.png`(序章對白,索爾)→
`m5-play-ch01-02-enemy-phase-banner.png`(Tab 觸發 ENEMY PHASE 橫幅)→
`m5-play-ch01-03-false-defeat-bug-prefix.png`(**修復前**:Tab 後幾乎立即出現的虛假敗北畫面)→
`m5-play-ch01-04-combat-animation.png`(真實攻擊確認:亞雷斯 vs 盜賊戰鬥剪影動畫)→
`m5-play-ch01-05-damage-number.png`(傷害數字「亞雷斯 攻擊 盜賊,造成 21 傷害」)→
`m5-play-ch01-06-postfix-no-defeat.png`(**修復後**:同樣 Tab 結束回合,敵人逼近但不再誤判敗北,四名隊員全部存活)→
`m5-play-ch01-07-turn3-survived-postfix.png`(**修復後**:連續存活到第 3 回合,證實非單次僥倖)。

### 系統性驗證清單(全部透過真實 xdotool 按鍵確認,非程式碼閱讀猜測)

| 項目 | 結果 |
|---|---|
| 標題畫面→START→序章對白(王座廳/王城/比劍/發現悠妮蓋亞/行軍) | 正常渲染、Enter 正確逐句推進,約 80-150 次 Enter(遠少於 DOSBox-X 的 ~800,remake 每鍵即跳整句而非逐字) |
| ch01 戰前部署對白+盜賊宣戰對白 | 正常渲染 |
| 移動游標(方向鍵) | 每鍵精確移動 1 格,相機正確跟隨 |
| 選取單位→顯示移動範圍 | 正常(範圍大小與 Phase 3 剛修好的 MV 數值吻合,未見異常大/小) |
| 指令環(攻擊/法術/物品/待機) | 開啟正常;預設焦點在「法術」(index1)非「攻擊」(index0),與 `main.go:7568` 附近註解「opening defaults to selection=1/spell」一致 |
| 指令環 native 資料驅動的可用性檢查 | 真實驗證到 `nativeActionSelectable()` 會依原版 FDOTHER availability word 擋下不可用指令,顯示「此指令目前不可用」——這是忠實原版行為,不是 bug |
| Tab 結束回合 | 100% 可靠觸發「ENEMY PHASE」橫幅,`main.go:6722` 的無條件 `endTurn()` 綁定確認在真實輸入路徑下正常 |
| 敵方 AI 回合 | 正常執行(單位移動、逼近) |
| 真實攻擊(移動到鄰格→開環→攻擊→選目標→確認) | 成功一次:亞雷斯(Ares)攻擊「盜賊」,螢幕正確顯示戰鬥剪影動畫(雙方 HP 條+姓名)與「亞雷斯 攻擊 盜賊,造成 21 傷害」——AP26 vs DP2 敵人算出 21 點傷害,數值合理,證實 Phase 3 的 AP/DP 修正在真實戰鬥中確實生效 |
| Escape 逐層退回 | 確認:環→取消攻擊目標選擇回環;已移動的單位環→退回移動前位置;未移動的單位選取→取消選取 |
| 撤退/重試迴圈(敗北後) | 修 bug 前驗證了 3 次:「撤退!先回頭整頓,再找機會反攻……」對白播完後乾淨重跑整個 ch01 開場(含序章對白),無崩潰無卡死 |

### 發現並修復的真實 bug:`applyPersistentStats` 誤把角色姓名當「持久化狀態」複製,導致每場戰鬥開局即誤判敗北

**症狀**:連續 3 次嘗試(含刻意把索爾撤到最遠角落單獨待命)都在按下 Tab 結束玩家回合、
敵方 AI 甚至還沒真正行動的瞬間就跳出「敗北」畫面。

**根因**(用臨時 `FD2_DEBUG_RESULT=1` debug log 追出,非猜測——完整追蹤鏈記錄如下):
1. `internal/battle/event.go` `PartyUnits()` 從 `ch01.json` scenario 的 `party` 陣列正確建構
   出 `Name:"索爾"` 等 4 個具名單位(log 證實)。
2. 這些單位被 append 進 `g.storyActors`,經 `applyLoadCH()`(`cmd/fd2/main.go:1830`)的
   `seedPersistentPartyFromLoadCH()` 路徑,把「目前這份正確具名的單位」餵給
   `materializeNativeJoinPersistentUnit()`——這個函式的 `unit := base` 起手式雖然保留了
   `base.Name`,但產物存進 `g.partyRoster[fig]`,而 `g.partyRoster` 一旦在遊戲開場(序章
   對白流程本身也會呼叫 `applyLoadCH`)被填入任何一筆記錄後,就會讓後續**每一次**
   `applyLoadCH`(包含 ch01 自己的 pre-battle loadch)都走進
   `if len(g.partyRoster) != 0 { g.applyPersistentParty(...) }` 分支。
3. `applyPersistentParty()` 對每個 Own 單位用 `g.partyRoster[dst.Fig]` 查表,呼叫
   `applyPersistentStats(dst, src)`——這個函式**無條件**執行
   `dst.Name = src.Name`,把剛剛(2)才正確建好名字的單位,用同一個 `g.partyRoster`
   查表結果覆寫回去。矛盾點:log 證實 `g.partyRoster` 裡對應 fig=0/4/9/30 的 entry 其實
   本身 Name 就是空字串(entry 的來源鏈——native JOIN constructor 的位元組重建——完全沒有
   「人類可讀姓名」這個概念,天生只會產生 `""`)。淨效果:每次 `applyLoadCH` 都把正確
   姓名洗成空字串。
4. `checkResult()`(`main.go:5729`)寫死 `protect := []string{"索爾"}`,用
   `u.Name == "索爾"` 找存活單位——找不到任何 Name 非空的 Own 單位,`Result()`
   立刻回傳 `"lose"`,**與索爾實際 HP 完全無關**(debug log 直接證實:索爾當時
   HP 42/42,滿血,但因為場上沒有任何 unit.Name=="索爾" 而誤判敗北)。

**修復**:`applyPersistentStats()` 移除 `dst.Name = src.Name` 這一項複製(`ClsName`/
`ClassID`/`Lv` 等其餘欄位維持原樣持久化——姓名跟這些不同,是每章 scenario 自己的
`party` 綁定就會正確供應的靜態身分,不需要、也不該被「持久化狀態轉移」覆寫)。

- Commit `faecef3e`(`battle: fix false-positive defeat -- persistent stats sync was
  erasing unit names`)。
- `go build`/`go vet`/`go test ./...` 全綠(含 `cmd/fd2` 完整重跑,約 95 秒),無回歸。
- **修復後用同一套全新 no-debug-hook 流程重播確認**:同一場 ch01 戰鬥,同樣的部署,
  按 Tab 結束玩家回合後**不再誤判敗北**——連續驗證 3 個完整回合(2 次 ENEMY PHASE
  banner + 2 次敵方 AI 實際行動 + 2 次正確返回玩家回合),索爾、亞雷斯、悠妮、蓋亞
  全數存活,無任何虛假 lose 觸發。

**這個 bug 的影響範圍遠不只 ch01**:`applyPersistentStats`/`applyPersistentParty` 是
每一章 `applyLoadCH` 的共用路徑,`checkResult()` 的「索爾死亡」判定是**每章通用預設**
(`main.go:5729` 附近註解「索爾是每章通用預設,永遠檢查」)。這代表修復前,**任何一次
真正從頭玩、經過序章對白建立 `g.partyRoster` 之後的正常遊玩,理論上每一章開局
Tab 一下都會立刻誤判敗北**——這正是為什麼「用正常輸入完整玩過哪怕一章」在這個專案
的整個歷史上從未真正發生過:所有先前的即時驗證都是用 `FD2_SHOT_*`/`FD2_CAMP_NODE`
直接跳到目標畫面,從未走過序章→ch01 這條會讓 `g.partyRoster` 第一次被填入的真實路徑。

### 已知的、與這次 bug 無關的次要發現(記錄但不視為阻擋)

- **指令環輸入節流**:剛開啟指令環的頭幾幀,方向鍵/Enter 有時不會立即生效(需要
  額外 0.3-0.5s 真實 wall-clock 等待才會被讀到)——與 doc98 續一記錄的「
  church UI 動畫節流」是同一類方法論教訓(`drawRing`/`beginActionOverlayOpen`
  很可能有類似的「至少要真的 Draw 過一次才前進」節流),只是這次節流對象是戰鬥
  指令環而非 church 選單轉場。**不是 bug,不需要修**——真人在 60fps 下不會注意到,
  只有工具化的快速連續按鍵會踩到;下一輪操作指令環時,每次方向鍵切換後留
  0.4-0.6s 再送下一鍵即可穩定重現。
- **視覺上的鄰格 ≠ 邏輯上的鄰格**:這個 diamond/brick-tile 美術風格下,螢幕上看起來
  緊貼的兩個 sprite 不保證在邏輯網格上真的相鄰(可能相差 1-2 格,或武器
  `atk_min`/`atk_max` 排除了看起來很近但實際射程外的目標)。本輪多次在「看起來
  貼在一起」的位置嘗試攻擊卻收到「此指令目前不可用」,最終只在精確算過 own_deploy
  座標的位置成功攻擊一次。**這不是新發現的 bug**——`docs/knowledge-base/
  51-remake-playtest-gaps-r2.md`/Phase 2 已確認 `InAttackRange` 讀的是真實
  per-weapon `AtkMin`/`AtkMax`,本輪只是親身體會到這個機制在互動操作下的實際手感
  ——下一輪若要繼續手動攻擊,建議先讀 `assets/maps/map0/map0_units.json` 的
  `own_deploy` 與 scenario 的 `initial_groups` 敵方座標算出精確格距,而非憑螢幕
  觀感猜測。
- **`028` 這種與 Sol 外觀（藍帽紅衣）幾乎相同的敵方 sprite**:本輪一度誤把敵方
  單位當成自己隊伍的索爾(靠左下角面板 ID 顏色——白字=我方、紅字=敵方——才分辨
  出來)。根據 ch01 目標卡「本章可能加入:哈諾(出現前勿滅隊)」的敘述,這個
  外觀相近的敵方單位很可能就是尚未加入的「哈諾」。純美術資源重用造成的辨識
  困難,不是程式邏輯 bug。

## 停在哪裡、為什麼

**本輪的自然停止點**:ch01 戰鬥本身**尚未實際打贏**(手動精準攻擊在這個
diamond-grid 美術+指令環節流的組合下,即使已知方法仍然操作成本很高;本輪只
成功執行了 1 次真正的攻擊確認傷害數字),但本輪的核心目標——**證實 Phase 4
「無 debug hook 正常玩」這條路徑本身在修復前完全走不通、修復後確實走得通**——
已經達成並有完整證據鏈(debug log 追蹤 + 修復 + 修復後 3 回合零虛假敗北的
live 重播)。這是一個**架構性阻擋**的修復,不是某個畫面的裝飾性 bug,理論上
解開了整個 M5 milestone 的最大路障。

繼續花費本 session 剩餘時間手動打完 ch01(需要對 8 個敵方単位逐一移動+攻擊,
每次攻擊在目前的操作精度下平均需要 3-5 輪嘗試才能找到有效鄰格)边際效益已經
低於及時記錄與收尾——下一輪應該直接從「已知 own_deploy=[(7,20)索爾,(10,21)
亞雷斯,(8,22)悠妮,(11,23)蓋亞]、敵方 group1(遠,y=0-3 可忽略)+group2
(近,(1,21)(2,22)(3,22)(4,23))」這個已算好的精確座標表出發,不需要重新
摸索。

## 給下一輪的具體建議

1. **不需要重跑 debug 排查**——`applyPersistentStats`/`checkResult` 的 bug 已修好、
   已提交、已 live 驗證,下一輪可以直接假設「Tab 不會再誤判敗北」這個前提成立。
2. 直接用本文件記錄的 `own_deploy`/敵方座標表規劃移動,不要再用螢幕觀感猜測鄰格。
3. 指令環操作:每次方向鍵切換聚焦後,留 0.4-0.6s 真實等待再送 Enter,比連續快速
   按鍵可靠得多。
4. 目標是先打贏 ch01(驗證 postbattle 轉場+`on_win: story_ch02`),再視session
   剩餘時間決定要不要繼續 ch02+。
5. Xvfb `:970` 這個 display 編號本輪用過即釋放(session 結束前已 `pkill`/`kill -9`
   清乾淨,`ps aux`/`tmux ls` 收尾核對過三方——canonical `:99`/`dbg` 等其他 instance
   全程未被動過),下一輪可以沿用或換一個全新編號,兩者皆可。
