package main

import (
	"errors"
	"fmt"
	"image"
	"image/color"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/indexedmap"
)

// nativeSpawnIntroJob owns sub_32999's twelve observable presentation passes.
// The following 0x1366A call remains the next independent compiled Beat.
type nativeSpawnIntroJob struct {
	schedule []fdother.NativeSpawnIntroStep
	work     []byte
	vga      []byte
	frames   [][]byte
	palette  color.Palette
	sound    []byte
	frame    int
	drawn    bool
	then     func()
}

func cloneStoryUnitPointers(source []battle.Unit) []*battle.Unit {
	values := append([]battle.Unit(nil), source...)
	pointers := make([]*battle.Unit, len(values))
	for i := range values {
		pointers[i] = &values[i]
	}
	return pointers
}

// prepareNativeStorySpawn executes the proven future-group placement against
// private clones. The caller commits the returned values only after every
// visual pass has preflighted successfully.
func (g *Game) prepareNativeStorySpawn(group int, rawGate byte) ([]battle.Unit, []battle.Unit, error) {
	if g.m == nil || g.m.W <= 0 || g.m.H <= 0 || len(g.storyRoster) == 0 ||
		len(g.storyCompositionEventBytes) != g.m.W*g.m.H || g.storySpawned == nil || g.storySpawned[group] {
		return nil, nil, fmt.Errorf("native story spawn group %d lacks unmaterialized FDFIELD state", group)
	}
	active := cloneStoryUnitPointers(g.storyActors)
	roster := cloneStoryUnitPointers(g.storyRoster)
	state := &battle.State{
		W: g.m.W, H: g.m.H, Roster: roster,
		NativeCompositionEventBytes: append([]byte(nil), g.storyCompositionEventBytes...),
	}
	if err := state.AppendNativeMapSelectorBatch(active); err != nil {
		return nil, nil, fmt.Errorf("native story spawn existing roster: %w", err)
	}
	if n, err := state.AppendGroupWithNativePlacement(group, rawGate); err != nil {
		return nil, nil, err
	} else if n <= 0 {
		return nil, nil, fmt.Errorf("native story spawn group %d appended no units", group)
	}
	resultActors := make([]battle.Unit, len(state.Units))
	for i, unit := range state.Units {
		resultActors[i] = *unit
	}
	resultRoster := make([]battle.Unit, len(state.Roster))
	for i, unit := range state.Roster {
		resultRoster[i] = *unit
	}
	return resultActors, resultRoster, nil
}

func (g *Game) startNativeSpawnIntro(group int, rawGate byte, then func()) error {
	if g.spawnIntroTransition != nil || g.indexedTransition != nil {
		return errors.New("native spawn-intro transition already active")
	}
	if !nativeSpawnIntroAssetsAvailable(g.nativeMapAssets) || len(g.sfxSpawnIntro) == 0 {
		return errors.New("native spawn-intro visual/audio assets unavailable")
	}
	oldCount := len(g.storyActors)
	candidateActors, candidateRoster, err := g.prepareNativeStorySpawn(group, rawGate)
	if err != nil {
		return err
	}
	oldInput, err := g.buildNativeIndexedTransitionInputForActors(g.storyActors)
	if err != nil {
		return fmt.Errorf("native spawn-intro baseline input: %w", err)
	}
	candidateInput, err := g.buildNativeIndexedTransitionInputForActors(candidateActors)
	if err != nil {
		return fmt.Errorf("native spawn-intro candidate input: %w", err)
	}

	work := make([]byte, indexedmap.NativeUnitPresentWorkSize)
	if err := indexedmap.ComposeNativeUnitPresentTerrainSnapshot(work, oldInput); err != nil {
		return fmt.Errorf("native spawn-intro baseline terrain: %w", err)
	}
	if err := indexedmap.RedrawNativeUnitPresentObjects(work, oldInput); err != nil {
		return fmt.Errorf("native spawn-intro baseline objects: %w", err)
	}
	snapshot, err := indexedmap.SeedNativeSpawnIntroSnapshot(work)
	if err != nil {
		return err
	}
	vga := make([]byte, indexedmap.NativeMapVGASize)
	schedule := fdother.NativeSpawnIntroSchedule()
	input := indexedmap.NativeSpawnIntroFrameInput{Frame: candidateInput, OldUnitCount: oldCount}
	frames := make([][]byte, 0, len(schedule))
	for _, step := range schedule {
		if err := indexedmap.ComposeNativeSpawnIntroPass(
			work, vga, snapshot, input,
			g.nativeMapAssets.SpawnIntro[step.LMIEntry], step,
		); err != nil {
			return fmt.Errorf("native spawn-intro preflight pass %d: %w", step.Pass, err)
		}
		frames = append(frames, append([]byte(nil), vga...))
	}
	if len(frames) != fdother.NativeSpawnIntroPassCount {
		return errors.New("native spawn-intro preflight did not produce twelve frames")
	}

	// Commit constructor state only after the full renderer transaction has
	// succeeded. Native mutates the unit array before pass 0, so the blocked
	// presentation owns this already-constructed roster until completion.
	g.storyActors = candidateActors
	g.storyRoster = candidateRoster
	g.storySpawned[group] = true
	job := &nativeSpawnIntroJob{
		schedule: schedule, work: work, vga: append([]byte(nil), frames[0]...),
		frames: frames, palette: append(color.Palette(nil), g.nativeMapAssets.Palette...),
		sound: append([]byte(nil), g.sfxSpawnIntro...), then: then,
	}
	g.spawnIntroTransition = job
	return nil
}

func (g *Game) stepNativeSpawnIntro() {
	j := g.spawnIntroTransition
	if j == nil || !j.drawn {
		return
	}
	if j.frame+1 < len(j.frames) {
		j.frame++
		copy(j.vga, j.frames[j.frame])
		j.drawn = false
		if j.schedule[j.frame].SoundResource == fdother.NativeSpawnIntroSoundResource {
			g.playRaw(j.sound)
		}
		return
	}
	then := j.then
	g.nativeMapWork = append(g.nativeMapWork[:0], j.work...)
	g.nativeMapVGA = append(g.nativeMapVGA[:0], j.vga...)
	g.spawnIntroTransition = nil
	if then != nil {
		then()
	}
}

func (g *Game) drawNativeSpawnIntro(screen *ebiten.Image) bool {
	j := g.spawnIntroTransition
	if j == nil || len(j.vga) != indexedmap.NativeMapVGASize || len(j.palette) != 256 {
		return false
	}
	img := image.NewPaletted(image.Rect(0, 0, 320, 200), j.palette)
	copy(img.Pix, j.vga)
	op := &ebiten.DrawImageOptions{}
	op.GeoM.Scale(2, 2)
	screen.DrawImage(ebiten.NewImageFromImage(img), op)
	j.drawn = true
	return true
}
