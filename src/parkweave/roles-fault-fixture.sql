-- Optional, synthetic test database ONLY. API and worker both require
-- PARKWEAVE_MODE=FAULT_INJECTION; no external credentials or network calls.
GRANT SELECT,INSERT,UPDATE ON fixture_effects TO parkweave_app;
