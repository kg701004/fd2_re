# 32 — 物品 / 戰鬥數值系統反組譯(進行中)

> 目標:反組譯「裝備如何加成 AP/DP」「物品使用效果」「轉職」,供 M1 戰鬥結算用。
> 本篇記錄**已確認**與**待續**(誠實標註,rulebook 62/63)。本輪深度有限,物品/轉職機制需後續多輪。

## 1. 物品表結構 [驗](EXE `0x540AC`,23B/item,215 筆)

`dump_exe_tables.py` → `docs/data/exe_tables/item.json`:
```
-- TY AP AP HT HT DP DP EV EV S1 S2 R1 R2 K1..K6 MM MM ...
   type  ap(u16) hit(u16) dp(u16) ev(u16) atk_attr atk_rate range[2] K[6] price(u16)
```
例:item#64 `type7 ap80 hit95 price1200`(武器,攻擊力+80)。→ **物品帶 ap/dp/hit/ev 加值**,裝備時加到單位。

## 2. 傷害計算鏈 [驗]

```
攻擊執行(大函式 0x15xxx,含演出+結算)
   ├ 算攻方 AP → 全域暫存 [0x53c27](0x15aff 寫)
   ├ 算守方 DP → 全域暫存 [0x53c2b](0x15b08 寫)
   └ 舊筆記標為 0x15356 的傷害公式（地址未由 canonical scan 證實）：
        normalized dmg = AP×地形AP%[地形]/100 − DP×地形DP%[地形]/100
        （地形表 0x1A12 / 0x1A2A；`dmg≤2`/擊殺加成不得當作 native AI 證據）
```
即 **normalized/remake 的傷害估值**可使用 `[0x53c27]`/`[0x53c2b]` 作 raw lead；canonical scan 尚未證明 `0x15356` 是 native callee，也不能以此行宣稱完整 attack/AI parity。

## 3. 已知操作(攻略/doc 13)

- 物品選單(移動後「右」):**使用 / 給予 / 裝備 / 丟棄**(notes.md)。
- 裝備自帶法術不耗 MP、但施放無經驗(item.md)。賣價 = 原價 75 折。
- 單位 roster 26B 含 **物品×8 + 法術×8**(parse_field;即每單位 8 裝備欄 + 8 法術欄)。

## 3.5 主角隊起始武器 + AP/HIT/EV 合成公式 [驗](worklist 第8輪後,對 orig_07 截圖逐位吻合)

**人物出場屬性表**(modify2 §4,EXE `0x55BA1`,anchor `01 01 01 2A`,24B/人物,順序同 growth 表 §5):
`RA(1) CL(1) LV(1) HP(u16) MP(u16) MV(1) MG(4) IT(6) AP(u16) DP(u16) DX(u16)`。IT[0]=起始武器 id、
IT[1]=起始防具 id(FDFIELD 出場人物資訊同款慣例:前兩個固定武器+防具)。此表 `dump_exe_tables.py` 尚未收錄
(anchor 早已定義,缺 `dump_char()`),本輪用臨時腳本直讀驗證,未來若需其他角色可補上該函式。

索爾(idx0)/亞雷斯(idx4)/悠妮(idx9)/蓋亞(idx30,索引與 growth 表 §5 一致)起始武器/防具:

| 角色 | 職業 | 武器 id | 武器 | 防具 id | 防具 |
|---|---|---|---|---|---|
| 索爾 | 劍士 | 0x00 | 短劍(AP10 HIT95) | 0x84 | 皮甲(DP8) |
| 亞雷斯 | 騎士 | 0x14 | 刺矛(AP20 HIT90 射程1-2) | 0x80 | 布衣(DP2) |
| 悠妮 | 法師 | 0x34 | 長棍(AP8 HIT85) | 0xA4 | 長袍(DP5) |
| 蓋亞 | 機兵 | 0x48 | 威力手臂(AP15 HIT90) | 0xB2 | 戰鬥裝甲(DP8) |

**合成公式(對 `extracted/remake_shots/orig_07_unit_status.png` 索爾逐位吻合,LV·01 DX·002 HIT·097 AP·016 EV·002 DP·012)**:

```
角色底值(空身無裝備,list.md §7.3 交叉驗證) = char表base + LV×growth_min(AP/DP同理;HP/MP用(LV-1))
有效 AP  = 角色底 AP + 武器.ap                  (索爾 6+10=16 ✓)
有效 DP  = 角色底 DP + 防具.dp                  (索爾 4+8=12 ✓)
有效 HIT = 角色底 DX + 武器.hit                 (索爾 2+95=97 ✓ ←關鍵發現:item表HIT/EV是「增值」,非絕對值)
有效 EV  = 角色底 DX + 防具.ev                  (索爾 2+0=2  ✓;起始4件防具ev皆為0)
```

四人算出:索爾 AP16/DP12/HIT97/EV2/crit5%;亞雷斯 AP26/DP6/HIT92/EV2/crit3%;
悠妮 AP11/DP7/HIT86/EV1/crit3%;蓋亞 AP22/DP14/HIT92/EV2/crit0%(resist_crit.json 依職業)。
已串進 `internal/battle/event.go` PartyMember(新增 HIT/EV/CritPct 欄位 + spawn_party 賦值)與
`assets/scenarios/ch01.json`,修好主角隊 HIT=0 導致 100% miss / 0 傷害的問題。

> 此發現直接解答下方原「[阻] 裝備加成精確公式」——至少對「基礎四圍(AP/DP/HIT/EV)如何疊加裝備」已鎖死
> (DX 是 HIT/EV 的底值來源,item 表 HIT/EV 欄是疊加增量);轉職後 DX 底值/其他角色武器仍待逐一 RE。

## 4. 待續(需後續輪次)[阻]

### 4.0 2026-07-27 item row caller audit（新增證據）

官方 IDA 9.4 重新檢查 `0x4e56c` 的多個呼叫者，確認 raw row 的用途比單一攻擊 caller 更廣：

- `0x1145a` 與 `0x1b750` 都只在 inventory flag `&0x40` 時讀 row `+1/+3/+5/+7`，分別累加到衍生 AP/HIT/DP/EV；這是裝備合成資料流，不是 UI 顯示專用欄位。
- `0x14237` 讀 row `+0x0b/+0x0c` 後呼叫 `0x14818`；目前只把它記為 caller-specific geometry inputs，不能把 `+0x0b` 命名為通用射程上限。
- `0x1567e` 會讀 row `+0x0d/+0x10/+0x11/+0x12`，依分支呼叫 `0x14818` 或 `0x149f8`；這證實特殊物品效果共用幾何 routines，但仍不足以命名效果或欄位。
- `0x1bbdc`／`0x20c6f` 以 row `+0x0d` 做 type dispatch，並由不同原生 callee 消費；數值方向、顯示語意與 target ABI 仍未閉合。
- `0x1e0db(value, digitBias, target)` 只在 target 位於 camera bounds 時，把 `value` 轉成四位十進位字元，寫入四組 raw presentation queue（位置碼 `2,7,12,17`、target index 與 digit bytes），最後遞增 queue count。它不是 HP/MP/damage/heal 的命名 renderer；`0x1e1dc` 是相鄰的四 byte raw queue writer。
- `0x1debe(actor, x, y)` 只證實 active gate、曼哈頓相鄰一格與 equipped item row `+0x0b <= 1`；它不能推出 item `+0x0b` 是所有武器的通用最大射程。

因此目前安全結論是：`item.json` 的 normalized AP/HIT/DP/EV 與已驗證的 `weapon_range.json` 可供 remake 使用；raw table base `0x602ad`、stride `0x17` 已知，但 runtime table 邊界及其餘欄位仍 fail-closed，不能直接把 215 筆 normalized rows 宣稱為 runtime table 的完整證明。

### 4.1 2026-07-20 direct range-field trace（2026-07-27 勘誤）

以 `tools/disasm_le.py` 追 `0x318ad` 與 item pointer helper `0x4e56c` 後，欄位偏移更正如下：

```
+0x0 type, +0x01 AP, +0x03 HIT, +0x05 DP, +0x07 EV
+0x0a..+0x0d caller-specific raw inputs, +0x0e..0x13 K[6]
```

原先把這四個 byte 命名成 `atk_attr/atk_rate/range_min/range_max` 並把 `0x14237` 的 `+0x0c` 稱為通用 `range_min`，現撤回。已確認的安全描述是：`0x14237` 將 item row `+0x0b/+0x0c` 以 caller-specific 順序傳入 `0x14818` 的 `a5/a4`；`mode<0x10` 時 `a5` 會排除 marker cells，`mode>=0x10` 走 cross branch。另一條 `0x18d8c` 也讀相鄰 raw bytes，`+0x0d` 另有特殊 effect dispatch caller；這些都不足以反推出通用武器射程或 normalized `AtkMin/AtkMax`。

因此 remake 暫時只沿用已由 `weapon_range.json` 獨立驗證的 normalized 武器射程；不得把 raw `+0x0b..+0x0d` 臆測成 `AtkMin/AtkMax`。這輪只修正 provenance 斷言，不改變未證實的戰鬥公式。

- **[阻] 表 base-relative 存取**:item/unit/growth 表(0x540ac…)在 code 中以「obj2 基底(reg)+ offset」讀,
  絕對位址不經 fixup → 不能用 `refs` 直接找讀取點,要追基底暫存載入處。
- **[~] 物品使用效果碼**：`0x1bbdc` 的 selector／transfer／equip branches 已部分釘出：`0x1b932` 是保留八格空槽／裝備旗標的 selector、`0x1bb8c` first-empty-slot insertion、`0x1b8e7` source removal、`0x1bffe` equip；case 0 的 `0x20c6f` type dispatch 與數條 raw mutation route 已閉合，但 target-list producer、presentation 與玩法語意仍待解碼。remake 已接八格 item selector shell，保留 raw slot 空洞，Enter 對 case 0 只顯示 fail-closed 訊息，不改變 HP/MP/inventory。`+0xd/+0x10/+0x15` 與 `type=0x17` class/level gate 已知；藥水/卷軸等 gameplay mapping 不得由目前 raw route 猜出。
- Docker Capstone 也已閉合共用 item pointer `0x4e56c(item)`：table base `0x602ad`、row stride `0x17`（23 bytes）。這只確定 raw 定址；row 欄位與 table 長度尚未證實，不能把 bytes 直接填入本文件的 normalized `ItemStats`。
- `0x20c6f` 的 Docker trace 已確認 `item+0xd` type-dispatch 至 `0x211a4/0x22af6/0x21082/0x22d1b/0x22866/0x22721/0x2111a/0x2218a` 等原生 routines；這些 callee 的數值效果與顯示語意仍未完成，因此維持 fail-closed。
- `0x21082` 已確認是 modifier-word + unit-field-offset、effect display、`0x1b750` synthesis、source removal 的共同路徑；`0x22af6` 已確認掃 target list 並累加全域結果，但兩者的 item-table 欄位對應與正負方向仍不可命名。
- `0x20c6f`→`0x21082` 的 type 8/9/0xa raw route 已補閉合：三者分別把 item row `+0xe` word 作 delta，將 target raw word 寫入 offsets `0x37/0x39/0x3e`，並傳 presentation selectors `0x11/0x12/0x13`；這些 offset/selector 仍保持 opaque，不命名成 HP/MP/AP 或其他玩法。
- `0x211a4`（item type `5/0xd`）已由 Docker Capstone 閉合部分資料流：先以 raw subcommand `0xd` 建立／清除 target context，再逐 supplied byte list 呼叫 `0x1c916`（word amount + target byte），並呼叫 `0x1e0db` 做 presentation。這只證實 list-driven mutation topology，不能把 type 命名成治療／藥水；caller 的 list/count/amount ABI 與 effect fields 尚待。
- `0x1c916` 的 raw HP mutation 已新增 `battle.ApplyNativeRawHPRestore` regression：RNG step、`amount*9/10 + (rng%100)*amount/1000`、`+0x40` cap `+0x42` 與 raw score gate 均保存；仍不把它接成 normalized heal/item effect。
- 相鄰 `0x1c9dd` MP path 亦已新增 `battle.ApplyNativeRawMPRestore`：同一 arithmetic 寫 `+0x44`/cap `+0x46`，但 score 僅用 `+0x21`、沒有 HP 的 class bonus；仍保持 raw adapter。
- type `21→0x2111a` 已補 raw topology：`0x1c4cc` context → `0x1cac7` 對 selected record `+0x44` 減去 `0x4e516` 來源 byte（16-bit wrap）→ target list `0x1c75e`/`0x1e0db`。來源 record、byte 與 list ABI 尚未命名成 MP cost／具體效果。
- 新增 `battle.ApplyNativeRawWordSubtract` 保存該 subtract core 的 `(unit, wordOffset, byteAmount)`、low-16 wrap 與 bounds regression；不取代 normalized `SpendNativeCommandMP`，也不替 raw word 命名。
- `0x22af6` common flag branch 已新增 `battle.ApplyNativeRawFlagRestore`：nonzero paired flag 才以 raw `0x1c916(target,10)` 恢復、清 flag、累加 `effective*4`；flag/status 語意與 presentation 保持未命名。
- `0x22d1b` application branch 已新增 `battle.ApplyNativeRawApplication` 與 `ApplyNativeHPDamage`：保存 marker-zero/class gate、兩次 RNG、raw HP subtract、marker `(rng%4)+2` 與 `8*+0x21` accumulator；不接 status/UI 名稱。
- type `0x17→0x2218a` 已確認會呼叫 `0x22253` indexed renderer，並寫 target unit `+0/+1`；這是特殊 state/演出 branch，但欄位與玩法語意仍保持 unknown。
- **[阻] 轉職系統**:攻略層有(Lv20+教會、轉職道具表 58h–60h→英雄/聖者/召喚師…,doc 02 §5.10);反組譯機制(職業數值替換、能力繼承、成長表切換)未做。
- **[阻] 轉職與 sprite**:角色 id = 肖像 = sprite組 恆等(doc 31,memory.md 權威);轉職後換成轉職態肖像編號(memory.md 0x20–0x41),sprite組是否隨之切到另一組**待反組譯轉職碼確認**。⚠ 舊版「凱拉斯組17→49、轉職當機」已作廢(DATO_067 誤判,凱拉斯實為 id16,三者恆等)。

## 5. 對 remake 的暫行做法

數值都在 `item.json` / `unit.json` / `growth.json` + 攻略公式(doc 02 §4),所以 **M1 僅可作 normalized vertical slice：暫用「base(unit表)+裝備(item表 ap/dp)」與攻略公式**；這不是 native item/stat source 的證明，也不得接入 native command/effect/UI 或宣稱原版一致。反組譯機制(精確累加/使用效果/轉職)仍需後續校正，不阻塞戰鬥切片。

> 相關:doc 02(數值/公式)· 03(EXE 表)· 11(AI/傷害)· 13(物品選單)· 27(戰鬥規則)。資料:`docs/data/exe_tables/`。
