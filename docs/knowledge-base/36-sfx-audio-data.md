# 36 — 音效(SFX)資料位置與格式

> 回答「音效資料存在哪、什麼格式」。音樂(BGM)見 `07`/`12`;`.DIG`/`.MDI` 是 Miles AIL 的**驅動程式**
> (依音效卡型號選一份載入),不是遊戲資料,見 `01` §6 / `04`。本篇反組譯 `FD2.EXE` 找出「遊戲真正播放
> 的數位音效樣本存在哪個檔案、哪個 index、什麼編碼」。

## 結論(一句話)

**《炎龍騎士團2》有數位音效,儲存在 `FDOTHER.DAT`(而非獨立音效檔),以巢狀 `LLLLLL` 容器裝著多個
「8-bit unsigned mono raw PCM」樣本,播放走 Miles AIL 的 `AIL_*_sample` 系列 API(非 `.DIG` 驅動本身
含資料 ── `.DIG` 只是硬體訪問層)。**

## 證據鏈(反組譯,file offset = linear,已用 capstone 交叉驗證)

### 1. 找到「播 SFX」函式:`0x26896` / `0x26945`

戰場命中/選單游標等處呼叫的通用「播放樣本」函式(`table_ptr, index, priority` 三參數):

```
0x026896  play_sfx_a(table, index, priority):   ; **第三個參數其實是 loop count,見 §19 訂正**
0x0268c7    push  [0x53ee4]            ; SFX 播放 handle A
0x0268cd    call  0x3a2b5              ; 取狀態/index 檢查(-1 則跳過)
0x0268dc    mov   eax, index
0x0268e0    shl   eax, 2               ; index*4 → 進表
0x0268e3    add   eax, table_ptr
0x0268eb    add   edx, [eax+6]         ; edx = table_ptr + entry.start   ← 樣本起始位址
0x0268f2    mov   edx, [eax+6]
0x0268f5    mov   eax, [eax+0xa]       ; entry.end
0x0268f8    sub   eax, edx             ; len = entry.end - entry.start
0x0268fd    push  [0x53ee4]
0x026903    call  0x39fd1              ; AIL_init_sample(handle)
0x02690b    push  len
0x02690e    push  addr
0x026912    push  [0x53ee4]
0x026918    call  0x3a144              ; AIL_set_sample_address(handle, addr, len)
0x026920    push  priority
0x026924    push  [0x53ee4]
0x02692a    call  0x3a55e              ; AIL_set_sample_loop_count(handle, priority)
0x026932    push  [0x53ee4]
0x026938    call  0x3a248              ; AIL_start_sample(handle)
```

`0x026945` 是同一份函式的第二份拷貝,操作另一個獨立 handle `[0x53ee8]`(雙聲道,兩個 SFX 可疊播)。

**呼叫端內嵌函式名確認鏈**(每個 `AIL_*` wrapper 內都有 debug-trace,push 一個字串位址再呼叫
`0x3ff1b`;字串位址用 fixup 解回實際文字,逐一比對):

| wrapper 位址 | 內嵌字串(file offset → 文字) | 對應 AIL API |
|---|---|---|
| `0x39fd1` | `0x505f8` → `"AIL_init_sample(0x%X)"` | `AIL_init_sample` |
| `0x3a144` | `0x50632` → `"AIL_set_sample_address(0x%X,0x%X,%u)"` | `AIL_set_sample_address` |
| `0x3a55e` | `0x5073b` → `"AIL_set_sample_loop_count(0x%X,%d)"` | `AIL_set_sample_loop_count` |
| `0x3a248` | `0x50679` → `"AIL_start_sample(0x%X)"` | `AIL_start_sample` |

(同段程式碼另找到 `0x658` → `"AIL_set_sample_file(...)"`、`0x658` 一帶的 `"AIL_set_sample_type(...)"` 等
其餘樣本 API 字串,證實 EXE 內確有完整 AIL digital-sample 呼叫鏈,而非只有驅動殼子。)

### 2. 找到「表從哪來」:一次性 init 載入 `FDOTHER.DAT` 資源 `#31`(`0x1f`)

`[0x53eec]`(上面 `table_ptr`)在啟動 init 區(緊接在 `play_bgm` 之後,`0x26a63`)被設定:

```
0x026a63  push  0x1f                   ; 資源 index = 31
0x026a65  push  [0x53eec]              ; 舊指標(釋放用)
0x026a6b  push  0x1a4d                 ; ->0x51a4d = "FDOTHER.DAT"(字串已確認)
0x026a70  call  0x11fba                ; 通用「載容器資源」函式(與 play_bgm 載 FDMUS.DAT 用同一支)
0x026a78  mov   [0x53eec], eax         ; 存起來
```

同一段 init 另外把 `FDOTHER.DAT` 資源 `#1`、`#2` 分別載進 `[0x53a4d]`、`[0x53a89]`。#2 已由
UI renderer trace 確認為 action overlay 的 raw indexed cell bank（doc57）。#1 已由 `0x122dc→0x126f7`
關閉：它是 `{u16 24,u16 24,u16 20,u32 offsets[]}` 的 four-mode RLE descriptor bank，range overlay
modes 1..5 以 descriptors 0..18 經 `0x4deda` 使用；故不是 SFX 資料。

`[0x53eec]` 被 code 讀取(`push dword ptr [0x53eec]` 系列)共 **58 處**,散布在選單/游標/對話等一般 UI
流程 ── 符合「UI 通用音效池」的角色。

### 3. 戰鬥/攻擊音效:另一張表,同一個檔案,動態 index

戰場動畫更新函式(`0x28ee0` 一帶,單位受擊/攻擊演出)另外從 `FDOTHER.DAT` 動態載入:

```
0x028f1a  mov   eax, [esp+0x50]
0x028f1e  add   eax, 0x21              ; index = 某資料表[unit/attack]+0x21(依攻擊種類變化)
0x028f21  push  eax
0x028f24  push  0x1a4d                 ; "FDOTHER.DAT"
0x028f29  call  0x11fba
0x028f33  mov   [0x5411f], 0
...
0x028f41  movzx eax, [esp+eax-0xc]     ; 第二個動態 index(byte,依攻擊資料)
0x028f49  push  0x1a4d                 ; "FDOTHER.DAT"
0x028f4e  call  0x11fba
0x028f56  mov   [0x5411f], eax
```

`[0x5411f]` 再被 `0x268c7`/`0x26976` 形式的 `play_sfx` 呼叫(32 處 xref,全落在 `0x27000`–`0x2c600`
戰鬥演出程式碼範圍內)。**結論:戰鬥音效(揮擊/受擊等)也走 `FDOTHER.DAT`,但 index 依攻擊/單位資料
動態決定**(不是固定 index),对应「每種招式配自己的音效」設計 ── index 表本身待第 9 輪逐招對照。

### 4. 直接解包驗證:`FDOTHER.DAT` 資源 #31 = 巢狀容器,內容是原始 PCM

```
$ python3 tools/unpack_dat.py --list FDOTHER.DAT | grep '^    31'
    31  0x000fe4f3       31771
```

抽出這段 bytes,開頭即 `LLLLLL` magic → 資源 #31 本身**又是一個 `LLLLLL` 容器**(嵌套,與 doc23
記錄的資源 #7 巢狀容器同一手法),內含 **14 個子樣本**:

| sub# | 長度(bytes) | 特徵 |
|---|---|---|
| 0 | 160 | 極短,值域窄(`0x77`–`0x90`) → 短促 UI 提示音(游標移動量級) |
| 1 | 3322 | 值集中 `0x80` 附近 | 
| 2 | 667 | 短 |
| 3 | 6324 | 最長,值域寬(`0x67`–`0x8f`) → 較長效果音 |
| 4 | 3438 | 值域最寬(`0x58`–`0x90`) |
| 5–6 | 3058, 3058 | 幾乎全 `0x80`(近似靜音段) |
| 7 | 160 | 與 #0 同長度、不同波形 |
| 8 | 2652 | 全 `0x80` 開頭 |
| 9 | 390 | 短、值窄 |
| 10 | 3304 | 全 `0x80` 開頭 |
| 11 | 2442 | 漸變波形 |
| 12 | 2734 | 全 `0x80` 開頭 |
| 13 | 0 | 空(目錄結尾哨兵) |

所有子樣本 byte 值都集中在 **`0x80`(128)附近上下擺動**(unsigned 8-bit PCM 的靜音中心值恰為
128) ── **這就是無壓縮、無檔頭的 8-bit unsigned mono raw PCM**,與 Miles AIL digital sample API
(`AIL_set_sample_address` + `AIL_set_sample_type`)直接吃裸 PCM buffer 的用法完全吻合:不需要 WAV/VOC
檔頭,取樣率/位元深度另由 `AIL_set_sample_type`/`AIL_set_sample_playback_rate` 呼叫端設定(未逐一反組譯
其立即數,取樣率待後輪用實機錄音比對確認,推定 11025Hz ── 1995 年 AIL 遊戲常見預設值)。
**續一百六十一(FD2.EXE 反組譯)**:取樣率不由呼叫端設定 —— `AIL_init_sample`(`0x39521`)在 `0x39584` 呼叫 `0x414e0`,它把樣本 `+0x3c` 預設成 `0x2b11` = 11025、格式 `+0x34` = 0(8-bit mono);`play_sfx_a`(`0x25a96`)只呼叫 stop / init / set_sample_address / set_sample_loop_count / start,不改這兩個欄位。11025 Hz / 8-bit mono 由推定改為已確認(`evidence/timer_base_and_delay_slowdown_s161_20261028.json`)。

## `.DIG` / `SAMPLE.*` 的角色釐清(避免與資料混淆)

| 檔案 | 角色 |
|---|---|
| `*.DIG`(`SBLASTER.DIG` 等) | Miles AIL **數位輸出驅動**(依音效卡選一份載入),純程式碼,不含遊戲音效資料 |
| `SAMPLE.BNK` | 標準 Miles SDK 隨附的 **AdLib 樂器名稱庫**(`ADLIB-` magic + 樂器名字串表),FM 合成器音色定義,與遊戲 SFX 資料無關 |
| `SAMPLE.AD` / `SAMPLE.OPL` | 與 `SAMPLE.BNK` 配套的偏移索引表,同屬 AIL SDK 標準檔案 |
| `FDOTHER.DAT` 資源 `#31`、動態 index(`+0x21`/`[+eax-0xc]`) | **真正的遊戲 SFX 樣本資料**(本篇結論) |

`SAMPLE.BNK/AD/OPL` 三檔的內容(偏移遞增表 + 樂器名字串)是 Miles Sound System 開發套件的**通用隨附
檔**,不含 `FLAME2` 專屬資料 ── 判斷依據:內容與已知其他 Miles/AIL 遊戲的同名檔案結構特徵一致(遞增
uint32 表 + `ADLIB-`/樂器名字串),且遊戲程式碼中未找到任何對 `"SAMPLE.BNK"`/`"SAMPLE.AD"`/`"SAMPLE.OPL"`
字串的參照(僅 `.MDI`/`.DIG` driver 內部會用到,由 AIL library 自己讀取,不是 `FD2.EXE` 遊戲邏輯呼叫)。

## 重製對應(SDL2 / Ebiten)

| 原版 | 現代 |
|---|---|
| `FDOTHER.DAT` #31(巢狀容器,14 個 8-bit unsigned PCM) | 逐個解出轉 WAV(補標準 44-byte RIFF 檔頭,8-bit unsigned mono),或轉 OGG |
| `AIL_init_sample` → `set_sample_address` → `set_sample_loop_count` → `start_sample` | SDL_mixer `Mix_LoadWAV` + `Mix_PlayChannel` |
| 雙 handle(`[0x53ee4]`/`[0x53ee8]`) | 兩個 SDL_mixer channel(允許疊播) |
| 戰鬥音效動態 index(`+0x21`) | 第12輪已解出 action_id 0-9 → `FDOTHER.DAT` #82-90 資源層級對照(見下方第12輪段落);`attack_id → sfx_index` 對照表仍缺招式中文名稱標籤 |

## 待辦(後輪)

- [x] `FDOTHER.DAT` #31 的 14 個子樣本導出成 WAV(見下方「導出 WAV」)。
- [x] `[0x53eec]` UI 表 index 0 對照確認(見下方「事件→樣本對照」);其餘 index 已列出呼叫端證據,
  精確語意(哪個選單/哪個動作)待後輪配合畫面實測確認。
- [x] 戰鬥動態 index 表載入點已定位到真實位址(`0x028110`–`0x028156`,取代第 8 輪誤記的 `0x28f24`/
  `0x28f49`),且發現通用容器載入函式本身位址也錯了(`0x11fba`→應為`0x111ba`,見「位址勘誤第二輪」)。
  已用 PCM 特徵掃描找出候選資源家族(`#48/#49/#50/#51/#52/#53/#64/#78/#88`,見「戰鬥音效池」節)並
  導出 WAV。**未完成**:`[esp+0x50]+0x21`/`[esp+eax-0xc]` 兩個動態 index 各自對應到候選家族中哪個
  資源號、「招式/攻擊 → 子樣本」精確對照表,仍未反推出。第 11 輪已把 index2 的填值來源往上追了 4 層
  呼叫鏈(見「`index2` 陣列填值來源追蹤」節),確認不是 `0x027fc9` 自己的表,並意外解出一個相鄰陣列
  (`+0xc8`)的填值來源是 `0x1c269` 40-bit bit-scan；但 index2 真正讀的
  `[esp+0xd0+counter]` 陣列填值來源仍未接上,是下一輪切入點(`docs/data/battle_sfx_map.json` 有完整
  位址證據鏈)。
- [x] 取樣率呼叫端已追蹤(見下方「取樣率:負向證據」),**確認遊戲程式碼從未呼叫**
  `AIL_set_sample_type`/`AIL_set_sample_playback_rate`,故無法從呼叫端立即數反查——沿用 11025Hz/8-bit
  推定值,已從「未查證」升級為「查證後仍無直接證據,推定值維持」。
  續一百六十一:直接證據找到了,是 `AIL_init_sample` 的預設值(`0x414e0` 設 `+0x3c` = `0x2b11`,FD2.EXE 反組譯),見開頭。
- [x] `FDOTHER.DAT` #1（同一次 init 載入至 `[0x53a4d]`）是 `0x122dc/0x126f7` range overlay 的 20-entry
  24×24 four-mode RLE descriptor bank，#0..18 由 modes 1..5 使用；#2 是 action overlay raw cell bank。

## 導出 WAV(第 9 輪)

`tools/export_sfx.py` 解開 `FDOTHER.DAT` 資源 #31 的巢狀容器,逐個子樣本補 44-byte RIFF/WAV 檔頭
(8-bit unsigned mono,取樣率沿用 11025Hz 推定值),輸出到 `remake/assets/sfx/sfx_00.wav` ~ `sfx_12.wav`
(sub#13 是 0 bytes 的目錄結尾哨兵,不輸出)。用 Python `wave` 模組開啟驗證皆合法:

| 檔名 | bytes | 時長 |
|---|---|---|
| sfx_00.wav |    160 |  14.5 ms |
| sfx_01.wav |   3322 | 301.3 ms |
| sfx_02.wav |    667 |  60.5 ms |
| sfx_03.wav |   6324 | 573.6 ms |
| sfx_04.wav |   3438 | 311.8 ms |
| sfx_05.wav |   3058 | 277.4 ms |
| sfx_06.wav |   3058 | 277.4 ms |
| sfx_07.wav |    160 |  14.5 ms |
| sfx_08.wav |   2652 | 240.5 ms |
| sfx_09.wav |    390 |  35.4 ms |
| sfx_10.wav |   3304 | 299.7 ms |
| sfx_11.wav |   2442 | 221.5 ms |
| sfx_12.wav |   2734 | 248.0 ms |

**續一百七十八(DOSBox-X 呼叫紀錄 lc173a / lc174a / lc174b + FD2.EXE 反組譯)**:開機 → 標題 → 開始的三份紀錄裡,DIG 混音每次填緩衝的長度
依混音器 `0x49690` 的模型(步長 11025 / 22050、每次填緩衝累加器從 0x80000000 起)換回樣本長度,只對得到這幾段:
`sfx_09`(390 bytes)每份 32 次、`sfx_02`(667 bytes)9 / 9 / 10 次、FDOTHER `#77` 第 1 段(4277,確認音效)、`#78` 第 0 段(6478)、
6235 bytes 那段(FDOTHER `#49` 第 6 / `#53` 第 2 / `#77` 第 3 段逐位元組相同)。哪個畫面事件觸發 index 9 / 2 沒追。見 `98-tooling-infrastructure.md` 續一百七十八。
續一百七十九:6235 那段是標題 `title_seq` `0x1fd24` 從 `#77` 放的(DOSBox-X 呼叫紀錄 cl1 .. cl14 的指標處就是 `#77` 開頭);
`sfx_09` 是腳步音(`play_step_sfx`)、`sfx_02` 是對話打字音(`typewriter_tick`),見下面 index 表。

## ⚠ 位址勘誤(第 9 輪發現,影響本文件先前版本的絕對位址)

本文件先前版本(第 8 輪)記載的 `play_sfx_a=0x026896`、`play_sfx_b=0x026945`、
`table_ptr 載入=0x026a63` 等位址,經第 9 輪用 `tools/disasm_le.py range` 重新反組譯比對,**內容對不上**
(該位址範圍實際是別的函式)。追查後確認:這批位址是**檔案偏移(file offset)誤當成 linear 位址**沿用
造成的系統性誤差,固定偏差 `+0xE00`(= `data_off(0x10e00) - CODE_BASE(0x10000)`,見
`tools/disasm_le.py` 檔頭註解的 `lin2file` 公式)。`tools/le_xref.py str` 指令印出的「被參照(file)」
本來就是檔案偏移,不能直接餵給 `disasm_le.py range/dis`(它吃 linear);必須先用
`disasm_le.py refs <linear字串位址>` 或手動減 `0xE00` 換算。

**正確 linear 位址**(已用 capstone 重新反組譯逐位元組核對,邏輯與第 8 輪文字敘述一致,只有數字錯):

| 用途 | 第 8 輪誤記(file offset) | 第 9 輪修正(linear) |
|---|---|---|
| `play_sfx_a`(handle A,`[0x53ee4]`) | `0x026896` | **`0x25a96`** |
| `play_sfx_a` 內 `AIL_init_sample` 呼叫 | `0x0268c7`/`call 0x39fd1` | `0x25afd`/`call 0x391d1` |
| `play_sfx_b`(handle B,`[0x53ee8]`) | `0x026945` | **`0x25b45`** |
| handle A/B 配置(`AIL_allocate_sample_handle`) | — | `0x25c43`(A)、`0x25c56`(B) |
| `[0x53eec]` 載入 `FDOTHER.DAT` #31 | `0x026a63` | `0x25c63` |
| `AIL_set_sample_type` wrapper | — | `0x393c6`(真呼叫 `0x41280`) |
| `AIL_set_sample_playback_rate` wrapper | — | `0x395fc`(真呼叫 `0x412c0`) |

第 8 輪的**邏輯結論不受影響**(表結構、AIL 呼叫鏈、巢狀容器判讀皆正確),僅絕對位址數字需依上表換算;
`doc13`(選單游標 `0x1864D` 等)不受影響,經抽查該位址用同一支工具反組譯內容正確對得上(方向鍵掃描碼
比對邏輯),偏差只出現在第 8 輪 SFX 段落記錄的位址。

## 事件→樣本對照(第 9 輪)

### 呼叫慣例(已確認)

`play_sfx_a`/`play_sfx_b` 呼叫端固定 3-push 慣例:

```
push priority      ; 觀察到的呼叫端全部是常數 1(唯一例外見下)
push index          ; UI 池全部是常數 0 .. 0xc(見下表);其他池有暫存器(動態 index)
push table_ptr       ; 通常是 [0x53eec](UI 音效池),戰鬥路徑另有動態表(見下)
call 0x25a96         ; (或 0x25b45 = handle B,允許與 handle A 疊播)
```

全 EXE 掃描(遞迴找 `call 0x25a96`/`call 0x25b45` 的相對呼叫端,而非線性 sweep,避免誤判):
`play_sfx_a` **111 處**、`play_sfx_b` **11 處**(續一百八十由 `ev_s180.py` 重算並鎖住;原本寫的 107 出自 2026-07-02,沒有留下
產生器,無法重現,`tools/fd2_sfx_static_reachability.py` 2026-09-04 已數到 111)。table_ptr 除了 `[0x53eec]`(UI 池,本篇 14 個樣本)外,
還有 `[0x53b13]`、`[0x54117]`、`[0x5411f]`(= 第 8 輪記錄的 `[0x5411f]`,戰鬥動態表,前綴 `0x54` 打字誤
差 1 位)三個**不同的資源**,不是同一批 14 個 UI 樣本——**戰鬥音效與本篇 UI 音效是兩個獨立池**,對照
時不要混用。

### `[0x53eec]`(UI 音效池,對應本篇 WAV)index 語意

前四欄由 `evidence/generators/ev_s180.py` 逐格核對(續一百八十):靜態呼叫端 = 推本池與該 index 的路徑數(含經無條件 jmp 跳進共用尾端的),
防拷問答函式唯一的呼叫點前面是無條件 jmp、走不到(續一百七十九);函式名取 `docs/data/function_names.json`;
「cl1 .. cl14 次數」是續一百零七那 12 份 DOSBox-X 呼叫紀錄以本池實際播放的次數(每個入口只記前 200 次,只代表「有沒有出現」,不是頻率),
每一次的返回位址都是同 index 的某個靜態呼叫端。改這四欄而沒有同步程式碼,`ev_s180.py` 就失敗。

| index | 靜態呼叫端 | 呼叫端函式(登錄名) | cl1 .. cl14 次數 | 觸發情境 | 信心 |
|---|---|---|---|---|---|
| 0 | A 36 / B 0(防拷 1 處走不到) | `target_cursor_loop`、`battle_main_input_loop`、`item_grid_select`、`command_grid_select`、`town_hub_main`、`carousel_menu_select`、`item_list_select`、`choice_box_left_right`、`equip_compare_select`、`sortie_member_select`、`copy_protection_password_check` | 131 | 各種選單 / 游標的方向鍵分支(`cmp eax,0x48/0x50/0x4b/0x4d`,如 `0x117a1`/`0x11a33`/`0x11a54`/`0x11a75`/`0x11a96`);2026-09-07 實機在其中 4 處命中且與所按方向對應 | **確認:游標移動音** |
| 1 | A 1 / B 0 | `town_hub_main` | 12 | `0x265a7`:按鍵 0x1c / 0x20(`[0x53f4a]` ≠ 2)時放,接著進 `town_hub_select`(續一百八十一 `ev_s181.py`) | **確認:城鎮選設施**(續一百八十四實機:選酒店按 Return → 進酒店) |
| 2 | A 3 / B 0(防拷 2 處走不到) | `typewriter_tick`、`copy_protection_password_check` | 1846 | `0x16546`:對話 / 訊息逐字顯示時每字一次(doc14);2026-09-08 實機在按鍵開訊息時命中這裡 | **確認:對話打字音** |
| 3 | A 1 / B 0 | `unit_death_sweep` | 0 | `0x1ddaa`:掃出 HP 0 且未標記死亡的單位、跑動畫後標記;2026-09-07 實機以 HP 0 / 上限 0 的存檔觸發命中 | **確認:陣亡音** |
| 4 | A 2 / B 0 | `rest_hp_recover`、`battle_phase_advance` | 0 | `0x1a3df`:回合開始時只有我方有人受傷才播,接著 HP += 上限 / 5(2026-09-07 實機正反對照);`0x1403d` 在 `rest_hp_recover` | **確認:回血音** |
| 5 | A 4 / B 0 | `unit_info_cards`、`info_card_open_anim`、`save_slot_selector`、`sortie_member_select` | 31 | 面板展開迴圈(由 0xb 往下數)在第 0xb / 5 格放:`info_card_open_anim` `0x17ede`、`sortie_member_select` `0x2b08a`;法術列表畫完 `0x17c56`、存檔欄畫完 `0x29c8a`。cl1 .. cl14 每一次 `unit_info_cards` 的播放順序都與靜態預測相同(續一百八十一 `ev_s181.py`) | **確認:面板展開**(2026-09-04 / 09-08 兩次實機各看到一段,不矛盾) |
| 6 | A 3 / B 0 | `unit_info_cards`、`sortie_member_select` | 16 | 面板收起迴圈(由 0 往上數)在第 0 / 7 格放:`unit_info_cards` `0x17d26`、`sortie_member_select` `0x2b1f1`;`0x17b2e` 只在已習得法術數非 0 時、裝備卡收走換法術列表時放 | **確認:面板收起**(同上) |
| 7 | A 4 / B 1(防拷 1 處走不到) | `battle_main_input_loop`、`save_slot_selector`、`sortie_member_select`、`copy_protection_password_check` | 37 | `0x1193a`:游標下沒有可行動的我方單位時按確認;2026-09-07 實機兩次命中 | **確認:無效選取音** |
| 8 | A 2 / B 0 | `action_ring_open`、`action_ring_close` | 4 | `0x17495`(`action_ring_open`)/ `0x176d3`(`action_ring_close`) | **確認:行動環開 / 收**(續一百八十四實機) |
| 9 | A 1 / B 0 | `play_step_sfx` | 228 | `0x322c7`:步態 0 每 6 步、1 每 4 步(doc35 §16.4),經 `0x322c9` jmp 到 `0x32301` 的共用尾端 | **確認:腳步音** |
| 0xa | A 1 / B 0 | `play_step_sfx` | 57 | `0x32280`:`0x1f183` 回傳非 0 時每 6 步,經 `0x32282` jmp 到同一尾端 | **確認:腳步音** |
| 0xb | A 1 / B 0 | `play_step_sfx` | 0 | `0x322ff`:步態 2 / 3 每 9 步,直落到同一尾端;步態 2 / 3 = 職業 3 / 11 / 15 / 19(騎士 / 聖騎士 / 龍劍士 / 龍騎士)。cl1 .. cl14 沒有這些職業走路 | **確認:腳步音(這四個職業)**(續一百九十,lc184a 呼叫紀錄:6 次全是亞雷斯(騎士)走路,636 次 `play_step_sfx` 逐次預測全中;「騎乘」是由職業名推的,INFERRED) |
| 0xc | A 0 / B 2 | `ai_mode_dispatch`、`field_cell_treasure_check` | 0 | `0x13d13`(AI 模式 5 走到 `+0x3d` 指定的可見寶箱格、開走之後;金錢寶箱也放)/ `0x191a9`(寶箱 `yes_no_prompt` 回答「是」之後),用 handle B 與 handle A 疊播 | **確認:寶箱打開**(續一百八十四實機,`field_cell_treasure_check` 那處;`ai_mode_dispatch` 那處續一百八十五靜態:敵方模式 5 搶寶箱;續一百八十六實機:第 10 張圖盜賊搶寶箱 5 次都放 0xc,見 doc98 該節) |

續一百八十的更正:舊表 0xb 列寫的 `0x2cac3` 不是呼叫端(該處是 `cmp`,2026-09-07 實機已發現);舊表沒有 index 1 / 0xa;
index 8 / 0xc 各有 2 處、index 4 多一處 `rest_hp_recover`。`docs/data/ui_sfx_index_semantics.json` 撤回的「`0x32307` 放 index 10」
其實成立 —— 那次只看到 `0x32307` 尾端合併的 9 / 0xb,漏了 `0x32280` 的 `push 0xa`;cl1 .. cl14 看得到 index 10 共 57 次,全來自這個尾端。
該 json 的 index 2「UI 主迴圈動畫 tick」說法也已由 doc14 / 函式登錄表(2026-09-19)取代。實機紀錄的來源見該 json 的 `_live_*` 各節。

續一百八十(二)(`evidence/sfx_dialogue_step_s180b_20261101.json`,產生器 `ev_s180b.py`;DOSBox-X 呼叫紀錄 cl1 .. cl14):
- index 2 對到的句子:每次 `typewriter_tick` 歸到最內層包住它的 dialog(`0x15f84`)呼叫,取其文字表(指標處 32 位元組 = 某個 FDTXT 資源開頭)與字串索引。
  2239 次裡 1258 次歸得到,共 15 句:序章 FDTXT_002 #0 .. #2(羅德鎮)、FDTXT_003 #0 .. #3(賽拉村前的橋)、FDTXT_033 #0 / #1(晉見父王),
  與 FDTXT_000 的系統提示(#513「要進入戰場嗎?」、#419 / #420 結束回合、#415 / #416、#585)。其餘 981 次都在 dialog 已記滿 200 次的紀錄裡、
  落在最後一次記到的 dialog 返回之後 —— 是紀錄上限,不是沒有對話。
- index 9 / 0xa / 0xb 的單位:`play_step_sfx` 的第 1 個參數(單位索引)在 cl1 .. cl14 有 17 種,呼叫端是 `step_anim_left` / `step_anim_right` /
  `step_anim_down` / `end_player_phase_if_all_acted`。單位索引對到哪個角色要看當時的單位表,沒有對。
  (續一百八十二,`ev_s182.py`:1626 次全部由紀錄本身的單位記錄傾印對到 —— 第 1 張圖 0 索爾、5 / 7 / 9 男村民、6 / 8 / 10 女村民、11 盜賊;
  第 2 張圖 6 鐵諾、7 士兵;第 32 張圖 2 索爾;第 10 章 CONTINUE 0 索爾、13 .. 19 獸人 / 獸人隊長、38 珊。種族 4 / 5 的只放 0xa,其餘只放 9。
  FDFIELD 建構單位的名稱是 INFERRED,見 doc98 續一百八十二。)
  (續一百九十,`ev_s190.py`:cl1 .. cl14 沒有 0xb 是因為走路的單位沒有職業 3 / 11 / 15 / 19。續一百八十四 lc184a 開場有 6 次 0xb,
  全是亞雷斯(角色 4、職業 3 騎士);用當時 debugger 讀出的單位表與全域計數器 `[0x54132]`(開機 0、只有 `play_step_sfx` 讀寫)逐次模擬,
  636 次放 / 不放與 index 全中,其他起始值與三個對照模型都不符。職業表值 0(週期 6)那支仍沒有走路資料。)

續一百八十一(`ev_s180b.py` (C) 段、`ev_s181.py`;DOSBox-X 呼叫紀錄 cl1 .. cl14、FD2.EXE):
- 打字音改用 `typewriter_tick` 自己的文字游標(第 4 個參數,每字 + 2;指標處 32 位元組 = 游標之後的 FDTXT 字碼)對 FDTXT 位元組:
  2239 次全部歸到字串,共 46 句;包得住的 1258 次與 dialog 參數歸屬逐次相同,上面「其餘 981 次」也都對到了(多是 FDTXT_000 的系統句)。
  「每句打字音次數 = 字數」不成立(按鍵一次跳過,同一句 26 .. 76 次)。
- index 5 / 6:展開 / 收起迴圈放音的格數與 `unit_info_cards` 的順序見上表;cl1 .. cl14 沒有出現「沒有已習得法術」那一支。(續一百八十四實機:盜賊的資訊卡 `unit_list_bits_1a` 回 0,播放 5, 5, 6, 6,一鍵收起)
- index 1 / 8 / 0xc 的語意由呼叫情境與登錄名推(INFERRED),沒有畫面。(續一百八十四:實機看到,見上表與 doc98 該節)

### 戰鬥音效(`[0x5411f]`/`[0x54117]`/`[0x53b13]`)與本篇 UI 池的關係澄清

`[0x5411f]` 在 `0x28f24`/`0x28f49`(第 8 輪位址,未受本輪位址勘誤影響——已抽查落在合理範圍)呼叫
`0x11fba`(通用容器資源載入)**動態載入 FDOTHER.DAT 的另一個子資源**,把回傳指標存進 `[0x5411f]`,
再拿它當 `table_ptr` 呼叫 `play_sfx_a`(index 常數 1/2/3/-1,見 `0x2621f`/`0x2671d`/`0x265b9`/`0x2855a`
等)。即戰鬥音效走的是**攻擊資料決定的另一個容器**,不是本篇解開的資源 #31 這 14 個樣本——第 8 輪
待辦「戰鬥音效逐招對照」須先確認 `0x11fba` 在戰鬥路徑載入的是哪個資源 index,才能導出對應 WAV,
與本篇 UI 池分開處理。`[0x53b13]`(另一獨立表,見 `0x1c309`/`0x1d50a` 等,`index=-1` 疑為「靜音/取消
播放」旗標)用途待查,同樣不是資源 #31。

## 取樣率:負向證據(第 9 輪)

`tools/le_xref.py` 找到 EXE 內確有 `AIL_set_sample_type`(字串 linear `0x50858`)與
`AIL_set_sample_playback_rate`(字串 linear `0x508d7`)兩個完整 wrapper(分別在 linear `0x393c6`
真呼叫 `0x41280`、`0x395fc` 真呼叫 `0x412c0`)。**但**:

1. 用遞迴 call-graph(掃全 code segment 找 `call 0x393c6`/`call 0x395fc` 的相對呼叫端)只找到
   5+6 個呼叫端,**全部落在 `0x41800`–`0x45a00` 範圍**——這段是 Miles AIL SDK 自己的內部函式聚集區
   (非 FLAME2 game logic 範圍,`0x10000`–`0x38000` 才是遊戲自己的程式碼)。
2. 反組譯其中一個呼叫端(`0x418a5`–`0x418ae`)看到經典 Sound Blaster DSP「Time Constant」公式:
   `movzx ebp, byte[edi+4]`(讀一個 byte)→ `mov eax,0x100; sub eax,ebp`(`256 - tc`)→
   `xor edx,edx; mov eax,0xF4240`(`1,000,000`)→ `div ebp` → `rate = 1000000 / (256 - tc)`。這是
   **Creative Voice File(.VOC)區塊標頭**的標準欄位配置(byte 4 = 頻率除數),說明這是 AIL SDK
   內建的「.VOC 檔泛用載入器」,不是 FLAME2 專屬程式碼。
3. 反查 `play_sfx_a`/`play_sfx_b`(`0x25a96`/`0x25b45`)、handle 配置後(`0x25c43`/`0x25c56`)、以及
   戰鬥音效路徑(`0x28f24` 一帶),**都沒有呼叫 `AIL_set_sample_type`/`AIL_set_sample_playback_rate`**。
   在整個 code segment(`0x10000`–`0x38000`)搜尋 `push 8000/11025/22050/44100` 立即數也**零命中**。

**結論**:遊戲自己的 SFX 播放路徑從未顯式設定樣本格式/取樣率,這兩個 API 只在 AIL SDK 自帶但**未被
遊戲呼叫**的 `.VOC` 載入器內出現(靜態連結進來的死碼,或只給其他用途保留)。實際取樣率應由 `.DIG`
驅動的預設輸出格式決定(driver-level default,而非 per-sample 設定)——這條線需要追 `.DIG` 驅動初始化
(`AIL_startup` 一類呼叫)才可能挖到,超出本輪範圍。`11025Hz/8-bit` 維持**推定值**,但現在有明確的
「查過、查無呼叫端證據」記錄,避免後續重複查找同一批 wrapper。

**續一百六十一**:上面「由 `.DIG` 驅動的預設輸出格式決定」的推測不需要了 —— 預設值在 `AIL_init_sample` 裡(`0x39584` → `0x414e0`,`+0x3c` = `0x2b11` = 11025、`+0x34` = 0;FD2.EXE 反組譯)。`AIL_set_sample_playback_rate`(`0x3994c`)的 5 個呼叫端都在 AIL 的檔案載入函式裡(`0x41b84` / `0x41deb` / `0x458f0`),從 main(`0x25bf4`)沿直接呼叫到不了(`callgraph_le.py` 的可達集;對照組 `0x25b03` 到得了)。證據 `evidence/timer_base_and_delay_slowdown_s161_20261028.json`。

## 工具

`tools/le_xref.py`(字串/call xref)+ `tools/unpack_dat.py`(容器解包,含巢狀容器直接可用同一支
`parse_directory` 邏輯手動遞迴)。本輪額外用 capstone(`docker fd2-cap` 已內建)做逐指令交叉驗證 ──
專案既有 `tools/disasm_le.py` 在部分 range 有指令邊界誤判問題(如 `0x25a96` 一帶會錯位),遇到可疑
反組譯結果時改用 capstone 從已知正確的函式起點(如 `play_bgm=0x26777`)線性反組譯校正。

## ⚠ 位址勘誤第二輪(第 10 輪發現):通用容器載入函式真址是 `0x111ba`,不是 `0x11fba`

第 8/9 輪全文引用的「通用「載容器資源」函式 `0x11fba`」**本身也是同一種 file-offset-當-linear 誤差**
(`0x11fba − 0x111ba = 0xE00`,與第 9 輪已修正的 `play_sfx_a/b` 誤差同一固定偏移)。第 9 輪的位址勘誤
只重新核對了 `play_sfx_a/b`/`[0x53eec]` 載入點一段,**沒有連帶回頭核對 `0x11fba` 這個數字本身**,
導致它原封不動地被第 9 輪沿用、繼續傳播。

**直接反組譯驗證**:在 `0x111ba` 找到的函式内容 ── 開檔(`call 0x36fcc`,帶字串 id `0xde`)→
用 `index*4+6` 讀目錄 offset(與 `LLLLLL` 容器格式的 `+6` 起始目錄欄位定義完全吻合)→ 算長度 → malloc
→ 讀檔,是名副其實的「通用容器資源載入」函式;`0x25c70`(`[0x53eec]` 載入 `FDOTHER.DAT` #31 處,
第 9 輪已修正的正確 linear)、`0x28129`/`0x2814e`(下方戰鬥音效載入處)、`0x033a1e` 一帶等所有
「載某個具名容器檔」呼叫端,反組譯後 `call` 目標都是 `0x111ba`,無一是 `0x11fba`。

**本文件先前所有寫作「`call 0x11fba`」之處,一律理解為 `call 0x111ba`**(含第 2 節「表從哪來」、
第 3 節「戰鬥/攻擊音效」、`.DIG` 角色釐清表格、重製對應表)。第 9 輪已修正過的 `play_sfx_a/b`/
handle 配置/`[0x53eec]` 等位址不受影響(那批本來就是第 9 輪核對過的正確值)。

## 戰鬥音效池(第 10 輪)

### `[0x5411f]` 載入點:linear `0x028110`–`0x028156`(取代第 8 輪誤記的 `0x28f24`/`0x28f49`)

反組譯出的真實函式(入口 `0x027fc9`,標準 `push 0x6c; call 0x36cd7` 頻框序言,兩個參數:
`[esp+0x4c]` = 單位索引(進 `[0x53a45]` 起、stride 80 bytes 的隊伍/單位表)、`[esp+0x50]` = 招式/動作 id):

```
0x028110  mov   eax, [esp+0x50]          ; eax = 招式/動作 id
0x02811e  add   eax, 0x21                ; index1 = id + 0x21
0x028121  push  eax
0x028122  push  0                        ; old_ptr(釋放用)= 0
0x028124  push  0x1a4d                   ; ->0x51a4d = "FDOTHER.DAT"
0x028129  call  0x111ba                  ; 通用容器載入(第 10 輪修正後真址)
0x028131  mov   edi, eax                 ; 結果存 edi,不進 [0x5411f](供其他用途,疑動畫/招式資料)
0x028133  mov   dword ptr [0x411f], 0    ; [0x5411f] 先歸零
0x02813d  mov   eax, [esp+0x50]          ; 重讀招式 id
0x028141  movzx eax, byte ptr [esp+eax-0xc]  ; index2 = 由招式 id 索引的區域性 byte 陣列(第二個動態值)
0x028146  push  eax
0x028147  push  0
0x028149  push  0x1a4d
0x02814e  call  0x111ba                  ; 第二次載入 —— 這次的結果才是真正的 SFX table_ptr
0x028156  mov   dword ptr [0x411f], eax  ; [0x5411f] = 本次載入結果
```

**結論**:`[0x5411f]` 的值來自**第二次** `call 0x111ba`,index2 是「以招式 id 為 index,查一個位於呼叫端
局部堆疊(`esp-0xc` 附近)的 byte 陣列」算出來的,**該陣列的填值來源本輪未追出**(需要往更早的招式資料
載入路徑回溯,超出本輪「簡查不深挖」的範圍,標記待確認)。第一次 `call 0x111ba`(index1 = 招式id+0x21)
載的資源存進 `edi`,不是 SFX table_ptr,用途待確認(疑為招式動畫/特效資料,非本篇範圍)。

### 候選戰鬥 SFX 資源家族:`FDOTHER.DAT #48/#49/#50/#51/#52/#53/#64/#78/#88`

因 index2 是動態值,本輪改用「PCM 特徵掃描」反向驗證:對 `FDOTHER.DAT` 全部 104 個資源做巢狀
`LLLLLL` 偵測 + byte 值分布統計(平均值/標準差/值域),排除掉明顯是圖檔的巢狀容器(`#7`/`#12`/`#63`,
sub0 開頭 `40 01 c8 00` = `0x140,0xc8`=320×200 VGA 解析度標頭、std≈80、值域鋪滿 0–254),
篩出以下 9 個「所有子項都集中在 128 附近、std 個位數~20 幾、值域窄」的候選,判讀為戰鬥 SFX 池:

| 資源號 | 子樣本數 | 備註 |
|---|---|---|
| #48 | 7(6 有效) | |
| #49 | 8(7 有效) | |
| #50 | 6(5 有效) | |
| #51 | 6(5 有效) | |
| #52 | 7(6 有效) | |
| #53 | 5(4 有效) | |
| #64 | 7(6 有效) | |
| #78 | 2(1 有效) | 只有一個真樣本 |
| #88 | 3(2 有效) | **唯一有固定 index 佐證**(見下) |

**關鍵佐證**:`#48`/`#49`/`#50`/`#51`/`#52`/`#53`/`#64` 這 7 個資源的 **sub0 完全逐位元組相同**
(`len=4182, mean=122.2, range=[47,204]`)── 同一份「共用音效」(疑為通用揮擊/命中聲)被複製進每個
武器/職業分類的池子裡,每個池子另外再帶自己專屬的幾個音效,這正是「每個武器/攻擊分類一個容器,
內含共用音 + 專屬音」的典型遊戲資料設計,支持「這批就是戰鬥 SFX 池家族」的判讀。

### `#88`:唯一確認的**常數 index**戰鬥音效載入點(linear `0x033987`)

```
0x033979  mov   dword ptr [0x3b13], 0
0x033983  push  0x58                     ; index = 0x58 = 88(十進位),常數,非動態
0x033985  push  0
0x033987  push  0x1a4d                   ; "FDOTHER.DAT"
0x03398c  call  0x111ba
0x033994  mov   dword ptr [0x3b13], eax  ; [0x53b13] = 資源 #88
...(後續固定座標繪圖 + 3 次 play_sfx_a(index=1) 疊播,疑為固定特效/事件演出,非一般攻擊)
```

這是本輪唯一**直接反組譯證實**的具體 index(`#88`),其餘 `#48`–`#64`/`#78` 是 PCM 特徵比對推斷,
未各自反組譯出對應的常數/動態載入點,標記「候選,未逐一證實」。

### `[0x54117]` 簡查:並非走 `0x111ba` 容器載入

`[0x54117]` 在 xref 中最常見的寫入點(linear `0x0288d7`)是 `mov [0x54117], eax`,但 `eax` 來自
`call 0x2bc9a`(非 `call 0x111ba`)── 即這個位置的 `[0x54117]` 不是「載某個容器資源」的回傳指標,
可能是別的函式回傳值(次數/handle 之類)。`[0x53b13]` 上方已證實走 `0x111ba` + 常數 index `#88`。
`[0x54117]`/`[0x53b13]` 的完整語意(是否也在其他呼叫點走動態 index)未逐一深挖,留待後續。

## `index2` 陣列填值來源追蹤(第 11 輪,部分解出)

延續第 10 輪待辦「`[esp+eax-0xc]`(index2)陣列填值來源未追」,本輪往呼叫鏈上游深挖,結論寫入
`docs/data/battle_sfx_map.json`(含完整位址證據)。摘要:

1. **`0x027fc9`(`[0x5411f]` 載入函式)本身的 `[esp+id-0xc]` 不是它自己宣告的穩定陣列**——該位址落在
   函式自身 `sub esp,0x38` 宣告的 0x38-byte 區域之外/邊界上,只有 `id` 落在特定範圍(20/24/28/32)時才會
   讀到函式一開始存的 4 個全域快照值(`[0x2554f]`/`[0x52553]`/`[0x52557]`/`[0x5255b]`,esp+8/0xc/0x10/0x14
   四個 dword),其餘 `id` 值讀到的是未初始化/暫存 push 殘值——**不是一張正規查表**。
2. **`0x027fc9` 唯一 caller**:`0x02a6bd`(呼叫點 `0x02a7ce`)。招式id = `0x02a6bd` 的第 2 參數
   (讀進 `ebp`,`0x02a6d1`),且只有 `ebp>=0x20` 才會呼叫 `0x027fc9`(`0x02a7b3 cmp ebp,0x20;jl skip`)。
3. **`0x02a6bd` 有兩個 caller**,id 語意可能不同:
   - `0x015400`(`0x015311` 函式內):id = `call 0x014818` 的回傳值。反組譯 `0x014818` 發現這其實是
     **地圖 AoE/範圍距離標記函式**(在 `[0x53a51]` 地圖旗標陣列寫 `0xff`,依 `[0x3ac1]`/`[0x3ac5]`
     地圖寬高 + 半徑參數判定),不是單純的「招式編號查表」——此路徑 id 的真實語意存疑,未追到函式
     真正 `ret` 處確認回傳值定義。
   - `0x01d43c`(`0x01cff0` 函式內):id = `byte ptr [esp + [0x3c57] + 0xd0]`,`[0x3c57]` 是目前步驟計數器。
4. **意外收穫**:`0x01cff0` 內有一個**平行陣列** `[esp+0xc8+counter]`(比對 `9`/`0x17`/
   `0x18`/`0x1b`/`0x1e`),其填值來源**已追出**:`0x01d150 lea eax,[esp+0xc8]; push eax; push [資料
   指標]; call 0x1c269`。`0x1c269` 的 direct body 只定案為：從單位資料表
   (`[0x53a45]+idx*80`)偏移 `+0x1a` 起掃描 **5 bytes(40 bit)**，把已設定 bit 轉成 0–39 byte index，
   寫入呼叫端緊密陣列；輸出究竟是 spell、move 或其他 command inventory 仍未證實。
   - `unit+0x1a..+0x1d` 與 FDFIELD `initial_command_mask` 複製範圍重疊；它是 runtime 五位元組 command bitset 的初始四位元組。`unit+0x22..+0x24` 則是 constructor 清零後由能力流程寫入的 raw transient/modifier bytes；其 derived-stat/property/status 名稱仍待完整 caller 證據。不得用後者反推前者的 spell bitfield。
   - 但 `0x027fc9` 真正讀取的是 **`[esp+0xd0+counter]`**(offset 0xd0,與 `0xc8` 相差 8,且並非同一次
     `call 0x1c269` 填的緊密陣列——`0x1c269` 只填一個目標緩衝區),**這個陣列的填值來源本輪仍未追出**,
     是下一輪的直接切入點。

**結論(一句話)**:`index2`(真正 SFX table_ptr 的 index)填值來源**部分解出**——確認它不是 `0x027fc9`
自己的區域表,而是源自呼叫鏈上游(`0x01cff0` 函式)一個尚未定位填值來源的陣列(`[esp+0xd0+counter]`);
   同一函式內一個平行陣列(`+0xc8`)已完整追出填值來源為 `0x1c269` 的 40-bit bit-scan
(`0x1c269`),是本輪最扎實的具體成果,但與 SFX index2 本身仍隔一層未接上。`docs/data/battle_sfx_map.json`
記錄完整位址證據鏈與候選 FDOTHER 資源池(沿用第 10 輪 PCM 特徵掃描結果,未變動)。

## ⚠ 位址勘誤第三輪 + 逐招對照突破(第 12 輪,2026-08-19)

**本輪任務**:worklist L584/604/622(三項同一件事:「逐招對照」核心未解)。改用 Ghidra headless
(`-readOnly -noanalysis`,真正做過 LE 載入的專案 `C:\Users\kg701\Desktop\GAME\FD2_ghidra_projects\FD2Analysis3`,
方法見專案 memory `fd2-live-ghidra-headless-probe`)反組譯 + decompile 交叉核對,取代 `tools/disasm_le.py`
(該工具已知在特定位址範圍反組譯出誤位元組邊界,見專案 memory `fd2-disasm-le-range-bug`)。

**先驗證再信任**:`FD2Analysis3` 專案內部實際載入的 EXE 是 802705 bytes、MD5 `a6e341a8decc6ebf7f4872076d9cf161`
(`currentProgram.getExecutablePath()=/D:/Codex/FD2_extracted/FD2/FD2.EXE`),與 `docs/data/fd2-reference-files.json`
記載的現行基準(509158 bytes、MD5 `33464c81e6a364fd0660141139aa8e6e`)是**不同檔案**。用五個第9/10輪已透過
capstone 交叉驗證過的位址(`play_sfx_a=0x25a96`、`play_sfx_b=0x25b45`、`[0x53eec]`載入=`0x25c63`、
通用容器載入器=`0x111ba`)在 `FD2Analysis3` 內 decompile,結果與文件既有描述逐項語意吻合(guard 條件、
AIL 呼叫序列、三個資源載入順序皆對得上)——確認這兩份 build 在 `0x10000`–`0x40000` 這段程式碼區「位址與
機器碼位元組完全相同」(與 `docs/knowledge-base/58-remake-live-verification-log.md` 先前記錄的「不同 build
但共用區段 byte-identical」現象一致),本輪反組譯結果可放心沿用到現行 509158-byte 基準版本的位址。

**發現位址誤植**:第 10/11 輪手動用 `tools/disasm_le.py` 反組譯出的「`[0x5411f]` 載入函式,入口
`0x027fc9`」是誤判——`getFunctionContaining(0x27fc9)` 在 Ghidra 內查證,`0x27fc9` 實際落在
`FUN_00027f4a`(一個與 SFX 完全無關的「2 選項上下游標選單迴圈」)內部。round 11 描述的上游呼叫鏈**形狀**
是對的(`0x01cff0`/`0x015311` 兩個 caller 確實存在),但中繼位址(`0x02a6bd`)在真實控制流中根本不存在,
它們其實**直接**呼叫下面的 `0x2ff01`,中間沒有那一層。

**真實呼叫鏈**(`ReferenceManager.getReferencesTo` 逐一找 caller,非猜測位址):

```
玩家可用指令 40-bit bit-scan(0x1c269,unit+0x1a..+0x1e,round11 已定案)
  → local_20[] 指令清單(填值函式 0x1cff0)
  → bVar1 = local_20[目前選單 index]   ; 這是 round11「index2」要找的上游語意本體:
                                        ; 玩家目前選中的「指令 id」(bit-scan 輸出,0-39)
  → if bVar1<9 或 ==0x18 或 >0x1b:
        FUN_0002ff01(unit_idx, bVar1, target_count, target_array)   ; 0x2ff01,真正的攻擊/招式總派送函式
          if bVar1<0x20 且不是(==0x18 或 >0x1b):
              走自己的 body ── ~~物理攻擊動畫~~(**2026-09-06訂正：`command_labels.json`證實
              bVar1=0-8是元素攻擊法術火炎術..聖光彈，不是物理攻擊，見本文件下方「仍缺的
              部分」第1點**) + SFX 池載入(見下)
          elif bVar1==0x18 或 0x1c..0x1f:
              呼叫 FUN_0002cf30(0x2cf30)   ; 法術/魔法演出
          else(bVar1>=0x20):
              呼叫 FUN_0002d80d(0x2d80d)   ; 另一組(id 0x20-0x23,四類特殊演出)
    else(bVar1 落在 [9,0x17] 的合法值):
        (**(DAT_00051d01 + bVar1*4))()   ; 個別指令 id 專屬處理函式指標表(9-23),未逐一展開,超出本輪範圍
```

`FUN_0002ff01` 的兩個 caller 正是 `0x01d43c`(在函式 `0x1cff0` 內)與 `0x015400`(在函式 `0x015311` 內)——
**round11 找到的這兩個 caller 位址本身是對的**,只有它們原本以為的中繼函式(`0x02a6bd`/`0x027fc9`)是
`disasm_le.py` 誤解析出的錯誤數字。

**攻擊 SFX 池 index 表的真身:資料段一段固定 byte array,linear `0x0526bc`**

`FUN_0002ff01` 一進函式就把 `0x0526bc` 起的資料(四小段,各自用 `MOVSD/MOVSD/MOVSW`(或 `MOVSB`)複製)
搬進堆疊區域變數,稍後用 `movzx eax, byte ptr [esp + bVar1 + 0xa4]`(linear `0x3026c`)讀出「這個
指令 id 該載入 `FDOTHER.DAT` 的哪個資源號」,寫進 `DAT_00054153`(這才是「戰鬥 SFX table_ptr」的真身,
取代第 10/11 輪誤記的 `[0x5411f]`/`[0x54117]`;後續 `push dword ptr [0x00054153]` 直接餵給
`play_sfx_a`/`play_sfx_b`,已用原始反組譯逐一核對過,見 `docs/data/battle_sfx_map.json`)。已用 Ghidra
直接 dump `0x0526bc` 起 48 bytes 原始資料,並用同一段程式碼裡 `LEA EDI,[ESP+0x98/0xa4/0xb0/0xbc]` 四個
複製目的位址反推出每一段的堆疊落點,得到完整 id→資源號對照,並逐一解包 `FDOTHER.DAT`(md5
`0496698f0ac67a3ff2448d8c7d80113f`,與現行基準檔一致)驗證資源型態:

| action_id(bVar1) | 全域來源位址 | FDOTHER.DAT 資源號 | 解包驗證 |
|---|---|---|---|
| 0 | 0x526d9 | **82** | ✅ LLLLLL,3 subs(2 有效 PCM) |
| 1 | 0x526da | **82** | 與 id0 共用同一份資源 |
| 2 | 0x526db | **83** | ✅ LLLLLL,5 subs(4 有效) |
| 3 | 0x526dc | **84** | ✅ LLLLLL,4 subs(3 有效) |
| 4 | 0x526dd | **85** | ✅ LLLLLL,3 subs(2 有效) |
| 5 | 0x526de | **86** | ✅ LLLLLL,3 subs(2 有效) |
| 6 | 0x526df | **87** | ✅ LLLLLL,5 subs(4 有效) |
| 7 | 0x526e0 | **88** | ✅ LLLLLL,3 subs(2 有效)(與第10輪常數index載入點`0x033987`巧合命中同一資源) |
| 8 | 0x526e1 | **89** | ✅ LLLLLL,4 subs(3 有效) |
| 9 | 0x526e2 | **90** | ✅ LLLLLL,4 subs(3 有效) |
| 12 | 0x526cf | 20 | ❌ 不是 LLLLLL(非 SFX,型態未鑑定) |
| 13 | 0x526d0 | 21 | ❌ 未逐一驗證(同一批,推定非 SFX) |
| 14 | 0x526d1 | 27 | ❌ 同上 |
| 15 | 0x526d2 | 43 | ❌ 同上 |
| 16 | 0x526d3 | 23 | ❌ 同上 |
| 17 | 0x526d4 | 25 | ❌ 同上 |
| 19 | 0x526d6 | 38 | ❌ 同上 |
| 20 | 0x526d7 | 30 | ❌ 同上 |
| 21 | 0x526d8 | 44 | ❌ 不是 LLLLLL(已驗證) |
| 25 | 0x526c7 | 19 | ❌ 不是 LLLLLL(已驗證) |
| 26 | 0x526c8 | 26 | ❌ 不是 LLLLLL(已驗證) |
| 27 | 0x526c9 | 39 | ❌ 不是 LLLLLL(已驗證) |
| 10, 11, 22, 23 | 落在四段複製之間、未被任何一段覆蓋的兩個 2-byte 缺口(`0x98`-`0xa1`/`0xbc`-`0xc4`/`0xb0`-`0xb9`/`0xa4`-`0xad` 四段之間的 `0xae`-`0xaf`、`0xba`-`0xbb`) | 未初始化 | 讀到的是堆疊殘值,語意不明,標記待查 |
| 18(=0x18)、0x1c-0x1f | N/A | — | 改走法術分支(`FUN_0002cf30`),不查這張表 |

**id=0-9 逐一解包驗證**(直接讀 `FDOTHER.DAT` 目錄,已用 `tools/export_sfx.py --actionid` 匯出全部
25 個有效 WAV 到 `remake/assets/sfx/actionid_<資源號>_<子序>.wav`):資源 `#82/83/84/85/86/87/88/89/90`
全部是巢狀 `LLLLLL` 容器、逐項 8-bit unsigned PCM(值域集中 0x80 附近),且 **sub0 對這 9 個資源逐位元組
完全相同**(`82 80 7a 80 80 79 80 85 7c 80 80 76 80 82 79 80 …`,6561 bytes)── 與第 10 輪已記錄的
「共用揮擊音 + 各池專屬音」設計完全吻合。資源 `#19/20/21/26/27/30/38/39/43/44`(action_id 12-21/25-27
範圍)逐一檢查皆**不是** `LLLLLL` 容器(不同 magic bytes),證實這個 id 範圍載入的不是音效資源。

**與第 10 輪候選家族的關係**:第 10 輪 PCM 特徵掃描獨立找到的候選池 `#48/49/50/51/52/53/64/78`
與本輪動態追出的真實家族 `#82-90` 是**兩個不同、相鄰的資源家族**,僅 `#88` 重疊(第10輪常數 index
載入點 `0x033987` 與本輪 action_id=7 的動態載入,巧合指向同一份資源)。`#48-53/64/78` 目前仍只有 PCM
特徵佐證,未找到任何動態/常數載入點的反組譯證據 ── **維持第10輪「候選,未證實載入點」狀態,不因本輪
而升級**。

**remake `atkAnim` 現有 SFX hook 點對照**:`remake/cmd/fd2/main.go` 的 `atkAnim`(struct 定義
`:420`,揮擊/命中/陣亡播放點 `:5794-5800`)**已經**掛了 SFX,但用的是第10輪未證實載入點的候選池
(`g.sfxSwing=battle_48_00.wav`、`g.sfxImpact=battle_64_00.wav`、`g.sfxDeath=battle_88_00.wav`,
載入處 `:8910-8912`,程式碼註解已誠實標註「近似:...;attack_id→sfx 對照表 doc36 未 RE」),對**所有**
攻擊一律套用同一組固定音效,不分 action_id。本輪找到的 `actionid_82_00.wav`..`actionid_90_00.wav`
(9 個真正動態驗證過、逐 action_id 對應的池)尚**未**接進 remake ── 要接上仍缺「action_id 從哪個
remake 資料結構取得」這一層(remake 的攻擊資料模型目前無 0-39 範圍的原生 action_id 欄位),以及上面
仍未解的「招式中文名稱↔action_id」對照,故本輪不動 remake 程式碼,只記錄現狀供下一輪接線參考。

**id≥0x20 分支(`FUN_0002d80d`,即第10/11輪原本誤以為是 `0x027fc9` 本身內容的那段邏輯)**:在正確位址
重新核對後確認,其內部同樣是「`id+0x21` 載入一次 `FDOTHER.DAT`,再用一個 `byte[&pcStack_54 + id]`
動態值載入第二次,結果同樣存進 `DAT_00054153`」的兩段式載入模式 ── 但這次的 index 來源是這個函式
**自己**的另一塊堆疊暫存區,不是 `0x526bc` 那張全域表。round11 對(當時位址錯誤的)
`0x027fc9`「並非編譯器宣告的穩定陣列」這句評語,套用在正確位址 `0x2d80d` 上依然成立。

> **2026-08-24 續輪(doc27 §6.5)追出並關閉**:原始反組譯確認 `0x2d981..0x2d985` 的
> `movzx eax, byte ptr [ESP + commandId*0x1 - 0xc]`──`commandId`(0x20-0x23 全值)直接當 byte
> offset,落在函式序言把單一全域 `DAT_00052668`(一個 dword)存入的 4-byte 堆疊區內。`bytes` action
> 直接 dump `0x52668`:`5b 5c 5d 5e`(十進位 91/92/93/94)。用 `tools/export_sfx.py --res {91,92,93,94}`
> 逐一解包驗證:四個都是合法巢狀 `LLLLLL` SFX 容器(91/94 各 4 個 sub-sample、92/93 各 3 個,sub0 皆為
> 同一份 6561-byte 共用揮擊音,與本節 `#82-90` 家族結構完全同構),resource 編號緊接在 `#82-90` 之後、
> 連號 91-94,對映 id 0x20/0x21/0x22/0x23(32/33/34/35=熾天使/風妖精/破壞神/暗邪鬼)。四個 WAV 已匯出
> 至 `remake/assets/sfx/battle_{91,92,93,94}_{00,01,...}.wav`。**此為本節唯一未解項,現已關閉**;完整
> 四分支(id 32-35 各自呼叫的 native command/buff/status callee 與跟 doc02 攻略文字的三重印證)見
> `docs/knowledge-base/27-combat-rules-and-validation-checklist.md` §6.5。

**仍缺的部分(誠實列出)**:
1. action_id 0-9 對應的玩家可讀招式名稱(劍/斧/拳/弓/…)未解 ── ~~同一函式另外用 `unit.byte[7]`
   選FIGANI.DAT動畫資源,語意上兩者可能共享同一條「武器類別」軸,但未交叉證實~~。**2026-09-06
   撤回這個猜測,理由如下,同時撤回本節同日稍早「doc02 8種武器類別vs7個movement action_id」
   那則假說(建立在同一個錯誤前提上)**：`docs/knowledge-base/06-animation-format.md`(2026-06-29
   已反組譯確認、與本節屬不同輪次)明確記載`unit[+7]`是**戰鬥FIGANI的角色身分selector**——
   `0x287b5`讀`unit[+7]`,`0x2884c`算`×3`(+0/+1兩個攻擊動作幀組)得到FIGANI資源index,已用
   實測值驗證(索爾0→FIGANI0、亞雷斯4→12、盜賊96→FIGANI288)。**這是「這個單位長什麼樣子/
   用哪一套個人肖像動畫」的身分軸,不是「使用哪種武器類別」的招式軸**——doc06自己在同一段落
   也明講「不可和地圖FDICON selector混稱」，屬於角色識別層，跟`action_id`(本節`DAT_000524c6`
   索引,來自`bVar1`即玩家目前選中的指令id,`0x1c269`40-bit可用指令點陣掃描)完全是兩條不同的
   軸,不會共用。**招式名稱交叉對照需要換一條路**：`bVar1`(0-39)是「這個單位目前有哪些指令
   可用」點陣掃描出的**指令id**,不是武器類別也不是角色識別;doc02§6.2「劍技(4招,各自綁定
   特定角色索爾/鐵諾/蜜蒂/羅德曼)」看起來也對不上(那是MP消耗的角色專屬技能,不是`action_id`
   這種跨單位共用、走`FUN_0002ff01`物理攻擊分支的通用id)。**下一輪需要的是找到`bVar1`這個
   0-39指令id空間本身在其他地方(選單UI文字渲染、`0x1c269`點陣掃描的來源資料)有沒有已知的
   逐id命名對照，而不是再猜FIGANI/武器類別/角色技能這幾條已經被排除的軸**。

   **2026-09-06查證,這條路本身在專案既有紀律下也已知會走到瓶頸,誠實記錄而非再猜一個新假說**：
   `docs/knowledge-base/13-battle-menu-system.md`「行動選單選項」一節明文記載——「早期『典型
   戰棋的移動/攻擊/法術/道具/待機/狀態』列舉不是原版證據,已刪除」，且`Get_EasyMagic`一節
   明講「可用command的label、spell-family、個別spell ID對照仍待完成,**不得由raw bit或舊
   M1-M5名稱推導**」。doc13同時證實commands 17-30這個較高id範圍(狀態效果類,與本節action_id
   2/8/9同一種機制家族)已經有「全部七個command的正式名稱」表(2026-08-19/20兩輪反組譯關閉)，
   但那是針對UI native command(`+0x1a..+0x1e`可用指令欄位的更高id段),沒有涵蓋本節0-8這個
   物理攻擊子範圍的具體命名。**結論**:本專案自己已經走過「用結構猜名稱」這條路並在doc13
   明確立下禁止先例(不得由raw bit/舊分類推導)——0-8這個action_id範圍的「招式中文名稱」若要
   在不違反這個既有紀律的前提下解開，只有兩條路:(a)找到commands 17-30那兩輪反組譯用的
   同一種方法(可能是FDTXT字串表或選單render呼叫點)是否也覆蓋0-16範圍、或(b)live DOSBox-X
   實測特定武器攻擊時觸發哪個action_id並對照UI顯示的招式文字。純靜態猜測到此為止,不再
   產生新的「可能是武器類別/可能是角色技能」這類未經驗證的假說，避免違反本專案自己已經
   立下的紀律。

   **2026-09-06再查證,上一段(a)路走通了,`docs/data/command_labels.json`早就涵蓋0-8範圍——
   剛才「沒有涵蓋本節0-8這個物理攻擊子範圍的具體命名」這句話錯了,誠實訂正**：直接讀
   `command_labels.json`(schema `fd2.native_command_labels.v1`,來源`FDTXT_000`,`string_index
   = 0x1b9 + command_id`,provenance鏈`0x1ceed -> 0x15f84`，2026-09-03已用`export_command_labels.py`
   重生驗證過)——**command_id 0-8的正式FDTXT名稱是**：
   0=火炎術、1=烈炎術、2=炎龍術、3=天火術、4=電擊術、5=落雷術、6=轟雷術、7=神雷術、8=聖光彈。
   **這徹底推翻本節開頭把`FUN_0002ff01`own body分支稱為「物理攻擊動畫」的假設——這9個
   command其實全部是元素攻擊法術(火系4個/雷系4個/聖光1個)，doc36從第10/11輪開始的「物理
   攻擊」框架本身是誤植**。這也讓本輪的movement/狀態效果結構分類有了更合理的語意：
   action_id0(火炎術,單向遞增X位移40→120→70)、1(烈炎術,對稱擴散-59↔55)可能對應**火球飛行
   軌跡/爆裂擴散**這類視覺;4/5/7(電擊術/落雷術/神雷術,逐指令同構的單軸10-dword模板)三個
   雷系法術共用同一套簡單模板,吻合「都是同一種雷擊視覺、只是傷害/資源不同」的直覺;6(轟雷術,
   含疑似角度常數)可能是**較廣範圍/較大角度的雷擊**;2(炎龍術,狀態旗標而非位移)、8(聖光彈,
   最小資料量)則需要進一步確認為何用狀態機制而非位移(炎龍術有機會是延續既有全域旗標控制
   一次性演出而非逐幀位移,聖光彈也可能是單發彈道靠別的共用present完成，不需要私有關鍵幀
   表)——**這兩個是本輪唯一還說不通的地方,誠實保留,不強行套進movement敘事**。

   **2026-09-06再查證,action_id9邊界問題已解開,不是doc36文字摘要誤差,而是param_2==9在
   `FUN_0002ff01`本體裡有大量、貫穿全函式的專屬特判邏輯**：直接`decompile FUN_0002ff01`
   全文(3876 bytes,先前輪次只轉述過pseudocode摘要,本輪首次拿到完整偽代碼)確認`param_2==9`
   絕非邊緣case——函式一開頭就有`if(param_2==9){for(iVar3=0;iVar3<0xb;iVar3++){0x11eb0();
   if(iVar3!=10){0x2eb9f();} 0x2eb9f();0x11eb0();} thunk_FUN_0003e01d();}`這段9專屬的
   額外11迴圈前置演出，接著全函式**至少6處**`if(param_2!=9){FUN_0002eb9f();}`型態的條件
   跳過，以及結尾另一段`if(param_2==9){for(iVar3=7;-1<iVar3;iVar3=iVar3+-1){逐步倒數
   4個already-known呼叫}}`收尾演出——這種貫穿整個函式、進場退場都有專屬段落的密度，
   證實`param_2==9`是這個函式刻意支援、常態會被呼叫到的合法輸入，不是「意外落在表尾的
   殘值」。這代表doc36先前引述的「bVar1<9才進own body」這句outer gate condition的文字
   摘要本身確實不夠精確(真正的outer gate應該允許9通過，可能是`<=9`或`<10`，但本輪沒有
   反組譯outer caller`0x1cff0`/`0x015311`本體去確認精確運算子，只確認了`FUN_0002ff01`
   自己接受param_2==9並有專屬邏輯這件事)。**額外發現**:同一段decompile也證實`param_2==8`
   (聖光彈)與`param_2>3`(即4-23範圍)各自觸發`local_54`/`local_64`兩個區域變數的不同
   override值(`0xb0/0x13`、`0xb0/0xf`，預設是`0x20/0xb`)，這是SFX優先度或sub-pool大小
   相關的參數,語意細節未展開，是sub-index觸發時機這個仍開放的子缺口的一部分線索。

   **item 584「招式中文名稱」這個子缺口，對9/10個action_id而言已經解開(引用既有
   command_labels.json,非本輪新解碼，是本輪首次把它跟`DAT_000524c6`結構分類接上)，
   action_id9邊界問題本輪已用完整decompile解開(是合法特判，非誤差)，只剩action_id2/8
   兩個語意不吻合處，與「sub-index觸發時機」(含新發現的`param_2==8`/`>3`兩組override)
   仍待查**。
2. 每個資源池內 2-5 個子樣本各自何時觸發(例如揮空/命中/爆擊分別對應哪個 sub index)未追出 ──
   需要反組譯「每指令動畫函式指標表」`DAT_000524c6[action_id*4]` 的個別函式內容,本輪只定位了表位址,
   未展開。
3. ~~action_id 12-21/25-27 載入的非 SFX 資源型態未鑑定~~ → **2026-09-06反組譯後撤回這個前提,見下方**。
4. ~~action_id 10/11/22/23 落在表的未初始化缺口,語意不明~~ → **2026-09-06反組譯後撤回這個前提,見下方**。
5. ~~`FUN_0002d80d`(id≥0x20 分支)自己的 index 來源未追出~~ → **2026-08-24 續輪已追出並關閉,見上方引述段落**:`DAT_00052668` 四個 byte(91/92/93/94)。

**2026-09-06,`tools/ghidra_batch_probe.py`(`bytes`/`disasm`交叉)反組譯確認:第3、4點的前提本身
是錯的——`DAT_000524c6`不是一個延伸到 action_id 27 的稀疏函式指標陣列,而是恰好 10 個有效函式
指標(action_id 0-9),表本身在 offset `+0x28`(40 bytes = 10×4)就結束了,再往後不是「未初始化的
表格缺口」，是一塊完全不同、緊接在表尾的**共用移動關鍵幀資料區****：

```
0x524c6..0x524ed (40 bytes): 10 個函式指標 (action_id 0-9)
  action_id0: 0x2b996   action_id5: 0x2c441
  action_id1: 0x2bb33   action_id6: 0x2c67d
  action_id2: 0x2bd6c   action_id7: 0x2cafc
  action_id3: 0x2bfd9   action_id8: 0x2ccf4
  action_id4: 0x2c217   action_id9: 0x2ce1a
0x524ee (+0x28, 7 bytes): 每幀 flag/type byte 陣列 = 00 00 01 00 01 00 00
0x524f5 (+0x2f, 28 bytes = 7 dword): X位移關鍵幀 = 40,70,120,80,50,100,70
0x52511 (+0x4b, 28 bytes = 7 dword): Y位移關鍵幀 = 0,-10,-20,0,-15,-5,0
```

反組譯`action_id0`本體(`0x2b996`)逐指令確認它自己就是**唯一直接讀取這三段資料的函式**：
用`MOVSD/MOVSW/MOVSB`把7-byte flag陣列複製到局部stack buffer(`[ESP+0x38]`)，再用兩次
`REP MOVSD(ECX=7)`把兩個28-byte陣列分別複製到`[ESP+0x1c]`/`[ESP+0]`——**X/Y位移數列的形狀
(前段遞增到120再回落、Y值下探到-20再回0)高度符合一個「向前撲擊、身體下沉再回正」的近戰
攻擊動畫關鍵幀曲線**，不是SFX/資源index表。這也解釋了本節開頭「10 個獨立資源」的動作範圍
剛好等於這 10 個函式指標——**原本任務框架裡「action_id 12-21/25-27」「10/11/22/23 gap」的
提法本身建立在錯誤假設上(誤把緊鄰的關鍵幀資料當成表格延伸)，這兩點誠實撤回，不是延伸解開；
真正剩下的是第1、2點(招式中文名稱、sub-index觸發時機)，仍待下一輪對照其餘9個函式本體**
(本輪只完整反組譯了`action_id0`的資料讀取段落，其餘8個函式的stack-check前導碼與粗略frame
大小已確認同構——`0x6c/0x2c/0x74/0x54×2/0x6c/0x50/0x38/0x18`各不相同的stack frame暗示每個
action的細節不同，未逐一反組譯到底)。

**2026-09-06續，action_id2(`0x2bd6c`)逐指令反組譯,確認是完全不同性質的機制,不是movement**：
用同一個`[0x53a45]+idx*0x50+6`公式讀取單位record byte[6]是否為0(設一個local flag),再讀第5個
參數(byte)分流:值為0時清空**三個連續全域byte**`[0x53fb2]`/`[0x53fb3]`/`[0x53fb4]`並回傳
`EAX=0x1d`(29);值為3時把`[0x53fb2]`設成`0x10`並回傳`EAX=0xc`(12);其餘值走向未反組譯的
`0x2bdee`分支。函式epilogue單純`pop`+`ret`,回傳值`EAX`(12/29等)語意上很像「要播放的SFX
resource id」——**action_id2看起來是狀態異常(中毒/麻痺/詛咒類)套用/解除函式，寫入的是狀態
旗標而非移動座標**，與action_id0的「7-step X/Y攻擊撲擊動畫」是完全不同類型的機制。

**同輪追加,action_id1(`0x2bb33`)反組譯,確認是與action_id0同模板但不同形狀的movement動畫**：
結構逐指令與action_id0同構(同樣的unit byte[6]檢查、同樣的`REP MOVSD`資料複製慣用法)，差異
是這次複製**兩個8-dword(32-byte)陣列**(無7-byte flag陣列)，來源位址是`0x5252d`/`0x5254d`
(與action_id0的`0x524ee`一帶完全不同、各自獨立的資料區，不是共用表)。dump值：
X位移=`-59,-39,0,39,55,39,0,-39`(對稱式左右擺動,首尾接近0,不像action_id0的「單向撲擊」)、
Y位移=`-10,-24,-30,-24,-10,4,10,4`(下探到-30再回升到+10的弧線)。**兩個action的關鍵幀形狀
明顯不同**(action_id0淨位移偏向前方,action_id1對稱擺盪後回到原點)，支持「不同action_id對應
視覺上不同的攻擊動作(如刺擊vs揮砍)」這個招式名稱交叉對照的前提是成立的，不是套同一個模板
換皮膚。

**同輪追加,一次批次反組譯action_id3-8共6個(連同已知的action_id9)，10個action函式現已
100%完成結構分類**(byte級關鍵幀數值只逐一核對了action_id0/1/2，其餘用REP MOVSD的次數
`ECX`與是否有unit byte[6]檢查兩個結構特徵分類，未逐一手算每個關鍵幀數值，避免像本輪一次
位址算錯造成誤讀的風險)：

| action_id | FDTXT名稱(`command_labels.json`) | 位址 | 資料形狀 | 分類 |
|---|---|---|---|---|
| 0 | 火炎術 | `0x2b996` | 7-byte flag + 7-dword X + 7-dword Y (各自獨立表) | template-A(movement,雙軸) |
| 1 | 烈炎術 | `0x2bb33` | 8-dword X + 8-dword Y (各自獨立表) | template-A(movement,雙軸) |
| 2 | 炎龍術 | `0x2bd6c` | 無關鍵幀表,依第5參數分流寫`[0x53fb2..4]`狀態旗標 | template-B(狀態效果) |
| 3 | 天火術 | `0x2bfd9` | 12-dword + 3-dword + 3-dword(三段,比0/1更大) | template-A變體(movement,規模更大) |
| 4 | 電擊術 | `0x2c217` | 單一10-dword陣列(無獨立Y陣列) | template-A變體(movement,單軸) |
| 5 | 落雷術 | `0x2c441` | 與action_id4逐指令同構,10-dword陣列(不同位址) | template-A變體(movement,單軸,與4同型) |
| 6 | 轟雷術 | `0x2c67d` | 寫入一個literal常數`0x3c8efa2d`(若視為float≈0.0174,接近1度弧度制,疑似角度) + 5-dword + 5-byte | template-A變體(movement,含角度常數,疑似拋物線/投擲類) |
| 7 | 神雷術 | `0x2cafc` | 與action_id4/5逐指令同構,10-dword陣列(第三個同型) | template-A變體(movement,單軸,與4/5同型) |
| 8 | 聖光彈 | `0x2ccf4` | 只有4-dword(比其他都小) + 依`[ESP+0x34]`參數分流 | template-B候選(資料量小、有flag分流，形狀更接近action_id2/9而非0/1) |
| 9 | 咒殺術(邊界待查,見下) | `0x2ce1a` | 無關鍵幀表,依第1參數分流寫`[0x5412e]`/`[0x5412f]`狀態旗標,回傳0x14(20) | template-B(狀態效果,已於更早輪次讀出但未寫入本文件) |

**名稱來源**：`docs/data/command_labels.json`(FDTXT_000,既有資料,非本輪解碼)——本輪的貢獻是
**把這份已存在的command名稱表跟`DAT_000524c6`的結構分類接上**,不是重新解出名稱本身。0-8全部
是元素攻擊法術(火系×4/雷系×4/聖光×1)，不是doc36第10/11輪以來一直誤稱的「物理攻擊」，詳見
下方「仍缺的部分」第1點的訂正。9(咒殺術)卡在doc36引述的dispatch條件邊界外一格，關聯性未確認。

**2026-09-06 live獨立驗證**：用`tools/fd2_dosbox_live_helper.py`啟動一個全新instance(`d8probe`)，
LOAD既有真實存檔(figaniA留下的ch27進度)，進入軍營帳篷→跟NPC對話開啟索爾的法術清單畫面，
**實機截圖直接顯示**：聖光彈-MP24、行動術-MP24、暗邪鬼-MP36、裂地術-MP80、熾天使-MP76、
風妖精-MP52、傳送術-MP20、破龍擊-MP22、破壞神-MP28——**這9個名稱與`command_labels.json`
裡對應command_id(8/25/35/12/32/33/23/24/34)完全逐字吻合**，是本輪對「command_labels.json
名稱真的會顯示在玩家看得到的畫面上」這件事的第一次**直接視覺獨立驗證**(先前只確認FDTXT
字串解碼pipeline本身正確，沒有實機比對過畫面)。截圖存證：
[`sol-spell-list-command-labels-live-verify.png`](../figures/sol-spell-list-command-labels-live-verify.png)。
**副產品，誠實記錄**：本輪原目標是嘗試觸發worklist 791的「D8」battle-entry slide-in畫面
(`0x1f1cc`/`0x1f30a`)，但這份存檔LOAD後停在軍營帳篷hub(NPC對話"還有事嗎？")，不是進行中的
戰鬥——要從這裡走到真正的battle-entry轉場需要先離開帳篷、找到地圖上的戰鬥觸發點，屬於比
本輪預期更長的導航路徑，本輪未繼續往791推進，只留下這個獨立的、有價值的command_labels.json
live驗證副產品。

**誠實範圍**:這張表是**結構分類**,不是完整語意解讀——`template-A`的4/5/7「單軸10-dword」
是否代表「只有Y沒有X」或反過來、action_id6的角度常數具體怎麼用、action_id3為何比0/1多一組
3+3的額外資料，都還沒反編譯到底。但比起本輪開始時「完全不知道10個action函式在幹嘛」，現在
已經確定**至少2大類機制**(movement類佔0/1/3/4/5/6/7共7個、狀態效果類佔2/8/9共3個)，且
movement類內部至少再分3種子形狀(雙軸/單軸/含角度常數)——這個分類本身就足以支撐「不同
action_id是不同招式」的招式名稱交叉對照工作，下一輪可以針對子分類挑1-2個代表逐一決定
byte-exact的關鍵幀語意，不需要每個都做到底。`0x53fb2`
一帶三個連續byte全域**尚未在本專案任何既有doc命名**。`xref_to 0x53fb2`回傳0筆——這正是
本輪`.object1`盲區的延伸效應:Ghidra的`-noanalysis`分析連這個function本身都不認得,自然也
不會追蹤它內部的data reference,不是這個全域真的沒有其他讀寫者。下一輪若要追這三個byte的
語意,需要用`bytes`直接讀取live記憶體(而非靜態`xref_to`)或改用逐一手動反組譯掃過其餘9個
action函式本體去找有沒有其他函式也碰這三個位址(2026-09-06已把全部10個action函式做完
結構分類,見上方表格,但沒有專門為此再去核對每個是否寫`0x53fb2`)。

**同輪追加,交叉核對doc02武器分類數量與action_id的movement/狀態效果比例,得到一個有希望但
未證實的假說**——**本節稍後(同日續二)已撤回,見上方「仍缺的部分」第1點**：這個假說建立在
「`unit.byte[7]`是武器類別軸」這個前提上,而doc06已反組譯確認`unit[+7]`其實是角色身分selector
(FIGANI肖像index),跟武器類別無關,所以下面這段推論的前提本身不成立,保留原文只是誠實記錄
本輪走過這條死路，不要在下一輪重複同樣的假設。doc02 §5.1-5.8列出遊戲**恰好8種武器類別**
(刀劍/匕首/槍矛/斧鎚/弓/杖/拳爪/
機兵手臂)，doc36本節開頭已知item1的假說是「action_id可能與`unit.byte[7]`選的FIGANI武器類別
共用同一條軸」。本輪結構分類找到7個movement類action_id(0/1/3/4/5/6/7)——與8種武器類別
「接近但不完全對得上」，加上doc02同時列出至少2種**武器自帶機率型特殊效果**(黑暗劍/淬毒刀
10-30%中毒、斬鐵劍/忍者刀5-30%暴擊)，這可能解釋為什麼3個action_id(2/8/9)不是movement而是
狀態旗標寫入——**假說**：movement類7個對應7種「基礎揮擊/攻擊動畫」類別(可能弓/杖/機兵手臂
三者共用同一套或其中一種不需要獨立位移動畫)，狀態效果類3個(2/8/9)則是「中毒/暴擊/其他狀態
異常」這類**附加在普通攻擊之後的機率觸發特殊效果**,不是獨立的武器動畫。這個假說能解釋doc02
「黑暗劍10%中毒」這類機率文字敘述的機制層對應(武器擊中後額外roll一次觸發action_id2/8/9之一)，
但**7≠8的落差、哪個action_id對應哪個武器類別、`unit.byte[7]`的實際讀取位址**這三點都還沒有
反組譯或live驗證支持，**明確標記為假說,不是結論**——下一輪若要證實，需要找到`unit.byte[7]`
被讀取、送進`DAT_000524c6`索引運算的那個確切呼叫點(目前只知道doc36 item1原始猜測的存在，
未定位其位址)，或用DOSBox-X對照特定武器攻擊時實際命中的action_id。

**worklist L584/604/622 完成度**:三項合併視為「逐招對照」核心同一件事的完成度判斷 ──
- ✅ 修正了 round10/11 引用的錯誤函式位址(`0x027fc9` 其實是無關的選單迴圈;真正的攻擊總派送函式是
  `0x2ff01`,其上游 caller `0x1cff0`/`0x015311` 位址本身原本就是對的)。
- ✅ 完整解出「action_id 0-9 → `FDOTHER.DAT` #82-90」的資源層級對照,10/10(9 個獨立資源,id0/1共用)
  皆逐一解包驗證為合法 PCM SFX 池,且 sub0 共用機制與第10輪推論吻合,25 個 WAV 已匯出。
- ✅ **2026-08-24 續輪**:`0x20-0x23` 分支自己的 index 來源已追出並關閉(`DAT_00052668`→91-94,四個
  WAV 已驗證匯出),見上方引述段落與 doc27 §6.5。
- ✅ **2026-09-06**:`id 12-21/25-27 載入資源的型態`/`id 10/11/22/23 的表缺口`兩點**撤回**——
  `DAT_000524c6`反組譯確認只有10個有效函式指標(action_id 0-9)，表尾+0x28起是共用的7-step
  X/Y移動關鍵幀資料區,不是延伸的action_id表,原本的「gap」/「型態未鑑定」提法建立在誤判表格
  範圍的錯誤假設上,不是真的還有12-27這些action_id待查。
- ❌ 仍未解:id 0-9 對應的玩家可讀招式名稱;池內子樣本個別觸發時機(需要逐一反組譯9個剩餘
  action函式本體，本輪只完整解出action_id0的資料讀取段落)。
- **綜合判斷**:四個子缺口中兩個(型態/表缺口)已撤回定案，剩兩個(招式名稱、sub-index觸發時機)
  仍待下一輪逐一反組譯`0x2bb33`/`0x2bd6c`/`0x2bfd9`/`0x2c217`/`0x2c441`/`0x2c67d`/`0x2cafc`/
  `0x2ccf4`/`0x2ce1a`共9個action函式本體(方法沿用本輪的Ghidra headless disasm/decompile，
  這些函式全部落在`.object1`盲區、function_bounds回報「不在任何function內」，需從各自位址
  直接反組譯而非依賴decompile)，並對照`FDICON`/指令文字表或FIGANI byte[7]武器類別軸。**item
  1511/852的既有教訓在此適用**：這9個函式若也各自讀取相鄰的關鍵幀資料區(不同offset)，逐一
  反組譯前應先用`bytes`確認各自表尾後方的資料形狀，避免重蹈本次「先誤判表格範圍」的彎路。

> **2026-11-04(doc98 續一百九十一 (6))**:id 0..9 = 法術場景 `0x2ff01` 的 phase handler(表 `0x524c6`),名稱 = FDTXT_000 `0x1b9 + id`(2 = 炎龍術、8 = 聖光彈);法術池 = FDOTHER #82, 82, 83..90(表 `0x526d9`,`[0x54153]`),子樣本依事件碼與幀計數選,不分命中。物理攻擊(`0x2ebe1`):命中幀未命中放 sub 0、命中放幀標頭 `+5`;會心(結果[4] `0x2f9da`)只閃白,沒有專屬音效;攻擊池 FDOTHER #48..#53 的 sub 0 是同一段揮空音(上面 410..412 行「sub0 疑為通用揮擊/命中聲」更正為揮空音)。
> **2026-11-04 實機(doc98 續一百九十二 (2))**:物理攻擊 LOG CONFIRMED —— lc192a / lc192b 36 輪攻擊、187 次幀音效:一般幀放幀 +5、命中幀命中放 +5、命中幀未命中放 sub 0(揮空音);會心(結果 +4)只走 `0x2f179` 閃白,音效序列與非會心命中相同。會心門檻表 `0x524a8` 以「職業 − 1」索引。

## 導出 WAV:戰鬥音效候選池(第 10 輪)

> **記憶修正（2026-07-25）**：本節舊版「40-bit 已知招式遮罩／已學會招式清單」措辭已作廢。`0x1c269` 目前只證實為 5-byte bit-scan 與輸出 ABI；其欄位不命名為 spell、move 或 learned-list，且不得把 `unit+0x22..+0x24` raw transient/modifier bytes 當成法術 bitfield。

`tools/export_sfx.py --battle` 把上表 9 個候選資源解開巢狀容器,逐子樣本補 WAV 檔頭,輸出到
`remake/assets/sfx/battle_<資源號>_<子序>.wav`。2026-08-01 另加入固定資源 #95：
`0x32999` 的第1次呈現直接呼叫 `0x25A96(resource95,0,1)`；其容器有1個
10444-byte 有效 raw PCM 與1個空哨兵，因此目前 `--battle` 共匯出43個 WAV。
11025Hz 仍是工具鏈推定值，#95 的玩家可聽語意也仍未知；不能因 runtime 已接線
就提升成已證實的音效名稱。
(續一百六十一:11025 Hz 已由 `AIL_init_sample` 的預設值確認(`0x414e0`,FD2.EXE 反組譯),見本文件開頭;#95 的玩家可聽語意仍未知。)
`--res <idx>` 可導出任意單一 FDOTHER.DAT 資源號(供後續驗證其他候選用)。

## 2026-09-04:原版實機確認 `play_sfx_a`,並更正 worklist 沿用的舊位址

### worklist 一直在用第 8 輪的誤記位址

本文件第 9 輪(見上方勘誤節)已把 `play_sfx_a` 由 `0x026896` 更正為 **`0x25a96`**
(第 8 輪把 file offset 誤當 linear,固定偏差 `+0xE00`)。但
`91-worklist.md` 的 M5-F「UI 音效 index 2-0xb 語意畫面實測」那一列**沒有跟著改**,
仍寫「要在 `0x026896` 下斷點讀參數」。本輪已就地更正。

這個陳年錯誤特別值得記,因為它**會產生假結論而不是報錯**:用 `0x026896` 下斷點永遠不會
命中,而「斷點沒命中」在操作上看起來就等於「這個動作沒有音效」。

**本輪用 Ghidra 獨立佐證兩邊**:

| 位址 | function_bounds | xref_to |
|---|---|---|
| `0x26896`(第 8 輪誤記) | **不是函式入口**,落在 `FUN_0002670e`(`0x2670e..0x26995`)中間 | **0 個** |
| `0x25a96`(第 9 輪更正) | `FUN_00025a96`,`0x25a96..0x25b44`,175 bytes | **81 個** |
| `0x25b45`(`play_sfx_b`) | — | 5 個 |

### 原版實機命中,且與靜態呼叫端清單交叉吻合

DOSBox-X 實機(ch27 存檔,delta `0x19c000` 由 gate-check signature 實測校準),
`BP 0170:001C1A96`(= `0x25a96`):**按方向鍵當場命中**。讀呼叫現場堆疊得到

```
index = 0   priority = 1   table = 0x208018   返回位址 = ghidra 0x117a6
```

三次取樣(→ / ↑ / ←)完全一致。**交叉驗證**:靜態 `xref_to 0x25a96` 的 81 個呼叫端裡
就有 **`0x117a1`** —— 正是返回位址 `0x117a6` 前面那道 `call`。活體與靜態互相對上。

**已確定:戰場游標移動 = SFX index 0(呼叫端 `0x117a1`)。**

### 兩個工具面的坑(都會讓人誤判「這個動作沒有音效」)

1. **斷點命中後 CPU 可能已步過入口。** `0x25a96` 是 `push 0x1C`(5 bytes),下一道
   `0x25a9b` 是 `call`。EIP 停在 `0x1C1A9B` 時**仍然是命中**,只是 ESP 比進入時低 4,
   讀參數要位移 4。只認入口位址會把真命中記成「沒有音效」。
2. **`MEMDUMPBIN` 在斷點停住時會靜默失敗**(DOSBox-X upstream #3629,本專案 doc58
   續四十九/續五十已記載)。本輪它在 Alt+Pause 停住時可用、在斷點停住時反覆失敗。

### 尚未完成(不宣稱已解)

index → **畫面**的完整對照還沒做完。靜態路線是可行且比逐鍵活體取樣更完整的:
81 個呼叫端各自 push 的是常數 index,逐一反組譯即可得到完整 index→呼叫端對映;
剩下的是把呼叫端函式對應到玩家看得到的畫面。本輪只閉合了 index 0 這一筆。

### index → 呼叫端 → 函式:靜態全表(2026-09-04)

位址修正之後,這一項不必再逐鍵在活體上試。`play_sfx_a(table, index, priority)` 是
`__stdcall`,絕大多數呼叫點的 index 是**常數**,所以直接從 EXE 讀 `call` 前的
`push` 立即數就能一次拿到全表。

做法:`xref_to 0x25a96` 取 81 個呼叫端 → 用 `le_xref.parse_le` 把 linear 換成 file
offset → 由 `call` 往回貪婪解析 `6A imm8` / `68 imm32` / `FF 35 mem` / `50-57 push reg`。
**65/81 解出常數 index;其餘 16 個的 index 放在暫存器(動態),靜態解不出來,不猜。**

> 驗證映射用的是已知真值:`0x117a1` 的位元組必須是 `E8` 且相對位移指向 `0x25a96`。
> 實讀 `e8 f0 42 01 00` → 目標 `0x25a96`,吻合;其前是 `6a 01`(priority=1)、
> `6a 00`(index=0)、`ff 35 ...`(table),**與同一個呼叫點的活體讀值逐欄相同**。
> (第一版解析器只認 `6A`/`68`,碰到 `FF 35` 就中止,81 個全部解不出來——
> 不是映射錯,是解析器少一種 push 形式。)

| index | 呼叫端數 | 呼叫端所屬函式(專案既有識別) | 佐證等級 |
|---|---|---|---|
| **0** | 37 | `0x115b6` 移動確認 selector(`0x117a1`)等 | **原版實機已確認 = 戰場游標移動** |
| 1 | 4 | `0x1c2da`、`0x26152` | 靜態 |
| 2 | 1 | `0x164e8`(`0x16546`) | 靜態 |
| 3 | 1 | `0x1db65`(`0x1ddaa`)——`0x18d8c` 攻擊分支呼叫的同一支 | 靜態 |
| 4 | 3 | **`0x13fd4` 休息回復**(`0x1403d`)、`0x1a30b`、`0x1e98c` | 靜態 |
| 5 | 4 | **`0x17aed` 狀態/裝備卡演出**(`0x17c56`)、`0x17e0b` present compositor、`0x29bcb`、`0x2af28` | 靜態 |
| 6 | 3 | **`0x17aed`**(`0x17b2e`/`0x17d26`)、`0x2af28` | 靜態 |
| 7 | 3 | **`0x117e7` 頂層戰場游標鍵盤 handler**(`0x1193a`)、`0x29bcb` ×2 | 靜態 |
| 8 | 2 | `0x1741c`、`0x176b4`(`0x18d8c` 按鍵迴圈後緊接呼叫的那支) | 靜態 |
| 11 | 1 | `0x32230`(`0x32307`) | 靜態 |
| 255 | 6 | `0x1d50a`、`0x2e284`、`0x2e918`、`0x30d1b`、`0x2d770`、`0x2dd9e` | 靜態;`0xFF` 疑為「停止/無音」哨兵,未證實 |

完整資料:[`docs/data/sfx_index_callers.json`](../data/sfx_index_callers.json)。

**誠實的界線**:上表的「index → 呼叫端 → 函式」是靜態確定的;但
**「index → 玩家看到的畫面」目前只有 index 0 有原版實機證據**。其餘各列的畫面語意是
「該函式在本專案既有文件中的身分」推得的**強推論**,不是實機驗證。要收口需要對每個
index 的呼叫點各下一次斷點並辨識當下畫面——方法已通(用**呼叫點**下斷點即可,
不必讀堆疊,因為呼叫點本身就決定 index;這一點很重要,因為 `MEMDUMPBIN` 在斷點停住時
會靜默失敗)。本輪未逐項完成,不宣稱已解。

### 2026-09-04 續:index→畫面的實測方法(**兩個對照缺一不可**),以及對前一段的限縮

嘗試用「在呼叫點下斷點 → 按鍵 → 看命中哪個」把 index 對應到畫面。
`tools/fd2_sfx_screen_map.py` 是這個流程的工具化。**第一版的做法是錯的**,
兩個必要的對照都缺,而缺任一個都會產生看起來很乾淨的假結論。

#### 對照一:零輸入基準(有些呼叫點會自己命中)

第一次量測得到「confirm → index 2(`0x16546`)」,連續五個不同按鍵**全部**回報同一個
呼叫點。控制實驗:**完全不按鍵**,連續觀察——`0x16546` 仍然 4/4 命中。
它在每幀/待機路徑上,與按了什麼無關,前面五筆因此全部作廢。

**已確認會自走的呼叫點(零輸入即命中)**:

| 呼叫點 | index | 意義 |
|---|---|---|
| `0x16546` | 2 | 不繫於任何離散 UI 動作 |
| `0x32307` | 11 | 同上 |

而且**基準必須迭代**:兩者都武裝時,先命中的會把另一個遮住,要排除一個再測一次才會露出下一個。

#### 對照二:必須確認 debugger 真的停住

register view 在**執行中也會更新**,所以 EIP 落在某個位址完全可能只是 CPU 正好經過。
漏掉這一步時,連續四筆 probe 讀到同一個 EIP 而被判成「每次都命中」。
工具現在先檢查 pane 是否為 `(Running)`,不是停住就不採信 EIP。

#### ⚠ 限縮上一段的「戰場游標移動 = index 0」

那筆是在 **ch27** 量到的(呼叫點 `0x117a1`,靜態 xref 也對得上)。本輪在 **ch01** 的
瀏覽游標層(已用「方向鍵確實移動 `[0x53ab1]/[0x53ab5]`」確認層級)重測:

- 武裝 `play_sfx_a` 本體 → 按方向鍵**命中**,所以確實有播音效;
- 但同時武裝 `0x117a1`、`0x1193a`、`0x11a33/54/75/96` 六個候選呼叫點 → **一個都沒命中**。

**所以「游標移動 = index 0」只在 ch27 的量測狀態成立,不可外推。** ch01 同一個動作
走的是候選集合以外的呼叫點,index 未知。原文的措辭已因此限縮。

#### 目前結論

- index → 呼叫點 → 函式:**靜態確定**(65/81),見上一段的表。
- index → 畫面:**尚未建立**。唯一的兩筆實機事實是「index 2 與 index 11 的唯一呼叫點都是
  自走的」,以及「ch27 的游標移動走 `0x117a1`」。
- 方法本身現在是可信的(兩個對照都內建於工具),剩下的是逐狀態逐動作跑,
  而**每換一個章節/UI 層級都要重新做零輸入基準**。

### 2026-09-04 續二:差異原因已確認 —— `0x16546` 每幀執行,而它會偽裝成「按鍵觸發的音效」

前一段留下的問題是:同樣是「移動游標」,ch27 量到 `0x117a1`(index 0),ch01 卻六個候選
呼叫點全不命中。追下去的結果如下。

#### 事實 1:ch01 的 `play_sfx_a` 呼叫來自 `0x16546`,參數 index=2

武裝函式本體 `0x25a96`,按方向鍵命中後讀呼叫現場堆疊:

```
[ESP+0] 返回位址 0x1b254b → ghidra 0x1654b  ⇒ call 在 0x16546
[ESP+4] table = 0x208018   [ESP+8] index = 2   [ESP+C] priority = 1
```

#### 事實 2:`0x16546` **零輸入也每幀執行**(有對照)

| 武裝的斷點 | 零輸入觀察 | 結果 |
|---|---|---|
| `0x16546` | resume 後立即 + 6/12/18/24 秒 | **每次都停住**(5/5) |
| `0x1193a`(對照) | 5/10/15 秒 | **持續執行**,一次都沒停 |

對照組證明 `resume` 有效、斷點只在真被打到時才停,所以 `0x16546` 是真的每幀在跑。
(合理的機制:`play_sfx_a` 開頭就有 `cmp byte [0x1EFEF1],0` 之類的閘,重複呼叫同一個
index 應該會被擋掉而不重播——**未證實,不宣稱**。)

#### 因此:兩個結論的正確處置

- **「ch01 游標移動 = index 2」不成立。** 那次堆疊讀值是在按鍵之後抓到的,但該呼叫點
  本來就每幀在跑,**按不按鍵都會讀到同一組參數**。是我先前把「按鍵後讀到」誤當成
  「按鍵造成」。
- **先前的零輸入基準是對的**,反而是後來這次堆疊讀值把我帶偏。基準判定 `0x16546` 自走,
  而它確實自走。
- **「ch27 游標移動 = index 0」仍然只是狀態相依的一筆**:那次用函式斷點抓到的是按鍵後
  第一個呼叫,但我從未確認在 ch27 的那個狀態下有沒有別的呼叫點同時在跑。
  它的**排他性未經驗證**。

#### 方法上的結論(對後續所有 index→畫面 量測都適用)

**只要存在自走呼叫點,「按鍵後抓下一個 `play_sfx_a` 呼叫」這個做法就是不可靠的**——
它會穩定地抓到那個自走的呼叫,看起來像是按鍵造成的,而且每次都一致(所以「重複量測
得到相同結果」在這裡**不構成佐證**)。

正確順序:
1. 在**該狀態**下先做零輸入基準,找出所有自走呼叫點(需**迭代**,先命中的會遮住後面的);
2. 只武裝安靜的呼叫點;
3. 用「函式本體會命中、但安靜呼叫點都不命中」來判定「這個動作的音效來自自走呼叫點以外
   的地方,且不在已武裝集合內」。

**每換一個章節或 UI 層級都要重做步驟 1**——自走與否是狀態相依的(同一個 `0x16546`
在 ch27 的量測狀態下顯然沒有搶先命中)。

### 2026-09-04 續三:差異原因**完全釐清**,並取得第一批可信的 index→畫面對應

前兩段留下兩個未確認項:ch01 的游標移動實際播什麼、以及 ch27 那筆 index 0 是否也是汙染。
把 UI 層級固定住之後兩個都解掉了。

#### 關鍵前提:先證明層級,再量測

用 `fd2_battle_autoplay.py --ensure-browse`(以 `0x18890` 斷點自證在瀏覽游標層)固定層級,
再做零輸入基準——**這次全部呼叫點都武裝、5 次零輸入,零自走命中**。

**這修正了前一段的說法**:`0x16546` 的自走**不是全域性質,是「指令環層」的性質**。
先前觀察到它 5/5 自走時,UI 其實在環裡(事後截圖證實)。在確認過的瀏覽層它不會自己命中。

#### 結果(基準乾淨 + 層級已證 + 同組態內含陽性對照)

| 操作(瀏覽游標層) | 呼叫點 | index |
|---|---|---|
| **→** | `0x11a96` | **0** |
| **↑** | `0x11a33` | **0** |
| **←** | `0x11a75` | **0** |
| **↓** | `0x11a54` | **0** |
| **Enter(選取單位)** | `0x1193a` | **7** |
| **Escape** | —— | **不播音效** |

**四個方向鍵各自命中不同的呼叫點、卻同為 index 0** —— 這正是 `0x117e7` 每個方向有獨立
分支、共用同一個游標音效的樣子。而且這種結果**汙染產生不出來**:壞掉的第一版是四個鍵
全報同一個呼叫點。四對四的方向專屬對應本身就是方法有效的簽章。

`Escape` 的「無音效」是在方向鍵於**同一組態**下會命中的前提下取得的,所以是有意義的負結果,
不是「沒量到」。

#### 原本那個差異,完整成因

ch27 量到 `0x117a1`(index 0)、ch01 六個候選全不命中,原因是三層疊加:

1. **UI 層級不同**:`0x117a1` 在 `0x115b6`(移動選格游標),`0x11a33/54/75/96` 在
   `0x117e7`(瀏覽游標)。**兩層都用 index 0 當游標移動音**,所以 index 一致、呼叫點不同。
2. **ch01 那次量測時 UI 在環裡**,不在瀏覽層,所以那六個候選本來就不會被走到。
3. **環層有自走呼叫點 `0x16546`**,把函式斷點先搶走,於是堆疊讀到的是它的 index 2。

**因此 ch27 的 index 0 不再可疑**:index 0 = 游標移動已由 ch01 的四個方向獨立確認,
ch27 那筆與之一致,只是走另一層的呼叫點。

#### 目前 index→畫面 的確立程度

| index | 對應 | 等級 |
|---|---|---|
| 0 | 戰場游標移動(瀏覽層四方向 + 移動選格層) | **原版實機**,ch01 四方向 + ch27 一筆 |
| 7 | 瀏覽層按確認鍵選取單位 | **原版實機** |
| 2 | 出現在環層的自走呼叫點 `0x16546`;語意未定 | 觀察到,語意未確認 |
| 11 | 自走呼叫點 `0x32307`;語意未定 | 同上 |
| 1,3,4,5,6,8 | 呼叫端已知,畫面未量 | 靜態 |

### 2026-09-04 續四:環層與資訊卡的 index,以及一次三重確認的截圖

沿用續三的流程(`ensure_browse` 證層級 → **該層**零輸入基準 → 只在基準乾淨時 probe),
把量測推進到指令環層與資訊卡。**每換一層都重做基準**——環層與瀏覽層的自走情況不同。

| 操作 | 呼叫點 | 所屬函式 | index |
|---|---|---|---|
| 瀏覽層 → / ↑ / ← / ↓ | `0x11a96`/`0x11a33`/`0x11a75`/`0x11a54` | `0x117e7` | **0** |
| 瀏覽層 Enter(選取單位) | `0x1193a` | `0x117e7` | **7** |
| **環內確認選擇** | `0x176d3` | `0x176b4` | **8** |
| **環內「休息回復」執行** | `0x1403d` | `0x13fd4` | **4** |
| **對已行動單位按 Enter(資訊卡演出)** | `0x17ede` | `0x17e0b` present compositor | **5** |
| 瀏覽層 Escape | —— | —— | **不播音效** |
| **環內方向鍵** | —— | —— | **不播音效** |

兩個「不播音效」都是在**同一組態下 confirm 會命中**的前提取得的,所以是有意義的負結果。

#### index 4 的量測順帶做了一次判別性再驗

`0x13fd4` 只在「現值 ≠ 最大值」時才回復,所以先把 `+0x40` 寫成 20(`+0x42` 維持 42),
再走環內 ↓ + 確認。結果:index 4 命中,且**回復後讀到 HP 28/42**。

`floor(42/5) = 8`,`20 + 8 = 28` —— 只有在「最大值 = 42 位於 `+0x42`」時成立;
若偏移相反(max=20)應得 24。**這是用遊戲自己的算術做的判別,與續三那次靠顯示順序的
讀法完全獨立**,HPcur/HPmax 的指派因此有兩個互不相關的佐證。

#### 一張截圖同時確認三件事

`card_acted` 那張(對已行動的索爾按 Enter 後):

- **`MV·20`** —— 稍早寫進 `+0x3b` 的值真的顯示出來了,補上 MV 偏移先前缺的畫面佐證;
- **`HP 028/042`** 與記憶體逐欄相符,而且血條是**部分填滿**——終於是個**非退化樣本**;
- 這張卡本身就是 index 5 的演出。

#### 目前 index→畫面 覆蓋率

已量到畫面:**0、4、5、7、8**(5 個)。
仍未量:**1、3、6**(呼叫端已知,尚未找到觸發它們的操作);
**2、11** 只觀察到「在某些層會自走」,語意未定。

### 2026-09-04 續五:index 6 未觸發,以及它對字模截圖那一項的意涵

`0x17aed` 依 doc13 §2 是「(**有已知法術才加演**)法術列表卡 → (一定會播)裝備/道具卡」。
index 5 的呼叫點 `0x17ede` 在 present compositor `0x17e0b`,index 6 的兩個呼叫點
`0x17b2e`/`0x17d26` **都在 `0x17aed` 內**,合理推測落在法術卡那一段。

實測(ch01,悠妮已行動、MP 8/8、`+0x1a..+0x1e` mask = `0100000000`):

- 按 Enter → **index 5 命中**(`0x17ede`);
- 續跑讓演出播完 → **沒有任何 index 6 呼叫點命中**;
- 逐幀截圖(t=0.25/0.45/0.7/1.0s)→ **全部是裝備卡,法術列表從未出現**。

所以 `FUN_0001c269(unit,0)` 對這個狀態的悠妮回傳 0 —— 她那一個 mask bit 不足以讓
法術卡那一段播出。**index 6 因此未能量到,原因是條件未達成,不是量測失敗。**

#### 對 `glyph 423`(麻痺術)原版截圖的意涵

那一項需要在原版畫面上看到「麻痺術」這三個字模。目前唯一已知會列出法術**名稱**的畫面
就是 `0x17aed` 的法術列表卡,而本輪確認:

1. 路徑本身可達(對已行動單位按 Enter 必進 `0x17aed`,index 5 命中可證);
2. 但**要有足夠的已知法術**才會演出法術卡,ch01 的 LV1 悠妮不夠;
3. 麻痺術是 command 27,依 `+0x1a..+0x1e` 的 mask 解讀,**ch27 存檔那批單位的 mask
   (`001180020f` 等)第 27 位也是 0** —— 即手上兩份可用存檔的角色**都不會這個法術**。

**因此這一項的瓶頸不是方法,是資料可得性**:需要一個真的學會 command 27 的角色
(更後期的存檔,或用記憶體寫入補上該 mask 位元再觸發演出)。後者是可行的下一步,
但那會是「人為造出的畫面」,取證時必須註明。
(mask 的位元對映本身也尚未獨立驗證,上面第 3 點應視為強推論而非已證。)

### 2026-09-04 續六:index 6 已量到;真實攻擊**不**走 index 1/3/6

#### index 6 = 資訊卡演出的較後段

續五記錄「index 6 未命中」,那是取樣時機的問題,不是條件未達成。改用「武裝
`play_sfx_a` 本體、逐鍵讀呼叫現場堆疊」重測,序列清楚:

| 按鍵 | 呼叫點 | index |
|---|---|---|
| Enter | `0x17ede`(`0x17e0b` present compositor) | 5 |
| Enter | `0x17ede` | 5 |
| ↑ | **`0x17d26`(`0x17aed` 內)** | **6** |
| Enter | `0x17d26` | 6 |

所以 **index 5 是資訊卡演出的開頭、index 6 是較後段**,兩者同屬對已行動單位按 Enter
那條路徑。續五「演出播完沒有 index 6」的觀察,是因為當時的續跑取樣落在它之前就判定結束。

#### 真實攻擊的音效不在已解出的常數 index 裡

用 MV 覆寫(`+0x3b`=30)把 idx2 移到敵 idx8 相鄰格,實際執行一次攻擊:
**敵方 HP 由 28/28 降到 7/28(21 點傷害),攻擊確實執行**。
但全程武裝 index 1/3/6 的 8 個呼叫點,**一個都沒命中**。

`0x18d8c` 的攻擊分支(case 0)會呼叫 `FUN_0001db65`,而 index 3 的唯一呼叫點 `0x1ddaa`
正在那支函式裡——它沒響,表示那條路徑這次沒走到那一行,或攻擊音效根本來自別的呼叫點。

**最可能的解釋**:攻擊音效來自那 **16 個 index 放在暫存器的動態呼叫點**之一
(見本文件靜態全表那一段:65/81 解出常數 index,其餘 16 個是動態)。
若是如此,**靜態表在原理上就涵蓋不到攻擊音效**,只能靠活體讀呼叫現場堆疊。
這一點尚未證實,不宣稱。

#### 覆蓋率更新

已量到畫面:**0、4、5、6、7、8**(6 個)。
仍未量:**1、3**;**2、11** 只觀察到在某些層自走,語意未定。
攻擊音效:**已知不在 1/3/6**,實際 index 未定。

### 2026-09-04 續七:`0x117a1` 直接印證;`0x32307` 的靜態/活體讀值**互相衝突**(未解)

一次完整的「選取 → 移動 → 落點 → 環選攻擊 → 執行 → 確認目標」全程武裝 `play_sfx_a`
本體並逐鍵讀呼叫現場:

| 步驟 | 呼叫點 | 活體 index |
|---|---|---|
| 選取單位 | `0x1193a` | 7 |
| **移動選格內移動游標 ×8** | **`0x117a1`** | **0** |
| 確認落點 / 環選攻擊 / 執行攻擊 / 確認目標 | `0x32307` | **9** |

#### 好消息:`0x117a1` = 移動選格層的游標移動,ch27 那筆直接印證

ch27 當初量到 `0x117a1`(index 0),ch01 瀏覽層量到的卻是 `0x11a33/54/75/96`。
本輪在**同一個實例**裡同時看到兩者:瀏覽層走 `0x11a33/…`,**移動選格層走 `0x117a1`**,
兩層都是 index 0。續三對這個差異的解釋(層級不同、index 相同)因此不再只是推論。

#### ⚠ 未解衝突:`0x32307` 靜態說 11、活體說 9

直接讀 EXE 位元組(`0x32307` 前 24 bytes):

```
6a 01        push 1      (priority)
6a 0b        push 0x0b   (index = 11)
ff 35 ...    push [mem]  (table)
e8 8a37ffff  call        → rel32 驗算目標正是 0x25a96
```

但活體在該呼叫點讀到的 `[ESP+8]` 是 **9**,連續四次都是 9。

**不是讀取版面的問題**:同一次量測裡 `0x117a1` 的靜態位元組是 `6a 00`,活體讀到 index=0,
**完全吻合**——同一段程式碼、同一個版面,對一個位址對、對另一個不對。

目前無法判定哪一邊錯,**兩個值都不採信**。可能方向(皆未驗證):
活體命中時 `play_sfx_a` 已在執行中被再次進入,ESP 指向的不是該次呼叫的框;
或 `0x32307` 之外還有另一個呼叫點的返回位址恰好落在同一計算結果上。

**因此靜態全表(65/81)至少有一筆與活體不符,不應被當成已驗證資料整批引用。**
需要的下一步是對同一呼叫點同時記錄 EIP、ESP 與返回位址三者做交叉核對。

### 2026-09-04 續八:`0x32307` 的 11 vs 9 —— 已排除四種解釋,仍未解

續七記錄靜態 11、活體 9。本輪把能排除的都排除了,**結論是它仍未解**,但範圍縮得很小。

#### 已排除

| 候選解釋 | 排除方式 |
|---|---|
| 跑的不是同一份 EXE | 兩邊 md5 皆 `33464c81…`,與 pristine 相符 |
| `MEMDUMPBIN` 讀到舊檔 | 改成每次寫不同檔名,三次 md5 各不相同 |
| 堆疊版面解錯 | **同一批量測**中 `0x17495`、`0x176d3` 兩個呼叫點靜態皆 index 8,活體也讀到 8 |
| 位址映射錯 | 活體讀 `0x1CE307` 的位元組與檔案一致;唯一差異是 `ff 35 ec3e0000`→`ff 35 ecfe1e00`,即 `0x3eec + 0x19c000`,正是 LE fixup |

#### 現場的實際位元組(活體)

```
85 d2              test edx,edx
75 12              jnz  +0x12        ← 跳過整個 call 區塊
6a 01              push 1            (priority)
6a 0b              push 0x0b         ← index 應為 11
ff 35 ec fe 1e 00  push [0x1EFEEC]   (table,fixup 後)
e8 8a 37 ff ff     call 0x25a96
```

`jnz` 的落點在 call 之後,所以**走到這個 call 就必然經過 `push 0x0b`**。
而活體堆疊在 `EIP=0x1C1A96`(函式入口,`push 0x1C` 尚未執行)讀到
`[ret=0x1ce30c][table=0x208018][9][1]`——`ret` 與 `table` 都正確,只有 index 位置是 9。

#### 處置

**兩個值都不採信,此列標為未解。** 這也是為什麼靜態全表(65/81)不應被整批當成已驗證:
至少一列與活體不符,而且不符的原因目前無法歸因。

要收口的下一步(本輪未做):在該 call **本身**下斷點(`BP 0170:001CE307`),
命中時 EIP 就在 call 上、參數已全部 push 完,直接讀 `[ESP]/[ESP+4]/[ESP+8]`,
不經過 `play_sfx_a` 入口這一層——若那時讀到 11,問題出在入口那一刻的堆疊判讀;
若仍是 9,問題出在更前面。

### 2026-09-04 續九:**已解** —— `call` 被「跳進」時,靜態的「取前面的 push」會歸屬錯誤

續八列的下一步(在 call 本身下斷點)做完了,而且它**沒有**支持任何一邊,反而把成因逼出來。

#### 決定性的一次量測(同一個 halt,同時 dump 程式碼與堆疊)

在 `BP 0170:001CE307`(call 本身)命中時:

```
程式碼 @0x1CE2FD:  6a 01  6a 0b  ff 35 ec fe 1e 00  e8 …
                   push 1 push 11  push [table]      call
堆疊   @ESP:       table=0x208018   index=9   priority=1
```

- **程式碼沒有被改寫**(命中當下讀到的仍是 `6a 0b`);
- **堆疊上的 index 是 9,不是 11**;
- 對照:同一批量測裡在 `play_sfx_a` 入口讀到的是 `[ret=0x1ce30c][table][9][1]`,
  兩處一致,所以不是版面或讀取問題。

#### 結論

程式碼未被改寫、而參數又不等於緊鄰其上的 push,只剩一個自洽解釋:
**執行流是從別處跳進 `0x32307` 這個 `call`,沒有經過它上面那兩個 `push`。**
(現場的 `jnz +0x12` 落點在 call 之後,所以 fall-through 才是 push-11 那條;
實際走到的是另一條。跳入來源未追,不宣稱。)

#### 這對靜態全表的意義(重要)

`docs/data/sfx_index_callers.json` 的產生方式是「從 `call` 往回貪婪解析 `push`」。
**這個方法預設每個 call 都是從它上面 fall-through 進來的**——一旦某個 call 會被跳進,
歸屬就會錯,而且**錯得毫無徵兆**:解析成功、格式正確、數字看起來合理。

因此:

- **`0x32307` 的 index 應為 9,不是表上的 11**(活體雙重量測);
- 表上其餘 64 筆**未受檢驗**——同一個盲點可能還影響其他被跳進的 call;
- 已用活體確認過的六筆(`0x117a1`→0、`0x1193a`→7、`0x17495`/`0x176d3`→8、
  `0x1403d`→4、`0x17ede`→5、`0x17d26`→6)靜態與活體**皆吻合**,那六筆維持成立。

**修正後的立場:靜態表是候選清單,不是已驗證資料。** 每一列都要有活體命中才算數。

## `[esp+0xd0+counter]`(`local_20`)填值來源追蹤(2026-09-06,回應 worklist L604/L622,部分收斂)

延續本文件第 11 輪留下的缺口(`[esp+0xd0+counter]` 陣列填值來源未追出),用
`ghidra_batch_probe.py`對`FUN_0001cff0`(`0x1cff0`,即doc27§6.4已經定位的法術/道具
選單主函式)做完整decompile+逐段disasm複核。

**確認的事實**:
1. `local_20`在Ghidra decompile裡宣告成`byte local_20[12]`(12 bytes,對照
   `+0xd0..+0xdc`)。**整個`FUN_0001cff0`函式體內,沒有任何一行直接寫入`local_20`**
   ——它只在`if/else`分支條件裡被讀(`local_20[DAT_00053c57]`,用來判斷commandId是
   9-23/25-27走跳表、還是0-8/24/28-31走`FUN_0002ff01`大dispatcher、還是`==0x1e`
   (30)特殊處理),證實doc27§6.4「`local_20[選定索引]=commandId`」的語意判讀是對的,
   但**填值來源不在這個函式本體內部**。
2. **排除了一個候選**:函式一開始有個`for(iVar3=0xb; -1<iVar3; iVar3=iVar3-1)
   FUN_00018409(iVar3, [0x53c5b], [0x53c5f], [0x53c63])`迴圈(剛好12次,跟
   `local_20`的12 bytes數目吻合,一度懷疑是填值迴圈)——decompile確認`FUN_00018409`
   本體只是依`param_1`範圍分派到`FUN_00018312`/`FUN_0001839b`兩個繪圖類函式,不寫
   任何記憶體回傳,是**純UI繪製**(畫12個選單格icon),不是填值迴圈。
3. **真正的填值機制,找到了**:`FUN_0001cff0`的`DAT_00053c57=0; do{FUN_0001d51d()}
   while(...)`導覽迴圈,每次呼叫`FUN_0001d51d`處理一次按鍵。逐指令反組譯
   `FUN_0001d51d`按到確認鍵(`0x1c`/`0x39`)的分支,找到關鍵序列(`0x1d67b..0x1d698`):
   ```
   0001d67b  MOV EAX,ESP                    ; EAX = 目前(FUN_0001d51d自己的)ESP
   0001d67d  PUSH EAX                       ; -> 緩衝區指標參數
   0001d67e  PUSH dword ptr [ESP+0x20]      ; -> 單位index參數(來自FUN_0001d51d自己的傳入參數)
   0001d682  CALL 0x0001c269                ; FUN_0001c269(unitIdx, bufPtr=目前ESP) 把該單位已知
                                             ; 法術/道具的id清單寫進bufPtr指向的記憶體
   0001d687  ADD ESP,0x8                    ; 兩個參數彈出,ESP回到呼叫前的值(=bufPtr本身)
   0001d68a  MOVZX ESI,word ptr [ESI+0x44]  ; ESI = 目前MP
   0001d68e  MOV EAX,[0x00053c57]           ; EAX = 目前選到第幾個
   0001d693  MOVZX EAX,byte ptr [ESP+EAX*0x1] ; **緊接著讀剛剛`0x1c269`填好的同一塊記憶體**,
                                             ; 取出commandId
   0001d697  PUSH EAX
   0001d698  CALL 0x0004e866                ; 用這個commandId查法術/道具record
   ```
   **`FUN_0001c269(unitIdx, bufPtr)`把`bufPtr`(呼叫當下的ESP,不是傳統意義上「命名過的陣列」,
   是`FUN_0001d51d`自己stack frame最上緣那塊臨時空間)當輸出緩衝區,寫進這個單位目前所有
   已知法術/道具的commandId清單,寫完立刻在下一行用相同的`[ESP+DAT_00053c57]`定址讀出
   「目前選到那一格」的id**——這正是本文件第11輪已經證實過的「`0x1c269`是通用bitfield掃描
   →輸出index清單」語意在這裡的第二個實例(第一個實例是`+0xc8`那個,填的是完全不同的unit
   command bitset)。`FUN_0001cff0`自己的`local_20`之所以在decompile裡被Ghidra畫成一個
   獨立的12-byte區域變數,是因為`FUN_0001d51d`寫入的這塊「目前呼叫深度下的ESP臨時空間」,
   跟`FUN_0001cff0`prologue(`SUB ESP,0xd8`)保留的部分區域,在正常呼叫深度/堆疊佈局下
   剛好是同一塊實體記憶體(byte offset +0xd0 一帶)——**這是C編譯器常見的「callee直接借用
   caller已保留、當下未被佔用的那段stack當scratch buffer」模式,不是傳統的具名全域陣列**。
   本輪沒有逐byte核對兩邊stack offset算術完全吻合(需要精算`FUN_0001cff0`從
   `SUB ESP,0xd8`到呼叫`FUN_0001d51d`當下之間所有push/pop淨變化,再加上`FUN_0001d51d`
   自己到`0x1d67b`為止的push/pop淨變化,才能byte-exact證明兩邊真的是同一位址而非巧合),
   但語意鏈路(填值→立刻同位址讀值→取commandId→查record→比對MP)完全自洽,可信度高。

**現況**:`local_20`/`[esp+0xd0+counter]`的填值機制**在語意層級已經找到並可信**——是
`FUN_0001d51d`確認鍵分支透過`FUN_0001c269(unitIdx, bufPtr=目前ESP)`即時填的,不是某個
獨立的、需要另外初始化的全域表。worklist L604/L622原本問的「填值上游」問題到此已有具體、
自洽的答案,可以視為靜態RE層級收斂;唯一保留的誠實邊界是「兩邊stack offset的byte-exact
算術吻合」這一步沒有逐一算完,不宣稱到那個精確度。

## 2026-09-06:新發現的第三個SFX池——FDOTHER.DAT資源#80，item effect專用，live記憶體直接
驗證，解開worklist item 1117多輪追不出來的「index→PCM樣本」矛盾

**背景**:item 1117多輪靜態反組譯已byte-exact確認`0x25a96`(play_sfx_a)的index查表算式
跟`tools/unpack_dat.py`的LLLLLL容器目錄格式逐byte吻合，但拿算出來的index(12/6/7/8/14/5等)
直接去查FDOTHER.DAT**頂層**目錄，發現對應的resource是LMI1圖片/LLLLLL巢狀容器，不是音效——
連續兩輪(續十二/十三)否證了兩個假說(writer可能不固定寫FDOTHER.DAT、extracted/可能是舊版)，
矛盾仍未解開。本輪用已修正的WSL distro名稱(`Ubuntu`，不是先前誤用的`kali`，見persistent
memory訂正)重新取得live DOSBox-X存取，直接對`[0x53b13]`(=table_ptr)下記憶體讀取。

**決定性的live證據**：載入`FD2_ch27_test.SAV`存檔進入真實戰鬥後(先前在城鎮選單畫面
`[0x53b13]`恆為0，證實FUN_0001d4cb在那些畫面沒被呼叫)，`mem dump`直接讀`[0x53b13]`的值
是`0x00398018`——**這是一個真正的live記憶體位址值，不需要再套用ghidra↔live的靜態delta**
(FUN_000111ba的回傳值是runtime配置的真實指標，不是靜態image offset)。直接對這個位址dump
64 bytes，開頭正是`4c 4c 4c 4c 4c 4c`("LLLLLL"容器magic)，後面接著`4a 00 00 00`(=74)、
`eb 19 00 00`(=6635)……一組合法的17-entry offset table。

**關鍵一步——這組直接搜尋活體FDOTHER.DAT檔案找出真正位置**：把這組live bytes當
byte-signature去搜真正的`FDOTHER.DAT`檔案，在檔案offset **2,863,791**處逐byte命中——用
`unpack_dat.py`重新解FDOTHER.DAT頂層目錄後確認，這個offset剛好是**resource #80的起點**
(第80筆，長度116165 bytes)。**真相大白**：`table_ptr`從來不是指向FDOTHER.DAT頂層目錄
本身，而是指向FDOTHER.DAT**頂層resource #80**——這個resource自己又是一個獨立的、17個
子項的LLLLLL巢狀容器，之前多輪查的都是頂層目錄(裝著圖片/巢狀容器完全正確)，但沒人想到
`table_ptr`實際上是某個**子容器**的位址，不是頂層容器本身的位址。

**resource #80子項統計特徵逐一確認是8-bit unsigned PCM**(用`tools/export_sfx.py --res 80`
重新導出成標準WAV，取代手動bytes dump)：

| sub-index | bytes | mean | stdev | min | max |
|---|---|---|---|---|---|
| 1 | 4452 | 127.4 | 8.7 | 88 | 168 |
| 5 | 7138 | 127.6 | 14.0 | 80 | 173 |
| 6 | 5530 | 127.3 | 22.2 | 48 | 208 |
| 7 | 3438 | 127.2 | 12.8 | 68 | 181 |
| 8 | 1812 | 127.3 | 15.7 | 89 | 169 |
| 12 | 4550 | 127.7 | 13.5 | 84 | 168 |
| 14 | 10099 | 125.0 | 7.3 | 93 | 162 |

全部17個子項mean都落在127-128(unsigned 8-bit PCM的靜音中心值)、範圍對稱分布、無截波
(clip)——教科書等級的PCM audio特徵，不是巧合。

**item 1117 SFX子項最終解答**：`item.json`裡`itemRow+0xd`(effect type)透過
`FUN_0001c4cc`本體的`local_60[param_2]`查表，得到的index是**FDOTHER.DAT resource #80這個
巢狀容器自己的sub-index**，不是FDOTHER.DAT頂層resource編號。已知的type→sub-index對照
(`param_2`→`local_60[param_2]`，見worklist item 1117續十一)：type5/13(HP恢復)/type11
(MP恢復)=sub#12、type16(魔刃)=sub#6、type15(魔鎧)=sub#7、type12(風行)=sub#8；另有
`FUN_0001c2da`("雙胞胎"函式，每個`FUN_0001c4cc`caller後面都會接著呼叫)固定用sub#1(不
經過任何table查詢，疑似「使用道具」通用音效)。**這是本專案第一個byte-exact+live記憶體
雙重驗證、含實際可播放WAV檔的item-effect SFX池**，輸出於`extracted/sfx/battle_80_NN.wav`
(沿用`export_sfx.py`既有`--res`模式的檔名慣例，語意上是item/spell effect池非戰鬥池，
未來若要重新命名需連帶更新`export_sfx.py`的prefix邏輯，本輪未做)。

**取樣率**：沿用既有resource#31/battle家族的11025Hz推定值(見本文件開頭既有段落)，本輪
沒有找到`AIL_set_sample_type`立即數呼叫點確認確切取樣率，維持既有已知限制。
(續一百六十一:取樣率已由 `AIL_init_sample` `0x414e0` 的預設值 `0x2b11` 確認,見本文件開頭。)

**⚠已於2026-09-07補完並訂正，見本檔案末「item 1117 殘留補完」段落。** **誠實範圍**：只驗證了7個已知type對應的sub-index(1/5/6/7/8/12/14)，17個子項裡其餘10個
(0/2/3/4/9/10/11/13/15/16)尚未對到具體item effect type；`FUN_0001d4cb`的其餘5個caller
(`FUN_00015311`/`FUN_0001cff0`/2個unlabeled/`FUN_0002d80d`)沒有逐一確認是否也讀這同一個
resource #80，還是各自另有目的(理論上因為`FUN_0001d4cb`本身完全hardcoded，答案必然相同，
但本輪只在battle情境下實測過，未在其餘5個caller各自的情境下重複live驗證)。

## 2026-09-07：item 1117 殘留（17 個子項只對應出 7 個）補完——完整 type→sub-index 對照直接由表列出

item 1117 關閉時的誠實範圍是「只驗證了 7 個已知 type 對應的 sub-index，17 個子項裡其餘 10 個
未對應」。本輪回頭處理這個殘留，發現**不需要新的 live 驗證，完整對照本來就在 `local_60`
表裡**——先前只是逐個查了手上剛好有名字的那幾個 type，沒有把整張 33 格的表列完。

`local_60`（`0x51f75`，33 bytes，索引 = effect type `param_2`）：

```
06 06 06 06 09 09 09 09 0a 0e 00 00 00 0c 0c 0c 0c 06 07 08 04 04 03 00 00 05 03 02 00 00 00 00 09
```

逐格展開後的完整對照（sub-index 為 FDOTHER 資源 #80 這個巢狀池的子項編號）：

| sub-index | 使用它的 effect type |
|---|---|
| 0（不播音效） | 10, 11, 12, 23, 24, 28, 29, 30, 31 |
| 2 | 27 |
| 3 | 22, 26 |
| 4 | 20, 21 |
| 5 | 25 |
| 6 | 0, 1, 2, 3, 17 |
| 7 | 18 |
| 8 | 19 |
| 9 | 4, 5, 6, 7, 32 |
| 10 | 8 |
| 12 | 13, 14, 15, 16 |
| 14 | 9 |

**結論**：33 個 effect type 全部有明確去向；被引用到的 sub-index 是
**11 個**（2,3,4,5,6,7,8,9,10,12,14），不是先前記錄的 7 個。資源 #80 的 17 個子項中，
**0/1/11/13/15/16 這 6 個從未被 `local_60` 引用**——也就是說它們不是「還沒對應出來」，
而是**item-effect 這條路徑根本不會用到它們**（可能供其他系統使用，或是未使用的素材）。
原殘留敘述「其餘 10 個未對應」因此是誤述：真正的情況是 11 個有對應、6 個確定不被此表引用。

**誠實範圍**：本表回答的是「哪個 effect type 播哪個子項」，**不包含**「effect type 的編號各自
對應遊戲中哪個道具效果的中文名稱」——那是另一個問題（type 命名），本節未處理；6 個未被引用的
子項是否被別的系統使用，本輪也未追查（只確定不由 `local_60` 引用）。

## `play_sfx_a` 與 `play_sfx_b` 的差別:兩個獨立的 AIL sample handle(2026-09-11)

worklist 584 一直把這兩支的差別記為「(音量/聲道)未查」。本輪對比兩支本體後發現
**它們的指令序列逐條相同**,唯一的差別是讀哪一個全域:

| | `play_sfx_a` = `0x25a96` | `play_sfx_b` = `0x25b45` |
|---|---|---|
| 使用的 handle | `[0x53ee4]` | `[0x53ee8]` |
| 守衛 | `[0x53ef1] != 0`、`[0x51e62] != 0`、`[0x54133] == 0` | **完全相同** |
| 呼叫序列 | `0x39805` → `0x39521` → `0x39694` → … | **完全相同** |
| 取樣表偏移 | `[eax+6]` 起點、`[eax+0xa]` 終點 | **完全相同** |

**初始化處給出答案**(`0x25c30`):

```
[0x53edc] = <驅動 handle>          ; 取得失敗(eax==0)就整段跳過,不設可用旗標
[0x53ef1] = 1                      ; 「音效可用」——即兩支 play_sfx 的第一道守衛
[0x53ee4] = 0x392d0([0x53edc])     ; sample handle #1
[0x53ee8] = 0x392d0([0x53edc])     ; sample handle #2   ← 同一個函式,對同一個驅動呼叫兩次
```

`0x392d0` 對**同一個驅動 handle 呼叫兩次**、把兩個回傳值存成兩個相鄰 dword,這是
Miles AIL 配置 sample handle 的標準用法(`0x39xxx` 這一段正是 play_sfx 內部呼叫的
`0x39805`/`0x39521`/`0x39694` 所在的驅動層)。

**結論:兩支是同一段播放邏輯綁在兩個獨立的播放 voice 上,不是音量差異。**
用途是讓兩個音效**重疊播放**——這正好解釋了法術演出 handler 為何交錯使用兩者:
咒殺在動畫影格 6 用 `_a`、影格 `0x24` 用 `_b`;落雷術先 `_b` 後 `_a`(見
`attack_spell_presentation_dispatch.json` 的 `_sfx_index_trigger_conditions`)。
若兩者共用一個 handle,後一個音效會截斷前一個。

**順帶確認兩個守衛全域**:`[0x53ef1]` 是「音效已初始化」(僅 3 個引用,兩處在
play_sfx、一處是上面的初始化);`[0x54133]` 是靜音/暫停旗標(19 個引用,判準是
`!= 0 就跳過播放`)。

~~**誠實範圍**:`0x392d0`/`0x39805`/`0x39521`/`0x39694` 的本體未展開,「Miles AIL
sample handle」是由**呼叫形狀 + 兩次配置 + 驅動層位址群**推得,不是逐指令證實到
驅動內部。兩個 handle 是否有優先權差異(例如 `_b` 可被搶佔)本輪未查。~~
**兩項均已於 §19 補完(2026-09-11):四個函式的名字直接來自 binary 自帶的 AIL_DEBUG
追蹤字串——是資料,不是推論;而「優先權差異」這個問題不成立,整份 image 從未呼叫過任何
優先權/音量/pan/取樣率設定 API。**

## 19. 整層 Miles AIL 的函式名是**資料**,不是推論 —— 105 個進入點機械命名(2026-09-11)

§(play_sfx 那節)的「誠實範圍」寫著:`0x392d0`/`0x39805`/`0x39521`/`0x39694` 的本體未展開,
「Miles AIL sample handle」是由呼叫形狀推得。本輪發現**根本不需要展開本體**。

### 19.1 這份 binary 連進來的 AIL 保留了它自己的 AIL_DEBUG 追蹤設施

每個 AIL API 進入點在共用前導之後,都會把**自己的名字**當格式字串傳給追蹤函式 `0x3f46b`:

```
0x39316  mov  edi, [esp + 0x10]
0x3931a  push edi
0x3931b  push 0x5078d              ; "AIL_allocate_sample_handle(0x%X)
"
0x39320  mov  ebp, [0x54164]
0x39326  push ebp
0x39327  call 0x3f46b
```

obj2 裡這種 `AIL_xxx(fmt)
` 追蹤字串共 **105 條**,涵蓋 Miles AIL 的整個 API 表面
(startup/shutdown、timer、DIG 與 MDI driver、sample、sequence、timbre、channel、
wave synthesizer)。環境變數名 `AIL_DEBUG` / `AIL_SYS_DEBUG` 也在同一段(`0x50313`/`0x50320`)。

### 19.2 `tools/derive_ail_entry_points.py`(新,已登錄產物重生表與突變測試表)

用兩段互相獨立的機制把「字串 → 進入點」做成可重生的對照表
(`docs/data/ail_entry_points.json`,105/105 全解出):

- **字串端**:掃 obj2 找 `AIL_<name>(<fmt>)
`。
- **程式端**:用 LE fixup 表反查每條字串被哪個 `push imm32` 引用,再往前找共用前導對
  `[0x54178]`(巢狀深度計數)的引用,跨過連續的單 byte `push ebx/ebp/esi/edi` 即進入點。

**判準是四個先以手工反組譯獨立確認過的位址必須被純機械地重現**
(`0x392d0`/`0x39521`/`0x39694`/`0x39805`),寫進 `--selftest`。另有負向控制:把前導錨點
換成 `0x54174`(前導裡另一個被讀、但**不是**被 `inc` 的全域),對照表必須對不上真值——
第一版沒有這個控制,而「往前找最近的前導」這一步若沒做事,真值檢查會平凡通過。
**開發過程中這條真值檢查真的抓到一個錯**:前導對 `[0x54178]` 有**兩次**引用(讀 + 寫,
相隔 7 個 byte),第一版取「最近的一次」抓到寫,105 個進入點全部固定偏後 9~10 個 byte,
名字卻全對——只看名字對不對是驗不出來的。

### 19.3 因此可以確認的、以及必須訂正的

**確認**:`play_sfx_a`(`0x25a96`)/`_b`(`0x25b45`)的整段序列現在是字面上的 AIL 呼叫,不是「標準用法」的推測:

```
AIL_stop_sample(h)                        0x39805
AIL_init_sample(h)                        0x39521
AIL_set_sample_address(h, base+[eax+6], [eax+0xa]-[eax+6])   0x39694
AIL_set_sample_loop_count(h, p3)          0x39aae
AIL_start_sample(h)                       0x39798
```

`_a` 全程用 `[0x53ee4]`、`_b` 全程用 `[0x53ee8]`,兩者都由 `AIL_allocate_sample_handle`
(`0x392d0`)對同一個驅動配置——**兩個獨立 voice**這個結論由函式名直接證實。

**訂正一(本文「⚠ 位址勘誤(第 9 輪…)」那張新舊版對照表)**:「`play_sfx_a` 內 `AIL_init_sample` 呼叫」的新版位址寫成
`0x25afd`/`call 0x391d1`。`0x25afd` 是 `push [0x53ee4]`,真正的 `call` 在 `0x25b03`,
目標是 **`0x39521`**;而 `0x391d1` **不是任何 AIL 進入點**(它落在 `AIL_install_DIG_driver_file`
= `0x39176` 的函式體中段)。

**訂正二(本文開頭的簽名)**:`play_sfx_a(table, index, priority)` 的第三個參數不是優先權,
是 **loop count**。逐指令核對堆疊:進入點 `push 0x1c; call 0x3702f; push ebx; sub esp,8` 之後
`[esp+0x18]` 就是第三個參數,而 `0x25b20 push [esp+0x18]` 正是
`AIL_set_sample_loop_count(handle, n)` 的第二個實參。所有呼叫端傳的 `1` 是「播一次」,
不是「優先權 1」。**這又是欄位/參數語意由消費端決定的一例**——「小整數 + 播音函式 = 優先權」
是形狀推論,追到消費端只要一步。

**訂正三(「優先權差異」這個問題不成立)**:整份 image 對
`AIL_set_sample_volume`(`0x399c2`)、`AIL_set_sample_pan`(`0x39a38`)、
`AIL_set_sample_playback_rate`(`0x3994c`)的呼叫端數皆為 **0**;同一支掃描工具對
`AIL_init_sample`(`0x39521`)與 `AIL_start_sample`(`0x39798`)各回 **2 筆**
(`play_sfx_a` 與 `play_sfx_b`),所以這個「0」不是掃描失效——有正向對照。
遊戲從不設音量、pan、取樣率或任何優先權,兩個 handle 的設定完全對稱。
這順帶**獨立佐證**了本文既有的結論「兩支的差別是 `[0x53ee4]`/`[0x53ee8]` 兩個獨立播放 voice,不是音量差異」:
音量 API 根本沒被呼叫過。

## 2026-11-06:`0x54153..0x54195` 的 11 個全域 —— 戰鬥演出音效 bank 與 AIL_DEBUG 追蹤設施的狀態(資料區段登錄,`docs/data/data_map.json`)

全部由原版 FD2.EXE 反組譯逐條讀過(`python tools/disasm_le.py FD2.EXE range 0x37b8c 0x37ed8`),
寬度與讀寫次數來自 `python tools/re_coverage.py --show-data`。除了 `0x5417c` 是字串緩衝,其餘都是 4 byte 直接定址。
`0x54157` 沒有任何引用(不登錄)。

### `[0x54153]`:戰鬥演出期間的音效 bank 指標(不屬於 AIL)

32 筆存取,寫 4、讀 28。寫入點成對:`0x2d977` / `0x30262` 先寫 0,緊接 `push idx; push 0; push 0x51a4d ("FDOTHER.DAT"); call 0x111ba`
(通用資源載入器 load(filename, oldbuf, index)),`0x2d99a` / `0x30284` 寫回載入結果;寫入點分屬 `0x2d80d` 與法術場景 `0x2ff01`。
讀取:**26 筆 `push dword ptr [0x54153]` 接 `call 0x25a96`(19)或 `call 0x25b45`(7)**(兩個 play_sfx),分布在 13 個函式;
另 2 筆是演出結束時 `push dword ptr [0x54153]; call 0x3776e`(free,`0x2dda6` / `0x30d23`)。
所以它是「目前這段戰鬥演出載入的 FDOTHER 音效 bank」,演出開始載入、結束釋放。
(交接文件曾把 `0x54153..0x5417c` 整批寫成 AIL 內部狀態;`0x54153` 不是。)

### AIL_DEBUG 追蹤設施(`0x54158..0x54195`)

`0x37d3e` 就是 `ail_entry_points.json` 唯一沒解出的 `AIL_startup`(追蹤站 `0x37ebe` 在它裡面:`0x37ebd push 0x5042e "AIL_startup()\n"`)。流程:

1. `call 0x37b8c`:`[0x527e4]` 為 0 時,用 DPMI `int 0x31` ax=`0x600`(Lock Linear Region,`0x365da`)鎖住程式碼 `0x37b8c..0x3ca23`,
   再用 `0x3666c(addr, 4)` 逐一鎖住 `0x54174`、`0x54170`、`0x54164`、`0x54168`、`0x5416c`、`0x54160`、`0x5415c`、`0x54158`,最後 `[0x527e4] = 1`。
2. `[0x54174] = 0`、`[0x54170] = 0`。`getenv("AIL_DEBUG")`(`0x50313`)為 NULL 就直接做真正的 startup(`0x3fca9`)後返回 ——
   **一般執行不設 AIL_DEBUG,所以下面的狀態全部停在 0,追蹤不會輸出任何東西**。
3. `getenv("AIL_SYS_DEBUG")`(`0x5031d`)非 NULL → `[0x54170] = 1`。
4. `fopen(AIL_DEBUG 的值, "w+t")`(`0x37324`,模式字串 `0x5032b`)→ `[0x54164]`(寫入點 `0x37d9d`,全程唯一一次寫入);NULL 同樣直接 startup 返回。
5. `time` → `localtime` → `asctime` → `strcpy(0x5417c, …)`,再 `mov byte ptr [0x54194], 0`:
   asctime 的結果是 26 byte(24 字 + `\n` + NUL),第 24 byte 的 `\n` 被改成 NUL。之後印表頭
   `"Audio Interface Library application usage script generated by AIL V%s\n"`(`%s` = `"3.02"`)與 `"Start time: %s\n"`(引數 `0x5417c`)。
6. 真正的 startup(`0x3fca9`)後,時鐘四格清 0,`0x3f236(0x37c30)` 登錄計時器回呼、結果寫 `[0x54158]`(`0x37e83`),
   `0x3f3c8(handle, 100)` 設 100 Hz、`0x3f2f0(handle)` 啟動(這三個內部函式的名稱是依引數形狀對應 AIL 的
   register_timer / set_timer_frequency / start_timer,INFERRED;100 Hz 由回呼本身「100 次進 1 秒」交叉印證)。
7. `[0x54174] = 1`、`[0x54178] = 1`,印時間戳(`0x37c9c`),`[0x54178] = 0`,印 `"AIL_startup()\n"`。

100 Hz 回呼 `0x37c30` 是一個經過時間的時鐘:`[0x5415c]` 每次 +1,到 100 歸 0 並讓 `[0x54160]` +1;`[0x54160]` 到 60 歸 0 並讓 `[0x5416c]` +1;
`[0x5416c]` 到 60 歸 0 並讓 `[0x54168]` +1。進入時若已是 99:59:59.99 就不再走(上限)。
所以 `0x5415c` / `0x54160` / `0x5416c` / `0x54168` = 百分秒 / 秒 / 分 / 時。

時間戳 `0x37c9c`:在 `0x3ea74` / `0x3ea81`(對 `[0x52bea]` 加一 / 減一)之間讀出四格;`[0x54178] == 1` 時
`fprintf([0x54164], "[%.02u:%.02u:%.02u.%.02u] ", 時, 分, 秒, 百分秒)`(`0x502f4`),
否則印 14 個空白(`0x5030f` 印 14 次)再印 `[0x54178] − 1` 個 `0xFA`(`0x50311`)當縮排。

每個 AIL API 進入點的共用前導(例 `AIL_shutdown` `0x37ed8`):`[0x54178]` +1;`[0x54174] != 0` 且(深度 == 1 或 `[0x54170] != 0`)
且 `0x3f22a()` 回 0 時才印時間戳與 `"AIL_xxx(...)\n"`;結尾 `dec dword ptr [0x54178]`。
`[0x54178]` 的 111 個寫入點:`mov edx,[0x54178]; inc edx; mov [0x54178],edx` 共 105 條(104 個進入點 + `AIL_startup` 的設 1),
`AIL_startup` 歸 0 一條,`dec dword ptr [0x54178]` 只有 5 條 —— 其餘進入點離開時跳到共用的結尾(例 `0x3916a`)做 −1。
因此:**`[0x54178]` = AIL API 呼叫巢狀深度**(331 筆存取);
**`[0x54174]` = 追蹤已開啟**(只在 `0x37d4b` 寫 0、`0x37ea6` 寫 1);
**`[0x54170]` = AIL_SYS_DEBUG**(內部巢狀呼叫也記錄;只在 `0x37d51` 寫 0、`0x37d85` 寫 1);
**`[0x54164]` = 追蹤檔 FILE\***(246 筆存取:寫 1、取址 1(鎖定)、讀 244,其中 238 筆讀之後的第一個 call 是追蹤輸出 `0x3f46b`)。
`AIL_shutdown` 收尾時 `0x3759c([0x54164])` 關檔。

## 2026-11-06:`[0x538a8]` / `[0x538b0]` = AIL 混音一輪的來源結束位址 / 建構緩衝結束位址(資料區段登錄,`docs/data/data_map.json`)

FD2.EXE 反組譯逐條讀過,存取次數來自 `python tools/re_coverage.py --show-data`:兩個位址各 **74 筆,全是 4 byte 直接定址,讀 73、寫 1**,引用它們的是同一組 73 個函式
(`ail_mix_samples` `0x49690` + 72 個 `mix_merge_*` 累加常式)。

寫入都在 `ail_mix_samples`(參數 S = 取樣,`0x4969b` 由 `[S + 0]` 取驅動 D):
- `0x49778`(迴圈外,一次):`[0x538ac] = [D + 0x50]`、**`[0x538b0] = [D + 0x50] + [D + 0x4c]`** —— 建構緩衝的起點加長度 = 結束位址。
- `0x4979b`(迴圈 `0x49783` 內,每換一個取樣緩衝重寫):b = `[S + 0x28]`,`[0x538a4] = [S + 8 + b*4] + [S + 0x18 + b*4]`、
  **`[0x538a8] = [S + 8 + b*4] + [S + 0x10 + b*4]`** —— 目前取樣緩衝的起點加長度 = 結束位址(`[0x538a4]` 是起點加已播位置 = 本輪讀取起點)。

讀取:**73 筆 `[0x538a8]` 全是 `cmp esi, dword ptr [0x538a8]`、73 筆 `[0x538b0]` 全是 `cmp edi, dword ptr [0x538b0]`**。
72 個累加常式各一筆(例 `mix_merge_8_mono_u_to_mono` `0x489c6`:esi 到 `[0x538a8]` 或 edi 到 `[0x538b0]` 就 ret);
`ail_mix_samples` 各一筆:常式返回後 `0x497dc` / `0x497e0` 把 esi − 起點寫回 `[S + 0x18 + b*4]`,
`0x497e4` esi 未到 `[0x538a8]` 就結束這一輪(來源還有剩,是建構緩衝滿了),到了才處理迴圈次數 / 換緩衝;`0x49813` edi 未到 `[0x538b0]` 就回 `0x49783` 用下一個緩衝繼續填。
72 個累加常式裡 36 個另外讀 `[0x538b4]` / `[0x538b8]`(`0x49733` / `0x4975b` 寫入的重取樣步進),這兩個位址本輪不登錄。

## 2026-11-06:`0x5030f` / `0x50311` = AIL_DEBUG 記錄的縮排字串 `" "` / `"\xFA"`(資料區段登錄,`docs/data/data_map.json`)

FD2.EXE 反組譯逐條讀過,存取次數來自 `python tools/re_coverage.py --show-data`:兩個位址各 **60 筆,全是 `push` 取位址(沒有讀寫內容)**,在同樣的 54 個函式裡。
內容:`0x5030f` = `20 00`(`" "`),`0x50311` = `fa 00`(`"\xFA"`),後面 `0x50313` 是 `"AIL_DEBUG"`;前面 `0x5030e` 是 `0x502f4` 時間戳格式字串的結尾 NUL。

**60 處全是同一個形狀**(以 `0x3801b` 為例):
`xor ebx, ebx; jmp` → `push 0x5030f; push dword ptr [0x54164]; call 0x3f46b`(fprintf)`; inc ebx; cmp ebx, 0xe; jb` ——
接著 `mov ebx, 1; jmp` → `push 0x50311; push dword ptr [0x54164]; call 0x3f46b; inc ebx; cmp ebx, dword ptr [0x54178]; jb`。
**120 個推入點逐一檢查:60 個 `0x5030f` 都是 `cmp 計數, 0xe` + `jb` 回推入點、前面 `xor` 清 0;60 個 `0x50311` 都是 `cmp 計數, [0x54178]` + `jb`、前面 `mov 計數, 1`。**
所以每處印 14 個空白再印(巢狀深度 − 1)個 `0xFA`,寫到 AIL_DEBUG 記錄檔 `[0x54164]`。

分布:1 處在 `ail_debug_trace_prefix` `0x37c9c`(深度不是 1 時取代時間戳,即上面「否則印 14 個空白」那一支);其餘 59 處在另外 53 個函式裡(`0x37f70` .. `0x3c8b4` 的 AIL 程式碼,`0x3846a` 有 7 處),
縮排之後接著 fprintf 一行記錄(例 `0x38017` 這一處,後面是 `push esi; push 0x50468`(`"Result = %d\n"`))。14 個空白與時間戳 `"[%.02u:%.02u:%.02u.%.02u] "` 的 14 字等寬。

## 2026-11-07:`[0x538b4]` / `[0x538b8]` = AIL 重取樣的分數步進 / 整數步進(資料區段登錄,`docs/data/data_map.json`)

FD2.EXE 反組譯逐條讀過,存取次數來自 `python tools/re_coverage.py --show-data`:兩個位址各 **37 筆,讀 36、寫 1**,引用它們的是同一組 37 個函式
(`ail_mix_samples` `0x49690` + 36 個重取樣累加常式)。`[0x538b4]` 37 筆全是直接定址;`[0x538b8]` 的 36 筆讀取是直接 6、索引 30。EXE 內初值都是 0。

寫入都在 `ail_mix_samples`(ecx = S = 取樣、edi = D = 驅動,`0x4969b` `mov edi, [ecx]`),在迴圈外算一次:
- `0x496fd`..`0x49715`:`edx:eax = [S + 0x3c] << 32`(`[S + 0x3c]` ≤ 0 時當 1),`div ([D + 0x14] << 16)` → eax = `[S + 0x3c] × 0x10000 / [D + 0x14]`,16.16 定點的步進比。
  (`[S + 0x3c]` = 取樣播放率、`[D + 0x14]` = 驅動輸出率是依這個除法的形狀推定,INFERRED。)
- `0x49719`..`0x49729`:`|eax − 0x10000|` ≤ `[0x54324]` 就跳過(`jbe 0x4976d`),不設重取樣。
- 否則:ebx = eax >> 16(整數部分),**`0x49733` `[0x538b4]` = eax << 16**(只留分數部分,放在高 16 位元);eax = 整數部分、ebx = 整數部分 + 1;
  `[0x538a0]` 有 2(來源雙聲道)就兩者 × 2、有 8(16 位元來源)再 × 2,**`0x4975b` `[0x538b8]` = eax**(整數步進 byte 數)、`0x49760` `[0x538bc]` = ebx(整數 + 1 的 byte 數),
  `0x49766` `[0x538a0] |= 0x20`(選重取樣版累加常式)。

讀取:**36 筆 `[0x538b4]` 全是 `add ecx, dword ptr [0x538b4]`**,每個重取樣常式一筆;ecx 累加分數,溢位進位 = 來源多走 1 個取樣。之後取來源指標的方式有兩種:
- **6 筆 `adc esi, dword ptr [0x538b8]`**(直接定址):6 個 `mix_merge_8_mono_*_resample_*`(`0x48d7a` / `0x48da6` / `0x4902c` / `0x49053` / `0x49430` / `0x49457`)。來源取樣 1 byte,esi += 整數步進 + 進位。
- **30 筆 `xor ebp, ebp; add ecx, [0x538b4]; adc ebp, ebp; add esi, dword ptr [ebp*4 + 0x538b8]`**(索引):來源取樣 2 或 4 byte,進位不能直接加,
  改用 ebp = 進位(0 / 1)挑 `[0x538b8]`(整數步進)或 `[0x538bc]`(整數 + 1)。30 個裡 28 個名字帶 `_resample`,另 2 個是沿用舊名的
  `0x48f6c` `mix_merge_16_stereo_u` / `0x48fea` `mix_merge_16_stereo_swap_u`(doc98 的 AIL 混音累加表條目記為第 0xab / 0xaf 格:16 位元雙聲道、無號、重取樣)。
- 6 + 30 = 36,和 `[0x538b4]` 的 36 個讀取常式是同一組。

`[0x538bc]` 本輪不登錄:除了上面的 `0x49760` 寫入與 30 筆以 `0x538b8` 為基底的索引讀取,`math_err_build_exception` `0x499da` 的 `0x49a4c` 另有一筆 `[eax*4 + 0x538bc]`(eax = 旗標 & 0x1f),用途沒有追。

## 2026-11-07:`[0x53eec]` = UI 音效池(FDOTHER.DAT 第 31 號資源)的指標(資料區段登錄,`docs/data/data_map.json`)

FD2.EXE 反組譯逐條讀過,存取次數來自 `python tools/re_coverage.py --show-data 0x53eec`:**62 筆全是 4 byte 直接定址,讀 61、寫 1**,分布在 24 個函式。EXE 內初值 0。

**唯一的寫入點**是 `game_main` `0x25bf4` 的 `0x25c78`:`0x111ba("FDOTHER.DAT"(0x51a4d), [0x53eec], 0x1f)` 的回傳值,之後不再改。
(本篇 §2 的 `0x26a63` / `0x26a78` / `call 0x11fba` 是同一段程式的檔案位移,和線性位址差 0xe00。)

**61 筆讀取**:
- `0x111ba` 的舊緩衝引數 1 筆:`game_main` `0x25c65`(就是上面那次載入)。
- **`push dword ptr [0x53eec]` 緊接 `call 0x25a96`(play_sfx_a)57 筆**。前一條推的是音效號:
  - 0 號 36 筆:`item_grid_select` 6、`command_grid_select` 6、`battle_main_input_loop` 4、`item_list_select` 4、`choice_box_left_right` 4、`sortie_member_select` 4、`town_hub_main` 2、`carousel_menu_select` 2、`equip_compare_select` 2、`target_cursor_loop` 1、`copy_protection_password_check` 1(多半是選單游標移動)。
  - 1 號 1(`town_hub_main` `0x265a1`)、2 號 3(`typewriter_tick` `0x16540`、`copy_protection_password_check` `0x34120` / `0x3415c`)、3 號 1(`unit_death_sweep` `0x1dda4`)、4 號 2(`rest_hp_recover` `0x14037`、`battle_phase_advance` `0x1a3d9`)。
  - 5 號 4(`unit_info_cards` `0x17c50`、`info_card_open_anim` `0x17ed8`、`save_slot_selector` `0x29c84`、`sortie_member_select` `0x2b084`)、6 號 3(`unit_info_cards` `0x17b28` / `0x17d20`、`sortie_member_select` `0x2b1eb`)。
  - 7 號 4(`battle_main_input_loop` `0x11934`、`save_slot_selector` `0x29d2a` / `0x29d66`、`copy_protection_password_check` `0x34178`)、8 號 2(`action_ring_open` `0x1748f`、`action_ring_close` `0x176cd`)、0xb 號 1(`play_step_sfx` `0x32301`)。
  - 前第 2 條推的第 3 個引數:55 筆是 1;`town_hub_main` `0x265a1` 是 3、`copy_protection_password_check` `0x341e1` 是 eax。
- **`push dword ptr [0x53eec]` 緊接 `call play_digital_sample` `0x25b45` 3 筆**:0xc 號 2(`ai_mode_dispatch` `0x13d0d`、`field_cell_treasure_check` `0x191a3`,後者第 3 個引數是 ebx)、7 號 1(`sortie_member_select` `0x2b0c1`)。

1 + 57 + 3 = 61。用到的音效號最大 0xc。

## 2026-11-07:`0x541f4` = AIL 的錯誤訊息緩衝(256 bytes;資料區段登錄,`docs/data/data_map.json`)

存取來自 `python tools/re_coverage.py --show-data 0x541f4`:**40 筆,位址引用 39、1 byte 寫入 1**,分布在 20 個 AIL 函式,沒有遊戲函式。EXE 內初值 0。

- **內嵌 strcpy 35 筆**:`mov edi, 0x541f4; mov esi, 訊息; mov ecx, n; rep movsd`,再以 movsw / movsb 補尾。訊息都是 AIL 自己的錯誤字串,
  例如 `ail_impl_api_read_ini` `0x3f907` 複製 `0x511f7` `"Corrupted .INI file\n"`(ecx 5 → 20 bytes,加 movsb 1 byte = 21 = 字串 20 字 + NUL)、
  `ail_driver_install_core` `0x3f968` 複製 `0x5120c` `"Insufficient memory for driver descriptor\n"`、`ail_impl_create_wave_synthesizer` `0x45e47` 複製 `0x516a0` `"Insufficient memory for HWAVE descriptor\n"`。
  分布:`ail_dig_install_core` 7、`ail_mdi_install_core` 6、`ail_driver_install_core` 5、`ail_impl_init_sequence` 3、`ail_impl_allocate_file_sample` 2、`ail_impl_set_sample_file` 2,其餘 10 個函式各 1。
- **`sprintf(0x541f4, 格式, …)` 2 筆**:`ail_impl_init_sequence` `0x4475d`(格式 `0x51638` `"Driver could not install timbre bank %u, patch %u\n"`)、`ail_impl_install_timbre` `0x44bd3`(格式 `0x5166c`)。
- **DPMI 鎖定 2 筆**:`ail_api_lock_memory` `0x3f51f` `dpmi_lock_range(0x541f4, 0x100)`、`ail_api_unlock_memory` `0x3fe1b` `dpmi_unlock_range(0x541f4, 0x100)`。
- **清空 1 筆**:`ail_set_default_preferences` `0x3fca9`(上一節所說真正的 startup)的 `0x3fda4` `mov byte ptr [0x541f4], ah`(ah 剛 `xor ah, ah`)。

35 + 2 + 2 + 1 = 40。長度 256 bytes:鎖定範圍是 0x100,下一個被引用的位址正好是 `0x542f4`。
40 筆裡沒有讀取 —— EXE 裡沒有直接讀這段文字的指令(以常數位址間接取用的情形本輪沒有查)。

## 2026-11-07:`[0x53b13]` = 法術 / 效果演出用的音效 bank(FDOTHER.DAT 第 80 或 88 號資源;資料區段登錄,`docs/data/data_map.json`)

存取次數來自 `python tools/re_coverage.py --show-data 0x53b13`:**21 筆全是 4 byte 直接定址,讀 17、寫 4**,分布在 14 個函式。EXE 內初值 0。

**4 個寫入點 = 2 個載入處,各先寫 0 再寫 `load_res("FDOTHER.DAT"(0x51a4d), 0, 號)` 的結果**:
- `load_fdother_80_to_53b13` `0x1d4d5` / `0x1d4f0`:80 號(0x50)。呼叫端 6:`ai_spell_execute` `0x1540a`、`player_spell_select` `0x1d446`、`item_effect_dispatch` `0x20c87`、`0x24618` 的 `0x2462d` / `0x2474a`(開頭與結尾各一次)、`spell_scene_effects` `0x2ddbe`。
- `command_handler_52` `0x33979` / `0x33994`:88 號(0x58),寫入前先呼叫 `0x205da`。
- 兩處的舊緩衝引數都是 0。

**17 筆讀取**:
- 當 `play_sfx_a(bank, 音效號, 1)`(`0x25a96`)的 bank 16:
  - 音效號 1:`0x1c2da` `0x1c303`(呼叫端 11 個效果函式)、`command_handler_52` `0x339e5` / `0x33a0e` / `0x33a37` / `0x33a60`(前 3 次之後各接 `0x24b4d(0x14)` 與 `0x3790a(0x258)`)。
  - 音效號 2:`command_handler_11` `0x2186d`、`command_handler_12` `0x21aac`。
  - 音效號 0xb:`command_handler_13` `0x21ae7`、`command_handler_14` `0x21ba7`、`command_handler_15` `0x2212a`、`command_handler_16` `0x22161`、`0x24618` `0x2467f`。
  - 音效號 0xd:`earthquake_spell_effect` `0x217ac`;音效號 0:`spell_palette_flicker` `0x1d6dc`;音效號 −1:`play_loaded_sfx_and_free` `0x1d504`。
  - 音效號來自表格:`play_map_effect_animation` `0x1c656`(`byte [esp + ebp + 0x28]`,doc35 記的 `0x51f75` +4 表)。
- 釋放 1:`play_loaded_sfx_and_free` `0x1d512` `push [0x53b13]` 後 `jmp 0x1a80a`,那裡是 `call 0x3776e`(heap_free)。

5 + 2 + 5 + 3 + 1 = 16;16 + 1 = 17。EXE 裡釋放 `[0x53b13]` 的只有這一處;`play_loaded_sfx_and_free` 的呼叫端 4 個(`ai_spell_execute`、`player_spell_select`、`item_effect_dispatch`、`spell_scene_effects`),
都同時是 `load_fdother_80_to_53b13` 的呼叫端。`0x24618` 與 `command_handler_52` 載入後沒有對應的釋放(本輪只查直接引用)。
91-worklist 記的字面音效號 {0, 1, 2, 11, 13, 255} 與這裡相同(255 = −1)。
