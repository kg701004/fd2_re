# 35 — 全螢幕戰鬥演出繪圖機制(FIGANI 攻守動畫)

> 反組譯《炎龍騎士團2》FD2.EXE(DOS4GW LE,obj1 linear=file offset)的**全螢幕戰鬥演出**:
> 攻擊發生時切到的那張大圖畫面 —— 守方 / 攻方全身 FIGANI、戰場背景、狀態欄、斬擊與閃紅。
> 所有結論附反組譯位址佐證;runtime 才決定的值標「待確認」。
> 相關:doc 06(FIGANI 格式)· doc 31(FDICON 地圖小人,另一套)· doc 13(戰鬥選單)· doc 25(戰鬥事件)。

## 0. 兩個演出函式(別搞混)

| 函式 | 入口 | 參數 | 用途 |
|---|---|---|---|
| 單圖演出 | **0x28784** | 1 個 unit index | 顯示**單一**單位全身圖(施法/單體演出) |
| 攻守演出 | **0x28a6c** | **2 個** unit index(攻方、守方) | 攻擊的**對打**全螢幕演出(本篇重點) |

兩者 prologue 都是 Watcom 風格 `push <frameSize>; call 0x36cd7`(stack-probe):
- 0x28784:`push 0x54; call 0x36cd7`(0x28789),func 範圍 0x28784–0x28a6b `ret`。
- 0x28a6c:`push 0x64; call 0x36cd7`(0x28a71),func 範圍 0x28a6c–0x29116 `ret`。

> ⚠ 既有錨點把 0x287b5(`movzx esi,[ebx+7]`)當成「攻守演出」入口,實際它在**單圖** 0x28784 內;
> 真正的攻守雙圖演出是 **0x28a6c**(0x28ad6 `movzx eax,[ebx+7]` 攻方組、0x28ade `movzx eax,[esi+7]` 守方組)。

### 呼叫鏈(誰觸發演出)

`calls 0x28a6c`(相對 call 來源):

| caller linear | 傳參 | 意義 |
|---|---|---|
| **0x1561f** | `push [0x53c4b]; push ebx; call` → `0x28a6c(ebx, [0x53c4b])` | 攻擊執行流:**arg0=ebx=攻方 idx、arg1=[0x53c4b]=守方 idx** |
| 0x18fc6 | — | 另一觸發點(待確認) |
| 0x2c2aa | `mov [0x540ff],ecx; push 1; push 0; call` → `0x28a6c(0, 1)` | 先設演出 phase 旗標再呼叫 |
| 0x35435 | — | 另一觸發點(待確認) |

`calls 0x28784` → 唯一 caller 0x15195(單圖路徑,與 0x1561f 同一攻擊執行區 0x15xxx,符合「攻擊執行 0x15xxx」推測)。

**[0x540ff] = 演出 phase / 重繪旗標**(`refs 540ff` 找到 writer):函式外 0x25ac0、0x25b6f 設定;函式內 0x28ae8/0x28c15/0x28cdb/…/0x28ef1(設 1)讀寫。
語意:`0` = 第一次進場(載入資源 + 全畫面合成),非 0 = 後續增量幀(只重畫變動層)。動畫靠**重複呼叫 0x28a6c 推進**,phase 旗標決定這一幀做哪些事。

---

## 1. FIGANI 載入(組 × 3)+ buffer

- 攻方組 = `unit_attacker[+7]`(0x28ad6 → `[esp+0x10]`);守方組 = `unit_defender[+7]`(0x28ade → `[esp+0xc]`)。
  這是 battle FIGANI selector；map FDICON `0x127e0` 另讀 `unit+2`，不得稱為同一欄。
- **FIGANI 動畫 index = 組 × 3**:0x28c57 `mov edx,[esp+0x10]; shl eax,2; sub eax,edx`(= 組×4−組 = 組×3),
  再 0x28c78 `組×3`、0x28c99 `inc`(組×3+1)。**每組 3 個動畫**(待機 / 出招 / 受擊,+0/+1/+2;對映待確認),
  確認了既有結論「FIGANI = sprite組 × 3」。
- 載入經 **0x111ba**(資源解碼器,見 §6),descriptor = **0x52388**(FIGANI 動畫容器表):
  `0x111ba(0x52388, prevSlot, 組×3+k)` → 回傳該動畫的 frame 描述子 buffer。
- 解出的動畫描述子存:**[0x54117]=攻方、[0x5411b]=守方**(0x28e4a / 0x28e5b,經 `0x2bc9a` 後處理)。
  另 [0x53a49] / [0x53a5d] 為單圖路徑(0x28784)用的 FIGANI buffer(對映既有錨點)。
- 龍騎兵 / 飛行特例:0x28b72 檢查 `unit[+0x20]==0x13`(職業 0x13=龍騎士)或 `unit[+0x1f] in {4,5}` 且 `unit[+7]==0x1c` → 走特殊組路徑(`call 0x12e38` 換組)。

> 動畫描述子格式(0x2939d / 0x2935b 讀法):`byte[ebp]` = frame 數;`[ebp + i*4 + 8]` = 第 i 幀相對 offset;
> `byte[ebp+1]` = 類型旗標(0=靜態單幀走 BG 路徑,非 0=多幀動畫)。

---

## 2. 守 / 攻 blit 座標 + 縮放(最關鍵)

### 2.1 blit 原語 0x4e63d(原生尺寸,無縮放)

`0x4e63d(src, X, Y, dst, stride, transp)`(由 `ebp+8..ebp+0x1c` 取參,0x4e643 起):
```
esi = src                         ; 來源(自帶尺寸)
word[src+0]→[0x627b4] = 寬          ; 0x4e646 lodsw
word[src+2]→[0x627b6] = 高          ; 0x4e64e lodsw
ecx = X (ebp+0xc)
eax = Y (ebp+0x10);  edx = stride (ebp+0x18)
edi = dst (ebp+0x14);  edi += Y*stride + X      ; 0x4e663 mul / 0x4e665-667
transp = ebp+0x1c   (-1 = 用 RLE 透明跳過;否則色鍵)
```
**關鍵結論:`dst 位址 = dst + Y*stride + X`,圖以 src header 自帶的寬高原生繪製。整條 blit 路徑沒有任何 `imul`/`fild`/`fmul` 縮放運算。**
→ **守方較小、攻方較大不是 runtime 縮放,而是 FIGANI 美術本身就畫成不同尺寸**(景深感燒進素材)。
remake 對不準的根因即在此:該照各 frame header 的寬高 + 下面的座標貼,不要自己 scale。

### 2.2 座標來源

- **螢幕錨點常數 (X=0xa4=164, Y=0x9d=157)**:出現在 0x28f55(`0x4e63d(src, 0xa4, 0x9d, edi, 0x280, -1)`)與
  0x29164 的 figure/台座路徑(0x291b0/0x29268/0x29295)，**不是**狀態欄。這是演出區/單位圖的
  固定錨點(160×100 半屏中央偏下)。
- **figure 的螢幕貼圖錨點是固定常數 (X=0xa4=164, Y=0x9d=157)**,不是 `word[unit+0x40]`:
  - ⚠ 修正既有斷言:`0x29582 push [esp+0x50]` 因前面已 `push -1; push 0x280`(esp 下移 8),實際讀的是 frame local `+0x48`(=**dst work buffer**),**不是** `word[unit+0x40]`。`word[unit+0x40]` 在 `0x294ad` 讀進 `[esp+0x50]` 後是**餵給 `0x29f72` 的算式**,不是直接當 blit X。
  - 最終 figure blit 的螢幕座標寫死在合成處:`0x28f67`(主合成)、`0x29ded:0x29ea2`(==0 路徑):
    `0x4e63d(figureSrc, 0xa4, 0x9d, dst, 0x140, -1)` → **(164,157) 是 figure 的螢幕左上錨**(全 figure 共用此常數)。
- **⚠⚠ 重大修正(第一性原理追到底,2026-06-29):`word[unit+0x40]` = 當前 HP,不是「戰場格 X」!**
  舊斷言(把 +0x40 當座標)**錯誤,已推翻**。決定性兩證:
  - **血條鐵證**:`0x18c98 movsx ebp, word[esi+0x40]`(esi=[0x53a45]+idx×80)→ push 給 `0x18795`,
    算 `len = word[+0x40]×101 / word[+0x42]`(0x187ad imul 0x65 + idiv)。座標×101÷座標無意義,
    只有 **當前HP×101÷最大HP = 血條%長度** 才合理 → **+0x40=當前HP、+0x42=最大HP**。
  - **figure displacement 更正**：先前把 `0x29f72` stack locals 反推為 runtime
    `unit+0x48/+0x4a` 的螢幕投影座標，已被 command 17/18 的 direct writers 推翻：它們以
    `+0x22/+0x23` 暫時旗標對這兩個 word 套 15% 增幅，而 class synthesis 亦寫
    `+0x48/+0x4a/+0x4c/+0x4e` 作 derived AP/DP/HIT/EV，不能再用這些 runtime offsets 當座標。
    `0x2935b` 已直接閉合真正來源：descriptor 的 `frameIndex*4+8` relative pointer 指向單幀 header，
    其 `u16 +0/+2` 是每幀 X/Y，payload `+9` 交 `0x4e63d`。
  - **正確欄位**:**`+0x40`=當前HP、`+0x42`=最大HP、`+0x44`=當前MP、`+0x46`=最大MP**(spawn 0x10fe9 設 cur=max=滿血滿魔);
    figure displacement 是 frame metadata 的逐幀 X/Y；HP/MP 演出中被攻擊/施法改寫,狀態欄即時反映。
  - **寫入點**:spawn `0x10FE9`(`+0x40=+0x42=`HP、`+0x44=+0x46=`MP,值從 caller 參數來=該角色滿 HP/MP)、`0x1142A`(同款);
    戰鬥演出中 `0x2975A` 每幀寫 `word[unit+0x40]`——**= 被攻擊時 HP 抽乾的逐幀內插**(舊誤標「lunge 前衝 current X」);狀態欄血條即時跟著縮。
  - `0x114E4/0x1B821` 與 figure placement 的 exact ABI 需重新追查；先前把它們寫成
    `+0x48..+0x4e` screen bounding box 的斷言已撤回。
- **`0x29f72(攻方idx, 守方idx, &out)` = 戰鬥結果 resolver，非 lunge**:
  - `ebp`/`edi` = 雙方 unit(各 `idx*80`,base `[0x53a45]`)；直接讀攻方 `+0x48/+0x4c`、守方
    `+0x4a/+0x4e`（derived AP/DP/HIT/EV）、守方 current/max HP `+0x40/+0x42`，以及 item record。
  - 在 `0x1f183` gate 未通時，分別以 `0x12e38` control byte+1 索引 `0x51a12` AP 與
    `0x51a2a` DP 百分比，加入攻／守 derived stats；再以 `0x4e893` RNG 建立 hit/crit/damage 路徑。
    這也證實兩張 table 不是 figure direction/pose 微調表。
  - 輸出 struct 的 `+0/+4/+8/+0x10` 為結果旗標，`+0x14` 為最後 damage；`[0x53ec8]` 是由結果／
    unit fields 算出的 presentation 用量。它不輸出或讀取已證實的 figure screen coordinate。
  - → 撤回「figure 前衝幅度 = 雙方格距 × 動畫% × 方向微調」。figure 位移已由
    `0x2935b` frame metadata 的 X/Y header 閉合，不可借 `0x29f72` 命名。
- **frame 自帶 (dx,dy)**:figure 繪製 wrapper **0x2935b** 解單幀:
  ```
  eax = frameIdx*4 + descriptor          ; 0x2936a
  edx = descriptor + [eax+8]             ; 該幀資料 ptr
  word[edx+0]=幀X偏移, word[edx+2]=幀Y偏移 ; 0x2937a/0x2937d
  src 像素 = edx+9                        ; 0x2938f add eax,9
  → 0x4e63d(edx+9, 幀X, 幀Y, dst, stride, transp)
  ```
  → 每幀內嵌自己的 (dx,dy),**斬擊弧 / 出招前傾 / 受擊後仰就是逐幀換 (dx,dy)**。

### 2.3 翻轉 / 左右:**沒有 runtime 水平翻轉**,靠 `byte[unit+6]` 選合成路徑(已確認)

- **全 blit 家族不做水平鏡像**:`0x4e63d` 的 RLE 解碼只有前向 `stosb`/`movsb`/`rep movsb`(`0x4e6a7`/`0x4e6bd`/`0x4e6d3`),
  全檔唯一 `std`(反向)在 `0x373EB`(memcpy 輔助,與 blit 無關)。→ **攻 / 守 figure 不是同一張圖 runtime 翻轉,而是 FIGANI 美術各自畫好朝向**
  (與 §2.1「大小燒進素材」同理:朝向也燒進素材)。**remake 守方原圖已面右就別再翻**。
- **`byte[unit+6]` 分支(0x29536)決定走哪條合成路徑**(figure 本體 blit 兩路都用同一個 `0x2935b`,不翻):
  - `byte[unit+6]!=0` → `jne 0x295c3` 迴圈 → 收尾 `0x295f8` `call **0x29c90**`(BG 貼 (0,50)、figure 進 buffer 走 frame 內嵌 (dx,dy)、往一方向 slide-in)。
  - `byte[unit+6]==0` → `jmp 0x2969f` 迴圈 → 收尾 `0x296d4` `call **0x29ded**`(BG 貼 (0,50)、**figure 貼固定錨 (164,157)** `0x29ea2`、反方向 slide-in)。
  - → 兩路差在 **slide 進場方向** + **figure 錨點**(==0 用 (164,157),!=0 用 frame 內嵌 (dx,dy))→ 這正是**攻 / 守腳底 Y 不同**的程式來源
    (remake 量攻方腳 y≈175 / 守方 y≈150:一方錨在 157、一方走 frame dy;非統一 Y)。確切「哪邊是攻、哪邊 frame-dy 落在 150」需 runtime `byte[unit+6]` 對照,**機制已定、配對待確認**。
- **左 / 右 buffer**:`0x28dfd` 同檢查 `byte[unit+6]`,`0x28e05-0x28e16` 視之交換 `[0x54107]↔[0x54103]`(決定誰進左 / 右 BG buffer)。

---

## 3. 背景 BG 繪製 + 戰場→BG 對應

### 3.1 BG 多層載入 + blit

- 演出進場前,BG.DAT 由 **0x22d1b** 載入(既有錨點;0x2866x 區三次 `0x22d1b` 以 index 對載地形圖,在前置函式內)。
- 演出函式內,BG 分**多層**經 0x111ba(descriptor = **0x52381**,該位址本身就是字串 `"BG.DAT\0"` → 0x111ba 是「開 .DAT 取 entry[index]」)解出:
  - `0x54107`（`0x28CD4`，index＝章節表算出的變動值）、`0x54103`
    （`0x28DAA`，index 0）、`0x5410B`（`0x28DC4`，index 0）、`0x5410F`
    （`0x28DDE`，index 1）、`0x54113`（`0x28DF8`，index 2）。
  - → BG.DAT 至少 **3–5 個 entry**(idx 0/1/2 + 章節索引層),遠景 / 近景 / 土台分層。
- **BG blit 座標**:`0x4e63d(BGsrc, X=0, Y=0x32=50, dst, stride, -1)`:
  - 0x28d42(`[0x54107]`)、0x28e27(`[0x54103]`),stride 0x140=320;slide 合成 `0x29c90`/`0x29ded` 再把 `[0x5410b/0f/13]`(idx 0/1/2)循環貼於 (0,50)。
  - → **背景與各層都貼在 X=0, Y=50,寬 320**(整屏寬;上方 50px 與下方留給狀態 UI）。

### 3.2.5 已驗 battle fixture：我方背影+台座／敵方正面（不可全域外推）

- 已驗收的亞雷斯／盜賊 capture 是從我方背後看戰場：我方背影並帶TAI台座，
  敵方正面。這證明該fixture的合成選擇，不足以證明所有角色、特殊戰鬥或
  `unit+6` raw分支永遠等同高階陣營。
- 在這個fixture中台座跟隨我方slice，而不是當回合攻／守；跨caller規則仍須
  由TAI selector與`unit+6` writer驗證。
- 故 orig_05:亞雷斯(藍衣**背影**、腳下大 dither 土台)= **我方**;盜賊(紅頭巾**正面**)= **敵方**。
  (先前 doc 用「攻方 / 守方」描述左右是**誤框架**,正名為「我方(背影,右,有土台)/ 敵方(正面,左)」。)
- remake 對映:我方單位用背影 FIGANI 幀 + 腳下貼 **TAI.DAT 台座**(見 §3.3);敵方用正面 FIGANI 幀、無台座。

### 3.3 我方腳下「土台」= **TAI.DAT 菱形台座素材**(反組譯確認),非 FIGANI 自帶、非 BG 層、非程式畫

- **反組譯鐵證**:figure 演出函式 `0x29164` 在 `0x28c46` 呼叫 `0x111ba("TAI.DAT"@0x52393, prevSlot, idx)`
  載入台座圖,**與 figure 一起淡入畫在腳下**(見 §4.0)。→ **土台是 TAI.DAT 獨立 sprite,不是 FIGANI 圖的一部分**。
- **TAI.DAT 格式 / 內容**:sprite-RLE(FIGANI codec 家族);**TAI_004=154×42、TAI_005=155×42 = 菱形透視台座**
  (worklist `91` 早記錄「TAI.DAT=WxH sprite-RLE,如 155×42」);台座 idx 由 `byte[unit+6]`/職業算(預設 3)。
- **靜態前提**:戰鬥合成只走 `0x4e63d`(blit)/`0x11eb0`(present)/`0x11d40`(色盤),無 fillrect/circle → 土台必是素材。
- **刪除的錯誤斷言**(本輪推翻,省 token):
  - ❌ **「土台 = FIGANI_013_f01 自帶 dither 橢圓」= 誤判**:FIGANI 圖底那圈 dither 是 sprite 自帶的**腳下小陰影**,
    **不是** orig 顯示的綠色大台座;真正的大台座是 `0x29164` 獨立載入 blit 的 **TAI.DAT**。我把小陰影誤當主土台,繞了一圈。
  - ❌ 「土台 = BG.DAT 前景層 `[0x5410b/0f/13]`」:該三層由 `0x111ba("BG.DAT", idx=0/1/2)` 載入 = `BG_000/1/2`
    = 垂直藍漸層(`3f4f→3f4e` 每列遞減,反組譯 + dump 雙證),是藍底 / 捲簾,非土台。
  - ❌ 「土台 = FIGANI_012 自帶小 dither」:用錯幀。
- **remake 對映**:抽 **TAI.DAT 台座 sprite**(`decode_figani`/`decode_sprite` codec)貼我方腳下,
  **不要 drawEllipse、也不要倚賴 FIGANI 自帶 dither**;台座顯示為綠是 TAI 素材本身的顏色(疊草地)。
  **TAI 確切 entry / 顏色 / 對齊位置待 decode 驗證**(worklist 第 6 輪步驟 1)。

### 3.4 攻擊白斬擊弧 = FIGANI 攻擊幀自帶,非程式畫(視覺確認)

- orig_05 那道大白色揮砍弧**燒在 `FIGANI_013` 攻擊幀的 sprite 像素裡**(連續幀畫出揮劍殘影),
  不是 runtime 用 vector / 畫線疊的。remake **不要自己用 `vector.StrokeLine` 補白弧**(舊版這樣做,已移除),
  畫對攻擊動作幀(組×3+1)弧就自然帶出。

### 3.2 戰場 → BG 參數對應

- **章節參數表 0x52363**:`[0x53c03]`(= 章節 byte,既有錨點)當 index 取 `byte[chapter + 0x52363]`:
  0x28b61 `mov edx,[0x53c03]; movzx edx, byte[edx+0x2363]` → `[esp+0x18]`。
  表值 = `[4, 9, 14, 18, 14, 0, 2, 4, 6, 8, 10, …]`(0x52363 起,前 6 個是章節用)。
- 此值參與 figure / BG 選擇分支(0x28b89 與龍騎兵特例聯動),**確切語意(選哪張 BG / 色盤)待確認**;
  但「**戰場→演出參數由章節 [0x53c03] 索引 0x52363 表**」這條對應已確認。
- 既有錨點 BG_004 森林 320×100:與本處「BG 寬 320、貼在 y=50」尺寸吻合。地形→BG index 的細部對應待續(追 0x22d1b 的 index 參數來源)。

---

## 4. 狀態欄(血條框)繪製 — 真正函式 0x18c6d(2026-06 嚴格 RE 修正)

> ⚠ **重大修正:0x29164 不是狀態欄函式**(舊 §4 標錯)。0x29164 畫的是 **figure 全身圖 + 腳下台座(TAI.DAT)** 的淡入演出(見 §4.0)。
> 真正畫「深藍底框 + 立體邊 + 名字 + LV + HP/MP 條 + 數值」的是 **0x18c6d**(見 §4.2)。
> 三元素拆解結論(各附位址):**框 = 素材 sprite、HP/MP 條 = 程式畫(寬度算出來)+ 逐欄 cell、文字 = 點陣字 / 數字 cell 素材**。

### 4.-1 [z-order] 狀態欄先畫、figure 後畫 → figure 蓋住狀態欄(已確認)

演出主函式 0x28a6c 內的繪製順序(反組譯 call 序):
- **狀態欄(0x2a289→0x18c6d)在 `0x28ce7`、`0x28d62` 先畫**;
- **figure(0x29164 全身圖+台座、0x2939d renderer)在 `0x28e76`、`0x28e9a`、`0x28ee0` 後畫**。
- → **figure z-order 高於狀態欄**:動畫格完整、狀態欄被 figure 蓋住一部分(orig_05 亞雷斯的劍穿過我方欄上緣即此)。
- remake 對映:`drawBattleScene` 順序必須 **BG → 狀態欄 → figure**(figure 最後畫蓋上),別反過來。
- 另:**我方欄上緣離畫面頂有間隔**(非貼頂)、敵方欄離 150 線有 ~3px@320 間隔(對照截圖量)。

### 4.0 0x29164 = figure + 台座(TAI.DAT)淡入,非狀態欄

`0x29164(unitIdx, stride, dst, …, platformFrame, figureSrc)`(攻守各一次,caller 0x28e76 / 0x288f3):

- prologue `push 0x2c; call 0x36cd7`;`esi=[0x53a45]+idx*80`;`movzx ebx, byte[unit+6]`(0x2918a)選兩條對稱路徑(左半 / 640-寬右半 off-screen buffer)。
- **figure 全身圖**:`0x4e63d(figureSrc, X=0xa4=164, Y=0x9d=157, …)`(0x291b0 / 0x29268 / 0x29295)— 與 §2.2 figure 錨點一致。
- **台座(platformFrame)**:`0x2935b(platformFrame, 0, dst, stride, -1)`(0x291cf / 0x29247)貼一張 frame。
  **platformFrame 來自 TAI.DAT**:0x28c46 `0x111ba("TAI.DAT"@0x52393, prevSlot, idx)`(idx 由 byte[unit+6]/職業算,預設 3)。
  TAI.DAT = LLLLLL 容器、**53 個 ~155×42 菱形台座 sprite**(7-byte 空槽佔位另計);解出來是**透視菱形格台座**(orig 截圖右下藍 figure 腳下那塊綠色台座)。
  → 舊 §4「name/LV/HP/MP 經 0x2935b 以幀方式貼」**錯**:0x2935b 在此貼的是台座,不是文字。
- **8 次迴圈 + `0x11d40(0, 0xff, esi*6)`**(0x291f9 esi=8→0)= **figure/台座的色盤淡入(brightness ramp 0→48)**,每圈 `0x11eb0` present 一次 → 進場時 figure 由暗轉亮。
  → 舊 §4 / §5「HP 條 = 色盤寫入 0x11d40」**錯**:這個 0x11d40 迴圈是 figure 淡入,跟 HP 條無關(HP 條在 0x18c6d 用程式畫,見 §4.2)。

> TAI = 台(台座 / dais),非「態(狀態)」。視覺與反組譯雙重確認(155×42 菱形 + 0x29164 貼在 figure 同函式)。
> 這也補充 §3.3:figure 腳下那塊 dais = TAI.DAT sprite(由 0x29164 經 0x2935b 貼),不是 BG 層、不是純 FIGANI dither(§3.3 的「圓圈/土台」歸屬需併此重看)。

### 4.1 視覺對照(orig_05 放大)

放大 orig_05 攻 / 守欄(`_orig_atkbar` / `_orig_defbar`):
- **底框**:深藍底 + **左上亮白、右下暗的 raised bevel 立體邊**(光源左上);半屏寬;敵欄右上、我欄左下。
- **內容**:名(白字,左上)、`LV‧NN`(白字右上,僅我方單位有)、`HP`/`MP` 淺藍標籤、HP **亮黃**長條 / MP **暗紅**長條、數值(白字右對齊)。

### 4.2 狀態欄繪製器 0x18c6d(三元素拆死)

**呼叫鏈**:演出函式 0x28a6c 在 0x288a9 / 0x28ce6 `call 0x2a289` →

- **0x2a289 = 算欄位螢幕座標 + 呼叫繪製器**:`movzx eax, byte[unit+6]`;`==0 → off=0xc080`(= work 偏移 0xc080,/0x140=row154 → **(x=0, y=154) 左下**,我方 盜賊 欄)、`!=0 → off=0x5ab`(/0x140 → **(x=171, y=4) 右上**,敵方 亞雷斯 欄);章節 0x18 + unit 0x11 特例強制 0xc080。`dst = bufBase + off`;`call 0x18c6d(dst, stride=0x140, unitIdx)`。
- **0x18c6d** body 0x18c6d–0x18d87:`esi=[0x53a45]+idx*80`;`ebp=word[unit+0x40]`、`[esp+8]=word[+0x42]`、`[esp+4]=word[+0x44]`、`[esp]=word[+0x46]`。

**① 框 / 底框 + 左上亮白立體邊 = 素材 sprite(blit)**
- `eax=[0x53a81]; eax+=[eax+0x5e]`(取 UI 容器內的面板底圖 sub-resource)→ `call 0x4e8af(dst, panelBgSprite, stride)`(0x18cbb-0x18cc1)。
- **0x4e8af = RLE 逐列 blit 原語**(`lodsw`寬、`lodsw`高、逐列 `call 0x4e916` 解 RLE `stosb`、`add edi,stride`)。姊妹 0x4e8e1 = 水平鏡像版(`dec edi`)。
- → **整塊面板背景(深藍底 + bevel 立體邊 + 可能含 "HP"/"MP"/"LV" 標籤字)是一張預渲染 sprite,blit 上去,不是程式畫線/填色**。來源 = 全域 UI 容器 `[0x53a81]` 的 +0x5e entry(`[0x53a81]` = FDOTHER.DAT 級 UI sprite 容器,loader 待確認;由 digit/bar/面板共用此容器佐證)。
- → **修正 §4.1 舊註「bevel 來源未確認 / remake 用程式 bevel 近似」**:bevel 是素材,remake 應改 blit 面板 sprite(FDOTHER 內),別再用 drawBattlePanel 程式畫。

**② HP / MP 血條 = 程式畫(長度算出來)+ 逐欄 cell blit,非色盤、非單張條 tile**
- HP 條:`0x18795(x, dst, 0x17, curHP=word[+0x40], maxHP=word[+0x42])`(0x18cc9);MP 條:`0x18795(x, dst, 0x1a, curMP=word[+0x44], maxMP=word[+0x46])`(0x18ce6)。`0x17/0x1a` = 兩條的 Y 列。
- **0x18795 算填充長度**:`if maxHP==0 return; if curHP==0 len=0; else len = curHP*0x65/maxHP + 1`(0x65=101)→ **條長 = 當前/最大 × 101 + 1 像素欄**;再 `call 0x17d6f` 畫。
- **0x17d6f 逐欄畫條**:`ebp=len`;前 `len` 欄 `call 0x1685c(x+i, y, [0x53a81], colorIdx)` 用「傳入的條色 cell」;`len..101` 欄改用**空槽 cell index 0x1d**(暗版),端點 0x1e / 0x5d 收尾。
- **0x1685c → 0x4e9bb**:`edx=[0x53a81]; edx += [edx + colorIdx*4 + 6]`(容器查 entry)→ `0x4e9bb` 逐列 `rep movsb` blit 該欄 cell。→ **條的像素是 [0x53a81] 容器裡的 1px-寬漸層欄 cell(素材),但「畫幾欄」由 HP 比例算(程式)**;空槽 = index 0x1d cell。
- **血條長度來源釘死**:`unit+0x40 = 當前 HP`、`+0x42 = 最大 HP`、`+0x44 = 當前 MP`、`+0x46 = 最大 MP`(由 0x18795 的 `cur*101/max` 推得;spawn 時 0x10fe9 把 +0x40=+0x42、+0x44=+0x46 設成同值=滿血滿魔)。
  > ✅ **衝突已釐清(第一性原理追到底)**:`+0x40/+0x42/+0x44/+0x46` = **HP/MaxHP/MP/MaxMP**(血條算式鐵證)。
  > 舊「戰場格 current/home X/Y」標法錯誤；其後把 figure lunge 位置改標為
  > `+0x48/+0x4a`（螢幕投影）的說法也已撤回，
  > `0x29f72` 雖讀 +0x40 但沒拿去算位置。詳見 §2.2 開頭「重大修正」框。
- → **修正 §4/§5 舊註「HP 條 = 色盤動畫 0x11d40」**:HP/MP 條是 0x18795/0x17d6f 程式畫(逐欄填),色盤 0x11d40 那段是 0x29164 的 figure 淡入,兩者無關。

**③ 名字 / LV / 數值 = 素材文字 cell(點陣字 + 數字 cell),非 TTF、非單張預渲染整條**
- **角色名(亞雷斯 / 盜賊)**:`0x15f84([0x53a7d] 字串表, nameIdx=byte[unit+8]+1, dstAddr, …, 0xcd, 0x4c)`(0x18d61-0x18d7f)。
  0x15f84 = 字串排版器:`esi=字串表; eax=index; movsx eax,word[esi+idx*2]; esi+=eax`(word-offset 字串表)→ 逐字 `call 0x16559`。
  **2026-07-27 official IDA correction**：一般字不是走 `0x16559/[0x53a85]`。
  `0x15f84` 對每個普通 word 呼叫
  `0x4ea2a([0x53a75],glyph,dst,stride,foreground,shadow,background)`；
  `[0x53a75]` 是 boot 載入的 **FDOTHER.DAT #4 16×16 1bpp font**。
  `0x16559(index)` 才會從目前 DATO `[0x53a85]` 的 offset table取 mouth
  frame並以 `0x4e8af/0x4e8e1` 重貼 portrait，只由對話控制／嘴型路徑呼叫。
  → **名字 = 16×16 1bpp glyph + 程式指定 foreground/shadow/background**，
  不是 TTF、不是 DATO sprite、不是整條預渲染。
  → **remake 名字偏小的修法**:名字用 16px-class 點陣字(每全形字 16px 寬),別用 TTF 縮放;名字寬 ≈ 字數 × 16(狀態欄路徑 0x15f84 的實際 advance 可能略窄,精確值待確認)。
- **數值(LV-NN / HP 028 / MP 000)**:`0x187d6` = 數字繪製器(`call 0x377d9` itoa → 逐位 `[0x53a81]` 容器取 **digit cell**,`imul eax,ebx,6` → **每位數字 cell 寬 6px**,blit 經 0x1685c/0x4e9bb)。
  - LV/狀態值:0x18d02 `0x187d6(…, byte[unit+0x21], 0x1f, mode2)`(mode2 上限 99);HP/MP 數值:`0x1875d`(0x18d25/0x18d42)→ 內部 `cur==max ? 色0x1f : 色0x2a` 再 `call 0x187d6`(滿血 / 非滿血換色)。
  - → **數字 = 6px-寬預渲染 digit cell 素材**([0x53a81] 容器),itoa 後逐位 blit;不是字型。
- **"HP" / "MP" / "LV" 標籤字**:內含在 ① 的面板底圖 sprite 裡(已視覺確認:框圖 #22 自帶 HP/MP/LV‧ 標籤,見 §4.2.5)。

### 4.2.5 [已破解] UI 容器 = FDOTHER#5 "LMI1" directory（codec 必須依 caller 決定）

`[0x53a81]` = `0x111ba("FDOTHER.DAT", [0x53a81], 5)` 載入的 **FDOTHER 第 5 個資源**,本身是 **"LMI1" 子容器**(doc 14 對話框框圖同源):
- **LMI1 結構**:`char[4]"LMI1"` + `uint16 N`(sub-resource 數,FDOTHER#5=138) + `uint32[N] offset` + 各 sub-resource(`uint16 w, uint16 h, codec 資料`)。
  - 2026-07-25 player-asset regression 更正：offset 是各 entry 的**開始**位址，不是壓縮資料的嚴格 end；
    `0x4e916` 依目的 `w×h` 停止，最後一段 repeat 可跨下一 entry 的 offset。解析器須以容器末端為
    唯一 source bound，不得以 `offset[i+1]` 截斷資料並誤判原版 #5 為 malformed。
- **`0x4e916` 像素 codec（僅適用其 caller 選到的 entries）** —— **本輪關鍵破解,跟 FIGANI/TAI 的 4-mode、doc05 image-RLE 都不同**:
  ```
  讀控制 byte c:
    c <= 0xC0 : c 本身就是一個像素值(literal 單 px)        ; 0x4e91e cmp 0xc0 / 0x4e922 xor ah,ah
    c >  0xC0 : run,長度 = c - 0xC0,後跟 1 個像素值,重複  ; 0x4e925 sub ah,0xc1 / 0x4e92a lodsb
  (透明 = palette index 0;run 跨行,線性解 w*h;純 literal 小圖等同 raw)
  ```
- **`0x4e916` blit 端**:`0x4e8af`(正向)/ `0x4e8e1`(水平鏡像 `dec edi`)逐列呼叫 `0x4e916` 取像素 `stosb`；不得據此推論整個 LMI1 directory 都走這條 codec。
- **⚠ LMI1 容器內混用兩種 codec**(對應兩條 blit 路徑,踩過):
  - 大圖(框 #20/21/22)= **0x4e916 codec**(上述),blit 走 `0x4e8af`;
  - 小 cell(血條欄 / 數字)= **FIGANI 4-mode sprite RLE**(doc06),blit 走 `0x1685c→0x4e9bb`。
  - 用錯 codec 解出來是彩色雜訊——先看該資源的 blit 端(0x4e8af vs 0x4e9bb)決定 codec。
- **狀態欄用到的 sub-resources(視覺+模板匹配驗證,err=0 像素全等)**:
  - **框 = #22(149×42)**:深藍底 + 左上亮白 raised bevel + 「LV‧」+「HP」「MP」標籤 + 血條紅槽,**全燒在這張素材**(`[0x53a81]+0x5e` → #22)。框內槽 native:HP y22–26、MP y31–35、槽 x21–123。
  - **血條 cell = #27–30(1×5)**:純色漸層欄(#27/28 黃=HP、#29/30 紅=MP/空槽);raw(值全 ≤0xC0)。
  - **數字 digit cell(6×8,「1」5 寬)三套色**:**#31–40 = 白/藍影 0–9(戰鬥狀態欄用)**、#42–51 = 白/綠、#119–128 = 白/黃橘(`0x1875d` 滿血/非滿血換色的素材面)。
  - **數字排版(模板匹配 orig 定位)**:advance 7px;首位數字 local 座標 LV(132,4)/HP(126,21)/MP(126,30)。
  - **框在畫面上是 149×42 原生 blit**(非拉伸):敵方欄 @320 (0,154)、我方欄 (171,4)(右緣貼齊 320)。
- **工具**:`tools/decode_lmi.py`(列 sub-resource / 解 PNG,index0 透明)。**remake**:抽 #22 框貼上(`remake/assets/ui/panel.png`),名字 / LV / 血條填充 / 數值疊在框上(槽座標見上)。
- ⚠ **palette 陷阱(踩過)**:FDOTHER#0 調色盤是 **VGA DAC 6-bit(0–63)**(doc05),任何新解碼工具都要 `(v<<2)|(v>>4)` 轉 8-bit,否則圖整體暗 4 倍(狀態欄底色 (14,21,38) vs 正確 (56,85,154))。

### 4.3 三題結論速查

| 元素 | 素材 or 程式畫 | 位址 / 來源 |
|---|---|---|
| 框 + 深藍底 + 立體 bevel | **素材 sprite(blit)** | 0x4e8af blit `[0x53a81]+0x5e`(UI 容器面板底圖);繪製器 0x18c6d,座標器 0x2a289(byte[+6]: 0→(0,154)、≠0→(171,4)) |
| HP / MP 血條 | **程式畫長度 + 逐欄 cell** | 0x18795(len=`cur*101/max+1`)→ 0x17d6f 逐欄 0x1685c blit `[0x53a81]` 漸層欄 cell;空槽 cell 0x1d;HP=unit+0x40/+0x42、MP=+0x44/+0x46 |
| 角色名 | **16×16 1bpp 點陣 glyph** | 0x15f84 排版 → 0x4ea2a blit `[0x53a75]` FDOTHER#4 font；字串表 `[0x53a7d]`,index byte[unit+8]+1；caller指定前景/陰影/背景色 |
| LV / HP / MP 數值 | **6px digit cell 素材** | 0x187d6 itoa→逐位 blit `[0x53a81]` digit cell(寬6);0x1875d 滿血換色 |
| 台座(figure 腳下) | **素材 sprite** | TAI.DAT(0x52393)entry,0x29164 經 0x2935b blit;155×42 菱形 dais |

### 4.1 視覺對照(orig_05 放大)+ remake 對映

放大 orig_05 攻 / 守欄(`_orig_atkbar` / `_orig_defbar`):
- **底框**:深藍底 + **左上亮白、右下暗的 raised bevel 立體邊**(光源左上);半屏寬(160×40@320,攻右上 / 守左下)。
- **內容**:名(白字深描邊,左上)、`LV‧NN`(白字右上)、`HP`/`MP`(淺藍標籤)、HP **亮黃**長條 / MP **暗紅**長條(幾乎佔欄寬)、數值(白字右對齊)。空槽 = 該條色的暗版(暗黃 / 暗紅),非統一黑。
- **⚠ 框 bevel 來源未 RE 確認**：§4 已證實名字走 glyph、數值走 digit cell、
  HP／MP 條由 `0x18795→0x17d6f` 程式逐欄繪製；但**底框＋bevel 是預渲染
  素材圖塊還是程式畫，尚未追**。
  remake 暫用程式 bevel(`drawBattlePanel`:深藍底 + 左上亮 / 右下暗 2px 邊 + 暗槽=色暗版)近似 orig 視覺;bevel 規則純色非紋理,屬合理近似,**確認是素材後再換素材**。

---

## 5. 動畫階段機制(windup → swing → impact → standoff)

- **驅動**:phase 旗標 **[0x540ff]** + **重複呼叫 0x28a6c**(每幀一次);非「一次畫完整段」。
  進場 phase=0(載資源 + 全合成,0x28e3e 區算 [0x54117]/[0x5411b]),之後 0x28ef1 設 [0x540ff]=1 走增量。
- **進度百分比**:figure renderer **0x2939d** 內 0x2946a `call 0x4e893` → 0x2947b `idiv 100`(`mov ebx,0x64; idiv`),
  取餘數判斷階段(`cmp edx,3` < 3 時 `[esp+0x4c]=2`,多畫一層)→ **動畫進度以 0–99% 表示,百分比決定當前幀 / 疊層**。
- **幀迴圈**:0x2939d 以 `byte[ebp]`=幀數迴圈(0x29409-0x29424)；在 phase gate 下先呼 0x29f72
  取得戰鬥結果／階段旗標，再由 0x2935b 貼 frame；不可把該 resolver 當位移輸出。
  幀的 (dx,dy) 內嵌(§2.2)→ **swing 斬擊弧 = 逐幀位移 + 換幀**。
- **idle / fallback 描述子**:0x2939d 進場 `rep movsd` 從 **0x5255f**(6 dword)與 **0x52577**(6 dword)複製預設描述子到區域 frame
  (0x293cf / 0x293df)→ 沒有真實動畫時的**待機姿態 fallback**。
- **閃紅 / figure 淡入 = 色盤操作,不是重畫像素**:
  - **0x11d40** 是 VGA DAC 寫入迴圈:`push 0x3c8 / push 0x3c9; call 0x37795`(0x11d5c / 0x11d73)→
    out 到埠 **0x3c8(palette index)/0x3c9(palette data)**。0x37795 = DAC 埠寫入原語。
  - 同手法在 0x28784 / 0x286dd 的 fade-in 迴圈(用 0x53a65 色表插值),以及 0x29164 的 figure/台座淡入(`0x11d40(0,0xff,esi*6)`,brightness ramp,見 §4.0)。
  - → **守方受擊閃紅 = 改色盤**(把該圖用色暫時拉紅再復原);效能極低成本。
    精確的「閃紅幀數 / 色值序列」待確認(需追 0x37795 的色值來源表)。
  - ⚠ **修正**:**HP 條變化不走色盤**。HP/MP 條是 0x18c6d 的程式畫(0x18795 算長度 `cur*101/max+1` → 0x17d6f 逐欄填),見 §4.2;舊註「HP 條亦走 0x11d40 色盤」已刪。
- **standoff**:演出結束 0x290xx 釋放所有 buffer(0x28fc1-0x2900e 連續 `0x37416` free)、復原色盤(0x290b8 `0x375c0`)、`0x11cac` 還原畫面。

---

## 6. 螢幕座標系(確認)

| 量 | 值 | 出處 |
|---|---|---|
| 螢幕寬 | 0x140 = 320 | 0x28f3c / 0x4e63d stride 參數 |
| 螢幕高 | 0xc8 = 200 | 0x28f37 / 0x11eb0 rows |
| VGA framebuffer | 0xa0000 | 0x28945 / 0x28fb4 |
| **work buffer stride** | **0x280 = 640** | 0x28f47 / 0x28f57 / 0x2935b |
| present 來源寬 | 0x140 = 320 | 0x11eb0 bytesPerRow |

- **work buffer 是 640 寬、但只 present 左半 320**:`0x11eb0` 每列 memcpy 320 byte、來源 stride 640、200 列 → VGA 320×200。
  雙倍寬 work buffer(`lea ebx,[edi+0x140]` 0x2929 系列存取右半)疑作**off-screen 預備區**(下一幀 / 滑入的 figure 先畫右半再捲入),
  具體用途待確認,但「**work stride 640、可視 320**」這條已確認 → remake 若用單寬 buffer 要注意座標換算。
- present 原語 **0x11eb0**(`rows, dstStride, src/dst, srcStride …`,逐列 `0x373c4` memcpy):BG→work、work→VGA 都走它。

---

## 7. 函式 / 位址速查

| 位址 | 角色 |
|---|---|
| 0x28784 | 單圖演出(1 unit) |
| **0x28a6c** | **攻守演出主函式(2 unit)** |
| 0x29164 | **figure 全身圖 + 台座(TAI.DAT)淡入**(非狀態欄;舊標錯,見 §4.0) |
| **0x2a289** | **狀態欄座標器**:byte[+6] → off 0xc080=(0,154)/0x5ab=(171,4);`call 0x18c6d` |
| **0x18c6d** | **狀態欄(血條框)繪製器**:框 sprite + HP/MP 條 + 名 + 數值(§4.2) |
| 0x4e8af / 0x4e8e1 | RLE 逐列 blit 原語(正向 / 水平鏡像);面板底圖 + glyph 都走它 |
| 0x18795 | 血條長度算 + 畫(`len=cur*101/max+1` → 0x17d6f) |
| 0x17d6f / 0x1685c / 0x4e9bb | 逐欄畫條(查 [0x53a81] cell → 逐列 rep movsb);空槽 cell 0x1d |
| 0x15f84 / 0x4ea2a | FDTXT 排版 / FDOTHER#4 16×16 1bpp glyph blit |
| 0x16559 | 從目前 DATO `[0x53a85]` 取 mouth frame重貼 portrait；不是一般 glyph renderer |
| 0x187d6 / 0x1875d / 0x377d9 | 數值繪製(itoa → 6px digit cell @ [0x53a81];0x1875d 滿血換色) |
| 0x2935b | 單幀 figure/台座 貼圖 wrapper(解 frame header dx/dy → 0x4e63d;dst/stride/transp 由 caller 傳穿) |
| 0x2939d | figure 動畫 renderer(幀迴圈 + 百分比進度;0x29536 依 byte[unit+6] 分兩合成路徑) |
| **0x29f72** | **戰鬥結果 resolver**：derived AP/DP/HIT/EV、HP、item record、terrain table、RNG → hit/crit/damage flags 與 presentation value；非 lunge coordinate helper |
| 0x29c90 | 合成路徑 A(byte[unit+6]≠0):BG (0,50) + figure 走 frame (dx,dy) + slide-in 方向 A |
| 0x29ded | 合成路徑 B(byte[unit+6]==0):BG (0,50) + **figure 固定錨 (164,157)**(0x29ea2)+ slide-in 方向 B |
| 0x114e4 / 0x1b821 | figure placement / derived-field interaction待重判；不得再命名 `+0x48..+0x4e` 為螢幕投影 |
| 0x10fe9 / 0x1142a / 0x250b1 | unit 格座標寫入 / 布陣 / 演出後復位(+0x42→+0x40) |
| 0x4e63d | blit 原語(原生尺寸 RLE,dst+Y*stride+X) |
| 0x11eb0 | 矩形 present(逐列 memcpy,work↔VGA) |
| 0x11d40 | VGA DAC 色盤寫（閃紅／figure 淡入／fade，ports `0x3c8/0x3c9`）；HP／MP 條不走此路徑 |
| 0x111ba | 資源解碼器:`(descriptor, prevSlot, index)` → 解 entry[index],釋放 prevSlot,回新 buffer |
| 0x22d1b | BG.DAT 載入(前置) |
| 0x4e893 | 動畫進度來源(被 idiv 100) |
| 0x37795 | VGA DAC 埠寫入原語 |

### 關鍵 descriptor / 變數
| 符號 | 意義 |
|---|---|
| 0x52381 | BG 多層 descriptor(0x111ba 用) |
| 0x52388 | FIGANI 動畫 descriptor(index = 組×3+k) |
| 0x52393 | **"TAI.DAT" 字串**(台座容器,53× ~155×42 菱形 dais sprite;0x29164 經 0x2935b 貼於 figure 腳下) |
| [0x53a81] | **FDOTHER.DAT resource #5** 的 LMI1 UI directory；boot `0x25c97` 明確呼叫 `0x111ba(...,5)`，不是待確認來源 |
| [0x53a7d] / [0x53a85] | `[0x53a7d]` boot 載入 FDTXT.DAT #0；`[0x53a85]` 是會被 caller 重載的工作指標（例如 `0x17eef` 依 unit `+7` 載 DATO portrait），不可跨 scene 固定命名成單一容器 |
| 0x52363 | 章節→演出參數表 `[4,9,14,18,14,0,…]`(`[0x53c03]` 索引) |
| 0x5255f / 0x52577 | idle / fallback 動畫描述子(各 6 dword) |
| [0x53a45] | 單位陣列基底(每單位 80 byte) |
| [0x540ff] | 演出 phase / 重繪旗標 |
| [0x54117] / [0x5411b] | 攻方 / 守方 FIGANI 動畫描述子 buffer |
| [0x54107]/[0x54103]/[0x5410b]/[0x5410f]/[0x54113] | BG 各層 buffer |
| [0x53c03] | 當前章節 |
| [0x53c4b] | 守方 unit idx(0x1561f 傳入) |
| unit[+7] | battle FIGANI resource selector（`×3`）；非 map FDICON `unit+2` selector |
| unit[+0x40]/[+0x42] (word) | **當前 HP / 最大 HP**(0x18c6d 血條 `cur×101/max` + 第一性原理釘死;spawn 0x10fe9 設 cur=max)。✅ 已推翻舊「戰場格 X」誤標 |
| unit[+0x44]/[+0x46] (word) | **當前 MP / 最大 MP** |
| unit[+0x48]/[+0x4a] (word) | **derived AP / DP**（class synthesis `0x1b750` 與 command 17/18 的 15% modifier writers）；非螢幕座標 |
| unit[+0x44]/[+0x46] (word) | **當前 MP / 最大 MP**(同上;舊「戰場格 Y」標法推翻) |
| unit[+8] | 角色名 / 職業 index(0x18d73 `byte[+8]+1` 查名字表 [0x53a7d]) |
| unit[+0x21] | 狀態欄顯示的等級 / 數值(0x18d06 餵 0x187d6,mode2 上限 99) |
| unit[+0x48]/[+0x4a]/[+0x4c]/[+0x4e] (word) | derived AP / DP / HIT / EV；先前 screen bounding-box 斷言已撤回 |
| unit[+6] | 攻 / 守旗標:選合成路徑(0x29c90 vs 0x29ded)+ 左右 buffer 交換(0x28e05) |
| [0x5018d] | 1.15 double 常數；與 transient modifier / renderer 的精確關係待重判 |
| 0x51a12 / 0x51a2a | map HUD `0x1acf3` 的地形 AP / DP 百分比表，索引為 FDSHAP control byte+1；已驗證 0→(+5,0)、1/5→(0,0)、2/3→(-5,+10)、4→(-5,-5) |
| [0x53ec8] | `0x29f72`相關combat-result／presentation state；下游語意尚未閉合，不是已證實的縮放或figure X座標(**2026-08-19 更新**:下游語意已由 `27` §5 反組譯閉環為單次行動經驗值暫存累加器,`0x29f72` 即本輪 project 內編號 `0x2f7b6`,細節見該文件) |

---

## 8. 六項成果摘要 + 待確認

1. **入口 + 呼叫鏈** ✅:單圖 0x28784(caller 0x15195)、攻守 0x28a6c(caller 0x1561f 傳 `攻方ebx, 守方[0x53c4b]`,另 0x18fc6/0x2c2aa/0x35435)。phase = [0x540ff]。
2. **figure 座標 / 翻轉 / 縮放** partial:blit 0x4e63d 原生尺寸 `dst+Y*stride+X`,**全程無縮放運算**;每幀 displacement=descriptor header `u16 X/Y`，固定 `(164,157)` 是某些 figure/台座 caller 的 anchor；`word[unit+0x40]`=當前 HP（非座標）。`+0x48/+0x4a` 是 derived AP/DP，`0x29f72` 是 combat-result resolver。**待確認**:byte[unit+6] 攻守配對、土台 entry、所有 caller 的 schedule。
3. **BG 繪製與TAI台座是兩條素材路徑**：BG.DAT多層走
   `[0x54107…54113]`並以`0x4e63d(X=0,Y=50,寬320)`合成；腳下大台座由
   `0x29164`另載TAI.DAT sprite，不是BG層或程式純色。TAI entry、raw selector
   與跨角色對齊仍待逐caller驗證。
4. **狀態欄(血條框)** ✅(本輪嚴格 RE 重做,§4):真函式 = **0x18c6d**(座標器 0x2a289,byte[+6]→ 我方(0,154)/敵方(171,4))。**0x29164 不是狀態欄,是 figure + 台座(TAI.DAT)淡入**(舊標錯已改)。三元素釘死:**① 框/深藍底/立體 bevel = 素材 sprite**(0x4e8af blit [0x53a81]+0x5e);**② HP/MP 條 = 程式畫**(0x18795 算 `len=cur*101/max+1` → 0x17d6f 逐欄 blit [0x53a81] 漸層欄 cell,空槽 0x1d;HP=unit+0x40/+0x42、MP=+0x44/+0x46);**③ 名 = `0x15f84→0x4ea2a` 以 `[0x53a75]` FDOTHER#4 font畫 16×16 glyph**、**數值 = 6px digit cell**([0x53a81],0x187d6)。`[0x53a81]` loader 已由 boot `0x25c97` 定案為 FDOTHER #5；`[0x53a85]` 是 DATO mouth-frame工作指標，不再誤稱字模。
5. **動畫階段** ✅:[0x540ff] phase + 重複呼叫驅動;0x2939d 幀迴圈 + `idiv 100` 百分比進度;幀 (dx,dy) = swing 斬擊弧;**閃紅 = VGA DAC 色盤 0x3c8/0x3c9(0x11d40)**(figure 淡入同手法);**HP 條非色盤**(程式畫,見 §4.2,舊「HP 抽乾=色盤」已刪);idle fallback 0x5255f/0x52577。**待確認**:閃紅色值序列、各階段確切幀數。
6. **座標系** ✅:320×200、VGA 0xa0000、**work stride 640 但只 present 左半 320**(雙寬 off-screen 預備區,用途待確認)。

---

## 9. 2026-08-20 — `0x2bce5`/`0x2c548` party montage cluster:純 Ghidra headless 反組譯,誠實負面結論 + 一個真實但不同主題的新發現

> 任務範圍:worklist L862/863/864/865/866/867(cluster master)/899/1017/1018/1019/1020,全部卡在
> `0x2bce5` chapter-ending renderer 與 `0x2c548` 之後的 party montage 資產解碼(FDOTHER#56/TAI#3/
> FIGANI/DATO,見 `remake/assets/endings/native_2bce5.json`、`native_2c548.json`)。本輪**只用**
> Ghidra headless(`analyzeHeadless -readOnly`,`FD2Analysis3` project,方法見
> `reference_fd2_live_ghidra_headless_probe` memory),未碰 DOSBox-X/WSL2/Docker(Docker 已於
> 2026-08-16 移除)。全部一次性 probe script 留在 `FD2_ghidra_projects/Probe{MontageMaster,
> MontageAlign,MontageLinear,MontageReal,LoadchCalls,FindTableRefs,TableDump,TableBytes,
> PhaseTable,FindDispatcher,MasterLoop,CallersOf2ff01,CommandContext2}.java` 供覆核。

### 9.1 結論先講:`0x2bce5`/`0x2c172`/`0x2c405`/`0x2c439`/`0x2c469`/`0x2c548`/`0x2c5e3`/`0x2c773` 在這個
Ghidra project 裡**不是任何已知程式碼或資料的位址**

逐一驗證方法與結果:

1. **直接反組譯**:`getInstructionAt(0x2c548)` 回傳 null(該區塊從未被 base 976-function 分析
   碰過)。強制 `disassemble(0x2c548)` 會從**該 byte 的字面位移**開始線性解碼,但 0x2c548 實際上
   落在另一個真實 function(`FUN_0002c217`,見 9.2)內部一條 `JMP rel32` 指令的**中間位元組**
   (該 JMP 在 0x2c530+22=0x2c546 起、長 5 bytes,0x2c548 正好是其 immediate 的第 3 個
   byte),導致 Ghidra 產生「overlaps instruction」警告與完全垃圾的 decompile(隨機 tick 計數器,
   跟 TAI.DAT/FDOTHER 毫無關係)。**這是本輪最大的方法論教訓**:forcing disassembly at a literal
   cited address without first confirming instruction alignment produces confident-looking but
   wrong decompiles;必須先用其他證據(caller、資料表)釘死真正的 entry point。
2. **原始 byte dump 校正**:手動逐 byte 解碼 `0x2c530..0x2c630` 確認該區塊本身是合法、自洽的
   x86 code(非亂碼),但其語意是一個 6-slot tick counter(`[0x54050]`)配 `FUN_0004ebe3`/
   `FUN_0002eb9f`/`FUN_00025a96`/`FUN_00025b45` 呼叫,和 TAI.DAT/FDOTHER.DAT 完全無關。
3. **窮舉 DWORD 掃描**:對 `0x2bce5`/`0x2c172`/`0x2c405`/`0x2c439`/`0x2c469`/`0x2c548`/
   `0x2c5e3`/`0x2c773` 逐一在整個程式記憶體image 做 little-endian DWORD byte-pattern 搜尋
   (`Memory.findBytes`,不依賴 Ghidra 是否已反組譯該處)——**全部「no hits」**,只有
   `0x2c67d` 命中一次(見 9.2,但那屬於另一個不相關的子系統)。
4. **窮舉 CALL/JMP flow 掃描**:對整個 base 976-function image 裡**每一條**已定義指令呼叫
   `insn.getFlows()`(直接位址,含已解析的相對跳轉),找 target 落在 `0x2b000..0x2d000` 的——
   全部命中都在 `0x2b000..0x2b97f`(屬於 9.2 的子系統)或 `0x2cfd8`/`0x30300+`(同上),
   **完全沒有任何一條指令直接呼叫 0x2bce5/0x2c172/0x2c405/0x2c548/0x2c5e3/0x2c773**。

三種獨立方法(資料表掃描、直接呼叫掃描、逐 byte 反組譯)都得到一致的負面結果:**在
`FD2Analysis3` 這個 project 裡,這批位址目前既不是有效的指令邊界,也不是任何資料表/直接呼叫的
目標**。這些位址原本是 2026-07 系列 session 用「official IDA 9.4」與(已移除的)「Docker
Capstone」交叉確認的(見 doc91 worklist 1368/1377/1380 行);本輪換一個工具(Ghidra headless on
`FD2Analysis3`)得到的結果對不上,原因無法在本輪內確定——可能是(a)IDA 分析的是不同的 EXE
build(對照 `feedback_fd2_old_new_exe_address_instability` memory,這個專案先前就証實過舊/新版
位址不能直接套用同一常數位移)、(b)Capstone 分析的其實是 live DOSBox 記憶體位址而非靜態檔案
offset(對照 `reference_fd2_dosbox_live_memory_extraction` memory 提到的 selector/delta 問題)、
或(c)這批位址本身在原始筆記裡就有轉錄誤差。**下一輪如果要再嘗試,建議先用官方 IDA 或
DOSBox-X live memory 重新獨立核對這幾個位址,而不要預設它們在 Ghidra 這邊直接可信**——
Ghidra 這邊窮舉搜尋的結果目前是紮實的負面證據,不是「還沒找」而是「目前找不到」。

### 9.2 意外發現:一個完整、可驗證的 FIGANI/TAI.DAT/BG.DAT/FDOTHER.DAT phase-table 演出引擎——但屬於**戰鬥指令選單**,不是章節結局

在窮舉搜尋 9.1 的位址時,順藤摸到一個結構幾乎一模一樣(FIGANI+TAI.DAT+BG.DAT+FDOTHER.DAT 資產、
9-tick 淡入淡出、[0x53a45]+slot×0x50 unit lookup、`0x17aa9` tick-wait)但**位址完全不同**、而且
**完整可反組譯/可反編譯**的子系統。逐項證據:

- **字串 anchor**:`0x524a0` 處是原始 ASCII `"TAI.DAT\0"`(Ghidra 從未把它標成 defined string,
  純 raw bytes,故先前的 defined-data 字串搜尋找不到)。緊接其後 `0x524a8..0x524c5` 是一段數字
  header,再來 `0x524c6..0x524ed` 是一張**10 筆、單調遞增的程式位址表**(逐 byte 手動核對,非
  4-byte-aligned 陷阱已排除):

  | index | 位址 | Ghidra function | body | 大小(bytes) |
  |---|---|---|---|---|
  | 0 | `0x2b996` | `FUN_0002b996` | 0x2b996..0x2c944(共用尾端) | 423 |
  | 1 | `0x2bb33` | `FUN_0002bb33` | 0x2bb33..0x2c944(共用尾端) | 579 |
  | 2 | `0x2bd6c` | `FUN_0002bd6c` | 0x2bd6c..0x2bf82 | 535 |
  | 3 | `0x2bfd9` | `FUN_0002bfd9` | 0x2bfd9..0x2c216 | 574 |
  | 4 | `0x2c217` | `FUN_0002c217` | 0x2c217..0x2c440 | 554 |
  | 5 | `0x2c441` | `FUN_0002c441` | 0x2c441..0x2c67c | 572 |
  | 6 | `0x2c67d` | `FUN_0002c67d` | 0x2c67d..0x2cafb | 1151 |
  | 7 | `0x2cafc` | `FUN_0002cafc` | 0x2cafc..0x2ccf3 | 504 |
  | 8 | `0x2ccf4` | `FUN_0002ccf4` | 0x2ccf4..0x2ce19 | 294 |
  | 9 | `0x2ce1a` | `FUN_0002ce1a` | 0x2ce1a..0x2cf2f | 278 |

  全部 10 個都**依表格順序**(避免了 9.1 教訓裡的「先碰到誤植邊界污染後續分析」問題)個別
  `getFunctionContaining`+decompile,全部成功、乾淨、無 overlap 警告。

- **共同 calling convention**:每個 handler 都是 `FUN(int param_1_slot)`(除 idx8/idx9 為全域、
  不吃 slot),用一個隱藏的 event code(`in_stack_00000014`,實際是呼叫端 AL/stack 傳入)分派
  0/1/2/3/4/5/6/7/8 九種事件:`0`=初始化(reset 一組 N 元素的 per-slot tick 陣列,N 依 handler
  而異:7/8/1(single-byte state 0..0x12)/12/6/6/5/3/16/1)、`3`=回傳固定 duration 常數、
  `6`=「凍結」旗標、`1/2/5/7/8`=每幀 tick(遞增陣列、到門檻時呼叫 `FUN_0002eb9f`/`FUN_00025a96`/
  `FUN_00025b45`,疑似 present/SFX cue,並把「下一個顯示的內容」用一個 `0..N-1` 的次要索引陣列
  以 mod-N 方式輪替——即角色進場輪替)。逐 slot 的 mirror 判斷都是同一條
  `*(char*)(DAT_00053a45+6+param_1*0x50)==0`(和 doc91 既有「unit_side_offset:6」文件完全吻合)。
  **idx6(`0x2c67d`)特別不同**:用 `0.017453277`(π/180)+ `iVar*0x48`(72°)算 5 個等角點的 sin/cos
  座標(`func_0x0003cbd5`/`func_0x0003cbe8`),再乘一個每 tick ±6 的 `DAT_000540c9` 角度/半徑
  累加器——這是一個**5 點圓弧 carousel 定位器**,不是既有文件講的「stage×10 平移淡出」。

- **主控引擎**:窮舉掃描整個已分析程式,找到唯二兩處用這張表做**間接呼叫**的地方——
  `CALL dword ptr [EAX*0x4 + 0x524c6]`(共 10 處,`0x30469..0x30a7f`)與
  `CALL dword ptr [EBP*0x4 + 0x524c6]`(共 4 處,`0x312dd..0x3143c`)。前者全部落在
  `FUN_0002ff01`(**master 引擎**,body `0x2ff01..0x30e24`,3876 bytes,簽名
  `(int param_1, int param_2, int param_3, int param_4)`),後者落在
  `FUN_00031266`(**過場助手**,body `0x31266..0x314dd`,632 bytes)。完整反編譯確認:
  - `param_2`(0..9)同時是 phase-table index**與** UI 模式碼(對照
    `param_2==0x18`/`param_2>0x1b` 提早跳走、`param_2==8`/`param_2>3` 調整 duration)。
  - 開場依序 `sub_111ba` 載入(逐一比對 push 的字串位址確認):**`BG.DAT`**(`0x5248e`)、
    **`TAI.DAT`**(`0x524a0`,唯一 1 次)、**`FIGANI.DAT`**(`0x52495`,2 次)、
    **`FDOTHER.DAT`**(`0x51a4d`,2 次),接著迴圈 `for(i=0;i<param_3;i++) local_140[i]=sub_111ba()`
    再載 `param_3`(疑似逐角色 DATO 頭像,對照既有文件「DATO=unit+7」推論,未逐位元組證實)
    份額外資源。
  - `param_3`/`param_4`:`param_3`=顯示的角色數,`param_4`=長度 `param_3` 的 slot-index 陣列
    (`DAT_00053a45 + param_4[i]*0x50` 取得每個角色的 unit record)——**這正是 party roster
    cycle 的 caller-supplied 清單**。
  - 主迴圈:`for(i=0;i<param_3;i++)` 逐角色,對每個角色跑 `table[param_2]()` 驅動的 per-frame
    迴圈(含 palette-delta 4 元素 rotation `local_c8[local_1c]`、`0x1c75e` legality check、
    `unit.+0x40` 欄位在 `FUN_0004ebe3()` 隨機值控制下的**線性內插 tween**),角色與角色之間
    (除最後一位)呼叫 `FUN_00031266`——即 4-tick 正向+5-tick 反向(共 9 tick)的轉場,和既有
    doc91 文件「`0x29164` 9 次 present、DAC baseline delta=esi×6」的敘述在**節奏與次數上**吻合,
    但實際位址、buffer 佈局、觸發路徑完全不同。
  - 尾段:3 次以 `DAT_00053a6d`(FDOTHER#3 LUT bank,和 `0x22046`/`0x24618` 共用同一全域)做的
    LUT-indexed DAC 轉場,然後釋放全部已載資源、回填 baseline DAC。

- **關鍵反證(排除是章節結局)**:`FUN_0002ff01` 的**唯二**兩個呼叫者是 `FUN_0001cff0`
  (`0x1d43c`)與 `FUN_00015311`(`0x15400`)——這兩個都是 doc91/doc13 既有文件裡**戰鬥指令
  dispatch/選單**的已知位址(`0x1cff0` 是「command table」,`0x15311` 緊鄰既有文件記錄的
  `0x14818`/`0x15195` 戰鬥動畫 caller neighborhood)。兩處呼叫前都先讀 `[0x53c57]`
  (doc13 既有的「action-ring 狀態選擇器」)去查一張 stack-copied per-command byte table
  (`[ESP+EAX+0xc8]` 判斷是否要播、`[ESP+EAX+0xd0]` 取 0..9 的 phase index),完全在**戰鬥指令
  選單**的控制流內,窮舉搜尋也**找不到任何從 `0x25xxx`(ch29/30 handler)或 `0x1088d`(loadch)
  範圍呼叫 `0x2ff01` 的路徑**。因此這是一個**戰鬥指令選單裡的角色瀏覽/carousel 演出**(可能是
  formation 換位、替補角色瀏覽等尚未命名的指令),**不是**章節結局 party montage。

### 9.3 對本 cluster 11 個 worklist 項目的具體影響

- **L862/863/864/865/866/867(cluster master)**:blocker(`0x2bce5` ending renderer)**未解除**。
  本輪窮舉三種獨立方法(資料表掃描/呼叫掃描/逐 byte 反組譯)排除了「這批位址在 `FD2Analysis3`
  裡可直接反組譯」這個假設,並發現一個表面很像但實際屬於戰鬥選單的無關子系統(9.2)——
  這是有價值的**負面結果**,可以避免下一輪重複走同一條死路,但不構成 renderer 解封。
- **L899**(chapter ending renderer,已釘死結構但缺 compositing adapter):同上,無新進展;
  9.2 的 phase-table/master-engine 架構(param_2 event dispatch、per-slot tween、LUT 轉場)
  如果日後証實 ending renderer 用的是**同一種設計模式**(不同位址、不同呼叫者),可以作為
  「這類 native 演出大致長怎樣」的參考藍圖,但目前**不能**當成同一份程式碼直接套用。
- **L1017/1018/1019/1020**(`0x2c548` 後 party montage 資產解碼,FDOTHER#56/TAI#3/FIGANI/DATO):
  同上,`0x2c548`/`0x2c5e3` 本身在這個 project 裡验证為不可達,montage renderer 仍未解。
  9.2 找到的資源載入序列(BG.DAT→TAI.DAT→FIGANI.DAT×2→FDOTHER.DAT×2→per-角色資源)結構上
  與既有 `native_2c548.json` 描述的資產組合高度相似(TAI.DAT/FIGANI/FDOTHER 都在),值得下一輪
  在**重新獨立核對舊位址**之後,比對這兩套呼叫序列是否其實是同一支函式在不同 EXE 版本裡的
  位移結果——但本輪未能證實這個推測,不可當結論使用。

### 9.4 給下一輪的具體建議

1. **先重新核對舊位址的來源**,不要預設 Ghidra 這邊的窮舉負面結果是「還沒找到」——三種獨立
   方法一致找不到,足以懷疑原始位址轉錄本身(工具差異或版本差異),應該先用官方 IDA(如果還
   拿得到同一份 session)或(如果使用者同意破例)DOSBox-X live memory 重新單獨核對
   `0x2bce5`/`0x2c548` 這兩個錨點,而不是再花時間在 Ghidra 這邊重試同一批位址。
2. 9.2 的 `FUN_0002ff01`/`FUN_00031266`/`0x524c6` phase table 是完整、可驗證、有明確 caller 的
   一手資料,值得另開一個 worklist 項目(不在本次授權範圍內編輯 91-worklist.md,故留在這裡
   供之後採用)描述為「戰鬥指令選單 party carousel 演出引擎」,對照 doc13/doc91 既有的
   `0x1cff0`「完整 native 演出」缺口(稽核索引 510/532/533/534/536/538/539/540/541/548/555/572
   行)可能有直接幫助。
3. 本輪所有 probe script(`ProbeMontageMaster.java`、`ProbeMontageAlign.java`、
   `ProbeMontageLinear.java`、`ProbeMontageReal.java`、`ProbeLoadchCalls.java`、
   `ProbeFindTableRefs.java`、`ProbeTableDump.java`、`ProbeTableBytes.java`、
   `ProbePhaseTable.java`、`ProbeFindDispatcher.java`、`ProbeMasterLoop.java`、
   `ProbeCallersOf2ff01.java`、`ProbeCommandContext2.java`)留在
   `C:\Users\kg701\Desktop\GAME\FD2_ghidra_projects\` 供覆核,方法論本身(窮舉 DWORD/CALL-flow
   掃描找 dispatch table、依表格順序而非字面位址順序碰觸函式邊界)可以重複使用在其他「有文件
   位址但 Ghidra 反組譯不出對應語意」的 worklist 項目上。

## 9.5 2026-08-20 續:「2 位元組落差=固定偏移量」假說根因調查——已排除,但附帶一個更根本的新發現

> 動機:9.1 記錄了 doc11(§「版本核對」)先前發現的落差——`FD2Analysis3` 實際分析的檔案
> (MD5 `a6e341a8decc6ebf7f4872076d9cf161`)與 `docs/data/fd2-reference-files.json` 記載的
> 基準新版 `FD2.EXE`(MD5 `33464c81e6a364fd0660141139aa8e6e`)逐 byte 只差 2 處。假說:如果這
> 2 個 byte 差異對應到一個**固定位址偏移量**,套用在 `0x2bce5` 這批位址上或許就能在
> `FD2Analysis3` 裡找到真正對應的位置。本節獨立重新核對此假說,**結論:假說不成立**,但過程中
> 發現一個對本專案定址慣例更根本、更有價值的事實(見 9.5.3)。

### 9.5.1 先定位兩個候選檔案,確認 `FD2Analysis3` 實際分析的是哪一份

MD5 比對(`Get-FileHash`)鎖定:

| 路徑 | 大小 | MD5 | 對應 |
|---|---:|---|---|
| `C:\Users\kg701\Desktop\GAME\FD2\FD2.EXE` | 509158 | `33464C81E6A364FD0660141139AA8E6E` | = `fd2-reference-files.json` 基準「新版」 |
| `C:\Users\kg701\Desktop\GAME\FD2_USB\FD2.EXE` | 509158 | `33464C81E6A364FD0660141139AA8E6E` | 與基準相同(USB 備份) |
| `C:\Users\kg701\Desktop\GAME\FD2_APK\FD2.EXE` | 509158 | `A6E341A8DECC6EBF7F4872076D9CF161` | = `FD2Analysis3` 實際分析的檔案(doc11 記錄的 hash) |

即:`FD2Analysis3` project 實際載入分析的是 `FD2_APK\FD2.EXE`,不是 `GAME\FD2\FD2.EXE`
這份目前的參考基準檔。兩者檔案大小完全相同(509158 bytes)。

### 9.5.2 重新逐 byte diff,確認落差內容 + 修正 doc11 的 2 個 hex 位址誤植

用 Python 對兩份檔案逐 byte 比對(`open(...).read()` 後逐 index 比較),獨立於 doc11 當時用的
`cmp -l` 重做一次:

```
num diffs: 2
0-based file offset 0x4455c (十進位 279900): 0x74 -> 0xeb
0-based file offset 0x4a84b (十進位 305227): 0x0d -> 0x12
```

**與 doc11 記錄比對**:doc11 給的十進位偏移(`cmp -l` 1-based)279901/305228 完全正確
(= 本次 0-based 279900/305227 各 +1,換算一致),byte 值 `0x74→0xeb`、`0x0d→0x12` 也完全一致。
但 doc11 附帶寫的兩個 **hex 位址是誤植**:`0x44575`(應為 `0x4455d`,1-based hex)、
`0x4a80c`(應為 `0x4a84c`,1-based hex)——十進位轉 hex 手動換算時的筆誤,不影響 doc11 原本
「相隔極遠、不影響本節結論」的判斷,但下一輪如果要用 hex 位址原文查證,請用這裡訂正後的值。

**context bytes(各取 patch byte 前後 12 bytes,`GAME\FD2\FD2.EXE`=ref,`GAME\FD2_APK\FD2.EXE`=apk)**:

```
0x4455c: ref: 7c 24 20 0f b6 28 0f b6 70 01 29 ee 74 0e e8 94 06 03 00 89 c2 c1 fa 1f
         apk: 7c 24 20 0f b6 28 0f b6 70 01 29 ee eb 0e e8 94 06 03 00 89 c2 c1 fa 1f
0x4a84b: ref: 00 6a 47 e8 37 ee fe ff 83 c4 04 6a 0d e8 a1 03 00 00 83 c4 04 85 c0 74
         apk: 00 6a 47 e8 37 ee fe ff 83 c4 04 6a 12 e8 a1 03 00 00 83 c4 04 85 c0 74
```

**指令級解讀**:
- Patch#1:`74 0e`(`JE +0xe`)→`eb 0e`(`JMP +0xe`,同一位移 byte 不變)——把一個條件分支
  改成無條件跳轉,兩者都是 2-byte 指令,**指令長度完全不變**。
- Patch#2:`6a 0d`(`PUSH 0x0d`)→`6a 12`(`PUSH 0x12`),緊接 `e8 ... CALL`——改的是傳給
  下一個 `CALL` 的立即數引數,同樣是 1-byte immediate,**指令長度完全不變**。

兩處都是典型「同尺寸 opcode/operand 級別 in-place 修改」,符合 doc11 原判斷「疑似
no-CD/簡易 patch」的外觀(条件跳轉改無條件跳轉+改一個傳給 call 的參數,常見於繞過某個
檢查失敗分支或改寫提示訊息代碼)。

### 9.5.3 假說判定:**不成立**——同尺寸 byte 代換不可能產生任何位移,更遑論「固定」位移

這一步不需要更多證據就能下結論:

> **Patch#1/#2 都是「原地代換」,不是插入或刪除**——兩個檔案總長度完全相同(509158 bytes
> = 509158 bytes),且除了這 2 個 byte 之外逐 byte 全部相同。同尺寸代換在數學上**不可能**讓
> 這兩個 byte 之後(或之前)的任何其他位元組挪動位置。換句話說:這兩個檔案中,**每一個其他
> 位元組的檔案 offset 都完全相等**,包括 `0x2bce5`/`0x2c172`/…/`0x2c773` 那批位址所在的整個
> `0x2b000..0x2d000` 區段——不管用哪個檔案當基準,這批位址對應的原始檔案位元組**逐 byte
> 完全相同**。

因此「2 byte 落差 → 固定偏移量 → 套用在 0x2bce5 上找到真正位址」這條推理鏈在第一步就不成立:
根本沒有偏移量可言(不是「偏移量算出來但很小/很怪」,而是「偏移量恆為 0,兩個候選檔案在
party montage cluster 這個區段本來就是同一份資料」)。9.1 的窮舉負面結果因此**不可能**是這 2
個 byte 造成的——9.1 用的 `FD2Analysis3`(分析 `FD2_APK` 版)與參考基準版在這個區段逐 byte
相同,即使當初改用參考基準版重新開一個 Ghidra project,`0x2bce5` 等位址一樣會得到相同的
「no hits / 非指令邊界」結果。**此假說到此已可視為排除**,以下 9.5.4 記錄一個過程中意外發現、
與本假說無關但對未來 RE 工作有實際價值的事實。

### 9.5.4 意外發現(比原假說更根本):「檔案 byte offset」與 Ghidra「linear 位址」在這份 EXE 裡**不是同一件事**,且兩者間沒有單一全域常數可換算

追查 patch byte 在 Ghidra 裡實際落在哪個函式時,直接對 `FD2Analysis3`(`toAddr(0x4455c)`/
`toAddr(0x4a84b)`,把 raw file offset 當成 linear 位址查詢)得到的反組譯結果,跟用 Python 讀出的
raw byte context(見 9.5.2)**對不上**——`toAddr(0x4455c)` 落在一個完全不同、语意不相關的既有
函式裡。改用**位元組特徵搜尋**(`Memory.findBytes`,搜尋 9.5.2 那兩段 24-byte context,不依賴
任何位址假設,兩段各只命中 1 次,確認唯一)直接定位這兩段 patch 在 Ghidra 記憶體裡的**真正**
linear 位址:

| patch | raw file offset(0-based) | Ghidra 真正 linear 位址 | delta(linear − file_offset) |
|---|---:|---:|---:|
| #1(JE→JMP) | `0x4455c` | `0x1e548`(所在函式 `FUN_0001e529`) | `-155668`(`-0x26014`) |
| #2(PUSH imm8) | `0x4a84b` | `0x2483b`(`PUSH 0x12; CALL 0x24bde`,前一句 `CALL 0x1366a`) | `-155664`(`-0x26010`) |

兩個 delta 幾乎相同(只差 4),**但都遠不是 0**——直接推翻了 doc35 檔頭「obj1 linear=file
offset」這句話字面上「raw .EXE 檔案 byte 位置 == Ghidra linear 位址」的解讀。另外**交叉核對**
9.2 已獨立確認的 `"TAI.DAT\0"` 字串(反組譯/反編譯證實其 linear 位址為 `0x524a0`):它在
raw 檔案裡的實際 byte 位置是 `0x774b4`(`bytes.find`,唯一命中)——delta 為 `-151572`
(`-0x25014`),**跟前兩個 code delta 又不一樣**(差恰好 `0x1000`=一個 page)。

**結論**:raw `.EXE` 檔案位元組 offset 與 Ghidra 的 linear 位址之間,在這份 DOS4GW LE
執行檔裡**不存在單一全域常數換算式**——code 區段(object1)內部的 delta 大致落在
`-0x26010~-0x26014` 一帶但仍會隨位置小幅漂移(~4 bytes/25KB,疑似 LE object page 邊界或
fixup table 造成),data 區段的字串常數 delta 又整整差了一個 page。因此:

1. 本專案文件裡「obj1 linear=file offset」這句慣例寫法,**必須理解成「已經用適當工具/轉換
   处理過的 linear 位址」之間彼此一致,不能望文生義成「可以直接拿 raw .EXE 檔案的 byte 位移
   當成 Ghidra 位址查詢」**——這次直接測試證實兩者對不上。9.1/doc91/doc11 等處引用的
   `0x1A30B`、`0x524a0`……等大量已驗證位址,都是透過 Ghidra 本身的反組譯/反編譯/交叉呼叫鏈
   確認的**linear 位址**,不是從任何 raw 檔案 byte 位移直接算出來的——這些既有結論本身沒有
   問題,只是「linear=file offset」這句話不能被逆用去做「檔案 diff → 位址算術」。
2. 就算暫時忽略 9.5.3 已經排除假說的結論,強行套用這次量到的 delta(`~-0x26010`)去試著
   把 `0x2bce5` 解讀成某種「raw file offset」需要先減去 delta 才能拿到真正 linear 位址——
   算出來是 `0x2bce5 - 0x26014 ≈ 0x5cd1`,遠低於 `FD2Analysis3` 的最小可定址位址
   `0x10000`(見 `currentProgram.getMinAddress()`),**不是有效位址**,連嘗試都站不住腳。
   這進一步佐證:`0x2bce5` 這批位址原本就是以 Ghidra/IDA 的 linear 位址記錄的(而非某種
   raw 檔案位移的別名),9.1 直接用 `toAddr(0x2bce5)` 查詢的作法是正確的方法論,問題不在
   查詢方式,而在這批位址本身的來源(見 9.1 已有的「可能是不同 EXE build / live-memory
   位址 / 轉錄誤差」三個假說,本節未能新增證據去裁決其中哪一個)。

### 9.5.5 對 party montage cluster(11 個 worklist 項目)的最終影響

**本節排除了「2 byte 差異是位址對不上的根因」這個假說,且 9.5.4 的延伸測試顯示套用這次量到
的 delta 也無法讓 `0x2bce5` 落在有效位址範圍內** ——两条路都走到底,結論一致。9.1 的三種獨立
窮舉方法(資料表掃描/呼叫掃描/逐 byte 反組譯)得到的負面結果因此**維持不變**,`0x2bce5`/
`0x2c548` renderer 的 blocker **仍未解除**,11 個 worklist 項目(L862/863/864/865/866/867/899/
1017/1018/1019/1020)狀態不變。給下一輪的具體建議(取代「檢查 2-byte 落差是否為根因」這條,
因為已經走完且排除):

1. **不要再嘗試從 `FD2Analysis3` 內部用位址算術(offset/delta)去反推 `0x2bce5` 這批位址**——
   9.5.4 已證實這份 EXE 沒有可用的全域 file-offset↔linear 換算常數,這條路完全走不通,無論
   起點是哪一份候選 EXE。
2. 依然是 9.1/9.4 原本的建議:**直接用官方 IDA(如果還拿得到同一份 session)或
   DOSBox-X live memory 重新獨立核對 `0x2bce5`/`0x2c548` 這兩個錨點**,不要預設它們能在
   `FD2Analysis3` 的 linear 位址空間裡直接解出。
3. **一般性提醒(適用所有未來 RE 工作,不限本 cluster)**:任何時候要拿「raw `.EXE` 檔案
   byte offset」(例如用 `cmp`/`fc`/Python 逐 byte diff 出來的結果)去對照 Ghidra 反組譯位址,
   **必須先用 `Memory.findBytes` 位元組特徵搜尋獨立核實對應的 linear 位址**,不能假設兩者
   相等或存在簡單常數位移——本節示範的方法(截取 patch 前後 ~24 bytes 當特徵、
   `findBytes(start, pattern, null, true, monitor)`)可以直接複用。

## 9.6 2026-08-20 續:換方法論再攻堅——三個新方法論全部窮盡,仍未解封,但排除一個新假說、確立一個更明確的定性

> 動機:9.1/9.5 已用「在 `FD2Analysis3` 內部查詢/位址算術」的方法論窮盡三輪,本節換掉整個方法論,
> 改成「回頭找最原始證據」「搜遍整台機器找遺失的舊版 EXE」「查清 `FD2_APK` 目錄的真實來源」三條
> 全新路徑,逐一詳細記錄嘗試過程與結果。**結論先講:三條路都做到底,均未能解封
> `0x2bce5`/`0x2c548` 等位址,但排除了一個原本合理的新假說(見 9.6.1 尾段),並且確認 `FD2_APK`
> 目錄不是先前猜測的「行動版/APK 反解版本」。**

### 9.6.1 方法1:回頭找「這些位址最早怎麼記錄下來的」原始證據——結論:從未存在過 raw byte context,只有語意結論被保存;但找到約40個更細的 sub-address,逐一測試後仍全部落空(含一個排除掉的「像是巧合命中」插曲)

**先確認「原始證據」根本不存在**:對 8 個 cluster 位址(`0x2bce5`/`0x2c172`/`0x2c405`/`0x2c439`/
`0x2c469`/`0x2c548`/`0x2c5e3`/`0x2c773`)以及後續從 `remake/assets/endings/native_2bce5.json`/
`native_2c548.json`/`native_2c405.json` 取出的約 40 個更細的 sub-address(如 `0x2bd8b`/`0x2c584`/
`0x29164`/`0x2935b`/`0x2927e` 等),分別用 `git log --all -S"<addr>"` 對整個 repo 歷史(非只搜
working tree)做 pickaxe 搜尋,並直接讀出每一個「第一次出現」的完整 commit diff
(`01117a5065b9`「docs: capture chapter ending renderer evidence」2026-07-20、`dd120bc2`「docs:
map finale party montage boundary」2026-07-20、`e52da455`「docs: close finale montage gate
provenance」2026-07-26 等)。三個 commit 的 diff **只新增了 worklist/json 裡的語意結論
一行文字**(buffer 大小、資源名稱、呼叫順序),完全沒有任何 hex byte、opcode 助憶符或反組譯行
被提交進 repo。`e52da455` 的訊息甚至直接寫「IDA 9.4 ASM 直接確認」、`dd120bc2` 寫「Docker
Capstone 切出三個 native buffers」——**證實這些位址一開始就是透過互動式工具(官方 IDA GUI／
互動式 Docker Capstone session)人工讀出後,只把「結論」謄寫進文件,原始 byte-level 輸出從未
落地成檔案**。同時查了 `docs/data/ida/*.txt`、`docs/data/*_ida.txt`(全部 IDA 匯出檔)與
`git log --all --diff-filter=D`(尋找任何被刪除的原始匯出檔)——沒有任何一個檔案含這批位址的
任何一個。**結論:沒有原始 byte context 可以拿來當 signature 用,這條路的「找證據」字面意義
到此為止,已經是能做到的極限**。

**退而求其次:找到 40 個更細的 sub-address,用 Ghidra 逐一測試(9.1 只測過 8 個粗位址,從未
測過這些)**。`native_2c548.json`/`native_2bce5.json`/`native_2c405.json` 裡記錄的並非只有
handler 入口位址,還有大量內部子位址(`allocations[].source`、`resources[].source`、
`party_cycle.source`、`figure_fade.source` 等),對應到當初 Docker Capstone/IDA 讀出的具體指令
位置(例如 `0x2c584` = `sub_111ba("TAI.DAT",3)` 呼叫點、`0x29164` = `figure_renderer`、
`0x2935b`/`0x2927e` = `mirror_branch`/`figure_fade` 相關呼叫)。寫了
`FD2_ghidra_projects/ProbeFineSubAddrs20260820.java`,一次測試全部 59 個位址(8 個原 cluster +
40 個新 sub-address + 已知有效的 sanity-check 位址如 `0x1088d`/`0x111ba`/`0x2ff01`),用
`analyzeHeadless -readOnly` 對 `FD2Analysis3` 跑(方法見
`reference_fd2_live_ghidra_headless_probe` memory)。結果:

- 原 8 個 cluster 位址(含 `0x2bce5`/`0x2c548`)**全部 MISS**,與 9.1 一致。
- 新增的約 40 個 sub-address 裡,**35 個 MISS**,只有 4 個技術上落在真實已定義的函式裡:
  `0x29164`(`PUSH dword ptr [0x53c57]`,函式 `FUN_00028f65`)、`0x2935b`(`PUSH 0xc8`,函式
  `FUN_00029300`)、`0x2927e`(`INC dword ptr [ESP+4]`,函式 `FUN_0002921a`),另有兩個落在函式體內
  但不在指令邊界上。

**追查這 4 個「技術上命中」是不是真突破**:寫了 `ProbeDecompCheck20260820.java` 反編譯這三個
函式,結果**確認是數值巧合,不是版本位移後的真正對應**:

- `FUN_00028f65`(含 `0x29164`)反編譯後是一個對 `DAT_00053c57`(action-ring 選擇器,與 9.2 已
  證實的「戰鬥指令選單」全域完全一致)與 `DAT_00053a45+iVar2*2`(8-slot 陣列、bit 0x80 判斷)操作
  的**戰鬥指令選單狀態機**,和「party montage figure renderer」語意完全無關。
- `FUN_0002921a`(含 `0x2927e`)是一個泛用的仿射/旋轉缩放 blit 原語(`param_4` 當步進值逐行
  逐列取樣來源緩衝),函式簽名 `(param_1,param_2,param_3,param_4)` 4 個參數,和 json 描述的
  `mirror_branch`(`work_stride`/`stage_start`/`palette_delta_formula` 等欄位)對不上。
- `FUN_00029300`(含 `0x2935b`)是一個 `DAT_00053c57` 0/1/2 三分支選單迴圈,尾端有一個
  10 次遞減迴圈搭配 `&DAT_00052363`/`&DAT_00052375`(sin/cos 查表)算座標、呼叫
  `FUN_0002921a` 10 次——**結構上確實很像某種圓弧 carousel 效果**(與 9.2 記錄的
  `0x2c67d`「5 點圓弧 carousel」精神類似),但呼叫簽名(7 個參數,含查表結果與 `iVar7*-9+0x80`)
  跟 `native_2c548.json` 記載的 `0x2935b(primary_figani,frame,staging,320,-1)` 完全對不上,
  也不是黨 5 點而是 10 點迭代。

**結論**:即使把搜尋粒度從 8 個粗位址細到 40 個內部子位址,`FD2Analysis3` 裡仍然找不到任何一個
在語意上真正對應 party montage/chapter ending renderer 的位置——技術上落入函式體的 4 個
sub-address 全部是與 party montage 無關的其他子系統(戰鬥選單/仿射 blit 原語/另一個 carousel
變體)的數值巧合,**不構成解封**。

**一個原本合理、但本節已排除的新假說(值得記錄,避免下一輪重複嘗試)**:懷疑這批位址
(全部首見於 2026-07-20~07-28 的 commit)搞不好單純是「還沒套用 2026-08-18 `ca5703b3`
rebaseline(改用新版 509158 bytes `FD2.EXE` 當基準)之前,對舊版 357074 bytes build 記錄的位址,
從未被回頭轉換」。**用同一時期(2026-07-20/07-25/07-26)的其他位址交叉核對後,此假說不成立**:
`0x22253`(2026-07-20 首見,`2c982c3d`/`ab3400bf`)、`0x25089`(2026-07-20 首見,`ab3400bf`)、
`0x1cff0`(2026-07-25 首見,`92d13c9e`)——這些位址跟 `0x2bce5`/`0x2c548` 出自**完全相同的
7 月時間窗、完全相同的工具鏈(worklist 明確標「Docker Capstone」/「官方 IDA」)**,而且在
9.2 的窮舉裡已經獨立確認**目前在 `FD2Analysis3`(post-rebaseline)裡完全有效**、doc13/doc91
持續引用至今。既然同一時期、同一工具產出的其他位址在 rebaseline 後仍然有效,「這批位址是舊版
build 的殘留、只是還沒轉換」這個解釋就站不住腳——時間點本身不是問題的成因。真正原因目前仍
無法確定,維持 9.1 原本列出的三個假說(不同 EXE build、live-memory 位址、轉錄誤差)中的後兩者。

### 9.6.2 方法2:搜尋整台機器找有沒有殘留其他版本的 FD2.EXE——結論:徹底搜過,確認真的遺失,沒有第三份候選

用 PowerShell `Get-ChildItem -Recurse -Include *.EXE,*.exe` 對 `C:\Users\kg701`、`C:\tools`
(`D:\` 在這台機器上不存在,`Test-Path` 確認)做大小篩選(300000~600000 bytes,涵蓋新舊版兩種
大小附近的合理範圍),共 238 筆命中,逐筆人工檢視檔名/路徑。與 FD2 相關的只有 5 筆,全部
509158 bytes:`GAME\FD2\FD2.EXE`、`GAME\FD2_USB\FD2.EXE`、`GAME\FD2_APK\FD2.EXE`、
`GAME\FD2_APK\FD2_old.EXE`(**先前完全沒被檢查過的候選檔**,見 9.6.3)、
`fd2_re\org_game\炎龍騎士團\FLAME2\FD2.EXE`。逐一 MD5:

| 檔案 | MD5 | 對應 |
|---|---|---|
| `GAME\FD2\FD2.EXE` | `33464c81e6a364fd0660141139aa8e6e` | 目前參考基準(新版) |
| `GAME\FD2_USB\FD2.EXE` | `33464c81e6a364fd0660141139aa8e6e` | 與基準相同 |
| `fd2_re\org_game\...\FLAME2\FD2.EXE` | `33464c81e6a364fd0660141139aa8e6e` | 與基準相同 |
| `GAME\FD2_APK\FD2_old.EXE` | `33464c81e6a364fd0660141139aa8e6e` | **與基準逐 byte相同**(見 9.6.3,檔名誤導) |
| `GAME\FD2_APK\FD2.EXE` | `a6e341a8decc6ebf7f4872076d9cf161` | 9.5 已知的 2-byte патch 版 |

**沒有找到任何第三種、跟這兩個 hash 都不同的 509158 bytes 候選**。另外針對舊版文件記載的精確
大小 357074 bytes(對應 MD5 `b97caf2239a27a896069d03549d96e1e`,見
`docs/data/fd2_ai_command_index_disasm.txt` 檔頭)在同樣的搜尋樹(`C:\Users\kg701`、`C:\tools`)
裡做**精確大小比對**(`Where-Object { $_.Length -eq 357074 }`)——**零命中**。也用
`Shell.Application` COM 物件列舉資源回收筒(`Namespace(10)`,3 個項目)——全部是無關的錄影檔/
舊作業壓縮檔,無 FD2 相關項目。另檢查了 `C:\tools\ghidra_project\FD2Project.rep`(memory 記載
「只看得到 16-bit stub」的舊 project)的 `idata\00\00000000.prp` 中繼資料——只記錄
`NAME="FD2.EXE"`,沒有內嵌任何 MD5/size,無法在不開啟該 project 的情況下確認它當初匯入的是
哪一份檔案(且 memory 已明確建議忽略此 project,故本節未進一步開啟它去查——開啟的預期效益低,
不值得冒著意外變更該唯讀 project 的風險)。

**結論**:在使用者機器上、依任務指定的合理範圍內(`C:\Users\kg701`、`C:\tools`,`D:\` 不存在)
搜尋徹底,確認**舊版 357074 bytes(`b97caf22...`)的 `FD2.EXE` 真的已經完全遺失,沒有任何殘留
拷貝**,USB 備份、`FD2_APK`、`org_game` 目錄下的所有 EXE 都只是新版 509158 bytes 的（含或不含
2-byte patch）拷貝。

### 9.6.3 方法3:重新檢視 `FD2_APK` 目錄名稱與內容——結論:不是「行動版/APK 反解」,是一份含手動 patch EXE 的 1995 年 DOS 安裝目錄,附帶找到一個先前漏查的 `FD2_old.EXE`

列出 `GAME\FD2_APK\` 完整內容(50 個檔案)並核對每個檔案的 `LastWriteTime`/`CreationTime`:

- 目錄內容是一份**標準 1995 年 FD2 DOS 安裝**:全部音效卡驅動(`*.MDI`/`*.DIG`)、`*.DAT` 資源檔、
  `PLAY.BAT`/`SETUP.BAT`,**沒有任何 APK 封裝檔、Android/行動裝置相關產物,也沒有任何
  README/log 說明這個目錄名稱的由來**。
- 驅動檔案 `LastWriteTime` 全部落在 1995-01-18(原版發行雛型日期一致),主要 `*.DAT` 落在
  1995-06/07(與已知發行日期吻合),但 `FD2.SAV`(1995-07-15 存檔起始,後續存檔到
  2007-08-07)、`FD2.TMP`(2007-10-22)——**這是一份被實際玩到 2007 年的個人存檔目錄**,不是
  單純的原版光碟映像備份。
- **關鍵新發現**:`FD2_APK\FD2.EXE` 的 `LastWriteTime` 是 **2004-10-23**(明顯晚於旁邊
  `FD2_old.EXE` 與所有其他候選保留的原始 1995-07-07 時間戳),與 9.5 已證實的「同尺寸、2 處
  in-place byte 代換(`JE→JMP`、`PUSH 0x0d→PUSH 0x12`)」完全吻合——**這份 `FD2.EXE` 就是 2004 年
  有人手動改過的破解/微調版本**,而緊鄰它的 `FD2_old.EXE`(9.6.2 新找到、逐 byte 與目前基準
  相同)才是原始未修改版,只是被人用「_old」這個容易誤導的名字保存下來（大概是修 patch 前的
  備份,而不是"比目前基準還舊的另一個 build"）。
- 全部 50 個檔案的 `CreationTime` 一致為 `2026-08-14 14:21:22`——代表整個資料夾是在
  2026-08-14 那一次以資料夾為單位整批複製進這台 Windows 機器的(與 doc「2026-08-14 rebaseline
  調查」的時間點吻合),但這只說明「這台機器何時取得這份拷貝」,對資料夾更早的來源沒有幫助。

**結論**:`FD2_APK` 這個資料夾名稱**不代表任何行動版/APK 反解來源**——目錄內容、檔案格式、
驅動程式清單都是純正的 1995 年 DOS 遊戲安裝,沒有任何證據指向 Android/行動裝置。它其實是
「一份被實際玩到 2007 年、EXE 曾在 2004 年被手動 patch 過的個人 DOS 安裝備份」,`FD2_old.EXE`
只是这份備份裡順手保留的「patch 前備份」,byte-for-byte 就是目前的基準版,**不是**任何新的
候選版本。9.5.1 已經證實的「`FD2Analysis3` 分析的是 `FD2_APK\FD2.EXE`(2 byte patch 版),不是
canonical baseline」這個落差,到這裡可以確認**與本輪要解的位址對不上問題完全無關**(9.5.3
已經證明這 2 byte 是同尺寸原地代換,不影響任何位址)。

### 9.6.4 給下一輪的總結建議

三個新方法論都做到窮盡,沒有解封 `0x2bce5`/`0x2c548` 等位址,但都得到明確的負面結論,可以
排除下一輪重複去做:

1. **不要再花時間找「原始 byte context」**——9.6.1 已確認這批位址從一開始就只以「互動式工具
   讀出後手寫的結論」形式存在,repo 裡從未有、現在也不可能回頭生出原始 byte-level 匯出檔。
2. **不要再懷疑是舊版 357074 bytes build 沒轉換位址**——9.6.1 尾段已用同期其他位址反證排除;
   9.6.2 也已證實舊版 EXE 在這台機器上真的完全找不到,連驗證這個假說的材料都沒有。
3. **不要再去查 `FD2_APK` 的來源或懷疑它是行動版**——9.6.3 已徹底查清,它只是個人 DOS 存檔
   備份,`FD2_APK\FD2.EXE`/`FD2_old.EXE` 兩者都已經被 9.5+9.6.2 排除在外。
4. **如果還要再攻堅**,剩下唯一沒被排除的假說是 9.1 原本列出的「Capstone 分析的其實是 live
   DOSBox 記憶體位址(含 relocation/loader 位移),不是靜態檔案 linear offset」——這條路需要
   實際重新用 DOSBox-X live memory(`reference_fd2_dosbox_live_memory_extraction` memory)去對
   `0x2bce5`/`0x2c548` 這兩個錨點跑一次即時記憶體特徵搜尋,而不是繼續在靜態工具（Ghidra/IDA/
   git 歷史）裡打轉——這是三輪 static-only 嘗試後唯一還沒被實際測過的路徑。
5. 本節新增的探測腳本 `ProbeFineSubAddrs20260820.java`、`ProbeDecompCheck20260820.java`
   留在 `C:\Users\kg701\Desktop\GAME\FD2_ghidra_projects\` 供覆核,方法本身(從 editable IR json
   反推子位址、逐一 probe 再用 decompile 排除數值巧合)可複用在其他「粗位址查無此人,細位址
   要不要也試」的情境。
