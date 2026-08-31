# 28 — 全 30 關玩家可見目標候選（攻略整理 × 部分 handler 對照）

> **證據邊界更正（2026-07-28）**：青衫攻略是玩家可見規則的E3 authored
> reference，可建立逐章候選與測試案例，但不能「完美印證」raw predicate。
> doc26的`0x3453e(idx)`只直接證實讀取runtime record `byte[+5]&1`；
> constructor、HP writer及其他caller不足以把它全域命名成「指定單位存活」。
> 本篇把攻略30關的勝利／失敗／加入條件結構化，並記錄部分handler對照；
> 它不是可直接生成忠實campaign的ground truth。
> 來源:青衫圖文攻略(僅整理事實性規則 + 標出處,不轉載原文)。章號對應:**攻略第 N 章 = `battle_events.json` chapter N−1**。

## 1. 玩家規則與 native 候選的交叉對照（不是 ABI 證明）

| native/raw 候選(doc 26) | 攻略對應 | 可安全採用的結論 |
|---|---|---|
| `0x3453e(idx)`讀`record+5 & 1` | 每關「失敗條件:索爾死亡 + 某某死亡」 | 某些caller很可能服務護衛／目標判定；每章仍須保留branch方向與slot provenance |
| `0x33499(id)`查persistent roster identity | 加入條件「若某角色未出現便消滅完則不加入」 | 可作入隊／在隊條件候選；招募side effect與時機仍須handler證據 |
| result code、回合global與event dispatcher | 攻略「第N回合後…援軍/連鎖」 | 可建立E2測試案例；不能由攻略把result code或event id全域命名 |
| 非default勝利branches | 「消滅卡特那／擊毀機甲隊長／解除防衛系統」 | 玩家可見目標可信；native slot、predicate及後續流程仍逐章驗證 |

> 攻略第30章的魔神時序是重要E3測試oracle，但目前不得直接寫成
> `[0x53bef] + unit_state + result code1`的完整native實作；須由ch29 battle
> handler／event dispatcher逐branch閉合。

## 2. 全 30 關目標表

「失敗」欄省略每關必有的**索爾死亡**(主角,全關通用);只列額外護衛目標。

| 攻略章 | bev ch | 標題 | 勝利條件 | 額外護衛(死亡=敗北) | 加入角色(條件) |
|---|---|---|---|---|---|
| 1 | 0 | 初試身手 | 敵全滅 | — | 哈諾(出現前勿滅完) |
| 2 | 1 | 羅德鎮 | 敵全滅 | **村民全滅** | 希莉亞 |
| 3 | 2 | 往塞拉村途中 | 敵全滅 | — | 鐵諾(未死) |
| 4 | 3 | 塞拉村前 | 敵全滅 | — | — |
| 5 | 4 | 塞拉村 | **消滅卡特那** | — | 瑪琳 |
| 6 | 5 | 普里茲港 | 敵全滅 | — | 貝克威 |
| 7 | 6 | 往王城途中 | 敵全滅 | — | 凱麗(未死) |
| 8 | 7 | 王城前的戰鬥 | 敵全滅 | — | 洛娜 |
| 9 | 8 | 騎士的抉擇 | 敵全滅 | — | 萊汀 |
| 10 | 9 | 洞窟中的激戰 | 敵全滅 | 索菲亞、卡納恩三世 | 萊汀、索菲亞 |
| 11 | 10 | 幻之森林 | 敵全滅 | — | 珊 |
| 12 | 11 | 北山道 | 敵全滅 | 米亞斯多德 | 米亞斯多德 |
| 13 | 12 | 哈斯米爾之戰 | 敵全滅 | **精靈族全滅** | — |
| 14 | 13 | 平原的會戰 | 敵全滅 | — | — |
| 15 | 14 | 拉卡湖的激戰 | 敵全滅 | 賽可邦勒 | 賽可邦勒 |
| 16 | 15 | 冰原之戰 | 敵全滅 | 蜜蒂 | 蜜蒂(HP320+/18回合內/部下陣亡未過半) |
| 17 | 16 | 血與冰之刃 | 敵全滅 | — | 凱拉斯 |
| 18 | 17 | 遙遠的彼岸 | **黑暗騎士死亡** | 約拿、蘭斯洛特 | 約拿、蘭斯洛特 |
| 19 | 18 | 黑暗中的狙擊 | 敵全滅 | 巴拿羅西亞 | 巴拿羅西亞(出現前勿滅完) |
| 20 | 19 | 死亡般的沈寂 | **沼澤怪物外敵全滅** | 謝多、精靈全滅 | 謝多;達可塞(15回合內) |
| 21 | 20 | 亞述森林 | 敵全滅 | 羅蘭、希爾法 | 希爾法、羅蘭 |
| 22 | 21 | 遠古呼喚 | 敵全滅 | 希爾法 | 莎拉(出現前勿滅完) |
| 23 | 22 | 向天空之旅 | **擊毀機甲隊長** | 希爾法、卡里斯、羅德曼 | 卡里斯(持天空之鑰) |
| 24 | 23 | 在天空的彼方 | 敵全滅 | — | — |
| 25 | 24 | 火焰的審判 | 敵全滅 | 聖寇拉斯 | 亞奇梅吉、聖寇拉斯 |
| 26 | 25 | 未知的迴廊 | 敵全滅 | 悠妮、亞奇梅吉 | 渥德 |
| 27 | 26 | 命運的交會點 | **擊毀機甲隊長** | 悠妮 | — |
| 28 | 27 | 探索者 | **擊毀機甲隊長** | 悠妮 | — |
| 29 | 28 | 探索者(防衛) | **解除防衛系統** | 悠妮 | — |
| 30 | 29 | 傳說的終章 | **空魔神死亡** | 悠妮 | —(地/水/風/火魔神連鎖) |

> 註:攻略章數與 `battle_events.json` 的 30 個 chapter 數一致(原版 33 張 FDFIELD 圖含少數非戰鬥/分支圖)。個別 bev ch 與攻略章的精確戰場對位,以實作時逐關核對為準。

## 3. 玩家可見勝利條件分類（先作 authored candidate）

1. **殲滅**（多數攻略所述）：default handler `0x205b4/0x205be` 的直接
   規則是 camp0 活躍列與 record0 raw bit0 產生 code0/1/2；「敵全滅」是
   玩家可見對照，不能取代 raw camp／bit 的逐關驗證。
2. **擊殺指定目標**:消滅卡特那(ch4)、黑暗騎士死亡(ch17)、擊毀機甲隊長(ch22/26/27)、空魔神死亡(ch29)。
3. **特殊**:解除防衛系統(ch28)、沼澤怪物外全滅(ch19)。

攻略所列的**玩家可見失敗條件**可正規化為
`索爾死亡 OR 任一護衛目標死亡`；括號中的native predicate與branch方向
不得預設為`unit_state(idx)==0`，須由各章handler證明。

## 4. remake DSL(把攻略目標資料化,對映 doc 19/26 + battle_events.json)

```jsonc
// 每關 campaign 節點
{
  "win":  { "any": ["annihilate"] },              // 或 {"kill":"機甲隊長"} / {"custom":"解除防衛系統"}
  "lose": { "unit_dead": ["索爾", "悠妮"] },        // 護衛目標(對應攻略失敗條件)
  "recruit": [                                     // 對應 roster_has + 出現邏輯
    { "who": "莎拉", "if": "出現後未被搶先殲滅" }
  ],
  "events": [                                      // 回合/連鎖(對應碼1 + [0x53bef])
    { "when": {"turn>=":2, "unit_dead":["地魔神"]}, "do":"spawn:水魔神+機甲" }
  ]
}
```
- `lose.unit_dead` ← 攻略護衛清單(本表第 4 欄)+ 索爾
- `win` ← 本表第 3 欄
- `recruit` ← 本表第 5 欄(「出現前勿滅完」= 需該角色已登場才可招募)
- `events` ← 攻略「事件/說明」段的回合觸發(如 ch29 魔神連鎖、ch6 第七回合獸人出現)

→ 攻略與 `battle_events.json` 只能作 authored/normalized 起點，**不能取代逐章
handler、postbattle、town/shop/preparation 與 persistent roster 的證據**。凡會改變
勝敗分支、招募、獎勵、戰後流程或存檔邊界的章節仍須逐章閉合，未閉合者fail closed。

## 5. 對 handler 碼語意的最終說明(誠實)

handler 的 `0x3453e(idx)` 只直接證實讀取 runtime record
`byte[+5]&1`；攻略可旁證某些caller涉及護衛／目標單位，但不能把這個raw
predicate全域命名成「存活」。同樣地，result code 1/2 與玩家層中途／勝／敗／
續的精確映射仍須由外層戰役迴圈與各caller閉合。
這個映射**會影響重製**：攻略可協助命名玩家可見目標，但 handler return code、
中途事件、招募與 postbattle side effects 才決定原版流程。尚未取得 E0/E2 證據的
條件只能標為 authored approximation，不可當成原版等價規則。

> 相關:doc 26(handler 條件→動作)· doc 25(事件系統)· doc 24(戰役迴圈碼分派)· doc 02(數值/公式)· doc 19(腳本系統)。資料:`docs/data/battle_events.json`、`references/text/fd2.md`(青衫攻略,本機)。

## 6. ch25(raw24)「敵轉友」機制範圍確認——結論:不存在,亞奇梅吉是標準 JOIN,不是 record 轉換(2026-08-31)

**背景**:`91-worklist.md`「ch26 亞奇梅吉(ii)範圍確認」上一輪(2026-08-30)把這題評估為「大/不確定範圍」，理由是「map24 unit54(亞奇梅吉)`camp:"enemy"`，doc28 卻說她會被招募——這個『敵人被擊敗後轉換成永久隊友』的原生轉換機制，本專案從未反組譯過」。本輪奉命純靜態反組譯 ch25(raw24)的 win-check(`table_win[24]`)與 postbattle(`table_post[24]`)handler，直接查證這個假設的轉換機制是否存在。

**結論(高信心)**:**這個轉換機制根本不存在，也不需要存在**。亞奇梅吉的招募走的是本專案早已完整反組譯、記錄在 doc25 §9.3 的標準 `JOIN` constructor(`0x112a5(join_id)`/`MaterializePersistentUnit`)，跟 ch00 序章索爾/悠妮/亞雷斯/蓋亞、ch16 JOIN(18)是**同一支函式、同一種呼叫模式**，唯一差別只是這次的呼叫端位在 postbattle handler 尾端(用 tail-jump 共用程式碼），不是 dialogue beat 裡的直接 CALL。她 map24 的 `camp:"enemy"` 純粹是戰鬥本身的敵我旗標,跟她事後怎麼加入名冊(標準 JOIN)是兩件互不相關的事——不需要,也沒有,任何「把一筆敵方 record 原地改寫成己方 record」的特殊 writer。

### Step 1:跳表 index 公式複驗(比照 `ch29disasm`/`ch30disasm`/`ch10disasm` 既有方法論)

`tools/ghidra_batch_probe.py`一次 `bytes` 讀出 `0x51b19`(`table_win`)與 `0x51de9`(`table_post`)各 128 bytes(32 個 dword)。與既有文件記錄的 index 9/21/26/27/28/29/30/31 逐 byte 吻合(`ch10disasm`/`ch29disasm`/`ch30disasm`/`ch2729-static`四輪獨立記錄的既知值全部通過 sanity check)：

- **`table_win[24]` = `0x20b14`**(raw24 = story ch25,依「玩家第 N 章 = raw(N-1)」慣例)
- **`table_post[24]` = `0x24df2`**

### Step 2:win-check `0x20b14` 完整反組譯——單一 record 死亡檢查,跟亞奇梅吉無關

10 條指令,`RET` 結尾,`stop_reason:"ret"`,`truncated:false`：

```c
void ch25_win_check(void)
{
  FUN_0003702f(8);                 // 標準 prologue
  FUN_000205be();                  // default handler(殲滅 based 預設結果)
  if (FUN_00034894(0x10) != 0) {   // record[16].+5 & 1 != 0(單位16陣亡)
    *(dword*)0x53ecc = 1;          //  → 覆寫成敗北
  }
  return;
}
```

`record[16]` 換算:map24_units.json `own_deploy` 陣列長度 = 16(部署格 16 個),比照 `ch10disasm` 輪已驗證的 `record[N] = own_deploy_count + 本地 index` 公式，`record[16] - 16 = 0` → **`map24_units.json units[0]`**：`camp:"own", portrait:26, native_record_byte8:26, group:0`。doc28 §2 對 ch25(raw24)列的護衛欄位剛好是「聖寇拉斯」一人——本欄目換算結果與 doc28 護衛表精確吻合，win-check 只保護她，跟亞奇梅吉完全無關(她不是這個 handler 檢查的對象)。

### Step 3:postbattle `0x24df2` 完整反組譯——40 條指令,直線+單一 tail-jump,零分支,零死亡檢查

flow-directed `disasm`(`max_bytes=400`,`stop_reason:"jmp"`,`truncated:false`,`0x24df2..0x24e7b`共 137 bytes)。逐 byte 核對(`bytes` action 獨立讀出 142 bytes,與 disasm 結果逐位元組吻合)：

```c
void ch25_post_handler(void)
{
  FUN_0003702f(0x28);                          // 標準 prologue(引數 0x28=40)
  FUN_00015f84(sel=6, [0x53a79], 0xa0000,       // 戰後對話/演出呼叫#1(9 引數)
               0x140, 0xcd, 0x4c, 0x4a, 0x13, 1);
  FUN_000135dd(4, 0x10);                        // 鏡頭微移(doc25/47 已知同款呼叫)
  FUN_00010b4e(2);                              // spawn_group(2) —— 亞奇梅吉所在的 group!
  FUN_0001366a(0x4b);                           // 已知 spawn_group_with_intro 尾段呼叫(doc25 §6.1)
  FUN_00015f84(sel=7, [0x53a79], 0xa0000,       // 戰後對話/演出呼叫#2(selector 6→7)
               0x140, 0xcd, 0x4c, 0x4a, 0x13, 1);
  FUN_000112a5(0x1a);                           // JOIN(26) = 聖寇拉斯 直接 CALL
  FUN_00011506();                               // persist-sync(doc56 已知:按 +8 比對,把完整 0x50-byte record 從 runtime 複製進 persistent roster)
  // 尾端不是 RET，是帶引數的 tail-jump：
  goto 0x237c8;  // 呼叫前先 PUSH 0x1d(=29)
}
```

逐指令原始 bytes(節錄關鍵段，其餘見 raw disasm)：`6a 02`(PUSH 2)`e8 18 bd fe ff`(CALL 0x10b4e)…`6a 1a`(PUSH 0x1a)`e8 34 c4 fe ff`(CALL 0x112a5)`83 c4 04`(ADD ESP,4)`e8 8d c6 fe ff`(CALL 0x11506)`6a 1d`(PUSH 0x1d)`e9 48 e9 ff ff`(**JMP 0x237c8，不是 CALL/RET**)。

**全程 137 bytes 內沒有任何一條指令呼叫 `FUN_00034894`(死亡位元檢查)，也沒有任何 `JZ`/`JNZ` 條件分支**——這代表 `table_post[24]` 對亞奇梅吉(或聖寇拉斯)是否在戰鬥中存活/死亡完全不查，是無條件直線執行。`table_post[chapter]` 本身也是 `FUN_00025bf4` 主迴圈在 `[0x53ecc]==2`(已判定獲勝)時無條件呼叫(doc25 §「戰場重設」行已記錄),因此只要贏了 ch25(即滿足 win-check 的「聖寇拉斯活著」條件),這整段「spawn_group(2) → JOIN(26) → JOIN(29)」序列就會無條件跑一次。

### Step 4:`0x237c8` 尾跳目標——確認就是 `call_scan(0x112a5)` 命中的第 12 個 caller,`CALL 0x112a5` 緊接在跳入點

先前對 `0x112a5` 做的 `call_scan`(全 EXE 窮舉,非 `xref_to`,回避 doc98 記載的「`-noanalysis` 下 `xref_to` 不可靠」已知盲點)命中 28 個真實 CALL 位址,其中 `0x237c8` 正是其一。直接對 `0x237c8` 反組譯(3 條指令,`stop_reason:"jmp"`)：

```
0x237c8  CALL 0x112a5     ; 消耗 table_post[24] 尾端 PUSH 進來的 0x1d(=29) 引數
0x237cd  ADD  ESP,0x4
0x237d0  JMP  0x231f2      ; 繼續跳往另一段共用尾段(未展開，非本輪範圍)
```

`0x237c8` 落在 `table_post[10]`(`0x23790`)與 `table_post[11]`(`0x237d5`)之間，是**另一章 postbattle handler 內部、被多章共用的一段 tail 程式碼**(Watcom 編譯器常見的 tail-merge，不代表跟 ch11 有劇情關聯)——`table_post[24]` 用 `JMP` 而非 `CALL` 跳進來，靠呼叫前 `PUSH 0x1d` 把引數留在堆疊上，讓共用的 `CALL 0x112a5` 直接讀到 `join_id=29`。**這條鏈路(`PUSH 0x1d; JMP 0x237c8` → `CALL 0x112a5`)就是 `JOIN(0x1d=29)` 的完整、無截斷證據**——`0x1d`=29(十進位)精確等於亞奇梅吉的 `native_record_byte8`/DATO id。

### Step 5:交叉核對——`native_join_constructor.json` id29/id26 兩列都是已存在、已驗證的正式列,不是空表

`remake/assets/data/native_join_constructor.json`(32-row 表,schema 綁定 FD2.EXE 精確 size/MD5/SHA256)：

- **id 29**(`default_file_offset:0x55e59`,`growth_file_offset:0x55fe0`,對應 `0x55ba1+29*0x18`/`0x55ea1+29*0x0b` 公式)的 `default_raw`/`growth_raw` 十六進位值，逐 byte 展開後與 `map24_units.json` unit54(亞奇梅吉)的 `native_constructor.record`(24 bytes)/`aux_record`(11 bytes)**完全相同**——這不是巧合，是這個專案既有的資料匯出工具鏈本來就用同一份 `0x112a5` constructor 公式反推 `map*_units.json` 每個 unit 的 `native_constructor` 欄位，所以「map24 unit54 是從 join-table id29 這一列建構出來的」這件事，其實從資料匯出時就已經隱含證實了；本輪的貢獻是**找到原生程式碼裡真的有一條執行路徑對這個 id 呼叫 `0x112a5`**，把資料層的巧合升級成 handler 層的直接證據。
- **id 26**(`0x55ba1+26*0x18`)同樣是已存在的正式列,對應 `map24_units.json` unit0(聖寇拉斯,`camp:"own"`,護衛目標)——她也在同一個 postbattle handler 裡被 `JOIN(26)` 直接 CALL 一次,doc28 §2 對 ch25 的 recruit 欄位本來就寫「亞奇梅吉、聖寇拉斯」兩人並列，本輪的 handler 證據精確對上這兩個名字，不多不少。

### 對 91-worklist.md「敵轉友原生機制」假設的修正

上一輪的假設前提是「她需要一個把 `camp:enemy` record 原地轉換成 `camp:own` 的特殊 writer」。本輪的完整反組譯(win-check 10 指令 + postbattle 40 指令，均 `RET`/`JMP` 收尾、無截斷)證明**這個特殊 writer 不存在，因為根本不需要**：`table_post[24]` 不去碰戰鬥用的 enemy record，而是直接呼叫跟其他任何一個 JOIN 角色(索爾/悠妮/哈諾/id18…)完全同款的 `0x112a5(29)`，從獨立的 join-table(而非戰鬥 record)重新生成一筆全新的 persistent roster record。她的 map24 `camp:"enemy"` 只是「這場戰鬥怎麼呈現/對待這個 unit」的旗標，跟「戰鬥結束後怎麼把她加進名冊」完全是兩條不相交的資料路徑——doc28 原本「先打後收」的敘述在效果上沒錯(玩家確實要先打贏 ch25 才會觸發這段 postbattle JOIN)，但機制上更精確的說法是「贏 ch25 觸發一段無條件 postbattle 演出，演出裡呼叫標準 JOIN，不是把她的戰鬥 record 轉換過去」。

### 誠實邊界與下一步(供未來 wiring 輪參考,本輪不寫 campaign_full.json/partyRoster)

- **未展開**:`FUN_00015f84`(戰後對話/演出呼叫，9 引數，selector 6→7)、`FUN_0001366a(0x4b)`、`0x231f2`(第二個 tail-jump 目標)本輪均只記位址/引數，未逐一反組譯內部——這些只影響演出呈現細節，不影響「JOIN(29) 確實被呼叫」這個核心結論的信心度。
- **未查**:`spawn_group(2)` 召喚的 group2 除了亞奇梅吉(unit54)還有沒有其他 unit(`map24_units.json` 掃描只找到 unit54 一筆 `group==2`，本輪未擴大搜尋其餘章節/地圖是否有共用 group 編號的慣例陷阱，比照 doc99 反覆強調的「每章不可外推」原則，這點留給任何要動 map24 的後續輪自行複核)。
- **未做但也不需要**:`0x55ba1`/`0x55ea1` 這兩個 join-table 基底位址本輪嘗試直接 `bytes` 讀取失敗(`MemoryAccessException`，這兩個位址在 `FD2Analysis3` project 裡目前對應到未映射/不可讀區段，可能是 file_offset 而非 loaded RAM 位址的既有落差，非本輪新發現的问题)——不影響結論，因為 `native_join_constructor.json` 本身已經是這個表格資料的既有驗證來源(schema 綁定 exe size/hash)，本輪只需要「原生程式碼有沒有呼叫 `0x112a5(29)`」這個 handler 層事實，不需要重新讀一次表格內容本身。
- **安全 wiring 方向(下一輪動手前的建議)**:亞奇梅吉的招募現在應該被當成**跟 ch16 JOIN(18)、ch00 序章 JOIN(0/9/4/0x1e) 同一類**的標準 scripted JOIN 事件，用 `remake/cmd/fd2/main.go` 既有的 `partyJoinOrder`/beat-driven JOIN 機制(`b.CharID` 出現時 `append` 進 `g.partyJoinOrder`)去表示，而不是等待任何新的「敵轉友」機制——只需要在 ch25 postbattle 對應的 story/scenario beat 腳本裡補一個 `JOIN(char_id=29)` beat(聖寇拉斯 id26 若尚未有對應 beat，應一併確認/補上，兩者證據等級相同)。**這是下一輪的實作範圍，本輪刻意不動 `campaign_full.json`/`partyRoster`/`ForceDeploy`**，留給使用者審閱本輪反組譯證據後再決定。

> 本節新增位址:`0x20b14`(`table_win[24]`)、`0x24df2`(`table_post[24]`)、`0x237c8`(共用 JOIN tail-jump 片段)。方法論:純靜態 `tools/ghidra_batch_probe.py`(`-readOnly -noanalysis`)，`bytes`/`disasm`/`call_scan`/`function_bounds` 四種 action，全程未碰 DOSBox-X，比照同日 `ch10disasm`/`ch29disasm`/`ch30disasm` 既有方法論。

### 續一(2026-08-31,回應上一輪「安全 wiring 方向」建議):**JOIN(26)/JOIN(29) 兩個 beat 其實從專案早期就已編譯進生產資料,不需要新寫**

上一輪建議「在 ch25 postbattle 對應的 story/scenario beat 腳本裡補一個 `JOIN(char_id=29)` beat」——直接檢查 `remake/assets/cutscenes/handlers/ch25_post.json`(這份檔案早在 `9b68baef`「feat: export editable cutscene handler scripts」就已由既有的 handler-compile 工具鏈從原始反組譯自動產生,`git log --follow` 確認之後只被 `d5200aa0`「chapter handler manifest 系統性 off-by-one」動過,與本輪反組譯發現的內容完全無關)發現這兩個 beat **早就在裡面**:

```json
{ "op": "join", "char_id": 26, "source": { "addr": "0x24e6c", "target": "0x112a5" } },
{ "op": "sync_party", "source": { "addr": "0x24e74", "target": "0x11506" } },
{ "op": "join", "char_id": 29, "source": { "addr": "0x237c8", "target": "0x112a5" } }
```

位址(`0x24e6c`/`0x237c8`,皆 `target:0x112a5`)跟本輪反組譯獨立重新推導出的完全一致——這不是巧合,是同一套 handler-compile 工具鏈本來就會把 `0x24df2` 的原始位元組(含尾端 `JMP 0x237c8` 這種跨函式 tail-merge)正確編譯出對應 beat,只是這份輸出從產生以來從未被連結到「亞奇梅吉的招募機制」這個問題上,直到這兩輪(上一輪的反組譯 + 這輪的資料稽核)才把兩邊對上。

**生產綁定鏈路已核實為現行有效,不是死資料**:`battle_ch25.on_win → postbattle_ch25_persist → handler_binding:"assets/cutscenes/bindings/ch24_post.json" → handler_script:"../handlers/ch25_post.json"`(`remake/assets/scenarios/campaign_full.json`/`remake/assets/cutscenes/bindings/ch24_post.json` 逐層核對);`python3 tools/audit_postbattle_binding_gates.py` 回報 `ACTIVE postbattle_ch25_persist`(非 `blocked`)。

**新增回歸測試**`remake/cmd/fd2/beatrunner_test.go` 的 `TestBeatJoinRecruitsCh25DefeatedEnemyAsPermanentAlly`:直接餵 `map24_units.json` unit54 的真實戰場欄位(`camp:"enemy"`、`native_record_byte8:29`、擊敗後 `HP:0`)進 `{Op:"join", CharID:29}` 這條 production beat,證明:①「敵人陣營+HP歸零」不會擋下既有的 `NativeRecordByte8` 比對邏輯,不需要任何敵轉友專屬程式碼;② materialize 出的 persistent record 正確帶 `HasNativeIdentity/NativeIdentity=29`(原生教會/商店/名冊UI靠這個欄位查表顯示名字,不靠 Go `.Name` 字串,故不需要額外補 `map24_units.json` 的 `name` 欄位);③ 新隊員是滿血個體,不會繼承戰場上的擊敗狀態。`go build ./...`/`go test ./...` 全綠。

**結論:上一輪建議的「wiring 下一步」已不需要執行,亞奇梅吉的招募機制在生產資料裡已經是完整、有效、現在也有回歸測試覆蓋的狀態**——`91-worklist.md` ch26 條目可以真正關閉,不再是「留給未來專門一輪」的開放項目。唯一保留的誠實邊界:`FUN_00015f84`/`0x1366a`/`0x231f2` 演出細節、`spawn_group(2)` 是否還有其他未掃到的 unit,兩點與上一輪相同,不影響本節結論。
