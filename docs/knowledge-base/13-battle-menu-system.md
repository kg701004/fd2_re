# 13 — 戰場選單與行動系統

> 戰棋上選一個我方單位後,怎麼移動、怎麼跳出行動選單(攻擊/法術/道具/待機/狀態)、
> 游標怎麼操作、一個單位的「一回合」怎麼算完。第 3 輪反組譯 `FD2.EXE`。

## 一個單位的回合:行動狀態機

每個場上單位的行動狀態在結構欄位 **`AA`(0x0D)**(見 `03-…`):

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

選單項目(典型戰棋):**移動 / 攻擊 / 法術 / 道具 / 待機 / 狀態**。
- **攻擊 / 法術**選後進入「選目標」(範圍 / 視線判定,與 AI 共用 `0x1ECBE`/`0x4F355`)。
- 各選項是否可選依當下狀態 gate(已移動?MP 夠不夠?有無道具?)。

### `Get_EasyMagic` — 法術 / 狀態面板(已反組譯 `0x18ED0+`)

EXE 內洩漏的函式名 `Get_EasyMagic`,位於 `0x18ED0` 起。逐一讀單位的 **5 組法術 bitfield
`M1–M5`(結構 0x22–0x26)**,判斷該組是否已習得法術:

```
for 第 k 組(0x22..0x26):
    if  [ebx+0x22+k] != 0 :  顯示「可用」標記(glyph 0x77)
    else                  :  顯示「不可用」標記(glyph 0x2A)
    並繪出對應數值(HP [ebx+0x48] / MP [ebx+0x4C] 等)
```

→ 即玩家按「法術」時看到的面板:**哪幾系法術可用 + 目前 HP/MP**。繪字 / 數字用 `0x195D6`(在 320 寬 buffer 定位繪製)。實際施法時再由各組 bitfield 展開成可選法術清單(法術編號見 `02`/`03`)。

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
| 2 | → | `0x1bbdc`：讀 item record `+0xd/+0x10/+0x12/+0x15`、做 range/effect selection，特殊 item `0x17` 另有 gate | 物品（case 2） |
| 3 | ↓ | `0x13fd4`（未移動時 HP/狀態處理）→ `0x190ac` 格子互動／寶物檢查 | 待機／格子互動（case 3） |

因此撤回舊 mapping「↑道具／←攻擊／→魔法／↓待機」。`0x1cff0` 的 command-`0x1e` spell path 已證實；family priority、damage/effect jump table 仍待完整拆解，本表不宣稱所有 effect 已完成。

### `0x1cff0` command evidence（2026-07-25, Docker Capstone）

`0x1cff0` 會以 `[0x3c57]` 選中的 byte 從 local command array 取出 `0x4e516` record；record `+3` 是 command code，`+4` 參與 MP／費用欄位，`+6` 參與目標幾何。已釘死的分支：command `0x17` 走特殊 target geometry（`0x14818`，使用 record `+6`）；command `0x1e` 走 `record+3-0x10` → `0x149f8` 的 spell-family path；其他 command 走 `0x2a6bd` 或 `0x1d6c8` jump-table effect path，最後統一回 `0x1aa1d`／`0x1d4f6` 收尾。

因此「法術 command 以 `command-0x10` 形成 spell id」已有 direct caller 證據；但 `0x149f8` 的 family-specific damage/target priority 與 jump-table 每項 effect 尚未完整 lower，remake 仍保持 partial。

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
| Get_EasyMagic | 依已習得法術(M1–M5 bitfield)動態產生法術選單 |
| 選目標範圍判定 | 共用攻擊/法術 range + LOS 計算 |

## 待辦(後輪)
- 反組譯選單繪製與選項表,確認確切選項與排列(2D 位置)。
- ✅ 按鍵綁定(Enter/Space 確認、ESC 取消、方向鍵)— 已反組譯。
- ✅ `Get_EasyMagic`(0x18ED0,讀 M1–M5 bitfield 顯示可用法術 + HP/MP)— 已反組譯。
- 各選項的 enable gate 條件(已移動 / MP / 道具 / 攻擊範圍內有無目標)的完整反組譯。
- 施法時各 bitfield → 可選法術清單的展開(法術編號見 `02`/`03`)。
