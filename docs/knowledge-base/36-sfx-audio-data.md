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
0x026896  play_sfx_a(table, index, priority):
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
push index          ; 通常是常數(0/2/3/4/5/6/7/8/0xb/0xc),少數是暫存器(動態 index)
push table_ptr       ; 通常是 [0x53eec](UI 音效池),戰鬥路徑另有動態表(見下)
call 0x25a96         ; (或 0x25b45 = handle B,允許與 handle A 疊播)
```

全 EXE 掃描(遞迴找 `call 0x25a96`/`call 0x25b45` 的相對呼叫端,而非線性 sweep,避免誤判):
`play_sfx_a` **107 處**、`play_sfx_b` **11 處**。table_ptr 除了 `[0x53eec]`(UI 池,本篇 14 個樣本)外,
還有 `[0x53b13]`、`[0x54117]`、`[0x5411f]`(= 第 8 輪記錄的 `[0x5411f]`,戰鬥動態表,前綴 `0x54` 打字誤
差 1 位)三個**不同的資源**,不是同一批 14 個 UI 樣本——**戰鬥音效與本篇 UI 音效是兩個獨立池**,對照
時不要混用。

### `[0x53eec]`(UI 音效池,對應本篇 WAV)index 語意

| index | 呼叫端數量(A+B) | 觸發情境(反組譯呼叫端上下文) | 信心 |
|---|---|---|---|
| 0 | 30+ | 遊戲各處大量重複出現;**5 處直接掛在方向鍵掃描碼比對之後**(`cmp eax,0x48/0x50/0x4b/0x4d` 分別對應上下左右,見 `0x117a1`/`0x11a33`/`0x11a54`/`0x11a75`/`0x11a96`),與 `sfx_00`(160 bytes,14.5ms 短促)長度吻合 | **確認:游標移動音** |
| 2 | 2 | `0x16546` 等,前置呼叫非明顯繪圖/文字函式,語意未定 | 待確認 |
| 3 | 1 | `0x1ddaa`,前置呼叫 `0x11eee`(帶 `0x1c8/0xd/8` 座標類參數,疑為繪視窗/框線)+ `0x127a9` | 待確認(疑開窗音) |
| 4 | 2 | `0x1a3df` 等,前置呼叫 `0x11eb0`(同樣帶座標參數)並用回傳的 flag 條件觸發(`cmp byte ptr[esp+4],0`) | 待確認 |
| 5 | 4 | `0x17c56`/`0x3060f` 等,前置皆呼叫 `0x4e8af`(帶字串指標參數,疑為顯示文字/訊息) | 待確認(疑文字顯示音) |
| 6 | 3 | `0x17b2e`/`0x31b76` 等,一處是條件式(`0x1c269` 回傳非 0 才播)、一處是 12 項清單迴圈中 `ebx==0` 或 `ebx==7` 時播 | 待確認 |
| 7 | 3(A)+1(B) | `0x1193a` 等,某位元旗標檢查失敗時播(`test eax,eax; je →播7`),否則呼叫另一函式 `0x17aed`(其內部在 `0x17b2e` 播 index 6) | 待確認 |
| 8 | 1 | `0x17495`,前置為陣列索引運算後把 4 個 dword 設為 `0x390`(疑重置某計數) | 待確認 |
| 0xb | 1 | `0x2cac3`,以 `某計數 % 9 == 0` 為觸發條件(`idiv 9; test edx,edx; jne 跳過`),疑週期性動畫 tick 音 | 待確認 |
| 0xc | 1(僅 handle B) | `0x13d13`,伴隨把 `[某結構+0x31]`byte 設 1(疑「已選定」旗標),用 handle B 播放以便與正在播的 handle A 疊聲 | 待確認 |

僅 index 0(游標移動)有多重獨立證據(5 個方向鍵分支 × 波形長度吻合)可視為確認;其餘 index 已列出
確切呼叫端位址與上下文,但語意需要配合畫面實測(第 10 輪待辦)才能升級為確認,此處不臆測標籤。

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
              走自己的 body ── 物理攻擊動畫 + SFX 池載入(見下)
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
1. action_id 0-9 對應的玩家可讀招式名稱(劍/斧/拳/弓/…)未解 ── 同一函式另外用 `unit.byte[7]` 選
   `FIGANI.DAT` 動畫資源,語意上兩者可能共享同一條「武器類別」軸,但未交叉證實;需要下一輪對照
   `FDICON`/指令文字表,或允許動態驗證時用 DOSBox-X 實測按鍵觸發哪個 id(本輪任務範圍禁止碰
   DOSBox-X/WSL2)。
2. 每個資源池內 2-5 個子樣本各自何時觸發(例如揮空/命中/爆擊分別對應哪個 sub index)未追出 ──
   需要反組譯「每指令動畫函式指標表」`DAT_000524c6[action_id*4]` 的個別函式內容,本輪只定位了表位址,
   未展開。
3. action_id 12-21/25-27 載入的非 SFX 資源型態未鑑定。
4. action_id 10/11/22/23 落在表的未初始化缺口,語意不明。
5. ~~`FUN_0002d80d`(id≥0x20 分支)自己的 index 來源未追出~~ → **2026-08-24 續輪已追出並關閉,見上方引述段落**:`DAT_00052668` 四個 byte(91/92/93/94)。

**worklist L584/604/622 完成度**:三項合併視為「逐招對照」核心同一件事的完成度判斷 ──
- ✅ 修正了 round10/11 引用的錯誤函式位址(`0x027fc9` 其實是無關的選單迴圈;真正的攻擊總派送函式是
  `0x2ff01`,其上游 caller `0x1cff0`/`0x015311` 位址本身原本就是對的)。
- ✅ 完整解出「action_id 0-9 → `FDOTHER.DAT` #82-90」的資源層級對照,10/10(9 個獨立資源,id0/1共用)
  皆逐一解包驗證為合法 PCM SFX 池,且 sub0 共用機制與第10輪推論吻合,25 個 WAV 已匯出。
- ✅ **2026-08-24 續輪**:`0x20-0x23` 分支自己的 index 來源已追出並關閉(`DAT_00052668`→91-94,四個
  WAV 已驗證匯出),見上方引述段落與 doc27 §6.5。
- ❌ 未解:id 0-9 對應的玩家可讀招式名稱;池內子樣本個別觸發時機;id 12-21/25-27 載入資源的型態;
  id 10/11/22/23 的表缺口。
- **綜合判斷**:三項從「核心完全未解」推進到「資源層級 index 對照已完整解出且逐一驗證,語意標籤與
  sub-index 觸發時機仍缺」── **部分關閉,非完全關閉**。建議下一輪標題聚焦「`DAT_000524c6` 個別指令
  動畫函式反組譯 + 招式中文名稱交叉對照」,方法沿用本輪的 Ghidra headless decompile(不要再用
  `tools/disasm_le.py` 手動反組譯這個位址範圍)。

## 導出 WAV:戰鬥音效候選池(第 10 輪)

> **記憶修正（2026-07-25）**：本節舊版「40-bit 已知招式遮罩／已學會招式清單」措辭已作廢。`0x1c269` 目前只證實為 5-byte bit-scan 與輸出 ABI；其欄位不命名為 spell、move 或 learned-list，且不得把 `unit+0x22..+0x24` raw transient/modifier bytes 當成法術 bitfield。

`tools/export_sfx.py --battle` 把上表 9 個候選資源解開巢狀容器,逐子樣本補 WAV 檔頭,輸出到
`remake/assets/sfx/battle_<資源號>_<子序>.wav`。2026-08-01 另加入固定資源 #95：
`0x32999` 的第1次呈現直接呼叫 `0x25A96(resource95,0,1)`；其容器有1個
10444-byte 有效 raw PCM 與1個空哨兵，因此目前 `--battle` 共匯出43個 WAV。
11025Hz 仍是工具鏈推定值，#95 的玩家可聽語意也仍未知；不能因 runtime 已接線
就提升成已證實的音效名稱。
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
