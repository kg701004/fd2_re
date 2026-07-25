# 57 — UI evidence matrix（SDD-1 baseline，2026-07-25）

> 這是 SDD 的第一份可執行盤點，不是「已還原」宣告。行號以本輪 `remake/cmd/fd2/main.go` 為準；`partial`／`missing` 必須先補 E0/E1/E2 證據才可改成 verified。

## 現有 runtime evidence

| Contract | 現有 code evidence | 判定 | 下一個證據問題 |
|---|---|---|---|
| UI-01 title/menu | 原版 `0x1fe2c` scan-code loop（↑/↓ wrap；Enter/Space/`0xe0`/`0x52` confirm）、`0x25ebb` return dispatcher、DOSBox oracle `docs/figures/title-original-dosbox.png` 已固定 START／LOAD／CONTINUE 與 title cursor；remake title boot path 尚未拆成獨立 scene contract | partial | native third return branch 的持久資料來源、`0x30550` 四槽 selector／valid-save path、remake slot model 與畫面差分 |
| UI-02 field | map/camera/cursor/unit/HUD Draw 約 3441–3568、4571、4595 | partial | 原版 cursor camera、HUD anchor、FDOTHER panel resource |
| UI-03 action menu | Docker Capstone `0x18890` + `0x18d8c`：↑0 attack、←1 spell、→2 item、↓3 wait/field interaction；但 native `0x1c269` 實際從 unit `+0x1a..+0x1e` 五個 bitmask 列舉最多 40 個 command ID，再餵 `0x4e516`；`0x159fa` 再以 command `+5 <= unit+0x44`（current MP）過濾。真正 selector `0x1d51d` 是每欄四列、可變欄數的 command grid：↑/↓ linear wrap、←/→ ±4、Enter/Space 僅 MP 足夠確認、Esc cancel；renderer `0x1ceed` 以 `0x1b9+commandID` 查 label。remake `ringInput` 約 2407 的四格 mapping 僅為 partial approximation。item branch `0x1bbdc` selector/equip/transfer partially traced；`0x19953` 是另一個 battle selector，不取代此 ABI | partial | command bitmask 的 producer／label 資料表、完整 renderer、`0x20c6f` item effect table、end-turn entry |
| UI-04 target/range | `0x1cff0` + `0x149f8` 證實 command record `+3/+4/+6` 參與 target-candidate geometry；`0x1bbdc` item case 0 也呼叫 `0x14818`；Docker/Capstone 已釘 `0x14818` 先以 table record 更新 target grid，再疊 `abs(x-cx)+abs(y-cy) < radius` marker、依 unit camp/active state 過濾輸出；remake movement/attack/spell selection 已有，item action 約 2475 仍提示未實裝 | partial/missing | selector↔spell family 對照、`0x20c6f` item effect table、native argument↔weapon min/max mapping、AOE/LOS、不可用目標灰化 |
| UI-05 dialog | dialog Draw 約 3590–3686；`dlgAdvance` 有 page/scroll state；ch01 original oracle `docs/figures/ch01-dialogue-original-dosbox.png` 固定左肖像下框、文字、page indicator | partial | 每種 upper/lower portrait anchor、control-code renderer、native clipping |
| UI-06 HUD | target HUD 約 3557–3568；full-screen battle panel 約 4065、4180 | partial | FDOTHER loader、數字 cell、游標避讓和 320×200 ground truth |
| UI-07 postbattle | `campInput` battle result 約 2394；campaign node 可表達 post node；`campaign_full` 30 戰 transition matrix 已逐列展開 | partial | 以原版 handler offset／DOSBox input 差分核對每章是否進 town/shop/rest/preparation/ending |
| UI-08 town | `enterNode`/`campInput` 的 `town` branch 約 1584、2133 | partial | 原版 town menu、church/shop 入口與戰後 persistent timing |
| UI-09 shop | buy/sell/equip/recipient 約 2256–2391 | partial | 商品 menu sprite、游標邊界、secret shop flag、原版 cancel semantics |
| UI-10 church | revive/class-change 約 2162–2256；未接服務明確顯示待 callee | partial/fail-closed | 0x30dc3/0x31385 完整 fee、候選、確認與 renderer |
| UI-11 preparation | quota/checklist 約 1588、2133–2160；15/19 limit 欄位；native `0x1a30b` 會在 battle-entry loop 呼叫 `0x1f1cc/0x1f30a` 做 indexed buffer present；`0x1f42d` 的 LMI1 #0x52 double-slide entry/anchor 已釘 | partial | MAP/TURN 資料來源、行軍 YES/NO input 與 remake screenshot |
| UI-12 save/load | F5/F9 global path；save package 自有 schema；原版 `FD2.SAV` 的 `0x59cb` boundary、rolling-XOR/u32 byte-sum checksum、4×logical `0xa28` records at `+0x312b`（metadata `0x28` + roster `0xa00`）已由真實 sandbox decode 與 codec regression 覆蓋；metadata `+0`=chapter、`0xff`=empty marker；`0x30550` 明確為 4-slot（0..3）、↑↓ bounded、Enter/Space confirm、Esc cancel；empty-slot oracle `docs/figures/load-empty-original-dosbox.png` 證實 1–4 四列框與第一列 cursor | partial | remaining metadata semantics、delete/overwrite、successful-load restore、remake 四槽 model 與畫面差分 |

### UI-03 dispatch-wrapper recheck（2026-07-25，E0 partial）

Docker/Capstone 重新從 `0x18d8c` 入口線性追到 return，確認這是 action dispatch 的
**wrapper**，不能誤當 command-grid renderer：它先清 caller output 的 `+0` 與 global
`[0x53ec8]`。先前把 `0x1b83d(unitSlot,0)` 寫成「前序選擇」是錯的，現已刪除：它精確掃
unit `+0x0a + slot*2` 的八個 inventory slots，找 `bit0x40` 已設且 item ID `<0x80` 的第一格；
找不到時回 `-1`，wrapper 只設 output `+0=1`。命中時才經 `0x1b722 → 0x4e56c` 取該 slot 的
item record `+0xb/+0xc`，再呼叫 `0x14818(x,y,0,record+0xc,record+0xb,0)` 建立前序 target state。

其後 `0x1b8a6(unitSlot)` 精確計數八格中 `bit0x80` **未**設的 slots，因此它為零（所有 slots
空）時設 output `+8=1`；`0x1c269(unitSlot,0)` 為零及 `unit[+0x27] != 0` 都設 output
`+4=1`。前兩個 raw precondition 已閉合，三個 caller-visible flags 對應哪個可見 action／disabled
icon 仍未由 callee 或實機畫面閉合，SDD 保留 raw offsets，不能擅自畫圖示。`0x177fc`
是 wrapper 等待的選擇 loop，回傳 `-1` 則直接取消；非取消才按 `[0x53c57]` 分派：0 走
attack pipeline、1 走 `0x1cff0` command selector、2 走 `0x1bbdc` item selector，其他值才走
`0x13fd4/0x190ac` 的 wait/field path。這補強 UI-03 的取消階層與 dispatch 邊界，但不增加
任何 renderer 或 flag 語意斷言。

`unit+0x27` 的 action effect 已額外由 `0x1598a` 固定：它先取 `0x1c269` command count，隨即讀
`unit+0x27`；count 為零或此 byte 非零都在**任何** command record、MP gate、target-grid 建立之前
直接走 zero return。因此 `+0x27` 是整個 native command submenu 的 gate，不只是 wrapper 的一個
局部 flag。全 code 掃描的另外兩個 `+0x27` 命中是這個 read 與 wrapper read；`0x1eb64` 的 `lea
[ebx+0x27]` 是 UI resource frame index，並非 unit access。尚未定位此 byte 的寫入者／遊戲名稱，
故不得稱其為沉默、封魔或任一 status effect。

### UI-03 action overlay/input closure（2026-07-25，E0 partial）

`0x173e7` 先由四個 availability words 找第一個零值，寫 global current action `[0x53c57]`。
`0x177fc` 的 input loop 再以同一四-word state 拒絕不可用方向：scancode `0x48/0x4b/0x4d/0x50`
分別只在 word `0/1/2/3 == 0` 時選擇 `↑/←/→/↓` action `0/1/2/3`；`0x1c`/`0x39`
（Enter/Space）回 confirm，`0x01` 回 `-1` cancel。這是 command-grid `0x1d51d` 以外的 action
chooser ABI，現有 remake ring 的四向 mapping 只可作 interaction approximation。

renderer `0x1741c` 以 `[0x53a89]` 的 relative asset table 選四張 state-dependent images，透過
`0x4e9e4` 寫入 indexed overlay。它不是瞬間顯示：四張都從 shared origin `+0x390` 開始，每次
present 後 4-frame slide 分別更新 offset `up -= 0x8e8`（5 native rows）、`left -= 6`、
`right += 6`、`down += 0x8e8`。`0x175a9` 在開啟前備份 72×72 bytes（`0x1440`）到 private buffer，
`0x17643` 在每幀 restore。Docker Capstone 重讀 `0x176b4` 後，撤回「單純反向」的過度概括：它的
四幀 close 初始 byte offset 是 `[−0x23a0,0x378,0x3a8,0x2ac0]`，每幀改為
`[+0x8e8,+6,−6,−0x8e8]`。這證實十字狀 indexed overlay、方向與節奏。asset provenance 現已閉合：boot
`0x25c97..0x25cac` 將 `FDOTHER.DAT #2` 交給 `0x111ba`
並寫入 `[0x53a89]`。raw #2 是 untagged 78-cell offset bank（首 `u32=0x138` 即 directory end），cell
為 `{u16 width,u16 height,width*height indexed pixels}`；`0x4e9e4` 逐列 direct blit，index 0 preserve。
實測為 74 個 24×20、4 個 24×16 cells，strict `fdother.ParseRawCellBank` 與 player asset regression 已覆蓋。
`0x1741c` 的 relative table index ABI 也可重跑：每個方向取 `availabilityWord`（同一個供
`0x177fc` gate 的四-word array）與 `directionState`，cell index=`3*availabilityWord +
2*directionState`，再讀 `u32 relativeOffset=base[index]`、貼 `base+relativeOffset`。官方 IDA 重新
追 `0x18d8c` 後更正舊斷言：**battle action wrapper 的 directionState 是固定 `[0,1,2,3]`**，故
available cells=`[0,2,4,6]`，disabled cells=`[3,5,7,9]`。先前把 `0x1728c` 的
`[0x12+(byte_51e61==0),0x14+(byte_51e62==0),0x16+(byte_53af9!=0),0x18+(byte_51aab==0)]`
套到 battle action 是錯誤；該 caller 選中方向後只切換這些 byte state 並重畫自己的巢狀四向 menu。
`fdother.BattleActionOverlayState` 現以 unit test 固化真正 battle table；它不替這個另一個 submenu
的四個 byte 命名。remake runtime 現可選擇性讀玩家自己的 `FD2_ORIGINAL_FDOTHER`／
`assets/original/FDOTHER.DAT`：FDOTHER#0 的 6-bit VGA palette 轉為透明 index-0 palette，#2 的 raw
cells 0..9 以 final open frame 幾何直接貼到 cursor。這不包含原版 asset，也不把 current remake 的
attack/spell/item availability approximation 說成 native `0x1b83d/0x1c269/0x1b8a6` 全等價；open/close
動畫與原版 DOSBox side-by-side pixel diff 仍待驗證。Docker/Xvfb 以 player-provided FDOTHER.DAT read-only
實跑的 [native overlay remake screenshot](../figures/action-overlay-native-remake.png) 已證實 loader、palette、
cell geometry 與 font-independent draw path 實際出畫；它不是原版畫面對照。

2026-07-25 renderer gate 縮小：native skin adapter 現至少直接套用 `0x1b83d` 的「equipped 且
ID `<0x80`」attack 前提，並在 raw `NativeCommandMask` 非零時以其作 spell availability；沒有 raw
mask 的舊 editable scenario 才退回 normalized `Spells`。attack target geometry、`unit+0x27` 的名稱及
item effect 仍未閉合，因此這不是 native gate 全等價。

2026-07-26 official IDA 9.4 重讀 `0x1741c/0x176b4`：open/close 都是四次 cell blit、present
(`0x11eb0`) 與 72×72 backup restore 的直線迴圈；迴圈本體沒有顯式 delay/wait call。因此 offset
sequence 是 E0，但每一幀應停留多少 presentation ticks 尚未由這兩個函式證實；remake 不得自行把
它命名或硬編成 60ms 等固定動畫時間。

### UI-03 native command-grid renderer closure（2026-07-26，E0）

official IDA 9.4 的 `0x1d51d→0x1ceed` 證實 command submenu 是 320×200 indexed-buffer 的四列 grid，
不是 remake 的單列 spell list：對第 `i` 個由 `0x1c269` 輸出的 command ID，`column=i/4`、`row=i%4`；
label 由 FDTXT_000 的 `0x1b9+commandID` 畫於
`x=0x12+0x64*column, y=0x67+0x16*row`。選中項 text palette index=`0xc9`，其他項=`0xcd`；同一欄的
MP/record `+5` 數字使用右側 `x+0x49`／`y+5` 的 numeric renderer。↑/↓在完整 list 頭尾 wrap，←只在
index≥4 時減4，→只在 `index+4<count` 時加4，故水平不 wrap；Enter/Space 還會以 unit `+0x44` 與 command
record `+5` 的 MP gate 再確認一次。這閉合 layout/input ABI，但不命名 `+5` 以外的 command effect，也不使
normalized `Spells` list 自動成為原版 command grid。

2026-07-26 label bridge：若玩家提供 editable `assets/data/command_labels.json`（FDTXT_000 的
`0x1b9+commandID` export），remake 會只覆蓋已載入 EXE spell rows的 presentation label；缺檔或
malformed JSON 維持 normalized labels。這改善既有 spell presentation 的原始文字 fidelity，並沒有把
legacy vertical spell UI 宣稱成 `0x1ceed` command grid，也沒有擴大 effect semantics。

2026-07-25 重讀 `0x1741c` 並以 `0x179d5` 交叉驗證後，收斂了一層 framebuffer anchor：四張 cell
的共同地址為 `framebuffer + 0x8088 + 0x18*cursorColumn + (0x18*0x1c8)*cursorRow`。
`0x11bfa/0x11c59` 的 cursor movement 證明 `[0x53ab9]/[0x53abd]` 是這對可視 cursor coordinates：
在右／下邊界時分別改寫 `[0x53aa9]/[0x53aad]` 的 camera scroll，否則才遞增它們。因此撤回「A/B
語意未證實」；`fdother.ActionOverlayOrigin` 已把命名後的 byte-address expression 獨立測試。剩餘的是
將 native indexed framebuffer 接到 runtime，以及 DOSBox visual-diff 驗證實際 skin。

## 明確缺口（不可用 fallback 掩蓋）

- `item` action 仍是提示字串，不能宣稱道具 UI 完成。
- touch 目前只移動游標，不能 confirm/cancel；沒有 gamepad/key-binding UI。
- `unit_present` 與 `indexed_transition` 尚未有 native indexed adapter；RGBA／色塊 fallback 僅供診斷。
- church 主選單前兩項仍會顯示「尚待原版 callee 完整接線」。
- battle `Tab` 可結束回合是現有配置，不代表已證實原版是 Tab 或可見選單；需 E0/E2。

## 可重跑盤點命令

```sh
rg -n 'func \(g \*Game\) (enterNode|campInput|Draw)|ringInput|尚未實裝|尚待原版' remake/cmd/fd2/main.go
git diff --check
test ! -e /tmp/fd2cap
```

### UI-01 DOSBox title oracle（2026-07-25，E2 partial）

`tools/docker/fd2-dosbox-screenshot.Dockerfile` 以既有 Xvfb/xdotool/ImageMagick image 建立隔離 runner；
它只接受可寫的 **`/tmp` game sandbox** 掛載與明確 `/tmp` shots mount，原始 `FLAME2` 不掛進容器。
以 `svga_s3`、`fixed 18000` 跑 `wait:2; Escape ×4; wait:8` 後取得
`docs/figures/title-original-dosbox.png`（320×200 crop）。畫面直接證實 title 的 START／LOAD／CONTINUE
縱列與 START cursor；這是 UI-01 的 E2 畫面 oracle，不證明 title input dispatch、存讀檔語意或 remake
title renderer 已完成。

同一 timeline 在 title 選 LOAD 後可重現 `docs/figures/load-empty-original-dosbox.png`：原版在空 save
sandbox 顯示四列 `1)` 到 `4)`、每列「無儲存記錄」，第一列有 selection outline。這是 UI-12 的空槽
E2 oracle；它沒有有效存檔資料，因此不證明 record layout、LOAD 成功路徑或 SAVE overwrite confirmation。

START 分支首個可重現對話 crop 為 `docs/figures/ch01-dialogue-original-dosbox.png`：第一章場景中可見
左側 DATO portrait、下方藍框、兩行文字與框底中央 page indicator。這提升 UI-05 的一個 lower/left
E2 anchor；它不涵蓋 upper/right speaker、FFxx control code、完整 pagination timing 或 remake renderer。

### D8 native trace（2026-07-25，E0 partial）

Docker/Capstone 直讀 `0x1a30b`：battle-entry 先掃 unit buffer、以 `0x1da16` 更新 320×200
offscreen surface，再呼叫 `0x11eb0` present；接著呼叫 `0x1a813`／`0x1a866`，並在 phase
`[0x53ecc]==0` 時進入 `0x1a7bd → 0x1d80b → 0x1a7f1`。其中 `0x1a4c7` 明確呼叫
`0x1f1cc(0x52)`、20ms、`0x1f30a(0x52)`，完成 redraw 後才進後續 dispatch；`0x1f1cc`
與 `0x1f30a` 都配置 64000-byte indexed buffer、呼叫 `0x15f0e` 取資源並逐幀
`0x11d40` palette/present。進一步 trace `0x15f0e` 可確定它以 `base + 6 + frame*4`
取 frame offset，descriptor 前兩個 signed words 是 width/height，先配置
`width*height+8` 再經 `0x4e96f` 解壓、`0x4e85b` 以 stride 寫入 indexed surface；
這是可重用的 frame-resource ABI；`[0x53a81]` 的 loader provenance 已由 UI trace
確認為 `FDOTHER.DAT` resource #5 的 `LMI1` 容器（doc35 §4.2.5），remake 已新增
strict `fdother.ParseLMI1` 與 codec regression。
`LMI1Entry.BlitAt` 亦已對應 `0x4e8af` 的 index-0 transparent preserve 與
`0x4e8e1` 水平鏡像路徑；它只接受顯式 surface/anchor，尚未擅自接入 D8 layout。
實際玩家 `FDOTHER.DAT#5` regression（138 entries，#0x52=72×14）另證實 directory
offset 只標示 entry start：`0x4e916` 的 repeat 可跨下一個 offset，原版依 width×height
停止，因此 parser 不得把 next offset 誤當壓縮 stream 結尾。
`0x1f42d` 不是文字 helper：`0x1f1cc` 以 offset `100,75,50,25,0` 各呼叫一次，
每幀把 LMI1 **entry #0x52** 貼到 offscreen `(85-offset,82)` 與
`(165+offset,81)`（stride 456），present 一 tick，再以 `0x15e71` restore；這是
兩側 UI cell 的五幀滑入。它的反向 path 由 `0x1f30a` 使用同一 helper。這只閉合
indexed cell/座標/節奏，不足以命名 MAP/TURN 欄位或確認其為「行軍確認圖」，故 UI-11
仍 partial。

下一輪先處理 UI-03／UI-04 的原版 dispatch 與 weapon reach provenance，再補 D8 的
MAP/TURN text source 與 YES/NO input ABI；在此之前不新增猜測性 renderer。

### UI-04 geometry slice（2026-07-25，E0 partial）

`0x14818` 先以固定的 table record 0（`0x61646`，20 bytes）呼叫 `0x4e040`，並將原始
`(x,y,mode)` 傳入，建立／更新 target grid；`0x4e040` 以 mode 作 seed grid byte，內層再依
tile flag 與 record byte table 的 cost gate 擴張。此 raw mode 的玩法名稱尚未確定。其後才有可獨立
證實的一層幾何：以 source cell `(cx,cy)` 掃全格、
對每一格算 `abs(x-cx)+abs(y-cy)`，只有嚴格小於 caller radius 的格寫入 `0xff` marker。
最後掃 0x50-byte unit buffer：死亡／inactive unit 跳過、非 marker cell 跳過，再依 caller selector
對 `unit+6` camp 過濾，將 slot index 寫入可選 target output。當另一個 mode argument 大於等於
`0x10` 時另走一條十字形 clear path；它的玩法語意與 weapon `min/max` 欄位尚未完成 caller-dataflow
對照，不能把這個 raw `radius` 直接等同 remake `AtkMax` 或宣稱已解 LOS。

補作 `0x1cff0` caller 的 stack-dataflow 後，`0x14818` 的參數順序已可固定為
`(x, y, output, mode, radius, campSelector)`：`mode` 是第 4 參數、上述嚴格曼哈頓比較使用
第 5 參數，unit filter 使用第 6 參數。特別 command `0x17` 傳入 `record+3` 作 mode、`1`
作 radius、`record+6` 作 selector；一般 command 則傳 `record+4` 作 mode、`0` 作 radius、
`record+6` 作 selector。因此一般 path 不會在這一 call 新畫 diamond，而是消費前序已建立的
marker grid。`record+3/+4` 仍不能在未追到 producer 前命名為 weapon min/max。

該 record 的 producer 已定位：`0x1cff0` 將選單結果 ID 傳給 `0x4e516`，而
`0x4e516(id) = 0x619fd + 7*id`。因此 `+3/+4/+6` 是靜態 7-byte command ABI 的欄位，
不是這個 handler 自行組出的暫存結構；在有 field-name 或實機資料對照前，仍以 raw offset
記錄，不擅自命名成攻擊／法術的 min/max range。

command ID 並非 four-way ring 的固定索引：`0x1c269(unitIndex, out)` 讀取該 0x50-byte unit
record 的 `+0x1a..+0x1e` 五個 byte，逐 bit 把 set bit 寫出成 `byteIndex*8 + bitIndex`（0..39）。
`0x1cff0` 以這份 list 的目前選項取得 ID、再呼叫 `0x4e516`。因此 UI-03 的完整 SDD 必須資料化
command bitmask、ID→label/rendering、enable gate 與 cancel hierarchy；現行四格 `ringInput` 只能保留
為 provisional interaction，不能冒充原版完整 command menu。

bitmask 的 construction ABI 也已定位：`0x10f7f` 將 source record `+0x0d..+0x10` 的 4 bytes
copy 到 unit `+0x1a..+0x1d`，並清 unit `+0x1e`；另一 construction path `0x11399` 同樣 copy
4 bytes（其 source `+8..+0xb`）再清 `+0x1e`。後續 `0x1d7fb` 以 `commandID/8` 選 byte、OR
對應 bit 寫回 `unit+0x1a` 起的 array。因此 40-bit 是真實 runtime ABI，但初始 source 只有 32 bits，
第 5 byte 由後續流程擴充；source record 的遊戲語意仍不可未證實地命名。

原版另有已證實的可用性 gate：`0x159fa` 先取得同一份 `0x1c269` list，逐個取 command record
`+5`，僅當該 byte `<= word[unit+0x44]` 時保留；`+0x44` 已由 battle HUD 證實為 current MP。
因此 `command+5` 是 MP cost/requirement 的 E0 ABI，而不是 UI 的任意排序值。bitmask 的寫入
producer、每個 ID 的名稱與其他 enable gate 尚未閉合。

`0x1d51d` 是這份 command list 的 input loop（不是 `0x19953`）：每次先 call `0x1ceed` render，
再取 `0x1c269` count。scancode `0x48/0x50` 對線性 cursor 做 -1/+1 並在 `[0,count-1]` wrap；
`0x4b/0x4d` 分別在 index >=4 時 -4、在 index+4<count 時 +4；renderer 座標證實每欄四列（不是四欄）。
`0x1c/0x39`（Enter/Space）重新查 `command+5`，只有 current MP 足夠回傳 confirm；`0x01`（Esc）回傳
cancel。`0x1ceed` 的 list index `i` 使用 `x=0x12+0x64*floor(i/4)`、`y=0x67+0x16*(i%4)`，以
`0x15f84([0x53a7d], 0x1b9+commandID, ...)` 顯示 label，並以 `0x187d6` 顯示 command `+5`。這鎖定
label index ABI 與 geometry。常駐 `[0x53a7d]` table 已由其他 callsite 的 direct trace 對齊為
FDTXT_000；raw strings `0x1b9..0x1e0` 已匯出為 `docs/data/command_labels.json`。其中空字串與
系統訊息 slot 證實文字不等於可達指令；cursor cell／不可用 command 的可見表現仍待 resource／實機畫面，
不得猜作四方向 ring。

補充 record evidence：`0x4e516` 的 `0x619fd+7*id` 對 IDs 0..35 byte-for-byte 等同 EXE spell table，
所以 command record 的 `+3/+4/+5/+6` 可分別沿用 spell row `dist/range/mp/target` 的已證實欄位；資料掃描中
FDFIELD/character default initial masks 只出現 IDs 0..30。36..39 的鄰接 bytes 與 FDTXT 系統訊息不能被當成
可選技能。

動態 command producer 亦已定案：level-up routine `0x1e292` 讀 portrait growth row 的 `learn_idx`，以
`0x4e4a2` 取固定 12-byte learning row，掃最多六組 `(level, commandID)`，level 命中便呼叫
`0x1d79c(commandID, runtimeSlot)` OR bit 並顯示 FDTXT_000 #587。20 rows 已原樣導出；這不是一般
selector effect trace，故不代表所有已學 command 已有可執行 remake effect。

`0x4e040` 並非僅由這個 target caller 使用：`0x14344` 先以 unit `+0x20`（fallback record
`0x13`）透過 `0x4e555` 取另一個 20-byte record，再把 map grid、terrain table 一併傳入。
其內層 `0x4e16e` 讀 tile flag 與該 record 的 byte table 後決定是否擴張。故目前可用的
E0 模型是 **seed mode + table + terrain/cost gate + marker + unit filter**；尚不可把 target highlight
reducer 成單一菱形或宣稱其完整路徑／LOS 規則。
