"""Background Target catalog acquisition; independent of Qt and bridge sessions."""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import sys
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET


Record = tuple[str, ...]


@dataclass(frozen=True)
class CatalogSource:
    commander: Path
    library: Path
    script: bytes

    def identity(self) -> dict[str, str]:
        result = {'script_sha256': hashlib.sha256(self.script).hexdigest()}
        for name, path in (('commander', self.commander), ('library', self.library)):
            result[name + '_path'] = os.path.normcase(str(path.resolve(strict=True)))
            result[name + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result


def resource_directory() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


def _resolve_source() -> CatalogSource:
    import pylink.library  # type: ignore[import-untyped]
    library = pylink.library.Library()
    try:
        if not library._path:
            raise FileNotFoundError('J-Link library not found; install the J-Link software pack')
        path = Path(library._path).resolve(strict=True)
    finally:
        library.unload()
    if sys.platform != 'win32':
        raise RuntimeError('Automatic catalog export is supported on Windows only')
    return CatalogSource(path.parent / 'JLink.exe', path,
                         (resource_directory() / 'JLinkCommandFile.jlink').read_bytes())


EXPORT_TIMEOUT = 30.0


def _export(source: CatalogSource, directory: Path, cancelled: threading.Event) -> None:
    script = directory / 'JLinkCommandFile.jlink'
    script.write_bytes(source.script)
    environment = os.environ.copy()
    environment['PATH'] = str(source.commander.parent) + os.pathsep + environment.get('PATH', '')
    with (directory / 'commander.log').open('wb') as log:
        process = subprocess.Popen([str(source.commander), '-CommandFile', str(script)],
                                   cwd=directory, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        try:
            deadline = time.monotonic() + EXPORT_TIMEOUT
            while process.poll() is None:
                if cancelled.wait(0.05):
                    raise RuntimeError('Catalog refresh cancelled')
                if time.monotonic() >= deadline:
                    raise TimeoutError(f'Commander export exceeded {EXPORT_TIMEOUT:g} seconds')
            if process.returncode:
                raise RuntimeError(f'Commander export failed (exit {process.returncode})')
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


@dataclass(frozen=True)
class CatalogSnapshot:
    state: str = 'loading'
    records: tuple[Record, ...] = ()
    reason: str = ''
    fingerprint: str = ''


def _parse(xml: str) -> tuple[Record, ...]:
    root = ET.fromstring(xml)
    records = []
    for vendor in root.findall('VendorInfo'):
        for device in vendor.findall('DeviceInfo'):
            name, core = device.attrib['Name'], device.attrib['Core']
            manufacturer = vendor.attrib['Name']
            if not all(value.strip() for value in (name, core, manufacturer)):
                raise ValueError('Empty required Target field')
            flash = sum(int(bank.attrib['Size'], 16)
                        for bank in device.findall('FlashBankInfo'))
            ram = int(device.get('WorkRAMSize', '0'), 16)
            if flash < 0 or ram < 0:
                raise ValueError('Negative Target memory size')
            size = f'{flash // 1024} KB' if flash < 1024**2 else f'{flash // 1024**2} MB'
            records.append((manufacturer, name, core, '1', size, f'{ram // 1024} KB'))
    if root.tag not in ('DeviceDatabase', 'Database') or not records:
        raise ValueError('XML contains no usable Target records')
    return tuple(records)


class DeviceCatalog:
    def __init__(self, *, cache_dir: Path | None = None, baseline: Path | None = None,
                 resolve_source: Callable[[], CatalogSource] = _resolve_source,
                 export: Callable[[CatalogSource, Path, threading.Event], None] = _export) -> None:
        if cache_dir is None:
            cache_dir = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'RTT2UART'
        self._cache = cache_dir / 'catalog.json'
        self._baseline = baseline if baseline is not None else resource_directory() / 'JLinkDevicesBuildIn.xml'
        self._resolve_source = resolve_source
        self._export = export
        self._snapshot = CatalogSnapshot()
        self._worker: threading.Thread | None = None
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._busy = False
        self._failures: dict[str, str] = {}

    @property
    def snapshot(self) -> CatalogSnapshot:
        return self._snapshot

    @property
    def busy(self) -> bool:
        return self._busy

    def prepare(self, *, retry: bool = False, recheck: bool = False) -> None:
        with self._lock:
            if self._cancelled.is_set() or self._busy:
                return
            if self._worker is not None and not (retry or recheck):
                return
            self._busy = True
            self._snapshot = CatalogSnapshot()
            self._worker = threading.Thread(target=self._run, args=(retry,), name='Target catalog')
            self._worker.start()

    def _run(self, retry: bool) -> None:
        result = self._prepare(retry)
        with self._lock:
            if not self._cancelled.is_set():
                self._snapshot = result
            self._busy = False

    def _prepare(self, retry: bool) -> CatalogSnapshot:
        previous = None
        try:
            previous = json.loads(self._cache.read_text(encoding='utf-8'))
            if not isinstance(previous['source'], dict):
                raise ValueError('Invalid cache source metadata')
            xml = previous['xml']
            if hashlib.sha256(xml.encode('utf-8')).hexdigest() != previous['xml_sha256']:
                raise ValueError('Cache data/provenance mismatch')
            _parse(xml)
        except Exception:
            previous = None
        fingerprint = ''
        try:
            source = self._resolve_source()
            identity = source.identity()
            fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            if not retry and previous is not None and previous['source'] == identity:
                return CatalogSnapshot('cached', _parse(previous['xml']), fingerprint=fingerprint)
            if not retry and fingerprint in self._failures:
                raise RuntimeError(self._failures[fingerprint])
            with tempfile.TemporaryDirectory(prefix='rtt2uart-catalog-') as temporary:
                directory = Path(temporary)
                self._export(source, directory, self._cancelled)
                xml = (directory / 'JLinkDevicesBuildIn.xml').read_text(encoding='utf-8')
                records = _parse(xml)
                if self._resolve_source().identity() != identity:
                    raise RuntimeError('J-Link export inputs changed during refresh; Retry')
                generation = {'source': identity, 'xml': xml,
                              'xml_sha256': hashlib.sha256(xml.encode('utf-8')).hexdigest()}
                self._cache.parent.mkdir(parents=True, exist_ok=True)
                staged = self._cache.with_suffix('.tmp')
                try:
                    with staged.open('w', encoding='utf-8') as output:
                        json.dump(generation, output)
                        output.flush()
                        os.fsync(output.fileno())
                    with self._lock:
                        if self._cancelled.is_set():
                            return CatalogSnapshot('closed')
                        os.replace(staged, self._cache)
                    return CatalogSnapshot('fresh', records, fingerprint=fingerprint)
                finally:
                    staged.unlink(missing_ok=True)
        except Exception as error:
            if fingerprint:
                self._failures[fingerprint] = str(error)
            try:
                records = _parse(previous['xml'] if previous is not None else
                                 self._baseline.read_text(encoding='utf-8'))
                return CatalogSnapshot('fallback', records, str(error))
            except Exception as baseline_error:
                return CatalogSnapshot('error', reason=f'{error}; {baseline_error}')

    def close(self, *, wait: bool = True) -> None:
        with self._lock:
            self._cancelled.set()
            self._snapshot = CatalogSnapshot('closed')
        if wait and self._worker is not None:
            self._worker.join()
