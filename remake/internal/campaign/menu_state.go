package campaign

// MenuEvent is the input vocabulary shared by editable choice/town nodes.
// It intentionally describes navigation only; option labels and their
// transition targets remain campaign data.
type MenuEvent uint8

const (
	MenuTick MenuEvent = iota
	MenuUp
	MenuDown
	MenuConfirm
)

// MenuState is the bounded campaign-node selector used by the remake's
// choice/town hub. It has no native service names or scene side effects.
type MenuState struct {
	Selection int
	Count     int
}

func (s *MenuState) Step(event MenuEvent) (selected int, confirm bool) {
	if s.Count < 0 {
		s.Count = 0
	}
	if s.Selection < 0 {
		s.Selection = 0
	}
	if s.Count == 0 {
		s.Selection = 0
	} else if s.Selection >= s.Count {
		s.Selection = s.Count - 1
	}
	switch event {
	case MenuUp:
		if s.Selection > 0 {
			s.Selection--
		}
	case MenuDown:
		if s.Selection+1 < s.Count {
			s.Selection++
		}
	case MenuConfirm:
		if s.Count > 0 {
			return s.Selection, true
		}
	}
	return s.Selection, false
}
