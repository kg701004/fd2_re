# 13 — 戰場選單與行動系統

> 戰棋上選一個我方單位後,怎麼移動、怎麼跳出行動選單(攻擊/法術/道具/待機/狀態)、
> 游標怎麼操作、一個單位的「一回合」怎麼算完。第 3 輪反組譯 `FD2.EXE`。

> **⚠️ 操作前必讀**：判斷「游標是否真的選中某個單位」，不要用截圖肉眼比對游標框跟角色立繪的
> 畫面位置——角色立繪比地圖磚高，會戳進正上方那格的畫面空間，造成空地也像對準角色的錯覺。改看
> 左下角迷你狀態卡：有角色頭像+HP才是真的選中；只有地形圖示是空地。詳見
> `98-tooling-infrastructure.md`「操作前必讀」與記憶`feedback_fd2_re_cursor_tile_verification`
> (2026-09-02)。

## 移動/攻擊操作流程(2026-08-18 實機操作實測,E1 行為證據,非反組譯)

以下是玩家實際操作原版 `FD2.EXE`(heavy-debug build,WSLg 視窗)觀察到的完整按鍵流程,
補上本文件先前完全沒記載的「移動」這一段。**這是行為層觀察,不是反組譯結論**——尚未
對應到具體 native 位址,若後續反組譯出對應函式,應該把位址補回這裡並升級證據等級。
詳細操作記錄見 doc58「續二十」。

1. 戰鬥開場預設有一個「瀏覽游標」,方向鍵在己方單位間切換,畫面左下角小狀態框顯示
   目前游標所在單位的 HP。
2. 對準要操作的單位按 **Enter**:進入「操作該單位」狀態,畫面左上角跳出該單位完整
   HP/MP 狀態列;背景同時有**緩慢閃爍**的移動範圍高亮(閃爍週期偏長,單張截圖容易
   剛好拍到「暗」的瞬間,誤判成沒有範圍顯示)。
3. 此狀態下方向鍵移動的是**獨立的目的地預覽游標**,不是角色本體——可以連續按很多次
   自由試探路線,角色完全不會動;游標移到已有其他單位的格子上按 Enter 沒有反應
   (格子已占用,非按鍵失敗)。
4. 游標移到空格按 **Enter 確認**:角色本體才真的走過去,隨即自動跳出攻擊/法術/道具/
   待機四選一指令環(既有 ↑/←/→/↓ mapping 見下方),中間沒有額外的「要不要行動」
   確認畫面。
5. 指令環按 **Escape**(不選任何選項)會退回步驟 2 的狀態列畫面,**不會**讓角色反灰、
   也不會撤銷剛才的移動——移動可以重來很多次,只有真的選定四選一其中一項才會消耗
   這個單位的回合。
6. 若移動後範圍內有敵人,指令環的攻擊圖示會自動預設跳動選取;直接按 Enter 確認攻擊,
   目標游標會**自動吸附到最近的敵人**,再按一次 Enter 才真正出手。
7. 命中且擊殺後,若是正常生命值歸零死亡(非記憶體竄改),會跳出「從敵人身上,得到
   XXXX 元！」戰利品對話框——這是判斷「這隻死亡有沒有真的走過原生死亡處理路徑」
   最可靠的訊號。

## 一個單位的回合:行動狀態機

以下「AA／一回合」段落是早期 gameplay 摘要，並非目前已閉合的 native UI contract；現行 action chooser、
command grid、end-turn 與 campaign transition 以 SDD56／UI matrix57 的 raw evidence 為準。舊文件把行動狀態
誤掛到 `AA(0x0D)`；目前只保留已驗證的 record byte `+5` bit0／bit7 raw predicates：

```
+5 bit0: admission test `(+5 & 1)==0`／reject test `(+5 & 1)!=0`（raw mask only）
+5 bit7: test/set/clear `(+5 & 0x80)`（raw mask only）
```

回合流程:

```
已觀察的 caller fragments：raw `+5` mask gate → 可能的移動／target helper → action chooser；
各段是否必然串成完整回合、何時呼叫 writer，仍待 current UI/campaign evidence。
```

> 攻略 modify1 揭露的行動規則(改的就是這套狀態機):
> - #5/#6「行動後可再行動」的攻略說法不能直接映射成 raw writer；是否設 `+5 bit7` 需看具體 handler。
> - #7「移動後可施法,隨時可存檔」是攻略層摘要，不能當 native end-turn 或 command gate 證據。
> - 動作完畢旗標 `0x80` 的檢查見 `0x12717`(`test byte [..+5],0x80`)。

## 行動選單選項

早期「典型戰棋的移動／攻擊／法術／道具／待機／狀態」列舉不是原版證據，已刪除。原版 action
chooser 現有 E0 的四項只可寫為 `↑=attack`、`←=command`、`→=item`、`↓=wait/field`（見下方
`0x18d8c` switch）；各 action 的完整 availability gate 仍須按各 callee 分開證明，不能以通用 RPG
假設補齊。

### `Get_EasyMagic` — 法術 / 狀態面板(已反組譯 `0x18ED0+`)

EXE 內洩漏的函式名 `Get_EasyMagic`,位於 `0x18ED0` 起。舊文件曾把 runtime `unit+0x22..0x26` 誤標成 **5 組法術 bitfield**；constructor direct trace（`0x10f6b..0x10fa5`）已推翻此說：magic raw 是 `unit+0x1a..0x1d`；`+0x22..+0x27` 目前只保留 raw transient／modifier bytes，不能由局部 writer 直接命名成 AP/DP/HIT 或 status。以下只保留函式名與 UI caller 的已證實部分，法術欄位對映維持 partial：

```
native magic raw / menu state:
    由 `+0x1a..+0x1d` 與 `0x1cff0` command path 產生可選項
    （`+0x22..+0x27` 不可當法術 bitfield，也不自動等於 named stats/status）
```

→ 即玩家按「法術」時看到的面板：可用 command 與目前 HP/MP。繪字／數字用 `0x195D6`（在 320 寬 buffer 定位繪製）。可用 command 的 label、spell-family、個別 spell ID 對照仍待完成，不得由 raw bit 或舊 M1–M5 名稱推導。

## 游標 / 鍵盤操作(已反組譯)

### 2026-07-25 Docker Capstone recheck: `0x18890` action dispatcher

`0x18890` 是「單位移動後進入 action dispatch」的 caller，而非單純繪圖 helper：它以 `ebp` 計算 `[0x53a45] + unit*0x50`，讀 unit context，呼叫 `0x18d8c(ebp, ..., mode)` 取得 action result；result `0` 繼續等待，`-1` 走取消／返回，其他 result 進入 `0x13a44` target/action path。它同時串接 `0x13488` path-walk 與 `0x134e4` 完成通知，移動後重寫 unit X/Y bytes，再由 `0x13512`／`0x13a44` 進後續 action。

這段 caller 沒有單獨證實 `0x18d8c` 的選項表與 result 編號，因此撤回「`0x18890` 只是選單繪圖」類推；目前 remake radial 方向 mapping 仍不得宣稱原版一致，直到 `0x18d8c` 本體和 menu/resource table 完成交叉引用。

### `0x18d8c` switch closure（2026-07-25, Docker Capstone）

`0x18d8c` 讀 `[0x3c57]` 後的四個分支已釘死：

| `[0x3c57]` | 方向 | native callee / 行為 | remake 對應 |
|---:|---|---|---|
| 0 | ↑ | `0x14818`(候選)→`0x115b6`(confirm)→`0x12c0d`(取target idx)→`0x1f04a`(僅算面向byte`+3`，**不**呼叫`0x28a6c`)→`0x2e2b0`(真正的攻擊orchestrator，內部呼`0x2ebe1`×3做多幀受擊/HP寫回，`0x2ebe1`呼`0x2f7b6`算命中率`(HIT-EV)%`與傷害基值`(AP-DP)*0.9`並寫回 target `+0x40`) | 攻擊（case 0） |
| 1 | ← | `0x1cff0`：配置 320×200 演出 buffer、法術 command／演出 loop（`0x1c269` 失敗會 disable） | 法術選單（case 1） |
| 2 | → | `0x1bbdc`：item action loop；case 0 讀 item record `+0xd/+0x10/+0x12/+0x15`、做 target geometry，進 `0x20c6f` effect/target path；case 1 transfer uses `0x1bb8c` insertion + `0x1b8e7` removal；case 2 `0x1bffe` equips via `0x1c1c3` compatibility + `0x1c142` slot flags | 物品（case 2） |
| 3 | ↓ | `0x13fd4`（current HP≠max HP 且 raw `+0x25/+0x26==0` 時回復 `floor(maxHP/5)`）→ `0x190ac` 格子互動／寶物檢查 | 休息回復／格子互動（case 3） |

因此撤回舊 mapping「↑道具／←攻擊／→魔法／↓待機」。`0x1cff0` 的 command-`0x1e` spell path 已證實；family priority、damage/effect jump table 仍待完整拆解，本表不宣稱所有 effect 已完成。

**2026-08-19 訂正（doc58「續二十六」，純靜態 Ghidra headless 重新反組譯 `0x18d8c` case 0）**：先前把 case 0（↑）寫成「`0x1f04a` → `0x28a6c`：攻擊目標／全螢幕攻擊演出」是錯誤映射，已撤回。完整反組譯 `FUN_0001f04a`（body `0x1f04a..0x1f0db`，僅 106 byte）證實它純粹是依攻守雙方 `+0/+1`(X/Y) 算出攻方應面向哪個方向、寫回攻方 `+3`，不呼叫 `0x28a6c`，也不做任何傷害/HP 運算。真正串接演出與命中/傷害計算的是 `0x18d8c` 在 `0x1f04a` **之後另外呼叫**的 `0x2e2b0`（先前完全未反組譯過）；其內部呼叫 `0x2ebe1`（真正的多幀受擊 HP 寫回迴圈，直接讀寫 `target+0x40`，跟 debugger 監看的原始 record 是同一份，無 shadow copy）與 `0x2f7b6`（真正的命中/傷害公式：命中率 `(uint)攻方+0x4c(HIT) − (uint)守方+0x4e(EV)` 轉 `(int)` 跟 `rand()%100` 比較，`EV≥HIT` 時因 unsigned 減法下溢成負數而**確定性 0% 命中**；命中後傷害基值 `(AP-DP)*0.9`），與 `docs/knowledge-base/27-combat-rules-and-validation-checklist.md`／`remake/internal/battle/combat.go` 既有記載的「命中率=(HIT−EV)%」「傷害≈AP×0.9−DP」逐項吻合，這是首次由反組譯（而非攻略轉錄）直接證實。完整呼叫鏈與這條路徑如何解釋「敵人 HP 卡在 1 不動」的謎團，見 doc58「續二十六」。連帶發現 `0x28a6c` 在目前 project 裡不是函式起始位址（位於 `FUN_0002872b` 內部），全 EXE 無任何靜態 `CALL` 以它為目標；`doc35` 對 `0x1561f→0x28a6c` 的呼叫描述與本輪對 `0x1561f` 原始機器碼（實際是 `CALL 0x0002e2b0`）的直接反組譯不符，這部分留給下一輪查證，本次訂正只涵蓋 `0x18d8c` 表格本身。

### `0x1cff0` command evidence（2026-07-25, Docker Capstone）

`0x1cff0` 會以 `[0x3c57]` 選中的 byte 從 local command array 取出 `0x4e516` record。修正舊筆記：MP gate 是 record `+5`（`0x159fa` 的 direct compare），不是 `+4`；`+3/+4/+6` 在本 selector 的 geometry/control path 都有讀取，但未追到 field-name 前仍只能保留 raw offsets。已釘死的分支：command `0x17` 走特殊 target geometry（`0x14818`，使用 record `+6`）；command `0x1e` 走 `record+3-0x10` → `0x149f8` 的 spell-family path；其他 command 走 `0x2a6bd` 或 `0x1d6c8` jump-table effect path，最後統一回 `0x1aa1d`／`0x1d4f6` 收尾。

官方 IDA 9.4 的 `0x1d3f3` dispatch 再釘細一層：target confirm 後 command ID `0..8`、`0x18`、以及 `>=0x1c` 直接呼叫 `0x2a6bd(unit, commandID, target, scratch)`；ID `0x09..0x17` 與 `0x19..0x1b` 則先以 `0x1d6c8(commandID)` 做四輪 palette flicker，再呼叫 `funcs_1541f[commandID]` effect jump table。故悠妮 source mask 的 command 0 已能證實進 generic effect pipeline，卻尚未證實其效果名、傷害公式或等同 legacy `Spells[0]`；remake 對 unknown effect 必須繼續 fail-closed。

後續 direct dataflow 已閉合 command 0 的數值 writer：`0x2a6bd` 對每個 target 呼叫 `0x1c75e(target,commandID)`；它讀 command record `u16+0`／byte `+2`，以 target class ID（constructor 寫入 unit `+0x20`）索引 `word_51f96` 形成 base。命中擲骰是 `0x1c7ed call 0x4e893` 後取 shared uint16 state `%100 < record[+2]`；命中後 `0x1c81f` 在 `0x1c869` 再呼同一 RNG，以 90% 加 0..9.9% random 的整數值扣 target `+0x40`，clamp 0。舊 adapter 使用 Go `math/rand` 是錯誤替代，已刪除。`word_51f96` 的 loaded file offset=`0x51d96`，就是 `resist_crit.json` 每職業的 `resist_raw`（每 row 4 bytes）；因此 base=`record.dmg*resist_raw/10`，等價於既有職業魔抗百分比。這是 native damage/HP ABI；command0 effect name、target family與 normalized spell equivalence 仍未證實。

同一條 caller dataflow 排除了「confirm 只傳回一個格子」的猜測：一般 record 先以 actor cell 的 `+3/+6` 呼叫 `0x14818` 產生可選中心 stack candidate-index array，`0x115b6` 接收 `(mode=+6,count,array)` 做游標／確認；成功後 `0x1cff0` 以**確認游標格**的 `+4/+6` 第二次呼叫 `0x14818`，`0x2a6bd` 接到的是這個第二 array/count，並逐 element 呼叫 `0x1c75e`。故 command0 有 per-final-effect-candidate 傷害；`+6` target-code 與 `0x14818` geometry 的現行 direct closure如下。現有單格 normalized target UI 仍不是原版證明。

`0x14818` 本體現已釘其 raw geometry：record `+3 < 0x10` 時交由 `0x4e555` 產生 map/reach mask；`+3 >= 0x10`
時只 mark 同 x 或同 y、距離不超過 `(+3-0x10)` 的十字格。接著掃 roster，略過 inactive unit 與 mask=`0xff` 格，再用 record `+6` 篩 runtime `unit+6`：code 0 要 `==0`、1 要 `!=0`、2 要 `==1`、3 要 `==2`。`0x10c50` constructor 已證實 `unit+6` 是 FDFIELD `b0` camp（0敵/1友/2己）；故 code 0=敵、1=非敵、2=友、3=己。**2026-07-28 correction：**先前把 code2 寫成 `!=1`／非友是分支方向抄反，已由 `0x149b0..0x149be` 與 `0x147d5..0x147e1` direct Capstone 撤回。

上述 `dist<0x10` 不是無條件 Manhattan：`0x4e555(0)` 回傳 20-byte cost row，真正的 `0x4e040` 以 `dist`
做四方向 flood-fill，grid flag `0x40` 不可通過；`0x80` 不是零成本，`0x4e19a`
會在扣除 terrain cost 後把該格的 remaining-budget byte 強制寫成 0，因此該格可達但不能形成
zero-cost chain。對 command selector 而言 row index 固定
為 0，EXE `word_61646` 的該 20-byte row 全為 1；故不套地形加權，但障礙仍可使可達格少於 Manhattan circle。
remake `InCastRange` 仍不能作為 native contract，除非也帶入同一 grid flags。

`0x149f8` 的本體語意是 target-candidate builder：依起點／方向步進 `count` 次，做地圖邊界檢查，呼叫 `0x12c0d` 取 unit，依 selector 篩選 `unit+6` 狀態後把 unit index 寫入輸出陣列。一般 AI caller 的 selector-family 對照仍待 RE；但玩家 ID30 已由 `0x1d339` 的完整 push 順序閉合為一條不同的 special line（如下）。

`0x115b6` 的 confirm loop 已直接讀 `0x53ab1/0x53ab5`，並以兩值比對 runtime unit `+0/+1`；方向鍵 helpers 改寫同一對 globals。因此它們是這條 selector 的 cursor cell，而不是相機 scroll。ID30 的 `0x1d287..0x1d354` 先以 record `+3=0x14` 的 normal `0x14818` candidate list 確認一個 enemy cursor，保存確認前 cursor `(savedX,savedY)`，再傳確認後 cursor `(confirmedX,confirmedY)` 給 `0x149f8`。callee 的七個 args 已可靜態對應：output、confirmed X/Y、saved X/Y、`count=record+3-0x10=4`、selector=1。它從 saved cell **先走一步**，若 X 不同則只走 X（savedX>confirmedX 為 −1，否則 +1）；僅 X 相同才以同規則走 Y；兩座標相同落入原始 `<=` 的 +Y branch。每一步由 `0x12c0d` 取得第一個 active unit，selector=1 僅收 native camp=0（Go `Enemy`），越界只是略過。故 ID30 是「保存游標→確認游標」的最多四格 cardinal line，不是 actor→confirmed 的 generic ray，也不走第二次 `0x14818`。`ExecuteNativeCommand30` 已用顯式兩 cursor 接 strict final state slice；native cursor UI、multi-hit indexed presentation、SFX 仍未接。

### `0x1bbdc` item action evidence（2026-07-25, Docker Capstone）

物品 action 不是「完全不存在」：`0x1b932→0x1b9de` 是八格 raw
inventory 的 **兩欄×四列** selector。它只計算 signed flag非負的 occupied
prefix；原版 insertion/removal 維持 compact prefix，不把 raw hole 畫成
固定空白列。↑/↓沿 prefix linear wrap（slot3→4會跨欄），←/→以±4切欄；
Enter/Space confirm、Esc cancel。battle-use mode另外拒絕 selected item
row `+0x0d==0`，非 battle mode不套此 gate。`0x1bb8c` 只把 item 插入
第一個空槽；case1 與 `0x1b8e7` 串成 transfer。case2 進 `0x1bffe`，
由 `0x1c1c3` compatibility 與 `0x1c142` 設 `0x40` equipped flag，再
呼 `0x1b750` 重算。case0 的 target/effect ABI現已閉合；remake item
Enter仍未接 transaction。

`0x184c0` 的 original geometry 也已固定：display index `n` 的 label
在 `x=42+150*(n/4), y=103+22*(n%4)`，第五筆從 `(192,103)` 開始；
category icon在 `x-29,y-2`，item文字取 FDTXT index `itemID+181`，
selected/unselected color raw 201/205。row byte0 `<0x15`／`<0x20`／其他
選 icon59/60/61，equipped再+3；右側 stat icon/value 依同 byte與
type5/11 分流。`NativeItemSelectorCells` 保存 compact layout與raw icon
IDs，但 indexed blit/字型與 opening/closing animation 尚未接 GUI。

opening/closing schedule 本身現已閉合：`0x17e0b` 依 frame11→0 開啟，
`0x1b932` 依0→11關閉，每幀都先從 saved 64000-byte buffer重建，再由
`0x18409` 組三塊 320-stride region並present。left panel來源
`(5,7,86,86)` 在 frame6後每幀向左clip16px，frame11只剩11px；
upper來源 `(92,7,223,86)` 在 frame3後向上clip16px，frame9起消失；
bottom來源 `(5,94,310,102)` 從 y94每幀下移16px，frame6起消失。
`NativeItemPanelSchedule` 保存十二幀與exact clipped rectangles。
`0x17eef` 的 source construction 也已閉合：先以
`0x168b6(dst,320,5,7,5,5)` 在 `(5,7)` 建 5×5 框，unit record `+7`
選 DATO portrait並貼到 `(8,10)`；`[0x53a81]+86/+90` 是 FDOTHER #5
LMI1 directory entries 20/21，分別貼到 `(92,7)` 與 `(5,94)`。
`0x17fc0` 的兩條 bar、四個 compared-number、八個 raw-number、三段
FDTXT及四組 icon destination/record-offset schedule 已由
`NativeItemPanelBaseLayoutFor`／`NativeItemPanelDataPlanFor` 資料化並測試。
`RenderNativeItemPanelResources` 已以玩家 FDOTHER/FDTXT/DATO archive完成
corrected 49-cell grid、portrait frame0、entries20/21，以及 `0x17fc0`
bar/digit/icon/FDTXT dynamic overlay，整張 atomic commit。三條 codec
嚴格分離：raw opaque cells、four-mode transparent frames、FDOTHER#4
1bpp font。`RenderNativeItemPanelRows` 另完成 `0x184c0` compact rows：
category/stat icons、item FDTXT `ID+181`、selected color201、unselected205
與 stat value座標。可重現 oracle 見
[`item-panel-native-indexed.png`](../figures/item-panel-native-indexed.png)。
Ebiten runtime現以 `NativeItemPanelRecordForUnit` 嚴格要求 raw `+6/+8`、
`+0x1f/+0x20`、DATO selector與8格inventory provenance，接完整 compositor、
compact ↑↓/←→ input及 opening11→0/closing0→11 clipped presentation；
缺證據／缺archive即回 legacy shell。`0x112a5` 已證實 JOIN id直接選
lower constructor record，寫 `+0x1f/+0x20`；轉職只改 `+0x20`與`+7`。
30章scenario、persistent overlay及class-change writer現保留這組獨立raw
provenance，正常ch01 campaign integration已可準備原版面板。現在剩 item
Enter的大多數 effect/target transaction；尚未獨立證實的 raw offsets 仍不命名。

第一組完整 Enter transaction 已接：tracked IDs198/199/200 的 type8/9/10
與 IDs94/95/96 的 type17/18/19 均以 row selection/effect mode0、
target code1 經兩段 `0x14818` 驗證 actor self-target。前組依 `0x21082`
對 raw base AP/DP/DX 做16-bit wrap加值；後組對 MaxHP/MaxMP/MV 加值，
其中 MV保存相鄰EXP byte，Max值增加不回填current值。兩組都依
`0x1b8e7` compact移除來源。成功後 `0x1bbdc` 直接呼 `0x13512`，故 runtime
同時設 raw `+5 bit7`、normalized `Acted`並退出action；不是回到item menu。
AP/DP缺 equipment-base provenance時整筆拒絕，不以有效值冒充raw base。

`0x20c6f` 已再以 Docker Capstone 展開：它依 item `+0xd` type 分派至多個原生 effect routines（例如 type `5/0xd→0x211a4`、`6/7→0x22af6`、`8/9/0xa→0x21082`、`0xe/0xf/0x10→0x22d1b/0x22866/0x22721`、`0x15→0x2111a`、`0x17→0x2218a`）。其中 type5/13 已定案為以 row `+0xe` 恢復 target-list HP：type5 隨後經 `0x1b8e7` 消耗來源 slot，type13 不移除來源；這是 effect 與 consumption contract，不推測道具顯示名稱。其餘尚未閉合的 routine 仍不可直接映射成藥水／卷軸規則。

其中 type `8/9/0xa→0x21082` 已由 raw table 全表對齊與 `0x1145a`
base/equipment data flow 閉合：item row `+0xe` 分別永久增加 persistent
base AP(`+0x37`)、DP(`+0x39`)、DX(`+0x3e`)，呼叫 `0x1b750` 重算後移除
來源 slot；已知 IDs 198/199/200 的量為 9/9/7。顯示 selector 仍未命名，
也不能把此語意套到共用 callee 的 type17–19。type6/7 已閉合成
consumable marker-clear HP restore：分別讀 target runtime record
`+0x25/+0x26`；nonzero 才以 base amount10 經 `0x1c916` 實際恢復
9 HP、清同一 record marker，最後消耗來源 slot。tracked IDs196/197。
舊 adapter 將 marker 當 parallel `flags[]` 的實作已修正；status 名稱未知。

type11 已由同一 dispatcher loop 閉合為 MP restore consumable：row `+0xe`
是 amount，target max MP `+0x46==0` 時跳過且不前進 RNG；其餘依 list 順序
由 `0x1c9dd` 增加 current MP `+0x44`、cap `+0x46`，最後經 `0x1b8e7`
消耗來源 slot。已知 raw IDs206/207 amounts=80/200；顯示名稱仍不猜測。

type12 則重用 `0x22997`：target marker `+0x24` 非零時跳過且不耗 RNG；
成功時寫 `(rng%4)+2` 並把 derived HIT/EV `+0x4c/+0x4e` 各加 15。
dispatcher 直接 cleanup、不移除來源 slot。raw fixture 目前只有 ID210
走此 type；道具名稱與 marker 的 UI 顯示仍未閉合。

type15/16 也是 retained modifier：type15 以 marker `+0x23` gate，將
derived DP `+0x4a` 增加 `trunc(DP×0.15+1)`；type16 對 marker `+0x22`
與 derived AP `+0x48` 做同式。marker 已存在就不耗 RNG，兩條 dispatcher
都不移除來源；tracked rows 是 ID213/214。

type14/22 共用 `0x22d1b` 且保留來源。marker (`+0x26/+0x27`) 必須為零、
class 不能是 `0x19/0x1a`；第一 RNG `%100<50` 才呼
`0x1c81f(target,10)`。注意 10 是 damage base amount：`0x1c81f` 再消耗
第二 RNG，原生整數公式在 amount=10 時實際減 9 HP；第三 RNG 才寫
`(rng%4)+2` marker。tracked rows 是 ID212/57。marker 的 status 名稱未知。

type17–19 雖共用 `0x21082`，欄位已由獨立 producer/consumer 閉合：
type17 max HP `+0x42` +20、type18 max MP `+0x46` +20；type19 對
`+0x3b` 做 word +1，但 caller 保存並恢復 `+0x3c` EXP，因此結果只增加
MV byte、EXP 不變。三條都由 callee 移除來源 slot；tracked IDs94/95/96。

type20/21/24 的 row word 不是恢復量或 MP 扣值，而是交給 `0x1c75e`
的 command ID。type20/24 先走 `0x1cd17` 十幀 indexed presentation；
type21 由 `0x2111a→0x1cac7` 走另一套 presentation，之後三者都依
target list 呼叫既有 command damage writer。dispatcher 不呼叫
`0x1ca89`、也不移除來源 slot。tracked type20 IDs11/56/60 對 commands
2/0/2，type21 IDs29/38/51/99 對 6/1/7/6，type24 ID79 對 command3。
先前把 `0x1cac7` 說成 MP subtract 是地址混淆，已撤回；真正的 command
MP debit helper 是 `0x1ca89`。

type23（`0x17→0x2218a`）也已閉合 post-confirm transaction。item selector
要求 actor runtime `+0x08==24` 且 max MP `+0x46>=20`；舊稱
class/level gate 是錯的。handler 只取 target list 第一筆，以
`0x1ca89(actor,command23)` 直接按 command record `+5` 扣 current MP
（原生 16-bit wrap），再依 target class `+0x20`／level `+0x21` 增加
raw accumulator。兩次 `0x22253` 先以原座標演出並寫 `0xff/0xff`，
再寫 destination cursor globals 至 target `+0/+1`；不走 path traversal，
dispatcher 也不移除來源物品。tracked item ID101 的 row word1 不被
handler 使用。`NativeItemRelocationRoute`／executor 保存這些 state
mutation。mode-6 落點 predicate 也已資料化：除 selected target 外，
任何同座標且 raw `+5 bit0==0` 的 record 都阻擋；movement selector
通常取 target class `+0x20`，`+7==0x1c` 改1，否則 class `0x13` 或
race `+0x1f∈{4,5}` 改19；`0x4e555` 對應 29×20 table 的目的地 terrain
entry 必須等於20。indexed renderer 與 Ebiten UI 尚未接。

選單游標導航在 `0x1864D` 一帶,用 PC 方向鍵掃描碼:

| 掃描碼 | 鍵 | 行為 |
|---|---|---|
| `0x48` | ↑ | 上移選項 |
| `0x50` | ↓ | `[ebx+0xc]==0` 時 `[0x3C57]=3` |
| `0x4B` | ← | `[ebx+4]==0` 時 `[0x3C57]=1` |
| `0x4D` | → | `[ebx+8]==0` 時 `[0x3C57]=2` |

- **`[0x3C57]`** = 目前選到的選項編號(全域)。↑→0、(其餘方向)→1/2/3。
- `[ebx]` / `[ebx+4]` / `[ebx+8]` / `[ebx+0xC]` = 上/左/右/下各方向是否有可移動到的相鄰選項
  (選單為 2D 排列,該方向無項目(旗標≠0)就不動)。
- 「方向鍵移到神祕商店」(攻略 #16,`0x2DBF3` 等多處)= 商店畫面的方向鍵游標邊界判定。

### 確認 / 取消鍵(已反組譯 `0x18610`)

選單主迴圈 `call 0x18698` 取鍵後:

| 鍵 | 掃描碼 | 行為 |
|---|---|---|
| **Enter** | `0x1C` | 確認 / 選定(函式回傳 1) |
| **Space** | `0x39` | 同 Enter,確認 / 選定 |
| **ESC** | `0x01` | 取消 / 返回(`0x18698` 回傳 1 → 外層回傳 −1 = 取消) |
| ↑ ↓ ← → | `0x48 0x50 0x4B 0x4D` | 移動游標 `[0x3C57]`(受各方向啟用旗標 gate) |

→ **「ESC 取消、Enter / Space 確認」的離開語意在原版即成立**(ESC 比較在 EXE 出現 72 處 = 各層皆可退)。

## 相關全域 / 結構

- `[0x3C57]` 選單游標選項;`[0x3C43]`/`[0x3C47]`/`[0x3C4B]`/`[0x3C4F]` AI 最佳落點/目標(見 11-…)。
- 單位陣列 `[0x3A45]`,每單位 0x50,數量 `[0x3BEB]`;已驗證 action/inactive predicates 在 record `+5`，其餘欄位保持 raw。

## 重製對應(SDL2 / Ebiten)

| 原版 | 現代 |
|---|---|
| 舊 AA 行動狀態(00/01/80) | 已撤回；目前只保存 raw `+5` bit0/bit7 predicates，end-turn 組合條件仍待 evidence |
| flood-fill 移動範圍 | BFS/Dijkstra(MV + 地形成本)→ 高亮可走格 |
| `[0x3C57]` 選單游標 + 方向鍵 | 選單元件,↑↓←→ 導航、Enter 確認、ESC 取消(見離開鐵則) |
| Get_EasyMagic | 依 native magic raw／command inventory 動態產生法術選單（`+0x22..+0x24` 不是 bitfield） |
| 選目標範圍判定 | 共用攻擊/法術 range + LOS 計算 |

## native commands 17..19 殘留缺口收斂(2026-08-19)

> 回應 `91-worklist.md` 第 536 行「**native commands 17..19 transient modifiers**」段落結尾列出的
> 四項殘留缺口：status labels、duration decrement、UI、engine integration。方法：純靜態 Ghidra
> headless(`FD2Analysis3`，唯讀)重新反組譯 `0x1A866`(本輪新增)，並交叉核對既有
> `docs/data/command_labels.json`（FDTXT_000 native 字串表）與 `remake/internal/battle`
> 既有實作。逐項結論如下。

### 1. status labels（已閉合）

`docs/data/command_labels.json`（來源 FDTXT_000，`0x1ceed→0x15f84([0x53a7d], 0x1b9+command_id, …)`
既有 provenance）直接給出 native 遊戲內名稱：`command17="魔刃術"`、`command18="魔鎧術"`、
`command19="風行術"`。這與 `spells.json` 的 raw 7-byte row 交叉吻合：ID17/18 的
`dist=4,range=2,mp=5`、ID19 的 `dist=4,range=2,mp=8`，恰好對上 `docs/knowledge-base/02-game-data-reference.md`
§6.4 表格「魔刃術(攻擊術) dist4/range2/mp5」「魔鎧術(防禦術) dist4/range2/mp5」
「風行術(加速術) dist4/range2/mp8」三行——native record 與攻略公式表雙重印證同一組法術 ID。

本輪額外反組譯出**更直接**的證據：`0x1A866`(見下節)在每個 transient byte 歸零時，會用
`0x15F84` 印出對應的**到期訊息**，string index = `0x1E1 + transient陣列索引`。索引 0/1/2
正是 command17/18/19 各自的 duration byte(`+0x22/+0x23/+0x24`)。用既有的
`tools/export_story_index_map.py:parse_fdtxt_strings` + `docs/data/glyph_map.json` 對
`extracted/raw/FDTXT/FDTXT_000.bin` 解出這三條原始字串（本輪新解出，未見於既有文件）：

| index | 陣列索引 | offset | 到期訊息(FDTXT_000 原文) | 對應 command |
|---|---|---|---|---|
| 0x1E1 (481) | 0 | `+0x22` | 「增加攻擊力的效果消失了！」 | 17 魔刃術(AP+15%) |
| 0x1E2 (482) | 1 | `+0x23` | 「增加防禦力的效果消失了！」 | 18 魔鎧術(DP+15%) |
| 0x1E3 (483) | 2 | `+0x24` | 「增加速度的效果消失了！」 | 19 風行術(HIT+15,EV+15) |

三條文字與 `command_labels.json` 的法術名稱、`02-game-data-reference.md` §6.4 的效果描述完全一致，
status labels 缺口視為**完全閉合**。附帶一個措辭差異：ID19 的到期文字寫「速度」，但
`0x1B750`/`0x22997` 的實際 writer 是對 derived `+0x4c/+0x4e`（HIT/EV）各加 15，不動任何
MV/速度欄位——這是原版文字的比喻（風行=移動快=直覺聯想「速度」），不是機制上的第三個效果，
撤回先前草案「風行 MV+2」猜測後不需要再懷疑一個隱藏 speed 欄位。

同一批解碼也順帶把陣列索引 3/4/5(`+0x25/+0x26/+0x27`)的到期文字釘死：
「身上的毒性消退了！」／「身上的痲痺消退了！」／「封咒的效果消失了！」，與既有
`command20/26=+0x25`(中毒)、`command21/27=+0x26`(麻痺)、`command22=+0x27`(封咒) 的結論
（見 doc56 `2026-08-14` 補充）形成第三重獨立印證(command label + `0x1A866` 中毒迴圈 + 本輪到期文字)。

### 2. duration decrement（已閉合，本輪自行重新反組譯確認）

`FD2Analysis3` 唯讀反組譯 `0x1A866`(size 到 `0x1AA1C`)證實它是**兩個獨立迴圈**：

- **迴圈 1(中毒扣血，`0x1A897..0x1A93C`)**：對每個 `record+6==selector`、`record+5&1==0`、
  `record+0x25!=0` 的單位，`uVar2=word[+0x42]/10`(maxHP/10)，`word[+0x40] -= uVar2` 並 clamp
  至 0，然後呼叫 `0x12D7B`(數值渲染，push 單位 index)、`0x1956B`(push `record+7`)、
  `0x15F84(txtbuf=[0x53a7d], idx=0x1E7, …)`——**固定字串 idx487「毒性發作，HP減少<點數>點！」**，
  再呼又 `0x4E381/0x1E5C0/0x196CB`。這條迴圈**不遞減** `+0x25`，只扣血並顯示訊息，跟 doc56
  已有的 `ApplyNativeTransientPoisonDamage` 描述一致。
- **迴圈 2(六 byte 遞減，`0x1A957..0x1AA18`)**：對每個合格單位，逐一檢查 `+0x22..+0x27`
  六個 byte(內層 `EDI=0..5`)，非零才 `DEC`；`DEC` 後若變 0，才呼叫同一組
  `0x12D7B/0x1956B/0x15F84(idx=0x1E1+EDI)/0x4E381/0x1E5C0/0x196CB` 顯示到期訊息，
  **緊接著呼叫 `0x1B750(unit)`**(`0x1AA0F PUSH EBP; 0x1AA10 CALL 0x1B750`)。

`0x1B750` 已由既有 2026-08-02 反組譯（`sub_1B750` 範圍 `0x1B750..0x1B83D`）證實：它讀
`+0x22/+0x23` 是否非零決定要不要把 AP/DP 乘 1.15(x87 朝零)、`+0x24` 非零決定要不要把
HIT/EV 各加 15，再寫回 `+0x48/+0x4A/+0x4C/+0x4E`。因此 duration 到期並不是「對
`+0x48..+0x4E` 做一次對稱減法」，而是**整個 derived-stat 欄位由 `0x1B750` 重新從
persistent base 生成**——duration byte 一旦變 0，下一次(也是緊接著這一次)`0x1B750` 呼叫
自然不再套用 15% / +15，等同移除該增益。這條路徑跟 `+0x25/+0x26/+0x27`(中毒/麻痺/封咒)共用
同一個 decrement 迴圈與到期訊息呼叫序列，但**只有 index0/1/2(command17/18/19)緊接著呼叫
`0x1B750`**——此為本輪反組譯新確認的細節，先前文件只泛稱「歸零才…並 `0x1B750` 重算」，
未逐 index 檢查是否每個 offset 都觸發同一個 recompute call（結果是：確實六個 index 共用同一段
程式碼、同一個 `CALL 0x1B750`，並非只有 17-19 專屬分支）。

remake 對應：`battle.TickNativeTransientsRaw(selector)`(`remake/internal/battle/native_transient.go`)
已忠實保留這個「逐 byte 獨立 decrement、歸零回報 expiry」的資料層行為；但它**不**呼叫任何
`0x1B750` 等價重算（`ApplyNativeRuntimeEquipmentRecalc` 是獨立函式，未被 tick 呼叫串接），
所以 raw-ABI 這條路徑目前只更新 duration 陣列本身，不會連動改回 derived AP/DP/HIT/EV——
这是下一節 engine integration 缺口的一部分。

### 3. UI（native 端已閉合為「文字訊息」，remake 未接）

原版沒有找到任何獨立的狀態圖示/圖層渲染呼叫加在 `0x1A866` 的兩個迴圈裡；兩個迴圈能找到的
UI 只有 `0x15F84` 文字框訊息（同一個對白/選單渲染器，見 doc14/47/57 既有 provenance）：
中毒扣血時逐單位跳出「毒性發作，HP減少X點！」，任一 transient byte 到期時跳出對應的
「增加OO的效果消失了！」（或中毒/麻痺/封咒版本）。沒有找到常駐圖示（icon）或角色卡狀態列的
額外渲染呼叫——**native 端的「UI」就是這個到期/扣血 popup 文字，不是持續顯示的 buff 圖示**，
這點更正了本段任務描述中「有沒有畫面顯示」這個問題預設的「持續圖示」假設。

remake 目前完全沒有對應實作：`grep BuffAPPct|BuffDPPct|BuffHit|BuffEV|BuffTurns` 全 repo，
`cmd/fd2/main.go` 只有戰鬥結束/存檔時的歸零賦值，沒有任何繪製或訊息呼叫；native raw ABI 側
（`ApplyNativeCommandModifier`/`ApplyNativeRuntimeEquipmentRecalc`/`TickNativeTransientsRaw`）
也沒有訊息佇列串接。UI 缺口對 remake 而言仍是真缺口，但 native 端「應該長什麼樣」現在已經
有逐字原文可以對照實作（見上表六條字串）。

### 4. engine integration（兩條並存、互不相同的路徑，如實記錄）

- **legacy/normalized 路徑（已上線，玩家可玩到）**：`remake/internal/battle/magic.go`
  `applySpell` 的 `case 17/18/19` 呼叫 `applyBuff(tgt, rng, apPct, dpPct, hit, ev)`，寫入
  `Unit.BuffAPPct/BuffDPPct/BuffHit/BuffEV` 與共用計時器 `BuffTurns`(`buffRoll`=2–4 回合，
  對齊 doc02 §6.4)；`Unit.EffectiveAP/EffectiveDP/EffectiveHIT/EffectiveEV`(`model.go:441-446`)
  在戰鬥公式中套用這些加成；`Unit.TickStatus()`(`model.go:450-462`)在 `BuffTurns` 歸零時
  **一次性清空全部四個欄位**（對稱、非逐效果獨立到期）。`TickStatus()` 已接在
  `cmd/fd2/main.go:9535` 的真實回合結算迴圈裡，並有 `magic_test.go`/`native_command_compound_exec_test.go`
  regression。這是一個**刻意簡化**的可玩近似（單一共用 timer、對稱清除），doc42 稽核表已明示
  「不能把 legacy Buff 視為同一機制」——它不是 native raw ABI 的位元組對映，只是同一份
  doc02 效果數字的另一種實作。
- **native raw ABI 路徑（RE 已閉合、未接成可玩指令）**：`battle.ApplyNativeCommandModifier`
  嚴格映射 ID17→`0x22721`、ID18→`0x22866`、ID19→`0x22997` 的 raw arithmetic（`__CHP` 朝零、
  `rand()%4+2` duration），`battle.ApplyNativeRuntimeEquipmentRecalc` 保存 `0x1B750` 的
  1.15/朝零/+15 條件式 synthesis，`battle.TickNativeTransientsRaw` 保存 `0x1A866` 的
  decrement 迴圈。**這三個函式彼此沒有被串接**：沒有一個等價於 `ExecuteNativeCommandClearRestore`
  (ID20/21)或 `ExecuteNativeCommandApplication`(ID22/26/27)的
  `ExecuteNativeCommand17_19`——也就是說 ID17/18/19 缺少「target 解析 + `0x1CA89` MP debit +
  呼叫 `ApplyNativeCommandModifier` 寫 duration」這一層 command executor，跟已經接好的
  ID20-27 兄弟指令形成明顯落差(`56-fd2-remake-sdd.md` UI-03 matrix 同一行已標「未接」)。
  另外，即使日後接上，`ApplyNativeRuntimeEquipmentRecalc` 目前也未被 `TickNativeTransientsRaw`
  的 expiry 呼叫，duration 歸零不會自動觸發 recompute；且目前所有地圖資產的
  `native_transient` 皆全零(doc56 已記錄)，就算接上也暫無實機可觀察效果。

**結論**：玩家在 remake 裡確實能施放並看到魔刃/魔鎧/風行的效果（透過 legacy 路徑），但那是
一個經過驗證吻合 doc02 數字的簡化近似，不是逐位元組還原原版 `0x22721/0x22866/0x22997→0x1A866→0x1B750`
的 native ABI；後者仍只是三個彼此獨立、有測試覆蓋的資料層 primitive，尚未組成一個可執行的
command，也沒有訊息/UI。

### 對 worklist 第 536 行的完成度

四項殘留缺口：**status labels 已閉合**(FDTXT_000 command label + 本輪新解出的到期訊息文字
雙重印證)、**duration decrement 已閉合**(本輪重新反組譯 `0x1A866` 兩迴圈，確認歸零後呼叫
`0x1B750` 重算而非對稱減法)、**UI 已釐清 native 端形態**(到期/扣血文字 popup，非持續圖示；
remake 未實作)、**engine integration 誠實區分兩條路徑**(legacy 已上線可玩、native raw ABI
三個 primitive 未串成可執行 command)。第 536 行本身不修改，但其結尾「status labels、duration
decrement、UI、engine integration 尚未閉合」的斷言至此可視為**前三項收斂、第四項精確定位剩餘
落差**，不再是完全開放的未知。

## native commands 20..27 殘留缺口收斂(2026-08-19,續)

> 同一批任務的延續：套用剛完成的 17..19 方法(純靜態 Ghidra headless 重新反組譯 command
> handler，交叉核對 `docs/data/command_labels.json`/FDTXT_000 與 `remake/internal/battle`)
> 到 command 20..27 家族。方法與工具同上一節：`FD2Analysis3`(唯讀)+
> `analyzeHeadless -readOnly -noanalysis`，用 `getFunctionContaining`/強制 `disassemble()`
> 逐位址驗證，不信任任何舊文件的位址轉錄而不覆核。

### 0. worklist 行號對應澄清(先確認，任務本身要求)

worklist 開頭的「D-」稽核區塊（約第 75-85 行）引用的行號(510/532/533/534/536/538/539/540/
541/548)是**舊快照**，檔案後續增補內容把它們全部往下推移；今天直接讀那些行號會看到完全無關的
內容(ch02..ch15 story handler 清單)。逐條用內文比對(doc56 行號/關鍵字)才能定位真正對應項目：

| 任務給的行號 | 實際對應 | 現行 worklist 位置 |
|---|---|---|
| L510 | `0x1cff0` command table／完整 native 演出 | 現行 L665(「魔法系統」項) |
| L532 | doc56 舊 L608-616＝IDs13..16 治療 | 現行 L687 |
| L533 | doc56 舊 L618-627＝ID24 | 現行 L688 |
| L534 | doc56 舊 L775＝UI-03 matrix「28,29,31」列 | 現行 L689 |
| L536 | doc56 舊 L770＝UI-03 matrix「17–19」列(逐字比對「`ApplyNativeRuntimeEquipmentRecalc`…command transaction與phase-expiry caller仍未接」) | **就是上一節已收斂的 17..19 項本身**，不是另一個 536 鄰近項 |
| L538/539 | doc56 舊 L677-689＝`command_labels.json` 20/21/26/27/22 命名補充 | 現行 L691(17-19 項尾註)+本節 |
| L540 | doc56 舊 L698-722＝`0x1a30b` 全流程 7 步驟+`completeTurn()` 接線 | 現行 L691 段落內(同一大節) |
| L541 | doc56 舊 L724-729＝ID23 relocation | 現行 L696-701 |
| L548 | doc56 舊 L731-736＝IDs25..27 jump table | 現行 L703-709 |

**L536 的結論**：任務描述本身已預期「這行行號跟已解的17-19那項不同,可能是另一個536-鄰近項」——
逐字核對後確認**不是**另一項，就是 17-19 那條(doc56 UI-03 matrix 表格同一行同時涵蓋 raw
writer／`ApplyNativeRuntimeEquipmentRecalc`／「command transaction與phase-expiry caller仍未接」
三件事，跟上一節「native commands 17..19 殘留缺口收斂」逐項對應)。上一節已經完整處理，此處不重複。

### 1. status labels(全部七個 command 的正式名稱，含新解出的 24/28/29/30)

`command_labels.json` 用 `docs/data/glyph_map.json` 解出的完整清單（`export_story_index_map.py`
既有 pipeline，Read 工具直接讀取避免終端機字碼錯亂）：

| command | label | 對應 offset/機制 |
|---|---|---|
| 20 | 解毒術 | `+0x25` 清除 |
| 21 | 社麻術(疑「解痲術」字模誤判，見 doc09) | `+0x26` 清除 |
| 22 | 封咒術 | `+0x27` 施加(無對應清除指令) |
| 23 | 傳送術 | 特殊座標搬移(非 CastArea) |
| 24 | **破龍擊**(本輪新解出，doc56 先前只描述機制未命名) | 玩家專屬 derived-strike，倍率15 |
| 25 | 行動術 | 清 `record+5` bit `0x80`(acted flag) |
| 26 | 毒擊術 | `+0x25` 施加 |
| 27 | 麻庫術(疑「麻痺術」字模誤判) | `+0x26` 施加 |
| 28 | 淒煌斬 | derived-strike 倍率20 |
| 29 | 熾炎刀 | derived-strike 倍率12 |
| 30 | 音速刃 | 特殊 cursor derived-strike 倍率18 |
| 31 | (FDTXT string 472 為空字串) | derived-strike 倍率18(與30共用預設倍率，命名缺) |

24/28/29/30 是本輪新查(先前 doc56/doc13 只描述數值行為，未附遊戲內名稱)。31 的空字串不是解碼失敗，
是資源本身該 slot 沒有文字——不可臆測名稱。

### 2. commands 20/21：清除/回復路徑(反組譯確認，位元組級)

強制反組譯 `0x22a85`(cmd20 wrapper)/`0x22bc6`(cmd21 wrapper)/`0x22aa8`/`0x22af6`，證實：

- `0x22a85`：`PUSH 0x25`(flag offset 常數，即 `+0x25`)→ 轉發 → `PUSH 0x14`(=20，command ID 常數)
  → `CALL 0x22aa8`。
- `0x22bc6`：`PUSH 0x26`(flag offset)→ 轉發 → `PUSH 0x15`(=21)→ **`JMP 0x22a9b`**——不是獨立
  call，是直接尾跳進 cmd20 wrapper 呼叫 `0x22aa8` 前的同一段程式碼，兩個 command 100% 共用同一份
  機器碼，只差兩個立即數常數。
- `0x22aa8`：`0x1CA89(actor, id)` MP debit → 轉發 5 個參數給 `0x22af6`。
- `0x22af6`：動畫 `0x1C4CC`/`0x1C2DA` → 逐 target 迴圈：讀 class(`+0x20`/`+0x21`)算 class-adjusted
  level(class 在 9..0x18 之間**不**加 `0x1e`，否則加)→ 讀 `record[+offset]`(`+0x25` 或 `+0x26`)→
  為 0 就走失敗顯示(`0x1E1DC`)；非 0 就固定以 `record10`(literal `0xa`)呼 `0x1C916(target,10)` 回血、
  `0x1E0DB(...,0x69,target)` 顯示、**清空該 flag byte 為 0**、`class-adjusted level << 2`(×4)
  累加進 `[0x53EC8]`（見第 7 節）。

跟 doc56 舊敘述("`0x22A85/0x22BC6→0x22AA8→0x22AF6`，clear `+0x25/+0x26` 並借 record10 restore")
完全吻合，本輪新增：wrapper 共用機器碼的精確跳轉關係、class-adjusted level 的確切位元運算、以及
`×4` EXP 累加(此為全新發現，doc56 未記載)。

### 3. commands 22/26/27：施加路徑(反組譯確認，三個 command 共用同一核心)

強制反組譯 `0x22be1`(cmd22)/`0x22cbf`(cmd26)/`0x22e41`(cmd27)/`0x22cda`/`0x22d1b`：

- `0x22be1`：`PUSH 0x27`(flag offset，**確認封咒綁定 `+0x27`**)→ `PUSH 0x16`(=22)→
  `CALL 0x22cda`。
- `0x22cbf`：`PUSH 0x25`(flag offset，**確認毒擊綁定 `+0x25`，與解毒配對**)→ `PUSH 0x1a`(=26)→
  **`JMP 0x22bf7`**(尾跳進 cmd22 wrapper 呼叫 `0x22cda` 前的同一段)。
- `0x22e41`：`PUSH 0x26`(flag offset，**確認麻庫/麻痺綁定 `+0x26`，與社麻/解痲配對**)→
  `PUSH 0x1b`(=27)→ 同樣 `JMP 0x22bf7`。三個 command 共用一份機器碼，只差 flag offset 與 command ID
  兩個常數，跟 20/21 的 wrapper 共用模式完全一致。
- `0x22cda`：`0x1CA89(actor,id)` MP debit → 轉發 5 參數給 `0x22d1b`。
- `0x22d1b`：動畫 `0x1C4CC`/`0x1C2DA` → 逐 target：讀 `record[+offsetParam]`，**非 0(已有效果)直接
  跳失敗**；讀 class，**class==0x19 或 0x1a 直接跳失敗**(此 exclusion 原僅記載於 doc56 的 ID22 描述，
  本輪確認它其實是**三個 command 共用**的同一段程式碼，22/26/27 皆適用，非 ID22 專屬)；
  `rand()%100`(`CALL 0x4EBE3`)`>=50` 跳失敗；否則固定金額 `0xa`(10)呼
  `0x1C81F(target,10)`(內部 90–99.9% RNG，doc56 已知的「base10 實際9 HP」由這裡的共用 writer 產生，
  非本函式自己再骰一次)、`0x1E0DB(...,0x5e,target)` 顯示 damage；`rand()%4+2`(第二個 `0x4EBE3`)
  寫入 flag byte 當 duration；`class-adjusted level(+0x21) << 3`(×8)累加進 `[0x53EC8]`。

跟 doc56 的「`0x22BE1→0x22CDA→0x22D1B`」「gate RNG→damage RNG→duration RNG 三 draws」（此處
指 `rand()%100` gate + `rand()%4+2` duration 兩次自身骰，加上 `0x1C81F` 內部第三次骰）完全吻合。
本輪新增：wrapper 共用機器碼細節、class exclusion 泛化到三個 command（非 ID22 專屬）、以及 `×8`
EXP 累加。

### 4. command 25：行動點清除(獨立 handler，非共用 wrapper 家族)

`0x22C04` 是獨立函式(不像 20/21/22/26/27 用共用 wrapper 尾跳模式)：`0x1CA89(actor, 0x19)`
(=25) MP debit → 逐 target `TEST record[+5], 0x80`，未設就失敗顯示；已設就 `AND record[+5], 0x7f`
清除該 bit(**這正是「acted」旗標**，`SetNativeRecordBit7`/`ClearNativeRecordBit7All` 的同一個
bit)→ 同樣 `class-adjusted level(+0x21) << 3`(×8)累加進 `[0x53EC8]`——跟第 3 節的 22/26/27 用
完全相同的 ×8 常數，且與 command25 自己的遊戲內名稱「**行動術**」吻合(見第 7 節與 doc02 §4.5
交叉印證)。跟 doc56「`0x22C04` 以 record25 MP debit，僅在 target `+5 bit0x80` 已設時清 raw bit」
完全吻合；`ExecuteNativeCommand25` 的既有 raw core（`remake/internal/battle/native_command25.go`）
與此逐位元組一致。

### 5. command 23：傳送術特殊搬移(反組譯確認，含 EXP 印證)

`0x2218A`：`0x12D7B` 數值 popup → `0x1CA89(actor, 0x17)`(=23)MP debit → class-adjusted
level `IMUL ×0xa`(=10)累加進 `[0x53EC8]`(見第 7 節，精確吻合 doc02「傳送術=10×」)→ 讀 selected
unit 原座標 `+0/+1` → 呼叫 `0x22253` 兩次：

1. 第一次傳入 `0xff/0xff` 取代原座標(離場演出，原座標仍保留給呼叫端)；
2. 中間清 `[0x51A83]=0`(忙碌/鎖定旗標)，接著讀 selector cursor globals `[0x51CF9]/[0x51CFD]`；
3. 第二次以這對 cursor globals 呼叫 `0x22253`(入場演出)，結束後 `[0x51A83]=1`。

跟 doc56「`0x2218A` 以 record23 扣 MP，並呼叫 `0x22253` 兩次…第一次將 selected unit 的 runtime
`+0/+1` 寫為 `0xff/0xff`…第二次直接寫為 selector cursor globals」完全吻合，逐指令釘死。`0x22253`
本身確認是真正的 framebuffer blit routine(`+0x8088` 位址運算、`0x11EEE` blit 呼叫、`0x22470`
子程式)，複雜度真實存在，非文件過度謹慎——renderer 未接是誠實描述，不是保守化的免責聲明。

### 6. commands 24/28/29/31：derived-strike 位址修正(與同日另一輪 doc27 §6.3 獨立收斂)

doc56/worklist 引用的「`0x276EC`」在**目前這個 Ghidra 專案裡經強制反組譯證實不是有效的指令邊界**：
`getFunctionContaining(0x276ec)` 回傳 `FUN_000275e6`，逐指令走訪該函式後發現它是一個**跟 derived
strike 完全無關**的通用選單方向鍵游標 handler(掃鍵碼 `0x48/0x4a/0x4b/0x4d/0x50` 上下左右、Enter
`0x1c`/`0x39`、ESC `0x1`，操作游標邊界變數 `[0x53c57]`／`[0x53f4e]`)；`0x276ec` 精確落在其中一條
`CMP EAX,dword ptr [0x53c57]` 指令的 4-byte 立即數中段，不是指令起點。

**寫下這段之後才發現** `docs/knowledge-base/27-combat-rules-and-validation-checklist.md` §6.3
（同一天、幾乎同一時段的另一輪工作，檔案 mtime 比本節動筆時間更新)已經用完全獨立的方法（不是
`getReferencesTo(0x1c81f)`，而是先重新反組譯 `0x1cff0→0x2ff01` 大型 dispatcher，發現 `0x2a6bd`
本身也不是有效指令邊界，再從 `0x2ff01` 內部 `commandId==0x18 || commandId>0x1b` 分支直接讀出跳轉
目標)得出**完全相同的結論**：真正的 derived-strike 宿主函式是 `0x2CF30`。兩條獨立路徑（本節的
xref-to-`0x1c81f`反查、doc27 §6.3 的 dispatcher 逐層反組譯）收斂到同一個位址，是很強的交叉印證，
不是巧合。本節保留 xref 方法的完整記錄（`getReferencesTo(0x1c81f)` 只有三個呼叫端：`0x1C75E`
(IDs0-12 共用 writer)、`0x22D1B`(第 3 節的 22/26/27 application core)、以及 `0x2CF30`），但
`0x2a6bd`/`0x2ff01`/`0x1cff0` 分支結構的完整版本請見 doc27 §6.2/§6.3，本節不重複展開，以避免兩份
文件各自維護一套可能漂移的敘述。這也再次印證專案既有教訓([[fd2-old-new-exe-address-instability]])：
**舊文件位址不可盲目信任，須用 xref/反組譯覆核**。

逐指令反組譯 `0x2CF30`(範圍至少到 `0x2D695`，是個含大量 `0x111BA`/`0x11EB0`/`0x37910` 資源載入與
blit 呼叫的大型多段演出函式，doc27 §6.2 進一步確認它是 `0x2ff01` 內 `commandId==0x18||commandId>0x1b`
分支的直接跳轉目標)確認：

- 倍率 dispatch(`0x2CFF9`-`0x2D049`)：`command==0x18`(24)→ mult=`0xf`(15)；
  `command==0x1c`(28)→ mult=`0x14`(20)；`command==0x1d`(29)→ mult=`0xc`(12)；否則(31)→
  mult=`0x12`(18)。**與 doc56 舊敘述的四個倍率數值(15/20/12/18)完全一致，只有位址引用需要修正**，
  數值結論不變。
- `0x2D062`-`0x2D07A`：`trunc(actor derived +0x48 × mult / 10)`，跟 doc56 公式一致。
- `0x2D42E`-`0x2D47E`：讀 target `+0x40`(current HP)/`+0x4a`(derived defense-like stat)，
  `delta = multResult - target+0x4a`，呼叫 `0x1C81F(targetHP, delta)`。
- `0x2D488`-`0x2D49F`：結果 `clamp` 到**原始已存的 HP 上限**(不得超過)——這正是 doc56 敘述的
  「原版為了多段演出會先暫存 total delta、把 HP 復原，再以等份遞減回最終值」機制的具體指令位址，
  先前只有敘述沒有位址佐證。

`ExecuteNativeCommand24`/`ExecuteNativeCommandDerivedStrike`(`remake/internal/battle`)目前引用的
是抽象的 state-only final delta，不依賴 `0x276EC` 這個位址本身，因此**這個位址修正不影響既有
remake 程式碼的正確性**，只影響文件引用；下一輪如果要對照原生位址驗證，應改查 `0x2CF30`
而非 `0x276EC`。

### 7. `[0x53EC8]` 經驗值累加器：與 doc27 §5.1 獨立交叉印證+一項增量發現

反組譯 command 20..27 途中，在 20/21/22/23/25/26/27 的 handler 尾端都看到同一種
「`class-adjusted level << N` 累加進 `[0x53EC8]`」寫法。寫完初稿後才發現
`docs/knowledge-base/27-combat-rules-and-validation-checklist.md` §5.1（同一天、更早收尾的
另一輪工作)已經用完全獨立的方法（對 `[0x53EC8]` 做完整 xref 掃描 + decompile，而非本節這樣
逐 command wrapper 往下追)把「傳送術/行動術/魔刃魔鎧風行/麻痺毒擊/解毒祛麻的經驗值公式」這個
open item 標記為完整閉合，列出 6 個寫入點：`0x22721`(魔刃×2)/`0x22866`(魔鎧×2)/`0x22997`
(風行×2)/`0x22af6`(清除×4)/`0x22d1b`(施加×8)/`0x2218a`(傳送×10)——跟本節第 2/3/5 節與下表
的倍率**完全一致**（`0x22af6`/`0x22d1b` 是共用核心，本節額外指出它們涵蓋哪些 command ID；
doc27 §5.1 focus 在寫入點本身，不逐 command 展開）。兩輪各自獨立反組譯收斂到相同的六個位址與
倍率，是有力的交叉印證。

**本節增量發現(doc27 §5.1 未列出)**：command 25 除了透過共用 `0x22af6`/`0x22d1b` 核心之外，
**本身的獨立 handler `0x22C04` 也有自己的一份 `class-adjusted level << 3`(×8)累加**（見第 4
節），不經過 `0x22d1b` 這個共用 application core。doc27 §5.1 的六格清單只列了
`0x22af6`(清除族)與`0x22d1b`(施加族)兩個共用寫入點，沒有單獨列出 `0x22C04` 這個 ID25 專屬的
第三個寫入點——雖然數值同樣是 ×8(跟施加族相同常數)，但**位址不同、不經過共用 application
core**，是這張清單目前唯一遺漏的寫入點，值得在下一輪合併時補上。

對照 `docs/knowledge-base/02-game-data-reference.md` §4.5：

| command(s) | `[0x53EC8]` 倍率 | doc02 §4.5 對應列 | 結果 |
|---|---|---|---|
| 17/18/19(魔刃/魔鎧/風行) | ×2 | 「2 × Σ(受法者等級/施法者等級)」 | **精確吻合** |
| 23(傳送術) | ×10 | 「10 × (受法者等級/施法者等級)」 | **精確吻合** |
| 25(行動術，`0x22C04` 專屬+透過`0x22d1b`共用) | ×8 | 「8 × (受法者等級/施法者等級)」 | **精確吻合**，且遊戲內名稱本身就是「行動術」，三重印證(名稱+機制+EXP係數) |
| 22/26/27(封咒/毒擊/麻庫，共用`0x22d1b`) | ×8 | doc02 只列「麻痹術／毒擊術＝Σ(40×9/受法者總HP)×(等級比)」，**未列封咒術**這個類別 | **不吻合**：程式碼是簡單 ×8 常數，非含 HP 項的複雜公式；封咒(22)透過共用核心拿到跟毒擊/麻痺一樣的係數，但攻略表格沒有封咒這一列 |
| 20/21(解毒/社麻，共用`0x22af6`) | ×4 | 「解毒術／祛麻術＝Σ(40×9/受法者總HP)×(等級比)」(與麻痹/毒擊同一條公式文字) | **不吻合**：程式碼是簡單 ×4 常數，剛好是施加路徑(×8)的一半，「清除=半額、施加=全額」的乾淨設計，非攻略描述的 HP 加權公式 |

**麻痺毒擊/解毒祛麻的攻略文字落差是本節新增的觀察**，doc27 §5.1 把六個類別標記「完整閉合」是
指「寫入點全部找到」，但沒有逐格核對 doc02 §4.5 的公式文字是否真的對得上數值——本節核對後發現
其中兩類（麻痺毒擊、解毒祛麻）攻略文字的 `Σ(40×9/受法者總HP)` HP 加權項在程式碼裡找不到，只有
簡單常數倍率，呼應 doc27 §5 對攻擊/治療經驗公式已有的「攻略轉錄可能比實際公式複雜」判斷，但這次
是套用到「解毒祛麻/麻痺毒擊」這兩個先前(§5.1 寫作時)未及逐格核對的類別。不推翻 doc27 §5.1 的
「寫入點已閉合」結論，只是在其上補一層「數值 vs 攻略文字」的核對。

`remake` 對這整條 EXP pipeline（`grep 0x53ec8\|NativeExperience` 全 `remake/internal/battle`
無結果）完全沒有實作，doc27 已將其列為「非重製核心／低優先」，本節不改變那個優先順序判斷。

### 8. engine integration 對照 remake/internal/battle(逐 command)

`grep` 確認以下檔案與函式**已存在**且與本輪反組譯結果逐位元組一致(檔案路徑供覆核)：

- `remake/internal/battle/native_command20.go`：`ExecuteNativeCommandClearRestore`，涵蓋 ID20/21。
- `remake/internal/battle/native_command25.go`：`ExecuteNativeCommand25`。
- `remake/internal/battle/native_command26.go`：`ExecuteNativeCommandApplication`，涵蓋
  ID22/26/27(檔名雖叫 26 但涵蓋三個 command，與本輪確認的「三者共用同一核心」設計一致)。
- `remake/internal/battle/native_command17.go`：涵蓋 17/18/19 的 `ApplyNativeCommandModifier`。
- `remake/internal/battle/native_command_compound_exec.go`：ID32-35 的 `NativeCompoundCommandPlan`。

**沒有找到**的部分（`grep -r "0x53ec8\|NativeExperience\|NativeActionExp" remake/internal/battle`
零結果）：第 7 節的 EXP 累加器整條 pipeline，以及 ID23 relocation 的 legality/camera/render、
ID24/28/29/31 的 multi-hit 演出、所有 command 的 UI/status icon。這些跟 doc56 UI-03 matrix 既有的
「未接」標記一致，本輪未改變任何一個 UI/renderer 欄位的狀態——純粹是把 engine-side 的 raw dataflow
證據加厚，沒有新增可玩功能。

### 對 worklist 相關行的完成度(依第 0 節對映)

- **L510**(`0x1cff0` command table)：本輪未新增證據，維持 D(「完整 native 演出」子句仍未解)。
- **L532**(IDs13-16 治療)：本輪未觸碰，維持既有狀態不變。
- **L533**(ID24)：機制數值不變，但**位址引用修正**(`0x276EC`→`0x2CF30`)+**新增遊戲內名稱「破龍擊」**+
  新增 EXP 累加對照(不吻合 doc02，未列類別)；multi-hit/SFX/native UI 仍未接，D 不變。
- **L534**(28/29/31 UI matrix 列)：同 L533，位址修正+新增遊戲內名稱(淒煌斬/熾炎刀/音速刃)+31 名稱缺；
  UI 未接，D 不變。
- **L536**(＝17-19 項本身)：已在上一節完全收斂，本節第 7 節額外補上其 EXP 係數(×2，精確吻合 doc02)。
- **L538/L539**(20/21/26/27/22 命名)：狀態名稱早已由 `command_labels.json` 解出；本輪新增**逐指令反組譯
  佐證**(wrapper 共用機器碼、flag offset 常數、class exclusion 泛化)+**EXP 係數對照**(25=行動術精確吻合，
  22/26/27 不吻合攻略文字但已找到程式碼真值)。engine/UI 整合狀態不變，仍 D。
- **L540**(`0x1a30b` 全流程)：本輪未重新觸碰，狀態不變，維持 D。
- **L541**(ID23 relocation)：逐指令反組譯確認 wrapper/`0x22253` 呼叫序列與 doc56 完全吻合，新增
  EXP 係數(×10，精確吻合 doc02「傳送術」)；legality/camera/render/UI 仍未接，D 不變。
- **L548**(IDs25-27 jump table)：逐指令反組譯確認 jump table 本身+新增 25「行動術」名稱與 EXP 係數
  三重印證；UI/status labels 仍未接，D 不變。

所有十項的既有 D 判定（「可續靜態 RE，非必須 live DOSBox」）**維持不變**——本輪工作完全符合這個判定：
新增了大量位元組級反組譯佐證、與同日另一輪 doc27 工作獨立交叉印證了一個位址修正(`0x276EC`→
`0x2CF30`)與六個 EXP 寫入點、補上 doc27 §5.1 清單遺漏的一個寫入點(`0x22C04`)並指出兩個類別的
攻略文字落差，但沒有一項從 D 升級到可玩 UI/engine 完整整合（那需要 renderer/legality/status icon，
本輪明確不做）。

## 待辦(後輪)
- 反組譯選單繪製與選項表,確認確切選項與排列(2D 位置)。
- ✅ 按鍵綁定(Enter/Space 確認、ESC 取消、方向鍵)— 已反組譯。
- [~] `Get_EasyMagic`(0x18ED0) 的 UI caller 已定位；magic raw=`+0x1a..+0x1d`、`+0x22..+0x24` 僅保留 raw transient/modifier bytes，完整 bit 展開與高階欄位語意仍待重審。
- ✅ 各選項的 enable gate 條件(武器 / 道具 / 法術已知 / 攻擊範圍內有無目標)— 已反組譯,見下方
  「指令環 4 選項的動態 enable gate(2026-08-21)」。
- command bits → 可選 command／spell ID 的完整展開（法術編號見 `02`/`03`）。
- native commands 17..19 的 `ExecuteNativeCommand17_19`(target 解析 + MP debit + duration write)
  尚未接成可執行 command；`TickNativeTransientsRaw` 到期未串接 `ApplyNativeRuntimeEquipmentRecalc`
  重算；到期/扣血文字 popup(`0x15F84` idx `0x1E1+offset`／固定 idx487)在 remake 端完全未實作。

## native commands 20..27 EXP pipeline 接線 + 前提修正(2026-08-20)

> 任務起點誤判需要澄清:交辦描述認為 command 20-27「RE 完成但玩家完全碰不到」,但實際
> grep `cmd/fd2/main.go`(`nativeCommandTargetSupported`/`executeNativeCommandTarget`,約
> L4529-4539、L5353-5388)發現 **20/21/22/24/25/26/27/28/29/31 這十個 ID 早已接進戰鬥指令
> 選單**:選單本身用 `g.sel.NativeCommandIDs()`(單位自己的 raw command bitset)動態產生選項、
> `g.nativeCommandLabels`(`command_labels.json` 來源)提供文字標籤,Enter 確認後經
> `executeNativeCommandTarget` 分派到 `ExecuteNativeCommandClearRestore`(20/21)、
> `ExecuteNativeCommandApplication`(22/26/27)、`ExecuteNativeCommandDerivedStrike`(24/28/29/31)、
> `ExecuteNativeCommand25`(25)——這些函式本身也早已具備 MP debit(`SpendNativeCommandMP`)、
> 命中率(`rand()%100<50`)、傷害、duration 寫入(`SetNativeTransientDuration`)。也就是說,
> 「選單能選到 / MP 有扣 / duration 有寫」這幾項在本輪任務**開始前就已完成**,不是這輪新增的。
> 本輪重新核實後,把心力集中在文件與 grep 都證實**真正缺**的兩塊:EXP pipeline、command 23。

### 1. EXP pipeline:`[0x53EC8]` 累加器接線(新增)

`remake/internal/battle/native_command_exp.go`(新檔)新增共用 helper:

- `nativeCommandExpLevelFactor(target)`:`target.Lv`,若 `target.ClassID` 落在 `(8,0x19)`
  (9..24)則 `+0x1e(30)`——逐位元組對映 doc27 §5.1.A 的 `levelFactor` 定義。
- `(s *State) awardNativeCommandExp(actor, targets, multiplier, rng)`:對每個已成功的
  target 累加 `levelFactor*multiplier`,`clamp(0,99)`(對映 `0x117e7`/`0x1e292` 的單次行動
  clamp),再用**既有**的 `State.GainExp`(`growth.go`,legacy CastArea 法術路徑已在用的
  threshold-100/連續升級/`0x1b750`-equivalent 屬性成長管線)一次性餵入——不另開第二個
  持久化經驗欄位,`Unit.Exp` 是原生 `+0x3c` 持久化經驗 byte 的唯一 remake 對映,兩條來源
  (legacy CastArea 與 native raw 指令)本就該匯入同一個累加器。

接線位置與倍率(doc13 §7 / doc27 §5.1.A 六個既證實寫入點 + doc13 §7 本身新增的第七個):

| command | 檔案/函式 | 倍率 | 觸發條件 |
|---|---|---|---|
| 17/18/19 | `native_command17.go ExecuteNativeCommandModifier` | ×2 | 每個 `Applied` target |
| 20/21 | `native_command20.go ExecuteNativeCommandClearRestore` | ×4 | 每個 `Cleared` target |
| 22/26/27 | `native_command26.go ExecuteNativeCommandApplication` | ×8 | 每個 `Applied` target |
| 25 | `native_command25.go ExecuteNativeCommand25` | ×8 | 每個 `Cleared`(acted bit)target;獨立 `0x22C04` 寫入點,不經共用 application core |
| 23 | `native_command23.go ExecuteNativeCommand23`(新) | ×10 | 單一 target,非迴圈 |

`ExecuteNativeCommand25` 簽章新增 `rng *rand.Rand` 參數(原本沒有 RNG 需求;EXP 需要
`GainExp` 的成長擲骰);呼叫端(`cmd/fd2/main.go:5386`)與既有測試已同步更新為傳入
`g.rng`/`nil`。三個既有呼叫點全部確認過,無遺漏。

**24/28/29/31(derived-strike)是誠實標記的判斷,非逐位元組還原**:doc13 §6/§7 與 doc27
§5.1.A 的 `[0x53EC8]` 六寫入點清單都**沒有**列出 derived-strike 宿主 `0x2CF30`,即目前反組譯
證據不支援「這四個 command 直接寫 `[0x53EC8]`」這個結論(可能完全沒有,也可能經由另一條
尚未追出的路徑,如 §6 提到但未展開的攻擊經驗 `0x2f7b6`/`0x1ecc7`)。`native_command24.go
ExecuteNativeCommandDerivedStrike` 選擇改用已驗證的一般攻擊經驗公式(`growth.go AttackExp`,
doc02 §4.5「攻擊」列,`combat.go` 既有攻擊路徑同一條公式),理由是:這四個 command 本質上是
經 `0x1C81F` 傷害寫入 primitive 的一次攻擊,讓玩家可見傷害的技能完全不給經驗值不合理。
**這是本輪的工程判斷,不是 RE 結論**,未來若反組譯出 `0x2CF30` 或其呼叫鏈實際寫 `[0x53EC8]`
的證據,應以那個結果取代這裡的近似。

### 2. command 23(傳送術):新增 state-only executor,UI 仍未接(誠實範圍限縮)

`remake/internal/battle/native_command23.go`(新檔)新增 `ExecuteNativeCommand23(actor,
target, destX, destY, rng)`:record23 MP debit → 目的地合法性(**簡化版**:僅檢查邊界內 +
無其他存活單位佔用,不是逐位元組還原 `NativeRelocationDestinationAllowed` 的 raw-byte
movement-cost/table pipeline,因為那個函式吃的是 raw `[]byte` unit record + 地形 cost row,
不是 `*Unit`)→ `SetMapPlacement` 搬移 → `[0x53EC8]` ×10 EXP(見上表)。

**沒有做**、仍是真缺口:doc13 §5 描述的地圖游標目的地選取 UI(0xff/0xff 離場→cursor
globals 入場的那套 renderer/legality/camera)在 remake 完全不存在,`nativeCommandTargetSupported`
白名單(main.go L4534)刻意**不**加入 23——那個白名單的既有 unit-target 兩段式合流程
(`nativeCommandTargetUnitsFor`)是給「選一個單位」設計的,23 選的是「選一個地圖格」,兩者
合約不同,硬塞進同一個白名單只會讓 `nativeCommandTargetUnitsFor` 對著一個沒有候選單位清單的
命令回錯誤。因此 23 現在的狀態是:**有一個測試覆蓋、可從程式碼呼叫的 state primitive,
但玩家在戰鬥選單裡選到 23(如果他的 raw command bitset 剛好開了這個 bit)仍會落入
main.go L4400-4407 的既有 fallback(「目標／效果尚未驗證」訊息,不執行、不消耗回合)**,
因為 `nativeCommandTargetSupported(23)==false`。下一輪若要真正讓玩家用到,需要新增一個
目的地格選取的輸入模式(類似既有 `g.reach`/`g.walk` 但沒有「已行動格排除」限制),不是本輪
範圍(任務說明本身也把 23 列為次要)。

### 3. 測試

新增/擴充 regression test(`go test ./...` 全綠,含既有 test 未受影響的驗證):

- `native_command_exp_test.go`(新):`nativeCommandExpLevelFactor` 邊界(class 8/9/0x18/0x19)、
  `awardNativeCommandExp` 的 clamp99、Enemy actor no-op 不耗用 RNG、空 target 清單 no-op。
- `native_command17_test.go`/`native_command20_test.go`/`native_command26_test.go`/
  `native_command25_test.go`/`native_command24_test.go` 各新增至少一組「Own-camp actor 成功
  路徑要拿到經驗值、no-op/gated-out 路徑不拿經驗值」的測試。
- `native_command23_test.go`(新):搬移+MP debit+EXP 成功路徑、目的地被佔用/越界/book 缺失
  三種 fail-closed 路徑。

**測試踩坑記錄(供下一輪參考)**:`NativeCommandTargetMatches(targetCode, selector, unit.Camp)`
用**候選單位自己的 Camp**、不是施法者 Camp,判斷是否符合 `TargetCode`(0=`Enemy`、
1=`!=Enemy`、2=`Ally`、3=`Own`)——把既有測試的 actor/target 陣營同時换成 Own 來滿足
「Own 才有經驗值」的 `GainExp` 前提時,若沒同步檢查對應 `TargetCode` 期望的候選陣營,
目標解析會直接回傳空清單(不是報錯,是「這個 command 對這個陣營組合沒有合法目標」),
容易誤判成程式邏輯錯誤。

## 指令環 4 選項的動態 enable gate(2026-08-21,呼應 doc58「續三十六」)

**任務背景**:doc58「續三十六」live 操作在 ch27 把鐵諾移動到 3 隻敵人旁邊、指令環正確跳出,
但窮舉上/左/右/下 4 個方向全部只導向「法術列表卡」或「裝備資訊卡」,沒有一個方向明確對應
「攻擊」,最終沒能出手。本節純靜態 Ghidra headless 反組譯(`analyzeHeadless -readOnly
-noanalysis`,`ProbeBatch.java`/`tools/ghidra_batch_probe.py`,見 doc98)指令環的完整
dispatch 邏輯,回答任務要問的核心問題:**指令環的 4 個選項不是固定的,是每次開啟時依角色
裝備/存量動態決定 enable/disable**,並且找到「攻擊選項會消失」的具體觸發條件。

### 0. 呼叫鏈總覽(核對既有 memory `fd2-battle-input-dispatch-decompile`,逐位元組吻合)

```
0x117e7(頂層戰場游標鍵盤 handler,呼叫端 0x25dce 戰鬥主迴圈)
  Enter/Space(0x39/0x1c) 選中單位後,三個 gate 全部成立才進「真正的指令環」:
    record[+6]      == 0x02   (單位可操作狀態)
    record[+5]&0x80  == 0     (Acted 旗標未設)
    record[+0x26]    == 0     (第三個 gate,語意未定名)
  三者任一不成立 → 改呼叫 FUN_00017aed(下方 §2,非互動式固定卡片演出,不是選單)
  三者成立      → do { FUN_00018890(); } while(...)        ← 進入指令環
      0x18890 → 移動確認(0x115b6)完成後 → do{ FUN_00018d8c(); }while(iVar3==0)  ← 指令環主迴圈
```

這與既有 memory `fd2-battle-input-dispatch-decompile`(2026-08-17,記錄到 `0x117e7`
的三個 gate)逐位元組吻合,本輪用完整 decompile(而非當時的部分反組譯)重新核實過一次,
沒有發現出入。

### 1. `0x18d8c`(指令環主迴圈):4 個選項的 enable 陣列現已完整反組譯

`0x18d8c(unit, enableFlags[4], mode)` 在進入按鍵迴圈(`0x177fc`)之前,依序對 `enableFlags`
四個 slot 做以下判定(`param_2`=`enableFlags`,`param_2[0..3]` 依序對應 上/左/右/下即
攻擊/法術/道具/待機):

| slot | 方向 | 選項 | disable 條件(`enableFlags[i]=1` 時該方向被跳過) |
|---|---|---|---|
| `[0]` | ↑ | 攻擊 | `FUN_0001b83d(unit,0)==-1`(**無武器類 slot**,見下)**或** `FUN_00014818(actorX,actorY,0,weaponRange,weaponClass,0)==0`(**該武器射程內找不到任何敵方 camp 候選**) |
| `[1]` | ← | 法術 | `FUN_0001c269(unit,0)==0`(**已知法術 bitfield`+0x1a..+0x1e`全空**)**或** `unit+0x27 != 0`(第二 gate,語意未定名,推測是封印/沉默一類狀態) |
| `[2]` | → | 道具 | `FUN_0001b8a6(unit)==0`(**8 格道具欄全空**,bit7 clear 計數為 0——此位址已在 `verified_addresses.json` 收錄為 `RE-ITEM-AVAILABILITY-GATE-1B8A6`,本輪交叉核對一致) |
| `[3]` | ↓ | 待機 | **永遠不 disable**——待機這個選項在目前反組譯範圍內沒有找到任何 gate,永遠可選。 |

反組譯佐證(`FD2_ghidra_projects/results_cmdring_20260821.json`/`results_cmdring2_20260821.json`/
`results_cmdring3_20260821.json`,本輪產出,已附在 commit 內供覆核):

```c
// 0x18d8c 節錄(decompile,param_2 即 enableFlags[4])
iVar2 = FUN_0001b83d(unit, 0);
if (iVar2 == -1) { param_2[0] = 1; }              // 無武器 → 攻擊 disable,不再呼叫 0x14818
else {
    classByte = FUN_0001b722(unit, iVar2);         // 該武器 slot 的 class byte(slot+0xb)
    itemRow   = FUN_0004e8bc(classByte);            // = &DAT_000602ad + classByte*0x17
                                                      //   (即既有 verified_addresses.json
                                                      //    收錄的 0x602AD raw item-row 表,
                                                      //    stride 0x17=23 bytes)
    weaponClass = itemRow[0xb];  weaponRange = itemRow[0xc];
    if (FUN_00014818(actorX, actorY, /*outArray=*/0, weaponRange, weaponClass, /*camp=*/0) == 0)
        param_2[0] = 1;                             // 射程內無敵方候選 → 攻擊 disable
}
if (FUN_0001b8a6(unit) == 0)  param_2[2] = 1;       // 道具 disable
if (FUN_0001c269(unit,0) == 0) param_2[1] = 1;      // 法術 disable(無已知法術)
if (unit[+0x27] != 0)          param_2[1] = 1;      // 法術 disable(額外狀態 gate)
do { iVar1 = FUN_000177fc(unit, param_2); } while (iVar1 == 0);   // 按鍵迴圈
```

```c
// 0x177fc 節錄(按鍵迴圈本體)——disable 的方向鍵被「靜默吞掉」
scancode = FUN_00017898();
if (scancode == 1) return -1;                       // Esc 取消
if (scancode != 0x39 && scancode != 0x1c) {          // 不是 Enter/Space
    if (scancode==0x48 && enableFlags[0]==0) DAT_00053c57 = 0;   // ↑→case0 攻擊
    else if (scancode==0x50 && enableFlags[3]==0) DAT_00053c57 = 3; // ↓→case3 待機
    else if (scancode==0x4b && enableFlags[1]==0) DAT_00053c57 = 1; // ←→case1 法術
    else if (scancode==0x4d && enableFlags[2]==0) DAT_00053c57 = 2; // →→case2 道具
    return 0;                                        // 不論有沒有真的切換,一律回 0 繼續等鍵
}
return 1;                                            // Enter/Space:「確認目前 DAT_00053c57」
```

**關鍵行為**:`DAT_00053c57`(目前反白的選項)是一個**跨指令環實例存活的全域變數**,`0x18d8c`
本身**不會**在每次開指令環時重設它。當某方向被 disable,按對應方向鍵時 `DAT_00053c57`
完全不變(函式回 0,單純繼續等鍵),畫面上不會有任何切換動作。這代表:**如果攻擊被
disable,按「上」不會顯示任何提示或跳到別的畫面——它就是沒有反應**;真正決定 Enter
會執行哪個 case 的,是 `DAT_00053c57` 當下殘留的值(可能是**上一次**指令環實例、甚至
上一個單位的指令環留下的選擇)。

### 2. 指令環的「非互動式替代畫面」`0x17aed`——續三十六很可能撞到的是這個,不是真指令環

`0x117e7` 三個 gate(`+6==2`/`+5&0x80==0`/`+0x26==0`)任一不成立時,Enter 呼叫的是
`FUN_00017aed`(`0x17aed..0x17d6e`,642 bytes),完整反組譯後發現**這個函式完全不讀取任何
按鍵**——它是一段固定播放順序的演出:

```c
FUN_00017e0b(); FUN_00016c57();
if (FUN_0001c269(unit,0) != 0) {          // 該單位「有已知法術」時才播這一段
    for (i=0;i<7;i++) { 畫格...絕不讀鍵 }  // 開場 7 幀(法術列表卡樣式演出)
    ...; for (i=6;i>=0;i--) { 畫格... }    // 收場 7 幀
}
for (i=0;i<12;i++) { FUN_00018409(); }    // 永遠執行:12 幀開/關,doc13 §item panel
                                            // 已記載的同一個 present compositor(0x17e0b/
                                            // 0x1b932/0x18409 opening-closing schedule),
                                            // 即「裝備/道具資訊卡」的呈現函式
```

也就是說,`0x17aed` 是「(有法術才加演)法術列表卡 → (一定會播)裝備/道具資訊卡」這個固定
順序,**不含任何選單邏輯,不可能走到攻擊**。它的三個已知呼叫端是 `0x11926`/`0x11a17`
(均在 `0x117e7` 內部,對應上面兩個 gate 分支)與 `0x29656`(尚未追,留待後續)。

**這給續三十六的兩個候選解釋都補上了反組譯依據,兩者都可能同時發生在那輪操作裡**:

- **(A) 若確實在真指令環內(`0x18d8c`/`0x177fc`)**:攻擊被 §1 的 gate disable(缺武器,或
  `0x14818` 判定射程內敵方候選數=0),按上沒有任何反應;由於 `DAT_00053c57` 不會重置,
  Enter 直接確認殘留值(可能是先前操作留下的 1=法術或 2=道具),於是每次 Enter 都落在
  法術/道具卡,跟按了哪個方向鍵無關——這完全解釋「上→法術卡、左/右/下→均為裝備資訊卡」
  這種「看起來方向有差、其實只是殘留狀態被反覆確認」的現象,也解釋「confirm 後又跳回
  瀏覽游標」(法術/道具流程自己的候選目標判定同樣可能因射程/存量不足而自我取消)。
- **(B) 若當時三個入口 gate(`+6`/`+5&0x80`/`+0x26`)其中一個沒過**(例如反覆 Escape/
  重試移動的過程中,單位不小心被標成 Acted,或殘留了某個中繼狀態旗標),則玩家壓根不在
  `0x18890`/`0x18d8c` 裡——`0x17aed` 這個純演出函式本來就不讀方向鍵,「窮舉 4 個方向」
  這個操作本身在這個分支下無意義,難怪怎麼按都繞不出法術卡/裝備卡這兩張畫面。

兩者用純畫面觀察很難分辨(`0x17aed` 的法術卡演出跟真指令環選到法術後的 `0x1cff0` 演出,
以及 `0x17aed` 一定會播的裝備卡跟真指令環選到道具後 `0x1bbdc`/`0x184c0` 的道具格畫面,
外觀有相當重疊),但有一個可用的行為區分點:**真指令環裡,一個明確「可選」的方向鍵按下去
畫面上的反白/游標圖示應該會立刻切換;`0x17aed` 從頭到尾不理會任何按鍵,不會有這種切換感**,
下一輪 live 操作可以拿這個當診斷依據(見下方 checklist)。

### 3. 「法術列表卡」與「裝備/道具資訊卡」分別對應哪個位址

| 續三十六描述的畫面 | 可能來源 A(真指令環內) | 可能來源 B(`0x17aed` 替代演出) |
|---|---|---|
| 法術列表卡 | `0x1cff0`(case1,選中「法術」後的 320×200 command/演出 loop,doc13 已有的 `0x1cff0` 段落) | `0x17aed` 內以 `0x1c269(unit,0)!=0` 為條件的 7(+7)幀開場/收場演出 |
| 裝備資訊卡(巨神戟 AP320／龍神鎧甲 DP300) | `0x1bbdc`/`0x184c0`(case2,「道具」選項的兩欄×四列格,doc13 §item 已記載「右側 stat icon/value 依同 byte 與 type5/11 分流」——**裝備武器/防具本來就以帶 AP/DP 數值的道具列呈現**,跟續三十六描述的畫面完全吻合) | `0x17aed` 尾端**必定執行**的 `0x18409`×12 幀 present(doc13 §item panel 的同一個 compositor) |

兩欄都指向同一組底層渲染函式(`0x18409`/`0x184c0`/`0x1cff0`),這是意料中的——`0x17aed`
本來就是拿指令環「法術」「道具」兩個選項各自的呈現邏輯直接重播一遍,只是拿掉了選單互動,
所以外觀真的會跟「選到法術/選到道具」高度相似,這是造成續三十六誤判「指令環正確跳出」
的合理原因。

### 4. 給下一輪 live 驗證的具體 checklist

1. **移動前(或至少開指令環前)先確認角色武器已裝備**:`0x1b83d` 要求 8 格道具欄裡至少一格
   `flags(slot+10) & 0x40 != 0`(武器類旗標),沒有武器 → 攻擊選項在 `0x18d8c` 一開始就
   被 disable,`0x14818` 的射程/candidate 判定根本不會被呼叫。若手上角色是用「近戰職業
   預設空手」測試,這步會直接卡死,建議先用 debugger 或既有存檔確認該單位有武器道具。
2. **確認目標在武器射程內,且用的是「地形感知」的距離判定,不是純目測相鄰**:`0x14818`
   對 melee 武器(射程 raw byte `<0x10`)呼叫的是 doc13 §「`0x14818`」既有記載的
   `0x4e040`/`0x4e555` flood-fill,`grid flag 0x40` 是不可通過格、會擋住 flood-fill——
   **柵欄/牆本身如果被標成 0x40,即使視覺上緊貼著,也可能因為柵欄阻擋而候選數=0**,這正是
   續三十六自己提出的假說(a),現在有反組譯依據支持它是合理成因之一。射程 raw byte
   `>=0x10` 的遠程武器則走「同 X 或同 Y、距離 `<=(range-0x10)`」的十字判定,不吃地形。
   下一輪如果懷疑攻擊被 disable,優先換一個「明確無地形阻隔、直線可達」的相鄰敵人測試,
   排除地形誤判這個變因。
3. **按方向鍵時盯著指令環圖示本身有沒有真的切換/反白**,不要只看最後 Enter 跳出的畫面
   內容——如果按上完全沒有任何視覺回應(游標/反白沒有動),就是攻擊被 disable 的直接徵兆
   (§1);如果每次 Enter 出來的畫面都一樣(不管按了哪個方向),高度懷疑是在確認
   `DAT_00053c57` 的殘留值,不是方向鍵真的把你導向那張卡。
4. **法術/道具選項一樣會被 gate 掉**:法術欄位全空(`+0x1a..+0x1e`=0)或 `+0x27!=0`
   時左鍵也會被吞;8 格道具全空時右鍵也會被吞。如果懷疑攻擊被 disable,可以先試「下」
   (待機,§1 顯示這個方向目前反組譯範圍內找不到任何 disable 條件,理論上永遠可選)當
   一個「指令環還活著、按鍵確實有在切換」的陽性對照——**但要注意選到待機再按 Enter 確認
   會真的消耗這個單位的回合**,只拿來測試「方向鍵有沒有反應」不要真的二次 Enter 確認。
5. **懷疑落入 `0x17aed` 替代演出時**(即真指令環的三個入口 gate 之一失敗:`record[+6]
   !=0x02`、`record[+5]&0x80!=0`(已行動)、`record[+0x26]!=0`),不要繼續在同一個單位上
   窮舉方向鍵組合——這個函式從頭到尾不讀鍵,怎麼按都不會有差異。改用 `0x117e7` 裡記載的
   「跳到下一個尚未行動單位」熱鍵(Esc/Z/Numpad5,掃描碼 `1`/`0x2c`/`0x4c`,精確邏輯是
   掃描 `record[+6]==0x02` 的單位並跳游標,見既有 memory `fd2-battle-input-dispatch-
   decompile`)換一個保證新鮮、未行動過的單位重新開始,而不是在同一個可能已經被標記
   Acted 的單位上繼續試錯。

**尚未解出、留給後續的缺口(誠實記錄)**:`record[+0x26]`(進真指令環的第三 gate)與
`unit+0x27`(法術選項的額外 disable 條件)兩個 raw byte 的具體語意本輪都沒有反組譯到
寫入端(只確認了讀取端的判斷邏輯),不能命名成「已行動」以外的具體狀態名稱;`0x1b83d`
的 `param_2`(武器 class threshold,呼叫時固定傳 0)在不同武器類型間是否曾經被傳非 0
也沒有追——本輪只確認了戰鬥指令環唯一會用到的呼叫路徑(固定傳 0)。

## `0x18d8c` 完整反組譯 + `DAT_00053c57` 全域 writer 普查(2026-08-22,純 Ghidra headless 靜態分析,呼應 doc58「續四十六」缺口)

**任務背景**:doc58「續四十六」live 驗證證實 `enableFlags[4]` 全部 enabled(推翻「攻擊被 gate
disable」假說),但發現 `DAT_00053c57`(目前反白選項)在 debugger 純 `RUN`(沒送任何按鍵)
之間會**自行**在 `00→02`、`02→00` 之間翻轉,且誠實記錄「真正的攻擊分派邏輯,在 `0x18d8c`
switch-case 本體這一段本輪完全沒有反組譯或 live 驗證過」。本節用 `ProbeBatch.java` +
`tools/ghidra_batch_probe.py`(`-readOnly -noanalysis`,project `FD2Analysis3`)對 `0x18d8c`
做完整 `decompile`/`disasm`/`function_bounds`,並對 `DAT_00053c57`(`0x53c57`)做全域
`xref_to` 掃描,把這段缺口補上——**同時發現一個修正既有 §1 記載的重要新事實**。

### 1. `0x18d8c` 本體現已完整 decompile(800 bytes,`0x18d8c..0x190ab`)

簽名確認:`undefined4 __stdcall FUN_00018d8c(int param_1, undefined4 *param_2, int param_3)`——
`param_1`=unit **index**(不是指標,函式內部自己算 `DAT_00053a45 + param_1*0x50`)、
`param_2`=`enableFlags[4]`、`param_3`=mode(用於 case 3,見下)。完整流程(節錄,呼應既有 §1
但補齊之前省略的兩段 `FUN_000173e7()` 呼叫,見下節訂正):

```c
*param_2 = 0;  DAT_00053ec8 = 0;
iVar2 = FUN_0001b83d(unit, 0);                       // 武器 slot 查詢
if (iVar2 == -1) { *param_2 = 1; }                    // 無武器 → 攻擊 disable
else {
    FUN_0001b722(); iVar2 = FUN_0004e8bc();            // weapon class → item row(0x602AD 表)
    weaponClass=itemRow[0xb]; weaponRange=itemRow[0xc];
    if (FUN_00014818(...) == 0) { *param_2 = 1; }      // 射程內無候選 → 攻擊 disable
    FUN_0004df4c();
}
FUN_000173e7(param_2);                                 // ★第一次呼叫(此時 param_2[1..3] 尚未算出)
FUN_0001741c();
if (FUN_0001b8a6(unit) == 0)  { param_2[2] = 1; }      // 道具 disable
if (FUN_0001c269(unit,0) == 0) { param_2[1] = 1; }     // 法術 disable(無已知法術)
if (unit[+0x27] != 0)          { param_2[1] = 1; }     // 法術 disable(額外狀態 gate)
FUN_000173e7(param_2);                                 // ★第二次呼叫(此時 4 個 gate 全部就緒)
do { iVar1 = FUN_000177fc(unit, param_2); } while (iVar1 == 0);   // 按鍵迴圈(既有 §1 已記載)
FUN_000176b4(); FUN_00011cac();
if (iVar1 == -1) { return 0xffffffff; }                // Esc:整個 0x18d8c 直接回 -1

if (DAT_00053c57 == 0) {                                // ===== case 0:攻擊 =====
    local_1c=DAT_00053ab1; local_20=DAT_00053ab5;
    FUN_0003706e(); FUN_00014818(); iVar2 = FUN_000115b6(); FUN_0004df4c(); FUN_0003776e();
    if (iVar2 == -1) { FUN_00012cea(); return 0; }      // 目標確認被取消 → 整個 0x18d8c 回 0(caller 重呼)
    FUN_00012c0d(); FUN_0001f04a();                      // 面向計算(不算傷害,見既有 08-19 訂正)
    FUN_0002e2b0();                                      // 真正的攻擊 orchestrator(命中/傷害/HP寫回)
    FUN_000134e4(); FUN_0001b6b7(); FUN_0001db65(); FUN_0001aa1d(); FUN_00013512(); FUN_0004e381();
}
else if (DAT_00053c57 == 1) {                           // ===== case 1:法術 =====
    do { iVar1 = FUN_0001cff0(); } while (iVar1 == 0);
    if (iVar1 == -1) { return 0; }
    FUN_00013512();
    /* MP 消耗:DAT_00053ec8 /= (unit+0x21,若 unit+0x20>8 再 +0x1e) */
}
else if (DAT_00053c57 == 2) {                           // ===== case 2:道具 =====
    do { iVar2 = FUN_0001bbdc(); } while (iVar2 == 0);
    if (iVar2 == -1) { return 0; }
    DAT_00053ec8 = 0;
}
else {                                                   // ===== default(涵蓋 3,也涵蓋任何非 0/1/2 的值,見下)=====
    if (param_3 == 0) { FUN_00013fd4(); }                // HP regen(内部另有 +0x25/+0x26==0 gate,既有 §1 記載)
    FUN_000190ac(); FUN_00013512();
}
return 1;
```

**與既有 §1「switch closure」表格(2026-07-25)/「switch 節錄」(2026-08-21)交叉核對**:四個
case 的 callee 序列完全吻合,新反組譯**沒有推翻**既有映射(↑=攻擊/←=法術/→=道具/↓=待機),
但補上了既有兩份筆記都沒記載的細節——完整的攻擊 case 後續呼叫鏈(`0x134e4`/`0x1b6b7`/
`0x1db65`/`0x1aa1d`/`0x13512`/`0x4e381`,`0x2e2b0` 之後)、法術 case 的 MP 扣除算式
(`DAT_00053ec8 /= unit+0x21`,職業轉職`unit+0x20>8`再 `+0x1e`)、以及**這是純 if/else-if
比較鏈(`CMP DAT_00053c57` 系列),不是 jump table**——回答任務項目 2。

**攻擊 case 目標值與額外條件(回答任務項目 4)**:`DAT_00053c57==0` 對應攻擊,跳轉序列
`0x14818`(候選)→`0x115b6`(確認,可被 Esc 取消,取消時 `0x18d8c` 整體回傳 `0`,回到
`0x18890` 的外層 `do{FUN_00018d8c();}while(iVar3==0)` 重呼,不是回傳錯誤)→`0x12c0d`→
`0x1f04a`(僅算面向,08-19 訂正已記載)→`0x2e2b0`(真正命中/傷害/HP 寫回 orchestrator)。
射程判定沿用同一個 `0x1b83d`(武器 slot)→`0x4e8bc`(item row)→`0x14818`(候選)鏈,與既有
§1 表格逐位元組一致,本輪重新反組譯沒有發現任何出入。

### 2. **訂正既有 §1「`DAT_00053c57` 不會在每次開指令環時重設」的說法**——`FUN_000173e7` 是專門的「跳過 disabled、選第一個 enabled 選項」初始化函式

`FUN_000173e7`(`0x173e7..0x1741b`,53 bytes)完整反組譯:

```c
void __stdcall FUN_000173e7(int enableFlags /* = param_2 */)
{
  for (DAT_00053c57 = 0;
       (DAT_00053c57 < 4 && *(int*)(enableFlags + DAT_00053c57*4) != 0);
       DAT_00053c57 = DAT_00053c57 + 1) {}
}
```

也就是說:**每次 `0x18d8c` 被呼叫,都會把 `DAT_00053c57` 從 0 開始線性掃描 `enableFlags[]`,
跳過每一個「disabled(flag!=0)」的 slot,停在第一個「enabled(flag==0)」的 slot 上**——這是
一個明確的「自動選第一個可選項」初始化邏輯,而 `0x18d8c` 在按鍵迴圈開始前**呼叫了它兩次**
(`xref_to 0x173e7`:呼叫端 `0x18e53`、`0x18ed6`,均落在 `0x18d8c` 函式範圍`0x18d8c..0x190ab`
內;第三個呼叫端 `0x1bc65` 在 `FUN_0001bffe`〔道具流程裡的「裝備」子選項〕內,見下節)。

**這直接推翻既有 §1「`0x18d8c` 本身不會在每次開指令環時重設它」的結論**——`0x18d8c` 確實會在
每次進入時強制重設 `DAT_00053c57`,不是保留殘留值。舊結論很可能是先前反組譯時手動簡化
pseudocode、漏看了這兩個沒有可見回傳值/引數的 `FUN_000173e7()` 呼叫所致(本輪用
`ProbeBatch.java` 直接吐出 Ghidra decompiler 原始輸出,沒有經過手動摘要,交叉比對舊
`results_cmdring_20260821.json` 系列後確認新舊兩次反組譯用的是同一顆 Ghidra project,不是
project 內容有變動)。

**尚待驗證的細節(誠實記錄,本輪未閉合)**:第一次 `FUN_000173e7()` 呼叫發生在 `param_2[0]`
(攻擊 gate)已算出、但 `param_2[1]`(法術)/`param_2[2]`(道具)**尚未算出**的時間點——此時
這兩個 slot 讀到的是呼叫端(`0x18890`)stack 上的殘留值,是否在呼叫前已被呼叫端清零,本輪
沒有走到 `0x18890` 的呼叫現場逐位元組確認,不能排除「第一次呼叫用還沒算好的 gate 資料把
`DAT_00053c57` 設到一個之後又被第二次呼叫覆蓋掉的暫態值」這個可能性——但由於兩次呼叫之間
沒有任何會被玩家觀察到的畫面更新(中間只夾了 `FUN_0001741c()` 和 3 個 gate 判定,不含任何
`0x18409`/present 呼叫),這個暫態值理論上不會被畫面呈現出來,**不太可能是續四十六觀察到的
`00→02→00` live 翻轉的成因**(見下節)。

### 3. `DAT_00053c57`(`0x53c57`)全域 writer 普查——這是一個橫跨整個戰鬥/選單子系統的共用暫存變數,不是指令環專屬

`xref_to 0x53c57` 掃出 **209 筆引用**,其中 **write / read_write 落在至少 20 個不同函式**,
橫跨 `0x15055` 到 `0x2a9ff` 這麼大的位址範圍(遠遠超出指令環 `0x18d8c`/`0x177fc`/`0x173e7`
自己的範圍)。逐一用 `function_bounds` 定位擁有者函式:

| writer 函式(entry) | 範圍 | 已知語意 | 備註 |
|---|---|---|---|
| `FUN_000173e7`(`0x173e7`) | 53B | 指令環「選第一個 enabled 選項」初始化(見上節) | `0x18d8c` 呼叫 2 次,`0x1bffe` 呼叫 1 次 |
| `FUN_000177fc`(`0x177fc`) | 156B | 指令環按鍵迴圈(既有 §1) | ↑↓←→ 直接寫入 0/3/1/2,四個寫入點在 `0x1783f`/`0x17858`/`0x17871`/`0x1788a` |
| `FUN_00016f55`(`0x16f55`) | 823B | **另一個獨立的頂層選單 dispatcher**,同樣「`do{FUN_000177fc();}while(...)` → 依 `DAT_00053c57==0/1/2/3` 分支」的結構,但呼叫的是 `0x19df7`/`0x19953`(內含 roster 迴圈,篩 `+5&0x85==0 && +6==2`,即「未行動、非死亡的我方單位」)/`0x1728c`——**不是戰鬥指令環**,推測是軍營/隊形類選單(見下方討論) | 唯一呼叫端 `0x118c1` |
| `FUN_0001728c`(`0x1728c`) | 347B | `0x16f55` 的 case2 分支 callee | |
| `FUN_00019953`(`0x19953`) | 1188B | 一個獨立的、有自己按鍵迴圈(`FUN_00010620` 輪詢 + `'K'`/`'M'` 熱鍵直接寫 `DAT_00053c57=0/1`)的畫面,17 個呼叫端(`0x17047`/`0x1720e`/`0x1917e`/`0x192d6`/...一路到 `0x2b404`),散布在道具/法術/裝備/甚至 `0x26xxx-0x2bxxx` 範圍 | 可能是通用的「確認/取消」對話框或 loading 過場,不是選單本體 |
| `FUN_0001b932`(`0x1b932`) | 172B | 既有 §「裝備/道具資訊卡」open/close schedule(`0x17e0b`/`0x18409` compositor 同一組) | 進入時無條件 `DAT_00053c57=0`,6 個呼叫端 |
| `FUN_0001b9de`(`0x1b9de`) | 430B | 道具兩欄×四列 selector(既有 §「`0x1bbdc`」段記載的 helper) | |
| `FUN_0001bffe`(`0x1bffe`) | 324B | 裝備 sub-case(既有 §1 case2 內部提過) | 呼叫 `0x173e7`(見上) |
| `FUN_0001cff0`(`0x1cff0`) | 1243B | 指令環 case1(法術)command loop | |
| `FUN_0001d51d`(`0x1d51d`) | 427B | 緊接在 `0x1d6c8`(既有文件記載的「四輪 palette flicker」)之前的函式,尚未反組譯過本體 | |
| `FUN_00015055`(`0x15055`) | 700B | 未追,位址在指令環/道具/法術範圍之外 | |
| `FUN_00025ebb`/`FUN_000279bc`/`FUN_00026e38`/`FUN_0002872b`/`FUN_00028cbd`/`FUN_00028f65`/`FUN_00029300`/`FUN_0002968d`/`FUN_0002986f`/`FUN_00029daa`/`FUN_0002a29d`/`FUN_0002a857` | 各數百 bytes | 全部落在 `0x25e00-0x2aa00` 這個密集區塊,與既有 §「`0x2a6bd` command effect jump table」/「`0x1c75e` 傷害 writer」/「`0x28a6c` 疑案(現已知在 `FUN_0002872b` 內部,見既有 08-19 訂正)」是**同一個大範圍**,推測是法術/技能演出與命中判定的內部狀態機共用同一個變數當 loop/frame index 或 target-slot 暫存 | 本輪只定位到函式邊界,未逐一 decompile 內部語意,誠實記錄為待查 |

**推論(回答任務項目 3——自發翻轉的可能解釋)**:`DAT_00053c57` 明顯**不是指令環專屬變數**,
而是整個戰鬥/選單子系統共用的「目前反白/選中 index」暫存全域,至少被 3 套完全不同的選單邏輯
(指令環 `0x18d8c`、另一個獨立頂層選單 `0x16f55`、法術/技能演出的 `0x25e00-0x2aa00` 叢集)
各自重複使用。續四十六觀察到的「純 `RUN`、不送按鍵,兩次翻轉 `00→02`、`02→00`」現象,**最可能
的成因不是指令環自己的邏輯自發翻轉,而是 debugger 的 `RUN` 讓 CPU 繼續執行到「下一次任何函式
寫入這個位址」為止**——如果此時遊戲執行緒還在跑某個殘留/正在收尾的演出(例如 `0x25e00-
0x2aa00` 叢集裡任何一個函式,或者殘留呼叫堆疊裡還沒退出的 `0x19953` 型態對話框),BPM 就會
命中那個**跟指令環完全無關**的寫入點,而不是玩家按鍵造成的切換。**這只是目前證據支持度最高的
假說,不是逐位元組證實的結論**——本輪是純靜態分析,沒有辦法在沒有 live EIP/call stack 的情況
下確認續四十六那兩次 BPM 命中具體是哪個函式寫的;哪個函式真正造成了那兩筆寫入,留給下一輪
live 驗證直接用 `BPM` 命中時的 `EIP`/call stack 回溯確認(見 doc58 補充的 checklist)。

### 4. 小結:`0x18d8c` dispatch 邏輯現在完整,`DAT_00053c57` 的「不會重設」舊結論已被推翻

- **Enter 確認後的分派邏輯**是 `0x18d8c` 函式體內部的 if/else-if 比較鏈(不是 jump table),
  四個分支的 callee 序列與既有 §1 表格完全吻合,新增了先前沒記載的完整攻擊/法術 case 尾段
  呼叫鏈。
- **方向鍵更新 `DAT_00053c57` 的方式**是直接寫入常數值(`0`/`1`/`2`/`3`),不是「目前值+位移量」
  運算,與既有 §1 記載一致,本輪用獨立 decompile 重新確認一次沒有出入。
- **`DAT_00053c57` 會在每次 `0x18d8c` 呼叫時被 `FUN_000173e7` 強制重設**成「掃描
  `enableFlags[]`、跳過 disabled、停在第一個 enabled 的 slot」——這點推翻既有 §1「不會重設」
  的舊結論,是本輪最重要的訂正。
- **`DAT_00053c57` 是至少 3 套獨立選單子系統共用的暫存全域**,這是「自發翻轉」現象目前證據
  支持度最高的解釋,但具體是哪個函式造成續四十六那兩次翻轉,仍待下一輪 live 驗證用 EIP/call
  stack 直接確認。

## `0x18890` 完整反組譯——找到獨立於 `0x117e7` 三個 gate 之外的第二層短路分支(2026-08-21,呼應 doc58「續四十」)

**任務背景**:doc58「續四十」用 live 斷點在 `0x11912` 證實 `0x117e7` 的三個已知 entry gate
(`record[+6]==2`/`+5&0x80==0`/`+0x26==0`)全部乾淨、理論上必定通過,但畫面依然表現出
「卡在角色資料卡、方向鍵零反應」的非互動特徵,把矛盾焦點轉移到「gate 通過之後、
`0x18890`(真指令環入口)內部」這個此前從未被完整反組譯過的區域(先前所有反組譯都停在
`0x117e7` 的 gate 檢查本身,`0x18890` 只在上面 §0/§1 被當作「移動確認 `0x115b6` 完成後
`do{FUN_00018d8c()}while(...)` 這個轉接點」引用過,函式本體從未逐行走過)。本節用
`ProbeBatch.java`/`tools/ghidra_batch_probe.py`(`function_bounds`/`decompile`/`disasm`/
`call_scan`/`xref_to`,見 doc98)補上這個空白,`FD2_ghidra_projects/results_r1..r4_20260821.json`
(本輪產出,已附在 commit 內供覆核)。

### 0. function bounds 與唯一呼叫端

`function_bounds 0x18890` → `0x18890..0x18b83`(756 bytes,含序言/收尾)。`xref_to`/
`call_scan` 均確認**唯一呼叫端是 `0x11943`**(位於 `FUN_000117e7` 內,即 `0x117e7` 的
`do { EAX = FUN_00018890(ESI); } while (EAX == 0);` 迴圈本身,`0x11942 PUSH ESI; 0x11943
CALL 0x18890; 0x1194b TEST EAX,EAX; 0x1194d JZ 0x11942`),與 doc13 §0/doc58 記錄的呼叫鏈
逐位元組吻合,沒有第二個呼叫端。

### 1. 完整 decompile(756 bytes 全函式,非片段)

```c
int __stdcall FUN_00018890(int param_1)          // param_1 = unit index
{
  FUN_0003702f();                                 // 輸入緩衝清理(doc98 已知的高頻共用開頭)
  // 複製 4 個 dword(16 bytes)從 &DAT_00053f12 到區域變數 local_3c..local_14
  DAT_00053c53 = 0;                                // 見 §3,這是本函式的「最終回傳結果」暫存,
                                                     // 不是 doc13 上方 §1 的 DAT_00053c57(反白選項)
  DAT_00051a8f = 0xff;
  iVar3 = DAT_00053a45 + param_1 * 0x50;           // unit record 基底(標準 0x50-byte record)
  local_24 = record[+0x3b];                        // 讀入但本函式內未再使用(可能給下游共用)
  FUN_0001f183();                                   // 回傳值被丟棄,見 §4(反常訊號)
  FUN_0004e8a5();                                   // &DAT_00061646 + unit*0x14(per-unit struct)
  local_20 = local_1c = FUN_0003706e();            // 配置一塊 scratch 緩衝區(疑似移動範圍格陣列)
  FUN_000145cd();                                   // 依 param 掃全體 unit,對符合條件者呼叫 0x14625
  FUN_0004e390();                                   // 建立移動範圍格陣列(寫 DAT_00060068/69=寬高)
  FUN_000146d1();                                   // 清除不符篩選條件單位的高亮 overlay byte
  local_14 = DAT_00053ab1; local_18 = DAT_00053ab5; // 記下目前游標座標(供之後「取消移動,復原座標」用)
  FUN_00018b84();                                   // 純 idle-animation ticker(不讀鍵,見 §2)
  local_2c = FUN_000115b6();                        // ★移動確認迴圈——會讀鍵,見 §2
  FUN_0004df4c();                                   // 已知高頻共用尾綴(doc98/doc58續三十九記錄)
  if (local_2c == -1) {                             // 移動確認階段按 Escape
    FUN_00012cea();
    FUN_0003776e();
    return 1;                                       // ★出口A:完全不進 0x18d8c
  }
  FUN_000145cd();
  iVar2 = FUN_0004e4f6();                           // ★路徑可達性驗證,見 §3——預設回傳 0xff
  local_28 = iVar2;
  FUN_0004df4c();
  DAT_00051a83 = 0; FUN_00012cea(); DAT_00051a83 = 1;
  if ((iVar2 == 0) || (iVar2 == 0xff)) {
    if (local_28 != 0) return 1;                    // ★出口B:iVar2==0xff → 完全不進 0x18d8c
    do { iVar3 = FUN_00018d8c(); } while (iVar3 == 0);   // iVar2==0 → 直接開真指令環(原地不動)
    if (iVar3 != -1) { FUN_00013a44(); FUN_0003776e(); return 1; }
    FUN_0003776e();
    if (DAT_00053c53 == 0) return 0;                 // Escape 出指令環、沒選任何動作 → 回0,外層再loop
  } else {
    FUN_00013488(); FUN_000134e4();                  // iVar2 是別的值 → 真的有位移,先播路徑動畫
    cVar1 = record[+7];
    if (cVar1 != 0x12 && cVar1 != 0x13 && cVar1 != 0x22) { local_38 = 1; }
    do { iVar3 = FUN_00018d8c(); } while (iVar3 == 0);   // 動畫播完後才開真指令環
    if (iVar3 != -1) { FUN_00013a44(); FUN_0003776e(); return iVar3; }
    FUN_0003776e();
    if (DAT_00053c53 == 0) {                          // Escape 出指令環 → 復原座標
      record[+0] = local_14; record[+1] = local_18;
      FUN_00012cea();
      return DAT_00053c53;                            // 即 return 0
    }
  }
  FUN_00013512();                                     // ★設定 record[+5] bit7=1(Acted 旗標寫入端!)
  FUN_00013a44();
  return DAT_00053c53;
}
```

(完整原始 decompile 文字保留於 `FD2_ghidra_projects/results_r1_20260821.json` 的
`decomp_18890` 項,上面是加了語意註解的整理版,控制流與變數對應逐一核對過,沒有精簡掉
任何分支。)

### 2. 核心問題:`0x18890` 有沒有讀鍵盤輸入?——**有,而且是兩層獨立的讀鍵迴圈**

- **第一層:`FUN_000115b6`(561 bytes,`0x115b6..0x117e6`——注意這個範圍精確銜接在
  `0x117e7` 正前方,不是巧合,是同一個原始碼檔案裡相鄰的函式)**,doc13 §0 稱為「移動確認」。
  完整 decompile 顯示它是一個**貨真價實的方向鍵/Enter/Escape 讀鍵迴圈**:呼叫
  `FUN_00012dac()`(見下)取得 scancode,`==1` 直接 `return 0xffffffff`(Escape),
  `0x48/0x50/0x4b/0x4d`(上下左右)分別呼叫 `FUN_00011b48`/`FUN_00011b9b`/`FUN_00011c59`/
  `FUN_00011bfa`(移動候選格游標)後 `CALL 0x25a96`(重繪)再回到迴圈頂端,
  `0x39`/`0x1c`(Enter/Space)在滿足特定條件(`param_1!=5` 且目標格 `record`
  不是 `-1` 空格,`param_1==4` 或 `FUN_00014742()!=0`)時 `return 1`(確認)。
  **只有 `-1`(Escape)或 `1`(確認)兩種回傳值**,decompile 沒有第三種正常回傳路徑。
- `FUN_00012dac`(140 bytes,`0x12dac..0x12e37`)是這一層實際的按鍵輪詢器:
  `while(true){ iVar1=FUN_00010620(); if(iVar1!=0) break; FUN_0004e31c(); if(幀計時器變化)
  FUN_00011cac(); }`——**忙等迴圈,持續呼叫 `FUN_00010620()` 直到有鍵可讀才跳出**,
  之後 `FUN_000370f0()` 真正取 scancode 並正規化幾個特殊值。這是合法的阻塞式讀鍵,
  跟 doc13 上方 §1 記載的 `FUN_00017898`(`0x18d8c`/`0x177fc` 用的讀鍵器)**結構幾乎一致**
  (同一組 `0x10620`/`0x4e31c`/`0x370f0` 家族函式),差別只在 `0x17898` 額外插入了
  6 個畫面重繪呼叫(`0x1297d`/`0x11eee`/`0x127a9`/`0x1acf3`/`0x179d5`/`0x11eb0`,對應
  指令環反白閃爍動畫),`0x12dac` 沒有這些、換成單一 `0x11cac`。
- **第二層:`FUN_00018d8c`(真指令環主迴圈)**——doc13 §1 已完整記載,經 `0x177fc`→
  `0x17898` 讀鍵,4 選項 enable/disable 邏輯與此次反組譯完全一致,不再重複。

**結論:`0x18890` 本身(透過它呼叫的 `0x115b6` 與 `0x18d8c`)在正常控制流下必定會讀鍵盤,
不存在「完全不讀鍵」的靜態盲區**——這點跟 `0x17aed`(完全不呼叫任何讀鍵函式,見下方 §3
既有段落)形成鮮明對比。**但**——這正是 §3 要說明的——`0x18890` 內部存在**兩個提早返回、
從未進入 `0x18d8c` 因而也從未進入其讀鍵迴圈的短路出口**,這才是解開矛盾的關鍵。

### 3. `0x18890` 與 `0x17aed` 的關係——`call_scan` 確認完全不相交,但找到了獨立的第二層短路

`call_scan 0x17aed` 這次連同 `0x18890` 一起重新掃過整個程式映像(不只之前查過的範圍),
**確認 `0x17aed` 的呼叫端只有 3 個:`0x11926`/`0x11a17`(均在 `0x117e7` 內部,對應三個
gate 失敗的兩個分支)與 `0x29656`(在另一個獨立函式 `FUN_00029620` 內,跟戰鬥指令環無關)。
`0x18890` 的 756 bytes 全函式範圍內,沒有任何一條指令呼叫 `0x17aed`**。兩者是完全平行、
互不相交的兩條路徑,由 `0x117e7` 自己的三個 gate 在 `CALL` 之前就已經分岔決定死,不會在
`0x18890` 內部又匯合回 `0x17aed`。

但 `0x18890` **確實有自己獨立的、`0x117e7` 三個 gate 之外的第二層判斷**——不是呼叫
`0x17aed`,而是**兩個會直接跳過整個 `0x18d8c` 真指令環、提早 `return` 的短路出口**
(見上面 §1 標星號 ★出口A/★出口B 的兩處):

- **出口A:`FUN_000115b6`(移動確認)回傳 `-1`**(玩家在移動確認迴圈裡按 Escape)→
  `0x18890` 直接 `return 1`,完全不呼叫 `FUN_00018d8c`。
- **出口B:`FUN_000115b6` 回傳 `1`(確認移動/原地不動)之後,`FUN_0004e4f6()` 回傳
  `0xff`**(見下)→ `0x18890` 同樣直接 `return 1`,完全不呼叫 `FUN_00018d8c`。

`FUN_0004e4f6`(214 bytes,`0x4e4f6..0x4e5cb`,`call_scan` 確認除了 `0x18890` 自己這個
呼叫端 `0x189f8` 外,還有另外 3 個呼叫端在 `0x14121`/`0x14b78`,均與這次追蹤範圍無關)
完整 decompile 顯示它做的事情是:把 10 個參數整批寫進 `DAT_0006006a`..`DAT_0006017a`
這組全域(跟 `FUN_0004e390` 寫入的**同一個** `DAT_00060064`/`68`/`69` 移動範圍格陣列
共用),然後**先把 `DAT_00060078 = 0xff` 當成硬編碼的預設/失敗值**,才呼叫
`FUN_0004e751` + `FUN_0004e5cc`(一對互相遞迴的 flood-fill 函式,`0x4e5cc` 遞迴呼叫自己
與 `FUN_0004e680`,邊界條件用 `DAT_00060068`/`DAT_00060069`(格陣列寬高)——典型的
「在移動範圍格陣列裡搜尋能不能走到目標格」BFS/DFS 寫法),**只有 `FUN_0004e751` 內部
真正命中目標座標(`DAT_00060071`/`DAT_00060072`)時才會用 `DAT_00060078 = DAT_00060077`
(目前遞迴深度/路徑長度)覆寫這個預設值**,最後回傳 `DAT_00060078`。

**也就是說:`FUN_0004e4f6()` 語意是「驗證剛才確認的目的格是否真的可達,可達則回傳路徑
長度,不可達回傳寫死的 `0xff`」——`0xff` 不是隨機髒值,是原始碼裡明確寫死的失敗 sentinel。**
`0x18890` 把這個 `0xff`(以及 `0`,同一個 if 分支涵蓋)當成「不需要開真指令環」的訊號,
直接短路返回——這是一個**完全獨立於 `0x117e7` 三個已知 gate、獨立於 `0x17aed`** 的
第二層判斷式,理論上足以單獨解釋「gate 通過、但畫面卡住不進真指令環、方向鍵零反應」
這個症狀,不需要假設 record 欄位被改壞,也不需要牽扯 `0x17aed`。

### 4. 給下一輪 live 驗證的具體建議

1. **直接驗證出口B是否真的被觸發**:在 `CALL 0x0004e4f6`(`0x189f8`,位於 `0x18890`
   內部)之後緊接的 `ADD ESP,...`/下一條指令設中斷點,單步到那裡時讀 `EAX`(=
   `FUN_0004e4f6` 的回傳值)——如果是 `0xff`,直接坐實出口B;同時 `MEMDUMPBIN` 讀
   `DAT_00060068`/`DAT_00060069`(格陣列寬高,linear 位址 `0x60068`/`0x60069`)與
   `DAT_00060064`(格陣列指標)當下的即時值,確認這個陣列在這場離線 patch+存檔跳章的
   戰鬥裡是不是被正確建立(寬高是不是合理的正整數、指標是不是指向有效記憶體),而不是
   殘留垃圾或 0。
2. **同時驗證出口A**:在 `FUN_000115b6` 的 `RET`(`0x117e6` 附近)或 `0x18890` 內
   `CALL 0x000115b6` 之後設中斷點,讀 `EAX` 確認 `local_2c` 到底是 `-1` 還是 `1`——
   續四十觀察到「RUN 後沒送任何鍵,畫面就直接跳出角色卡」,最可能的解釋是**中斷點暫停
   横跨了一次物理案件的按下/放開,導致 `FUN_00012dac()`(阻塞式讀鍵)在恢復執行後立刻
   讀到一個殘留/重複觸發的 Enter scancode(`0x39`/`0x1c`)**,而不是遊戲邏輯真的沒有
   讀鍵——這與 §2 證實的「`0x115b6`/`0x18d8c` 都是合法阻塞式讀鍵迴圈」完全一致。
   **建議下一輪對任何「斷點恢復後畫面在沒有新按鍵下自動推進」的觀察都先預設為
   debugger-pause 造成的殘留按鍵假訊號,除非能證明當時鍵盤確實完全沒有輸入**,這是
   一個新的方法論提醒,補充進 doc58 續四十既有的方法論小節。
3. **`FUN_0004e42c`(被 `FUN_0004e390` 呼叫、真正負責填格子的 flood-fill 本體)這輪
   完全沒有反組譯,是找出「為什麼可達性驗證會失敗」的最高優先候選**——如果它依賴某個
   只有正常戰鬥初始化流程(而非離線 patch + 存檔跳章合成)才會被設好的欄位(例如
   單位的「本回合剩餘移動力」或地形通行表指標),就會系統性地讓移動範圍格陣列建得不對,
   導致 `FUN_0004e4f6` 對任何目標格都判定不可達,回傳 `0xff`——這能解釋續三十六/三十七
   觀察到的「**所有**測試單位都卡進同一種非互動症狀」(不是單一單位的問題,是整個移動
   範圍計算系統性失效)。
4. **反常訊號待查**:`0x18890` 開頭呼叫 `FUN_0001f183()` 但**回傳值在 decompile 裡完全
   沒有被使用**(不是賦值給任何變數,也沒有出現在任何條件式裡)——`FUN_0001f183` 本身
   邏輯是 `record[+7]!=0x1c && (record[+0x20]==0x13 || record[+0x1f]∈{4,5}) → return 1
   else 0`,看起來像一個有意義的狀態檢查,但呼叫端沒用到結果,不合常理。下一輪應該用
   `disasm`(而非 decompile)重新核對這個 `CALL` 前後的組合語言,確認是不是
   decompile-arg-blindness(doc98 已知盲點)以外的另一種 decompiler 失真,或者這確實是
   死碼(例如除錯/未完成功能的殘留)。

### 5. 本輪呼叫的子函式,已解出 vs 待解出候選一覽

| 函式 | 語意(本輪確認/延續) | 狀態 |
|---|---|---|
| `0x3702f` | 輸入緩衝清理(高頻共用開頭) | 已知(doc98) |
| `0x1f183` | `record[+7]/[+0x20]/[+0x1f]` 狀態檢查,回傳 0/1 | **本輪新解出邏輯,但呼叫端未用回傳值,待查** |
| `0x4e8a5` | `&DAT_00061646 + unit*0x14` per-unit struct 存取器 | 本輪新解出 |
| `0x3706e` | 配置 scratch 緩衝區(續三十九曾見過 224000-byte 版本,這裡的大小未確認是否相同) | 部分已知,待確認 |
| `0x145cd` | 掃全體 unit,依 `param_1`/`record[+6]` 篩選後呼叫 `0x14625` | 本輪新解出外層,`0x14625` 本體未查 |
| `0x4e390` | 建立移動範圍格陣列(`DAT_00060068`/`69`=寬高),呼叫 `0x4e42c` | 本輪新解出外層,**`0x4e42c` 本體未查,最高優先候選** |
| `0x146d1` | 清除不符篩選條件單位的高亮 overlay byte | 本輪新解出 |
| `0x18b84` | 純 idle-animation ticker,呼叫 6 個重繪函式但**不讀鍵** | 本輪新解出,確認非讀鍵函式 |
| `0x115b6` | 移動確認讀鍵迴圈(見 §2),只回傳 -1/1 | 本輪完整反組譯 |
| `0x12dac` | 移動確認迴圈用的阻塞式讀鍵器 | 本輪完整反組譯 |
| `0x4df4c` | 高頻共用尾綴 | 已知(doc98/doc58續三十九) |
| `0x4e4f6` | 路徑可達性驗證,預設回傳 `0xff`(見 §3) | 本輪完整反組譯,**候選根因** |
| `0x4e751`/`0x4e5cc`/`0x4e680` | 遞迴 flood-fill,命中目標格才覆寫 `DAT_00060078` | `0x4e751`/`0x4e5cc` 本輪反組譯,`0x4e680` 未查 |
| `0x13488` | 依路徑碼陣列(0/1/2/其他)分派 `0x12eaa`/`0x1300d`/`0x13185`/`0x13315` 播放走位動畫 | 本輪新解出外層,4 個動畫函式本體未查 |
| `0x134e4` | 清 `record[+3]` 全體 + `thunk_0x3e01d`(移動完成通知) | 本輪新解出 |
| `0x13512` | 設定 `record[+5] bit7 = 1`(**Acted 旗標寫入端**) | 本輪新解出,重要——這是目前唯一確認的 Acted 旗標寫入端位址 |
| `0x13a44` | 依 `record`(`DAT_00053a55+0x33`/`+0x34`)條件式設定 `DAT_00051a8f` | 已知(doc13 §0) |
| `0x12cea`/`0x3776e` | 頻繁呼叫的收尾函式,語意仍是「畫面刷新/HUD 復位」的推測,未證實 | 未查,次要候選 |
| `0x18d8c` | 真指令環主迴圈(讀鍵、4 選項 enable/disable) | 已知(doc13 §1) |

## flood-fill 家族(`0x4e42c`/`0x4e4f6`/`0x4e751`/`0x4e5cc`)完整反組譯——推翻「地圖/地形 buffer 未初始化」假說,找到 record `+0x3b`(MV)才是真正候選根因(2026-08-21,呼應 doc58「續四十二」)

**任務背景**:上一節(續四十一)把 `FUN_0004e4f6()==0xff`(路徑可達性驗證失敗,`0x18890` 出口B)
釘為候選根因,但誠實標注「`FUN_0004e42c`(移動範圍格陣列 flood-fill 本體)這輪完全沒有反組譯」,並
提出一個具體假說:flood-fill 依賴的地形資料如果來自某個只有「正常戰鬥初始化流程」才會設好的
runtime buffer,而離線 patch+存檔跳章合成的戰鬥略過了這個初始化步驟,buffer 就會是垃圾值,
導致 flood-fill 系統性判定「不可達」。本節用 `ProbeBatch.java`/`tools/ghidra_batch_probe.py`
補完 `0x4e42c`/`0x4e4f6`/`0x4e751`/`0x4e5cc` 及其全部子函式,**用直接反組譯的 CALL 現場逐位元組
核對每一個傳入參數的真正來源,而不是停在 decompile 的模糊 pseudo-code**——結果**推翻**了上述假說,
但找到一個更具體、更可驗證的替代候選。查詢紀錄留存於 `FD2_ghidra_projects/results_r5..r18_20260821.json`
(本輪產出,18 批次)。

### 0. 四個函式的 function bounds

| 函式 | 範圍 | 大小 |
|---|---|---|
| `FUN_0004e42c` | `0x4e42c..0x4e4bd` | 146 bytes |
| `FUN_0004e4be`(`0x4e42c` 的葉節點測試/寫入函式,本輪新發現,舊文件未提過) | `0x4e4be..0x4e4f5` | 56 bytes |
| `FUN_0004e390`(`0x4e42c` 的唯一呼叫端「建立移動範圍陣列」外層) | `0x4e390..0x4e42b` | 156 bytes |
| `FUN_0004e4f6` | `0x4e4f6..0x4e5cb` | 214 bytes |
| `FUN_0004e751` | `0x4e751..0x4e794` | 68 bytes |
| `FUN_0004e5cc` | `0x4e5cc..0x4e67f` | 180 bytes |
| `FUN_0004e680`(`0x4e5cc` 的葉節點測試/寫入函式,本輪新發現) | `0x4e680..0x4e702` | 131 bytes |

`call_scan 0x4e42c` 確認唯一非遞迴呼叫端是 `0x4e424`(位於 `FUN_0004e390` 內);`call_scan 0x4e4f6`
確認除了 `0x18890` 自己(`0x189f8`)外,還有 `0x14121`(`FUN_00014121`,1 處)與 `0x14b78`
(`FUN_00014b78`,3 處)——這兩個是 doc13 §「指令環4選項的動態 enable gate」記載的**攻擊射程
候選判定**呼叫端,證實移動確認 flood-fill 與攻擊射程 flood-fill 是**同一套引擎**,只是不同呼叫端。

### 1. `FUN_0004e42c`/`FUN_0004e4be`:遞迴 flood-fill 引擎本體

`FUN_0004e42c` 是純暫存器 ABI 的遞迴函式(不是標準 stack-arg 呼叫)——`DX`=目前格 packed X/Y、
`CL`=剩餘移動預算、`EBX`=目前格在陣列裡的指標。反組譯逐指令核對(`0x4e42c..0x4e4bd`)顯示它對
上下左右 4 個方向各做一次:邊界檢查(`DL`/`DH` 與 `DAT_00060068`/`DAT_00060069` 寬高比較)→
呼叫 `FUN_0004e4be(候選格)` 做「能不能走」測試並寫入→若成功(`CF`=0)才 `CALL FUN_0004e42c`
遞迴展開。**它自己維護一個獨立於真實 x86 呼叫堆疊之外的「軟堆疊」,固定位址 `LEA EDI,[0x60079]`,
每層 7 bytes(word XY + byte CL + dword EBX)**,不是用真正的區域變數/堆疊框架——這解釋了為什麼
decompile 版本充滿 `unaff_EBX`/`unaff_EBP`/`unaff_EDI` 這些「未定義暫存器」警告(Ghidra decompiler
對這種手寫暫存器狀態機的已知盲點,非資料遺失)。

`FUN_0004e4be`(56 bytes,葉節點,本輪首次反組譯,先前所有文件都不知道有這個函式)是真正的
「這格能不能走」判定與寫入:

```
XOR EAX,EAX
MOV AX,[EBX-3]            ; 目前格的地形類別 word(相對於格指標 EBX 的 -3 offset)
AND AH,0x3                ; 取 4 種地形子類別之一(0..3)
SHL AX,0x2
ADD EAX,[0x60060]          ; + 每單位地形成本表指標(DAT_00060060)
INC EAX
MOV CH,[EAX]                ; CH = 這個地形類別對這個單位的「原始成本等級」
XOR EAX,EAX
MOV AL,CH
SUB CL,[ESI+EAX]            ; CL -= 全域「成本等級→實際點數」表(ESI=DAT_0006006a)查表值
JC fail                     ; 預算下溢(不夠走)→失敗
MOV CH,[EBX]                ; 目前這格已記錄的剩餘預算
CMP CL,CH
JLE fail                     ; 沒有比已知路徑更好→失敗(不覆寫)
MOV AL,[EBX-1]              ; 這格的地形 flag byte
TEST AL,0x40
JNZ fail                     ; bit 0x40 = 不可通過(與 doc13 舊文件記載的 `0x14818` 攻擊射程
                              ;   flood-fill 用的同一個 0x40 語意完全一致——證實是同一套系統)
TEST AL,0x80
JZ ok
XOR CL,CL                    ; bit 0x80 → 強制歸零(零成本鏈中斷,同 doc13 舊文件記載)
ok:  MOV [EBX],CL; CLC; RET  ; 寫入新的剩餘預算,回傳成功
fail: RET                    ; CF 保持 set,回傳失敗
```

每一格是 4-byte struct:`[+0..1]`=地形類別 word(相對這格「budget byte」的 `-3`)、`[+2]`=flag byte
(`-1`)、`[+3]`=剩餘預算 byte(`0`,flood-fill 執行期間反覆覆寫)。這與 doc13 舊文件記載的
`0x14818`/`grid flag 0x40 不可通過`/`0x80 強制歸零` 語意逐位元組吻合——**確認移動確認 flood-fill
與攻擊射程候選判定共用同一份地形資料格式與同一顆判定引擎**。

### 2. `FUN_0004e390`:「建立移動範圍陣列」外層——**逐一核對 6 個參數的真正來源**

`FUN_0004e390` 收 6 個 stack 參數(非 9,先前 decompile 因未用到的變數編號誤導成 `param_1..param_9`,
本輪改用 disasm 直接核對 `EBP+0x8..EBP+0x1c` 逐一對應)。用 `0x18890` 唯一呼叫端(`0x1894d`)的
真實 `PUSH` 序列(6 個 `PUSH`,程式順序 = 反向堆疊順序)逐一比對:

| Push 順序(程式碼中) | 值來源 | 對應 `EBP+offset`(callee) | 寫入哪個全域 |
|---|---|---|---|
| 6(最後 push,= `EBP+0x8`) | `EDI` = `FUN_0004e8a5(unit)` 回傳值 | `+0x8` | `DAT_0006006a`(每單位地形成本表指標,見上 `SUB CL,[ESI+EAX]` 的 `ESI`) |
| 5 | `DAT_00053ab1`(游標 X,`0x115b6` 確認迴圈直接讀寫的同一對全域) | `+0xc` | `DAT_0006006e`(起點 X,byte) |
| 4 | `DAT_00053ab5`(游標 Y) | `+0x10` | `DAT_0006006f`(起點 Y,byte) |
| 3 | `[ESP+0x18]`,經逐一回溯堆疊位移確認**就是 `0x188d9 MOVZX EAX,byte ptr [ESI+0x3b]` 讀出的 unit record `+0x3b`**(`ESI`=`DAT_00053a45+unit*0x50` 該單位 record 基底) | `+0x14` | `DAT_00060070`(初始移動預算 byte) |
| 2 | **`DAT_00053a51`**(絕對位址、無堆疊位移歧義) | `+0x18` | **`DAT_00060064`(格陣列指標!)** |
| 1(最先 push,= `EBP+0x1c`) | `DAT_00053a69`(絕對位址) | `+0x1c` | `DAT_00060060`(上面 `FUN_0004e4be` 用的「地形類別→原始成本等級」表指標) |

`FUN_0004e390` 讀 `*param(+0x18)`(= `*DAT_00053a51`)當寬度、`param(+0x18)[2]` 當高度,寫入
`DAT_00060068`/`DAT_00060069`——這正好對應 doc01 記載的 FDFIELD 構成資源格式(`u16 W, u16 H,
然後每格 u16 地形索引+u16 事件`):header 4 bytes 之後每格 4 bytes,與 flood-fill 引擎的
`(-3,-1,0)` 相對 offset 規則完全吻合。

**這是本節最關鍵的發現:`DAT_00060064`(flood-fill 讀寫的「格陣列」)不是 `0x18890` 自己
`FUN_0003706e()`(見下)配置的新鮮 scratch buffer,而是直接指向 `DAT_00053a51`——遊戲從
`FDFIELD.DAT` 載入、貫穿整場戰鬥、持續在用的**同一份地圖資料 buffer**。**

在 `0x189f8`(`0x18890` 呼叫 `FUN_0004e4f6` 的現場)重覆同一套比對,`FUN_0004e4f6` 的 10 個
`PUSH` 裡同樣有一個絕對位址 `PUSH dword ptr [0x00053a51]`,對應到它的「格陣列指標」參數——
**確認 `FUN_0004e4f6`(可達性驗證)與 `FUN_0004e390`(建立移動範圍陣列)用的是同一顆
`DAT_00053a51`,不是兩份獨立 buffer,更不是各自新配置的 scratch**。

### 3. 誰載入/填好 `DAT_00053a51`?——兩條初始化路徑都會做,**推翻本節任務原始假說**

`xref_to 0x53a51` 顯示只有極少數 WRITE(其餘 80 筆都是 READ,分布在指令環、AI、渲染等一大片
函式,證實這是全域共用的地圖資料 buffer)。反組譯這幾個 WRITE 所在的函式:

- **`FUN_00010010`(`0x10010..0x1061f`,1552 bytes)**:完整章節/戰鬥初始化流程(呼叫
  `FUN_000111ba()` 連續載入 6 個封存資源,含 `DAT_00053a51 = (short*)FUN_000111ba();
  DAT_00053ac1 = *DAT_00053a51; DAT_00053ac5 = DAT_00053a51[1];`,再建立 roster
  `DAT_00053a45 = FUN_0003706e()` 並逐一單位呼叫 `FUN_00011019()`)。
- **`FUN_0001088d`(`0x1088d..0x10b42`,694 bytes,即 doc23 記載的「僅重載地圖/roster,不跑
  完整開場」的**章節跳轉**函式,`存檔跳章`測試手法用的就是這條路徑)**:**逐字重複同一段
  `DAT_00053a51 = FUN_000111ba(); DAT_00053ac1/ac5 = ...` 載入邏輯**,同樣建立 roster。

**兩條路徑都會正確載入/填好 `DAT_00053a51`/`DAT_00053ac1`/`DAT_00053ac5`**——`存檔跳章`用的
`0x1088d` 輕量路徑並沒有跳過地圖資料載入這一步。另外 `xref_to 0x53a69`(`FUN_0004e390` 用的
「地形類別→原始成本等級」表)同樣在**兩條路徑**裡都由 `FUN_000111ba()` 填入。而
`FUN_0004e8a5()`(每單位地形成本表,`&DAT_00061646+unit*0x14`)`xref_to 0x61646` 只找到**一筆
DATA 參照,就是 `FUN_0004e8a5` 自己算位址那行,全程式沒有任何 WRITE**——這代表 `DAT_00061646`
是**編譯期就烘焙進 EXE `.object3` 資料段的常數表**,不是 runtime 填的 buffer,不可能因為任何
戰鬥初始化流程被跳過而「未設好」。

**誠實結論(推翻任務原始假說)**:本節任務背景提出的假說——「flood-fill 依賴的地形資料來自
某個只有正常戰鬥初始化才會設好的 runtime buffer,離線 patch+存檔跳章合成戰鬥略過這步導致
buffer 是垃圾值」——**用直接反組譯的證據被推翻**。無論走 `FUN_00010010`(完整初始化)還是
`FUN_0001088d`(存檔跳章用的輕量重載),flood-fill 依賴的三份資料(地圖 `DAT_00053a51`、
地形類別表 `DAT_00053a69`、每單位地形成本表 `DAT_00061646`)都會被正確設好。這也與已知事實
一致:攻擊射程候選判定(`0x14121`/`0x14b78`)用的是**同一套** flood-fill 引擎與**同一顆**
`DAT_00053a51`,而過去的 live 測試裡攻擊射程 gate(`0x14818` 的近戰射程 flood-fill)並沒有
表現出系統性故障的跡象——如果 `DAT_00053a51` 真的是垃圾值,攻擊射程判定應該也會一起壞掉。

### 4. 新候選:`record[+0x3b]`(MV,已由 doc13/32/56/58 定案的欄位)直接餵給 flood-fill 起始預算

上面 §2 表格「push 順序 3」直接鎖定:`FUN_0004e390` 的「初始移動預算」參數(`DAT_00060070`)
**來自 `0x18890` 一開始(`0x188d9`)讀取的 unit record `+0x3b`**——這個 offset 在 doc13(行 218)、
doc32(行 385/586)、doc56(行 2463-2464)、doc58(行 3754,`+0x3b | puVar7[7](MV) | ...+0x3b MV一致`)
**已經被多輪反組譯獨立定案為 MV(機動力)stat**,是跟 AP/DP/MaxHP/MaxMP 同等級的**持久角色屬性**
(職業轉換公式 `0x1e529` 會 `add` 到既有值,不是每回合重算)。`0x18890` 把這個 byte **原封不動**
當成 flood-fill 的起始 `CL`(剩餘預算)傳給 `FUN_0004e390`,`FUN_0004e4be` 第一步就會
`SUB CL,[點數表]`——**如果這個 unit record 的 `+0x3b` byte 是 `0`(或任何小於任一方向最低移動
點數的值),flood-fill 在第一步就會對所有 4 個方向 `JC fail`,任何位移量 `>0` 的目標都會被判定
不可達,回傳 `0xff`**——這與續三十六/三十七觀察到的「**所有**測試單位、涵蓋 0 格與多格移動,
全部一致落入同一種非互動症狀」完全吻合(0 格移動走 `iVar2==0` 分支,不受這個問題影響,能解釋
為什麼「原地不動」偶爾看起來還有反應,但任何實際移動都卡住)。

**這比任務原始假說更具體、更可 live 驗證,是本節最終候選根因**:不是共用地圖 buffer 沒初始化,
而是**這場離線 patch+存檔跳章合成戰鬥裡,受測單位 record `+0x3b`(MV)這個持久屬性欄位本身的值
可能是 0 或不合理**——無論是存檔跳章流程本身沒有正確保留這個 byte,還是離線 patch 敵人表工具
沒有一併處理玩家單位/敵人單位的這個欄位。

### 5. 給下一輪 live 驗證的具體建議(取代續四十一原本「檢查 `0x4e390`/`0x4e42c` 依賴的地形資料」)

1. **最高優先:在 `0x188d9`(`MOVZX EAX,byte ptr [ESI+0x3b]`,`0x18890` 一開始)或直接在
   `0x18890` 入口對 `ESI+0x3b` 設記憶體監看,dump 受測單位這個 byte 的即時值**——如果是 `0`
   (或明顯過小),直接坐實 §4 的候選根因,不需要再懷疑地圖 buffer。
2. **次要:同時 dump `DAT_00053a51`(應為非空指標)、`DAT_00053ac1`/`DAT_00053ac5`(應為合理的
   地圖寬高正整數)、`DAT_00053a69`(應為非空指標)——這是把 §3「兩條初始化路徑都會填好」的
   靜態結論做最後一次 live 交叉驗證,理論上這三者都該是乾淨值**,如果 live 驗證發現其中之一
   竟然是垃圾值,代表本節的靜態分析漏看了某個例外路徑,需要另開一輪追查。
3. **若 §4 坐實(`+0x3b`==0 或不合理)**,下一步是追查這個 byte 在存檔跳章/離線 patch 流程的
   哪個環節被錯誤處理——不需要再回到 Ghidra 反組譯(欄位語意已由既有 doc13/32/56/58 定案),
   而是應該去看**存檔跳章工具本身讀寫 unit record 的邏輯**(不在 `FD2.EXE` 反組譯範圍內)。
4. **若 §4 也被排除(`+0x3b` 是合理非零值)**,回到 `FUN_0004e4be` 的完整判定鏈——`ESI`
   (`DAT_0006006a`,即 `FUN_0004e8a5()` 回傳的每單位地形成本表指標)、`DAT_00060060`
   (`DAT_00053a69`,地形類別表)兩者的實際內容值都還沒有被 live dump 過,只確認了「指標本身
   不是垃圾」,不代表表格內容數值正確;可以在 `CALL 0x0004e4be` 前對這兩張表做一次記憶體
   dump 逐值核對是否合理。

## `0x115b6` 在「攻擊目標確認」呼叫現場的完整反組譯——找到 Enter 確認的真正 gate 是 `FUN_00014742`(敵方鄰近性再驗證),其距離門檻讀自一個 96-xref 的高度共用 global(2026-08-22,呼應 doc58「續四十七」缺口)

**任務背景**:doc58「續四十七」live 驗證證實開指令環立刻 Enter 會選到攻擊(`DAT_00053c57==0`),
但後續無論送多少次 Enter,`0x2e2b0`(攻擊 orchestrator)斷點從未命中、索爾的已行動旗標
(`+5 bit7`)全程維持 `00`——誠實記錄卡點收斂到「`0x18d8c` case 0 呼叫鏈裡 `0x14818`→`0x115b6`
(目標確認)這一段」,並指出 `0x115b6`「內部邏輯尚未完整反組譯」。**這個說法需要先澄清一個
容易混淆的既有事實**:`0x115b6` 本體(561 bytes,`0x115b6..0x117e6`)其實已經在本文件上一節
(「`0x18890` 完整反組譯」,2026-08-21)被完整反組譯過一次——但那一輪的呼叫現場是**移動確認**
(`0x18890` 內 `0x18981` 呼叫,`param_1=4`),不是這裡要查的**攻擊目標確認**(`0x18d8c` case 0
內 `0x18f76` 呼叫,`param_1=0`)。`0x115b6` 是同一份機器碼被至少 9 個不同呼叫端共用的通用
「候選游標＋確認」函式(`param_1` 是 mode selector),兩種呼叫現場的 `param_1` 不同,會走進函式
內部完全不同的分支——這正是這次任務要補的缺口:不是函式本體沒查過,是**這個特定呼叫現場
(`param_1=0`)沒有被逐位元組追過參數與分支**。本節用 `ProbeBatch.java`/`tools/ghidra_batch_probe.py`
(`disasm`/`decompile`/`call_scan`/`xref_to`/`bytes`,`-readOnly -noanalysis`)補齊,查詢紀錄留存於
`FD2_ghidra_projects` 對應 `results_*_20260822.json`(本輪 queries/results 亦存於
scratchpad,可依需要另行搬入 repo)。

### 0. `0x115b6` 的全部 9 個呼叫端與 `0x2e2b0` 的全部 4 個呼叫端(`call_scan` 窮舉)

`call_scan 0x115b6`(比 `xref_to` 可靠,見既有方法論)找到 **9 個呼叫端**,全部 `confirmed_call_instruction=true`:

| 呼叫位址 | 所在函式 | 語意 |
|---|---|---|
| `0x18981` | `FUN_00018890`(移動確認外層,doc13 上一節) | 移動目的地確認,`param_1=4` |
| `0x18f76` | `FUN_00018d8c`(指令環,本節) | **攻擊目標確認,`param_1=0`** |
| `0x1bd54`/`0x1bdf2`/`0x1bedb` | `FUN_0001bbdc`(道具 action,doc13 舊 §「`0x1bbdc`」) | 道具目標確認(3 處,`param_1` 未逐一查) |
| `0x1d1da`/`0x1d238`/`0x1d2e3`/`0x1d3ac` | `FUN_0001cff0`(法術 command loop) | 法術目標確認(4 處,`param_1` 未逐一查) |

`call_scan 0x2e2b0`(攻擊 orchestrator)找到 **4 個呼叫端**,同樣全部 `confirmed_call_instruction=true`:
`0x1561f`(`FUN_0001548e` 內,doc13 08-19 訂正已記載的舊 `doc35` 誤標對象)、**`0x18fc6`**
(`FUN_00018d8c` 內,即本節攻擊 case 0 的呼叫點)、`0x31aee`、`0x3578b`(這兩個 in_function=null,
待查,但與本次「索爾攻擊為何沒出手」無關,因為索爾走的是 `0x18d8c` 路徑)。**`0x2e2b0` 只有這
4 個呼叫端,不存在第 5 條隱藏路徑**——這回答了任務項目 4。

### 1. 攻擊目標確認呼叫現場(`0x18f76`,`0x18d8c` case 0 內)——逐位元組核對參數與 Enter/Escape 分支

直接反組譯 `0x18f50..0x18fb0` 附近的機器碼(而非只看 decompile,因為 `FUN_000115b6()` 在
decompile 裡完全不顯示參數,是已知的 decompiler arg-blindness),精確還原呼叫序列:

```asm
PUSH dword ptr [0x00053ab5]      ; DAT_00053ab5(游標 Y)
PUSH dword ptr [0x00053ab1]      ; DAT_00053ab1(游標 X)
CALL 0x00014818                  ; 候選陣列 builder,回傳 count(EAX)
ADD  ESP,0x18
PUSH ESI                         ; = param_3(候選陣列指標)
PUSH EAX                         ; = param_2(候選 count)
PUSH 0x0                         ; = param_1(mode=0，攻擊)
CALL 0x000115b6                  ; @0x18f76
MOV  EDI,EAX                     ; 回傳值存 EDI(對應 decompile 的 iVar2)
ADD  ESP,0xc
PUSH dword ptr [0x00053a51]
CALL 0x0004df4c                  ; 已知共用尾綴
ADD  ESP,0x4
PUSH ESI
CALL 0x0003776e                  ; 已知共用尾綴
ADD  ESP,0x4
CMP  EDI,-1                      ; if (iVar2 == -1)
JNZ  0x00018fb3                  ; 不等於 -1 → 跳過取消區塊，繼續往下
  PUSH dword ptr [ESP+0x74]
  PUSH dword ptr [ESP+0x7c]
  CALL 0x00012cea
  XOR  EAX,EAX
  JMP  <epilogue>                ; return 0(取消，回到 0x18890 外層重呼 0x18d8c)
0x18fb3: ...                      ; 繼續 → 0x12c0d → 0x1f04a → 0x18fc6: CALL 0x0002e2b0
```

**結論(回答任務項目 3)**:`0x115b6` 回傳後,`0x18d8c` case 0 只有唯一一個分支
——`CMP EDI,-1 / JNZ`——完全對應既有 decompile 記載的 `if (iVar2 == -1) { ...; return 0; }`。
**沒有第二個隱藏 gate**:只要 `0x115b6` 回傳的不是 `-1`(即回傳 `1`,confirm 成功),執行流就會
無條件依序呼叫 `0x12c0d`→`0x1f04a`→`0x2e2b0`,中間沒有任何額外的 `CMP`/`TEST`/`Jcc`。**這代表
「orchestrator 斷點從未命中」不可能是這段 `0x18d8c` 尾段邏輯本身的問題——真正的卡點只能是
`0x115b6` 從未回傳 `1`(甚至從未回傳,卡在自己內部的阻塞式讀鍵迴圈裡)。**

### 2. `0x115b6` 完整職責(`param_1=0` 攻擊分支的逐位元組路徑)——回答任務項目 2

完整反組譯 + decompile 交叉核對後的精確簽名與控制流(取代上一節較簡化的敘述版本):

```c
undefined4 __stdcall FUN_000115b6(int param_1 /*mode*/, uint param_2 /*count*/, byte *param_3 /*候選陣列*/)
```

- `param_1==6`:特殊「同格多單位堆疊」模式(把 `param_2` 另存 `local_18`、`param_2` 歸零),不是
  本次路徑,略過。
- `param_2==0`(本次無關,因為 `0x14818` 一定會回傳至少 1 個候選才會進 case 0——見 §4):
  直接跳過候選格繪製,進入按鍵迴圈。
- **按鍵迴圈**(`FUN_00012dac()` 阻塞式讀鍵,doc13 上一節已證實其結構):
  - `scancode==1`(Esc) → `return 0xffffffff`。
  - `scancode∈{0x39(Space),0x1c(Enter)}` 且 `param_1!=6` → 直接跳到 **confirm 驗證段**(見下)。
  - 方向鍵(`0x48/0x50/0x4b/0x4d`)→ 呼叫對應的候選格移動 helper(`0x11b48`/`0x11b9b`/
    `0x11c59`/`0x11bfa`,doc13 上一節已列)、`0x25a96` 重繪,迴圈頂端。
  - 其他鍵(`0x2c`/`0x4c`,且 `param_2!=0`)→ 候選陣列內循環换下一個候選格(`uVar5` 遞增並
    wrap),迴圈頂端。
- **confirm 驗證段(`LAB_00011719`)**:
  ```c
  if (param_1 == 5) goto 迴圈頂端;              // mode 5 永遠拒絕確認(語意待查)
  if (目標格 record(DAT_00053a51 索引 cursorY*width+cursorX 的 +7 byte) == -1)
      goto 迴圈頂端;                             // 目標格是空格 → 靜默拒絕，繼續讀鍵
  if (param_1 == 4) return 1;                    // 移動確認：格子非空即可，不再驗證
  iVar3 = FUN_00014742(cursorX, cursorY, <距離門檻>, 0, param_1);
  if (iVar3 == 0) goto 迴圈頂端;                  // ★★★ 見 §3，這是攻擊確認唯一的額外 gate
  return 1;
  ```
  **`param_1=0`(攻擊)這條路徑,confirm 成功的必要條件是 `FUN_00014742(...)!=0`**——這是
  doc13/doc58 先前從未追過的一段,也是本節的核心發現。

### 3. `FUN_00014742`:重新驗證「游標當下位置附近是否還有活著的敵方單位」,距離門檻讀自一個 96-xref 的高共用 global

`FUN_00014742`(214 bytes,`0x14742..0x14817`)完整反組譯,簽名
`FUN_00014742(int cursorX, int cursorY, int distThreshold, int outBuf, int campFilter)`(5 參數,
逐一由 `0x1174c..0x1175f` 的 5 個 `PUSH` 直接反組譯核對,不依賴 decompile 的空參數列表)。呼叫端
實際傳入:`cursorX=DAT_00053ab1`、`cursorY=DAT_00053ab5`、`distThreshold=` **`0x115b6` 自己入口處
`clamp(DAT_00051a83)`**(`EAX=DAT_00051a83; 若 EAX>1 則 EAX--`,見 `0x115dc..0x115ea`,結果存在
`0x115b6` 自己的 local frame,`0x14742` 呼叫現場用 `PUSH dword ptr [ESP+0x10]` 讀出這個值)、
`outBuf=0`(不寫陣列,只要 count)、`campFilter=param_1`(本次=0)。函式本體:

```c
int FUN_00014742(cursorX, cursorY, distThreshold, outBuf, campFilter) {
  int matchCount = 0;
  for (i = 0; i < DAT_00053beb /*roster size*/; i++) {
    rec = DAT_00053a45 + i*0x50;
    dx = abs(rec[+0] - cursorX);           // FUN_00037932 = abs()
    dy = abs(rec[+1] - cursorY);
    if ((rec[+5] & 1) == 0                  // raw admission bit0（doc13/25/26 既有: 不可直接命名死亡/存活）
        && dx+dy < distThreshold            // Manhattan 距離門檻
        && campFilter 對應 rec[+6] 相符（0=敵/1=非敵/2=友/3=己，既有 code）) {
      if (outBuf != 0) outBuf[matchCount] = i;
      matchCount++;
    }
  }
  return matchCount;
}
```

**也就是說:攻擊目標確認的 Enter 鍵,真正判定「可以確認」的條件不是候選陣列本身,而是重新
掃一遍全體單位,現場核對「游標目前所在位置附近、距離 < `distThreshold` 的範圍內,是否還存在
一個 `rec[+5]&1==0`(raw admission bit0 清除)且 `rec[+6]==0`(敵方陣營)的活躍單位」——這是一個
**即時再驗證**,不是單純讀候選陣列的第 N 個元素。`distThreshold` 若為 `1`(即 `DAT_00051a83==1`
時 clamp 後不變),則 `dx+dy<1` 要求 **游標必須恰好落在該敵方單位所在格**(距離 0),與既有
gameplay 記載(doc13「移動/攻擊操作流程」item 6:「目標游標會自動吸附到最近的敵人」)吻合——
這個 gate 語意上應該是「confirm 當下,游標吸附到的那格是否還站著一個可打的活敵人」,不是廣義
的武器射程檢查(武器射程已經在更早的 `0x14818` 候選建構階段用過)。

**但 `DAT_00051a83` 本身不能被靜態信任為「這裡一定是 1」**:`xref_to 0x00051a83` 掃出
**96 筆引用**,寫入端(`WRITE`)散布在**至少 40+ 個不同位址**、橫跨 `0x10483` 一路到
`0x328f4`(含 `0x13xxx`/`0x14xxx`/`0x15xxx`/`0x16xxx`/`0x17xxx`/`0x18xxx`/`0x1axxx`/
`0x1bxxx`/`0x1dxxx`/`0x2022xx`/`0x323xx-0x328xx` 這麼大的範圍),**結構上跟 doc13 前一節
記載的 `DAT_00053c57`(20+ 個 writer、3 套獨立選單子系統共用)高度相似**——這很可能又是一個
被多套完全不相關的子系統(移動/選單/道具/法術/演出叢集)共用的暫存 global,不是攻擊確認
專屬的「射程」變數。**目前唯一已知會把它設成 `1` 的地方是 `0x18890`(移動確認外層)在**
**move-confirm 成功之後**(`DAT_00051a83 = 0; FUN_00012cea(); DAT_00051a83 = 1;`,doc13
上一節記載)——但 `0x18d8c`(指令環)自己完整反組譯後確認**完全不觸碰這個 global**,所以
攻擊確認當下 `DAT_00051a83` 到底是不是 `1`,完全取決於**这次遊戲執行到攻擊確認之前,這 40+
個 writer 裡最後一個被執行到的是哪一個、寫了什麼值**——這是純靜態分析無法回答的問題,
必須靠 live 記憶體讀取。

### 4. 對「離線 patch+存檔跳章」情境的具體風險檢查(回答任務項目 5,仿照 `0x18890`/floodfill 的同類型檢查)

`FUN_00014742` 這個 gate 依賴三類「可能只有正常流程才會設好」的狀態,逐一列出:

1. **`DAT_00051a83`(距離門檻的原始值)**:見 §3,是一個 40+ writer 共用的 global,**如果這場
   離線 patch+存檔跳章合成的戰鬥從一開始沒有走過任何一個正常會寫入它的 code path(例如从未
   成功完成過一次 `0x18890` 的 move-confirm,因為續四十七這次連移動確認本身都不可靠)**,它的值
   可能停留在某個跟「1」無關的殘留值——過大(門檻寬鬆,不會卡)或過小/負值/垃圾值(門檻永遠
   不滿足,confirm 永遠失敗,完全吻合續四十七觀察到的症狀)。
2. **敵方單位 `rec[+5]` bit0(raw admission bit)**:doc13/25/26 三份文件都明確警告「不可直接
   命名成死亡/存活」,但已知 writer 包括 constructor(`0x10eed` 寫 0)與 HP 死亡路徑
   (`0x1dc61`/`0x1dd4c`/`0x32975` 寫 1)。**如果離線 patch 敵人成長表(續二十七)的工具在改寫
   敵人 record 時,連帶把這個 raw byte 誤寫成非 0(bit0=1),或者存檔跳章合成流程沒有正確重建
   這個 byte(例如直接複製了另一份已經標記過「不可選」的敵人 record)**,`FUN_00014742` 會把
   這隻敵人整個排除在外——即使牠在畫面上明顯存活、站在原地。這跟續四十五推翻的「MV=0」假說
   結構完全一樣:**一個持久狀態欄位如果被外部工具動過手腳,會在完全不同的 native 函式
   (這次是 `0x14742`,不是 floodfill)裡造成同一種「confirm 永遠失敗」症狀**。
3. **游標吸附位置(`DAT_00053ab1`/`DAT_00053ab5`)是否真的落在敵人格上**:`distThreshold`
   若為 `1`,要求距離恰好為 `0`。這依賴更早的 `0x14818`(候選 builder)或方向鍵 helper
   正確把游標「吸附」到敵人格——**本節沒有查證 `0x14818` 是否在攻擊 case 0 這次呼叫裡真的執行
   了自動吸附,還是游標停在移動前的殘留位置**;如果游標沒有精確落在敵人格上,`FUN_00014742`
   同樣會回傳 0,不需要牽扯 `+5`/`DAT_00051a83` 任何一個假說。

**與續四十七「SMV 傳送繞過移動」的張力**:上述三個依賴都是**敵方單位或全域暫存狀態**,不是
索爾自己的 record——`SMV` 只改了索爾的 `+0`/`+1`,不會直接影響這三者。但**如果續四十七的
SMV 傳送同時也跳過了正常 `0x18890` move-confirm 流程(它確實跳過了,見 §3 對
`DAT_00051a83` 的分析)**,`DAT_00051a83` 這條依賴就會落空——這是一條 SMV 傳送**間接**
造成 confirm 失敗的新機制,不同於續四十七自己提出但存疑的「格子佔用索引表」假說,**推薦優先
驗證這一條,因為它有具體位址與具體讀取值可以直接對照**。

### 5. 小結

- `0x115b6` 這個特定呼叫現場(`param_1=0`,攻擊目標確認)**這次是首次被完整反組譯**,`0x18d8c`
  回傳後到 `0x2e2b0` 之間**只有一個 `CMP EDI,-1/JNZ` gate**,沒有第二個隱藏條件——回答任務
  項目 3。
- `0x2e2b0` 全 EXE 只有 4 個呼叫端,索爾這條路徑唯一相關的是 `0x18fc6`(`0x18d8c` 內)——回答
  任務項目 4。
- 真正決定「Enter 能不能確認攻擊」的是 `0x115b6` 內部呼叫的 `FUN_00014742`,它在**游標目前
  位置**重新掃一遍找活敵人,距離門檻來自一個 96-xref、40+ writer 的高共用 global
  `DAT_00051a83`——這個 global 的值**無法靜態確定**,必須 live 讀取。
- 三個具體、可 live 驗證的候選根因已列出(§4),優先順序:`DAT_00051a83` 的即時值 >
  敵方 `+5` bit0 的即時值 > 游標吸附位置是否精確命中敵人格。

---

## 2026-09-04:指令環鏈路的**原版實機**驗證(DOSBox-X live,斷點逐段命中)

本節以前的 §0/§1 是純反組譯推得的。本輪在原版 DOSBox-X 的 ch01 實戰中逐段下斷點確認,
載入 delta 由 gate-check byte signature 實測校準(單一命中,`0x19c000`)。
**這是原版側證據**,不受 2026-09-04 remake 排除判準影響。

### 鏈路逐段命中

| 動作 | 斷點 | 結果 |
|---|---|---|
| 瀏覽游標按 Enter | `BP 0170:001B4890`(= `0x18890`) | **EIP=`0x001B4890` 命中**;resume 後畫面出現正常的移動範圍選格(索爾 LV-01/HP042/MP000 標頭卡 + 可移動格亮起) |
| 確認落點後 | `BP 0170:001B4D8C`(= `0x18d8c`) | **EIP=`0x001B4D8C` 命中**,四方向指令環開啟 |

即 §0 記載的 `0x117e7 → 0x18890 → 0x115b6 → 0x18d8c` 在原版上成立。
同時活體讀到戰鬥確實在進行:`[0x53bef]`=1(回合1)、`[0x53beb]`=12(我方4+敵方8)、
游標 `[0x53ab1]/[0x53ab5]`=(7,14) 正落在 idx0(索爾,camp 0x02,acted 0)。

### `DAT_00053c57` 的方向→索引對映:**實測證實 §1 的索引配置**

在環開啟狀態下逐鍵讀 `[0x53c57]`:

| 操作 | `[0x53c57]` | 對應 §1 的 slot |
|---|---|---|
| 環剛開啟 | 0 | — |
| ↑ | **0** | `[0]` 攻擊 |
| ← | **0(不變)** | `[1]` 法術——**被 disable,符合預測** |
| → | **2** | `[2]` 道具 |
| ↓ | **3** | `[3]` |

←不動是**被預測到的**無反應:索爾 MP 000/000、無已知法術,正是 §1 所列
`FUN_0001c269(unit,0)==0`(法術 bitfield `+0x1a..+0x1e` 全空)的 disable 條件。
§1「被 disable 的方向按了不會有任何提示,就是沒有反應」在原版上成立。
同理當時按 ↑(攻擊)畫面無反應,也符合 `0x14818` 射程內無敵方候選的 disable 條件
——索爾(短劍射程1)周圍確實沒有相鄰敵人。

### ⚠ 與 §1 不符的一點:slot `[3]` 的語意標籤「待機」**未被原版行為支持**

§1 把 `param_2[3]`(↓)標為「待機——永遠不 disable」。實測:

1. 按 ↓ 後 `[0x53c57]`=3(索引正確);
2. 按 Enter 確認後,**索爾的 `+5` 仍為 `0x00`**(bit7 Acted 未設),
   重讀單位陣列兩次皆然;
3. 畫面出現的是**單位狀態卡 + 裝備/道具資訊卡**(短劍+AP010/皮甲+DP008/藥草+HP040),
   不是結束行動;
4. 反向佐證:之後**還能再次對索爾開環**(`0x18d8c` 斷點再次命中)——若他已行動,
   `0x117e7` 的 `+5&0x80==0` gate 會擋下並改走 `0x17aed`。

也就是說**確認 slot 3 沒有結束該單位的行動**。§1 的索引配置(0/1/2/3 對應 上/左/右/下)
已被實測證實,但**把 `[3]` 稱為「待機」是尚未驗證的語意標籤**,且與上述行為矛盾。

**同輪已用反組譯解出,並更正上面第 3 點的措辭。** `FUN_00018d8c` 的 dispatch 完整長這樣
(`FD2_ghidra_projects/results_ring_20260904.json`,本輪產出):

```c
do { iVar1 = FUN_000177fc(); } while (iVar1 == 0);   // 按鍵迴圈
if (iVar1 == -1) return 0xffffffff;                  // 取消
if      (DAT_00053c57 == 0) { ... FUN_00014818(); FUN_000115b6(); ... FUN_0002e2b0(); }  // 攻擊
else if (DAT_00053c57 == 1) { do { FUN_0001cff0(); } while (...); ... }                  // 法術
else if (DAT_00053c57 == 2) { do { FUN_0001bbdc(); } while (...); DAT_00053ec8 = 0; }    // 道具
else {                       // == 3
    if (param_3 == 0) FUN_00013fd4();   // 休息回復
    FUN_000190ac();                     // 格子互動/寶物檢查
    FUN_00013512();
}
```

**這揭露本文件自己的內部矛盾**:§1 的表把 `[3]` 標為「待機——永遠不 disable」,
但本文件**另一張表(見上方 §「0 ↑ / 3 ↓」那張 case 對照表)早就把
`0x13fd4`→`0x190ac` 標為「休息回復／格子互動(case 3)」**。兩處說法不一致,
而反組譯支持後者:case 3 根本沒有「待機」語意,它是 rest-heal + 格子互動。

**§1 表格中 `[3]`=「待機」應更正為「休息回復／格子互動」**,與本文件另一張表一致。

這也解釋了實測為何毫無反應:索爾 HP 42/42 是滿的,`0x13fd4` 的
「current HP≠max HP」條件不成立 → 不回復;腳下沒有寶物 → `0x190ac` 也無事發生。
**四個分支裡沒有任何一個在本函式內設 `+5` bit7**,Acted 由各自的 callee 鏈負責。

⚠ **更正上面第 3 點**:當時記「畫面出現狀態卡+裝備卡」——那很可能是**前一次測試
(index 2 道具)留在畫面上的卡片沒有被更新**,而不是 case 3 畫出來的。case 3 在滿血+
空格子的條件下本來就不該有任何可見變化。**可確定的只有「Acted 未被設起來」**;
「它會顯示某張卡」這個敘述證據不足,撤回。
`0x18d8c` 的四個 case 各自呼叫什麼,需要再一輪反組譯或對每個 index 逐一實測 acted/HP
變化來定名。在那之前,§1 的 `[3]`=「待機」應視為**假說,不是已證實**。

（附帶:這也表示「自動結束回合」那一項還不能測——它需要先能讓單位真的完成行動。
本輪沒有做到,不當成已解。）

### 2026-09-04 續:`0x13512` = SetActed,以及「自動結束回合」的原版實證

**`FUN_00013512(unitIndex)` 就是設 Acted 的函式**(本輪反組譯,
`FD2_ghidra_projects/results_acted_20260904.json`):

```c
void __stdcall FUN_00013512(int param_1) {
  FUN_0003702f();
  pbVar1 = (byte *)(DAT_00053a45 + 5 + param_1 * 0x50);
  *pbVar1 = *pbVar1 | 0x80;      // record[+5] |= 0x80
  return;
}
```

`0x18d8c` 的 case 1 與 case 3 都無條件呼叫它,case 0 走 `0x134e4` 另一條。

#### ⚠ 撤回上一段的「確認 slot 3 不會設 Acted」

那個結論**證據不足,已證實為錯**。錯因值得記:我當時用讀 `DAT_00053c57` 得到 3
來認定「環是開的」,但**本文件自己就寫過 `DAT_00053c57` 是不會重置的殘留值**——
環關掉之後它照樣是 3。那幾次測試裡多按的 Escape 已經把環關掉了,我卻以為還開著。

**用環自己的斷點證明環是開的**之後重測:`BP 0170:001B4D8C`(=`0x18d8c`)命中 →
確認環開啟 → 換上 `BP 0170:001AF512`(=`0x13512`)→ 按 ↓ 再按 Enter →
**EIP 命中 `0x001AF512`**,resume 後讀回 idx0 `acted=0x080`。
所以 **case 3 確實會設 Acted、確實會結束該單位的行動**。

**可重現的單位行動序列**(每一步都可用 `+5` bit7 客觀驗證):

```
瀏覽游標對準單位 → Enter(進 0x18890 移動選格)→ Enter(確認落點,不移動)
→ ↓(DAT_00053c57=3)→ Enter  ⇒ record[+5] |= 0x80
```

#### 「自動結束回合」:**原版會自動換邊,不需要玩家手動結束**

M5-F 的命題是「原版在全員行動完畢後會不會自動換邊?還是也要玩家手動結束?」
本輪在 ch01 用上述序列讓我方四人依序行動,**第四人行動後不再按任何鍵**,然後讀記憶體:

| 觀察 | 結果 |
|---|---|
| 我方 idx0-3 的 `+5` bit7 | 由 `0x080` **全部被清回 `0x000`** |
| 敵方單位座標 | **7 個從初始位置移動了**(如 idx4 (1,4)→(3,6)、idx8 (3,18)→(5,16)) |
| 敵方 `+5` bit7 | 6 個為 `0x80` |

**結論:是,原版自動換邊。** 全員行動完畢 → 敵方回合自動執行 → 我方旗標自動重置,
全程零輸入。此項可自 M5-F 結案(原版側證據)。

**附帶一個未解的觀察,不改既有記載,只記錄**:跑完一整輪(我方→敵方→我方)之後,
`[0x53bef]` 仍然是 `1`,沒有增加。doc24/本文件既有記載說它是「回合/進度 counter
(開始1/inc/cmp N)」——至少在這一次換邊上它沒有 inc。這可能是它按別的事件遞增,
也可能既有描述需要修正;**證據不足以下結論,留待後續。**

### 2026-09-04 續二:想用 `0x17aed` 取得原版法術名稱字模——**路徑可行性未定,本輪未成**

`glyph 423`(麻痺術)還缺一張原版指令環的字模截圖。本輪試了一條不需要法術選單可用的
路徑:doc13 §2 記載三個 gate 任一不成立時,Enter 會呼叫 `0x17aed`,而該函式在單位
**有已知法術**時會加演「法術列表卡」。所以只要讓單位先設上 Acted,再對它按 Enter,
理論上就能叫出法術名稱清單。

**已確認可用的部分**:

- 用 debugger 的 `SMV <linear> 80` 直接寫 `record[+5]` 成功(讀回 `acted=0x080`),
  不必真的完成一次行動。ch27 的陣列基底由 `mem read-unit-array` 印出(本輪 `0x26df88`),
  `idx N` 的 `+5` 位址 = `base + N*0x50 + 5`。
- **副產物(原版側觀察)**:Acted 一設起來,該單位在地圖上立刻變成**灰色石像樣式的貼圖**。
  這與 FD2「已行動單位變灰」的表現一致,是 `+5` bit7 = Acted 的獨立佐證。

**未成的部分,以及為什麼不能據此下結論**:

對該單位按 Enter 後 `0x17aed` 的斷點沒有命中。但**加上 `0x117e7` 的對照組之後發現
兩個都沒命中**,而當下 EIP 停在 `0x12DBF`——那是 `0x12dac..0x12e37`,
`0x115b6` 專用的阻塞式讀鍵迴圈。也就是說當時**根本不在瀏覽游標狀態**,而是還在移動
確認裡,Enter 被那個迴圈吃掉了。游標全域仍讀到 `(16,54)` 是因為那是 selector 自己的游標。

**所以本輪不能宣稱「對已行動單位按 Enter 不會走 `0x17aed`」**——前提就不成立。
doc13 §2 的記載未被動搖。下一輪要重試這條路徑,必須先用 `0x117e7` 的斷點證明
確實回到了瀏覽游標狀態,再按 Enter;**只讀游標全域不足以證明所在的 UI 層級**,
這是本輪反覆踩到的同一個坑。

### 2026-09-04 續三:**`+0x40`/`+0x42` 的 cur/max 標反了**——本節的中毒公式是對的

查「哪些狀態會持續扣 HP」時發現兩份文件互相矛盾:

- 本節 §2(`0x1A866` 中毒扣血迴圈)寫:傷害 = `word[+0x42]/10`(**maxHP**/10),
  扣在 `word[+0x40]`(**現值**)。
- `fd2_dosbox_live_helper.py` 的欄位表(源自 doc92 續四,2026-09-02)寫:
  `+0x40 = HPmax`、`+0x42 = HPcur`——**正好相反**。

**根因:原始驗證用的是退化樣本。** doc92 續四說它「逐欄對過狀態卡」,但對照樣本是
索爾的 **HP 042/042**——滿血,`cur == max`,那個對照**在該狀態下根本無法分辨這兩個
offset**。今天讀到的每一筆也都是滿血(999/999、782/782、823/823),所以一直沒暴露。

**判定實驗(原版實機)**:寫兩個**不同**的值,強制重繪後讀畫面。

| 寫入 | 畫面顯示 | 結論 |
|---|---|---|
| `+0x40`=500, `+0x42`=300 | `HP 500/300`,且 HP 條呈**滿**(現值 500 > 上限 300 被夾住) | `+0x40`=現值、`+0x42`=最大值 |
| `+0x44`=400, `+0x46`=200 | `MP 400/200` | `+0x44`=現值、`+0x46`=最大值 |

同一張截圖裡「數字順序」與「HP 條是否滿」兩個獨立讀法互相印證。
修正工具欄位後重讀,得到 `HP 500/300 / MP 400/200`,與畫面逐欄吻合。

**因此本節 §2 的中毒公式成立,不必修改**:中毒每回合扣的是**最大 HP 的 1/10**,
扣在現值上——是會致死的(約十回合),不是「當前 HP 的 10%」那種永遠打不死的遞減。

⚠ 注意寫入後**畫面不會自動重繪**(見 doc48 §11):第一次截圖仍顯示舊的 999/999,
Escape 再 Enter 強制重繪後才看到 500/300。若沒察覺這點,這個實驗會得出相反的結論。

### 2026-09-04 續四:`[0x53bef]` 的遞增時機(單次觀察)

doc24/本文件既有記載說它是「回合/進度 counter(開始1/inc/cmp N)」,但 2026-09-04 稍早
曾觀察到「跑完一整輪之後仍是 1」而留下疑點。本輪用取樣把它釘住。

**方法**:不驅動、只旁觀,每 6 秒同時讀 `[0x53bef]`、`[0x53beb]`、
以及單位陣列裡我方/敵方各自的 `+5` bit7 已行動數。

| 取樣 | `[0x53bef]` | 我方已行動 | 敵方已行動 |
|---|---|---|---|
| 0s | 1 | 0/4 | 0/8 |
| 6s | 1 | 0/4 | 3/8 |
| 12s | 1 | 0/4 | 4/8 |
| **18s** | 1 | **0/0** | **0/12** ← 見下 |
| **24s** | **2** | 0/4 | 6/8 |
| 30s+ | 2 | 0/4 | 0/8(旗標已清) |

**結論(單次觀察,未重現)**:`[0x53bef]` 是在**敵方回合結束、新的我方回合開始**那個
邊界遞增的,**不是**在我方→敵方那次翻轉。這正好解釋稍早那個疑點:當時的取樣落在敵方
回合進行中,新的我方回合尚未開始,所以讀到的仍是 1。

⚠ 本輪嘗試驅動第二個回合以求重現**未成功**(`fd2_battle_autoplay.py` 的行動迴圈仍有
已知問題,見 doc48 §5),所以這是**一次觀察**,不是可重現結論。

#### 附帶發現:轉換瞬間的單位陣列**不可靠**

18s 那一筆讀到「我方 0 人、敵方 12 人」——陣營位元組 `+6` 在回合轉換的瞬間是不一致的
(12 個槽全部被讀成同一陣營)。

**這意味著任何在該窗口取樣的判定都可能出錯**,包括 `fd2_in_battle_check.py` 的
「我方存活單位 ≥ 2」條件——它在那一瞬間會判定不在戰鬥中。實務上:讀單位陣列要避開
回合轉換,或連讀兩次確認一致。

## 2026-09-05:目的地確認再驗證鏈路(`FUN_0004e4f6`/`e5cc`/`e680`/`e751`)完整反組譯——追查 C.16 的 DOS-exit 機制,「軟堆疊寬鬆剪枝可跑深」假說被真實呼叫現場的參數值推翻

> 背景:`docs/knowledge-base/SESSION-HANDOFF-2026-09-04.md` 附錄 C.16 用
> `tools/fd2_trial_runner.py`(N=5/組,3 平行)確立了一個有統計意義的結果——
> `fd2_battle_autoplay.py --attack`(移動並確認一個算出來的落點)讓 FD2.EXE 退回 DOS
> 提示字元的機率遠高於 `--mv 0`(mv4 5/5 死、mv0 0/5 死,Fisher's exact p≈0.0079)——
> 但機制未知。交接清單把「靜態反組譯 `FUN_0004e4f6` 及其呼叫端」列為下一步。本節是
> 對這個交接項目的第一次真正動手,**純靜態**(直接反組譯位元組,無 DOSBox-X 活體驗證)。

### 0. 先釐清:C.16 踩到的是哪一段路徑

`FUN_0004e4f6` 有 4 個呼叫端(`call_scan` 確認):`0x189f8`(`0x18890` 內,**目的地確認**,
即 doc13 上一節「§3 出口B」記載的那顆)、`0x14121`/`0x14b78`(攻擊射程候選判定)。`--attack`
的按鍵序列(移動候選格→Enter 確認)精確對應 `0x189f8` 這條路徑——這是本節鎖定的範圍,
跟上面「flood-fill 家族」那節(2026-08-21)反組譯的 `FUN_0004e42c`/`FUN_0004e4be` 是**不同
的一對函式**:`0004e42c` 家族在**移動選單一打開**就跑(建立整個移動範圍格陣列),
`0004e4f6`→`0004e5cc`/`0004e680`/`0004e751` 這一對是**確認落點的那一刻**才跑(單獨驗證
「這一格是否真的可達」)。C.16 的按鍵序列必定會走到後者,不必然會讓前者重跑。

### 1. 完整反組譯(flow-directed,逐 byte 核對,取代先前只讀 decompile 的版本)

```asm
; FUN_0004e4f6(esi_costtab, startX, startY, initCL, outBuf, tgtX, tgtY, mode, gridptr, classtab)
0x4e4f6  push ebp
0x4e4f7  mov ebp, esp
0x4e4f9  pushal
0x4e4fa  mov esi, [ebp+8]        ; ESI = 每單位地形成本表指標
0x4e4fd  mov [0x6006a], esi
0x4e503  ...                     ; 其餘 8 個參數逐一寫進 DAT_0006006e..DAT_0006017a(見 §2)
0x4e5a2  lea edi, [0x60079]      ; 軟堆疊基底,跟 FUN_0004e42c 用同一個位址
0x4e5a8  mov [ebx], cl           ; 起點格寫入初始預算
0x4e5aa  mov byte[0x60077], 0    ; 深度計數器歸零
0x4e5b1  mov byte[0x60078], 0xff ; 結果 sentinel(不可達預設值)
0x4e5b8  call 0x4e751            ; 先檢查起點格本身是不是目標格(0 步移動的邊界情況)
0x4e5bd  call 0x4e5cc            ; ★ 第二套遞迴 flood-fill 的根呼叫
0x4e5c2  popal
0x4e5c3  xor eax,eax
0x4e5c5  mov al,[0x60078]        ; 回傳值 = 結果(0xff 或路徑長度)
0x4e5ca  pop ebp
0x4e5cb  ret
```

`FUN_0004e5cc`(180 bytes)結構上跟 `FUN_0004e42c` 是同一個模板,但**槽位是 8 bytes 不是
7 bytes**(多存一個 CH 旗標 byte):進入時 `EDI += 8`(push)、4 個方向各呼叫一次
`FUN_0004e680`(可否進入這格)+ 條件式遞迴呼叫自己、**函式最尾端只有一次 `SUB DI,8`**
(pop)才回到呼叫端——跟 `FUN_0004e42c` 完全一樣的「進入時 push 一次、離開時 pop
一次」紀律,不是每次遞迴呼叫後個別 pop。這代表 **EDI 的最大偏移量 = 最大同時遞迴深度**,
不是整趟 flood-fill 呼叫總次數的累加——**軟堆疊會確實收斂回原點,不是只增不減的洩漏**。
`inc byte[0x60077]` / `dec byte[0x60077]` 分別在進入/離開時執行,證實 `DAT_00060077`
就是即時遞迴深度(呼應既有文件「目前遞迴深度/路徑長度」的說法,本節逐位元組坐實)。

`FUN_0004e680`(可否進入這格的葉節點判定,對應 `FUN_0004e42c` 用的 `FUN_0004e4be`)
關鍵差異在剪枝條件:

```asm
0x4e6a5  cmp cl, al       ; al = 這格已記錄的預算
0x4e6a7  jl  fail          ; CL <  已記錄值 → 失敗(比 e4be 一樣嚴格)
0x4e6a9  jg  accept        ; CL >  已記錄值 → 接受(比 e4be 一樣嚴格)
             ; CL == 已記錄值(相等,e4be 在這裡直接 fail):
0x4e6ab  cmp byte[0x6017a], 1
0x4e6b2  jne fail          ; mode != 1 → 一樣失敗
             ; mode == 1 才會接受「相等」也算成功 —— e4be 完全沒有這條路
```

**`FUN_0004e4be`(移動選單用)只接受嚴格 `>`;`FUN_0004e680`(確認落點用)在 `mode==1`
時額外接受「相等」。** 這是一個真實存在的、`0004e42c`/`0004e5cc` 兩套引擎之間的行為差異,
先前完全沒有文件記載過。**如果 mode==1 在真實遊戲的呼叫現場成立,「相等預算的格子可以被
重複踩」會打破 e42c 那種「深度 ≈ 初始 CL / 最小地形成本」的天然上限,同一條路徑可以在
同成本地形間反覆進出,讓遞迴深度(進而軟堆疊用量)遠超單純的 MV 估算**——這是一個
具體、可證偽的候選機制,寫下來之前先去查真實呼叫現場到底傳的是哪個 mode。

### 2. 真實呼叫現場(`0x189f8`)的 10 個參數逐一核對——**mode 是硬編碼 `0`,不是 `1`**

Flow-directed 反組譯 `0x188d9..0x189fd`(`0x18890` 內,目的地確認呼叫現場),10 個 `PUSH`
(程式順序,對應到 callee `[ebp+8]..[ebp+0x2c]` 反向):

```asm
0x189cd  push dword ptr [0x53a69]   ; classtab  = DAT_00053a69(地形類別表)
0x189d3  push dword ptr [0x53a51]   ; gridptr   = DAT_00053a51(跟移動範圍陣列同一份地圖)
0x189d9  push 0                     ; ★ mode      = 0(硬編碼立即數,不是變數)
0x189db  push dword ptr [0x53ab5]   ; tgtY      = 游標 Y
0x189e1  push dword ptr [0x53ab1]   ; tgtX      = 游標 X
0x189e7  push dword ptr [esp+0x30]  ; outBuf    (未逐一回溯來源,不影響本節結論)
0x189eb  push dword ptr [esp+0x30]  ; initCL    (同上)
0x189ef  push dword ptr [esp+0x40]  ; startY    (同上)
0x189f3  push dword ptr [esp+0x48]  ; startX    (同上)
0x189f7  push edi                   ; costtab   = FUN_0004e8a5(unit) 回傳值
0x189f8  call 0x4e4f6
```

`push 0` 是**立即數**,不是讀某個可能因存檔/離線 patch 而壞掉的變數——**這條路徑在任何
情況下 mode 都是 0,不可能在正常或異常存檔狀態下變成 1**。回到 §1 的剪枝邏輯:mode=0
時,`CL == 已記錄值` 這條路一樣 `jne fail`,跟 `FUN_0004e4be` 的行為**等價**,不是更寬鬆。

**因此:「`FUN_0004e680` 的相等值放行路徑讓遞迴跑得比 e42c 深」這個假說,被目的地確認
呼叫現場的真實參數值推翻——mode 恆為 0,放行路徑從未啟用。**

### 3. 軟堆疊溢位的物理空間 & 誠實結論

用 LE object table 逐一核對(`tools/le_xref.py` 的 `parse_le`):`DAT_00060xxx` 系列全部落在
obj2(`0x60000..0x634d2`,13522 bytes)。軟堆疊基底 `0x60079` 到下一個**已知有意義的常數表**
`DAT_00061646`(每單位地形成本表,編譯期烘焙常數,見上面「flood-fill 家族」一節 §3)之間有
**0x15cd = 5581 bytes 的空間**。`FUN_0004e5cc` 槽位 8 bytes/層,理論上要疊到 **約 697 層**
才會開始踩進 `DAT_00061646`。而 mode=0 確認後,最大同時遞迴深度理應跟 `FUN_0004e42c` 同一
數量級——由初始 `CL`(≈ MV,`fd2_stat_override.py` 自己夾在 60 以內)除以每步最小地形成本
決定,正常情況下遠低於 697 層。

**誠實結論(這是本節唯一能負責任地說的話)**:

1. `FUN_0004e5cc`/`FUN_0004e680` 這一路(destination-confirm 專用)第一次被完整反組譯,
   跟移動選單用的 `FUN_0004e42c`/`FUN_0004e4be` 結構高度相似但不完全相同(槽位大小、
   剪枝條件的 mode 分支)——這是**新增的既有事實**,先前文件從未記載這兩套引擎有差異。
2. 本節原本想驗證的「mode==1 的相等值放行路徑讓遞迴失控」這個具體候選機制,**被真實呼叫
   現場 mode=0 的證據推翻**,不是本節迴避掉的——查了、有明確反例。
3. **C.16 的 DOS-exit 機制依然未解。** 軟堆疊本身(不管是 e42c 還是 e5cc 那條)在「mode
   固定、無跳表 EQUAL 放行、CL 上限 60」的正常前提下,理論可用深度遠低於它會撞到已知常數
   表的門檻——這個事實**弱化**(不是排除)了「單純遞迴深度撞穿軟堆疊」假說,因為它排除了
   一條原本看起來可信的「深度失控」路徑。剩下未查的候選(留給下一輪,本節不猜):
   - `FUN_0004e71f`(`0x4e680` 兩條 accept 分支都會呼叫,本節完全沒有反組譯,不知道它
     對 `[ebx-2]` 之外還動了什麼)。
   - 地形成本表如果真的存在 0 成本 tile(本節沒有讀出實際表格內容,只讀了查表**邏輯**),
     深度上限的「CL / 最小成本」估算會失真——這一步需要**讀出 `DAT_00060060`/`DAT_00060070`
     指向的實際表格數值**,不是本節反組譯範圍能回答的,需要靜態讀常數段或活體 dump。
   - `FUN_0004e751`(命中檢查,§1 已完整反組譯)裡的 `STOSB` 迴圈用 `[0x53a73]`(`outBuf`)
     當目的地、迴圈上限是 `AH`(即 `DAT_00060078` 讀出的深度)——如果 `outBuf` 配置的緩衝區
     大小小於實際可能的深度,這是**另一個獨立、不需要動到軟堆疊本身**的溢位候選,本節
     沒有查 `outBuf`(`FUN_0003706e` 配置)的緩衝區大小,留給下一輪。

### 4. `FUN_0004e71f`/`FUN_0004e703` 逐一查完——都是無害的唯讀/定長寫入,不是新候選

- **`FUN_0004e71f`**(反組譯完畢,`0x4e71f..0x4e750`):純唯讀掃描,`ESI` 從軟堆疊基底
  `0x60079` 走到 `AH`(=當下深度 `DAT_00060077`)層,統計每層 `+3` 那個方向標記 byte
  跟前一層不同的次數(轉彎計數),回傳 `count*4`。**只讀不寫、迴圈上限就是已經追蹤的深度
  本身**,不會讓軟堆疊多長一分,不是溢位候選。
- **`FUN_0004e703`**:只在地形 flag `bit0x40`(不可通過)成立時才動作,固定寫 2 bytes 到
  `outBuf[0]`/`outBuf[1]`(記錄第一個擋路格座標)並把 `DAT_00060078` 設成 `1`——**定長寫入,
  不隨深度增長**,也不是溢位候選。

兩個子函式都查完了,結論:**這條呼叫鏈裡真正有「寫入量隨路徑長度增長」特性的,只有
`FUN_0004e751` 自己的 `STOSB` 迴圈**(見 §5)。

### 5. **新候選,比軟堆疊本身更具體**:`outBuf` 是 `malloc(MV)`,`STOSB` 迴圈寫入量 = 路徑長度——如果地形成本表有 0 點的 tile,兩者可以對不上

反組譯 `FUN_0003706e`(`0x3706e`/`0x3707e`)確認它是 **Watcom runtime 的 `malloc()` 包裝**
(內部呼叫 `0x3d5c0`,失敗時走 `0x3d842`/`0x3da42` 兩段記憶體壓縮重試——標準 Watcom
`_nmalloc` retry-on-fail 樣板,不是自訂配置器,大小完全由呼叫端決定,沒有內部 padding)。

呼叫現場(`0x18890` 內 `0x18912..0x18916`):

```asm
0x188d9  movzx eax, byte ptr [esi+0x3b]   ; eax = 本單位 MV(見既有多輪已定案的欄位)
0x188dd  mov [esp+0x18], eax
...
0x18912  push dword ptr [esp+0x18]         ; ★ malloc 的 size 參數 = MV 本身,原封不動
0x18916  call 0x3706e
0x1891b  mov [esp+0x20], eax               ; local_20/local_1c(decompile 命名)
```

**配置大小精確等於這個單位的 MV 屬性值,沒有任何倍數或保留量。** 而 `push dword ptr
[esp+0x30]`(§2 的 push6,`FUN_0004e4f6` 的 `outBuf` 參數)在同一個函式的呼叫序列裡,
指向的正是這個 `local_20`——**本節沒有逐一 byte 核對這條 ESP 位移鏈到底是不是同一個
變數**(`0x18890` 函式體內 ESP 因為多層 push/pop 反覆變動,人工核對容易算錯),所以這一步
**標記為推論、不是逐位元組釘死**,但兩者的角色(唯一一個 `malloc` 出來的 scratch 指標、
唯一一個「大小由 MV 決定」的緩衝區)高度吻合,值得優先驗證。

若這條推論成立:`FUN_0004e751` 的 `STOSB` 迴圈(§1)在命中目標格時,寫入
`AH`(=`DAT_00060077`,當下遞迴深度)個 byte 到 `outBuf`。**正常情況下深度上限 ≈ 初始
`CL`(=MV)÷ 每步最小地形成本**——如果每步至少扣 1 點,深度絕不超過 MV,`malloc(MV)`
剛好夠用,沒有溢位。**但如果地形成本等級表(`DAT_0006006a` 指向的「成本等級→實際點數」
表)裡存在任何一個 0 點的 tier,單位就可以在該類地形上無限步進而不消耗 `CL`,深度可以
超過 MV 任意多——這時 `STOSB` 會寫出 `malloc(MV)` 緩衝區之外,是一個結構完整、動機明確
的 heap buffer overflow,而且完全不需要 §2 已被推翻的 mode==1 分支。**

**本節原本以為這一步需要活體驗證(表內容以為是 runtime 才填的 per-地圖資源)——這是
本節自己的一個錯誤:重新核對後,`SUB CL,[ESI+EAX]` 的 `ESI`(`DAT_0006006a`)來自
`FUN_0004e8a5(unit)=&DAT_00061646+unit*0x14`,而 `DAT_00061646`(§3「flood-fill 家族」
一節,2026-08-21)早就已經 `xref_to` 查過、坐實是「編譯期就烘焙進 EXE `.object3` 資料段的
常數表」——這一步其實跟 §5 前段提到的地形**類別**表(`DAT_00053a69`,runtime 載入)是
兩張不同的表,本節一開始把兩者混為一談了。真正決定「每步扣幾點」的最後一次查表
(`[ESI+EAX]`)用的是**靜態常數表**,不需要活體,可以直接讀 EXE 檔案位元組。**已經讀了,
結果如下。**

### 6. 靜態讀出 `DAT_00061646` 表——**沒有 0 點 tier,§5 的候選機制被推翻**

用 `tools/le_xref.py` 的 `parse_le`/`file_to_linear` 把 `0x61646` 換算成檔案位移
(`0x7a65a`),直接讀 1024 bytes、以每列 20 bytes(`unit*0x14`)切開:前 29 列
(`unit[0]`..`unit[28]`,對應 §2 分析的「movzx eax,[esi+0x20]」小整數欄位,語意是移動
類型/職業 id,不是戰場單位陣列 index)是結構一致的成本列,只出現 `0x01`(=1 點)、
`0x02`(=2 點)、`0x03`(=3 點)、`0x14`(=20 點,實務上等同「不可通過」)四種值——
**檢查範圍內(每列前 10 bytes,涵蓋所有實際會被 `AND AH,3` 之類遮罩產生的合理 tier
索引)沒有任何一個 `0`**。第 29 列開始出現 `0xff` 與遞增小數值等完全不同的位元組樣式,
代表這張表在第 29 列(`0x61646+29*0x14=0x617c2`)前就已經結束,後面讀到的是相鄰的
另一張表,不屬於這次分析範圍。

**結論:§5 的「地形成本表可能有 0 點 tier,讓 depth 超過 MV」候選機制,被直接讀出的表
內容推翻——最小非零/非阻擋成本是 1,沒有 0 點捷徑。** 這代表 `outBuf`(若真是
`malloc(MV)`)在正常查表邏輯下不會被 `FUN_0004e751` 的 `STOSB` 寫爆,§5 提出的具體
溢位候選**不成立**。

### 7. 現況總結與給下一輪的建議

本節依序驗證了兩個具體候選機制(§2 的 mode==1 寬鬆剪枝、§5/§6 的 0 點地形成本),
**兩者都用直接證據推翻了**——不是沒查,是查了、有明確反例。C.16 的 DOS-exit 機制
**依然未解**,但排除掉了兩條原本看起來可信的靜態路徑,這本身是有價值的收斂(避免
下一輪重複踩同樣的死路)。

1. ~~次要:逐位元組核對 ESP 位移鏈,坐實 `outBuf`=`local_20`~~ ——**已用腳本(不是手動)
   坐實,§5 的推論成立**。放棄手動追蹤是對的(風險確實存在),但正確的解法是寫一支小
   腳本沿著同一段 flow-directed 反組譯,對每條指令按 `push`(+4)/`pop`(-4)/
   `add esp,N`(-N)/`sub esp,N`(+N)線性疊加一個「虛擬 ESP 位移」,把每個 `[esp+K]`
   參照換算成「相對某個固定基準點的絕對槽位」(`slot = K - depth`)——兩個參照只要換算
   出來的 `slot` 相同,就是同一個區域變數,不管中間夾了幾層 push/pop。跑出來的結果:
   `0x1891b`(`local_1c`,decompile 命名)與 `0x189e7`(`outBuf` 那個 push,即 push6→
   `[ebp+0x18]`)換算後**都是 `slot=0x1c`,完全相同**——`outBuf` 確實就是
   `FUN_0003706e()`(`malloc`)剛配置、大小等於單位 MV 值的那塊記憶體,不是推論,是
   逐指令核對過的結果。同一次追蹤也順帶確認 `initCL`(push7→`[ebp+0x14]`)換算後是
   `slot=0x18`,跟 `0x188dd` 存 MV 值的那格完全相同——`FUN_0004e4f6` 的起始預算就是
   單位的原始 MV byte,未經任何縮放,這點先前只在 §2 靠人工核對過一次,這裡是第二個
   獨立方法給出同一個答案。**§5/§6 的推翻結論不受影響**(表裡本來就沒有 0 點,`outBuf`
   到底是不是 `malloc(MV)` 不會讓「有沒有 0 點 tier」這個事實改變),但「`outBuf` 是
   `malloc(MV)`」這件事本身現在是**確認過的新事實**,不再是推論。
2. ~~開放候選:`FUN_0004e42c`/`FUN_0004e4be` 有沒有類似問題~~ ——**已用既有事實回答,
   不需要新反組譯**:`e390`/`e4f6` 兩條路徑的 `ESI`(地形成本表指標)都來自**同一個**
   `FUN_0004e8a5(unit)` 呼叫(同一個 `edi` 暫存器值在 `0x18890` 內被兩條路徑各自重用,
   見 §2 呼叫序列),即 §6 讀出的是**兩套 flood-fill 共用的同一張表**——「沒有 0 點 tier」
   這個結論對 `e42c`/`e4be` 同樣成立,不需要另開一輪反組譯確認。
3. 如果 §7.1 也沒查到東西,C.16 的機制搜索需要換一個完全不同的角度(例如:不是這條
   移動/路徑鏈路本身,而是移動動畫播放、或某個跟按鍵時序有關的競態),不建議在同一條
   flood-fill 鏈路裡繼續深挖——本節跟前面「flood-fill 家族」(2026-08-21)、本節自己
   兩輪加起來已經是這條路徑第三次被系統性檢查,邊際報酬在下降。

### 8. 2026-09-05(續):換角度——debugger 斷點/讀值本身可能才是變因,不是遊戲程式碼

**背景**:本節 §1-§7 的整個前提是「崩潰的成因在 `FD2.EXE` 自己的移動/路徑驗證程式碼裡」。
但 `docs/knowledge-base/SESSION-HANDOFF-2026-09-04.md` 附錄 C.3(2026-09-04)早就記過一個
沒有被 C.16 的 trial-runner 重新排除的候選:**手動迴圈(完全跳過 `ensure_browse`)跑
29 次同樣的攻擊按鍵序列全部存活,而經過 `ensure_browse`(反覆 `BPDEL *`/`BP 0x18890`/
6 次 Escape/`BPDEL *`)的每一次都死**——懷疑對象是「debugger 反覆下斷點/刪斷點」這個
**工具行為本身**,不是遊戲邏輯。C.16 的 trial-runner 測試(mv4 5/5 死、mv0 0/5 死)雖然
兩組都會經過同一套 `fd2_drive_to_playable.sh`(含 `ensure_browse`),但 `--attack` 模式
額外會在每個單位的動作裡呼叫 `select_ring()`(`enter_debugger`→讀 `[0x53c57]`→`resume`,
每個單位一次),`--mv 0` 的 rest 路徑理論上也呼叫同一個 `select_ring()`——**兩者的
debugger churn 密度差異本節先前沒有量化過**,只是假設兩者可比。

**今天做的事**:另開一個全新實例(`blind1`),套用同樣的 `fd2_stat_override.py` 預設值,
但**攻擊動作序列全程只用 `key` 這個最底層指令**(純 `xdotool` 按鍵注入,不經過
DOSBox-X debugger,`send_keys()` 本身就不呼叫 `enter_debugger`)——**連 `select_ring()`
的驗證讀值都不用**,盲送「確認→移動鍵→確認→↑→確認→確認」這組跟 `approach_then_act`/
`attack_unit` 結構相同的按鍵,狀態確認全部改用外部螢幕截圖(`import -window root`,
同樣不經過 debugger)。連續跑了 **6 輪**這個序列(比 `vic1` 今天崩潰時經歷的動作量還多——
`vic1` 是在**第 2 回合**的移動確認就死了),**全程存活,遊戲畫面持續正常回應**。

**這不是決定性證據(n=1 vs n=1,同一個方法論教訓這份文件已經講過很多次)**,但方向是
一致的、而且是**今天第一次真正把「debugger 讀值頻率」當成獨立變因來測**,而不是像
C.16 那樣只控制遊戲側的按鍵語意(`--attack` vs `--mv 0`)、放任兩者的 debugger churn
不受控。如果這個方向成立,代表:

1. C.16「movement/destination-confirm 導致崩潰」的因果歸屬可能**部分或完全是混淆的**——
   真正的變因是「這個動作序列需要更多次 `enter_debugger`/`resume` 循環來驗證」,不是
   移動本身。`--attack` 每個單位多一次 `select_ring` 讀值,`--mv 0` 的 `rest_unit` 也呼叫
   `select_ring`,但如果 `--mv 0` 路徑更常在「已經確認過的位置」略過驗證、或迴圈更短、
   或根本很少真的呼叫到 rest 路徑(因為沒有敵人可打就直接跳過整輪),兩者的 debugger
   churn 次數可能本來就不對等——這一步本節**沒有逐行核對**,只是提出這個可能性。
2. 如果之後想真正定案,需要**正規的配對試驗**(比照 `fd2_trial_runner.py` 的方法論):
   固定遊戲側動作語意(例如都用 `--attack`),只切換「攻擊序列裡要不要呼叫
   `select_ring`/`ring_selection` 驗證」這一個變因,N=5 以上、多個獨立全新實例,才能
   把這個新假說跟 C.16 的舊結論放在同一個嚴謹程度上比較——**本節只是提供一個值得追的
   方向,不是取代 C.16**。
3. **如果這個方向被證實**,對「勝利曲量測」這類需要打贏一整場戰鬥的驗證任務是個好消息:
   代表全程用**盲按+外部截圖**(不進 debugger)驅動戰鬥可能是可行的解法,不需要先解出
   `FD2.EXE` 自己的機制才能繼續——本節今天的 6 輪存活就是這個做法的第一次正面訊號。

**給下一輪**:在真正做正規配對試驗之前,不要把這個發現寫成「解決了」——它是一個新的、
值得追、方向一致的線索,跟 §1-§7 的「兩個候選被推翻」一樣重要,但層級不同(§1-§7 是
排除遊戲程式碼裡的候選,本節是質疑「崩潰到底是不是遊戲程式碼的問題」這個更上層的前提)。

### 9. 正規配對試驗第一輪(N=5)——方向一致,但**不到統計顯著**,且盲模式也會死

在 `fd2_battle_autoplay.py` 加了 `--blind` 旗標(只讓 `select_ring()` 跳過
`enter_debugger`/回讀驗證,盲按之後假設生效;工具其餘的 snapshot 驗證不受影響),
用 `fd2_trial_runner.py --trials 5 --workers 3 --cond "blind:--turns 3 --mv 4 --attack
--blind"` 跑第一輪正規試驗,對照 C.16 既有的 `mv4`(未盲、有 debugger 讀值)基準
5/5 全死:

| 條件 | N | 退回 DOS | 存活 |
|---|---:|---:|---:|
| `mv4`(C.16 既有基準,未盲) | 5 | 5 | 0 |
| `blind`(本節新跑) | 5 | 2 | 3 |

Fisher's exact test(`[[5,0],[2,3]]`):**p≈0.167,不到常規顯著門檻(0.05)**。
方向確實一致(盲模式死亡率較低),但**樣本數不足以排除只是運氣**——這正是
`fd2_trial_runner.py` 自己頭檔警告過的「3/5 跟 1/5 看起來有差,實際上分不出來」
那種情況,不能因為方向吻合假說就跳過統計檢定直接採信。

**同樣重要的一點**:`blind` 條件裡**還是有 2/5 死了**(`t29f854`/`td9c80c`,兩者都是
在第 1 幀取樣就已經是 `game_alive()==False`,即幾乎是動作一送出就死,不是撐了幾幀才死)。
這代表**就算完全不進 debugger,遊戲本身仍然有一定機率會退回 DOS**——「debugger 讀值
是唯一成因」這個最強版本的假說,被這 2 筆反例排除。比較站得住腳的版本是**「debugger
讀值可能是一個加成因子,不是唯一因子」**,或者純粹是運氣(N=5 CI 太寬,無法分辨)。

**下一步**:已經另開一輪 N=5、`verified`(未盲)與 `blind` 同時同批跑(避免用歷史基準
可能有的環境漂移),detail 見本節下一小節(若尚未寫入,查 commit 記錄或
`/tmp/fd2_blind_trial_round2.json`)。

### 10. 第二輪(同批 `verified`+`blind` 各 N=5)——**方向消失,§8/§9 的假說被自己的下一輪資料打回原形**

同一批、同時跑(排除歷史基準的環境漂移疑慮),`verified`(未盲,`--turns 3 --mv 4
--attack`)與 `blind`(同參數 +`--blind`)各 N=5:

| 條件 | N | 退回 DOS | 存活 |
|---|---:|---:|---:|
| `verified`(本輪重跑,不是沿用歷史基準) | 5 | 4 | 1 |
| `blind` | 5 | 4 | 1 |

**兩組完全一樣,Fisher's exact test p=1.0。** 兩輪合併(`verified` 9/10、`blind` 6/10):
p≈0.303,一樣遠遠不到顯著門檻。

**誠實結論:§8/§9 提出的「debugger 讀值(至少是 `select_ring` 這一個讀值點)是加成
因子」這個方向性發現,被自己蒐集的第二批資料打回原形。** 第一輪的 2/5 vs 5/5 看起來
像訊號,現在看更像是 N=5 這種小樣本下的運氣——這正是本專案自己在 C.12 記過的同一種
陷阱(小樣本下 3/5 跟 1/5 分不出來),這次是**同一個調查者、同一天,親手示範了一次**。
不是說本輪的假設檢定方法錯了(用 `fd2_trial_runner.py`、同批次配對、Fisher's exact 都
是對的做法),是說**運氣本來就會讓 N=5 的第一輪看起來像有效果**,這正是為什麼要跑第二輪
才能相信,而不是看到第一輪方向對就停。

**跟本節 §8 那個手動 6 輪全部存活的觀察怎麼調和**:`--blind` 旗標**只**讓
`select_ring()` 跳過讀值,主迴圈自己的 `snapshot()`(每個單位動作前後都會呼叫,
`enter_debugger`+讀整個單位陣列)完全沒有跳過——**`--blind` 其實只拿掉了一小部分的
debugger 互動,不是全部**。§8 的手動測試才是真正「全程零 debugger 互動」的版本。
兩者的差距本身就是一個線索:**如果 debugger 互動真的有影響,可能不是 `select_ring`
這個讀值點,而是 `snapshot()` 那種更頻繁、讀更大範圍記憶體的操作**——但這只是重新
提出一個更窄的候選,不是新證據,§8 本身也還只是 n=1,一樣需要正規配對試驗才能信。

**給下一輪**:
1. 不要再把「debugger churn 是加成因子」當成本輪已建立的結論引用——它現在是
   **被自己的第二輪資料推翻**的假說,跟 §6/§7 的兩個候選同一個下場,只是這次
   推翻它的不是新反組譯,是多跑一輪同方法論的資料。
2. 如果真要繼續追這個方向,下一個具體、更窄的候選是 `snapshot()`(不是
   `select_ring()`),需要另一個 `--blind`-類旗標讓主迴圈改用**不讀記憶體、
   純預先寫死的按鍵序列**(放棄「找到最近的活敵人」這種依賴即時讀值的邏輯),
   這比現有 `--blind` 的改動大得多,建議先確認有沒有更值得追的角度再投入。
3. **C.16 的機制依然完全未解**——這是本節從 §1 到現在唯一沒有變過的事實。

### 11. 2026-09-05(續):`fd2_crash_capture.py` 四輪嘗試,無一捕捉到崩潰當下現場——誠實記錄一個 null result,不是「排除」

**背景**:`fd2_crash_capture.py`(見 `SESSION-HANDOFF-2026-09-04.md` C.2/C.3)武裝
`BPINT 21 4C` 後跑真實 `--attack mv4` 回合,目的是在崩潰當下凍結 debugger 現場——這是
一個跟 §1-§10 的統計/靜態方法都不同的第三個角度:**不是問「有沒有關係」或「哪段程式碼
可疑」,是想直接看崩潰那一刻的 EIP/暫存器**。全新實例 `crashcap1`,driven to ch01
browse-cursor layer,四輪嘗試(`--rounds 12/12/12/15`,共約 51 個真實 round-attempt):

| 輪次 | 結果 | 說明 |
|---|---|---|
| 1 | 未捕捉、未崩潰 | 環選擇連續落在 index 2/3(期望 0),`select_ring()` 的安全機制正確拒絕盲按確認——這一輪**幾乎沒有真的執行到攻擊動作**,不構成有效樣本 |
| 2 | 疑似崩潰,經截圖確認**是假警報** | 第 3 輪後 array dump 連續 3 次全 0,觸發 `game_alive()==False` 判定;截圖顯示遊戲其實仍在戰鬥中(索爾 048,移動範圍高亮清晰可見)——這是本專案自己記過的「read failure 不是 negative result」教訓(見 `feedback_read_failure_is_not_a_negative_result`)又發生一次,這次是在新工具上 |
| 3 | 未捕捉、未崩潰 | 12 輪全部乾淨執行(無安全機制阻擋、無讀取異常),BPINT 全程未觸發,遊戲存活到底 |
| 4 | 疑似崩潰,再次**確認是假警報** | 第 14 輪後同一種 array-dump-全0 症狀,截圖再次證實遊戲仍在同一場戰鬥中(索爾 048,同一張地圖畫面)——這是本節第二次遇到同一個假警報樣式,兩次都在畫面高度相似的時刻觸發,值得記錄成一個新的候選觀察(未證實):**這個讀取失敗可能跟畫面上某個特定動畫/捲動狀態相關,不是隨機時機**,但本輪未做進一步隔離 |

**誠實結論**:四輪(~51 個 round-attempt)都沒有捕捉到一次真正的 DOS-exit 崩潰——BPINT
從未觸發,也沒有看到一次真的 `C:\>` 畫面。這**不能**當成「這次 crashcap1 的環境下 C.16
不會發生」的證據(C.16 是機率性的,見 `fd2_trial_runner.py` 的方法論,n=51 次「行動」不
等於 n=51 次獨立的完整戰鬥試驗,且本節多輪根本沒有真的執行到攻擊——見輪1),只能誠實
記錄「這次沒抓到」。**跟 §7.3 呼應**:本節 §1-§10 的靜態+統計調查已經把最有希望的幾條
線索(mode==1 剪枝、0 點地形成本、debugger churn 混淆)都查過並推翻,§7.3 當時就說過
「如果都查不到東西,C.16 的機制搜索需要換一個完全不同的角度,不建議在同一條路徑繼續
深挖」——這次的 `fd2_crash_capture.py` 嘗試换的正是這個新角度(直接捕捉崩潰現場而不是
統計相關性或靜態反組譯),但也沒有拿到新資料。**工具本身沒有問題,可以直接重跑**
(`python tools/fd2_crash_capture.py --instance <name> --rounds 12 --mv 4`,配合
`fd2_stat_override.py` 先套用預設值),下一輪如果要繼續追,建議先確認前幾輪 rest_unit()
在遇到「沒有相鄰敵人」時走的 approach_then_act 路徑是否真的觸發跟 C.16 已知試驗
(`fd2_trial_runner.py --attack`)完全相同的按鍵序列語意——本節沒有逐行核對兩者的動作
序列是否等價,這是一個沒有被排除的變因。

### 12. 2026-09-05(續):對「環選擇未生效」重新診斷——**很可能不是輸入不可靠,是 enable gate 正確擋下了不成立的攻擊**,修正 §11 的隱含假設

**背景**:本節 §11 與同日另一輪 FDTXT_002 speaker-resolution 嘗試,都撞到
`select_ring()` 印出「環選擇是 2/3(期望 0)——按鍵未生效,不盲按確認」,兩輪都直接
記成「跟輸入可靠性問題同一類」就放棄重試。本節重新讀 `select_ring()`/`attack_unit()`
自己的 docstring,發現這個假設**可能是錯的**。

**`attack_unit()` docstring 原文已經寫明**:「`↑` 是絕對設值,但有前提:
`enableFlags[0]==0`(攻擊可用)。射程內沒有候選時 `↑` 完全不生效,`[0x53c57]` 維持
原值」——也就是說,如果呼叫端(`run_one_round()`/`fd2_crash_capture.py`)判定的
「這格是攻擊範圍內」跟遊戲引擎自己的 enable gate 判定不一致(例如呼叫端只算了格子
曼哈頓距離=1,但遊戲要求的是武器射程、朝向、或其他條件),遊戲會**正確地**讓 `↑`
鍵毫無作用,環維持在原本開啟時的預設項(可能是 2 或 3),不是按鍵沒送到。

**這代表本節 §11 记錄的「工具本身沒有問題」這個結論下得太快**:工具的
select_ring() 驗證機制運作正常(它如實回讀並拒絕盲按),但**呼叫端「這格可以攻擊」
的判定條件可能本來就跟遊戲不一致**——如果真是這樣,`fd2_crash_capture.py`/
`fd2_battle_autoplay.py` 大多數輪次可能根本沒有真正測到 C.16 想測的「確認一個算出來
的落點」這條路徑,因為很多輪根本沒有真的按下攻擊。

**本節未完成的部分(誠實記錄,不是新發現的結論)**:沒有時間逐一比對
`adjacent_foe()`/`nearest_foe()`(呼叫端用的判定)跟 `enableFlags[0]` 實際依賴的
條件(武器射程/朝向/距離)是否等價——這只是重新讀 docstring 後的一個**合理推論**,
不是逐位元組核對過的結論。**給下一輪的具體建議**:在下一次呼叫 `select_ring()` 前,
先用 `MEMDUMPBIN` 或既有的單位陣列讀取工具把目標單位的 `enableFlags` 或等效欄位讀出來
(如果 doc13 前面章節已經定位過這個位址),跟呼叫端判定的「可攻擊」比較,一次性
確認兩者是否經常不一致——如果確實常常不一致,修法在呼叫端(改用跟遊戲一致的射程/
朝向判定),不在 `select_ring()` 本身。

**補強(同日,重讀本文件 2026-08-22 段落後):上面的推論其實已經有間接的既有證據支持,
不是全新假說**。本文件「`0x18d8c` 完整反組譯」一節(2026-08-22)已經完整反組譯過
`FUN_000173e7()`——**每次指令環開啟(`0x18d8c` 被呼叫)都會先呼叫它兩次**,邏輯是
「`DAT_00053c57` 從 0 開始線性掃描 `enableFlags[]`,跳過每個 disabled(flag!=0)的
slot,停在第一個 enabled 的 slot」。這代表**環一開啟就已經自動選好了「當下唯一存在的
第一個可用選項」**,不是停在上一次殘留值(那是同一節訂正掉的舊 §1 說法)。呼叫端
按上鍵後讀到 `DAT_00053c57==2` 或 `3`,依這個機制反推:**攻擊(0)與法術(1)在那一刻
對那個單位都是 disabled 的**,不是按鍵沒生效這麼單純。攻擊 disable 的兩個已知成因
(同節 §1 已完整反組譯)是「`0x1b83d` 查無武器 slot」與「`0x14818` 的射程候選掃描
回傳 0」——後者正好呼應 §12 上文的推論:`adjacent_foe()` 只算格子曼哈頓距離,`0x14818`
算的是真正的武器射程/候選,兩者不一致時,呼叫端誤判「這格可以攻擊」但遊戲判定不行,
環因此自動落在下一個真正可用的 slot(2 或 3)。**這仍然是把既有反組譯證據串起來的推論,
沒有這一輪自己新做 live 驗證去核對某一次具體失敗案例的 `enableFlags` 實際值**,但已經
不只是「重新讀 docstring 的合理推論」這麼弱——是跟本文件自己已經反組譯過的初始化邏輯
吻合的具體機制解釋。

### 13. 2026-09-05(續):**§12 的假說 CONFIRMED,並已在 `approach_then_act()` 修好——這才是 C.16 與 FDTXT_002 兩條攻擊線都卡住的真正根因**

§12 上文把「環選擇是 2/3(期望 0)」重新解讀成「enable gate 正確擋下不成立的攻擊」,
但當時明說「沒有這一輪自己新做 live 驗證」。這一節補上那個驗證,並直接修掉根因。

**live 診斷(一次性腳本,用完即刪,不是新增工具)**:寫了一支臨時腳本,對一個真實
instance 做:選一個離最近敵人 9 格、`mv=4` 的單位,呼叫既有的 `approach_then_act()`,
在移動**之後**、開環**之前**重新讀單位陣列跑一次 `adjacent_foe()`。結果
`adjacent_foe()==False`(9 格、`mv=4` 走一次本來就到不了),但函式仍然無條件開了攻擊環,
截圖顯示環面板上「攻擊」「法術」明確是灰階/disabled,「道具」「待機」才是 enabled——
跟 §12 的推論完全吻合:**不是按鍵沒生效,是根本沒有走到能攻擊的格子,遊戲判定正確,
是呼叫端沒檢查移動後是否真的相鄰就硬開攻擊環**。

**真正的 bug 位置**:`approach_then_act()`(`tools/fd2_battle_autoplay.py`)算出朝敵人的
移動向量後,如果距離大於 `mv` 就按比例縮放(`scale = mv/distance`)移動那麼多格,然後
**不驗證縮放後的落點是否真的與任何存活敵人相鄰**,就直接呼叫 `select_ring(RING_ATTACK)`。
縮放走不到相鄰格時,遊戲正確 disable 攻擊,環自動落在下一個 enabled slot(道具=2或
待機=3),`select_ring()` 的「讀值核對,不盲按確認」保護正確拒絕確認——但呼叫端沒有任何
後備動作,單位卡在原地,外層迴圈只能一直印「行動未生效,重試一次」,永遠原地打轉。這正是
**C.16 crash-capture 前 4 輪(§11)與同日 FDTXT_002 live 攻擊嘗試(見
`project_fd2_re_speaker_resolution_start` 記憶檔)共同卡住的同一個根因**——很可能兩邊
大部分回合根本沒有真的打出過一次攻擊。

**修法**:`approach_then_act()` 新增移動後、開環前的重新快照 + `adjacent_foe()` 再檢查
(`blind=True` 時略過,維持原行為);若確認移動後仍不相鄰,改選 `RING_REST`(待機)
乾淨地結束這個單位的行動,不再嘗試攻擊;若 `select_ring(RING_REST)` 本身也失敗(理論上
待機應該永遠 enabled),才退回單純 `cancel`。新增 `selector`/`count` 參數把 snapshot
用的記憶體位址/單位數傳進來(呼叫端本來就有這兩個值,不必重新硬編碼)。同步更新
`tools/fd2_crash_capture.py` 的呼叫點傳入這兩個新參數。

**修的過程中自己引入又修掉的一個錯**:第一版寫 `_, post_units = snapshot(...)` 直接把
`snapshot()` 回傳的 `[{"cursor":...}] + units` 整包當成單位清單迭代,少切掉開頭的
cursor dict,導致真實測試時 `KeyError: 'idx'`。改成 `post_snap` 並 `post_snap[1:]`
後修好。

**live 驗證(負向案例/回歸測試,已完成)**:`fd2_battle_autoplay.py --instance ringtest1
--turns 1 --attack --mv 4` 重跑,4 個單位全部乾淨解析為「改走待機,不嘗試攻擊」,
`我方未行動 0`——不再有先前那種永遠「行動未生效,重試一次」的卡死迴圈。

**尚未完成、明確不宣稱已驗證的部分**:同一輪嘗試接一個多回合測試,想確認「真的走到相鄰格
時,攻擊仍然正常打得出去」(正向案例),但測試中途 instance 自己的 `--keepalive 1200`
逾時到期(`status` 確認是逾時,不是遊戲崩潰),測試被打斷,只留下負向分支又正確觸發一次
的結果(idx1/idx3 都乾淨落到待機分支)。**正向案例(相鄰時攻擊確實成功)這一輪沒有驗證
到**,下一輪需要一個 keepalive 開更長或提早重開的 instance 補做。

**對 C.16/FDTXT_002 的意義**:修好之後,`fd2_crash_capture.py`/
`fd2_speaker_capture.py --resolve-todo`(需要真實戰鬥觸發對話)兩條線之後的嘗試應該能
真的打出攻擊、產生真實傷害/死亡事件,而不是像過去那樣大部分回合卡在無效重試——C.16 本身
的崩潰機制依然未解,但至少之後的試驗輪次資料會更乾淨、更有意義。

### 14. 2026-09-05(續二):補做正向案例——**新開一個乾淨 instance 才發現雙重驅動污染,乾淨重跑後暴露出 §13 修法本身有第二個未解問題:`RING_REST` 的回退假設跟本文件自己早就記過的證據矛盾**

**環境問題,先記一筆**:這一輪一開始想補 §13 留下的正向案例測試,launch 了新
instance(`ringtest2`)但背景呼叫過早結束(`LAUNCHER` 欄位變 `no`,但 `tmux`/`Xvfb`
仍活著)——teardown 一個不相關的舊 stale instance(`mv1`)的動作幾乎同時發生,兩者
共用同一個 display 編號 `127.0.0.1:199`,teardown 之後 `ringtest2` 立刻 `XIO: fatal
IO error` 死掉(螢幕全黑、`tmux capture-pane` 讀到 X server fatal 訊息)。懷疑是
display 編號分配沒有正確處理併發 teardown/launch 的碰撞,但沒有進一步深挖——教訓是
**不要在另一個 instance 還在啟動/存活時對別的 instance 做 teardown**,即使兩者看起來
無關。重開第三個 instance(`rt3`)、期間**不做任何其他 instance 操作**,順利跑到
title screen。

**第二個環境問題**:透過 Bash 工具的 `run_in_background` 呼叫
`fd2_drive_to_playable.sh`,`| tail -N` 這個常見的檢查習慣讓輸出在整條 pipeline
結束前完全不會落地(`tail` 沒有 `-f` 就是全讀完才印),誤判成「background 卡死沒
進度」,因而**手動又開了第二個 foreground 呼叫跑同一支 driver script,對同一個
instance 送出重複的按鍵序列**。兩邊最後都跑完(背景那個 200 次確認後放棄「無法確定
層級」,前景那個 180 次確認後成功判定「已確定在瀏覽游標層」),截圖確認畫面是合理的
ch01 戰鬥瀏覽游標畫面,沒有明顯損壞——但**這是僥倖,不是可信賴的方法**;下次要嘛只用
一個 driver 呼叫,要嘛先用 `ps`/`status` 確認前一個真的結束再開新的。

**正向案例測試的真實結果:部分成功,但暴露出新問題,不能宣稱「攻擊完全修好」**。
`fd2_battle_autoplay.py --instance rt3 --turns 3 --attack --mv 8`:
- idx0 移動後 `adjacent_foe()==False`,§13 修法正確判定改走 `RING_REST` 回退分支——
  但 `select_ring(RING_REST, "down")` 這次回報「環選擇是 2(期望 3)」,**回退分支本身
  的環選擇也失敗了**,`select_ring()` 正確拒絕盲按確認,退回 `cancel`。idx0/idx2 兩個
  單位都卡在「行動未生效,重試一次」——跟 §13 修好之前同一種卡死症狀,只是觸發點從
  「攻擊」換成了「回退用的待機」。
- 截圖確認遊戲仍活著、仍在正常戰鬥中(不是崩潰),只是 debugger array dump 那三次
  讀取真的全 0(跟本文件 §11、`feedback_read_failure_is_not_a_negative_result` 是
  同一種截圖前不要輕信讀值的已知模式,截圖確認後排除崩潰假說)。

**更關鍵的問題:回頭核對本文件自己已經記過的證據,`RING_REST`(index 3)這個回退選項
本身的語意可能就不成立**。本文件「⚠ 與 §1 不符的一點」一節(2026-08-22,line 1705
起)已經反組譯證實:slot `[3]`(↓)呼叫的是 `0x13fd4`(HP 不滿才回血)+`0x190ac`
(格子互動/寶物檢查),**不是「待機」**,而且實測「滿血站空地」的情況下確認 slot 3
之後 **Acted 沒有被設起來**——該節結論明講:「`[3]`=『待機』應視為假說,不是已證
實」。也就是說 §13 把 `RING_REST` 當成「安全的回退動作,能讓單位乾淨結束行動」這個
假設,**跟本文件自己 13 天前就已經記錄、還沒被推翻的證據直接衝突**——如果單位滿血且
腳下沒有寶物,confirm slot 3 很可能跟 confirm slot 2(道具,如果沒帶可用道具)一樣,
根本不會設 Acted,外層迴圈仍然會卡住重試,只是卡住的原因從「攻擊 disable」換成
「rest-heal 條件不成立」。這是寫 §13 修法時沒有先查這份文件自己既有內容犯的錯,呼應
[[feedback_check_existing_evidence_before_disasm]]。

**誠實現況,不宣稱已解決**:
1. §13 的核心修正(移動後重新檢查相鄰、不再對著不相鄰目標盲開攻擊環)方向仍然正確,
   且靜態程式碼讀起來 `still_adjacent==True` 分支跟修法之前完全相同,理論上沒有改到
   已知會動作的路徑。
2. 但 `RING_REST` 回退分支本身**不能視為已驗證能可靠結束單位行動**——這一輪的
   live 測試顯示連環選擇都可能失敗,而且就算選中了,語意上是否真的設 Acted 依然是
   本文件自己標記的未證實假說。
3. **「正向案例(真的相鄰時攻擊成功)」這一輪依然沒有取得乾淨驗證**——三個雙重驅動+
   環境問題疊加,沒有一輪測試乾淨跑完到能看到一次成功攻擊。
4. 下一輪建議:(a) 先用單一 instance、不觸碰其他 instance,一次跑到底;(b) 針對
   `RING_REST` 回退分支,先做小範圍實測回答「index 3 在各種 HP/腳下地形組合下,
   confirm 之後 Acted 到底會不會被設起來」,如果不會,§13 的回退邏輯需要換一個真正
   可靠的「結束單位行動」動作(可能得回頭找 `0x117e7`/`0x13512` 直接呼叫路徑,而不是
   透過 UI 環選擇),而不是繼續假設 `RING_REST` 安全。

### 15. 2026-09-05(續三):**純靜態複核回答了§14的問題——`RING_REST` confirm 之後其實有呼叫 `SetActed`,§14/2026-08-22舊測試「Acted沒被設」的結論很可能是誤判,不是遊戲行為**

用 `ghidra_batch_probe.py` 對 `0x18d8c` 做完整 decompile(不是只看 switch 本體,是連
switch 外層一起看),四個 case 分支之後的完整程式碼如下:

```c
else {                                   // case 3(↓,RING_REST)
    if (param_3 == 0) {
        FUN_00013fd4();                  // 休息回復(HP 不滿才有效)
    }
    FUN_000190ac();                      // 格子互動/寶物檢查
    FUN_00013512();                      // ← SetActed,**無條件呼叫**,不在任何if裡面
}
return 1;
```

`FUN_00013512()` 的本體(這輪也重新 decompile 確認)是:

```c
void __stdcall FUN_00013512(int param_1)
{
    byte *pbVar1;
    pbVar1 = (byte *)(DAT_00053a45 + 5 + param_1 * 0x50);
    *pbVar1 = *pbVar1 | 0x80;            // 設 Acted bit(+5 bit7),跟 §「0x13512=SetActed」既有結論一致
}
```

`call_scan` 找到 `0x18d8c` 內對 `0x13512` 的三個呼叫點:`0x18ff3`(case 0 攻擊)、
`0x19021`(case 1 法術)、`0x19094`(case 3 待機),**case 2(道具)完全沒有呼叫**。三個
呼叫點在 decompile 裡都顯示成 `FUN_00013512();`(不帶參數),即使函式本體明確要求
一個 `param_1`——這是 Ghidra decompiler 對這個呼叫點參數偵測失敗的常見現象,不代表
runtime 真的沒傳參數。**用結構對稱性可以推翻「case 3 沒設 Acted」的疑慮**:case 0(攻擊)
的呼叫點是完全相同的裸 `FUN_00013512();` 寫法,而攻擊確實會正確設 Acted(本專案幾週
來大量 live 戰鬥自動化都證實這件事)——如果是同一個 decompile 顯示怪異,三個呼叫點理應
一致隱藏同一個真實有效的參數,不會只有 case 3 那個是「真的沒傳參數」的例外。

**與 §「⚠ 與 §1 不符的一點」(2026-08-22)舊結論的直接衝突,如何理解**:舊結論是「按 ↓
確認後,索爾的 `+5` 仍為 `0x00`,重讀單位陣列兩次皆然」。這輪靜態證據強烈指向 case 3
本身確實會呼叫 `SetActed`,所以舊結論更可能的解釋是**該次 live 測試在別的地方出了差錯**
(例如當時的按鍵/讀值時機、或選錯了單位索引),而不是遊戲邏輯真的沒有把 Acted 設起來。
**這不是撤回 2026-08-22 的觀察本身(那次讀值可能真的讀到 0x00),而是修正它的因果推論**
——「讀到 0x00」跟「case 3 的 code path 不會設 Acted」是兩件事,這輪的完整 decompile
顯示後者不成立。

**回頭修正 §14 自己的推論**:§14 把「`select_ring(RING_REST)` 這次選到 index 2 不是 3」
跟「就算選中 3,Acted 也未必被設」兩個問題混在一起討論,並引用了 2026-08-22 舊結論支持
後者的疑慮。這輪的複核顯示**後者的疑慮本身理由不足**——真正該追的只有前者(§14 的
live 測試裡,環選擇本身就沒有成功landing在 3,所以從來沒有真的確認過 case 3,
`FUN_00013512()` 那次根本沒被呼叫到,不是被呼叫了但沒生效)。

**現況(誠實邊界)**:
1. **靜態證據強:`RING_REST` confirm 之後應該會設 Acted**,跟攻擊/法術同一套機制,
   結構對稱性支持這個結論,但**這輪沒有做新的 live 測試去正面確認**(需要先解決前述
   ring 選擇能不能穩定landing在3的問題,才有辦法乾淨測到「選中3之後confirm」這一步)。
2. **`approach_then_act()` 的 REST 回退分支的真正待解問題,收斂成單一個**:
   `select_ring(RING_REST, "down")` 為什麼有時候(如§14的live測試)選不到index 3——
   這是輸入/UI導覽問題,不是「REST本身沒用」的遊戲邏輯問題。下一輪如果要繼續這條線,
   應該直接做「開環後,反覆按↓直到讀到`[0x53c57]==3`,不限一次按鍵」這種更寬容的
   selection邏輯,而不是懷疑REST本身的語意。

### 16. 2026-09-05(續四):針對上面第2點,`select_ring()` 加了重試——**已實作,這輪沒有live驗證**

把上一節的建議直接實作進 `tools/fd2_battle_autoplay.py` 的 `select_ring()`:新增
`retries`參數(預設3次),同一個方向鍵最多重按3次,每次都重新回讀`[0x53c57]`確認;
只要中途對過一次就回`True`。**不會**因為重試次數用完就放寬驗證標準——3次都不符,
一樣老實印出失敗訊息、回`False`,呼叫端仍要自己決定退路,不會在這裡改成盲按確認。
這個retry精神跟`0x18d8c`本體處理按鍵輸入自己也是`do {...} while(iVar1==0)`(讀不到
有效輸入就重讀)一致,不是引入新的容錯哲學。

`fd2_crash_capture.py`不需要改動(它透過`approach_then_act()`間接呼叫，簽章沒變、
新參數有預設值)。語法與既有90項unittest全數通過(`python3 -m unittest discover -s
tools -p "test_*.py"`)。**誠實邊界:這輪只做了語法/單元測試層級的驗證，沒有另開
live instance 實際測試這個retry是否真的解決§14看到的選擇失敗**——下一輪若要驗證，
直接用§14同樣的repro(單位離最近敵人超過mv、mv不夠走到相鄰)重跑`fd2_battle_autoplay.py
--attack`，觀察是否還會印出「重按X次仍未生效」。

### 17. 2026-09-05(續五):**§16 retry補丁上線後第一次live測試,重跑就撞到DOS-exit——新資料點,不是結論**

按§16自己列的驗證步驟做:單一乾淨instance(`rv2`,全程沒碰過其他instance)、乾淨跑到
瀏覽游標層(第11批,110次確認,截圖確認畫面正常)、`fd2_battle_autoplay.py --instance
rv2 --turns 2 --attack`(用預設`--mv 30`,不是C.16原本聚焦的`--mv 4`)。

**觀察到的第一個新現象**:idx3 移動後`adjacent_foe()`判定不相鄰,改走REST回退分支,
但`select_ring(RING_REST,"down")`這次是**環自動預設落在index 0(攻擊)**,連續按3次
「下」讀回來全部還是0,3次都沒有移動到3——跟§14那次「落在2,按下沒變」是不同的
起始點,但同樣「按下沒有生效」。這跟doc13/§15剛建立的「slot3結構上永不gate-disable,
按鍵應該是絕對設值」的結論不吻合,值得懷疑:**如果ring auto-select已經停在slot0(攻擊)
enabled的狀態,那`adjacent_foe()`判定的「不相鄰」可能是我們自己這支工具的Manhattan
距離簡化算法錯誤,遊戲的真實射程判定(`0x14818`)其實認為可以攻擊**——這正是doc13
§12提過的舊已知落差,這次不是新發現,但這次是第一次看到它可能導致retry補丁三次
按鍵都沒用的具體案例,而不是純粹的輸入時序問題。

**觀察到的第二個現象,嚴重得多**:3次retry用盡、`select_ring()`老實回`False`、
呼叫端`cancel`退出後,接著3個單位(idx3/idx1/idx2)都印出「行動未生效,重試一次」,
然後**array dump連續3次讀取失敗(全0)**——這次沒有像§11/§14那樣是誤報:**截圖直接
確認畫面是`C:\>`,遊戲真的已經退回DOS**。這是本輪(2026-09-05)第一次在單一次
`fd2_battle_autoplay.py`跑批裡直接撞到C.16同款的DOS-exit crash,而且剛好發生在
本輪自己新增的retry邏輯執行路徑之後。

**誠實地說,這只是一個新的資料點,不是「retry補丁導致崩潰」的證明**:
1. C.16 本身是機率性的(§7-§10 已有多輪正規配對試驗結論),原本就會在各種攻擊
   序列下偶發崩潰,不需要retry補丁參與也一樣會發生——這次崩潰有沒有跟retry邏輯
   因果相關,不能只憑「發生在retry之後」這一個時間先後關係下結論。
2. 這次沒有像`fd2_crash_capture.py`那樣事先武裝`BPINT 21 4C`,崩潰當下的debugger
   狀態(EIP等)完全沒有捕捉到,**沒有辦法定位崩潰發生在哪一行**,自然也不能判斷
   跟retry迴圈是否有關。
3. §16 的 retry 迴圈確實比修法之前多送出最多 2 次額外按鍵(3次嘗試 vs 原本1次)——
   如果 C.16 真的跟按鍵序列/時序有關(§7-§10 已經大幅弱化但沒有完全排除這個方向),
   retry補丁客觀上確實改變了輸入時序,是一個合理該追查的新變因,不能忽略。

**下一輪如果要追這條線,正確做法是**:用`fd2_crash_capture.py`(已經武裝
`BPINT 21 4C`)搭配這次的repro條件(同樣的地圖/單位配置、`--mv 30`)重跑多輪,
才能拿到崩潰當下的debugger現場,分辨是retry迴圈本身的問題還是C.16既有機制的
另一次偶發重現。在有更多資料之前,§16 的retry補丁**不撤回**(它的邏輯本身合理、
跟既有90項unittest相容),但**不宣稱已驗證安全**——下次有人要跑大量`--attack`
批次測試前,应该先意識到這個新資料點。

### 18. 2026-09-05(續六):照§17自己的建議做了武裝斷點的複現嘗試——**8輪同一個repro全部存活,沒有重現崩潰,但意外抓到retry補丁旁邊一個真正的迴圈bug**

新開一個乾淨instance(`cc1`),同樣單一instance、不碰其他instance,乾淨跑到瀏覽游標層
(第11批、110次確認)。用`fd2_crash_capture.py --instance cc1 --rounds 8 --mv 30`
(跟§17同樣的`--mv 30`,而且這支工具本來就會先`BPINT 21 4C`才開始跑)。

**結果:8輪全部存活,`BPINT`從未觸發,回傳碼3(「這次沒有重現崩潰」)。**
不是誤報——收工前有截圖確認遊戲仍在正常戰鬥畫面,不是殘留值。

**但8輪的log本身暴露了一個新問題,不是原本要找的崩潰**:8輪內容**逐字重複**——
每一輪都是「idx1移動後不相鄰→改走REST→環選擇3次都落在0→重按3次仍未生效→不盲按
確認」,連續8次一模一樣。這代表`fd2_crash_capture.py`的`run_one_round()`(每輪重新
挑「最近的未行動單位」)每次都挑回同一個idx1,而idx1的行動因為§16的retry補丁exhausted
之後,從未真正完成(沒有進到`select_ring()`回`True`的分支,也沒有觸發`cancel`以外的
任何流程),所以`+5`bit7(Acted)一直沒被設起來,下一輪重新掃描時idx1還是「未行動」,
於是又被選中——**陷入單一單位的無窮重試迴圈,永遠不會換到別的單位或推進戰鬥狀態**。
這解釋了為什麼8輪下來沒有崩潰:遊戲畫面幾乎沒有真正的新輸入序列在跑,只是同一組
按鍵在同一個情境下重複,不是探索新狀態。

**這對§17的問題本身的回答是:8/8存活,跟§17的1/1崩潰放在一起看,比較支持「§17的
崩潰是C.16既有機制的一次偶發重現,不是retry補丁本身系統性導致的」——如果retry
補丁本身穩定會觸發崩潰,不太可能連續8輪一模一樣的輸入序列都存活。但這不是嚴謹的
統計結論(n=8同一情境不等於8個獨立樣本,前面§9-§10已經有過如何正確做配對試驗的
教訓),只能算是弱的、方向性的支持,不是排除。**

**新發現、需要記錄的獨立問題**:`approach_then_act()`目前的邏輯是「不相鄰就試REST,
REST選擇失敗就cancel退出」——但退出之後沒有任何「強制標記已處理/跳過這個單位」的
機制,導致外層(不管是`fd2_battle_autoplay.py`的`main()`還是`fd2_crash_capture.py`
的`run_one_round()`)在下一輪重新選擇時還是會選中同一個永遠卡住的單位。這是一個
跟§16/§17不同的、獨立的bug,**這輪沒有修**——修法上需要想清楚「跳過」在遊戲語意上
是什麼意思(直接不管這個單位,留給玩家/下一次真人輸入處理?還是要想辦法找到一個
真正能結束它行動的動作?),不是機械地加一個計數器就了事,留給下一輪。

### 19. 2026-09-05(續七):**改成「一律先試攻擊,交給遊戲自己的enable gate判斷」——邏輯修好了,live測試結果好壞參半,不宣稱完全解決**

針對§18發現的根因,把`approach_then_act()`重構:**不再用`adjacent_foe()`的結果決定
要不要嘗試攻擊**,一律先呼叫`select_ring(RING_ATTACK)`,只有遊戲自己的enable gate
也判定不能攻擊(`select_ring`回`False`)時才落到REST分支。理由:`adjacent_foe()`
只是格子曼哈頓距離的簡化近似,不是`0x14818`的真實射程判定(doc13 §12已指出過這個
落差),§17/§18的live測試證實了這個落差真的會導致誤判——`adjacent_foe()`說不相鄰,
但環自動落在攻擊(enabled)。改成信任遊戲自己的gate,不是我們自己的距離計算。

**Live驗證(單一乾淨instance `cc2`,同樣先跑`fd2_drive_to_playable.sh`到瀏覽游標層,
再用`fd2_crash_capture.py --rounds 8 --mv 30`跑)**:

- **正向訊號**:第1輪log顯示idx1(距最近敵人超過mv、adjacent_foe()判不相鄰)這次
  **沒有落到REST分支,直接照樣先試攻擊,而且`select_ring(RING_ATTACK)`成功了**
  (沒有印出「遊戲自己的enable gate判定不能攻擊」),流程正確走到「執行→目標選擇→
  確認目標」的兩次confirm。跟§17/§18那種「連續8輪同一個單位卡在REST選擇失敗」的
  症狀相比,這是明確的行為改善——不再無條件跳過攻擊。
- **後續無法完全確認**:round1之後的array dump又是連續3次全0(這次截圖確認**不是
  崩潰**,遊戲仍在正常畫面,是這個專案已知的「動畫/選單過場時讀值不穩定」模式)。
  手動額外補送2次confirm(2.5s、3.5s wait)後,直接讀單位陣列確認:**idx1的acted
  仍是0,沒有任何敵方單位HP下降**——攻擊動作看起來卡在目標選擇畫面沒有真正執行完,
  截圖看起來像瀏覽游標畫面(卡在某個路人盜賊单位附近的方框游標),不確定是不是真的
  停在攻擊的target-select子畫面,還是已經跳出攻擊流程回到別的狀態。

**誠實結論**:這次的重構**解決了「不相鄰就整個跳過攻擊」這個已確認的邏輯錯誤**,
`select_ring(RING_ATTACK)`本身確實在原本會被錯誤攔下的情境成功了——這是靜態分析
(§15)加上這次live複現共同支持的結論。**但完整的「打出去→真的造成傷害/結束單位
行動」這條鏈,這一輪仍然沒有乾淨驗證到底**——目標選擇之後的畫面卡住的原因待查,
可能是額外confirm的時間點/次數不對,也可能是目標選擇這一段本身還有別的問題。
**不宣稱「攻擊完全能用」,只宣稱「不會再錯誤跳過攻擊」**。下一輪如果要繼續,應該
在`attack_unit()`/`approach_then_act()`確認目標之後,立刻(不要等待其他輪次)重讀
單位陣列確認acted跟敵方HP,把整個攻擊序列的每一步都插入即時回讀,而不是像這次事後
用手動按鍵去補測。

### 20. 2026-09-05(續八):**加了即時回讀之後,問題精確定位到「環開得成功,但目標選擇/執行沒有真正完成」——而且過程中又撞到一次DOS-exit,這次意義不一樣**

照§19最後的建議,在`approach_then_act()`攻擊分支的兩次confirm之後**立刻**加一段回讀
(不等下一輪、不用手動事後補按):讀`me`的acted位元(`+5 & 0x80`)跟所有敵方單位HP
是否比攻擊前(移動後那次快照)低,兩者都沒有才印「攻擊確認**未生效**」。

**新開一個乾淨instance(`cc3`),單一instance、不碰其他instance,乾淨跑到瀏覽游標層,
`fd2_battle_autoplay.py --instance cc3 --turns 1 --attack`(預設`--mv 30`)。結果**:

- **idx3**:`select_ring(RING_ATTACK)`成功(沒有印「enable gate判定不能攻擊」),
  兩次confirm送出,**立即回讀確認「攻擊確認未生效」**——acted沒設、沒有敵方HP下降。
- **idx1**:這次反過來,`select_ring(RING_ATTACK,"up")`連續3次都卡在index 3
  (REST),從未移到0——跟§17/§18看到的「REST選不到3」正好相反的失敗方向(這次是
  「ATTACK選不到0」)。落到REST分支後(這次沒加回讀,還是舊行為)一樣「行動未生效」。
- **idx2**:跟idx3一樣的模式——環開成功、兩次confirm送出、立即回讀確認「未生效」。
- 之後又是array dump連續3次全0,**這次截圖確認是真的DOS-exit crash**(`C:\>`)。

**這一輪把問題精確定位了**:2/2確認案例(idx3、idx2)都是「`select_ring(RING_ATTACK)`
本身成功(環真的開在攻擊、遊戲的enable gate也同意)、兩次confirm也送出去了,但攻擊
序列最終沒有造成任何可觀測的效果(acted未設、HP未變)」——**問題已經不在環選擇這一層
(§16/§19的修法已經解決那一層),而是在「確認目標」之後的某個環節**:可能是目標
選擇畫面需要方向鍵才能選中候選(不是自動鎖定唯一目標)、也可能是`confirm`的等待
時間(3.0s)不夠讓畫面轉場完成、也可能是`confirm`按鍵在那個畫面情境下根本沒被
遊戲接收。這輪沒有進一步分辨是哪一種,需要在兩次confirm之間插入截圖才能看清楚
目標選擇畫面實際長什麼樣。

**這次的DOS-exit crash,意義比§17/§18那次更值得重視**:§18用`fd2_crash_capture.py`
連跑8輪、8輪log逐字相同、8輪都存活,當時把這個結果解讀為「弱支持retry補丁不是
崩潰系統性成因」。**現在回頭看,那個解讀站不住腳**——8輪log逐字相同代表8輪其實
卡在同一個單位、同一個失敗點,根本沒有真正探索到不同的遊戲狀態/輸入序列,是本專案
自己已經記過的「degenerate sample」陷阱([[feedback_degenerate_verification_sample]]
的同一類問題,不是新教訓,是這次才意識到自己剛好又犯了一次)——「8輪都存活」這個
觀察對「這條code path安不安全」幾乎沒有鑑別力,因為8輪根本沒有真的跑出8種不同的
執行內容。**這一輪(`cc3`)因為§19的攻擊優先修法生效,才真的讓迴圈跑過3個不同單位、
送出3組不同的按鍵序列**,然後崩潰了——這比§18那8輪雷同的log更接近「真的在測試
C.16」,雖然還是n=1不是嚴謹樣本,但不能再引用§18的「8/8存活」當作安全證據。

**誠實現況(累積到這裡)**:
1. `select_ring()`的重試(§16)跟攻擊優先判定(§19)這兩個修法,靜態邏輯跟既有
   90項unittest都沒問題,而且live測試證實**確實讓環選擇/攻擊嘗試比修法前更常成功
   走到「確認目標」這一步**——這是真實改善,不是空話。
2. 但「確認目標」之後的完整攻擊生效鏈,到目前為止**連續3輪live測試(§17、§19這輪
   的idx3/idx2)都沒有看到成功案例**,問題已經收斂到這個更窄的範圍,下一輪應該
   直接針對這裡插入截圖分段診斷,而不是再測整個`approach_then_act()`。
3. C.16 DOS-exit崩潰在這一輪又出現一次,累積到本文件記錄過的已經有多次獨立重現
   ——機制仍未解,但§18對「8/8存活」的樂觀解讀已經撤回,不要再引用。

### 21. 2026-09-05(續九):照§20的建議插入分段截圖——**看到了「目標選擇」畫面本身,但這輪自己的手動腳本有問題,結果不能當成乾淨結論**

新開一個乾淨instance(`ts1`),寫一支一次性診斷腳本(用完即刪,不是新增工具)手動
重現`approach_then_act()`的每一步,在兩次confirm之間插入截圖。

**看到的畫面**:兩次confirm之間的截圖顯示一個**方框游標**,位置在某個路人盜賊單位
旁邊的空地上,畫面左下角資訊卡顯示地形(不是單位卡)。按一次「左」之後,游標移到
盜賊單位頭上,**同時畫面上出現一片淡化的十字形高亮區域**(很像移動範圍顯示)。再按
一次確認後,高亮消失,游標留在原地,但**讀單位陣列確認完全沒有變化**(沒有HP下降、
沒有acted設起來)。

**這輪的問題:腳本本身很可能有bug,不能信任這個結果代表「攻擊真的沒用」**。整個
序列跑完後,直接讀單位陣列發現**idx1(理論上這輪操作的單位)座標完全沒變**
(`(10,15)`,跟操作前一模一樣)——照腳本邏輯應該先把它移動4格再confirm,如果移動
真的生效,座標不可能不變。這代表**從一開始「移動」這一步可能就沒有真的作用在idx1
身上**,後面看到的「方框游標」跟「移動範圍高亮」很可能是別的東西(可能是瀏覽游標
本身移到別的位置,不是攻擊目標選擇)——**這輪的畫面觀察是真實的,但無法確定它是不是
attack target-select 畫面**,不能拿來確認或推翻「攻擊執行鏈哪裡卡住」這個問題。

**誠實現況**:§20 定位出的問題(環開成功、兩次confirm送出、但沒有可觀測效果)依然
**沒有被這輪解開**,只是多看到了一個可能相關、也可能無關的畫面。**下一輪如果要繼續
這條線,必須先確認`move_cursor()`真的把游標移到了目標單位身上、且第一次`confirm`
真的進入了該單位的行動選單**——每一步都要用截圖或debugger回讀個別驗證,不能像這輪
一樣連續送出一串按鍵才回頭一次性檢查結果。這是本輪在效益遞減的訊號下主動停止繼續
猜測的決定,不是把問題解開了。

### 22. 2026-09-05(續十):**照§21的建議逐步截圖,終於找到真正根因——超出真實移動力的落點,遊戲悄悄取消單位選擇退回自由瀏覽,不是停在任何選單/環畫面**

新開一個乾淨instance(`ts2`),這次**每按一個鍵就截一次圖**,不批次送按鍵。

**逐步過程**:
1. 初始瀏覽游標剛好在idx1(悠妮)身上,資訊卡顯示單位卡(portrait 028)。
2. 按一次確認:出現「悠妮 LV.01 HP028/MP008」狀態卡,**同時地圖出現淡化十字形
   移動範圍高亮**——這是正常的「單位已選,進入移動選格」畫面,跟預期一致。
3. 按方向鍵(左):游標在高亮範圍內移動,資訊卡正確顯示地形加成(「A-05 D+10」,
   森林地形)——移動選格運作正常。
4. **再連續按3次左、4次down(模擬`--mv 30`算出來的落點,累計移動7格)**:
   截圖顯示**移動範圍高亮消失了**,游標停在一個沒有高亮的空地格,資訊卡變回
   純地形卡——這代表游標已經走出了這個單位**真實能移動的範圍**(不是我們外部
   給的`--mv 30`那個參數代表的範圍)。
5. **在這個超出範圍的格子按確認**:畫面上完全沒有任何反應(不是錯誤訊息、
   不是彈回移動選格、也沒有開任何環)。截圖看起來就是原本第0步的瀏覽畫面。
6. **關鍵驗證**:直接讀debugger確認——游標座標變成`(7,17)`(不是悠妮所在的
   `(10,15)`,也不是我們剛剛按確認的那個超範圍格子),悠妮(idx1)本身
   座標**完全沒變、acted仍是0**。這證明**確認一個超出真實移動力的落點,
   遊戲直接悄悄取消整個單位選擇、退回自由瀏覽游標**,不是停在移動選格畫面
   等你重選,也不是進入任何攻擊/環相關的畫面。

**這就是§17-§21一連串「環選對了、確認也送了,但完全沒有效果」的真正根因**:舊版
`approach_then_act()`用`scale = mv / distance`把落點縮放到**我們自己傳入的
`--mv`參數**(這一整輪測試常用`--mv 30`,遠超過大多數單位真實的移動力)以內,
但這個縮放後的落點依然可能超出**遊戲真正認定的移動範圍**——確認這種落點會讓
遊戲悄悄取消選擇退回自由瀏覽,而舊版完全沒檢查這件事,直接往下呼叫
`select_ring(RING_ATTACK)`,對著**已經不知道對應哪個單位的自由瀏覽狀態**送出
方向鍵跟確認鍵。讀到的`[0x53c57]`是殘留值或恰好路過的別的東西,不是這個單位的
攻擊結果——這也解釋了為什麼§17/§19/§20 login裡「環選擇是X(期望Y)」的X值每次
都不一樣、看似隨機。

**已經修的地方**(`tools/fd2_battle_autoplay.py`的`approach_then_act()`):
在「確認落點」之後,若本來就打算移動(`dx`或`dy`非0)但移動後座標跟移動前完全
相同,判定為「落點被拒絕、單位選擇已取消」,直接印出診斷訊息並`return`,**不再
往下呼叫`select_ring()`**——避免對自由瀏覽狀態亂送按鍵。這個檢查本身很輕量
(用既有的`post_snap`回讀,沒有新增額外的debugger呼叫)。

**還沒做、誠實列出**:
1. 這一輪的診斷用的是手動逐步腳本,**修法本身這輪還沒有重新跑一次完整的
   live測試驗證**(語法/90項unittest都過,但沒有另開instance測`--mv`設小一點
   的正常情境下,原本能動的攻擊還會不會正常動)。
2. 沒有查出這個單位(悠妮)真實的移動力數值是多少——只知道7格(3左4down)超出
   範圍、1格(左)在範圍內,真實邊界在1到7之間,沒有進一步二分定位。
3. 舊有**所有**用`--mv 30`(或任何超過真實移動力的值)跑過的live測試結果
   (§13正向案例測試除外,那次mv=8且確認過移動軌跡合理;§17/§19/§20/§21全部
   用`--mv 30`)都應該被**重新解讀**:那些「攻擊沒生效」的觀察,很可能根本不是
   「攻擊環/目標選擇有問題」,而是「移動落點一開始就超出範圍,根本沒有真的進入
   任何環」。**不是舊觀察本身是假的,是舊觀察對「哪一步壞掉」的歸因大概率是錯的**。
4. C.16的崩潰重現(§17、§19、§20)是不是也跟這個「confirm在自由瀏覽狀態下對
   錯誤的單位/情境送出」有關,還沒有查——這是一個新的、值得追的候選機制,
   比之前查過的候選(mode=1剪枝、0點地形tier、debugger churn)都更貼近實測現象
   (都涉及對「已經不在原本假設的畫面」送出按鍵),但這輪沒有時間展開驗證。

### 23. 2026-09-06:**用真實(小)mv重新測§22的修法——乾淨、0卡死、0崩潰,而且看到戰鬥真的有傷害交換**

補上§22自己列的「還沒做」第1項:新開一個乾淨instance(`ts3`),這次用
`--mv 4`(貼近本專案C.16測試一貫用的真實mv量級,不是這幾輪一直用的`--mv 30`)
跑`fd2_battle_autoplay.py --instance ts3 --turns 1 --attack`。

**結果乾淨**:4個單位(idx1/idx2/idx0/idx3)這回合全部因為距離太遠(mv=4確實
夠不到任何敵人相鄰格),`adjacent_foe()`判不相鄰後仍照樣先試攻擊(§19邏輯),
遊戲的enable gate正確判定不能攻擊(環穩定落在index 2,不是之前mv=30那幾輪
看到的隨機值),乾淨改走待機。**`回合1:我方未行動 0`**——4個單位全部正常結束
行動,沒有一個卡死、沒有任何「行動未生效,重試一次」的訊息。§22的落點合法性
檢查這一輪沒有被觸發(因為mv=4算出來的落點本來就沒有超出範圍),但整體流程
(移動→確認落點→ring→REST fallback)全程乾淨。

**回合結束後截圖確認遊戲繼續正常運作,而且看到真實的雙向傷害交換**:自動進入
敵方AI回合,截圖捕捉到「索爾」LV.01對戰「盜賊」LV.02的全螢幕戰鬥動畫,盜賊
HP從028降到008(真的中了一次重擊),下一張截圖顯示「亞雷斯」LV.01 HP從042
降到014(也真的挨了一下)——雙方都有真實傷害,不是靜止畫面,戰鬥系統本身
完全正常。全程沒有DOS-exit崩潰。

**這輪確認的範圍**:用真實mv時,§16(retry)、§19(攻擊優先判定)、§22(落點
合法性檢查)三個修法疊起來之後,**整條「移動→REST fallback」的路徑乾淨無卡死、
無崩潰**;戰鬥系統本身(含敵方AI攻擊、傷害計算)透過截圖確認正常運作。**仍然
沒有直接確認**:我方單位主動發起攻擊、成功命中敵人的正向案例(這回合4個單位
都因為距離太遠沒有進入攻擊分支)——這需要挑一個mv範圍內確實能碰到敵人的情境
(例如多跑幾回合讓雙方靠近,或手動擺一個已經相鄰的初始局面),留給下一輪。

### 24. 2026-09-06(續):**追正向案例,`--mv 6`跑3回合——§22的落點合法性檢查正確攔下2個真的超出範圍的單位,但第3個單位落點合法、環開了、確認也送了,依然沒有效果,而且又撞到一次DOS-exit**

新開一個乾淨instance(`pos1`),`fd2_battle_autoplay.py --instance pos1 --turns 3
--attack --mv 6`。

**§22的修法確實在運作**:idx3(dx=-4,dy=1,共5格)、idx1(dx=-3,dy=3,共6格)
都被新加的落點合法性檢查正確攔下(「確認落點後座標完全沒變」),乾淨放棄那個
單位這一輪的行動,**沒有**像舊版一樣誤送按鍵到自由瀏覽狀態——這是§22修法在
比§23(mv=4)更貼近真實臨界值的情境下的正面證據,連 idx1 的 dx+dy=6 都超出
範圍,代表這個單位真實的移動力比6還小(可能是4或5)。

**但idx2遇到的是另一個問題**:idx2這次落點合法性檢查通過(座標真的變了,
沒有觸發§22的攔截),`select_ring(RING_ATTACK)`本身也成功,兩次confirm送出,
**§20加的立即回讀還是回報「攻擊確認未生效」**——acted未設、無敵方HP下降。
這證明**即使排除了落點不合法這個變因,攻擊執行鏈末端(目標選擇→實際命中)
依然有獨立於§22這個bug之外的問題**,§20當時定位的問題並沒有被§22完全解決,
只是被§22排除了一部分（落點不合法那部分）的干擾。

**緊接著又是array dump連續3次全0,這次也截圖確認是真的DOS-exit**(`C:\>`)。
這是本輪(2026-09-05/06這整條調查線)第4次獨立撞到C.16同款崩潰,而且是在
idx2「攻擊確認未生效」之後立刻發生——跟前幾次崩潰的觸發時機(都緊跟在一次
「確認送出但沒有效果」的攻擊嘗試之後)是同一種模式,進一步支持doc13
`project_fd2_re_dos_exit_p_lt_01`記憶檔裡新提出的候選假說:「對著已經不是
呼叫端假設的畫面狀態送出確認鍵」可能跟C.16的觸發有關,但這仍然只是同一個
模式的第4次觀察,不是嚴謹配對試驗,不能當成證明。

**誠實現況總結,這整條線目前為止的完整進度**:
1. §16(環選擇重試)、§19(攻擊優先於距離判定)、§22(落點合法性檢查)三個
   修法都各自解決了一個真實、獨立的bug,live測試都有正面證據支持。
2. **但「我方主動攻擊成功命中敵人」這個正向案例,連續4輪不同mv值
   (30、30、4、6)的live測試,一次都沒有乾淨確認過**——不是因為單位卡住,
   就是因為落點不合法被正確攔下,就是因為攻擊確認送出後依然沒有效果。
3. §20定位的「環開成功、確認送出、卻無效果」這個問題,獨立於§22修的落點
   合法性問題之外,**依然完全未解**,累積了3次獨立live觀察(idx3/idx2於
   §20,idx2於本節)。
4. C.16崩潰累積4次獨立重現,且都跟「confirm送出後沒有預期效果」的情境
   時間上緊鄰,值得下一輪用`fd2_crash_capture.py`(先武裝斷點)搭配一個
   刻意設計成「落點合法但確認後依然無效」的重現條件去追,而不是繼續盲測。

### 25. 2026-09-06(續二):**修了§18/§24的無窮重試——用「游標移回原地、零移動重新開環」恢復,確實打破了原本的degenerate loop,但揭露outer-loop卡死問題還沒真正解決,只是換了一種卡死方式**

用`fd2_crash_capture.py --rounds 10 --mv 6`直接重現§24的degenerate loop(idx2連續
10輪印一模一樣的「確認落點後座標完全沒變」)時發現:這正是§18當初就已經記過、
明講「這輪沒有修」的outer-loop bug——`approach_then_act()`偵測到落點不合法之後
直接`return`放棄,外層下一輪重新選到同一個單位、算出同一個必然失敗的落點,
無窮重複,不會真的探索到不同的遊戲狀態。

**這輪的修法**:偵測到落點被拒絕時,不再直接放棄——把游標移回這個單位原本的
位置、重新選取,這次用**零移動**(dx=dy=0,原地不動,結構上一定合法)重新開環,
保證能真的觸發攻擊/待機分支之一,不會再無窮迴圈在「同一個必然失敗的移動」上。

**Live測試結果,好壞參半,誠實記錄**:新開一個乾淨instance(`cc5`),同樣
`--rounds 10 --mv 6`。**修法確實生效**:idx1不再印「確認落點後座標完全沒變」
然後就此打住,而是印出恢復訊息、真的重新開環、嘗試攻擊——這一層的degenerate
loop被打破了。**但緊接著卡進了另一種degenerate loop**:idx1連續9輪都是「零移動
重新開環→`select_ring(RING_ATTACK)`成功→兩次confirm送出→§20的立即回讀還是
回報『攻擊確認未生效』」,一模一樣的結果重複9次——因為Acted始終沒被設起來,
外層下一輪還是重新選到同一個idx1,這次卡在§20那個更深層、還沒解開的問題上,
不是本節修的這一層。第9輪之後又是array dump 3次全0,截圖確認**不是崩潰**
(游標/移動高亮都還在,遊戲正常)。

**誠實現況**:
1. 本節的修法本身是真的改善——「落點不合法」這一類卡死已經不會再無窮重試同一個
   必然失敗的動作。
2. 但**outer-loop整體的「單位永遠卡住,迴圈永遠選到同一個」問題並沒有被徹底
   解決**,只是把卡住的層級從「移動落點」換成「§20的攻擊無效」。只要§20那個
   更深的問題不解開,`fd2_crash_capture.py`/`fd2_battle_autoplay.py`的多輪測試
   依然無法真正探索到不同的遊戲狀態(換單位、換敵人、真正打出傷害)。
3. **一個值得記住的新線索**:idx1連續9輪的「攻擊確認未生效」結果完全一致
   (不是偶發、不是有時成功有時失敗)——代表§20這個問題**在固定的遊戲狀態下是
   決定性的(deterministic),不是時序造成的偶發**。這對下一輪很有用:決定性的
   bug比偶發的bug容易用逐步截圖/debugger回讀鎖定,不需要像C.16那樣做統計試驗
   ——直接針對這個固定會重現的idx1情境,逐步截圖攻擊執行鏈的每一步,應該能
   一次定位問題,不需要碰運氣。

### 26. 2026-09-06(續三):**§20/§25那個「決定性」bug終於逐步截圖定位到——idx1(悠妮)是法師,沒有近戰武器,「攻擊」選項其實開的是法術選單,而法術一樣有射程限制、選了唯一的候選法術之後照樣悄悄取消,跟§22的落點問題是同一種模式在不同選單重現**

新開一個乾淨instance(`da1`),直接手動重現idx1的零移動開環序列(不經過
`select_ring()`的驗證層,單純逐鍵送、每按一鍵截一次圖),對照§25確認過的
「連續9輪一模一樣」情境。

**逐步過程**:
1. 選取idx1、原地確認(零移動,§25的恢復路徑):**截圖看到的是指令環**,
   四個選項——上(紅底高亮,自動選中)、左、右、下,四個圖示都不是文字,肉眼
   無法直接判斷語意。
2. 對高亮的「上」選項按確認:**畫面切成單位資訊卡**——「悠妮」LV.01、
   **人類 法師**(職業明確標示是法師)、HP028/028、MP008/008、DX001、
   **MV.004**(這裡順便確認了她真實的移動力就是4,呼應§23/§24用mv=4/6測試
   時的落點合法性判定)、HIT086、AP011、EV001、DP007,下方列出**「火炎術-
   MP02」**——這是法術清單畫面,不是武器攻擊的目標選擇畫面。**代表本輪一路
   稱呼的`RING_ATTACK`(index 0,方向鍵「上」)對悠妮來說,自動選中的其實是
   法術,不是物理攻擊**——她沒有近戰武器,`0x1b83d`(查無武器slot,doc13
   `attack_unit()`docstring已經記過的兩個disable成因之一)讓「攻擊」被disable,
   環自動落到下一個enabled選項,對法師來說就是法術。
3. 對唯一列出的「火炎術」按確認:**畫面直接跳回瀏覽游標畫面**,cursor剛好停在
   悠妮自己的格子上(資訊卡顯示的是她的單位卡),debugger回讀確認**acted依然
   是0**——法術選擇這個confirm,悄悄把整個流程取消掉了,不是進入「選目標」
   畫面。
4. 再按一次方向鍵(左):游標移動到旁邊的樹格,資訊卡正確顯示地形加成
   (「A-05 D+10」),**跟§22 step3看到的畫面一模一樣**——這就是純自由瀏覽
   游標,不是任何選目標的子畫面。

**結論**:idx1(悠妮)整個這輪一直卡住的原因,是她**沒有近戰武器,「攻擊」選項
實際上開的是法術選單**,而選了唯一候選的「火炎術」之後,遊戲一樣因為射程/
候選判定不成立而**悄悄取消整個流程退回自由瀏覽**——跟§22找到的「落點超出範圍
就悄悄取消單位選擇」是**同一種UI取消模式,只是這次發生在法術目標判定,不是
移動落點判定**。舊版`approach_then_act()`在`select_ring(RING_ATTACK)`成功後
無條件送兩次confirm(執行→目標選擇、確認目標),這個假設對「有近戰武器的單位
在射程內攻擊」成立,但對「法師,而且法術目標也不在範圍內」完全不成立——兩次
confirm裡,第一次confirm其實是選法術清單裡的項目,第二次confirm撞上的是
「射程外,悄悄取消」的畫面,不是攻擊真的執行了卻沒效果。

**這不是新bug,是既有bug(選項可能不是攻擊,而是法術)的一個新面向**:§19
已經知道「攻擊」選項自動落到哪一項要看enable gate,但一直沒有意識到**對法師
類角色,自動落到的很可能是法術而不是攻擊本身**,兩者UI流程不同(法術多一層
「選哪個法術」的清單,即使清單只有一項也要一次confirm去選它)。§20/§24/§25
反覆看到的「攻擊確認未生效」,至少在idx1(悠妮)這個案例上,現在有了具體、
可驗證的解釋:**不是「攻擊執行了但沒效果」,是「這兩次confirm根本沒有真的
在跑攻擊流程」**。

**下一輪建議**:
1. **不要再用idx1(法師)當「攻擊」的測試案例**——她結構上很難走純物理攻擊路徑
   (沒近戰武器),適合測的是法術命中,不是攻擊確認的正向案例。
2. 正向案例的驗證,應該挑一個**確定有近戰武器的單位**(例如idx0,已知的
   劍士索爾,見§23截圖確認過他能造成/承受物理傷害)。
3. `approach_then_act()`/`attack_unit()`若要真正通用支援法師類單位,需要偵測
   「這次開的環,選中的是攻擊還是法術」(讀`[0x53c57]`實際落在哪個index,而
   不是假設一定是`RING_ATTACK`那個語意),並且法術路徑的confirm次數/後續流程
   (選法術→是否還要再選目標→confirm)可能跟純攻擊不同,需要另外反組譯
   `FUN_0001cff0`那個法術選擇迴圈才能確定——這輪沒有做,留給下一輪。

### 27. 2026-09-06(續四):**正向案例終於乾淨確認——`fd2_battle_autoplay.py --instance sol1 --turns 3 --attack --mv 4`第2回合,idx1真的打中一個敵人,HP從18掉到13,第3回合那個敵人就從存活清單消失了**

延續§26的假設(idx1/悠妮不適合測正向案例),新開一個乾淨instance(`sol1`),
不特別手動指定單位,直接跑`--turns 3 --mv 4`讓遊戲自然輪替單位。

**第1回合**:4個單位(idx3/idx2/idx0/idx1)全部因為距離太遠,環都落在index 2
(不是攻擊),乾淨改走待機,`我方未行動0`——跟§23的乾淨結果一致。

**第2回合開頭有個新symptom,先記一筆**:回合切換時印了一行「等不到可操作狀態
(敵方回合/演出未結束?),中止本回合」,`main()`本身把這個狀況印出來但沒有
進一步處理,不影響本節重點,留待下一輪細看。

**第2回合,真正的正向案例出現了**:

```
idx1 確認落點後座標完全沒變(dx=-1,dy=0)——落點很可能超出這個單位真實的移動力,
    §22的偵測攔下,§25的零移動恢復路徑接手,原地開環
idx1 用 adjacent_foe() 的簡化格距判定移動後不相鄰,仍然照樣先試攻擊
idx1 攻擊已確認生效:acted=False, HP下降=[(8, 18, 13)]
```

**敵方idx8的HP真的從18降到13**(即時回讀直接讀到,不是事後猜測)——這是本輪
(2026-09-05/06這一整條調查線,從§13算起)第一次乾淨確認「我方單位主動發起
攻擊、真的命中造成傷害」的正向案例。第3回合的存活清單`[4, 5, 6, 7, 10, 11]`
不再包含idx8——這個敵人在後續(可能是同一回合的追加傷害,或敵方AI回合的連鎖
事件)死亡了。收工前截圖也捕捉到一個「得到」道具訊息框(悠妮頭像),佐證這是
真實、有意義的戰鬥推進,不是空跑。

**一個值得記錄的小落差,不影響上面的結論**:`acted=False`但HP確實下降了——
代表§27的verify邏輯裡`acted_now`那個判定這次讀到False(可能是讀值時機比遊戲
真正設起Acted早一點,或者這個特定的攻擊路徑設Acted的時機跟攻擊生效的時機
不同步),但**HP下降是不會騙人的直接證據**,不依賴acted判定。副作用:外層
迴圈那句「idx1 行動未生效(acted 仍為 0x00),重試一次」是誤判——這個單位
其實已經打中了,不應該被當成失敗重試。這是`main()`外層判斷「這個單位是否
已完成行動」只看acted位元、沒有交叉比對HP變化的一個小bug,留給下一輪,不影響
本節「正向案例已確認」的結論。

**整條線的階段性總結(§13-§27)**:`select_ring()`重試(§16)、攻擊優先於
距離判定(§19)、落點合法性偵測(§22)、卡死恢復(§25)四個修法疊起來,
搭配識別出idx1是法師不適合測攻擊(§26),終於在真實mv值下乾淨看到一次
完整、可驗證的攻擊命中。C.16崩潰機制本身依然未解,但整個battle autoplay
工具鏈的可靠性,相較session開始時已經有實質、多次live驗證過的進步。
