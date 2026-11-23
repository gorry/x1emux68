# X1IO.o の FDC ポートを通したテスト。tmpb で実行する。
#   T2N.x = 変更後の X1IO + X1D88 / T2O.x = 変更前の X1IO
import os, random, struct, subprocess, sys

RUN68, D88MAKE = sys.argv[1], sys.argv[2]
fails = 0


def check(name, cond, info=""):
    global fails
    if not cond:
        fails += 1
        print("NG", name, str(info)[:300])


class Script:
    def __init__(self):
        self.c, self.reads = [], []

    def out(self, port, v):
        self.c.append(struct.pack(">BBBBHH", 0, port, v & 255, 0, 1, 0))

    def outs(self, port, v, n):
        self.c.append(struct.pack(">BBBBHH", 2, port, v & 255, 0, n, 0))

    def name(self, slot):
        self.c.append(struct.pack(">BBBBHH", 3, 0, slot, 0, 0, 0))

    def chg(self, drive):
        self.c.append(struct.pack(">BBBBHH", 4, drive, 0, 0, 0, 0))

    def set0(self):
        self.c.append(struct.pack(">BBBBHH", 5, 0, 0, 0, 0, 0))

    def inp(self, port, n=1, tag=""):
        self.c.append(struct.pack(">BBBBHH", 1, port, 0, 0, n, 0))
        self.reads.append((tag, n))

    # ---- X1 のプログラムがするような手順
    def select(self, head, drive=0, motor=1):
        self.out(0xFC, (motor << 7) | (head << 4) | drive)

    def seek(self, cyl):
        self.out(0xFB, cyl); self.out(0xF8, 0x10); self.inp(0xF8, 1, "seek st")

    def read(self, sec, n=256, cmd=0x80, tag="", poll=True):
        self.out(0xFA, sec); self.out(0xF8, cmd)
        if poll:
            self.inp(0xF8, 1, tag + " st0")
        else:
            self.inp(0xFB, 1, tag + " dummy")
        self.inp(0xFB, n, tag + " data")
        self.inp(0xF8, 1, tag + " st1")

    def write(self, sec, fill, n=256, cmd=0xA0, tag=""):
        self.out(0xFA, sec); self.out(0xF8, cmd)
        self.inp(0xF8, 1, tag + " st0")
        self.outs(0xFB, fill, n)
        self.inp(0xF8, 1, tag + " st1")

    def wrtrk(self, data, tag=""):
        self.out(0xFA, 1); self.out(0xF8, 0xF0)
        self.inp(0xF8, 1, tag + " st0")
        for b in data:
            self.out(0xFB, b)
        self.inp(0xF8, 1, tag + " st1")

    def readid(self, tag=""):
        self.out(0xF8, 0xC0); self.inp(0xF8, 1, tag + " st0"); self.inp(0xFB, 6, tag + " id"); self.inp(0xF8, 1, tag + " st1")


def run(exe, img, sc):
    open("T.IMG", "wb").write(img)
    open("T.CMD", "wb").write(b"".join(sc.c))
    if os.path.exists("T.OUT"):
        os.remove("T.OUT")
    r = subprocess.run([RUN68, exe], capture_output=True)
    if r.stdout.strip() or r.stderr.strip():
        print("run68:", r.stdout[:200], r.stderr[:200])
    out = open("T.OUT", "rb").read()
    res, p = {}, 0
    for tag, n in sc.reads:
        res.setdefault(tag, []).append(out[p:p + n]); p += n
    warn = struct.unpack(">II", out[p:p + 8]) if len(out) == p + 8 else None
    check("output size " + exe, warn is not None, (len(out), p))
    return res, warn, open("T.IMG", "rb").read()


def fmt(c, h, fill):
    """16 セクタ・256 バイトのフォーマットで FDC に渡すデータ ($1900 バイト)"""
    b = b"\x4E" * 80 + bytes(12) + b"\xF6" * 3 + b"\xFC" + b"\x4E" * 50
    for r in range(1, 17):
        b += bytes(12) + b"\xF5" * 3 + bytes([0xFE, c, h, r, 1, 0xF7]) + b"\x4E" * 22
        b += bytes(12) + b"\xF5" * 3 + b"\xFB" + bytes([fill]) * 256 + b"\xF7" + b"\x4E" * 54
    return b.ljust(0x1900, b"\x4E")


def d88toraw(img):
    offs = struct.unpack_from("<164I", img, 0x20)
    raw = b""
    for t in range(80):
        p, secs = offs[t], {}
        for _ in range(16):
            size = struct.unpack_from("<H", img, p + 14)[0]
            secs[img[p + 2]] = img[p + 16:p + 16 + size]
            p += 16 + size
        raw += b"".join(secs[r] for r in range(1, 17))
    return raw


random.seed(2)
raw = bytes(random.randrange(256) for _ in range(327680))
open("T.2D", "wb").write(raw)
subprocess.run([sys.executable, D88MAKE, "-i", "T.2D", "A.D88"], check=True, capture_output=True)
d88 = open("A.D88", "rb").read()


def scenario(common_only):
    s = Script()
    s.inp(0xF8, 1, "init st")
    for (c, h, r) in [(0, 0, 1), (0, 1, 16), (1, 0, 2), (20, 1, 9), (39, 1, 16), (39, 0, 1)]:
        s.select(h); s.seek(c); s.read(r, tag="rd %d/%d/%d" % (c, h, r))
    s.select(0); s.seek(5); s.read(3, tag="rd nopoll", poll=False)
    s.select(1); s.seek(7); s.read(1, n=4096, cmd=0x90, tag="rdm", poll=False)
    s.select(0); s.seek(9); s.read(1, n=4096, cmd=0xE0, tag="rdtrk", poll=False); s.inp(0xFB, 0x900, "rdtrk rest"); s.inp(0xF8, 1, "rdtrk end")
    s.select(1); s.seek(3); s.write(5, 0x10, tag="wr"); s.read(5, tag="wr reread")
    s.select(0); s.seek(8); s.write(1, 0x33, n=4096, cmd=0xB0, tag="wrm"); s.read(16, tag="wrm reread")
    s.select(0); s.seek(6); s.wrtrk(fmt(6, 0, 0xFF), tag="wrtrk"); s.read(7, tag="wrtrk reread")
    s.select(0, motor=0); s.inp(0xF8, 1, "motor off st")
    s.select(1); s.seek(20); s.read(9, tag="again")
    # 中断 (FORCE INTERRUPT) のあとのリード
    s.out(0xFA, 2); s.out(0xF8, 0x80); s.inp(0xF8, 1, "abort st0"); s.inp(0xFB, 10, "abort data")
    s.out(0xF8, 0xD0); s.inp(0xF8, 1, "abort st1"); s.read(10, tag="after abort")
    s.out(0xF8, 0x00); s.inp(0xF8, 1, "restore st"); s.inp(0xF9, 1, "restore tr"); s.read(1, tag="rd trk0")
    if not common_only:
        s.select(1); s.seek(12)
        for k in range(18):
            s.readid("id")
        s.select(0); s.seek(4); s.read(17, tag="rnf"); s.write(17, 0, tag="wr rnf")
        s.select(0); s.seek(45); s.read(1, tag="rd cyl45"); s.readid("id cyl45")
        s.wrtrk(fmt(45, 0, 0xE5), tag="wrtrk cyl45"); s.read(3, tag="rd cyl45 new"); s.select(1); s.seek(39); s.read(16, tag="rd last")
        s.select(0); s.seek(10); s.out(0xF9, 11); s.read(1, tag="tr mismatch"); s.out(0xF9, 10); s.read(1, tag="tr match")
    return s


# ---- 1. 2Dのベタイメージ: 変更前と変更後で同じ動きをする
s = scenario(True)
ro, wo, fo = run("T2O.x", raw, s)
rn, wn, fn = run("T2N.x", raw, s)
check("raw: same reads", ro == rn, [k for k in ro if ro[k] != rn.get(k)])
check("raw: same file", fo == fn and fo != raw)
check("raw: same warn", wo == wn, (wo, wn))
print("warn (d0/d1 upper) old,new:", wo, wn)
check("raw: end status", rn["rdm st1"] == [bytes([0x10])] and rn["rdtrk end"] == [bytes([4])] and rn["wrm st1"] == [bytes([0x10])] and rn["wr st1"] == [bytes([0])], (rn["rdm st1"], rn["rdtrk end"], rn["wrm st1"]))
check("raw: rd", ro["rd 20/1/9 data"][0] == raw[20 * 0x2000 + 0x1000 + 0x800:][:256])

# ---- 2. D88: 同じ手順で同じデータが読み書きできる
s = scenario(False)
rd, wd, fd = run("T2N.x", d88, s)
print("warn (d0/d1 upper) d88:", wd)
for k in rn:
    if k in ("rdtrk rest",):
        continue
    check("d88 = raw: " + k, rd[k][:len(rn[k])] == rn[k], (rd[k][0][:8], rn[k][0][:8]))
check("d88 rdtrk rest", rd["rdtrk rest"][0] == bytes(0x900) and rd["rdtrk end"] == [b"\x04"], rd["rdtrk end"])
check("d88 file = raw file", d88toraw(fd) == fn, sum(a != b for a, b in zip(d88toraw(fd), fn)))
# シリンダ 45 をフォーマットしたので、トラック 90 がディスクの終わりに足されている
hd = bytearray(d88[:0x2B0]); struct.pack_into("<I", hd, 0x1C, len(d88) + 16 * 272); struct.pack_into("<I", hd, 0x20 + 90 * 4, len(d88))
check("d88 header", fd[:0x2B0] == bytes(hd) and len(fd) == len(d88) + 16 * 272, (len(fd), len(d88)))
check("d88 new track", fd[len(d88):] == b"".join(struct.pack("<BBBBHBBB5xH", 45, 0, r, 1, 16, 0, 0, 0, 256) + b"\xE5" * 256 for r in range(1, 17)))
ids = rd["id id"]
check("d88 id", sorted(x[2] for x in ids[:16]) == list(range(1, 17)) and all(x[0] == 12 and x[1] == 1 and x[3] == 1 for x in ids)
      and ids[16] == ids[0] and all(x == b"\x03" for x in rd["id st0"]) and all(x == b"\x00" for x in rd["id st1"]), ids[:3])
check("d88 rnf", rd["rnf st0"] == [b"\x10"] and rd["wr rnf st0"] == [b"\x10"], (rd["rnf st0"], rd["wr rnf st0"]))
check("d88 cyl45", rd["rd cyl45 st0"] == [b"\x10"] and rd["id cyl45 st0"] == [b"\x10"] and rd["wrtrk cyl45 st0"] == [b"\x03"]
      and rd["wrtrk cyl45 st1"] == [b"\x00"] and rd["rd cyl45 new st0"] == [b"\x03"] and rd["rd cyl45 new data"] == [b"\xE5" * 256]
      and rd["rd last data"] == [raw[39 * 0x2000 + 0x1F00:][:256]],
      (rd["rd cyl45 st0"], rd["id cyl45 st0"], rd["wrtrk cyl45 st0"], rd["wrtrk cyl45 st1"], rd["rd cyl45 new st0"]))
check("d88 tr", rd["tr mismatch st0"] == [b"\x10"] and rd["tr match st0"] == [b"\x03"]
      and rd["tr match data"][0] == raw[10 * 0x2000:][:256], (rd["tr mismatch st0"], rd["tr match st0"]))

# ---- 3. D88: 書き込み禁止のヘッダ
p = bytearray(d88); p[0x1A] = 0x10
s = Script(); s.select(0); s.inp(0xF8, 1, "sel st"); s.seek(2); s.read(4, tag="rd")
s.out(0xFA, 4); s.out(0xF8, 0xA0); s.inp(0xF8, 1, "wr st")
r3, w3, f3 = run("T2N.x", bytes(p), s)
check("d88 protect", r3["sel st"] == [b"\x40"] and r3["wr st"] == [b"\x40"] and r3["rd data"][0] == raw[2 * 0x2000 + 0x300:][:256]
      and f3 == bytes(p), (r3["sel st"], r3["wr st"]))

# ---- 4. D88: 256バイトでないセクタ、削除マーク、CRCエラー
def sec(c, h, r, n, dl, st, data, ns):
    return struct.pack("<BBBBHBBB5xH", c, h, r, n, ns, 0, dl, st, len(data)) + data
dd = lambda n, k: bytes((k * 11 + i * 5) & 255 for i in range(n))
trk = [(1, 2, 0, 0, 512), (2, 3, 0, 0, 1024), (3, 0, 0, 0, 128), (4, 1, 0x10, 0x10, 256), (5, 1, 0, 0xB0, 256)]
body = b"".join(sec(0, 0, r, n, dl, st, dd(z, r), len(trk)) for (r, n, dl, st, z) in trk)
img = b"X".ljust(26, b"\0") + bytes([0, 0]) + struct.pack("<I", 0x2B0 + len(body)) + struct.pack("<164I", 0x2B0, *([0] * 163)) + body
s = Script(); s.select(0); s.seek(0)
for (r, n, dl, st, z) in trk:
    s.read(r, n=z, tag="s%d" % r)
s.write(1, 0x21, n=512, tag="w1"); s.read(1, n=512, tag="w1 reread")
s.write(4, 0x22, tag="w4"); s.read(4, tag="w4 reread")
r4, w4, f4 = run("T2N.x", img, s)
for (r, n, dl, st, z) in trk:
    e = {4: 0x20, 5: 0x08}.get(r, 0)
    check("odd s%d" % r, r4["s%d st0" % r] == [b"\x03"] and r4["s%d data" % r][0] == dd(z, r) and r4["s%d st1" % r] == [bytes([e])],
          (r4["s%d st0" % r], r4["s%d st1" % r]))
pat = lambda f, n: bytes((f + i) & 255 for i in range(n))
check("odd w1", r4["w1 st0"] == [b"\x03"] and r4["w1 st1"] == [b"\x00"] and r4["w1 reread data"][0] == pat(0x21, 512), (r4["w1 st0"], r4["w1 st1"]))
check("odd w4", r4["w4 reread data"][0] == pat(0x22, 256) and r4["w4 reread st1"] == [b"\x00"], r4["w4 reread st1"])

# ---- 5. ディスクイメージの入れ替え (ドライブ0: 組0=T.IMG(D88) 組2=SI.IMG(2D) 組5=SU.IMG(D88) / ドライブ1: 組0だけ)
rawB = bytes(random.randrange(256) for _ in range(327680))
open("T.2D", "wb").write(bytes(x ^ 0x5A for x in raw))
subprocess.run([sys.executable, D88MAKE, "-i", "T.2D", "SU.IMG"], check=True, capture_output=True)
open("SI.IMG", "wb").write(rawB)
rawC = bytes(x ^ 0x5A for x in raw)
want = lambda img, c, h, r: img[c * 0x2000 + h * 0x1000 + (r - 1) * 0x100:][:256]
s = Script(); s.set0(); s.name(2 * 4 + 0); s.name(5 * 4 + 0)
s.select(1); s.seek(3); s.read(2, tag="p0")                       # 組0
s.chg(0); s.read(2, tag="p1")                                     # 組2 (モーターONのまま)
s.write(9, 0x44, tag="w"); s.read(9, tag="p1w")
s.chg(0); s.select(1, motor=0); s.select(1); s.seek(3); s.read(2, tag="p2")   # 組5 (モーターOFFの間に)
s.chg(0); s.read(2, tag="p3")                                     # 組0 に戻る
s.chg(1); s.read(2, tag="p4")                                     # ドライブ1は組0だけ: 変わらない
s.chg(0); s.chg(0); s.read(2, tag="p5")                           # 2回押す: 組2を飛び越えて組5
s.chg(0); s.chg(0); s.read(2, tag="p6")                           # 2回押す: 組0を通って組2
s.read(9, tag="p6w")
s.chg(0); s.chg(0); s.chg(0); s.read(2, tag="p7")                 # 3回押す: 一周して組2のまま
r5, w5, f5 = run("T2N.x", d88, s)
exp = {"p0": raw, "p1": rawB, "p2": rawC, "p3": raw, "p4": raw, "p5": rawC, "p6": rawB, "p7": rawB}
for k, img in exp.items():
    check("swap " + k, r5[k + " st0"] == [bytes([3])] and r5[k + " data"][0] == want(img, 3, 1, 2), (k, r5[k + " st0"]))
patw = bytes((0x44 + i) & 255 for i in range(256))
after = open("SI.IMG", "rb").read()
check("swap write", r5["p1w data"][0] == patw and r5["p6w data"][0] == patw and want(after, 3, 1, 9) == patw
      and f5 == d88 and open("SU.IMG", "rb").read()[0x2B0:0x2C0] is not None)

print("FAILS", fails)
