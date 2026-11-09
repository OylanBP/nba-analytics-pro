/* Verified background snapshots. Missing fields are never inferred. */
(function(){
'use strict';
let pending;
const draftTeams={ATL:"亞特蘭大老鷹",BOS:"波士頓塞爾提克",BKN:"布魯克林籃網",NJ:"紐澤西籃網",CHA:"夏洛特黃蜂",CHI:"芝加哥公牛",CLE:"克里夫蘭騎士",DAL:"達拉斯獨行俠",DEN:"丹佛金塊",DET:"底特律活塞",GS:"金州勇士",HOU:"休士頓火箭",IND:"印第安納溜馬",LAC:"洛杉磯快艇",LAL:"洛杉磯湖人",MEM:"曼菲斯灰熊",MIA:"邁阿密熱火",MIL:"密爾瓦基公鹿",MIN:"明尼蘇達灰狼",NO:"紐奧良鵜鶘",NY:"紐約尼克",OKC:"奧克拉荷馬雷霆",ORL:"奧蘭多魔術",PHI:"費城76人",PHX:"鳳凰城太陽",POR:"波特蘭拓荒者",SAC:"沙加緬度國王",SA:"聖安東尼奧馬刺",TOR:"多倫多暴龍",UTAH:"猶他爵士",WSH:"華盛頓巫師",SEA:"西雅圖超音速"};
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const countries={'USA':'美國','United States':'美國','Canada':'加拿大','France':'法國','Serbia':'塞爾維亞','Greece':'希臘','Slovenia':'斯洛維尼亞','Cameroon':'喀麥隆','Australia':'澳洲','Germany':'德國','Spain':'西班牙','Nigeria':'奈及利亞','Lithuania':'立陶宛','Latvia':'拉脫維亞','Finland':'芬蘭','Japan':'日本','China':'中國','South Sudan':'南蘇丹','Bahamas':'巴哈馬','Democratic Republic of the Congo':'剛果民主共和國','Switzerland':'瑞士','Turkey':'土耳其','Croatia':'克羅埃西亞','Senegal':'塞內加爾','United Kingdom':'英國','New Zealand':'紐西蘭','Belgium':'比利時','Dominican Republic':'多明尼加共和國','Ukraine':'烏克蘭','Brazil':'巴西','Italy':'義大利','Israel':'以色列','Mali':'馬利','Jamaica':'牙買加','Guinea':'幾內亞','Georgia':'喬治亞'};
const awards={'Most Valuable Player':'最有價值球員','NBA Finals Most Valuable Player':'總冠軍賽最有價值球員','Finals MVP':'總冠軍賽最有價值球員','Rookie of the Year':'年度最佳新秀','Defensive Player of the Year':'年度最佳防守球員','Sixth Man of the Year':'年度最佳第六人','Most Improved Player':'年度最佳進步球員','All-NBA 1st Team':'年度第一隊','All-NBA 2nd Team':'年度第二隊','All-NBA 3rd Team':'年度第三隊','All-Defensive 1st Team':'防守第一隊','All-Defensive 2nd Team':'防守第二隊','All-Rookie 1st Team':'新秀第一隊','All-Rookie 2nd Team':'新秀第二隊','All-Star Game Most Valuable Player':'明星賽最有價值球員'};
Object.assign(countries,{"Austria": "奧地利", "Bosnia & Herzegovina": "波士尼亞與赫塞哥維納", "Congo": "剛果", "Czech Republic": "捷克", "Democratic Republic of Congo": "剛果民主共和國", "England": "英格蘭", "Estonia": "愛沙尼亞", "Mexico": "墨西哥", "Netherlands": "荷蘭", "Nicaragua": "尼加拉瓜", "Portugal": "葡萄牙", "Russia": "俄羅斯", "Sweden": "瑞典", "Türkiye": "土耳其"});
Object.assign(awards,{"1st Team AP All-American": "美聯社全美第一隊", "AP Player of the Year": "美聯社年度最佳球員", "All-Star MVP": "明星賽最有價值球員", "Bob Cousy Award": "鮑勃・庫西獎", "Clutch Player of the Year": "年度關鍵時刻球員", "Final Four Most Outstanding Player": "四強賽最傑出球員", "Jerry West Award": "傑瑞・威斯特獎", "Julius Erving Award": "朱利葉斯・厄文獎", "Kareem Abdul-Jabbar Award": "卡里姆・阿布杜爾賈霸獎", "Karl Malone Award": "卡爾・馬龍獎", "MVP": "最有價值球員", "NABC Player of the Year": "全美籃球教練協會年度最佳球員", "NBA Cup All-Tournament Team": "NBA 盃最佳陣容", "NBA Cup MVP": "NBA 盃最有價值球員", "NBA Eastern Conference Finals MVP": "東區決賽最有價值球員", "NBA Western Conference Finals MVP": "西區決賽最有價值球員", "Naismith Award": "奈史密斯獎", "Twyman-Stokes Teammate of the Year Award": "年度最佳隊友獎", "Wooden Award": "伍登獎"});
function draft(value){return typeof value==='string'?value:value?`${value.year} 年，第 ${value.round} 輪、總順位 ${value.pick}（${draftTeams[value.team]||value.team}）`:'未提供';}
function link(url,label){try{if(new URL(url).protocol!=='https:')return '';}catch{return '';}return `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(label)} ↗</a>`;}
async function load(){if(!pending)pending=Promise.all(['biographies','player_stories'].map(async name=>{const r=await fetch(`data/${name}.json`);if(!r.ok)throw Error('background unavailable');return r.json();})).catch(e=>{pending=null;throw e;});return pending;}
async function show(id,container,teamNames){
 container.innerHTML='<p class="muted" role="status">正在讀取球員背景…</p>';
 try{
 const [data,stories]=await load();if(!container.isConnected)return;
 teamNames={...teamNames,'New Jersey Nets':'紐澤西籃網','Seattle SuperSonics':'西雅圖超音速','New Orleans Hornets':'紐奧良黃蜂','Charlotte Bobcats':'夏洛特山貓'};
 const p=data.players[String(id)],story=(stories.players||stories)[String(id)];
 if(!p){container.innerHTML='<h3>身世與籃球旅程</h3><p class="muted">這位球員的可靠背景資料尚未取得。</p>';return;}
 const b=p.birthplace||{},place=[b.city,b.state,countries[b.country]||b.country].filter(Boolean).join('，')||p.birthplace_text;
 const fields=[['出生日期',p.birthday],['出生地',place],['就讀學校（來源記載）',p.college],['NBA 初登場年份',p.debut_year],['NBA 選秀',draft(p.draft)]];
 const history=(p.history||[]).map(h=>`<li><span>${escape(h.seasons.replace('CURRENT','至今'))}</span> ${escape(teamNames[h.team]||h.team)}</li>`).join('');
 const honors=(p.awards||[]).map(a=>`<li>${escape(awards[a.name]||a.name)}${a.seasons?.length?'：'+escape(a.seasons.join('、')):''}</li>`).join('');
 container.innerHTML=`<h3>身世與籃球旅程</h3><dl class="bio-facts">${fields.map(([k,v])=>`<div><dt>${k}</dt><dd>${escape(v||'未提供')}</dd></div>`).join('')}</dl><p class="muted">出生地不等於國籍；學校欄不代表已取得學位。缺漏資料不作推測。</p>${story?`<article class="bio-story"><h4>${escape(story.title)}</h4><p>${escape(story.text)}</p><p>${link(story.source_url,story.source_label)}</p><small>查核日期：${escape(story.checked_on)}</small></article>`:'<p class="muted">家庭與成長故事尚未取得可核實資料。</p>'}${history?`<h4>生涯球隊</h4><ul class="bio-history">${history}</ul>`:''}${honors?`<details><summary>個人獎項紀錄</summary><ul>${honors}</ul></details>`:''}<p class="muted">${link(p.source_url,'ESPN 球員背景來源')}<br>資料更新：${escape(new Date(p.updated_at_utc).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'}))}（台灣時間）</p>`;
 }catch{if(container.isConnected){container.innerHTML='<h3>身世與籃球旅程</h3><p class="muted">背景資料暫時無法讀取，其他球員數據仍可查看。</p><button type="button" class="tab">重新讀取背景</button>';container.querySelector('button').onclick=()=>show(id,container,teamNames);}}
}
window.PlayerBackground={show};
})();
