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

## N-way 平行 dosbox-x live-verification harness(`tools/dosbox_harness.sh`,2026-08-24)

**問題**:`docs/knowledge-base/91-worklist.md` 還剩約 30 個 E-class(需要 live DOSBox-X 驗證)
項目,doc48 §8 的 recipe 一次只能跑一顆 dosbox-x(固定 tmux session `dbg`、Xvfb `:99`、工作
目錄 `~/fd2-run`),多個互不相關的待驗證項目只能排隊一個一個做。

**解法**:`tools/dosbox_harness.sh`,一支純 bash 腳本(這台專案 `tools/` 目錄本身已有多支
`.sh` 走 `set -euo pipefail` + 純指令列風格,這支延續同樣風格),把 doc48 §8.4 的單 instance
recipe 包成可命名、可重複呼叫、彼此隔離的子指令:

```
tools/dosbox_harness.sh launch <name> [keepalive_seconds]   # 起一顆全新隔離 instance(長駐,見下)
tools/dosbox_harness.sh screenshot <name> [output_path]     # 截當前畫面成 PNG
tools/dosbox_harness.sh send-keys <name> <key> [key2 ...]   # 送遊戲按鍵(xdotool key 語法)
tools/dosbox_harness.sh enter-debugger <name>                # 送 Alt+Pause,切進 ncurses debugger TUI
tools/dosbox_harness.sh debugger-cmd <name> <指令文字...>     # 對 debugger console 打字+Enter
tools/dosbox_harness.sh status                                # 列出目前所有 harness 管理的 instance
tools/dosbox_harness.sh teardown <name>                       # 收掉單一 instance
tools/dosbox_harness.sh teardown-all                          # 收掉全部 harness instance
```

因為 Windows 側呼叫 WSL2 有續五十五記錄的 `$變數`/`~`路徑被外層 relay 吃掉的問題,這支工具
**寫成實體 `.sh` 檔案放在 repo 裡**(不是塞進 `bash -c '...'` 字串),呼叫方式固定是:

```
MSYS_NO_PATHCONV=1 wsl -d Ubuntu bash /mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/dosbox_harness.sh <子指令> ...
```

**隔離設計(每個 instance 三件事都各自獨立,不只是換名字)**:
1. **Xvfb TCP display**:自動配置,從 `:199` 起、每個新 instance +100(`:199`/`:299`/…),
   配置時同時檢查①harness 自己的 registry(`~/.fd2-harness/instances/*.state`)②
   `ss -tln` 實際監聽中的 port,雙重確認不撞號——不只避開彼此,也避開 doc48 §8.4 canonical
   recipe 固定用的 `:99`。
2. **獨立 tmux server**:harness 的所有 tmux 操作一律加 `-L fd2harness`,也就是完全另開一個
   tmux **server 進程**,不是在 default server 上開不同 session 名字。這樣即使將來子指令的
   session 名字算錯或打錯,`kill-session`/`kill-server` 的作用範圍也物理上不可能碰到
   default server 上的 `dbg`(doc58 續五十九/續六十在跑的那個)。
3. **獨立工作目錄**:每次 `launch` 都把 `~/fd2-run`(canonical 遊戲檔案來源,可用
   `FD2_HARNESS_SOURCE_DIR` 覆寫)`cp -r` 一份全新的到 `~/fd2-run-harness-<name>`,單顆
   87MB、機器有 950GB 可用空間,不共用、不互相污染存檔/暫存檔。

**建置過程中踩到的坑**:
- **真的抓到一個 bug**:第一版把 `Xvfb "127.0.0.1:$port" ...` 當成顯示器參數直接丟給
  `Xvfb`,結果 Xvfb 直接報 `Fatal server error: Unrecognized option: 127.0.0.1:199` 整個
  無法啟動——`Xvfb` 的顯示器參數只能是裸 `:N`(display number),`127.0.0.1:N` 這個完整
  TCP 位址形式**只用在 client 端**(`xdotool`/`dosbox-x`/`import` 的 `DISPLAY` 環境變數),
  doc48 §8.4 的範例其實已經是對的寫法(`Xvfb :99 ...` + `export DISPLAY=127.0.0.1:99`),
  是這次重新包裝成參數化腳本時手滑弄反了兩者。已修正並重新實測通過。
- 延續 doc48 §8.4 續二十一/續四十六的既有教訓:`launch` 子指令**必須**以
  `exec sleep <keepalive>` 結尾撐住整條 WSLg 連線,呼叫方(agent)**必須**把整個
  `wsl -d Ubuntu bash .../dosbox_harness.sh launch ...` 當成單一次呼叫背景執行(工具的
  `run_in_background:true`),不能自己在腳本內部再包一層 `&` 讓外層 wsl.exe 提前 return——
  否則同樣會在 15-60 秒內被整組回收。這個限制现在是**per-instance**的:每個 `launch` 呼叫
  都要各自維持自己的一條長駐連線,`status`/`screenshot`/`send-keys`/`debugger-cmd`/
  `teardown` 才是可以隨時單發呼叫的短指令。
- **teardown 絕不用 blanket `pkill -9 dosbox-x`/`pkill -9 -f Xvfb`**(doc48 §8.4 給單
  instance 手動復原時用的寫法)——那樣會連 canonical `dbg`/`:99` 或別的 harness instance
  一起殺掉。改成只 kill 自己 registry 記錄的**具體 PID**,而且 kill 前用
  `ps -p <PID> -o args=` 核對該 PID 現在跑的程式仍然是預期的 Xvfb/sleep(防呆:萬一該
  PID 因為系統重用而變成別的進程,不會誤殺)。
- `launch` 只確認 DOSBox 視窗**存在**(`STATUS=running`),**不代表**開場動畫/標題畫面已經
  跑完——doc48 既有的「送鍵前先 screenshot 確認畫面」原則對每個 harness instance 依然
  適用,harness 本身不擅自幫你判斷「已經到標題」。
- `teardown` 預設**保留**工作目錄(`~/fd2-run-harness-<name>`,方便事後檢查崩潰現場的
  `FD2.TMP`/存檔),只清 registry 狀態檔+process;要收空間自己手動 `rm -rf`。

**2026-08-24 實測驗證(不是紙上談兵,是真的並行跑過)**:

- 驗證前用 `ps aux`/`tmux ls` 確認 doc58 續五十九/續六十的 canonical session(`dbg`、
  `:99`、`~/fd2-run`)當時確實正在跑,harness 全程避開這三個名字,測完再次確認它完全沒被動過。
- `launch alpha` + `launch beta`(各自背景執行,間隔約 40 秒)成功各自配到 `:199`/`:299`,
  `status` 顯示兩者 `XVFB_OK`/`SESS_OK` 皆為 `yes`,加上原本的 canonical instance,當時
  **同時有 3 顆 dosbox-x 進程在跑**。
- `screenshot alpha`/`screenshot beta` 同一時刻各截一張:alpha 已到標題畫面(START/LOAD/
  CONTINUE 選單),beta 還在約 30 秒的開場過場動畫中途——直接證明兩者進度完全獨立,不是
  同一個畫面複製出來的。
- 兩者都到標題畫面後,對 alpha 送 `send-keys alpha Down Down`(不碰 beta),再次分別截圖:
  alpha 反白移到 `CONTINUE`,beta 仍停在預設的 `START`——證明 X11/xdotool 按鍵通道確實
  各自獨立路由,沒有互相干擾。
- 對 beta 送 `enter-debugger` + `debugger-cmd beta 'D CS EIP'`,`tmux -L fd2harness
  capture-pane` 讀到 `DEBUG: Set data overview to F000:CFD0`,證明 debugger console
  通道也正常運作;之後重新截圖 alpha,畫面仍是先前的 `CONTINUE` 反白狀態沒有變化,證明
  beta 進 debugger 這件事沒有影響到 alpha。
- `teardown-all` 之後,`ps aux`/`tmux ls`(default server)/`tmux -L fd2harness ls` 三方
  核對:canonical `dbg`/`:99`/dosbox-x 三個進程原封不動仍在執行,harness 自己開的兩顆
  Xvfb/dosbox-x 全部消失,`fd2harness` 這個 tmux server 整個不存在了(`no server
  running`)——teardown 精準,沒有誤傷、也沒有殘留。

**資源使用量測(用來定並行上限,不是憑空假設)**:3 顆 dosbox-x 同時跑(canonical + 2 個
harness)時,`free -h` 顯示僅用掉 954MiB/7.8GiB(這台機器 `.wslconfig` 限制的 WSL2 VM 記憶體
上限),`uptime` load average 0.43(4 核心)——完全沒有壓力跡象,每顆 dosbox-x 進程 CPU
佔用約 13-23%。

**建議並行上限:2-3 顆 harness instance**(疊加在可能同時存在的 1 顆 doc48 §8.4 canonical
instance 之上)。**2 顆是這次直接實測驗證過的**(如上);3 顆是根據觀察到的資源餘裕(3 顆
共用時記憶體/CPU 都遠低於 `.wslconfig` 的 4 核心/8GB 上限)做的保守外推,**尚未實際測過 3
顆同時 launch**,下一輪如果要衝更高並行數,應該先重新量測而不是直接假設會線性延伸——
dosbox-x 的 cycles 模擬對單一 instance 是 CPU-bound 的,這台 VM 實際只有 4 個邏輯核心,
核心數才是真正的硬上限,記憶體目前看起來還不是瓶頸。

**環境變數覆寫**(不想用預設值時):`FD2_HARNESS_REGISTRY_DIR`(state 檔目錄,預設
`~/.fd2-harness/instances`)、`FD2_HARNESS_TMUX_SOCKET`(預設 `fd2harness`)、
`FD2_HARNESS_SOURCE_DIR`(canonical 遊戲檔案來源,預設 `~/fd2-run`)、
`FD2_HARNESS_DOSBOX_BIN`(dosbox-x 執行檔路徑,預設
`~/fd2-dosbox-build/dosbox-x/src/dosbox-x`,與 doc58 續二十一起 WSL2-native 建置沿用的
同一顆二進位檔)、`FD2_HARNESS_SHOT_DIR`(screenshot 輸出目錄,預設
`<repo>/.wsl_build/harness`,已在 `.gitignore` 的 `.wsl_build/` 規則下,不會誤入版控)。

## Ground-truth 執行流程追蹤(`tools/dosbox_exec_trace.sh` + `tools/dosbox_exec_trace_analyze.py`,2026-08-25)

**問題**:doc35 §9 的 party montage renderer 獵尋(§9.1-§9.14,15+ 輪)一直是「猜一個候選位址→
驗證→失敗」的模式——每個候選都靠人工推理(位址算術、decompile 偽代碼、live 斷點取樣)挑出來,
猜錯了就要重新猜。這個方法論本身有上限:Ghidra 的 base 分析在關鍵區域(§9.10-§9.11 發現的
`0x31529`/`0x320a1` 一帶)從未建立 function boundary,`function_bounds`/`xref_to`/`call_scan`
全部失靈,純靜態方法在這種區域**structurally 找不到任何線索去猜下一個候選**。

**解法思路**:不用猜的——直接記錄 CPU 在目標畫面(例如結局 CG 播放中)實際執行過的**每一個**
位址,再拿這份 ground-truth 清單去跟 Ghidra 比對,凡是「Ghidra 完全沒建過 function boundary」
的位址,就是有真實證據支持的候選,不是猜測。

**第一步(前情提要,不要重做):dosbox-x heavy-debug build 內建就有這個功能,不需要自己刻**。
WebSearch(`"dosbox-x debugger LOG command trace instructions"`)+ 直接讀 WSL2-native 建置
(`~/fd2-dosbox-build/dosbox-x/src/debug/debug.cpp`,doc48 §8 記載的同一顆原始碼)證實:
`--enable-debug=heavy`(這個專案的建置腳本本來就有加,見 doc48 §2)編進了一組完整的指令追蹤
debugger console 指令——`LOG`/`LOGS`/`LOGL`/`LOGC`/`ADDLOG`/`HEAVYLOG`,`strings` 對建好的
二進位檔案確認全部存在(2026-08-25 對這個專案實際用的 build 二進位親自驗證,不是查文件猜的)。
其中 **`LOGC <hex count>`** 是本工具用的變體——`debug.cpp` 原始碼裡 `LogInstruction()` 對
`cpuLogType==3`(`LOGC` 對應的模式)只印一行 `"CCCC:IIIIIIII"`(`setw(4) SegValue(cs) << ":" <<
setw(8) reg_eip`),完全不含暫存器/flag(`LOG`/`LOGS`/`LOGL` 三個變體都會印完整暫存器狀態,
每行貴很多,對純位址獵尋沒有額外價值)。所以**不需要自己刻一個腳本化單步+EIP 擷取的替代方案**
——原本規劃書 step 3 設想的「單步太慢,退而求其次用取樣」這條備案完全沒用到,LOGC 本身已經是
一個高效、逐指令、非取樣的完整追蹤工具。

**LOGC 的關鍵行為(全部是本輪 live 實測驗證,不是讀 source 猜的)**:
1. 在 debugger console(`Alt+Pause` 進去、TUI 顯示 `I->` 提示字元的狀態)下 `LOGC <hex count>`
   + Enter,會把 `debugging` 旗標設回 `false`、呼叫 `DOSBOX_SetNormalLoop()`——也就是**立刻
   恢復真正的模擬執行**,不是純粹的 debugger 內部操作。每執行一條指令就在
   `DEBUG_HeavyIsBreakpoint()`(`C_HEAVY_DEBUG` 編譯開關下才存在,per-instruction 呼叫)裡
   寫一行到 `LOGCPU.TXT`、遞減計數器,計數器歸零時自動 `DEBUG_EnableDebugger()`(游戲此時
   凍結,回到 debugger TUI,印出 `DEBUG: cpu log LOGCPU.TXT created`)。
2. **這段追蹤期間遊戲畫面持續正常渲染、也持續正常接受 `xdotool` 鍵盤輸入**——這是最關鍵的
   實測發現,不是理所當然的事(原本擔心 LOGC 是一個會凍結整個模擬器的同步阻塞操作)。實測
   方法:armed 一個 30M/150M/600M 指令的 LOGC 之後,立刻對遊戲視窗送出正常的 `xdotool key
   Return` 序列並 `import -window root` 截圖,畫面確實持續前進(從角色走路→轉送站對白→CG
   過場→詩句捲動→角色卡),證實 LOGC 不是需要「先跑完、再操作」的阻塞式操作,可以邊記錄
   邊正常玩。
3. **吞吐量**(這台專案 WSL2 VM 實測,2026-08-25):10,000,000 instructions ≈ 3.8 秒 wall
   clock(≈140MB 檔案,14 bytes/行的固定格式);600,000,000 instructions 在本輪實際任務裡
   完整跑完,產生 7.9GB 的 `LOGCPU.TXT`。這個吞吐量**跟遊戲的模擬速度(`cycles=5000`)是兩回事
   ——不要把 `cycles=5000` 讀成「每秒 5000 條指令」**:`cycles` 是每個 timer tick 的 CPU 週期
   預算,timer tick 本身在沒有真實 vsync 節流(Xvfb 沒有螢幕刷新率限制)的環境下可以跑得比
   1995 年原生硬體快很多,LOGC 底下的迴圈更是完全不受這層節流影響(它直接接管主迴圈,寫檔
   I/O 才是唯一瓶頸)。實務結論:**幾百萬到幾億這個量級的 hex count,幾秒到一分鐘內就能跑完,
   足以涵蓋好幾秒鐘的真實遊戲內容**,不需要精算「這個場景大概要多少條指令」,直接給一個寬鬆
   的大數字(例如 `600000000` 對應本輪實測涵蓋了從戰前對白到角色卡渲染的完整轉場)。
4. **去重後的位址數遠小於原始行數**——600,000,000 行(逐指令、含所有重複的迴圈疊代)`awk
   '!seen[$0]++'` 單趟去重後只剩 **12,297** 筆唯一 `CS:EIP`(其中主程式碼段 `CS=0170` 佔
   8,727 筆),再往下只有 1,579 筆(18%)落在 Ghidra base 分析從未建過 function boundary
   的區域。這代表「窮舉去重」這件事本身**完全可行**,不需要退而求其次做取樣——去重後的候選
   清單小到可以在幾秒內全部餵給 `ghidra_batch_probe.py` 做 `function_bounds` 批次查詢
   (8,727 筆查詢實測 6.6 秒跑完,見下)。`awk` 去重本身(不是 `sort -u`,那個量級會太慢)
   對 600M 行、7.9GB 的檔案約 70 秒完成。

**工具本身**:
- `tools/dosbox_exec_trace.sh`——WSL 端(bash),負責「武裝」LOGC(`arm <tmux-session>
  <hex-count> [workdir]`,對已經在 debugger console 待命的 session 送 `LOGC <hex>` +
  Enter)、輪詢是否跑完(`wait-done`)、查看目前進度(`status`)、單趟 `awk` 去重
  (`dedup`,輸出 `trace_unique_cseip.txt`)。**只負責 arm/collect,不負責送遊戲按鍵**——
  每個場景的觸發序列都不一樣(doc58 已經記錄好各章節的具體按鍵序列),武裝完之後用平常的
  `xdotool`/`tmux send-keys` 照舊操作即可,不需要學新的按鍵介面。跟 `tools/dosbox_harness.sh`
  一樣支援 `FD2_TRACE_TMUX_SOCKET` 覆寫(用在 harness 的私有 tmux server 上,而不是
  doc48 §8.4 canonical `dbg` session 用的 default server)。
- `tools/dosbox_exec_trace_analyze.py`——Windows 端(python,呼叫本機 Ghidra 安裝),吃
  `trace_unique_cseip.txt`,做三件事:①依 `--cs`(預設 `0170`)過濾、依 `--delta`(預設
  `0x19C000`,這個專案 live→native 位址換算的既有常數)換算成 native 位址、去重;②把換算
  後的 native 位址清單餵給 `tools/ghidra_batch_probe.py` 做一次批次 `function_bounds` 查詢;
  ③依結果分三類:**(a) 已知/已記錄**——`in_function=true` 且該 function 起點位址能在
  `docs/knowledge-base/*.md` 裡用**位元組邊界安全**的 regex 找到(見下的「假陽性」教訓);
  **(b) Ghidra 已分析但未記錄**——`in_function=true` 但文件裡查無此位址,值得下一輪直接
  `decompile` 看內容;**(c) 完全未分析**——`in_function=false`,Ghidra base 分析從未在這個
  位址建過 function boundary,這是最有價值的一類,再依 `--cluster-gap`(預設 `0x40` bytes)
  把相鄰位址合併成連續區塊,並且**對區塊裡的每一個位址個別做文件比對**(不是只查區塊起點/
  終點)——因為像 `0x320a1` 這種已知案例,它自己不是 function 起點,單查邊界值查不到,但
  區塊裡別的位址可能有記錄。

**踩到並修正的一個坑(值得記錄,免得下一輪重踩)**:第一版的文件比對用裸子字串搜尋
(`hex_string in text`),結果對 `0x43270` 一帶的位址(5 位十六進位、沒有字母的短數字)產生
**假陽性**——`0x432b2` 命中是因為它剛好是某個 MD5-like hash 字串
(`3c0a2c935260b8ca80432b25b3600111`)的子字串,`0x43385` 命中是因為它剛好是某個 baidu.com
URL(`597a0643385421312b5243cf.html`)的子字串,兩者都跟位址完全無關。**這正是 doc35 §9 整條
調查線反覆踩過的「位址巧合重疊」陷阱的同一個坑,只是這次是文件比對版本**,不是 live 驗證版本
——教訓一致:**任何位址字串比對都要做邊界檢查**(`grep_docs_for_address()` 改成
`(?<![0-9A-Fa-f])(?:0[xX])?<hex>(?![0-9A-Fa-f])` 這種前後不能接續十六進位字元的 regex,
確認不是更長十六進位字串/URL/hash 的子字串),不能只做裸子字串搜尋。修正後重新核對過幾個
`0x24b14`/`0x25089` 這類確實命中的案例,確認都是文件裡貨真價實的位址引用(如
`docs/knowledge-base/50-cutscene-script-system-design.md` 的「`0x25186 call 0x24b14(item
0x64)`」),不是巧合子字串。

**已知限制(誠實列出)**:
1. `LOGC` 只記 `CS:EIP`,不記完整 call stack/暫存器——知道「執行過這裡」,不知道「從哪裡呼叫
   過來的」;要接上呼叫鏈仍要另外對候選位址做 `xref_to`/`call_scan`(常常一樣落空,見 doc35
   §9.10-§9.11 的既有經驗)或 live 讀 `D SS:ESP` 找 return address。
2. `.gitignore` 的 `.wsl_build/` 規則下,原始 `LOGCPU.TXT`(GB 級)與去重後的
   `trace_unique_cseip.txt`(KB~數百 KB 級)都不進版控——只有分析結果(本文件/doc35/doc58
   的文字紀錄)會留下來,原始追蹤檔案是單輪 process 產物,跟 harness 的 screenshot 同等級。
3. 文件比對(category a/c-known vs c-new 的判定)是 **best-effort、非權威**——比對到只代表
   「該去讀那份文件」,讀了才能判斷這個位址是不是真的已經被理解;沒比對到也不保證真的是全新
   (文件可能用了不同的位址系統,如 §9.14.4 記錄過的「另一份 IDA session/live 位址誤記成
   linear 位址」假說)。
4. `LOGC` 記錄期間如果遊戲觸發了 dosbox-x 本身的其他斷點(`BP`/`BPM`)也會被打斷提前結束——
   本輪操作時特別注意在武裝 `LOGC` 前先清掉不需要的舊斷點,避免誤判「LOGC 提前結束」為
   「count 已經跑完」。
5. 本工具驗證了「600M 指令、8700+ 唯一位址、批次比對 6.6 秒」這個量級可行,**沒有**測試更大
   數量級(例如數十億指令)是否會遇到新瓶頸(檔案系統/awk 記憶體),下一輪如果要拉更長的
   追蹤窗口,應該先重新量測而不是直接假設線性延伸。

**首次實戰結果**:2026-08-25 用這套工具實際捕捉了 ch27 戰前「轉送站幻象」montage 的完整執行
流程(從戰前對白、經 CG 過場、詩句捲動、到萊汀角色卡渲染),完整技術細節與交叉比對結果見
`docs/knowledge-base/58-remake-live-verification-log.md` 續六十六與
`docs/knowledge-base/35-battle-animation-rendering.md` §9.15。

## DOSBox-vs-remake byte-exact pixel diff harness(`tools/dosbox_diff_harness.sh` + `tools/dosbox_diff_harness.py`,2026-08-26)

**解決的問題**:`docs/knowledge-base/91-worklist.md`的 UI-VIS-DIFF-HARNESS 項目要求「固定同一
FD2.SAV／roster／camera／cursor／tick,輸出DOSBox與remake 320×200 pair及pixel diff」。這件事
本身在本 session 已經被多個獨立回合手刻過至少 5-6 次(UI-08-TOWN-VARIANT0、UI-09-CH02-SECRET-
SHOP-*、UI-VIS-TOWN variant1/2、UI-SHOP-*-E2……),每次都重新發明一套螢幕截圖/裁切/diff腳本,
且**達到的嚴謹度不一致**——UI-08-TOWN-VARIANT0 用(已移除的)Docker pipeline 取得「320×200 raw
RGB 全幀 MD5 相同」等級的證據,但同年 UI-VIS-TOWN variant1/2 改用`tools/dosbox_harness.sh`的
`import -window root`+手動裁切/resize,文件裡誠實記錄了「未達 variant0 等級的 byte-exact RGB
MD5」這個倒退。本工具的目的是把「怎麼拿到真正 byte-exact 的 320×200 pair」這件事一次做對、
包成可重複呼叫的形式,不要再讓下一輪 E2 任務手刻出比 variant0 更弱的版本。

**關鍵發現:variant0 的 byte-exact 證據其實來自 plain `dosbox`,不是 `dosbox-x`**——回頭讀
`tools/docker/fd2-dosbox-screenshot.sh`(2026-08-26 稽核時發現的既有腳本,先前沒有文件明確點出
這一層)才確認:它的 config 用了 `[sdl] output=surface` + `[render] scaler=none aspect=false`,
呼叫的二進位是 `dosbox`(套件版 0.74-3),**不是**`docs/knowledge-base/48-dosbox-x-debugger-
build.md`§8 一路沿用的 heavy-debug `dosbox-x`。這個差異是本工具重建時卡關的關鍵:同一組
config 套用在 `dosbox-x` 上,視窗仍然會是 640×417(附帶`Main CPU Video Sound DOS Drive Capture
Debug Help`GUI選單列,即使非全螢幕),因為 dosbox-x 的視窗化 SDL 輸出本身就會畫這條選單列,
`scaler=none`/`aspect=false`不影響它;換成套件版 `dosbox`(這台機器上本來就有裝,
`/usr/bin/dosbox`,`apt list --installed`確認)後,同一組 config 讓視窗**精確**等於當前模擬
視訊模式的原生解析度(標題/戰鬥選單等 mode 13h 畫面量到 320×200,開場動畫的 SVGA 過場量到
640×400,無任何 letterbox/選單列)。**純截圖工作不需要 debugger**(本任務brief已預告這點),
所以放棄 dosbox-x 換 plain dosbox 沒有任何功能損失。

**架構**:

1. `tools/dosbox_diff_harness.sh`(WSL 端)——`tools/dosbox_harness.sh`的姊妹腳本,**不是**修改
   它(避免影響同時可能在跑`tools/dosbox_harness.sh`的其他 agent),完全獨立的 registry
   (`~/.fd2-diffharness/instances`)、tmux socket(`fd2diffharness`)、Xvfb port range(`:799`
   起,跟 canonical `:99` 與 harness 的 `:199/:299/…` 都不重疊)。子指令:
   ```
   dosbox_diff_harness.sh launch <name> [keepalive_seconds] [sav_file]
   dosbox_diff_harness.sh raw-screenshot <name> [output_path]   # 精確 320x200,無法達成則 fail closed
   dosbox_diff_harness.sh geometry <name>
   dosbox_diff_harness.sh send-keys <name> <key> [key2 ...]
   dosbox_diff_harness.sh wait-pixel <name> <x,y,r,g,b> <delay_s> <max_tries>
   dosbox_diff_harness.sh status / teardown <name> / teardown-all
   ```
   `launch`可選第三參數直接把一份已 chapter-jump-patch 過的 FD2.SAV 覆蓋進隔離 workdir(啟動前
   複製,不是遊戲執行中熱替換)。`raw-screenshot`在送出`import -window <winid>`前先用
   `xdotool getwindowgeometry`核對視窗剛好 320×200,不是就直接報錯**拒絕**產出(不會偷偷
   crop/resize 掩蓋過去——這正是本工具要修正的舊 rigor gap),成功時額外印
   `rgb_md5=<內容雜湊>`(`convert img.png rgb:- | md5sum`,只雜湊像素內容不含 PNG 容器 metadata)。
   Xvfb screen 用 1024×768(不能比開場動畫的最大視窗小,否則視窗被裁切/位移,本輪實測踩過)。

2. `tools/dosbox_diff_harness.py`(Windows 端)——單一 CLI 把整條流程接起來:
   ```
   # chapter-jump патch 一份真實 FD2.SAV 的 slot0 章節 byte(沿用 UI-VIS-TOWN variant1/2 已驗證
   # 過的技巧,原理見 tools/fd2save.py;chapter_byte+1 = 存檔清單顯示的「第N章」)
   python tools/dosbox_diff_harness.py patch-sav --src FD2.SAV --dst out.SAV --chapter-byte 0x01

   # 完整城鎮 hub 情境:啟動/沿用 diffharness instance、Title→LOAD→(patch過的存檔)→城鎮 hub、
   # 兩側各自截圖、對每個候選 pulse(0..3)做 diff、輸出 side-by-side PNG + JSON report
   python tools/dosbox_diff_harness.py town --instance diffharness \
       --chapter-byte 0x01 --node town_ch02 --selection 0 --pulses 0,1,2,3

   # 低階原語(自組其他情境的 navigate 序列時用)
   python tools/dosbox_diff_harness.py raw-shot --instance diffharness --out out.png
   python tools/dosbox_diff_harness.py remake-shot --node town_ch02 --town-state 0,0 --out out.png
   python tools/dosbox_diff_harness.py diff --a orig.png --b remake.png --out-prefix report
   ```
   remake 側呼叫的是**既有的**`remake/fd2-linux-verify`(2026-08-15 build,Docker 移除前建置、
   本輪確認在 WSL2-native Xvfb 下可直接執行,不需要重建),用`FD2_CAMP_NODE`/`FD2_SHOT_TOWN_STATE`/
   `FD2_SHOT`/`FD2_SHOT_FRAME`驅動,並自動補上`FD2_ORIGINAL_FDOTHER`/`FD2_ORIGINAL_FDTXT`/
   `FD2_ORIGINAL_DATO`(**本輪新發現**:沒有這三個環境變數,native town/shop/church 這類原生 UI
   compositor 完全不會啟動,`FD2_SHOT_TOWN_STATE`自己的「必須是 native town node」檢查會直接
   fail closed——先前文件沒有明講這是必要條件,只在個別 E2 回合的 ad hoc 指令裡出現過)。
   截圖固定產出 640×400(`logicalW/H`原生畫布 ×2,見`remake/cmd/fd2/main.go`),本工具用
   `arr[0::2, 0::2, :]`(取每個 2×2 區塊左上角像素)還原成真 320×200——這是**無損**還原,不是
   resize:因為 renderer 本來就是把每個原生像素畫成純色 2×2 區塊,沒有插值可言。diff 統計量
   (mean-abs-diff、exact-pixel-match %、raw RGB MD5)完全計算在這兩份真 320×200 陣列上。

**已知踩坑,寫給下一輪**:
- **`wsl.exe`本身會偶發回傳非零 exit code,即使遠端指令本身邏輯上一定成功**(例如
  `pkill ...; true`這種保證 exit 0 的指令,`wsl.exe`wrapper 偶爾還是回 9)。本工具的
  `wsl_run()`預設`check=False`,靠 stdout 內容或後續主動 probe(如`ensure_remake_xvfb`用
  `xdotool getdisplaygeometry`重新驗證連線)判斷成敗,不要相信 subprocess 的 returncode。
- **給 remake 截圖用的 Xvfb 不要每次呼叫都 pkill 重開**——`nohup Xvfb ... &`+立刻`kill`的
  重啟模式會偶發讓新 Xvfb bind 失敗(前一個 socket 還沒真的釋放),導致
  `fd2-linux-verify`卡在 X11 連線且沒有任何錯誤輸出。改成`ensure_remake_xvfb()`:進程內
  快取「這個 display 已確認可用」,首次呼叫才真的探測(`xdotool getdisplaygeometry`成功才算
  活著,不能只信`pgrep`——殭屍 process 仍會被`pgrep`比對到但拒絕新連線),探測失敗才
  pkill+重啟+再探測一次。
- **remake 側需要真實原版素材路徑**(見上,`FD2_ORIGINAL_*`三個環境變數),否則截圖本身不報錯
  但畫面是空白 fallback,`FD2_SHOT_TOWN_STATE`會直接 fail closed 讓你馬上發現,但如果未來換
  一個不做這層檢查的畫面種類,可能會安靜地截到不代表 native UI 的畫面——新場景務必先確認
  remake 端真的是 native compositor 在畫,不是預設 placeholder。
- `fd2-linux-verify`單次呼叫時間不穩定(觀察到 5-40+ 秒都有,可能跟 WSL2 磁碟 I/O 或 asset
  首次載入有關),`remake_shot()`預設 timeout 75 秒;`town`子指令對每個 pulse 值的呼叫個別
  try/except,單一 pulse 逾時不會讓整份 report 失敗,只會在輸出裡標記該 pulse 被跳過。

**驗證(2026-08-26,非紙上談兵)**:
1. **對已閉合的 UI-01 title-screen oracle 重放,取得逐位元組相同的結果**:用本工具的
   `raw-screenshot`對(全新 WSL2-native 環境、跳過開場動畫後)標題畫面截圖,`rgb_md5`與
   `docs/figures/title-original-dosbox.png`(2026-07-25 用已移除的 Docker pipeline 產生)
   **完全相同**(`d05b5e19806e5dc3d3e78d199eb74168`)——證明這個 WSL2-native 替代方案在
   byte-exact 這個維度上跟舊 Docker pipeline **等價**,不是「看起來差不多」而是逐位元組雜湊
   相同。
2. **端到端自動化重跑 ch02 城鎮 hub selection0(UI-08-TOWN-VARIANT0 同一個場景)**:`town`
   子指令全自動完成 chapter-jump patch(slot0 章節 byte→`0x01`)→啟動 instance→Escape
   跳開場→Title→Down→Enter選LOAD→Enter選唯一存檔位(確認畫面文字為「第 二 章 羅德鎮」)→
   輪詢 320×200 原生解析度出現→截圖,全程不需要人工介入或猜測 sleep 時長(用視窗幾何輪詢取代
   固定延遲)。與 remake 側(`FD2_CAMP_NODE=town_ch02`、`FD2_SHOT_TOWN_STATE=0,<pulse>`)四個
   候選 pulse 值逐一 diff,背景/帳篷造型顏色/柵欄/樹叢/「酒店」label 等絕大部分畫面達到
   **99.3-99.4% exact-pixel-match、mean-abs-diff 0.34-0.45**(最佳 pulse 落在 2)。
3. **誠實記錄:沒有達到 100% 全幀相同,而且這次的落差是真實發現,不是本工具的精度問題**——
   diff heatmap 把差異精確定位在一塊 24×24px、369 個像素的小區域(角色胸口),裁圖比對後
   確認是 remake 端在該場景多畫了一個 DOSBox-X 原版完全沒有的小紅色方塊(疑似某種 pulse/
   selection 標記錯位),四個 pulse 候選值沒有一個能讓這塊區域消失。**這不是本工具的 bug**——
   高精度的逐像素 diff 本來就應該比先前 variant1/2 用的「crop/resize 後肉眼+統計比對」更容易
   抓到這種小範圍真實 compositor 差異;舊方法的統計數字(exact-pixel 35-51%)雜訊太大,反而
   蓋掉了這種小範圍精確定位。已建議另開一個 worklist 項目追這個新發現的小紅方塊 discrepancy
   (不在本工具的範圍內處理)。

**已知限制(誠實列出)**:
1. 本工具只自動化了「chapter-jump→LOAD→城鎮 hub」這一種 navigate 序列(`reach_town_hub()`)。
   商店/教會/整備等其他場景需要各自的 navigate 序列,跟這個專案過去每一輪 E2 都需要各自的
   按鍵序列一樣——`raw_screenshot`/`remake_shot`/`diff_frames`這些底層原語是通用的,但「怎麼
   走到某個畫面」永遠是場景專屬的,不冒稱能自動走到任意畫面。
2. remake 端的 pulse/tick 是`FD2_SHOT_TOWN_STATE`這個 screenshot-only 的**強制覆寫**鉤子,
   不是模擬真實經過的時間;DOSBox-X 端擷取到的是某個真實時刻的動畫相位,兩者只能靠窮舉幾個
   候選 pulse 值來對齊,不保證每個新場景都能找到 100% 吻合的候選(如上,這次就沒找到)。
3. 尚未針對其他既有 E2 場景(商店、教會、整備、戰鬥)逐一重放驗證,只驗證了 title 與 ch02 城鎮
   hub 兩個場景;下一輪若要用這個工具升級其他 variant1/2 等級的證據,應該先重複這裡的流程。

完整 shell 腳本細節見 `tools/dosbox_diff_harness.sh` 檔頭註解;完整 CLI 用法/guarantee 邊界見
`tools/dosbox_diff_harness.py` 模組 docstring。`docs/knowledge-base/48-dosbox-x-debugger-
build.md`§11 有一個指向本節的簡短入口。

### 2026-08-26 續:town-hub badge 修復後的兩個 follow-up gap(接 task_4845f230)

`49b16f6e`(town-hub selector icon 修好、`native_town_scene.go` 改用`leaderKey`解析
`MapSelectorKey`)的 commit message 誠實記錄了一個未收尾的缺口:當時用本工具的
`town`/`remake-shot`路徑重放城鎮 hub 場景,remake 側只給了`FD2_CAMP_NODE`卻沒給
party binding,新加的 fail-closed 檢查(正確地)拒絕產出畫面,導致那輪修復完全沒有
live 重放證據。同時獨立發現 DOSBox-X 端本身重跑會給出不同結果。本節記錄兩者都已處理。

**缺口一:remake 側 party binding——已解**。`remake/cmd/fd2/main.go:8984`的
`FD2_SHOT_PARTY_BINDING`環境變數(讀取一份`remake/assets/cutscenes/bindings/*.json`
handler binding、透過`materializeShotPartyFromBinding()`重建`g.partyJoinOrder`/
`g.partyRoster`)才是正確的機制——這不是新發現,`docs/knowledge-base/58-remake-live-
verification-log.md`續轮(2026-08-16)的`town_ch03`/`shop_ch02_item`等節點早就手動用過
(`FD2_SHOT_PARTY_BINDING=ch01_pre.json`),只是先前沒有被接進`dosbox_diff_harness.py`
本身。已修:
- 新增`default_party_binding_for_chapter(chapter_byte)`——把 slot0 章節 byte 對應到
  `ch{chapter_byte:02d}_pre.json`(驗證依據:`ch01_pre.json`的`loadch.chapter`欄位確實是
  1、`party_order=[0,9,4,30,1]`,與 doc58 續五十九手動用過的組合完全一致;目前僅
  `ch00`/`ch01`/`ch02_pre.json`三份 binding 真的帶`party_order`,其餘章節的`_pre.json`
  尚未補上這段資料,呼叫時 remake 側會用清楚的錯誤訊息說「no complete party LOADCH
  state」,不是靜默錯誤)。
- `remake_shot()`新增`party_binding`參數,設定時自動加上
  `export FD2_SHOT_PARTY_BINDING=...`;`town`子指令預設自動代入,`remake-shot`子指令
  開放`--party-binding`手動指定(給 town/shop/church 以外、章節推導規則不適用的場景用)。
- **live 驗證(2026-08-26,全新 instance,非紙上談兵)**:未修前重放`town_ch02`/
  `selection0`,remake 側因為沒有 leaderKey 直接產出全黑/無效畫面,diff 統計爛到
  `exact_pixel_pct≈2.7%`(比對到錯誤畫面,不是失敗)。修完後同一場景重放,remake 側
  正確畫出城鎮 hub(帳篷、柵欄、「酒店」選單、正確的隊伍縮圖清單),與 DOSBox-X 側
  對齊後達到`exact_pixel_pct=99.36-99.43%`(4個候選pulse值),與本文件上一節
  2026-08-26首次驗證記錄的 99.3-99.4% 同一量級——證實這不只是「有畫面就好」,是真的
  重新達到先前已記錄的 rigor 等級。側圖見
  `docs/knowledge-base/evidence/town_ch02_sel0_badgefix_diffharness_20260826.png`,
  角色頭部無紅色斑塊,與`49b16f6e`修復的視覺結論一致(該 commit 自己的證據是靜態合成
  的 FDICON 比對,這是本輪補上的第一份**動態 E2 live 重放**證據)。

**缺口二:DOSBox-X 端本身重跑不穩定——已定位根因、已驗證一個範圍內的緩解,誠實列出限制**。

*重現*:對同一份已 chapter-jump patch 過的`FD2.SAV`,連續啟動 5 個全新獨立 instance、
各自走`reach_town_hub()`→`raw_screenshot()`,4 次拿到相同`rgb_md5`,1 次不同——確認這是
DOSBox-X 擷取端本身的變異,與 remake/Go 端改動無關(本輪測試時 Go 端程式碼本身沒有變動)。

*根因*:比對那 1 次離群結果與其餘 4 次,只有 362/64000 像素(0.57%)不同,且全部集中在
一塊 24×24px 的小範圍內,精確對應**隊伍隊長的站立 sprite**——放大比對後確認是同一個
角色、同一個姿勢,只是待機呼吸/晃動循環裡的**下一幀**(不是殘破/半繪製的截圖,也不是
截到完全不同的畫面)。這個工具鏈裡沒有任何機制釘住「畫面截圖那一刻,待機動畫剛好走到
第幾幀」——`wait_for_native_geometry()`的輪詢與`reach_town_hub()`裡的固定 sleep 只保證
「城鎮 hub 大致已經顯示」,不保證是哪一幀。

*緩解(已驗證有效,範圍有限)*:新增`lock_pulse_phase()`——重用既有的`wait-pixel`原語
(`dosbox_diff_harness.sh`本來就有的子指令,先前只在文件裡提過、沒有被`.py`呼叫過),
對城鎮 hub 場景鎖定一個**已知會在不同待機幀之間翻轉**的像素座標/顏色組合(本輪對
`town_ch02`/`selection0`實測找到`(x=40,y=57)=(142,0,0)`,是隊長紅領巾的一小塊像素),
截圖前先輪詢等它出現。`reach_town_hub()`新增`pulse_lock`參數,`town`子指令透過
`KNOWN_PULSE_LOCKS`表(目前只有`("town_ch02", 0)`一筆)預設自動套用(`--no-pulse-lock`
可關閉)。**效果實測**:同樣連續 5 個全新獨立 instance,加鎖後**5/5 次`rgb_md5`完全相同**
(先前未加鎖是 4/5)。

*誠實列出限制*:
1. 這是**逐場景**的緩解,不是通用解——`(x,y,rgb)`這組數字是針對`town_ch02`/`selection0`
   這個具體畫面挑出來的,換一個節點/角色隊長/城鎮美術,大機率需要重新用同一手法(比對
   兩次離群結果、找一個會翻轉的像素)重新挑一組,`KNOWN_PULSE_LOCKS`目前只有這一筆。
   沒有登記的場景組合會自動 fall back 回未加鎖行為,可能重現同一類(但通常很小、侷限在
   角色 sprite 範圍內的)變異。
2. 鎖定的是「這個像素落在其中一種已觀察到的幀」,不是證明窮舉了所有可能幀——如果待機
   循環實際有 3 幀以上,這個方法只保證鎖定其中鎖定目標對應的那一幀,不保證是「原版真正
   同步的那一幀」(反正 DOSBox-X 本身跑的是即時模擬,「哪一幀算正確」這個問題本來就沒有
   單一標準答案,鎖定的意義是讓**同一份 harness 重複呼叫時可重現**,不是宣稱找到了原版
   權威時刻)。
3. 這與續五十四/續五十五記錄的 Enter/Space 選擇性掉鍵問題是**完全不同類別**的不穩定——
   那個是輸入傳遞層(未解),這個是擷取時機對到即時動畫相位(已定位、已驗證緩解),兩者
   不要混為一談。
4. `lock_pulse_phase()`本身有成本(預設`max_tries=60`、`delay=0.15s`,最長多等9秒)且
   仰賴`import -window root`(全螢幕截圖再挑像素,不是`raw-screenshot`的
   `-window $win`),與`raw_screenshot()`本身的擷取路徑是兩條獨立的 X11 呼叫——本輪未
   發現兩者互相干擾的證據,但沒有專門測試這條路徑本身的穩定性上限(例如`wait-pixel`
   本身會不會偶爾也卡住)。

兩處修復都已寫進`tools/dosbox_diff_harness.py`模組 docstring(`WHAT THIS TOOL ACTUALLY
GUARANTEES`/`WHAT THIS TOOL DOES NOT GUARANTEE`兩節)與相關函式的 docstring
(`default_party_binding_for_chapter`/`lock_pulse_phase`/`reach_town_hub`),含完整驗證
數字,不只在本文件重複一次。

## 全章節結構性掃描(`tools/fd2_chapter_sweep.py`,2026-08-27)

**目標**:`docs/knowledge-base/91-worklist.md` M5 的「正常玩法可達性驗證」項目(30 章
全破關鏈需要人類完整遊玩才能判斷)一直是`[ ]`完全未動工。這支工具把「每章的戰鬥/劇情
內容是否存在且能在引擎層面正常運作(不崩潰/不卡死/能轉場)」這件事包成可重複呼叫、
逐章跑、失敗不中斷整批的自動化掃描,把「有沒有人整套玩過」從「需要人類手動玩 30 章」
降級成「機器結構性掃過,異常交給人類複查」。

**架構**(Windows 端 python,呼叫模式與`tools/dosbox_diff_harness.py`一致——`wsl_run()`/
`sh()`/`to_wsl_path()`同一套 subprocess 包裝,呼叫的是`tools/dosbox_harness.sh`而非
diff harness 的姊妹腳本,因為這支工具不需要 byte-exact 320×200 擷取,只需要能看、能送鍵、
能進 debugger 讀寫記憶體):

1. `prepare_chapter_save()`——複製一份真實 FD2.SAV,用既有`tools/fd2save.py`的
   `set_slot_chapter()`把 slot0 章節 byte patch 成目標章節,並用`estimate_roster_size()`
   (數`docs/data/chapter_beats/ch{01..N-1}_post.json`裡`op=="join"`的 beat 累積數,
   跟前一輪人工推導 ch11-22/23-29 名冊成長規模用的方法完全同源)決定要不要用既有
   `append_roster_members()`補足合成隊員,`--no-roster-pad`可關閉(驗證已知存檔如
   ch27 時應該關閉,見下)。
2. 開一個獨立`dosbox_harness.sh` instance,把 patch 過的存檔複寫進其 workdir 的
   FD2.SAV(遊戲只在玩家真的選 LOAD 那一刻才讀檔,啟動後任何時間覆寫都安全)。
3. Escape 跳過開場動畫、Down+Enter 選 LOAD、Enter 選存檔位。
4. **戰鬥偵測是讀記憶體,不是看畫面**——讀`DAT_00053a45`(戰鬥單位陣列基底指標,已驗證
   即時線性位址`0x1EFA45`,selector`0178`,見`docs/knowledge-base/58-remake-live-
   verification-log.md`多輪`native+0x19C000=live`delta 推導與交叉確認)的值,落在合理
   heap 位址範圍內視為「目前在戰鬥中」,否則視為「劇情/城鎮/其他節點」。這是工程層面的
   結構性訊號,不是像素判讀,符合本任務「檢查引擎層結構完整性,不是模擬人類判斷畫面」的
   定位。
5. **戰鬥中**:掃描`0x50`-byte stride 的 unit record 陣列(逐格讀`+6`camp byte,
   2=我方/0=敵方,續六十二/續六十三已證實),對每個敵方 slot 寫入死亡 signature
   (`+5=0x01`,**不是**我方的`Acted`旗標值`0x80`,兩者刻意分開,不會誤寫我方 record),
   接著送出續六十二證實過的 End-Turn→YES 捷徑(`Enter`開指令環→`Down`選 END→`Enter`
   確認→`Enter`確認「結束本回合？」)。
6. **非戰鬥**:落回一個通用、無章節專屬知識的`advance_generic()`bounded 迴圈(單發
   Enter/Escape/方向鍵輪替,每步截圖+做戰鬥指標檢查,偵測連續同雜湊畫面視為 stall)。
   `KNOWN_NAVIGATE_HINTS`允許對個別章節掛一段已知按鍵提示(目前只有 ch27,來自續五十七/
   五十八/六十二記錄的兩種變體嘗試),但**這是本工具驗證過程中最弱的一環**,見下。
7. **主要 verdict 訊號是讀回存檔,不是猜畫面**:全程跑完後把 harness workdir 的
   FD2.SAV 複製回來、解碼、比對 slot0 章節 byte 是否比 patch 進去的值更高——原生 autosave
   把章節 byte 往前推,是這個專案從續二十三/二十四起一路採信的「乾淨轉場」ground truth,
   遠比嘗試辨識未知章節的轉場畫面可靠。
8. 不論成功與否都會截圖存證、把每章的完整過程 log 寫入`result.json`、並且**保證呼叫自己
   instance 的`teardown`**(`try/finally`包住整段核心邏輯,單章丟例外不會讓實例卡著或讓
   整批中斷)。

**2026-08-27 Phase 1 驗證(ch27/ch02,誠實記錄,包含一個未解的已知限制)**:

- **基礎設施面(harness 層)驗證乾淨**:對 ch27 連續跑了 3 輪(含 2 輪調整導航策略後重測)
  +獨立手動 probe 2 輪,ch02 跑 1 輪,共 5 次 launch/teardown 循環,每次`ps aux`/
  `tmux -L fd2harness ls`/`tmux ls`(default socket)都確認乾淨——沒有殘留 dosbox-x、
  Xvfb、或 tmux server,doc48 §8.4 canonical `dbg` session(本輪未使用但同時檢查)全程
  未被碰過。全程沒有任何一次腳本崩潰或未捕捉例外,每次都正確落到`result.json`並清楚寫出
  verdict/detail/log。
- **戰鬥偵測機制的「陰性」訊號驗證正確**:ch02(真的沒有戰鬥可觸發)與 ch27 的多次嘗試裡,
  `read_battle_array_base()`全程正確回報「不在戰鬥中」,從未在真正的城鎮/營帳畫面上誤判
  成戰鬥——這是這個機制在真實資料上的第一次正面驗證(先前只在文件記錄的位址推導上驗證過)。
- **章節跳轉與 roster 估算邏輯驗證正確**:`prepare_chapter_save()`對 ch02(估算 2 人,
  源存檔已有 13 人,不補)與 ch27(`--no-roster-pad`關閉時估算 23 人,`--no-roster-pad`
  開啟時保留源存檔的 13 人)都產生預期的行為;round-trip 自檢(`fd2save.decode`)全程通過。
  這裡有一個本工具自己發現、值得記住的細節:機器上唯一的真實存檔(md5
  `e6d9a35756cddfc2519969b10f039181`)slot0 本來就已經是 ch27 raw chapter byte
  (`0x1a`),所以對 ch27 的驗證其實是拿續五十七到續六十三**同一份、位元組不變**的存檔在測,
  不是另一份「看起來像」的存檔——這讓 ch27 的驗證比預期更貼近既有 live 紀錄的基準線。
- **誠實的未解限制:通用 advance_generic 導航無法在本輪的步數/嘗試預算內走到 ch27 的戰場**。
  ch27 這次連續 3 輪(含 1 輪改良版本、1 輪掛 ch27 專屬`KNOWN_NAVIGATE_HINTS`)+2 輪
  獨立手動互動式 probe(共約 30+ 次即時方向鍵嘗試,含系統性嘗試四個角落與圍籬沿線)都停在
  post-load 的「可行走營帳地圖」節點,從未觸發doc58續五十九描述的「圍籬缺口→出口→YES」
  轉場。**這不是本工具獨有的缺陷**——doc58 續五十七到續六十三記錄了這個專案自己過去要
  解出 ch27 這一個章節的可靠 reach 序列,花了跨越多輪、由人類即時操作+反覆試錯才成功
  (且續五十九明確記載同一套存檔在不同 session 呈現過至少兩種不同 UI 型態:icon 選單 vs.
  可行走地圖,沒有已知的判別方式能事先預測會拿到哪一種)。本工具忠實反映了這個已知的
  專案級開放問題,而不是掩蓋或假裝解決——`verdict=needs_manual_followup`是正確、誠實的
  輸出,不是一個 false pass。
- **有意義的旁證發現**:ch02 與 ch27 的 post-load 營帳地圖畫面(截圖)**逐像素肉眼比對
  完全相同**(同一套帳篷佈局、同一組 4 個商店熱點:酒店/道具店/武器店/教會),證實這是
  全遊戲共用的通用「營帳」場景樣板,不是各章節各自的美術——這代表**解開任一章節的「走到
  圍籬缺口」座標,理論上能立刻套用到所有使用同一樣板的其他章節**,是下一輪如果要優先攻堅
  導航問題時最值得投資的單點(本輪已用完合理的即時互動式試錯預算,留給下一輪用更有系統的
  方法,例如反組譯地圖 collision/exit-trigger 表,而不是繼續盲目試方向鍵)。

**戰鬥處理核心邏輯的驗證方式**:由於上述導航限制,無法在本輪端到端觸發一次真正的戰鬥掃描/
mass-kill/End-Turn 呼叫鏈並觀察其效果。這部分改用**靜態核對**驗證——`BATTLE_ARRAY_PTR_LIVE`
(`0x1EFA45`)、`UNIT_STRIDE`(`0x50`)、`UNIT_CAMP_OFFSET`(`+6`)、`UNIT_ACTED_OFFSET`
(`+5`)、死亡 signature 值(`0x01`,與我方`Acted`旗標`0x80`刻意分開)、End-Turn 按鍵序列
(`Enter→Down→Enter→Enter`)全部逐一比對`docs/knowledge-base/58-remake-live-verification-
log.md`續六十二/續六十三的原始記錄,確認是逐字抄錄既有已用真實勝利驗證過的數值,不是重新
猜測——但**這個核對本身不是新的 live 證據**,下一輪一旦解出通用/ch27 專屬的可靠 reach 序列,
應該優先重跑一次端到端驗證取得真正的 live 交叉核對,而不是繼續信賴這次的靜態核對。

**已知限制(誠實列出)**:
1. `advance_generic()`與`KNOWN_NAVIGATE_HINTS`對絕大多數(28/30)章節完全沒有專屬知識,
   預期會大量產生`needs_manual_followup`,而不是`pass`——這忠實反映「這個專案自己都還沒
   解出可靠通用 reach 序列」的現況,見上。
2. 戰鬥偵測與死亡 signature/enemy scan 只在 ch27 一個章節被 live 驗證過(續六十二/
   六十三),本工具假設同一份`DAT_00053a45`陣列與`+5`/`+6` layout 對所有章節的戰鬥通用,
   這個假設**尚未跨章節交叉驗證**——如果某章戰鬥用不同陣列/layout,最壞情況是
   `scan_enemy_slots`回傳 0 筆(因為讀到的 camp byte 不符合預期的`2`/`0`兩值),會誠實
   標成 anomaly,不會靜默寫壞不相關的記憶體(寫入動作只作用在自己讀到`camp==0`的位址)。
3. 合成 roster 補位(`append_roster_members`)不跑 Go 端的裝備 recalc 尾段(見
   `tools/fd2save.py`模組 docstring),補位單位的裝備戰鬥數值不準確;本輪只在離線邏輯
   測試過,未在真正補位過的存檔上做過 live 驗證。
4. 主要 pass 訊號(章節 byte 是否前進)依賴原生 autosave 在本工具的執行時間窗口內真的落地
   ——如果某章節的 autosave 在結局 montage 播完才寫入(續六十二記錄過montage可以很長),
   本工具目前的截止時間可能在 autosave 之前就結束,產生「戰鬥其實打贏了但章節 byte 沒動」
   的`anomaly`而非`pass`,這是已知、故意保守(寧可誤判 anomaly 也不要誤判 pass)的行為。

用法、CLI 參數、完整 docstring 見`tools/fd2_chapter_sweep.py`檔頭;Phase 2 掃描結果見
`docs/knowledge-base/99-chapter-sweep-results.md`。

**Phase 2(2026-08-27):30/30 章節全數掃過,單一背景 process 循序跑完,~63 分鐘,零崩潰
/零掛起/收尾三方(`ps aux`/兩個 tmux socket)全部乾淨**。30 章 verdict 全部是
`needs_manual_followup`(如預期,見上面 Phase 1 的誠實限制),但掃描本身帶出兩個有具體
後續行動價值的新發現:①用 post-load 截圖分類,**22 章落在共用的「營帳」樣板場景、6 章
(ch23/24/25/28/29/30)完全跳過營帳直接落在正式的「出戰人數選人」畫面,零例外精確吻合
`docs/knowledge-base/25-battle-event-system.md` §9.1 先前僅用靜態反組譯推導、標記「尚待
驗證」的「raw chapter 22/23/24/27/28/29 是整備限定流程」結構性主張**,是這個推論的第一次
live 交叉驗證;②`hashlib.md5`去重確認**唯一**提前 stall(全黑畫面卡住)的是 ch01,可歸因
於本工具唯一可用的真實存檔(晚期 13 人 roster)反向 patch 回最初章節產生的「早章節+晚期
滿編隊伍」未定義組合,不代表 ch01 本身有結構缺陷。完整章節分類表、方法論、下一輪建議見
doc99。

## remake 側(`fd2-linux-verify`,Ebiten/GLFW)在無 WM 的 Xvfb 下的 xdotool 合成鍵盤輸入可靠性(2026-08-31)

**背景/矛盾**:`docs/knowledge-base/58-remake-live-verification-log.md` 同一天出現兩個互相矛盾的
結論。續八十一用`xdotool key --window <winid> <key>`對`fd2-linux-verify`(Ebiten/GLFW,無 WM 的
Xvfb `:897`)完整跑完 F5/F9 快速存讀檔互動 session,證實輸入確實送達。續八十五(church3 remake側
class-change pixel-parity 嘗試)用**看起來相同**的手法(`xdotool key --window <winid> <key>`,同樣
無 WM 的 Xvfb `:898`)卻回報「這個 remake 視窗完全沒收到任何合成鍵盤事件」,連`keydown`+`keyup`、
`mousemove`+`click`、`windowactivate`/`windowfocus`都全部失敗,並把根因推測為「GLFW 需要真正的
X11 input focus 而非單純 XSendEvent」。本節目的是實際重現、而非只是理論推敲兩者的差異。

**方法**:全新、獨立、與本專案其他任何 canonical/harness instance(`:99`/`dbg`/`diffharness`等)
不重疊的 Xvfb `:955`(`Xvfb :955 -screen 0 1400x900x24 -ac -nolisten local -listen tcp`),先用
`ensure_remake_xvfb()`同款`xdotool getdisplaygeometry`探測確認活著,再用續八十五回報失敗時**逐字
相同**的環境變數組合啟動`fd2-linux-verify`(`FD2_CAMPAIGN=assets/scenarios/campaign_full.json
FD2_MUTE=1 FD2_TITLE=0 FD2_CAMP_CLASS_FIXTURE=1 FD2_CAMP_NODE=church_ch02`+三個
`FD2_ORIGINAL_*`),用同一個binary(今日重建,HEAD與go.mod/go.sum自2026-08-01起未變動過
ebiten/glfw版本——即續八十五用的2026-08-15舊build與本輪binary在輸入處理相關的第三方函式庫層完全
相同,排除「函式庫版本差異」這個假說)。全程用`run_in_background`+同一turn內同步輪詢(不背景丟給
下一輪),`ps aux`核對啟動前後只有自己這兩個PID。

**結論一:input 確實可靠送達,續八十五「GLFW 完全不接受合成事件」的結論不成立**——用完全相同的
`xdotool key --window 0x200020 <key>`語法,在同一顆 bounded fixture 上重現出兩個真實、可截圖驗證
的雙向狀態轉換:
1. `Return`:教會主選單「有什麼事嗎?」→ raw index0 roster 畫面(悠妮 portrait+姓名),截圖
   `docs/figures/xvfb-input-probe-church-menu-entry.png`→`xvfb-input-probe-church-roster-
   select.png`,ImageMagick `compare -metric AE` 量出 392092 個像素真的改變(非雜訊/動畫)。
2. `Escape`:roster 畫面→教會主選單,但這次對白文字正確從「有什麼事嗎?」變成「還有事嗎?」
   (`docs/figures/xvfb-input-probe-church-menu-return.png`)——證明不只是「畫面變了」而是遊戲**狀態
   機真的推進**(對白文字取決於是否已進過教會選單,不是重複畫面)。
3. `keydown --window <id>`+`sleep 0.3`+`keyup --window <id>`(續八十五回報失敗的第二種手法)同樣
   可靠重現①的轉換。
4. `xdotool getwindowfocus`全程回報`2097184`(=`0x200020`,即遊戲視窗本身)——**X11 input focus
   從頭到尾就在遊戲視窗上**,不需要任何 WM、也不需要`windowactivate`/`windowfocus`(這兩個指令因
   `_NET_ACTIVE_WINDOW`不受支援而報錯是預期行為,是 doc98 續四十五已記錄的已知現象,但**這個報錯
   對後續`key --window`不構成任何副作用**——本輪直接測試:故意跑一次失敗的`windowactivate`後,
   `getwindowfocus`前後數值不變,緊接著的`Return`依然正確觸發畫面轉換)。

**結論二:找到一個會製造出「完全靜默、無錯誤訊息、任何手法都無效」這個確切症狀的操作性錯誤,是
續八十五案例最合理的解釋(誠實聲明:因無法取得續八十五當輪的原始逐行終端機記錄,以下是**目前
唯一能重現出相同症狀的假說**,不是100%對到號的鐵證)**——`xdotool key --window <winid>`送到
**錯誤的視窗 id**(例如 root window `0x21f`,或任何非目前遊戲視窗的舊/其他 id)時:
- **不會**報任何錯誤(`exit=0`,無 stderr),與送到完全不存在的 id(`0x999999`)會噴
  `X Error ... BadWindow`形成鮮明對比——這個「靜默成功但毫無效果」的訊號組合,與續八十五描述的
  「指令都正常跑完、但畫面/存檔毫無反應」完全吻合。
- 畫面**逐位元組零變化**(`md5sum`相同),與續八十五觀察到的「連無害的 F3 debug HUD 測試鍵都毫無
  畫面變化」表面上一致。

**結論三(額外發現,獨立於輸入問題本身,對下一輪嘗試 stretch goal 的人有直接參考價值)**:F3 debug
HUD 鍵在**任何非戰鬥畫面**(包含教會這整條路徑)本來就不會產生可見變化——`cmd/fd2/main.go:7319`
的`if g.debug {...ebitenutil.DebugPrintAt...}`外層包在`if g.st != nil && ...`(只有`g.st`非nil、
也就是戰鬥畫面才會畫),church 場景`g.st`必為nil。**續八十五用 F3「零變化」當作「輸入完全沒送達」
的獨立佐證,這個特定測試方法本身是偽陰性(false negative)**,F3 鍵事件即使正確送達也不會在church
畫面產生任何像素差異,不能用來證明或否證輸入是否送達。另外,本輪深入重現時發現:即使用確認可靠
送達的`Return`,`FD2_CAMP_CLASS_FIXTURE=1`這個「bounded headless oracle」(見
`cmd/fd2/main.go:9029`附近註解「Bounded headless oracle only」)在 roster 畫面選取悠妮進入
status/command panel 這一步**完全沒有反應**——連續多次、間隔拉長到 10 秒的`Return`都無效,但同一
session 內`Return`(menu→roster)、`Escape`(roster→menu)前後都正常運作,排除「輸入間歇性失效」。
對照`cmd/fd2/main.go:3672`附近`status_roster`模式的`enter && listLen > 0 && g.churchSel < listLen`
判斷式,roster 畫面本身能顯示姓名代表`listLen>=1`,理論上該分支應該觸發——**這是一個獨立於輸入
tooling 的、真正卡在應用層的行為,根因未查(本輪判斷範圍外,留給下一輪)**,但代表**即使把
xdotool輸入問題完全解掉,續八十五當時用的這個特定 bounded fixture 路線也走不到 class-change
status/command panel 深層畫面**——要重跑那個 pixel-parity stretch goal,建議改用續八十五三個
church服務其中已成功的「真實存檔+正常 title→LOAD→church 互動路徑」(而非
`FD2_CAMP_CLASS_FIXTURE`捷徑),見下方「可靠流程」。

**可靠流程(供下一輪直接照抄)**:
```
# 1. 全新、獨立、確認未與其他 instance 衝突的 display
Xvfb :<N> -screen 0 1400x900x24 -ac -nolisten local -listen tcp &
xdotool getdisplaygeometry --display 127.0.0.1:<N>   # 確認活著才繼續

# 2. 啟動 fd2-linux-verify(cwd=remake/),1400x900 screen 對應互動模式 1280x800 視窗
#    (doc58續八十一已記錄的1024x768裁切陷阱,本輪沿用1400x900未再踩)
DISPLAY=127.0.0.1:<N> FD2_CAMPAIGN=assets/scenarios/campaign_full.json FD2_MUTE=1 \
  FD2_ORIGINAL_FDOTHER=$HOME/fd2-run/FDOTHER.DAT FD2_ORIGINAL_FDTXT=$HOME/fd2-run/FDTXT.DAT \
  FD2_ORIGINAL_DATO=$HOME/fd2-run/DATO.DAT ./fd2-linux-verify &

# 3. 每次都用 xwininfo 現查視窗 id,不要沿用/複製前一個 session 的數字
#    ——這是本輪找到的、與症狀完全吻合的唯一失效模式
DISPLAY=127.0.0.1:<N> xwininfo -root -tree   # 找 "GLFW-Application" 那個 child window id

# 4. 直接送鍵,不需要任何 WM、不需要 windowactivate/windowfocus(會報錯但無害、可略過)
DISPLAY=127.0.0.1:<N> xdotool key --window <該次真正查到的id> <KeyName>
DISPLAY=127.0.0.1:<N> import -window <同一個id> out.png   # 截圖驗證
```
**Caveats**:①只在這台 WSL2 Ubuntu、這個 ebiten/glfw 版本上驗證過,未測試過有 WM 或原生 X.Org 的
情境;②F3 debug HUD 測試鍵不能當作「輸入是否送達」的通用探針,見結論三;③`FD2_CAMP_CLASS_FIXTURE`
捷徑本身有未查明的深層畫面卡住問題,與本節輸入結論無關,不要混為一談;④結論二的「wrong window
id」只是目前唯一可重現同症狀的假說,不是對續八十五當輪逐指令的鐵證確認。

### 續一(2026-08-31)：③的「深層畫面卡住問題」已用純程式碼閱讀+既有測試證據解開，不是 bug，是動畫幀節流

**結論**：`FD2_CAMP_CLASS_FIXTURE` 卡在教會 roster-select 這步，根因是 church UI 的開闔轉場**刻意**
要求每一幀先被真的 `Draw()` 過一次(`job.drawn=true`)才會前進到下一幀——`inpututil` 按鍵在
`nativeChurchUIBlocksInput()`(`native_church_ui.go:161`,`return g.nativeChurchUIJob != nil`)/
`nativeClassUIBlocksInput()`(`native_class_ui_lifecycle.go:194`,同款)回傳 true 的整段期間會被
`main.go:3592`直接吞掉，回傳`return true`但不做任何狀態轉換。這個「未真正 Draw 過的幀不會前進」
行為本身**已有既有回歸測試鎖住**——`native_church_ui_test.go`的
`TestNativeChurchUILifecycleCannotSkipUndrawnFrame`：連續呼叫兩次`stepNativeChurchUILifecycle`
但都不先設`job.drawn=true`，斷言`job.frame`必須維持 0，不能前進。

**卡住的完整幀數**：選教會選單case0(狀態/service0)這一步，實際要跑完兩段各自獨立節流的動畫才會
真正進入`status_roster`模式並開始接受 Enter：`beginNativeChurchMenuClosing`(選單收合，
`nativeChurchUIJob`，4幀)接著`beginNativeChurchRosterOpening`(名冊展開，改用**另一個**
`nativeClassUIJob`，6幀)——合計10幀，每一幀都要求先有一次真正的`Draw()`呼叫才會前進。在真實
DOSBox-X/`fd2-linux-verify`互動session(續八十一/church3等輪)裡，這件事在正常60fps遊戲迴圈下
是自動、瞬間完成的(遠低於人類按鍵間隔)，從未被注意到是個「步驟」；但`FD2_CAMP_CLASS_FIXTURE`
這類**bounded 一次性截圖工具**若在兩次按鍵之間沒有讓真實 Ebiten 主迴圈跑滿至少10幀(或用等效的
screenshot-confirm節奏)，第二次(選悠妮的)Enter就會被前一段動畫還沒收尾的`nativeChurchUIJob`/
`nativeClassUIJob`原封不動吞掉，症狀正是續八十五記錄的「卡在roster-select這步」。

**這不是程式碼缺陷，不需要修**——跟 doc48 §8.4 反覆強調的「送鍵早於片頭動畫，要靠screenshot確認
才送下一鍵」是同一類方法論教訓，只是這次的節流對象是 remake 自己的 indexed UI 轉場，不是 DOSBox-X
的片頭動畫。**下一輪若要用`FD2_CAMP_CLASS_FIXTURE`類bounded工具重跑這條路徑**：兩次按鍵之間至少
留出足以讓主迴圈跑滿10幀的真實wall-clock等待(60fps下理論值~167ms，Xvfb/WSL2下留更寬裕的
300-500ms較保守)，或比照今天`church3`/續八十一輪的做法改用單發按鍵+screenshot確認再送下一鍵，
不要批次/連續送鍵。

## `tools/fd2_live_input_helper.{py,sh}` — M5 Phase 4 正常玩法機械化輔助工具(2026-09-01)

**目的/範圍**：把上面兩節(以及`92-m5-normal-playthrough-log.md`)記錄的三個每輪都要重新解一次的
機械問題——現查視窗id、節流動畫的wait/confirm、螢幕鄰格≠邏輯鄰格——包成可重複呼叫的原語，**刻意
不做任何戰術判斷**(不選目標、不規劃移動、不決定攻擊時機)，純粹讓「如何可靠執行一個已決定好的動作」
變便宜。細節與逐項對應doc92/doc98段落的說明見`fd2_live_input_helper.py`模組docstring本身,這裡只記錄
建置過程中新發現、且會讓下一輪重蹈覆轍的兩個環境級陷阱。

**用法**：`python tools/fd2_live_input_helper.py launch --instance <name>`(全新Xvfb+
fd2-linux-verify、預設無任何`FD2_SHOT_*`/`FD2_CAMP_*`)、`window-id`/`key`(confirm/cancel別名、
`--wait`固定等待或`--settle`輪詢畫面直到連續兩張截圖相同兩種模式擇一,拒絕在兩者都沒指定時真正的
零等待送鍵)/`screenshot`/`status`/`teardown`(PID+process name驗證後才kill,絕不`pkill`)。`grid
distance`/`grid range`/`grid dump-map`三個子指令是純資料查詢+算術,不連線任何live instance,直接讀
`mapN_units.json`的`own_deploy`/`units[].atk_min/atk_max`,`range`子指令的預設規則(0視為1)逐行對應
`remake/internal/battle/move.go`的`InAttackRange`。

**陷阱一(新發現,已修正)：`wsl.exe`的`bash -c "多語句字串"`會靜默丟失語句間的shell變數狀態**——
建置過程中用Python`subprocess.run(["wsl","-d","Ubuntu","bash","-c","x=hello; echo got:$x"])`(真正
的argv list,不是shell字串,排除Windows/MSYS quoting層造成的可能性)重現:輸出`got:`(空字串),但
`declare -p x`在**同一個**`-c`字串裡確實顯示`x`已正確賦值成`"hello"`——賦值本身成功,只是後面的
「使用」丟失。改用stdin管線餵給不帶`-c`的`wsl -d Ubuntu bash`,或(本工具最終採用的作法,也是
`dosbox_harness.sh`/`dosbox_diff_harness.sh`一直以來事實上依賴、但從未明講原因的作法)把腳本寫成
真正的`.sh`檔案、用`wsl -d Ubuntu bash <script.sh> <arg1> <arg2> ...`這種單純argv呼叫,兩者都正常,
包含真正的位置參數傳遞($1/$2/...)。根因未完全查明(可以確定不是bash本身的問題——同一段腳本貼進
互動式bash session執行完全正常;推測與`wsl.exe`/interop層在bash真正看到`-c`參數前對其做的某種
重新tokenize有關),但這是`fd2_live_input_helper.py`架構決策的直接依據——所有WSL側呼叫一律走
`wsl_argv_run()`/`sh()`(真正argv list),`fd2_live_input_helper.sh`裡任何需要跨陳述式保留變數狀態
的邏輯都活在這個`.sh`檔案本身裡,絕不會被壓縮回一個Python組出來的多語句`-c`字串。**下一個要在這個
專案裡新增WSL側工具的人,請直接沿用「真.sh檔案+純argv呼叫」這個模式,不要假設`bash -c`字串可以
安全攜帶跨陳述式的變數狀態。**

**陷阱二(新發現,已修正)：`nohup cmd & disown`對`fd2-linux-verify`這個Ebiten/Go binary不夠,
`setsid`才夠**——`launch`要啟動兩個長駐背景行程(Xvfb、fd2-linux-verify),第一版兩者都用
`nohup ... & disown`(`dosbox_diff_harness.py`的`ensure_remake_xvfb()`已驗證過這個模式對Xvfb有效)。
實測(本工具自己的第一輪live smoke test)發現:Xvfb在啟動它的`wsl.exe`/bash session關閉後確實存活,
但`fd2-linux-verify`卻在session關閉後不久就消失,且自己的log裡沒有任何panic/crash trace——用一個
獨立的對照腳本(同一組nohup+&語法,同時起兩個行程,session關閉後從**另一個**全新`wsl.exe`呼叫查
`ps aux`)重現確認:Xvfb活著、fd2-linux-verify不見。換成`setsid cmd &`(讓行程開一個全新session,
徹底脫離原session,而不只是忽略SIGHUP)後,同款對照測試下fd2-linux-verify在session關閉後依然存活
(同樣用一個全新`wsl.exe`呼叫的`ps aux`確認)。根因(為什麼`nohup`對這個特定binary不夠、`Xvfb`卻夠)
未深入查——不影響修法本身,`setsid`已經是更徹底的方案,不需要先查清楚`nohup`為何不夠才能採用它。
`fd2_live_input_helper.sh`現在對Xvfb和game process都用`setsid ... & pid=$!`(`$!`在真正的`.sh`檔案
裡是可靠的,陷阱一的`-c`字串問題不適用於這裡)。**下一輪任何要在這個環境背景啟動長駐GUI/game
process的工具,請直接用`setsid`,不要只用`nohup`就假設夠了。**

**驗證方式(誠實記錄)**:1-4號原語(launch/window-id/key/screenshot)全部live驗證過,見下方截圖
序列——全新獨立instance(port :199,與另一個當時仍在跑的agent session `:980`/pid 9763完全不重疊,
teardown前後都用`ps aux`核對過對方毫髮無傷)、`launch`成功、`window-id`回報`0x200020`、
`screenshot`先拍到片頭前空白幀、`key`送5次Escape(`--wait 1.0`)後screenshot證實跳過片頭到達標題
畫面(FLAME DRAGON 2 LOGO+START/LOAD/CONTINUE)、`key confirm --settle`送出後screenshot證實正確
進入序章對白(索爾晉見父王),但`--settle`本身在這個持續有動畫/文字的畫面上如預期地TIMEOUT——這正是
`wait_for_settle()`docstring裡誠實記錄的已知取捨(持續動畫的畫面永遠不會有連續兩張完全相同的截圖),
不是bug。5號(grid distance/range/dump-map)全部單元驗證過,`dump-map`對`map0_units.json`的輸出與
`92-m5-normal-playthrough-log.md`已手算記錄的`own_deploy=[(7,20)索爾,(10,21)亞雷斯,(8,22)悠妮,
(11,23)蓋亞]`座標表逐一比對一致。teardown驗證了PID+process-name核對邏輯在「game process已提早
結束、只有Xvfb還活著」這個部分失敗場景下確實正確分流(不誤殺、不誤報)。**未做的驗證**:沒有刻意
建構「送到stale window id」的失敗案例(工具本身的設計——每次呼叫都現查——結構性排除了這個場景,
沒有辦法在不繞過工具本身邏輯的前提下人工重現);沒有實際打過一場戰鬥去驗證`grid range`的輸出與
真實UI「此指令目前不可用」訊息一致(`map0_units.json`裡的敵方單位`atk_min`/`atk_max`原始值都是
0——doc32/model.go註解已說明這是舊版units.json的已知特徵,不代表工具本身有問題,只是這個特定地圖
沒有非1的射程可供交叉驗證,下一輪若拿到`atk_min`/`atk_max`非零的地圖JSON值得補一次這個驗證)。

### 續二(2026-09-01)：`screenshot`加`--resize`降低LLM讀圖的vision token成本

**動機**:這個工具本身解決的是「輸入送達可靠性」的問題,不是「呼叫代理人讀截圖要花多少token」的
問題——`key --settle`/`wait-settle`的輪詢截圖只拿來做md5比對,從不餵給LLM,便宜;但`screenshot`
指令產出的PNG,呼叫方(agent)每次都要真的Read進vision才能判斷畫面狀態,這部分token和像素面積成
正比,是一輪即時playthrough token消耗的主要來源之一,不是工具設計缺陷,是即時視覺驗證這種做法本身
的固有成本。

**實測發現的具體浪費**:`fd2-linux-verify`的視窗大小是`defaultWindowSize()`依實際螢幕挑的640×400
邏輯畫布整數倍——這個工具固定用1400×900的Xvfb screen(`fd2_live_input_helper.sh`的`launch`),
實測跑出來的視窗是1280×800(2倍放大)。`import -window`直接存這個放大後的尺寸,對LLM來說,那多出來
的2×2→1像素完全不含額外資訊,純粹是在為「被放大的像素」多付vision token。

**修法**:`cmd_screenshot`(`.sh`)在`import`之後可選再跑一次`convert "$out" -resize "$geometry" "$out"`
(不加`!`,fit-within、保比例,不是裁切);Python側`screenshot()`/`screenshot`子指令新增`--resize`,
預設值`DEFAULT_SCREENSHOT_RESIZE = "640x400"`(遊戲自己的邏輯畫布尺寸,不是隨便選的縮放比例),
傳空字串取消縮放拿原始解析度。這是純加法,舊呼叫(不帶`--resize`)行為改變僅限於「預設值從『無縮放』
變成『縮到640×400』」,不影響任何既有選項的語意。

**驗證(獨立instance `resizecheck`,port :299,與同一時間仍在跑的M5 Phase 4正式agent session完全
隔離,teardown後清理乾淨)**:同一畫面分別存了`--resize`預設值與`--resize ""`兩張——確認
1280×800(112092 bytes)→640×400(16233 bytes),面積4倍、檔案大小約7倍差距;縮小後的640×400畫面
(片頭剪影畫面)人工檢視仍清晰可辨,因為這本來就是從整數倍(2x)放大回原生尺寸,是精確逆運算,不是
有損壓縮或裁切,不會漏看任何遊戲原生解析度就有的細節。**未做的驗證**:沒有拿實際戰鬥畫面(含指令環
文字、HP數字)在640×400下測試LLM讀圖是否仍能正確辨識細小文字——如果之後某輪發現640×400讀不清楚
戰鬥UI的文字/數字,加大`--resize`(例如`960x600`,1.5倍)或針對特定截圖呼叫`--resize ""`保留全解析
度,不要假設640×400在所有畫面類型下都夠用。

### 續三(2026-09-01)：`screenshot`加`--autocrop`,戰鬥畫面本身就有大片黑邊可裁

檢視`ch01run`(當時仍在跑的M5 Phase 4正式agent)已經存下的真實戰鬥截圖,連同`docs/figures/`裡
commit `e576ad87`留下的舊戰鬥截圖(1280×800全解析度那組)一起量測,發現**戰鬥/地圖畫面本身就只
畫在640×400邏輯畫布的左上角約79%寬×50%高**,其餘是純黑——兩張獨立時間點、獨立解析度拍到的畫面
這個比例幾乎一致(1016/1280=79%、392/800=49% vs 508/640=79%、199/400=50%),不是單一畫面的巧合。
但同一輪測試裡的片頭剪影畫面是滿版無黑邊——代表這個黑邊只出現在戰鬥/地圖畫面,不是每種畫面都有,
不能當成全域預設去裁。

**修法**:`cmd_screenshot`在(可選的)resize之後,再加一段可選的`convert -fuzz 3% -trim +repage`
(`-trim`本身只會裁掉「四周純色邊框」,對已經滿版的畫面是安全的no-op,不會誤裁進真實內容)。Python
側新增`--autocrop`(預設關閉,`action="store_true"`)。**刻意不預設開啟**:雖然`-trim`理論上對
無黑邊畫面是no-op,但目前只驗證過戰鬥畫面這一種情境,還沒有把選單/商店/對話等每種畫面都實際截圖
驗證過,遵循這個專案一貫的「沒驗證過的視覺假設不能當預設」紀律,先做成需要呼叫方自己判斷、主動加
這個旗標的選用功能。

**驗證(用`ch01run`已經存的真實戰鬥截圖複製出一份測試,沒有動到agent自己在用的原始檔)**:
`convert -fuzz 3% -trim +repage`把640×400裁到508×198,與人工掃描黑邊邊界算出的(508,199)幾乎完全
吻合;人工檢視裁完的圖,地圖、單位、HP面板、底部戰鬥訊息文字全部完整保留,沒有任何真實內容被誤裁。
`--resize`+`--autocrop`兩者疊加,戰鬥畫面的像素面積從原始1280×800降到508×198,約是原始的1/10,
對應vision token大概也是同等級的降幅。

### 續四(2026-09-01)：改正設計缺陷——`--resize`/`--autocrop`原本是就地覆寫原圖,原始檔案因此消失

**問題(使用者發現)**:續二/續三的第一版實作是`convert "$out" ... "$out"`,直接把resize/autocrop的
結果寫回同一個檔案——代表`screenshot`指令一存檔,原始未處理的截圖就已經被覆蓋消失,沒有留下任何
可以回頭核對的原圖。這在平時看縮圖沒事,但萬一以後某種畫面類型的autocrop誤裁(續三已明講只驗證過
戰鬥畫面,選單/商店/對話都還沒測),就完全沒有原圖可以拿來對照、判斷是裁切邏輯錯還是畫面本身就長
那樣。

**修法**:`cmd_screenshot`(`.sh`)簽名改成`<name> <out_path> [resize] [autocrop] [view_out_path]`——
`import -window`永遠只寫到`out_path`,寫完立刻`echo`回報,之後**不再對`out_path`做任何修改**。若
`resize`或`autocrop`任一個有值,才把`out_path`複製到呼叫方指定的`view_out_path`,resize/trim只動這
份複本。Python側`screenshot()`回傳值改成`ScreenshotResult(raw, view)`具名tuple——`raw`永遠存在,
`view`只有在確實做了resize/autocrop時才非`None`(自動命名規則:`<out_path去掉副檔名>_view<副檔名>`,
或呼叫方自己用`--view-out`指定)。`cmd_screenshot`(CLI)輸出改成兩行`raw: <path>`/`view: <path>`
(後者沒有就不印)。

**驗證(獨立instance `rawviewcheck`,port :199,測完teardown乾淨)**:預設參數(`--resize`
640x400、`--autocrop`關)下,`raw`確實停在1280×800原始解析度、`view`是縮小後的640×400,兩個檔案
互不影響;另外測了`--resize ""`(resize跟autocrop都關)的情況,確認完全不會產生`_view`檔——沒有
要求任何處理時,不會憑空多存一份沒用的複本。

## `tools/fd2_dosbox_live_helper.{py,sh}` — 包裝`dosbox_harness.sh`的DOSBox-X即時操作便利工具(2026-09-02)

**目的/範圍**：`tools/fd2_live_input_helper.{py,sh}`(上面兩節)是remake側(`fd2-linux-verify`)的
機械化輔助工具,這個工具是它在DOSBox-X側的對應物——包裝既有的`tools/dosbox_harness.sh`(N-way平行
dosbox-x heavy-debugger harness,見本檔案「N-way 平行 dosbox-x live-verification harness」一節),
**不重建**它的launch/teardown/registry核心邏輯,只加上這個session實際做live驗證工作時發現缺少的
四項便利/修法:screenshot resize/裁切、settle-confirmed送鍵、一鍵化的live memory read、canonical
檔案完整性檢查。架構上延續`fd2_live_input_helper.py/.sh`已經寫入本檔案的「兩檔案分工+真.sh檔案+純
argv呼叫,絕不用Python組出的多語句`bash -c`字串」設計——這裡不重複那段論證,只記錄這次新發現的坑。

**用法**：
```
python tools/fd2_dosbox_live_helper.py launch --instance myrun --keepalive 3600   # 長駐前景呼叫,自己背景化
python tools/fd2_dosbox_live_helper.py status / teardown --instance myrun / teardown-all
python tools/fd2_dosbox_live_helper.py key --instance myrun Escape --wait 0.5
python tools/fd2_dosbox_live_helper.py key --instance myrun Return --settle
python tools/fd2_dosbox_live_helper.py screenshot --instance myrun --label title --autocrop --resize 320x260
python tools/fd2_dosbox_live_helper.py enter-debugger --instance myrun
python tools/fd2_dosbox_live_helper.py debugger-status --instance myrun
python tools/fd2_dosbox_live_helper.py mem dump --instance myrun --selector 0170 --linear 1ADD73 --bytecount 20
python tools/fd2_dosbox_live_helper.py mem read-unit-record --instance myrun --selector 0170 --linear 26DF88
python tools/fd2_dosbox_live_helper.py verify-canonical [--path <windows或wsl路徑>]
```

### 發現一：`dosbox_harness.sh`的screenshot是`import -window root`,不是`import -window <dosbox-x視窗id>`

這是這次任務brief原本假設「DOSBox-X視窗本身就等於模擬視訊模式的原生解析度、可能沒有letterbox可裁」
(依據本檔案「DOSBox-vs-remake byte-exact pixel diff harness」一節的既有發現)的一個重要修正：那個
既有發現是對的沒錯——**遊戲畫面內容本身**確實沒有letterbox(下面續一的3種畫面型態實測都印證這點)——
但`dosbox_harness.sh`的`screenshot`子指令用`import -window root`,抓的是**整個Xvfb虛擬螢幕**
(這個專案的launch設定是1024×768),不是只抓dosbox-x自己的視窗。原因是dosbox-x(heavy-debug build)
視窗化SDL輸出本身固定會畫一條GUI選單列(`Main CPU Video Sound DOS Drive Capture Debug Help`,約
17px高,不受`scaler`/`aspect`設定影響——這正是前述pixel-diff-harness那節的既有發現:同一組config
套用在`dosbox-x`上視窗會是640×417,套用在套件版`dosbox`上才會是精確640×400),所以真實視窗本身就
比模擬視訊模式的原生解析度多了這條選單列,而`import -window root`又比真實視窗本身還多了一圈周圍的
Xvfb桌面背景。這代表這個工具的screenshot要處理的「無用像素」跟remake側template（`fd2_live_input_
helper.sh`,裁的是遊戲自己邏輯畫布內的黑邊）**性質上是兩個不同的問題**,不能照搬同一套裁法。

**實測(2026-09-02,獨立instance `dosboxtoolcheck`,port :199,全程無其他agent同時在跑)**：
`xdotool getwindowgeometry`量到dosbox-x真實視窗是`640x417`、位置`Position: 192,184`——與
`import -window root`存出來的`1024x768`原始截圖用`convert -fuzz 3% -trim +repage`得到的裁切結果
`640x417`（crop offset`+192+184`,`identify`不加`+repage`直接印出`1024x768+192+184`）**完全吻合**,
在片頭剪影畫面(`toolcheck_boot.png`)與剛進LOAD存檔清單畫面(`toolcheck_load.png`)兩張獨立截圖上都
成立。但**同一組`-fuzz 3% -trim`在LOAD存檔清單畫面上量到的是`640x413`,不是`640x417`**——這揭露了
一個真實的邊界案例:這台環境的Xvfb桌面背景實測是純黑`#000000`(用`convert -crop 10x10+0+0 txt:-`量
過畫面左上角桌面背景與畫面內容黑色區域,兩者顏色bytes完全一致),跟遊戲畫面自己的黑色UI背景**同一個
顏色**——純粹靠`-fuzz`色彩啟發式的`-trim`,沒辦法區分「視窗外的桌面」跟「視窗內、真的是黑色但屬於
遊戲畫面自己的內容」,這次量到的差距(4px)沒有吃掉任何看得見的真實內容(存檔清單方塊、選單列文字都
完整保留,人工核對截圖確認),但這只是運氣好,原則上不能保證每種畫面都這麼幸運。

**修法**：`fd2_dosbox_live_helper.sh`的`--autocrop`改成兩步驟,不是remake template那種單一
`-fuzz`+`-trim`：**第一步永遠是精確的視窗邊界裁切**——每次都現查`xdotool getwindowgeometry`(同一套
「絕不快取視窗資訊,每次重查」紀律),用查到的`WxH+X+Y`做`convert -crop`,這是決定性的,不靠顏色猜測,
不會有上面那種吃掉真實內容的風險；**第二步**才是選用性質、疊加在第一步結果上的`-fuzz 3% -trim`,用
來額外裁掉dosbox-x自己畫的那條選單列(或任何畫面本身真的有的黑邊)——這步驟沿用remake template
「只驗證過幾種畫面型態,預設不開,呼叫方自己判斷」的紀律,不是預設一定安全。`--resize`在這個工具上
**沒有強制預設值**(remake template的640x400是遊戲自己固定的邏輯畫布尺寸,這裡沒有對應物——
DOSBox-X同一個工具混合了320×200-mode被2倍放大成640×400的畫面跟原生640×400 SVGA過場畫面,兩者共用
同一條不會跟著縮放的17px選單列,沒有單一「縮小2倍、零資訊損失」的操作對每種畫面都成立),要縮圖得
自己指定geometry。

### 續一(2026-09-02)：4種畫面型態實測,遊戲內容本身沒有letterbox的假說再次確認成立

除了上面用來抓桌面邊界的片頭剪影/LOAD清單兩張,另外實測了標題logo選單畫面(`FLAME DRAGON 2 /
LEGEND OF GOLDEN CASTLE / START LOAD CONTINUE`)、以及送出Escape+讀完存檔後意外停在的一張角色立繪
過場畫面（頭髮藍色的男性角色半身立繪，佔滿畫面）——**4種畫面型態,`--autocrop`裁完後遊戲內容都填滿
到選單列正下方的640×400,沒有一種在畫面內部另外找到黑邊**,與這次任務brief引用的既有pixel-diff-
harness發現(dosbox-x/dosbox視訊模式輸出本身沒有letterbox)一致——`--autocrop`在這個工具上主要的
價值是裁掉「視窗外的桌面」跟「選單列」這兩塊真正的無用像素,不是remake側那種「遊戲畫布內部本身有大
片黑邊可裁」的情境,這點在Python CLI/`.sh`兩邊的docstring都已經寫清楚,不假裝這是同一種裁法。

### 續二(2026-09-02)：`mem dump`/`mem read-unit-record`live驗證——dump出的bytes與debugger自己的
Code Overview反組譯逐byte吻合

`enter-debugger`進入ncurses debugger TUI後,Register Overview讀到`CS=0170 EIP=001ADD73`(保護模式,
`Pr32`),Code Overview同一畫面列出`0170:001ADD73`起的反組譯(`68 C8 03 00 00`=`push 000003C8`、
`E8 68 5D 02 00`=`call 001D3AE5`……)。用`mem dump --selector 0170 --linear 1ADD73 --bytecount 20`
(內部走`MEMDUMPBIN 0170 1ADD73 20`)dump出的32-byte原始bytes(`68 c8 03 00 00 e8 68 5d 02 00 83 c4
08 89 d8 c1 e0 02 29 d8 8b 15 65 fa 1e 00 0f b6 04 02 29 f0`)與Code Overview印出的反組譯bytes
**逐byte完全一致**——這是一個獨立於MEMDUMPBIN本身之外的交叉核對(debugger自己的反組譯視窗是另一條
完全不同的讀取路徑),不是「指令跑完沒報錯」這種弱驗證。`mem read-unit-record`(內部固定用0x32=50
bytes,對應doc58續四十驗證過的完整戰鬥unit record大小)在同一位址上機械性測試通過,正確印出hexdump
與doc58續四十記錄過的5個已知欄位(`+0x05`/`+0x06`/`+0x07`/`+0x1f`/`+0x26`)——**這個位址本身不是真實
的unit record**(這次只是站在標題選單畫面,沒有進戰鬥),印出來的欄位值沒有RE意義,這裡只驗證了工具
本身的資料通路正確,不是宣稱驗證了任何新的RE結論。selector`0`的拒絕guard也live測試過:
`mem dump --selector 0 ...`確實在送出`MEMDUMPBIN`之前就被`fd2_dosbox_live_helper.sh`擋下,印出
doc58引用的已知失敗模式說明,不會像人工誤傳一樣安靜地拿到一份看似成功、實際是垃圾資料的dump。

### 續三(2026-09-02)：`debugger-status`的已知盲點——離開debugger後,tmux pane可能還顯示舊的
「ACTIVE」內容(誠實記錄,不是解決)

`debugger-status`用`tmux capture-pane`抓文字畫面,搜尋`Code Overview`字串來判斷debugger TUI是否
正在顯示。實測(同一個`dosboxtoolcheck` instance)：第一次`enter-debugger`後`debugger-status`正確
回報`ACTIVE`；**再送一次`enter-debugger`(理論上應該離開debugger、恢復執行)後,`debugger-status`
依然回報`ACTIVE`**,而且pane裡的`EAX`/`EIP`/`cc=`數值跟離開前完全相同(凍結畫面,不是即時更新)。
用`screenshot --autocrop`交叉核對SDL視窗本身,確認遊戲**真的已經恢復執行**(畫面從標題選單前的片頭
剪影變成一張全新的角色立繪過場,不是同一張凍結畫面)——這證明debugger TUI恢復RUN之後,dosbox-x**不會
主動重繪tmux pty這個畫面**(遊戲畫面走SDL/X11視窗那條完全獨立的路徑),`capture-pane`抓到的只是「
上次debugger TUI畫過的內容還留在螢幕緩衝區裡」,不是「目前真的還在暫停」的可靠證據。這個發現已經
寫進`fd2_dosbox_live_helper.sh`的`cmd_debugger_status`本身的註解與CLI輸出文字裡(`ACTIVE`那行現在
附帶這個警語)——**這不是bug修復,是誠實記錄一個做不到的保證**：`debugger-status`只能可靠回答「這個
pane有沒有『曾經』畫過debugger TUI且之後沒有別的東西蓋過它」,回答不了「現在」是否真的還暫停在
debugger裡；需要真的確定時,交叉核對一張screenshot(暫停中的畫面不會變、恢復執行的畫面會變)比單獨
信任`debugger-status`可靠。

### 續四(2026-09-02)：`key --flag-no-response`/`wait-settle --baseline`——「按鍵疑似沒反應」提示旗標

使用者提議：既然`--settle`已經在做畫面截圖比對,能不能順便標記「送鍵前後畫面完全沒變」這件事,讓
呼叫端至少能發現異常而不是靜默當成成功。實作方式：`key --settle --flag-no-response`在送鍵**之前**
多截一張baseline截圖,`wait-settle`(`.sh`側)在settle成功後,把最終那張settled截圖的md5跟baseline
md5比對,相同就在輸出多附一段`response=NO_RESPONSE`(不同則是`response=CHANGED`),Python側解析成
`FLAG: NO_RESPONSE`印到stderr。獨立instance(`flagtest`)live測試：對著同一個當下畫面連送兩次
Escape,第一次已回報`NO_RESPONSE`(畫面本來就是靜止的過場幀,Escape沒有可見效果)；接著送Return再送
Down,兩次都正確回報`response=CHANGED`(畫面確實往前推進)——確認旗標在「真的沒變」與「真的有變」
兩種情況下都給對答案,不是恆真或恆假。

**刻意的設計邊界(如同建議時就先講清楚的)**：這仍然只是「螢幕像素沒變」這個弱信號,不是「按鍵被
遊戲邏輯吃掉/沒吃掉」的直接證明——有些按鍵在特定畫面上本來就合法地不會造成任何可見變化(例如移動
到地圖邊界後再按同方向)。因此`--flag-no-response`預設**關閉**(需要顯式加旗標,而且只有搭配
`--settle`才有意義,單獨用`--wait`模式沒有可靠的「settle後那一幀」可比對,遇到這個組合會印警告並
忽略旗標而不是報錯),多付出「送鍵前多一次截圖」的代價才啟用,不是`key`預設行為的一部分——呼叫端
拿到`NO_RESPONSE`後應該視為「值得再看一眼」,不是自動判定失敗或自動重送。

### 續五(2026-09-02)：3項新增測試功能——`debugger-status --baseline`、`status`孤兒偵測、
`fd2_dual_verify.py`

使用者要求評估還缺哪些測試功能,討論後核准3項,全部已實作並live測試通過:

**1. `debugger-status <name> [baseline]`——把續三記錄的盲點變成可主動檢查的訊號**：沿用
`--flag-no-response`同一套baseline比對手法——呼叫端在已知時刻(例如剛進debugger時)存一張截圖,
之後`debugger-status`再比對現在的畫面跟這張baseline是否相同,印出`SCREEN_CHECK: unchanged`
(與「真的還暫停」一致)或`SCREEN_CHECK: CHANGED`(與pane文字的`ACTIVE`矛盾→pane過期了,執行
其實已經恢復)。獨立instance(`dv_dosbox`)live測試3種情境:進debugger前(pane INACTIVE)vs
持續動畫中的過場畫面比對,正確印出`CHANGED`；剛進debugger後立刻比對,正確印出`unchanged`(此時
畫面確實靜止,暫停生效)；離開debugger後拿舊baseline比對,印出`unchanged`——這次沒有重現續三
記錄過的「pane過期」矛盾情境,獨立額外測試證實原因是當下遊戲片頭剛好停在靜止幀(前後4秒2次截圖
md5完全相同),不是這個新功能本身的邏輯錯誤——`unchanged`跟`CHANGED`兩種輸出在各自對應的真實
情境下都正確,只是這次沒有剛好撞上會製造矛盾的時間點。

**2. `status [stale_after_seconds]`——孤兒instance偵測**：passthrough `dosbox_harness.sh status`
的輸出後,對每個instance比對UPTIME_S欄位是否達到門檻(預設3600秒,鏡射`dosbox_harness.sh`自己的
`KEEPALIVE_DEFAULT`),達到就多印一行`STALE:`警告——純提示,不會自動teardown。存在原因：Phase 4
第2輪確實發生過「以為是新一輪,結果是13小時前忘記關的instance」(`92-m5-normal-playthrough-log.md`)。
live測試：預設門檻(3600s)對一個剛啟動35秒的instance不觸發,`--stale-after 10`則正確觸發並印出
警告文字。

**3. `tools/fd2_dual_verify.py`——remake vs DOSBox-X雙邊同步截圖比對工具**：對兩個「已經各自啟動
好」的instance(一個remake、一個DOSBox-X)送同一個按鍵、兩邊都截圖、寫一筆manifest.jsonl紀錄
(index/label/key/兩邊screenshot路徑/settle狀態/no-response旗標)。存在原因：這個專案已經因為
「兩邊分開跑、事後拼screenshot比對」反覆繞路過(索爾/盜賊誤判、`~/fd2-run/FD2.EXE`污染事件)——
把「同一個按鍵送兩邊」這個動作本身變成一個機械化、逐步紀錄的原子操作,至少讓「兩邊到底是不是同一個
時間點/同一個輸入」不再是要事後回憶的事。**刻意沒做的事**：不負責啟動/同步兩邊到同一個起始畫面
(remake跟DOSBox-X的launch語意差太多,場景同步只能由呼叫端自己決定要不要先手動對齊)、不負責判斷
兩張截圖是否「相同」(只負責配對存檔,比對仍是人/agent讀圖的工作)。獨立instance(`dv_remake`+
`dv_dosbox`,各自單獨啟動、沒有刻意同步起始畫面)live測試`step`一次:manifest正確寫入、兩邊
screenshot都是有效PNG(remake那張是索爾對父王對話的過場,dosbox那張是片頭鑰匙孔logo)——**兩邊
畫面確實不同**,這正確反映了兩邊沒有被同步到同一個時間點的事實(這是預期行為,不是bug:這個工具
本來就不負責同步起始狀態),也再次確認manifest/檔案配對的機制本身是對的。

### 誠實記錄：這個工具刻意沒有解決什麼

**輸入可靠性問題**：`key --wait`/`key --settle`/`wait-settle`是`fd2_live_input_helper.{py,sh}`
同一套「settle-confirmed送鍵」模式的DOSBox-X版本,是**緩解**手段,不是修法——這個專案已經花了9輪
獨立調查(`58-remake-live-verification-log.md`續七十~續七十七,關鍵字「xtrace」/「掉鍵」)在這個
Xvfb/xdotool/DOSBox-X輸入層問題上,doc58自己的結論是「已重新定界的環境限制」，不是解決。這次live
測試也印證了`--settle`誠實的定義邊界：在一張仍在動畫過場的畫面上送Escape後,`--settle`在極短時間內
就回報`SETTLED`——螢幕截圖前後2次確實pixel-identical(角色立繪過場恰好停在同一張靜止幀上),`--settle`
如實回報了它觀察到的事實,但這只證明「這段輪詢窗口內畫面沒有變」,不代表遊戲邏輯真的處理了那次
Escape、也不代表畫面永遠不會再變——跟remake側template docstring裡「持續動畫的畫面永遠不會有連續
兩張完全相同的截圖」的既有警語是同一個誠實邊界,這裡再次確認,沒有新解法。

**MEMDUMPBIN已知upstream bug(#3629,回報成功卻不產生檔案)**：`mem-dump`只是在偵測到這個症狀時把
它清楚標示出來、並在錯誤訊息裡指向`D`資料檢視指令這個既有workaround(`doc48`§4.2/§8.4),**沒有**
自動切換去執行`D`指令再解析——這次任務brief明確劃定範圍是「把既有已證實的技巧包成好用的指令」,不是
再開一條新的RE或環境調查支線,這次也確實沒遇到這個bug發生(所有`mem dump`呼叫都順利拿到檔案),沒有
機會實測這個fallback路徑本身。

### 產出/收尾

Live測試全程使用獨立instance(`dosboxtoolcheck`/`dosboxtoolcheck2`/`dosboxtoolcheck3`,port
`:199`/`:299`,期間`dosbox_harness.sh status`與`ps aux`都確認過沒有跟其他canonical session
(`:99`/`dbg`/`~/fd2-run`)或其他agent的instance重疊)。全部測試結束後`teardown-all`+`ps aux`
(`dosbox-x`/`Xvfb`/`tmux`都查無殘留)+手動清掉3個測試用workdir(共約426MB)收尾乾淨。全程沒有寫入
或修改`~/fd2-run/FD2.EXE`——`verify-canonical`預設路徑跑出的`MISMATCH`結果(`72e36e47...`)與已知
的ch27 debug-patch狀態(`docs/knowledge-base/92-m5-normal-playthrough-log.md`續八/續九)完全吻合,
`--path`指向`C:\Users\kg701\Desktop\GAME\FD2`那份獨立乾淨備份時正確回報`OK`——兩種路徑都驗證過。

### 續 — windowfocus修法後的完整迴歸測試(2026-09-02,用戶明確要求「完整檢測工具本身」)

在92續六發現並修好`cmd_send_keys`/`cmd_enter_debugger`缺少`windowfocus --sync`的問題之後,
用戶要求把整個工具(不只按鍵傳遞這一項)重新完整測過一輪。方法：全新instance
(`fulltest`/`fulltest2`/`fulltest3`,對`~/fd2-run-pristine`),逐一測每個子指令的正常路徑
跟至少一個錯誤路徑,不假設「先前測過一次就代表現在還是對的」。

**全部驗證通過(正常路徑)**：
- `verify-canonical`——預設路徑正確抓到`~/fd2-run/FD2.EXE`的已知污染狀態(MISMATCH,
  `72e36e47...`)、`.pristine_bak`正確回報OK；`~/fd2-run-pristine`整份也正確回報OK(兩個檔案都
  match pristine hash)。
- `status`/`--stale-after`——預設3600秒不誤報剛開的instance；手動給極小門檻(`--stale-after 3`)
  正確標出STALE警告,行為與原始碼邏輯一致。
- `screenshot`——raw/`--autocrop`/`--resize`三種模式`identify`逐一核對維度：raw恆為1024x768
  (整個Xvfb畫面,未被autocrop/resize動過,符合文件承諾)；autocrop view裁到640x415(符合doc記載的
  640x417再扣掉fuzzy trim的幾px)；resize view精確縮放到指定的320x240,無變形。
- `key`——別名(`confirm`/`up`/`down`/`left`/`right`/`space`)全部正確解析成xdotool key name；
  `--flag-no-response`在沒有`--settle`時正確印警告並忽略,不會誤用。
- `debugger-status`/`--baseline`——ACTIVE/INACTIVE偵測正確；baseline SCREEN_CHECK交叉比對機制
  本身運作正常,但**再次現場驗證了原始碼註解裡已經記載的「pane文字離開debugger後可能不會即時更新」
  這個已知限制**(連續3次Alt+Pause切換後,pane文字仍持續顯示ACTIVE、`Code Overview`字串仍在——用
  原始`tmux capture-pane`直接讀Register Overview欄位交叉確認,這不是新bug,是已知caveat的再次
  現場複現，不需要修）。
- `wait-settle`獨立指令——在畫面確實靜止時2次輪詢內就正確settle,行為符合文件描述(先前續六發現的
  「持續動畫畫面永遠不settle」不是這個指令本身壞掉,是特定畫面類型的固有限制,這裡在非動畫畫面上
  驗證了正常情況也是對的)。
- `mem dump`/`mem read-unit-record`——正常路徑成功寫出並hexdump；`read-unit-record`對超出
  dump範圍的欄位正確印出`<out of range>`而非猜測或崩潰。
- N-way隔離——同時起兩個instance(`fulltest`/`fulltest2`,各自獨立DISPLAY port `:199`/`:299`),
  對`fulltest2`單獨送鍵後用md5確認`fulltest`的畫面完全不受影響(跟送鍵前byte-for-byte相同)——隔離
  機制正常。
- `teardown-all`——同時關閉兩個instance,`status`確認乾淨,無殘留Xvfb/tmux/dosbox-x行程。

**錯誤路徑全部給出正確的診斷內容,但發現一個真實的呈現面缺口(已修)**：`mem dump --selector 0`
(零selector防呆)、對不存在instance送`screenshot`——兩者底層`.sh`腳本回傳的錯誤訊息內容都完全正確
且資訊充分,但`fd2_dosbox_live_helper.py`的`sh_checked()`是用`raise RuntimeError(...)`,而`main()`
先前沒有包`try/except`，導致CLI使用者看到的是一整段Python traceback，真正有用的錯誤訊息被埋在
traceback最底下。**這是本輪唯一找到、且確認修好的真實缺口**——在`main()`加一層`except RuntimeError`
只印`ERROR: {e}`+`return 1`，不動`SystemExit`路徑(`key --settle`逾時等既有的直接`raise
SystemExit(2)`不受影響，因為`SystemExit`不是`RuntimeError`的子類別)。修好後兩個錯誤路徑重測都變成
乾淨的一行`ERROR: ...`+`rc=1`，`--help`跟其他既有成功路徑不受影響。

**另一個確認：先前(92續六)提過的`verify-canonical --path`「WSL-style路徑」文件承諾的小陷阱**——
測試時發現如果外層呼叫本身是Git Bash(這個Bash工具)又沒加`MSYS_NO_PATHCONV=1`，一個看似合法的
`/home/.../fd2-run-pristine`路徑會在Python腳本收到參數之前就被Git Bash自己的MSYS轉換打亂，導致
"not a directory"的誤導性錯誤——**這不是Python工具本身的bug**(工具收到什麼字串就如實使用什麼字串，
逐字傳遞的承諾對它自己收到的argv是兌現的)，而是「呼叫者環境」這一層的既有已知陷阱(跟這個專案其他
`wsl bash -c`相關的MSYS路徑重寫問題同源)。價值：確認了這不需要在Python工具內修，但值得在這裡記一筆，
避免未來有人被這個特定錯誤訊息誤導去改錯地方。

**結論(當時的自我評估，事後發現偏樂觀，見下方續二的誠實修正)**：這一輪覆蓋了大部分子指令的正常
路徑跟部分錯誤路徑，除了已修的traceback呈現問題之外沒有找到其他功能性錯誤——`windowfocus`修法沒有
引入任何回歸。commit `10c09678`，push到`fork`。

### 續二 — 用戶追問「工具的所有功能都確認了嗎？」，誠實核對後發現續一其實沒有真的覆蓋到全部(2026-09-02)

用戶這句追問本身就點出續一的結論下得太早——逐一比對子指令清單跟續一實際跑過的測試，發現至少5個
先前沒測到的洞：

1. **`key --settle --flag-no-response`——這個功能本身核心的`response=CHANGED`/`response=
   NO_RESPONSE`輸出，先前兩輪都從沒真的看到過**（續六唯一一次呼叫因為畫面持續動畫而TIMEOUT，
   TIMEOUT分支的`.sh`程式碼根本不會印`response=`這個tag；續一的完整測試裡這個旗標本身完全沒被叫
   到過）。這是本輪認為最重要的一個洞——`--flag-no-response`是9/2當天新建的功能，先前的live驗證
   全部間接依賴這個機制「應該」正常，但從沒真正逼出它的兩種輸出。
2. `wait-settle --baseline`（獨立指令，不是透過`debugger-status`那條不同程式碼路徑）完全沒測過。
3. 必要參數缺失的防呆（`key`不給任何鍵、`mem dump`缺`--selector`）、`teardown-all`對空registry
   的行為——都沒測過。
4. `screenshot --out`/`--view-out`自訂路徑（先前全部用預設路徑）沒測過。
5. `--wait 0`的警告訊息路徑沒測過。

**逐一補測，全部通過**：新開`flagtest` instance，等~35秒非skippable開場動畫播完到達靜態標題選單
(START/LOAD/CONTINUE)。用`wait-settle --baseline`(獨立指令)在真的什麼都沒送的情況下確認先settle
再正確判定`NO_RESPONSE`；接著用`key Down --settle --flag-no-response`(游標會移動)拿到真正的
`settle: OK (...response=CHANGED)`；再用`key q --settle --flag-no-response`(標題選單沒綁定的鍵)
拿到真正的`FLAG: NO_RESPONSE`+`response=NO_RESPONSE`——**這是這個旗標從被寫出來到現在，第一次
兩種輸出都被真正逼出來確認過**。`key`缺鍵/`mem dump`缺selector正確走argparse自己的
`required`檢查(乾淨的usage訊息，非追加的手寫防呆)；`teardown-all`對空registry印
`(no harness instances registered, nothing to tear down)`+`rc=0`；`--out`/`--view-out`自訂
路徑正確寫到指定位置；`--wait 0`正確印出doc58援引的掉鍵風險警告。全部teardown+`status`確認乾淨。

**結論(修正後，這次才是誠實的完整版)**：工具的每一個子指令、每一個文件裡承諾過的旗標行為，現在
都至少有一次end-to-end的live確認，沒有殘留「應該可以但沒測過」的角落。唯一仍然刻意留白、不是這次
沒做到而是本來就超出這個工具audit範圍的：MEMDUMPBIN的upstream `#3629`空檔案fallback路徑(這次
`mem dump`呼叫全部順利拿到檔案，沒機會踩到這個症狀，續一已誠實記錄過這一點)，以及Attack/Spell/
Item卡在ring之後的深層RE謎團(那是遊戲邏輯本身的問題，不是這個工具的功能)。
