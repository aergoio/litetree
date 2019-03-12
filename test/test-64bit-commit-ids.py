#
# Copyright defined in LICENSE.txt
#
import unittest
import json
import os
import platform
import lmdb
import varint

if platform.system() == "Darwin":
    import pysqlite2.dbapi2 as sqlite3
else:
    import sqlite3

sqlite_version = "3.27.2"

if sqlite3.sqlite_version != sqlite_version:
    print "wrong SQLite version. expected: " + sqlite_version + " found: " + sqlite3.sqlite_version
    import sys
    sys.exit(1)

def delete_file(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)

v64bit_increment = 0xFFFFFFFE

class Test64bitCommitIds(unittest.TestCase):

    def test01_create_database(self):
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

        conn.close()


    def test02_replace_by_64bit_commit_ids(self):

        env = lmdb.open('test.db', subdir=False, max_dbs=1024)

        pages_db = [None]  # the first element (0) stores None
        maxpg_db = [None]

        with env.begin(buffers=True) as txn:

            value = txn.get('last_branch_id')
            num_branches = varint.decode(value)[0]
            self.assertEqual(num_branches, 2)

            for branch_id in range(1, num_branches + 1):
                pages_db.append(env.open_db('b' + str(branch_id) + '-pages'))
                maxpg_db.append(env.open_db('b' + str(branch_id) + '-maxpage'))
                self.assertEqual(len(pages_db) - 1, branch_id)
                self.assertEqual(len(maxpg_db) - 1, branch_id)

        with env.begin(write=True, buffers=True) as txn:

            value = txn.get('b1.name')
            self.assertEqual(bytes(value).decode("utf-8"), "master\x00")

            value = txn.get('b2.name')
            self.assertEqual(bytes(value).decode("utf-8"), "test\x00")

            for branch_id in range(1, num_branches + 1):
                prefix = 'b' + str(branch_id)

                key = prefix + '.last_commit'
                value = txn.get(key)
                last_commit = varint.decode(value)[0]
                last_commit += v64bit_increment
                value = varint.encode(last_commit)
                txn.put(key, value)

                key = prefix + '.source_commit'
                value = txn.get(key)
                source_commit = varint.decode(value)[0]
                if source_commit > 0:
                    source_commit += v64bit_increment
                    value = varint.encode(source_commit)
                    txn.put(key, value)

                # iterate all the keys from the sub-db
                dbx = pages_db[branch_id]
                for key, value in txn.cursor(db=dbx):
                    res = varint.decode(key)
                    pgno = res[0]
                    size1 = res[1]
                    res = varint.decode(key[size1:len(key)])
                    commit = res[0]
                    size2 = res[1]
                    if commit < v64bit_increment:
                        commit += v64bit_increment
                        key2 = varint.encode(pgno) + varint.encode(commit)
                        txn.put(key2, value, db=dbx)
                        txn.delete(key, db=dbx)

        env.close()


    def test03_64bit_database(self):
        conn = sqlite3.connect('file:test.db?branches=on')
        c = conn.cursor()

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

        c.execute("pragma new_branch=sub-test1 at test." + str(v64bit_increment + 2))
        c.execute("pragma new_branch=sub-test2 at test." + str(v64bit_increment + 3))
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

        c.execute("pragma branch=master." + str(v64bit_increment + 3))
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master." + str(v64bit_increment + 3))

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",)])

        c.execute("pragma branch=master." + str(v64bit_increment + 4))
        c.execute("pragma branch")
        self.assertEqual(c.fetchone()[0], "master." + str(v64bit_increment + 4))

        c.execute("select * from t1")
        self.assertListEqual(c.fetchall(), [("first",),("second",),("third",)])

        conn.close()


    def test04_branch_info(self):
        conn = sqlite3.connect('file:test.db?branches=on')
        c = conn.cursor()

        c.execute("pragma journal_mode")
        self.assertEqual(c.fetchone()[0], "branches")

        c.execute("pragma branch_info(master)")
        obj = json.loads(c.fetchone()[0])
        self.assertEqual(obj["total_commits"], v64bit_increment + 5)

        c.execute("pragma branch_info(test)")
        obj = json.loads(c.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], v64bit_increment + 2)
        self.assertEqual(obj["total_commits"], v64bit_increment + 3)

        c.execute("pragma branch_info('sub-test1')")
        obj = json.loads(c.fetchone()[0])
        self.assertEqual(obj["source_branch"], "master")
        self.assertEqual(obj["source_commit"], v64bit_increment + 2)
        self.assertEqual(obj["total_commits"], v64bit_increment + 2)

        c.execute("pragma branch_info('sub-test2')")
        obj = json.loads(c.fetchone()[0])
        self.assertEqual(obj["source_branch"], "test")
        self.assertEqual(obj["source_commit"], v64bit_increment + 3)
        self.assertEqual(obj["total_commits"], v64bit_increment + 4)

        conn.close()


    @classmethod
    def tearDownClass(self):
        delete_file("test.db")
        delete_file("test.db-lock")


if __name__ == '__main__':
    unittest.main()
