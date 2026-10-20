// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"crypto/ed25519"
	"encoding/base64"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"golang.org/x/mod/sumdb/note"
)

// Bí mật do bao-agent-ledger render từ OpenBao vào volume tmpfs (core/openbao/agent-ledger.hcl):
//
//	signing_key  khóa ký checkpoint Ed25519 dạng note ("PRIVATE+KEY+<origin>+<hash>+<base64>"),
//	             secret/core/ledger, sinh MỘT lần bởi scripts/openbao-init.sh. Không bao giờ in ra log.
//	writers      mỗi dòng "<tên dịch vụ> <token>": dịch vụ nội bộ được ghi (auth.go)
const (
	signingKeyFile = "signing_key"
	writersName    = "writers"
)

type keySet struct {
	signer      note.Signer
	verifier    note.Verifier
	verifierKey string
}

func writersFile(dir string) string { return filepath.Join(dir, writersName) }

// waitFile chờ file có nội dung (bao agent render sau khi đăng nhập AppRole).
func waitFile(ctx context.Context, path string, wait time.Duration) ([]byte, error) {
	deadline := time.Now().Add(wait)
	for {
		b, err := os.ReadFile(path)
		if err == nil && len(strings.TrimSpace(string(b))) > 0 {
			return b, nil
		}
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("chưa có %s sau %s. OpenBao đã init/unseal và có khóa ký chưa? Chạy: make bao-init", path, wait)
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(2 * time.Second):
		}
	}
}

func loadKeys(ctx context.Context, dir string, wait time.Duration) (*keySet, error) {
	raw, err := waitFile(ctx, filepath.Join(dir, signingKeyFile), wait)
	if err != nil {
		return nil, err
	}
	if _, err := waitFile(ctx, writersFile(dir), wait); err != nil {
		return nil, err
	}
	return parseSigningKey(strings.TrimSpace(string(raw)))
}

// parseSigningKey dựng signer và suy ra verifier key (khóa công khai) từ khóa ký dạng note.
// Lỗi không bao giờ chứa nội dung khóa.
func parseSigningKey(skey string) (*keySet, error) {
	s, err := note.NewSigner(skey)
	if err != nil {
		return nil, fmt.Errorf("khóa ký checkpoint không hợp lệ: %w", err)
	}
	parts := strings.SplitN(skey, "+", 5)
	if len(parts) != 5 {
		return nil, errors.New("khóa ký checkpoint không đúng dạng note")
	}
	k, err := base64.StdEncoding.DecodeString(parts[4])
	if err != nil || len(k) != 1+ed25519.SeedSize || k[0] != 1 {
		return nil, errors.New("khóa ký checkpoint không phải Ed25519")
	}
	pub := ed25519.NewKeyFromSeed(k[1:]).Public().(ed25519.PublicKey)
	vkey, err := note.NewEd25519VerifierKey(s.Name(), pub)
	if err != nil {
		return nil, err
	}
	v, err := note.NewVerifier(vkey)
	if err != nil {
		return nil, err
	}
	if v.KeyHash() != s.KeyHash() {
		return nil, errors.New("verifier suy ra không khớp khóa ký")
	}
	return &keySet{signer: s, verifier: v, verifierKey: vkey}, nil
}
