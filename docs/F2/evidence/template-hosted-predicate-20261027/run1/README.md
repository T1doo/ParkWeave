# One new-runner read-only diagnostic — current Chrome mode rejected

[Run40449861501](https://github.com/T1doo/ParkWeave/actions/runs/40449861501),
workflow run1/attempt1, source `20b423fe6097e9b5c2091d4a556567c36ac1666c`.
The job completed in28s; predicate inspection took0.674s. No dependency/font
download, Chrome/PG/API invocation, business request, credential generation or
system permission change was performed by the diagnostic. Standard CI checkout
and pinned action acquisition are separate from these application counters.

The unique false check is `chrome_not_group_or_other_writable`: the regular,
non-symlink, trusted-owner Chrome binary has mode0777. This violates the existing
`st_mode & 0o022 == 0` requirement. Host/source/closed-profile, fontconfig and
fresh-scratch/cache predicates passed. The diagnostic returns1 for this finding;
its single public JSON and original ZIP were preserved and independently checked.

The image comparison differs from run49; this proves a current environmental
block, **not the historical cause of run49**. No old denied log was retrieved.
This new artifact was obtained through the normal authorized connector and its
827B ZIP matched the official digest in receipt.json. The ZIP has just one member,
the1817B diagnostic.json copied here byte-for-byte. No scripts were executed from it.

Do not chmod, weaken the predicate, disable sandbox, or copy the writable image
binary elsewhere to claim trusted provenance. A trusted environment provider must
supply Chrome meeting the existing static file/permission contract (for example,
trusted owner, regular non-symlink0755 binary). Browser integration remains unrun;
both business activation contracts remain disabled. No automatic repeat job.
