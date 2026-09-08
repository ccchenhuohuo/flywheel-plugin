"""Readable business report plus local, searchable execution/evidence views."""
import html
import json
from collections import Counter
from acceptance_core import read, write

STATE={'complete':'完整执行','limited':'执行完成但存在证据限制','incomplete':'未完成'}
VERDICT={'pass':'放行','qualified':'有保留放行','reject':'建议打回受影响范围','undetermined':'尚不能整体放行'}


def display_count(value):return '待重建' if value is None else str(value)


def render(run):
    v=read(run.path/'validation.json');m=run.manifest
    content=read(run.path/'report-content.json') if (run.path/'report-content.json').exists() else {'summary':['尚未形成业务结论，请按待办补足调查与证据。'],'findings':[]}
    lines=[f"# {m['data_month']} 大盘数据验收",'',f"运行 `{m['run_id']}` · 方法 {m['method_version']} · {STATE[v['execution_state']]} · **{VERDICT[v['business_verdict']]}**",'']
    lines += ['- '+s for s in content['summary']]
    lines += ['', '## 本次看了什么', '',f"范围：{'、'.join(m['sites'])}；各国自配置起点至 {m['data_month']}，国家与标准类目 L1–L3，SPU 数量、固定价格带、销量和本币销售额。中国合并淘宝与天猫；不同国家金额不汇总。"]
    lines += ['',f"基础任务 {v['baseline_jobs']['verified']}/{v['baseline_jobs']['expected']} 通过独立复核；候选 {display_count(v['candidates']['disposed'])}/{display_count(v['candidates']['expected'])} 均关联处理状态（包括待补证，不等同完成根因核实）；稳定语义抽样 {display_count(v['semantic_sample']['reviewed'])}/{display_count(v['semantic_sample']['expected'])} 有核验记录。"]
    if content.get('normal_scope'):lines += ['', '已检查且未见规则信号的范围：'+content['normal_scope']]
    for i,f in enumerate(content.get('findings',[]),1):
        lines += ['',f"## {i}. {f['title']}",'',f"**范围：**{f['scope']}",'']
        lines += f['facts'] if isinstance(f['facts'],list) else [f['facts']]
        lines += ['', '**证据及反证：**'+f['counterevidence'],'','**判断：**'+f['assessment'],'','**行动：**'+f['action']]
        refs=[]
        for eid in f['evidence_ids']:
            run.get_evidence(eid)
            refs.append(f'[{eid[-8:]}](evidence/{eid}.json)')
        lines += ['', '可复核证据：'+'、'.join(refs)+f"。关联候选 {len(f.get('candidate_ids',[]))} 个。"]
    lines += ['', '## 限制与使用边界', '', '数据源为服务商原始宽表和公司标准类目代理；价格与销售额属于估算。贡献分解仅定位变化，不能单独证明原因。没有记录的月份不视为零。']
    if content.get('limitations'):lines += ['',*['- '+s for s in content['limitations']]]
    counts=Counter(x.split(':')[0] for x in v['limitations'])
    for key,n in counts.items():
        if key=='candidate_needs_evidence':lines += [f'- {n} 个候选仍需补证，未按“正常”关闭。']
        elif key=='sample_external_verification_pending':lines += ['- 部分语义抽样尚缺独立平台或经营证据。']
        else:lines += ['- '+key]
    if v['errors']:lines += ['', '尚未完成的执行事项：',*['- '+e for e in v['errors']]]
    lines += ['', '指纹复核只能发现已观测聚合值变化，不能提供事务快照保证。治理发布版本与已验收上游还须对应核对。', '', '[执行与证据看板](audit.html) · [机器核验结果](validation.json) · [冻结任务计划](plan.json)', '']
    (run.path/'报告.md').write_text('\n'.join(lines))
    dashboard(run,v,content)
    run.event('report.rendered',findings=len(content.get('findings',[])),execution_state=v['execution_state'])


def dashboard(run,v,content):
    jobs=read(run.path/'plan.json')['jobs'] if (run.path/'plan.json').exists() else []
    candidates=read(run.path/'candidates.json') if (run.path/'candidates.json').exists() else []
    dispositions=run.dispositions()
    # Store a grouped decision once; repeating its candidate IDs per row is quadratic.
    decisions={d['decision_id']:{**{k:val for k,val in d.items() if k!='candidate_ids'},'candidate_count':len(d['candidate_ids'])} for d in dispositions.values()}
    reviews={}
    if (run.path/'sample-reviews.json').exists():
        for review in read(run.path/'sample-reviews.json'):
            for sid in review['sample_ids']:reviews[sid]={k:val for k,val in review.items() if k!='sample_ids'}
    data={'validation':v,'decisions':decisions,'jobs':[{**{k:j[k] for k in ['job_id','family','site','level','entity','year','lag'] if k in j},'record':run.job_record(j['job_id'])} for j in jobs],
        'candidates':[{**c,'decision_id':dispositions.get(c['candidate_id'],{}).get('decision_id')} for c in candidates],
        'samples':[{**s,'review':reviews.get(s['sample_id'])} for s in (read(run.path/'samples.json') if (run.path/'samples.json').exists() else [])],
        'events':[json.loads(line) for line in run.events_path.read_text().splitlines()],
        'checks':read(run.path/'checks.json') if (run.path/'checks.json').exists() else [],'summary':content['summary']}
    embedded=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    page=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>验收执行与证据</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#182335;font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}header,main{max-width:1300px;margin:auto;padding:28px}header{padding-bottom:8px}h1{font-size:30px;margin:0}h2{font-size:20px}a{color:#1261aa}.muted{color:#56657a}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card,section{background:white;border:1px solid #dae1e9;border-radius:12px;padding:18px;margin-bottom:18px}.big{font-size:28px;font-weight:700}.tabs{display:flex;gap:10px;flex-wrap:wrap}button,select,input{font:inherit;border:1px solid #b5c2d3;border-radius:7px;padding:7px 12px;background:white}button{cursor:pointer}button.active{background:#163d67;color:white}input{min-width:330px;max-width:100%}.row{display:flex;gap:14px;align-items:center;flex-wrap:wrap}table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #e0e6ed}th{background:#f6f8fb;position:sticky;top:0}pre{white-space:pre-wrap;word-break:break-word;font-size:12px;max-height:500px;overflow:auto}details{max-width:820px}summary{cursor:pointer}.tablewrap{overflow:auto;max-height:680px}.badge{display:inline-block;background:#edf3fa;padding:1px 8px;border-radius:10px}.warn{color:#9b4208}.error{color:#ab2435}.pager{margin:16px 0}@media(max-width:780px){header,main{padding:15px}.metrics{grid-template-columns:repeat(2,1fr)}input{min-width:240px}td,th{padding:7px}}@media print{.tabs,.filters,.pager{display:none}.tablewrap{max-height:none}}</style>
<header><p class="muted">MONTHLY ACCEPTANCE · 可观测的执行记录</p><h1>从验收结论追到每一次查询</h1><p id="identity" class="muted"></p></header><main><div class="metrics" id="metrics"></div><section><h2>本次结果</h2><ul id="summary"></ul><p><a href="报告.md">业务报告</a> · <a href="validation.json">独立核验</a> · <a href="run.json">冻结口径</a> · <a href="events.jsonl">全部事件</a></p><details><summary>执行缺口与证据限制</summary><pre id="limits"></pre></details></section><section><div class="tabs" id="tabs"></div><p class="muted">完整记录均可筛选；每页 50 条仅用于展示，不改变扫描或候选范围。金额保留原币，不跨国相加。</p><div class="row filters"><input id="search" placeholder="查国家、类目、月份、候选或错误"><select id="country"><option value="">所有国家</option><option>cn</option><option>US</option><option>DE</option><option>JP</option></select><button id="reset">清空</button></div><div class="pager row"><button id="prev">上一页</button><span id="count"></span><button id="next">下一页</button></div><div class="tablewrap"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div></section></main><script id="data" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('data').textContent),V=D.validation;let tab='jobs',page=0;const $=s=>document.getElementById(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
$('identity').textContent=V.run_id+' · '+V.execution_state+' · '+V.business_verdict;
const metrics=[['基础任务',V.baseline_jobs.verified+'/'+V.baseline_jobs.expected],['候选登记',(V.candidates.disposed??'待重建')+'/'+(V.candidates.expected??'待重建')],['语义抽样',(V.semantic_sample.reviewed??'待重建')+'/'+(V.semantic_sample.expected??'待重建')],['原始证据',V.evidence_count]];
$('metrics').innerHTML=metrics.map(([k,v])=>'<div class="card"><div class="muted">'+esc(k)+'</div><div class="big">'+esc(v)+'</div></div>').join('');$('summary').innerHTML=D.summary.map(s=>'<li>'+esc(s)+'</li>').join('');$('limits').textContent=JSON.stringify({errors:V.errors,limitations:V.limitations},null,2);
const labels={jobs:'任务与分页',candidates:'候选与判断',checks:'覆盖矩阵',samples:'语义样本',events:'实际行为轨迹'};
$('tabs').innerHTML=Object.entries(labels).map(([k,v])=>'<button data-tab="'+k+'">'+v+'</button>').join('');$('tabs').onclick=e=>{if(e.target.dataset.tab){tab=e.target.dataset.tab;page=0;draw()}};
function detail(r){const decision=D.decisions[r.decision_id];let links=[];for(const id of new Set([...(r.evidence_ids||r.record?.evidence_ids||[]),...(decision?.evidence_ids||[]),...(r.review?.evidence_ids||[])])){if(/^ev-[a-f0-9]{32}$/.test(id))links.push('<a href="evidence/'+id+'.json">证据 '+id.slice(-8)+'</a>')}if(r.query_path&&/^queries\/[a-f0-9]{64}\.sql$/.test(r.query_path))links.push('<a href="'+r.query_path+'">实际查询 SQL</a>');return '<details><summary>展开记录与证据</summary>'+links.join(' · ')+'<pre>'+esc(JSON.stringify(decision?{...r,decision}:r,null,2))+'</pre></details>'}
const searchIndex={};function draw(){const q=$('search').value.toLowerCase(),site=$('country').value;if(!searchIndex[tab])searchIndex[tab]=D[tab].map(r=>JSON.stringify({...r,decision:D.decisions[r.decision_id]}).toLowerCase());let all=D[tab].filter((r,i)=>(!site||r.site===site||searchIndex[tab][i].includes('"site":"'+site.toLowerCase()+'"'))&&(!q||searchIndex[tab][i].includes(q)));const total=Math.max(1,Math.ceil(all.length/50));page=Math.min(page,total-1);$('count').textContent='共 '+all.length+' 条 · 第 '+(page+1)+' / '+total+' 页';$('prev').disabled=page===0;$('next').disabled=page===total-1;
document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));let headings=tab==='jobs'?['国家 / 任务','状态','数据范围','证据']:tab==='candidates'?['国家 / 类目','月份 / 类型','优先级 / 判断','事实与证据']:tab==='checks'?['国家 / 层级','月份 / 检查','状态','范围与依据']:tab==='samples'?['国家 / 类目','商品','语义判断','样本与证据']:['顺序 / 时间','行为','状态','细节'];$('thead').innerHTML='<tr>'+headings.map(h=>'<th>'+h+'</th>').join('')+'</tr>';$('tbody').innerHTML=all.slice(page*50,(page+1)*50).map(r=>{let cells=tab==='jobs'?[esc(r.site)+' / '+esc(r.family),esc(r.record?.execution_status||'未运行'),esc('L'+(r.level??'—')+' '+(r.entity||'')+' '+(r.year||'')+' '+(r.record?.row_count??'')+' 行'),detail(r)]:tab==='candidates'?[esc(r.site)+'<br>'+esc(r.path),esc(r.month)+'<br>'+esc(r.comparison||r.kind),esc(r.priority)+'<br>'+esc(D.decisions[r.decision_id]?.status||'未处置'),detail(r)]:tab==='checks'?[esc(r.site)+' / L'+esc(r.level??'—'),esc(r.month)+'<br>'+esc(r.family),esc(r.state),detail(r)]:tab==='samples'?[esc(r.site)+'<br>'+esc(r.path),esc(r.product_id),esc(r.review?.status||'未复核'),detail(r)]:[esc(r.seq)+'<br>'+esc(r.time),esc(r.type),esc(r.status||''),detail(r)];return '<tr>'+cells.map(c=>'<td>'+c+'</td>').join('')+'</tr>'}).join('')}
$('prev').onclick=()=>{page--;draw()};$('next').onclick=()=>{page++;draw()};let searchTimer;$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{page=0;draw()},180)};$('country').onchange=()=>{page=0;draw()};$('reset').onclick=()=>{$('search').value='';$('country').value='';page=0;draw()};draw();</script></html>'''
    (run.path/'audit.html').write_text(page.replace('__DATA__',embedded))
