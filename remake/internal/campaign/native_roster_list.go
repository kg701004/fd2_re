package campaign

import (
	"errors"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

const NativeRosterVisible = 6

// NativeRosterRow is one caller-resolved party entry consumed by 0x2ea90.
// The native FDICON pointer and FDTXT name index are kept explicit so missing
// provenance fails closed instead of guessing from a remake roster key.
type NativeRosterRow struct {
	Sprite        fdicon.Sprite
	NameTextIndex int
}

// NativeTwoColumnWindow mirrors 0x2e6b8's stateful [0x5412f] viewport. The
// caller preserves start between moves. It changes by two only after the
// selection crosses the current six-entry window, so moving back within the
// window does not prematurely reset the scroll origin.
func NativeTwoColumnWindow(count, selected, start int) (nextStart, visible int) {
	if count <= 0 || selected < 0 || selected >= count || start < 0 || start%2 != 0 {
		return 0, 0
	}
	maxStart := count - NativeRosterVisible
	if maxStart < 0 {
		maxStart = 0
	}
	if maxStart%2 != 0 {
		maxStart++
	}
	if start > maxStart {
		start = maxStart
	}
	for selected < start && start >= 2 {
		start -= 2
	}
	for selected >= start+NativeRosterVisible && start < maxStart {
		start += 2
	}
	visible = count - start
	if visible > NativeRosterVisible {
		visible = NativeRosterVisible
	}
	return start, visible
}

// RenderNativeRosterRows reproduces 0x2ea90's two-column, six-entry draw.
func RenderNativeRosterRows(
	dst []byte,
	rows []NativeRosterRow,
	selected int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
) error {
	if len(dst) != NativeClassListStride*NativeClassListHeight {
		return errors.New("campaign: native roster requires a 320x200 indexed frame")
	}
	if len(rows) == 0 || len(rows) > NativeRosterVisible ||
		selected < 0 || selected >= len(rows) {
		return errors.New("campaign: invalid native roster rows or selection")
	}
	if strings == nil || font == nil {
		return errors.New("campaign: native roster text assets are unavailable")
	}
	staged := append([]byte(nil), dst...)
	for i, row := range rows {
		column, line := i%2, i/2
		if err := row.Sprite.BlitAt(
			staged, NativeClassListStride, 14+132*column, 117+26*line,
		); err != nil {
			return fmt.Errorf("campaign: native roster row %d sprite: %w", i, err)
		}
		foreground := byte(205)
		if i == selected {
			foreground = 201
		}
		if err := blitNativeClassListText(
			staged, strings, font,
			40+132*column, 121+26*line, row.NameTextIndex, foreground,
		); err != nil {
			return fmt.Errorf("campaign: native roster row %d name: %w", i, err)
		}
	}
	copy(dst, staged)
	return nil
}

// ComposeNativeRosterFrame applies FDOTHER#14 entry16 and then 0x2ea90.
func ComposeNativeRosterFrame(
	background []byte,
	panel fdother.LMI1Entry,
	rows []NativeRosterRow,
	selected int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
) ([]byte, error) {
	if len(background) != NativeClassListStride*NativeClassListHeight {
		return nil, errors.New("campaign: native roster background requires a 320x200 indexed frame")
	}
	if panel.Width != nativeClassPanelW || panel.Height != nativeClassPanelH {
		return nil, fmt.Errorf("campaign: native roster panel is %dx%d, want 310x86", panel.Width, panel.Height)
	}
	frame := append([]byte(nil), background...)
	if err := panel.BlitOpaqueAt(
		frame, NativeClassListStride, nativeClassPanelX, nativeClassPanelY, false,
	); err != nil {
		return nil, fmt.Errorf("campaign: native roster panel: %w", err)
	}
	if err := RenderNativeRosterRows(frame, rows, selected, strings, font); err != nil {
		return nil, err
	}
	return frame, nil
}
