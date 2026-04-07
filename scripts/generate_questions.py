#!/usr/bin/env python3
"""
generate_questions.py
Generate simple MCQ questions from a UD SQLite database.

Question templates included:
 - POS identification: "ما فئة الكلام للكلمة '...' في الجملة؟"
 - Case identification (when FEATS contains Case): "ما حالة الإعراب للكلمة '...'؟"

Output: JSON array of questions.
"""
import argparse
import sqlite3
import json
import random
from collections import Counter


COMMON_POS = ['NOUN','VERB','ADJ','ADV','PRON','PROPN','ADP','NUM','DET','AUX']


def load_tokens(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT t.id,t.sentence_id,t.token_index,t.form,t.lemma,t.upos,t.feats,s.text FROM tokens t JOIN sentences s ON s.id=t.sentence_id')
    rows = cur.fetchall()
    conn.close()
    tokens = []
    for r in rows:
        tid, sid, idx, form, lemma, upos, feats_text, sent_text = r
        try:
            feats = json.loads(feats_text) if feats_text else {}
        except Exception:
            feats = {}
        tokens.append({'tid':tid,'sid':sid,'index':idx,'form':form,'lemma':lemma,'upos':upos,'feats':feats,'sent':sent_text})
    return tokens


def make_pos_question(token, pos_types):
    form = token['form']
    sent = token['sent']
    correct = token['upos'] or 'X'
    choices = [correct]
    others = [p for p in pos_types if p!=correct]
    random.shuffle(others)
    while len(choices)<4 and others:
        choices.append(others.pop())
    random.shuffle(choices)
    correct_index = choices.index(correct)
    q = f"ما فئة الكلام للكلمة «{form}» في الجملة: «{sent}»؟"
    explain = f"التصنيف في بيانات UD: {correct}"
    return {'q':q,'options':choices,'correct':correct_index,'explain':explain}


def make_case_question(token):
    form = token['form']
    sent = token['sent']
    feats = token['feats']
    case = feats.get('Case')
    if not case: return None
    choices = [case]
    distractors = ['Nom','Acc','Gen','None']
    for d in distractors:
        if d not in choices:
            choices.append(d)
        if len(choices)>=4: break
    random.shuffle(choices)
    correct_index = choices.index(case)
    q = f"ما حالة الإعراب (Case) للكلمة «{form}» في الجملة: «{sent}»؟"
    explain = f"المعلومة من بيانات UD: Case={case}"
    return {'q':q,'options':choices,'correct':correct_index,'explain':explain}


def generate(db_path, out_path, n=100):
    tokens = load_tokens(db_path)
    pos_counts = Counter([t['upos'] for t in tokens if t['upos']])
    # get candidate POS types
    pos_types = list({p for p in COMMON_POS if p in pos_counts} | set([p for p in pos_counts]))
    random.shuffle(tokens)
    questions = []
    for t in tokens:
        if not t['form'] or t['form'].strip()=='' or t['upos'] in (None,'PUNCT'):
            continue
        if len(questions)>=n: break
        # prefer POS questions
        q = make_pos_question(t, pos_types)
        questions.append(q)
        # also add case question if available
        cq = make_case_question(t)
        if cq and len(questions)<n:
            questions.append(cq)
    with open(out_path,'w',encoding='utf-8') as f:
        json.dump({'source_db':db_path,'count':len(questions),'questions':questions}, f, ensure_ascii=False, indent=2)
    print('Wrote', out_path, 'questions:', len(questions))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True, help='SQLite db produced by parse_conllu_to_sqlite.py')
    p.add_argument('--out', default='../data/ud_questions.json', help='Output JSON file')
    p.add_argument('--n', type=int, default=100, help='Number of questions to generate')
    args = p.parse_args()
    dbp = args.db
    outp = outp = args.out
    import os
    outp = os.path.abspath(os.path.join(os.path.dirname(__file__), outp))
    dbp = os.path.abspath(dbp)
    generate(dbp, outp, args.n)


if __name__ == '__main__':
    main()
