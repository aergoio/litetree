#
# Copyright defined in LICENSE.txt
#
import unittest
import json
import os
import platform
import shutil

if platform.system() == "Darwin":
    import pysqlite2.dbapi2 as sqlite3
else:
    import sqlite3

sqlite_version = "3.24.0"

if sqlite3.sqlite_version != sqlite_version:
    print "wrong SQLite version. expected: " + sqlite_version + " found: " + sqlite3.sqlite_version
    import sys
    sys.exit(1)

def delete_file(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)


class TestSQLiteBranches(unittest.TestCase):

    def test01_branches(self):
        delete_file("test.db")
        conn = sqlite3.connect('file:test.db?branches=on')
        c = conn.cursor()

        c.execute("pragma page_size")
        self.assertEqual(c.fetchone()[0], 4096)

        c.execute("pragma journal_mode")
        self.assertEqual(c.fetchone()[0], "branches")

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",)])

        c.execute("create table t1(name)")
        conn.commit()
        c.execute("insert into t1 values ('first')")
        conn.commit()
        c.execute("insert into t1 values ('second')")
        conn.commit()

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",)])

        c.execute("pragma new_branch=test at master.2")

        # it should deny the creation of another branch with the same name
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=test at master.2")

        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",),("test",)])
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "test")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",)])

        c.execute("insert into t1 values ('from test branch')")
        conn.commit()
        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("from test branch",)])

        c.execute("pragma branch=master")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",)])

        c.execute("insert into t1 values ('third')")
        conn.commit()

        c.execute("insert into t1 values ('fourth')")
        c.execute("insert into t1 values ('fifth')")
        c.execute("insert into t1 values ('sixth')")
        conn.commit()

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])

        c.execute("pragma branch=test")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "test")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("from test branch",)])

        c.execute("pragma new_branch=sub-test1 at test.2")
        c.execute("pragma new_branch=sub-test2 at test.3")
        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",)])
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "sub-test2")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("from test branch",)])

        c.execute("insert into t1 values ('from sub-test2 branch')")
        conn.commit()

        c.execute("pragma branch=sub-test1")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "sub-test1")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",)])

        c.execute("pragma branch=sub-test2")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "sub-test2")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("from test branch",),("from sub-test2 branch",)])

        c.execute("pragma branch=test")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "test")

        values = [("val1",),(2,),(3.3,)]
        c.executemany("INSERT INTO t1 VALUES (?)", values)
        conn.commit()

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("from test branch",),("val1",),(2,),(3.3,)])

        conn.close()


    def test02_branch_info(self):
        conn = sqlite3.connect('file:test.db?branches=on')
        c = conn.cursor()

        c.execute("pragma journal_mode")
        self.assertEqual(c.fetchone()[0], "branches")

        c.execute("pragma branch_info(master)")
        obj = json.loads(c.fetchone()[0])
        self.assertEqual(obj["total_commits"], 5)

        c.execute("pragma branch_info(test)")
        obj = json.loads(c.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 2)
        self.assertEqual(obj["total_commits"], 4)

        c.execute("pragma branch_info('sub-test1')")
        obj = json.loads(c.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 2)
        self.assertEqual(obj["total_commits"], 2)

        c.execute("pragma branch_info('sub-test2')")
        obj = json.loads(c.fetchone()[0])
        self.assertEqual(obj["source_branch"], "test")
        self.assertEqual(obj["source_commit"], 3)
        self.assertEqual(obj["total_commits"], 4)

        conn.close()


    def test03_sql_log(self):
        conn = sqlite3.connect('file:test.db?branches=on')
        c = conn.cursor()

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("pragma branch_log")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('fifth')",),
            ("master",5,"insert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('fifth')",),
            ("master",5,"insert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"21:create table t1(name),",),
            ("master",2,"31:insert into t1 values ('first'),",),
            ("master",3,"32:insert into t1 values ('second'),",),
            ("master",4,"31:insert into t1 values ('third'),",),
            ("master",5,"32:insert into t1 values ('fourth'),31:insert into t1 values ('fifth'),31:insert into t1 values ('sixth'),",)
        ])

        c.execute("pragma branch_log master --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"21:create table t1(name),",),
            ("master",2,"31:insert into t1 values ('first'),",),
            ("master",3,"32:insert into t1 values ('second'),",),
            ("master",4,"31:insert into t1 values ('third'),",),
            ("master",5,"32:insert into t1 values ('fourth'),31:insert into t1 values ('fifth'),31:insert into t1 values ('sixth'),",)
        ])

        c.execute("pragma branch_log --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth');insert into t1 values ('fifth');insert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log master --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth');insert into t1 values ('fifth');insert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log --delimited[||]")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')||insert into t1 values ('fifth')||insert into t1 values ('sixth')",)
        ])


        c.execute("pragma branch_log master.1-5")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('fifth')",),
            ("master",5,"insert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log master.2-4")
        self.assertListEqual(c.fetchall(), [
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
        ])

        c.execute("pragma branch_log master.1")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
        ])

        c.execute("pragma branch_log master.3")
        self.assertListEqual(c.fetchall(), [
            ("master",3,"insert into t1 values ('second')",),
        ])

        c.execute("pragma branch_log master.5")
        self.assertListEqual(c.fetchall(), [
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('fifth')",),
            ("master",5,"insert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log master.2-5 --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",2,"31:insert into t1 values ('first'),",),
            ("master",3,"32:insert into t1 values ('second'),",),
            ("master",4,"31:insert into t1 values ('third'),",),
            ("master",5,"32:insert into t1 values ('fourth'),31:insert into t1 values ('fifth'),31:insert into t1 values ('sixth'),",)
        ])

        c.execute("pragma branch_log master.2-4 --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",2,"31:insert into t1 values ('first'),",),
            ("master",3,"32:insert into t1 values ('second'),",),
            ("master",4,"31:insert into t1 values ('third'),",),
        ])

        c.execute("pragma branch_log master.3 --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",3,"32:insert into t1 values ('second'),",),
        ])

        c.execute("pragma branch_log master.5 --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",5,"32:insert into t1 values ('fourth'),31:insert into t1 values ('fifth'),31:insert into t1 values ('sixth'),",)
        ])

        c.execute("pragma branch_log master.2-5 --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth');insert into t1 values ('fifth');insert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log master.3-4 --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
        ])

        c.execute("pragma branch_log master.3 --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",3,"insert into t1 values ('second')",),
        ])

        c.execute("pragma branch_log master.5 --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",5,"insert into t1 values ('fourth');insert into t1 values ('fifth');insert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log master.5 --delimited[\\x0D\\x0A---\\x0d\\x0a]")
        self.assertListEqual(c.fetchall(), [
            ("master",5,"insert into t1 values ('fourth')\x0D\x0A---\x0D\x0Ainsert into t1 values ('fifth')\x0D\x0A---\x0D\x0Ainsert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log master.5 --delimited[\\n---\\n]")
        self.assertListEqual(c.fetchall(), [
            ("master",5,"insert into t1 values ('fourth')\n---\ninsert into t1 values ('fifth')\n---\ninsert into t1 values ('sixth')",)
        ])

        c.execute("pragma branch_log master.5 --delimited[\\t]")
        self.assertListEqual(c.fetchall(), [
            ("master",5,"insert into t1 values ('fourth')\tinsert into t1 values ('fifth')\tinsert into t1 values ('sixth')",)
        ])


        c.execute("pragma branch_log test")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1')",),
            ("test",4,"INSERT INTO t1 VALUES (2)",),
            ("test",4,"INSERT INTO t1 VALUES (3.3)",),
        ])

        c.execute("pragma branch_log test --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1');INSERT INTO t1 VALUES (2);INSERT INTO t1 VALUES (3.3)",),
        ])

        c.execute("pragma branch_log test --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"21:create table t1(name),",),
            ("master",2,"31:insert into t1 values ('first'),",),
            ("test",3,"42:insert into t1 values ('from test branch'),",),
            ("test",4,"30:INSERT INTO t1 VALUES ('val1'),25:INSERT INTO t1 VALUES (2),27:INSERT INTO t1 VALUES (3.3),",),
        ])

        c.execute("pragma branch_log test.*-2")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",)
        ])

        c.execute("pragma branch_log test.2-*")
        self.assertListEqual(c.fetchall(), [
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1')",),
            ("test",4,"INSERT INTO t1 VALUES (2)",),
            ("test",4,"INSERT INTO t1 VALUES (3.3)",),
        ])


        c.execute("pragma branch_log sub-test2")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("sub-test2",4,"insert into t1 values ('from sub-test2 branch')",)
        ])

        c.execute("pragma branch_log sub-test2 --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("sub-test2",4,"insert into t1 values ('from sub-test2 branch')",)
        ])

        c.execute("pragma branch_log sub-test2 --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"21:create table t1(name),",),
            ("master",2,"31:insert into t1 values ('first'),",),
            ("test",3,"42:insert into t1 values ('from test branch'),",),
            ("sub-test2",4,"47:insert into t1 values ('from sub-test2 branch'),",)
        ])


        # test --strict

        #c.execute("pragma branch_log test --strict")
        c.execute("pragma branch_log --strict test")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1')",),
            ("test",4,"INSERT INTO t1 VALUES (2)",),
            ("test",4,"INSERT INTO t1 VALUES (3.3)",),
        ])

        c.execute("pragma branch_log --strict test --delimited")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1');INSERT INTO t1 VALUES (2);INSERT INTO t1 VALUES (3.3)",),
        ])

        c.execute("pragma branch_log --strict test --netstring")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"42:insert into t1 values ('from test branch'),",),
            ("test",4,"30:INSERT INTO t1 VALUES ('val1'),25:INSERT INTO t1 VALUES (2),27:INSERT INTO t1 VALUES (3.3),",),
        ])


        # test on a sub-branch

        c.execute("pragma branch=test")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "test")

        c.execute("pragma branch_log")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1')",),
            ("test",4,"INSERT INTO t1 VALUES (2)",),
            ("test",4,"INSERT INTO t1 VALUES (3.3)",),
        ])

        c.execute("pragma branch_log --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1');INSERT INTO t1 VALUES (2);INSERT INTO t1 VALUES (3.3)",),
        ])

        c.execute("pragma branch_log --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"21:create table t1(name),",),
            ("master",2,"31:insert into t1 values ('first'),",),
            ("test",3,"42:insert into t1 values ('from test branch'),",),
            ("test",4,"30:INSERT INTO t1 VALUES ('val1'),25:INSERT INTO t1 VALUES (2),27:INSERT INTO t1 VALUES (3.3),",),
        ])

        # test --strict on a sub-branch

        c.execute("pragma branch_log --strict")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1')",),
            ("test",4,"INSERT INTO t1 VALUES (2)",),
            ("test",4,"INSERT INTO t1 VALUES (3.3)",),
        ])

        c.execute("pragma branch_log --strict --delimited")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"insert into t1 values ('from test branch')",),
            ("test",4,"INSERT INTO t1 VALUES ('val1');INSERT INTO t1 VALUES (2);INSERT INTO t1 VALUES (3.3)",),
        ])

        c.execute("pragma branch_log --strict --netstring")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"42:insert into t1 values ('from test branch'),",),
            ("test",4,"30:INSERT INTO t1 VALUES ('val1'),25:INSERT INTO t1 VALUES (2),27:INSERT INTO t1 VALUES (3.3),",),
        ])



        c.execute("pragma branch=test.3")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "test.3")

        c.execute("pragma branch_log")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
        ])

        c.execute("pragma branch_log --strict")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"insert into t1 values ('from test branch')",)
        ])

        c.execute("pragma branch_log --strict --delimited")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"insert into t1 values ('from test branch')",)
        ])

        c.execute("pragma branch_log --strict --netstring")
        self.assertListEqual(c.fetchall(), [
            ("test",3,"42:insert into t1 values ('from test branch'),",)
        ])


        # test on another sub-branch

        c.execute("pragma branch=sub-test2")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "sub-test2")

        c.execute("pragma branch_log")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("sub-test2",4,"insert into t1 values ('from sub-test2 branch')",)
        ])

        c.execute("pragma branch_log --delimited")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("test",3,"insert into t1 values ('from test branch')",),
            ("sub-test2",4,"insert into t1 values ('from sub-test2 branch')",)
        ])

        c.execute("pragma branch_log --netstring")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"21:create table t1(name),",),
            ("master",2,"31:insert into t1 values ('first'),",),
            ("test",3,"42:insert into t1 values ('from test branch'),",),
            ("sub-test2",4,"47:insert into t1 values ('from sub-test2 branch'),",)
        ])

        # test --strict on a sub-branch

        c.execute("pragma branch_log --strict")
        self.assertListEqual(c.fetchall(), [
            ("sub-test2",4,"insert into t1 values ('from sub-test2 branch')",)
        ])

        c.execute("pragma branch_log --strict --delimited")
        self.assertListEqual(c.fetchall(), [
            ("sub-test2",4,"insert into t1 values ('from sub-test2 branch')",)
        ])

        c.execute("pragma branch_log --strict --netstring")
        self.assertListEqual(c.fetchall(), [
            ("sub-test2",4,"47:insert into t1 values ('from sub-test2 branch'),",)
        ])


        # sql logs up to the current commit

        c.execute("pragma branch=master.3")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.3")

        c.execute("pragma branch_log")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
        ])

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('fifth')",),
            ("master",5,"insert into t1 values ('sixth')",)
        ])


        # invalid commands

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma branch_log --srtict test --netstring")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma branch_log --strict teest --netstring")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma branch_log teest --netstring")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma branch_log teest")


        conn.close()


    def test04_edit_commits(self):
        shutil.copy("test.db","test2.db")
        conn = sqlite3.connect('file:test2.db?branches=on')
        c = conn.cursor()

        c.execute("pragma branch_log --add master.5 insert into t1 values ('seventh')")

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('fifth')",),
            ("master",5,"insert into t1 values ('sixth')",),
            ("master",5,"insert into t1 values ('seventh')",)
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",),("seventh",)])


        c.execute("pragma branch_log --del master.5 2,3")

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('seventh')",)
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",),("third",),("fourth",),("seventh",)])


        c.execute("pragma branch_log --add master.5 update t1 set name = name || '-';insert into t1 values ('new')")

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('seventh')",),
            ("master",5,"update t1 set name = name || '-'",),
            ("master",5,"insert into t1 values ('new')",)
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first-",),("second-",),("third-",),("fourth-",),("seventh-",),("new",)])


        c.execute("insert into t1 values ('eighth')")
        conn.commit()

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('seventh')",),
            ("master",5,"update t1 set name = name || '-'",),
            ("master",5,"insert into t1 values ('new')",),
            ("master",6,"insert into t1 values ('eighth')",),
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first-",),("second-",),("third-",),("fourth-",),("seventh-",),("new",),("eighth",)])


        c.execute("pragma branch_log --del master.5 3")

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('seventh')",),
            ("master",5,"insert into t1 values ('new')",),
            ("master",6,"insert into t1 values ('eighth')",),
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",),("third",),("fourth",),("seventh",),("new",),("eighth",)])


        c.execute("pragma branch_log --set master.5 delete from t1;insert into t1 values ('newest')")

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"delete from t1",),
            ("master",5,"insert into t1 values ('newest')",),
            ("master",6,"insert into t1 values ('eighth')",),
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("newest",),("eighth",)])


        # the commit 2 is parent of other branches
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma branch_log --set master.2 29:insert into t1 values ('1st'), master.3 29:insert into t1 values ('2nd'),")


        c.execute("pragma branch_log --set master.3 29:insert into t1 values ('2nd'), master.4 29:insert into t1 values ('3rd'),29:insert into t1 values ('4th'),")

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('2nd')",),
            ("master",4,"insert into t1 values ('3rd')",),
            ("master",4,"insert into t1 values ('4th')",),
            ("master",5,"delete from t1",),
            ("master",5,"insert into t1 values ('newest')",),
            ("master",6,"insert into t1 values ('eighth')",),
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("newest",),("eighth",)])


        c.execute("pragma branch_log --del master.5 1")

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('2nd')",),
            ("master",4,"insert into t1 values ('3rd')",),
            ("master",4,"insert into t1 values ('4th')",),
            ("master",5,"insert into t1 values ('newest')",),
            ("master",6,"insert into t1 values ('eighth')",),
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("2nd",),("3rd",),("4th",),("newest",),("eighth",)])


        conn.close()
        conn = sqlite3.connect('file:test2.db?branches=on')
        c = conn.cursor()


        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('2nd')",),
            ("master",4,"insert into t1 values ('3rd')",),
            ("master",4,"insert into t1 values ('4th')",),
            ("master",5,"insert into t1 values ('newest')",),
            ("master",6,"insert into t1 values ('eighth')",),
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("2nd",),("3rd",),("4th",),("newest",),("eighth",)])


        # test commits in any order
        c.execute("pragma branch_log --set master.6 30:insert into t1 values ('last'), master.4 32:insert into t1 values ('before'),33:insert into t1 values ('another'), master.3 31:insert into t1 values ('after'),31:insert into t1 values ('third'),")

        c.execute("pragma branch_log master")
        self.assertListEqual(c.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('after')",),
            ("master",3,"insert into t1 values ('third')",),
            ("master",4,"insert into t1 values ('before')",),
            ("master",4,"insert into t1 values ('another')",),
            ("master",5,"insert into t1 values ('newest')",),
            ("master",6,"insert into t1 values ('last')",),
        ])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("after",),("third",),("before",),("another",),("newest",),("last",)])


        conn.close()


    def test05_reading_branches_at_the_same_time(self):
        conn1 = sqlite3.connect('file:test.db?branches=on')
        conn2 = sqlite3.connect('file:test.db?branches=on')
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("pragma journal_mode")
        c2.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "branches")
        self.assertEqual(c2.fetchone()[0], "branches")

        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",)])
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",)])

        c2.execute("pragma branch=sub-test2")
        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "sub-test2")

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])
        self.assertListEqual(c2.fetchall(), [("first",),("from test branch",),("from sub-test2 branch",)])

        c1.execute("pragma branch=master.3")
        c2.execute("pragma branch=master.4")
        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master.3")
        self.assertEqual(c2.fetchone()[0], "master.4")

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",)])

        c1.execute("pragma branch=master.5")
        c2.execute("pragma branch=test")
        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master.5")
        self.assertEqual(c2.fetchone()[0], "test")

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])
        self.assertListEqual(c2.fetchall(), [("first",),("from test branch",),("val1",),(2,),(3.3,)])

        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",)])
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",)])

        conn1.close()
        conn2.close()


    def test06_concurrent_access(self):
        delete_file("test2.db")
        conn1 = sqlite3.connect('file:test2.db?branches=on')
        conn2 = sqlite3.connect('file:test2.db?branches=on')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("pragma journal_mode")
        c2.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "branches")
        self.assertEqual(c2.fetchone()[0], "branches")

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "master")

        # make modifications on connection 1
        c1.execute("create table t1(name)")
        conn1.commit()
        c1.execute("insert into t1 values ('first')")
        conn1.commit()

        # the new modifications should appear on connection 2
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",)])

        # make modifications on connection 1
        c1.execute("insert into t1 values ('second')")
        conn1.commit()

        # the new modifications should appear on connection 2
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",)])

        c2.execute("pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",)])

        # create a new table on connection 1
        c1.execute("create table t2(name)")
        conn1.commit()

        # the new table should appear on connection 2
        c2.execute("select name from sqlite_master")
        self.assertListEqual(c2.fetchall(), [("t1",),("t2",)])

        # create a new branch on connection 1
        c1.execute("pragma new_branch=b2 at master")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "b2")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("b2",)])

        # the new branch should appear on connection 2
        c2.execute("Pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("b2",)])

        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('file:test2.db?branches=on')
        conn2 = sqlite3.connect('file:test2.db?branches=on')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        # create a new branch on connection 1
        c1.execute("pragma new_branch=b3 at master.2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "b3")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("b2",),("b3",)])

        # the new branch should appear on connection 2
        c2.execute("pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("b2",),("b3",)])

        conn1.close()
        conn2.close()


    def test07_single_connection_uri(self):
        conn1 = sqlite3.connect('file:test2.db?branches=on&single_connection=true')
        conn2 = sqlite3.connect('file:test2.db?branches=on&single_connection=true')
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("pragma journal_mode")
        c2.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "branches")
        self.assertEqual(c2.fetchone()[0], "branches")

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "master")

        # make modifications on connection 1
        c1.execute("create table t3(name)")
        conn1.commit()
        c1.execute("insert into t1 values ('third')")
        conn1.commit()

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",)])

        # the new modifications should NOT appear on connection 2
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",)])
        c2.execute("select name from sqlite_master")
        self.assertListEqual(c2.fetchall(), [("t1",),("t2",)])

        # create a new branch on connection 1
        c1.execute("pragma new_branch=b4 at master.2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "b4")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("b2",),("b3",),("b4",)])

        # the new branch should NOT appear on connection 2
        c2.execute("pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("b2",),("b3",)])

        conn1.close()
        conn2.close()


    def test08_invalid_branch_name(self):
        conn = sqlite3.connect('file:test2.db?branches=on')
        c = conn.cursor()

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")
        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",),("b2",),("b3",),("b4",)])

        # try to create a branch in which its name contains a dot
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=another.branch at master.2")

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")
        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",),("b2",),("b3",),("b4",)])

        conn.close()


    def test09_rename_branch(self):
        conn1 = sqlite3.connect('file:test.db?branches=on')
        conn2 = sqlite3.connect('file:test.db?branches=on')
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",)])
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",)])

        # try to rename an unexistent branch
        with self.assertRaises(sqlite3.OperationalError):
            c2.execute("pragma rename_branch test33 must-fail")

        # create a new branch on connection 1
        c1.execute("pragma new_branch=test2 at master.3")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test2")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("test2",)])

        c1.execute("pragma branch=test")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test")

        # try to rename it on connection 2
        c2.execute("pragma rename_branch test2 new-branch")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "master")
        c2.execute("pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("new-branch",)])

        # check the current branch name on connection 1
#        c1.execute("pragma branch")
#        self.assertEqual(c1.fetchone()[0], "new-branch")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("new-branch",)])

        c1.execute("pragma branch=new-branch")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "new-branch")

        # insert a new value on connection 1
        c1.execute("insert into t1 values ('from the new renamed branch')")
        conn1.commit()
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("from the new renamed branch",)])

        # check the value on connection 2
        c2.execute("pragma branch=new-branch")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "new-branch")
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("from the new renamed branch",)])

        # close and reopen the connections
        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('file:test.db?branches=on')
        conn2 = sqlite3.connect('file:test.db?branches=on&single_connection=true')
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        # the new name should be there
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("new-branch",)])
        c2.execute("pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("new-branch",)])

        # rename branch in one conn and try to move to the previous/old name on another conn (should work if single_conn=true)
        c1.execute("pragma new_branch=test2 at master.3")
        conn1.commit()
        c1.execute("pragma rename_branch new-branch renamed-branch")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test2")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])

        # try to move to the previous/old name on connection 2 (should work if single_connection=true)
        c2.execute("pragma branch=new-branch")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "new-branch")
        c2.execute("pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("new-branch",)])
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("from the new renamed branch",)])

        c1.execute("pragma branch=renamed-branch")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "renamed-branch")

        conn1.close()
        conn2.close()


    def test10_truncate_branch(self):
        # test: truncate in one conn a branch that is in use in another conn, then try to access it in this second conn
        # test: truncate in one conn a branch that is NOT in use in another conn, then try to access it in this second conn

        shutil.copy("test.db","test3.db")

        conn1 = sqlite3.connect('file:test.db?branches=on')
        conn2 = sqlite3.connect('file:test.db?branches=on')
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "master")

        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertGreater(obj["total_commits"], 4)

        # try to truncate to a not allowed point
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_truncate(master.2)")

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])

        c1.execute("pragma branch_log master")
        c2.execute("pragma branch_log master")
        self.assertListEqual(c1.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('fifth')",),
            ("master",5,"insert into t1 values ('sixth')",)
        ])
        self.assertListEqual(c2.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
            ("master",5,"insert into t1 values ('fourth')",),
            ("master",5,"insert into t1 values ('fifth')",),
            ("master",5,"insert into t1 values ('sixth')",)
        ])

        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertGreater(obj["total_commits"], 4)

        # try to truncate to an allowed point
        c1.execute("pragma branch_truncate(master.4)")

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",)])

        c1.execute("pragma branch_log master")
        c2.execute("pragma branch_log master")
        self.assertListEqual(c1.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
        ])
        self.assertListEqual(c2.fetchall(), [
            ("master",1,"create table t1(name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",4,"insert into t1 values ('third')",),
        ])

        # try to move to a deleted point
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch=master.5")

        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")

        c1.execute("pragma branch=master.3")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master.3")
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",)])

        c1.execute("pragma branch=master.2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master.2")
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",)])

        c1.execute("pragma branch=test")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test")
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("from test branch",),("val1",),(2,),(3.3,)])

        # close and reopen the connections
        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('file:test.db?branches=on')
        conn2 = sqlite3.connect('file:test.db?branches=on&single_connection=true')
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        # the new name should be there
        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",)])

        conn1.close()
        conn2.close()


    def test11_delete_branch(self):
        # test: delete a branch and then try to access its children branches (should work)
        # test: delete in one conn then try to access it in another conn (should fail)
        # test: delete in one conn a branch that is in use in another conn (should delete. the current branch on the other conn should be invalid)
        # test with invalid current branch (or no current branch): query (select), modification (insert), 
        conn1 = sqlite3.connect('file:test3.db?branches=on')
        conn2 = sqlite3.connect('file:test3.db?branches=on')
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "master")

        # try to delete the branch that is the current one (should fail)
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma del_branch(master)")

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "master")

        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])

        c1.execute("pragma branch=sub-test1")
        c2.execute("pragma branch=sub-test1")
        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "sub-test1")
        self.assertEqual(c2.fetchone()[0], "sub-test1")

        c1.execute("pragma del_branch(master)")

        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])
        self.assertListEqual(c2.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "sub-test1")
        self.assertEqual(c2.fetchone()[0], "sub-test1")

        # delete a branch that is currently in use in another db connection

        c2.execute("pragma branch=test2")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "test2")

        c1.execute("pragma del_branch(test2)")

        c1.execute("prAGma branches")
        self.assertListEqual(c1.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",)])

        with self.assertRaises(sqlite3.OperationalError):
            c2.execute("pragma branches")

        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "sub-test1")

        with self.assertRaises(sqlite3.OperationalError):
            c2.execute("pragma branch")


        '''

        # try to move to the deleted branch
        c1.execute("pragma branch=master")
        c2.execute("pragma branch=master")
        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test")
        self.assertEqual(c2.fetchone()[0], "")



        c1.execute("pragma branch=sub-test1")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "sub-test1")

        '''

        c1.execute("pragma branch=test")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("from test branch",),("val1",),(2,),(3.3,)])

        #with self.assertRaises(sqlite3.OperationalError):
        #    c2.execute("select * from t1")


        # close and reopen the connections
        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('file:test3.db?branches=on')
        conn2 = sqlite3.connect('file:test3.db?branches=on&single_connection=true')
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",)])
        self.assertListEqual(c2.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",)])

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test")
        self.assertEqual(c2.fetchone()[0], "test")

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("from test branch",),("val1",),(2,),(3.3,)])
        self.assertListEqual(c2.fetchall(), [("first",),("from test branch",),("val1",),(2,),(3.3,)])

        conn1.close()
        conn2.close()


    def test12_rollback(self):
        conn = sqlite3.connect('file:test.db?branches=on')
        conn.isolation_level = None  # enables autocommit mode
        c = conn.cursor()

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("begin")
        c.execute("insert into t1 values ('another')")
        c.execute("create table t2(name)")
        c.execute("insert into t2 values ('first')")
        c.execute("insert into t2 values ('second')")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",),("third",),("another",)])

        c.execute("select * from t2")
        self.assertListEqual(c.fetchall(), [("first",),("second",)])

        conn.rollback()

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("select * from t2")

        c.execute("select name from sqlite_master")
        self.assertListEqual(c.fetchall(), [("t1",)])

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",),("third",)])

        conn.close()


    def test13_attached_dbs(self):
        delete_file("test4.db")
        delete_file("attached.db")

        connat = sqlite3.connect('attached.db')
        ca = connat.cursor()

        ca.execute("pragma page_size")
        self.assertEqual(ca.fetchone()[0], 4096)

        ca.execute("pragma journal_mode")
        self.assertEqual(ca.fetchone()[0], "delete")

        ca.execute("create table t2(name)")
        ca.execute("insert into t2 values ('att1')")
        ca.execute("insert into t2 values ('att2')")
        connat.commit()

        ca.execute("select * from t2")
        self.assertListEqual(ca.fetchall(), [("att1",),("att2",)])

        ca.execute("attach database 'test1.db' as temp1")
        ca.execute("detach database temp1")

        # test db with branches with attached db
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        conn2 = sqlite3.connect('file:test4.db?branches=on')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("pragma journal_mode")
        c2.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "branches")
        self.assertEqual(c2.fetchone()[0], "branches")

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "master")

        # make modifications on connection 1
        c1.execute("create table t1(name)")
        conn1.commit()
        c1.execute("insert into t1 values ('first')")
        conn1.commit()

        c1.execute("attach database 'attached.db' as sec")

        # the new modifications should appear on connection 2
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",)])

        # the attached db and its tables should not appear on conn2
        with self.assertRaises(sqlite3.OperationalError):
            c2.execute("select * from t2")
        with self.assertRaises(sqlite3.OperationalError):
            c2.execute("select * from sec.t2")

        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",)])
        c1.execute("select * from sec.t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",)])

        c1.execute("pragma sec.journal_mode")
        self.assertEqual(c1.fetchone()[0], "delete")
        c1.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "branches")

        # create a new branch on connection 1
        c1.execute("pragma new_branch=dev at master.2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "dev")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("dev",)])

        c1.execute("insert into t1 values ('second')")
        conn1.commit()

        ca.execute("insert into t2 values ('att3')")
        connat.commit()

        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",),("att3",)])
        c1.execute("select * from sec.t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",),("att3",)])
        ca.execute("select * from t2")
        self.assertListEqual(ca.fetchall(), [("att1",),("att2",),("att3",)])

        c1.execute("insert into t2 values ('att4')")
        conn1.commit()

        ca.execute("select * from t2")
        self.assertListEqual(ca.fetchall(), [("att1",),("att2",),("att3",),("att4",)])
        c1.execute("select * from sec.t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",),("att3",),("att4",)])

        # on 32bit Windows we cannot open 3 litetree dbs at the same time ...
        if platform.system() == "Windows" and platform.architecture()[0] == "32bit":
            conn2.close()
            # ... unless we use the max_db_size URI parameter when opening them, like this:
            #ca.execute("attach database 'file:test4.db?branches=on&max_db_size=134217728' as ext")

        ca.execute("attach database 'file:test4.db?branches=on' as ext")

        ca.execute("select * from t1")
        self.assertListEqual(ca.fetchall(), [("first",)])
        ca.execute("select * from ext.t1")
        self.assertListEqual(ca.fetchall(), [("first",)])

        ca.execute("pragma branches")
        self.assertListEqual(ca.fetchall(), [])
        ca.execute("pragma ext.branches")
        self.assertListEqual(ca.fetchall(), [("master",),("dev",)])

        ca.execute("pragma branch")
        self.assertListEqual(ca.fetchall(), [])
        ca.execute("pragma ext.branch")
        self.assertEqual(ca.fetchone()[0], "master")

        ca.execute("pragma ext.branch=dev")
        ca.execute("pragma ext.branch")
        self.assertEqual(ca.fetchone()[0], "dev")

        ca.execute("select * from t1")
        self.assertListEqual(ca.fetchall(), [("first",),("second",)])
        ca.execute("select * from ext.t1")
        self.assertListEqual(ca.fetchall(), [("first",),("second",)])

        ca.execute("insert into t1 values ('3rd')")
        connat.commit()
        ca.execute("insert into ext.t1 values ('4th')")
        connat.commit()

        ca.execute("pragma ext.branch=master")
        ca.execute("pragma ext.branch")
        self.assertEqual(ca.fetchone()[0], "master")

        ca.execute("select * from t1")
        self.assertListEqual(ca.fetchall(), [("first",)])
        ca.execute("select * from ext.t1")
        self.assertListEqual(ca.fetchall(), [("first",)])

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("3rd",),("4th",)])

        c1.execute("pragma branch=master")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",)])

        conn1.close()
        conn2.close()
        connat.close()


    def test14_temporary_db(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()

        c1.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)

        c1.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "branches")

        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")

        # make modifications on connection 1
        c1.execute("create table t1(name)")
        conn1.commit()
        c1.execute("insert into t1 values ('first')")
        conn1.commit()

        # attach a temporary db
        c1.execute("attach database '' as tmp")

        c1.execute("pragma tmp.page_size")
        self.assertEqual(c1.fetchone()[0], 4096)

        c1.execute("pragma tmp.journal_mode")
        self.assertEqual(c1.fetchone()[0], "delete")

        c1.execute("create table tmp.t2 (name)")
        c1.execute("insert into t2 values ('att1')")
        c1.execute("insert into t2 values ('att2')")
        conn1.commit()

        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",)])

        # create a new branch on connection 1
        c1.execute("pragma new_branch=dev at master.2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "dev")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("dev",)])

        c1.execute("insert into t1 values ('second')")
        conn1.commit()

        c1.execute("insert into t2 values ('att3')")
        conn1.commit()

        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",),("att3",)])
        c1.execute("select * from tmp.t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",),("att3",)])

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",)])

        c1.execute("pragma branch=master")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",)])

        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",),("att3",)])
        c1.execute("select * from tmp.t2")
        self.assertListEqual(c1.fetchall(), [("att1",),("att2",),("att3",)])

        conn1.close()


    def test15_forward_merge(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        conn2 = sqlite3.connect('file:test4.db?branches=on')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("pragma journal_mode")
        c2.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "branches")
        self.assertEqual(c2.fetchone()[0], "branches")

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "master")

        # make modifications on connection 1
        c1.execute("create table t1(name)")
        conn1.commit()
        c1.execute("insert into t1 values ('first')")
        conn1.commit()

        # the new modifications should appear on connection 2
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",)])

        # create a new branch on connection 1
        c1.execute("pragma new_branch=dev at master.2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "dev")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("dev",)])

        # the new branch should appear on connection 2
        c2.execute("Pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("dev",)])

        # add new commits to the child branch
        c1.execute("insert into t1 values ('second')")
        conn1.commit()
        c1.execute("insert into t1 values ('third')")
        conn1.commit()
        c1.execute("insert into t1 values ('fourth')")
        conn1.commit()
        c1.execute("insert into t1 values ('fifth')")
        conn1.commit()

        # read the db on conn2 in the master branch
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",)])

        # move to the child branch
        c2.execute("pragma branch=dev")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "dev")

        # read the db on conn2 in the dev branch
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])


        # create 2 new branches starting at the child (dev) branch

        # branch test1
        c1.execute("pragma new_branch=test1 at dev.3")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test1")

        c1.execute("insert into t1 values ('from test1')")
        conn1.commit()

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("from test1",)])

        # branch test2
        c1.execute("pragma new_branch=test2 at dev.6")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test2")

        c1.execute("insert into t1 values ('from test2')")
        conn1.commit()

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("from test2",)])

        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("dev",),("test1",),("test2",)])

        # go back to the dev branch
        c1.execute("pragma branch=dev")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "dev")


        # check the branch info

        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["total_commits"], 2)

        c1.execute("pragma branch_info(dev)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 2)
        self.assertEqual(obj["total_commits"], 6)

        c1.execute("pragma branch_info(test1)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "dev")
        self.assertEqual(obj["source_commit"], 3)
        self.assertEqual(obj["total_commits"], 4)

        c1.execute("pragma branch_info(test2)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "dev")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)

        # check also on conn2

        c2.execute("pragma branch_info(master)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["total_commits"], 2)

        c2.execute("pragma branch_info(dev)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 2)
        self.assertEqual(obj["total_commits"], 6)

        c2.execute("pragma branch_info(test1)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "dev")
        self.assertEqual(obj["source_commit"], 3)
        self.assertEqual(obj["total_commits"], 4)

        c2.execute("pragma branch_info(test2)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "dev")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)


        # test invalid parameters
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev 0")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev -1")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev -2")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.0")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.1")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.2")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.10")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.3 1")

        # move 2 commits from child branch to master
        c1.execute("pragma branch_merge --forward master dev 2")
        self.assertListEqual(c1.fetchall(), [("OK",)])


        # check if the commits were moved

        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["total_commits"], 4)

        c1.execute("pragma branch_info(dev)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 4)
        self.assertEqual(obj["total_commits"], 6)

        c1.execute("pragma branch_info(test1)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 3)
        self.assertEqual(obj["total_commits"], 4)

        c1.execute("pragma branch_info(test2)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "dev")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)

        # the conn 2 should reload the array

        c2.execute("pragma branch_info(master)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["total_commits"], 4)

        c2.execute("pragma branch_info(dev)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 4)
        self.assertEqual(obj["total_commits"], 6)

        c2.execute("pragma branch_info(test1)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 3)
        self.assertEqual(obj["total_commits"], 4)

        c2.execute("pragma branch_info(test2)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "dev")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)


        # read the db on conn2 in the dev branch
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        # move to the parent branch
        c2.execute("pragma branch=master")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "master")

        # it must have 2 more rows on t1
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",)])

        # move to branch test1
        c2.execute("pragma branch=test1")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "test1")

        # it must have the same records
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("from test1",)])

        # move to branch test2
        c2.execute("pragma branch=test2")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "test2")

        # it must have the same records
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("from test2",)])

        # move to the child branch
        c2.execute("pragma branch=dev")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "dev")

        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])


        # read the db on conn1 in the dev branch
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        # move to the parent branch
        c1.execute("pragma branch=master")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")

        # it must have 2 more rows on t1
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])

        # move to branch test1
        c1.execute("pragma branch=test1")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test1")

        # it must have the same records
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("from test1",)])

        # move to branch test2
        c1.execute("pragma branch=test2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test2")

        # it must have the same records
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("from test2",)])

        # move to the child branch
        c1.execute("pragma branch=dev")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "dev")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])


        # now test the merge while at the parent branch
        c1.execute("pragma branch=master")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")


        # test invalid parameters
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.1")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.2")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.3")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev.4")

        # move up to commit 6 from child branch to master
        c1.execute("pragma branch_merge --forward master dev.6")
        self.assertListEqual(c1.fetchall(), [("OK",)])


        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        c1.execute("pragma branch=dev")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "dev")


        # check if the commits were moved

        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["total_commits"], 6)

        c1.execute("pragma branch_info(dev)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 6)

        c1.execute("pragma branch_info(test1)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 3)
        self.assertEqual(obj["total_commits"], 4)

        c1.execute("pragma branch_info(test2)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)

        # the conn 2 should reload the array

        c2.execute("pragma branch_info(master)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["total_commits"], 6)

        c2.execute("pragma branch_info(dev)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 6)

        c2.execute("pragma branch_info(test1)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 3)
        self.assertEqual(obj["total_commits"], 4)

        c2.execute("pragma branch_info(test2)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)


        # read the db on conn2 in the dev branch
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        # move to the parent branch
        c2.execute("pragma branch=master")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "master")

        # read the db on conn2 in the master branch
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        # move to branch test1
        c2.execute("pragma branch=test1")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "test1")

        # it must have the same records
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("from test1",)])

        # move to branch test2
        c2.execute("pragma branch=test2")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "test2")

        # it must have the same records
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("from test2",)])

        # move to the child branch
        c2.execute("pragma branch=dev")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "dev")

        # read the db on conn2 in the dev branch
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])


        # read the db on conn2 in the dev branch
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        # move to the parent branch
        c1.execute("pragma branch=master")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")

        # read the db on conn2 in the master branch
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        # move to branch test1
        c1.execute("pragma branch=test1")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test1")

        # it must have the same records
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("from test1",)])

        # move to branch test2
        c1.execute("pragma branch=test2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test2")

        # it must have the same records
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("from test2",)])

        # move to the child branch
        c1.execute("pragma branch=dev")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "dev")

        # read the db on conn2 in the dev branch
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])


        # create a new table on connection 1
        c1.execute("create table t2(name)")
        conn1.commit()

        # the conn 2 should reload the array

        c2.execute("pragma branch_info(master)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["total_commits"], 6)

        c2.execute("pragma branch_info(dev)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)


        # the new table should appear on connection 2
        c2.execute("select name from sqlite_master")
        self.assertListEqual(c2.fetchall(), [("t1",),("t2",)])


        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        conn2 = sqlite3.connect('file:test4.db?branches=on')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c2.execute("pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("dev",),("test1",),("test2",)])

        c2.execute("pragma branch_info(master)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["total_commits"], 6)

        c2.execute("pragma branch_info(dev)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)

        c2.execute("pragma branch_info(test1)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 3)
        self.assertEqual(obj["total_commits"], 4)

        c2.execute("pragma branch_info(test2)")
        obj = json.loads(c2.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], 6)
        self.assertEqual(obj["total_commits"], 7)

        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",)])

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        c1.execute("pragma branch=test1")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test1")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("from test1",)])

        c1.execute("pragma branch=test2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "test2")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("from test2",)])

        c2.execute("pragma branch=dev")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "dev")

        c2.execute("select name from sqlite_master")
        self.assertListEqual(c2.fetchall(), [("t1",),("t2",)])

        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        conn1.close()
        conn2.close()


    def test16_forward_merge(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        conn2 = sqlite3.connect('file:test4.db?branches=on')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("pragma journal_mode")
        c2.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "branches")
        self.assertEqual(c2.fetchone()[0], "branches")

        c1.execute("pragma branch")
        c2.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "master")
        self.assertEqual(c2.fetchone()[0], "master")

        c1.execute("create table t1(name)")
        conn1.commit()

        c1.execute("pragma new_branch=b2 at master.1")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "b2")

        c1.execute("insert into t1 values ('first')")
        conn1.commit()

        c1.execute("pragma new_branch=b3 at b2")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "b3")

        c1.execute("insert into t1 values ('second')")
        conn1.commit()

        c1.execute("pragma new_branch=b4 at b3")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "b4")

        c1.execute("insert into t1 values ('third')")
        conn1.commit()

        c1.execute("pragma new_branch=b5 at b4")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "b5")

        c1.execute("insert into t1 values ('fourth')")
        conn1.commit()

        c1.execute("pragma new_branch=last at b5")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "last")

        c1.execute("insert into t1 values ('fifth')")
        conn1.commit()


        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("b2",),("b3",),("b4",),("b5",),("last",)])

        c2.execute("Pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("b2",),("b3",),("b4",),("b5",),("last",)])

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [])

        c2.execute("pragma branch=last")
        c2.execute("pragma branch")
        self.assertEqual(c2.fetchone()[0], "last")

        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])


        # extend branch b3
        c1.execute("pragma branch=b3")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "b3")

        c1.execute("insert into t1 values ('from b3')")
        conn1.commit()

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("from b3",)])

        c1.execute("pragma branch=last")
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "last")


        # check the branch info

        for c in (c1,c2):
           c.execute("pragma branch_info(master)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["total_commits"], 1)

           c.execute("pragma branch_info(b2)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["source_branch"], "master")
           self.assertEqual(obj["source_commit"], 1)
           self.assertEqual(obj["total_commits"], 2)

           c.execute("pragma branch_info(b3)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["source_branch"], "b2")
           self.assertEqual(obj["source_commit"], 2)
           self.assertEqual(obj["total_commits"], 4)

           c.execute("pragma branch_info(b4)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["source_branch"], "b3")
           self.assertEqual(obj["source_commit"], 3)
           self.assertEqual(obj["total_commits"], 4)


        # test forward merge using the last of a chain of branches
        c1.execute("pragma branch_merge --forward master last 2")
        self.assertListEqual(c1.fetchall(), [("OK",)])


        # b2 should be deleted
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("b3",),("b4",),("b5",),("last",)])
        c2.execute("Pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("b3",),("b4",),("b5",),("last",)])


        # test forward merge using the last of a chain of branches
        c1.execute("pragma branch_merge --forward master last")
        self.assertListEqual(c1.fetchall(), [("OK",)])


        # check if the commits were moved

        for c in (c1,c2):
           c.execute("pragma branch_info(master)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["total_commits"], 6)

           c.execute("pragma branch_info(b3)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["source_branch"], "master")
           self.assertEqual(obj["source_commit"], 3)
           self.assertEqual(obj["total_commits"], 4)

           c.execute("pragma branch_info(last)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["source_branch"], "master")
           self.assertEqual(obj["source_commit"], 6)
           self.assertEqual(obj["total_commits"], 6)


        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("b3",),("last",)])

        c2.execute("Pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("b3",),("last",)])


        # test persistence

        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        conn2 = sqlite3.connect('file:test4.db?branches=on')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()


        for c in (c1,c2):
           c.execute("pragma branch_info(master)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["total_commits"], 6)

           c.execute("pragma branch_info(b3)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["source_branch"], "master")
           self.assertEqual(obj["source_commit"], 3)
           self.assertEqual(obj["total_commits"], 4)

           c.execute("pragma branch_info(last)")
           obj = json.loads(c.fetchone()[0])
           self.assertEqual(obj["source_branch"], "master")
           self.assertEqual(obj["source_commit"], 6)
           self.assertEqual(obj["total_commits"], 6)

           c.execute("pragma branches")
           self.assertListEqual(c.fetchall(), [("master",),("b3",),("last",)])

           c.execute("pragma branch")
           self.assertEqual(c.fetchone()[0], "master")

           c.execute("select * from t1")
           self.assertListEqual(c.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

           c.execute("pragma branch=last")
           c.execute("pragma branch")
           self.assertEqual(c.fetchone()[0], "last")

           c.execute("select * from t1")
           self.assertListEqual(c.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])


        conn1.close()
        conn2.close()


    def test18_savepoints(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        conn1.isolation_level = None  # disables wrapper autocommit
        c1 = conn1.cursor()

        # to enforce cache spill
        c1.execute("pragma cache_spill=true")
        c1.execute("pragma cache_size=2")

        c1.execute("create table t1 (name)")
        conn1.commit()
        c1.execute("insert into t1 values ('first')")
        conn1.commit()

        c1.execute("savepoint s1")
        c1.execute("create table t2 (name)")
        c1.execute("insert into t1 values ('second')")

        c1.execute("savepoint s2")
        c1.execute("create table t3 (name)")
        c1.execute("insert into t1 values ('third')")
        c1.execute("insert into t2 values ('first')")
        c1.execute("insert into t3 values ('first')")

        c1.execute("savepoint s3")
        c1.execute("create table t4 (name)")
        c1.execute("insert into t1 values ('fourth')")

        c1.execute("savepoint s4")
        c1.execute("create table t5 (name)")
        c1.execute("insert into t1 values ('5th')")
        c1.execute("insert into t2 values ('second')")
        c1.execute("insert into t3 values ('second')")

        c1.execute("savepoint s5")
        c1.execute("insert into t1 values ('6th')")
        c1.execute("insert into t2 values ('third')")
        c1.execute("insert into t3 values ('third')")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("5th",),("6th",)])
        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        c1.execute("select * from t3")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",),("t4",),("t5",)])

        c1.execute("rollback to savepoint s5")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("5th",)])
        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("first",),("second",)])
        c1.execute("select * from t3")
        self.assertListEqual(c1.fetchall(), [("first",),("second",)])
        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",),("t4",),("t5",)])

        c1.execute("release savepoint s5")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("5th",)])
        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("first",),("second",)])
        c1.execute("select * from t3")
        self.assertListEqual(c1.fetchall(), [("first",),("second",)])
        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",),("t4",),("t5",)])

        c1.execute("rollback to savepoint s4")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",)])
        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("first",)])
        c1.execute("select * from t3")
        self.assertListEqual(c1.fetchall(), [("first",)])
        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",),("t4",)])

        c1.execute("rollback to savepoint s3")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("first",)])
        c1.execute("select * from t3")
        self.assertListEqual(c1.fetchall(), [("first",)])
        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",)])

        #conn1.commit()
        c1.execute("release savepoint s1")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("first",)])
        c1.execute("select * from t3")
        self.assertListEqual(c1.fetchall(), [("first",)])
        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",)])

        c1.execute("pragma branch_log master")
        self.assertListEqual(c1.fetchall(), [
            ("master",1,"create table t1 (name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"create table t2 (name)",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",3,"create table t3 (name)",),
            ("master",3,"insert into t1 values ('third')",),
            ("master",3,"insert into t2 values ('first')",),
            ("master",3,"insert into t3 values ('first')",),
        ])

        conn1.close()

        conn1 = sqlite3.connect('file:test4.db?branches=on')
        conn1.isolation_level = None  # disables wrapper autocommit
        c1 = conn1.cursor()

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("first",)])
        c1.execute("select * from t3")
        self.assertListEqual(c1.fetchall(), [("first",)])
        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",)])

        c1.execute("pragma branch_log master")
        self.assertListEqual(c1.fetchall(), [
            ("master",1,"create table t1 (name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"create table t2 (name)",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",3,"create table t3 (name)",),
            ("master",3,"insert into t1 values ('third')",),
            ("master",3,"insert into t2 values ('first')",),
            ("master",3,"insert into t3 values ('first')",),
        ])

        c1.execute("savepoint s1")
        c1.execute("create table tx (name)")
        c1.execute("insert into t1 values ('to be deleted')")

        c1.execute("rollback to savepoint s1")
        c1.execute("create table t4 (name)")
        c1.execute("insert into t1 values ('fourth')")

        c1.execute("savepoint s2")
        c1.execute("create table ty (name)")
        c1.execute("insert into t2 values ('second')")

        c1.execute("rollback to savepoint s2")
        c1.execute("insert into t4 values ('first')")
        c1.execute("insert into t2 values ('third')")
        c1.execute("insert into t3 values ('third')")

        c1.execute("release savepoint s1")

        c1.execute("select name from sqlite_master")
        self.assertListEqual(c1.fetchall(), [("t1",),("t2",),("t3",),("t4",)])
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",)])
        c1.execute("select * from t2")
        self.assertListEqual(c1.fetchall(), [("first",),("third",)])
        c1.execute("select * from t3")
        self.assertListEqual(c1.fetchall(), [("first",),("third",)])
        c1.execute("select * from t4")
        self.assertListEqual(c1.fetchall(), [("first",)])

        c1.execute("pragma branch_log master")
        self.assertListEqual(c1.fetchall(), [
            ("master",1,"create table t1 (name)",),
            ("master",2,"insert into t1 values ('first')",),
            ("master",3,"create table t2 (name)",),
            ("master",3,"insert into t1 values ('second')",),
            ("master",3,"create table t3 (name)",),
            ("master",3,"insert into t1 values ('third')",),
            ("master",3,"insert into t2 values ('first')",),
            ("master",3,"insert into t3 values ('first')",),
            ("master",4,"create table t4 (name)",),
            ("master",4,"insert into t1 values ('fourth')",),
            ("master",4,"insert into t4 values ('first')",),
            ("master",4,"insert into t2 values ('third')",),
            ("master",4,"insert into t3 values ('third')",),
        ])

        conn1.close()


    def test19_closed_connection(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        c1 = conn1.cursor()

        c1.execute("create table if not exists foo (name)")
        conn1.commit()
        c1.execute("insert into foo values ('first')")
        conn1.commit()
        c1.execute("insert into foo values ('second')")
        conn1.commit()
        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["total_commits"], 3)

        # open another connection, read from a previous commit and close the connection
        conn2 = sqlite3.connect('file:test4.db?branches=on')
        c2 = conn2.cursor()
        c2.execute("pragma branch=master.2")
        c2.execute("select * from foo")
        self.assertListEqual(c2.fetchall(), [("first",)])
        conn2.close()

        # try to write and read on the first connection
        c1.execute("insert into foo values ('third')")
        conn1.commit()
        c1.execute("select * from foo")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])

        conn1.close()


    def test20_open_while_writing(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        conn1.isolation_level = None  # disables wrapper autocommit
        c1 = conn1.cursor()

        c1.execute("create table if not exists foo (name)")
        conn1.commit()
        c1.execute("insert into foo values ('first')")
        conn1.commit()
        c1.execute("insert into foo values ('second')")
        conn1.commit()

        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["total_commits"], 3)

        # start writing on the first connection
        c1.execute("begin")
        c1.execute("insert into foo values ('third')")

        # open another connection, read the db and close the connection
        conn2 = sqlite3.connect('file:test4.db?branches=on')
        c2 = conn2.cursor()
        c2.execute("select * from foo")
        self.assertListEqual(c2.fetchall(), [("first",),("second",)])
        c2.execute("pragma branch=master.2")
        c2.execute("select * from foo")
        self.assertListEqual(c2.fetchall(), [("first",)])
        conn2.close()

        # continue writing on the first connection
        c1.execute("insert into foo values ('fourth')")
        conn1.commit()

        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertEqual(obj["total_commits"], 4)

        c1.execute("select * from foo")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",)])

        conn1.close()


    def test21_normal_sqlite(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('test4.db')
        conn2 = sqlite3.connect('test4.db')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("create table t1(name)")
        conn1.commit()
        c1.execute("insert into t1 values ('first')")
        conn1.commit()
        c1.execute("insert into t1 values ('second')")
        conn1.commit()

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",)])

        c2.execute("insert into t1 values ('third')")
        conn2.commit()

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",)])

        c1.execute("insert into t1 values ('fourth')")
        c1.execute("insert into t1 values ('fifth')")
        c1.execute("insert into t1 values ('sixth')")
        conn1.commit()

        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])

        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('test4.db')
        conn2 = sqlite3.connect('test4.db')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",),("sixth",)])

        c2.execute("delete from t1 where name='sixth'")
        conn2.commit()

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])
        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",),("fourth",),("fifth",)])

        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('test4.db')
        conn2 = sqlite3.connect('test4.db')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma journal_mode")
        c2.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "delete")
        self.assertEqual(c2.fetchone()[0], "delete")

        c1.execute("pragma journal_mode=wal")
        c1.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "wal")

        c1.execute("update t1 set name='3rd' where name='third'")
        conn1.commit()

        c2.execute("select * from t1")
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("3rd",),("fourth",),("fifth",)])
        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("3rd",),("fourth",),("fifth",)])

        c2.execute("pragma journal_mode")
        self.assertEqual(c2.fetchone()[0], "wal")

        conn1.close()
        conn2.close()
        conn1 = sqlite3.connect('test4.db')
        conn2 = sqlite3.connect('test4.db')
        if platform.system() == "Darwin":
            conn1.isolation_level = None  # enables autocommit mode
            conn2.isolation_level = None  # enables autocommit mode
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma journal_mode")
        c2.execute("pragma journal_mode")
        self.assertEqual(c1.fetchone()[0], "wal")
        self.assertEqual(c2.fetchone()[0], "wal")

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("3rd",),("fourth",),("fifth",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("3rd",),("fourth",),("fifth",)])

        conn1.close()
        conn2.close()


if __name__ == '__main__':
    unittest.main()
