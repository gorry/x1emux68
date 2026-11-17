# ROM・CONFIGファイル・ディスクイメージを探すフォルダのテスト。短いパスの作業フォルダで実行する。
#   usage: t4.py <run68> <tools> <src>
#   作業フォルダに X1STAT.o DMYZ80DB.o Z801.o Z802.o X1D88.o X1IO.o と DOSCALL.MAC・IOCSCALL.MAC があること
#   X1EMU.has のコピーに「ROM を読んだあとで名前を表示して終わる」処理を入れた X1T.x を作って動かす
import os, shutil, subprocess, sys

RUN68, TOOLS, SRC = sys.argv[1:4]
fails = 0
BS = "\\"


def check(name, cond, info=""):
    global fails
    if not cond:
        fails += 1
        print("NG", name, str(info)[:400])


s = open(os.path.join(SRC, "X1EMU.has"), "rb").read().decode("cp932")
a = "\tjsr\tLDROM\r\n"
assert s.count(a) == 1
s = s.replace(a, a + "\tjmp\tTDUMP\r\n")
a = "EXIT:\tdc.w\t$FF00"
assert s.count(a) == 1
s = s.replace(a, """TDUMP:
	lea	FDNAME,a1
	moveq	#40-1,d2
TD1:	lea	(a1),a0
	jsr	PRINT
	lea	TDNL,a0
	jsr	PRINT
	lea	$80(a1),a1
	dbra	d2,TD1
	move.b	IPLROM,TDCH
	move.b	CGROM+8,TDCH+1
	move.l	P_ROM,d0			* 読んでいなければ -1
	addq.l	#1,d0
	beq.s	TD2
	subq.l	#1,d0
	movea.l	d0,a0
	move.b	(a0),TDCH+2
TD2:	lea	TDCH,a0
	jsr	PRINT
	dc.w	$FF00
TDNL:	dc.b	$0D,$0A,0
TDCH:	dc.b	'---',$0D,$0A,0
	.even
""".replace("\n", "\r\n") + a)
open("X1EMUT.has", "wb").write(s.encode("cp932"))
r = subprocess.run([RUN68, os.path.join(TOOLS, "has309", "HAS.X"), "-w", "X1EMUT.has", "-s", "Z80DEBUG=0", "-o", "X1EMUT.o"],
                   capture_output=True)
check("assemble", not r.stdout.strip(), r.stdout.decode("cp932", "replace"))
r = subprocess.run([RUN68, os.path.join(TOOLS, "HLK301B", "hlk301.x"), "X1STAT.o", "DMYZ80DB.o", "X1EMUT.o", "Z801.o", "Z802.o",
                    "X1D88.o", "X1IO.o", "-o", "X1T.x"], capture_output=True)
check("link", not r.stdout.strip(), r.stdout.decode("cp932", "replace"))

shutil.rmtree("t", ignore_errors=True)
for d in ("exe", "cfg", "cfg/sub", "other", "abs", "cwd"):
    os.makedirs("t/" + d)
T = os.path.abspath("t")                 # H:\\...\t
TN = T[2:]                               # ドライブ名なし
shutil.copy("X1T.x", "t/exe/X1T.x")


def put(name, data=b"x"):
    open("t/" + name, "wb").write(data)


put("exe/IPLROM.X1", b"I" * 0x1000)
put("exe/CGROM.X1", b"C" * 0x800)
put("cwd/IPLROM.X1", b"x" * 0x1000)      # こちらは読まれないはず
put("cwd/CGROM.X1", b"x" * 0x800)
put("cfg/IPLROM.X1", b"y" * 0x1000)
put("cfg/R.BIN", b"R" * 0x10000)
put("cwd/R.BIN", b"x" * 0x10000)
for f in ("cfg/A.D88", "cfg/sub/B.D88", "other/C.D88", "abs/D.D88", "abs/E.D88", "cwd/A.D88", "cwd/X.D88"):
    put(f)


def cfg(name, lines):
    put(name, ("\r\n".join(lines) + "\r\n").encode("cp932"))


cfg("cfg/C1.X1", ["FD0=A.D88", "FD1=sub\\B.D88", "FD2=" + TN + "\\abs\\D.D88", "FD3=" + T + "\\abs\\E.D88",
                  "FD10=..\\other\\C.D88", "ROM=R.BIN", "CONFIG=sub\\C2.X1"])
cfg("cfg/sub/C2.X1", ["FD11=B.D88", "FD12=..\\A.D88", "FD13=/" + TN[1:].replace(BS, "/") + "/abs/D.D88"])
cfg("cwd/CONFIG.X1", ["FD0=A.D88"])
cfg("cfg/C3.X1", ["FD0=" + TN + "\\abs\\D.D88", "FD1=A.D88", "FD21=sub\\B.D88"])
cfg("cfg/C4.X1", ["FD0=" + "L" * 123])
cfg("cfg/C5.X1", ["FD0=NONE.D88", "FD1=A.D88"])
cfg("cfg/C6.X1", ["FD0=A.D88", "FD1=A.D88"])
cfg("cfg/C7.X1", ["FD0=" + "M" * (127 - len("..\\cfg\\"))])
cfg("cfg/C8.X1", ["FD0=" + "M" * (128 - len("..\\cfg\\"))])


def run(*args):
    # キー入力待ち (DOS _GETC) は run68 では進められないので、時間切れで止める
    p = subprocess.Popen([RUN68, "..\\exe\\X1T.x", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd="t/cwd")
    try:
        o = p.communicate(timeout=5)[0]
    except subprocess.TimeoutExpired:
        p.kill()
        o = p.communicate()[0]
    return o.decode("cp932", "replace").replace("\r", "").split("\n")


def dump(out):
    """表示の終わりの 41 行 = 名前 40 個 (組*4+ドライブ) と ROM の先頭の字"""
    while out and out[-1] == "":
        out.pop()
    return out[-41:-1], out[-1], out[:-41]


def names(d):
    e = [""] * 40
    for k, v in d.items():
        e[(k // 10) * 4 + k % 10] = v
    return e


C = "..\\cfg\\"
# -F で別のフォルダのファイル (拡張子は付け足される)
n, rom, head = dump(run("-F", "..\\cfg\\C1"))
check("A names", n == names({0: C + "A.D88", 1: C + "sub\\B.D88", 2: TN + "\\abs\\D.D88", 3: T + "\\abs\\E.D88",
                            10: C + "..\\other\\C.D88", 11: C + "sub\\B.D88", 12: C + "sub\\..\\A.D88",
                            13: "/" + TN[1:].replace(BS, "/") + "/abs/D.D88"}), n)
check("A rom", rom == "ICR", rom)
check("A open", not any("開けません" in x for x in head), head)
# -F なし
n, rom, head = dump(run())
check("B names", n == names({0: "A.D88"}), n)
check("B rom", rom == "IC-", rom)
check("B open", not any("開けません" in x for x in head), head)
# -F にファイル名がない
for a in (["-F"], ["-F", "-H"], ["-H", "-F"]):
    out = run(*a)
    check("C " + " ".join(a), any("CONFIGファイルが指定されていません" in x for x in out) and not any("A.D88" in x for x in out), out)
# -F がドライブ名つき
n, rom, head = dump(run("-F", T + "\\cfg\\C3.X1"))
check("D names", n == names({0: T[:2] + TN + "\\abs\\D.D88", 1: T + "\\cfg\\A.D88", 21: T + "\\cfg\\sub\\B.D88"}), n)
check("D open", not any("開けません" in x for x in head), head)
# 長すぎる名前
out = run("-F", "..\\cfg\\C4.X1")
check("E", any("CONFIGファイルに誤りがあります" in x for x in out), out)
out = run("-F", "..\\cfg\\C7.X1")          # ちょうど入る長さ (ファイルはないので、開けないという表示で確かめる)
check("E 127", any("FD0=" + C + "M" * 120 + " が開けません" in x for x in out), out)
out = run("-F", "..\\cfg\\C8.X1")
check("E 128", any("CONFIGファイルに誤りがあります" in x for x in out), out)
# -D はカレントフォルダから
n, rom, head = dump(run("-D", "FD0=X.D88", "-F", "..\\cfg\\C6.X1"))
check("F names", n == names({0: "X.D88", 1: C + "A.D88"}), n)
check("F open", not any("開けません" in x for x in head), head)
# ないファイル
head = run("-F", "..\\cfg\\C5.X1")
check("G", any("何かキーを押すと続行します" in x for x in head) and any("FD0=" + C + "NONE.D88 が開けません" in x for x in head) and sum("開けません" in x for x in head) == 1, head)
# ない CONFIGファイル
out = run("-F", "..\\cfg\\NONE")
check("H", any("..\\cfg\\NONE.X1 が見つかりません" in x for x in out), out)

print("FAILS", fails)
