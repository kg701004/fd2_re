# 驅動腳本存檔(續一百 ~ 一百三十三)

當時在 DOSBox-X / WSL 上產生原始紀錄的 scratchpad 腳本。每個檔第一行(`.sh` 在 shebang 之後)加了「存檔」標頭,換行改成 LF,其餘內容不改;
路徑保留當時的工作環境(`C:/Users/kg701/...`、WSL `~/fd2-run-harness-*`、修補版 dosbox-x 的位置),不保證能直接執行。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu` 使用。

- 怎麼挑的:從對話紀錄找出 2026-10-06 之後真的被執行(`python X.py`、`bash X.sh`、`wsl ... X`,不算 cat / sed / grep 讀檔)的 scratchpad 腳本,
  留下操作 DOSBox-X / WSL 的,再補上它們 import 或呼叫的檔(`live.py`、`cl.py`、`s103_dedup.sh`)。
- 版本:是 scratchpad 的最後一版。每個檔最後一次修改都在最後一次執行之前,所以至少等於最後一次執行的版本;更早的執行(例如 `lc122.py` 在
  10:27 ~ 10:58 之間改過)用的是不是同一版,沒有逐次比對。表裡的 sha256 是加標頭前的原檔。
- `live.py` 是續六十六那支小工具後來的版本,與上一層 `generators/live.py` 不同(所以放在這個子目錄,`from live import` 會取到這一份)。
- `logs/`:lc122 ~ lc131 執行時的 stdout(`*_launch.txt` 有 harness 裡 FD2.EXE 的 md5)。`mk_a1_125.py` 讀 `lc125_rec_a1_part1.txt`。
- 靜態檢查(2026-10-19,沒有在 DOSBox-X 上重跑):28 個 `.py` 可解析、沒有未定義名稱、import 找得到、`模組.屬性` 在 tools/ 模組裡存在、
  helper 子命令存在;12 個 `.sh` 過 `bash -n`、呼叫的腳本都在本目錄或 tools/。

| 檔 | 原檔 sha256(前 16 碼) | 對話紀錄裡的執行時間(UTC,第一次 .. 最後一次) | 用途(檔頭第一行) |
|---|---|---|---|
| `lt.py` | `0546d92726044bc3` | 2026-10-07T07:45 .. 2026-10-07T08:37 | 續一百:原版 FD2.EXE 從開機就錄的 LOGC 擷取驅動(只對原版 EXE,WSL -d Ubuntu)。 |
| `s102.py` | `cb6ac12334470755` | 2026-10-07T12:19 .. 2026-10-07T12:32 | 續一百零二:原版 FD2.EXE 第 1 章戰場,只在敵方回合錄 LOGC(只對原版 EXE,WSL -d Ubuntu,instance s102)。 |
| `s103.py` | `2a23814b0d5f7dc6` | 2026-10-07T13:28 .. 2026-10-07T15:58 | 續一百零三:原版 FD2.EXE 第 1 章戰場,玩家逐一施放法術 9..27 與敵方 [0x53af9]=1 回合錄 LOGC(只對原版 EXE,WSL -d Ubuntu,instance s103)。 |
| `s103_grep.sh` | `894e73c809dc6637` | 2026-10-07T14:22 .. 2026-10-07T14:22 | 續一百零三:在 LOGCPU.TXT 找 28 個法術 handler 入口第一次出現的行號(背景跑,完成時寫 grep.done)。 |
| `s103_dedup.sh` | `d86a348c8017f9ac` | 2026-10-07T14:24 .. 2026-10-07T15:58 | 續一百零三:原始軌跡去重成 <name>_unique_cseip.txt(背景跑,完成寫 <name>.done)。用法:s103_dedup.sh <workdir> <raw 檔> <name> |
| `s103c_dedup_both.sh` | `1300076d16374709` | 2026-10-07T15:41 .. 2026-10-07T15:41 | 續一百零三:s103c 兩段原始軌跡依序去重(不平行,避免 WSL I/O 擁塞)。完成寫 s103c_all.done。 |
| `s104_arm.py` | `9f7b498e60184fd9` | 2026-10-07T15:54 .. 2026-10-07T15:54 | 續一百零四:s104 停在開機,BPINT 21 4B 逐次 RUN,DS:DX 是 FD2.EXE 時刪斷點、LOGC 7FFFFFFF(會恢復執行)。 |
| `fpu_opt_test.sh` | `1ee63fb721b162aa` | 2026-10-07T17:13 .. 2026-10-07T17:13 | 從 dosbox_harness.sh 抽出 FD2_HARNESS_FPU 區塊,逐值測:合法值 -> 參數、非法值 -> die、未設 -> 空 |
| `calllog_opt_test.sh` | `2ebcea4fa45bc5be` | 2026-10-08T01:20 .. 2026-10-08T01:20 | 把 dosbox_harness.sh 的 FD2_HARNESS_CALLLOG 區塊單獨抽出來逐值測(die 換成 exit 1 的樁)。 |
| `trace_census.sh` | `8739736a910aa177` | 2026-10-07T03:21 .. 2026-10-07T03:21 | WSL:~ 底下所有 trace_unique_cseip.txt 的雜湊分布,與其他可能的軌跡輸出 |
| `cl.py` | `a9957db704b5e07f` | 2026-10-08T01:45 .. 2026-10-17T06:52 | 續一百零八:以修補版 dosbox-x(FD2_HARNESS_CALLLOG)照既有路線錄函式呼叫紀錄(只對原版 FD2.EXE,WSL -d Ubuntu)。 |
| `ringidx.py` | `657f2a72dc2ccc27` | 2026-10-08T02:33 .. 2026-10-08T02:34 | python ringidx.py NAME:停機讀 [0x53c57](指令環選項)與 [0x53a45](單位陣列指標,判斷 selector 是否為遊戲的),再恢復執行。 |
| `rig.py` | `849551c9bb503dea` | 2026-10-08T03:04 .. 2026-10-08T03:05 | 續一百零八 cl4:續一百零二的受控設計(敵方 AI 施法 / 攻擊 / 道具),寫入後逐筆讀回。只對原版 FD2.EXE 的 harness instance。 |
| `dbgclear.sh` | `61e5dcf798513085` | 2026-10-08T02:34 .. 2026-10-08T02:34 | 清掉 harness 除錯器輸入列(退格),再送 RUN;$1 = instance 名稱 |
| `cl5.py` | `f8eb766a7a3ced17` | 2026-10-08T05:50 .. 2026-10-08T06:31 | 續一百一十一 cl5:第 1 章戰場,給悠妮 8 個法術與 MP,逐一施放,讓修補版 dosbox-x 記下法術效果函式的呼叫。 |
| `cl6.py` | `f9ad17ed3ff5200b` | 2026-10-08T06:34 .. 2026-10-08T06:34 | 續一百一十一 cl5:第 1 章戰場,給悠妮 8 個法術與 MP,逐一施放,讓修補版 dosbox-x 記下法術效果函式的呼叫。 |
| `town6.py` | `6084868e7e1c91e1` | 2026-10-08T06:35 .. 2026-10-08T06:40 | cl6 城鎮:原始 enter-debugger(不檢查單位表指標)讀名冊、把一名成員設成陣亡(+5 /= 1),再恢復。 |
| `pick6.py` | `733f61056dc7fe88` | 2026-10-08T06:48 .. 2026-10-08T06:52 | cl6 出擊選人:讀 / 改旗標陣列(sortie_member_select 堆疊上,0x1f15e4,32 bytes)。 |
| `cast5.sh` | `4b0a034d825f4fc1` | 2026-10-08T05:58 .. 2026-10-08T06:05 | cast5.sh COL ROW:悠妮再行動 → 選她 → 環形選單 Left(魔法,讀回確認)→ 清單 (COL, ROW) → 目標選擇畫面截圖。(DOSBox-X 按鍵驅動) |
| `item5.sh` | `0cfbbf6e78ff8ce4` | 2026-10-08T06:11 .. 2026-10-08T06:15 | item5.sh COL ROW:悠妮再行動 → 環形選單 Right(道具,讀回確認)→ 子選單 Up(使用)→ 道具清單 (COL, ROW) → 目標畫面截圖。(DOSBox-X 按鍵驅動) |
| `cl7.py` | `0e521b16c206b95d` | 2026-10-08T07:47 .. 2026-10-08T08:03 | 續一百一十二 cl7:第 1 章戰場,升級學法術、MP 回復道具(type 0xb)、F1 地圖縮圖。 |
| `s10.py` | `6c291b018af57314` | 2026-10-12T04:41 .. 2026-10-12T04:53 | 續一百一十四 cl10:城鎮 -> 出擊選人,錄 sortie_required_member_check / roster_move_member_to_slot1(只對原版 FD2.EXE)。 |
| `cl_title.py` | `fbae3e7b7b388556` | 2026-10-12T05:01 .. 2026-10-13T04:45 | 續一百一十四:帶 DOS 環境變數(FD2_HARNESS_DOS_SET)開 instance 到標題畫面為止(只對原版 FD2.EXE)。 |
| `cp121.py` | `1abb827c08d1af07` | 2026-10-13T09:53 .. 2026-10-13T09:57 | 續一百二十一(第 3 項):copy_protection_password_check 的比對迴圈是否恆通過 —— DOSBox-X 實機(只對原版 FD2.EXE,只改模擬器記憶體)。 |
| `lc122.py` | `a687a0b1443127b9` | 2026-10-13T10:27 .. 2026-10-13T10:58 | 續一百二十二:lut_circle_ramp_at_unit(0x2189a)在畫面上的樣子 —— DOSBox-X 實機(只對原版 FD2.EXE,只改模擬器記憶體裡的單位資料)。 |
| `chk_wsl122.sh` | `041fca7ce5edacf9` | 2026-10-13T12:15 .. 2026-10-13T12:15 | 唯讀檢查:有沒有殘留的 DOSBox-X、今天哪些 harness 檔被改過。 |
| `lc123.py` | `daea5743212e8a6d` | 2026-10-13T14:57 .. 2026-10-13T15:22 | 續一百二十三:ai_item_action(0x15055)在圓形換色之後的流程 —— DOSBox-X 實機(只對原版 FD2.EXE,只改模擬器記憶體裡的單位資料)。 |
| `lc124.py` | `a466429e8bc5b4d1` | 2026-10-14T03:39 .. 2026-10-14T03:54 | 續一百二十四:(1) 玩家「休息」的 rest_hp_recover;(2) item_effect_dispatch 的 0x14 / 0x18 分支內部 —— DOSBox-X 實機。 |
| `lc125.py` | `2333d8b0d19b4e3e` | 2026-10-14T12:47 .. 2026-10-14T12:57 | 續一百二十五:grant_reward_rows 種類 3 的台詞與 spell_damage_apply 的經驗值累加 —— DOSBox-X 實機。 |
| `mk_a1_125.py` | `aff61b54a25e66aa` | 2026-10-14T13:01 .. 2026-10-14T13:01 | 續一百二十五:round A 的錄製腳本在第一條台詞後當掉,沒有寫出 a1.json。把它印在 stdout 的每一站(Python dict 字面值)轉成 a1.json。 |
| `lc126.py` | `589afae2bcf110f6` | 2026-10-15T03:47 .. 2026-10-15T03:59 | 續一百二十六:章節索引 22 的戰後處理器 0x24754 裡三次 lut_circle_ramp_at_unit,以及每幀停留多久 —— DOSBox-X 實機。 |
| `lc126t.py` | `c3edf58461ee94e6` | 2026-10-15T04:11 .. 2026-10-16T05:50 | 續一百二十六:lut_circle_ramp_at_unit(0x2189a)每幀停留多久 —— DOSBox-X 實機,讀 BIOS tick(線性 0x46c)。 |
| `lc127.py` | `0d63088668042bf2` | 2026-10-15T05:58 .. 2026-10-15T05:58 | 續一百二十七:正式第 22 章戰場(章節位元組 22,完整隊伍存檔)的戰後處理器 0x24754 裡三次 lut_circle_ramp_at_unit —— DOSBox-X 實機。 |
| `go127.py` | `d6ec99f3cc9fe2e3` | 2026-10-15T05:54 .. 2026-10-15T05:54 | 續一百二十七:以 fd2_chapter_sweep 的完整隊伍存檔進章節位元組 22 的戰場(畫面第 23 章;sweep 編號 chapter_n = 23)。 |
| `pick127.py` | `8cb26013063e24b7` | 2026-10-15T05:51 .. 2026-10-15T05:52 | 續一百二十七:出戰選擇畫面,隊伍只有 12 名候選、目標 15 名時,在 0x2b0e3 cmp eax, ebp 把 EBP 改成已選人數。 |
| `holdkey.sh` | `1f30066b1ce7e3ac` | 2026-10-16T05:33 .. 2026-10-16T05:49 | 續一百二十九:cycles 2500 下按鍵會掉,改成 keydown -> 持續 HOLD 秒 -> keyup(只送給該 instance 的 DOSBox 視窗,harness 不改)。 |
| `find_h4.sh` | `1a16b665d8d2c6ee` | 2026-10-16T05:20 .. 2026-10-16T05:21 | 找出哪幾份 unique_cseip 軌跡含指令表第 0..9 格的 handler 入口(native = linear + 0x19c000) |
| `lc130.py` | `11b93e8b4eb146b0` | 2026-10-16T06:37 .. 2026-10-17T06:44 | 續一百三十:沒有斷點時光束炮相位迴圈畫出哪幾階 —— 呼叫紀錄只列 5 個 EIP,遊戲途中不下任何斷點 |
| `lc131.py` | `f11450c800638479` | 2026-10-17T05:40 .. 2026-10-17T06:44 | 續一百三十一:(1) 移動範圍的明暗是不是 draw_terrain_layer 的換色段 (2) 續一百二十三第二輪的擺法在沒有斷點時畫哪幾階。 |
| `live.py` | `af43b446a061a2bc` | (由其他腳本呼叫) | 續六十六:DOSBox-X 即時操作的小工具(包 fd2_dosbox_live_helper.py)。只對原版 FD2.EXE 使用。 |
