# 32 — 物品 / 戰鬥數值系統反組譯(進行中)

> 目標:反組譯「裝備如何加成 AP/DP」「物品使用效果」「轉職」,供 M1 戰鬥結算用。
> 本篇記錄**已確認**與**待續**(誠實標註,rulebook 62/63)。本輪深度有限,物品/轉職機制需後續多輪。

## 1. 物品表的兩種錯位視圖 [驗](2026-07-27 勘誤)

`dump_exe_tables.py` 的攻略／normalized 視圖從 EXE file `0x540AC` 起，以
23B/item 匯出目前攻略列出的 215 個 ID 到 `docs/data/exe_tables/item.json`：
```
-- TY AP AP HT HT DP DP EV EV S1 S2 R1 R2 K1..K6 MM MM ...
   type  ap(u16) hit(u16) dp(u16) ev(u16) atk_attr atk_rate range[2] K[6] price(u16)
```
例:item#64 `type7 ap80 hit95 price1200`(武器,攻擊力+80)。→ **物品帶 ap/dp/hit/ev 加值**,裝備時加到單位。

這不是 `0x4e56c` 回傳指標的同一個 row 起點。Docker data dump 與 EXE
逐 byte 比對確認：原生 helper 的 linear `0x602AD` 對應 file `0x540AD`，
也就是比上述 normalized view 向後一 byte；stride 同為 `0x17`。因此 runtime
row 0 是 normalized row 0 的 bytes 1..22 再接 normalized row 1 的 byte 0，
不能直接把兩份資料用相同 offset 命名。

匯出器現在另產生 `native_item_effect_rows.json`，保存 215 個已知 ID 的 raw
runtime prefix，並在 docs 與 remake assets 各追蹤一份。這只閉合「已知 prefix
的逐 byte producer」，不證明 native table 正好在 ID 214 結束。

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

## 3.6 六張核心數值表對現有 EXE 逐 byte 驗證 [驗](2026-08-19)

來源：使用者提供一份含精確 hex offset 的靜態資料表(內容詳實到單一 byte 結構，疑似來自
modify2 系外部攻略/逆向資源)。本輪用 Python 直接 `seek`/`read` 現有 `FD2.EXE`
(509158 B，即 doc03 §B 所稱「新版」，唯一可用的一份)逐 byte 核對，不只驗 anchor，
每張表的**每一列**都比對。完整結果：

| 表 | offset | 列數 | 結果 |
|---|---|---|---|
| 人物出場屬性(24B/人) | 0x7ADB5 | anchor 驗證(使用者未提供逐列表) | ✓ `01 01 01 2A` 精確吻合 |
| 升級成長(11B/人) | 0x7B0B5 | 66 列 | ✓ 全部逐 byte 吻合 |
| 法術習得等級(12B/項) | 0x7B6C7 | 20 列 | ✓ 全部逐 byte 吻合 |
| 職業魔法抗性(4B/職業) | 0x76FAA | 26 職業 | ✓ 全部吻合(含「？？？」1Ah 職 60% 抗性) |
| 職業暴擊率(1B/職業) | ~~0x773AF~~ **0x774BC** | 26 職業 | ✓ 內容吻合，但**使用者/攻略給的 offset 錯了**，全檔案唯一符合 `05 03 03 05` anchor 的位置是 `0x774BC`，差原記載 `0x10D` byte |
| 敵/友等級資訊(10B/單位) | 0x7AB0D | 60 列(6 友 + 54 敵) | 59/60 吻合，1 處數值錯誤：見下 |

**發現的兩處外部資料錯誤**(均已用 EXE bytes 裁決，不是新舊版差異)：

1. **職業暴擊率表 offset 錯誤**：`0x76FAA`(職業魔法抗性表起點)到下一個已知表之間，
   全檔 `find()` 只有唯一一處 `05 03 03 05` 吻合，位於 `0x774BC`，不是原記載的 `0x773AF`。
   其餘 5 張表的新版(0x7xxxx)/舊版(0x5xxxx)offset 差全部精確等於固定值 `0x25214`；
   若把這個固定位移套用到暴擊表的舊版 offset `0x5219B`，理論新版位置正是
   `0x5219B+0x25214=0x774AF`，跟實測的 `0x774BC` 仍差 `0xD`（未到位元組級精確，但已比
   `0x773AF` 更接近真值，可能舊版本身在這張表附近也有幾 byte 版本差；不影響結論——內容比對
   已鎖定 `0x774BC` 是本 EXE 裡的正確位置)。已回頭訂正 `03-exe-and-data-structures.md` 表格。
2. **大惡魔(RA 5, CL 0x1A, `0x7ACB1` 列)AP 成長值**：使用者提供的表格寫 `31`，EXE 實際 bytes
   (`0x7ACB1+5`=`0x21`)是 `33`。`docs/data/exe_tables/unit.json` idx42(來自已遺失的舊版
   EXE，`0x55a9d`)同樣是 `"ap": 33`——新舊兩版一致，`33` 才是正確值，`31` 是外部表格轉錄
   筆誤。這個訂正在下方「續二十五 ch24 敵人模板」章節也有實際使用(大惡魔的真實 AP 影響
   ch24 反擊傷害量級估算)。

**人物出場屬性表(24B)欄位語意確認**：使用者提供的版面把資料畫成 2 行 × 16 欄(共 32 格，含
前 5 格與後 3 格的 `--` 佔位)，但表頭明寫「每個人物 24 byte」。實測 `0x7ADB5` 起 24 byte
(`01 01 01 2A 00 00 00 04 00 00 00 00 00 84 C0 FF FF FF 00 00 00 00 00 00`)顯示 magic
`01 01 01 2A` 就是這 24 byte 記錄的**開頭**(RA=01, CL=01, LV=01, HP 低位=0x2A)，不在畫面
中間；換句話說使用者原始素材裡的「兩行 32 欄」版面是十六進位傾印時跨列換行造成的視覺假象
(前 5、後 3 個 `--` 屬於鄰接記錄，不是本記錄的額外欄位)，真正的 24-byte 記錄欄位序列是：

```
RA(1) CL(1) LV(1) HP(u16) MP(u16) MV(1) MG(4) IT(6) AP(u16) DP(u16) DX(u16)  = 1+1+1+2+2+1+4+6+2+2+2 = 24B
```

與既有 §3.5「人物出場屬性表」記載的欄位序列完全一致，這輪只是把「為什麼使用者素材看起來
是 32 欄」的疑點解釋掉，不是新結論。

**敵/友單位表(0x7AB0D，10B)是「每級成長值」，不是 base 值——出場真實 MaxHP/MaxMP 公式**：
既有反組譯證據(constructor `0x10fe9`，函式範圍 `0x10db4..0x10e58`，見
SESSION-HANDOFF-2026-07-06.md 2026-07-27 條目)早已指出這張表對應的分支(`high_class`)公式是
`+0x42(MaxHP) = u16(record+2) * level`，另一分支(`lower_class`，即人物出場屬性表 + 升級成長
表那組)才是玩家角色熟悉的 `base+(LV-1)*growth`。本輪用這張表(已逐 byte 驗證)實際代入
ch24 `remake/assets/maps/map24/map24_units.json` 的多筆單位驗算，全部與 JSON 已算好的
`native_record_word42`/`native_record_word46` 精確相符(例：惡魔 LV14，HP 成長值 40 → 40×14=560，
MP 成長值 5 → 5×14=70，與 JSON `native_record_word42:560`／`native_record_word46:70` 完全一致)。
**MaxMP 用同一套公式**(`+0x46 = u16(record+4-ish MP growth) * level`，本輪未見獨立否證)。
**AP/DP/DX 是否也套用同一 growth×level 公式仍未被獨立反組譯證實**——這是下面「續二十五」
ch24 謎團調查的關鍵未決點，remake 匯出的 map JSON 目前 `ap`/`dp`/`mv` 欄位是每個單位共用的
佔位值(`20`/`12`/`6`)，不是依 growth 表算出的真實值，不能拿來當佐證或反證。

## 4. 待續(需後續輪次)[阻]

### 4.0 2026-07-27 item row caller audit（新增證據）

官方 IDA 9.4 重新檢查 `0x4e56c` 的多個呼叫者，確認 raw row 的用途比單一攻擊 caller 更廣：

- `0x1145a` 與 `0x1b750` 都只在 inventory flag `&0x40` 時讀 row
  `+1/+3/+5/+7`；215 個已知 raw rows 已逐筆與 normalized `item.json`
  交叉，四個 little-endian words 全數等於 AP/HIT/DP/EV。這是裝備合成
  資料流，不是 UI 顯示專用欄位。
- `0x14237` 讀 row `+0x0b/+0x0c` 後呼叫 `0x14818`；目前只把它記為 caller-specific geometry inputs，不能把 `+0x0b` 命名為通用射程上限。
- `0x1567e` 會讀 row `+0x0d/+0x10/+0x11/+0x12`，依分支呼叫 `0x14818` 或 `0x149f8`；這證實特殊物品效果共用幾何 routines，但仍不足以命名效果或欄位。
- `0x1bbdc`／`0x20c6f` 以 row `+0x0d` 做 type dispatch，並由不同原生 callee 消費；數值方向、顯示語意與 target ABI 仍未閉合。
- `0x1e0db(value, digitBias, target)` 只在 target 位於 camera bounds 時，把 `value` 轉成四位十進位字元，寫入四組 raw presentation queue（位置碼 `2,7,12,17`、target index 與 digit bytes），最後遞增 queue count。它不是 HP/MP/damage/heal 的命名 renderer；`0x1e1dc` 是相鄰的四 byte raw queue writer。
- `0x1debe(actor, x, y)` 只證實 active gate、曼哈頓相鄰一格與 equipped item row `+0x0b <= 1`；它不能推出 item `+0x0b` 是所有武器的通用最大射程。

因此目前安全結論是：`item.json` 的 normalized AP/HIT/DP/EV 與已驗證的
`weapon_range.json` 可供 remake 使用；raw table base `0x602ad`、stride
`0x17` 與 215 個 ID 的 byte-exact prefix 已另存
`native_item_effect_rows.json`。runtime table 的最終邊界及其餘欄位仍
fail-closed，不能把 215 筆 prefix 宣稱為完整 table。

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
- **[~] 物品使用效果碼**：`0x1bbdc` 的 selector／transfer／equip branches
  與 observed type5–24 mutation routes已閉合。重要 UI correction：
  `0x1b9de/0x184c0` 不是把八個 raw holes原位顯示，而是依 signed flag
  非負 compact成兩欄四列；native writers 維持 occupied prefix。
  ↑/↓ linear wrap、←/→±4；battle-use Enter拒絕 effect type0。
  `NativeItemSelectorCells`／`AdvanceNativeItemSelector` 已保存 input、
  `(42/192,103+22r)` geometry、category/equipped/stat icon raw IDs。
  現行 remake shell仍保留八個 raw位置，是 provenance/debug UI而非原版
  parity；Enter transaction、indexed animation仍待接。
- Docker Capstone 也已閉合共用 item pointer `0x4e56c(item)`：table base
  `0x602ad`、row stride `0x17`（23 bytes）。EXE file view 已確認從
  `0x540ad` 起，與 normalized `item.json` 的 `0x540ac` 起點相差一 byte；
  215-row raw prefix 已獨立匯出並由 loader regression 固定。table 最終
  長度與其餘未命名欄位仍未證實；只有已全表交叉的 `+1/+3/+5/+7`
  可命名為 AP/HIT/DP/EV。
- `0x20c6f` 的 Docker trace 已確認完整 type dispatch；目前 typed gameplay
  closures 已覆蓋 5/13、8–12、14–16、22。其餘 callee 或 presentation
  語意仍依個別證據 fail-closed，不能再用「全部效果都未完成」的舊斷言
  掩蓋已閉合 routes。
- `0x21082` 已確認是 modifier-word + unit-field-offset、effect display、
  `0x1b750` synthesis、source removal 的共同路徑；`0x22af6` 已確認掃
  target list 並累加全域結果，但後者的 status/gameplay 名稱仍不可猜測。
- `0x20c6f`→`0x21082` 的 type 8/9/0xa 已閉合為永久 base-stat item：
  item row `+0xe` unsigned word 分別加到 persistent `+0x37/+0x39/+0x3e`
  的 base AP/DP/DX，經 `0x1b750` 重算後移除來源 slot。三筆已知 raw item
  IDs 198/199/200 的 amount 分別是 AP+9／DP+9／DX+7。presentation
  selectors `0x11/0x12/0x13` 的顯示名稱仍保持 opaque；共用 callee 的
  type17–19 由下列獨立欄位證據閉合，不套用 base AP/DP/DX 名稱。
- `0x211a4(actor,count,targetBytes,amount)` ABI 已由官方 IDA 9.4 閉合：
  `0x20c6f` 把自己的 `a3/a4` 直接作 count/list，item row `+0x0e` word
  作 HP restore amount；callee 依 list 順序逐筆呼叫
  `0x1c916(target,amount)`，寫 current HP `+0x40` 並 cap max HP
  `+0x42`。dispatcher 尾端進一步證實 type5 restore 後跳
  `0x1b8e7` 消耗來源 slot，type13 則保留來源。`ApplyNativeItemHPRestore`
  保存 sequential RNG、atomic preflight 與這個 consumption 分歧。
  道具顯示名稱、renderer/SFX 仍 fail-closed；共享 `0x211a4` 的非 item
  caller 不改變這兩條 item branch 的已證實語意。
- `0x1bbdc` target transaction 已由官方 IDA 9.4/Capstone 閉合：row `+0x10` 是 first-stage raw mode、`+0x15` 是兩階段共用 target code；只有 type `0x17` 的 first stage 帶 inner marker 1。確認後以 row `+0x12` 從 confirmed cell 建 final list，inner marker 固定 0。`NativeItemTargetPlanFromRow`／`NativeItemEffectTargets` 保存此 ABI、confirmed-candidate gate 與 raw grid flags；不把三個 byte命名為 normalized range/AOE。
- `0x1c916` 的 HP mutation 已新增 `battle.ApplyNativeRawHPRestore`
  regression：RNG step、`amount*9/10 + (rng%100)*amount/1000`、
  current HP `+0x40` cap max HP `+0x42` 與 raw score gate 均保存。
  此 helper 仍是 shared primitive；只有 caller 已閉合的 type5/13 item
  route 可宣稱 item HP restore。
- 相鄰 `0x1c9dd` MP path 亦已新增
  `battle.ApplyNativeRawMPRestore`：同一 arithmetic 寫 current MP
  `+0x44`、cap max MP `+0x46`，score 僅用 `+0x21`、沒有 HP class
  bonus。`0x20c6f` type11 caller 已閉合成 consumable MP restore：
  max MP 為零的 target 跳過且不消耗 RNG，其餘依 list 順序恢復，最後
  移除來源 slot；IDs206/207 amounts=80/200。
- type12 已閉合為 retained HIT/EV modifier：`0x22997` 只處理 marker
  `+0x24==0` 的 target，成功才前進 RNG、寫 `(rng%4)+2`，並把 derived
  HIT/EV `+0x4c/+0x4e` 各加 15；dispatcher 不呼 `0x1b8e7`。tracked
  raw row 是 ID210。marker 的玩家可見名稱仍未知。
- type15/16 已閉合為 retained DP/AP modifier：marker
  `+0x23/+0x22` 為零才前進 RNG並寫 `(rng%4)+2`；derived
  DP `+0x4a`／AP `+0x48` 分別增加 `trunc(current×0.15+1)`。dispatcher
  不移除來源，tracked rows 是 ID213/214。
- type17/18/19 已閉合為 consumable maxHP/maxMP/MV modifier：
  `+0x42/+0x46` 分別加 row amount20；type19 對 word `+0x3b` 加1，
  caller 在 `0x21082` 前後保存/恢復 byte `+0x3c`，故只改 MV byte、
  EXP 不變。三條都由共用 callee `0x1b8e7` 消耗來源；IDs94/95/96。
- type20/21/24 已由 official IDA 9.4 caller ABI 與 Docker Capstone
  重核閉合：row word 直接成為 `0x1c75e(target,commandID)` 的 command
  ID。20/24 用 `0x1cd17` 十幀 presentation，21 用
  `0x2111a→0x1cac7`；兩個 presentation helpers 都不做 gameplay
  mutation。dispatcher 沒有 `0x1ca89` MP debit 或 `0x1b8e7` inventory
  removal，故來源保留。type20 IDs11/56/60→commands2/0/2，
  type21 IDs29/38/51/99→6/1/7/6，type24 ID79→command3。
- `battle.ApplyNativeRawWordSubtract` 的 arithmetic core 實際對應
  `0x1ca89`，不是 `0x1cac7`；既有 normalized `SpendNativeCommandMP`
  才保存 verified selector-success MP transaction。type20/21/24
  都不呼叫兩者。
- `0x22af6` 舊 adapter 把 marker 當 caller-owned parallel `flags[]` 是錯的，
  已撤回。正確 ABI 是 target runtime `record+a5`：type6/7 分別用
  `+0x25/+0x26`，nonzero 才以 base amount10 經 `0x1c916` 實際恢復
  9 HP、清該 record marker，最後 `0x1b8e7` 消耗來源。
  `ApplyNativeItemMarkerClearRestore` 保存 record-local mutation、RNG 與
  atomic source preflight；IDs196/197。status/presentation 名稱仍未知。
- `0x22d1b` application branch 的舊「兩次 RNG／固定10 damage」斷言已
  撤回。正確順序是：gate RNG；成功後 `0x1c81f(...,baseAmount=10)`
  再消耗 damage RNG，實際整數結果為 9 HP；第三 RNG 寫 marker。
  type14/22 item callers 分別用 marker `+0x26/+0x27`，來源保留；
  `ApplyNativeItemMarkerApplication` 保存 class exclusion、50% gate、
  三次 RNG、HP mutation、marker與 atomic preflight。status/UI 名稱仍未知。
- type23 `0x2218a` 已閉合為 post-confirm direct relocation：只取第一
  target，以 command23 record cost 對 actor current MP `+0x44` 做
  16-bit subtract；target class `+0x20`／level `+0x21` 形成 raw
  accumulator delta，最後把 destination cursor bytes 寫入 target
  `+0/+1`。actor gate 是 identity `+8==24`、max MP `+0x46>=20`；
  dispatcher 保留來源物品。落點 mode-6 raw legality已定位，但完整
  predicate 現由 `NativeRelocationDestinationAllowed` 保存：排除 other
  raw-active occupant，依 target class/race/unit+7 選 29×20
  `0x4e555` editable cost row，目的地 terrain entry 必須為20。完整
  indexed renderer/Ebiten selector仍未接。
- **[~] 轉職系統**(worklist #247/M4):機制鏈(觸發→物品判定→數值替換→能力繼承→成長表切換)已由既有
  official IDA 9.4 + Docker Capstone 交叉證據閉合,本輪(2026-08-19)整理進 §6 並新增
  growth 表位址串接、道具↔職業表跨驗、本地 Ghidra 新版 EXE spot-check。**未閉合**:舊版
  (0x1e529/0x2a2e8/0x31571/0x3151a/0x526a7 等)地址在唯一倖存的新版 EXE 尚未重新定位;
  `class_change_targets.json` 的 portrait11–13 item_id 疑似輪轉錯位(見 §6.5)。詳見 §6。
- **[阻] 轉職與 sprite**：已撤回「角色 id = DATO 肖像 = FDICON
  sprite組」的全域恆等斷言。`unit+2` 是 `0x11019` 回傳的 FDICON
  raw-key cache slot，`unit+7` 有獨立 constructor／class-change writer；
  DATO portrait 又由場景文字／設施資源選取。轉職後 sprite、portrait 與
  persistent identity 的映射必須分別追 writer/caller，不能以相同數字推導。

## 5. 對 remake 的暫行做法

數值都在 `item.json` / `unit.json` / `growth.json` + 攻略公式(doc 02 §4),所以 **M1 僅可作 normalized vertical slice：暫用「base(unit表)+裝備(item表 ap/dp)」與攻略公式**；這不是 native item/stat source 的證明，也不得接入 native command/effect/UI 或宣稱原版一致。反組譯機制(精確累加/使用效果/轉職)仍需後續校正，不阻塞戰鬥切片。

> 相關:doc 02(數值/公式)· 03(EXE 表)· 11(AI/傷害)· 13(物品選單)· 27(戰鬥規則)。資料:`docs/data/exe_tables/`。

## 6. 轉職系統反組譯(worklist 第 247 行/M4)[部分驗](2026-08-19)

> 目標:轉職觸發(教會/道具)、職業數值替換、能力繼承、轉職後成長表切換,並與攻略道具表(勇者徽章→
> 英雄…)交叉驗。本節**不是本輪從零反組譯**——核心機制早在 2026-07-20/26/28 由 official IDA 9.4
> (`fd2-ida-authorized-local`)+ Docker Capstone 雙重閉合(見 `SESSION-HANDOFF-2026-07-06.md` 該幾日
> 條目、`remake/internal/campaign/church.go`/`class_change_table.go`),只是先前散落在 handoff log
> 未整理進正式 doc。本輪工作是:①整理成完整流程並附位址、②新增 growth 表位址串接證據(回答任務
> 背景提出的「轉職後升級表切換到哪裡」)、③用**本地 Ghidra 新版 EXE**(`FD2Analysis3`)重新 spot-check
> 這批位址是否在唯一倖存的 EXE 上仍站得住、④用資料本身(不靠新反組譯)交叉驗攻略道具表,順帶抓出一個
> 既有 JSON 的可疑錯位。

### 6.1 觸發流程(教會)

```
0x3072f  教會主選單:讀服務選擇,依 0..3 分派 0x2ffa5/0x2f8ea/0x30dc3/0x31385
0x31385  轉職服務入口:呼叫 0x31793 建候選 → 無候選顯示 FDTXT 0x24f,
         有候選顯示 0x250,confirm 後顯示 0x252
0x31793  候選/target resolver(見 §6.2)
0x311DC  三列可見角色清單(↑/↓ bounded scroll;`NativeClassCandidateWindow`/
         `NativeThreeRowWindow` 已還原視窗演算法);0x31019 逐列畫
         portrait/角色名/目前 class/FDTXT593/target class,
         selected/unselected palette index 201/205
0x19953  兩選項(是/否)確認 prompt,只認左右鍵,不 wrap(`AdvanceNativeClassConfirmation`)
```

**候選條件**(`0x31793` 的 exact filter,已由 `campaign.CanChangeClass` 還原):
`Lv >= 20 且 portrait < 0x12(18) 且 portrait != 7`。Lv20 門檻與攻略「等級20以上可到教會轉職」
(doc02 §2)一致;`portrait<0x12` 排除已轉職過的角色(轉職後 portrait 落在 0x20–0x43);`portrait!=7`
的原生排除原因未證實(蘭斯洛特初始即聖騎士,見 §6.5 邊界案例)。

### 6.2 職業數值替換 — target 判定與道具消耗

`0x31793` 對每個候選角色只解出**一個** target(不是同畫面多分支選單):

1. **Default**:`current_portrait + 0x20` 的固定 target(職業表見 `0x615fe`,見 §6.4)。
2. **Optional override**:若角色 inventory 有 `0x526a7[current_portrait]` 指定的 item id,改用
   `current_portrait + 0x32` 的 target 覆蓋 default。
3. **Special override**(僅 portrait 9=悠妮):若持有 item `0x5a`(精靈契印),最終覆寫成 target `0x34`
   (召喚師),優先權高於 optional。

```
0x3151a..0x3152d  依 portrait 查轉職道具:portrait 9 固定查 item 0x5a;
                  其餘 promoted portrait 由 0x526a7+portrait 這個 raw byte table 查
0x31860           掃角色 8 個 inventory slot 找該 item id
0x1b8e7           成功後移除該 inventory slot(標準 compact-remove primitive,
                  與物品使用消耗共用同一 callee)
```

remake 端 `NativeClassChangeTarget`(`class_change_table.go:105`)完整還原這個
default→optional→special 覆寫序,並用 `ClassChangeCandidates`/`CanChangeClass` 還原 §6.1 篩選。

### 6.3 能力繼承 — 累加不是覆寫

```
0x2a2e8  轉職重算入口(church 流程專用,與物品裝備後的 0x1b750 recalc 是不同 callee)
0x1e529  對五組 growth pair([min,max) 範圍,idiv 取值)逐一 roll 後 ADD 到既有 raw:
         +0x37 AP, +0x39 DP, +0x3e DX(HIT/EV 底值來源,見 §3.5), +0x42 MaxHP, +0x46 MaxMP
         尾端指令是 `add word [target], ax`,不是覆寫(2026-07-20 由使用者實測 PTT 表回報
         「轉職結果與原版差距巨大」逼出這個更正,見 handoff 381 行)
0x31571..0x3157a  寫 raw class byte(+0x20)與 portrait byte(+7);+0x1f 不動
```

- **Lv 保留**:整段流程沒有寫 level byte。
- **EXP 歸零**:raw `+0x3c` 清零。
- **HP/MP 全滿**:`+0x40`/`+0x44`(current)在重算後回填為新的 `+0x42`/`+0x46`(max)。
- **MV**:`0x4e48d(new portrait)+1` 的 mobility increment 加到 raw `+0x3b`(即
  `class_change_targets.json` 的 `mobility_increment` 欄)。

`ApplyClassChange`(`church.go:157`)逐項對應以上五個動作(`u.AP+=ap` 等 accumulate、
`u.HP=u.MaxHP`、`u.MV+=growthGroup`、`u.Exp=0`,Lv 未觸碰),並有 `campaign` 套件的
regression test 覆蓋。外部佐證:[PTT 實測表](https://www.ptt.cc/bbs/Dynasty/M.1185344950.A.91B.html)
與[轉職攻略](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/INDEX.html)皆
吻合「舊能力+新職成長」而非絕對重設。

### 6.4 成長表切換 — 確認 7B215 起就是轉職後的 reroll/leveling 表

任務背景問的是:轉職後升級改吃哪張表、是否就是 §3.6 驗證過的 `0x7B0B5` 66(實為 **68**,見下)列
成長表 idx32 起(`0x7B0B5+32*11=0x7B215`)。本輪把三條先前互相獨立的證據串起來,答案是**同一張表**:

| 證據來源 | 位址(舊版,SESSION-HANDOFF 2026-07-26) | 對應(新版,doc32 §3.6 已逐 byte 驗證) |
|---|---|---|
| `0x4e4d1(portrait)` 指標解出的 runtime 11-byte growth record | `0x620a1 + portrait*0x0b`(68×11) | — |
| item 表同款 file↔runtime 位移(§1 已證) | file `0x540AD` ↔ runtime `0x602AD`,差 `0xC200` | — |
| 本表對應 file 位址 | `0x620a1 − 0xC200 = 0x55EA1` | `0x55EA1 + 0x25214 = 0x7B0B5`(§3.6 已逐 byte 驗證,
  含固定新舊版位移 `0x25214`) |

`0x55EA1` 正是 `docs/data/exe_tables/growth.json` idx0 的 `off` 欄位——即 `0x4e4d1` 選出的
**就是** growth.json 這張表,不是另一張獨立表。`growth.json` 實際共 **68 列**(idx0–67,file `0x55ea1`
–`0x5618d`),不是 §3.6 舊記載的 66 列(該筆是使用者提供比對表當時只覆蓋 66 列,不是表本身只有 66
列;已在此更正)。列 0–31 對應 32 名角色的**基礎**(轉職前)成長,列 32–67(共 36 列)直接以
**target portrait**(`0x20`–`0x43`)索引,是轉職後的 reroll/leveling 共用列——`class_change_table.go`
的 `LoadClassChangeGrowth` 正是取 idx 32–67 這 36 列。換算成任務背景給的 offset:
`idx32` 的新版位址 `0x7B0B5+32*11 = 0x7B215` **精確吻合**背景提供的「轉職後升級屬性從 7B215 起」。

`unit+7`(FDFIELD roster byte1,doc45/doc31 已證)是這張表的 selector,對玩家角色即是「目前 portrait」;
轉職把 `unit+7` 從 0–17 範圍(對應 growth idx 0–31 的基礎成長)改寫成 0x20–0x43 範圍(對應 growth
idx 32–67 的轉職後成長),之後每次升級用的 growth row 自然跟著換——**「成長表切換」的真正機制不是換一張
表,而是同一張 68 列表裡切換 selector(portrait)所落在的區段**,§6.3 的一次性 reroll 與之後每級的固定
成長吃的是同一列。

### 6.5 攻略道具表交叉驗(doc02 §5.10/§7.1)

用 `docs/data/exe_tables/class_change_targets.json`(`current_portraits`/`target_portraits`,
2026-07-20 由官方 IDA 建立)+ `characters.json`(角色 index/portrait 對照)+ `class_equip_types.json`
的 classNames,逐 portrait 解出「角色→預設職業→道具→最高職業」,跟 doc02 §7.1 逐行核對:

| portrait | 角色 | 基礎(現有) | 預設轉職 | 道具(hex) | 進階轉職 | doc02 §7.1 對照 |
|---|---|---|---|---|---|---|
| 0 | 索爾 | 劍士 | 劍聖 | 0x59 勇者徽章 | 英雄 | ✓ 完全吻合 |
| 1 | 哈諾 | 戰士 | 聖戰士 | 0x5D 白金徽章 | 魔戰士 | ✓ 完全吻合 |
| 2 | 鐵諾 | 劍士 | 劍聖 | (無) | — | ✓ 吻合(無最高職業) |
| 3 | 哈瓦特 | 戰士 | 聖戰士 | 0x5D 白金徽章 | 魔戰士 | ✓ 完全吻合 |
| 4/5/6 | 亞雷斯/洛娜/萊汀 | 騎士 | 聖騎士 | 0xCD 飛龍卵 | 龍騎士 | ✓ 完全吻合(×3) |
| 7 | 蘭斯洛特 | 聖騎士(初始) | 聖騎士(self) | 0xCD 飛龍卵 | 龍騎士 | ⚠ doc02 未列蘭斯洛特有龍騎士路徑,見下 |
| 8 | 希莉亞 | 弓兵 | 狙擊手 | 0x5C 心眼之書 | 神射手 | ✓ 完全吻合 |
| 9 | 悠妮 | 法師 | 大法師 | 0x58 聖者之戒/0x5A(special) | 聖者/召喚師 | ✓ 完全吻合,含「限悠妮」 |
| 10 | 瑪琳 | 僧侶 | 祭師 | 0x58 聖者之戒 | 聖者 | ✓ 完全吻合 |
| 11 | 索菲亞 | 僧侶 | 祭師 | **0x5B 領悟之書** | 聖者 | ✗ doc02 記載應為 0x58 聖者之戒,見下 |
| 12 | 凱麗 | 武者 | 鬥士 | **0x5C 心眼之書** | 武聖 | ✗ doc02 記載應為 0x5B 領悟之書,見下 |
| 13 | 貝克威 | 弓兵 | 狙擊手 | **0x58 聖者之戒** | 神射手 | ✗ doc02 記載應為 0x5C 心眼之書,見下 |
| 14 | 珊 | 法師 | 大法師 | 0x58 聖者之戒 | 聖者 | ✓ 完全吻合 |
| 15 | 賽可邦勒 | 武者 | 鬥士 | 0x5B 領悟之書 | 武聖 | ✓ 完全吻合 |
| 16 | 凱拉斯 | 龍劍士(初始) | 聖戰士(?) | (無) | — | ⚠ 基礎已是龍劍士卻仍有轉職列,見下 |
| 17 | 米亞斯多德 | 劍士 | 龍劍士 | (無) | — | ✓ 吻合(無最高職業) |

18 筆裡 13 筆與攻略逐字吻合,3 筆(portrait 11/12/13)不吻合,2 筆(7/16)是攻略未提及的邊界情況:

- **portrait 11/12/13 的道具疑似輪轉錯位**:同職業配對本應共用同一道具(doc02 明寫瑪琳=索菲亞
  皆用聖者之戒、希莉亞=貝克威皆用心眼之書、凱麗=賽可邦勒皆用領悟之書),而 portrait 8/9/10/14/15
  這五筆都與配對角色一致,只有 11/12/13 這**連續三筆**的 item_id 恰好是「預期值的左旋一格」
  (`expected[11,12,13]=[58,5B,5C]` → `actual[11,12,13]=[5B,5C,58]`,即 `actual[i]=expected[i+1]`)。
  這個訊號型態(僅三筆、恰好循環位移、非隨機亂序)比較像 `class_change_targets.json` 原始建表時的
  欄位/列對齊疏失,而不是遊戲設計刻意讓同職業角色轉職道具互異——但**未經新版 EXE 位址重新定位**
  (見下),不能排除是遊戲本身如此、doc02 攻略才是簡化寫法。誠實標註為未決,列入 worklist 後續。
- **portrait 7(蘭斯洛特)**:原始表格顯示他即使基礎已是聖騎士,持有飛龍卵仍會被轉去龍騎士,但 doc02
  §7.1 該行寫「—」(無列出的最高職業)。可能是攻略遺漏,也可能是劇本從不讓他拿到飛龍卵而從未觸發;
  未進一步查證,列為已知落差。
- **portrait 16(凱拉斯)**:`characters.json` 顯示他基礎 `cls_name` 已是龍劍士(doc02 標「初始」),
  但 `current_portraits` 仍給他一筆 default→聖戰士的轉職列,語意矛盾。可能是
  `characters.json.face_portrait` 與這張轉職表用的 portrait 不是同一個編號空間(即凱拉斯的實際
  runtime class-change portrait 不是 16),尚未反組譯證實,列為已知落差、不臆測。

### 6.6 本地 Ghidra 新版 EXE spot-check(2026-08-19,readOnly, `FD2Analysis3`)

上述位址全部來自 2026-07 官方 IDA 9.4(Docker `fd2-ida-authorized-local`)工作,而該工具當時掛載的
EXE 已在 2026-08-14 確認遺失(見 memory「fd2_re EXE version mismatch」),專案現在唯一可用的是新版
EXE。本輪用 `analyzeHeadless -readOnly`(`ProbeClassChange.java`/`ProbeClassChangeItemTable.java`,
腳本留在 `FD2_ghidra_projects/`)對這批舊版位址逐一在**新版**上做 spot-check,結果:

- **`0x615fe`(target_portraits 的 class/mobility pair 表)在新版同一位址逐 byte 吻合**——直接讀出
  `09 01 0a 00 09 01 0a 00 0b 01 0b 01 0b 01 0b 01 0c 01 0d 01 0e 01 0e 01 10 00 0c 01 0d 01 10 00
  0a 00 0f 01 11 02 12 00`,與 `class_change_targets.json` `target_portraits[32..51]` 逐項相符。這是
  本輪新增的、對新版 EXE 的第一手獨立佐證。
- **`0x526a7`(current_portraits 的 raw item byte 表)在新版同位址不吻合**:讀出
  `00 00 00 00 00 fd ff ff ff fe ff ff ff ff ff ff ff 00 00 00 00 07 08 06 0d`,不像任何合理的
  item id 序列;全檔搜尋 18-byte 期望序列(`59 5D FF 5D CD CD CD CD 5C 58 58 5B 5C 58 58 5B FF FF`)
  也**零命中**。
- **`0x1e529`(growth-add)、`0x2a2e8`(重算入口)、`0x31571`/`0x3151a`(class/portrait 寫回、道具判定)
  在新版對應位址不是同一段程式**(`0x1e529` 落在一段無關的堆疊檢查/表分派函式開頭;`0x2a2e8`/
  `0x3151a` 甚至沒有已反組譯的指令)。

**結論**:轉職機制的「規則/順序/累加語意」證據力仍然很高(官方 IDA 9.4 + Docker Capstone 雙工具、
外部 PTT 實測交叉驗證,不因換版而改變的是遊戲邏輯本身),但**引用的具體位址目前只對舊版(已遺失)成立**,
新版對應位址尚未重新定位(除 `0x615fe` 這張表巧合仍在原位)。這與既有 memory
「fd2_re old/new EXE address instability」一致——位移不是全檔案固定常數,需要逐段用 byte-signature
重新定位,不能整批套用單一 delta。後續如需在新版上引用這些位址(例如要做 native 行為的即時比對),
必須先重跑訊號比對定位,本輪未做完整重新定位(超出本次任務範圍,留待下一輪)。

### 6.7 對 remake 的現況

`remake/internal/campaign/church.go`、`class_change_table.go`、`native_class_confirm.go`、
`native_class_list.go` 已完整實作 §6.1–6.3 的 state machine(候選/target 解析/道具消耗/五組成長累加/
class-portrait 寫回),並有對應 regression test(`church_test.go`/`class_change_table_test.go`/
`native_class_confirm_test.go`/`native_class_list_test.go`)。§6.5 找到的三筆道具錯位若屬實會讓
索菲亞/凱麗/貝克威轉職到錯誤的 item 需求,建議下一輪先確認(可能只是修正 JSON 三個欄位),再視需要
回頭補新版位址重新定位(§6.6)。

