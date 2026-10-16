# Recovery UI and native access scope review

Read-only source review, no PostgreSQL execution and no shared edits.

## UI recovery-only entry

Actual observed EXECUTE revocation makes original loadMaterialReuse GET reject and clear the preparation view before original cancellation key recovery becomes reachable. Root authorized a narrow UI routing fix only, not a reuse permission change.

The recovery-only branch must require original preparation GET success, current owner role context, and exact opaque handle preparation ID + Case ID + original owner actor match. Original cancellation GET remains the authority and every existing 403 clearing behavior stays intact. No failed GET may be treated as successful proof. Current generation/token/context checks must survive each await. NOT_OBSERVED retains the original handle and does not unlock new writes. Only original key GET recovery is exposed; no automatic POST.

Candidate initial patch has two issues sent to UI agent/root:
- Match omitted handle Case ID; include it before selecting recovery-only routing.
- Setting prep-decision.hidden=true (or hiding all forms) is sticky because original loadPreparation/clearPreparation never restores this form hidden state. Use a temporary parent readonly class/data attribute and clear it on normal context reset, or restore only states explicitly changed. Do not globally set every form.hidden=false. Verify switching to another authorized ordinary Case restores original form visibility without exposing otherwise hidden forms.

Move routing before unrelated readiness/reuse/facts requests; keep normal no-handle behavior and all original unauthorized-view clearing unchanged.

## Native access scope

Original sd._handoff_enabled excludes isolated adapters but not _native_run_access. NativeRunAccess explicitly treats itself as ordinary PG access. native_run_access_activation requires managed_access=None and writes native_access without changing ordinary successful case.create/run namespace proof. Therefore neither existing managed_access refusal nor ordinary run proof intrinsically rejects native-marked assignments. The new schema33 helper retains that original gate behavior.

No evidence justifies claiming native access was rejected. Adding only an in-memory store attribute check would not enforce a durable source-origin prohibition, since a reconstructed owner Store can omit it. Root recommendation: preserve the original contract and accurately report no native-specific rejection coverage; if native exclusion is separately required it needs an explicit persistent marker policy and bounded tests.
