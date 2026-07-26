package fdother

import (
	"errors"

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

// DecodeMapTerrainResources loads the evidenced FDSHAP pairing for a map:
// image bank #2N and its adjacent four-byte-per-tile control table #2N+1.
// The map index must come from an explicit campaign/map binding; neither the
// image count nor normalized map data is permitted to guess it.
func DecodeMapTerrainResources(datPath string, mapIndex int) (*fdicon.Bank, []byte, error) {
	if mapIndex < 0 {
		return nil, nil, errors.New("fdother: negative FDSHAP map index")
	}
	resource := mapIndex * 2
	bank, err := DecodeSpriteBankResource(datPath, resource)
	if err != nil {
		return nil, nil, err
	}
	controls, err := ReadResource(datPath, resource+1)
	if err != nil {
		return nil, nil, err
	}
	if len(controls) == 0 || len(controls)%4 != 0 || len(bank.Sprites) > len(controls)/4 {
		return nil, nil, errors.New("fdother: FDSHAP image/control resource pair is inconsistent")
	}
	return bank, controls, nil
}
