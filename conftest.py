# -*- coding: utf-8 -*-
"""项目根级 conftest.py.

确保 XQMagicUI 包可被测试代码导入,并把项目根加入 sys.path。
"""

import sys
from pathlib import Path

# 项目根目录 = 本文件所在目录
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 让 PyQt 在无头环境下也能跑测试（Linux CI 需要）
try:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
except Exception:
    pass
