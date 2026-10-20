// SPDX-License-Identifier: Apache-2.0

package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"io/fs"
	"log/slog"
	"net/http"
	"os"
	"path"
	"strconv"
	"strings"
	"time"

	"github.com/transparency-dev/formats/log"
	"github.com/transparency-dev/tessera"
	"github.com/transparency-dev/tessera/api/layout"
	"github.com/transparency-dev/tessera/client"

	"github.com/disaster-dxos/disaster-dxos/core/ledger/leaf"
)

// Quyền ghi (#28): ledger không mở cổng ra máy host, APISIX không có route POST tới ledger
// (core/apisix/apisix.yaml chặn 403). Chỉ dịch vụ trong mạng Docker nội bộ gọi được
// POST /ledger/entries, và phải gửi "Authorization: Bearer <token>" khớp một dòng trong file writers.
// Token sinh ngẫu nhiên cho từng ứng dụng (secret/app/<APP>/ledger trong OpenBao), chỉ backend của
// ứng dụng đó (vd cuu-tro-api) và ledger đọc được. Ứng dụng tự kiểm vai trò người dùng (dieu-phoi)
// trước khi gọi ghi; ledger không nhận JWT người dùng.
const maxBody = 4096

type server struct {
	lg      *ledgerLog
	keys    *keySet
	writers string
	root    *os.Root
}

func newServer(lg *ledgerLog, keys *keySet, writers string) *server {
	root, err := os.OpenRoot(lg.storageDir)
	if err != nil {
		slog.Error("không mở được thư mục lưu trữ", "loi", err)
		os.Exit(1)
	}
	return &server{lg: lg, keys: keys, writers: writers, root: root}
}

func (s *server) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /ledger/entries", s.addEntry)
	mux.HandleFunc("GET /ledger/proof/{index}", s.proof)
	mux.HandleFunc("GET /ledger/checkpoint", s.static)
	mux.HandleFunc("GET /ledger/tile/", s.static)
	mux.HandleFunc("GET /ledger/verifier", s.verifier)
	mux.HandleFunc("GET /healthz", s.healthz)
	return mux
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, code int, msg string) {
	writeJSON(w, code, map[string]string{"error": msg})
}

// writer trả tên dịch vụ ứng với Bearer token, "" nếu không có quyền. So sánh SHA-256 của token
// trong thời gian hằng; đọc lại file mỗi lần để đổi token (OpenBao) không cần khởi động lại.
func (s *server) writer(r *http.Request) string {
	auth := r.Header.Get("Authorization")
	tok, ok := strings.CutPrefix(auth, "Bearer ")
	if !ok || tok == "" {
		return ""
	}
	want := sha256.Sum256([]byte(tok))
	f, err := os.Open(s.writers)
	if err != nil {
		slog.Error("không đọc được danh sách dịch vụ được ghi", "loi", err)
		return ""
	}
	defer f.Close()
	found := ""
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		name, t, ok := strings.Cut(line, " ")
		if !ok {
			continue
		}
		got := sha256.Sum256([]byte(strings.TrimSpace(t)))
		if subtle.ConstantTimeCompare(want[:], got[:]) == 1 && found == "" {
			found = name
		}
	}
	return found
}

type addRequest struct {
	Type   string            `json:"type"`
	Ref    string            `json:"ref"`
	SHA256 string            `json:"sha256"`
	Attrs  map[string]string `json:"attrs,omitempty"`
}

type addResponse struct {
	Index     uint64 `json:"index"`
	LeafHash  string `json:"leaf_hash"`
	Duplicate bool   `json:"duplicate"`
	TreeSize  uint64 `json:"tree_size"`
	Origin    string `json:"origin"`
}

func (s *server) addEntry(w http.ResponseWriter, r *http.Request) {
	who := s.writer(r)
	if who == "" {
		w.Header().Set("WWW-Authenticate", "Bearer")
		writeErr(w, http.StatusUnauthorized, "cần token ghi của dịch vụ nội bộ")
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxBody))
	if err != nil {
		writeErr(w, http.StatusRequestEntityTooLarge, "body quá lớn")
		return
	}
	var req addRequest
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, "body không đúng dạng {type, ref, sha256, attrs}: "+err.Error())
		return
	}
	e := leaf.Entry{V: leaf.Version, Type: req.Type, Ref: req.Ref, SHA256: req.SHA256, Attrs: req.Attrs}
	data, err := e.Encode()
	if err != nil {
		writeErr(w, http.StatusUnprocessableEntity, err.Error())
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), s.lg.timeout)
	defer cancel()
	// Await: chờ tới khi checkpoint đã ký bao gồm lá này, để proof có ngay sau khi trả về
	idx, cpRaw, err := s.lg.awaiter.Await(ctx, s.lg.appender.Add(ctx, tessera.NewEntry(data)))
	if err != nil {
		if errors.Is(err, tessera.ErrPushback) {
			w.Header().Set("Retry-After", "2")
			writeErr(w, http.StatusServiceUnavailable, "sổ cái đang bận, thử lại sau")
			return
		}
		slog.Error("ghi lá lỗi", "dich_vu", who, "type", e.Type, "ref", e.Ref, "loi", err)
		writeErr(w, http.StatusServiceUnavailable, "không ghi được lá")
		return
	}
	cp, _, _, err := log.ParseCheckpoint(cpRaw, s.keys.signer.Name(), s.keys.verifier)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "checkpoint không hợp lệ")
		return
	}
	slog.Info("đã ghi lá", "dich_vu", who, "type", e.Type, "ref", e.Ref, "index", idx.Index, "trung", idx.IsDup)
	code := http.StatusCreated
	if idx.IsDup {
		code = http.StatusOK
	}
	writeJSON(w, code, addResponse{
		Index:     idx.Index,
		LeafHash:  hex.EncodeToString(leaf.Hash(data)),
		Duplicate: idx.IsDup,
		TreeSize:  cp.Size,
		Origin:    cp.Origin,
	})
}

type proofResponse struct {
	Index      uint64   `json:"index"`
	TreeSize   uint64   `json:"tree_size"`
	RootHash   string   `json:"root_hash"`
	Leaf       string   `json:"leaf"`
	LeafHash   string   `json:"leaf_hash"`
	Proof      []string `json:"proof"`
	Checkpoint string   `json:"checkpoint"`
}

// buildProof dựng inclusion proof của lá index theo checkpoint đang công bố, từ chính tile và entry
// bundle trên đĩa (cùng dữ liệu mà client ngoài tải qua /ledger/tile/).
func (s *server) buildProof(ctx context.Context, index uint64) (*proofResponse, error) {
	cpRaw, err := s.lg.reader.ReadCheckpoint(ctx)
	if err != nil {
		return nil, err
	}
	cp, _, _, err := log.ParseCheckpoint(cpRaw, s.keys.signer.Name(), s.keys.verifier)
	if err != nil {
		return nil, err
	}
	if index >= cp.Size {
		return nil, errNotYet
	}
	pb, err := client.NewProofBuilder(ctx, cp.Size, s.lg.reader.ReadTile)
	if err != nil {
		return nil, err
	}
	p, err := pb.InclusionProof(ctx, index)
	if err != nil {
		return nil, err
	}
	bundle, err := client.GetEntryBundle(ctx, s.lg.reader.ReadEntryBundle, index/layout.EntryBundleWidth, cp.Size)
	if err != nil {
		return nil, err
	}
	i := index % layout.EntryBundleWidth
	if i >= uint64(len(bundle.Entries)) {
		return nil, errors.New("entry bundle thiếu lá")
	}
	data := bundle.Entries[i]
	out := &proofResponse{
		Index:      index,
		TreeSize:   cp.Size,
		RootHash:   hex.EncodeToString(cp.Hash),
		Leaf:       string(data),
		LeafHash:   hex.EncodeToString(leaf.Hash(data)),
		Proof:      make([]string, len(p)),
		Checkpoint: string(cpRaw),
	}
	for j, h := range p {
		out.Proof[j] = hex.EncodeToString(h)
	}
	return out, nil
}

func (s *server) proof(w http.ResponseWriter, r *http.Request) {
	index, err := strconv.ParseUint(r.PathValue("index"), 10, 64)
	if err != nil {
		writeErr(w, http.StatusBadRequest, "index phải là số nguyên không âm")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	out, err := s.buildProof(ctx, index)
	// Tile một phần có thể vừa được thay bằng tile đầy đủ giữa hai lần đọc: thử lại một lần
	if err != nil && !errors.Is(err, errNotYet) {
		out, err = s.buildProof(ctx, index)
	}
	switch {
	case errors.Is(err, errNotYet):
		writeErr(w, http.StatusNotFound, err.Error())
	case err != nil:
		slog.Error("dựng proof lỗi", "index", index, "loi", err)
		writeErr(w, http.StatusInternalServerError, "không dựng được proof")
	default:
		w.Header().Set("Cache-Control", "no-cache")
		writeJSON(w, http.StatusOK, out)
	}
}

// static phục vụ checkpoint và tile/ theo tlog-tiles, chỉ đọc, giới hạn trong thư mục log (os.Root:
// không thoát ra ngoài bằng ".." hay symlink), không liệt kê thư mục, không phục vụ .state/.
func (s *server) static(w http.ResponseWriter, r *http.Request) {
	rel := strings.TrimPrefix(path.Clean(r.URL.Path), "/ledger/")
	if rel != "checkpoint" && !strings.HasPrefix(rel, "tile/") {
		http.NotFound(w, r)
		return
	}
	f, err := s.root.Open(rel)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil || st.IsDir() {
		http.NotFound(w, r)
		return
	}
	switch {
	case rel == "checkpoint":
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.Header().Set("Cache-Control", "no-cache")
	case strings.Contains(rel, ".p/"):
		// Tile một phần sẽ được thay khi đầy
		w.Header().Set("Content-Type", "application/octet-stream")
		w.Header().Set("Cache-Control", "no-cache")
	default:
		// Tile đầy đủ không bao giờ đổi (tlog-tiles)
		w.Header().Set("Content-Type", "application/octet-stream")
		w.Header().Set("Cache-Control", "max-age=31536000, immutable")
	}
	http.ServeContent(w, r, "", st.ModTime(), f)
}

func (s *server) verifier(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = io.WriteString(w, s.keys.verifierKey+"\n")
}

func (s *server) healthz(w http.ResponseWriter, r *http.Request) {
	if _, err := s.lg.reader.ReadCheckpoint(r.Context()); err != nil {
		code := http.StatusServiceUnavailable
		if errors.Is(err, fs.ErrNotExist) {
			// Log mới: checkpoint đầu tiên (cây rỗng) được ký trong vài giây đầu
			writeErr(w, code, "chưa có checkpoint")
			return
		}
		writeErr(w, code, "không đọc được checkpoint")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "origin": s.keys.signer.Name()})
}
