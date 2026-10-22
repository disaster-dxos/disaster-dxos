// SPDX-License-Identifier: Apache-2.0

// Lệnh ledger-verify: người ngoài TỰ kiểm chứng một lá của sổ cái minh bạch (#28) mà không cần tin
// máy chủ. Chỉ dùng dữ liệu đọc công khai theo tlog-tiles (checkpoint + tile + entry bundle), không
// dùng endpoint /ledger/proof của máy chủ:
//
//  1. tải checkpoint, kiểm chữ ký Ed25519 bằng khóa công khai (verifier key) do người dùng đưa vào;
//  2. tải entry bundle chứa lá, đọc nội dung lá (mã giao dịch, SHA-256 bản ghi, thuộc tính);
//  3. tự dựng inclusion proof từ tile hash và kiểm lá nằm trong cây có root ghi trong checkpoint;
//  4. (tùy chọn) băm lại bản ghi chuẩn hóa (JSON) mà ứng dụng công bố, so với SHA-256 trong lá.
//
// Ví dụ (qua API Gateway):
//
//	go run ./cmd/ledger-verify -log http://localhost:9080/ledger/ \
//	  -verifier "$(curl -s http://localhost:9080/ledger/verifier)" -index 3 -record phieu.json
//
// Khóa công khai nên lấy từ một nguồn độc lập với máy chủ (tài liệu phát hành, bản ghi đã lưu trước);
// lấy từ chính máy chủ thì chỉ chứng minh được tính toàn vẹn so với khóa máy chủ đang công bố.
// Mã thoát: 0 = đã xác minh; 1 = không khớp / không xác minh được; 2 = sai tham số hoặc lỗi mạng.
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/transparency-dev/merkle/proof"
	"github.com/transparency-dev/merkle/rfc6962"
	"github.com/transparency-dev/tessera/api/layout"
	"github.com/transparency-dev/tessera/client"
	"golang.org/x/mod/sumdb/note"

	"github.com/disaster-dxos/disaster-dxos/core/ledger/leaf"
)

type result struct {
	Origin     string     `json:"origin"`
	TreeSize   uint64     `json:"tree_size"`
	RootHash   string     `json:"root_hash"`
	Index      uint64     `json:"index"`
	Leaf       leaf.Entry `json:"leaf"`
	LeafHash   string     `json:"leaf_hash"`
	RecordHash string     `json:"record_sha256,omitempty"`
	Verified   bool       `json:"verified"`
	Problems   []string   `json:"problems,omitempty"`
}

// errUsage: lỗi tham số hoặc mạng (mã thoát 2), khác với "không khớp" (mã thoát 1)
var errUsage = errors.New("usage")

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("ledger-verify", flag.ContinueOnError)
	fs.SetOutput(stderr)
	logURL := fs.String("log", "", "URL gốc của sổ cái (thư mục chứa checkpoint và tile/), vd http://localhost:9080/ledger/")
	vkey := fs.String("verifier", "", "khóa công khai dạng note: <origin>+<hash>+<base64>")
	vkeyFile := fs.String("verifier-file", "", "đọc khóa công khai từ file (thay cho -verifier)")
	index := fs.Int64("index", -1, "vị trí lá trong sổ cái (ledger_index)")
	record := fs.String("record", "", "file JSON bản ghi chuẩn hóa mà ứng dụng công bố (object phẳng, giá trị chuỗi/null); \"-\" = stdin")
	ref := fs.String("ref", "", "mã giao dịch mong đợi trong lá (mặc định: trường \"id\" của -record nếu có)")
	asJSON := fs.Bool("json", false, "in kết quả dạng JSON")
	timeout := fs.Duration("timeout", 20*time.Second, "thời gian chờ tối đa")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *vkeyFile != "" {
		b, err := os.ReadFile(*vkeyFile)
		if err != nil {
			fmt.Fprintln(stderr, "đọc -verifier-file:", err)
			return 2
		}
		*vkey = string(b)
	}
	if *logURL == "" || strings.TrimSpace(*vkey) == "" || *index < 0 {
		fmt.Fprintln(stderr, "cần -log, -verifier (hoặc -verifier-file) và -index")
		fs.Usage()
		return 2
	}
	var recordRaw []byte
	if *record != "" {
		var err error
		if *record == "-" {
			recordRaw, err = io.ReadAll(os.Stdin)
		} else {
			recordRaw, err = os.ReadFile(*record)
		}
		if err != nil {
			fmt.Fprintln(stderr, "đọc -record:", err)
			return 2
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()
	res, err := verify(ctx, *logURL, strings.TrimSpace(*vkey), uint64(*index), recordRaw, *ref)
	if err != nil {
		fmt.Fprintln(stderr, "LỖI:", err)
		if errors.Is(err, errUsage) {
			return 2
		}
		return 1
	}
	if *asJSON {
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		_ = enc.Encode(res)
	} else {
		printText(stdout, res)
	}
	if !res.Verified {
		return 1
	}
	return 0
}

func verify(ctx context.Context, logURL, vkey string, index uint64, recordRaw []byte, wantRef string) (*result, error) {
	u, err := url.Parse(logURL)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") {
		return nil, fmt.Errorf("%w: -log phải là URL http(s)", errUsage)
	}
	v, err := note.NewVerifier(vkey)
	if err != nil {
		return nil, fmt.Errorf("%w: khóa công khai không hợp lệ: %v", errUsage, err)
	}
	f, err := client.NewHTTPFetcher(u, &http.Client{Timeout: 10 * time.Second})
	if err != nil {
		return nil, fmt.Errorf("%w: %v", errUsage, err)
	}

	// 1. Checkpoint: chữ ký phải hợp lệ với khóa công khai, origin phải là tên khóa
	cp, _, _, err := client.FetchCheckpoint(ctx, f.ReadCheckpoint, v, v.Name())
	if err != nil {
		return nil, fmt.Errorf("checkpoint không xác minh được bằng khóa công khai: %v", err)
	}
	res := &result{Origin: cp.Origin, TreeSize: cp.Size, RootHash: hex.EncodeToString(cp.Hash), Index: index}
	if index >= cp.Size {
		return nil, fmt.Errorf("lá %d chưa có trong checkpoint (kích thước cây %d)", index, cp.Size)
	}

	// 2. Nội dung lá từ entry bundle công khai
	bundle, err := client.GetEntryBundle(ctx, f.ReadEntryBundle, index/layout.EntryBundleWidth, cp.Size)
	if err != nil {
		return nil, fmt.Errorf("tải entry bundle: %v", err)
	}
	i := index % layout.EntryBundleWidth
	if i >= uint64(len(bundle.Entries)) {
		return nil, errors.New("entry bundle thiếu lá")
	}
	data := bundle.Entries[i]
	lh := leaf.Hash(data)
	res.LeafHash = hex.EncodeToString(lh)
	e, err := leaf.Decode(data)
	if err != nil {
		res.Problems = append(res.Problems, "nội dung lá không đúng định dạng: "+err.Error())
	}
	res.Leaf = e

	// 3. Inclusion proof tự dựng từ tile, kiểm với root của checkpoint đã ký
	pb, err := client.NewProofBuilder(ctx, cp.Size, f.ReadTile)
	if err != nil {
		return nil, err
	}
	p, err := pb.InclusionProof(ctx, index)
	if err != nil {
		return nil, fmt.Errorf("dựng inclusion proof từ tile: %v", err)
	}
	if err := proof.VerifyInclusion(rfc6962.DefaultHasher, index, cp.Size, lh, p, cp.Hash); err != nil {
		res.Problems = append(res.Problems, "inclusion proof sai: "+err.Error())
	}

	// 4. Bản ghi do ứng dụng công bố → SHA-256 → so với lá
	if recordRaw != nil {
		canon, err := leaf.CanonicalJSON(extractRecord(recordRaw))
		if err != nil {
			return nil, fmt.Errorf("%w: %v", errUsage, err)
		}
		sum := sha256.Sum256(canon)
		res.RecordHash = hex.EncodeToString(sum[:])
		if res.RecordHash != e.SHA256 {
			res.Problems = append(res.Problems, "SHA-256 của bản ghi KHÔNG khớp với lá: bản ghi đã bị sửa hoặc không phải bản ghi của lá này")
		}
		if wantRef == "" {
			var m map[string]any
			if json.Unmarshal(canon, &m) == nil {
				if id, ok := m["id"].(string); ok {
					wantRef = id
				}
			}
		}
	}
	if wantRef != "" && wantRef != e.Ref {
		res.Problems = append(res.Problems, fmt.Sprintf("mã giao dịch trong lá là %q, không phải %q", e.Ref, wantRef))
	}
	res.Verified = len(res.Problems) == 0
	return res, nil
}

// extractRecord nhận object bản ghi, hoặc nguyên phản hồi của trang minh bạch có trường
// "ban_ghi_chuan_hoa" (apps/cuu-tro), để người dùng lưu thẳng phản hồi rồi kiểm.
func extractRecord(raw []byte) []byte {
	var wrap struct {
		Record json.RawMessage `json:"ban_ghi_chuan_hoa"`
	}
	if json.Unmarshal(raw, &wrap) == nil && len(wrap.Record) > 0 {
		return wrap.Record
	}
	return raw
}

func printText(w io.Writer, r *result) {
	fmt.Fprintf(w, "Sổ cái:        %s\n", r.Origin)
	fmt.Fprintf(w, "Checkpoint:    kích thước %d, root %s (chữ ký hợp lệ)\n", r.TreeSize, r.RootHash)
	fmt.Fprintf(w, "Lá #%d:        type=%s ref=%s sha256=%s\n", r.Index, r.Leaf.Type, r.Leaf.Ref, r.Leaf.SHA256)
	if len(r.Leaf.Attrs) > 0 {
		b, _ := json.Marshal(r.Leaf.Attrs)
		fmt.Fprintf(w, "Thuộc tính:    %s\n", b)
	}
	fmt.Fprintf(w, "Leaf hash:     %s\n", r.LeafHash)
	if r.RecordHash != "" {
		fmt.Fprintf(w, "Bản ghi:       sha256=%s\n", r.RecordHash)
	}
	if r.Verified {
		fmt.Fprintln(w, "KẾT QUẢ:       ĐÃ XÁC MINH (lá nằm trong sổ cái đã ký và khớp bản ghi)")
		return
	}
	fmt.Fprintln(w, "KẾT QUẢ:       KHÔNG KHỚP")
	for _, p := range r.Problems {
		fmt.Fprintln(w, "  -", p)
	}
}
