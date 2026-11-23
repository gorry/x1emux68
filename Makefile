AS = has.x
LD = hlk.x

ASFLAGS = -w -o $@ $<

ASM = $(AS) $(ASFLAGS)

SRCDIR = src
OBJDIR = obj
PKGDIR = package

.PHONY: x clean arc

x	:	X1.x X1DB.x

X1.x		:	$(OBJDIR)/X1STAT.o $(OBJDIR)/DMYZ80DB.o $(OBJDIR)/X1EMU.o $(OBJDIR)/Z801.o $(OBJDIR)/Z802.o $(OBJDIR)/X1D88.o $(OBJDIR)/X1IO.o
	$(LD) $^ -o $@ > err.err

X1DB.x		:	$(OBJDIR)/X1STAT.o $(OBJDIR)/Z80DB.o $(OBJDIR)/Z80DIS.o $(OBJDIR)/X1EMUDB.o $(OBJDIR)/Z801_DB.o $(OBJDIR)/Z802_DB.o $(OBJDIR)/X1D88.o $(OBJDIR)/X1IO.o
	$(LD) $^ -o $@ > err.err

$(OBJDIR)/X1EMU.o		:	$(SRCDIR)/X1EMU.has
	$(ASM) -s Z80DEBUG=0 > err.err

$(OBJDIR)/X1EMUDB.o	:	$(SRCDIR)/X1EMU.has
	$(ASM) -s Z80DEBUG=1 > err.err

$(OBJDIR)/Z801.o		:	$(SRCDIR)/Z80.has
	$(ASM) -s F_ROM=0 -s Z80DEBUG=0 > err.err

$(OBJDIR)/Z802.o		:	$(SRCDIR)/Z80.has
	$(ASM) -s F_ROM=1 -s Z80DEBUG=0 > err.err

$(OBJDIR)/Z801_DB.o	:	$(SRCDIR)/Z80.has
	$(ASM) -s F_ROM=0 -s Z80DEBUG=1 > err.err

$(OBJDIR)/Z802_DB.o	:	$(SRCDIR)/Z80.has
	$(ASM) -s F_ROM=1 -s Z80DEBUG=1 > err.err

$(OBJDIR)/X1IO.o		:	$(SRCDIR)/X1IO.has
	$(ASM) > err.err

$(OBJDIR)/X1D88.o	:	$(SRCDIR)/X1D88.has
	$(ASM) > err.err

$(OBJDIR)/X1STAT.o	:	$(SRCDIR)/X1STAT.has
	$(ASM) > err.err

$(OBJDIR)/Z80DB.o		:	$(SRCDIR)/Z80DB.has
	$(ASM) -s DUMMYDB=0 > err.err

$(OBJDIR)/DMYZ80DB.o	:	$(SRCDIR)/Z80DB.has
	$(ASM) -s DUMMYDB=1 > err.err

$(OBJDIR)/Z80DIS.o	:	$(SRCDIR)/Z80DIS.has
	$(ASM) > err.err

clean:
	-rm -f obj/*.o X1.x X1DB.x err.err

arc	:	$(PKGDIR)/X1EmuX68_202611231.lzh

$(PKGDIR)/X1EmuX68_202611231.lzh	:	X1.x X1DB.x CONFIG.X1.sample README.txt NOTICE LICENSE doc/X1.DOC doc/X1VG.DOC 2DTOOL.LZH SRC.LZH
	-rm $@
	-mkdir $(PKGDIR)
	lha a -x $@ $^
	-rm README.txt

README.txt	:	README.md
	nkf -s -Lw $< > $@

SRC.LZH : $(SRCDIR)/*.has z80/*.* Makefile
	-rm $@
	lha a -x $@ $^

