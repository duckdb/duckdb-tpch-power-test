# 2024-08-21, hannes@duckdblabs.com

import threading
import duckdb
import psycopg2
import pathlib
import tempfile
import time
import functools
import operator
import os
import shutil
import psutil
import datetime
import subprocess

scale_factor = 1

datadir = f'/Users/hannes/source/tpch/tpch_tools_3.0.1/dbgen/invariant-sf{scale_factor}'
db_file = f'tpch-invariant-sf{scale_factor}.duckdb'

use_parquet = False
reader = 'read_csv'
ext = ''
if use_parquet:
	ext = '.parquet'
	reader = 'read_parquet'

def export(dir):
	con.sql(f"COPY (SELECT * FROM lineitem ORDER BY l_orderkey, l_linenumber) TO '{dir}/lineitem.tbl' (FORMAT CSV, DELIMITER '|', HEADER FALSE)")
	con.sql(f"COPY (SELECT * FROM orders ORDER BY o_orderkey) TO '{dir}/order.tbl' (FORMAT CSV, DELIMITER '|', HEADER FALSE)")

#db = psycopg2.connect()
db = duckdb.connect(db_file)
con = db.cursor()

con.execute("select count(*) from information_schema.tables where lower(table_name)='lineitem'")
lineitem_exists = con.fetchone()[0] == 1

#if not os.path.exists(db_file):
if not lineitem_exists:
	print(f"begin loading into {db_file}")
	#con = duckdb.connect(db_file)
	# con.begin()
	schema = pathlib.Path('schema.sql').read_text()
	con.execute(schema)
	for t in ['customer', 'lineitem', 'nation', 'orders', 'part', 'partsupp', 'region', 'supplier']:
		con.execute(f"COPY {t} FROM '{datadir}/{t}.tbl' (FORMAT CSV, HEADER FALSE, DELIMITER '|')")
	con.execute("CREATE TABLE refresh(last_refresh INTEGER)")
	con.execute("INSERT INTO refresh VALUES (0)")
	export("/Users/hannes/source/tpch/reference-tables")
	db.commit()
	#con.commit()

else:
	print(f"using existing database {db_file}")
	#con = duckdb.connect(db_file)


def refresh(con, n):	
	con.execute("BEGIN TRANSACTION")
	# print(con.execute("select count(*) from orders").fetchone()[0])
	# print(con.execute("select count(*) from lineitem").fetchone()[0])

	lineitem = f"{datadir}/lineitem.tbl.u{n}{ext}"
	orders = f"{datadir}/orders.tbl.u{n}{ext}"
	con.execute(f"COPY lineitem FROM '{lineitem}' (FORMAT CSV, HEADER FALSE, DELIMITER '|')")
	con.execute(f"COPY orders FROM '{orders}' (FORMAT CSV, HEADER FALSE, DELIMITER '|')")
	delete = f"{datadir}/delete.{n}{ext}"
	con.execute(f"CREATE TEMPORARY TABLE deletes (pk INTEGER, gunk varchar(1))")
	con.execute(f"COPY deletes FROM '{delete}' (FORMAT CSV, HEADER FALSE, DELIMITER '|')")

	con.execute("DELETE FROM orders WHERE o_orderkey IN (SELECT pk FROM deletes)")
	con.execute("DELETE FROM lineitem WHERE l_orderkey IN (SELECT pk FROM deletes)")
	con.execute("DROP TABLE deletes")
	con.execute("DELETE FROM refresh")
	con.execute(f"INSERT INTO refresh VALUES ({n})")
	con.execute("COMMIT")


while True:
	con.execute("SELECT last_refresh FROM refresh")
	next_refresh = con.fetchone()[0] + 1
	print(next_refresh)
	if (next_refresh > 3999):
		print("checking invariant")
		diffdir = "invariant-checking"
		export(diffdir)
		res = subprocess.call(f'cmp reference-tables/order.tbl {diffdir}/order.tbl', shell=True)
		if res > 0:
			raise ValueError("Found diff in orders!")
		res = subprocess.call(f'cmp reference-tables/lineitem.tbl {diffdir}/lineitem.tbl', shell=True)
		if res > 0:
			raise ValueError("Found diff in lineitem!")
		next_refresh = 1	
	refresh(con, next_refresh)