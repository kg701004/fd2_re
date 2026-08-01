package main

// TitleMenuAction is the observable result of a completed native-style title
// menu confirmation. Keeping this transition pure gives the UI trace a stable
// contract without pretending the JSON save format is FD2.SAV-compatible.
type TitleMenuAction uint8

const (
	TitleMenuNoAction TitleMenuAction = iota
	TitleMenuStart
	TitleMenuLoadSlots
	TitleMenuContinue
)

type TitleMenuEvent uint8

const (
	TitleMenuTick TitleMenuEvent = iota
	TitleMenuUp
	TitleMenuDown
	TitleMenuConfirm
)

// TitleMenuState models the three-entry main menu and its native confirmation
// flash. Selection wraps; confirmation resolves only after FlashTicks reaches
// zero, matching titleUpdate's visible confirmation delay.
type TitleMenuState struct {
	Selection  int
	FlashTicks int
}

func (s *TitleMenuState) Step(event TitleMenuEvent) TitleMenuAction {
	switch event {
	case TitleMenuUp:
		s.Selection = (s.Selection + 2) % 3
	case TitleMenuDown:
		s.Selection = (s.Selection + 1) % 3
	case TitleMenuConfirm:
		s.FlashTicks = 24
	case TitleMenuTick:
		if s.FlashTicks > 0 {
			s.FlashTicks--
			if s.FlashTicks == 0 {
				if s.Selection == 1 {
					return TitleMenuLoadSlots
				}
				if s.Selection == 2 {
					return TitleMenuContinue
				}
				return TitleMenuStart
			}
		}
	}
	return TitleMenuNoAction
}

type TitleSlotEvent uint8

const (
	TitleSlotTick TitleSlotEvent = iota
	TitleSlotUp
	TitleSlotDown
	TitleSlotConfirm
	TitleSlotCancel
)

// TitleSlotState preserves native 0x30550's bounded four-slot selector: no
// wrap at either edge, confirm loads the selected slot, and cancel returns to
// the title menu.
type TitleSlotState struct {
	Selection int
}

func (s *TitleSlotState) Step(event TitleSlotEvent) (selected int, confirm, cancel bool) {
	switch event {
	case TitleSlotUp:
		if s.Selection > 0 {
			s.Selection--
		}
	case TitleSlotDown:
		if s.Selection < 3 {
			s.Selection++
		}
	case TitleSlotConfirm:
		return s.Selection, true, false
	case TitleSlotCancel:
		return s.Selection, false, true
	}
	return s.Selection, false, false
}
