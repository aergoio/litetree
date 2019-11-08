#
# Copyright defined in LICENSE.txt
#
import json
import os
import platform

if platform.system() == "Darwin":
    import pysqlite2.dbapi2 as sqlite3
else:
    import sqlite3

sqlite_version = "3.27.2"

if sqlite3.sqlite_version != sqlite_version:
    print "wrong SQLite version. expected: " + sqlite_version + " found: " + sqlite3.sqlite_version
    quit()

def delete_file(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)

def delete_files(filepath):
    delete_file(filepath)
    delete_file(filepath + "-journal")
    delete_file(filepath + "-wal")
    delete_file(filepath + "-shm")
    delete_file(filepath + "-lock")

delete_files("normal.db")
delete_files("wal.db")
delete_files("mmap.db")
delete_files("branch.db")

conn1 = sqlite3.connect('file:normal.db', isolation_level=None)
conn2 = sqlite3.connect('file:wal.db', isolation_level=None)
conn3 = sqlite3.connect('file:mmap.db', isolation_level=None)
conn4 = sqlite3.connect('file:branch.db?branches=on', isolation_level=None)

c = conn2.cursor()
c.execute("pragma journal_mode=wal")
c.close()

c = conn3.cursor()
c.execute("pragma mmap_size=" + str(64 * 1024 * 1024))
c.execute("pragma journal_mode=wal")
c.close()


def write_normal():
    test_write(conn1)

def write_wal():
    test_write(conn2)

def write_mmap():
    test_write(conn3)

def write_litetree():
    test_write(conn4)


def read_normal():
    test_read(conn1)

def read_wal():
    test_read(conn2)

def read_mmap():
    test_read(conn3)

def read_litetree():
    test_read(conn4)



def test_write(conn):

    c = conn.cursor()

    c.execute("drop table if exists t1")

    c.execute("create table t0(name)")
    c.execute("create table t1(name)")

    for n in range(100):
        c.execute("insert into t1 values ('record " + str(n) + "')")

    c.execute("begin")
    for n in range(100):
        c.execute("insert into t1 values ('record " + str(n + 100) + "')")
    conn.commit()

    c.execute("begin")
    for n in range(1000):
        #c.execute("drop table if exists t" + str(n))
        c.execute("create table if not exists t" + str(n) + " (name)")
    conn.commit()

    for n in range(10):
        c.execute("begin")
        for t in range(1000):
            c.execute("insert into t" + str(t) + " values ('rec " + str(n) + "')")
        conn.commit()

    for n in range(10):
        c.execute("begin")
        for t in range(1000):
            c.execute("update t" + str(t) + " set name = 'new value " + str(n) + "' where name = 'rec" + str(n) + "'")
        conn.commit()

    for n in range(10):
        c.execute("begin")
        for t in range(1000):
            c.execute("update t" + str(t) + " set name = 'another new and bigger value " + str(n) + "' where rowid = " + str(n + 1))
        conn.commit()

    #for t in range(10):
    #    for n in range(10):
    #        c.execute("delete from t" + str(t) + " where name = 'new value " + str(n) + "'")

    c.close()


def test_read(conn):

    c = conn.cursor()

    for n in range(10):
        for t in range(1000):
            c.execute("select * from t" + str(t) + " where name = 'another new and bigger value " + str(n) + "'")
            result = c.fetchall()
            assert result[0][0] == "another new and bigger value " + str(n)

    for n in range(10):
        for t in range(1000):
            c.execute("select * from t" + str(t) + " where name = 'non existing value " + str(n) + "'")
            result = c.fetchall()
            assert len(result) == 0

    for t in range(1000):
        c.execute("select * from t" + str(t))
        result = c.fetchall()

    c.execute("select name from sqlite_master")
    result = c.fetchall()
    for t in range(1000):
        assert result[t][0] == "t" + str(t)

    c.close()



if __name__ == '__main__':
    import timeit

    normal   = timeit.timeit("write_normal()", setup="from __main__ import write_normal", number=1)
    wal      = timeit.timeit("write_wal()", setup="from __main__ import write_wal", number=1)
    mmap     = timeit.timeit("write_mmap()", setup="from __main__ import write_mmap", number=1)
    litetree = timeit.timeit("write_litetree()", setup="from __main__ import write_litetree", number=1)

    print
    print("writing:")
    print("--------")
    print("normal   = " + str(normal) + " seconds")
    print("wal      = " + str(wal) + " seconds")
    print("mmap     = " + str(mmap) + " seconds")
    print("litetree = " + str(litetree) + " seconds")

    normal   = timeit.timeit("read_normal()", setup="from __main__ import read_normal", number=1)
    wal      = timeit.timeit("read_wal()", setup="from __main__ import read_wal", number=1)
    mmap     = timeit.timeit("read_mmap()", setup="from __main__ import read_mmap", number=1)
    litetree = timeit.timeit("read_litetree()", setup="from __main__ import read_litetree", number=1)

    print
    print("reading:")
    print("--------")
    print("normal   = " + str(normal) + " seconds")
    print("wal      = " + str(wal) + " seconds")
    print("mmap     = " + str(mmap) + " seconds")
    print("litetree = " + str(litetree) + " seconds")

    print

    conn1.close()
    conn2.close()
    conn3.close()
    conn4.close()
