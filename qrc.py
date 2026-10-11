"""Offline-only QRC background patch for the fingerprinted 368K Launcher."""
import argparse
import hashlib
import io
import json
import pathlib
import shutil
import struct
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[1]
STOCK_SHA = 'f92b2c2c627b0d61a1bbf7f750f5b6efea808fded396b67c2ce2c2c1215db473'
GROUP = 'qrc_res_sport.cpp'
TARGETS = {f'/res_sport/SPORT_NIGHT_BG_{n}.png' for n in (6, 12, 18, 24)}

def require(condition,message):
    if not condition: raise ValueError(message)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def tables_from_elf(b):
    require(b[:6] == b'\x7fELF\x02\x01', 'Expected little-endian ELF64')
    shoff = struct.unpack_from('<Q', b, 40)[0]
    shsize, shnum = struct.unpack_from('<HH', b, 58)
    sections = [struct.unpack_from('<IIQQQQIIQQ', b, shoff + i * shsize) for i in range(shnum)]
    groups = {}
    for section in sections:
        if section[1] != 2:
            continue
        ss = sections[section[6]]
        names = b[ss[4]:ss[4] + ss[5]]
        group = None
        for pos in range(section[4], section[4] + section[5], section[9]):
            ni, info, other, si, value, size = struct.unpack_from('<IBBHQQ', b, pos)
            name = names[ni:names.find(b'\x00', ni)].decode(errors='replace')
            if name.startswith('qrc_') and name.endswith('.cpp'):
                group = name
                groups[group] = {}
            if group and name.startswith('_ZL') and ('qt_resource_' in name):
                kind = next((k for k in ('data', 'name', 'struct') if name.endswith(k)))
                sec = sections[si]
                require(sec[1] != 8, 'Invalid ELF/QRC structure')
                groups[group][kind] = (sec[4] + value - sec[3], size)
    require(all((len(t) == 3 for t in groups.values())), 'Invalid ELF/QRC structure')
    return groups

def read_resources(b, tables):
    resources = []
    for group, t in tables.items():
        tree, tree_size = t['struct']
        names, names_size = t['name']
        data, data_size = t['data']
        require(tree_size % 22 == 0, 'Invalid ELF/QRC structure')
        visited = set()

        def visit(index, parent):
            require(index not in visited and 0 <= index < tree_size // 22, 'Invalid ELF/QRC structure')
            visited.add(index)
            node = tree + index * 22
            no, flags = struct.unpack_from('>IH', b, node)
            require(no + 6 <= names_size, 'Invalid ELF/QRC structure')
            name_len = struct.unpack_from('>H', b, names + no)[0]
            require(no + 6 + name_len * 2 <= names_size, 'Invalid ELF/QRC structure')
            name = b[names + no + 6:names + no + 6 + name_len * 2].decode('utf-16-be') if index else ''
            path = parent + '/' + name if name else parent
            if flags & 2:
                count, first = struct.unpack_from('>II', b, node + 6)
                for child in range(first, first + count):
                    visit(child, path)
            else:
                country, language, relative = struct.unpack_from('>HHI', b, node + 6)
                require(relative + 4 <= data_size, 'Invalid ELF/QRC structure')
                length = struct.unpack_from('>I', b, data + relative)[0]
                require(relative + 4 + length <= data_size, 'Invalid ELF/QRC structure')
                resources.append({'group': group, 'path': path, 'flags': flags, 'country': country, 'language': language, 'node_offset': node, 'offset': data + relative + 4, 'length': length})
        visit(0, '')
        require(len(visited) == tree_size // 22, 'Invalid ELF/QRC structure')
    require(len({(r['group'], r['path'], r['country'], r['language']) for r in resources}) == len(resources), 'Invalid ELF/QRC structure')
    return resources
