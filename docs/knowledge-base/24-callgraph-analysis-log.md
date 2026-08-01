# 24 — Call-graph 逐步反組譯紀錄(釘死 doc 23 受阻項)

> 本篇原先用遞迴可達 call graph 找到 `0x10010` 的兩個真 caller，並正確
> 排除了線性 sweep 的偽命中；但又錯把「同屬一個函式」推成「同一分支
> 線性串接」。2026-07-29 直接展開 `0x25ec8..0x26151` 與 main
> `0x25dbd..0x25dce` 後已撤回該結論。
>
> 正確結論：新遊戲與四槽讀檔分支各自執行章節 pre-handler，`0x25ebb`
> 返回 0 後由 main 呼叫 `0x117e7`；第三主選單分支才在 `0x26130`
> 呼叫 `0x10010`，由 FD2.SAV current-runtime snapshot 恢復續戰。

## 方法:為何遞迴可達 > 線性 sweep

線性 sweep 從某位址逐位元組解碼,遇到資料(跳表、字串、對齊填充)會把它當指令,產生「偽 call」。
遞迴可達反組譯只從**種子函式**出發,跟隨真正會執行到的 `call`/`jcc`/`jmp`(立即數)目標,標記「可達指令集」。
於是「誰呼叫 X」只回報落在可達集內的 call —— **資料偽命中自動被排除**(它們不可達)。
工具:`callgraph_le.py`,子命令 `reach`/`callers`/`rpath`/`funcof`/`edges`/`jtab`。

## 步驟 1 — 建可達集

```
$ callgraph_le.py FD2.EXE reach 0x25bf4
種子 ['0x25bf4']:可達指令 46782,direct call 點 4218
```
從真 main(0x25bf4,doc 23 已驗證)出發,46782 條可達指令、4218 個直接 call 點。涵蓋面足以做全域 caller 分析。

## 步驟 2 — 釘死 0x10010（current-runtime snapshot loader）的真 caller

```
$ callgraph_le.py FD2.EXE callers 0x10010
可達 caller of 0x10010:
  call @ 0x01a251
  call @ 0x026130
```

**比對(關鍵):**
| 來源 | 對 0x10010 caller 的說法 | 裁決 |
|---|---|---|
| `le_xref calls`(raw 0xe8 線性掃描) | **0 處** | ✗ 漏報(相對位移計算/範圍限制) |
| doc 23 撰寫時某 agent 猜測 | 0x1b051 / 0x26f30 | ✗ **偽命中**(落在漂移/資料區,不可達) |
| **callgraph(可達)** | **0x1a251、0x26130** | ✅ 採信(兩者皆在可達集內) |

→ caller 集合本身已閉合；它只證明 call-site 可達，不能證明不同條件分支
會依原始碼位址順序彼此落下。

## 步驟 3 — 兩個 caller 的語境(disasm 佐證)

```
caller B 0x26130:                       caller A 0x1a251:
  0x26124 push 0; push -1               0x1a245 push 0; push -1
  0x26128 call 0x25977  ; play_bgm(-1)   0x1a249 call 0x25977 ; play_bgm(-1)
  0x26130 call 0x10010  ; 主選單續戰      0x1a251 call 0x10010 ; 戰內重載
  0x26135 play_bgm([0x53c03]→[0x51e63])  0x1a256 jmp 0x1a193  ; 回模組迴圈
```
兩者都先停曲再由 FD2.SAV current-runtime header、runtime roster、event table
及地圖 blobs 重建目前戰鬥；B 之後恢復該章 BGM，A 回到戰內模組。

## 步驟 4 — 反向追到 main + 函式歸屬

```
$ callgraph_le.py FD2.EXE rpath 0x10010
0x25bf4 → 0x25ebb → 0x10010

$ callgraph_le.py FD2.EXE funcof 0x260f5   → 0x25ebb   (章節跳表 call = cutscene)
$ callgraph_le.py FD2.EXE funcof 0x26130   → 0x25ebb   (進戰場 call)
$ callgraph_le.py FD2.EXE funcof 0x1a251   → 0x19df7   (讀檔/過場子模組)
```

**2026-07-29 直接分支判讀：**
- `0x25f10` 是新遊戲分支的 pre-handler call，隨後設 BGM、清輸入並由
  `0x25f3a→0x2614c` 返回 0。
- `0x260f5` 是四槽讀檔分支的 pre-handler call，隨後由同函式返回。
- `0x26124` 是 `eax!=0 && eax!=1` 的獨立第三分支，才呼叫 `0x10010`。
- main 在 `0x25dbd` 呼叫 `0x25ebb`；回傳 0 時於 `0x25dce` 呼叫
  `0x117e7`。所以新遊戲的正確自動鏈是：

```
main 0x25bf4
  └ driver 0x25ebb
       ├ [0x53c03]=0                         ; 新遊戲歸零章節
       ├ call [0*4 + 0x51d71] = 0x3231b      ; 開場 cutscene(與前代主角對話)→ ret
       └ return 0
  └ call 0x117e7                             ; 戰鬥主迴圈
```

## 步驟 5 — 獨立驗證章節跳表(修了一個工具 bug)

第一次 `jtab 0x51d71` 回報 `raw 0x0`:**發現工具 bug** —— 跳表 0x51d71 在 **obj2 data 段(0x50000+)**,而 fixup 解析與讀取只涵蓋了 obj1 code 段。修正 `fixup_map` 改掃**全部 object 的 fixup pages**、`page_base_linear` 依 page 所屬 object 換算 linear 後:

```
跳表 A 0x51d71(章節→戰前/劇情):  [0]0x3231b [1]0x32d18 [2]0x32e8c [3]0x32fb2 [4]0x33049 …
跳表 B 0x51de9(章節→phase-2 戰後): [0]0x22ef6 [1]0x22f37 [2]0x230f2 [3]0x231bc [4]0x231f9 …
驗 [0]:0x32326 mov [0x53c03],0x20 ; call 0x205da   → 確為 cutscene
```

**比對:** 與 doc 23 §4/§5 中由 agent 給出的跳表內容**完全一致**——但這次是修好 data 段 fixup 後**獨立重現**,不是照搬。agent 的結論於此升級為「已自驗」。

## 步驟 6 — `[0x53ecc]` 戰後/事件狀態機完整追蹤

doc 23 把 `[0x53ecc]` 標為「戰鬥結果碼(1 事件、2 勝利),戰後狀態圖未追完」。本步追完。

> **2026-07-29 IDA 優先勘誤：**本節的控制流順序仍有效，但早期把碼 1
> 直接命名為「世界地圖／中場」、碼 2 直接命名為「勝利／章節結束」超出
> 直接證據。碼 1 的外層分支只證實固定呼叫 `0x22E5C`；該函式載入
> `FDOTHER.DAT` 資源 #79 並呈現，不讀章節索引。碼 2 只證實先走章節索引
> 戰後表，再進 `0x2CAD7`，回傳零時才走第二張章節表。以下高階舊名稱均由
> 這項 raw 邊界取代。

### 6.1 戰役迴圈完整分支(disasm 0x25d80–0x25ea0)

```
0x25db1  ┌─ next-battle 迴圈頭
0x25db5  │   call 0x25977            ; 場景/BGM
0x25dbd  │   call 0x25ebb            ; driver(載章節+cutscene+進戰場)
0x25dc6  │   test eax,eax; jne 0x25e88   ; driver 回傳非0 → quit
0x25dce  ├─ same-battle 迴圈頭
0x25dce  │   call 0x117e7            ; 戰場指令迴圈(打,逐單位行動)
0x25dd5  │   cmp [0x53ecc],1 ─ ==1 → call 0x22e5c(固定資源 #79 呈現)→ 清碼 → 0x25e74
0x25e02  │   cmp [0x53ecc],2 ─ ==2 → 停曲; call [章節*4+0x51de9](章節索引戰後表);
0x25e2a  │                          call 0x2cad7(raw gate); test eax
0x25e3a  │                          ├ 回傳0: call [章節*4+0x51d71]+ play_bgm
0x25e65  │                          └ [0x53ecc]=0; call 0x4e031(BIOS 鍵盤緩衝 word copy；清除效果為強推論)
0x25e74  │   test esi,esi; je 0x25dce   ; esi==0 → 續打同場
0x25e8f  └─ test edi,edi; je 0x25db1    ; edi==0 → 下一場;否則 0x25e97 cleanup→quit
```

### 6.2 `[0x53ecc]` 全部讀寫點(fixup xref + opcode 模式解析,41 處)

線性反組譯這些點會漂移(grep 無命中);改用 **LE fixup 列出所有觸及 0x53ecc 的位址,再以 opcode 模式從 ref 反推指令**(`C7 05`=mov imm32、`81 3D`/`83 3D`=cmp imm32/imm8、`A1`/`A3`=mov eax、`8B 05`/`89 05`=mov reg、`FF 35`=push):

| 動作 | 處數 | 位置 | 意義 |
|---|---|---|---|
| `mov [0x53ecc], 1` | **22** | 分散於 0x205be–0x20c64 的 default／章節 handlers | raw pending/result code 1；外層如何消費依 caller |
| `mov [0x53ecc], 2` | **6** | 同區 | raw pending/result code 2；含 `0x205be` 的預設值 |
| `mov [0x53ecc], 0` | 3 | 0x205ef、0x25df1、0x25e65 | 處理後清旗標 |
| `cmp [0x53ecc], n` | 9 | 0x25dd5/0x25e02(戰役迴圈)、0x1a4xx/0x1d8xx(讀==0) | 分派 / 檢查無 pending |
| `mov reg,[0x53ecc]` | 1 | 0x20c64 | 讀 |

### 6.3 結論:`[0x53ecc]` = 事件解譯器↔戰役迴圈的「pending 動作碼」

- **寫方**：章節戰場事件 handler 表中的多個獨立函式；不是
  `0x205c9–0x20c64` 單一大函式。
- **讀方**:**戰役迴圈**(0x25dd5/0x25e02)據碼分派、處理後清 0;過場/讀檔模組讀 ==0 確認無 pending。
- **碼義**：本層只證實 `0` = 無 pending；`1` 走固定 `0x22E5C`
  資源 #79 呈現；`2` 走章節索引戰後表與 `0x2CAD7` gate。各 writer 的
  玩家可見原因與結果必須依逐章 handler／原版路徑另證。
- **修正記憶**：舊稱「1=事件／世界地圖／中場、2=勝利／章節結束」已撤回；
  raw pending 碼及上述外層分支才是可跨文件沿用的語意。
- **[已解,見 doc 25]** ~~事件解譯器(0x205xx)入口無 prologue、caller 空~~ → doc 25 挖出真相:0x205xx 區**不是單一 byte-code 解譯器**,而是**第三張章節跳表 `0x51b19` 指向的「每章一個 C handler 函式」**(default 0x205b4 + 18 特殊 handler);dispatch 在戰場迴圈 `0x1197b: call [章節*4+0x51b19]`。22 個 `=1`/6 個 `=2` 分散在各章 handler,依該章特殊條件設定。用詞「事件腳本解譯器」應正名為**章節戰場事件 handler 表**。

## 與先前結論/記憶的比對總表(避免殘留錯誤)

| 項目 | 先前狀態 | 本輪裁決 |
|---|---|---|
| `0x10010` caller | doc 23 §7 標 **[阻]**(線性工具釘不死) | ✅ **已解**：`0x1a251`、`0x26130`；2026-07-29 更正其語意為 current-runtime snapshot loader |
| 0x1b051 / 0x26f30 是 caller | 某 agent 推測 | ❌ 偽命中,刪除 |
| cutscene→戰場是否經相位機 | doc 23 用「相位機接手」描述 | 不經相位機；pre-handler 由 `0x25ebb` 返回 0，main 再呼叫 `0x117e7`。舊「同 driver 線性落入 `0x10010`」也已撤回 |
| 章節跳表 0x51d71/0x51de9 內容 | agent 給出 | ✅ 獨立驗證一致 |
| main = 0x25bf4 | doc 23 已驗證 | ✅ main prologue 與 `0x25dbd→0x25dce` 控制流再確認 |
| `[0x53ecc]` 語意 | 上輪記「只管戰後分支 1事件/2勝利」 | ◐ 精化：章節 handler↔戰役迴圈的 pending/result 碼；`0x205be` 另以 raw roster predicate 產生 0/1/2，不能把所有 writer 的 1/2 都先命名成同一玩法事件 |
| 記憶層(fd2-* 記憶) | — | ✅ 無被推翻結論;本輪精化 [0x53ecc] 已回填 control-flow-anchors 記憶 |

## 步驟 6 方法附記:定位「具名全域變數所有讀寫點」

要找某全域變數(如 `[0x53ecc]`)的**所有**讀寫,別用線性 disasm(會漏、會漂移)。
正確錨:**LE fixup 表**——凡指令裡引用該變數絕對位址的 disp32,都會在 fixup 表登記一筆。
`disasm_le.py refs <abs>` 一次列全;再用 **opcode 模式**(見 6.2)從每個 ref 反推指令類型與立即數,
即可在不依賴線性對齊的情況下,把讀/寫/比較/常數值全部分類出來。這對「漂移嚴重的腳本/資料夾雜區」特別有效。

## 本輪受阻 / 待續(誠實標註)

- **[已解]** `0x25ebb` 的三個主選單回傳分支已逐條展開：新遊戲與四槽
  讀檔各自執行 pre-handler 後返回；第三分支才呼叫 `0x10010`。這次勘誤
  也確立方法限制：`funcof`／可達 caller 只能回答函式歸屬與可達性，不能
  取代條件分支的直接指令檢查。
- **狀態校正**：`[0x53ecc]==1` 的 caller 與 `0x22e5c` 已確認為固定
  資源 #79 呈現，但「章1專屬／世界地圖／中場」沒有章節讀取或同狀態
  執行期證據，故不再沿用。回合增援由
  `0x1a813`→`0x51b91`→spawn 原語消費。`[0x53ecc]==2` 的戰後表仍有
  各章 town/shop/preparation/ending 分支待逐列 E0/E2 核對，不能宣稱
  整個 campaign flow 已完成。
- **工具**:`callgraph_le.py` 的 `edges`/`path` 為近似版;間接呼叫(跳表)需手動以 `jtab` 解出再分析。

> 相關:doc 23(開場流程,本篇釘死其受阻項)· doc 12(BGM)· doc 19/21(重製對映)。工具:`tools/callgraph_le.py`、`tools/disasm_le.py`、`tools/le_xref.py`。
