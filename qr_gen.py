"""
Minimal QR Code generator - pure Python, no external dependencies.
Generates a simple data matrix encoded as SVG or as a base64 PNG-like image
using only Pillow (which we have).
We'll use segno-style manual approach with PIL.
"""
import hashlib
import struct
import zlib
import base64
import io

def _png_chunk(chunk_type, data):
    c = chunk_type + data
    crc = zlib.crc32(c) & 0xffffffff
    return struct.pack('>I', len(data)) + c + struct.pack('>I', crc)

def _make_simple_qr_png(text, size=200, module_size=6, border=4):
    """
    Generate a very simplified "QR-like" matrix barcode using PIL.
    This is a visual representation using the text's hash for determinism.
    For production, use python-qrcode. This is a demo fallback.
    """
    from PIL import Image, ImageDraw
    
    # Create a deterministic grid from the text
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    modules = 21  # Standard QR version 1 is 21x21
    
    grid = [[False]*modules for _ in range(modules)]
    
    # Finder patterns (top-left, top-right, bottom-left)
    def finder(r, c):
        for dr in range(7):
            for dc in range(7):
                dist_r = min(dr, 6-dr)
                dist_c = min(dc, 6-dc)
                # outer ring = True, inner ring = False, center = True
                if dist_r == 0 or dist_c == 0:
                    grid[r+dr][c+dc] = True
                elif dist_r >= 2 and dist_c >= 2:
                    grid[r+dr][c+dc] = True
                else:
                    grid[r+dr][c+dc] = False
    
    finder(0, 0)
    finder(0, modules-7)
    finder(modules-7, 0)
    
    # Separators and timing
    for i in range(modules):
        if i % 2 == 0:
            if 8 <= i < modules-8:
                grid[6][i] = True
                grid[i][6] = True
    
    # Data modules (fill remaining with hash-derived bits)
    bits = bin(seed)[2:]
    bit_idx = 0
    for r in range(modules):
        for c in range(modules):
            if r < 9 and (c < 9 or c >= modules-8):
                continue
            if r >= modules-8 and c < 9:
                continue
            if r == 6 or c == 6:
                continue
            grid[r][c] = bits[bit_idx % len(bits)] == '1'
            bit_idx += 1
    
    # Draw with PIL
    cell = module_size
    total = (modules + 2 * border) * cell
    img = Image.new('RGB', (total, total), 'white')
    draw = ImageDraw.Draw(img)
    
    for r in range(modules):
        for c in range(modules):
            if grid[r][c]:
                x = (border + c) * cell
                y = (border + r) * cell
                draw.rectangle([x, y, x+cell-1, y+cell-1], fill='#1a472a')
    
    # Resize to requested size
    img = img.resize((size, size), Image.NEAREST)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode()


def generate_qr_b64(data_str, size=200):
    return _make_simple_qr_png(data_str, size=size, module_size=6, border=3)
