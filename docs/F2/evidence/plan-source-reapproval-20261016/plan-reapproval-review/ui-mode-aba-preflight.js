// Controlled original context functions only; no HTTP, browser or PostgreSQL.
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const html=fs.readFileSync('src/parkweave/web.html','utf8');
const code=html.match(/function deliveryContext\(\)\{[^\n]+/)[0]+'\n'+html.match(/function deliveryCurrent\(c\)\{[^\n]+/)[0];
const fields={'delivery-case':{value:'case-A'},'delivery-reapproval':{checked:true}},context={resourceContext:()=>({generation:1}),resourceCurrent:()=>true,$:id=>fields[id],combinationSelection:new Map([['h',{id:'hold',resource_revision:1}]])};
vm.createContext(context);vm.runInContext(code,context);const old=context.deliveryContext();fields['delivery-reapproval'].checked=false;const during=context.deliveryCurrent(old);fields['delivery-reapproval'].checked=true;const after=context.deliveryCurrent(old);
process.stdout.write(JSON.stringify({layer:'CONTROLLED_ORIGINAL_CONTEXT_FUNCTIONS_NO_HTTP_BROWSER_PG',source_sha256:crypto.createHash('sha256').update(html).digest('hex'),before:true,during_other_mode:during,after_mode_ABA:after,unresolved_if_after_true:true})+'\n');
