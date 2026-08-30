# 48 — dosbox-x(heavy debugger)建置與操作

> 目的:doc 47 §5 留下的未解——`0x627d8` acting 資源表的填表點(表在 BSS,填表位址靠暫存器基底寫入,
> 靜態難尋)——建議下一輪用「dosbox 記憶體 dump 反查來源」(rulebook 64 第三條路)。原版 `DOSBox.exe`
> (0.74)不含 debugger,本篇建置支援 heavy debugger 的 **dosbox-x**,並記錄如何用它 dump 執行期記憶體。

> **2026-08-23 更新**:§1-7 記錄的 **Docker 建置方案已停用**(Docker Desktop 因無法修復的
> `AF_UNIX` bug 已於 2026-08-16 整個移除,見 `project_docker_desktop_af_unix_broken` 記憶)。
> 自續二十一(2026-08-18)起,所有 live 驗證輪次都改用 **WSL2 native build**(同一顆 dosbox-x
> 原始碼直接在 `wsl -d Ubuntu` 裡編譯執行,不經過容器),累積了 30+ 輪獨立 session 的實戰經驗。
> **§8 是這條 WSL2-native 路線的完整稽核總結與目前已驗證最穩定的啟動 recipe,新 session 應該
> 直接看 §8,不需要重建 §1-7 的 Docker 環境**(§1-7 保留作為 debugger 指令集/`MEMDUMPBIN`
> 語法等仍然通用的參考,只是「建置」步驟本身已經是歷史記錄)。

## 1. 為什麼是 dosbox-x 不是原版 DOSBox

原版 DOSBox 官方 build 不含互動式 debugger(需自行編譯 `--enable-debug` 的特殊 build,且專案已停止更新)。
**dosbox-x**(joncampbell123 維護的 active fork)把 `--enable-debug=heavy` 直接做成建置腳本選項,
底層沿用同一顆 ncurses debugger(命令集與原版 DOSBox debugger 相容),適合拿來對 FD2 這種 16-bit
protected-mode(DOS4GW)老遊戲做記憶體 dump。

## 2. 建置

Dockerfile:[`docker/dosbox-x/Dockerfile`](../../docker/dosbox-x/Dockerfile)

```dockerfile
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
        automake autoconf libtool pkg-config \
        gcc g++ make nasm \
        libncurses-dev \
        libsdl-net1.2-dev libsdl2-net-dev libsdl2-dev \
        libpcap-dev libslirp-dev \
        fluidsynth libfluidsynth-dev \
        libavdevice-dev libavformat-dev libavcodec-dev libswscale-dev \
        libfreetype-dev libxkbfile-dev libxrandr-dev \
        libpng-dev zlib1g-dev \
        xvfb x11-apps imagemagick tmux xdotool \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN curl -sL -o dosbox-x.tar.gz \
        https://github.com/joncampbell123/dosbox-x/archive/0d7b272b690351a92405ee1d672152ee134da35b.tar.gz \
    && tar xzf dosbox-x.tar.gz \
    && mv dosbox-x-0d7b272b690351a92405ee1d672152ee134da35b dosbox-x \
    && rm dosbox-x.tar.gz

WORKDIR /src/dosbox-x
RUN ./build-debug-sdl2 && make install

WORKDIR /game
ENV SDL_VIDEODRIVER=x11 DISPLAY=:70
CMD ["dosbox-x"]
```

```
docker build -t fd2-dosbox-x docker/dosbox-x
```

- 套件清單抄自 dosbox-x 官方 `BUILD.md`「To compile DOSBox-X in Ubuntu」段(逐一在 `debian:bookworm-slim`
  驗證過皆存在),另加 `libsdl2-dev`(讓建置腳本偵測到系統 `sdl2-config`,跳過內建重編 SDL2,加速建置)、
  `xvfb`/`x11-apps`/`imagemagick`/`xdotool`(headless 開圖 + 截圖 + 送鍵,沿用 dq3 專案已驗證的
  `tools/dosbox_run.sh` 模式)、`tmux`(驅動 ncurses debugger TUI,見 §4)。
- 來源固定 commit `0d7b272b690351a92405ee1d672152ee134da35b`(2026-07-04 抓的 master HEAD)而非
  `git clone`,理由:①docker build 內 `git clone` 該 repo 曾在此環境實測逾時(repo 含大量歷史
  二進位測試資料,`.git` 遠大於單一 commit 的 tarball);②commit 釘死可重現,不受上游後續 push 影響。
- **`--enable-debug=heavy`**(由 `build-debug-sdl2` 腳本內建呼叫)= `configure.ac` 定義
  `C_DEBUG` + `C_HEAVY_DEBUG`(需要 curses)。這就是啟用 debugger 的唯一開關,查證依據:
  `dosbox-x/configure.ac` 第 1140-1154 行 `AC_ARG_ENABLE(debug, ...)` 區塊。

## 3. 驗證(本輪已實測,非紙上談兵)

| 項目 | 指令 | 結果 |
|---|---|---|
| 版本 | `docker run --rm fd2-dosbox-x dosbox-x --version` | `DOSBox-X version 2026.07.02 SDL2` |
| debugger 編進去 | `strings /usr/bin/dosbox-x \| grep -E '^MEMDUMPBIN$\|^BPLM$\|^DEBUGBOX$'` | 三個字串皆命中(只在 `#if C_DEBUG` 編譯區塊存在,證明 heavy debug 真的編進去) |
| debugger 真的能互動 | Xvfb + tmux 跑 `dosbox-x` + `xdotool key --window <win> alt+Pause` | tmux pane 截到完整 ncurses TUI(Code Overview / Output 視窗 + `I->` 提示字元),見 §4.1 |
| **MEMDUMPBIN 真的能 dump** | debugger 內 `tmux send-keys` 送 `MEMDUMPBIN F000 D186 20` | pane 印出 `DEBUG: Memory dump binary success.`,容器內確認 `MEMDUMP.BIN` 產生,大小 32 bytes(與要求的 0x20 相符) |
| 能跑 FD2 到畫面 | 掛遊戲目錄跑 `FD2.EXE`,Xvfb + `import -window root` 截圖 | `extracted/dosbox_x_verify/fd2_title.png`(序幕過場其中一幀:紅背景剪影 + 機器人臉,證明遊戲圖像正確渲染) |

啟動 FD2(掛載唯讀遊戲目錄,`-c` 疊加 autoexec;實測用的完整指令):

```bash
docker run --rm -e TERM=xterm \
  -v "$PWD/org_game/炎龍騎士團/FLAME2:/game:ro" \
  -v "$PWD/extracted/dosbox_x_verify:/out" \
  fd2-dosbox-x bash -c '
    Xvfb :70 -screen 0 1024x768x24 -ac >/tmp/xvfb.log 2>&1 &
    sleep 2
    export DISPLAY=:70
    mkdir -p /tmp/run && cp -r /game/* /tmp/run/    # 唯讀掛載改複製到可寫目錄,避免 FD2.TMP/存檔寫入失敗
    cd /tmp/run
    tmux new-session -d -s t -x 200 -y 50 \
      "dosbox-x -c \"MOUNT C /tmp/run\" -c \"C:\" -c \"FD2.EXE\" -c \"EXIT\""
    sleep 8
    import -window root /out/fd2_title.png
  '
```

- 遊戲目錄用 `:ro` 掛載沒問題,但 FD2 執行期會寫 `FD2.TMP` 等暫存檔,直接在唯讀掛載點跑會出錯,
  **實測解法**:掛進容器後先 `cp -r` 到容器內可寫路徑(`/tmp/run`)再從那邊跑 `dosbox-x`。
- 8 秒後截到的是序幕開場動畫的其中一幀而非嚴格的標題選單畫面(該幕約 30 秒,見 doc 46/23);
  要截到真正標題畫面需拉長 `sleep` 或送按鍵跳過(`xdotool key --window ... Return`)略過開場。

## 4. debugger 操作

### 4.1 怎麼進 debugger(本輪實測修正)

- Linux/Mac:**debugger TUI 需要一個真正的 pty**——`tmux new-session` 開的 pane 算數(已實測跑通),
  單純 `dosbox-x &` 丟到 log 檔重導向**不算**(沒有 pty,ncurses 起不來)。
- **實測結果推翻了「預設就會啟動即斷」的預期**:`[log]` 段 `debuggerrun=debugger` 是預設值沒錯,但
  它只決定「debugger 被觸發後的行為模式」,**不代表 dosbox-x 一啟動就自動斷點暫停**——實測 8 秒內
  終端機只印一般 `LOG:` 訊息,直到主動觸發才會切換成 ncurses TUI。
- **實際觸發方式(已驗證)**:熱鍵 `Alt+Pause` 是 SDL 視窗的 mapper shortcut,必須用
  `xdotool key --window <DOSBox 視窗 ID> alt+Pause` 對著 X11 視窗送(不是對 tmux pane 送,tmux 對
  這個熱鍵無效)。送出後,原本印 LOG 的那個 pty 畫面**立刻切換成 ncurses debugger TUI**
  (Code Overview / Data / Output 視窗 + 底部 `I->` 指令列),此時才能用 tmux 對同一個 pane
  send-keys 打 debugger 指令。
- `DEBUGBOX <command> [options]`:DOS shell 內建指令,可放進 `[autoexec]`,啟動指定程式並斷在
  entry point(**本輪未實測**,理論上比等 Alt+Pause 手動觸發更適合「一啟動就要斷」的場景,留待下輪)。

### 4.2 常用指令(節錄自 `README.debugger`)

| 指令 | 用途 |
|---|---|
| `BP <seg> <off>` / `BPM` / `BPLM <offset>` | 中斷點(real mode / protected mode / linear) |
| `BPPM <seg> <off>` | 記憶體變更中斷點(protected mode) |
| `RUN` / `RUNWATCH` | 恢復執行(後者邊跑邊顯示狀態) |
| `MEMDUMP <seg> <off> <bytecount>` | dump 記憶體到 `MEMDUMP.TXT`(文字) |
| **`MEMDUMPBIN <seg> <off> <bytecount>`** | dump 記憶體到 `MEMDUMP.BIN`(binary,我們要的) |
| `C <seg> <off>` / `D <seg> <off>` / `DV <offset>` / `DP <offset>` | 設定 code / data(seg:off / linear / physical)檢視位置 |
| `SR <reg> <value>` | 設定暫存器值 |
| `GDT` / `LDT` / `PAGING` | 傾印 GDT/LDT/分頁表(DOS4GW 保護模式定位必備,見 §5) |
| `F5`(鍵) / `F9`(鍵) / `F10`/`F11`(鍵) | Resume / 設中斷點 / Step over / Step into |

完整指令表見 `README.debugger`(dosbox-x 原始碼根目錄,已抄錄於本文撰寫時的查證過程)。

**參數語法陷阱（2026-07-15 實測）**：三個數字參數用 debugger 的裸十六進位語法，**不可**帶
`0x` 前綴。例如 `MEMDUMPBIN DS 24B2F0 1900` 會產生 `0x1900=6400` bytes；寫成
`... 0x1900` 雖仍印 `Memory dump binary success.`，實際檔案卻是 0 bytes。每次擷取後都要先
`ls -l MEMDUMP.BIN` 驗證大小，再把 dump 當證據。

### 4.3 headless 自動化(本輪已實測跑通,沿用 dq3 專案模式,見 `docs/29-dosbox-oracle.md`)

**雙通道輸入**——這是本輪最重要的釐清,兩者不能混用,且已用真實流程驗證(§3):

1. **X11/xdotool 通道**:遊戲鍵盤輸入(方向鍵、Enter 過場等)**以及**觸發 `Alt+Pause` 進 debugger,
   都是對 Xvfb 上那個 SDL 視窗送事件,用 `xdotool key --window $(xdotool search --name DOSBox) <key>`。
   dq3 專案的 `tools/dosbox_run.sh` 已驗證同一模式,FD2 可直接照搬。
2. **tmux/pty 通道**:**已經進入 debugger TUI 之後**,對著跑 `dosbox-x` 的那個 tmux pane 用
   `tmux send-keys` 打字串指令(如 `MEMDUMPBIN F000 D186 20` + `Enter`)——本輪已實測 `MEMDUMPBIN`
   真的產生檔案(§3)。**進 debugger 前**這個 pane 只是普通 LOG 輸出,tmux 送鍵對遊戲本身無效
   (遊戲鍵盤走 X11,不走 stdin)。

已驗證流程(以本輪實測指令為基礎):

```bash
Xvfb :70 -screen 0 1024x768x24 -ac >/tmp/xvfb.log 2>&1 &
export DISPLAY=:70
tmux new-session -d -s dbg -x 200 -y 50 'dosbox-x -c "MOUNT C /tmp/run" -c "C:" -c "FD2.EXE"'
sleep 4                                            # 等 SDL 視窗建立(有上界)
WIN=$(xdotool search --name DOSBox | head -1)
xdotool key --window "$WIN" alt+Pause              # 觸發:切進 debugger TUI(已驗證)
sleep 2
tmux send-keys -t dbg 'BPLM 0x627d8' Enter          # 中斷點(實際換算見 §5,本輪未對 FD2 實測)
tmux send-keys -t dbg 'RUN' Enter
# ... 等中斷點觸發(有上界;不可無限等,配合 rulebook 35)...
tmux send-keys -t dbg 'MEMDUMPBIN DS 0 0x10000' Enter
tmux capture-pane -t dbg -p > /tmp/debugger_screen.txt   # 佐證目前 TUI 狀態(已驗證會印出結果訊息)
```

`dosbox-x` 若有「設定檔/命令列自動跑一串 debugger 指令」的原生機制(如序列化 debugger script),
**本輪未找到**——`README.debugger` 與 `configure.ac` 都沒有這類選項;`-c` 命令列參數是疊加
`[autoexec]` 的 **DOS shell 指令**(給 `MOUNT`/跑 `.EXE` 用),不會被 debugger 主控台解讀。
所以自動化 debugger 操作目前只能走「xdotool 觸發進 debugger + tmux 送鍵打指令」這條路,
沒有更捷徑的原生批次介面——但這條路本身已完整驗證可行,不是空想。

## 5. 針對 acting 資源表(`0x627d8`)的備註

- FD2 用 **DOS4GW**(Watcom/Rational Systems DOS extender)跑保護模式,`0x627d8` 是**反組譯工具算出來
  的 app 端 linear/flat 位址**(從 EXE 的 LE/LX 影像位移推算),**不是** dosbox-x 模擬器的實體記憶體
  位址,也不等於 `DV`/`DP` 直接可用的位移——兩者中間隔著 DOS4GW 的 GDT/LDT 段描述子與分頁表映射。
  直接對 `0x627d8` 下 `DP`/`MEMDUMPBIN` **極可能对錯位址**。
- **不要用「硬算基底」的方式換算**(如假設某固定 offset)。正確做法:
  1. 中斷點打在**已知會讀寫這張表的 code**(getter `0x4e803`,已在 doc 47 §5 定位),用 `BPLM` 或
     `BP <seg> <off>`(先用 `C`/`GDT`/`LDT` 對照 CS 段基底換算 seg:off)。
  2. 觸發後用暫存器視窗直接讀出**當時的有效位址**(debugger 的 Register/Data 視窗會顯示 CPU 實際
     算出的 seg:off,不必自己反推)。
  3. 以該有效位址為準 `MEMDUMPBIN` 整張表,再用**已知簽章掃描**(FDTXT/FDOTHER/FDICON 等容器已知
     header pattern,或 acting 幀格式的 `[幀數]+每幀{(拍數,N)+N×(單位idx,姿態)}` 結構)反查
     dump 出來的位元組落在哪個資源檔案裡——這比「dump 完再猜位址對應哪個檔案」可靠(rulebook 64
     第三條路:已知輸出反推位置,不要反過來瞎猜)。

## 6. Acting getter：舊 dump 撤回與 ACT99 live provenance（2026-07-15）

**撤回**：早期在非目標 ACT／錯 context 讀得的 `0x207718`、高 ID `0x50..0x99`、74 筆有效資源及
`id−48` 對映，均不得再作為 acting decoder、handler binding 或 map0 的依據。

正確方法是在目標 ACT entry `0158:1C966A` 的 normal-core code breakpoint 停下，讀 stack 的 return
address／id，再讀 getter 已被 loader 修補的 machine bytes。ACT99 的重抓結果：

```text
stack return = 0x1E8348, id = 0x63  -> static handler caller 0x32343
getter       = 0x2047f8, disp32 immediate = 0x2077d8
table[99]    = 0x208493
resource     = 01 06 01 02 02
```

因此 ACT99 是一個 normal frame：`beats=6, slot=2, pose=2`。同一呼叫前後的完整 unit buffer 只有
slot2 改變，Y `42→36`、pose `0→2`，直接證明它是索爾向上六格的演出。

靜態來源為 `FD2.EXE file+0x565d8` 的 **106×u32** offset directory（entry `0..105`，資料位址為
`file+0x53e00+offset`）。getter 的參數就是 direct entry ID，沒有章節 window。ACT100 隨後也在相同
entry breakpoint 命中：return=`0x1E83FA`、id=`0x64`（handler `0x323f5`），resource
`01 0A 01 02 00`；slot2 實際 Y `8→18`、pose=`0`。舊 slot60 結論至此由 live 差分完全推翻。

## 7. BPLM 量化判死 + 對白時刻快照(task_f,2026-07-04)

- **cycles/core 量測**:normal core + cycles=fixed 80000 只比 dynamic 慢 17%(42s vs 36s 到標題),基礎速度可用。
- **BPLM 病態行為量化證實**:同設定下設 3 個 BPLM(0x1366a/0x13185/0x137e6 執行期位址),三者皆有觸發
  (證實王座廳序幕確實呼叫此三函式);但觸發後 RUN 退化——20 次 RUN/4 秒僅推進 1 cycle;刪斷點後同
  session RUN 2 秒 cc 恢復 32 億級。**結論:dosbox-x heavy-debug 下任何 BPLM 存在即讓 RUN 近似單步,
  非 cycles/core 配置問題,此路判死**。副作用:命中時 CS:EIP 卡 real-mode callback(F000:xxxx),
  讀不到命中瞬間暫存器 → unit_idx→槽映射公式、0x13185 精確語意退回純靜態反組譯(低優先)。
- **對白時刻 21 槽快照**:「兒臣索爾」顯示中,cam=(3,20)、索爾(槽2)=(8,21)——鏡頭頂端下一格,與
  畫面「索爾在紅毯上段、王座正下方」吻合;為 task_e 遞減序列(31→27→…)的自然延續。⚠更正(doc55§7影片4幀NCC):(8,21)是【對話開始中途快照】非終點,索爾之後續走到王座前【(8,8)】(此處舊述「walk終點非(8,8)」錯)。
  **⚠再更正(doc47 §11,2026-07-05 RE handler call序列 + 原版截圖驗證)**:(8,21) 不是「中途快照」而是**第一次對話的停位**——handler `STEP×15 → 對話#0(line0索爾晉見) → STEP×13 → 對話#1(line1+父王)`;索爾在 (8,21) 停下播 line0(此時被守衛 (5,21)/(12,21) 左右緊鄰,原版 shot 16-48-19),再走到 **(8,8)** 播其餘。**final=(8,8) 確認正確**(此值一度被誤改成 (8,14),已撤回)。
  而是 ~(8,21) 時對白已開(對白與走位重疊的證據)。
- **slot3=索爾(4,46) 之謎已解**:map32 FDFIELD roster 本就有兩筆索爾(slot2=(8,42) 走入起點、
  slot3=(4,46) path 幕站位),非「多場景混放」異常——roster 順序=槽序再次驗證。

## 8. WSL2-native 環境健檢總結與最終穩定 recipe(2026-08-23)

**背景**:doc58 續二十一起累積 30+ 輪 WSL2/dosbox-x live 驗證,過程中反覆記錄過至少 6 類獨立
環境問題(WSLService deadlock、`/tmp/.X11-unix` 唯讀、Dynamic core 斷點不可靠、`Up` 鍵重複
`Alt+Pause` 後失效、移動確認 Enter 不穩定、`MEMDUMPBIN` upstream bug),但這些記錄散落在
doc58 十幾個不同「續X」小節裡,沒有一份集中、系統性驗證過的總結。本節是一次專門的基礎設施
稽核(不繼續 ch27 RE 進度),目的是把散落的問題逐一重新驗證(不是重述舊記錄),並產出一份
真正可信賴的啟動 recipe。**這次稽核的機器狀態**:使用者已於本輪任務開始前重開機
(`LastBootUpTime`=2026-08-23 17:59:38),所以下面關於「重開機後是否恢復」的測項都是在乾淨
開機狀態下驗證的,不是延續某個已經跑了很久的 session。

### 8.1 WSL2 `WSLService` deadlock——沒有找到根因,Windows Event Log 完全沒有留下任何痕跡

**方法**:`Get-WinEvent`查 `System`/`Application` log(此機器 `System` log 實際回溯到
2026-05-15,循環覆寫、不是每次開機重置),鎖定 `WSLService`/`vmcompute`/`hns`/`Hyper-V` 相關
provider 與訊息關鍵字,涵蓋續三十五(2026-08-21)與續四十九(2026-08-23 早些時候,同一天稍早)
兩次已知發生 deadlock 的時間點附近。

**結果(確定性負面結果,不是沒查到)**:
- `Get-WinEvent -ListProvider *wsl*/*vmcompute*/*hns*/*hcs*/*lxss*` 全部回報「找不到 provider」
  ——這台機器**沒有註冊任何 WSL 專屬的 ETW event log channel**(不是查詢方式錯誤,是這個
  channel 在預設安裝下就不存在,`wsl --debug-shell` 那類進階診斷模式才會產生對應紀錄)。
- `System` log 裡 `Service Control Manager` provider 的全部 Error 等級事件(近 2 萬筆事件裡篩出
  8 筆),逐筆核對**沒有一筆與 WSL/vmcompute/hns 有關**(全部是 Windows Update、Defender、
  `Claude` service 這類無關項目)。續三十五/續四十九兩次 deadlock 發生的時間點附近,`System` log
  完全沒有任何 Error/Warning 級別的 Hyper-V 或服務相關記錄。
- **結論**:`WSLService` 這個 deadlock 是一次**真正的掛起(hang),不是崩潰(crash)**——服務
  進程本身沒有異常終止、沒有觸發任何看門狗或錯誤回報機制,SCM 層級一路顯示`Running`,所以
  完全沒有東西可以被記錄下來。這解釋了為什麼續三十五/續四十九兩輪都無法從「查記錄」找到任何
  線索——**不是還沒查到,是這種故障模式在預設 Windows 事件記錄設定下structurally不可能留下
  痕跡**。要真正診斷根因,需要使用者在下次 deadlock 發生的當下(不是事後)用系統管理員權限跑
  `wsl --debug-shell`或Hyper-V的`Get-VM`/`vmcompute.exe`附加除錯器,這超出目前非管理員權限
  session 能做的範圍。

**記憶體使用量假說**:這台機器 32GB RAM、16 邏輯核心,先前**沒有 `.wslconfig`**,代表 WSL2
VM 預設可用到 host 記憶體的 50%(約 15.7GB)。沒有直接證據(event log 空白)證實 deadlock
跟記憶體壓力有關,但作為「降低發生機率」的預防性措施(不是已證實的根因修復),已在
`C:\Users\kg701\.wslconfig` 新增:

```ini
[wsl2]
memory=8GB
processors=4
swap=4GB
vmIdleTimeout=60000
```

**已驗證**:`wsl --shutdown` 套用新設定後,`wsl -d Ubuntu -- free -h`/`nproc` 確認實際生效
(7.8GiB 可用記憶體、4 核心、4GB swap);套用後重新完整跑一輪 dosbox-x 啟動+按鍵測試
(見 §8.3),**沒有發現任何效能倒退或新的不穩定**,可以放心保留這個設定。

**給下一輪最有行動力的建議(取代「沒有根因就無法行動」的無力感)**:
1. **不要等 deadlock 發生才處理**——與其在故障後嘗試各種非管理員權限的修復手段(續三十五/
   續四十九已經證實這些手段全部無效,不用再重複測試同一組),更務實的做法是**每一輪 live
   驗證結束時都主動 `wsl --shutdown` 一次**(不是只在出問題時才做),把 WSL2 VM 的存活時間
   控制在單次任務範圍內,不讓它跨 session 長時間掛著——這雖然無法保證deadlock 不會發生
   (根因未知),但顯著縮短了它有機會發生的時間窗口。
2. 如果 deadlock 發生,**第一時間就應該請使用者用系統管理員權限處理**(`wsl --shutdown`或
   重開機),不要在非管理員權限下反覆重試殭屍 process 清理或 `Restart-Service`——續三十五
   跟續四十九兩輪獨立驗證過這些手段 100% 無效,不是「這次可能運氣好」的問題。
3. 如果使用者未來想真正抓到根因,需要在**deadlock 正在發生的當下**(不是重開機恢復之後)
   用系統管理員權限跑進階診斷(`wsl --debug-shell`、附加 `vmcompute.exe`/`wslservice.exe`
   除錯器、或啟用 WSL 的 ETW tracing),這件事本身超出一般 session 的權限與時間範圍,建議
   當作一個獨立、需要使用者在場配合的專門任務,不要期待某次 live 驗證輪次能順便解決。

### 8.1.1 2026-08-29 外部資料調查更新——修正「Restart-Service 已證實無效」的適用範圍

`ch27win`/`ch27win2` 兩輪連續被同一個 deadlock 擋住之後,派了一次專門的網路調查(英文+中文
來源,含 `microsoft/WSL` GitHub issues、CSDN、Zhihu、PTT)。結論分三點:

1. **這是已知的一類 bug,不是本機獨有現象**。`microsoft/WSL` repo 上有多筆高度吻合的 issue,
   例如 [#9534](https://github.com/microsoft/WSL/issues/9534)、
   [#8529](https://github.com/microsoft/WSL/issues/8529)(明確指出跟**睡眠/喚醒循環**有關,
   只有重開機能解)、[#9855](https://github.com/microsoft/WSL/issues/9855)(睡眠/休眠喚醒後
   `wsl --shutdown` 本身也卡死,幾乎與本專案症狀一致)、
   [#40994](https://github.com/microsoft/wsl/issues/40994)(分析指向虛擬化層的 handle
   deadlock 卡住 WSLService 無法 unmount)、
   [#8628](https://github.com/microsoft/WSL/issues/8628)(以系統管理員權限單獨砍
   `wslservice.exe` 是唯一解法)。中文來源(CSDN等)多半只是「以管理員重開/重開機」這類通用
   排除法,沒有更深入的根因分析,其中一篇 CSDN 提到的「Control Flow Guard 衝突」說法查無
   可信佐證,不採信。
2. **上面 §8.1 第 2 點「Restart-Service 已證實 100% 無效」需要修正適用範圍**——續三十五/
   續四十九兩輪測試的是**非管理員權限**下的 `Restart-Service`,這類系統服務在非管理員權限下
   本來就會直接被拒絕(Access Denied),根本沒有真的執行到重啟,所以那個「無效」的結論其實
   只證明了「非管理員權限行不通」,並沒有真正驗證過「系統管理員權限的 targeted service
   restart」這條路。外部多筆 issue 顯示,**管理員權限下單獨 `Restart-Service vmcompute`
   (必要時加 `hns`、`LxssManager`)** 有機會比整個 `wsl --shutdown`/重開機更快清除卡死,
   下次使用者要處理 deadlock 時值得優先一試,失敗再退回原本的 `wsl --shutdown`(admin)/
   重開機。
3. **可能的預防性措施(未在本機驗證,列為待測建議)**:
   - 關閉 Windows 快速啟動(`powercfg /h off` 或控制台設定)——多篇 issue 指出快速啟動的
     休眠式關機/開機路徑跟這類 VM 層卡死有關聯,對開發機沒有明顯壞處,值得直接關閉。
   - 下次 deadlock 發生時,回溯是否剛好在一次睡眠/喚醒循環之後——如果每次都吻合,代表觸發
     條件其實已知(避免在長時間 live 驗證任務期間讓機器進入睡眠),而不是真的無跡可尋。
   - 確認 `wsl --update` 已更新到最新版(部分上述 issue 後續已被官方修過)。
   - `.wslconfig` 的 `networkingMode=mirrored` 等調整目前**沒有找到直接證據**對這個特定
     deadlock 有效,列為低優先、探索性選項,不是已知修復。

這些都還沒有被官方確認為根因或正式修復(#2、#40994 在來源查詢當下都還是 open 狀態),
§8.1 第1點「每輪結束主動 `wsl --shutdown`」的預防建議依然有效、繼續適用。

### 8.2 `/tmp/.X11-unix`——重開機後重新驗證:仍然是唯讀,證實是永久性 WSLg 行為,不是暫時性狀態

續四十五(2026-08-22)第一次記錄這個問題時,只在同一個未重開機的 session 裡遇到,當時就懷疑
「可能只是這次 session 的暫時狀態」。**這輪在使用者已重開機的乾淨環境下重新驗證**:

```
$ wsl -d Ubuntu -- mount | grep X11-unix
none on /tmp/.X11-unix type tmpfs (ro,relatime)
$ wsl -d Ubuntu -- ls -la /tmp/.X11-unix
srwxrwxrwx 1 kg701004 kg701004 0 ... X0
$ touch /tmp/.X11-unix/test_write_check
touch: cannot touch '/tmp/.X11-unix/test_write_check': Read-only file system
```

**結論(訂正續四十五的猜測):這不是暫時性狀態,是這台機器上 WSLg 的標準、持續性行為**——
`/tmp/.X11-unix` 被 WSLg 掛成唯讀 tmpfs,目的是保護它自己的 `X0` socket(WSLg 自己的
display `:0`)不被其他程式在同一個目錄下建立/覆寫 socket 檔案干擾,不是某次啟動的偶發異常。
`sudo -n mount -o remount,rw ...`確認**沒有 passwordless sudo**(`sudo: a password is
required`),所以「remount 成可寫」這條路在目前的非互動 session 裡走不通,也不建議去問使用者
要密碼(違反安全規則)。

**最終結論:TCP-Xvfb workaround 是這台機器上永久、必要的標準做法,不是一次性繞過**——
下一輪不需要再花時間重新診斷或嘗試 unix socket,直接採用 §8.4 recipe 裡的
`Xvfb :99 ... -nolisten local -listen tcp` + `DISPLAY=127.0.0.1:99` 組合即可。

### 8.3 鍵盤按鍵可靠性——系統性量測,850 次按鍵測試 0 次掉鍵(cycles 5000-20000 範圍內),但找到一個新的、更嚴重的低 cycles 失效模式

**方法**:doc58 續四十七起懷疑「cycles 太低導致 SDL 輸入層來不及輪詢到短暫按鍵脈衝」,但這個
假說從未被量化驗證過(只有零星的「這次按鍵沒反應」軼事記錄)。這輪設計了一個可重複、程式化
驗證的測試:標題畫面 `START/LOAD/CONTINUE` 是一個 3 選項、`Down` 鍵可自由 wrap 的選單(已用
逐格測試確認:`START→LOAD→CONTINUE→START` 循環,不是 clamp)。用 ImageMagick 對固定像素座標
(`(264,351)`/`(264,369)`/`(264,387)`,對應三個選項左側的反白圓點標記)做顏色取樣,精確判定
目前反白在哪個選項,不依賴肉眼判讀截圖。測試腳本、方法與逐輪原始 CSV 過程檔留在
`.wsl_build/`(非 repo 追蹤內容,`keytest_run.sh`/`keytest_burst.sh`/`find_dots.awk`)。

**測項 A:單次按鍵(single-tap),每次按鍵後間隔 0.3 秒才送下一次,共 100 次/組**:

| core | cycles | 按鍵數 | 掉鍵數 |
|---|---|---|---|
| normal | 5000 | 100 | 0 |
| normal | 10000 | 100 | 0 |
| normal | 15000 | 100 | 0 |
| normal | 20000 | 100 | 0 |
| dynamic | auto(max) | 100 | 0 |

**測項 B:連續爆發(burst),10 次 `Down` 幾乎無間隔(inter-key delay 0~0.05 秒)連續送出後才
偵測一次最終狀態,偵測用 `(expected − actual) mod 3` 反推「這次爆發裡遺漏了幾次按鍵」**:

| core | cycles | inter-key delay | 爆發次數×每次按鍵數 | 總按鍵數 | 偵測到掉鍵的爆發次數 | 估計遺漏按鍵數 |
|---|---|---|---|---|---|---|
| normal | 5000 | 0.05s | 15×10 | 150 | 0 | 0 |
| normal | 5000 | 0s | 5×10 | 50 | 0 | 0 |
| normal | 20000 | 0s | 15×10 | 150 | 0 | 0 |

**總計 850 次獨立按鍵、涵蓋 5 種 core/cycles 組合、兩種送鍵節奏(單發 0.3s 間隔 / 連發 0~0.05s
間隔),掉鍵數全部是 0**——在 doc58 過去記錄過的常見安全範圍(`cycles=5000..20000`,`core=
normal` 或 `dynamic+auto`)裡,**沒有偵測到任何跟 cycles 數值相關的、漸進式的掉鍵率差異**,
續四十九「cycles 太低導致 SDL 漏接短暫按鍵脈衝」這個假說,**在這個測試範圍內沒有得到支持**。

**意外發現一個更嚴重、之前從未記錄過的失效模式:cycles 低於安全範圍不是「變慢」,是直接讓
dosbox-x 在開場動畫的解析度切換過程中當機**——測試 `cycles=1000`與`cycles=3000`(均
`core=normal`,比續四十四起確立的 `5000` 下限更低)時,dosbox-x **兩次獨立測試都在到達標題
畫面之前,於開場動畫的多次解析度/長寬比切換過程中崩潰**,tmux pane 印出:

```
XIO:  fatal IO error 0 (Success) on X server "127.0.0.1:99"
      after 13582/13668 requests (...) with 0 events remaining.
```

兩次崩潰發生的 X11 request 計數(13582、13668)高度接近,不是隨機時機的巧合。額外用同樣
「連續重啟環境、不留緩衝時間」的節奏對 `cycles=5000` 重新測試過一次,**沒有重現這個崩潰**——
排除「純粹是連續重啟太快」的替代解釋,確認崩潰跟 cycles 過低本身相關,不是重啟節奏問題。

**結論(訂正並收斂續四十九的假說)**:
1. 在 `cycles∈[5000,20000]` 這個範圍內,**鍵盤掉鍵率是 0%,不是一個隨 cycles 漸進變化的量**——
   沒有證據支持「調高 cycles 能讓輸入更可靠」這個猜測,`5000` 已經完全足夠,調到 `20000`
   沒有偵測到任何額外好處。
2. `cycles` 真正的風險不是「掉鍵率上升」,而是**低於某個門檻(這次驗證的 `1000`/`3000` 兩個
   值都會)直接讓模擬器在開場動畫的畫面模式切換時當掉**,是一個二元的崩潰/不崩潰門檻,不是
   連續變化的可靠度曲線。**建議下限維持 `cycles=5000`**(續四十四起的既有經驗值,這次重新
   驗證確認合理,沒有理由改動)。
3. **重要範圍限定,避免下一輪過度推廣這個結論**:這次測試的是**標題選單的按鍵讀取路徑**
   (相對單純、doc13 完全反組譯過的一個獨立子系統),**不是**doc58 續四十七/續四十八記錄的
   「戰鬥地圖移動確認 Enter」或「重複 `Alt+Pause` 後 `Up` 鍵失效」那兩個問題所在的程式碼路徑
   (`0x18890`/`0x115b6`附近,戰鬥指令環相關)。續四十八第二輪已經在**完全不碰 debugger、
   全新開機**的乾淨環境下獨立重現過「移動確認 Enter 無效」,這代表那個問題**不需要 debugger
   介入就會發生**,但這次的量化測試(同樣不碰 debugger、只測標題選單)完全沒有重現任何掉鍵
   ——兩者合起來看,續四十七/四十八記錄的症狀**更可能是戰鬥地圖這條特定程式碼路徑本身的
   邏輯問題(entry gate 判定、`DAT_00051a83`等),而不是一個「cycles 太低導致 SDL 全域性
   漏接按鍵」的通用環境問題**——這次的量化結果應該用來**降低**「cycles/SDL 輸入層」這個
   假說在下一輪待辦清單裡的優先度,把精力導回續四十七/四十八自己建議的靜態反組譯路線
   (`0x18890`按鍵讀取到 gate 判斷邏輯)。

### 8.4 最終建議:已驗證穩定的完整啟動 + 操作 recipe

**啟動參數(固定,不要在互動 debugger 裡事後切換)**:

```bash
Xvfb :99 -screen 0 1024x768x24 -ac -nolisten local -listen tcp > xvfb.log 2>&1 &
sleep 3
export DISPLAY=127.0.0.1:99
tmux new-session -d -s dbg -x 200 -y 50 \
  "dosbox-x -c 'MOUNT C <遊戲目錄>' -c 'C:' \
            -c 'config -set core=normal' -c 'config -set cycles=5000' \
            -c 'FD2.EXE'"
sleep 2
tmux set-option -t dbg remain-on-exit on   # 避免 dosbox-x 意外結束時整個 tmux session 陪葬
```

- `core=normal` + `cycles=5000`:§8.3 重新驗證過的安全下限,不要低於這個值(會導致開場動畫
  解析度切換時崩潰,見 §8.3);沒有證據顯示調更高(到 20000)有額外好處,除非某個特定畫面
  需要更快的模擬時間流逝速度。
- **這整段(Xvfb+tmux+dosbox-x)必須包成同一次 shell 呼叫,呼叫本身用工具的
  `run_in_background:true` 背景執行,且腳本結尾要接一段長 `sleep`(例如 `sleep 3595`)**——
  這是續二十一(2026-08-18)最早確立、至今每一輪都還要依賴的根因修法:讓「建立這個 Xvfb/
  tmux/dosbox-x 環境」的那一個 WSLg 連線本身留在背景一直活著,否則 15-60 秒內整組行程會被
  WSLg 連帶收掉。**不要**在腳本內部用 `&` 把 Xvfb/dosbox-x 背景化後讓外層 `wsl.exe` 立刻
  return——同樣會被連帶收掉(續四十六的教訓)。

**X11**:這台機器 `/tmp/.X11-unix` 已確認是永久唯讀(§8.2),固定用 `-nolisten local -listen
tcp` + `DISPLAY=127.0.0.1:99`,不要嘗試 unix socket。

**按鍵發送最佳實踐**:
- 用 `xdotool key --window <winid> <key>` 對指定視窗送鍵,不需要也不應該呼叫
  `xdotool windowactivate`(這個環境沒有 window manager,`activate` 一定失敗,見續四十五)。
- `xdotool search --name '.'` 可靠取得唯一視窗 id,同一個 X server session 內穩定不變。
- §8.3 證實 `cycles=5000` 下**沒有量化到任何掉鍵**,單發按鍵不需要額外的人工延遲補償;但
  如果操作的是戰鬥地圖(移動確認/指令環),續四十七/四十八記錄過該路徑本身有獨立於輸入時序
  的不可靠性,遇到「送鍵後畫面無反應」時**優先假設是那條程式碼路徑的邏輯問題,不要盲目調
  cycles 或加延遲重試**(§8.3 已經排除這是通用輸入層問題)。
- **除錯 console(`Alt+Pause` 進 debugger)的指令送出**:用 `tmux send-keys -t dbg -l
  '<指令文字>'`,**獨立**一次 `tmux send-keys -t dbg -l $'\r'`(續四十四驗證,`-l` literal
  flag 不可省略,不要跟具名 `Enter`/`C-m` 鍵混用)。指令被拒絕(not recognized)不會自動清行,
  需要連續 `BSpace`(具名鍵)清空後才能送下一個指令。
- **重複 `Alt+Pause` 之後,`Up` 鍵有相當機率單獨失效**(`Down`/`Left`/`Right` 不受影響,續
  四十七)——一旦發現任何方向鍵送出後畫面/debugger 狀態完全無反應,**不要在同一個 session
  裡繼續除錯,直接完整重開整個環境**(`pkill -9 dosbox-x` + `pkill -9 -f Xvfb` +
  `tmux kill-server`,重新走一次啟動序列),這比嘗試修復卡死的鍵盤狀態省時間。
- `MEMDUMPBIN` 是 DOSBox-X 已知的 upstream bug(GitHub issue #3629,回報成功但不產生檔案),
  一律改用 `D <seg> <off>` 逐行讀記憶體。
- `tmux capture-pane` 在連續高頻操作 debugger console 之後,曾多次記錄「送出新指令但畫面回傳
  跟前一次完全相同的 stale 內容」(續四十七起累積);任何依賴 `capture-pane` 輸出做判斷的
  自動化流程,建議在關鍵結論前**用一個已知會改變狀態的對照組指令**驗證 pane 是不是真的更新
  過,不要對單次輸出照單全收。

**已知仍未解決的限制(誠實列出,不宣稱已修好)**:
1. `WSLService` deadlock 根因未知,無法從軟體層面預防或自行修復,只能靠使用者主動
   `wsl --shutdown`/重開機恢復,見 §8.1。
2. 戰鬥地圖「移動確認 Enter」/「指令環無法開啟(`0x17aed`假畫面)」這兩個症狀,續三十六到
   續五十反覆出現、時好時壞,§8.3 已經排除是通用鍵盤/cycles 問題,但真正根因(entry gate
   欄位在 ch27 這個特定存檔路徑上的寫入時序)仍未定案,留給下一輪純靜態反組譯攻堅
   (doc58 續五十結尾建議,查 `record[+6]`/`record[+5]`/`record[+0x26]` 的寫入端)。
   **2026-08-29「ch27ret」輪追加**:`99-chapter-sweep-results.md`同日「ch27sky」輪
   記錄過一次範圍更廣的變體——連本專案最可靠的「空地格 End-Turn」`Return`路徑都完全
   無反應(不是本項原本記載的「有假畫面但不能互動」,是**完全沒有任何畫面變化**)。
   `ch27ret`輪完整反組譯了`0x117e7`(Enter 分派入口)與其呼叫的`FUN_00016f55`(空地格
   /系統環子系統),確認`0x117e7`在比對到游標下有一個活著單位時,`unit[+7]=='y'`或
   `unit[+0x1f]==0x0a`任一成立會讓整段 Enter 處理(含本項①②③三個 entry gate 與後續
   handler 呼叫鏈)完全跳過、直接無聲 return——這是目前反組譯庫裡唯一精確吻合「連
   系統環都不開」症狀的已知程式碼路徑,與 doc58 續三十九/四十獨立發現的同一組前置
   檢查互相印證,但**只是尚未證實的候選**:`ch27ret`輪用同一份真實存檔、同一批
   record 位址,完整重演「ch27sky」輪的天空之鑰寫入+機甲隊長 teleport 操作後,live
   測試中`Return`兩次都正常運作(第二次乾淨開出真正的系統環,截圖確認),未能重現
   「完全無反應」的症狀,也確認過游標當下沒有落在任何活著記錄上(前置檢查分支未被
   觸發)。**結論:這個更嚴重的變體根因仍未定案**,已排除是本輪測試的環境迴歸、也
   排除是天空之鑰寫入或機甲隊長 teleport 這兩個操作本身的確定性後果,較可能是
   「ch27sky」輪那次長 session 累積的暫態狀態,與本項原本記載的「時好時壞」屬同一
   類別而非新增的獨立限制,不要假設已經解決。
3. dosbox-x heavy debugger 的 `BP`/`BPM` 斷點在 Dynamic core 下對非分支目標(區塊中段)位址
   不可靠(已知官方限制,`core=normal`可解,見續四十三/四十四),但**即使在 Normal core
   下**,續四十八/續五十仍記錄過斷點「registered 但從未命中」的個案,不是 100% 徹底解決,
   遇到時建議優先用畫面/screenshot 驗證遊戲狀態,不要完全依賴 debugger 讀值。
4. **按鍵發送一律用 `xdotool key --window <winid>`(`XTestFakeKeyEvent`),不要嘗試
   `ydotool`(Linux kernel `uinput` 注入)**——doc58 續七十二(2026-08-26)已實測排除:
   `Xvfb` 架構上只支援 `XTest` extension 合成事件,沒有 `evdev`/`libinput` 熱插拔支援
   去消費 `ydotoold` 透過 `uinput` 建立的虛擬鍵盤裝置。直接用 `xev` 在 X11 事件層核對,
   `ydotool` 送出的按鍵(含 DOSBox-X 標題選單上累計 47 次獨立嘗試,20 Enter+20 Space
   批次測試在內)**送達率 0%**,同一 session 穿插的 `xdotool` 按鍵 100% 正常送達——這不是
   「`ydotool` 也會掉鍵」的統計性負面結果,是「這條注入路徑在這個 headless Xvfb 環境下
   architecturally 無法送達」的確定性結論,不需要重新驗證,除非未來環境改用真正支援
   evdev 熱插拔的顯示後端(例如 WSLg 自己的 Wayland/Xwayland display,但那條路線引入
   §8.1/8.2 記載過的其他已知限制,doc58 續七十二**沒有**測試過,不是建議)。這**不代表**
   續五十五指認的 `XTestFakeKeyEvent`/Xvfb 一般性不可靠候選被推翻或證實——本輪 `xdotool`
   全程 100% 成功,沒有復現任何掉鍵,也沒有對那個候選做任何新測試;戰鬥地圖 Enter 確認
   間歇性失效(本節第 2 項)的根因依然完全未解。
5. **需要用 `xtrace` 做 X11 協定層封包擷取時,固定用法**(doc58 續七十七,2026-08-26 驗證):
   fake display 一律用 TCP 主機限定形式 `-D 127.0.0.1:<port>`,**不能**用裸 `:<port>`
   形式——裸形式會嘗試在 `/tmp/.X11-unix` 建立 unix socket,這個目錄在本機永久唯讀
   (§8.2),導致 `xtrace` 無聲失敗(`ps` 查無存活行程)。同時加 `-n`
   (`--nocopyauthentication`)跳過 `xauth`(`~/.Xauthority` 不存在會報錯)、`-k`
   (`--keeprunning`)容忍 `xdotool` 這類短命 client 連了又斷。完整範例:
   `xtrace -n -d 127.0.0.1:99 -D 127.0.0.1:100 -k -o capture.log`,DOSBox-X 與
   `xdotool` 都要指向 fake display(`127.0.0.1:100`),不是 Xvfb 本身的真實 display。
6. **啟動 Xvfb/xtrace/tmux/dosbox-x 這類長駐行程時,一律不要用 `setsid`**(doc58
   續七十七新發現的環境陷阱,與 §8.4 開頭已知的「不要在腳本內部提前用 `&` 把行程丟到
   背景」是兩種不同的失效模式,不要混淆):任何帶 `setsid <command> &` 的啟動腳本,
   不論前景 `timeout` 呼叫或背景執行,都會在**啟動後不到一秒內**讓整個 `wsl.exe`
   行程樹被 SIGKILL(逐行 bisect 確認是 `setsid` 本身觸發,拿掉它、其餘完全不變的
   腳本立刻穩定成功)——推測與 WSL2 行程/pty 追蹤機制依賴子行程留在原本
   session/程序群組裡有關,細節未知。單純 `&` 加上本節開頭「整段包成一次背景呼叫 +
   結尾長 `sleep`」的既有 recipe 已經足夠,不需要也不要用 `setsid` 追求更乾淨的脫離。

## 9. N-way 平行驗證 harness(`tools/dosbox_harness.sh`,2026-08-24)

§8.4 的 recipe 一次只跑一顆 dosbox-x(tmux session `dbg`、Xvfb `:99`、工作目錄 `~/fd2-run`)。
`tools/dosbox_harness.sh` 把它包成可重複呼叫的 `launch`/`screenshot`/`send-keys`/
`enter-debugger`/`debugger-cmd`/`status`/`teardown`/`teardown-all` 子指令,讓多個互不相關的
91-worklist 項目可以同時各開一顆獨立 dosbox-x 驗證,不用排隊。每個 instance 有自己的 Xvfb TCP
display(自動配置,`:199`/`:299`/…)、自己的 tmux **server**(`-L fd2harness`,與 §8.4 用的
default server 完全分開,不只是換 session 名字)、自己的工作目錄(`~/fd2-run-harness-<name>`,
從 `~/fd2-run` 複製而來),所以可以跟 §8.4 這條「單一 instance」recipe 的 session 同時跑,
互不干擾——2026-08-24 已在 §8.4 的 canonical session(`dbg`/`:99`)**正在執行中**時,額外並行
啟動兩顆 harness instance 實測驗證過(畫面各自獨立進度、送鍵/debugger 指令互不串線、
`teardown-all` 只清掉 harness 自己的 process,`dbg`/`:99` 全程未受影響)。

完整用法、已驗證的並行上限(2-3 顆)、建置過程中踩到的坑(含一個真的 bug:Xvfb 的顯示器參數
只能是裸 `:N`,不能是 `127.0.0.1:N`,那個形式只用在給 client 端的 `DISPLAY` 環境變數)記錄在
`docs/knowledge-base/98-tooling-infrastructure.md`,不在此重複。

## 10. 內建執行流程追蹤指令(`LOG`/`LOGC`,2026-08-25)——`tools/dosbox_exec_trace.sh`

除了 §4.2 表列的斷點/dump 指令,這個專案用的 heavy-debug build(`--enable-debug=heavy`,見 §2)
**內建**了一組逐指令執行追蹤指令:`LOG`/`LOGS`/`LOGL`/`LOGC <hex count>`(輸出到 debugger
工作目錄的 `LOGCPU.TXT`)、`ADDLOG`、`HEAVYLOG`——`strings`(對這台專案 WSL2-native 建置的
二進位)與 `debug.cpp` 原始碼(`~/fd2-dosbox-build/dosbox-x/src/debug/debug.cpp`,同一顆
§8 沿用至今的建置)都已 2026-08-25 直接核對確認存在,不是猜測。`LOGC` 只印 `CS:EIP`(最輕量,
無暫存器/flag),是位址獵尋任務(如 doc35 §9 的 party montage renderer 獵尋)的正確選擇——
不需要像原本規劃過的備案那樣自己刻一支腳本化單步+EIP 擷取工具,這個功能 dosbox-x 本來就有。

已驗證(不是紙上談兵):武裝 `LOGC` 之後遊戲畫面持續渲染、持續接受 `xdotool` 按鍵——不是
會凍結整個模擬器的阻塞操作,可以邊記錄邊照常操作遊戲;吞吐量約每秒數百萬到近千萬指令(與
`cycles=5000` 這個模擬速度設定是兩回事,不要混為一談,見下方 doc98 連結裡的完整說明);
600,000,000 指令的一次追蹤,`awk` 單趟去重後只剩 12,297 筆唯一 `CS:EIP`(主程式碼段
`CS=0170` 佔 8,727 筆),批次比對 Ghidra 的 `function_bounds` 只要 6.6 秒。

完整用法、內部行為的 `debug.cpp` 依據、吞吐量實測數字、一個文件比對假陽性的教訓(位址字串比對
沒做邊界檢查會被 hash/URL 之類的長字串子字串誤判)、已知限制,見
`docs/knowledge-base/98-tooling-infrastructure.md`「Ground-truth 執行流程追蹤」一節,不在此
重複。封裝好的工具是 `tools/dosbox_exec_trace.sh`(WSL 端武裝/收集/去重)+
`tools/dosbox_exec_trace_analyze.py`(Windows 端換算 native 位址、批次比對 Ghidra、分類
已知/已分析未記錄/完全未分析三類)。首次實戰結果(ch27 戰前「轉送站幻象」montage 完整執行
流程捕捉)見 `docs/knowledge-base/58-remake-live-verification-log.md` 續六十六與
`docs/knowledge-base/35-battle-animation-rendering.md` §9.15。

## 11. DOSBox-vs-remake byte-exact pixel diff harness(`tools/dosbox_diff_harness.sh`,2026-08-26)

§9 的 `tools/dosbox_harness.sh` 是給互動式/視覺檢查用的通用 N-way harness,`screenshot`子指令
用 `import -window root`,視窗多大就截多大——這對「肉眼看畫面對不對」足夠,但**不是** byte-exact
擷取(視窗通常比遊戲原生 320×200 大,要縮到 320×200 得經過一次 resize,引入取樣誤差)。

`tools/dosbox_diff_harness.sh`是專門給 pixel-diff 用的姊妹腳本(獨立 registry/tmux
socket/Xvfb port range,刻意不修改`dosbox_harness.sh`本身,避免影響同時在跑的其他 agent),
啟動的是**套件版 `dosbox`(非 dosbox-x)**,搭配`[sdl] output=surface`+
`[render] scaler=none aspect=false`config,讓 SDL 視窗精確等於目前模擬視訊模式的原生解析度
(標題/戰鬥選單等 mode 13h 畫面=320×200,開場動畫的 SVGA 過場=640×400),`raw-screenshot`
子指令在擷取前會核對視窗幾何、量到的尺寸不對就直接報錯,不會偷偷 crop/resize。改用 plain
dosbox 而非本篇§2-8 的 heavy-debug `dosbox-x`,是因為 dosbox-x 的視窗化 SDL 輸出固定會多畫一條
GUI 選單列(即使非全螢幕),讓視窗永遠比原生解析度大;純截圖工作用不到 debugger,換掉沒有
任何功能損失。

配套的 `tools/dosbox_diff_harness.py`(Windows 端)把 FD2.SAV chapter-jump patch、DOSBox-X
擷取、`remake/fd2-linux-verify`擷取(640×400 邏輯畫布→無損 2×2 區塊取樣還原 320×200)、diff
統計/視覺化全部接成一條 CLI 指令。2026-08-26 已驗證:①對既有 UI-01 title-screen oracle 重放
取得逐位元組相同的 raw RGB MD5;②全自動重放 ch02 城鎮 hub selection0(UI-08-TOWN-VARIANT0
同一場景),99.3-99.4% exact-pixel-match,並精確定位出一個先前用較弱比對方法(variant1/2 的
crop/resize+統計)沒抓到的小範圍 remake compositor 差異。完整設計、踩坑記錄、已知限制見
`docs/knowledge-base/98-tooling-infrastructure.md`「DOSBox-vs-remake byte-exact pixel diff
harness」一節,對應 `docs/knowledge-base/91-worklist.md` 的 UI-VIS-DIFF-HARNESS 項目。

## 12. 全章節結構性掃描(`tools/fd2_chapter_sweep.py`,2026-08-27)

對應 `docs/knowledge-base/91-worklist.md` M5「正常玩法可達性驗證」項目:把 §9 的
`tools/dosbox_harness.sh`(啟動/截圖/送鍵/debugger console)、`tools/fd2save.py`
(章節跳轉 patch/合成 roster)、以及§10 記錄過的`native+0x19C000=live`位址換算慣例
組合成一支逐章跑、失敗不中斷整批的自動化掃描工具——對每個章節 N:chapter-jump patch
存檔→LOAD→讀`DAT_00053a45`(live`0x1EFA45`)判斷是否在戰鬥中→若是則掃描 unit record
陣列寫入敵方死亡 signature+送出續六十二證實過的 End-Turn→YES 捷徑,若否則用通用
bounded 按鍵迴圈嘗試推進→讀回存檔章節 byte 是否前進作為主要 pass 訊號。

2026-08-27 對 ch02/ch27 的驗證:harness 層(launch/screenshot/debugger-cmd/teardown)
與戰鬥偵測的「陰性」判斷(正確認出「不在戰鬥中」,從未誤判)都乾淨驗證通過,但**通用
導航仍無法在合理步數預算內走到 ch27 的戰場**——這忠實反映了本篇§8.4 已知的專案級開放
問題(doc58 續五十七到續六十三記錄過解出 ch27 一個章節的 reach 序列本身就花了多輪人工
即時試錯,且同一存檔在不同 session 觀察到至少兩種不同 UI 型態)。完整驗證記錄、已知限制、
下一輪建議見`docs/knowledge-base/98-tooling-infrastructure.md`「全章節結構性掃描」一節;
掃描結果見`docs/knowledge-base/99-chapter-sweep-results.md`。
