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
| 進入非玩家階段 | `0x1A4EB`／`0x1A58F` 兩條階段專用呼叫點 | 已證明有兩條不同原始選擇值的單位掃描流程；尚不能直接命名為敵方／友軍 |
| 挑下一個單位 | `0x1D80B`／`0x1D8BA`／`0x1D988` 依執行期陣列順序掃描 | 會檢查 `+6`、`+5 & 0x81`、`+0x26` 等原始欄位；欄位語意尚未全閉合 |
| 取得可用行動 | `0x13A9F→0x14EF0`，另含 `0x1598A`／`0x1567E` | 已證明依記錄命令與可用命令產生候選；不是單一「AI 主函式」 |
| 枚舉物理落點 | `0x145CD→0x4E040→0x146D1→0x14B16` | 已閉合阻擋標記、原版移動成本、佔用格排除及 Y 優先／X 次之的固定順序 |
| 每格枚舉目標 | `0x14237→0x14818` | 依該呼叫者專用幾何建立目標；不可把物品原始位元組通稱為武器射程 |
| 物理評分 | `0x14237..0x145CC` | 先比較優先級、再比較分數；完全同分保留先枚舉的落點與目標 |
| 法術評分 | `0x15AD8→0x15B77` | 已閉合數個原始分支；尚未完整接入重製執行期 |
| 執行選中結果 | `0x1548E` 等執行鏈 | 消費已選落點／目標並播放移動與戰鬥；不是尋路器 |

因此目前對「電腦如何選攻擊目標」最精確的回答是：原版不是只找最近角色。
物理路徑會按固定落點順序，對每個落點列出合法目標，套地形後計算攻防差，
拒絕分數 `<=2` 的候選；能嚴格超過目標原始欄位 `+0x40` 的候選提高優先級並將
分數加倍，另受 `0x1DEBE` 與目標原始欄位 `+8` 修正。先比較優先級，再比較
分數；兩者完全相同時保留較早出現的候選。尚不能回答的是「完全沒有可攻擊
方案時如何選擇接近路線」，以及上層 selector 對每一種敵方／友軍行為模式的
名稱。

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

`0x15b77` 本身目前可確認：command `<0x0d` 逐目標讀 runtime record `+0x40`，基礎分數
為 8，若 spell value 大於 record value 則為 `0x18`；record `+8==0` 時以 native
FPU path 對分數乘 `1.5` 並轉回整數。command `0x0d..0x10` 走 recovery 分支，讀
current/max HP 與 record `+0x34 bit0`；`0x14..0x16` 掃 raw `+0x25/+0x26/+0x27`
並呼叫 `0x1c269`。這些是 raw score branches，不足以替欄位命名成攻擊、治療或狀態，
也尚未證明它就是完整 AI 回合入口。

同一輪 caller scan 找到一個較可信的 dispatch boundary：`0x14ef0` 有六個 direct callers
（`0x13af5`、`0x13b2d`、`0x13b4d`、`0x13b6d`、`0x13c24`、`0x13dec`）。其 body 先呼叫
`0x14237`、`0x1598a`、`0x1567e`，再依 raw score/global state 分派至 `0x1548e`、
`0x15311` 或 `0x15055`。這足以取代舊 `0x15140` 作為下一輪追蹤起點，但目前仍只稱
**candidate dispatch boundary**：六個 callers 的 turn/camp 語意、`0x14237` 與
`0x1567e` 的完整資料契約尚未閉合。

更上游的 `0x13a9f` 是目前可重現的 unit-action dispatcher：它以 `unit index` 建立
`0x50`-byte record，先檢查 raw `+5` 的 `0x05` bits，再取 `record+0x34 & 0x0f`。
command nibble `0/1/2/3/5/10` 會呼叫 `0x14ef0`，`4`/`7`/`9`/`11` 則各走不同
movement／portrait／score fallback；`0x0b` 分支直接呼叫 `0x1598a`，在 score gate
後選 `0x15311` 或 `0x1548e`。這是「record command→action helper」的已證實邊界，
但尚不能把 nibble 值命名成攻擊、移動或 AI 陣營語意。

`0x1d80b`、`0x1d8ba`、`0x1d988` 是目前確認的上層掃描 callers：三段都以
`[0x3beb]` 遍歷 `0x50`-byte records，先檢查 raw `+6`、`+5 & 0x81`、`+0x26`，再分別
呼叫 `0x13a9f` 或 `0x1598a→0x1567e→0x13a9f`。每筆之後依 `[0x51a8f]` function table
與 `[0x53c03]` table dispatch，並受 `[0x53ecc]` loop flag 控制。這證明它們是
unit-scan/action-loop 的 caller boundary；`+6` 的 camp/phase 名稱、table entry 的
劇本語意仍不命名。

更高一層的 callsite 也已固定：`0x1a4eb` 在 `0x1a813(1) → 0x1a866(1)` 後呼叫
`0x1a7bd → 0x1d80b → 0x1a7f1`；另一段 `0x1a58f` 在 `0x1a813(0) → 0x1a866(0)`
後呼叫 `0x1a7bd → 0x1d8ba → 0x1a7f1`。這只證明兩個 phase-specific unit-scan
callsites 位於同一場景流程；`0x1a813/0x1a866` 的 selector 與 campaign phase 仍保持
raw，不能把它們直接命名成「敵方回合開始／結束」。

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

- `0x15688` 開始的函式逐一掃描單位可用命令。`0x15735` 讀取命令描述子的 command byte；`command<=0x0F` 走物理攻擊，`command>0x0F` 在 `0x1579A–0x157B5` 做 `spell_id=command-0x10`，並呼叫 `0x149F8` 取得／建立後續 target-candidate 資料；candidate 之後才交給 `0x15B77` score branches，不能把 `0x149F8` 直接命名成傷害／命中評分。
- 選中的命令由全域 `0x53C3F` 保存。`0x15055` 執行 AI 行動時於 `0x150C2` 讀回同一 command byte；`command>=0x10` 在 `0x150D3–0x150F1` 再次轉成 spell id 並呼叫 `0x149F8`，之後 `0x15168→0x28784` 播放施法者演出。
- 因此「敵方 AI 施法」不是推測機制，而是已由 callsite 證實；尚待補的是 command inventory/可用法術條件、治療目標選擇，以及 `0x15880/0x15B77` 對不同法術效果的精確優先級。
- remake 已先把 editable item 23-byte row 的 K4（raw byte `0x11`）資料化為 `AICommandSpell`（command `>=0x10` → `spell_id=command-0x10`）；這只建立 command inventory，不提前猜測 AI ranking、可用條件或治療目標。

2026-07-27 raw availability slice：`NativeAvailableAISpellCommandIDs` 現重用 `0x1598a` 的 `unit+0x27==0` gate、
40-bit command mask、36-entry command book 與 `record+5 <= unit+0x44` MP gate，只回傳 raw command IDs `>=0x10`。
它不在 adapter 內轉換 `command-0x10`，也不接 target、score、Cast 或 effect；因此不會把 inventory bridge 誤宣稱成 AI 施法完成。

`0x15B77` 的 spell-target 評分分支也已直接反組譯（呼叫點 `0x15AD8`）：

- spell id `0..12` 走攻擊術分支，逐一掃候選目標；依目標 HP 與施法者法術值累加基本／高優先分數（可見常數 `8` 與 `0x18`）。
- spell id `13..16` 走治療／恢復分支，改掃己方候選；Hex-Rays `0x15c30..0x15c4b` 顯示 `current HP < max/3` 給 raw score 8，否則 `< max/2` 給 3，否則 0，且 record `+0x34` bit0 會把該分數乘 2。這是 score gate，不命名 bit0 或效果。
- spell id `17..19` 進入另一個 raw scoring helper；`20/21/26/27` 讀取 `+0x25/+0x26` flag bytes，ID22 先 gate `+0x27` 再呼 `0x1C269`。這些是 call/score topology，不足以命名成增益、毒麻或其他 gameplay status。
- 依 spawn constructor `0x10f6b..0x10fa5` 的 direct trace，FDFIELD b13..b16 的 `initial_command_mask` 只複製到 runtime `unit+0x1a..+0x1d`，而 `unit+0x22..+0x27` 另由 constructor 清零。前者是 runtime 五位元組 command bitset 的初始四位元組；後者目前只能稱為 raw transient／modifier bytes。雖然 writer paths 會讀寫其中幾個欄位，derived-stat/property/status 名稱仍未由完整 equipment recompute、presentation 與 caller evidence 證實；不能把它們命名成 AP/DP/HIT 或 M1–M5 spell bitfield。AI 仍依 spell family 選目標，individual command ID 與後續 modifier writer 待另行接線。

## 下一步最小驗證

1. 在固定原版存檔與固定單位上，依序於 `0x1D80B`、`0x13A9F`、
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

目前只能把已釘死的 raw scoring branches 保存成 adapter；不可直接宣稱照搬這段摘要即可重現原版 AI。
`0x1DEBE` 條件、raw `+8`、上層 mode／selector 語意，以及
spell command inventory/MP/target transaction 尚未全部閉合。remake 的 normalized `aiActUnit`／`NextAIPlan`
因此維持 approximation，只有具備完整 raw record、caller gate 與 target evidence 時才可新增 native AI slice；
難度調整參數也不得被當成原版等價設定。
