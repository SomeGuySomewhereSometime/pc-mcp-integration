"""Check desktop MCP output and local enablement without accessing the desktop."""
import copy
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('BRIDGE_WORKSPACE', '/home/user')
import mcp_server


class DesktopMCPTests(unittest.TestCase):
    def test_image_is_native_content_not_duplicate_base64_metadata(self):
        result = {'snapshot_id': 's', 'image': {'data': 'aGVsbG8=', 'width': 10, 'height': 10}}
        r = mcp_server.desktop_result(result)
        self.assertEqual([c.type for c in r.content], ['text', 'image'])
        self.assertEqual(r.content[1].data, 'aGVsbG8=')
        self.assertNotIn('aGVsbG8=', r.content[0].text)
        self.assertNotIn('data', r.structured_content['image'])

    def test_partial_failure_retains_receipts_and_native_image(self):
        r = mcp_server.desktop_result({'ok': False, 'completed': 1, 'observation': {
            'image': {'data': 'aGVsbG8=', 'width': 10}}})
        self.assertTrue(r.is_error)
        self.assertEqual(r.structured_content['completed'], 1)
        self.assertEqual(r.content[1].type, 'image')

    def test_disabled_desktop_never_starts_helper(self):
        with patch.object(mcp_server.bridge, 'BRIDGE_CONFIG', {}), patch.object(mcp_server.desktop_client, 'call') as call:
            with self.assertRaisesRegex(mcp_server.ToolError, 'disabled'):
                mcp_server.desktop_status()
            call.assert_not_called()

    def test_enabled_desktop_uses_only_fixed_operation(self):
        with patch.object(mcp_server.bridge, 'BRIDGE_CONFIG', {'desktop': {'enabled': True}}), patch.object(mcp_server.desktop_client, 'call', return_value={}) as call:
            mcp_server.desktop_status()
            call.assert_called_once_with('status')


if __name__ == '__main__':
    unittest.main()
