"""Select stale features from committed git history. Python 3 standard library only."""
import fnmatch
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SKILL = Path(__file__).resolve().parent.parent

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args], stderr=subprocess.PIPE)

def patterns(path, key):
    lines = [s[len(key)+1:].strip() for s in path.read_text().splitlines() if s.startswith(key+':')]
    if len(lines) != 1:
        raise ValueError(f'{path}: require exactly one {key}: JSON array')
    value = json.loads(lines[0])
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x or x.startswith('/') or '..' in x.split('/') for x in value):
        raise ValueError(f'{path}: {key} must contain repo-relative paths/globs')
    return value

def matches(path, globs):
    def globmatch(pattern):
        parts, rules = path.split('/'), pattern.split('/')
        @lru_cache(None)
        def at(i, j):
            if j == len(rules):
                return i == len(parts)
            if rules[j] == '**':
                return at(i, j+1) or (i < len(parts) and at(i+1, j))
            return i < len(parts) and fnmatch.fnmatchcase(parts[i], rules[j]) and at(i+1, j+1)
        return at(0, 0)
    return any(globmatch(p) for p in globs)

def changed(base, head):
    base = git('rev-parse', '--verify', '--end-of-options', base+'^{commit}').decode().strip()
    head = git('rev-parse', '--verify', '--end-of-options', head+'^{commit}').decode().strip()
    # Disable rename detection so both old and new paths invalidate their owners.
    return set(x.decode('utf-8', 'surrogateescape') for x in git('diff', '--no-renames', '--name-only', '-z', base, head).split(b'\0') if x)

def main():
    if len(sys.argv) > 3:
        raise ValueError('usage: bash scripts/affected.sh [base [head]]')
    index = SKILL/'features/README.md'
    scope = patterns(index, 'Service paths')
    records = re.findall(r'^Verified: (\S+\.md) (\S+)\s*$', index.read_text(), re.M)
    sync = dict(records)
    features = {p.name: patterns(p, 'Covers') for p in sorted((SKILL/'features').glob('*.md')) if p.name != 'README.md'}
    if not features or len(sync) != len(records) or set(sync) != set(features):
        raise ValueError('require exactly one Verified: <file.md> <commit|NEVER> per feature')
    head = sys.argv[2] if len(sys.argv) == 3 else 'HEAD'
    explicit = changed(sys.argv[1], head) if len(sys.argv) >= 2 else None
    all_changes = set()
    cache = {}
    for name, covers in features.items():
        base = sync[name]
        if base != 'NEVER' and not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base):
            raise ValueError(f'{name}: Verified requires a full immutable commit SHA or NEVER')
        if explicit is not None:
            paths = explicit
        elif base == 'NEVER':
            # Unknown baseline always requires driving; inspect latest change for unmapped paths.
            paths = set(x.decode('utf-8', 'surrogateescape') for x in git('diff-tree', '--root', '--no-commit-id', '--no-renames', '--name-only', '-r', '-z', head).split(b'\0') if x)
        else:
            if base not in cache:
                cache[base] = changed(base, head)
            paths = cache[base]
        all_changes.update(paths)
        if (explicit is None and base == 'NEVER') or any(matches(p, covers) for p in paths):
            print('AFFECTED '+name)
    for p in sorted(all_changes):
        if matches(p, scope) and not any(matches(p, c) for c in features.values()):
            print('UNMAPPED '+p)

if __name__ == '__main__':
    try:
        REPO = Path(os.environ.get('VERIFY_REPO') or subprocess.check_output(['git', '-C', str(SKILL), 'rev-parse', '--show-toplevel'], text=True).strip())
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print('INCONCLUSIVE: affected selection failed: '+str(e), file=sys.stderr)
        sys.exit(2)
