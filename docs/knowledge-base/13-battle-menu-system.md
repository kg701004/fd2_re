# 13 — 戰場選單與行動系統

> 戰棋上選一個我方單位後,怎麼移動、怎麼跳出行動選單(攻擊/法術/道具/待機/狀態)、
> 游標怎麼操作、一個單位的「一回合」怎麼算完。第 3 輪反組譯 `FD2.EXE`。

## 一個單位的回合:行動狀態機

以下「AA／一回合」段落是早期 gameplay 摘要，並非目前已閉合的 native UI contract；現行 action chooser、
command grid、end-turn 與 campaign transition 以 SDD56／UI matrix57 的 raw evidence 為準。每個場上單位的
行動狀態在結構欄位 **`AA`(0x0D)**(見 `03-…`):

```
00 = 尚未行動    01 = 死亡    80 = 行動完畢
```

回合流程:

```
選我方單位(AA=00)
  → 顯示可移動範圍(flood-fill,依 MV 0x42 與地形成本;同 AI 的 0x4EE40)
  → 移動到目標格(或原地不動)
  → 跳出【行動選單】(見下)
  → 執行選項 → 單位 AA 設為 0x80(行動完畢,圖像變灰)
全部我方單位 AA=80 → 該回合結束,換敵方/友軍 AI(見 11-…)
```

> 攻略 modify1 揭露的行動規則(改的就是這套狀態機):
> - #5/#6「行動後可再行動」= 不把 AA 設成 0x80。
> - #7「移動後可施法,隨時可存檔」= 放寬移動後的可選動作與存檔 gate。
> - 動作完畢旗標 `0x80` 的檢查見 `0x12717`(`test byte [..+5],0x80`)。

## 行動選單選項

早期「典型戰棋的移動／攻擊／法術／道具／待機／狀態」列舉不是原版證據，已刪除。原版 action
chooser 現有 E0 的四項只可寫為 `↑=attack`、`←=command`、`→=item`、`↓=wait/field`（見下方
`0x18d8c` switch）；各 action 的完整 availability gate 仍須按各 callee 分開證明，不能以通用 RPG
假設補齊。

### `Get_EasyMagic` — 法術 / 狀態面板(已反組譯 `0x18ED0+`)

EXE 內洩漏的函式名 `Get_EasyMagic`,位於 `0x18ED0` 起。舊文件曾把 runtime `unit+0x22..0x26` 誤標成 **5 組法術 bitfield**；constructor direct trace（`0x10f6b..0x10fa5`）已推翻此說：magic raw 是 `unit+0x1a..0x1d`；`+0x22..+0x27` 目前只保留 raw transient／modifier bytes，不能由局部 writer 直接命名成 AP/DP/HIT 或 status。以下只保留函式名與 UI caller 的已證實部分，法術欄位對映維持 partial：

```
native magic raw / menu state:
    由 `+0x1a..+0x1d` 與 `0x1cff0` command path 產生可選項
    （`+0x22..+0x27` 不可當法術 bitfield，也不自動等於 named stats/status）
```

→ 即玩家按「法術」時看到的面板：可用 command 與目前 HP/MP。繪字／數字用 `0x195D6`（在 320 寬 buffer 定位繪製）。可用 command 的 label、spell-family、個別 spell ID 對照仍待完成，不得由 raw bit 或舊 M1–M5 名稱推導。

## 游標 / 鍵盤操作(已反組譯)

### 2026-07-25 Docker Capstone recheck: `0x18890` action dispatcher

`0x18890` 是「單位移動後進入 action dispatch」的 caller，而非單純繪圖 helper：它以 `ebp` 計算 `[0x53a45] + unit*0x50`，讀 unit context，呼叫 `0x18d8c(ebp, ..., mode)` 取得 action result；result `0` 繼續等待，`-1` 走取消／返回，其他 result 進入 `0x13a44` target/action path。它同時串接 `0x13488` path-walk 與 `0x134e4` 完成通知，移動後重寫 unit X/Y bytes，再由 `0x13512`／`0x13a44` 進後續 action。

這段 caller 沒有單獨證實 `0x18d8c` 的選項表與 result 編號，因此撤回「`0x18890` 只是選單繪圖」類推；目前 remake radial 方向 mapping 仍不得宣稱原版一致，直到 `0x18d8c` 本體和 menu/resource table 完成交叉引用。

### `0x18d8c` switch closure（2026-07-25, Docker Capstone）

`0x18d8c` 讀 `[0x3c57]` 後的四個分支已釘死：

| `[0x3c57]` | 方向 | native callee / 行為 | remake 對應 |
|---:|---|---|---|
| 0 | ↑ | `0x1f04a` → `0x28a6c`：攻擊目標／全螢幕攻擊演出 | 攻擊（case 0） |
| 1 | ← | `0x1cff0`：配置 320×200 演出 buffer、法術 command／演出 loop（`0x1c269` 失敗會 disable） | 法術選單（case 1） |
| 2 | → | `0x1bbdc`：item action loop；case 0 讀 item record `+0xd/+0x10/+0x12/+0x15`、做 target geometry，進 `0x20c6f` effect/target path；case 1 transfer uses `0x1bb8c` insertion + `0x1b8e7` removal；case 2 `0x1bffe` equips via `0x1c1c3` compatibility + `0x1c142` slot flags | 物品（case 2） |
| 3 | ↓ | `0x13fd4`（未移動時 HP/狀態處理）→ `0x190ac` 格子互動／寶物檢查 | 待機／格子互動（case 3） |

因此撤回舊 mapping「↑道具／←攻擊／→魔法／↓待機」。`0x1cff0` 的 command-`0x1e` spell path 已證實；family priority、damage/effect jump table 仍待完整拆解，本表不宣稱所有 effect 已完成。

### `0x1cff0` command evidence（2026-07-25, Docker Capstone）

`0x1cff0` 會以 `[0x3c57]` 選中的 byte 從 local command array 取出 `0x4e516` record。修正舊筆記：MP gate 是 record `+5`（`0x159fa` 的 direct compare），不是 `+4`；`+3/+4/+6` 在本 selector 的 geometry/control path 都有讀取，但未追到 field-name 前仍只能保留 raw offsets。已釘死的分支：command `0x17` 走特殊 target geometry（`0x14818`，使用 record `+6`）；command `0x1e` 走 `record+3-0x10` → `0x149f8` 的 spell-family path；其他 command 走 `0x2a6bd` 或 `0x1d6c8` jump-table effect path，最後統一回 `0x1aa1d`／`0x1d4f6` 收尾。

官方 IDA 9.4 的 `0x1d3f3` dispatch 再釘細一層：target confirm 後 command ID `0..8`、`0x18`、以及 `>=0x1c` 直接呼叫 `0x2a6bd(unit, commandID, target, scratch)`；ID `0x09..0x17` 與 `0x19..0x1b` 則先以 `0x1d6c8(commandID)` 做四輪 palette flicker，再呼叫 `funcs_1541f[commandID]` effect jump table。故悠妮 source mask 的 command 0 已能證實進 generic effect pipeline，卻尚未證實其效果名、傷害公式或等同 legacy `Spells[0]`；remake 對 unknown effect 必須繼續 fail-closed。

後續 direct dataflow 已閉合 command 0 的數值 writer：`0x2a6bd` 對每個 target 呼叫 `0x1c75e(target,commandID)`；它讀 command record `u16+0`／byte `+2`，以 target class ID（constructor 寫入 unit `+0x20`）索引 `word_51f96` 形成 base、擲 `rand()%100 < record[+2]`，命中才由 `0x1c81f` 以 90% 加 0..9.9% random 的整數值扣 target `+0x40`，clamp 0。`word_51f96` 的 loaded file offset=`0x51d96`，就是 `resist_crit.json` 每職業的 `resist_raw`（每 row 4 bytes）；因此 base=`record.dmg*resist_raw/10`，等價於既有職業魔抗百分比。這是 native damage/HP ABI；command0 effect name、target family與 normalized spell equivalence 仍未證實。

同一條 caller dataflow 排除了「confirm 只傳回一個格子」的猜測：一般 record 先以 actor cell 的 `+3/+6` 呼叫 `0x14818` 產生可選中心 stack candidate-index array，`0x115b6` 接收 `(mode=+6,count,array)` 做游標／確認；成功後 `0x1cff0` 以**確認游標格**的 `+4/+6` 第二次呼叫 `0x14818`，`0x2a6bd` 接到的是這個第二 array/count，並逐 element 呼叫 `0x1c75e`。故 command0 有 per-final-effect-candidate 傷害，而 `+6` target-code 的值域與 `0x14818` geometry 仍須逐值 RE；現有單格 normalized target UI 不是原版證明。

`0x14818` 本體現已釘其 raw geometry：record `+3 < 0x10` 時交由 `0x4e555` 產生 map/reach mask；`+3 >= 0x10`
時只 mark 同 x 或同 y、距離不超過 `(+3-0x10)` 的十字格。接著掃 roster，略過 inactive unit 與 mask=`0xff` 格，再用 record `+6` 篩 runtime `unit+6`：code 0 要 `==0`、1 要 `!=0`、2 要 `!=1`、3 要 `==2`。`0x10c50` constructor 已證實 `unit+6` 是 FDFIELD `b0` camp（0敵/1友/2己）；故 code 0=敵、1=非敵、2=非友、3=己。這是 direct branch evidence。

上述 `dist<0x10` 不是無條件 Manhattan：`0x4e555(0)` 回傳 20-byte cost row，真正的 `0x4e040` 以 `dist`
做四方向 flood-fill，grid flag `0x40` 不可通過、`0x80` 的格成本視為 0。對 command selector 而言 row index 固定
為 0，EXE `word_61646` 的該 20-byte row 全為 1；故不套地形加權，但障礙仍可使可達格少於 Manhattan circle。
remake `InCastRange` 仍不能作為 native contract，除非也帶入同一 grid flags。

`0x149f8` 的本體語意是 target-candidate builder：依起點／方向步進 `count` 次，做地圖邊界檢查，呼叫 `0x12c0d` 取 unit，依 selector 篩選 `unit+6` 狀態後把 unit index 寫入輸出陣列。一般 AI caller 的 selector-family 對照仍待 RE；但玩家 ID30 已由 `0x1d339` 的完整 push 順序閉合為一條不同的 special line（如下）。

`0x115b6` 的 confirm loop 已直接讀 `0x53ab1/0x53ab5`，並以兩值比對 runtime unit `+0/+1`；方向鍵 helpers 改寫同一對 globals。因此它們是這條 selector 的 cursor cell，而不是相機 scroll。ID30 的 `0x1d287..0x1d354` 先以 record `+3=0x14` 的 normal `0x14818` candidate list 確認一個 enemy cursor，保存確認前 cursor `(savedX,savedY)`，再傳確認後 cursor `(confirmedX,confirmedY)` 給 `0x149f8`。callee 的七個 args 已可靜態對應：output、confirmed X/Y、saved X/Y、`count=record+3-0x10=4`、selector=1。它從 saved cell **先走一步**，若 X 不同則只走 X（savedX>confirmedX 為 −1，否則 +1）；僅 X 相同才以同規則走 Y；兩座標相同落入原始 `<=` 的 +Y branch。每一步由 `0x12c0d` 取得第一個 active unit，selector=1 僅收 native camp=0（Go `Enemy`），越界只是略過。故 ID30 是「保存游標→確認游標」的最多四格 cardinal line，不是 actor→confirmed 的 generic ray，也不走第二次 `0x14818`。`ExecuteNativeCommand30` 已用顯式兩 cursor 接 strict final state slice；native cursor UI、multi-hit indexed presentation、SFX 仍未接。

### `0x1bbdc` item action evidence（2026-07-25, Docker Capstone）

物品 action 不是「完全不存在」：`0x1b932` 是 8-slot selector（status `0x80` 空槽、`0x40` equipped；方向鍵/wrap、Enter/Space、ESC）。`0x1bb8c` 只把 item 插入第一個空槽；case 1 將它與 `0x1b8e7` removal 串成 transfer。case 2 進入 `0x1bffe`，由 `0x1c1c3` compatibility predicate 與 `0x1c142` 設定選中 slot 的 `0x40` flag，再呼叫 `0x1b750` 重算。case 0 讀 `+0xd/+0x10/+0x12/+0x15`，其 effect/target callee 是 `0x20c6f`，仍未解碼；`type=0x17` 有 class/level gate（角色 `+8==0x18` 時另要求 level `+0x46 >= 20`）。因此 remake item action 繼續 fail-closed，不以 shop/inventory code 冒充戰鬥 item use。

`0x20c6f` 已再以 Docker Capstone 展開：它依 item `+0xd` type 分派至多個原生 effect routines（例如 type `5/0xd→0x211a4`、`6/7→0x22af6`、`8/9/0xa→0x21082`、`0xe/0xf/0x10→0x22d1b/0x22866/0x22721`、`0x15→0x2111a`、`0x17→0x2218a`），並在部分分支更新 unit state、顯示 effect、最後統一回收選取／戰鬥 UI。這只證實 type-dispatch 與具體 callee provenance；各 routine 的數值語意尚未閉合，不能直接映射成藥水／卷軸規則。

其中 type `8/9/0xa→0x21082` 的 body 可再確認為「以 caller 傳入的 unit-field offset 加上一個 word modifier，顯示 type `0x5e` effect，呼叫 `0x1b750` 重算，再移除來源 slot」；offset 與 modifier 的 item-table 對應尚未證實，故不命名成 HP/MP/AP 等具體效果。type `6/7→0x22af6` 則掃描 target list，依 target unit `+0x20/+0x21` 計算 accumulator 並清除已處理 target，仍不足以判定傷害／恢復方向。

type `0x17→0x2218a` 也已展開：它先以 target unit `+0x20/+0x21` 算入全域 accumulator，呼叫 `0x22253`（native indexed off-screen renderer）做專用演出，並將 caller 提供的兩個 byte 寫回 target unit `+0/+1`。這證實 type `0x17` 是帶有 renderer/state-write 的特殊 item branch；`+0/+1` 的欄位語意及 class/level gate 之外的規則仍未證實，不能命名為轉職、復活或其他具體玩法。

選單游標導航在 `0x1864D` 一帶,用 PC 方向鍵掃描碼:

| 掃描碼 | 鍵 | 行為 |
|---|---|---|
| `0x48` | ↑ | 上移選項 |
| `0x50` | ↓ | `[ebx+0xc]==0` 時 `[0x3C57]=3` |
| `0x4B` | ← | `[ebx+4]==0` 時 `[0x3C57]=1` |
| `0x4D` | → | `[ebx+8]==0` 時 `[0x3C57]=2` |

- **`[0x3C57]`** = 目前選到的選項編號(全域)。↑→0、(其餘方向)→1/2/3。
- `[ebx]` / `[ebx+4]` / `[ebx+8]` / `[ebx+0xC]` = 上/左/右/下各方向是否有可移動到的相鄰選項
  (選單為 2D 排列,該方向無項目(旗標≠0)就不動)。
- 「方向鍵移到神祕商店」(攻略 #16,`0x2DBF3` 等多處)= 商店畫面的方向鍵游標邊界判定。

### 確認 / 取消鍵(已反組譯 `0x18610`)

選單主迴圈 `call 0x18698` 取鍵後:

| 鍵 | 掃描碼 | 行為 |
|---|---|---|
| **Enter** | `0x1C` | 確認 / 選定(函式回傳 1) |
| **Space** | `0x39` | 同 Enter,確認 / 選定 |
| **ESC** | `0x01` | 取消 / 返回(`0x18698` 回傳 1 → 外層回傳 −1 = 取消) |
| ↑ ↓ ← → | `0x48 0x50 0x4B 0x4D` | 移動游標 `[0x3C57]`(受各方向啟用旗標 gate) |

→ **「ESC 取消、Enter / Space 確認」的離開語意在原版即成立**(ESC 比較在 EXE 出現 72 處 = 各層皆可退)。

## 相關全域 / 結構

- `[0x3C57]` 選單游標選項;`[0x3C43]`/`[0x3C47]`/`[0x3C4B]`/`[0x3C4F]` AI 最佳落點/目標(見 11-…)。
- 單位陣列 `[0x3A45]`,每單位 0x50,數量 `[0x3BEB]`;行動狀態 `AA`(0x0D)。

## 重製對應(SDL2 / Ebiten)

| 原版 | 現代 |
|---|---|
| AA 行動狀態(00/01/80) | unit.state enum(idle/dead/done),回合結束條件 = 全 done |
| flood-fill 移動範圍 | BFS/Dijkstra(MV + 地形成本)→ 高亮可走格 |
| `[0x3C57]` 選單游標 + 方向鍵 | 選單元件,↑↓←→ 導航、Enter 確認、ESC 取消(見離開鐵則) |
| Get_EasyMagic | 依 native magic raw／command inventory 動態產生法術選單（`+0x22..+0x24` 不是 bitfield） |
| 選目標範圍判定 | 共用攻擊/法術 range + LOS 計算 |

## 待辦(後輪)
- 反組譯選單繪製與選項表,確認確切選項與排列(2D 位置)。
- ✅ 按鍵綁定(Enter/Space 確認、ESC 取消、方向鍵)— 已反組譯。
- [~] `Get_EasyMagic`(0x18ED0) 的 UI caller 已定位；magic raw=`+0x1a..+0x1d`、`+0x22..+0x24` 僅保留 raw transient/modifier bytes，完整 bit 展開與高階欄位語意仍待重審。
- 各選項的 enable gate 條件(已移動 / MP / 道具 / 攻擊範圍內有無目標)的完整反組譯。
- command bits → 可選 command／spell ID 的完整展開（法術編號見 `02`/`03`）。
