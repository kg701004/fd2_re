package fdother

import "errors"

// NativeTerrainLUTIndex reads FD2.EXE's static 0x51a97 table used by 0x11eee
// when no explicit palette override is active. The 20 phases select FDOTHER
// #3 LUT entries 0..10 then 9..1; phase is the runtime 0x53c1f counter.
func NativeTerrainLUTIndex(phase int) (int, error) {
	const phases = 20
	if phase < 0 || phase >= phases {
		return 0, errors.New("fdother: invalid native terrain LUT phase")
	}
	return [phases]int{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1}[phase], nil
}
