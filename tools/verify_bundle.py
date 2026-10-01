"""Check that a built executable is self-contained.

The PyInstaller spec prunes Qt libraries the application never loads, and it is
easy to prune something that is still in use. A missing library of that kind does
not fail the build - it fails when the resulting executable is started, which on
a machine whose security policy blocks unsigned binaries may be never.

This script closes that gap. It reads the single-file archive, parses the PE
import table of every bundled module, and reports any import that is satisfied by
neither another bundled module nor a DLL that ships with Windows. A library that
was pruned while something still links against it shows up here.

Usage:
    pyinstaller packaging/battery_charge_notifier.spec
    python tools/verify_bundle.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "dist" / "BatteryChargeNotifier.exe"

from PyInstaller.archive.readers import CArchiveReader

SYSTEM32 = Path(r"C:\Windows\System32")

#: Libraries the pruning is expected to remove.
PRUNED = (
    "opengl32sw.dll",
    "qt6qml.dll",
    "qt6quick.dll",
    "qt6pdf.dll",
    "qt6svg.dll",
    "libcrypto-3.dll",
    "libssl-3.dll",
)

#: Libraries the application cannot start without.
REQUIRED = (
    "qt6core.dll",
    "qt6gui.dll",
    "qt6widgets.dll",
    "qt6network.dll",
    "qwindows.dll",
    "qico.dll",
)


def read_imports(data: bytes) -> list[str]:
    """Return the DLL names in the PE import directory of *data*.

    Args:
        data: Raw bytes of a PE image.

    Returns:
        Lowercased imported DLL names, or an empty list when the file is not a PE
        image or has no imports.
    """
    if data[:2] != b"MZ":
        return []
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        return []

    coff = pe_offset + 4
    num_sections = struct.unpack_from("<H", data, coff + 2)[0]
    size_optional = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    magic = struct.unpack_from("<H", data, optional)[0]

    # The data directories begin after the fixed part of the optional header,
    # whose size differs between PE32 and PE32+.
    directories = optional + (112 if magic == 0x20B else 96)
    import_rva, _import_size = struct.unpack_from("<II", data, directories + 8)
    if import_rva == 0:
        return []

    sections: list[tuple[int, int, int]] = []
    section_base = optional + size_optional
    for index in range(num_sections):
        offset = section_base + index * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, offset + 8
        )
        sections.append((virtual_address, max(virtual_size, raw_size), raw_pointer))

    def to_offset(rva: int) -> int | None:
        for virtual_address, size, raw_pointer in sections:
            if virtual_address <= rva < virtual_address + size:
                return raw_pointer + (rva - virtual_address)
        return None

    names: list[str] = []
    descriptor = import_rva
    for _ in range(256):  # bounded: a malformed table must not loop forever
        offset = to_offset(descriptor)
        if offset is None:
            break
        entry = data[offset : offset + 20]
        if len(entry) < 20 or entry == b"\0" * 20:
            break
        name_rva = struct.unpack_from("<I", entry, 12)[0]
        name_offset = to_offset(name_rva) if name_rva else None
        if name_offset is None:
            break
        end = data.index(b"\0", name_offset)
        names.append(data[name_offset:end].decode("ascii", "replace").lower())
        descriptor += 20
    return names


def is_system_dll(name: str) -> bool:
    """Whether Windows itself provides *name*.

    Args:
        name: Lowercased DLL file name.

    Returns:
        True for the API set stubs and for anything installed in System32.
    """
    if name.startswith(("api-ms-win-", "ext-ms-win-")):
        return True
    return (SYSTEM32 / name).exists()


def main(argv: list[str] | None = None) -> int:
    """Verify the dependency closure of a built executable.

    Args:
        argv: Command line arguments; the first may be the executable to check.

    Returns:
        Process exit status: 0 when the bundle is self-contained, 1 otherwise.
    """
    args = sys.argv[1:] if argv is None else argv
    exe = Path(args[0]) if args else DEFAULT_EXE
    if not exe.is_file():
        print(f"no build found at {exe}")
        print("build it first: pyinstaller packaging/battery_charge_notifier.spec")
        return 1

    reader = CArchiveReader(str(exe))
    toc = reader.toc
    print(f"bundle : {exe.name} ({exe.stat().st_size / 1_048_576:.1f} MiB)")
    print(f"entries: {len(toc)}")

    bundled: dict[str, bytes] = {}
    for name in toc:
        base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if base.endswith((".dll", ".pyd", ".exe")):
            try:
                bundled[base] = reader.extract(name)
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"  could not extract {name}: {exc!r}")
    print(f"modules: {len(bundled)}")
    print()

    # Assets and Python sources are not PE images; they yield no imports.
    available = set(bundled) | {"python3.dll"}
    problems: dict[str, set[str]] = {}
    for module, data in sorted(bundled.items()):
        for imported in read_imports(data):
            if imported not in available and not is_system_dll(imported):
                problems.setdefault(module, set()).add(imported)

    status = 0
    if problems:
        print("UNRESOLVED IMPORTS - a pruned library is still linked:")
        for module, imports in problems.items():
            print(f"  {module}: {sorted(imports)}")
        status = 1
    else:
        print("ok: every PE import resolves to a bundled module or a Windows DLL")

    print()
    print("pruned as intended:")
    for name in PRUNED:
        present = name in bundled
        print(f"  {name:<20} {'STILL PRESENT' if present else 'removed'}")
        status = status or int(present)

    print()
    print("required and present:")
    for name in REQUIRED:
        present = name in bundled
        print(f"  {name:<20} {'present' if present else 'MISSING'}")
        status = status or int(not present)

    return status


if __name__ == "__main__":
    sys.exit(main())
