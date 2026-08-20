# 10 — Sprite 繪製:敵 / 我方與狀態的動畫機制

> 同一個角色,在戰棋上分「己方 / 友軍 / 敵方」,還有受傷閃光、陰影、被選取等狀態。
> 這份文件討論**漢堂怎麼用同一份 sprite 資料、靠繪製時的變體做出敵我與狀態差異**。
> 第 3 輪反組譯 `FD2.EXE`(capstone)+ 單位結構(memory.md)整理。與 `06-animation-format.md`(codec)互補。

> 補(`31`):**地圖上的單位小人 = `FDICON.B24`**(1680 個 24×24 Q 版,sprite-RLE);本文的「24×24 場景單位解碼器 0x4EB52」即解它。FIGANI 是戰鬥演出全身大圖,兩者分工。

## 核心觀念:sprite 資料是「陣營中立」的,差異在繪製時做

關鍵證據:`FIGANI.DAT` 共 **264 個動畫**。角色約 32 名,每名約 8 種動作(待機 / 走 / 攻擊 / 受擊 /
施法 / 倒地…)→ 32×8 ≈ 256,與 264 吻合。**若敵 / 友 / 己各存一份,應是 3 倍(~800)**。
→ 同一份 sprite 不分陣營,**敵我差異是繪製時即時做出來的**(省記憶體,1990 年代 DOS 的務實設計)。

判定陣營 / 狀態的欄位在每個場上單位的 80-byte 結構(見 `03-…` / memory.md):

| 偏移 | 欄位 | 用途 |
|---|---|---|
| 0x0A | Z1 圖形 | 選哪一組 sprite |
| 0x0B | Z2 方向 | 面向(見下「面向」) |
| 0x0C | Z3 跑步動作 | 走路 / 動作幀 |
| 0x06 | **camp** | **00=敵方 01=友方 02=己方**；`0x10c50` 直接從 FDFIELD unit `b0` 寫入。舊「0x0E BB=陣營」已撤回 |
| 0x0F | FA 肖像 | 對話頭像 |
| 0x2A.. | 狀態旗標 | 中毒 / 麻痺 / 封咒 / 增益 → 影響閃色 |

## sprite 解碼器家族(`0x4E000`–`0x4F800`)= 同 codec、多種「著色變體」

全部共用 `06-…` 的 4 模式 RLE 文法(高 2 bit 模式 / 低 6 bit count),差別只在
**不透明像素「怎麼著色」**。反組譯出的變體:

| 入口 | 尺寸 | 不透明像素怎麼畫 | 推定用途 |
|---|---|---|---|
| `0x4EB52` / `0x4EAC6` | 24×24 | 經 **`[ebp+eax]` 調色 remap 表** | 場景單位,**依陣營換色**(換 remap 表) |
| `0x4EA40` | 24×24 | **算術變色** `add al,ah; and al,dh; add al,dl` | 整體加亮 / 變暗(夜戰 / 受選取?) |
| `0x4ED4C` | 24×24 | `rep movsb` 原色;mode11 填 `0x49` | 原色繪製(底色 0x49) |
| `0x4F43D` | **任意 W×H** | 色彩模式 = −1 → 原色 RLE | **戰鬥動畫(FIGANI)正常繪製** |
| `0x4F4FB` | 任意 | 全部不透明像素填 `ah`(單色) | **silhouette / 閃光**(受擊閃白、出現 / 消失特效) |
| `0x4F76F` / `0x4F7BB` | 任意(未壓縮) | `rep movsb` 矩形複製 | 存 / 還原畫面、清除 sprite(double buffer) |

`0x4F43D` 的色彩模式參數(stack `[ebp+0x1C]`):
- `= -1`:正常全彩 RLE(`0x4F48C` 分支)。
- `= 某 byte 值`:跳 `0x4F4FB`,把整個 sprite 畫成**該色的剪影**(`mov al,ah; rep stosb`),透明處仍透明。

> 即:**同一段動畫,正常播放用全彩;受傷瞬間用 silhouette 填白;陣營差異用 24×24 場景單位的 remap 表換色。**

## 敵 / 我方與狀態的「顏色」差異:調色 remap [已驗證]

場景單位(24×24)經 `[ebp+eax]` 查表上色:`eax` = 原始像素索引,`ebp` = 一張 **256-byte remap LUT**,
輸出 = `LUT[原始索引]`。同一份 sprite 套不同 LUT → 不同顏色 / 明暗。

**remap LUT 來源(已反組譯 + dump)**:
- 場景單位繪製 `0x13A00` 呼叫 `0x4EB52`(remap 解碼器);`[edx+3]==0xFF` → 無 remap(走 `0x4ECDA`),
  否則用 LUT。LUT 表指標 `[0x3A6D]`,於 `0x26AC6` 從 **`FDOTHER.DAT` 資源 #3** 載入。
- **`FDOTHER` 資源 #3 = `"LMI1"` 容器,內含 23 張 256-byte remap LUT**(magic `LMI1` + uint16 數量 + uint32 offset 表)。

**實測套用效果**(把同一騎士 sprite 套不同 LUT,`tools/dump_remap.py`):
- **LUT0 = 灰階** → 可作畫面上的灰階觀察；與 record `+5` bit7 的關聯仍是 caller/UI projection，不能回推舊 `AA=0x80` 欄位。
- LUT1–4 = 披風紅↔橙的色階、LUT15 = 藍色調、LUT20 = 褐色調 → 陣營 / 狀態 / 場景時段染色。

**LUT 索引怎麼選**(已反組譯 `0x13980`):LUT 指標 = `[0x3A6D] + idx*4 + 6`(吻合 LMI1 offset 表)。
`idx` 來自**全域狀態** `[0x3C1F]` 經一張表(linear `0x1A97`)轉出——即這條地形繪製路徑的 LUT 是
**全域色調**(場景 / 時段 tint、已行動變灰之類),不是逐 unit 直接讀 BB。圖塊本身的繪製旗標來自
`[0x3A69] + 地形索引*4`(bit3 / bit7 控制)。

> [已驗證] remap 機制 + 23 張 LUT 資料 + LUT 索引來源(全域狀態表)。
> [推定/待續] 戰鬥單位(非地形)的「敵我陣營染色」可能走另一繪製路徑或固定 LUT 索引,
> 與此地形全域 tint 路徑分開;確切 camp→LUT 仍待對到單位繪製碼。

## 面向(方向)

解碼器全部 `inc edi`(順向寫),**家族內沒有水平鏡像(`dec edi` / `std` 反向)的 RLE 變體**。
→ 面向不是靠鏡像翻轉,而是**用不同方向的幀**:單位結構 `Z2 方向`(0x0B)選方向、`Z3`(0x0C)選動作幀,
對應到該角色 sprite 組裡不同的幀。(戰鬥動畫 FIGANI 多為單一面向的攻擊演出;場景走動才需多方向。)

[推定] 待確認:各角色的 24×24 場景 sprite 是否每方向各存一組幀(對照 FIGANI / 場景 sprite 容器數量)。

## 狀態效果

- **受擊閃光**:`0x4F4FB` silhouette,填白(或填某色)1–2 幀。
- **陰影**:RLE **mode 01(dither)**——隔位寫、佔 2×count 寬,半透明點陣(地面影子,已於騎士動畫驗證)。
- **中毒 / 麻痺 / 增益**(狀態旗標 0x2A..):推定用算術變色變體(`0x4EA40`)或換 remap 表做色調(綠 / 黃閃),待確認。

## 重製對應(SDL2 / Ebiten)

| 原版機制 | 現代做法 |
|---|---|
| 陣營 remap 表 | 每陣營一張 palette LUT;或 shader 依 team color 重映射索引 |
| silhouette 填色 | 用 tint / flat-color shader,保留 alpha |
| dither 陰影 | 半透明 sprite 或 alpha-blend 影子 |
| 多方向幀 | 維持原幀;或水平 flip(現代可直接鏡像,省幀) |

## 待辦(後輪)
- 反組譯場景單位繪製呼叫端,確認「BB 陣營 → remap 表」對應,dump 各陣營 remap 表還原實際配色。
- 確認方向幀的組織(每方向幀組 vs 共用)。
- 把 264 個 FIGANI 動畫對應到「角色 × 動作」,標出敵 / 我共用關係。

## 2026-08-19 補充:native map HUD「逐章 view/gates/anchor」通用機制稽核

> 對應 `91-worklist.md`「**native terrain/unit map HUD (`0x1acf3`)**」項(項目文字所在行號因檔案增修漂移,
> 現行約在 L1121,内容與任務要求核對的「L966」為同一項)。本節只記錄**這輪新反組譯出的兩塊證據**——
> `0x12c0d` 的完整 raw predicate/順序,以及「gate 是否逐章各自寫」的靜態呼叫鏈稽核;HUD 六個 subpass
> 本身(panel/terrain/AP/DP/icon/HP)之前已在 `91-worklist.md` 與 `56-fd2-remake-sdd.md` 閉合,不重複。
> 方法:純靜態 Ghidra headless(`analyzeHeadless -readOnly`,`FD2Analysis3` project,自寫 probe script,
> 不碰 DOSBox-X/WSL2),`getFunctionContaining`/`getReferencesTo` 取函式邊界與呼叫端,與既有 `FD2_disasm_full.txt`
> 交叉核對位址,未使用 `tools/disasm_le.py`(已知 LE 分頁解析 bug)。

### 1. `0x12c0d` exact raw lookup predicate/order [已閉合]

完整反組譯 `0x12c0d`(函式本體 `0x12c0d..0x12c5f`,`push 0x10; call 0x3702f` 是標準 stack-check prologue):

```
0x12c19  mov ebx,[0x53a45]        ; 戰場單位陣列基底(0x50-byte/單位,同 doc25/26/35 已證)
0x12c1f  xor esi,esi              ; esi = 掃描索引,從 0 起
0x12c27  cmp esi,[0x53beb]        ; esi >= count → 找不到,跳 0x12c58 回傳 -1
0x12c2f  movzx edx,byte[ebx]      ; record+0 = 單位 X 格(doc50 §「單位結構」已證 +0=X格)
0x12c32  movzx eax,byte[ebx+1]    ; record+1 = 單位 Y 格(+1=Y格)
0x12c36  cmp edx,[0x53ab1]        ; X 是否等於 search-X
0x12c3c  jnz 0x12c23              ; 不等 → ebx+=0x50, esi++, 繼續下一筆
0x12c3e  cmp eax,[0x53ab5]        ; Y 是否等於 search-Y
0x12c44  jnz 0x12c23              ; 不等 → 繼續下一筆
0x12c46  push esi; call 0x34894   ; NativeRecordByte5Bit0(esi)(doc26 已證 = byte[idx*0x50+5]&1)
0x12c4f  test eax,eax
0x12c51  jnz 0x12c23              ; predicate 非 0(bit0=1)→ 拒絕,繼續下一筆
0x12c53  mov eax,esi; ret         ; 三條件全過 → 回傳該筆 index
0x12c58  mov eax,-1; ret          ; 掃完仍無 → 回傳 -1
```

**Predicate/順序(逐字):** 由 index 0 起遞增線性掃描 `[0x53a45]`(count=`[0x53beb]`),對每筆先比對
`record+0==[0x53ab1]`(X),不等即跳下一筆;相等才比對 `record+1==[0x53ab5]`(Y),不等跳下一筆;
X/Y 都相等才呼叫共用 predicate `0x34894`(=`byte[idx*0x50+5]&1`),非 0(bit0 已設)則仍跳下一筆。
三個條件全部通過的**第一筆**(最小 index)勝出,回傳其 index;整個陣列掃完仍無匹配回傳 `-1`。
三個條件之間是嚴格 AND、短路序(X→Y→predicate),沒有平手/優先權邏輯。

**`[0x53ab1]`/`[0x53ab5]` 身分澄清(避免與另一組全域混淆):** 這對 search-X/Y **不是**
`91-worklist.md`/`58-remake-live-verification-log.md` 已證的持久 anchor 游標對 `[0x53ab9]`/`[0x53abd]`
(那對只由 `0x1ad2a..0x1ad5f` 的兩條 branch 改寫,見 `91-worklist.md` 「native HUD persistent anchor branch」)。
`58-remake-live-verification-log.md`(2026-08-18,`#112/#118`)已完整反組譯攝影機平移函式 `0x135dd`,
證實它逐格步進寫 `[0x53aa9]/[0x53aad]`(目標鏡頭 X/Y)與 `[0x53ab1]/[0x53ab5]`,**完全不碰**
`[0x53ab9]/[0x53abd]`。故 `0x12c0d` 的 search-X/Y 是**攝影機目前平移到的格子座標**,不是持久
anchor 游標——`56-fd2-remake-sdd.md`/`SESSION-HANDOFF-2026-07-06.md` 稱它「`0x12c0d(cursor)`」
是口語簡稱(正常玩法下鏡頭確實跟隨選取游標移動,語意上大致重合),但底層是兩組不同全域,寫入端也不同函式,
不能互相代換或合併成同一個變數處理。

**`0x12c0d` 不是 HUD 專用函式**:對 `0x12c0d` 進入點做 `getReferencesTo`,共 **9** 個直接呼叫點,
分屬 6 個不同 caller 函式——`0x117e7`(×2)、`0x1741c`、`0x176b4`、`0x179d5`、`0x18d8c`(`13-battle-menu-system.md`
已證的「action-ring dispatcher」,指令環攻擊呼叫鏈 `0x18d8c→0x14818→0x115b6→0x12c0d→…`)、
**`0x1acf3` 自己**(HUD compositor 對 `0x12c0d` 的呼叫,即 worklist「native HUD unit-icon subpass」項)、
`0x1bbdc`、`0x149f8`(`13-battle-menu-system.md` 已證的「target-candidate builder」)。
即:同一顆「掃單位陣列找格子座標命中且 bit0 未設的第一筆」raw primitive,同時被戰鬥指令目標選取
與地圖 HUD 共用,佐證它是引擎層通用工具,不是為某一章或某個畫面寫的專屬碼。

### 2. `0x51aab`/`0x51aac` raw gate:通用機制稽核結果 [已確認為通用,非逐章]

對全程式掃出的每一個 `0x51aab`/`0x51aac` 讀寫點(`FD2_disasm_full.txt` 逐一核對: `0x10436`、
`0x135b4`/`0x135d4`、`0x170ba`/`0x17163`/`0x1726b`/`0x17277`、`0x25dde`/`0x25dea`、
`0x26080`/`0x260de`/`0x26112`、`0x29774`、`0x299aa`)做 `getFunctionContaining` 定出擁有函式,
再對每個擁有函式的入口做 `getReferencesTo` 取呼叫端,結果:

| gate 讀寫位址 | 擁有函式 | 呼叫端(全部) |
|---|---|---|
| `0x10436` | `FUN_00010010`(`0x10010..0x1061f`) | `0x1a251`、`0x26130` |
| `0x135b4`/`0x135d4` | `FUN_00013565`(`0x13565..0x135dc`) | `0x11985` |
| `0x170ba`/`0x17163`/`0x1726b`/`0x17277` | `FUN_00016f55`(`0x16f55..0x1728b`) | `0x118c1` |
| `0x25dde`/`0x25dea` | `FUN_00025bf4`(`0x25bf4..0x25eba`) | `0x460dc` |
| `0x26080`/`0x260de`/`0x26112` | `FUN_00025ebb`(`0x25ebb..0x26151`) | `0x25dbd` |
| `0x29774` | `FUN_0002968d`(`0x2968d..0x2986e`) | `0x26331`、`0x2940e` |
| `0x299aa` | `FUN_0002986f`(`0x2986f..0x29ab1`) | `0x29424` |

**每個擁有函式只有 1–2 個固定呼叫端**,且沒有任何一個呼叫端落在既有 KB 已定案的「逐章 handler
dispatch 位址帶」(`26-per-chapter-event-handlers.md` 記錄的 ch15/16/17 post-handler 都在
`0x239bd`/`0x23a0a`/`0x23d39` 一帶)。反而:

- `FUN_00013565`(`0x13565`)、`FUN_00016f55`(`0x16f55`)兩個函式的函式體**各自內含**
  `91-worklist.md`「0x1a30b shared-caller correction」項已證的 3 個共用呼叫點之 1 或 2 個
  (`0x135c5` 落在 `0x13565..0x135dc` 內;`0x17154`/`0x17272` 都落在 `0x16f55..0x1728b` 內)——
  也就是說,這兩個函式本身就是「gate B 關 → 呼叫 `0x1a30b`(NativeBattleEntryStep 共用 primitive)
  → gate B 開」的**通用 wrapper**,doc91 早已證實 `0x1a30b` 不分章節共用。
- `FUN_00025bf4`(`0x25bf4`)經獨立交叉核對就是 `58-remake-live-verification-log.md`(2026-08-19,
  「問題2核心」節)已完整反組譯 711 條指令、確認名稱為**戰役主迴圈**的函式:它以
  `[0x53c03]*4+0x51de9` 讀 dispatch 表**無條件**(無 gate)呼叫全部 30 章的 post-battle handler。
  即 ch01..ch30 的章節轉換全部通過這**同一個**函式,而這個函式正是 `0x25dde`/`0x25dea` 兩個
  gate B 寫入點的擁有者。
- 另外三個叢集(`FUN_00025ebb`/`FUN_0002968d`/`FUN_0002986f`,位址範圍 `0x25ebb..0x29ab1`)
  彼此呼叫端也都只有 1–2 個,且都在同一個 `0x25xxx–0x29xxx` 引擎子系統區段內互相呼叫,沒有
  發現任何一個呼叫端數量隨章節數增加(如 30 個不同 caller)的模式。

**結論:通用機制已確認存在,不需要逐章特判程式碼。** 全部 `0x51aab`/`0x51aac` 讀寫都發生在
共用引擎層(battle-turn wrapper + 戰役主迴圈 + 相鄰場景轉換子系統),沒有任何一個 gate 寫入點
是被 30 個各自獨立的 per-chapter caller 呼叫;`worklist` 已記錄的「inherited HUD state vertical
slice」bullet(`native_map_hud_inherited`)本身就已經用同一條 loader 路徑覆蓋 ch01/ch26/ch27——
三章横跨全遊戲前段/後段,若真的逐章各自寫 code 理應在這三章間出現差異,但没有,這與本輪的
呼叫鏈稽核互相印證。

**因此 worklist 該項「其餘 ch02+ 缺逐章 view/gates/anchor 來源」的殘留範圍,實際性質是
「資料」而非「程式碼」**:每章戰鬥入口的 gate A(save-persistent)/anchor/camera/cursor
**初值**仍需要對每章分別確認其來源(繼承自 `FD2.SAV`、或由該章 pre-handler 顯式寫入),
但不需要為每章重新反組譯一套獨立的 gate/HUD 呼叫邏輯——共用機制已經是同一份程式碼。
本輪未逐章跑完 30 章的初值來源盤點(超出單輪範圍,且沒有 DOSBox 320×200 pixel oracle 可供
逐章截圖核對,原文早已標註此限制仍未解除);已確認的三章(ch01/ch26/ch27)之外,其餘 27 章
的「初值 from save vs from pre-handler」仍待後續個別確認,但已知**不必再懷疑「是否存在另一套
機制」**。

**L966(現行行號約 1121)完成度更新**:
- `0x12c0d` exact raw lookup predicate/order → **已閉合**(見上,含 9 個呼叫點的共用性佐證)。
- 「其餘 ch02+ 缺逐章 view/gates/anchor 來源」→ **通用機制已確認存在**(gate 寫入端與
  `0x1acf3`/`0x12c0d`/`0x1a30b` 全部是共用引擎碼,非逐章特判);殘留範圍縮小為**純資料層**
  的逐章初值來源盤點,已核對 ch01/ch26/ch27 三章(沿用既有 `native_map_hud_inherited`),
  其餘 27 章的初值來源尚未逐一確認,但不再需要逐章反組譯新的 code path。
- 原版 DOSBox 320×200 HUD pixel oracle 仍缺,不受本輪影響,維持 open。
