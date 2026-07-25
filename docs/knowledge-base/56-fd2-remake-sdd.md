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
`tools/ida_export_fd2_xrefs.py`，供使用者授權的私有 IDA workspace 匯出 xref 後重跑。2026-07-25 嘗試以官方 `idat -A` 分析唯讀 FD2.EXE 時沒有產生 `.i64` 或 `fd2_xrefs.json`；這符合 IDA 尚待首次 GUI 接受授權條款的狀態。待使用者在官方 GUI 一次性完成接受後，才可重跑 batch export；在實際 report 可驗證前，現有結論仍以 Docker Capstone 作 E0，不以工具名稱或缺檔猜測。

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
| UI-03 | Action menu | move/attack/magic/item/status/wait/end-turn 的可見項、enable gate、取消回上一層 | partial；原版 action overlay 的 battle cell table（enabled `[0,2,4,6]`／disabled `[3,5,7,9]`）、open/close 四幀 byte-offset、以可視 cursor column/row 算出的 framebuffer anchor 已閉合。native command grid 亦已定為 320×200、每欄四列，label `(18+100*col,103+22*row)`、MP 右側、↑↓ wrap/←→±4 bounded；scenario raw command mask 已可 materialize。玩家提供 `FD2_ORIGINAL_FDOTHER`（或 user assets）時，remake 會直接讀 FDOTHER#0 palette＋#2 cells 並畫 final-open skin；舊 PNG ring 是 fail-closed fallback。raw grid confirm 現明確拒絕送入 legacy `CastArea`，直到 native two-stage target/effect 閉合。動畫、完整 native gate 與 visual-diff 尚缺 |
| UI-04 | Target/range | 武器 min/max reach、法術 range/AOE、不可用目標灰化、確認／取消 | missing/partial；不能再把攻擊距離寫死相鄰格 |
| UI-05 | Dialog | 上／下框、portrait anchor、文字避讓、控制碼、分頁／捲動、嘴型、輸入鎖 | partial；已有 regression，但 native frame/資源與所有 speaker layout 未閉合 |
| UI-06 | Battle HUD | HP/MP/LV/name、面板 sprite、數字 cell、依游標避讓、palette/clip | partial；需以 FDOTHER/UI loader 和截圖差分驗收 |
| UI-07 | Postbattle | result → handler → reward/roster cleanup → town/shop/rest/preparation 或 ending；不可預設直連下一戰 | partial；campaign schema 可表達，逐關 branch 證據仍不足 |
| UI-08 | Town/hub | 可見選單、離開、shop/church/preparation 入口、BGM/SFX、持久隊伍 | partial；`town` 可選 node，但需逐章節驗證 |
| UI-09 | Shop | buy/sell、商品／角色／slot 游標、裝備詢問、金錢／庫存原子更新、secret gate | partial；buy/sell/equip 有 code，UI sprite/layout 與原版分支未驗 |
| UI-10 | Church | revive、class change、費率、候選過濾、確認／取消、缺資料 fail-closed | partial；現有 service menu 對未接 callee 明確擋下 |
| UI-11 | Preparation | JOIN chronology、deploy quota（15／19）、勾選／取消、預覽、F5 save、進戰場 | partial；資料與 quota 有 code，原版 layout/操作未做差分 |
| UI-12 | Save/load | scene-safe boundary、campaign cursor、flags、party/inventory/equipment、version/checksum、四槽 selector | partial；自有格式可用。native 已知 `FD2.SAV` rolling-XOR/checksum envelope 與 4×logical records（`+0x312b+i*0xa28`，`0x28` metadata + roster `0xa00`）；metadata `+0`=chapter/`0xff` empty、`+2..+5`=currency 已閉合，其餘語意未閉合，尚非相容實作 |

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

同樣地，`0x1b6b7` 不是 effect calculator：它掃 native runtime roster，只對符合 `+5/+0x31/+0x40` 後處理條件的 record 複製三 bytes（source `+0x31`）到 caller buffer；`0x1cff0` 再把此 buffer 交給 `0x1aa1d`。後者因此是 post-resolution 的訊息／掉落／互動處理層，不能拿來推回 command 0 的原始傷害或 status writer。確切三個 byte 的遊戲語意尚未命名，維持 raw offsets。

command 0 的 damage writer 已閉合到 `0x1c75e(target, commandID)→0x1c81f(target, amount)`：前者取
`record.u16[+0] * resist_raw[unit+0x20] / 10` 為 base；constructor `0x10f7f/0x11399` 直接把 source
class byte 寫入 `unit+0x20`，故這是 target class-ID-indexed table，而非未明角色欄位。對 command 0 以 `record[+2]` 做 `rand()%100`
命中門檻；命中才呼叫後者。`0x1c81f` 算 `damage = floor(base*0.9) + floor((rand()%100)*base/1000)`，
將 target `unit+0x40` 減去 damage，並 clamp 至 0，直接證實 `+0x40=current HP`、`+0x42=max HP`。
IDA `word_51f96` 的 loaded-data file offset 正是既有 `0x51d96` 職業魔抗表：每 class 的 4-byte row
低 byte 是 `resist_raw`（法師=7 即 30% magic resistance）。因此這個乘數的 raw ABI 與玩法名稱都已閉合，
並以 `NativeCommand0Damage` 的獨立 resolver 實作及 regression 固定；它不共用 legacy normalized magic
resolver。`remake/assets/data/native_command_resistances.json` 是同一 raw table 的可編輯 runtime copy；target
geometry、動畫及 post-resolution 仍未閉合，故 UI 不得把已知數值公式誤擴張成完整 native effect。

`State.ExecuteNativeCommand0` 現將已證實的 core contract 組合為 non-UI engine slice：strict ID-0 record、
actor `+3`→confirmed candidate→cursor `+4`、一次 `+5` MP debit、每個 final candidate 的 class multiplier/hit/HP
clamp。任何缺失 raw flags、record、confirmed candidate 或 resistance row 都在 mutation 前拒絕；special command、
animation、post-resolution 與 UI remain unbound。Game bootstrap 將 strict `native_command_resistances.json` copy 到
`State.NativeCommandResistances`；`ExecuteBoundNativeCommand0` 只使用此 state-bound raw table，缺表不回退 legacy magic。
成功結束時才投影 wrapper `0x18d8c→0x13512` 的 runtime `unit+5|=0x80` 為 `actor.Acted=true`；失敗不設。
UI vertical slice 現僅對 ID0 開啟：raw grid Enter 會以 `+3` candidate highlighter 進入 target mode，Enter 交
`ExecuteBoundNativeCommand0` 作完整 verified core，ESC 回 native grid；缺 raw data／其他 ID 一律不接 legacy cast。
官方 IDA 顯示 ID1、2、3 皆只將常數 ID push 後跳入同一 `sub_21227`；續查 ID4..7 亦進
`sub_213B7`、ID8 回 `sub_2121A`、ID9 直接呼叫 `0x1CA89→0x1C75E`。故 engine 的
`ExecuteNativeCommandDamage` 嚴格支援 ID0..9 共用 numeric/MP/acted contract；UI 仍只啟用 ID0，直到每個
presentation/effect boundary 有獨立驗證。

IDs13..16 是另一條已閉合的治療核心，不能併入上面的 damage route。其 jump-table handlers
`0x21AD9/0x21B99/0x2211C/0x22153` 各以 ID `13/14/15/16` 和各自的演出參數跳到共同
`0x21B18`；它在 generic target-confirm 後，以同一 final target array 呼叫專用 indexed 演出
`0x1C4CC/0x1C2DA`、再經 `0x1CA89(actor,id)` 扣 record `+5` MP。它逐 target 呼叫
`0x1C8ED(target,id)→0x1C916(target,record.u16+0)`：`+0x40` 增加
`floor(amount*9/10)+floor(rand()%100*amount/1000)`，上限 clamp 為 `+0x42`，並以
`0x1E0DB(...,0x69,target)` 顯示結果。這直接證實 IDs13..16 是 per-final-target HP restore（ID13 raw row 為
`dmg=70, +3=4, +4=0, mp=3, target=1`），但尚未把這個獨立 resolver、專用 renderer、SFX 或 UI 接入 remake；
在有對應 regression 前仍 fail-closed。

IDs17..19 是第三條 transient-modifier family，亦不能交給 damage/heal executor。ID17
`0x226EA→0x22721`、ID18 `0x2282F→0x22866`、ID19 `0x22960→0x22997` 都在 final target loop 中先拒絕
已設 flag 的 unit：17/18 在 `+0x22/+0x23` 為零時設 `rand()%4+2`，並分別對 `+0x48/+0x4a`
加 `__CHP(value*0.15+1)` 的 FPU-rounded increment；19 對 `+0x24` 同樣設 duration，並對 `+0x4c/+0x4e` 各加 15。
這與 `0x1b750` 對 `+0x48/+0x4a/+0x4c/+0x4e` 的 derived AP/DP/HIT/EV synthesis 相容，因而撤回先前把
這些 offsets 稱為 screen coordinates 的斷言。duration 的 tick/clear、玩家可見 status 名稱、專用演出與
remake state/UI 仍未閉合，不能據此補出 gameplay names。

IDs20..21 共享另一條「flag-present 才生效」route：`0x22A85/0x22BC6→0x22AA8→0x22AF6` 各以
command ID 20/21 扣 MP，對每個 final target 讀 `+0x25/+0x26`。該 byte 為零時只走失敗 display；非零時呼叫
`0x1C916(target,10)` 的既有 HP-restore writer、清零該 byte，並顯示結果。這證實 raw gate、clear 與
HP writer，但尚未命名兩個 status，亦未接 engine/UI。ID22 是不同的 `0x22BE1→0x22CDA→0x22D1B` route：final
target 的 `+0x27` 必為零、class `+0x20` 不得為 `0x19/0x1a`、且 `rand()%100<0x32`，才以
`0x1C81F(target,10)` 固定扣 10 HP、顯示 damage，並寫 `rand()%4+2` 至 `+0x27`。它須獨立追蹤，不能併稱為 cure
或依 raw offsets 猜測 status name。

這六個 transient bytes 的生命週期已由 `0x1A866(camp)` 閉合：turn/camp phase driver `0x1A30B` 對各 camp
呼叫它；routine 只掃該 camp 的 active unit，依序對 `unit+0x22..+0x27` 的每個非零 byte decrement。任何一個
byte 變零時才顯示 expiry feedback 並呼叫 `0x1B750(unit)` 重算 derived fields；因此 ID17/18 的 AP/DP 增幅會在
自己的 duration 歸零後由重算移除，其他 flag 不可因為共用 sweep 就被誤認為同一 status。這是 phase-based timer ABI，
不是每次 action 或 frame 的 timer；status labels/UI icon 仍未命名。

ID23 走 `0x1CFF0` 的 command-`0x17` special selector，不能套 generic two-stage target contract。其 handler
`0x2218A` 以 record23 扣 MP，並呼叫 `0x22253` 兩次：依 C stack ABI，第一次將 selected unit 的 runtime
`+0/+1` 寫為 `0xff/0xff`（以原座標作離場 indexed 演出），第二次直接寫為 selector cursor globals
`0x51CF9/0x51CFD`（並作入場演出）。因此已證實它是無 path traversal 的直接 grid-coordinate relocation；
落點 selection/legality、camera choreography、renderer 與 remake UI 尚未閉合，不能把它泛化成普通 move 或 generic
target effect。

IDs25..27 也已由 jump-table 閉合。ID25 `0x22C04` 以 record25 扣 MP，僅對 final target 已有
`unit+5 bit0x80` 的項目清該 bit，直接對應 action-complete 的 raw state writer（不憑名稱推導）。ID26
`0x22CBF` 與 ID27 `0x22E41` 分別將 command ID 和 flag offset `+0x25/+0x26` 傳給與 ID22 同一
`0x22CDA→0x22D1B` application helper，所以同樣受 zero flag、class、`rand()%100<50` gate，成功固定扣 10 HP
並寫 2..5 duration。這使 ID20→`+0x25` clear 與 ID26→`+0x25` apply、ID21→`+0x26` clear 與 ID27→`+0x26`
apply 成為 direct code-pairs；仍不以此取代 UI/status icon 的獨立驗證。

command 0 的 selector boundary 也已縮小：`0x1cff0` 對一般 record（非 command `0x17`／`0x1e` special
branch）先以 actor cell、`record[+3]`、`record[+6]` 呼叫 `0x14818`，把可選中心的 unit indices 寫進 caller
stack array；`0x115b6(mode=record[+6], count, array)` 作 cursor/confirm。confirm 成功後，它以**確認游標格**、
`record[+4]` 和同一 target code 再呼叫 `0x14818`，此第二個 candidate array/count 才傳入
`0x2a6bd(unit, commandID, count, array)`，後者逐 index 呼叫 `0x1c75e`。這證實 command 0 的 numeric resolver
是 **per final-effect candidate**，而非 legacy UI 的單格 `CastArea` contract；`0x14818` 的方向／形狀
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
portrait→growth-row provenance 是 direct ABI：`0x4e4d1(unit+7)=0x620a1+portrait*11`，第 11 byte 就是
`learn_idx`。remake `State.GainExp` 因此只在已注入這個 editable table 時，於剛達到的 level OR exact
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

### 5.1 目前 editable graph audit（E1，不等同原版 E0）

`remake/assets/scenarios/campaign_full.json` 的 30 個 battle node 已逐一展開
`on_win`，並沿著 post/cutscene 節點走到第一個可操作戰間節點。這張表是目前 remake
的可編輯基線；只有標成「native 待核」的項目仍不可宣稱已還原原版 handler。

| battle | 勝利後第一個戰間節點 | 路線型態 | native 證據狀態 |
|---|---|---|---|
| 01 | `story_ch02` → `town_ch02` | 劇情→城鎮 | native 待核 |
| 02–20 | `story/postbattle_chNN` → `town_ch(NN+1)` | 劇情／持久化→城鎮 | native 待核 |
| 21 | `story_ch21_post_sky_key_intro` → `inventory_recipe_ch21_sky_key` | 劇情→合成 gate（非直接下一戰） | gate E1；native 待核 |
| 22–24 | `postbattle_chNN_persist` → `preparation_ch(NN+1)` | 持久化→整備 | native 待核 |
| 25–26 | `postbattle_chNN_persist` → `town_ch(NN+1)` | 持久化→城鎮 | native 待核 |
| 27 | `inventory_gate_ch27_sky_key` → success/missing branch | 道具 gate→分支劇情 | gate E1；native 待核 |
| 28–29 | `postbattle_chNN_persist` → `preparation_ch(NN+1)` | 持久化→整備 | native 待核 |
| 30 | `ending` | 終局（不接下一戰） | ending renderer fail-closed |

因此不能以「battle node 有 `on_win`」推導下一節就是下一戰；town、shop、church、
preparation、inventory gate 與 ending 都必須留在 graph。下一個 SDD-2 子任務是以
原版 handler offset／DOSBox 操作逐列補 E0/E2 證據，並為每列加入 save/reload regression。

## 6. Reverse-engineering re-audit workstreams

SDD 通過後按以下順序重審，不先補 renderer 猜測：

1. **Boot/menu/UI dispatch**：以 Ghidra/IDA 建立 call graph、keyboard scan、menu item table、resource loader；Docker Capstone 只作可重跑交叉驗證。
2. **Resource provenance**：把 FDOTHER/FDTXT/DATO/FIGANI/TAI/FDFIELD 的 loader、entry、palette、stride、clip 寫成 machine-readable bindings，並與 UI contract 對應。
   `0x22253` 的 Docker trace 已固定為 FDOTHER immediate `0x51`（十進位 **81**）→ nested `LLLLLL` entry（outer 18710 bytes、directory first-word `0x12`；nested payload #1 為 9782 bytes）；其後由 `0x11eee` 準備 renderer data，`0x22547` 以 `0x53a6d` descriptor table 做 6 次 indexed `0x22046` blit/present（每次 10ms），尾端再兩次 BIOS tick。`internal/fdother.ArchiveEntry` 現可驗證 nested raw boundary，但 frame-table／`0x11eee` data selection 尚未閉合；這是 renderer provenance，不可寫成 layout 或音訊資源。
3. **Battle interaction**：追 action menu enable gates、weapon reach、spell inventory/targeting、end-turn 判定、HUD anchor；每一項先找 caller/data flow，再改 Go。
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
