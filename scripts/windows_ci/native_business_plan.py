"""Reviewable operation list. Printing this plan grants or executes nothing."""
import json


def plan():
    from scripts.windows_portable.native_acceptance_issuer import issuer_status
    return dict(schema='parkweave-native-business-approval-plan/1',
        platform='one disposable GitHub-hosted windows-2025 x64 standard runner; never user PC',
        repository='T1doo/ParkWeave', branch='dev/local-product-runtime-20261028',
        job_timeout_minutes=25, execution='one source-bound run; attempt 1; no paid fallback or retries',
        work_seconds=900,cleanup_seconds=60,
        coordinator='existing official runner Python 3.12 x64 with -I -B -S; candidate files/imports remain pinned',
        trial_domain='persistent TRIAL_ONLY root marker; formal acquisition and production issuer refuse it',
        source='must pin reviewed full commit and rebuilt candidate manifest/archive SHA256 before enabling',
        operations=[
            'Read original primary token user/owner/default DACL; derive owned restricted primary token',
            'Set TokenOwner (TokenInformationClass 4) and TokenDefaultDacl (6) ONLY on that derived token',
            'Exclusively create one private RUNNER_TEMP trial subtree with creation-time protected descriptors',
            'Generate two PostgreSQL passwords, six synthetic application tokens and six independent test login passwords',
            'CURRENT_USER DPAPI protect/unprotect in original held files; wrong-entropy refusal',
            'Start fixed hash-pinned initdb with original protected named pipe and owned Job; SCRAM credentials',
            'Create one synthetic PostgreSQL database/application role/schema and single-transaction synthetic seed',
            'Start owned loopback PostgreSQL/API/worker; execute real submit/correct/review/confirm/reopen sequence',
            'Stop owned Jobs, original process-HANDLE signal and Job-zero observation, close held resources',
            'Reopen same installation with fresh composition, verify physical identity and exact business readback',
            'Four registered owned interruption children write ONLY inherited original auxiliary file handles; terminate at fixed stages',
        ],
        secrets='no plaintext secrets in files/logs/argv; original necessary DB connection configuration uses child memory/environment',
        scope_exclusions=['no OS account creation', 'no system ACL/security/privilege changes',
            'no runtime installation', 'no external database adoption', 'no OAuth/new GitHub credentials',
            'no production READY or gate override', 'no main/merge/Release/deploy'],
        cleanup='terminate only original owned Jobs; close only own held resources; retain trial data until runner disposal; '
            'never recursive-delete a path or touch unrelated files; UNKNOWN retained, no retry; '
            'DPAPI may create runner-profile OS keys, never manually remove them',
        publication='source-only normal dev push already authorized; candidate bytes/CI enablement need exact source+hash scope',
        execution_ready=False,
        remaining_source_work=['native target API-set/IAT and complete loaded-module source producers',
            'reviewed minimum-runtime policy and original independent OS identity input',
            'approved exact candidate build/staging in disposable runner; no transfer fallback'],
        source_admission='IMPLEMENTED_DISABLED_WORKFLOW_AND_NULL_RECORD',
        filesystem_scope='process interruption only; no power-loss/directory-durability acceptance',
        acceptance=issuer_status())


if __name__ == '__main__':
    print(json.dumps(plan(), ensure_ascii=False, indent=2))
