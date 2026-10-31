'use strict';
const Analytics = (() => {
  const num = value => value == null || value === '' || !Number.isFinite(+value) ? null : +value;
  function metric(row, key) {
    if (!['ts', 'efg'].includes(key)) return num(row[key]);
    const fields = key === 'ts' ? ['pts','fga','fta'] : ['fgm','fga','three_pm'];
    const [x,y,z] = fields.map(k => num(row[k]));
    if ([x,y,z].includes(null)) return null;
    const divisor = key === 'ts' ? 2 * (y + 0.44 * z) : y;
    return divisor > 0 ? 100 * (key === 'ts' ? x : x + 0.5 * z) / divisor : null;
  }
  function leaders(players, key, minimum) {
    return players.map(p => ({...p, value:metric(p.stats,key)}))
      .filter(p => num(p.stats.gp) >= Math.max(1, minimum) && p.value !== null)
      .sort((a,b) => b.value-a.value || a.name.localeCompare(b.name));
  }
  function history(games, team) {
    return games.filter(g => g.h != null && [g.home,g.away].includes(team))
      .sort((a,b) => a.date.localeCompare(b.date)).map(g => {
        const home = team === g.home;
        return {...g, opponent:home ? g.away : g.home, scored:home ? g.h : g.a, allowed:home ? g.a : g.h};
      });
  }
  function summary(rows) {
    if (!rows.length) return null;
    const avg = k => rows.reduce((n,r) => n+r[k],0)/rows.length;
    return {scored:avg('scored'), allowed:avg('allowed'), wins:rows.filter(r=>r.scored>r.allowed).length};
  }
  // Freeze ratings throughout each UTC date so simultaneous games cannot leak outcomes.
  function model(games, now = Date.now()) {
    const ratings = new Map(), seen = new Set(), picks = [];
    let lastSeason, hits=0, count=0, loss=0, homeWins=0;
    const days = new Map();
    for (const g of [...games].sort((a,b)=>a.date.localeCompare(b.date))) {
      const day = g.date.slice(0,10);
      if (!days.has(day)) days.set(day,[]);
      days.get(day).push(g);
    }
    for (const group of days.values()) {
      const season = group[0].season;
      if (lastSeason && season !== lastSeason) {
        for (const [team,r] of ratings) ratings.set(team,1500+(r-1500)*0.75);
      }
      lastSeason=season;
      const updates = [];
      for (const g of group) {
        const diff=(ratings.get(g.home)??1500)-(ratings.get(g.away)??1500)+65;
        const p=1/(1+10**(-diff/400));
        if (g.h == null) {
          if (Date.parse(g.date)>now && seen.has(g.home) && seen.has(g.away)) picks.push({...g,p});
          continue;
        }
        const win=Number(g.h>g.a);
        if (seen.has(g.home) && seen.has(g.away)) {
          hits+=Number((p>=0.5)===Boolean(win)); count++; loss+=(p-win)**2; homeWins+=win;
        }
        updates.push([g.home,20*(win-p)], [g.away,20*(p-win)]);
      }
      for (const [team,delta] of updates) {ratings.set(team,(ratings.get(team)??1500)+delta); seen.add(team);}
    }
    return {hits,count,brier:count?loss/count:null,homeWins,picks};
  }
  return {leaders,metric,history,summary,model};
})();
if (typeof module !== 'undefined') module.exports=Analytics;
