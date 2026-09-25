#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_core_no_ui — 确保 core/ 零 UI 耦合、零第三方依赖：
1. 静态扫描：core/ 所有源文件不 import tkinter / src.* / numpy / pandas
2. 动态验证：屏蔽第三方模块后 import core 仍成功
"""
import ast
import glob
import os
import subprocess
import sys

import pytest

CORE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")

FORBIDDEN_MODULES = {"tkinter", "numpy", "pandas", "src", "PyQt5", "wx"}


def core_source_files():
    return sorted(glob.glob(os.path.join(CORE_DIR, "*.py")))


def test_no_forbidden_imports_static():
    violations = []
    for path in core_source_files():
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_MODULES or alias.name.startswith("src."):
                        violations.append((path, alias.name))
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in FORBIDDEN_MODULES:
                    violations.append((path, node.module))
    assert not violations, "core/ 引入了被禁止的依赖: {0}".format(violations)


def test_core_imports_with_third_party_blocked():
    """屏蔽 numpy/pandas/tkinter 后 core 仍可完整导入"""
    code = (
        "import sys\n"
        "class Blocker:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name.split('.')[0] in ('numpy', 'pandas', 'tkinter'):\n"
        "            return self\n"
        "        return None\n"
        "    def load_module(self, name):\n"
        "        raise ImportError('blocked: ' + name)\n"
        "sys.meta_path.insert(0, Blocker())\n"
        "import core\n"
        "assert core.ScoringAlgorithm().skating_system_available\n"
        "print('CORE_OK')\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], cwd=CORE_DIR + "/..",
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "CORE_OK" in proc.stdout
