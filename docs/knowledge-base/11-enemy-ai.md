# 11 — 戰鬥人工智慧專題：敵方與 NPC 的行動決策

> **版本基準：**本文件所有位址只適用於大小 `357074` 位元組、MD5
> `b97caf2239a27a896069d03549d96e1e`、SHA-256
> `222b7d067ad4450eb9c5f6e6bce1797d54bb050417ba39ced6067f8039f28c4f`
> 的 `FD2.EXE`。完整原版資產指紋見
> [`fd2-reference-files.json`](../data/fd2-reference-files.json)。
>
> **2026-07-27 標準執行檔重核（Docker Capstone）：**重新做直接掃描，
> `calls 0x15140` 與
> `calls 0x15356` 均沒有結果；`0x15140` 實際是 `0x15055` 函式中段把
> record byte `+0x12` 加 2 寫入 `[0x51a83]` 的 raw selector writer，不能以本檔舊摘要
> 直接當作 AI 主函式或傷害公式。後續重核已在 `0x14237` 找到真正的物理候選
> 評分迴圈，另保留 `0x15ad8 → 0x15b77` 法術評分邊界；兩者不可混成同一函式。
> 舊 `0x15140`、`0x1527b`、`0x1529e`、`0x152ab`、`0x15356` 位址仍作廢，
> 不得作為重製等價證據或接入正式執行路徑。

## 本專題要回答的問題

1. 一個非玩家回合以什麼條件挑出下一個行動單位？
2. 單位如何產生可用命令、移動落點與候選目標？
3. 候選方案如何評分、如何處理同分？
4. 選定後如何依序執行移動、攻擊、施法、待機？
5. 沒有合法攻擊目標時，原版如何決定接近、原地待機或其他行為？

目前只閉合部分原始呼叫拓撲與評分分支，尚未還原完整決策規則。重製端的
`NextAIPlan`／`aiActUnit` 是正規化近似，不得反過來當成原版證據。

## 玩家看見的敵方回合，程式目前可拆成什麼

| 階段 | 原版直接證據 | 目前結論 |
|---|---|---|
| 進入非玩家階段 | `0x1A4EB`／`0x1A58F` 兩條階段專用呼叫點 | constructor 與 target-code 消費端已固定 raw `+6` 陣營碼：友1先單遍，敵0再做預選＋第二遍；己2不在這兩個 AI 掃描內 |
| 挑下一個單位 | `0x1D80B`／`0x1D8BA`／`0x1D988` 依執行期陣列順序掃描 | 除陣營碼外仍檢查 `+5 & 0x81`、`+0x26`；後兩欄只保留 raw gate |
| 取得可用行動 | `0x13A9F→0x14EF0`，另含 `0x1598A`／`0x1567E` | 已證明依記錄命令與可用命令產生候選；不是單一「AI 主函式」 |
| 枚舉物理落點 | `0x145CD→0x4E040→0x146D1→0x14B16` | 已閉合阻擋標記、原版移動成本、佔用格排除及 Y 優先／X 次之的固定順序 |
| 每格枚舉目標 | `0x14237→0x14818` | 依該呼叫者專用幾何建立目標；不可把物品原始位元組通稱為武器射程 |
| 物理評分 | `0x14237..0x145CC` | 先比較優先級、再比較分數；完全同分保留先枚舉的落點與目標 |
| 法術評分 | `0x15AD8→0x15B77` | 已閉合數個原始分支；尚未完整接入重製執行期 |
| 執行選中結果 | `0x1548E` 等執行鏈 | 消費已選落點／目標並播放移動與戰鬥；不是尋路器 |

2026-07-29 再以 Docker Capstone 展開三個掃描入口後，可把上表第一、二列
收緊如下；完整指令保存於
[`phase setup`](../data/fd2_ai_phase_setup_disasm.txt)、
[`unit scans`](../data/fd2_ai_unit_scan_disasm.txt) 與
[`mode dispatch`](../data/fd2_ai_mode_dispatch_disasm.txt)，每份都內含來源
大小、MD5 與 SHA-256：

1. `0x1A4E6` 依序呼叫 `0x1A7BD→0x1D80B→0x1A7F1`。
   `0x1D80B` 只讓 `record+6==1`、`(+5 & 0x81)==0`、`+0x26==0`
   的記錄進 `0x13A9F(unit,1)`。
2. 中間完成 `0x13536`、`0x1A813(0)`、`0x1A866(0)` 等收束後，
   `0x1A58A` 依序呼叫 `0x1A7BD→0x1D8BA→0x1A7F1`；掃描返回後
   `0x1A5B9` 才增加 `[0x53BEF]`。所以這個計數寫入不是第一掃描的
   前置 gate，也不能單靠鄰近位址命名為任一陣營的回合開始。
3. `0x1D8BA` 對 `record+6==0` 的合格記錄做兩次逐列掃描。第一遍先呼叫
   `0x1598A(unit,0)` 與 `0x1567E(unit,0)`；只有 signed
   `[0x53C23]>=6` 或 `[0x53C33]>=6` 才再呼叫 `0x13A9F(unit,0)`。
   第二遍 `0x1D988` 對相同三個 raw gate 的記錄直接呼叫
   `0x13A9F(unit,0)`。因此 `0x1D8BA` 不能降成單一「每個敵人行動一次」
   迴圈。
4. 三個逐單位路徑都在 mode dispatcher 後，先以 `[0x51A8F]`（非
   `0xFF` 時）索引 90 筆全域事件表 `0x51B91`，再重新讀取章節索引
   `[0x53C03]`，無條件呼叫 30 筆章節戰場事件處理器表 `0x51B19`；
   兩張表之後才檢查 raw pending 碼 `[0x53ECC]`，非零就離開掃描。
   合法 IDA Pro 9.4 已證實兩張表的原始邊界及指標；其直接資料交叉參照中，
   `0x13A44` 是 `[0x51A8F]` 唯一非重設寫入端。這些表不是未知位址，
   但各 handler 的高階效果仍須逐筆閉合；raw pending 碼 1／2 也不可在
   本層直接改名成「中場／勝利」。
5. `0x13A9F` 的所有模式最後合流至 `0x13E77`：
   `0x13A44(record.x,record.y,1)→0x13512(unit)→0x134E4→0x11CAC(0)`，
   然後返回上述掃描迴圈。這直接固定 selector1、bit7 與重畫的先後，
   但不替 mode 命名；`record+6` 已由獨立 writer／consumer 證據固定為
   原始陣營碼，不再列為未知。

因此目前對「電腦如何選攻擊目標」最精確的回答是：原版不是只找最近角色。
物理路徑會按固定落點順序，對每個落點列出合法目標，套地形後計算攻防差，
拒絕分數 `<=2` 的候選；能嚴格超過目標原始欄位 `+0x40` 的候選提高優先級並將
分數加倍，另受 `0x1DEBE` 與目標原始欄位 `+8` 修正。先比較優先級，再比較
分數；兩者完全相同時保留較早出現的候選。模式0沒有可用 action 時的
`0x14121→0x13E9C` blocked-cell／最近相反分組座標備援已閉合，不能再寫成
完全未知；真正尚不能回答的是敵軍為何需要預選與第二遍、兩個預選分數
各自的完整玩法名稱，以及每種 mode 對玩家可見的完整玩法名稱。

重製端 `fdother.PlanNativePhaseUnitScans` 以完整 `0x50` records 與
呼叫端提供的 signed `[0x53C23]/[0x53C33]` 分數，分別輸出
selector1 單遍、selector0 預選與 selector0 第二遍。它保留原始逐列順序、
三個 raw admission gates 與「任一分數至少6」條件；三個 pass 不會被攤平成
一列，因為每筆後方的全域事件／章節 handler 可能寫 pending 碼而提早退出。
缺少逐單位 score provenance 時整體失敗即關閉。這是 E0 phase contract，
尚未授權正規化 `NextAIPlan` 冒充原版兩遍執行期。

2026-07-29 的 IDA 優先複核再補上
`fdother.ExecuteNativePhaseUnitScans`：它不是拿上述靜態 plan 直接執行，
而是三遍都重新讀 raw record。這是必要條件，因為第一個 selector0 優先遍
成功後會由 `0x13512` 設 `record+5 bit7`，第二遍必須重新 gate 才能排除
已行動者。兩張表的尾段對每一筆 record 都會執行，即使該筆未通過 action
gate；全域事件 handler 可能先設 pending，但章節 handler 仍會執行，之後
才檢查是否退出。索引超出 90／30 筆或缺任一回呼時一律失敗即關閉。直接
證據與表格指標見
[`fd2_ai_phase_callback_tables_ida.txt`](../data/fd2_ai_phase_callback_tables_ida.txt)。

兩個門檻現在可以按 producer 範圍命名，但不能擴張成特定技能：
`0x1598A` 產生法術候選並把最佳分數寫到 `[0x53C23]`；
`0x1567E` 枚舉物品內的 command 候選並把最佳分數寫到 `[0x53C33]`。
第一遍只讓任一分數至少6的敵軍進 `0x13A9F`，其共用收尾
`0x13512` 會設 `record+5 bit7`；第二遍 admission 使用
`(+5 & 0x81)==0`，所以已在優先遍行動者不會再次行動。原版的兩遍因此
是「高價值法術／物品命令優先遍，再處理其餘敵軍」，不是同一敵軍雙動。
分數低於6仍可能在第二遍由完整 mode dispatcher 選擇行動。

## 單位行動模式的資料來源與分支（2026-07-29）

原版建立 `0x50` 位元組戰場單位記錄時，`0x10FB6` 把 FDFIELD 名冊列
`b17` 複製到執行期 `record+0x34`，`b18/b19` 分別複製到
`record+0x35/+0x36`。因此 `0x13A9F` 讀取的低四位模式不是臨時猜值，
而是每張地圖可編輯的初始資料；高四位另有評分與事件用途，不能把整個
`+0x34` 通稱為單一「人工智慧模式」。

重新解析同一份指紋已固定的 FDFIELD.DAT，共 33 張地圖、1887 筆名冊：

| `b17 & 0x0F` | 筆數 | `b17 & 0x0F` | 筆數 |
|---:|---:|---:|---:|
| 0 | 1063 | 1 | 34 |
| 2 | 535 | 3 | 78 |
| 4 | 34 | 5 | 41 |
| 7 | 4 | 8 | 90 |
| 9 | 2 | 10 | 6 |

初始資料沒有模式 6 或 11；完整逐圖與完整位元組分布保存於
[`fdfield_native_ai_modes.json`](../data/fdfield_native_ai_modes.json)。
執行期仍可改寫：`0x3419C` 會對指定的連續單位索引範圍保留高四位、
只替換低四位；`0x13D20` 會把整個位元組寫成 7；章節處理器另有
`0x34A2F/0x34A9C/0x34AE6/0x34C59/0x34C67/0x34CC7` 等直接寫入。

目前只能以「可觀察動作」描述 `0x13A9F` 的分支，不替模式取攻擊、
護衛、逃跑或狂暴等名稱：

| 低四位模式 | 已證實的可觀察流程 |
|---:|---|
| 0 | 先走 `0x14EF0` 候選流程；失敗依序走 `0x14121` blocked-cell 搜索與 `0x13E9C` 最近相反分組座標備援 |
| 1 | 先走 `0x14EF0`；失敗只走 `0x14121` |
| 2 | 先走 `0x14EF0`；失敗呼叫固定回傳 0 的 `0x14237`，接著必然呼叫 `0x13FD4` 的條件式 HP 回復；不走 `0x13E9C` 最近座標備援 |
| 3 | 先走 `0x14EF0`；失敗以 `+0x35` 經 `0x12C60` 找單位並移向其座標；找不到才回到模式 0 備援 |
| 4 | 直接以 `+0x35/+0x36` 為目的座標交給 `0x14B78` |
| 5 | 先走 `0x14EF0`；失敗依 `+0x3D` 事件資料取得座標並移動；抵達後套用事件記錄並把整個 `+0x34` 寫成 7 |
| 7 | 直接移向 `+0x35/+0x36`；抵達後呼叫 `0x32975`，其已知效果僅是整個 `record+5` 寫成 1 |
| 8 | 沒有模式專屬動作，進入共用完成路徑 |
| 9 | 以 `+0x35` 找單位並移向其座標；找不到時回到一般 `0x14EF0` 路線 |
| 10 | 先走 `0x14EF0`；失敗改移向 `+0x35/+0x36` |
| 11 | 先以 `0x1598A` 建第一組結果；signed `[0x53C23]>=6` 時執行 `0x15311`，但仍繼續以 `0x14237` 建物理結果。signed `[0x53C4F]>=6` 時執行 `0x1548E`；否則走 `0x14121`，失敗才呼叫 `0x13FD4` |

**2026-08-14 模式 5 深挖 + 位址不可跨版位移警示**：模式 5 的 `+0x3D` 事件
資料機制已完整反組譯——`0x12D7B(actor)` 只是把 pathing 原點重置成單位當下
座標(讀 record[0]/[1] 轉呼叫另一個座標 setter),對可觀察遊戲狀態無副作用,
可安全略過;`0x15DF3(event_id,&out)` 對地圖網格做雙層迴圈掃描,呼叫
`0x3804C(x,y,&local)` 取每格 FDSHAP 衍生資料,篩選條件是地形控制旗標
`&0x60==0x20`(與 doc25 已記載的「寶箱/隱藏物品」旗標定義同一組位元),且
其內嵌值等於 `event_id`,找到就把 (x,y) 寫回 `*out`;抵達後在
`[0x53a55+0x53+event_id*3]` 讀 3-byte-stride 記錄(kind byte + word 值),
`kind<2` 時寫入 `record+0x31/+0x32`(即 `Unit.NativeRecordDeathEffect` 既有
儲存位置),`kind==0` 額外呼叫 `0x1BB8C`(`AssignNativeReservedItem`)發放
物品,最後標記 `[0x53AD5+event_id]`(`State.NativeEventState`)為已觸發並把
`record+0x34` 整個寫成 7(下次評估直接進模式 7,因為此時已站在目標格,會
立刻觸發模式 7 的抵達停用)。**"已觸發"分支**(`NativeEventState[id]!=0`)
與模式 1 的備援體完全同構,已在 `ApplyNativeAIMode5MovementFallback` 實作。

**"尚未觸發"分支已補上(2026-08-15)——原以為缺資料抽取,實際上資料早就
在,只是沒接線**:動手抽取前先查 `remake/internal/*/*.go`(依
`feedback_check_existing_evidence_before_disasm` 記憶的教訓)發現
`State.Treasures map[Cell]Treasure`(`model.go` 的 `loadTreasures`,在
`battle.Load` 時就已建好)早就把「FDSHAP 逐格 `&0x60` 旗標(`0x40`=隱藏,
對應這裡說的地形控制旗標)+ 控制段 16-slot 寶物 kind/value 表(`f.Chests`,
即 `[0x53a55+0x53+id*3]` 那組 3-byte-stride 記錄)」join 好了,資料來源是
`tools/sync_native_treasures.py`(逐格 `treasure_slots`/`treasure_hidden`,
每張 `map.json` 都有)——這正是 `0x15DF3` 掃描重現所需的完整資料,只是先前
沒人把它接進 AI 移動 fallback。已在 `ApplyNativeAIMode5MovementFallback`
補上:掃 `s.Treasures` 找 `Slot==record+0x3D` 的格子(`nativeMode5TreasureTargetCell`),
找到就用既有的 `ctx.moveToward` 移動過去(不使用 `OpenedTreasure` 二次
過濾——那是玩家 `ClaimTreasure` 用的獨立旗標,跟這裡已經檢查過的
`NativeEventState` 是不同概念)。找不到對應格子(該圖真的沒有這個
event_id,或資料不全)才 `ok=false` 交還呼叫端,不猜測。新增
`TestApplyNativeAIMode5MovementFallbackMovesTowardTreasureCellWhenNotYetConsumed`
覆蓋成功路徑;`go build/vet/test ./...` 全綠,零回歸。抵達後套用效果
(寫 `record+0x31/+0x32`、發放物品、標記已觸發、`record+0x34=7`)仍未做——
那是 task #98(執行鏈)的範圍,這裡只補了移動決策。

反組譯這兩個函式時發現一個重要教訓:`docs/data/fd2_ai_mode_dispatch_disasm.txt`
的位址(`0x13a9f` 等)全部來自已遺失的舊版 357074-byte EXE,**不能直接套用到
現行 509158-byte「新版」參考檔**——實測用位元組特徵搜尋確認,dispatcher 本體
在新版位於 `0x38CBD`,不是 `0x13A9F`,且位移量本身在模組內也不是常數
(進入點位移 0x25114,其第一個被呼叫函式位移卻是 0x25214,相差 0x100)。
正確作法是直接對新版 EXE 在其真實位址重新反組譯(byte-pattern 定位入口後
用 capstone 讀取當下 call 目標),而非把舊位址加一個猜測 delta。這不影響
模式 0/1/2/3/4/7/8/9/10 既有結論(全部源自自洽的舊版 dump 檔,並與 doc11
自身獨立記載的表格交叉核對,從未把舊位址直接套進新版即時反組譯)。

重製資料管線現保留 `native_record_byte34/35/36`，並可依原版規則
讀取低四位或保留高四位地批次改寫。這只是可執行的原始資料契約；
正規化 `NextAIPlan` 尚未依此表驅動，所以不能宣稱敵方回合已與原版相同。

### 模式 2／11 與 `0x13FD4` 的精確閉合

模式 2 的舊摘要曾把 `0x13B5F→0x14237` 後的共用跳點誤讀成
`0x13E9C` 最近座標備援。直接控制流實際是：

```text
0x14EF0 成功 → 共用收尾
0x14EF0 失敗 → 0x14237 → 固定回傳 0 → 0x13FD4 → 共用收尾
```

`0x13FD4` 不是泛稱的待機函式。它只在 current HP `+0x40` 不等於
max HP `+0x42`，且 raw `+0x25/+0x26` 都為零時，寫入
`min(currentHP + floor(maxHP/5), maxHP)` 並回傳 1；否則不改資料並
回傳 0。`ApplyNativeAIIdleRecovery` 保存這段狀態變更，畫面呈現仍分離。

模式 11 有兩個彼此獨立的有號門檻：

1. 一定先呼叫 `0x1598A`；只有 `[0x53C23] >= 6` 才執行 `0x15311`。
2. 無論第一段有沒有執行，仍呼叫 `0x14237`；只有
   `[0x53C4F] >= 6` 才執行 `0x1548E`。
3. 第二個門檻不足時呼叫 `0x14121`；其回傳 0 才呼叫 `0x13FD4`。

`PlanNativeUnitMode2/11` 只輸出上述位址導向的有界呼叫計畫。原始資產沒有
初始模式 11；目前唯一找到的低四位 11 writer 是全域事件 82 handler
`0x35F92` 內
`0x36078→0x3419C(0x14,0x14,0x0B)`：當 battle-local state
`[0x53AD5]+0x10 == 4` 時，把單位索引 20 的低四位改成 11。合法 IDA 9.4
確認 `0x35F92..0x36088` 函式邊界及其多個通用事件／介面 dispatcher
交叉參照；一般玩家如何選到事件 82 仍未知，而且 33 張 FDFIELD 格子事件表
沒有事件 82。這仍不足以替該狀態或模式命名成特定人物、章節或狂暴。

## 目前可重現的原始評分邊界（2026-07-29）

### 物理移動落點：`0x145CD→0x4E040/0x4E16E→0x146D1→0x14B16`

`0x14237` 在評分目標前，先建立所有可評分落點：

1. `0x145CD` 掃描所有有效執行期記錄。依呼叫者的原始選擇值，
   把另一組單位的中心格設 `0x40`（不可進入），四個相鄰格設 `0x80`
   （可進入，但扣除地形成本後將剩餘步數強制成 0）。
2. `0x4E040` 建立搜尋狀態，再由 `0x4E0DC` 以右、左、下、上順序遞迴；
   `0x4E16E` 是實際檢查 `0x40/0x80` 與地形成本的鄰格消費端。每格從
   FDFIELD 圖塊索引高位取得 `0..3`
   分組，查 FDSHAP 地形記錄 `+1` 的移動代碼，再以該代碼索引
   `0x4E555` 選出的 20 位元組成本列。只有新剩餘步數嚴格大於既有值才覆寫。
3. `0x146D1` 排除同一原始選擇組、有效且非行動單位的佔用格。
4. `0x14B16` 以 Y 外迴圈、X 內迴圈掃描所有不等於 `0xFF` 的剩餘步數格，
   因此最後候選是穩定的逐列順序（row-major），而非 `0x4E0DC` 的遞迴順序。

`battle.NativeAIPhysicalDestinations` 保存這四段只接受原始資料的契約，要求完整
執行期記錄、呼叫者短生命週期的執行期旗標（live flags）、
`NativeTerrainMoveCodes` 與20位元組
成本列；任何輸入缺失或越界都拒絕，不回退到重製端 `Cost`／`Reachable`。
選擇值的零／非零分組仍保持原始名稱，不猜成陣營或階段。

### 物理攻擊候選：`0x14237`

2026-07-29 以 Docker Capstone 重新讀取 `0x14237..0x145CC`，閉合下列順序：

1. `0x14258` 以第一參數索引 `0x50` 位元組單位記錄，保存 actor
   `word +0x48/+0x4A`。
2. `0x14288→0x1B83D` 及 `0x1429C→0x1B722→0x4E56C` 取得 actor
   的 raw command record；上一節四段流程建立候選格集合。
3. 每個候選格若通過 `0x1F183(actor)`，`0x143D9→0x12E38` 取地形
   control byte，依 `0x51A12/0x51A2A` 百分比表修正 actor
   `word +0x48/+0x4A`。
4. `0x14430→0x14818` 從候選格建立目標索引陣列。每個目標另在
   `0x1452A..0x14584` 以其所在格地形修正 target `word +0x48/+0x4A`。
5. 原始分數先計算 `actor word48 - target word4A`；`<=2` 直接略過。
   其餘候選的基本優先級為 8。若分數**嚴格大於** target `word +0x40`，
   分數乘 2、優先級升為 `0x12`。
6. `0x1448A→0x1DEBE` 回傳 1 時，分數再加
   `actor word4A - target word48`。target raw `byte +8==0` 時，
   以原版有號整數向零截斷規則乘 `3/2`。這兩個條件仍保留 raw 名稱，
   不猜成反擊或狀態。
7. `0x144C5..0x144F4` 先比較優先級，再比較分數；只有嚴格較大才覆寫
   最佳值，因此完全同分保留先枚舉者。勝出目的格、目標索引與優先級寫入
   `0x53C43/0x53C47/0x53C4B/0x53C4F`。

合法 IDA 9.4 以同一雜湊交叉確認函式邊界 `0x14237..0x145CC`，直接 callers
為 `0x13A9F` 兩處及 `0x14EF0` 一處；`0x1DEBE` 只有本評分函式的一個 caller。

**2026-08-25 live DOSBox-X 記憶體讀取閉合「鄰接卻不攻擊」子題目：確認不是
empty-weapon fail-closed，是 score `<=2` 拒絕門檻本身在真實戰鬥中命中**
（`tools/dosbox_harness.sh launch aiattack`，doc48 §8 + §9 recipe，ch08
「王城前的戰鬥」存檔）。延續同一份 RE-BATTLE-AI-SPECIAL-TOPIC 子題（上一輪
只用畫面觀察、未讀 record，見 doc91 該條目 2026-08-25 前段）——這輪主動誘敵
索爾（`camp=2`、AP922、**DP711**，`0x1EFA45`→`0x26C484` 陣列 slot0）北上，
連續兩回合後與 3 隻敵方單位同時鄰接：兩隻 `人類 法師`（LV11、HP11/11、
MP11/11，裝備 `巨錘`+`僧侶袍`）與一隻 `人類 戰士`／`鎧甲武士`（LV08、
HP8/8，裝備 `巨劍`+`鎖子甲`，slot11，位址 `0x26C7F4`）。End Turn 後：

1. 兩隻法師的 MP 都從 `011/011` 降到 `009/011`（逐一 `D` 讀 record 交叉確認，
   非畫面猜測）——與 `火炎術`(`-MP02`) 完全吻合，索爾 HP 從 `802`
   降到 `705`（-97），MP 全滿不變，證實是物理系以外的手段命中，兩隻法師都
   有出手（至少嘗試施法，MP 照扣，命中與否是另一件事）。
2. **戰士 slot11 的完整 raw record**（`D 0170:26C7F4`）：
   `+0x00/+0x01`(X,Y)=`0E 18`(14,24，與索爾當時座標(14,25)恰好 Y 差
   1，Manhattan 鄰接)；`+0x05`=`00`(未見已行動 raw gate，但跨 phase
   會被清，不能單獨當「本回合沒行動」的證據)；`+0x06`=`00`(敵方 camp，
   raw 已固定語意)；**`+0x0A`=`40`、`+0x0B`=`03`**——flag byte
   `0x40`（`0x80` 位元清除＝非空）＋item id `3`，**武器欄位確認非空**，
   與角色資訊畫面顯示的「巨劍」逐位元組吻合，直接**推翻**這個個案的
   empty-weapon 假說；`+0x34`＝`02`（低四位＝模式 2，doc11 表格既有
   「先走 `0x14EF0`；失敗呼叫固定回傳 0 的 `0x14237`」的行為，符合這隻
   戰士不會有第二次真實攻擊機會的預期）；`+0x48/+0x4A`(AP/DP)＝
   `49 00`/`30 00`＝`73`/`48`（戰士自己的 AP/DP，與角色資訊畫面的
   `AP·073`/`DP·048` 逐位元組吻合）。
3. **真正的拒絕點**：`0x14237` 第 5 步公式是 `actor AP − target DP`，
   `<=2` 直接略過候選（本文件既有記載，非本輪新結論）。此處
   `actor`＝戰士（AP73），`target`＝索爾（DP711，同一輪從索爾 record
   `+0x48/+0x4A`＝`9A 03`/`C7 02`＝`922`/`711`，與角色資訊畫面
   `AP·922`/`DP·711` 逐位元組吻合）：`73 − 711 = −638`，遠低於 `<=2`
   門檻——**這隻戰士對索爾完全沒有合法物理攻擊候選，不是因為它沒有武器，
   而是因為索爾的防禦力對它的攻擊力差距過大，命中既有評分公式的
   拒絕分支**。三個獨立來源（角色資訊畫面 UI、live record 位元組、
   doc11 既有反組譯公式）在 AP/DP 數值上完全收斂，信心度高。
4. **結論**：doc91 上一輪對 ch08 銀甲守衛（138HP）的「可能是 empty-weapon
   fail-closed」假說，在**這個個案**（不同的敵方個體，`人類 戰士`
   `鎧甲武士`，非上一輪那隻 138HP 守衛本體——同一場戰鬥/同一存檔下的
   另一隻鄰接不攻擊敵人，138HP 那隻本體這輪未在已初始化的 33 筆
   `0x26C484` 陣列中定位到，可能屬於後續增援波）被直接**推翻**：
   武器欄位確認非空，真正原因是已有靜態反組譯基礎的 AP−DP score `<=2`
   拒絕門檻，不是未知或缺記錄的行為。因為此門檻是 `0x14237` 通用評分
   公式的一部分（非任何特定單位/章節的特例），且索爾在兩輪調查中都是
   同一個高 DP 角色，doc91 原案例（138HP 守衛）極可能命中同一條門檻，
   但這點仍是推論，未對該特定個體做過位元組級驗證，保留為待補。截圖：
   `docs/figures/re-battle-ai-e2-ch08-armed-warrior-mode2-no-attack-2026-08-25.png`。

`battle.ScoreNativePhysicalAttackCandidate` 保存上述單一候選的 raw
評分契約；`SelectNativePhysicalAttackCandidate` 另保存優先級、分數及同分
保留先出現者的選擇順序。兩者沒有接入目前正規化 `NextAIPlan`，也沒有替
`0x1DEBE`、raw `+8` 或兩個 `word` 欄位擴張語意。

**2026-08-14 欄位語意交叉確認 + `0x1DEBE` 補完**(2026-09-05 補注:這幾個 offset 當時
只靠 remake 的 `native_equipment.go`/`tryIdleRecovery` 佐證,依現行判準不構成原版事實
的獨立證據;但同一組 offset 後來已經被**原版側** live 記憶體讀取獨立重新對過——見
`tools/fd2_stat_override.py` 檔頭 2026-09-02/2026-09-04 的逐欄對狀態卡記錄,結論一致,
故下面的公式推論仍然成立,只是引用鏈這裡補上原版側的獨立佐證):`ApplyNativeEquipmentRecalc`/
`ApplyNativeRuntimeEquipmentRecalc`(既有,`native_equipment.go`)已證實
`record+0x48/+0x4A/+0x4C/+0x4E` 分別是裝備結算後的 AP/DP/HIT/EV;
`tryIdleRecovery`(本次 session 稍早,mode 0/1 移動 fallback)已證實
`record+0x40/+0x42` 是目前/最大 HP。兩者交叉後,`0x14237` 的物理評分公式
語意變得清楚(僅公式層面,不改變任何 raw 命名規則):`actor AP − target DP`,
若嚴格大於 `target 目前 HP` 則分數翻倍、優先級提高(等同「預估可斬殺」加權),
`0x1DEBE` 條件成立再加 `actor DP − target AP`(近戰反打加成)。`0x1DEBE(actor,x,y)`
本身(doc91 `RE-ITEM-ADJACENCY-GATE-1DEBE` 條目,前次 session 已閉合)現已補上
Go 實作:`NativeAI1DEBEAdjacencyGate`——active gate、Manhattan 相鄰一格、
`0x1B83D(actor,0)`(`NativeEquippedInventorySlot`,既有)找到的裝備武器之
`item row +0x0b<=1`。

**地形百分比表(第 3-4 步)**:`ebx`=地形 control byte(來自 `0x3804C`/`0x12E38`
查表,mode5 investigation 已確認的通用函式),以 `ebx*4` 索引一張 6 筆
dword-stride 表,`adjustedWord = word + word*table[ebx]/100`(有號除法向零截斷)。
表的絕對位址(`0x51A12`/`0x51A2A`)在新版 EXE 上因 DOS4GW loader 重定位而無法
靠檔案位移直接推算,但**表的實際數值早就在 `remake/internal/battle/terrain.go`
的 `NativeTerrainAPDPPct` 裡**(`0x1acf3` 索引同一組位址,6 筆:
`(5,0)/(0,0)/(-5,10)/(-5,10)/(-5,-5)/(0,0)`),且已接進 `combat.go` 的
`AttackWithRNG`/`estDamage`。2026-08-14 用 DOSBox-X live memory 直接讀執行中
的遊戲記憶體獨立重新驗證過一次(方法:對照檔案裡已知的函式 prologue 位元組特徵,
在 live memory 找到同一特徵算出位移差值,再換算目標指令的真實位址;
`MEMDUMPBIN` 的 selector 參數必須用真正的 flat selector 如 `178`,填 `0`
會讀到垃圾),讀出的數值逐項相同;也用戰場游標實測的地形 UI 面板
(平地 A+05/D+00、樹林 A−05/D+10)獨立交叉驗證,同樣吻合——UI 面板顯示的正是
這張表的原始百分比,不是套用到特定單位 AP/DP 後的結果。三個獨立來源(舊
disasm 公式、live memory、遊戲內 UI)在此收斂,信心度很高。這套 DOSBox-X
live memory 萃取方法論存進了使用者記憶(`fd2-dosbox-live-memory-extraction`),
下次真的遇到位址算不出來的資料缺口可以直接套用。**教訓**:判斷「這個資料
還沒有」之前一定要先查 `remake/internal/*/*.go` 有沒有現成實作,不能只查
`docs/`——花了一整輪裝 Docker、建 dosbox-x 才發現這張表根本早就在 `terrain.go`
裡,`feedback_check_existing_evidence_before_disasm` 這條記憶已擴大範圍記錄
此教訓。

**`0x14237` composer 真正還缺的部分**:上面關閉的是**公式**(第 1、3、5-7 步)。
第 2 步(`0x14288→0x1B83D`/`0x1429C→0x1B722→0x4E56C` 取 actor raw command
record)與第 4 步(`0x14430→0x14818` 從候選格建立目標索引陣列,含 per-target
地形修正)都還沒有 Go 實作,也還沒有任何函式把 `NativeAIPhysicalDestinations`
(落點)、目標枚舉、`TerrainAPDPPct`(地形修正)、
`ScoreNativePhysicalAttackCandidate`+`SelectNativePhysicalAttackCandidate`
(評分/選擇)串成一個「輸入 actor,輸出最佳物理攻擊候選」的完整函式——
`combat.go` 現有的 `estDamage` 只是不含 priority 分級/`0x1DEBE`/raw`+8`
的 normalized 估值,不能當作已完成。

**2026-08-14 對第 2/4 步的進一步反組譯**(延續同一份
[`fd2_ai_physical_score_14237_disasm_partial_2026-08-14.txt`](../data/fd2_ai_physical_score_14237_disasm_partial_2026-08-14.txt),
補完到第 374 行,涵蓋完整第 1-4 步本體):

- **第 2 步已確認**:`0x40a51(actor,0)` 就是 `0x1B83D(actor,a2=0)`(裝備武器 slot,
  找不到回 -1、直接整個函式回傳 0——跟已知的 attack precondition 完全一致);
  找到 slot 後 `0x40936(selector,slot)`→item ID,再 `0x73ad0(itemID)`→該 item
  在 EXE item table 的 row 指標,讀 **row `+0xb`/`+0xc`** 存起來(doc32 已標記
  這兩個欄位是「caller-specific geometry inputs」,現在確認 caller 正是
  `0x14237` 物理評分本身,跟目標枚舉的幾何參數有關,不是通用武器射程)。
- **候選格集合的建構**(第 1-2 步收尾)其實是 `0x14237` 自己內部呼叫
  `0x397e1`(反標記對方陣營格 `0x40`+四鄰格,邏輯跟既有
  `nativeAIMarkOpposingGroupFlags` 完全一致)接著 `0x398e5`(疑似 budget
  flood-fill,尚未展開)產生的——證實 `battle.NativeAIPhysicalDestinations`
  重現的正是這條鏈路的最終結果,可以直接重用,不用重新反組譯 `0x397e1`/
  `0x398e5`/`0x398bb` 這幾個底層 helper。
- **第 3 步(地形修正)逐格重複執行兩次**:候選格迴圈裡先對 **actor 自己」
  當下座標**套一次 `0x3804C`+百分比表調整(`[esp+0x3c]`=adjusted AP),
  找到目標後又對**每個目標自己的座標**再套一次同一張表(`[esp+0x24]`附近
  的第二次 `0x3804C`+`idiv 100` 區塊,`0x039762` 起),分別調整 actor/target
  的 AP/DP——這與 `battle.TerrainAPDPPct` 目前「呼叫端自己對 actor 格、target
  格各查一次」的使用方式完全吻合,不需要改介面。
- **第 4 步(目標索引陣列)卡在 `0x39a2c`**:候選格迴圈在算完 actor 地形修正後
  呼叫 `0x39a2c`(6 個參數,含 item row `+0xc`、目的格 X/Y),回傳目標數量
  並把目標索引填進一塊 100-byte 緩衝區。這個函式本體**還沒有反組譯**——
  是目前唯一還卡住完整 composer 的未知函式;拿到它的參數語意與內部邏輯後,
  第 4 步就能收工,`0x14237` composer 才有辦法真正組裝完成。
- 額外發現:候選格→目標的雙層迴圈本身(`0x39a2c` 找到目標後,對每個目標
  再做一次差值檢查、`priority` 累積、寫回 `[0x3c43/47/4b/4f]`)已經跟第 5-7
  步(`ScoreNativePhysicalAttackCandidate`/`SelectNativePhysicalAttackCandidate`)
  的邏輯一一對應得上,沒有發現新的分歧。

**結論**:composer 現在缺的唯一硬缺口,是反組譯 `0x39a2c` 本體(目標索引陣列
產生器)。這是一個**有明確邊界、可獨立完成**的小任務,不是「量級遠大於已完成
部分」的大工程——跟先前 0x1DEBE/地形表比,難度相近。

**2026-08-14 `0x39a2c` 反組譯完成,composer 全部組裝完畢**:對新版 EXE 直接
反組譯 `0x39a2c` 本體(174 行,含其收尾迴圈),確認它是「以純 Manhattan 距離
(不含地形成本/尋路)+ `record+6` 的 0/1/2/3 raw 陣營碼」枚舉目標——跟
`0x14818`(`NativeCommandTargetFieldBytes`,給法術/道具用)是不同、更簡單的
函式,不能重用,已新增 `NativeAIPhysicalAttackTargets` 獨立實作。同一輪也
釐清了三個先前不確定的細節(皆已在反組譯中直接確認,非推測):

- **`0x1F183`(舊版位址)在新版對應的是 `0x44397`,不是消失了**——每個候選格
  都會對 actor 呼叫一次、每個目標也會各自呼叫一次,回傳 0 時**整段地形修正
  直接跳過**(維持 raw 值),不是「調整後套用另一個值」。跟 `move.go` 既有的
  `nativeMovementRow19Predicate`(class 0x13 或 race∈{4,5})是同一條 raw 公式,
  現以 `nativeAIPhysicalTerrainPercentApplies` 重現(raw-record 版本,原因見
  下)。
- **actor 的搜尋 budget 不是固定 28**,而是 actor 自己的 `record+0x3B`(剩餘
  步數)——這跟 mode 0 fallback 的 `0x14121`(固定 28)不同,是 `0x14237` 自己
  另外呼叫的。
- **`0x1DEBE` 的 `(x,y)` 參數是候選目的格,不是目標的座標**——從壓堆疊順序
  直接讀出來(`push[esp+0x48]`兩次,讀到的是目的格 X/Y 的相鄰記憶體,不是
  target 的);也就是這個近戰反打加成檢查的是「actor 現在的位置離候選目的格
  夠不夠近」,跟 target 在哪裡無關。

新增 `battle.NativeAIPhysicalAttackTargets`(目標枚舉)、
`battle.ScoreNativeAI14237`(完整 composer:武器裝備查詢→候選格→地形修正→
目標枚舉→逐目標評分→`SelectNativePhysicalAttackCandidate` 選出勝者),含
端到端測試(含 1DEBE 加成、raw+8 三分之二乘數同時觸發的完整公式路徑,驗證
跟已獨立測試過的底層 primitive 一致)。`go build/vet/test` 全綠。

**接線狀態(2026-08-14 更新)**:`ScoreNativeAI14237` 已接進真正驅動
`cmd/fd2` 敵方回合演出的路徑——`combat.go` 的 `NextAIPlan()`(不是
`aiActUnit`;後者從未被 `cmd/fd2` 呼叫,是死碼,見下一段)。接法是
fail-closed 的並聯,不是替換:`NextAIPlan` 每個單位先呼叫
`nativeAI14237Plan`,`ok==true` 時直接採用其 Path/Target(並標記
`AIPlan.NativeSourced=true`,純除錯/驗證用欄位,遊戲邏輯不應依賴它);
`ok==false`(原始資料不全)時完全退回既有 `aiTargets`/`estDamage` 正規化
近似,對現有 29 個章節的既有行為零改動零風險。`go build/vet/test ./...`
全綠,零回歸。另外(次要,`aiActUnit` 目前無人呼叫,但保留供未來復活該
路徑時沿用同一套邏輯)也在 `combat.go` 的 `aiActUnit` 開頭接了
`ApplyNativeAI14237PhysicalAttack`。

> ⛔ **[remake 證據排除]**(2026-09-04):以下這次「live 驗證」是透過 remake 的
> `FD2_CAMP_PREP_BATTLE` debug hook 取得的,依現行判準不構成原版 AI 行為的證據。
> 它觀察到的資料缺口可作為線索,但結論需以 DOSBox-X 原版重驗才算數。
>
> **2026-09-04(續)結案:主體不存在,且其中可查的子事實已被原版資料推翻。**
> 整段的主體是 remake 自己的型別與函式(`NativeAIScoringRecords`/`nativeAI14237Plan`/
> `ScoreNativeAI14237`),**沒有任何一句宣稱原版 AI 行為**;remake 已於 2026-09-02
> 移除,所以沒有「重驗」的對象。唯一能用原版資料查證的子事實則是**錯的**:
> 原文稱 ch01 那 8 個敵人「`inventory_slots[0]` 全部是 `0`(FD2 的「空」占位 item ID)」,
> 但直接讀 `FDFIELD_000`(`tools/parse_field.py`)得到的是 `slots=[0,128,255,255,…]`,
> 而 `exe_tables/item.json` 裡 **item 0 是真實武器**(type 1 / ap 10 / hit 95,最弱的一把)、
> **item 128 是防具**(type 21 / dp 2),**item 255 根本不在 0..214 的物品表內**——
> 空槽標記是 `0xFF` 而不是 `0`(`parse_field` 自己的過濾條件也是 `!= 0xFF`)。
> 全 30 張地圖的 slot0/slot1 值分布同樣是「武器 id / 防具 id」兩群,不是稀疏的 0。
> 因此「這些敵人手上沒武器,composer 正確判斷打不了」的解釋**不成立**;
> `HasWinner=false` 的真正原因未知(且因 remake 已移除而無實益)。
> 見 `docs/data/remake_excluded_claims.json` 的 `refuted_by_original_data`。

**live 驗證(2026-08-14,`FD2_CAMPAIGN=1 FD2_CAMP_PREP_BATTLE=battle_ch01
FD2_SHOT_AI=1 FD2_SHOT_TURN=1`,配合新增的 `AI決策: ... native=%v` 除錯輸出
逐幀觀察)發現一個真實、與本次 composer 工作無關的既有資料缺口**:
`NativeAIScoringRecords`(把整個 roster 編碼成 native raw record 陣列,
`nativeAI14237Plan`/`ApplyNativeAI14237PhysicalAttack` 都靠它)要求陣列
中**每一個**單位(不只是行動中的 AI 單位本身)都有完整的
`NativeRecordByte34/35/36`+`NativeRecordWord42/46` 原始 provenance;
ch01 實際戰鬥中,4 名玩家角色(索爾/亞雷斯/悠妮/蓋亞,透過
`internal/campaign` 的隊伍延續/加入路徑構造)這五個欄位全部缺席
(`Has...=false`),而同一場戰鬥的敵方單位(直接從
`assets/maps/map0/map0_units.json` 載入,該檔案本身就含這些欄位)全部
齊全。結果是 `NativeAIScoringRecords` 對整個 roster 回傳
`"unit 0 lacks raw provenance"` 錯誤,`nativeAI14237Plan` 因而對**每一個**
敵方單位都 fail-closed 退回 `aiTargets` 近似——也就是說,在今天的實際
玩家隊伍資料下,`ScoreNativeAI14237` 雖然接線正確、公式正確、單元測試
全過,但在真正戰鬥裡**目前還沒有機會真的觸發**。這不是接線的 bug(接線
本身的 fail-closed 行為完全正確,寧可退回近似也不要用不完整資料算出
錯誤決策),而是玩家隊伍單位建構路徑(`internal/campaign/
native_join_constructor.go`/`native_persistent_party.go`/
`native_continue_runtime_units.go`)還沒有反組譯出 byte34/35/36+word42/46
在「玩家角色」語境下該填什麼值——這幾個欄位目前只在敵方 JSON 資料裡
有現成值可搬,玩家角色從來沒有經過那條原始資料管線。留給下一輪有時間
做這個獨立小型反組譯調查時補上;補上後 `ScoreNativeAI14237` 不需要再
改一行程式碼就會自動在真正戰鬥中開始生效(fail-closed 設計的直接好處)。

**加碼驗證(同日,臨時 debug-only 補丁,已完全復原不留痕跡)**:為了分清
「接線本身有問題」跟「只是資料缺口」,額外用一個僅存在於當次測試 build、
從未進正式程式碼的臨時補丁,把上述 4 名玩家角色缺的 5 個欄位填上中性
占位值,重新跑同一場 live 驗證。結果:

- `NativeAIScoringRecords` 對整個 roster 編碼成功,不再報錯——證實先前
  的失敗確實只是資料缺口,不是接線邏輯錯誤。
- `ScoreNativeAI14237` 完整跑到底(武器裝備查詢→候選落點→地形修正→
  目標枚舉→評分→選擇),對 ch01 開場那 8 個已上場敵人(全部 group 1/2)
  逐一回傳 `HasWinner=false`——追查後每一筆都對得上:這 8 個敵人的
  `inventory_slots[0]` 全部是 `0`(FD2 的「空」占位 item ID),對應
  `0x14237` 反組譯註記本身就寫明的「沒裝備武器不是錯誤,直接回傳無候選」
  早退路徑——換句話說,composer 正確判斷「這些敵人手上沒武器,打不了」,
  不是漏抓目標。
- 進一步想找一個真的有武器的敵人強制站到玩家單位旁邊驗證「真的會選中
  攻擊目標」,但發現 `map0_units.json` 裡有武器(`inventory_slots[0]`
  非 0/0xff)的敵人全部屬於 group 10/11(後續增援波,例如索引 23/24/25
  是 `[1,...]`/`[52,...]`),ch01 prep-battle 這條路徑載入的初始 roster
  只有 group 1/2 共 8 個單位,增援波當下根本不在 `st.Units` 裡——要湊出
  這個情境需要額外接增援出場邏輯,已超出「驗證接線是否正確」的範圍,
  沒有繼續往下做。
- **結論**:composer 的資料管線+執行邏輯用真實遊戲資料格式跑起來是對的
  (跟先前 session 已詳盡覆蓋的 Go 單元測試——含 1DEBE 加成、raw+8 乘數
  同時觸發的完整公式路徑——互相印證);今天在真正戰鬥裡看不到它選中
  目標,原因僅止於上述玩家角色 provenance 缺口,不是 composer 本身還有
  未發現的邏輯問題。

**玩家角色 provenance 缺口正式補上(2026-08-15)**:改用使用者上傳的完整
976-fn Ghidra decompile(`FD2_decompile_full.txt`,見
[[fd2-ghidra-decompile]])做靜態反組譯(原本規劃的 DOSBox-X 活體記憶體
路線因這台機器 Docker Desktop 本身的環境問題卡死,已放棄,詳見下方
「環境問題」附記),找到 FDFIELD 驅動的敵方部署建構器本體(對應舊文既
記載的「FDFIELD b17/b18/b19→runtime+0x34/+0x35/+0x36」那個函式),逐行
核對後得到兩個可直接落地的結論:

1. **`record+0x34/0x35/0x36` 是 FDFIELD 部署建構器專屬欄位**——反組譯全文
   搜尋每一個讀寫 `+0x34`/`+0x35`/`+0x36` 的位置,除了這個建構器本身,
   唯一的讀取端是 `0x13A9F` AI 分派器(byte34 低 4 位是 mode nibble、
   byte35/36 是 mode7「返回重生點」用的 X/Y——不是旗標位元),而
   `0x13A9F` 從不對玩家陣營(`Own`)執行。另外三個位元讀取點
   (`&0x40`/`&0x80`/`&1`,對應既有文件記過的「+0x34 bit0 令法術治療分數
   ×2」)全部只用在**施法者評估自己同陣營候選**的場景,敵方 AI 從不會把
   玩家單位當這種候選(玩家跟敵方是對立陣營)。**結論:對玩家單位而言,
   這三個位元組的實際數值在目前任何已知 AI 讀取路徑下都不影響決策**,
   而透過 JOIN/class-table 建構器(`native_join_constructor.go`)的反組譯
   也證實它從未寫入這三個位元組——也就是說原始二進位下,新加入隊伍的
   玩家角色這幾個位元組本來就是(record slot 的)零初始狀態,不是猜測。
2. **`record+0x42/+0x46`(最大 HP/MP)不是 FDFIELD 專屬**——同一個建構器
   在新單位剛生成、目前 HP/MP 等於上限時,把 `+0x40`(目前HP)跟
   `+0x42`(最大HP)寫入同一個計算值,`+0x44`/`+0x46` 同理——證實
   `NativeRecordWord42 = uint16(單位的MaxHP)`、`NativeRecordWord46 =
   uint16(單位的MaxMP)` 這個既有假設(部分既有程式碼——
   `native_join_constructor.go`/`native_persistent_party.go`/
   `native_continue_runtime_units.go`——早已用這個公式,只是沒覆蓋到
   `event.go` 的 `Scenario.PartyUnits`,也就是最單純的「剛開場的隊伍」
   構造路徑)是對的。

已在 `remake/internal/battle/event.go`(`Scenario.PartyUnits`)、
`remake/internal/campaign/native_join_constructor.go`、
`remake/internal/campaign/native_persistent_party.go` 三個新單位建構點
補上 `NativeRecordByte34/35/36=0` + `NativeRecordWord42/46=MaxHP/MaxMP`
(`native_continue_runtime_units.go` 是存讀回真實 raw record 的續存路徑,
本來就正確,未動)。`go build/vet/test ./...` 全綠,零回歸。用同一套
`FD2_CAMP_PREP_BATTLE=battle_ch01 FD2_SHOT_AI=1 FD2_SHOT_TURN=1` 重跑
live 驗證,`NativeAIScoringRecords` 不再對整個 roster 報錯——先前擋住
**每一個**敵方單位的資料缺口正式關閉。ch01 開場那個特定敵人仍然
`HasWinner=false`,但原因跟前面確認過的完全一致(它裝備的是 item ID 0,
FD2 的「空」占位——沒武器打不了是正確結果),不是新引入的問題。

**環境問題附記(跟 fd2_re 專案本身無關)**:這台機器的 Docker Desktop 在
這次調查中反覆出現 `dockerInference`/`docker-secrets-engine` 等多個
AF_UNIX socket 檔案「The filename, directory name, or volume label
syntax is incorrect」錯誤,連 factory reset、整機重開機都沒解決(只有
把單一卡死目錄整個改名才讓它往前一步,隨即在另一個全新路徑撞上同一種
錯誤)——判斷是這台 Windows 環境本身 AF_UNIX socket 建立機制的系統性
問題,不是這個專案的 Docker 設定或 `docker/dosbox-x/Dockerfile` 的問題。
已改用靜態反組譯路線繞過,不影響本項結論的正確性,但代表
`reference_fd2_dosbox_live_memory_extraction` 那套活體記憶體方法論在這台
機器上暫時不可用,需要時再另外排查(可能需要系統管理員權限層級的
Windows AF_UNIX/防毒軟體診斷)。

### `0x14EF0` 本體：三分數決策 + 分派（2026-08-14 新版即時反組譯首度取得）

沿用「先確認 `0x13A9F` 在新版真實位址(`0x38CBD`)，再讀取其對 `0x14EF0` 的
呼叫得到 `0x14EF0` 真實新版位址(`0x3A104`)」這條已驗證鏈路（見上方「位址
不可跨版位移」節），直接對新版 EXE 反組譯 `0x14EF0` 本體，完整結構首次取得
（舊版 dump 只到 `0x13A9F` 為止，從未涵蓋 `0x14EF0` 內部）。完整反組譯見
[`fd2_ai_14ef0_dispatch_disasm_2026-08-14.txt`](../data/fd2_ai_14ef0_dispatch_disasm_2026-08-14.txt)。

確認的結構（呼叫端已知全等於 `actor,selector` 兩參數）：

1. 依序呼叫**物理**評分(`0x14237`)、**法術**評分(`0x1598A`，`battle.ScoreNativeAI1598A` 已閉合)、**道具**評分(`0x1567E`，`battle.ScoreNativeAI1567E` 已閉合)。三者各自把結果寫進 `[0x53C43/47/4B/4F]`(物理:目的X/Y/目標索引/**priority**，非 score)、`[0x53C23]`(法術 MaxScore)、`[0x53C33]`(道具 MaxScore)。
2. **三分數門檻**：`[0x53C4F]>=6 OR [0x53C23]>=6 OR [0x53C33]>=6` 任一成立才繼續；三者皆 `<6` 直接回傳 0(無行動)。**物理槽位比較的其實是 priority(值域只有 8 或 0x12)，不是分數**——這代表物理的「>=6」門檻在實務上等同「有沒有找到任何被接受的候選」，跟法術/道具的門檻在語意上不是同一種東西，這點先前完全沒被記錄過。
3. **勝者選擇——2026-08-15 訂正為逐行反組譯版本(見
   `docs/data/fd2_ai_14ef0_dispatch_disasm_2026-08-14.txt` 完整證據,下面這段先前是
   不夠精確的自然語言摘要,已用 `battle.SelectNativeAIThreeScoreWinner`
   (`native_ai_three_score_choice.go`,9 條測試逐分支覆蓋)重新逐行核對過)**:

   ```
   若 physical<6 且 spell<6 且 item<6 → 無行動
   若 physical>spell 且 physical>item → 物理
   若 physical==spell 且 physical>item:
       若 spellCommandID<0xb(攻擊術家族):
           若 book[spellCommandID].Damage < (actor.AP-target.DP,以物理候選自己的
              actor/target 重算,不是 0x14237 內部已存的分數)→ 物理
           否則 → 法術
       否則(spellCommandID>=0xb,回復/增益/狀態術家族):
           bit==0 → 法術;bit!=0 → 物理
   若 physical==item 且 physical>spell:
       bit==0 → 道具;bit!=0 → 物理
   若 spell>physical 且 spell>=item → 法術
   若 item>physical 且 item>spell → 道具
   以上皆不成立(例如三者剛好完全相等)→ 無行動(不呼叫任何一條執行分派)
   ```

   `bit = actorRecord[0x34]&0x40`(**高四位**,跟已知的低四位 mode nibble 是不同
   bit,遊戲語意未命名)。**重要訂正**:先前筆記誤以為「三者完全相等時看 bit 決定
   法術或道具」,逐行核對組語後確認**三者完全相等(physical==spell==item)會落到
   跟三者皆<6 不同、但同樣是「無行動」的分支**——bit 只在「物理與法術(或物理與
   道具)兩者相等、且都嚴格大於第三者」時才生效,不是三方全等時的 tie-break。另一個
   先前完全沒記錄到的重點:物理/法術同分時,若法術是攻擊術家族(命令 ID<11),
   tie-break 用的是**該指令的 Damage 數值 vs 重算的物理分數**,不是 bit——bit 只用
   在法術是回復/增益/狀態術家族(ID>=11)時。
4. 三個執行分派目標也已個別確認開頭：
   - **物理執行**(`0x3A6A2`)：呼叫 `0x12D7B`(重置 pathing 原點，本 session mode5 investigation 已證實無副作用)→ 以 `[0x53C47]`(Y)、`[0x53C43]`(X) 呼叫 `0x14B78` 移動 → 再讀 `[0x53C4B]`(target index)、再呼叫一次 `0x12D7B`。跟 `0x1548E` 已知的移動+攻擊呈現流程高度吻合，但這次是從 `0x14EF0` 直接反組譯確認呼叫端，不是舊 doc 的位址推測。
   - **法術執行**(`0x3A525`)：讀 `[0x53C2F]`(未命名的 spell-related global)，經一個「by-index 取 record 指標」共用 helper(`0x73A7A`)取得 record，讀其 raw camp byte(`+6`)。**2026-08-14 補充偵察**(反組譯了 `0x3A525` 本體,`0x3A525..0x3A6A1`,約 380 bytes):先檢查 `[0x3C23]>=6`(法術分數門檻,低於則整段直接回傳 0,像是保險檢查);接著呼叫 `0x12D7B`(pathing 重置),再呼叫 `0x39A2C`——**確認 `0x39A2C` 是通用函式,不是物理專屬**,法術執行這裡也拿它建目標索引陣列(用 `[0x3C27]/[0x3C2B]` 當座標、`esi+4` 當某種 range/tier 值),不影響本節已完成的 `NativeAIPhysicalAttackTargets` 實作(那是以物理攻擊的參數語意包一層,函式本身仍是同一顆)。再往下呼叫 `0x55115`、`0x426DF`/`0x4270A`(經 `[eax*4+0x1D01]` 的 jump table,疑似依法術 family 分派效果 handler)、`0x40867`、`0x42D79`、`0x3FC31` 等一整串完全沒追過的函式,還牽涉 `[0x3AF9]` 這個未命名旗標(疑似演出/動畫開關)。**結論:法術執行鏈確實是量級遠大於評分本身的獨立效果系統(傷害/回復/狀態套用+演出),不是能在同一輪順手關閉的小任務**,doc42「量級更大」的判斷經這次偵察確認無誤,不是還沒查過就假設困難。
   - **道具執行**(`0x3A269`)：讀 `[0x53C3F]`(即 `battle.NativeAI1567EScoreResult.InventorySlot`)，以 `(actorIndex, inventorySlot)` 呼叫一個道具使用/消耗 helper。

**2026-08-15 深入偵察(task #98,Docker 4.83.0 降版後重新可用 DOSBox-X live 記憶體)**:
完整反組譯了 `0x3A269` 本體(約 150 條指令,`docs/data/fd2_ai_item_exec_3a269_disasm_2026-08-15.txt` 有完整逐行證據+每個子函式的獨立反組譯),混用 `tools/disasm_le.py` 做 LE object0 範圍內(`[0x10000,0x4EF29)`)的純靜態反組譯,以及 DOSBox-X live 記憶體讀取 overlay 區(超出 LE object 範圍的呼叫目標,已知屬 task #8 的 overlay 機制)兩種方法:

- **確認的 call chain**:`0x40936(actorIndex,slot)` 只回傳 `actorRecord[0xb+slot*2]`(即 FLAGS byte,偶數 offset,不是 item ID)→ `0x73AD0(flagsByte)` 回傳 `0x1f22ad + flagsByte*23`(23-byte-stride 表,**確認**是 `0x73A7A`「by-index 取指標」helper 家族的另一個成員,表格內容語意未解)→ 依表格 row+0x10 的「type」byte 決定走 `0x39C0C`(type>0xF,`command-0x10` 分支,跟已知 `0x1567E` 評分的 command 分裂規則完全對上)還是**確認**已知的通用 `0x39A2C`(type≤0xF,建目標陣列)。
- **道具執行後半段幾乎全是演出,不是效果套用**——逐一反組譯確認:`0x4425E` 是「依兩單位座標算 4 方向並寫入 record+3(Pose)」的朝向計算(不是效果);`0x46AAE`/`0x36EC0` 是 cell→screen 座標換算+ sprite blit(跟既有 `foreground_layer.go` 的 `0x8088` work-buffer base 字面值完全對上,強力交叉驗證);`0x3CCBD` 是讀 BIOS tick counter(絕對位址 `0x46c`)的忙等延遲迴圈;`0x531DC`(overlay 區,live 反組譯)配置兩個 VGA framebuffer 大小的緩衝區(0xfa00=64000、0x1f400=128000 bytes)並呼叫已知的 `0x3804C(actorX,actorY,&out)`(mode5 investigation 已確認的「取該格 FDSHAP 衍生資料」helper),疑似螢幕擷取/縮放轉場效果,尚未追完。
- **仍未找到真正的「消耗道具/套用效果」邏輯**——上述每一個已追完的呼叫都是演出或純目標枚舉,沒有一個在修改 HP/MP/inventory slot。真正的效果套用要嘛藏在還沒追的呼叫裡(`0x39C0C` 本體、`0x73160`、`0x37006`、`0x531DC` 後半段),要嘛在 `0x3A269` 尚未反組譯的尾段(`jmp 0x3a4f9` 之後)。**結論:跟法術執行鏈一樣,道具執行也是量級遠超「評分→執行」單純轉發的獨立系統,這次偵察定位出大量演出層 helper 並排除它們是效果來源,但核心效果邏輯仍未關閉**——不誇大偵察範圍,誠實標記為部分完成。
- **方法論副產物,對未來繼續有價值**:1) 確認同一個 container run 內,`0x73A7A`/`0x73AD0` 這類 overlay 區位址無法靠 `disasm_le.py` 純靜態讀到(超出 LE object0/1/2 宣告範圍,需要 live 記憶體);2) 確認 live delta(這次 run 是 `0x176DEC`,即時對照 byte 特徵搜出來的,**不可**沿用到下次 container 重啟)必須每次重新用位元組特徵搜尋法重新推導,不能用 MEMDUMPBIN 直接餵靜態位址(這次一開始犯過這個錯,浪費了一輪);3) 確認 CODE 的 relocation delta 和內嵌絕對位址「DATA」引用的 patch 量是**兩個不同的量**(0x176DEC vs `[0x3a45]`→`[0x1efa45]` 的差值 0x1EC000),不能假設同一個 delta 兩者通用。

**2026-08-15 重大結構性發現:道具與法術執行鏈共用同一個效果核心 `0x45E83`**——
繼續往下追 `0x3A269` 尾端(`jmp 0x3a4f9` 之後,先前標記「尚未反組譯」的部分)找到
`push actorIndex,inventorySlot,targetArrayPtr,&localBuf; call 0x45E83`。完整反組譯
`0x45E83` 本體(約 280 條指令,已整段附進
`docs/data/fd2_ai_item_exec_3a269_disasm_2026-08-15.txt`)後確認:

1. **函式一開頭就呼叫 `0x426DF`**——這正是 doc11 先前為**法術執行鏈**(`0x3A525`)
   記錄過的「疑似依法術 family 分派效果 handler」的 jump-table 函式之一。函式**結尾**
   (不管中間走哪個分支,`kind` 落在已知範圍或未知都會匯合到這裡)則依序呼叫
   `0x4270A`(法術鏈另一個已知 jump-table 函式)→`0x408CB`→`0x42D79`(法術鏈另兩個
   先前完全沒追過的函式)。**結論:`0x45E83` 不是道具專屬,是道具與法術共用的核心
   效果套用系統**——`0x3A269`(道具)跟 `0x3A525`(法術)最終都會走進同一套機制,
   代表法術執行鏈原本被判斷「量級遠大於評分本身」的那個獨立效果系統,跟這裡找到
   的道具效果系統是**同一個東西**,不是兩套要分別關閉的工程。這大幅改變了 task #98
   剩餘工作的樣貌(從「兩條各自要追的獨立系統」變成「一個共用核心 + 兩個很薄的
   前段轉接層」),但也代表這個共用核心本身规模夠大,值得先看完整 kind 目錄再評估。

**⚠️ 2026-08-15 重大修正(讀者請先看這段再看下面的 kind 表)**:下面這張表跟後續
公式小節,是這輪反組譯的產出,但**核對既有 Go 程式碼後發現裡面大部分(HP/MP 回復、
HP 傷害、BaseAP/DP/DX 調整、HIT/EV/DP%/AP% buff、狀態清除、狀態施放)在更早的 session
就已經反組譯+實作+測試完成**,只是用舊版位址編號(`0x1c916`/`0x1c81f`/`0x1c9dd`/
`0x22997`/`0x22721`/`0x22866`/`0x22af6`/`0x22d1b`)記錄在
`remake/internal/battle/native_raw_*.go`,這次沒有事先查就重新反組譯了一輪——是這個
專案已經記過的「重工」錯誤模式再犯一次(見 `feedback_check_existing_evidence_before_disasm`
memory)。下表**保留**是因為:(a) 新舊位址對照本身有價值,(b) 逐行反組譯**證實**了既有
Go 實作跟原生二進位的公式一致(含一個修正:公式的 RNG 項是 `bonus%100`(餘數),先前
筆記誤寫成 `bonus/100`(商數),已核對既有程式碼 `nextRNG%100` 訂正),不是平白無據的
猜測。**新舊位址對照**:`0x41B2A`=`0x1c916`(HP回復)、`0x41A33`=`0x1c81f`(HP傷害)、
`0x41BF1`=`0x1c9dd`(MP回復)、`0x47BAB`=`0x22997`(HIT/EV buff)、`0x47A7A`=`0x22866`
(DP% buff)、`0x47935`=`0x22721`(AP% buff)、`0x47D0A`≈`0x22af6`(狀態清除,
`ApplyNativeRawFlagRestore`)、`0x47F2F`≈`0x22d1b`(狀態施放,`ApplyNativeRawApplication`)。
**真正的缺口不是效果公式本身**(那些已經做完),**是 AI 決策從來沒有連到這些既有實作**
——`combat.go` 的 `NextAIPlan` 每個分支都寫死 `SpellID: -1`,`cmd/fd2/main.go` 的
`ExecuteNativeCommand*` 系列只接在玩家手動操作的 `confirm()`,`aiStep`(AI 回合驅動)
完全沒有呼叫過。道具side 更早一步:`native_item_*.go` 的 6 個 `RouteForType`+`Apply*`
配對(HP回復/MP回復/APDP/HITEV/狀態清除/狀態施放,同樣已存在+測試)甚至**沒有任何
呼叫端**——不只 AI 沒接,玩家道具介面也沒接,是比法術更早一步的缺口。詳見本節最後
「真正待辦」的修正版。

2. **`kind` byte 分派表(來源:`0x73AD0(flagsByte)` 回傳的 23-byte-stride table row
   的 `+0xd` byte,`+0xe` 是伴隨的 16-bit payload word)**——目前已個別確認呼叫目標
   的 kind 值(**目標函式位址已確認,個別函式內部語意大多還沒追,除了特別註記的
   幾個**):

   | kind | 呼叫目標 | 狀態 |
   |---:|---|---|
   | 5, 0xd | `0x463B8` → `0x41B2A` | ✅ **完整證實**:HP 回復,見下方公式小節(含 `0x73DF7` RNG 加成項,已解開) |
   | 6 | `0x47D0A(0x25,...)` | ✅ **結構證實**:狀態解除模式(清 `record+0x25`+小量回復 10),見下方小節 |
   | 7 | `0x47D0A(0x26,...)` | ✅ **結構證實**:同上模式,清 `record+0x26` |
   | 8 | `0x46296(...,0x37,payload,...)` | ✅ **完整證實**:`record[target+0x37] += payload`(`+0x37`=已知 `BaseAP`),接著呼叫 `0x40964`(既有裝備 recalc 函式)重算有效 AP |
   | 9 | `0x46296(...,0x39,payload,...)` | ✅ **完整證實**:同上,`record[target+0x39] += payload`(`+0x39`=已知 `BaseDP`) |
   | 0xa | `0x46296(...,0x3e,payload,...)` | ✅ **完整證實**:同上,`record[target+0x3e] += payload`(`+0x3e`=已知 `DX`) |
   | 0xb | inline | ✅ **完整證實**:`record+0x46`(`MaxMP`)非零呼叫 `0x41BF1`(MP 版 `0x41B2A`,讀寫 `+0x44/+0x46`)+顯示,為零呼叫 `0x433F0`(resist)——對有 MP 單位回 MP、無 MP 顯示無效,道具「Ether」類效果 |
   | 0xc | `0x47BAB` | ✅ **完整證實**:`RNG()/100+2` 寫入 `record+0x24`(buff 持續回合數),`word[target+0x4c] += 0xf`、`word[target+0x4e] += 0xf`(`+0x4c`=`HIT`、`+0x4e`=`EV`,均已知 offset)——**HIT/EV 各 +15 的定量 buff,持續 2~? 回合(RNG 決定上限未知,除數為 100 但沒看到明確上限測試,先只記「除以 100 再 +2」這個確切算式)** |
   | 0xe, 0x16 | `0x47F2F(0x26/0x1b,...)` / `(0x27,...)` | ✅ **完整證實**:先種族免疫檢查(`race==0x19 或 0x1a` 直接跳過)+目標欄位(`record+呼叫端傳入的 offset`,kind0xe 是 `+0x1b`)已非零就跳過(已中招不重複),否則 `RNG()%100>=50` 也跳過(**50% 機率**)——命中才呼叫 `0x41A33(targetByte,10)`,已逐行反組譯確認是 `0x41B2A`(HP回復)的**完全鏡像**:同樣的 `payload*9/10+RNG加成/1000` 算式,但用**減法**且夾在 0 以下(不是加法夾 maxHP),即 **~9 點傷害+隨機加成的直接傷害**,並把 `RNG()%4+2`(2~5 回合)寫入該欄位,`[0x3ec8]` 另外累加 `race[+0x21]*8` 的種族修正——**狀態異常(如中毒/麻痺類,附帶命中瞬間小量傷害)的完整命中判定+持續回合機制,公式跟數值完全閉合**;`kind0e` 寫入的欄位 `+0x1b` 落在已知的 `initial_command_mask`(`+0x1a..+0x1d`)範圍內,語意待進一步確認是否真的是指令遮罩位元還是巧合重疊 |
   | 0xf | `0x47A7A` | ✅ **完整證實**:`RNG()/4+2` 寫入 `record+0x23`(buff 持續回合),`word[target+0x4a]`(`DP`)套用 `floor(DP*常數[0x218]+1)` 的百分比加成——**DP 百分比 buff,持續 2~5 回合** |
   | 0x10 | `0x47935` | ✅ **完整證實**:同構,`RNG()/4+2` 寫入 `record+0x22`,`word[target+0x48]`(`AP`)套用 `floor(AP*常數[0x210]+1)` 百分比加成——**AP 百分比 buff,持續 2~5 回合** |
   | 0x11 | `0x46296(...,0xd,payload,...)` | ✅ **機制證實,語意未定**:`record[target+0xd] += payload`(word add)——`+0xd` 落在 inventory 區(slot1 flags+id 兩個 byte 疊在一起被當 16-bit 加),語意不明,**不可**套用 kind8/9/a 的 stat-offset 猜測 |
   | 0x12 | `0x46296(...,0xd,payload,...)` | 同上,offset 同為 `0xd`,只差 id 常數 `0x46` |
   | 0x13 | `0x46296(...,0x3b,...)`,外層先存後還原 `record+0x3c` | 未確認語意,「暫存一 byte、套效果、還原」的模式 |
   | 0x14, 0x18 | inline,`0x41972` 判斷 | ✅ **結構證實**:`0x41972` 讀 `record+0x20`(已知 `RACE`)並呼叫 `0x73A7A`,==0 時對 target 套用+顯示(`0x432EF id=0x5e`),否則 `0x433F0`(resist)——強烈疑似種族抗性檢查,未逐行證實 `0x73A7A` 後半段在比對什麼確切種族清單 |
   | 0x15 | `0x4632E` | ✅ **結構證實**:跟 kind0x14/0x18 用同一個 `0x41972` 抗性檢查骨架,同一套 resist/apply 分支 |
   | 0x17 | `0x4739E` | 🟡 **不同類型,未確認**:不是狀態迴圈模式——讀 actor 自己的 X/Y,push 兩個 `0xff` 常數後呼叫另一函式,疑似「以座標為目標」的效果(傳送/範圍類?),跟其他 kind 的「對 target 陣列迭代」模式不同,需要獨立追蹤 |

   共 20 個已定位的 kind 分支。**11 個完整證實**(5/0xd, 8, 9, 0xa, 0xb, 0xc, 0xe/0x16,
   0xf, 0x10),**4 個結構證實但確切語意未 100% 閉合**(6,7,14,15,18),**3 個機制證實、
   語意未定**(0x11,0x12,0x13),**1 個結構完全不同、獨立仍未追**(0x17)。

3. **共用 primitive 目錄(這輪新確認)**:
   - `0x432EF`:✅ 已證實**只是浮動數字顯示**(拆位數寫進 UI 緩衝、檢查目標是否在鏡頭
     可視範圍),不套用效果,先前「疑似套用數值」的猜測已排除。
   - `0x433F0`:✅ 已證實是「resist/無效」訊息顯示(讀 `[0x204a]` 格式字串,跟
     `0x432EF` 讀 `[0x2045]` 是不同訊息),同樣做鏡頭可視檢查。
   - `0x46296`:✅ 已證實是**通用 16-bit record word 累加 primitive**——
     `record[target+offset] += payload`,offset 由呼叫端決定(kind8/9/a/11/12/13
     各自傳不同 offset),之後統一呼叫 `0x432EF` 顯示、`0x36EC0`+`0x4316C` 播動畫、
     `0x40964`(裝備 recalc)、`0x40AFB`(疑似 inventory UI 清單刷新)。
   - `0x41972`:✅ 已證實讀 `record+0x20`(RACE)+呼叫 `0x73A7A`,是 kind14/15/18
     共用的抗性判斷式(細節未完全閉合)。
   - `0x39C0C`(道具 `0x3A269` 本體、command>0xF 分支專用):✅ **已證實**跟已知
     `0x149F8`(評分端)是同一種「從起點朝目標走 N 步」路徑建構器——item command 值
     (`command-0x10`)決定走幾步,逐步累加 `[0x3ab1]`/`[0x3ab5]` 座標,產生沿線
     cell 陣列。至此 `0x3A269` 本體(不含共用效果核心 `0x45E83`)裡原本標記
     「尚未追」的部分已全部關閉。

**`0x41B2A`:kind5/0xd(HP 回復)的完整公式,已逐行反組譯證實**——這是整個效果系統
目前唯一一個從「選中道具」到「record 被寫入新值」全程證實的分支:

```
target = 目標單位 record(param1 by-index)
curHP  = word[target+0x40]      # 目前 HP(已知欄位)
maxHP  = word[target+0x42]      # 最大 HP(已知欄位)
payload = param2                 # 23-byte-stride table row+0xe 的 16-bit payload word

termA = (payload * 9) / 10                 # 89~90% payload,整數除法無條件捨去
bonus = call 0x73DF7()                     # ✅ 已證實是 RNG:seed=word[live-patched全域];
                                            # seed=(seed+0x9014) rol 1 rol 1 rol 1;寫回並回傳新 seed
                                            # (簡單 additive+rotate LCG-like PRNG,無參數、純內部狀態)
termB = ((bonus % 100) * payload) / 1000   # ⚠️ 訂正(2026-08-15):原筆記誤寫成
                                            # bonus/100(商數),重核 idiv 後 imul 的是
                                            # edx(餘數)不是 eax(商數),應為 bonus%100;
                                            # 跟既有 Go 實作 native_raw_restore.go 的
                                            # `int(nextRNG%100)*amount/1000` 完全一致

newHP = min(curHP + termA + termB, maxHP)  # 加總後夾在 maxHP 以內
delta = newHP - curHP                       # 保存差值(給下方 0x432EF 的浮動數字顯示用)
word[target+0x40] = newHP                   # ***實際寫回,這是真正的遊戲狀態變更***
```

**此公式現已 100% 閉合,不含任何未知函式**——`0x73DF7` 這輪已完整反組譯確認是純
RNG,不影響已確認的公式結構。

`0x432EF(delta, effectAnimID, targetByte)` 緊接著被呼叫,反組譯後確認**只做畫面
呈現**(把 `delta` 拆位數、寫進螢幕座標旁的浮動數字顯示緩衝區,並檢查目標是否在
目前鏡頭可視範圍內,不在畫面內就整段跳過不顯示——不影響已經寫入 record 的實際效果),
不是效果套用的一部分,先前「疑似套用數值」的猜測已被排除。`0x433F0` 同樣是訊息顯示
(resist/無效,讀不同的格式字串),不套用效果。

**`record+0x22..+0x27` 狀態/buff 持續回合欄位家族(這輪完整定位)**:
- `+0x22`:kind0x10(AP% buff)持續回合,`RNG()/4+2`
- `+0x23`:kind0xf(DP% buff)持續回合,`RNG()/4+2`
- `+0x24`:kind0xc(HIT/EV +15 定量 buff)持續回合,`RNG()/100+2`
- `+0x25`:kind6 清除目標(cure)
- `+0x26`:kind7 清除目標(cure);也是 kind0xe 的狀態異常欄位(`0x47F2F` 呼叫端傳入)
- `+0x1b`(不在 +0x22..+0x27 範圍內,落在已知的 `initial_command_mask` 區):
  kind0xe 實際 SET 的欄位——offset 落點待確認是否真的跟指令遮罩衝突或只是巧合

**2026-08-15 修正後的真實現況**:20 個 kind 裡,**至少 9 個(5,0xd,6,7,8,9,0xa,0xb,0xc,
0xf,0x10,0xe,0x16——比原本數字還多,因為訂正後把 0xe/0x16 也算進「效果+公式都閉合」
而非只有「結構」)公式已經在既有 Go 程式碼(`native_raw_*.go`)裡實作+測試過**,這次
反組譯只是重新證實+補上新舊位址對照,不是從零開始的新工作。**3 個機制證實、語意
未定**(0x11,0x12,0x13,offset `0xd` 落在 inventory 區的語意仍不明,這部分確實還沒有
既有實作對照,是真的新發現)。**1 個結構完全不同、仍未追**(0x17)。

**真正的缺口,修正後的版本**:
1. ~~AI 決策沒有連到已存在的法術執行~~ **✅ 已完成並測試(2026-08-15 續)**——見下方
   「三分數決策已接進 NextAIPlan」段落。
2. ~~道具側連玩家都沒接~~ **⚠️ 這句話是錯的,2026-08-15 續再次核對後撤回**:
   `cmd/fd2/native_item_panel_ui.go` 的 `applyNativeTargetItem` 早就是一個完整、
   已接進玩家 `confirm()`(經由 `g.nativeItemTargeting` 游標選擇流程)的頂層
   dispatcher,依序試 `NativeItemHPRestoreRouteForType`/`MPRestore`/
   `MarkerClearRestore`/`HITEVStep`/`APDPStep`/`MarkerApplication`/
   `CommandDamage`/`Relocation` 八組 route,呼叫對應 `Apply*`。**這是本文件先前
   幾輪反組譯中沒有交叉檢查 `cmd/fd2/` 目錄就下的錯誤結論**——教訓:確認「沒有
   呼叫端」之前必須同時 grep `internal/battle/` 與 `cmd/fd2/` 兩邊,只查
   `native_item_*.go` 內部看不到外部呼叫者。真正沒接的只有 **AI 側**:
   `applyNativeTargetItem` 全程依賴 `g.sel`/`g.nativeItemTargeting` 等玩家游標
   UI 狀態,`nativeAIThreeScorePlan`(見下方)在道具獲勝時目前刻意 `return nil,
   false` 完全讓給 legacy fallback,原因是重構這條已上線、玩家在用的路徑成
   AI 可呼叫的無 UI 版本,風險/工作量都明顯大於法術那條(法術那條的
   `ExecuteNativeCommand*` 系列本來就已經是無 UI 純函式,只有 `confirm()` 的
   switch 外殼是 UI 綁定,拆殼即可重用)。
3. ~~`ScoreNativeAI1567E`(道具評分)也沒接進 `NextAIPlan`~~ **✅ 已完成並測試
   (2026-08-15 續二)**——見下方「道具執行鏈已閉環」段落。
4. 剩餘機制未定的 3 個 kind(0x11/0x12/0x13)、跟結構完全不同的 kind0x17,可以留到
   之後——它們不影響「先把已有的 9+ 個 kind 接上 AI 決策」這個更高優先、更明確的
   工作。

**2026-08-15(續)三分數決策已接進 `NextAIPlan`,法術執行鏈已閉環**:
`native_ai_three_score_plan.go` 的 `nativeAIThreeScorePlan` 直接呼叫
`ScoreNativeAI14237`/`ScoreNativeAI1598A`/`ScoreNativeAI1567E` 三個既有評分函式,
再用 `SelectNativeAIThreeScoreWinner`(見上方「勝者選擇」段落)決定贏家,取代
`combat.go NextAIPlan` 原本只呼叫 `nativeAI14237Plan`(只有物理)的寫法。法術獲勝
時設定真正的 `plan.SpellID`(不再永遠 -1),`cmd/fd2/main.go` 的 `aiStep` 也已改為
在 `plan.SpellID>=0` 時呼叫新拆出的 `executeNativeCommandTarget`(從 `confirm()` 的
`nativeCommand0Targeting` switch 殼抽出的無 UI 版本,兩邊共用同一份邏輯)而不是
永遠呼叫 `AttackWithRNG`。`go build && go vet && go test ./...`(整個 remake 模組)
全綠,新增 `TestNextAIPlanThreeScoreFullProvenancePhysicalWinsWithNoSpellbook` 證明
「完整 production 形狀資料(含真正的 `NativeCommandBook`,先前 `nativeAI14237_apply_test.go`
的 fixture 從未設定這欄,實際上一直在悄悄退回 legacy fallback 而非真的測到 native
composer)下物理仍正確獲勝」。**尚未做的是實機驗證**(`FD2_SHOT_AI=1` 截圖確認 AI
真的選擇施法而非一律近戰)與**道具執行鏈**(見上方第 2 點)。

**2026-08-15(續二)道具執行鏈已閉環,task #98 三條執行鏈全部接完**:
新增 `internal/battle/native_ai_item_execute.go` 的 `ApplyNativeAIItemCommand`,
是 `cmd/fd2/native_item_panel_ui.go` 的 `applyNativeTargetItem` 的直接無 UI 版本
(同一套 RouteForType 級聯:HP/MP 回復、狀態清除回復、HIT/EV 增益、AP/DP 增益、
marker application、command damage 八種類型逐一嘗試;record/sync bookkeeping
逐行對照原函式重寫,不是重新設計)。`AIPlan` 新增 `ItemID`/`ItemSlot` 欄位
(比照既有 `SpellID: -1` 慣例,`ItemID: -1` 表示本計畫不用道具,7 個既有
`&AIPlan{...}` 建構點全部同步補上)。`nativeAIThreeScorePlan` 的
`NativeAICommandItem` 分支不再無條件 `return nil, false`,改成解析
`ScoreNativeAI1567E` 的獲勝 `(X,Y)` 格→`UnitAt`→設定 `ItemID`/`ItemSlot`
(找不到單位錨點的 AoE 型道具——原地施放無單位——仍 fail-closed 退回
legacy)。`cmd/fd2/main.go` 的 `aiStep` 新增道具分支呼叫
`ApplyNativeAIItemCommand`。**重要的安全修正**:道具/法術分支執行失敗時原本會
落到下面「一般攻擊」分支,但道具/治療類法術的目標經常是我方單位——加了
`plan.Target.Camp != u.Camp` 守衛,確保任何 fallback 都不會打到友軍。新增
`ApplyNativeAIItemCommand` 三個測試(HP 回復+消耗道具格成功案例、行列不合法
fail-closed、遷移類型 23 unsupported-但不報錯的 defer 案例),`go build/vet/test
./...`(整個 remake 模組)全綠。

這代表 task #98 三條執行鏈(物理/法術/道具)**全部接線完成並通過單元測試**,
真正的瓶頸從「反組譯規模龐大的獨立效果系統」變成「實機驗證」——目前只有
disassembly-grounded 單元測試(含用真正 production 形狀資料的整合測試)證明
正確性,還沒有用 `FD2_SHOT_AI=1` 截圖確認 AI 在真實戰鬥中會選擇施法/用道具
(2026-08-15 續嘗試過,原生 Windows 從未跑過這條 headless 驗證路徑——過去都是
靠已刪除的 `fd2-go-test-local` Docker+Xvfb image,重建它是獨立、有一定成本的
後續工作,不影響本次接線工作的正確性結論)。

**2026-08-15(續三)實際重建 Docker image 並實跑,誠實記錄結果——不是「完成」,
是「比之前更多的證據,但仍有明確缺口」**:用保存的
`tools/docker/fd2-go-test.Dockerfile` 重建 `fd2-go-test-local`(原 image 已刪除,
Dockerfile 還在),編出 Linux 版 `fd2-linux`,以 `xvfb-run` + 既有的
`FD2_CAMPAIGN=1 FD2_CAMP_PREP_BATTLE=battle_ch01 FD2_SHOT_AI=1` 組合(跟
2026-08-14 物理鏈驗證同一套指令)實跑:

- **確認的部分**:整條新管線(`nativeAIThreeScorePlan`→三個 `Score*` 呼叫→
  `SelectNativeAIThreeScoreWinner`→`aiStep` 分派)對著真正 production 資料
  (真實載入的 `NativeCommandBook`/`NativeItemEffectRows`/`NativeTerrainMoveCodes`
  等,不是單元測試的合成 fixture)完整跑過一輪,沒有 crash、沒有 panic,正確判定
  「三個管線都沒有候選」(`physicalPriority=0 spellMax=0 itemMax=0`)並退回移動
  近似——這是新增的、比之前更強的證據,證明接線在真正編譯的執行檔裡確實會被呼叫
  且不會炸掉,不只是 Go test 裡自我一致。
- **沒有確認的部分**:battle_ch01 這個場景本身沒能重現「AI 真的選擇施法/用道具」
  的畫面。原因追出來了(不是新 bug):(1) 這個 harness 的 `FD2_SHOT_TURN` 只是
  直接呼叫 `g.endTurn()` N 次來快轉觸發增援事件,**不會**真的模擬移動,所以
  無法讓敵人在多回合後真的接近玩家單位;(2) ch01 唯一的敵人「盜賊」載入時就在
  玩家單位的攻擊/施法範圍外,而盜賊本身也沒有法術/道具能力(mask 全 0,即使
  真的贴近了也只會考慮物理);(3) 寫了一個一次性掃描工具(已刪除,不是留在
  repo 裡的東西)找到 map7(`battle_ch08`)有法術能力(`NativeCommandMask` 非0)
  的敵人一開場就在玩家單位 3-4 格內,但 `battle_ch08` 這個節點透過
  `FD2_CAMP_PREP_BATTLE` 完全沒進到可互動的 native 戰場狀態(截圖幀數開到 1500
  仍然连一次 `aiStep` 都沒觸發)——這跟本文件 task 清單裡「調查 ch02-25/28-30
  為何連不上 harness 的 interactive native state」是同一類、先前就記錄過的
  harness 限制,不是這次接線造成的新問題。
- **保留下來的工具**:`internal/battle/native_ai_three_score_plan.go` 新增
  `nativeAIDebugf`(`FD2_AI_DEBUG=1` 才輸出,平常完全靜默),把三個管線各自的
  分數、以及 gate 在哪個檢查點失敗印出來——這是這輪診斷「native=false 到底是
  資料缺失還是真的沒候選」花了不少時間才分清楚後,決定留下來給下一次驗證用的,
  仿照 `main.go` 既有一堆 `FD2_SHOT_*` debug hook 的慣例。

**誠實結論**:task #98 的三條執行鏈程式碼完成、單元測試通過、且**這次追加了
一次成功的真機執行**(證明管線在真正的編譯執行檔裡跑得動),但**沒有拿到
「AI 真的選擇施法/用道具」這個畫面**——這需要要嘛寫腳本模擬多回合玩家操作
撐過 harness 限制,要嘛另外構造/找到一個施法者敵人一開場就在射程內的合成
戰場。這是有明確成本的後續工作,不是「順手就能補上」的小事,留給使用者
決定要不要繼續投入。

**2026-08-15(續四)深挖 ch08 harness 連不上的根因,釐清這不是接線 bug**:
- `FD2_CAMP_NODE=battle_ch08`(走完整的 `g.enterNode()` 節點分派)截圖出來是一張
  **正確算繪、乾淨的隊伍部署畫面**(地圖、建物、寶箱、游標都對,玩家隊伍聚在
  出生點,尚未各自展開到戰術位置)——證明 harness 本身、地圖算繪都沒問題。
> ⛔ **[remake 證據排除]**(2026-09-04):本行自陳這條 remake 捷徑是「ch01 驗證一路
> 在用的」——依現行判準,凡以它為基礎的 AI 結論一律視為未驗證,需 DOSBox-X 原版重驗。
>
> **2026-09-04(續)結案為 void:無可重驗對象。** 本段描述的是 remake harness 自己的
> 畫面損壞 bug(`FD2_CAMP_PREP_BATTLE` 與 `enterNode()` 重跑節點設定的交互),
> 通篇沒有對原版行為的任何宣稱。remake 已移除,該 bug 連同程式碼一起消失,
> **不再列入「待原版重驗」清單**。見 `remake_excluded_claims.json` 的 `void_subject_removed`。

- `FD2_CAMP_PREP_BATTLE=battle_ch08`(ch01 驗證一路在用的捷徑,`resetBattle()`
  之後仍會被隨後的 `g.enterNode()` 對「當時 `g.camp.Cur`」重跑一次節點設定)
  截圖出來卻是**明顯損壞的畫面**(紅色色塊、單位貼圖比例錯亂/被裁切)——這是
  一個真的 bug,只是恰好在 ch01 這張最簡單的地圖上沒炸出來。已用 spawn_task
  另外記錄、不在本次範圍內修。
- 兩邊都沒有任何 `aiStep`/AI決策 log,因為**兩者都停在部署畫面**,沒有進到
  戰鬥回合——這正好對上任務清單本身的狀態:task #67「Ch01 戰鬥機制」
  in_progress,task #68 起的 ch02+`「戰鬥+商店/教會/城鎮/整備」`全部
  `[pending]`。換句話說:**ch08 連不上互動 native 狀態,不是 harness 缺陷,
  是 ch08 的部署→開戰這段流程本身還沒被驗證/接上 headless 操作腳本**——這其實
  是 task #74 未來要做的工作範圍,不是這次三條 AI 執行鏈接線可以順手解決的事。

**最終決定(這次不繼續追,誠實記錄邊界)**:再往下走(寫腳本模擬部署確認+
開戰,或另開一個合成場景的 debug hook)屬於明顯更大、超出「接線 AI 決策」
範圍的工作。task #98 停在:**三條執行鏈程式碼完成、單元測試(含 disassembly
-grounded 的決策邏輯與用 production 形狀資料的整合測試)全部通過、且已有一次
成功的真機執行證明管線本身不會 crash 且對真實資料判斷正確**;但**沒有拿到
「AI 選擇施法/用道具」的實機畫面**,這需要先做完 ch02+ 的部署/開戰腳本化
(task #74 系列)才有辦法達成,不建議為了這一個驗證畫面去搶跑那塊工作。

**2026-08-15 補充判斷:物理執行鏈可能不需要額外工程**——`0x3A6A2` 反組譯出的
序列(重置 pathing 原點→移動→讀 target index→再重置 pathing 原點)本身沒有
獨立的「套用傷害」opcode,而是結構上等同已知的 `0x1548E` 移動+攻擊呈現流程
(同一個「移到目標旁邊、resolve 目標、交給共用近戰呈現」骨架,原版靠這個
共用流程本身觸發傷害計算,不是 `0x3A6A2` 自己另外算)。這正是這個 session
已經接進 `NextAIPlan`/`aiStep` 的 Path+Target→walk→`AttackWithRNG` 流程
在做的事——中度信心判斷(未在 0x3A6A2 之後繼續往下追出明確的傷害計算
呼叫點,不是 100% 端到端證實),但足以認為**物理執行鏈目前已被既有接線
覆蓋,不需要再花額外反組譯工程**,跟法術/道具那兩條真的還沒接執行效果的
情況不同。task #98 的剩餘範圍實際上只有法術+道具兩條執行鏈,不是三條。

**這次反組譯把 `0x14EF0` 的決策骨架整個閉合了**，是目前為止對這一塊最完整的
一次考證。**仍未閉合、也是啟動完整實作前最後的缺口**：
- 物理分支的地形百分比表數值已確認(見上一節,`terrain.go` 既有 + 三個獨立來源交叉驗證)，
  但 `0x14237` composer 本身(候選格→目標枚舉→評分→選擇全部串起來)仍未組成一個可呼叫的
  Go 函式——這是接線工程,不是資料問題。
- 法術/道具**執行**(不是評分)本身分別是另外兩條獨立、目前完全沒追過的效果鏈
  (法術傷害/回復/狀態套用、道具消耗與效果)，比評分本身的量級更大。
- `[0x53C2F]`、`0x73A7A`、`0x40936` 三個新出現的 raw 符號都還沒有命名或
  接入型別化 Go。

### 法術命令評分：`0x15B77`

Docker Capstone 直接讀到 `0x15a1e..0x15b76` 的 caller：它枚舉 bounded candidate
array，呼叫 `0x14818` 建立 target data，接著以 `(candidate, target, command)` 呼叫
`0x15b77`，回傳值和既有 best score 比較；平手時再比較 candidate record word，最後寫入
`0x53c23/0x53c27/0x53c2b/0x53c2f`。這是目前唯一足夠的 AI-like score topology，不能把
caller 自動命名為完整 enemy-turn dispatcher。

2026-07-29 重新核對 `0x1C269` 與選中結果執行端 `0x15311` 後，撤回舊
「`0x1598A` 只保留 command ID `>=0x10`，再由 caller 減 `0x10`」斷言。
`0x1C269` 直接輸出 `unit+0x1A..+0x1E` 中每個 set bit 的 `0..39`
索引；`0x1598A` 對每個索引直接呼叫 `0x4E516`，並把同一索引直接傳給
`0x15B77`，沒有減法。`0x15311` 也直接以 `[0x53C2F]` 查 `0x4E516`
及索引效果表。`command-0x10` 只屬於另一條 `0x1567E` 物品內 command
路徑，兩者不可再混用。完整直接指令保存於
[`fd2_ai_command_index_disasm.txt`](../data/fd2_ai_command_index_disasm.txt)。

`0x15b77` 本身目前可確認：command `<0x0d` 逐目標讀 runtime record `+0x40`，基礎分數
為 8，若 spell value 大於 record value 則為 `0x18`；record `+8==0` 時以 native
FPU path 對分數乘 `1.5` 並轉回整數。command `0x0d..0x10` 走 recovery 分支，讀
current/max HP 與 record `+0x34 bit0`；`0x14..0x16` 掃 raw `+0x25/+0x26/+0x27`
並呼叫 `0x1c269`。這些是 raw score branches，不足以替欄位命名成攻擊、治療或狀態，
也尚未證明它就是完整 AI 回合入口。

重製端新增 `battle.NativeAIScoringRecords`，只建立上述評分與 phase gate
所需的 detached `0x50`-byte 原始快照。它要求每筆單位已有 native map
presentation、`battle_fig`、`+5`、`+6`、`+34..+36`、identity、race/class
與 inventory provenance；任何一欄缺失就拒絕整批，不以 normalized
`X/Y`、`Acted`、`Camp` 或 status 補值。map0 真實匯出資產已通過
`坐標(1,3)、+5=0、+6=0、+34=0、HP=28` anchor regression。後續候選、
群組評分、單位最大分數與三遍門檻已由下述具型別切片接續；它仍沒有接進
`NextAIPlan` 或執行交易。

同一條輸入已再接至
`battle.NativeAIScoredCommandCandidateGroups`：依 command record `+3`
經 `0x4E040→0x14B16` 產生穩定逐列目的格，再依 `+4` 呼叫
`0x14818` 的等價 raw target filter。selector 非零時沿用 command
target code；selector 為零時，command code 0 改成1、其他值改成0，
與 `0x15B40..0x15B5C` 分支一致。目標保持 runtime record index 順序，
`+5 bit0` 排除 inactive，沒有目標的目的格不輸出。這個 caller 不自行
執行物理路徑的 `0x145CD/0x146D1` roster blocker pass，而要求 caller
提供當時的 exact grid flags。

map0 真實匯出 roster、`spells.json` command #0、原版 movement-cost row 0
及 map raw flags 的 Docker regression，已確認 identity 103 的 enemy actor
能在目的格 `(23,14)` 產生 raw ally target index。其後
`ScoreNativeAIScoredCommandGroups` 與 `ScoreNativeAI1598A` 已呼叫各分支
評分並保存正分最佳命令；仍不執行或呈現動作。

同一輪 caller scan 找到一個較可信的 dispatch boundary：`0x14ef0` 有六個 direct callers
（`0x13af5`、`0x13b2d`、`0x13b4d`、`0x13b6d`、`0x13c24`、`0x13dec`）。其 body 先呼叫
`0x14237`、`0x1598a`、`0x1567e`，再依 raw score/global state 分派至 `0x1548e`、
`0x15311` 或 `0x15055`。這足以取代舊 `0x15140` 作為下一輪追蹤起點，但目前仍只稱
**candidate dispatch boundary**：六個 callers 的 turn/camp 語意、`0x14237` 與
其後執行分支仍未閉合。`0x14237` 的物理 producer 與 `0x1567e` 的
item-command producer 已由後述具型別解碼器分別閉合；不得再把靜態 producer
缺口與尚缺的動態 phase／執行交易混為一談。

更上游的 `0x13a9f` 是目前可重現的 unit-action dispatcher：它以 `unit index` 建立
`0x50`-byte record，先檢查 raw `+5` 的 `0x05` bits，再取 `record+0x34 & 0x0f`。
command nibble `0/1/2/3/5/10` 會呼叫 `0x14ef0`，`4`/`7`/`9`/`11` 則各走不同
movement／portrait／score fallback；`0x0b` 分支直接呼叫 `0x1598a`，在 score gate
後選 `0x15311` 或 `0x1548e`。這是「record command→action helper」的已證實邊界，
但尚不能把 nibble 值命名成攻擊、移動或 AI 陣營語意。

`0x1d80b`、`0x1d8ba`、`0x1d988` 是目前確認的上層掃描 callers：三段都以
`[0x3beb]` 遍歷 `0x50`-byte records，先檢查 raw `+6`、`+5 & 0x81`、`+0x26`，再分別
呼叫 `0x13a9f` 或 `0x1598a→0x1567e→0x13a9f`。每筆之後依 `[0x51a8f]` function table
與 `[0x53c03]` 章節戰場事件 handler dispatch，並受 `[0x53ecc]`
pending 碼控制。這證明它們是 unit-scan/action-loop 的 caller boundary；
`+6` 的 raw camp code 已由 constructor 與 target-code 消費端閉合；兩張
表與 pending 碼也不得再標成未知語意。仍未知的是兩遍敵軍掃描的玩法理由。

更高一層的 callsite 也已固定：`0x1a4eb` 在 `0x1a813(1) → 0x1a866(1)` 後呼叫
`0x1a7bd → 0x1d80b → 0x1a7f1`；另一段 `0x1a58f` 在 `0x1a813(0) → 0x1a866(0)`
後呼叫 `0x1a7bd → 0x1d8ba → 0x1a7f1`。這只證明兩個 phase-specific unit-scan
callsites 位於同一場景流程。`0x1a813/0x1a866` 必須使用 raw provenance，
不能用缺少 `NativeRecordByte6` 的 normalized `Camp` 代替；selector 0／1
在這裡只證實是 `sub_1A813/sub_1A866` 的 raw camp filter。尤其 raw camp0
handler 在 `0x1A58F` 敵軍 AI 前執行，不能僅憑數值把兩者改名成敵軍／友軍
陣營碼；舊稱已撤回。

### 物理選擇結果執行：`0x1548E`

`0x1548E..0x1567D` 只有兩個直接呼叫點 `0x13E39` 與 `0x14F9B`。它不是
路徑或目標評分入口，而是消費既有選擇結果：

- 第一參數是 actor index；第二參數原樣轉交 `0x14B78`，作為零／非零
  單位分組選擇值。
- `0x154B5..0x154C6` 將
  `(0x53C43,0x53C47,actor,callerArg)` 傳給 `0x14B78`。
- 之後以 `0x53C4B` 作為 target index，`0x1F04A` 寫 actor 面向；
  `0x1F0DC` 檢查兩單位 raw 關係，並依 `0x53AF9` 走地圖呈現鏈或
  `0x28A6C(actor,target)` 戰鬥演出鏈。
- 收尾依序呼叫 `0x134E4`、`0x1B6B7`、`0x1DB65`、
  `0x1AA1D`、`0x1E292`，最後固定回傳 1。

全函式沒有呼叫舊筆記所稱的 `0x4EE40` 或 `0x4F355`。因此目前可證實的是
「已選結果的移動／攻擊呈現與收尾」，不是「產生可達路徑」。
合法 IDA 9.4 另確認其函式邊界與兩個 callers，結果與 Capstone 一致。

### 實際尋路與無攻擊備援：`0x4E1A6`／`0x14B78`／`0x14121`／`0x13E9C`

舊文件把 `0x15192` 當成「接近最近敵人」分支是錯誤斷言；該位址位於
`0x15055` 的施法演出流程。2026-07-29 重新由 `0x13A9F` 的
`0x14EF0` 失敗分支往下追，取得真正流程：

1. `0x14B78(destinationX,destinationY,actor,selector)` 依 actor
   `record+0x20` 選 `0x4E555` 成本列；`0x1F183` 成立時改用列 19，
   actor `record+8==0x1C` 時改用列 1。
   **2026-08-14 補完(Ghidra 反組譯「新版」基準版 FD2.EXE，逐行核對)**：
   `0x14B78` 本身的選擇順序已逐行確認 —— 預設 `ESI=record+0x20`(class)；
   呼叫 `0x1F183(actor)` 非零則 `ESI=0x13`(列19)；接著**不論上一步結果**
   再檢查 `record+8==0x1C`，成立則 `ESI=1`(列1)——**列1 蓋過列19**，
   兩者同時成立時以列1為準。`0x1F183` 本身也已完整反組譯：
   `record = unitArrayBase(0x53a45) + actorIndex*0x50`；
   `if record+0x7==0x1C: return false`；
   `elif record+0x20==0x13: return true`(class 0x13，這個分支跟預設
   selector 本來就會選到列19，屬於 no-op 情形)；
   `elif record+0x1F(race) in {4,5}: return true`；`else: return false`。
   已寫入 `remake/internal/battle/move.go` 的 `nativeMovementRow19Predicate`
   +`nativeMoveCost`，`record+0x1f/+0x20` 對應既有 `NativeRecordRace`/
   `ClassID`；`record+7` 這個閘門 byte 是全新欄位，目前沒有任何 map
   的 units.json 匯出管線填過它，因此故意不建模、不猜測——只會讓少數
   本該被 `record+7==0x1C` 抑制的單位多套用一次列19，範圍比先前完全
   不套用列19還要窄，符合本專案 fail-closed 原則。
2. 它先以 actor `record+0x3B` 為剩餘步數，呼叫
   `0x4E1A6` mode 0 直接尋路。方向碼由 `0x13488` 的四個執行分支證實：
   `0=下、1=左、2=上、3=右`；搜尋鄰居順序固定為右、左、下、上。
3. `0x4E1A6` 與可達格使用同一個 FDFIELD tile 高位分組 →
   FDSHAP `+1` 移動代碼 → 20-byte cost row。mode 0 只接受剩餘步數
   嚴格改善的重訪；`0x40` 不可進入，`0x80` 進入後剩餘步數歸零。
   到達目的地時保存方向陣列；較短路徑取代較長路徑。
4. 直接尋路失敗時，`0x14B78` 以 budget 28、mode 1 再找一次。
   mode 1 在剩餘步數相同時，只有方向連續段數更多才接受重訪。
   若取得方向陣列，再沿該陣列選出 actor 原始移動 budget 內最後仍可達的格。
5. 它重新列出所有合法落點，以 Manhattan 距離最小者優先；同距離時，
   再選 `abs(abs(dx)-abs(dy))` 較小者，完全同分保留
   `0x14B16` 逐列順序。最後再用 mode 0 產生正式方向陣列，交
   `0x13488(actor,path,length)` 逐格執行。

`0x13A9F` 的一般 mode 0 在 `0x14EF0` 沒有候選時，先呼 `0x14121`：
它以 `0x145CD` 標出另一 selector 組的 `0x40` 中心格，再以 budget 28、
`0x4E1A6` mode 2 搜索。mode 2 可以進入 `0x40` 格，記住其座標並繼續
遍歷；後出現的合法 blocked 格會覆寫先前結果。找到座標後再交 `0x14B78`
移向該單位。

若 `0x14121` 仍失敗，才呼 `0x13E9C`。它掃 runtime record 順序，
selector 0 選 `record+6!=0`，selector 非零選 `record+6==0`，以
Manhattan 距離選最近座標，完全同距離保留先出現者，再交 `0x14B78`。
這段本身沒有 inactive/dead gate，因此不得把它擴張成「最近存活敵人」。

重製端新增 `NativePathDirections`、`NativePathBlockedCoordinate`、
`SelectNativeMovementDestination` 與
`SelectNativeNearestOppositeCoordinate` 保存上述只接受原始資料的契約；
尚未直接取代 `NextAIPlan`，避免在上層 mode／record 欄位未完整接線前冒稱
整個敵方回合已與原版相同。

**2026-08-14 補完**：mode 0 這整段 fallback(`0x14121→0x13E9C→0x13FD4`)
已組成 `battle.ApplyNativeAIMovementFallback` 並接進 `aiActUnit`(見
`native_ai_movement_fallback.go`)——這是**只有「原地無立即行動時該往哪移動」
這一小塊**,不是完整 `NextAIPlan`;「原地是否已有可攻擊目標」的 `0x14EF0`
三分數決策，以及 mode 0 以外其餘 8+ 個 mode 分支，仍是重製近似，尚未替換。
`0x14121` 找到的座標會餵給 `0x14B78` 做正常尋路移動(不是直接落點)這件事，
本次用 Ghidra 反組譯 `0x14121` 本體重新逐行核對過，跟本節既有敘述一致。

**訂正(同一天稍晚)**：最初接線時漏查了單位自己的 mode 值就套用 mode 0 邏輯，
是真的 bug，已修正——`ApplyNativeAIMovementFallback` 現在會先檢查
`record+0x34&0xf`，只有等於 `NativeAIDispatchMode0`(0)才執行；其餘 mode 的
單位 fail-closed 回傳 `ok=false`，退回舊近似。33 張地圖實際統計 mode 分布：
0=1063、1=34、2=535、3=78、4=34、5=41、7=4、8=90、9=2、10=6 (共 1887 筆)——
mode 0 雖是多數(56%)，但 mode 2 也佔了 28%，不能省略這個檢查。

> 戰棋上敵方(與友軍 NPC)每回合怎麼決定「移動到哪、打誰、打不打」。
> 舊第 3 輪筆記曾把 `0x15140` 記為 AI 主決策函式；該地址目前已被 canonical recheck 撤回，單位陣列 `[0x3A45]`、
> 每單位 0x50 byte、數量 `[0x3BEB]`(見 `03-…` 單位結構)。

## 已刪除的舊斷言

舊版文件曾宣稱敵方與 NPC 必然共用同一完整決策函式，並把 `0x4EE40`、
`0x4F355`、`0x15140`、`0x15356` 串成「逐落點×逐目標」、傷害小於等於 2
就放棄、擊殺分數加倍、地形攻防修正等完整公式。這些敘述缺少可重現 caller
與欄位契約，且其中關鍵入口已被直接掃描否定，因此舊位址與函式鏈不再保留。
其中「門檻、擊殺優先、地形修正」現已在不同的真正入口 `0x14237` 重新取得
直接指令證據；只能引用上節的新位址與精確比較規則。

## 施法命令也在 AI 評分與執行路徑內（2026-07-20 direct disasm）

先前把 `0x154D1` 誤當施法入口的判讀已撤回；真正的證據在 AI 命令枚舉與執行函式：

- `0x1567E` 開始的函式逐一掃描庫存槽。`record+0x0B+2*slot` 是 item ID，
  `0x4E56C(item)+0x10` 才是 command byte；row `+0x0D==0` 直接略過。
  `command<=0x0F` 走 `0x14818`，`command>0x0F` 在
  `0x1579A–0x157B5` 做 `command-0x10` 並呼叫 `0x149F8` 建候選。
  兩支都交給 `0x15880` 評分，並不進 `0x15B77`；後者只屬
  `0x1598A` 的另一條命令遮罩路徑。
- `[0x53C3F]` 保存勝出的庫存槽索引，不是 command byte。`0x1507C`
  將它交給 `0x1B722(unit,slot)` 讀出 item，`0x150C2` 才從 item row
  `+0x10` 取得 command；`command>=0x10` 再呼叫 `0x149F8`。
- 因此原版確有可導向施法演出的 item-command 路徑，但不可將整條
  `0x1567E` 統稱為施法決策，也不可與 `0x1598A→0x15B77` 的 ranking 合併。
- `ScoreNativeAIItemCommandTargets` 已將 `0x15880` 保存成原始欄位 adapter：
  type5／0x0D 依 current HP `<=max/3` 得8、否則 `<=max/2` 得3，
  `+0x34 bit7` 再乘3；type0x14／0x15 由 row `+0x0E` 經 `0x4E516`
  取 command word，type0x18 直接用 row word，target HP 小於等於門檻得
  0x12，否則8。其他 type 回零；不為 type 或 bit 指派效果名稱。
- `ScoreNativeAI1567E` 已閉合完整數值 producer。它以 `0x1B8A6` 的
  bit7-clear count 掃 raw slots `0..count-1`，依 slot item row 建
  row-major 目的地；低 command 以第二個 `0x14818` 產生 roster-ordered
  targets，高 command 以 `0x149F8` 從 actor 朝目的地走
  `command-0x10` 步且固定只收 raw camp0。每個候選交 `0x15880`，
  只有分數嚴格大於目前最大值才保存 `(score,x,y,slot)`。
- map0 真實 roster／constructor 後 `+2 & 0x1F` 基底與原始 item79 row 的交叉 fixture固定
  actor index23 得 score8、目的地 `(19,15)`、raw slot0。fixture 只替 actor
  注入已追蹤 item79 以關閉 producer；不宣稱一般玩家 map0 原本持有該物品。
- remake 已先把 editable item 23-byte row 的 K4（raw byte `0x11`）資料化為 `AICommandSpell`（command `>=0x10` → `spell_id=command-0x10`）；這只建立 command inventory，不提前猜測 AI ranking、可用條件或治療目標。

上述勘誤的直接指令、執行端消費者與 inventory bound helper 已保存於
`docs/data/fd2_ai_item_preselection_disasm.txt`；`0x14818/0x149F8/0x14B16`
完整候選窗口另存 `docs/data/fd2_ai_item_candidate_disasm.txt`。兩者皆綁定
參考 FD2.EXE 雜湊。

2026-07-29 availability 勘誤：`NativeAvailableAIScoredCommandIDs` 重用
`0x1598A` 的 `unit+0x27==0` gate、40-bit command mask、36-entry
command book 與 `record+5 <= unit+0x44` MP gate，保留已知範圍
`0..35` 的原始 set-bit 索引，包含低於 `0x10` 的值。它不接 target、
score、Cast 或 effect；36..39 仍因沒有已驗證 command record 而省略。

`0x15B77` 的 spell-target 評分分支也已直接反組譯（呼叫點 `0x15AD8`）：

- spell id `0..12` 走攻擊術分支，逐一掃候選目標；依目標 HP 與施法者法術值累加基本／高優先分數（可見常數 `8` 與 `0x18`）。
- spell id `13..16` 走治療／恢復分支，改掃己方候選；Hex-Rays `0x15c30..0x15c4b` 顯示 `current HP < max/3` 給 raw score 8，否則 `< max/2` 給 3，否則 0，且 record `+0x34` bit0 會把該分數乘 2。這是 score gate，不命名 bit0 或效果。
- spell id `17..19` 進入另一個 raw scoring helper；`20/21/26/27` 讀取 `+0x25/+0x26` flag bytes，ID22 先 gate `+0x27` 再呼 `0x1C269`。這些是 call/score topology，不足以命名成增益、毒麻或其他 gameplay status。
- 依 spawn constructor `0x10f6b..0x10fa5` 的 direct trace，FDFIELD b13..b16 的 `initial_command_mask` 只複製到 runtime `unit+0x1a..+0x1d`，而 `unit+0x22..+0x27` 另由 constructor 清零。前者是 runtime 五位元組 command bitset 的初始四位元組；後者目前只能稱為 raw transient／modifier bytes。雖然 writer paths 會讀寫其中幾個欄位，derived-stat/property/status 名稱仍未由完整 equipment recompute、presentation 與 caller evidence 證實；不能把它們命名成 AP/DP/HIT 或 M1–M5 spell bitfield。AI 仍依 spell family 選目標，individual command ID 與後續 modifier writer 待另行接線。

2026-07-29 地圖輸入勘誤與評分橋接：

- 先前文件雖已證實 FDFIELD b13..b16 是命令遮罩來源，但 33 張重製地圖的
  1887 個單位實際全都缺少 `initial_command_mask`。這不是只有文件漏寫，
  而是正式資產管線未接。同步器現已補齊；263 筆非零遮罩中，有 261 筆同時
  通過原始命令表與 MP 成本閘門。
- `0x10d7f..0x1100c` 直接指令另證實建構器的最大 MP：高階分支是
  `high[+4]*level`，低階分支是
  `u16(lower[+5])+lower_aux[+8]*(level-1)`，並寫入 `+0x44/+0x46`。
  1885 筆地圖單位已取得 `native_record_word46`；map32 的兩筆未覆蓋
  selector 維持缺值。`NativeAIScoringRecords` 現要求 `word42/word46`
  完整來源，不能以正規化 HP/MP 猜回原始記錄。
- `ScoreNativeAIScoredCommandGroups` 已依 `0x15B77` 的完整命令 ID 家族，
  將每個 `0x1598A` 目的地／目標群組送入既有攻擊、恢復、旗標或零分支。
  map0 真實資產的 command0 在 `(23,14)` 命中四個友軍，各得24、合計96。
  IDs10..12 缺呼叫者提供的 `0x1F183` 閘門時拒絕評分。
- 尚未閉合的是零分候選時保存命令字的區域變數初值。`[0x53C23]` 的數值
  最大值由零開始，因此可安全重現數值比較；但在確認該區域變數前，不能把
  零分結果宣稱為原版選中的命令，也不能接入正式行動執行。
- `ScoreNativeAI1598A` 現已把命令可用性、候選群組與群組評分收斂成單位級
  數值結果；只在分數大於零時輸出可證實的勝者。它會交叉檢查 actor 的命令
  遮罩及目前 MP 必須與 detached record 一致。map0 的實際 roster／地圖輸入
  加入已證實 command0 後，固定得到 `(23,14)`、分數96；全零分 fixture
  保留 `MaxScore=0` 且不創造命令。
- `BuildNativeAIPhaseDiagnosticPlan` 現依原版 `0x1D8BA` 順序，對每筆合格
  selector-zero 記錄先執行 `ScoreNativeAI1598A`、再執行
  `ScoreNativeAI1567E`，並將96／8這類數值分別送入 `[0x53C23]`／
  `[0x53C33]` 的 signed `>=6` 三遍掃描計畫。輸入必須逐單位完整且唯一，
  函式不改寫戰鬥狀態。
- map0 測試是修改狀態的 E0 交叉夾具：沿用真實名冊、構成格基底、地形、命令
  與物品資料，但排除其他 selector-zero 記錄，並替 index23 注入 command0
  與 item79；它不能證明一般玩家 map0 的實際敵方決策。
- 先前把 FDFIELD 封存 `+2` 直接命名成 `native_target_flags` 是錯誤斷言。
  33 張 map 現均逐位元組同步為 `native_composition_event_bytes`；原版
  合法 IDA Pro 9.4 已先確認函式邊界、呼叫者與 writer／consumer，
  Capstone 再逐指令交叉驗證：`0x4DBFC` 先遮成 low5，
  caller-specific `0x145CD` 才依 roster 加
  `0x40/0x80`。map19 有1600格、7格非零；真實 unit55（identity92、遮罩
  `[4,0,0,8,0]`、MP288）在完整原始輸入下兩個 producer 都得到零分，
  且不創造勝者。這是 E0 負向資產錨點，不是原版動態回合 trace。
- 合法 IDA Pro 9.4 已確認 `0x1598A` 與 `0x1567E` 在每次目的格／目標候選
  使用後呼叫 `0x4DBFC`，兩者都不呼叫 `0x145CD`。因此這兩個預選 producer
  使用每次重建的低五位（low5）基底，不持有跨單位執行期旗標；直接指令見
  [`fd2_ai_composition_flag_lifetime_disasm.txt`](../data/fd2_ai_composition_flag_lifetime_disasm.txt)。
- 這個橋只涵蓋無副作用的分數與門檻，沒有呼叫 `0x13A9F`、逐單位事件／章節
  回呼或 `[0x53ECC]` 提早離開，因此不是正式敵方回合執行器。

## 2026-08-20：完整回合主鏈收尾——native end-turn 的 caller／team predicate／AI completion timing（回應 worklist L145/L210/L304/L1038）

> **方法**：Ghidra headless（`analyzeHeadless -readOnly -noanalysis`，`FD2Analysis3` 專案，
> `ProbeGlobalEvents58to89.java`／`ProbeCheckHash.java` 等一次性 probe 腳本存於
> `FD2_ghidra_projects/`）直接對已完整反組譯的 976-fn 資料庫取
> `FUN_0001a30b`／`FUN_00013565`／`FUN_00016f55`／`FUN_0001728c` 的
> decompile／disasm，逐行核對；FDTXT 字串以既有 `tools/decode_text.py` 對
> `extracted/raw/FDTXT/FDTXT_000.bin` + `extracted/raw/FDOTHER/FDOTHER_004.bin`
> 字型渲染成圖片後目視核對，不是猜測。
>
> **版本核對**：`FD2Analysis3` 實際分析的檔案 MD5 為 `a6e341a8decc6ebf7f4872076d9cf161`
> （`ProbeCheckHash.java` 讀出），與 `docs/data/fd2-reference-files.json` 記載的目前基準
> 「新版」`FD2.EXE`（`33464c81e6a364fd0660141139aa8e6e`，同為 509158 bytes）**不完全相同**——
> 逐 byte `cmp -l` 只有兩處差異：檔案位移 `279901`(`0x44575`, `0x74→0xeb`) 與
> `305228`(`0x4a80c`, `0x0d→0x12`)，皆為單一 opcode 級別的就地修改（`je→jmp` 型態，疑似
> no-CD／簡易 patch），與本節引用的所有位址（`0x1a30b`/`0x13565`/`0x16f55`/`0x1728c`
> 及事件 handler 區段 `0x354fe..0x36100`）都相隔極遠，不影響本節結論；仍如實記錄此落差，
> 供未來若在 `0x44575`/`0x4a80c` 附近做 RE 時提高警覺。

前面各節已個別關閉「評分」（`0x14EF0` 三分數決策）與「執行」（物理／法術／道具三條
執行鏈皆已接進 `NextAIPlan`/`aiStep`），但「一個 AI 單位的回合怎麼被觸發、又怎麼結束」
一直缺一個貫穿的主鏈證據——這正是 worklist 稽核索引 L1038（「native end-turn 完整
caller／team predicate／AI completion timing」）、L145（「turn/camp 與 runtime
execution」）、L210（「回合 orchestration」）與 L304（AI 完整權重的觸發時機）共同指向的
缺口。本節直接反組譯補上，取代先前「兩遍敵軍掃描的玩法理由未知」的開放狀態。

### 完整主鏈（玩家輸入 → team predicate → 回合 orchestrator → 敵我 AI 掃描 → 回合計數）

```
0x117E7 主戰鬥迴圈讀鍵
  │ Enter/Space(scancode 0x1c/0x39)且游標下有己方(camp2)可用單位(+5&0x80==0, +0x26==0)
  ├─► 0x18890 指令環(既有：doc13/doc25 §6「跑戰鬥」)
  │        …單位完成行動後，收尾 0x13512 設 record+5 bit7(已知：標記已行動)
  ├─► 0x1E292、章節 handler 表 [0x53c03*4+0x51b19]()（既有：doc25 §3 全 30 章 handler）
  └─► 0x13565()  ★ team predicate（本節新證）
           │ 逐筆掃 record[0..count) ：若存在任一 record+6=='\x02'(camp2/己方)
           │ 且 (record+5 & 0x81)==0(未行動且非死亡/非另一 raw bit) 且 record+0x26==0(無麻痺類 transient)
           │ → bVar2=false(隊伍未完成)
           ├─ bVar2==true(己方無人再需要行動) → [0x51aac]=0;[0x51a83]=0; 0x1A30B(); [0x51a83]=1;[0x51aac]=1
           └─ bVar2==false → 直接返回，回主迴圈等下一次輸入
  └─► 若 [0x51A8F]!=0xFF：呼叫 [0x51A8F*4+0x51b91]()（既有：doc25 §6.2 格子事件全域 dispatch），再清 0xFF
```

`0x13565` 是原生「己方是否已無人可行動」的精確判定式：它只看 `record+6==2`（doc11 既有
「敵0／友1／己2」raw camp 定義）的單位，`+5&0x81` 沿用既有的 bit7(已行動)／bit0 rawgate，
`+0x26` 是 doc56 已定名的「麻痺」transient byte（command21/27 綁定）。因此「team predicate」
字面上就是「己方陣營裡還有沒有一個活著、未行動、未被麻痺的單位」；只要答案是否定，
`0x117E7` 立刻呼叫 `0x1A30B` 進入下一輪。

### `0x1A30B`：回合 orchestrator 與兩個 AI 掃描的精確交織順序（補完 doc56 既有骨架）

doc56（2026-08-14）已完整反組譯 `0x1A30B`（size 1202）本體並列出七步序列（own regen→
selector1→兩次勝負檢查→selector0→兩次勝負檢查(內含 `INC [0x53BEF]`)→回合跑馬燈→
selector2），本節這次逐行反組譯進一步確認：doc56 所稱的「兩次勝負條件檢查」**分別內嵌
的正是 doc11 本文早已各自獨立證實的兩個敵我 AI 掃描函式**，寫成一條連續呼叫鏈（非
recheck 前的推測）：

```
0x1A30B():
  1. own-camp(record+6==2) 自然回血掃描：+0x25==0 且 +0x26==0 才 +0x40 = min(+0x40++0x42/5, +0x42)
     （= doc11 已知 0x13FD4 同一公式，這裡是獨立內嵌版本，套用對象是玩家隊伍不是 AI 單位）
  2. 0x11CAC(重繪) → 0x1A813(1) → 0x1A866(1, 六個 transient byte tick，見 doc56)
  3. if [0x53ECC]==0:
       0x1A7BD(resource setup) → 0x1D80B() ★友軍(camp1) AI 單遍掃描(doc11 已閉合) → 0x1A7F1(resource release)
       if [0x53ECC]==0:
         （章節 BGM 表切換等既有步驟）
         0x11CAC() → 0x1A813(0) → 0x1A866(0)
         if [0x53ECC]==0:
           0x25977() → 0x1A7BD() → 0x1D8BA() ★敵軍(camp0) AI 預選+第二遍掃描(doc11 已閉合) → 0x1A7F1()
           if [0x53ECC]==0:
             [0x53BEF] += 1   ★★★ 回合計數器遞增——AI completion timing ★★★
             （章節 BGM 表切換）→ 9 幀 + 4 幀回合數字跑馬燈(0x15F0E/0x187D6/0x15E71)
             → 0x11CAC() → 0x1A813(2) → 0x1A866(2) → 0x12D7B() → 0x4E381()
```

這把「AI completion timing」釘死成一句可驗證的話：**`[0x53BEF]`（回合數）只在
`0x1D80B`（友軍單遍）與 `0x1D8BA`（敵軍預選＋第二遍）兩個掃描都跑完、且沿途任何一次
`[0x53ECC]` pending 檢查都維持 0（沒有任何全域事件／章節 handler 中途插隊）時才會遞增**；
只要其中一次掃描或其後的章節 handler 把 `[0x53ECC]` 設成非 0，整個 `0x1A30B` 提前
return，回合不推進，[0x53BEF] 也不變。三個 `0x1A866` 呼叫（selector 1/0/2）與友軍／敵軍
AI 掃描不是同一件事，但**順序是固定交織的**：selector1 緊接友軍掃描、selector0 緊接
敵軍掃描（並包住計數器遞增）、selector2 在回合跑馬燈之後單獨執行，不再接 AI 掃描。這是
L145「turn/camp 與 runtime execution」與 L210「回合 orchestration」原本缺的那條連接線。

### `0x16F55`：手動強制結束回合——「全軍前進」與「結束回合」是兩個不同指令（全新反組譯）

`0x117E7` 在游標下沒有可行動己方單位時呼叫 `0x16F55()`（既有 doc23 只記到「回標題/選單
模組」，未記錄它也是**戰場內的系統選單**，本節補上）。它是一個 0..3 四項 ring
（`[0x53C57]` 選擇 index，`0x1741C`/`0x177FC` 讀鍵），逐項反組譯＋FDTXT 字串核對如下
（字串以 FDOTHER_004 字型渲染 `FDTXT_000` 對應 index 直接目視確認，非猜測）：

| `[0x53C57]` | 呼叫鏈 | FDTXT 確認文字 | 結論 |
|---:|---|---|---|
| 0 | 直接呼叫 `0x19DF7` | （無確認對話） | 存檔（既有 doc56 2026-08-02 已記） |
| 1 | `0x1956B(record0+7)`(Yes/No dialog) → `0x19953` 確認 → 若 Yes 且 `[0x53C57]` 仍為0：對每個 `record+6==2` 且 `(record+5&0x85)==0` 的己方單位執行 `0x12CEA`(鏡頭 focus 到該單位) → `0x14B78([0x53AB1],[0x53AB5], unitIdx, 1)`(走既有 doc11 移動管線，目的座標是進選單前就讀入、迴圈中固定不變的錨點座標) → `0x134E4` → `0x13512`(標記已行動)；全部單位跑完才呼叫 `0x1A30B()` | FDTXT `0x1A1`＝**「決定要行軍嗎？」**；確認後 FDTXT `0x1A2`＝**「那麼全軍發進吧！」** | **「全軍前進」**：強制每個尚未行動的己方單位都跑一次真正的移動管線（往同一個固定錨點座標），逐一標記已行動，最後才進 `0x1A30B` |
| 2 | `0x1728C()` | （未展開，見下） | 另一個子選單，4 個 ring 項目依 `[0x51E61]`/`[0x51E62]`/`[0x53AF9]`/`[0x51AAB]` 四個既有旗標決定是否反白；本節未展開其内容，留待後續 |
| 3 | `0x1956B(0x4B)`(Yes/No dialog) → `0x19953` 確認 → 若 Yes 且 `[0x53C57]` 仍為0：等待 200 tick(`0x3790A`) → `0x196CB`(收尾動畫) → **直接**呼叫 `0x1A30B()`，**不**跑選項1那個逐單位移動迴圈 | FDTXT `0x1A3`＝**「要結束本回合的行動嗎？」**；確認後 FDTXT `0x1A4`＝**「好的，就結束本回合的行動吧！」** | **「結束回合」**：不移動任何單位，直接跳進回合 orchestrator |
| （拒絕／取消任一分支） | — | FDTXT `0x19C`＝**「是嗎？那麼就不要了。」** | 兩個分支共用同一句取消文字 |

（原始位址、字串 index 與渲染流程存於本次 session 的
[`fd2_field_menu_endturn_disasm_2026-08-20.txt`](../data/fd2_field_menu_endturn_disasm_2026-08-20.txt)；
FDTXT_000 目前共 661 條字串，index `0x19c/0x1a1/0x1a2/0x1a3/0x1a4` 皆在範圍內且已渲染核對。）

這證實原版有**兩個語意不同的手動結束回合入口**，不是同一個「結束回合」按鈕的兩種措辭：
「全軍前進」會讓每個還沒行動的己方單位真的跑一次移動管線（往同一個固定錨點），才進入
`0x1A30B`；「結束回合」則完全不移動任何單位，直接進入 orchestrator。兩者跟 `0x13565`
的自然（全員已行動才自動觸發）路徑是**三條可以到達 `0x1A30B` 的獨立入口**，且都遵守
「先讓己方（camp2）的狀態穩定下來，才進兩個 AI 掃描」這個不變式——手動路徑用強制移動
或直接跳過取代 `0x13565` 的判斷，但送進 `0x1A30B` 之後的行為（own regen → 友軍掃描 →
敵軍掃描 → 回合計數）完全相同，沒有另開後門跳過 AI 掃描。

### L145／L210／L304／L1038 完成度

- **L1038（native end-turn 完整 caller／team predicate／AI completion timing）**：
  **本輪視為已閉合**。三個入口（`0x13565` 自動判定、`0x16F55` selector1「全軍前進」、
  selector3「結束回合」）與 `0x1A30B` 本體（doc56 已閉合，本輪補上與 `0x1D80B`/`0x1D8BA`
  的精確交織順序）合起來完整回答了 caller、team predicate 與 AI completion timing 三個
  子問題，均有反組譯位址與（結束回合選單部分）FDTXT 字串佐證。**尚未閉合**的只有
  `0x1728C`（selector2 子選單）本體語意，以及 remake 端尚未把這三個手動入口與
  `0x13565` 自動判定接成統一的 Go 實作（目前 `remake/cmd/fd2/main.go` 仍是 Tab
  手動換回合，見 worklist L1193「⬜ 自動結束回合」原文）——這是工程接線，不是新的 RE
  缺口。
- **L145（doc11「候選格順序／raw helper 語意／turn/camp 與 runtime execution」）**：
  候選格順序、raw camp 定義（+6=0/1/2）與物理/法術/道具三條執行鏈皆早已個別關閉；
  本輪補上的 `0x1A30B` 交織順序，是最後一塊「runtime execution 怎麼被觸發／怎麼收尾」
  的證據。**視為完成度大幅提升、僅剩極小尾巴**：`0x14818` 各 caller-specific mode
  是否有額外視線（LOS）判定、`0x1728C` 子選單語意，兩者仍待未來 session。
  同分/ tie-break、地形修正、`0x1DEBE` 等公式細節維持既有 [x] 狀態不變。
- **L210（REMAKE-AI-MODE-RUNTIME「剩餘模式玩法名稱／event82 觸發／回合
  orchestration」）**：「回合 orchestration」子項**本輪已閉合**（見上方主鏈與
  `0x1A30B` 交織順序）；「event82 觸發」子項在 doc25 2026-08-19 的全 EXE writer 稽核
  已窮盡（見 doc25 §6.3 附記，本文件不重複）；**唯獨「剩餘模式玩法名稱」仍未閉合**——
  這是本專案刻意的 fail-closed 立場（見本文件多處「不替模式命名」聲明），不是遺漏，
  只有在找到可靠的玩家可見語意證據（例如攻略對照或 DOSBox E2 逐幀比對）前才會補上。
- **L304（敵方 AI 回合完整權重／target selection）**：物理／法術／道具三條評分公式與
  `0x14EF0` 三分數 tie-break 早已個別關閉（見本文件前段各節）；本輪新補的是「兩遍敵軍
  掃描為什麼存在」的**觸發時機**面（`0x1D8BA` 在 `0x1A30B` 內只會被呼叫一次、且是
  selector0 那一次，跟 selector1 的 `0x1D80B` 友軍單遍不是同一次呼叫，此前只知道兩者
  都在某個更外層流程裡，現在確定是同一個 `0x1A30B` 裡先友後敵、緊接著遞增回合數的
  固定順序）。**target selection 的完整權重公式面維持既有 [x] 狀態**；「為何需要
  預選與第二遍」這個玩法設計層的問題，本輪未新增證據，仍待後續。

## 下一步最小驗證

1. 在固定原版存檔與固定單位上，依序於 `0x1D8BA`、`0x13A9F`、
   `0x14EF0`、`0x15AD8` 記錄單位索引、關鍵原始欄位與
   `0x53C23..0x53C3F`。比較只改一格位置或一個候選的兩個狀態。
2. 追蹤 `0x14237` 的 `0x1B83D→0x1B722` command record 來源，
   再以固定原版存檔動態比對已閉合的候選落點、方向陣列與實際選定結果。
3. 先證實單位掃描順序、候選數與選定結果的資料來源，再命名剩餘 raw 欄位；
   不以現有重製人工智慧輸出補足原版未知值。

## 仍待確認

- `0x154D1` 只是 `0x1548E` 執行函式中段，不能當施法入口。
- `0x14818` 各 caller-specific mode 的完整幾何與是否另有視線判定。
- `[ebx+0x40]` 擊殺門檻、`[ebx+8]` 狀態旗標的精確語意。
- 上層 raw mode 0 以外各分支何時選 `0x14121`／`0x13E9C`，以及 selector
  對敵方、友軍 NPC 與劇情行為的完整命名。

## 重製對應（fail-closed）

目前已能以完整原始記錄、命令遮罩、MP、候選幾何、兩個單位級分數及三遍
門檻建立原始 AI 診斷切片；另有逐筆回呼順序、動態 bit7 重判及 pending
提前退出的 E0 執行契約，但尚未提供 `0x13A9F` 與各表 handler 的正式效果，
不可宣稱整回合已重現。`0x1DEBE` 條件、raw `+8`、上層 mode 語意、
零分勝者與動態原版對照仍未全部閉合。重製端的正規化
`aiActUnit`／`NextAIPlan` 因此仍是近似路徑；難度調整參數也不得當成原版
等價設定。

## 2026-08-20 續：L145 尾巴收尾（0x14818 LOS + 0x1728C 子選單）

> **方法**：純靜態、唯讀 Ghidra headless（`analyzeHeadless -readOnly -noanalysis`，
> `FD2Analysis3` 專案）對 `FUN_00014818`／`FUN_0001728c` 做
> `createFunction`+`DecompInterface` 完整反編譯，再逐指令反組譯同一函式邊界
> 核對（`ProbeL145Tail0820.java`）；接著對 `0x1728c` 用到的四個旗標
> （`[0x51e61]`/`[0x51e62]`/`[0x53af9]`/`[0x51aab]`）做全 EXE xref 掃描
> （`ProbeFlagXrefs0820.java`），並反組譯存檔寫入端 `0x19DF7` 與讀取端
> `0x10010` 附近指令核對這四個欄位在存檔結構裡的位置（`ProbeSaveFlags0820.java`）。
> FDTXT 字串以既有 `tools/decode_text.py` 的 `parse_strings`/`render_glyph`
> 對 `extracted/raw/FDTXT/FDTXT_000.bin` + `extracted/raw/FDOTHER/FDOTHER_004.bin`
> 字型直接渲染成圖片目視核對，非猜測。三支 probe script 與渲染小工具皆存於
> `FD2_ghidra_projects/`（不刪除，供覆核）。
>
> **版本核對**：本輪 `ProbeCheckHash.java`（沿用既有腳本）讀出 `FD2Analysis3`
> 目前載入檔案 MD5 為 `a6e341a8decc6ebf7f4872076d9cf161`、記憶體映像大小
> `802705` bytes——與本文件同一天稍早「完整回合主鏈」那節記錄的版本**完全一致**，
> 沒有出現版本漂移；`0x14818` 反組譯出的函式邊界 `0x14818..0x149f7`（size 480）
> 也與 doc03（`03-exe-and-data-structures.md`）舊筆記「`0x14818`(size 480)」
> 精確吻合，可視為同一函式在不同 session、不同工具鏈下的獨立交叉驗證。

### 1. `0x14818` 完整本體：確認無額外視線（LOS）判定

`0x14818..0x149f7`（480 bytes）已完整反編譯+反組譯（見
[`fd2_14818_1728c_disasm_2026-08-20.txt`](../data/fd2_14818_1728c_disasm_2026-08-20.txt)）。
Hex-Rays 風格反編譯結果精簡如下（變數名為 Ghidra 自動命名，非重新詮釋）：

```c
int __stdcall FUN_00014818(int param_1,int param_2,int param_3,int param_4,int param_5,int param_6)
{
  if (param_4 < 0x10) {                         // mode<0x10：reach mask 分支
    FUN_0004e8a5(); FUN_0004e390();              // = 舊位址 0x4e555→0x4e040（既有 doc13 已閉合的
                                                  //   flood-fill occupancy grid，非本節新證）
    if (param_5 != 0) {                          // a5(inner radius)!=0 才做額外排除
      for (每格 (x,y)) {
        // iVar1/iVar2 = |x-a4x|、|y-a4y|（呼叫 FUN_00037932，等價舊 0x375e2）
        if (iVar2 + iVar1 < param_5) 該格 mask = 0xff;   // 純 Manhattan 距離排除，例如施法者自己
      }
    }
  } else {                                        // mode>=0x10：十字形分支
    radius = param_4 - 0x10;
    for (每個 x) if (|x-param_2 對應軸| <= radius) 該列 mask 清 0;   // 同 row 直線
    for (每個 y) if (|y-param_1 對應軸| <= radius) 該欄 mask 清 0;   // 同 column 直線
  }
  for (每個 roster 單位 idx) {
    if ((單位 raw+5 & 1)==0                      // 既有「+5 bit0 排除 inactive」
        && mask[該格] != 0xff                     // 既有排除 marker cell
        && camp filter(param_6, 單位 raw+6))       // 既有 0/1/2/3 陣營碼過濾
      輸出 idx；
  }
  return count;
}
```

逐行核對後的結論：**整個 480-byte 函式本體只有三段邏輯——(a) `mode<0x10` 的
flood-fill reach mask（呼叫既有已閉合的 `0x4e8a5`/`0x4e390`，即舊位址
`0x4e555`/`0x4e040`，doc13 已證實其唯一的「阻擋」語意是移動成本格
`0x40` 不可通過，`0x80` 非零成本）加上可選的 Manhattan 內圈排除（`a5!=0`
時把距離 `<a5` 的格子蓋 `0xff`，即既有「施法者自身格排除」用法）；(b)
`mode>=0x10` 的十字形半徑判斷，**這個分支完全沒有呼叫任何額外函式做阻擋
判斷**，純粹是 `|Δx|<=radius`／`|Δy|<=radius` 的線性比較；(c) 統一的
roster 掃描+陣營過濾。全函式沒有第三種呼叫（沒有任何逐格 raycast、沒有
呼叫 `0x1F183`/`0x44397` 這類地形 gate 函式、也沒有呼叫任何新的未知
子函式）。**結論：`0x14818` 除了已知的 Manhattan/十字距離＋（僅
`mode<0x10` 才有的）flood-fill 佔用阻擋之外，本體內完全沒有另一層「能不能
看到/命中」的視線判定；`mode>=0x10` 的十字分支甚至連佔用阻擋都沒有，是
純幾何直線。** 這是窮盡反組譯整個函式邊界後的結論，不是抽樣推測。

### 2. `0x1728C`：選項旗標「切換環」，語意仍未閉合但已大幅收斂

`0x1728c..0x173e6`（347 bytes）同樣完整反編譯+反組譯（同一份
[disasm 檔](../data/fd2_14818_1728c_disasm_2026-08-20.txt)）。結構是一個
`[0x53c57]=0` 起始、`0x1741C`(建環)/`0x177FC`(讀鍵，`-1`＝取消)/`0x176B4`
(收尾/重繪) 組成的固定 4 項迴圈：每次重繪前先算出四個項目各自要顯示的
FDTXT 字串 index（依旗標目前值在一對相鄰 index 間二選一），選到某項按確認
鍵時**只是把對應旗標做 boolean 翻轉，然後回圈重繪**，沒有任何一項會呼叫
戰鬥/移動/施法之類的功能函式：

| 環項 index (`[0x53c57]`) | 旗標 | 顯示字串（依旗標 0/非0 二選一，FDTXT_000） | 確認鍵動作 |
|---:|---|---|---|
| 0 | `[0x51e61]` | idx `0x12`＝**「米亞斯多德」**／idx `0x13`＝**「蜜蒂」** | 翻轉 `[0x51e61]`；翻轉後另呼叫 `FUN_0003b124([0x53ed0], 新值?0x7f:0, 0x3e8)` |
| 1（其餘 index 皆不成立時的 `else`） | `[0x51e62]` | idx `0x14`＝**「羅德曼」**／idx `0x15`＝**「莎拉」** | 直接翻轉 `[0x51e62]`（`0`↔`1`），無額外呼叫 |
| 2 | `[0x53af9]` | idx `0x16`＝**「約拿」**／idx `0x17`＝**「卡里斯」** | `XOR [0x53af9],1` |
| 3 | `[0x51aab]` | idx `0x18`＝**「羅蘭」**／idx `0x19`＝**「希爾法」** | `XOR [0x51aab],1` |
| 取消（`0x177FC` 回傳 `-1`） | — | — | 跳出迴圈，回 `0x16FDD`（既有 `0x16F55` 流程） |

八個 FDTXT_000 字串（idx `0x12..0x19`）已用字型渲染成圖片直接目視核對，
非猜測（見 [`fd2_1728c_submenu_strings_2026-08-20.png`](../data/fd2_1728c_submenu_strings_2026-08-20.png)
與逐字文字紀錄 [`fd2_1728c_submenu_strings_2026-08-20.txt`](../data/fd2_1728c_submenu_strings_2026-08-20.txt)）：
渲染結果是「米亞斯多德／蜜蒂／羅德曼／莎拉／約拿／卡里斯／羅蘭／希爾法」
八個**人名**，且與 doc49（`49-character-id-name-table.md` 第 55-62 行）
既有的「角色 ID 17..24」表**逐一對應、僅差 +1 的固定索引位移**（char
ID17=米亞斯多德對到 FDTXT idx18、...、charID24=希爾法對到 FDTXT
idx25）——這是獨立來源（doc49 的對話/`characters.json` 證據 vs. 本節的
FDTXT 直接渲染）互相印證，不是同一份證據重複引用。

**額外 xref 稽核（`ProbeFlagXrefs0820.java`，
[`fd2_1728c_flag_xrefs_2026-08-20.txt`](../data/fd2_1728c_flag_xrefs_2026-08-20.txt)）
把這四個旗標的語意問題往前推進一大步，但尚未真正命名**：

- 這四個旗標**不是 `0x1728c` 私有的臨時變數**，而是在整支 EXE 裡被多處
  讀寫的全域 byte：存檔寫入端 `0x19DF7`（`0x16F55` selector0，既有
  doc11 本文已閉合的「存檔」入口）與讀取/還原端 `0x10010` 各自連續
  讀寫這四個位址；反組譯 `0x19DF7`／`0x10010` 附近指令（
  [`fd2_1728c_save_metadata_mapping_2026-08-20.txt`](../data/fd2_1728c_save_metadata_mapping_2026-08-20.txt)）
  證實它們落在同一段存檔 metadata 的連續 byte 上（`[0x53af9]`／
  `[0x51aab]`／`[0x51e61]`／`[0x51e62]` 依序相鄰）。這與
  `docs/knowledge-base/23-boot-title-and-scenario-flow.md` 第 292 行**早已
  記錄、但明確聲明「玩法名稱仍不猜」**的存檔 metadata
  `+6/+7/+8/+9→[0x51aab]/[0x53af9]/[0x51e61]/[0x51e62]` 是同一組欄位——
  本節新證只是把「這四個 byte 在存檔裡相鄰」跟「這四個 byte 各自對應
  哪一個 in-battle 切換選項、顯示哪一對人名標籤」兩件事釘在一起，
  **doc23 原本刻意不猜的玩法語意，本節依然不猜**（doc23 的 store
  順序敘述 `+6/+7`＝`aab/af9` 跟本節反組譯出的實際 store 順序
  `+6/+7`＝`af9/aab` 剛好相反，這是尚待厘清的小落差，不影響「同一組
  欄位」這個主結論，如實記錄供未來對照）。
- `[0x53af9]` 額外被 `0x1A7BD`／`0x1A7F1`（本文件同一天稍早「回合
  orchestrator」一節已閉合的 AI 掃描 resource setup／release 包裹函式）
  與 `0x1548E`／`0x15311`（本文件既有「物理選擇結果執行」／`0x1598A`
  執行分支消費者）各讀取一次；另外三個旗標則沒有出現在這些戰鬥執行路徑
  裡。這暗示 `[0x53af9]`（對應「約拿／卡里斯」那組標籤）可能跟其餘三個
  旗標的語意類別不完全相同（更接近戰鬥期間會被讀取的某種模式開關），但
  這只是 xref 分布觀察，不足以命名。
- 六個尚未展開的函式（`0x25977`／`0x25a96`／`0x25b45`／`0x25ebb`／
  `0x2968D`／`0x2986F`）也都讀寫這四個旗標之一；其中 `0x25EBB` 正是
  doc23 第 286 行已定位的「標題選單新遊戲/讀取存檔」回傳值分派函式，
  地址相鄰的 `0x2968D`／`0x2986F` 很可能是同一個標題流程裡的存檔槽
  處理 helper——這是合理但**未反組譯驗證**的推測，留給下一輪。
- `FUN_0003b124`（項目0翻轉旗標時額外呼叫的函式）已反編譯：本體只是
  一個計數器遞增＋條件呼叫 `0x3f22a`/`0x37c9c`/`0x3f46b`/`0x449e0`/
  `0x38255` 的通用「等待/幫浦幀」型函式（跟 `0x16F55` 選項3用到的
  `0x3790A`「等待 200 tick」是同一類型的 helper），**不能確認是音量/
  音效專屬呼叫**——先前草稿曾臆測是音量設定，此處撤回，改為如實記錄
  「通用 tick/frame pump，用途未證實」。

**結論（誠實記錄，不誇大）**：`0x1728C` 的**機制**（4 項旗標切換環、
各自對應存檔 metadata 裡哪個 byte、切換時顯示哪兩個 FDTXT 人名標籤、
確認鍵除了翻轉旗標以外是否有額外呼叫）已經完整反組譯+反編譯閉合，且
新增了「這四個旗標同時是 doc23 已知但未命名的存檔 metadata `+6..+9`
欄位」這個先前沒有的連接證據。但**這四個旗標實際控制遊戲裡什麼行為
（是否真的是「二選一 recruit/上場角色」、還是純粹的 UI 選項、或是其他
用途）仍未閉合**——doc23 對同一組欄位「玩法名稱仍不猜」的立場沒有被
本節推翻，只是補上了目前為止最完整的旁證（人名標籤配對＋存檔欄位位置
＋額外的戰鬥期讀取點分布）。下一步建議：反組譯 `0x25977`/`0x25a96`/
`0x25b45`/`0x25ebb`/`0x2968D`/`0x2986F` 這六個函式本體，確認是否為
標題選單存檔槽 loader/UI，會是最快能進一步收斂語意的路徑；若要真正
命名，最終仍需要動態對照（本專案安全規則下這輪不做 DOSBox-X/WSL2）。

### L145 完成度（本輪最終盤點）

- **`0x14818` 視線判定缺口：視為已閉合**。窮盡反組譯整個 480-byte 函式
  本體後確認：除既有已知的 Manhattan（`mode<0x10`，含可選內圈排除）／
  十字（`mode>=0x10`）距離規則，以及僅 `mode<0x10` 才有的 flood-fill
  佔用阻擋（`0x4e8a5`/`0x4e390`，即舊位址 `0x4e555`/`0x4e040`，doc13
  已閉合）之外，函式本體不呼叫任何額外的視線/阻擋子函式；`mode>=0x10`
  的十字分支甚至完全沒有阻擋判斷。這是明確、可驗證的「沒有」結論，不是
  找不到就放棄。
- **`0x1728C` 子選單語意：機制層閉合，玩法語意層仍未閉合**。4 項切換環
  的完整結構、對應存檔欄位、FDTXT 人名標籤配對、額外呼叫（含撤回先前
  「音量呼叫」臆測）皆已反組譯查證；但四個旗標實際的玩法效果、為何用
  人名配對顯示，仍是開放問題，與 doc23 既有立場一致，留待下一輪（建議
  先靜態展開上述六個候選函式）。
- 兩個缺口原本都屬於 worklist L145「doc11 候選格順序/turn-camp 與
  runtime execution」殘留項的最後尾巴：第一個（LOS）本輪徹底收工；第二個
  （`0x1728C`）從完全空白推進到「機制全懂、語意未知」，不宜再往上誇大
  成「已閉合」。
