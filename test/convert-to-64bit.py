#
# Copyright defined in LICENSE.txt
#
import os
import sys
import lmdb
import struct
import varint


def delete_file(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)


def convert_db(filename1):

    if not os.path.exists(filename1):
        print 'the file does not exist'
        quit()

    filename2 = filename1 + '-converted'
    delete_file(filename2)
    print 'converting', filename, 'to', filename2, '...'

    env1 = lmdb.open(filename1, subdir=False, max_dbs=1024)
    env2 = lmdb.open(filename2, subdir=False, max_dbs=1024)

    pages_db1 = [None]  # the first element (0) stores None
    maxpg_db1 = [None]

    pages_db2 = [None]  # the first element (0) stores None
    maxpg_db2 = [None]

    with env1.begin(buffers=True) as txn1:

        with env2.begin(buffers=True) as txn2:

            value = txn1.get('last_branch_id')
            num_branches = struct.unpack('i', value)[0]
            print 'branches:', num_branches

            for branch_id in range(1, num_branches + 1):
                dbname = 'b' + str(branch_id) + '-pages'
                pages_db1.append(env1.open_db(dbname))
                pages_db2.append(env2.open_db(dbname))
                dbname = 'b' + str(branch_id) + '-maxpage'
                maxpg_db1.append(env1.open_db(dbname, integerkey=True))
                maxpg_db2.append(env2.open_db(dbname))


    with env1.begin(buffers=True) as txn1:

        with env2.begin(write=True, buffers=True) as txn2:

            txn2.put('last_branch_id', varint.encode(num_branches))

            value = txn1.get('change_counter')
            value = struct.unpack('i', value)[0]
            value = varint.encode(value)
            txn2.put('change_counter', value)

            for branch_id in range(1, num_branches + 1):
                prefix = 'b' + str(branch_id)

                key = prefix + '.name'
                name = txn1.get(key)
                print 'processing branch:', name
                txn2.put(key, name)

                key = prefix + '.visible'
                value = txn1.get(key)
                value = struct.unpack('i', value)[0]
                value = varint.encode(value)
                txn2.put(key, value)

                key = prefix + '.source_branch'
                value = txn1.get(key)
                value = struct.unpack('i', value)[0]
                value = varint.encode(value)
                txn2.put(key, value)

                key = prefix + '.source_commit'
                value = txn1.get(key)
                value = struct.unpack('i', value)[0]
                value = varint.encode(value)
                txn2.put(key, value)

                key = prefix + '.last_commit'
                value = txn1.get(key)
                value = struct.unpack('i', value)[0]
                value = varint.encode(value)
                txn2.put(key, value)

                # iterate all the keys from the sub-db
                db1 = pages_db1[branch_id]
                db2 = pages_db2[branch_id]
                for key, value in txn1.cursor(db=db1):
                    # read the key
                    pgno = struct.unpack('>i', key[0:4])[0]
                    commit = struct.unpack('>i', key[4:8] )[0]
                    print 'page', pgno, 'commit', commit
                    # write the new key
                    key2 = varint.encode(pgno) + varint.encode(commit)
                    txn2.put(key2, value, db=db2)

                # iterate all the keys from the sub-db
                db1 = maxpg_db1[branch_id]
                db2 = maxpg_db2[branch_id]
                for key, value in txn1.cursor(db=db1):
                    # read the key
                    commit = struct.unpack('i', key)[0]
                    print 'commit', commit
                    # write the new key
                    key2 = varint.encode(commit)
                    txn2.put(key2, value, db=db2)

    env1.close()
    env2.close()

    print 'done. you can open it with the command: sqlite3 "file:' + filename2 + '?branches=on"'



if len(sys.argv) == 1:
    print 'usage: python', sys.argv[0], '<db_file>'
    quit()

filename = sys.argv[1]

convert_db(filename)
