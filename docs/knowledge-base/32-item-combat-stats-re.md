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

### 1.1 2026-08-19 table 真正邊界/stride 最終閉合(215 rows,回應 worklist L366/L1354)[驗]

**先修正一個 provenance bug**：上面 §1 與既有 `tools/dump_exe_tables.py` 的
`ANCHORS["item"]=(0x540AC, ...)` 是**舊版(357074B,已遺失)EXE 的 file offset**，
不是目前唯一可用的 509158B「新版」EXE 的真實位置。直接對現有 `FD2.EXE`
(md5 `33464c81e6a364fd0660141139aa8e6e`，與 `docs/data/fd2-reference-files.json`
記載的基準一致)重跑 `dump_exe_tables.py` 可重現這個問題：

```
錨定特徵對齊:
  item    @0x540ac ✗
  shop    @0x56190 ✗
  spell   @0x557fd ✗
  ...(全部 9 張表 ✗)
⚠ 部分錨定特徵未對齊,offset 可能不適用此版本!
```

對照 `03-exe-and-data-structures.md` 第 39-121 行早已記載的結論：這 9 張表的
file offset 在「新版」EXE 裡整批位移了(其中 5 張已於 2026-08-19 逐 byte
驗證固定位移 `0x25214`)，只有**程式碼(code/text section)位址沒有位移**。
物品表先前不在那 5 張已驗證表之列，本輪補上：

- 物品表 anchor `0B 01 0A 00 5F 00` 在目前 EXE 精確命中於 file `0x792C0`
  (`03-exe-and-data-structures.md` 早已記載新版 offset 為 `0x792C1`，1 byte
  差屬既有定位慣例)。用這個位置重讀 215 個已知 ID，`raw` 欄位與
  `docs/data/exe_tables/item.json`(2026-08-07 用舊版 EXE 匯出)逐筆 byte-exact
  相同——**證實物品表內容本身新舊版無差異，只有 file offset 位移了
  `0x792C1 − 0x540AD = 0x25214`**，與另外 5 張表完全相同的固定位移一致，
  可以把「item」正式併入那條位移規律，不再是例外。
- 這代表 `docs/data/exe_tables/item.json`／`native_item_effect_rows.json`
  的**數值本身仍然正確可信**；只有兩份 JSON 內的 `off`/`linear` 溯源欄位
  (寫的是舊版 file offset)在目前 EXE 上已經失效，若要重新用 file offset
  定位這張表必須用 `0x792C0`(normalized)／`0x792C1`(native)，不能沿用
  `0x540AC`/`0x540AD`。`tools/dump_exe_tables.py` 的 `ANCHORS` dict 本身也還
  沒更新成新版 offset(全部 9 張表都還是舊版值)，這是本輪發現、留給後續
  輪次修的獨立 bug，不在本次任務範圍內處理。**（2026-08-20 已修：見 §1.2）**

**Row 數/stride 的真正邊界**：runtime linear base `0x602AD`、stride `0x17`
(23B)不變(Ghidra `FD2Analysis3` 對現有 EXE `-readOnly` 反組譯直接證實：
trivial pointer accessor 現址 `FUN_0004e8bc`——舊文件記載的 `0x4e56c` 只是
**函式本身**的舊版位址，`return &DAT_000602ad + param_1 * 0x17;` 一行完全
不變，這也再次印證「code 位址位移、data 位址不位移」的既有結論)。

用正確的新版 file base(`0x792C1` = native row 0 起點)往後推 215 列
(`0x792C1 + 215*0x17 = 0x7A612`)、換算回 runtime linear(`0x602AD +
215*0x17 = 0x615FE`)，這個位址與 file offset **精確等於**既有 §6.6 已
逐 byte 驗證過的 class-change `target_portraits` class/mobility pair 表
起點（`0x615FE`，首 8 byte `09 01 0a 00 09 01 0a 00`）——實際讀取 file
`0x7A612` 得到的 bytes 正是 `09010a0009010a00`，**零 byte 間隙**：

```
native row214(最後一個已知 item ID)結束於 file 0x7A611
native row215(第一個「越界」row)起點  file 0x7A612 / runtime 0x615FE
                                    == 已知的 target_portraits 表起點,完全重疊,無 padding
```

**結論(回應 worklist L366/L1354)**：物品效果表 `0x602AD` 的真正邊界就是
**215 rows(ID 0..214)、stride `0x17`(23B)、無隱藏 padding**，第 216 個
「理論 row」的位置已經被另一張已證實的表(class-change `0x615FE`)佔用，
不存在更多未知 item row。215-row prefix 不再只是「已知前綴」，而是**證實
完整的 table**。取得這個結論不需要新的 caller 反組譯，只需要修正 §1 沿用
的舊版 file offset provenance bug 後直接讀 byte。

### 1.2 2026-08-20 `tools/dump_exe_tables.py` 全部 9 張表 ANCHORS 修正 [驗]

接續 §1.1 留下的 provenance bug：`ANCHORS` dict 當時全部 9 張表都還是已遺失舊版
EXE(357074 B)的 file offset，對現有唯一可用的新版 `FD2.EXE`(509158 B)全部
anchor 失敗。本輪逐表核對 `03-exe-and-data-structures.md` §B 第 60-70 行已記載
的「新版/舊版」對照表，並直接對 canonical EXE 讀 bytes 驗證每一個候選 offset：

| 表(ANCHORS key) | 舊版 offset | 新版 offset(已驗證) | 位移量 | anchor bytes |
|---|---|---|---|---|
| item   | 0x540AC | 0x792C0 | +0x25214 | `0B 01 0A 00 5F 00` |
| shop   | 0x56190 | 0x7B3A4 | +0x25214 | `80 81 84 A5 FF` |
| spell  | 0x557FD | 0x7AA11 | +0x25214 | `32 00 5A 05` |
| char   | 0x55BA1 | 0x7ADB5 | +0x25214 | `01 01 01 2A` |
| growth | 0x55EA1 | 0x7B0B5 | +0x25214 | `06 08 04 06` |
| learn  | 0x564B3 | 0x7B6C7 | +0x25214 | `05 11 09 01` |
| resist | 0x51D96 | 0x76FAA | +0x25214 | `0A 00 00 00 0A 00 00 00` |
| crit   | 0x5219B | 0x774BC | **+0x321(例外)** | `05 03 03 05` |
| unit   | 0x558F9 | 0x7AB0D | +0x25214 | `01 02 12 00 00 05` |

8/9 張表精確符合 §3.6 已確立的固定位移 `0x25214`；`crit`(職業暴擊率表)沿用同一
既有例外(見 §3.6 第 1 點)，新版真實位置 `0x774BC` 與位移公式理論值 `0x774AF`
仍差 `0xD` byte，用 anchor byte `05 03 03 05` 全檔搜尋鎖定，唯一命中處就是
`0x774BC`。

另外兩個函式(`dump_native_movement_cost_rows`、`dump_class_equip_types`)先前
把舊版 offset 直接寫死在函式體內、未經 `ANCHORS` dict 引用，同樣需要修正：

| 函式 | 用途 | 舊版 offset | 新版 offset(已驗證) |
|---|---|---|---|
| `dump_native_movement_cost_rows` | 地形移動成本(20B×29 selector) | 0x55445 | 0x7A659 |
| `dump_class_equip_types` | 職業裝備相容白名單(7B×29 職業) | 0x55689 | 0x7A89D |

兩者同樣是 `+0x25214`，且驗證後發現 `0x7A659 + 29*20 = 0x7A89D` 恰好等於
`class_equip_types` 新版起點，零間隙銜接，與 §1.1 對 item 表邊界驗證用的同一
手法互相佐證位移量正確。`dump_growth`/`dump_unit` 另有兩處以舊版 offset
(`0x56190`、`0x55BA1`)當作迴圈上界字面值，一併改為引用
`ANCHORS["shop"][0]`/`ANCHORS["char"][0]`，不再硬編碼。

對現有 `FD2.EXE`(509158 B)重跑 `python3 tools/dump_exe_tables.py`：

```
錨定特徵對齊: item/shop/spell/char/growth/learn/resist/crit/unit 全部 ✓(9/9)
數值自驗(對照青衫攻略字面值): 全部通過 ✓
```

`tools/test_dump_exe_tables.py` 裡 `test_native_movement_cost_rows_have_exact_29_by_20_boundary`
原本硬寫舊版 `base = 0x55445`，同步改為新版 `0x7A659`；4/4 單元測試通過。

### 1.3 2026-08-24 獨立複驗(回應 worklist L366/L1354，不重新推導，只核對既有結論)[驗]

> 背景：worklist 上這兩行的原始措辭仍是「base/stride/215-row prefix 仍未閉合」，但 §1.1/§1.2/
> §4.3 已在 2026-08-19～20 記錄「狀態：完成」。查證前先確認這不是文件互相矛盾——worklist 本身
> 的措辭是先前輪次留下未同步的舊文字（任務指示不得直接改 `91-worklist.md`），不是真的還有缺口。
> 本輪不重新推導，只用純靜態證據**獨立**核對 §1.1 的三個關鍵斷言，確認沒有錯誤或遺漏。

直接對 canonical `FD2.EXE`(509158 bytes)重新 `seek`/`read`(不經任何既有 exporter，避免沿用
同一套可能共享的 bug)：

- md5 `33464c81e6a364fd0660141139aa8e6e`，與 `docs/data/fd2-reference-files.json` 記載基準一致。
- file `0x792c0` 起 6 bytes = `0b 01 0a 00 5f 00`，與 §1.1 記載的 anchor 完全相同。
- file `0x792c1`(native row0)起 23 bytes = `01 0a 00 5f 00 00 00 00 00 00 00 01 01 00 00 00 00
  00 05 00 32 00 05 00`，stride `0x17` 起點內容存在、非全零/垃圾資料。
- **零 gap 邊界獨立核對**：file `0x7A611`(row214 最後一個 byte)= `00`；file `0x7A612`
  (row215/理論第 216 列起點)起 8 bytes = `09 01 0a 00 09 01 0a 00`——與 §1.1 引用的 class-change
  `target_portraits` 表起點首 8 byte **逐 byte相同**，且 `0x7A612` 精確等於
  `0x792c1 + 215*0x17` 的算術結果，無 padding、無缺口，與 §1.1 結論一致。

`FUN_0004e8bc` 重新 `decompile` + 逐指令 `disasm`(`FD2Analysis3`，`-readOnly`，Ghidra headless)：

```
undefined * __stdcall FUN_0004e8bc(int param_1)
{
  return &DAT_000602ad + param_1 * 0x17;
}
```
逐指令核對：`MOV EAX,[EBP+8]`(param_1)→`MUL 0x17`→`LEA EDX,[0x602ad]`→`ADD EAX,EDX`→`RET`，
單一 5 行 accessor，與 §1.1 記載完全一致，沒有隱藏的 bounds check 或第二個分支。

**結論**：base `0x602ad`(runtime linear)／file `0x792c1`(新版)、stride `0x17`(23B)、215-row
(ID 0..214)零 gap 邊界、`FUN_0004e8bc` 單行 accessor——四項獨立複驗全部與 §1.1 既有結論
byte-exact 吻合，沒有發現任何需要修正之處。**本項到此確認為真正閉合，worklist L366/L1354
可視為已解決，不需要再排入下一輪 RE 工作**；欄位語意層面仍只剩 §4.1/§4.3 已明確標註的
`+0xb/+0xc`(caller-specific 幾何)與結構性冗餘 `+0x16` 未強行命名，這是刻意保留的
fail-closed 邊界，不是遺漏。

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
`native_item_effect_rows.json`。**2026-08-19 更新**：runtime table 的最終
邊界已由 §1.1 閉合為精確 215 rows(與 `0x615FE` class-change 表零 gap
銜接)，不再是「不能宣稱完整」；下面 §4.1 的欄位語意也已部分補上
（`+0x9/+0xa` 見 §4.1 與 doc27 §5 第 5 項），僅 `+0x11` 仍待個別 caller
證據。

### 4.1 2026-07-20 direct range-field trace（2026-07-27 勘誤）

以 `tools/disasm_le.py` 追 `0x318ad` 與 item pointer helper `0x4e56c` 後，欄位偏移更正如下：

```
+0x0 type, +0x01 AP, +0x03 HIT, +0x05 DP, +0x07 EV
+0x0a..+0x0d caller-specific raw inputs, +0x0e..0x13 K[6]
```

原先把這四個 byte 命名成 `atk_attr/atk_rate/range_min/range_max` 並把 `0x14237` 的 `+0x0c` 稱為通用 `range_min`，現撤回。已確認的安全描述是：`0x14237` 將 item row `+0x0b/+0x0c` 以 caller-specific 順序傳入 `0x14818` 的 `a5/a4`；`mode<0x10` 時 `a5` 會排除 marker cells，`mode>=0x10` 走 cross branch。另一條 `0x18d8c` 也讀相鄰 raw bytes，`+0x0d` 另有特殊 effect dispatch caller；這些都不足以反推出通用武器射程或 normalized `AtkMin/AtkMax`。

因此 remake 暫時只沿用已由 `weapon_range.json` 獨立驗證的 normalized 武器射程；不得把 raw `+0x0b..+0x0d` 臆測成 `AtkMin/AtkMax`。這輪只修正 provenance 斷言，不改變未證實的戰鬥公式。

**2026-08-19 補完：row 內三個互不相同的「type」欄位，避免混淆**——這張表同時有三個
語意完全不同、卻都可能被籠統叫做「type」的 byte，回應 worklist L366/L1354「未命名
欄位語意」的要求，逐一列清楚：

| offset | 語意 | 證據 |
|---|---|---|
| `+0x0` | 裝備分類(武器/防具/其他) | 本輪 `FD2Analysis3` readOnly 反組譯的 UI icon 選擇函式 `FUN_000272d0`，以及裝備 recalc 函式(對應 `0x1145a`/`0x1b750` 邏輯、新版位址 `FUN_00028632`)都以 `<0x15`(武器類,icon `0x3b`)／`0x15..0x1f`(防具類,icon `0x3c`)／`>=0x20`(其他,icon `0x3d`)三段切分；裝備 recalc 用同一個 `<0x15` 分界判斷「同格另一件裝備是否落在對面陣營」才把 `+1/+3/+5/+7` 計入 AP/DP/HIT/EV，兩處分界完全一致 |
| `+0xd` | 物品使用效果 dispatch code(type5/6/7/8-12/13/14-16/17-19/20-24 等) | 既有 `0x1bbdc`／`0x20c6f` 全表已閉合(見下方各條) |
| `+0x9` | **武器命中後特殊效果 selector**(0=無;2=命中後對目標套用持久 marker `+0x25`,消耗一顆額外 RNG;3=只設定一個未命名 output flag;4=固定加成暴擊率) | doc27《27-combat-rules-and-validation-checklist.md》§5 第 5 項(`0x2f7b6` 完整 crit 分支反組譯)首先閉合；下方 §4.2(同輪稍後的續輪成果)進一步用 215 筆 `native_item_effect_rows.json` 逐筆分類出全部觸發物品 id(0=200 筆無效果、2=6 筆、3=1 筆、4=8 筆)，並找到第二份獨立、byte-for-byte 相同的 copy(`FUN_0001ecc7`)交叉印證 |
| `+0xa` | 上一欄的強度值：`type==4` 時直接加進職業暴擊基準值(`DAT_000524a7[actorClass]`)；`type==2` 時當成 0-100 的 RNG 機率門檻 | 同上，見 doc27 §5 第 5 項與下方 §4.2 |

`+0x9/+0xa` 不需要重新反組譯——doc27 與下方 §4.2 已用 `0x2f7b6`(doc27 §5
第 1/2/4 項也引用的同一個物理攻擊主函式，取代了本文 §2 舊「大函式 0x15xxx」的猜測位址)
完整閉合，本節只是把這個結論接回 row 欄位表，避免多份文件各自宣稱「未閉合」。

`+0x15`(row 最後一個非跨列 byte)也已經在下面「Docker Capstone」段落與 `0x1bbdc`
分析中閉合為「兩階段共用 target code」，不是未命名欄位。本輪在 `FUN_00015055`
(新函式，item-use 進入點，同樣以 `+0x10<0x10` 分派 `0x14818`/`0x149f8`，並在其後
把 `DAT_00051a83 = row+0x12 + 2`)找到第三個獨立 caller，交叉印證 `+0x10`/`+0x12`
的既有語意，不需要更名。唯一仍完全沒有任何 caller 讀取的是 native row 最後一個 byte
`+0x16`——結構上它就是「下一列 normalized row 的 byte 0」(見 §1 的一 byte 錯位)，
且 §1.1 已證實 row215 起點與另一張表零 gap 銜接，故 `+0x16` 大機率只是這個 1-byte
錯位視圖本身的副作用，不是被消費的獨立欄位；沒有找到反例，暫不強行命名。

> **worklist L1118 更新(2026-08-19 續輪)**：先前留的「仍待對位 `0x14344` caller」懸念已釐清——純靜態
> Ghidra headless(`FD2Analysis3`,唯讀)`getFunctionContaining(0x14344)` 直接回傳 `FUN_00014237`
> (body `0x14237..0x145cc`),即本節一直在描述的同一個 `0x14237`,`0x14344` 只是它中段的一個位址,
> **不是獨立的第二個 caller function**。因為專案是 `-noanalysis` 模式,反編譯器在這段沒有完整還原呼叫
> 參數(`FUN_0004e8bc`/`FUN_0004e8a5`/`FUN_0003706e` 等多個呼叫顯示成看似無參數),本輪未能逐位元組
> 核對 `0x14344` 這個精確位址存取的是 `+0x0b` 還是 `+0x0c`;但足以排除「這是不是另一條獨立資料流」的
> 疑慮——它與上面 `0x14237` 的 caller-specific、fail-closed 描述是同一份證據,不需要當成新的獨立佐證點,
> 也不改變本節「不得臆測 raw `+0x0b..+0x0d` 為通用射程」的結論。

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
- Docker Capstone 也已閉合共用 item pointer(舊版位址 `0x4e56c`，新版 EXE
  同一段邏輯現位於 `FUN_0004e8bc`，兩者都是單行 `return base+idx*0x17`，
  詳見 §1.1)：table base `0x602ad`、row stride `0x17`（23 bytes）。
  **2026-08-19 更新**：`0x540ad` 只是舊版(已遺失)EXE 的 file offset，
  目前唯一可用的新版 EXE 上正確 file offset 是 `0x792c1`（見 §1.1，
  已排除 provenance bug）；215-row raw prefix 已獨立匯出並由 loader
  regression 固定，且 §1.1 已用「row215 與已知的 `0x615FE` class-change
  表零 gap 銜接」證實 table 就是恰好 215 rows，不再是「未證實的前綴」。
  除已全表交叉的 `+1/+3/+5/+7`(AP/HIT/DP/EV)外，`+0x9/+0xa`(武器命中特效
  selector/強度)、`+0xd`(效果 dispatch code)、`+0x10/+0x12/+0x15`(target
  mode/target code)也已由 §4.1 與 doc27 §5 收斂命名；仍未命名的只剩
  `+0xb/+0xc`(caller-specific 幾何輸入，多個 caller 各自解讀方式不同，
  未見單一通用語意)與結構性冗餘的 `+0x16`。
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

### 4.2 2026-08-19 續輪:`0x20c6f` type dispatch 全 25 種 case 窮舉閉合 + 武器命中特殊效果來源鏈(回應 worklist L246)

> 方法:純靜態 Ghidra headless(`FD2Analysis3`,唯讀,`ProbeAudit0820.java`/`ProbeAudit0820b.java`)
> 對 `0x20c6f` 做完整 `DecompInterface` 反編譯,並對 `0x2f7b6` 做逐指令原始反組譯還原被 `-noanalysis`
> 省略的呼叫參數。完整輸出見 `FD2_ghidra_projects/probe_audit0820_out.txt`／`probe_audit0820b_out.txt`。

**A. `0x20c6f` 的 `cVar1`(item row `+0x0d`)dispatch 現在窮盡列出全部分支,不再只是「已覆蓋
5/13、8–12、14–16、22」的部分清單**:

| cVar1(row `+0x0d`) | 分派目標 | 對應既有結論 |
|---|---|---|
| 5, 13 | `0x211a4`(HP restore) | 已知 |
| 6, 7 | `0x22af6`(marker clear/restore) | 已知 |
| 8, 9, 10 | `0x21082`(base-stat add) | 已知 |
| 11 | inline MP restore loop → `0x1c9dd` | 已知 |
| 12 | `0x22997`(風行 HIT/EV+15) | 已知 |
| 14 | `0x22d1b`(狀態施加) | 已知 |
| 15 | `0x22866`(魔鎧 DP+15%) | 已知 |
| 16 | `0x22721`(魔刃 AP+15%) | 已知 |
| 17, 18 | `0x21082`(同 8/9/10 分支) | **本輪新確認**——先前只記「type17–19 由獨立欄位證據閉合」,現在補上 17/18 與 8/9/10 共用同一 callee 的 dispatch 證據 |
| 19 | `0x21082`,但呼叫前後 save/restore raw `+0x3c`(EXP byte) | 已知,本輪補上 dispatch-level 佐證 |
| 20, 24(`'\x18'`) | `0x1cd17`+`0x1c75e` 迴圈 | 已知 |
| 21 | `0x2111a` | 已知 |
| 22 | `0x22d1b`(同 14) | 已知 |
| 23 | `0x2218a`(relocation) | 已知 |
| **0, 1, 2, 3, 4** | **無分支命中,直接跳到清尾(`DAT_00053ec8=0`+`0x1b6b7`/`0x1db65`/`0x1aa1d`),不呼叫任何 gameplay callee** | **本輪新發現**:這 5 個 type 值透過此 dispatcher「使用」時是純粹的 no-op |

**結論**:`cVar1`(row `+0x0d`)0–24 全部 25 個可能值現在都有明確歸屬(20 個有 callee、5 個是
no-op),`0x20c6f` 這個 caller 的「使用效果碼」窮舉閉合,不再有「其餘 callee 仍依個別證據
fail-closed」這種開放式表述必要——只剩 type3(見下)的下游旗標消費者與若干 marker 的玩家可見名稱未知。

**B. 武器命中特殊效果(cVar4,先前 doc27 §5 表第 5 項標「原生獨有,remake 未實作」)來源鏈解出**：

`FUN_0004e8bc(itemId)` 反組譯只有一行 `return &DAT_000602ad + itemId*0x17;`——與已知 item pointer
helper `0x4e56c`(table base `0x602ad`、stride `0x17`)是**同一張表**(第二個編譯副本,見上方
§1.1 併行確認的同一事實)。逐指令追蹤 `0x2f7b6` 對它的呼叫(`0x2f870 CALL 0x1b83d(unit,0)` 找已裝備
`id<0x80` 武器 slot → `0x2f87d CALL 0x1b722(slot,unit)` 轉 item id → `0x2f886 CALL 0x4e8bc(itemId)`
轉 row 指標),`cVar4 = row+9`(type)、`uVar9 = row+10`(強度值)。**堆疊偏移核對顯示這裡查詢的是
`FUN_0002f7b6` 的第二個參數**(函式內扮演 DP/守方角色的那個 unit),不是直覺會猜的攻方武器——這是
誠實記錄,不宣稱已確認是「攻方觸發」。

用已存在的 `native_item_effect_rows.json`(215 筆,不需新反組譯,直接讀 byte[9]/[10])做全表分類,
配合 `item.json` 的 AP/HIT/DP/EV/price 佐證：

| type | 筆數 | 效果 | id(強度值) |
|---|---|---|---|
| 0 | 200 | 無效果 | 其餘全部 |
| 2 | 6 | 命中後 `RNG%100<強度值` 觸發:目標 `record+0x25` 寫 `(RNG%4)+2` | 4(10) 14(30) 46(10) 59(30) 65(20) 66(20) |
| 3 | 1 | 只設輸出旗標 `param_3[4]=1`,不改 record;下游消費者未追 | 71(強度值未使用) |
| 4 | 8 | 固定加成暴擊率 `crit% += 強度值` | 7(30) 11(30) 18(5) 30(20) 39(10) 43(80) 49(10) 69(20) |

**交叉連結**:type2 寫入的 `record+0x25`,與上面已文件化的「item type6/7 → `0x22af6`,讀 target
`+0x25/+0x26`」是**同一個 byte**——這 6 把武器命中後可能附加的異常狀態,能被 item type6 治癒。狀態的
玩家可見名稱仍未知,但資料流已封閉。detail 與第二個獨立實作(`0x1ecc7`,結構與 `0x2f7b6` 幾乎相同,
同樣有 `cVar4` dispatch)見 `27-combat-rules-and-validation-checklist.md` §5.1。

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

### 4.3 2026-08-19 worklist L366/L368/L1354 完成度小結

> 編號承接上方獨立續輪新增的 §4.2(worklist L246，`0x20c6f` type dispatch 窮舉 +
> 武器命中特殊效果來源鏈)，兩節是同一天不同續輪各自產出，內容互補不重疊，§4.1 的
> `+0x9/+0xa` 欄位說明已改為同時引用 doc27 與 §4.2。

- **L366／L1354(同一件事,已合併處理)**：`0x602ad` table 的真正邊界/stride 已在 §1.1
  完全閉合——精確 215 rows(ID 0..214)、stride `0x17`、row215 與已知的 class-change
  `0x615FE` 表零 gap 銜接，不再是「已知前綴」。未命名欄位語意也在 §4.1(併同 §4.2)
  收斂：`+0x0`(裝備分類)、`+0x9/+0xa`(武器命中特效 selector/強度)、`+0xd`(效果
  dispatch code，§4.2 已窮舉全部 25 個值)、`+0x10/+0x12/+0x15`(target mode/target
  code)均已命名或已有既有結論可引用；只剩 `+0xb/+0xc`(caller-specific 幾何，語意
  隨 caller 而異)與結構性冗餘的 `+0x16` 仍未強行命名，但已排除「可能有更多未知
  row」的疑慮。**狀態：完成**。過程中額外發現並記錄一個獨立 provenance bug
  （`tools/dump_exe_tables.py` 的 `ANCHORS` 全部 9 張表都還是舊版 file offset，
  見 §1.1），已記錄但不在本次任務範圍內修。
- **L368**：查證後確認這行 worklist 描述的「`+0x22/+0x23/+0x24` DX/race/multiplier」
  與本文 `0x602ad` 物品表**完全無關**——它指的是另一個結構(persistent 戰鬥單位 record
  的暫態 buff 持續時間 byte，command17/18/19「魔刃術/魔鎧術/風行術」各自的
  AP+15%/DP+15%/HIT+15,EV+15 效果)，且已在 `13-battle-menu-system.md`(2026-08-19)
  用 `0x1A866` 的到期訊息字串(FDTXT `0x1E1/0x1E2/0x1E3`)完整閉合，不是「race」也不是
  「multiplier」欄位。本次未對 `0x602ad` 表做任何 `+0x22/+0x23/+0x24` 相關 RE，因為
  那些 offset 根本超出這張表 23-byte 的 row 範圍(`0x22`=34 > `0x17`=23)。
  **狀態：與本表無關，已查明是另一結構且已在別處閉合；worklist 該行文字本身過時，
  但依任務指示不改動 `91-worklist.md`，僅在此記錄查證結果。**

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

**2026-08-19 續輪(worklist L247)第二個確認性 spot-check**：既然 `0x526a7` 的 byte-search 已零命中,
本輪換一個角度——直接對舊版候選/target resolver 入口 `0x31793` 在**新版** EXE 上強制反組譯
(`ProbeAudit0820b.java`,`disassemble()` fallback)。結果：`0x31793` 在新版**確實是合法的可反組譯
程式碼**(不是資料或未對齊的位元組),但內容與轉職候選判定完全無關——它呼叫的是已知的 `0x11eb0`
(viewport `memmove` blitter,見 worklist L1120)與 `0x11d40`(已證實的 postbattle handler helper)、
`0x2eb9f`(疑似文字/數字渲染),並比對 `[0x53c03]==0x1a`(章節/模式號)做分支——看起來是某個無關的
UI/清單畫面,不是轉職邏輯。這是**第二個獨立資料點**,強化(而非首次證明)`0x31793`/`0x526a7` 這類
「用同一位址直接查」的 spot-check 方法已經走到頭:新版 EXE 在這個 code 區段做過重新編譯/佈局,兩個
獨立位址的探測都指向「同位址已被別的功能佔用」而非「移了幾個 byte」,要繼續追這條線必須做全檔
byte-signature 重新定位(等同重做一次官方 IDA 的分析範圍),不是本回合能負擔的靜態探測量。portrait
11–13 道具輪轉錯位問題(§6.5)**維持未決**,不因本輪而更新結論方向,只是排除了「換個位址探探看」
這條路。

### 6.7 對 remake 的現況

`remake/internal/campaign/church.go`、`class_change_table.go`、`native_class_confirm.go`、
`native_class_list.go` 已完整實作 §6.1–6.3 的 state machine(候選/target 解析/道具消耗/五組成長累加/
class-portrait 寫回),並有對應 regression test(`church_test.go`/`class_change_table_test.go`/
`native_class_confirm_test.go`/`native_class_list_test.go`)。§6.5 找到的三筆道具錯位若屬實會讓
索菲亞/凱麗/貝克威轉職到錯誤的 item 需求,建議下一輪先確認(可能只是修正 JSON 三個欄位),再視需要
回頭補新版位址重新定位(§6.6)。

## 7. worklist 稽核索引 L245/L246/L247/L248/L1118/L1515 完成度總結(2026-08-19 續輪)

> 本節逐項回應任務指定的六個稽核索引行號,含未在本檔本輪修改、但需要交代完成度的項目(L245 主體在
> `27-combat-rules-and-validation-checklist.md` §5.1;L248 主體在 `49-character-id-name-table.md`)。

- **L245**(doc27§5 剩餘清單:經驗值攻守等級因子/`0x2f7b6` cVar4 分支/6 種傳送魔刃經驗公式/法術命中率
  逐 ID)：**大部分收口**。cVar4 分支來源鏈與全部 15 個觸發武器 id 解出(本檔 §4.2)、6 種經驗公式全部
  找到反組譯(doc27 §5.1)、等級因子疑慮部分收斂(第二個獨立實作 `0x1ecc7` 佐證)。**唯一完全未動**的
  是法術/道具命中率逐 ID 核對(`0x1c7ed` 的 `record[+2]` 未逐一 dump 比對 `spell.json`)。詳見 doc27 §5.1。
- **L246**(物品系統裝備加成精確累加點與使用效果碼未反組譯)：**裝備加成精確累加點**早在 §3.5 已閉合
  (`有效AP=角色底AP+武器.ap` 等四條公式,對截圖逐位吻合)。**使用效果碼**本輪(§4.2)把 `0x20c6f` 的
  `cVar1` dispatch 從「部分覆蓋清單」補成 0–24 全 25 個值窮舉(20 個有 callee、5 個是 no-op),武器
  on-hit 特殊效果(`cVar4`)也解出來源鏈與全部觸發武器 id。剩餘缺口只有:type3 旗標(僅 1 個道具
  id71)的下游消費者、幾個 marker/狀態的玩家可見名稱。**視為已大幅收口**。
- **L247**(class_change_targets.json portrait11–13 輪轉錯位仍待查)：**未解決,但探測方法已窮盡**。
  本輪(§6.6 新增段落)對第二個舊版位址(`0x31793`)在新版 EXE 做 spot-check,確認該位址現在是無關的
  UI 程式碼,強化(非首次證明)同位址探測法已走到頭。要解開輪轉是否為 JSON 建表錯誤或原生設計,需要
  全檔 byte-signature 重新定位轉職相關函式,超出本輪可負擔的探測量,**維持 D(可續但需大量前置工程)**。
- **L248**(角色名對應需逐圖解 FDFIELD roster)：**本輪未展開新工作**。`49-character-id-name-table.md`
  (2026-08-19)已用對話 identity-tag 交叉驗證把 38/135 組角色名定案,並明確記錄其餘約 97 組(泛用
  怪物/路人)因為對話走 `-19/-20`(場景相依、不可信)而**不可能靠對話反推**,必須逐張地圖解 FDFIELD
  roster `byte[+7]` 才能繼續——這是遠大於本輪範圍的工程量(每張地圖都要解),doc49 已誠實列為待辦,
  本輪未新增任何一張地圖的解碼。狀態不變。
- **L1118**(doc32 L169:remake 暫沿用獨立驗證的 normalized 武器射程,不得臆測 raw `+0x0b..+0x0d`,
  仍待對位 `0x14344` caller)：**懸念已釐清**(本檔 §4.1 新增段落)。`0x14344` 經 Ghidra
  `getFunctionContaining` 證實就在既有已文件化的 `0x14237` 函式體內,不是獨立的第二個 caller,不需要
  也不應該當成新的獨立佐證點。因 `-noanalysis` 模式反編譯器未還原該處呼叫參數,精確 byte 存取(`+0x0b`
  或 `+0x0c`)仍未逐位元組核對,但這是既有 `0x14237` fail-closed 描述範圍內的已知限制,不是新缺口。
- **L1515**(核對 `remake/internal/battle/native_inventory_search.go` 與 `main.go:2683-2695`,raw
  gate minor 殘留範圍)：**已核對,確認完整、無需修改**。`FindNativeInventoryItemInUnit`/
  `FindNativeInventoryItem`(`native_inventory_search.go:11-46`)完整重現 `0x31860`→`0x1b8a6`
  →raw slot scan 的 count-sized prefix 搜尋,不驗證 compactness,與原生行為一致。`main.go:2683-2690`
  的函式註解本身已誠實記載:`partyHasItemID` 優先呼叫這個 exact raw adapter,只有在 itemID 超出
  byte 範圍或找不到 runtime records 時才退回 normalized/persistent roster 掃描(`main.go:2699-2721`)
  這個「刻意保留的相容路徑」,不是未修的 raw gate 缺口。項目描述的「minor 殘留範圍」與程式碼現況完全
  相符,無需改動。

