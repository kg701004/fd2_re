#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續一百零三:s103c 兩段原始軌跡依序去重(不平行,避免 WSL I/O 擁塞)。完成寫 s103c_all.done。
~/s103_dedup.sh ~/fd2-run-harness-s103c raw_s103c_0.TXT s103c0_spell27_enemy_phase
~/s103_dedup.sh ~/fd2-run-harness-s103c raw_s103c_1.TXT s103c1_enemy_tail_teleport
echo done > ~/fd2-run-harness-s103c/s103c_all.done
