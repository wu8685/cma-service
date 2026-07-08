package config

import "testing"

func TestLoadDefaults(t *testing.T) {
	t.Setenv("CMA_LISTEN", "")
	t.Setenv("CMA_STATE_FILE", "")
	t.Setenv("CMA_API_KEYS", "")

	c := Load()
	if c.Listen != ":8787" {
		t.Errorf("Listen = %q, want :8787", c.Listen)
	}
	if c.StateFile != "cma-state.json" {
		t.Errorf("StateFile = %q, want cma-state.json", c.StateFile)
	}
	if len(c.APIKeys) != 0 {
		t.Errorf("APIKeys = %v, want empty (allow-all)", c.APIKeys)
	}
}

func TestLoadOverridesAndAPIKeys(t *testing.T) {
	t.Setenv("CMA_LISTEN", "127.0.0.1:18791")
	t.Setenv("CMA_STATE_FILE", "/tmp/state.json")
	t.Setenv("CMA_API_KEYS", "k1, k2 ,, k3")

	c := Load()
	if c.Listen != "127.0.0.1:18791" {
		t.Errorf("Listen = %q", c.Listen)
	}
	if c.StateFile != "/tmp/state.json" {
		t.Errorf("StateFile = %q", c.StateFile)
	}
	for _, k := range []string{"k1", "k2", "k3"} {
		if !c.APIKeys[k] {
			t.Errorf("APIKeys missing %q (blank entries must be skipped)", k)
		}
	}
	if len(c.APIKeys) != 3 {
		t.Errorf("APIKeys = %v, want exactly k1,k2,k3", c.APIKeys)
	}
}
