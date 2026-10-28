# 驅動腳本存檔(續一百五十九)

續一百五十九的兩項:第 5 項第 5 次實機(instance `lc159a`,使用者 2026-10-28「第五項 核准授權你重新實機重跑驗證」)(DOSBox-X)與第 6 項的目錄快照
(使用者 2026-10-28「第六項 若需要新建或優化工具 請自行解決 並 完整解決問題」)。實機只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、
WSL `-d Ubuntu`;第 6 項只讀磁碟上的遊戲目錄,不改任何檔案。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `ret159.py` | 第 5 項:`prompt`(找空格 → 開指令環 → END,停在「結束這回合?」並截圖)/ `kill`(索爾 +5 的 bit0 設 1,讀回比對)/ `go`(Return(YES)+ 清對話迴圈 N 次、逐次記主機時間)。`entries` / `launch` / `post` / `pull` 沿用 [`drivers_s158/ret157b.py`](../drivers_s158/ret157b.py) | `.wsl_build/lc159_live/lc159a/prompt/` |
| `pred159_item5.txt` | 第 5 項量之前寫下的預測 P0 .. P5(P1 .. P5 照 `drivers_s158/pred157_item5.txt` 原文);這次沒有進到量測,全部 NOT TESTED | — |
| `snap159.py` | 第 6 項:`GAME/FD2`、`FD2_USB`、`FD2_APK` 的檔名、大小、修改時間、md5 快照,複製 `FD2_APK` 的 `PASS.DAT`、`PLAY.BAT`、`SETUP.BAT` | `.wsl_build/s159_copyprot/dirs.json` 與三個複本 |

當時的步驟:`ret157b.py entries` → `ret157b.py launch lc159a` → `lc157.py hud lc159a`(33 次清對話 Return 後看到戰場 HUD)→ `ret159.py prompt lc159a`
(Up 判為空格)。之後沒有「結束這回合?」框,索爾移到上一格並行動結束(`ev_s159` (D));依規則停止,`kill` 與 `go` 沒有跑,instance 保持執行、沒有再送鍵。

`.wsl_build/s159_copyprot/scan_c_drive.txt` 是 PowerShell 對整個 C 槽的掃描(大小 509158,或檔名 `PASS.DAT`、`FD2*.EXE`、`*.apk` 等封存檔),
命令在 doc98 續一百五十九;WSL 的 ext4 磁碟映像不在掃描範圍內(harness 目錄裡的 FD2.EXE 都是 `~/fd2-run/FD2.EXE` 的複本)。

已知限制:

- `prompt` 步驟沒有在每個鍵之後截圖,只能從前後兩張判斷結果,不能判斷 Return / Down / Return 各自做了什麼。
- 修改時間是 Windows 上的本地時間(UTC+8),複製檔案時可能改變;快照記的是 2026-10-28 當時的值。
