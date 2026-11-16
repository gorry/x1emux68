# X1STAT.o のテスト。短いパスの作業フォルダで実行する。
#   T3.x = T3.o + X1STAT.o (VRAM・パレット・CRTC の equ を消し、rte を置き換えたコピーからアセンブルしたもの)
import struct, subprocess, sys

RUN68 = sys.argv[1]
fails = 0


def check(name, cond, info=""):
    global fails
    if not cond:
        fails += 1
        print("NG", name, str(info)[:300])


font = bytes(((c * 37) ^ (r * 91) ^ (c >> 3)) & 255 for c in range(256) for r in range(8))
font = font[:0x20 * 8] + bytes(8) + font[0x21 * 8:]          # スペースは空白
open("T.FNT", "wb").write(font)
BS = bytes([0x5C])
names = [b"A:" + BS + b"X1" + BS + b"DISK1.D88", b"LONGFILENAMEFILENAME.2D", b"", b"/a/b:c.d88"]
open("T.NAM", "wb").write(b"".join(n.ljust(0x80, b"\0") for n in names))
r = subprocess.run([RUN68, "T3.x"], capture_output=True)
if r.stdout.strip() or r.stderr.strip():
    print("run68:", r.stdout[:200], r.stderr[:200])
out = open("T.OUT", "rb").read()
GV, TX = 16 * 2048, 4 * 16 * 128
REC = GV * 2 + TX * 2 + 42
ND = 17
check("size", len(out) == REC * ND + 4, (len(out), REC * ND + 4))

BG, FG, OFF, RD, WR = 4, 3, 5, 6, 7


def row(text, leds):
    """期待するステータス行 (8ライン x 1024ドットの色)"""
    px = [[BG] * 1024 for _ in range(8)]
    for d in range(4):
        s = b"%d:" % d + text[d][:16].ljust(16)
        for i, ch in enumerate(s):
            col = d * 20 + 1 + i
            for y in range(8):
                b = font[ch * 8 + y]
                for x in range(8):
                    px[y][col * 8 + x] = FG if b & (0x80 >> x) else BG
        for y in range(1, 7):
            for x in range(1, 7):
                px[y][d * 160 + x] = leds[d] or OFF
    return px


def get(i):
    b = out[i * REC:(i + 1) * REC]
    g = [b[p * GV:(p + 1) * GV] for p in range(2)]
    tx = []
    for p in range(2):
        t = b[2 * GV + p * TX:2 * GV + (p + 1) * TX]
        pl = [t[k * 16 * 128:(k + 1) * 16 * 128] for k in range(4)]
        tx.append([[sum(((pl[k][y * 128 + x // 8] >> (7 - x % 8)) & 1) << k for k in range(4)) for x in range(1024)]
                   for y in range(16)])
    pal = struct.unpack(">16H", b[2 * GV + 2 * TX:2 * GV + 2 * TX + 32])
    crtc = struct.unpack(">5H", b[-10:])          # R21, R06, R07, STSCR0, STSCR1
    return g, tx, pal, crtc


shown = [b"DISK1.D88", b"LONGFILENAMEFILE", b"", b"c.d88"]
shown2 = [shown[0], shown[1], b"NEW.2D", shown[3]]
exp = [(shown, [0, 0, 0, 0]), (shown, [0, 0, 0, 0]), (shown, [0, RD, 0, 0]), (shown, [0, 0, 0, WR]), (shown, [0, 0, 0, WR]),
       (shown, [0, 0, 0, 0]), (shown, [RD, 0, 0, 0]), (shown2, [RD, 0, 0, 0]), (shown2, [RD, 0, 0, 0]), (shown2, [0, 0, 0, 0]),
       (shown2, [0, 0, 0, 0]), (shown2, [0, 0, 0, 0]), (shown2, [0, 0, 0, 0]),
       ([shown[0], shown[1], b"PEND.D88", shown[3]], [RD, 0, 0, 0]), ([shown[0], shown[1], b"PEND2.D88", shown[3]], [RD, 0, 0, 0]),
       ([shown[0], shown[1], b"PEND2.D88", shown[3]], [RD, 0, 0, 0]), ([shown[0], shown[1], b"ORIG.2D", shown[3]], [RD, 0, 0, 0])]
# (13 からのドライブ 0 の LED は、STATUS=OFF の間に出したリードの要求が残っているもの)
# 8: STHIDE のあと / 9: STEXIT のあと / 10: 31kHz で描き直し / 11: STATUS=OFF (10 の STEXIT のあと何も描かない) / 12: ON に戻す
page0_blank = (8, 9, 11, 12)
orig_pal = (9, 11, 12)
crtc_exp = {i: (0x0170, 23, 439, 0x1F8, 0x2F8) for i in range(10)}
crtc_exp[10] = (0x0170, 24, 440, 0x1F8, 0x2F8)
crtc_exp[11] = (0x0170, 31, 431, 0x200, 0x300)
crtc_exp[12] = (0x0170, 31, 431, 0x1F8, 0x2F8)
crtc_exp[13] = crtc_exp[14] = crtc_exp[15] = crtc_exp[16] = (0x0170, 23, 439, 0x1F8, 0x2F8)
# 13: 要求 1 回で次の名前 / 14: 2 回でその次の名前 / 15: 入れ替えたあと (同じ名前のまま) / 16: もう 1 回で最初の名前
mypal = (0x4210, 0x0040, 0xF800, 0x07C0)
for i, (text, leds) in enumerate(exp):
    g, tx, pal, crtc = get(i)
    want = row(text, leds)
    blank = [[0] * 1024 for _ in range(8)]
    for p in range(2):
        gw = struct.unpack(">%dH" % (16 * 1024), g[p])
        check("dump %d page %d graphic" % (i, p), all(v == 0x5555 for v in gw[:4 * 1024]) and all(v == 0 for v in gw[4 * 1024:12 * 1024])
              and all(v == 0x5555 for v in gw[12 * 1024:]))
        pg = tx[p]
        check("dump %d page %d guard" % (i, p), all(v == 15 for y in (0, 1, 2, 3, 12, 13, 14, 15) for v in pg[y]))
        w = blank if (i in page0_blank and p == 0) else want
        got = pg[4:12]
        bad = [(y, x, got[y][x], w[y][x]) for y in range(8) for x in range(1024) if got[y][x] != w[y][x]]
        check("dump %d page %d row" % (i, p), not bad, bad[:5])
    orig = tuple(0x1000 + k for k in range(16))
    wantpal = orig if i in orig_pal else orig[:4] + mypal + orig[8:]
    check("dump %d palette" % i, pal == wantpal, [hex(v) for v in pal[3:9]])
    check("dump %d crtc" % i, crtc == crtc_exp[i], crtc)
check("flash count", struct.unpack(">I", out[-4:])[0] == 2, out[-4:].hex())
print("FAILS", fails)
