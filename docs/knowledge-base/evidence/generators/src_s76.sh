#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十六:把引用到的 DOSBox-X 原始碼(執行中二進位的同一棵樹,GIT_COMMIT_HASH 6fb8c07)複製到 .wsl_build,供證據腳本重算。
set -euo pipefail
dst=/mnt/c/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/dosbox_src_6fb8c07
src="$HOME/fd2-dosbox-build/dosbox-x"
mkdir -p "$dst"
for f in src/cpu/cpu.cpp src/hardware/memory.cpp src/hardware/cmos.cpp src/debug/debug_gui.cpp \
         src/cpu/core_normal/prefix_none.h src/cpu/core_normal/prefix_66.h include/cpu.h include/build_timestamp.h; do
  cp "$src/$f" "$dst/"
done
# 二進位裡有這些訊息字串(證明讀的原始碼就是跑的那一版)
strings -a "$src/src/dosbox-x" | grep -E 'Triple Fault. Resetting|already in progress, triggering double|INT 15 block move reset|JMP Illegal descriptor type' > "$dst/binary_strings.txt"
md5sum "$src/src/dosbox-x" > "$dst/binary_md5.txt"
ls "$dst"
