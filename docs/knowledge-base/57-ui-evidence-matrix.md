# 57 — UI evidence matrix（SDD-1 baseline，2026-07-25）

> 這是 SDD 的第一份可執行盤點，不是「已還原」宣告。行號以本輪 `remake/cmd/fd2/main.go` 為準；`partial`／`missing` 必須先補 E0/E1/E2 證據才可改成 verified。

## 現有 runtime evidence

| Contract | 現有 code evidence | 判定 | 下一個證據問題 |
|---|---|---|---|
| UI-01 title/menu | F2/F3/F5/F9 global input（約 3065、3291）；title boot path 尚未拆成獨立 scene contract | partial | Ghidra/IDA：menu item table、scan-code dispatch、save/load branch |
| UI-02 field | map/camera/cursor/unit/HUD Draw 約 3441–3568、4571、4595 | partial | 原版 cursor camera、HUD anchor、FDOTHER panel resource |
| UI-03 action menu | Docker Capstone `0x18890` + `0x18d8c`：↑0 attack、←1 spell、→2 item、↓3 wait/field interaction；remake `ringInput` 約 2407 已改同序 | partial | `0x1cff0` command/effect table、`0x1bbdc` item sub-callees、完整 enable gate、end-turn entry |
| UI-04 target/range | `0x1cff0` + `0x149f8` 證實 command record `+3/+4/+6` 參與 target-candidate geometry；`0x1bbdc` item case 0 也呼叫 `0x14818`；remake movement/attack/spell selection 已有，item action 約 2475 仍提示未實裝 | partial/missing | selector↔spell family 對照、item effect table、weapon reach、AOE/LOS、不可用目標灰化 |
| UI-05 dialog | dialog Draw 約 3590–3686；`dlgAdvance` 有 page/scroll state | partial | 每種 upper/lower portrait anchor、control-code renderer、native clipping |
| UI-06 HUD | target HUD 約 3557–3568；full-screen battle panel 約 4065、4180 | partial | FDOTHER loader、數字 cell、游標避讓和 320×200 ground truth |
| UI-07 postbattle | `campInput` battle result 約 2394；campaign node 可表達 post node | partial | 每章 on-win handler 是否進 town/shop/rest/preparation/ending |
| UI-08 town | `enterNode`/`campInput` 的 `town` branch 約 1584、2133 | partial | 原版 town menu、church/shop 入口與戰後 persistent timing |
| UI-09 shop | buy/sell/equip/recipient 約 2256–2391 | partial | 商品 menu sprite、游標邊界、secret shop flag、原版 cancel semantics |
| UI-10 church | revive/class-change 約 2162–2256；未接服務明確顯示待 callee | partial/fail-closed | 0x30dc3/0x31385 完整 fee、候選、確認與 renderer |
| UI-11 preparation | quota/checklist 約 1588、2133–2160；15/19 limit 欄位 | partial | native layout、JOIN chronology、preview、auto-confirm timing |
| UI-12 save/load | F5/F9 global path；save package 自有 schema | partial | scene-safe boundaries、versioning、原版 save semantics |

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

下一輪先處理 UI-03／UI-04 的原版 dispatch 與 weapon reach provenance，再接 UI-07 的逐章 transition matrix；在此之前不新增猜測性 renderer。
