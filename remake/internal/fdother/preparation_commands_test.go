package fdother

import (
	"encoding/binary"
	"testing"
)

func TestParseNativePreparationCommandsUsesThreeByteRecords(t *testing.T) {
	raw := make([]byte, 9)
	raw[0] = 0
	binary.LittleEndian.PutUint16(raw[1:], 0x1234)
	raw[3] = 1
	binary.LittleEndian.PutUint16(raw[4:], 0x00b5)
	raw[6] = 3
	binary.LittleEndian.PutUint16(raw[7:], 0xa000)
	commands, err := ParseNativePreparationCommands(raw, 3)
	if err != nil {
		t.Fatal(err)
	}
	want := []NativePreparationCommand{{Kind: 0, Payload: 0x1234}, {Kind: 1, Payload: 0xb5}, {Kind: 3, Payload: 0xa000}}
	for i := range want {
		if commands[i] != want[i] {
			t.Fatalf("command %d=%#v, want %#v", i, commands[i], want[i])
		}
	}
}

func TestParseNativePreparationCommandsRejectsTruncation(t *testing.T) {
	if _, err := ParseNativePreparationCommands(make([]byte, 5), 2); err == nil {
		t.Fatal("short command stream must fail closed")
	}
}
