'use strict';
function startAnalytics({getRosters,getStats,teamNamesZh}) {
  const el = id => document.getElementById(id);
  const option = (select,text,value) => select.add(new Option(text,value));
  const time = date => new Date(date).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false});
  const percent = n => (100*n).toFixed(1)+'%';
  function table(id,headers,rows) {
    const host=el(id);
    host.replaceChildren();
    if (!rows.length) {host.textContent='目前沒有符合條件的資料。';return;}
    const t=document.createElement('table');
    const header=t.createTHead().insertRow();
    for (const label of headers) {const th=document.createElement('th');th.textContent=label;header.append(th);}
    const body=t.createTBody();
    for (const row of rows) {const tr=body.insertRow(); for(const val of row) tr.insertCell().textContent=val;}
    host.append(t);
  }
  const rosters=getRosters();
  Promise.all([rosters,getStats()]).then(([r,s])=>{
    const players=new Map();
    for (const team of r.teams) for(const p of team.players) {
      if(s.players[p.id]) players.set(p.id,{name:p.name, team:teamNamesZh[team.name]||team.name,stats:s.players[p.id]});
    }
    function rank() {
      const key=el('rank-stat').value, advanced=['ts','efg'].includes(key);
      const rows=Analytics.leaders([...players.values()],key,Number(el('rank-min').value));
      el('rank-meta').textContent=`${s.season_year-1}–${s.season_year} 例行賽 · 符合條件 ${rows.length} 人 · 快照 ${time(s.updated_at_utc)}`;
      table('rank-table',['名次','球員','目前球隊','出賽','數值'],rows.slice(0,50).map((p,i)=>[i+1,p.name,p.team,p.stats.gp,p.value.toFixed(1)+(advanced?'%':'')]));
    }
    el('rank-stat').onchange=rank;el('rank-min').oninput=rank;rank();
  }).catch(()=>{el('rank-meta').textContent='球員統計快照讀取失敗。';});
  Promise.all([rosters,fetch('./data/games.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();})]).then(([r,data])=>{
    const names=new Map(r.teams.map(t=>[String(t.id),teamNamesZh[t.name]||t.name]));
    for(const [id,name] of names) option(el('hist-team'),name,id);
    const years=[...new Set(data.games.map(g=>g.season))].sort((a,b)=>b-a);
    for(const year of years) option(el('hist-year'),`${year-1}–${year}`,year);
    function history() {
      const team=el('hist-team').value;
      const all=Analytics.history(data.games.filter(g=>g.season===Number(el('hist-year').value)),team);
      const rows=all.slice(-Number(el('hist-window').value));
      const s=Analytics.summary(rows);
      el('hist-meta').textContent=s?`${rows.length} 場 · ${s.wins} 勝 ${rows.length-s.wins} 敗 · 場均得 ${s.scored.toFixed(1)} 分／失 ${s.allowed.toFixed(1)} 分 · 淨得分 ${(s.scored-s.allowed).toFixed(1)}`:'所選賽季尚無完賽資料。';
      const svg=el('trend');svg.replaceChildren();
      if(rows.length) {
        const high=Math.max(...rows.flatMap(g=>[g.scored,g.allowed])) || 1;
        const ns='http://www.w3.org/2000/svg';
        for(const [key,color] of [['scored','#69bfff'],['allowed','#ffb077']]) {
          const line=document.createElementNS(ns,'polyline');
          const points=rows.map((g,i)=>[12+i*576/Math.max(1,rows.length-1),132-120*g[key]/high]);
          for (const [x,y] of points) {const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',x);dot.setAttribute('cy',y);dot.setAttribute('r',2);dot.setAttribute('fill',color);svg.append(dot);}
          line.setAttribute('points',points.map(p=>p.join(',')).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke',color);line.setAttribute('stroke-width',2);svg.append(line);
        }
      }
      table('hist-table',['台灣時間','對手','主客場','得分','失分','結果'],[...rows].reverse().map(g=>[time(g.date),names.get(g.opponent),g.home===team?'主場':'客場',g.scored,g.allowed,g.scored>g.allowed?'勝':'敗']));
    }
    for(const id of ['hist-team','hist-year','hist-window']) el(id).onchange=history;
    history();
    const m=Analytics.model(data.games);
    el('model-meta').textContent=m.count?`歷史回測 ${m.hits}／${m.count} 場命中（${percent(m.hits/m.count)}） · 全猜主隊基準 ${percent(m.homeWins/m.count)} · 布里爾分數 ${m.brier.toFixed(3)}（越低越好）`:'歷史樣本不足，尚無可評估場次。';
    el('game-source').textContent=`來源：ESPN 公開例行賽賽程 · 資料更新於 ${time(data.updated)}（台灣時間）`;
    table('pred-table',['台灣時間','客隊','主隊','客勝機率','主勝機率'],m.picks.slice(0,15).map(g=>[time(g.date),names.get(g.away),names.get(g.home),percent(1-g.p),percent(g.p)]));
  }).catch(()=>{el('hist-meta').textContent=el('model-meta').textContent='比賽快照尚未取得，請稍後重試。';});
}
