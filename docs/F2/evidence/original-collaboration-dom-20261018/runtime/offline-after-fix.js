// Bounded offline diagnostic only: same old mock/page, no business API replies.
const fs=require('fs');
const filename=process.argv[2],source=fs.readFileSync(filename,'utf8');
const prefix=source.slice(0,source.indexOf('(async()=>{'));
if(!prefix||prefix.length===source.length)throw Error('expected original harness boundary');
const suffix=`
const diagnosticPage=page('src/parkweave/web.html');let observed=null;
try{diagnosticPage.read('beginCaseWorklistEntry()');}catch(error){observed={name:error.name,message:error.message,stack:error.stack};}
console.log(JSON.stringify({kind:'OFFLINE_AFTER_FIX_DIAGNOSTIC',observed,backend_calls:calls.length,production_functions_replaced:0}));
lines.close();process.exit(observed===null&&calls.length===0?0:1);
`;
new Function('require','process',prefix+suffix)(require,process);
