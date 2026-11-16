AS = has.x
LD = hlk.x

SRCDIR = src
OBJDIR = obj

x	:	X1.x X1DB.x

X1.x		:	$(OBJDIR)/DMYZ80DB.o $(OBJDIR)/X1EMU.o $(OBJDIR)/Z801.o $(OBJDIR)/Z802.o $(OBJDIR)/X1IO.o
	$(LD) $^ -o $@ > err.err

X1DB.x		:	$(OBJDIR)/Z80DB.o $(OBJDIR)/Z80DIS.o $(OBJDIR)/X1EMUDB.o $(OBJDIR)/Z801_DB.o $(OBJDIR)/Z802_DB.o $(OBJDIR)/X1IO.o
	$(LD) $^ -o $@ > err.err

$(OBJDIR)/X1EMU.o		:	$(SRCDIR)/X1EMU.has
	$(AS) -w $^ -s Z80DEBUG=0 -o $@ > err.err

$(OBJDIR)/X1EMUDB.o	:	$(SRCDIR)/X1EMU.has
	$(AS) -w $^ -s Z80DEBUG=1 -o $@ > err.err

$(OBJDIR)/Z801.o		:	$(SRCDIR)/Z80.has
	$(AS) -w $^ -s F_ROM=0 -s Z80DEBUG=0 -o $@ > err.err

$(OBJDIR)/Z802.o		:	$(SRCDIR)/Z80.has
	$(AS) -w $^ -s F_ROM=1 -s Z80DEBUG=0 -o $@ > err.err

$(OBJDIR)/Z801_DB.o	:	$(SRCDIR)/Z80.has
	$(AS) -w $^ -s F_ROM=0 -s Z80DEBUG=1 -o $@ > err.err

$(OBJDIR)/Z802_DB.o	:	$(SRCDIR)/Z80.has
	$(AS) -w $^ -s F_ROM=1 -s Z80DEBUG=1 -o $@ > err.err

$(OBJDIR)/X1IO.o		:	$(SRCDIR)/X1IO.has
	$(AS) -w $^ -o $@ > err.err

$(OBJDIR)/Z80DB.o		:	$(SRCDIR)/Z80DB.has
	$(AS) -w $^ -s DUMMYDB=0 -o $@ > err.err

$(OBJDIR)/DMYZ80DB.o	:	$(SRCDIR)/Z80DB.has
	$(AS) -w $^ -s DUMMYDB=1 -o $@ > err.err

$(OBJDIR)/Z80DIS.o	:	$(SRCDIR)/Z80DIS.has
	$(AS) -w $^ -o $@ > err.err


arc	:	X1V100G4.zip
X1V100G4.zip	:	X1.x X1DB.x CONFIG.X1 doc/X1.DOC doc/X1VG.DOC SRC.zip 2DTOOL.zip X1FILE.zip
	zip $@ $^

SRC.zip	:	Makefile $(SRCDIR)/X1EMU.has $(SRCDIR)/X1IO.has $(SRCDIR)/Z80.has $(SRCDIR)/Z80DB.has $(SRCDIR)/Z80DIS.has \
			z80/TEST.Z8D z80/TEST.Z80
	zip $@ $^

