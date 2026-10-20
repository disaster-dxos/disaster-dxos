// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/transparency-dev/formats/log"
	"github.com/transparency-dev/merkle/proof"
	"github.com/transparency-dev/merkle/rfc6962"
	"golang.org/x/mod/sumdb/note"

	"github.com/disaster-dxos/disaster-dxos/core/ledger/leaf"
)

const testToken = "token-thu-nghiem-cuu-tro"

func newTestLedger(t *testing.T, persistentAS bool) (*httptest.Server, *keySet) {
	t.Helper()
	dir := t.TempDir()
	skey, _, err := note.GenerateKey(rand.Reader, "test.local/ledger")
	if err != nil {
		t.Fatal(err)
	}
	keys, err := parseSigningKey(skey)
	if err != nil {
		t.Fatal(err)
	}
	writers := filepath.Join(dir, "writers")
	if err := os.WriteFile(writers, []byte("# dịch vụ được ghi\ncuu-tro "+testToken+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	cfg := config{
		storageDir: filepath.Join(dir, "log"), antispamDir: filepath.Join(dir, "antispam"),
		cpInterval: 100 * time.Millisecond, batchMaxAge: 20 * time.Millisecond, batchMaxSize: 16,
		antispamMemory: 64, persistentAS: persistentAS, awaitTimeout: 10 * time.Second,
	}
	ctx, cancel := context.WithCancel(context.Background())
	lg, err := openLog(ctx, cfg, keys)
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewServer(newServer(lg, keys, writers).routes())
	t.Cleanup(func() {
		ts.Close()
		_ = lg.shutdown(context.Background())
		cancel()
	})
	// Chờ checkpoint đầu tiên (cây rỗng)
	deadline := time.Now().Add(10 * time.Second)
	for {
		r, err := http.Get(ts.URL + "/healthz")
		if err == nil {
			r.Body.Close()
			if r.StatusCode == 200 {
				break
			}
		}
		if time.Now().After(deadline) {
			t.Fatal("ledger không sẵn sàng")
		}
		time.Sleep(50 * time.Millisecond)
	}
	return ts, keys
}

func post(t *testing.T, ts *httptest.Server, token, body string) (*http.Response, map[string]any) {
	t.Helper()
	req, _ := http.NewRequest(http.MethodPost, ts.URL+"/ledger/entries", strings.NewReader(body))
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	r, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Body.Close()
	var m map[string]any
	_ = json.NewDecoder(r.Body).Decode(&m)
	return r, m
}

func entryBody(ref string) string {
	return `{"type":"cuu-tro.phieu-kho","ref":"` + ref + `","sha256":"` + strings.Repeat("0a", 32) +
		`","attrs":{"direction":"nhap","quantity":"10.00"}}`
}

func TestWriteRequiresToken(t *testing.T) {
	ts, _ := newTestLedger(t, false)
	for _, tok := range []string{"", "sai-token", testToken + "x"} {
		r, _ := post(t, ts, tok, entryBody("p-1"))
		if r.StatusCode != http.StatusUnauthorized {
			t.Errorf("token %q: mã %d, muốn 401", tok, r.StatusCode)
		}
	}
	r, m := post(t, ts, testToken, `{"type":"x","ref":"y","sha256":"z","them":"1"}`)
	if r.StatusCode != http.StatusBadRequest {
		t.Errorf("trường lạ: mã %d (%v)", r.StatusCode, m)
	}
	r, m = post(t, ts, testToken, `{"type":"cuu-tro.phieu-kho","ref":"p-1","sha256":"`+strings.Repeat("0a", 32)+`","attrs":{"sdt":"0905123456"}}`)
	if r.StatusCode != http.StatusUnprocessableEntity {
		t.Errorf("SĐT trong thuộc tính: mã %d (%v)", r.StatusCode, m)
	}
}

func TestAddProofAndStatic(t *testing.T) {
	ts, keys := newTestLedger(t, true)
	var indexes []uint64
	for _, ref := range []string{"p-1", "p-2", "p-3"} {
		r, m := post(t, ts, testToken, entryBody(ref))
		if r.StatusCode != http.StatusCreated {
			t.Fatalf("%s: mã %d (%v)", ref, r.StatusCode, m)
		}
		indexes = append(indexes, uint64(m["index"].(float64)))
	}
	if indexes[0] != 0 || indexes[1] != 1 || indexes[2] != 2 {
		t.Fatalf("index = %v", indexes)
	}
	// Gửi lại đúng lá cũ: chống trùng trả index cũ, không thêm lá
	r, m := post(t, ts, testToken, entryBody("p-2"))
	if r.StatusCode != http.StatusOK || m["duplicate"] != true || uint64(m["index"].(float64)) != 1 {
		t.Fatalf("lá trùng: mã %d %v", r.StatusCode, m)
	}

	// Proof của lá 1 kiểm được với root trong checkpoint đã ký
	pr, err := http.Get(ts.URL + "/ledger/proof/1")
	if err != nil {
		t.Fatal(err)
	}
	var p proofResponse
	if err := json.NewDecoder(pr.Body).Decode(&p); err != nil {
		t.Fatal(err)
	}
	pr.Body.Close()
	cp, _, _, err := log.ParseCheckpoint([]byte(p.Checkpoint), keys.signer.Name(), keys.verifier)
	if err != nil {
		t.Fatal(err)
	}
	e, err := leaf.Decode([]byte(p.Leaf))
	if err != nil || e.Ref != "p-2" {
		t.Fatalf("lá 1: %+v %v", e, err)
	}
	lh, _ := hex.DecodeString(p.LeafHash)
	var hashes [][]byte
	for _, h := range p.Proof {
		b, _ := hex.DecodeString(h)
		hashes = append(hashes, b)
	}
	if err := proof.VerifyInclusion(rfc6962.DefaultHasher, 1, cp.Size, lh, hashes, cp.Hash); err != nil {
		t.Fatalf("proof không hợp lệ: %v", err)
	}
	if cp.Size != 3 {
		t.Fatalf("kích thước cây %d", cp.Size)
	}
	// Lá chưa có
	pr, _ = http.Get(ts.URL + "/ledger/proof/99")
	pr.Body.Close()
	if pr.StatusCode != http.StatusNotFound {
		t.Errorf("proof lá chưa có: mã %d", pr.StatusCode)
	}

	// Đọc tĩnh: checkpoint, entry bundle một phần, verifier; .state và thư mục thì không
	for path, want := range map[string]int{
		"/ledger/checkpoint":               200,
		"/ledger/tile/entries/000.p/3":     200,
		"/ledger/tile/0/000.p/3":           200,
		"/ledger/verifier":                 200,
		"/ledger/tile/":                    404,
		"/ledger/tile/../.state/treeState": 404,
		"/ledger/.state/treeState":         404,
	} {
		r, err := http.Get(ts.URL + path)
		if err != nil {
			t.Fatal(err)
		}
		b, _ := io.ReadAll(r.Body)
		r.Body.Close()
		if r.StatusCode != want {
			t.Errorf("GET %s: mã %d, muốn %d", path, r.StatusCode, want)
		}
		if path == "/ledger/verifier" && strings.TrimSpace(string(b)) != keys.verifierKey {
			t.Errorf("verifier = %q", b)
		}
	}
}

func TestParseSigningKeyErrorsDoNotLeakKey(t *testing.T) {
	skey, _, _ := note.GenerateKey(rand.Reader, "test.local/ledger")
	// Đổi hash → khóa sai; thông báo lỗi không được chứa khóa
	parts := strings.SplitN(skey, "+", 5)
	parts[3] = "00000000"
	bad := strings.Join(parts, "+")
	_, err := parseSigningKey(bad)
	if err == nil {
		t.Fatal("khóa sai hash phải bị từ chối")
	}
	if strings.Contains(err.Error(), parts[4]) {
		t.Fatal("thông báo lỗi chứa khóa bí mật")
	}
}
