#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fast & Lightweight Pip Package Lister
- 零第三方依赖 (纯标准库)
- 毫秒级极速查询 (采用底层 scandir 解析，耗时通常 < 5ms)
- 支持模糊过滤、JSON 导出、requirements.txt 格式导出
"""

import sys
import os
import site
import argparse
import time
from typing import Dict, Tuple, List, Optional


def get_search_paths() -> List[str]:
    """获取当前 Python 环境所有包搜索路径"""
    paths = list(sys.path)
    if hasattr(site, "getsitepackages"):
        try:
            paths.extend(site.getsitepackages())
        except Exception:
            pass
    if hasattr(site, "getusersitepackages"):
        try:
            user_site = site.getusersitepackages()
            if isinstance(user_site, str):
                paths.append(user_site)
        except Exception:
            pass

    # 去重并保留存在的目录
    seen = set()
    valid_paths = []
    for p in paths:
        if p and p not in seen and os.path.isdir(p):
            seen.add(p)
            valid_paths.append(p)
    return valid_paths


def scan_packages(paths: List[str]) -> Dict[str, Tuple[str, str, str]]:
    """
    极速扫描目录下的 .dist-info 和 .egg-info
    返回字典结构: {标准包名小写: (原包名, 版本号, 所在目录)}
    """
    packages: Dict[str, Tuple[str, str, str]] = {}

    for path in paths:
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    name = entry.name
                    if name.endswith(".dist-info"):
                        base = name[:-10]
                        pkg, sep, ver = base.rpartition("-")
                        if sep:
                            key = pkg.lower().replace("_", "-")
                            if key not in packages:
                                packages[key] = (pkg, ver, path)
                    elif name.endswith(".egg-info"):
                        base = name[:-9]
                        pkg, sep, ver = base.rpartition("-")
                        if sep:
                            key = pkg.lower().replace("_", "-")
                            if key not in packages:
                                packages[key] = (pkg, ver, path)
        except (PermissionError, FileNotFoundError):
            continue

    return packages


def get_installed_packages(query: str = "") -> List[Dict[str, str]]:
    """
    供外部模块调用的 API 接口:
    返回包含字典的列表: [{"name": ..., "version": ..., "location": ...}, ...]
    """
    paths = get_search_paths()
    pkg_dict = scan_packages(paths)
    sorted_items = sorted(pkg_dict.values(), key=lambda x: x[0].lower())
    if query:
        q = query.lower().replace("_", "-")
        sorted_items = [
            item for item in sorted_items
            if q in item[0].lower().replace("_", "-")
        ]
    return [
        {"name": item[0], "version": item[1], "location": item[2]}
        for item in sorted_items
    ]


def format_table(rows: List[Tuple[str, str, str]], show_path: bool = False) -> str:
    """生成整洁轻巧的文本表格"""
    if not rows:
        return "没有找到已安装的包。"

    col1_head, col2_head, col3_head = "Package", "Version", "Location"
    max_name = max(len(r[0]) for r in rows)
    max_name = max(max_name, len(col1_head))
    max_ver = max(len(r[1]) for r in rows)
    max_ver = max(max_ver, len(col2_head))

    if show_path:
        header = f"{col1_head:<{max_name}}  {col2_head:<{max_ver}}  {col3_head}"
        sep = f"{'-' * max_name}  {'-' * max_ver}  {'-' * 30}"
        lines = [header, sep]
        for name, ver, loc in rows:
            lines.append(f"{name:<{max_name}}  {ver:<{max_ver}}  {loc}")
    else:
        header = f"{col1_head:<{max_name}}  {col2_head:<{max_ver}}"
        sep = f"{'-' * max_name}  {'-' * max_ver}"
        lines = [header, sep]
        for name, ver, _ in rows:
            lines.append(f"{name:<{max_name}}  {ver:<{max_ver}}")

    return "\n".join(lines)


def main():
    # 确保 Windows 终端中文输出不乱码
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="极速轻量级 Python 已安装库查询工具 (零外部依赖，毫秒级响应)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="可选：按包名模糊过滤（如：requests、torch、numpy）",
    )
    parser.add_argument(
        "-p", "--path",
        action="store_true",
        help="显示安装路径 (Location)",
    )
    parser.add_argument(
        "-f", "--freeze",
        action="store_true",
        help="以 requirements.txt 格式输出 (package==version)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结果",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="静默模式，不输出统计耗时等附加信息",
    )

    args = parser.parse_args()

    # 记录起始时间
    t0 = time.perf_counter()

    paths = get_search_paths()
    pkg_dict = scan_packages(paths)

    # 排序
    sorted_packages = sorted(pkg_dict.values(), key=lambda x: x[0].lower())

    # 过滤
    if args.query:
        q = args.query.lower().replace("_", "-")
        sorted_packages = [
            item for item in sorted_packages
            if q in item[0].lower().replace("_", "-")
        ]

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # JSON 格式输出
    if args.json:
        import json
        out_list = [
            {"name": item[0], "version": item[1], "location": item[2]}
            for item in sorted_packages
        ]
        print(json.dumps(out_list, indent=2, ensure_ascii=False))
        return

    # Freeze 格式输出 (类似 pip freeze)
    if args.freeze:
        for name, ver, _ in sorted_packages:
            print(f"{name}=={ver}")
        return

    # 表格输出
    print(format_table(sorted_packages, show_path=args.path))

    # 统计信息
    if not args.quiet:
        print()
        status_line = f"[统计] 共查询到 {len(sorted_packages)} 个包"
        if args.query:
            status_line += f" (筛选关键词: '{args.query}')"
        status_line += f" | 耗时: {elapsed_ms:.2f} ms | Python: {sys.version.split()[0]}"
        print(status_line)


if __name__ == "__main__":
    main()
