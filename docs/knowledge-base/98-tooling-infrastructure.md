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
