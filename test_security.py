import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
import bridge
import security


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bridge-security-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "workspace"
        self.root.mkdir()
        for key in ("WORKSPACE", "COMMAND_WORKSPACE"):
            p = patch.object(bridge, key, self.root)
            p.start()
            self.addCleanup(p.stop)
        self.policy = {"filesystem": {"denied_paths": [str(self.root / "private")],
                                     "read_only_paths": [str(self.root / "control")]}}
        p = patch.object(bridge, "BRIDGE_CONFIG", self.policy)
        p.start()
        self.addCleanup(p.stop)
        (self.root / "source").write_text("keep")
        (self.root / "private").mkdir()
        (self.root / "private" / "key").write_text("synthetic-private-marker")
        (self.root / "control").mkdir()
        (self.root / "control" / "policy").write_text("original")

    def test_move_refuses_root_and_overlapping_paths_before_deleting(self):
        for src, dst in [("source", "."), (".", "destination"), ("source", "source"),
                         ("source", "source/nested"), ("control/policy", "control"), ("source", "..")] :
            with self.subTest(src=src, dst=dst), self.assertRaises(HTTPException):
                bridge.move(bridge.MoveRequest(source=src, destination=dst, overwrite=True))
        self.assertEqual((self.root / "source").read_text(), "keep")

    def test_move_never_recursively_erases_nonempty_destination(self):
        (self.root / "from_dir").mkdir()
        (self.root / "to_dir").mkdir()
        (self.root / "to_dir" / "keep").write_text("survives")
        with self.assertRaises(HTTPException):
            bridge.move(bridge.MoveRequest(source="from_dir", destination="to_dir", overwrite=True))
        self.assertTrue((self.root / "from_dir").is_dir())
        self.assertEqual((self.root / "to_dir" / "keep").read_text(), "survives")

    def test_move_replaces_regular_file(self):
        (self.root / "destination").write_text("previous")
        bridge.move(bridge.MoveRequest(source="source", destination="destination", overwrite=True))
        self.assertEqual((self.root / "destination").read_text(), "keep")

    def test_delete_unlinks_symlink_instead_of_its_target(self):
        outside = Path(self.temp.name) / "outside"
        outside.write_text("outside-data")
        (self.root / "link").symlink_to(outside)
        bridge.delete(bridge.DeleteRequest(path="link"))
        self.assertEqual(outside.read_text(), "outside-data")
        self.assertFalse((self.root / "link").is_symlink())

    def test_policy_protects_direct_alias_and_ancestor_operations(self):
        (self.root / "alias").symlink_to(self.root / "private", target_is_directory=True)
        for path in ["private/key", "alias/key"]:
            with self.assertRaises(HTTPException):
                bridge.read_file(bridge.PathRequest(path=path))
        with self.assertRaises(HTTPException):
            bridge.write_file(bridge.WriteRequest(path="control/policy", content="bad"))
        with self.assertRaises(HTTPException):
            bridge.delete(bridge.DeleteRequest(path="control", recursive=True))
        self.assertEqual(bridge.read_file(bridge.PathRequest(path="control/policy"))["content"], "original")

    def test_desktop_environment_does_not_forward_credentials(self):
        with patch.dict(os.environ, {"CONTROL_PLANE_API_KEY": "synthetic", "AWS_SECRET_ACCESS_KEY": "synthetic", "DISPLAY": ":0"}):
            env = bridge.desktop_environment()
        self.assertNotIn("CONTROL_PLANE_API_KEY", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertEqual(env["DISPLAY"], ":0")

    def test_fixed_launcher_arguments_cannot_be_extended(self):
        policy = {"applications": {"demo": {"executable": "/usr/bin/true", "fixed_args": ["approved"], "allow_args": False}}}
        with patch.object(bridge, "BRIDGE_CONFIG", policy), patch.object(bridge, "launch_application") as launch:
            launch.return_value.pid = 123456
            launch.return_value.unit = "mcp-app-test.service"
            bridge.app_launch(bridge.AppLaunchRequest(app="demo"))
            self.assertEqual(launch.call_args.args[0], [str(Path("/usr/bin/true").resolve()), "approved"])
            with self.assertRaises(HTTPException):
                bridge.app_launch(bridge.AppLaunchRequest(app="demo", args=["unapproved"]))

    @unittest.skipUnless(os.environ.get("BRIDGE_SANDBOX_TESTS") == "1", "requires host Bubblewrap")
    def test_real_sandbox_hides_ipc_and_denied_files_and_protects_control(self):
        result = bridge.run_command(bridge.CommandRequest(command="test ! -S /run/user/$(id -u)/bus && test ! -e private/key && cat control/policy && echo no > control/policy", cwd="."))
        self.assertNotEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"].strip(), "original")
        self.assertEqual((self.root / "control" / "policy").read_text(), "original")
        result = bridge.run_command(bridge.CommandRequest(command="printf yes > valid-output"))
        self.assertEqual(result["returncode"], 0, result)
        self.assertEqual((self.root / "valid-output").read_text(), "yes")

    @unittest.skipUnless(os.environ.get("BRIDGE_SANDBOX_TESTS") == "1", "requires host Bubblewrap")
    def test_search_does_not_follow_external_symlinks_or_read_private_files(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "data").write_text("synthetic-external-marker")
        (self.root / "external-link").symlink_to(outside, target_is_directory=True)
        self.assertEqual(bridge.search(bridge.SearchRequest(query="synthetic-"))["matches"], "")
        self.assertIn("keep", bridge.search(bridge.SearchRequest(query="keep"))["matches"])

    @unittest.skipUnless(os.environ.get("BRIDGE_SANDBOX_TESTS") == "1", "requires host Bubblewrap")
    def test_patch_respects_read_only_control_but_can_edit_project(self):
        def diff(path):
            return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-original\n+changed\n"
        (self.root / "control" / "policy").write_text("original\n")
        with self.assertRaises(HTTPException):
            bridge.apply_patch(bridge.PatchRequest(patch=diff("control/policy")))
        self.assertEqual((self.root / "control" / "policy").read_text(), "original\n")
        (self.root / "editable").write_text("original\n")
        self.assertTrue(bridge.apply_patch(bridge.PatchRequest(patch=diff("editable")))["ok"])
        self.assertEqual((self.root / "editable").read_text(), "changed\n")


if __name__ == "__main__":
    unittest.main()
