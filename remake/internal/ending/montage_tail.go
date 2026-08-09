package ending

import (
	"encoding/json"
	"fmt"
	"os"
)

// MontageTail is the raw, editable schedule after the party montage.  It
// deliberately exposes byte offsets and native call shapes instead of
// assigning names such as unit state, animation, or ending outcome.
type MontageTail struct {
	SchemaVersion int                 `json:"schema_version"`
	NativeHandler string              `json:"native_handler"`
	Status        string              `json:"status"`
	Source        string              `json:"source"`
	Resources     []MontageTailAsset  `json:"resources"`
	RawTables     MontageTailRawTable `json:"raw_tables"`
	Loop          MontageTailLoop     `json:"loop"`
	Gate          MontageTailGate     `json:"gate"`
}

type MontageTailAsset struct {
	Archive string `json:"archive"`
	Index   int    `json:"index"`
	Source  string `json:"source"`
	Role    string `json:"role"`
}

type MontageTailRawTable struct {
	Global540FF []int `json:"global_540ff"`
	UnitPlus7   []int `json:"unit_plus_7"`
	UnitPlus14  []int `json:"unit_plus_14"`
}

type MontageTailLoop struct {
	Count                int    `json:"count"`
	UnitBaseGlobal       string `json:"unit_base_global"`
	UnitStride           int    `json:"unit_stride"`
	UnitByte6First       int    `json:"unit_byte_6_first"`
	UnitByte6Later       int    `json:"unit_byte_6_later"`
	UnitByte7Source      string `json:"unit_byte_7_source"`
	UnitByte56Source     string `json:"unit_byte_0x56_source"`
	UnitByte57Source     string `json:"unit_byte_0x57_source"`
	Global540FFSource    string `json:"global_540ff_source"`
	UnitPresentCall      string `json:"unit_present_call"`
	PaletteCall          string `json:"palette_call"`
	FrameCall            string `json:"frame_call"`
	WaitBeforeFrameTicks int    `json:"wait_before_frame_ticks"`
	WaitAfterFrameTicks  int    `json:"wait_after_frame_ticks"`
	WaitHelper           string `json:"wait_helper"`
	PresentHelper        string `json:"present_helper"`
	RestoreHelper        string `json:"restore_helper"`
}

type MontageTailGate struct {
	Source string `json:"source"`
	Reason string `json:"reason"`
}

// MontageTailEntry keeps the three raw table bytes together for one native
// loop index.  It is a plan only: no renderer, unit mutation, or campaign
// transition is performed by this package.
type MontageTailEntry struct {
	Index       int
	Global540FF byte
	UnitPlus7   byte
	UnitPlus14  byte
	UnitByte6   byte
}

func LoadMontageTail(path string) (*MontageTail, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var tail MontageTail
	if err := json.Unmarshal(raw, &tail); err != nil {
		return nil, err
	}
	if tail.SchemaVersion != 1 || tail.NativeHandler != "0x2c194" || tail.Status != "mapped_post_montage_tail_fail_closed" ||
		tail.Source != "0x2c194..0x2c39a" || len(tail.Resources) != 4 || tail.Loop.Count != 20 ||
		tail.Loop.UnitBaseGlobal != "0x53a45" || tail.Loop.UnitStride != 0x50 ||
		tail.Loop.UnitByte6First != 0 || tail.Loop.UnitByte6Later != 2 ||
		tail.Loop.UnitByte7Source != "unit_plus_7" ||
		tail.Loop.UnitByte56Source != "unit_plus_14_lt_0x4c ? 2 : 0" ||
		tail.Loop.UnitByte57Source != "unit_plus_14" ||
		tail.Loop.Global540FFSource != "global_540ff" ||
		tail.Loop.UnitPresentCall != "0x28a6c(0,1)" ||
		tail.Loop.PaletteCall != "0x11d40(0,255,0)" ||
		tail.Loop.FrameCall != "0x2935b(resource_57,loop_index,staging,0x140,-1)" ||
		tail.Loop.WaitBeforeFrameTicks != 20 || tail.Loop.WaitAfterFrameTicks != 78 ||
		tail.Loop.WaitHelper != "0x17aa9" || tail.Loop.PresentHelper != "0x1f882" ||
		tail.Loop.RestoreHelper != "0x375c0" || tail.Gate.Source == "" || tail.Gate.Reason == "" {
		return nil, fmt.Errorf("ending montage tail %q has incomplete native contract", path)
	}
	for i, resource := range tail.Resources {
		wantIndex := []int{60, 58, 57, 59}[i]
		if resource.Archive != "FDOTHER.DAT" || resource.Index != wantIndex || resource.Source == "" || resource.Role == "" {
			return nil, fmt.Errorf("ending montage tail %q resource %d is incomplete", path, i)
		}
	}
	for name, table := range map[string][]int{
		"global_540ff": tail.RawTables.Global540FF,
		"unit_plus_7":  tail.RawTables.UnitPlus7,
		"unit_plus_14": tail.RawTables.UnitPlus14,
	} {
		if len(table) != tail.Loop.Count {
			return nil, fmt.Errorf("ending montage tail %q table %s has %d entries", path, name, len(table))
		}
		for i, value := range table {
			if value < 0 || value > 0xff {
				return nil, fmt.Errorf("ending montage tail %q table %s entry %d is not a byte", path, name, i)
			}
		}
	}
	return &tail, nil
}

// Plan returns the raw 20-entry schedule while retaining the native side
// branch as byte 6.  It does not write a unit or present a frame.
func (t MontageTail) Plan() ([]MontageTailEntry, error) {
	if t.Loop.Count <= 0 || len(t.RawTables.Global540FF) != t.Loop.Count || len(t.RawTables.UnitPlus7) != t.Loop.Count || len(t.RawTables.UnitPlus14) != t.Loop.Count {
		return nil, fmt.Errorf("ending montage tail has incomplete raw tables")
	}
	entries := make([]MontageTailEntry, t.Loop.Count)
	for i := range entries {
		if t.RawTables.Global540FF[i] < 0 || t.RawTables.Global540FF[i] > 0xff || t.RawTables.UnitPlus7[i] < 0 || t.RawTables.UnitPlus7[i] > 0xff || t.RawTables.UnitPlus14[i] < 0 || t.RawTables.UnitPlus14[i] > 0xff {
			return nil, fmt.Errorf("ending montage tail raw table entry %d is not a byte", i)
		}
		unitByte6 := t.Loop.UnitByte6Later
		if i == 0 {
			unitByte6 = t.Loop.UnitByte6First
		}
		if unitByte6 < 0 || unitByte6 > 0xff {
			return nil, fmt.Errorf("ending montage tail unit byte 6 is not a byte")
		}
		entries[i] = MontageTailEntry{Index: i, Global540FF: byte(t.RawTables.Global540FF[i]), UnitPlus7: byte(t.RawTables.UnitPlus7[i]), UnitPlus14: byte(t.RawTables.UnitPlus14[i]), UnitByte6: byte(unitByte6)}
	}
	return entries, nil
}
