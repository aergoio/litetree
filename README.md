<a href="https://aergo.io"><img src="http://litesync.io/litetree/aergo-presents-black-round.svg" width="20%"></a> [![Build Status](https://travis-ci.org/aergoio/litetree.svg?branch=master)](https://travis-ci.org/aergoio/litetree) [![Build Status](https://ci.appveyor.com/api/projects/status/github/aergoio/litetree?branch=master&svg=true)](https://ci.appveyor.com/project/kroggen/litetree)

# LiteTree: SQLite with Branches

![](http://litesync.io/litetree/graph-litetree.png)

Imagine being able to have many connections to the same database, each one reading a separate branch or commit at the same time. Or even writing to separate branches.

This is possible with **LiteTree**. It is a modification of the SQLite engine to support branching, like git!

Database branching is a very useful tool for blockchain implementations and LiteTree will be at the core of [Aergo](https://github.com/aergoio/aergo).

This is how it works:

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
>
> from test branch


We can move to the master branch:

```
PRAGMA branch=master
```

And executing the same SELECT command (but now in the master branch) it will return:

> first
>
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

## Supported commands

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
- Truncating a branch at a specific commit:
	```
	PRAGMA branch_truncate(<name>.<commit>)
	```
- Displaying the tree structure:
	```
	PRAGMA branch_tree
	```
- Retrieving the branch info:
	```
	PRAGMA branch_info(<name>)
	```
- Showing the commit and SQL log/history for a branch:
	```
	PRAGMA branch_log(<name>)
	```
- Showing the row-level diff between 2 branches or commits:
	```
	PRAGMA branch_diff <from_branch>[.<commit>] <to_branch>[.<commit>]
	```
	The command returns a single JSON document describing the set of
	inserts, deletes and updates that turn the `from` point into the
	`to` point:
	```json
	{
	  "from": "master.2",
	  "to":   "dev.3",
	  "tables": {
	    "t1": {
	      "columns": ["id", "name", "value"],
	      "pk":      ["id"],
	      "inserts": [ [3, "charlie", 30] ],
	      "deletes": [ [2, "bob", 20] ],
	      "updates": [
	        {"old": [1, "alice", 10], "new": [1, "alice", 99]}
	      ]
	    }
	  }
	}
	```
	Each row is emitted as a positional array aligned with `columns`.
	NULLs become JSON `null`, numbers stay numbers, text becomes a
	string and blobs are wrapped as `{"blob":"<hex>"}`. For updates,
	both `old` and `new` carry the full row image (unchanged columns
	are filled in from the baseline table), so consumers can render
	the complete before/after rows without extra lookups.

	Schema changes between the two points are reported as extra markers
	on the affected table entry, so `branch_diff` never fails because
	of a schema difference:

	- A table that exists only on the `to` side gets `"created": true`
	  alongside its `columns`, `pk`, and every row as `inserts`.
	- A table that exists only on the `from` side gets `"dropped": true`
	  alongside its `columns`, `pk`, and every row as `deletes`.
	- A table that exists on both sides but with a different `CREATE`
	  statement is reported with `"schema_mismatch": true` together
	  with a `schema_diff` object describing the column-level changes.
	  The normal `columns` / `pk` / `inserts` / `deletes` / `updates`
	  fields are still emitted: `columns` is the union of both sides
	  (from-side order first, then any to-only columns appended), and
	  every row array renders `null` at positions the side doesn't
	  have. Row-level diff is computed only when the PK columns are
	  identical on both sides.

	`schema_diff` has three lists:

	- `added`: columns only on the `to` side, each `{"name":..., "type":...}`
	- `removed`: columns only on the `from` side, same shape
	- `modified`: same column name on both sides with a different type,
	  `notnull`, `dflt_value`, or primary-key flag. Only the attributes
	  that actually changed are reported, each as `{"from":..., "to":...}`.

	Example (column added, column removed, column type changed):
	```json
	"t1": {
	  "schema_mismatch": true,
	  "schema_diff": {
	    "added":    [{"name": "extra",   "type": "TEXT"}],
	    "removed":  [{"name": "old_col", "type": "TEXT"}],
	    "modified": [{"name": "value",
	                  "type": {"from": "INTEGER", "to": "TEXT"}}]
	  },
	  "columns": ["id", "name", "value", "old_col", "extra"],
	  "pk":      ["id"],
	  "inserts": [[4, "dave", "40", null, null]],
	  "deletes": [[3, "charlie", 30, null, null]],
	  "updates": [
	    {"old": [1, "alice", 10,  "legacy", null],
	     "new": [1, "alice", "10", null,   "x"]}
	  ]
	}
	```

	Renames of tables or columns are not detected — a rename shows up
	as a `dropped` + `created` pair (for a table rename) or as
	`removed` + `added` inside `schema_diff` (for a column rename).
- Rebasing commits onto a new base (SQL-replay):
	```
	PRAGMA branch_rebase [--check|--force] [{to_rebase}] {new_base} [{new_branch}]
	```
	Where `{to_rebase}` is either a branch name, a single commit
	`branch.commit`, or a commit range `branch.start-end`. If omitted,
	the current branch is rebased. `{new_base}` is the target point
	(a branch tip or `branch.commit`). If `{new_branch}` is given, the
	rebased commits are written into that newly-created branch;
	otherwise the commits are appended to the `{new_base}` branch
	(which must therefore be at its tip). `--check` performs the
	replay against a throw-away scratch branch and discards it.
	`--force` keeps going on SQL errors instead of aborting.

	Rebase re-executes the original SQL commands, so expressions like
	`UPDATE t SET x=x+1` are re-evaluated against the new base state.
	Two branches that each ran `x=x+1` will therefore be summed —
	this is the main reason to prefer rebase over a merge for that
	kind of change.

#### Not yet available

Some of these commands are being developed:

- Modifying a commit:
	```
	PRAGMA branch_log [--set|--add|--del] <name> <sql commands>
	```
- [Save metadata to each branch and/or commit](https://github.com/aergoio/litetree/wiki/Storing-metadata)
- [Merging 2 branches](https://github.com/aergoio/litetree/wiki/Merging-branches)

And maybe these extended features could be supported:

- Access control by branch

Check the roadmap on our [wiki](https://github.com/aergoio/litetree/wiki). Feature requests and suggestions are welcome.


## Technologies

We can use LiteTree with big databases (many gigabytes). There is no data copying when a new branch is created. When a new transaction is commited only the modified database pages are copied.

LiteTree is implemented storing the SQLite db pages on LMDB.

The data is not compressed, and each db page is stored on just one disk sector (4096 bytes by default). This is achieved by reserving some bytes at each SQLite db page so it can fit into one LMDB overflow page, that can hold 4080 (4096 - 16) bytes.

## Performance

LiteTree is way faster than normal SQLite (journal mode) with comparable performance to WAL mode.

Here are the some results:

##### Linux

```
writing:
--------
normal   = 22.8921730518 seconds
wal      = 10.7780168056 seconds
mmap     = 10.4009709358 seconds
litetree = 10.8633410931 seconds

reading:
--------
normal   = 0.817955970764 seconds
wal      = 0.660045146942 seconds
mmap     = 0.592491865158 seconds
litetree = 0.619393110275 seconds
```

##### MacOSX

```
writing:
--------
normal   = 1.9102909565 seconds
wal      = 1.30300784111 seconds
mmap     = 1.21677088737 seconds
litetree = 0.988132953644 seconds

reading:
--------
normal   = 0.999235868454 seconds
wal      = 0.776713132858 seconds
mmap     = 0.653935909271 seconds
litetree = 0.714652061462 seconds
```

##### Windows

```
writing:
--------
normal   = 68.0931215734 seconds
litetree = 39.239919979 seconds

reading:
--------
normal   = 0.012673914421 seconds
litetree = 0.00631055510799 seconds
```

You can make your own benchmark (after installing LiteTree) with this command:

```
make benchmark
```

## Current Limits

Number of branches: 1024 branches  (can be increased)

Number of commits per branch: 2^64 = 18,446,744,073,709,551,615 commits

Concurrent db connections to the same db: XXX readers

## Some Limitations

A database file created in one architecture cannot be used in another. This is a limitation of LMDB. We need to dump the database using `mdb_dump` and load it using `mdb_load`.

The db file cannot be opened by unmodified SQLite libraries.

Savepoints are not yet supported.


## How to use

LiteTree can be used in many programming languages via existing SQLite wrappers.

1. Update your app to open the database file using an URI containing the `branches` parameter, like this:
	```
	“file:data.db?branches=on”
	```

2. Make your app use this new library instead of the pre-installed SQLite library:

### On Linux

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


### On Mac OSX

 This can be achieved in these ways:

- Patching your wrapper or app to search for the library in the new path:

	```
	install_name_tool -change /old/path/to/libsqlite3.dylib /usr/local/lib/litetree/libsqlite3.dylib lib_or_app
	```

	You can check the old path with this command:

	```
	otool -L lib_or_app
	```

	This method can be used with all programming languages and wrappers as long as they are not protected by the OS.

	It it is protected then you will need to install a new copy of the wrapper, modify it and use it instead of the protected one.

- Using the `DYLD_LIBRARY_PATH` environment variable:

	```
	DYLD_LIBRARY_PATH=/usr/local/lib/litetree ./myapp
	```

	This can be used if the wrapper was linked to just the library name and does not contain any path.

	If it does not work we can patch the wrapper to not contain any path:

	```
	install_name_tool -change /old/path/to/libsqlite3.dylib libsqlite3.dylib lib_or_app
	```

	But if you are able to modify the wrapper with `install_name_tool` then the first method above may be better.

- Linking to the LiteTree library:

	```
	gcc myapp.c -L/usr/local/lib/litetree -lsqlite3
	```


### On Windows

Copy the modified SQLite library to the system folder.

- On 64 bit Windows:

	C:\Windows\System32 (if 64 bit DLL)

	C:\Windows\SysWOW64 (if 32 bit DLL)

- On 32 bit Windows:

	C:\Windows\System32


## Compiling and installing

### On Linux and Mac OSX

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

### On Windows

You can use these pre-compiled binaries: (can be outdated)

- [32 bit DLLs](http://litesync.io/litetree/litetree-binaries-win-x86.zip)
- [64 bit DLLs](http://litesync.io/litetree/litetree-binaries-win-x64.zip)

Or follow these steps:

1. Compile LMDB using [MinGW](https://github.com/kroggen/lmdb) or Visual Studio ([1](https://github.com/Ri0n/lmdb) or [2](https://github.com/htaox/lightningdb-win))

2. Compile LiteTree using MinGW or Visual Studio

3. Copy the libraries to the Windows System folder


## Running the Tests

The tests are written in Python using the [pysqlite](https://github.com/ghaering/pysqlite) wrapper.

On **MacOSX** we cannot use a modified SQLite library with the pre-installed system python due to the System Integrity Protection so we need to install another copy of pysqlite and link it to the LiteTree library:

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

## License

MIT

## Creator

Developed by Bernardo Ramos at

<a href="https://aergo.io"><img src="http://litesync.io/litetree/aergo-logo-black-slim.svg" width="30%"></a>
