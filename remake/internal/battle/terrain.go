// terrain.go — FDSHAP control byte+1 的原版地形 AP/DP 修正。0x1acf3 以該 byte
// 索引 0x51a12 (AP) 和 0x51a2a (DP)；NativeTerrainMoveCodes 是匯出 map 的逐格
// 原始索引，不以歸一化的 MoveCost 猜測地形。
package battle

// NativeTerrainAPDPPct is the verified six-entry static table.  The bool is
// false for an unrecognised control value so callers can fail closed.
func NativeTerrainAPDPPct(moveCode byte) (apPct, dpPct int, ok bool) {
	switch moveCode {
	case 0:
		return 5, 0, true
	case 1, 5:
		return 0, 0, true
	case 2, 3:
		return -5, 10, true
	case 4:
		return -5, -5, true
	default:
		return 0, 0, false
	}
}

// TerrainAPDPPct returns a cell's combat modifiers.  Complete native map
// exports take precedence.  Old/incomplete maps retain the historical Cost
// fallback so loading them remains compatible; that fallback is deliberately
// not evidence of original terrain semantics.
func (s *State) TerrainAPDPPct(x, y int) (apPct, dpPct int) {
	if s != nil && x >= 0 && x < s.W && y >= 0 && y < s.H && len(s.NativeTerrainMoveCodes) == s.W*s.H {
		if apPct, dpPct, ok := NativeTerrainAPDPPct(s.NativeTerrainMoveCodes[y*s.W+x]); ok {
			return apPct, dpPct
		}
	}
	switch s.MoveCost(x, y) {
	case 2: // 沼澤(export_engine_assets.py:move_code 4 -> cost 2)
		return -5, -5
	case 1: // 正常(含目前無法分辨的森林,見檔頭與本函式註解;s.Cost==nil/越界也落此分支)
		return 5, -5
	default: // 不可通行(cost>=BLOCKED_COST)等其他值:不套地形修正
		return 0, 0
	}
}
