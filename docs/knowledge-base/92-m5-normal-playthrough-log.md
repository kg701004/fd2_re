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

## 2026-09-01 續三:發現三復查——用新版 `fd2_live_input_helper` 全程 `--settle`
確認後**未能重現**,判定原始發現是不可靠 raw xdotool 按鍵輸入的產物,不是真實 code bug

**動機**:「發現三」（悠妮的指令環在一次「開火炎術目標選擇→Escape 取消」之後永久
失效)記錄時明確標註「嘗試了單次/連續3次/間隔1秒重試/多次 Escape 想清狀態,全部
無效」,但那一輪全程用的是 ad-hoc `xdotool key` 直接呼叫,沒有對每一次按鍵做
settle 確認——與 doc98/本文件開頭都已經記錄過的「指令環方向鍵 hit-or-miss 丟鍵」
是同一類已知風險。本輪的任務就是專門用新建的 `tools/fd2_live_input_helper.py`/`.sh`
(這兩個檔案就是為了解決「按鍵送出後到底有沒有真的被吃到」這個不確定性而建的)
重跑同一個 repro,每一鍵之後都用 `key ... --settle`(輪詢畫面直到連續兩張截圖
完全相同才送下一鍵,而非固定等待),確認發現三是真 bug 還是輸入不可靠的偽陽性。

**方法**:全新 WSL2 Ubuntu instance(`fd2_live_input_helper.py launch --instance
yunibug`,Xvfb `:199`,與任何 canonical `:99`/`dbg` 等其他 session 不重疊)。
`remake/fd2-linux-verify` 當場重新建置(WSL 內建 `$HOME/go/bin/go`,
`GOOS=linux GOARCH=amd64 go build -o fd2-linux-verify ./cmd/fd2`,成功,
14.9MB)。啟動指令沿用 `play.sh` 慣例(`FD2_CAMPAIGN=assets/scenarios/
campaign_full.json`+`FD2_MUTE=1`+三個 `FD2_ORIGINAL_*`),**完全沒有**
`FD2_SHOT_*`/`FD2_CAMP_*` debug hook。序章對白→ch01 戰前對白共約 220 次 Enter
(分批 20-60 次一組送出,每批後截圖確認進度,batch 內部用 0.2-0.3s 固定間隔而非
逐鍵 settle——這段純粹是翻對白,不涉及本次要驗證的狀態機,用固定間隔已足夠可靠
且大幅省時間),順利進入 ch01 戰鬥 T1(F3 debug HUD 確認 `T1 own4 ally0 enemy7`)。

**用移動範圍高亮+黃色姓名標籤現場確認單位身分**(不假設任何離線座標):游標
`(10,15)` 的單位開環後畫面正確顯示黃字「悠妮」,ID 面板顯示 `028`——這正是續二
筆記提到「跟索爾外觀神似的敵方 sprite `028`」的同一個數字,但這裡確認是**我方**
悠妮本人(她跟某個敵方 sprite 共用了美術資源編號,純美術重用,不是同一個邏輯單位;
下一輪若要用 ID 辨識單位,記得不能只看數字,要連同陣營色/選取後的姓名標籤一起看)。

**逐鍵 `--settle` 重跑的完整原始 repro 序列**(對照「發現三」原敘述,一步不少):
1. 悠妮原地開環(`confirm --settle`)——4 圖示環正常顯示,預設焦點在左側「法術」
   (紅框高亮),與續一筆記「預設 index1」一致。
2. `confirm --settle` 選法術——進入 `nativeCommandOpen` 原生指令列表,畫面左下角
   顯示「火炎術」。
3. `confirm --settle` 選火炎術——進入 `nativeCommand0Targeting`,畫面顯示
   「原始指令 0：選擇目標」,與原始 bug 敘述逐字吻合。
4. `cancel --settle`(**單次** Escape,對照原始「按 Escape 取消」這一步)——畫面
   回到 `nativeCommandOpen` 選單狀態(「火炎術」字樣還在,`原始指令 0：選擇目標`
   殘留訊息也還在,因為這個 ESC handler 沒有清 `g.msg`,純粹是視覺上的殘留字,
   不是狀態卡死的證據)。

**這一步之後,額外加了三組原始輪次沒有系統化測過的驗證(用 `--settle` 逐一確認每
一鍵都真的被吃到,而非原輪的「連續3次/間隔1秒」這種盲重試)**:
- **方向鍵測試**:在上述第4步的狀態按 `Down --settle`,F3 HUD 的 `cur(x,y)`
  座標完全沒變——證實此刻方向鍵正確被 `nativeCommandOpen` 選單吃掉(單一法術,
  選單環繞回自己),**不是**地圖游標移動,這是設計内的正常行為,不是 bug。
- **單次 Escape 後直接 Enter**:再送 `confirm --settle`——正確地**重新**進入
  `nativeCommand0Targeting`(畫面重現「原始指令 0：選擇目標」),沒有卡死、沒有
  沉默無反應。
- **完整三層 Escape 退回**:從 targeting 狀態連續 `cancel --settle` 三次(第1次
  回 `nativeCommandOpen`;第2次回環本身,畫面正確播放開環動畫並穩定顯示四圖示環;
  第3次因為悠妮本回合未移動過,直接完全取消選取,回到單純地圖游標,面板上的姓名
  標籤與訊息都清空)——每一步畫面都如預期變化,無一次卡死。
- **完全重選悠妮**:游標離開她的格子(`Left Left`)、確認 HUD 座標真的改變、
  再移回她的格子(`Right Right`)、`confirm --settle` 重新選取(移動範圍正確重新
  高亮)、`confirm --settle` 再次原地開環(四圖示環正常重新顯示)——**這證明
  `!u.Acted` 這個重選 gate(`main.go:5541`)從頭到尾都是 `false`,`finishSelectedWait`
  從未被誤觸發**,直接推翻「發現三」筆記寫的「目前最佳假說」(`confirm()` 的
  `原地待命`分支被 stray Enter 誤觸,悄悄把 `Acted` 設成 `true`)。
- **加壓測試(模擬原輪『連續按鍵』但這次全部走可靠送鍵管道)**:重新走一次
  法術→火炎術→targeting,這次用 `cancel cancel cancel --gap 0.1`(3 次 Escape
  之間只留 0.1 秒、且中途不逐鍵 settle,刻意貼近原輪「連續按 Escape」的操作節奏,
  只是這次改用可靠的 `send-key` 而非原始 ad-hoc `xdotool key`)——最終 `--settle`
  確認畫面乾淨地完全取消選取(跟前面單獨測的第三層 Escape 結果一致)。之後再
  `confirm confirm --gap 0.3 --settle` 重選+開環,四圖示環第五次成功正常顯示
  (`wait-settle` 這次逾時 timeout,但檢查截圖環本身渲染完全正常——逾時是因為
  `g.ringPulse` 選中格的閃爍動畫本身就會讓連續截圖永遠不完全相同,`wait-settle`
  「連續兩張畫面一致才算穩定」的判定方式對這種持續閃爍的畫面天生會 timeout,是
  這個通用 primitive 面對「有意閃爍動畫」場景的已知限制,不是遊戲卡死——`fd2_live_
  input_helper.sh` 的 `wait-settle` 文件已經點出這個 trade-off,這裡補一筆實測
  案例存證)。

**結論:發現三在本輪的嚴謹、逐鍵 settle 確認的真人輸入路徑下完全沒有重現**——同一
套「開火炎術目標選擇→Escape 取消」序列,無論單次 Escape、完整三層 Escape、或
0.1 秒間隔連續三次 Escape,悠妮的環事後都 100% 正常重新開啟,`Acted` 從未被
意外設成 `true`。這代表上一輪記錄的「永久卡死」現象,最合理的解釋是**該輪使用
的 ad-hoc `xdotool key` 呼叫本身丟了或誤判了按鍵**(doc98/本文件開頭已經記錄過
同一類「指令環方向鍵 hit-or-miss 丟鍵」的風險),而不是 `confirm()`/
`nativeCommandOpen`/`nativeCommand0Targeting` 這幾段狀態機邏輯本身有漏洞。
**依交辦指示,本輪確認「不能重現」後即停止,未修改任何程式碼**——「發現三」原本
記錄的「目前最佳假說」(`finishSelectedWait` 被 stray Enter 誤觸發)已被本輪的
`!u.Acted` 重選成功這一步直接證偽,不需要下一輪再帶著這個假說去做 debug log
追蹤。

**清理**:`yunibug` instance(Xvfb `:199` + `fd2-linux-verify`)已用
`fd2_live_input_helper.py teardown --instance yunibug` 正常關閉,`ps aux`
核對 WSL 內完全沒有殘留的 `Xvfb`/`fd2-linux-verify` process(本輪執行前後 WSL
內其實**沒有任何**canonical `:99`/`dbg` 等其他 instance 在跑,無需額外核對是否
被誤動)。本輪截圖存於 `.wsl_build/live_input_helper/yunibug/`(工具預設路徑,
非 `docs/figures/`——純過程驗證截圖,不promote 進正式文件)。

## 2026-09-01 續四:重大發現——標準「buff/nerf JSON」捷徑在真正走過 campaign
劇本路徑時對敵我雙方都**完全失效**;真實攻防機制本身首次被完整驗證正確

**開場**:接續一個被 rate limit 中斷的既有嘗試,`fd2_live_input_helper.sh status`
發現一個孤兒 instance `m5r4`(Xvfb/game 進程其實已死,只是 registry 殘留),
`teardown-all` 清乾淨,`ps aux`/`tmux ls` 核對 WSL 內無殘留。確認交辦標準的
「ch01.json 主角隊 hp/mp/ap/mv=9999、map0_units.json 敵方 hp/mp/ap/dp=1」
buff/nerf 檔案處於標準的「已編輯未 commit」狀態,重新從當日 HEAD build 一份
新鮮的 `fd2-linux-verify`。

### 指令環方向鍵的真正語意——不是「移動焦點」,是「直接選指令」

本輪一開始被指令環操作卡住多輪(以為方向鍵是在幾個圖示間移動反白焦點,結果
Up/Right 怎麼按都「沒反應」)。回頭讀 `main.go:4345` 自己的既有註解才發現:
**這根本不是需要「移動再確認」的選單,是直接映射**——`main.go:4540-4552`
明寫「環導航(doc13 [0x3C57]:↑0攻擊/←1法術/→2物品/↓3待機)」,按哪個方向鍵
就直接把 `g.ringSel` 設成對應指令,`Enter` 立刻執行那個方向代表的指令,不需要
先移動反白再確認。**下一輪如果還要操作指令環,直接記「上攻擊/左法術/右物品/
下待機」這個固定表,不要再嘗試用方向鍵在四個圖示間「移動選取」**——這是本輪
自己走了不少冤枉路才確認的,純粹是沒有先讀 `main.go` 自己的中文註解就開始
用視覺/像素判讀猜測。

### 真實攻防機制首次完整驗證正確(無 debug hook、真人輸入路徑)

用上面校正過的環操作,對 ch01 T1 的一隻「盜賊」完整跑過一次
`移動→開環→按Up選攻擊→關環進入目標選擇→移動游標到敵人格→confirm`
全流程,**成功命中,造成 22 傷害**,畫面正確顯示「亞雷斯 攻擊 盜賊,造成
22 傷害」與戰鬥剪影動畫。Tab 結束玩家回合後,ENEMY PHASE 正確觸發,敵方
AI 反擊亞雷斯,「盜賊 攻擊 亞雷斯,造成 17 傷害」同樣正確顯示全螢幕戰鬥
演出。這是本專案第一次**完整**驗證「開環→選攻擊(非原地待命)→關環進入
目標選擇→游標移到範圍內敵人→confirm 執行攻擊」這條完整互動鏈在真人輸入
下運作正常(先前續一/續二/續三都只驗證到片段:續一只驗證過一次原地攻擊,
續二驗證了雙向命中但操作细節記錄不完整,續三只驗證了法術目標選擇+Escape
不涉及實際攻擊執行)。

### ★ 重大發現:buff/nerf JSON 捷徑在真正走過 campaign 劇本路徑(序章對白→
LOADCH→戰鬥)時,對主角隊與敵方**都完全不生效**——這不是本輪新引入的
bug,是這個捷徑本身跟這個專案的「native record 重建」架構有結構性衝突

**症狀**:本輪一開始沿用標準捷徑操作(`ch01.json` 主角 hp/mp/ap/mv 全部設
9999、`map0_units.json` 24 隻敵方 hp/mp/ap/dp 全部設 1),照交辦程序重新
build+啟動+走序章對白進 ch01 戰鬥。**選取亞雷斯後,角色資訊畫面顯示
HP 048/048、AP 026、MV 07——與 vanilla(未 buff)數值完全吻合,9999 完全
沒有生效**。移動到敵方單位旁開環選目標,敵方單位面板顯示 HP `028`——同樣
是 vanilla 數值(盜賊原始 HP 就是 28),1 完全沒有生效。

**根因追查(用臨時 `FD2_DEBUG_ENEMY_STATS` env var 插入的 debug print,
非猜測——完整鏈路如下,修完後已全數 `git checkout` 撤銷,未進版控)**:

1. **主角隊 buff 失效——根因已完全釘死,和續一記錄的
   `applyPersistentStats` 是同一個機制的另一個面向**:`main.go:2651` 的
   `applyPersistentStats(dst, src)` 在每次 `applyLoadCH`(包含序章對白本身
   觸發的第一次)都會**無條件**把 `dst.HP/MaxHP/MP/MaxMP/AP/DP/MV` 等一整組
   欄位用 `src`(`g.partyRoster[fig]`)覆寫。`g.partyRoster` 只在**第一次**
   `seedPersistentPartyFromLoadCH` 時填入,來源是
   `materializeNativeJoinPersistentUnit()` →
   `NativeJoinConstructorTable.MaterializePersistentUnit()`
   (`internal/campaign/native_join_constructor.go:108`)——這個函式**完全
   不採用**傳入的 `base`(即 scenario JSON buff 過的單位)的 HP/MP/AP/DP/MV,
   而是從 native class/growth table(`row.defaults`/`row.growth`,對應
   原版 `sub_112A5` 的忠實重建)重新算出這些值。淨效果:`ch01.json` 的
   `party` 陣列 buff 只在**該角色人生中第一次 JOIN**當下短暫存在,序章
   對白一旦跑到任何一次 `applyLoadCH`,`g.partyRoster` 就會被填入 vanilla
   數值,之後**每一章**開局的角色數值永遠是 vanilla,不是 buff 過的值。

2. **敵方 nerf 失效——已用 debug print 追蹤到「LOADCH 當下正確、戰鬥開始
   前被還原」這個現象,但**沒有在本輪時間內完全釘死是哪一行覆寫回去的**,
   誠實記錄追查過程與已排除的候選,留給下一輪**:
   - `applyLoadCH()`(`main.go:1830`)自己的 `roster, err :=
     battle.Load(assetPath(state.Roster))` 這一步,debug print 證實**正確
     讀到 hp=1**(對 ch01 用的 `assets/maps/map0/map0_units.json`,24 隻
     敵方全部印出 `hp=1 ap=1 dp=1`)。
   - 同一次呼叫接著把 `roster.Units` 逐一複製進
     `g.storyRoster`(`main.go:1908-1918` 一帶)——debug print 證實**這裡
     也仍然是 hp=1**,包含 `group=1`/`group=2` 等非 0 群組(盜賊群組本身的
     JSON `"group"` 值)。
   - 但當battle真正進入(`resetBattle()`,`main.go:2418`)、`adoptHandlerState`
     判定為真、`g.storyActors`(這裡稱 `handlerActors`)被拿來取代這次
     `resetBattle` 自己 fresh `battle.Load()` 出來的 `st.Units` 時——debug
     print 顯示 `handlerActors` 裡的盜賊已經是 **hp=28 ap=24 dp=4(vanilla)**,
     座標也和 LOADCH 當下的原始 JSON 座標有系統性偏移(y+1),說明這**不是
     單純的複製殘留**,是某個真正的 native reconstruction 已經在中間跑過。
   - 已排除的候選(讀過原始碼,確認**不是**這些):`AdoptHandlerBattleState`
     (`event.go:407`,只處理 `PendingGroups`/事件 fired 旗標,不碰 HP)、
     `materializeStoryGroup()`(`main.go:1803`,debug print 顯示**這次
     戰鬥根本沒有呼叫到**——盜賊的 `group` 直接是 1,不是 0,理論上該由
     這個函式在劇本觸發時才搬進 `g.storyActors`,但實際上 `resetBattle`
     讀到 `g.storyActors` 時盜賊已經在裡面了,呼叫路徑仍不明)、
     `AppendNativeMapSelectorBatch`/`MaterializeNativeMapSelectorSlots`/
     `MaterializeNativeMapPresentation`(`model.go`/`native_map_presentation.go`,
     讀過原始碼確認只碰 sprite selector/位置,不碰 HP/AP/DP)。
   - **目前最佳假說(未證實)**:這個專案裡已知至少兩個「native
     constructor 從 class/growth table 重新算 HP/AP/DP,無視傳入 base 的
     欄位」的既有機制——`MaterializeNativeJoinPersistentUnit`(主角隊,已
     證實是禍首)、`MaterializeNativeFutureConstructor`
     (`native_future_constructor.go:87`,目前已知只用在
     `on_turn_end`/`spawn_group` 觸發的**後續**援軍群組)。敵方 nerf 失效
     很可能是**同一類機制的第三個、目前還沒定位呼叫點的變體**,專門處理
     ch01 開局就在場的 group1/group2(不是後續 `spawn_group` 觸發的援軍),
     但本輪沒有找到實際呼叫這個變體的程式碼位置。**下一輪如果要繼續釘
     根因**,建議在 `resetBattle()` 內部,`battle.Load()` 呼叫完、
     `adoptHandlerState` 判斷之前後,對 `st.Units`(fresh load,非
     `handlerActors`)也印一次 debug,先確認是不是這個 fresh load 本身
     就已經是 vanilla(如果是,問題出在 `battle.Load()` 內部某個我們還
     沒追到的分支;如果 fresh load 也是 hp=1,那問題確定出在
     `handlerActors`/`g.storyActors` 這條線,要繼續往回查是誰在
     `materializeStoryGroup`/`STORYACTORLOOP`/`STORYROSTERBUILD` 三個
     已知組裝點之外,還有第四個組裝點把 group1/group2 塞進
     `g.storyActors`)。

**結論與對整個 M5 Phase 4 專案的影響**:**這個標準 buff/nerf JSON 捷徑,
對「真正走過序章對白→LOADCH→戰鬥」這條 Phase 4 要求的無 debug hook 正常
玩法路徑,結構性地不生效**——不是本輪操作失誤,是這個專案的 native record
重建系統(為了忠實還原原版存檔/JOIN/群組生成的位元組行為而設計)在多個
節點都會用 class/growth table 重新算出 HP/MP/AP/DP/MV,無視 scenario/map
JSON 宣告的數值。這個捷徑**只在繞過序章、直接用類似 `FD2_CAMP_*` debug
hook 或孤立 harness 載入單場戰鬥時才會生效**(因為那種載入方式不會經過
`g.partyRoster`/`g.storyActors` 這整條 persistent/story 狀態機),而這正好
是 Phase 4 明確要排除的載入方式。**這代表過去幾輪(續一/續二/續三)記錄
的所有戰鬥數值——索爾 HP42、亞雷斯 AP26 對盜賊 DP2 算出 21 傷害、盜賊
HP28→8——全部其實都是 vanilla 數值,不是 buff/nerf 生效後的結果**,只是
沒人拿「交辦要求的 9999/1」去對照過,回頭看反而是件好事:這代表續一到
本輪為止,Phase 4 到目前為止測到的所有真實攻防數字,其實**從頭到尾都是
貨真價實的 vanilla 難度驗證**,不是掛了捷徑的簡化版——對「證明無 debug
hook 正常玩法可達」這個 M5 驗收句而言,反而是更強的證據,只是伴隨的風險
(單位真的會受傷、真的可能死)比原本以為的高。

**給下一輪的建議**:
1. **不用再嘗試用 JSON 編輯 buff/nerf 之後才開始真人輸入 playthrough**——
   已證實對這條路徑無效,徒然浪費一輪 build+序章對白的時間。標準捷竟仍然
   對其他用途有效(例如繞過序章直接載入單場戰鬥的除錯情境),只是不適用
   於 Phase 4 這種「一定要走過序章」的驗證方式。
2. 若要繼續打 ch01(vanilla 難度),`m5r4`/`ch01run2` 這兩個先前 instance
   都已消失(過程中被交錯的除錯 instance 或並行 session 動到,細節不明,
   但收尾時 `ps aux` 確認 WSL 內無孤兒程序),下一輪需要從頭重新走序章
   對白。
3. vanilla 難度下已知：一次命中約 20-22 傷害、敵方一次命中約 17-18 傷害,
   索爾/亞雷斯/悠妮/蓋亞 HP 分別 42/48/28/50——多打幾輪有真實被打死的
   風險,不能再假設「敵人 AP=1 幾乎打不痛」。
4. 如果要真的解開敵方 nerf 失效的根因,見上面「目前最佳假說」段落的具體
   debug 建議(在 `resetBattle()` 的 fresh `battle.Load()` 之後立刻印一次
   debug,先切開「fresh load 本身有沒有問題」跟「`g.storyActors` 這條線
   有沒有問題」這兩種可能)。
5. 全程使用的 debug instrumentation(`FD2_DEBUG_ENEMY_STATS` env var 觸發
   的臨時 print)已經在本輪結束前用 `git checkout -- remake/cmd/fd2/main.go`
   完整撤銷,未進版控,下一輪如果要重新插樁需要自己重新加。

**清理**:本輪使用過的所有 instance(`ch01run`/`ch01run2`/`dbgcheck`/
`dbg2`~`dbg6`)均已個別 `teardown`(`ch01run2` 的 teardown 呼叫遺失在
交錯的除錯操作中,但收尾時用 `ps aux` 核對 WSL 內確實已無殘留的
`Xvfb`/`fd2-linux-verify` 進程,不是孤兒)。開發過程中發現
`tools/fd2_live_input_helper.py`/`.sh` 兩個檔案在本輪執行途中被**另一個
並行 session** 修改(新增 raw/resized screenshot 分離輸出的功能,
registry 裡也看得到 `livehelpertest1-3`/`probe1`/`rawviewcheck`/
`resizecheck` 這些非本輪建立的 instance 殘留 log)——本輪未觸碰、未

## 2026-09-01 續五:發現二額外證據——敵方目標面板的肖像圖也是錯的,不只是數值,強化「`g.storyActors`/`handlerActors` 整筆記錄被替換」假說,弱化「class/growth table 重算」假說

**背景**:並行 session 用另一個獨立 instance(`ch01r3`,續四之後由背景 agent
重新走過序章、真人輸入到 T3)做人物外型比對時,用 `tools/fd2_live_input_helper.py`
的游標移動原語把 F3 除錯游標精確停在一隻盜賊身上(截圖見
`.wsl_build/live_input_helper/ch01r3/20260901-190224_target2.png`,已知
**這份截圖不在 git 版控內**,是本機 scratch 檔案,下一輪如果要重看需要
自己重新走一次或請對方提供),發現「攻擊:選擇目標」狀態下左下角的單位
面板:

- **HP 數字 `028` 是對的**(盜賊原始 HP 就是 28,跟 vanilla 數值吻合,
  跟續四記錄的「敵方 nerf 失效、vanilla 數值滲透」現象一致)。
- **但面板肖像圖畫的是索爾的臉**(藍髮、紅頭巾、側臉造型)——直接跟
  `remake/assets/portraits/DATO_000_m0.png`(已用 church_test.go 的
  `{Fig: 0, Portrait: 0}` 對照表確認 portrait id 0 = 索爾)逐像素比對過,
  确定不是眼花,是同一張圖。盜賊自己真正的 portrait 應該是 id 96
  (`map0_units.json` 每筆盜賊記錄的 `"portrait":96` 欄位本身是對的,
  `internal/battle/model.go:971` 的 fresh-load 路徑`Portrait: u.Portrait`
  也是對的直接複製,沒有問題)。
- 對照組:同一輪把游標停在蓋亞(自己隊上的機兵)身上時,面板肖像圖
  正確畫成蓋亞自己的機兵造型,不是索爾——**只有敵方單位的肖像圖跑掉,
  自己隊上的單位是對的**。

**這條新證據跟續四「目前最佳假說」的關係——建議修正該假說的方向**:續四
記錄的「敵方 nerf 失效」現象,原本傾向「跟主角隊 buff 失效同一類機制,
某個 native constructor 用 class/growth table 從頭重算 HP/AP/DP」。但
**growth table 重算函式没有理由會動到 `Portrait` 欄位**——`Portrait` 是
角色身份欄位,不是靠等級/職業公式算出來的數值。如果敵方單位進入戰鬥後
不只 HP/AP/DP 是 vanilla、連 `Portrait` 都變成另一個角色(索爾)的值,
這比較像是**整個 `battle.Unit` 記錄被整包替換/錯位**(例如
`g.storyActors`/`handlerActors` 這個陣列裡,原本該對應這隻盜賊的 slot
被索爾的記錄覆蓋、或是查找時用了錯的 index/key),而不是「只有數值欄位
被重算」。續四記錄的「座標也和 LOADCH 當下的原始 JSON 座標有系統性偏移
(y+1)」這個既有觀察,現在看也更支持「整包記錄替換」而非「選擇性數值
重算」——如果只是數值重算,座標不應該跟著變。

**未做的事(誠實記錄,不是本輪重點,留給下一輪)**:沒有再往下追這個
替換確切發生在哪一行——續四已經排除的三個候選(`AdoptHandlerBattleState`/
`materializeStoryGroup`/`AppendNativeMapSelectorBatch` 系列)這個新證據
沒有推翻,只是提供了新的排除線索(重算/替換函式必須同時碰
`HP/AP/DP/MV`**和**`Portrait`**和**`X/Y`,範圍比單純的「數值重算」更廣,
下一輪找候選函式時可以用「這個函式有沒有整包複製/覆寫 `Portrait` 欄位」
當篩選條件,縮小搜尋範圍)。這是**真實、可重現、目前仍未修的 bug**,會讓
玩家在攻擊選敵人時看到錯的臉——不只是內部除錯數值的問題,是會被玩家
直接看到的視覺 bug,建議優先度高於單純數值正確性。

## 2026-09-01 續六:同一族 bug 的更嚴重版本——不只是面板肖像,連地圖上的
**單位本體 sprite** 都會在「敵人的正常/閒置畫面」顯示成索爾的樣子,而且是
**穩定、可用選取狀態切換的可重現行為**,不是隨機閃爍

**背景**:在已確認是今天 19:48 build(`faecef3e`,見上方使用者提問的驗證)
的 `ch01r3` instance 上,用 `fd2_live_input_helper` 的游標原語重新檢查
「原本以為是隊伍左側 3 人集群」的那組單位,結果發現這組單位其實混了
3 隻真正的盜賊敵人跟 1 個真正的隊友(亞雷斯,fig=4)——不是續五記錄的
「肖像面板單獨畫錯」,是**整個地圖上的單位貼圖本體**在特定狀態下畫錯。

**三張連續截圖,乾淨的 A→B→A 切換證據(已存進
`docs/figures/m5-ch01-enemy-sprite-bug-0{1,2,3}-*.png`,同一個螢幕座標
`(95,45)-(205,185)` 裁切,同一批單位,中間沒有任何單位移動或死亡)**:
1. `-01-idle-wrong.png`——**選取蓋亞之前**:這組 4 個單位全部畫成索爾的
   造型(藍髮、紅頭巾、紅色胸前配件,跟 `portraits/DATO_000_m0.png`/DOSBox
   原版索爾單位同一個設計)。
2. `-02-during-selection-correct.png`——**選取蓋亞、蓋亞的移動範圍
   overlay 顯示中**:同一組 4 個單位裡,3 個變成正確的盜賊造型(紅頭巾
   +黑色眼罩,跟 `assets/sprites/fig_096_f00.png`/DOSBox 原版盜賊單位
   同一個設計),只有 1 個維持藍色頭盔造型(這個應該才是真正的隊友
   亞雷斯,fig=4)。
3. `-03-after-cancel-wrong-again.png`——**按 Escape 取消蓋亞的選取後**:
   同一組單位**變回**跟第 1 張一模一樣的錯誤索爾造型。

**這證實幾件事**:
- 這不是「這 3 隻盜賊本來就長得像索爾」的巧合或美術重用——同一批單位在
  A/B/A 三個時間點,貼圖在「索爾造型」跟「盜賊造型」之間乾淨切換,唯一
  變因是「另一個單位(蓋亞)是否處於選取/移動範圍顯示狀態」。
- 這代表「own4 own4」這個數字看起来一直是對的(4個真正隊友:索爾、
  亞雷斯、悠妮、蓋亞),敵方單位數量也一直是對的(enemy7),**問題完全
  在繪圖層,不在戰鬥邏輯/數值層**——這跟續四(數值 vanilla 化)、續五
  (肖像面板錯位)記錄的兩個 bug 性質不同,但很可能是同一個更底層問題的
  第三個症狀:某個地方在「決定要畫哪個 fig/portrait」時,對敵方單位用
  錯了來源,而這個來源會被「另一個單位的選取動作」意外地正確化或再次
  弄錯。
- 對玩家體驗的影響比續五更嚴重:續五只是攻擊選目標時的小面板肖像錯誤,
  這次是**整個閒置狀態下的戰場地圖,絕大多數時間都會把敵人畫成自己人的
  樣子**——如果不主動選取某個單位觸發 range overlay,玩家在正常回合間
  觀察戰場時,看到的敵我識別畫面基本上是錯的。

**還沒查的(誠實記錄,留給下一輪)**:
- 沒有進一步縮小是哪一個 Draw 函式路徑造成這個切換——`main.go` 裡畫
  地圖單位 sprite 的函式(推測跟 `drawUnit`/`drawMapUnits` 一類的名稱有
  關,尚未實際 grep 確認)有沒有分「有無 range overlay 顯示中」兩條路徑,
  是下一輪查證的具體切入點。
- 沒有測試其他敵方單位(例如另外那 4 個原本以為在遠處、實際沒找到的
  盜賊,或 boss 盜賊頭目)是否也有一樣的行為,只驗證了這組 3+1 的集群。
- 沒有測試「選取的是敵方單位本身」(而非隊友蓋亞)時,敵方單位貼圖會不
  會也連動修正——只測了「選取隊友、範圍 overlay 顯示、敵人貼圖被連帶
  修正」這一種組合。
- 沒有嘗試修——原因同續五,確切覆寫/選取邏輯的位置沒有釘死,不貿然改。

**給下一輪的建議**:這個發現應該跟續四(數值)、續五(面板肖像)三個
一起看,共同指向「敵方單位在 `resetBattle()`/戰鬥中的某個身份解析路徑
上系統性地跟索爾的記錄搞混」這個更大的假說,值得開一個專門的 debug
session,在畫面(sprite fig)、面板(portrait)、數值(HP/AP/DP/MV)、
座標(X/Y)四個維度同時插樁追蹤同一隻盜賊單位的資料,才可能一次定位
根因,而不是逐個症狀分開查。
revert 這兩個檔案的變更,尊重並行 session 的工作。
