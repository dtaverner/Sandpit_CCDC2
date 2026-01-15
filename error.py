#### DRAFT README ###
# This pipeline iterates over entries in the CSD. First it extracts an entry's SMILES string, RDKit then attempts to parse and sanitise 
# the SMILES. If parsing fails, parsing without sanitisation is attempted to diagnose the cause of parsing error. Results are
# classified into diagnostic error categories. Results are written to a SQLite database (csd_results_complete.sqlite) with one row per
# CSD entry and columns "Identifier"; "category (parse outcome: success, empty_smiles, valence, kekulise)"; "truncated RDKit diagnostic error message";
# "processed_at: UTC timestamp". 
# The pipeline uses multiprocessing to distribute SMILES parsing across multiple CPU cores and worker processes are restarted periodically.
# # This script was developed with assistance from ChatGPT (OpenAI) Oxford University Edu Account, including code structure, logic, and documentation.
 


#!/usr/bin/env python3
"""
csd_fast_classifier.py
Classifier that writes results to SQLite in batches.

Usage:
    python csd_fast_classifier.py
Tweak N_PROCS, CHUNKSIZE, BATCH_INSERT to match your machine.
"""
import sqlite3
import time
import traceback
import sys
from datetime import datetime
import multiprocessing as mp
import os
from ccdc import io
from rdkit import Chem
from rdkit import RDLogger

# Supress console warnings from RDKit
RDLogger.logger().setLevel(RDLogger.CRITICAL)

# ---------- classify function ----------
def classify_smiles(smiles):
    '''When RDKit fails to read this SMILES, where is it failing and why'''
    if not smiles:
        return "empty_smiles", "empty or missing SMILES" # Rejection for empty input
    mol = Chem.MolFromSmiles(smiles) # Parse and sanitise the Smiles
    if mol is not None:
        return "success", "parsed_and_sanitized"  # mol returns None when unable to be parsed
    
    # If fails (mol returns None), try parsing without sanitisation.
    try:
        mol = Chem.MolFromSmiles(smiles, sanitize=False) # RDKit try and parse without sanitising
    # If parsing itself fails, return 'parse_exception'
    except Exception as e: 
        return "parse_exception", str(e)
    # If mol returns none despite no sanitisation, RDKit check valence, aromaticity, kekularisation, ring closure consistency
    # Determines chemical acceptability
    if mol is None:
        return "none_returned", "MolFromSmiles returned None (sanitize=False)"
    try:
        Chem.SanitizeMol(mol)
        return "success_after_fallback", "parsed_with_sanitize_false_then_sanitized"
    except Exception as e:
        msg = str(e).lower()
        # Create categories of error classes for Valency, kekulize, other sanitise errors
        if "valence" in msg:
            return "valence", str(e)
        if "kekul" in msg:
            return "kekulize", str(e)
        return "other_sanitize_error", str(e)

# ---------- worker setup ----------
def worker_init():
    # silence RDKit console errors again in each worker process (multiple cores)
    RDLogger.logger().setLevel(RDLogger.CRITICAL)

def worker_task(pair):
    '''Classify an identifier, smiles pair by success or error group'''
    ident, smiles = pair
    # Classify each pair by success or error 
    try:
        cat, msg = classify_smiles(smiles)
    # If there is a problem with classify_smiles or corrupted SMILES string, mark as 
    # 'worker_exception and do not crash the worker
    except Exception as e:
        cat, msg = "worker_exception", f"{type(e).__name__}: {e}"
    # Ensures msg is always a string, avoiding None to SQLite
    if msg is None:
        msg = ""
    # Return truncated and simple error messages
    return ident, cat, (msg[:1000] if len(msg) > 1000 else msg)

# ---------- DB helpers ----------
def init_db(path):
    '''Create and configure the SQLite database'''
    # Open or create SQLite file at path
    con = sqlite3.connect(path, timeout=30, isolation_level=None)  # autocommit off handled manually
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        identifier TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        message TEXT,
        processed_at TEXT NOT NULL
    )""")
    con.commit()
    # Return live database connection for use in the main process.
    return con

def batch_insert(cur, rows):
    # rows: list of (identifier, category, message, processed_at)
    cur.executemany("INSERT OR IGNORE INTO results (identifier, category, message, processed_at) VALUES (?, ?, ?, ?)", rows)

# ---------- tasks generator ----------
def tasks_generator(max_entries=None, skip_set=None):
    '''Iterate through CSD and yield identifier,smiles pairs for workers'''
    reader = io.EntryReader("CSD")
    for i, entry in enumerate(reader):
        if max_entries and i >= max_entries:
            break
        ident = getattr(entry, "identifier", None)
        if skip_set and ident in skip_set:
            continue
        smiles = None
        try:
            mol = entry.molecule
            smiles = mol.smiles if mol and getattr(mol, "smiles", None) else None
        except Exception:
            # if reading entry fails, send a row with None SMILES and let worker classify
            smiles = None
        yield ident, smiles

# ---------- main ----------
def main(
    DB_PATH="csd_results.sqlite",
    N_PROCS=None,
    CHUNKSIZE=50,
    BATCH_INSERT=1000,
    MAX_ENTRIES=None,
    MAxtasksperchild=500,
):
    if N_PROCS is None:
        # default to number of physical cores (best practice)
        try:
            import psutil
            N_PROCS = psutil.cpu_count(logical=False) or max(1, mp.cpu_count()//2)
        except Exception:
            N_PROCS = max(1, mp.cpu_count()//2)

    print(f"Starting with N_PROCS={N_PROCS}, chunksize={CHUNKSIZE}, batch_insert={BATCH_INSERT}", flush=True)
    # Initialise SQLite database
    con = init_db(DB_PATH)
    cur = con.cursor()

    # optional resume: load processed ids into set if small enough
    processed_set = None
    cur.execute("SELECT COUNT(1) FROM results")
    processed_count = cur.fetchone()[0]
    if processed_count > 0 and processed_count <= 3_000_000:
        print(f"Resuming: {processed_count} already processed; loading into skip set...", flush=True)
        cur.execute("SELECT identifier FROM results")
        processed_set = set(r[0] for r in cur.fetchall())
        print("Loaded skip set.", flush=True)

    #Create multiprocessing parallelisation for RDKit-safe worker processes
    ctx = mp.get_context("spawn")

    # Worker pool: initialiser silences RDKit logging per worker. Maxtaskperchild prevents memory/resource leakage over long runs
    pool = ctx.Pool(processes=N_PROCS, initializer=worker_init, maxtasksperchild=MAxtasksperchild)

    #Buffers and counters for batching and progress tracking
    rows_to_insert = []
    total_seen = 0
    total_inserted = 0
    t0 = time.time()

    try:
        # Generate (identifier,smiles) tasks from the CSD
        it = tasks_generator(max_entries=MAX_ENTRIES, skip_set=processed_set)
        for ident, cat, msg in pool.imap_unordered(worker_task, it, chunksize=CHUNKSIZE):
            total_seen += 1
            rows_to_insert.append((ident, cat, msg, datetime.utcnow().isoformat()))

            #Once the number of rows = batch size, write to SQlite in one transaction
            if len(rows_to_insert) >= BATCH_INSERT:
                try:
                    cur.execute("BEGIN")
                    batch_insert(cur, rows_to_insert)
                    cur.execute("COMMIT")
                    total_inserted += len(rows_to_insert)
                    rows_to_insert = []
                except Exception:
                    try:
                        cur.execute("ROLLBACK")
                    except Exception:
                        pass
                    traceback.print_exc()
                    # if inserting entire batch of rows into the database fails, fall back to attempt inserting rows one-by-one
                    for r in rows_to_insert:
                        try:
                            cur.execute("BEGIN")
                            cur.execute("INSERT OR IGNORE INTO results (identifier,category,message,processed_at) VALUES (?,?,?,?)", r)
                            cur.execute("COMMIT")
                            total_inserted += 1
                        except Exception:
                            try:
                                cur.execute("ROLLBACK")
                            except Exception:
                                pass
                    rows_to_insert = []

            # Periodic progress reporting 
            if total_seen % 1000 == 0:
                elapsed = time.time() - t0
                rate = total_seen / elapsed if elapsed > 0 else 0.0
                print(f"[{datetime.utcnow().isoformat()}] Seen {total_seen} (inserted {total_inserted}) — {rate:.1f} /s", flush=True)

    # Shutdown on Ctrl+C
    except KeyboardInterrupt:
        print("KeyboardInterrupt — terminating pool...", flush=True)
        pool.terminate()
        pool.join()
    # On any other unhandled exception: terminate workers and re-raise    
    except Exception:
        print("Unhandled exception in main loop:", file=sys.stderr)
        traceback.print_exc()
        pool.terminate()
        pool.join()
        raise

    # Normal completion: close worker pool 
    else:
        pool.close()
        pool.join()
    finally:
        # final flush of any remaining buffered rows
        if rows_to_insert:
            try:
                cur.execute("BEGIN")
                batch_insert(cur, rows_to_insert)
                cur.execute("COMMIT")
                total_inserted += len(rows_to_insert)
            except Exception:
                try:
                    cur.execute("ROLLBACK")
                except Exception:
                    pass
                # try one-by-one as fallback
                for r in rows_to_insert:
                    try:
                        cur.execute("BEGIN")
                        cur.execute("INSERT OR IGNORE INTO results (identifier,category,message,processed_at) VALUES (?,?,?,?)", r)
                        cur.execute("COMMIT")
                        total_inserted += 1
                    except Exception:
                        try:
                            cur.execute("ROLLBACK")
                        except Exception:
                            pass

        # Final commit and cleanup
        con.commit()
        con.close()
        elapsed = time.time() - t0
        print(f"Finished. Seen {total_seen}, inserted {total_inserted}. Elapsed: {elapsed:.1f}s — {total_seen/elapsed if elapsed>0 else 0:.1f}/s", flush=True)


# Entry point: run the pipeline only when the file is executed directly in terminal, and start with specific runtime parameters.
if __name__ == "__main__":
    main(
        DB_PATH="csd_results_complete.sqlite",
        N_PROCS=8,
        CHUNKSIZE=50,
        BATCH_INSERT=2000,
        MAX_ENTRIES=None,
        MAxtasksperchild=400,
    )



