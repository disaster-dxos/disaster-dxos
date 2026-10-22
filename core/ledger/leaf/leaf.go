// SPDX-License-Identifier: Apache-2.0

// Package leaf định nghĩa nội dung một lá (entry) của sổ cái minh bạch (D-007, #28).
//
// Lá là một object JSON nhỏ, dạng chuẩn tắc (khóa sắp xếp, không khoảng trắng):
//
//	{"attrs":{"at":"…","direction":"nhap","quantity":"10.00"},"ref":"<mã giao dịch>","sha256":"<64 hex>","type":"cuu-tro.phieu-kho","v":1}
//
// Lá CHỈ chứa mã giao dịch, loại, SHA-256 của bản ghi chuẩn hóa (bản ghi đầy đủ nằm trong CSDL
// của ứng dụng) và vài thuộc tính ngắn không định danh (số lượng, thời điểm). Không có dữ liệu cá
// nhân: bộ ký tự của thuộc tính bị giới hạn (không dấu, không khoảng trắng nên không ghi được họ tên)
// và dãy từ 9 chữ số bắt đầu bằng 0 (dạng SĐT, CCCD Việt Nam) bị từ chối; số tiền lớn vẫn ghi được. Lõi không biết nghiệp vụ: loại và thuộc tính do ứng dụng Tầng 2 quyết định.
package leaf

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"sort"
	"strings"

	"github.com/transparency-dev/merkle/rfc6962"
)

// Version là phiên bản định dạng lá hiện tại (trường "v").
const Version = 1

// Giới hạn kích thước: lá nhỏ, cố định; sổ cái không phải nơi chứa dữ liệu.
const (
	MaxAttrs       = 8
	MaxAttrValue   = 64
	MaxEncodedSize = 1024
)

var (
	reType     = regexp.MustCompile(`^[a-z0-9][a-z0-9_.-]{0,63}$`)
	reRef      = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$`)
	reSHA256   = regexp.MustCompile(`^[0-9a-f]{64}$`)
	reAttrKey  = regexp.MustCompile(`^[a-z][a-z0-9_]{0,31}$`)
	reAttrVal  = regexp.MustCompile(`^[A-Za-z0-9_.:+-]{1,64}$`)
	reLongDigs = regexp.MustCompile(`(^|[^0-9])0[0-9]{8,}`)
)

// Entry là nội dung một lá.
type Entry struct {
	V      int               `json:"v"`
	Type   string            `json:"type"`
	Ref    string            `json:"ref"`
	SHA256 string            `json:"sha256"`
	Attrs  map[string]string `json:"attrs,omitempty"`
}

// Validate kiểm định dạng và chặn những gì giống dữ liệu cá nhân trong thuộc tính.
func (e Entry) Validate() error {
	if e.V != Version {
		return fmt.Errorf("v phải là %d", Version)
	}
	if !reType.MatchString(e.Type) {
		return errors.New("type không hợp lệ (chữ thường, số, . _ -, tối đa 64 ký tự)")
	}
	if !reRef.MatchString(e.Ref) {
		return errors.New("ref không hợp lệ (chữ, số, . _ : -, tối đa 128 ký tự)")
	}
	if !reSHA256.MatchString(e.SHA256) {
		return errors.New("sha256 phải là 64 ký tự hex thường")
	}
	if len(e.Attrs) > MaxAttrs {
		return fmt.Errorf("tối đa %d thuộc tính", MaxAttrs)
	}
	for k, v := range e.Attrs {
		if !reAttrKey.MatchString(k) {
			return fmt.Errorf("tên thuộc tính %q không hợp lệ", k)
		}
		if !reAttrVal.MatchString(v) {
			return fmt.Errorf("giá trị thuộc tính %q không hợp lệ (chữ, số, . _ : + -, 1-%d ký tự, không có khoảng trắng)", k, MaxAttrValue)
		}
		if reLongDigs.MatchString(v) {
			return fmt.Errorf("thuộc tính %q có dãy số dạng SĐT/CCCD (bắt đầu bằng 0, từ 9 chữ số): không đưa dữ liệu cá nhân lên sổ cái", k)
		}
	}
	return nil
}

// Encode trả bytes chuẩn tắc của lá (sau khi kiểm hợp lệ).
func (e Entry) Encode() ([]byte, error) {
	if err := e.Validate(); err != nil {
		return nil, err
	}
	if len(e.Attrs) == 0 {
		e.Attrs = nil
	}
	b, err := json.Marshal(e)
	if err != nil {
		return nil, err
	}
	// encoding/json giữ thứ tự trường của struct; đổi sang khóa sắp xếp như CanonicalJSON
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	b, err = marshalSorted(m)
	if err != nil {
		return nil, err
	}
	if len(b) > MaxEncodedSize {
		return nil, fmt.Errorf("lá dài %d byte, tối đa %d", len(b), MaxEncodedSize)
	}
	return b, nil
}

// Decode đọc một lá và bảo đảm nó đúng dạng chuẩn tắc (mã hóa lại phải ra đúng các byte đó).
func Decode(b []byte) (Entry, error) {
	var e Entry
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&e); err != nil {
		return Entry{}, fmt.Errorf("lá không phải JSON hợp lệ: %w", err)
	}
	again, err := e.Encode()
	if err != nil {
		return Entry{}, err
	}
	if !bytes.Equal(again, b) {
		return Entry{}, errors.New("lá không ở dạng chuẩn tắc")
	}
	return e, nil
}

// Hash là leaf hash RFC 6962 (SHA-256(0x00 || lá)), giá trị nằm trong cây Merkle của sổ cái.
func Hash(b []byte) []byte {
	return rfc6962.DefaultHasher.HashLeaf(b)
}

// CanonicalJSON trả dạng chuẩn tắc của một object JSON phẳng (giá trị là chuỗi hoặc null) mà ứng
// dụng dùng để băm bản ghi: khóa sắp xếp theo thứ tự byte, không khoảng trắng, UTF-8 (không escape
// ký tự ngoài ASCII hay < > &). Trùng với RFC 8785 (JCS) cho object chỉ gồm chuỗi, trừ U+2028/U+2029
// viết dạng  /  như encoding/json. Bên Python: json.dumps(sort_keys=True,
// separators=(",", ":"), ensure_ascii=False) rồi thay U+2028/U+2029 (apps/cuu-tro/workflow).
func CanonicalJSON(raw []byte) ([]byte, error) {
	var m map[string]any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&m); err != nil {
		return nil, fmt.Errorf("bản ghi không phải object JSON: %w", err)
	}
	if m == nil {
		return nil, errors.New("bản ghi không phải object JSON")
	}
	for k, v := range m {
		switch v.(type) {
		case string, nil:
		default:
			return nil, fmt.Errorf("trường %q: bản ghi chuẩn hóa chỉ gồm chuỗi hoặc null", k)
		}
	}
	return marshalSorted(m)
}

// marshalSorted mã hóa map với khóa sắp xếp, không escape HTML, không xuống dòng cuối.
func marshalSorted(m map[string]any) ([]byte, error) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var buf bytes.Buffer
	buf.WriteByte('{')
	for i, k := range keys {
		if i > 0 {
			buf.WriteByte(',')
		}
		if err := writeJSON(&buf, k); err != nil {
			return nil, err
		}
		buf.WriteByte(':')
		if sub, ok := m[k].(map[string]any); ok {
			b, err := marshalSorted(sub)
			if err != nil {
				return nil, err
			}
			buf.Write(b)
			continue
		}
		if err := writeJSON(&buf, m[k]); err != nil {
			return nil, err
		}
	}
	buf.WriteByte('}')
	return buf.Bytes(), nil
}

func writeJSON(buf *bytes.Buffer, v any) error {
	var tmp bytes.Buffer
	enc := json.NewEncoder(&tmp)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return err
	}
	buf.WriteString(strings.TrimSuffix(tmp.String(), "\n"))
	return nil
}
