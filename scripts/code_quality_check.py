"""
Code quality check script.

Checks for:
- Docstring coverage
- Function complexity
- Error handling
- Code organization
"""

import os
import ast
import sys
from pathlib import Path
from typing import List, Tuple

def check_docstrings(file_path: str) -> Tuple[int, int, List[str]]:
    """
    Check docstring coverage in a Python file.
    """
    try:
        # Added utf-8 encoding for safety
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except (SyntaxError, UnicodeDecodeError, PermissionError) as e:
        # If we can't parse it, we treat it as 0 items rather than crashing
        return 0, 0, []
    
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    
    total = len(functions) + len(classes)
    documented = 0
    missing = []
    
    for node in functions + classes:
        if node.name.startswith('_') and not node.name.startswith('__'):
            total -= 1
            continue
        
        docstring = ast.get_docstring(node)
        if docstring:
            documented += 1
        else:
            missing.append(f"{node.name} (line {node.lineno})")
    
    return total, documented, missing


def check_error_handling(file_path: str) -> Tuple[int, int]:
    """
    Count functions with error handling.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except:
        return 0, 0
    
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    total = len([f for f in functions if not f.name.startswith('_')])
    with_try = 0
    
    for func in functions:
        if func.name.startswith('_'):
            continue
        
        for node in ast.walk(func):
            if isinstance(node, ast.Try):
                with_try += 1
                break
    
    return total, with_try


def analyze_code_metrics(directory: str):
    """Analyze code quality metrics for directory."""
    print("=" * 60)
    print("CODE QUALITY ANALYSIS")
    print("=" * 60)
    print()
    
    py_files = []
    # Key modification: Added logic to skip unwanted directories
    skip_dirs = {'.venv', 'venv', 'env', '__pycache__', 'node_modules', '.git'}
    
    for root, dirs, files in os.walk(directory):
        # Modify dirs in-place to prevent os.walk from entering them
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        # Also skip test folders as per your original logic
        if 'test_' in root:
            continue
        
        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                py_files.append(os.path.join(root, file))
    
    # 1. Docstring coverage
    print("1. DOCSTRING COVERAGE")
    print("-" * 60)
    
    total_items = 0
    total_documented = 0
    files_with_issues = []
    
    for file_path in py_files:
        total, documented, missing = check_docstrings(file_path)
        
        if total > 0:
            total_items += total
            total_documented += documented
            coverage = (documented / total * 100) if total > 0 else 100
            
            rel_path = os.path.relpath(file_path)
            
            if coverage < 100:
                print(f"⚠️  {rel_path}: {coverage:.0f}% ({documented}/{total})")
                print(f"    Missing: {', '.join(missing)}")
                files_with_issues.append((rel_path, missing))
            else:
                print(f"✅ {rel_path}: 100% ({documented}/{total})")
    
    overall_coverage = (total_documented / total_items * 100) if total_items > 0 else 100
    print(f"\n📊 Overall: {overall_coverage:.1f}% ({total_documented}/{total_items})")
    
    if files_with_issues:
        print(f"\n⚠️  {len(files_with_issues)} file(s) with missing docstrings")
    
    # 2. Error handling
    print("\n2. ERROR HANDLING")
    print("-" * 60)
    
    total_funcs = 0
    funcs_with_error_handling = 0
    
    for file_path in py_files:
        total, with_try = check_error_handling(file_path)
        total_funcs += total
        funcs_with_error_handling += with_try
    
    error_coverage = (funcs_with_error_handling / total_funcs * 100) if total_funcs > 0 else 0
    print(f"Functions with try/except: {funcs_with_error_handling}/{total_funcs} ({error_coverage:.1f}%)")
    
    # 3. File organization
    print("\n3. FILE ORGANIZATION")
    print("-" * 60)
    
    modules = {
        'data': 0,
        'config': 0,
        'regime': 0,
        'tests': 0,
        'scripts': 0,
    }
    
    for file_path in py_files:
        for module in modules:
            if module in file_path:
                modules[module] += 1
                break
    
    for module, count in modules.items():
        print(f"  {module:12s}: {count} file(s)")
    
    print(f"\n  Total modules: {len(py_files)} files")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    issues = []
    
    if overall_coverage < 90:
        issues.append(f"Docstring coverage low ({overall_coverage:.1f}%)")
    
    if error_coverage < 20:
        issues.append(f"Error handling coverage low ({error_coverage:.1f}%)")
    
    if issues:
        print("⚠️  Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ No major code quality issues")
    
    # Recommendations
    print("\n📋 Recommendations:")
    
    if overall_coverage < 100:
        print("  - Add docstrings to undocumented functions")
    
    if error_coverage < 50:
        print("  - Consider adding error handling to key functions")
    else:
        print("  - Code quality is good")
    
    print()


def check_line_counts():
    """Count lines of code by category."""
    
    print("=" * 60)
    print("CODE METRICS")
    print("=" * 60)
    print()
    
    categories = {
        'Production code': ['data/', 'config/', 'regime/features.py', 'regime/classifier.py', 'regime/visualization.py'],
        'Tests': ['tests/', 'regime/tests/'],
        'Scripts': ['scripts/'],
        'Documentation': ['docs/', 'README.md', 'CHANGELOG.md'],
    }
    
    for category, paths in categories.items():
        total_lines = 0
        
        for path in paths:
            if os.path.isfile(path):
                with open(path, 'r') as f:
                    total_lines += len(f.readlines())
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if file.endswith('.py') or file.endswith('.md'):
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'r') as f:
                                    total_lines += len(f.readlines())
                            except:
                                pass
        
        print(f"{category:20s}: {total_lines:5d} lines")
    
    print()


def main():
    """Run all code quality checks."""
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("=" * 60)
    print("CODE QUALITY CHECK")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print()
    
    # Analyze main code directories
    for directory in ['.']:
        analyze_code_metrics(directory)
    
    # Line counts
    check_line_counts()
    
    print("=" * 60)
    print("✅ Code quality check complete")
    print("=" * 60)


if __name__ == "__main__":
    main()