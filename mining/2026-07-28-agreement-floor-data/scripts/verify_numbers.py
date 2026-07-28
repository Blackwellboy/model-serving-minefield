#!/usr/bin/env python3
"""Independent re-derivation of every number published in the agreement-floor note.
The extraction and arithmetic are re-implemented from scratch rather than
shared with the original scorer, so a bug in one would not reproduce in the other.
Run it with no arguments from anywhere; it resolves ../raw relative to itself."""
import json, os, re, math, itertools

S = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw")
IDENT = ["nodeA_srv1_pass1","nodeA_srv1_pass2","nodeA_srv2_pass1","nodeB_srv1_pass1"]
NOSPEC = ["nodeA_nospec_pass1","nodeA_nospec_pass2"]

def read(tag):
    out={}
    for line in open(f"{S}/{tag}.jsonl", encoding="utf-8"):
        r=json.loads(line); out[r["idx"]]=r
    return out

def pick(r):
    t=(r.get("content") or "").strip() or (r.get("reasoning_content") or "").strip()
    if not t: return None
    m=re.search(r"\b([ABCD])\b", t)
    if m: return m.group(1)
    return t[0].upper() if t[0].upper() in "ABCD" else None

D={t:read(t) for t in IDENT+NOSPEC}
def score(t): return sum(1 for r in D[t].values() if pick(r)==r["gold"])

print("CHECK 1 - run scores (claim: 513/512/516/514, range 512-516)")
sc={t:score(t) for t in IDENT}
for t in IDENT: print(f"   {t:20s} {sc[t]}/600 = {100*sc[t]/600:.2f}%")
print(f"   range {min(sc.values())}-{max(sc.values())}  -> claim 512-516: "
      f"{'MATCH' if (min(sc.values()),max(sc.values()))==(512,516) else 'MISMATCH'}")

print("\nCHECK 2 - six pairwise agreements + discordant counts")
tot_k=tot_n=0; rows=[]
for a,b in itertools.combinations(IDENT,2):
    idx=sorted(set(D[a])&set(D[b])); n=len(idx)
    k=sum(1 for i in idx if pick(D[a][i])==pick(D[b][i]))
    dis=[i for i in idx if pick(D[a][i])!=pick(D[b][i])]
    ap=sum(1 for i in dis if pick(D[a][i])==D[a][i]["gold"])
    bp=sum(1 for i in dis if pick(D[b][i])==D[b][i]["gold"])
    tot_k+=k; tot_n+=n
    rows.append((a,b,k,n,100*k/n,ap,bp,100*(sc[a]-sc[b])/n))
    print(f"   {a[:14]:14s} vs {b[:14]:14s} {k}/{n} = {100*k/n:.2f}%  discordant {ap}/{bp}  delta {100*(sc[a]-sc[b])/n:+.2f}")

print(f"\nCHECK 3 - pooled (claim 3513/3600 = 97.58%)")
print(f"   {tot_k}/{tot_n} = {100*tot_k/tot_n:.2f}%  -> "
      f"{'MATCH' if (tot_k,tot_n)==(3513,3600) and abs(100*tot_k/tot_n-97.58)<0.005 else 'MISMATCH'}")

print("\nCHECK 4 - discordant multiset (claim 7/6, 5/8, 6/7, 5/3 among the four cited)")
got=[(r[5],r[6]) for r in rows]
print(f"   all six observed: {got}")
claim=[(7,6),(5,8),(6,7),(5,3)]
print(f"   claimed four    : {claim}")
print(f"   all four present in observed: {'MATCH' if all(c in got for c in claim) else 'MISMATCH'}")

print("\nCHECK 5 - MTP-off arm (claim 98.17% vs within-process 97.33%)")
a,b=NOSPEC; idx=sorted(set(D[a])&set(D[b])); n=len(idx)
k=sum(1 for i in idx if pick(D[a][i])==pick(D[b][i]))
print(f"   nospec within-process {k}/{n} = {100*k/n:.2f}%   scores {score(a)}/{score(b)}"
      f"  delta {100*(score(a)-score(b))/n:+.2f}")
wp=[r for r in rows if r[0]=="nodeA_srv1_pass1" and r[1]=="nodeA_srv1_pass2"][0]
print(f"   MTP-on within-process {wp[2]}/{wp[3]} = {wp[4]:.2f}%")
print(f"   -> {'MATCH' if abs(100*k/n-98.17)<0.005 and abs(wp[4]-97.33)<0.005 else 'MISMATCH'}")

def wilson(k,n,z=1.96):
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d; return 100*(c-h),100*(c+h)
print(f"   CI nospec {wilson(k,n)[0]:.2f}-{wilson(k,n)[1]:.2f}  CI mtp-on {wilson(wp[2],wp[3])[0]:.2f}-{wilson(wp[2],wp[3])[1]:.2f}"
      f"  overlap: {'YES' if wilson(k,n)[0] < wilson(wp[2],wp[3])[1] else 'NO'}")

print("\nCHECK 6 - integrity: errors / unparsable / truncation, all six arms")
for t in IDENT+NOSPEC:
    n=len(D[t])
    print(f"   {t:20s} n={n} errors={sum(1 for r in D[t].values() if 'error' in r)} "
          f"unparsable={sum(1 for r in D[t].values() if pick(r) is None)} "
          f"truncated={sum(1 for r in D[t].values() if r.get('finish_reason')=='length')}")

print("\nCHECK 7 - cross-machine vs within-process structure")
cm=[r[4] for r in rows if ("nodeB" in r[0])!=("nodeB" in r[1])]
print(f"   cross-machine pairs: {[f'{x:.2f}' for x in cm]}")
print(f"   within-process pair: {wp[4]:.2f}")
print(f"   straddles (min<wp<max): {'YES' if min(cm) < wp[4] < max(cm) else 'NO'}")

print("\nCHECK 8 - max |score delta| among identical configs")
md=max(abs(r[7]) for r in rows)
print(f"   {md:.2f} pts (claim 0.67)  -> {'MATCH' if abs(md-0.67)<0.005 else 'MISMATCH'}")
