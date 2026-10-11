# Independent fifth-window findings

**BLOCKED pending action-target UI corrections.** Source manifest `d51af3cccec273588727773f5ab2e8989891b5f9cf11bc20806c8ed87e2f65de`, 405 files, uncommitted product window.

The 30 independent probes passed, including all six actual product failures from the fourth window under their original test IDs. Source drift was zero before and after, exit0. The original failed windows remain failed evidence, and the two independent oracle mistakes also remain preserved.

A separate actual production-callback NodeVM window produced **4 FAIL, exit1**, source drift zero. **MEDIUM AR-UI-003**, `src/parkweave/web.html:534`: controlled-plan responses without top-level Case ID, independent delivery quotes, and approval proposals for Case B incorrectly fell back to residual preparation Case A and blocked B. Conversely, receipt CREATE for preparation A used an existing receipt view for B, allowing A's form through its unknown-request freeze. The minimal correction is to use each command's owned context/preparation mapping and to distinguish receipt CREATE from operations on an existing receipt step. No server guard bypass was observed.

`fifth-full-independent-probes.xml/log/run.json` and `fifth-cross-case-capture.xml/log/run.json` retain all exact IDs and outcomes. Six source/test byte snapshots are retained in `fifth-frozen-source-snapshot.json` and its linked files. Complete new backend/offline modules are NOT RUN independently on this interim source; they will run after the next stable/final freeze. Browser NOT RUN, 0 attempts. No whole repository result is claimed; the unknown historic Case0 cause remains unconfirmed.
