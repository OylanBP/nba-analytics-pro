const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const script=fs.readFileSync('biographies.js','utf8');
function setup(fetch){const context={window:{},URL,fetch};vm.runInNewContext(script,context);return context.window.PlayerBackground;}
const player={birthday:'1995-01-01',birthplace:{country:'France'},draft:{year:2014,round:2,pick:41,team:'DEN'},history:[{team:'Denver Nuggets',seasons:'2014-CURRENT'}],source_url:'https://www.espn.com/nba/player/bio/_/id/1',updated_at_utc:'2026-11-09T00:00:00Z'};
test('verified fields render translated teams, overall pick and escaped story text',async()=>{
 const api=setup(async url=>({ok:true,json:async()=>url.includes('biographies')?{players:{1:player}}:{1:{title:'<script>bad</script>',text:'hello',source_url:'javascript:alert(1)',checked_on:'2026-11-09'}}}));
 const el={isConnected:true};await api.show(1,el,{'Denver Nuggets':'丹佛金塊'});
 assert.match(el.innerHTML,/丹佛金塊/);assert.match(el.innerHTML,/總順位 41/);assert.match(el.innerHTML,/法國/);
 assert.match(el.innerHTML,/&lt;script&gt;/);assert.doesNotMatch(el.innerHTML,/<script>|javascript:/);
 assert.match(el.innerHTML,/未提供/);
});
test('switching profiles cannot overwrite detached previous profile',async()=>{
 let release;const gate=new Promise(r=>release=r);
 const api=setup(async()=>{await gate;return {ok:true,json:async()=>({players:{1:player}})};});
 const el={isConnected:true};const task=api.show(1,el,{});el.isConnected=false;release();await task;
 assert.doesNotMatch(el.innerHTML,/出生日期/);
});
test('missing player does not borrow another player biography',async()=>{
 const api=setup(async()=>({ok:true,json:async()=>({players:{1:player}})}));
 const el={isConnected:true};await api.show(2,el,{});assert.match(el.innerHTML,/尚未取得/);assert.doesNotMatch(el.innerHTML,/1995/);
});
