"""Catalog behavior through the same preparation/snapshot seam as the GUI."""
from pathlib import Path
import tempfile
import unittest
import threading
import os
import subprocess
import sys
from unittest.mock import patch

from device_catalog import DeviceCatalog, CatalogSource
from tests.fakes import wait_until


FIXTURE = Path(__file__).parent / 'fixtures' / 'device-list.xml'


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def catalog(self, **kwargs):
        catalog = DeviceCatalog(cache_dir=self.root / 'cache', baseline=FIXTURE,
                                resolve_source=lambda: (_ for _ in ()).throw(
                                    OSError('J-Link not installed')), **kwargs)
        self.addCleanup(catalog.close)
        return catalog

    def resolved(self, catalog):
        catalog.prepare()
        wait_until(lambda: catalog.snapshot.state != 'loading')
        return catalog.snapshot

    def test_missing_tools_expose_validated_baseline_and_preserve_table_mapping(self):
        result = self.resolved(self.catalog())
        self.assertEqual(result.state, 'fallback')
        self.assertIn('J-Link not installed', result.reason)
        self.assertEqual(result.records, (
            ('Test', 'STM32F407VG', 'Cortex-M4', '1', '1 MB', '128 KB'),
            ('Test', 'STM32F103C8', 'Cortex-M3', '1', '64 KB', '0 KB')))

    def test_first_export_then_restart_reuses_a_matching_atomic_generation(self):
        commander = self.root / 'JLink.exe'
        library = self.root / 'JLink_x64.dll'
        commander.write_bytes(b'commander')
        library.write_bytes(b'library')
        source = CatalogSource(commander, library, b'ExpDevListXML JLinkDevicesBuildIn.xml\nExit\n')
        calls = []
        def export(source, directory, cancelled):
            calls.append(source)
            (directory / 'JLinkDevicesBuildIn.xml').write_bytes(FIXTURE.read_bytes())
        def new():
            catalog = DeviceCatalog(cache_dir=self.root / 'cache', baseline=FIXTURE,
                                    resolve_source=lambda: source, export=export)
            self.addCleanup(catalog.close)
            return catalog
        first = self.resolved(new())
        self.assertEqual(first.state, 'fresh')
        second = self.resolved(new())
        self.assertEqual(second.state, 'cached')
        self.assertEqual(second.fingerprint, first.fingerprint)
        self.assertEqual(second.records, first.records)
        self.assertEqual(len(calls), 1)

    def controlled(self, export=None, baseline=FIXTURE):
        self.commander = self.root / 'JLink.exe'
        self.library = self.root / 'JLink_x64.dll'
        self.commander.write_bytes(b'commander')
        self.library.write_bytes(b'library')
        self.script = b'ExpDevListXML JLinkDevicesBuildIn.xml\nExit\n'
        self.calls = []
        def resolve():
            return CatalogSource(self.commander, self.library, self.script)
        def run(source, directory, cancelled):
            self.calls.append(source)
            if export:
                export(source, directory, cancelled)
            else:
                (directory / 'JLinkDevicesBuildIn.xml').write_bytes(FIXTURE.read_bytes())
        self.options = dict(cache_dir=self.root / 'cache', baseline=baseline,
                            resolve_source=resolve, export=run)
        catalog = DeviceCatalog(**self.options)
        self.addCleanup(catalog.close)
        return catalog

    def wait_result(self, catalog):
        wait_until(lambda: catalog.snapshot.state != 'loading')
        return catalog.snapshot

    def test_failure_suppression_explicit_retry_and_new_source(self):
        def fail(*args):
            raise OSError('Repair Commander')
        catalog = self.controlled(fail)
        first = self.resolved(catalog)
        self.assertEqual(first.state, 'fallback')
        for _ in range(3):
            catalog.prepare()
        self.assertEqual(len(self.calls), 1)
        catalog.prepare(retry=True)
        self.wait_result(catalog)
        self.assertEqual(len(self.calls), 2)
        catalog.prepare(recheck=True)
        self.wait_result(catalog)
        self.assertEqual(len(self.calls), 2)
        self.library.write_bytes(b'changed')
        catalog.prepare(recheck=True)
        self.wait_result(catalog)
        self.assertEqual(len(self.calls), 3)

    def test_loading_coalesces_requests_and_close_invalidates_delayed_output(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(source, directory, cancelled):
            entered.set()
            release.wait(2)
            (directory / 'JLinkDevicesBuildIn.xml').write_bytes(FIXTURE.read_bytes())
        catalog = self.controlled(delayed)
        self.addCleanup(release.set)
        catalog.prepare()
        self.assertTrue(entered.wait(1))
        for _ in range(3):
            catalog.prepare(retry=True)
        self.assertEqual(catalog.snapshot.state, 'loading')
        self.assertEqual(len(self.calls), 1)
        catalog.close(wait=False)
        release.set()
        wait_until(lambda: not catalog.busy)
        self.assertFalse((self.root / 'cache' / 'catalog.json').exists())
        self.assertEqual(catalog.snapshot.state, 'closed')

    def test_content_changes_in_each_known_input_invalidate_even_with_same_stat(self):
        catalog = self.controlled()
        initial = self.resolved(catalog)
        for path in (self.commander, self.library):
            stat = path.stat()
            path.write_bytes(b'X' * stat.st_size)
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            catalog.prepare(recheck=True)
            changed = self.wait_result(catalog)
            self.assertEqual(changed.state, 'fresh')
            self.assertNotEqual(changed.fingerprint, initial.fingerprint)
            initial = changed
        self.script += b'\n'
        catalog.prepare(recheck=True)
        self.assertEqual(self.wait_result(catalog).state, 'fresh')
        unused = self.root / 'unused-installation'
        unused.mkdir()
        (unused / 'JLink.exe').write_bytes(b'newest')
        catalog.prepare(recheck=True)
        self.assertEqual(self.wait_result(catalog).state, 'cached')
        self.assertEqual(len(self.calls), 4)

    def test_retry_forces_export_even_when_known_inputs_still_match(self):
        catalog = self.controlled()
        self.resolved(catalog)
        catalog.prepare(retry=True)
        self.assertEqual(self.wait_result(catalog).state, 'fresh')
        self.assertEqual(len(self.calls), 2)

    def test_invalid_cache_rebuilds_and_ignores_interrupted_staging_file(self):
        catalog = self.controlled()
        self.resolved(catalog)
        path = self.root / 'cache' / 'catalog.json'
        original = path.read_bytes()
        for bad in (b'', b'{', b'{}', original.replace(b'STM32F407VG', b'CORRUPTED'),
                    original.replace(b'"source":', b'"missing":')):
            with self.subTest(bad=bad[:30]):
                path.write_bytes(bad)
                (path.parent / 'catalog.tmp').write_bytes(b'partial publication')
                catalog.prepare(recheck=True)
                self.assertEqual(self.wait_result(catalog).state, 'fresh')

    def test_failed_commit_preserves_last_generation_then_explicit_retry_recovers(self):
        catalog = self.controlled()
        self.resolved(catalog)
        path = self.root / 'cache' / 'catalog.json'
        previous = path.read_bytes()
        self.library.write_bytes(b'changed')
        with patch('device_catalog.os.replace', side_effect=PermissionError('cache locked')):
            catalog.prepare(recheck=True)
            result = self.wait_result(catalog)
        self.assertEqual(result.state, 'fallback')
        self.assertIn('cache locked', result.reason)
        self.assertEqual(path.read_bytes(), previous)
        catalog.prepare(retry=True)
        self.assertEqual(self.wait_result(catalog).state, 'fresh')
        self.assertNotEqual(path.read_bytes(), previous)

    def test_export_failures_and_invalid_output_keep_last_good_without_success_marker(self):
        catalog = self.controlled()
        self.resolved(catalog)
        previous = (self.root / 'cache' / 'catalog.json').read_bytes()
        for output in (None, '', '<DeviceDatabase>', '<DeviceDatabase/>',
                       '<Other><VendorInfo Name="A"><DeviceInfo Name="B" Core="C"/></VendorInfo></Other>',
                       '<DeviceDatabase><VendorInfo Name="A"><DeviceInfo Name="B"/></VendorInfo></DeviceDatabase>',
                       '<Database><VendorInfo Name="A"><DeviceInfo Name="B" Core="C" WorkRAMSize="bad!"/></VendorInfo></Database>'):
            def invalid(source, directory, cancelled):
                if output is not None:
                    (directory / 'JLinkDevicesBuildIn.xml').write_text(output, encoding='utf-8')
            self.options['export'] = invalid
            self.library.write_bytes(str(output).encode())
            other = DeviceCatalog(**self.options)
            self.addCleanup(other.close)
            result = self.resolved(other)
            self.assertEqual(result.state, 'fallback', output)
            self.assertEqual(len(result.records), 2)
            self.assertTrue(result.reason)
            self.assertFalse(result.fingerprint)
            self.assertEqual((self.root / 'cache' / 'catalog.json').read_bytes(), previous)

    def test_unusable_baseline_and_unwritable_cache_are_recoverable(self):
        missing = self.root / 'absent.xml'
        bad = DeviceCatalog(
            cache_dir=self.root / 'blocked', baseline=missing,
            resolve_source=lambda: (_ for _ in ()).throw(OSError('no tools')))
        self.addCleanup(bad.close)
        self.assertEqual(self.resolved(bad).state, 'error')
        catalog = self.controlled()
        (self.root / 'cache').write_bytes(b'not a directory')
        self.assertEqual(self.resolved(catalog).state, 'fallback')

    def test_source_change_during_export_never_publishes_old_completion(self):
        def change(source, directory, cancelled):
            (directory / 'JLinkDevicesBuildIn.xml').write_bytes(FIXTURE.read_bytes())
            self.library.write_bytes(b'new source')
        catalog = self.controlled(change)
        result = self.resolved(catalog)
        self.assertEqual(result.state, 'fallback')
        self.assertIn('changed during refresh', result.reason)
        self.assertFalse((self.root / 'cache' / 'catalog.json').exists())
        catalog.prepare(recheck=True)
        self.assertEqual(self.wait_result(catalog).state, 'fresh')

    def test_real_child_timeout_launch_failure_exit_and_cancellation_are_owned(self):
        catalog = self.controlled()
        del self.options['export']
        actual_popen = subprocess.Popen
        environment = os.environ.copy()
        working_directory = os.getcwd()
        for command, text in ((['-c', 'import time; time.sleep(10)'], 'exceeded'),
                              (['-c', 'raise SystemExit(9)'], 'exit 9')):
            children = []
            def launch(args, **kwargs):
                self.assertEqual(Path(args[0]), self.commander)
                self.assertEqual(args[1], '-CommandFile')
                self.assertEqual(Path(args[2]).read_bytes(), self.script)
                self.assertNotEqual(str(kwargs['cwd']), working_directory)
                self.assertIsNot(kwargs['env'], os.environ)
                child = actual_popen([sys.executable, *command], **kwargs)
                children.append(child)
                return child
            with patch('device_catalog.subprocess.Popen', side_effect=launch), patch('device_catalog.EXPORT_TIMEOUT', 0.15):
                other = DeviceCatalog(**self.options)
                self.addCleanup(other.close)
                result = self.resolved(other)
            self.assertEqual(result.state, 'fallback')
            self.assertIn(text, result.reason)
            self.assertIsNotNone(children[0].poll())
        with patch('device_catalog.subprocess.Popen', side_effect=OSError('cannot launch')):
            other = DeviceCatalog(**self.options)
            self.addCleanup(other.close)
            self.assertIn('cannot launch', self.resolved(other).reason)
        with patch('device_catalog.subprocess.Popen', side_effect=launch):
            command = ['-c', 'import time; time.sleep(10)']
            other = DeviceCatalog(**self.options)
            other.prepare()
            wait_until(lambda: len(children) == 2)
            other.close()
            self.assertEqual(other.snapshot.state, 'closed')
            self.assertIsNotNone(children[-1].poll())
        self.assertEqual(os.environ, environment)
        self.assertEqual(os.getcwd(), working_directory)


if __name__ == '__main__':
    unittest.main()
