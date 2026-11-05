"""Check the flashed echo fixture through the production USB adapter, without COM."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import threading
import time

from usb_transport import USBChannel, USBConfig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.serial <= 0 or args.output.exists() or not args.output.parent.is_dir():
        parser.error("Use a positive probe serial and a new output file in an existing directory.")
    channel = USBChannel(USBConfig(target="STM32H750VB", serial_number=args.serial,
                                  interface=1, speed=1000, startup_reset=False), threading.Event())
    record: dict[str, object] = {
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "actual USBChannel/probe/Target; no serial, Bridge or GUI",
        "probe_serial": args.serial, "target": "STM32H750VB", "speed_khz": 1000,
        "interface": "SWD", "startup_reset": False,
        "pattern": "bytes(range(256)) repeated 256 times",
        "chunk_bytes": 1024, "loop_sleep_seconds": 0.001,
    }
    try:
        channel.open()
        record["observed_probe"] = channel.serial_number
        initial = bytearray()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            block = channel.read()
            if not block:
                break
            initial.extend(block)
        record["initial_buffer_hex"] = initial.hex()
        expected = bytes(range(256)) * 256
        sent = 0
        received = bytearray()
        started = time.perf_counter()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and (sent < len(expected) or len(received) < len(expected)):
            if sent < len(expected):
                chunk = expected[sent:sent + 1024]
                count = channel.write(chunk)
                assert 0 <= count <= len(chunk), "Invalid accepted byte count"
                sent += count
            received.extend(channel.read() or b"")
            time.sleep(0.001)
        elapsed = time.perf_counter() - started
        record.update(sent_bytes=sent, received_bytes=len(received), elapsed_seconds=elapsed,
                      expected_sha256=hashlib.sha256(expected).hexdigest(),
                      received_sha256=hashlib.sha256(received).hexdigest())
        assert bytes(received) == expected, "Echo byte values/order differ or timed out"
        record.update(result="pass", observed_bytes_per_second_each_direction=len(expected) / elapsed)
    except BaseException as error:
        record.update(result="fail", error=repr(error))
        raise
    finally:
        try:
            channel.close()
            record["cleanup_completed"] = True
        except BaseException as error:
            record.update(result="fail", cleanup_error=repr(error))
            raise
        finally:
            args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
