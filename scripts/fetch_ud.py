#!/usr/bin/env python3
"""
fetch_ud.py
Simple helper to download a UD treebank CoNLL-U file.

Usage:
  python fetch_ud.py --url <RAW_CONLLU_URL> --out data/ar_ud.conllu

By default it downloads UD_Arabic-PADT train file from UniversalDependencies GitHub.
"""
import argparse
import os
import requests


DEFAULT_URL = 'https://raw.githubusercontent.com/UniversalDependencies/UD_Arabic-PADT/master/ar_padt-ud-train.conllu'


def download(url, out_path, force=False):
    if os.path.exists(out_path) and not force:
        print(f"File already exists: {out_path} (use --force to overwrite)")
        return out_path
    r = requests.get(url, stream=True)
    r.raise_for_status()
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print(f"Downloaded: {out_path}")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default=DEFAULT_URL, help='Raw URL to .conllu file')
    p.add_argument('--out', default='../data/ar_ud_train.conllu', help='Output path for .conllu')
    p.add_argument('--force', action='store_true')
    args = p.parse_args()
    out = os.path.abspath(os.path.join(os.path.dirname(__file__), args.out))
    download(args.url, out, args.force)


if __name__ == '__main__':
    main()
