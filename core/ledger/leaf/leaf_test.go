// SPDX-License-Identifier: Apache-2.0

package leaf

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"testing"
)

func valid() Entry {
	return Entry{
		V: Version, Type: "cuu-tro.phieu-kho", Ref: "e0000000-0000-4000-8000-000000000001",
		SHA256: strings.Repeat("ab", 32),
		Attrs:  map[string]string{"quantity": "1500.00", "direction": "nhap", "at": "2026-10-20T08:15:30.123456Z"},
	}
}

func TestEncodeCanonical(t *testing.T) {
	b, err := valid().Encode()
	if err != nil {
		t.Fatal(err)
	}
	want := `{"attrs":{"at":"2026-10-20T08:15:30.123456Z","direction":"nhap","quantity":"1500.00"},` +
		`"ref":"e0000000-0000-4000-8000-000000000001","sha256":"` + strings.Repeat("ab", 32) +
		`","type":"cuu-tro.phieu-kho","v":1}`
	if string(b) != want {
		t.Fatalf("lá:\n got %s\nwant %s", b, want)
	}
	e, err := Decode(b)
	if err != nil {
		t.Fatal(err)
	}
	if e.Ref != valid().Ref || e.Attrs["quantity"] != "1500.00" {
		t.Fatalf("giải mã sai: %+v", e)
	}
	// Không có thuộc tính: bỏ trường attrs
	e2 := valid()
	e2.Attrs = map[string]string{}
	b2, err := e2.Encode()
	if err != nil || strings.Contains(string(b2), "attrs") {
		t.Fatalf("attrs rỗng: %s %v", b2, err)
	}
}

func TestValidateAllowsAmounts(t *testing.T) {
	e := valid()
	e.Attrs["amount"] = "150000000.00"
	e.Attrs["at"] = "2026-10-20T08:15:30.000001Z"
	if err := e.Validate(); err != nil {
		t.Fatalf("số tiền lớn phải ghi được: %v", err)
	}
}

func TestDecodeRejectsNonCanonical(t *testing.T) {
	b, _ := valid().Encode()
	for _, bad := range []string{
		strings.Replace(string(b), `{"attrs"`, `{ "attrs"`, 1),
		strings.Replace(string(b), `"v":1}`, `"v":1,"x":"y"}`, 1),
		`{"v":2,"type":"a","ref":"b","sha256":"` + strings.Repeat("0", 64) + `"}`,
	} {
		if _, err := Decode([]byte(bad)); err == nil {
			t.Errorf("phải từ chối lá %s", bad)
		}
	}
}

func TestValidateRejects(t *testing.T) {
	cases := map[string]func(*Entry){
		"sha256 hoa":           func(e *Entry) { e.SHA256 = strings.Repeat("AB", 32) },
		"sha256 ngắn":          func(e *Entry) { e.SHA256 = "abcd" },
		"type có khoảng trắng": func(e *Entry) { e.Type = "phieu kho" },
		"ref rỗng":             func(e *Entry) { e.Ref = "" },
		"SĐT trong thuộc tính": func(e *Entry) { e.Attrs["nguoi_nhan"] = "0905123456" },
		"CCCD":                 func(e *Entry) { e.Attrs["so"] = "ID-079203001234" },
		"chữ có dấu/khoảng trắng": func(e *Entry) {
			e.Attrs["ghi_chu"] = "Nguyễn Văn A"
		},
		"tên thuộc tính hoa": func(e *Entry) { e.Attrs["Qty"] = "1" },
		"quá nhiều thuộc tính": func(e *Entry) {
			for _, k := range []string{"a", "b", "c", "d", "e", "f"} {
				e.Attrs[k] = "1"
			}
		},
	}
	for name, mut := range cases {
		e := valid()
		mut(&e)
		if _, err := e.Encode(); err == nil {
			t.Errorf("%s: phải bị từ chối", name)
		}
	}
}

// Vector dùng chung với apps/cuu-tro/workflow/tests (băm bản ghi chuẩn hóa bên Python phải ra đúng
// các byte này): khóa sắp xếp, UTF-8 nguyên dạng, không escape < > &, null giữ nguyên.
const (
	vectorRecord = `{"quantity": "1500.00", "note": "Tiếp nhận <từ> huyện & \"đội\"", "id": "e0000000-0000-4000-8000-000000000001", "shelter_id": null}`
	vectorCanon  = `{"id":"e0000000-0000-4000-8000-000000000001","note":"Tiếp nhận <từ> huyện & \"đội\"","quantity":"1500.00","shelter_id":null}`
)

func TestCanonicalJSONVector(t *testing.T) {
	got, err := CanonicalJSON([]byte(vectorRecord))
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != vectorCanon {
		t.Fatalf("chuẩn hóa:\n got %s\nwant %s", got, vectorCanon)
	}
	sum := sha256.Sum256(got)
	t.Logf("sha256 vector = %s", hex.EncodeToString(sum[:]))
	if _, err := CanonicalJSON([]byte(`{"quantity": 1500}`)); err == nil {
		t.Error("số phải bị từ chối (bản ghi chuẩn hóa chỉ gồm chuỗi/null)")
	}
	if _, err := CanonicalJSON([]byte(`[1]`)); err == nil {
		t.Error("mảng phải bị từ chối")
	}
}

func TestHashIsRFC6962Leaf(t *testing.T) {
	// SHA-256(0x00 || "") của RFC 6962
	if got := hex.EncodeToString(Hash(nil)); got != "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d" {
		t.Fatalf("leaf hash rỗng = %s", got)
	}
}
