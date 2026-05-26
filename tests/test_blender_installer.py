import pathlib
import tempfile
import unittest
from unittest import mock

import install_blender_addons as installer


class TestBlenderInstaller(unittest.TestCase):
    def _create_fake_repo(self, root: pathlib.Path) -> None:
        (root / "__init__.py").write_text("bl_info = {}\n", encoding="utf-8")
        (root / "properties.py").write_text("x = 1\n", encoding="utf-8")

        for pkg_name in ("operators", "panels", "utils", "four_s_addon"):
            pkg = root / pkg_name
            pkg.mkdir(parents=True, exist_ok=True)
            (pkg / "__init__.py").write_text("# init\n", encoding="utf-8")
            (pkg / "module.py").write_text("value = 1\n", encoding="utf-8")

    def test_build_staging_packages_creates_two_addons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            repo = tmp_path / "repo"
            repo.mkdir()
            self._create_fake_repo(repo)

            staging = tmp_path / "staging"
            packages = installer._build_staging_packages(repo, staging)

            self.assertEqual(
                sorted(pkg.name for pkg in packages),
                sorted([installer.SOLO_STUDIO_PACKAGE, installer.FOUR_S_PACKAGE]),
            )
            self.assertTrue((staging / installer.SOLO_STUDIO_PACKAGE / "__init__.py").exists())
            self.assertTrue((staging / installer.FOUR_S_PACKAGE / "__init__.py").exists())

    def test_install_package_rolls_back_on_copy_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            package_dir = tmp_path / "pkg"
            package_dir.mkdir()
            (package_dir / "__init__.py").write_text("# init\n", encoding="utf-8")

            addons_dir = tmp_path / "addons"
            addons_dir.mkdir()
            target = addons_dir / "pkg"
            target.mkdir()
            (target / "__init__.py").write_text("# old\n", encoding="utf-8")
            (target / "old.txt").write_text("old", encoding="utf-8")

            backup_root = tmp_path / "backups"

            with mock.patch("install_blender_addons.shutil.copytree", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    installer._install_package(package_dir, addons_dir, backup_root)

            self.assertTrue((target / "old.txt").exists())
            self.assertFalse((target / "__init__.py").read_text(encoding="utf-8").startswith("# init"))

    def test_main_zip_only_creates_archives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            repo = tmp_path / "repo"
            repo.mkdir()
            self._create_fake_repo(repo)

            dist = tmp_path / "dist"
            addons_dir = tmp_path / "addons"
            exit_code = installer.main(
                [
                    "--repo-root",
                    str(repo),
                    "--dist-dir",
                    str(dist),
                    "--addons-dir",
                    str(addons_dir),
                    "--zip-only",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((dist / f"{installer.SOLO_STUDIO_PACKAGE}.zip").exists())
            self.assertTrue((dist / f"{installer.FOUR_S_PACKAGE}.zip").exists())
            self.assertFalse(addons_dir.exists())


if __name__ == "__main__":
    unittest.main()
