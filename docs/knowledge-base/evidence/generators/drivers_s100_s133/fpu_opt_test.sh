# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 從 dosbox_harness.sh 抽出 FD2_HARNESS_FPU 區塊,逐值測:合法值 -> 參數、非法值 -> die、未設 -> 空
src=/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/dosbox_harness.sh
blk=$(sed -n '/local fpu_arg=()/,/^    fi$/p' "$src")
[ -n "$blk" ] || { echo "FAIL: block not found"; exit 1; }
die() { echo "DIE: $*"; return 1; }
run() { ( name=t; eval "f() { $blk
  echo \"ARGS=[\${fpu_arg[*]@Q}]\"; }"; f ) 2>&1 | tr '\n' ' '; echo; }
unset FD2_HARNESS_FPU; echo "unset: $(run)"
for v in false 387 'false x' 'true;id' FALSE ''; do FD2_HARNESS_FPU="$v"; export FD2_HARNESS_FPU; echo "[$v]: $(run)"; done
