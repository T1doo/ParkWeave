"""Concrete synthetic API scenario shared by the native business adapter.

This is an explicit test operation, never an automatic product workflow. Every
write has a fresh retained UUID and is dispatched once. A lost response ends the
trial UNKNOWN; executing the object again cannot create a duplicate case. The
private checkpoint is only business evidence, not native acceptance.
"""
import math
import threading
import time
from uuid import uuid4

from .controller import CandidateRefused
from .local_preparation import PreparationWorkspace


class PreparationBusinessTrial:
    def __init__(self, *, seconds=120):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 180:
            raise CandidateRefused('bounded business trial required')
        self.seconds = seconds
        self.state = 'NOT_STARTED'
        self.deadline = self.checkpoint = self.first_workspace = None
        self.keys = ()
        self._lock = threading.Lock()

    def __reduce__(self):
        raise TypeError('business trial cannot be serialized')

    def __copy__(self):
        raise TypeError('business trial cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('business trial cannot be copied')

    def _workspace(self, workspace):
        if type(workspace) is not PreparationWorkspace:
            raise CandidateRefused('original business workspace required')
        workspace.check()
        if self.deadline is None or time.monotonic() >= self.deadline:
            raise CandidateRefused('business trial deadline')
        # Caller must install the same bound before any request. This cannot
        # lengthen the original invocation budget or grant native admission.
        if workspace.deadline is None or workspace.deadline > self.deadline:
            raise CandidateRefused('shared absolute workspace budget required')

    def begin(self):
        """Reserve one scenario before entering any Controller/OS operation."""
        with self._lock:
            if self.state != 'NOT_STARTED':
                raise CandidateRefused('business trial is single use')
            self.state = 'RESERVED'
            self.deadline = time.monotonic() + self.seconds
            return self.deadline

    def create(self, workspace):
        with self._lock:
            if self.state != 'RESERVED':
                raise CandidateRefused('business trial first invocation already consumed')
            self.state = 'UNKNOWN'  # Consume before RNG or any request.
            self._workspace(workspace)
            self.first_workspace = workspace
            self.keys = tuple(str(uuid4()) for _ in range(11))
            keys = iter(self.keys)
            owner, reviewer = workspace.enterprise, workspace.reviewer
            run = owner.submit_case('SYNTHETIC 云端原生验收 资料准备', next(keys))
            owner.wait_run(run)
            ref = owner.create_preparation(run, next(keys))
            ref = owner.add_evidence(ref, next(keys), slot='need_summary',
                text='SYNTHETIC 初稿，待审核补正', source_label='SYNTHETIC 样例一')
            ref = reviewer.request_changes(ref, next(keys), reason='SYNTHETIC 请补齐并修订两个材料槽',
                slots=['need_summary', 'material_outline'])
            ref = owner.add_evidence(ref, next(keys), slot='need_summary',
                text='\u0085SYNTHETIC 修订需求\u0085', source_label='SYNTHETIC 补正二')
            # One requested slot remains unresolved. This is a genuine business
            # state, not a lost-response UNKNOWN or a successful completion.
            if ref.state != 'CHANGES_REQUESTED':
                raise CandidateRefused('remaining requested material must stay unresolved')
            ref = owner.add_evidence(ref, next(keys), slot='material_outline',
                text='\ufeffSYNTHETIC 申请与人员清单\ufeff', source_label='SYNTHETIC 清单一')
            ref = reviewer.review(ref, next(keys), reason='SYNTHETIC 专员复核两个当前材料并解决补正')
            ref = owner.confirm(ref, next(keys), reason='SYNTHETIC 企业确认当前复核材料')
            ref = owner.reopen(ref, next(keys), reason='SYNTHETIC 显式重开已确认材料')
            ref = reviewer.review(ref, next(keys), reason='SYNTHETIC 重开后再次专员复核')
            ref = owner.confirm(ref, next(keys), reason='SYNTHETIC 重开后企业再次确认')
            self.checkpoint = owner.checkpoint(ref)
            view = owner.read(ref)
            expected = ['CREATE', 'ADD_EVIDENCE', 'REQUEST_CHANGES', 'ADD_EVIDENCE',
                        'ADD_EVIDENCE', 'REVIEW', 'CONFIRM', 'REOPEN', 'REVIEW', 'CONFIRM']
            if [event['action'] for event in view['history']] != expected or ref.revision != 10:
                raise CandidateRefused('complete original business history required')
            self.state = 'FIRST_CONFIRMED'

    def reopened(self, workspace):
        with self._lock:
            if self.state != 'FIRST_CONFIRMED':
                raise CandidateRefused('one completed original business invocation required')
            self.state = 'UNKNOWN'
            self._workspace(workspace)
            if workspace is self.first_workspace or self.first_workspace._active:
                raise CandidateRefused('first business workspace must have ended before readback')
            observed = workspace.enterprise.verify_reopened(self.checkpoint)
            self.state = 'EXACT_BUSINESS_READBACK'
            return observed
