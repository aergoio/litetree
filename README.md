# LiteTree: SQLite with Branches

![](http://litesync.io/litetree/graph-litetree.png)

Imagine being able to have many connections to the same db, each one reading a separate branch or commit at the same time. Or even writing to separate branches.

This is possible with **LiteTree**. It is a modification of the SQLite engine to support branching.

Each database transaction is saved as a commit, and each commit has an incremental number. Let's consider an empty db in which we run this first SQL command:

```
CREATE TABLE t1 (name)
```

Now it will have the first commit (number 1) in the automatically created `master` branch:

![](http://litesync.io/litetree/graph-1-commit.png)

When we execute new transactions it will add new commits to the current branch:

```
INSERT INTO t1 VALUES ('first')
INSERT INTO t1 VALUES ('second')
```
Now we have 3 commits:

![](http://litesync.io/litetree/graph-3-commits.png)

To include many SQL commands in a single commit we must enclose them in `BEGIN` and `COMMIT`  commands.

We create new branches informing the source branch and commit number:

```
PRAGMA new_branch=test at master.2
```

After this command is executed the new branch is created but without any new data added to it. The database connection also moves to this new branch, having it as the current branch.

We can check the current branch with the command:

```
PRAGMA branch
```

In this case it will return: `test`

If we execute a SQL command on this db connection the commit will be saved in the connection's current branch:

```
INSERT INTO t1 VALUES ('from test branch')
```

Now the graph state will be:

![](http://litesync.io/litetree/graph-2-branches.png)

We can also read the database at this new branch:
```
SELECT * FROM t1
```

It will return these values:


> first
> from test branch


We can move to the master branch:

```
PRAGMA branch=master
```

And executing the same SELECT command (but now in the master branch) it will return:

> first
> second

Different content for the same table on separate branches.

Commits in separate branches have the same numbering based on the distance from the first commit:

![](http://litesync.io/litetree/graph-commit-numbers.png)

We can read the database in a previous point-in-time by moving to that commit, like this:

```
PRAGMA branch=master.2
```

At this point the table `t1` has a single row and if we do a SELECT it will return just `first`.

We cannot write to the database when we are in a defined commit, writing is only possible at the head of each branch. If you want to make modifications to some previous commit you must create a new branch that starts at that commit.

It is also possible to truncate a branch at a specific commit, rename a branch, delete it and retrieve branch info.

### Supported commands

- Selecting the active branch:
	```
	PRAGMA branch=<name>
	```
- Selecting a specific commit in a branch:
	```
	PRAGMA branch=<name>.<commit>
	```
- Retrieving the current/active branch:
	```
	PRAGMA branch
	```
- Listing the existing branches:
	```
	PRAGMA branches
	```
- Creating a new branch:
	```
	PRAGMA new_branch=<name> at <source>.<commit>
	```
- Deleting a branch:
	```
	PRAGMA del_branch(<name>)
	```
- Renaming a branch:
	```
	PRAGMA rename_branch <old_name> <new_name>
	```
- Retrieving the branch info:
	```
	PRAGMA branch_info(<name>)
	```
- Truncating a branch at a specific commit:
	```
	PRAGMA branch_truncate(<name>.<commit>)
	```

#### Not yet available:

These commands could be implemented if required:

- Showing the commit and SQL log/history for a branch:
	```
	PRAGMA branch_log(<name>)
	```
- Showing the diff between 2 branches or commits:
	```
	PRAGMA branch_diff <from_branch>[.<commit>] <to_branch>[.<commit>]
	```
- Displaying the tree structure in some format:
	```
	PRAGMA branch_tree
	```


### Technologies

We can use LiteTree with big databases (many gigabytes). There is no data copying when a new branch is created. When a new transaction is commited only the modified database pages are copied.

LiteTree is implemented storing the SQLite db pages on LMDB.

The data is not compressed, and each db page is stored on just one disk sector (4096 bytes by default). This is achieved by reserving some bytes at each SQLite db page so it can fit into one LMDB overflow page, that can hold 4080 (4096 - 16) bytes.

### Performance

To Do

### Current Limits

Number of branches: 1024 branches  (can be increased)

Number of commits per branch: 2^32 = 4,294,967,295 commits

- This value can be increased to 64 bits

Concurrent db connections to the same db: XXX readers

### Some Limitations

A database file created in one architecture cannot be used in another. This is a limitation of LMDB. We need to dump the database using `mdb_dump` and load it using `mdb_load`.

The db file cannot be opened by unmodified SQLite libraries.

Savepoints are not yet supported.


### How to use

LiteTree can be used in many programming languages via existing SQLite wrappers.

1. Update your app to open the database file using an URI containing the `branches` parameter, like this:
	```
	“file:data.db?branches=on”
	```

2. Make your app use this new library instead of the pre-installed SQLite library:

##### On Linux

 This can be achieved in 4 ways:

- Using the `LD_LIBRARY_PATH` environment variable:
	```
	LD_LIBRARY_PATH=/usr/local/lib/litetree ./myapp
	```
	This can be used with all programming languages and wrappers.

- Patching your wrapper or app to search for the library in the new path:
	```
	patchelf --set-rpath /usr/local/lib/litetree lib_or_app
	```

- Setting the `rpath` at the link time:
	```
	LIBPATH = /usr/local/lib/litetree
	gcc myapp.c -Wl,-rpath,$(LIBPATH) -L$(LIBPATH) -lsqlite3
	```
	You can use this if your app is linking directly to the LiteTree library.

- Replacing the pre-installed SQLite library on your system

	This can also be used with many programming languages. But use it with care because the native library may have been compiled with different directives.


##### On Windows

Copy the modified SQLite library to the system folder.

- On 64 bit Windows:

	C:\Windows\System32 (if 64 bit DLL)

	C:\Windows\SysWOW64 (if 32 bit DLL)

- On 32 bit Windows:

	C:\Windows\System32


### Compiling and installing

##### On Linux and Mac OSX

Install [LMDB](https://github.com/lmdb/lmdb) if not already installed:

```
git clone https://github.com/lmdb/lmdb
cd lmdb/libraries/liblmdb
make
sudo make install
```

Then install LiteTree:

```
git clone https://github.com/aergoio/litetree
cd litetree
make
sudo make install
```

##### On Windows

1. Compile the library using MinGW or Visual Studio

2. Copy the LiteTree library to the Windows System folder


### Running the Tests

The tests are written in Python using the [pysqlite](https://github.com/ghaering/pysqlite) wrapper.

On MacOSX we cannot use a modified SQLite library with the pre-installed system python due to the System Integrity Protection so we need to install another copy of pysqlite and link it to the LiteTree library:

```
git clone https://github.com/ghaering/pysqlite
cd pysqlite
echo "include_dirs=/usr/local/include" >> setup.cfg
echo "library_dirs=/usr/local/lib/litetree" >> setup.cfg
python setup.py build
sudo python setup.py install
```

To run the tests:

```
make test
```

### License

MIT

### Creator

Developed by Bernardo Ramos at Blocko Inc. ([blocko.io](http://blocko.io))

### Contact

bernardo AT blocko D0T io
