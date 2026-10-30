"""Concrete native cluster orchestration with protected initdb transport."""
import time

from .cluster_processes import FixedClusterProcesses, ClusterStartFailure
from .controller import CandidateRefused
from .processes import Command, PrivateProcessAdapter
from .native_instance_security import NativeClusterPrerequisites,NativeFixedStoreSecurity


class NativeProtectedClusterProcesses(FixedClusterProcesses):
    def __init__(self,prerequisites,**pins):
        if type(prerequisites) is not NativeClusterPrerequisites:
            raise CandidateRefused('exact native cluster prerequisites required')
        super().__init__(prerequisites,**pins)
        self.endpoint=None;self._adapters={}

    def _require_data_directory(self,lease,inputs):
        # PG's DOS command path differs from the lease's volume-GUID path.
        # Only the original held PGDATA/security binding may authorize it.
        if self.lease is not lease or type(self.prerequisites.security) is not NativeFixedStoreSecurity:
            raise CandidateRefused('same original native PGDATA binding required')
        self.prerequisites.security.require_inputs(lease,inputs)

    def require_bound_inputs(self,lease,inputs,security):
        if (type(security) is not NativeFixedStoreSecurity or security is not self.prerequisites.security
                or self.lease is not lease or self.inputs is not inputs):
            raise CandidateRefused('same original native cluster inputs required')
        security.require_inputs(lease,inputs)

    def _register_adapter(self,adapter,register):
        def record(token):
            if id(token) in self._adapters:
                raise CandidateRefused('distinct original cluster ownership required')
            self._adapters[id(token)]=adapter
            self._record(register)(token)
        return record

    def _run(self,mode,lease,credentials,register):
        if self.mode is not None or self.failed or not callable(register) or lease.status()!='CLUSTER':
            raise CandidateRefused('single original native cluster attempt required')
        self.mode,self.lease=mode,lease
        deadline=time.monotonic()+30;phase='CONFIGURATION'
        try:
            self.inputs,port=self._configuration(lease,credentials,deadline)
            if mode=='NEW':
                phase='PROTECTED_INITDB'
                self.prerequisites.initialize_protected(lease,self.inputs,self.initdb,
                    lambda adapter,token:self._register_adapter(adapter,register)(token),deadline-5)
            phase='SERVER_INPUTS'
            self._time(deadline,5)
            self.prerequisites.before_server(lease,self.inputs,mode,deadline)
            command=Command(self.postgres.relative_executable,self.postgres.sha256,self.postgres.size,
                ('-D',self.inputs.data_directory,'-h','127.0.0.1','-p',port,'-c','unix_socket_directories=',
                 '-c','ssl=off','-c','logging_collector=off','-c','log_statement=none'),'WINDOWS_JOB')
            self.adapter=PrivateProcessAdapter(lease,{'postgres':command})
            phase='SERVER_START'
            token=self.adapter.launch('postgres',self._register_adapter(self.adapter,register))
            identity=self.adapter.live_identity(token)
            phase='OWNED_DATABASE_ENDPOINT'
            self.prerequisites.server_ready(lease,self.inputs,self.adapter,token,deadline-3)
            if self.adapter.live_identity(token)!=identity:
                raise CandidateRefused('original postgres creation changed')
            self.endpoint=self.prerequisites.security.endpoint
            return self.inputs
        except BaseException as error:
            self.failed=True
            raise ClusterStartFailure(phase,error,None) from error

    def stop_owned(self,token):
        row=self._owned.get(id(token));adapter=self._adapters.get(id(token))
        if row is None or row[0] is not token or adapter is None:
            raise CandidateRefused('original native cluster capability required')
        if row[1]:return True
        if row[2]:return False
        row[2]=True
        try:
            if adapter.stop_owned(token) is not True:self.failed=True;return False
            row[1]=True
            return True
        except BaseException:self.failed=True;raise
