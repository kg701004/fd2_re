package fdother

import (
	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
)

// DecodeSpriteBankResource loads one LLLLLL archive resource whose payload is
// the native 24x24 four-mode B24 layout. FDSHAP's even resources use this
// form; callers retain responsibility for pairing a map with its evidenced
// resource number and for keeping the adjacent control table separate.
func DecodeSpriteBankResource(datPath string, resource int) (*fdicon.Bank, error) {
	raw, err := ReadResource(datPath, resource)
	if err != nil {
		return nil, err
	}
	return fdicon.Parse(raw)
}
