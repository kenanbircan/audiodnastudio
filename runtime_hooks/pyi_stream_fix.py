import os
import sys

# PyInstaller GUI executables can have None stdio streams. ML libraries such as
# PyTorch/tqdm may call write()/flush()/isatty() on them. Provide real file
# objects before any application imports.
_KEEP=[]
def _open(mode):
    f=open(os.devnull, mode, buffering=1 if 'w' in mode else -1, encoding='utf-8', errors='replace')
    _KEEP.append(f)
    return f
if sys.stdout is None: sys.stdout=_open('w')
if sys.stderr is None: sys.stderr=_open('w')
if sys.stdin is None: sys.stdin=_open('r')
