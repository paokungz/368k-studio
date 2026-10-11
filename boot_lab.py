#!/usr/bin/env python3
"""Offline-only Zontes 368K animation builder. No network or flashing code.

Supports the backed-up Android boot header v2 image with no second-stage or
recovery DTBO payload. Preserves the kernel, DTB, CPIO records and partition
suffix. Uses AOSP v2 image-ID ordering, including the zero recovery size.
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import io
import json
import pathlib
import struct
import sys
from dataclasses import dataclass

STOCK_SHA256 = "5440329a310e624ff41fdbdf96420ee5d44ddc8c8e72798e17dae86a3e35ad26"
TARGET = "animation.fex"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def aligned(n, alignment):
    return (n + alignment - 1) // alignment * alignment


@dataclass
class Boot:
    data: bytes
    page: int
    kernel_size: int
    ramdisk_size: int
    ramdisk_start: int
    dtb_size: int
    dtb_start: int
    image_end: int

    @property
    def kernel(self):
        return self.data[self.page:self.page + self.kernel_size]

    @property
    def ramdisk(self):
        return self.data[self.ramdisk_start:self.ramdisk_start + self.ramdisk_size]

    @property
    def dtb(self):
        return self.data[self.dtb_start:self.dtb_start + self.dtb_size]

    def image_id(self):
        digest = hashlib.sha1()
        # Android boot v2: kernel, ramdisk, second, recovery DTBO, DTB.
        for payload in (self.kernel, self.ramdisk, b"", b"", self.dtb):
            digest.update(payload)
            digest.update(struct.pack("<I", len(payload)))
        return digest.digest() + b"\0" * 12

    def summary(self):
        return {
            "header_version": 2, "page_size": self.page,
            "kernel_bytes": self.kernel_size,
            "kernel_sha256": sha256(self.kernel),
            "ramdisk_bytes": self.ramdisk_size,
            "ramdisk_offset": self.ramdisk_start,
            "dtb_bytes": self.dtb_size, "dtb_offset": self.dtb_start,
            "dtb_sha256": sha256(self.dtb), "padded_image_bytes": self.image_end,
            "file_bytes": len(self.data), "image_id": self.image_id().hex(),
        }


def parse_boot(data, check_id=True):
    require(len(data) >= 2048 and data[:8] == b"ANDROID!", "Not an Android boot image")
    k, _ka, r, _ra, second, _sa, _tags, page, version, _os = struct.unpack_from("<10I", data, 8)
    require(version == 2, "This tool supports boot header v2 only")
    require(page in (2048, 4096, 8192, 16384), "Unsupported page size")
    require(second == 0, "Second-stage payload is unsupported; refusing to repack")
    recovery_size = struct.unpack_from("<I", data, 1632)[0]
    recovery_offset = struct.unpack_from("<Q", data, 1636)[0]
    header_size = struct.unpack_from("<I", data, 1644)[0]
    dtb_size = struct.unpack_from("<I", data, 1648)[0]
    require(recovery_size == 0 and recovery_offset == 0, "Recovery DTBO is unsupported")
    require(header_size == 1660, "Unexpected v2 header size")
    require(k > 0 and r > 0 and dtb_size >= 40, "Missing boot payload")
    ramdisk_start = page + aligned(k, page)
    dtb_start = ramdisk_start + aligned(r, page)
    image_end = dtb_start + aligned(dtb_size, page)
    require(image_end <= len(data), "Truncated boot image or partition")
    require(data[dtb_start:dtb_start + 4] == b"\xd0\x0d\xfe\xed", "DTB magic mismatch")
    require(struct.unpack_from(">I", data, dtb_start + 4)[0] == dtb_size, "DTB total-size mismatch")
    require(data[ramdisk_start:ramdisk_start + 2] == b"\x1f\x8b", "Ramdisk is not gzip")
    boot = Boot(data, page, k, r, ramdisk_start, dtb_size, dtb_start, image_end)
    if check_id:
        require(data[576:608] == boot.image_id(), "Android v2 image ID does not match payloads")
    return boot


@dataclass
class Entry:
    name: str
    fields: tuple
    start: int
    data_start: int
    next_start: int
    content: bytes
    raw: bytes


def parse_cpio(data):
    entries = []
    names = set()
    pos = 0
    while pos + 110 <= len(data):
        magic = data[pos:pos + 6]
        require(magic in (b"070701", b"070702"), "Invalid newc CPIO header")
        fields = tuple(int(data[pos + 6 + i * 8:pos + 14 + i * 8], 16) for i in range(13))
        size, name_size = fields[6], fields[11]
        require(0 < name_size <= len(data) - pos - 110, "Invalid CPIO filename length")
        name_bytes = data[pos + 110:pos + 110 + name_size]
        require(name_bytes[-1:] == b"\0", "CPIO filename is not terminated")
        name = name_bytes[:-1].decode("utf-8")
        require(name not in names, "Duplicate CPIO entry: " + name)
        names.add(name)
        data_start = aligned(pos + 110 + name_size, 4)
        next_start = aligned(data_start + size, 4)
        require(next_start <= len(data), "Truncated CPIO content")
        content = data[data_start:data_start + size]
        if magic == b"070702":
            require(sum(content) & 0xffffffff == fields[12], "CPIO CRC mismatch")
        entries.append(Entry(name, fields, pos, data_start, next_start, content, data[pos:next_start]))
        pos = next_start
        if name == "TRAILER!!!":
            require(size == 0 and not any(data[pos:]), "Unexpected nonzero CPIO suffix")
            return entries
    raise ValueError("No CPIO trailer")


def animation_entry(entries):
    found = [entry for entry in entries if entry.name == TARGET]
    require(len(found) == 1, "Expected exactly one animation.fex at initramfs root")
    entry = found[0]
    require(entry.fields[1] & 0xf000 == 0x8000, "animation.fex is not a regular file")
    require(entry.fields[4] == 1, "Hard-linked animation.fex is unsupported")
    return entry


def replace_animation(cpio, replacement):
    entry = animation_entry(parse_cpio(cpio))
    prefix = bytearray(cpio[entry.start:entry.data_start])
    # Preserve all metadata except file size and, for newc CRC, checksum.
    prefix[54:62] = f"{len(replacement):08x}".encode("ascii")
    if prefix[:6] == b"070702":
        prefix[102:110] = f"{sum(replacement) & 0xffffffff:08x}".encode("ascii")
    record = bytes(prefix) + replacement + b"\0" * ((-len(replacement)) % 4)
    updated = cpio[:entry.start] + record + cpio[entry.next_start:]
    return updated + b"\0" * ((-len(updated)) % 512)


def jpeg_info(data):
    require(data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9", "Invalid JPEG boundaries")
    pos = 2
    while pos < len(data):
        require(data[pos] == 255, "Invalid JPEG marker")
        while pos < len(data) and data[pos] == 255:
            pos += 1
        require(pos < len(data), "Truncated JPEG marker")
        marker = data[pos]
        pos += 1
        if marker in (0xda, 0xd9):
            break
        if marker == 1 or 0xd0 <= marker <= 0xd8:
            continue
        require(pos + 2 <= len(data), "Truncated JPEG segment")
        length = struct.unpack_from(">H", data, pos)[0]
        require(length >= 2 and pos + length <= len(data), "Invalid JPEG segment size")
        if marker in (0xc0, 0xc1, 0xc2):
            require(length >= 8, "Truncated SOF")
            height, width = struct.unpack_from(">HH", data, pos + 3)
            components = data[pos + 7]
            require(length == 8 + 3 * components, "Invalid SOF size")
            ids = [data[pos + 8 + 3 * j] for j in range(components)]
            sampling = [data[pos + 9 + 3 * j] for j in range(components)]
            return {"sof_marker": marker, "precision": data[pos + 2],
                    "width": width, "height": height,
                    "component_ids": ids, "sampling": sampling}
        pos += length
    raise ValueError("No supported JPEG SOF")


def parse_fex(data):
    require(len(data) >= 8, "FEX too short")
    count = struct.unpack_from("<I", data)[0]
    require(1 <= count <= 1000, "Invalid frame count")
    frames = []
    formats = []
    pos = 4
    for _ in range(count):
        require(pos + 4 <= len(data), "Truncated FEX length")
        size = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        require(size > 0 and pos + size <= len(data), "Truncated FEX frame")
        frame = data[pos:pos + size]
        frames.append(frame)
        formats.append(jpeg_info(frame))
        pos += size
    require(pos == len(data), "Unexpected bytes after final FEX frame")
    require(all(info == formats[0] for info in formats), "Mixed JPEG frame formats")
    info = formats[0]
    require(info["sof_marker"] == 0xc0 and info["precision"] == 8, "JPEG must be 8-bit baseline")
    require(info["component_ids"] == [1, 2, 3] and info["sampling"] == [0x22, 0x11, 0x11],
            "JPEG must use three YCbCr components with 4:2:0 sampling")
    return frames, {
        "frames": count, "width": info["width"], "height": info["height"],
        "format": "JPEG Baseline, 8-bit YCbCr 4:2:0",
        "bytes": len(data), "min_frame_bytes": min(map(len, frames)),
        "max_frame_bytes": max(map(len, frames)), "sha256": sha256(data),
    }


def pack_fex(frames):
    return struct.pack("<I", len(frames)) + b"".join(struct.pack("<I", len(f)) + f for f in frames)


def require_stock(data):
    require(sha256(data) == STOCK_SHA256, "Input is not this vehicle's verified stock partition backup")
    stock = parse_boot(data)
    require(len(data) == 64 * 1024 * 1024, "Expected the full 64 MiB partition backup")
    require(not any(data[stock.image_end:]), "Nonzero partition suffix requires separate analysis")
    return stock


def repack(stock, new_cpio):
    rd = gzip.compress(new_cpio, compresslevel=9, mtime=0)
    new_dtb_start = stock.ramdisk_start + aligned(len(rd), stock.page)
    new_end = new_dtb_start + aligned(stock.dtb_size, stock.page)
    require(new_end <= len(stock.data), "Repacked image exceeds partition")
    result = bytearray(stock.data)
    affected_end = max(stock.image_end, new_end)
    result[stock.ramdisk_start:affected_end] = b"\0" * (affected_end - stock.ramdisk_start)
    result[stock.ramdisk_start:stock.ramdisk_start + len(rd)] = rd
    result[new_dtb_start:new_dtb_start + stock.dtb_size] = stock.dtb
    struct.pack_into("<I", result, 16, len(rd))
    unchecked = parse_boot(bytes(result), check_id=False)
    result[576:608] = unchecked.image_id()
    return bytes(result)


def verify_pair(stock_data, candidate_data, expected_animation=None):
    stock = require_stock(stock_data)
    candidate = parse_boot(candidate_data)
    require(len(candidate_data) == len(stock_data), "Candidate must be a full-sized partition image")
    require(candidate.page == stock.page and candidate.kernel == stock.kernel, "Kernel changed")
    require(candidate.dtb == stock.dtb, "DTB changed")
    old_cpio = gzip.decompress(stock.ramdisk)
    new_cpio = gzip.decompress(candidate.ramdisk)
    old_entries, new_entries = parse_cpio(old_cpio), parse_cpio(new_cpio)
    require([e.name for e in old_entries] == [e.name for e in new_entries], "CPIO entries or order changed")
    unchanged = 0
    for old, new in zip(old_entries, new_entries):
        if old.name != TARGET:
            require(old.raw == new.raw, "Unrelated CPIO record changed: " + old.name)
            unchanged += 1
        else:
            old_meta, new_meta = list(old.fields), list(new.fields)
            for i in (6, 12):
                old_meta[i] = new_meta[i] = 0
            require(old_meta == new_meta, "animation.fex metadata changed")
            require(new.content != old.content, "Animation was not changed")
    old_animation = animation_entry(old_entries).content
    new_animation = animation_entry(new_entries).content
    _, old_info = parse_fex(old_animation)
    new_frames, new_info = parse_fex(new_animation)
    require((old_info["frames"], old_info["width"], old_info["height"]) == (99, 1024, 600),
            "Unexpected stock animation specifications")
    require((new_info["frames"], new_info["width"], new_info["height"]) == (99, 1024, 600),
            "Candidate animation specifications changed")
    require(new_info["bytes"] <= old_info["bytes"], "Animation exceeds conservative stock total size")
    require(new_info["max_frame_bytes"] <= old_info["max_frame_bytes"], "Frame exceeds conservative stock maximum")
    if expected_animation is not None:
        require(new_animation == expected_animation, "Embedded animation differs from generated FEX")
    # Byte changes outside ramdisk/relocated DTB may only be rd_size and ID.
    old_prefix = bytearray(stock_data[:stock.ramdisk_start])
    new_prefix = bytearray(candidate_data[:stock.ramdisk_start])
    for start, end in ((16, 20), (576, 608)):
        old_prefix[start:end] = new_prefix[start:end] = b"\0" * (end - start)
    require(old_prefix == new_prefix, "Unexpected header, kernel or padding change")
    end = max(stock.image_end, candidate.image_end)
    require(stock_data[end:] == candidate_data[end:], "Unrelated partition suffix changed")
    require(not any(candidate_data[candidate.image_end:]), "Unexpected candidate partition suffix")
    require(candidate_data[candidate.ramdisk_start + candidate.ramdisk_size:candidate.dtb_start] ==
            b"\0" * (candidate.dtb_start - candidate.ramdisk_start - candidate.ramdisk_size),
            "Unexpected ramdisk padding")
    require(not any(candidate_data[candidate.dtb_start + candidate.dtb_size:candidate.image_end]),
            "Unexpected DTB padding")
    return {
        "offline_verification": "PASS", "hardware_boot_test": "NOT_RUN",
        "vehicle_write_performed": False, "manufacturer_acceptance": "NOT_VERIFIED",
        "original_sha256": sha256(stock_data), "candidate_sha256": sha256(candidate_data),
        "checks": {"original_backup_hash": True, "both_v2_image_ids": True,
                   "kernel_unchanged": True, "dtb_content_unchanged": True,
                   "all_other_cpio_records_unchanged": True,
                   "animation_metadata_preserved": True,
                   "frame_format_and_size_limits": True,
                   "changes_confined_to_animation_repacking_and_required_header_fields": True,
                   "partition_length_and_suffix_preserved": True},
        "cpio_records_total_including_trailer": len(new_entries),
        "cpio_records_unchanged_including_trailer": unchanged,
        "original_boot": stock.summary(), "candidate_boot": candidate.summary(),
        "original_animation": old_info, "candidate_animation": new_info,
        "gzip_mtime": 0, "jpeg_decode_all_frames": "NOT_RUN_BY_STDLIB_VERIFIER",
        "notes": ["Offline structure checks do not establish boot success or steering-lock behavior.",
                  "SHA-1 boot image ID is an integrity field, not a manufacturer signature.",
                  "Only an animation file is intentionally changed inside initramfs; ramdisk recompression changes its compressed bytes."],
    }


def pillow_modules():
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ValueError("Pillow is needed for build: python -m pip install -r requirements.txt") from exc
    return Image, ImageOps


def convert_gif(source_data, old_info):
    Image, ImageOps = pillow_modules()
    source = Image.open(io.BytesIO(source_data))
    require(source.format == "GIF", "Input must be the selected GIF")
    count = old_info["frames"]
    timeline = []
    durations = []
    elapsed = 0
    for i in range(source.n_frames):
        source.seek(i)
        duration = int(source.info.get("duration", 100))
        require(duration > 0, "GIF has a zero or negative frame duration")
        timeline.append(elapsed)
        durations.append(duration)
        elapsed += duration
    source_indices = [max(0, bisect.bisect_right(timeline, i * elapsed / count) - 1) for i in range(count)]
    frames = []
    for index in source_indices:
        source.seek(index)
        rgba = source.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        background.alpha_composite(rgba)
        frames.append(ImageOps.pad(background.convert("RGB"), (old_info["width"], old_info["height"]),
                                  method=Image.Resampling.LANCZOS, color="black"))
    for quality in range(90, 24, -5):
        payloads = []
        for frame in frames:
            buffer = io.BytesIO()
            frame.save(buffer, format="JPEG", quality=quality, subsampling=2,
                       progressive=False, optimize=False)
            payloads.append(buffer.getvalue())
        packed = pack_fex(payloads)
        if len(packed) <= old_info["bytes"] and max(map(len, payloads)) <= old_info["max_frame_bytes"]:
            parse_fex(packed)
            return packed, {
                "source_frames": source.n_frames, "source_duration_ms": elapsed,
                "source_size": list(source.size), "source_frame_indices": source_indices,
                "sampling": "99 evenly spaced times over the supplied GIF duration",
                "jpeg_quality": quality, "jpeg_optimize": False,
                "source_sha256": sha256(source_data),
            }
    raise ValueError("Cannot meet stock animation size limits at JPEG quality >= 25")


def decoded_frames(fex):
    Image, _ = pillow_modules()
    frames, _ = parse_fex(fex)
    result = []
    for payload in frames:
        image = Image.open(io.BytesIO(payload))
        image.load()
        require(image.size == (1024, 600) and image.mode == "RGB", "Decoded frame format mismatch")
        result.append(image.copy())
    return result


def preview_bytes(fex, duration_ms):
    Image, _ = pillow_modules()
    decoded = decoded_frames(fex)
    # GIF stores time in 10 ms units. Split the requested total across frames.
    ticks = round(duration_ms / 10)
    durations = [(round((i + 1) * ticks / len(decoded)) - round(i * ticks / len(decoded))) * 10
                 for i in range(len(decoded))]
    require(min(durations) > 0, "Preview duration too short")
    small = [image.resize((512, 300), Image.Resampling.LANCZOS) for image in decoded]
    buffer = io.BytesIO()
    small[0].save(buffer, format="GIF", save_all=True, append_images=small[1:],
                  duration=durations, loop=0, optimize=False, disposal=2)
    still = io.BytesIO()
    decoded[len(decoded) // 2].save(still, format="PNG")
    return buffer.getvalue(), still.getvalue()


def inspect_file(path):
    data = pathlib.Path(path).read_bytes()
    boot = parse_boot(data)
    cpio = gzip.decompress(boot.ramdisk)
    entries = parse_cpio(cpio)
    _, animation = parse_fex(animation_entry(entries).content)
    return {"sha256": sha256(data), "matches_verified_vehicle_backup": sha256(data) == STOCK_SHA256,
            "boot": boot.summary(), "cpio_records_including_trailer": len(entries),
            "animation": animation}


def write_outputs(folder, files, overwrite, input_paths):
    folder = pathlib.Path(folder).resolve()
    inputs = {pathlib.Path(p).resolve() for p in input_paths}
    for name in files:
        target = folder / name
        require(target not in inputs, "Refusing to overwrite an input")
        require(not target.is_dir(), "Output target is a directory")
        require(overwrite or not target.exists(), "Output already exists; choose a new directory or use --overwrite: " + str(target))
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)


def build(args):
    stock_data = pathlib.Path(args.boot).read_bytes()
    stock = require_stock(stock_data)
    cpio = gzip.decompress(stock.ramdisk)
    old_animation = animation_entry(parse_cpio(cpio)).content
    _, old_info = parse_fex(old_animation)
    require((old_info["frames"], old_info["width"], old_info["height"]) == (99, 1024, 600), "Stock specs changed")
    source_data = pathlib.Path(args.gif).read_bytes()
    new_animation, conversion = convert_gif(source_data, old_info)
    candidate_data = repack(stock, replace_animation(cpio, new_animation))
    report = verify_pair(stock_data, candidate_data, new_animation)
    new_boot = parse_boot(candidate_data)
    preview, still = preview_bytes(new_animation, conversion["source_duration_ms"])
    old_preview, old_still = preview_bytes(old_animation, conversion["source_duration_ms"])
    report["jpeg_decode_all_frames"] = "PASS: all 99 original and all 99 candidate JPEGs"
    report["conversion"] = conversion
    report["created_date_local"] = __import__("datetime").date.today().isoformat()
    report["preview"] = {"size": [512, 300], "duration_ms": conversion["source_duration_ms"],
                         "timing": "Assumed for comparison; actual vehicle playback timing is unknown"}
    report["dtb_offset_changed"] = stock.dtb_start != new_boot.dtb_start
    compact = candidate_data[:new_boot.image_end]
    report["compact_image_sha256"] = sha256(compact)
    files = {
        "boot-partition.experimental.img": candidate_data,
        "boot.experimental.fex": compact,
        "animation.experimental.fex": new_animation,
        "animation.original.fex": old_animation,
        "preview.gif": preview, "preview.png": still,
        "original-preview.gif": old_preview, "original-preview.png": old_still,
    }
    report["artifacts"] = {name: {"bytes": len(data), "sha256": sha256(data)} for name, data in files.items()}
    files["verification.json"] = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    checksums = "".join(f"{sha256(data)}  {name}\n" for name, data in files.items())
    files["SHA256SUMS.txt"] = checksums.encode("ascii")
    write_outputs(args.out, files, args.overwrite, [args.boot, args.gif])
    # Re-read saved files and verify the actual bytes on disk.
    destination = pathlib.Path(args.out)
    for name, data in files.items():
        require((destination / name).read_bytes() == data, "Saved file mismatch: " + name)
    verify_pair(stock_data, (destination / "boot-partition.experimental.img").read_bytes(),
                (destination / "animation.experimental.fex").read_bytes())
    return {"result": "OFFLINE_BUILD_AND_VERIFY_PASS", "out": str(destination.resolve()),
            "jpeg_quality": conversion["jpeg_quality"], "animation_bytes": len(new_animation),
            "ramdisk_bytes": new_boot.ramdisk_size, "dtb_offset": new_boot.dtb_start,
            "candidate_sha256": sha256(candidate_data), "vehicle_write_performed": False,
            "hardware_boot_test": "NOT_RUN"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect", help="Read and inspect a local image")
    inspect_parser.add_argument("--boot", required=True)
    build_parser = sub.add_parser("build", help="Build LOCAL experimental files; never connects to a vehicle")
    build_parser.add_argument("--boot", required=True)
    build_parser.add_argument("--gif", required=True)
    build_parser.add_argument("--out", required=True)
    build_parser.add_argument("--overwrite", action="store_true")
    verify_parser = sub.add_parser("verify", help="Compare a full local candidate image with verified stock")
    verify_parser.add_argument("--stock", required=True)
    verify_parser.add_argument("--candidate", required=True)
    verify_parser.add_argument("--animation")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect_file(args.boot)
        elif args.command == "build":
            result = build(args)
        else:
            expected = pathlib.Path(args.animation).read_bytes() if args.animation else None
            result = verify_pair(pathlib.Path(args.stock).read_bytes(), pathlib.Path(args.candidate).read_bytes(), expected)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, EOFError, struct.error) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
