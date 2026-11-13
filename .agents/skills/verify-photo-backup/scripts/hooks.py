"""Opt-in local git hook dispatcher. Leaves original hook bytes untouched."""
import json
import os
from pathlib import Path
import subprocess
import sys

SKILL = Path(__file__).resolve().parent.parent
HOOKS = 'applypatch-msg pre-applypatch post-applypatch pre-commit pre-merge-commit prepare-commit-msg commit-msg post-commit pre-rebase post-checkout post-merge pre-push pre-auto-gc post-rewrite sendemail-validate push-to-checkout reference-transaction'.split()
def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()
def config(*args):
    p=subprocess.run(['git','config',*args],capture_output=True,text=True)
    if p.returncode not in (0,1): raise RuntimeError(p.stderr)
    return p.stdout.strip() if p.returncode == 0 else None

def main():
    root=Path(git('rev-parse','--show-toplevel')); os.chdir(root)
    state=Path(git('rev-parse','--git-path','bstack-hooks')).resolve()
    action=sys.argv[1] if len(sys.argv)==2 else ''
    if action=='install':
        if state.exists(): raise RuntimeError('already installed; uninstall before changing registration')
        skill=str(SKILL.relative_to(root))
        original=Path(git('rev-parse','--git-path','hooks'))
        # Relative hooksPath resolves in the hook execution cwd (repo root here).
        if config('--get','core.hooksPath') is None:
            original=original.resolve()
        previous=config('--local','--get','core.hooksPath')
        state.mkdir(parents=True)
        (state/'state.json').write_text(json.dumps({'previous':previous,'original':str(original),'skill':skill}))
        # Wrap every existing hook and all standard names, including non-post hooks.
        names=set(HOOKS)|{p.name for p in original.glob('*') if p.is_file() and not p.name.endswith('.sample')}
        for name in names:
            if not name.replace('-','').isalnum(): raise RuntimeError('unsupported hook name: '+name)
            wrapper=state/name
            wrapper.write_text('#!/bin/sh\nexec python3 '+__import__('shlex').quote(str(state/'dispatch.py'))+' '+__import__('shlex').quote(name)+' "$@"\n')
            wrapper.chmod(0o755)
        (state/'dispatch.py').write_text(DISPATCH)
        subprocess.check_call(['git','config','--local','core.hooksPath',str(state)])
        print('Installed local hooks; uninstall: python3 '+str(SKILL/'scripts/hooks.py')+' uninstall')
    elif action=='uninstall':
        data=json.loads((state/'state.json').read_text())
        if config('--local','--get','core.hooksPath')!=str(state): raise RuntimeError('hooksPath changed since install; refusing to replace it')
        if data['previous'] is None: subprocess.check_call(['git','config','--local','--unset','core.hooksPath'])
        else: subprocess.check_call(['git','config','--local','core.hooksPath',data['previous']])
        import shutil
        shutil.rmtree(state); print('Restored original hooks configuration')
    else: raise RuntimeError('usage: python3 scripts/hooks.py install|uninstall')

DISPATCH=r'''
import json, os, pathlib, subprocess, sys
state=pathlib.Path(__file__).resolve().parent
data=json.loads((state/'state.json').read_text())
name=sys.argv[1]; prior=(pathlib.Path(data['original'])/name).absolute()
code=0
if prior.is_file() and os.access(prior,os.X_OK):
    code=subprocess.call([str(prior),*sys.argv[2:]])
if name in ('post-merge','post-checkout'):
    try:
        root=pathlib.Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())
        skill=root/data['skill']; svc=skill.name.removeprefix('verify-')
        pending=root/'.verify'/svc/'pending'; pending.parent.mkdir(parents=True,exist_ok=True)
        p=subprocess.run(['bash',str(skill/'scripts/affected.sh')],text=True,capture_output=True)
        output=p.stdout if p.returncode==0 else 'INCONCLUSIVE: '+p.stderr.strip()+'\n'
        previous=pending.read_text().splitlines() if pending.exists() else []
        gaps={line[9:] for line in previous if line.startswith('UNMAPPED ')}
        if p.returncode==0 and gaps:
            # A verified mapped journey cannot discharge an unmapped surface.
            import runpy
            selector=runpy.run_path(str(skill/'scripts/affected.py'))
            covers=[c for f in (skill/'features').glob('*.md') if f.name!='README.md'
                    for c in selector['patterns'](f,'Covers')]
            gaps={path for path in gaps if not selector['matches'](path,covers)}
        lines=set(output.splitlines())|{'UNMAPPED '+path for path in gaps}
        output=''.join(line+'\n' for line in sorted(lines))
        # Replace atomically; default selection includes all still-stale sync ranges.
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w',dir=pending.parent,delete=False) as f:
            f.write(output); tmp=pathlib.Path(f.name)
        tmp.replace(pending)
        if output: print('bstack: stale verification; see '+str(pending),file=sys.stderr)
    except Exception as e:
        print('bstack: INCONCLUSIVE hook: '+str(e),file=sys.stderr)
sys.exit(code)
'''
if __name__=='__main__':
    try: main()
    except Exception as e:
        print('bstack hooks: '+str(e),file=sys.stderr); sys.exit(2)
