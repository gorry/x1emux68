# X1D88.o のテスト。tmpb (短いパス) で実行する。
import os, random, struct, subprocess, sys

RUN68, D88MAKE = sys.argv[1], sys.argv[2]
REC = 16 + 0x1900
fails = 0


def check(name, cond, info=""):
    global fails
    if not cond:
        fails += 1
        if isinstance(info, dict):
            info = {k: v for k, v in info.items() if k != "buf"}
        print("NG", name, str(info)[:300])


def parse(img):
    """D88 -> {track: [sector dict]} (1枚目だけ)"""
    offs = struct.unpack_from("<164I", img, 0x20)
    first = min(o for o in offs if o)
    n = (first - 0x20) // 4
    tr = {}
    for t, o in enumerate(offs[:min(n, 164)]):
        if not o:
            continue
        secs, p = [], o
        while True:
            c, h, r, nn, ns, dens, dl, st = struct.unpack_from("<BBBBHBBB", img, p)
            size = struct.unpack_from("<H", img, p + 14)[0]
            secs.append(dict(c=c, h=h, r=r, n=nn, dl=dl, st=st, size=size, off=p,
                             data=img[p + 16:p + 16 + size]))
            p += 16 + size
            if len(secs) >= ns:
                break
        tr[t] = secs
    return tr


def mk(tracks, hdr=0x2B0, prot=0, kind=0):
    """{track: [(c,h,r,n,del,stat,data)]} -> D88"""
    body, offs, pos = b"", [0] * 164, hdr
    for t in sorted(tracks):
        offs[t] = pos
        for (c, h, r, n, dl, st, data) in tracks[t]:
            s = struct.pack("<BBBBHBBB5xH", c, h, r, n, len(tracks[t]), 0, dl, st, len(data)) + data
            body += s
            pos += len(s)
    head = b"TEST".ljust(17, b"\0") + bytes(9) + bytes([prot, kind]) + struct.pack("<I", pos)
    head += struct.pack("<164I", *offs)
    return head[:hdr] + body


def fmt(secs, fm=False, gap3=54, cut=False):
    """[(c,h,r,n,mark,data)] -> ライトトラックで FDC に渡すデータ ($1900 バイト)。data が None なら ID だけ"""
    if fm:
        b = b"\xFF" * 40 + bytes(6) + b"\xFC" + b"\xFF" * 26
    else:
        b = b"\x4E" * 80 + bytes(12) + b"\xF6" * 3 + b"\xFC" + b"\x4E" * 50
    for (c, h, r, n, mark, data) in secs:
        if fm:
            b += bytes(6) + bytes([0xFE, c, h, r, n, 0xF7]) + b"\xFF" * 11
            if data is not None:
                b += bytes(6) + bytes([mark]) + data + b"\xF7" + b"\xFF" * gap3
        else:
            b += bytes(12) + b"\xF5" * 3 + bytes([0xFE, c, h, r, n, 0xF7]) + b"\x4E" * 22
            if data is not None:
                b += bytes(12) + b"\xF5" * 3 + bytes([mark]) + data + b"\xF7" + b"\x4E" * gap3
    assert cut or len(b) <= 0x1900, len(b)
    return b[:0x1900].ljust(0x1900, b"\xFF" if fm else b"\x4E")


def trk(secs, dens=0):
    """[(c,h,r,n,del,data)] -> D88 のトラック"""
    return b"".join(struct.pack("<BBBBHBBB5xH", c, h, r, n, len(secs), dens, dl, 0, len(data)) + data
                    for (c, h, r, n, dl, data) in secs)


def apply(img, t, new):
    """img のトラック t を new に置き換えたイメージ (後ろをずらし、テーブルとディスクサイズを直す)"""
    size = struct.unpack_from("<I", img, 0x1C)[0]
    offs = list(struct.unpack_from("<164I", img, 0x20))
    n = 160 if min(o for o in offs[:160] if o) < 0x2B0 else 164
    offs[n:] = [0] * (164 - n)
    pos = offs[t] or size
    nxt = min([o for o in offs if o > pos] + [size])
    delta = len(new) - (nxt - pos)
    body = img[:pos] + new + img[nxt:]
    offs = [o + delta if o > pos else o for o in offs]
    offs[t] = pos
    head = body[:0x1C] + struct.pack("<I", size + delta) + struct.pack("<%dI" % n, *offs[:n])
    return head + body[len(head):]


def run(img, cmds, wtk=()):
    open("T.D88", "wb").write(img)
    open("T.WTK", "wb").write(b"".join(wtk))
    open("T.CMD", "wb").write(b"".join(struct.pack(">6BH", *c) for c in cmds))
    if os.path.exists("T.OUT"):
        os.remove("T.OUT")
    r = subprocess.run([RUN68, "T88.x"], capture_output=True)
    if r.stdout.strip() or r.stderr.strip():
        print("run68:", r.stdout, r.stderr)
    out = open("T.OUT", "rb").read()
    check("record count", len(out) == REC * len(cmds), (len(out), len(cmds)))
    res = []
    for i in range(len(out) // REC):
        b = out[i * REC:(i + 1) * REC]
        op, ret, st, scr, rdat, wdat, pdisk, erd, typ = struct.unpack(">BBBBHHHHI", b[:16])
        res.append(dict(op=op, ret=ret, st=st, scr=scr, rdat=rdat, wdat=wdat, pdisk=pdisk,
                        erd=erd, typ=typ, buf=b[16:]))
    return res, open("T.D88", "rb").read()


random.seed(1)

# ---- A: d88make.py で作った標準の2Dディスク
raw = bytes(random.randrange(256) for _ in range(327680))
open("T.2D", "wb").write(raw)
subprocess.run([sys.executable, D88MAKE, "-i", "T.2D", "A.D88"], check=True, capture_output=True)
imgA = open("A.D88", "rb").read()


def rawsec(c, h, r, n=1):
    o = c * 0x2000 + h * 0x1000 + (r - 1) * 0x100
    return raw[o:o + 0x100 * n]


cmds = [(0, 0, 0, 0, 0, 0, 0)]
cmds += [(1, c, h, c, r, 0, 0) for (c, h, r) in [(0, 0, 1), (0, 1, 16), (20, 0, 7), (39, 1, 16), (39, 1, 1)]]
cmds += [(1, 5, 0, 6, 1, 0, 0), (1, 5, 0, 5, 17, 0, 0), (1, 5, 0, 5, 0, 0, 0), (1, 40, 0, 40, 1, 0, 0),
         (1, 100, 0, 100, 1, 0, 0)]
cmds += [(2, 7, 1, 7, 1, 0, 0), (2, 7, 1, 7, 9, 0, 0), (2, 7, 1, 7, 17, 0, 0)]
cmds += [(3, 9, 0, 9, 1, 0, 0), (3, 41, 0, 41, 1, 0, 0)]
cmds += [(4, 12, 1, 0, 0, 0, 0)] * 18 + [(4, 60, 0, 0, 0, 0, 0)]
res, _ = run(imgA, cmds)
it = iter(res)
r = next(it)
check("A open", r["ret"] == 0 and r["typ"] == 0xFF000000, r["typ"])
for (c, h, s) in [(0, 0, 1), (0, 1, 16), (20, 0, 7), (39, 1, 16), (39, 1, 1)]:
    r = next(it)
    check("A read %d/%d/%d" % (c, h, s),
          r["ret"] == 0xFF and r["st"] == 3 and r["rdat"] == 0xFF and r["pdisk"] == 0xFFFE
          and r["erd"] == 0xFF00 and r["buf"][:256] == rawsec(c, h, s) and r["buf"][256:] == b"\xCC" * (0x1900 - 256), r)
for name in ["TR mismatch", "R=17", "R=0", "cyl 40", "cyl 100"]:
    r = next(it)
    check("A rnf " + name, r["ret"] == 0xFF and r["st"] == 0x10 and r["buf"] == b"\xCC" * 0x1900, (r["st"], r["ret"]))
r = next(it)
check("A multi 1", r["st"] == 3 and r["rdat"] == 0xFFF and r["erd"] == 0x0010 and r["pdisk"] == 0xFFFE
      and r["buf"][:0x1000] == rawsec(7, 1, 1, 16) and r["buf"][0x1000:] == b"\xCC" * 0x900)
r = next(it)
check("A multi 9", r["st"] == 3 and r["rdat"] == 0x7FF and r["erd"] == 0x0010 and r["buf"][:0x800] == rawsec(7, 1, 9, 8)
      and r["buf"][0x800:] == b"\xCC" * 0x1100)
r = next(it)
check("A multi 17", r["st"] == 0x10)
r = next(it)
check("A track", r["st"] == 3 and r["rdat"] == 0x18FF and r["erd"] == 0x0004 and r["pdisk"] == 0xFFFE
      and r["buf"] == rawsec(9, 0, 1, 16) + bytes(0x900))
r = next(it)
check("A track none", r["st"] == 0x10)
for k in range(18):
    r = next(it)
    rr = (k + 1) % 16 + 1
    check("A readadrs %d" % k, r["ret"] == 0xFF and r["st"] == 3 and r["pdisk"] == 0 and r["rdat"] == 5 and r["erd"] == 0
          and r["scr"] == 12 and r["buf"][:6] == bytes([12, 1, rr, 1, 0, 0]), r["buf"][:6])
r = next(it)
check("A readadrs none", r["st"] == 0x10 and r["pdisk"] == 0xFFFF)

# 書き込み
cmds = [(0, 0, 0, 0, 0, 0, 0),
        (5, 3, 1, 3, 5, 0x10, 0),      # 1セクタ
        (5, 3, 1, 3, 17, 0x10, 0),     # ない
        (6, 8, 0, 8, 15, 0x80, 0),     # m: 15,16
        (6, 8, 1, 8, 1, 0x33, 0),      # m: 1-16
        (9, 5, 0, 5, 1, 0, 0),         # トラック (同じ構成、データは $FF)
        (7, 82, 0, 82, 1, 0, 0),       # テーブルにないトラック
        (1, 3, 1, 3, 5, 0, 0),
        (8, 0, 0, 0, 32, 0, 0),        # RREC 0, 32バイト
        (8, 0, 0, 3, 0xE8, 0, 37),     # RREC 37, 1000バイト
        (8, 0, 0, 1, 0, 0, 1280)]      # 範囲外
res, after = run(imgA, cmds, [fmt([(5, 0, r, 1, 0xFB, b"\xFF" * 256) for r in range(1, 17)])])
exp = bytearray(imgA)
tr = parse(imgA)


def put(t, r, data, mark=True):
    s = [x for x in tr[t] if x["r"] == r][0]
    exp[s["off"] + 16:s["off"] + 16 + len(data)] = data


pat = lambda f, n: bytes((f + i) & 255 for i in range(n))
put(3 * 2 + 1, 5, pat(0x10, 256))
p = pat(0x80, 512)
put(8 * 2, 15, p[:256]); put(8 * 2, 16, p[256:])
p = pat(0x33, 4096)
for i in range(16):
    put(8 * 2 + 1, i + 1, p[i * 256:(i + 1) * 256])
for i in range(16):
    put(5 * 2, i + 1, b"\xFF" * 256)
check("A write file", bytes(exp) == after, sum(a != b for a, b in zip(exp, after)))
check("A write 1", res[1]["ret"] == 0x7F and res[1]["st"] == 0 and res[1]["wdat"] == 0xFF, res[1])
check("A write rnf", res[2]["ret"] == 0xFF and res[2]["st"] == 0x10)
check("A write m 15", res[3]["ret"] == 0x7F and res[3]["st"] == 0x10 and res[3]["wdat"] == 0x1FF)
check("A write m 1", res[4]["ret"] == 0x7F and res[4]["st"] == 0x10 and res[4]["wdat"] == 0xFFF)
check("A write trk", res[5]["ret"] == 0x7F and res[5]["st"] == 0 and res[5]["wdat"] == 0x18FF)
check("A write trk none", res[6]["ret"] == 0xFF and res[6]["st"] == 0x20)
check("A reread", res[7]["st"] == 3 and res[7]["buf"][:256] == pat(0x10, 256))
check("A rrec 0", res[8]["ret"] == 0 and res[8]["buf"][:32] == raw[:32] and res[8]["buf"][32] == 0xCC)
check("A rrec 37", res[9]["ret"] == 0 and res[9]["buf"][:1000] == raw[37 * 256:37 * 256 + 1000] and res[9]["buf"][1000] == 0xCC)
check("A rrec out", res[10]["ret"] == 0xFF)

# ---- B: 160個のテーブル、書き込み禁止、いろいろなセクタ
d = lambda n, seed: bytes((seed * 7 + i * 3) & 255 for i in range(n))
tracksB = {
    0: [(0, 0, 1, 0, 0, 0, d(128, 1)), (0, 0, 2, 2, 0, 0, d(512, 2)), (0, 0, 3, 3, 0, 0, d(1024, 3)),
        (0, 0, 4, 1, 0x10, 0x10, d(256, 4)), (0, 0, 5, 1, 0, 0xB0, d(256, 5)), (0, 0, 6, 1, 0, 0xA0, d(256, 6)),
        (0, 0, 7, 1, 0, 0xF0, d(256, 7)), (0, 0, 8, 1, 0x10, 0, d(256, 8)), (9, 0, 9, 1, 0, 0, d(256, 9)),
        (0, 0, 10, 1, 0, 0, b"")],
    3: [(1, 1, 1, 1, 0, 0, d(256, 10)), (1, 1, 2, 1, 0, 0, d(256, 11))],
    159: [(79, 1, 1, 1, 0, 0, d(256, 12))],
}
imgB = mk(tracksB, hdr=0x2A0, prot=0x10)
cmds = [(0, 0, 0, 0, 0, 0, 0)] + [(1, 0, 0, 0, r, 0, 0) for r in range(1, 11)]
cmds += [(1, 0, 0, 9, 9, 0, 0), (2, 0, 0, 0, 1, 0, 0), (3, 0, 0, 0, 0, 0, 0),
         (1, 1, 1, 1, 2, 0, 0), (1, 79, 1, 79, 1, 0, 0), (1, 80, 0, 80, 1, 0, 0),
         (5, 0, 0, 0, 2, 0x40, 0), (5, 0, 0, 0, 4, 0x41, 0), (5, 0, 0, 0, 5, 0x42, 0),
         (1, 0, 0, 0, 4, 0, 0), (1, 0, 0, 0, 5, 0, 0)]
res, after = run(imgB, cmds)
check("B open", res[0]["ret"] == 0x40 and res[0]["typ"] == 0xFF000000, res[0])
e = [(128, 0x00), (512, 0x00), (1024, 0x00), (256, 0x20), (256, 0x08), None, None, (256, 0x20), None, None]
for i, x in enumerate(e):
    r = res[1 + i]
    if x is None:
        check("B rnf R=%d" % (i + 1), r["st"] == 0x10, r["st"])
    else:
        n, st = x
        check("B read R=%d" % (i + 1), r["st"] == 3 and r["rdat"] == n - 1 and r["erd"] == 0xFF00 + st
              and r["buf"][:n] == d(n, i + 1) and r["buf"][n] == 0xCC, (r["st"], r["rdat"], hex(r["erd"])))
check("B C=9", res[11]["st"] == 3 and res[11]["buf"][:256] == d(256, 9))
r = res[12]
m = d(128, 1) + d(512, 2) + d(1024, 3) + d(256, 4) + d(256, 5)
check("B multi", r["st"] == 3 and r["rdat"] == len(m) - 1 and r["erd"] == 0x0038 and r["buf"][:len(m)] == m, (r["rdat"], hex(r["erd"])))
r = res[13]
m = d(128, 1) + d(512, 2) + d(1024, 3) + d(256, 4) + d(256, 5) + d(256, 6) + d(256, 8) + d(256, 9)
check("B track", r["st"] == 3 and r["rdat"] == 0x18FF and r["buf"] == m + bytes(0x1900 - len(m)))
check("B trk3", res[14]["st"] == 3 and res[14]["buf"][:256] == d(256, 11))
check("B trk159", res[15]["st"] == 3 and res[15]["buf"][:256] == d(256, 12))
check("B trk160", res[16]["st"] == 0x10)
check("B write 512", res[17]["ret"] == 0x7F and res[17]["wdat"] == 0x1FF and res[17]["st"] == 0)
check("B reread 4", res[20]["st"] == 3 and res[20]["erd"] == 0xFF00 and res[20]["buf"][:256] == pat(0x41, 256), hex(res[20]["erd"]))
check("B reread 5", res[21]["st"] == 3 and res[21]["erd"] == 0xFF00 and res[21]["buf"][:256] == pat(0x42, 256))
ta = parse(after)
check("B file", ta[0][1]["data"] == pat(0x40, 512) and ta[0][3]["dl"] == 0 and ta[0][3]["st"] == 0 and ta[0][4]["st"] == 0
      and ta[0][0]["data"] == d(128, 1) and ta[0][2]["data"] == d(1024, 3) and len(after) == len(imgB))

# ---- C: 2Dのベタイメージは D88 と判定しない
for name, img in [("random", raw),
                  ("zero", bytes(327680)),
                  ("boot", bytes([1]) + b"TESTNAME     Sys" + bytes(15) + bytes(0x2B0 - 32) + raw[0x2B0:]),
                  ("size", bytes(0x1C) + struct.pack("<I", 327680) + bytes(327680 - 0x20)),
                  ("short", bytes(100))]:
    res, after = run(img, [(0, 0, 0, 0, 0, 0, 0), (1, 0, 0, 0, 1, 0, 0), (4, 0, 0, 0, 1, 0, 0), (5, 0, 0, 0, 1, 0, 0)])
    check("C " + name, [x["ret"] for x in res] == [0, 0, 0, 0] and res[0]["typ"] == 0 and after == img
          and all(x["st"] == 0xEE for x in res[1:]), [(x["ret"], x["st"]) for x in res])

# ---- D: 複数枚のイメージは1枚目を使う
imgD = imgA + mk({0: [(0, 0, 1, 1, 0, 0, d(256, 99))]})
res, _ = run(imgD, [(0, 0, 0, 0, 0, 0, 0), (1, 20, 0, 20, 7, 0, 0)])
check("D", res[0]["typ"] == 0xFF000000 and res[1]["buf"][:256] == rawsec(20, 0, 7))

# ---- E: 壊れたイメージ
bad = bytearray(imgA); struct.pack_into("<I", bad, 0x20 + 4 * 10, len(imgA) + 5)
res, _ = run(bytes(bad), [(0, 0, 0, 0, 0, 0, 0)])
check("E offset out", res[0]["typ"] == 0)
res, _ = run(imgA[:len(imgA) - 1000], [(0, 0, 0, 0, 0, 0, 0)])
check("E truncated", res[0]["typ"] == 0)
bad = bytearray(imgA); struct.pack_into("<I", bad, 0x1C, len(imgA) + 0x100000)
res, _ = run(bytes(bad) + bytes(0x100000), [(0, 0, 0, 0, 0, 0, 0), (1, 39, 1, 39, 16, 0, 0)])
check("E big", res[0]["typ"] == 0xFF000000 and res[1]["buf"][:256] == rawsec(39, 1, 16))
# 最後のトラックがファイルの終わりで切れている (ディスクサイズは正しい)
t = mk({0: [(0, 0, 1, 1, 0, 0, d(256, 1)), (0, 0, 2, 1, 0, 0, d(256, 2))]})
t = bytearray(t[:-100]); struct.pack_into("<I", t, 0x1C, len(t))
res, _ = run(bytes(t), [(0, 0, 0, 0, 0, 0, 0), (1, 0, 0, 0, 1, 0, 0), (1, 0, 0, 0, 2, 0, 0)])
check("E cut sector", res[0]["typ"] == 0xFF000000 and res[1]["st"] == 3 and res[2]["st"] == 0x10, [x["st"] for x in res])

# ---- F: ライトトラック (フォーマット)。セクタの構成を変える
pd = lambda r, n: bytes((r * 17 + i * 5) & 255 for i in range(n))
OPEN = (0, 0, 0, 0, 0, 0, 0)


def wt(c, h, k):
    return (9, c, h, c, 1, 0, k)


def rd(c, h, r):
    return (1, c, h, c, r, 0, 0)


def geo(c, h, n, count, mark=0xFB, order=None):
    """(ライトトラックのデータ, D88 のトラック)"""
    rs = order or list(range(1, count + 1))
    size = 128 << n
    return (fmt([(c, h, r, n, mark, pd(r, size)) for r in rs]),
            trk([(c, h, r, n, 0x10 if mark == 0xF8 else 0, pd(r, size)) for r in rs]))


def fcheck(name, after, exp, maxlen=None):
    # run68x は大きさ 0 の _WRITE でファイルを切り詰めないので、縮めたあとは後ろにごみが残る
    check(name + " file", after[:len(exp)] == exp, (len(after), len(exp), sum(a != b for a, b in zip(after, exp))))
    check(name + " size", len(after) == (maxlen or len(exp)), (len(after), maxlen or len(exp)))


def okw(r):
    return r["ret"] == 0x7F and r["st"] == 0 and r["wdat"] == 0x18FF


def okr(r, data):
    return r["st"] == 3 and r["rdat"] == len(data) - 1 and r["buf"][:len(data)] == data


# 同じ構成で、データだけ変える (ファイルの大きさもヘッダも変わらない)
w1, t1 = geo(5, 0, 1, 16)
res, after = run(imgA, [OPEN, wt(5, 0, 0), rd(5, 0, 7), rd(6, 0, 3)], [w1])
exp = apply(imgA, 10, t1)
fcheck("F same", after, exp)
check("F same header", after[:0x2B0] == imgA[:0x2B0] and len(after) == len(imgA))
check("F same res", okw(res[1]) and okr(res[2], pd(7, 256)) and okr(res[3], rawsec(6, 0, 3)), [(x["ret"], x["st"]) for x in res])

# 大きくなる・もう一度大きくなる・小さくなる (後ろのトラックがずれる)
w2, t2 = geo(5, 0, 2, 9)
w3, t3 = geo(5, 0, 3, 5)
w4, t4 = geo(5, 0, 1, 8, order=[1, 5, 2, 6, 3, 7, 4, 8])
res, after = run(imgA, [OPEN, rd(39, 1, 16),
                        wt(5, 0, 0), rd(5, 0, 9), rd(39, 1, 16), rd(5, 1, 2), rd(4, 1, 16),
                        wt(5, 0, 1), rd(5, 0, 5), rd(39, 1, 1),
                        wt(5, 0, 2), rd(5, 0, 8), rd(5, 0, 9), rd(39, 1, 16), rd(5, 1, 1), rd(0, 0, 1)], [w2, w3, w4])
e2 = apply(imgA, 10, t2)
e3 = apply(e2, 10, t3)
e4 = apply(e3, 10, t4)
check("F resize lens", len(e2) == len(imgA) + 400 and len(e3) == len(e2) + 448 and len(e4) == len(imgA) - 2176, (len(e2), len(e3), len(e4)))
fcheck("F resize", after, e4, len(e3))
check("F resize size field", struct.unpack_from("<I", after, 0x1C)[0] == len(e4))
check("F resize parse", [(x["r"], x["size"]) for x in parse(after[:len(e4)])[10]] == [(r, 256) for r in [1, 5, 2, 6, 3, 7, 4, 8]]
      and parse(after[:len(e4)])[79][15]["data"] == rawsec(39, 1, 16))
check("F resize res", okw(res[2]) and okr(res[3], pd(9, 512)) and okr(res[4], rawsec(39, 1, 16)) and okr(res[5], rawsec(5, 1, 2))
      and okr(res[6], rawsec(4, 1, 16)) and okw(res[7]) and okr(res[8], pd(5, 1024)) and okr(res[9], rawsec(39, 1, 1))
      and okw(res[10]) and okr(res[11], pd(8, 256)) and res[12]["st"] == 0x10 and okr(res[13], rawsec(39, 1, 16))
      and okr(res[14], rawsec(5, 1, 1)) and okr(res[15], rawsec(0, 0, 1)), [(x["ret"], x["st"]) for x in res])

# フォーマットされていないトラック (ディスクの終わりに足す)、テーブルの最後、テーブルの外
w5, t5 = geo(50, 0, 1, 16)
w6, t6 = geo(41, 1, 3, 5)
w7, t7 = geo(81, 1, 0, 3)
res, after = run(imgA, [OPEN, rd(50, 0, 3), wt(50, 0, 0), rd(50, 0, 3), wt(41, 1, 1), rd(41, 1, 5), rd(50, 0, 16),
                        wt(81, 1, 2), rd(81, 1, 2), wt(82, 0, 2), rd(39, 1, 16)], [w5, w6, w7])
exp = apply(apply(apply(imgA, 100, t5), 83, t6), 163, t7)
fcheck("F new", after, exp)
check("F new res", res[1]["st"] == 0x10 and okw(res[2]) and okr(res[3], pd(3, 256)) and okw(res[4]) and okr(res[5], pd(5, 1024))
      and okr(res[6], pd(16, 256)) and okw(res[7]) and okr(res[8], pd(2, 128))
      and res[9]["ret"] == 0xFF and res[9]["st"] == 0x20 and okr(res[10], rawsec(39, 1, 16)), [(x["ret"], x["st"]) for x in res])

# 最後のトラック (後ろにずらすものがない)
w8, t8 = geo(39, 1, 2, 9)
res, after = run(imgA, [OPEN, wt(39, 1, 0), rd(39, 1, 9), rd(39, 0, 16)], [w8])
fcheck("F last", after, apply(imgA, 79, t8))
check("F last res", okw(res[1]) and okr(res[2], pd(9, 512)) and okr(res[3], rawsec(39, 0, 16)), [(x["ret"], x["st"]) for x in res])

# テーブルが 160 個のイメージ (テーブルのすぐ後ろのトラックを壊さない)。160 番めからはテーブルの外
w9, t9 = geo(0, 0, 1, 16)
wa, ta = geo(1, 0, 2, 9)
res, after = run(imgB, [OPEN, wt(0, 0, 0), rd(0, 0, 16), rd(1, 1, 2), rd(79, 1, 1), wt(1, 0, 1), rd(1, 0, 9), rd(79, 1, 1),
                        wt(80, 0, 0), rd(1, 1, 1)], [w9, wa])
exp = apply(apply(imgB, 0, t9), 2, ta)
fcheck("F 160", after, exp)
check("F 160 res", okw(res[1]) and okr(res[2], pd(16, 256)) and okr(res[3], d(256, 11)) and okr(res[4], d(256, 12)) and okw(res[5])
      and okr(res[6], pd(9, 512)) and okr(res[7], d(256, 12)) and res[8]["ret"] == 0xFF and res[8]["st"] == 0x20
      and okr(res[9], d(256, 10)), [(x["ret"], x["st"]) for x in res])

# ID がひとつもないデータ (Write Fault、ファイルは変わらない)
res, after = run(imgA, [OPEN, rd(5, 0, 1), wt(5, 0, 0), rd(5, 0, 1), wt(60, 0, 0), rd(60, 0, 1)], [b"\x4E" * 0x1900])
check("F no id", after == imgA and res[2]["ret"] == 0x7F and res[2]["st"] == 0x20 and okr(res[3], rawsec(5, 0, 1))
      and res[4]["st"] == 0x20 and res[5]["st"] == 0x10, [(x["ret"], x["st"]) for x in res])

# 削除マーク、データのない ID、N が 4 以上、途中で切れたセクタ
wb = fmt([(7, 0, 1, 1, 0xFB, pd(1, 256)), (7, 0, 2, 1, 0xF8, pd(2, 256)), (7, 0, 3, 1, 0xFB, None), (7, 0, 4, 5, 0xFB, pd(4, 256)),
          (7, 0, 5, 3, 0xFB, pd(5, 1024)), (7, 0, 6, 3, 0xFB, pd(6, 1024)), (7, 0, 7, 3, 0xFB, pd(7, 1024)),
          (7, 0, 8, 3, 0xFB, pd(8, 1024)), (7, 0, 9, 3, 0xFB, pd(9, 1024)), (7, 0, 10, 3, 0xFB, pd(10, 1024))], cut=True)
tb = trk([(7, 0, 1, 1, 0, pd(1, 256)), (7, 0, 2, 1, 0x10, pd(2, 256)), (7, 0, 4, 5, 0, pd(4, 256))]
         + [(7, 0, r, 3, 0, pd(r, 1024)) for r in (5, 6, 7, 8)])
res, after = run(imgA, [OPEN, wt(7, 0, 0), rd(7, 0, 2), rd(7, 0, 3), rd(7, 0, 4), rd(7, 0, 8), rd(7, 0, 9)], [wb])
fcheck("F marks", after, apply(imgA, 14, tb))
check("F marks res", okw(res[1]) and okr(res[2], pd(2, 256)) and res[2]["erd"] == 0xFF20 and res[3]["st"] == 0x10
      and okr(res[4], pd(4, 256)) and res[4]["erd"] == 0xFF00 and okr(res[5], pd(8, 1024)) and res[6]["st"] == 0x10,
      [(x["ret"], x["st"], hex(x["erd"])) for x in res])

# 単密度 (ID の前に $F5 がない)
wc = fmt([(2, 1, r, 0, 0xFB, pd(r, 128)) for r in range(1, 17)], fm=True, gap3=27)
tc = trk([(2, 1, r, 0, 0, pd(r, 128)) for r in range(1, 17)], dens=0x40)
res, after = run(imgA, [OPEN, wt(2, 1, 0), rd(2, 1, 16), rd(2, 0, 1)], [wc])
fcheck("F fm", after, apply(imgA, 5, tc), len(imgA))
check("F fm res", okw(res[1]) and okr(res[2], pd(16, 128)) and okr(res[3], rawsec(2, 0, 1)), [(x["ret"], x["st"]) for x in res])

# 複数枚のイメージ (2 枚めもいっしょにずれる)
res, after = run(imgD, [OPEN, wt(5, 0, 0), rd(5, 0, 9), wt(5, 0, 1), rd(5, 0, 8), rd(39, 1, 16)], [w2, w4])
ed = apply(imgD, 10, t2)
check("F multi tail", ed[len(imgA) + 400:] == imgD[len(imgA):])
fcheck("F multi", after, apply(ed, 10, t4), len(ed))
check("F multi res", okw(res[1]) and okr(res[2], pd(9, 512)) and okw(res[3]) and okr(res[4], pd(8, 256))
      and okr(res[5], rawsec(39, 1, 16)), [(x["ret"], x["st"]) for x in res])

print("FAILS", fails)
