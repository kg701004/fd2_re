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
> **AP/DP/MV 缺口已解決(2026-08-31，M5 Phase 3)**：對 constructor `0x10c50`(body
> `0x10c50..0x11010`，含先前只驗過一半的 `0x10d7f..0x10e23` 這段)做官方 IDA/Ghidra 完整
> decompile(`ghidra_batch_probe.py` `decompile` action)，一次看到 HP/MP 之外的 AP/DP/MV/DX
> 全部寫入邏輯，答案是「growth×level，但跟 HP/MP 不是同一種形狀」：
> - **AP(`+0x37`)/DP(`+0x39`)：確認也是 growth×level**，high branch(敵/友表,
>   `raw_unit_key>=0x44`)公式跟 HP/MP 一模一樣——`base_ap = table_byte[+5]*level`、
>   `base_dp = table_byte[+6]*level`(這正是 `docs/data/exe_tables/unit.json` 裡那個「每個單位
>   相同」的 `ap`/`dp` 欄位本身──它從頭到尾就是這個 growth-per-level byte，只是從沒被乘上等級)。
>   lower branch(角色出場式 24B+11B 表，`raw_unit_key<0x44`)則是
>   `growth_byte*level + base_word`(注意**不是** `level-1`，跟 HP/MP 的 lower branch 形狀不同，
>   直接讀 pseudocode 逐行核對過，不是套用假設)。
> - **MV(`+0x3b`)：確認是 flat 值，完全沒有等級縮放**——high/low 兩個 branch 都是
>   `puVar16[0x3b] = puVar12[8 或 7]` 直接複製，不涉及乘法。原本以為的「MV 缺口」其實不是
>   縮放問題，而是舊 `base_stats(exe, race, cls)` 用 FDFIELD 的「敘事身分」race/cls 去查表，
>   跟 constructor 實際用的 `raw_unit_key` 索引表常常對不上同一列(職業名顯示錯位那個已知
>   bug的同一根因)，MV 因此常常也撈到錯的列，不是缺公式。
> - **DX(`+0x3e`)**：附帶確認也是跟 AP/DP 同形狀的 growth×level(high:
>   `table_byte[+7]*level`；low: `aux_growth*level + base_word`)，但 DX 沒有獨立匯出欄位
>   (只間接餵給 HIT/EV 公式的 `bs["dx"]`)，這次沒有動它——`hit_ev_for_unit()` 目前仍吃舊的
>   `base_stats()` flat `dx`，同樣的「race/cls 對錯列」+「沒乘等級」兩個問題大機率也存在，
>   留給後續一次單獨的 HIT/EV RE 工作，不在本輪 AP/DP/MV 範圍內。
>
> 用 ch24 `map24_units.json` 那隻 LV14 惡魔(`native_constructor.record = [5,26,40,0,5,30,18,6,6,180]`)
> 驗算：AP=30×14=420、DP=18×14=252、MV=6(flat)，跟修正後 JSON 完全相符。跨全部 30 個
> `mapN_units.json`(map0-29)抽測：1818 個 high_class 單位裡，舊 flat 值與新公式值不同的比例
> 高達 98%(AP)/98%(DP)/87%(MV)，證實這不是邊緣案例而是全面性的資料錯誤。已用
> `tools/native_ap_for_raw_unit_key()`/`native_dp_for_raw_unit_key()`/`native_mv_for_raw_unit_key()`
> (mirror 既有 `native_record_word42/46_for_raw_unit_key()`寫法)算出正確值，`tools/export_units.py`
> 的 `main()` 生成流程與新的 `tools/patch_units_ap_dp_mv.py`(mirror 既有
> `patch_units_hit_ev.py`寫法，只動 ap/dp/mv 三個 key)都已接上；30 個 `mapN_units.json` 已
> 全部重新 patch(每份 100% 單位都有可信 native provenance，0 skipped)。`go build ./remake/...`
> `go test ./remake/...` 全綠(純數值變更，無需改任何既有測試)。map30-32(非戰鬥過場地點)
> 依 M5 稽核範圍不在此次 patch 範圍內。
>
> **DX 缺口已解決,HIT/EV 已接上正確 base(2026-08-31,M5 Phase 3 後續)**：上面標的「留給後續
> 一次單獨的 HIT/EV RE 工作」在這輪補上。第二輪、獨立於上方 doc 文字的 `ghidra_batch_probe.py`
> `decompile 0x10c50` + `disasm 0x10d7f..0x10e23` 覆核(不是照抄 doc 文字假設),逐指令核對後
> **doc 原文完全準確**：
> - high branch(`raw_unit_key>=0x44`)：`0x10e09 MOVZX DX,byte ptr [EAX+0x7]` 接
>   `0x10e19 MOV word ptr [EDX+0x3e],BX` —— 精確是 `table_byte[+7]*level`,緊接在
>   AP(`+5`)/DP(`+6`)後面一個 byte,MV(`+8`)則跳過 `+7`,序列一致且無縫。
> - low branch(`raw_unit_key<0x44`)：`sVar6 = *(short *)(puVar12 + 0x16)` 加
>   `pbVar13[4]*uVar8` 寫入 `+0x3e` —— 精確是 `lower_aux_byte[+4]*level +
>   lower_class_word[+0x16]`,跟 AP(aux`+0`/word`+0x12`)、DP(aux`+2`/word`+0x14`)
>   同一組 stride-2 排列,DX 接續在後。
>
> 新增 `native_dx_for_raw_unit_key()`(mirror `native_ap/dp_for_raw_unit_key()`寫法)到
> `tools/export_units.py`,`main()` 的 `hit_ev_for_unit()` 呼叫改吃這個新公式算出的 `base_dx`
> (查不到 native provenance 才退回舊 `base_stats()` flat `dx`)。`tools/patch_units_hit_ev.py`
> (原本只重算 hit/ev 但輸入仍是舊 flat dx,沒真的修好這個 bug)同步改用同一個
> `native_dx_for_raw_unit_key()`,並補上原本缺的 `native_unit_tables.json` 參數。
>
> 驗算沿用同一隻 ch24 LV14 惡魔(`record=[5,26,40,0,5,30,18,6,6,180]`,`inventory_slots=
> [81,183,255,...]`)：DX=`record[7]*14=6*14=84`；item 81 hit=110/ev=0,item 183
> hit=0/ev=0(兩者皆在出場 inventory 前兩格,依 `spawn_equipped_item_ids()` 判定已裝備)；
> `hit=84+110=194`,`ev=84+0=84`。與重新 patch 後 JSON 精確相符(舊值 `hit=114/ev=4`,對應舊
> flat `dx=4`)。跨全部 30 個 `mapN_units.json`(map0-29,1826 個單位)重新 patch:**98.7%
> 單位的 hit 與 ev 值都變了**,跟 AP/DP/MV 那輪 98%/98%/87% 同一量級,證實這也不是邊緣案例。
> `go build ./remake/...`/`go test ./remake/...` 全綠(純數值變更,無需改任何既有測試)。
> map30-32(非戰鬥過場地點)依 M5 稽核範圍不在此次 patch 範圍內。
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

### 2026-09-04 勘誤:`+0x37` 與 `+0x48` **不是矛盾,是兩組不同欄位**

本文件與 `fd2_dosbox_live_helper.py` 的欄位表長期互相衝突:本文件說 AP 在 `+0x37`、
DP `+0x39`、MV `+0x3b`、DX `+0x3e`(constructor `0x10c50` 反組譯),欄位表卻說
AP 在 `+0x48`(實機對狀態卡驗證)。因為這個衝突,`fd2_stat_override.py` 一直不敢碰 MV。

重解 constructor 後答案很單純:**它對同一筆記錄寫入兩組欄位**。

```c
*(ushort *)(puVar16 + 0x37) = ...   // 基礎 AP(growth×level)
*(ushort *)(puVar16 + 0x39) = ...   // 基礎 DP
puVar16[0x3b]               = ...   // MV,u8,直接複製,無等級縮放
*(ushort *)(puVar16 + 0x3e) = ...   // 基礎 DX
*(short  *)(puVar16 + 0x40) = sVar15  // HP
*(short  *)(puVar16 + 0x42) = sVar15  // HP —— 同一個值
*(short  *)(puVar16 + 0x44) = sVar14  // MP
*(short  *)(puVar16 + 0x46) = sVar14  // MP —— 同一個值
```

`puVar16` 宣告為 `undefined1 *`(byte 指標),所以 `[0x3b]` 就是位元組偏移 0x3b,
`(puVar16 + 0x37)` 也是位元組偏移——**不涉及指標型別縮放**。

| 偏移 | 內容 |
|---|---|
| `+0x37`/`+0x39`/`+0x3e`(u16)、`+0x3b`(u8) | **基礎** AP/DP/DX/MV,constructor 依 growth×level 寫入 |
| `+0x48`/`+0x4a`/`+0x4c`/`+0x4e`(u16) | **生效值**,狀態卡顯示的是這一組 |

**算術佐證(三個獨立來源)**:索爾 `+0x37`=6、卡片上短劍寫 `+AP 010`、`+0x48`=16、
畫面顯示 `AP·016`。**6 + 10 = 16**。

因此 `fd2_dosbox_live_helper.py` 原本把 `+0x48` 註記成
「base value before weapon bonus」**是反的**——它是**加成之後**的值,加成前的在 `+0x37`。
已更正。

### 附帶:這解釋了為什麼 HP 的 cur/max 會被標反兩天

constructor **把同一個值 `sVar15` 同時寫進 `+0x40` 與 `+0x42`**(MP 的 `+0x44`/`+0x46`
亦然)。單位出生時 cur == max 是**設計如此**,所以任何拿新生/滿血單位做的欄位對照
都**不可能**分辨這兩個 offset。這是 2026-09-04「退化樣本」診斷的獨立佐證
(見 `13-battle-menu-system.md` 該日段落)。

### MV 解除封鎖

`+0x3b` 已確認:讀到索爾 = 4,與狀態卡 `MV·04` 相符;寫入 20 後讀回 20。
`fd2_stat_override.py` 新增 `--ours-mv`,並把上限夾在 60——可移動格是 flood fill,
地圖才 ~20×60,設上萬沒有意義且有風險。

## `0x3776e` = heap free,與 `0x3706e`(配置)是對稱的一對(2026-09-10)

`0x3776e` 是 `dump_chapter_beats` 最後一個未命名原語。doc13 記「語意仍是推測,**未證實**」
(並提醒被反組譯成 memmove 的是它的鄰居 `0x3771c`)。**「未證實」說的是證據不足,
而證據是可以去產生的**——本輪展開兩層,五條互相獨立的證據都指向同一個結論。

**第一層(thunk)完全對稱**:

```
0x3706e:  push ebp ; mov ebp,esp ; push [ebp+8] ; call 0x3707e ; add esp,4 ; pop ebp ; ret
0x3776e:  push ebp ; mov ebp,esp ; push [ebp+8] ; call 0x3777e ; add esp,4 ; pop ebp ; ret
```

**第二層(實作)共用同一組 heap 全域**:

| | `0x3707e`(配置) | `0x3777e`(本支) |
|---|---|---|
| heap 描述子 | `eax=0x527a8` / `ebx=0x527b0` / `edx=ds` | **完全相同** |
| 核心呼叫 | `call 0x3d5c0` → **回傳**區塊指標 | `call 0x3d670`,**吃**區塊指標、無回傳 |
| 收尾 | `byte [0x5419c] = 0` | **完全相同** |
| 邊界行為 | `size == 0` 直接回 0;取不到時走 `0x3d842`/`0x3da42` 重試迴圈 | 無 |

`size==0 → NULL` 與「取不到 → 嘗試整理再重試」是 malloc 的標準形狀;對側吃一個指標、
不回傳值、共用同一個 heap 描述子,就是 free。

**第五條證據來自使用端**:`0x24336`(doc35 §13)在函式尾對**恰好那兩個先前取得的指標**
(`0x3706e` 配置的畫面緩衝、`0x111ba` 載入的資源)各呼叫一次 `0x3776e`,之後兩者都不再
被使用——教科書式的 free 位置。

**`0x3776e` 的參數個數 = 1**:`derive_native_argcounts` 判 CONFIRMED(205 個呼叫端,帶
`callsites_disagree` 旗標);thunk 本體也只取 `[ebp+8]` 一個參數。

~~**誠實範圍**:`0x3d670` / `0x3d5c0` 本體本輪未展開;`0x5419c` 用途也未追。~~
**2026-09-11 `0x3d670` / `0x3d5c0` / `0x5419c` 三者都已補完,見下一節。** doc13 的「未證實」註記不刪除,改為指向本節。

## `0x3d670` / `0x3d5c0` 本體:boundary-tag 配置器,`heap_free` 由推得升級為逐指令證實(2026-09-11)

前一節把 `0x3776e` 命名為 `heap_free`,誠實範圍寫著結論是由「呼叫形狀 + 共用 heap 描述子
+ 對稱性」推得。本輪展開兩個實作,結論不變而證據升級。

**`0x3d670`(free)**——教科書式的 boundary-tag 釋放:

```
eax == 0            -> 直接返回                  ; free(NULL) 是 no-op
esi = eax - 4                                    ; 區塊表頭在使用者指標前 4 bytes
eax = dword[esi] ; (al & 1) == 0 -> 返回          ; 最低位元=in-use;已釋放就 bail(double-free 防護)
al &= 0xfe                                       ; 清掉旗標得到區塊大小
edi = esi + eax                                  ; 相鄰的下一塊
(dword[edi] & 1) == 0 ->                         ; 下一塊空閒 -> 向前合併
    edi == [ebx+8] -> [ebx+8] = esi              ; 需要時更新 rover
    eax += dword[edi] ; dword[esi] = eax         ; 併大小
    [ [edi+4] + 8 ] = [edi+8]                    ; 雙向空閒串列解鏈
    [ [edi+8] + 4 ] = [edi+4]
    dec dword[ebx + 0x18]                        ; 空閒區塊計數--
```

**`0x3d5c0`(malloc)**——同一組結構:`size == 0` 回 NULL;`add eax,7` 後以進位偵測溢位;
`and al,0xfc` 對齊 4;用 `sbb/and` 把大小夾到最小 12;與 `[ebx+0x10]`(最大空閒區塊快取)
比較,超過就直接失敗;否則自 `[ebx+8]` 沿 `[esi+8]` 走空閒串列直到哨兵 `[ebx+0x1c]`。

**因此 `0x3776e` = free 不再是推論**:free(NULL) no-op、in-use 位元、向前合併、雙向串列
解鏈、空閒計數遞減——五個特徵同時出現,不是別的函式會有的形狀。

**順帶解出 heap 描述子(`0x527b0`)的部分欄位**:

| 偏移 | 用途 | 依據 |
|---|---|---|
| `+0x08` | rover / 空閒串列目前位置 | free 更新它、malloc 自它起走 |
| `+0x10` | 最大空閒區塊大小快取 | malloc 先比它決定要不要直接失敗;走完串列後回寫 |
| `+0x18` | 空閒區塊計數 | free 合併後 `dec` |
| `+0x1c` | 空閒串列哨兵 | malloc 走到它就停 |
| `+0x20` / `+0x24` | heap 範圍上下界 | free 的範圍檢查 |

**`0x5419c` 也一併查掉:它在這份 image 裡是死的。** 用 **LE fixup 表**(不受線性反組譯
對齊影響)查「哪些程式碼位置指向 `0x5419c`」,結果是**恰好 2 處**——`0x370de`(malloc 收尾)
與 `0x37799`(free 收尾),**兩處都是寫 0,全 image 沒有任何讀取**。應是 Watcom runtime 的
殘留狀態旗標,讀取端已被連結器移除。這不是「用途未知」,是「有寫無讀」——兩者是不同的結論。

**誠實範圍**:`0x3d5c0` 只展開到走空閒串列那一段(`0x3d619` 之後的切割/回填未逐條讀);
`0x3d670` 的 `0x3d6b2` 之後那條「不合併」路徑只讀到範圍檢查與 `[ebx+0x14]/[ebx+0x18]` 的
除法啟發式,未完整展開。本節主張的五個特徵都落在已讀的部分。

## 2026-09-11:戰場單位 record 舊標記整段偏移 8 —— 座標與道具欄位已由消費端訂正

本節的欄位表混了兩代來源:有出處的列(camp `+0x06`、race `+0x1f`、class `+0x20`、
HP `+0x40/+0x42`、MP `+0x46`、AP `+0x48`)都是由 `0x10c50` constructor 或明確 writer trace 定的;
另一批沒有出處的舊標記(`XX,YY` / `Z1,Z2,Z3` / `FA` / `NN` / `IT×8`)承自更早的表。
本輪在追道具效果列時發現**這批舊標記整段比實際位置大 8**,其中兩列已由消費端直接證死:

| 舊表寫的 | 實際 | 證據(互相獨立) |
|---|---|---|
| `0x08` XX, YY | **`0x00` x、`0x01` y** | (a) constructor `puVar16[0] = local_24; puVar16[1] = local_1c`;(b) `0x14818` 末段收集迴圈用 `*pbVar3 + pbVar3[1]*width` 算格子索引 |
| `0x12` IT×8(狀態+編號) | **`0x0a` 起,8 槽 ×2 byte**(偶=狀態,奇=編號) | (a) `0x1b722(unit,slot)` = `byte[unit + slot*2 + 0x0b]`(道具 id);(b) `0x1b8a6(unit)` 逐槽 `test byte[unit + slot*2 + 0x0a], 0x80` 數非空槽,上限 8;(c) constructor `[10]=0x40; [0xb]=來源; [0xc]=0x80` |

舊表對**狀態碼**的描述(`0x40`=裝備、`0x00`=持有、`0x80`=空)反而是對的,constructor 與
`0x1b8a6` 都吻合;錯的只有基底偏移。這一列特別要緊——任何照 `0x12` 去讀背包的程式會整個讀錯。

**其餘三列的偏移同樣少 8(依據同樣是 `0x10c50` constructor 的逐欄寫入),但只有「寬度與位置吻合」這層證據,名稱仍是未經證實的舊標記**,
因此本表只把偏移標成待證,不改名:

- `0x0A` Z1,Z2,Z3 → `0x02..0x04`(constructor `[2] = FUN_00011019(); [3] = 0; [4] = 0`,恰好三個 byte)
- `0x0F` FA 肖像 → `0x07`(constructor `[7] = bVar2`)
- `0x10` NN(2) 姓名 → `0x08`(constructor `[8] = bVar2; [9] = 0`,恰好兩個 byte)

**一條記下但**不**命名的線索**:constructor 把**同一個來源 byte**(`*(byte *)(iVar9 + 0x84)`)
同時寫進 `+0x07` 與 `+0x08`。若上面的舊標記在偏移訂正後為真,那就是「肖像編號」與「姓名編號」
共用同一個角色 id。這條線索的實用意義在於 doc27 §6.7 記的傳送法杖閘門:
`0x1bdad` 之後檢查 `unit[+8] == 0x18` 且 `word[+0x46](max MP) >= 0x14`——若 `+8` 真是角色 id,
那條閘門就是「限定某一名角色、且 max MP ≥ 20 才能用」。**但 `+8` 的唯一消費端只把它跟 `0x18`
相比,沒有任何一處以它去索引名字表或肖像表**,所以本輪不命名,只把證據與推測分開記下,
留給下一輪去找那個索引用的消費端。
