const test=require('node:test'), assert=require('node:assert/strict');
const {leaders,metric,history,summary,model}=require('../analytics.js');
const games=[['01',90,100],['02',105,97],['03',null,null]].map(([d,h,a])=>({date:'2025-01-'+d+'T12:00Z',home:'1',away:'2',season:2025,h,a}));
test('v1.1 出賽門檻、缺值與排序',()=>assert.deepEqual(leaders([['a',1,90],['b',2,15],['c',3,20],['d',4,null]].map(([name,gp,pts])=>({name,stats:{gp,pts}})),'pts',2).map(p=>p.name),['c','b']));
test('v1.2 真實與有效命中率',()=>{assert.equal(metric({pts:20,fga:10,fta:0},'ts'),100);assert.equal(metric({fgm:5,fga:10,three_pm:2},'efg'),60);assert.equal(metric({pts:0,fga:0,fta:0},'ts'),null);assert.equal(metric({fga:4},'efg'),null)});
test('v1.3 時序與完賽篩選',()=>assert.deepEqual(history([...games].reverse(),'2').map(r=>r.scored),[100,97]));
test('v1.4 場均得失分',()=>assert.deepEqual(summary(history(games,'2')),{scored:98.5,allowed:97.5,wins:1}));
test('v1.5 最近一場與空樣本',()=>{assert.equal(history(games,'1').at(-1).scored,105);assert.equal(summary([]),null)});
test('v2.0 逐日回測、暖機與未來賽程',()=>{const r=model(games,0);assert.equal(r.count,1);assert.equal(r.hits,1);assert.equal(r.picks.length,1);assert.ok(r.brier>0 && r.brier<0.25);assert.equal(model(games,Date.now()).picks.length,0);assert.equal(model([games[0],{...games[1],date:games[0].date}]).count,0)});
