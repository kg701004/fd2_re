# 56 — FD2 remake 系統設計規格（SDD，2026-07-25）

> 本文件是重新開始 remake 前的設計闸門。目標不是把目前能啟動的 Ebiten demo 擴張成更多 placeholder，而是以可追溯的反組譯證據，重建原版的操作介面、戰間流程、資料與腳本引擎。未滿足證據與驗收條件的語意保持 fail-closed。

## 1. 目標與現況判定

### 1.1 目標

- 原版 30 關的 campaign、戰鬥、戰後城鎮／商店／教會／整備、存檔與結局可循環遊玩。
- 對話、事件、商店、部署、過場和 UI layout 都由外部資料／腳本驅動；新增戰役不需修改 Go runtime。
- UI 操作語意以原版為目標：游標、action overlay／command grid、射程／目標、對話框、狀態欄、商店、教會和戰後節點均須有可見且可測的操作入口；未取得 E0/E1/E2 證據的現有 UI 只算 approximation。
- native indexed renderer 與現代 RGBA/Ebiten 顯示層分離；未完成 native ABI 時不得用泛用淡出、PNG 或空白畫面冒充完成。

### 1.2 現況（以 2026-07-25 working tree 與程式碼為準）

目前不是「沒有程式」，而是「有一個可跑的垂直切片，尚未達 remake」：`remake/cmd/fd2/main.go` 仍承擔 scene state、輸入 dispatch、戰鬥 UI、對話、town、shop、church、preparation 與 Draw；`internal/battle`、`internal/campaign`、`internal/ending`、`internal/figani` 已有可測的部分 primitive。這些 primitive 不等於原版 UI 或完整 campaign。

已存在但必須重新驗收：story/cutscene BeatRunner、dialog 分頁／捲動、campaign node、persistent roster、shop buy/sell/equip、church revive/class-change、preparation quota、indexed ending prefix。明確缺口包括：原版選單完整 dispatch、可見的回合結束流程、武器射程、完整 spell effects/演出、HUD 避讓、完整 UI sprite/layout、所有 postbattle branch、native ending montage。

AI spell scoring raw slice：Docker Capstone/Hex-Rays 已閉合 `0x15b77` attack IDs0..12 的 HP threshold/`+0x08` branch、recovery IDs13..16 的 max/3→8、max/2→3 tiers/`+0x34 bit0` branch、ID17/18/19 的 `+0x22/+0x23/+0x24` zero flag score 3、ID20/21 的 nonzero `+0x25/+0x26` score 6、ID22 的 `+0x27` gate→`0x1c269` bit scan→6，以及 ID26/27 的 zero `+0x25/+0x26` score 4；`ScoreNativeAISpellAttack`／`ScoreNativeAISpellRecovery`／`ScoreNativeAISpellFlag`／`ScoreNativeAISpellZeroFlag`／`ScoreNativeAISpell22` 只接受 raw records，ID10..12 另要求 caller-supplied `0x1f183` gate。這些函式不命名欄位、不接 AI runtime 或 target UI。

`0x1598a` dispatcher 的 raw selection boundary 也已閉合：`unit+0x27==0` 後，`0x1c269` 產生 command bytes；每筆 command 先以 record `+5 <= unit+0x44` 過濾，再由 `0x4e040`/`0x14818` 產生目標候選，呼 `0x15b77(command,candidateCount,candidateBytes)` 評分。最大 score 勝；同分比較 command record `+0`，仍同分則保留先出現者。`battle.SelectNativeAISpellCandidate` 只保存此 score/tie-break 與 raw `(x,y,command)`，不代替 MP、target resolver、`+0x27` gate、UI 或施法執行。
`battle.NativeAvailableAICommandIDs` 另保存 dispatcher 前置 gate：raw `+0x27` 非零時不產生任何 AI command IDs；為避免把第五 command byte 的未知 physical IDs36..39 當可執行命令，仍只回傳已驗證的 0..35 records。

## 2. 證據分級與反組譯規則

每個進入 runtime 的常數、座標、幀數、資源索引和 handler 語意都必須附證據：

| 等級 | 來源 | 可否解除 implementation gate |
|---|---|---|
| E0 | 原版 EXE/DAT bytes、Docker `fd2-cap-local` Capstone、Ghidra/IDA call graph | 可以，需保留 offset、呼叫者與反組譯片段 |
| E1 | deterministic parser、pixel/byte regression、資產 round-trip | 可以，需能重跑且輸出穩定 |
| E2 | DOSBox/Xvfb 實機操作、逐幀截圖／輸入差分 | 可以，需保存 command、frame、artifact |
| E3 | 攻略、影片、視覺推論或 UX 慣例 | 只能列為假設，不得解除 native/handler gate |

本輪重新核對的已知更正：`0x16559` 是 DATO mouth-frame／glyph blit caller，`0x4ea2a` 才是 native glyph renderer；FDTXT `0x2c469` 的 `load_ch_text(30)` 對 archive resource #31 的物理表，不能直接命名成 ch30；`0x2c548` 有 `i=0→slot1、i=1→slot0` swap；`0x29164` 第一參數是 party unit index，TAI#3 是 7-byte transparent aux，不是可見台座。這些結論要在新工具鏈重跑後才能再擴展，不可由名稱推導 renderer 語意。

`~/.codex/knowledge-base` 在本執行環境目前沒有可讀檔案（`rg --files /home/anr2/.codex/knowledge-base` 無輸出），因此其中的 Ghidra/IDA 技巧尚未納入本輪證據。使用者已確認 `/home/anr2/ida_pro/ida94b1/idapro.hexlic` 為其合法持有的授權檔；官方 Docker image 的文字版 `/opt/ida-9.4/idat -h` 已以該檔唯讀掛載驗證可啟動。不得使用同目錄既存的 `kg_patch` 設定、檔案或 Compose 掛載。

repo 提供不含 license／遊戲資料的 `tools/docker/fd2-ida.Dockerfile` 與
`tools/ida_export_fd2_xrefs.py`，供使用者授權的私有 IDA workspace 匯出 xref 後重跑。2026-07-26 已以使用者
合法的本機 IDA Docker image、臨時 overlay 的容器內 Python 3.12、唯讀遊戲檔與 `/tmp` IDA database 實跑；
`docs/data/ida/fd2_xrefs.json` 已由 IDA 9.4/Hex-Rays 產出。過程修正 IDA 9.4 移除的
`ida_xref.get_xref_type` API；export 現只保存 address/caller/function metadata，絕不提交 binary、database 或 license。
這份 report 可作 call-graph E0 交叉驗證，但不自行證明遊戲語意；語意仍須由指令與資料流佐證。

## 3. 目標架構

```text
Input adapters (keyboard/mouse/gamepad)
        ↓ normalized Commands
Scene FSM: title → story/cutscene → battle → postbattle → town/shop/church/preparation
        ↓                         ↘ save/load snapshot
Campaign/Script runner          Persistent party + flags + inventory
        ↓
Battle rules / target selection / AI / animation scheduler
        ↓
Indexed native surfaces + RGBA/Ebiten presentation adapter
        ↓
UI skin/assets (FDOTHER/FDTXT/DATO/FIGANI/TAI/FDFIELD) + audio
```

Runtime 不應再讓 `main.go` 同時決定資料模型、輸入、規則和像素座標。下一階段先定義 interfaces，再搬移；在搬移完成前不增加新的 hard-coded handler。

## 4. UI interaction contracts

每個 contract 都必須有 state、可見 render model、輸入 command、side effect、headless test 與一個實機／截圖 gate。

| ID | UI / 流程 | 必須還原的操作契約 | 目前狀態 |
|---|---|---|---|
| UI-01 | Title/main menu | 上下選擇、確認、取消、save/load、游標音效與 focus state | partial；需從 boot/menu call graph 重審 |
| UI-02 | Battle field | 游標格、鏡頭、可移動格、高亮、單位 HUD、方向／面向 | partial；HUD 固定錨點與完整 native sprite 未閉合 |
| UI-03 | Action menu | move/attack/magic/item/status/wait/end-turn 的可見項、enable gate、取消回上一層 | partial；原版 action overlay 的 battle cell table（enabled `[0,2,4,6]`／disabled `[3,5,7,9]`）、open/close 四幀 byte-offset、以可視 cursor column/row 算出的 framebuffer anchor 已閉合。native command grid 亦已定為 320×200、每欄四列，label `(18+100*col,103+22*row)`、MP 右側、↑↓ wrap/←→±4 bounded；scenario raw command mask 已可 materialize。Docker/Xvfb 以 player FDOTHER.DAT 捕捉的 [悠妮 command-0 grid](../figures/native-command-grid-remake.png) 證實 mask→label→palette/font→renderer 路徑，非 original visual diff。玩家提供 `FD2_ORIGINAL_FDOTHER`（或 user assets）時，remake 會直接讀 FDOTHER#0 palette＋#2 cells 並畫 final-open skin；舊 PNG ring 是 fail-closed fallback。raw grid confirm 現明確拒絕送入 legacy `CastArea`，直到 native two-stage target/effect 閉合。動畫、完整 native gate 與 visual-diff 尚缺 |
| UI-04 | Target/range | 武器 min/max reach、法術 range/AOE、不可用目標灰化、確認／取消 | missing/partial；不能再把攻擊距離寫死相鄰格 |
| UI-05 | Dialog | 上／下框、portrait anchor、文字避讓、控制碼、分頁／捲動、嘴型、輸入鎖 | partial；`internal/dato.MouthState` 已按 `0x16D00` cadence 接入更新迴圈，native frame/資源與所有 speaker layout 未閉合 |
| UI-06 | Battle HUD | HP/MP/LV/name、面板 sprite、數字 cell、依游標避讓、palette/clip | partial；需以 FDOTHER/UI loader 和截圖差分驗收 |
| UI-07 | Postbattle | result → handler → reward/roster cleanup → town/shop/rest/preparation 或 ending；不可預設直連下一戰 | partial；campaign schema 可表達，逐關 branch 證據仍不足 |
| UI-08 | Town/hub | 可見選單、離開、shop/church/preparation 入口、BGM/SFX、持久隊伍 | partial；`town` 可選 node，但需逐章節驗證 |
| UI-09 | Shop | buy/sell、商品／角色／slot 游標、裝備詢問、金錢／庫存原子更新、secret gate | partial；buy/sell/equip 有 code，UI sprite/layout 與原版分支未驗 |
| UI-10 | Church | revive、class change、費率、候選過濾、確認／取消、缺資料 fail-closed | partial；現有 service menu 對未接 callee 明確擋下 |
| UI-11 | Preparation | JOIN chronology、deploy quota（15／19）、勾選／取消、預覽、F5 save、進戰場 | partial；資料與 quota 有 code，原版 layout/操作未做差分；`0x1f42d` split-slide indexed cell primitive 已閉合 |
| UI-12 | Save/load | scene-safe boundary、campaign cursor、flags、party/inventory/equipment、version/checksum、四槽 selector | partial；remake title LOAD 已還原四槽 bounded selector（slot 1 保留舊 `fd2_save.json`，slot 2–4 使用 `fd2_save_1..3.json`）。`remake/internal/fdsave` 已提供 raw rolling-XOR/checksum、slot bounds、verified metadata 與 opaque `WriteSlot` adapter；但 native `FD2.SAV` roster/opaque metadata 尚未接入自有 campaign save；4×logical records（`+0x312b+i*0xa28`，`0x28` metadata + roster `0xa00`）仍非相容實作 |

### UI acceptance gate

在 `UI-01…UI-12` 每項至少有一個 deterministic input script、預期 state trace 和 screenshot artifact；只通過 Go unit test 不算 UI 完成。截圖測試需記錄解析度、幀號、輸入序列，並比較 cursor/menu/dialog/panel 的 bounding boxes。無法取得原版 ground truth 的項目標為 blocked/assumption，不得用「看起來合理」關閉。

### UI-03 native command data contract（E0 partial）

原版 `0x1c269` 將 0x50-byte unit record 的 `+0x1a..+0x1e` bit array 展開為
`command_id = byte_index*8 + bit_index`（0..39）；`0x4e516(id)` 對應到
`0x619fd + id*7` 的 command record。construction path `0x10f7f/0x11399` 只 copy initial
4 bytes 至 `+0x1a..+0x1d`、清 `+0x1e`，而 `0x1d7fb` 可依 `id/8` 將 runtime bit OR 回 array。
`0x159fa` 另要求 `command_record[5] <= unit.current_mp`（unit `+0x44`）。

FDFIELD 26-byte roster 的 source bytes `b13..b16` 現由 `parse_field.py` 和
`export_units.py` 保留為 `initial_command_mask`；battle `Unit.NativeCommandMask` 以五個 bytes
materialize，並只提供原版 byte-major／low-bit-first 列舉與 bounded OR。這條管線刻意不覆蓋既有
`Spells` normalized list：後者是 legacy gameplay approximation，不能再被宣稱為原版 raw command source。

Scenario party override 也已採同一欄位：`PartyMember.initial_command_mask` 只接受空值（舊 editable
scenario）或精確四 bytes；`LoadScenario` 對其他長度 fail-closed，避免截斷後偽造另一個 command inventory。
`gen_campaign.py` 從 EXE `character_defaults.json` 依角色 index 帶入該 raw source，並已重產
`ch01..ch30.json`，且不覆寫既有手工驗證的 scenario 欄位。ch01 的悠妮為 `[1,0,0,0]`，其餘初始三人為全零，均直接來自
character-default table，絕非由 legacy `Spells` 反推。戰後 persistent snapshot 亦保留完整五-byte runtime
mask，因此 `0x1d7fb` 型 level-up OR 不會在 town/preparation 邊界遺失。

`0x4e516(id)` 的 backing bytes 對 `id=0..35` 與 EXE `spell.json` 7-byte rows 逐 byte 相同，故這個
已證實範圍的 record layout 可共用 `dmg:u16, hit:u8, dist:u8, range:u8, mp:u8, target:u8`；MP gate 是其
第 5 byte 的獨立直接證據。IDs 36..39 雖可由 pointer arithmetic 取到相鄰 7-byte data，FDTXT labels
卻是空字串／系統訊息，且所有 FDFIELD + character-default initial masks 實測最高只設到 ID 30。故不得把
36..39 加進 `SpellBook` 或宣稱第五 byte 的 dynamic path 已被實機素材證實。

runtime 對 native path 使用 `NativeCommandRecord`，不使用 normalized `Spell`：它將 bytes `+3/+4/+5/+6`
明確暴露為 `SelectionMode/EffectMode/MPCost/TargetCode`。loader 可讀現有的 physical export `spells.json`，但逐 row
重解 `raw` 的七個 bytes 並要求所有 JSON field 一致，且只接受連續 ID 0..35；任一 editable presentation 欄改壞、
缺列或未知 ID 都 fail-closed。Game bootstrap 只把這份 immutable book copy 到每個新 `battle.State.NativeCommandBook`；
它不取代 `SpellBook`，也尚未驅動 UI/effect。

選單 confirm 的 execution contract 必須再區分：`0x1cff0` 先完成 raw command ID 的 selector/target path，再由 ID 分派。`0..8`、`0x18`、`>=0x1c` 呼叫 `0x2a6bd(unit, id, target, scratch)`；`0x09..0x17` 與 `0x19..0x1b` 先走 `0x1d6c8(id)` 的四輪 palette flicker，之後才進 `funcs_1541f[id]` jump table。這證實 command 0 屬 generic pipeline，**不**證實它等同 normalized `Spells[0]`、也不允許在未解 callee 前為它填 damage/target contract。native-grid confirm 對無完整 effect trace 的 ID 必須維持 fail-closed。

`0x2a6bd` 的 command-0 entry 本身也不能被誤讀成 effect formula：它以 ID 作 presentation mode，command 0 不走 `>=0x20`／`0x18..0x1b` 的 special early branch，而採 generic compositor defaults，並經 `funcs_2ac25[0]=0x26152` 多輪繪製 320×200 battle buffers、FIGANI／FDOTHER cells、present/tick。這是已證實的 renderer boundary；HP、status、MP mutation 的責任仍需沿其後續 callee／caller 另行 dataflow 證明。

2026-07-26 official IDA recheck further closes the `0x2c405 → 0x2c548` hand-off boundary. After the 500-pass phase-0 scroll, native code frees staging, allocates one `0x1f400` and two `0xfa00` buffers, loads `TAI.DAT` entry `3` and `FDOTHER.DAT` entry `0x38`, and blits the latter into the first indexed buffer before iterating party records from `[0x53bfb]-1`. This resource/buffer contract is now recorded in `assets/endings/native_2c548.json`/worklist; it does **not** authorize a PNG or generic-fade adapter. DATO/FIGANI scheduling, mirror branch, and the dedicated indexed renderer remain fail-closed.

The same IDA pass closes the previously omitted `0x29164` mirror branch. When `unit[+6]==0`, the native path at `0x2927e..0x29357` retains the 9-pass `stage=8..0` and `stage*6` DAC cadence, but addresses the primary FIGANI frame at `staging+0x140-stage*10`; `arg4==0` gates the extra TAI#3 and secondary-FIGANI draws. This is now an explicit `mirror_branch` record in the editable montage schema with a loader regression. It remains evidence-only: no PNG approximation or runtime renderer permission follows from the transcription.

`Montage.PlanMirrorFigureFade(unitSide,sideFlag)` exposes that schedule as a pure, testable plan (nine exact offsets and DAC deltas, with the `arg4==0` secondary/platform gate). The planner is deliberately not a pixel adapter and keeps the montage fail-closed.

Correction: `[0x53a81]` in this call chain is `FDOTHER.DAT#5` (the dialogue-frame bank), not DATO. Official IDA shows `0x2c773` calling `0x168b6(destination=C, stride=0x140, arg8=5, argC=7, arg10=5, arg14=5)` to build that dialogue frame/grid; the later DATO pointer `[0x53a85]` is pasted by `0x4e8af`. This is a resource/layout boundary only; it does not authorize a single-static-portrait or guessed mouth cadence adapter.

`internal/dato` now provides the corresponding resource boundary: four-frame DATO LLLLLL parsing, the native `0x4e916` high-run codec, opaque-zero semantics, and bounds-checked indexed blit. `MouthState` preserves the verified `0x16D00` cadence as a pure tested adapter and is used by the dialogue update loop; the `0x168b6` grid choreography, complete DATO runtime resource binding, and ending UI integration remain explicit gates. For the separate `0x24618` transition, `fdother` now preserves the native full-buffer seed and 456→320 viewport copy contract, but runtime LUT selection and indexed presentation are still fail-closed.

`Montage.PlanDialogueFrameGrid()` now transcribes all 49 `sub_1685c` calls for the proven `0x168b6` invocation (12 fixed cells, two `3×2` loops, and a `5×5` raw grid). It exposes only `FDOTHER#5` resource indices and byte offsets; cell semantics and DATO mouth timing remain intentionally unnamed.

Codec correction: the `0x1685c→0x4e9bb` path copies each selected `FDOTHER#5` cell's width×height bytes directly (`rep movsb`). It is not the `0x4e916` high-run codec used by DATO portraits. `fdother.ParseLMI1RawEntry` now preserves this separate contract and has a real entry-1 byte regression.

`RenderDialogueFrameGrid` now executes that narrow primitive against the 49 verified placements, writing literal zero bytes and preserving native overwrite order. It is only the C-buffer frame layer; DATO portrait paste, text glyphs, input, and ending runtime remain gated.

`RenderDialogueFrameGridResource` now runs the same contract against the player-provided `FDOTHER.DAT#5` entries 1..17, with missing assets failing closed. This verifies the raw resource boundary without promoting the frame bank into a guessed semantic UI renderer.

`RenderDATOFrameAt` and `dato.Frame.BlitAtOffset` now cover the separate opaque `0x4e8af` portrait paste with explicit stride/offset inputs. The caller must supply the recovered staging destination (the ending call site uses `staging+[0x53c67]`); the helper deliberately does not turn that global into a universal UI anchor or infer mouth timing.

`RenderMirrorFigureFadePass` now implements only the proven `0x292ad` indexed primitive: it requires a caller-preseeded 640-stride work surface, presents `work+0x140`, blits primary at `+0x140-stage*10`, conditionally blits secondary for `arg4==0`, and presents the same right viewport again. It validates TAI#3's transparent bytes but does not claim to render the unresolved DATO/portrait or complete montage.

Generic scheduler closure：`funcs_2ac25` 是 command-indexed function bank（ID0 entry `0x26152`）。`0x2a6bd` 先以 mode 0 呼該 entry 取得 animation step count，接著在 640-stride off-screen buffer 的逐 step loop 呼 mode 2、`0x11eb0` copy 320×200 至 VGA、`0x17aa9(1)` tick、再呼 mode 1；收尾的雙 buffer path 還會呼 mode 4。`0x2b9a1` 並非未知 effect，它以 descriptor `frameIndex*4+8` 指向 frame的 byte+6 delay，遞增 `0x540fc`／`0x540fd` subframe counters並在上界 reset。這固定了 phase/order，仍不替每個 command entry 的視覺語意命名。

Generic presentation 的 BG selector 亦已閉合為 raw dataflow：`0x2a6bd` 呼 `0x2b5e1(finalCount, finalTargetArray)`，後者**倒序**掃 target slot，對該 unit cell 呼 `0x12e38`；若 raw `0x1f183` gate 不通、或累積 selector 為零，才以 decoded control byte+2 取代 selector，最後才餵 `0x111ba("BG.DAT", selector)`。`fdicon.NativeCommandBackgroundSelector` 保留該 strict pure rule。command ID 的 generic branch 不可被說成直接選 BG resource；selector 的高階地形／場景語意仍不命名。

BG asset boundary：`BG.DAT` 是 LLLLLL archive；generic compositor 的前三個已知 layer #0/#1/#2 都是 `{u16 width,u16 height, 0x4e63d four-mode RLE}` single-frame payload，實測各為 320×100。`fdother.DecodeArchiveSingleFrame` 明確解這種無 frame-directory 的 archive entry，player-archive regression 對三個 layer 解入 320×100 indexed surface。它不替 `0x2b5e1` 的其他 raw selector 命名，也不自動把 current PNG background 當 native layer schedule。

### UI-03 action chooser availability contract（E0 partial）

`0x18d8c` 先清四個 dword，按固定順序傳給 `0x173e7/0x177fc`：`[+0]` attack、`[+4]`
native command、`[+8]` item、`[+12]` wait。`0x173e7` 選第一個值為 0 的方向，`0x177fc`
只允許落在值為 0 的方向；因此這些值是 disabled flag（非可用 count）。具體 E0 precondition 為：

- attack：`0x1b83d(actor,0)` 必須在 runtime inventory 的八個 2-byte slots 找到 flag `0x40`
  且 ID `<0x80` 的 entry；其 item record `+0xb/+0xc` 傳入 `0x14818` 後仍須產生 target，否則 `+0=1`。
  `battle.NativeEquippedInventorySlot` 已保存此 raw predicate；有 constructor flags 時 overlay 不再以
  normalized `Equipped` 取代它，缺 provenance 仍保留 legacy fallback。
- native command：`0x1c269(actor,0)` 必須枚舉至少一個 raw command bit，且 raw `unit+0x27==0`；任一失敗皆寫 `+4=1`。
  command 22 已證實會寫入此 duration byte；其遊戲名稱與所有 producer 尚未閉合，故 remake 只以
  `NativeTransient[5]` 保存並 gate raw command，**不得再說它等於 legacy `Sealed`**。
  選定 command 的 MP availability 另由 `0x159fa` 驗證 record `+5 <= unit+0x44`；`battle.NativeCommandAvailable`
  只在 raw bit、完整 0..35 command record 與 MP gate 同時成立時回 true，未知 36..39 bits 與 malformed book
  fail-closed，不把 selector gate 誤當 action-direction 或 target geometry。
- item：`0x1b8a6(actor)` 計數八 slot 中 flag `0x80` 未設的 entries；零個即 `+8=1`。
  `battle.NativeInventoryAvailableCount` 已保存此 raw count，overlay 在 constructor flags 存在時不再用
  `len(Inventory)` 取代它；沒有八格 provenance 的 legacy JSON 才保留明確標記的 approximation。
- wait：wrapper 未寫 `+12`，故在這條 chooser path 永遠可選。

既有 normalized `Spells`／`Sealed` 只保留給缺 raw command mask 的舊 editable scenario 相容 UI；它不得作為
FD2 native action gate 的證據，也不得覆蓋 raw mask 已存在時的 `unit+0x27` gate。remake 的 confirm path 已同樣
拒絕非零 disabled word，避免「灰色 cell 仍可 Enter 執行」。攻擊 geometry 與 item selector/effect 仍未閉合，native
overlay 維持 partial。

同樣地，`0x1b6b7` 不是 effect calculator：它掃 native runtime roster，只對符合 `+5/+0x31/+0x40` 後處理條件的 record 複製三 bytes（source `+0x31`）到 caller buffer；`0x1cff0` 再把此 buffer 交給 `0x1aa1d`。後者因此是 post-resolution 的訊息／掉落／互動處理層，不能拿來推回 command 0 的原始傷害或 status writer。確切三個 byte 的遊戲語意尚未命名，維持 raw offsets。

玩家 table 的 IDs0..12 numeric damage writer 已閉合到 `0x1c75e(target, commandID)→0x1c81f(target, amount)`：前者取
`record.u16[+0] * resist_raw[unit+0x20] / 10` 為 base；constructor `0x10f7f/0x11399` 直接把 source
class byte 寫入 `unit+0x20`，故這是 target class-ID-indexed table，而非未明角色欄位。這些 handler 以 `record[+2]` 做 `rand()%100`
命中門檻；命中才呼叫後者。`0x1c81f` 算 `damage = floor(base*0.9) + floor((rand()%100)*base/1000)`，
將 target `unit+0x40` 減去 damage，並 clamp 至 0，直接證實 `+0x40=current HP`、`+0x42=max HP`。
IDA `word_51f96` 的 loaded-data file offset 正是既有 `0x51d96` 職業魔抗表：每 class 的 4-byte row
低 byte 是 `resist_raw`（法師=7 即 30% magic resistance）。因此這個乘數的 raw ABI 與玩法名稱都已閉合，
並以 `NativeCommandDamage` 的獨立 resolver 實作及 regression 固定；它不共用 legacy normalized magic
resolver。`remake/assets/data/native_command_resistances.json` 是同一 raw table 的可編輯 runtime copy；target
geometry、動畫及 post-resolution 仍未閉合，故 UI 不得把已知數值公式誤擴張成完整 native effect。

玩家 dispatch 的可達性已重新核對：`0x1cff0` 對 IDs0..8 直接呼叫 `0x2a6bd`，沒有經 table 內的
`0x21227/0x213b7` wrappers；但 `0x2a6bd` 不是純 renderer：它先經 `sub_2b659` 的 MP event，final-target loop
直接以 array slot 和 command ID 呼叫 `0x1c75e(targetSlot, commandID)`。因此 IDs0..8 與 ID9 direct path、及
IDs10..12 compositor tail 都已閉合為同一 numeric/MP/raw-completion contract；dispatch 分流不表示 state effect
缺失，也不表示 renderer 等同。

`State.ExecuteNativeCommandDamage` 嚴格支援 IDs0..12，以 raw record、兩階段 target、class multiplier/hit/HP
clamp 和 success-only raw completion writer 做 bounded engine slice。`ExecuteBoundNativeCommand0`／raw-grid ID0 target slice
只接此 state core；缺 flags、record、candidate 或 resistance row 均在 mutation 前拒絕。專用 renderer、SFX、
post-resolution、其他 ID UI 與 screenshot oracle 仍未完成。

IDs13..16 是另一條已閉合的治療核心，不能併入上面的 damage route。其 jump-table handlers
`0x21AD9/0x21B99/0x2211C/0x22153` 各以 ID `13/14/15/16` 和各自的演出參數跳到共同
`0x21B18`；它在 generic target-confirm 後，以同一 final target array 呼叫專用 indexed 演出
`0x1C4CC/0x1C2DA`、再經 `0x1CA89(actor,id)` 扣 record `+5` MP。它逐 target 呼叫
`0x1C8ED(target,id)→0x1C916(target,record.u16+0)`：`+0x40` 增加
`floor(amount*9/10)+floor(rand()%100*amount/1000)`，上限 clamp 為 `+0x42`，並以
`0x1E0DB(...,0x69,target)` 顯示結果。這直接證實 IDs13..16 是 per-final-target HP restore（ID13 raw row 為
`dmg=70, +3=4, +4=0, mp=3, target=1`），但尚未把這個獨立 resolver、專用 renderer、SFX 或 UI 接入 remake；
在有對應 regression 前仍 fail-closed。

ID24 必須和上段嚴格分開。`funcs_1541f[24]` 雖然在 AI／自動執行的 `0x15311` 分派表中別名到
`0x22153`，使該表項把 **ID16** 傳入共同治療尾端；但玩家的 `0x1cff0` 明確將 `0x18` 直入
`0x2a6bd`，後者又以精確 ID24 分支至 `0x276ec`，完全不經 `funcs_1541f`。所以 table alias 不能當成
玩家 ID24 的效果或 MP ABI。玩家 `0x276ec` 的 state dataflow 已知：它選固定倍率 `15`，算
`trunc(actor.+0x48 * 15 / 10)`，逐 final target 扣 target `+0x4a` 後送入
`0x1c81f(target, amount)`；該共用 writer 再以其既有 90–99.9% RNG 路徑扣 `+0x40`、clamp 至零。
`0x276ec` 先經 `0x2b659`；該 event 對 ID24 以 `0x1ca89(actor,0x18)` 扣 record24 `+5` MP。原版為了
多段演出會先暫存 total delta、把 HP 復原，再以等份遞減回最終值；state-only remake 因此可一次套用相同
最終 delta。AI alias 的設計意圖與 native UI/SFX/timing 仍未以 remake regression 關閉，故不可冒充 ID16 heal
或接入 generic numeric executor。

IDs17..19 是第三條 transient-modifier family，亦不能交給 damage/heal executor。ID17
`0x226EA→0x22721`、ID18 `0x2282F→0x22866`、ID19 `0x22960→0x22997` 都在 final target loop 中先拒絕
已設 flag 的 unit：17/18 在 `+0x22/+0x23` 為零時設 `rand()%4+2`，並分別對 `+0x48/+0x4a`
加 `__CHP(value*0.15+1)` 的 toward-zero increment；19 對 `+0x24` 同樣設 duration，並對 `+0x4c/+0x4e` 各加 15。
這與 `0x1b750` 對 `+0x48/+0x4a/+0x4c/+0x4e` 的 derived AP/DP/HIT/EV synthesis 相容，因而撤回先前把
這些 offsets 稱為 screen coordinates 的斷言。duration 的 tick/clear、玩家可見 status 名稱、專用演出與
remake state/UI 仍未閉合，不能據此補出 gameplay names。

這一族的 MP transaction 有一個不可泛化的細節：jump-table ID17 的 `0x226EA` 與 ID18 的
`0x2282F` 都直接呼叫 `0x1CA89(actor,0x12)`，而 raw records 17、18 的七個 bytes 都是
`00 00 00 04 02 05 01`。因此目前只可證實兩者在這個版本有相同 MP debit；不得從 wrapper index
推導「所有 handler 都把自身 command ID 傳給 `0x1CA89`」。ID19 則明確傳 `0x13`。這不改變其
modifier writer／duration 證據，但阻止錯誤泛化 command transaction ABI。

IDs20..21 共享另一條「flag-present 才生效」route：`0x22A85/0x22BC6→0x22AA8→0x22AF6` 各以
command ID 20/21 扣 MP，對每個 final target 讀 `+0x25/+0x26`。該 byte 為零時只走失敗 display；非零時呼叫
`0x1C916(target,10)` 的既有 HP-restore writer、清零該 byte，並顯示結果。這證實 raw gate、clear 與
HP writer，但尚未命名兩個 status，亦未接 engine/UI。ID22 是不同的 `0x22BE1→0x22CDA→0x22D1B` route：final
target 的 `+0x27` 必為零、class `+0x20` 不得為 `0x19/0x1a`、且 `rand()%100<0x32`，才以
`0x1C81F(target,10)` 固定扣 10 HP、顯示 damage，並寫 `rand()%4+2` 至 `+0x27`。它須獨立追蹤，不能併稱為 cure
或依 raw offsets 猜測 status name。

這六個 transient bytes 的 decrement 已由 official IDA 釘死，但 gate 仍是 raw ABI：turn/camp phase driver `0x1A30B` 傳入 selector，`0x1A866` 只接受 `record+6 == selector` 且 `(record+5 & 1)==0` 的 record；不可把它改寫成 `Camp/OnField/Alive` normalized 條件。通過 gate 後依序對 `unit+0x22..+0x27` 的每個非零 byte decrement。任何一個 byte 變零時才顯示 expiry feedback 並呼叫 `0x1B750(unit)` 重算 derived fields；因此 ID17/18 的 AP/DP 增幅會在自己的 duration 歸零後由重算移除，其他 flag 不可因為共用 sweep 就被誤認為同一 status。這是 phase-based timer ABI，不是每次 action 或 frame 的 timer；status labels/UI icon 仍未命名。

Remake 已以 `Unit.NativeTransient[6]` 及 optional `NativeRecordByte5/6` 保留這段 raw ABI，並提供 bounded offset access（只接受 `0x22..0x27`）及 `State.TickNativeTransientsRaw(selector)`；FDFIELD b0→runtime `+6` 的 parser/exporter provenance 也已補上，缺少 raw gates 時仍 fail-closed。它刻意不呼叫 normalized `TickStatus` 或 legacy shared `BuffTurns`，也尚未自行接 campaign equipment recompute；expiry consumer/UI 必須先帶入 `0x1B750` 對應的資料依賴才能開放。

ID23 走 `0x1CFF0` 的 command-`0x17` special selector，不能套 generic two-stage target contract。其 handler
`0x2218A` 以 record23 扣 MP，並呼叫 `0x22253` 兩次：依 C stack ABI，第一次將 selected unit 的 runtime
`+0/+1` 寫為 `0xff/0xff`（以原座標作離場 indexed 演出），第二次直接寫為 selector cursor globals
`0x51CF9/0x51CFD`（並作入場演出）。因此已證實它是無 path traversal 的直接 grid-coordinate relocation；
落點 selection/legality、camera choreography、renderer 與 remake UI 尚未閉合，不能把它泛化成普通 move 或 generic
target effect。

IDs25..27 也已由 jump-table 閉合。ID25 `0x22C04` 以 record25 扣 MP，僅對 final target 已有
`record+5` bit `0x80` 已設的項目清該 bit，直接保留 raw clear writer（不命名 acted/action-complete）。ID26
`0x22CBF` 與 ID27 `0x22E41` 分別將 command ID 和 flag offset `+0x25/+0x26` 傳給與 ID22 同一
`0x22CDA→0x22D1B` application helper，所以同樣受 zero flag、class、`rand()%100<50` gate，成功固定扣 10 HP
並寫 2..5 duration。這使 ID20→`+0x25` clear 與 ID26→`+0x25` apply、ID21→`+0x26` clear 與 ID27→`+0x26`
apply 成為 direct code-pairs；仍不以此取代 UI/status icon 的獨立驗證。

`State.ExecuteNativeCommand25` 現是另一個 non-UI, fail-closed engine slice：它只接受完整 raw book/flags 的
generic two-stage target contract，完成 record25 MP debit 後，對 final targets 的 raw `+5` bit `0x80` 作精確 clear-if-set，
最後才套用 actor raw bit writer。`Unit.Acted` 只是目前 engine projection，不是 native semantic。target invalid、缺 flags 或 MP 不足都在 mutation 前拒絕；它不使用 normalized CastArea，
也未開 native grid/UI、renderer 或 message feedback。

`State.ExecuteNativeCommandApplication` 現對 IDs22/26/27 提供另一條 strict non-UI core：以各自 record 建 generic
two-stage final targets、扣各自 MP；每個 target 只在 raw `+0x27/+0x25/+0x26` 為零、class 不為 `0x19/0x1a`、
`rand()%100<50` 時固定扣 10 HP，並寫 `rand()%4+2` 到同一 raw byte。已有 duration/class gate 的 target 不會
mutation，但 handler 已成功時仍遵循原版 MP debit/actor raw completion writer；unknown ID、缺 raw data 或 invalid target 在
mutation 前拒絕。此 route 不映射 legacy Poisoned/Paralyzed fields，UI/renderer 仍 fail-closed。

`State.ExecuteNativeCommandClearRestore` 對 IDs20/21 亦已接 strict non-UI core：各自 record 只供 target/MP；
final target 的 raw `+0x25/+0x26` 非零時，才以 **record10** 的 raw damage 呼 `ApplyNativeCommandRestore`，再清同一
raw byte。restore 精確算 `amount*9/10 + rand()%100*amount/1000`、HP cap，並分開報告 rolled value 與實際
HP delta，避免把原版 display number 誤當 mutation。empty flag 不 restore，但 successful handler 仍 debit MP/complete
actor；不映射 legacy named status/UI。

`State.ExecuteNativeCommandHeal` 現對 IDs13..16 接 strict non-UI core：每個 ID 只使用自己的 raw record
完成 generic two-stage targets、MP debit、並以同 record `u16 damage` 走 `0x1C916` restore/cap；成功後才執行
actor raw completion writer。它與 ID20/21「借 record10」的 clear/restore route 明確分開，並不因共用 restore primitive 而推論
`0x1C4CC/0x1C2DA` 專用演出、SFX、message 或 UI 已完成。

### UI-03 native command family implementation matrix（E0/E1 status）

下表是 raw command table ID，不是 legacy `Spell.ID` 的別名。`engine` 只表示 strict non-UI state core；
沒有 UI/renderer evidence 的列不得由 command grid 開放。這個 matrix 是每次擴充 effect 時的 fail-closed gate。

| IDs | 原版已驗 dataflow | engine 狀態 | UI / renderer 狀態 |
|---|---|---|---|
| 0–8 | `0x2A6BD→2B659/1C75E`，two-stage final targets、MP event、numeric hit/HP | `ExecuteNativeCommandDamage`；ID0 有 target slice | 僅 ID0 grid target；compositor/SFX/post-resolution 未接 |
| 9–12 | direct/`0x21548` tail → `1CA89→1C75E` | `ExecuteNativeCommandDamage` | 未接；numeric 共用不代表演出共用 |
| 13–16 | `0x21AD9…0x22153→21B18→1C8ED/1C916` | `ExecuteNativeCommandHeal` | 專用 animation/SFX/grid confirm 未接 |
| 17–19 | `0x226EA/2282F/22960` modifier writers、`+0x22..+0x24` duration；`__CHP` toward-zero 已釘死 | `ApplyNativeCommandModifier` 僅 dispatch 到已閉合 raw word/pair branches；derived-base/equipment recompute、transaction 仍未接 | 未接 |
| 20–21 | `0x22A85/22BC6→22AF6`，clear `+0x25/+0x26` 並借 record10 restore | `ExecuteNativeCommandClearRestore` | 未接 |
| 22 | `0x22BE1→22D1B`，class/RNG gate、fixed 10 HP、write `+0x27` | `ExecuteNativeCommandApplication` | 未接 |
| 23 | `0x2218A→22253` special relocation selector | 未接；普通 two-stage target 不適用 | 未接 |
| 24 | 玩家 `2A6BD→276EC→2B659/1CA89→1C81F`：`actor +48 * 15/10 - target +4a`；AI table 另別名 `22153`，不可混用 | `ExecuteNativeCommand24`（state-only final delta） | multi-hit／SFX／native UI 未接 |
| 28, 29, 31 | 同玩家 `276EC` derived-strike route，倍率分別 20、12、18；各自 record MP/一般 two-stage selector | `ExecuteNativeCommandDerivedStrike` | multi-hit／SFX／native UI 未接 |
| 30 | `1CFF0→14818→115B6` 先確認 record+3 candidate；再以 saved cursor→confirmed cursor 進 `149F8`，`count=record+3-16`、X-first cardinal line、只收 enemy，最後 `2A6BD→276EC` default倍率18 | `ExecuteNativeCommand30`（顯式兩 cursor、state-only final delta） | native cursor lifecycle／multi-hit／SFX／indexed UI 未接 |
| 25 | `0x22C04` clear target acted bit | `ExecuteNativeCommand25` | 未接 |
| 26–27 | `0x22CBF/22E41→22D1B`，分別 write `+0x25/+0x26` | `ExecuteNativeCommandApplication` | 未接 |
| 32 | `2A6BD→27FC9→2111A→1C75E` numeric per-final-target；選單 MP gate已知但此 chain 未見 debit | 未接：transaction boundary未關閉 | 未接 |
| 33 | `27FC9` 先清每 target `+25..+27`，再 `211A4(...,800)` restore | 未接：transaction boundary、raw clear/restore contract待 regression | 未接 |
| 34 | `27FC9` 依序呼 `22721/22866/22997`，嘗試三種 modifier writer | 未接：transaction／baseline-recompute／x87 rounding boundary | 未接 |
| 35 | `27FC9` 依序以 IDs26/22/27 呼 `22D1B`，對 `+25/+27/+26` 三 application gates | 未接：transaction boundary；不可由三次 helper 推論 UI/status name | 未接 |

實作和測試必須以本表逐 ID 更新。不得因 record bytes、label 或 generic dispatch 可見，就把未知 ID 送進
legacy `CastArea` 或宣稱整個 native command menu 已完成。

AI boundary correction：在 `0x1598a` 的 spell-command path，`0x149F8` 目前只可稱為 target-candidate
builder；候選建立後才進 `0x15B77` 的 family-specific score branches。任何文件或 adapter 都不得把
`0x149F8` 直接命名成傷害／命中評分，也不得把 `unit+0x22..+0x27` 的 raw bytes 直接命名成 AP/DP/HIT/status。

Runtime bridge：`battle.AIPlan.NativeSpellCommands` 現只保存通過 raw `+0x27`、40-bit command mask、
36-record 與 MP gates 的 command IDs `>=0x10`；它不填 `SpellID`、不選 target、不評分，也不執行 effect。
缺少完整 `NativeCommandBook` 時回傳 nil，保持 legacy planner 與 native evidence 的邊界。

IDs32..35 的 `0x27fc9` 是一個獨立 multi-effect presentation wrapper，不能因為各 helper 已在其他 command
family 出現就直接重用既有 executor。direct static trace 已見：32 進 `0x2111a→0x1c75e`；33 對每個 final target
`memset(+0x25, 0, 3)` 後傳固定 `0x320` 給 `0x211a4→0x1c916`；34 連續呼
`0x22721/0x22866/0x22997`；35 連續呼 `0x22d1b(actor,26,...,+0x25)`、
`0x22d1b(actor,22,...,+0x27)`、`0x22d1b(actor,27,...,+0x26)`。先前「wrapper／helper 未見
`0x1ca89`」的負向斷言已撤回：`0x27fc9` 在 `0x28189` 進共同 presentation/effect routine `0x2b659`，而
`0x2b738..0x2b753` 會在其**載入 FIGANI container header 的 `byte+4 == 1`**時呼
`0x1ca89(actor, commandID)`。這個 resource 選擇已對 player class-19 path 關閉：command-learn row 19 提供
IDs32..35；原始可達來源是 portrait/visual group 4..7 的 optional class-change 與 group20 的初始 class19，
故 `group*3+1` 分別取 FIGANI #13/#16/#19/#22/#61。原 archive header byte4 依序為 `2/2/2/5/5`，全不等於 1；
而 `0x27fc9` 唯一 caller 是 `0x2a6bd`，`0x2b659` 是這條 presentation path 中唯一的 `0x1ca89` call site。
因此可證實這些**玩家可達 class-19 路徑不經已知 MP debit sink**，即使 record `+5` 的 selector gate 仍要求
76/52/28/36 MP。這不是「所有 runtime entity 免費」或 transaction rollback 的結論；AI／未盤點 runtime unit
visual group、其他 MP writer 與 compound effect ordering 仍未閉合，engine 保持 fail-closed。

command 0 的 selector boundary 也已縮小：`0x1cff0` 對一般 record（非 command `0x17`／`0x1e` special
branch）先以 actor cell、`record[+3]`、`record[+6]` 呼叫 `0x14818`，把可選中心的 unit indices 寫進 caller
stack array；`0x115b6(mode=record[+6], count, array)` 作 cursor/confirm。confirm 成功後，它以**確認游標格**、
`record[+4]` 和同一 target code 再呼叫 `0x14818`，此第二個 candidate array/count 才傳入
`0x2a6bd(unit, commandID, count, array)`。這證實 command 0 的 selector 是 **per final-effect candidate**，
而非 legacy UI 的單格 `CastArea` contract；`0x2a6bd` 對 IDs0..8 的 state writer 尚未閉合，不能從 final array
推論 numeric resolver。`0x14818` 的方向／形狀
與 target-code semantics 已有 raw closure：`dist<0x10` 經 native map/reach mask 決定可見格；`dist>=0x10`
使用十字線，半徑=`dist-0x10`（同 x 或同 y）。掃候選時必須是 alive/on-grid，並以 target code 對 runtime
`unit+6` 做精確 predicate：`0: ==0`、`1: !=0`、`2: !=1`、`3: ==2`。constructor `0x10c50` 證實 `unit+6`
直接來自 FDFIELD `b0` camp（敵=0、友=1、己=2），故四個 code 分別是 enemy/non-enemy/non-ally/own；
`dist<0x10` 的 mask 已閉合為 `0x4e040` 四方向 flood-fill：起點 budget=`dist`，grid flag bit `0x40` 阻擋、
bit `0x80` 使該步成本為零。雖然 callee 支援 terrain-cost row，command selector 固定呼叫 `0x4e555(0)`，而
EXE `word_61646` row 0 的 20 bytes 全為 `1`；因此這條 native command contract 不套地形加權，而是避障的
cardinal range（無阻擋時才等於 Manhattan）。

`battle.NativeCommandTargetCells`／`NativeCommandTargets` 已把**一次** verified `0x14818` 呼叫做成獨立資料層：
caller 必須提供精確原版 grid flags，缺失或長度不符即 fail-closed；不重用現有 `map.json.cost`，並明確選定 first
selection stage (`actor,+3`) 或 confirmed effect stage (`cursor,+4`)。它覆蓋 four-way flood-fill、bit40/bit80、
cross branch 與四個 camp predicates。`NativeCommandEffectTargets` 進一步要求 confirmed unit 確在 first candidate
list，才以其 cell 與 `+4` 取 effect list，固定 generic two-stage contract；UI 尚未接管這個流程，故不可自動替換
legacy cast。

`battle.NativeAttackCandidates` 另保存 `0x14237` 的 caller-specific geometry：它先以 item-row
傳入的 raw `(a4=mode,a5=innerRadius)` 執行同一 `0x14818` grid pass，僅在 `mode<0x10` 時排除
Manhattan distance `< innerRadius` 的 marker cell；`mode>=0x10` 保留 native cross branch，不套
inner-radius。這個 adapter 不把 `+0x0b/+0x0c` 命名成 range min/max，也不宣稱已完成 item-row producer、LOS、UI
或 attack effect。

Provenance closure：`0x4e040` 把 FDFIELD composition entry 的 `+3` 當 path budget，讀 `+2`（event word
low byte）作 block/zero-cost flags；它不是 terrain-control `byte0`。`export_engine_assets.py` 因此輸出
`native_target_flags` raw array。

`battle.Load` 現只在 map dimensions 與 array length 都精確吻合時載入 `State.NativeTargetFlags`；缺檔／舊 export／
壞長度皆保持 nil。這使 engine data layer 已可把它傳給 `NativeCommandTargets`，但 UI 尚未自動切換 native target
mode，避免未完成 command effect/confirm contract 時搶走 legacy playable path。

### Native command MP transaction（E0 verified, UI unbound）

`0x21227`（generic command 0 route）在 candidate array 建立後、逐 target effect 前呼叫 `0x1CA89(actor, commandID)`；後者以
`0x4e516(commandID)` 取 record，讀 `byte+5`，直接從 runtime `unit+0x44` 扣除。可達性 gate 已在 selector
先比較 `currentMP >= record+5`，因此扣除不應在失敗 confirm 發生。`battle.SpendNativeCommandMP` 保留這個交易
contract：只接受 raw 0..255 cost，MP 不足／無 unit 一律不變更。它刻意不吃 normalized `Spell`，也尚未接 UI，直到
native candidate confirm、command 0 effect sequence 與原版 renderer 都能一起驗證。

升級的 dynamic producer 現已閉合，但僅限資料層：native `0x1e292` 在 EXP 達門檻後增加 runtime
level，從 portrait growth row 的 `learn_idx` 經 `0x4e4a2` 查 `0x626b3 + idx*12`，逐一比對最多六組
`(required_level, command_id)`；命中就呼叫 `0x1d79c` OR command bit，並顯示 FDTXT_000 #587「學會了！」。
`docs/data/exe_tables/command_learn.json` 已保存 20 張 raw table（`FF/FF` sentinel 不轉成假資料）。
growth-row 的**raw selector**是 direct ABI：`0x4e4d1(unit+7)=0x620a1+unit[+7]*11`，第 11 byte 就是
`learn_idx`。constructor `0x10d7f..0x10efc` 已閉合 FDFIELD roster `b1→unit+7`；這是 battle
FIGANI/DATO selector 的來源，並不使它和 map `unit+2` alias。remake `State.GainExp` 因此只在已注入這個
editable table 時，於剛達到的 level OR exact
command bit；`remake/assets/data/command_learn.json` 是 runtime copy，`Game` 在每個新 battle state bind
同一張 table。legacy standalone `GainExp` 與 `Spells` 都不補造結果。

remake 的可編輯資料模型必須至少表達這些 raw facts，而非固定四個 ring action：

```json
{
  "unit_command_mask": [0, 0, 0, 0, 0],
  "commands": [
    {
      "id": 0,
      "mp_cost": 0,
      "native_record": { "raw_hex": "00000000000000" },
      "label": null,
      "target_contract": null,
      "enabled_when": []
    }
  ]
}
```

`unit_command_mask` 必須是固定五 bytes；初始 source 可只填前四 bytes，但 runtime mutation 不得截斷
第 5 byte。可見 command 的最小 gate 是「該 bit set 且 `current_mp >= mp_cost`」。`label` 已有可編輯、
逐 slot 的原始證據：`docs/data/command_labels.json` 保留 FDTXT_000 的 physical index
`0x1b9+command_id` 與 decoded text。它只表示 native renderer 讀到的文字；空字串或系統訊息 slot
不能被提升為可選戰技。`target_contract`、其他 `enabled_when` 在未有 E0 producer／effect evidence 時維持
`null`／空集合，renderer 必須顯示未解析或禁用狀態，不得將 ID 猜成 attack/spell/item。驗收 test 應涵蓋 bit 0、7、8、31、32、39
的展開順序、MP 邊界（cost-1/cost）與 unknown ID fail-closed；只有在 ID→label/render/effect trace 完整後，
才可淘汰現有 four-way ring approximation。

原版 selector `0x1d51d` 對這份展開 list 使用**每欄四列、欄數可變**的 grid：↑／↓在線性 index 上
-1/+1 並 wrap，←／右只在合法時 -4/+4；Enter／Space 在重新檢查 MP gate 後確認，Esc cancel。`0x1ceed`
renderer 已釘 x=`0x12+0x64*floor(index/4)`、y=`0x67+0x16*(index%4)`，並以 `0x1b9+command_id` 作
`[0x53a7d]` label index；該常駐 table 是 FDTXT_000，且 `0x1b9..0x1e0` 的 40 physical strings
已由 raw resource 逐筆匯出。故 UI state 至少要有 `selected_index`、`rows_per_column=4`、
`visible_command_ids` 與 `cancel_parent`，並以 command count 而非固定四個 action 計算邊界。這是
selector／label ABI，並不證明每個 ID 可達、圖示或 effect；那些欄位仍保持 fail-closed，直到
producer／effect call graph 補齊。

## 5. Campaign / postbattle 設計

每個 battle node 必須明確指定：

```json
{
  "on_win": "post_chNN",
  "on_lose": "lose_chNN",
  "persistent": ["roster_cleanup", "reward", "flags"],
  "next": "town_or_shop_or_preparation_or_ending"
}
```

`postbattle` 是一級可編輯 node，不是 `battle.on_win` 的隱含 callback。允許 `battle→town/rest`、`battle→shop`、`battle→church`、`battle→preparation`、`battle→ending`，也允許連戰區間明確沒有 town/shop。每個 transition 都需有 handler offset／資產／攻略旁證的 evidence list；只有攻略證據時仍標 E3。

Persistent party 的 transaction 順序固定為：結算結果 → reward/drop → transient status cleanup → MaxHP/MaxMP／equipment recompute → roster save → branch flags → 下一個 node。任何中途資料缺失都停在錯誤畫面，不自動跳到下一戰。

`syncPartyFromBattle`／`applyPersistentStats` 現在會在 raw provenance 存在時保存 `NativeRecordByte5/6`，並以
byte5 bit0 決定戰後 HP refill；缺 raw 才退回舊的 `OnField/Alive` projection。這個 fallback 仍是 E1，不能當成
原版 `0x11506` byte-for-byte compatibility；LOADCH 完整 raw record materialization 後才可移除。

### 5.0.1 Handler predicate boundary（E0 slice）

可編輯 handler 的 `if` 不是自由表達式。每種 predicate 都必須對應已反組譯的 native helper，並在 runtime 缺資料時 fail-closed。現有 `any_unit_inactive` 是 remake 對「指定 caller 讀取 runtime `record+5 & 1`」的投影名稱，不是宣稱全域生命欄位；`roster_has(char_id)` 對應 `0x33499` 對永久我方名冊 `[0x53bf7]` 的 `record[+8]` 掃描，`char_id` 僅限原版永久玩家 `0..31`，不得改以暫時出戰隊伍、portrait、NPC 或 story actor 推論。

目前 `cmd/fd2` 的 `any_unit_inactive` 執行器仍在缺少 `HasNativeRecordByte5` 時使用 `OnField/Alive` 作相容 projection；這是明確的 E1 gap，不是 native parity。constructor、已知 damage/death writer、revive writer 與 `deactivate_unit` 已開始同步 raw byte5；仍要補完整 LOADCH／所有死亡入口的 provenance，並讓 strict binding 缺 raw 時 fail-closed。在此之前，ch01/ch02 authored handler 只能算可測試腳本切片。

ch14 pre-handler (`0x334d9`) 是已閉合的動態文字例：`0x33499(12)` 的回傳經 `xor al,1; mul 3` 得到 FDTXT_015 base index。因此有 char_id 12 時依序播放 index `0/1/2`，否則 `3/4/5`；中間仍依原順序 pan `(24,17)`、呼叫 acting 48、最後 focus slot 0。資料以 `handlers/ch14_pre.json` 的兩個結構化 `if roster_has` 與 address-keyed binding 表達，保留六個原始 dialog call-site，避免在 runtime 猜 EBX/EAX。

`layout_units` 是另一個必須 address-keyed 的 handler primitive。Official IDA 9.4 定義 `0x233c6..0x2345b`，並確認它被 15 個不同 post-handler caller 共用；其 call-site supplies X/Y byte arrays、slot range、pose source、optional special-slot placement，以及 focus/camera inputs。每個可播放 binding 必須保存完整 materialized `(slot,x,y,pose)` 與 camera 值；不得把任一 caller 的 table 位址、長度或 special-slot rule 泛化給其他關。缺少任一欄位的 layout 保持 compile issue／runtime fail-closed。

`0x24618..0x24754` is a separate map-transition compositor, not an actor `acting` decoder. Its callers include post-handler functions `0x33af1`/`0x33c9d`; it renders a 13×8 terrain region to an offscreen buffer, performs exactly nine strip-composite passes with a caller-supplied progression, then performs palette updates from 0 through 62 in steps of 2 (4 ms each). Its first two arguments feed tile geometry (`arg1*24+12`, `arg2*24+16`); the third starts a radial radius and the fourth increments that radius per pass. `0x22046` supplies a fixed scale of 16 to its two `0x219ad` radial LUT passes and derives its final rectangular radius as `trunc(radius*1.6)`. Its remaining constants are a pass row range `[start_y,end_y)=[0,192)`, not a source coordinate or blit width; the editable fields retain those names. A playable binding must either supply a verified transition adapter or fail closed—never lower it to `act`, `pan`, or an arbitrary fade.
The `0x22046` inner order is now executable as a raw primitive: `fdother.BuildNativeIndexedTransitionPass` preserves its scale-16, second-radial start row, and final-rectangle `a2` alias; `fdother.ApplyIndexedTransitionPass` validates both radial specs and the final centered rectangle before applying the first LUT remap, requiring the caller-owned `0x127a9` redraw callback, then applying the second remap and rectangle LUT. `indexedmap.BuildNativeTerrainCells` now materializes the exporter’s raw FDFIELD tile/high-byte arrays, and `indexedmap.ComposeNativeTransitionFrame` supplies the verified terrain→unit/foreground→pass→312×192 viewport composition with atomic work/VGA commit when all raw banks and controls are supplied. `loadNativeMapAssets` now also requires FDOTHER#3 LUT entries 1..9 before exposing the all-or-nothing native map bundle. `fdother.BuildNativeIndexedTransitionSchedule` preserves the outer nine-pass FDOTHER#3 LUT index order `9..1`, caller radius progression, 5ms pass delay, 500ms tail hold, and palette deltas `0..62` step 2 at 4ms; `NativeIndexedTransitionLUT` resolves those raw indices only against the 256-byte bank entries. Campaign runtime asset binding, palette timing, and Ebiten scene presentation remain explicit gates.

Native battle-local event state is a separate editable boundary. `[0x53ad5]` points to a 32-byte table, but an index must not be named from a single reader. For example, entry 12 is set only on the successful `0x356bc` path after item `0xd0` is consumed; that path also runs its presentation, spawns FDFIELD group 1, JOINs char 31, and displays FDTXT #4. ch25 post later reads entry 12 to select its FDTXT base (`+5` or `+8`). Official IDA 9.4 identifies `0x356b7..0x35822` and eight control-flow xrefs from generic event/UI dispatcher functions (`0x117e7`, `0x16f55`, `0x190ac`, `0x1a813`, `0x1aa1d`, `0x1d80b`, `0x1d8ba`); this does **not** prove a ch25-only trigger or a map-local event coordinate. A future binding may expose this as an address/index-backed event-state predicate only after its persistent/runtime representation and both branch arms are complete; it must not substitute a treasure, unit, or generic party predicate.

Inventory gates are distinct from item-consuming event commands. Native `0x24b14(item)` scans only runtime slots `0..15` through `0x31860` and returns found/not-found; it neither filters camp/activity nor removes an item. In ch26 post, `0x24b14(0x64)` selects the sky-key success arm; that arm contains no `0x1b8e7` call and only later performs sync/chapter increment/persistent cleanup. The missing arm is a separate ending presentation path. Therefore an editable `inventory_gate` must preserve item `0x64`; it may not be lowered to a recipe, reward, or consume action.

`0x25052(start,delay_ms)` is an independently editable palette-ramp primitive: it emits inclusive descending `0x11df2(0,255,start..0)` updates, waiting after each update. The ch26 success arm calls `(5,80)`, `(4,80)`, `(3,80)`, then `(2,80)`, `(2,80)`, `(2,80)` interleaved with native waits. This is not a black fade and must preserve every delta including zero; compiler input is restricted to immediate `start∈[0,63]` and non-negative delay.

`0x1f882` is a separate native palette fade-out, not a timing/vsync helper: it initializes `ebx=0`, then emits 64 inclusive `0x11d40(0,255,ebx)` steps with a 2 ms wait after each. Unlike `0x25052`, `0x11d40` applies the native darkening path rather than `0x11df2`'s signed RGB delta. The handler compiler preserves this as `native_palette_fade_out{start:0,end:63,delay_ms:2}`; until the indexed DAC adapter exists runtime explicitly fails closed, and it must not silently become a generic story fade.

### 5.1 目前 editable graph audit（E1，不等同原版 E0）

`remake/assets/scenarios/campaign_full.json` 的 30 個 battle node 已逐一展開
`on_win`，並沿著 post/cutscene 節點走到第一個可操作戰間節點。這張表是目前 remake
的可編輯基線；只有標成「native 待核」的項目仍不可宣稱已還原原版 handler。

| battle | 勝利後第一個戰間節點 | 路線型態 | native 證據狀態 |
|---|---|---|---|
| 01 | `story_ch02` → `town_ch02` | 劇情→城鎮 | E0 hub gate；逐章文字／E2 待核 |
| 02–20 | `story/postbattle_chNN` → `town_ch(NN+1)` | 劇情／持久化→城鎮 | E0 hub gate；逐章 handler／E2 待核 |
| 21 | `story_ch21_post_sky_key_intro` → `inventory_recipe_ch21_sky_key` | 劇情→合成 gate（非直接下一戰） | gate E1；native 待核 |
| 22–24 | `postbattle_chNN_persist` → `preparation_ch(NN+1)` | 持久化→整備 | E0 preparation route；逐章 handler／E2 待核 |
| 25–26 | `postbattle_chNN_persist` → `town_ch(NN+1)` | 持久化→城鎮 | E0 hub gate；逐章 handler／E2 待核 |
| 27 | `inventory_gate_ch27_sky_key` → success/missing branch | 道具 gate→分支劇情 | gate E1；native 待核 |
| 28–29 | `postbattle_chNN_persist` → `preparation_ch(NN+1)` | 持久化→整備 | E0 preparation route；逐章 handler／E2 待核 |
| 30 | `ending` | 終局（不接下一戰） | ending renderer fail-closed |

因此不能以「battle node 有 `on_win`」推導下一節就是下一戰；town、shop、church、
preparation、inventory gate 與 ending 都必須留在 graph。下一個 SDD-2 子任務是以
原版 handler offset／DOSBox 操作逐列補 E0/E2 證據，並為每列加入 save/reload regression。

### 5.3 Native postbattle hub gate（E0，IDA 9.4）

`0x2d093` is the concrete gate reached from the postbattle loop before the next-battle table. Its raw selection byte `[0x5412b]` dispatches to the recovered scene callers: option `0` calls `0x2fc85` (inn/hotel), options `1` and `3` call `0x2e341` (the weapon/item/secret-shop family), and option `4` calls `0x3072f` (church). Option `2` is the preparation/leave route: it presents the save/confirm text, then admits the party to `0x318ad`, whose cap is 15 before the late chapters and 19 afterwards. The Hex-Rays bodies close the subscene boundary further: `0x2e341` selects raw resource `12`, `29`, or `63` for the ordinary/alternate/secret shop branches, dispatches its service choices to `0x2f0b0`, `0x2f642`, `0x2f883`, or `0x2f8ea`, and fades back to the hub; `0x2fc85` loops its hotel choices through `0x2ffa5`, `0x30012`, `0x301f4`, or the character/preparation path using `0x197e5`, then likewise fades back. These callee labels remain address-level names where their service semantics are not independently proven. Each facility path returns through the hub and the caller restores track 10; the next-battle BGM table is not selected until the outer `0x25de5` loop resumes. Docker raw-table reading confirms `byte_526b9[22..24]` and `[27..29]` are `1`, while `[0..21]` and `[25..26]` are `0`; in `0x2cad7`, nonzero entries take the preparation-only path and zero entries enter the selectable town hub. Chapter indexing is the native next-battle index, not the human-facing battle number. Exact per-chapter text, cursor art, and DOSBox visual timing remain E2 work, but the graph must not collapse these proven hub/prepare branches into a direct next battle.

### Church service selector input/transition boundary (IDA E0, 2026-07-27)

Official IDA 9.4 decompilation closes the previously missing selector edge:
`0x3072f` calls `0x2d669(0)` to open the church menu, then `0x2d7bd()` to read the
selection. `0x2d7bd` accepts raw scancodes `75` (left) and `77` (right), updates
`[0x53c57]` with four-entry wrap (`0→3`, `3→0`), returns `1` on Enter/Space
(raw `28`/`57`), and returns `-1` on Escape (`1`). It does not use the up/down
bounded list contract used by character selection. After confirmation, the
caller dispatches raw selection `0→0x2ffa5`, `1→0x2f8ea`, `2→0x30dc3`, and
`3→0x31385`; these remain address-level service branches unless their own
callee semantics are independently proven.

`0x2d669` is the indexed church-menu transition: it snapshots a 64000-byte
buffer, clears a 20×104 region at the native menu origin
`buffer + 320*(169+i) + 201` with byte `0x4a`, then performs four
direction-dependent cell blits for each of four passes. The copied cell-offset
bank at `0x526da` is the signed sequence `[-39,-13,13,39]`; the transition
uses divisor `4-j` while opening (`a1==0`) and `j+1` while closing. Each blit
uses the native width/stride argument `0x140`, restores the buffer between
passes, and finally restores the source frame when opening. This is evidence
for a native transition/compositor boundary, not proof of a particular menu
layout or service label. The remake therefore adopts only the verified
left/right selector ABI and keeps the menu art/service names fail-closed.

The two raw service branches share a second selector contract. `0x2e6b8` is a
roster/list selector used by `0x2ffa5` and `0x2f8ea`: left/right move by one,
up/down move by two, movement is bounded (no wrap), and the visible window
scrolls in two-entry increments once the cursor crosses its six-entry window.
Enter/Space return `1`, while Escape returns `-1`. `0x2df6b` is the same
bounded two-column selector for a caller-supplied list count and calls the
caller renderer after movement. These helpers are input/layout evidence only;
their caller-owned list entries do not establish service names.

`0x2f8ea` then builds a caller-local list by scanning the selected runtime
record's eight inventory cells and retaining cells whose signed flag byte is
non-negative. This includes both `0x40` equipped cells and `0x00` ordinary
cells; only bit-7-set (`0x80`) reserved cells are excluded. It enters a
second `0x2e0bd`/`0x2df6b` list, confirms through another selector, performs
the caller's `0x2f4c6` indexed feedback and `0x2d516` amount path, then invokes
the native item removal/recompute sequence. The `0x1bb8c` call and amount
meaning are not independently named here; remake must not lower this branch
to sell, donate, equip, or any other normalized service until that writer is
closed.

The writer is now closed at raw level: `0x1bb8c(destination,item)` scans the
destination's eight two-byte cells, finds the first cell whose flag byte is
negative, writes flag `0` and the supplied item byte, and returns `1`; a full
destination returns `-1` without mutation. In the `0x2f8ea` topology the
source cell is removed by `0x1b8e7` before this insertion, so the proven
operation is a source-to-destination inventory transfer with an unequipped
destination cell. The item ID and higher-level menu label remain raw; the
remake exposes `TransferNativeInventoryItem` as an atomic adapter but does
not silently wire it to an unnamed church menu branch.

The remake now exposes this proven transfer topology as an explicit church
mechanics slice: `transfer_source` → `transfer_item` → `transfer_dest`, with
bounded two-column cursor movement and atomic source/destination update. Its
source eligibility uses constructor-derived raw flags when `inventory_slots`
provenance is available; legacy JSON without that provenance retains a
conservative projection and is not native parity. Malformed or missing raw
provenance remains fail-closed for the native gate.

The other raw branch, `0x2ffa5 → 0x17aed`, is a separate boundary. Its body
allocates/copies three 64000-byte indexed buffers, calls `0x17e0b` to stage the
selected record, calls `0x16c57(0)` for the input wait, conditionally renders
the command/overlay path through `0x1ceed`, and executes repeated buffer
restore/redraw passes. The body contains no direct persistent roster,
inventory, gold, HP, or class writer. This rejects the previous "ability
service" wording, but does not assign a high-level label: raw index 0 remains
an unnamed information/presentation boundary until its renderer/text contract
is independently closed.

### 5.2 Native campaign loop ordering（E0，IDA 9.4）

Official IDA pseudocode of `0x25de5` closes the outer ordering that the editable graph must preserve. After `sub_25ebb` returns the battle-driver result, the loop calls `sub_117e7`; when global phase `[0x53ecc]==1`, it calls the fixed chapter-1 interlude `0x22e5c`, clears the phase, and continues. When `[0x53ecc]==2`, it first stops BGM, calls the chapter-indexed post-handler table `funcs_25e23[dword_53c03]`, and only then calls `sub_2cad7()`. If `sub_2cad7()` returns nonzero, the loop exits through the terminal/return path; only when it returns zero does the loop call the second chapter-indexed table `funcs_25e3a[dword_53c03]`, select `byte_51e63[dword_53c03]` for the next battle BGM, clear the phase, and resume the driver. The exact table entries and `0x2cad7` visual/menu labels remain separate evidence work, but this call order is enough to reject any generic `battle → next battle` shortcut. A remake transition must retain an explicit post-handler/menu gate before a next-battle node, even when the high-level node is still opaque.

## 6. Reverse-engineering re-audit workstreams

### 6.0 Runtime/UI boundary（2026-07-26 audit）

現有 Ebiten runtime 已具地圖、游標、單位 HUD、四向 action shell、legacy spell list、dialog、town/shop/
church/preparation 與 save/load；這是 E1 playable shell，不是「UI 尚未存在」，也不是 original renderer。
`57-ui-evidence-matrix.md` 將它分成 UI-01…UI-12：其中 native command grid 的 layout/input/raw mask 有 E0
slice，但 item use、native target/effect、indexed transition、`unit_present`、four-slot native save UI 及大部分
DOSBox pixel differential 仍未閉合。所有文件提到 legacy `CastArea`、ring 或 `spell.json` 時，均只可稱
normalized/editable approximation，不能用來提升 native command 的完成度。

SDD 通過後按以下順序重審，不先補 renderer 猜測：

1. **Boot/menu/UI dispatch**：以 Ghidra/IDA 建立 call graph、keyboard scan、menu item table、resource loader；Docker Capstone 只作可重跑交叉驗證。
2. **Resource provenance**：把 FDOTHER/FDTXT/DATO/FIGANI/TAI/FDFIELD 的 loader、entry、palette、stride、clip 寫成 machine-readable bindings，並與 UI contract 對應。
   `0x22253` 會載入 FDOTHER immediate `0x51`（十進位 **81**）的 nested `LLLLLL` entry（outer 18710 bytes、directory first-word `0x12`；nested payload #1 為 9782 bytes），但完整 stack-slot trace 顯示此 local pointer 不傳入 `0x22470`／`0x22547`／`0x22656`，尾端只 free；它是 resource lifetime，**不是** pixel/frame source。`0x11eee` 是背景／tile redraw；boot 載入 FDOTHER #3 到 `0x53a6d`。FDOTHER #6 是 230-entry `LMI1` bank：`0x22470` 先以 entries `0x72..0x7c` 做 **11** 次 LMI present/tick（#0x72=12×21，#0x73..0x7b=20×22，+0x1f6=#0x7c=24×23）；`0x22547` 再倒序 #3 entries5→0 做 **6** 次 10ms remap present＋2 ticks；最後 `0x22656` 以 #3 entries0→9 做 **10** 次 remap present/tick，合計 27 次 present。其共用 compositor `0x22046` 有六個靜態 caller，並非只屬於 unit presentation：它兩次呼 `0x219ad`，後者以 `sqrt(radius²-dy²)*scale/10` 的 scanline span 作 in-place LUT remap；接著自身對第二個矩形範圍做同一 LUT remap。`__CHP` 已確認以 temporary x87 control word 的 toward-zero `frndint` 實作；`fdother.ApplyRadialLUTRemap` 和 `ApplyCenteredRectLUTRemap` 現分別保存 strict-radius 與 final-rectangle 的純 indexed ABI。兩 radial pass 中間的 `0x127a9→0x127e0` 會掃 object roster，經 `0x4deda/0x4de56` 寫同一 `0x53a49` buffer，故不得合併／略過。各 caller 的畫面語意與 Ebiten adapter 都未閉合。先前 6-frame `unit_present` schema 不完整，禁止接 runtime。`internal/fdother.ArchiveEntry` 僅驗證 #81 nested raw boundary，不可把它寫成 layout、音訊或 frame table。
3. **Battle interaction**：追 action menu enable gates、weapon reach、spell inventory/targeting、end-turn 判定、HUD anchor；每一項先找 caller/data flow，再改 Go。

   Renderer boundary addendum: `0x127e0` chooses a camera-relative 24×24 object sprite and writes the current indexed buffer through either `0x4deda` (raw indexed RLE) or `0x4de56` (RLE palette-remap path). `0x127a9` then calls `0x129ec`, which performs further map/object overlay work on that same buffer. `0x129ec` iterates visible runtime units after their sprites, calls `0x12ac6` for the unit cell and its upper neighbour, and during a nonzero `unit+4` movement offset redraws one pose-dependent neighbour. `0x12ac6` only draws field entries whose resolved tile flag has bit 7 set, to `buffer+0x8088+(y-cameraY)*24*456+(x-cameraX)*24`; bit `0x08` adds `2*flip`, and its FDSHAP descriptor lookup is deliberately the offset-table entry `index+1` (`base+0x0a`). Its raw/alternate tile branch depends on the field entry's byte `+3`. The alternate `0x4dd52` branch is now closed as the same 24×24 four-mode RLE decoder with an explicit caller-supplied 256-entry index table, not an unknown visual effect. Loader `0x10937..0x1096f` obtains the image descriptor base `0x53a5d` and flag table `0x53a69` as the selected FDSHAP even/odd resource pair via `0x111ba`. `0x12ac6` selects its FDOTHER #3 LUT through the same `0x51a97[0x53c1f]` terrain phase table as `0x11eee`; that selector is closed. This is evidence for a foreground-terrain occlusion layer, not merely a redraw marker. The full scheduler remains incomplete, so an Ebiten adapter cannot claim native presentation.

   Asset boundary correction: FDSHAP four-mode decoding retains a separate opacity mask, and `export_engine_assets.py` writes RGBA `tileset.png` for the raw `0x4deda` preview path (opaque index 0 remains opaque). This is **not** a universal native compositor: `0x11eee` selects raw iff composition entry byte `+3==0xff`; otherwise `0x4dcc6` maps opaque source indices through a supplied LUT and, critically, maps mode-3 spans from the existing destination pixel through that LUT. The exporter now preserves raw `native_tile_blit_modes` (the FDFIELD event-word high byte) so a future indexed adapter can distinguish these branches; it must not substitute alpha for the LUT branch or infer the `0x129ec` schedule.

   Native terrain-frame contract: for each visible FDFIELD composition cell, `0x11eee` masks the tile ID to 10 bits and reads the selected FDSHAP terrain-control byte. Frame selection is priority-ordered: bit `0x08` adds `2*flip(0x53a40)`; otherwise bit `0x10` adds truncating `0x3c0b/2`; otherwise bit `0x04` adds `flip(0x53a40)`; otherwise it uses the base tile. It then performs the raw/LUT branch above. These are raw flag semantics only—names such as water/fire animation are not inferred.

   `fdicon.NativeTerrainFrameIndex` is the strict pure form of that selector: it accepts only a 10-bit tile and flip 0/1, preserves the native priority and signed toward-zero division, and returns a descriptor index rather than a rendered image.

   `fdicon.Bank.BlitNativeTerrainCell` composes the verified single-cell path: it selects the FDSHAP descriptor index, then uses raw `0x4deda` only for FDFIELD entry byte `+3==0xff` or `BlitLUT` otherwise. Its regression covers both branches and the mode-3 destination remap. It deliberately has no camera loop, LUT-phase selection or `0x129ec` foreground pass.

   `fdicon.Bank.BlitNativeTerrainRegion` now supplies the corresponding pure `0x11eee` row-major visible-cell pass. It accepts raw composition cells, the raw four-byte-per-tile FDSHAP control table, map origin and explicit destination/LUT; it validates map/control bounds before calling the single-cell compositor. `0x11cac` establishes the normal caller ABI as destination `buffer+0x8088`, stride 456, width 13, height 8, camera X/Y, followed by range overlay, unit layer, then foreground overlay. The pure region adapter does not schedule those later passes.

   Native range-overlay contract: `0x122dc` dispatches raw mode 1..5 to an **ordered** table of `0x126f7(x,y,descriptor)` calls. `fdother.NativeRangeOverlayPlacements` preserves all 1/1/5/13/21 calls respectively, including the mode-3 centre descriptor `14` and the mode-5 repeated coordinates with distinct descriptors; it must not normalize them into an inferred diamond or ordinary movement range. `0x25c7d..0x25c92` loads FDOTHER #1 to `0x53a4d`; real asset inspection fixes its `{24,24,20,u32 offsets[]}` four-mode RLE bank and `0x126f7` selects `base + *(base+6+4*descriptor)` before direct `0x4deda`. `fdother.DecodeNativeRangeOverlayBank` requires all 20 entries and `BlitNativeRangeOverlay` reproduces the 456-stride base `0x8088`, 24-pixel camera-relative placement and pre-blit camera clip. Mode 6 is not a draw table: `0x108f0..0x10932` establishes `[0x53a51]` as raw FDFIELD `{i16 width,i16 height,cell[4]}` and `0x4dbfc` initializes each cell byte+3 to `0xff`; its write therefore clears precisely that selected cell's event-high/raw-blit-mode byte. `ClearNativeRangeOverlayMode6FieldByte` preserves that raw mutation without assigning it a gameplay label. Native framebuffer lifetime and the runtime/Ebiten presentation adapter remain unclosed, so GUI range highlights are still not native-equivalent.

   Steady-frame scheduler boundary: `indexedmap.ComposeFrame` is the first executable owner of the recovered normal order `terrain → range → unit → foreground → HUD → 0x11eb0 copy`. It requires an explicit HUD callback; omitting it fails before mutation, so callers cannot accidentally present a frame that skipped the native HUD position. `ComposeNativeFrame` is the non-approximation form: it binds `NativeFrameInput`'s recovered HUD resources/raw input directly to that position. Both compose into a private 456-stride work clone and only commit work/VGA after all layers and HUD succeed; final copy is the verified 320×192 source `work+0x8088` to 320-stride indexed VGA. This closes an indexed orchestration primitive, not an Ebiten adapter: map/resource lifetime, palette DAC and presentation timing remain separate gates.

   `fdicon.NativeForegroundRedrawEligible` plus `NativeForegroundRedrawCells` are the corresponding pure `0x129ec` schedule primitives. A slot must pass `unit_inactive` (`unit+5 bit0==0`) and the raw `0x1f183` gate: `unit+7==0x1c` passes; other `unit+7` values are excluded for class `0x13` or race `4/5` (these values are deliberately not given visual/gameplay names). This corrects an earlier mistaken use of the word “group”: map sprite group is `unit+2`, not this field. Eligible slots then preserve the exact ordered calls `(x,y)`, `(x,y-1)`, then only for nonzero `unit+4` one neighbour selected by pose: 0→`(x,y+1)`, 1→`(x-1,y)`, 2→`(x,y-2)`, all other values→`(x+1,y)`. The coordinate helper intentionally returns off-map coordinates too, because native `0x12ac6` performs its own visibility/bounds gate. Neither primitive invokes a GUI renderer.

   `fdicon.Bank.BlitNativeForegroundLayer` now supplies the matching steady indexed layer. It applies those raw unit gates and schedule in roster order, then reproduces `0x12ac6`'s camera interval, foreground-control bit7, bit8 flip adjustment, `index+1` descriptor selection, `buffer+0x8088` placement, and raw versus LUT-transparent branch. It preflights the full selected set before a write. Coordinates that would index outside the supplied editable map are intentionally skipped rather than reading unchecked native memory; that is an explicit fail-closed adapter boundary. Scripted `0x1366a` composition, range overlay, HUD and VGA present remain separate.

   `fdicon.Bank.BlitNativeUnitLayer` now closes the intervening steady `0x127a9→0x127e0` layer as a pure indexed pass. It accepts only raw unit subset fields (`+2` slot, `+3` pose, `+4` movement offset, `+5` bit7 palette branch, `+0x26` base-frame flag) plus the preceding inactive gate, exact camera extents, global idle/moving cycles and pixel shift. It preserves the native visible bounds `X∈[camX−1,camX+maxX]`, `Y∈[camY−1,camY+maxY+1]`, negative-offset skip, slot→key pointer resolution, and raw versus palette-band blit. All selected entries are preflighted before the destination changes, so malformed editable selector input cannot yield a partial indexed frame. It is deliberately not an Ebiten adapter and does not schedule foreground/HUD/present.

   Caller boundary correction: native foreground is not confined to the steady `0x127a9` redraw. Official IDA 9.4 shows `0x1366a` also calls `0x129ec` after its step-specific `0x11eee` base-terrain redraw and per-slot `0x127e0` sprite loop, before `0x11eb0` and the later present/redraw calls. This path mutates runtime `unit+3` from its scripted step data while composing frames. The 106-entry `0x1366a` input bank is already decoded as editable acting frames; this evidence adds its indexed layer order. A future adapter must therefore schedule foreground occlusion in both steady and scripted-step frame paths. The final native presentation stages remain unmodelled.

   `0x11eb0` is now closed as a plain row-by-row `memmove`, not an unknown effect: the standard `0x11cac` caller copies width 320 × height 192 from `buffer+0x8088` (source stride 456) to VGA `0xA0504` (destination stride 320). `fdicon.CopyNativeIndexedRegion` preserves that explicit indexed-buffer contract with bounds validation; it deliberately does not allocate VGA memory or claim an Ebiten presentation adapter.

   Selected-unit HUD boundary: `0x11cac` calls `0x1acf3` after terrain, range and unit/foreground layers but before the viewport copy. `0x1acf3` returns without drawing unless both raw display bytes `0x51aab` and `0x51aac` are nonzero. It first calls `0x12e38` on cursor globals: that helper is a terrain-cell resolver, yielding FDFIELD tile word masked to 10 bits, event low five bits, and the selected four-byte FDSHAP control record; `fdicon.NativeTerrainCursorInfoForCell` preserves this raw contract. Its control byte+1 indexes the verified `0x51a12`/`0x51a2a` terrain AP/DP table: 0→(+5,0), 1/5→(0,0), 2/3→(-5,+10), 4→(-5,-5). `battle.Load` derives the same byte per validated map cell and combat consumes it directly. The now-closed panel geometry is FDOTHER #5 LMI1 #130 (69×34) at `buffer + stride*157 + x`, terrain icon at `+6`, AP signed-number path at `stride*8+0x2b`, and DP at `stride*19+0x2b`; `0x1aeb1` chooses raw directory entry #0x83 (6×7) for a nonnegative table value or #0x84 (6×5) for a negative one, makes the value absolute, then calls the native decimal digit path at `+8`. These are literal hexadecimal immediates in `0x1aeb1`, not decimal 83/84. The resource artwork's semantic label remains unassigned. `x` is the raw static anchor (initial 1). Direct Docker Capstone reading of `0x1ad2a..0x1ad5f` confirms it is persistent: only `0x53abd>5 && 0x53ab9<3` writes `0xf2`; otherwise only `0x53abd>5 && 0x53ab9>9` writes `1`; all other pairs retain the prior global. `indexedmap.AdvanceNativeMapHUDAnchor` preserves that raw state machine without naming either coordinate. The optional unit icon is FDICON group `unit+2 * 12 + rawState`, with raw state 3 aliasing 1, blitted at `stride*5+6`; its current/max HP words `+0x40/+0x42` feed `0x1875d` at `stride*21+9` in raw mode 3. `fdicon.NativeMapHUDUnitFrameIndex` preserves only that selector. The global and icon/HP semantic names remain raw. Therefore the current map HUD is explicitly an approximation and must not reuse the full-screen battle-panel asset as proof of native equivalence.

   `indexedmap.BlitNativeMapHUDPanel` is the executable first subpass only: it requires both recovered raw gates, validates FDOTHER #5 entry #130's 69×34 geometry, and transparently blits it at `NativeMapHUDLayoutFor(anchorX,456).Frame`. **Codec correction:** #130/#0x83/#0x84 are directory entries sent to `0x4e63d`; `DecodeNativeMapHUDFrames` uses `ParseLMI1FrameEntry`/four-mode `Frame`, not ordinary `ParseLMI1` (`0x4e916`) cells. Terrain/unit icons and digits remain explicitly out of this primitive; callers can use it as the required HUD callback in `ComposeFrame` without pretending the partial panel is a complete native HUD.

   `indexedmap.BlitNativeMapHUDSignedNumber` closes the immediately following `0x1aeb1` selector boundary: it accepts an already-recovered number origin, uses #0x83 (6×7) for `value>=0` or #0x84 (6×5) for `value<0`, then invokes a mandatory decimal callback at `origin+8` with the absolute value. The primitive commits atomically only after that callback succeeds. It neither supplies a decimal font nor decides the table value, AP/DP source, or number meaning; those remain caller/data-flow work.

   That callback is now closed for this call-site by `BlitNativeMapHUDTwoDigitNumber`: `0x1aeb1` supplies `0x187d6` glyph base `0x1f` and fixed width 2; `0x187d6` patches `%0.5d` to `%0.2d`, then calls `0x16886→0x4e63d` for glyph directory entries `0x1f+digit` at offsets `origin+8` and `origin+14`. Real FDOTHER #5 confirms digit entries #0x1f..#0x28 are 6×8 except #0x20 (digit 1) at 5×8; advance is nevertheless six pixels. The adapter rejects values outside `0..99` rather than silently rendering native's truncated first two characters. Number source/meaning remains unassigned.

   Terrain-icon subpass closure: immediately after `0x12e38(cursor)` fills its eight-byte local, `0x1acf3` reads local word0 (the masked 10-bit terrain descriptor), uses it as the selected FDSHAP bank offset-table index, and raw-blits through `0x4deda` to panel `+6`. `indexedmap.BlitNativeMapHUDTerrainIcon` preserves exactly that raw descriptor input and destination, validating only editable bounds; it does not reuse texture previews or name the terrain category.

   Unit-icon subpass closure: if `0x12c0d(cursor)` returns a runtime unit index, `0x1acf3` uses `unit+2` as the global selector-cache slot, reads the raw global state counter (3 aliases 1), resolves that cached twelve-frame FDICON block and raw-blits it to panel `stride*5+6`. `indexedmap.BlitNativeMapHUDUnitIcon` preserves the cache slot/state boundary and makes no inference that slot is a character or portrait identity.

   Terrain AP/DP subpass closure: `0x1acf3` indexes its two static signed tables with the resolver's raw control byte+1: 0→(+5,0), 1/5→(0,0), 2/3→(-5,+10), 4→(-5,-5). `indexedmap.NativeMapHUDTerrainAPDP` keeps that bounded raw mapping, and `BlitNativeMapHUDTerrainAPDP` calls the verified signed two-digit renderer at the exact AP/DP layout origins atomically. The control byte's higher meaning and HP ratio path remain separate.

   HP subpass closure: after the optional unit icon, `0x1ae8e` zero-extends unit words `+0x40/+0x42`, passes `(destination,stride,current,maximum,3)` to `0x1875d`, and destination is the recovered HP origin. That helper selects glyph base #0x1f only when the two words are equal, otherwise #0x2a; `0x187d6` then formats **current** to exactly three digits at six-pixel advances. For current >999 it does not truncate: it blits `base+10` directly. Real FDOTHER #5 verifies #0x29 and #0x34 are 18×8 overflow frames, while both bases' digit #1 is 5×8 and all other digits 6×8. `indexedmap.BlitNativeMapHUDHP` preserves this raw comparison/unsigned-word boundary atomically; it does not call the unequal branch “damage” nor infer a percentage calculation.

   Full proven HUD assembly is now `indexedmap.BlitNativeMapHUD`: panel → terrain → AP → DP → optional icon → optional HP, in the direct `0x1ad72..0x1aea9` order and as one transaction. It accepts `NativeMapHUDInput` raw resolver outputs; `OptionalUnit=nil` represents no `0x12c0d` result or a post-lookup skip. The latter is closed as `NativeMapHUDOptionalUnitEligible`: raw `unit+7==0x79` skips; otherwise raw `unit+0x1f==0x0a && unit+6==1` skips. The three bytes retain raw names rather than a guessed character model. Closed display gates remain a no-op before resource validation.

   Constructor provenance correction: Docker Capstone plus official IDA 9.4 of `0x10d7f..0x10efc` proves runtime `unit+6` receives FDFIELD roster byte0 and `unit+7/+8` receives roster byte1; the existing editable `map_selector_key` and `battle_fig` fields therefore preserve those two raw sources. A further table trace closes the high-class branch: `0x10da4` computes `FDFIELD b1-0x44`, calls `0x4e4ff`, and that helper returns the 10-byte record at `0x61af9 + index*0xa`; `unit+0x1f/+0x20` are record bytes 0/1, while bytes 2/4/5/6/7/8 feed the other native fields. This is an EXE static table, not a proven DATO resource. The lower branch calls `0x4e4e8 → 0x61da1` (24-byte records) and `0x4e4d1 → 0x620a1` (11-byte records); `unit+0x1f/+0x20` come from the selected `0x61da1` record bytes 0/1. `0x619fd` belongs to the distinct `0x4e516` helper and is not part of this constructor path. Until both branch selectors and these raw table records are exported, optional unit/HP admission remains nil; portrait/class must not be used as a substitute.

   Export bridge: when supplied the paired FDSHAP terrain resource, `export_engine_assets.py` writes `native_terrain_control` (the complete raw four-byte records) alongside per-cell `native_tile_blit_modes`. This preserves the precise inputs of the region adapter; normalized `cost` remains a separate gameplay approximation.

   Runtime bridge: `battle.Load` accepts those two fields only when map dimensions, cell count, control-record alignment and every 10-bit tile index validate exactly; otherwise all native renderer/mechanics fields stay nil. It retains the raw tables and derives `NativeTerrainMoveCodes` from each tile's FDSHAP control byte+1. This is the authoritative combat AP/DP input; normalized `cost` is used only as a legacy incomplete-export fallback. The fields are not silently substituted into the current PNG/Ebiten path.

   Archive bridge: `fdother.DecodeSpriteBankResource` is the explicit LLLLLL-resource→24×24 four-mode-bank route for FDSHAP's evidenced even image resources. It deliberately returns only a `fdicon.Bank`: map/resource pairing and adjacent control resource selection remain caller-owned, preventing an image bank from being silently paired with a guessed terrain table.

   Map resource pairing closure: `DecodeMapTerrainResources` accepts an explicit map index N and loads only FDSHAP image #`2N` plus control bytes #`2N+1`; it rejects an inconsistent bank/control capacity. This replaces any future tile-count heuristic. Player archive map 0 regression fixes the concrete pair to 288 frames and 1200 control bytes.

   Production gate: `cmd/fd2.Game.loadMap` now attempts this complete original bundle (HUD FDOTHER frames, explicit FDSHAP pair, FDICON.B24, FDOTHER palette) and stores it only when every decoder succeeds. The current PNG presentation remains unchanged until the indexed-to-Ebiten bridge consumes the bundle; missing or malformed original files therefore cannot create a half-native frame.

   Regression/harness closure (2026-07-26): Docker image `fd2-go-test-local` already contains Xvfb; running `GOMAXPROCS=1 GOFLAGS=-p=1 xvfb-run -a -s "-screen 0 1280x1024x24" go test ./...` passes every remake package. `cmd/fd2.assetPath` now searches cwd ancestors after the existing user-data/AppImage/executable layers, because Go runs package tests with cwd `cmd/fd2`; this fixes test/runtime asset resolution without weakening the editable-user override or fail-closed resource rules. The ch14 continuation-line assertion now follows FDTXT_015 count-aligned indices 2/5 (scene lines 4..12 / 4..8), and conditional ch16 SPAWN remains branch-local after LOADCH with no merged-slot assumption.

   Native unit table export boundary (2026-07-26): `tools/extract_native_unit_tables.py` reads the LE object through `le_xref` and emits only raw records: `high_class` `0x61af9` (68×10, helper `0x4e4ff`, selector `FDFIELD b1-0x44`), `lower_class` `0x61da1` (32×24, helper `0x4e4e8`, selector `FDFIELD b1` in the lower branch), and `lower_aux` `0x620a1` (68×11, helper `0x4e4d1`, same selector). Docker extraction against the real FD2.EXE validates all 68/32/68 records. The JSON deliberately keeps selector provenance and `bytes_hex` without assigning gameplay names; it is an editable RE fixture, not permission to substitute portrait/class or to enable HUD optional unit/HP.

   Editable unit boundary: `tools/export_units.py` accepts the optional raw-table JSON and writes `native_constructor:{branch,index,record,aux_record}` per portrait-selected unit. `battle.NativeConstructorTable` validates the exact 68/32/10/24/11 dimensions on load and preserves legacy assets without the field. No renderer or gameplay path reads these bytes yet; malformed records fail closed rather than falling back to portrait/class semantics.

   HUD raw-state closure: `sub_11cac` calls `sub_1297d` immediately before the native map compositor. Its `[0x53c0b]` state advances `3→0` only when signed `rawScanline([0x46c])-rawLastScanline([0x53c0f])` is negative or greater than four, then stores the new last scanline; all other calls preserve it. `indexedmap.AdvanceNativeMapHUDState` now preserves this pure ABI and its boundary tests. The actual runtime caller still owns scanline/call timing, so the Ebiten optional unit icon remains fail-closed until those globals are materialized.

   Campaign flow correction: `postbattle_ch29_persist` now points to the recovered editable `ch29_post` binding before `preparation_ch30`; it no longer replaces that handler with synthetic `sync_party → set_chapter` beats. The native handler's proven LOADCH/persistent-roster reconstruction is the persistence boundary, while unresolved `0x2bce5` remains the sole tolerated fail-closed renderer issue. Campaign regression explicitly allows this native persistence exception and still forbids a direct battle→preparation edge.

   Presentation bridge (partial by evidence): `drawNativeMapHUD` now converts the verified 456-stride indexed buffer to a 320×200 paletted Ebiten image and presents panel/terrain/AP/DP when raw tile/control bounds pass. It deliberately supplies no optional unit/HP until runtime unit-record admission bytes are exported; any failure falls back to the documented legacy panel before drawing.

   Codec boundary: LMI1 is a directory, not one universal codec. `0x1acf3` sends #130 and its table-value-dependent hexadecimal #0x83/#0x84 entries to `0x4e63d`, the four-mode transparent RLE path. `fdother.ParseLMI1FrameEntry` / `DecodeLMI1FrameResource` preserve that explicit route and regression-decode the three player-archive entries at their verified geometries (69×34, 6×7, 6×5). `fdicon.NativeMapHUDLayoutFor` preserves the six strict 456-stride destinations and rejects an anchor whose 69-pixel frame does not fit the native 320-pixel viewport. These adapters intentionally do not reinterpret adjacent LMI1 cells handled by `0x4e916` or claim an Ebiten renderer.

   FIGANI placement bridge: `0x2935b` uses each frame header's signed X/Y, so runtime `assets/figani/meta.json` is placement data, not a hand-tuned animation hint. `cmd/fd2` regression reads every metadata resource from player-provided `FIGANI.DAT` and checks every exported `(X,Y)` against `internal/figani.DecodeResource`; a missing archive skips only that player-asset assertion. PNG rendering remains a presentation adapter, but cannot silently drift from the native frame coordinates.

   FIGANI scheduler boundary: official IDA at `0x2b9a1` shows `arg4==0` only clears the subframe counter and performs no render. On the advancing path, native code selects the current frame first, calls `0x2935b`, then reads descriptor `+6` as the delay; only after the rendered subframe reaches that delay does it reset subframe and wrap the frame index. `internal/figani.NativeScheduler.Step` implements this state machine as a pure, caller-owned primitive. It does not infer `0x2935b` presentation semantics or authorize an ending renderer.

   Preparation split-slide boundary: official IDA at `0x1f42d`/`0x1f1cc` fixes FDOTHER#5 LMI1 entry `0x52`, stride 456, five offsets `100,75,50,25,0`, and placements `(85-offset,82)` plus `(165+offset,81)`. `fdother.NativeSplitSlideSteps`, clipped cell blit, and `RunNativeSplitSlide` preserve one present/restore pair per pass. This proves indexed choreography only; MAP/TURN labels, movement confirmation input, and native VGA restore remain caller-owned and fail-closed. A deterministic remake shell capture is tracked as [`preparation-remake.png`](../figures/preparation-remake.png) (Xvfb, `FD2_CAMP_NODE=preparation_ch02`, frame 30, 640×400); it is not an original visual oracle.

   Preparation record gate boundary: the official `0x1a866` loop reads only raw unit offsets `+0x25`, `+0x05`, `+0x06`, `+0x40`, `+0x42`; it accepts when `+0x25!=0`, selector equals `+0x06`, and `+0x05 bit0==0`, then writes `+0x40 := max(0,+0x40-(+0x42/10))` and stores the divisor. `fdother.ParseNativePreparationRecord`, `NativePreparationEligible`, and `NativePreparationAdjustedWord40` preserve this ABI without naming the fields as active/alive, deployment, coordinates, or gameplay stats.

   Preparation dispatch boundary: `0x1a813` computes each candidate as `base+3*i` for exactly 16 slots, compares bytes `+3` and `+5` to caller/global gates, then reads byte `+4` as an index into a separate function table and invokes it with zero. `fdother.FindNativePreparationDispatch` preserves the overlapping 3-byte stride and returns raw matches only; it does not invoke callbacks or assign event names.

   Preparation timer boundary: official `0x1a941` scans 0x50-byte records selected by `+6==selector` and `+5 bit0==0`, then decrements six bytes at `+0x22..+0x27`; only a nonzero byte that becomes zero emits the downstream redraw path, whose source argument is `0x1e1+counterIndex`. `fdother.TickNativePreparationTimers` preserves this in-place transition and returns raw expiry metadata without naming statuses or effects.

   Preparation input boundary: official `0x19953` maps scan codes `0xe0/0x52/0x1c/0x39` to return `1`, `0x01/0x53` to return `-1`, and updates raw cursor `[0x53c57]` to `0` for `0x4b` or `1` for `0x4d`; all other keys continue waiting. `fdother.ApplyNativePreparationInput` preserves this result/state contract, without labeling the two terminal returns as YES/NO.

   D8 scope correction: the official `0x1a30b` body contains no `0x15f84` text call and therefore does not prove MAP/TURN/ENEMY/FRIEND/NPC labels. Its first loop gates raw record bytes `+6==2`, `+5&0x81==0`, `+0x25==0`, `+0x26==0`, then advances word `+0x40` by `word+0x42/5` with an upper clamp before indexed redraw. `fdother.NativeBattleEntryStep` preserves this numeric transition only; the later `0x1f1cc/#0x52` slide is a separate indexed choreography.

   Shared-caller correction: official xrefs show `0x1a30b` is called from `0x135c5`, `0x17154`, and `0x17272`, not only from the battle-entry path. The latter callers sit beside FDTXT_000 `0x19c/0x1a4` interaction messages and `0x1728c` selector-flag handling. Therefore the raw transition must remain a reusable record primitive; it cannot be labeled or wired as a D8-only preparation action.

   Raw action-bit helpers: official `0x13512(index)` sets `record[index*0x50+5] |= 0x80`, while `0x13536` clears that bit across the record count. `battle.SetNativeRecordBit7` and `ClearNativeRecordBit7All` now preserve these byte-level mutations with bounds checks; they do not force a higher-level turn interpretation.

   Inventory-cell correction: official `0x1b8a6(unit)` scans exactly eight two-byte cells at `record+0x0a+2*i`; it increments the occupied/raw prefix count when each cell's flag byte bit7 is **clear**. Bit7 set is the reserved empty state consumed by `0x1bb8c`, so the former `free-slot count` assertion and `battle.NativeInventoryFreeSlotCount` name were wrong and are removed. `battle.NativeInventoryOccupiedCount` preserves the raw prefix rule and ignores item-byte values; it does not lower the result to a normalized inventory length or item semantic.

   Inventory reservation boundary: official `0x1bb8c(unit,item)` scans those same eight cells, takes the first flag-bit7 reserved cell, clears its flag, writes the supplied item byte, and returns native success/failure (`1/-1`). `battle.AssignNativeReservedItem` reproduces this atomic raw mutation; no item category or shop meaning is inferred.

   Correction: the `0x1ac62` loop is not a preparation command stream. Its caller `0x1aa1d` uses FDTXT_000 indices `0x1b0..0x1b3`, which decode to post-resolution loot/interaction messages (enemy item, full inventory, money), so the higher-level preparation label is withdrawn. The proven part is only a `base+3*i` `{kind:byte,payload:u16le}` stream with observed kind `0/1/2/3` branches; `fdother.ParseNativePostResolutionCommands` preserves it and refuses truncation without assigning event names.

   `internal/fdicon.Sprite.BlitLUT` now reproduces the `0x4dcc6` pixel contract as a pure indexed primitive: RLE source writes become `lut[source]`; mode-3 spans become `lut[destination]`; mode-1 dither holes remain unchanged. Its fixture regression covers all three effects. It deliberately accepts an explicit LUT and destination buffer only—the map palette-entry selector, frame scheduler and foreground pass remain separate adapters.

   `fdother.ParseLUTBank`/`DecodeLUTResource` now close the FDOTHER #3 input boundary: its `LMI1` directory contains 23 independent 256-byte tables, not UI cells. The original-archive regression verifies that count and every table length. This loader plus `BlitLUT` is sufficient for a caller that has an evidenced selector; it does not infer one.

   The default `0x11eee` selector is now evidenced too: static table `0x51a97` maps runtime phase `0x53c1f` 0..19 to FDOTHER #3 entries `[0,1,2,3,4,5,6,7,8,9,10,9,8,7,6,5,4,3,2,1]`. `fdother.NativeTerrainLUTIndex` makes the bounded sequence explicit. The separate explicit-override branch remains raw/unlabelled; no visual name is inferred for the cycle.

   Correction: the sprite pointer table is no longer opaque. `0x11019` builds/caches a twelve-pointer FDICON block from its raw key and resource arguments; `0x10c50` passes FDFIELD `b0` plus its caller resource and writes the returned cache slot to `unit+2`. `0x127e0` then selects `unit+2 × 12 + pose×3 + cycle`. Thus `unit+2` is a cache result, not a direct character/portrait field. This is distinct from battle `0x287b5..0x2884c`, which selects `FIGANI.DAT` by `unit+7 × 3`. Constructor `0x10d7f..0x10efc` closes FDFIELD `b1→unit+7`, so `export_units.py` writes `battle_fig`; missing older JSON retains an explicit `fig` fallback. `fig` remains an unseparated map-`+2` approximation. Cycle is global idle/moving animation state, not unit `+4`; that byte offsets the camera-relative placement. The remaining adapter boundary is the resource/key→slot materialization, remap selection and layer order—not an invented FIGANI mapping.

   `fdicon.NativeSelectorCache` is the fail-closed data primitive for this ABI: `0x11019` keeps one process-global first-seen raw-key table (`0x53b17`/`0x53bdf`) and rejects non-byte keys in the remake. Its second argument is consumed only to materialize a new twelve-pointer block; both player `0x10a25` and scripted `0x10b69` load `FDICON.B24`, and cache lookup itself does not compare a resource pointer. Scripted FDFIELD source is explicit (`b0`, also native camp `+6`); player source is persistent `+7`. It deliberately does not map a slot to a character, portrait, or archive index; the remaining boundary is full mixed player/scripted construction order and indexed layer integration.

   The pointer-copy detail is now represented too: `KeyForSlot` reverses `unit+2` to the raw B24 key, and `SpriteForNativeSlot` then applies `key×12 + pose×3 + cycle`. This matches `0x11019`'s copied twelve-pointer block followed by `0x127e0`; it remains a process-global key cache and does not infer character identity.

   Runtime stores native map selection separately as optional `MapSelectorSlot`: its presence means an explicit native `unit+2` cache slot (including slot zero); absence must not fall back from legacy story/save `Fig`. This keeps the indexed compositor fail-closed while legacy UI remains compatible.

   The editable boundary now also carries optional `map_selector_key` (`MapSelectorKey` plus presence flag), the raw byte supplied to `0x11019` before slot allocation. `battle.MaterializeNativeMapSelectorSlots` accepts only an explicitly ordered construction batch and a process-global `fdicon.NativeSelectorCache`; it validates every key before allocating first-seen slots, then writes `MapSelectorSlot`. Missing/invalid keys leave both unit slots and cache untouched. Loader and renderer do not call it implicitly: the caller must first preserve the player-persistent then scripted-spawn order.

   `State.AppendNativeMapSelectorBatch` now supplies the atomic state seam for that proven order. It owns one process-global cache and appends only a fully valid batch; party `[9,4]` followed by scripted `[0,2,0]` produces slots `[0,1,2,3,2]`, while a missing-key batch changes neither runtime unit order nor cache. All 33 versioned map assets now carry the explicitly sourced scripted fields through `tools/sync_native_selector_fields.py --check`; existing scenario append nevertheless remains deliberately legacy until its mixed player/scripted construction order is explicitly connected, so no UI path is falsely upgraded to native rendering.

   Player-party construction is a separate proven source path: `0x1088d` copies each persistent 0x50-byte roster record from `[0x53bf7]` into the battle roster at `0x10a77`, then passes the copied record's `+7` byte and the chapter FDICON resource to `0x11019`; only its returned slot is written to runtime `unit+2` at `0x10aa2`. Map-script construction instead reaches `0x10c50` and supplies FDFIELD `b0`. These are distinct inputs to the same cache ABI. The remake must preserve explicit source provenance/order before it materializes slots, and must not derive either path from legacy `Fig`.

   The initial player source has one further closed edge: `JOIN` constructor `0x112a5(join_id)` writes `join_id` to both persistent record `+7` and `+8`; `0x33499` establishes `+8` as its character-ID lookup. Consequently a freshly joined player's raw FDICON key is its character ID when `0x10a77` later consumes `+7`. This is deliberately scoped to that writer and does not authorize a general character-ID/portrait/NPC selector alias or a default JSON fallback. It is mutable: class-change flow `0x314a7..0x3157a` writes its UI-selected target byte to live roster `+7` after locating `0x53a45+slot×0x50`. The native persistence ABI is closed separately: post-handler `0x11506` matches by `+8` and copies the full 0x50-byte record runtime→persistent, so any native flow that invokes it persists `+7`. The remake now exposes optional editable `PartyMember.native_identity` and runtime `Unit.NativeIdentity`; sync uses this key only when explicitly present and skips unknown keys. Missing legacy fields retain the normalized Fig projection, so the path remains partial rather than byte-identical. The engine must carry an explicit raw key rather than infer it from identity fields.

   The party projection now applies this narrow player contract: fresh `PartyMember.Fig` seeds `BattleFig` and explicit `MapSelectorKey` only because it represents the verified JOIN identity; `campaign.ApplyClassChange` leaves stable `Fig` intact, updates `BattleFig`/raw key to its proven selected target byte, and invalidates an old cache slot. Persistent overlay copies those split fields. This is state preservation only, not authorization to render arbitrary legacy `Fig` as native FDICON.

   Runtime selector bridge: `Scenario.ExecuteAction(spawn_party)` now materializes the party as one global-key batch; `AppendGroup` does the same for each later FDFIELD group, preserving party-first then group append order. A rejected editable batch records `State.NativeMapSelectorError` and preserves the legacy unit append, but disables native key resolution for the whole battle—there is no partial selector mix. The battle-unit draw path alone resolves `unit+2 slot → raw key` through that state cache; story/cutscene actors explicitly retain their editable `Fig` path. This is an exact selector adapter over the current PNG/Ebiten draw, **not** a claim that the native indexed buffer, palette branch, layer order, or HUD are now reproduced.

   `internal/fdicon` now decodes the 24×24 FDICON B24 container and preserves four-mode RLE transparency/dither plus both exact native blits: `0x4deda` raw indices and `0x4de56` opaque-index transform `(index&7)+0x18`. It has an original-asset 1680-sprite regression, but it is only an indexed asset primitive; no native frame schedule or UI handler is thereby enabled.

   `Bank.SpriteFor(key,pose,cycle)` enforces the recovered raw-key `key×12 + pose×3 + cycle` lookup inside one FDICON resource (pose 0..3, cycle 0..2). The renderer-facing formula remains `slot×12 + pose×3 + cycle`; `0x11019` performs the key→slot block copy. `NativeFrameIndex` captures the proven global idle/moving counters; battle `Fig` and `Dir` still provide only part of the runtime ABI, and no GUI integration is inferred.

   The raw/palette-band choice is also closed: `0x127e0` tests runtime unit `+5 bit7`; clear uses raw `0x4deda`, set uses `0x4de56` band. `fdicon.BlitForNativeFlags` makes that dependency explicit; it is not a guessed camp or LUT selection.

   Native placement is also represented as a pure byte-offset primitive: `NativePlacementOffset` preserves `0x127e0`'s `0x75d8 + (y-cameraY)*24*456 + (x-cameraX)*24 + unit[+4]*directionOffset` equation (pose 0/1/2/3 = down/left/up/right), with the `unit+0x26`-gated native 0-or-1 pixel shift. It deliberately does not claim an Ebiten coordinate or layer order.
4. **Campaign/postbattle**：逐關標記 battle end handler、town/shop/church/preparation/rest、persistent record append/reset、敗北路線；不能以章號順序推導。
5. **Native presentation**：完成 indexed off-screen/double-buffer、palette、透明 RLE、FIGANI/TAI/DATO compositing 後才接 Ebiten；任何 opaque segment 保持 fail-closed。

## 7. Milestones / gates

| Milestone | Deliverable | Gate |
|---|---|---|
| SDD-0 | 本文件、requirements matrix、證據分級、缺口清單 | 文件 review；無未標註的推測 |
| UI-1 | title→story→battle field→action menu→dialog→town/shop 的 shell vertical slice | command trace + headless tests + screenshots |
| UI-2 | battle target/range/end-turn/HUD 正確 | weapon/spell/menu RE evidence + differential tests |
| FLOW-1 | 全部 battle→postbattle→town/shop/church/preparation branches 可編輯 | 每章 transition matrix、save/reload regression |
| NATIVE-1 | indexed renderer primitives（含 ending／FIGANI／TAI） | byte/pixel regression；無 generic fallback |
| CONTENT-1 | ch01–ch30 script、資產、事件與結局完整 | campaign replay、無 load error、可編輯 round-trip |

## 8. Definition of done

- 所有 UI contract 有明確 state machine 和輸入測試；玩家不需要 debug key 才能完成基本流程。
- 所有戰後段落可在 campaign JSON 中看見；town/shop/rest/preparation 不被隱含吞掉。
- 所有 native 值有 E0/E1/E2 證據；E3 只存在於標註為 blocked 的文件，不進 runtime。
- Docker-only Capstone 與 Go regression 可重跑；`/tmp/fd2cap` 不存在，host Python 不安裝 Capstone。
- headless、畫面、存檔、reload、資源缺失 fail-closed 測試全綠；`git diff --check` 通過。

## 9. 本輪決策

本 SDD 完成前不再新增新的 remake handler 或 renderer 語意。`0x29164` non-mirrored figure-fade 的窄 indexed primitive 已以實際 regression 驗證並可提交，但這不等於完整 ending：primary FIGANI、DATO text、mirrored branch 與 player integration 仍 fail-closed。下一輪仍需完成 UI-01/UI-03/UI-07 的 RE evidence matrix，再選一條可截圖的 vertical slice。

### 2026-07-26 — native phase dispatch raw boundary

Official Docker Capstone recheck of `0x1d80b` closes only its first loop's admission boundary: records are addressed as `[0x53a45] + unit*0x50`, bounded by `[0x53beb]`; a candidate must satisfy raw `+6 == 1`, `(+5 & 0x81) == 0`, and `+0x26 == 0`. The native caller then passes `(unitIndex, record+6)` to `0x13a9f`, which may set `[0x51a8f]` before the event and chapter function tables are called and `[0x53ecc]` is checked. `fdother.FindNativePhaseDispatchCandidates` preserves this as an offset-level, fail-closed planner. It intentionally does not invoke callbacks or assign event names; no campaign node may treat it as a completed phase/event renderer.

The same audit rechecked `0x1b8e7` because it is shared by class-change, item, and post-resolution callers. Official IDA 9.4 decompiles a uniform `sub_1B8E7(int unit, int slot)`: `memmove(record+0x0a+2*slot, record+0x0c+2*slot, 2*(7-slot))`, followed by `record+0x18=0x80`. `battle.RemoveNativeInventorySlot` now reproduces this byte-level removal, including the native stale item byte in the final cell. The previous claim about an unresolved third stack argument was incorrect and has been removed; higher-level callers still decide why a slot is removed.

The shared upstream `0x13a9f` is bounded at its raw mode boundary: after `record+5 & 5 == 0`, it reads `mode=(record+0x34)&0x0f`, bytes `+0x35/+0x36`, and byte `+0x3d`. `fdother.PlanNativeUnitMode` records those values plus the caller's unit/second argument and performs no callee invocation. Mode branches remain evidence-only; no battle, town, shop, or event meaning is assigned from the mode number.

The item-action effect dispatcher `0x20c6f` is now also transcribed at call-topology level. It reads item-row byte `+0x0d` and word `+0x0e`; observed raw branches are: `5/13→0x211a4`, `6→0x22af6` subcommand `0x14`, `7→0x22af6/0x15`, `8→0x21082/0x37`, `9→0x21082/0x39`, `10→0x21082/0x3e`, `11→0x1c4cc→0x1c2da` loop, `12→0x22997`, `14→0x22d1b/0x1b`, `15→0x22866`, `16→0x22721`, `17→0x21082/0x42`, `18→0x21082/0x46`, `19→0x21082/0x3b`, `20/24→0x1c4cc→0x1cd17` loop, `21→0x2111a`, `22→0x22d1b/0x16`, `23→0x2218a`. `battle.NativeItemEffectRouteForType` now preserves this raw route and integer arguments without invoking any callee. This is an editable evidence map only; the remake must not label these type IDs as potion, status, damage, or equipment effects until the callees and target ABI are closed.

Official IDA 9.4 also closes the small presentation helper `0x1e0db(value, digitBias, target)`: after a camera-bounds check it formats `value` as four decimal digits and appends four raw queue entries with position codes `2,7,12,17`, target index, and digit bytes; `0x1e1dc` writes a parallel four-byte queue from a global raw source. This is a presentation-queue ABI, not proof of HP/MP/damage/heal semantics. The adjacent `0x1debe(actor,x,y)` gate only checks active state, Manhattan adjacency, and equipped row byte `+0x0b <= 1`; it must not be promoted to a universal weapon max-range rule.

The remake has a data-only `battle.AppendNativePresentationDigits` adapter with right-alignment, bias, camera no-op, and raw position-code regression coverage. It deliberately stops before renderer, palette, SFX, or gameplay naming.

Official IDA 9.4 decompilation of the shared type-6/7 callee `0x22af6(a1..a5)` closes one mutation-only boundary: it iterates `a3` unit indices from byte list `a4`, reads `record+a5`, clears nonzero bytes, and accumulates `4*effective(record+0x21)` where `+30` applies only when `record+0x20` is strictly between 8 and 25. `battle.ClearNativeUnitByte` reproduces that raw mutation and returns per-unit/raw totals without executing the native rendering calls or assigning a buff/debuff/experience meaning. Zero-byte entries remain unmodified.

Official IDA 9.4 decompilation of common callee `0x21082(a1..a7)` closes the corresponding word-write path: it reads one unit index from `a6`, adds the low 16 bits of `a2` to the word at `record+a3` (native wrap semantics), then calls `0x1b8e7(a1,a4)` to compact/remove the caller's inventory slot. `battle.ApplyNativeWordDeltaAndRemove` preserves explicit target/removal units, raw word offset, signed delta representation, and atomic bounds validation; it does not name the word or run renderer/effect callbacks.

The growth-marker callers around `0x22721/0x22866/0x22997` use `0x4e893`: 16-bit `rol3(state+0x9014)`, then `idiv 4` and the **remainder** in `EDX`, followed by `+2`. `fdother.NativeRNGStep`/`NativeRNGMarker` preserve this state transition and marker source. Any earlier interpretation as quotient-based growth marker is invalid and must not be used.

Official IDA 9.4 decompilation of `0x22721(a1,count,indexBytes)` closes the first raw growth writer: it skips records whose `+0x22` marker is nonzero; for each zero marker it advances the shared RNG, writes `+0x22=(rng%4)+2`, computes `trunc(word(+0x48)*0.15+1)` using the native toward-zero `_CHP` helper, adds that low-word increment to `+0x48`, and accumulates `2*effective(+0x21)`. `battle.ApplyNativeRawWordStep` reproduces this batch mutation and score while leaving presentation and the `0x1317d` tail outside the adapter. It does not call the function for already-marked records or consume RNG for them.

The adjacent `0x22866` branch is byte-for-byte the same arithmetic with marker `+0x23` and word `+0x4a`; `battle.ApplyNativeRawWordStepAtOffsets` shares the implementation and regression without assigning either field a gameplay name.

The neighboring `0x22997` branch is a separate fixed-pair mutation: marker `+0x24` is gated, successful units advance the same RNG and add `0x0f` independently to raw words `+0x4c` and `+0x4e`, then contribute the same `2*effective(+0x21)` raw score. `battle.ApplyNativeRawPairStep` captures this with 16-bit wrap and marked-skip behavior; presentation remains outside scope.

The `0x22d1b` path is intentionally kept separate from that family. Its raw loop skips a nonzero `record+a5` or class byte `+0x20` equal to `0x19/0x1a`; otherwise the first `0x4e893()%100` remainder must be `<50`, then it calls `0x1c81f(unit,10)`, advances RNG again, writes `(rng%4)+2` to `record+a5`, and adds `8*record[+0x21]` to the raw presentation accumulator. This is an evidence-only branch map: the HP writer and renderer are separate contracts, and no status/effect name is inferred.

The raw mutation is now executable without normalized command semantics: `battle.ApplyNativeRawHPDamage` preserves the `0x1c81f` subtract/clamp core, and `battle.ApplyNativeRawApplication` preserves the `0x22d1b` marker-zero/class gate, two RNG draws, marker write, and `8*record[+0x21]` accumulator. Its presentation and status meaning remain fail-closed.

Official IDA 9.4 decompilation of `0x22253` closes the command-23 state write: after its indexed renderer work, it writes the supplied final `a13/a14` bytes to `record[+0]/record[+1]`. Caller `0x2218a` passes `0xff/0xff` as the pre-render pair and cursor globals as the final pair. `battle.SetNativeUnitCoordinateBytes` preserves only this raw write; movement pathfinding, camera, indexed presentation, and cursor semantics remain separate.

Caller-scope correction (Docker Capstone, 2026-07-26): `0x22253` is shared by the chapter-ending/post handler at `0x250cc`, not command-23-only. That path calls it after `0x1c2da` with unit index `1`, pre-render bytes `0xff/0xff`, and the selected record's raw `+0/+1` bytes, then continues to `0x25089` cleanup and `0x2bce5` ending rendering. The remake therefore treats `SetNativeUnitCoordinateBytes` as a shared raw writer only; command-23 selector, ending layout, renderer, and campaign transition remain independent fail-closed contracts.

The `0x25348` branch audit further fixes the ending-only order: FDOTHER frames `0x0d`, `0x0e`, `0x0f` are presented around `0x1c2da`; the shared `0x22253` write for unit `1` follows with raw `+0/+1`, frame `0x10` follows, and then `0x25089→0x2bce5` enters the terminal self-loop. This is call-order evidence only. The `0x24b14` return and frame IDs remain unnamed, and this branch must not be used as a generic battle→town/shop transition.

The ch26 item gate is now closed as a raw read-only primitive. Docker Capstone shows `0x24b14(item)` scanning units `0..15`, while `0x31860(unit,item)` first calls `0x1b8a6` and then compares only the count-sized prefix of item bytes read by `0x1b722` at `record+0x0b+2*slot`. `battle.FindNativeInventoryItemInUnit` and `FindNativeInventoryItem` preserve that prefix/count behavior, return the first raw `(unit,slot)` for an editable gate, and never remove or mutate a cell. The existing campaign `partyHasItemID` is only a normalized-inventory compatibility projection and no longer claims byte identity; runtime raw-record plumbing is still a gate before using it for native equivalence. The native `0x24b14` success/failure result is therefore not a recipe, reward, camp filter, or item-consumption proof; ch26's later success/missing presentation remains a separate handler branch.
Portrait text correction (official IDA, 2026-07-26): the epilogue selector at `0x2c8f7..0x2c8f9` is controlled by the outer `edi` portrait-loop counter, not a bitwise `|45` expression. It is `unit[+8]+0x0c` while `edi < 0xdc`, then fixed current-FDTXT index `0x2d`. `Montage.PlanPortraitText` preserves this exact branch and rejects short unit records; no text renderer is inferred from the mapping.

Persistent identity lookup is separately closed at `0x24bde`: Docker Capstone shows a caller-supplied count loop over the persistent `[0x53bf7]` array, stride `0x50`, comparing only the unsigned byte at record `+0x08`, with native boolean success/failure. `battle.FindNativePersistentIdentity` preserves the first raw index, explicit count/capacity validation, and read-only behavior. This is an identity-table primitive only; it does not rename `+8` as portrait, Fig, NPC, or a general character alias.

The adjacent `0x24d22(arg)` boundary remains evidence-only. Capstone shows `arg!=0` writing only its low byte to global `0x51a10` and returning; `arg==0` instead allocates/copies indexed buffers using `0x51a10`, `0x53aff`, and stride `0x138`, then frees through `0x37416`. The setter and the renderer/copy branch are therefore separate contracts. No name is assigned to `0x51a10`, and the copy loop is not lowered as a generic fade or presentation effect.

The adjacent `0x24e80` handler contains one independent raw mutation loop: for runtime indices `0x10 <= i < caller_count`, records with byte `+0x07 == 0x1f` receive `+0=0x10` and `+1=0x06`. `battle.RewriteNativeMarker1F` preserves the explicit start/count, matching-marker-only writes, and bounds validation. The bytes remain unnamed and are not treated as roster identity or renderer state.

The mutation core after a selected `0x11506` pair is independently transcribed: copy runtime→persistent `0x50` bytes; clear persistent bytes `+0x22..+0x27`; mask persistent byte `+0x05` with `1`; if the result is not `1`, copy word `+0x42` to `+0x40`; always copy word `+0x46` to `+0x44`. `battle.ApplyNativePersistentRecordCopy` implements only this raw core with atomic bounds validation. The preceding `0x3453e` zero-identity/inactive gate and trailing `0x1145a` call remain outside the helper and outside remake sync semantics.

The preceding `0x3453e(index)` predicate is now closed independently: it returns exactly `record[index*0x50+0x05] & 1` and performs no write. `battle.NativeRecordByte5Bit0` preserves this mask/bounds contract without labeling the bit as acted, alive, or active; callers must still prove their own higher-level gate.

   The `0x1145a(persistentIndex)` tail is also data-flow closed: it starts signed base words at record `+0x37`, `+0x39`, and `+0x3e`; scans eight cells; only a cell flag with bit `0x40` set causes its item byte `+1` to index `0x4e56c`; effect words `+1`, `+5`, `+3`, and `+7` accumulate into raw destinations `+0x48`, `+0x4a`, `+0x4c`, and `+0x4e`. `battle.ApplyNativeEquipmentRecalc` now preserves this raw operation with atomic bounds validation and 16-bit wrapping. Existing `campaign.RecomputeEquipment` remains a normalized projection, not proof of byte-identical raw item-table plumbing; row fields remain unnamed.

The shared item-row helper `0x4e56c(item)` is now bounded at the proven arithmetic boundary: it returns a pointer at linear table base `0x602ad + item*0x17` (23-byte rows). `battle.NativeItemEffectRowOffset` exposes only the table-relative offset for a byte-sized selector; row size/field semantics and table bounds remain unproven, so no normalized `ItemStats` field is wired to these bytes.

The type `5/0xd` callee `0x211a4` is now bounded at call topology: it receives the caller's target-list context, enters `0x1c4cc`/`0x1c2da` with raw subcommand `0xd`, then iterates the supplied byte list and calls `0x1c916` with the item-row word and each target byte before the `0x1e0db` presentation call. This proves a list-driven raw mutation/presentation loop, not a generic heal/potion contract; target-list/count/amount argument names and the presentation path remain fail-closed.

Official IDA 9.4 pseudocode now closes the previously opaque presentation callers without naming their gameplay effect. `0x1c4cc(a1, subcommand, count, targetBytes)` copies three 33-byte global frame tables, snapshots the indexed 456-stride buffer, iterates `frame < frameCount[subcommand]`, selects a frame from `frameBank[subcommand]`, redraws each supplied target's visible 24×24 cell when it is inside the camera bounds, presents the 312×192 viewport, and emits only the observed subcommand/frame-specific SFX branches before a BIOS-tick wait. `0x1c2da(a1, subcommand, count, targetBytes)` starts the same presentation family with SFX index 1, redraws each target through the indexed pointer bank selected by `12*unitVisual + currentCycle` (with the native `cycle==3` remap), then performs five restore/present pairs before returning the saved buffer. `0x211a4` calls both with raw subcommand `13` before the per-target `0x1c916` mutation. This closes the caller ABI, frame ordering, camera bounds, and restore cadence only; the item row word, target list producer, SFX labels, and native renderer asset provenance remain opaque and fail-closed.

The same IDA pass closes the type `20/24` presentation loop at `0x1cd17(a1, subcommand, count, targetBytes)`: it copies a 30-byte frame-remap table, runs exactly ten frames, restores the saved indexed buffer before every frame, redraws each camera-visible target through `0x4dc34` using `7-(frame mod 8)` as the raw blend argument, presents the same 312×192 viewport, waits one BIOS tick, then restores the original frame. This is a distinct ten-frame path from `0x1c4cc`/`0x1c2da`; it is not evidence that item type 20/24 is a named status or damage effect. The compatibility predicate used by the item selector is also exact at `0x1c1c3(actor,item)`: `0x4e53e(actor class)` supplies six raw item bytes and the predicate compares item-row byte `+0` against those six entries. The six-byte table and row byte remain opaque inputs; no class/equipment name is inferred.

The table provenance is now closed at `0x4e53e(class)`: it returns `0x6188a + class*7`, so the selector's six-byte comparison consumes bytes `row+0..row+5` and leaves `row+6` opaque. `battle.NativeClassCompatibilityRowOffset` and `NativeClassItemCompatible` preserve this address/length contract with bounds and short-row rejection. This is a raw selector adapter only; it does not expose a normalized class or item compatibility field.

The shared `0x1c916` HP mutation core is now separately executable as `battle.ApplyNativeRawHPRestore`: it advances the Docker-verified 16-bit RNG, applies `amount*9/10 + (rng%100)*amount/1000`, clamps raw `+0x40` to `+0x42`, and preserves the native raw score gate (`record+0x07 < 0x4b`, class byte range `9..24` adds `0x1e`, score factor `40*effective*delta/max`). It is an isolated raw adapter; no normalized item, heal, or UI semantics are inferred.

The sibling `0x1c9dd` MP mutation is now captured by `battle.ApplyNativeRawMPRestore`: the same RNG and amount arithmetic writes `+0x44` capped by `+0x46`, while its score uses only `record+0x21` (no HP routine's class-range bonus). This remains raw state/evidence only.

The type-`21` callee `0x2111a` has a separate raw boundary: it establishes target context through `0x1c4cc`, calls `0x1cac7`, then iterates the supplied byte list through `0x1c75e` and `0x1e0db`. `0x1cac7` obtains a byte from `0x4e516` and subtracts it from selected runtime record word `+0x44` with native 16-bit wrap. The source record/byte and list ABI are preserved as opaque inputs; no MP-cost or item-effect name is inferred.

`battle.ApplyNativeRawWordSubtract` now preserves that `0x1cac7` mutation as an explicit `(unit, wordOffset, byteAmount)` adapter with low-16-bit wrap and preflight bounds. It is deliberately generic and does not replace the normalized `SpendNativeCommandMP` path or assign a gameplay field name.

The common `0x22af6` flag branch is now captured by `battle.ApplyNativeRawFlagRestore`: paired target/flag bytes are preflighted; each nonzero flag invokes the proven raw HP restore with amount `10`, clears only that flag, and adds the raw `effective*4` accumulator (class range `9..24` adds `0x1e`). Flag/status names and presentation remain outside the adapter.

Caller-level evidence around `0x24838` must remain separate from the raw lookup adapters. It first branches on `0x24b14(0x64)`; the success arm presents text `#8` and calls `0x112a5(0x16)`. It then branches on `0x24bde(0x12)`: hit presents text `#10`, acting `#0x48`, and `0x32975(0x11)`; miss branches on global count `0x53bef < 0x0f`, choosing text `#13` plus `0x112a5(0x13)` or text `#12` plus `0x32975(0x11)`. Shared sync/presentation follows. These are address/order facts only; no item, character, chapter, or NPC names are inferred from the immediates.

The downstream `0x32975(index)` mutation is independently closed: it computes the selected runtime record at `base + index*0x50` and writes byte `+0x05 = 1`, overwriting the entire byte. `battle.SetNativeRecordByte5One` preserves that overwrite and bounds behavior. It is intentionally separate from the `0x13512` bit7 setter and does not name byte5 as acted, turn, or action state.

### 2026-07-27 — constructor inventory flag materialization

Official IDA 9.4 pseudocode for `0x10c50` closes the constructor's eight raw
inventory flags. The first cell always receives `0x40`; if source byte 0 is
`0xff`, source byte 1 is placed in that first item cell and the second flag is
reserved `0x80`; otherwise the second flag is also `0x40`. Source bytes 2..7
copy to the remaining item cells, with flag `0x00` for a present item and
`0x80` for source `0xff`. `battle.NativeInventoryFlagsFromSource` preserves
only those byte writes, and `NativeInventoryCompactEligible` applies the
caller gate as a signed-byte test: `0x40` and `0x00` are eligible, `0x80` is
not. `Load`/`PartyUnits` retain these flags when the eight `inventory_slots`
source is present; legacy JSON remains a conservative projection. This fixes
the former incorrect “un-equipped only” description and does not assign an
item category or church service name.
