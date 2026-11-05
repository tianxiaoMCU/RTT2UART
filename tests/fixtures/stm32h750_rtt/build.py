"""Build/check the hardware-only echo fixture; never connect or flash a Target."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zipfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, required=True, help="ARM GCC bin directory")
    parser.add_argument("--rtt-zip", type=Path, required=True, help="Installed SEGGER_RTT_V754d.zip")
    parser.add_argument("--fault-cycle", action="store_true", help="Build the isolated command-driven H05 fixture")
    parser.add_argument("--core-observer", action="store_true", help="Build the H08 internal counter observer with H05 cycle")
    parser.add_argument("--output-dir", type=Path, help="Use a fresh build directory when preserving earlier evidence")
    args = parser.parse_args()
    fixture = Path(__file__).resolve().parent
    fault_cycle = args.fault_cycle or args.core_observer
    name = "issue13-h750-core-observer" if args.core_observer else (
        "issue13-h750-fault-cycle" if fault_cycle else "issue13-h750")
    output = args.output_dir if args.output_dir is not None else fixture.parents[2] / "build" / name
    output.mkdir(parents=True, exist_ok=True)
    expected = "6b18a9d1dd47c2770ef65b977a2534471f13e35082d0597ab6ceb6364d75de73"
    if hashlib.sha256(args.rtt_zip.read_bytes()).hexdigest() != expected:
        raise SystemExit("Expected the recorded SEGGER RTT 7.54d archive; revalidate other versions first.")
    vendor = output / "segger-rtt-7.54d" / "RTT"
    vendor.mkdir(parents=True, exist_ok=True)
    config = vendor.parent / "Config"
    config.mkdir(exist_ok=True)
    (config / "SEGGER_RTT_Conf.h").write_bytes((fixture / "SEGGER_RTT_Conf.h").read_bytes())
    with zipfile.ZipFile(args.rtt_zip) as archive:
        for name in ("SEGGER_RTT.c", "SEGGER_RTT.h"):
            (vendor / name).write_bytes(archive.read("RTT/" + name))
    gcc = args.toolchain / "arm-none-eabi-gcc.exe"
    elf = output / "rtt-echo.elf"
    binary = output / "rtt-echo.bin"
    command = [str(gcc), "-mcpu=cortex-m7", "-mthumb", "-mfloat-abi=soft",
               "-Os", "-g3", "-Wall", "-Wextra", "-Werror", "-ffreestanding",
               "-ffunction-sections", "-fdata-sections", "-nostartfiles",
               "--specs=nano.specs", "--specs=nosys.specs", "-I", str(fixture),
               "-I", str(vendor), str(fixture / "main.c"), str(vendor / "SEGGER_RTT.c"),
               "-T", str(fixture / "stm32h750.ld"), "-Wl,--gc-sections",
               "-Wl,-Map=" + str(output / "rtt-echo.map"), "-o", str(elf)]
    if fault_cycle:
        command += ["-DRTT_FAULT_CYCLE", str(fixture / "fault_cycle.c")]
    if args.core_observer:
        command += ["-DCORE_OBSERVER", str(fixture / "core_observer.c")]
    subprocess.run(command, check=True)
    subprocess.run([str(args.toolchain / "arm-none-eabi-objcopy.exe"), "-O", "binary",
                    str(elf), str(binary)], check=True)
    symbols = {}
    for line in subprocess.check_output([str(args.toolchain / "arm-none-eabi-nm.exe"),
                                         "--defined-only", str(elf)], text=True).splitlines():
        address, _, name = line.split(maxsplit=2)
        symbols[name] = int(address, 16)
    image = binary.read_bytes()
    stack, reset = struct.unpack_from("<II", image)
    assert stack == 0x24080000 and stack % 8 == 0, "Bad initial stack"
    assert reset & 1 and 0x08000000 <= reset < 0x08000000 + len(image), "Bad reset vector"
    assert 0 < len(image) <= 128 * 1024, "Image exceeds STM32H750VB flash"
    assert symbols["_sidata"] % 4 == 0, "Unaligned word-copy source"
    assert 0x24000000 <= symbols["_SEGGER_RTT"] < symbols["_ebss"] < stack - 4096
    record = {"compiler": subprocess.check_output([str(gcc), "--version"], text=True).splitlines()[0],
              "command": command, "rtt_archive_sha256": expected,
              "source_sha256": {name: hashlib.sha256((fixture / name).read_bytes()).hexdigest()
                                for name in (("main.c", "SEGGER_RTT_Conf.h", "stm32h750.ld", "build.py")
                                             + (("fault_cycle.c",) if fault_cycle else ())
                                             + (("core_observer.c",) if args.core_observer else ()))},
              "binary_bytes": len(image), "binary_sha256": hashlib.sha256(image).hexdigest(),
              "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
              "rtt_control_block": hex(symbols["_SEGGER_RTT"]),
              "test_stats": hex(symbols["test_stats"]), "self_check": "passed"}
    if fault_cycle:
        assert symbols["fault_stats"] + 44 < stack - 4096
        record.update(fault_stats=hex(symbols["fault_stats"]),
                      command_hex=b"\x1b[H05:RTT-OFF]\r\n".hex(), delay_ms=3000, off_ms=15000)
    if args.core_observer:
        assert symbols["core_observer"] >= symbols["_ebss"]
        assert symbols["_noinit_end"] - symbols["core_observer"] == (22 + 64 * 8) * 4
        record.update(core_observer=hex(symbols["core_observer"]), observer_words=22 + 64 * 8,
                      capture_ticks=2880000000, clock_hz=64000000, threshold_ticks=6400,
                      observer_magic=hex(0x48303854), observer_counters="TIM2 / debug-frozen TIM5")
    (output / "firmware-build.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
