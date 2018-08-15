# The SONAME sets the api version compatibility.
# It is using the same SONAME from the pre-installed sqlite3 library so
# the library can be loaded by existing applications as python. For this
# we can set the LD_LIBRARY_PATH when opening the app or set the rpath
# in the executable.

LIBFLAGS = -Wall -I$(LMDBPATH) $(CFLAGS)
LDFLAGS  = $(LFLAGS) -L$(LMDBPATH) -llmdb

ifeq ($(OS),Windows_NT)
    IMPLIB   = litetree-0.1
    LIBRARY  = litetree-0.1.dll
    LMDBPATH = ../lmdb/libraries/liblmdb
    #LIBFLAGS += $(LMDBPATH)mdb.c $(LMDBPATH)midl.c
    LDFLAGS  += -static-libgcc -static-libstdc++
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        OS = OSX
        LIBRARY  = liblitetree.0.dylib
        LIBNICK1 = liblitetree.dylib
        LIBNICK2 = libsqlite3.0.dylib
        LIBNICK3 = libsqlite3.dylib
        INSTNAME = $(LIBPATH2)/libsqlite3.dylib
        CURR_VERSION   = 1.0.0
        COMPAT_VERSION = 1.0.0
    else
        LIBRARY  = liblitetree.so.0.0.1
        LIBNICK1 = liblitetree.so.0
        LIBNICK2 = liblitetree.so
        LIBNICK3 = libsqlite3.so.0
        LIBNICK4 = libsqlite3.so
        SONAME   = libsqlite3.so.0
    endif
    LMDBPATH = /usr/local/lib
    prefix  ?= /usr/local
    LIBPATH  = $(prefix)/lib
    LIBPATH2 = $(prefix)/lib/litetree
    INCPATH  = $(prefix)/include
    EXEPATH  = $(prefix)/bin
    LIBFLAGS += -fPIC
    LDFLAGS  += -lpthread
    SHELLFLAGS = -DHAVE_READLINE
endif

CC = gcc

SHORT = sqlite3

# the item below cannot be called SHELL because it's a reserved name
ifeq ($(OS),Windows_NT)
    SSHELL = sqlite3.exe
else
    SSHELL = sqlite3
endif

#LIBFLAGS = -Wall -DSQLITE_USE_URI=1 -DSQLITE_ENABLE_JSON1 -DSQLITE_THREADSAFE=1 -DHAVE_USLEEP -DSQLITE_ENABLE_COLUMN_METADATA
LIBFLAGS := $(LIBFLAGS) -DSQLITE_USE_URI=1 -DSQLITE_ENABLE_JSON1 -DSQLITE_THREADSAFE=1 -DHAVE_USLEEP -DSQLITE_ENABLE_COLUMN_METADATA


.PHONY:  install debug test clean


all:   $(LIBRARY) $(SSHELL)

debug: $(LIBRARY) $(SSHELL)

debug: export LIBFLAGS := -g -DSQLITE_DEBUG=1 -DDEBUGPRINT $(LIBFLAGS)

litetree-0.1.dll: $(SHORT).o
	$(CC) -shared -Wl,--out-implib,$(IMPLIB).lib $^ -o $@ $(LDFLAGS)
	strip $(LIBRARY)

liblitetree.0.dylib: $(SHORT).o
	$(CC) -dynamiclib -install_name "$(INSTNAME)" -current_version $(CURR_VERSION) -compatibility_version $(COMPAT_VERSION) $^ -o $@ $(LDFLAGS)
	#strip $(LIBRARY)
	install_name_tool -change liblmdb.so /usr/local/lib/liblmdb.so $@
	ln -sf $(LIBRARY) $(LIBNICK1)
	ln -sf $(LIBRARY) $(LIBNICK2)
	ln -sf $(LIBRARY) $(LIBNICK3)

liblitetree.so.0.0.1: $(SHORT).o
	$(CC) -shared -Wl,-soname,$(SONAME) -Wl,-rpath,$(LMDBPATH) $^ -o $@ $(LDFLAGS)
	strip $(LIBRARY)
	ln -sf $(LIBRARY) $(LIBNICK1)
	ln -sf $(LIBNICK1) $(LIBNICK2)
	ln -sf $(LIBRARY) $(LIBNICK3)
	ln -sf $(LIBNICK3) $(LIBNICK4)

$(SHORT).o: $(SHORT).c $(SHORT).h
	$(CC) $(LIBFLAGS) -c $< -o $@

$(SSHELL): shell.o $(LIBRARY)
ifeq ($(OS),Windows_NT)
	$(CC) $< -o $@ -L. -l$(IMPLIB)
else ifeq ($(OS),OSX)
	$(CC) $< -o $@ -L. -lsqlite3 -ldl -lreadline
else
	$(CC) $< -o $@ -Wl,-rpath,$(LIBPATH) -L. -lsqlite3 -ldl -lreadline
endif
	strip $(SSHELL)

shell.o: shell.c
	$(CC) -c $(SHELLFLAGS) $< -o $@

install:
	mkdir -p $(LIBPATH)
	mkdir -p $(LIBPATH2)
	cp $(LIBRARY) $(LIBPATH)/
	cd $(LIBPATH) && ln -sf $(LIBRARY) $(LIBNICK1)
ifeq ($(OS),OSX)
	cd $(LIBPATH2) && ln -sf ../$(LIBNICK1) $(LIBNICK2)
	cd $(LIBPATH2) && ln -sf $(LIBNICK2) $(LIBNICK3)
else
	cd $(LIBPATH) && ln -sf $(LIBNICK1) $(LIBNICK2)
	cd $(LIBPATH2) && ln -sf ../$(LIBRARY) $(LIBNICK3)
	cd $(LIBPATH2) && ln -sf $(LIBNICK3) $(LIBNICK4)
endif
	cp $(SHORT).h $(INCPATH)
	cp $(SSHELL) $(EXEPATH)

clean:
	rm -f *.o $(LIBRARY) $(LIBNICK1) $(LIBNICK2) $(LIBNICK3) $(LIBNICK4) $(SSHELL)

test: test/test.py
ifeq ($(OS),Windows_NT)
ifeq ($(PY_HOME),)
	@echo "PY_HOME is not set"
else
	cd $(PY_HOME)/DLLs && [ ! -f sqlite3-orig.dll ] && mv sqlite3.dll sqlite3-orig.dll || true
	cp litetree-0.1.dll $(PY_HOME)/DLLs/sqlite3.dll
	cp $(LMDBPATH)/lmdb.dll $(PY_HOME)/DLLs/lmdb.dll
	cd test && python test.py -v
endif
else ifeq ($(OS),OSX)
	cd test && python test.py -v
else
	cd test && LD_LIBRARY_PATH=.. python test.py -v
endif

# variables:
#   $@  output
#   $^  all the requirements
#   $<  first requirement
