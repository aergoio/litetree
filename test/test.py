#
# Copyright defined in LICENSE.txt
#
import unittest
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
    import sys
    sys.exit(1)

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

    def test01_branches(self):
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
        self.assertEqual(obj["total_commits"], 3)

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
        self.assertListEqual(c2.fetchall(), [("first",),("from test branch",)])

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

        # try to create a branch in which its name contains a dot
        with self.assertRaises(sqlite3.OperationalError):
            c.execute("pragma new_branch=another.branch at master.2")

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

        c1.execute("pragma branch_info(master)")
        obj = json.loads(c1.fetchone()[0])
        self.assertGreater(obj["total_commits"], 4)

        # try to truncate to an allowed point
        c1.execute("pragma branch_truncate(master.4)")

        c1.execute("select * from t1")
        c2.execute("select * from t1")
        self.assertListEqual(c1.fetchall(), [("first",),("second",),("third",)])
        self.assertListEqual(c2.fetchall(), [("first",),("second",),("third",)])

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
        self.assertListEqual(c1.fetchall(), [("first",),("from test branch",)])

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
        self.assertListEqual(c1.fetchall(), [("first",),("from test branch",)])

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
        self.assertListEqual(c1.fetchall(), [("first",),("from test branch",)])
        self.assertListEqual(c2.fetchall(), [("first",),("from test branch",)])

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


    def test13_forward_merge(self):
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


        # test invalid parameters
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev ")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev 0")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev -1")
        with self.assertRaises(sqlite3.OperationalError):
            c1.execute("pragma branch_merge --forward master dev -2")

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
