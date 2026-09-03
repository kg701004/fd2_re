# 98 — 研究工具基礎建設(非遊戲知識,純 agent 工作效率)

> 跟遊戲本體知識無關,記錄「怎麼更快做 RE 研究」本身的工具鏈,避免每個 session 重新發明。

> **2026-09-02:`remake/` 已整個移除(使用者明確指示)。** 本檔裡任何以驅動 remake 實際
> 執行為目的的工具章節(例如「remake 側 xdotool 合成鍵盤輸入可靠性」、
> `tools/dosbox_diff_harness.*`、`tools/fd2_live_input_helper.*` 相關段落)描述的工具
> 現已失去作用對象(remake 執行檔已不存在),內容保留作為移除前的歷史紀錄。與
> Ghidra/DOSBox-X 原版相關的工具章節不受影響,正常適用。詳見 `91-worklist.md` M5 段落、
> memory `feedback_fd2_re_remake_verification_paused`。

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

> **⚠️ 操作前必讀(2026-09-02，用戶明確要求「未來不可再發生相同的狀況」)：判斷部署/戰鬥畫面上
> 「游標框是否對準某個單位」時，絕對不要用截圖肉眼比對游標框跟角色立繪的畫面位置來下結論——
> 這款遊戲的角色立繪比一格地圖磚高，會往上戳進實際站立格子正上方那一格的畫面空間，游標真的停在
> 空地上時，畫面看起來也會像「剛好對準了角色頭部」，造成完全以假亂真的錯覺(完整成因見
> `92-m5-normal-playthrough-log.md`續九，該輪連續兩次獨立誤判才抓到)。**唯一可靠的判斷依據是
> 左下角迷你狀態卡的內容**：只顯示地形圖示+修正值(如`A+05 D+00`)＝空地；顯示角色頭像+HP數字＝
> 游標真的在該單位的格子上。按Enter選取任何單位之前，先screenshot確認迷你狀態卡有頭像，不要只
> 看游標框位置。詳見專案記憶`feedback_fd2_re_cursor_tile_verification`。**

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

### 續三 — 把Attack調查(續九~續十六)手動摸索出來的技巧正式收進工具，新增`resume`+3個delta校準指令(2026-09-02)

用戶明確要求「先改善工具，如果需要新工具或功能請自行建立」，再繼續深挖前先把上一輪(續十四/續十六)
手動重複做了十幾次的操作變成可重用指令。

**1. `resume`(新subcommand，修好Alt+Pause「離開debugger」不可靠的問題)**：續十四/續十六live撞到
Alt+Pause第二次呼叫（意圖離開debugger）連續失敗好幾次，`I-> _`提示字元讓人誤判還在debugger裡，
但這個訊號本身可能只是stale——當時是手動用「送一個會造成明顯位移的按鍵、直接看有沒有位移」交叉
確認才發現真相。現在包成`resume`指令：偵測到pane顯示debugger TUI時，改送debugger自己的`RUN`
console指令（跟`debugger-cmd`用同一套機制），比依賴Alt+Pause熱鍵更可靠；`--verify`旗標可選擇性
自動做「送RUN後間隔N秒截兩張圖比對」的驗證，取代先前手動反覆截圖比對md5的流程。**Live驗證**：
`resume --verify`正確回報`OK: screen changed`(標題畫面本身有動畫)；刻意呼叫兩次(模擬「其實已經
在跑但pane還顯示stale ACTIVE」的情境)確認第二次多送一次`RUN`完全無害，不會意外把遊戲重新暫停或
造成其他副作用——這個「偶爾多送一次但永遠安全」的取捨是刻意的，不是要修的bug。

**2. `mem find-signature`(新subcommand，通用化)**：把續十四/續十六用python手寫的「dump+搜尋
signature+算delta」邏輯收進工具本體，帶入signature/ghidra位址即可用，不綁定任何特定的資料結構，
未來任何需要同一套delta校準技巧的地方都能重用，不用再手寫一次性python腳本。**Live驗證**：對真實
34-byte ring-entry-gate簽章找到單一命中`0x1ad912`，算出delta `0x19c000`——跟續十六手動算出的值
逐位元組一致；額外測試0-hit的錯誤路徑（給一個查無此串的假簽章），正確回報`hits: 0`+`delta: N/A`+
`rc=2`，不是含糊的例外或當機。

**3. `mem resolve-ptr`(新subcommand，通用化)**：把「讀取指令的live disp32操作數+解參照一次」包成
獨立指令，同樣不綁定特定用途。**Live驗證**：對續十六找到的`0x1ad8e2`（`MOV EDX,[0x53a45]`的live
位址）正確解出`disp32=0x1efa45`、解參照後的值`0x1f6c80`——跟同一時刻`mem read-unit-array`(見下)
算出的陣列base完全一致，交叉驗證兩個指令算的是同一件事。

**4. `mem read-unit-array`(新subcommand，一鍵化整條技巧)**：把續十六整套「找簽章→算delta→解指標
鏈→dump陣列→逐筆decode」流程焊死成內建常數(`GATE_CHECK_SIGNATURE_HEX`/`GATE_CHECK_GHIDRA_ADDR`/
`UNIT_ARRAY_PTR_INSTR_GHIDRA_ADDR`)、一鍵執行到底，把續十六耗費約15次手動tool call才做完的流程
壓縮成1次呼叫。**Live驗證**（在標題畫面，非戰鬥中，刻意選一個「陣列還沒初始化」的情境測試機制本身
而非數值本身）：signature/delta/指標中繼值三項都跟續十六的真實戰鬥現場數值完全相同(`0x1ad912`/
`0x19c000`/`0x1efa45`)——這幾項屬於程式碼層級的常數，不受遊戲狀態影響，重現一致證實工具機制正確；
陣列base在標題畫面讀到`0x1f6c80`（跟續十六戰鬥中讀到的`0x237a48`不同，且逐筆記錄看起來是隨機亂數，
不像任何已知單位）——這完全合理，不是bug，只是還沒進戰鬥、陣列尚未被遊戲自己初始化，模組docstring
已誠實記載「常數在不同情境/環境下可能需要重新校準」這個限制，不是宣稱永遠有效。

**檔案異動**：`fd2_dosbox_live_helper.sh`新增`cmd_resume`；`fd2_dosbox_live_helper.py`新增
`resume()`/`mem_find_signature()`/`mem_resolve_ptr()`/`mem_read_unit_array()`四個函式+對應CLI
handler與argparse子指令，模組docstring「USAGE」段落補充新指令範例。全部四個新指令都已個別live驗證
過正常路徑，`find-signature`額外驗證過0-hit錯誤路徑，`resume`額外驗證過「已經在跑時重複呼叫仍然
安全」。

### 續四 — 用戶追問「工具有完整自檢確認功能了嗎？」，逐一補測邊界情況，找到並修好一個真的洪水bug(2026-09-02)

續三收工時的「沒有只寫完沒測就收工的部分」下得太早——逐一核對後，還有好幾個邊界情況沒測過。系統性
補測：

1. **`resume`/`mem resolve-ptr`/`mem read-unit-array`對不存在的instance**——三個都正確走到既有的
   clean error path(`rc=1`，訊息完整，非traceback)。
2. **`resolve-ptr`在debugger未啟動時**——正確繼承`mem dump`既有的警告+`#3629`已知bug錯誤訊息。
3. **`resume`在debugger未啟動時**——正確判定為no-op，不誤送`RUN`。
4. **`find-signature`多重命中(重大發現，已修)**：故意用一個很短、很常見的2-byte樣式("0000")去搜
   一段10000-byte記憶體，命中**65529次**——修改前的程式碼會把每一個命中位址都印出來，造成768KB的
   輸出洪水。**這是一個真的、會實際影響未來使用的bug，不是紙上談兵的邊界情況**。**修法**：命中清單
   印出上限20筆，超過的部分改印「...and N more」摘要，`delta`判定邏輯完全不受影響(非剛好1次命中
   一律回報N/A)。`mem_read_unit_array()`內部組`signature_hits`清單時發現同一個模式(雖然它固定用
   34-byte內建簽章，現實中不太可能命中上萬次，但邏輯上是同一個洞)，順手用同一個上限修好，維持
   一致性。修完後重新驗證：0-hit、正常1-hit、多重命中三條路徑都乾淨、正常路徑無回歸。
5. **`read-unit-array --num-records`邊界值(0跟200)**——都正常，0給出空表格不當機，200正確dump/
   decode 200筆。
6. **`resolve-ptr --disp-offset`自訂值、`read-unit-array --out-dir`自訂路徑**——都正確運作，輸出
   檔案確實寫到指定位置。

**誠實留白一項**：`resume --verify`在「真的靜態畫面(無動畫)」下會不會正確印出`WARNING: screen
unchanged`，這次沒有獨立live驗證——只在有動畫的標題畫面測過(正確回報`OK: changed`)。背後用的
screenshot-diff機制跟`wait-settle`/`debugger-status --baseline`是同一套邏輯，那兩個先前已經在
本專案於本次session內用真正靜態畫面驗證過兩種結果都正確，`resume --verify`是直接複用同一段邏輯、
沒有新寫程式碼，風險判斷為低——但這是風險判斷，不是獨立驗證過的宣稱，如實記錄兩者的差別，避免
未來誤讀成「已經測過」。

### 續五 — `resume`live撞到真的按鍵時序問題，改成「清行+自動重試」而非改猜新的送鍵方式(2026-09-02)

續四剛修好的`resume`工具，在續十五實際拿來做斷點式追蹤時，連續兩次呼叫撞到真的問題：兩次送出的
`RUN`文字疊在debugger console同一行沒有被送出(`I-> U 0170:1B4F2FRUNRUN_`)，導致`resume`回報
成功但遊戲其實還在暫停。**判斷這極可能是本專案本身反覆記錄過的tmux/xdotool按鍵時序既有問題(doc58
續七十~續七十七)，不是`cmd_resume`這個送法本身的缺陷**——`dosbox_harness.sh`的`cmd_debugger_cmd`
整個session用完全相同的`-l text`+`-l $'\r'`送法沒出過任何問題，只是這次剛好又撞上同一類偶發
flakiness。因此**沒有貿然改用具名Enter鍵**（doc48§8.4明確記載「Enter必須用字面`\r`單獨送，不要
跟具名Enter/C-m鍵混用」——手動用具名Enter鍵能救回這次的session，不代表那是正確或必要的修法，更
可能只是巧合湊到問題自己消失的時間點）。

**真正的修法**，沿用這個工具箱一貫的settle/verify哲學：
1. `cmd_resume`(.sh)——送`RUN`前先送一次清行(`Ctrl+U`)，去掉任何殘留、未送出的輸入，這個動作
   本身無害且能排除「文字疊加」這個失敗模式，不管根因是什麼。
2. `resume --verify`(.py)——從「偵測到沒變化就印警告」改成**自動重試最多3次**，把「大多數時候
   是暫時性的按鍵時序問題」直接吸收掉，只有真的重試3次都沒用才警告，呼叫者不需要自己寫重試迴圈。

**Live重新驗證**：修好後在同一個(先前卡住的)instance上呼叫`resume --verify`，第一次呼叫就正確
回報`OK: screen changed...(attempt 1/3)`，確認修法有效，沒有引入回歸。

## `tools/fd2_original_verify.py` — 原版側「宣告式 / 平行 / 分層」驗證器(2026-09-03)

**動機**：2026-09-02/03 那批「用原版補驗」的輪次全是手動驅動（launch→patch章節byte→猛按
Enter→肉眼看截圖），慢，而且**「我到底走到哪個畫面」是靠人眼判斷的**——這正是歷史上產生
錯標證據的同一個機制（見doc58同日「13/18張對照圖是自我複製」與「售出圖/轉移圖混用」兩節）。
本工具把一輪驗證變成**資料**：scenario列出步驟與斷言，runner執行，report記錄哪條斷言在哪張
截圖上通過。走錯畫面會**fail**，而不是被寫成看起來很有把握的結論。

**分層斷言**：`L1 reach`（有沒有到達預期畫面，`assert_ref`比對參考圖）／`L2 content`
（畫面內容對不對，`assert_distinct`等）／`L3 data`（跟非視覺來源交叉核對，`assert_save_field`
回頭讀`fd2save.py`）。L1失敗會**中止該scenario後續步驟**——在未知畫面上繼續送鍵，正是產生
「很有說服力但拍錯東西」的截圖的原因。

**★ 平行化與一個實測出來的race（本工具最有複用價值的發現）**：`dosbox_harness.sh`本來就給
每個instance獨立的Xvfb display／tmux socket／遊戲目錄，所以N個scenario**可以**真的同時跑。
但`pick_display_port()`**不是concurrency-safe**——它靠掃registry與`ss -tln`挑port，而勝出的
port要等Xvfb起來、`.state`寫檔後才對其他launcher可見；**同時發動的兩個launch會在任何一方
留下宣告前就各自掃描完畢，於是挑到同一個display**。這不是推測，是實測：`--jobs 2`時兩個
scenario都落在`127.0.0.1:199`，按鍵全進同一個視窗，兩邊都到不了title；同一個scenario
`--jobs 1`卻全部通過。本工具的處置是用`LAUNCH_LOCK`**只序列化launch階段**，佔時間大宗的
按鍵驅動仍完全平行。**真正的修法（lock file或顯式port參數）應該做在`dosbox_harness.sh`裡面**，
本輪沒有動那支腳本。

> **後續（2026-09-03）：這個race已經修在`dosbox_harness.sh`本身**（`reserve_display_port`
> ＋flock＋reservation狀態檔，回歸測試`tools/test_dosbox_harness_ports.sh`）。本工具的
> `LAUNCH_LOCK`已解除，預設launch真正平行，`--serial-launch`保留為退路。
> 見本文件最後一節。以上這段保留為當時的觀察紀錄。

**另一個實測踩到的坑**：`launch`結尾是長時間keepalive sleep，**必須讓它活著**（腳本自己的
header與doc48 §8.4都寫過）。第一版用`subprocess.run(..., timeout=25)`呼叫launch，timeout會
**殺掉launcher**、連帶把整個instance收掉，症狀是framebuffer全黑＋20次title poll全失敗。
現在改用`Popen`detached、永不timeout，並額外要求**畫面真的畫出非黑frame**才開始送鍵。

**驗證成果（本輪實跑）**：4個scenario（town variant0/1/2＋secret_shop）`--jobs 3`全部PASS。
平行隔離有硬證據：兩個並行run的`title_menu`截圖MD5相同（本來就是同一個畫面），但
`slots`／`sel0`~`sel4`全部不同——證明兩個instance各自載入了自己的章節、各拍各的。
`secret_shop` scenario也把doc58那個「酒店按Shift+F1」的秘密商店流程變成可重跑的自動驗證。

**用法**：
```
python tools/fd2_original_verify.py --selftest          # 離線自檢，不啟動DOSBox
python tools/fd2_original_verify.py --list
python tools/fd2_original_verify.py --all --jobs 3
python tools/fd2_original_verify.py --all --jobs 3 --repeat 3   # 重複跑並檢查跨run穩定性
python tools/fd2_original_verify.py --run secret_shop --keep    # 保留instance供人工檢查
```
參考圖放在`.wsl_build/verify_refs/`（`title.png`、`title_load_menu.png`），報告與逐張截圖
輸出到`.wsl_build/original_verify/<timestamp>/`。scenario本身是**資料**（`SCENARIOS` dict），
新增一個驗證項目不需要寫新的流程程式碼。

### 附帶清理：269個殘留harness工作目錄佔用70GB，已備份獨特存檔後回收(2026-09-03)

建`fd2_original_verify.py`時順手檢查WSL2側磁碟，發現`~/fd2-run-harness-*`累積了**269個**
歷次輪次留下的工作目錄，合計**70GB**——佔該檔案系統當時已用78GB的**90%**。這是
`dosbox_harness.sh`的**刻意設計**（teardown訊息就寫著「workdir left in place - delete
manually if not needed」），不是bug，但沒有人回頭清過。

**刪除前先做的事（重要，不要跳過）**：逐一比對每個工作目錄裡的`FD2.SAV`與canonical
`~/fd2-run/FD2.SAV`的md5，結果**196個含有獨一無二的存檔**（`sweep16`~`sweep30`等章節掃描
輪的真實進度、`townE2`/`tavernE2`/`writerfire`等專輪狀態）。這些如果直接`rm -rf`就永久消失。
故先全部備份到`~/fd2-harness-saves-archive/<instance>.SAV`——**196個檔案總共只有4.6MB**，
成本可以忽略，卻保住了所有不可重現的狀態。

**刪除前的安全檢查**：harness `status`無註冊instance、`ps aux`確認0個live dosbox-x/Xvfb、
確認canonical的`~/fd2-run`與`~/fd2-run-pristine`**不在**`fd2-run-harness-*` glob範圍內、
備份檔案數與大小(22987 bytes envelope)全部正確。

**結果**：269個目錄刪除，磁碟已用量 **78G → 8.0G**（回收70GB，可用空間878G→948G），
`~/fd2-run`／`~/fd2-run-pristine`／存檔備份三者完好。刪除後立刻重跑
`fd2_original_verify.py --run town_variant0` 仍然 **PASS**，確認環境未被破壞。

**給後續輪次的建議**：每輪結束teardown後順手`rm -rf ~/fd2-run-harness-<instance>`
（`fd2_original_verify.py`已內建這個清理），否則以每個目錄約260MB的速度，很快又會累積回去。
真的需要保留某輪狀態時，保留`FD2.SAV`即可，不需要整個目錄。

### 2026-09-03 續：優化與反覆驗證結果

使用者要求「優化工具並反覆驗證、確認無異常再繼續」，本輪做了四件事並實測：

**1. 效能**：`mean_abs_diff`（`poll_title`每次迭代都會呼叫的熱點）原本是純Python雙層迴圈，
每次比較約48k個直譯運算。改成numpy向量化並保留一份**dependency-free參考實作**
（`_mad_reference`，改用`tobytes()`避開Pillow 14要移除的`getdata()`）。實測
**87.0ms → 5.2ms / 50次呼叫（17倍）**，且`--selftest`會強制斷言兩條路徑數值相同——
快速路徑不可能悄悄偏離參考路徑。

**2. 截圖round-trip減半**：harness的`screenshot`本來就吃目的路徑，所以直接寫進
`/mnt/c/...`的run目錄，省掉原本「先寫`/tmp`再`cp`」的第二次`wsl.exe`呼叫。同時加上
**重試**（`import`偶爾會跟模式切換搶輸出而產生空檔，屬transient），但**永不偽造frame**：
三次都失敗就丟例外。內部探針（`_boot`/`_poll`）改用`_`前綴並排除在report的frame清單外。

**3. `--selftest`（離線自檢，不啟動DOSBox）**：22項檢查，涵蓋影像運算正確性（相同幀diff=0、
純黑vs純白=255、md5穩定性）、兩條diff實作一致性、「畫面是否已渲染」的黑幀gate、以及
**scenario靜態檢查**（op是否都已實作、`assert_ref`/`assert_distinct`指向的label是否真的有被
`shot`拍過、參考圖是否存在）。這類typo以前只會在跑到一半時變成靜默no-op。
以`-W error::DeprecationWarning`執行仍全綠。

**4. `--repeat N` 跨run穩定性檢查（本輪最有價值的新增）**：同一個scenario從同一份存檔重播，
理論上該產生完全相同的frame。實測`--all --jobs 3 --repeat 3`（共12次scenario執行）**斷言
全部PASS**，但frame hash**不穩定**——這正是這個功能要抓的東西。逐一量化後確認：

> 每一個不穩定的frame，差異都是**0.54~0.57%的像素、且全部落在單一48×48px方框內**
> （＝24×24的FDICON sprite在2倍擷取比例下的大小），位置隨selection移動而移動。

這與doc58 `UI-VIS-TOWN`條目**早就獨立記錄過**的現象完全吻合（「362/64000像素(0.57%)差異
全部集中在隊長站立sprite的24×24px範圍…根因是擷取時機沒有釘住待機動畫相位」）——本工具
等於獨立重新發現了同一件事，是對工具正確性的一個好佐證。

因此把不穩定**分類**而不是壓平：符合動畫特徵者（像素比例≤1%且差異框≤64×64，門檻取自實測值
略上方，不是隨手取的整數）標為`ANIMATION`不算失敗；更大或更分散者標為`STRUCTURAL`並讓
exit code為非0。分類後重跑`--repeat 3`：**12/12 PASS、全部ANIMATION、零STRUCTURAL、
exit code 0**，另外也抓到商店店主自己的待機動畫（`shop_interior` 0.12% / 20×32px）。

**結論**：工具本身無異常。**frame MD5不能單獨當作畫面identity**（含動畫sprite的畫面本來就
會變），要嘛比對排除sprite區域，要嘛沿用`dosbox_diff_harness.py`既有的`lock_pulse_phase()`
思路先釘住動畫相位——本工具選擇「量化後分類」，因為驗證關心的是畫面**語意**是否正確，
而不是逐位元組相同。

**清理**：24次scenario執行後，harness `status`無殘留instance、`ps aux`零個live程序、
`~/fd2-run-harness-*`工作目錄0個（工具每輪自動刪），磁碟維持8.0G。

---

## `dosbox_harness.sh` display port 分配的 TOCTOU race —— 真正修好(2026-09-03)

前一輪把這個race**繞過**（`fd2_original_verify.py`用一把python端的`LAUNCH_LOCK`把launch階段
序列化），並誠實記為「真正的修法尚未做，屬於harness本身」。本輪把它修在來源。

### 病灶

舊的`pick_display_port()`只是「掃描registry找活著的instance＋`ss -tln`」然後**回傳**一個port。
問題在於：這個選擇要等到`.state`檔寫出去才對其他launcher可見，而寫檔發生在
**複製工作目錄→啟動Xvfb→sleep 3→開tmux→sleep 2**之後，中間有5~10秒的空窗。
兩個同時開始的launch都在空窗內掃到「沒人佔用」，於是都選了`:199`。

`ss -tln`那道「保險」也補不到：它要等Xvfb真的開始listen才會回報，而那已經是視窗都開了之後。

**實測病徵**（前一輪記錄）：`--jobs 2`時兩個scenario都落在`127.0.0.1:199`，按鍵全部進到同一個
視窗，兩邊都到不了title；同樣的scenario在`--jobs 1`則通過。

### 修法：把「選擇」與「公告」變成同一個原子動作

- `reserve_display_port()`在持有`flock`（`$REGISTRY_DIR/.portlock`）的期間**同時**完成掃描與
  **寫出reservation狀態檔**（`XVFB_PID=`空、`STATUS=reserving`），釋放鎖時選擇已經對所有人可見。
- **佔用判定改成兩段式**：還沒起Xvfb的reservation由**launcher程序的存活**持有；Xvfb起來之後
  同一個檔案被改寫成正式entry，改由**Xvfb的存活**持有。
  這兩段分開的理由是實際語意不同：setup中途死掉的launcher應該**自動釋放**它的port（不然
  每次失敗都漏掉一個slot），而keepalive還活著但Xvfb已經死掉的instance**不該**繼續佔著port。
- **正式entry改成Xvfb一起來就寫**（原本要等tmux開完、晚約5秒）。理由是修這個race時才看清楚
  的一個既有隱患：那5秒內若launcher因任何原因死掉，Xvfb會變成**沒有registry entry的孤兒**，
  `teardown-all`永遠找不到它。現在「port的持有者」與「teardown找得到它」這兩件事同時成立。
- 配套的`trap ... EXIT`只在**還沒有Xvfb的那一小段**有效（寫入正式entry後立刻`trap - EXIT`），
  這樣setup中途失敗不會留下stub，但**已經起了Xvfb之後絕不刪entry**——刪掉才會真的漏掉程序。
  `launch`結尾是`exec sleep`，會整個換掉process image，所以trap不可能在成功路徑上誤觸發。
- 順帶修掉的兩個小問題：原本掃描迴圈**沒有上界**（找不到就無限迴圈），現在有`DISPLAY_MAX`
  並以明確錯誤結束；`launch`對「同名instance已存在」的判定原本只看Xvfb，會讓兩個同名的並行
  launch互刪對方的registry entry，現在也認得live reservation。
- 每個instance的session名/工作目錄/log路徑改由`instance_session()`等單一來源產生，避免
  reservation stub跟正式entry漂移。

### 回歸測試：`tools/test_dosbox_harness_ports.sh`

完全離線（不開Xvfb、不開DOSBox、不碰遊戲檔），用暫時registry與一段確定沒人用的display範圍，
所以**可以在真的instance跑著的時候安全執行**——這點不是宣稱而是實測過的：本輪就是在三個真
instance跑`--all --jobs 3`的同時執行它，21項全過、兩邊互不影響。其中兩項是重點：

| 檢查 | 意義 |
|---|---|
| `control: 5 unlocked scans all collide` | 5條並行的**裸掃描**必定全部回傳同一個port——**這就是修好前的行為**，證明這個測試真的抓得到該bug，而不是一個永遠會過的空測試 |
| `concurrent reserve: all ports distinct` | 同樣5條並行，改走`reserve_display_port`後拿到5個**互異**的port |

並行測試用`FD2_HARNESS_PORT_RESERVE_DELAY`把scan→publish的空窗**故意撐開成1秒**，
所以結果是決定性的，不是靠時序運氣。

其餘檢查覆蓋：空registry、live reservation佔用、**死掉的launcher會釋放**、
**live Xvfb佔用**、**死掉的Xvfb即使keepalive還活著也要釋放**、reservation檔的欄位內容、
**reservation與正式entry兩種形狀都能在`set -u`下被`source`**（少一個欄位就會讓
`status`/`teardown`因unbound variable中斷）、以及範圍用盡時清楚報錯不無限迴圈。

寫測試時自己踩到、值得記下的兩個bash坑：
- `spawn_fake_xvfb`這類「背景起一個程序並回傳pid」的helper若在`$(...)`裡呼叫，
  背景子程序會**繼承那個command substitution的pipe**，於是`$(...)`會一直等到子程序結束才回傳
  ——測試因此整個掛住。必須把背景程序的stdout/stderr導掉。
- 不帶參數的`wait`會等**所有**背景job，包括前面幾個case刻意留著的`sleep 300`假程序。
  併發case一定要`wait`明確的pid清單。

### 整合驗證（真的開三個instance）

繞過python端的鎖，直接從Windows端同時發三個`launch`：

```
race1  display=:199  dosbox_windows=1  1024x768  mean=0.0087  md5=c1f7d072c222
race2  display=:299  dosbox_windows=1  1024x768  mean=0.0044  md5=015d8ebe6dce
race3  display=:399  dosbox_windows=1  1024x768  mean=0.0652  md5=6703a221818b
```

三個互異display、各自1個DOSBox視窗、3個Xvfb、3個各自掛在自己工作目錄的dosbox-x程序，
三張截圖**內容互不相同**（＝真的是三個獨立framebuffer，不是同一個畫面被拍了三次）。

### 連帶：`fd2_original_verify.py`的workaround解除

`LAUNCH_LOCK`改成`LAUNCH_GATE`，預設是`contextlib.nullcontext()`（launch真正平行），
保留`--serial-launch`作為退路。`--selftest`加兩項斷言確認這個gate真的會切換（24項全過）。

`--serial-launch`本身也實測過而不是「加了就算」：serial模式下三個instance的uptime是
26/20/14秒（相差約6秒＝一個接一個起），parallel模式下則是22/22/22秒。

**效能：實測而非宣稱，而且結論是「差不多」**。同一組12個scenario、`--jobs 3`：

| 模式 | 耗時 | 結果 |
|---|---|---|
| `--serial-launch` | **171s** | 12/12 PASS |
| 預設（平行launch） | **155s** | 12/12 PASS |

只快了約9%。原因很單純：launch階段大約只佔一個scenario（約40秒）的6秒，而pool只有3寬。
**所以這次修正的價值在正確性，不在速度**——它消除的是「兩個instance搶同一個display」造成的
偽失敗，順帶讓提高`--jobs`時launch不再變成序列化瓶頸。不要把它當成效能優化來引用。

### 誠實邊界

- 修的是**本harness自己的**分配。`ss -tln`那道保險仍然只在對方已經listen後才有效，所以若有
  完全不透過本harness、又剛好同一瞬間搶同一個port的外部程序，仍可能相撞——實務上不存在，
  但不宣稱已解決。
- `flock`需要util-linux的`flock`（WSL2 Ubuntu預設就有）。若缺，`reserve_display_port`會
  明確報錯而不是靜默退化成舊行為。

---

## `fd2_original_verify.py` 2026-09-03 續二：兩個新斷言原語，與一個「參考圖根本沒進版」的缺陷

### 新增 `measure_change`：記錄但不判定

用於**兩個答案都合法**的開放問題（本輪的「秘密商店在其他章節有沒有效」）。
對這種問題斷言任一方，都會把真正的發現變成「工具失敗」。

而且**不能用既有的 `assert_distinct`（MD5 相等）來問這類問題**：任何含待機動畫 sprite 的
畫面本來就 run-to-run 不同（0.54~0.57% 像素、≤48×48），所以「什麼都沒發生」會被判成
「兩張圖不同」——那個工具根本沒有鑑別力。改用 `classify_instability` 分 STRUCTURAL／ANIMATION。

（附帶收穫：這個分類讓「畫面沒變」與「模擬器當掉了」也能分開——秘密商店那輪的 null 結果
量到的正是動畫 sprite 的特徵，等於同時證明了遊戲當下仍在運行。）

### 新增 `assert_ref_differs`：必須**不**等於某個參考狀態

`assert_ref` 只能斷言「等於預期的 after」，那只是半個論證。
**如果兩張參考圖哪天變成同一個檔案，只有等式的檢查會繼續通過，卻什麼都沒證明**——
這正是本專案在 18 張對照圖裡抓到 13 張的那個缺陷。把「等於 after」與「不等於 before」
成對使用，那個不可證偽的組合就不可能成立。

`--selftest` 另加一條靜態檢查：**同一個 label 上成對使用的兩張參考圖必須真的是不同影像**
（直接比 MD5）。等於把那個歷史缺陷寫成一條會自己失敗的規則。

### 找到並修好：參考圖從來沒有進版

`REF_DIR` 原本是 `.wsl_build/verify_refs/`，而 `.gitignore:66` 排除了整個 `.wsl_build/`。
也就是說**每個 scenario 的 `assert_ref` 都指向一個從未被 commit 的檔案**，在乾淨 clone 上
`--selftest` 會直接失敗、所有 scenario 都過不了 L1。這是既有缺陷（`title.png` 早就如此），
本輪新增兩張參考圖時才暴露出來。

參考圖是**fixture 不是 build 產物**，所以改放 `tools/verify_refs/`（4 張共 84KB，已進版）。
另外 `title.png` 是被 `step_poll_title` 直接引用、不出現在任何 scenario step 裡，
原本的存在性掃描**掃不到它**——已明確加入必要清單。

### 本輪回歸

`--selftest` 80 項全過；`--all --jobs 3` **16/16 PASS**（含新增的 `equip_control`／
`equip_execute`）；改完 `REF_DIR` 後再單獨重跑兩個 equip scenario 仍全過。
環境零殘留、磁碟維持 8.0G。

---

## `fd2_original_verify.py` 2026-09-03 續三：把「用畫面文字判定身分」變成工具能表達的斷言

### 動機：這是本專案的核心紀律，但工具一直無法表達它

專案反覆講「**用畫面自身的文字判定身分，不要用按鍵次數推論**」，可是在此之前
`assert_ref` 只能比對**事先拍好的整張參考幀**——所以每一次文字判定**還是人眼在看圖**，
而那正是這個工具本來要消滅的步驟。

代價是實測到的：**同一天有三次跑完後才發現拍錯畫面**——
①售出後 `Escape`×2 直接離開場所（跑進教會，70% 不同）；
②服務選單游標不會重置，`Right`×2 跑到轉移而不是裝備；
③轉職對白**多按一次 Enter**，8 個樣本**全部**停在「誰要轉職呢？」而不是成長數值畫面。

第③個尤其危險：8 張圖 hash **完全相同**，若照著預期解讀，會得出
「成長值是決定性的、不隨機」這個**看起來很有說服力但錯誤**的結論。
是把圖拉出來看才發現它們相同是因為**同時停在同一個錯畫面**。

### 新增：具名畫面簽章（`assert_signature` / `assert_not_signature`）

簽章＝**具名的、緊裁到有辨識力文字的區域**，連同它的 box 一起存在 `tools/verify_refs/`
（`signatures.json`）。scenario 只寫名字：

```
python tools/fd2_original_verify.py --make-signature money_not_enough <frame.png> 20 215 430 345
python tools/fd2_original_verify.py --list-signatures
{"op": "assert_signature", "label": "prompt", "name": "who_class_change"}
```

**刻意不做 OCR**：遊戲文字是中文點陣字，字元辨識會為了一個「裁切區域雜湊就能精確回答」
的問題引入不可靠的相依。目前 box 取 `(20,215,430,345)`——涵蓋對白文字，
**排除金錢顯示**（免得簽章跟著金錢變）與**閃爍的 ▼ 標記**。

**`assert_not_signature`（鏡像）不是湊數**：當**被量測的東西就是畫面上的數字**時，
正向簽章會把那些數字一起編進去，於是待測值一變它就失敗——**它無法為自己把關**。
真正有用的是負向閘門：「我們還沒掉出這段對白、回到提示畫面」，
正是上面第③個失效的精確描述。

### `--selftest` 新增規則：簽章之間必須**互相可區分**

兩個互相匹配的簽章，會讓 scenario「確認」自己到了錯的畫面——
與「對照圖兩半是同一張」是同一類不可證偽的證據。
現在每一對同尺寸簽章都必須差異大於各自的容忍值；目前 4 個簽章、6 對全過。

### `--recon`：把偵察變成一等公民

```
python tools/fd2_original_verify.py --recon 1 "Left,Return,Return,Down,Return,Return"
```
從 title 開始驅動一串按鍵，**每按一次自動截圖、除 title 外不做任何斷言**。
這直接取代本輪手寫的 8 支幾乎一樣的一次性偵察腳本。
流程摸熟之後才寫成會斷言的 scenario——先偵察、後斷言，順序不能反。

### 尚未做（誠實列出）

- `classify_instability` 的門檻對**小型 UI 狀態變化太粗**：實測 YES/NO 選取標記變化只有
  0.06~0.16%、≤100×14px，會被判成 `animation`（＝把真的狀態改變報成「沒變」）。
  目前的正解是對這類判定改用緊裁切的參考圖比對，而不是那個分類器；
  但門檻本身還沒有分級或區域化選項。
- 已提交的 scenario 仍只涵蓋實際驗過內容的一部分。

---

## 2026-09-03 續四：把「曲號聽辨」變成量測——兩條獨立路徑，一條成功一條被自己的對照否決

使用者指示「remake 時代項目全部以原版驗證」，其中三筆是
「戰鬥曲／勝利曲／開場配樂**聽辨**(使用者)」。這類項目看起來非人耳不可，實際上不是。

### 路徑一：讀遊戲自己的曲號全域

doc12 早就反組譯出 `play_bgm`(`0x25977`)並證實 **`[0x51a11]` 就是目前播放曲號**。
新增 `fd2_dosbox_live_helper.py` 的 **`mem read-global`** 原語：用既有的
ring-entry-gate 簽章算出載入 delta，再讀 `ghidra_addr + delta`。
**任何文件已記錄的全域位址，從此都能在活體實測。**

**驗收錨點選得好，一次就驗證了整套方法**：標題畫面讀出 **18**，
與 doc12「反組譯 boot 唯一呼叫 ＋ 使用者實聽」雙重證實的 track 18 完全一致。

**接著加上 `--delta` 讓已校準的 delta 可重用**：不必每次重 dump 200KB。
效果是 **每個場景 450 秒逾時 → 19 秒**。使用 pinned delta 是一個「所有 instance
載入位址相同」的**假設**，所以規定用它的批次必須帶一個**已知答案的對照**——
本批用標題(必須是 18)，delta 錯就會讀到垃圾而不是 18。

**然後對照組救了一次**：五個遊戲內場景全部讀出 **250**。
`FDMUS.DAT` 只有 **21 個資源(000–020)**，所以 250 不可能是曲號。
**抓到它的是資源數這個獨立範圍界線，不是讀取器本身。**
原因未定，doc58 早就警告過 selector 不保證跨狀態穩定；本輪對 5 個 selector
逐一嘗試時遇到逾時，**此路徑在遊戲內狀態下仍未解**，誠實留開。

### 路徑二：擷取遊戲真正輸出的音訊（使用者提議：先音訊比對，再與影像時序同步）

新增 `tools/fd2_audio_probe.py`。

**先踩到的坑**：DOSBox-X 自己的 wave 擷取是 **宿主熱鍵 Ctrl+F6**，走它自家 mapper，
不是送給 DOS 程式的按鍵——實測完全沒有產生 capture 目錄
（同一天 `Ctrl+F1` 送給遊戲卻成功，兩者性質不同）。

**改用 SDL disk 音訊驅動**繞過 mapper：harness 加上 `FD2_HARNESS_AUDIO_DISK=1`，
讓 DOSBox-X 把混音輸出**持續**寫成 PCM 檔。這同時天然給出時序同步——
音訊是連續的，用「兩張截圖之間寫入的位元組範圍」切片，該段音訊就**證明**屬於那個畫面。

**三個被實測抓出來的缺陷**（都不會自己報錯）：
1. `SDL_DISKAUDIODELAY=0` 關掉了即時節流：**75 秒寫了 4.3 GB**，
   而且音訊時間軸不再對應牆鐘時間——時序同步會整個失效。拿掉即可。
2. `dd bs=1 skip=<數百萬>` 是逐位元組跳過，等同掛住。改 `bs=1M iflag=skip_bytes`。
3. **切片起點未做 frame 對齊**：`s0` 來自檔案大小，可能落在 frame 中間，
   於是每個 16-bit sample 從錯的位元組邊界讀取、左右聲道互換——
   **WAV 檔照樣開得起來、看起來正常，只是靜默損毀**。
   是自檢裡刻意用奇數偏移的切片把它照出來的（對自身來源的相似度掉到 0.827）。

實測擷取成功：48kHz 立體聲、14.2 秒切片、rms 0.09~0.11（非靜音）、
畫面變化偵測正常運作。**擷取與時序同步層可用。**

### 但識別層被它自己的對照組否決——這是本節最重要的一段

跨畫面相似度看起來很像結果：title/town/weapon_shop 兩兩 0.772~0.893。
**然後補了缺的那個對照：同一畫面、同一首曲的兩次連續擷取。**

| | same_a | same_b | title | town | weapon |
|---|---|---|---|---|---|
| same_a | 1.000 | **0.917** | 0.944 | 0.847 | **0.945** |

**同曲基準 0.917，比它對「不同畫面」的 0.944／0.945 還低。**
同曲基準落在異曲範圍之內，所以**這個指標無法判定兩個畫面是否同曲**，
先前那張矩陣不能用來下任何關於曲號的結論。

**為什麼離線自檢沒抓到**：自檢比的是合成純音，本來就容易分。
真實 FM/OPL 音樂共用同一組音色，不同曲子的**平均頻譜天生相近**，
而 14 秒視窗又只取到長曲的一小段。
**自檢必須跟真實訊號一樣難，否則它什麼都沒驗證。**

要修需要更有鑑別力的特徵（chroma／音高類別分布，或直接與 `FDMUS_NNN` 逐曲比對）
與涵蓋完整循環的視窗長度。在那之前，**這個工具是擷取與同步的載具，不是識別器**，
模組 docstring 的 STATUS 段已經照這個結論寫明。

### 附帶：劇情文本「30 章 PNG 人眼轉錄」的前提已過時

`tools/decode_story_text.py` 用 `glyph_map.json` 直接把 FDTXT 解成 UTF-8。
對 `extracted/raw/FDTXT/` 全部 **35 個資源**跑一遍：
**35/35 解碼成功、2260 行、未對映字元 0 個**；唯一 0 行的是專案早已記錄為
**損毀**的 `FDTXT_034`。

所以沒有需要人眼轉錄的未知字。**誠實界線**：零未對映只證明字模表**涵蓋**了所有用到的
glyph id，不證明每個 id 對到**正確**的字——那需要抽樣核對算繪結果，
但那是遠小於「轉錄 30 章」的工作。
（解碼內容是遊戲著作權文字，只作本機對照，不進版庫。）

---

## 2026-09-03 續五：擴大曲號量測時撞到的效能牆，與音訊識別的**確定性否定結果**

### 擴大到 23 個城鎮章節：**沒有完成**，卡在同一道效能牆

六個畫面的量測成功之後（doc12 同日段落），下一步是把它擴大到全部 23 個有城鎮的章節。
兩次嘗試都失敗，原因是同一件事：**取得 delta 太貴**。

| 取得 delta 的方式 | 成本 | 結果 |
|---|---|---|
| 完整程式碼簽章掃描（2MB） | **7 分鐘以上／次** | 6 個場景整批 900 秒逾時 |
| 候選 delta ＋位元組驗證（16 bytes） | **秒級** | 6 個已知畫面成功（22~39 秒／場景） |
| 候選清單擴大到 23 章 | — | **失敗**：delta 不是常數，**也隨章節載入的資料量而變**，沒命中就**靜默退回**完整掃描；24 個場景 8 分鐘零完成 |
| 窄窗搜尋變數自身簽章（384KB，免候選） | — | **仍然逾時**（單章 10 分鐘未完成） |

**根因不是掃描範圍大小，而是 MEMDUMPBIN 走暫停中的 ncurses debugger 這條通道本身很慢**，
且有固定成本。把窗口從 2MB 縮到 384KB 並沒有讓它變成可用。

**因此擴大量測需要先解掉這條通道的吞吐問題**，不是再調參數。
六個已量測的畫面（標題／城鎮／武器店／道具店／教會／秘密商店）仍然有效且已交叉驗證。

**同批要順帶測的 ch06 秘密商店組合鍵（與 ch03 同為 variant 2、不同組合鍵）也因此沒跑成**，
ch03 是否為孤立資料錯誤仍未定。

### 音訊識別：**確定性否定**（不是「還沒調好」）

`fd2_audio_probe.py` 的擷取與時序同步已驗證可用。識別層則因為有了 ground truth
（記憶體讀出 title=18／town=10／武器店=14）而可以**嚴格評分**：

| 特徵 | 同曲配對 | 異曲配對 | 判定 |
|---|---|---|---|
| 平均頻譜 band | 0.883~0.945 | 0.772~0.944 | **重疊，不可用** |
| chroma（音高類別分布） | 0.933~0.993 | 0.911~0.952 | **重疊，不可用** |

chroma 是為了「丟掉這些曲子共用的音色、保留它們不同的和聲」而加的，區間確實更緊，
**但仍然重疊**。14 秒視窗下兩者都無法判定兩個畫面是否同曲。

**而離線自檢一路都是通過的**——因為它比的是合成純音，本來就容易分。
**自檢必須跟真實訊號一樣難，否則它什麼都沒驗證。**

**結論：這條路現在是多餘的**——它要回答的問題已由記憶體讀取精確解決，且便宜得多。
`fd2_audio_probe.py` 定位為「擷取與時序同步的載具」，模組 STATUS 已照此寫明。
若未來要復活識別，該換的是方法（涵蓋完整循環的視窗長度、或直接與 `FDMUS_NNN` 逐曲比對），
不是門檻值。

### 字模表稽核（離線，`glyph_map.json` 1825 筆）

「精校」可機械化的部分：**10 個字被兩個不同 glyph id 對映**——
`．`(347/585)、`庫`(423/1614)、`查`(468/1041)、`一`(487/1813)、`：`(913/1366)、
`營`(1035/1256)、`義`(1070/1167)、`、`(1188/1507)、`端`(1189/1581)、`癒`(1274/1709)。

重複本身**不等於錯誤**（字型可能真的有兩個字模對到同一個字），但這正是文件記錄過的
那類 bug 的形狀（557/560 曾被誤標，查明後是「值」「下」）。
**這給出一份 10 項的具體待目視確認清單，取代「校對 30 章」這個量級的描述。**

---

## 2026-09-03 續六：**反向驗證**（使用者要求）—— 找到 1 個守衛漏洞、3 個崩潰路徑

前面幾輪一直在用「正向」方式驗證工具（有沒有給出預期答案）。使用者要求**反向驗證**：
證明這套裝置**在該失敗時真的會失敗**。做了兩件事，兩件都抓到東西。

### A. 陽性對照：ch06 的四格全陰性，到底是「沒觸發」還是「裝置瞎了」？

ch06 的 2×2（mapper on/off × 送鍵 window/xtest）四格全部「無反應」。
**但那個測試沒有陽性對照**——全陰性同樣可能代表這套裝置根本偵測不到任何觸發。

補做：把 **ch02 已知會觸發的 `Shift+F1`** 放進**完全相同的四格**跑。

| mapper | 送鍵模式 | ch02（已知會觸發） |
|---|---|---|
| off | window | ✅ GATE FIRED (1.97%) |
| off | xtest | ✅ GATE FIRED (1.97%) |
| on | window | ✅ GATE FIRED (1.97%) |
| on | xtest | ✅ GATE FIRED (1.98%) |

**4/4 都偵測到** → 裝置不瞎，**ch06 的全陰性結果可信**。

### B. 故障注入：故意餵一個錯的 delta，工具會不會拒絕？

**第一次注入的結果證明守衛不夠**：錯誤 delta 讀到 `raw=00000000` → `u8=0` →
**「track 0」是完全合法的曲號，直接通過了 `<=20` 的範圍檢查**。

也就是說，先前那次真實事故（讀到 250）**只是剛好超出範圍才被抓到**；
一個讀到零的錯誤位址會靜靜地矇混過去。

**修法**：範圍檢查之外，再要求**變數自身的位元組簽章**——
正確的讀值恆為 `NN 05 00 00 00 00 00 00 00 fb ff ff ff fb ff ff`，只有 `NN` 是曲號。

**修完後重測，連續兩次一致**：

| | 結果 |
|---|---|
| 注入錯誤 delta | **`INVALID_SIGNATURE`（拒絕）** |
| 同一次執行的對照組（完整掃描） | **10（正確）** |

對照組正確，代表守衛不是「把全部都拒絕」這種假通過。

### C. 反向驗證順帶抓出的 3 個崩潰路徑（全是同一個形狀）

注入測試跑不起來的過程本身暴露了一連串 bug：
`resume`、`debugger-status`、以及讀取本身，**三個外部呼叫各自逾時後都會拋出例外，
把原本應該「乾淨回報失敗」的情況變成整個 scenario 崩掉**——
也就是**負責回報失敗的處理器自己失敗了**。

逐個補了兩次之後改成一次解決：新增 `_run_soft()`，
這個 step 裡所有外部呼叫一律不得向上拋。

### D. 附帶：`NO_DEBUGGER` 這個狀態

Alt+Pause 是間歇性會掉的（本專案長期未解的輸入可靠性問題）。
現在讀取前會**確認 debugger TUI 真的起來**（最多重試 3 次），
起不來就回報 `NO_DEBUGGER` 並**明確標註「這不是一個 null 結果」**——
因為「沒讀到」與「讀到沒有」是完全不同的兩件事，
而注入測試就曾經因為兩者被混為一談而白跑了兩輪。

### 回歸

`--all --jobs 3` **16/16 PASS**、port 回歸 **21/21**、audio selftest **11/11**、環境零殘留。

---

## 2026-09-03(續)全工具多重驗證(`tools/verify_all_tools.py`)

使用者要求「針對所有工具進行全面多重驗證,必須詳細驗證確保功能完整及正確」。
`tools/` 底下有 91 個 `.py` + 12 個 `.sh`,過去從來沒有整體被檢查過一次。
新建 `tools/verify_all_tools.py`,把「一支工具還能不能用」拆成 10 個獨立層,
每層各自出一份判決表(`--layer` 可單選,`--json` 出機器可讀報告)。

### 為什麼要分層

因為「壞掉」在本專案有好幾種完全不同的長相,混在一起就會互相掩蓋:

| 層 | 檢查什麼 | 抓到的真實問題 |
|---|---|---|
| `syntax` | `.py` 能 parse、`.sh` 能過 `bash -n` **且不是 CRLF** | **6 支 shell 工具在 Linux bash 下完全無法執行** |
| `structure` | module level 有沒有直接做事(決定下一層能不能 import) | 41 支 import 即執行,故意不 import |
| `imports` | 真的 import 一次(隔離 cwd + timeout) | — |
| `deps` | 不能 import 的,至少靜態解析它 import 的模組存不存在 | — |
| `cli` | 有 argparse 的跑 `--help` | — |
| `invoke` | 沒有 argparse 的(65 支,過去零執行覆蓋)空目錄無參數執行 | `font_grid.py` 直接 IndexError;**`export_sfx.py` 把已刪除的 `remake/` 樹長回來** |
| `env` | 每支工具的第三方相依在 Windows python / WSL python3 各自能不能滿足 | **25 支只能在 Windows python 跑**(WSL 沒有 PIL/numpy/capstone/torch) |
| `refs` | 路徑字面值是否指向已不存在的樹,並區分「會開啟」與「只是提到」 | 3 支開啟 `remake/` 下的檔 |
| `tests` | 所有 `test_*.py` + `test_*.sh`(shell 測試走 WSL) | 3 個測試套件失敗 |
| `selftest` | 有 `--selftest` / `selftest` 子命令的工具 | — |

### 修掉的東西

1. **6 支 `.sh` 是 CRLF,Linux bash 直接 syntax error**(`export_fm` / `export_mt32` /
   `export_music_ogg` / `extract_fd2_video_frame` / `docker/fd2-dosbox-screenshot` /
   `docker/fd2-ida-entrypoint`)。根因有兩層:`.gitattributes` 的 pattern 寫成
   `tools/*.sh` **不遞迴**,`tools/docker/` 兩支從來沒被涵蓋;另外 4 支雖然有規則,
   但檔案是規則加入(2026-08-24)之前 checkout 的,index 是 LF 而 working tree 還是
   CRLF,規則對它們從未生效。pattern 放寬成 `*.sh` + 重新 checkout,現在 WSL 下
   12/12 全過。
   **注意:Git Bash 的 `bash -n` 會接受 CRLF 腳本**,所以在 Windows 端手動掃一遍
   會得到「全部正常」的假結果——本次就先踩過這個假 PASS,是把腳本以二進位餵給
   真正的 bash 才顯形的。
2. **`export_sfx.py` 兩個 bug**:輸入路徑寫成 `extracted/FDOTHER/`(實際是
   `extracted/raw/FDOTHER/`),所以用預設參數從來沒跑起來過;修好之後它又用
   `__file__` 相對路徑把 13 個 WAV 寫進 `remake/assets/sfx`,**把已依使用者指示刪除
   的 remake/ 樹重新建立**(已刪除,輸出改到 `extracted/sfx`)。
   `invoke` 層因此加了 worktree 前後指紋比對,把任何工作區變動歸屬到剛剛跑的那支工具。
3. **`font_grid.py`** 無參數執行時 `argv[1]` IndexError,改成印用法。
4. **3 個測試套件的失敗全部來自 remake/ 移除**,不是迴歸:`test_fd2save`(2)、
   `test_gen_campaign`(1)、`test_extract_event_id_groups`(import 就爆)。
   改成帶理由的 `skipTest`,讓真正的迴歸不會被永久性缺口蓋掉。現在 11/11 全過
   (含 6 個標明理由的 skip)。

### 兩份 `docs/data/` 產物與自己的產生工具已不同步

這是本輪最有價值的發現,而且是**用工具重跑一次、跟已 commit 的檔案逐欄比對**才看見的:

- **`command_labels.json`:40 筆裡有 5 筆與重跑結果不同。** commit `a1851a76` 修好
  glyph_map 的 751 筆錯位之後,只重生了 `remake/assets/data/` 底下那一份,`docs/data/`
  這份留在修正前的舊值(id17 魔刃術 / id18 魔鎧術 / id19 風行術 / id26 毒擊術);
  remake/ 於 2026-09-02 移除後,修正過的那份也一起消失了。已用現行 glyph_map 重生,
  40 筆裡 39 筆與工具輸出逐字元一致,唯一例外 id9 是有理由的人工值
  (glyph 181 的點陣全零,raw decode 會解成空白),連同理由寫進檔案的
  `manual_overrides` 欄位。
- **`unicode_to_glyph.json`:1812 筆裡有 751 筆索引錯位。** 同一個根因——
  `a1851a76` 之後沒有重生。錯位分佈與該 commit 自述的損壞完全對上:
  722 筆 +1(對應「443-1168 這 725 筆整體 offset 1」)、16 筆 +4 與 5 筆 +3
  (對應「423-441 這 19 筆 offset 3-4」)、6 筆零散值(對應「418-422/1163/1198」),
  範圍 418..1198。用 `encode_text.py revtable` 重生後與 glyph_map 完全互為反表
  (不一致 0 筆),另外補回 2 個原本整個漏掉的字(掌、擴)。
  **這張表有真正的消費者**(`tools/encode_text.py` 的中文化重打流程),所以錯位不是
  純文件問題。

### `encode_text.py roundtrip` 不能當作 glyph_map 正確性的證據

驗證上面那份反向表時順手做了故障注入,結果推翻了一個看起來很合理的前提:

把 glyph 500-599 的值整段輪轉一格,`decode_story_text` 的劇情文字明顯壞掉
(「很快就到了。」→「很快就到了極」、「帶著我」→「帶著們」),
**但 35 個 FDTXT 資源的 roundtrip 仍然全數回報一致(35/35)。**

原因是它用同一份 glyph_map 同時建解碼表與編碼表,「解碼→再編碼→再解碼」這個恆等式
在任何**自洽**的表上都成立,包含錯的表。它證明的是可逆性,不是正確性。
(第一次注入我還打錯了目標——改的是 `unicode_to_glyph.json`,而 roundtrip 根本不讀
那個檔;「注入沒反應」當下看起來像「檢查是瞎的」,實際上是**注入沒生效**。
先確認注入真的改到被檢查的東西,再談結論。)
已把這段寫進 `encode_text.py` 的 docstring,避免以後有人引用「roundtrip 35/35」。

### 舊版 EXE 的三支工具:gate 是對的,而且是必要的

`extract_event_id_groups.py` / `extract_native_field_event_rules.py` /
`extract_native_treasure_event_rules.py` 都對 FD2.EXE 做身分檢查,而釘的是已遺失的
**舊版**(357074 B)。使用者手上只有新版(509158 B),所以三支都跑不起來。

把 gate 換成新版雜湊強行執行(只在 scratchpad,未進 repo),結果證明這些 gate
不能放寬:treasure 表的物品編號從 `[29,43,51,61,71]` 變成 `[54,1,0,0,199]`,
field 規則少掉一整條 event_id 62。也就是**舊版位址在新版 EXE 上指到別的東西**,
這與 memory `fd2-old-new-exe-address-instability` 一致,並把它從「不是常數 delta」
推進到「會安靜地產生看起來合法的錯資料」。

連帶影響:`fd2save.load_join_constructor_table()` 依賴的
`remake/assets/data/native_join_constructor.json` 同時踩到兩件事(檔案隨 remake/ 消失、
且是舊版位址抽出的),**不從 git 歷史還原**,改成丟出講清楚原因的錯誤;
兩條相關測試改 skip。要復原必須先在新版 EXE 上重新錨定 JOIN 表位址。

### 功能面真的跑過的部分(不只是「能啟動」)

- `unpack_dat.py`:10 個容器全部重新解包,**970/970 個 sub-resource 與已 commit 的
  `extracted/raw/` 逐位元組相同**。
- `hash_fd2_reference.py`:13 個原版檔案的 size/md5/sha256 **13/13 與
  `docs/data/fd2-reference-files.json` 完全吻合**——同時也再確認手上這份就是新版基準。
- `dump_exe_tables.py`:錨定特徵全部對上新版、內建的數值自驗(對照青衫攻略字面值)
  全數通過、而且 Windows 與 WSL 兩邊產出的 10 個 JSON 在正規化換行後**逐位元組相同**。
  (它在 Windows console 會因 cp950 印不出 ✓ 而 UnicodeEncodeError——是 console 的問題
  不是工具的問題,harness 因此統一給子行程 `PYTHONIOENCODING=utf-8`。)
- `extract_all.py`:end-to-end 跑完,33/33 地圖、1005 個 sub-resource、124 張圖、
  136 個頭像、15 首 MIDI、1824 字模 atlas;各項數字與各容器單獨解包的結果互相吻合。
- `dump_native_ai_modes.py`:輸出與 `docs/data/fdfield_native_ai_modes.json` 除了
  `--source` provenance 區塊(那是選用參數)之外完全相同。
- 其餘 decoder(`decode_ani/lmi/figani/fdicon/sprite/dato/image/text/story_text`、
  `dump_remap`、`render_map`、`render_story`、`parse_field`、`extract_maps`、
  `font_grid`、`dump_terrain_table`、`extract_native_unit_tables`、`le_xref`)
  逐一用真實輸入跑過,輸出內容合理。

### harness 自己的反向驗證(19 項)

`python tools/verify_all_tools.py --selftest` 在暫存目錄裡放一組**故意壞掉的**假工具,
要求 harness 對每一種故障都判 FAIL,同時放一組**同組態的陽性對照**要求判 PASS。
建這支工具的過程中,它的對照組抓到了它自己的兩個 bug:

1. **`bash -n` 拿到的是 Windows 路徑**——`good.sh` 對照組先失敗才發現。
2. **改用 stdin 之後,Windows 的 text-mode stdin 把 `\n` 換成 `\r\n`**,於是 12 支
   `.sh` 全部被誤判成 CRLF 壞檔。這個假失敗一開始沒被對照組擋下來,因為當時的
   `good.sh` 只有 `echo ok` 一行——**對照組比真實訊號簡單**,CRLF 對它無害。
   把對照組改成含 brace function 與 `for/do/done`(真實腳本用的結構)才成立,
   並補上一個 CRLF 版的配對對照,兩者必須一個 PASS 一個 FAIL。

另外兩個值得記的:`no_guard.py` 這個 fixture 被執行時會寫一個 sentinel 檔,
selftest 斷言**該檔從未出現**——證明 harness 真的「拒絕 import」,而不是
「import 了但剛好沒事」;`writes_outside.py` 則驗證工作區變動能被歸屬到正確的工具。

### 最終數字

`syntax 103/103`、`tests 11/11`(含 6 個標明理由的 skip)、`selftest 2/2`、
harness 自身 `19/19`、port 回歸 `21/21`、audio selftest `11/11`。
全 10 層總計 **PASS 413 / FAIL 3 / WARN 73 / SKIP 126**。

剩下的 3 個 FAIL 全部是同一件事:`audit_postbattle_binding_gates.py`、
`audit_story_script_coverage.py`、`fd2_live_input_helper.py` 開啟的是 `remake/` 底下的
檔案。它們不是壞掉,是**沒有作用對象**;已在各自 docstring 開頭標明狀態,
並且不要為了讓它們跑起來而復原 remake/。同類的 `apply_hd_assets.py`、
`apply_hd_composite.py`、`story_to_script.py`、`gen_campaign.py` 也一併標註
(後兩支的預設輸出目錄在 remake/ 之下,執行會把該樹長回來)。

### 追加:同一個換行問題,`.py` 側更嚴重(64/91)

修完 6 支 `.sh` 之後回頭掃 `.py`,發現**同一個根因影響範圍大得多**:
`tools/` 底下 91 支 Python 有 82 支帶 shebang 且已設 executable bit,
其中 **56 支的 shebang 行以 CR 結尾**,在 WSL 下直接執行會得到:

```
env: 'python3\r': No such file or directory
```

也就是這 56 支「可執行檔」其實一支都不能直接執行,只有寫成 `python3 tools/x.py`
才會動。這件事之所以能長期潛伏,是因為**每一種現有檢查都看不到它**:
Python 直譯器本身完全接受 CRLF、`ast.parse` 過、`--help` 過、單元測試也過——
壞的只有 shebang 那一行。

`.gitattributes` 加上 `*.py text eol=lf` 並重新 checkout 後,
82/82 exec+shebang 工具在 WSL 下直接執行皆正常(以 `./tools/fd2save.py --help`
與 `./tools/unpack_dat.py` 實測)。

harness 的 `structure` 層補上這個檢查(放這裡而不是 `syntax`,因為檔案在語法上
完全有效)。加上之後 selftest 立刻抓到 harness 自己的一個問題:
它寫 fixture 時用預設 newline,在 Windows 上一律寫成 CRLF,於是**陽性對照
`good_tool.py` 自己就踩了這個新檢查**——fixture 改成明確 `newline=""`,
只有 `crlf_shebang.py` 這個故障注入 fixture 才是 CRLF。selftest 20/20。

### 追加 2:移除 12 支 remake 專用工具(使用者指示)

使用者問「原先供 remake 的工具還有用嗎?如果沒用就移除吧」。判準定為
**每一條程式路徑都需要 `remake/` 存在才有意義**才移除;只要有一半是從原版抽資料的就保留。

**先把知識落地再刪。** `gen_campaign.py` 裡夾帶三張**原版反組譯結論**,其中
`BGM_BATTLE_TABLE` 與 `MV_BY_CLASS` 在 `docs/` 底下是 0 筆引用——直接刪會連知識一起丟掉。
已抽成 `docs/data/native_chapter_tables.json`(含出處與限制):

| 表 | 筆數 | 出處 | 交叉驗證 |
|---|---|---|---|
| 戰鬥 BGM 章節表 | 30 | `0x51e63` | **與 doc12 用 Ghidra 獨立 dump 的 30 bytes 逐項相符** |
| 秘密商店 gate | 23 | `0x6238d` record `+1`/`+2` | doc58 已有同一份表 |
| 城鎮 variant | 23 | `0x6238d` record byte 0 | doc42/doc91 |

`MV_BY_CLASS`／`AP_HP_RATIO_*` **刻意不保留**——該檔自己就註明「這段是近似值不是 RE 結果」,
是為了填 remake 缺資料而推的比例,留著只會被後人誤當成原版數值。

**移除清單(12 支)**:`apply_hd_assets.py`、`apply_hd_composite.py`、
`realesrgan_batch_tilesets.py`、`audit_postbattle_binding_gates.py`、
`audit_story_script_coverage.py`、`gen_campaign.py`＋`test_gen_campaign.py`、
`story_to_script.py`、`fd2_live_input_helper.py`＋`.sh`、`fd2_dual_verify.py`、
`export_runtime_roster.py`。

**兩支原本要刪、查了引用鏈之後保留**:
- `export_story_index_map.py` —— `export_command_labels.py` 真的 `from export_story_index_map
  import parse_fdtxt_strings`,而後者正是今天重生 `command_labels.json` 的工具。刪了會斷。
- `dosbox_diff_harness.py`／`.sh` —— 比對的另一半(remake)沒了,但原版側的
  raw 320×200 擷取與 `lock_pulse_phase` 是可用技術,且 doc98 前面幾節都在引用。
  功能已被 `fd2_original_verify.py` ＋ `dosbox_harness.sh` 取代,標記為待淘汰而非刪除。

`fd2_dual_verify.py` 是連帶移除:它 `import fd2_live_input_helper as remake_tool`,
本身就是 remake-vs-原版雙邊比對器,單獨留著不會動。

**移除後全 10 層重跑:FAIL 從 3 降到 0**(PASS 367／WARN 64／SKIP 117),
`refs` 層 90/90 全過。並確認被保留的相依鏈仍完好:`export_command_labels.py` 重跑後
40 筆裡仍只有 command_id 9(已記錄的手工值)與檔案不同。

---

## 2026-09-03(續三)用新版 EXE 複驗舊版抽出的資料(`verify_native_tables_new_edition.py`)

**要回答的問題不是「讓那四支工具能跑」**(它們產出的資料早已 commit,而且沒有任何活著的
工具在讀),**而是「`25-battle-event-system.md` 的結論對手上這份 EXE 成不成立」**。
那份 2576 行文件的證據基底,是從已遺失的 357074-byte 舊版抽出來的。

走的是便宜的那條路:**只驗數值,不遷移工具程式碼。**

### 結果:三層裡兩層落地

| 層 | 結果 | 內容 |
|---|---|---|
| L1 寶物物品表 | **PASS** | `[29,43,51,61,71]` 在新版 linear `0x4ee96` **唯一命中**(舊版 `0x5274e`) |
| L2 event handler 跳表 | **PASS** | 見下,這層最強 |
| L3 重抽 spawn group | **INCONCLUSIVE** | 有具體阻礙,誠實標示,不硬給答案 |

### L2:跳表位址根本沒變,90 個 handler 整批平移 +0x356

`0x51b19` 起有 **120 筆連續 fixup**——正好是文件記載的「30 章表 + 90 筆 event 表」,
而且 `0x51b19`/`0x51b91` 這兩個 linear 位址在新舊版**相同**。
90 筆 handler 指標與已 commit 的值**全部相差 exactly `+0x356`,90/90 只有一個 delta**。

一個位址吻合可能是巧合,90 個位址以同一個位移吻合不是。這證明:**這 90 個 handler 在新版
是同一批函式、同順序、同大小,只是整體搬了位置。**

> 這也修正了本專案先前「舊版位址不會沿用」的印象:更精確的說法是
> **不同區段有各自的位移,但區段內是常數**——handler 區 `+0x356`、
> 寶物資料表 `-0x38b8`、跳表本身 `0`。

**先前找不到跳表是我漏了一層**:跳表項目在分頁原始資料裡不是絕對位址,真正的目標存在
**LE fixup record** 裡。用 raw dword 掃描永遠掃不到,必須先建 fixup map。

### L3 做不到,而且原因具體

要在新版重抽 spawn group,得先能正確重建 object 0 的 linear code image,而目前兩種
候選映射反組譯出來都不自洽:`0x14818+0x356` 給出乾淨的 prologue
(`push ebx/esi/edi/ebp`),但 `0x10c50+0x356`、`0x2ff01+0x356` 是垃圾;
`0x2ff01` **不加位移**反而像合法程式碼;而且解出的絕對運算元是 `[0x2754]`、`[0x1a83]`
這種不可能的小位址(真實全域在 `0x53xxx`)。page map 已確認是 identity(1..71),
不是頁序問題。

**實際跑過一次,得到 0 筆 spawn。那是映射沒對的產物,不是「新版沒有 spawn」這個發現——
沒把它寫成結論,是這一輪最重要的事。**

### 順帶抓到 `le_xref.parse_le` 的真實 bug

`parse_le` 把 LE header 的 data-pages offset 原樣回傳,而**每一個使用者**
(`page_file()`、`extract_event_id_groups.load_code()`)都當成檔案絕對位置用。
它其實是**相對 LE header** 的,而這份新版的 LE header 在 `0x27acc`。

判準不是規格書而是實測:`dump_exe_tables.py` 已在新版逐位元組驗證通過的三個 anchor
(item `@0x792c0`、shop `@0x7b3a4`、spell `@0x7aa11`)**全部落在 `le+data_off` 區內、
全部落在 `data_off` 區外**。

`le_xref.py` 本身**這輪沒有改**——動它會牽動整個 LE 工具家族,應該跟 L3 一起做,
不適合夾在這輪裡。

### 反向驗證(7 項)

每一層都要在被注入故障時失敗、未動過的輸入要通過、單 byte 特徵要回報
`INCONCLUSIVE` 而不是隨便挑一個命中;**配對對照**是把 90 個 handler 一起加同一個
常數,要求**仍然 PASS**——證明位移檢查抓的是「不一致」,而不是「跟記載的值不同」。

### 續完(同一輪稍後):三層全部落地,doc25 的結論**已對新版逐筆複驗**

上面寫「L3 做不到」是**當下狀態,不是結論**——把分頁映射解對之後就通了。

**關鍵在分頁區起點,前兩種寫法都錯:**

| 寫法 | 值 | 結果 |
|---|---|---|
| `data_off` 當絕對值(le_xref 既有使用者) | `0x10e00` | 錯 |
| `le + data_off`(LE 規格字面解讀) | `0x388cc` | 也錯 |
| **由檔尾回推 `(pages-1)*page_size + last_page_size`** | **`0x36014`** | **正確** |

判準是可否證的:用它映射時,寶物物品表落在 linear **`0x5274e`——與舊版記載的
`item_table_address` 完全相同**;前兩種分別給出 `0x4ee96` 與落在分頁區外,
對不上任何已知值。

**最終結果:45 筆 spawn 記錄逐筆驗證,44 筆完全吻合、1 筆是編碼差異。**

驗的不是「重跑一次得到同樣輸出」(那可以靠同一個 bug 兩邊一致而通過),而是更難造假的:
把每筆記錄的呼叫點位址 +0x356,要求新版該處確實是轉移指令、目標是預期的 spawn 函式、
且前置 push 的立即數等於記錄的 group(staging 則是三個引數 group/y/x 全部吻合)。

唯一一筆差異在 **event 63 的第二筆 staging spawn**(`0x35c3b`):
新版是 **`jmp` 而不是 `call`**——tail-call 最佳化,語意完全相同,
而且前置引數 `[2, 27, 15]` 與記錄的 (group 2, y 27, x 15) **逐項吻合**。
抽取器只認 `call`,所以重跑時會少這一筆;這是 1995→1998 重建的編碼差異,**不是資料差異**。
(順帶說明了為何 `test_event63_preserves_both_staging_calls` 這條測試當初要特別寫。)

**位移地圖(分區段常數,不是全域常數):**

| 區段 | 位移 |
|---|---|
| event handler 本體(`0x34xxx`-`0x35xxx`) | `+0x356` |
| `spawn_group`(`0x10b4e`)/`spawn_group_with_intro`(`0x32999`) | `0` |
| event_id 跳表(`0x51b91`)、寶物物品表(`0x5274e`) | `0` |
| staging helper(`0x35822`) | `+0x356` |

**結論:`docs/data/event_id_groups.json` 與 `native_treasure_event_rules.json`
描述的就是使用者手上這份新版遊戲**,doc25 建立在它們之上的結論成立。

**兩個踩過的坑,都是「看起來像發現、其實是自己的 bug」:**
1. 把 `SPAWN_FNS`(`0x10b4e`/`0x32999`)也 `+0x356` → 抽到 **0 筆 spawn**。
   差一點寫成「新版沒有 spawn」。
2. capstone 對小立即數印的是 `push 3` 而非 `push 0x3`,只認 `"0x"` 開頭
   → 所有 group 編號都讀成 `None`,45 筆裡 38 筆被誤判成對不上。
   兩次都是**先看註記細節、發現 `target_ok=True` 而 `group_ok=False` 這種內部矛盾**
   才沒有把它當成資料問題。

反向驗證加到 **9 項**,新增兩項針對 L3:改一筆 spawn 的 group 引數、改一筆呼叫點位址,
都必須判 FAIL。

### 剩下要做的

L3 已完成,doc25 的結論**已確認對新版成立**。剩下的是**選做**的工程工作:
把 `extract_event_id_groups.py` 等四支工具真正遷移到新版(分頁起點改由檔尾回推、
handler 區段常數 `+0x356`、`SPAWN_FNS` 不動),以及修 `le_xref.parse_le` 的
`data_off`——後者會牽動整個 LE 工具家族,要一併回歸測試。
沒有人在等這些產出,所以優先度低;真正的問題(資料能不能信)已經回答了。
