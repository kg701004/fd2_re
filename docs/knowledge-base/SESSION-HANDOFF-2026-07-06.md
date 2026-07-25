# 交接文件 — 給下一個 session(2026-07-06)

## 2026-07-25 resume note — SDD first

依使用者要求本輪先建立 `56-fd2-remake-sdd.md`，暫停新增 handler／renderer。盤點確認目前已有 Ebiten battle/story/cutscene、shop、church、preparation、save 與部分 native ending primitive，但原版 menu dispatch、完整 postbattle town/rest flow、weapon reach、item UI、native indexed presentation 仍未達 remake。`42`/`51` 只作 baseline。

working tree 的 `native_2c548.json`、`internal/ending`、`internal/figani` figure-fade 變更是上一輪未提交工作，已保留未覆蓋；待 SDD gate 後另行 Docker regression。`/tmp/fd2cap` 不存在。使用者所述 `~/.codex/knowledge-base` 在本環境無可讀檔案，Ghidra/IDA 技巧尚未宣稱已套用，待提供可見路徑或下一輪補入。

下一項：UI evidence matrix（title/menu/action/target/HUD/dialog）與逐章 battle→postbattle→town/shop/church/preparation/ending matrix；保持 fail-closed。

> 炎龍騎士團2 RE + Go/Ebiten remake(`/home/anr2/cht/fd2`,repo `wicanr2/fd2_re` main)。
> 記憶檔(`~/.claude/projects/.../memory/`)會自動載入=長期真相;本檔補「這段 session 的當前狀態 + 開放線索」。
> **動手前先讀:記憶索引 MEMORY.md、`docs/knowledge-base/00-index.md`(問題導向路由)、`doc50`(過場機制主檔)。**

> **2026-07-15 Codex 更正**：撤回舊 `0x207718`、id−48、74-resource 與「context 差 48 entries」
> 結論，它們來自錯 context／錯時刻的 acting dump。EXE 靜態 directory 是 106 entries（file+0x565d8，
> data=`file+0x53e00+offset`）；getter 以 source ACT ID 直接索引，沒有 chapter-local window。已驗 ACT99：caller
> `0x32343`、getter immediate=`0x2077d8`、table[99]=`0x208493`、bytes=`01 06 01 02 02`，即 slot2
> 上行六格（Y42→36、pose0→2）。ACT100 亦由 caller `0x323f5`/id100 live 驗為 slot2 下行十格
>（Y8→18、pose0）。不要以舊 map0/window 推論覆蓋此 provenance。

> **2026-07-16 第十九次 Codex 更新（戰後資料不再在城鎮邊界遺失）**：全30戰勝利流盤點發現
> `battle_ch04..10,12,14,16,18,19,22..26,28,29` 共19條非終局路徑直接進 town/preparation；但
> `enterNode` 會清掉 completed battle state，因此實際丟失等級、HP、戰利品與裝備。已在每條插入可編輯
> `postbattle_chNN_persist`：`sync_party → set_chapter → 原本 town/preparation`，不改城鎮／商店／教會
> ／整備去向。campaign regression 逐條追蹤 chapter1..29 正常路徑，強制在第一個戰間節點前恰一次 sync；
> chapter30 保留 direct ending。下一個商店切片必須使用同一 `partyRoster` numeric inventory，不能再寫入舊
> 的名稱字串清單。

> **2026-07-16 第二十次 Codex 更新（商店資料與原版收件規則）**：`shops.json`、demo 與 full
> campaign 的337筆商品皆已保存 EXE 原版 unsigned-byte `id`，逐筆以 `item.json` 的價格交叉驗證；
> generator 會拒絕缺 ID 商品。原版購買順序已 RE 為「確認→金錢檢查→選收件者→8格容量→插入首空槽→
> 裝備品詢問立即裝備→最後扣錢」；滿包／取消／無可裝備者均不扣錢。`0x1c1c3` 是純 class×item.type
> 六欄白名單，EXE file `0x55689`、stride7、首 byte 常數、後六 byte 才是 type；已匯出
> `docs/data/exe_tables/class_equip_types.json` 並加入 exporter selftest。尚未完成的是把此規則接進
> UI 的收件者選單、裝備狀態與能力重算；不得再把購買寫入 `Game.items []string` 當作真實 inventory。

> **2026-07-20 第二十二次 Codex 更新（商店收件者 UI）**：`main.go` 已接入 runtime eligibility assets，
> 商品 Enter 後進入第二段收件者清單，順序使用 `partyJoinOrder`、資料使用 persistent `partyRoster`；裝備品
> 依 class×item.type 篩選，消耗品列全隊，購買成功後以 map copy 寫回 roster 並保留 numeric inventory。
> Escape 可從收件者返回商品清單，商品頁再回原 town。已編譯驗證並推送 `39817dc`。尚待原版「要裝備上去嗎？」
> prompt、equipped flag／能力重算，以及賣出功能。

> **2026-07-16 第二十一次 Codex 更新（商店核心可測、等待 UI 接線）**：`battle.Unit` 已保留 FDFIELD
> numeric `ClassID`；`campaign.BuyGood` 已實作指定收件者的原子購買（成功才入8格 inventory 並扣金，滿欄／
> 缺錢完全不變）；`CanEquip` 已固定原版 class×item.type predicate，`LoadShopEligibility` 讀打包 runtime
> assets。`remake/assets/data/item.json` 與 `class_equip_types.json` 已強制納入 build（不是只放 docs），並有
> campaign regression。**下一輪第一件事**：在 `main.go` 將舊 `g.items []string` 商店分支換成「確認→合格
> 收件者→BuyGood→裝備詢問」UI state machine；裝備 flag、能力重算與賣出仍未實作。

> **2026-07-15 第二次 Codex 更新**：全 60 handler 重新抽取後 unknown 146→133。完整 callee body
> 已把 0x32975/0x32999/0x134e4/0x12d7b 定性成 deactivate_unit/spawn_intro/reset_pose/focus_unit；
> ch00 的 13 個缺漏 FDTXT calls 與 5 個 PAN 已接上；ACT99/100、兩段 scroll_step 與 focus_unit
> 也已 lower 並有 regression。`ch00_pre` 現可完整編譯為 editable beats，**0 unresolved issues**。

> **2026-07-15 第三次 Codex 更新**：`campaign_full.json` 預設入口已切到
> `story_ch00_handler → bindings/ch00_pre.json`，不再預設走手寫分幕。headless GUI smoke 已實際跑過
> 王座、草地、map31 全段並進入 map0 第一段對白；frame220 抓圖亦確認 ACT99+scroll 後索爾在
> `(8,21)` 正常顯示「兒臣索爾，晉見父王陛下。」。完整 runtime/unit tests 與 106-entry exporter check 全綠。

> **2026-07-15 第四次 Codex 更新（external overlay 排查）**：依使用者建議，重新追所有 DOS file
> open/read/seek 與 LE object mapping。結論是 handler/acting **不在外部 DAT，也沒有載入 text section**：
> handler code 在 EXE 跳表；acting directory `[0x627d8]` 是 EXE LE object #3 的 initialized data
>（file+`0x565d8`），payload bank=file+`0x53e00`。`0x111ba` 只把 FDTXT/FDFIELD/FDSHAP/美術資源讀進
> malloc heap。另以 DOSBox-X `-log-fileio` 實跑到 map32 草地對話，acting 期間沒有 FDOTHER/ANI/
> FIGANI/FD2.TMP read；`FD2.TMP` 只有 207360-byte write，無 read-back。詳證補在 `doc50`。

> **2026-07-15 第五次 Codex 更新（戰後 persistent roster）**：`0x11506` 的 **24 個戰後
> caller** 已由完整 body 定案，不是查詢函式。它以角色 ID 配對 runtime battle array 與 persistent
> roster，將完整 `0x50`-byte unit **由 runtime 複製回 persistent**；隨即清 persistent `+0x22..+0x27`
> 六 bytes 與 transient flags，存活 active 者 HP 回滿、全員 MP 回滿，死亡／inactive 者保留零 HP，再呼叫 `0x1145a`
> 依裝備重算衍生值。ch00 post 已 editable lower 成 `dialog → sync_party → set_chapter(1)`，由
> `story_ch02` 的 `bindings/ch00_post.json` 接入；`partyRoster` 會在下一戰 materialize 時覆蓋持久能力
> 值，且已納入 remake JSON save/load。全量 handler `unknown` 因此由 **133 降至 109**。完整位元組流程
> 與欄位證據（包含 ID 0 inactive/dead 時原版會跳過 copy 的特例）見 `doc50 §3.2`。

> **2026-07-15 第六次 Codex 更新（戰後獎勵物品）**：`0x1c220(item_id)` 已由完整 body 與
> `0x1bb8c` 定案為「按 runtime slot 找第一個我方且 8-slot inventory 有空位的角色，放入 item」。
> 兩個 caller 是 ch01 `0xC6` 力量藥水與 ch20 `0x64` 天空之鑰；已 lower 成 editable
> `grant_item`，角色 `Inventory` 會經 `sync_party` 與 save/load 跨章保留，handler unknown 109→107。
> 此更新當時另發現 slots 5..10 存活分支與 FDTXT_002 缺 8 句等 11 issues，不能把 #6/#7 兩條
> 路徑直線串播；分支已由下一筆更新解決，其餘 binding 問題仍待處理。

> **2026-07-16 第七次 Codex 更新（handler control-flow，已校正 bit 方向）**：ch01 post 的 diamond 已從原版
> 指令形狀復原成 editable `if any_unit_inactive(slots 5..10)`。任一村民死亡只播 #7；全員存活才播 #6
> 並送 `0xC6`，之後共同 continuation 只執行一次。compiler 會先 resolve 兩臂、runtime roster 不完整
> 時 fail closed；dialogue binding/unknown diagnostics 亦會遞迴 branch。詳見 `doc50 §3.4`。

> **2026-07-16 第八次 Codex 更新（FDTXT_002 完整化）**：`ch02.json` 已由 53 補到原版 61
> logical utterances，#6/#7 互斥獎勵已拆開，#5 與 #11..16 亦保留在獨立資料位置；ch01 post
> 的五個 dialog call-sites 全部取得精確 mapping，compile issues 11→6。並修正 `FFED operand`
> 不是角色 ID 而是 runtime slot：村民 slots5..10 以 `speaker_slot` 動態解析 DATO134/133，缺 slot
> 時 fail closed。詳見 `doc50 §3.5`。

> **2026-07-16 第九次 Codex 更新（ch01 post 完整接線）**：ch02 battle 已恢復原版 runtime
> constructor 順序：party0..4、村民5..10、group2=11..20、turn3 group3=21..26，戰後 SPAWN4
> 才 append 希莉亞為 slot27；group255 不再預佔 runtime array。`ch01_post.json` binding 以明確
> postbattle context 驗證 slot frontier，PAN 定案為 `(336,48)/(336,24)`，ACT14/15/16 直接作用於
> canonical battle state，compiler 為 0 issues。campaign 已接成 battle→post→下一章 town/preparation，完整測試、
> build 與 Xvfb branch/PAN/SPAWN/ACT14 截圖均通過。戰後演出中因 save 尚不序列化 battle array，
> F5 會明確拒絕，下一節點恢復可存。詳見 `doc50 §3.6`。

> **2026-07-16 第十次 Codex 更新（shared tail + 第二章戰前）**：修正 exporter 把「下一個 jump-table
> entry」誤當 CFG 絕對終點的問題；原版多支 handler 會跳到邊界外／較低位址的共用尾段。60 支
> handler 重新機械輸出後 top-level beats **624→701**，unknown **107→108**；兩個合成 CFG 測試固定
> external/backwards shared-tail 順序。`ch01_pre` 現完整包含尾端 `FDTXT_002 #3` 與 focus(slot0)，
> 四段原版字串展開 20 句、compiler 0 issues；兩段 PAN 依 `0x135dd` 改為 X-first、每次一 tile 的
> `tile_step`。另由 battle-event caller `0x341e6 push 1; call 0x112a5` 定案哈諾在 turn3 JOIN，
> persistent party 順序為 `[索爾0,悠妮9,亞雷斯4,蓋亞30,哈諾1]`，再 materialize group3；campaign
> 已接成 `ch00_post → ch01_pre → battle_ch02`。同時撤回舊的 `ch05_pre=玩家第五章` 假設：它是
> 零起算 table index5，實際選 map5/FDTXT_006（玩家第六章），其 shared dialog 與後期 JOIN chronology
> 尚未閉合，所以不再冒充 campaign complete consumer。詳見 `doc50 §3`。

> **2026-07-16 第十一次 Codex 更新（第三章戰前 + FDTXT_003）**：`ch02_pre` 16 source beats 已
> 完整 lower 成26 runtime beats、0 issues：六人 JOIN-order party `[0,9,4,30,1,8]`，三段 X-first
> tile PAN，ACT18→SPAWN1九人→ACT17/19，以及跨 handler shared dialog/reset/focus。map2 battle 同步
> 改為 party-first runtime append，group255 不再汙染 slots。更重要的是回原始 FDTXT_003 找回舊
> `ch03.json` 真正漏掉的六句 turn3 葛雷／卡蘿硬編碼對話，全文由33補成39，索引重生後達39/39
> count-aligned（generated contexts 81→83、skipped 89→87）。campaign `story_ch03` 已由章標 stub
> 改接 authored ch02_pre。後續已以 constructor/death/revive 完整 body 解開 slot6 bit0 方向，
> 下一筆更新與 `doc50 §3.7` 為現行定案。

> **2026-07-16 第十二次 Codex 更新（bit0 全域翻案 + ch03 條件）**：完整反組譯與 live
> dump 交叉證實 `unit+5 bit0=0` 才是 active/alive，`1` 是死亡／隱藏／inactive；bit7 才是
> acted。有效 constructor `0x10eed` 寫0，HP0 路徑 `0x1dc61/0x1dd4c` 寫1，復活 `0x30f9c`
> 清0。exporter/runtime 因此改名 `unit_inactive`、`any_unit_inactive`、`deactivate_unit`，60 支 handler
> 已由原 EXE 重生。ch01 post 現為六村民全存活才 #6+item198；ch03 turn3 新增
> `unit_slot_active:6`，鐵諾死亡時不再誤生 group2。`0x11506` 也同步校正為存活者 HP 回滿、
> 死亡者保留零 HP。`ch02_post` 真 CFG 已釘死為 `sync → inactive?#6:(layout+#7+JOIN2) → chapter3`；
> 下一優先是 single-slot diamond、`0x233c6 layout_units` 與 15/27-slot runtime frontier。

> **2026-07-16 第十三次 Codex 更新（ch02 post 完整閉合）**：extractor 已以通用指令形狀
> 復原 single-slot diamond，`ch02_post` 現為 `sync_party → if any_unit_inactive([6])`；死亡臂只播
> #6 五句，存活臂執行 `layout_units`、#7 十句並 JOIN2，共同 `set_chapter(3)` 只保留一次。
> `0x233c6` binding 保存 slots0..6 絕對 X/Y/pose、camera `(48,0)`、redraw/fade/delay200；
> post runtime 只接受 15/27 slots，對應 turn3 援軍未生／已生兩種真實 frontier。campaign 已接
> `battle_ch03 → story_ch03_post → town_ch04 → preparation_ch04 → story_ch04`，compiler 0 issues。同輪把全 post handlers 的
> `inc [chapter]` 保留成 editable `set_chapter`，15 個 `0x233c6` caller 改為已命名、待逐章 binding 的
> `layout_units`；全 60 支 manifest 為 **725 top-level beats / 93 unknown calls**。詳見 `doc50 §3.8`。

> **2026-07-16 第十四次 Codex 更新（戰後 town/preparation 全戰役契約）**：原版 victory
> driver 已重追為 `post[current] @0x25e23 → intermission 0x2cad7 → pre[next] @0x25e3a`，
> 不是 post 後直接下一戰。`byte[chapter+0x526b9]` 的零起算章表是 0..21 town、
> 22..24 preparation、25..26 town、27..29 preparation；這與商店只存在玩家章
> 2..22、26、27 相符，也證明 shops.json 的章數是「下一場」，舊 campaign 整體 off-by-one 已修正。
> remake 新增 editable `town`、`preparation`、`church` 節點；town 保留酒店／武器店／出口／
> 道具店／教會五設施與 hidden secret shop，各設施離開後回 hub，出口才進可存檔的隊伍整備；
> 原版無 town 章也依然有「要記錄戰況嗎？」與 sortie preparation。
> `TestCampaignFullPostBattleTownContractMatchesOriginalShopChapters` 已對全戰役固定 shop 章集合、
> post→town/prep→next pre、facility 回 hub、無 town 仍有 prep 及最終 ending；詳證見 `doc50 §3.9`。
> 尚未閉合的原版分支是玩家第27章戰後：天空之鑰 `0x64` 存在才增章進第28章，
> 無鑰匙則 `0x2545d → 0x2bce5` 壞結局；這個 handler/inventory condition 仍需後續接線。

> **2026-07-16 第十五次 Codex 更新（ch03 turn3 通用 battle-event sequencing）**：新增與
> campaign BeatRunner 分離的 `battleEventRun`；`Scenario.TriggerActions` 保存 JSON action 原序，
> runtime 完整播放 `SPAWN2 → PAN(3,0) → 800ms → PAN(3,17) → 200ms → FDTXT_003 #4 七句`。
> map2 24px tile 使鏡頭精確到 `(72,0)/(72,408)`，等待為48/12 ticks；事件最後一句前 Turn 與
> status 都不 tick，finishTurn 重入不重複觸發。battle event 同時改用原版320×200（13×8格）
> viewport；完整 Go tests 與 Xvfb frame120 實畫均通過。詳見 `doc50 §3.7`。

> **2026-07-16 第十六次 Codex 更新（第27章天空之鑰 gate）**：campaign 新增非玩家選擇的
> editable `inventory_gate`，`battle_ch27` 勝利後以 item `0x64` 分成兩臂。有鑰匙才執行
> `sync_party → set_chapter(27)` 並停在 `preparation_ch28`，缺鑰匙進獨立壞結局；Load/runtime
> 對 item/兩臂 fail closed，測試固定原版 `0x24b14` 只掃 runtime slots0..15、無 camp/active filter，
> persistent roster fallback 則明記為 save/load projection。另已釘死真正取得路徑在零起算
> ch20_post（玩家第21章戰後）：必須集齊 `0xD1..0xD6` 六素材，成功才移除六件並 grant `0x64`；
> 目前 `battle_ch21` 還沒接這個 diamond，所以正常實玩仍拿不到鑰匙，下一批要接成
> `battle_ch21 → ch20_post → town_ch22`，不可無條件發鑰匙或跳過城鎮。

> **2026-07-16 第十七次 Codex 更新（玩家第21章戰後鑄造）**：已以完整 disassembly 更正
> 「六種各一件」簡化；原版其實計算 `D1..D6 × runtime slots0..15` 的 `(item,slot)` 命中組合，
> 總數必須**恰為6**，因此 duplicate 分散角色會改變結果。通用 editable `inventory_recipe`
> 現 byte-exact 保存這個怪癖、成功 pair-ordered 移除與 grant `0x64`，失敗不改 inventory。
> campaign 已接 `battle_ch21 → #5十句 → recipe → crafted #7..#10全16句 / insufficient #6全4句`，
> 兩臂共同 JOIN24/JOIN23、sync、chapter21，最後都回 `town_ch22`。layout/ACT63/64/`0x24336`
> 鑄造動畫仍待 lower，且更早章節尚無 D1..D6 正常取得路徑；文字／物品／持久化／城鎮流已接，
> 但不可宣稱這支視覺演出或 true-ending 實玩取得鏈已完整。Xvfb 已以真實 battle_ch21 context
> 實畫 #5 與 #6；#6 畫面仍會露出未 layout 的黑區，這是明列待辦，不以手寫鏡頭假裝還原。

> **2026-07-16 第十八次 Codex 更新（六素材正常取得鏈第一個可玩垂直切片）**：D1 已由
> EXE 人物 defaults 證實在索菲亞 `[36,A7,D1]`，並接入 ch11 party；D2/D6/D4 已由 FDFIELD
> composition terrain flag + slot + control reward 精確接成 map10 `(18,37)`、map12 `(38,18)`、
> map19 hidden `(30,7)` 的可編輯寶物。原版只在站上該格選「休息／待機」時取，背包滿不開箱，
> 敵我皆可取；runtime 已按此實作。D3/D5 不是泛用 inventory 搬運：特殊死亡 id39/id41 的 EXE
> handlers 明確 lower 為單一 `D3/D5` reward，已接 once-only death reward 與跨戰 party sync。
> ch11/13/15/17/20 勝利現在都先經 editable `postbattle_chNN_persist` 再回
> town12/14/16/18/21，沒有為保存素材跳過城鎮／商店／整備。尚未完成的是 D2/D6 獸人主動搶箱與
> 逃離 AI、普通寶箱 opened terrain+1 視覺、物品滿欄時原版互動轉移 UI；詳證見 `doc50 §3.10`。

## 0. 目前焦點(接手就做這裡)
`ch00_pre`、`ch00_post`、`ch01_pre`、`ch01_post` 已成為前四個 campaign 實際 consumer；ch01 post 的 branch、
reward、61-utterance FDTXT_002、dynamic speaker slots、PAN、SPAWN4、ACT14..16、JOIN/sync/chapter tail
與第二、第三章戰前／戰後 handler 均已完整 lower 且 compiler **0 issues**；ch03 turn3 的
slot6 active 條件、SPAWN2、兩段 PAN、800/200ms 與 FDTXT_003 #4 七句也已完整；第27章戰後
天空之鑰→第28章整備／壞結局 gate，以及玩家第21章戰後的六素材 recipe／完整分支文字／
共同 JOIN/sync/town22 均已接；D1 人物 default、D2/D6/D4 寶箱、D3/D5 特殊死亡 reward 與五個
關鍵戰後 persistence→town 節點也已完成第一個可玩垂直切片。下一個具體焦點是 D2/D6 獸人搶箱／
逃離 AI 與普通寶箱 opened 換圖，或 lower ch20_post 的 layout/ACT63/64/鑄造動畫，再選下一支
`0x233c6` post caller 依原版 arrays 補 binding。下方「草地深層未解」是 2026-07-06 歷史記錄，已被 2026-07-15 direct table 修正推翻，
不得再當目前 blocker。

## 1. 這段 session 做完的事
- **王座傳位幕**:走位 (8,42)→**(8,21)**第一次對話→**(8,8)**最終(對原版截圖+FDFIELD 守衛地標實測);
  守衛 dir=0(面向玩家);對話切分 line0 / line1-18;對話框修 4 項(文字不蓋頭像/上下框移入畫面/漸層/**長對白分頁**)。
- **草地幕(palace_path)**:亞雷斯 2 段進場(13,47→11,47→8,46 面向索爾)、進場句用**上框**、對話後索爾走到旁邊。
  ⚠ **「兩人一起走離+淡出」(結尾)先前試做又還原了**(見 §3 待辦)。
- **debug 工具**(cmd/fd2/main.go):`FD2_UNIT_LABELS=1`(sprite 標 `[idx]f<fig>(x,y)dDir`)、
  `FD2_CUTSCENE_LOG=1`(過場 node/beat/走位逐步印 stderr)。
- **文件集中化**:`doc50`=過場機制唯一主檔;新增 `scene-decode/ch1-throne.md`+`ch1-meadow.md`(每幕原始資料×解讀)。

## 2. 已驗證的 RE 定論(耐用真相,別再翻案)
- **走位來源 = step 家族 + 路徑走位 + acting normal frame**：`0x12eaa`下/`0x1300d`左/`0x13185`上/`0x13315`右(各推一格+捲鏡頭);
  通用 `0x13488(單位idx, 方向陣列, 步數)` 走任意路徑。王座是「全上」特例(直接 0x13185×15/13)。單位結構 +0X/+1Y/+3pose/+4tick/+8角色ID。
- **此 handoff 的 acting「只設面向」結論已於 2026-07-15 推翻**：normal frame 依 pose 每拍移一格，
  special frame 才原地顯示。格式與證據以 `doc50 §1.2` 為唯一準據。
  bit7 不改變 (unit,pose) 意義。normal frame 的低7位拍數=移動格數；special frame 的拍數才是
  原地顯示節奏。+4 tick 配繪製公式 `0x127e0=格+tick×f(pose)` 做每一格內的平滑內插。
- **map32 roster(dosbox dump `task_f/slots0_20_dialogue.bin`)**:slot0王/1后/**2=王座索爾**/**3=草地索爾(4,46)**/**4=草地亞雷斯(13,47)**/5-20守衛。
- **面向規則(全劇本)**:dir 預設 0(下/面向玩家);FDFIELD 不存面向;非0僅「走位者面向移動方向」或「劇情主角對看」。

## 3. ~~最大開放問題:草地主角走位~~（2026-07-15 已解）
- 錯表 decoder 才把 ACT101..105 誤讀成守衛16/17。direct resources 實際操作 slot3/4：ACT101/102
  讓亞雷斯接近，ACT103/104 原地定向，ACT105 讓索爾與亞雷斯離場。handler 顯式 ACT 已完整解釋影片，
  不存在額外走位機制或森林 context table。
- 正確機械輸出由 `tools/export_acting_resources.py` 直接讀 EXE 106-entry bank；舊本機 dump 僅考古。
- **方法論(使用者定)**:證據(截圖/影片)+ 已知機制 → 可「由上而下」回原版資料找出處,不必每次 RE 到底。

## 4. 其他待辦(worklist doc91;不急)
- ~~草地結尾兩人一起走~~：已由 direct ACT105 承接，不再用手寫 `exit_walks`。
- **對話分頁捲動動畫**(原版有「文字往上捲」;自寫平滑捲動即可,速度自訂非 RE)。
- **自動結束回合**(全員行動完自動換陣營,免手動 Tab)。
- **狀態欄位置**(HUD 擋單位,doc51)、**哈諾父子死亡→暴走**驗證、**export_units.py 全 33 章敵人數值**套合成公式。

## 5. 鐵則 / 紀律(這段 session 使用者立的,務必遵守)
- **[HARD] 禁臆測**:每個進 code 的值要有 RE 依據(反組譯/dosbox/青衫/影片/FDFIELD);拿不到→標「待RE」→外推前先問使用者。
  驗收=對 reference 實測(原版截圖/影片),不是「測試綠」或「看起來像」。(記憶 `fd2-goal-and-no-speculation-rule`)
- **[HARD] 知識集中一份 markdown**:動手新增文件前先查既有→擴展它;其他檔只引用不複製。過場機制=doc50。
- **[HARD] sonnet 只做 coding;比較/判斷/驗證/反組譯語意 一律旗艦親自做**:sonnet 反組譯猜錯 6/7 原語、
  截圖判讀也會幻覺(回報「視覺達標」實測沒有)。派 sonnet 實作後,「像不像/算不算完成」旗艦親自截圖親看。
- **dosbox 不萬能**:heavy-debug 下執行類斷點卡死;採樣率跟不上快變值會誤判;headless 截圖 fps≠60 送鍵易對不上。
  優先靜態 RE + 原版截圖(靜止參照);Go 測試(確定性)驗邏輯、截圖驗版面。
- **我這 session 自己犯又修的錯(別重犯)**:①「15呼叫=15格→row27」線性外推錯(→21);②「(8,8)改(8,14)」誤判(→8);
  ③ 此處「acting 只設面向」的舊判讀已撤回；後續請以 doc50 的 2026-07-15 更正為準。

## 6. 關鍵檔案地圖
- **機制主檔**:`doc50-cutscene-script-system-design.md`(過場原語/走位/acting/handler/DSL)。
- **每幕原始資料×解讀**:`scene-decode/ch1-throne.md`(含 acting byte 反組譯附錄)、`scene-decode/ch1-meadow.md`。
- **handler 逐 beat 轉錄**:`doc47`(§3 三段/§7 機械抽取/§9 走位實驗/§10-11 step 公式)。
- **草地影片量測**:`doc55`;**remake↔文件溯源+落差**:`doc44 §5`;**dosbox 實測**:`doc48`。
- **remake 對話框渲染規則**:`doc09`。**戰鬥演出**:`doc35`。
- **原版 dump**(本機,gitignore):`extracted/dosbox_dump/`(acting_decoded/、task_e|f/slots、out/);
  **原始 .DAT 解包**:`extracted/raw/`(FDFIELD/FDTXT/FDOTHER…);**原版錄影**:`video/fd2-ch1.mp4`。
- **工具**:`tools/disasm_le.py`(反組譯,docker `fd2-cap`)、`tools/parse_field.py`(FDFIELD)、
  `tools/export_acting_resources.py`（由 FD2.EXE direct bank 產生／檢查 106-entry editable JSON）。
  `extracted/.../decode_acting.py` 與舊 transcript 是 gitignore 考古物，不得作 canonical input。
- **remake**:`remake/`(build:`cd remake && ./build.sh` docker;跑:`./play.sh`;headless 截圖:見 play.sh --shot 或 FD2_SHOT env)。

## 7. 環境速記
- 反組譯:`docker run --rm -v /home/anr2/cht/fd2:/w -w /w fd2-cap sh -c "python3 tools/disasm_le.py 'org_game/炎龍騎士團/FLAME2/FD2.EXE' range 0xA 0xB"`
- headless 截圖:`xvfb-run -a -s "-screen 0 1280x800x24" env LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe FD2_MUTE=1 FD2_CAMPAIGN=... FD2_CAMP_NODE=<node> FD2_SHOT=out.png FD2_SHOT_FRAME=N ./fd2-linux`
- EXE 位址:tool-linear = 檔內位址(disasm 直接吃);執行期位址另有 loader 偏移(見 doc48 §5)。
- **每輪做完 commit + push**(CLAUDE.md 要求)。素材/dump/org_game/references 一律 gitignore 不入庫。

## 2026-07-20 Codex shop transaction slice
- 商店購買已拆成原版順序：選收件者後先插入未裝備物品，裝備類進入「要裝備上去嗎？」；Enter 裝備、ESC 保留未裝備，兩者最後才扣款。
- `battle.Unit` 新增與 Inventory 對齊的 `Equipped []bool`，並在 persistent sync、recipe 移除、死亡獎勵、寶箱領取時維持欄位對齊；`ClassID` 亦納入 persistent overlay。
- `campaign.ReserveGood`/`FinalizeGood` 保留兩階段交易原語；`BuyGood` 維持既有一次完成 API。
- 已以官方 Go 1.22 容器跑 `go test ./internal/campaign ./internal/battle ./cmd/fd2 -count=1`；能力值重算與換裝（覆蓋同類舊裝）仍待下一輪 RE/實作。
- 本輪補上 `campaign.SellGood` 純交易核心（原價 3/4、先驗證再移除欄位）；尚未接 UI。裝備數值暫不臆測：現有 FDFIELD/character dump 丟失原版 inventory slot flag，且 scenario AP/DP/HIT/EV 是有效值，必須先補 provenance 才能安全重算。
- 2026-07-20 後續：商店已接賣出 UI（Tab 切換、角色、指定 inventory slot、ESC 返回），以 `item.json.price` 載入原價並呼叫 `SellSlot`；duplicate item ID 不會賣錯欄位。能力重算仍刻意保留待 RE。
- 2026-07-20 RE 補證：以 `tools/disasm_le.py` 反組譯原版 `0x1145a` 與 `0x1c142`。`0x1145a` 明確掃 8 個 `+0x0a+slot*2`，檢查第一 byte `bit 0x40`，從 item record `+1/+5/+3/+7` 累加 AP/DP/HIT/EV；`0x1c142` 的換裝規則是 item ID `<0x80` 與 `>=0x80` 分兩類，清除同類已裝備 flag，再將新 slot 第一 byte 寫 `0x40`。
- 2026-07-20 provenance slice：`parse_field.py`/`export_units.py`/`dump_exe_tables.py` 現在保留固定長 `inventory_slots`（FDFIELD 8 bytes、character defaults 6 bytes 後補兩個 `0xff`），不再只存 compact inventory；33 張 map units 與 ch11 Sophia 已帶入。`Unit.AddInventoryItem`/`RemoveInventoryIndex`、寶箱、死亡獎勵、配方、商店、persistent sync 都同步維護 raw slots。
- remake 已新增 `BaseAP/BaseDP/BaseHIT/BaseEV` 與 `RecomputeEquipment`。進一步確認原版 spawn `0x10f06..0x10f31`：source inventory 前兩 bytes 直接寫成 flag `0x40`，後續 bytes 為 `0x80` held；remake 現在 materialize 前兩欄 equipped，並由 `InitializeEquipmentBase` 從 authored effective 值扣回一次，避免 double-count。raw `inventory_slots` 已保留原始 `0xff` 空槽位置，並由新增/移除/同步流程維護。
- 2026-07-20 materialization 修正：原始 `inventory_slots` 是 FDFIELD source bytes，不是 runtime 欄位。依 `0x10f06..0x10f31` 的分支，source[0] 為 `0xff` 時 source[1] 會壓入 runtime slot0；否則 source[0]/source[1] 分別進 runtime slot0/1，source[2..7] 保留原位。`Load` 與 `PartyUnits` 現在先 materialize 成 8 格 runtime slots，再建立 compact `Inventory` 與對齊的 `Equipped`；商店、寶箱、配方、死亡獎勵以 runtime slot 操作，避免內部空槽時錯移裝備。核心測試與 `go test -c ./cmd/fd2` 已通過。
- 2026-07-20 town/preparation audit：`campaign_full.json` 的 ch01→town02、ch02..21→postbattle→town、ch22..24 的連戰 preparation、ch25→town26、ch26→town27、ch27→prep28、ch28→prep29、ch29→prep30、ch30→ending 串接均已盤點；town 的 shop/rumor/church 返回原 town。尚缺的是 `main.go` 的 preparation 編成與 church 行為仍為 placeholder（Enter/ESC 直接 Advance），下一輪需先建立可編輯的 party/deploy/equipment 整備節點與 persistent roster/gold 不丟失測試。
- 2026-07-20 item range RE：`0x14237` generic attack target path 讀 item `+0x0c range_min` 並傳給 `0x14818` 的 Manhattan geometry cutoff；`+0x0b atk_rate` 在該路徑未再讀，`+0x0d range_max` 只在特殊 item/effect 路徑出現，不能臆測成通用 `AtkMax`。`0x1df3f` 另以 `atk_rate` 做特殊限制，`0x1ed6a` 將 `atk_attr` 帶入攻擊效果分支。remake 繼續使用已驗證的 `weapon_range.json`，完整 item multiplier/effect 仍待 direct callsite。
- 2026-07-20 preparation slice：反組譯 `0x318ad` 證實整備畫面建立 30-byte 勾選表；一般章節 cap=`0x0f` (15)，late route cap=`0x13` (19)，方向鍵移動、Enter 切換角色，達 cap 後自動離開。remake 新增 `Node.party_limit`（ch28–30=19，其他 preparation 以 direct fallback=15）、`Game.partyDeploy` 暫時出擊名冊與 preparation UI；永久 `partyMembers` 不被改寫，下一場 battle 只以 `partyDeploy` filter，避免 JOIN/save roster 遺失。核心測試與 GUI compile 已通過。
- 2026-07-20 church RE：`0x3072f` 讀教會服務選擇並分派 `0..3` 到 `0x2ffa5/0x2f8ea/0x30dc3/0x31385`；`0x30dc3` 的 `0x24c` 是「無須復活」訊息，存在死亡候選才用 `0x24d` 選人，確認費用後 `0x2d516` 扣款、清 `[unit+5]` 死亡 flag、把 `[unit+0x42]` 複製到 `[unit+0x40]` 恢復 HP。`0x31385` 的 `0x24f/0x250/0x252` 分別是無候選／選人／確認轉職。教會沒有免費一般治療分支；下一步先資料化 revive/class-change service nodes。
- 2026-07-20 revive core slice：直接讀出 `0x52669 + class*2` 的 29 筆 u16 class fee table，新增 `docs/data/exe_tables/revive_fee_rates.json` 與 editable runtime copy `remake/assets/data/revive_fee_rates.json`。`campaign.ReviveUnit` 依已證實公式 `feeRate * level` 先驗金額，再原子寫回 HP=MaxHP、清除死亡投影 `OnField`；不足金或非死亡候選不改狀態。尚未把 church selector 接到 UI，也尚未追完 class-change 寫回能力表。
- 2026-07-20 class-change candidate slice：`campaign.CanChangeClass`／`ClassChangeCandidates` 已接上 `0x31793` 的 exact filter：Lv>=20、portrait<0x12 且 portrait!=7，保留 JOIN order；尚未實作 `0x31860` 道具分支與 `0x2a2e8` class/portrait/能力寫回。
- 2026-07-20 church selector slice：`main.go` church 節點已從直接返回 town 改成四項服務選單；第3項接 `campaign.ReviveUnit` 與 EXE fee table，第4項顯示 exact class-change candidates但保留 item/能力寫回待接。xvfb 實機截圖已存 `docs/figures/church-selector.png`。
- 2026-07-20 class-change RE continuation：`0x3151a..0x3152d` 依 portrait 查轉職道具（portrait 0x34→item 0x5a，其餘 promoted portrait→`0x526a7+portrait` byte），`0x31860` 掃 8 個 inventory slot；成功後 `0x1b8e7` 移除 item、`0x2a2e8` 重算、`0x31571..0x3157a` 寫 class(+0x20)/portrait(+7)。目前只接 candidate/UI，mapping table 尚待完整導出。
- 2026-07-20 class target tables：已導出 `0x615fe` portrait→(class,mobility increment) pairs 與 `0x526a7` raw item bytes 至 `docs/data/exe_tables/class_change_targets.json`；portrait 0x34 的 item 0x5a special override 已明列。`0xff` raw item 代表該 target branch 尚不能直接視為可用道具，runtime 尚不接猜測性 class mutation。
- 2026-07-20 class target table correction：原表把 `0x526a7` 誤標成 target portrait index；依 `0x31793` 實際指令，現在拆成 `current_portraits`（current portrait 0..0x11，default=current+0x20、optional=current+0x32，raw item `[0x526a7+current]`）與 `target_portraits`（`0x615fe` 的 class/mobility increment pairs）。raw `0xff` 不建立 optional target；current portrait 9 的 item 0x5a→target 0x34 special branch 保留。新增 `class_change_table_test.go` 驗證 18/34 rows 與 index 對齊。
- 2026-07-20 `0x31602` stat-reset 定案（更正）：`0x4e4d1(portrait)=0x620a1+portrait*0x0b` 的 11-byte 成長列，五組 row pairs 經 `0x1e529` **加到既有** unit words `+0x37(AP),+0x39(DP),+0x3e(DX/HIT-EV base),+0x42(MaxHP),+0x46(MaxMP)`；`0x1e529` 尾端是 `add word [target], ax`，不是覆寫。`+0x40/+0x44` 由後段回填 current HP/MP；`0x4e48d(new portrait)+1` 的 mobility increment 加到 raw `+0x3b`。流程清 raw EXP `+0x3c`，**未寫 level byte，故保留原 Lv**，HP/MP 全滿。row random 是 pair 的 `[min,max)` 取值。
- 2026-07-20 class mutation core slice：`campaign.ApplyClassChange` 依 `0x31602` 寫回 target portrait/class、AP/DP/DX/MaxHP/MaxMP、MV(+0x3b)、Lv=1/Exp=0/HP=MaxHP/MP=MaxMP，並移除 branch item；invalid range/item 失敗不改動 unit。新增成功與 atomic rollback tests；尚未把 UI/JSON growth rows 接上，也尚未呼叫 equipment recompute（避免猜測舊 Base*）。
- 2026-07-20 class-change editable bridge：新增 `LoadClassChangeTable` 解析 current/target portrait maps，`ClassChangeTargets` 依原版順序產生 default/optional/special branches 與 compact inventory index，並以 `LoadClassChangeGrowth` 將 `growth.json` idx32..67 映射至 target portrait 0x20..0x43；已驗證 18/34 target rows、36 growth rows 與道具存在條件。
- 2026-07-20 church class target UI slice：church 選轉職角色後進入 target branch 選單，依 default/optional/special 顯示 target portrait/class；Enter 會用 shared RNG 執行 `ApplyClassChange`、移除 branch item、設定 class name、重建 equipment base/recompute 並寫回 `partyRoster`。新增 runtime `class_change_targets.json`/`class_change_growth.json`（force-added，assets 預設 ignore）；GUI compile 與 campaign/battle tests 通過。尚待 xvfb 實機操作驗證與 race/multiplier raw bytes 接線。
- 2026-07-20 `0x1b750` synthesis continuation（校正）：`0x1b750` 讀 raw `+0x37/+0x39/+0x3e` 與 item table 23-byte row 的 `+1/+3/+5/+7`，寫 derived `+0x48/+0x4a/+0x4c/+0x4e`；它是 class path 後的 equipment/stat synthesis，不是 screen-only projection。`+0x22/+0x23/+0x24` 雖會影響該 routine 的 transient branches，但 constructor 先清零且 `0x31602` 不寫它們，不能當成 class growth source。`campaign.RecomputeAfterClassChange` 與 double-count regression test 已保留。
- 2026-07-20 xvfb fixture hook：`FD2_CAMP_CLASS_FIXTURE=1` 僅供 headless oracle，注入一名 Lv20 portrait9（索爾顯示名）並帶 item 0x58/0x5a；在 `FD2_CAMP_NODE=church_ch02` 下可用 xdotool `Down×3 Enter` 進轉職、再 `Enter` 選唯一候選，target branch 畫面應列 default portrait 0x29、optional 0x3b、special 0x34。此 hook 不在正常啟動路徑。
- 2026-07-20 xvfb class-target proof：以 fixture、`FD2_CAMPAIGN=assets/scenarios/campaign_full.json`、church_ch02 與 xdotool 減速按鍵實機操作，成功截得三分支畫面 [`docs/figures/church-class-targets.png`](../figures/church-class-targets.png)；畫面文字實際顯示「基本轉職 → portrait 29h / class 13」、「道具 58h → portrait 3Bh / class 22」、「特殊道具 5Ah → portrait 34h / class 21」。
- 2026-07-20 battle progression slice：campaign `Node.Protect` 已資料化，`checkResult` 依 battle node 的 protect 欄位判定敗北，空值維持索爾相容預設；新增 campaign test。另修正升級：原版 DX 是 HIT/EV 共用 raw base，`GainExp` 在已有 equipment base 時同步更新 BaseHIT/BaseEV 與有效 HIT/EV，保留裝備加成並新增 regression test。
- 2026-07-20 AI low-damage slice：依 `docs/knowledge-base/11-enemy-ai.md` 的 `0x15140` 證據，AI 候選目標若預估 `dmg≤2` 直接略過，不會為了微小傷害發動攻擊；若沒有合格目標則保留接近／待命計畫。`aiActUnit` 與 `NextAIPlan` 共用同一套候選篩選，並以固定場景測試邊界值 2/3，避免兩條執行路徑漂移。情境加成、狀態倍率及敵方施法入口仍待後續 RE。
- 2026-07-20 AI spell-entry audit：臨時 capstone 容器 direct disasm `0x15470..0x15618`，並查到呼叫點 `0x13E39`、`0x14F9B`。`0x1548E` 才是函式入口；`0x154D1` 位於其本體，實際流程可見 `0x14B78` 路徑／移動與 `0x12D7B` 演出狀態呼叫，沒有 `Cast` dispatch 證據。已撤回「0x154D1 是施法入口」舊註記；敵方 AI 施法仍待從法術函式反向找真正 callsite。
- 2026-07-20 AI spell dispatch proof：direct disasm `0x15688..0x15880` 與 `0x14F80..0x15220` 證實原版 AI 會枚舉並執行法術命令：`0x1579A–0x157B5` 將 `command>0x0F` 轉為 `spell_id=command-0x10` 呼叫 `0x149F8` 評分；選中後 `0x150D3–0x150F1` 重算同一 spell，`0x15168→0x28784` 播放施法演出。`0x154D1` 仍只是移動函式中段。remake 下一步需把 SpellID／command inventory 與攻擊、治療目標優先級接到 `NextAIPlan`。
- 2026-07-20 AI spell data bridge：remake `battle.State` 新增可注入 `SpellBook`，`AIPlan.SpellID` 以 `-1` 明確表示目前物理／待命計畫不施法；`loadGame` 將已載入的 EXE spell table 複製進 state，並新增 regression test 防止物理 AI 偷生 spell command。刻意未加入猜測性的 spell ranking、治療目標或施法座標；這些要等 command inventory 對映與 `0x15880/0x15B77` 語意定案。
- 2026-07-20 AI spell-family scoring：direct disasm `0x15B77..0x15DA1` 證實法術目標選擇不是通用物理評分：spell `0..12` 掃攻擊目標並累加 8/0x18 等優先分數，`13..16` 掃補血目標，`17..19` 走增益分支，`20..22`、`26`、`27` 走狀態／毒麻分支，部分條件由 `0x1C269` 檢查。現行欄位結論以 constructor trace 為準：magic raw=`unit+0x1a..+0x1d`，`+0x22..+0x24` 是 transient modifier flags；remake 仍不猜接線。
- 2026-07-20 class-change fidelity correction：使用者實測指出轉職結果與原版差距巨大；direct disasm `0x1E529` 尾端確認是 `add word [target], ax`，PTT 實測表亦吻合「舊能力 + 新職 growth row」而非絕對重設。已修正 `ApplyClassChange`：AP/DP/DX/MaxHP/MaxMP 改為累加、Lv 保留、EXP 清零、HP/MP 回滿；campaign/battle 測試通過。外部旁證：[PTT 實測表](https://www.ptt.cc/bbs/Dynasty/M.1185344950.A.91B.html)、[FD2 轉職攻略](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/INDEX.html)。
- 2026-07-20 外部流程盤點：攻略頁逐章列出武器店／道具店／教會／神秘店，至少第4、7、9、14、16、18、19、21章有明確整備設施與隱藏商店證據（[第4章](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/4.html)、[第7章](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/7.html)、[第16章](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/16.html)）。頁面未明文保證「勝利後立即進入」，故只作 campaign town/shop 節點的外部交叉證據，不取代 EXE branch/table；`campaign_full.json` 仍須保留 postbattle→town/preparation→next battle 的可編輯順序。
- 2026-07-20 class-change equipment correction：發現 `ApplyClassChange` 先改有效 AP/DP/MV、再呼叫 `RecomputeAfterClassChange` 時，已有裝備會被重算兩次。現以既有 equipped item 貢獻反推 raw base，再套用已確認的 `0x1b750` stat/equipment synthesis；新增回歸測試證明 AP/DP 不會由 18/12 錯變 21/14，campaign/battle 測試通過。
- 2026-07-20 handoff reconciliation：本檔較早的 church/class-change 條目是歷史快照；其中「Lv=1」、「尚未接 UI／能力寫回」、「church 仍是 placeholder」等描述已由後續 RE 與實作更正。現行權威狀態是：保留 Lv、清 EXP、五組成長累加、target/item/UI/persistent roster 已接；仍待的是 `+0x22/+0x23/+0x24` transient writer 的完整來源、原版實機數值回歸與完整 GUI 轉職操作截圖。
- 2026-07-20 class raw-field audit：`0x1b750` 的 AP/DP/HIT/EV synthesis 會讀 `+0x22/+0x23/+0x24` 的非零旗標分支，但 spawn constructor `0x10f6b..0x10fa5` 先把 `+0x22..+0x27` 清零，且 `0x31602` class path 不寫這些 bytes；它們是後續 transient/effect writer 的欄位，不是 M1–M5 spell bitfield，也不是可直接從 class growth row 匯出的 modifier。remake 暫不猜測接線。
- 2026-07-20 raw-unit pointer/schema 對齊：spawn constructor `0x10f6b..0x10fa5` 直接證實 FDFIELD b13..b16 的 `initial_command_mask` 複製到 runtime `unit+0x1a..+0x1d`；它是 runtime 五位元組 command bitset 的初始四位元組，不是 spell table。runtime `+0x22..+0x27` 另以 memset 清零，後續才由能力流程寫入 modifier flags。因此 `+0x22/+0x23/+0x24` 不是 spells；individual command ID 的玩法語意仍待對照。已同步修正 `03-exe-and-data-structures.md` 與 `11-enemy-ai.md`，避免錯誤 schema 繼續污染 remake。
- 2026-07-20 AI command inventory slice：item EXE row 是 23 bytes，K4 command 位於 raw byte `0x11`（item 79 的 `0x1f`→spell 15）；新增 `campaign.LoadAICommandSpellMap` 與 `State.AICommandSpell`，只資料化 command `>=0x10`，不猜測 AI ranking／治療目標。campaign/battle 核心測試通過。
- 2026-07-20 AI available-spell slice：新增 `State.AIAvailableSpells(unit)`，依 unit inventory 順序把 command map 解析出的 spell IDs 對到 EXE `SpellBook`，去重且忽略未知 spell；此層只重現 command inventory，不改 `NextAIPlan` 的目標評分或施法執行。
- 2026-07-20 AI spell-family candidate slice：新增 `State.AISpellCandidates`，依 direct `0x15B77` family 分支提供 attack(0..12)、heal(13..16)、buff(17..19)、cure(20 解毒／21 祛麻，僅掃對應己方狀態)、status(22/26/27) 的 live/camp 候選掃描；保留 runtime order，不猜原版分數與施法執行。
- 2026-07-20 story script fallback slice：`campaign.Runner.NodeID()` 暴露目前 editable node key；`main.enterNode` 對精確 `story_chNN` generic node 自動載入 `assets/story/chNN.json`，因此 ch04–30 等已有完整可編輯劇本不再只播兩句節點 fallback。named/pre/post cutscene 不套用，避免整章重播；Xvfb GUI package test 通過。
- 2026-07-20 ch02/ch03 handler audit：`ch02_pre` 的四組 dialogue index 已由 `count-aligned.json` 對到 `ch03.json` scene0 lines 0–13，並有 act18/17/19、spawn/pan/layout overrides；`ch02_post` 的 Tino 分支對到 scene1 lines1–5，else 分支對到 lines6–15、JOIN char2、sync/set_chapter3。`ch03_post` 僅有一段已證實對到 `ch04.json` scene3 lines0–3。進一步以 jump-table index3、`load_chapter` 的 FDTXT(章節+1) 規則及 direct push index 證實 `ch03_pre` 的 idx0/idx1 分別是 `FDTXT_004` string #0/#1，新增 `bindings/ch03_pre.json`（scene0 lines0–3、scene1 lines0–4、map3/acting20），並將 `story_ch04` 接回 handler；campaign regression 通過。
- 2026-07-20 ch04_pre slice：同一 FDTXT(章節+1) 規則與 `count-aligned` 證實 handler `0x33049` 的 idx0/1/2 對 `FDTXT_005` → `ch05.json` 的 scene0 lines0–5、scene1 lines0–8；新增 `bindings/ch04_pre.json`（map4 50-slot frontier、pan 3,3/8,14、acting22/21），`story_ch05` 現在實際執行可編輯 pre-handler，不再空 cutscene。campaign/battle 全套 regression 通過。
- 2026-07-20 cross-scene dialogue adapter：`HandlerDialog.Segments[]` 現在保留一個 native FDTXT lookup 的 scene-target 順序，compiler 逐 segment→line flatten 成普通 dialog beats；runtime 每拍依明確 Script/Scene/SceneIndex 載入，沒有文字猜測或跨 scene Count。`FDTXT_006 #0` 的 18 句已通過 scene0(1)→scene1(3)→scene2(5)→scene3(9) regression，`ch05_pre` binding 完整，`story_ch06` 接回 editable handler。
- 2026-07-20 ch06_pre slice：`FDTXT_007` index0/1 都是單 scene mapping（2+6句），handler `0x33169` 的 map6/40-slot、pan 8,1→8,0、acting28/29 已新增 binding；`story_ch07` 接回原版 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch07_pre slice：`FDTXT_008` index0（跨兩 scene、15句）與 index1（2句）由 segments adapter 展開；handler `0x33219` 的 map7/60-slot、pan 7,32→7,23、acting31/32 已新增 binding，`story_ch08` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch08_pre slice：`FDTXT_009` index0/1（2+5句，單 scene）與 handler `0x3327d` map8/60-slot、pan 6,0、acting35 已新增 binding；`story_ch09` 接回原版 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch09_pre slice：`FDTXT_010` index0 跨 scene0/1 共12句，handler `0x3332b` map9/60-slot、pan 10,0 已新增 binding；segments adapter 維持 6+6 line 順序，`story_ch10` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch10_pre slice：`FDTXT_011` index0 跨 scene0/1/2（4+6+2句），index1/2 延續 scene2；handler `0x33367` map10/40-slot、pan 10,7、acting38/39 已新增 binding，`story_ch11` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch11_pre slice：`FDTXT_012` index0 跨 scene0/1（2+9句），handler `0x333f5` map11/60-slot、pan 4,4→11,40、acting40/41 已新增 binding；`story_ch12` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch12_pre slice：`FDTXT_013` index0 單 scene 6句，handler `0x3346b` map12/70-slot、loadch/ch13 script 已新增 binding；`story_ch13` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch13_pre slice：`FDTXT_014` index0 單 scene 4句，handler `0x3347c` map13/70-slot、pan 20,20、loadch/ch14 script 已新增 binding；`story_ch14` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch14/ch15 boundary：`ch14_pre` 含已證實的 `roster_has(12)`，其 EBX/EAX 動態 text index 尚待 direct control-flow mapping，暫不猜接線。下一個無動態分支的 `ch15_pre` 已完成：FDTXT_016 index0 16句、map15/60-slot、ch16 script，`story_ch16` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch17_pre slice：`FDTXT_018` index0/1/2（7+4+13句，segments 保留 scene 邊界），handler `0x335da` map17/70-slot、pan 16,4、acting54/55 已新增 binding；`story_ch18` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch18_pre slice：handler `0x33475` 的實際 pre 呼叫只有 FDTXT_019 index0（8句，scene0），已新增 map18/70-slot 與 ch19 script binding；`story_ch19` 接回 pre-handler，campaign/battle regression 通過。其餘 FDTXT_019 strings 不在此 handler 呼叫，未擅自播完整章節。
- 2026-07-20 ch19_pre slice：handler `0x33475` 的 FDTXT_020 index0（17句，scene0）已新增 map19/70-slot、ch20 script binding；`story_ch20` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 ch20_pre slice：handler `0x33475` 的 FDTXT_021 index0（17句，scene0）已新增 map20/80-slot、ch21 script binding；`story_ch21` 接回 pre-handler，campaign/battle regression 通過。
- 2026-07-20 save durability slice：save JSON 改以同目錄暫存檔後 `rename` 原子替換，避免戰後 town／商店／整備節點存檔時因程序中斷留下半份 JSON；新增完整內容與暫存檔清理 regression test。campaign/battle 核心測試通過；GUI package 測試在目前容器缺少 ALSA/X11 headers，需用含圖形依賴的驗證容器重跑。
- 2026-07-20 external flow cross-check（非 EXE 硬證據）：GameFAQs、PTT 與中文攻略逐章列出 Town of Rod、Sara Village、武器店／道具店／教會／旅館／神秘商店，以及戰後角色加入與下一段旅程；這支持保留 postbattle→town/shop/church/preparation 的可編輯節點，但精確順序仍以 `campaign_full.json` 與 direct disassembly 為準。參考：[GameFAQs walkthrough](https://gamefaqs.gamespot.com/pc/582384/flame-dragon-2/faqs/31054)、[第4章攻略](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/4.html)、[第16章攻略](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/16.html)。
- 2026-07-20 ch21_pre slice：handler 的 FDTXT_022 index0 實際為 11 句、scene0；binding 已補上 map21/70-slot、pan(16,28)、acting67 與 ch22 script/party scenario，`story_ch22` 改接 editable pre-handler。新增 compiler regression，確認段落順序、載入、鏡頭與演出資源；campaign/battle tests 通過。
- 2026-07-20 web survey（僅作外部交叉證據）：公開資源頁確認原版以外部 `FDFIELD.DAT`（含 mod 目錄替換）提供場景資料，故後續 loader 應保留 DAT provider/override layer，不把所有內容假定在 EXE。攻略資料亦明載章節間先進戰鬥準備，可購買／換裝、教會復活、存讀檔後才進下一章；campaign graph 必須維持 battle→postbattle/town/preparation→next battle。參考：[FD2 資源頁](https://chiuinan.github.io/game/game/intro/ch/c31/fd2.htm)、[準備畫面介紹](https://leoandvc.pixnet.net/blog/posts/13079662050)、[第七章商店觸發](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/7.html#L55-L58)。尚未找到可靠公開 DAT binary 格式，格式結論仍以本地檔案與反組譯為準。
- 同輪補充：GitBook 的 [FD2.EXE 修改表](https://jaceju-favorite-games.gitbooks.io/fd2/content/modify/FD2_EXE.html) 可作低成本行為 oracle（入隊 ID、行動後再動、隨時存檔、等級上限、寶箱持久化）；只採其可對照的行為線索，不把社群 byte patch 當 loader 格式證據。
- 2026-07-20 ch22_pre control-flow slice：`0x336b5` 的 `EBX` 不是 roster_has，而是 `repeat_hint(limit=16, loop_back=0x336b4)` 的固定清理迴圈；compiler 現在把 `unit_slot_expr:"ebx"` 明確展開成 slots 0..15，並以 active loadch slot_count 驗證。這解開 ch22 的動態索引阻塞；`0x24618` 視覺效果與 `0x11df2` palette/fade 仍保留 unknown，故 story_ch23 尚未猜接。
- 2026-07-20 palette/transition RE correction：`0x11df2(start,end,delta)` 對 `[0x53a65]` 每色 RGB 加 delta、clamp 0..0x3f 後逐項寫 VGA DAC，是一次性 `palette_update`；`0x11d40` 才是減亮 fade-out。compiler 已將 native `0x11df2` immediate calls lower 成 `palette_update`（ch22 呼叫皆 delta=0，runtime 保留順序，不誤當黑幕 fade）。`0x24618` 定案為 `(x,y,palette_delta,step)` 固定 9-frame transition/reveal（每幀 present、5ms、尾端 delay500ms），仍待 indexed transition renderer，未猜接。
- 2026-07-20 ch23_pre slice：handler `0x338ce` 的 FDTXT_024 index0/index1 共 14 句（scene0，5+9），map23/70-slot、四段 pan(0,4→0,22→26,24→26,2)、spawn group1 與 ch24 script 已新增 binding；`story_ch24` 接回 editable pre-handler，compiler/campaign/battle regression 通過。
- 2026-07-20 ch24 transition/audio slice：`0x24b4d(count)` 完整 RE 確認為先 terrain/main redraw，再以兩個 `0x1c8` buffer 交替 present、每幀 20ms；ch24 calls 為 20/20/20/60（400ms/1.2s）。compiler/runtime 已新增 `transition_reveal`，binding 將 `load_res` FDOTHER#88、四次 `play_sfx(priority=1,index=1)` 接到 `battle_88_01.wav`，並把 `0x1d50a` 的 index=-1 stop 與 `0x1a80a` release 接回 handle；`story_ch25` 已切回 editable handler。剩餘差異只在 indexed double-buffer visual adapter（目前保留 exact count/timing，PNG renderer 每幀重繪）。
- 2026-07-20 ch25_pre slice：FDTXT_026 全章因後續分支／raw utterance 與 authored line 數不一致，未宣稱全量 count-aligned；但 handler 實際呼叫的 string0 可直接對到 `ch26.json` scene0 12 lines。已新增 ch25_pre binding（map25/70-slot、pan 9,39、acting76、dialog line0/count12/scene0）並將 `story_ch26` 接回 editable handler；後續 FDTXT_026 分支仍待條件控制流 mapping。
- 2026-07-20 ch26_pre slice：逐字解析 FDTXT_027 證實 handler 的 idx0/3/4/5/6/7 分別對到 `ch27.json` scene0 的 lines 0–3、4、5–6、7、8–12、13–21；新增 `bindings/ch26_pre.json` 與六組 direct line/count overrides，`story_ch27` 接回 editable pre-handler。`0x24b14(100)` 依既有 LE disasm 是天空之鑰 item `0x64` 的 16-slot inventory gate，仍保留 unresolved branch/effect，不把 gate 猜成自動跳轉。
- 2026-07-20 ch27_post slice：`FDTXT_028` 已 count-aligned，handler idx7 (`0x231e5`) 精確對到 `ch28.json` scene1 lines 11–15；新增 `bindings/ch27_post.json`，掛在天空之鑰 present branch 後、進 preparation_ch28 前。sync_party/set_chapter 原語保留原順序。
- 2026-07-20 ch28_pre audit→resolved：FDTXT_029 idx7/idx8 分別精確對到 `ch29.json` scene1 lines 5–12（8句）與 scene2 lines 0–5（6句），pan(9,56)→(216,1344)、acting86 已建 binding。Capstone direct disasm 證實 `0x35822(x,y,group)` 為 pan→spawn→delay300→palette(0,255,0)→delay200→palette(0,255,0)→redraw；compiler 已 lower 且 `story_ch28` 已接回 handler，無 unresolved issues。
- 2026-07-20 ch26_post gate audit：`0x25186` 後 `cmp eax,-1 / JE 0x25348` 證實 item `0x64` 缺失會進 FDTXT_027 idx13–16 離別支線，命中才繼續 idx9–12 正線並 `sync_party/set_chapter(27)`；campaign gate 現已承載缺匙對話 scene→ending，ch26_post 的大量 visual/effect unknown 仍待拆解。
- 2026-07-20 missing-key branch slice：新增 `ch27.json` 可編輯場景「缺少天空之鑰的離別(分支)」，收錄 FDTXT_027 idx13–16 的 17 句離別對話；`inventory_gate_ch27_sky_key.if_missing` 現在先進該 scene，再接 `ending_ch27_no_sky_key`，不再用 generic ending 吞掉原版對白。`0x25052/0x24618/0x1c2da` 視覺／系統效果與 `0x22253` 的 runtime adapter 仍刻意保留為待辦。
- 2026-07-20 isolated RE toolchain：新增 `tools/docker/fd2-cap.Dockerfile`，建立本機 `fd2-cap-local` image（Python 3.12 + capstone 5.0.3）；所有後續 `disasm_le.py` 以 repo read-only mount 執行，不污染 host Python。實際 Capstone disasm 確認 `0x35822(x,y,group)` 是 pan→spawn→delay300→palette(0,255,0)→delay200→palette(0,255,0)→redraw；compiler 已 lower，ch28_pre binding 無 unresolved issues，`story_ch28` 已接回 editable handler。
- 2026-07-20 dialogue pagination slice：對話長句翻頁現在以 10 幀可編輯平滑上捲呈現（舊頁上移、新頁由底部進入，框內 clip），動畫期間 Enter 不會跳過頁面；新增 `dlg_test.go` 狀態 regression。核心 campaign/battle 測試通過；GUI package 實測仍受容器缺 ALSA/X11 headers 限制，待圖形依賴容器重跑。
- 2026-07-20 ch29_post audit：Capstone 直接確認 `0x12cea` 是 X-first/Y-second focus(22,23)；`0x24618` 是 palette_delta=10、step=8 的 9-frame alternating-buffer transition；`0x25089` 是 persistent roster cleanup（清 transient、回填 HP/MP），`0x11df2` 是 dynamic 0x3e→0、delta0 palette loop，`0x17aa9` 是 tick busy-wait，`0x2bce5` 是專用 ending renderer。新增 staged `bindings/ch29_post.json` 與四組精確對白 mapping（FDTXT_029→ch29 scene2 lines6–7；FDTXT_030→ch30 scene0 lines0–14），但因 layout/load-text/focus/transition/ending native ops 尚未全部 lower，暫不接 campaign runtime。
- 2026-07-20 focus lowering slice：`0x12cea(x,y)` 的 direct Capstone 證據已接入 compiler，保留 X-first/Y-second 語意並 lower 成 tile-step pan；新增 regression，ch29_post staged binding 的 focus unknown 已可解析，其餘 transition/roster/ending native ops 仍 fail-closed。
- 2026-07-20 ch29 focus slice：`0x12cea` 已依 direct LE ABI（handler PUSH 順序為 y,x）lower 成 tile-step camera pan(22*24,23*24)，並有 staged handler regression；其餘 ch29 post native cleanup/transition/ending 仍待完成，故 campaign 尚不啟用整段 handler。
- 2026-07-20 persistent roster cleanup slice：`0x25089` 已保留為獨立 editable `reset_persistent_roster_state` beat，不與 `sync_party` 混用；runtime 會清除 transient 行動／位置／buff／中毒／麻痺／封印狀態並以 MaxHP/MaxMP 回填。這是 postbattle 進 town/shop/preparation 前的持久隊伍整備基礎，仍需補 direct handler binding 與 runtime regression。
- 2026-07-20 `0x22253` correction：Docker/Capstone 追到 wrapper 內部實際為 6 次 render+present、每次 10ms，尾端兩次 tick(1)；不可再稱 11-frame 或用 `layout_units` 代替。尚無 DSL 等價 primitive，先 fail-closed，待建立 `native_22253` place/present adapter。
- 2026-07-20 `0x17aa9` timing correction：Docker/Capstone 確認它讀 DOS BIOS tick counter（約 54.9ms/tick），不是 60Hz 單幀；compiler 以每 native tick 3 個 remake display frames（約50ms）保留等待邊界，並加 regression，避免把 ch29 尾端 busy-wait 壓成 16.7ms。
- 2026-07-20 `0x22253` renderer audit correction：Docker/Capstone 確認 immediate `0x51` 是 FDOTHER **十進位 #81** 的 nested `LLLLLL` entry（outer 18710 bytes、directory first-word `0x12`；nested payload #1=9782 bytes），不是 #51 音訊或 PCM 資源；`0x11eee` 後續 nested data selection 尚未閉合，`0x22547` 再用 `0x53a6d` descriptor table 做 indexed `0x22046` blit/present，loop 為 6 次、每次 10ms，尾端兩次 BIOS tick。現有 PNG story renderer 沒有 indexed buffer／resource adapter，故 `unit_present` 仍 fail-closed，禁止降級成 layout 或 generic redraw。
- 2026-07-20 `0x2bce5` ending renderer audit：Docker/Capstone 確認它載入 FDOTHER `#0x36`，建立 320×200 雙 buffer，先 ANI/圖像 compositing，再做 0→63 的 palette fade（每步4ms）、2000ms停留、依 chapter 26/29 分支繪製不同 ending text/figures，最後以 200×4ms fade-out 與 1000ms delay 收尾；不能以 generic `ending` 或普通 fade 取代，需建立 evidence-backed ending_renderer adapter。
- 2026-07-20 external town-flow survey（subagent，非 EXE 硬證據）：中文攻略逐章列出羅德鎮、塞拉村、普里茲港等戰間武器店／道具店／神秘商店／教會與整備；第2章明載保住村民後戰後獎勵力量藥水，第6章明載戰後貝克威加入。這強力支持 battle→postbattle→town/shop/preparation→next battle 的可編輯圖，但攻略無法單獨證明「勝利後自動進城」的程式級轉移；精確順序仍以 `campaign_full.json` 與 direct disassembly 為準。參考：[青衫 FD2 攻略](https://chiuinan.github.io/game/game/intro/ch/c31/fd2/fd2/fd2.htm)、[PTT 攻略轉載](https://www.ptt.cc/man/Old-Games/D9EE/D31B/D56E/M.1099301522.A.DE5.html)、[GitBook 第7章](https://jaceju-favorite-games.gitbooks.io/fd2/content/walkthrough/7.html)。
- 2026-07-20 ch29 cleanup slice：`0x25089` 已 lower 成可編輯 `reset_persistent_roster_state`，runtime 依 direct disassembly 清 persistent roster transient/acted 欄位並將 HP/MP 回填 MaxHP/MaxMP；與 `sync_party` 分離，避免把戰後投影誤當終盤清理。campaign/cmd regression 已補上；GUI package 仍受容器缺 ALSA/X11 headers 限制。
- 2026-07-20 external town-flow survey（subagent，非 EXE 硬證據）：GameFAQs 明載第14章對話「途中有小鎮，先休息」，直接支持 battle→town/rest；第22章明載至第26章前沒有 rest/buy/sell，故 ch23–25 不得強插 town/shop。其餘第2、5、6、7、9–22、26–27章有旅館／教會／武器店／道具店／秘密店旁證；攻略無法單獨證明 handler 觸發時機，精確順序仍以 `campaign_full.json` 與 EXE/資產為準。
- 2026-07-20 ch29 tick slice：`0x17aa9(1)` direct RE 的全域 tick busy-wait 已 lower 成 editable `delay(frames=1)`，保留 ch29 redraw loop 的每次 60Hz 邊界；compiler regression 通過，`0x24618`/`0x2bce5` 仍維持 fail-closed。
- 2026-07-20 ch29 palette-loop slice：`0x11df2(EBX,255,0)` 的 direct loop（EBX=0x3e..0、每次後接 4ms wait）已 materialize 為 63 組 editable `palette_update` + `delay(ms=4)`，不再把 register expression 靜默丟失；其餘 ch29 unresolved 降至 layout/0x24618/load-text/pan/0x2bce5。
- 2026-07-20 0x24618 indexed-transition audit：Capstone 確認 9→1 frame、每幀 descriptor/double-buffer copy、5ms tick，尾端 500ms；之後 32 次 `0x11df2(start=0,end=255,delta=0..62 step2)` + 4ms，這是整張 VGA palette brightness ramp，不是 `(0,255,index)`。新增 `HandlerIndexedTransition` editable metadata 與 explicit binding resolver/compiler test；PNG renderer 仍 fail-closed，尚未接 campaign。
- 2026-07-20 0x24618 schema completion：metadata 另保留 fixed `source_y=0`、`blit_width=0xc0`、clip `0x138×0xc0`，以及 tile/source step；compiler 只接受完整 9-frame/500ms/palette timing，避免把 descriptor copy 簡化成普通 fade。
- 2026-07-20 ch29 post `0x1088d` correction：先前將 `0x25870 → 0x1088d` 縮窄 lower 成 `load_ch_text(ch30.json)` 已撤回，因 Docker/Capstone 證實本體不只載 FDTXT：它依 chapter 載三個 FDFIELD resource、讀 map control、重建 `0x1e00` runtime unit buffer、從 persistent `[0x53bf7]` 複製 own records、套 own-deploy coordinates 並 spawn groups。現已以既有完整 `loadch` state（chapter30/map29/roster70/ch30 story+scenario）重新 lower，compiler regression 明確鎖住不得退回文字-only；handler 仍因 layout、transition、ending 等 unresolved ops fail-closed，尚未接 campaign。internal chapter 29 是最終戰 handler，`0x2bce5` 返回後自迴圈，不會進 generic preparation；現行 final battle→generic ending 暫時略過此 handler。
- 2026-07-20 ch29 post layout audit：Docker/Capstone 證實 `0x257b4 → 0x233c6` 使用三個固定 20-byte arrays（slots 0..19 的 X/Y/pose）與 camera `(16,18)`；數值已可重取，但 remake 尚未證實 20-slot `handlerUnitAt(slot)` 身分等同 native runtime array，且 campaign 未接這個 native post handler。因此不建立猜測性 `layout_units` binding，維持 fail-closed；先需補 roster frontier/identity evidence。
- 2026-07-20 terminal-flow reconciliation：`0x25970 call 0x2bce5` 之後的 `EB FE` 是 `jmp 0x25975` self-loop，證實 `0x25757` 不會返回通用戰後/整備流程。它對應 internal chapter 29（玩家面向的 map29 最終戰）；`preparation_ch30` 仍是最終戰**之前**的既有節點，不能把此 post handler 接到 map28 的 `battle_ch29` 勝利。
- 2026-07-20 map29 final roster provenance：`0x1088d` 證實 `[0x53a45]+slot*0x50` slots 0..19 先由 persistent `[0x53bf7]` ordinal 0..19 複製，再寫 map29 own-deploy ordinal positions；`0x233c6` 只覆寫該同一 buffer 的 x/y/pose。`0x1b750` 是裝備／衍生能力 synthesis，不改 identity。進一步 direct `0x112a5` 證實 JOIN 以 `[0x53bfb]*0x50` append 一筆 persistent record 後遞增 count，故正常遊戲 ordinal 就是首次 JOIN chronology；remake `partyJoinOrder`／`reorderScenarioParty` 的角色順序方向正確。map JSON row order 仍不得替代此 persistent order。
- 2026-07-20 final layout materialization：將 `0x257b4 → 0x233c6` 的三個 native 20-byte arrays 完整寫入 editable `layout_units` binding（slot0..19、camera 16×24/18×24）；compiler regression 鎖定首兩筆、末筆、camera。這只保存已證實資料，不能繞過終局 handler 的 runtime array/renderer gate；其餘 unresolved ops 仍阻止 campaign playback。
- 2026-07-20 final camera pan：`0x25933 push 12; 0x25935 push 11; call 0x135dd` 依 native x-first/y-second ABI lower 為 editable tile-step pan `(264,288)`；compiler regression 鎖定此 final-map camera target。它不影響仍 fail-closed 的 transition/ending path。
- 2026-07-20 final indexed-transition callsite：`0x233c6` 先初始化 viewport origin `(16,18)`、focus `(22,23)` 經 `0x11bfa/0x11b9b` 將 scroll offsets 寫為 `(6,5)`，故 `0x25848` 的 dynamic args `[0x53ab9], [0x53abd]+1` 精確為 `(6,6)`。完整 9-frame descriptor/palette metadata 已以 editable `indexed_transition(tile=6,6; source=10,step8)` binding 保存；runtime adapter 尚未具備 indexed descriptor renderer，仍 fail-closed。
- 2026-07-20 ending asset audit correction：`0x2bce5` 的 `push 0x36` 是十六進位 immediate，實際由 `0x111ba` 載入 FDOTHER index **54**，即 `FDOTHER_054.bin`（263655B、111-frame table），不是 `FDOTHER_036.bin`（31008B、408×138 的無關資源）。`0x111ba` 已直接確認只讀 archive entry、沒有解壓/轉碼；`0x2935b` 因而直接吃 raw #054。frame descriptor 的 `+0/+2`=destination dx/dy，`+9/+11`=real width/height，payload `+9` 交給 `0x4e63d`。新增純 Go `internal/fdother` fail-closed parser/blitter：透明 skip 與 dither 都保留既有 indexed destination，不能像 PNG exporter 寫 index0；合成 RLE 與玩家素材 #054 frame geometry regression 均已覆蓋。其 `DecodeResource(FDOTHER.DAT, 0x36)` archive loader 另以 raw #054 byte-for-byte 驗證。ANI `#2` 已有 `internal/afm` decoder（26 frames），但完整 branch/text/ANI schedule與 runtime bridge 尚未接入，故 ending 仍 fail-closed。
- 2026-07-20 ending #054 schedule audit：`0x2bce5` 的可證實部分為 frame0→offscreen/copy、1000ms、palette `(0,255,63)`、frame9、`63..0`×4ms fade、2000ms hold；不透明文字 helper branch 後有三輪 `63..0`×4ms +200ms，frame12..108 每幀20ms；之後第一段 40 次 640-stride frame-pair composite，第二段 200 次 frame-pair/VGA composite（每次20ms，final 64 次的 `0x11d40` first arg 才由0改1）。已將 #054 全111幀以原版透明分支實際 decode 回歸。`0x2c39b` 只證實兩個 caller args 會轉交 `0x1956b`，未證實為字串 ID 或位置，故 timeline 只能將其 opaque 保存、不能猜成 editable dialogue；ANI/後段戰鬥動畫 bridge 仍 fail-closed。
- 2026-07-20 editable terminal-prefix IR：新增版控 `remake/assets/endings/native_2bce5.json`（僅 RE choreography，沒有原版美術）及 `internal/ending` loader。它將所有已釘死 prefix calls 存為可編輯 JSON，including #054 frame0/9/12..108、palette ramps、兩個 `0x2c39b` chapter branch 的 **opaque arg pairs**、兩段 exact loop bound/formula。status 固定 `recovered_prefix_only_fail_closed`，loader 的 `Ready()` 只在明確 `ready` 才可真值；現階段 regression 鎖住不得被 campaign 誤播。下一輪要先釘死 0x2c39b 的字串/位置與 buffer/palette helper，再談 renderer bridge。
- 2026-07-20 ending text-helper slice：`0x2c39b` 在保存 EBX 後將 caller arg1 交給 `0x1956b`，再以 caller arg2 呼叫 `0x15f84([0x53a79], idx, ...)`；`0x15fb9` 的 FDTXT offset-table lookup 證實 arg2 是 **current FDTXT string index**。終局 loader 已選 `FDTXT_030`，故 final-route else branch `(37,2),(21,3),(26,4),(105,5),(32,6)` 精確 count-align 至 `ch30.json` scene1 lines `0..5,6..7,8..9,10..11,12`；後段 `(45,7)` 對應 line13。timeline 現把它們做 editable `else_dialogue` blocks；arg1 僅記為 `visual_resource_index`，因 `0x51a70` archive 類型尚未直接命名，不能猜成 portrait。chapter==26 的另一臂 indexes17..20 仍依當時 current FDTXT 待另行 mapping；ending status 不變。
- 2026-07-20 chapter26 ending-text closure：`0x2545d → 0x2bce5` 在 `ch26_post` 內沒有後續 LOADCH，故 `0x2c39b` chapter==26 branch 的 current table 是 `FDTXT_027`。Docker-isolated raw string decode 證實 idx17/18/19/20 依序正是 `ch27.json` appendix scene（index3）的 lines1/2/3/4：「看！是黃金城」到「一個沒有人找得到的地方」。timeline 的 `then_dialogue` 已保存這四個可編輯 blocks，並為每個 exact visual-resource index、FDTXT string、scene/line/count 建 regression；不再把 bad ending 只寫成 generic text。`0x51a70` resource type和 renderer bridge仍未證實，維持 fail-closed。
- 2026-07-20 ending portrait-type closure：既有 doc14 的 direct trace 已明載 `0x51a70="DATO.DAT"`；本輪核對 `0x2c39b`，其 arg1→`0x1956b`→`0x111ba(0x51a70,arg1)`→DATO decoder `0x4e8e1`。因此 ending timeline 的第一參數從保守 `visual_resource_index` 正名為 `portrait_id`，而非猜測的背景／figure id；所有 final/bad-ending dialogue blocks 的 DATO IDs 均保留。這解除文字 helper 的兩個 ABI 語意，但仍未提供 320×200 ending compositor／palette/ANI bridge，status 維持 fail-closed。
- 2026-07-20 `0x2935b` decoder contract：ending callsites 證實 source 是 frame-table container；frame `n` 的 descriptor 位址來自 `base + uint32[base+8+n*4]`，`u16 width/u16 height` 位於 descriptor `+0/+2`，RLE payload 由 `+9` 以 transparent `-1` blit 至指定 320/640 stride buffer。`0x2bce5` 已釘出 frame0→offscreen、frame9→screen fade、12..108 timed sequence與後續 double-buffer interleave；仍須把這些 calls/branch text變成資料化 schedule後才可接 runtime。
- 2026-07-20 ending prefix player slice：新增 `internal/ending.Player`，以 presentation millisecond clock 執行 `frame0→offscreen/copy→1000ms→ANI#2`（ANI first frame immediate、每後續幀100ms）。Docker `fd2-cap-local` read-only disasm 直接證實第一 ramp loop 是 `0x11df2(0,255,EBX)`、EBX=63..0、每步4ms；player 已以既有 clamp/additive DAC helper 實作它，玩家 `FDOTHER.DAT #54`/`ANI.DAT #2` integration regression 可走到第一個 `native_text_branch_opaque`。之後 native text 或 composite loop 才會以 `PlaybackBlocked` 停住並保留最後 indexed VGA，沒有 generic fallback。`cmd/fd2` 的 `FD2_ENDING_PREFIX=1` 是獨立 320×200×2 Ebiten oracle（`FD2_FDOTHER`/`FD2_ANI` 可指定素材），沒有接到 campaign terminal handler。host 無 capstone、`/tmp/fd2cap` 不存在。下一步是將已定案 DATO/FDTXT text blocks 做成阻塞式 native sequence UI，再處理後段 composite。
- 2026-07-20 native ending dialogue bridge：`Player.BlockedDialogue(chapter)` 只對 `native_text_branch_opaque` 交出 timeline 的 exact then/else blocks；preview 以 `FD2_ENDING_CHAPTER=26|29` 明確選擇 native branch，使用 `loadStoryScriptAt(chNN.json, scene_index)` 的 line/count slice，並用 timeline `portrait_id` 覆寫 transcript speaker，符合 `0x2c39b` arg1=DATO、arg2=FDTXT index 的 direct ABI。preview bypass map loading 時仍載 DATO portraits/font，Enter/Space 可逐頁／逐句；對話清完仍保持 player blocked，沒有越過未復原 composite。
- 2026-07-20 native text resume boundary：preview 在最後一頁最後一句被確認後才呼叫 `Player.ResumeBlockedDialogue()`；此 API 只接受 `native_text_branch_opaque`，會清 block、segment+1 回到 running。任何其他 opaque op（含 composite）都不能 resume，確保 UI 不會以「按完對話」跳過尚未反組譯的 renderer。
- 2026-07-20 text-post palette repeat：timeline 的 `palette_ramp_repeat`（native 3× EBX=63..0、4ms/step、每輪後200ms）已在 `NewPlayer` 展開成可時鐘驅動的三組 `palette_ramp`/`delay_ms`，保留每個 DAC mutation 與 hold，不降級為 fade。完成後下一 gate 是已知但尚未 player 實作的 frame12..108 20ms sequence。
- 2026-07-20 timed ending frames：`blit_frame_sequence` 現由 player 展開 frame12..108 的逐幀 transparent VGA blit + 20ms delay，完成後可到第二個 `native_text_branch_opaque`；composite loop 的文字欄位改名 `first_frame_formula`，避免與可執行 sequence `first_frame:int` 同名造成 JSON unmarshal ambiguity。`0x2bf60` 的 640-stride composite 已有精確 adapter，但後續 `0x2c172` montage 仍 blocked。
- 2026-07-20 ending composite correction：`0x2bf60` 和 `0x2c0c5` 都以 `(i%4)+1`、`(i%4)+5` 循環取兩組 frame；先前資料中的 `floor(i/4)+1` 是轉錄錯誤，已修正並以 timeline regression 鎖定。200-pass loop 完成後仍只允許到 `0x2c172` gate，絕不把未恢復的 finale montage 當作完成。
- 2026-07-20 composite helper closure：Docker-only Capstone 確認 `0x11eb0(dest,destStride,src,srcStride,bytes,rows)` 是逐列 copy。第一個40-pass loop 已完整釘死：`EBX`=320×200 background、`ESI`=640×200 work；每輪先 EBX→Work viewport x=160，再將 frames `(i%4)+1`／`(i%4)+5` 以 stride640 blit 到 primary/secondary origins，20ms 後 present Work[x=160..479]。primary 初值290，i0..24每輪-4、i25..39每輪-2；secondary 初值80、每輪+2。完成後 second loop 幾何也已知為 Work 320-stride pair；唯一未證實的是其 `0x11d40` palette helper 語意。下一步可安全實作 `BlitAt`／`CopyRect`，不需再猜 buffer layout。
- 2026-07-20 composite scheduler：`Player` 已接 first 40-pass `0x2bf60` loop，逐輪 `Composite40(i)` 後等待20ms，完成才落至第二個 text gate；source 不是 `0x2bf60` 的 composite 仍必定 blocked。完整 internal ending regression 已通過。
- 2026-07-20 `0x11d40` closure：Docker Capstone 直接確認它讀 `[0x53a65]` 的基準 RGB DAC、逐分量做 `base-delta` clamp 到0，再寫 VGA DAC；不是對目前 palette 累加/減。第二200-pass caller 的 EDI 前136輪為0、最後64輪為1。實作第二 loop 必須保留 baseline palette snapshot，不能誤用破壞式 `0x11df2`/`PaletteDelta`。
- 2026-07-20 finale `0x2c405` phase-0 control-flow closure（Docker-only Capstone）：handler 先 `load_ch_text(30)`，alloc/clear `0x36b00` bytes staging buffer，並由 `0x15f84` 將 native text composite 寫至 `staging+0x12c30`；接著正好500次 loop。每次以 `0x11d40(0,255,BL)` 套 baseline palette，從 `staging + iteration*320` 複製 320×200 到 VGA，並 wait 1ms。`BL` 初始40；iteration≤300 時每5 tick 在非零時減1，之後每5 tick 加1。staging glyph path 與 ABI 已恢復，但可執行範圍仍只到後續 `0x2c548` montage gate，不能以空白 scroll 或 generic ending 取代。
- 2026-07-20 finale phase-0 script correction：先前把 `0x2c469` 的 `0x2c` 誤投射到 FDTXT_030 logical #44，已撤回。`0x2c405` 先 `load_ch_text(30)`，而 `0x1088d` 的 resource rule 是 chapter+1，所以 current table 是 **FDTXT_031**；其 raw offset table 有46項，`0x15f84` arg2=`0x2c` 正是合法實體 string #44。raw bytes decode 為「在亞克斯王國宮廷中…各奔前程…」的後日談跑馬燈前言，已對位跨資源重用的 editable `ch32.json` scene0 line0。`native_2c405.json` 與 raw-resource regression 已改為 `FDTXT_031/#44`；完整 finale montage 未復原前，`Ready()` 仍固定 false。
- 2026-07-20 `0x4ea2a` glyph ABI closure：Docker-only Capstone 顯示 arg1=1bpp font base、arg2=glyph index（`index*32`）、arg3=destination、arg4=stride、arg5=foreground、arg6=shadow、arg7=optional background。每 set bit 寫 foreground，並寫左一格／下一列 shadow；arg7 非零時才填整個16×16 cell。`0x15f84` 的 four shifting `push [esp+0x50]` 還原為 caller arg4..7；finale `0x2c469` 因此是 stride320、foreground `0xCD`、shadow `0x4C`、background0。`internal/fdtxt.BlitNativeGlyph` 已逐 pixel regression；仍不可把此 primitive 當作完整 `0x15f84` control-code renderer。
- 2026-07-20 finale phase-0 glyph composition correction：FDTXT_031 physical #44 的130 words 含121個 glyph + 9個 `FFFE` soft line breaks（末尾 FFFF terminator 不在 parser words）。`0x15f84` 的 FFFE path 是 `destination + (++line)*arg8*stride`；本 caller arg8=`0x19`，故每行跳 `25×320` bytes，而非自然 buffer wrap。`ComposePhase0Text` 現精確套此規則並以 FDOTHER #4 / CD/4C/0 style blit；其他 FFxx 仍拒絕，phase readiness false。
- 2026-07-20 finale phase-0 bridge：Docker/Capstone 重驗 `0x2c405` 會在 `0x2c4b4` 前保留前段 indexed presentation 的 DAC，首 pass 呼叫 `0x11d40(0,255,40)`，並在 `0x2c172` 先清 VGA。`Player.EnableRecoveredPhase0` 因此不接外部便利 palette：僅當同一 compositor 已由 `PresentANI` 捕獲原版 palette 才能 hand-off；後續 500 pass 完成會停在 `0x2c548` 的獨立 montage gate。無 baseline、其他 source、或 phase asset 不完整都仍 fail-closed。
- 2026-07-20 finale phase-0 scheduler closure：`0x2c4d6` 的 `[esp+0x20]` 因前面三個 pushes 實際回指 loop local `[base+0x14]`，即 i；source 是 `ESI+i*320`。i=0 先 present palette delta40 / row0，之後若 i<200 且 i%5=0、delta非零便減；`i<=300` 直接 wait1/inc，i>300 後 i%5=0 才加。`Phase0Player` 以此 500×1ms cadence 實作且測試 i0/i1、i195、i305、i499；它結束時不跳進 `0x2c548`。
- 2026-07-20 post-composite boundary：`0x2c172` 後不是 handler return：先 free work、clear/present、呼叫 `0x2c405`，再載 FDOTHER #60/#58/#57/#59、呼叫 full battle renderer `0x28a6c` 與更多 palette/tick choreography。現行 player 的 recovered prefix 到200-pass composite為止；不得把 `PlaybackCompleted` 宣稱為完整 native ending 或接 campaign terminal route，後段應另建 editable phase/RE。
- 2026-07-20 finale montage first slice：`0x2c405` 先 `loadch(30)`、alloc/clear `0x36b00` staging buffer，執行500 native ticks 的 baseline palette/scroll choreography；再 alloc 0x1f400 + two 0xfa00 buffers、載 FDOTHER #56，並以 native unit records 載 FIGANI/DATO resources、`0x29164`/`0x2b9a1`/`0x28a6c` battle render path 作多輪 320×200 present。這是獨立 finale-montage phase，不可降級重用一般 battle scene；目前只記錄資料邊界，仍 fail-closed。
- 2026-07-20 finale `0x2c548` first party-cycle closure（Docker-only Capstone）：0x2c551/560/573 依序 alloc 0x1f400（320×400 staging）、0xfa00、0xfa00；`0x111ba(TAI.DAT,#3)`、`0x111ba(FDOTHER.DAT,#56)` 後先貼 backdrop。更正 TAI#3：raw bytes 恰為 `0A00 0300 C9C9C9`，即 10×3 全 transparent RLE placeholder，**不是**可見 platform，故 `0x29164` 中該參數的 renderer role 尚未猜定。迴圈 index 由 `[0x53bfb]-1` 向下，但 native 選 unit 不是 identity：`i==0→slot1、i==1→slot0、else→sloti`，再以 `[0x53a45]+slot*0x50` byte `+7` group 形成 FIGANI `group*3+1` 和 `group*3`。`0x29164` 後先有 `0x2b9a1(F0,-1)` 20×1ms loop，再有 `0x2935b(F1,frame)` 逐 descriptor `+6` delay loop，才進 portrait/text/input branch。以上結構進 `assets/endings/native_2c548.json`；既有 Ebiten RGBA battle renderer 只有 group asset naming 可重用，不能替代 native indexed 0x29164/0x2935b composition，gate 維持 `0x2c5e3`。
- 2026-07-20 finale `0x2c548` portrait/text closure（Docker-only Capstone）：後段 DATO resource=`unit[+7]`；current `[0x53a79]` 是 FDTXT_031，#10「姓名：」→`staging+0x16e9`、#11「職業：」→`+0x2fe9`、`unit[+8]+0x0c`（或 special #45）→`+0x7d08` epilogue。permanent `[0x53a7d]` 是 **FDTXT_000**（不是001），`unit[+8]+1`→`+0x171b` character name、`unit[+0x20]+0x96`→`+0x301b` class name；全部用 stride320/CD/4C/transparent glyph style。`0x10620` kbhit 只會令 outer counter=1，窗口完成後才跳過剩餘角色；DATO countdown/anchor 與 why special epilogue 的 slot 語意仍不猜。資料由 strict `Montage` loader/planner 驗證，但 renderer 未接，仍 fail-closed。
- 2026-07-20 indexed FIGANI decoder：新增 `remake/internal/figani`，以通用 LLLLLL reader 讀 FIGANI resource，嚴格驗 frame offset table、13-byte header（signed dx/dy、`+6` delay、`+9/+11` real geometry），完整 4-mode RLE 轉成 indexed `Pixels+Mask`；transparent/dither span 保持 native destination-preserve，不把它化成 PNG alpha 或 palette0。`Frame.BlitAt` 可供 native 320/640 stride surface 使用，synthetic codec 與 player-provided `FIGANI.DAT` #13 regression 都通過。尚未宣稱 `0x29164` 完成：仍需 TAI #3、640-stride layout、8-step palette fade 和 specific slot renderer state。
- 2026-07-20 `0x29164` argument/fade correction（Docker-only Capstone）：`0x2c663` 的最後 push（前方已有6 pushes）才是 arg1=party loop unit index；callee 以 arg1×0x50 讀 `[0x53a45]+6` 決定兩條 path。因此 TAI#3 是尾端 aux argument，且其7-byte all-transparent raw **不能**是 `0x2935b` frame table。兩 path 都從 `esi=8` 倒數到0，逐輪 `0x11d40(0,255,esi*6)`，即 delta 48,42,36,30,24,18,12,6,0，合計9次 320×200 present（不是先前籠統寫的8-step fade）。640-stride figure/platform geometry 與 aux role仍待下輪，禁止接 RGBA renderer。
- 2026-07-20 `0x29164` final-caller non-mirrored geometry：`0x2c663` 呼叫 mode=1、使 finale party records 走 `unit+6!=0` path。每 stage 8→0 以 `work640 + stage*10` 為 byte origin，對 TAI#3 以 (164,157) 做 transparent no-op，對 **secondary** FIGANI（group×3）以 `0x2935b(frame0)` blit，再從 work left viewport copy 320×200 至 VGA；DAC delta=stage×6。這一條已資料化成 `Montage.PlanFigureFade(1)` 的九 pass，且 test 明確拒絕 unitSide0 mirrored path。restore buffer的實際初始來源／後段 primary FIGANI仍未 lower，故 schedule 本身不是可播放 renderer。
- 2026-07-20 `0x29164` restore/compositor closure（Docker-only Capstone）：`A=0x1f400` work、`B=first 0xfa00`、`C=second 0xfa00`；FDOTHER#56 先 blit 到 B。每 non-mirror fade pass 的直接 `0x11eb0` 是 **B→A**（dstStride640/srcStride320、320×200），再 secondary FIGANI→`A+stage*10`、A left viewport→VGA；`RenderFigureFadePass` 已用 indexed buffer 實作這個完整且窄的 primitive，要求 TAI#3 exact transparent bytes。primary FIGANI animation 後 `0x373c4(C,B,0xfa00)`，故 C 是 portrait/text loop 的 frozen restore base（後段每 tick C→A 都為320 stride）。這解除 restore 來源，但未 lower primary animation/DATO text 或 mirrored path，player integration 仍封閉。
- 2026-07-20 finale #56 format closure：玩家 raw `FDOTHER_056.bin` 為13609 bytes，前4 bytes直接是 little-endian 320×200，後接**單一** `0x4e63d` payload、沒有 #54 的 frame-table。新增 player-asset regression 證實以 `Frame{Width:320,Height:200,Pixels:data}.Blit(...,320,-1)` 成功 decode；可重用既有 transparent RLE grammar，但不可使用 `ParseFrames` offset table parser。
- 2026-07-25 item-action provenance correction：Docker/Capstone 重檢 `0x1bbdc` 與 `0x20c6f`。`0x1bb8c` 僅是把 item 插入第一個空 inventory slot，不是 item effect；case1 為 transfer（插入+`0x1b8e7` removal），case2 為 `0x1bffe` equip。case0 依 item `+0xd` type 進 `0x20c6f`，再分派至多個原生 effect routines；各 callee 數值語意仍未閉合，remake 維持 fail-closed。已同步更新 battle-menu、item RE、UI evidence、worklist，刪除錯誤 effect/consume 斷言。
- 2026-07-25 non-mirrored figure-fade implementation：將已證實的 `0x29164` 窄 primitive（B→A 320→640 restore、secondary FIGANI frame0 置於 `stage*10`、A left viewport→VGA、baseline DAC `stage*6`）整理成 `RenderFigureFadePass`，`BlitAtBase` 支援 native work-surface origin，並以 exact TAI#3 transparent bytes 與像素 regression 鎖定。這只完成 evidence-backed primitive；primary FIGANI、DATO text、mirrored branch 與完整 ending player 仍 fail-closed。
- 2026-07-25 type-0x17 item callee audit：Docker/Capstone 展開 `0x2218a`，確認它依 target unit `+0x20/+0x21` 更新全域 accumulator，呼叫 `0x22253` indexed off-screen renderer，並把 caller bytes 寫回 target unit `+0/+1`。文件不再把此 branch 猜成轉職／復活；只保留特殊 renderer/state-write provenance，欄位玩法語意維持 unknown。
- 2026-07-25 nested FDOTHER boundary：`FDOTHER.DAT#0x51` raw entry 已由 Docker-backed regression 證實是 nested `LLLLLL`（first-word `0x12`、18710 bytes）；新增 `fdother.ArchiveEntry` 只做 raw boundary validation，不把 nested payload 猜成 frame table。`0x11eee` data selection 與 `0x22253` indexed runtime adapter 仍 fail-closed。
- 2026-07-25 acting decoder correction：Docker/Capstone 直接重檢 `0x1366a`。`bit7=0` 每格固定 7 tick，逐 tick 寫 unit `+3=pose`、`+4=1..7`，第 7 tick 才依 pose 更新 X/Y；`bit7=1` 不搬格。`bit7=1/low7=0` 仍是有效 frame，原版含 delay(1)+重繪+delay(2)，remake 以三 tick 保留時序並每 tick 重寫 pose；新增 zero-special pose/timing regression。direct 106-entry acting bank 與 slot ABI 維持已解定，renderer/presentation 尚不猜測接入。
- 2026-07-25 command-label table closure：Docker-only Capstone 的 `0x1ceed` 直接呼叫 `0x15f84([0x53a7d], 0x1b9+commandID, ...)`；既有 permanent-table trace 對齊 `[0x53a7d]` 為 FDTXT_000。從 raw offset table strict decode 的 physical strings #441..#480 已匯出到 `docs/data/command_labels.json`（含空 slot 與系統訊息）。這使 label 成為 editable evidence；它**不**證明每個 command ID 可達或定義 effect／target，後者仍 fail-closed。
- 2026-07-25 raw command-mask pipeline：FDFIELD roster 的 `b13..b16`（constructor `0x10f7f` copy 到 runtime `+0x1a..+0x1d`）不再被 parser 丟棄。`parse_field.py`／`export_units.py` 輸出 `initial_command_mask`，battle `Unit.NativeCommandMask` materialize 為 5-byte ABI，strictly 支援 native order enumeration 與 0x1d7fb-style bounded OR；malformed source 拒絕載入。legacy `Spells` list 仍是另一條 normalized gameplay approximation，不能當作這個 raw mask。
- 2026-07-25 command-record table identity：Docker read-only table comparison 證實 `0x4e516(id)=0x619fd+7*id` 的 IDs 0..35 與 EXE spell table 完全同 bytes；這正名 `+3/+4/+5/+6=dist/range/mp/target`，且 MP gate 有獨立 selector trace。33 maps FDFIELD + 32 character defaults 的 initial masks 實測只出現 IDs 0..30。36..39 的 pointer-adjacent 7-byte data 對應 FDTXT 空／系統訊息 labels，未證實可達，保持 fail-closed。
- 2026-07-25 level-up command learning closure：`0x1e292` 在 EXP threshold 後 increment runtime level，經 portrait growth row `+0x0a=learn_idx`、`0x4e4a2(idx)=0x626b3+12*idx` 掃最多六組 `(required_level,command_id)`；命中後唯一 caller `0x1d79c` OR 5-byte mask，並印 FDTXT_000 #587「學會了！」。20 rows 已由 `dump_exe_tables.py` 導出 `command_learn.json`，FF/FF sentinel 保留。尚無 portrait→growth row 的完整 runtime provenance，不能以 legacy Spells 取代。
- 2026-07-25 learning runtime bridge correction：`0x4e4d1(unit[+7])=0x620a1+portrait*11` 直接證實 portrait→growth row，不再稱 provenance 未解。`State.GainExp` 以 injected `CommandLearn` table 在每次 level increment 後精確比對 row[portrait]／new level、OR native command bit，並回傳 learned IDs；standalone legacy `GainExp` 不自動造資料，保持相容與 fail-closed。
- 2026-07-25 learning runtime asset binding：generated `command_learn.json` 已加入 `remake/assets/data`，Game 在 bootstrap 讀它並在 `resetBattle` 的每個新 State bind 同一 table；缺檔不回退 legacy Spells。Docker internal regression 全綠。
- 2026-07-25 UI test container closure：`tools/docker/fd2-go-test.Dockerfile` 集中 Ebiten Linux 所需 ALSA/X11/GL `pkg-config` development headers，並在 image build 時預抓 `go.mod` dependencies；`fd2-go-test-local` 已以 `--network=none` 實跑 `go test ./cmd/fd2 ./internal/... -count=1`、exit 0。這取代先前散落的「GUI compile 被缺 ALSA/X11 容器阻塞」說法；它是可重現的 source regression，不等同完成原版 UI 實機對照。
- 2026-07-25 UI action wrapper correction（Docker-only Capstone）：`0x18d8c` 是 action dispatch wrapper。撤回把 `0x1b83d` 稱為「前序選擇」的錯誤說法：它掃 unit 八個 inventory slots，找 `bit0x40` equipped 且 item ID `<0x80` 的第一格；找不到才設 output `+0=1`，命中才以該 item record 的 `+0xb/+0xc` 建前序 target state。`0x1b8a6==0` 精確等於八格皆 empty（bit0x80 全 set），故設 output `+8=1`；`0x1c269==0` 或 unit `+0x27!=0` 設 `+4=1`。`0x177fc` 回 `-1` 是 selector cancel；僅其後依 `[0x53c57]` 分派 attack／`0x1cff0` command／`0x1bbdc` item／wait-field。flags 對應的可見 action/icon 仍未閉合，保持 raw，沒有接 renderer。
- 2026-07-25 command gate scope correction（Docker-only Capstone）：`0x1598a` 在列舉 command record、MP 或 target grid **之前**，只要 `0x1c269` count 為零或 `unit+0x27!=0` 就直接 zero return；`+0x27` 因此是整個 native command submenu gate，而不是僅 wrapper 局部 flag。全 code scan 另兩個 `+0x27` 命中就是此處與 wrapper read；`0x1eb64` 只是 UI resource frame index。寫入者／status 名稱未閉合，禁止稱作沉默、封魔或接入 remake effect。
- 2026-07-25 native action overlay/input closure（官方 IDA 9.4 + Docker Capstone）：`0x173e7` 由四個 availability words 選第一個零值；`0x177fc` 只允許 availability=0 的 ↑/←/→/↓ 選 action 0/1/2/3，Enter/Space confirm、Esc 回 -1 cancel。`0x18d8c` battle wrapper 的 state table 是固定 `[0,1,2,3]`，故 enabled cells=`[0,2,4,6]`、disabled=`[3,5,7,9]`；舊 handoff 將 `0x1728c` 的另一個巢狀 menu state 誤套於 battle overlay，已撤回。`0x1741c` 以 `[0x53a89]` relative asset table 經 `0x4e9e4` 畫四張 state image，從 shared `+0x390` 做四 frame 十字 slide：up `-0x8e8`、left `-6`、right `+6`、down `+0x8e8`；`0x175a9`/`0x17643` 以 72×72 (`0x1440`) indexed backup restore，`0x176b4` close sequence 為獨立初值／delta（非簡單 reverse）。`0x11bfa/0x11c59` 證實 anchor 使用 visible cursor `[0x53ab9]/[0x53abd]`：共同 byte address=`framebuffer+0x8088+0x18*column+(0x18*0x1c8)*row`，而 `[0x53aa9]/[0x53aad]` 才是 camera scroll。resource provenance／實機 skin 外觀仍未閉合，不能將 remake ring 宣稱成原版皮膚。
- 2026-07-25 action asset provenance/decoder closure：`0x25c97..0x25cac` 直接將 `FDOTHER.DAT#2` 載至 `[0x53a89]`；該 raw 是 untagged 78-cell offset bank（first `u32=0x138` directory end），每 cell `{u16 w,u16 h,w*h raw indexed pixels}`，不是 LMI1 或 ending frame-table。`0x4e9e4` 精確逐列 blit、index0 preserve。新增 strict `fdother.ParseRawCellBank`／`RawCell.BlitAt` 和 player-asset regression；實測 74×24×20 加 4×24×16 cells。relative table→action cell index、anchor 與 runtime renderer 未閉合，保持 fail-closed。
- 2026-07-25 terminology correction：README、SDD、doc14 與 worklist 不再把原版 action UI 斷言成「radial 指令環」；E0 證據是 FDOTHER#2 四張 indexed asset 的十字 overlay 加獨立 command grid。現行 `ringInput` 只保留為 provisional interaction，不能再當 original skin/mechanism 的證明。
- 2026-07-25 title screenshot oracle：新增 repo-maintained `tools/docker/fd2-dosbox-screenshot.*`，以 SVGA/Xvfb/xdotool 對 `/tmp` FD2 sandbox 跑可編輯 timeline；原始 FLAME2 不掛載。連續 Escape 跳 opening 的真實 320×200 crop 已加為 `docs/figures/title-original-dosbox.png`，直接證實 title START／LOAD／CONTINUE 及 cursor。它只提升 UI-01 畫面 E2，不代表 title input、save/load 或 remake title renderer complete。
- 2026-07-25 empty LOAD oracle：原版 title→LOAD 在 empty sandbox 直接得到 `docs/figures/load-empty-original-dosbox.png`，證實 4-slot 縱列、空記錄文字與 row1 outline；僅為 UI-12 empty-state E2，沒有有效 FD2.SAV，故不對 save record、覆寫確認或成功 load 做任何斷言。
- 2026-07-25 ch01 dialogue oracle：原版 START flow 的 `docs/figures/ch01-dialogue-original-dosbox.png` 固定一種 lower/left DATO portrait、blue dialogue box、兩行文字及 bottom-center page indicator。只提升 UI-05 該 anchor E2；upper/right/control code/pagination 仍未閉合。
- 2026-07-25 native action overlay remake slice：remake 可在使用者明確提供 `FD2_ORIGINAL_FDOTHER`（或本機未版控 `assets/original/FDOTHER.DAT`）時，strict 解析 FDOTHER #0 的 6-bit VGA palette 與 #2 的 raw action cells，畫出已證實的最終 opening frame 十字 skin；檔案缺失或格式異常一律回退既有 placeholder。這是靜態 renderer 垂直切片，availability 仍只是目前 remake 的保守近似，尚未聲稱為原版 gate；opening/closing animation、原版 input dispatch 與實機畫面對照仍待完成。
- 2026-07-25 overlay gate tightening（官方 IDA 9.4 asm re-read）：`sub_1B83D(unit,0)` 的 attack precondition 確為 inventory slot 的 `bit0x40` 已裝備且 ID `<0x80`，不是「有任一物品」；`sub_1C269` 的 5-byte low-bit-first command inventory 也可直接作 command availability。remake native skin adapter 已接這兩個狹義前提；當 editable legacy scenario 根本沒有 raw mask 時才保留 normalized Spells fallback。`+0x27`、原版 target geometry 與 item effect 沒有被命名或接入。
- 2026-07-26 native action overlay screenshot closure：Docker/Xvfb 對 player-provided FDOTHER.DAT 的 read-only mount 實跑，截圖 [`action-overlay-native-remake.png`](../figures/action-overlay-native-remake.png) 可見 final-open cross skin。過程修正 screenshot frame scheduler（不能假設 exact frame）與一個實際 renderer bug：`drawRing`/`drawSpellMenu` 不可被 optional Chinese font gate 包住。截圖只證明 remake loader/render path，不取代原版 DOSBox side-by-side visual diff，也不宣稱 gate 或 animation 已完成。
- 2026-07-26 action animation timing correction（official IDA 9.4）：`sub_1741C` 與 `sub_176B4` 都是四輪 `0x4e9e4` cell blit→`0x11eb0` present→backup restore，迴圈中沒有明確 delay/wait；不可由 offset 個數推導每幀毫秒數。保留 open/close geometry E0，presentation cadence 需從 outer loop／實機 trace 另行取得。
- 2026-07-26 command-grid renderer closure（official IDA 9.4）：`0x1d51d→0x1ceed` 確為 320×200 的四列 command grid。第 i command 的 label 位置=`(0x12+0x64*(i/4),0x67+0x16*(i%4))`，FDTXT_000 index=`0x1b9+commandID`；選中/未選中 palette index 分別 `0xc9/0xcd`，record `+5` 的 MP numeric 位於右側。↑↓ wrap、←/→±4 且水平 bounded，confirm 再比較 unit `+0x44` 與 record `+5`。這是 layout/input ABI，不是 effect 或 command-name 斷言；remake command-grid renderer 仍待接入。
- 2026-07-26 native command-grid primitive：新增 `battle.NativeCommandGrid`／`NativeCommandGridMove`，以官方 IDA 確認的四列座標與 0x1d51d navigation 實作成無 effect 語意的純資料層；Docker regression 覆蓋第5項換欄、上下 wrap 與水平 boundary。這為 renderer/input 共用 ABI，尚未把 legacy spell menu 冒充完整原版 command runtime。
- 2026-07-26 command-label bridge：`cmd/fd2` 現可選擇性讀玩家 editable 的 `assets/data/command_labels.json`，以 `command_id` 覆蓋同 ID EXE spell row 的顯示名稱；缺檔／壞檔安全退回 normalized spellNames。這只接 FDTXT label provenance，不改 selection layout、MP gate 或 effect。
- 2026-07-26 native command-grid runtime slice：有 player FDOTHER palette+editable labels 時，ring command branch 現以 raw `NativeCommandMask` 顯示 official-ID A recovered four-row grid，直接使用 palette `0xc9/0xcd` text entries；native navigation ABI 已接。confirm 僅對有 EXE spell record 的 IDs 接既有 target path，其他 ID fail-closed；缺資產保留 legacy spell UI，沒有宣稱 native frame/effect completed。
- 2026-07-26 scenario command-mask audit：command-grid screenshot fixture 盤點顯示 default chapter scenario party lacks raw masks；原因是 party override schema 沒有 FDFIELD `initial_command_mask`，不是 renderer 可任意以 normalized Spells 補齊。runtime 因此正確 fallback；下一個 RE/remake bridge 是把 proven raw field 帶經 exporter→scenario→party materialization，並逐章測試。
- 2026-07-26 scenario command-mask bridge：`PartyMember.initial_command_mask` 現已接通並在 `LoadScenario` 只接受空值或精確四 bytes（malformed fail-closed）；`PartyUnits` materialize 至 native five-byte runtime mask。`gen_campaign.py` 從 EXE `character_defaults.json` 依角色 index 合併 raw source 至 ch01..ch30，保留既有手工 scenario 欄位；ch01 悠妮直接為 `[1,0,0,0]`，不是從 legacy spells 推導。另修正 postbattle persistent projection：完整 `NativeCommandMask` 現跨 town/preparation 保留，故 native level-up `0x1d7fb` 的 fifth-byte OR 不會遺失。已覆蓋 materialization、malformed schema 與 persistent copy regression；仍待每章真機 availability / command effect 對照。
- 2026-07-26 command-confirm dispatch correction（official IDA 9.4 DB/ASM）：`0x1cff0` 在 target confirm 後，IDs `0..8`、`0x18`、`>=0x1c` 直入 `0x2a6bd(unit,id,target,scratch)`；IDs `0x09..0x17`、`0x19..0x1b` 才先跑 `0x1d6c8(id)` 四輪 palette flicker 再呼叫 `funcs_1541f[id]`。撤回舊文「record +4 是 MP/cost」：direct MP gate 為 `+5`。因此悠妮 raw command0 已知進 generic pipeline，仍不能命名成 normalized spell 或接猜測性效果。
- 2026-07-26 command0 compositor boundary（official IDA 9.4 DB/ASM）：`0x2a6bd` 的 ID0 不走 `>=0x20` 或 `0x18..0x1b` special early branch；它使用 generic presentation defaults，`funcs_2ac25[0]=0x26152` 反覆合成 320×200 buffers/FIGANI/FDOTHER 並 present/tick。這只能證明 command0 的 battle renderer path，不能將它誤當 damage、MP 或 status formula；效果 state writer 待後續 dataflow。
- 2026-07-26 command post-resolution boundary：`0x1b6b7` 掃 runtime roster，僅把符合 `+5/+0x31/+0x40` 條件者的 source `+0x31` 起三 bytes 複製至 caller buffer；`0x1cff0` 再傳給 `0x1aa1d`。故這條是後處理（訊息／掉落／互動）資料流，不是 command0 damage/status calculator。三個 raw bytes 的遊戲語意仍未命名。
- 2026-07-26 command0 damage closure re-verified（official IDA 9.4 ASM）：`0x2a6bd` 的 final-target loop 以 `arg_C[var_34]` 取 target slot，並直接 `call 0x1c75e(targetSlot, ebp=commandID)`；該函式在同一 direct path 前呼叫 `sub_2b659`，其 frame event 以 actor／command ID 呼叫 `0x1ca89`。先前一次 grep 漏掉 loop 內 call 而錯誤撤回，現已恢復 ID0 record/hit/HP/MP executor；`+0x40/+0x42` 的 HP 意義亦由此與其他 handlers 交叉支持。
- 2026-07-26 command class-multiplier closure（official IDA 9.4 DB/ASM）：constructor `0x10f7f/0x11399` direct copy source race/class/level 至 runtime `+0x1f/+0x20/+0x21`；故 `0x1c75e` 的 `word_51f96[unit+0x20]` 是 target class-ID-indexed damage multiplier。撤回 doc03 將 race/class/level 放在 `+0x27` 的舊標記；個別 multiplier 的玩法名稱仍待 table/data 對照。
- 2026-07-26 numeric damage resistance closure（official IDA 9.4 DB/ASM + EXE bytes）：`word_51f96` 的 loaded-data file mapping 是 `0x51d96`，即既有職業魔抗 table 的 4-byte rows；其 low byte=`resist_raw`（法師=7 即 30% magic resistance）。已閉合 numeric route 的 base 為 `record.dmg*resist_raw[target class]/10`，並以 `NativeCommandDamage` resolver（hit draw、damage draw、HP clamp）及 fail-closed editable-table loader 實作；不可再把它專屬歸因給 ID0。
- 2026-07-26 command0 target-array closure（official IDA 9.4 ASM）：一般 command record 的 `+3/+6` 進 `0x14818` 產生 candidate unit-index stack array；`0x115b6(mode=+6,count,array)` 做 cursor/confirm，之後第二階段 effect array 才傳 `0x2a6bd(unit,id,count,array)`，其 final loop 可達 `0x1c75e`。撤回把 native command0 當單格 legacy cast 的暗示；尚未命名 target-code/geometry 值域。
- 2026-07-26 `0x14818` target geometry closure（official IDA 9.4 ASM）：`record+3<0x10` 用 `0x4e555` map/reach mask；`>=0x10` 為 horizontal/vertical cross，radius=`+3-0x10`。scan roster 跳 inactive/mask `0xff`，record `+6` 的 raw predicate 是 0:`unit+6==0`, 1:`!=0`, 2:`!=1`, 3:`==2`。保留 raw values，尚未猜命名／map-mask 行走規則。
- 2026-07-26 target reach closure correction（official IDA 9.4 ASM/data）：`0x4e555` 是 20-byte cost-row helper，mask producer 是 `0x4e040`。它做 cardinal flood-fill，grid bit40 block、bit80 cost=0；但 command selector 固定取 row0，而 `word_61646` row0 的 20 bytes 全=1。因此 command target 不用 terrain-weight，但會受 blockers 限制；撤回「需要 class/tile cost 才能接 native command range」及「無條件 Manhattan」兩種錯誤暗示。
- 2026-07-26 camp offset correction（official IDA 9.4 `0x10c50` constructor）：FDFIELD unit `b0` 直接寫 runtime `unit+6`，值 0敵/1友/2己。撤回 docs 把 runtime `+0x0e` 寫成 camp 的舊表；這也正名 `0x14818` target codes 0=enemies、1=non-enemies、2=non-allies、3=own。
- 2026-07-26 native command MP transaction closure（official IDA 9.4 ASM）：generic route `0x21227` 在 candidate array 建立後、逐 target effect 前呼叫 `0x1CA89(actor,commandID)`；後者由 `0x4e516(commandID)` 取 record `byte+5`，直接扣 runtime current MP `unit+0x44`。selector 的 `currentMP >= byte+5` gate 在此前，因此 remake `SpendNativeCommandMP` 只表達已確認交易、invalid/不足不寫入，且不以 normalized `Spell` 冒充 raw command。target confirm/effect/UI 仍不接。
- 2026-07-26 native command two-stage target correction（official IDA 9.4 ASM）：撤回「`0x115b6` confirm 後把 first `record+3` candidate array 直接交給 `0x2a6bd`」的錯誤捷徑。一般 `0x1cff0` 先以 actor cell/`+3`/`+6` 建可選中心並交 `0x115b6`；confirm 後以 cursor cell/`+4`/`+6` **再**建 final-effect array，僅第二 array/count 傳入 `0x2a6bd`。`NativeCommandTargetCells` 只表達一次 `0x14818` primitive，caller 必須明確選 stage；UI 繼續 fail-closed。
- 2026-07-26 raw command UI fail-closed correction：撤回 native command grid「有同 ID `spells.json` row 就可進 legacy `CastArea`」的暫接。這會跳過已證實的 actor `+3`→cursor confirm→cursor `+4` target pipeline，且 table identity 不證明 effect equivalence。grid confirm 現清楚顯示未驗證並回 action overlay；legacy spell menu 仍是獨立、可編輯的 approximation。
- 2026-07-26 verification note：Docker `go test ./internal/battle` 通過；同 image 的 `cmd/fd2` compile/test 在此 runner 會停於 Ebiten/CGO build（`CGO_ENABLED=0` 則明確報 cglfw build constraints），故此次 UI guard 僅以 gofmt、battle regression 與 diff check 驗證。不可把該環境限制解讀為 UI behavior 測試已通過；應在 Xvfb-capable image 補 UI smoke。
- 2026-07-26 command completion flag closure（official IDA 9.4 ASM）：`0x18d8c` 的 native command branch 僅在 `0x1cff0` success（非 0/non-cancel）後呼叫 `0x13512(unitSlot)`；後者唯一寫 `runtime unit+5 |= 0x80`。這直接證實 native command 成功耗用行動、失敗/取消不耗用。只可套用於已閉合 handler；不能據此替 ID0 猜測 mutation。
- 2026-07-26 ID0 UI vertical slice re-enabled：direct `0x2a6bd→sub_2b659/0x1c75e` dataflow 已逐行確認後，raw native grid 的 ID0 恢復 actor `+3` candidate highlight、confirmed cursor `+4` final effect、state-bound record/resistance/flags core 與 ESC 回 grid；仍不包括原版 compositor/post-resolution/SFX or screenshot oracle。
- 2026-07-26 shared damage IDs0..8 correction：wrapper 可達性與 player dispatch 是兩個不同問題；雖 IDs0..8 不經 `sub_21227`，它們的 direct `0x2a6bd` final-target loop 同樣達 `0x1c75e`，並藉 `sub_2b659` event 扣 MP。故 engine 仍 bounded 支援 IDs0..12；renderer/effect visual 不推論相同。
- 2026-07-26 native command IDs13..16 healing closure（official IDA 9.4 ASM）：jump-table `0x21AD9/0x21B99/0x2211C/0x22153` 只換 ID `13/14/15/16` 與演出參數後跳共同 `0x21B18`；它對 generic final target array 先跑專用 indexed presentation `0x1C4CC/0x1C2DA`，再 `0x1CA89(actor,id)` 扣 MP；每個 target 的 `0x1C8ED→0x1C916` 以 record `u16+0` 算 `floor(amount*0.9)+floor(rand()%100*amount/1000)`，將 runtime `+0x40` 加至最多 `+0x42`，並以 `0x1E0DB(...,0x69,target)` 顯示數字。IDs13..16 因此是 per-target HP restore，不是 IDs0..9 numeric damage route；renderer/UI/SFX 及 remake resolver 未接，維持 fail-closed。
- 2026-07-26 native commands 17..19 modifier-writer closure（official IDA 9.4 ASM）：ID17 `0x226EA→0x22721` 以 `+0x22` gate，ID18 `0x2282F→0x22866` 以 `+0x23` gate，兩者在零值時設 `rand()%4+2` duration，對 `+0x48/+0x4a` 加 `__CHP(value*0.15+1)` 的 FPU-rounded increment；ID19 `0x22960→0x22997` 以 `+0x24` gate，設 duration後對 `+0x4c/+0x4e` 各加 15。這與 `0x1b750` 的 derived AP/DP/HIT/EV writers 一致，故撤回 doc35 將 `+0x48..+0x4e` 誤稱螢幕座標／bounding box 的 assertion；status names、tick/decrement、UI、remake integration 未閉合。
- 2026-07-26 native commands 20..21 flag-clear/restore closure（official IDA 9.4 ASM）：ID20 `0x22A85` 與 ID21 `0x22BC6` 只換 command ID/flag offset，均進 `0x22AA8→0x22AF6`；MP debit 用 command20/21 record，final target 的 `+0x25/+0x26` 為零則失敗 display，非零時 `0x1C916(target,10)` 回復 HP 並清該 flag。兩 status 名稱、UI 與 integration 未閉合；ID22 是不同 `+0x27` application route，不可混稱 cure。
- 2026-07-26 native command 22 application closure（official IDA 9.4 ASM）：`0x22BE1→0x22CDA→0x22D1B` 對 final target 先檢查 `+0x27==0`、class `+0x20` 非 `0x19/0x1a` 及 `rand()%100<0x32`；三者成立才以 `0x1C81F(target,10)` 固定扣 10 HP、display damage、寫 `rand()%4+2` 至 `+0x27`，否則只失敗 display。未命名 status、tick/UI/remake integration，禁止以 raw offset 臆測。
- 2026-07-26 transient command duration lifecycle closure（official IDA 9.4 ASM）：turn/camp phase driver `0x1A30B` 每 camp 呼 `0x1A866(camp)`；後者只掃 active 同-camp unit，對 `+0x22..+0x27` 六個 duration byte 各自 decrement，任一歸零才顯示 expiry feedback 並呼 `0x1B750` 重算 derived AP/DP/HIT/EV。故 command17..22 寫入的 `rand()%4+2` 是 camp-phase duration，非每 action/frame timer；status names/icons/UI/remake state未接。
- 2026-07-26 native command 23 relocation boundary（official IDA 9.4 ASM）：ID23 走 `0x1CFF0` command-`0x17` special selector；`0x2218A` 用 record23 扣 MP，對 selected unit 兩次呼 `0x22253`。C stack ABI 釘住第一次 direct write unit `+0/+1=0xff/0xff`（原座標離場演出），第二次 direct write `+0/+1=0x51CF9/0x51CFD` cursor globals（入場演出）。這證實直接格座標 relocation、非 path movement；落點 legality/UI/camera/renderer 未閉合。
- 2026-07-26 native commands 25..27 closure（official IDA 9.4 ASM）：ID25 `0x22C04` 以 record25 MP debit，僅在 final target `unit+5 bit0x80` 已設時清 bit；ID26 `0x22CBF`、ID27 `0x22E41` 只換 command ID 與 `+0x25/+0x26` flag offset，皆進 ID22 的 `0x22CDA→0x22D1B` application helper，保留 zero/class/RNG gate、10 HP damage、`rand()%4+2` duration。故 ID20/26 與 ID21/27 分別是 direct raw clear/apply pairs；status names/UI/remake integration未接。
- 2026-07-26 raw transient data-layer slice：`battle.Unit.NativeTransient[6]` 現保存原始 `+0x22..+0x27`，`NativeTransientDuration/SetNativeTransientDuration` 僅接受該 bounded offset range；`State.TickNativeTransients(camp)` 以 `0x1A866` 的同-camp、active/alive、每 byte independent decrement/expiry ABI 實作並回歸。它不混用 legacy normalized Buff/Poison/Seal/Paralyze timers，也尚未自動做 `0x1B750` equipment/stat recompute，保持 fail-closed。
- 2026-07-26 native command25 engine slice：`State.ExecuteNativeCommand25` 依 `0x22C04` 只接 generic two-stage targets、record25 MP debit 與 final target `Acted` clear-if-set；wrapper-success 後才設 actor acted。缺 raw book/flags、invalid confirmation 或 MP不足均在 mutation 前拒絕。UI/renderer/message feedback 未接，且不重用 normalized CastArea。
- 2026-07-26 native commands22/26/27 engine slice：`State.ExecuteNativeCommandApplication` 只接受 IDs22/26/27，依各 record generic two-stage targets/MP debit；final target 需 raw `+0x27/+0x25/+0x26==0`、class 非 `0x19/0x1a`、`rand()%100<50` 才 fixed-10 HP damage 並寫 `rand()%4+2` raw duration。target gate 失敗時不 mutation，但已成功 handler 仍耗 MP/actor completion；不映射 legacy Poisoned/Paralyzed，UI/renderer未接。
- 2026-07-26 native commands20/21 engine slice：`State.ExecuteNativeCommandClearRestore` 只接受 IDs20/21，依各 record generic targets/MP debit；final target 的 `+0x25/+0x26` 非零時，以 **record10** amount 走 `0x1C916` formula/HP cap 後清同 raw byte，empty flag仍是 successful command completion。`ApplyNativeCommandRestore` 分離 rolled display amount 與 actual HP delta；不映射 legacy named status，UI/renderer未接。
- 2026-07-26 native commands13..16 engine slice：`State.ExecuteNativeCommandHeal` 只接受 IDs13..16，使用自己的 raw record generic targets/MP debit/`0x1C916` restore-cap/actor completion；與 IDs20/21 借 record10 的 clear/restore route 分開。專用 indexed animation、SFX/message/UI未接，保持 fail-closed。
- 2026-07-26 native damage route correction for IDs0..12（official IDA 9.4 ASM）：`0x21548` 開頭 `0x1CA89(actor,id)` 扣 MP，尾端 final target loop 直接 `0x1C75E(target,id)`；ID10 `0x21527`、ID11 `0x2185F`、ID12 `0x21A9E` 皆可閉合 numeric core，ID9 亦 direct `1CA89→1C75E`，IDs0..8 則是 `2A6BD→2B659/1C75E` direct family。`ExecuteNativeCommandDamage` bounded range 恢復 0..12；presentation/SFX 不推論相同。
- 2026-07-26 official IDA xref export unblocked：使用者合法 `ida-pro-9.4-ver2` local Docker image 以 `/tmp/fd2-ida-analysis` 保存 IDA sidecar、repo 只接收 address-only report。IDA 9.4/Hex-Rays batch 已完成並輸出 `docs/data/ida/fd2_xrefs.json`；`tools/ida_export_fd2_xrefs.py` 移除 IDA 9.4 不存在的 `ida_xref.get_xref_type` 呼叫。repo Dockerfile 仍不含 license；為 IDAPython 安裝的授權 image overlay 只留本機 Docker cache、不可提交。report 僅驗 call graph，不能獨立命名 handler／status 語意。
- 2026-07-26 modifier MP ABI correction（official IDA 9.4 ASM + raw rows）：jump-table ID17 `0x226EA` 與 ID18 `0x2282F` 都呼叫 `0x1CA89(actor,0x12)`；records17/18 的 seven-byte raw row 完全相同（`00000004020501`），所以可觀察 debit 相同，但不可泛化成 handler 一律傳自身 command ID。ID19 `0x22960` 明確傳 `0x13`。modifier writers／duration 的既有結論不變；這只撤回會污染後續 executor 的 transaction 便利假設。
- 2026-07-26 ID24 player/AI dispatcher split（official IDA 9.4 ASM + Docker Capstone）：撤回「`funcs_1541f[24]=0x22153` 因此玩家 ID24 是 ID16 heal alias」的錯誤捷徑。該 table 只在 `0x15311` AI／自動 dispatcher 使用，確實會把 ID16 傳入共同 heal tail；玩家 `0x1cff0` 則對 `0x18` 直入 `0x2a6bd→0x276ec`，不經此 table。後者的 `0x2b659` 明確以 `0x1ca89(actor,0x18)` 扣 record24 MP，再以 `trunc(actor.+0x48*15/10)-target.+0x4a` 呼 `0x1c81f`；多段畫面先暫存並復原 HP，最後等份扣至相同 delta。`ExecuteNativeCommand24` 已只接 final non-UI state slice；multi-hit/presentation/SFX/UI 仍未接。同步刪除 doc37 將 `0x2a6bd` 說成武器專用、與 command 無關的舊斷言。
- 2026-07-26 0x276EC family expansion（official IDA 9.4 ASM）：同一 player handler 對 ID28 選倍率20、ID29 選12、ID31（default）選18，均沿一般 two-stage selector 與 `0x2b659→0x1ca89(actor,id)`；`ExecuteNativeCommandDerivedStrike` 因此將 24/28/29/31 限定接成 state-only final delta。ID30 在 `0x1cff0` 改走 `0x149f8` special selector，IDs32..35 走 `0x27fc9`，故未被泛化接線。
- 2026-07-26 IDs32..35 compound-handler closure（official IDA 9.4 ASM）：`0x27fc9` 對 ID32→`0x2111a→0x1c75e`、ID33 對每 final target 清 `+0x25..+0x27` 後以固定 800 進 `0x211a4→0x1c916`、ID34 順序呼三個 modifier writers `0x22721/0x22866/0x22997`、ID35 順序以 IDs26/22/27 呼 application helper `0x22d1b` 寫 `+0x25/+0x27/+0x26`。這條 wrapper、其 helper 與 `0x1d4cb` presentation setup 都未見 `0x1ca89`；它只暴露 selector MP gate 和 debit writer 之間的未閉合差距，不能聲稱免費施放或由 remake 猜扣 MP，故四 ID 暫不接 engine。
