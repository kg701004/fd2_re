package main

import (
	"errors"
	"fmt"
	"image"
	"image/color"
	"strings"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/indexedmap"
)

type nativeTurnStagingPhase uint8

const (
	nativeTurnStagingPan nativeTurnStagingPhase = iota
	nativeTurnStagingDelay
	nativeTurnStagingFlash
)

// nativeTurnStagingJob owns event63's two blocking 0x35822 calls. The raw DAC
// and indexed frame remain separate; roster snapshots are prepared privately
// before the first camera tick so a bad second call cannot leave group1 live.
type nativeTurnStagingJob struct {
	event    battle.NativeTurnEvent
	states   []*battle.State
	call     int
	phase    nativeTurnStagingPhase
	ticks    int
	vga      []byte
	dac      []byte
	baseline []byte
	palette  color.Palette
	drawn    bool
	indexed  bool
	then     func()
}

func validateNativeEvent63(event battle.NativeTurnEvent) error {
	s := event.Staging
	if event.EventID != 63 || event.RawCamp != 0 || !strings.EqualFold(event.Handler, "0x358c7") ||
		!strings.EqualFold(s.Helper, "0x35822") || !strings.EqualFold(s.PanHelper, "0x135dd") ||
		!strings.EqualFold(s.SpawnHelper, "0x10b4e") || s.DelayBeforeFlashMS != 300 ||
		!strings.EqualFold(s.PaletteHelper, "0x11df2") || s.PaletteStart != 0 || s.PaletteEnd != 255 ||
		s.FlashDelta != 255 || s.FlashHoldMS != 200 || s.RestoreDelta != 0 ||
		!strings.EqualFold(s.RedrawHelper, "0x11cac") || s.RawPlacementGate != 0 || len(s.Calls) != 2 {
		return errors.New("event63 editable staging signature differs from recovered handler")
	}
	want := []battle.NativeTurnStagingCall{
		{Group: 1, X: 3, Y: 27, Source: "0x358d7"},
		{Group: 2, X: 15, Y: 27, Source: "0x358e5"},
	}
	for i, call := range s.Calls {
		if call.Group != want[i].Group || call.X != want[i].X || call.Y != want[i].Y ||
			!strings.EqualFold(call.Source, want[i].Source) {
			return fmt.Errorf("event63 staging call %d differs from recovered handler", i)
		}
	}
	return nil
}

func cloneNativeTurnStagingState(source *battle.State) (*battle.State, error) {
	if source == nil || source.W <= 0 || source.H <= 0 ||
		source.NativeMapSelectorCache == nil || source.NativeMapSelectorError != nil {
		return nil, errors.New("event63 lacks a complete runtime roster/selector state")
	}
	candidate := *source
	candidate.Units = cloneBattleUnitPointers(source.Units)
	candidate.Roster = cloneBattleUnitPointers(source.Roster)
	candidate.NativeMapSelectorCache = source.NativeMapSelectorCache.Clone()
	candidate.NativeCompositionEventBytes = append([]byte(nil), source.NativeCompositionEventBytes...)
	return &candidate, nil
}

func (g *Game) preflightNativeEvent63(event battle.NativeTurnEvent) ([]*battle.State, []byte, bool, error) {
	if err := validateNativeEvent63(event); err != nil {
		return nil, nil, false, err
	}
	if g.st == nil || g.m == nil || g.tileset == nil || len(g.tiles) == 0 ||
		g.m.TileW <= 0 || g.m.TileH <= 0 || g.st.W != g.m.W || g.st.H != g.m.H {
		return nil, nil, false, errors.New("event63 map/state assets unavailable")
	}
	base, err := cloneNativeTurnStagingState(g.st)
	if err != nil {
		return nil, nil, false, err
	}
	var baselineFrame []byte
	indexed := false
	if nativeMapAssetsAvailable(g.nativeMapAssets) {
		claimsIndexedState := g.st.HasNativeMapViewState && g.st.HasNativeMapRangeModeState &&
			g.st.HasNativeMapHUDState && g.st.HasNativeMapCycleState
		probe := *g
		probe.st = base
		probe.nativeMapWork, probe.nativeMapVGA = nil, nil
		if err := probe.composeNativeMapFrame(); err == nil {
			baselineFrame = append([]byte(nil), probe.nativeMapVGA...)
			indexed = true
		} else if claimsIndexedState {
			return nil, nil, false, fmt.Errorf("event63 claimed indexed baseline frame: %w", err)
		}
	}

	candidate, err := cloneNativeTurnStagingState(g.st)
	if err != nil {
		return nil, nil, false, err
	}
	states := make([]*battle.State, 0, len(event.Staging.Calls))
	for i, call := range event.Staging.Calls {
		if call.X+13 > g.m.W || call.Y+8 > g.m.H {
			return nil, nil, false, fmt.Errorf("event63 staging call %d camera exceeds native viewport", i)
		}
		if n, err := candidate.AppendGroupWithNativePlacement(
			call.Group, byte(event.Staging.RawPlacementGate),
		); err != nil || n <= 0 {
			return nil, nil, false, fmt.Errorf("event63 staging call %d group %d: append=%d err=%v", i, call.Group, n, err)
		}
		snapshot, err := cloneNativeTurnStagingState(candidate)
		if err != nil {
			return nil, nil, false, err
		}
		if indexed {
			probeState, err := cloneNativeTurnStagingState(snapshot)
			if err != nil {
				return nil, nil, false, err
			}
			frameProbe := *g
			frameProbe.st = probeState
			frameProbe.camX = float64(call.X * g.m.TileW)
			frameProbe.camY = float64(call.Y * g.m.TileH)
			frameProbe.nativeMapWork, frameProbe.nativeMapVGA = nil, nil
			if err := frameProbe.composeNativeMapFrame(); err != nil {
				return nil, nil, false, fmt.Errorf("event63 staging call %d frame: %w", i, err)
			}
		}
		states = append(states, snapshot)
	}
	return states, baselineFrame, indexed, nil
}

// startNativeRawCamp0TurnEvents is the sub_1A813(0) owner. Scenarios opt in by
// supplying native_turn_events; once opted in, every matching live row must
// have exactly one typed consumer or the enemy AI remains stopped.
func (g *Game) startNativeRawCamp0TurnEvents() (bool, error) {
	if g.sc == nil || len(g.sc.NativeTurnEvents) == 0 {
		return false, nil
	}
	events, err := g.sc.NativeTurnEventsAt(g.st, 0)
	if err != nil {
		return false, err
	}
	if len(events) == 0 {
		return false, nil
	}
	if len(events) != 1 {
		return false, fmt.Errorf("raw camp0 has %d simultaneous handlers; adapter only proves event63", len(events))
	}
	states, frame, indexed, err := g.preflightNativeEvent63(events[0])
	if err != nil {
		return false, err
	}
	job := &nativeTurnStagingJob{
		event: events[0], states: states,
		vga:     append([]byte(nil), frame...),
		indexed: indexed, then: g.beginEnemyPhase,
	}
	if indexed {
		a := g.nativeMapAssets
		job.dac = append([]byte(nil), a.PaletteDAC...)
		job.baseline = append([]byte(nil), a.PaletteDAC...)
		palette, err := fdother.VGAPaletteFromDAC(job.dac)
		if err != nil {
			return false, err
		}
		job.palette = palette
	}
	g.nativeFullDACWhite = false
	g.nativeTurnStaging = job
	g.sel, g.reach, g.moved = nil, nil, false
	g.startNativeTurnStagingCall()
	return true, nil
}

func (g *Game) startNativeTurnStagingCall() {
	job := g.nativeTurnStaging
	if job == nil || job.call < 0 || job.call >= len(job.event.Staging.Calls) {
		g.failNativeTurnStaging("call index unavailable")
		return
	}
	call := job.event.Staging.Calls[job.call]
	job.phase, job.drawn = nativeTurnStagingPan, false
	g.camPan = &camPanJob{
		fromX: g.camX, fromY: g.camY,
		toX: float64(call.X * g.m.TileW), toY: float64(call.Y * g.m.TileH),
		tileStep: true,
		then:     g.commitNativeTurnStagingSpawn,
	}
}

func (g *Game) commitNativeTurnStagingSpawn() {
	job := g.nativeTurnStaging
	if job == nil || job.call < 0 || job.call >= len(job.states) {
		g.failNativeTurnStaging("preflighted spawn unavailable")
		return
	}
	// Capture the final pan redraw before publishing the new group. The helper
	// does not call 0x11CAC between 0x10B4E and the white flash.
	if job.indexed {
		if err := g.composeNativeMapFrame(); err != nil {
			g.failNativeTurnStaging("final pan frame: " + err.Error())
			return
		}
		copy(job.vga, g.nativeMapVGA)
	}
	*g.st = *job.states[job.call]
	job.phase = nativeTurnStagingDelay
	job.ticks = nativeDelayTicks(job.event.Staging.DelayBeforeFlashMS)
}

func (g *Game) stepNativeTurnStaging() {
	job := g.nativeTurnStaging
	if job == nil {
		return
	}
	switch job.phase {
	case nativeTurnStagingPan:
		return
	case nativeTurnStagingDelay:
		if job.ticks > 0 {
			job.ticks--
			return
		}
		if job.indexed {
			if err := fdother.ApplyVGAPaletteDelta(
				job.dac, job.baseline, job.event.Staging.PaletteStart,
				job.event.Staging.PaletteEnd, job.event.Staging.FlashDelta,
			); err != nil {
				g.failNativeTurnStaging("white flash: " + err.Error())
				return
			}
			palette, err := fdother.VGAPaletteFromDAC(job.dac)
			if err != nil {
				g.failNativeTurnStaging("white palette: " + err.Error())
				return
			}
			job.palette = palette
		} else {
			g.nativeFullDACWhite = true
		}
		job.phase, job.ticks, job.drawn = nativeTurnStagingFlash, nativeDelayTicks(job.event.Staging.FlashHoldMS), false
	case nativeTurnStagingFlash:
		if !job.drawn {
			return
		}
		if job.ticks > 0 {
			job.ticks--
			return
		}
		if job.indexed {
			if err := fdother.ApplyVGAPaletteDelta(
				job.dac, job.baseline, job.event.Staging.PaletteStart,
				job.event.Staging.PaletteEnd, job.event.Staging.RestoreDelta,
			); err != nil {
				g.failNativeTurnStaging("palette restore: " + err.Error())
				return
			}
			palette, err := fdother.VGAPaletteFromDAC(job.dac)
			if err != nil {
				g.failNativeTurnStaging("restored palette: " + err.Error())
				return
			}
			job.palette = palette
			if err := g.composeNativeMapFrame(); err != nil {
				g.failNativeTurnStaging("redraw: " + err.Error())
				return
			}
			copy(job.vga, g.nativeMapVGA)
		} else {
			g.nativeFullDACWhite = false
		}
		job.call++
		if job.call < len(job.event.Staging.Calls) {
			g.startNativeTurnStagingCall()
			return
		}
		then := job.then
		g.nativeFullDACWhite = false
		g.nativeTurnStaging = nil
		if then != nil {
			then()
		}
	}
}

func (g *Game) failNativeTurnStaging(message string) {
	g.loadErr = "native event63 staging: " + message
	g.nativeFullDACWhite = false
	g.camPan = nil
	g.nativeTurnStaging = nil
}

func (g *Game) drawNativeTurnStaging(screen *ebiten.Image) bool {
	job := g.nativeTurnStaging
	if job == nil || len(job.vga) != indexedmap.NativeMapVGASize || len(job.palette) != 256 {
		return false
	}
	if job.phase == nativeTurnStagingPan {
		if err := g.composeNativeMapFrame(); err != nil {
			g.failNativeTurnStaging("pan redraw: " + err.Error())
			return false
		}
		copy(job.vga, g.nativeMapVGA)
	}
	img := image.NewPaletted(image.Rect(0, 0, 320, 200), job.palette)
	copy(img.Pix, job.vga)
	op := &ebiten.DrawImageOptions{}
	op.GeoM.Scale(2, 2)
	screen.DrawImage(ebiten.NewImageFromImage(img), op)
	job.drawn = true
	return true
}
