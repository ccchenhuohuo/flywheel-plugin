#!/usr/bin/env python3
"""独立运行包：只管理文件，不查询数据、不裁决、不写全局指纹。"""
import argparse
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILL = ROOT / '.claude/skills/monthly-acceptance'
BASE = Path(os.environ.get('ACCEPTANCE_DIR', str(ROOT / '验收'))).resolve()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    with path.open('x', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write('\n')


def start(month):
    if len(month) != 7 or datetime.strptime(month, '%Y-%m').strftime('%Y-%m') != month:
        raise ValueError('月份必须是 YYYY-MM')
    if not (SKILL / 'SKILL.md').is_file():
        raise ValueError('缺少 SKILL.md，不能冻结不完整的方法包')
    now = datetime.now().astimezone()
    run_id = now.strftime('%Y%m%dT%H%M%S%z') + '-' + uuid.uuid4().hex[:10]
    sources = [p for p in SKILL.rglob('*') if p.is_file() and p.suffix in {'.md', '.sql', '.py'}]
    sources += [BASE / 'config.yaml', BASE / '项目范围.md']
    if any(not p.is_file() for p in sources):
        raise ValueError('缺少 config.yaml 或 项目范围.md，先补全有效输入')
    run = BASE / 'runs' / month / run_id
    run.mkdir(parents=True, exist_ok=False)
    (run / 'evidence').mkdir()
    frozen = {}
    for source in sorted(sources):
        relative = Path('skill') / source.relative_to(SKILL) if source.is_relative_to(SKILL) else Path('project') / source.name
        target = run / 'inputs' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        frozen[str(target.relative_to(run))] = {'source': str(source), 'sha256': digest(target)}
    write_json(run / 'run.json', {'run_id': run_id, 'data_month': month,
               'created_at': now.isoformat(), 'method_version': '2.1', 'inputs': frozen})
    print(run)


def seal(directory):
    run = Path(directory).resolve()
    if not run.is_relative_to(BASE / 'runs') or not (run / 'run.json').is_file():
        raise ValueError('仅封存本验收目录 runs 下的运行包')
    if (run / 'sealed.json').exists():
        raise ValueError('已封存，不覆盖；补查请新建运行包')
    manifest = json.loads((run / 'run.json').read_text())
    for name in ['观察.md', '报告.md']:
        if not (run / name).is_file() or not (run / name).read_text().strip():
            raise ValueError(f'缺少非空 {name}')
    evidence = [p for p in (run / 'evidence').rglob('*') if p.is_file() and p.stat().st_size]
    if not evidence:
        raise ValueError('evidence 缺少本次查询、范围及结果文件')
    for name, source in manifest['inputs'].items():
        path = (run / name).resolve()
        if not path.is_relative_to(run / 'inputs') or digest(path) != source['sha256']:
            raise ValueError(f'冻结输入被修改：{name}')
    files = {}
    for path in sorted(run.rglob('*')):
        if path.is_symlink():
            raise ValueError('运行包中不允许链接代替本次证据')
        if path.is_file():
            files[str(path.relative_to(run))] = digest(path)
    write_json(run / 'sealed.json', {'run_id': manifest['run_id'],
               'sealed_at': datetime.now().astimezone().isoformat(), 'sha256': files})
    print(run / 'sealed.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('start').add_argument('--month', required=True)
    sub.add_parser('seal').add_argument('directory')
    args = parser.parse_args()
    try:
        start(args.month) if args.command == 'start' else seal(args.directory)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
