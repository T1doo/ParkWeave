"""Executable offline Linux trial planner; no installer or process launcher.

Direction selection and a matching catalog never authorize sensitive actions.
The existing owner reference is deliberately not rendered as a restricted argv.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import native_run_access_preflight as preflight


class PublicHostPlan(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    platform: Literal['linux']
    trial_root: str = Field(pattern=r'^/tmp/parkweave-trial-[a-f0-9]{32}$')
    source_sha: str = Field(pattern=r'^[a-f0-9]{40}$')
    identities: Literal['EXISTING_DISTINCT_IDENTITIES']


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def prepare(spec=None, snapshot=None, host_plan=None):
    report = dict(schema='parkweave-linux-restricted-trial-plan/1', route='LINUX_DIRECT_RESTRICTED_DML',
        status='MISSING_CONFIG', launch_authorized=False, installation_authorized=False,
        activation_enabled=False, production_connected=False, actual_run='NOT_RUN',
        writer_argv=None, writer_runtime='NOT_IMPLEMENTED',
        qualification='OFFLINE_PUBLIC_PLAN_ONLY; no identity/secret/path/permission/source proof',
        pending_actions=[])
    comparison = preflight.analyze(spec, snapshot)
    report['comparison'] = comparison
    if comparison['status'] in ('REFUSED', 'MISSING_CONFIG', 'NOT_CONNECTED'):
        report['status'] = comparison['status']
        return report
    if host_plan is None:
        report['missing'] = ['public_host_plan']
        return report
    try:
        host = PublicHostPlan.model_validate(host_plan)
        config = preflight.InstallationSpec.model_validate(spec)
        policy = config.policy
        if (config.permission_strategy != 'DIRECT_DML' or config.transport != 'LINUX_UNIX' or
                config.api_uid in (None, 0) or config.writer_uid in (None, 0) or
                config.api_uid == config.writer_uid or
                not re.fullmatch(r'fixture_[a-f0-9]{32}', policy.database_name) or
                policy.database_host not in ('127.0.0.1', 'localhost') and
                not policy.database_host.startswith(host.trial_root+'/')):
            raise ValueError('isolated local target required')
        start, end = datetime.fromisoformat(policy.valid_from), datetime.fromisoformat(policy.valid_until)
        if not start <= datetime.now(timezone.utc) < end:
            raise ValueError('current declared interval required; no automatic renewal')
        paths = dict(command=host.trial_root+'/writer/command.sock',
                     verify=host.trial_root+'/writer/verify.sock',
                     private_bootstrap=host.trial_root+'/writer/bootstrap.json',
                     public_pin=host.trial_root+'/host/pin.json')
        if any(len(path.encode()) > 103 for name, path in paths.items() if name in ('command', 'verify')):
            raise ValueError('bounded Unix endpoint declaration required')
        # Public references are hashed, never dereferenced or shown as credentials.
        digest = _digest(dict(spec=config.model_dump(), snapshot=snapshot, host_plan=host.model_dump()))
    except (ValidationError, ValueError, TypeError, AttributeError):
        report.update(status='REFUSED', reason='INVALID_OR_UNSUPPORTED_PUBLIC_TRIAL_INPUT; values not echoed')
        return report
    permissions = []
    for label, action, table, column in preflight.required_privileges(config.parent_lock_column):
        if action == 'LOCK_UPDATE':
            continue  # A technical prerequisite, not a PostgreSQL GRANT verb.
        permissions.append(dict(role=policy.writer_role, action=action, schema='pg_catalog' if action == 'EXECUTE' else 'public',
                                object=table, column=column))
    permissions.extend([
        dict(role=policy.writer_role, action='CONNECT', object=policy.database_name),
        dict(role=policy.writer_role, action='USAGE', object='public'),
    ])
    report.update(status='APPROVAL_REQUIRED', plan_digest=digest, declared_source_sha=host.source_sha,
        declared_paths=paths, intended_uids=dict(api=config.api_uid, writer=config.writer_uid),
        declared_case_scope=dict(source=policy.source.model_dump(), approver_id=policy.approver_id,
            beneficiary_id=policy.beneficiary_id, valid_from=policy.valid_from, valid_until=policy.valid_until),
        writer_permission_requirements=permissions,
        permission_delta=comparison['changes'],
        lock_requirement=dict(table='preparations', technical_update_column=config.parent_lock_column),
        runtime_blocker='Existing owner reference rejects the restricted contract. A separately reviewed private host/runtime adapter is required; no reference argv substitution.',
        pending_actions=[
            dict(action='PROVISION_ISOLATED_TARGET', scope=dict(trial_root=host.trial_root,
                database=policy.database_name), required='Fresh owned UUID database creation proof; identity/OID/system identifier and original source rechecked. No existing or production target.'),
            dict(action='APPROVE_EXACT_STORAGE_AND_ACL_DELTA', required='Only missing reviewed 3-column/3-function/3-trigger storage and required effective writer permissions. No app assignment/control-system rights, broad role, business Grant or automatic overwrite.'),
            dict(action='PROTECT_EXISTING_IDENTITIES_AND_PRIVATE_INPUTS', required='Existing distinct nonroot API/writer identities, protected source/interpreter/parent paths and private policy/key/credential delivery. New identity/credential or mode/owner changes require separately specified approval; no silent creation.'),
            dict(action='START_BIND_AND_RUN_ONCE', required='Approved private runtime adapter under actual writer UID; trusted host observes both endpoint PID/UID/start/inode/device/boot/policy, binds app, and tests one exact ordinary successful synthetic Run/Case within the original UTC interval. No implicit renewal or real model.'),
            dict(action='STOP_AND_REMOVE_OWNED_TRIAL_RESOURCES', required='Stop only observed owned children; remove only the newly created trial database/files by original creation proof. Preserve failed evidence; no production DROP or shared identity removal.'),
        ])
    return report


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            self.exit(4, 'REFUSED: unsupported plan arguments; values not echoed\n')
    parser = Parser(allow_abbrev=False, description='Linux受限DML试运行公共计划；不连接、赋权、改权限或启动。')
    for name in ('spec', 'snapshot', 'host-plan'):
        parser.add_argument('--'+name, type=Path)
    args = parser.parse_args(argv)
    try:
        read = lambda path: json.loads(path.read_text()) if path else None
        report = prepare(read(args.spec), read(args.snapshot), read(args.host_plan))
    except (OSError, ValueError):
        report = dict(status='REFUSED', reason='PUBLIC_INPUT_UNREADABLE_OR_INVALID; values not echoed',
                      launch_authorized=False, installation_authorized=False, activation_enabled=False,
                      production_connected=False, actual_run='NOT_RUN', writer_argv=None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return {'MISSING_CONFIG': 2, 'NOT_CONNECTED': 3, 'REFUSED': 4, 'APPROVAL_REQUIRED': 5}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
