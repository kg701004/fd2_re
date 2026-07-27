package ending

import (
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

const (
	NativeMontagePortraitOffset       = 0x0c88
	NativeMontagePortraitNormalFrame  = 0
	NativeMontagePortraitMouthFrame   = 3
	NativeMontagePortraitSplitTick    = 0xdc
	NativeMontagePortraitRegularTicks = 0xdc
	NativeMontagePortraitFinalTicks   = 0x1b8
)

// MontagePortraitState is the exact local byte countdown at
// 0x2c7ed..0x2c9a9. RandomByte is caller-supplied because native obtains it
// from 0x4e893; this adapter does not invent or share a replacement RNG.
type MontagePortraitState struct {
	Countdown int
}

// Step returns the DATO frame selected for one native portrait-loop
// iteration. A zero countdown is replaced with (random&31)+40 without an
// immediate decrement; nonzero countdowns decrement first. Values 1 and 0
// select pointer-table offset 12, i.e. DATO frame 3.
func (s *MontagePortraitState) Step(randomByte byte) (int, error) {
	if s == nil || s.Countdown < 0 || s.Countdown > 0x47 {
		return 0, fmt.Errorf("ending: invalid montage portrait countdown")
	}
	if s.Countdown == 0 {
		s.Countdown = int(randomByte&0x1f) + 0x28
	} else {
		s.Countdown--
	}
	if s.Countdown < 2 {
		return NativeMontagePortraitMouthFrame, nil
	}
	return NativeMontagePortraitNormalFrame, nil
}

// NativeMontagePortraitIterations preserves the caller's asymmetric duration:
// native loop index zero receives 440 ticks; every other party entry receives
// 220. Since PlanPartyCycle swaps indexes zero and one, this is intentionally
// keyed by LoopIndex rather than UnitSlot.
func NativeMontagePortraitIterations(loopIndex int) (int, error) {
	if loopIndex < 0 {
		return 0, fmt.Errorf("ending: invalid montage party loop index")
	}
	if loopIndex == 0 {
		return NativeMontagePortraitFinalTicks, nil
	}
	return NativeMontagePortraitRegularTicks, nil
}

// ComposeMontagePortraitFrame executes the recovered static portion of one
// 0x2c7ed portrait tick: restore the FDOTHER#5 dialogue-grid snapshot, paste
// the selected DATO frame at 0x0c88, and render the five proven FDTXT fields.
// It returns a fresh 320x200 indexed frame so malformed inputs never partially
// mutate the caller's restore buffer.
func ComposeMontagePortraitFrame(
	m Montage,
	restore []byte,
	unit []byte,
	edi, datoFrame int,
	portraitFrames []dato.Frame,
	current, permanent *fdtxt.Strings,
	font *fdtxt.Font,
) ([]byte, error) {
	cycle := m.PartyCycle.PortraitText.Cycle
	if len(restore) != Bytes || datoFrame < 0 || datoFrame >= len(portraitFrames) ||
		current == nil || permanent == nil || font == nil {
		return nil, fmt.Errorf("ending: invalid montage portrait assets")
	}
	if cycle.Destination != NativeMontagePortraitOffset {
		return nil, fmt.Errorf("ending: unsupported montage portrait destination")
	}
	plan, err := m.PlanPortraitText(unit, edi)
	if err != nil {
		return nil, err
	}
	frame := append([]byte(nil), restore...)
	if err := RenderDATOFrameAt(
		frame, portraitFrames[datoFrame], Width, cycle.Destination,
	); err != nil {
		return nil, err
	}
	fields := []struct {
		placement TextPlacement
		lines     int
	}{
		{plan.NameLabel, 0},
		{plan.CharacterName, 0},
		{plan.ClassLabel, 0},
		{plan.ClassName, 0},
		{plan.Epilogue, 20},
	}
	for _, field := range fields {
		table := current
		if field.placement.Table == "permanent" {
			table = permanent
		} else if field.placement.Table != "current" {
			return nil, fmt.Errorf("ending: invalid montage text table")
		}
		words, err := table.Words(field.placement.Index)
		if err != nil {
			return nil, err
		}
		if err := renderMontageText(
			frame, font, words, field.placement.Destination, field.lines,
			m.PartyCycle.PortraitText.GlyphStyle,
		); err != nil {
			return nil, err
		}
	}
	return frame, nil
}

func renderMontageText(
	frame []byte,
	font *fdtxt.Font,
	words []uint16,
	origin, lineAdvanceRows int,
	style MontageGlyphStyle,
) error {
	if style != (MontageGlyphStyle{
		Stride: Width, Foreground: 0xcd, Shadow: 0x4c, Background: 0,
	}) {
		return fmt.Errorf("ending: unsupported montage glyph style")
	}
	base, line, column := origin, 0, 0
	for _, word := range words {
		if word == 0xfffe {
			if lineAdvanceRows <= 0 {
				return fmt.Errorf("ending: unexpected montage line break")
			}
			line++
			column = 0
			base = origin + line*lineAdvanceRows*style.Stride
			continue
		}
		if word >= fdtxt.ControlMin {
			return fmt.Errorf("ending: unsupported montage text control %#x", word)
		}
		offset := base + column*fdtxt.GlyphWidth
		if err := font.BlitNativeGlyph(
			frame, style.Stride, offset, int(word),
			fdtxt.NativeGlyphStyle{
				Foreground: byte(style.Foreground),
				Shadow:     byte(style.Shadow),
				Background: byte(style.Background),
			},
		); err != nil {
			return err
		}
		column++
	}
	return nil
}
