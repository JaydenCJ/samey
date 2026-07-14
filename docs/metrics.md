# samey metrics reference

This document defines every number samey reports, exactly as implemented in
v0.1.0. All metrics are computed offline, deterministically, and with the
standard library only.

## Records and tokens

An input corpus is a list of *records* (one generation output each; see the
README for input formats). Each record is tokenized by NFKC-normalizing,
casefolding, and taking maximal runs of word characters (internal
apostrophes kept: `don't` is one token). Punctuation is dropped. `\w`
matches CJK ideographs and kana, so multilingual outputs tokenize without a
language-specific segmenter.

## Distinct-n

For each requested n (default 1, 2, 3), all n-grams from all records are
pooled:

```
distinct-n = |unique n-grams| / |total n-grams|
```

Pooling is deliberate: per-record distinct-n stays high even when every
record is a copy of one sentence; the pooled ratio is what collapses.
A corpus with no n-grams of size n reports ratio 1.0 (no evidence of
repetition). Records shorter than n tokens contribute nothing.

## Self-similarity

The mean Jaccard similarity over record pairs, computed on token bigram
sets (records shorter than the n-gram fall back to their full token tuple;
token-free records fall back to character 4-shingles):

```
J(A, B) = |A ∩ B| / |A ∪ B|
self-similarity = mean over pairs (i, j), i < j
```

- **≤ 400 records:** exact, all pairs.
- **> 400 records:** 128-hash MinHash signatures, averaged over up to
  20 000 pairs sampled with a fixed seed. Signatures use `blake2b`-based
  shingle hashing and constant universal-hash parameters, so results are
  bit-for-bit reproducible across runs and machines.

The report also lists the most similar pairs — usually the fastest way to
see what collapsed.

## Duplicate clusters

Two passes, merged with union-find (smallest index becomes the cluster
representative):

1. **Exact:** records identical after NFKC + casefold + whitespace
   collapsing are always clustered, regardless of threshold.
2. **Near:** records whose token trigram-shingle Jaccard is ≥ the threshold
   (default 0.7). Small corpora verify all pairs; above 400 records,
   candidates come from MinHash LSH banding (32 bands × 4 rows, ~97%
   catch probability at Jaccard 0.7) and every candidate is re-verified
   exactly.

```
duplicate fraction = Σ (cluster size − 1) / record count
```

This is the "money wasted" number: the share of generations a smaller set
would not have missed.

## Token entropy

Shannon entropy of the pooled unigram distribution, in bits, plus a
normalized form (divided by log2 of the vocabulary size): 1.0 means a flat
distribution, values near 0 mean a handful of tokens dominate.

## Compression redundancy

```
redundancy = 1 − size(zlib(concat)) / Σ size(zlib(record))
```

Records that repeat each other compress far better together than alone.
Note the floor is not 0: unrelated prose in one language still shares
character statistics, so diverse corpora typically land around 0.3–0.45.
Read it comparatively (against a baseline run), not absolutely.

## Sameness score

```
sameness = 100 × ( 0.35 × (1 − distinct-2)
                 + 0.35 × self-similarity mean
                 + 0.30 × duplicate fraction )
```

distinct-2 reacts to phrase-level repetition, self-similarity to
whole-record resemblance, and the duplicate fraction to outright wasted
generations; each alone is gameable, together they are hard to fool.
distinct-2 is always computed for the score even when `--ngram` omits it.
Entropy and compression redundancy are reported for diagnosis but do not
enter the score.

Bands: **0–25 diverse**, **25–50 repetitive**, **50–75 mode collapse
likely**, **75–100 collapsed**. The weights are fixed in v0.1.0;
configurable weights are on the roadmap.
