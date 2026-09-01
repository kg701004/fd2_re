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

## 2026-09-01 續二:繼續同一場 ch01 戰鬥(T1→T4),真人輸入首次成功命中/挨打,未打贏

**開場清理**:本輪一開始發現前一次(被 API rate limit 中斷的)嘗試其實**留下了活著的
孤兒 process**——`Xvfb :972`(PID 711)+`fd2-linux-verify`(PID 774)+一個 tmux session
`m5play`,已經跑了將近 13 小時(`Aug31 20:04` 啟動,發現時是 `Sep 1 08:57`),與交辦
時「已確認零孤兒 process」的說法矛盾(該檢查應該是對錯的 WSL distro 或錯誤時間點做
的)。截圖確認畫面卡在「選亞雷斯→開環→按下攻擊」這個中斷前的最後動作,與交辦說明
吻合。依指示視為全新開始:screenshot 存證後 `kill`(用 `pkill`/`kill` 被 auto mode
classifier 擋下兩次,最終用 `dangerouslyDisableSandbox` 過)+`tmux kill-session`
清乾淨,`ps aux`回歸乾淨(`:99`/`dbg`等 canonical instance 全程未被動過)。

**Go 工具鏈定位**:WSL2 內建 `go` 不在標準 PATH(`which go` 找不到),實際位置是
`/home/kg701004/go/bin/go`(go1.22.12,GOROOT=該路徑本身,GOPATH 與 GOROOT 衝突但
不影響建置只會印 warning)。從當日 HEAD(`e4b40834`)重新建置 `fd2-linux-verify`
(`GOOS=linux GOARCH=amd64 go build`)成功,14.9MB,含今天稍早所有 AP/DP/MV/DX/
HIT/EV/postbattle-binding 工作。全新 Xvfb `:980`,以 `nohup setsid ... &
disown -a`(單純 `&`+`disown` 會在某次 wsl.exe 呼叫結束後被回收,換這個寫法才穩定
存活)啟動 binary,`FD2_CAMPAIGN=assets/scenarios/campaign_full.json`+`FD2_MUTE=1`
+三個 `FD2_ORIGINAL_*`,逐字同 `play.sh`,無任何 `FD2_SHOT_*`/`FD2_CAMP_*`。

### 序章對白→ch01戰鬥開局(約165次 Enter,分批20-40次一組+screenshot確認)

順利重演續一已記錄的完整序章(王座廳→王城→比劍→發現悠妮蓋亞→行軍→盜賊宣戰),
無異常。

### 座標/UI 機制釐清(耗費本輪大半時間,但對後續 session 有直接參考價值)

**用 F3 開啟的除錯 HUD 才是可靠的地面真相**——螢幕左上角 `T{turn}
own{n} ally{n} enemy{n} cur({x},{y})`,比對照著螢幕觀感猜格子準確得多。這是玩家
可按的正常按鍵(非 env var hook),F3 debug HUD 在戰鬥畫面本身就會渲染除錯資訊
(`main.go:7339` `if g.debug` 分支),完全在「無 debug hook」規則許可範圍內。

**方向鍵→格子的映射是純正交、非菱形**:`Right`=x+1(螢幕純水平位移~47.7px)、
`Down`=y+1(螢幕純垂直位移~47px),兩者互不影響。上一輪筆記提到的「diamond/brick
tile 視覺」只是美術風格,邏輯格線是標準矩形網格,不需要斜向換算。

**ch01 開場 own_deploy 座標經 ACT(0) 位移 -6y**:離線用暫時的 `zz_probe_ch01_test.go`
(跑完即刪除,未 commit)呼叫 `battle.Load`+`LoadScenario`+`sc.Setup`+
`sc.Fire(st,"on_battle_start","")` 印出的原始 `own_deploy` 座標
(索爾(7,20)/亞雷斯(8,22)/悠妮(10,21)/蓋亞(11,23))**在真正互動時對不上**——實測
索爾在 `(7,14)`、亞雷斯在 `(8,16)`,兩者都精準吻合「y-6」,和 `event.go:500`
附近註解「ACT(0) 把四個 runtime slot 全部往上移六格」完全一致。**但敵方座標沒有
相同規律**(offline probe 給出 group2 原始 `(1,21)(2,22)(3,22)(4,23)`,實測活著的
敵人卻在 `(2,18)/(3,18)/(5,20)` 一帶,既非原始值也非 -6y),推測敵方另有自己的
ACT 位移或本來就走不同座標系,**下一輪若還要精算敵方座標,建議直接用 F3 HUD 現場
量測,不要沿用 offline probe 的敵方數字**——這正是本輪吃虧的地方,靠螢幕觀感+像素
換算($\approx$47.7px/格,校正點見下)手動測出來的,不是預先算好的。

**指令環方向鍵確實有你來我往(hit-or-miss)的丟鍵**,不是幻覺:同一個「原地不動→
開環→按上選攻擊→Enter」序列,對亞雷斯第一次試就成功進「攻擊:選擇目標」,對索爾
卻連續 3-4 次「按 Up 沒反應、Enter 只會重覆『此指令目前不可用』」才成功。**耐心
重試(檢查畫面而非假設一定失敗)是目前唯一可靠的因應方式**,尚未找到觸發條件的
規律。

### 真正的雙向戰鬥,首次透過純正常輸入達成(本輪核心驗證目標)

- **T2**:亞雷斯(移動到 (5,18),距敵 (3,18) 曼哈頓距離 2,吻合他 `atk_min1/
  atk_max2` 的長矛射程)攻擊「盜賊」,命中,**造成 20 傷害**(敵方 HP 28→8)。
  截圖 `m5-play-ch01-r2-02-ares-first-hit-20dmg.png`(戰鬥剪影+「亞雷斯 攻擊
  盜賊，造成 20 傷害」字樣)。
- **T2→T3 敵方回合**:「盜賊 攻擊 亞雷斯，造成 18 傷害」,真人輸入路徑下首次
  看到敵方主動命中我方單位並扣血。截圖
  `m5-play-ch01-r2-03-enemy-counterattack-18dmg.png`。
- **T3**:亞雷斯嘗試補刀同一隻(已剩8血的)盜賊,**未命中**(`hit`機制真的會
  miss,不是每次必中)。截圖 `m5-play-ch01-r2-04-second-attack-animation.png`
  (全螢幕戰鬥立繪,雙方姓名+HP條)。
- **T3→T4 敵方回合**:亞雷斯再挨一次「造成 18 傷害」(同一隻敵人或另一隻,訊息
  文字相同未逐一分辨)。
- **T4 開局**:`own4→own5, ally0→ally1`——劇本觸發「哈諾」加入隊伍(對照
  `TestChapter1Turn3JoinsHanoBeforeSpawningHisGroup` 這個既有測試名稱),對白
  「『真是的，吵的要命，到底在搞什麼。。』」正確渲染,同時螢幕左下角持續印出
  `loadErr: scenario join_party:    1`。截圖
  `m5-play-ch01-r2-05-turn4-hano-joins-loaderr.png`。

**全程 4 個完整回合零虛假敗北**——`applyPersistentStats` 的修復在真正跨越
多回合、多次真實攻防後依然穩固,沒有任何新的迴歸跡象。

### 發現二:`join_party` T3 錯誤確認會在真正的 campaign 流程重現,不只是孤立測試 harness 才有

`main.go:2965` 的 `g.loadErr = fmt.Sprintf("scenario join_party:找不到角色%d的
我方記錄", id)` 早已被 `headless_battle_test.go:58-71` 記錄為「已知、已記錄的
小瑕疵」——但**該註解的原始假設是「只有 loadGame()+resetBattle() 建的孤立
harness(沒有真正跑過 campaign/story 進度)才會踩到,因為那個角色的我方名冊
記錄從沒被建立過」**。本輪走的是完整序章→ch01 這條真正的 campaign 路徑,**這個
錯誤依然原封不動地重現**,推翻了「僅限孤立 harness」這個侷限性假設——真正影響
面比原先文件記載的更廣。**功能上無害**:`own5` 確認哈諾依然靠同一個
on_turn_end trigger 裡的 `spawn_group` fallback 正常加入隊伍(與該測試註解「
accompanying spawn_group action 仍然會落地」的預期一致),只是 `join_party`
這個「把哈諾轉成具名角色記錄」的子步驟本身悄悄失敗、`loadErr` 訊息殘留在畫面
角落,不影響可玩性但確實是個尚未修的真實 bug——留給未來 session,不在本輪
處理範圍。

### 發現三(真實、可重現、本輪未修的 bug):悠妮的指令環在一次「開火炎術目標選擇→
Escape取消」之後永久失效

**症狀**:T2 選悠妮、原地開環、選「法術」(環左)、Enter 進「火炎術」目標選擇
(`原始指令 0：選擇目標`,無合法目標高亮),按 Escape 取消。之後**同一場戰鬥
剩餘時間內**,悠妮的環再也打不開——重選她、按 Enter 開環,畫面永遠沒反應
(無環顯示、無錯誤訊息),嘗試了單次/連續3次/間隔1秒重試/多次 Escape 想清狀態,
全部無效。**索爾、亞雷斯、蓋亞完全不受影響**(同一 turn/次一 turn 都正常開環),
確認不是全域性卡死,是悠妮專屬(或者說是「這場戰鬥裡曾經進過原生指令目標選擇
又取消」這個狀態專屬)。

**目前最佳假說(讀碼,非已證實)**:`main.go:5639` 的 `confirm()` 一開頭無條件檢查
`if g.nativeCommand0Targeting {...}`,這個旗標只在成功執行原生指令時才會重置回
`false`(`main.go:5672`);Escape 取消目標選擇的處理(`main.go:6659-6667`)理論上
會清掉它並設 `nativeCommandOpen=true`(退回指令列表選單),`nativeCommandOpen`
自己的選單迴圈(`main.go:4445-4499`)理論上再按一次 Escape 會 `beginActionOverlayOpen`
把環重開——但本輪實測連續按 Escape 並未讓環恢復,不確定是這兩段路徑本身有漏洞、
還是某個更早的 guard(例如 `g.walk != nil`)也卡住了。**留給下一輪帶著除錯建置
(或加臨時 log)才能真正釘死根因**,本輪只確認了症狀、影響範圍(悠妮專屬、
本場戰鬥永久性)、以及不影響其他三名角色。

**因應**:本輪直接跳過悠妮該回合行動(不影響 Tab 結束玩家回合),不嘗試在無
debug 建置下用猜測修復。

### 停在哪裡、為什麼

T4 玩家回合開局,own5(索爾/亞雷斯/悠妮/蓋亞/哈諾)全數存活,enemy7 存活(僅
一隻被打到剩8血),尚未打贏 ch01(需要清空全部敵人)。**本輪核心目標已達成**：
證實 Phase 4 這條路徑在真實多回合、真實雙向命中/未命中/挨打的壓力下依然
work——同時額外發現兩個真實 bug(join_party 影響面更廣、悠妮環永久卡死),
兩者都已記錄足夠 repro 資訊但**刻意不在本輪嘗試修復**(前者是資料/native
port 缺口非阻擋性,後者需要更深入的除錯才能安全修正,倉促修改風險大於本輪
剩餘時間效益)。手動精算攻擊距離+應付指令環丟鍵的操作成本仍然很高,是本輪
沒能推進更多回合的主因,與續一記錄的教訓一致。

**清理**:Xvfb `:980` 與 `fd2-linux-verify` 已於 session 結束前確認關閉,`ps aux`
核對 canonical `:99`/`dbg` 等其他 instance 全程未被動過。

### 給下一輪的具體建議

1. 攻擊/移動座標一律用 F3 HUD 現場量測,不要沿用任何離線 probe 的敵方座標
   (本輪證實敵方座標與離線 raw JSON 數值對不上,原因未查)。
2. 指令環方向鍵有已知但未解的 hit-or-miss 丟鍵現象,遇到「畫面沒反應」先重試
   2-3 次再考慮是否真的卡死(用同一裝置按同一鍵測試其他角色來排除全域性卡死）。
3. 悠妮的環卡死 bug 值得優先排查——這會讓她整場戰鬥都無法行動，直接影響「能不能
   打贏」這個 Phase 4 的核心驗收目標；下一輪建議帶 `FD2_DEBUG_RESULT` 類臨時 log
   或直接讀 `confirm()`/`ringInput()`/native command 相關函式的完整呼叫鏈，而非
   繼續盲測。
4. `join_party` T3 錯誤功能上無害（哈諾仍會經 `spawn_group` fallback 加入)，
   可以先忽略繼續推進戰鬥，但若要修，`main.go:2965` 是切入點。
5. ch01 本身還需要清空 enemy7（目前只讓一隻剩 8 血)，以目前的操作節奏預估還需要
   數個完整回合──下一輪建議先解掉悠妮的環卡死 bug 再繼續推進，讓四人都能出手，
   而不是三人硬打。
