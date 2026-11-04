/* Non-secret original-request handles only. No bearer, password or material. */
(function(root){
 'use strict';
 const schema='parkweave-local-pending/1';
 const digest=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
 const actorOK=a=>a&&Object.keys(a).sort().join(',')==='id,org_id,park_id,role'&&Object.values(a).every(x=>typeof x==='string'&&x.length>0&&x.length<=128);
 const fixedPath=p=>typeof p==='string'&&(/^\/api\/(runs|preparations)$/.test(p)||/^\/api\/preparations\/[a-f0-9-]{36}\/commands$/.test(p));
 function journal(storage,installation,actor,credentialHash,locks){
  if(!digest(installation)||!actorOK(actor)||!digest(credentialHash))throw new Error('原身份绑定不可用');
  if(!locks||typeof locks.request!=='function')throw new Error('浏览器不支持原请求互斥存储，写操作已暂停');
  const key=schema+':'+installation+':'+actor.id;
  const read=()=>{
   const raw=storage.getItem(key);if(raw===null)return null;
   if(raw.length>4096)throw new Error('待核对请求记录不可读，写操作已暂停');
   const value=JSON.parse(raw);
   if(!value||Object.keys(value).sort().join(',')!=='action,actor,credential_sha256,expected_revision,fingerprint,installation_id,path,request_key,schema'
    ||value.schema!==schema||value.installation_id!==installation||!actorOK(value.actor)
    ||Object.keys(actor).some(k=>actor[k]!==value.actor[k])||!digest(value.credential_sha256)
    ||!fixedPath(value.path)||typeof value.action!=='string'||!['CREATE_RUN','CREATE_PREPARATION','ADD_EVIDENCE','REQUEST_CHANGES','REVIEW','CONFIRM','REOPEN'].includes(value.action)
    ||!Number.isInteger(value.expected_revision)||value.expected_revision<0
    ||typeof value.request_key!=='string'||!/^[-a-f0-9]{36}$/.test(value.request_key)
    ||!digest(value.fingerprint))throw new Error('原请求句柄绑定不完整，写操作已暂停');
   return value;
  };
  return {
   key,read,
   async prepare(path,requestKey,action,revision,fingerprint,guard){
    if(typeof guard!=='function')throw new Error('原提交身份核对不可用');
    return locks.request(key,{mode:'exclusive'},()=>{
     guard();
     if(read())throw new Error('仍有原请求待核对，不会创建新请求键');
     const value={schema,installation_id:installation,actor:{...actor},credential_sha256:credentialHash,
      path,request_key:requestKey,action,expected_revision:revision,fingerprint};
     storage.setItem(key,JSON.stringify(value));
     const observed=read();if(JSON.stringify(observed)!==JSON.stringify(value))throw new Error('原请求句柄保存未确认，未发送请求');
     return value;
    });
   },
   async settle(original){
    return locks.request(key,{mode:'exclusive'},()=>{
     const observed=read();
     if(!observed||JSON.stringify(observed)!==JSON.stringify(original))throw new Error('待核对请求发生变化，保持暂停');
     storage.removeItem(key);
     if(read()!==null)throw new Error('原请求句柄移除未确认，保持暂停');
    });
   }
  };
 }
 const api={journal};
 root.ParkWeavePending=api;
 if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
