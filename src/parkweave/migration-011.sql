-- Single-resource local synthetic confirmation; no external reservation.
ALTER TABLE synthetic_resource_holds DROP CONSTRAINT synthetic_resource_holds_state_check;
ALTER TABLE synthetic_resource_holds ADD CONSTRAINT synthetic_resource_holds_state_check CHECK(state IN ('HELD','CONFIRMED','RELEASED'));
ALTER TABLE synthetic_resource_receipts DROP CONSTRAINT synthetic_resource_receipts_action_check;
ALTER TABLE synthetic_resource_receipts ADD CONSTRAINT synthetic_resource_receipts_action_check CHECK(action IN ('HOLD','CONFIRM','RELEASE'));
INSERT INTO schema_version VALUES(11) ON CONFLICT DO NOTHING;
