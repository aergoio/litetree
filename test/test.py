#
# Copyright defined in LICENSE.txt
#
import unittest
import json
import os
import platform
import sqlite3

sqlite_version = "3.27.2"

if sqlite3.sqlite_version != sqlite_version:
    print("wrong SQLite version. expected: " + sqlite_version + " found: " + sqlite3.sqlite_version)
    import sys
    sys.exit(1)

omit_logs = False

def delete_file(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)

delete_file("test.db")
delete_file("test.db-lock")

delete_file("test2.db")
delete_file("test2.db-lock")

delete_file("test3.db")
delete_file("test3.db-lock")

delete_file("test4.db")

class TestSQLiteBranches(unittest.TestCase):

    def test00_read_config(self):
        delete_file("test.db")
        delete_file("test.db-lock")
        conn = sqlite3.connect('file:test.db?branches=on')
        c = conn.cursor()

        c.execute("pragma branch_log")
        if c.fetchone()[0] == "disabled":
            global omit_logs
            omit_logs = True

        conn.close()


    def test01_branches(self):
        delete_file("test.db")
        delete_file("test.db-lock")
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


    def test02_branch_tree(self):
        conn = sqlite3.connect('file:test.db?branches=on')
        c = conn.cursor()

        tree1 = "1-2-3-4-5  master\n"  \
                "  |\n"                \
                "  +-3-4  test\n"      \
                "  | |\n"              \
                "  | `-4  sub-test2\n" \
                "  |\n"                \
                "  `-  sub-test1"

        tree2 = "1-2-3-4-5  master\n"  \
                "  |\n"                \
                "  +-  sub-test1\n"    \
                "  |\n"                \
                "  `-3-4  test\n"      \
                "    |\n"              \
                "    `-4  sub-test2"

        c.execute("pragma branch_tree")
        self.assertIn(c.fetchone()[0], [tree1,tree2])

        conn.close()


    def test02b_sql_log(self):

        if omit_logs:
            self.skipTest("sql log support was not compiled")

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


    def test03_reading_branches_at_the_same_time(self):
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


    def test04_concurrent_access(self):
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


    def test05_single_connection_uri(self):
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


    def test06_invalid_branch_name(self):
        conn = sqlite3.connect('file:test2.db?branches=on')
        c = conn.cursor()

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")
        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",),("b2",),("b3",),("b4",)])

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=  at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch= at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch= ")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=")

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=another.branch at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=.test. at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=.test at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=test. at master.2")

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch==test at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=test= at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=aaa=bbb at master.2")

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=(test at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=test( at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=aaa(bbb at master.2")

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=)test at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=test) at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=aaa)bbb at master.2")

        # invalid characters at beginning
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=-test at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=--test at master.2")

        # numbers
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=3 at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=123 at master.2")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch= 123 at master.2")

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")
        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",),("b2",),("b3",),("b4",)])

        conn.close()


    def test07_rename_branch(self):
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


    def test08_truncate_branch(self):
        # test: truncate in one conn a branch that is in use in another conn, then try to access it in this second conn
        # test: truncate in one conn a branch that is NOT in use in another conn, then try to access it in this second conn

        import shutil
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

        if not omit_logs:
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

        if not omit_logs:
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

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",)])

        # the new name should be there
        c1.execute("pragma branches")
        c2.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])
        self.assertListEqual(c2.fetchall(), [("master",),("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("test2",)])

        conn1.close()
        conn2.close()


    def test09_delete_branch(self):
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

        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",)])

        with self.assertRaises(sqlite3.OperationalError):
            c2.execute("pragma branches")

        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "sub-test1")

        with self.assertRaises(sqlite3.OperationalError):
            c2.execute("pragma branch")


        c1.execute("pragma new_branch=new-one at test")
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("new-one",)])
        c1.execute("pragma branch")
        self.assertEqual(c1.fetchone()[0], "new-one")

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("from test branch",),("val1",),(2,),(3.3,)])



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
        self.assertListEqual(c1.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("new-one",)])
        self.assertListEqual(c2.fetchall(), [("test",),("sub-test1",),("sub-test2",),("renamed-branch",),("new-one",)])

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


    def test10_rollback(self):
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


    def test11_attached_dbs(self):
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

        delete_file("test1.db")
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


    def test12_temporary_db(self):
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


    def test13_discard_commits(self):

        def build_list(start,end):
            list = []
            for i in range(start,end+1):
                list.append(("c" + str(i),))
            return list

        delete_file("test5.db")
        conn = sqlite3.connect('file:test5.db?branches=on')
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

        for i in range(2,16+1):
            c.execute("insert into t1 values ('c" + str(i) + "')")
            conn.commit()

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,16))

        c.execute("pragma new_branch=test at master.8")
        #c.execute("pragma new_branch=test2 at master.8")

        # it should deny the creation of another branch with the same name
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=test at master.2")

        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",),("test",)])
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "test")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,8))

        c.execute("pragma discard_commits master.2-4")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,8))

        c.execute("pragma branch=master")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,16))

        for i in range(2,4+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))

        c.execute("pragma branch=master.1")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.1")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [])

        for i in range(5,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        c.execute("pragma branch=master.5")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.5")

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma discard_commits master.4-7")

        c.execute("pragma branch=master.8")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.8")

        c.execute("pragma discard_commits master.4-7")

        for i in range(2,7+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))


        c.execute("pragma branch=master.1")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.1")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [])

        for i in range(8,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        c.execute("pragma branch=master.8")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.8")


        c.execute("pragma discard_commits master.1-3")

        for i in range(1,7+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))

        for i in range(8,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma discard_commits master.7-9")

        c.execute("pragma branch=master.8")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.8")

        c.execute("pragma discard_commits master.9-11")

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.8")
        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,8))

        for i in range(1,7+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))

        for i in range(9,11+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))

        for i in range(12,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        c.execute("pragma branch=test")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "test")
        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,8))

        conn.close()

        #--------------------------------------------------

        delete_file("test5.db")
        conn = sqlite3.connect('file:test5.db?branches=on')
        c = conn.cursor()

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",)])

        c.execute("create table t1(name)")
        conn.commit()

        for i in range(2,16+1):
            c.execute("insert into t1 values ('c" + str(i) + "')")
            conn.commit()

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,16))

        c.execute("pragma discard_commits master.3-5")

        for i in range(3,5+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma new_branch=test at master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch_truncate master." + str(i))

        c.execute("pragma branch=master.6")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.6")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,6))

        for i in range(1,2+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        c.execute("pragma branch=master")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,16))

        c.execute("pragma discard_commits master.10-12")

        for i in range(10,12+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma new_branch=test at master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch_truncate master." + str(i))

        for i in range(6,9+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        for i in range(13,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        c.execute("pragma branch=master.8")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master.8")

        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma discard_commits master.6-9")

        c.execute("pragma branch=master")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("pragma discard_commits master.6-9")

        for i in range(3,12+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma new_branch=test at master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch_truncate master." + str(i))

        for i in range(1,2+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        for i in range(13,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        c.execute("pragma branch=master")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("pragma discard_commits master.1-7")

        for i in range(1,12+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma new_branch=test at master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch_truncate master." + str(i))

        for i in range(13,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        conn.close()

        #--------------------------------------------------

        delete_file("test5.db")
        conn = sqlite3.connect('file:test5.db?branches=on')
        c = conn.cursor()

        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("pragma branches")
        self.assertListEqual(c.fetchall(), [("master",)])

        c.execute("create table t1(name)")
        conn.commit()

        for i in range(2,16+1):
            c.execute("insert into t1 values ('c" + str(i) + "')")
            conn.commit()

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), build_list(2,16))

        c.execute("pragma discard_commits master.1")
        c.execute("pragma discard_commits master.1-2")
        c.execute("pragma discard_commits master.3-3")
        c.execute("pragma discard_commits master.1-4")

        for i in range(1,4+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma new_branch=test at master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch_truncate master." + str(i))

        for i in range(5,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        c.execute("pragma discard_commits master.7-10")

        for i in range(7,10+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma new_branch=test at master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch_truncate master." + str(i))

        for i in range(5,6+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        c.execute("pragma branch=master")
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master")

        c.execute("pragma discard_commits master.1-12")

        for i in range(1,12+1):
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch=master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma new_branch=test at master." + str(i))
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("pragma branch_truncate master." + str(i))

        for i in range(13,16+1):
            c.execute("pragma branch=master." + str(i))
            c.execute("pragma branch")
            self.assertEqual(c.fetchone()[0], "master." + str(i))
            c.execute("select * from t1")
            self.assertListEqual(c.fetchall(), build_list(2,i))

        conn.close()


    def test14_forward_merge(self):
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
        c1.execute("pragma new_branch=dev")
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
            c1.execute("pragma branch_merge dev master 0")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge dev master -1")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge dev master -2")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge dev.0 master")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge dev.10 master")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge dev.3 master 1")

        # commits that are at or below the merge-base are a no-op (Git's
        # "Already up to date.") and return OK, not an error.
        c1.execute("pragma branch_merge dev.1 master")
        self.assertListEqual(c1.fetchall(), [("OK",)])
        c1.execute("pragma branch_merge dev.2 master")
        self.assertListEqual(c1.fetchall(), [("OK",)])

        # move up to commit 4 from child branch to master (equivalent to 2 commits)
        c1.execute("pragma branch_merge dev.4 master")
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


        # commits at or below the merge-base are a no-op (Git's "Already up to date.")
        c1.execute("pragma branch_merge dev.1 master")
        self.assertListEqual(c1.fetchall(), [("OK",)])
        c1.execute("pragma branch_merge dev.2 master")
        self.assertListEqual(c1.fetchall(), [("OK",)])
        c1.execute("pragma branch_merge dev.3 master")
        self.assertListEqual(c1.fetchall(), [("OK",)])
        c1.execute("pragma branch_merge dev.4 master")
        self.assertListEqual(c1.fetchall(), [("OK",)])

        # move up to commit 6 from child branch to master
        c1.execute("pragma branch_merge dev.6 master")
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
        c1.execute("pragma branch_merge last.3 master")
        self.assertListEqual(c1.fetchall(), [("OK",)])


        # b2 should be deleted
        c1.execute("pragma branches")
        self.assertListEqual(c1.fetchall(), [("master",),("b3",),("b4",),("b5",),("last",)])
        c2.execute("Pragma branches")
        self.assertListEqual(c2.fetchall(), [("master",),("b3",),("b4",),("b5",),("last",)])


        # test forward merge using the last of a chain of branches
        c1.execute("pragma branch_merge last master")
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

        if not omit_logs:
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

        if not omit_logs:
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

        if not omit_logs:
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


    def test21_internal_temporary_dbs(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('file:test4.db?branches=on')
        c1 = conn1.cursor()

        c1.execute("create table t1 (val int)")
        conn1.commit()

        c1.execute("insert into t1 values (1),(2),(3)")
        conn1.commit()

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [(1,),(2,),(3,)])

        c1.execute("with recursive inc(val) as (values (1) union all select val+1 from t1 where val<10) select val from inc")
        self.assertListEqual(c1.fetchall(), [(1,),(2,),(3,),(4,)])

        c1.execute("insert into t1 select val from t1")
        conn1.commit()

        c1.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [(1,),(2,),(3,),(1,),(2,),(3,)])

        c1.execute("with recursive inc(val) as (values (1) union all select val+1 from inc where val<7) select val from inc")
        self.assertListEqual(c1.fetchall(), [(1,),(2,),(3,),(4,),(5,),(6,),(7,)])

        conn1.close()


    def test22_normal_sqlite(self):
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


    def test23_merge(self):
        delete_file("test5.db")
        delete_file("test5.db-lock")

        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("pragma journal_mode")
        self.assertEqual(c.fetchone()[0], "branches")

        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (1, 'alice', 10)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (2, 'bob', 20)")
        conn.commit()

        c.execute("PRAGMA new_branch=source at master")
        c.execute("PRAGMA branch")
        self.assertEqual(c.fetchone()[0], "source")

        c.execute("INSERT INTO t1 VALUES (3, 'charlie', 30)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (4, 'dave', 40)")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t1 VALUES (5, 'eve', 50)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (6, 'frank', 60)")
        conn.commit()

        c.execute("SELECT count(*) FROM t1")
        self.assertEqual(c.fetchone()[0], 4)

        c.execute("PRAGMA branch_merge source")
        self.assertEqual(c.fetchone()[0], "OK")

        c.execute("SELECT count(*) FROM t1")
        self.assertEqual(c.fetchone()[0], 6)

        c.execute("SELECT name FROM t1 ORDER BY id")
        self.assertListEqual(
            c.fetchall(),
            [("alice",), ("bob",), ("charlie",), ("dave",), ("eve",), ("frank",)],
        )

        c.execute("PRAGMA branch=source")
        c.execute("SELECT count(*) FROM t1")
        self.assertEqual(c.fetchone()[0], 4)

        conn.close()

        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (1, 'alice', 10)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (2, 'bob', 20)")
        conn.commit()

        c.execute("PRAGMA new_branch=conflict_src at master")
        c.execute("UPDATE t1 SET value=999 WHERE id=2")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("UPDATE t1 SET value=888 WHERE id=2")
        conn.commit()

        with self.assertRaises(sqlite3.OperationalError) as ctx:
            c.execute("PRAGMA branch_merge conflict_src")
        self.assertIn("abort", str(ctx.exception).lower())

        conn2 = sqlite3.connect("file:test5.db?branches=on")
        c2 = conn2.cursor()
        c2.execute("PRAGMA branch=master")
        c2.execute("SELECT value FROM t1 WHERE id=2")
        self.assertEqual(c2.fetchone()[0], 888)
        conn2.close()
        conn.close()

        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (1, 'alice', 10)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (2, 'bob', 20)")
        conn.commit()

        c.execute("PRAGMA new_branch=theirs_src at master")
        c.execute("UPDATE t1 SET value=999 WHERE id=2")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("UPDATE t1 SET value=888 WHERE id=2")
        conn.commit()

        c.execute("PRAGMA branch_merge --strategy=theirs theirs_src")
        self.assertEqual(c.fetchone()[0], "OK")

        c.execute("SELECT value FROM t1 WHERE id=2")
        self.assertEqual(c.fetchone()[0], 999)

        conn.close()

        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (1, 'alice', 10)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (2, 'bob', 20)")
        conn.commit()

        c.execute("PRAGMA new_branch=ours_src at master")
        c.execute("UPDATE t1 SET value=999 WHERE id=2")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("UPDATE t1 SET value=888 WHERE id=2")
        conn.commit()

        c.execute("PRAGMA branch_merge --strategy=ours ours_src")
        self.assertEqual(c.fetchone()[0], "OK")

        c.execute("SELECT value FROM t1 WHERE id=2")
        self.assertEqual(c.fetchone()[0], 888)

        conn.close()

        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (1, 'alice', 10)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (2, 'bob', 20)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (3, 'charlie', 30)")
        conn.commit()

        c.execute("PRAGMA new_branch=del_src at master")
        c.execute("DELETE FROM t1 WHERE id=3")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t1 VALUES (4, 'dave', 40)")
        conn.commit()

        c.execute("PRAGMA branch_merge del_src")
        self.assertEqual(c.fetchone()[0], "OK")

        c.execute("SELECT id FROM t1 ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (2,), (4,)])

        conn.close()



    def test24_branch_diff(self):
        delete_file("test5.db")
        delete_file("test5.db-lock")

        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (1, 'alice', 10)")
        c.execute("INSERT INTO t1 VALUES (2, 'bob', 20)")
        conn.commit()

        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t1 VALUES (3, 'charlie', 30)")
        c.execute("DELETE FROM t1 WHERE id=2")
        c.execute("UPDATE t1 SET value=99 WHERE id=1")
        conn.commit()

        c.execute("PRAGMA branch=master")

        # 1. forward diff (master -> dev) covers insert, delete, update
        c.execute("PRAGMA branch_diff master dev")
        raw = c.fetchone()[0]
        self.assertIsNotNone(raw)
        d = json.loads(raw)
        self.assertIn("from", d)
        self.assertIn("to", d)
        self.assertIn("tables", d)
        self.assertIn("t1", d["tables"])
        tbl = d["tables"]["t1"]
        self.assertEqual(tbl["columns"], ["id", "name", "value"])
        self.assertEqual(tbl["pk"], ["id"])
        self.assertEqual(tbl.get("inserts", []), [[3, "charlie", 30]])
        self.assertEqual(tbl.get("deletes", []), [[2, "bob", 20]])
        self.assertEqual(len(tbl.get("updates", [])), 1)
        u = tbl["updates"][0]
        self.assertEqual(u["old"], [1, "alice", 10])
        self.assertEqual(u["new"], [1, "alice", 99])

        # 2. empty diff (same branch on both sides)
        c.execute("PRAGMA branch_diff master master")
        d2 = json.loads(c.fetchone()[0])
        self.assertEqual(d2["tables"], {})

        # 3. reverse direction (dev -> master) swaps inserts/deletes and
        # inverts the update
        c.execute("PRAGMA branch_diff dev master")
        d3 = json.loads(c.fetchone()[0])
        tbl3 = d3["tables"]["t1"]
        self.assertEqual(tbl3.get("inserts", []), [[2, "bob", 20]])
        self.assertEqual(tbl3.get("deletes", []), [[3, "charlie", 30]])
        u3 = tbl3["updates"][0]
        self.assertEqual(u3["old"], [1, "alice", 99])
        self.assertEqual(u3["new"], [1, "alice", 10])

        # 4. partial commit (branch.N) — diff against an intermediate point.
        # dev was forked at master.2 so dev.2 == master.2 (empty diff).
        c.execute("PRAGMA branch_diff master dev.2")
        d4 = json.loads(c.fetchone()[0])
        self.assertEqual(d4["tables"], {})
        self.assertEqual(d4["to"], "dev.2")

        # 5. invalid branch -> error
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_diff bogus master")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_diff master bogus")

        # 6. missing "to" argument -> usage error
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_diff master")

        conn.close()

        # 7. Schema changes between the two points must NOT fail. Instead,
        # each affected table is reported with one of:
        #   - "schema_mismatch": true  -> same name, different CREATE stmt
        #   - "created": true          -> exists only on "to"
        #   - "dropped": true          -> exists only on "from"
        # Created/dropped tables also carry columns, pk, and all rows as
        # inserts/deletes so callers can still render them.
        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("INSERT INTO t1 VALUES (1, 'alice')")
        # second table: schema stays identical on both sides
        c.execute("CREATE TABLE t2(id INTEGER PRIMARY KEY, val INTEGER)")
        c.execute("INSERT INTO t2 VALUES (1, 10)")
        # third table: will be dropped on the "to" branch below
        c.execute("CREATE TABLE t_dropped(id INTEGER PRIMARY KEY, payload TEXT)")
        c.execute("INSERT INTO t_dropped VALUES (7, 'gone'), (8, 'bye')")
        conn.commit()

        c.execute("PRAGMA new_branch=schema_dev at master")
        c.execute("ALTER TABLE t1 ADD COLUMN extra TEXT")
        c.execute("UPDATE t1 SET extra='x' WHERE id=1")
        c.execute("INSERT INTO t2 VALUES (2, 20)")
        c.execute("DROP TABLE t_dropped")
        # table that exists only on schema_dev (i.e. "created" vs master)
        c.execute("CREATE TABLE t_created(id INTEGER PRIMARY KEY, lbl TEXT)")
        c.execute("INSERT INTO t_created VALUES (1, 'new'), (2, 'row')")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("PRAGMA branch_diff master schema_dev")
        raw = c.fetchone()[0]
        d = json.loads(raw)

        # t1 -> schema differs (column added) => schema_mismatch carries a
        # schema_diff describing the added column plus a union-column
        # row-level diff (unchanged rows are omitted).
        self.assertIn("t1", d["tables"])
        t1 = d["tables"]["t1"]
        self.assertTrue(t1.get("schema_mismatch"))
        sd = t1["schema_diff"]
        self.assertEqual([a["name"] for a in sd["added"]], ["extra"])
        self.assertEqual(sd["removed"], [])
        self.assertEqual(sd["modified"], [])
        self.assertEqual(t1["columns"], ["id", "name", "extra"])
        self.assertEqual(t1["pk"], ["id"])
        # no inserts/deletes; id=1 gained extra='x', others unchanged
        self.assertEqual(t1["inserts"], [])
        self.assertEqual(t1["deletes"], [])
        self.assertEqual(t1["updates"], [
            {"old": [1, "alice", None], "new": [1, "alice", "x"]},
        ])

        # t2 -> matching schema, normal DML diff
        t2 = d["tables"]["t2"]
        self.assertNotIn("schema_mismatch", t2)
        self.assertNotIn("created", t2)
        self.assertNotIn("dropped", t2)
        self.assertEqual(t2.get("inserts", []), [[2, 20]])

        # t_created -> only on schema_dev (the "to" side)
        self.assertIn("t_created", d["tables"])
        tc = d["tables"]["t_created"]
        self.assertTrue(tc.get("created"))
        self.assertNotIn("dropped", tc)
        self.assertNotIn("schema_mismatch", tc)
        self.assertEqual(tc["columns"], ["id", "lbl"])
        self.assertEqual(tc["pk"], ["id"])
        self.assertEqual(tc["inserts"], [[1, "new"], [2, "row"]])

        # t_dropped -> only on master (the "from" side)
        self.assertIn("t_dropped", d["tables"])
        td = d["tables"]["t_dropped"]
        self.assertTrue(td.get("dropped"))
        self.assertNotIn("created", td)
        self.assertNotIn("schema_mismatch", td)
        self.assertEqual(td["columns"], ["id", "payload"])
        self.assertEqual(td["pk"], ["id"])
        self.assertEqual(td["deletes"], [[7, "gone"], [8, "bye"]])

        conn.close()

        # 8. Schema mismatch with a column removed AND a column type changed:
        # union column list is "from-first, then to-only"; rows are reported
        # with phantom positions rendered as null on the side that lacks the
        # column. Type-only changes show up in schema_diff.modified.
        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute(
            "CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT, "
            "value INTEGER, old_col TEXT)"
        )
        c.execute("INSERT INTO t1 VALUES (1,'alice',10,'legacy')")
        c.execute("INSERT INTO t1 VALUES (2,'bob',20,NULL)")
        c.execute("INSERT INTO t1 VALUES (3,'charlie',30,NULL)")
        conn.commit()

        c.execute("PRAGMA new_branch=dev at master")
        # rebuild t1 with a different declared type and a new "extra" column,
        # dropping "old_col"
        c.execute("ALTER TABLE t1 RENAME TO t1_old")
        c.execute(
            "CREATE TABLE t1(id INTEGER PRIMARY KEY, name TEXT, "
            "value TEXT, extra TEXT)"
        )
        c.execute("INSERT INTO t1 SELECT id, name, CAST(value AS TEXT), NULL FROM t1_old")
        c.execute("DROP TABLE t1_old")
        c.execute("DELETE FROM t1 WHERE id=3")
        c.execute("INSERT INTO t1 VALUES (4,'dave','40',NULL)")
        c.execute("UPDATE t1 SET extra='x' WHERE id=1")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("PRAGMA branch_diff master dev")
        d8 = json.loads(c.fetchone()[0])
        t1 = d8["tables"]["t1"]
        self.assertTrue(t1.get("schema_mismatch"))
        sd = t1["schema_diff"]
        self.assertEqual([a["name"] for a in sd["added"]],   ["extra"])
        self.assertEqual([r["name"] for r in sd["removed"]], ["old_col"])
        self.assertEqual([m["name"] for m in sd["modified"]], ["value"])
        # modified entry carries only changed attributes (type here)
        self.assertEqual(
            sd["modified"][0]["type"],
            {"from": "INTEGER", "to": "TEXT"},
        )
        # union columns: from-order first (id,name,value,old_col), then
        # to-only (extra)
        self.assertEqual(t1["columns"],
                         ["id", "name", "value", "old_col", "extra"])
        self.assertEqual(t1["inserts"], [[4, "dave", "40", None, None]])
        self.assertEqual(t1["deletes"], [[3, "charlie", 30, None, None]])
        updates = {u["old"][0]: u for u in t1["updates"]}
        self.assertIn(1, updates)
        self.assertEqual(updates[1]["old"], [1, "alice", 10, "legacy", None])
        self.assertEqual(updates[1]["new"], [1, "alice", "10", None, "x"])

        conn.close()


    def test25_branch_rebase(self):
        delete_file("test5.db")
        delete_file("test5.db-lock")

        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        # --- 1. SQL-replay: UPDATE x=x+1 on both branches should sum up ---
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 10)")
        conn.commit()

        c.execute("PRAGMA new_branch=dev at master")
        c.execute("UPDATE t SET val = val + 1 WHERE id = 1")
        conn.commit()
        c.execute("UPDATE t SET val = val + 1 WHERE id = 1")
        conn.commit()
        # dev now has val = 12

        c.execute("PRAGMA branch=master")
        c.execute("UPDATE t SET val = val + 1 WHERE id = 1")
        conn.commit()
        # master now has val = 11

        # rebase dev onto master tip: the two UPDATE x=x+1 commands are re-
        # executed against master's state (11), so the result should be 13
        c.execute("PRAGMA branch=dev")
        c.execute("PRAGMA branch_rebase master")
        self.assertEqual(c.fetchone()[0], "OK")

        c.execute("PRAGMA branch=master")
        c.execute("SELECT val FROM t WHERE id = 1")
        self.assertEqual(c.fetchone()[0], 13)
        conn.close()

        # --- 2. rebase into a named new branch leaves originals untouched ---
        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 10)")
        conn.commit()

        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (2, 20)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (3, 30)")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (4, 40)")
        conn.commit()

        c.execute("PRAGMA branch_rebase dev master rebased")
        self.assertEqual(c.fetchone()[0], "OK")

        # originals untouched
        c.execute("PRAGMA branch=master")
        c.execute("SELECT id FROM t ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (4,)])

        c.execute("PRAGMA branch=dev")
        c.execute("SELECT id FROM t ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (2,), (3,)])

        # new branch has master's content plus dev's replayed commits
        c.execute("PRAGMA branch=rebased")
        c.execute("SELECT id FROM t ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (2,), (3,), (4,)])
        conn.close()

        # --- 3. --check must not modify anything ---
        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 10)")
        conn.commit()

        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (2, 20)")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (3, 30)")
        conn.commit()

        # capture branches before
        c.execute("PRAGMA branches")
        before = sorted([r[0] for r in c.fetchall()])

        c.execute("PRAGMA branch=dev")
        c.execute("PRAGMA branch_rebase --check master")
        self.assertEqual(c.fetchone()[0], "OK")

        # same branches, same content
        c.execute("PRAGMA branches")
        self.assertListEqual(sorted([r[0] for r in c.fetchall()]), before)

        c.execute("PRAGMA branch=dev")
        c.execute("SELECT id FROM t ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (2,)])

        c.execute("PRAGMA branch=master")
        c.execute("SELECT id FROM t ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (3,)])
        conn.close()

        # --- 4. range rebase (branch.start-end) to an internal commit ---
        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
        conn.commit()
        for i in range(1, 5):
            c.execute("INSERT INTO t VALUES (?)", (i,))
            conn.commit()
        # master.1 = CREATE TABLE
        # master.2..5 = INSERT 1..4

        # move commits master.4-5 (INSERT 3, INSERT 4) onto master.2 into 'moved'
        c.execute("PRAGMA branch_rebase master.4-5 master.2 moved")
        self.assertEqual(c.fetchone()[0], "OK")

        c.execute("PRAGMA branch=moved")
        c.execute("SELECT id FROM t ORDER BY id")
        # moved = master.2 (has id=1) + INSERT 3 + INSERT 4
        self.assertListEqual(c.fetchall(), [(1,), (3,), (4,)])
        conn.close()

        # --- 5. default strategy aborts on conflict; --force proceeds ---
        delete_file("test5.db")
        delete_file("test5.db-lock")
        conn = sqlite3.connect("file:test5.db?branches=on")
        c = conn.cursor()

        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()

        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (2, 200)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (3, 300)")
        conn.commit()

        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (2, 999)")  # same pk as dev.2
        conn.commit()

        # default: abort on UNIQUE constraint
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_rebase dev master newb")

        # newb must not be left behind
        c.execute("PRAGMA branches")
        self.assertNotIn("newb", [r[0] for r in c.fetchall()])

        # --force: skip the conflicting statement, apply the rest
        c.execute("PRAGMA branch_rebase --force dev master newb2")
        self.assertEqual(c.fetchone()[0], "OK")

        c.execute("PRAGMA branch=newb2")
        c.execute("SELECT id, val FROM t ORDER BY id")
        # keeps master's (2, 999); dev's (2, 200) was skipped; (3, 300) applied
        self.assertListEqual(c.fetchall(), [(1, 100), (2, 999), (3, 300)])
        conn.close()

        delete_file("test5.db")
        delete_file("test5.db-lock")


    # ------------------------------------------------------------------
    # test26_merge_conflicts — exhaustive merge conflict scenarios that
    # test23_merge did not cover (insert/insert, delete/update, update/delete,
    # unique-index collision, multi-table merges, --check dry run, source.N
    # partial-commit merges, self-merge no-op).
    # ------------------------------------------------------------------
    def test26_merge_conflicts(self):

        def fresh(label="test5"):
            """Start from a clean database on every sub-case."""
            delete_file(label + ".db")
            delete_file(label + ".db-lock")
            return sqlite3.connect("file:" + label + ".db?branches=on")

        # ---- 1. INSERT/INSERT with same PK: default aborts --------------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (1, 200)")   # same PK, different value
        conn.commit()
        with self.assertRaises(sqlite3.OperationalError) as ctx:
            c.execute("PRAGMA branch_merge dev")
        self.assertIn("abort", str(ctx.exception).lower())
        # master unchanged
        c.execute("SELECT val FROM t WHERE id=1")
        self.assertEqual(c.fetchone()[0], 200)
        conn.close()

        # ---- 2. INSERT/INSERT same PK: --strategy=theirs takes dev's ----
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (1, 200)")
        conn.commit()
        c.execute("PRAGMA branch_merge --strategy=theirs dev")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT val FROM t WHERE id=1")
        self.assertEqual(c.fetchone()[0], 100)        # theirs wins
        conn.close()

        # ---- 3. INSERT/INSERT same PK: --strategy=ours keeps master's ---
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (1, 200)")
        conn.commit()
        c.execute("PRAGMA branch_merge --strategy=ours dev")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT val FROM t WHERE id=1")
        self.assertEqual(c.fetchone()[0], 200)        # ours wins
        conn.close()

        # ---- 4. DELETE (source) vs UPDATE (dest): default aborts --------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("DELETE FROM t WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("UPDATE t SET val=999 WHERE id=1")
        conn.commit()
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_merge dev")
        # master unchanged
        c.execute("SELECT val FROM t WHERE id=1")
        self.assertEqual(c.fetchone()[0], 999)
        conn.close()

        # ---- 5. DELETE (source) vs UPDATE (dest): theirs -> row gone ----
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("DELETE FROM t WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("UPDATE t SET val=999 WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch_merge --strategy=theirs dev")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT count(*) FROM t")
        self.assertEqual(c.fetchone()[0], 0)           # delete applied
        conn.close()

        # ---- 6. UPDATE (source) vs DELETE (dest): default aborts --------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("UPDATE t SET val=777 WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("DELETE FROM t WHERE id=1")
        conn.commit()
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_merge dev")
        c.execute("SELECT count(*) FROM t")
        self.assertEqual(c.fetchone()[0], 0)           # master unchanged
        conn.close()

        # ---- 7. UPDATE (source) vs DELETE (dest): theirs omits the UPDATE
        # because its "old" row is missing. The row therefore stays deleted
        # (this is the standard sessions NOTFOUND->OMIT behaviour).
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("UPDATE t SET val=777 WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("DELETE FROM t WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch_merge --strategy=theirs dev")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT count(*) FROM t WHERE id=1")
        self.assertEqual(c.fetchone()[0], 0)
        conn.close()

        # ---- 8. UNIQUE index collision (non-PK column) ------------------
        conn = fresh()
        c = conn.cursor()
        c.execute(
            "CREATE TABLE t(id INTEGER PRIMARY KEY, "
            "email TEXT NOT NULL UNIQUE)"
        )
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 'a@x')")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (2, 'collide@x')")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (3, 'collide@x')")  # same email
        conn.commit()
        # different PKs but the UNIQUE(email) constraint is violated
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_merge dev")
        conn.close()

        # ---- 9. Multi-table merge: insert in t1, update in t2, delete t3 -
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY, v INTEGER)")
        c.execute("CREATE TABLE t2(id INTEGER PRIMARY KEY, v INTEGER)")
        c.execute("CREATE TABLE t3(id INTEGER PRIMARY KEY, v INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t1 VALUES (1, 10)")
        c.execute("INSERT INTO t2 VALUES (1, 20)")
        c.execute("INSERT INTO t3 VALUES (1, 30), (2, 40)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t1 VALUES (2, 99)")
        c.execute("UPDATE t2 SET v=200 WHERE id=1")
        c.execute("DELETE FROM t3 WHERE id=2")
        conn.commit()
        c.execute("PRAGMA branch=master")
        # master touches different tables/rows so no conflicts
        c.execute("INSERT INTO t1 VALUES (3, 50)")
        c.execute("INSERT INTO t3 VALUES (3, 60)")
        conn.commit()
        c.execute("PRAGMA branch_merge dev")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT id FROM t1 ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (2,), (3,)])
        c.execute("SELECT v FROM t2 WHERE id=1")
        self.assertEqual(c.fetchone()[0], 200)
        c.execute("SELECT id FROM t3 ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (3,)])
        conn.close()

        # ---- 10. --check dry-run: no mutation on conflicting merge -----
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 1)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("UPDATE t SET v=11 WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("UPDATE t SET v=22 WHERE id=1")
        conn.commit()

        # --check must not mutate anything, even when conflicts exist
        c.execute("PRAGMA branch_merge --check dev")
        # OK return -- check is informational; concrete status would need
        # a richer contract, but the mutation rule is what we care about.
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT v FROM t WHERE id=1")
        self.assertEqual(c.fetchone()[0], 22)         # master untouched
        c.execute("PRAGMA branch=dev")
        c.execute("SELECT v FROM t WHERE id=1")
        self.assertEqual(c.fetchone()[0], 11)         # dev untouched
        conn.close()

        # ---- 11. Self-merge is a no-op ----------------------------------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        c.execute("PRAGMA branch_merge master master")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT count(*) FROM t")
        self.assertEqual(c.fetchone()[0], 1)
        conn.close()

        # ---- 12. Partial-commit merge (source.N) ------------------------
        # Only take the first change from dev, not the second.
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (1, 10)")      # dev commit #2
        conn.commit()
        c.execute("INSERT INTO t VALUES (2, 20)")      # dev commit #3
        conn.commit()

        c.execute("PRAGMA branch=master")
        # merge only dev up to its commit 2 -> only (1,10) comes in
        c.execute("PRAGMA branch_merge dev.2")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT id FROM t ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,)])
        conn.close()

        # ---- 13. Merge with disjoint INSERTs (pure fast-forward-like) ---
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (1, 10)")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (2, 20)")
        conn.commit()
        c.execute("PRAGMA branch_merge dev")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT id FROM t ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (2,)])
        conn.close()

        delete_file("test5.db")
        delete_file("test5.db-lock")


    # ------------------------------------------------------------------
    # test27_rebase_conflicts — exhaustive rebase conflict scenarios.
    # test25_branch_rebase already covers: SQL-replay summing, rebase into
    # a named new_branch, --check idempotency, range rebase, UNIQUE default
    # abort vs --force. Here we add: UPDATE against a deleted row, NOT NULL
    # violation, CHECK constraint, single-commit rebase, rebase with no
    # commits in range, rebase into internal commit without new_branch,
    # rebase that creates a table (DDL replay), and rebase producing
    # multiple commits preserved as separate entries in the log.
    # ------------------------------------------------------------------
    def test27_rebase_conflicts(self):

        def fresh(label="test5"):
            delete_file(label + ".db")
            delete_file(label + ".db-lock")
            return sqlite3.connect("file:" + label + ".db?branches=on")

        # ---- 1. UPDATE a row deleted on the new base --------------------
        # The replayed UPDATE simply affects 0 rows; rebase succeeds silently.
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 100)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("UPDATE t SET v=200 WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("DELETE FROM t WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch_rebase dev master newb")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("PRAGMA branch=newb")
        c.execute("SELECT count(*) FROM t")
        self.assertEqual(c.fetchone()[0], 0)           # row is still gone
        conn.close()

        # ---- 2. NOT NULL violation (default aborts, --force skips) ------
        conn = fresh()
        c = conn.cursor()
        c.execute(
            "CREATE TABLE t(id INTEGER PRIMARY KEY, "
            "name TEXT NOT NULL)"
        )
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        # record an INSERT with a value that will later violate NOT NULL
        # after schema change on master (we simulate it by dropping and
        # re-creating the table on master with a narrower constraint).
        c.execute("INSERT INTO t VALUES (1, 'alice')")
        conn.commit()
        c.execute("PRAGMA branch=master")
        # add a CHECK constraint by rebuilding
        c.execute("ALTER TABLE t RENAME TO t_old")
        c.execute(
            "CREATE TABLE t(id INTEGER PRIMARY KEY, "
            "name TEXT NOT NULL CHECK(length(name)>=5))"
        )
        c.execute("INSERT INTO t SELECT * FROM t_old")
        c.execute("DROP TABLE t_old")
        conn.commit()
        # dev's INSERT ('alice' is fine -> 5 chars). Use a name that
        # violates the check to force the conflict.
        c.execute("PRAGMA branch=dev")
        c.execute("INSERT INTO t VALUES (2, 'hi')")    # length < 5
        conn.commit()

        # default: abort because of CHECK
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_rebase dev master newb_default")
        # newb_default must not be left behind
        c.execute("PRAGMA branches")
        names = [r[0] for r in c.fetchall()]
        self.assertNotIn("newb_default", names)

        # --force: skip the offending row
        c.execute("PRAGMA branch_rebase --force dev master newb_force")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("PRAGMA branch=newb_force")
        c.execute("SELECT count(*) FROM t")
        # only master's (1,'alice') survives; dev had no other rows above
        # its source commit, and the INSERT ('hi') was skipped.
        self.assertEqual(c.fetchone()[0], 1)
        conn.close()

        # ---- 3. Rebase a single commit (branch.commit syntax) -----------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (1, 10)")      # dev.2
        conn.commit()
        c.execute("INSERT INTO t VALUES (2, 20)")      # dev.3
        conn.commit()
        c.execute("INSERT INTO t VALUES (3, 30)")      # dev.4
        conn.commit()
        c.execute("PRAGMA branch=master")
        # rebase only dev.3 onto master into a new branch
        c.execute("PRAGMA branch_rebase dev.3 master only3")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("PRAGMA branch=only3")
        c.execute("SELECT id FROM t ORDER BY id")
        self.assertListEqual(c.fetchall(), [(2,)])
        conn.close()

        # ---- 4. Rebase range covering 0 real new commits (src_from==src_to+1
        #         case)  — we target the first commit on master to prove the
        #         function doesn't crash on a single commit range. -------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        c.execute("PRAGMA new_branch=other at master.1")
        # rebase only master.2 (the INSERT) onto other -> result has the row
        c.execute("PRAGMA branch_rebase master.2-2 other replay")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("PRAGMA branch=replay")
        c.execute("SELECT id FROM t")
        self.assertListEqual(c.fetchall(), [(1,)])
        conn.close()

        # ---- 5. Rebase onto an internal commit WITHOUT new_branch -> err
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (2)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (3)")
        conn.commit()
        # rebase dev onto master.2 (internal commit) without giving a new
        # branch name -> MISUSE
        c.execute("PRAGMA branch=master")
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("PRAGMA branch_rebase dev master.2")
        conn.close()

        # ---- 6. Rebase with DDL replay (CREATE TABLE on source) ---------
        # The source commit contains a schema statement; replaying must
        # create the table on the target.
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE base(id INTEGER PRIMARY KEY)")
        conn.commit()
        c.execute("INSERT INTO base VALUES (1)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("CREATE TABLE extra(x INTEGER, y INTEGER)")
        conn.commit()
        c.execute("INSERT INTO extra VALUES (10, 20)")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO base VALUES (2)")
        conn.commit()
        c.execute("PRAGMA branch_rebase dev master ddl_new")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("PRAGMA branch=ddl_new")
        # the new table was created by SQL replay
        c.execute("SELECT * FROM extra")
        self.assertListEqual(c.fetchall(), [(10, 20)])
        # and the base table still has the master rows
        c.execute("SELECT id FROM base ORDER BY id")
        self.assertListEqual(c.fetchall(), [(1,), (2,)])
        conn.close()

        # ---- 7. Multi-commit rebase preserves one commit per source ----
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (1, 10)")      # dev.2
        conn.commit()
        c.execute("INSERT INTO t VALUES (2, 20)")      # dev.3
        conn.commit()
        c.execute("INSERT INTO t VALUES (3, 30)")      # dev.4
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (9, 90)")      # master.2
        conn.commit()
        c.execute("PRAGMA branch_rebase dev master rebased_multi")
        self.assertEqual(c.fetchone()[0], "OK")
        # The branch log must have one replayed commit per source commit,
        # each owned by rebased_multi (not master).
        c.execute("PRAGMA branch_log rebased_multi")
        rows = c.fetchall()
        replayed = [r for r in rows if r[0] == "rebased_multi"]
        self.assertEqual(len(replayed), 3)
        # And the commit numbers are contiguous starting from master.tip+1.
        nums = sorted(r[1] for r in replayed)
        self.assertEqual(nums, [3, 4, 5])
        conn.close()

        # ---- 8. Rebase is a no-op when source == base tip and target is
        #         the same branch --------------------------------------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        # rebase master onto master.tip with no new branch -> no-op OK
        c.execute("PRAGMA branch_rebase master master")
        self.assertEqual(c.fetchone()[0], "OK")
        c.execute("SELECT id FROM t")
        self.assertListEqual(c.fetchall(), [(1,)])
        conn.close()

        delete_file("test5.db")
        delete_file("test5.db-lock")


    # ------------------------------------------------------------------
    # test28_branch_diff_extras — diff cases that test24_branch_diff did
    # not exercise: BLOB hex encoding, NULL values, composite PKs, TEXT
    # PKs, WITHOUT ROWID tables, diff from branch.commit (partial), and
    # branches with completely disjoint change sets.
    # ------------------------------------------------------------------
    def test28_branch_diff_extras(self):

        def fresh(label="test5"):
            delete_file(label + ".db")
            delete_file(label + ".db-lock")
            return sqlite3.connect("file:" + label + ".db?branches=on")

        # ---- 1. BLOB values are serialized as {"blob":"<hex>"} ----------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, data BLOB)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, x'DEADBEEF')")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (2, x'CAFEBABE')")
        c.execute("UPDATE t SET data=x'00FF' WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("PRAGMA branch_diff master dev")
        d = json.loads(c.fetchone()[0])
        t = d["tables"]["t"]

        # INSERT: blob wrapped as object
        self.assertEqual(len(t["inserts"]), 1)
        blob_ins = t["inserts"][0][1]
        self.assertIsInstance(blob_ins, dict)
        self.assertIn("blob", blob_ins)
        self.assertEqual(blob_ins["blob"].lower(), "cafebabe")
        # UPDATE: old and new blobs both encoded
        self.assertEqual(len(t["updates"]), 1)
        upd = t["updates"][0]
        self.assertEqual(upd["old"][1]["blob"].lower(), "deadbeef")
        self.assertEqual(upd["new"][1]["blob"].lower(), "00ff")
        conn.close()

        # ---- 2. NULL values in inserts and updates ---------------------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, a TEXT, b INTEGER)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 'x', 10)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (2, NULL, NULL)")
        c.execute("UPDATE t SET a=NULL, b=NULL WHERE id=1")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("PRAGMA branch_diff master dev")
        d = json.loads(c.fetchone()[0])
        t = d["tables"]["t"]
        self.assertEqual(t["inserts"], [[2, None, None]])
        self.assertEqual(t["updates"][0]["old"], [1, "x", 10])
        self.assertEqual(t["updates"][0]["new"], [1, None, None])
        conn.close()

        # ---- 3. Composite primary key ----------------------------------
        conn = fresh()
        c = conn.cursor()
        c.execute(
            "CREATE TABLE t(a INTEGER, b INTEGER, v TEXT, "
            "PRIMARY KEY(a, b))"
        )
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 1, 'one')")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (1, 2, 'one-two')")
        c.execute("UPDATE t SET v='updated' WHERE a=1 AND b=1")
        c.execute("INSERT INTO t VALUES (2, 1, 'two-one')")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("PRAGMA branch_diff master dev")
        d = json.loads(c.fetchone()[0])
        t = d["tables"]["t"]
        self.assertEqual(t["pk"], ["a", "b"])
        self.assertEqual(sorted(t["inserts"]),
                         [[1, 2, "one-two"], [2, 1, "two-one"]])
        self.assertEqual(t["updates"][0]["old"], [1, 1, "one"])
        self.assertEqual(t["updates"][0]["new"], [1, 1, "updated"])
        conn.close()

        # ---- 4. TEXT primary key ---------------------------------------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE kv(k TEXT PRIMARY KEY, v INTEGER)")
        conn.commit()
        c.execute("INSERT INTO kv VALUES ('alpha', 1)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO kv VALUES ('beta', 2)")
        c.execute("UPDATE kv SET v=99 WHERE k='alpha'")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("PRAGMA branch_diff master dev")
        d = json.loads(c.fetchone()[0])
        t = d["tables"]["kv"]
        self.assertEqual(t["pk"], ["k"])
        self.assertEqual(t["inserts"], [["beta", 2]])
        self.assertEqual(t["updates"][0]["old"], ["alpha", 1])
        self.assertEqual(t["updates"][0]["new"], ["alpha", 99])
        conn.close()

        # ---- 5. WITHOUT ROWID table ------------------------------------
        conn = fresh()
        c = conn.cursor()
        c.execute(
            "CREATE TABLE wr(k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID"
        )
        conn.commit()
        c.execute("INSERT INTO wr VALUES ('a', 'A')")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO wr VALUES ('b', 'B')")
        c.execute("DELETE FROM wr WHERE k='a'")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("PRAGMA branch_diff master dev")
        d = json.loads(c.fetchone()[0])
        t = d["tables"]["wr"]
        self.assertEqual(t["pk"], ["k"])
        self.assertEqual(t["inserts"], [["b", "B"]])
        self.assertEqual(t["deletes"], [["a", "A"]])
        conn.close()

        # ---- 6. Diff with a branch.commit endpoint on the "from" side --
        # master.2 is before any of master's inserts; diff(master.2, dev)
        # should show everything dev has minus the shared starting state.
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v INTEGER)")  # master.1
        conn.commit()
        c.execute("INSERT INTO t VALUES (1, 10)")                        # master.2
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t VALUES (2, 20)")                        # dev.3
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("INSERT INTO t VALUES (3, 30)")                        # master.3
        conn.commit()

        c.execute("PRAGMA branch_diff master.2 dev")
        d = json.loads(c.fetchone()[0])
        self.assertEqual(d["from"], "master.2")
        t = d["tables"]["t"]
        self.assertEqual(t["inserts"], [[2, 20]])                        # dev's row
        self.assertEqual(t.get("deletes", []), [])
        self.assertEqual(t.get("updates", []), [])
        conn.close()

        # ---- 7. Diff against self with explicit commits is empty -------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
        conn.commit()
        c.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        c.execute("PRAGMA branch_diff master.2 master.2")
        d = json.loads(c.fetchone()[0])
        self.assertEqual(d["from"], "master.2")
        self.assertEqual(d["to"], "master.2")
        self.assertEqual(d["tables"], {})
        conn.close()

        # ---- 8. Disjoint multi-table changes show up per table ---------
        conn = fresh()
        c = conn.cursor()
        c.execute("CREATE TABLE t1(id INTEGER PRIMARY KEY)")
        c.execute("CREATE TABLE t2(id INTEGER PRIMARY KEY)")
        c.execute("CREATE TABLE t3(id INTEGER PRIMARY KEY)")
        conn.commit()
        c.execute("PRAGMA new_branch=dev at master")
        c.execute("INSERT INTO t1 VALUES (1)")
        c.execute("INSERT INTO t2 VALUES (2)")
        c.execute("INSERT INTO t3 VALUES (3)")
        conn.commit()
        c.execute("PRAGMA branch=master")
        c.execute("PRAGMA branch_diff master dev")
        d = json.loads(c.fetchone()[0])
        self.assertEqual(set(d["tables"].keys()), {"t1", "t2", "t3"})
        self.assertEqual(d["tables"]["t1"]["inserts"], [[1]])
        self.assertEqual(d["tables"]["t2"]["inserts"], [[2]])
        self.assertEqual(d["tables"]["t3"]["inserts"], [[3]])
        conn.close()

        delete_file("test5.db")
        delete_file("test5.db-lock")


    @classmethod
    def tearDownClass(self):
        delete_file("test.db")
        delete_file("test.db-lock")

        delete_file("test1.db")
        delete_file("attached.db")

        delete_file("test2.db")
        delete_file("test2.db-lock")

        delete_file("test3.db")
        delete_file("test3.db-lock")

        delete_file("test4.db")
        delete_file("test4.db-lock")

        delete_file("test5.db")
        delete_file("test5.db-lock")


if __name__ == '__main__':
    unittest.main()
