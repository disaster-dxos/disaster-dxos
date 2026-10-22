// SPDX-License-Identifier: Apache-2.0

package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/transparency-dev/tessera"
	"github.com/transparency-dev/tessera/storage/posix"
	"golang.org/x/mod/sumdb/note"

	"github.com/disaster-dxos/disaster-dxos/core/ledger/leaf"
)

const record = `{"id":"p-2","direction":"nhap","quantity":"10.00","note":"Hàng cứu trợ","shelter_id":null}`

// testLog dựng một log Tessera POSIX thật trong thư mục tạm có 3 lá (lá 1 là bản ghi record) và
// phục vụ nó như file tĩnh (giống /ledger/ qua gateway).
func testLog(t *testing.T) (url, vkey, dir string) {
	t.Helper()
	dir = t.TempDir()
	skey, vkey, err := note.GenerateKey(rand.Reader, "test.local/ledger")
	if err != nil {
		t.Fatal(err)
	}
	s, _ := note.NewSigner(skey)
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	d, err := posix.New(ctx, posix.Config{Path: dir})
	if err != nil {
		t.Fatal(err)
	}
	app, shutdown, reader, err := tessera.NewAppender(ctx, d, tessera.NewAppendOptions().
		WithCheckpointSigner(s).WithCheckpointInterval(100*time.Millisecond).WithBatching(16, 20*time.Millisecond))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = shutdown(context.Background()) })
	aw := tessera.NewPublicationAwaiter(ctx, reader.ReadCheckpoint, 20*time.Millisecond)
	canon, _ := leaf.CanonicalJSON([]byte(record))
	sum := sha256.Sum256(canon)
	for _, ref := range []string{"p-1", "p-2", "p-3"} {
		h := strings.Repeat("0", 64)
		if ref == "p-2" {
			h = hex.EncodeToString(sum[:])
		}
		b, err := leaf.Entry{V: 1, Type: "cuu-tro.phieu-kho", Ref: ref, SHA256: h}.Encode()
		if err != nil {
			t.Fatal(err)
		}
		wctx, wcancel := context.WithTimeout(ctx, 10*time.Second)
		if _, _, err := aw.Await(wctx, app.Add(wctx, tessera.NewEntry(b))); err != nil {
			t.Fatal(err)
		}
		wcancel()
	}
	ts := httptest.NewServer(http.FileServer(http.Dir(dir)))
	t.Cleanup(ts.Close)
	return ts.URL + "/", vkey, dir
}

func runCLI(args ...string) (int, string) {
	var out, errb bytes.Buffer
	code := run(args, &out, &errb)
	return code, out.String() + errb.String()
}

func TestVerifyOK(t *testing.T) {
	url, vkey, _ := testLog(t)
	f := filepath.Join(t.TempDir(), "phieu.json")
	_ = os.WriteFile(f, []byte(record), 0o600)
	code, out := runCLI("-log", url, "-verifier", vkey, "-index", "1", "-record", f)
	if code != 0 || !strings.Contains(out, "ĐÃ XÁC MINH") {
		t.Fatalf("mã %d\n%s", code, out)
	}
	// Phản hồi của trang minh bạch (bản ghi nằm trong "ban_ghi_chuan_hoa") cũng nhận được
	_ = os.WriteFile(f, []byte(`{"trang_thai":"da_xac_minh","ban_ghi_chuan_hoa":`+record+`}`), 0o600)
	if code, out := runCLI("-log", url, "-verifier", vkey, "-index", "1", "-record", f); code != 0 {
		t.Fatalf("phản hồi trang minh bạch: mã %d\n%s", code, out)
	}
}

func TestVerifyDetectsTampering(t *testing.T) {
	url, vkey, dir := testLog(t)
	f := filepath.Join(t.TempDir(), "phieu.json")

	// Bản ghi bị sửa số lượng → SHA-256 không khớp lá
	_ = os.WriteFile(f, []byte(strings.Replace(record, "10.00", "100.00", 1)), 0o600)
	if code, out := runCLI("-log", url, "-verifier", vkey, "-index", "1", "-record", f); code != 1 || !strings.Contains(out, "KHÔNG khớp") {
		t.Fatalf("bản ghi sửa: mã %d\n%s", code, out)
	}
	// Bản ghi đúng nhưng hỏi sai vị trí lá → mã giao dịch / SHA-256 không khớp
	_ = os.WriteFile(f, []byte(record), 0o600)
	if code, _ := runCLI("-log", url, "-verifier", vkey, "-index", "0", "-record", f); code != 1 {
		t.Fatalf("sai index: mã %d", code)
	}
	// Khóa công khai khác → checkpoint không xác minh được
	_, other, _ := note.GenerateKey(rand.Reader, "test.local/ledger")
	if code, out := runCLI("-log", url, "-verifier", other, "-index", "1"); code != 1 || !strings.Contains(out, "checkpoint") {
		t.Fatalf("khóa lạ: mã %d\n%s", code, out)
	}
	// Sửa lá trên đĩa (đổi ref trong entry bundle, giữ nguyên độ dài) → inclusion proof sai
	bundle := filepath.Join(dir, "tile", "entries", "000.p", "3")
	b, err := os.ReadFile(bundle)
	if err != nil {
		t.Fatal(err)
	}
	_ = os.WriteFile(bundle, bytes.Replace(b, []byte(`"ref":"p-2"`), []byte(`"ref":"p-9"`), 1), 0o644)
	if code, out := runCLI("-log", url, "-verifier", vkey, "-index", "1", "-ref", "p-9"); code != 1 || !strings.Contains(out, "inclusion proof sai") {
		t.Fatalf("lá bị sửa trên đĩa: mã %d\n%s", code, out)
	}
	// Thiếu tham số
	if code, _ := runCLI("-log", url); code != 2 {
		t.Fatalf("thiếu tham số: mã %d", code)
	}
}
