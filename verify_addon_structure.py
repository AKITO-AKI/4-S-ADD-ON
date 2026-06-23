#!/usr/bin/env python
"""
Blender アドオン構造検証
========================
"""

import sys
import os
import ast

def verify_addon_structure():
    """Blender アドオン構造を検証"""
    print("=" * 60)
    print("Blender アドオン構造検証")
    print("=" * 60)
    
    # bl_info チェック
    addon_init = "four_s_addon/__init__.py"
    try:
        with open(addon_init, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        # bl_info 定義を検索
        bl_info = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'bl_info':
                        bl_info = node.value
        
        if bl_info:
            print("✓ bl_info 定義確認")
            print(f"  - アドオン構造はアドオンとして認識可能")
        else:
            print("✗ bl_info 定義がありません")
            return False
        
        # register/unregister 関数の確認
        has_register = any(
            isinstance(node, ast.FunctionDef) and node.name == 'register'
            for node in ast.walk(tree)
        )
        has_unregister = any(
            isinstance(node, ast.FunctionDef) and node.name == 'unregister'
            for node in ast.walk(tree)
        )
        
        if has_register and has_unregister:
            print("✓ register/unregister 関数確認")
        else:
            print(f"✗ register/unregister 不完全 (register={has_register}, unregister={has_unregister})")
            return False
        
        return True
    except Exception as e:
        print(f"✗ アドオン構造エラー: {e}")
        return False


def verify_property_groups():
    """プロパティグループの検証"""
    print("\n" + "=" * 60)
    print("プロパティグループ検証")
    print("=" * 60)
    
    try:
        addon_init = "four_s_addon/__init__.py"
        with open(addon_init, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 必須プロパティを確認
        required_props = [
            'comfyui_host',
            'comfyui_port',
            'positive_prompt',
            'negative_prompt',
            'cfg_scale',
            'steps',
            'seed',
            'output_dir',
            'render_depth',
            'render_lineart',
            'generation_status',
            'generation_progress',
            'is_running',
        ]
        
        missing = []
        for prop in required_props:
            if prop not in content:
                missing.append(prop)
        
        if not missing:
            print(f"✓ すべての必須プロパティが定義されています")
            print(f"  - 定義プロパティ数: {len(required_props)}")
        else:
            print(f"✗ 不足しているプロパティ: {missing}")
            return False
        
        return True
    except Exception as e:
        print(f"✗ プロパティグループエラー: {e}")
        return False


def verify_operator_classes():
    """オペレーター定義の検証"""
    print("\n" + "=" * 60)
    print("オペレーター定義検証")
    print("=" * 60)
    
    operators = {
        'operators/render_passes.py': [
            'SOLOSTUDIO_OT_RenderPasses',
            'SOLOSTUDIO_OT_RenderDepthLineart',
        ],
        'operators/send_to_comfyui.py': [
            'SOLOSTUDIO_OT_SendToComfyUI',
            'SOLOSTUDIO_OT_CancelGeneration',
        ],
        'operators/auto_import.py': [
            'SOLOSTUDIO_OT_AutoImportVSE',
            'SOLOSTUDIO_OT_ManualImportVSE',
        ],
    }
    
    all_ok = True
    for filepath, class_names in operators.items():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for class_name in class_names:
                if f"class {class_name}" in content:
                    print(f"✓ {class_name} 定義確認")
                else:
                    print(f"✗ {class_name} が見つかりません")
                    all_ok = False
        except Exception as e:
            print(f"✗ {filepath} 読み込みエラー: {e}")
            all_ok = False
    
    return all_ok


def verify_panel_classes():
    """パネル定義の検証"""
    print("\n" + "=" * 60)
    print("パネル定義検証")
    print("=" * 60)
    
    try:
        with open('four_s_addon/panels.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        panel_classes = [
            'SOLOSTUDIO_PT_MainPanel',
            'SOLOSTUDIO_PT_DebugPanel',
        ]
        
        for panel_class in panel_classes:
            if f"class {panel_class}" in content:
                print(f"✓ {panel_class} 定義確認")
            else:
                print(f"✗ {panel_class} が見つかりません")
                return False
        
        return True
    except Exception as e:
        print(f"✗ パネル定義エラー: {e}")
        return False


def main():
    print("\n📋 Blender アドオン構造検証\n")
    
    results = []
    results.append(("アドオン構造", verify_addon_structure()))
    results.append(("プロパティグループ", verify_property_groups()))
    results.append(("オペレーター定義", verify_operator_classes()))
    results.append(("パネル定義", verify_panel_classes()))
    
    print("\n" + "=" * 60)
    print("検証結果サマリー")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n総合: {passed}/{total} 成功\n")
    
    if passed == total:
        print("🎉 Blender アドオンの構造がすべて正常です。")
        print("   Blender 内で 'SoloStudio' タブから操作できます。\n")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
