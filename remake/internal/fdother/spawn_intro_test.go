package fdother

import (
	"os"
	"testing"
)

func TestNativeSpawnIntroSchedulePreservesAllTwelvePasses(t *testing.T) {
	steps := NativeSpawnIntroSchedule()
	if err := ValidateNativeSpawnIntroSchedule(steps); err != nil {
		t.Fatal(err)
	}
	if len(steps) != 12 || steps[0].LMIEntry != 0 || steps[11].LMIEntry != 11 {
		t.Fatalf("spawn-intro steps=%#v", steps)
	}
	if steps[1].SoundResource != 95 || steps[0].SoundResource != -1 || steps[2].SoundResource != -1 {
		t.Fatalf("pass1 raw resource boundary=%#v", steps)
	}
	if got := steps[6]; got.SnapshotMode != NativeSpawnIntroSplitUnits || got.RedrawTerrain || got.NewUnitPixelLift != -8 {
		t.Fatalf("pass6=%#v", got)
	}
	if got := steps[7]; got.SnapshotMode != NativeSpawnIntroSplitUnits || !got.RedrawTerrain || got.NewUnitPixelLift != -5 {
		t.Fatalf("pass7=%#v", got)
	}
	if got := steps[8]; got.SnapshotMode != NativeSpawnIntroFullFrame || !got.RedrawTerrain || got.NewUnitPixelLift != 0 {
		t.Fatalf("pass8=%#v", got)
	}
	for _, pass := range []int{0, 1, 2, 3, 4, 5, 9, 10, 11} {
		if steps[pass].SnapshotMode != NativeSpawnIntroKeepSnapshot || steps[pass].DelayTicks != 1 {
			t.Fatalf("ordinary pass %d=%#v", pass, steps[pass])
		}
	}
}

func TestValidateNativeSpawnIntroScheduleRejectsFormerTwelveTickShortcut(t *testing.T) {
	steps := NativeSpawnIntroSchedule()
	steps[6].SnapshotMode = NativeSpawnIntroKeepSnapshot
	if err := ValidateNativeSpawnIntroSchedule(steps); err == nil {
		t.Fatal("schedule without pass6 snapshot rebuild was accepted")
	}
	if err := ValidateNativeSpawnIntroSchedule(steps[:11]); err == nil {
		t.Fatal("short spawn-intro schedule was accepted")
	}
}

func TestFDOTHER009NativeSpawnIntroFrames(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(datPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	entries, err := DecodeNativeSpawnIntroFrames(datPath)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != NativeSpawnIntroPassCount || entries[0].Width != 42 || entries[11].Width != 66 {
		t.Fatalf("FDOTHER#9 spawn-intro entries=%#v", entries)
	}
}

func TestNativeSpawnIntroVisibilityAndLMIOriginMatch32999(t *testing.T) {
	if !NativeSpawnIntroVisible(9, 20, 10, 20, 12, 7) ||
		NativeSpawnIntroVisible(9, 19, 10, 20, 12, 7) ||
		!NativeSpawnIntroVisible(22, 28, 10, 20, 12, 7) ||
		NativeSpawnIntroVisible(23, 28, 10, 20, 12, 7) {
		t.Fatal("0x32999 camera bounds differ")
	}
	want := 0x8088 + 24*(14-10-1) + 24*0x1c8*(23-20) - 0xab0
	if got := NativeSpawnIntroLMIOrigin(14, 23, 10, 20); got != want {
		t.Fatalf("origin=%#x, want %#x", got, want)
	}
	work := make([]byte, 0x25680)
	for i := range work {
		work[i] = 0xee
	}
	entry := LMI1Entry{Width: 2, Height: 1, Pixels: []byte{0, 0x44}}
	if err := BlitNativeSpawnIntroLMI(entry, work, 14, 23, 10, 20); err != nil {
		t.Fatal(err)
	}
	origin := NativeSpawnIntroLMIOrigin(14, 23, 10, 20)
	if work[origin] != 0xee || work[origin+1] != 0x44 {
		t.Fatalf("transparent LMI=%#x/%#x", work[origin], work[origin+1])
	}
}
