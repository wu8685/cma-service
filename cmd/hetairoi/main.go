// Command hetairoi is the event-driven scenario layer: it watches external
// sources (GitHub, CodeHub, workitems) and drives an ahsir agent fleet through
// the official CMA SDK. The CMA API itself is served by ahsir's own facade —
// hetairoi is a pure CMA client + eventbus, never a gateway.
package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"path/filepath"

	"github.com/wu8685/hetairoi/internal/api"
	"github.com/wu8685/hetairoi/internal/config"
	"github.com/wu8685/hetairoi/internal/eventbus"
	"github.com/wu8685/hetairoi/internal/sdkdriver"
)

func main() {
	cfg := config.Load()

	// The eventbus drives ahsir's CMA facade through the official anthropic-sdk-go
	// (exactly as any external CMA client would). CMA_FACADE_URL is required.
	facadeURL := os.Getenv("CMA_FACADE_URL")
	if facadeURL == "" {
		log.Fatalf("CMA_FACADE_URL is required (the ahsir CMA facade base URL, e.g. http://127.0.0.1:18790)")
	}
	driver := sdkdriver.New(facadeURL, os.Getenv("CMA_API_KEY"))

	// Mount the event-bus control plane: POST/GET/DELETE /v1/eventbus/{sources,
	// handlers} let an operator wire event monitoring at runtime; persisted specs
	// are rebuilt here on boot. State/persist dir is derived from CMA_STATE_FILE.
	busDir := filepath.Dir(cfg.StateFile)
	bus := eventbus.New(driver, busDir, 8)
	reg, err := eventbus.NewRegistry(context.Background(), bus, busDir)
	if err != nil {
		log.Fatalf("event bus registry: %v", err)
	}

	srv := api.New(cfg)
	srv.SetEventRegistry(reg)

	log.Printf("hetairoi (eventbus-only) listening on %s (facade=%s)", cfg.Listen, facadeURL)
	if err := http.ListenAndServe(cfg.Listen, srv.Handler()); err != nil {
		log.Fatalf("serve: %v", err)
	}
}
