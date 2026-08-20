# 31 — 地圖單位 Sprite:FDICON Q 版小人 + 待機動畫

> 戰場地圖上的單位(原版那種 Q 版大頭小人)= **`FDICON.B24`** —— 1680 個 24×24 sprite。
> 這跟 `FIGANI`(戰鬥演出的全身大圖)是兩套東西:**地圖走 FDICON,戰鬥動畫走 FIGANI**。
> 本篇記錄 FDICON 格式、分組、解碼、與 remake 接法。用**原版實機截圖當 oracle**(rulebook 64)驗證。

## 0. 一個差點殘留的誤判(教訓)

`FDICON.B24`(624010 bytes,無 `LLLLLL` 外殼)早先被誤用「不透明 bg-RLE」模型解 → 全是橫條亂圖,於是一度想把「1680 個 24×24」這個斷言改成「待確認」。
**但斷言是對的,錯的是解碼方法**:FDICON 與 FDSHAP 都使用 native four-mode RLE ABI；FDICON 是含透明的單位 sprite，FDSHAP 也可含 mode-3 span，但原版 renderer 對兩者的 raw/LUT 分支不同。換對 four-mode 解碼器立刻解出 Q 版小人。
→ 教訓:**解碼失敗 ≠ 斷言錯,先換解碼器/方法再質疑事實**(rulebook 62/63)。

## 1. 格式

```
+0  u16 tileW   = 0x18 (24)
+2  u16 tileH   = 0x18 (24)
+4  u16 count   = 0x0690 (1680)
+6  u32[count]  offset 表(相對檔頭)
各 tile:sprite 4-mode RLE(高 2 bit=模式:色run/dither/literal/透明;低 6 bit=count−1)
        透明 = index 0
```
header 與 FDSHAP tileset 同骨架(尺寸+count+offset 表)，且兩者都可用同一 four-mode RLE ABI 解讀；差別是資產用途與 renderer branch：FDICON 走 unit raw/palette-band，FDSHAP 依 FDFIELD entry 可走 raw 或 destination-LUT compositor。

## 2. 分組:每角色 12 sprite = 4 方向 × 3 待機幀 [驗]

實測組 0(index 0–11):
```
 0  1  2   面向【下】3 幀(站 / 抬左手 / 抬右手)
 3  4  5   面向【左】3 幀
 6  7  8   面向【上】3 幀(背面)
 9 10 11   面向【右】3 幀
```
**3 幀循環 = 待機時手腳微擺的動感**(使用者指出的「手會左右移動」)。
角色組 = `index // 12`。已辨識:組 0=紅帽主角、1=藍帽、2=灰甲機器人、9(108–119)=紅髮主角、8(96–107)=綠衣盜賊…(共約 140 組,涵蓋全角色 + 敵兵 + 怪物 + 機器人)。

## 3. FDICON(地圖) vs FIGANI(戰鬥)

| | FDICON.B24 | FIGANI.DAT |
|---|---|---|
| 用途 | **地圖上的單位小人** | 戰鬥演出(攻擊/受擊)全身動畫 |
| 尺寸 | 24×24(正好一格) | 80–175(大圖) |
| 風格 | Q 版大頭 | 寫實全身 |
| 數量 | 1680(≈140 組×12) | 264 動畫 / 2118 幀 |
| codec | sprite 4-mode RLE | 同 codec(參數化 0x4F43D) |

> doc 10 提的「24×24 場景單位解碼器 0x4EB52」即對應 FDICON;FIGANI 用 0x4F43D。地圖顯示 FDICON 小人,選單位/進入戰鬥才切 FIGANI 大圖。

## 4. 工具

- `tools/decode_fdicon.py`:解全 1680 sprite(sprite-RLE,index 0 透明)→ 透明 PNG;`--overview` 出標 index 的總覽(看分組)。
- `tools/export_sprites.py`:對指定**角色組**導出「面向下」3 待機幀 → `remake/assets/sprites/fig_<grp>_f<0..2>.png`。
- `tools/export_units.py`:保留 legacy `fig` compatibility 欄位。它不是已閉合的 FDICON selector source；真正的
  runtime `unit+2` producer 仍在追查。

## 5. remake 接法

- 引擎 `loadSprites()` 載 `fig_<grp>_f*.png` 分組;`drawUnitSprite()` 用 `(g.frame/12)%3` 循環待機幀,**24×24 直貼格**(略上移讓單位站在格上),陣營色腳標 + HP bar,已行動套灰（對映原版已驗證 record `+5 bit7=0x80`，不是舊 AA `+0x0D` 標記；§6 / doc 27）。
- 原版實機截圖與 DATO face 可做單一角色素材的 oracle，但不能單獨證明 runtime map selector。battle FIGANI
  走另一條已閉合的 `unit+7×3` 路徑（doc06）。

## 6. sprite index 公式（已驗證）；source identity 待閉合

不靠猜測,**反組譯戰場單位繪製碼(0x128e0–0x12932)鎖死了公式**:

```asm
0x12823  mov  eax,[0x53a45]        ; 單位陣列基底
0x12831  movzx edi, byte[eax+2]    ; raw map selector
0x12835  movzx esi, byte[eax+3]    ; 方向(0..3)
0x1291e  imul edi, edi, 0xc        ; 組 × 12
0x12921  mov eax,esi; shl 2; sub esi   ; 方向 × 3
0x12928  add eax, edi              ; 組×12 + 方向×3
0x1292a  add eax, edx              ; + cycle（由全域 idle/moving phase 選出）
0x1292c  mov edx,[0x53a61]         ; FDICON sprite 指標表
0x12932  mov eax,[edx + eax*4]     ; sprite[index]
```

→ **FDICON sprite index = slot × 12 + 方向 × 3 + cycle**（公式已驗證）；slot 為 `unit[+2]`。第三項不是 runtime `+4` 或 `+0x26`：`+4` 是沿方向的次格 placement offset；`+4==0` 選 global idle phase `0x3c0b`、非零選 moving phase `0x3c07`，phase 3 會正規化為 1，而 `+0x26!=0` 只強制 cycle 0 並加上已證實的全域繪製偏移。`0x10c50→0x11019` 以 FDFIELD `b0` 查全域 raw-key table；只有新 key 才用 caller archive pointer 建十二指標 block，回傳 cache slot 寫入 `unit+2`。它不是直接 copy 的角色／肖像 byte。

> **撤回全域 identity assertion（2026-07-26）**：角色表、DATO、FDICON 素材與若干玩家 roster 的數值相同，
> 只能作為素材觀察，不能證明 `unit+2 = character id = portrait`。完整 constructor trace 已證實 FDFIELD
> `b1→unit+7`，而 scripted FDFIELD constructor 已閉合 `b0→0x11019→unit+2 cache slot`：`b0` 亦寫
> native camp `+6`（敵0／友1／己2），不是角色／portrait byte。玩家 persistent roster 則有獨立的 `+7`
> source path；兩者共享 cache ABI，不能 alias。
> 因此敵方、玩家及轉職都不得由「恆等」推導 map group，`fig` 僅保留 compatibility approximation。`unit+7`
> 的 battle FIGANI/DATO path 也不能反推 `unit+2`。先前關於特定轉職 group、龍人例外與 DATO_067 的敘述皆
> 不再作為 renderer/exporter 的證據。

> **玩家初始 record 的狹窄例外（2026-07-26）**：`JOIN` 的 `0x112a5(join_id)` 建立 persistent
> 0x50-byte record 時，直接將同一 `join_id` 寫入 `+7` 與 `+8`；`0x33499` 已證實 `+8` 是
> roster character-ID lookup。之後 `0x10a77` 讀 copied persistent `+7` 當 `0x11019` key。因此新加入
> 的玩家 record **初始** map key 等於 character ID。這是特定 writer 的資料流，不是 FDFIELD/NPC 的
> identity rule。它也不是 immutable：class-change flow `0x314a7..0x3157a` 以 selected roster slot
> 定位 live `0x53a45+slot×0x50`，最後把 UI-selected raw byte 寫回 `+7`（同時重算 `+0x20`）。因此
> 「join-id 相等」只適用於 fresh record；target byte 的高階名稱仍須另追。其 persistence ABI 已知：戰後
> `0x11506` 以 `+8` 配對後完整 copy 0x50 bytes runtime→persistent，故只要 flow 呼叫 `sync_party`，這個
> `+7` mutation 就會被保存；class-change flow 是否在同一 town interaction 立刻進該 post handler 仍不可假定。

| runtime byte | 已證實的狹窄意義 | evidence |
|---|---|---|
| `unit+2` | `0x11019` 回傳的 FDICON cache slot；不可命名為角色／肖像／素材組 | `0x10a92..0x10aa2`、`0x10c50→0x11019`、`0x12831` |
| `unit+3` | map pose/direction selector (`0..3`) | `0x12835`、`pose×3` |
| `unit+4` | movement placement offset；不是 animation frame | `0x127e0` placement branch |
| `unit+6` | native camp raw byte（FDFIELD 路徑的 `b0`） | `0x10ef1`、target predicates |
| `unit+7` | battle FIGANI selector（FDFIELD 路徑的 `b1`） | `0x10ef8`、`0x287b5..0x2884c` |
| index | `slot×12 + pose×3 + cycle` | `0x1291e` |

> **刪除舊表的錯誤 offset/identity 對應**：它把另一份結構標記混入 runtime 0x50-byte
> battle roster，並把觀察到的相等值升格為欄位 alias。今後僅以以上直接讀寫為準；未閉合欄位不另命名。

## 7. sprite & face 統一 authoring 系統（remake 擴充設計，非原版 ABI）

remake 可把自創角色做成**單一資料表**，明確配置 face 與 sprite；這是便利的
authoring schema，不表示原版 raw id、DATO、FDICON cache slot 數值恆等。加新人加一筆:

```jsonc
// characters.json — 角色 id → 頭像 + 地圖 sprite + 數值
{
  "0":   { "name":"索爾",  "face":"dato/000_m*"   /* 4 嘴型幀 */, "sprite":"fdicon/grp000", "stats":{...} },
  "3":   { "name":"哈瓦特", "face":"dato/003_m*", "sprite":"fdicon/grp003" },
  "68":  { "name":"一般士兵","face":"dato/068_m*", "sprite":"fdicon/grp068" },
  // …原版 id 0–136 = 原版角色(DATO 頭像 137 / FDICON 組 140)
  "200": { "name":"自創英雄","face":"custom/hero_m*" /* 自繪也要 4 嘴型 */,"sprite":"custom/hero_grp", "new":true }
}
```
- **face**:對話頭像 = DATO_N 的 **4 嘴型幀**(`DATO_N_m0~m3`,80×80,本機 `extracted/portraits/`)。
  **對話時循環播放做嘴巴開合 + 眨眼,不是單張靜圖**(漢堂讓對話有生氣的手法)。characters.json 的 `face` 指向「一組 4 幀」。
- **sprite**:地圖 12 幀(FDICON 組 N=4方向×3幀;或自繪同規格)

> 新引擎可自行定義角色 asset id；這是 remake extension schema，**不是**原版 runtime map-selector
> provenance。原版 `unit+2` 與 DATO/FIGANI field 的關係仍須由 constructor/resource trace 決定。
- **加新人**:分配未用 id(≥137)、給 face PNG + 12 幀 sprite + 數值 → 引擎自動吃,事件/招募(doc 26/28 `roster_has`)直接用該 id。
- **角色總覽**:`tools/char_summary.py` → 本機 character_summary.png(140 組 sprite+face 並排,統一編號全圖佐證、加新人看缺號)。
- 工具:`decode_fdicon.py`(導原版組)、`decode_dato.py`(導原版頭像)、`export_units.py`（legacy `fig` compatibility）已就緒；
  不得由此自動生成原版 selector mapping。

→ 這把「炎龍 remake」從「複刻」升級成**可擴角色的平台**:配合可擴展事件系統(doc 29),能做原版沒有的角色 + 劇情 + 戰役。

## 8. 受阻 / 待校

- **[待閉合] original map-selector presentation adapter**：`0x127e0` 的公式和 `unit+2` read 已證實；
  `0x11019` 已證實為全域 raw-key cache，且 player/scripted loaders 都開啟 `FDICON.B24`。但 indexed
  framebuffer 的 layer/palette schedule 尚未接到 GUI，故不能由角色表、DATO id、FDICON 檔案序號或轉職表直接
  定 legacy `Fig`。保留玩家/怪物素材的個別對照資料，但不把它當 exporter 或 runtime mapping。
- **[線索] 廢案人物**:FDICON 有些組**沒畫滿 12 格**(未採用角色,僅部分方向/幀);因 sprite 用「組×12 + 方向×3 + 幀」定位,廢案組仍佔 12 格 stride(部分空/重複)。未來可挖廢案角色來用(加新人素材庫)。
- **[M2 待做]** 對話框**嘴型動畫**:DATO_N 的 m0~m3 對話時播放(嘴開合 + 眨眼)。哪幀=閉嘴/開嘴/眨眼、播放節奏(隨文字推進?固定循環?)待反組譯文字渲染器(0x16D00 區,doc 14)確認;M2 對話層實作。
- 方向:目前只導「面向下」待機;4 方向(走動/面敵)待加。
- 戰鬥演出切 FIGANI 大圖:M1 戰鬥動畫階段再接。

> 相關:doc 10(sprite 繪製/陣營著色)· doc 06(FIGANI 動畫)· doc 27(byte[+5] 狀態旗標)· doc 30(工作拆解)。工具:`tools/decode_fdicon.py`、`export_sprites.py`。素材:`extracted/fdicon/`(本機,1680 PNG)。

## 9. `0x22253` native unit presentation choreography(27-present indexed reveal)與 `unit_present` metadata 缺口根因(2026-08-19)

> 這條與 §6 的 FDICON per-unit sprite 選幀公式是**兩套不同機制**:§6 是「每幀畫哪張 24×24 sprite」,
> 本節是「單位在地圖上瞬間**離場/進場/位移**時,320×192 indexed 雙緩衝要怎麼演出」——後者是
> `worklist.md` 91 檔 L852/874/898 三項圍繞的同一缺口,本節逐一釐清。

### 9.1 反組譯鏈路(位址+證據,呼應 91 檔 1026–1053 行 `[x]`/`[~]` 項)

```
0x22253(unitSlot,newX,newY,visualX,visualY)   ; 5 引數 ABI,尾端寫 record[+0]=newX、record[+1]=newY
  ├─ 0x11eee                                  ; 地形快照進 0x25680-byte 工作緩衝(無 unit/foreground/HUD)
  ├─ 0x22470  intro (11 present)               ; FDOTHER#6 "LMI1" bank entries 0x72..0x7c,逐張 blit→
  │                                             ; 0x127a9 object redraw→320×192 present→1 tick
  │                                             ; 目的地位址 = 0x8088+24*(x-camX)+0x1c8*24*(y-camY)+0x1c8
  ├─ 0x22547  contract (6 present,10ms/幀)      ; FDOTHER#3 descriptor bank entries 5→0(倒序);
  │                                             ; 呼 0x22046 做「兩次 radial LUT remap + 置中矩形 LUT remap」
  │                                             ; 最後一幀多等 2 tick
  └─ 0x22656  release (10 present,1 tick/幀)     ; 同一 0x22046 幾何,entries 0→9,contract 之逆
```

- `0x22046` 幾何(RE-22046-INDEXED-PASS-SEQUENCE / 0x24618 pass-range 條目):**radius 固定 11、scale 固定 16**,
  中心 `(centerX,centerY) = (24*[0x53AB9]+12, 24*[0x53ABD]+15)`;`[0x53AB9]/[0x53ABD]` 已由 doc14 §(對話框
  誤判修正)證實為 **camera-relative 可視 cursor column/row**,非對話框寬高。`startY = trunc((24*[0x53ABD]+15)/5) * lutIndex`
  只在 contract 幀變化,release 幀固定從 row 0 開始。兩次 radial remap 之間**必須**插入一次
  `0x127a9`(camera-relative object redraw,寫 `0x53a49`),不可合併或省略(已由 IDA 9.4 覆核)。
- `0x22253` 尾端座標寫入已由 **官方 IDA 9.4** 閉合(RE-COMMAND23-COORD-WRITE):`record[+0]=a13`、`record[+1]=a14`,
  即「新座標」在整段 27-present 演出**跑完後**才真正寫進單位紀錄——演出期間單位視覺位置(`visualX/visualY`)
  與最終邏輯座標(`newX/newY`)是分離的兩組引數,這解釋了為何三個 caller 都要傳「離場用 0xff/0xff」與
  「進場用真實座標」兩組不同 pair。

### 9.2 `unit_present` metadata「不完整」的根因——不是反組譯不夠,是資料模型過時

`remake/internal/campaign/campaign.go` 目前**同時存在兩個** schema:

```go
// 舊 schema(仍保留於 JSON tag `unit_present`,但已被拒絕編譯):
type HandlerUnitPresent struct {
    Slot int; X int; Y int
    Frames int; FrameDelayMs int; TailTicks int   // "六幀"模型
}

// 新 schema(0x33f78 wrapper 的真實 ABI,可編譯):
type NativeStagingPresent struct {
    Slot int; X int; Y int; FocusX int; FocusY int
}
```

`HandlerUnitPresent` 是**早期**(尚未追出 11+6+10=27-present 完整鏈路時)對 `0x22253` 的第一版猜測——
以為它是「單一 N 幀+固定延遲+尾端 tick」的簡單演出。後來(`RE-22046-INDEXED-PASS-SEQUENCE` 等輪)反組譯
證實真實結構是三段、each 段有各自 present 數與延遲單位(ms vs tick),`Frames/FrameDelayMs/TailTicks` 三個
欄位**表達不了**這個結構,`handler_compile.go` 因此**刻意讓舊 schema 編譯失敗**(見 `campaign.go:293-296`
註解「later direct trace found 11+6+10 presentation phases, so this six-frame schema is deliberately
rejected」)。這就是「既有 `unit_present` metadata 不完整」的**確切根因**:不是欄位缺漏可以直接補,
而是整個資料形狀(shape)已被證明對不上真實鏈路,需要換成 `NativeStagingPresent`(已完成,對應 0x33f78
wrapper 的 5 引數)。

`NativeStagingPresent` 本身**可以編譯**(`handler_compile.go:960-961` 已將 ch29 pre 的 7 個 `0x33f78` call-site
lower 成 `native_staging_present` beat),但 `cmd/fd2/main.go` 對兩個 op 都在 runtime 端硬性拒絕:

```go
// main.go:1050-1059 —— 舊 "unit_present" op(即便編譯到也擋)
g.loadErr = "beat unit_present: native 0x22253 renderer adapter未完成"

// main.go:1119-1128 —— 新 "native_staging_present" op(0x33f78 已知七呼叫點)
g.loadErr = "beat native_staging_present: native 0x22253 renderer adapter未完成"
```

`beatrunner_test.go:425` 的 `TestBeatNativeStagingPresentFailsClosedWithoutRendererAdapter` 把這個
fail-closed 行為固定成回歸測試——即**這是刻意設計**,不是遺漏。

### 9.3 已完成 vs 仍缺:精確的 fail-closed 邊界

**已完成且有回歸測試**(這輪確認,非本輪新做):
- `remake/internal/fdother/unit_present_schedule.go`(10 個測試,`unit_present_schedule_test.go`):
  `NativeUnitPresentByteOrigin`(intro 目的地位址公式)、`NativeUnitPresentContractStartY`、
  `NativeUnitPresentLUTPass`(0x22046 幾何)、`BlitNativeUnitPresentLMI`/`RunNativeUnitPresentLMIIntro`
  (11-present intro)、`RunNativeUnitPresentLUTFrame`(contract/release 共用的 snapshot-restore-remap-present
  交易)、`NativeUnitPresentSchedule`/`ValidateNativeUnitPresentSchedule`(27-present 順序的機器可讀 schedule)。
- `remake/internal/indexedmap/frame.go`(20 個測試,`frame_test.go`):
  `ComposeNativeUnitPresentTerrainSnapshot`、`RedrawNativeUnitPresentObjects`、
  `CopyNativeUnitPresentViewport`、`ComposeNativeUnitPresentIntroFrame`、`ComposeNativeUnitPresentLUTSnapshot`、
  `ComposeNativeUnitPresentLUTFrame`、`ComposeNativeUnitPresentStripBridge`、`NativeUnitPresentStripLayoutFor`。
  這些函式把 §9.1 的三段鏈路組成可呼叫、有 preflight/fail-closed 邊界的 Go API,且都用私有 clone
  做交易(拒絕時不改 caller buffer)。

→ 也就是說,**幾何/緩衝區交易本身已經反組譯完整且已實作**,`91` 檔 1046–1051 行說的「不再籠統寫成『沒有
indexed buffer』」是準確的。

**仍缺、且是目前唯一的 fail-closed 觸發點**:`cmd/fd2` 沒有任何 Ebiten 端的「job/state machine」把
§9.1 的 27-present schedule 逐幀跑起來、畫到螢幕上。作為對照,同性質的 `0x24618`(`indexed_transition`
op)**已經有**這樣的 driver ——`cmd/fd2/native_indexed_transition.go` 的 `nativeIndexedTransitionJob`
(phase 狀態機:`nativeTransitionPass`→`nativeTransitionTail`→`nativeTransitionPalette`)、
`startNativeIndexedTransition`/`stepNativeIndexedTransition`/`drawNativeIndexedTransition`,並在
`main.go` 的 `Update()`(6429 行 `g.stepNativeIndexedTransition()`)、`Draw()`(6898 行
`g.drawNativeIndexedTransition(screen)`)與 beat runner(1060-1068 行 `case "indexed_transition"`)
三處都已接線。`0x22253` 完全沒有這一層對應物——搜尋整個 `cmd/fd2` 找不到任何
`stagingPresent`/`unitPresentJob` 之類的結構或呼叫。這確認了「個別 caller 視覺語意 / descriptor buffer
adapter / Ebiten adapter 仍缺」的說法精確落在**這一層**,而不是落在幾何數學或緩衝區交易上。

### 9.4 三個已知 caller 的視覺語意(逐一補上,盡力而為)

`0x22253` 在全 EXE 只有三處已知呼叫鏈(RE-COMMAND23-CALLER-SCOPE-CORRECTION 已否定「command-23 專屬」的
舊假設):

1. **`0x33f78`(ch29 staging wrapper)→ `native_staging_present`**:raw push-order `[y,x,slot]`,
   先呼 `0x12cea(slot,x)` 把鏡頭 focus 到該單位所在格,再呼 `0x22253(slot,x,y,x,y)`——`NewX/NewY` 與
   `VisualX/VisualY` **相同**,即這個 caller 沒有「假離場座標」,是單純的**鏡頭跟拍 + 單位就地演出**
   (7 個 call-site 均在 ch29 pre-battle handler,對應終局戰前把角色一一擺上場的分鏡)。視覺語意:
   **鏡頭聚焦某單位所在格,播放一次完整 27-present 進場特效(indexed radial reveal)**。

2. **`0x2218A→0x22253`(native command 23 / item type23 relocation)**:已由 `RE-ITEM-TYPE23-RELOCATION`
   閉合觸發條件——**戰鬥中道具 ID101** 的效果,gate 是目標 raw identity `+8==24` 且 max MP `+0x46>=20`,
   花費 20 MP,對第一目標生效。呼叫 `0x22253` **兩次**:第一次把目標單位 `+0/+1` 寫 `0xff/0xff`
   (visual anchor 也是 `0xff/0xff`,即「先讓單位在畫面上消失/離場」),第二次以
   **destination cursor globals `[0x51CF9]/[0x51CFD]`** 當新座標寫入(即「玩家用游標選的目的地格」)。
   視覺語意:**戰鬥中的瞬間移動(teleport)道具效果**——先播一次 27-present 讓單位「淡出離場」,
   再播一次讓單位在游標選定的新格「淡入進場」。`battle.SetNativeUnitCoordinateBytes` 已把座標寫入
   部分做成 raw writer,但 27-present 演出本身仍走同一個 fail-closed renderer adapter。

3. **`0x250cc→0x22253`(chapter-ending / ch29 terminal handler)**:`CHAPTER-ENDING-250CC-BRANCH-AUDIT`
   已固定呼叫序:先送 FDOTHER frame `#0x0d/#0x0e/#0x0f`,呼 `0x1c2da`,再以**固定 unit slot `1`**、
   pre-render `0xff/0xff`(即離場 anchor)呼 `0x22253` 寫 `+0/+1`,送 frame `#0x10`,最後
   `0x25089`(persistent cleanup)→`0x2bce5`(ending renderer)並 self-loop。視覺語意:**最終戰結束、
   進入結局蒙太奇前,把 slot 1(通常是隊長/主角)那個單位從戰場上「演出淡出」**,作為終局轉場的
   一部分。這條路徑同時被 `0x2bce5`(chapter ending renderer,§8/91 檔另一個獨立缺口)卡住,即使
   `0x22253` adapter 做出來,這條路徑仍會在 `0x2bce5` 處 fail-closed(兩個缺口彼此獨立、不互相解鎖)。

共通觀察:三個 caller 的 `newX/newY` vs `visualX/visualY` 用法不同(caller 1 相同、caller 2/3 用
`0xff/0xff` 當「離場態」),證實 §9.1 提到的「演出態與最終邏輯態分離」不是巧合,而是這條 native
routine 刻意支援「離場」與「進場/就地」兩種語意的共用機制。

### 9.5 誠實列出:仍無法窮盡的部分

- **FDOTHER#6 LMI1 bank(230 entries)的逐 entry 視覺內容,尚未對到三個 caller 各自實際會選中
  哪些 entry**。§9.1 已知 intro phase 固定用 entries `0x72..0x7c`(12×21、九個 20×22、24×23 尺寸),
  但這些 entry 畫的是「單位本身淡出/淡入的漸變遮罩」還是「場景光效」,只能從尺寸推測,未逐張像素比對
  dosbox 實機畫面驗證(§9 全篇無 DOSBox-X 對照,純靜態反組譯)。
  - **descriptor buffer adapter**:FDOTHER#3 bank(`0x53a6d`,contract/release 用)的 23 張 remap LUT
    在 doc10 §「remap LUT 來源」已有基礎記錄,但哪一張 LUT 對應「離場變暗」、哪一張對應「進場恢復」,
    本輪未逐張核對色彩效果,故仍標「待閉合」而非直接命名。
- **raw53AB9/raw53ABD(游標 col/row)是否對三個 caller 都是同一組全域,還是各自有獨立的 cursor 狀態**:
  doc14 已證實這對全域在**對話框渲染路徑**是可視游標座標;本節沿用 91 檔既有反組譯結論(該欄位同時
  被 `0x22046` 讀取),但未做 live trace 確認 caller 2(戰鬥中道具)或 caller 3(結局)呼叫當下這對
  全域的實際數值——理論上應等於「目標格/該單位所在格」,但這是**推論**,不是逐一 trace 出的證據。
- **Ebiten job driver 本身不是 RE 工作,是工程實作**:§9.3 指出的缺口(仿 `nativeIndexedTransitionJob`
  寫一個 27-present state machine)已經有完整反組譯依據可以直接照抄公式與時序實作,不需要更多靜態
  分析;之後仍會撞上 caller 3 的 `0x2bce5` 獨立缺口。
- 三個 caller 的視覺 mock-up(不猜測性補畫面)未產出——rulebook 64 要求以原版實機截圖為 oracle,
  本輪未取得三個場景的 DOSBox 對照畫面,因此上面的「視覺語意」描述是**依呼叫序列與引數的邏輯推論**,
  非像素級驗證。

### 9.6 91 檔 L852 / L874 / L898 完成度(本輪不編輯 91-worklist.md,僅在此註記)

- **L852(indexed double-buffer visual adapter,ch24/25 pre-handler `transition_reveal`)**:**仍開放**,
  且與本節主題(`0x22253`)是**不同的 native 位址**(`0x24b4d` alternating-buffer present,非
  `0x22046`/`0x22253`)。查證 `cmd/fd2/main.go` 的 `"transition_reveal"` case(約 1532 行)目前只建立
  `transitionRevealJob{remaining,delay,then}`——純**計時骨架**,沒有任何真實 indexed 緩衝區交替寫入;
  真正的「雙緩衝視覺內容」仍未實作。本輪未觸碰此項,如實維持 D。
- **L874(`unit_present` metadata 不完整,fail-closed)**:本輪**已找出精確根因**(§9.2:舊六幀 schema
  對不上真實 11+6+10 鏈路,已被新 schema 取代但兩者在 runtime 端都被硬性擋下)並補上三個 caller 的
  視覺語意(§9.4)。但 fail-closed 本身**未解除**——沒有寫任何新的 Ebiten job driver 代碼(本輪任務
  範圍是反組譯記錄,非引擎實作)。故完成度:**根因與 caller 語意已釐清,運作缺口原樣保留**,worklist
  仍應維持 D/未關閉。
- **L898(`native 0x22253 renderer adapter`)**:與 874 是同一缺口的不同措辭。本輪確認 §9.3 列出的
  幾何/緩衝區交易(`fdother`/`indexedmap` 兩package)**已完整存在且有 30 個回歸測試**,唯一缺的是
  §9.3 指出的 Ebiten job driver 這一層,並已用同性質的 `0x24618`/`nativeIndexedTransitionJob` 做出
  精確對照。完成度:**「可能已部分由 `ComposeNativeTransitionFrame` 覆蓋」的舊猜測已被本輪修正**——
  `ComposeNativeTransitionFrame` 服務的是 `0x24618`(§9.1 明確是不同 native 位址),不覆蓋 `0x22253`;
  兩者只是共用 `ApplyIndexedTransitionPass`/`0x22046` 幾何原語,不能因此判定 898 部分關閉。仍應維持 D。
