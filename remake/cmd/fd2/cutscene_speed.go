// cutscene_speed.go — 過場加速(重製目標 #4:「過場時間減少至幾乎無感」)。
//
// 做法刻意保守:只調整各計時器「每 tick 前進多少」,不改動 beatStart 等處設定
// frames/delay 的原始數值本身。那些數值是逐一對照反組譯位址的證據(doc50/doc46
// 註解逐案標明),繼續保留代表的是原版真實節奏,只是本檔讓 remake 用更快的步調
// 走完同一段插值/倒數——native_acting 與 stepOriginalActing 的逐 tick 精確重現
// (doc50 §1.2,tick=1..7 對應原版格線位移)刻意不動,那段每個 tick 值本身就是
// 行為的一部分,跳 tick 會漏放中間格。
package main

import (
	"os"
	"strconv"
)

// cutsceneSpeedUp 是所有過場/劇情計時器的加速倍率。預設值就是這份個人重製分支
// 要的「幾乎無感」;設環境變數 FD2_CUTSCENE_SPEED=1 可還原原版節奏,方便跟
// doc50/doc46 的證據數值做 A/B 對照除錯。
var cutsceneSpeedUp = loadCutsceneSpeedUp()

func loadCutsceneSpeedUp() int {
	if v := os.Getenv("FD2_CUTSCENE_SPEED"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 1 {
			return n
		}
	}
	return 5
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
