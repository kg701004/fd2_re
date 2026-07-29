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
   `0xFF` 時）索引已閉合的 90-entry 全域事件表 `0x51B91`，再以章節
   索引 `[0x53C03]` 呼叫章節戰場事件 handler 表 `0x51B19`；每筆最後
   檢查已閉合的 pending 碼 `[0x53ECC]`，非零就離開掃描。這不是三個
   未知 callback：前者消費 selector 產生的事件 ID，後者可寫中場碼1
   或章節結束碼2。
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

重製端新增 `fdother.PlanNativePhaseUnitScans`，以完整 `0x50` records 與
caller-supplied signed `[0x53C23]/[0x53C33]` 分數，分別輸出
selector1 單遍、selector0 預選與 selector0 第二遍。它保留原始逐列順序、
三個 raw admission gates 與「任一分數至少6」條件；三個 pass 不會被攤平成
一列，因為每筆後方的全域事件／章節 handler 可能寫 pending 碼而提早退出。
缺少逐單位 score provenance 時整體失敗即關閉。這是 E0 phase contract，
尚未授權正規化 `NextAIPlan` 冒充原版兩遍執行期。

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

### 物理移動落點：`0x145CD→0x4E040→0x146D1→0x14B16`

`0x14237` 在評分目標前，先建立所有可評分落點：

1. `0x145CD` 掃描所有有效執行期記錄。依呼叫者的原始選擇值，
   把另一組單位的中心格設 `0x40`（不可進入），四個相鄰格設 `0x80`
   （可進入，但扣除地形成本後將剩餘步數強制成 0）。
2. `0x4E040` 從行動單位 `(record+0/+1)` 與 `record+0x3B` 初始剩餘步數開始，
   以右、左、下、上順序遞迴。每格從 FDFIELD 圖塊索引高位取得 `0..3`
   分組，查 FDSHAP 地形記錄 `+1` 的移動代碼，再以該代碼索引
   `0x4E555` 選出的 20 位元組成本列。只有新剩餘步數嚴格大於既有值才覆寫。
3. `0x146D1` 排除同一原始選擇組、有效且非行動單位的佔用格。
4. `0x14B16` 以 Y 外迴圈、X 內迴圈掃描所有不等於 `0xFF` 的剩餘步數格，
   因此最後候選是穩定的逐列順序（row-major），而非 `0x4E040` 的遞迴順序。

`battle.NativeAIPhysicalDestinations` 保存這四段只接受原始資料的契約，要求完整
執行期記錄、`NativeTargetFlags`、`NativeTerrainMoveCodes` 與 20 位元組
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

`battle.ScoreNativePhysicalAttackCandidate` 保存上述單一候選的 raw
評分契約；`SelectNativePhysicalAttackCandidate` 另保存優先級、分數及同分
保留先出現者的選擇順序。兩者沒有接入目前正規化 `NextAIPlan`，也沒有替
`0x1DEBE`、raw `+8` 或兩個 `word` 欄位擴張語意。

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
不能用缺少 `NativeRecordByte6` 的 normalized `Camp` 代替；但 selector
0／1 本身已可分別稱為原始敵軍／友軍陣營碼。

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
- map0 真實 roster／target flags 與原始 item79 row 的交叉 fixture 固定
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
- map0 測試是修改狀態的 E0 交叉夾具：沿用真實名冊、目標旗標、地形、命令
  與物品資料，但排除其他 selector-zero 記錄，並替 index23 注入 command0
  與 item79；它不能證明一般玩家 map0 的實際敵方決策。
- 先前「只有 map0 有 `native_target_flags`」已確認是同步工具漏欄。
  33 張 map 現均由雜湊吻合的 FDFIELD 構成格 `+2` 逐位元組同步並檢查。
  map19 有1600格、7格非零；真實 unit55（identity92、遮罩
  `[4,0,0,8,0]`、MP288）在完整原始輸入下兩個 producer 都得到零分，
  且不創造勝者。這是 E0 負向資產錨點，不是原版動態回合 trace。
- 這個橋只涵蓋無副作用的分數與門檻，沒有呼叫 `0x13A9F`、逐單位事件／章節
  回呼或 `[0x53ECC]` 提早離開，因此不是正式敵方回合執行器。

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
門檻建立原始 AI 診斷切片；仍不可宣稱整回合已重現。逐單位回呼與 pending
code、`0x1DEBE` 條件、raw `+8`、上層 mode 語意、零分勝者與動態原版對照
尚未全部閉合。重製端的正規化
`aiActUnit`／`NextAIPlan` 因此仍是近似路徑；難度調整參數也不得當成原版
等價設定。
