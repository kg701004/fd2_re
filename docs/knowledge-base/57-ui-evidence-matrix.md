# 57 — UI evidence matrix（SDD-1 baseline，2026-07-25）

> 這是 SDD 的第一份可執行盤點，不是「已還原」宣告。行號以本輪 `remake/cmd/fd2/main.go` 為準；`partial`／`missing` 必須先補 E0/E1/E2 證據才可改成 verified。

## 2026-07-28 visual-parity audit

這一節回答的是「玩家目前看到的操作畫面與原版相差多少」，不能與
codec、RE 函式數或可編譯測試數混算。分數是依 repo 內 DOSBox／錄影
oracle、目前 source rebuild 截圖、indexed fixture，以及外部原版畫面逐項
審查後的工程估計；它不是 pixel-diff 百分比，也不是遊戲總完成度。

| 畫面／流程 | 視覺還原估計 | 直接證據與主要差距 |
|---|---:|---|
| title/main menu | 60–70% | runtime 使用原始 title/menu 圖與接近原座標；但 README 的 `title.png` 只是錯色盤的 raw 解碼產物，並非目前 runtime screenshot。四槽讀檔畫面與 LOAD restore owner 已接；畫面仍加了非原版 F2 提示，logozoom 是近似，CONTINUE current-battle restore 尚未閉合 |
| tactical field/HUD | 60–70%（限 ch01 E2 slice；全 33 圖已有 E0 renderer inputs） | `native-map-ch01-original-video.png` 與 `native-map-ch01-remake.png` 已對齊 terrain、cursor、HUD resource/layout；2026-07-29 稽核發現只有 map0 曾帶 `native_tile_blit_modes/native_terrain_control`，現已從雜湊鎖定的 FDFIELD／FDSHAP 同步至全部 33 圖並有全圖 regression。ch26 又由 pre-handler PAN/FOCUS 與 cursor state machine 閉合 event61 所需 runtime view/HUD E1；ch27 的 selector0→event62→event63 raw camp0 敵軍 AI 前 runner、兩批增援與全白／恢復演出已達重製端 E1，戰前 view／selector0 及 inherited HUD owner 也已閉合並接線。gate A 由存檔保存、anchor 為程序內持續、gate B 由 controller 物化；仍缺未修改 DOSBox 同狀態逐幀比較與一般玩家 CONTINUE 路徑。其餘 ch02+ 與同狀態畫面仍未驗，不能把資料完整度當成 renderer E2 |
| action/command/item/target UI | 50–60%（ch01 攻擊環已有 E2 slice） | action skin、command grid、item panel已有原資源 indexed adapters；**2026-08-15**：ch01 攻擊指令環（開環→上選攻擊→相鄰格目標鎖定→擊殺）首次拿到同狀態 DOSBox 互動實測（非截圖 harness）——圖示/配色/四方位置與 remake 逐一比對吻合，攻擊流程走一次真的看到敵人變墓碑，見 doc58 對應段落。這只閉合了「近戰攻擊」這一條路徑；法術/道具子選單的 selector 6/7+、完整 availability、effect presentation、其餘 UI 狀態的同狀態 DOSBox diff 仍未閉合 |
| story dialogue | 30–40% | 原版 oracle 固定左下 80×80 portrait、native frame/text/page marker；目前一般 runtime 仍有 RGBA/font/layout path，upper/right anchor、FFxx、scroll/clipping 未逐類驗收。README 的 `dialogue.png` 是文字解碼圖，不是 remake 對話 runtime screenshot |
| full-screen battle presentation | 40–50% | FIGANI/AFM、部分 status frame與局部 pixel-equal slices可重播；command/spell/item完整 presentation、音效與 palette/timing sequence仍缺 |
| postbattle/campaign transition | 25–35% | graph與部分 handler已接，但原版每章 postbattle→town／連戰／整備的可見轉場未逐章 E2 驗收 |
| town hub | ch02 examined slice 85–90%；全章 partial | ch02 variant0 selection0–5 均取得原版 DOSBox E2，且各自能和 production remake 某個 pulse 的 320×200 raw RGB MD5 整幀相同；Left/Right wrap、Shift+F1 reveal、Enter進variant5及Escape返回selection5皆由原版 input trace 到達。23個town中只驗收ch02，仍缺variant1/2與其餘章E2；85–90%不可外推成全遊戲town覆蓋率 |
| weapon/item/secret shop | ch02 examined slice 92–95%；全章 partial | 69個shop節點已用variant1/3/5啟用indexed owner，但DOSBox E2只覆蓋ch02：三種variant service menu、variant5 wrap/return、weapon purchase-list四個selection、Yes/No、gold0不足金及gold1000裝備收件者selection0/cycle1全幀相同。selection0按Down到selection1亦以exact-pixel同步人物動畫相位後，remake三cycle各取得不遮罩的整幀AE=0；Down/Up與horizontal no-op input已觀測。購買成功裸畫面撤回過早DATO第0幀覆蓋後，25/26個原版樣本可對上來源影格整幀AE=0；唯一樣本在`0x16886`寫入途中只差效果區兩點，不當成原子影格。`0x2d516`八位數downward odometer修正literal `(16,98)`後，16個原版atomic debit samples各有整幀AE=0。recipient E2依screenshot-only LOADCH typed-party bootstrap；正常JOIN→LOADCH roster另有runtime regression，但尚無完整campaign/save input E2。仍缺四人以上recipient scroll、no-recipient/full、sell/equip/transfer child panel與其他章節E2；92–95%不可外推成69店全覆蓋率 |
| church | 60–70%（已接 slices） | church main/status/transfer/revive/class 多數已有原始 FDOTHER/FDICON/FDTXT indexed畫面與 lifecycle；transfer的`0x2f8ea`亦由shop service3共用，非church專屬；缺 DOSBox side-by-side、部分 fallback與完整 persistent/save parity |
| preparation | 35–45% | 舊「兩欄文字核取方塊」與「確認框仍是重製殼層」斷言已失效。城鎮 FDTXT `0x201` 出發提示會保存／還原實際 town frame；無城鎮 FDTXT `0x19a` 記錄提示使用原版黑色來源，存檔延至完整關框後。兩者與 `0x31d3c` 最終確認都接上 6＋4＋兩 tick 脈動＋4＋5＋還原。`0x318ad/0x31e80` 選人主畫面、`0x17fc0` 狀態與 `0x1297d` 待機週期亦已接正式路徑。README 的整備圖均為 E1 原始資源合成，不是 DOSBox 實機。仍缺跨畫面初始相位、晚期存檔與同狀態實機差分 |
| save/load | 45–55% | 四槽 input、native save envelope、原版 indexed loadslots 與 chapter-slot→typed party→town/preparation restore owner 已接；空槽及修改存檔 chapter1 有效槽畫面均與 DOSBox 全幀 RGB 相同。一般玩家有效槽 E2、CONTINUE current battle、delete/overwrite 仍缺 |
| ending | 20–30% | prefix已跑到 `0x2c548`，portrait compositor已閉合一段；campaign仍可落入 generic「結局」半透明文字頁，party montage、音訊與terminal route未完成 |

上表百分比是各欄已檢視切片的工程估計；town/shop已明列為ch02 scoped，
不能把它們當成23 town／69 shop的coverage denominator。綜合未驗收章節與
缺失state後，整體仍估約 **40–45%**，因此現階段應對外寫成「操作界面
視覺還原約 40–45%」，而不是「原版視覺 parity 已完成」。如果評的是
原始圖檔／字型／動畫／indexed codec 可解碼程度，則可合理估為 75–85%；
如果評的是可操作 state flow，約 50–55%；這三種指標不可互相替代。

外部交叉證據只用來辨認原版畫面結構，不取代本機 DOSBox oracle：

- [巴哈文章搜尋摘要](https://home.gamer.com.tw/artwork.php?sn=1432264)
  明確包含「進入教會的畫面」；頁面目前會拒絕自動抓取，故不作像素證據。
- [小黑盒原版回顧](https://api.xiaoheihe.cn/maxnews/app/share/detail/2265131)
  的原版 shop screenshot 可見店員、店內背景、藍色對話框、gold counter
  與圖示選單，直接排除「地圖上通用半透明商品清單」是原版等價 UI。
- [百度原版攻略畫面](https://jingyan.baidu.com/article/597a0643385421312b5243cf.html)
  可見戰場 action menu 是原生像素 overlay，不是一般現代文字 panel。
- [圖文攻略](https://egameinsider.com/p/dko871470c83/)
  顯示章間服務並非每戰後同一流程；例如第22–25章是連續戰、沒有村落
  補給，支持 campaign 必須逐章保存 town／shop／連戰節點。

### 視覺優先順序

1. 先把 town、weapon/item shop、preparation、loadslots 從 generic
   `drawCampaignUI` 分離，建立 320×200 original-indexed scene owner。
2. 每個 owner 必須有同一 state/input 的 DOSBox screenshot；不能只用
   原資源 fixture 宣稱 E2 parity。
3. 戰場驗收要固定同一 save／roster／camera／cursor／animation tick，再
   做 palette-index或RGB pixel diff；目前兩張 ch01 圖只能證明 compositor
   slice，不能證明整幀等價。
4. README 只展示並列且標清 `original DOSBox`、`remake runtime`、
   `indexed fixture`、`raw decode` 的圖片，禁止再把 raw decode 說成 remake。

### 2026-08-19 視窗縮放 filter 查證（worklist L660／L815，純 code inspection）

`remake/cmd/fd2/main.go:9696` 有一段註解宣稱「Ebiten 對非整數縮放預設套用平滑 box
filter，見 `run.go SetScreenFilterEnabled` 註解」。逐一查證後：

- `remake/cmd/fd2` 目錄**沒有 `run.go` 這個檔案**，全 repo 也沒有任何 `SetScreenFilterEnabled`
  呼叫或函式——這是一句指向不存在檔案/函式的過期註解。`ebiten.SetScreenFilterEnabled`
  是 Ebiten v1 的 API，v2（本專案用的 `github.com/hajimehoshi/ebiten/v2 v2.6.6`）已移除，
  也沒有替代的公開開關。
- `windowScaleFor`/`defaultWindowSize`（同檔 9682-9702 行）與 `ebiten.SetWindowResizingMode
  (ebiten.WindowResizingModeEnabled)`（9736 行）證實視窗確實可被玩家自由拖曳成**任意非整數
  倍率**的大小，不限制在整數倍。
- 全 repo `grep` 找到的所有 `op.Filter = ebiten.FilterLinear` 呼叫（`main.go`/`title.go` 共
  10 餘處）都是**個別素材**的顯式選擇（例如 `title.go:362` 的行內註解說明標題圖含「細密網點
  材質」，需要線性濾波才能還原漸層觀感，否則放大後網點各自可見）；其餘 `op.GeoM.Scale` 呼叫
  沒有設 `op.Filter`，預設走 `ebiten.FilterNearest`（Ebiten v2 的預設值）。這些都是**遊戲內部
  draw call** 的濾波設定，不是「最終畫面 → 視窗」這一層的縮放。
- Ebiten v2 的架構是：遊戲把邏輯畫布（本專案 `logicalW×logicalH`＝640×400）畫到一張內部
  image，再由 Ebiten 引擎自己把這張 image 縮放貼到實際視窗大小——這一層縮放**不受遊戲程式碼
  的任何 `op.Filter` 設定控制**，是 Ebiten runtime 內建、獨立於使用者 draw call 的最終合成步驟。
  Ebiten v2 對這個最終合成預設使用類似雙線性的平滑濾波（"screen" 濾波），且沒有暴露開關能改成
  nearest-neighbor（v1 的 `SetScreenFilterEnabled(false)` 語意在 v2 已不存在）。

**結論**：worklist 猜測的「可能 linear 暈染」成立——由於視窗可被拖曳成任意非整數倍率
（`WindowResizingModeEnabled`），且專案沒有（也無法用目前 Ebiten v2 API）覆寫最終畫面→視窗
這一層的縮放濾波，非整數視窗大小下像素藝術邊緣確實會被 Ebiten 內建的平滑濾波模糊，這是
Ebiten v2 runtime 本身的行為，不是本專案程式碼的 bug；`main.go:9696` 引用的 `run.go
SetScreenFilterEnabled` 是過期／不存在的說明，應更正或移除。可行的改善方向（本輪未實作，
留給下一輪）：限制 `WindowResizingMode` 只接受整數倍率、或在 `defaultWindowSize`／resize
handler 裡把實際視窗尺寸捨入到最近的整數倍。

## 現有 runtime evidence

| Contract | 現有 code evidence | 判定 | 下一個證據問題 |
|---|---|---|---|
| UI-01 title/menu | 原版 `0x1fe2c` scan-code loop（↑/↓ wrap；Enter/Space/`0xe0`/`0x52` confirm）、`0x25ebb` return dispatcher、DOSBox oracle `docs/figures/title-original-dosbox.png` 已固定 START／LOAD／CONTINUE 與 title cursor；四槽 selector、valid-save typed restore 與 indexed 畫面已接。CONTINUE 的 FDFIELD 控制映像、battle-local event state、current-runtime-order selector rebuild，以及標題 caller 的 opening／interactive range mode、HUD gate B／anchor 已閉合成唯讀 preflight；後續 map timing、live field、runtime units、future-group transaction 與未改寫 chapter0 pending roster 亦有嚴格 consumer | partial | 第三主選單 CONTINUE 的 production owner 仍缺動態 turn-writer／group-formula 的通用 pending-group binding，及 `0x117E7` 對應的正式 `Game` controller handoff；另缺刪除／覆寫與完整 boot 畫面差分 |
| UI-02 field | map/camera/cursor/unit/HUD Draw 約 3441–3568、4571、4595；camera、absolute/visible cursor、HUD anchor/gates 與 FDOTHER #130 panel 已有直接原版資料流；ch26 event61 所需 view/HUD 已達 E1。ch27 event62 已接向左一步第七拍 selector0，能由完整 raw row 與 `0x2066E` 已證實的新戰鬥回合初始值1啟用 event63；`sub_1A813(0)` 的敵軍 AI 前 owner、兩次 0x35822 增援、delta255 全白／delta0 恢復及 AI continuation 已接正式 runner。ch26_pre 返回 battle_ch27 的 view `(camera 9,49; cursor 14,54; visible 5,5)`、selector0 與 inherited HUD 已由 IDA／Capstone 閉合並接線；gate A 從存檔、anchor 從程序持續狀態、gate B 從 controller 取得，不猜章節常數。event63 的 indexed regression 由雜湊綁定 `NativeJoinConstructorTable` 建立凱麗 fresh raw `+0x42=151`，不再手填 fixture，也不由章節近似 HP 反推。ch00 的 `0x32999` 已以 FDOTHER #9 接12次索引呈現、pass6/7/8 snapshot 重建及 pass1 #95，兩次各12幀後能沿正式 handler 進入戰鬥、戰後、城鎮與整備。ch01 global event1/2 又驗證 turn4/5 各12次呈現後才執行 ACTING(3/4)，event2 對話不會越過 acting；缺 acting 資源時不發布 roster/cache/turn continuation。這些目前是 E1 決定性路徑，不是同狀態 DOSBox 畫面 E2 | partial | 除 ch26／ch27 event62/63／ch00／ch01 event1/2 E1 切片外，ch02+ 的逐章 dynamic view/gates/anchor producer、ch27 一般玩家／CONTINUE 同 roster/event/tick DOSBox 像素差分、該時點角色 raw record 的實際值，以及 `0x12c0d` 的 exact raw lookup predicate/order；另補 ch00 與 ch01 event1/2 同 camera/roster/pass 的原版逐幀比較 |
| UI-03 action menu | Docker Capstone `0x18890` + `0x18d8c`：↑0 attack、←1 spell、→2 item、↓3 wait/field interaction；native command grid每欄四列。item branch `0x1bbdc` 的compact兩欄四列input、`0x17eef/0x17fc0/0x184c0`完整 indexed compositor與12-frame三區clip schedule已有 Ebiten adapter；tracked item Enter transaction已接。`0x19953` 是另一 selector | partial | end-turn entry、indexed effect presentation、DOSBox visual diff與缺archive UX |
| UI-04 target/range | `0x1cff0` + `0x149f8` 證實 command record `+3/+4/+6` 參與 target-candidate geometry；`0x1bbdc` item case 0 的 two-stage targets、observed type5–24 effect dispatch 已閉合。item entry materialize `row[+0x12]+2`；first selector return後grid reset且selector回1。type23 destination把literal target code6傳給`0x115b6`，不是global selector6；兩層取消都回item panel。remake已接tracked transaction、occupancy/class/race/29×20 cost/terrain gate。**2026-08-20**：AoE 候選陣列上游生成器 `0x14818` 全鏈路（flood-fill/十字掃描/陣營篩選）已完整反組譯關閉（doc27 §6.4），本體亦確認無額外 LOS 判定（doc11 本輪段落）；本輪（見下「不可用目標灰化」小節）進一步窮盡 `0x14818` 全域 call-xref，鎖定玩家 UI 唯一消費端 `0x115b6`，逐指令反組譯後確認**原版沒有「灰化」視覺元素**——合法性只在按確認鍵當下用單一呼叫點 `0x14742` 判定一次，游標可自由移動、不合法確認會被靜默拒絕、不觸發任何額外渲染/音效分支 | partial | **2026-09-06訂正**：global selector6的production owner其實doc56/doc37(2026-07-28)早已閉合(見下方訂正段落)，非仍待；native argument↔weapon min/max mapping已收斂為distance+mode語意確認；indexed item/effect presentation已收斂為純presentation(道具名稱/icon/SFX)缺口。AOE／LOS／不可用目標灰化三項本輪已閉合（見下），不再是開放問題 |
| UI-05 dialog | dialog Draw 約 3590–3686；`dlgAdvance` 有 page/scroll state；ch01 original oracle `docs/figures/ch01-dialogue-original-dosbox.png` 固定左肖像下框、文字、page indicator | partial | 每種 upper/lower portrait anchor、control-code renderer、native clipping |
| UI-06 HUD | native map HUD `0x1acf3` 的 panel→terrain→AP→DP→optional unit icon→HP 已由 `BlitNativeMapHUD→ComposeNativeFrame` 接入 ch01 production full frame；display gates、persistent anchor、LMI1 #130／hex #0x83/#0x84、digit banks與FDICON selector均有 regression。`0x11cfa`證實HUD base是`work+0x8088`。FD2.SAV 初始快照為 camera `(1,13)`／absolute cursor `(8,17)`／visible `(7,4)`；原版錄影434.5秒的較晚比較幀則與remake對齊 `(1,13)`／`(8,15)`／`(7,2)`、tree icon及`A -05/D +10`。全 33 圖現具雜湊驗證後同步的 composition byte+3 與 terrain control；ch01／ch26／ch27 已改用 `native_map_hud_inherited`：gate A 由 custom save／native chapter restore 保存，anchor 在程序內持續，gate B 只接受已證實的 controller entry 1。event63 production regression 已由正式 JOIN table 提供 persistent raw record 並進 indexed path；#22仍只在 native admission 失敗時 fallback | partial | 除 ch26／ch27 E1 切片外，ch02+逐章動態 view/gates/anchor provenance、ch27 未修改一般玩家／CONTINUE 同一 roster/event state 的 pixel diff、`0x12c0d` exact raw lookup predicate/order；raw globals高階名稱仍不猜 |
| UI-07 postbattle | `campInput` battle result 約 2394；campaign node 可表達 post node；`campaign_full` 30 戰 transition matrix 已逐列展開。主迴圈直接指令、scenario `chNN→map(N-1)` 與 handler `chNN_post→set_chapter(N+1)` 共同證實玩家戰鬥 N 使用 raw `ch(N-1)_post`。13個既有同號錯接已全數清除；**2026-08-19 重跑 `tools/audit_postbattle_binding_gates.py`
現況為 24 個 postbattle 節點、19 active／5 blocked**（blocked：`ch17/ch22/ch23/ch24/ch29`；
`ch29` 即 `postbattle_ch29_persist` 空 placeholder，見上文與 doc56 討論）。raw ch06→玩家ch07 已閉合 map6 六格 selector0 event26 的 raw `+6` gate、slots9..27 mode寫入與 state16 producer；enemy turn10 event25 只有在 state16==1 時才建立34→44 runtime、寫state17，戰後再經slot43 raw gate、唯一JOIN12 persistent record進 `town_ch08`。未踏格反例維持34 slots；先前「第10回合必定增援」與96-slot空白 frontier斷言均已撤回。raw ch07→玩家ch08 已撤回無 producer 的初始 groups1／8／9／10，正常入口為party10＋group0共29 slots；event27回合2..7逐組追加兩筆，戰後接受29..41奇數 frontier，依序執行layout、ACTING33／34、完整全黑、JOIN5、sync與chapter8，再進 `town_ch09`。raw ch09→玩家ch10 現保留60／61兩種強推論 frontier，依原始位址執行 DAC delta 0→63 淡出、sparse record/view patch、delta 64→0 淡入、FDTXT_010 index4／5、ACTING37、JOIN11／6、sync與chapter10，再進 `town_ch11`。raw ch19→玩家ch20現以固定record0＋選15人和map19 group0建立83-slot入口；round15執行group1→84與JOIN28，round16精確略過，兩路共同JOIN25後進`town_ch21`。raw ch12→玩家ch13由table bytes固定interior entry `0x2389f`並接`town_ch14`。raw ch05／ch25／ch27則分別屬玩家ch06／ch26／ch28；第27戰天空之鑰成功分支不重用raw ch27。raw `ch15_post` 實屬玩家第16戰；**2026-08-18（doc26 §7.3/§7.4）已把 `postbattle_ch16_persist`
接上 `bindings/ch15_post.json` 並轉為 active**，鏈路(節點跳轉/binding/與`ch17_pre`
`roster_has(18)`互補條件/compile-time回歸)已逐節點核對無斷點；唯一剩缺口是 battle_ch16
一般玩家原版 runtime capture(確認 slots66-73/`[0x53bef]`/record0`+0x42`在postbattle當下
的實際填充狀態)，如實維持 unbound fail-closed 等待 live 驗證，**不代表整個 ch16 節點仍
unbound**。位址證據見[`fd2_ch19_post_ida.txt`](../data/ida/fd2_ch19_post_ida.txt)及各切片證據檔。 | partial | 以原版 handler offset／DOSBox input 差分核對每章是否進 town/shop/rest/preparation/ending；**2026-08-19現況**：blocked=`ch17/ch22/ch23/ch24/ch29`（ch16已於2026-08-18轉active，見左欄），第7／8／10／20戰尚缺一般玩家DOSBox E2；ch00 `0x3241f` 尚缺 raw FDICON key producer，仍是明示的 RGBA E1 近似（doc50 2026-08-19已排除`0x1f525`本身含此邏輯，見doc50） |
| UI-08 town | `0x2cd16/0x2cf71/0x11eb0`；FDOTHER#11/#61/#62背景、#10 label、FDTXT `0x1ef+selection`、FDICON pulse、三variant×六selection座標；23筆raw variant已接production。ch02 postbattle 以 `/tmp` sandbox route patch 走完原版 handler，variant0 [`selection0–5 contact sheet`](../figures/town-hub-six-selections-original-vs-remake.png) 的每格都能和指定 remake pulse 做 raw RGB 整幀 hash 配對。input trace另證實 Left/Right wrap、Shift+F1 reveal、Enter進variant5及Escape回selection5；`0x2ce7a/0x2ceac/0x2cef7` 不寫 pulse counter，已刪除方向鍵／secret reveal reset | partial（E1 + ch02 variant0 E2） | 補variant1/2 |
| UI-09 shop | purchase、sell、standalone equip與transfer均有original-resource regression及production owner；strict adapters在raw projection不完整時fail-closed。secret gate保存23筆normal selection與Shift/Ctrl/Alt-F1..F10 BIOS scan；chord只揭露selection5，後續confirm才進variant5。ch02 variant1/3/5 service0 selected phase均與同gold remake整幀AE=0；variant5四service、wrap及Escape→town selection5亦閉合。weapon purchase list四個selection、其後Yes/No、gold0不足金，以及gold1000裝備收件者selection0/cycle1也各自全幀AE=0；該E2使用screenshot-only LOADCH typed-party bootstrap，DX 2/2/1/2是visible HIT/EV與known equipment rows交叉約束的projection、不是直接raw dump。成功動畫裸畫面、尾端DATO第0幀恢復與`0x2d516`扣款odometer已接production；25個原版成功動畫原子樣本及16個扣款原子樣本各有整幀AE=0。正常campaign JOIN→LOADCH typed roster另有ch00→ch02 recipient regression，但不是完整playthrough E2/native FD2.SAV | partial（E1 + ch02 shop menu/purchase-list/confirmation/insufficient/equipment-recipient/success/debit stable E2） | recipient scroll、no-recipient/full、sell/equip/transfer child panel E2；其他章節route/state與native save |
| UI-10 church | `0x2d7bd` 左右四項循環；`0x3072f` dispatch `0→0x2ffa5` status、`1→0x2f8ea` item transfer、`2→0x30dc3` revive、`3→0x31385` class。class path已接 exact list/confirmation lifecycle；raw0已接兩欄 roster與完整唯讀`0x17aed` status/items→command/MP lifecycle。raw1與shop service3共用`0x2f8ea`：FDTXT510/511/512、source/item/destination roster、`0x2dc55(mode1)`、FDTXT506滿欄與raw remove→append/recalc均已接；destination roster保留source本人，self-transfer依原指令做unequipped尾端重排。缺 raw flags／identity fail-closed。revive已接 raw byte5 bit0候選、raw class×level費用、三列名單與完整feedback；成功animation/BGM lifecycle亦已接。 | partial/fail-closed | command effect/target、FD2.SAV與DOSBox E2 visual diff |
| UI-11 preparation | `0x2d0d1` 城鎮出發提示使用 FDTXT `0x201`／`(95,119)` 與原 town source；`0x2cc04..0x2cc87` 無城鎮提示先清 VGA、使用 FDTXT `0x19a`／`(100,119)`，肯定才在關框後呼叫存檔。`0x318ad` 清除30旗標；`0x31a7c..0x31b08` 左右±1、上下±10；`0x31e80` 接三區背景、10欄角色格、游標、彩色／灰色角色及 `0x17fc0` 狀態。`0x320fc`直接證實record0固定、旗標i對應record i+1；重製已修正為固定1人＋可選15／19人，總上場16／20。`0x1297d` 待機週期與 `0x31d3c` 最終確認的完整 Draw 確認生命週期均已接；原始圖像索引、記錄或資源缺值即退回 | partial（E1） | 查明跨戰場／城鎮的行程全域初始相位；取得合法晚期存檔，以同一狀態做 DOSBox／重製像素差分。`0x1f42d` 已更正為戰場進入演出，不屬此選人視窗 |
| UI-12 save/load | F5/F9 global path；save package 自有 schema；原版 `FD2.SAV` 的 `0x59cb` boundary、rolling-XOR/u32 byte-sum checksum、4×logical `0xa28` records at `+0x312b`（metadata `0x28` + roster `0xa00`）已由真實 sandbox decode、`tools/fd2save.py` 與 `internal/fdsave` regression 覆蓋。合法 IDA 9.4 已固定 reader `0x2602c..0x26098` 與 writer `0x30012`：兩者只處理 metadata `+0..+9`；writer 只由 `0x2cad7` 直接整備與酒店呼叫。production 以雜湊綁定的 `0x526b9` gate table 把 raw chapter 1..29 還原到 `town_ch02..27` 或 `preparation_ch23..30`，先完整驗證 persistent record→typed party、節點型別與重複 identity，再原子套用 campaign cursor、gold、party 與 raw metadata 保存值；ch21/ch27 postbattle inventory gate 不會重播，任何錯誤留在 selector且不落入 JSON loader。空槽及修改存檔 chapter1 有效槽畫面均與 DOSBox 全幀 RGB 相同 | partial（空槽 E2；有效槽排版與 restore 為修改／合成路徑 E1，不升為一般玩家 E2） | 未修改一般玩家有效槽 successful native-load、metadata `+10..+39` 其他可能 consumer、CONTINUE current-battle owner、delete/overwrite |

### 2026-08-19 現況掃描（worklist L1065／L1117／L1138／L1139，批次小任務，非新反組譯）

本節只做**現況核對與跨文件盤點**，逐項確認自 2026-07-26（本檔上次逐行更新）以來
是否有其他 doc 已經關閉這幾行列出的缺口；沒有的維持 partial，不重複造證據。

**L1065 — 本表整體 partial 欄位盤點（截至 2026-08-19）**：上面「現有 runtime evidence」表
12 行**全部**仍是 `partial`，沒有任何一行能升級成 `verified`／`closed`。逐行殘留缺口摘要
（詳細內容見各行本身，這裡只列尚未解決的頭條）：
UI-01（第三主選單 CONTINUE 的動態 turn-writer 通用 binding）、
UI-02（ch02+ 逐章 dynamic view/gates provenance，ch27 一般玩家 DOSBox 像素差分）、
UI-03（end-turn entry，見下）、
UI-04（weapon min/max/AOE/LOS/灰化，見下）、
UI-05（每種 upper/right speaker anchor、control-code renderer）、
UI-06（ch02+ 逐章 anchor/gate provenance）、
UI-07（postbattle 逐章 DOSBox 差分，見下方最新 active/blocked 統計）、
UI-08（town variant1/2）、
UI-09（recipient scroll、sell/equip/transfer child panel）、
UI-10（command effect/target、FD2.SAV／DOSBox E2）、
UI-11（跨戰場/城鎮行程全域初始相位、晚期存檔差分）、
UI-12（一般玩家有效槽 successful native-load、CONTINUE current-battle）。
這些缺口性質分兩類：一類需要 DOSBox-X 即時比對（本任務範圍排除），一類是可續靜態 RE／
remake 接線工程（見各行 D 判定）；沒有發現任何一行的 partial 判定本身是過期的。

**L1117 — UI-04 native weapon min/max、AOE、LOS、不可用目標灰化**：§「UI-04 geometry
slice」小節（下方）已閉合 command record `+3/+4/+6` 對應 `0x619fd+7*id` 靜態 spell table
的 `dist/range/mp/target` 欄位（IDs 0-35，逐 byte 核對）——**但這是法術/指令 command 的
min/max，不是「武器」的 min/max**。另外核對 `docs/knowledge-base/32-item-combat-stats-re.md`
146-169 行，武器類 item row `+0x0b/+0x0c` 餵給 `0x14818` 的 `a4/a5` 這條路徑**已被明確
撤回**過一次「range_min/range_max」的命名（該文件原話：「這些都不足以反推出通用武器射程
或 normalized `AtkMin/AtkMax`」），remake 目前改用獨立驗證的 `weapon_range.json`，不讀
raw `+0x0b/+0x0c`。本輪重新確認這個撤回仍然是目前最後結論，沒有新證據能重新命名這兩個
byte。**2026-08-20 更新——AOE／LOS／不可用目標灰化三項已全數閉合，不再是開放問題**：
AOE 候選陣列上游生成器 `0x14818` 全鏈路（`record[+3]`/`[+4]` → flood-fill/十字掃描 →
陣營篩選 → unit-index 陣列）已由 doc27 §6.4 用位址級反組譯完整追出；同一天稍早的 doc11
段落窮盡反組譯 `0x14818` 全部 480 bytes 本體，確認除已知的 Manhattan/十字距離規則與
flood-fill 佔用阻擋外，函式內完全沒有第三種呼叫（沒有 raycast、沒有呼叫任何地形 gate
函式），即「LOS 是否擋路徑」已有明確答案：**`0x14818` 本體沒有 LOS 判定**。「不可用目標
灰化」則由本輪（見下方新增小節「UI-04 不可用目標灰化」）窮盡 `0x14818` 的全域 call-xref
（8 個 caller 函式、17 個呼叫點）解決：玩家 UI 路徑（`0x18d8c`／`0x1bbdc`／`0x1cff0`，其餘
5 個 caller 皆為 doc11 已證實的敵方 AI 決策路徑、無玩家可見 UI）全部匯流到同一個互動
游標／確認迴圈 `0x115b6`，其唯一的合法性判定呼叫 `0x14742`（全域僅一個呼叫點，
`0x1175f`）只在按下確認鍵那一刻執行一次；方向鍵游標移動（`0x11b48`/`0x11b9b`/`0x11c59`/
`0x11bfa`）完全不參照候選陣列或呼叫任何合法性判定，游標可自由移到地圖任何格；不合法
確認被靜默拒絕（跳回同一個「讀下一個輸入」入口，跟按任何其他鍵一樣，沒有專屬分支）。
**結論：原版沒有灰化這個 UI 元素**，合法性只在出手確認當下判定一次。

**L1138 — UI-03 end-turn entry**：`91-worklist.md` 稽核記錄與 doc58 都指向同一個未閉合點——
doc58「續 N」的一次 live DOSBox-X 觀測已確認選單結構（上=系統選單/左=行軍/右=設定/下=END，
選「下」觸發結束回合確認框），並規劃「先下斷點在 `0x24618` 再結束回合，讀 EAX」作下一步，
但**該次 live session 尚未完成最後一步**，且本任務明確排除 DOSBox-X/WSL2，因此本輪無法
延續那條路徑。純靜態面：`0x1a30b` 家族（battle-entry indexed choreography）與 end-turn
本身的呼叫關係，在現有 doc26/56 中沒有找到新的直接反組譯證據；`0x19953`（battle selector
input）已確認呼叫 `0x36d98` 讀 scancode，Enter/Space/`0xe0`/`0x52` 走確認、`0x01`/`0x53`
走取消，但這是「selector 內部確認/取消」而不是「D8/END 選單本身怎麼呼叫到回合結算」。
維持 partial，worklist 判定（D，可續靜態，非必須 live）不變；本輪未新增反組譯（時間分配到
其他優先項目，未深挖）。

**2026-09-06 補完：答案其實已經在 `doc11` 裡，本行當時沒有查到——完全靜態閉合**。
`docs/knowledge-base/11-enemy-ai.md`「`0x16F55`：手動強制結束回合」一節(2026-08-20，同一天
的另一輪工作，回應的是worklist L145/L1038而非L1138，所以沒有交叉引用回這裡)已經完整反組譯
**正是本行要問的「D8/END選單本身怎麼呼叫到回合結算」**：`0x117E7`在游標下沒有可行動己方
單位時呼叫`0x16F55()`，這是一個0..3四項ring，selector3(「結束回合」/END)的完整呼叫鏈是
`0x1956B(0x4B)`(Yes/No對話框)→`0x19953`確認→若Yes且`[0x53C57]`仍為0：等待200 tick
(`0x3790A`)→`0x196CB`(收尾動畫)→**直接**呼叫`0x1A30B()`(回合orchestrator)，不跑任何
單位移動迴圈。FDTXT字串核對：`0x1A3`＝「要結束本回合的行動嗎？」，確認後`0x1A4`＝「好的，
就結束本回合的行動吧！」，两者都已用FDOTHER_004字型渲染目視確認，不是猜測。**這條鏈路
完全靜態，不需要活體DOSBox-X驗證**(本行原本卡住的「先下斷點再結束回合讀EAX」那條路徑已經
不需要了)。UI-03 end-turn entry至此收斂為已解，可改標A。

**L1139 — UI-07 postbattle，哪些章節仍 fail-closed（現況已與本表文字有落差）**：
`tools/audit_postbattle_binding_gates.py` 目前輸出 `postbattle_nodes=24
status={'active': 19, 'blocked': 5}`——**與本表 UI-07 行文字「17 active／7 blocked」不同，
已經有進展但未同步**。逐一核對：blocked 的是 `ch17/ch22/ch23/ch24/ch29`（`ch29` 即上面
doc56 討論的同一個空 placeholder）；**`ch16` 已經是 active**（`postbattle_ch16_persist`
現有 `handler_binding:"assets/cutscenes/bindings/ch15_post.json"`），doc26 §7.3/§7.4 記錄
這是 2026-08-18 的修復（`raw ch15 postbattle layout audit`），本表 UI-07 行與「明確缺口」
小節仍寫著「ch16 等仍 fail-closed」是 2026-07-25 的舊字句，**已過期**，下方逐行更新。
沒有 `postbattle_ch02/ch03/ch21/ch27/ch30_persist` 節點可比對（ch21/ch27 併入其他章節、
ch30 直接走 `ending`，非漏算）。

### UI-03 dispatch-wrapper recheck（2026-07-25，E0 partial）

Docker/Capstone 重新從 `0x18d8c` 入口線性追到 return，確認這是 action dispatch 的
**wrapper**，不能誤當 command-grid renderer：它先清 caller output 的 `+0` 與 global
`[0x53ec8]`。先前把 `0x1b83d(unitSlot,0)` 寫成「前序選擇」是錯的，現已刪除：它精確掃
unit `+0x0a + slot*2` 的八個 inventory slots，找 `bit0x40` 已設且 item ID `<0x80` 的第一格；
找不到時回 `-1`，wrapper 只設 output `+0=1`。命中時才經 `0x1b722 → 0x4e56c` 取該 slot 的
item record `+0xb/+0xc`，再呼叫 `0x14818(x,y,0,record+0xc,record+0xb,0)` 建立前序 target state。

其後 `0x1b8a6(unitSlot)` 精確計數八格中 `bit0x80` **未**設的 slots，因此它為零（所有 slots
空）時設 output `+8=1`；`0x1c269(unitSlot,0)` 為零及 `unit[+0x27] != 0` 都設 output
`+4=1`。前兩個 raw precondition 已閉合，三個 caller-visible flags 對應哪個可見 action／disabled
icon 仍未由 callee 或實機畫面閉合，SDD 保留 raw offsets，不能擅自畫圖示。`0x177fc`
是 wrapper 等待的選擇 loop，回傳 `-1` 則直接取消；非取消才按 `[0x53c57]` 分派：0 走
attack pipeline、1 走 `0x1cff0` command selector、2 走 `0x1bbdc` item selector，其他值才走
`0x13fd4/0x190ac` 的休息回復／格子互動路徑；`0x13fd4` 已由直接指令固定為
raw `+0x25/+0x26` 零值 gate 與 `floor(maxHP/5)` 回復，不是泛稱的 wait helper。
這補強 UI-03 的取消階層與 dispatch 邊界，但不增加
任何 renderer 或 flag 語意斷言。

`unit+0x27` 的 action effect 已額外由 `0x1598a` 固定：它先取 `0x1c269` command count，隨即讀
`unit+0x27`；count 為零或此 byte 非零都在**任何** command record、MP gate、target-grid 建立之前
直接走 zero return。因此 `+0x27` 是整個 native command submenu 的 gate，不只是 wrapper 的一個
局部 flag。`0x1eb64` 的 `lea [ebx+0x27]` 是 UI resource frame index，並非 unit access。後續已定位
command 22 的 `0x22BE1→0x22D1B` 會寫入 `rand()%4+2`；狀態名稱與所有 producer 仍未閉合，故不得稱其為
沉默、封魔或任一 status effect。

### UI-03 action overlay/input closure（2026-07-25，E0 partial）

`0x173e7` 先由四個 availability words 找第一個零值，寫 global current action `[0x53c57]`。
`0x177fc` 的 input loop 再以同一四-word state 拒絕不可用方向：scancode `0x48/0x4b/0x4d/0x50`
分別只在 word `0/1/2/3 == 0` 時選擇 `↑/←/→/↓` action `0/1/2/3`；`0x1c`/`0x39`
（Enter/Space）回 confirm，`0x01` 回 `-1` cancel。這是 command-grid `0x1d51d` 以外的 action
chooser ABI，現有 remake ring 的四向 mapping 只可作 interaction approximation。

renderer `0x1741c` 以 `[0x53a89]` 的 relative asset table 選四張 state-dependent images，透過
`0x4e9e4` 寫入 indexed overlay。它不是瞬間顯示：四張都從 shared origin `+0x390` 開始，每次
present 後 4-frame slide 分別更新 offset `up -= 0x8e8`（5 native rows）、`left -= 6`、
`right += 6`、`down += 0x8e8`。`0x175a9` 在開啟前備份 72×72 bytes（`0x1440`）到 private buffer，
`0x17643` 在每幀 restore。Docker Capstone 重讀 `0x176b4` 後，撤回「單純反向」的過度概括：它的
四幀 close 初始 byte offset 是 `[−0x23a0,0x378,0x3a8,0x2ac0]`，每幀改為
`[+0x8e8,+6,−6,−0x8e8]`。這證實十字狀 indexed overlay、方向與節奏。asset provenance 現已閉合：boot
`0x25c97..0x25cac` 將 `FDOTHER.DAT #2` 交給 `0x111ba`
並寫入 `[0x53a89]`。raw #2 是 untagged 78-cell offset bank（首 `u32=0x138` 即 directory end），cell
為 `{u16 width,u16 height,width*height indexed pixels}`；`0x4e9e4` 逐列 direct blit，index 0 preserve。
實測為 74 個 24×20、4 個 24×16 cells，strict `fdother.ParseRawCellBank` 與 player asset regression 已覆蓋。
`0x1741c` 的 relative table index ABI 也可重跑：每個方向取 `availabilityWord`（同一個供
`0x177fc` gate 的四-word array）與 `directionState`，cell index=`3*availabilityWord +
2*directionState`，再讀 `u32 relativeOffset=base[index]`、貼 `base+relativeOffset`。官方 IDA 重新
追 `0x18d8c` 後更正舊斷言：**battle action wrapper 的 directionState 是固定 `[0,1,2,3]`**，故
available cells=`[0,2,4,6]`，disabled cells=`[3,5,7,9]`。先前把 `0x1728c` 的
`[0x12+(byte_51e61==0),0x14+(byte_51e62==0),0x16+(byte_53af9!=0),0x18+(byte_51aab==0)]`
套到 battle action 是錯誤；該 caller 選中方向後只切換這些 byte state 並重畫自己的巢狀四向 menu。
`fdother.BattleActionOverlayState` 現以 unit test 固化真正 battle table；它不替這個另一個 submenu
的四個 byte 命名。remake runtime 現可選擇性讀玩家自己的 `FD2_ORIGINAL_FDOTHER`／
`assets/original/FDOTHER.DAT`：FDOTHER#0 的 6-bit VGA palette 轉為透明 index-0 palette，#2 的 raw
cells 0..9 由 caller-owned lifecycle 依 opening `0..3`／closing `0..3` 幾何貼到 cursor。輸入在兩段
四-present 序列中被鎖定，confirm/cancel 的 child state 只在 close frame3 已呈現後提交；沒有把
`0x1741c/0x176b4` 未提供的 delay 猜成毫秒值。這不包含原版 asset，也不把 current remake 的
attack/spell/item availability approximation 說成 native `0x1b83d/0x1c269/0x1b8a6` 全等價。
[8-frame Xvfb artifact](../figures/action-overlay-open-close-remake.png) 與
[settled overlay screenshot](../figures/action-overlay-native-remake.png) 已證實 loader、palette、
cell geometry、frame order 與 font-independent draw path 實際出畫；它們不是原版 DOSBox 畫面對照。

2026-07-25 renderer gate 縮小：native skin adapter 現至少直接套用 `0x1b83d` 的「equipped 且
ID `<0x80`」attack 前提，並在 raw `NativeCommandMask` 非零時以其作 spell availability；沒有 raw
mask 的舊 editable scenario 才退回 normalized `Spells`。attack target geometry、`unit+0x27` 的名稱及
item effect 仍未閉合，因此這不是 native gate 全等價。

2026-07-26 official IDA 9.4 重讀 `0x1741c/0x176b4`：open/close 都是四次 cell blit、present
(`0x11eb0`) 與 72×72 backup restore 的直線迴圈；迴圈本體沒有顯式 delay/wait call。因此 offset
sequence 是 E0，但每一幀應停留多少 presentation ticks 尚未由這兩個函式證實；remake 不得自行把
它命名或硬編成 60ms 等固定動畫時間。

### UI-03 native command-grid renderer closure（2026-07-26，E0）

official IDA 9.4 的 `0x1d51d→0x1ceed` 證實 command submenu 是 320×200 indexed-buffer 的四列 grid，
不是 remake 的單列 spell list：對第 `i` 個由 `0x1c269` 輸出的 command ID，`column=i/4`、`row=i%4`；
label 由 FDTXT_000 的 `0x1b9+commandID` 畫於
`x=0x12+0x64*column, y=0x67+0x16*row`。選中項 text palette index=`0xc9`，其他項=`0xcd`；同一欄的
MP/record `+5` 數字使用右側 `x+0x49`／`y+5` 的 numeric renderer。↑/↓在完整 list 頭尾 wrap，←只在
index≥4 時減4，→只在 `index+4<count` 時加4，故水平不 wrap；Enter/Space 還會以 unit `+0x44` 與 command
record `+5` 的 MP gate 再確認一次。這閉合 layout/input ABI，但不命名 `+5` 以外的 command effect，也不使
normalized `Spells` list 自動成為原版 command grid。

2026-07-26 label bridge：若玩家提供 editable `assets/data/command_labels.json`（FDTXT_000 的
`0x1b9+commandID` export），remake 會只覆蓋已載入 EXE spell rows的 presentation label；缺檔或
malformed JSON 維持 normalized labels。這改善既有 spell presentation 的原始文字 fidelity，並沒有把
legacy vertical spell UI 宣稱成 `0x1ceed` command grid，也沒有擴大 effect semantics。

2026-07-26 native command-grid runtime slice：當 player-provided FDOTHER VGA palette 與 editable
`command_labels.json` 都存在，ring 的 command branch 以 `NativeCommandMask` 開 native four-row grid，
label 直接採原始 `0xc9/0xcd` palette entries，↑↓／←→採 recovered ABI。confirm 現一律明確停在未接 native
two-stage target/effect，**不再**因 ID 剛好有 EXE spell row 就送入 legacy `CastArea`；缺任一 asset 則退回 legacy
spell UI。這是可視 layout/input slice，不是所有 command effect 或 native frame/background renderer 的完成宣告。

runtime audit（2026-07-26，更新）：chapter `Scenario.Party` 現已保存 exact
`initial_command_mask`；產生器從 EXE `character_defaults.json` 依角色 index 帶入，並已重產 ch01..ch30。
loader 僅接受空值或四 bytes，避免以截斷值製造假 command inventory；persistent roster 亦保留 runtime
fifth byte。這只閉合 raw availability bridge，不以 normalized `Spells` 填補，也不證明 command effect、frame
background 或全部原版 input state。

2026-07-25 重讀 `0x1741c` 並以 `0x179d5` 交叉驗證後，收斂了一層 framebuffer anchor：四張 cell
的共同地址為 `framebuffer + 0x8088 + 0x18*cursorColumn + (0x18*0x1c8)*cursorRow`。
`0x11bfa/0x11c59` 的 cursor movement 證明 `[0x53ab9]/[0x53abd]` 是這對可視 cursor coordinates：
在右／下邊界時分別改寫 `[0x53aa9]/[0x53aad]` 的 camera scroll，否則才遞增它們。因此撤回「A/B
語意未證實」；`fdother.ActionOverlayOrigin` 已把命名後的 byte-address expression 獨立測試。剩餘的是
將 native indexed framebuffer 接到 runtime，以及 DOSBox visual-diff 驗證實際 skin。

## 明確缺口（不可用 fallback 掩蓋）

- `item` action 仍是提示字串，不能宣稱道具 UI 完成。
- touch 目前只移動游標，不能 confirm/cancel；沒有 gamepad/key-binding UI。
- `unit_present` 與 `indexed_transition` 尚未有 native indexed adapter；RGBA／色塊 fallback 僅供診斷。
- church 主選單前兩項仍會顯示「尚待原版 callee 完整接線」。
- battle `Tab` 可結束回合是現有配置，不代表已證實原版是 Tab 或可見選單；需 E0/E2。

## 可重跑盤點命令

```sh
rg -n 'func \(g \*Game\) (enterNode|campInput|Draw)|ringInput|尚未實裝|尚待原版' remake/cmd/fd2/main.go
git diff --check
test ! -e /tmp/fd2cap
```

### UI-01 DOSBox title oracle（2026-07-25，E2 partial）

`tools/docker/fd2-dosbox-screenshot.Dockerfile` 以既有 Xvfb/xdotool/ImageMagick image 建立隔離 runner；
它只接受可寫的 **`/tmp` game sandbox** 掛載與明確 `/tmp` shots mount，原始 `FLAME2` 不掛進容器。
以 `svga_s3`、`fixed 18000` 跑 `wait:2; Escape ×4; wait:8` 後取得
`docs/figures/title-original-dosbox.png`（320×200 crop）。畫面直接證實 title 的 START／LOAD／CONTINUE
縱列與 START cursor；這是 UI-01 的 E2 畫面 oracle，不證明 title input dispatch、存讀檔語意或 remake
title renderer 已完成。

同一 timeline 在 title 選 LOAD 後可重現 `docs/figures/load-empty-original-dosbox.png`：原版在空 save
sandbox 顯示四列 `1)` 到 `4)`、每列「無儲存記錄」，第一列有 selection outline。這是 UI-12 的空槽
E2 oracle；它沒有有效存檔資料，因此不證明 record layout、LOAD 成功路徑或 SAVE overwrite confirmation。

START 分支首個可重現對話 crop 為 `docs/figures/ch01-dialogue-original-dosbox.png`：第一章場景中可見
左側 DATO portrait、下方藍框、兩行文字與框底中央 page indicator。這提升 UI-05 的一個 lower/left
E2 anchor；它不涵蓋 upper/right speaker、FFxx control code、完整 pagination timing 或 remake renderer。

### D8 native trace（2026-07-25，E0 partial）

Docker/Capstone 直讀 `0x1a30b`：battle-entry 先掃 unit buffer、以 `0x1da16` 更新 320×200
offscreen surface，再呼叫 `0x11eb0` present；接著呼叫 `0x1a813`／`0x1a866`，並在 phase
`[0x53ecc]==0` 時進入 `0x1a7bd → 0x1d80b → 0x1a7f1`。其中 `0x1a4c7` 明確呼叫
`0x1f1cc(0x52)`、20ms、`0x1f30a(0x52)`，完成 redraw 後才進後續 dispatch；`0x1f1cc`
與 `0x1f30a` 都配置 64000-byte indexed buffer、呼叫 `0x15f0e` 取資源並逐幀
`0x11d40` palette/present。進一步 trace `0x15f0e` 可確定它以 `base + 6 + frame*4`
取 frame offset，descriptor 前兩個 signed words 是 width/height，先配置
`width*height+8` 再經 `0x4e96f` 解壓、`0x4e85b` 以 stride 寫入 indexed surface；
這是可重用的 frame-resource ABI；`[0x53a81]` 的 loader provenance 已由 UI trace
確認為 `FDOTHER.DAT` resource #5 的 `LMI1` 容器（doc35 §4.2.5），remake 已新增
strict `fdother.ParseLMI1` 與 codec regression。
Codec/blit correction：`0x4e8af` 對每個 decoded pixel 都直接 store，index 0
也是 opaque overwrite；舊「index-0 transparent preserve」斷言已撤回。
`LMI1Entry.BlitOpaqueAt` 保存此路徑，`BlitAt` 則只留給另有證據會 preserve zero
的 caller；兩者都要求顯式 surface/anchor，未擅自接入 D8 layout。
實際玩家 `FDOTHER.DAT#5` regression（138 entries，#0x52=72×14）另證實 directory
offset 只標示 entry start：`0x4e916` 的 repeat 可跨下一個 offset，原版依 width×height
停止，因此 parser 不得把 next offset 誤當壓縮 stream 結尾。
`0x1f42d` 不是文字 helper：`0x1f1cc` 以 offset `100,75,50,25,0` 各呼叫一次，
每幀把 LMI1 **entry #0x52** 貼到 offscreen `(85-offset,82)` 與
`(165+offset,81)`（stride 456），present 一 tick，再以 `0x15e71` restore；這是
兩側 UI cell 的五幀滑入。它的反向 path 由 `0x1f30a` 使用同一 helper。這只閉合
indexed cell/座標/節奏，不足以命名 MAP/TURN 欄位或確認其為「行軍確認圖」，故 UI-11
仍 partial。

下一輪先處理 UI-03／UI-04 的原版 dispatch 與 weapon reach provenance，再補 D8 的
MAP/TURN text source 與 YES/NO input ABI；在此之前不新增猜測性 renderer。

#### D8 scope correction (2026-07-26)

官方 `0x1a30b` 本體沒有 `0x15f84` 呼叫；它先以 raw unit-record gates 做 `+0x40` 向 `+0x42` 的 `max/5` transition，再進 indexed redraw 與 `0x1f1cc/#0x52` slide。故目前 D8 證據只支持 battle-entry indexed choreography，不支持 MAP/TURN/ENEMY/FRIEND/NPC 字串或 YES/NO input；那些欄位仍是缺口。

#### D8 觸發條件訂正："battle-entry" 這個框架本身不準確，`0x1a30b` 是回合結算/推進主流程，不是入場專屬 (2026-09-06)

`91-worklist.md` 791 這輪(2026-09-06)完整反組譯了 `FUN_0001a30b`(即本節的 `0x1a30b`)全文，
連同它呼叫的 `FUN_0001d80b`——結果顯示本節「battle-entry」這個框架從一開始就是誤導性簡化：

```c
FUN_0001a30b(void) {
  ...(own regen / 逐單位掃描更新等)...
  FUN_0001a813(); FUN_0001a866();
  if (DAT_00053ecc == 0) {              // ← 關鍵閘門
    FUN_0001a7bd(); FUN_0001d80b(); FUN_0001a7f1();
    if (DAT_00053ecc == 0) {            // ← 再檢查一次，兩層都要通過
      ...
      FUN_0001f1cc(); thunk_FUN_0003e01d(); FUN_0001f30a();   // 就是D8本體(本節已知)
      ...
    }
  }
}
```

`DAT_00053ecc` **不是**「battle-entry phase counter」——`docs/knowledge-base/25-battle-event-
system.md`(獨立、早於本輪的既有文件)已把它記載為**逐章戰場事件handler(`0x51b19`跳表)寫入
的raw pending碼**(`0`=繼續、`1/2`=勝敗判定觸發)，`FUN_0001d80b`的迴圈本體逐一掃描存活敵方
單位、呼叫`(**(&DAT_00051b19 + DAT_00053c03*4))()`(逐章handler)，**一旦某次呼叫把
`DAT_00053ecc`寫成非0(判定出勝敗)，迴圈立刻break**。

**這代表D8的`0x1f1cc`/`0x1f30a`slide只會在「完整跑過一輪全體單位win/loss掃描、確認勝敗都
還沒發生」的時間點觸發**——也就是**每回合結算(end-turn)推進到下一回合之前**，不是「進入
戰場的那一刻」。doc57先前(2026-07-25/26)把這整條呼叫鏈定性為「battle-entry indexed
choreography」是**不準確的框架**，只是碰巧`FUN_0001a30b`也會在戰鬥剛開始時執行一次(初始化
第一回合)，讓「入場」看起來像是合理的觸發時機，但真正的閘門條件(`[0x53ecc]==0`雙重檢查)
綁定的是「這一輪掃描完，沒有人剛好輸贏」，不是「剛進入戰場」。

**這完整解釋了91-worklist.md 791本輪三次live嘗試(截圖法×2、`BPLM`記憶體斷點×1)全數落空的
原因**：三次嘗試都只走到LOAD→戰前過場→打開戰鬥指令環，**沒有一次真正執行完一整個回合**
(End-Turn)，`FUN_0001a30b`很可能根本還沒被以「回合結算」模式呼叫過，`[0x53ecc]`自然全程
維持初始值不變——不是這個live驗證方法有問題，是三次嘗試都還沒推進到真正會觸發它的遊戲
階段。**下一輪如果要live驗證D8**，需要先讓玩家單位完成至少一次End-Turn(既有的「空地格→
Return開系統環→↓選END→Enter→Enter確認YES」捷徑，`tools/fd2_chapter_sweep.py`已有實作
可參考)，而不是只停在戰鬥開場畫面。

#### D8 與既有「ENEMY PHASE」/「PLAYER PHASE」live觀察首次交叉引用 (2026-09-06)

`91-worklist.md` 791 這輪直接呼叫`tools/fd2_chapter_sweep.py`的`find_empty_adjacent_tile()`
(importlib載入既有函式，不是重寫)找到空地格,跑完完整End-Turn序列(系統環→END→YES確認)，
**確認YES後畫面直接疊出橘黃色英文字樣「ENEMY PHASE」在戰場地圖上**——截圖存證：
[`ch27-enemy-phase-banner-live-verify.png`](../figures/ch27-enemy-phase-banner-live-verify.png)。

**誠實訂正(同日稍後發現)**：本輪commit最初把這個畫面稱為「D8調查以來第一次真正目擊」，
這句話是錯的——`docs/knowledge-base/58-remake-live-verification-log.md`(續六十/續六十一等
多輪，均早於本session)與`docs/knowledge-base/99-chapter-sweep-results.md`都已經**多次、
獨立地**live觀察並記載過這個「ENEMY PHASE」banner(甚至還記載過對稱的「PLAYER PHASE」，
99文件的「敵方因為全滅直接跳過」那個場景就是PLAYER PHASE觸發的例子)——`confirm_end_turn()`
這個既有函式本身的docstring也早就假設End-Turn會跳出這個banner。**這不是全新發現，是本輪
第一次把這個早已存在、多輪重複觀察過的live現象,跟doc57本節2026-07-25/26原始「D8」調查用
「MAP/TURN/ENEMY/FRIEND/NPC」英文代稱描述的未知欄位接上關聯**——「ENEMY」這個代稱與「ENEMY
PHASE」字樣吻合，暗示doc57原作者當時可能是從反組譯出的字串/呼叫模式推測有這類欄位存在，
但doc57本身從未引用過doc58/doc99既有的live觀察紀錄去交叉核對這個假說，本輪才第一次把兩邊
接起來。**誠實範圍**：尚未反組譯這個banner字串的來源resource id(doc58/doc99的多輪紀錄也
都只是live觀察畫面內容，未反組譯字串來源)、doc99確認PLAYER PHASE也存在但doc57的MAP/TURN/
FRIEND/NPC其餘三個代稱是否對應到別的畫面元素仍未查、也未確認這個banner文字層與本節已反組譯
的`0x1f1cc`/`0x1f30a`(sprite/RLE blit滑入動畫)是否為同一視覺元素或另一個獨立疊加層。下一輪
應該對`FUN_0001a30b`呼叫鏈裡負責畫面疊字的呼叫點
做反組譯定位，而不是繼續被動live截圖等待更多banner出現。

**2026-09-06續七,執行上述建議,在`FUN_0001a30b`尾端(`[0x53ecc]==0`雙重通過後的最深層分支)
找到兩個新的候選迴圈**：
```c
for (iVar4 = 0; iVar4 < 9; iVar4++) {
  FUN_00015f0e();                    // 已知的frame/resource取件primitive(doc57本節已記載)
  if (6 < iVar4) { FUN_000187d6(); } // 條件式呼叫
  thunk_FUN_0003e01d();
  if (iVar4 == 8) { thunk_FUN_0003e01d(); }
  FUN_00015e71();                    // 已知的restore primitive
}
for (iVar4 = 2; iVar4 < 6; iVar4++) {
  if (iVar4 == 5) { iVar4 = 9; }     // 只跑iVar4=2,3,4三次
  FUN_00015f0e();
  FUN_000187d6();                    // 無條件呼叫
  FUN_00011eb0();                    // 已知present primitive
  FUN_00017aa9();                    // 已知tick primitive
  FUN_00015e71();
}
```
**新反組譯`FUN_000187d6(param_1,param_2,param_3,param_4,param_5)`**：這是一個**通用N位數字
繪製函式**——`param_3`是要畫的數值(clamp到>=0)，`param_5`是位數(2或3)；若`param_5==3`且
值>999、或`param_5==2`且值>99則只呼叫一次`FUN_00016886()`(溢位處理，畫overflow符號)，
否則迴圈`param_5`次呼叫`FUN_00016886()`(逐位數繪製)。**這正是`FUN_0001a30b`裡緊接在
`0x15f0e`(取D8面板資源)之後、與已知present/tick原語同一個迴圈內被呼叫的函式**——時機上
與本輪live觀察到的「ENEMY PHASE」轉場完全吻合，強烈暗示**這個迴圈同時繪製了D8面板本身
(經`0x15f0e`)與某個數字欄位(經`0x187d6`，很可能是doc57原始「TURN」代稱指的回合數)**。
**誠實範圍**：`FUN_00016886`(實際逐位數blit的leaf函式)本輪未反組譯，`0x187d6`的
`param_1/param_2/param_4`(可能是螢幕座標/來源buffer)也未展開，仍不能100%確認這就是
「TURN」欄位而非其他數字(如HP/傷害數字，因為這是通用工具函式，全遊戲共用)——但呼叫時機
(卡在`0x53ecc`==0雙重確認之後、與D8的`0x15f0e`同一輪迴圈)是本輪能拿到最強的間接證據。
下一輪應反組譯`FUN_00016886`本體與`0x187d6`的座標參數，確認繪製位置是否落在D8面板範圍內。

**2026-09-06續八,反組譯`FUN_00016886`本體+`0x187d6`原始反組譯,找到與D8面板共用同一個資源
容器的直接證據**：`FUN_00016886`本體只是包一層stack-check再呼叫`FUN_0004e98d()`——這正是
本文件其他章節(town-hub investigation)已完整反組譯過的**raw/palette-band/solid-fill三模式
blit函式**，證實`0x187d6`的逐位數繪製走的是**真正的blit呼叫**，不是字型渲染引擎，跟本篇
「digit/overflow banks」既有記載的圖形化數字系統一致。**更關鍵的發現**：`0x187d6`原始
反組譯顯示它呼叫`0x16886`前會`PUSH dword ptr [0x00053a81]`——**這正是本節同一份文件稍早
已確認的loader provenance「[0x53a81]=FDOTHER.DAT resource #5的LMI1容器」全域**！這代表
**這個疑似「TURN」計數器的數字繪製,跟D8面板本身(`0x1f1cc`/`0x1f30a`經`0x15f0e`)共用同一個
FDOTHER.DAT resource #5容器**——不是巧合的資源重疊，是同一張圖(或同一個LMI1容器裡不同
entry)同時提供了面板背景圖與數字字型glyph。另外`0x187d6`把要畫的值(`param_3`)`+0xa`(10)
後才當index傳進`0x16886`,暗示這個LMI1容器裡index 0-9可能保留給其他用途(圖示/符號)，
數字glyph 0-9實際存在index 10-19。**誠實範圍**：仍未反組譯出resource #5的完整entry清單
去確認index 10-19真的是`0-9`數字字型(需要`tools/export_sfx.py`同類的LMI1 dump工具，本輪
未執行)，也仍未證實這個數字欄位具體代表回合數而非其他數值——但「共用同一個resource #5
容器」這個結構性事實已經是靜態證據，不是猜測。此結論已足夠支撐下一輪直接dump FDOTHER.DAT
resource #5全部entry做視覺比對，而不需要再重複這輪的反組譯路徑。

**誠實訂正(同日續九，不需要重新dump)**：本文件`0x53a81`一節(§4.2.5)早就完整記載過resource
#5的數字glyph清單——**`#31-40`=白/藍影0-9(戰鬥狀態欄用)、`#42-51`=白/綠、`#119-128`=白/
黃橘**——本輪`0x187d6`的「+0xa(10)」index偏移跟這三套任何一個的起始index(31/42/119)都不
精確吻合，代表傳進`0x16886`的index不是LMI1最終sub-resource index本身，`FUN_0004e98d`
內部或其他呼叫層還有一段base offset計算本輪未追出。**這不影響「TURN候選用resource #5共用
glyph bank」的結構性結論**，只是精確對應到31-40/42-51/119-128哪一套仍待查——**不需要重新
dump resource #5(本文件§4.2.5已經dump過)，用既有dump結果核對index運算即可**，這是本輪
第二次差點重複「檢查既有證據」紀律違規(第一次是ENEMY PHASE的「第一次目擊」誤稱)，誠實記錄
避免再犯。

**2026-09-06續十,追完最後一段呼叫鏈,確認index運算本身，結論：這是resource #5一個先前
從未記錄過的第4組數字glyph(index 10-19)，不是既有的31-40/42-51/119-128任何一組**：
反組譯`FUN_00016886`原始位元組(先前只拿到無用的薄decompile)：
```
0x16886(base_ptr, index):
  stack_check(0x20)
  EDX = base_ptr; EAX = index
  EDX = EDX + [EDX + EAX*4 + 6]   ; 標準LMI1 directory查表(base+directory[idx*4+6])
  FUN_0004e98d(entry_ptr=EDX, x=0, y=0, dst_stride/base=同一參數重複, param_6=-1)
```
`param_6=-1`(0xFFFFFFFF)正是`FUN_0004e98d`已知三模式的**「原樣寫入,不重著色」**模式——
確認`FUN_0004e98d(ushort *param_1,...)`的`param_1`就是這裡算出來的LMI1 entry指標,不是
index本身。**index運算精確等於`digit值+0xa(10)`**(來自`0x187d6`)——即digit 0→index 10、
digit 9→index 19。**這個index範圍(10-19)跟doc35§4.2.5已記載的三組數字glyph(31-40/42-51/
119-128)完全不重疊**——代表resource #5裡**還有一組先前任何一輪都沒記錄過的數字glyph
(index 10-19)**，且用`param_6=-1`原樣複製(不像其他三組可能透過`0x4e8d3`的LUT重映射做
變色)，暗示這組專門用於本篇的end-turn轉場數字顯示,不是共用戰鬥狀態欄的既有三組。**item 791
的「TURN」候選欄位到此已達到高信心的靜態結論**：resource #5 index 10-19是一組獨立、先前
未記錄的數字glyph，很可能就是end-turn轉場banner的回合數顯示，原樣複製不重著色。**誠實範圍**：
仍未實際dump index 10-19去看glyph長相是否真的是0-9(理論上跟31-40等其他組同樣是6×8,但本輪
沒有實際解出PNG核對)，也仍未100%證明這個數字欄位語意上真的是「回合數」而非其他計數——但
呼叫鏈/index運算本身已經是byte-exact反組譯結論，不是猜測。維持D，但「TURN」欄位已經是本項目
在791這條調查線上除了「ENEMY」之外最扎實的第二個具體發現。

**誠實訂正(2026-09-06續十一，「第4組數字glyph(index 10-19)」結論錯誤，予以撤回)**：先跑了
實際存在的`tools/decode_lmi.py`工具(前一輪只靠反組譯推論，從未真正dump過)：
```
python tools/decode_lmi.py extracted/raw/FDOTHER/FDOTHER_005.bin extracted/raw/FDOTHER/FDOTHER_000.bin .wsl_build/lmi_probe
```
結果resource #5的index 10-19尺寸完全不一致(`#10 3x16`、`#12 16x3`、`#13 16x16`、`#18/#19
14x10`……)，**不是均一的6×8數字glyph形狀**，直接證偽續十的「第4組數字glyph」結論。回頭
重新反組譯`0x187d6`的完整三條分支才發現先前的「+0xa」判讀只挑了其中一條分支，遺漏了另外
兩條：
- **3位數溢位分支**(`param_5==3`且值>999)：`0x1880f MOV EAX,[ESP+0x3c]; 0x18813 ADD EAX,0xa`
  ——這裡的`[ESP+0x3c]`不是常數0，是**呼叫端傳入的第4參數(下方證實=42)**，「+0xa(10)」是
  **相對於這個base的偏移**，不是絕對index 10-19。
- **2位數溢位分支**(`param_5==2`且值>99)：直接`PUSH 0x5d(93)`——完全繞過base+offset運算，
  push一個寫死的常數index，兩條溢位分支的index計算方式甚至不一樣，本來就不該套同一套規則。
- **正常(非溢位)渲染路徑**(`0x1883c`起，本輪首次追到)：`MOV BL,[ESP+0x40]; ADD BL,0x30`
  (位數轉ASCII字元'2'/'3')組出格式字串，`CALL 0x37b29`(等同`sprintf(buf,fmt,value)`)，
  接著逐位數迴圈(`0x1885e`-`0x18886`)：`MOVZX EAX,[ESP+EBX]`(取sprintf輸出的第i個ASCII
  字元)→`ADD EAX,[ESP+0x3c]`(**加上同一個第4參數base**)→`SUB EAX,0x30`(ASCII轉0-9再套base)
  →組4個參數(含`x_pos=EBX*6`、`EBP`、`[0x53a81]`容器、算出的index)呼叫`0x16886`。

**關鍵新證據——直接反組譯`FUN_0001a30b`兩個呼叫`0x187d6`的call site(`0x1a678`/`0x1a6fa`)
的push序列**：兩處都是`PUSH 0x3(digit_count); PUSH 0x2a(42! glyph base); PUSH [某個live數值
的table查表結果]; ...; CALL 0x187d6`——**兩個call site的glyph base參數都是42**，也就是說
`0x187d6`的index運算是`(ASCII digit - 0x30) + 42`，**精確落在doc35§4.2.5早就記載的白/綠
數字glyph`#42-51`裡**，不是新的第4組，也不是「10-19」。續十的「+0xa」只是溢位分支裡的一個
特例(意義應該是同一個base之後的第10格，很可能是一個「溢位/滿格」提示符號，不是完整的
0-9數字glyph重複組)，被誤判成整個函式的index公式。**index 10-19在decode_lmi.py裡量到的
不規則尺寸小圖，跟這條數字渲染路徑完全無關**，只是resource #5裡剛好排在數字glyph前面的
其他UI小圖，本輪之前的静态推論方向就走偏了。**item 791「TURN」候選欄位的正確結論**：這是
resource #5**已知**白/綠數字集(`#42-51`)的3位數渲染，兩個call site各自從不同的global-table
查表位置(`[0x53a49]+EDI*456+0x812f`與`[0x53a49]+0x8088`／`[0x53bef]`)取值渲染——語意上仍是
「某個3位數HUD數值」，是否確實是「回合數」依然未證實(呼叫時機仍是本輪最強的間接證據，見
續八/續九)，但**glyph來源已改判為既有的`#42-51`集，不再宣稱有未記錄的第4組**。維持D。

**2026-09-06續十二，item 791「YES/NO input仍未證實」子句取得byte-exact靜態答案**：反組譯
`FUN_0001a30b`的三個直接caller(`0x13565`/`0x16f55`)發現`FUN_00016f55`是一個依`DAT_00053c57`
(0/1/2/3)分支的指令環主迴圈，`case 1`分支會先跑一輪重置全部單位acted旗標的迴圈才呼叫
`FUN_0001a30b`——這正是`tools/fd2_chapter_sweep.py`既有`confirm_end_turn()`方法論鎖定的
「確認結束回合→YES」路徑。往回追這個分支裡連續呼叫的四個子函式(`FUN_0001956b`/
`FUN_00016559`/`FUN_00019953`/`FUN_000197e5`)，完整反組譯確認：
- `FUN_0001956b(param_1)`：依呼叫端傳入的`param_1`(0x80/0x81/0x82/0x83/0x84/其他)分六路
  設定全域`DAT_00053c67`為六個不同常數(`0x10bb`/`0x6ab`/`0xf63`/`0x576`/`0xe3c`/`0x9017`)——
  這是「哪一種Yes/No確認框」的種類選擇器。**誠實範圍**：`DAT_00053c67`同一個全域在
  doc58續六十九(`0x32000`一帶CG解壓縮路徑)已被證實另作「work buffer目的地偏移」用途，兩處
  是不同執行時期對同一個scratch全域的重用，不是矛盾；本輪未追出`FUN_0001956b`這六個常數
  在Yes/No情境下具體代表畫面座標還是文字資源offset，不擅自命名。
- `FUN_00019953`才是真正的**輸入迴圈**：呼叫`FUN_000370f0()`讀鍵盤掃描碼進`DAT_00053a8e`，
  `'K'(0x4B)`→`DAT_00053c57=0`、`'M'(0x4D)`→`DAT_00053c57=1`——精確對應PC BIOS scan code
  set 1的方向鍵延伸碼(`0x4B`=←、`0x4D`=→)，即**左右鍵切換NO/YES兩個選項的高亮狀態**；
  `-0x20(0xE0)`/`'R'(0x52)`/`'\x1c'(0x1C=Enter make code)`/`'9'(0x39=Space make code)`
  四者任一則跳出迴圈確認——與doc58全系列記錄的「Enter確認YES/NO框」實測行為完全吻合。
  `FUN_00016559`/`FUN_000197e5`是這個對話框開合的过场動畫(`FUN_0004ec31`/`FUN_0004ebff`
  淡入淡出、`FUN_0003771c`逐步繪製邊框)，非輸入邏輯本體。**item 791「YES/NO input」子句
  結論**：K/M(左右)切換、Enter/Space等4種掃描碼確認——這是byte-exact反組譯結果，不是猜測，
  可從doc57原始5個開放子句移除，維持D的僅剩MAP/TURN/ENEMY/FRIEND/NPC五個代稱本身。

**2026-09-06續十三，item 791「TURN」候選欄位取得機制層級的語意佐證(仍非100%確認，但比
「呼叫時機巧合」強得多)**：完整反組譯`FUN_0001a30b`本體(先前只反組譯過片段)，關鍵一行：
`_DAT_00053bef = _DAT_00053bef + 1;`——這個increment**卡在跟D8滑入動畫完全相同的
三層`DAT_00053ecc==0`(尚未分出勝負)閘門後面，且緊接在第二次`0x1f1cc/0x1f30a`(D8滑入)
呼叫之前**，即整個`FUN_0001a30b`(已知的end-of-turn orchestrator)執行一次只會讓這個值
+1一次。`xref_to 0x53bef`(誠實範圍：`-noanalysis`下`xref_to`已知不完整，見`call_scan`
說明，本輪未做`call_scan`交叉驗證)找到的兩個READ位址(`0x1a668`/`0x1a6d9`)恰好落在
續十二確認的`0x187d6`(數字渲染)兩個呼叫點的push序列裡——**兩個呼叫都是拿這個剛incr過的
值當`param_3`(要畫的value)去渲染**，不是兩個獨立數值。這兩個呼叫點分屬decompile裡兩個
獨立迴圈(`for iVar4<9`內`6<iVar4`時呼叫2次、`for iVar4=2..4,9`內無條件呼叫4次，共6次
動態呼叫)，每次呼叫算出的目的位址(`0xa726b`/`[0x53a49]+0x812f+EDI*456`類的算式，換算
落在VGA framebuffer `0xA0000`bank內)彼此不同——**最可能的解讀是同一個(已incr過的)回合數
以動畫式多幀重繪呈現(配合D8面板滑入)，而不是"incr前/incr後各畫一次"**；本輪未逐一算出
6次呼叫各自的精確螢幕座標去證實"是同一個位置重繪還是逐位數/逐幀不同位置"，這仍是誠實
缺口。**結論**：「TURN候選欄位在end-of-turn orchestrator裡恰好被+1一次，且incr後的
值立刻用已確認的digit-render路徑(glyph `#42-51`)重繪」——這是比先前"呼叫時機吻合"更直接
的機制證據，item 791的TURN子句信心等級由此再提升一階，但仍未達到「語意100%confirmed」
(仍差一步：live記憶體watch，在DOSBox-X環境下對`0x53bef`(對應native+0x19C000後的live位址)
下`BPLM`監看，逐回合確認數值真的遞增且螢幕顯示同步——這需要WSL2 DOSBox-X live環境，本輪
純Windows端`ghidra_batch_probe.py`環境不含這個工具鏈，留給下一輪)。維持D。

**2026-09-07——上面「差一步」的live watch已補上，但不是用BPLM(那條路是死路，見doc48§7的
既有量化結論：任何BPLM存在就讓RUN退化成近似單步，命中時CS:EIP還卡在real-mode callback讀
不到暫存器)，改用輪詢式`mem dump`跑完一整輪真正取得數值變化**：`FD2_ch27_test.SAV`進入
真實戰鬥，確認`[0x1EFBEF]`基準值`1`，END回合確認YES(此時再次dump仍是`1`)後畫面立即疊出
「ENEMY PHASE」banner，推進過完整的敵方AI行動段落，控制權還給玩家後重新dump得到`2`——
遞增恰好一次，且3秒後複查仍是`2`(排除自由跑動計數器)、同時`[0x1EFECC]`(勝負旗標)為`0`
(排除靠假造勝利觸發)。item 791「TURN」候選欄位**正式達到語意100%confirmed**：這個回合
orchestrator裡的`+1`不只是「時機/index運算byte-exact」，是真正在一次完整玩家+AI回合週期
裡被觀察到遞增一次的回合計數器。完整過程見`91-worklist.md` 791項「2026-09-07再續十七」。

**2026-09-06續十四，item 791 ENEMY/FRIEND banner的resource-ID選擇點搜尋——排除法縮小範圍，
未找到選擇點本身，誠實記錄negative result**：完整反組譯`0x1f1cc`/`0x1f30a`(D8滑入動畫)本體
確認**兩者完全沒有任何依side/phase的條件分支**——16格迴圈裡逐格呼叫`FUN_00015f0e()`(兩次)+
`FUN_0003776e()`(兩次)+`FUN_00011d40()`，全部是無條件執行，跟前一輪(續八)「只有sprite/RLE
blit,沒有文字渲染呼叫」的結論一致，也確認**這裡不是banner的內容選擇點**。往下一層追
`FUN_00015f0e`本體：呼叫的三個子函式`FUN_0004ecbf`/`FUN_0004ebab`/`FUN_00015983`全部是
**無參數或內部走固定全域**(`FUN_00015983`甚至是空函式，本體只有`return`，本輪確認的一個
額外小發現，尚不知道是這個版本裁掉的debug/cheat hook殘留還是編譯器內聯後留下的空殼)；
`FUN_0004ebab`是`FUN_0004ec66`(doc35§9.9.3已確認的RLE getbyte原語)的高階包裝，屬於通用
解壓縮管線，不含side邏輯。**結論(排除法)**：ENEMY/FRIEND banner的resource-ID選擇**不在
D8滑入動畫本體、也不在其呼叫的blit/解壓縮原語內部**，必然是**呼叫`0x1f1cc`/`0x1f30a`之前
就已經寫進某個全域**(`FUN_00015f0e`才會無參數地讀到)。`FUN_0001a30b`本體裡`(&DAT_00051e63)
[DAT_00053c03] != (&DAT_00051e81)[DAT_00053c03]`觸發的`FUN_00025977()`(已知的cache-aware
resource loader，見續十三前的討論)是本輪僅存、跟"side索引`DAT_00053c03`"掛勾的候選機制，
但**本輪未證實`FUN_00025977`載入的資源就是`FUN_00015f0e`後續讀到的同一份**，這條連結仍是
假說而非結論。下一輪具體建議：`decompile FUN_000111ba`(資源載入器)+核對它寫入的目的全域
是否正好是`0x4ecbf`/`0x4ebab`讀取的來源，或改用`xref_to DAT_00053c03`直接列出所有讀寫點
找出這個側標記(side flag)實際在哪裡被翻轉(目前只看到被讀，從未看到被寫的位置)。維持D。

**誠實訂正(2026-09-06續十五)——`DAT_00053c03`不是side/phase flag，是劇本(story script)
逐筆記錄的opcode欄位,續十四的假說作廢**：`xref_to DAT_00053c03`列出的寫入點裡，`0x25ed6`/
`0x26067`兩筆都落在同一個函式`FUN_00025ebb`(`0x25ebb-0x26151`)。完整反組譯後發現這是一個
**劇本/過場腳本播放器**：以`DAT_00053c57*0xa28+iVar1+0x312b`(每筆記錄2600 bytes，`DAT_00053c57`
在這裡的用法是「目前劇本筆數索引」，跟同名全域在指令環context下的"選單狀態選擇器"用法完全
是同一個scratch全域在不同執行時期的重用，不是矛盾)算出目前記錄位址，逐欄位讀出
`DAT_00053c03=record[+0xa00]`、`DAT_00053bfb=record[+0xa01]`、`DAT_00053bf3=record[+0xa02]`
(4 bytes)、`DAT_00051aab=record[+0xa06]`、`DAT_00053af9=record[+0xa07]`、`DAT_00051e61=
record[+0xa08]`、`DAT_00051e62=record[+0xa09]`，再用`(&PTR_FUN_00051d71)[DAT_00053c03]()`
跳到對應的**劇本指令handler**（很像`FUN_0002ff01`那條native command dispatch的姊妹結構，
只是這裡是劇本/過場opcode，不是戰鬥指令opcode）。**這代表`FUN_0001a30b`裡讀到的
`DAT_00053c03`只是「上一次執行過的劇本opcode」這個共用暫存器的殘值**，`(&DAT_00051e63)
[DAT_00053c03] != (&DAT_00051e81)[DAT_00053c03]`這個比較很可能是「這個opcode對應的某個
屬性(疑似palette/資源id)本輪跟上輪不同才需要`FUN_00025977()`重載」，**跟combat的
ENEMY/PLAYER側別完全無關**——續十四提出的「`DAT_00053c03`=side flag，`FUN_00025977`=
banner resource loader」假說到此正式排除，不是縮小範圍而是整條線索作廢。**ENEMY/FRIEND
banner的真正resource-ID選擇點，本輪排除了D8滑入動畫本體(續十四)跟這條side-flag假說
(本節)兩個方向，仍未找到，回到完全開放狀態**，下一輪需要換全新切入點(可能得從live
DOSBox-X對banner出現當下的screenshot時間點做記憶體diff，而不是繼續猜靜態候選)。維持D。

**2026-09-07——找到了，不是全域寫入，是call-site literal參數**：續十四找錯了地方(在
`0x1f1cc`/`0x1f30a`本體內找side分支)，真正的選擇點在**呼叫端**`FUN_0001a30b`。完整反組譯
該函式裡兩次D8觸發點，發現兩處push進`0x1f1cc`/`0x1f30a`的常數不同——緊接在`0x1d80b`(item
304已確認的敵軍掃描)之後push`0x52`，緊接在`0x1d8ba`(item 304已確認的友軍掃描，且緊接在
`inc [0x53bef]`即TURN counter遞增**之前**)之後push`0x50`。追蹤這個常數：`0x1f1cc`原封
不動轉呼叫`FUN_0001f42d(param_1,offset)`(迴圈5次)，`FUN_0001f42d`內部算出`ebx=0x55-
param_1`(0x52→3，0x50→5)，這個差值成為`0x15f0e`(item 1117已確認的LMI1容器resource-fetch
原語，讀取共用全域`[0x53a81]`=D8面板本身resource #5)的其中一個引數——**ENEMY/PLAYER
banner共用同一個LMI1容器，靠這個call-site常數選容器內不同sub-entry**，跟item 1117的
「同容器、靠index選子項」結構完全同構。本輪(見791項再續十七)自己live觀察到「結束回合YES
後立即出現ENEMY PHASE banner」，時序精確對應`0x52`那個分支，是同一輪session內的直接
交叉確認，不是巧合。**誠實範圍**：`0x55-param_1`算出的3/5在`0x15f0e`六個引數裡對應哪一個
維度(row/col/index)、`FUN_0001f42d`內第二個`0x15f0e`呼叫是否也讀param_1，這兩點的ESP
偏移追蹤本輪未完全展開，留給下一輪用`capstone_probe`複查或live dump驗證。完整過程見
`91-worklist.md` 791項「2026-09-07再續十八」。

### UI-04 geometry slice（2026-07-25，E0 partial）

`0x14818` 先以固定的 table record 0（`0x61646`，20 bytes）呼叫 `0x4e040`，並將原始
`(x,y,mode)` 傳入，建立／更新 target grid；`0x4e040` 以 mode 作 seed grid byte，內層再依
tile flag 與 record byte table 的 cost gate 擴張。此 raw mode 的玩法名稱尚未確定。其後才有可獨立
證實的一層幾何：以 source cell `(cx,cy)` 掃全格、
對每一格算 `abs(x-cx)+abs(y-cy)`，只有嚴格小於 caller radius 的格寫入 `0xff` marker。
最後掃 0x50-byte unit buffer：死亡／inactive unit 跳過、非 marker cell 跳過，再依 caller selector
對 `unit+6` camp 過濾，將 slot index 寫入可選 target output。當另一個 mode argument 大於等於
`0x10` 時另走一條十字形 clear path；它的玩法語意與 weapon `min/max` 欄位尚未完成 caller-dataflow
對照，不能把這個 raw `radius` 直接等同 remake `AtkMax` 或宣稱已解 LOS。

補作 `0x1cff0` caller 的 stack-dataflow 後，`0x14818` 的參數順序已可固定為
`(x, y, output, mode, radius, campSelector)`：`mode` 是第 4 參數、上述嚴格曼哈頓比較使用
第 5 參數，unit filter 使用第 6 參數。特別 command `0x17` 傳入 `record+3` 作 mode、`1`
作 radius、`record+6` 作 selector；一般 command 則傳 `record+4` 作 mode、`0` 作 radius、
`record+6` 作 selector。因此一般 path 不會在這一 call 新畫 diamond，而是消費前序已建立的
marker grid。`record+3/+4` 仍不能在未追到 producer 前命名為 weapon min/max。

該 record 的 producer 已定位：`0x1cff0` 將選單結果 ID 傳給 `0x4e516`，而
`0x4e516(id) = 0x619fd + 7*id`。因此 `+3/+4/+6` 是靜態 7-byte command ABI 的欄位，
不是這個 handler 自行組出的暫存結構；在有 field-name 或實機資料對照前，仍以 raw offset
記錄，不擅自命名成攻擊／法術的 min/max range。

command ID 並非 four-way ring 的固定索引：`0x1c269(unitIndex, out)` 讀取該 0x50-byte unit
record 的 `+0x1a..+0x1e` 五個 byte，逐 bit 把 set bit 寫出成 `byteIndex*8 + bitIndex`（0..39）。
`0x1cff0` 以這份 list 的目前選項取得 ID、再呼叫 `0x4e516`。因此 UI-03 的完整 SDD 必須資料化
command bitmask、ID→label/rendering、enable gate 與 cancel hierarchy；現行四格 `ringInput` 只能保留
為 provisional interaction，不能冒充原版完整 command menu。

bitmask 的 construction ABI 也已定位：`0x10f7f` 將 source record `+0x0d..+0x10` 的 4 bytes
copy 到 unit `+0x1a..+0x1d`，並清 unit `+0x1e`；另一 construction path `0x11399` 同樣 copy
4 bytes（其 source `+8..+0xb`）再清 `+0x1e`。後續 `0x1d7fb` 以 `commandID/8` 選 byte、OR
對應 bit 寫回 `unit+0x1a` 起的 array。因此 40-bit 是真實 runtime ABI，但初始 source 只有 32 bits，
第 5 byte 由後續流程擴充；source record 的遊戲語意仍不可未證實地命名。

原版另有已證實的可用性 gate：`0x159fa` 先取得同一份 `0x1c269` list，逐個取 command record
`+5`，僅當該 byte `<= word[unit+0x44]` 時保留；`+0x44` 已由 battle HUD 證實為 current MP。
因此 `command+5` 是 MP cost/requirement 的 E0 ABI，而不是 UI 的任意排序值。bitmask 的寫入
producer、每個 ID 的名稱與其他 enable gate 尚未閉合。

`0x1d51d` 是這份 command list 的 input loop（不是 `0x19953`）：每次先 call `0x1ceed` render，
再取 `0x1c269` count。scancode `0x48/0x50` 對線性 cursor 做 -1/+1 並在 `[0,count-1]` wrap；
`0x4b/0x4d` 分別在 index >=4 時 -4、在 index+4<count 時 +4；renderer 座標證實每欄四列（不是四欄）。
`0x1c/0x39`（Enter/Space）重新查 `command+5`，只有 current MP 足夠回傳 confirm；`0x01`（Esc）回傳
cancel。`0x1ceed` 的 list index `i` 使用 `x=0x12+0x64*floor(i/4)`、`y=0x67+0x16*(i%4)`，以
`0x15f84([0x53a7d], 0x1b9+commandID, ...)` 顯示 label，並以 `0x187d6` 顯示 command `+5`。這鎖定
label index ABI 與 geometry。常駐 `[0x53a7d]` table 已由其他 callsite 的 direct trace 對齊為
FDTXT_000；raw strings `0x1b9..0x1e0` 已匯出為 `docs/data/command_labels.json`。其中空字串與
系統訊息 slot 證實文字不等於可達指令；cursor cell／不可用 command 的可見表現仍待 resource／實機畫面，
不得猜作四方向 ring。

補充 record evidence：`0x4e516` 的 `0x619fd+7*id` 對 IDs 0..35 byte-for-byte 等同 EXE spell table，
所以 command record 的 `+3/+4/+5/+6` 可分別沿用 spell row `dist/range/mp/target` 的已證實欄位；資料掃描中
FDFIELD/character default initial masks 只出現 IDs 0..30。36..39 的鄰接 bytes 與 FDTXT 系統訊息不能被當成
可選技能。

動態 command producer 亦已定案：level-up routine `0x1e292` 讀 portrait growth row 的 `learn_idx`，以
`0x4e4a2` 取固定 12-byte learning row，掃最多六組 `(level, commandID)`，level 命中便呼叫
`0x1d79c(commandID, runtimeSlot)` OR bit 並顯示 FDTXT_000 #587。20 rows 已原樣導出；這不是一般
selector effect trace，故不代表所有已學 command 已有可執行 remake effect。

`0x4e040` 並非僅由這個 target caller 使用：`0x14344` 先以 unit `+0x20`（fallback record
`0x13`）透過 `0x4e555` 取另一個 20-byte record，再把 map grid、terrain table 一併傳入。
其內層 `0x4e16e` 讀 tile flag 與該 record 的 byte table 後決定是否擴張。故目前可用的
E0 模型是 **seed mode + table + terrain/cost gate + marker + unit filter**；尚不可把 target highlight
reducer 成單一菱形或宣稱其完整路徑／LOS 規則。

### UI-04 不可用目標灰化——窮盡 `0x14818` caller xref，結論「原版沒有灰化」（2026-08-20）

> **背景**：UI-04 row 長期標記「AOE/LOS/不可用目標灰化」完全沒有證據鏈，是矩陣裡少數
> 從未被真正調查過的項目。同一天稍早 doc27 §6.4 已完整追出 AoE 目標陣列上游生成器
> `0x14818`（依 spell/item record `[+3]`/`[+4]` 分流成 flood-fill 圓形／十字直線兩條路，
> 收集陣營篩選後的 unit-index 陣列），doc11 本輪段落亦窮盡反組譯其 480-byte 本體確認無
> 額外 LOS 判定。本節任務：對 `0x14818` 做**全域 call-xref 掃描**（不只看已知的
> `0x2ff01` 攻擊執行路徑），找出是否有另一個 caller 是在**選單顯示/游標移動階段**呼叫
> （而非實際出手階段），並反組譯它如何把候選結果轉成 UI 呈現。
>
> **方法**：純靜態、唯讀 Ghidra headless（`analyzeHeadless -readOnly -noanalysis`，
> `FD2Analysis3` 專案）。腳本：`ProbeUI04Xrefs0820.java`（call-xref 掃描）、
> `ProbeUI04CursorLoop0820.java`（`0x115b6`/`0x14742` 本體逐指令反組譯）、
> `ProbeUI04Tail0820.java`（`0x14742` 收尾、`0x12d7b`、`0x11b48` 逐指令反組譯），皆存於
> `FD2_ghidra_projects/`；合併輸出見
> [`fd2_14818_callers_and_115b6_disasm_2026-08-20.txt`](../data/fd2_14818_callers_and_115b6_disasm_2026-08-20.txt)。

#### 1. 全域 call-xref：`0x14818` 共 8 個 caller 函式、17 個呼叫點

逐一核對每個 caller 函式的角色：

| caller 函式 | 呼叫點 | 角色 |
|---|---|---|
| `FUN_00018d8c`(`0x18d8c`) | `0x18e25`、`0x18f6a` | 玩家 UI——「指令環攻擊」action-ring dispatcher（doc10/doc13 已證）|
| `FUN_0001bbdc`(`0x1bbdc`) | `0x1bc3c`/`0x1bd43`/`0x1bd93`/`0x1becf` | 玩家 UI——item two-stage target（RE-ITEM-TWO-STAGE-TARGET-1BBDC 已證）|
| `FUN_0001cff0`(`0x1cff0`) | `0x1d1c9`/`0x1d211`/`0x1d2bf`/`0x1d32a`/`0x1d38e` | 玩家 UI——一般 command（法術/道具）dispatcher（doc27 §6.4 已證）|
| `FUN_00014237`(`0x14237`) | `0x14448` | 敵方 AI——物理落點候選枚舉（doc11 已證，`unit[+0x34]&0xf` 狀態機閘門）|
| `FUN_00015055`(`0x15055`) | `0x15114` | 敵方 AI——法術執行演出流程（doc11/doc27 §6.4 已證，非玩家路徑）|
| `FUN_00015311`(`0x15311`) | `0x15381` | 敵方 AI——執行結果分派（doc11/doc36 已證，`0x2ff01` 的另一個 caller，但走 AI 閘門）|
| `FUN_0001567e`(`0x1567e`) | `0x1575a`/`0x157d4` | 敵方 AI——道具 command 預選（doc11 已證）|
| `FUN_0001598a`(`0x1598a`) | `0x15aaa` | 敵方 AI——command mask 預選（doc11 已證）|

即：**只有 3 個 caller 函式是玩家可見 UI 路徑**（`0x18d8c`／`0x1bbdc`／`0x1cff0`），其餘 5
個全部是 doc11 已定案、由 `0x13a9f` 依 `unit[+0x34]&0xf` 狀態機呼叫的敵方 AI 決策鏈，
沒有玩家可見的選單/游標渲染。窮盡這 17 個呼叫點後，**沒有找到任何額外的「選單顯示/
游標移動階段專屬」caller**——3 個玩家 UI caller 全部都是「先呼叫 `0x14818` 取得候選陣列、
緊接著呼叫 `0x115b6` 做互動確認」的同一種模式（見下）。

#### 2. `0x115b6`：玩家路徑唯一共用的游標/確認迴圈

對 `0x115b6` 做同樣的 call-xref 掃描，得 9 個呼叫點，全部落在上述 3 個玩家 UI caller
函式內（外加 `FUN_00018890`@`0x18981`，是 `0x18d8c` 的外層 wrapper，直接呼叫 `0x115b6`
而不自己呼叫 `0x14818`）——**`0x115b6` 是攻擊環/道具/法術三條玩家路徑共用的唯一互動
游標/確認迴圈**，是回答「合法目標怎麼呈現給玩家」的正確位置。

逐指令反組譯 `0x115b6..0x117e6`（335 bytes）結構如下：

- **入口**：`EDI`=targetCode（`0`-`6`，即 record `+6`）、`EBP`=候選陣列元素數、
  `[ESP+0x30]`=候選 unit-index 陣列指標（皆為 `0x14818` 的直接輸出）；`radius=[0x51a83]`
  （`>1` 才 `-1`）。
- **候選陣列 cycling（非移動鍵，`0x2c`/`0x4c`）**：`ESI` 是陣列索引，wrap-around 遞增，
  每次切到新候選 `EBX`（unit index）就呼叫 `0x12d7b(EBX)`——反組譯後確認這是讀該 unit
  record `+0/+1`（X/Y 座標）再呼叫 `0x12cea(x,y)`，即「把游標**吸附**到這個候選的格子
  上」，不是繪製灰階/高亮色塊的 renderer。
- **自由方向鍵移動（`0x48`/`0x50`/`0x4b`/`0x4d`）**：分別呼叫 `0x11b48`/`0x11b9b`/
  `0x11c59`/`0x11bfa`。逐指令反組譯 `0x11b48`（上）確認：它只對 `[0x53ab5]`(游標Y)/
  `[0x53abd]`/`[0x53aad]`(捲動門檻/camera) 做遞增遞減與邊界檢查，再呼叫 `0x11cac(0)`
  更新畫面；**完全沒有讀取候選陣列、沒有呼叫 `0x14818` 或 `0x14742`，也沒有任何合法性
  判斷**——玩家可以把游標自由移到地圖上任何一格，不受候選清單限制。
- **確認鍵（scancode `0x39` 空白鍵／`0x1c` Enter）**：`targetCode==5` 一律直接拒絕；
  `==6`（搬移/relocation）走獨立的地形合法性分支（`0x1637`-`0x1719`，已由
  RE-RELOCATION-MODE6-LEGALITY 記錄關閉，屬另一條路徑）；其餘先讀游標所在格在
  `0x14818` 已標記的地圖緩衝區 byte（`[0x53a51]+cellIdx*4+7`），`==0xff` 一律拒絕；
  `==4` 通過後直接接受；否則（`0`/`1`/`2`/`3`）呼叫**全域僅一個呼叫點**（`0x1175f`）的
  `0x14742(cursorX, cursorY, radius, 0, targetCode)`，其回傳值（非零才接受）決定確認
  是否成立。

#### 3. `0x14742`：合法性判定的完整本體，以及拒絕分支的視覺表現

逐指令反組譯 `0x14742..0x14817`（214 bytes，全域唯一呼叫點 `0x1175f`）：對全部
`[0x53beb]` 個 unit 逐一計算與游標的曼哈頓距離（兩次 `0x37932` 純 `abs()` 相加），
死亡/inactive（`unit[+5]&1`）或距離 `>=radius` 者跳過；依 `targetCode` 做陣營篩選
（`0`→`unit+6==0` 接受、`1`→`!=0` 接受、`2`→`==1` 接受、`3`→`==2` 接受，與
`0x14818`/`0x14742` 既有的 camp-selector 慣例完全一致）；命中則計數器 `EDI` 遞增（若
呼叫端有給非空輸出指標，同時把該 unit index 寫入輸出陣列），迴圈結束回傳 `EDI`——
即回傳「游標半徑內符合陣營篩選的候選數」，非零才算合法，與既有文件「count 非零才
確認」的結論完全吻合，本輪以獨立反組譯重新核實。

**確認被拒絕時，`0x115b6` 唯一的處理是 `JMP`/`JZ` 回到 `0x117a9`（`CALL 0x12dac` 讀下
一個輸入事件）——這跟按任何其他非動作鍵時走的路徑完全相同，沒有專屬分支、沒有呼叫
任何額外的繪製/調色盤/音效函式。** 也就是說，游標移到不合法目標既不會變色也不會有
任何特殊呈現；玩家按下確認鍵時若目標不合法，畫面上什麼都不會發生，只是迴圈繼續等待
下一個輸入。

#### 結論

窮盡 `0x14818` 的全部 17 個呼叫點後，**沒有第二個「選單顯示/游標移動階段專屬」的
caller**——玩家可見的 3 條路徑（攻擊環/道具/法術）全部共用同一個 `0x115b6` 互動迴圈，
而這個迴圈本身已被完整反組譯：合法性判定被壓縮成「按下確認鍵那一刻的單一次
`0x14742` 呼叫」，游標移動階段完全自由、不受候選清單或合法性約束，也沒有任何條件式
渲染呼叫可以充當「灰化」。**這代表原版根本沒有「不可用目標灰化」這個 UI 元素**——
選目標合法性是在確認出手那一刻才判定，玩家可以自由把游標移到任何格子，選到非法
目標時只會被靜默拒絕（無反應），不是先預先把不可選格畫成灰色。`0x14818` 產生的候選
陣列，唯一的 UI 用途是讓「切換候選」熱鍵（`0x2c`/`0x4c`）把游標吸附到下一個合法目標，
而不是限制或渲染游標可達範圍。

**UI-04「不可用目標灰化」完成度**：**已關閉**，結論明確且窮盡（並非找不到證據而交
白卷）——原版沒有灰化機制，legality gate 只在確認時判定一次。連帶地，AOE（doc27
§6.4）與 LOS（doc11 本輪段落，`0x14818` 本體無額外視線判定）兩項也已在同一天閉合，
UI-04 row 剩餘的開放項目縮小為「native argument↔weapon min/max mapping」、
「indexed item/effect presentation」與「global selector6 的 production owner」，與
`0x14818`/`0x115b6`/`0x14742` 這條合法性判定鏈無關。

**誠實訂正(2026-09-06)——「global selector6 的 production owner仍待」是stale標記，
doc56/doc37早已解開，本節從未交叉引用**：`docs/knowledge-base/56-fd2-remake-sdd.md`
「Native overlay/selection-selector contract」段落(2026-07-28)與`37-spell-effect-figani.md`
§2(同日)都已明確記載：`[0x51a83]`(selector全域)由**4個具名writer**——`0x15140`／
`0x153b1`／`0x1bd14`／`0x1d188`——各自把command/item record的一個byte(spell table的
`range`欄位)zero-extend後`+2`寫入。**value6specifically**：不是`0x122dc`的畫圖表項目
(該表只處理1-5)，而是觸發清除FDFIELD selected-cell byte+3的分支；當某個command/item
record的range欄位恰好等於4時，`+2`公式就會產生selector=6。這正是本行提問的「production
owner」——不是未解，是2026-07-28就已經用official IDA data xref(`docs/data/ida/
fd2_51a83_xrefs.txt`)閉合，只是doc57這一行(2026-08-20新寫)從未回頭核對doc56/doc37，
才誤以為還開放。比照本專案「145/1038文件已結論關閉、D標籤未同步」的既有處理模式訂正：
UI-04 row與worklist 1117的「global selector6的production owner」子項應改標**已關閉**，
真正剩下的只有「native argument↔weapon min/max mapping」(已由本文件2026-09-06系列
commit收斂為distance+mode語意確認)與「indexed item/effect presentation」(已收斂為
純presentation層級的道具名稱/icon/SFX缺口，見doc32/worklist對應段落)。

**2026-09-06續，「native argument↔weapon min/max mapping」進一步收斂——重新對
`0x14742`本體做獨立decompile(`ghidra_batch_probe.py`，非重複使用舊結果)，確認一個
具體的負面結論**：本體只有一個距離比較`iVar2 + iVar1 < param_3`（曼哈頓距離嚴格小於
`param_3`=`radius`=`[0x51a83]`=selector6同一個global，即command/item record的
`range`欄位`+2`）——**全函式沒有任何下界/最小距離比較**，`param_5`(=targetCode，即
0/1/2/3的陣營篩選，與續十二節同一套慣例)只影響`unit+6`的陣營比對，不影響距離判定。
往上一層的`0x14818`候選陣列生成器（§UI-04 geometry slice，本文件既有段落）同樣只有
「嚴格小於radius才寫入0xff marker」的單向比較，沒有第二個下界比較。**結論**：目前已
窮盡的兩條native geometry路徑（候選陣列生成`0x14818`＋確認時合法性判定`0x14742`）
都只實作單一「距離嚴格小於某個radius」的上界檢查，**沒有找到任何min-range(最小攻擊
距離)的原生機制**——native端目前的證據顯示「min/max」這個框架本身可能問錯了問題：
真正存在的只是一個由`range`欄位換算出的單一半徑值，加上一個mode/陣營選擇欄位
（record`+3`/`+5`／`targetCode`），不是兩個獨立的min/max欄位。**誠實範圍**：這只
排除了「min存在於這兩個已窮盡函式內部」的可能，不能排除min-range邏輯藏在完全
不同、目前未被這條call chain連到的地方（例如某些近戰/遠程武器類型專屬的另一個
legality path，或是某個從未被列入`0x14818`/`0x14742` call-xref的獨立分支）——未做
`0x14818`/`0x14742`的`xref_from`全域反查，此路仍留待下一輪如果要繼續深挖。維持D，
但「native argument↔weapon min/max mapping」現在有一個可驗證的具體候選答案（單一
radius+mode，非min/max對），不再是完全空白的問句。
