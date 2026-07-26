# 11 — 戰場 AI:敵人 / NPC 的行動決策

> **2026-07-27 canonical-binary recheck (Docker Capstone):** 重新對版控中的
> `org_game/炎龍騎士團/FLAME2/FD2.EXE` 做 direct scan，`calls 0x15140` 與
> `calls 0x15356` 均沒有結果；`0x15140` 的實際指令落在過場／畫面流程，不能以本檔舊摘要
> 直接當作 AI 主函式或傷害公式。現階段唯一保留的 AI score callsite 是
> `0x15ad8 → 0x15b77`，但其 caller context 與完整 entry 仍待重建。因此下文原有
> `0x15140`、`0x1527b`、`0x1529e`、`0x152ab`、`0x15356` 流程降級為**歷史待核對假說**，
> 不得作為 remake parity 證據或接入 runtime。

## 目前可重現的 raw score 邊界（2026-07-27）

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

> 戰棋上敵方(與友軍 NPC)每回合怎麼決定「移動到哪、打誰、打不打」。
> 舊第 3 輪筆記曾把 `0x15140` 記為 AI 主決策函式；該地址目前已被 canonical recheck 撤回，單位陣列 `[0x3A45]`、
> 每單位 0x50 byte、數量 `[0x3BEB]`(見 `03-…` 單位結構)。

## 敵與友 NPC 共用同一套 AI

引擎不分「敵 AI / 友軍 AI」——**同一決策函式**,只是依單位的**陣營欄位 `BB`(0x0E)**決定誰是
攻擊對象(敵方打己方/友軍,友軍 NPC 打敵方)。所以本文件同時涵蓋「敵人 AI」與「戰場 NPC AI」。
玩家己方(`BB=02`)由玩家操作,不走此 AI。

## 決策流程(每個 AI 單位的回合)

```
1. 算可達格:對該單位位置做 flood-fill(0x4EE40),依移動力 MV(0x42)與地形移動成本,
   得出所有可移動到的落點。(0x15916 計算落點數)
2. 對每個可達落點 dest:
     建立「從 dest 可攻擊到的目標清單」(0x15618;最多 16 個,呼叫 0x4F355 做範圍/視線判定)
     對清單中每個目標 target 評分(見下)
3. 取所有 (落點, 目標) 組合中分數最高者
4. 移動到該落點,攻擊該目標;若無可攻擊目標 → 走另一分支(接近 / 待命)
```

## 目標評分公式(核心)

對一個候選 target,分數 `score` 與優先級 `prio` 這樣算(位址見括號):

1. **預期傷害**(0x15356–0x1538C):
   ```
   myAP'  = myAP  × 地形AP%[地形] / 100      (地形表 0x1A12)
   tarDP' = tarDP × 地形DP%[地形] / 100      (地形表 0x1A2A)
   dmg    = myAP' − tarDP'
   if dmg ≤ 2:  跳過此目標(不值得打)         ← 攻略「不管防禦都攻擊」patch 改的就是這條
   else:        score = dmg, prio = 8(基本可攻擊)
   ```
2. **可擊殺加成**(0x1527B–0x15285):若 `dmg ≥ 目標關鍵值[ebx+0x40]`(力量/門檻)→
   `score ×= 2`、`prio = 0x12`(18,最高優先)。→ **AI 偏好能造成重創 / 擊殺的目標**。
3. **情境加成**(0x1529E,呼叫 0x1ECBE):某條件成立(疑為「不會被反擊」或目標類型)→ score 再加成。
4. **狀態倍率**(0x152AB):目標某旗標 `[ebx+8]==0`(疑為「尚未行動 / 可被夾擊」)→ `score ×= 1.5`。
5. **擇優**(0x152C5–0x152F4):比較 `(prio, score)`,**先比優先級、再比分數**;勝出者記錄成目前最佳
   (落點與目標存全域 `0x3C43`/`0x3C47`/`0x3C4B`/`0x3C4F`)。

> 直覺:AI 會走到「能對最有價值目標造成最大傷害(最好能擊殺)」的格子;打不痛(≤2)的目標直接略過。

## 地形對 AI 的影響

評分時會把地形的攻防百分比修正算進去(表 `0x1A12` = AP%、`0x1A2A` = DP%,以地形編號索引,除以 100)。
→ AI 知道「站高地 / 防禦地形的目標較難打」,會據此選目標與落點。地形編號來自地圖(見 `03-…` FDSHAP 地形控制)。

## 已知 AI 行為(與攻略 / 玩法吻合)

- **不打防禦過高、傷害 ≤2 的目標**(攻略 modify1 #25 即解除此限制 → 敵人無腦攻擊)。
- **優先擊殺 / 重創**(可擊殺 ×2 + 最高優先)。
- **會利用地形**修正評估。
- **逐落點 × 逐目標**全枚舉取最佳(非貪婪近似)→ 行為穩定可預測。

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

## 仍待確認(後輪)

- `0x1548E` 才是移動函式入口；`0x154D1` 位於函式本體中，不能當施法入口。真正的 spell dispatch 已在上節 `0x150D3–0x150F1` 找到；法術 family 目標評分則在 `0x15B77`。
- `0x1ECBE` / `0x4F355`:目標清單的**攻擊範圍 / 視線 / 距離**判定細節。
- `[ebx+0x40]` 擊殺門檻、`[ebx+8]` 狀態旗標的精確語意。
- 無可攻擊目標時的「接近最近敵人」路徑選擇分支(0x15192 一帶)。
- flood-fill `0x4EE40` 的移動成本表(哪些地形耗幾點 MV)。

## 重製對應（fail-closed）

目前只能把已釘死的 raw scoring branches 保存成 adapter；不可直接宣稱照搬這段摘要即可重現原版 AI。
`0x1ECBE` 情境加成、`[ebx+0x40]` 擊殺門檻、`[ebx+8]` 狀態旗標、無攻擊目標時的移動分支，以及
spell command inventory/MP/target transaction 尚未全部閉合。remake 的 normalized `aiActUnit`／`NextAIPlan`
因此維持 approximation，只有具備完整 raw record、caller gate 與 target evidence 時才可新增 native AI slice；
難度調整參數也不得被當成原版等價設定。
