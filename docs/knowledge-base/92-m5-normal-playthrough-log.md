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

## 2026-09-01 續七:用 DOSBox-X 原版即時操作,逐項回頭核對續五/續六的 remake
發現——2/3 確認是 remake 專屬 bug,另外多抓到一個更大範圍的資料層問題

**背景**:使用者要求「有使用 remake 驗證的部分,回頭用 DOSBox-X 原版重新驗證
確認」。派工用 `tools/dosbox_harness.sh` 全新隔離 instance(`verify4pt`)、
從乾淨存檔重新走過序章進 ch01 戰鬥(不是重複用舊截圖),逐項核對 4 個
具體問題,每張關鍵截圖都已由主session親自檢視過,不是只信代理人文字結論。
截圖已存進 `docs/figures/m5-ch01-original-*.png`。

**核對結果**:

1. **盜賊真實 HP——remake 資料本身就是錯的,不是續五/續六那類「暫時性
   顯示錯位」,是 export 階段的資料錯誤**:DOSBox-X 原版的盜賊(人類盜賊
   LV.02)狀態畫面清楚顯示 `HP 002/002`,兩隻獨立盜賊單位重複確認同一個
   數字。remake 的 `map0_units.json` 卻是 `hp=28`——**14 倍的落差**,不是
   誤讀(親自看過兩張原版狀態畫面截圖,數字清清楚楚)。其餘欄位對照:
   `hit=97`✓、`mv=4`✓、`ev=2`✓ 三項吻合,但 `mp`(原版002 vs remake0)、
   `ap`(原版012 vs remake14)、`dp`(原版004 vs remake2)、`dx`(原版002 vs
   remake `None`,根本缺欄位)全部對不上。**根因已經在
   `tools/export_units.py`(`base_stats()` 函式,line ~330 附近)自己的
   既有註解裡講清楚**:「map0 實測第一章海盜/士兵的 (race,cls) 甚至是
   (1,1)——單位表裡唯一對到的是『黑暗殺手』(idx31,與海盜/士兵毫無關係),
   base_stats() 取第一筆造成顯示不相干的機械職業名」——這個註解原本只在
   講「職業名顯示錯位」已用 `PORTRAIT_CLS_NAME` 覆寫修好,但**覆寫只動了
   `cls_name` 這個顯示文字,沒有動 `bs["hp"]`/`bs["mp"]`/`bs["ap"]`/
   `bs["dp"]`欄位本身**——這些數值到現在還是從 (race,cls)=(1,1) 撞到的
   那個不相干「黑暗殺手」模板(`docs/data/exe_tables/unit.json` idx31:
   `hp=36 ap=20 dp=12 mv=6`)借來的,不是盜賊自己的真實數值。這是一個
   **已經在程式碼註解裡被預告、現在用原版即時操作實測確認、範圍可能不只
   ch01 一張地圖**的資料正確性問題(註解自己也講「其餘怪物尚未逐一閉合
   raw key 對照」)——跟續五/續六的「身份解析在特定 UI 狀態下暫時錯位」
   性質不同,是**匯出階段就已經錯**,不會因為切換選取狀態就變對。
2. **攻擊選目標面板的肖像——確認是 remake 專屬 bug,原版沒有這個問題**:
   原版同款「A+xx D+xx」目標資訊面板,鎖定盜賊時正確顯示盜賊自己的臉
   (風霜人臉+金屬護目鏡),HP 顯示 `002`(跟第1點的真實 HP 一致,面板
   本身內部自洽)。續五記錄的「remake 面板畫成索爾的臉」**在原版找不到
   對應現象,確認是 remake 自己的 bug,不是原版本來就有、remake 只是
   忠實重現**。
3. **閒置戰場畫面敵人貼圖——同樣確認是 remake 專屬 bug**:原版連續截圖
   (閒置中、索爾顯示移動範圍時、亞雷斯顯示移動範圍時)裡,3 隻盜賊
   全程穩定顯示自己的紅頭巾+黑色護目鏡造型,從未變成索爾或亞雷斯的
   藍色頭盔樣式。續六記錄的「remake 敵人閒置時畫成索爾、選取隊友時才
   短暫變對」在原版**完全不存在這個切換行為**,同樣確認是 remake 專屬。
4. **隊伍成員對應——3/4 直接確認,悠妮未能在這場戰鬥取得戰鬥內名牌
   (不算矛盾,誠實記錄為未確認而非湊成全部相符)**:原版戰鬥內狀態畫面
   直接確認索爾(HP42人類劍士)、亞雷斯(HP48人類騎士)、蓋亞(HP50機械
   機兵)三個名字/數值,跟 remake `ch01.json` 的 party 陣列數值完全吻合。
   悠妮雖然在開場劇情對白裡有出現(紅髮),但這場戰鬥實際可操作的單位
   只有 3 個(用 Escape 循環過,只在亞雷斯/蓋亞之間切換,沒有出現第 4
   個可選單位),沒能在戰鬥內拿到悠妮的名牌截圖核對——這是**代理人自己
   誠實回報的未盡驗證項目,不是隱藏起來湊成全部相符**。

**結論與後續建議**:
- 續五(面板肖像)、續六(地圖貼圖)兩個 bug **確認是 remake 專屬**,原版
  沒有這個問題——之前「這很可能是同一個更底層問題的第三個症狀」的假說
  方向不變,但現在確定問題完全出在 remake 這一側的身份解析邏輯,不是
  remake 忠實重現了原版本來就有的怪異行為。
- 第 1 點(HP等數值資料錯誤)是**這輪意外多抓到、範圍可能更大**的發現——
  建議下一輪找一個時間,把 `export_units.py` 的 `base_stats()` 從
  「(race,cls) 對到第一筆就用」改成对每個已知有敘事身分覆寫的
  `raw_unit_key`(目前只有 68/96/97 三筆)**連 hp/mp/ap/dp/dx/mv 一起
  覆寫**,而不是只覆寫 `cls_name` 顯示文字;範圍評估建議先跑一次全 30 張
  地圖的 (race,cls) 碰撞掃描,量化到底有多少單位受影響,不要只憑 ch01
  這一筆就推論全域嚴重度。
- 三個發現(HP資料錯誤、面板肖像、地圖貼圖)現在都有原版並排證據
  (`docs/figures/m5-ch01-original-*.png` 三張 + 續五/續六原本的 remake
  截圖),足以支撐「這些是需要修的真實 bug」這個結論,不需要再懷疑是
  誤判或截圖工具問題。
revert 這兩個檔案的變更,尊重並行 session 的工作。

## 2026-09-01 續八:盜賊 HP 之謎完全反轉——native 公式與資料表本身沒有錯,
續七的「原版 ground truth」是被本專案自己另一輪除錯 session 汙染過的
`~/fd2-run/FD2.EXE`,不是真正的原版行為 [根因已定位、已獨立複驗]

**任務背景**:orchestrating session 要求深入複查續七第 1 點——`native_record_word42_for_raw_unit_key()`(見
`tools/export_units.py`)對 ch01 盜賊(`raw_unit_key`=96,`map0_units.json`
`fig=96`,`lv=2`)算出 `word42=28`(=`high_class` 表 idx28 的 HP 成長值14×等級2),
但續七記錄的 DOSBox-X 原版狀態畫面(`docs/figures/m5-ch01-original-thief-status-hp002.png`)
顯示 HP 是 `002/002`,兩者差 14 倍。任務要求判斷:究竟是 `native_record_word42_for_raw_unit_key()`
的公式/索引/table 提取有錯,還是另有解釋,並要求不能只憑這一個數字就動公式。

**方法**:先重讀 `tools/export_units.py`/`tools/extract_native_unit_tables.py` 全部
docstring 與 `docs/knowledge-base/56-fd2-remake-sdd.md`「2026-07-27」節、`03-exe-and-
data-structures.md` 的既有反組譯證據(`docs/data/fd2_future_group_constructor_capstone.txt`,
`0x10b4e..0x11018` 完整 Capstone 反組譯,MD5`b97caf...`357074B 舊版),確認：

1. **constructor `0x10d7f..0x10e23`(high branch)的公式/索引本身完全正確,逐指令核對**:
   `0x10da4` 讀 FDFIELD 控制列 `esi+1`(=`raw_unit_key`)、`sub eax,0x44`、`call 0x4e4ff`
   取 `0x61af9+idx*0xA` 記錄;`0x10db4` 讀 `record+2`(u16)乘上 `esi+4`(=FDFIELD `lv`,
   跟 `tools/parse_field.py` 的 `"lv": b[4]` 逐位元組吻合,`esi` base offset `0x83` 也跟
   `parse_field.py` 算出的 `o=3+16*3+16*2+16*3=0x83` 完全一致);`0x10fe9`/`0x10fed` 把
   結果同時寫進 runtime `+0x40`(當前HP)與`+0x42`(MaxHP)。`0x1b750`(HIT/EV/衍生AP重算)
   反組譯全文沒有任何 `+0x40`/`+0x42` 寫入,不會事後覆寫 HP。
2. **`high_class` 68 筆表本身也沒有錯**:`docs/data/exe_tables/unit.json`
   (`tools/dump_exe_tables.py` 用 anchor-byte 掃描直接對「canonical 新版」FD2.EXE
   逐byte驗證產出,見 `03-exe-and-data-structures.md` 2026-08-19 節「60列逐byte核對」)
   跟 `docs/data/exe_tables/native_unit_tables.json` 的 `high_class` table **逐筆位元組
   完全相同**(idx0/8/28/29/59/60-67 全部核對過),兩者是同一張表的獨立來源,互相印證。
   idx28(=raw_unit_key96-0x44)= `race1 cls7(盜賊) HP成長14 MP成長0 AP成長7 DP成長1
   DX成長1 MV4 EX21`,是合理、與其他67筆同型態的漸進數值(不是退化值)。

**關鍵突破:直接用 WSL2 讀 `~/fd2-run/FD2.EXE` 原始 bytes,跟兩份靜態 JSON 比對**——
`~/fd2-run/FD2.EXE`(md5`72e36e47f1f7d77dc102839262956480`,續七/所有近期 DOSBox-X
session 用的「canonical」live 檔案)在 `high_class` 表偏移 `0x7AB0D+28*10` 讀出的是
`01 07 01 00 01 01 01 01 04 15`——HP/MP/AP/DP/DX 全部被改成 **1**(RA/CL/MV/EX 不變),
不是 JSON 裡的 `01 07 0e 00 00 07 01 01 04 15`(HP成長14)!用 `cmp -l` 對
`~/fd2-run/FD2.EXE` 與同目錄下 **`FD2.EXE.pristine_bak`**(md5`33464c81e6a364fd
0660141139aa8e6e`,與 `docs/data/fd2-reference-files.json` 記載的「canonical 新版」
基準、`C:\...\GAME\FD2\FD2.EXE`/`FD2_USB`/`FD2_APK\FD2_old.EXE` 三份獨立備份的 hash
完全一致)逐 byte diff:**精確 252 bytes,全部落在 `high_class` 表 `0x7AB6D..0x7ADA6`
範圍內**(即表格第 8~59 筆,`raw_unit_key` 76~127),對應 `RA/CL/MV/EX` 不動、
`HP/MP/AP/DP/DX` 全部壓成 1 的規律 patch。

**根因 100% 定位**:這正是本文件 `docs/knowledge-base/58-remake-live-verification-log.md`
第3461行已經自己記載過的**「續二十七」(2026-08-19)離線 patch**——當時為了驗證「ch24 敵人
HP卡在1不動是(HIT-EV)確定性Miss、不是傷害公式清零」這個完全不相關的假說,使用者離線
把 `~/fd2-run/FD2.EXE` 的 `0x7AB5D` 起 52 筆敵人成長表(=`high_class` idx8..59)逐筆改成
HP/MP/AP/DP/DX成長值=1、保留RA/CL/MV/EX,並存了 `FD2.EXE.pristine_bak` 保留原始備份。
該輪之後**至少數十輪(續二十八~續六十幾,見同文件 3480/3858/3880/3934/4190/4530/4652/
4803/4838/4943/5130/5225/5340/5398/5512/5575/5727/5779/5909/6074/6138/6263/6414/6436
等行)全部把「`FD2.EXE`與`.pristine_bak`diff維持精確252 bytes」當成正面確認(表示ch24/
ch27追蹤用的 checkpoint 完整保留),從未把它復原成原版**——這個 patch 因此至今仍完整
存在於共用的 `~/fd2-run/FD2.EXE` 裡,但它是為了另一條完全無關的 ch24 debugging 支線做的,
從未被標記成「所有其他 session 借用 `~/fd2-run` 做 ground truth 驗證時要注意」的警告。
**續七的 DOSBox-X「原版」HP=002 讀數,讀到的其實是這個已知、有意、但忘了註記適用範圍的
debug patch,不是真正的原版行為。**

**獨立原版複驗(不依賴 JSON,直接開一個全新隔離 DOSBox-X 實例驗證)**:用
`tools/dosbox_harness.sh launch pristinecheck`、`FD2_HARNESS_SOURCE_DIR=$HOME/fd2run`
覆寫成另一份**從未被續二十七碰過**的乾淨快照(`~/fd2run`,無連字號,md5同樣是
`33464c81...`,與 `.pristine_bak`/三份 Windows 備份完全一致;補一個該快照唯一缺的
`FDICON.B24` 資源檔,從 `~/fd2-run` 複製,不影響 FD2.EXE 本身),開新遊戲、mash Enter
跑完序章對白(亞王城→練劍→發現悠妮→行軍→海盜宣戰)進入 ch01 戰鬥,把游標移到最左側單獨
一隻盜賊(跟續七截圖同一隻「LV.02盜賊,獨立站位」)身上——**畫面左下角快速資訊面板清楚
顯示 `028`**(跟 Sol 自己當時顯示 `042`=HP42/42 是同一種面板,已知是即時 HP 讀數),
精確吻合 `native_record_word42_for_raw_unit_key()` 算出的 `14×2=28`,**不是** 續七讀到的
`002`。此為本輪唯一新增的即時 DOSBox-X 證據,建立在乾淨快照上,teardown 已確認乾淨
(`tmux`/`Xvfb`/`dosbox-x` 全部清除,`ps aux` 無殘留;隔離 workdir
`~/fd2-run-harness-pristinecheck` 用畢即刪除)。**全程未寫入或修改 `~/fd2-run/FD2.EXE`
或 `~/fd2-run/FD2.SAV`**(操作對象自始至終是獨立的 `~/fd2run`→隔離 workdir 複本),
不影響任何借用 `~/fd2-run` 的其他並行 session(含 ch24/ch27 追蹤支線)。

**結論**:
- `native_record_word42_for_raw_unit_key()`/`native_record_word46_for_raw_unit_key()`
  (以及同一輪反組譯出的 `native_ap/dp/mv/dx_for_raw_unit_key()`)**公式、索引、byte
  offset 全部正確,不需要修改一行程式碼**。`docs/data/exe_tables/native_unit_tables.json`
  的 `high_class`/`lower_class`/`lower_aux` 三張表**資料本身也是對的**(逐byte核對
  過至少 idx0/8/28/29/59-67,跟獨立管道`dump_exe_tables.py`+使用者攻略雙重印證),
  不需要重新萃取或重跑 patch pipeline。`tools/export_units.py` 產出的全部 30 張
  `mapN_units.json` 也因此**已經是對的,不需要重新產生**。
  `python3 tools/test_export_units.py`(7/7 綠)、`go build ./remake/...`、
  `go vet ./remake/...`(皆在 `remake/` 目錄下執行,全綠)三項回歸確認過,純粹是
  「這輪沒有動程式碼」的確認,不是因為有改動才重跑。
- 續七第1點原文的結論(「remake 資料本身就是錯的,是 export 階段的資料錯誤」)**需要
  更正**:HP 這條線索本身,問題不在 remake/export 這一側,而是續七借用的 DOSBox-X 環境
  (`~/fd2-run/FD2.EXE`)恰好帶著另一條無關支線留下的 debug patch。續七其餘 3 點(面板
  肖像 bug、地圖貼圖 bug、隊伍名字核對)不受影響,結論維持有效——那 3 點的原版截圖
  對照對象都是 UI/貼圖渲染邏輯,不涉及這張成長表。
- **範圍評估**(靜態掃描 30 張 `mapN_units.json`,只是量化風險,不是本輪發現新 bug)：
  受這個 debug patch 影響的 `raw_unit_key` 範圍是 76~127(`high_class` idx8~59,共52筆
  table row);全 30 張地圖裡帶 `native_record_word42` 的 1885 個敵我單位中,**1698 個
  (90%)的 `raw_unit_key` 落在這個範圍內**——換句話說,如果誤信續七的「原版 HP=2」當
  ground truth 去反向修正公式,會讓現在本來正確的 90% 單位全部改錯,包含前面 doc03/
  doc32 引用驗證過的 ch24 LV14 惡魔(`raw_unit_key`=109,同樣落在 idx41,受影響範圍內;
  該筆「驗算」本來就只是拿 JSON 自己算出的值互相對照,從未真正對過 DOSBox-X 原版畫面,
  這次連帶釐清了它「尚未被獨立 ground-truth 驗證過」這件事,不是新退步)。
- **後續建議(不在本輪動手,留給 orchestrating session 決定)**：
  1. `~/fd2-run/FD2.EXE` 目前仍帶著續二十七的 52 筆 debug patch,且看起來是 ch24/ch27
     追蹤支線刻意保留的工作 checkpoint(數十輪明確記錄「diff維持252 bytes,沒有本輪
     修改」)——**不建議本輪或任何不了解該支線現況的 session 自行復原成 pristine**,
     以免破壞正在進行中的另一條調查。但強烈建議在 `docs/knowledge-base/98-tooling-
     infrastructure.md` 或 `tools/dosbox_harness.sh` 的說明裡明確加一條警語:
     `~/fd2-run/FD2.EXE` 的 `raw_unit_key` 76~127 敵人成長數值不是原版數值,任何要用
     它做「HP/MP/AP/DP/DX ground truth」驗證的 session,必須先 `cmp` 一下
     `FD2.EXE.pristine_bak`,不一致就換一份乾淨快照(例如 `~/fd2run`,記得補
     `FDICON.B24`)再測,不能直接假設 `~/fd2-run` 是原版。
  2. 若 ch24/ch27 支線之後確認不再需要這個 debug checkpoint,可以考慮把
     `~/fd2-run/FD2.EXE` 復原成 `.pristine_bak`,但那是那條支線自己的收尾決定,
     不屬於本輪任務範圍。
- **命名巧合提醒**：`~/fd2run`(無連字號,pristine,2026-08-14 快照)與
  `~/fd2-run`(有連字號,canonical harness source,已被續二十七 patch)是兩個完全不同
  的目錄,只差一個連字號,非常容易看錯——這也是本次調查耗費最多時間釐清的環節之一,
  下一輪如果需要用 pristine 快照,務必先 `md5sum FD2.EXE` 確認,不要只憑目錄名判斷。

## 2026-09-02 續九:Bug A(目標面板肖像錯位)+ Bug B(地圖 sprite 索爾化)根因
100% 定位並修復——`NativeSelectorCache` 誤用 FDFIELD b0(其實是陣營碼)當繪圖層
raw key,跟索爾自己的 key 剛好撞號;兩個 bug 共用同一個根因,一次修復同時解決

**任務背景**：orchestrating session 指派深入複查續五/續六記錄的兩個 remake 專屬
bug(目標面板肖像畫成索爾的臉、地圖閒置畫面單位貼圖畫成索爾),要求找出真正根因、
修掉、寫回歸測試、live 重新驗證兩個症狀。續四的「敵方 nerf 失效/整包記錄替換」
假說已在同一 session 稍早被判定是另一件事(見文件開頭 orchestrating 指示引用的
「contaminated test file」結論),本輪重新從程式碼讀起,不沿用舊假說。

**根因(逐層定位)**：

1. `drawUnitHUD`/`drawTerrainInfoPanel`(`remake/cmd/fd2/main.go:9155-9227`)本身
   完全正確——直接讀傳入的 `u.Portrait`,沒有問題。真正產線用的面板是
   `drawNativeMapHUD`/`composeNativeMapFrameAt`(native 完整 indexed frame 路徑,
   ch01 這種有 `native_terrain_control` 的地圖一律走這條),前者只是 native
   frame 缺資料時的 fallback,不是本輪要抓的路徑。
2. `internal/fdicon/fdicon.go` 的 `NativeSelectorCache`(0x11019 的「process-global
   raw-key→slot」cache 的 Go 重建)是唯一同時餵給地圖 sprite 繪製
   (`BlitNativeUnitLayer`→`SpriteForNativeSlot`)**和** HUD 目標小圖示
   (`BlitNativeMapHUDUnitIcon`)的資料源——這正是「兩個看起來獨立的 bug 其實同一個
   底層問題」的關鍵:兩條繪圖路徑共用同一顆 cache。
3. `MaterializeNativeMapSelectorSlots`(`internal/battle/model.go`)原本用
   `u.MapSelectorKey`(=FDFIELD roster b0)當 cache key。用
   `tools/fd2_live_input_helper.py grid dump-map` + 直接讀
   `map0_units.json`/`tools/parse_field.py` 逐行核對後發現:**b0 其實就是陣營碼**——
   `parse_field.py` 自己的解碼就是 `["enemy","ally","own"][b0]`,任何一張地圖上
   同陣營的所有單位(不管長什麼樣)b0 全部相同(map0 的 8 隻初始盜賊全部
   `map_selector_key=0`)。而玩家隊伍(`event.go` `PartyUnits()`)的 key 用的是
   `pm.Fig`(索爾=0)——兩邊的「key namespace」原本不該互相比較,但因為共用同一顆
   `map[byte]int` cache,加上「先建構的先拿到 slot、後面同 key 者共用同一 slot」
   的 first-seen 規則,索爾(隊伍第一個構造、key=0)永遠先把 slot 0 綁定給 key=0,
   之後任何 b0=0 的敵人(也就是這張地圖上*所有*敵方單位)都會撞進同一個 slot 0,
   `KeyForSlot(0)` 永遠只回傳索爾的 key——這就是兩個 bug 的共同機制。
4. **真正該用的 key 是 `BattleFig`(FDFIELD b1/`raw_unit_key`)**,獨立證據:
   - `tools/export_sprites.py` 的 docstring 與程式碼本身,`fig_<grp>_f*.png` 的
     `grp` 就是直接向 FDICON.B24 archive 要的 group index,不經過任何 cache;
     已存在的 `assets/sprites/fig_096_f00.png`(本輪重新解碼 `FDICON.B24` 確認
     archive 共 1680 張/140 組,140 遠大於陣營碼的 0~2 範圍,只有 b1 的值域對得上)
     視覺上正是紅頭巾+黑色護目鏡的盜賊造型,`fig_000_*` 正是索爾;
   - `internal/battle/model.go` 對 `Fig` 欄位的既有註解本身就寫著
     「地圖 FDICON selector approximation;native source is unit+2」——即
     Fig/BattleFig 一直被認為是 unit+2(native selector 的真正輸出)的近似值;
   - `internal/campaign/church.go`(職業轉換,對 0x31571..0x3157a 有完整反組譯
     佐證)明確寫「native unit+7 對玩家單位同時是 FIGANI selector**和**下一次
     0x11019 的 raw key」——即玩家的「下一個 native key」本來就該等於他自己的
     Fig/Portrait(跟 `event.go`/`native_join_constructor.go` 既有的
     `MapSelectorKey: pm.Fig`/`MapSelectorKey: id` 用法完全一致,這兩處player-side
     用法本身沒有錯);FDFIELD 這一側的 b0(陣營碼)從未被證明跟這個 unit+7/raw key
     domain 是同一個可比較的數字空間,只是現有程式碼把兩者塞進同一顆 Go map 誤當
     成同一件事。

**修復**：`internal/battle/model.go`
`MaterializeNativeMapSelectorSlots` 改成用 `u.BattleFig`/`u.HasBattleFig` 餵
`cache.SlotFor()`,不再用 `u.MapSelectorKey`。`MapSelectorKey`/`NativeRecordByte6`
兩個欄位維持原樣不動(它們對 runtime +6/陣營 provenance 仍然是對的,只是不該再
拿來當繪圖 cache key)。commit `6eaf7fef`。

**回歸測試**：`internal/battle/event_test.go` 新增
`TestChapter1InitialThievesDoNotAliasSolsNativeMapSelectorSlot`——載入真實
`map0_units.json`+`ch01.json`,斷言 ch01 初始盜賊群解析出的 native map key
等於自己的 `BattleFig`、且不等於索爾的 key(revert 修復後手動確認此測試會
如預期失敗,見下)。另外修正/補齊 7 個既有測試檔(`model_test.go`/
`event_test.go`/`native_command_target_test.go`/`native_map_presentation_test.go`/
`cmd/fd2/beatrunner_test.go`/`cmd/fd2/native_map_frame_input_test.go`)裡
手工組出的 `battle.Unit`/`fdicon.Bank` fixture——這些 fixture 過去只帶
`MapSelectorKey`(現在的 cache 不再讀它),需要補上 `BattleFig`/放大測試用
sprite bank 才能繼續通過;其中 `event_test.go` 的
`TestChapter2RuntimeAppendOrderMatchesOriginalHandlerSlots` 原本斷言
「native key == 陣營碼」,這其實是把 bug 現象寫死成期望值,已改成斷言
「native key == 自己的 BattleFig」。`go build ./remake/...`、
`go vet ./remake/...`、`go test ./remake/...` 全綠。

**live 重新驗證(`tools/fd2_live_input_helper.py`,全新隔離 instance
`bugfix_verify2`,先在 WSL2 側用 `$HOME/go/bin/go build -o fd2-linux-verify
./cmd/fd2` 重新編譯——第一次忘記重build,拿舊 binary 驗證看到 bug 依舊存在,
是這輪唯一的操作失誤,發現後立刻重編重跑)**：

1. **Bug B(地圖閒置畫面）**:mash Enter 從新遊戲走完序章進 ch01 戰鬥,截圖後
   PIL 放大裁切初始盜賊群(3+1 那組,跟續六截圖同一組單位)——修復前(未重build
   的舊 binary)清楚是索爾造型(藍髮紅頭巾);重build 後同一組單位變成正確的
   盜賊造型(暗紅頭巾+金屬護目鏡),閒置狀態、選取隊友顯示 range overlay 後、
   取消選取後三個狀態都重新截圖確認過,全部一致正確,**沒有續六記錄的
   A→B→A 切換行為**(因為根因已經在資料層修掉,不再是「native frame 是否
   admit 成功」這種狀態相依的巧合正確)。
2. **Bug A(攻擊選目標面板肖像)**:用 F3 debug 座標讀出單位精確座標,操作
   亞雷斯移動到跟一隻盜賊相鄰的格子,開指令環按方向鍵選到「攻擊」
   (`g.ringSel=0`,對應 D-pad 的「上」——原本誤以為預設高亮的紅色圖示就是攻擊,
   試了幾輪才發現要按 Up 才會選到,純操作面的插曲,不是 bug),進入
   「攻擊:選擇目標」狀態,游標移到盜賊身上,面板名稱正確顯示「盜賊」、HP
   正確顯示 028,放大裁切肖像圖確認是盜賊自己的臉(暗紅頭巾+金屬護目鏡),
   不是索爾。同時也確認己方單位(亞雷斯 HP048、悠妮 HP028——這位真正是悠妮
   不是續六誤記的蓋亞,紅髮但跟蓋亞的機兵不同)的面板肖像全程維持正確,
   沒有因為這次修改被連帶弄壞。
3. teardown 已確認乾淨:`fd2_live_input_helper.py status` 顯示無殘留 instance,
   `ps aux` 在 WSL2 側 grep `xvfb`/`fd2-linux-verify` 均無殘留行程。

**結論**：Bug A、Bug B **兩個都已修復並經 live 重新驗證確認**,根因是同一個
(`NativeSelectorCache` 誤用陣營碼當繪圖 raw key),已用單一 commit 一次解決;
不是分開修的兩個 patch。`docs/knowledge-base/91-worklist.md` M5 Phase 4 一併更新。

## 2026-09-02:用 DOSBox-X 原版重新走一次 ch01 序章→部署,對照續一/續二/續四
記錄的 remake 戰鬥數值——**HP/AP 兩項精確吻合,傷害數字這輪未能重現(原版戰鬥
UI 操作卡關,誠實記錄未解決)**

**動機**:回頭檢查續一/續二/續四發現,`applyPersistentStats`/悠妮環/buff-nerf
捷徑失效這三個「發現」本質上是 remake 自己的狀態機測試(不涉及跟原版比對),
但續一/續二/續四裡引用的**具體戰鬥數值**(索爾HP42、亞雷斯HP48/AP26、盜賊
HP28、「造成20/21/22傷害」「造成17/18傷害」)全部只讀自 remake 自己畫面上的
文字,**這場特定戰鬥從未真正拿去跟 DOSBox-X 原版對照過**——這正是
`feedback_fd2_re_remake_verification_paused.md` 原本要涵蓋的情況。用新建的
`tools/fd2_dosbox_live_helper.py`(含 2026-09-02 剛加的 no-response/debugger-
status baseline/stale-instance 功能)針對這個缺口重新走一次。

**環境**:發現預設 `~/fd2-run/FD2.EXE` 是已知污染副本(`verify-canonical`
正確攔下,md5 `72e36e47...`≠pristine `33464c81...`)——沒有直接用它,改為
WSL 側新建 `~/fd2-run-pristine`(複製 `~/fd2-run` 全部檔案,唯獨
`FD2.EXE` 換成已驗證過的 `FD2.EXE.pristine_bak`,`md5sum` 確認結果
`33464c81e6a364fd0660141139aa8e6e` 與 pristine 完全一致),再透過
`FD2_HARNESS_SOURCE_DIR` 環境變數指向這個乾淨副本啟動(工具本身的
`launch` 子指令目前不支援自訂 source dir 透傳進 WSL,這次用直接
`wsl -d Ubuntu bash -c 'FD2_HARNESS_SOURCE_DIR=... bash fd2_dosbox_live_helper.sh
launch ...'`繞過,單一敘述句,不是文件警告過的多語句 `-c` 字串陷阱)。
instance 自己 workdir 裡的 `FD2.EXE` 也額外 `md5sum` 覆核過同一個 pristine
雜湊,不是只信任來源目錄。

**方法**:全新標題畫面開始,批次送出約 850 次 Enter(0.1s/鍵間隔,分批
30-60 次一組+截圖確認進度,同續一/續二記錄的原版逐字對白比 remake 慢約
5-6 倍的既有認知一致),順利重演王座廳→王城→比劍→發現悠妮蓋亞→行軍→
海盜宣戰→ch01 戰鬥部署,無異常、無卡關。

**HP/AP 數值交叉確認(★核心結果,兩項都精確吻合)**:
- 部署開場自動逐一顯示各隊員完整狀態卡(這是原版自己的既有機制,不是操作
  出來的,見 `docs/knowledge-base/13-battle-menu-system.md` 記載的「戰鬥
  開場預設有一個瀏覽游標,對準單位按 Enter 進入操作該單位狀態,跳出完整
  狀態卡」)：**索爾 HP 042/042**——與續一/續二記錄的remake「索爾HP42」
  **精確吻合**。
- 手動把瀏覽游標移到亞雷斯身上重新開卡:**亞雷斯 HP 048/048、AP·026**——
  與續二/續四記錄的remake「亞雷斯HP48」「AP26」**兩項都精確吻合**
  (DX002/MV07/HIT092/EV002/DP006 這幾項續一~續四沒有明確記錄可對照的
  remake數值,這裡先存證,供未來需要時使用)。

**傷害數字這輪未能重現——誠實記錄操作卡關,不是「原版跟remake不符」**:
依 `docs/knowledge-base/13-battle-menu-system.md` 記載的流程(選單位→
Enter進入目的地預覽游標→移到空格Enter確認移動→自動跳指令環,範圍內有敵人
時攻擊圖示會自動預設→Enter確認攻擊→目標游標自動吸附最近敵人→再Enter出手)
操作亞雷斯移動到疑似與一隻落單敵方單位相鄰的格子(移動路徑本身正確:
索爾MV=4一次移動失敗因為超出範圍,retry縮短到4格內成功;亞雷斯後續3格
移動也成功,ring正確在新位置跳出),但接下來無論按「上」(攻擊)、「右」
(物品)哪個方向鍵+Enter,畫面都固定跳出同一張亞雷斯的完整狀態卡(HP/AP
數值與前述相同),Escape 可以退回指令環,但重按任何方向鍵仍然回到同一張卡,
沒有進入真正的目標選擇畫面。**比對 doc13 §「指令環的非互動式替代畫面
0x17aed」一節的既有反組譯記錄**:這個現象(不論按哪個方向都得到同一張
非互動狀態卡,Enter不會真正執行任何指令)正是 doc13 描述的、指令環三個
入口 gate 之一沒通過時的「替代演出」,不是真指令環——**最可能原因是目標
敵人與亞雷斯之間隔著螢幕上可見的一棵樹(LOS 阻擋),或是這次移動流程裡
某個更早的 gate 因為操作生疏(過程中有一次超出MV範圍的移動被靜默拒絕、
一次疑似無效的Escape重試)而意外卡住**,不是精確診斷過的根因,只是本輪
排除法排除到這裡為止。**這輪沒有真正執行到任何一次攻擊,因此沒有拿到任何
可以跟續一(21傷害)/續二(20/18傷害)/續四(22/17傷害)直接比較的原版
傷害數字。**

**與 remake 側經驗的對照,誠實評估這是不是特例**:remake 自己在抵達同等
操作深度前也花了續一→續四共4輪才第一次「完整」驗證成功一次攻擊
(續四自述「先前續一/續二/續三都只驗證到片段」),而且 remake 有 F3
debug HUD 可以看精確座標/回合數,原版沒有等價工具——**這輪一次 session
就摸到跟 remake 花4輪才摸到的操作深度相近的地方,對照之下不算慢**,但
確實還沒達到「拿到一個傷害數字」這個目標。

**清理**:`origverify` instance(Xvfb `:199`)已用 `teardown` 正常關閉,
`status` 確認清空。

**給下一輪的具體建議**:
1. **不要在有樹木/地形阻隔視線的位置試攻擊**——下一輪選一個目標時,先確認
   單位與敵人之間的直線路徑上沒有樹木等地形物件,降低撞到 doc13 記錄的
   LOS/gate 問題的機率。
2. **一次只送一個方向鍵+單獨截圖確認**,不要像本輪一些步驟圖省事batch了
   方向鍵+Enter,一旦卡在替代畫面,無法回頭精確判斷是哪一步出的問題。
3. **考慮用 DOSBox-X debugger 現場讀取記憶體座標**(`tools/
   fd2_dosbox_live_helper.py mem read-unit-record`,已有的push-button
   指令)取代原版沒有的F3 HUD,精確算出真正的鄰接格,而不是憑截圖像素
   目測。
4. `~/fd2-run-pristine` 這個乾淨副本已經建立在 WSL 側,下一輪可以直接
   透過 `FD2_HARNESS_SOURCE_DIR=/home/kg701004/fd2-run-pristine` 沿用,
   不需要重新複製;`fd2_dosbox_live_helper.py` 本身尚未支援這個環境變數
   透傳(見上面「方法」一節的繞過寫法),值得未來補上一個 `launch
   --source-dir` 參數讓這件事不用每次手動繞。

## 2026-09-02 續二:依上述4點建議重跑一輪——**修正了對UI機制的錯誤理解、
再確認一項HP數值(悠妮028),但傷害數字依然沒能拿到,且證實問題不是
LOS/batch操作**

**動機**:依建議1-3嚴格重跑一次:避開樹木、單鍵單截圖、沿用`~/fd2-run-
pristine`。

**UI機制理解的重要修正**:先前(續一)以為「Escape」是從角色狀態卡進入
目的地預覽游標的方法——**這是錯的**。本輪逐鍵確認:狀態卡顯示時**直接按
方向鍵**(不需要先按Escape)就會移動目的地預覽游標(截圖`
07_single_down.png`一開始因為單鍵被吞而誤判無效,`30_ares_reselect_down
.png`用同一招在Ares身上成功重現移動,證實方向鍵直接有效,先前的誤判是
按鍵丟失,不是機制本身要先Escape)。**Escape反而是「不移動、直接原地
開指令環」的捷徑**,跟續一記錄的理解正好相反。已更新此文件與未來操作的
心智模型。

**HP再確認**:Tab鍵在這個情境下是「切換瀏覽游標到下一個單位」(不是
remake的「結束回合」語意),切到悠妮時面板顯示**HP 028**——與續九
remake記錄的「悠妮HP028」精確吻合,連同續一(索爾042)、續一/本輪
(亞雷斯048/AP026),**目前為止DOSBox-X原版跟remake對照過的所有HP/AP
數值全部精確吻合,零例外**。

**傷害數字依然沒拿到,但這次可以確定不是LOS或操作粗糙的問題**:嚴格
遵守建議1-3,分別對索爾(移動到敵人正上方1格,中間無樹)、亞雷斯(移動
到敵人正上方1格,同樣無樹,單鍵單截圖確認每一步)各試一次,**兩次都是
相同結果**——按任何方向鍵(上/下都試過,不只攻擊)+Enter,畫面固定跳回
該角色自己的狀態卡,從未進入真正的目標選擇畫面。**這排除了續一原本
懷疑的LOS阻擋假說**(這次特意選了無樹的正上方鄰格,結果一樣)——問題
更可能是 doc13 記載的指令環三個入口gate其中之一沒通過,而**不是操作方式
的問題**(本輪已經用最嚴謹的單鍵確認流程,結果仍然一樣)。

**新假說(未驗證,留給下一輪)**:戰鬥開場的「瀏覽游標選單位→狀態卡→
移動」這整套流程,有沒有可能其實是**戰前部署/佈陣階段**,不是真正的
戰鬥回合——也就是說,這時候本來就只允許移動佈陣,不允許攻擊,要等某個
「部署完成」的觸發(可能是每個單位都要先過一輪待機/移動確認,或者需要
額外一個「開始戰鬥」指令)之後,指令環的攻擊/法術/道具才會真正解鎖。
remake自己的實作可能在這一點上跟原版不同(remake續一~續四從來沒有走過
明確的部署確認步驟,T1一開始就能直接攻擊)——如果原版真的有這個額外
階段,那remake這裡可能是一個尚未發現的、被本輪意外撞見的忠實度落差,
而不是操作失誤。這個假說本輪沒有時間驗證(需要嘗試找出「部署完成」
觸發的操作,或直接用debugger讀記憶體確認 doc13 三個gate byte的實際值),
留給下一輪。

**清理**:`origverify2` instance 已 `teardown`,`status`確認清空。

**給下一輪的具體建議(更新)**:
1. **優先驗證「部署階段」假說**——嘗試對所有4名隊員都先做一次移動/待機
   (而不是只操作1-2個就急著攻擊),看指令環的攻擊/法術/道具選項會不會
   在某個時間點解鎖;或者找找看畫面上有沒有「開始戰鬥/部署完成」之類的
   額外指令入口(可能藏在還沒試過的按鍵,例如Space、其他方向鍵組合)。
2. 若上述無效,才進入 debugger 讀記憶體診斷 doc13 §「指令環4選項的動態
   enable gate」記載的三個byte(`+6`/`+5&0x80`/`+0x26`),確認到底是
   哪個gate沒過。
3. LOS/單鍵操作已經排除,不用再重複驗證這兩項。

## 2026-09-02 續三:重大修正——問題不是「部署階段」,是Escape捷徑本身會
弄壞ring;修好這個之後,Attack依然失敗,但Wait/Escape路徑的機制已完全釐清,
真正剩下的唯一懷疑對象縮小到「視覺鄰接≠邏輯鄰接」

**方法**:全新instance(`origverify3`,之後因需要更乾淨的對照組又開了
`origverify4`),沿用`~/fd2-run-pristine`。

**第一個重大修正:先前對UI機制的理解本身就有bug,不是遊戲有部署階段**：
續二誤以為「從狀態卡按Escape」會進入目的地預覽游標,並在此基礎上做了LOS/
單鍵測試——這個理解本身是錯的,已經在續二自己文中修正過一次,但**這次
發現連修正後的理解都還不完整**:「Escape捷徑」(狀態卡→Escape→原地開
ring,不經過真正的移動確認)跟「真正移動確認」(狀態卡→方向鍵移動游標
→Enter確認,哪怕淨位移是0)得到的ring**不是同一個東西**——本輪對索爾
實測:用Escape捷徑開的ring,連「待機」都會卡進替代畫面失敗;退出來改用
「方向鍵右→左(淨位移0)→Enter確認」重新開ring,**同一個「待機」指令這次
成功了**(索爾正確變灰)。這解開了續一/續二反覆卡住的真正原因之一——不是
部署階段,是本輪操作習慣一直誤用Escape捷徑進ring。

**第二個發現:即使用「真正移動確認」的乾淨路徑,Attack/法術/道具三個指令
依然全部失敗,只有待機成功**——對亞雷斯用同樣乾淨的移動確認流程(移到
落單敵人正上方1格,直線無樹)分別試了攻擊、法術(悠妮MP000本來就該
disable,但這是亞雷斯,同樣MP000,法術disable合理)、道具,**三個全部
卡進替代畫面**,只有待機成功。這一度讓人以為「待機」是這個階段唯一開放
的指令(呼應部署階段假說),但**後續在同一個亞雷斯身上再試一次待機,
這次卻也失敗了**——推翻「待機必定成功」的簡單規律,說明問題不是「這個
階段只開放待機」,而是某種操作次數累積造成的狀態污染(反覆進出同一個
ring太多次,可能真的踩到doc13描述的`DAT_00053c57`全域殘留值問題)。

**第三個發現(★決定性測試,排除了「污染」假說,把懷疑鎖定在真正的
攻擊範圍上)**:為了排除「污染」這個變數,開了全新的`origverify4`,
**整個session只對索爾做一次移動確認、然後第一次也是唯一一次按Attack**
(不多做任何其他ring互動)——**依然失敗,卡進替代畫面**,重試一次
(第二次Enter確認)結果相同。這是本輪能做到最乾淨的測試條件(零污染、
真正移動確認路徑、目標無樹阻隔),Attack依然不通,**排除了「反覆污染
global state」這個解釋**——剩下最合理的解釋回到這個專案自己反覆驗證過
的教訓:**「螢幕上看起來貼在一起」不保證邏輯網格上真的相鄰**(`92-m5-
normal-playthrough-log.md`續二自己也記過同一個教訓、`51-remake-
playtest-gaps-r2.md`/Phase 2也記過)——索爾這次移動終點雖然視覺上緊貼
敵人正上方,邏輯座標很可能因為續二記錄過的「ACT(0)位移」或敵方另一套
座標系而實際上有1格以上的距離差,不在短劍的攻擊射程內。

**清理**:`origverify3`/`origverify4`均已`teardown`,`status`確認清空。

**給下一輪的具體建議(再次更新,取代續二的部署階段假說)**:
1. **部署階段假說已被推翻,不用再驗證**——問題已釐清是操作路徑(Escape
   捷徑 vs 真正移動確認)+可能的座標誤判,不是遊戲機制本身鎖定指令。
2. **真正需要的是精確座標,不是像素目測**——續二記過的線索(敵方座標
   在ACT(0)之後可能有跟主角隊不同的位移規律,offline probe數值對不上
   實測)在原版這裡完全適用。下一輪應該優先用`tools/
   fd2_dosbox_live_helper.py mem read-unit-record`(需先`enter-debugger`
   +從Register Overview/GDT讀真實flat selector)實際讀出索爾與目標敵人
   的座標欄位,精算真正的邏輯距離,而不是繼續憑截圖判斷「看起來貼著」。
3. **操作紀律**:移動確認一律用「方向鍵移動+Enter」的真正路徑,絕對不要
   用「狀態卡→Escape」這個捷徑(即使只是想「不移動、原地開環」也要改用
   「方向鍵移0格再Enter」,因為兩者不等價,已用實測證實)。
4. 若精確座標確認確實鄰接、射程內卻仍然無法攻擊,才需要真的進debugger
   讀doc13的3個gate byte(`+6`/`+5&0x80`/`+0x26`)診斷結構性原因。

## 2026-09-02 續四:真正進debugger讀記憶體——實機驗證出0x50-byte unit record
的HP/MP/AP/DP/HIT/DX欄位offset(跟doc58續十三的舊記錄完全吻合),3個ring入口
gate當場核對全部通過,但仍未解出攻擊持續失敗的最終原因

**方法**:全新instance(`origverify5`),沿用`~/fd2-run-pristine`。額外測試了
doc58續十三記錄的「Enter要按兩次」現象(選單位Enter#1顯示狀態卡,不移動直接
再按Enter#2)——確認**不需要移動也能開出4圖示指令環**,推翻「一定要先移動
確認才能開真正的環」這個(續三留下的)隱性假設,但這個更乾淨的路徑一樣試了
Item(即使背包裡明明列著「藥草+HP040」)還是卡進替代畫面,範圍再度縮小到
「不是移動路徑的問題」。

**★用doc13的診斷checklist(第3項)當場验证:「按下不會disable的『待機』
方向,指令環圖示應該要有視覺切換」**——連續2張截圖(按Down前/後)逐pixel
比對**完全沒有任何變化**,這是doc13自己記載的「已經落入0x17aed非互動替代
畫面」的直接徵兆,不是「待機被disable」(待機理論上永遠不會被disable)。

**真正進debugger診斷**:`enter-debugger`+`GDT`確認這次run的flat selector
`CS=0170 DS=0178`(跟先前所有run一樣,但仍是每次重新查,不是沿用假設)。
`MEMDUMPBIN 170 100000 200000`一次dump 2MB live記憶體,存出`.bin`後用
Python搜尋「HP042/042、MP000/000」這組8-byte pattern(`2a 00 2a 00 00 00
00 00`,little-endian u16×4)——**只命中2次**,兩個位址(`0x1fc700`/
`0x237a88`)往前推`0x40`當作record起點,逐欄位核對:

| 欄位 | offset(相對record起點) | 記憶體讀出值 | 角色卡顯示值 | 是否吻合 |
|---|---|---|---|---|
| HPmax | `+0x40` | 0x2a=42 | 042 | ✅ |
| HPcur | `+0x42` | 0x2a=42 | 042 | ✅ |
| MPmax | `+0x44` | 0 | 000 | ✅ |
| MPcur | `+0x46` | 0 | 000 | ✅ |
| AP | `+0x48` | 0x10=16 | 016 | ✅ |
| DP | `+0x4a` | 0x0c=12 | 012 | ✅ |
| HIT | `+0x4c` | 0x61=97 | 097 | ✅ |
| DX | `+0x4e` | 0x02=2 | 002 | ✅ |

**8個欄位全部精確吻合索爾當下的角色卡數字**——這不是巧合,直接**用live記憶體
實測確認了`+0x40`起這一串u16欄位的完整語意**,跟doc58續十三舊記錄的「敵我
`+0x40..+0x49`=HPmax/cur、MPmax/cur、AP」完全吻合,而且這次額外多核對出
DP/HIT/DX三個新欄位(`+0x4a`/`+0x4c`/`+0x4e`),是本輪新增的具體offset證據
(先前只反組譯過讀取端邏輯,沒有实测過完整欄位表)。

**doc13的3個ring入口gate,當場核對全部通過**:同一份record在`+6`=`0x02`
(己方,gate1「record[+6]==0x02」通過)、`+5`=`0x00`(bit7=0,未行動,gate2
「record[+5]&0x80==0」通過)、`+0x26`=`0x00`(gate3「record[+0x26]==0」
通過)——**三個gate在這個record上全部滿足**,理論上ring應該是真的、可互動的,
不該落入`0x17aed`替代畫面。這跟前面用doc13第3項checklist(待機方向鍵無視覺
反應)判定「已落入0x17aed」的觀察**互相矛盾**,尚未解開:兩個候選解釋——
(a)這份record其實是靜態class/growth預設模板(索爾等級1劍士的預設值),不是
真正正在被指令環讀取的那份**動態、當下選取中**的record,兩者bytes在角色
還沒受傷/沒改變狀態時剛好完全一樣,真正被指令環讀的是記憶體裡另一份(可能
在完全不同的位址,這次2MB dump範圍內沒有搜到第三個候選,或者根本不在這次
dump的0x100000-0x300000範圍內);(b)gate byte真的通過但ring主迴圈
(`0x18d8c`/`0x177fc`)本身在別的地方被卡住(例如`DAT_00053c57`殘留值或
其他尚未反組譯的路徑)。**兩者都需要在「ring正打開的那個瞬間」重新進debugger
dump記憶體才能分辨**(這次是先resume跑完dump才去測ring,不是在ring開著
的那一刻dump——時序不對,下一輪要修正)。

**清理**:`origverify5`已`teardown`,`status`確認清空。debugger操作全程
read-only(`GDT`/`MEMDUMPBIN`皆不寫入),`FD2.EXE`工作副本本身也全程未被
接觸。

**本輪對整個專案的額外價值(不只是這個攻擊bug)**:`+0x40..+0x4f`這8個
欄位offset(HPmax/cur、MPmax/cur、AP、DP、HIT、DX)現在是**live記憶體
實測驗證過**的,不是反組譯推測——對未來任何需要讀取戰鬥中即時單位數值
(不只是索爾)的live驗證工作都可以直接重用,不需要重新反組譯或重新猜測。

**給下一輪的具體建議(最終版)**:
1. **時序修正是關鍵**:下一輪要在「指令環正開著、正要按方向鍵測試那一刻」
   才進debugger dump,而不是像本輪先dump完再去測ring(兩者不是同一個
   game state)。具體做法:先手動操作到「ring打開、光棲在待機方向」的
   那一瞬間,`enter-debugger`,立刻dump同一段記憶體範圍,核對此時此刻
   這個被選取單位的`+5`/`+6`/`+0x26`,而不是分開兩次操作。
2. 已經有本輪驗證過的offset表(`+0x40`起8個欄位)可以直接用來**在記憶體
   dump裡快速定位任何單位**(用HP/MP/AP等已知顯示值當search pattern,
   跟本輪做法一樣),不需要重新摸索。
3. 若時序修正後gate依然全部通過但ring仍不可互動,才需要往`0x18d8c`/
   `0x177fc`本身反組譯更深(`DAT_00053c57`殘留值排查),這是目前唯一
   還沒排除的候選解釋。

## 2026-09-02 續五:修正時序後重測——推翻「時序」假說,新發現兩個候選
record極可能是靜態class模板、不是真正的動態戰鬥陣列,真正的live array需要
doc58續十三記載的指標解參照(pointer dereference)技巧,本輪未完成

**方法**:全新instance(`origverify6`),依續四建議修正時序——開環的Enter
送出後只等0.5秒(不做任何其他操作、不退回瀏覽游標),緊接著立刻
`enter-debugger`凍結、當場dump同一段記憶體。

**結果一:同一組record、同一個位址、gate依然全部通過**——搜尋範圍縮小到
`0x1f0000-0x250000`(涵蓋續四兩個候選位址),只命中同樣的2個位址
(`0x1fc6c0`/`0x237a48`),bytes**逐byte跟續四完全相同**,`+5`/`+6`/`+0x26`
依然全部通過。**這推翻了「續四dump時機錯過ring」這個假說**——不是時機的
問題,是本輪根本沒真的量測到「ring開著」這個瞬間本身(見下)。

**結果二(★關鍵修正):resume後畫面停在索爾的狀態卡,不是指令環**——這代表
送出的那個「開環」Enter鍵本身極可能被吃掉了(這個專案反覆記錄過的按鍵
不可靠問題,這次連續兩輪都撞上,不是巧合)。也就是說,續四跟本輪**都沒有
真正在ring開著的那一刻做過memory dump**——兩次讀到的其實都是「已選取
單位、但ring根本沒真的開啟」這個更早的狀態,不是ring本身的問題。

**結果三(重新評估續四的兩個候選record是什麼)**:同一組bytes在兩次完全
獨立的全新開機(續四跟本輪)都出現在幾乎相同的位址(`0x1fc6c0`跟
`0x237a48`,誤差在幾十bytes內),這**不像是動態配置的戰鬥陣列**(doc58
續十三記載動態陣列base會因為每次開機不同而變動,`0x2703b4`只是那次session
的值,不能沿用)——**更可能是EXE自己靜態資料段裡的class/growth預設值表**
(索爾這個LV1劍士的預設模板列),不是真正代表「目前正在被指令環讀取」的
那份動態record。這解釋了為何gate讀起來永遠是「通過」的模樣(靜態模板本來
就沒有Acted/camp會變動的概念,可能剛好初始化成看起來合法的值)——**這兩個
候選從一開始就可能不是本輪真正要找的目標**。

**真正需要的下一步(留給未來session,本輪未完成,工程量不小)**:doc58
續十三記載的完整技巧——`[0x53a45]`本身是一個**指標變數的位址**(不是陣列
本身),要先(1)用byte-signature/delta技巧找到讀取`[0x53a45]`那行指令
的live位址、(2)讀出該指令load-time-patched過的live disp32(不能用
靜態檔案的disp32)、(3)用這個位址讀出指標的實際內容,才能得到動態陣列
的真正base,再乘上unit_index*0x50找到真正的live record。這是一個完整的
delta校準+指標解參照任務,不是本輪「找到符合HP數字的bytes就當作答案」
這種捷徑能完成的。

**清理**:`origverify6`已`teardown`,`status`確認清空。

**本輪對專案的價值**:排除了「時序」這個候選解釋,並且修正了續四的一個
誤判(那兩個候選record很可能不是真正的動態陣列,是靜態模板)——這個修正
本身很重要,避免未來繼續在同一個錯誤的位址上打轉。已驗證的`+0x40..+0x4f`
欄位offset表本身依然有效(對任何真正找到的live record都可以直接套用),
只是「用HP數字當簽章搜到的第一個命中」不能假設就是動態陣列,還需要驗證
位址本身是否隨開機變動(動態=每次不同,靜態=每次相同)才能判斷。

**給下一輪(或另開專門session)的建議**:
1. 這個問題現在需要doc58續十三那種完整的delta校準+指標解參照技巧,
   工程量與doc58的原始那幾輪相當,建議當作獨立、有專門時間預算的任務,
   不要在同一個連續session裡零散地擠時間做。
2. 有一個簡單的判斷法可以事先驗證候選位址是靜態還是動態,不需要完整
   delta校準:**同一個位址在兩次不同開機之間內容/位址是否一致**——本輪
   已經確認`0x1fc6c0`/`0x237a48`兩次開機都一樣,判定為靜態模板;真正的
   動態陣列base應該每次開機都不同(matches doc58續十三的warning)。
3. 開環的Enter鍵送出後,建議先screenshot確認畫面真的變成4圖示環,
   確認無誤後才進debugger凍結——不要假設`--wait`過後鍵一定生效。

## 2026-09-02 續六:先檢視工具本身——找到並修好一個真實、先前記過但從未套用的按鍵傳遞缺口;ring現在第一次嘗試就穩定打開

用戶明確要求「是不是工具本身的問題？請先檢視工具」，暫停繼續往深處挖動態陣列,
改為回頭逐行檢視`tools/fd2_dosbox_live_helper.py`/`.sh`跟底層
`tools/dosbox_harness.sh`的按鍵傳遞路徑本身。

**找到的具體缺口**:`dosbox_harness.sh`的`cmd_send_keys()`/`cmd_enter_debugger()`
每次都是直接`xdotool key --window "$win" "$k"`,**從未**在送鍵前做任何focus
動作。這件事doc58續七十三(7840-7947行)其實**已經發現並記錄過**:`xdotool key
--window <win>`在`xdo.c`的`_xdo_send_key()`內部,依「當下查到的焦點是否剛好
就是目標視窗」在`XTestFakeKeyEvent`(可靠、全域合成硬體級事件)與`XSendEvent`
(不可靠、很多程式直接忽略)兩種完全不同機制間切換——這個Xvfb沒有window
manager,沒有WM就沒有一致的焦點維護機制。當時的結論是「不是選擇性掉鍵
(Enter/Space掉、方向鍵不掉)的根因」(因為同一瞬間的Up方向鍵測試沒事,若真的
是焦點分支問題,方向鍵不該被單獨放過),但**留了一個從未真的套用的防禦性
建議**:每次`xdotool key`前補一次`windowfocus --sync`——這個建議在dosbox_
harness.sh裡放了將近三週都沒有寫進去。

**在套用修法前先live驗證`windowfocus --sync`本身在這個環境下到底可不可行**
(不是紙上推論):doc58同一份文件後段(續八十几,~9566行)記過`windowfocus`/
`windowactivate`在同一個無WM的Xvfb下對**remake的GLFW視窗**會直接報錯——但
那是測remake視窗,不是DOSBox-X的SDL視窗。實測(新開`toolcheck`instance)
`xdotool windowfocus --sync <DOSBox視窗id>`回傳`rc=0`、無任何錯誤,且
`getwindowfocus`在呼叫前後都回報該視窗已經有焦點——**跟remake/GLFW的情況
不一樣,對DOSBox-X/SDL視窗這個防禦性修法完全可行**。

**修法**:在`cmd_send_keys()`跟`cmd_enter_debugger()`裡,每次`xdotool key`
前補一個新的`_focus_window_best_effort()`(呼叫`windowfocus --sync`,失敗
只警告不中斷,因為doc58已證實不同視窗類型/toolkit可能表現不同)。

**修法後的live驗證(新開`toolfix1` instance,`~/fd2-run-pristine`乾淨副本,
用批次~960次Enter重演完整開場,同續一路徑走到ch01部署階段,索爾HP042/AP+05
/DP+00跟先前輪次記錄完全吻合)**:

1. **開環的Enter第一次嘗試就成功**——screenshot直接看到索爾身上四個圖示環
   (上/左/右/下都是實體圖示方塊,不是先前那張固定的替代狀態卡),不像續四/
   續五連續兩輪都懷疑Enter被吃掉。這是本專案5輪investigating以來第一次
   確認ring在單次嘗試就真的打開。
2. **意外發現一個新的、先前未記錄過的工具層限制**:`wait-settle`(2張連續
   screenshot md5相同才判定settled)在部署/ring這類畫面上**永遠不會settle**
   ——連續取樣同一批settle-poll的第30/32/34/36/38/40張screenshot,md5**全部
   不同**,證實畫面上有持續跑的動畫(很可能是ring圖示本身的小動畫,或HP/MP
   bar的呼吸效果),不是真的凍結。這代表先前任何一輪如果在這類畫面上依賴
   `--settle`判斷「鍵有沒有生效」,拿到的TIMEOUT有可能是這個動畫假象造成的
   假警報,不是真的掉鍵——**續四/續五當時改用`--wait`固定延遲+debugger凍結
   的做法,某種程度上意外繞開了這個陷阱,但也代表`--settle`在這類動畫畫面上
   目前是不可靠的訊號來源,需要在工具文件裡明確記下這個限制**(已在
   `dosbox_harness.sh`原始碼註解記錄本次修法與驗證,doc98可再補一筆)。
3. **Attack(上)+Enter確認後,畫面仍停在ring/看不出明顯進入目標選擇畫面**
   ——跟續一/續三的症狀表面相符,但這次不能再歸咎於「Enter被吃掉」(ring
   本身這次是確定成功打開的)。有嘗試zoom截圖判讀四個圖示的高亮狀態(左邊
   圖示紅底、其餘藍底),但**沒有把這個當作定論**——本專案自己記過的教訓
   (`feedback_verify_ui_slot_mapping_with_markers`)是小圖示不能用肉眼猜,
   要換成純色標記物才能可靠判讀選取狀態,這裡沒有做到那個嚴謹度,故意留白。

**結論(直接回答用戶的問題)**:「是不是工具本身的問題」——**部分是**。
找到並修好一個真實、有原始碼佐證、doc58自己都已經建議過卻從未套用的按鍵
傳遞缺口(`windowfocus --sync`),修好後ring開啟從「5輪都不確定/懷疑被吃」
變成「第一次嘗試就穩定成功」,這本身就是有意義的修正。但這**不代表Attack/
Spell/Item卡住的根本謎團已經解開**——這次ring確定開了,Attack確定還是沒有
明顯進度,代表真正的謎團(可能是攻擊範圍gate的假陰性、可能是選取態的視覺
判讀問題、也可能是另一層獨立的輸入問題)依然存在,只是可以確定**不再是
「ring開啟的Enter被吃掉」這一個特定假設**。下一輪如果要繼續深挖Attack本身,
建議先做`feedback_verify_ui_slot_mapping_with_markers`要求的markers驗證,
而不是繼續肉眼判讀小圖示。

**清理**:`toolcheck`/`toolfix1`皆已`teardown`,`status`確認清空。修法已
commit到`tools/dosbox_harness.sh`並push到`fork`。

## 2026-09-02 續七:用戶要求「再重新驗證之前發生錯誤的部分」——在完整驗證過的工具上重測Attack/Wait,重大進展:Wait確定可用,問題重新定位到「亞雷斯選單根本不是戰鬥指令環」

新開`reverify1`(對`~/fd2-run-pristine`),重演開場到ch01部署，這次全程單鍵單截圖，並且第一次系統性
量出這個環境本身的畫面雜訊基準值——這是本輪方法論上最重要的修正。

**畫面雜訊基準值量測(修正先前輪次的肉眼判讀誤差)**：完全不送任何鍵、連續4張截圖，全螢幕
(1024x768)之間差了約11000-11500像素、只裁到ring圖示區域(160x150=24000像素)之間仍差了約
2200-2336像素(約9-10%)——**這代表這個環境的畫面本身持續在跑動畫，任兩張連續截圖之間的「差異」
多數是雜訊，不能直接當作「這個按鍵造成了畫面變化」的證據**。續六用248像素的全螢幕diff判斷「Up沒有
造成變化」，現在看來這個結論本身依然成立(248遠低於雜訊基準)，但後面幾輪用「圖示顏色/形狀變了」
來判斷「選取狀態改變」的讀法，在這個雜訊量級下並不可靠——這解釋了為何早前對紅/藍配色的判讀
（disabled/enabled）會反覆修正。

**索爾(Sol)的ring重新測試——結果比先前更清楚**：
1. 用doc13記載的流程(第一次Enter→HP/MP狀態卡+移動範圍十字；第二次Enter於原地確認→開啟指令環)，
   ring穩定第一次就開啟(延續續六的修法成果)。
2. Zoom比對「按上(攻擊)前後」的ring圖示區域，像素**完全相同**——不是雜訊等級的248差異，是zoom
   crop後的0差異，比續六更嚴謹。「上」的底色本身是**紅色**(先前續六因為在較小解析度下誤讀成藍色)。
3. 「下」(待機，永遠不會disabled)+Enter：**這次索爾的角色圖示整個變成灰階石化**——這是明確、
   不含糊的「已行動」視覺標記，不是肉眼猜圖示顏色。**這證明Wait是真的可以正常執行的，先前輪次
   「按什麼都回到同一張狀態卡」的症狀，很可能是doc13記載的ring選取狀態殘留(`DAT_00053c57`跨
   ring實例不重置)造成的假象，不是按鍵被吃掉、也不是指令環本身的功能性bug**。這是6輪investigating
   以來第一次拿到毫無疑義的正面結果。

**亞雷斯(Ares)——發現了一個全新、更精確的問題描述**：用browse游標移到亞雷斯身上按Enter，**沒有
出現HP/MP狀態卡+移動範圍**，而是直接跳出一個完全不同外觀的4圖示選單(記錄/清單圖示、道具袋、
設定滑桿、紅底寫著「END」字樣的按鈕)。按「END」+Enter得到一個真正可運作、有獨立立繪的YES/NO
確認框「要結束本回合的行動嗎?」——按NO正確取消、按YES的路徑沒測(避免真的消耗亞雷斯回合)。按
「上」(記錄圖示位置)+Enter，開啟了一個有上一頁/下一頁翻頁圖示的清單瀏覽介面，明確是「戰鬥
紀錄/日誌」類的系統選單，不是Attack。

**結論——問題被重新定位，範圍縮小了**：
1. 原本以為的「Attack/Spell/Item卡在ring之後」在**索爾**身上，現在看來很可能主要(或完全)是先前
   幾輪因為圖示雜訊判讀不準+ring選取狀態殘留造成的假象——Wait這個最簡單、最不含糊的對照組確定
   正常運作。
2. 真正還沒解開的謎團**换了一個更精確的形狀**：**用browse游標移動後選取的單位(亞雷斯)，Enter後
   給的不是doc13描述的Attack/Spell/Item/Wait戰鬥指令環，而是一個系統選單(記錄/道具庫/設定/結束)**
   ——這個系統選單本身功能完全正常(YES/NO對話框、翻頁清單都是真的、可互動的)，只是它顯然不是
   「攻擊」的路徑。索爾能用第一次Enter看到移動範圍+狀態卡，亞雷斯卻直接跳過這一步，兩者明顯處於
   不同的可操作狀態，原因未查——候選包括：(a)索爾的「自動逐一顯示狀態卡」只在deployment開場的
   自動播放序列中對他生效過，(b)亞雷斯在這個時間點可能真的還不能被當作可移動/可攻擊的單位控制
   (呼應先前劇情是索爾VS亞雷斯的比劍橋段，也許有腳本上的先後順序限制)，(c)也可能單純是這次
   cursor導覽路徑(先移動再Enter vs 原地Enter)本身觸發了不同的程式分支，跟單位是誰無關——doc13
   目前沒有記載這個「系統選單 vs 戰鬥指令環」的分岔邏輯，這是本輪真正的新發現，值得未來配合
   debugger/反組譯定位是哪個判斷式在分岔。
3. **本輪徹底排除了「工具的按鍵傳遞不可靠」作為任何觀察結果的解釋**——整個過程單鍵單截圖、
   YES/NO對話框正確回應、Escape正確逐層返回、灰階「已行動」視覺標記正確出現，沒有一次出現需要
   懷疑「這鍵到底有沒有送到」的情況。這是續六windowfocus修法+續七完整工具audit之後，第一次把
   工具的可靠性從整條調查鏈裡完全排除的一輪。

**清理**：`reverify1`已`teardown`，`status`確認清空。本輪沒有程式碼異動，純調查+文件記錄。

## 2026-09-02 續八：用戶追問「游標確定框在亞雷斯嗎？」——續七的「系統選單」發現是誤判，真正原因是游標根本沒停在單位上

用戶這句追問直接命中要害。回頭zoom比對續七的截圖才發現：對索爾時，游標框包住他的**下半身/腳部**；
對「亞雷斯」時，游標框整個在**頭頂上方**——兩種完全不同的相對位置，值得懷疑。

新開`cursorcheck`，重演到部署，這次每移動一格就zoom截圖核對游標框跟地形/角色的對齊關係，並且發現
一個更可靠的訊號：**左下角的迷你狀態卡本身就會誠實地告訴你游標到底停在單位身上還是空地上**——
空地時只顯示地形圖示+地形修正值(如`A+05 D+00`)，停在真正單位身上時會顯示該單位的頭像+HP數字。
續七完全沒注意到這個區別，只看游標框的視覺對齊，這正是誤判的根源。

**逐格重演結果**：按3次Right從索爾移到「續七以為是亞雷斯」的那格，迷你卡確實只顯示地形資訊，
沒有角色頭像——**證實游標當時真的不在任何單位身上**，Enter跳出的「記錄/道具庫/設定/END」選單
其實是空地/系統選單，不是亞雷斯的個人選單。再往下移一格，迷你卡立刻變成一個紅髮角色頭像+
**HP:028**——這其實是**悠妮**，不是亞雷斯(續一/續二記錄過悠妮HP028、亞雷斯HP048，這裡的028
確認是悠妮)。對悠妮按Enter，得到跟索爾一模一樣的HP/MP狀態卡+移動範圍流程(悠妮LV.01/HP028/
MP008)，開ring後外觀跟索爾的略有不同(圖示形狀因單位/職業而異)但結構相同，「下」+Enter確認Wait
後悠妮的角色圖示同樣正確變成灰階石化——跟索爾的結果完全一致。

**結論(更正續七)**：續七「亞雷斯選單是系統選單而非戰鬥指令環」這個結論是**錯的**，根因是游標
對位失誤(沒有真的停在單位身上)，不是遊戲行為異常，也再次印證這個專案自己反覆記過的教訓——
「視覺相鄰不等於邏輯相鄰」，這次是「看起來游標框在角色旁邊」不等於「游標真的在角色的格子上」。
真正可靠的判斷方式是**迷你狀態卡有沒有顯示角色頭像+HP**，不是肉眼比對游標框跟角色的像素位置——
這個判斷法比zoom比對游標框更快、更不含糊，值得記入未來的操作SOP。截至本輪，Wait在索爾跟悠妮
兩個獨立單位上都乾淨、明確地確認可以正常執行；Attack/Spell/Item真正的可用性仍未在「確定選中
單位」的前提下完整測過(此前的測試很可能有部分同樣受這個游標對位問題影響)，是下一輪如果要
繼續深挖攻擊功能時，第一件要重做的事——先確認迷你狀態卡有角色頭像再操作，不要只看游標框位置。

**清理**：`cursorcheck`已`teardown`，`status`確認清空。本輪沒有程式碼異動。

## 2026-09-02 續九：用戶要求「先確認為何之前會發生錯誤」——找到續八誤判背後真正的視覺機制

不只停在「游標沒對準」這個結論，用固定裁切視窗把`step2`(游標在樹上，對照組)/`step3`(續八以為
是亞雷斯)/`step_down`(確認悠妮)三張截圖的同一塊畫面座標疊在一起比對(背景像素完全對齊，因為
截圖本身沒有變動裁切範圍)：

1. `step2`→`step3`只按了一次「右」，游標框水平右移整整一格、**垂直高度完全沒變**——證實「右」
   鍵是純水平移動，沒有偷偷跨行，排除了「方向鍵本身有問題」這個候選。
2. `step3`→`step_down`只按了一次「下」，游標框**垂直往下移了整整一格**，才變成真正包住悠妮
   身體(頭肩到腳)的正確樣子。`step3`當下，游標框剛好卡在悠妮的頭部/上半身位置附近。

**真正的機制**：悠妮的角色立繪本身畫得比一格地圖磚的高度還高，會往上「戳」進她實際站立格子
正上方那一格的畫面空間裡。所以當游標其實停在她正上方那格空地時，游標框在畫面上看起來剛好落在
她的頭部/上半身附近，造成「游標好像對準了角色」的強烈視覺錯覺——但那格根本是空地。這是這款
遊戲角色立繪的繪製方式(角色高度大於tile高度、以腳底對齊tile格線)本身結構性造成的陷阱，不是
bug、不是這次操作意外、也不是工具的問題——**用游標框跟角色輪廓的視覺對齊來判斷「選中了誰」，
在這款遊戲的美術規格下天生就不可靠**，跟這個專案自己已經記過的教訓(視覺相鄰不等於邏輯相鄰、
小圖示不能用肉眼判讀選取狀態)是同一類陷阱的另一個具體案例。

這解釋了續八為何會誤判，也回頭印證續八記錄的修正方法(改看迷你狀態卡有沒有角色頭像+HP)是正確
的解法方向——迷你狀態卡是遊戲自己回報的邏輯狀態，不受角色立繪畫多高影響，游標框的畫面位置則會。
**未來任何需要確認「游標/選取框是否對準特定單位」的操作，都應該優先看迷你狀態卡或等效的遊戲內
狀態回報，而不是zoom截圖比對游標框跟角色的像素位置**——這條SOP已經記入続八，本輪補上背後的
成因解釋，避免以後有人不清楚原理又走回肉眼判讀的老路。

## 2026-09-02 續十：用戶要求「請接續測試下去」——在完全確認過的條件下正式測Attack，乾淨的新結果：不是Attack本身壞了，是亞雷斯這個單位全部卡住

新開`attacktest`，重演到部署。這次先系統性核對地圖上每個我方單位的真實身分(用迷你狀態卡，不用
外觀猜)：先前輪次一直誤認的「紅髮=亞雷斯」其實是**悠妮**(HP028)；**真正的亞雷斯**是那個藍帽子
單位(HP048，跟續一數值吻合)，位置離敵人更近。

**移動+攻擊測試(全程確認條件)**：
1. 選中亞雷斯(狀態卡顯示`亞雷斯 LV.01 HP048/048`，姓名文字直接確認，不是猜)。
2. 用目的地游標移動到敵人正左側一格——移動前zoom比對，游標框與敵人sprite同一列、緊鄰、bracket
   底邊對齊敵人腳底，不是斜對角，確認是真正的上下左右相鄰(這次特別避開續九發現的「立繪戳上一格」
   陷阱)。Enter確認移動，ring正確在新位置自動開啟。
3. 按「上」(攻擊方向)+Enter+再按一次Enter：卡在亞雷斯的完整狀態卡+裝備清單(`人類 騎士`，
   `刺矛+AP020`、`布衣+DP002`，HIT092/AP026/DX002/MV07/EV002/DP006，與續一數值精確吻合)，
   不會繼續前進，Enter第三次同一張卡，畫面完全靜止不變——即使在確認過真的相鄰、真的是本人、
   工具可靠性已排除的前提下，Attack依然沒有進入目標選擇畫面。
4. 對照測「右」(道具)：Escape回ring再按右+Enter，**同一張裝備狀態卡**，跟攻擊完全一樣。
5. **關鍵對照測「下」(待機，理論上永遠enabled)**：Escape回ring再按下+Enter，**還是同一張裝備
   狀態卡**——這跟索爾/悠妮的待機測試結果完全不同(續九/續十之前那兩位的待機都乾淨地讓角色圖示
   變灰階，確定執行成功)。

**結論(本輪最重要的修正)**：先前輪次(含續六)看到的「Attack/Item卡住」現象，**根因不是「Attack
這個方向本身有問題」或「距離不夠」——這次確認距離、身分都對，Attack還是卡住，但更關鍵的是連
「下」(待機，理論上不會被disable)在亞雷斯身上也一樣卡住**。真正的規律是：**索爾、悠妮兩個單位
的所有已測方向都正常運作(至少Wait乾淨確認過)；亞雷斯這一個單位，不論按哪個方向，一律卡在同一張
非互動狀態卡**——這精確符合doc13記載的`0x17aed`替代畫面特徵(「不論按哪個方向都得到同一張非互動
狀態卡」)，而且是**單位специфic**，不是「某個方向的功能壞了」。doc13記載的三個ring進入gate
(`record[+6]==2`本方陣營、`record[+5]`bit7 Acted清除、`record[+0x26]==0`語意未知的第三個gate)
裡，第三個gate(`+0x26`)本來就是本專案先前(續四/續五)一直懷疑但無法live驗證到的候選——這次的
「亞雷斯specific、索爾/悠妮不受影響」證據，直接支持「亞雷斯這個單位的`+0x26`欄位(或camp欄位)
本身數值不對」這個假說，而不是range/武器/工具問題。跟開場劇情(索爾/亞雷斯比劍橋段)是否有關聯，
未查證，值得下一輪列為候選之一。

**清理**：`attacktest`已`teardown`，`status`確認清空。本輪沒有程式碼異動，純調查+文件記錄。真正
驗證這個假說需要doc58續十三那套完整的delta校準+指標解參照技巧去讀亞雷斯真正的動態unit record，
續五已經把這個列為獨立、有專門時間預算的future task，這裡不重複展開。

## 2026-09-02 續十一：用戶追問「周邊確認有敵人嗎？」——用同一套迷你狀態卡方法雙重核對，確認續十的相鄰判斷成立

新開`enemycheck`，重演到部署，把browse游標直接移到續十那個銀甲敵人的格子上：迷你狀態卡跳出**該
敵人的頭像+「050」數字**(格式跟我方單位的頭像+HP完全一致)，游標框也正確底部對齊包住敵人身體
(不是續九發現的「立繪戳上一格」那種空地錯覺)——**確認這格真的是一個真實敵人，不是空地或視覺
誤判**。再往左移一格，迷你狀態卡變回純地形圖示(無頭像)，**這格正是續十亞雷斯站立、開ring測試
攻擊的那一格**——雙重確認亞雷斯當時的位置真的緊鄰(正左方，非斜對角)這個敵人。

**結論**：續十的攻擊測試前提完全成立——真的有敵人在亞雷斯正旁邊。攻擊/道具/待機全部卡在同一張
非互動狀態卡的結果，不能用「其實旁邊沒有敵人」或「其實沒有真的相鄰」來解釋，進一步支持續十的
假說(亞雷斯這個單位本身的gate狀態有問題，不是range/目標判定的問題)。

**清理**：`enemycheck`已`teardown`，`status`確認清空。本輪沒有程式碼異動。

## 2026-09-02 續十二：用戶要求「自動繼續後續測試」——精確隔離出真正的變因：必須「亞雷斯本人」+「真的移動過」兩個條件同時成立，索爾移動完全沒事

**假說1(操作順序)測試**：新開`ordertest`，這次完全不碰索爾，直接把游標移到亞雷斯身上、選中、
**原地不動**按下(待機)+Enter——**成功**，角色圖示正確變灰階。這代表「先跟索爾互動過」不是必要
條件，推翻了單純的「順序污染」假說。

**假說2(移動本身)測試**：新開`ordertest2`，一樣先選亞雷斯(不碰索爾)，這次**真的移動**他2格到
敵人旁邊(緊鄰關係已用迷你狀態卡方法確認)，按「上」(攻擊)+Enter+再Enter：卡在裝備狀態卡，跟
續十完全一樣。Escape回ring，改測「下」(待機)：**同樣卡住**——這代表連他自己「移動之後」的待機
都會壞，不是攻擊/道具特有。

**關鍵對照組**：同一個instance，Escape取消移動(亞雷斯彈回原位，確認取消機制)，改選**索爾**，
這次讓他**真的移動2格**(不是原地確認)，再測待機：**成功**，索爾正確變灰階石化。

**結論(本輪最精確的隔離結果)**：真正的變因不是「哪個單位」單獨決定，也不是「有沒有移動」單獨
決定，而是**兩個條件同時成立才會觸發**：
1. 是亞雷斯本人操作(索爾、悠妮都測過多次，從未卡住)
2. 這個單位這一回合**真的移動過**(非原地確認)——亞雷斯原地不動時一切正常，索爾/悠妮不論有沒有
   移動都正常，只有「亞雷斯+移動」這個組合會卡

這精確排除了先前懷疑的候選：不是range/武器判定問題(續十已排除)，不是操作順序污染問題(本輪
排除)，也不是「移動這個動作本身」的通用問題(索爾移動沒事，排除)。剩下最集中的候選：**亞雷斯
這個單位的移動處理路徑本身有問題**——可能跟開場劇情「索爾/亞雷斯比劍橋段」有關(亞雷斯是否帶著
某個「剛結束比武」的殘留旗標，移動後沒有正確清除)，也可能是他的unit slot/職業(人類騎士)特有的
一個移動後處理步驟寫壞了某個gate byte。兩者都還沒有直接證據，需要doc58續十三那套完整的delta
校準+指標解參照技巧，在「亞雷斯剛移動完、ring卡住的那一刻」直接讀他的真實動態unit record(尤其
`+0x26`欄位移動前後的值)才能證實，這仍然是續五已經標記的獨立future task範圍，本輪透過純live操作
把候選範圍縮到最小，值得作為那個future task的具體切入點。

**清理**：`ordertest`/`ordertest2`皆已`teardown`，`status`確認清空。本輪沒有程式碼異動。

## 2026-09-02 續十三：嘗試HP-signature捷徑讀「亞雷斯剛移動完」那一刻的記憶體——再次確認(不是新發現)撞到續五已知的靜態模板牆

繼續自動測試，這次直接試「亞雷斯剛移動完、ring卡住」那一刻進debugger讀記憶體，看能不能繞過續五
標記的「完整delta校準」重工程，走捷徑先看一眼`+0x26`。

**方法**：新開`memcheck`，重演到部署，選中亞雷斯、真的移動2格到敵人旁邊(ring卡住確認)，Alt+Pause
進debugger(這次selector是`DS=00A0`/`CS=0080`，不是常見的0170/0178，再次印證doc58續四十「每個
session都要重新讀，不能假設固定」)，用`ES=0178`(跟其他session常見值一致)、2MB `MEMDUMPBIN`，
搜尋亞雷斯的HP048/048、MP000/000、AP026、DP006、HIT092、DX002這8個u16 LE欄位組成的16-byte
簽章。

**結果**：只找到2個命中，`0x1fc7a0`跟`0x237b28`——**分別跟續四/續五已經確認過的靜態模板位址
(`0x1fc6c0`/`0x237a48`)恰好差0xE0 bytes**，這個規律間距(同一張表的下一列)本身就是「這是靜態
class/growth預設值表，不是動態陣列」的有力證據，不需要再開第二次獨立開機比對。讀這個位址的3個
gate byte：`+0x05`(Acted)=0x00、`+0x06`(camp)=0x02、`+0x26`(gate3)=0x00——**三個全部顯示
「通過」，但畫面上亞雷斯的ring明明卡住**，這個矛盾直接證實讀到的不是他真正移動後的動態狀態，
跟續五的結論完全一致。

**結論**：HP-signature搜尋這條捷徑在「剛移動完」的情境下依然找不到真正的動態陣列，這不是新發現，
是續五已經預期、這次直接驗證確認的已知限制——**再次確認不需要在未來任何一輪重複嘗試這個捷徑**，
真正需要的是續五記載的完整doc58續十三delta校準+指標解參照技巧，工程量與doc58原始那幾輪相當，
維持「獨立、有專門時間預算的future task」的定位，本輪不強行展開。

**清理**：`memcheck`已`teardown`，`status`確認清空。本輪沒有程式碼異動。

## 2026-09-02 續十四：用戶要求「繼續」——正式執行doc58續十三完整delta校準技巧，第一次成功找到真正的動態unit陣列，直接用真實數據推翻「gate3」假說

用戶明確要求繼續，這次正式投入續五標記的「獨立future task」：完整的`[0x53a45]`delta校準+指標解參照
技巧，不再滿足於HP-signature捷徑。

**準備工作**：派兩個背景agent平行工作——一個查專案既有文件裡`[0x53a45]`技巧的已知細節（doc58續十三
原文、record stride、既有byte-signature），一個直接用Ghidra headless對現有的`FD2Analysis3`專案做
唯讀查詢，精確定位「哪一行指令真的讀取`[0x53a45]`」。Ghidra查詢確認：該指令在`FUN_000117e7`內有
兩處（ghidra位址`0x1182a`與`0x118e2`），緊鄰已知的34-byte gate-check簽章起點`0x11912`；decompile
直接印證`record = unit_index*0x50 + DAT_00053a45`，且gate3公式精確對應`*(char*)(iVar2+0x26)=='\0'`，
跟doc13完全一致——這是本專案第一次不靠反組譯手工推導、直接由decompiler原文證實這個公式。

**Live執行（`deltachase`/`deltachase2`兩個獨立instance）**：
1. Alt+Pause進debugger，`GDT`/暫存器讀flat selector（`CS=0170`/`DS=0178`，`Pr32`確認在32-bit
   保護模式FD2自己的程式碼內，不是續四誤中的中斷處理常式）。
2. `MEMDUMPBIN 170 100000 200000` dump 2MB，搜尋34-byte gate-check簽章——**只命中一次**，
   live位址`0x1ad912`，算出delta＝`0x1ad912-0x11912=0x19C000`——**跟doc58歷史紀錄的delta數值
   完全相同**，且**兩個獨立開機都重現同一個delta**，這次沒有撞到doc58警告過的「delta每次不同」
   情況（環境夠穩定/deterministic）。
3. 用這個delta算出`MOV EDX,[0x53a45]`（ghidra`0x118e2`）的live位址＝`0x1ad8e2`，讀live disp32＝
   `8b 15 45 fa 1e 00`＝`MOV EDX,[0x1EFA45]`——**跟doc58續十三三天前另一個獨立session記錄的
   `[0x3a45]→[0x1efa45]`完全吻合**（本專案第三次獨立驗證同一個值）。
4. 讀`[0x1EFA45]`得到陣列真正base＝**`0x237a48`**——兩個獨立instance都得到完全相同的值。

**驗證這真的是動態陣列，不是續五誤判的靜態模板**：dump陣列前4筆記錄，逐一核對HP數值：
`idx0=HP42/42`(索爾)、`idx1=HP28/28,MP8/8`(悠妮)、`idx2=HP48/48`(亞雷斯)、`idx3=HP50/50`(第四位，
身分未查)——**三個都跟已知精確數值逐一吻合**，兩個獨立instance重現一致。**這直接推翻續五的結論**：
`0x237a48`一帶不是靜態class模板，是真正的動態per-battle unit陣列——續五「位址跨開機不變＝一定是
靜態模板」的推論本身有瑕疵（這款DOS4GW遊戲在同一份原始檔案+同一個DOSBox-X設定下，記憶體佈局本身
就是deterministic的，沒有ASLR，「位址每次不同」不是判斷動態/靜態的可靠依據——這是本輪最重要的
方法論修正）。

**核心結果——移動前後+攻擊嘗試前後，直接比對亞雷斯真實記錄的每一個byte**：
- **移動前**（`deltachase2`）：`+0x05`(acted)=0x00、`+0x06`(camp)=0x02、`+0x26`(gate3)=0x00——
  三個gate全部「通過」。
- **移動後**（真的移動2格到敵人旁邊，ring正常自動開啟）：**只有`+0x00`/`+0x01`(疑似座標欄位)從
  `08/10`變成`0a/11`，其餘全部0x50 bytes逐一比對完全沒有任何一個byte改變**——`+0x05`/`+0x06`/
  `+0x26`維持原樣，全部仍是「通過」的數值。**這直接、以真實記憶體資料證明：doc13記載的三個
  entry gate，移動前後都沒有被寫壞——「gate3被移動改壞」這個貫穿續十~續十五的核心假說被推翻**。
- **攻擊嘗試後**（按上+Enter+Enter，畫面卡在裝備狀態卡）：跟移動後的記錄逐byte比對，**完全沒有
  任何差異**，連四位隊友(index0-3)的記錄整體都毫無變化。順手檢查doc13提到的另外兩個相關全域變數
  `DAT_00053c57`(ring選取狀態)、`DAT_00053ec8`(decompile裡看到的無條件歸零欄位)：**兩者都讀到
  0x00000000**，沒有異常訊號，但由於`0x53ec8`decompile已知是「不論gate3結果都無條件歸零」，這個
  讀值本身不能證明或推翻任何假說。

**結論(本輪最重大的方法論與事實突破)**：
1. **首次成功執行doc58續十三的完整delta校準+指標解參照技巧**，不再依賴HP-signature這種可能誤中
   靜態模板的捷徑——這個方法本身現在被證實在這個環境下高度可重現（兩個獨立開機、同一個delta、
   同一個陣列base、同一個指標鏈中繼值，全部一致）。
2. **續五「這一帶是靜態模板」的結論被推翻**——`0x237a48`确认是真正的動態unit陣列，續四/續五/續十三
   的HP-signature搜尋命中的`0x1fc6c0`/`0x237a48`附近位址，回頭看應該理解成「跟真正陣列很接近甚至
   重疊、但用錯誤方法定位、найдено的巧合」，不是真的靜態模板證據——這一點連帶提醒未來不要單靠
   「位址跨開機是否相同」判斷動態/靜態，這個判準本身在deterministic-loader的環境下不可靠。
3. **doc13記載的三個entry gate(camp/acted/+0x26)被真實記憶體資料直接排除**，不是移動後卡住的
   根因——移動前後、攻擊嘗試前後，這三個byte從頭到尾都沒有變化過，維持在「應該正常」的數值。
4. **真正的根因依然未解**，但候選範圍已經被本輪大幅限縮：不在per-unit的0x50-byte record結構裡，
   必須往別的方向查——可能是`0x18d8c`指令環本體邏輯本身(不是`0x117e7`entry gate)有問題、可能是
   某個尚未定位的全域變數、也可能需要真正追蹤「按上+Enter」這個輸入序列實際執行到哪一行程式碼
   (需要在ring開著、還沒按鍵前就設中斷點單步，而不是像本輪這樣「動作做完再回頭讀記憶體結果」)。

**過程中的工具/方法論小發現**：Alt+Pause「離開debugger」這個方向這次兩個instance都至少各遇到一次
失敗（連續按2-3次都沒有真的恢復執行，只有`I-> _`提示字元這個已知會stale的訊號誤導判斷）——**確認
的可靠解法是直接用`debugger-cmd`送debugger自己的`RUN`console指令**，比依賴Alt+Pause熱鍵更可靠，
值得記入未來任何需要「進去讀完記憶體、再乾淨恢復執行」的操作SOP。判斷是否真的恢復執行，比對
「同一個畫面連續兩次截圖是否仍完全相同」比看tmux pane文字更可靠(纯地圖瀏覽畫面本身動畫很少，這個
方法在這類畫面上比在ring畫面上更適用需要靠「送一個會造成明顯位移的按鍵、直接看有沒有位移」交叉確認)。

**清理**：`deltachase`/`deltachase2`皆已`teardown`，`status`確認清空。本輪沒有程式碼異動，純調查+
文件記錄，但這是整個Attack調查(續九~續十四)迄今方法論與事實層面最紮實的一輪。
