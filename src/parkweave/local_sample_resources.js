/* Explicit read-only sample configuration; no Case, HOLD or publish operation. */
(function(){
 'use strict';const get=id=>document.getElementById(id),button=get('local-sample-resources-read'),
  status=get('local-sample-resources-status'),items=get('local-sample-resource-items'),token=get('token');
 let epoch=0,busy=false;
 token.addEventListener('input',()=>{epoch++;busy=false;button.disabled=false;items.replaceChildren();status.textContent='';});
 button.onclick=async()=>{
  if(busy)return;busy=true;button.disabled=true;const own=++epoch,session=token.value;
  try{
   const response=await fetch('/api/local-sample/resources',{headers:{Authorization:'Bearer '+session},redirect:'error'});
   const value=await response.json();if(own!==epoch||session!==token.value)return;
   if(!response.ok||value.scope!=='LOCAL_SYNTHETIC_RESOURCE_CONFIGURATION_READ_ONLY'||!Array.isArray(value.items))throw Error('当前账号无法读取样例资源配置。');
   items.replaceChildren();
   for(const row of value.items){const card=document.createElement('article');
    for(const text of [row.name+' · v'+row.revision,'合成容量 '+row.capacity+' · '+row.timezone,
     '开放窗口 '+row.open_from+' — '+row.open_until,'来源：'+JSON.stringify(row.source)]){
     const p=document.createElement('p');p.textContent=text;card.append(p);
    }items.append(card);
   }status.textContent='已读取 '+value.items.length+' 项合成资源配置；未读取企业占位、私有事项或履约。';
  }catch(error){if(own===epoch){items.replaceChildren();status.textContent=error.message;}}
  finally{if(own===epoch){busy=false;button.disabled=false;}}
 };
})();
