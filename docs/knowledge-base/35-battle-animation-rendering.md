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

## 9.7 2026-08-21 — 行為指紋全域掃描:換掉整個方法論(不再信任任何位址),掃遍 976 個 function 找 ending renderer 的行為特徵——誠實負面結論,但排除了「同時符合任兩個特徵」這個組合假說,並意外揪出一個嚴重的 Ghidra decompile 偽代碼盲點

> 動機:9.1/9.5/9.6 三輪都是「先假設一批位址是對的,再想辦法在 `FD2Analysis3` 裡驗證/换算它」,
> 三輪全部失敗。本節換一個完全不同的方向:**不引用任何舊位址**,改成先把 ending renderer 已經
> 釘死的**行為規格**(doc35 §9 / `native_2bce5.json`)寫成 4 條可程式化檢查的特徵,再對整個
> `FD2Analysis3`(976 個已知 function,無一遺漏)逐一比對——如果 renderer 真的還在這個 project
> 的靜態分析範圍內,不管它現在被 Ghidra 標成哪個位址、叫什麼名字,行為特徵都應該找得到它。

### 9.7.1 四條行為特徵(對照 `native_2bce5.json`/`docs/knowledge-base/23-boot-title-and-scenario-flow.md` L411 訂出)

| # | 特徵 | 依據 |
|---|---|---|
| c1 | 呼叫已證實的通用資源載入器 `FUN_000111ba`(簽名 `(descriptor, prevSlot, index)`,doc23 L411/doc35 §6),且 `index` 引數為 **54(0x36)**——即載入 FDOTHER.DAT 第 54 號資源 | `native_2bce5.json`:`"resource": {"archive": "FDOTHER.DAT", "index": 54}` |
| c2 | 同一個 function 裡同時出現常數 **320**(0x140)與 **200**(0xc8) | ending 畫面是 320×200 雙緩衝(doc35 §9 前言) |
| c3 | 呼叫已證實的 VGA DAC 色盤寫入 helper `FUN_00011d40`(doc06/doc35 §6,`push start,end,value; call 0x11d40`) | `native_2bce5.json` 的 `palette_update`/`palette_ramp`/`palette_ramp_repeat` 全部落在此呼叫 |
| c4 | 同一個 function 裡同時出現常數 **2000**(hold 時間 ms)與 **4**(每步 palette ramp 延遲 ms) | `native_2bce5.json`:`{"op":"delay_ms","ms":2000}` 緊接 `{"op":"palette_ramp",...,"delay_ms":4}` |

### 9.7.2 第一輪(decompile 文字比對)先撞上一個更根本的方法論陷阱:這個 project 的 Ghidra decompile **幾乎不顯示任何呼叫引數**

寫了 `GlobalBehaviorScan.java`(留在 `FD2_ghidra_projects\`),對 976 個 function 逐一
`DecompInterface.decompileFunction`,在偽代碼文字裡 regex 比對上述 4 條特徵。跑完(976/976,
0 個 decompile 失敗,7 秒):**c1 全域 0 命中**,c4 全域 0 命中,c3(呼叫 `FUN_00011d40`)命中
15 個 function,但沒有任何一個同時命中 c1 或 c4,最高分數只有 1(單一特徵)。

**在把這個結果當結論之前先做二次確認**(參照 memory「檢查現有證據」與「驗證資料來源」習慣):
抽查已知一定會呼叫 loader 的 `0x25977`(doc12 §15 輪已證實呼叫 `0x111ba` 載 FDMUS.DAT)跟
`FUN_000111ba` 自己的 decompile,結果**兩者的呼叫語句全部不顯示引數**——例如
`FUN_00025977` 裡載入呼叫顯示成 `DAT_00053ee0 = FUN_000111ba();`(空括號),連
`FUN_000111ba` 自己內部呼叫 `FUN_0003776e()`/`FUN_00037324()`……等 6 個 helper 也全部是空括號,
即使它自己的正式簽名已經是 `int __stdcall FUN_000111ba(undefined4 param_1,int param_2)`
（兩個具名參數）。**結論:這不是 loader 專屬的問題,是這個 project 的 decompiler 呼叫引數渲染
在系統性層級上大量失效**(推測是 Watcom stdcall 呼叫端 p-code 的引數綁定沒有被完整重建,
與是否 `-noanalysis` 無關,因為 decompile 本身有自己的 per-function p-code 正規化)。這代表
**任何「在 decompile 偽代碼文字裡搜引數字面值」的方法論,在這個 project 上先天不可靠**——
9.2 記錄的「`0x111ba("TAI.DAT"@0x52393, prevSlot, idx)` 帶引數字面值」那類寫法,回頭核對
應理解為分析當時人工從 disasm 逐條核對出來的**還原**,不是 Ghidra decompile 視窗直接顯示的
原始輸出。這是本輪除了 ending renderer 本身以外,對「之後任何要用 decompile 文字比對的
研究」都有直接影響的新發現,已同步記入 `docs/knowledge-base/98-tooling-infrastructure.md`。

### 9.7.3 第二輪:改用純指令層級(CALL flow target + PUSH 立即數回溯),用已知 ground truth 驗證方法本身正確

寫了 `GlobalBehaviorScanV2.java`:不再看 decompile 文字,改成對每個 function 的**每一條指令**
直接用 `insn.getFlows()`(9.1 method 4 已驗證過的技巧)判斷是否為呼叫 `0x111ba`/`0x11d40`;
命中呼叫 `0x111ba` 時,從該 CALL 往回掃最近 8 條指令裡的 `PUSH <立即數>`,收集成引數候選清單
(c1);c2/c4 則對整個 function 的**每一條指令、每一個 operand**做 `Scalar` 掃描,不依賴
decompile 呈現。

**先驗證方法本身可信**:對 boot 已知序列(doc23 L411 已證實 `0x25c97` 呼叫 `0x111ba(...,5)`
載入 FDOTHER#5)——本輪掃出 `FUN_00025bf4`(body `0x25bf4..?`)connectedly 依序呼叫
loader 6 次,index 引數逐一為 `0x1f→0x1→0x2→0x3→0x4→0x5→0x6`,descriptor 全部是
`0x51a4d`(即 `"FDOTHER.DAT\0"` 字串位址,doc35 §9.2 已證實)——**與既有文件記錄的
「boot `0x25c97` 呼叫 `0x111ba(...,5)`」逐位元組吻合**,證明這套「CALL flow + PUSH 回溯」
方法本身可靠,可以拿去信任其餘結果。

**全域統計**:976/976 function 掃完(<1 秒)。全程式共 **113 處**呼叫 `0x111ba`,其中
**48 處**的 descriptor 引數確認指向 `0x51a4d`(FDOTHER.DAT,經逐一核對 `PUSH 0x51a4d`
指令的 `getReferencesFrom` 落在該字串位址)。這 48 筆逐一列出 index 引數,**沒有任何一筆
index 是字面 `54`/`0x36`**——實際出現過的值含 `0x0/0x1/0x2/0x3/0x4/0x5/0x6/0x7/0x8/0x9/0xa/
0xd/0xe/0x1f/0x2a/0x37/0x40/0x4a/0x4c/0x4d/0x4e/0x4f/0x50/0x51/0x5f/0x63/0x65/0x66`,範圍涵蓋
到 `0x66`(102),但恰好跳過 `0x36`(54)——**c1(在整個程式的 113 個 loader 呼叫點裡找字面
index=54)全域 0 命中,且這次的方法已經用已知正確答案驗證過可信,不是方法失效**。

c2(320+200 同一 function)命中 **21 個** function、c3(呼叫 `0x11d40`)命中 **20 個**
function(比 v1 的 15 個多,因為不再受 decompile 引數盲點影響)、c4(2000+4 同一 function)
命中 **1 個**(`0x25977`,已知的 FDMUS.DAT 音樂載入函式,與 party montage 無關,判定為巧合)。
**同時符合 c2+c3(score=2)的有 6 個 function**,是本輪最高分,**沒有任何 function 同時符合
c1(0 命中)**——即使把「符合 c3 加另一條就當候選」的門檻放到最寬,能列出的候選也只有這 6 個。

### 9.7.4 對 6 個 score=2 候選逐一人工複核:全部確認屬於已有文件記錄的其他子系統,無一是 ending renderer

| 位址 | function | 大小 | 呼叫端 | 人工複核結論 |
|---|---|---:|---|---|
| `0x1f894` | `FUN_0001f894` | 1765B | `0x25ec8`(在既有 boot/開場序列範圍) | 內部呼叫 `0x1f525`/`0x1f81e`/`0x1f73f`/`0x1f882`(doc39 已記錄的**開場/標題 palette fade 家族**),535 幀主迴圈,屬於**開機/標題演出**,不是章節結局 |
| `0x279bc` | `FUN_000279bc` | 887B | `0x26966` | 內部 `DAT_00053c57` 0/1/2/3 dispatch(doc13 已證實的「action-ring 狀態選擇器」)+ 10 點圓弧 sin/cos carousel(呼叫 `FUN_0002921a`)——**與 doc35 §9.2/§9.6.1 已認定的「戰鬥指令選單 party carousel」完全同一家族**，descriptor `0x51a4d` 引數解出的 index 經 9.7.5 register-history 回溯確認只有 `{0xc,0x1d,0x3f}` 三種可能，不含 54 |
| `0x29300` | `FUN_00029300` | — | — | **就是 9.6.1 已經反編譯過、已排除的同一個 function**(該節結論:「戰鬥指令選單 carousel，跟 party montage 語意不合」)——本輪從行為指紋角度重新找到同一個答案，交叉驗證 9.6.1 沒有找錯 |
| `0x29daa` | `FUN_00029daa` | 720B | `0x2693a` | 與 `0x279bc` 幾乎逐行相同的樣板(`DAT_00053c57` dispatch 到另外 4 個 handler + 同一段 10 點 carousel),同一家族的另一個菜單情境實例 |
| `0x2e9a8` | `FUN_0002e9a8` | 503B | 5 處(`0x2e137`/`0x2e6ba`/`0x30356`/`0x2d31e`/`0x2d9b1`) | 8 迴圈 `0x11eb0` present + `0x11d40` 色盤 + `*(char*)(DAT_00053a45+6+param_1*0x50)` unit-side 判斷——**正是 doc35 §4.0/§9.2 已證實的「figure/台座淡入」共用 helper**，被至少 5 個不同呼叫端共用，是通用元件不是 renderer 本體 |
| `0x2fb2c` | `FUN_0002fb2c` | 744B | `0x2abcc`(= `FUN_0002aa00`) | `FUN_0002aa00` 正是 `0x29daa` 的 `DAT_00053c57==3` 分支目標——**同一個戰鬥選單家族的第 4 個情境 handler**,載入 3 個資源(index 由暫存器決定,未解出字面值)後跑 8 迴圈 blit+色盤，仍是選單演出,不是 party montage |

六個候選全部人工複核完畢,**沒有一個是 ending renderer**——其中三個(`0x279bc`/`0x29300`/
`0x29daa`)加上 `0x2fb2c` 共四個,其實都是 doc35 §9.2/§9.6.1 已經定性過的「戰鬥指令選單 party
carousel」家族的不同情境實例(對照既有文件,這個家族目前已知至少有 `0x2ff01`/`0x29300`/
`0x279bc`/`0x29daa`/`0x2fb2c` 五個同構 function,比 9.2 原本只認出 1 個多);`0x1f894` 屬於
開場/標題;`0x2e9a8` 是被多處共用的底層淡入 helper。**這次behavior-first 掃描沒有意外撞見
renderer,但意外把「戰鬥選單 carousel 家族」的成員數從 1 個擴到至少 5 個,補全了 doc35 §9.4
給下一輪的建議 2 提到的「值得另開項目」**。

### 9.7.5 第三輪:補一個資料流缺口——57/113 個 loader 呼叫點的 index 是暫存器/迴圈算出來的,v2 看不到;寫 v3 加一層簡單的暫存器歷史回溯,結果仍是 0 命中

複查 v2 的「index 引數不是立即數」(v2 標記為 `null`)的呼叫點時,手動反組譯其中一個
(`FUN_000279bc` 在 `0x27a1a` 的呼叫)發現真正的模式是**「預設值 + compare-and-branch 覆寫」**:

```
0x279d7  MOV ESI,0xc        ; 預設 index=0xc(12)
0x279f0  CMP [0x53f4a],0x3
0x279f7  JNZ 0x27a00
0x279f9  MOV ESI,0x1d       ; 若條件==3,覆寫成 0x1d(29)
0x27a00  CMP [0x53f4a],0x5
0x27a07  JNZ 0x27a0e
0x27a09  MOV ESI,0x3f       ; 若條件==5,覆寫成 0x3f(63)
0x27a0e  PUSH ESI ... CALL 0x111ba
```

`PUSH ESI` 本身沒有立即數 operand,v2 的純 PUSH-立即數回溯完全看不到 `{0xc,0x1d,0x3f}` 這三個
候選值——這是 v2 的已知盲點,不查會讓「c1 全域 0 命中」這個結論**打折扣**(可能只是漏看,不是
真的沒有)。寫了 `GlobalBehaviorScanV3.java`:對每個 function 做**單趟正向掃描**,追蹤「每個
暫存器最後一次被 `MOV reg,imm` 設成的值」+「這個暫存器在這個 function 裡曾經被設過的所有
不同立即數值」(涵蓋上面這種 if/else 分支鏈覆寫模式,不含真正的迴圈/表格運算),`PUSH reg` 時
額外回報該暫存器的歷史立即數集合。

**結果**:113 個 loader 呼叫點裡,**43 個**是直接立即數(與 v2 一致)、**13 個**靠暫存器歷史
回溯解出(新增覆蓋,例如 `0x279bc`/`0x29daa`/`0x1f894`/`0x2ff01` 的部分呼叫點),合計
**56/113**(50%)有解出具體候選值;**57 個**(50%)仍然真正無法用這個層級的靜態方法解出
(多半落在 `0x2ff01`/`0x2cf30`/`0x2d80d`/`0x2dfc8`/`0x2e2b0`/`0x2fb2c`/`0x1088d` 等已知的
**迴圈/表格驅動**載入函式裡,例如 9.2 已記錄的 `0x2ff01` 內 `for(i=0;i<param_3;i++)
local_140[i]=sub_111ba()` 逐角色迴圈——這類迴圈索引原則上執行期真的可能算出 54,但無法靠
靜態單趟暫存器追蹤解出,誠實標記為「未解出」而非「排除」)。**在可解出的 56 個呼叫點裡,
沒有任何一個候選值等於 54/0x36**——`GlobalBehaviorScanV3` 全域回報
`functions_with_any_54_hit_direct_or_register_history: 0`。

### 9.7.6 誠實結論與對 11 個 worklist 項目的影響

**結論**:本輪用一個和 9.1/9.5/9.6 完全不同的方向(行為特徵優先,不引用任何舊位址)、對
`FD2Analysis3` 976 個 function **無一遺漏**地做了排除法——涵蓋 113 個 loader 呼叫點裡
56 個可靜態解出的 index 值、20 個呼叫色盤 helper 的 function、21 個同時有 320+200 常數的
function——**任何組合(單條件或雙條件)都沒有指向一個新的 ending renderer 候選**。這比
9.1/9.5/9.6 的「查不到某幾個特定位址」更進一步:**這次是「就算完全不管位址、只看行為,這個
project 裡目前分析出的 976 個 function 也沒有一個表現出 ending renderer 的行為特徵組合」**——
對「這段程式碼可能是 overlay/動態載入、Ghidra 靜態分析看不到」這個假說(9.1 三個假說之一)
是一次獨立、方法論完全不同的加強佐證,但仍不是證明(57 個迴圈/表格驅動的呼叫點沒有徹底解開,
理論上不能 100% 排除 renderer 藏在其中某個既有 function 的一段迴圈索引裡,只是**沒有任何
證據支持**這個可能,且與已知的 5 個「戰鬥選單 carousel」家族更吻合)。11 個 worklist 項目
(L862/863/864/865/866/867/899/1017/1018/1019/1020)的 blocker **依然未解除**,但下一輪如果
還要嘗試,**不要再重複「行為指紋 vs 976 個 function 全比對」這條路**——本輪已經做到窮盡,
唯一還沒試過的仍是 9.6.4 結論 4 提到的「DOSBox-X live memory 重新獨立核對錨點」(本次任務
明確排除、不碰 DOSBox-X/WSL2)。

### 9.7.7 本輪的兩個附帶價值(獨立於 ending renderer 本身)

1. **戰鬥選單 carousel 家族從 1 個成員擴到至少 5 個**(`0x2ff01`/`0x29300`/`0x279bc`/
   `0x29daa`/`0x2fb2c`,均為 `DAT_00053c57` 狀態機 + 10 點或 5 點 sin/cos carousel 的同構
   變體),補全 doc35 §9.4 建議 2「值得另開一個 worklist 項目」的具體範圍。
2. **新工具盲點記錄**(已同步 doc98):`FD2Analysis3` 的 Ghidra decompile 在這個 project 上
   系統性地不顯示呼叫引數(即使目標 function 已有具名參數的正式簽名)——任何未來要用
   decompile 偽代碼文字比對引數字面值的研究,必須先用一個已知答案的呼叫點驗證,不能預設
   decompile 輸出忠實反映引數;指令層級 `insn.getFlows()` + `PUSH` 立即數回溯(必要時加一層
   單趟暫存器歷史追蹤,見 9.7.5)是目前唯一驗證過在這個 project 上可信的替代方法。

### 9.7.8 本輪腳本清單

`GlobalBehaviorScan.java`(v1,decompile 文字比對,已知對這個 project 有 9.7.2 記錄的盲點,
保留供對照)、`GlobalBehaviorScanV2.java`(v2,指令層級 CALL-flow + PUSH 立即數回溯,主要方法,
已用 boot loader ground truth 驗證)、`GlobalBehaviorScanV3.java`(v3,加一層單趟暫存器歷史
回溯,補 v2 的 `PUSH reg` 盲點)、`GlobalBehaviorScanDebug.java`(v1 結果可疑時的輔助稽核腳本,
列出每個呼叫 loader 的 function 完整 decompile 引數文字,是發現 9.7.2 盲點的直接原因)。全部
留在 `C:\Users\kg701\Desktop\GAME\FD2_ghidra_projects\`,結果 JSON(`global_behavior_scan_
results.json`/`_v2_results.json`/`_v3_results.json`/`_debug_results.json`)一併保留供覆核。

## 9.8 2026-08-24 — 首次用 live 執行流程觸發真正的 postbattle 勝利轉場，深入結局 montage 本體；`0x2bce5`/`0x2c548` 舊候選再次被 live 印證不可達，但捕捉到一個全新候選解碼迴圈

> 完整過程見 `docs/knowledge-base/58-remake-live-verification-log.md` 續六十二。本節只摘要對
> 本篇(doc35 §9)有直接影響的結論，供之後靜態反組譯攻堅時引用。

**背景**：doc25 §3.1(2026-08-24 同日完成)靜態反組譯出 ch27 真正的引擎層勝利判定是
`0x51b19[26]=0x20a87 → CALL 0x205be`，`0x205be` 是純掃描「目前存活的敵方 record 是否為
0」的通用邏輯，不是隊長專屬計數器。doc58 續六十二據此把 ch27 的 47 格敵方 record 全部寫入死亡
signature(`+5=0x01`)，並在真實 UI 的「End Turn 確認 YES」操作點上觸發了一次真正的
postbattle 勝利轉場(非直接寫入死亡 signature 本身觸發，見下)。

**對本篇的直接影響**：

1. **`0x2bce5`/`0x2c548`(§9.1-9.7 記錄的舊候選 cluster)這次用 live 執行流程再次印證不可達**：
   本輪在觸發勝利之前，於 `0x2bce5+0x19C000=0x1C7CE5`、`0x2c548+0x19C000=0x1C8148` 兩處
   下斷點，全程(CG 過場、詩句捲動文字、角色回顧卡)持續 `RUN`，**兩個斷點自始至終未命中一次**。
   這與 §9.1-9.7 三種獨立靜態方法論(資料表掃描/呼叫掃描/逐 byte 反組譯/行為指紋全域掃描)的
   「全 EXE 無任何靜態 CALL 指向這批位址」負面結論完全吻合——第一次由 live 執行流程(而非
   純靜態分析)交叉印證同一個負面結論，信心等級再往上補一層，**§9.1-9.7 的結論維持不變，
   不需要修正**。
2. **新候選：一個 RLE 風格解碼迴圈，live 位址 `0x1EAC6A`/`0x1EAE28`，native 約
   `0x4EC6A`/`0x4EE28`**——CG 過場(天空島嶼)與角色回顧卡(萊汀)畫面顯示期間，兩次獨立
   `Alt+Pause` 手動取樣，EIP 都落在同一個小 range 內：
   - `0x1EAC6A`：`FECC(dec ah); C3(ret); AC(lodsb); 3CC0(cmp al,C0); 7703(ja +3);
     32E4(xor ah,ah); C3(ret); 8AE0(mov ah,al); 80ECC1(sub ah,C1); AC(lodsb); C3(ret)`——
     教科書等級的 RLE 解碼原語(讀 control byte，≤0xC0 視為 literal，否則算 run-length
     並讀填充值)。
   - `0x1EAE28`：`FEC9; jne $-13; pop edi; add edi,ebp; FECD; jne $-21; popad; pop ebp; ret`——
     像是外層迴圈收尾(雙層 loop counter 遞減 + `popad` 還原暫存器)。
   兩次獨立取樣都落在這個範圍，暗示這是 montage 渲染期間**被高頻率呼叫**的熱迴圈，很可能是
   角色卡 portrait/CG 圖像解壓縮的核心 helper。**本輪未反向追出呼叫端**(沒有查 function
   bounds/xref_from)，不能直接當成「montage orchestrator 入口」本身，比較像是 orchestrator
   呼叫的共用底層解碼 primitive——但這是本篇 §9 系列首次拿到一個 **live 執行流程實際命中、
   且與已知目標場景(結局 montage 渲染中)同時發生**的具體候選位址，遠比純靜態窮舉更有方向性。

**給下一輪的具體建議**：

1. 用 `tools/ghidra_batch_probe.py` 對 `0x4EC6A`/`0x4EE28` 做 `function_bounds`+`xref_from`
   查詢，找出真正的函式邊界與呼叫端——這是目前唯一有具體位址可查的線索，比 §9.1-9.7 對
   `0x2bce5`/`0x2c548` 的盲目窮舉更有機會定案。
2. 若呼叫端本身也不在已知 976-function 清單內(重演 §9.1 的「該區塊從未被 base 分析碰過」
   窘境)，可複用續六十二的方法——**先 set breakpoint、live RUN 到這個場景，命中瞬間對
   `D SS:ESP` 取值**(CALL 後 [ESP] 即為返回位址=呼叫端)，不需要靜態反組譯就能拿到下一層線索；
   這比純靜態方法更適合這個 project(§9.7.2 已記錄 decompile 引數渲染系統性失效，呼叫鏈追蹤
   本來就更依賴 live 佐證)。
3. 完整重現路徑(不需重新摸索)：doc58 續六十二 §2-3 已記錄從「全滅 47 格敵方 record」到
   「觸發勝利→CG 過場→詩句文字→角色卡」的完整操作序列與時間點，可直接複用，不需要重新
   反覆嘗試 doc58 續四十六~六十一 那套「真實逐格擊殺」路線。

## 9.9 2026-08-24(同日)— 對 §9.8 新候選 `0x4EC6A`/`0x4EE28` 做完整靜態反查：位址換算逐 byte
坐實，但兩者皆為深度共用的通用引擎原語(RLE 解壓縮 getbyte + `TXT(idx)` 對白播放器的字型描邊
子函式)，不是 montage 專屬 orchestrator——靜態方法論到此收斂到已知的死路，誠實負面結論

> 用 `tools/ghidra_batch_probe.py`(`disasm`/`function_bounds`/`decompile`/`call_scan`/`xref_from`)
> 對 §9.8 記錄的 native `0x4EC6A`/`0x4EE28` 做完整反查，依 §9.8 給下一輪的建議逐項執行。

### 9.9.1 位址換算:逐 byte 核對,`0x19C000` delta 在這個位址範圍精確成立,不需校正

`python tools/query_verified_address.py` 對 `0x4EC6A`/`0x4EE28`/`0x1EAC6A`/`0x1EAE28` 四個位址
查詢均回傳「資料庫裡沒有記錄」——這是全新位址,不在既有 `verified_addresses.json`/
`known_address_errata.json` 收錄範圍內,也不是任何已知勘誤對象。

用 `disasm` 對 native `0x4EC6A`/`0x4EE28` 直接反組譯,結果與 doc58 續六十二記錄的 live 手動取樣
**逐 byte 完全吻合**:

- native `0x4ec6a`:`fe cc`(`DEC AH`)+`c3`(`RET`) —— 對應 live `0x1EAC6A` 記錄的
  `FECC(dec ah); C3(ret); ...` 開頭兩個 byte。
- native `0x4ee28`:`fe c9`(`DEC CL`)、`75 ed`(`JNZ 0x4ee19`)、`5f`(`POP EDI`)、
  `03 fd`(`ADD EDI,EBP`)、`fe cd`(`DEC CH`)、`75 df`(`JNZ 0x4ee12`)、`61`(`POPAD`)、
  `5d`(`POP EBP`)、`c3`(`RET`) —— 與 live `0x1EAE28` 記錄的
  `FEC9; jne $-13; pop edi; add edi,ebp; FECD; jne $-21; popad; pop ebp; ret` **逐指令精確吻合**
  (`jne $-13`/`$-21` 是相對位移寫法,換算後正是 `0x4ee2a→0x4ee19`/`0x4ee31→0x4ee12`)。

**結論**:`native + 0x19C000 = live` 這個 delta 在這個位址範圍(0x4Exxx)一樣精確成立,不是近似值,
不需要额外校正——這是本專案第 N 次獨立交叉驗證這個 delta(見 doc58 續四十~續六十二的完整歷史),
這次補上的是「一個先前從未驗證過的新位址區段」也同樣吻合。

### 9.9.2 function_bounds:兩個位址落在兩個不同的小函式裡,不是同一段程式碼的頭尾

- native `0x4EC6A` 落在 `FUN_0004ec66`(`0x4ec66`–`0x4ec7b`,22 bytes)內部——不是函式進入點本身,
  是進入點往後 4 bytes 處的**第二個進入點**(典型的「多重 tail-entry 共用程式碼」手法,常見於
  手寫組合語言的小工具函式)。
- native `0x4EE28` 落在 `FUN_0004ed7a`(`0x4ed7a`–`0x4ee35`,188 bytes)的尾端(entry+0xae)。

兩者是**完全不同的兩個函式**,彼此沒有直接呼叫關係——doc58 續六十二把這兩個位址一併歸類成
「RLE 解碼迴圈」的假說,在 §9.9.3 逐一 decompile 後證實**只有一半成立**。

### 9.9.3 decompile:第一個確實是教科書級 RLE getbyte;第二個其實是 16×16 字型描邊繪製器,
跟 RLE 完全無關

**`FUN_0004ec66`**(含 `0x4EC6A`)——逐 byte 手動反組譯 22 bytes
(`0a e4 74 03 fe cc c3 ac 3c c0 77 03 32 e4 c3 8a e0 80 ec c1 ac c3`)+ Ghidra decompile
兩相印證,結構為:

```
OR AH,AH          ; 測試「剩餘重複次數」計數器(AH)
JZ  read_new       ; 若計數器為 0,讀新的 control byte
DEC AH             ; 否則計數器 -1(仍在重複填色模式)
RET                ; 回傳(AL 沿用上次呼叫留下的填色值——呼叫端把 EAX 當狀態保存)
read_new:
LODSB              ; AL = *ESI++,讀 control byte
CMP AL,0xC0
JA  is_run
XOR AH,AH
RET                ; literal byte(<=0xC0),回傳,計數器歸零
is_run:
MOV AH,AL
SUB AH,0xC1        ; AH = 重複次數-1
LODSB              ; AL = *ESI++,讀填色值
RET
```

這是標準的 run-length-encoded bytestream「取下一個解壓縮 byte」原語,與 doc58 續六十二對
live `0x1EAC6A` 的判讀(「教科書等級的 RLE 解碼原語」)**完全吻合**,這部分假說成立。

**`FUN_0004ed7a`**(含 `0x4EE28`)——decompile 出來的結構跟 RLE **完全無關**,是一個
**16×16 點陣字型/圖示描邊繪製器**:

1. 前段:把 10 個參數存進一批全域(`DAT_000627a3`~`DAT_000627b0`),若填色參數
   (`param_10`,即描邊背景色)非 0,先用它把 16 列(每列 4 個 dword=16 px)的目的緩衝區全部
   填滿——即字元格背景/底色。
2. 後段:`DAT_000627ac + DAT_000627b0 * 0x20` 是字型表基底(以「字元碼 × 0x20 bytes」定位,
   0x20=32 bytes=16 列 × 2 bytes/列,是標準 16×16 單色點陣字型格式);逐列讀一個
   16-bit bitmask,逐 bit 檢查,若該 bit 為 1,對輸出緩衝區同一位置寫 3 個像素:
   `puVar9`(主體色 `uVar1`)、`puVar9-1`(左側描邊色 `uVar2`)、`puVar9+1`(右側描邊色 `uVar2`)——
   這是標準的「主體色+左右描邊色」文字繪製手法(常見於 RPG 對話框文字加陰影/描邊,確保文字
   在任何背景上都可讀)。尾端 `fe c9;75 ed;...popad;pop ebp;ret`(即 live `0x1EAE28`)正是這組
   雙層 16×16 迴圈(內層逐 bit、外層逐列)收尾的部分。

**結論**:doc58 續六十二「兩次取樣都落在同一個 RLE 解碼迴圈附近」的判讀**只對了一半**——
`0x1EAC6A`(CG 過場取樣)確實是 RLE getbyte,`0x1EAE28`(角色卡取樣)其實是**完全不同、
語意上是文字描邊繪製**的函式,只是兩次取樣剛好落在程式碼記憶體裡相鄰的位置(`0x4ec66`/
`0x4ed7a` 相距僅 0x114 bytes,同屬 `.object1` 這個小型美術/文字工具函式聚落),兩者之間
**沒有呼叫關係**,不應該被當成同一個機制的兩個切面。

### 9.9.4 call_scan 逐層往上追:兩條線都在 2-3 層內收斂到「深度共用的通用引擎原語」,符合
本篇任務自己預先訂的「幾十個不相關呼叫點=generic utility」判準

**RLE getbyte 這條線**(`FUN_0004ec66`):

- 直接呼叫者只有 3 個(`0x4ebcb`∈`FUN_0004ebab`、`0x4ec1f`∈`FUN_0004ebff`、
  `0x4ec51`∈`FUN_0004ec31`),乍看很集中。
- 但這 3 個 sibling 函式各自被呼叫的地方分別是 **9 / 36 / 5** 個直接呼叫點,散佈在
  `0x15f77`(對白系統)、`0x1c60a`/`0x1cc14`/`0x1ddcd`/`0x1de3a`/`0x1e0b0`(戰鬥選單/走位一帶)、
  `0x224f5`/`0x225a3`(另一批選單邏輯)、`0x2663d`~`0x2b012`(spell/FIGANI 特效一帶,doc37 涵蓋
  的區段)、`0x32ab5` 等等——橫跨全 EXE 幾乎所有已知子系統,語意完全不相關。這確認
  `FUN_0004ec66` 及其 3 個 wrapper 是一個**通用的「解壓縮資料到緩衝區」引擎工具**,任何
  地方只要要展開一段 RLE 壓縮資料(文字表、圖塊、調色盤…)都會呼叫它,不是 montage 專屬。

**字型描邊繪製這條線**(`FUN_0004ed7a`):

- 直接呼叫者只有 2 個(`0x16119`/`0x16477`),而且**兩者都在同一個函式** `FUN_00015f84` 內部,
  看起來高度集中,像是找到專屬呼叫端了。
- 但 `FUN_00015f84` **早就是本專案 doc50(`50-cutscene-script-system-design.md` L19/L29)
  記載的已知函式**——就是全遊戲通用的 **`TXT(idx)` 對白播放原語**(「播章文本第 idx 條
  (開框/頭像/翻頁)」),`call_scan` 對它本身找到 **296 個直接呼叫點**,散佈在
  `0x100e9` 到 `0x32e24`+ 幾乎整個 EXE 範圍,含自我遞迴呼叫(`0x16073`)。decompile 顯示它是
  一個 bytecode 腳本直譯器:讀一串 `short` 控制碼陣列,`-1`=結束、`-2`/`-3`=換行/分頁(並在
  特定音樂 ID 下插入 `FUN_00016e24` 額外處理)、`-4`/`-5`=遞迴呼叫下一段腳本(`FUN_00015f84`
  呼叫自己)、`-6`=迴圈畫 `bVar3` 張 portrait/字卡(逐次呼叫 `FUN_0004ed7a` 畫一張)、
  `-0x11`~`-0x14`=切換 `DAT_00053c67`(音樂/場景 ID,`0x728`/`0x9017`)並重置狀態、
  default(其餘正值)=畫一行文字(呼叫一次 `FUN_0004ed7a`,`iVar5 += 0x10` 換行)。這與 doc50
  對 `TXT(idx)` 的既有描述(對白逐條播放、含開框/頭像/翻頁)完全吻合,是**全 27 章對白系統共用
  的通用直譯器**,doc50 §3 記載的每一章 cutscene compiler 輸出都會呼叫它。

### 9.9.5 誠實結論

1. **§9.8 的位址換算完全正確**:`native + 0x19C000 = live` 這次在全新位址範圍(`0x4Exxx`)
   逐 byte 精確吻合,`0x4EC6A`/`0x4EE28` 兩個 native 位址本身沒有問題。
2. **`0x1EAC6A`(native `0x4EC6A`)確實是 RLE 解碼原語,`0x1EAE28`(native `0x4EE28`)其實是
   一個跟 RLE 完全無關的 16×16 字型描邊繪製子函式**——§9.8「兩者是同一個 RLE 迴圈」的假說
   訂正:只有一半成立,兩者只是程式碼位置相鄰,沒有呼叫關係。
3. **兩者都不是 ending montage 專屬的 orchestrator,而是深度共用的通用引擎原語**,完全符合
   本篇任務自己預先訂出的判準(「若從幾十個不相關地方被呼叫,是 generic utility 而非
   dedicated renderer」)——RLE getbyte 一線在 2 層內發散到 9+36+5 個跨子系統呼叫點;
   字型描邊一線更極端,2 層內直接撞進 doc50 早已記載、擁有 **296 個呼叫點**的全遊戲共用
   `TXT(idx)` 對白直譯器。這不是新發現的子系統,是本專案文件裡本來就有名字、有位址、
   全遊戲每一章都在用的既有機制。
4. **對 doc91 11 個 worklist 項目的影響**:本輪**沒有**達成「定位到專屬 montage orchestrator」
   這個目標,§9.1–9.9 累積下來的證據形狀高度一致——不只是「找不到 `0x2bce5`/`0x2c548`」,
   連 §9.8 補的新候選線索,往上追蹤也一樣收斂到通用共用機制。這跟 doc35 §9.2 對戰鬥指令
   選單得到的既有結論(「完整可驗證的 FIGANI/TAI.DAT/BG.DAT/FDOTHER.DAT phase-table 演出
   引擎」)是同一種架構模式的側面印證:**這個引擎很可能根本沒有「一個特定 function 是
   ending montage 的 orchestrator」這種東西**——真正驅動 montage 演出的很可能是餵給
   `FUN_00015f84`(`TXT`)這個通用直譯器的**一段特定 script/bytecode 資料**(放在某個
   FDTXT/資源檔裡,尚未定位是哪一份、哪個 index),而不是一段獨立的 CODE。継續在 CODE
   空間裡找「montage 專屬 function」這件事,本身可能是問錯問題。
5. **給下一輪的具體建議(如果要繼續這條線)**:不要再往 `FUN_00015f84` 的 296 個呼叫點上游
   窮舉(不可行,且 §9.7 全域行為指紋掃描已經證明這類窮舉在本專案容易撞上更根本的
   decompile 引數盲點)。改成 **live 方法**——在確認 YES 觸發勝利、即將進入 CG/詩句/角色卡
   畫面前,對 `TXT`(live `0x15f84+0x19C000=0x1B1F84`)入口設中斷點,命中時直接讀
   `param_1`/`param_2`(依 doc50 `TXT(idx)` 簽名,通常是 text_index 或章節文本表指標)與
   `D SS:ESP` 找呼叫端——這樣才可能找到「是哪個 chapter handler / 哪個 index 把 ending
   montage 的文本/演出腳本餵給這個通用直譯器」,而不是繼續在 leaf 原語層面打轉。這個方法論
   跟 doc58 續六十二 §4 建議 2 一致,只是這次補上了具體理由：**呼叫端在 976-function 清單內
   不代表能收斂——因為這個特定呼叫端(`TXT`)本身就是全遊戲共用的直譯器,問題的答案在
   「餵給它的資料」而不是「呼叫它的 CODE」**。

## 9.10 2026-08-25 — 執行 §9.9 的具體建議:對 `TXT` 入口(live `0x1B1F84`)下斷點 live 捕捉呼叫參數,
找到一個真正專屬、不在 976-function 清單內的 character-card 共用 renderer;附帶一個意外發現——
本篇一直在追的「結局 montage」內容其實在 ch27 **戰前**就會播放一次(轉送站幻象),不需要 47 格全滅
捷徑就能重現(doc58 續六十四完整記錄,本節摘要靜態相關部分)

> 完整 live 操作過程、環境 bug、UI 導覽細節見 `docs/knowledge-base/58-remake-live-verification-log.md`
> 續六十四。本節只摘錄對本篇 11 個 worklist 項目直接相關的靜態反查結論。

### 9.10.1 `TXT` 斷點 live 命中,揪出一段真正專屬的呼叫序列:native `0x320a1..0x32139`(~150 bytes)

在結局 montage 畫面(CG 過場+角色卡)播放期間,對 `TXT`(native `0x15f84`,live `0x1B1F84`)入口
下斷點並連續 `RUN`,`D SS:ESP` 逐次讀出 `[ESP+0]`=return address、`[ESP+4]`=`param_1`(FDTXT table
指標)、`[ESP+8]`=`param_2`(=idx),與 doc50/SESSION-HANDOFF-2026-07-06 記載的 `TXT([0x53a79 或
0x53a7d], idx, ...)` cdecl ABI 逐 byte 吻合。連續 5 次命中的 return address(native)**精確循環
重複**:`0x320a1`(idx=10)→`0x320ce`(idx=7)→`0x320f7`(idx=11)→`0x32128`(idx=153)→`0x32165`
(idx=18)→回到 `0x320a1`——證實這是**同一個函式內連續 5 次 `CALL 0x15f84`**,不是 `TXT` 自身遞迴。

### 9.10.2 靜態反查:`function_bounds`/`xref_to` 全部落空(與舊候選 cluster 同宗同源的「未分析區域」),
但 `disasm` 顯示這段程式碼**混合硬編碼常數與 `EBP` 相對欄位計算**,不是通用原語

`ghidra_batch_probe.py` 對 native `0x320a1` 查詢:

- `function_bounds`:`{"in_function": false, "note": "address not contained in any known function
  boundary"}`——與 §9.1/§9.7 反覆撞到的「這塊區域從未被 base analysis 碰過」**完全同宗同源**。
- `xref_to`:0 筆——與舊候選 cluster 的「零 xref」症狀一模一樣。
- `disasm`(`0x320a1..0x32139`,46 條指令):每次呼叫前 `PUSH 0,0,0,0x4C,0xCD,0x140`(6 個常數)、
  `LEA EAX,[ESI+<偏移>]; PUSH EAX`(字串/資源指標),然後或是 `MOVZX EAX,[EBP+8]; INC EAX; PUSH EAX`
  (用 `EBP+8` 算出 idx=10/7)、或是直接 `PUSH 0xB`(字面常數 idx=11)、或是 `MOVZX EAX,[EBP+0x20];
  ADD EAX,0x96; PUSH EAX`(用 `EBP+0x20`+150 算出 idx=153),最後 `PUSH [0x53a79]` 或
  `PUSH [0x53a7d]`、`CALL 0x15f84`。`0x32128` 之後接 `CMP EDI,0xDC; JGE ...` 迴圈控制。

**性質判定(高信心)**:這**不是**§9.9 判定過的「深度共用通用引擎原語」(RLE getbyte／字型描邊,
2-3 層內發散到幾十個不相關呼叫點、296 個呼叫點的 `TXT` 本身)——這段「大部分寫死常數、只有少數
欄位參數化」的模式,是針對某個特定畫面手寫的**專屬呼叫序列**,不是可被任意呼叫端重用的通用 API。

### 9.10.3 Live 交叉驗證:同一段 `0x320a1` 序列透過改變 `EBP`(角色 record 指標)被複用在萊汀卡與
悠妮卡兩張不同角色卡上——證實是「角色卡共用 renderer」

萊汀卡畫面時 `EBP=0026B3D8`,推進到悠妮卡畫面後重新命中的斷點顯示**呼叫序列完全相同**
(return address 依然精確是 `0x320a1`、idx=10、table 指標 `0x238238`),但 `EBP` 已變成
`0026B068`(指向悠妮的 record 緩衝區)。**結論**:`0x320a1` 起的呼叫序列是一個單一、專屬、被
複用的「畫一張角色卡」渲染函式,不同角色卡之間只有 `EBP` 不同,呼叫序列本身完全一致。

### 9.10.4 對 §9.9.5 兩個開放問題的回應

1. **問題(a)「是否有 specific、findable 的 caller/data-table」——本輪答案是部分成立的「有」**:
   `0x320a1` 起~150 bytes 是一段真正專屬、被角色卡渲染重複使用、不在 976-function 清單內的
   **CODE**(不是純資料),與 §9.9 判定的「深度共用通用引擎原語」性質不同——只服務角色卡渲染
   這一種用途,沒有觀察到被其他子系統呼叫的證據。
2. **問題(b)「genuinely indistinguishable from any other TXT call」——本輪答案是「不是」**:
   `0x320a1` 的呼叫序列有清楚可辨識特徵(硬編碼常數混合 `EBP` 相對欄位計算、固定 5 次連續呼叫
   模式、`EDI` 迴圈計數器控制),只是**目前只能靠 live 執行流程配合手動 disasm 找到**——Ghidra
   的自動化靜態分析(`function_bounds`/`xref_to`/`call_scan`)在這個區域全部失靈,這解釋了
   §9.1-9.7 累積 5 輪失敗的根本原因:**不是候選位址找錯,是整塊未分析程式碼區域讓任何純靜態
   方法在這裡都注定失敗**,除非先用 live 執行流程標出至少一個真實命中位址、再回頭手動 disasm。

### 9.10.5 未完全閉環的缺口(誠實記錄)

1. **呼叫鏈未 100% 證實**:`0x320a1` 本身不是函式進入點(是某個更早 CALL 的返回位址),本輪
   沒有找到真正的函式邊界(prologue),也沒有找到呼叫這整個函式的呼叫端——`xref_to`/`call_scan`
   對 `0x320a1` 與 ch27 戰前 handler 入口 `0x33c9d`(用章節分派表 `0x51d71[27]` 定位、
   `disasm` 核對其開頭 `CALL 0x205da`=`LOADCH` 原語確認合法性)皆 0 筆命中,兩者只能確認同屬
   一塊緊鄰的未分析程式碼區,不能給出精確的 CALL 指令位址。
2. **doc58 續六十四的意外發現**:本篇一直在追的「結局 montage」內容,其實在 ch27 **戰前**
   (camp exit confirm YES 之後、真正抵達可操作戰場之前)就會完整播放一次「轉送站幻象」版本,
   文字與 doc58 續六十二記錄的**戰後真實 montage 逐句相同**——不需要 47 格死亡 signature+
   End Turn 確認的整套流程就能重現視覺/文字內容,但本輪**未查證**戰前/戰後兩條路徑是否共用
   完全相同的呼叫序列起點。
3. **悠妮卡永久循環**:doc58 續六十二與續六十四在兩條獨立路徑(戰後真實 montage / 戰前幻象)
   都卡在悠妮卡同一組 2 段文字,續六十四排除了「換個方向鍵就能推進」的假說(5 個方向鍵+15 次
   連續快速按 `Down` 全部無效)——目前最合理的解讀是這是演出腳本的設計終點,但沒有直接反組譯
   `0x320a1` 所在函式的迴圈退出條件去 100% 坐實。
4. **舊候選 `0x2bce5`/`0x2c548`**:本輪在戰前幻象這條全新路徑下再次確認 live 不可達,§9.1 的
   負面結論維持不變。

**對 11 個 worklist 項目的影響**:本輪定位到一個真正專屬的 character-card renderer,回答了
§9.9.5 的核心問題(montage 不是「純資料無專屬 CODE」),但 §9.10.5 記錄的呼叫鏈缺口與悠妮卡
終點判斷仍是高信心推論而非 100% 閉環證據,依專案一貫標準暫不足以標記 11 個項目為「完全解封」,
留給下一輪視是否需要補齊 `0x33c9d`→`0x320a1` 的直接 CALL 證據、或反組譯迴圈退出條件來決定。

## 9.11 2026-08-25 — 純靜態方法補齊 §9.10.5 呼叫鏈缺口:手動 instruction-boundary 回溯找到
`0x320a1` 的真正函式邊界與唯一呼叫端,`call_scan` 逐層向上追出完整鏈,但真正的觸發點是
**ch26/ch29 戰後(`post`)handler,不是 `0x33c9d`(ch27 戰前 handler)**——訂正 §9.10 的框架、
順手解開「悠妮卡永久循環」懸案(binary 裡就是硬編碼 `JMP $` 死迴圈),`0x2bce5` 仍是另一個未解問題

> 任務動機:接手 §9.10.5 留下的具體缺口——`0x320a1` 的 `function_bounds`/`xref_to`/`call_scan`
> 全空,`0x33c9d`(ch27 戰前 handler)本身的 `call_scan`/往下 disasm 也接不上 `0x320a1`。本輪
> 目標是用同一套「從已知函式邊界逐 byte/逐指令手動回溯」方法論(呼應 doc25 §11.7 event58/76/78
> 的做法)先把 `0x320a1` 真正的函式起點找出來,再對起點做 `call_scan`(而不是對 `0x320a1` 這個
> return address 本身做,那從方法論上就不可能有命中)。

### 9.11.1 方法:`0x320a1` 不是函式進入點,用 Capstone 離線反組譯 + 手動 offset 對齊,逐層往回找「上一個函式的 `RET`」

`ghidra_batch_probe.py` 的 `disasm` action 只能「從指定位址往前走」,不能往回走(x86 變長指令
天生不可反向解碼)。改用 `bytes` action 撈大段原始 hex,搭配本機 `capstone`(`pip` 已裝,
`CS_ARCH_X86`/`CS_MODE_32`)離線反組譯、用「已知 `0x3209c` 是合法 `CALL` 指令邊界」這個錨點
去試探不同起始 offset,找出哪個 offset 能一路自我同步、無縫銜接到 `0x3209c`。逐步往回擴大
查詢範圍(`0x31f00`→`0x31c00`→`0x31800`→`0x31600`→`0x31400`),每次都用「這一段裡有沒有出現
`RET`,`RET` 後面是不是接著一個眼熟的 prologue」來判斷有沒有撞到真正的函式邊界。

**關鍵 prologue signature**(本 project 這個區塊的章節/場景 handler 慣用手法,與 `0x33c9d` 開頭
`PUSH 0x2C; CALL 0x3702f`(配置緩衝區)完全同宗):`PUSH <size>; CALL 0x3702f`(配置一塊
`size` bytes 的緩衝區)接著 `PUSH EBX,ESI,EDI,EBP; SUB ESP,<frame size>`(存 4 個 callee-saved
暫存器+開堆疊框)。這個 signature 在 `0x31c49` 與 `0x31529` 兩處各命中一次,且兩次都**緊接在
上一個函式的 `RET` 之後**——不是巧合湊出來的邊界,是真正的函式起點。

### 9.11.2 第一層:`0x320a1` 所在函式的真正起點是 `0x31c49`(不是 `0x320a1` 自己)

從 `0x31c00` 往回查到 `0x31c48: POP EBX; RET`,緊接著 `0x31c49: PUSH 0x5c; CALL 0x3702f`
(配置 92-byte 緩衝區)→`PUSH EBX,ESI,EDI,EBP; SUB ESP,0x24`——這就是包住 `0x320a1` 的
**真正函式進入點**。往前用 Capstone 對齊反組譯(offset 0,自 `0x31c49` 起共 191 條指令、
一路無縫到 `0x321ab` 都沒有再撞到 `RET`),證實 doc58 續六十四 live 捕捉到的 5 次 `TXT` 呼叫
序列(`0x320a1/0x320ce/0x320f7/0x32128/0x32165`,idx=10/7/11/153/18,table 指標
`0x53a79`/`0x53a7d`)**逐 byte 落在這同一個函式體內**,不是獨立函式——`0x3209c` 的
`CALL 0x15f84` 用 `bytes` action 直接讀原始位元組確認為 `E8 E3 3E FE FF`(disp32=`0xFFFE3EE3`,
`0x3209c+5+disp32=0x15f84`,精確吻合 `TXT` 位址),回傳位址正是 `0x320a1`——與 live 記錄
完全對上,這是本輪第一個「純靜態複現 live 發現」的交叉驗證。

對 `0x31c49` 做 `call_scan`:**恰好 1 筆命中,`0x319d3`,`confirmed_call_instruction: true`**。

### 9.11.3 第二層:`0x319d3` 本身落在另一個更大的函式裡,其真正起點是 `0x31529`——一個「換場+角色卡」的 orchestrator

`0x319d3` 所在的函式(稱為 G)做的事:畫面淡出/擦除迴圈(`EBX` 0→0xc8,呼叫已知的
`0x11eb0`/`0x3771c`)、依全域變數 `[0x53c03]`(目前章節編號)是否等於 `0x1a`(26)分支選擇
不同的裝飾圖示資源 id(`0x15/0x16/0x17` vs 通用的 `8/9`,兩處各出現一次同款分支,即
`cmp dword[0x53c03],0x1a; jne ...`)、然後在 `0x319d3` 呼叫 `0x31c49`(角色卡渲染,見 9.11.2)。
繼續往回查(`0x31800`→`0x31600`→`0x31400`),在 `0x31528: POP EDI; POP ESI; RET` 之後找到
G 的真正起點:`0x31529: PUSH 0x80; CALL 0x3702f`(配置 128-byte 緩衝區)→
`PUSH EBX,ESI,EDI,EBP; SUB ESP,0x54`——與 `0x31c49`/`0x33c9d` 同一套 prologue signature。

對 `0x31529` 做 `call_scan`:**恰好 2 筆命中,`0x2545d` 與 `0x25970`,皆
`confirmed_call_instruction: true`**——這是全 exe 範圍(`.object1/2/3`,`E8` opcode 逐 byte
掃描)的窮舉結果,不是抽樣。

### 9.11.4 第三層:`0x2545d`/`0x25970` 分別是 ch26、ch29 **戰後(post-battle)**handler 內部的呼叫點——與 doc39 既有結論獨立交叉吻合,但訂正了 doc58 續六十四「ch27 戰前」的框架

用 `bytes` action 重新讀出「戰後」跳表 `0x51de9`(32 個 4-byte 指標,與 doc50 記載一致)並自行
解碼(不沿用舊記錄,重新算一次):

| idx | native handler 位址 |
|---|---|
| 25 | `0x24e80` |
| **26** | **`0x250cc`** |
| 27 | `0x25464` |
| 28 | `0x2548c` |
| **29** | **`0x25757`** |
| 30 | `0x13130101`(非法指標,代表表格有效範圍只到 idx29) |

`0x250cc ≤ 0x2545d < 0x25464` → `0x2545d` 落在 **idx26(ch26 戰後 handler)** 的函式體內;
`0x25757 ≤ 0x25970`(idx30 起已是非法值,無上界,但 `0x25977` 緊接在後、已知是獨立的
`play_bgm` 函式起點,doc12 §15 已證實,精確卡出 `0x25757` 所屬函式的實際結尾)→ `0x25970`
落在 **idx29(ch29 戰後 handler,亦即全遊戲最後一戰的戰後 handler)** 的函式體內。這與
`docs/knowledge-base/39-ani-afm-format.md` L253 既有記錄(「`0x02bce5` 的呼叫端為
`0x2545d`/`0x25970`,兩者分別落在戰後跳表 `0x51de9` 第 26/29 項」)**用完全獨立的方法論
(本輪:call_scan 窮舉+自行重新解碼跳表;doc39:另一輪 Docker Capstone)得出同一組位址**,
是強交叉驗證。

逐指令核對兩處呼叫點的完整 byte 序列(Capstone):

```
0x25458: CALL 0x25089          ; 已知的 reset_persistent_roster_state(worklist#1173/1898)
0x2545d: CALL 0x31529          ; ← 本輪新確認,即 §9.11.3 的 G
0x25462: JMP 0x25462           ; EB FE,無條件跳自己,死迴圈
0x25464: ...                   ; 下一個 handler(idx27)起點,doc56 已知的 trampoline
```

```
0x25968: CALL 0x15f84          ; TXT(單句對白,先於角色卡序列)
0x2596d: ADD ESP,0x24
0x25970: CALL 0x31529          ; ← 本輪新確認,即 §9.11.3 的 G
0x25975: JMP 0x25975           ; EB FE,無條件跳自己,死迴圈
0x25977: ...                   ; play_bgm(doc12 §15 已證實),獨立函式邊界確認乾淨對齊
```

**因此完整、100% byte-level 靜態證據鏈是**:

```
table_post[26]=0x250cc (ch26 戰後 handler)
  └─ 0x2545d: CALL 0x31529
table_post[29]=0x25757 (ch29 戰後 handler,全遊戲最後一戰)
  └─ 0x25970: CALL 0x31529
         │  (兩處呼叫端皆用 call_scan 全域窮舉confirmed,無第三個呼叫端)
         ▼
0x31529 = G:換場淡出/擦除 + 依 [0x53c03]==26 分支挑裝飾圖示 id
  └─ 0x319d3: CALL 0x31c49        (call_scan 全域窮舉:僅此 1 筆)
         ▼
0x31c49 = 角色卡 renderer 本體(191+ 條指令、內含 5 次連續 CALL 0x15f84 序列)
  └─ 0x3209c: CALL 0x15f84 (TXT)  → 返回位址 0x320a1
         ▼
0x320a1  == doc58 續六十四 live 斷點捕捉到的 return address,逐 byte 吻合
         (idx=10, table=[0x53a79]=0x238238;同函式內另外 4 次呼叫 0x320ce/0x320f7/
          0x32128/0x32165 亦逐 byte 對上 live 記錄的 idx=7/11/153/18)
```

### 9.11.5 訂正 §9.10 的框架:`0x33c9d`(ch27 戰前 handler)與這條鏈無關,doc58 續六十四的
「ch27 戰前」是玩家敘事體感上的誤標,實際觸發點是 ch26 戰後 handler 的尾段

本輪也順手把 §9.10.5 缺口清單裡「`0x33c9d`→`0x320a1`」這個假設方向徹底排除:對 `0x33c9d`
(章節分派表「戰前」`0x51d71[27]` 的 ch27 handler入口)往下逐段 `disasm`(`0x33cbb`→
`0x33cef`→`0x33d11`,3 段共 30 條指令,`stop_reason` 分別為 `jmp`/`jmp`/`jmp`),內容是
**單純的 20-slot unit record 迴圈**——逐格檢查 `word[EAX+0x40]`(存活判定)、清
`byte[EAX+5]` 的 bit(`0x24-battle-input-dispatch` 已證實的 `Acted` 旗標)——這是**戰鬥開打前
重置角色「已行動」旗標**的例行初始化,與角色卡/montage 完全無關。`0x33c9d` 本身不在
`0x31529`/`0x31c49` 的 `call_scan` 命中清單裡,現在確定不是巧合,是**兩條完全獨立的呼叫鏈**:
`0x33c9d`(戰前跳表 idx27)是 ch27 這場戰鬥本身的初始化,`0x250cc`(戰後跳表 idx26)是
「ch26 戰鬥結束後」的過場劇情(camp、對話、幻象),兩者在敘事上緊鄰(玩家會先看到 ch26
戰後過場,再進入 ch27 戰鬥),但在 code 上是兩個完全不相干、分屬不同跳表的 handler。doc58
續六十四把這段內容記成「ch27 戰前」,是以玩家操作順序(LOAD 存檔→出營confirm YES→過場)
命名,體感上合理但技術上不精確——**本節在此訂正**:正確技術描述是「ch26 戰後 handler
(`table_post[26]=0x250cc`)尾段的角色卡演出」,不是「ch27 戰前 handler」。

### 9.11.6 副產品:「悠妮卡永久循環」懸案解開——binary 裡就是硬編碼 `JMP $` 死迴圈,不是輸入處理漏測

doc35 §9.10.5 第 3 點與 doc58 續六十二/續六十四都獨立卡在悠妮卡同一組 2 段文字,當時只能
「高信心推論」是演出腳本設計終點。本輪從 §9.11.4 的逐指令核對直接拿到答案:**`0x2545d`與
`0x25970` 呼叫 `0x31529` 之後,緊接著的下一條指令就是 `EB FE`(`JMP` 自己的位址)**——
一個無條件、無任何退出分支的 2-byte 死迴圈,兩個呼叫端(ch26 戰後、ch29 戰後)都是一樣的
寫法。這不是「還有沒測到的按鍵」,是編譯進 binary 的**硬性死路**:一旦執行流走到這裡,
CPU 永遠停在同一條指令,任何鍵盤輸入都不可能讓它往下執行——doc58 兩輪 live 測試分別在
戰後真實 montage(續六十二)與這次證實其實是「ch26 戰後」的路徑(續六十四)都卡在悠妮卡,
現在確認是**同一個根因**:兩條呼叫路徑最終都走到這同一個 `0x31529`,`0x31529` 內部渲染完
角色卡序列、返回上層之後,上層呼叫端立刻自我鎖死。

### 9.11.7 `0x320a1`(經 `0x31529`/`0x31c49`)是否在其他地方被重用——`call_scan` 給出精確、窮舉的否定+肯定答案

`call_scan(0x320a1)`:0 筆(預期中——`0x320a1` 是 `CALL 0x15f84` 的 return address,不是任何
指令的合法呼叫目標,本來就不該被 `CALL` 到)。`call_scan(0x31c49)`:僅 1 筆(`0x319d3`,即
`0x31529` 內部)。`call_scan(0x31529)`:僅 2 筆(`0x2545d`/`0x25970`)。三層全部用 `E8` opcode
對 `.object1`/`.object2`/`.object3` 全區段逐 byte 掃描,不依賴 Ghidra 的 `xref_to`(已知在這個
`-noanalysis` project 裡會漏筆,見 `call_scan` 工具本身的說明)。**結論(高信心,窮舉而非抽樣)**:
這個角色卡 renderer 鏈**只在 ch26 戰後與 ch29 戰後這兩個 handler 被呼叫,不是通用的
「角色選單/狀態畫面」共用元件,也沒有被結局以外的任何場景重用**——doc35 §9.10.4 問題(a)
判定的「有 specific、findable 的 caller」現在有了精確、窮舉驗證的座標。

### 9.11.8 誠實範圍:本輪**沒有**解開 `0x2bce5`/`0x2c548` 的資產解碼問題,`91-worklist.md`
11 個相關項目維持原狀不動;另外發現一處與既有文件的位址表述落差,留給下一輪核對

**任務原始要求的「補齊 `0x33c9d`→`0x320a1` 呼叫鏈」現在已經 100% 完成**——只是實際存在的
鏈路不是 `0x33c9d`,是 `table_post[26]`/`table_post[29]`(見 §9.11.5 的訂正)。但這**不等於**
解決了 `91-worklist.md` 裡以 `0x2bce5`/`native_2c548.json` 為核心的 11 個「party montage 資產
解碼」項目(#862/863/1017-1020/1226/1347-1354/1570-1608/1897-1898 等)——那是完全不同的問題
(FDOTHER#54/#56、TAI.DAT、FIGANI/DATO 這些**圖形資產格式**要怎麼組成 CG 過場動畫),`0x2bce5`
本身在本輪 `call_scan` 全域掃描下**0 筆直接 `CALL`**,代表它若真的會被呼叫,一定是透過間接呼叫
(本輪在回溯 `0x31529` 過程中,於其前一個不相關的 helper function 內看到一個
`CALL dword ptr [EBP*4+0x524c6]` 的 indirect call/跳轉表模式,不確定是否與 `0x2bce5` 有關,
**未驗證**,留給下一輪)。**因此本輪不更新 `91-worklist.md` 那 11 個項目**——它們描述的問題
本輪完全沒有觸碰,標記解封會是誤報。

**另需下一輪核對的落差**:`91-worklist.md` 第 1179/1898 行等既有記錄寫的是「`0x25970 → 0x2bce5`
返回後 self-loop」,與本輪逐位元組核對出的「`0x25970 → 0x31529` 返回後 self-loop」字面上的
呼叫目標不同(死迴圈本身的觀察是一致的)。本輪的結論來自對原始 bytes 做 `E8 <disp32>` 手算+
Capstone 交叉核對(見 §9.11.4 程式碼區塊),信心很高,但**沒有**回頭查證舊記錄當時用的是
什麼方法論得出 `0x2bce5` 這個目標(可能是決定於 decompile 偽代碼、可能是同一個 handler 內
另一個未探索到的間接呼叫點、也可能是舊記錄本身的簡化標註)——不在本輪誤改或誤判舊文件對錯,
單純如實記錄這個落差供下一輪核對。

## 9.12 2026-08-25 — 接手 §9.11.8 留下的落差:第二輪獨立 `ghidra_batch_probe.py` 覆核確認
`0x2545d`/`0x25970` 的 CALL 目標**只有** `0x31529`,`0x2bce5` 從未在全 exe 任何位置被直接
`CALL` 過——`91-worklist.md`/doc39/doc50/SESSION-HANDOFF/doc58 的舊 claim 是位址誤植,已加入
`known_address_errata.json`,並訂正 doc58 續三十二~續六十四整條 ch27 live 驗證任務的前提

> 任務動機:§9.11.8 誠實記錄了一個未查證的落差——舊文件(`91-worklist.md` L1179/L1898、
> doc39 L253)寫「`0x2545d`/`0x25970 → 0x2bce5`」,本輪 §9.11 逐 byte 核對出的是
> `→ 0x31529`,但沒有回頭確認舊 claim 當時的方法論、也沒有查這個字面數字落差是否已經影響到
> 其他文件。本輪目標:(1) 用**第二輪、完全獨立**的 `ghidra_batch_probe.py` 呼叫(不沿用
> §9.11 的 Capstone 手算過程,重新對 `0x25970`/`0x2545d`/`0x2bce5`/`0x31529` 做
> `disasm`/`bytes`/`call_scan`/`xref_to`)覆核 §9.11 的結論是否可獨立複現;(2) 全文搜尋
> `docs/knowledge-base/` 找出這個 `0x2bce5` claim 的**每一處**引用與**最初出處**;(3) 判定
> `0x2bce5` 是否曾經有任何真實 byte 證據支持這個呼叫邊,或是從一開始就是誤植;(4) 若確認是
> 誤植,依專案慣例登記 `known_address_errata.json` 並訂正所有受影響文件。

### 9.12.1 獨立覆核結果:與 §9.11 逐 byte 完全一致,`0x2bce5` 全 exe 掃描 0 筆直接 CALL

第二輪查詢(`fb1/fb2/d1/d2/b1/b2/cs1/cs2/x1/x2`,10 筆全部 `ok: true`,8.0s 完成)結果:

- **`bytes(0x25970,16)`** = `e8 b4 bb 00 00 eb fe 68 14 00 00 00 e8 ae 16 01`——`CALL` opcode
  `E8` 後 disp32(little-endian)`b4 bb 00 00` = `0x0000bbb4`,`0x25970+5+0xbbb4 = 0x31529`。
  緊接 `eb fe`(`0x25975: JMP 0x25975`,自我死迴圈)。
- **`bytes(0x2545d,16)`** = `e8 c7 c0 00 00 eb fe 68 28 00 00 00 e8 c1 1b 01`——disp32
  `c7 c0 00 00` = `0x0000c0c7`,`0x2545d+5+0xc0c7 = 0x31529`。緊接 `eb fe`
  (`0x25462: JMP 0x25462`,自我死迴圈)。
- **`disasm(0x25940..0x25975)`**(16 條指令,`stop_reason=jmp`)完整重現 §9.11.4 記錄的指令序列
  (`PUSH [0x53a79]; CALL 0x15f84`=TXT → `ADD ESP,0x24` → `CALL 0x31529` → `EB FE`),Ghidra
  的 `disasm` action 直接把 `0x25970` 的 `operands` 解成 `0x00031529`,不需要手算 disp32。
- **`call_scan(0x2bce5)`**:對 `.object1`(0x10000-0x4ef28)、`.object2`(0x50000-0x556af)、
  `.object3`(0x60000-0x634d1)、`.image`(0x0-0x7c4e5)**全區段** `E8` opcode 逐 byte 掃描,
  `raw_candidates: 0`,`hits: []`,`count: 0`——**`0x2bce5` 在整個 binary 裡沒有任何一處被
  `CALL` 指令以直接位址呼叫過**,不是抽樣結果,是窮舉。
- **`call_scan(0x31529)`**:`raw_candidates: 2`,`hits: [0x2545d, 0x25970]`,兩者
  `confirmed_call_instruction: true`——與 §9.11.3 的結果逐位址相同。
- **`xref_to(0x31529)`**:Ghidra 自身分析也給出同樣 2 筆(`0x25970`/`0x2545d`,皆
  `UNCONDITIONAL_CALL`)——這個未分析區域少見的「Ghidra `xref_to` 沒有失靈」案例,三種獨立
  訊號源(手算 disp32、`call_scan` 窮舉、Ghidra 原生 `xref_to`)完全吻合。
- **`xref_to(0x2bce5)`**:`refs: [], count: 0`。
- **`function_bounds(0x25970)`/`function_bounds(0x2545d)`**:兩者皆 `in_function: false`——
  與 §9.11 一致,這塊區域仍是 Ghidra base analysis 沒碰過的區域,不影響上述以 `E8` opcode
  直接掃描位元組得出的結論。

**結論(高信心,窮舉而非抽樣,第二輪獨立方法論複現)**:`0x2545d`/`0x25970` 這兩處呼叫端的
CALL 目標**只有** `0x31529` 一種可能,不存在「兩個呼叫都對、只是其中一個還沒被翻到」的空間——
`0x2bce5` 從未在任何位置被直接 `CALL` 過,舊記錄的「`0x25970 → 0x2bce5`」/「`0x2545d →
0x2bce5`」這條呼叫邊**從一開始就沒有 byte 證據支持**。

### 9.12.2 舊 claim 的完整傳播鏈:最初出處是 doc50 §3.9(2026-07-16),經 doc39/SESSION-HANDOFF/
91-worklist 輾轉引用,最終成為 doc58 續三十二~續六十四(10+ 輪)ch27 live 驗證任務的核心前提

全文搜尋 `docs/knowledge-base/` 找到的每一處字面引用:

| 文件 | 行號 | claim |
|---|---|---|
| `50-cutscene-script-system-design.md` §3.9 | L655 | 「回傳 -1 則走獨立 `ending_ch27_no_sky_key`,對應 `0x2545d call 0x2bce5` 壞結局」——**最初出處,2026-07-16**,早於本專案後期才建立的「每個位址 claim 都要有 disp32 byte 級證據」慣例 |
| `SESSION-HANDOFF-2026-07-06.md` | L221/L443/L452 | 「無鑰匙則 `0x2545d → 0x2bce5` 壞結局」/「`0x25970 call 0x2bce5` 之後的 `EB FE`...」/「`0x2545d → 0x2bce5` 在 `ch26_post` 內沒有後續 LOADCH」 |
| `39-ani-afm-format.md` §6 表格 | L253 | 「`0x02bce5` 的呼叫端為 `0x2545d`/`0x25970`,兩者分別落在戰後跳表 `0x51de9` 第 26/29 項」——§9.11.4 曾誤認這是「完全獨立方法論的強交叉驗證」,現在確認它其實繼承了同一個錯誤的呼叫目標數字(它對「`0x2545d`/`0x25970` 落在 table_post[26]/[29]」這部分是對的,只有「呼叫目標是 0x2bce5」這部分錯) |
| `91-worklist.md`(cluster master item) | L1179 | 「`0x25970 → 0x2bce5` 返回後是 self-loop」 |
| `91-worklist.md` | L1898 | 「最後 `0x25089→0x2bce5` 並 self-loop」(`0x25089` 是 `0x2545d` 前一條指令呼叫的 `reset_persistent_roster_state`,同一個錯誤的另一種標註方式) |
| `58-remake-live-verification-log.md` 續三十二 | ~L3660起 | 引用 doc50 §3.9,把這條 claim 定為「ch27 若無天空之鑰,戰後會短路直接呼叫終局渲染器 `0x2bce5`,不需要真的打到 ch29/30」的核心捷徑依據,此後續三十六、續四十六～續四十九、續五十六～續六十四(2026-08-19～2026-08-24,超過 10 輪)的 ch27 機甲隊長 live 驗證任務都以此為前提設計斷點(`0x2545d`/`0x2bce5` 附近) |

### 9.12.3 這個勘誤完整、事後解釋了 doc58 續三十六與續五十六~續六十四**全部**「`0x2bce5`
斷點從未命中」的負面結果——不是 live 驗證方法有問題,是斷點目標從一開始就不存在於呼叫路徑上

`doc58` 續三十六(2026-08-22)其實已經留下一個關鍵早期線索,但當時沒有深挖:對 `0x2545d`
套用已知 delta 換算出的 live 位址 dump 出來「不是一個乾淨的 CALL 指令邊界」,往前後搜尋到的
兩個真正 CALL 指令目標「都跟 `0x2bce5` 對不上」——續三十六當時誠實記成「這個特定目標位址的
翻譯沒有得到乾淨驗證」,未進一步排查根因。本輪確認:那正是因為 `0x2545d` 真正呼叫的是
`0x31529`,不是 `0x2bce5`,續三十六搜到的「兩個真正 CALL 指令」極可能就是本輪核對出的
`0x2545d: CALL 0x31529` 本身(或其附近),只是當時比對的目標數字(`0x2bce5`)本身就是錯的,
所以「對不上」是必然結果,不是搜尋範圍不夠或方法有誤。

同樣地,續五十六~續六十一(改走「ch27 無天空之鑰壞結局短路徑」試圖在 `0x2545d` 附近抓
`0x2bce5`)與續六十四(戰前幻象路徑,同樣在 `0x2545d`/`0x25970` 附近設 `0x2bce5` 斷點)的
「斷點全程沒有命中」負面結果,現在有了確定性的解釋:這些路徑最終走到的都是 `0x2545d`/
`0x25970` 這兩個 self-loop 終點,而它們的 CALL 目標本來就是 `0x31529`,`0x2bce5`
在這條呼叫路徑上**physically 不可能被執行到**——不是「live 驗證還沒抓到對的時機」,是
**斷點設在了一個從未被這條路徑呼叫過的位址上**。這解釋了為什麼連續 10+ 輪、跨越乾淨重開機、
不同存檔、不同進場路徑(戰後真實 montage / 戰前幻象)的 live 驗證,`0x2bce5` 斷點永遠是
0 命中——這是必然結果,不是運氣不好。

**重要邊界,避免誤讀**:這**不代表** doc58 續三十二~續六十四的 live 驗證工作是無意義的——
續六十二(2026-08-24)靠獨立的「全滅+End Turn」捷徑,真正打贏了 ch27 並深入觀察到完整結局
montage(CG 過場、詩句捲動、萊汀/悠妮角色回顧卡),這是本專案首次現場觀察到的真實內容,
價值不受本次勘誤影響。續六十二在那次真實 montage 期間對 `0x2bce5`/`0x2c548` 下的斷點**同樣
沒有命中**——這與本節結論完全吻合、不是新矛盾,但也意味著續六十二實際觀察到的角色卡內容,
很可能走的是另一條完全不同的呼叫鏈,值得下一輪查證是否與 §9.11.2 找到的「角色卡 renderer」
(`0x31c49`,經 `0x31529` 呼叫)、或戰後跳表 `table_post[30]`(ch30 真結局)有關——**本輪未
驗證這個猜想,只記錄為值得追查的線索,不宣稱已定案**。

### 9.12.4 已完成的訂正動作

1. `docs/data/known_address_errata.json` 新增一筆條目(`0x2545d call 0x2bce5 / 0x25970 call
   0x2bce5` → `0x2545d call 0x31529 / 0x25970 call 0x31529`),含完整傳播鏈與根因分析。
2. `docs/data/verified_addresses.json` 新增 `0x31529`/`0x2545d`/`0x25970` 三筆條目(先前這三個
   位址查 `query_verified_address.py` 完全沒有記錄,是本輪任務起點發現的資料庫缺口)。
3. `91-worklist.md` L1179/L1898 原地加註訂正(保留原文,附訂正說明與本節指標)。
4. `39-ani-afm-format.md` L253、`50-cutscene-script-system-design.md` L655、
   `SESSION-HANDOFF-2026-07-06.md` L221/L443/L452 原地加註訂正。
5. `58-remake-live-verification-log.md` 文末追加續六十五,說明續三十二~續六十四的前提訂正,
   不改寫原始記錄。

**誠實範圍**:本輪**沒有**解開 `0x2bce5` 真正如何被觸發(若真的會被觸發)的問題,`91-worklist.md`
以 `0x2bce5`/`0x2c548` 為核心的 11 個「party montage 資產解碼」項目(#862/863/1017-1020/1226/
1347-1354/1570-1608/1897-1898)維持原狀,不標記解封——那是完全不同的問題,本輪只處理了
「`0x2545d`/`0x25970` 呼叫目標是什麼」這一個窄範圍、但影響多份文件與一整條 live 驗證任務前提
的具體問題。

## 9.13 2026-08-25 續:核查 §9.11.8/§9.12 留下的 `0x524c6` indirect-call jump table 線索——
`0x2bce5` 不在表中,但很可能找到它為什麼「查無 CALL 目標」的根因:它是 9.2 已知子系統內部的
mid-function 分支位址,不是任何函式的進入點

> 任務動機:§9.12 排除了「`0x2545d`/`0x25970` 直接呼叫 `0x2bce5`」,但留下一個沒查證的
> 間接呼叫線索——`FUN_00031266`(在 `0x31529` 附近回溯時發現)內有
> `CALL dword ptr [EBP*4+0x524c6]`,而 `0x524c6` 這張表已在 §9.2 記錄過(唯二 caller 是
> `FUN_0002ff01`/`FUN_00031266`)。本輪目標:實際 dump 這張表、逐項核對是否有任何一項等於
> 或接近 `0x2bce5`/cluster,並完整反編譯 `FUN_00031266` 確認它的 index 是怎麼選出來的。

### 9.13.1 表格內容:與 §9.2 逐 byte完全一致,是同一張表——不是另一張獨立表

用 `ghidra_batch_probe.py`(`bytes` action)從 `0x524c6` 讀 40 bytes(10 個 dword):

```
0x524c6: 96 b9 02 00  → 0x0002b996   (idx0)
0x524ca: 33 bb 02 00  → 0x0002bb33   (idx1)
0x524ce: 6c bd 02 00  → 0x0002bd6c   (idx2)
0x524d2: d9 bf 02 00  → 0x0002bfd9   (idx3)
0x524d6: 17 c2 02 00  → 0x0002c217   (idx4)
0x524da: 41 c4 02 00  → 0x0002c441   (idx5)
0x524de: 7d c6 02 00  → 0x0002c67d   (idx6)
0x524e2: fc ca 02 00  → 0x0002cafc   (idx7)
0x524e6: f4 cc 02 00  → 0x0002ccf4   (idx8)
0x524ea: 1a ce 02 00  → 0x0002ce1a   (idx9)
```

10 項與 §9.2 表格記錄的 `0x2b996/0x2bb33/0x2bd6c/0x2bfd9/0x2c217/0x2c441/0x2c67d/0x2cafc/
0x2ccf4/0x2ce1a` **逐項完全相同**——`FUN_0002ff01` 用的 `[EAX*4+0x524c6]` 與 `FUN_00031266`
用的 `[EBP*4+0x524c6]` 是**同一張表、同一個 10 項 phase table**,不是兩張不同的表。再往下讀
`0x524ee` 起的 40 bytes(`00 00 01 00 01 00 00 28 00 00 00 46 00 00 00 78 ...`)是一串遞增但
非位址狀的小整數(`0x28`=40、`0x46`=70、`0x78`=120…),明顯不是位址表的延續——**表格就是
10 項,`EAX*4`/`EBP*4` 的索引範圍 0..9 沒有被低估**。

**每項逐一核對:沒有任何一項的字面值等於 `0x2bce5` 或 cluster 裡任何一個位址**
(`0x2bce5`/`0x2c172`/`0x2c405`/`0x2c439`/`0x2c469`/`0x2c548`/`0x2c5e3`/`0x2c773`)。步驟 2
的「表裡有沒有直接命中」問題答案是明確的**否**。

### 9.13.2 意外但更有價值的發現:8 個 cluster 位址**全部**落在這張表 10 個 handler 函式的
body 位址範圍內——很可能是「這條線索原本就查錯地方」的根因

用 `function_bounds`/`disasm` 逐一核對 8 個 cluster 位址落在哪個 handler 的位址區間裡(區間取
自 §9.2 表格已記錄的 body 範圍):

| cluster 位址 | 落在哪個 handler 區間 | 區間 |
|---|---|---|
| `0x2bce5` | idx1 `FUN_0002bb33` | `0x2bb33..0x2bd6c`(下一項起點前) |
| `0x2c172` | idx3 `FUN_0002bfd9` | `0x2bfd9..0x2c216` |
| `0x2c405` | idx4 `FUN_0002c217` | `0x2c217..0x2c440` |
| `0x2c439` | idx4 `FUN_0002c217` | `0x2c217..0x2c440` |
| `0x2c469` | idx5 `FUN_0002c441` | `0x2c441..0x2c67c` |
| `0x2c548` | idx5 `FUN_0002c441` | `0x2c441..0x2c67c` |
| `0x2c5e3` | idx5 `FUN_0002c441` | `0x2c441..0x2c67c` |
| `0x2c773` | idx6 `FUN_0002c67d` | `0x2c67d..0x2cafb` |

**8 個 cluster 位址無一例外全部落在 §9.2 已經完整反編譯、已經用 caller 分析排除是章節結局的
那 10 個 phase-table handler 函式的位址範圍內**——這批位址從來沒有離開過 9.2 描述的那個「戰鬥
指令選單 carousel」子系統的程式碼區段。

實際反組譯核對(`disasm` action,`function_bounds` 在這個 `-readOnly` project 目前對這批位址
回傳 `in_function: false`——§9.2 當時建立的 function 邊界屬於**該次** analyzeHeadless session
的暫存分析結果,`-readOnly` 不落盤,本輪重開一個新 session 後就看不到,這是已知、記錄在案的
限制,不影響下面純粹靠位元組反組譯得出的結論):

- **`0x2bce5`**(cluster 的核心錨點):從這個位址開始反組譯,**完全乾淨、無錯位**,連續
  19 條合理指令直到 `CALL 0x2eb9f`(`ADD ESP,0x14` 收尾)——`JGE 0x2bd27` → `MOV EAX,EBX` →
  `SHL EAX,2` → `CMP [EAX+0x53f92],0` → `JL 0x2bce1` → `CMP [EAX+0x53f92],0xf` →
  `JGE 0x2bce1` → 一段 `MOV EDX,[ESP+EAX+0x20]; IMUL EDX,EBP; ADD EDX,...; ADD EDX,0x50` 位址
  運算 → `PUSH -1; PUSH EBP; ADD EDX,[ESP+0x68]; PUSH EDX; PUSH [EAX+0x53f92];
  PUSH [ESP+0x6c]; CALL 0x2eb9f`。**`0x2eb9f` 正是 §9.2 記錄的「event 1/2/5/7/8 每幀 tick
  呼叫 `FUN_0002eb9f`/`FUN_00025a96`/`FUN_00025b45`(present/SFX cue)」三個函式之一**。兩個
  `JL`/`JGE` 都跳回 `0x2bce1`(比 `0x2bce5` 早 4 bytes)——即 `0x2bce5` 是一個**迴圈內部的
  分支目標**,不是函式進入點,`0x2bce5 - 0x2bb33 = 0x1b2`(434 bytes),落在 idx1 handler 到
  idx2 起點(`0x2bd6c`,gap 569 bytes,對照 §9.2 記錄的 idx1 大小「579」相符)的合理範圍內。
- **`0x2c172`**(cluster 成員之一):從這個位址冷啟動反組譯,前 3 條指令是明顯的**錯位垃圾**
  (`LES ECX,[ECX+ECX*4]`、`FADD ST0,ST1`、`LOOPNZ` 這種組合不構成合理程式邏輯),但從
  `0x2c179` 起自動重新對齊,出現與 `0x2bce5` **同一種模式**的乾淨程式碼:
  `INC dword ptr [EAX+0x53fb5]; CMP ...,0x3; JNZ; MOV EAX,[EAX+0x53fe5]; CMP byte ptr
  [ESP+EAX+0x30],0; JNZ; PUSH 1; PUSH 1; PUSH [0x54153]; CALL 0x25b45`——`0x25b45` 同樣是
  §9.2 列出的三個 tick-cue 函式之一。
- **`0x2c548`**(`91-worklist.md` 稱為 `native_2c548` 的核心錨點):同樣冷啟動反組譯前兩條是
  錯位垃圾,但從 `0x2c550` 起重新對齊,出現**幾乎一模一樣**的模式:
  `PUSH 1; PUSH 1; PUSH [0x54153]; CALL 0x25b45; ADD ESP,0xc; MOV EAX,[ESP+0x28];
  INC dword ptr [EAX*4+0x54050]; CMP dword ptr [EAX*4+0x54050],0x2; JNZ`。
- **`0x2c773`**:反組譯 48 bytes 全程沒有重新對齊成合理指令流(`MOVSB`、巨大立即值 `ADD`、
  中途 `LEAVE`、`CLC`、裸 `PUSH ES` 混雜)——這個位址本身很可能連「迴圈內部分支目標」都不是,
  單純是原始 cluster 清單轉錄時取到的一個錯位/非指令邊界位元組(不確定,未進一步深挖)。

**綜合判讀(中高信心,非窮舉但四點抽樣一致)**:`0x2bce5`/`0x2c172`/`0x2c548` 三個獨立核對點
共同的模式是——**它們都是 §9.2 已經完整記錄、已經用 caller 分析排除是章節結局的 10-entry
phase-table handler 函式內部,「每幀 tick 呼叫 present/SFX cue 函式」這個邏輯段落的分支目標
位址**,不是任何函式的進入點,也不出現在 `0x524c6` 表格的字面內容裡(該表只列 10 個函式的
**起點**,不會列迴圈內部位址)。這給出一個相當合理、可以解釋整條調查鏈「查無 CALL 目標」的
根因假說:**`0x2bce5` 從一開始就不是一個「應該被呼叫」的位址**——不管是直接 `CALL`(§9.12
窮舉排除)或透過 `0x524c6` 這張表間接呼叫(本輪排除,10 項字面值都不是它)——因為它本質上是
一段迴圈內部的條件分支目標,不是任何 calling convention 下的合法進入點。舊記錄把它當成「呼叫
目標」這件事本身,很可能源自對 decompiler 偽代碼位址或反組譯輸出的誤讀/誤標,與 §9.12 記錄的
`0x2545d call 0x2bce5` 誤植是**同一大類方法論問題的另一個案例**,但根因不完全相同(§9.12 是
「呼叫目標數字抄錯」,這裡更像是「把一個迴圈內部的分支位址誤認成一個可呼叫的函式/handler
位址」)。

**未能完全證實的部分(誠實列出)**:(a) 沒有在這個 `-readOnly` project 裡重建 `FUN_0002bb33`
等 10 個函式目前的正式 function 邊界,`0x2bce5` 屬於 idx1 handler 這件事是靠**位址算術+
反組譯出的程式碼模式高度吻合**推論出來的,不是 Ghidra `getFunctionContaining` 的直接確認;
(b) `0x2c773` 反組譯不出乾淨程式碼,不確定它在原始 cluster 清單裡是怎麼得出的,沒有進一步
排查;(c) 沒有反查「原始 cluster 清單(`0x2bce5`/`0x2c172`/`0x2c405`/`0x2c439`/`0x2c469`/
`0x2c548`/`0x2c5e3`/`0x2c773`)最初的出處/方法論」——這件事和 §9.12.2 對 `0x2545d call
0x2bce5` 做的傳播鏈追溯是同一類必要工作,但不在本輪範圍內完成。

### 9.13.3 `FUN_00031266` 完整反編譯:9-tick 轉場助手,index 不是自己選的,是呼叫端
(`FUN_0002ff01`)傳進來的同一個 phase-index 參數——不是獨立的 ending 路由器

```c
void __stdcall FUN_00031266(void)
{
  int iVar1;
  int in_stack_00000020;

  FUN_0003702f();
  for (iVar1 = 1; iVar1 < 5; iVar1 = iVar1 + 1) {
    FUN_00011eb0();
    (**(code **)(&DAT_000524c6 + in_stack_00000020 * 4))();
    FUN_0002eb9f();
    FUN_0002eb9f();
    (**(code **)(&DAT_000524c6 + in_stack_00000020 * 4))();
    FUN_00011eb0();
    FUN_00017aa9();
  }
  for (iVar1 = 4; -1 < iVar1; iVar1 = iVar1 + -1) {
    FUN_00011eb0();
    (**(code **)(&DAT_000524c6 + in_stack_00000020 * 4))();
    FUN_0002eb9f();
    FUN_0002eb9f();
    (**(code **)(&DAT_000524c6 + in_stack_00000020 * 4))();
    FUN_00011eb0();
    FUN_00017aa9();
  }
  return;
}
```

- **迴圈節奏**:`1..4`(4 次)正向 + `4..0`(5 次)反向,共 **9 次**——與 §9.2 既有描述
  「4-tick 正向+5-tick 反向(共 9 tick)」**完全吻合**,這次是從乾淨反編譯直接讀出來,不是
  推論。
- **`in_stack_00000020` 是呼叫端傳入的 stack 參數,函式本身完全沒有任何選擇/計算這個 index
  的邏輯**——4 個呼叫點(`0x312dd`/`0x3132f`/`0x313ea`/`0x3143c`)全部原封不動地重複使用同一個
  值,對照 §9.2 記錄的 `FUN_0002ff01` `param_2`(0..9,phase-table index 兼 UI 模式碼)語意,
  這個 `in_stack_00000020` 幾乎可以肯定就是同一個 `param_2` 沿呼叫鏈原樣傳下來的。
- **唯一 caller**:`call_scan(0x31266)` 窮舉全 exe(`.object1`/`.object2`/`.object3`/`.image`
  四個區段)只找到 **1 筆**直接 CALL——`0x3089d`,`in_function: FUN_0002ff01`。與 §9.2 記錄的
  「角色與角色之間(除最後一位)呼叫 `FUN_00031266`」完全對得上,`FUN_00031266` 不是一個
  有獨立入口/獨立選擇邏輯的「過場助手」,它是 `FUN_0002ff01` 主迴圈內部的一個私有轉場
  子程式,兩者共用同一個 phase-index、共用同一個 `0x524c6` 表格。

**結論(高信心)**:`FUN_00031266` 的 index 選擇邏輯**不是**章節號、不是場景類型碼、也不是
獨立的 UI 模式碼——它就是 `FUN_0002ff01`(戰鬥指令選單 carousel 主引擎)自己的 `param_2`
原樣傳遞。這排除了「`FUN_00031266` 是一個獨立的、可能通往結局演出的路由器」這個假說本身:
它從結構上就是 §9.2 那個已經證實只被 `0x1cff0`/`0x15311`(戰鬥指令 dispatch)呼叫的子系統
的內部零件,不具備獨立通往其他呼叫鏈(包括 ch27/ch29 結局)的能力。

### 9.13.4 對本 cluster worklist 的影響:未解封,但線索本身已查盡

`91-worklist.md` 的 11 個「party montage 資產解碼」項目(#862/863/1017-1020/1226/1347-1354/
1570-1608/1897-1898)**維持原狀不動**——`0x2bce5` 沒有出現在 `0x524c6` 表格裡,`FUN_00031266`
也被排除為獨立路由器,§9.11.8/§9.12 留下的這條間接呼叫線索**已查盡、查空**,不構成解封。

**給下一輪的具體建議**:
1. §9.13.2 的「`0x2bce5`/`0x2c172`/`0x2c548` 全部是 §9.2 子系統內部迴圈分支位址,不是可呼叫
   進入點」這個假說,值得優先反查原始 cluster 清單(`native_2c548.json`/`91-worklist.md`
   相關行)的最初出處與方法論——如果能確認這批位址當初就是從反組譯/decompile §9.2 這個子系統
   時記錄下來的(方法論層面的張冠李戴,而非位址轉錄手誤),就能像 §9.12 處理
   `0x2545d call 0x2bce5` 一樣,登記一筆更大範圍的 `known_address_errata.json` 條目,徹底
   結束這條長達多輪的死路,而不是每輪重新排除一次。
2. 本輪**沒有**執行「全域掃描其他 `CALL dword ptr [reg*4+imm32]` 間接呼叫跳表模式」——
   `ghidra_batch_probe.py`/`ProbeBatch.java` 目前只支援 `call_scan`(對單一已知目標位址窮舉
   找呼叫端),不支援「反查所有間接呼叫指令模式」這種全域 opcode 掃描,要做這件事需要新寫一支
   `GhidraScript`(掃 `FF 14 85 xx xx xx xx` / `FF 24 85 xx xx xx xx` 這類 `CALL/JMP
   dword ptr [reg*4+imm32]` opcode 編碼)。鑑於本輪已經對 `0x524c6` 這張最有希望的表給出
   明確查空結果,且 §9.13.2 提供了一個合理的根因假說,建議下一輪先做建議 1(反查 cluster
   清單出處),比直接開新工具做全域間接呼叫掃描的投資報酬率更高;若建議 1 也查不出結果,
   再考慮全域間接呼叫掃描。

## 9.14 2026-08-25 續:對照 §9.2/§9.13 的 phase-table carousel 系統與 11 個 worklist 項目逐項核對——
高信心確認「位址重疊是巧合、兩者是不同子系統」,但不撤回 party montage 本身的既有記錄

> 任務動機:§9.13 已高信心判定 8 個 cluster 位址落在 §9.2 那 10 個 handler 函式的 body
> 範圍內,但留下三個明確缺口:(a) `function_bounds` 在目前 `-readOnly` project 對這 10
> 個 handler 全部回傳 `in_function:false`,§9.13 用的「落在哪個 handler」是位址算術+
> 反組譯模式比對推論出來的,不是 Ghidra `getFunctionContaining` 直接確認;(b) 8 個 cluster
> 位址裡只驗證了 4 個(`0x2bce5`/`0x2c172`/`0x2c548`/`0x2c773`),另外 4 個
> (`0x2c405`/`0x2c439`/`0x2c469`/`0x2c5e3`)沒查;(c) 沒有把 §9.2 這個系統的**實際內容**
> 拿去跟 `91-worklist.md` 11 個項目**逐項**列出的具體訴求(FDOTHER#56、FIGANI/DATO 頭像、
> dialogue-frame grid、mirror/non-mirror 淡出、input-skip、2000ms/4ms 計時、FDOTHER#0x36/54、
> 320×200 buffer)直接比對,只有籠統的「戰鬥選單,不是結局」結論。本節補齊這三點。

### 9.14.1 補齊缺口 (a):`function_bounds` 直接重測 10 個 handler + 8 個 cluster 位址,結果與
§9.13 的推論一致——`-readOnly` 分析確實沒有持久化,但這不影響位元組層級的結論

用 `python tools/ghidra_batch_probe.py` 對 §9.2 表格的全部 10 個 handler 入口
(`0x2b996/0x2bb33/0x2bd6c/0x2bfd9/0x2c217/0x2c441/0x2c67d/0x2cafc/0x2ccf4/0x2ce1a`)與 8 個
cluster 位址各下一次 `function_bounds`(18 筆查詢,`.wsl_build/montage_task_queries.json`→
`montage_task_results.json`,6.4s 完成,18/18 `ok`),結果**全部** `in_function:false`——
包括 §9.2 當初已經完整反編譯過的 10 個 handler 本身。這與 §9.13.2 的觀察完全吻合:那次
`analyzeHeadless` 是加了 `-readOnly` 跑的,session 內用 `disassemble()`/`getFunctionContaining()`
建立的函式邊界不會寫回 `.gpr` project 檔,新開一個 headless session(不論是 §9.13 的還是本節
這次)都看不到,只有原本就在 base 976-function 分析裡的函式(如 `0x14818`/`0x2ff01`,見
doc98 記錄的驗證案例)才會持久存在。**這是這個 project 已知、記錄在案的限制,不是新問題**——
代表任何一輪要重新確認 §9.2 的 10 個 handler 邊界,都必須靠位元組層級方法(逐 byte 反組譯、
byte-pattern 掃描)重新推導,不能依賴 `function_bounds` 直接查到持久化結果。

### 9.14.2 補齊缺口 (b):剩餘 4 個 cluster 位址(`0x2c405`/`0x2c439`/`0x2c469`/`0x2c5e3`)逐一
反組譯,結果與 §9.13.2 已驗證的 4 個位址**同一種模式**,進一步強化(而非推翻)§9.13 的結論

- **`0x2c439`**:冷啟動反組譯直接給出一段**完全乾淨、無需重新對齊**的函式尾聲——
  `ADD ESP,0x2c; POP EBP; POP EDI; POP ESI; POP EBX; RET`(`start=0x2c439, end=0x2c440,
  stop_reason=ret`)。`0x2c440` **正是** §9.2 表格記錄的 idx4 handler(`FUN_0002c217`)body
  終點(`0x2c217..0x2c440`)——這是本節目前為止**最強的一筆直接證據**:不需要位址算術或模式
  比對,`0x2c439` 反組譯出的乾淨 `RET` 邊界字面上就落在 §9.2 早先記錄的函式終點前 7 bytes,
  逐位元組確認 idx4 handler 的邊界記錄準確。
- **`0x2c469`**:冷啟動第一條指令是 `LOOPNZ 0x2c46d`(不合理的函式開頭),但接下來立刻是
  一段乾淨、語意明確的邏輯:`SHL EDX,0x4; MOV EAX,[0x53a45]; MOVZX EAX,byte ptr
  [EDX+EAX*1+6]; TEST EAX,EAX; JNZ 0x2c49a; ...`——`[0x53a45]+slot×0x50+6` **正是** §9.2
  記錄的 mirror 判斷 `*(char*)(DAT_00053a45+6+param_1*0x50)==0`(unit_side_offset:6)。位址
  `0x2c469` 落在 idx5 handler(`0x2c441..0x2c67c`)範圍內,内容也确实是同一 handler 描述过的
  mirror-check 邏輯——與 §9.13.2 對 `0x2bce5`/`0x2c172`/`0x2c548` 的觀察(冷啟動略有錯位,
  但幾 byte 內重新對齊成 §9.2 已知邏輯段落)**同一種模式**。
- **`0x2c405`**:冷啟動前 7 bytes 是明顯垃圾(`INC EAX; ADD EAX,0; ADD AL,CH; SHL byte ptr
  [EDI],CL; ADD AL,[EAX]`),但從 `0x2c411` 起重新對齊成一段合理的「除以 2 並正確處理正負號」
  慣用法:`MOV EDX,EAX; MOV EBX,2; SAR EDX,0x1f; IDIV EBX; MOV EAX,EDX`——同樣落在 idx4
  handler(`0x2c217..0x2c440`)範圍內,語意上與 §9.2 記錄的「per-slot tween/palette-delta
  4 元素 rotation」需要的整數除法運算相容(未逐位元組證實是同一段,但模式一致)。
- **`0x2c5e3`**:冷啟動 `disasm` 回傳 `count:0, stop_reason:end_of_code`——**Ghidra 這次連
  一條指令都沒能在這個位址解出**(`getInstructionAt`/`disassemble()` 均未產生可讀結果,原始
  bytes `80 40 05 00 ff 44 24 28 ...` 手動解碼其實是合法的 `ADD byte ptr [EAX+5],0` 開頭,不
  確定是 Ghidra 內部因同一 batch session 先前查詢造成的暫態狀態衝突,還是這個位址本身有更深的
  問題)。這一筆**沒有**得到正面確認,誠實列為未解——但即使排除這一筆,其餘 3+4=7 個 cluster
  位址(§9.13 驗證 4 個+本節驗證 3 個)全部與「§9.2 handler 內部分支/邏輯片段」一致,`0x2c5e3`
  單獨一筆的不確定不足以動搖整體判讀。

**小結**:8 個 cluster 位址中,7 個(§9.13 的 4 個+本節新驗證的 3 個)都得到「冷啟動可能需要
1 到 7 bytes 重新對齊,但對齊後的程式碼與 §9.2 已記錄的 handler 內部邏輯段落(present/SFX cue
呼叫、mirror 判斷、tween 除法)一致,且位址算術上落在對應 handler 的 body 範圍內」這個結果;
`0x2c773`(§9.13 記錄)與 `0x2c5e3`(本節記錄)兩筆反組譯不出乾淨結果,誠實列為未決,但不影響
其餘 6 筆的一致結論。

### 9.14.3 補齊缺口 (c):把 §9.2 系統的實際內容,對 `91-worklist.md` 11 個項目逐項列出的具體
訴求逐一核對——結論是**主題不符**,§9.2 系統本質上答不出這些訴求裡的任何一項

`91-worklist.md` 對這個 cluster 的具體訴求(讀原文逐項摘出,而非用本節自己的轉述):

| worklist 具體訴求 | 出處 | §9.2 系統是否具備 | 判定 |
|---|---|---|---|
| FDOTHER `#0x36`(十進位54)、320×200 雙 buffer、palette 0→63/4ms、2000ms hold | L1226 | §9.2 開場載入的是 **FDOTHER.DAT 兩次**(具體 index 未反編譯出字面數字,只知道是逐角色資源,不是 index 54/56 固定資源);沒有 320×200 雙 buffer 記錄(§9.2 用的是**戰鬥畫面現有 VGA/work buffer**,不建立獨立的 ending 專用 buffer);沒有 4ms/2000ms 這組計時常數,§9.2 唯一的計時是 `0x17aa9` tick-wait 與 9-tick(4正+5反)轉場,節奏對不上 | **不符** |
| FDOTHER#56 backdrop、TAI#3、FIGANI/DATO party montage(`native_2c548.json`) | L1017-1020/1347-1354/1593 | §9.2 確實載入 **TAI.DAT**(唯一 1 次)+**FIGANI.DAT**(2 次)+**FDOTHER.DAT**(2 次),資源組合表面相似;但 §9.2 完全**沒有 DATO.DAT** 載入(worklist 的 party montage 明確依賴 DATO 頭像,`DATO=unit+7`),也沒有找到任何字面 `#56`/`#0x38` index 常數——§9.2 的 FDOTHER 用途是逐角色資源,不是固定的 backdrop 資源號 | **不符**(資源*類別*重疊,但缺 DATO,無固定 index) |
| dialogue-frame grid(`0x168b6`,49 次呼叫、`FDOTHER.DAT#5`) | L1595/1597-1600 | §9.2 完全沒有出現任何「49 次呼叫同一 layout 函式」或 `FDOTHER#5` 的痕跡;§9.2 的顯示對象是角色 sprite(FIGANI)本身,不是文字/對話框網格 | **不符** |
| mirror / non-mirror figure fade(`0x29164`,`unit+6` branch、9-present、DAC delta=esi×6/48→0/2或8ms、stage×10) | L1606-1610 | §9.2 **確實有**同構的邏輯:同一個 `unit+6==0` mirror 判斷(即本節 9.14.2 在 `0x2c469` 找到的那段)、`FUN_00031266` 的 9-tick(4正+5反)轉场與 doc91 描述的 9-present 節奏數字上吻合;但 §9.2 的 palette 是「4 元素 rotation」+`0x2eb9f`/`0x25a96`/`0x25b45` present/SFX cue,不是 worklist 描述的 `esi×6` DAC delta 或 `stage×10` 平移;**這是 8 個訴求裡唯一有結構性重疊的一項**,但重疊的解釋更可能是「兩個系統共用同一份 unit-record 佈局慣例(`[0x53a45]+slot×0x50+6`=mirror flag),各自獨立實作各自的 mirror 分支」,不是同一段程式碼 | **表層邏輯慣例重疊,但參數/計時/呼叫鏈不符** |
| input-skip handling | 通篇多處 | §9.2 完整反編譯裡**沒有任何**輸入輪詢/按鍵檢查——`FUN_0002ff01`/`FUN_00031266` 全程是純計時驅動的迴圈,不讀鍵盤/搖桿狀態 | **不符** |
| chapter26/29 分支文字、fade-out | L1226/1356 | §9.2 沒有任何 FDTXT 呼叫、沒有文字渲染,也沒有章節條件分支(`param_2` 是呼叫端傳入的 phase/UI 模式碼,不是章節號) | **不符** |

**7 項具體訴求裡,6 項在 §9.2 的完整反編譯內容裡找不到對應,1 項(mirror flag 慣例)只是共用
底層 unit-record 佈局,不是同一段程式碼**。加上 §9.2 自己的關鍵反證(9.3 已記錄):`FUN_0002ff01`
的唯二呼叫者是戰鬥指令 dispatch(`0x1cff0`/`0x15311`),窮舉搜尋找不到任何從 ch29/ch30 handler
或 `0x1088d`(loadch)範圍呼叫 `0x2ff01` 的路徑——**§9.2 這個系統在資源類別(TAI/FIGANI/FDOTHER)
表面相似之外,無論從呼叫鏈、參數語意、計時常數還是渲染對象(角色 sprite carousel vs. 文字+頭像
+backdrop montage)來看,都是一個服務戰鬥指令選單的獨立系統,不是章節結局 party montage 的
同一份程式碼**。

### 9.14.4 綜合判讀:高信心確認「位址重疊是巧合」,但明確**不撤回** `91-worklist.md` 既有的
party montage 記錄本身——兩者證據來源不同,矛盾指向的是「位址對應關係」而非「內容真偽」

必須誠實面對一個表面矛盾:`91-worklist.md` L1592-1610 對 `0x2c548`/`0x29164`/`0x2b9a1`/
`0x168b6`/`0x2c773` 的記錄極其具體(FIGANI/DATO 解碼器、49 次 dialogue-frame grid 呼叫、
`unit+6` mirror 分支的兩條路徑差異、`0x292ad`/`0x2927e..0x29357` 這種精確到個位 byte 的
分支位址),且明確標注是「官方 IDA(9.4)」「Docker Capstone」交叉確認、並與玩家提供的真實
`FDOTHER.DAT`/`DATO.DAT` 檔案做過逐 byte/逐 pixel regression——這**不是**可以用「舊記錄多半
是猜測」一句話帶過的低品質證據。但本節(與 §9.1/§9.6/§9.7/§9.9/§9.12/§9.13 五輪獨立方法論)
在 `FD2Analysis3` 這個目前使用的 Ghidra project 裡,對**字面上同一批 hex 位址**做窮舉/逐 byte
反組譯/decompile,得到的是一個內容、語意都完全不同的戰鬥選單子系統。兩邊都是紮實方法論做出來的
結果,不能簡單判定其中一邊「錯」。

最合理的解釋(§9.1 三個假說裡的其中一個,本節認為現在證據權重最高的一個):**`91-worklist.md`
L1592-1610 那批記錄所依據的「official IDA 9.4」/Docker Capstone session,分析的很可能不是
`FD2Analysis3` 現在載入的這一份 EXE build,或者是把 DOSBox-X live 記憶體位址誤記成靜態檔案
linear 位址**——這與這個專案自己的既有記憶(`feedback_fd2_old_new_exe_address_instability`:
「舊/新版位址不能直接套用同一常數位移」)、以及 §9.5.4 這一輪才確認的「這份 EXE 沒有可用的
file-offset↔linear 位址全域換算常數」完全一致:如果 L1592-1610 的位址記錄來自另一份 EXE build
或另一種位址空間,那麼「字面數字相同」本來就不代表「指向同一段位元組」,本節與 §9.2/§9.13 在
`FD2Analysis3` 裡找到一個完全不同、但表面資源組合相似的系統就不是巧合中的巧合,而是**同一組
「TAI/FIGANI/FDOTHER 讀取+9-tick 轉場+unit+6 mirror flag」引擎設計慣例,在兩個不同 build/
位址空間裡各自出現一次**的自然結果——原始 party montage 系統(FIGANI/DATO/dialogue-grid/
mirror-fade)很可能**依然真實存在**於遊戲裡,只是它在 `FD2Analysis3` 目前這份 EXE 裡的真正
linear 位址,還沒有被重新獨立核對出來。

**因此本節的結論分兩層,不可合併成一句話**:

1. **高信心(五輪以上獨立方法論一致)**:`0x2bce5`/`0x2c172`/`0x2c405`/`0x2c439`/`0x2c469`/
   `0x2c548`/`0x2c773`(以及大概率 `0x2c5e3`)這批**字面 hex 位址**,在 `FD2Analysis3` 這個
   Ghidra project 目前載入的 EXE 裡,對應的是 §9.2 記錄的戰鬥指令選單 party carousel 系統的
   內部分支/邏輯片段,**不是**章節結局 party montage 的程式碼。以這批字面位址為前提的「§9.2
   系統=結局 renderer」假說**明確排除**。
2. **中信心、不撤回**:`91-worklist.md` L1017-1020/1226/1347-1356/1570-1610/1897-1898 描述的
   party montage 系統本身(FDOTHER backdrop、FIGANI/DATO 頭像、dialogue-frame grid、
   mirror/non-mirror figure fade)的**內容**,證據來源獨立於本節(官方 IDA + 已移除的 Docker
   Capstone + 玩家真實檔案 regression),**不因本節的負面結果而被推翻**——本節排除的是「§9.2
   這個特定的 Ghidra 位址範圍是否就是它」,不是「它是否存在」。

### 9.14.5 對 11 個 worklist 項目的逐項最終判定

依任務要求逐一給出 full/partial/unrelated:

| # | worklist 項目 | 判定 | 理由 |
|---|---|---|---|
| 1 | L862(cluster master #1) | **unrelated**(對 §9.2 假說) | §9.14.3/9.14.4:§9.2 系統與訴求內容不符,blocker 本身未解除 |
| 2 | L863 | **unrelated** | 同上,同一 blocker 的另一種標註 |
| 3 | L864 | **unrelated** | 同上 |
| 4 | L865 | **unrelated** | 同上 |
| 5 | L866 | **unrelated** | 同上 |
| 6 | L867(terminal handler,cluster master) | **unrelated** | 同上;terminal handler 仍因未解的 ending renderer fail-closed |
| 7 | L899/L1226(chapter ending renderer 結構:FDOTHER#0x36、320×200 buffer、0→63/4ms、2000ms) | **unrelated** | §9.14.3 表格第 1 列:資源 index、buffer 佈局、計時常數全部對不上 §9.2 |
| 8 | L1017-1020/L1347-1354(FDOTHER#56/TAI#3/FIGANI/DATO montage) | **unrelated** | §9.14.3 表格第 2 列:資源*類別*重疊但缺 DATO、缺固定 index,呼叫鏈也不同 |
| 9 | L1570-1608(`0x2bce5` 可播放前綴、party cycle、dialogue-frame grid、mirror/non-mirror fade) | **partial**(僅底層慣例) | §9.14.3 表格第 4/5 列:dialogue-frame grid 完全不符;mirror flag 判斷式**慣例相同**(`[0x53a45]+slot×0x50+6`)但參數/計時/呼叫鏈不同,不是同一段程式碼——實務上仍應視為未解 |
| 10 | L1572(下一個 ending gate:FDOTHER#56 backdrop、FIGANI/DATO、dialogue-frame grid、mirror/non-mirror fade、input-skip) | **unrelated** | §9.14.3 表格全六列逐一核對,§9.2 缺 DATO、缺 dialogue grid、缺 input-skip;terminal route 仍不可接 |
| 11 | L1897-1898(command-23 raw writer 與 `0x2bce5` renderer 的呼叫關係) | **unrelated** | §9.12 已排除 `0x25089→0x2bce5` 的直接呼叫;§9.2/9.13/9.14 進一步確認 `0x2bce5` 本身是不相關子系統的內部分支,command-23 raw writer 與它從未有過真實呼叫關係 |

**總體信心**:對「§9.2 這個已完整反編譯的戰鬥選單系統=章節結局 party montage」這個具體假說,
**高信心排除**(五輪以上獨立方法論、含本輪新增的 3 個 cluster 位址驗證與 7 項具體訴求逐一核對,
結論一致無反例)。但對「這 11 個 worklist 項目描述的 party montage 系統本身是否存在/是否已被
正確記錄」這個更大的問題,**維持原有的中高信心**(來源是官方 IDA + 玩家檔案 regression,不受
本輪影響)——本輪**不構成任何一項的解封**,也**不構成對既有 party montage 記錄的撤回**,兩者
是完全不同的問題,不應混為一談。`91-worklist.md` 11 個項目狀態維持 `[~]`,僅在 master item 補註
指向本節。

**給下一輪的具體建議**:
1. 停止在 `FD2Analysis3` 裡用字面位址算術重試 `0x2bce5`/`0x2c548` 這批數字——本輪與前五輪
   一致證實這條路已經走到底,§9.14.4 給出的「不同 EXE build/位址空間」假說才是下一步該查的
   方向。
2. 具體做法:找出 L1592-1610 那批記錄實際使用的 IDA session/EXE 檔案(如果還留有 `.idb`/
   `.i64` 或當時的 session 記錄),用 `Memory.findBytes` 對 FIGANI/DATO 相關的已知字串或
   byte pattern(如 `"DATO"`、`0x168b6` 附近的 49 次呼叫特徵)在 `FD2Analysis3` 裡重新定位,
   而不是直接信任字面 hex 數字——這與 §9.5.4 排除「file offset vs linear address」假說時
   使用的方法完全同構,应可直接複用。
3. 若步驟 2 找到新位址,才有資格重新評分 L1017-1020/1226/1570-1608 等項目;在那之前,維持
   `[~]` fail-closed 是唯一誠實的狀態。

## 9.15 2026-08-25 續:換方法論——用 dosbox-x 內建 `LOGC` 指令追蹤捕捉真正的 montage 執行流程,
ground-truth 交叉驗證 `0x31529`/`0x320a1` 假說(高信心確認),並找出 13 個全新、Ghidra 從未
建過 function boundary 的候選區塊(未完全查證,誠實列為線索)

> 任務動機:§9.1-§9.14 累積 15+ 輪都是「猜候選位址→驗證」模式,在 Ghidra base 分析完全沒碰過
> 的區域(§9.10-§9.11 發現的 `0x31529`/`0x320a1` 一帶)structurally 找不到下一步線索。本輪
> 改用一個新工具(`tools/dosbox_exec_trace.sh`+`tools/dosbox_exec_trace_analyze.py`,見
> doc98/doc48 §10):不猜候選,直接記錄 CPU 在 montage 播放期間實際執行過的**每一個位址**,
> 再拿這份 ground-truth 清單去跟 Ghidra 比對。完整環境操作記錄見
> `docs/knowledge-base/58-remake-live-verification-log.md` 續六十六,本節只記錄反組譯/交叉
> 比對的技術細節。

### 9.15.1 方法論:dosbox-x heavy-debug build 內建 `LOGC <hex count>` 指令追蹤,武裝後遊戲
持續正常運作,可邊記錄邊操作

WebSearch+讀這個專案 WSL2-native 建置的 `debug.cpp` 原始碼確認:dosbox-x 的 heavy-debug
build 內建 `LOG`/`LOGS`/`LOGL`/`LOGC`/`ADDLOG`/`HEAVYLOG` 系列 debugger console 指令。
`LOGC <hex count>` 只印 `CS:EIP`(每行 `setw(4) cs << ":" << setw(8) eip`),對純位址獵尋
是最輕量的變體。已用真實操作驗證(續六十六 §2):武裝 `LOGC` 之後遊戲畫面持續渲染、持續接受
`xdotool` 鍵盤輸入,不是阻塞操作;吞吐量約每秒數百萬到近千萬指令,與 `cycles=5000` 這個模擬
節流設定無關(兩者是完全獨立的東西,不要混淆)。600,000,000 instructions 的一次追蹤(涵蓋
ch27 戰前「轉送站」幻象的戰前對白→CG1→CG2→詩句→萊汀角色卡)產生 7.9GB `LOGCPU.TXT`,`awk`
單趟去重後只剩 12,297 筆唯一 `CS:EIP`(主程式碼段 `CS=0170` 佔 8,727 筆)。

### 9.15.2 ground-truth 交叉比對結果:8,727 筆位址裡 1,579 筆(18%)落在 Ghidra base 分析
完全沒建過 function boundary 的區域,合併成 19 個連續區塊

`tools/dosbox_exec_trace_analyze.py` 對 8,727 筆位址批次查 `function_bounds`(6.6 秒完成):
7,148 筆 `in_function=true`(在既有 976-function 清單內),1,579 筆 `in_function=false`,
依相鄰位址(gap≤0x40 bytes)合併成 19 個區塊。

### 9.15.3 高信心正面結果:6 個區塊精確命中 §9.11 用純靜態方法定位的 `0x31529`/`0x31c49`/
`0x320a1` 角色卡 renderer 鏈——兩種完全獨立的方法論(窮舉 live 執行 vs 手動 instruction-
boundary 回溯)、兩條不同的觸發路徑(戰前幻象 vs 戰後真實 montage)得出同一組位址

19 個區塊裡,`0x31529..0x319D3`(331 個位址命中)與 `0x31BDF..0x321ED`(437 個位址命中)這
兩個區塊,逐一核對後**與 §9.11 用手動 instruction-boundary 回溯定位出的角色卡 renderer 鏈
(`0x31529`→`0x319d3`→`0x31c49`→`0x320a1`,§9.11.4 的完整呼叫鏈圖)完全落在同一個範圍內**:
`0x31529..0x319D3` 正是 §9.11.3 記錄的「G:換場淡出+依 `[0x53c03]==26` 分支挑裝飾圖示 id」
這段 orchestrator 本身的位址範圍;`0x31BDF..0x321ED` 則涵蓋了 `0x31c49`(角色卡 renderer
本體)一路到 `0x320a1`(續六十四 live 斷點捕捉到的 5 次連續 `CALL 0x15f84` TXT 呼叫序列,
`0x320a1..0x32139`)的整段。

**這個結果的方法論意義,值得特別強調**:§9.11 定位這條鏈用的是**純靜態方法**(手動反組譯、
逐層回溯上一個函式的 `RET`,§9.11.1 開頭已註明);續六十六本輪走的是**戰前「轉送站」幻象**
這條路徑(camp exit 確認 YES 之後、抵達戰場之前的劇情演出,續六十四首次發現),不是續六十二
用 47 格死亡 signature+End Turn 確認觸發的**戰後真實 montage**路徑;追蹤方法本身是**窮舉
live 執行**(逐指令記錄,不依賴任何人工挑選的斷點取樣)。三個維度(定位方法、觸發路徑、
驗證手段)全部獨立,結果卻精確落在同一組位址上——這是目前為止對「`0x31529`/`0x31c49`/
`0x320a1` 是角色卡 renderer」這個假說信心等級最高的一次交叉驗證,也是這個專案第一次真正做到
「不靠猜測、靠窮舉執行證據」去驗證一個候選位址範圍。

**副產品:回答了 §9.12(續六十五訂正)留下的一個開放猜想**。§9.12 訂正 `0x2545d call
0x2bce5` 是誤植、真正呼叫目標是 `0x31529` 之後,曾留下一句「續六十二實際看到的角色卡內容很
可能走的是 `0x31c49`/`0x31529` 這條鏈——這只是留給下一輪查證的線索,本則訂正未驗證這個猜想,
不宣稱已定案」。本輪雖然走的是戰前路徑而非續六十二的戰後路徑,但**兩條路徑呈現逐字相同的
角色卡文字內容**(續六十四 §2 已核對過),加上本輪的 ground-truth 執行證據確認戰前路徑確實
經過 `0x31529`/`0x31c49` 這條鏈,合理推斷(非 100% 直接證據,因為沒有對戰後路徑本身重跑一次
`LOGC`)兩條路徑共用同一個底層 renderer——這個猜想現在有了獨立方法論的正面支持,信心等級從
「留待查證的線索」提升到「中高信心、有交叉證據支持」。

### 9.15.4 全新候選:13 個區塊,Ghidra 從未建過 function boundary、文件裡也從未出現過,
逐一反組譯定性(未完全查證,誠實列為線索而非定論)

其餘 13 個區塊落在 `0x36000`-`0x4A000` 這個此前 doc35 §9 系列從未涉足過的位址範圍(舊有
9 輪調查全部集中在 `0x25000`-`0x33000`)。逐一用 `disasm`/`function_bounds`/`xref_to`/
`call_scan` 核對(方法與過去一致,`ghidra_batch_probe.py` 批次查詢),按大小排序:

| 區塊(native) | span | 命中數 | 反組譯內容定性 |
|---|---|---|---|
| `0x4364C..0x438D5` | 0x289(649B) | 148 | 巢狀迴圈+多次 `CALL 0x42980`(見下),含 `CMP EAX,0xb0/0xd0/0xe0` 這種 nibble/byte-range 分類跳轉——**格式判別/解碼分派邏輯的典型樣式** |
| `0x43270..0x43490` | 0x220(544B) | 133 | 主迴圈:`CMP ESI,0x64`(100)取模、`CMP ECX,0x20`(32)迴圈上界、反覆 `CALL 0x42980`,語意上像逐格/逐 tick 處理迴圈 |
| `0x404C0..0x40683` | 0x1C3(451B) | 114 | 一次性初始化樣式(`CMP [flag],0` 判斷是否已執行過,`CALL 0x382d6`/`0x382db`/`0x382e9` 三個地址相近的 helper) |
| `0x3EA8E..0x3EBB3` | 0x125(293B) | 86 | **確認是硬體中斷服務常式(ISR)**:`PUSHAD`+段暫存器存檔+`MOV SS,AX; MOV ESP,...`(stack-switch prologue,標準保護模式 ISR 樣式)、`OUT 0x20,AL`(AL=0x20,經典 8259 PIC EOI 指令)。**不是渲染代碼,是計時/tick 驅動的中斷處理常式**,但過去任何一輪都沒發現過這個常式的存在,值得記錄以免將來重複探索。 |
| `0x434D1..0x435AD` | 0xDC(220B) | 54 | `MOVZX EDI,[EAX+1]; MOVZX ESI,[EAX]; SHL EDI,8; SHL ESI,0x10; ...ADD` ——經典的「讀 3-byte RGB triple、組成 24-bit 值」pattern,**強烈疑似 palette/色彩處理**,是本輪除已知鏈外最值得追的一個候選 |
| `0x36F24..0x36FD2` | 0xAE(174B) | 82 | `LODSB; AND AH,0xC0; CMP AH,0xC0; JNZ` 讀 control byte 分支,取低 6 bits 當 run-length,`SHR ECX,1; REP STOSW; RCL ECX,1; REP STOSB`——**RLE/游程解壓縮迴圈**,與 doc35 §9(續六十二 §4)已知的另一個 RLE 原語(live `0x1EAC6A`,native `0x4EC6A`)結構不同(那個是 literal-vs-run 的 getbyte 原語,這個是「填值展開」型 RLE),可能是另一張不同資源格式的解碼器 |
| `0x4391F..0x43995` | 0x76(118B) | 29 | `0x43270` 那個大函式的收尾/迴圈控制片段(`JNZ` 跳回 `0x432ba`),與其同屬一個函式,`RET` 收尾乾淨 |
| `0x49430..0x49456` | 0x26(38B) | 11 | `EBP=[EDX+EAX*4]; [EDI]+=EBP; EDI+=4` 累加迴圈,疑似樣本/係數累加(見下方 0x4809b 一起討論) |
| `0x4809B..0x480B9` | 0x1E(30B) | 12 | `[ESI]→EAX; ADD ESI,4; CMP EAX,0x7fff/0xffff8000 做飽和 clamp; XOR EAX,0x8000; 取 AH 寫出` ——16-bit 帶正負號值轉無號、含溢位保護,**疑似 PCM 音訊混音累加/量化**,不是圖像代碼 |
| `0x47D88..0x47D98` | 0x10(16B) | 8 | 與 `0x4809b` 幾乎同構但沒有 clamp(直接 `XOR EAX,0x8000` 轉無號)——同一族的無 clamp 版本,同樣疑似音訊處理 |
| `0x36E57..0x36E64` | 0xD(13B) | 4 | `MOV ECX,0xC0; REP MOVSD; RET`——單純 memcpy 0xC0×4=768 bytes,**768 剛好是 VGA 256 色 palette 的 RGB triple 大小(256×3)**,疑似 palette buffer 複製,與 `0x434d1` 的 RGB triple pack 邏輯位置相近(`0x36xxx`),可能同屬一個 palette 處理子系統 |
| `0x4698A..0x4698C` | 0x2(2B) | 2 | `INT 0x16; RET`——BIOS 鍵盤服務呼叫的單指令 wrapper,無獨立語意 |
| `0x469DB..0x469DD` | 0x2(2B) | 2 | `INT 0x31; RET`——DPMI 服務呼叫的單指令 wrapper,無獨立語意 |

**額外交叉比對:`in_function=true` 但文件從未提及的 Ghidra-已分析函式(category b)有 110 個**,
其中命中數最高的是 `FUN_000443d0`(native `0x443d0`,946 bytes,169 個位址命中,是整個
capture 裡命中數最高的未記錄函式)。對它額外查 `xref_to`/`call_scan`:**找到 1 個確認的
直接呼叫端 `0x3ae6d`(在函式 `FUN_0003adf5` 內)**——這是本輪少數幾個新候選裡**有靜態呼叫證據
可查**的,值得下一輪優先 decompile `FUN_0003adf5`/`FUN_000443d0` 兩者。其餘同一 `0x3d000`-
`0x4e000` 範圍內的高命中未記錄函式(`FUN_0003d093`=448B/字串前導空白跳過樣式、`FUN_0003d842`
=512B、`FUN_00042980`=1094B/被 `0x43270`/`0x4364c` 反覆呼叫、`FUN_00049690`=513B 等)本輪
只做了粗略反組譯,未深入 decompile,留給下一輪。

### 9.15.5 誠實範圍:本輪定性全部基於「反組譯樣式辨識」,不是逐位元組還原語意;沒有找到任何
新候選的完整呼叫鏈;不構成任何一項 worklist 解封

**沒有查清的部分(誠實列出)**:
1. 13 個全新區塊裡,除了 `0x443d0`(見上,有 1 個確認呼叫端)之外,**其餘全部 `call_scan`/
   `xref_to` 落空**(對 `0x43270`/`0x404c0`/`0x3ea8e` 三個代表性起點做過 `call_scan` 全域
   窮舉,0 筆命中)——這與 §9.10-§9.11 遇到的情況同宗同源:這塊區域從未被 Ghidra base 分析
   碰過,連呼叫端本身可能也在同一塊未分析區域內,或是透過間接呼叫(跳表/函式指標)呼叫,純靜態
   窮舉在這裡結構性地找不到答案。
2. 本節的「疑似 palette/RGB 處理」「疑似 PCM 音訊混音」「疑似 RLE 解壓縮」「確認是 PIC EOI
   中斷常式」等定性,**全部基於反組譯樣式辨識**(暫存器操作模式、與已知 pattern 比對),
   **不是**逐位元組還原完整語意、**不是**跟已知資源格式(FDOTHER/FIGANI/DATO 等)做過 regression
   比對——比照 §9.9/§9.13 對「像不像」這種定性描述的既有標準,這些判斷屬於中信心,不是高信心
   結論。
3. **沒有**證實這 13 個新候選裡任何一個就是 `91-worklist.md` 那 11 個項目要找的 party montage
   資產解碼器(FDOTHER backdrop/FIGANI/DATO/dialogue-frame grid/mirror fade)本身——只是
   「這些位址在 montage 播放期間真的被執行過,且 Ghidra 從未分析過」,連結到具體 worklist
   訴求需要下一輪做 §9.14.3 那種逐項具體訴求比對(資源類別、呼叫鏈、參數語意),本輪時間範圍
   內未執行。
4. 因此**不修改 `91-worklist.md` 任何項目狀態**,維持 fail-closed。

**給下一輪的具體建議(按投資報酬率排序)**:
1. **優先**:對 `FUN_000443d0`(946B,169 命中,唯一有確認呼叫端 `0x3ae6d`)與其呼叫端
   `FUN_0003adf5` 做完整 `decompile`,這是本輪新候選裡少數能沿著真實靜態呼叫鏈往上追的起點。
2. `0x434d1`(RGB triple pack)+`0x36e57`(768-byte memcpy,疑似 palette buffer)+`0x36f24`
   (RLE 解壓縮)這三個雖然沒有靜態呼叫端,但反組譯樣式彼此吻合「palette/色彩資料處理子系統」
   的假說,值得對 `0x36000`-`0x37000`/`0x43000`-`0x44000` 這兩個範圍做更大範圍的
   `disasm`(擴大 `max_bytes`)完整還原,而不是只看起點附近的片段。
3. 若要更進一步接上這批新候選的呼叫鏈,可複用續六十六驗證過的方法:在已知會執行到這塊區域的
   時間點(例如 CG 播放中)對候選位址本身下 live 斷點,命中時讀 `D SS:ESP` 取 return address,
   比純靜態 `call_scan`/`xref_to` 更可靠(這是 §9.10-§9.11 已經驗證過對這類「未分析區域」
   有效的方法,不需要重新發明)。
4. 若要涵蓋悠妮卡或萊汀卡之後的內容(續六十六的 `LOGC` 剛好在萊汀卡耗盡),直接複用
   `tools/dosbox_exec_trace.sh`,從萊汀卡畫面(或更早的存檔點)重新武裝一次更大的 hex count
   繼續往後捕捉即可,不需要重新設計流程。

## 9.16 2026-08-25 續:§9.15.4 的 13 個全新候選逐一 decompile/disasm 查證完畢——**11 個確認是
通用 XMIDI/PCM 音訊驅動內部程式碼(含一次修正 §9.15.4 對 `0x434d1` 的誤判)、2 個是既有已知
AFM VM 調色盤 opcode handler 首次釘死的精確位址**,13 個裡**零個**是 montage 專屬渲染碼;
第二輪擴大 `LOGC` capture(10 億指令,獨立於續六十六的觸發/按鍵節奏)交叉確認上述判定並多找到
1 個新候選(判定為同一音訊子系統的通用 byte-FIFO push,非高信心)

> 任務背景:§9.15.4 列出 13 個全新候選,逐一定性為「疑似 palette/RGB」「疑似 PCM 音訊混音」
> 「疑似 RLE 解壓縮」「確認 PIC EOI 中斷常式」,但明確承認「反組譯樣式辨識,非逐位元組還原
> 語意」,且除 `FUN_000443d0`(有 1 個確認呼叫端)外,其餘全部 `call_scan`/`xref_to` 落空。
> 本輪任務:完整 decompile `FUN_000443d0` 與其呼叫端往上追,對其餘 12 個候選逐一擴大
> disasm/查 `function_bounds`+`call_scan`,判定各自是「通用共用工具程式(不論播什麼都會執行到)」
> 還是「montage 專屬」;若排除了全部 12 個,才嘗試擴大 live capture 涵蓋悠妮卡之後的內容。

### 9.16.1 `FUN_000443d0` 完整反編譯:XMIDI 音樂序列載入/timbre 目錄載入函式,呼叫鏈
`FUN_0003adf5`(暫停/切換/恢復音軌 wrapper)→ `FUN_00025977`(通用「設定目前音樂軌 ID」API,
**29 個呼叫點分散在 `0x10000`~`0x32000` 整個程式碼範圍**)——確認**不是** montage 專屬

`FUN_000443d0`(native `0x443d0`,946 bytes)完整 decompile 後,程式碼裡直接內嵌兩個除錯字串
`"Invalid XMIDI sequence\n"` 與 `"catNo timbres loaded\n"`,函式本體邏輯是:讀一個 IFF/RIFF
風格的 chunk 標頭(byte-swap 大端序長度運算)、在資料裡掃描子 chunk 找出三個位置索引
(`param_1[2]/[3]/[4]`,經 `FUN_0004997e` 比對 chunk id)、若找不到必要 chunk 就印
`"Invalid XMIDI sequence"` 並回傳 0、否則往下走一段配置 timbre(樂器音色)cache 的邏輯,失敗
時印 `"catNo timbres loaded"`(「catalog 編號的 timbre 已載入」除錯訊息)。這是一個**教科書等級
的 XMIDI(Extended MIDI,1990 年代 DOS 遊戲常見的 AIL 系列音樂格式)序列載入函式**,語意
非常明確,不需要更多佐證。

往上追呼叫鏈:
- **`FUN_0003adf5`**(native `0x39682`-`0x3aeed`,呼叫端 `0x3ae6d`)decompile 顯示它是一個
  「暫停音軌播放通道→呼叫 `FUN_000443d0()` 載入新序列→視情況恢復播放通道」的 wrapper(用
  `DAT_00054178` 做重入計數,呼叫 `FUN_0003f22a`/`FUN_00037c9c`/`FUN_0003f46b` 這組音軌控制
  helper)——語意是**切換目前播放的音樂序列**,不是渲染。
- **`FUN_00025977`**(native `0x25977`-`0x25a95`,decompile:`void FUN_00025977(uint
  param_1)`)是一個**通用「設定目前背景音樂軌道 ID」入口**:比對 `param_1` 跟目前音軌狀態
  `DAT_00051a11`,不同就更新狀態並(除非 `param_1==0xffffffff` 這個「停止」代碼)呼叫
  `FUN_000111ba`(載入資源)→`FUN_0003666c`→`FUN_0003adf5`(上面那個 wrapper)→
  `FUN_0003aeee`→`FUN_0003b124`/`FUN_0003b1a6`(收尾)。`xref_to` 對它查到
  **29 個獨立呼叫點**,位址範圍橫跨 `0x10000`(`0x1047b`)、`0x1a000` 系列(`0x1a249`/
  `0x1a2e7`/`0x1a51d`/`0x1a582`/`0x1a5c7`/`0x1a618`)、`0x22000`(`0x22e6b`)、`0x25000`~
  `0x27000` 一大段(對話/劇情引擎)、`0x2a000`(`0x2a670`/`0x2a681`/`0x2abbf`/`0x2abd8`)、
  `0x32000`(`0x323e1`/`0x32417`/`0x327bb`)——**這是整個遊戲通用的「切換背景音樂」API**,
  任何場景轉換(對話開始、進城鎮、進戰鬥……)只要換了配樂就會呼叫到它。

**結論:`FUN_000443d0` 鏈確認是通用音樂播放子系統,跟這次追蹤窗口正在播什麼畫面完全無關**——
之所以出現在本輪 trace 裡,純粹是因為轉送站幻象播放期間背景音樂換了一次(或維持播放),不是
因為它負責繪製任何 montage 內容。這修正了 §9.15.4「值得下一輪優先 decompile」的定位:decompile
完成後,答案是「優先度應該降到最低」,不是「優先度最高」——調查方向本身就走偏了,只是花的
成本很低(6.6 秒 Ghidra 批次查詢),值得記錄避免下一輪重工。

### 9.16.2 `0x4364c`/`0x43270`/`0x4391f`/`0x42980` cluster:游戲內建的軟體 MIDI 事件派發器
(`FUN_00042980` 對 classic MIDI status byte 的巢狀 switch),**訂正 §9.15.4 對 `0x434d1`
「疑似 RGB triple pack」的誤判**——擴大 disasm 後其實是同一個 MIDI 事件解析器的一部分

`FUN_00042980`(native `0x42980`-`0x42dc5`,1094 bytes)完整 decompile:簽名
`void FUN_00042980(int *param_1, uint param_2, uint param_3, int param_4, int param_5)`,
函式一開頭 `param_2 & 0xf0` 跟 `0xb0`/`0xc0`/`0xe0`/`0x90`/`0x80` 逐一比對——**這些正是標準
MIDI status byte 的高 nibble**(`0x80`=Note Off、`0x90`=Note On、`0xb0`=Control Change、
`0xc0`=Program Change、`0xe0`=Pitch Bend),`param_3` 另外對 `0x6c`~`0x77` 這段做細分派發
(XMIDI 特有的 meta/controller 子類型)。`call_scan` 對 `0x42980` 找到 **24 個確認呼叫點**,
全部落在 `0x42b00`~`0x45299` 這個同一個大範圍內部(`FUN_00042dd0`/`FUN_00042ea0`/
`FUN_00042f50`/`FUN_00043230`/`FUN_00044f00`/`FUN_000450b0` 等函式互相遞迴呼叫),是一個
自成一體、內聚的 MIDI 事件處理系統,不對外(不在這個範圍外有任何呼叫進來的證據)。

`0x4364c`(disasm)是這個 dispatcher 的一段呼叫端:讀取一個 3-byte 事件(`[EBX+0x14]` 指向的
`status/data1/data2`)、對 `status` 高 nibble 做 `CMP EAX,0xb0/0xd0/0xe0` 這種 range 判斷、
`CALL 0x42980`——是同一個 MIDI 派發系統的上層迴圈。`0x4391f`(擴大 disasm)是同一個迴圈的
**收尾/reset 段**:`DEC ECX`(遍歷計數)、`ADD ESI,0x6d4`(每個音軌/channel 狀態區塊
stride=0x6d4=1748 bytes)、迴圈結束後呼叫 `FUN_000382e9`(清空計數)、`POP EBP/EDI/ESI; RET`
——跟 `FUN_000443d0` 內部呼叫的清理 helper 是**同一個函式**(`0x382e9`),這是這個 cluster
跟 §9.16.1 的 XMIDI 載入鏈共用底層 helper 的直接證據,兩者屬於同一個音訊子系統不是巧合。

**訂正**:§9.15.4 把 `0x434d1` 定性為「經典的『讀 3-byte RGB triple、組成 24-bit 值』pattern,
強烈疑似 palette/色彩處理」。本輪擴大 disasm(`max_bytes=300`)後看到完整脈絡:
`EBX=[0x543e0]`(跟 `0x4364c` 讀的是同一個指標)、`EAX=[EBX+0x14]`(跟 `0x4364c` 讀的是
**同一個欄位**——上面確認過的「3-byte 事件游標」)、讀 `EAX[0]/EAX[1]/EAX[2]` 三個 byte 組
24-bit 值後寫回 `[EBX+0x6c]`,**最後 `JMP 0x433a5`——跳回 `0x4364c`/`0x43270` 所屬的同一個
MIDI 派發主迴圈內部**。這證明 `0x434d1` 讀的不是調色盤資料,是**同一個 3-byte MIDI 事件
tuple(status/data1/data2)**,只是剛好也是「讀 3 個相鄰 byte 組 24-bit 值」這個常見 pattern,
跟 palette RGB triple 撞了樣式(§9.15.4 自己也承認這類定性是「反組譯樣式辨識,不是逐位元組
還原語意」的中信心猜測)——**這次是那個警語應驗的實例,不是新錯誤,是原本就承認過的風險
兌現**。修正後:`0x434d1`、`0x4364c`、`0x43270`、`0x4391f`、`0x42980` 全部屬於**同一個 MIDI
事件派發器**,不是分散的獨立候選。

### 9.16.3 `0x3ea8e` 中斷常式完整反組譯:16 通道 rate-accumulator 軟體計時器,由 PIC IRQ 驅動,
逐通道呼叫已註冊的 callback 函式指標——確認是**跟畫面內容完全無關、全程持續運作**的計時基礎設施

擴大 disasm(`max_bytes=400`)後可以看到完整流程:`PUSHAD`+存 DS/ES/FS/GS+切換到私有 stack
(標準保護模式 ISR prologue)→**第一個迴圈**(`EDI` 從 0 到 `0x40` 步進 4,即 16 個通道):
每個通道讀一個 rate 值累加到 `[EDI+0x52ad4]`,跟門檻 `[EDI+0x52b14]` 比較,溢位就
`SUB`+`INC [EDI+0x52b54]`(該通道的「已到期 tick 數」計數器)——這是**16 通道獨立速率的
軟體分頻計時器**(每個通道可以有不同的觸發頻率,不依賴單一 18.2Hz BIOS tick)→`OUT 0x20,AL`
(`AL=0x20`,標準 8259 PIC EOI 指令)+`STI`→**第二個迴圈**:對每個「已到期 tick 數」不為 0
的通道,`DEC` 其計數、`CALL dword ptr [EDI+0x52a54]`(**呼叫該通道註冊的函式指標**)。

這是**驅動整個遊戲計時相關子系統(最可能是音樂序列播放的節拍時鐘,但介面本身是通用的
「N 個可獨立設速率的 callback 通道」,不限定用途)的自訂 IRQ handler**,在遊戲執行期間會
持續每個 timer tick 觸發一次,**跟螢幕上正在播放什麼內容完全無關**——這是本輪對 §9.15.4
「確認是硬體中斷服務常式」定性的完整補完(逐指令細節,不是只停在「有 PUSHAD+OUT 0x20 所以
是 ISR」的粗判),結論不變但證據等級提高。

### 9.16.4 `0x4809b`/`0x47d88`/`0x49430`:PCM 混音輸出/重取樣內迴圈,disasm 逐指令核對確認,
無新資訊但排除疑慮

`0x4809b`(disasm):`EAX=[ESI]; ESI+=4; CMP EAX,0x7fff; JG...; CMP EAX,0xffff8000; JL...;
XOR EAX,0x8000; MOV [EDI],AH; EDI++; loop`——**16-bit 有號值飽和 clamp(±32767)+轉無號
(`XOR 0x8000`)+只取高 byte 寫出**,是軟體混音器把 32-bit 累加緩衝區降轉成 8-bit 無號 PCM
輸出的標準寫法。`0x47d88` 是同構但沒有 clamp 的版本(同一族的簡化版)。`0x49430`(disasm):
`EBP=[EDX+EAX*4]; [EDI]+=EBP; EDI+=4`,搭配 `ADD ECX,[0x538b4]; ADC ESI,[0x538b8]`——**64-bit
(`ECX:ESI`)定點相位累加器**(典型的可變速率取樣播放重取樣手法),`EDX+EAX*4` 是取樣值查表。
三者共同構成一個完整的軟體 PCM 混音管線(重取樣→累加→clamp+輸出),跟 §9.15.4 的初步定性
完全吻合,擴大 disasm 沒有推翻任何結論,只是提高證據等級。

### 9.16.5 `0x404c0`(未完整 decompile,但共用 helper 是強證據)、`0x4698a`/`0x469db`(單指令
wrapper,無獨立語意)——維持 §9.15.4 定性,補一點佐證

`0x404c0` 本輪只查了 `xref_to`(`0x411ea`,DATA 型別),沒有時間完整 decompile,但它跟
`0x382d6`/`0x382db`/`0x382e9` 這組 helper 相鄰(§9.15.4 原記錄),而 `0x382e9` 已在
§9.16.1/§9.16.2 兩處分別確認是 `FUN_000443d0`(XMIDI 載入)跟 `0x4391f`(MIDI 派發器收尾)
共用的清理函式——**間接證據指向 `0x404c0` 也是同一個音訊子系統的初始化程式碼**,但這不是
直接證明,誠實列為「高度疑似,非確認」。`0x4698a`(`INT 0x16; RET`)、`0x469db`
(`INT 0x31; RET`)維持 §9.15.4 的定性:單指令 BIOS 鍵盤/DPMI 服務呼叫包裝,無獨立語意,
可能從程式任何地方被呼叫,不構成候選。

### 9.16.6 `0x36e57`/`0x36f24`:**唯一的正面關聯**——兩者是 doc39 §4.2 已經完整記錄過的
ANI.DAT/AFM 過場動畫 VM「調色盤 opcode 派發表」裡的既有 opcode handler,本輪首次靜態釘死
精確位址(表本身在 native `0x5276a`,逐 byte 讀出確認)——但這**不是新發現的獨立子系統**,
是替一個十幾輪前就已經完整反組譯過的既有框架(doc39)補上兩個原本沒點名的 handler 位址

對 native `0x5276a` 做 `bytes`(40 bytes = 10 個 4-byte 小端 function pointer)查詢,逐一
解碼:`table[0]=0x36e3d`、`table[1]=0x36e57`、`table[2]=0x36e65`、`table[3]=0x36ea7`、
`table[4]=0x36ee0`、`table[5]=0x36f08`、`table[6]=0x36f24`、`table[7]=0x36f69`、
`table[8]=0x36f82`、`table[9]=0x36fac`。§9.15.4 記錄的兩個候選精確對應到其中兩格:

- **`0x36e57`(table[1])**:disasm 只有 4 條指令——`MOV EDI,[0x52766]; MOV ECX,0xC0;
  REP MOVSD ES:EDI,ESI; RET`(768 bytes 逐字複製)。`[0x52766]` 正是 `39-ani-afm-format.md`
  行 87 已經記錄過的「VM palette 暫存指標」(`0x36c7d` 初始化,唯一呼叫端 `0x02048a` 傳入
  `palette=malloc(768)`)——跟 doc39 §4.2 opcode 表描述的「1 | palette | 整包字面載入
  (768 bytes 原樣拷貝)」語意逐字吻合。
- **`0x36f24`(table[6],§9.15.4 定性為「RLE/游程解壓縮迴圈」)**:擴大 disasm 確認完整迴圈——
  `LODSB`讀 control byte、`AND AH,0xC0; CMP AH,0xC0`(高 2 bit 全 1 判斷 run 模式)、
  `AND AL,0x3f`(低 6 bit 當 run length)、`SHR ECX,1; REP STOSW; RCL ECX,1; REP STOSB`
  (word/byte 混合填值展開)——跟 doc39 §4.2 描述的 opcode 2「RLE解壓(2-mode:控制byte高2bit
  ==11→run,否則→literal),填滿 768 bytes」演算法完全一致(doc39 原本只知道語意,沒有點名
  是表裡第幾格、native 位址是多少)。

**誠實範圍**:doc39 §4.2 原始的「十個 opcode」編號順序是否跟這張表的 raw index 一一對應
(例如 doc39「opcode 2」是否就是 `table[2]=0x36e65`,還是像本例這樣 `table[6]` 才是真正的
RLE handler)本輪**沒有逐格全部核對**(只驗證了 `table[1]`/`table[6]` 這兩個跟 §9.15.4 候選
重疊的格子),不排除 doc39 的「opcode N」編號本身跟原始位元組值有一層尚未記錄的映射差異——
這點留給下一輪如果需要完整重建整張表語意時再查,不影響本輪「這兩個位址屬於這張既有 VM
調色盤 opcode 表」的結論。**這兩個候選能被 `LOGC` 追蹤到,是因為本輪路徑經過了 CG 播放
(續六十六 §3 記錄的 CG1/CG2 場景),VM 在播放調色盤特效時執行到這兩個 opcode handler**——
跟 §9.16.1-§9.16.5 的音訊候選一樣,**不是** montage 專屬渲染碼,是遊戲整個過場動畫系統
(doc39,涵蓋開場 logo 到所有 CG 播放)共用的既有基礎設施,只是這次補上了兩個具體位址。

### 9.16.7 小結:13 個全新候選,11 個確認/高度疑似音訊驅動內部程式碼,2 個是既有 AFM VM
調色盤機制的既有位址——**零個**是全新的、montage 專屬的渲染候選

| 候選 | 本輪判定 | 信心 |
|---|---|---|
| `0x443d0`(`FUN_000443d0`) | XMIDI 序列載入,呼叫鏈通向 29 處通用「切換音軌」呼叫點 | 高(完整靜態呼叫鏈) |
| `0x4364c`/`0x43270`/`0x4391f`/`0x42980` | 通用軟體 MIDI 事件派發器(status byte switch) | 高(decompile+24 處內部呼叫) |
| `0x434d1` | **訂正**:同一 MIDI 派發器的 3-byte 事件讀取段,不是 RGB palette | 高(disasm 證實跳回同一迴圈) |
| `0x3ea8e` | 16 通道 rate-accumulator 計時器 ISR,PIC EOI 確認 | 高(完整指令流) |
| `0x4809b`/`0x47d88`/`0x49430` | PCM 混音 clamp/重取樣內迴圈 | 高(disasm 樣式精確匹配) |
| `0x404c0` | 疑似同一音訊子系統初始化(共用 helper `0x382e9`) | 中(間接證據,未完整 decompile) |
| `0x4698a`/`0x469db` | 單指令 BIOS/DPMI wrapper,無獨立語意 | 高(太簡單,沒有語意好爭) |
| `0x36e57`/`0x36f24` | doc39 §4.2 既有 AFM VM 調色盤 opcode 表(`0x5276a`)裡的既有 handler,非新子系統 | 高(byte-level 表格核對+行為完全吻合) |

**這是一個乾淨、有證據支持的「排除」結果,不是新發現渲染候選的正面成果**——13 個候選全數
查清語意,沒有一個指向 montage/角色卡/CG 渲染以外的新猜測。誠實地說,§9.15.4 當初「值得
下一輪優先追」的判斷本身(基於命中數排序、樣式匹配)這次被證明**方向錯了**——命中數最高
不代表跟目標場景最相關,音訊驅動因為背景音樂全程播放,天然會產生大量 trace 命中,這是
`LOGC` 這個方法論本身的已知限制(§9.15.5 已列出「LOGC 只記錄執行過,不記錄跟目前畫面內容的
語意關聯」),本輪是這個限制第一次被具體案例證實。

### 9.16.8 第二輪擴大 live capture(獨立於續六十六,10 億指令,`0x37B13`-`0x37B28` 新候選、
交叉確認 §9.16.1-9.16.6 判定)——技術上達成「往後延伸捕捉」但**沒有**乾淨捕捉到悠妮卡本身

依 doc48 §8.4 recipe 重新開一輪 live 環境(單一 canonical `dbg`/`:99`/`~/fd2-run`,MD5 核對
`FD2.SAV`/`FD2.EXE` 跟既有記錄一致),LOAD→存檔格1→軍營 `Right×3`→出口確認 YES 後,在確認
對話框畫面進 debugger 武裝 `LOGC 3B9ACA00`(十億指令,約續六十六 §3 那次 600,000,000 的
1.67 倍),接著連續送約 65 次 `Return`(每次間隔 0.6 秒,分批夾雜 screenshot 核對)推進——
**同樣重現了續六十六「推進過頭」的已知風險**:screenshot 序列顯示對話正常經過轉送站幻象
場景(莎拉對白→隊伍集合→悠妮開口「我..我..」),但最終停在一個顯示「823 A+05 D+00」戰鬥
HUD、隊伍列隊站在同一走廊場景的畫面(疑似隊長名冊/戰前轉場畫面,不是真正的戰術戰場網格)——
跟續六十六「第一次嘗試(70 次 Return)推進過頭,直接跳到戰場」記錄的症狀一致,`LOGC` 在
剛好 10 億筆時自動耗盡凍結,`FD2.SAV` md5 收尾核對跟開場一致(無 autosave side effect)。

**去重+交叉比對結果**(`tools/dosbox_exec_trace.sh dedup`+`tools/dosbox_exec_trace_analyze.py`,
輸出於 `.wsl_build/trace_analysis2/`):`CS=0170` 主程式碼段 **14,931** 筆唯一位址(比續六十六
的 8,727 筆多,符合「這輪涵蓋範圍更長」的預期)。`in_function=false` 分出 16 個區塊:

1. **15 個舊識**:§9.15.4/9.16 已經處理過的 `0x4364C`/`0x43270`/`0x404C0`/`0x3EA8E`/
   `0x434D1`/`0x4391F`/`0x49430`/`0x4809B`/`0x47D88`/`0x4698A`/`0x469DB` **全部原樣重新出現**
   ——這是**獨立按鍵節奏、獨立觸發路徑(這次多按過頭跳到隊長名冊/戰前轉場,不是續六十六停在
   萊汀卡)的第二次交叉驗證**,強化 §9.16.1-9.16.5「這些是全程持續運作的音訊驅動,跟畫面
   內容無關」的結論(換了完全不同的操作節奏,同一批位址照樣出現)。另外 4 個(`0x33AF1`/
   `0x24618`/`0x24B14`/`0x3312D` 一帶)是隊長名冊/`FDICON`/`31-map-unit-sprites-fdicon.md`
   已有記錄的既有系統,跟本輪停在的「列隊+HUD」畫面吻合,不是新內容。
2. **`0x36E57`/`0x36F24`(AFM VM 調色盤 handler)這次沒有出現**——與「本輪 Enter 節奏過快、
   可能跳過或加速通過了 CG 播放本身」的推測一致(§9.16.6 已確認這兩個位址只在**實際執行到
   CG 調色盤特效**時才會被 trace 到),是這次「按太快漏看 CG」的側面佐證,不是矛盾。
3. **1 個genuinely 全新區塊**:`0x37B13`..`0x37B28`(span 21 bytes,12 個命中位址),之前任何
   一輪(含 §9.15.4 的 13 個)都沒記錄過。

**`0x37B13` 定性**(disasm+`function_bounds`+`xref_to`+`call_scan`):12-byte 的完整小函式
(`PUSH EBX; PUSH EBP; MOV EBP,ESP; MOV EAX,[EBP+0xc]; MOV BL,[EBP+0x10]; MOV EDX,[EAX];
INC [EAX]; MOV [EDX],BL; INC [EAX+0x10]; POP EBP; POP EBX; RET`)——語意是**環狀緩衝區/FIFO
「寫入一個 byte」原語**:`EAX`(第 2 個參數)是緩衝區物件指標,`[EAX]` 存的是目前寫入位置的
指標(先讀出舊值存到 `EDX`,再對 `[EAX]` 本身做 `INC` 前進),把要寫入的 byte(第 3 個參數,
`BL`)寫到 `EDX` 指向的舊位置,`[EAX+0x10]` 是另外遞增的一個計數欄位(疑似「已寫入 byte 總
數」)。`xref_to` 只找到 **1 個 DATA 型別引用**(`0x37b35`,不是 CALL)——這個模式(只有
DATA xref,沒有 CALL xref)跟 §9.16.3 確認的 `0x3ea8e` ISR(唯一 xref 也是 DATA,來自一個
function-pointer 表)相同,暗示 `0x37B13` 也是某個 function-pointer 表/vtable 裡的一格,不是
被直接 `CALL` 呼叫。`call_scan` 全域掃描 0 筆命中,無法進一步確認呼叫端語意。

**誠實定性(中信心,非結論)**:這是一個**極度通用**的環狀緩衝/FIFO push 原語,語意本身
（"寫一個 byte 進佇列,前進寫入指標,遞增計數"）**沒有任何圖形/montage 相關的證據**(沒有
VGA framebuffer 位址、沒有調色盤/sprite 相關運算),且緊鄰 §9.16.1-9.16.2 已經確認的音訊
驅動位址範圍(`0x36000`-`0x3A000` 一帶,`0x37B13` 落在其中)。**傾向判定為同一音訊/裝置驅動
子系統裡的另一個通用 byte-stream 工具函式**(例如 MIDI 輸出位元組佇列),但**沒有找到直接
CALL 型呼叫端可以證實**,不排除是其他用途(如鍵盤輸入緩衝、序列埠 I/O)的通用工具——誠實
列為「疑似,非確認」,不構成 montage 渲染候選。

### 9.16.9 誠實結論:兩輪合計 14 個全新候選(13+1)全部查清語意,**沒有一個**是 montage 專屬
渲染碼;不修改 `91-worklist.md` 任何項目;`LOGC` 方法論本身的一個重要限制被具體案例證實

1. **Part 1(靜態 decompile/disasm)達成任務要求的核心目標**:§9.15.4 的 13 個候選全部完成
   `decompile`/擴大 `disasm`/`xref_to`/`call_scan` 查證,11 個確認或高度疑似屬於通用
   XMIDI/PCM 音訊驅動(含一次對 `0x434d1` 的誤判訂正),2 個確認是既有 doc39 AFM VM 調色盤
   opcode 表裡的既有 handler(補上精確位址,不是新子系統)。**FUN_000443d0**(任務指定的
   「最佳起點」)完整查明是 XMIDI 序列載入函式,呼叫鏈通向一個有 29 處呼叫點的通用背景音樂
   切換 API——確認**不是** montage 專屬,是這次追蹤窗口背景音樂持續播放留下的副產品。
2. **Part 2(擴大 live capture)技術上達成「延伸涵蓋範圍」**(14,931 筆位址 vs 續六十六的
   8,727 筆),但**沒有**乾淨命中悠妮卡本身或悠妮卡之後的新內容——這次的按鍵節奏比續六十六
   更快推進過頭,停在隊長名冊/戰前轉場畫面而不是任何一張角色卡上。多找到的 1 個新候選
   (`0x37B13`)語意上不像圖形渲染,中信心判定是另一個通用音訊/裝置工具函式,不構成正面
   進展。
3. **對 `LOGC` 方法論本身的重要限制,本輪首次用具體案例證實**(§9.15.5 原本只是理論上列出
   這個限制,沒有案例佐證):**「執行過」不等於「跟目標場景語意相關」**——背景音樂/計時器
   ISR 全程持續運作,會在任何追蹤窗口裡產生大量命中,命中數本身不能當作候選相關性的排序
   依據(§9.15.4 原本用命中數排序、優先追最高分的 `FUN_000443d0`,這次證實那正是誤判機率
   最高的一類)。下一輪如果要繼續用這個方法論找 montage 專屬渲染碼,**應該優先過濾掉已知的
   音訊/計時器位址範圍**(`0x36000`-`0x4A000` 這整塊,本輪已經把裡面能查的都查過),而不是
   單純看命中數排序。
4. **沒有**修改 `remake/` 原始碼或 campaign 資產,**沒有**觸發 `FD2.SAV` autosave(收尾 md5
   核對跟開場一致),**沒有**編輯 `91-worklist.md`——兩輪合計 14 個候選全數排除或歸類到既有
   系統,不構成任何一項 worklist 解封條件。`wsl --shutdown` 已在收尾執行(doc48 §8.1 建議的
   降低 deadlock 風險做法)。

## 9.17 2026-08-25 續:重用續六十六/續六十七留下的快取 trace 資料(不需重開 live 環境),對「已知
generic 原語是否也在這個場景被呼叫」做逆向 `call_scan`——排除 sprite-blit 家族、確認未分析區塊
是文字密集的腳本 handler,誠實縮小(但未關閉)montage 影像顯示機制的搜尋範圍(2026-08-25)

> 任務動機:續六十六/續六十七的 19+14 個候選全數排除後,懷疑真正的 CG-blit 程式碼可能藏在
> **已經有 Ghidra function boundary、之前只在其他脈絡下被記錄過**的既有原語裡(本節「假說A」),
> 而不是還要繼續找全新未分析位址。續六十六/續六十七的原始 `LOGCPU.TXT`(7.9GB/更大)雖已不在,
> 但去重後的 `trace_unique_cseip.txt`(12,297/14,931 筆)與完整的 `ghidra_batch_probe.py`
> 批次查詢結果(`trace_analysis/ghidra_results.json`、`trace_analysis2/ghidra_results.json`,
> 每筆 trace 位址各自的 `function_bounds` 結果)**仍留在 Windows 端 `.wsl_build/`**(`.gitignore`
> 排除,不進版控,但檔案本身沒被刪除)——不需要重開 WSL/dosbox-x 就能重新查詢,本節全程只用
> `tools/ghidra_batch_probe.py` 對已建好的 Ghidra project 做純靜態查詢。

### 9.17.1 方法:先列出 doc35 目前已記錄的 generic blit/present/palette 原語清單,對兩份 trace
的 `ghidra_results.json` 做「目標位址落在哪個已執行過的 function 範圍內」查詢(不是只比對
function 起點,避免漏掉「命中同一函式但不是入口那個 byte」的情況)

清單(全部整理自本文件 §2/§3/§4/§6/§9.9,共 12 個):`0x4e63d`(生成 blit,無縮放 RLE)、
`0x37795`(VGA DAC 埠寫入原語)、`0x373c4`(present 用 memcpy helper)、`0x4e8af`/`0x4e8e1`
(RLE 逐列 blit,正向/鏡像)、`0x4e916`(RLE getbyte codec)、`0x4e9bb`(cell blit 原語)、`0x4ea2a`
(FDOTHER#4 16×16 1bpp glyph blit)、`0x373eb`(memcpy helper,doc 明文「非 blit」)、`0x4ec6a`
(§9.9 確認的另一個 RLE getbyte 原語)、`0x2927e`/`FUN_0002921a`(仿射/旋轉縮放 blit 原語)、
`0x29164`(TAI.DAT 台座 loader/blit)。另外 `0x11eb0`(present)、`0x11d40`(VGA DAC 色盤寫)、
`0x1685c`(cell blit dispatcher)、`0x15f84`(FDTXT 排版)四個先前(§9.15.2)已經用「函式起點
精確比對」查過,本輪一併用「函式範圍」重查以確認結果一致。

### 9.17.2 結果(續六十六 trace,600M instructions,正確涵蓋戰前對白→CG1→CG2→詩句→萊汀角色卡
這段窗口):generic **present/palette/文字/字形** 原語全部命中,但整個 **sprite/figure blit 家族
零命中**

| 原語 | 位址 | 續六十六 trace 命中 | 續六十七 trace 命中 |
|---|---|---|---|
| present | `0x11eb0` | ✅ 26 | ✅ 26 |
| VGA DAC 色盤寫 | `0x11d40` | ✅ 56 | ✅ 56 |
| DAC 埠寫入原語 | `0x37795` | ✅ 13(在 `FUN_0003777e` 內) | ✅ 13 |
| cell blit dispatcher | `0x1685c` | ✅ 13 | ✅ 13 |
| FDTXT 排版 | `0x15f84` | ✅ 169 | ✅ 193 |
| cell blit / glyph blit(見下) | `0x4e9bb`/`0x4ea2a` | ✅ 74(同一函式 `FUN_0004e98d`) | ✅ 74 |
| memcpy helper(非 blit) | `0x373eb` | ✅ 83 | ✅ 81 |
| RLE getbyte 原語(§9.9 已知) | `0x4ec6a` | ✅ 13 | ✅ 13 |
| **生成 blit(無縮放)** | `0x4e63d` | ❌ 0 | ✅ 55 |
| **仿射/縮放 blit** | `0x2927e`/`0x2921a` | ❌ 0 | ✅ 73 |
| **RLE 逐列 blit(正向)** | `0x4e8af`/`0x4e8a5` | ❌ 0 | ✅ 9 |
| RLE 逐列 blit(鏡像) | `0x4e8e1` | ❌ 0 | ❌ 0 |
| present memcpy helper | `0x373c4` | ❌ 0(疑似位址誤植,見 9.17.5) | ❌ 0 |
| TAI.DAT 台座 loader | `0x29164` | ❌ 0 | ❌ 0 |

**第一個具體發現**:`0x4e9bb`(doc 舊稱「cell blit 原語」)與 `0x4ea2a`(doc 舊稱「FDOTHER#4
glyph blit」)**其實是同一個 Ghidra function**(`FUN_0004e98d`,`0x4e98d..0x4eb47`,442 bytes)
——過去分別記錄成兩個不同「原語」,現在確認是同一支函式裡的兩個內部位址,不是兩支獨立函式。

**第二個具體發現(核心)**:**兩輪 trace 對 present/palette/DAC/FDTXT/glyph-blit 這五類「文字與
螢幕更新」原語的命中結果完全一致(數字幾乎相同),但續六十六(正確涵蓋 CG 播放窗口的那次)對
`0x4e63d`/`0x2921a`/`0x4e8af` 這整個「sprite/figure blit 家族」是徹底的零命中**——不是命中數
低,是完全沒有任何一個位址落在這些函式的範圍內。續六十七才出現這三者的命中(55/73/9 次),但續
六十七本身在收尾時已誠實記錄「這次按太快、推進過頭,停在隊長名冊/戰前轉場畫面而非任何一張角色卡
上」(見 §9.16.8)。

### 9.17.3 續六十七的 sprite-blit 命中溯源:全部指向battle-menu/AI/portrait 既有子系統,不是
CG 畫面——用純靜態 `call_scan` 找到每個原語函式在全程式範圍內的呼叫端,逐一核對

對 `0x4e63d`(所在函式 `FUN_0004e5cc`)、`0x2921a`、`0x4e8a5` 三者的容器函式做 `call_scan`
(掃全 exe image 找 `E8 CALL rel32` 目標等於該位址的呼叫點,經 Ghidra 反組譯器逐筆確認合法),
逐一核對其呼叫端是否落在續六十七 trace 也命中的 function 範圍內:

- `0x4e63d`(`FUN_0004e5cc`)全程式只有 **1 個外部呼叫端**:`0x4e4f6`(`FUN_0004e4f6`,一個緊鄰的
  wrapper)。`0x4e4f6` 自己的呼叫端只有 4 個(`0x141b0`/`0x14c3a`/`0x14c7d`/`0x14e9f`/`0x189f8`,
  分屬 `FUN_00014121`/`FUN_00014b78`/`FUN_00018890`),續六十七 trace 裡只有 `FUN_00018890`
  (`0x18890`)被命中(112 次)。
- `0x2921a` 全程式有 **4 個呼叫端**:`0x268a3`(`FUN_0002670e`)、`0x27cc3`(`FUN_000279bc`)、
  `0x295c1`(`FUN_00029300`)、`0x2a037`(`FUN_00029daa`)。續六十七 trace 只命中 `0x2670e`
  (98 次),其餘三個都沒被觸及。
- `0x4e8a5`(RLE 逐列 blit)全程式有 **8 個呼叫端**,續六十七 trace 命中其中 4 個:`0x115b6`
  (52 次)、`0x14237`(4 次)、`0x14818`(90 次)、`0x18890`(與上面 `0x4e63d` 共用的同一個
  caller,112 次)。

**逐一查這些 caller 的既有文件記錄**:
- `0x18d8c→0x14818→0x115b6→0x12c0d` 是 `10-sprite-rendering-camp-and-state.md`(L144-150)已經
  完整證實的**戰鬥指令「action-ring」目標選取呼叫鏈**(`0x12c0d` 是「掃單位陣列找格子座標命中」
  的引擎通用 primitive,`13-battle-menu-system.md` 已證是「action-ring dispatcher」的一部分)。
- `0x14237`(`FUN_00014237`)所在的 byte 範圍(`0x14237..0x145CC`)是 `11-enemy-ai.md` 已經完整
  反組譯過的**敵方 AI 物理攻擊評分函式**(「物理攻擊候選」章節,`0x13A9F`/`0x14EF0` 是它的既有
  caller)。
- `0x2670e` 是 `40-speaker-portrait-mapping.md`(L360-362)列出的 12 個讀寫全域場景表
  `[0x53BF7]` 的 caller 之一(該文件本身未逐一展開語意,但已確認是「場景表」讀取相關,屬
  portrait/場景切換子系統)。

**結論**:續六十七命中的 sprite-blit 家族呼叫端**全部**回溯到已有獨立文件記錄的**戰鬥指令選單 /
敵方 AI / 場景表**子系統,沒有一個指向 CG 畫面或章節結局演出。這跟續六十七自己收尾時的誠實記錄
(「這次推進過頭,停在隊長名冊/戰前轉場畫面」)完全吻合——`823 A+05 D+00` 那個 HUD+全隊列隊畫面
很可能會途經戰鬥指令/單位游標一類的通用 UI 元件,連帶命中了它們背後共用的 sprite blit 原語,但
這不是 CG 資產顯示本身。

### 9.17.4 逆向 `call_scan`(從已知原語找呼叫端,而非從候選位址找呼叫端)在**未分析區塊本身**
上的結果:0x31000-0x34000 這塊(已確認含角色卡 renderer 鏈)呼叫 FDTXT **65+ 次**、呼叫
glyph-blit **3 次**、呼叫 sprite-blit 家族 **0 次**

續六十六/續六十七/§9.11 都在 `0x31529..0x321ED` 這段抓到了角色卡 renderer 鏈,但這段(以及它
所在、Ghidra 完全沒建過邊界的 `0x31000-0x34000` 一帶更大範圍)本身無法用 `xref_from`
查詢(`function_bounds` 回傳 `in_function:false`,`xref_from` 因此也拿不到任何結果——這是
§9.10-§9.15 已經記錄過的既有限制)。**但反過來,從已知原語出發做 `call_scan` 不受這個限制影響
**——`call_scan` 是逐 byte 掃全 exe image 找 `E8` opcode,不需要目標位址本身有函式邊界。

對 `0x15f84`(FDTXT)、`0x4e98d`(glyph/cell blit)、`0x1685c`(cell dispatcher)三者做
`call_scan`,只看呼叫端落在 `0x30000-0x34000` 這個範圍內的:

- **`0x15f84`**:全程式 296 個直接呼叫端,其中 **65 個**落在 `0x30000-0x34000`(`0x31c21` 起
  一路到 `0x33f21`,遠遠超出 §9.11 定位的 `0x31529..0x321ED` 那一小段,延伸進整個
  `0x32000-0x34000` 這塊此前完全沒碰過的區域)。
- **`0x4e98d`**(glyph/cell blit):全程式 39 個直接呼叫端,其中 **3 個**(`0x31a28`/
  `0x31bc1`/`0x31dfe`)落在**已確認的角色卡 renderer 鏈範圍內**(`0x31529..0x321ED`)。
- **`0x1685c`**(cell blit dispatcher):全程式 45 個直接呼叫端,**0 個**落在 `0x30000-0x34000`。
- 對照組——**`0x4e63d`/`0x2921a`/`0x4e8a5` 三個 sprite-blit 家族原語,全程式呼叫端清單裡沒有
  任何一個落在 `0x30000-0x34000`**(全部列在 §9.17.3,分別是 1/4/8 個呼叫端,位址範圍集中在
  `0x11000-0x2a000`)。

**解讀**:`0x31000-0x34000`(至少 12KB)這整塊 Ghidra 從未建過邊界的區域,是一個**文字極度密集**
的腳本化 UI handler——光是直接呼叫 FDTXT 排版就有 65 次以上,遠超過角色卡 renderer 鏈本身(§9.11
記錄的 `0x31529→0x319d3→0x31c49→0x320a1` 只是這塊裡的一小段)。它會呼叫 glyph-blit(畫字型
cell,3 次),但**完全不呼叫** sprite/figure blit 家族的任何一個原語。

### 9.17.5 綜合結論:假說A 部分成立(排除 sprite-blit 家族)但未完全解封——CG 影像本身很可能是
`0x31000-0x34000` 內未反組譯的 inline 程式碼,不是對外呼叫某個共用原語

把 §9.17.2-9.17.4 三條證據串起來:

1. **正確涵蓋 CG 播放窗口的續六十六 trace,對 doc35 已知的整個 sprite/figure blit 家族
   (`0x4e63d`/`0x2921a`/`0x4e8af`)是零命中**——這排除了「CG1/CG2 全螢幕圖像是透過跟戰鬥
   figure 相同的共用 blit 原語顯示」這個最直覺的假說。
2. 續六十七 trace 命中的 sprite-blit 家族,靜態溯源全部回到**已有獨立文件記錄的戰鬥選單/AI/
   場景表子系統**,且續六十七本身已知「推進過頭」跳過了目標 CG 畫面——這批命中對 CG 顯示機制
   沒有解釋力,是良性的 false lead。
3. 唯一在**正確視窗**裡命中的「畫面相關」原語是 present(`0x11eb0`)、色盤(`0x11d40`)、FDTXT
   排版(`0x15f84`)、以及一個小型 glyph/cell blit(`0x4e98d`)——後者的呼叫端逆向查證顯示它是
   `0x31000-0x34000` 這塊未分析區域拿來畫**文字**(角色名/數值/poem 字元)的通用工具,不是給
   整張 CG 圖片用的。
4. 同一塊未分析區域(`0x31000-0x34000`)透過逆向 `call_scan` 證實**大量直接呼叫 FDTXT**(65+
   次,遠超過角色卡本身需要的量,顯示整個章節開場的對白/CG字幕/詩句/角色卡是同一個腳本化
   handler 依序處理的文字密集序列)、但**完全不呼叫任何已知 sprite-blit 原語**。

**推論(中高信心,非定論)**:CG1/CG2 全螢幕圖像的解碼與寫入,很可能**不是**透過呼叫某個
doc35 已經記錄過的共用原語完成的——它更可能是**寫死在 `0x31000-0x34000` 這塊從未反組譯過的區域
內部的 inline 程式碼**(例如直接 `rep movsw`/`rep movsd` 把已解碼的圖像資料搬進 work buffer,
再靠已確認會命中的 `0x11eb0` present 出去),混雜在同一個大型腳本 handler 裡,跟角色卡的 FDTXT
呼叫、glyph blit 呼叫寫在一起——這能同時解釋:①為什麼多輪 `call_scan`/`xref_to` 對候選位址
本身持續落空(inline 程式碼沒有獨立的函式邊界可查)、②為什麼 present/palette 兩個「螢幕更新」
原語會被命中但沒有任何專屬「blit」原語被命中(inline 拷貝不透過已知 blit 呼叫)。

**沒有查清的部分(誠實列出)**:
1. 本節**沒有**逐 byte 反組譯 `0x31000-0x34000` 這塊區域裡,扣除已知的 FDTXT/glyph-blit 呼叫點
   之外的「其餘程式碼」——也就是說,還沒有直接找到、指認出具體的 CG 拷貝迴圈本身,只是透過
   排除法把搜尋範圍從「全新未分析位址」進一步限縮到「這塊已知範圍裡,不是 FDTXT 呼叫、不是
   glyph-blit 呼叫的部分」。
2. `0x373c4`(doc 記錄的 present 用 memcpy helper)兩輪都是零命中,但 `0x11eb0`(present 本身)
   有命中——這暗示 doc35 §6 對 `0x373c4` 的位址記錄可能有偏移誤差(類似 §9.5.4 已經發現過的
   「檔案 offset 不等於 linear 位址」陷阱),或者這個特定呼叫路徑没有真的呼叫到 `0x373c4` 那層
   helper;本節未展開查證,留給下一輪。
3. 假說B(用截圖時間點對齊 trace 找 CG 顯示的精確瞬間)本輪**沒有執行**——見下方給下一輪的建議。

### 9.17.6 給下一輪的具體建議

1. **優先**:對 `0x32000-0x34000`(續六十六/續六十七都沒深入查證、但確認有 65+ 個 FDTXT 呼叫
   密集分布的範圍)做一次完整的**逐 byte 線性反組譯**(不是流程導向反組譯,直接從 `0x32000`
   開始每個位址都嘗試解碼,类似 §9.11.1 手動 instruction-boundary 回溯的做法),重點找
   `REP MOVSW`/`REP MOVSD`/直接寫 `ES:[EDI]`/對 `0xA0000`-鄰近位址的直接參照——這類 pattern
   不會出現在 `call_scan` 結果裡(inline 拷貝不是 CALL),必須逐 byte 掃過去才找得到。
2. 若要驗證「CG 拷貝是 inline 而非呼叫」這個假說本身,可以對 `0x11eb0`(present)下 live
   斷點,在 CG1 剛顯示的那一刻用 `D SS:ESP` 讀 return address——如果 return address 落在
   `0x31000-0x34000` 這塊未分析區域內,直接證實 present 是被這塊區域的 inline 程式碼呼叫的,
   等於間接證實了本節的推論(比逐 byte 反組譯更快,但需要重開 live DOSBox-X 環境)。
3. 假說B(screenshot 時間點對齊 trace 找 CG 顯示瞬間)本輪未執行,原因:①`LOGC` 本身沒有
   timestamp/instruction-counter 可以跟截圖時間對齊,需要額外開發「每按一次鍵記錄當下已執行
   instruction 數」的輔助手法,續六十六/續六十七都沒有這樣的基礎設施;②本節用快取資料完成的
   假說A分析已經把搜尋範圍實質縮小(排除 sprite-blit 家族、鎖定 `0x31000-0x34000` 內部
   inline 程式碼這個更具體的方向),對 ROI 的邊際貢獻可能高於重新設計一套時間對齊機制。
   下一輪若要做,建議先試 #2(live present 斷點讀 return address)這個更便宜的驗證手段,
   假說B 的完整時間對齊機制留到 #2 也做不出結果時再上。

## 9.18 2026-08-25 — 執行 §9.17.6 建議 #1:對 `0x32000-0x34000` 逐 byte 線性反組譯,定位到具體的
CG 影像解碼呼叫點(`0x3205f`→`FUN_0004ebff`→`FUN_0004ec66`),用快取的 LOGC trace 交叉驗證確實在
正確視窗內執行過;誠實澄清這不是「新發現的專屬 blit 函式」,是已知的通用 RLE-decompress 引擎
在這個具體呼叫點的接線方式

> 任務:對 `0x32000-0x34000`(2KB,§9.17.4 已確認密集呼叫 FDTXT 的未分析區塊)做逐 byte 手動
> instruction-boundary walking,找 `REP MOVSW`/`REP MOVSD`/直接寫 `0xA0000` 鄰近位址/新的
> resource-load 呼叫。方法與 doc25 §11.7、doc35 §9.11.1 相同:用 `ghidra_batch_probe.py` 的
> `disasm` action(forced `disassemble()` + `getInstructionAt().getNext()` 逐指令步進,不靠
> Ghidra 自動 function 邊界),從已知合法邊界(`call_scan` 確認過的 CALL 指令位址、或前一段
> `RET`/`JMP` 後的下一個 byte)出發,遇到誤對齊(出現不合理的 opcode 序列)就換更近的合法邊界
> 重試。

### 9.18.1 先建立可靠的錨點:`call_scan` 對已知原語做窮舉,取得 0x32000-0x34000 內部所有已驗證的
指令邊界

對 `0x15f84`(FDTXT)、`0x111ba`(資源載入器)做 `call_scan`(全 exe 窮舉 `E8` opcode,每筆用 Ghidra
真反組譯器強制確認合法),過濾出落在 `0x32000-0x34000` 的呼叫點:

- **FDTXT**:64 筆(`0x3209c` 起一路到 `0x33f21`,與 §9.17.4 記錄的「65+ 個」一致,誤差是這次
  用精確窮舉重算)。
- **`0x111ba`**:**5 筆全新**(§9.17.4 沒有查過這個原語)——`0x329b3`/`0x329c7`/`0x3398c`/
  `0x33fe9`/`0x33ffe`。逐一手動回溯 PUSH 引數(§9.18.3 的方法),確認全部是
  `0x111ba("FDOTHER.DAT"@0x51a4d, prevSlot=0, index=N)`,`N` 依序見到
  `9`/`0x5f`(95)/`0x12`/`0x15`/`0x16`/`0x17`/`0x18`/`0x19`/`0x1a`/`0xe`/`0x10`/`0x12` 等多個小
  索引——這是這塊 handler 從 `FDOTHER.DAT` 載入一批 UI/CG 小資源的證據,但引數本身不足以單獨
  判定哪個 index 是 CG 圖片(見 9.18.5 開放問題)。

這批 confirmed CALL 位址提供了密集(每 60-90 bytes 一個)、逐 byte 驗證過的合法邊界網,足以支撐
逐段 `disasm` 而不必猜測對齊。

### 9.18.2 逐段線性反組譯 0x32000-0x34000:REP MOVS 家族全域掃描只找到 **1 筆**,且與 CG 顯示
無關(小型 7-dword struct copy,銜接一個已知的「移動」呼叫)

先用 `bytes` action 一次抓出整段 8192 bytes 原始 hex,在 Python 端做全域 byte-pattern 掃描
(比對 `REP MOVSD`=`F3 A5`、`REP MOVSW`=`F3 66 A5`、`REP MOVSB`=`F3 A4`、`REP STOSx` 三種、
`ES:` override prefix=`0x26`、字面值 `0xA0000`(LE `00 00 0A 00`)):

| pattern | 命中數 | 位址 |
|---|---|---|
| `REP MOVSD` | **1** | `0x3224b` |
| `REP MOVSW`/`REP MOVSB`/`REP STOSx` | 0 | — |
| `ES:` prefix | 5 | `0x33352`/`0x33360`/`0x333be`/`0x338b4`/`0x338f4`(均在後段,未逐一展開,見 9.18.5) |
| 字面 `0xA0000` | **66** | 幾乎每個 FDTXT 呼叫點前都有一個(見 9.18.4) |

對唯一一筆 `REP MOVSD`(`0x3224b`)用 `disasm` 逐指令核對上下文(從最近的合法邊界
`0x3222b` 的 `JMP` 之後、`0x32230` 開始重新解碼):

```
0x32230 PUSH  0x3c
0x32235 CALL  0x3702f          ; 與已知 0x37795/0x3790a 同宗的 DAC/palette helper 家族
0x3223a PUSH  ESI
0x3223b PUSH  EDI
0x3223c SUB   ESP,0x24
0x3223f MOV   ECX,0x7          ; 7 個 dword = 28 bytes
0x32244 MOV   EDI,ESP          ; 目的地是本地堆疊,不是 VGA/work buffer
0x32246 MOV   ESI,0x52725      ; 來源是一個固定的全域小 struct
0x3224b REP MOVSD               ; 複製 28 bytes 到堆疊
0x3224e PUSH  [ESP+0x30]
0x32252 CALL  0x1f183          ; 已知的「移動」相關呼叫(見專案 memory 備註「closed 0x1F183
                                 ; movement gap」),與圖像顯示無關
```

**結論**:這是把一個固定 28-byte 結構從 `0x52725` 複製到堆疊當作 `CALL 0x1f183` 的引數暫存區,
跟 CG 圖像資料量級(數萬 bytes)完全不成比例,語意上也接到已知的「移動」子系統,不是 CG blit。
**這排除了「CG 拷貝是一段裸露的 REP MOVS 迴圈」這個最直覺的子假說**——0x32000-0x34000 全域
唯一的 REP MOVS 指令跟 CG 顯示無關。

### 9.18.3 找到真正的機制:`0x3205f` 呼叫 `FUN_0004ebff`,一個「以資料流自帶的 width/height 為
迴圈邊界、逐列 RLE 解壓縮寫入、步進量(stride)由呼叫端傳入」的通用引擎函式——引數逐一回溯後,
這正是這塊 handler 用來把 CG 像素資料寫進 work buffer 的呼叫

在 §9.17.4 已知角色卡鏈 `0x31529..0x321ED` 內部的迴圈(`0x32031→0x32043→0x3213d→0x321ed`
循環,`INC EDI; CMP EDI,[ESP]; JGE 0x31e27` 跳回既有鏈)逐指令核對時,发现這段迴圈裡有一組先前
從未展開過的呼叫:

```
0x32031 DEC   byte ptr [ESP+0x1c]      ; 遞減一個「剩餘階段數」計數器
0x32035 MOVZX EAX,byte ptr [ESP+0x1c]
0x3203a CMP   EAX,0x2
0x3203d JGE   0x32043                  ; 剩餘 >=2 時 BL=0(fall through)
0x3203f MOV   BL,0xc                   ; 剩餘 <2 時 BL=0xC(12)——二選一的圖像/表格索引
0x32041 JMP   0x32045
0x32043 XOR   BL,BL
...
0x32045 MOVZX EAX,BL
0x32048 MOV   EBX,[0x53a85]            ; EBX = 表格基底指標
0x3204e ADD   EBX,dword ptr [EBX+EAX*1]; EBX += *(EBX+idx) —— relative-offset table,
                                        ; idx=0 或 0xC(12) 兩個 slot 解出實際來源指標
0x32051 PUSH  0x140                    ; stride = 320(螢幕寬度)
0x32056 PUSH  EBX                      ; 來源指標(剛解出的 RLE 資料流)
0x32057 MOV   EAX,[0x53c67]            ; 目的地偏移(同一全域,§9.9.4 已知是 TXT 直譯器切換的
                                        ; 「場景/音樂 ID」,這裡兼作 work buffer 內偏移量)
0x3205c ADD   EAX,ESI                  ; EAX = ESI(work buffer 基底) + 偏移
0x3205e PUSH  EAX                      ; 目的地指標
0x3205f CALL  0x4ebff                  ; FUN_0004ebff(dest=EAX, src=EBX, stride=0x140)
```

`FUN_0004ebff`(`0x4ebff-0x4ec30`,50 bytes)完整反組譯:

```
PUSH EBP; MOV EBP,ESP; PUSHAD
MOV EDI,[EBP+8]     ; param1 = dest (ESI+偏移,即 work buffer 內某個子區域)
MOV ESI,[EBP+0xc]   ; param2 = src  (RLE 壓縮資料流指標)
MOV EBX,[EBP+0x10]  ; param3 = stride (呼叫端傳入 0x140=320)
LODSW ESI            ; AX = *(WORD*)src; src+=2   -> 讀出資料流表頭的「寬度」
MOV BP,AX
LODSW ESI            ; AX = *(WORD*)src; src+=2   -> 讀出資料流表頭的「高度」
MOV DX,AX
XOR ECX,ECX; XOR AX,AX
row_loop:
  PUSH EDI
  MOV CX,BP                    ; 內層迴圈次數 = 寬度
  col_loop:
    CALL 0x4ec66                ; 見下方——標準 RLE getbyte 原語(§9.9 已記錄)
    STOSB ES:EDI                ; *dest++ = AL(解壓縮出的一個像素 byte)
    LOOP col_loop
  POP EDI
  ADD EDI,EBX                  ; dest += stride,換下一列
  DEC DX
  JNZ row_loop                 ; 外層迴圈次數 = 高度
POPAD; POP EBP; RET
```

`CALL 0x4ec66` 呼叫的正是 **doc35 §9.9.3 已經逐 byte 反組譯確認過的「教科書級 RLE getbyte 原語」**
(`OR AH,AH; JZ read_new; DEC AH; RET; read_new: LODSB; CMP AL,0xC0; JA is_run; XOR AH,AH; RET;
is_run: MOV AH,AL; SUB AH,0xC1; LODSB; RET`)——AH 是「目前顏色的剩餘重複次數」,AL 是目前要填的
顏色值,是標準的 run-length byte-stream 解碼器。

**這正是一個完整、自洽的「解壓縮一張點陣圖到緩衝區」迴圈**:資料流表頭前 4 bytes 是寬高
(`LODSW`×2),逐 pixel 呼叫 RLE getbyte 解出顏色、`STOSB` 寫進目的緩衝區,每列結束後用呼叫端
傳入的 `stride`(這裡是 `0x140`=320,螢幕寬度)推進到下一列——這不是「特定畫面專屬」的寫法,而是
一個 generic「RLE image blob → linear buffer, given width/height (from stream) + stride (from
caller)」函式,可以用在任何尺寸、任何目的緩衝區的圖像。

### 9.18.4 收尾:目的緩衝區與後續 `present()` 呼叫是同一個 `ESI`,直接串起「解壓縮進 work
buffer」→「present 到 VGA」的完整鏈

`0x3205f` 呼叫結束後幾十 bytes 內(`0x32165` 一帶),同一個 `ESI` 暫存器(呼叫 `FUN_0004ebff`
時用來算目的地位址的那個)被直接 `PUSH ESI` 當作 `0x11eb0`(已知 present 原語)的來源引數:

```
0x32168 PUSH 0xc8       ; 200(高度)
0x3216d PUSH 0x140       ; 320(stride)
0x32172 PUSH 0x140       ; 320(stride)
0x32177 PUSH ESI         ; 來源 = 同一個 work buffer 基底
0x32178 PUSH 0x140       ; 320
0x3217d PUSH 0xa0000     ; 目的地 = VGA framebuffer 線性位址
0x32182 CALL 0x11eb0     ; present(0xA0000, 0x140, ESI, 0x140, 0x140, 0xc8)
```

`0x3217d PUSH 0xa0000` 這個字面值在整段範圍出現 **66 次**——幾乎每一個 FDTXT 呼叫前都有一次,
證實這不是 CG 專屬的參數,而是 `FDTXT`/`present` 呼叫的標準樣板引數(目的地固定是 VGA
framebuffer、stride 固定是螢幕寬度),不是本節要找的「CG 專屬證據」;真正有鑑別力的是
`0x3205f` 這個呼叫點本身的引數接線方式(表格索引選圖 + 資料流自帶尺寸 + stride 傳遞),不是
`0xA0000` 這個常數。

**這條鏈完整回答了任務的核心問題**:CG 影像的像素資料,是先由 `0x111ba` 從 `FDOTHER.DAT` 載入
一段 RLE 壓縮的資料流(存進由 `[0x53a85]` 索引的一張 2-slot(至少)relative-offset 表,依一個
逐迴圈遞減的「剩餘階段數」計數器在兩個 slot 之間切換——結構上與任務描述的「CG1→CG2」兩張圖像
輪替吻合,但本節未逐一證實這兩個 slot 真的分別對應 CG1/CG2 或其他兩種資產),再由 `0x3205f`
呼叫已知的通用引擎函式 `FUN_0004ebff`(内部呼叫 §9.9 已記錄的 RLE getbyte 原語
`FUN_0004ec66`)逐列解壓縮寫進 `ESI` 為基底的 work buffer,最後由既有已知的 `present()`
(`0x11eb0`)把整個 work buffer copy 到 VGA framebuffer(`0xA0000`)。**沒有任何一步是裸露的
inline REP MOVS 拷貝**,§9.17.5 原本推論的「inline REP MOVS」假說沒有成立,但「CG 拷貝碼在
`0x31000-0x34000` 內部,不是靠呼叫某個 sprite-blit 家族原語」這個更上層的判斷成立——只是實際
機制是「呼叫另一個此前沒被列進 sprite-blit 家族清單、但本身也是通用共用原語的解壓縮函式」,不是
一段真正 hand-inlined 的拷貝迴圈。

### 9.18.5 用快取的 LOGC trace 交叉驗證:`FUN_0004ebff`/`FUN_0004ec66` 的函式本體在續六十六
trace(正確涵蓋 CG 顯示窗口)裡有 **61 個不重複位址命中**,證實這段程式碼確實在真正的 CG 顯示
當下執行過(不只是「可達」,是「真的執行了」)

用 `native+0x19C000=live` delta(§9.9.1 已在 `0x4Exxx` 這段位址範圍逐 byte 驗證過)把
`0x4ebff-0x4ec7b`(涵蓋 `FUN_0004ebff`+`FUN_0004ec66` 兩個相鄰函式)換算成 live 位址
`0x1EABFF-0x1EAC7B`,對 `.wsl_build/trace_unique_cseip.txt`(續六十六,600M instructions,
正確涵蓋戰前對白→CG1→CG2→詩句→萊汀角色卡窗口)做範圍過濾:**61 個不重複位址命中**(對照組:
`0x32000-0x34000` 整段範圍在同一份 trace 裡有 171 個不重複位址命中,量級一致,沒有異常)。

### 9.18.6 對 doc35 §9.9.4「`FUN_0004ebff`/`FUN_0004ec66` 是通用共用原語,不是 montage 專屬」
這個既有結論的關係澄清——兩者不矛盾,是同一件事的兩個層次

§9.9.4 已經用 `call_scan` 證實 `FUN_0004ebff` 全程式有 **36 個直接呼叫端**,散佈在對話系統、戰鬥
選單/走位、spell/FIGANI 特效(doc37)等幾乎所有子系統,並且明確給出的判準是「幾十個不相關呼叫點
=generic utility,不是 dedicated renderer」——這個結論**依然成立,本節沒有推翻它**,`0x32ab5`
(§9.9.4 原文已列出的其中一個呼叫端)本身就已經落在 `0x32000-0x34000` 這個範圍內,只是先前沒有
被連結到「這是 CG 顯示的機制」這件事上。

本節要澄清的是**問題本身問錯了層次**:任務要找的是「CG 影像是被什麼程式碼畫出來的」,不是「有沒有
一個 montage 專屬的 dedicated 函式」。doc9.9.5 point 4 早就預言過這個引擎的架構模式——「這個引擎
很可能根本沒有『一個特定 function 是 ending montage 的 orchestrator』這種東西」——本節的發現
精確印證了這個預言在 CG 影像顯示這一層也成立:CG 圖片的解壓縮呼叫的正是全遊戲共用的通用
「RLE-decompress-with-caller-supplied-stride」引擎函式,跟畫戰鬥選單、對話框描邊字型用的是**同一個
架構模式**(共用引擎原語 + 資料驅動),不是另外寫一套專屬的圖像 codec。這跟 §9.2 對戰鬥選單
carousel 系統的既有結論(「完整可驗證的 phase-table 演出引擎,靠資料索引驅動共用原語,不是
per-feature 專屬函式」)是同一種設計哲學的第三次獨立印證。

### 9.18.7 誠實範圍:沒有查清的部分

1. **`[0x53a85]` 這張 relative-offset 表格的完整內容**(有幾個 slot、slot 0 和 slot 0xC 分別解出
   的指標實際指向哪個資源、是否真的分別對應 CG1/CG2)本節**沒有**逐一 dump 出來確認——只確認了
   「用一個遞減計數器在至少 2 個 slot 之間切換」這個控制流結構,沒有確認資料語意。
2. **哪個 `0x111ba("FDOTHER.DAT", 0, index)` 呼叫(§9.18.1 列出的 11 個 index)實際把資料寫進
   `[0x53a85]` 表格**本節**沒有**逐一比對——只確認了這批 index 存在,沒有把「載入」跟「解壓縮進
   work buffer」這兩步用同一個 index 串起來。
3. **5 個 `ES:` prefix 命中**(`0x33352`/`0x33360`/`0x333be`/`0x338b4`/`0x338f4`,§9.18.2 表格)
   **沒有**展開查證——這些在角色卡/poem 段落之後的區塊(`0x33000+` 一帶),本節優先處理了
   `0x4ebff` 這條更接近核心目標的線索,沒有時間逐一核對這 5 個 `ES:` 命中的語意。
4. **本節全程沒有重開 live DOSBox-X 環境**(§9.17.6 建議 #2 的「對 present 下斷點讀 return
   address」沒有執行)——續六十六 trace 的**執行證據**(61 個位址真的被執行過,不只是可達)已經
   達到跟 live 斷點類似的驗證強度,ROI 判斷上沒有必要再開一輪 live 環境去重複驗證同一件事。

### 9.18.8 對 `91-worklist.md` 的影響:**未修改**——這是 ch27 戰前 CG1/CG2 顯示問題,跟 worklist
`0x2bce5`/`native_2c548` 那組「結局 party montage」cluster 是兩個獨立的東西

`91-worklist.md` 搜尋 `0x2bce5`/`native_2c548`/「下一個 ending gate」的 11 個項目,記錄的是
**ch26/ch29 戰後(post-battle)的「party montage」渲染系統**——doc35 §9.11.4/§9.11.5/§9.12-§9.14
已經用三輪獨立靜態方法確認這組位址(`0x2bce5`/`0x2c172`/.../`0x2c773`)全部落在既有的 §9.2
戰鬥選單 carousel handler 內部,跟本篇(§9.10 起)一直在查的 **ch27 戰前「轉送站」CG1/CG2/詩句/
角色卡演出**是完全不同的兩段程式碼、不同的觸發時機、不同的呼叫鏈,§9.11.5 已經明文訂正過這個
框架混淆。本節(§9.18)的發現屬於後者(ch27 戰前 CG 顯示機制),**不構成**對 `0x2bce5`/
`native_2c548` party montage cluster 任何一項的解封證據,因此依 worklist 稽核慣例維持這 11 項
現狀不動。

### 9.18.9 給下一輪的具體建議(如果要繼續深挖)

1. **最高優先**:dump `[0x53a85]` 表格的完整內容(有幾個 slot、每個 slot 解出的指標指向哪裡),
   搭配逐一核對 §9.18.1 列出的 11 個 `0x111ba(...,index)` 呼叫寫入哪個 slot——這能把「index 0
   和 0xC 分別是 CG1 還是 CG2」這個開放問題坐實。
2. 若想要 100% 影像級證據(不只是程式碼路徑證據),可以對 `0x4ebff`(live `0x1EABFF`)下斷點,
   命中時 dump `EDI`(目的地指標)指向的 work buffer 記憶體,存成 raw 320-wide 點陣圖用既有的
   `internal/afm`/`internal/fdother` 之類的 palette 轉換工具轉成 PNG 視覺比對,直接肉眼確認
   解出來的像素是不是遊戲截圖看到的 CG1/CG2 畫面——這是本篇任務(過去 20+ 輪)第一次有機會做到
   「反組譯結論 → 實際像素比對」的完整閉環,值得優先於任何其他後續動作。
3. §9.18.7 列出的 5 個 `ES:` prefix 命中值得順手查一下,但優先度低於 #1/#2——它們在角色卡/poem
   段落之後,大概率是另一組文字繪製相關的 helper,不太可能是另一個獨立的 CG blit。

## 9.19 2026-08-25 續:執行 §9.18.9 建議 #2——live 斷點 dump CG1 work buffer 做像素比對,
**發現並修正了自己的 native→live delta 加法錯誤**,修正後用活體斷點證實 `0x3205f`
(`FUN_0004ebff`)確實會被執行、且回傳位址/RLE 資料格式與 §9.18 的反組譯完全吻合——**但只在
角色卡(萊汀卡)畫面命中,CG1 本身與 CG1→CG2 之間的「懸浮天空島嶼淡入淡出」子動畫全程掛著同一個
斷點跑過去,一次都沒有命中**;因此把 §9.18「`0x3205f` 是 CG1/CG2 影像顯示機制」這個論斷改判為
**只對角色卡成立、對 CG1 本身不成立**,真正繪出 CG1 像素的程式碼仍未定位

> 任務:對 CG1 work buffer 下斷點、dump 記憶體、轉 PNG,跟真實截圖肉眼比對,做出本系列 20+ 輪
> 追蹤以來第一次「反組譯結論→實際像素」的完整閉環。

### 9.19.1 環境與方法論:`tools/dosbox_harness.sh` 隔離 instance(`cgcheck`),
**首次為這個任務找到比續六十四/六十六「隨機 Escape 亂按」更穩定的觸發手法**——47 格死亡
signature + End Turn 確認,兩輪獨立重開機都精確命中同一句台詞

依 doc48 §8.4/§9 recipe 啟動 `dosbox_harness.sh launch cgcheck`(WSL2 Ubuntu distro,不是舊記錄
提到的 kali-linux;`~/fd2-run`/`~/fd2-dosbox-build` 都在 Ubuntu 這顆 distro 下,合先敘明,免得
下一輪誤連錯 distro 空手而回)。LOAD→存檔格1(「1)第二十七章 命運的交會點」)→軍營`Right×3`→
出口確認YES→逐句 `Return` 推進戰前對白抵達戰場(`823 A+05 D+00` HUD fingerprint)。

**新方法論確認(比續六十四/六十六的「隨機 Escape 亂按」更可控)**:複用續六十二已驗證的
「47 格敵方死亡 signature + End Turn 確認」捷徑(`DAT_00053a45` 對應的 unit record 陣列,live
基底 `0x26DF88`,record stride `0x50` bytes,`+5` 為死亡/已行動旗標)。本輪**用 `D 0178:26DFC8`
核對索爾 HP 現值 `0x0337`=823,兩次獨立重開機都在同一個 live 位址精確拿到同一個數值**,證實這個
基底位址對這個特定存檔+場景是穩定、可重現的(不是每次重開機都要重新窮舉)。批次
`SMV <slot16..90 的 +5> 01`(用「明文展開成腳本檔案」的手法,避開續六十二記錄過的 bash 迴圈
+tmux send-keys 不穩定問題)寫死 47+ 格敵方 record 後,移動游標到空地格→`Return` 開系統選單環→
`Down` 選 `END`→`Return`→「要結束本回合的行動嗎?」確認框→`Return`(YES)——**兩次獨立重開機
都在確認 YES 後立刻精確重現同一句台詞**(莎拉「就是這個了,轉送站..好久沒看到這種東西了....」),
比續六十四/六十六記錄的「連續 Escape/Return 亂按、隨機觸發」更快、更可控、100% 可重現(本輪唯一
一次用純 `Escape`/`Left×4`/`Return` 隨機探索的嘗試,在同一個乾淨重開的 session 裡連續 4 次都
沒有觸發,證實這條「戰前 vision」捷徑本身確實跟先前記錄的一樣不穩定;47 格死亡 signature+End Turn
才是本輪找到的穩定替代路徑)。

**意外的內容補完**:這次完整逐句推進看到的對白,比續六十二/六十四/六十六記錄的「莎拉一句話帶過→
索爾一句『悠妮?妳還好吧』→直接 CG1」豐富得多——完整包含悠妮的告白(「所有過去的事,我都想起來了。
請原諒我騙了你...」)、索爾的挽留(「不管是為了什麼事,我都不會怪妳,我只是想送妳回家...相信我吧」)、
一段先前完全沒記錄過的「A1 型分解傳送啟動待命,座標1-1-72」控制台指令序列、悠妮的訣別
(「沒有天空之鑰,只有我能直接從此地前往黃金城...請忘了我吧,我並不是一般的人類」「索爾,永別了,
我永遠永遠也不會忘記你的,希望你以後幸福快樂....」)——**這一大段先前 3 輪記錄都跳過的完整劇情文字
本輪首次逐句截圖存證**(`.wsl_build/cg2_vis1~24.png`、`cg3_v2~v3.png`,過程 debug 產物)。CG1
(懸浮天空島嶼)顯示時索爾的台詞是「看!是..是黃金城!」,之後有一句「啊!又..又消失了!」——
**這證實 CG1 不是單張靜態全螢幕圖,懸浮小島本身是會淡入/淡出(出現又消失)的一段小動畫**,疊在
一張靜態天空+雲朵背景之上(§9.19.5 進一步討論這對假說的影響)。

### 9.19.2 關鍵除錯:發現並修正自己的 hex 加法錯誤——`0x3205f + 0x19C000` 正確值是 `0x1CE05F`,
不是先前誤算的 `0x1FC05F`;第一輪用錯值下斷點導致「CG1 全程無命中」的假陰性,修正後同一個位址在
角色卡畫面立刻命中

本輪第一次嘗試對 `0x3205f`(§9.18.3 判定的 CG 解碼呼叫點)下斷點時,**手動心算**
`0x3205f + 0x19C000`,誤算成 `0x1FC05F`——`BP 0170:1FC05F` 全程掛著 RUN,從戰前對白、CG1
懸浮小島出現/消失、到後續「index 帶回去的角色背影」子場景,**一次都沒有命中**,一度誤判為
「§9.18 的 `0x3205f` 假說被 live 證據推翻」。**除錯關鍵**:改用同一個 live 斷點對通用引擎
入口本身(`FUN_0004ebff`,native `0x4ebff`,live `0x1EABFF`,§9.18.5 已驗證過的位址)下斷點,
`RUN` 之後在**角色卡畫面**(萊汀卡,§9.19.4)立刻命中,讀出命中瞬間 `D SS:ESP` 的返回位址是
`0x1CE064`——換算 native(`-0x19C000`)得到 `0x32064`,**正是 `0x3205f` 這條 5-byte `CALL`
指令的下一條指令位址**,證實呼叫鏈完全按 §9.18.3 的反組譯發生。**回頭用 Python 重算
`0x3205f + 0x19C000`,正確值是 `0x1CE05F`**——這才發現自己第一次手動心算加錯了 `0x30000`
(誤算成 `1FC05F`,正確是 `1CE05F`)。**這是本輪最重要的方法論教訓**:live 斷點位址換算
一律要用工具(哪怕只是 `python3 -c "print(hex(...))"`一行)算,不要手動心算 hex 加法——本輪
因為這個純算術錯誤,浪費了一整輪「CG1 完全無法觸及此程式碼」的假陰性排查。

### 9.19.3 修正位址後重測:`BP 0170:1CE05F` 精確命中,引數與資料格式逐位元組核對,
與 §9.18.3 反組譯**完全吻合**——確認這條呼叫鏈是真實、會執行的程式碼,不是靜態反組譯的紙上猜測

用修正後的 `BP 0170:1CE05F`(斷在 `CALL` 指令本身,尚未執行)重新 `RUN` 到同一個角色卡畫面,
命中時直接 `D SS:ESP` 讀出三個引數(cdecl push 順序,`[ESP+0]`=dest、`[ESP+4]`=src、
`[ESP+8]`=stride):

```
dest   = 0x003FECA0
src    = 0x00266F38
stride = 0x00000140  (=320,螢幕寬度,與 §9.18.3 的 PUSH 0x140 逐位元組吻合)
```

`D 0178:266F38` 直接讀 src 指標指向的資料流(尚未被 `LODSW` 消耗,原始未動過):

```
50 00 50 00 C8 4A C1 FE C2 3F C1 FE 3E 3D 3C ...
```

前 4 bytes = width/height 各一個 word:`0x0050`=80、`0x0050`=80——**一張 80×80 的小圖**,不是
CG1 那種 320×200 全螢幕圖。第 5 byte 起 `C8 4A C1 FE C2 3F ...` 逐位元組核對 §9.18.3 記錄的
RLE getbyte 解碼規則(byte>0xC0 是 run marker):`C8`(=200)→ run_length=200-193+1=8,下一個
byte `4A` 是要重複填的顏色值,填 8 次;接著 `C1`(=193)→run=1,填 `FE` 一次;`C2`(=194)→
run=2,填 `3F` 兩次——**是一段合法、自洽的 RLE 位元組流,格式與 §9.18.3 反組譯出的解碼規則
完全對得上**。連續對同一個斷點 `RUN` 20 次,每次 dest/src/stride 三個引數逐位元組完全相同
(`EDI` 計數器從 1 一路數到 24+)——**這是這張卡片畫面本身的一個小動畫元素(可能是卡片邊框裝飾
或角色卡場景裡持續播放的某個效果)在每一楨都重新解碼同一份 80×80 資料**,不是每次畫不同內容。

**結論(高信心)**:`0x3205f`→`FUN_0004ebff`→`FUN_0004ec66` 這條呼叫鏈**確實會在真實遊戲執行中
被觸發、引數接線方式與 §9.18.3 純靜態反組譯出的結論逐位元組吻合**——這不再是「反組譯出來、理論上
成立」的假說,是 live 執行證據直接坐實的事實。§9.18 的核心反組譯工作(呼叫鏈本身怎麼接線、
RLE 解碼器怎麼運作)**完全禁得起 live 驗證**,沒有任何一步被推翻。

### 9.19.4 但意外的轉折:同一個斷點掛著繼續 `RUN`,CG1 本身(懸浮天空島嶼淡入淡出)整段**一次
都沒有命中**——只有進到角色卡畫面才命中;兩輪獨立重開機、外加一次對 §10.1 已知的通用 blit
原語(`0x4e63d`)加測都得到相同的負面結果

拿到 §9.19.3 的正面命中之後,本輪**回頭重新測試 CG1 本身**:兩次獨立重開機(§9.19.1 的兩輪),
都在「確認 YES」之後**立刻**用修正後的 `BP 0170:1CE05F` 掛著 `RUN`,逐句 `Return` 推進對白,
每次 `Return` 後用一支 `advance_watch_bp.sh` 腳本自動檢查 debugger pane 是否跳出 `(Running)`
狀態(=斷點命中)。**結果**:從「確認 YES」的瞬間開始,經過完整的告白/挽留/傳送對白
(§9.19.1 記錄的加長版劇情)、CG1 懸浮天空島嶼「看!是..是黃金城!」出現、到「啊!又..又消失了!」
島嶼淡出、再到後續「索爾....」+一段索爾背影對著天空的過場——**斷點全程一次都沒有命中**,直到
畫面轉場到角色卡(萊汀卡)才第一次命中。第二輪追加對 doc35 §10.1 已知的另一個通用 blit 原語
`0x4e63d`(無 RLE 的直接 blit,live `0x1EA63D`)下斷點,同樣掛著 RUN 走完 CG1 出現/消失的完整
子動畫,**同樣一次都沒有命中**。

**這是本輪最重要、最誠實需要記錄的負面發現**:§9.18 論證的「`0x3205f` 是 CG1/CG2 影像顯示機制,
表格 slot 0/0xC 分別對應 CG1/CG2」這個結論,**live 證據只支持了一半**——`0x3205f` 這條呼叫鏈
**確實真實存在、確實會執行**(§9.19.3),但**執行時機是角色卡畫面,不是 CG1 本身**。§9.18.5
用 LOGC trace 交叉驗證「`FUN_0004ebff`/`FUN_0004ec66` 在續六十六 trace 裡有 61 個位址命中,
且這份 trace 正確涵蓋 CG 顯示窗口」——本輪認為這個交叉驗證**方法論上有一個沒有意識到的缺口**:
續六十六那份 600,000,000 instruction 的 trace,錄製窗口是「戰前對白開始」到「萊汀卡渲染中」
**整整一段連續過程**,§9.18.5 只確認了這兩個函式的位址範圍在**這整段窗口內**命中過 61 次,
**沒有進一步切分是命中在 CG1 顯示的當下、還是命中在窗口末端萊汀卡渲染的當下**——本輪的 live
斷點證據顯示,更可能的情況是**這 61 次命中全部(或絕大多數)發生在角色卡渲染階段**,CG1 本身
一次都沒有貢獻命中。這不是推翻 §9.18.5 的執行證據本身(61 次命中是真的、確實發生過),而是
訂正「這 61 次命中證明了 CG1 顯示機制」這個推論——**執行證據存在,但發生的時間點跟原先假設的
不一樣**。

### 9.19.5 CG1「出現又消失」的懸浮小島動畫,**逐 pixel diff 已實測證實**是一個獨立的局部小型
精靈動畫疊在靜態天空背景上,不是單一張 320×200 全螢幕 RLE 圖重繪——這個假說本輪已完成驗證,
不再是待查的開放問題

§9.19.1 記錄過「看!是..是黃金城!」之後緊接著「啊!又..又消失了!」——懸浮小島本身會淡入/淡出,
但背景的天空+雲朵+太陽(以及島嶼消失後殘留在畫面上的部分)全程沒有變化。**本輪用純 Windows 端
PIL 逐 pixel diff 兩張連續截圖(`docs/figures/ch27-prebattle-cg1-island-visible.png` vs
`docs/figures/ch27-prebattle-cg1-island-gone.png`,像素級對齊、同一次 session 連續兩楨,不受
UI 位置漂移影響)完成了這個驗證**:

- 整張 1024×768 screenshot(含底部對白框)diff 出 33,748 個不同 pixel,但這包含了對白框文字
  從「看!是..是黃金城!」變成「啊!又..又消失了!」的差異,不能直接當成 CG 本身的變化範圍。
- **限定在對白框以上的 CG 顯示區(`y∈[233,427]`,`x∈[192,832]`,即遊戲畫面本身,排除對白框)**
  重新 diff:只剩 **8,084 個不同 pixel**,且這些差異點的 bounding box 是
  `x∈[432,587]`(寬 155px)、`y∈[287,424]`(高 137px)——**遠小於整個 640×194 的 CG 顯示區**,
  精確對應畫面中央「懸浮小島」本身的位置,天空、雲朵、太陽、畫面其餘區域逐 pixel 完全相同
  (bbox 外 diff=0)。換算回 320×200 原生解析度(screenshot 是遊戲畫面的 2 倍縮放),小島佔的
  區域大約是原生 **77×68 pixels**,遠小於 320×200 全螢幕。
- 兩張裁切對照圖存於 `docs/figures/ch27-prebattle-cg1-island-crop-visible.png`(小島可見,
  可清楚看到白雪覆頂的山峰+懸浮岩石根系)與
  `docs/figures/ch27-prebattle-cg1-island-crop-gone.png`(同一塊裁切區域,小島完全消失,只剩
  純天空+太陽局部+一小片雲,背景 pixel 與另一張逐一核對完全相同)。

**結論(高信心,live 逐 pixel 實測直接證據)**:CG1 的懸浮小島**確認是一個獨立的局部
sprite/動畫元素**,疊加在一張持續不變的靜態天空+雲朵+太陽背景之上——**不是單一張 320×200
全螢幕 RLE 靜態圖被整張重繪**。這代表 §9.18 原本假設的「CG1 是一張透過 `0x3205f` 解碼的
320×200 全螢幕 RLE 圖」這個問題本身可能問錯了層次:**天空背景**與**懸浮小島**很可能是**兩個
獨立繪製、獨立管理生命週期的資源**(背景可能確實是一張較大的靜態 CG,小島更可能是尺寸接近
`0x3205f` 那條呼叫鏈能處理的中小尺寸 sprite,類似 doc37 記錄的 FIGANI 特效播放機制,或另一個
獨立的 sprite blit 呼叫)——下一輪應該分開查證這兩層,而不是繼續假設「CG1」是單一個需要找到的
呼叫點。

### 9.19.6 誠實範圍:VGA framebuffer(`0xA0000`)無法用這個除錯器直接讀取——已嘗試三種定址方式
全部回傳全零,不是本輪操作失誤,是 DOSBox-X VGA 模擬的已知限制

嘗試過 `D 0178:A0000`(用 app 的 flat data selector)、`D A000:0000`(當作 real-mode 風格
segment,回傳 `LIN=XXXXXXXX PHY=FFFFFFFF`+`na` byte,代表這個「segment」在目前的 GDT 裡根本
不是合法 selector)、`DP A0000`(debugger 文件宣稱的「physical」定址模式)——**三種方式都回傳
全零**,即使當下畫面確實正顯示著 CG1 的懸浮小島(有色彩、非全黑畫面)。判斷這是 DOSBox-X 內部
VGA 模擬架構本身的限制:VGA framebuffer 的讀寫在 DOSBox-X 內部是透過特殊的 page-fault-handled
callback(mode 13h bank-switching/latch 邏輯)實作,不是一段單純的線性 RAM 陣列,debugger 的
通用記憶體讀取路徑繞過了這層 callback,讀到的是底層(未被這層邏輯填色的)記憶體,不是真正的
VGA 內容。**這證實了任務描述裡「work buffer 比 VGA framebuffer 更適合當 dump 目標」這個判斷
是對的**——但也代表如果找不到正確的 work buffer 位址(本輪找到的是角色卡的 80×80 素材,不是
CG1 本體),沒有備援手段可以直接讀 CG1 實際顯示的像素。

### 9.19.7 誠實整體結論

1. **CG1(懸浮天空島嶼)的真實解碼/繪製呼叫點,本輪依然沒有定位到**——§9.18 假設的 `0x3205f`
   被 live 證據排除(至少在 CG1 顯示的時間窗口內排除,見 §9.19.4);doc35 §10.1 已知的另一個
   通用 blit 原語 `0x4e63d` 同樣被排除。這代表繪出 CG1 的程式碼,要嘛是一個目前完全沒有候選的
   全新呼叫點,要嘛是懸浮小島的「出現/消失」動畫走的是完全不同的機制(如 doc39 §4.1-4.2 記錄的
   AFM VM「增量繪圖」bytecode 那一類,見 §9.19.5)。
2. **`0x3205f`→`FUN_0004ebff`→`FUN_0004ec66` 這條呼叫鏈的存在與運作方式,本輪首次用 live
   斷點證實為真**(§9.19.3)——引數接線、RLE 資料格式、返回位址,逐位元組跟 §9.18.3 的純靜態
   反組譯吻合,但**它繪的是角色卡(萊汀卡)畫面的一個 80×80 小動畫元素,不是 CG1**。§9.18 的
   反組譯工作本身沒有錯,錯的是「這條呼叫鏈負責 CG1/CG2」這個延伸推論。
3. **本輪首次為這條調查線(續三十二起、20+ 輪)找到一個比「隨機 Escape/Return 亂按」更穩定的
   觸發手法**——47 格死亡 signature + End Turn 確認,兩輪獨立重開機都精確重現同一句台詞,
   這比續六十四/六十六記錄的隨機觸發更適合下一輪重複使用。
4. **本輪首次完整記錄了這段「轉送站」演出比先前 3 輪記錄豐富得多的對白內容**(§9.19.1)——
   悠妮的告白、傳送啟動序列、訣別台詞,這些先前的記錄都被跳過或摘要成一兩句。
5. **一個純方法論教訓值得記錄**:live 斷點的 native→live 位址換算,一律要用工具算(哪怕只是
   一行 `python3 -c`),不要手動心算——本輪第一次嘗試因為手動心算 `0x3205f + 0x19C000` 算錯
   `0x30000`,浪費了一整輪「CG1 完全無法觸及此程式碼」的假陰性排查,直到改用另一個已知正確的
   位址(`0x1EABFF`)重新測出正確的返回位址,才發現是自己算錯,不是假說被推翻。
6. **這個持續 20+ 輪的謎題(ch27 戰前 CG1/CG2 blit 機制)依然沒有解決**——比續六十九當時樂觀
   判斷的「只差影像級驗證」倒退了一步:不是「機制已知、只差肉眼比對」,而是「機制本身的候選
   (`0x3205f`)被證明是錯的,需要重新找候選」。誠實的信心等級:**低**(對「CG1 具體怎麼畫出來」
   這個問題),但對「`0x3205f` 這條呼叫鏈本身如何運作、繪的是角色卡而非 CG1」這個新結論信心
   **高**(live 斷點直接證據,非推論)。

### 9.19.8 對 `91-worklist.md` 的影響

未修改(本節結論是「排除一個候選、沒有找到真正機制」的負面/訂正結果,不構成任何項目的解封證據;
且如 91-worklist.md 稽核慣例所述,ch27 戰前 CG1/CG2 問題與該檔案追蹤的 `0x2bce5`/`native_2c548`
post-battle party montage cluster 是不同的兩個問題,本節同樣不影響那 11 個項目)。

### 9.19.9 給下一輪的具體建議

1. ~~最高優先、成本最低:島嶼可見/不可見兩張截圖逐 pixel diff~~——**本輪已完成**(見 §9.19.5
   更新):確認是局部 sprite,不是全螢幕重繪。下一輪應直接從第 2 點開始。
2. **現在的最高優先**:天空背景與懸浮小島是兩個獨立資源,應分開查證。小島(約 77×68 原生
   pixels,尺寸介於角色卡小圖示與全螢幕 CG 之間)優先查 doc37(FIGANI 特效)已記錄的呼叫點
   清單,測試是否有任何一個目前已知的 FIGANI 播放函式在這個時間窗口被呼叫;天空背景(靜態,
   不隨小島出現/消失而變化)則可能才是真正走 `0x3205f`/`FUN_0004ebff` 這類 RLE 全螢幕解碼
   路徑的候選,值得針對「背景」單獨下斷點驗證(例如在小島消失、只剩純背景的那一楨前後動作,
   排除小島本身的干擾)。
3. 若小島或背景都不是 FIGANI/已知候選:回到 §9.18.1 記錄的 5 個尚未展開的 `ES:` prefix 命中
   (`0x33352`等)、或重新對 `0x32000-0x34000` 做更細緻的逐 byte 排查,這次要注意排除已經證實
   是角色卡專屬的 `0x3205f`。
4. **重用本輪找到的穩定觸發手法**(47 格死亡 signature+End Turn 確認)取代續六十四/六十六的
   隨機 Escape 亂按——兩輪都精確重現同一句台詞,是這條調查線目前最可靠的重現方法。
5. 任何 live 斷點位址換算,養成用 `python3 -c "print(hex(native+0x19C000))"` 算的習慣,
   不要手動心算(§9.19.2 的教訓)。

## 10. 視窗縮放 filter 查證(worklist 稽核索引「660」——原版全程無任何顯示縮放/內插程式碼)(2026-08-24)

> 任務:worklist 稽核索引曾列「視窗縮放filter查證(可能linear暈染)未見他doc解決,可續靜態code
> inspection,不需DOSBox」。目標是確認原版 EXE 的 320×200→640×400(或任何選單/轉場用到的)縮放,
> 用的是 nearest-neighbor(硬邊 2x 點放大,對齊 remake 目前的 `Scale(2,2)`)還是 linear/bilinear
> (會糊,不對齊 remake 現況)。方法:純靜態複核既有反組譯證據(本節、`03-exe-and-data-structures.md`、
> `39-ani-afm-format.md`),未跑新 Ghidra query——本文既有記錄已經足夠回答這個問題。

### 10.1 結論先講:原版圖形管線從頭到尾只有 320×200 原生解析度,**沒有任何數位縮放/內插運算**——
「nearest 還是 linear」這個問題本身對原版程式碼不成立

三條各自獨立、早於本輪就已完整反組譯的證據鏈同時指向同一個結論:

1. **顯示模式本身就是固定 320×200**:`03-exe-and-data-structures.md`(L11/L15)已確認 `FD2.EXE` 只用
   **VGA mode 13h**(320×200,256 色),DOS 擴充器是 Rational **DOS/4GW**——一個純粹把 16-bit DOS 切到
   32-bit 平坦記憶體的記憶體管理層,**不是圖形/縮放函式庫**。整個遊戲沒有第二個顯示模式,自然也沒有
   「切換到更高解析度模式再縮放進去」這種需求。
2. **blit 原語本身沒有縮放運算**(本文 §2.1、§6,早於本輪已反組譯釘死):
   - 通用 blit `0x4e63d(src,X,Y,dst,stride,transp)` 逐指令反組譯確認**整條路徑沒有任何
     `imul`/`fild`/`fmul` 縮放運算**——來源尺寸即 src header 自帶的寬高,`dst = dst + Y*stride + X`
     直接寫,無伸縮。守方 figure 較小、攻方較大是**美術素材本身畫成不同尺寸**(景深燒進素材),
     不是 runtime 縮放。
   - 螢幕座標系(§6)實測值:螢幕寬 `0x140`=320、高 `0xc8`=200、VGA framebuffer 固定在 `0xA0000`;
     `work buffer stride`=`0x280`=640 **不是** 2x 顯示縮放,是雙倍寬的**離螢幕捲動預備區**(右半用來
     預畫下一幀/捲入內容),present 原語 `0x11eb0` 是逐列 320-byte 的**純 memcpy**(`0x373c4`)把
     work buffer 左半 320 寬複製進 VGA——BG→work、work→VGA 兩段都走同一個無縮放 memcpy。
3. **開場「2」logo 縮放進場動畫也不是內插縮放,而是逐幀不同內容的 VM 繪圖腳本**:
   `39-ani-afm-format.md`(§4.1/§4.2,已由官方 IDA + Docker Capstone 反組譯確認)證實 `ANI.DAT`/AFM
   播放器主函式 `0x020421` 的每一幀是一段 10-opcode「增量繪圖 VM」bytecode,**VM opcode 直接寫 VGA
   `0xA0000`**,不透過額外 blit/縮放步驟。玩家看到的「2」逐幀放大是**美術師預先畫好一系列不同大小
   的幀內容、由 VM 逐幀繪出**,不是程式對單一來源圖做即時 resample。

### 10.2 為什麼原版不需要縮放:mode 13h 的「放大」是類比訊號輸出,不是數位運算

1995 年的實體 VGA 硬體以 320×200 直接驅動 RAMDAC 輸出類比訊號給 CRT,螢幕本身用掃描時序把這
320×200 的像素網格顯示滿整個畫面——這是類比電路層級的行為,不存在「nearest 還是 bilinear」這種
數位濾波選擇。換句話說,**「320×200→640×400 2x 倍增」在原版 EXE 的程式碼裡完全不存在**;這個倍增
關係只在下列兩種**現代**情境下才會出現,兩者都不是原版 EXE 的行為:

- DOSBox/DOSBox-X 之類模擬器的輸出縮放器(依使用者設定可選 nearest/hqx/其他濾波)。
- remake 自己的 `Ebiten` 呈現層——`cmd/fd2/main.go`/`internal/indexedmap/frame.go` 目前對 320×200
  的 indexed buffer 呼叫 `Scale(2,2)`(Ebiten 預設 `FilterNearest`,硬邊點放大),這是**remake 自訂
  的現代呈現選擇**,不是在「重現原版某個濾波演算法」。

### 10.3 對 remake 的意義

因為原版根本沒有任何縮放/內插濾波器可供比對,「remake 現在用 nearest 對不對」這個問題沒有一個
「原版真值」可以違反或吻合——**唯一有意義的判準是「像不像 mode 13h 從未被過濾過的原始硬邊像素」**,
而 `Scale(2,2)`(nearest)完全符合這個判準:它單純把每個原生像素複製成 2×2 色塊,不引入原版從未
存在過的模糊/漸層。若改用 bilinear/線性濾波,反而會產生原版**從未出現過**的暈染效果,是新增的失真
而不是「更貼近原版」。因此 `C:\Users\kg701\.claude\plans\hazy-crunching-liskov.md` 規劃中沿用
`Scale(2,2)`/nearest 的既有做法在這個 RE 事實基礎上是**正確選擇**,不需要改成 linear/bilinear 去
「貼近原版」——原版沒有這種東西可貼近。

**信心等級:高**——三條獨立證據鏈(顯示模式/DOS 擴充器性質、blit 原語逐指令反組譯無縮放運算、
AFM VM 直接寫 framebuffer)彼此不衝突,且都是早於本輪、經過反組譯確認的既有結論,本輪只是把它們
聚焦到「原版有沒有縮放 filter」這個具體問題上並下結論,未發現任何反例。
