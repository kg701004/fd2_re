# 40 — 說話者 → 頭像查表機制(第 15 輪 RE,裁決 story 管線三推論)

> story 文本管線(6 個 sonnet agent 分批精校 ch01-33)累積出三條「靜態截圖反推、無 EXE 佐證」的推論
> (見 `91-worklist.md` 第 14 輪、commit `52776ec` message)。本輪用 `FD2.EXE` 反組譯逐一裁決。
> 方法遵守 `rulebook/62`(靜態溯源):錨定已知實例(ch09/10/11/12/13 raw FDTXT bytes + 已對上的譯文)→
> 反向追到控制碼分派 → 讀真正的分派碼,不憑 doc14 舊摘要或截圖猜測。

## 一句話總覽

`0xFFEF`/`0xFFFEE`(-17/-18)開框碼的「肖像 ID」**不是直接索引**,是一個**身分標籤**,經
`0x12C60` 對**當前場景的兩張局部單位表**做線性搜尋(比對 `byte[+8]`)找到匹配單位,
再讀該單位 `byte[+7]` 當真正的 DATO.DAT 索引;`0xFFED`/`0xFFEC`(-19/-20)則是**直接**用該
數字當**戰場單位陣列 index**(`unit[idx].byte[+7]`)。兩條路徑最終都落回同一個 `unit.byte[+7]`
欄位——**這正是 story agent 看到「同一碼在不同章節對到不同人」的真正原因:不是碼表本身變了,
是「當前場景載入哪些單位」變了,查表用的碼是身分標籤或陣列位置,不是全域固定的頭像編號。**

## 修正 `docs/knowledge-base/14-text-control-codes.md` 的一處錯誤

`14` 原表(下表左欄)寫 `-17/-18` 的肖像來源是「DATO.DAT,ID=下個 word」(直接用,無查表)。
**這是錯的**——反組譯 `0x16140`(-17 handler)清楚看到 `call 0x12c60` 查表 + `byte[+7]` 覆寫。
只有 `-19/-20` 才是真正的「直接用數字」(當陣列 index,非 DATO id)。`14` 待更新。

| 碼 | int8 | 處理位址 | 真正機制(本輪修正) |
|---|---|---|---|
| `0xFFEF` | −17 | `0x16140` | 身分標籤 → `0x12C60` 查表 → `unit.byte[+7]` (見下) |
| `0xFFEE` | −18 | `0x1622A` | 同上(下框變體) |
| `0xFFED` | −19 | `0x16367` | **直接** `[0x53A45] + idx×0x50` → `byte[+7]`(doc14 原描述對) |
| `0xFFEC` | −20 | `0x163E3` | 同上(下框變體) |

## 反組譯細節

### `-17`/`-18`:身分標籤查表(`0x16140`,節錄)

```asm
0x01617e  movzx ebp, word ptr [esi+2]     ; ebp = 控制碼後的 word(FDTXT 原始位元組,即 story agent 看到的「字母碼」)
0x016182  push  ebp
0x016183  call  0x12c60                    ; ebp → 查表(見下),回傳 esi(找到的陣列 index)或 -1
0x016188  add   esp, 4
0x01618b  cmp   eax, -1
0x01618e  je    0x1619a                    ; 沒找到 → [esp+0x14]=0(肖像變體旗標=0)
0x016190  mov   dword ptr [esp+0x14], 2    ; 找到 → 變體旗標=2   ← 解 doc14 TODO「肖像左右朝向旗標」
0x0161a2  cmp   ebp, 0x27                  ; ebp(原始標籤) == 0x27(39)?
0x0161a5  je    0x161b1                    ; 是 → 跳過覆寫,直接用 ebp 當 DATO id(sentinel,見下)
0x0161a7  mov   edi, dword ptr [0x3c1b]    ; 否 → edi = [0x53C1B](0x12C60 內部設的「目前匹配單位」指標)
0x0161ad  movzx ebp, byte ptr [edi + 7]    ; ebp 被覆寫成 該單位.byte[+7] ← 真正的 DATO id
0x0161b1  push  ebp
0x0161b2  push  dword ptr [0x3a85]
0x0161b8  push  0x1a70                     ; "DATO.DAT"
0x0161bd  call  0x111ba                    ; 載入 DATO.DAT 第 ebp 個資源(137 張之一)
```

**`0x12C60`(身分標籤 → 單位搜尋,節錄反組譯)**:

```
in: edi = 原始標籤(tag)
[0x53C1B] = 0                              ; 清「目前匹配單位」
陣列①:base=[0x53A45](=戰場單位表,stride 0x50) count=[0x53BEB]
  for esi in 0..count-1:
    if byte[ base+esi*0x50 +8 ] == tag:
        [0x53C1B] = &base[esi]             ; 記下匹配單位
        if 0x3453E(esi) == 0: return esi   ; 通過額外檢查 → 回傳陣列 index
        (否則繼續掃描)
若陣列①掃完仍未return且 [0x53C1B]==0:
陣列②:base=[0x53BF7](count=[0x53BFB],同 stride 0x50)
  for esi in 0..count-1:
    if byte[ base+esi*0x50 +8 ] == tag:
        [0x53C1B] = &base[esi]             ; 同樣記下(未 return,持續掃到底)
未在陣列①以有效 index return → return -1
```

**關鍵**:陣列①`[0x53A45]`就是 `14` 文件已知的「戰場單位表」(與 `-19/-20` 直接索引的是**同一張表**,
stride 同為 `0x50`=80 bytes);陣列②`[0x53BF7]`是另一張同結構表,全程式 40+ 處讀寫
(`0x1011D`…`0x31C0F`,橫跨地圖載入/事件系統/UI),疑為「目前場景 NPC/劇情演員表」——
兩張表都是**隨地圖/場景載入而重新填的資料**,不是寫死在 EXE 裡的全域常數表。

**sentinel `tag==0x27`(=39)**:略過查表,直接把 39 當 DATO id 用。可能是保留給「畫外音/不對應任何
在場單位的旁白」的特殊值(本輪未窮舉驗證,標「靜態可查但未展開」)。

### `-19`/`-20`:直接陣列索引(`0x16367`,節錄)——doc14 原描述正確

```asm
0x0163a1  movzx edi, word ptr [esi+2]      ; edi = 控制碼後的 word = 陣列 index(不是 id)
0x0163a5  mov eax, edi
0x0163a7  shl eax, 2
0x0163aa  add eax, edi                     ; eax = edi*5
0x0163ac  shl eax, 4                       ; eax = edi*5*16 = edi*0x50   (= idx*80)
0x0163af  mov edi, dword ptr [0x3a45]      ; 同一張戰場單位表
0x0163b5  add edi, eax                     ; edi = &unit[idx]
0x0163b7  movzx ebp, byte ptr [edi + 7]    ; ebp = unit[idx].byte[+7] = DATO id(無查表,純位移)
0x0163bb  mov dword ptr [esp+0x14], 2      ; 變體旗標固定 = 2(與 -17 查無結果時的 0 不同)
...call 0x111ba(載入 DATO id=ebp)
```

## 三條推論逐一裁決

### 推論 ① 「字母碼是場景本地表非全域」→ **成立,但機制不是『表』是『陣列 index/身分標籤』**

用 raw FDTXT bytes(`extracted/raw/FDTXT/FDTXT_009/010/011.bin`)重新解析(只在 `-17/-18/-19/-20`
後消耗一個 word 當標籤/index,`-2/-3` 純換行不消耗 operand——這點 story 管線和舊 `render_story.py`
都做錯了,見下節),逐句比對已精校譯文:

| 章 | 控制碼 | 原始 word | 對到誰(譯文比對) | characters.json 對應? |
|---|---|---|---|---|
| ch09 | `-19`(直接 index) | 11 | 萊汀(入隊前,禁衛軍隊長身分登場) | 11 = 索菲亞(不符!) |
| ch09 | `-18`(查表) | 8 | 希莉亞 | 8 = 希莉亞(符合) |
| ch09 | `-18`(查表) | 0 | 索爾 | 0 = 索爾(符合) |
| ch10 | `-18`(查表) | 6 | 萊汀(已入隊) | 6 = 萊汀(符合) |
| ch10/11 | `-19`(直接 index) | 11 | 索菲亞 | 11 = 索菲亞(符合) |
| ch12 | `-18`(查表) | 17 | 米亞斯多德(自報姓名句「我叫做米亞斯多德」,文本直證) | 17 = 米亞斯多德(符合) |
| ch11 | `-18`(查表) | 13/14 | 貝克威/珊 | 13/14 符合 |

**裁決（限已驗證scene/constructor）**：部分已入隊角色的 `byte[+8]`
identity key與`byte[+7]` raw visual selector初值相同，足以支持目前
0–31 display projection；這不是兩欄全域alias，也不能外推到敵人、臨時單位、
轉職或其他constructor。ch09 萊汀則用 `-19`(直接 index)，而非 `-18`
(身分查表)——**編劇/
引擎刻意繞過身分查表,直接指定「目前場景單位陣列第 11 格」**,而那個場景的第 11 格單位是誰、
`byte[+7]`填什麼,是**該地圖(FDFIELD)的單位擺放資料決定的,不是全域頭像表決定的**。這就是
story agent 觀察到「ch09 的 B(=11)≠ch10/11 的 B(=11)」的真正成因:**兩處根本走不同的分派路徑
(index vs 查表),只是原始位元組數字剛好都是 11**,並非同一張「表」在兩處給了不同答案。

→ **對重製 / story JSON 的建議**：`-1`＋人工名只適合展示／編輯層。
faithful runtime script仍須保存opcode、scene/unit index與portrait/resource
provenance；不能用人名覆寫native selector。ch09仍需解對應FDFIELD constructor
與第11格`byte[+7]`來源。

### 推論 ② 「戰鬥小兵陣亡台詞的字母碼 = 另一張怪物表(與劇情 NPC 表同碼異義)」→ **不成立(無兩張表),但現象成因抓對了**

ch13 一段連續陣亡台詞(`extracted/raw/FDTXT/FDTXT_013.bin`)逐句解出:

```
[-19 直接idx] idx=15  『啊．．』
[-19 直接idx] idx=17  『你們消滅不了精靈族的．．啊．．』   ← story agent 讀作「H」,誤判=米亞斯多德
[-19 直接idx] idx=19  『哇啊．．』
[-19 直接idx] idx=21  『啊．．』
[-19 直接idx] idx=23  『哇啊．．』
```

同一份 ch13 稍早,`-18`(查表)code 也用了 `17`,對到「好極了，寶箱好像都還安然無恙」——
story agent 據此推「H(=17)在 ch12/13 是米亞斯多德,但陣亡吼的 H 是獸人,兩碼各表一張」。

**裁決**:根本原因不是「兩張表」,是 **`-18`(查表)和 `-19`(直接 index)本來就是兩種不同定址方式**,
恰好都用了數字 17——`-18` 的 17 是「身分標籤 17,查到入隊的米亞斯多德」;`-19` 的 17 是
「戰場單位陣列第 17 格,這場戰鬥裡剛好站著一個精靈守軍」。**兩者共用同一張陣列
`[0x53A45]`**(doc14 已知的戰場單位表),不存在「怪物表」與「NPC 表」的分裂——分裂只在於
**用陣列 index 還是用身分標籤去查**,這在控制碼(`-17/18` vs `-19/20`)上就已經寫死,不需要
額外一張表。米亞斯多德真正入隊後(有穩定身分標籤 17)和「這場戰鬥剛好第 17 格站著誰」
純屬巧合式數字重疊。

→ **對重製 / story JSON 的建議**:陣亡台詞類對白(通常用 `-19/-20`)一律應標「場景相依,
不可用固定 id→角色名靜態表對映」,現行 story JSON 把這類行的 `speaker` 設 `-1`
並用「甲乙丙丁/獸人一二三」等文本可讀慣例命名,**做法正確,不需回改**。

### 推論 ③ 「單碼 0-9,A-V(=10-31)→ face_portrait 線性,W(=32)如何處理」→ **字型表確為線性,但那是渲染巧合,不是 EXE 的編碼規則邊界**

`docs/data/glyph_map.json` 證實:glyph `0-9`='0'-'9',`10-35`='A'-'Z',`36+`=漢字(依首次出現順序
分配,無語意)。這條映射屬於**字型 / 字模表**,和 EXE 的 speaker id/idx **完全無關**——後者是
16-bit 整數,沒有任何「≤31 用一套規則、≥32 換一套規則」的分支(`0x12C60`與直接 index 兩條路徑
都只用 `cmp`/`je`,唯一的特例判斷是 `tag==0x27`)。

**story agent 為什麼會看到「A-V 剛好對得上,W 開始就亂了」**:因為 `0-31` 恰好是「已正式登記、
身分標籤穩定的 32 個核心角色」數量(`characters.json` 32 筆),數字上跟字型表的 `A-V`(10-31)
範圍重疊,兩者是**各自獨立的巧合**,不是同一條規則的兩段。超過 31 的 id(如 ch09 的 34、
ch10 的 50/51/69、ch13 的 72/103、聖寇拉斯所在陣營 39)一樣是合法整數,不需要「特殊處理」——
只是這些值落進字型表的漢字區,渲染工具(下節)把它們畫成看似隨機的單一漢字,才讓 agent 誤以為
「規則變了」。

→ **裁決**:story agent 的「A=10…V=31 線性」**觀察正確**,但那是字型表的性質,不是
speaker id 編碼規則的性質;`W` 之後不需要任何特殊 fallback,現行「大於 31 找不到就標 -1,
用可讀名字」的做法已經是正確處理方式。

## 「字母碼」的真正來源:自製 PNG 渲染工具的 bug(不是原版遊戲行為)

story agent 看到的 B/H/X/Y/單漢字,不是原版遊戲畫面上會出現的東西。真正的 `0x15F84` 渲染器
讀到控制碼後,把肖像 id/idx **當純二進位參數消耗掉**,從不把它丟進畫字迴圈——這點 `docs/
knowledge-base/14` 早已反組譯確認(`sign-extend cmp` 分派,取 word 純粹當參數)。

問題出在我們自己寫的 `tools/render_story.py`(把 FDTXT 轉可讀 PNG 給 agent 看的工具):

```python
# tools/render_story.py lay_out()
for c in s:
    if c >= 0xFF00:        # 控制碼 → 只換行,沒有消耗它後面的 operand word!
        ...
    else:
        line.append(c)     # 下一個 word(其實是肖像 id/idx)被當成普通字模畫進 PNG
```

`lay_out()` 只認得「控制碼本身要換行」,**完全沒有 -17..-20 之後還跟著一個 operand word 要跳過**
的邏輯。於是那個 operand word 原樣落進下一輪迴圈的 `else` 分支,被當一般字模用
`render_glyph(font, c)` 畫出來——而這個 c 剛好是 0-9/A-Z/CJK 字型表裡的值,於是它就以一個
無意義的字元「洩漏」進 PNG,緊貼在對白的開引號『前面。agent 逐頁看 PNG 轉錄劇本時,
把這個洩漏字元誤認成遊戲本身的「說話者代號」,才生出推論 ①②③。

`tools/decode_story_text.py`(另一支自動解碼工具,產出 `full_story_auto.md`)也有同源問題:
`PORT.get(spk, g2s([spk]))`——查無 `0-31` 對照表時直接把 raw id 丟進字型解碼當名字顯示,
同樣會洩漏。此檔案本就已標「不可信,glyph 對照表有系統性偏移」,不影響最終入庫的 ch01-33.json
(那批走人工 / sonnet PNG 精校,見 `story_to_script.py` docstring)。

**待辦**:`render_story.py` 的 `lay_out()` 應修正——遇到 `0xFFEF/EE/ED/EC` 時多跳過緊接的一個
operand word,PNG 才不會洩漏假字母/假漢字,未來章節重新渲染核對時不再誤導。本輪不動它
(只讀不改,任務範圍是查證,不是修 pipeline)。

## 結論摘要(回覆用)

1. **0xFFEF→頭像機制一句話**:`-17/-18` 開框碼帶的數字是「身分標籤」,經 `0x12C60` 對
   `[0x53A45]`(戰場單位表)與 `[0x53BF7]`(場景演員表,兩者 stride 皆 0x50)做線性搜尋
   (比對 `byte[+8]`)找到匹配單位後,讀其 `byte[+7]` 當 DATO.DAT 索引去 `0x111BA` 載肖像;
   `-19/-20` 則不查表,直接把數字當 `[0x53A45]` 的陣列 index 用同一個 `byte[+7]` 欄位。
   兩條路徑最終都落在同一張「戰場單位表」的同一個欄位,只是定址方式不同。
2. **推論①(場景本地表)**:部分成立——不是「表」本身隨場景換,是「查表用身分標籤」vs
   「直接用陣列位置」這兩種**定址方式**混用,且陣列內容(哪個單位在哪格)確實隨地圖/場景
   重新填入,才造成同一數字在不同章節指向不同角色的現象。已有位址佐證(見上)。
3. **推論②(怪物表 vs NPC 表)**:不成立——只有一張戰場單位表,不存在「與劇情 NPC 表同碼
   異義的另一張怪物表」;陣亡台詞用 `-19/-20`(陣列 index)恰好也會跟 `-18`(身分標籤)用到
   同一個數字,純屬巧合式重疊,不是兩張表。已有位址佐證。
4. **推論③(A-V 線性,W 起如何處理)**:字型表(glyph→Unicode)確實 `0-35` 線性對應
   `0-9,A-Z`,`36+` 為漢字——但這是字型表的性質,和 speaker id/idx 的編碼規則無關;
   EXE 端 id/idx 是普通整數,沒有 32 這個特殊邊界,不需要對「W 以上」做任何額外處理。
5. **story JSON 的界線**：現行「查得到就填characters.json、查不到填-1並人工
   標名」可保留作display projection，但不是最忠實的runtime表示。後續schema應
   另存native opcode、scene/unit index與resource provenance；ch09第11格來源仍是必要
   evidence工作，而非可選考據。

## 2026-08-19 補充:三個已釘位址展開(對應 `91-worklist.md` 第 705 行)

> 方法:read-only Ghidra headless(`FD2Analysis3`,`-noanalysis`,唯讀),對三個項目分別重新反組譯 +
> 全程式 xref 掃描獨立驗證(不只沿用舊 doc 結論)。腳本:`FD2_ghidra_projects/ProbeWorklist705{,b,c}.java`。

### ① `0x3453E`(`0x12C60` 內的額外檢查函式)—— **同一個「位址標籤過期」問題,已展開**

新鮮反組譯 `0x12C60`(節錄,array① 掃描段):

```asm
00012c91  MOVZX EAX,byte ptr [EBX+0x8]   ; 候選單位 byte[+8]
00012c95  CMP EAX,EDI                     ; == tag?
00012c97  JNZ 0x00012c85                  ; 不符→下一格
00012c99  MOV dword ptr [0x53c1b],EBX     ; 記下候選
00012c9f  PUSH ESI
00012ca0  CALL 0x00034894                 ; ← 實際呼叫目標,不是 0x3453E
00012ca5  ADD ESP,0x4
00012ca8  TEST EAX,EAX
00012caa  JNZ 0x00012c85                  ; 非0→視為拒絕,繼續掃描同一 tag 的下一格
00012cac  MOV EAX,ESI                     ; 0→接受,回傳 index
```

`0x12C60` 在 `0x12ca0` 呼叫的**真正**位址是 `0x34894`,不是 doc 舊 pseudocode 寫的 `0x3453E`——
這和 `docs/knowledge-base/26-per-chapter-event-handlers.md` §7.1.1(2026-08-18 前)已經獨立抓到的
「`0x23a74` 呼叫點位址標籤過期」是**同一種 bug**,只是這次出現在 `0x12C60` 這個呼叫點。逐位元組核對:

- `0x3453e` 的原始 bytes 是 `e8 62 cd fd ff` = `CALL 0x000112a5`,不在任何已定義 function 邊界內
  (`getFunctionContaining(0x3453e)` = NONE),屬於一個從 `0x34531` 開始的呼叫序列中段
  (`push 0x1; call 0x112a5; ...; push 0x3; call 0x10b4e; ...; push 8; push 5; call 0x135dd; ...`)。
  `0x112a5` 正是 doc26 §7.2 已定案的 **JOIN 角色 constructor**(`sub_112A5`/`MaterializePersistentUnit`);
  `0x34531` 這段呼叫序列因此高度疑似某個 JOIN 事件 handler(呼叫時 `push 0x1`=傳入角色/肖像 id),
  跟 speaker/portrait byte5-bit0 查詢完全無關。
- `0x34894`(`0x12C60` 實際呼叫的位址)反組譯確認 = `NativeRecordByte5Bit0(idx)`:
  ```asm
  00034894  PUSH 0x4
  00034899  CALL 0x0003702f
  0003489e  MOV EDX,[ESP+0x4]           ; idx
  000348a2  MOV EAX,EDX
  000348a4  SHL EAX,0x2
  000348a7  ADD EDX,EAX                  ; edx = idx*5
  000348a9  SHL EDX,0x4                  ; edx = idx*0x50
  000348ac  MOV EAX,[0x53a45]            ; 戰場單位陣列基底
  000348b1  MOV AL,[EDX+EAX+0x5]
  000348b5  AND AL,0x1
  000348b7  MOVZX EAX,AL
  000348ba  RET
  ```
  與 `docs/knowledge-base/26-per-chapter-event-handlers.md` §1/`docs/knowledge-base/50-cutscene-script-system-design.md`
  已經 Docker Capstone 閉合(`RE-RAW-BYTE5-BIT0-3453E`,2026-07-27)的 `NativeRecordByte5Bit0`
  完全一致(`byte[idx*0x50+5] & 1`,raw predicate,不寫入)。
- 全程式 xref 掃描:`0x34894` 共 **8** 個直接 CALL 呼叫點(`0x127c2/0x12a4a/0x12c47/0x12ca0/
  0x11682/0x1b63e/0x2a09f/0x11566`),`0x12C60`(`0x12ca0`)是其中之一——**這是本輪新確認的第 8 個
  caller**,先前 doc25/26/50 只追蹤過其他 caller(如 ch16_post `0x23a74`)。`0x12c47` 所在的
  `FUN_00012c0d`(緊鄰 `0x12C60` 前一個函式)也呼叫同一函式,疑是同族的另一個查表/驗證 helper,
  本輪未展開(範圍外)。

**結論(caller-local,不升級成全域命名)**:`0x12C60` 找到 `byte[+8]==tag` 的候選單位後,用
`NativeRecordByte5Bit0(候選index)` 再檢查一次——若該候選的 `byte[+5]&1 == 1`,`0x12C60` **拒絕該候選,
繼續掃描同一 tag 的下一格**;只有 `&1 == 0` 才接受並回傳。這是 `0x12C60` 這個 caller 自己的分支行為,
與 doc26 已建立的「byte[+5] bit0 是 caller-specific mask,不可全域命名成死亡/存活」原則一致——
在 speaker/portrait 身分查表的語境下,可以精確描述為「跳過該 raw bit 被設置的候選單位」,但不主張
這代表全域的「死亡/inactive」。**「額外檢查」語意已展開完畢,無殘留不確定性**(位址標籤已修正為
`0x34894`;doc40 開頭 §「反組譯細節」的 pseudocode 之後應同步改標)。

### ② `tag==0x27` sentinel —— **全程式窮舉掃描,確認唯一、且不與 -18 共用**

對整個 EXE(976 個已定義函式 + 全部已反組譯指令)掃描所有 `CMP reg, 0x27` 立即數比較,
**全程式僅此一處**:

```
000161a2  CMP EBP,0x27   [fn=FUN_00015f84]   ; 僅此一處,-17 開框碼(0x16140)內
```

同時重新反組譯 `-18`(`0xFFEE`,`0x1622A`)整段路徑,確認它**完全沒有 tag==0x27 判斷**——
`cmp eax,-1 / jz` 分流只影響肖像變體旗標(`[esp+0x14]`=`0x70` 或 `0`),兩條分支都直接匯合到
`0x1628c: MOV EDI,[0x53c1b]; MOVZX EBP, byte[EDI+7]`,無條件依賴 `0x12C60` 內部設的
`[0x53c1b]`(找不到任何匹配時,若 array② 也全空,`[0x53c1b]` 會停留在 `0x12C60` 入口清的 0)。
**這修正/收斂了 doc40 原文「(-18)同上(下框變體)」的措辭**:-18 與 -17 共用同一個 `0x12C60` 查表,
但只有 **-17** 的 handler 自己額外加了 `tag==0x27` 這一條旁路判斷;-18 沒有。

**結論**:`tag==0x27`(=39)是**僅存在於 `0xFFEF`(-17)開框碼 handler(`0x16140`)自身**的
特例分支,程式其他任何地方都不會再檢查這個立即數——不是一個被多處共用的全域 sentinel 常數。
比對成立;`je 0x161b1` 之後直接 `push ebp`(=0x27)當 DATO id,繞過 `[0x53c1b]` 查表結果,靜態邏輯本身
無殘留疑點。**但「為什麼恰好是 39」(DATO.DAT 資源 #39 代表什麼)無法只靠 EXE 程式碼反組譯回答**——
39 在指令流裡只是一個裸立即數,沒有任何字串/常數表把它標成「畫外音」或其他語意;要驗證 doc40 原本的
猜測,需要去查 `DATO.DAT` 第 39 張資源實際內容(圖檔),這已經超出「反組譯 EXE」的範圍。
**誠實標記**:sentinel 觸發條件與唯一性已窮舉確認[驗];「39 選這個數字的敘事/資產理由」仍需活體或
資產檔案佐證,不在本輪範圍內關閉。

### ③ `[0x53BF7]` 表用途 —— **doc40 原猜測「場景演員表」有誤,應正名為「我方持久名冊」**

全程式 xref 掃描:`[0x53BF7]` 共 **26** 處直接參照(15 個函式),其計數欄位 `[0x53BFB]` 共 **41** 處
(約 20 個函式)。三條各自獨立、彼此吻合的證據鏈,結論一致:

1. **`0x33499` = `roster_has(id)`**(doc26 §1 已知,本輪重新反組譯全 body 逐指令核對):
   `for edx in 0..[0x53bfb): if byte[[0x53bf7]+edx*0x50+8]==id: return 1` ——線性搜尋我方名冊,
   跟角色 ID 比對 `byte[+8]`,回傳布林。這是「我方是否擁有某角色」的查詢,不是場景/地圖概念。
2. **`0x11506` = 戰後 runtime→persistent 同步**(doc26/doc50 §3.2 已完整驗證):把剛結束那場戰鬥
   `[0x53a45]`(戰場單位陣列)的資料,依 `+8` 角色 ID 配對,複製進 `[0x53bf7]`——同步方向明確是
   「戰場資料寫回持久名冊」,語意上就是**存檔/跨關保留**的角色資料表,不會是隨場景重新填的暫態演員表。
3. **`0x112a5`(doc26 §7.2 已定案為 JOIN 角色 constructor `MaterializePersistentUnit`)本輪新確認寫入位置**:
   ```asm
   000112b6  MOV EDX,[0x53bfb]              ; 目前名冊人數(下一個空位 index)
   000112be  SHL EAX,0x2
   000112c1  ADD EAX,EDX
   000112c3  SHL EAX,0x4                     ; eax = count*0x50
   000112c6  MOV ESI,[0x53bf7]               ; 名冊基底
   000112cc  ADD ESI,EAX                     ; esi = &roster[count]  ← 新成員要寫入的槽
   ...
   00011337  MOV byte ptr [ESI+0x5],0x0      ; 新角色 byte[+5]=0(比照 doc26 已知的戰場單位 constructor 模式)
   0001133b  MOV byte ptr [ESI+0x6],0x2
   0001133f  MOV AL,[ESP+0x34]               ; caller 傳入的角色/肖像 id 參數
   00011343  MOV byte ptr [ESI+0x7],AL
   00011346  MOV byte ptr [ESI+0x8],AL       ; +7 與 +8 初始寫入同一個值(identity==portrait 初值)
   ...
   0001143e  PUSH dword ptr [0x53bfb]        ; (函式尾段)回傳舊 count 當新成員 index
   0001144c  INC dword ptr [0x53bfb]         ; 名冊人數 +1
   ```
   即「加入新隊員」直接把新角色寫進 **`[0x53bf7]` 陣列的 `[0x53bfb]` 那個空位**,再把計數 +1——
   這是**教科書等級的「往陣列尾端 append 一筆記錄」**,陣列語意只可能是「隊伍名冊」,不可能是
   「當前場景演員表」(場景演員應該隨地圖載入整批 memcpy,不會有「逐一 JOIN 時 append 一筆」這種
   API 形狀)。

**結論**:`[0x53BF7]`(32 槽 × 0x50 bytes,計數 `[0x53BFB]`)是**我方隊伍/角色的持久名冊**
(persistent party roster)——`roster_has` 查它、戰後同步把戰場結果寫回它、JOIN constructor 把新隊員
append 進它。**doc40 本文開頭「陣列②…疑為『目前場景 NPC/劇情演員表』」的猜測應撤回**,改採
`docs/knowledge-base/26-per-chapter-event-handlers.md` 第 45 行「`[0x53bf7]` = 我方隊伍/角色名冊」
與 `docs/knowledge-base/50-cutscene-script-system-design.md` §3.2 的既有定案(本輪用全新反組譯 +
JOIN constructor 寫入路徑獨立覆核,三條證據互相吻合,無矛盾)。

連帶回頭看 `0xFFEF`/`0xFFEE`(-17/-18)身分標籤查表機制:`0x12C60` 掃完戰場單位陣列 `[0x53A45]`
(array①)沒找到,才退而掃 **我方持久名冊 `[0x53BF7]`**(array②)——即開框碼的身分標籤查找,
其實是「先在當前戰場找,找不到就退回問玩家隊伍名冊」,不是「兩張場景表」。這比 doc40 原本
「陣列②是另一張同結構的場景表」更精確。

其餘 12 個也讀寫 `[0x53BF7]` 但本輪未逐一展開語意的函式(`0x19df7/0x10010/0x25ebb/0x26152/
0x2670e/0x2968d/0x2986f/0x2aa00/0x2af28/0x2b777/0x2b843/0x1088d`)——核心「這張表是什麼」的問題已
由上述三條獨立證據鏈確認,不影響結論;個別 caller 的欄位級細節(doc40 原「待辦」第 4 項,
`[0x53BF7]` 與 `[0x53A45]` 逐欄位比對)仍未做,留待需要時再展開。

## 待辦

- [ ] ch09 對應地圖 FDFIELD 單位表第 11 格 `byte[+7]` 反解(取得萊汀入隊前的真實肖像 id)。
- [x] `0x3453E`(`0x12C60` 內的額外檢查函式)語意——**2026-08-19 已展開**:位址標籤過期,`0x12C60`
      實際呼叫 `0x34894`(= doc26 已定案的 `NativeRecordByte5Bit0`);見上方新增小節①。
- [x] `tag==0x27` sentinel 語意——**2026-08-19 已窮舉確認**觸發條件與唯一性(全程式僅一處,且
      -18 不共用);「為何是 39」需 DATO.DAT 資產佐證,非 EXE 反組譯可關閉,誠實留白。見小節②。
- [x] `[0x53BF7]` 表用途——**2026-08-19 已展開並正名**:非「場景演員表」,是**我方持久名冊**
      (roster_has / 戰後同步 / JOIN constructor append 三條證據)。見小節③。逐欄位比對(與
      `[0x53A45]` 的細部欄位差異)仍未做,保留待辦。
- [ ] `tools/render_story.py` `lay_out()` operand-skip 修正(避免未來渲染再洩漏假字母)。
- [ ] `docs/knowledge-base/14-text-control-codes.md` 的 `-17/-18` 肖像來源描述需回頭更正
      (見本文件開頭「修正」一節)。

## 2026-09-05:新建活體工具 `fd2_speaker_capture.py`,首次解出 273 筆的 32 筆(FDTXT_033)

**方法**:`tools/decode_story_text.py --runtime-todo` 先把 273 筆結構化成
`(fdtxt, box_index, operand)` 清單(見該工具 2026-09-05 的新增);
`tools/fd2_speaker_capture.py --resolve-todo` 對一個活體 DOSBox-X 實例讀整個
單位陣列(重用 `fd2_dosbox_live_helper.mem_read_unit_array()` 已經驗證過的
訊號校準邏輯),取每個 `operand` 對應槽位的 `byte[+7]`(本文件 §「一句話總覽」
記載的 DATO.DAT 索引),查 `decode_story_text.PORT`(0x00-0x1F 是主角群,其餘
是 NPC/敵,字模顯示)。

**活體踩到的真實錯誤,已修好**:第一版工具沒有檢查「目前活體畫面到底是不是
呼叫端要解的那個 FDTXT」——同一次觀察(開場動畫後的第一段對話,畫面沒有變、
沒送任何按鍵),對正在播放的 `FDTXT_033` 跑一次、對根本沒在播放的 `FDTXT_032`
也跑一次,**兩次都「成功」印出結果**,因為 DATO 值剛好都查得到某個 NPC——
這正是本文件開頭「一句話總覽」自己講的「當前場景載入哪些單位變了,查表用的碼
是身分標籤或陣列位置,不是全域固定的頭像編號」那個陷阱,這次是工具自己毫無
徵兆地示範了一次。修法:`--resolve-todo` 現在**強制要求** `--confirm-text`
(呼叫端從螢幕截圖親眼看到的一段原文),必須能在目標 FDTXT 的某筆
`text_snippet` 裡找到才放行,否則拒絕執行——`FDTXT_032` 那次已作廢的結果
沒有進入任何紀錄檔。

**解出的結果(`docs/data/runtime_speaker_resolved.json`)**:`FDTXT_033`
(王位繼承場景,ch01 王宮劇情)全部 32 筆一次解完,只用了 4 個 roster 槽位:

| operand(idx) | DATO | 解出結果 |
|---:|---|---|
| 0 | `0x30` | NPC(PORT 查無對應,依對話內容「父王」「朕」推測是國王——**跟 doc09 原本只用 2 句截圖判定的「ch01 王宮兩句被標成索爾、實際是國王」完全吻合,這次是全 32 句規模的獨立活體交叉驗證**) |
| 1 | `0x42` | NPC(依對話內容「我們把你當成自己親生的孩子撫養長大」推測是王后) |
| 3 | `0x00` | 索爾(本人,同一個角色在這個場景占用 idx3,不是常見的 idx 0/1) |
| 4 | `0x04` | 亞雷斯 |

內容連貫(國王要索爾繼承羅特帝亞王位、索爾轉頭向亞雷斯抱怨不想當國王、邀他
去後山練劍解悶),不是查到就信、而是有敘事邏輯可以交叉核對的那種結果。

**FDTXT_032 仍未解——2026-09-05 再嘗試一次,原本的假設被推翻**:先前猜測 032
(童年練劍場景,索爾對亞雷斯說「趕快再來比一場！昨天輸給你」)緊接在 033
之後(033 結尾索爾邀亞雷斯「現在就陪我到後山去練劍」),所以驅動同一個新實例、
從開場動畫一路確認過 033 全部對話,再繼續往下按,想在後山/草地場景抓到 032。

**結果:沒有抓到**——033 結尾的「陪我去後山練劍」邀約之後,畫面確實轉場到草地
(索爾+亞雷斯的行走動畫,無對話框),但接下來出現的是**機器人衛兵的警告台詞**
(「不要再接近！否則我將照規定採取防衛行動！」)跟**悠妮的自我介紹**(「我叫..
我叫..悠妮吧。我怎麼會來到這裡的？」)——這是 ch01 真正戰鬥前導入 Yuni 的劇情,
不是 032 的練劍對話。**"032 緊接在 033 之後"這個假設本輪被推翻**:要嘛 032
出現在這兩者之間、被本輪的確認鍵批次(10 個一批送、批次間才截圖)跳過而沒看到
(033 結尾轉場到警告台詞中間只截了 1 張圖,視窗不夠密),要嘛 032 根本不是
緊接的下一段,是遊戲別處(不同章節的回憶片段等)才會觸發的內容。兩種可能都還
沒有排除,本輪沒有下定論就直接說「找不到」,是誠實記錄「這次没找到」,不是
「確定不在附近」。

**同一天,馬上找到真正的答案——而且根本不需要活體**:上面「下一輪建議」第 2 點
才寫完(查章節腳本綁定資料),一查就發現 `docs/knowledge-base/scene-decode/
ch1-forest.md`(2026-08-20,**比今天早了兩週的既有文件**)早就完整解出 032 了,
而且方法比活體讀記憶體更直接:**FDFIELD map31 自己的 spawn 群組呼叫
(`0x10b4e(group)`,handler `0x3231b`)靜態記載了每個 slot 是誰**——不用等到
runtime 才知道,map 資源本身就寫死了「這張圖 slot0=索爾、slot1=亞雷斯、
slot3=蓋亞、slot4=悠妮」。該文件已經逐句解出全部 11 條字串、40 段對白
(童年鬥嘴→發現昏迷的蓋亞與悠妮→蓋亞警戒→悠妮甦醒問名→決定同行去馬拉大陸),
內容連貫,跟本節今天活體探測誤打誤撞看到的「機器人警告」「悠妮自介」台詞
逐字對得上——**那些片段其實就是 032 本身,只是本節一開始沒認出來**。

**已經直接把這個既有結果套進 `decode_story_text.py --runtime-todo` 的
`box_index`/`operand` 清單**(兩者的 operand 0/1/3/4 剛好對應 ch1-forest.md
的 slot0/1/3/4,序列順序也完全吻合),40 筆全部寫進
`docs/data/runtime_speaker_resolved.json` 的 `FDTXT_032`——**是套用既有靜態
分析算出來的,不是新的活體結果**,已在檔案裡如實標註來源。

**方法論教訓(比找到答案本身更值得記住)**:本節今天一開始沒有先
`grep scene-decode/`,就直接建活體工具、跑真的 DOSBox-X 去找 032 的畫面——
繞了一大圈(建 `fd2_speaker_capture.py`、跑三個活體實例、寫「假設被推翻」的
負面記錄),繞到最後答案其實已經擺在 `docs/knowledge-base/` 裡兩週了。這正是
`feedback_check_existing_evidence_before_disasm` 這條記憶原本要防的事,這次
還是踩了一次——**下一輪解剩下的 241 筆之前,先查 `scene-decode/`、`doc47`、
`doc50` 有沒有現成答案,再決定要不要動用活體工具**;活體工具(`select_ring`
讀值那套)本身沒有錯,只是不該是第一個反射動作。

**下一輪建議(更新)**:
1. 剩下 241 筆:先查有沒有其他 FDTXT 也被 `scene-decode/` 或 `doc47`/`doc50`
   這類 handler-beat 反組譯文件靜態解過,再決定哪些真的需要活體工具。
2. idx0/1(FDTXT_033 的國王/王后)目前只是「依對話內容推測」,不是靠 DATO 值
   本身查出真名(`PORT` 查無對應)——如果要坐實真名,需要另外找這個 NPC 的
   DATO id 有沒有在別處(例如戰鬥中的敵方單位表,或美術資源)有對應紀錄。

## 2026-09-06:`fd2_speaker_capture.py`真的一支bug(`enter_debugger`漏呼叫)修好,FDTXT_002 roster組成初步摸清——但這輪沒有真正解出任何一筆,誠實記錄

跟隨 §「利用今天已修好的battle autoplay改善,嘗試恢復 FDTXT_002」的計畫,新開一個
乾淨instance(`spk6`)、乾淨跑到ch01戰鬥瀏覽游標層,想針對box_index 55-60(敵方死亡
台詞,operand 5-10)跟部分17-31(operand含11)試著解。

**先修了一個真bug**:`fd2_speaker_capture.py`的`read_roster_datos()`直接呼叫
`H.mem_read_unit_array()`,**沒有先呼叫`H.enter_debugger()`**(`fd2_battle_autoplay.py`
的`snapshot()`早就有這一步,這支工具當初漏寫)——導致`--dump-roster`/`--resolve-todo`
兩條路徑一律回報「debugger未在時限內停住,拒絕讀取」,完全無法使用。補上跟`snapshot()`
同款的`enter_debugger()`→讀→`resume()` bracket後,`--dump-roster`正常運作。

**roster組成(戰鬥開始當下,count=24)**:idx0=索爾、idx1=悠妮(DATO 0x09)、
idx2=亞雷斯、idx3=蓋亞;idx4-11全部是DATO=0x60(**同一種泛用「盜賊」,PORT查無對應,
也沒有在doc40/doc49任何既有表找到0x60的怪物名**);idx12-23全部是DATO=0xff(空格,
代表援軍要到戰鬥後段才會出現)。

**為什麼這輪沒有真正登記任何一筆到`runtime_speaker_resolved.json`**:
1. operand 5-10(box_index 55-60,死亡台詞)跟operand 11(box_index 17/19)雖然
   現在都能查到「DATO=0x60,泛用盜賊」,但**這只回答了「這個roster slot裡站的是
   誰」,回答不了「這句死亡台詞真的是這個slot死掉時觸發的」**——本工具的
   `--confirm-text`安全機制正是為了擋這種落差(FDTXT_032/033曾經因為沒做這一步
   誤判過),而box_index 55-60的台詞需要**真的在戰鬥裡打死那個單位**才會出現在
   螢幕上,這輪沒有真的打過去(§13-§28那條調查線雖然已經證實能打出真實傷害,
   但這輪沒有把兩者接起來,單純只是dump了開場roster)。
2. operand 0x60沒有名字可查(不在PORT的0x00-0x1F英雄範圍,doc40/doc49也沒有
   泛用怪物名字表涵蓋這個id)——就算box_index跟roster slot對得上,能記錄的也只是
   「某個沒有名字的盜賊」,不是一個具體人名,價值有限。

**誠實現況**:這輪的**唯一確定成果是修好`fd2_speaker_capture.py`的debugger初始化
bug**,現在這支工具真的能用了。roster組成的觀察(idx4-11皆泛用盜賊、idx12-23是
援軍空位)是有效資訊,但**不構成「解出FDTXT_002任何一筆說話者」的證據**,沒有
寫入`runtime_speaker_resolved.json`,避免重蹈FDTXT_032/033那次「看起來解出來但
其實搞錯場景」的錯誤。下一輪如果要真的解box_index 55-60,需要真的打死一個idx4-11
的盜賊,截圖確認死亡台詞出現在螢幕上,用`--confirm-text`比對文字後才能記錄——
而且既然DATO=0x60沒有名字,記錄下來的價值也有限,可能不值得為了「泛用盜賊」
花一整輪去打真實戰鬥;操作4-13(box_index 4-13,疑似盜賊登場台詞)可能更值得
優先,因為這些不需要殺死敵人,可能在戰鬥剛開始的演出階段就會出現,只是這輪
沒有嘗試捕捉。
