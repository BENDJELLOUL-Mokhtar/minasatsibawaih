#!/usr/bin/env python3
"""
parse_conllu_to_sqlite.py
Parse a CoNLL-U file and store sentences/tokens into a SQLite database.

Usage:
  python parse_conllu_to_sqlite.py --in data/ar_ud_train.conllu --out data/ud_ar.db

Tables:
  sentences(id INTEGER PRIMARY KEY, text TEXT)
  tokens(id INTEGER PRIMARY KEY, sentence_id INTEGER, token_index INTEGER, form TEXT, lemma TEXT, upos TEXT, xpos TEXT, feats TEXT, head INTEGER, deprel TEXT)
"""
import argparse
import os
import sqlite3
import json
from conllu import parse_incr


def init_db(db_path):
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS sentences (id INTEGER PRIMARY KEY, text TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sentence_id INTEGER,
        token_index INTEGER,
        form TEXT,
        lemma TEXT,
        upos TEXT,
        xpos TEXT,
        feats TEXT,
        head INTEGER,
        deprel TEXT
    )''')
    conn.commit()
    return conn


def parse_and_store(conllu_path, db_path):
    conn = init_db(db_path)
    cur = conn.cursor()
    with open(conllu_path, 'r', encoding='utf-8') as fh:
        for tokenlist in parse_incr(fh):
            sent_text = ' '.join([t['form'] for t in tokenlist if isinstance(t.get('form'), str)])
            cur.execute('INSERT INTO sentences (text) VALUES (?)', (sent_text,))
            sent_id = cur.lastrowid
            for tok in tokenlist:
                # skip multiword tokens (id like '1-2')
                tid = tok.get('id')
                if not isinstance(tid, int):
                    continue
                form = tok.get('form')
                lemma = tok.get('lemma')
                upos = tok.get('upostag') if tok.get('upostag') is not None else tok.get('upos')
                # conllu lib may provide 'upostag' or 'upos'
                xpos = tok.get('xpostag') or tok.get('xpos') or ''
                feats = tok.get('feats') or {}
                head = tok.get('head')
                deprel = tok.get('deprel')
                cur.execute('INSERT INTO tokens (sentence_id, token_index, form, lemma, upos, xpos, feats, head, deprel) VALUES (?,?,?,?,?,?,?,?,?)',
                            (sent_id, tid, form, lemma, upos, xpos, json.dumps(feats, ensure_ascii=False), head, deprel))
    conn.commit()
    conn.close()
    print('DB created at', db_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--in', dest='infile', required=True, help='Input CoNLL-U file')
    p.add_argument('--out', dest='outfile', default='../data/ud_ar.db', help='Output sqlite db path')
    args = p.parse_args()
    conllu_path = os.path.abspath(args.infile)
    out_db = os.path.abspath(os.path.join(os.path.dirname(__file__), args.outfile))
    parse_and_store(conllu_path, out_db)


if __name__ == '__main__':
    main()
