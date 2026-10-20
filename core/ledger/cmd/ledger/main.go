// SPDX-License-Identifier: Apache-2.0

// Lệnh ledger: dịch vụ sổ cái minh bạch của lõi (D-007, #28). Nhúng thư viện Tessera (driver POSIX)
// để duy trì một transparency log theo tlog-tiles (C2SP), không chứa nghiệp vụ.
//
//	POST /ledger/entries       thêm một lá (chỉ dịch vụ nội bộ có token ghi, xem auth.go)
//	GET  /ledger/proof/{index} inclusion proof của lá theo checkpoint hiện tại
//	GET  /ledger/checkpoint    checkpoint đã ký (note Ed25519), đọc công khai
//	GET  /ledger/tile/...      tile hash và entry bundle tĩnh theo tlog-tiles, đọc công khai
//	GET  /ledger/verifier      khóa công khai (verifier key) để ai cũng kiểm được chữ ký
//	GET  /healthz              sống + đọc được checkpoint
//
// "ledger healthcheck" gọi /healthz (healthcheck của container, image không có shell).
// Cấu hình qua biến môi trường (LEDGER_*), bí mật đọc từ file do bao agent render (keys.go).
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/transparency-dev/tessera"
	"github.com/transparency-dev/tessera/storage/posix"
	posixas "github.com/transparency-dev/tessera/storage/posix/antispam"
)

type config struct {
	listen         string
	storageDir     string
	antispamDir    string
	secretsDir     string
	secretsWait    time.Duration
	cpInterval     time.Duration
	batchMaxAge    time.Duration
	batchMaxSize   uint
	antispamMemory uint
	persistentAS   bool
	awaitTimeout   time.Duration
}

func env(name, def string) string {
	if v, ok := os.LookupEnv(name); ok && v != "" {
		return v
	}
	return def
}

func envDuration(name string, def time.Duration) time.Duration {
	d, err := time.ParseDuration(env(name, def.String()))
	if err != nil {
		slog.Error("biến môi trường không hợp lệ", "ten", name, "loi", err)
		os.Exit(2)
	}
	return d
}

func envUint(name string, def uint) uint {
	n, err := strconv.ParseUint(env(name, strconv.FormatUint(uint64(def), 10)), 10, 32)
	if err != nil {
		slog.Error("biến môi trường không hợp lệ", "ten", name, "loi", err)
		os.Exit(2)
	}
	return uint(n)
}

func loadConfig() config {
	return config{
		listen:      env("LEDGER_LISTEN", ":8090"),
		storageDir:  env("LEDGER_STORAGE_DIR", "/data/log"),
		antispamDir: env("LEDGER_ANTISPAM_DIR", "/data/antispam"),
		secretsDir:  env("LEDGER_SECRETS_DIR", "/run/secrets/dxos"),
		secretsWait: envDuration("LEDGER_SECRETS_WAIT", 120*time.Second),
		// Checkpoint ký lại tối đa mỗi giây khi có lá mới: lá mới có proof sau ~1 giây
		cpInterval:   envDuration("LEDGER_CHECKPOINT_INTERVAL", time.Second),
		batchMaxAge:  envDuration("LEDGER_BATCH_MAX_AGE", 200*time.Millisecond),
		batchMaxSize: envUint("LEDGER_BATCH_MAX_SIZE", 64),
		// Bộ nhớ chống trùng trong RAM (mỗi mục ~40 byte); chống trùng bền vững dùng BadgerDB
		antispamMemory: envUint("LEDGER_ANTISPAM_MEMORY_ENTRIES", 4096),
		persistentAS:   env("LEDGER_ANTISPAM_PERSISTENT", "true") == "true",
		awaitTimeout:   envDuration("LEDGER_AWAIT_TIMEOUT", 15*time.Second),
	}
}

func main() {
	slog.SetDefault(slog.New(slog.NewTextHandler(os.Stdout, nil)))
	cfg := loadConfig()
	if len(os.Args) > 1 && os.Args[1] == "healthcheck" {
		os.Exit(healthcheck(cfg.listen))
	}
	if err := run(cfg); err != nil {
		slog.Error("ledger dừng", "loi", err)
		os.Exit(1)
	}
}

func run(cfg config) error {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	keys, err := loadKeys(ctx, cfg.secretsDir, cfg.secretsWait)
	if err != nil {
		return err
	}
	slog.Info("khóa ký checkpoint đã nạp", "origin", keys.signer.Name(), "verifier", keys.verifierKey)

	lg, err := openLog(ctx, cfg, keys)
	if err != nil {
		return err
	}
	srv := &http.Server{
		Addr:              cfg.listen,
		Handler:           newServer(lg, keys, writersFile(cfg.secretsDir)).routes(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      cfg.awaitTimeout + 10*time.Second,
		IdleTimeout:       60 * time.Second,
	}
	errc := make(chan error, 1)
	go func() {
		slog.Info("ledger lắng nghe", "dia_chi", cfg.listen, "luu_tru", cfg.storageDir)
		errc <- srv.ListenAndServe()
	}()
	select {
	case err := <-errc:
		_ = lg.shutdown(context.Background())
		return err
	case <-ctx.Done():
	}
	slog.Info("nhận tín hiệu dừng: chờ ghi xong lô đang mở")
	shCtx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	_ = srv.Shutdown(shCtx)
	return lg.shutdown(shCtx)
}

// ledgerLog gom các phần của Tessera mà server dùng.
type ledgerLog struct {
	appender *tessera.Appender
	reader   tessera.LogReader
	awaiter  *tessera.PublicationAwaiter
	shutdown func(context.Context) error
	timeout  time.Duration
	// storageDir: thư mục gốc của log (checkpoint, tile/), phục vụ đọc tĩnh
	storageDir string
}

func openLog(ctx context.Context, cfg config, keys *keySet) (*ledgerLog, error) {
	if err := os.MkdirAll(cfg.storageDir, 0o755); err != nil {
		return nil, fmt.Errorf("tạo thư mục lưu trữ: %w", err)
	}
	driver, err := posix.New(ctx, posix.Config{Path: cfg.storageDir})
	if err != nil {
		return nil, fmt.Errorf("driver POSIX: %w", err)
	}
	var as tessera.Antispam
	if cfg.persistentAS {
		// Chống trùng bền vững: cùng một lá (cùng bytes) gửi lại sau khi khởi động lại vẫn trả index cũ
		a, err := posixas.NewAntispam(ctx, cfg.antispamDir, posixas.AntispamOpts{})
		if err != nil {
			return nil, fmt.Errorf("antispam BadgerDB: %w", err)
		}
		as = a
	}
	opts := tessera.NewAppendOptions().
		WithCheckpointSigner(keys.signer).
		WithCheckpointInterval(cfg.cpInterval).
		WithBatching(cfg.batchMaxSize, cfg.batchMaxAge).
		WithAntispam(cfg.antispamMemory, as)
	appender, shutdown, reader, err := tessera.NewAppender(ctx, driver, opts)
	if err != nil {
		return nil, fmt.Errorf("khởi tạo appender Tessera: %w", err)
	}
	return &ledgerLog{
		appender:   appender,
		reader:     reader,
		awaiter:    tessera.NewPublicationAwaiter(ctx, reader.ReadCheckpoint, 100*time.Millisecond),
		shutdown:   shutdown,
		timeout:    cfg.awaitTimeout,
		storageDir: cfg.storageDir,
	}, nil
}

func healthcheck(listen string) int {
	_, port, err := net.SplitHostPort(listen)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	c := &http.Client{Timeout: 3 * time.Second}
	r, err := c.Get("http://127.0.0.1:" + port + "/healthz")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	defer r.Body.Close()
	if r.StatusCode != http.StatusOK {
		fmt.Fprintln(os.Stderr, "healthz:", r.Status)
		return 1
	}
	return 0
}

var errNotYet = errors.New("lá chưa nằm trong checkpoint hiện tại")
