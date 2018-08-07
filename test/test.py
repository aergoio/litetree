#
# Copyright defined in LICENSE.txt
#
import unittest
import sqlite3
import json
import os

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
        c1 = conn1.cursor()
        c2 = conn2.cursor()

        c1.execute("pragma page_size")
        c2.execute("pragma page_size")
        self.assertEqual(c1.fetchone()[0], 4096)
        self.assertEqual(c2.fetchone()[0], 4096)

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
        c1.execute("pragma new_branch=b2 at master.2")
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


    def test10_normal_sqlite(self):
        delete_file("test4.db")
        conn1 = sqlite3.connect('test4.db')
        conn2 = sqlite3.connect('test4.db')
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
