# test/ のテストをビルドして実行する。X1.x・X1DB.x のビルドもできる。Windows の上で、run68x を使う。
#   usage: python test/run.py [t88] [t2] [t3] [t4]   (名前を省くと、テストを全部)
#          python test/run.py build                  (X1.x・X1DB.x を作る。Makefile の x と同じもの)
#   build は test/work で作ってから、X1.x・X1DB.x をリポジトリ直下に、*.o を obj/ にコピーする。
#   作業フォルダは test/work (中身は毎回作り直す)。パスが長いと HAS が出力ファイルを開けない。
#   場所を変えるときは、環境変数で指定する:
#     X1TEST_TOOLS   tools フォルダ (既定: ../../tools。run68x/run68.exe・has309/HAS.X・HLK301B/hlk301.x・macros/*.MAC を使う)
#     X1TEST_WORK    作業フォルダ   (既定: test/work)
import os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.abspath(os.environ.get("X1TEST_TOOLS") or os.path.join(ROOT, "..", "..", "tools"))
SRC = os.path.join(ROOT, "src")
RUN68 = os.path.join(TOOLS, "run68x", "run68.exe")
D88MAKE = os.path.join(HERE, "d88make.py")
WORK = os.environ.get("X1TEST_WORK") or os.path.join(HERE, "work")
HAS = os.path.join(TOOLS, "has309", "HAS.X")
HLK = os.path.join(TOOLS, "HLK301B", "hlk301.x")
OLD_X1IO = "f76399e"            # D88 対応の前の X1IO.has があるコミット (t2 が結果を比べる相手)
TESTS = ["t88", "t2", "t3", "t4"]


def die(msg):
    print("ERROR:", msg)
    sys.exit(2)


def tool(exe, *args):
    r = subprocess.run([RUN68, exe, *args], cwd=WORK, capture_output=True)
    return (r.stdout + r.stderr).decode("cp932", "replace").strip()


def asm(src, obj, *flags):
    if os.path.exists(os.path.join(WORK, obj)):
        return
    out = tool(HAS, "-w", src, *flags, "-o", obj)
    if out or not os.path.exists(os.path.join(WORK, obj)):
        die("assemble %s -> %s\n%s" % (src, obj, out))


def link(exe, *objs):
    out = tool(HLK, *objs, "-o", exe)
    if out or not os.path.exists(os.path.join(WORK, exe)):
        die("link %s\n%s" % (exe, out))


def write(name, data):
    open(os.path.join(WORK, name), "wb").write(data)


def stat_copy():
    """X1STAT.has のコピー: VRAM・パレット・CRTC の equ を xref にし、rte を通常の復帰にする"""
    s = open(os.path.join(SRC, "X1STAT.has"), "rb").read()
    names = [b"GVRAM", b"TVRAM", b"TXTPAL", b"CRTC06", b"CRTC07", b"CRTC21"]
    for i, n in enumerate(names):
        rep = b"\t.xref\t" + b",".join(names) + b"\r\n" if i == 0 else b""
        s, c = re.subn(rb"(?m)^" + n + rb"[ \t]+equ[ \t][^\n]*\n", lambda m: rep, s)
        if c != 1:
            die("X1STAT.has: %s の equ が %d 個" % (n.decode(), c))
    s, c = re.subn(rb"(?m)^(\w+:)?([ \t]+)rte[ \t]*\r?$",
                   lambda m: (m.group(1) or b"") + b"\taddq.l\t#2,sp\r\n\trts\r", s)
    if c != 1:
        die("X1STAT.has: rte が %d 個" % c)
    write("X1STATT.has", s)


def build_t88():
    asm("X1D88.has", "X1D88.o")
    asm("T88.has", "T88.o")
    link("T88.x", "T88.o", "X1D88.o")


def build_t2():
    r = subprocess.run(["git", "-C", ROOT, "show", OLD_X1IO + ":src/X1IO.has"], capture_output=True)
    if r.returncode:
        die("git show %s:src/X1IO.has\n%s" % (OLD_X1IO, r.stderr.decode("utf-8", "replace")))
    # I0F00・O0F00 は .xdef されていないので、テスト用のコピーにだけ足す
    xdef = b"\t.xdef\tI0F00,O0F00\r\n"
    write("X1IOO.has", xdef + r.stdout)
    write("X1IOT.has", xdef + open(os.path.join(SRC, "X1IO.has"), "rb").read())
    asm("X1D88.has", "X1D88.o")
    asm("X1IOT.has", "X1IOT.o")
    asm("X1IOO.has", "X1IOO.o")
    asm("T2.has", "T2N.o", "-s", "FDSW=1")
    asm("T2.has", "T2O.o", "-s", "FDSW=0")
    link("T2N.x", "T2N.o", "X1IOT.o", "X1D88.o")
    link("T2O.x", "T2O.o", "X1IOO.o")


def build_t3():
    stat_copy()
    asm("X1STATT.has", "X1STATT.o")
    asm("T3.has", "T3.o")
    link("T3.x", "T3.o", "X1STATT.o")


def build_t4():
    asm("X1STAT.has", "X1STAT.o")
    asm("Z80DB.has", "DMYZ80DB.o", "-s", "DUMMYDB=1")
    asm("Z80.has", "Z801.o", "-s", "F_ROM=0", "-s", "Z80DEBUG=0")
    asm("Z80.has", "Z802.o", "-s", "F_ROM=1", "-s", "Z80DEBUG=0")
    asm("X1D88.has", "X1D88.o")
    asm("X1IO.has", "X1IO.o")


# Makefile の x と同じ内容。Makefile を変えたら、ここも合わせる。
OBJS = [
    ("X1EMU.o", "X1EMU.has", ["-s", "Z80DEBUG=0"]),
    ("X1EMUDB.o", "X1EMU.has", ["-s", "Z80DEBUG=1"]),
    ("Z801.o", "Z80.has", ["-s", "F_ROM=0", "-s", "Z80DEBUG=0"]),
    ("Z802.o", "Z80.has", ["-s", "F_ROM=1", "-s", "Z80DEBUG=0"]),
    ("Z801_DB.o", "Z80.has", ["-s", "F_ROM=0", "-s", "Z80DEBUG=1"]),
    ("Z802_DB.o", "Z80.has", ["-s", "F_ROM=1", "-s", "Z80DEBUG=1"]),
    ("X1IO.o", "X1IO.has", []),
    ("X1D88.o", "X1D88.has", []),
    ("X1STAT.o", "X1STAT.has", []),
    ("Z80DB.o", "Z80DB.has", ["-s", "DUMMYDB=0"]),
    ("DMYZ80DB.o", "Z80DB.has", ["-s", "DUMMYDB=1"]),
    ("Z80DIS.o", "Z80DIS.has", []),
]
EXES = [
    ("X1.x", ["X1STAT.o", "DMYZ80DB.o", "X1EMU.o", "Z801.o", "Z802.o", "X1D88.o", "X1IO.o"]),
    ("X1DB.x", ["X1STAT.o", "Z80DB.o", "Z80DIS.o", "X1EMUDB.o", "Z801_DB.o", "Z802_DB.o", "X1D88.o", "X1IO.o"]),
]


def build_build():
    for obj, src, flags in OBJS:
        asm(src, obj, *flags)
    for exe, objs in EXES:
        link(exe, *objs)
    os.makedirs(os.path.join(ROOT, "obj"), exist_ok=True)
    for obj, _, _ in OBJS:
        shutil.copy(os.path.join(WORK, obj), os.path.join(ROOT, "obj", obj))
    for exe, _ in EXES:
        shutil.copy(os.path.join(WORK, exe), os.path.join(ROOT, exe))
        print(exe, os.path.getsize(os.path.join(ROOT, exe)))


ARGS = {"t88": [RUN68, D88MAKE], "t2": [RUN68, D88MAKE], "t3": [RUN68], "t4": [RUN68, TOOLS, SRC]}

sel = sys.argv[1:] or TESTS
for t in sel:
    if t not in TESTS + ["build"]:
        die("usage: run.py [%s] | build" % "] [".join(TESTS))
for p in [RUN68, HAS, HLK] + ([D88MAKE] if {"t88", "t2"} & set(sel) else []):
    if not os.path.exists(p):
        die("ファイルがない: " + p)

shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
for d, pat in ((SRC, r"\.has$"), (HERE, r"^T\w+\.has$"), (os.path.join(TOOLS, "macros"), r"\.MAC$")):
    for f in os.listdir(d):
        if re.search(pat, f):
            shutil.copy(os.path.join(d, f), os.path.join(WORK, f))

bad = []
for t in sel:
    print("==", t, flush=True)
    globals()["build_" + t]()
    if t == "build":
        continue
    r = subprocess.run([sys.executable, os.path.join(HERE, t + ".py"), *ARGS[t]], cwd=WORK,
                       capture_output=True, text=True, errors="replace")
    out = (r.stdout + r.stderr).rstrip()
    print(out, flush=True)
    if r.returncode or not out.endswith("FAILS 0"):
        bad.append(t)

print("== NG: " + " ".join(bad) if bad else "== OK")
sys.exit(1 if bad else 0)
