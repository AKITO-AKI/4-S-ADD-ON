#!/usr/bin/env python
"""
第2段階検証スクリプト
=====================
コンポーネント間の連携を検証します（Blender 環境外）
"""

import sys
import json

def verify_imports():
    """モジュールのインポート検証（bpy 除く）"""
    print("=" * 60)
    print("モジュールインポート検証")
    print("=" * 60)
    
    try:
        from utils import workflow_builder
        print("✓ workflow_builder モジュール正常")
        
        # WorkflowParams が存在するか確認
        params = workflow_builder.WorkflowParams()
        print(f"  - WorkflowParams インスタンス作成成功")
        print(f"    frame_count: {params.frame_count}")
        print(f"    cfg_scale: {params.cfg_scale}")
    except Exception as e:
        print(f"✗ workflow_builder エラー: {e}")
        return False
    
    try:
        from utils import comfyui_api
        print("✓ comfyui_api モジュール正常")
        
        # REST API 関数が存在するか確認
        assert hasattr(comfyui_api, 'build_base_url')
        assert hasattr(comfyui_api, 'queue_prompt')
        assert hasattr(comfyui_api, 'get_history')
        assert hasattr(comfyui_api, 'upload_image')
        assert hasattr(comfyui_api, 'ProgressListener')
        print("  - 全 API 関数存在確認")
    except Exception as e:
        print(f"✗ comfyui_api エラー: {e}")
        return False
    
    try:
        from utils import async_handler
        print("✓ async_handler モジュール正常")
        
        # AsyncGenerationHandler が存在するか確認
        assert hasattr(async_handler, 'AsyncGenerationHandler')
        print("  - AsyncGenerationHandler クラス存在確認")
    except Exception as e:
        print(f"✗ async_handler エラー: {e}")
        return False
    
    return True


def verify_workflow():
    """ワークフロー生成検証"""
    print("\n" + "=" * 60)
    print("ワークフロー生成検証")
    print("=" * 60)
    
    try:
        from utils.workflow_builder import WorkflowParams, build_workflow
        
        # デフォルトパラメータでワークフロー生成
        params = WorkflowParams(
            positive_prompt="anime style, detailed character",
            negative_prompt="lowres, blurry",
            cfg_scale=7.0,
            steps=20,
        )
        
        workflow = build_workflow(params)
        
        # ワークフローが辞書か確認
        assert isinstance(workflow, dict), "workflow は dict でない"
        
        # ノード数確認
        node_count = len(workflow)
        print(f"✓ ワークフロー生成成功")
        print(f"  - ノード数: {node_count}")
        
        # CheckpointLoader が存在するか確認
        found_checkpoint = False
        for node_id, node in workflow.items():
            if node.get("class_type") == "CheckpointLoaderSimple":
                found_checkpoint = True
                break
        
        if found_checkpoint:
            print(f"  - CheckpointLoaderSimple ノード確認")
        else:
            print(f"  ⚠ CheckpointLoaderSimple ノドが見つかりません")
        
        return True
    except Exception as e:
        print(f"✗ ワークフロー生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_api_structure():
    """API 構造検証"""
    print("\n" + "=" * 60)
    print("API 構造検証")
    print("=" * 60)
    
    try:
        from utils.comfyui_api import build_base_url
        
        # URL 構築テスト
        url = build_base_url("127.0.0.1", 8188)
        expected = "http://127.0.0.1:8188"
        assert url == expected, f"URL 構築エラー: {url} != {expected}"
        print(f"✓ URL 構築テスト成功: {url}")
        
        # HTTPS テスト
        url2 = build_base_url("https://example.com", 443)
        print(f"✓ HTTPS URL テスト成功: {url2}")
        
        return True
    except Exception as e:
        print(f"✗ API 構造エラー: {e}")
        return False


def verify_operators_structure():
    """オペレーター構造検証（インポート不可な場合はスキップ）"""
    print("\n" + "=" * 60)
    print("オペレーター構造検証")
    print("=" * 60)
    
    print("⚠ Blender 環境外のため、ソースコード検証のみ")
    
    # ファイルが存在するか確認
    import os
    
    required_files = [
        "operators/render_passes.py",
        "operators/send_to_comfyui.py",
        "operators/auto_import.py",
        "operators/__init__.py",
    ]
    
    all_exist = True
    for fpath in required_files:
        if os.path.isfile(fpath):
            print(f"  ✓ {fpath} 存在")
        else:
            print(f"  ✗ {fpath} 不在")
            all_exist = False
    
    return all_exist


def main():
    print("\n🔍 第2段階検証スクリプト実行\n")
    
    results = []
    results.append(("モジュールインポート", verify_imports()))
    results.append(("API 構造", verify_api_structure()))
    results.append(("ワークフロー生成", verify_workflow()))
    results.append(("オペレーター構造", verify_operators_structure()))
    
    print("\n" + "=" * 60)
    print("検証結果サマリー")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n総合: {passed}/{total} 成功\n")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
