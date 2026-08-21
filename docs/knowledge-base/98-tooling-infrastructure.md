# 98 — 研究工具基礎建設(非遊戲知識,純 agent 工作效率)

> 跟遊戲本體知識無關,記錄「怎麼更快做 RE 研究」本身的工具鏈,避免每個 session 重新發明。

## Ghidra 批次探測工具(`ProbeBatch.java` + `tools/ghidra_batch_probe.py`)

**問題**:過去每次要用 Ghidra headless 反組譯/decompile/查 xref/查 function bounds 某個位址,
都要寫一支新的 `GhidraScript` 子類別(`FD2_ghidra_projects/Probe*.java`,單一目錄已累積
超過 150 支同類型的一次性檔案),再跑一次 `analyzeHeadless`。每次呼叫都要重付 JVM 啟動
(~2-3 秒)+ project 開啟(~1-2 秒)的固定成本,查 10 個位址就要付 10 次。這個成本在
2026-08-20 之前的多輪 session 裡從未被攤銷過。

**解法(2026-08-20 建的通用工具)**:

- `FD2_ghidra_projects/ProbeBatch.java` — 通用 `GhidraScript`,一次讀入一份 JSON 查詢清單
  (`-postScript ProbeBatch.java <queries.json> <results.json>`,清單/輸出路徑走
  `getScriptArgs()`),對清單裡每一筆位址跑指定的 `action`,把所有結果寫進一份 JSON。
  單筆查詢失敗(位址無效、不在 function 內卻要 decompile…)只標記那筆失敗,**不會**中斷整批。
  支援 6 種 `action`:`disasm`(flow-directed 反組譯,仿舊 `ProbeCommand1012.java` 手法,
  遇 RET/無條件 JMP 或 `max_bytes` 上限停止)、`decompile`、`xref_to`、`xref_from`、
  `function_bounds`(不在任何已知 function 內時明確回傳 `in_function:false`,不是失敗)、
  `bytes`(純 hex dump)。
- `tools/ghidra_batch_probe.py` — Python wrapper,組出正確的 `analyzeHeadless` command line
  (絕對路徑、`-process "FD2.EXE"`、`-readOnly`、`-noanalysis`,這些都是前幾輪 session 已經
  踩過的坑,見 memory `fd2-live-ghidra-headless-probe`),執行、解析輸出、印摘要。用法見該
  檔案頂部 docstring(含完整 queries.json 格式範例),或直接:
  ```
  python tools/ghidra_batch_probe.py --queries queries.json --output results.json
  ```

**驗證(2026-08-20)**:用它重跑 3 個本 session 已知答案的位址,結果與既有文件記錄逐位元組吻合:
- `0x14818` 反組譯起始 28 條指令(至第一個無條件 JMP 為止)與既有 disasm 記錄一致;
  `function_bounds` 回傳 `0x14818..0x149f7`(480 bytes),與 doc03/doc58 記錄的「size 480」精確吻合。
- `0x2ff01` 的 `function_bounds` 回傳 `0x2ff01..0x30e24`(size=3876),與
  `probe_decompile_2ff01_out.txt` 當時 Ghidra 自己算出的 `body: 0002ff01..00030e24 size=3876`
  完全一致。
- `0x4df4c` 的 `disasm`(PUSH EBP…LOOP 0x4df65…RET)逐指令、逐 byte 與
  `probe_ch23post_4df4c_out.txt`(doc58 續三十/續三十一記錄的同一位址)吻合;`decompile`
  輸出的 C 偽代碼也逐字元相同;`xref_to` 找到的 31 個呼叫端位址與清單順序也完全一致。

10 筆混合查詢(disasm/decompile/xref_to/xref_from/function_bounds/bytes,含 1 筆刻意寫錯的
`action` 測試錯誤處理)一次 `analyzeHeadless` 跑完約 9-10 秒。對照組:過去每個位址各自跑一次
`analyzeHeadless` 的模式下,10 個位址需要 10 次獨立呼叫,每次都重付 JVM 啟動+project 載入
成本(單次約 9-10 秒起跳)——粗估這次批次省下了 **9 次 JVM 啟動+project 載入**,約 10 倍
wall-clock 加速(10 個查詢:一次呼叫 ~10s vs. 10 次呼叫 ~90-100s)。查詢數越多,攤銷效果越明顯。

**之後的 agent 該怎麼用**:除非只是要查單一位址且不在意那幾秒鐘固定成本,否則優先用這支工具
把當輪所有已知要查的位址一次列成 queries.json 丟進去,不要再回頭寫新的 `Probe*.java` 一次性
檔案。舊的 `Probe*.java` 檔案保留(考古/範例用途),但新查詢不建議再用該模式。

## 已驗證位址資料庫(`docs/data/verified_addresses.json` + `known_address_errata.json`)

**問題**:同一個 EXE offset 散落在多個 `.py`/`.go`/`.md` 檔案裡各自硬編碼,沒人同步更新,
導致重複踩坑——本 session 就至少修過 `tools/dump_exe_tables.py` 全部 9 張表的 offset,以及
`tools/export_acting_resources.py` 的 directory/data offset,兩次都是「舊版(357074B,已遺失)
EXE 的位址被誤用在新版(509158B)基準上」這同一類 bug。位址勘誤(如 `0x2a6bd`→`0x2ff01`、
`0x4dbfc`→`0x4df4c`)分散在各章節文件裡,新 agent 很容易在還沒讀到勘誤註記前就先引用了
舊的錯誤位址。

**解法(2026-08-20 建的統一資料庫)**:

- `docs/data/verified_addresses.json` — 結構化的位址清單,每筆條目含 `address`(位址字面值)、
  `linear_or_file_offset`(`linear`=程式碼/全域資料位址,新舊版 EXE 通用;`file_offset`=內嵌
  資料表在檔案內的 byte offset,隨 EXE 版本改變,見檔案 `_meta` 裡的換算規則)、`semantic`
  (語意描述)、`confidence`(`verified`=有反組譯佐證 / `inferred`=合理推測未證實 /
  `disputed`=文件間有矛盾)、`source_doc`/`source_section`/`verified_date`/`notes`。截至
  2026-08-20 收錄 45 筆,優先涵蓋本 session 新增/訂正的位址、`dump_exe_tables.py` 9 張表
  offset、以及 UI-04/AoE/SFX 派送等高頻引用的核心位址。
- `docs/data/known_address_errata.json` — 專門收錄「曾被誤植、後來訂正」的位址對照表(10 筆),
  每筆含 `wrong_address`/`correct_address`/`discovered_date`/`discovery_method`/`root_cause`/
  `still_pending`。這是最容易被誤用的高風險資訊,包含 `0x2a6bd→0x2ff01`、`0x276ec→0x2cf30`、
  `0x4dbfc→0x4df4c`、`0x3453E→0x34894`、crit 表 offset `0x773AF→0x774BC`、以及兩個舊版
  EXE 位址系統性失效的案例(`dump_exe_tables.py` 的 movement_cost/class_equip 表、
  `export_acting_resources.py` 的 directory/data offset)。
- `tools/query_verified_address.py` — 查詢 CLI,不依賴第三方套件:
  ```
  python tools/query_verified_address.py 0x14818       # 精確位址查詢(同時檢查兩份 JSON)
  python tools/query_verified_address.py --search "AoE"  # 關鍵字模糊搜尋 semantic/notes
  ```
  精確查詢會同時比對 `known_address_errata.json`——如果查的位址是某筆勘誤的「錯誤舊位址」,
  會印出醒目警告;如果是「已訂正的正確位址」,也會一併顯示對應的勘誤脈絡。

**怎麼維護**:未來每次訂正/新增一個位址語意時,在 `verified_addresses.json` 追加或更新一筆
條目;若是「舊位址錯誤→新位址」的勘誤,額外在 `known_address_errata.json` 記一筆。**不需要**
每次都把新位址塞進這裡才能繼續工作——這是輔助查詢用的資料庫,不是強制關卡;但引用任何
「聽起來眼熟」的位址前,先花一秒查一下能省下一整輪的重工。目前**尚未**把既有 `.py`/`.go`
工具改成讀這份資料庫(那是後續逐步遷移的工作,範圍較大,本輪只建資料庫本身+CLI)。

## 已知盲點:`FD2Analysis3` 的 Ghidra decompile 系統性不顯示呼叫引數(2026-08-21 發現)

**問題**:在 doc35 §9.7 的「行為指紋全域掃描」任務裡,第一輪嘗試用 `DecompInterface.
decompileFunction` 產生的 C 偽代碼文字去比對呼叫引數字面值(例如「有沒有把 `54` 傳給
資源載入器」),結果全域 0 命中。抽查已知一定會呼叫該 loader 的既有位址(`0x25977`)後發現
**decompile 輸出把呼叫顯示成空括號**(`FUN_000111ba()`),即使目標 function 本身已有具名的
正式簽名(`int __stdcall FUN_000111ba(undefined4 param_1,int param_2)`)。進一步抽查
`FUN_000111ba` 自己的 decompile,發現**它自己內部呼叫的 6 個 helper 也全部是空括號**——
證實這不是單一 function 的問題,是這個 project 的 decompiler 在呼叫端引數渲染上**系統性
失效**(推測是 Watcom stdcall 呼叫端的 p-code 引數綁定沒有被完整重建;與是否加 `-noanalysis`
無關,decompile 本身有自己的 per-function p-code 正規化)。

**影響**:任何「在 decompile 偽代碼文字裡搜引數字面值/常數」的方法論,在 `FD2Analysis3` 上
**先天不可靠**——先前一些文件段落(如 doc35 §9.2)裡出現的「`0x111ba("TAI.DAT"@0x52393,
prevSlot, idx)`」這類帶引數字面值的寫法,應理解成分析當時**人工從 disasm 逐條核對出來的
還原結果**,不是 Ghidra decompile 視窗直接吐出的原始輸出——回頭核對前不要假設兩者等價。

**替代方法(已驗證可信)**:改用純指令層級,不依賴 decompiler 對引數的重建:
1. 用 `insn.getFlowType().isCall()` + `insn.getFlows()` 判斷一條指令是否呼叫目標位址
   (doc35 §9.1 method 4、§9.7.3 都用這招,已用已知 ground truth——boot loader 依序載入
   FDOTHER #0x1f/#1/#2/#3/#4/#5/#6——逐位元組核對過)。
2. 呼叫端引數:從 CALL 往回掃最近幾條指令裡的 `PUSH <立即數>`(stdcall 引數由右至左壓入,
   緊接在 CALL 之前),用 `Instruction.getScalar(0)` 取立即數值。
3. 這招仍有盲點:`PUSH <暫存器>`(引數先被 `MOV reg,imm` 或 if/else 分支鏈設定後才 PUSH)
   看不到立即數。要補這個洞,需要對整個 function 做**單趟正向掃描**,追蹤每個暫存器「最後
   一次被 `MOV reg,imm` 設過的值」以及「這個 function 裡曾經被設過的所有不同立即數值」
   (可以覆蓋 doc35 §9.7.5 記錄的「預設值 + compare-and-branch 覆寫」樣式),`PUSH reg` 時
   回報該暫存器的歷史候選值集合。這仍然無法解開真正迴圈/表格算出來的索引(例如
   `for(i=0;i<n;i++) buf[i]=loader(...,table[i])`),那類狀況要誠實標記「未解出」,不能
   當成「已排除」。

**之後的 agent 該怎麼用**:任何要用 Ghidra decompile 文字比對引數/常數的新研究,**先用一個
已知答案的呼叫點驗證一次**(例如上面的 boot loader FDOTHER 序列),不要預設 decompile 輸出
忠實反映呼叫引數;預設改用指令層級 CALL-flow-target 掃描,必要時加暫存器歷史回溯這一層。
範例腳本(可直接參考或複製改寫):`FD2_ghidra_projects/GlobalBehaviorScan.java`(v1,示範
decompile 文字比對本身的盲點,對照用)、`GlobalBehaviorScanV2.java`(v2,指令層級主方法)、
`GlobalBehaviorScanV3.java`(v3,加暫存器歷史回溯)、`GlobalBehaviorScanDebug.java`
(輔助稽核,列出每個呼叫端完整的 decompile 引數文字,是本次發現盲點的直接工具)。
