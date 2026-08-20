# 03 — FD2.EXE 資料表與核心資料結構

> 來源：青衫攻略 modify1/modify2(記憶體/程式修改) + 第 1 輪實檔驗證。
> `FD2.EXE` 為 DOS4GW LE(Watcom 32-bit 保護模式)。攻略列出兩組 offset：
> 多數表有「新版 / 舊版」兩個位置(本作有不同發行版)。**實作時以反組譯確認當前版本為準。**

## A. 記憶體中的單位結構(每單位 0x50 = 80 byte)[攻略]

戰棋的每個場上單位 80 byte。欄位(偏移以 byte 計)：

| 偏移 | 欄位 | 說明 |
|---|---|---|
| 0x08 | XX, YY | 地圖座標(左上 0,0) |
| 0x0A | Z1,Z2,Z3 | 圖形 / 方向 / 跑步動作 |
| 0x0D | raw / 未重判 | 舊 AA 行動狀態標記未通過 current constructor/caller trace；已驗證的 inactive/action bits 位於 byte `+5`（bit0 / bit7） |
| 0x06 | camp | `0x10c50` constructor 將 FDFIELD unit `b0` 直接寫入；00=敵、01=友、02=己方。舊「0x0E BB=陣營」已被 direct trace 推翻並撤回 |
| 0x0F | FA | 肖像編號(見附錄) |
| 0x10 | NN(2) | 姓名 |
| 0x12 | IT×8 | 物品，各 2 byte = 狀態 + 編號；狀態 40=裝備 00=持有 80=空 |
| 0x1A | initial_command_mask(4) | FDFIELD b13..b16 複製到 runtime command bitset 的 bytes 0..3（command IDs 0..31）；個別 ID 的玩法語意仍待對照 |
| 0x22 | raw modifier bytes | constructor 先清零；後續 writer／AI score 會讀取這段 raw bytes，但 derived-stat/property/status 名稱尚未由完整 caller、equipment recompute 與 presentation 證實；並非法術 bitfield |
| 0x1F | race | constructor `0x10f7f/0x11399` 由 source byte0 寫入 |
| 0x20 | class ID | constructor 由 source byte1 寫入；`0x1c75e` 用作 command damage multiplier table index |
| 0x21 | level | constructor 由 source level 寫入 |
| 0x27 | raw / 未重判 | 舊「RA,CL,LV」標記與 direct constructor ABI 衝突，已撤回 |
| 0x2A | A+,D+,H+,-H,XA,XM | 增強 / 中毒 / 麻痺 / 封咒狀態旗標 |
| 0x3F | MT | 力量(影響 AP) |
| 0x40 | current HP(2) | `0x1c81f` 直接讀／減寫並向下 clamp 0；舊稱 DF 為錯誤斷言，已撤回 |
| 0x42 | max HP(2) | `0x1c81f` 讀作 current HP 的上限；舊稱 MV 為錯誤斷言，已撤回 |
| 0x43 | EX | 經驗(滿 100 升級) |
| 0x46 | max MP(2) | `0x1CA89` 對 `+0x44` current MP 扣值；spawn 將 `+0x44/+0x46` 初始化為 current/max MP |
| 0x48 | derived AP(2) | `0x1b750` synthesis 寫入；command 17 的 `+0x22` modifier 以 15% 增加 |
| 0x4A | derived DP(2) | `0x1b750` synthesis 寫入；command 18 的 `+0x23` modifier 以 15% 增加 |
| 0x4C / 0x4E | derived HIT / EV(2) | `0x1b750` synthesis 寫入；command 19 直接各加 15 |

法術原始欄位與後續技能表、肖像編號(0x00–0x41)、職業編號(0x00–0x1A)
詳見 `references/text/memory.md` 與本檔附錄。

## B. FD2.EXE 內資料表 offset

> **第 2 輪驗證(2026-06-28)**:當前 `FD2.EXE`(357074 B)= 攻略「**舊版**」佈局。
> 9 個錨定特徵全部命中於文件精確位置(新版 0x79xxx 超出檔案大小)。
> `tools/dump_exe_tables.py` 已傾印 5 表並對攻略字面值自驗**全通過**,輸出於 `docs/data/exe_tables/`：
>
> | 表 | offset(本版) | 結構 | 列數 | 驗證 |
> |---|---|---|---|---|
> | 物品功效 | 0x540AC | 23B | 215 | id0 `0B 01 0A 00 5F` ✓ |
> | 法術功效 | 0x557FD | 7B | 36 | 天火術 id3 dmg500 ✓、治療 id0xD 己方 ✓ |
> | 敵/友單位 | 0x558F9 | 10B(**HP 為 u16**) | 68 | 士兵/龍劍士/火龍 逐筆 ✓ |
> | 升級成長 | 0x55EA1 | 11B | 68 | 索爾/哈諾/鐵諾 raw ✓ |
> | 職業魔抗/暴擊 | 0x51D96 / 0x5219B | 4B / 1B | 26 | 法師 30%、聖騎士 10% ✓ |
>
> **修正舊敘述**:單位表(及人物出場表)的 HP/MP 欄為 **2-byte LE**(攻略 header「HP HP」「MP MP」即此意),
> 非單 byte。法術數值編號攻略原缺,現已從 EXE 還原(見 `docs/data/exe_tables/spell.json`)。
>
> 下表保留攻略原始的「新版/舊版」對照供參考：

### 攻略原始 offset 對照表 [攻略]

| 表 | 新版 offset | 舊版 offset | 結構 | 錨定特徵 |
|---|---|---|---|---|
| 物品功效 | 0x792C1 | 0x540AC | 23 byte / 物品 | `0B 01 0A 00 5F 00` |
| 商店出售 | 0x7B3A4 | 0x56190 | 28 byte / 章節 | `80 81 84 A5 FF` |
| 法術功效 | 0x7AA11 | 0x557FD | 7 byte / 法術 | `32 00 5A 05` |
| 人物出場屬性 | 0x7ADB5 | 0x55BA1 | 24 byte / 人物 | `01 01 01 2A` |
| 升級成長 | 0x7B0B5 | 0x55EA1 | 11 byte / 人物 | `06 08 04 06` |
| 法術習得等級 | 0x7B6C7 | 0x564B3 | 12 byte / 項 | `05 11 09 01` |
| 職業魔法抗性 | 0x76FAA | 0x51D96 | 4 byte / 職業 | `09 0A 00 00 00` |
| 職業暴擊率 | ~~0x773AF~~ **0x774BC**(見下方 2026-08-19 勘誤) | 0x5219B | 1 byte / 職業 | `05 03 03 05` |
| 敵/友等級資訊 | 0x7AB0D | 0x558F9 | 10 byte / 單位 | `01 02 12 00 00 05` |

> 兩組 offset 差約 0x23xxx，推測為兩個發行版。第 1 輪手上的 `FD2.EXE`(1998 重打包)需用「錨定特徵」grep 定位實際位置。
> **這是第 2 輪反組譯的直接切入點**：依錨定特徵在 EXE 內定位後，整批 dump 成結構化資料。

> **基準版本異動(2026-08-14,第 3 輪)**：上面「第 2 輪驗證」使用的舊版 `FD2.EXE`(357074 B)
> 已在使用者機器上遺失(含隨身碟備份也是同一份跟不上的拷貝)，經確認手上唯一可用的是這份
> **509158 B 新版**(1998 重打包版)。快速核對物品功效表錨定特徵 `0B 01 0A 00 5F 00`，在這份
> 新版 EXE 的 `0x792C0` 精準命中(對照上表 `0x792C1`，1 byte 差屬定位基準慣例，非誤判)——
> 證實這份新版確實就是本表原始記載的版本，不是第三個未知版本。`docs/data/fd2-reference-files.json`
> 已改以此版為基準（schema v2，含 `previous_edition` 欄位保留舊版 hash 供歷史對照）。
> **尚未做的**：上表「第 2 輪」對舊版做過的 9 表逐項 dump+自驗，還沒有對新版重跑一次；
> `tools/dump_exe_tables.py` 目前寫死的是舊版 offset,需要先改成讀新版 offset(上表新版欄)
> 或用錨定特徵自動定位，再逐表跑一次自驗證。這僅限「表 B」的**資料表**(0x5xxxx-0x7xxxx 範圍),
> 跟下面「已修正」的**程式碼位址**無關。
>
> **已修正(2026-08-14，第 4 輪）**：上一輪筆記寫「既有反組譯位址在新版裡未知」是過度悲觀——
> 玩家提供一份對「新版」基準版 FD2.EXE 做的完整 Ghidra 反組譯(976 個函式)，逐一核對後發現
> `0x1B750`(size 237)、`0x10c50`(size 961)、`0x1c75e`(size 193)+`0x1c81f`(size 206)、
> `0x14818`(size 480)、`0x1a866`(size 439)+`0x1aa1d`(size 726)、`0x1f183`(size 73)
> 這些函式在新版裡**位址與大小逐一精準吻合**舊版文件記載的值，且 `0x14b78`/`0x1f183` 兩個
> 函式的實際邏輯經逐行核對後跟既有文件敘述一致（見 doc11「2026-08-14 補完」）。也就是說
> **程式碼段(text section)在新舊版之間沒有位移，只有表 B 那些資料表位移了**——這才是新舊版
> 唯一的實質差異。往後對這 4 個檔案做「程式碼位址」層級的反組譯，可以直接沿用既有文件記載的
> 舊版位址，不需要每次都重新用錨定特徵定位；只有第 39-73 行「資料表」offset 才需要換成新版欄。
>
> **第 39-73 行「資料表」offset 首次對新版逐表逐列驗證(2026-08-19，第 5 輪)**：上面第 81 行標的
> 「尚未做的」在這輪補上——直接用 Python `seek`/`read` 對現有 `FD2.EXE`(509158 B，即本節「新版」)
> 逐 byte 核對使用者提供的完整表格內容(不只 anchor，是每一列)。結果：
> **人物出場屬性表**(0x7ADB5)、**升級成長表**(0x7B0B5，66 列)、**法術習得等級表**(0x7B6C7，20 列)、
> **職業魔法抗性表**(0x76FAA，26 職業)、**敵/友等級資訊表**(0x7AB0D，60 列)全數逐 byte 相符，
> 且新版(0x7xxxx)↔舊版(0x5xxxx)offset 之間的位移在這 5 張表全部固定為 `0x25214`（可作為往後
> 換算捷徑）。發現兩處錯誤：
> 1. **「職業暴擊率」表的新版 offset 原記載 `0x773AF` 是錯的**——`05 03 03 05` 這組 anchor
>    以及完整 26 職業暴擊率數值，在目前這份 EXE 裡實際位於 **`0x774BC`**(比原記載多 `0x10D`
>    bytes，唯一打破 `0x25214` 固定位移規律的一張表)。內容本身(26 職業的暴擊率數值)逐一與
>    doc02 §7.2／`resist_crit.json` 核對**完全一致**，純粹是 offset 數字抄錯（modify2 攻略或
>    先前轉錄環節），不是新舊版資料本身有差異。已在上方表格訂正。
> 2. **敵/友等級資訊表「大惡魔」一列的 AP 成長值，使用者提供的外部表格寫 `31`，實際 EXE bytes
>    是 `33`**(0x21，位於 `0x7ACB1+5`)。`docs/data/exe_tables/unit.json` idx42(對應舊版
>    `0x55a9d`，該檔在舊版 EXE 遺失前已匯出)同樣記載 `"ap": 33`，新舊兩版一致，佐證 `33` 才是
>    正確值，`31` 是外部表格轉錄筆誤，不代表版本差異。
>
> 附帶確認一項先前只有間接證據的公式：**敵/友單位(0x7AB0D 表)是「每級成長值」，出場即時
> 最大 HP/MP = 該列 HP/MP 欄位 × 等級**(不是玩家角色表那種 base+(LV-1)×growth)。用 ch24
> `map24_units.json` 的 `native_record_word42`/`native_record_word46`(已由既有 constructor
> 反組譯證據 `high=u16(record+2)*level` 產出，見 SESSION-HANDOFF 2026-07-27 條目)逐筆代入
> 驗算，全部吻合，例如惡魔 LV14：HP 40×14=560、MP 5×14=70，與 JSON 內 `native_record_word42:
> 560`／`native_record_word46: 70` 精確相符。AP/DP/DX 是否也是同一 growth×level 公式尚未被
> 獨立反組譯證實(remake 匯出的 map JSON 目前 `ap`/`dp`/`mv` 欄位是每個單位相同的佔位值，不是
> 真實算出值)，詳見 doc58「續二十五」。
>
> **`tools/dump_exe_tables.py` 的 `ANCHORS` dict 修正完成(2026-08-20，第 6 輪)**：上面第 82 行
> 標的「需要先改成讀新版 offset」在這輪補上——全部 9 張表(item/shop/spell/char/growth/learn/
> resist/crit/unit)的 `ANCHORS` 已改為第 60-70 行表格記載的新版(0x7xxxx)offset，並把兩處先前
> 寫死舊版 offset、未經 `ANCHORS` 間接引用的表(`dump_native_movement_cost_rows` 的
> `file_base`、`dump_class_equip_types` 的 `base`)也依同一 `0x25214` 固定位移換算並逐 byte 驗證
> 通過(前者 `0x55445→0x7A659`，後者 `0x55689→0x7A89D`；兩表恰好首尾相接、零間隙，佐證位移量
> 正確)。對現有 `FD2.EXE`(509158 B)重跑 `dump_exe_tables.py`：**9/9 錨定特徵命中，自驗全部通過**
> (含 growth/unit/職業魔抗/職業暴擊/裝備相容/索菲亞初始物品等既有斷言)。`tools/test_dump_exe_tables.py`
> 裡硬寫舊版 `0x55445` 的 `test_native_movement_cost_rows_have_exact_29_by_20_boundary` 同步改
> 為新版 `0x7A659`，4/4 單元測試通過。

### 各表欄位語意

- **物品(23B)**：`TY AP HT DP EV S1 S2 R1 R2 K1..K6 MM(2) ??`；TY 01=劍…20=道具；K1 為「使用後作用」碼表(見 modify2)。武器編號須 ≤0x7F。
- **法術(7B)**：`DA DA HT DS RN MP WH`(傷害/命中/距離/範圍/MP/對象)。0x10 距離旗標=直線。
- **人物出場(24B)**：`RA CL LV HP HP MP MP MV MG×4 IT×6 AP AP DP DP DX DX`。
- **升級成長(11B)**：`AP0 AP1 DP0 DP1 DX0 DX1 HP0 HP1 MP0 MP1 MG`(各屬性 min/max+1，最後是習得索引)。攻略已附 64 列全表。
- **敵/友單位(10B)**：`RA CL HP MP AP DP DX MV EX`(每級成長)。攻略已附約 70 種敵我單位全表。

## C. FDFIELD.DAT 地圖格式 [攻略，容器層已驗證]

容器外層為 LLLLLL(見 `01-…`)。攻略 modify2 描述每張地圖由三段組成，各地圖一組 3×uint32 指標：

1. **地圖構成**：寬(2)、高(2)、然後每格 2×uint16 =(地形編號, 觸發事件/寶箱編號)，先水平後垂直。
2. **地圖控制與寶箱**：地圖編號、己方可出場數、敵友總數、16 組回合事件(3B)、16 組保留、16 組寶箱(3B)、出場人物資訊(每位 26B)。
3. **人物出場位置**：人數(2)、每組 3×uint16 =(X, Y, 肖像；00=己方)。

出場人物 26B：`陣營 肖像 種族 職業 等級 物品×8 法術×8 出場回合 掉落物(4)`。

> [假設] 攻略所說「3 個 4 byte 指標 / 地圖」與第 1 輪實測的「100 個資源 offset」需對齊：
> 可能 100 個 offset 即 ~33 張地圖 × 3 段。第 2 輪用 unpacker 拆出後逐一驗證。

## D. FDSHAP.DAT 地形控制 [已驗證]

見 `01-container-and-asset-formats.md` §5。0x2422E 起、300 格 × 4 byte。

## 附錄：編號表

肖像編號(0x00–0x41)、職業編號(0x00–0x1A)、法術編號(0x00–0x23)、人物升級成長 64 列、
敵我單位約 70 列 — 完整數值見 `references/text/memory.md` 與 `references/text/modify2.md`，
結構化版本見 `02-game-data-reference.md`。
