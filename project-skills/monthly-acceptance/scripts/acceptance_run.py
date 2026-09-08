#!/usr/bin/env python3
"""Versioned acceptance execution, evidence, coverage and report CLI."""
import argparse
import asyncio
import fcntl
import json
from pathlib import Path
from acceptance_core import Run,create_run,read,write,digest
from acceptance_queries import plan,drilldown
from acceptance_transport import connect,scan,call,execute_job
from acceptance_analysis import analyze
from acceptance_validate import validate
from acceptance_render import render


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    start=sub.add_parser('start');start.add_argument('--month',required=True);start.add_argument('--base',default='验收');start.add_argument('--related-run')
    for name in ['scan','finish-scan','analyze','status','validate','render','seal','verify-seal']:
        p=sub.add_parser(name);p.add_argument('run');p.add_argument('--mcp-config') if name in ['scan','finish-scan'] else None
    p=sub.add_parser('query');p.add_argument('run');p.add_argument('--sql-file',required=True);p.add_argument('--label',required=True);p.add_argument('--mcp-config')
    p=sub.add_parser('drill');p.add_argument('run');p.add_argument('--candidate-id',required=True);p.add_argument('--mcp-config')
    p=sub.add_parser('record');p.add_argument('run');p.add_argument('--file',required=True)
    p=sub.add_parser('attach');p.add_argument('run');p.add_argument('--file',required=True);p.add_argument('--kind',required=True);p.add_argument('--source',required=True)
    args=parser.parse_args();skill=Path(__file__).resolve().parents[1]
    if args.command=='start':
        directory=create_run(args.base,skill,args.month,args.related_run);run=Run(directory);run.register_plan(plan(run.manifest));print(directory);return
    run=Run(args.run)
    with (run.path/'.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('此运行正在执行另一个写操作。请等待；观察 events.jsonl 不需要锁。')
        if args.command=='verify-seal':
            sealed=read(run.path/'sealed.json');errors=[]
            for path,sha in sealed['sha256'].items():
                p=(run.path/path).resolve()
                if not p.is_relative_to(run.path) or not p.exists() or digest(p.read_bytes())!=sha:errors.append(path)
            print(json.dumps({'file_integrity':not errors,'changed_or_missing':errors,'execution_state':sealed['execution_state'],'business_verdict':sealed['business_verdict']},ensure_ascii=False,indent=2));return
        run.writable()
        if run.verify_inputs():raise SystemExit('冻结输入已变更')
        if args.command=='scan':
            jobs=plan(run.manifest);run.register_plan(jobs);asyncio.run(scan(run,jobs,args.mcp_config))
        elif args.command=='finish-scan':
            asyncio.run(scan(run,plan(run.manifest,True),args.mcp_config,force=True))
        elif args.command=='analyze':print(json.dumps(analyze(run),ensure_ascii=False))
        elif args.command in ['status','validate']:
            v=validate(run,persist=args.command=='validate');print(json.dumps(v,ensure_ascii=False,indent=2))
        elif args.command=='record':
            value=read(args.file);decisions=value if isinstance(value,list) else [value]
            print(json.dumps([run.decide(d) for d in decisions],ensure_ascii=False))
        elif args.command=='attach':
            p=Path(args.file);print(run.evidence({'content':p.read_text(),'original_filename':p.name,'original_sha256':digest(p.read_bytes())},kind=args.kind,source=args.source))
        elif args.command=='query':
            async def query():
                async with connect(run,args.mcp_config) as session:
                    eid,data=await call(run,session,Path(args.sql_file).read_text(),args.label)
                    print(json.dumps({'evidence_id':eid,'rows':data['row_count'],'note':'自由查询结果仅为证据；不增加基础覆盖计数。截断风险须自行明确。'},ensure_ascii=False))
            asyncio.run(query())
        elif args.command=='drill':
            c=next(c for c in read(run.path/'candidates.json') if c['candidate_id']==args.candidate_id)
            if c['kind']!='result_change':raise ValueError('此候选需要按事实编写溯源查询，不能自动做 SPU 增减分解')
            lag=run.policy['comparisons'][c['comparison']]
            j={'job_id':'drill-'+c['candidate_id'],'family':'drill','site':c['site'],'candidate_id':c['candidate_id'],
                'key_fields':['product_id'],'sql':drilldown(run.manifest,c['site'],c['path'],c['level'],c['month'],lag)}
            write(run.path/'records'/(j['job_id']+'-plan.json'),j)
            async def execute():
                async with connect(run,args.mcp_config) as session:await execute_job(run,session,j)
            asyncio.run(execute())
        elif args.command=='render':render(run)
        elif args.command=='seal':
            v=validate(run);render(run);run.seal(v)
            print(json.dumps({'sealed':True,'execution_state':v['execution_state'],'business_verdict':v['business_verdict']},ensure_ascii=False))

if __name__=='__main__':main()
