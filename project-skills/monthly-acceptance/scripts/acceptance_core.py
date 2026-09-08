"""Versioned run records. Business completion, business verdict and sealing are distinct."""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import uuid
import sys
import platform
from datetime import datetime
from pathlib import Path

VERSION = '3.0.1'


def now():
    return datetime.now().astimezone().isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    os.replace(tmp, path)


def month(value):
    if not re.fullmatch(r'\d{4}-\d{2}', value):
        raise ValueError('月份必须是 YYYY-MM')
    datetime.strptime(value, '%Y-%m')
    return value


def shift(value, delta):
    year, mm = map(int, value[:7].split('-'))
    n = year * 12 + mm - 1 + delta
    return f'{n//12:04d}-{n%12+1:02d}'


def months(start, end):
    month(start); month(end)
    if start > end:
        raise ValueError('开始月份晚于结束月份')
    result = []
    while start <= end:
        result.append(start)
        start = shift(start, 1)
    return result


def business_key(*values):
    return digest(values)[:24]


def readonly_sql(sql):
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError('空查询')
    # Remove complete SQL literals first, so punctuation inside a title is harmless.
    tokens = re.sub(r"'(?:\\.|''|[^'\\])*'|`(?:``|[^`])*`|\"(?:\\.|\"\"|[^\"\\])*\"", ' ', sql)
    if any(c in tokens for c in ["'", '\"', '`', '--', '/*', ';']):
        raise ValueError('只接受单条无注释、无分号的只读查询；字符串须闭合')
    if not re.match(r'^\s*(SELECT|WITH|SHOW|DESC|DESCRIBE|EXPLAIN)\b', tokens, re.I):
        raise ValueError('仅允许 SELECT/WITH/SHOW/DESC/EXPLAIN')
    if re.search(r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|LOAD|GRANT|REVOKE|SET|INTO|OUTFILE|EXPORT|CALL|KILL)\b', tokens, re.I):
        raise ValueError('查询包含不允许的操作')
    return sql.strip()


def quoted(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def create_run(base, skill, data_month, related=None):
    import yaml
    base, skill = Path(base).resolve(), Path(skill).resolve()
    month(data_month)
    for name in ['config.yaml', '项目范围.md']:
        if not (base / name).is_file():
            raise ValueError(f'缺少 {base / name}')
    config = yaml.safe_load((base / 'config.yaml').read_text())
    excluded = set(config.get('暂不验收站点', []))
    starts = {str(k): str(v)[:7] for k, v in config['站点起始月份'].items() if k not in excluded}
    policy = read(skill / 'policies/default.json')
    override = base / 'policy-overrides.json'
    if override.exists():
        policy = merge(policy, read(override))
    for table in ['raw_table','std_table']:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*', policy[table]):
            raise ValueError('数据表必须为三段式标识符')
    if policy['levels'] != [0,1,2,3] or policy['comparisons'] != {'mom':1,'yoy':12}:
        raise ValueError('完整验收必须保留国家/L1/L2/L3及自然月环比和同比')
    if not isinstance(policy['page_size'],int) or not 1<=policy['page_size']<=10000:
        raise ValueError('page_size 必须为 1 至 10000')
    for edges in policy['price_bands'].values():
        if edges!=sorted(set(edges)) or any(not isinstance(x,(int,float)) or x<=0 for x in edges):
            raise ValueError('价格带边界须为严格递增的正数')
    for s in starts:
        if not re.fullmatch('[A-Za-z0-9_]+', s) or s not in policy['price_bands']:
            raise ValueError(f'站点缺少明确的政策：{s}')
        months(starts[s], data_month)
    rid = datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z') + '-' + uuid.uuid4().hex[:10]
    directory = base / 'runs' / data_month / rid
    directory.mkdir(parents=True, exist_ok=False)
    frozen = {}
    sources = [(p, Path('skill') / p.relative_to(skill)) for p in skill.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.md','.py','.sql','.json','.html','.yaml'}]
    sources += [(base / n, Path('project') / n) for n in ['config.yaml', '项目范围.md']]
    sources += [(p, Path('project')/p.name) for p in [override, base/'scope-contract.json', base/'open-issues.json'] if p.exists()]
    internal=base/'内部数据'/data_month
    if internal.exists():
        sources += [(p,Path('internal')/p.relative_to(internal)) for p in internal.rglob('*') if p.is_file()]
    for src, rel in sources:
        dest = directory / 'inputs' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        frozen[str(dest.relative_to(directory))] = {'sha256': digest(dest.read_bytes())}
    write(directory/'run.json', {'run_id':rid, 'method_version':VERSION, 'created_at':now(), 'data_month':data_month,
        'starts': starts, 'sites':sorted(starts), 'policy':policy, 'policy_hash':digest(policy), 'inputs':frozen,
        'runtime':{'python':sys.version.split()[0],'platform':platform.system(),'model_parameters':'not exposed by CLI; agent should record visible settings in execution-context.json'},
        'related_run':str(related) if related else None, 'data_consistency':'query-results-with-fingerprints; not transaction snapshot'})
    for d in ['evidence','records','queries','decisions','findings']:
        (directory/d).mkdir()
    run = Run(directory)
    run.event('run.created', scope={'sites': sorted(starts), 'end':data_month}, policy_hash=digest(policy))
    return directory


def merge(a,b):
    a = dict(a)
    for k,v in b.items():
        a[k] = merge(a[k],v) if isinstance(v,dict) and isinstance(a.get(k),dict) else v
    return a


class Run:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.manifest = read(self.path/'run.json')
        self.policy = self.manifest['policy']
        self.events_path = self.path/'events.jsonl'
        self.seq, self.previous = 0, None
        if self.events_path.exists():
            for line in self.events_path.read_text().splitlines():
                e=json.loads(line); self.seq=e['seq']; self.previous=e['hash']

    def writable(self):
        if (self.path/'sealed.json').exists():
            raise ValueError('运行已封存；补查建立新运行并关联，不能覆盖')

    def event(self, kind, **fields):
        self.writable(); self.seq += 1
        e={'event_id':uuid.uuid4().hex, 'run_id':self.manifest['run_id'], 'seq':self.seq,
           'time':now(), 'type':kind, 'previous_hash':self.previous, **fields}
        e['hash']=digest(e); self.previous=e['hash']
        with self.events_path.open('a') as out:
            out.write(canonical(e)+'\n'); out.flush(); os.fsync(out.fileno())
        return e['event_id']

    def verify_inputs(self):
        errors=[]
        for name,item in self.manifest['inputs'].items():
            p=(self.path/name).resolve()
            if not p.is_relative_to(self.path/'inputs') or not p.exists() or digest(p.read_bytes()) != item['sha256']:
                errors.append('input_changed:'+name)
        if digest(self.policy) != self.manifest['policy_hash']:
            errors.append('policy_hash_mismatch')
        return errors

    def register_plan(self, jobs):
        self.writable()
        plan={'policy_hash':self.manifest['policy_hash'],'jobs':jobs,'hash':digest(jobs)}
        p=self.path/'plan.json'
        if p.exists() and read(p)!=plan:
            raise ValueError('任务计划改变；请新建运行。不可在原运行缩小范围或改口径')
        if not p.exists():
            write(p,plan); self.event('plan.frozen', job_count=len(jobs), plan_hash=plan['hash'])

    def evidence(self, value, *, kind, parent_event=None, source=None):
        self.writable()
        eid='ev-'+uuid.uuid4().hex
        p=self.path/'evidence'/f'{eid}.json'
        write(p,value)
        info={'evidence_id':eid,'kind':kind,'path':str(p.relative_to(self.path)), 'sha256':digest(p.read_bytes()),
              'created_at':now(),'source':source,'parent_event_id':parent_event}
        write(self.path/'records'/f'{eid}.json',info)
        self.event('evidence.saved', evidence_id=eid, parent_event_id=parent_event, sha256=info['sha256'])
        return eid

    def get_evidence(self, eid):
        if not re.fullmatch(r'ev-[0-9a-f]{32}',eid): raise ValueError('非法 evidence_id')
        meta=read(self.path/'records'/f'{eid}.json');p=(self.path/meta['path']).resolve()
        if not p.is_relative_to(self.path/'evidence') or digest(p.read_bytes())!=meta['sha256']:
            raise ValueError('证据引用或哈希无效：'+eid)
        return read(p)

    def job_record(self, jid):
        p=self.path/'records'/f'job-{jid}.json'
        return read(p) if p.exists() else None

    def job_rows(self, jid):
        record=self.job_record(jid)
        if not record or record['execution_status']!='success':
            raise ValueError('任务未成功完整执行：'+jid)
        all_rows=[];seen=set()
        for eid in record['evidence_ids']:
            data=self.get_evidence(eid)['response']
            if not data.get('success'): raise ValueError('失败响应被用作成功证据')
            rows=data.get('data',[])
            if len(rows)!=data['row_count']: raise ValueError('返回行数不一致')
            all_rows.extend(rows)
        keys=record.get('key_fields',[])
        if keys:
            for r in all_rows:
                key=canonical([r[k] for k in keys])
                if key in seen: raise ValueError('分页键重复：'+jid)
                seen.add(key)
        if record.get('expected_rows')!=len(all_rows): raise ValueError('分页未完整：'+jid)
        return all_rows

    def decide(self, decision):
        self.writable()
        candidates={c['candidate_id']:c for c in read(self.path/'candidates.json')}
        ids=decision.get('candidate_ids',[])
        if not ids or any(c not in candidates for c in ids): raise ValueError('处置须引用现有候选')
        for field in ['title','facts','reason','next_action','scope','evidence_ids','counterevidence','status','business_verdict']:
            if field not in decision:raise ValueError('缺少处置字段：'+field)
        if decision['status'] not in ['confirmed_defect','supported_change','low_impact','needs_evidence']:
            raise ValueError('未知处置状态')
        if decision['business_verdict'] not in ['pass','qualified','reject','undetermined']:
            raise ValueError('未知使用判断')
        if not decision['evidence_ids']: raise ValueError('处置缺少证据')
        for eid in decision['evidence_ids']:self.get_evidence(eid)
        if not all(isinstance(decision[k],str) and decision[k].strip() for k in ['title','facts','reason','next_action','scope']):
            raise ValueError('判断说明不能为空')
        if decision['status']=='low_impact' and not all(k in decision.get('residual_impact',{}) for k in ['spus','bands','units','amount']):
            raise ValueError('低影响停止须交代四项残余影响')
        if decision['status'] in ['needs_evidence','confirmed_defect'] and decision['business_verdict']=='pass':
            raise ValueError('待核不能记为放行')
        did='decision-'+uuid.uuid4().hex;decision={**decision,'decision_id':did,'created_at':now()}
        write(self.path/'decisions'/f'{did}.json',decision)
        self.event('candidate.disposition', decision_id=did,candidate_ids=ids,status=decision['status'])
        return did

    def dispositions(self):
        result={}
        for p in sorted((self.path/'decisions').glob('*.json'), key=lambda p:read(p)['created_at']):
            d=read(p)
            for cid in d['candidate_ids']:result[cid]=d
        return result

    def verify_events(self):
        errors=[];previous=None
        for i,line in enumerate(self.events_path.read_text().splitlines(),1):
            e=json.loads(line);stored=e.pop('hash')
            if e['seq']!=i or e['previous_hash']!=previous or digest(e)!=stored:errors.append('event_chain:'+str(i))
            previous=stored
        return errors

    def seal(self, validation):
        self.writable()
        if self.verify_inputs():raise ValueError('冻结输入变更')
        for name in ['报告.md','validation.json']:
            if not (self.path/name).exists():raise ValueError('缺少 '+name)
        self.event('run.sealed', execution_state=validation['execution_state'],business_verdict=validation['business_verdict'])
        hashes={}
        for p in sorted(self.path.rglob('*')):
            if p.is_symlink():raise ValueError('封存不能包含链接')
            if p.is_file() and p.name not in ['.lock']:
                hashes[str(p.relative_to(self.path))]=digest(p.read_bytes())
        write(self.path/'sealed.json',{'run_id':self.manifest['run_id'],'sealed_at':now(),'sha256':hashes,
            'execution_state':validation['execution_state'],'business_verdict':validation['business_verdict'],
            'note':'文件封存不代表完整执行或数据放行'})
