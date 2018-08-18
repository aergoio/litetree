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

sqlite_version = "3.24.0"

if sqlite3.sqlite_version != sqlite_version:
    print "wrong SQLite version. expected: " + sqlite_version + " found: " + sqlite3.sqlite_version
    quit()

def delete_file(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)

delete_file("normal.db")
delete_file("branch.db")


conn1 = sqlite3.connect('file:normal.db')
conn2 = sqlite3.connect('file:branch.db?branches=on')


def write_normal():
    test_write(conn1)

def write_litetree():
    test_write(conn2)


def read_normal():
    test_read(conn1)

def read_litetree():
    test_read(conn2)



def test_write(conn):

    c = conn.cursor()

    c.execute("drop table if exists t1")
    conn.commit()

    c.execute("create table t1(name)")
    conn.commit()

    c.execute("insert into t1 values ('first')")
    conn.commit()
    c.execute("insert into t1 values ('second')")
    conn.commit()
    c.execute("insert into t1 values ('third')")
    conn.commit()
    
    for n in range(200):
        c.execute("insert into t1 values ('rec " + str(n) + "')")
        conn.commit()

    for n in range(1000):
        c.execute("insert into t1 values ('rec " + str(n + 200) + "')")
    conn.commit()

    for n in range(10):
        c.execute("drop table if exists t" + str(n))
        conn.commit()
        c.execute("create table t" + str(n) + " (name)")
        conn.commit()

    for t in range(10):
        for n in range(10):
            c.execute("insert into t" + str(t) + " values ('rec " + str(n) + "')")
            conn.commit()

    for t in range(10):
        for n in range(10):
            c.execute("update t" + str(t) + " set name = 'new value " + str(n) + "' where name = 'rec" + str(n) + "'")
            conn.commit()

    for t in range(10):
        for n in range(10):
            c.execute("update t" + str(t) + " set name = 'another new and bigger value " + str(n) + "' where rowid = " + str(n + 1))
            conn.commit()

    #for t in range(10):
    #    for n in range(10):
    #        c.execute("delete from t" + str(t) + " where name = 'new value " + str(n) + "'")
    #        conn.commit()


def test_read(conn):

    c = conn.cursor()

    for t in range(10):
        for n in range(10):
            c.execute("select * from t" + str(t) + " where name = 'another new and bigger value " + str(n) + "'")
            result = c.fetchall()
            assert result[0][0] == "another new and bigger value " + str(n)

    for t in range(10):
        c.execute("select * from t" + str(t))
        result = c.fetchall()

    c.execute("select name from sqlite_master")
    result = c.fetchall()
    for t in range(10):
        assert result[t][0] == "t" + str(t)



if __name__ == '__main__':
    import timeit

    normal   = timeit.timeit("write_normal()", setup="from __main__ import write_normal", number=1)
    litetree = timeit.timeit("write_litetree()", setup="from __main__ import write_litetree", number=1)

    print
    print("writing:")
    print("--------")
    print("normal   = " + str(normal) + " seconds")
    print("litetree = " + str(litetree) + " seconds")

    normal   = timeit.timeit("read_normal()", setup="from __main__ import read_normal", number=1)
    litetree = timeit.timeit("read_litetree()", setup="from __main__ import read_litetree", number=1)

    print
    print("reading:")
    print("--------")
    print("normal   = " + str(normal) + " seconds")
    print("litetree = " + str(litetree) + " seconds")

    print

    conn1.close()
    conn2.close()
