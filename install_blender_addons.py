#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import zipfile


REPO_ROOT = Path(__file__).resolve().parent

SOLO_STUDIO_PACKAGE = "solo_studio_director"
FOUR_S_PACKAGE = "four_s_addon"

SOLO_STUDIO_ENTRIES = [
    "__init__.py",
    "properties.py",
    "operators",
    "panels",
    "utils",
]


def _copy_entry(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _build_staging_packages(repo_root: Path, staging_root: Path) -> list[Path]:
    solo_src_root = repo_root
    solo_dst_root = staging_root / SOLO_STUDIO_PACKAGE
    solo_dst_root.mkdir(parents=True, exist_ok=True)

    for entry in SOLO_STUDIO_ENTRIES:
        src = solo_src_root / entry
        if not src.exists():
            raise FileNotFoundError(f"必要なファイルが見つかりません: {src}")
        _copy_entry(src, solo_dst_root / entry)

    four_s_src_root = repo_root / FOUR_S_PACKAGE
    if not four_s_src_root.exists():
        raise FileNotFoundError(f"必要なディレクトリが見つかりません: {four_s_src_root}")
    _copy_entry(four_s_src_root, staging_root / FOUR_S_PACKAGE)

    packages = [solo_dst_root, staging_root / FOUR_S_PACKAGE]
    for pkg in packages:
        init_file = pkg / "__init__.py"
        if not init_file.exists():
            raise RuntimeError(f"__init__.py が存在しません: {init_file}")

    return packages


def _zip_package(package_dir: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{package_dir.name}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_dir.rglob("*")):
            if path.is_dir():
                continue
            rel_path = path.relative_to(package_dir.parent)
            zf.write(path, arcname=str(rel_path))
    return archive_path


def _default_addons_dir(blender_version: str) -> Path:
    system = platform.system()
    home = Path.home()

    if system == "Windows":
        appdata = os.getenv("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA が取得できません。--addons-dir を指定してください。")
        return (
            Path(appdata)
            / "Blender Foundation"
            / "Blender"
            / blender_version
            / "scripts"
            / "addons"
        )

    if system == "Darwin":
        return (
            home
            / "Library"
            / "Application Support"
            / "Blender"
            / blender_version
            / "scripts"
            / "addons"
        )

    return home / ".config" / "blender" / blender_version / "scripts" / "addons"


def _install_package(package_dir: Path, addons_dir: Path, backup_root: Path) -> tuple[Path, Path | None]:
    target = addons_dir / package_dir.name
    backup_path: Path | None = None

    if target.exists():
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_path = backup_root / package_dir.name
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.move(str(target), str(backup_path))

    try:
        shutil.copytree(
            package_dir,
            target,
            dirs_exist_ok=False,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
    except Exception:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backup_path and backup_path.exists():
            shutil.move(str(backup_path), str(target))
        raise

    return target, backup_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Blenderアドオン(4-S-ADD-ON)を安定して導入するインストーラー",
    )
    parser.add_argument(
        "--blender-version",
        default="4.0",
        help="Blenderバージョン (例: 4.0, 4.1)",
    )
    parser.add_argument(
        "--addons-dir",
        type=Path,
        help="Blenderの addons ディレクトリを明示指定",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="リポジトリルート (既定: スクリプト配置場所)",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=REPO_ROOT / "dist",
        help="ZIP出力先ディレクトリ",
    )
    parser.add_argument(
        "--zip-only",
        action="store_true",
        help="ZIPのみ作成し、addons ディレクトリには導入しない",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際の導入はせず、実行内容のみ表示する",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    repo_root = args.repo_root.resolve()
    if not repo_root.exists():
        print(f"[ERROR] repo root が存在しません: {repo_root}")
        return 1

    addons_dir = (args.addons_dir or _default_addons_dir(args.blender_version)).expanduser().resolve()
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = addons_dir.parent / f"addons_backup_{timestamp}"

    with tempfile.TemporaryDirectory(prefix="four_s_installer_") as tmp:
        staging_root = Path(tmp) / "staging"
        packages = _build_staging_packages(repo_root, staging_root)

        archives = [_zip_package(pkg, args.dist_dir.resolve()) for pkg in packages]
        for archive in archives:
            print(f"[OK] ZIP作成: {archive}")

        if args.zip_only:
            print("[INFO] --zip-only のため導入処理をスキップしました。")
            return 0

        print(f"[INFO] 導入先: {addons_dir}")
        if args.dry_run:
            for pkg in packages:
                print(f"[DRY-RUN] {pkg.name} を {addons_dir / pkg.name} に導入")
            return 0

        addons_dir.mkdir(parents=True, exist_ok=True)
        installed: list[Path] = []
        backups: list[Path] = []

        try:
            for pkg in packages:
                target, backup_path = _install_package(pkg, addons_dir, backup_root)
                installed.append(target)
                if backup_path:
                    backups.append(backup_path)
                print(f"[OK] 導入完了: {target}")
        except Exception as exc:
            print(f"[ERROR] 導入中に失敗しました: {exc}")
            for target in installed:
                if target.exists():
                    shutil.rmtree(target, ignore_errors=True)
            for backup in backups:
                restore_target = addons_dir / backup.name
                if backup.exists() and not restore_target.exists():
                    shutil.move(str(backup), str(restore_target))
            return 1

        if backup_root.exists() and not any(backup_root.iterdir()):
            backup_root.rmdir()
        elif backup_root.exists():
            print(f"[INFO] 既存アドオンのバックアップ: {backup_root}")

        print("[DONE] Blenderアドオン導入が完了しました。")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
