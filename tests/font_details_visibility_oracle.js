'use strict';
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const text=[];
function element(tag,id,parent,open=false){
 const e={tagName:tag.toUpperCase(),id,parentElement:parent,children:[],open,
  contains(other){for(let p=other;p;p=p.parentElement)if(p===this)return true;return false;}};
 if(parent)parent.children.push(e);return e;
}
function words(e,value){text.push({data:value,parentElement:e});}
const body=element('body','',null);words(element('h1','visible-heading',body),'当前页面');
const outer=element('details','outer',body,input.mode==='opened'||input.mode==='inner_closed');
if(input.mode!=='no_summary'){
 const summary=element('summary','first-summary',outer);words(element('span','first-summary-span',summary),'来源证明');
}
words(element('p','hidden-or-open-content',outer),'事前历史可比较范围');
if(input.mode==='second_summary')words(element('summary','second-summary',outer),'第二摘要仍是折叠内容');
if(input.mode==='outer_closed'||input.mode==='inner_closed'){
 const inner=element('details','inner',outer,input.mode==='outer_closed');
 const summary=element('summary','inner-summary',inner);words(element('span','inner-summary-span',summary),'内部摘要');
 words(element('p','inner-content',inner),'内部来源正文');
}
global.document={body,createTreeWalker(){let n=0;return {nextNode(){return text[n++]||null;}};},createRange(){return {selectNodeContents(){},getClientRects(){return [{width:100,height:20,top:10,bottom:30,left:10,right:110}];}};}};
global.NodeFilter={SHOW_TEXT:4};global.CSS={escape:x=>x};global.innerWidth=1200;global.innerHeight=1000;
global.getComputedStyle=()=>({visibility:'visible',opacity:'1'});
const rows=eval('('+input.source+')')();
process.stdout.write(JSON.stringify(rows.map(x=>x.selector))+'\n');
