// Dependency-free interaction checks. Run with node scripts/test_benchmark_index.js.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(tag) { this.tag=tag; this.children=[]; this.events={}; this.attributes={}; this.value=''; this.textContent=''; this.classList={add(){},remove(){}}; }
  append(...items) { this.children.push(...items); if(this.tag==='select'&&this.children.length===items.length)this.value=items[0].value; }
  replaceChildren(...items) { this.children=[]; this.append(...items); }
  setAttribute(key,value) { this.attributes[key]=value; }
  addEventListener(event, fn) { this.events[event]=fn; }
  focus() {} select() {} scrollIntoView() {}
}
const elements = Object.fromEntries(['batch-data','search','filters','rows','status','count','add','reset','group-matching','expand-all','collapse-all'].map(id=>[id,new Element('div')]));
elements['group-matching'].checked=true;
const radios=['antigravity-ide','code'].map(value=>Object.assign(new Element('input'),{value}));
function batch(id,sf,variant,optimization) {
  const metadata={scale_factor:sf,variant,optimization};
  return {id,uid:id,group_id:`sf${sf}`,generated:'2026-10-30T12:00:00+00:00',directory:`/remote/${id}'s batch`,manifest:`batches/${id}/manifest.json`,labels:{baseline:'Baseline',comparison:'Merged'},metadata:{baseline:metadata,comparison:metadata},fields:{baseline:metadata,comparison:metadata},figures:15,queries:['q1.pb'],notices:[],rendering:null,related:[],redundant_of:null};
}
const a=batch('a',2,{materialize_into_join:false},{gco:false});
const b=batch('b',10,{materialize_into_join:true},{gco:true});
const old=batch('old',2,{materialize_into_join:false},{gco:false});
a.generated='2026-10-30T15:00:00+00:00';b.generated='2026-10-30T14:00:00+00:00';
a.related=[{uid:'old',generated:old.generated,id:'old',reason:'Same rendering fingerprint'}];
old.related=[{uid:'a',generated:a.generated,id:'a',reason:'Same rendering fingerprint'}];
old.redundant_of='a';
const fixtures=[a,b,old];
elements['batch-data'].textContent=JSON.stringify(fixtures);
let copied;
const storage=new Map();
function find(root,id){if(root.id===id)return root;for(const child of root.children){const result=find(child,id);if(result)return result;}return null;}
const context=vm.createContext({document:{getElementById:id=>elements[id]||find(elements.rows,id),createElement:tag=>new Element(tag),querySelectorAll:()=>radios},navigator:{clipboard:{writeText:async text=>{copied=text;}}},window:{isSecureContext:true,location:{hash:''}},setTimeout:fn=>fn(),localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)},console});
const html=fs.readFileSync(path.join(__dirname,'benchmark_index.html'),'utf8');
vm.runInContext(html.split('<script>')[1].split('</script>')[0],context);
assert.equal(elements.count.textContent,'3 of 3 batches · 2 configurations');
assert.equal(elements.rows.children.length,2);
assert.equal(elements.rows.children[0].id,'batch-a');
assert.equal(elements.filters.children.length,3);
assert.equal(elements.filters.children[2].children[0].value,'optimization');
const settings=elements.rows.children[0].children[4].children[0];
assert.equal(settings.tag,'ul');
assert.equal(settings.children[0].textContent,'gco: false');
// Each group's newest member represents it; expanding preserves member order.
elements.rows.children[0].children[0].children[0].events.click();
assert.deepEqual(elements.rows.children.map(row=>row.id),['batch-a','batch-old','batch-b']);
elements['collapse-all'].events.click();
assert.equal(elements.rows.children.length,2);
elements['expand-all'].events.click();
assert.equal(elements.rows.children.length,3);
elements['group-matching'].checked=false;elements['group-matching'].events.change();
assert.deepEqual(elements.rows.children.map(row=>row.id),['batch-a','batch-b','batch-old']);
elements['group-matching'].checked=true;elements['group-matching'].events.change();
elements['collapse-all'].events.click();
// Filters select configurations before grouping.
const sf=elements.filters.children[0];
sf.children[1].value=sf.children[1].children.find(option=>option.textContent==='2').value;
sf.children[1].events.change();
assert.equal(elements.count.textContent,'2 of 3 batches · 1 configurations');
elements.search.value='gco'; elements.search.events.input();
assert.equal(elements.count.textContent,'2 of 3 batches · 1 configurations');
elements.search.value='does-not-exist'; elements.search.events.input();
assert.equal(elements.count.textContent,'0 of 3 batches · 0 configurations');
elements.reset.events.click();
// A related-rendering link expands a hidden group member and jumps to it.
const badge=elements.rows.children[0].children[5].children.find(child=>child.className==='rendering-links');
const relatedLink=badge.children[1].children[1].children[0].children[0];
assert.equal(relatedLink.href,'#batch-old');
relatedLink.events.click({preventDefault(){}});
assert.equal(context.window.location.hash,'batch-old');
assert.ok(find(elements.rows,'batch-old'));
const oldBadge=find(elements.rows,'batch-old').children[5].children.find(child=>child.className==='rendering-links redundant');
assert.equal(oldBadge.children[0].textContent,'Redundant');
// Navigation clears conflicting filters rather than leaving a dead link.
elements.search.value='does-not-exist';elements.search.events.input();
vm.runInContext("navigateToBatch('old')",context);
assert.equal(elements.search.value,'');
assert.ok(find(elements.rows,'batch-old'));
// Change editor and verify the copied command stays quoted and uses -n.
radios[1].events.change();
assert.equal(storage.get('benchmark-editor'),'code');
const commandLine=elements.rows.children[0].children[5].children[0];
assert.equal(commandLine.children[0].tag,'input');
const button=commandLine.children[1];
assert.equal(button.className,'copy-button');
assert.match(button.innerHTML,/<svg/);
button.events.click();
setImmediate(()=>{
  assert.equal(copied,"code -n '/remote/a'\\''s batch'");
  assert.match(elements.status.textContent,/Command copied/);
  console.log('Index interactions passed: grouping, chronology, expand/collapse, filters, linked renderings, editor preference and copy');
});
