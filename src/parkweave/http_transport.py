"""Bounded official HTTPS transport. No environment, redirects or retry.
Live adapter construction requires a persistent LIVE budget, approved in coordinator.
Tests inject MockTransport into the same request/stream code; no sockets.
"""
import httpx
from .intern_adapter import ENDPOINT,ModelBoundaryError

class InternHTTPTransport:
    def __init__(self,transport=None):
        if transport is not None and type(transport) is not httpx.MockTransport:
            raise ModelBoundaryError('UNTRUSTED_TRANSPORT')
        self.transport=transport
    def post(self,payload,token,timeout):
        with httpx.Client(transport=self.transport,timeout=timeout,follow_redirects=False,trust_env=False) as client:
            with client.stream('POST',ENDPOINT,json=payload,headers={'Authorization':'Bearer '+token}) as response:
                chunks=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>65536:raise ModelBoundaryError('RESPONSE_LIMIT')
                    chunks.append(chunk)
                body=b''.join(chunks)
                if response.status_code==200 and token.encode() in body:raise ModelBoundaryError('SECRET_OUTPUT_REJECTED')
                return response.status_code,body
