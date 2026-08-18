// cutscene_speed.go — 過場加速開關。
//
// 2026-08-13:使用者要求先把過場/劇情步調改回原版真實節奏,再跟原版 DOSBox
// 做操作比對(加速過的話,兩邊天生就對不起來,比對沒有意義)。預設值改回 1
// (不加速);先前「幾乎無感」的加速需求(重製目標 #4)仍然保留在 FD2_CUTSCENE_SPEED
// 環境變數這條路徑,要重新啟用就設那個變數,不必再改這個預設值。
//
// 做法刻意保守:只調整各計時器「每 tick 前進多少」,不改動 beatStart 等處設定
// frames/delay 的原始數值本身。那些數值是逐一對照反組譯位址的證據(doc50/doc46
// 註解逐案標明),繼續保留代表的是原版真實節奏——native_acting 與
// stepOriginalActing 的逐 tick 精確重現(doc50 §1.2,tick=1..7 對應原版格線
// 位移)刻意不動,那段每個 tick 值本身就是行為的一部分,跳 tick 會漏放中間格。
package main

import (
	"os"
	"strconv"
)

// cutsceneSpeedUp 是所有過場/劇情計時器的加速倍率。預設 1=原版真實節奏;設
// 環境變數 FD2_CUTSCENE_SPEED=5 可還原先前「幾乎無感」的加速版本,方便 A/B。
var cutsceneSpeedUp = loadCutsceneSpeedUp()

func loadCutsceneSpeedUp() int {
	if v := os.Getenv("FD2_CUTSCENE_SPEED"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 1 {
			return n
		}
	}
	return 1
}

// titleSpeedUp paces the OPENING TITLE animation (flame-logo AFM cutscene /
// FDOTHER portrait-scroll fallback, title.go's "cutscene"/"scroll" phases)
// independently of cutsceneSpeedUp -- the user explicitly wants this specific
// sequence back at the original's own pace (it was inheriting the general
// in-game dialogue/story speedup, which was never meant to apply here), while
// keeping that unrelated in-game speedup untouched everywhere else. FD2_TITLE_SPEED
// overrides for A/B debugging, same convention as FD2_CUTSCENE_SPEED.
var titleSpeedUp = loadTitleSpeedUp()

func loadTitleSpeedUp() int {
	if v := os.Getenv("FD2_TITLE_SPEED"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 1 {
			return n
		}
	}
	return 1
}

// decTimer 依 cutsceneSpeedUp 遞減一個倒數計時器,下限 0,讓呼叫端既有的
// `== 0`/`<= 0` 判斷不必跟著改也能精確命中。
func decTimer(n int) int {
	n -= cutsceneSpeedUp
	if n < 0 {
		return 0
	}
	return n
}
