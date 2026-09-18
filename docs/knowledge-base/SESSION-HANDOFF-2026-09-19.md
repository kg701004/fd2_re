# SESSION-HANDOFF 2026-09-19

> 依 `AI_Development_Standard/00_Global/Project_Continuity.md` 撰寫:明確區分完成/未完成/
> 需人決定,每一項標註**驗證等級**,不把未驗證的寫成已驗證。
> 前一份:[`SESSION-HANDOFF-2026-09-18.md`](SESSION-HANDOFF-2026-09-18.md)(它的 §6.0 ~ §6.0f 是本段工作的逐步紀錄,
> 本文件是總結與交接)。

## 0. 本輪的主軸

commit 範圍 `3a4ba8a4..96c26715`(**11 個 commit**,14 檔 +28061 / −6;大宗是兩份產生的 JSON),全部已推送至
`fork remaster-local`。

使用者指示,依序:「紀錄並歸檔」→「一個小時內能做多少?」→「請先執行一小時內做得完的」→「請繼續」→
「同意」(下載 Watcom 函式庫;經我說明命中率疑慮後改為先不下載)→ 多次「依照你的建議自動繼續進行 不用問我」→
「紀錄並歸檔」。主題是 **程式碼層的解析**:先把分母做對,再用機械方法描述能描述的,最後開始人讀。

逐 commit 細節在 [`98-tooling-infrastructure.md`](98-tooling-infrastructure.md) 的 2026-09-18 續二十三 ~ 2026-09-19 續二十八。

---

## 1. 驗證等級對照

| 等級 | 意義 | 本輪用量 |
|---|---|---|
| **靜態 RE** | Capstone 反組譯確定,未經實機 | `function_names.json` 全部 80 筆(`confidence: static_re`) |
| **位元組證據** | 名稱附帶的 `{at, insn}` 在該位址逐字比對通過 | 80 / 80 |
| **工具自驗** | `--selftest` 通過,且突變窮舉 0 逃逸 | `function_inventory.py`(100 個可達突變,98 抓到 + 2 登錄) |
| **產物重生** | 重跑產生器與已提交檔逐位元組比對 | `function_inventory.json`、`function_structural_names.json`(REGISTRY 第 19、20 項) |
| **原版實機** | DOSBox-X 跑原版 EXE | 本輪**未使用** |
| **結構描述** | 由本體結構機械得出,不是語意 | `function_structural_names.json` 全部 258 筆 |

**本輪沒有任何結論依賴 remake。**

---

## 2. 已完成(可量測的部分)

| 指標 | 本輪開始 | 現在 |
|---|---|---|
| 程式碼層分母 | Ghidra「976 個函式」(錯的) | **1102 個入口,strong 858**(位元組訊號聯集) |
| strong 入口裡有真名的 | 231 | **295** |
| strong 入口裡有真名或文件記載為入口的 | 481(56%) | **512(59%)** |
| 結構性名稱(描述,不是語意) | 0 | **258** |
| strong 入口裡**完全沒有任何描述**的 | 377 | **189**(遊戲側 `__STK` 之前約 100) |
| 人讀名稱(`function_names.json`) | 0 | **80**,位元組證據全數通過 |
| 產物登錄 REGISTRY | 18 | 20 |
| 等價突變登錄表 | 104 | 106 |

新工具:`tools/function_inventory.py`

- 預設:寫出 `docs/data/function_inventory.json`(每個入口的訊號、呼叫端數、`span_upper`、`argc`、callees、globals)。
- `--coverage`:名稱/文件記載覆蓋率(現算,不進產物)。
- `--structural OUT`:結構性命名 —— `thunk`、`ail_only`、`wrapper`(依呼叫順序帶常數參數,例如
  `wrapper(load_res(0x1a4d, 0, 0x50))`)、`leaf_global`/`leaf_ptr`/`leaf_pure`(由反組譯本體判定)。
- `--check-names`:驗 `function_names.json` 每筆 evidence 在位元組上逐字相符、且落在函式範圍內。
- `--card ADDR`:單一入口的事實卡 + 呼叫端 + 帶名稱與 fixup 註記的反組譯。
- `--unnamed`、`--ghidra-export PATH`。

---

## 3. 抓出的既有錯誤

| 錯誤 | 證據 | 處置 |
|---|---|---|
| Ghidra 的「976 個函式」被當成程式碼層分母 | 226 個是 `.image::` 位址空間的 1-byte 空白佔位;另有 317 個有序頭或被 CALL 的入口落在任何 Ghidra 函式之外(101 個知識庫早已主張為入口);AIL 105 個只有 44 個是 Ghidra 起點 | 分母改由位元組訊號建立;Ghidra 降為 `--ghidra-export` 對照;記憶 `reference_fd2_ghidra_decompile` 補註 |
| `derive_native_argcounts.callee_argc` 遇到 `sub esp, eax` 崩潰 | `int(' eax', 0)` ValueError;先前只餵過幾十個目標,套到 1102 個入口才出現 | 回 None(位移不可知,不是 0),補成對案例 |
| E8 位元組掃描的假呼叫目標混進 callees | `0x16c57` 的 callees 有 `0x75c1f2d7` | `callees_by_owner` 只收 obj1 `[base, hi)` 內的目標 |

---

## 4. 我自己犯並更正的錯

1. **「函式庫區」說過頭**:把 `__STK`(`0x3702f`)之後整段叫函式庫區;那一段也有遊戲側繪圖常式(`0x4e98d`、`0x4df4c`、`0x4e390`)。
   函式庫要靠簽名判定,不能靠位址分段。
2. **可行性估計虛胖**:唯讀分析估名稱傳播上限 155,工具實測傳播 1 輪即停 —— 估計時把只有位址、沒有名稱字串的來源也算成「已知」。
3. **測試夾具會說謊**:`bytearray` 切片賦值超出尾端會把陣列撐長,「讀不滿 5 bytes」的案例其實讀得滿;突變窮舉才抓到。
   已寫進記憶 `feedback_fixture_must_state_its_premise`。
4. **又用 heredoc 修 patch 腳本**:`\d` 被吃掉,修正沒寫入、下一步照樣套用帶瑕疵的原版;selftest 當場抓到。
   記憶 `feedback_patch_scripts_go_through_the_write_tool` 補記。
5. **地圖格版面解讀錯**:第二批把地圖格寫成 6-byte 表頭的 byte0/byte1;讀到 `map_cell_info` 才看出是 4-byte 表頭、每格
   `{u16 tile, u8 旗標, u8 byte3}`。位元組證據擋得住抄錯位址,擋不住解讀錯 —— summary 要靠後續函式互相印證。
6. **說了「會繼續」卻停下**:提交 `5d55d039` 後的回報寫了「會繼續往下讀」,實際沒有接著做,使用者問「有自動繼續嗎」才補上。

---

## 5. 未完成(離線可做,有明確形狀)

| 項目 | 現況 | 下一步 |
|---|---|---|
| 人讀命名 | 80 筆;strong 完全無描述 189,遊戲側約 100 | 依 §6 的流程續做第十批起;先挑「完全沒有描述」的遊戲側函式 |
| 函式庫簽名比對 | 未做。EXE 執行期是 `WATCOM C/C++32 Run-Time … 1988-1993`,Open Watcom v2 是 2026 建置(`ow-snapshot.tar.xz`,150 MB),預期命中率低 | 需要時再評估;要下載須使用者同意 |
| `function_names.json` 的 summary 互證 | 名稱錨在位元組上,但 summary 的解讀只有靜態 RE | 讀到相鄰函式時回頭印證;有矛盾就訂正(第四批已訂正一次) |
| 09-18 交接文件 §5 的其餘項目 | 未動(`0x2cad7`、`0x15f84` 的 7 個參數、AI 細節、演出時序、M5) | 同該文件 |

---

## 6. 接手的工作流程(人讀命名)

1. 挑目標:strong、沒有真名、沒有結構性名稱、也不是文件記載的入口,位址在 `0x3702f` 之前,依呼叫端數排序。
2. 讀:`python tools/function_inventory.py --card ADDR`。Ghidra 偽碼對這些函式幾乎沒用(參數推不出來),讀反組譯。
3. 登錄:用 Write 工具寫一支腳本,把 `{addr, name, summary, confidence: static_re, date, evidence: [{at, insn}]}` 附加到
   `docs/data/function_names.json`。**名字只寫讀得出來的機制**,用途是推測時寫進 summary 並標明。
4. 驗:`--check-names`;重生 `--structural docs/data/function_structural_names.json`(新名字會讓更多 wrapper 解得出來);`--coverage` 看數字。
5. 閘門:`git diff --check`、`audit_evidence_provenance --diff/--gate`、`verify_address_citations --diff`、`verify_address_claim_coverage`、
   `verify_tool_hygiene --cross-check`、`verify_generated_artifacts`、`function_inventory --selftest`、`--precommit`。
   **只動資料檔的批次不需要突變窮舉**(`--precommit` 會回報沒有改動的工具);改了 `tools/*.py` 才需要。
6. 逐檔暫存、確認暫存 blob 無 CR、提交、只推 `fork remaster-local`。

---

## 7. 需要使用者決定

- **程式碼層要解析到什麼程度**:沿用 09-18 交接文件 §6.4 的「求可用」路線(使用者已同意「依照你的建議自動繼續進行」)。
  剩下約 100 個遊戲側函式多半是 200~1200 bytes 的流程函式,一批的產出會比前面少(第七~九批三批共 13 筆)。
  若目標改成「求完整」或「能新建遊戲」的特定子系統,挑選順序會不同。
