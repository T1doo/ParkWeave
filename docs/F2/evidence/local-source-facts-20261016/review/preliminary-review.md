# Independent preliminary review

Baseline: 41b7342cb0e757a3e17fe795e3d07a5b5b7ddd6b. Read-only source review; root is sole source/Git writer.

Reviewed scripts/local_case_entry_app.py, scripts/local_facts_web.html, Store.assess_facts and related FactInput/Intake/auth/field grants.

No new permission, PREPARE, assignment, approval, credential or model path observed. Recovery endpoint scopes exact owner, park and organization and current READ in READ ONLY transaction; candidate_review is excluded. Existing source decision algorithm is unchanged; receipt additions persist source excerpt, UNVERIFIED and reason-derived next conditions. Output uses textContent. Identity/read generation checks prevent old reads returning across identity changes.

Finding R1 (reported to root): initial page load does not restore pending sessionStorage before enabling POST. Empty session is accepted by front-end and may overwrite old unknown request handle before API rejects. Suggested initial restore/block and nonblank session gating, with reload/unchanged-handle/no-POST test.

Pending: source freeze and actual runtime independent tests.

Follow-up source review: R1 fixed by initial restoring=true, restore(context()) on load, nonblank-session controls/send guards. error() clears prior source status. Root added real Chromium lost-response/reload/unchanged-handle/no-POST test. Requested actual A→B→A held-response and altered fingerprint recovery checks in existing test; no further security-blocking source issue found.
