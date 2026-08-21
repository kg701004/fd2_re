# 13 — 戰場選單與行動系統

> 戰棋上選一個我方單位後,怎麼移動、怎麼跳出行動選單(攻擊/法術/道具/待機/狀態)、
> 游標怎麼操作、一個單位的「一回合」怎麼算完。第 3 輪反組譯 `FD2.EXE`。

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
