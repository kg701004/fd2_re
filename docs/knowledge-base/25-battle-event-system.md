# 25 — 戰場事件系統:章節 handler 與事件原語(反組譯)

> doc 24 §6.3 留的受阻項:`[0x53ecc]=1/2` 的 28 個寫入點(0x205c9–0x20c64)各對應哪種事件、整個「事件指令集」長怎樣。本篇挖完。
> **核心結論(且修正 doc 24 用詞)**:FD2 的戰場事件**不是 byte-code opcode VM**,而是**「每章一個編譯進 EXE 的 C handler 函式」**,放進第三張章節跳表 `0x51b19`。該表由戰場主迴圈及逐單位掃描路徑反覆呼叫；handler 檢查條件後可寫 `[0x53ecc]` raw pending 碼。碼 1／2 的玩家可見名稱必須由逐章 caller 與外層路徑另證。
> 方法:call-graph(`callgraph_le.py`)+ fixup 跳表解析,全程比對既有結論(rulebook 62/63)。標 **[驗]/[推]/[阻]**。

## 1. 三張章節跳表(都以 `[0x53c03]` 章節索引)

挖事件系統時補齊了第三張跳表,與 doc 23 的兩張並列:

| 跳表 | linear | 用途 | dispatch 點(已驗證) |
|---|---|---|---|
| **戰場事件** | `0x51b19` | 多個戰場路徑呼叫，可改寫 `[0x53ecc]` | `0x1197b`，以及逐單位 `0x1d8a0/0x1d96c/0x1d9fc` |
| 戰前/劇情 | `0x51d71` | 進章節前的 cutscene / 戰場設置 | 0x25f10、0x260f5、0x25e3a |
| phase-2 戰後 | `0x51de9` | raw phase 2 後的章節處理器 | 0x25e23 |

> 同一跳表 `0x51b19` 也被過場/世界地圖模組參照(0x1a950、0x1d8a3、0x1d96f、0x1d9ff)——即**戰場與過場共用同一套章節事件 handler**。[驗]

## 2. 為何是「handler 函式表」而非 byte-code

`0x1197b` 的 dispatch 用 **`[0x53c03]`(章節)** 當索引,不是讀腳本資料的 opcode。
跳表 30 個 entry 全部指向 code 段的函式入口(0x205b4–0x20bf5),不是資料偏移。
→ 漢堂沒做資料驅動的腳本 VM;**每一關的特殊事件邏輯,是工程師逐關手寫成 C 函式編進 EXE**。這是 1995 年常見做法(省去寫 VM + 編輯器的成本),代價是「改事件 = 改程式重編」。[驗]

## 3. `0x51b19` 全 30 章 handler 對映 [驗]

```
章: 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
hdl:D  a  D  D  D  D  D  D  D  b  D  c  d  D  e  f  g  h  i  j  k  L  m  D  n  o  L  L  p  q
```
- **D = default `0x205b4`**（11章：0,2,3,4,5,6,7,8,10,13,23）——
  落入共用 raw 三值結果規則；玩家可見勝敗名稱須由逐關與外層路徑驗證。
- 特殊 handler 18 個相異:a=0x206c5(章1)、b=0x20707(章9)、c=0x2073d、d=0x20765、e=0x20822、f=0x2084a、g=0x20872、h=0x208cf、i=0x20926、j=0x20957、k=0x20a51、**L=0x20a87(章21/26/27 共用)**、m=0x20aaf、n=0x20b14、o=0x20b3c、p=0x20b72、q=0x20bf5。

### 3.1 章27(`0x51b19[26]=0x20a87`)完整解碼:沒有隊長專屬計數器,真正勝利條件是「場上目前存在的敵方單位全滅」[驗]

> 任務背景:doc58「續五十九～續六十一」多輪 live 測試 ch27(玩家可見章節,對應本表 0-indexed 位置26)
> 「擊毀3隻機甲隊長」目標，續六十一直接把3隻隊長的record同步寫入死亡signature
> (`+5:0x00→0x01`、`+0x40`歸零)，戰況總覽`ENEMY`計數確實47→44，但勝利判定沒有觸發。
> 本節純靜態 Ghidra headless(`FD2Analysis3`，`-readOnly -noanalysis`)反組譯 `0x20a87`
> 本體，回答「勝利判定到底在檢查什麼」。

**位址鏈驗證**(三條獨立管道互相印證，非單一來源):
1. 直接讀 `0x51b19` 跳表原始 bytes(`bytes` action，不經反組譯)：offset `0x51b19+26*4`=`0x51b81`，
   4-byte little-endian值為`87 0a 02 00`=`0x20a87`。
2. `docs/data/battle_events.json` 條目 `{"chapter":26,"handler":"0x20a87",...}` 完全吻合。
3. 本篇 §3 既有(2026-08-20之前)dump 的「L=0x20a87(章21/26/27共用)」列表位置26同樣是`0x20a87`——
   三者互證，且與 doc58「ch24⇔`0x51b19[23]`」的既有換算規則(`table_idx = 玩家章節-1`)一致：
   位置26對應**玩家可見的ch27**，位置21/27則分別是ch22/ch28(共用同一支handler，本節不展開)。

**`0x20a87` 完整反組譯**(僅10條指令，函式本體極短，`FD2Analysis3`未將其登記為函式起點，
以`disasm` action從`0x20a87`線性反組譯到`RET`一次拿到全貌):

```asm
0x20a87  PUSH 0x8
0x20a8c  CALL 0x3702f        ; 標準 stack frame prologue(全EXE共用)
0x20a91  CALL 0x205be        ; ★呼叫§4已記錄的共用「三值結果規則」原語(見下)
0x20a96  PUSH 0x1
0x20a98  CALL 0x34894        ; NativeRecordByte5Bit0(1)：record[1].+5 & 1
0x20a9d  ADD  ESP,0x4
0x20aa0  TEST EAX,EAX
0x20aa2  JZ   0x20aae        ; record[1] 存活(bit0==0)則跳過
0x20aa4  MOV  [0x53ecc],0x1  ; record[1] 已死(bit0==1)→ 強制覆寫成 code1
0x20aae  RET
```

`0x34894`完整反組譯只有一行(`FUN_00034894(int idx){ return record[idx].+5 & 1; }`)，
與§4已登記的`0x3453e`是同一語意的另一個獨立呼叫殼(讀同一個bit)。**`idx=1`是硬編碼常數**，
對照攻略「敗北條件:索爾死亡/悠妮死亡」與本專案既有的「record0=索爾」慣例，`idx=1`極可能
就是悠妮的固定record槽位——**但這個身份對應本節未獨立核實角色名稱**，只確認了「check record[1]
的死亡bit，死亡則強制`[0x53ecc]=1`」這個行為本身。

**`0x205be`的邏輯**(§4已記錄，本節額外用`disasm`重新核對開頭6條指令逐位元組吻合，
無新矛盾)：

```asm
0x205be  PUSH 0x8 / CALL 0x3702f          ; prologue
0x205c9  MOV [0x53ecc], 0x2               ; ★基準值:先假設「已勝利」
0x205d3  XOR EDX,EDX                       ; loop index = 0
0x205d5  JMP <迴圈條件>
  迴圈本體(§4既有描述，未重新逐行反組譯，僅核對前6條指令的prologue與基準值寫入)：
  for (edx = 0; edx < [0x53beb]; edx++) {
    record = [0x53a45] + edx*0x50;
    if (record.+6 == 0 /*敵方陣營*/ && (record.+5 & 1) == 0 /*存活*/) {
      [0x53ecc] = 0;   // 還有敵人活著→戰鬥繼續，跳出/不再往下判斷
      break;
    }
  }
  if ((record0.+5 & 1) != 0 /*record0=索爾已死*/) [0x53ecc] = 1;  // 覆寫成code1
```

**結論(高信心，三條獨立管道互證)**：ch27 的 `0x51b19[26]=0x20a87` **完全沒有任何依
class-id(如任務假設的`0x74`機甲隊長)或per-scenario「目標單位清單」做判斷的分支**——它就是
`0x205be`這個全EXE共用的「掃描目前存活的全部敵方record，任一還活著就不算贏，全部死光才維持
基準值2(勝利)」通用邏輯，唯一在`0x205be`之上疊加的，是ch27自己額外多檢查的`record[1]`
(疑似悠妮)死亡覆寫。**真正的勝利觸發條件因此是「當下已在場上的全部敵方單位(`record.+6==0`，
掃描範圍`0..[0x53beb]`——這包含全部已出現的機甲隊長／守衛／突擊兵／兵／射手／光束砲座，以及
已觸發的每一波增援，不只是3隻隊長)同時滿足`+5 bit0==1`(死亡)」**，不存在單獨的「隊長擊殺計數器
達到3」這種機制。攻略文字「勝利條件:擊毀機甲隊長」應理解成**戰術/敘事層面的目標指引**(隊長可能是
戰場上最強力、最需要優先解決的威脅，或擊殺2/3隊長會觸發攻略記載的「增援立即出現」)，不是這個
handler 實際檢查的字面條件。

這也**完整解釋了續六十一的負面結果**：只把3隻(或本輪額外1隻，共4隻)敵方record寫成死亡signature，
战場上仍有43隻其他敵方record維持`+6==0 && bit0==0`(存活)，`0x205be`的迴圈必定在掃到其中任一筆
時就把`[0x53ecc]`寫回0並跳出——不論死掉的是不是隊長、不論死了幾隻，只要陣列裡還有**任何**一筆
存活的敵方record，這個判定永遠不會維持基準值2。「戰況總覽的`ENEMY`計數47→44」與「這裡的勝利
判定」讀的是同一份底層record陣列，但走的是兩條完全獨立的消費邏輯(UI計數 vs. handler win-check)，
所以計數會反映寫入、判定卻不會被觸發，兩者並不矛盾。

**對「單一捷徑寫入」問題的直接回答**：
- **(a) 不存在只寫3隻隊長就能觸發勝利的捷徑**——這在架構上已被本節排除,不只是續六十一那次測試
  湊巧失敗。
- **(b) 存在一個結構性、但工程量遠大於「3筆寫入」的替代捷徑**：若要繞開真實攻擊鏈，理論上可以
  用 debugger 一次性把`0..[0x53beb]`範圍內**所有**`record.+6==0`的敵方record都寫入死亡signature
  (`+5 |= 1`)，同時確保`record0`(索爾)與`record1`(疑似悠妮)維持`+5 bit0==0`(存活)，再觸發任一
  已知呼叫`0x51b19[26]`的路徑(`0x1197b`或逐單位掃描`0x1d8a0/0x1d96c/0x1d9fc`，見§1表格，本節未
  展開這幾個 caller 實際的觸發時機)。這個捷徑**未經 live 測試驗證**，只是本節反組譯得出的理論
  推導；比續六十一的「3筆寫入」多出約40+筆額外寫入，工程量與真人打完全場相比是否划算，留給
  下一輪 live 測試自行評估。
- **(c) 若目標仍是真正走完攻擊鏈**：本節排除了「有捷徑」這個希望，代表下一輪應該回到續六十§6
  建議1(索爾回合排除→完整 End Turn 重置)的真實UI流程，接受「必須真的殺光全部47+隻敵人」這個
  事實，不必再猜測隊長相關的捷徑寫入組合。

**誠實信心分級**：
- **高信心**：`0x51b19[26]=0x20a87`的位址鏈(三條獨立管道)、`0x20a87`本體10條指令的逐位元組反組譯、
  `0x205be`基準值寫入與loop prologue的重新核對——這幾項都有直接反組譯位元組佐證。
- **中信心**：`0x205be`迴圈本體與record0覆寫段落沿用§4既有記錄(本節未重新逐行反組譯迴圈內部，
  只核對了開頭6條指令)；`record[1]=悠妮`的角色身份對應是推論，未獨立核實。
- **未驗證**：`0x51b19[26]`(即`0x20a87`)在一場真實戰鬥中實際被呼叫的頻率/時機(是每次死亡後、
  每回合、還是其他觸發點)，本節只反組譯了 handler 本體，未追查§1列出的幾個 caller(`0x1197b`／
  `0x1d8a0`／`0x1d96c`／`0x1d9fc`)各自何時被呼叫；(b)項捷徑的可行性最終仍需一次 live 測試確認。

> **2026-08-24 同日 live 驗證更新(doc58 續六十二)**：(b)項捷徑**已 live 測試成立**——把
> ch27 全部47格敵方record(`slot16..62`，`0x26DF88+k*0x50`)一次寫入死亡signature(`+5=0x01`)，
> 維持`record0`(索爾)存活，再透過真實UI「移到空地格→開系統選單環→END→確認YES結束本回合」
> 這個具體操作路徑觸發，**成功進入真正的postbattle勝利轉場**(13人隊伍集合場景→CG過場→
> 結局詩句文字→逐角色回顧卡)。同時補上「未驗證」的觸發時機證據：**純被動輪詢(idle等待
> +游標移動+開關選單，未做End Turn確認)全程未觸發**，代表`0x205be`不是每畫面/每次互動被動
> 檢查，而是綁定在「End Turn確認YES」這個具體UI操作路徑上(嚴格說是行為證據，非直接在
> `0x205be`本體斷點命中坐實——下一輪若要100%釘死，應在確認YES前對`0x1C05BE`
> [native`0x205be`+`0x19C000`]重新下斷點)。詳細操作序列、截圖、與doc35§9結局montage
> renderer的後續發現見doc58續六十二。

## 4. 事件原語(handler 共用的條件 / 動作函式)

把 18 個 handler 呼叫的函式統計出來,扣掉 stack-probe(0x36cd7),得到事件系統的「指令集」——雖是函式呼叫形式:

| 原語 | linear | 次數 | 作用 | 狀態 |
|---|---|---|---|---|
| **查單位 raw bit** | `0x3453e` | 36 | `NativeRecordByte5Bit0(idx)`：`[0x53a45] + idx*0x50 + 5` 的 `&1`；高階語意必須由 caller branch 證明 | [驗] |
| **共用三值結果規則** | `0x205be` | 13 個直接 caller；default table 另可由 `0x205b4` 進入 | 先寫 code2；任一 `raw +6==0 && (+5&1)==0` 列存在則寫 code0；最後 `record0 +5 bit0` 可覆寫 code1 | [驗] |
| **戰場重設／章節載入** | `0x205da` | 28 個直接 caller | 清 `[0x51a83]/[0x53ecc]`、呼 `0x1088d([0x53c03])`，再重設戰場全域 | [驗]；與 `0x205be` 是不同入口 |
| **繪事件畫面** | `0x15f84` | 6 | 全螢幕圖繪製(過場 / 事件畫面) | [驗] |
| 我方名冊查詢 | `0x33499(id)` | 1(章16) | `roster_has(id)`:查我方名冊 `[0x53bf7]`(32槽×0x50B)byte[+8]==id | [驗] |

> **更正(doc 26 補完，範圍限定)**:早先把各章 ×1 的 `0x33499` 等列為「增援/對話動作」；在
> `battle_events.json` battle-event skeleton 的匯出範圍內，`0x33499` 是條件查詢(roster_has)，
> 其餘記錄只保存控制流／設碼／繪圖。這不能外推到 postbattle/cutscene handlers；ch14/ch15
> post 已證實含 dialog、acting、sync、JOIN 等動作，必須按 caller CFG 保存。

關鍵狀態變數:
- **`[0x53a45]`** = 戰場單位陣列基底(每單位 0x50 byte;doc 23)。事件條件多半在查它。[驗]
- **`[0x53bef]`** = **回合數**(戰場開始=1、`inc`、handler `cmp N`)→ 「第 N 回合觸發」類事件。[驗](doc 26)
- **`[0x53ec8]`** = 累積計數(`add reg`+每 tick `clamp` 99,0x11959;非回合數)→ 語意待定。[推]
- **`[0x53ecc]`** = raw pending 輸出碼；0 表示掃描繼續，1／2 由外層
  不同分支消費，不在 handler 層命名中場或勝利。[驗]

## 5. 實例:章 1 handler `0x206c5` [驗]

```
0x206d0  call 0x205be             ; 共用 raw 三值結果規則；不載入章節
0x206d5  edx = 5                   ; 迴圈單位 5..10
0x206dd  cmp edx,0xb; jge 0x206fb
0x206ed  eax=[0x53a45]            ; 單位陣列
0x206f2  test byte[ebx+eax+5],1    ; 查單位 #edx 狀態 bit0
0x206f7  je 0x20705                ; 有一個不滿足 → 跳出
0x206f9  (續迴圈)
0x206fb  mov [0x53ecc],1           ;★ 單位 5..10 全滿足 → 觸發中途事件
0x20718  push 0x32; call 0x3453e   ; 另查單位 #0x32(50)狀態
0x2073...  push 0x33; call 0x3453e ; 查單位 #0x33(51)
```
即:**章 1 的腳本邏輯 = 「若單位 5–10 的 raw bit0 全部為 1→ 觸發劇情事件;再依單位 50/51 的 raw predicate 分支」**。
這就是一條「事件指令」的真身——一段檢查單位狀態的硬編碼條件 + 設 `[0x53ecc]`。

> 單位 byte(+5) 的 bit0／bit7 目前只作 raw mask；constructor、HP writer、`0x32975` 的寫入點不能自動推出所有 caller 的高階欄位語意。先前依「初始化=1」與使用者記憶寫成「bit0=存活」的說法已撤回。回合數 `[0x53bef]` 的 increment 已觀察，但 team-completion／換邊語意仍待完整 state-machine caller。

## 6. 完整事件流(串起 doc 23/24/25)

```
戰場迴圈 0x117e7
  ├ 跑戰鬥(行動 0x18890…)
  ├ [0x53bef] 回合數(開始=1,回合切換 inc,inc 點 0x1a5b9);[0x53ec8] 累積計數 clamp 99
  ├ call [章節*4+0x51b19]           ; 章節戰場事件 handler(勝負判定,見上)
  └ call 0x1a813(camp_filter)       ; ★turn_events 消費點(見 §6.1),3 處呼叫點各帶 camp=1/0/2
       └ default 0x205b4/0x205be → raw 三值結果：
          camp0 活躍列存在→0；record0 bit0→1；其餘→2
              │
戰役迴圈(doc 24 §6)讀 [0x53ecc]
  ├ ==1 → 固定 0x22e5c 資源 #79 呈現 → 清0
  └ ==2 → 章節索引戰後表 0x51de9 → 0x2cad7 gate → 回傳0才走 0x51d71
```

## 6.1 turn_events.event_id → group 消費機制(已解,取代先前 [阻] 的 `0x22e5c` 猜測)

> **修正**:§8 先前把 `0x22e5c` 列為「turn_events 消費點,待解」。call-graph 驗證(`callgraph_le.py callers 0x22e5c`)
> 顯示它唯一 caller 是 `0x25de5`（戰役主迴圈在 `[0x53ecc]==1` 時呼叫），
> 且函式體載入固定的 `FDOTHER.DAT` 資源 #79、做兩次呈現，不觸碰
> FDFIELD 控制段或章節索引。這證明它與 turn_events 資料無關；但舊稱
> 「第1章專屬中場」沒有同狀態執行期證據，已撤回。真正的 turn_events
> 消費點是下面的 `0x1a813`。[驗]

**呼叫鏈(3 處呼叫點,camp 過濾)**:

| 呼叫點 | camp 參數 | 時機 |
|---|---|---|
| `0x1a4c7` | raw camp1 | 玩家控制段之前的 camp1 檢查點 |
| `0x1a554` | raw camp0 | 敵軍 AI `0x1a58f→0x1d8ba` 之前 |
| `0x1a78d` | raw camp2 | 同一世界地圖／戰場迴圈的另一檢查點 |

**`0x1a813(camp_filter)`**(turn_events 掃描迴圈):

```
0x01a813  ...
0x01a828  cmp ebx, 0x10            ; 迴圈 16 筆(FDFIELD turn_events[16])
0x01a831  mov ecx, [0x53a55]       ; ecx = FDFIELD 控制段 runtime 基底
0x01a83e  add eax, ecx             ; eax = ecx + i*3        (3B/筆,對齊 parse_field.py)
0x01a840  movzx edx, byte[eax+3]   ; edx = turn_events[i].turn   (ecx+3=跳過3B header)
0x01a844  cmp edx, [0x53bef]       ; == 目前回合數?
0x01a84a  jne next
0x01a84c  movzx edx, byte[eax+5]   ; edx = turn_events[i].camp
0x01a850  cmp edx, esi             ; == camp_filter(呼叫端傳入)?
0x01a852  jne next
0x01a854  movzx eax, byte[eax+4]   ; eax = turn_events[i].event_id ★
0x01a858  push 0
0x01a85a  call [eax*4 + 0x51b91]   ; ★★★ event_id → handler 跳表
```

即:`turn==目前回合` 且 `camp==呼叫端 filter` 的記錄,取其 `event_id`,呼叫 `[event_id*4+0x51b91]`。
`0x51b91` 是**與 §1 的 `0x51b19`(章節×30)不同的另一張跳表**。
舊版因 FDFIELD `turn_events.event_id` 只出現 0..57，誤把全表截成 58 項；
重定位資料實際連續到 `0x51cf5`，共 **90 entries（event_id 0..89）**，
下一筆 `0x51cf9` 已是其他資料。[驗]

0..57 的 handler 為 `0x341db..0x354dd`，是目前 FDFIELD 回合事件使用的
子集合；58..89 為 `0x354fe..0x360f8`，另有玩家操作、格子互動、單位行動
等通用 dispatcher 參照同一張表。例：event 82 的 table slot 是
`0x51b91 + 82*4 = 0x51cd9`，指向 `0x35f92`。因此「回合增援事件只用
0..57」可以保留，但「全域跳表只有 58 項」是錯誤斷言。

**event_id handler 內部(同 §2 結論:仍是硬編碼函式,非 byte-code)**:handler 呼叫兩個 spawn 原語:

| 原語 | linear | 作用 |
|---|---|---|
| `spawn_group(group_id)` | `0x10b4e` | 掃 FDFIELD 控制段 units 陣列(`[0x53a55]+0x83 + k*0x1a`,stride 26B=FDFIELD 單位記錄大小,欄位 `+0x15`=b21=group)找 `unit.group==group_id` 者啟用(offset `0x83`=3+48+32+48,正好是 header+turn_events+保留+chests,對齊 `parse_field.py` 的 units 起點)。[驗] |
| `spawn_group_with_intro(group_id)` | `0x32999` | 載入 FDOTHER #95/#9，保存工作畫面與舊單位數，內部呼叫 `0x10B4E(group_id)`，再以 #9 的 12 個 `LMI1` 項目做固定 12 次索引合成／呈現。`0x1366A` 是 wrapper 返回後由四個呼叫端另行執行，不在本函式內。[驗] |

`row+5` 在直接指令中只證實是供三個 caller 比對的 raw camp byte；不能僅依
0／1／2 把它提升成 enemy／ally／special 陣營名稱。尤其 `0x1A554` 明確在
敵軍 AI 前，舊稱「敵方 AI 回合結束後」已撤回。

`group_id` 引數**通常是 handler 裡的字面常數**(如 event_id0 呼叫 `push 3;call 0x10b4e` 和 `push 7;call 0x10b4e` → 兩個 group);
少數 handler(event_id 27/54/57)用**動態值 `[0x53bef]`(目前回合數本身)當 group_id**——對應 `turn_events.json` 中同一
`event_id` 在連續多回合重複出現(如 map7/章8 的 event_id27 於 turn 2-7 各出現一次):每回合觸發同一 handler,
但 group_id=當下回合數,達成「每回合多放一波、group 編號＝回合數」的遞增增援。[驗]

`[0x53bef]` 的新戰鬥初始寫入端是共用初始化函式 `sub_205DA` 內的
`0x2066e: mov dword [0x53bef],1`；29個章節開場呼叫者共用它，Capstone 亦獨立
重生出相同指令。CONTINUE 另從目前快照恢復即時值，不可重設為1。完整輸入雜湊、
位址空間與證據等級見
[`fd2_battle_round_seed_ida.txt`](../data/fd2_battle_round_seed_ida.txt)。[驗]

**工具**:`tools/extract_event_id_groups.py` 走訪 90 個 handler 自身的 basic-block 鏈(call 過站不進入、遇 ret 停止,
避免線性 sweep 漂移），擷取 `push <group_id>; call spawn_group[_with_intro]`；
2026-08-02 起也辨識 `0x35822` 的來源 `PUSH (group,y,x)` 與 event63 的共用
tail-call。staging metadata 保留 helper／spawn source／座標；event63 已由
獨立 raw camp0／敵軍 AI 前 runner 消費，其他 staging event 在各自 phase、
palette 與 redraw owner 閉合前仍不能降成一般 `spawn_group`。輸出
`docs/data/event_id_groups.json` 並附固定 FD2.EXE 雜湊與位址空間。
輸出同時保存 FDFIELD 未直接引用的 58..89，避免再把全域事件表誤當成
turn-events-only 表。無 spawn 呼叫只能證明該 handler 未呼叫兩個已知
spawn 原語，不足以命名成純對話、人工智慧或目標判定。[驗]

2026-08-01 的 runtime bridge 將45筆可解析 schedule 降階為46個可編輯
`spawn_group` action（event 0 的兩次 call 分開保留），每個 action 都帶
`native_event_id`，每次 call 都帶 source、via 與 `raw_placement_gate`。
這關閉的是事件來源與配置前綴；`spawn_group_with_intro` 的 acting／reveal／
present 尚未接入 turn-event action runner，不能只因單位已出現在正確座標就
宣稱整個 wrapper 已還原。[部分驗]

### 6.2 格子事件 selector：`0x13A44` 與控制段 16×2 表 [驗]

`0x13A44(x,y,selector)` 先由 `0x12E38` 讀取該格的地圖構成資料。地圖格
第二個 word 的低 5 位不是直接的 event_id，而是 **1-based 槽號**：
零表示沒有槽，1..16 對應控制段 `+0x33` 起的 16 筆兩位元組列。
每列第一 byte 是全域 event_id，第二 byte 必須等於呼叫端 selector；
event_id `0xFF` 或 selector 不符時不寫入 `[0x51A8F]`。

同一個低 5 位欄位也可表示寶箱，所以還有一層必要 gate：FDSHAP 對應 tile
的地形控制 byte0 若含 `0x20` 或 `0x40`，便走寶箱／隱藏物品路徑；
兩 bit 皆零才可當作格子事件槽。這也把 FDFIELD 控制段的舊
「保留 16×2 bytes」斷言更正為可編輯的格子事件表。

`tools/sync_native_field_events.py` 從固定雜湊的 FDFIELD／FDSHAP 原始資源
重建 33 張地圖的 `native_field_event_slots` 與 `native_field_events`。
`battle.NativeFieldEventIDAt` 保存邊界及 selector 比對，但尚未把未知
handler 接到正式戰鬥流程；資料缺失、越界或不符時一律失敗即關閉。

全圖掃描亦提供否定證據：event 82 沒有出現在任何格子事件列，因此
`0x35F92` 的一般玩家觸發不能命名成踩格事件。格子實際引用的 58 以上
event_id 為 59、60、61、62、65、69、75、80、84；另有 `0xFF` 空列，
不可當作 handler。[驗]

### 6.3 三位元組後處理列與特殊寶物事件 [驗]

`0x1AA1D` 以 `base+3*i` 讀 `{kind:u8,payload:u16le}`。kind 0 是物品、
kind 1 是金錢、kind 2 以 payload 索引 `0x51B91` 全域事件表；kind 3
走另一條呈現分支。`0x190AC` 對 FDFIELD 寶物控制列採相同三位元組契約：
type 0／1 分別給物品／金錢，其餘型態直接 dispatch payload，不能再把
所有非 1 型態都解析成物品。

`0x1B653/0x1B6B7` 只把符合 raw record gate 的 runtime `+0x31..+0x33`
複製成這種列。建構器 `0x10FA8..0x10FB2` 的來源是 FDFIELD
`b22` 與 `b23..b24` 的 16 位元 word；`b25` 未被這段複製。舊解析器把
`b23..b25` 合成 24 位元 payload 的斷言已撤回。

全 33 圖的靜態來源稽核目前找不到 event 82：turn-events、格子事件、
特殊寶物列、單位 `b22..b24` 效果列均沒有 payload 82；四個已知
handler 內硬編碼給 `0x1AA1D` 的單列亦全為 kind 0
（`00 D3 00`、`00 D5 00`、`00 65 00`、`00 0B 00`）。
這把 event 82 收窄成「目前無已知資料生產端」，但在所有 runtime writer
閉合前仍不宣稱程式碼不可達。

#### 2026-08-19 補記：runtime `+0x31..+0x33` 全 EXE writer 稽核（回應 worklist RE-EVENT82-REACHABILITY）[驗]

方法：不依賴既有 handler 清單，改用 Ghidra headless 對 `FD2.EXE` 全部
`.image`（code）段做指令層級掃描——遍歷目前資料庫內已定義的**全部
57,953 條指令、976 個函式**（與既有「976-fn 全量 Ghidra decompile」的
函式總數一致，確認此專案沒有大片未反組譯的程式碼區），對每條指令的
運算元做 `OperandType.isDynamic` 判定 + `getOpObjects` 掃描，找出「目的
運算元是暫存器相對記憶體、且位移常數恰為 `0x31`／`0x32`／`0x33`」的寫入
指令。全 EXE 只命中 **7 條**：

| 位址 | 所在函式 | 指令 | 分類 |
|---|---|---|---|
| `0x10AB1` | `0x1088D`（persistent party ctor，寫 `[0x53bf7]` 我方名冊陣列） | `MOV byte [EBX+0x31],0xFF` | 舊有已記錄：常數 sentinel |
| `0x10FAB` | `0x10C50`（FDFIELD battle-array ctor，寫 `[0x53a45]` 戰場單位陣列） | `MOV byte [EDX+0x31],AL` | 舊有已記錄：FDFIELD row `b22` 直拷 |
| `0x10FB2` | `0x10C50` | `MOV word [EDX+0x32],AX` | 舊有已記錄：FDFIELD row `b23..b24` 直拷 |
| `0x113D1` | **`0x112A5`（新找到）** | `MOV byte [ESI+0x31],0xFF` | 新 writer：常數 sentinel |
| `0x13CE6` | **`0x13A9F`（新找到）** | `MOV byte [EBX+0x31],AL` | 新 writer：table-driven，但有 gate |
| `0x13CEC` | `0x13A9F` | `MOV word [EBX+0x32],AX` | 新 writer：與上列同一 gate |
| `0x3FA6F` | `0x3F950` | `MOV word [EAX+0x32],CX` | 偽陽性：不同結構體 |

逐一反組譯／反編譯確認：

1. **`0x112A5`**（4 個呼叫端 `0x327F7/0x32801/0x3280B/0x32815`）：這是**先前未記錄的第三個 unit-record constructor**，寫入對象是
   `DAT_00053bf7 + DAT_00053bfb*0x50`——即我方名冊陣列 `[0x53bf7]`（32
   槽），不是戰場單位陣列 `[0x53a45]`。屬於「新增角色進名冊」的初始化
   函式（很可能是招募流程）。`+0x31` 寫入的是**字面常數 `0xFF`**，與
   `0x1088D` 對 `[0x53a45]` 記錄做的事完全平行，只是作用在名冊陣列上。
   常數寫入不可能產生 kind=2/payload=82，此 writer 排除。

2. **`0x13A9F`**（3 個呼叫端 `0x1D876`、`0x1D942`、`0x1D9D2`）：這正是
   doc26 單位結構表已標注「`+0x34` low nibble 的 dispatch 已閉合」的那個
   dispatcher 本體（`bVar4 = *(iVar5+0x34) & 0xF`）；先前只記錄了 dispatch
   本身已閉合，未把它的 `case 5` 分支交叉核對進本節的 event82 producer
   清單，這是本次補的空缺。`case 5`（欄位互動型態 5，行為近似寶箱：
   `bVar4==0` 時呼叫 `0x1BB8C(unit,item)` 給物品，語意與 doc §6.3 已知
   的 item/money kind 一致）從 `DAT_00053a55[uVar7*3 + 0x53 / +0x54]`
   讀出一組 `{kind:u8, payload:u16le}`，但反編譯清楚顯示複製動作被
   **`if (bVar4 < 2)` 硬 gate**：

   ```c
   bVar4 = *(byte *)(iVar5 + 0x53);
   uVar3 = *(undefined2 *)(iVar5 + 0x54);
   if (bVar4 < 2) {
     pcVar6[0x31] = bVar4;
     *(undefined2 *)(pcVar6 + 0x32) = uVar3;
     if (bVar4 == 0) { FUN_0001bb8c(); }
   }
   ```

   即只有 `kind∈{0,1}`（物品／金錢）才會被複製進 `+0x31..+0x33`；
   `kind==2`（event）在讀出後直接被 gate 擋掉，**不論來源表
   `DAT_00053a55` 裡實際存了什麼值都不影響這個結論**——這條 writer
   在結構上就不可能寫出 kind=2/payload=82，因此不必再額外稽核
   `DAT_00053a55` 這張表的 33 圖資料內容。

3. **`0x3F950`**：反編譯後是聲音／驅動程式初始化函式（字串常數
   `"Insufficient memory for driver descriptor"`、`"Out of driver
   handles"`、`"Out of timer handles"`），`+0x32` 寫入對象是驅動描述子
   結構 `*(iVar1+0xc)+0x32`（存 driver handle index），與戰場單位陣列
   完全無關，只是巧合共用同一個位移常數。判定為**偽陽性**，排除。

**結論**：全 EXE 976 個函式、57,953 條已定義指令中，寫入位移
`+0x31/+0x32/+0x33` 的指令只有 7 條；扣除 1 條偽陽性（不同結構體）後，
4 條是 unit-record 的真實 writer——2 條（`0x10AB1`／`0x113D1`）是寫常數
`0xFF` 的 sentinel，2 條（`0x13CE6`／`0x13CEC`）雖是 table-driven 但被
`kind<2` gate 擋死，2 條（`0x10FAB`／`0x10FB2`）是舊有已知的 FDFIELD
`b22..b24` 直拷（已由 33 圖靜態資料稽核排除 payload 82）。**已知 writer
全部封閉，沒有任何一條能寫出 kind=2/payload=82**——這把「無已知
producer」進一步坐實成「已窮盡全 EXE 指令層級 writer 稽核、仍無 event82
producer」。

**殘留不確定性（誠實記錄，未完全排除）**：
- 本次掃描比對的是「立即值位移 = 0x31/0x32/0x33」的固定運算元，
  抓不到位移完全由暫存器動態算出（例如 `MOV [EBX+ECX],AL` 而 `ECX`
  執行期算出 0x31）的寫入。目前 codebase 對這顆結構體其餘欄位
  （doc26 單位結構表 +0/+1…+0x4E 全部條目）一致採「固定位移 MOV」慣用法，
  沒有觀察到用 `REP MOVSB`/動態位移對這顆結構體做欄位複製的先例，
  但不能證明 100% 沒有這種寫法存在。
- 掃描範圍是目前 Ghidra 資料庫已定義為「指令」的位址集合；函式總數
  （976）與既有全量 decompile 記錄一致，可信已窮盡目前已知的程式碼區，
  但無法對「從未被任何已知路徑到達、Ghidra 從未自動反組譯出來、
  仍是 raw bytes」的區塊做出保證——這類區塊若存在，本掃描不會看到。

Worklist `91-worklist.md` 第 215 行 **RE-EVENT82-REACHABILITY**：以上即
本行「仍須稽核 runtime +0x31..+0x33 的其他 writer」的完整回應。全 EXE
writer 已窮盡列舉並逐一分類，未發現新的 event82 producer；上述兩點
殘留不確定性均為結構性極低機率的邊界情況，不影響「目前已知 writer
均不可達 payload82」的結論，但按規範不升級為「證實死碼」的滿分結論，
維持「已窮盡已知 writer 稽核、無新 producer、僅剩結構性邊界不確定性」
的狀態。

#### event 58：map25 五選一寶物 [驗-邏輯]/[更正-位址]（2026-08-24 更新，見 doc25 §11.7）

> **位址更正**：本節原標「handler `0x354FE`」，2026-08-24 re-verify（§11.7）用兩條獨立管道
> （跳表原始 bytes 逐 byte 讀值 + 指令邊界回溯）確認 `0x354FE` 是 `0x51b91` 跳表 event_id=58
> 槽位**真實、非誤讀**的登記值，但這個位址**落在 event57 handler(`0x354dd`)自己的
> `PUSH 0xcd` 立即值中段**，不含下述任何內容，也不是通往下述內容的路徑；下述 `0x1B8A6`/
> `0x5274E`/`0x1BB8C`/FDTXT`0x1E0` 邏輯改實際位於 `0x35854`（見 §11.7.5），且該函式
> **目前查無任何已知靜態呼叫者**（`xref_to`/`call_scan` 均 0 命中，含 `[58*4+0x51b91]`
> 本身）。**因此「map25 `{type:2,value:58}` 寶物 slot 在原版 runtime 究竟怎麼呼到這段
> 程式碼」目前是未解問題**——邏輯描述本身（以下）保持 [驗]，但「入口位址 `0x354FE`」與
> 「透過全域 event_id 58 dispatch 觸發」兩個歸因已撤回，留待後續專門稽核找出真正的呼叫路徑。

map25 的寶物 slots 0..4 都是 `{type:2,value:58}`。~~handler `0x354FE`~~（位址已撤回，
見上）先以 `0x1B8A6` 檢查行動單位的八格 raw inventory；等於 8 時只顯示
FDTXT_000 `0x1E0` 並返回，不改任何 opened state。仍有空格時，
`0x12E38` 取目前寶物 slot，以 slot 索引 EXE `0x5274E` 的五 bytes：

`[0x1D,0x2B,0x33,0x3D,0x47]`

接著 `0x1BB8C(unit,item)` 寫入物品，最後把 battle-local
`[0x53AD5]+0..4` 全設為 1，而不是只關閉當前寶箱。因此五個位置只能
選一個，取得哪件物品由位置 slot 決定。[驗]（邏輯本體；入口與觸發路徑見上方更正）

`native_treasure_event_rules.json` 以 FD2.EXE 雜湊、handler/table 位址保存
這條規則；map25 editable asset 引用 event58 rule。重製成功取得後同步標記
slots0..4 opened，滿欄則不改 inventory/opened。其他尚未 lower 的 event
寶物仍保持失敗即關閉。**注意**：`native_treasure_event_rules.json` 內若儲存了
`0x354FE` 當 handler 位址，該欄位已知有誤，應視為指向邏輯本體 `0x35854`（呼叫路徑仍待考證），
供後續資料稽核時比對。

### 6.4 map25 格子事件 59／60／61 [驗]

FDFIELD 直接把 map25 三條格子規則固定如下；這項資料證據取代先前只看
IDA 通用間接交叉參照而留下的「event61 沒有 map25-local caller」錯誤斷言：

| event | selector | 格子 | handler 行為 |
|---|---:|---|---|
| 59 | 0 | y=36 全列 31 格 | 觸發單位 runtime `+6 != 0` 時，`0x3419C(39,44,0)` |
| 60 | 0 | y=22 全列 31 格 | 同 gate，`0x3419C(23,24,0)` 與 `(53,56,0)` |
| 61 | 1 | `(1,46)` | entry12 為零且觸發單位持有 item D0 時才進成功臂 |

event59／60 的 `0x3419C` 保存高四位，只把指定單位範圍低四位設成 0。
event61 成功臂移除觸發單位的 D0、播放 resource45 的 59-frame 演出、
設 battle-local state entry12、spawn group1、JOIN character31，依序使用
FDTXT indices 3/4；沒有 D0 時只使用 index2，不改 entry12。ch25 post
再以 entry12 選擇後續文字分支。

`native_field_event_rules.json` 綁定 FD2.EXE 雜湊並保存三條 editable rule；
map25 資產只因實際引用而嵌入。後續實作已把 selector0 的 event59/60 與
selector1 的 event61 接入正式戰鬥路徑：event61 會在成功行動後播放 resource45
的59幀演出，完成後才提交移除 D0、寫 entry12、spawn group1 與 JOIN31，並將新角色
寫回持續隊伍。這是重製端決定性 E1 路徑；仍缺相同狀態的原版 DOSBox 一般玩家
逐幀比較，不能提升為 E2 或宣稱整個第26戰已完成。

2026-07-29 的合法 IDA 9.4 與 Docker Capstone 交叉檢查又閉合 selector0
時機。`0x13488` 逐 byte 消費路徑，只有 path byte 1 呼叫
`0x1300D`；後者在七拍動畫的提交拍把 runtime `+0` 與
`[0x53AB1]` 各減一，再以新 `(x,y)` 呼叫 `0x13A44(...,0)`。
`0x12E38` 的索引式 `x + mapWidth*y` 也獨立固定參數順序。因此 selector0
精確代表「每個向左格步驟提交後」，不能泛化成四方向或整條路徑完成。
重製 `stepBattleWalk` 已在相同提交點執行 event59/60；向右反例測試固定
不得觸發。selector1 仍橫跨 `0x13A9F` 與 `0x18890` 的多個行動成功臂，
event61 presentation 完成前不接線。

### 6.1.1 ch21/ch22 動態增援(event_id 47/49)eax 來源解密 [驗]

gen-campaign v4 report 留下 6 筆「`groups: [$reg_or_mem(eax)]`」——`spawn_group(eax)` 的 `eax` 來自暫存器計算,
非字面常數,擷取器放棄。反組譯 event_id 47(`0x35112`,ch21/map20)與 event_id 49(`0x351e9`,ch22/map21)的
handler 本體,兩者在 `call 0x10b4e` 前的計算完全同構:

```
0x03511c  mov  eax, [0x53bef]   ; eax = 回合數(turn counter)
0x035121  mov  edx, eax
0x035123  sar  edx, 0x1f        ; edx = eax 符號位擴散(正數→0,負數→-1)
0x035126  sub  eax, edx         ; 負數時 +1(修正無條件捨去→趨零捨去)
0x035128  sar  eax, 1           ; eax >>= 1(算術右移)
0x03512a  push eax
0x03512b  call 0x10b4e          ; spawn_group(eax)
```

這是編譯器產生「有號數除以 2」的標準慣用法(`sar edx,31; sub eax,edx; sar eax,1`),保證負數也趨零捨去;
`[0x53bef]` 恆為正(回合數 1,2,3…),故實際等價於 **`group_id = turn_counter DIV 2`(無條件捨去)**。
event_id 49(0x351e9)同一段位移量(handler+0x0a..0x12)逐位元組相同,同一公式。[驗]

**ch21(map0→map20)/ch22(map21)套公式，對照版本化map roster的group存在性**：

| 章 | turn | event_id | 公式算出 group | map units.json 該 group 存在? | camp |
|---|---|---|---|---|---|
| 21(map20) | 2 | 47 | 1 | ✓(4 單位) | enemy |
| 21(map20) | 4 | 47 | 2 | ✓(4 單位) | enemy |
| 21(map20) | 6 | 47 | 3 | ✓(4 單位) | enemy |
| 21(map20) | 8 | 47 | 4 | ✓(4 單位) | enemy |
| 22(map21) | 3 | 49 | 1 | ✓(6 單位) | enemy |
| 22(map21) | 7 | 49 | 3 | ✓(6 單位) | enemy |

map20 實際 group 集合 `{0,1,2,3,4,255}`、map21 `{0,1,2,3,255}`——`turn/2` 算出的 1/2/3/4 與 1/3 恰好全部落在
存在的 group 內,且 map21 的 group2 對應另一筆已解出的字面事件(event_id50,turn5,camp=special,groups=[2],
own 陣營)不衝突,6/6 全部吻合。**已用 `tools/extract_event_id_groups.py` 的同款 basic-block walk 手動核對兩
handler 反組譯,非猜測**;`docs/data/turn_events.json` 對應 6 筆已把 `groups` 從 `$reg_or_mem(eax)` 換成算出的
整數,並補 `group_formula` 欄位記錄機制。

> 與 §6.1「5 個解出動態(`$turn_counter`,即 group=回合數本身)」是**不同公式**:event27/54/57 是 `group=turn`,
> event47/49 是 `group=turn÷2`——同樣的「回合數驅動遞增 group」設計母題,但除以 2 是因為這兩章每 2 回合才觸發
> 一次(turn events 只登記偶數/隔輪回合),group 编號仍要對齊「第幾波」而非「第幾回合」。

**map0/章1 event→group mapping 4/4交叉吻合**：對照
`ch01.json` authored events與原版map roster；這只驗mapping，不把scenario
升格成完整handler oracle——

| turn_events(map0) | event_id | handler | 解出 group | ch01.json 正解 | 結果 |
|---|---|---|---|---|---|
| T3, camp=ally | 0 | 0x341db | {3, 7} | `hano_hawat_join`: groups[3,7] | ✓ |
| T4, camp=enemy | 1 | 0x342b5 | {4} | `enemy_reinforce`: groups[4] | ✓ |
| T5, camp=enemy | 2 | 0x3431d | {5} | `pirate_boss`: groups[5] | ✓ |
| T6, camp=ally | 3 | 0x34377 | {6} | `coast_guard`: groups[6] | ✓ |

group 數字、單筆 vs 雙筆(T3 兩組)、觸發回合、camp 全部吻合。`docs/data/turn_events.json` 已補上
`groups`/`handler` 欄位(全 30 章)。

## 7. 對重製(Go/Ebiten ScenarioRunner)的意義

- **原版事件 = 編進 EXE 的每章 handler**,無法像資料般直接搬。重製要嘛逐章反組譯 handler 邏輯重寫,
  要嘛(建議)用**資料驅動 DSL** 取代:把「條件(單位群狀態 / 回合數)→ 動作(增援 / 對話 / 勝負)」表達成
  campaign.json 的事件節點(對映 doc 19 腳本系統)。
- 已抽出的raw原語可形成DSL候選，例如
  `when native_record_byte5_bit0(i)`／`when turn>=N`；前者必須保留
  per-handler caller與branch方向，不得縮寫成全域`unit[i].flag`語意。
- default handler（11章）已閉合為 `0x205b4/0x205be` 的 raw
  camp0／record0 三值規則；重製不可只用正規化「敵全滅」取代。18個特殊
  handler 仍需逐關保存額外條件與結果覆寫。

## 7.5 戰場單位有兩個來源:FDFIELD roster vs 事件進場(2026-06-28 證實)

掃全 12 關 FDFIELD `own`(己方)roster,**沒有任何一關含索爾(id0)/亞雷斯(4)等主角**。
**第1章「初試身手」= 海邊第一戰 = map0**(敵方 portrait 盜賊96 + 海盜頭目97 + 海防/援軍76 + 103;
與青衫第1章敵方完全對應),其 own roster **只有哈諾(1)+哈瓦特(3)**,且這兩人也不是第一回合就在場
(青衫:第3回合己方結束才從房子出來)。索爾/亞雷斯/悠妮/蓋亞**完全不在 roster**。
→ 戰場單位是**雙來源**:

| 來源 | 內容 | 機制 |
|---|---|---|
| **FDFIELD roster** | 每關的敵人 + 部分配角/ally(各關 map<N>) | 開場擺位 **或** 由事件按回合放出(哈諾/哈瓦特雖在 roster,T3 才進場) |
| **隊伍名冊 `[0x53bf7]` + 事件** | 玩家主角隊(索爾/亞雷斯/悠妮/蓋亞) | **由 pre-battle cutscene / 事件腳本動態進場** |

**第1章開場演出(實機)**:索爾/亞雷斯/悠妮/蓋亞的部署與此前序章
acting／camera是不同階段；舊「四人從戰場邊緣移入中央」不可直接由攻略推定。
之後才進入可操作戰鬥。即第一戰不是「擺好棋子開打」,而是 scripted 入場 cutscene。
全關玩家可見時序可用doc28／青衫作E3案例：開場主角隊→T3哈諾／哈瓦特
→T4敵援軍→T5海盜頭目→T6警備隊；每段實作仍以event handler/FDFIELD為準。

> ⚠ 更正(2026-06-29):前一版誤把第一戰寫成「序章 ch0=map2」。**第一戰是 map0**;map2 敵方為 [76,77],屬另一關。map↔章節對應應以**各關敵方單位特徵對青衫各章**核對,別套「map=章節×3+2」公式(未對齊實際關卡)。

**對 remake 的意義**:`export_units.py` 目前只導 FDFIELD roster,**玩家主角隊要另從隊伍名冊注入**,
且 roster 內單位也可能帶「進場回合」(哈諾/哈瓦特 T3);第一戰要實作「單位從邊緣走入 + 對話」的進場演出
(事件腳本 DSL 的 `spawn`+`move`+`dialogue`+`when turn>=N` 節點),不能只靠 map_units.json。

## 7.5.1 序章主角隊進場 staging:**戰場進場**直接定位,**cutscene 幕內**另有走位(2026-07-04 範圍修正)

> **範圍修正(2026-07-04,doc46 開場時間軸影片證據後)**:本節原標題/結論「無行軍動畫」**範圍過大,需修正**。
> 下方 2026-07-03 的反組譯+dosbox 複驗證實的是**「戰場進場(map0 spawn)= 直接定位」**——這條在
> `docs/knowledge-base/46-ch1-opening-timeline.md` §4(模板匹配 remake `battle_ch01` 開局位置)**再次複驗仍成立**,
> 沒有推翻。**被推翻的是「序章全程無走位」這個更廣的推論**:doc46 用影片逐幀證據(0.5 秒間隔連續抽幀)
> 找到至少兩處明確的**跨多幀角色位移**,發生在**序幕 cutscene 畫面本身**(map31/map32 複合場景,非戰場):
> ①王座廳對白說完,索爾 sprite 沿紅毯走下場(~1.5 秒,`ch1_trans_t1_sheet.png`)
> ②後山密林「比劍邀約」轉「發現悠妮與蓋亞」之間,索爾+亞雷斯用多幀畫面逐步接近悠妮/蓋亞
> (FDFIELD 出場位置證實兩組座標相距 14 格,非同格瞬移,`ch1_trans_t4_sheet.png`)。
> **這兩處走位用的是哪個 EXE 機制,尚未重新反組譯**(不在下方 0x3231b 三原語表的已知範圍內,
> 可能是同一 handler 內未逐一展開的呼叫、也可能在其他尚未追的子程序);remake 對應實作見
> `remake/internal/campaign/campaign.go`(`Actor.FromX/FromY/WalkFrames` 進場走位、`Node.ExitWalk` 退場走位)
> 與 `remake/cmd/fd2/main.go`(`storyWalkJob`),重用既有 `OffX/OffY` 插值,不等待 EXE 機制查清才動手
> （影片可作視覺／時序oracle，機制仍須E0；見doc46）。**下方2026-07-03內容保留原文（歷史記錄），
> 但讀者請以本段範圍修正為準**:「直接定位無行軍動畫」只在**戰場單位進場**成立,不適用於**序幕
> cutscene 畫面內**的角色走位。

playtest 反饋 #3 指出「序章劇本 staging 機制沒 RE 完整」,且使用者記憶「索爾一行人一開始走到地圖中央」。
本節用**靜態反組譯 0x3231b 本體 + dosbox 全程重跑序章開場**兩路收斂,把 §7.5 的「事件進場」講清楚「怎麼進場」。

**靜態反組譯(`tools/disasm_le.py range/dis`,`fd2-cap` docker)**:章節0 handler `0x3231b`(跳表 `0x51d71[0]`)
本體是一長串**線性**呼叫序列(對白段 `0x1366a` + 場景重繪 `0x15f84` + 少量特效),逐一過站無分支迴圈,
其中出現三種「群組登場」原語,語意各不相同:

| 呼叫 | 語意 | 對單位座標的影響 |
|---|---|---|
| `0x10b4e(group_id)` | **直接 spawn**(第1章序章內見於 group 1/3/5 等) | 無逐幀移動；但座標不一定原樣照抄。`[0x53AFA]` 非零才直接採 paired 6-byte position row 的 X/Y low bytes；零值會先標記現有單位占用，再以全圖 row-major Manhattan 規則選最近空格。這是建構時重新配置，不是進場動畫。 |
| `0x13185(unit_idx)`(序章開場呼叫 2 次迴圈,共 15+13=28 次) | **攝影機平移**(讀寫 `[0x53aa9]`/`[0x53aad]` camX/camY,doc 25 §7.6 同一對變數) | 無——單位不動,是**鏡頭**在移動;每次呼叫只把攝影機原點挪一格,配合後續 `0x15f84` 逐 frame 重繪 |
| `0x32999(group_id)`（序章 group 1/2；全域事件 group 4/5）`spawn_group_with_intro` | `0x111BA` 載入 FDOTHER #95/#9，內部呼叫 `0x10B4E`，再固定掃描 #9 的 12 個 `LMI1` 項目；每次只對新增且位於攝影機視窗內的單位做 `0x4E85B` 索引合成與 `0x11EB0` 呈現。呼叫端返回後才各自呼叫 `0x1366A(1/2/3/4)`。 | 無逐幀位置插值；wrapper 與已知 caller 都不寫 `[0x53AFA]`，因此內部 `0x10B4E` 讀零值配置旗標。12 次原版 pass 不等同重製端等待 12 個畫面 tick。 |

**三者共通點:全程沒有任何「單位座標逐幀 +1/路徑插值」的迴圈。** 移動的是攝影機,不是單位精靈——這與
doc 35 攻擊演出「無 runtime 縮放/無翻轉,景深燒在素材」的結論同源:**原版能省的動畫運算一律省,
靠鏡頭運鏡或素材本身,不做角色位移插值。**

**dosbox 實機複驗(220+ 張連拍,`extracted/story/staging_dosbox/seq/`,本機不入庫)**:全新遊戲 → 標題 START →
throne room 父子送別 → 黑幕轉場 → 草地小憩(索爾/亞雷斯對話,`proof_01_field_rest.png`)→ 比劍邀約(兩人
靠近,暗轉,疑為另一段小型過場非本節重點)→ 悠妮/蓋亞加入(失憶對話「我們是從哪裡來的?」)→ 是否赴
馬拉大陸的爭論 → 海盜堵路對峙(`proof_02_pirate_prebattle.png`,索爾/悠妮/蓋亞已在最終戰鬥位置,3 海盜
+1 機械兵已在各自位置)→ 指令環開戰(`proof_03_battle_command_ring.png`,HP/MP 狀態欄出現,單位位置與
上一張幾乎相同)。**逐幀比對:每個場景切換都是「背景/對話框瞬間換」的硬切,場景內單位座標在連續多張
截圖間完全靜止;從對峙畫面到開戰指令環,單位位置沒有位移**——與靜態反組譯結論一致:主角隊(及本章
遇到的海盜/機械兵)都是**直接定位**,沒有觀察到任何「單位行走/行軍」動畫。

**結論(2026-07-03 原文;§7.5.1 開頭範圍修正已標記何處不再成立,見上方)**:
1. **remake 現行做法(main.go focusOnParty 純鏡頭對準 + event.go spawn_party 直接定位)已忠實**,#3 **不是 bug**,不需要補行軍動畫。——**此點對「戰場進場」仍成立**;但序幕 cutscene 本身(map31/32)需要走位動畫,已於 Phase 2 補上(見上方範圍修正段)。
2. ~~玩家記憶「一行人走到地圖中央」查無實據~~ **此點已被 doc46 影片證據部分推翻**:序幕 cutscene 內(非戰場)確實有角色跨幀走位(見上方範圍修正),雖然仍不是「世界地圖/道路移動」那種大範圍場景,但也不是「鏡頭動、人沒動」的錯覺——原文「最可能的解釋是攝影機平移錯覺」這個判斷本身是錯的,以 doc46 為準。
3. 先前 event.go 註解一度誤引「doc 25 §7.5.1 dosbox 實機證實[世界地圖走位]」,但該小節當時並不存在——本節即補上正確內容並修正該註解的引用鏈(§7.5.1 = 本節,無世界地圖佐證)。此點不受本次修正影響。

## 7.6 戰場視窗固定 13×8 格,原版無「地圖比視窗窄」的清背景邏輯(2026-07-03,反組譯)

remake 內部畫布 640×400(2x hi-res,tile 維持原生 24px),map0(24×24 格)在此畫布下比可視寬度窄
(576<640),右緣露出「畫面外」的區域;為了確認 remake 該填什麼色,反組譯原版戰場重繪鏈:

- **主重繪函式 `0x11cac`**(每幀呼叫,`0x10010`「戰場設置」進場後的主迴圈 call):依序呼叫
  `0x1297d`(捲動動畫計數器)→ `0x11eee`(地形層)→ `0x122dc`(移動範圍高亮疊圖)→ `0x127a9`(單位層,
  含 `0x129ec` 收尾)→ `0x1acf3`(游標/UI)→ `0x11eb0`(present)。work buffer stride **0x1c8=456**
  (與 doc 35 攻擊演出的 0x280=640 不同,tactical 另有獨立合成 buffer)。
- **地形層 `0x11eee`**:對「一般章節」(排除 9/0x18/0x19/0x1c/0x1d 世界地圖類與 0x11/0x15/0x16/0x17/0x1b
  過場標題類,那幾類走不同的 BG 貼圖分支),直接落入逐格迴圈(inline,0x12164–0x1222f):
  ```
  for row in 0..<8:              ; 高度計數硬編碼 8(0x011cd4 push 8)
    for col in 0..<13:           ; 寬度計數硬編碼 0xd=13(0x011cd6 push 0xd)
      idx = (row+camY)*[0x53ac1](地圖寬) + (col+camX)   ; camX/camY = [0x53aa9]/[0x53aad](捲動原點)
      entry = FDFIELD[idx*4 + [0x3a51]]                  ; [0x3a51] = FDFIELD.DAT 載入基底(le_xref 驗證)
      call 0x4deda / 0x4dcc6(dst, tile_sprite, stride)    ; 無條件 blit,兩者僅差是否轉透明色 0xFF
  ```
  **13×8 格 × 24px = 312×192px**,與 present 呼叫的視窗尺寸(`0x011d12 push 0xc0` / `0x011d17 push 0x138`
  = 192/312)吻合 → **原版戰場視窗永遠固定 13×8 格,不隨地圖尺寸縮放**。
- **關鍵:整個地形迴圈裡沒有任何 `memset`/fillrect/rect 原語**(比對戰鬥演出 doc35 §3 同一結論:
  「無 fillrect/circle」)——每格永遠呼叫 blit,**沒有「地圖格不存在就清某色」的分支**。
- **驗證:原版全 34 張地圖沒有一張窄於視窗**(`extracted/maps/maps_metadata.json` 全量掃描:
  最小寬 18 格 map2、最小高 20 格 map3,皆 ≥ 13×8)。→ **「地圖比視窗窄」在原版從未觸發過**,
  因此原版壓根沒有為這個情境寫清背景/邊框邏輯,不是「找不到」,是**這段代碼從未被需要過**。
  remake 會撞到這情境,純粹是 remake 自己選了比原版視窗寬的 FOV(640px、tile 仍 24px 原生尺寸
  ≈ 26.7 格可視寬,大於任何原版地圖或原版 13 格視窗)——**這是 remake 設計決策造成的新情境,不是
  移植失真**。
- **remake 對齊**:`cmd/fd2/main.go` 的 `screen.Fill(黑)` 在地圖繪製前打底,合理(無原版行為可循,
  黑色純粹是視覺乾淨的預設,非「原版就是這樣填」)。已截圖確認(`extracted/remake_shots/map0_edge_test.png`)
  map0 右緣為乾淨黑邊,非殘影黃白。

## 8. 受阻 / 待續

- **[已解,見 §3.1]** ~~ch27「擊毀機甲隊長」勝利判定的底層機制(class-id/計數器?)~~ →
  `0x51b19[26]=0x20a87`完整反組譯:沒有隊長專屬計數器，就是共用原語`0x205be`的「全部敵方
  record死光」通用判定，額外疊加`record[1]`(疑似悠妮)死亡覆寫。回應doc58續五十九～續六十一
  的live測試負面結果，解釋「捷徑寫3隻隊長不會贏」的根本原因；`0x51b19[26]`實際呼叫時機
  (§1 caller列表)未展開，留待下一輪。
- **[已解,見 §6.1]** ~~`turn_events.event_id → group` 對應機制(先前疑 `0x22e5c`,未解)~~ →
  真正消費點是 `0x1a813`(3 呼叫點 camp filter)+ 全域 `event_id` 跳表 `0x51b91`
  （全表 90 entries；FDFIELD 回合事件使用 0..57）+
  spawn 原語 `0x10b4e`/`0x32999`;`0x22e5c` 是固定資源 #79 呈現路徑，
  與 turn_events 無關；「第1章專屬中場」舊名稱已撤回。
  map0/章1 event→group mapping 4/4交叉吻合，`docs/data/turn_events.json` 已補 `groups` 欄；不代表完整章節handler已驗。
- **[已解,範圍限定見 doc 26]** ~~18 battle-event skeleton 語意 + 動作函式~~ → `docs/data/battle_events.json` 目前匯出的 battle-event skeleton 未記錄 action_fns，故該資料集只保存條件→設碼/繪圖；這不能外推到含 dialog/acting/sync/JOIN 的 postbattle cutscene handlers。條件原語與 raw caller 仍以各 handler CFG 為準。
- **[修正]** byte(+5) bit0 reader／writer 已分開：`0x3453e` 僅回傳 `&1`，constructor／HP writer／`0x32975` 是獨立 caller；不得把它們合併成全域死亡／存活欄位。舊說「bit0=存活、初始化=1」已撤回。回合數=`[0x53bef]`（非 `[0x53ec8]`，後者為累積計數）；team-completion 語意仍待 state-machine evidence。
- **修正 doc 24**:§6 稱「事件腳本解譯器(大函式 0x205c9–0x20c64)」用詞不精確 → 實為**章節戰場事件 handler 表 0x51b19,各 handler 在 0x205b4–0x20bf5**(非單一解譯器,非 byte-code)。已於 doc 24 §6.3 附註。
- **2026-07-29 函式邊界再勘誤**：`0x205be` 在 `0x205d5` 直接跳到
  `0x2067e`，不會落入相鄰的 `0x205da`。因此舊「`0x205be` 先設2、再清0並
  呼 `0x1088d`」是把兩個入口線性拼接的錯誤。直接指令與 callers 保存於
  [`fd2_battle_result_205be_disasm.txt`](../data/fd2_battle_result_205be_disasm.txt)。

## 9. 社群修改表 oracle 對照：存檔可用性與寶箱持久化(2026-08-19)

> 對應 `91-worklist.md` 第848行「社群行為 oracle 對照」；來源是
> [GitBook FD2.EXE 修改表](https://jaceju-favorite-games.gitbooks.io/fd2/content/modify/FD2_EXE.html)
> 列出的「入隊」「隨時存檔」「等級上限」「寶箱持久化」四項金手指行為線索
> (已記錄於 `SESSION-HANDOFF-2026-07-06.md` L411)。本節只把其中「隨時存檔」
> 「寶箱持久化」兩項，對照本 repo 既有 RE 證據(存檔 `0x30012`/`0x2602c`
> 系列、寶箱事件 `0x35854`(原誤記 `0x354FE`，見 doc25 §11.7)/`0x1AA1D` 系列)轉成
> 可編輯規則與 regression 方向；
> 不把修改表本身當位址證據，只用它的「行為描述」當低成本 oracle 對照對象。

### 9.1 存檔(save)：原版不是「隨處可存」，而是兩個固定戰間呼叫點 [驗]

> **2026-08-25 live 覆核旗標**：本節「`0x2cad7` gate→`0x2ccb6`→`0x30012`」
> 這條具體呼叫鏈是純靜態(xref)證據；`91-worklist.md` UI-VIS-LOAD
> 2026-08-25 續輪用 `LOGC` ground-truth 指令追蹤(見 `98-tooling-
> infrastructure.md`)重新走一次「town hub 出口→YES確認」的 live 路徑
> (存檔位 1「第二十七章 命運的交會點」)，3 億指令涵蓋 YES confirm 到
> 過場對白全程，**`0x2cad7`/`0x2ccb6`/`0x30012` 三個位址全部零命中**
> (同一份追蹤裡 `TXT` 直譯器 `0x1B1F84` 有命中，排除 delta 算錯)，
> `FD2.SAV` mtime/checksum 全程未變。這條 live 路徑顯示的文字內容
> (FDTXT `0x201`「要進入戰場嗎？」)與本節描述一致，但底下呼叫鏈明顯
> 不是這裡記載的這條——**「原版只能在戰間兩個固定點存檔」的大結論本身
> 未被推翻(沒有相反證據)，但`0x2cad7`/`0x2ccb6`是這條 live 路徑實際
> 呼叫鏈這個具體 claim 需要下一輪重新核對**，`[驗]` 標記對這個子結論
> 應視為待覆核，不要當成已定案的 live-verified 事實直接引用。完整過程
> 見 `91-worklist.md` UI-VIS-LOAD 條目。
>
> **2026-08-25 續輪(`savewriter`平行 harness)：真正的酒店存檔 writer 已用
> 同一套 `LOGC` ground-truth 追蹤方法論定位，修正本節標題與下方內文對
> `0x30012`/`0x2ccb6`/`0x2cad7` 的引用**——這條 live 路徑是「軍營帳篷場景
> (游標預設在酒店)→Enter進酒店→NPC對話框右下角4-icon列→Right×1選
> index1(磁片+左箭頭)→Enter開四槽清單→對slot1按Enter」，即
> `91-worklist.md` UI-VIS-LOAD 記載的「tavernE2」輪已 live 驗證會真的
> 寫入`FD2.SAV`的那條路徑。武裝`LOGC`(6億指令)涵蓋從進酒店到「記錄
> 儲存完畢！」全程，事後用`FD2.SAV`的`stat`確認`mtime`從harness
> fresh-copy的`Birth`時間(20:54:07)前進到`Modify`21:00:08(checksum
> 因為這次是「LOAD slot0→立即原地重存同一slot0」的idempotent write，
> 維持`e6d9a35756cddfc2519969b10f039181`不變——這正是`98-tooling-
> infrastructure.md`與本節上方旗標記錄過的「不能只看checksum，要核對
> mtime」陷阱的又一次實例，mtime本身已足以證明有真實write syscall)。
>
> 去重後 9960 個唯一位址交叉`ghidra_batch_probe.py`：舊鏈
> `0x30012`/`0x2ccb6`/`0x2cad7`/`0x2fd93`/`0x318ad`/其所在完整函式
> `0x2ff01`與其內部呼叫目標`0x2d80d`**全部零命中**，與 saveE2 輪對
> town-hub-exit路徑的既有結論一致再添一組獨立證據。**真正的 writer 是
> `0x2968d`**(`FUN_0002968d`，範圍`0x2968d..0x2986e`)，靜態反組譯全鏈
> 逐位元組核對：
> - 入口先 `fopen("FD2.SAV","rb")`→`fread(buf,1,0x59cb,fh)`→一個
>   transform helper(`0x4df28`)→`fclose`，把既有存檔內容讀進 0x59cb
>   (=**22987 十進位，與 harness `FD2.SAV`實際檔案大小逐位元組相同**)
>   bytes 的記憶體 buffer。
> - 迴圈以 `FUN_00029bcb()`讀取存檔位清單的使用者輸入事件(-1=取消退出)；
>   選定一個槽位後，把該槽 record(`buf+0x312b+slot*0xa28+0xa00..+0xa09`)
>   的 metadata 逐 byte 寫入(`DAT_00053c03`/`DAT_00053bfb`/`DAT_00053bf3`
>   /`DAT_00051aab`/`DAT_00053af9`/`DAT_00051e61`/`DAT_00051e62`)——這與
>   本節先前記載的「metadata `+0..+9`」欄位語意一致，是同一套`0x59cb`
>   envelope 格式的**另一個獨立實作**，不是同一段程式碼。
> - 再 `fopen("FD2.SAV","wb")`→checksum(`0x4df09(buf,0x59cb)`)寫入
>   `buf+0x59c7`(envelope 尾端 4 bytes，呼應本節「checksum」欄位的既有
>   描述)→transform(`0x4df28`)→`fwrite(buf,1,0x59cb,fh)`→`fclose`。
> - `fwrite`呼叫鏈完整靜態追到底：`0x377a3`→`0x3de66`→`0x46d53`→
>   `0x46da2: MOV AH,0x40 / INT 21h`(DOS 寫檔系統呼叫，`ghidra_batch_probe`
>   對函式起點做`bytes`批次掃描逐位元組確認`b4 40`opcode)；另外找到兩個
>   姊妹低階寫檔stub `0x3d12a`(`FUN_0003d093`)與`0x3d470`(`FUN_0003d3e5`)，
>   三者這輪追蹤裡都被命中，推測是同一份靜態鏈結 CRT 對`fwrite`的多個
>   inlined/重複副本。
> - fopen 檔名/模式字串直接 byte dump 核對：`0x50254`/`0x5025f`兩處都是
>   `"FD2.SAV\0"`，`0x50251`是`"rb\0"`、`0x5025c`是`"wb\0"`——與上面推論的
>   讀/寫兩段 fopen 完全吻合，不是猜測的函式簽名。
> - 呼叫者鏈：`FUN_0002968d`(0x2968d)由`0x29300`(`FUN_00029300`)的
>   `index==1`分支呼叫，該函式反編譯後是清楚的三分支(+一個 live 測試
>   從未觸及的第四分支)icon dispatcher：`index0→0x29620`(狀態)、
>   `index1→0x2968d`(存檔，本節新確認)、`index2→0x2986f`(離開)——與
>   `91-worklist.md` tavernE2 輪 live 觀察到的「index0=狀態/index1=存檔/
>   index2=離開/index3 未解」逐項精確對應。`0x29300`由`0x2670e`
>   (`FUN_0002670e`，酒店 NPC 對話框/4-icon列本體)呼叫。這條完整呼叫鏈
>   (`0x2670e→0x29300→0x2968d→...→0x46da2 INT21 AH40`)裡的每一個位址
>   都在本輪 `LOGC` 追蹤的 9960 個唯一命中位址集合裡被直接確認執行過，
>   不是靜態推論。
> - **誠實限制**：這條鏈是 tavern icon1 存檔路徑專屬(**不是**取代舊
>   `0x30012`鏈，是證明舊鏈在這條 live 路徑上未被呼叫、且找到這條路徑
>   實際呼叫的是誰)；`0x30012`/`FUN_0002ff01`本身是否仍是「整備/軍營
>   出口」流程真正的 writer(如果那條路徑真的會存檔)、或者它本身也是
>   另一條從未被 live 觸發過的死碼，**仍未證實**，需要另一輪針對
>   `0x2fd93`/`0x2cad7`整備分支單獨做 live trace 才能回答；本輪範圍
>   只涵蓋並修正 tavern icon1 這一條。截圖：
>   [`tavern-icon1-save-writer-logc-trace-confirmed.png`](../figures/tavern-icon1-save-writer-logc-trace-confirmed.png)。
>   完整過程見 `91-worklist.md` UI-VIS-LOAD 條目。
>
> **2026-08-25 續輪(`camproute`平行 harness)：本節標題與上面幾輪引用的
> `0x2cad7`/`0x2ccb6`/`0x2fd93` 三個位址本身是錯的(舊 EXE 版本的殘留位址，
> 未在目前 `FD2Analysis3` Ghidra project 裡對應到「城鎮hub存檔閘門」這段
> 邏輯)——`ghidra_batch_probe.py` 直接查證：`0x2cad7`/`0x2ccb6` 兩個位址
> **都不落在任何已知 function 邊界內**(`function_bounds` 回傳
> `in_function:false`，Ghidra base 分析從未在這裡建過指令邊界，硬解出來的
> `disasm` 是垃圾位元組)；`0x2fd93` **落在一個完全無關的函式**
> `FUN_0002fb2c`(0x2fb2c..0x2fe13，一段戰鬥前 party 動畫/montage 迴圈，
> 呼叫 `FUN_0004e98d`/`FUN_00017aa9` 這類移動渲染函式，與存檔邏輯無關)。
> 也就是說，本節從 `saveE2`/`savewriter` 輪起，每次「對 `0x2cad7`/
> `0x2ccb6`/`0x2fd93` 做 LOGC 追蹤得到零命中」的結論，其實是在追蹤**跟
> 存檔閘門完全無關的位址**，不是真的驗證了「城鎮 hub 出口流程沒有走存檔
> 閘門」這件事——零命中本身沒錯，但它沒有回答原本要問的問題。
>
> **修正後的靜態證據**(`xref_to` 與 `call_scan` 兩種獨立方法交叉確認，
> 結果一致)：writer `FUN_0002ff01`(entry `0x2ff01`，doc25 稱的
> `0x30012` 是其內部呼叫 `0x2d80d` 的那一行，位於函式中段偏移
> `0x111`)在目前 build 裡**全 EXE 只有兩個直接呼叫者**：
> - `0x15400`(位於 `FUN_00015311`，entry `0x15311`)——本身是一個依
>   `DAT_00053c2f`/`DAT_00053af9` 分流的閘門：`(DAT_00053c2f < 10) &&
>   (DAT_00053af9 == 0)` 才呼叫 writer，否則走一個 `DAT_00051d01` 索引的
>   函式指標跳表。`FUN_00015311` 由 `FUN_00013a9f`(0x13a9f，一個依
>   `record[+0x34]&0xf` 分流的 11 分支 per-unit 狀態機，`record` 基底
>   `DAT_00053a45 + unit_index*0x50`)與 `FUN_00014ef0`(0x14ef0，依多個
>   `DAT_00053c23`/`DAT_00053c33`/`DAT_00053c4f` 章節/難度門檻決定要不要
>   進 `FUN_00015311`)呼叫。
> - `0x1d43c`(位於 `FUN_0001cff0`，entry `0x1cff0`)——結構幾乎相同的
>   第二個閘門：`bVar1 = local_20[DAT_00053c57]`，`(bVar1<9) ||
>   (bVar1==0x18) || (bVar1>0x1b)` 才呼叫 writer，否則同樣走
>   `DAT_00051d01` 跳表。`FUN_0001cff0` 由 `FUN_00018d8c`(0x18d8c，一個
>   依 `DAT_00053c57` 模式選擇器分流的迴圈：`==0` 處理某種roster載入、
>   `==1` 就是反覆呼叫 `FUN_0001cff0()` 直到非零、`==2` 呼叫另一函式)
>   呼叫，`FUN_00018d8c` 本身由 `FUN_00018890`(0x18890)呼叫。
>
> 這兩條鏈跟本節標題原本描述的「`0x2cad7` gate table 分流兩條路徑」
> 結構上是同一個概念(兩個互斥的存檔閘門，各自依某個 per-chapter/
> per-mode 門檻決定要不要呼叫 writer)，但**位址完全不同**——舊位址是
> 錯的，`0x15311`/`0x1cff0` 這兩條才是目前 build 真正的呼叫鏈。
>
> **live 覆核(`camproute` harness，2026-08-25)**：用同一張 `saveE2`/
> `savewriter` 輪用過的存檔位1(raw chapter `0x1a`=26，顯示「第二十七章」，
> 依本節下方「城鎮流程」/「整備限定流程」分類屬於 `byte[chapter+0x526b9]
> ==0` 的**城鎮流程**、不是整備限定流程)，走「LOAD→軍營帳篷場景→
> icon選單`Right×3`→「出口」→「要進入戰場嗎？」YES」這條與 `saveE2`
> 輪完全相同的路徑，這次武裝 `LOGC`(10.7 億指令，涵蓋 YES confirm 到
> 完整過場對白到真正進入戰鬥地圖部署畫面全程)並用上面修正後的正確位址
> 交叉比對：
> - `0x18890`→`0x18d8c`→`0x1cff0` **三個位址全部命中**(在去重後 14,924
>   個唯一位址集合裡直接確認)，證實這條 live 路徑確實會執行到修正後的
>   真正閘門鏈——不是猜測，是這輪 `camproute` 自己重新武裝的追蹤直接測到的。
> - 但 `FUN_0002ff01`(0x2ff01/`0x30012`)、其內部呼叫的 `0x2d80d`、以及
>   另一條閘門鏈(`0x15311`/`0x15400`/`0x13a9f`/`0x14ef0`)**全部零命中**，
>   跟 per-unit roster 迴圈(`0x1d80b`/`0x1d8ba`)也零命中。
> - 對照 `FUN_0001cff0` 的分支條件(`bVar1<9||==0x18||>0x1b` 才呼叫
>   writer)：這條 live 路徑走的是**不呼叫 writer 的那一臂**(跳表分流)，
>   與本節下方「城鎮流程」章節分類完全自洽——這次測的存檔本來就屬於
>   `byte[chapter+0x526b9]==0` 的城鎮流程，不是唯一應該打到 writer 的
>   「整備限定流程」(raw chapter 22..24/27..29)。也就是說，**這輪並沒有
>   否定`0x30012`的可達性，反而用正確位址第一次乾淨地印證了本節原本的
>   結構性主張**(城鎮流程走跳表、只有整備限定流程才走 writer)——只是
>   手上沒有 raw chapter 22-24/27-29 的存檔可以直接 LOAD 測試「應該會
>   呼叫 writer」的那一臂，這需要真的推進到那幾章(或另尋捷徑)才能補齊，
>   不在本輪合理工作量內完成。
> - **誠實結論**：`0x30012`/`FUN_0002ff01` **不是死碼**——修正後的靜態
>   呼叫鏈(`0x15311`/`0x1cff0` 兩條)都是被 live 追蹤直接證實會執行到的
>   真實 UI 分派程式碼路徑(`0x1cff0` 這條本輪剛剛實測命中)，不是從未被
>   接進任何狀態機的孤立函式；但也**尚未被 live 直接命中過**——本輪與
>   之前所有輪次一致地顯示，凡是測過的存檔/路徑，走的都是這兩個閘門的
>   「跳過 writer」那一臂。下一輪如果要徹底補齊，需要一張 raw chapter
>   22-24 或 27-29 的存檔（目前 harness 內建的 4 個存檔位都不在這個範圍：
>   raw chapter 分別是 0x1a/0x06/0x07/0x08）。截圖：
>   [`camproute-town-hub-exit-confirm-dialog.png`](../figures/camproute-town-hub-exit-confirm-dialog.png)、
>   [`camproute-battle-map-after-yes-confirm-ch27.png`](../figures/camproute-battle-map-after-yes-confirm-ch27.png)。
>   完整過程見 `91-worklist.md` UI-VIS-LOAD 條目。
>
> **2026-08-25 續輪(`writerfire` 平行 harness)：終於用上 raw chapter 27
> (22-24/27-29 這個「整備限定流程」範圍)的合成存檔直接測試，但writer依然
> 零命中——且發現doc56的整備UI位址本身也是舊版殘留**。用 `tools/fd2save.py`
> 把 harness 私有 `FD2.SAV` slot0 的章節 byte 從 `0x1a`(26)改成 `0x1b`(27)
> (round-trip 自檢通過)，LOAD 後 UI 顯示「第二十八章」（=raw+1，與既有公式
> 吻合），**選中後畫面直接跳過城鎮 hub，顯示 FDTXT `0x19a`「要記錄戰況嗎？」**
> ——這是本節「整備限定流程跳過城鎮hub直接顯示0x19a」這個結構性主張第一次
> 被 raw chapter 真的落在 22-24/27-29 範圍內的存檔 live 印證（先前所有輪次
> 測的都是範圍外的章節）。武裝 `LOGC`(10 億指令)後按 Enter 接受，進入一個
> 與 `56-fd2-remake-sdd.md` 描述的 `0x318ad` 選人畫面外觀一致的介面（HP/MP
> 狀態欄＋出戰/剩餘人數計數器＋角色 icon 網格，Enter 對目前游標角色
> toggle 選取＋前進一格，剩餘人數同步遞減/遞增)。**用 `xref_to` 重新核對
> `FUN_0002ff01` 在目前 build 全 EXE 依然只有 `camproute` 找到的那兩個
> caller(`0x1d43c`/`0x15400`)，沒有第三個**；完整涵蓋「YES 確認→選人畫面
> 反覆互動(全選/reset 循環)」全程的 1 億～10 億指令 `LOGC` 追蹤，對 writer
> 本體(`0x2ff01`/`0x30012`)、兩個已知 caller、及它們各自的外層 dispatcher
> (`0x18890`/`0x18d8c`、`0x13a9f`/`0x14ef0`)**全部零命中**——比 `camproute`
> 的結果更弱：`camproute` 的城鎮路徑至少命中了 `0x18890→0x18d8c→0x1cff0`
> 這條 dispatcher(只是在 `0x1cff0` 內部走了跳過 writer 那一臂)，這輪的
> 整備限定路徑連 dispatcher 本身都沒進去過。**方法論已交叉驗證無誤**：
> 追蹤期間吞吐量最高的位址(native `0x10620`)換算後精確命中 Ghidra 一個
> 真實 50-byte 函式 `FUN_00010620`，逐位元組與 `56-fd2-remake-sdd.md`
> 描述的「`0x32004`...輪詢 `0x10620`」吻合，證實 delta(`0x19C000`)/CS
> (`0170`)換算沒有出錯。**同時發現 doc56 對這個選人 UI 本身引用的位址
> (`0x318ad`/`0x31e80`/`0x32004`/`0x320fc`/`0x31d3c`/`0x318c7`)全部
> `function_bounds` 回傳 `in_function:false`**——跟本節先前修正
> `0x2cad7`/`0x2ccb6`/`0x2fd93` 時發現的問題是同一類：舊版/舊 IDA session
> 殘留位址，從未在目前 `FD2Analysis3` 重新核對過，`56-fd2-remake-sdd.md`
> 的整備 UI 章節需要下一輪比照本節做同樣的 xref_to/LOGC 重新定位。
> **結構性卡點(誠實記錄，非猜測)**：這個選人畫面的出戰上限是 19(對應
> `[0x53c03]>0x1a`分支)，但整款遊戲可招募角色總數只有 13(與 `prepE2`
> 輪既有結論一致)，选滿 12 名可用角色後 `Escape`／`Delete`(依 doc56
> raw scancode 分析選出的兩個候選「確認」鍵)都只會把選取重置回全空，
> 不會前進到 `0x320fc`/`0x31d3c`——也就是說這條路徑在鍵盤操作範圍內
> **從未能真正推進到選人畫面之後**，无法排除 writer 其實在更下游(選人
> 完成後)才被呼叫的可能。曾嘗試把存檔 roster_count 從 13 硬改成 19(複製
> record0 填補空位)以求選滿，但這樣改完後遊戲在 YES 確認後直接靜默彈回
> 標題 LOAD 選單(重跑一次同樣發生，不是偶發)，判斷是 roster 完整性檢查
> 失敗，**不是**安全的合成測試手法，不建議下一輪重複。**誠實結論**：本輪
> 沒有能夠證實或推翻 writer 在整備限定流程真的會被呼叫；反而讓本節「Yes
> 才呼 `0x30012(0)`」這個沿用自舊文件的具體宣稱本身變得可疑——更可能的
> 結構是 writer(如果這條路徑真的會呼叫它)是在選人 UI**完成**(而非
> 剛進入)之後才被呼叫，需要下一輪先用 LOGC ground-truth 方法重新定位
> doc56 選人 UI 目前 build 的真實位址，才能繼續往下追。截圖：
> [`writerfire-fdtxt-0x19a-record-battle-confirm.png`](../figures/writerfire-fdtxt-0x19a-record-battle-confirm.png)、
> [`writerfire-selection-ui-all-selected-remaining07.png`](../figures/writerfire-selection-ui-all-selected-remaining07.png)、
> [`writerfire-selection-ui-delete-resets-to-empty.png`](../figures/writerfire-selection-ui-delete-resets-to-empty.png)。
> 完整過程見 `91-worklist.md` UI-VIS-LOAD 條目。
>
> **2026-08-26 續輪：deploy cap「19 vs 13」矛盾——確認不是誤讀，找到既有的
> 獨立驗證，19/15 門檻與「選滿才能過」都是真的，缺口在於測試存檔的
> 招募進度而不是遊戲邏輯**。任務：re-derive writerfire 記錄的「結構性卡點」
> ——選人畫面出戰上限 19、全遊戲僅 13 名可招募角色、Escape/Delete 只會
> 重置——先重跑 `ghidra_batch_probe.py` 對 doc56 UI-11 段落引用的
> `0x318ad/0x31e80/0x32004/0x320fc/0x31d3c/0x318c7/0x31a29/0x36d98`
> 八個位址做 `function_bounds`：**全部回傳 `in_function:false`**，逐一確認
> writerfire「doc56 整備 UI 位址也是舊版殘留」的猜測成立。嘗試重新定位：
> 對已驗證行為特徵『輪詢 `0x10620`』的 `0x10620` 做 `call_scan`（`xref_to`
> 在這類未分析區域會漏掉呼叫端，need call_scan 的 byte 級 E8 掃描），額外
> 抓到 `0x32194`（`in_function:null`，`confirmed_call_instruction:true`），
> 與舊位址 `0x32004` 差值 `+0x190`；套用同一 delta 到 `0x318c7` 得到
> `0x31a57`，`disasm` 顯示乾淨對齊、無 misalignment 的合法指令序列
> （`PUSH 0xa0000` 直寫 VGA framebuffer、經 `0x111ba` 存取 FDOTHER/FDICON
> entry）——兩個獨立位址都符合同一 `+0x190`，但套用到 `0x318ad`/`0x31a29`/
> `0x320fc`/`0x31d3c` 得到的候選點要嘛落在指令中段（bytes dump 逐一核對，
> 例如 `0x320fc+0x190=0x3228c` 精確命中鄰近一條 `MOV EAX,EDX` 指令中間第2
> byte，真正邊界在 5 byte 前）要嘛 `end_of_code`。**結論：`+0x190` 是這個
> 區塊局部有效的 anchor，不是全域常數 delta**——facility 入口/reorder/
> 最終確認三個對回答部署上限最關鍵的位址本輪未能精確定位，詳細記錄與
> bytes dump 見 `known_address_errata.json` 新增條目。
>
> **關鍵轉折：這個問題其實已經在完全獨立的另一輪調查裡被解開過，只是從未
> 被本節或 2026-08-25 這一批平行 harness 引用**。`docs/knowledge-base/
> 58-remake-live-verification-log.md` 2026-08-17/18（續九～續十一，
> task #118，比 writerfire 早了約一週）針對「ch23 選人畫面死結」做過同一個
> 畫面的完整反組譯＋live 驗證，**且明確用純檔案 byte-signature 搜尋對照過
> 目前實際在跑的 509158-byte `FD2.EXE`(MD5 `33464C81E6A364FD0660141139AA8E6E`，
> 已用 `PUSH 0x164` 開頭序列在該檔案裡找到 `0x2ff01` 對應的唯一 file offset
> `0x55f15`，確認就是本專案其餘各輪一直在用的同一份「真檔案」)，不是單靠
> Ghidra 專案（那一輪自己也踩過『Ghidra 專案其實裝的是另一個 802705-byte
> 版本』的坑，教訓記在該文件續十）**：
> - file offset `0x50f4e`＝出戰目標人數的立即值：預設 `0x0f`(15)，章節
>   `>26` 時改成 `0x13`(19)——與本文件（`[0x53c03]<=0x1a→15,>0x1a→19`）、
>   `56-fd2-remake-sdd.md` UI-11（`NativePreparationPartyLimit`）、
>   `91-worklist.md`「逐章旗標表」三份完全獨立的靜態/live 結論**三方一致**，
>   19 這個數字對 raw chapter 27（顯示第二十八章，`>26` 那一臂）而言
>   **不是誤讀**，是真實的目標值。
> - file offset `0x510f7`＝`CMP EAX,EBP`＋`JNZ`（已選人數≠目標就重複迴圈，
>   相等才真正離開）——**確認任務描述的解法(b)不成立**：這個畫面沒有
>   「選不滿也能用別的鍵確認離開」的分支，必須精確湊滿 15／19 才會走到
>   `0x320fc`/`0x31d3c`；Escape 對應的是該函式內另一個獨立、刻意寫死的
>   「整批重置回 15/15」分支，不是被誤讀的確認鍵。
> - **這輪也用即時 single-step 測試直接證實**（不是猜測）：Enter/方向鍵的
>   游標移動被寫死排除陣列最後一個 index（`roster_count-1`）——13 人存檔
>   時 index 12（隊伍第13人）**用任何輸入都無法到達**，讓已選人數永遠卡在
>   12，湊不滿 15，所以畫面看似「無限循環＋Escape重置」，其實是遊戲邏輯
>   本身正確地在等一個永遠不會出現的第13個可選欄位。
>
> **由此回答任務要求的四個解法選項**：(a) 不成立——章節>26 用 19 這個值
> 本身是對的，不是該用更低值的誤讀。(b) 在指令層級確認不成立——`JNZ` 迴圈
> 要求精確相等，沒有「選不滿也能確認」的隱藏路徑。**(c) 成立，且已有交叉
> 證據**：「全遊戲僅 13 名可招募角色」這個結論只對**本輪與之前所有輪次
> 測試用的存檔**成立（機器上僅有的 4 個真實存檔槽全是早期章節；writerfire
> 用的 raw ch27 存檔是 `fd2save.py` 直接改章節 byte 的捷徑合成檔，沒有真的
> 玩過中間章節），不是遊戲本身的結構性上限。獨立核對
> `docs/data/chapter_beats/ch{NN}_post.json` 的 `"join"` op 數量：ch01-10
> 共 9 次加入、**ch11-22 共 13 次加入**（與 doc58 續九引用的「背景 agent
> 查證 ch11-22 之間共有13名角色加入」的數字**逐一吻合**，兩個完全獨立的
> 資料來源給出同一個 13）、ch23-29 再 2 次。也就是說一個**真的照劇情打
> 過來**（不是章節跳躍合成）的存檔，抵達顯示選人畫面的章節（23-25/
> 28-31）時，隊伍規模粗估已在 20+ 人，遠超過 15／19 的目標，湊滿並不難；
> 之所以每一輪都卡住，是因為測試用的存檔全部繞過了 ch11-22 這一段負責
> 加人的劇情。
>
> **仍未解決、留給下一輪的具體問題**：doc58 續十一反組譯游標移動程式碼時
> 另外記錄一句「畫面實際渲染迴圈固定只畫 `EBX=0xb..0`(12張portrait)，
> 不論真實隊伍人數多少」——若這句話字面成立（渲染上限硬編碼 12，不隨
> `roster_count` 縮放），則即使隊伍真的有 20+ 人，這個畫面本身也永遠只能
> 顯示/選取 12 個欄位，19（或 15）的目標依然湊不滿，等於推翻上一段的
> (c) 結論。但該輪唯一測試過的存檔 roster_count 剛好也是 13（`roster_count
> -1=12`），跟「渲染固定 12」這個數字重合，**兩個假說（渲染上限=roster_count
> -1 的動態值，恰好這次算出12；或渲染上限=硬編碼常數12）在單一資料點下無法
> 區分**，doc58 本身從未在更大的 roster 上重測過。這是本輪認為唯一還沒閉合、
> 且可用一次乾淨測試（合成或真玩一個 roster_count≥15 的存檔進同一畫面，看
> 實際能否選超過 12 個）分出勝負的具體問題，本輪未嘗試 live 驗證（見
> `91-worklist.md` UI-VIS-PREPARATION 條目的誠實記錄）。
>
> **2026-08-26 續輪（`rostertest` harness，合成 26 人 roster，live DOSBox-X）：
> 「硬編碼 12」假說已被推翻，選滿確認流程已 live 驗證關閉**。用
> `tools/fd2save.py` 新增的 `build_join_record`/`append_roster_members`（逐位元組
> 複刻 production-verified 的 `native_join_constructor.go`
> `MaterializePersistentUnit`）把機器上真實 `~/fd2-run/FD2.SAV` slot0（13 真人
> roster）擴充成 26 人（新增 13 個各自不同、欄位精確的角色 record，不是
> record0 複製品——這正是 writerfire 輪「roster_count 硬改到 19 觸發疑似
> 完整性檢查、靜默彈回標題」失敗手法的對照修正），chapter 設 raw `0x1b`(27，
> `>0x1a`門檻，cap=19)。LOAD 該槽、FDTXT `0x19a` 按 **No**（見下方誠實限制）
> 後直接進選人畫面：**25 個 portrait 全部渲染**（10+10+5 三列，
> `roster_count-1=25`≠12），`roster_count-1` 動態上限假說證實成立，doc58
> 續十一「渲染固定 12」的字面假說被推翻——該輪測到的 12 只是巧合等於當時
> 唯一存檔的 `roster_count-1`。逐次 Enter 選取 5→12→19，每步「剩餘人數」
> 正確遞減，**選滿 19 後畫面自動跳出全新「確定要進入戰場嗎？」YES/NO 最終
> 確認框**，按 YES 正常進戰前過場對白（索爾「這裏就是黃金城嗎？」），沒有
> 卡住/錯誤——選人核取/`0x320fc`重排/`0x31d3c`最終確認三段，選滿19人這條
> 路徑本輪視為 E2 關閉。**誠實限制**：只測了 cap=19（raw>26）這一臂，cap=15
> 臂未測；用同一份合成 roster 對「No」分支武裝的 300M 指令 LOGC 追蹤（涵蓋
> No 確認到最終確認到過場對白全程）對 writer `0x2ff01`/`0x30012`/兩個已知
> caller/其 dispatcher 依然**全部零命中**，這是本節「整備限定流程走 No 分支
> 不呼叫 writer」結構性主張至今最乾淨的一次直接印證（不是像 writerfire 那輪
> 連選人畫面本身能不能選滿都不確定）。另一輪按 Yes 分支則確實觸發真實磁碟
> 寫入（slot1 變成 slot0 的逐位元組複製品），但遊戲隨後回到標題 LOAD 選單
> （不是進選人畫面），推翻本節先前「Yes/No 兩臂都進 0x318ad」的假設——No 才是
> 唯一通往選人畫面的分支；這個 Yes 分支的 LOGC 追蹤命中的是已知的 tavern
> icon1 writer `0x2968d`，不是 `0x2ff01`，但因為按鍵序列本身混雜多次重試、
> 不是乾淨單一路徑對照組，此一具體結論信心較低，留給下一輪用乾淨的單一動作
> 序列重新驗證。完整過程、截圖與 `test_fd2save.py` 新增的 known-answer
> regression 見 `91-worklist.md` UI-VIS-PREPARATION／UI-VIS-LOAD 兩個條目
> 2026-08-26 續輪段落。**下方 2026-08-26（`cleanretest` harness）續輪已用乾淨
> 單一動作重測，`0x2968d` 這個具體結論成立且信心已提升為高，但「回到標題
> LOAD 選單」與「已發生真實寫入」這兩個周邊敘述都需要修正，見下方完整記錄。**
>
> **2026-08-26 續輪（`cleanretest` harness，獨立全新 registry/Xvfb `:199`，
> 啟動前用 `tmux ls`/`ps` 確認無殘留 instance，結束後 teardown 乾淨）：
> 用乾淨單一動作重測 Yes 分支，`0x2968d` 命中已確認、寫入未命中已確認、
> 周邊兩個舊敘述已修正**。存檔合成沿用上一輪同一組 13 個新角色 id
> （`14,17,3,15,18,16,21,7,25,28,24,23,22`）以 `append_roster_members()`
> 疊加到真實 `~/fd2-run/FD2.SAV` slot0（13 真人 roster），
> `set_slot_chapter(0, 0x1b)`（raw 27，對應「第二十八章」）；
> `tools/fd2save.py --out` round-trip 自檢通過。全新 boot 後逐步 screenshot
> 確認狀態（title→`Down`→`Return`（開 LOAD）→`Return`（選 slot0，清單顯示
> 「1)第二十八章 探索者」）→直接顯示 FDTXT `0x19a`「要記錄戰況嗎？」，與上一輪
> 觸發點截圖一致，[`cleanretest-fdtxt-0x19a-record-battle-confirm.png`]
> (../figures/cleanretest-fdtxt-0x19a-record-battle-confirm.png)）。**本輪只做
> 一次動作**：`enter-debugger`（Alt+Pause）→`dosbox_exec_trace.sh arm`（LOGC
> 3 億指令）→單一次 `xdotool key Left Return`（選 YES）→不再送任何鍵，等
> LOGC 跑滿 3 億指令自動收工，全程未重試、未混入其他 slot 操作。
>
> **交叉核對結果**：
> - **`0x2968d`（`FUN_0002968d`）確實命中**，且不只是位址命中——完整
>   `disasm`（`ghidra_batch_probe.py`）逐指令核對，前 0x85 bytes 與本節上方
>   savewriter 輪已記錄的 tavern icon1 writer 讀取序列逐位元組相同結構
>   （`PUSH 0x38`→`CALL 0x3702f` alloc→`PUSH 0x59cb`→`CALL 0x3706e` alloc
>   buffer→push `"rb\0"`/`"FD2.SAV\0"`（`0x50251`/`0x50254`）→`CALL 0x37324`
>   fopen→`TEST EAX,EAX`/`JZ 0x296ee`→（存在時）`CALL 0x373ca` fread(buf,1,
>   `0x59cb`,fh)→`CALL 0x4df28` transform decode）——**這不是巧合撞位址，是
>   同一個 482-byte 函式（`0x2968d..0x2986e`）真的被完整執行到讀取階段**。
> - **`0x2ff01`/`FUN_0002ff01`（舊稱 `0x30012`）、其內部呼叫 `0x2d80d`、兩個
>   已知 caller（`0x1d43c`/`0x15400`）、其外層 dispatcher（`0x18890`/
>   `0x18d8c`/`0x15311`/`0x1cff0`/`0x13a9f`/`0x14ef0`）全部零命中**——與
>   `rostertest`/`camproute`/`writerfire` 歷輪一致，再次確認舊假設在這條路徑
>   上不成立。
> - **新發現：`0x2968d` 這次不是經由已知的 tavern dispatcher 鏈
>   （`0x29300`/`0x2670e`）呼叫的**——對 `0x2968d` 做 `xref_to` 找到全 EXE
>   只有兩個直接呼叫者：`0x2940e`（位於已知的 `FUN_00029300` 酒店 icon
>   dispatcher 內部，tavern icon1 路徑用這個）與**`0x26331`（位於
>   `FUN_00026152`——即本文件/`91-worklist.md` UI-VIS-TOWN 條目已記錄的
>   「town-hub 主迴圈/redraw 函式」內部，先前只知道它在 Enter/Space 時呼叫
>   `FUN_0002670e` 進 town-hub 選單，這個直接呼叫 `0x2968d` 的分支是本輪新
>   定位、先前未記錄的第二條路徑）**。本輪 LOGC 命中集合直接證實走的是
>   `0x26331` 這條（該位址與其前 16 個連續位址 `0x262f1..0x2632f` 均命中，
>   `0x2940e`/`0x29300` 零命中）——也就是說「整備限定流程」（跳過城鎮 hub、
>   直接顯示 `0x19a`）的 Yes 分支，是 `FUN_00026152` 內部一個獨立分支直接呼叫
>   存檔函式，不經過酒店 NPC 對話框那條 dispatcher 鏈，兩條路徑最終共用同一個
>   `0x2968d` 實作，但呼叫點不同。
> - **`FD2.SAV` 全程未變**：`md5sum`/`stat mtime` 在按鍵前後、以及 3 億指令
>   LOGC 完整跑完後，三次採樣完全相同（`1499a9ad12877e83238162db6acff922`，
>   mtime 停在 harness 複製檔案當下，不是按鍵後的時間）——**本輪沒有發生任何
>   真實磁碟寫入**，修正上一輪（混雜多次嘗試）「Yes 觸發真實寫入」的敘述。
> - **畫面「回到標題 LOAD 選單」的敘述需要修正，不是真的回到標題畫面**：
>   按 Yes 後螢幕確實顯示與標題 LOAD 選單外觀相同的四槽清單
>   ([`cleanretest-yes-branch-slot-picker-after-confirm.png`]
>   (../figures/cleanretest-yes-branch-slot-picker-after-confirm.png))，但
>   逐指令 disasm 證實這其實是 **`FUN_0002968d` 讀完檔案後，自己在 offset
>   `0x85`（`0x29712`）呼叫的內部目標槽位選擇器 `FUN_00029bcb`
>   （`0x29bcb..0x29da9`，479 bytes，獨立函式，`CMP EAX,-1` 判斷取消/Escape）**
>   ——程式仍在 Yes 分支的存檔流程內部，停在「請選擇要覆寫的存檔位」這個互動
>   輸入迴圈，**不是**跳出存檔流程回到 title 畫面重新進 LOAD；兩者視覺上用的
>   是同一個四槽清單 UI，只有讀 disasm 才分得出來。函式本體同一份 disasm
>   顯示，真正的 checksum（`0x4df09`）/寫入用 transform（`0x4df28`）/fwrite
>   鏈這段程式碼確實存在於 `0x2968d` 函式更後段（offset `0x11a`
>   起，`0x297ae`），只是要等 `FUN_00029bcb` 這個互動選擇器**真的收到一次槽位
>   選擇**才會執行到——本輪刻意只送一次 Yes 確認鍵、不再送任何後續鍵，所以
>   停在選擇器等待輸入的狀態，合理解釋了為什麼寫入沒發生。
> - **這也回頭解釋了上一輪的「確實真實寫入」為什麼會發生，不是互相矛盾**：
>   上一輪按鍵序列混雜多次嘗試，很可能除了選 Yes 之外還額外按了一次確認鍵
>   落進這個槽位選擇器並選中了某一槽，才觸發後段的 checksum/transform/fwrite
>   ——兩輪其實觀察到的是同一個函式的不同階段，不是兩個衝突的發現。
>
> **修正後的結論（本輪視為已關閉，信心高）**：「要記錄戰況嗎？」Yes 分支呼叫
> 的是 `FUN_0002968d`——與已獨立確認過的 tavern icon1 存檔 writer **同一個
> 函式**，不是舊假設的 `0x30012`/`FUN_0002ff01`；但這次是經由先前未記錄的
> `FUN_00026152`（`0x26331`）直接呼叫，不是經由酒店 icon dispatcher。Yes 本身
> **不會無條件寫入磁碟**——它會先讀入既有 `FD2.SAV`，再開啟一個與標題 LOAD
> 選單外觀相同、但其實是這個存檔函式自己的四槽目標選擇器，等玩家真的選定一個
> 槽位之後，同一函式後段的 checksum/transform/fwrite 才會執行，產生真實寫入
> （這部分沿用上一輪已觀察到的行為，本輪未重新觸發，誠實列為下一輪可低風險
> 補測的下一步：在這個選擇器上再按一次 `Return` 選 slot，確認出現「記錄
> 儲存完畢！」文字且 `FD2.SAV` 這次真的改變）。**No 分支**維持
> `rostertest` 輪已用同樣乾淨方法論確認的結論不變：直接進選人畫面，全程對
> `0x2968d`/`0x2ff01` 兩條鏈皆零命中。

**原版機制**(既有證據見 doc23 §"save storage boundary"、`56-fd2-remake-sdd.md`
UI-12、`91-worklist.md` L252/L260/L261/L1145)：

- 存檔 writer `0x30012` 全 EXE**只有兩個呼叫者**：`0x2ccb6`(經城鎮 hub
  `0x2cad7` 選項2「要進入戰場嗎？」confirm 之後)與 `0x2fd93`(經酒店/整備
  流程 `0x2fc85` 分支)。兩者都落在**戰後過場結束到下一戰整備畫面之間**
  的「戰間」流程內；全 EXE 主戰鬥迴圈(`0x10010` 起)沒有第三個
  `0x30012` caller，因此**原版在戰鬥進行中無法存檔**——不是 UI 隱藏了
  選單，是函式從未被接進戰鬥狀態機。
- `0x2cad7` 依 `byte[chapter+0x526b9]` gate table 分流兩條路徑，兩者互斥
  (已用 Docker 讀出 raw table：index `22..24`/`27..29`=1，其餘 town 範圍
  =0)：
  - **城鎮流程**(`0x526b9[index]==0`，對應 raw chapter 1..21/25..26)：
    先進城鎮 hub(`[0x5412b]` option0/1/3/4 分別是酒店/商店家族/教會，
    option2 才是存檔/整備入口)，Enter 後先顯示 FDTXT「要進入戰場嗎？」
    confirm，接受才呼 `0x2ccb6→0x30012`，再進 `0x318ad` 整備。
  - **整備限定流程**(`0x526b9[index]!=0`，對應 raw chapter 22..24/27..29
    即顯示章節23-25/28-30)：跳過城鎮 hub，直接顯示 FDTXT `0x19a`
    「要記錄戰況嗎？」；Yes 才呼 `0x30012(0)`，No 則略過存檔；兩臂之後
    都進 `0x318ad` 整備。
- LOAD(reader `0x2602c..0x26098`)只能從標題畫面四槽 selector 觸發；選定
  非空槽後，先複製 `0xa00` roster、再載 metadata `+0..+9`(chapter/roster
  count/currency 等)，接著**照樣重新進 `0x2cad7`** 用存檔章節決定回城鎮
  或整備——回讀路徑本身也不繞過「戰間」邊界，證實存檔內容本來就只代表
  一個戰間節點，從不代表任何戰鬥中途狀態。整個 `0x59cb` envelope(rolling
  XOR `0x4dbd8`、checksum `0x4dbb9`)裡沒有任何回合數/地圖/單位位置欄位。

**社群修改表「隨時存檔」對照**：修改表列的是繞過上述兩個呼叫點限制、
讓玩家能在戰鬥中或任何畫面觸發存檔的 patch；這反向證實原版預設規則正是
「只能在戰間兩個固定點存檔」，兩者互為肯定/否定證據，無矛盾。

**remake 現行對照**(`remake/cmd/fd2/save.go`)：

- `saveGameToSlot`(L70-103)已有一條 guard(L75)：node 是 `cutscene` 型別
  且(有 `HandlerBinding`+進行中 `g.st`，或 node ID 以 `postbattle_` 開頭)
  時拒絕存檔，訊息「戰後演出進行中，請在下一個節點存檔」——這對齊原版
  「戰後過場本身不能存檔，要等進到下一個節點(城鎮/整備)」的邊界，已有
  `TestSaveRejectsUnboundPostbattleBoundary`(`91-worklist.md` L119)。
- **差距**：guard 只檔 `cutscene` 型別節點，**沒有檔 `battle` 型別節點**
  (即實際戰鬥進行中的 `battle_chNN`)。目前 F5(`main.go` L6511-6512)在
  `battle_chNN` 節點會直接呼叫 `saveGameToSlot`，因為 `saveData`(L55-66)
  本來就不序列化 `g.st`(battle.State：單位/回合/寶箱)，所以存檔本身不會
  寫壞任何東西，但會建立一個「看似成功」的存檔——讀檔後只會把該 `battle_
  chNN` 節點**從頭重跑**，玩家在該場戰鬥內已推進的任何進度(含已開的寶箱、
  已行動的單位)全部消失且沒有警告。這與原版「戰鬥中完全不存在存檔路徑」
  的行為不同：原版玩家永遠不會誤觸一個會導致戰鬥重來的存檔，remake 玩家
  可能會。

**可編輯規則**：`SaveAllowedAtNode(nodeType, nodeID, hasActiveBattleState)`
只在下列情況回傳 true——node 不是 `battle` 型別，且不是進行中的
`postbattle_*`/handler-bound cutscene；即存檔只允許發生在「戰間」邊界
節點(town/preparation/shop/church/其他非戰鬥選單)，對齊原版 `0x30012`
兩個呼叫點皆位於戰間流程、戰鬥迴圈內不存在第三個呼叫點的事實。

**建議 regression 方向**：新增
`TestSaveRejectsDuringActiveBattleNode`——在 `battle_chNN` 節點、`g.st`
非 nil(模擬戰鬥進行中，可選擇先 `ClaimTreasure` 讓某格寶箱進入已開啟
狀態)時呼叫 `saveGameToSlot`，斷言回傳訊息與 `TestSaveRejectsUnboundPost
battleBoundary` 同構(拒絕存檔，不產生檔案)，而不是目前的「靜默寫入一個
會重跑整場戰鬥的節點邊界存檔」。這會把 guard 從「只擋 cutscene」擴大成
「戰鬥迴圈內完全比照原版無存檔路徑」，同時關掉一個目前使用者不會被告知
的資料遺失面。

### 9.2 寶箱持久化(chest)：戰鬥內部才存在的旗標，本來就不進 `FD2.SAV` [驗]

**原版機制**(既有證據見 doc25 §6.3、`91-worklist.md` L453/L1619、
`SESSION-HANDOFF-2026-07-06.md` L630/L2224/L2333)：

- 「已開啟」旗標存在**戰鬥期間才配置的 heap block** `[0x53AD5]`：
  main 以 `malloc(0x20)`(32 bytes)取得，初始化端 `0x10322` 複製 32 bytes
  進該 buffer(29 章開場共用)，事件路徑以 `0x13d00` 按 index 寫入單一
  byte。這是「battle-local event state table」，不是全域存檔欄位。
- 具體案例 map25 event58(五選一寶物，邏輯本體位於 `0x35854`——**不是**先前記錄的
  `0x354FE`；`0x354FE` 已由 doc25 §11.7(2026-08-24) 確認是 `0x51b91` 跳表 event58
  槽位的真實登記值，但落在 event57 handler 自己的指令中段，是 table artifact，
  與本段邏輯無關；`0x35854` 目前查無已知呼叫者，真正 runtime 觸發路徑待考證)：先以
  `0x1B8A6` 檢查行動單位八格 raw inventory 是否已滿(滿了只顯示 FDTXT `0x1E0` 並
  返回，不改任何 opened state)；否則 `0x12E38` 讀目前寶物 slot，以 slot
  索引 EXE 常數表 `0x5274E`(`[0x1D,0x2B,0x33,0x3D,0x47]`)取得物品，
  `0x1BB8C(unit,item)` 寫入後，**把 `[0x53AD5]+0..4` 全部設為 1**——即
  五個寶箱位置共用同一組「已選」旗標，拿走其中一個會讓其餘四個同時失效
  (不是各自獨立的 opened bit)。
- 這個 32-byte table 與另一張表不同，不要混淆：`[0x53A55]` 是**目前戰鬥
  的即時 FDFIELD control 快照**(含 16 筆 turn events、16 筆 field
  events、16 筆 chest controls 各 3B，`ContinueFieldControlView` 已拆解)，
  `0x19357` 會在戰鬥中更新其中的「chest value」(寶箱**內容值**，例如換成
  另一種獎勵)，這是內容/獎勵表，不是「已開啟」旗標本身。
- **關鍵事實**：`0x59cb` 存檔 envelope 的 reader/writer(`0x2602c..
  0x26098`/`0x30012`)只處理 metadata `+0..+9` 與 `0xa00` persistent
  roster，**完全不觸碰 `[0x53AD5]` 或 `[0x53A55]`**。這不是遺漏，而是與
  §9.1 的存檔邊界一致自洽：存檔只能發生在戰間(玩家已經離開該張戰鬥地圖)，
  而每張戰鬥地圖在整個戰役流程中只會造訪一次(33 張圖對應 30 章戰役，無
  「回頭重新踏上同一張地圖」的路徑)，所以「寶箱開啟狀態要不要跨存檔持久」
  這個問題在原版設計裡根本不會發生——旗標只需要在**同一場戰鬥的生命週期
  內**存在，戰鬥結束(無論勝負或存檔)那個 heap block 就跟著整場戰鬥狀態
  一起消滅，不需要也没有被序列化。

**社群修改表「寶箱持久化」對照**：修改表列的 patch 效果推測是讓玩家能重複
拿取同一寶箱(例如重讀已存檔但寶箱曾被拿過的進度後箱子又出現)，這與上一段
「旗標本來就不跨存檔」的結論一致——如果原版真的不持久化，玩家會觀察到
「重讀檔寶箱又出現」的現象，因為 `[0x53AD5]` 每次進戰鬥都由 `0x10322`
重新初始化，不是從存檔恢復；「持久化」修改表想解決的正是這個(對某些玩家
而言不理想的)预设行为，而不是修正一個記憶體 bug。

**remake 現行對照**(`remake/internal/battle/model.go`)：

- `State.OpenedTreasure map[int]bool`(L600 附近)明確標註為「remake-owned
  editable treasure state」，每次 `battle.Load` 建構新 `State` 時固定
  `OpenedTreasure: map[int]bool{}` 全新配置(L939-940)，行為對齊
  `0x10322` 每戰重新初始化的事實。
- `ClaimTreasure`(L751 起)一般格寶箱設 `s.OpenedTreasure[t.Slot]=true`
  (單槽獨立)；`claimNativeTreasureEvent`(L778 起)處理 event58 這類
  native rule 時，對 rule 定義的所有共享 slot 都設 true(L798)，已有
  regression `TestMap25NativeEventTreasureUsesEditableEvent58Rule` 驗證
  五個 slot 會被同時關閉，對齊 `[0x53AD5]+0..4` 全設 1 的原版行為。
- `remake/cmd/fd2/save.go` 的 `saveData`(L55-66)**沒有**任何寶箱/treasure
  欄位，因此 `OpenedTreasure` 本來就不會被寫進存檔——這與原版「寶箱旗標
  不進 `FD2.SAV`」的結論一致，是正確的對齊，不是遺漏。

**可編輯規則**：`OpenedTreasure` 的生命週期綁定「單場戰鬥的
`battle.State` 實例」，不綁定「campaign 存檔邊界」；規則本身已經是
remake 現狀，此處把它從「隱含行為」提升為**明確不變式**：
1) `battle.Load` 必須在每次建構 `State` 時重置 `OpenedTreasure` 為空；
2) `saveData`/campaign 存檔格式必須永遠不含 treasure/chest 欄位；
3) native event rule(如 event58)的「共享槽位」語意必須逐 rule 明確列出
   受影響 slot 集合，不能假設所有寶物槽互斥。

**建議 regression 方向**：
- 新增 `TestOpenedTreasureNotSerializedInSaveData`(可放在
  `remake/cmd/fd2/save_test.go`)：對一個已 `ClaimTreasure` 過的
  `battle.State` 觸發 `saveGameToSlot`，反序列化寫出的 JSON，斷言其中
  不存在任何 treasure/chest 相關 key——把「現狀正確」釘成不會被未來改動
  意外打破的不變式(目前只是結構上沒有欄位，沒有主動測試防止有人以後
  加欄位卻忘記排除戰鬥中途狀態)。
- 新增 `TestBattleLoadResetsOpenedTreasureAcrossInstances`：對同一張
  map 呼叫兩次 `battle.Load`，在第一個 `State` 上 `ClaimTreasure` 後，
  斷言第二個新建的 `State.OpenedTreasure` 是空的——把 `0x10322`「每戰
  重新初始化 32 bytes」的事實提升成可重複驗證的回歸，防止未來有人為了
  「玩家體感」誤把 `OpenedTreasure` 挪進 campaign 持久層。

### 9.3 worklist L848 完成度

本節完成 `91-worklist.md` 第848行「先挑 save/chest 兩項」範圍：save(隨時
存檔)與 chest(寶箱持久化)兩項的原版機制已有反組譯位址佐證(§9.1/§9.2)，
並各自轉成可編輯規則(`SaveAllowedAtNode`／`OpenedTreasure` 生命週期不變式)
與具體 regression 測試方向(尚未落地成測試碼，只完成規則設計與 test 命名/
斷言描述)。第848行其餘兩項——「入隊」(入隊 ID/條件)與「等級上限」——
不在本輪範圍內，留待後續 session。

#### 2026-08-19 補充：入隊／等級上限跨文件盤點(worklist L848 掃描)

重新盤點後發現這兩項在其他 doc 已有實質進展，只是§9.3寫作時未交叉引用；
本節只做跨文件核對與規則化，未新增反組譯：

- **入隊(JOIN)機制本身已完整閉合**：`0x112a5(join_id)` = JOIN constructor
  (`sub_112A5`)，把新成員寫入 `[0x53bf7]+count*0x50` 的 persistent record(`+7=+8=join_id`)
  並遞增 `[0x53bfb]`；`remake/internal/campaign/native_join_constructor.go`
  (`MaterializePersistentUnit`)＋schema 綁定的 `native_join_constructor.json`(32-row，
  含 FD2.EXE MD5/SHA256 驗證)已把這條路徑做成通過回歸(`TestNativeJoinConstructorMaterializesAllKnownRows`)
  的可編輯規則，見 doc26 §7.2、doc31、doc40 §「玩家初始 record 的狹窄例外」。
  **仍未閉合的是「哪一章、哪個 handler 呼叫哪個 join_id」這個逐章 ID/條件表**——
  這不是單一位址就能收斂的規則，而是隨每章 postbattle/pre-battle handler 解碼
  逐步累積(doc26 §1、doc47、doc56 L2190/L2502 已各自記錄部分 chapter 的 join_id/條件，
  例如 ch00 開場 `0x112a5(0/9/4/0x1e)`=索爾/悠妮/亞雷斯/蓋亞、ch16 `roster_has(18)`
  對應 JOIN18)。「入隊」因此不是一項可一次關閉的任務，而是隨 doc57 UI-07 postbattle
  逐章稽核自然收斂的副產品，不建議再開一個獨立 worklist 項目追蹤。
- **等級上限機制核心已由另一輪(worklist 245/266，doc58 續二十九，2026-08-19)反組譯**：
  `0x1e292` 的職業等級上限特例—`cVar1(actor+7)==0x1e/0x1f→99 上限`，否則`40 上限`—
  已記載於 doc27 checklist item15/#5(`0x1e292` 完整經驗值/升級迴圈)。**這才是「等級上限」
  的原生 gate**，不需要另外從頭反組譯。仍缺兩件事(doc27 明列，非本節新發現)：
  (a) `cVar1` 完整對應哪些角色/職業(機兵→99 之外，社群攻略提到的「80」第三層級
  在 `0x1e292` 目前只看到兩種分支，未證實存在第三分支，可能是社群近似值而非原生規則)；
  (b) remake 尚未把這條 gate 接成執行規則(`growth.go` 目前門檻只有「100 經驗一級」，
  沒有 class-specific cap／達上限經驗歸零)。**可編輯規則草案**：
  `LevelCapFor(classByte) = 99 if classByte in {0x1e,0x1f} else 40`；
  `if level>=cap: exp=0`(不繼續累加，對照 `0x1e292` 的 `while(local_18>99){...若達上限則local_18=0}`)。

因此 doc25§9.3「不在本輪範圍內」的措辭已過期：入隊機制與等級上限機制的**原生
mechanism 本身均已有反組譯佐證**，殘留缺口分別是「逐章 join_id 表」(持續累積中，
非獨立任務)與「class→cap 完整對應表 + remake 執行接線」(doc27 已追蹤，非本節新開)。

## 10. 2026-08-20：全域事件表 58..89 剩餘 handler 高階語意初步稽核（回應 worklist L212）

> worklist 91 稽核索引第212行：「REMAKE-GLOBAL-EVENT-DISPATCH 的 58..89 handler 高階語意
> 仍待逐一靜態反組譯」。§6.1 已證實全域事件表 `0x51b91` 共 90 entries（0..89），§6.4／
> §6.1.1／本文件其他小節已個別閉合 58／59／60／61／63／82（見上方各節）；本節對其餘
> 26 個 handler（62／64..81／83..89，扣掉已閉合的 6 個）做第一輪嘗試，方法與誠實的
> coverage 邊界如下。

**方法與已知限制**：`tools/extract_event_id_groups.py` 原本就是靠 basic-block walk（不是
線性掃）取得每個 handler 的 `spawn_group` 呼叫，`docs/data/event_id_groups.json` 已對
event_id 58..89 全部記錄 handler 入口位址（見下表）。本節新增
`ProbeGlobalEvents58to89.java`，直接對這 26 個入口位址呼叫 Ghidra `createFunction` +
`DecompInterface` 取高階 C 偽碼——但**用的函式邊界是「下一個 event_id 的入口位址」，
不是 Ghidra 自己認可的真正函式邊界**（成功案例是因為剛好對齊；失敗案例代表下一個
handler 的入口其實落在共用尾段、跳表 fallthrough 或另一個既有函式內部，不是獨立
函式起點）。這個方法對本表約半數 entry 給出乾淨、無暫存器殘留警告的偽碼，另一半
出現 `unaff_EBX`/`unaff_EBP`/`halt_baddata` 等 Ghidra 邊界錯誤訊號——後者**不代表該
handler 沒有語意**，只代表本次用的邊界猜測法在那個位置不成立，需要未來比照
`extract_event_id_groups.py` 的 basic-block walk（而非位址差）才能可靠展開。完整
原始 decompile 輸出（含失敗訊息）存於
[`fd2_global_events_58_89_decompile_2026-08-20.txt`](../data/fd2_global_events_58_89_decompile_2026-08-20.txt)。

### 10.1 乾淨結果（無邊界警告，[驗]）

| event | handler | 高階語意 |
|---:|---|---|
| 67 | `0x35a2f` | `0x1956B()`(確認?) → `0x2AEDB()`；回傳 -1 直接關閉退出。否則：`0x1B8E7()` → 畫面 → `0x111BA()`(資源載入) → **59 次迴圈**(`0x2EB9F`+`0x17AA9`，與 §6.4 event61 用的「resource45 59-frame 演出」同構) → `0x3776E()` → `[0x53AD5+0xC]=1`(battle-local event-state byte，index 12) → `0x12263()` → `0x10B4E()`(**spawn_group**) → `0x112A5()`(**JOIN constructor**，見 §9.3 2026-08-19 補充) → 畫面。**這是與 event61 同一種「59幀演出→spawn→JOIN」組合技的另一個 handler**，多了前置的 `0x2AEDB` 條件檢查（可能是「持有特定道具/旗標才觸發」的 gate，本節未展開 `0x2AEDB` 本體）。 |
| 69 | `0x35ab8` | 與 event67 幾乎相同的尾段（`0x111BA`→59次迴圈→`0x3776E`→`[0x53AD5+0xC]=1`→`0x12263`→`0x10B4E`(**spawn_group**)→`0x112A5`(**JOIN**)→畫面），但**沒有** event67 開頭的 `0x1956B`/`0x2AEDB` 條件檢查——即「無條件版」的同一組合技。兩者共用 `[0x53AD5+0xC]` 這個 battle-local 旗標，語意上應是彼此互斥或依序消耗的同一組事件狀態（比照 §9.2 已知的 `[0x53AD5]` battle-local event-state table 慣例），但本節未證實兩者實際會不會出現在同一張地圖。 |
| 76 | `0x35d60` | 只有 `0x15F84()`(畫面繪製) 然後返回——目前已知 primitive 裡最簡單的一種，近似 no-op 的畫面刷新，沒有 spawn／JOIN／狀態寫入。 |
| 78 | `0x35ed2` | `if (某條件!=0) { 0x15F84(); func_0x00035F10(); }` 之後固定 `[0x53AD5+0x13] += 1`(battle-local byte, index 19)。條件運算式本身因為函式邊界猜測受寄存器殘留干擾（`in_CF` 未定義輸入），不可信；但「若條件成立則畫面+呼叫某 helper，然後固定遞增 index19」這個骨架可信。`func_0x00035F10` 本體未展開。 |
| 84 | `0x360c0` | **多階段、自我重排程的計數器 handler**：`if ([0x53AD5+0x11] != 4) { 0x13512()(標記目前行動單位已行動) ; [0x53AD5+0x11]+=1 ; [0x53A55+3]=[0x53BEF]+1 }`（**`[0x53A55+3]` 正是 §6.1 已證實的 turn_events[0].turn 三位元組欄位**——即這個 handler 每次觸發只是把「下一次觸發」排到下一回合，同時假裝目前單位已完成行動）；**第 4 次觸發時**才走另一分支：畫面→`0x10B4E()`(**spawn_group**，未展開帶哪個 group 常數)→`[0x53AD5+0x15]=單位總數-3`→`[0x53A55+9]=[0x53BEF]`→兩次 `0x361B0()`+等待→迴圈3次 `0x361B0()`+畫面。**這是一個「連續 4 回合、每回合觸發一次，第 4 回合才真正 spawn 支援」的倒數機制**，與 §6.1.1 已知的「`group=turn/2`」「`group=turn`」兩種公式屬於同一「回合數驅動延遲增援」設計母題，但實作方式是自我重排程的計數器，不是單一算式。event84 是 §6.2 已列的「格子實際引用的 58 以上 event_id」之一，所以這個倒數機制大機率是某張地圖上「站上某格、連續 N 回合後才召喚援軍」的觸發器；哪張地圖、哪個格子仍待對照 `native_field_event_slots`。 |

### 10.2 部分可信（邊界警告存在，僅尾段/局部語意保留，[推]）

| event | handler | 可信片段 |
|---:|---|---|
| 65 | `0x3599b` | 尾段 `if (unit[param_4]+6 != 0) call func_0x000344F2()`——**讀取單位 raw camp byte(+6，doc11 既有定義)並在非 0（非敵方）時呼叫一個未展開的函式**；前段因邊界猜測產生暫存器殘留假象，不採信。`func_0x000344F2` 本體未展開（可能是 overlay 區呼叫，比照 doc11 task#98 已知的「`0x73A7A` 等 overlay 位址無法靠純靜態展開」限制）。 |
| 74 | `0x35c32` | `push 2; push 0x1B; call func_0x00035B78()`——固定以兩個字面常數 (`0x1B`=27, `2`) 呼叫一個未展開的 overlay 函式，可能是「給予/設定 27 號 item 或 flag，數量或型態 2」，但因 `func_0x00035B78` 本體不在目前 LE object 範圍內（overlay），無法進一步展開，本節不猜測。 |
| 75 | `0x35c79` | 尾段：呼叫 `func_0x00035B78()` 三次，`[0x51A83]=1`(既有：戰場輸入鎖旗標，本文件 L1038 端turn一節與 doc56 都用過)，`[0x53AD5+0x10] += 1`(battle-local byte, index 16)。前段暫存器殘留假象不採信。 |

### 10.3 未能展開（邊界猜測失敗，本節不下結論）

62／68／70／71／72／73／77／79／80／81／83／85／86／87／88／89 這 16 個 handler 這次
用「下一 event 入口位址」當邊界產生的偽碼含 `unaff_*` 暫存器殘留或
`halt_baddata`（Ghidra 判定該起點落在 bad instruction data），**不可信，未列入以上兩表**。
其中 85／86／87／88／89（對應的表列間距只有 7..24 bytes）高度疑似只是**共用尾段
fallthrough**（例如 event86 的 7-byte「handler」`*(unaff_EBX+0x11)+=1; [0x53A55+6]=[0x53BEF]+1;`
與 event84 第 4 次觸發前分支的最後兩行幾乎逐字相同——很可能 90-entry 跳表裡這幾個
slot 根本是指向另一個較大 handler 內部的共用出口，不是獨立函式），但這只是本節的
觀察推論，**未經 basic-block walk 或 xref 交叉確認，不升級為結論**。

### 10.4 2026-08-20 第二輪：basic-block walk 逐位元組定位（回應 §10.3 遺留的 16 個）[驗]/[推]

§10.3 的失敗根因**不是**「函式邊界猜測不準」這麼籠統——用 `getInstructionAt`+`.getNext()`
手動 basic-block walk（BFS：call 過站不進入、遇 RET/無條件 JMP 到別處才停，條件跳兩路都走，
與 `tools/extract_event_id_groups.py` 同一演算法，但直接在 Ghidra 資料庫上重放，因為
docker/capstone 環境已隨 2026-08-16 移除 Docker Desktop 不可用）搭配**逐位元組 hex dump**
（`getByte`，不經過任何反組譯器詮釋）比對後，找到一個可重現、可用位址證明的具體機制：

**這 16 個 event_id 在 `0x51b91` 跳表裡的 relocated 位址，有極高比例根本不是任何指令的
起始位元組——它們落在鄰近（通常是編號較小、已經解出的）handler 本體內部某條指令的
「中段」（ModRM/位移/立即值運算元的某個 byte）。** 這用 hex dump 可以直接、無歧義地證明：
取目標位址往前/往後各數十 byte 的原始 bytes，若能在其中辨認出「某條已知指令 X 的 opcode
起點在目標位址前 N byte 處，且 N+X 的指令長度剛好蓋過目標位址」，就證明目標位址是 X 的
操作數 byte，不可能是獨立進入點——這與 Ghidra 自己既有 976-函式分析對這些位址普遍回報
`getFunctionContaining()==null`／`halt_baddata`（=已經把該 byte 判定成別的指令的一部分，
拒絕在此重新起始反組譯）完全吻合，是兩種獨立方法給出的同一結論。

驗證用腳本：`ProbeGlobalEvents16BBWalk.java`(BFS walk)、`ProbeGlobalEventsRawBytes.java`／
`ProbeExtra.java`(hex dump)、`ProbeEvent67Walk.java`／`ProbeEvent84Walk.java`(鄰居 handler
的乾淨 walk，作為比對基準)，皆存於 `FD2_ghidra_projects/`，執行方式與既有
`reference_fd2_live_ghidra_headless_probe` 記憶一致（`-readOnly -noanalysis` + `-postScript`）。

#### 10.4.1 證實「落在鄰居 handler 內部、無獨立語意」（byte 級比對，[驗]）

先取 event67(`0x35a2f`)與 event84(`0x360c0`)兩個已由 §10.1 認證的乾淨 handler，各自重新
walk 出**真正**的逐指令位址表（見下方引用），再與 16 個目標的 hex dump 逐 byte 對照：

| event | 位址 | 落點 |
|---:|---|---|
| 68 | `0x35a48` | event67 自己的 `0x35a47: 83 C4 04`(ADD ESP,4，CALL 0x1956B 後的清棧)第 2 byte(`C4`)——並非新指令起點 |
| 70 | `0x35b05` | event67/68/69 共用 59 幀迴圈的 `0x35b04: 68 E4 BC 0A 00`(PUSH 0xABCE4，逐幀繪圖用的 resource id)第 2 byte |
| 71 | `0x35b6b` | 同一段共用尾聲 `0x35b67: FF 35 79 3A 05 00`(PUSH dword[0x53A79]，draw 呼叫前的最後一個引數)第 5 byte |
| 81 | `0x35f6f` | event80 自己的 `0x35f6e: C7 05 83 1A 05 00 01 00 00 00`(MOV dword[0x51A83],1)第 2 byte；9 byte 後即 RET |
| 85 | `0x360d8` | event84 自己的 `0x360d5: E8 38 D4 FD FF`(CALL 0x13512，即 doc 已載的「標記單位已行動」)第 4 byte |
| 86 | `0x360e3` | **恰好對齊** event84 自己的 `INC byte[EBX+0x11]`（`FE 43 11`）——是真指令邊界，但 EBX 未初始化：event84 本體要先執行 `0x360dd: MOV EBX,[0x53AD5]` 才設好 EBX，86 這個進入點跳過了那一步，若真被呼叫會對任意殘留 EBX 值做 `INC [EBX+0x11]`，即記憶體毀損，不像是設計上會被觸發的入口 |
| 87 | `0x360ea` | event84 自己的 `0x360e6: A0 EF 3B 05 00`(MOV AL,[0x53BEF])最後 1 byte |
| 88 | `0x360f1` | event84 自己的 `0x360ed: 8B 1D 55 3A 05 00`(MOV EBX,[0x53A55])第 5 byte |
| 89 | `0x360f8` | event84 自己的 `0x360f6: 83 C4 04`(ADD ESP,4)最後 1 byte，9 byte 後即 `POP EBX; RET` |

這 9 個（68／70／71／81／85／86／87／88／89）**沒有、也不可能有屬於自己的獨立高階語意**——
它們的「table entry」單純是 relocation 落在別人函式體中段的產物。這比 §10.3 原本「疑似
共用尾段但未確認」的推論更進一步：不只是**推論**，是**證實**（byte 級逐一比對，附精確
offset），也把 §10.3 對 85..89 的觀察從 [推] 升級為 [驗]，並新增 68／70／71／81 四個同類案例。

#### 10.4.2 有自己可讀出的具體行為（[推]，多數第一個位元組落在鄰居尾巴，但緊接著的本體乾淨自洽）

| event | 位址 | 行為 |
|---:|---|---|
| 62 | `0x35898` | 目標本身落在 `0x35895: FF 74 24 20`(PUSH dword[ESP+0x20])最後 1 byte，但緊接著 `0x35899: CALL 0x1B8A6`——與 event58 檢查行動單位八格 raw inventory 用的**同一個函式**。往回追溯（`ProbeExtra.java` 的 -120 byte 視窗）找到所在函式的乾淨序頭 `PUSH EBX,ESI,EDI; SUB ESP,0x10; ...; MOV ESI,0x5274E`——`0x5274E` 正是 §「event58：map25 五選一寶物」文件的同一張五格資源表；往後（本節較早的 BFS walk）也證實會以 FDTXT index `0x1E0` 顯示訊息，與 event58 記載的「inventory 滿時顯示的 FDTXT_000 `0x1E0`」逐字相同。**結論**：event62 是 event58「五選一寶物」機制在另一張地圖／另一套單位查找路徑下的平行副本（同演算法、不同 unit-record 讀取方式），不是同一份程式碼，但共用同一張資源表與同一句提示文字。**2026-08-24 更正(§11.7)**：event58 的登記位址 `0x354FE` 已確認是落在 event57 handler 中段的 table artifact，與這段「乾淨序頭 `PUSH EBX,ESI,EDI;...MOV ESI,0x5274E`」（即 `0x3585e`，緊接 `0x35854` 的 stack-probe 頭）完全無關——本列所稱「event58 機制」實際上就是**這一個函式本身**（`0x35854`），不是另一份「平行副本」；event58 自己的 table 槽位另外通到別處(event57)、與這裡描述的邏輯無交集。`0x35898`(本列 event62 登記位址) 是否真的是這個函式的入口、抑或本身也是落在其中某條指令中段的 artifact，本列原文已指出「往回追溯」才找到乾淨序頭，代表 `0x35898` 自己同樣疑似不是乾淨邊界起點——這點今天這輪未比照 §11.7 的標準重新驗證，留待後續。 |
| 72 | `0x35bf2` | 目標落在鄰近 `PUSH 0x4`（0x35bee 起）最後 1 byte，緊接 `CALL 0x3702F(arg=4)`（未展開的 overlay/helper，目標未解析）後即乾淨自洽：`MOV EAX,[0x53AD5]; CMP byte[EAX+0x11],0; JNZ +0x19（非0則跳到RET）; [若為0:] MOV DL,[0x53BEF]; INC DL; MOV byte[0x53A55+3],DL; MOV EAX,[0x53AD5]; MOV byte[EAX+0x11],1; RET`。即 event84 四回合倒數重排程機制的**單次版**（[0x53AD5+0x11] 當一次性旗標而非 0..4 計數器，把下回合排進 `turn_events[0].turn`（`[0x53A55+3]`）後就把旗標鎖住，之後再觸發直接 RET 不重複）。 |
| 73 | `0x35c23` | 目標落在鄰近一個 `CALL 0x3702F(arg=0x10)` 指令中段，緊接著乾淨自洽：`PUSH 1,0x1B,3; CALL 0x35B78; ADD ESP,0xC; PUSH 2,0x1B,0xF; JMP 0x3566E`（尾呼叫）。與 §10.2 已載的 event74（`push2;push0x1B;call 0x35B78`）、event75 是同一個「給予 item `0x1B`(27)」helper 家族的第三個變體（數量 3，尾呼叫帶 (2,0x1B,0xF) 三個引數到共用出口 `0x3566E`，與 event74/75 共用同一尾端）。 |
| 79 | `0x35ee6` | 目標落在 event78 自己 `PUSH 0x140` 指令（9-arg draw 呼叫序列的一部分）中段第 3 byte，緊接著的每個 byte 都與 event78「條件成立」分支逐一相同：`PUSH 0xA0000,2,[0x53A79]; CALL 0x15F84; CALL 0x35F10(arg=0x14); MOV EAX,[0x53AD5]; INC byte[EAX+0x13]; RET`。這證實（byte 級，非猜測）§10.1 原先對 event79 的推測——event79 就是 event78「必定執行、不檢查旗標」的版本，重入點精準落在 78 自己 `if` 判斷之後的 true 分支開頭附近。 |
| 80 | `0x35f5a` | 目標落在某 `CALL <give-item helper>(2,0x23,4)` 呼叫最後 1 byte，緊接乾淨自洽：`ADD ESP,0xC; PUSH 3,0x23,0xE; CALL <同家族 helper>; ADD ESP,0xC; MOV dword[0x51A83],1; RET`。與 event75 已載的「呼叫 `0x35B78` 系列 helper 數次 + `[0x51A83]=1`(戰場輸入鎖)」同一家族，這裡給予的是 item/flag `0x23`(35) 兩種數量(4、14)後鎖輸入。（event81 的「落點」即證實落在這個 `[0x51A83]=1` 指令中段，見 §10.4.1。） |
| 83 | `0x36088` | 目標落在鄰近一個 `MOV EAX,[0x53AD5]` 指令中段第 4 byte，緊接乾淨自洽：`MOV byte[EAX+0x11],1; MOV DL,[0x53BEF]; INC DL; MOV EAX,[0x53A55]; MOV byte[EAX+6],DL; MOV EAX,[0x53AD5]; MOV byte[EAX+0x10],4; MOV EAX,[0x53A55]; MOV DL,[0x53BEF]...`（超出本次 40-byte 視窗）。與 event72/event84 同屬「把下一次觸發排進某個 turn_events slot」家族，但這裡寫入的是 `[0x53A55+6]`（另一個 slot，不是 72/84 用的 `+3`）並額外把 `[0x53AD5+0x10]` 設成 4——確切是哪個 map/slot 觸發、`+0x10` 這個 battle-local byte 的完整語意，本節未展開，留待後續。 |

這 6 個（62／72／73／79／80／83）**取得了可引用位址、可讀懂的具體行為**，但因為緊鄰
handler 的真正起點多半只往回追了幾十 byte（未逐一重新驗證是否又落在「更前一個」
handler 的中段），標 [推] 而非 [驗]；其中 79 因為對照對象（event78）本身已是 §10.1
的 [驗] 結果，可信度最高。

#### 10.4.3 仍未解（[阻]，本節誠實承認）

| event | 位址 | 失敗原因（具體） |
|---:|---|---|
| 77 | `0x35ebe` | 目標落在一個 `JMP rel32`（尾呼叫）指令中段第 2 byte；往回 60 byte 的視窗看到這是一個**先前未記錄**、更大的多階段「給予 item type 7」handler 的尾端——依序 `PUSH id,7,qty; CALL <0x35B78 家族 helper>` 三次（引數組合 `(3,7,8)`、`(4,7,4)`、`(5,7,0)`，最後一組改用尾呼叫 `JMP` 到約 `0x35D56`），但**這個外層 handler 自己真正的入口位址本節沒有找到**（60-byte 視窗不夠，需要更長的回溯 walk，本節未做）。因此雖然「77 本身不是獨立進入點」這個結論成立（與 §10.4.1 同一現象），但沒有已知鄰居的「乾淨版本」可引用比對，不能像 68/70/71/81/85..89 那樣給出可信賴的精確位址佐證，故仍列為未解，而非證實共用。 |

### L212 完成度（2026-08-20 更新）

**本節（10.4）處理了 §10.3 列出的全部 16 個 handler，逐一都有明確結論**：

- **9 個（68／70／71／81／85／86／87／88／89）**：以 byte 級 hex dump + 已驗證鄰居的
  basic-block walk **證實**它們的 table 位址落在鄰居 handler 內部某條指令中段，不是獨立
  進入點、沒有屬於自己的語意——這是本節的核心新結論，把 §10.3 的「觀察推論」升級為
  [驗]。
- **6 個（62／72／73／79／80／83）**：取得可引用位址的具體行為描述（[推]），多與既有
  handler 家族（event58 五選一寶物、event72/84 turn 重排程、event73/74/75 給予 item、
  event78/79 條件繪圖）互為印證或擴充。
- **1 個（77）**：確認「非獨立進入點」但外層 handler 真正入口未定位，仍列未解。

**90 個 entry 累計**：先前 §6/§10.1/§10.2 已有具體行為描述的 14 個
（58／59／60／61／63／65／67／69／74／75／76／78／82／84）+ 本節新增 6 個
（62／72／73／79／80／83）= **20 個有具體位址佐證的行為描述**；另有 **9 個
（68／70／71／81／85／86／87／88／89）證實為共用鄰居代碼、無獨立語意**（這 9 個「解決」
的方式是證明它們不是真正的 handler，而非解出行為）；**1 個（77）**落點性質已知但外層
handler 未定位，仍未解；`64`／`66` 兩個 entry 在 §10 最早的範圍界定中被遺漏（26 個目標
只覆蓋到 24 個 + 本節 16 個，64/66 不在任一份清單內），不屬於本次任務範圍，留給後續
稽核；其餘 60 個（0..57 的 turn_events 子集）不在 L212 討論範圍內。

**下一步建議**：77 的外層 handler 需要更長距離的回溯 basic-block walk（本節 60-byte
視窗不足）才能定位真正入口；62/72/73/79/80/83 六個「[推]」項目若要升級為 [驗]，需要
對它們各自緊鄰的「上一個」handler 也做一次乾淨 basic-block walk 加以交叉確認（方法與
本節對 event67/84 所做的完全一樣，只是尚未對每一個都做）；64/66 兩個先前遺漏的 entry
建議與後續 event82-style 稽核一併排入。

## 11. 2026-08-24：58..89 殘留缺口(64/66/77)收斂 + 兩個共用原語解析 + 位址邊界方法論警示

> 回應 worklist L212 剩餘部分。§10 已處理 58..89 中 30 個(20 個有具體行為描述 + 9 個證實
> 「表項落在鄰居 handler 中段、無獨立語意」+ 1 個(77)落點已知但外層未定位)，但 §10 自己
> 承認「64/66 兩個 entry 在最早的範圍界定中被遺漏」——本節是這兩個 ID 第一次被觸碰。方法
> 與 §10.4 完全相同：`tools/ghidra_batch_probe.py`(disasm/decompile/bytes/xref_to/call_scan)
> 逐 byte 回溯，不假設表項位址就是真正指令起點。

### 11.1 event64：證實落在 event62 所屬大函式的尾端 tail-jump 位移運算元內 [驗]

`docs/data/event_id_groups.json` 記錄 handler=`0x358ea`。逐 byte dump(`0x358c0` 起 60 byte)
還原出的真實指令流，是 §10.4.2 已知的 event62 大函式(序頭 `0x3585e`)的延續：

```
0x358c2  push dword[0x53a7d]
0x358c8  call <sub> ; add esp,0x24
0x358d0  push 0 ; call <sub> ; add esp,4
0x358da  push 0 ; call <sub> ; add esp,4
0x358e4  call <sub>
0x358e9  jmp 0x35990            ; E9 A2 00 00 00
```

`event64` 註冊位址 `0x358ea` 正是這條 `jmp rel32`(操作碼 `E8` 在 `0x358e9`)位移運算元的
第 1 byte(4-byte 位移落在 `0x358ea..0x358ed`)。跳轉目標 `0x35990` 反組譯證實是
`ADD ESP,0x10; POP EDI; POP ESI; POP EBX; RET`——與 event62 大函式序頭
(`PUSH EBX,ESI,EDI; SUB ESP,0x10`)對稱的共用收尾。事件63 的註冊位址(`0x358c7`)也同樣
落在這段指令流中段(`PUSH dword[0x53a7d]` 的最後 1 byte)，這正是 §6.1 為何從未能靠
event63 自己的位址解出語意、必須改走「raw camp0/敵軍AI前 runner」路徑的 byte 級成因。

**結論**：event64 與 event63 相同，是「表項落在 event62 大函式中段」的產物，沒有獨立語意——
併入 §10.4.1「無獨立語意，byte 級證實」名單，成為第 10 個成員。

### 11.2 event65 完整函式(補完 §10.2 的 [推] 片段)、event66 落點與其執行路徑 [驗]/[推]

byte 級逐一回溯，找到兩個緊鄰、幾乎同構的完整函式：

**Function A**(event65 註冊位址 `0x3599b` 所在區段)，真正入口 `0x35997`：
```
0x35997  push 0x10 ; call 0x3702f         ; 標準輸入緩衝清理序頭
0x359a1  mov edx,[esp+4] ; eax=edx*0x50   ; 單位 stride 公式(shl 2;add;shl 4)
0x359af  mov edx,[0x53a45]                ; 單位陣列基底
0x359b5  cmp byte[edx+eax+6],0            ; 讀觸發單位 raw camp byte(+6)
0x359ba  jz 0x359ca                       ; ==0 直接跳過
0x359bc  push 0,0x2c,0x27 ; call 0x344f2 ; add esp,0xc
0x359ca  ret
```
`0x3599b`(event65 註冊位址)實際落在 `PUSH 0x10` 立即值的最後 1 byte——從那裡起跳會先產生
2 條垃圾指令，恰好在 `0x359a1` 重新對齊回真正指令流，這正是 §10.2 當時「尾段可信、前段
暫存器殘留」判斷的成因；現在補上完整、乾淨的函式全貌(`0x35997..0x359ca`)，把 event65 從
「尾段片段」升級為完整已知函式。

**Function B**(緊接在 Function A 之後)，入口 `0x359cb`：
```
0x359cb  push 0x10 ; call 0x3702f
0x359d5  mov edx,[esp+4] ; eax=edx*0x50
0x359e3  mov edx,[0x53a45]
0x359e9  cmp byte[edx+eax+6],0
0x359ee  jz 0x35a0c
0x359f0  push 0,0x18,0x17 ; call 0x344f2 ; add esp,0xc    ; 條件呼叫
0x359fe  push 0,0x38,0x35 ; call 0x344f2 ; add esp,0xc    ; 無條件呼叫
0x35a0c  ret
```

event66 註冊位址 `0x359c8` 落在 Function A 尾端 `ADD ESP,0xC`(`83 C4 0C`)的 ModRM byte，
**不是**任何函式的真正入口。但若字面上從 `0x359c8` 開始執行：bytes `C4 0C C3` 會被解碼成一條
(語意上應無害，只汙染 ECX/ES 段暫存器的)`LES ECX,[EBX+EAX*8]`，**恰好吃掉 3 bytes、精確
吃到 Function A 的 RET 為止**，程式計數器接著落在 `0x359cb`——無縫接上 Function B 的完整、
自洽入口。這是可重現、逐 byte 驗證過的執行路徑(非猜測)，故標 [推] 而非「無語意」：
**event66 實際執行內容 = Function B 的完整行為**(見上)。

event65/66 兩者都是「檢查觸發單位 raw camp(+6) 是否非零，再以不同常數呼叫同一個共用效果
函式 `0x344f2`」的同構事件，差異只在傳入常數(0x2c/0x27 vs 0x18/0x17 與 0x38/0x35)。

### 11.3 兩個先前「未展開」的共用呼叫目標

**`func_0x344f2(a,b,c)`**——原先各節標註「可能是 overlay 呼叫，靜態無法展開」，實際反組譯
證實是普通 in-segment 函式，本體用 tail-jump 共用實作：
```
0x344f2  push 0xc ; call 0x3702f
0x344fc  push ebx ; push esi
0x344fe  esi=[esp+0x10] ; ecx=[esp+0x14] ; edx=[esp+0xc]
0x3450a  jmp 0x3452a                      ; tail-call 到共用實作(本節未展開 0x3452a 本體)
```
不再是「不可展開的 overlay」，只是共用尾端(`0x3452a`)這次沒有再往下追展開。

**`func_0x35B78(group_id, item_id, count?)`**——**修正**先前 §10.2/§10.4.2/§10.4.3 對
event73/74/75/77 的推測(「給予道具的 helper」)。實際反組譯顯示這是一個**「spawn_group +
兩段調色盤淡入 + 全螢幕重繪」**的複合原語，不是純粹的給予道具函式：
```
0x35b78  push 0x10 ; call 0x3702f
0x35b82  push [esp+8] ; push [esp+8] ; call 0x135dd ; add esp,8   ; 未展開：對第2引數複製
                                                                    ; 兩次餵給 0x135dd
0x35b92  movzx eax,[esp+0xc] ; push eax ; call 0x10b4e            ; ★ spawn_group(底部引數=group_id)
0x35b9d  push 0x12c ; call 0x3790a ; add esp,4                    ; 未展開，疑似淡入階段1(時長300)
0x35bad  push 0xff,0xff,0 ; call 0x11df2 ; add esp,0xc            ; 未展開，疑似RGB/淡色參數
0x35bc1  push 0xc8 ; call 0x3790a ; add esp,4                     ; 疑似淡入階段2(時長200)
0x35bce  push 0,0xff,0 ; call 0x11df2 ; add esp,0xc
0x35bdf  push 0 ; call 0x11cac ; add esp,4                        ; ★主戰場重繪函式(§7.6 已證實)
0x35be9  jmp 0x35722                                               ; tail-call(本節未展開)
```
呼叫慣例(以 event73 `push 1,0x1B,3;call 0x35B78` 為例，cdecl 逆序push)：`group_id`=最底部
引數(=1)、`item_id`=中間引數(=0x1B)，傳給 `0x135dd` 的即是這個 `item_id`。**修正**：
event73/74/75/77 系列呼叫應理解為「用給定 group_id 呼叫 spawn_group、並用 item_id 對
`0x135dd` 做某種登記/檢查，再播放兩段調色盤淡入特效並重繪」——較可能是「援軍/新單位登場的
淡入演出」，不是單純給予道具。`0x135dd`、`0x3790a`、`0x11df2`、`0x3452a` 四個子函式本節
仍未展開，留待後續。

### 11.4 event77 外層 handler 完整重建 [驗]/[推]

沿用同一方法往回追，event76(見 §11.5 邊界更正)RET 之後緊接兩個此前未編號的短函式：
```
0x35d85  push 4 ; call 0x3702f ; eax=[0x53a55] ; dl=[0x53bef] ; mov[eax+6],dl ; ret
         ; turn_events slot(+6) 單次重排程寫入
0x35d9e  push 0x28 ; call 0x3702f ; 畫面draw(arg4) ; call 0x344f2(0,0x2d,0x29) ;
         畫面draw(arg6) ; mov[0x53ad5+0x12],1 ; ret
```
再接著才是**真正的 event77 外層函式，入口 `0x35e5b`**：
```
0x35e5b  push 0x28 ; call 0x3702f(0x28)
0x35e65  push 0,0x2d,0x29 ; call 0x344f2 ; add esp,0xc
0x35e73  畫面draw(9引數，arg5)
0x35e9a  push 3,7,8 ; call 0x35b78 ; add esp,0xc
0x35ea8  push 4,7,4 ; call 0x35b78 ; add esp,0xc
0x35eb6  push 5,7,0
0x35ebc  jmp 0x35d55                                    ; ★ tail-call，尾呼叫進另一個 0x35b78(5,7,0) 呼叫點
```
`0x35ebc` 這條 `jmp 0x35d55`(`E9 94 FE FF FF`)的位移運算元涵蓋 `0x35ebd..0x35ec0`，而
**event77 註冊位址 `0x35ebe` 正是這 4 bytes 位移中的第 2 byte**——byte 級精確證實，收斂
§10.4.3 原本「約落在 JMP 中段」的推論。若字面上從 `0x35ebe` 執行，開頭 2 bytes `FE FF`
會解碼成 `FE`(INC/DEC 群組)搭配 ModRM `FF`(reg 欄位=7，該 opcode 群組未定義此擴充)——
**不合法的操作碼編碼**，即這個位址若真的被 CPU 執行到，會是未定義行為，不是可運作的程式
路徑。

尾呼叫目標 `0x35d55` 反組譯證實是另一個 `push 1,0x12,0x11;call 0x35b78` 呼叫點，其後緊接
event76 自己的畫面draw序列。也就是說 event77「第三次 0x35b78 呼叫」透過尾呼叫其實落腳在
**另一個獨立呼叫點的程式碼裡**，不是進了新函式本體。

外層函式 `0x35e5b` 用 `call_scan`/`xref_to` 查無任何 `E8` 直接呼叫或既有 xref 指向它——即
這個函式**目前找不到已知呼叫者**，語意上自洽(給予/登記 item 7 的三個變體 + 淡入 + 重繪)，
但它與 event77 之間的關係僅止於「event77 的 table 項落在它的尾呼叫運算元裡」這個 byte 巧合，
不能反推「event77 事件被觸發時會執行它」——依 §10.4.3 同款判準，這仍歸類為「table 項不是
有效進入點」，但其所在的完整函式體本節首次完整記錄，供後續 caller 溯源使用。

### 11.5 方法論警示：「反組譯無警告」不足以證明表項是真正的函式入口

本節在核對 event77 上下文時，連帶用「回溯確認上一條指令是否恰好在表項位址結束」的方式，
覆核了幾個 §10.1 已標 [驗]「乾淨無警告」的既有結果——**這個邊界檢查此前沒有系統性做過**，
結果至少兩個既有 [驗] 結果實際上也沒通過：

| event | 既有記錄 | 本次回溯結果 |
|---:|---|---|
| 76 | 入口 `0x35d60`，「僅 `0x15F84()` 然後返回」 | `0x35d60` 落在 `PUSH 0x13` 指令的立即值 byte(該 `PUSH` 屬於一段從 `0x35d5d` 開始、`push 1,0x13,0x4a,0x4c,...` 的畫面draw引數序列，`0x35d5d` 本身緊接在 §11.4 event77 外層函式尾呼叫目標 `0x35d55` 的 `call 0x35b78` 之後)。從 `0x35d60` 起跳的 flow-directed 反組譯之所以「無警告」，是因為一條 3-byte 垃圾指令(`ADC EBP,[EDX+0x4a]`)剛好吃滿 3 byte、在 `0x35d63` 巧合重新對齊回真正的指令流——純屬巧合，不是證據。真正函式入口應為 `0x35d5d`(或更早，本節未回溯到底)。 |
| 78 | 入口 `0x35ed2`，「條件不可信/骨架可信」 | `0x35ed2` 落在 `CMP byte[EAX+0x13],0` 指令(真正起於 `0x35ed0`)的位移 byte。往回追可回溯到 `0x35ec1`(`PUSH 0x28;CALL 0x3702f` 標準序頭)，這才是本函式(緊接在 event77 外層函式尾聲之後)的真正入口。骨架結論(有條件則畫面+`0x35F10`，然後 `[0x53AD5+0x13]+=1`)不受影響，但引用位址應從 `0x35ed2` 改成 `0x35ec1`。 |

此外，`0x354FE`(既有「event 58：map25 五選一寶物」一節引用的入口)本次用同一方法
flow-directed 反組譯**直接產生不可信的垃圾指令流**(`ADD byte[EAX],AL` 等)，完全不含該節
描述的 `0x1B8A6`/`0x5274E`/FDTXT `0x1E0` 等內容；而這些內容**確實存在於程式中**，但位於
§10.4.2(event62)已知的另一個函式內——往回掃描該函式的標準「`push N;call 0x3702f`」序頭，
精確找到 `0x35854`(`push 0x44;call 0x3702f`，緊接已知的 `0x3585e` 序幕)。`0x35854` 是否
才是 event58 真正的表項值，本節**未能**透過獨立管道(直接重讀 `0x51b91` 原始跳表 bytes)
完全實錘——嘗試過直接讀表，但讀出的值與本文件其他已高度驗證的表項(event0、event82)對不
上，懷疑是資料段/多重疊加記憶體區塊的定址問題，非本節能力範圍內排除，**因此本節不更動
「event 58」既有小節的結論**，僅在此留下明確、可重現的 byte 證據與座標，供後續專門稽核。

**建議**：未來任何「flow-directed 反組譯從表項位址起跳、無 Ghidra 警告」的結果，都應該
**額外**做一次「往回確認上一條指令是否恰好在表項位址結束」的邊界檢查(本節示範的方法)，
不能只憑「沒有 `unaff_*`/`halt_baddata`」就判定 [驗]。已標 [驗] 的 58/76/78 三項建議重新
核對；67/69/82/84 本次已個別核對，邊界成立(前一指令恰好在表項位址結束)，維持 [驗]。

### 11.6 90 entries 累計現況更新(2026-08-24 首輪，見 §11.7 更正)

58..89 全 32 個 entry，加上本節後**全部都有明確狀態**(此前 64/66 完全遺漏)：
- **22 個有具體位址佐證的行為描述**：58/59/60/61/63/65/67/69/74/75/76/78/82/84(既有14) +
  62/72/73/79/80/83(§10 新增6) + **66(本節新增第22個)**。
- **11 個證實為表項落在鄰居 handler 中段、無獨立語意**：68/70/71/81/85/86/87/88/89(既有9)+
  **64、77(本節新增第10、11個)**。
- 60 個(0..57 turn_events 子集)不在 L212 範圍內。
- 開放子執行緒(非本節能力範圍，留給後續)：`0x135dd`/`0x3790a`/`0x11df2`/`0x3452a` 四個
  共用子函式本體未展開；58/76/78 三個既有 [驗] 條目的引用位址疑似需要修正(§11.5)；直接
  重讀 `0x51b91` 原始跳表 bytes 的定址異常待排除。

> **本節上述「22/11」統計已被 §11.7 更正**：58/76/78 三項經 §11.7 獨立管道釘死為 table
> artifact，應從「22 個有具體行為描述」移到「artifact」欄，最終統計改為 **19 / 14**。保留本節
> 原文字供對照 §11.5→§11.7 的推進過程。

### 11.7 2026-08-24(續輪)：event58／76／78 re-verify definitively 收斂——三者皆確認為 table artifact

> 回應 §11.5 留下的「證據強但未經獨立管道完全釘死」缺口，以及 `91-worklist.md` L212 的
> re-verify 要求。本輪找到 §11.5 當時缺的**第二條完全獨立管道**：不靠反組譯（不管是正向
> flow-directed 還是回溯 basic-block walk，兩者都仍是「反組譯器詮釋 bytes」），而是**直接讀
> `0x51b91` 跳表本身的原始 4-byte little-endian 值**，不經過任何指令解碼。§11.5 當時也試過
> 這條路，但「讀出的值與已驗證表項(event0、event82)對不上」而放棄；本輪的差異是**先找出
> 一致的偏移量、並用 4 個獨立錨點交叉驗證，而非只試一次就放棄**。

#### 11.7.1 找到並驗證跳表原始值的偏移常數

`ghidra_batch_probe.py` 的 `bytes` action 直接從 `0x51b91 + event_id*4` 讀 4 bytes（不反組譯）。
用 4 個**已經由其他方式高度驗證過**的 entry 當錨點：

| event | table 位址 | raw hex(LE) | raw 值 | 既有已驗位址 | raw − 已驗位址 |
|---:|---|---|---:|---|---:|
| 0 | `0x51b91` | `31 45 03 00` | `0x34531` | `0x341db`(§6.1) | `0x356` |
| 59 | `0x51c7d` | `97 59 03 00` | `0x35997` | `0x35641`(既有[驗]) | `0x356` |
| 77 | `0x51cc5` | `14 62 03 00` | `0x36214` | `0x35ebe`(§11.4 外層 handler tail-call 位移，[驗]) | `0x356` |
| 82 | `0x51cd9` | `e8 62 03 00` | `0x362e8` | `0x35f92`(§6.1) | `0x356` |

四個錨點**全部**得到同一個常數差 `0x356`（raw 值 = 真實 linear 位址 + `0x356`）。這解釋了
§11.5 當時為何「讀出來對不上」——**不是位址算錯，是沒扣掉這個偏移量**；本輪不是新方法，
只是把同一招用夠多錨點驗證到能信任為止（4/4 命中，零反例）。這個偏移量很可能是 LE
可執行檔的 relocation/object-base 記法造成的系統性 delta（該資料段本身可能是另一個
overlay/object 的鏡像），成因不在本節範圍內深究，但**其存在與大小已用 4 個獨立、彼此互不
依賴的錨點實錘**。

#### 11.7.2 用驗證過的偏移量，直接讀出 event58／76／78 的真實 table 值

| event | table 位址 | raw hex(LE) | raw 值 | raw − `0x356` | 對照既有登記位址 | 對照 §11.5 疑似「更早真入口」 |
|---:|---|---|---:|---:|---|---|
| 58 | `0x51c79` | `54 58 03 00` | `0x35854` | **`0x354fe`** | `0x354fe` ✅完全相同 | `0x35854` ❌不是table值 |
| 76 | `0x51cc1` | `b6 60 03 00` | `0x360b6` | **`0x35d60`** | `0x35d60` ✅完全相同 | `0x35d5d` ❌不是table值 |
| 78 | `0x51cc9` | `28 62 03 00` | `0x36228` | **`0x35ed2`** | `0x35ed2` ✅完全相同 | `0x35ec1` ❌不是table值 |

**結論(byte 級、非反組譯詮釋)**：三個表項的原始資料**逐 byte precisely 等於既有登記位址**
(`0x354fe`／`0x35d60`／`0x35ed2`)，不是讀表誤差、也不是四捨五入或鄰近湊巧。§11.5
回溯找到的「更早、乾淨的疑似真入口」(`0x35854`／`0x35d5d`／`0x35ec1`) **確定不是**
table 實際編碼的值——它們是真實存在的函式，但表項並不指向它們。

#### 11.7.3 排除 function_bounds／xref_to／call_scan 作為本案判準的可能性(陰性結果，但仍記錄)

對 6 個位址(`0x354fe`/`0x35854`/`0x35d60`/`0x35d5d`/`0x35ed2`/`0x35ec1`)各跑一次
`function_bounds`、`xref_to`、`call_scan`：

- `function_bounds`：**全部 6 個都回 `in_function:false`**——包含已知乾淨的 `0x35d5d`/
  `0x35ec1`，甚至連 §11.1 已驗證的 `0x3585e`(event62 大函式序頭)也回 false。即
  **Ghidra 的自動分析從未在整個 58..89 range 建立任何 function 定義**（indirect-only
  dispatch，靜態分析追不到），這個管道對本案完全不具鑑別力，不是「因為是 artifact才 false」。
- `xref_to`：全部 6 個 `count:0`。與工具文件已知警告一致(`-noanalysis` 模式下
  `getReferencesTo()` 不可靠，只有「剛好被探測過」的位址才有紀錄)，同樣不具鑑別力。
- `call_scan`(窮舉全 image 的 `E8` opcode)：全部 6 個 `raw_candidates:0`——**這是全 EXE
  範圍內找不到任何一個直接 `CALL` 指令指向這 6 個位址**。這點對「真 vs 假入口」也不具鑑別
  力，因為 58..89 這整個 range 的設計就是**只透過 `[eax*4+0x51b91]` 間接呼叫**，從來不會有
  直接 `E8 CALL`——即使是完全乾淨、真實存在的 `0x35d5d`/`0x35ec1`/`0x3585e` 也一樣 0 命中。

**因此本案的決定性證據來自 §11.7.1/11.7.2 的 raw table bytes 讀取，不是這三個管道**——但
仍完整記錄陰性結果，避免後續誤以為沒查過。

#### 11.7.4 指令邊界佐證(第二條獨立管道，與 §11.5 方法相同但補齊 event58)

§11.5 已經對 76／78 做過回溯 walk 並找到乾淨鄰居函式(`0x35d5d`/`0x35ec1`)，本輪重新
反組譯確認完全一致(見下)，並補齊 §11.5 當時**未做**的 event58：

- **event58**：從 event57 自己已知的 handler `0x354dd` 往前反組譯（非從 `0x354fe` 起跳），
  完整乾淨路徑 `0x354dd..0x3551b`(17 instr，`RET` 收尾)。`0x354fe` 落在其中
  `0x354fc: PUSH 0xcd`(`68 CD 00 00 00`，5-byte 立即值指令，涵蓋 `0x354fc..0x35500`)的
  **第 3 byte**(立即值 4 bytes 中的第 1 個 `0x00`)——這是 event57 自己「9-引數畫面 draw 呼叫」
  參數 push 序列的一部分，與 event58 的登記語意完全無關。從 `0x354fe` 起跳的
  flow-directed 反組譯會先解出 15 bytes 垃圾指令(`ADD byte[EAX],AL` 等)，**恰好在
  `0x3550d` 湊巧重新對齊**回到 event57 自己真正的收尾(`PUSH [0x53a79]; CALL 0x15f84;
  ADD ESP,0x24; RET`)——與 §11.5 對 event76/78 描述的「巧合 resync」機制**完全同款**。
- **event76**：`0x35d60` 落在 `0x35d5f: PUSH 0x13`(`6a 13`)的立即值 byte；真正函式入口
  `0x35d5d`，本輪反組譯重驗確認 12 instr 乾淨到 `RET`(`0x35d84`)，與 §11.5 結論一致。
- **event78**：`0x35ed2` 落在 `0x35ed0: CMP byte[EAX+0x13],0`(`80 78 13 00`)的位移
  byte；真正函式入口 `0x35ec1`，本輪反組譯重驗確認 22 instr 乾淨到 `RET`(`0x35f0f`)，
  與 §11.5 結論一致。

#### 11.7.5 definitive 結論

| event | 登記位址 | 判定 | 依據 |
|---:|---|---|---|
| **58** | `0x354fe` | **table artifact（確認，非 §11.5 疑慮）** | §11.7.2 raw table bytes 逐 byte = `0x354fe`；§11.7.4 證實落於 event57 handler(`0x354dd`)自己的 `PUSH 0xcd` 立即值中段，15-byte 巧合 resync |
| **76** | `0x35d60` | **table artifact（確認）** | §11.7.2 raw table bytes 逐 byte = `0x35d60`；落於獨立乾淨函式 `0x35d5d..0x35d84` 的 `PUSH 0x13` 立即值中段 |
| **78** | `0x35ed2` | **table artifact（確認）** | §11.7.2 raw table bytes 逐 byte = `0x35ed2`；落於獨立乾淨函式 `0x35ec1..0x35f0f` 的 `CMP` 位移中段 |

三者**全部確認為 table artifact，沒有獨立語意，也沒有屬於自己的函式入口**——先前
「[驗] 乾淨反組譯」的結論是反組譯器從表項位址起跳、巧合 resync 產生的假陽性，與
§11.5 已解決的 event64/66/77 同款。**§11.6 的「22/11」統計更正為 18/14**(§11.6 原文
「22」本身與其逐項清單加總對不上，實際應為 21；扣除本輪移出的 58/76/78 後為 18，
14+18=32 與全表 entry 數一致)：
- 18 個有具體行為描述：58..89 中扣除 58/76/78 後的
  `59/60/61/62/63/65/66/67/69/72/73/74/75/79/80/82/83/84` + 事件說明另見下方修正段。
- 14 個確認為 table artifact 無獨立語意：`58/64/68/70/71/76/77/78/81/85/86/87/88/89`。

**event58 額外修正(map25 五選一寶物歸屬)**：`0x354fe` 本身既不含 §6.3「event 58：map25
五選一寶物」節描述的 `0x1B8A6`/`0x5274E`/FDTXT `0x1E0` 內容，也不是通往那段內容的路徑
（該段內容落在 event57 handler 內部，兩者完全是不同的程式碼區塊，互不相通）。那段內容
真正所在的函式入口是 `0x35854`(`PUSH 0x44; CALL 0x3702f` 標準 stack-probe 序頭，緊接
`0x3585e`——與 §10.4.2 `event62` 列已記錄的「乾淨序頭 `PUSH EBX,ESI,EDI; SUB ESP,0x10;
...; MOV ESI,0x5274E`」是同一個函式)。`xref_to`/`call_scan` 對 `0x35854` 都是 0 命中——
**這個函式目前沒有任何已知的靜態呼叫者**（連 event62 的登記位址 `0x35898` 本身，依 §10.4.2
原文，也同樣落在這個函式**尾端一個 PUSH 指令的最後 1 byte**，是否真的是它的入口同樣未經
今天這輪同等程度的驗證）。**因此「map25 `{type:2,value:58}` 寶物 slot 在 runtime 究竟怎麼
呼到這段程式碼」目前是未解問題**——確定不是透過 `[58*4+0x51b91]`(已證實是死路，通到
event57)，真正的 dispatch 路徑待後續專門稽核；§6.3／§9.2 的邏輯描述本身（`0x1B8A6`
inventory check／`0x5274E` 五槽表／`0x1BB8C` 寫入／五槽共用旗標）不受影響，只有「入口位址
`0x354FE`」與「透過全域 event_id 58 觸發」兩個歸因需要撤回。

> 相關:doc 23(三大狀態 + 兩跳表)· doc 24(戰役迴圈 + [0x53ecc] 狀態機)· doc 19(腳本系統設計)· doc 11(AI)。工具:`tools/callgraph_le.py`、`tools/disasm_le.py`、`tools/ghidra_batch_probe.py`、`FD2_ghidra_projects/ProbeGlobalEvents16BBWalk.java`、`ProbeGlobalEventsRawBytes.java`、`ProbeExtra.java`、`ProbeEvent67Walk.java`、`ProbeEvent84Walk.java`。
