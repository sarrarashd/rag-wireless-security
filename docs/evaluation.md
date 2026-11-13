# Evaluation

This document reports how well WiSec Assistant retrieves passages and answers questions. It covers the test set, the five required demonstration questions, a comparison of search methods, chunk sizes and numbers of passages, and examples of successful and unsuccessful searches.

All numbers come from `python eval/run_eval.py --answers`, run on November 12, 2026 with `claude-opus-5-5` as the language model. The raw output is in `eval/results/`.

## Main findings

- **The default configuration answers 9 of 15 questions correctly, 5 partially and 1 incorrectly** (vector search, 500-character chunks, k = 5; graded by hand).
- **No answer was made up.** Both unanswerable questions received the safe response in all five configurations (10 of 10), and none of the 61 answers the system gave lacked citations. The one incorrect baseline answer is a refusal of an answerable question, which is the safer kind of error.
- **Vector search ranks the right passage higher than keyword search** (MRR 0.85 against 0.74) and handles reworded questions, but it missed one question that hinges on an exact term. Keyword search found that one and missed a reworded one.
- **Hybrid search fixes both misses**: it found a relevant passage in the top 3 for all 13 answerable questions and produced no incorrect answer.
- **Larger chunks give more complete answers** (13 correct against 10 by the automatic grader) because each passage carries more context, at the cost of one new failure and about 1 second more per answer.
- **Almost all response time is answer generation**: about 8.5 seconds, against 0.1 seconds for vector retrieval and 2 milliseconds for keyword retrieval.

## Test set

The test set has 15 questions in `eval/questions.json`. Each one records the documents expected to contain the answer, evidence terms that a relevant passage should contain, the key facts a correct answer should state, and a reference answer.

| Type | Questions | What it tests |
| --- | --- | --- |
| Direct | Q01 to Q06 | A fact stated in one document |
| Multi-document | Q07 to Q09 | An answer that needs passages from at least two documents |
| Paraphrase | Q10 to Q12 | A question in everyday words that the documents do not use |
| Unanswerable | Q13, Q14 | An on-topic question the documents do not cover |
| Ambiguous | Q15 | A question that does not say which technology it means |

| ID | Question | Expected source |
| --- | --- | --- |
| Q01 | What does SUCI stand for and what problem does it solve? | CSWP 36A |
| Q02 | What minimum Wi-Fi encryption does the NSA say a public network should have before I connect to it? | NSA sheet |
| Q03 | What is bluesnarfing? | SP 800-121 Rev. 2, NSA sheet |
| Q04 | In the 5G hardware-enabled security white paper, what does the remote attestation service do? | CSWP 36B |
| Q05 | In LTE, which key protects the new session after a handover to another eNodeB? | SP 800-187 |
| Q06 | What is the purpose of the 4-way handshake in IEEE 802.11i? | SP 800-97 (withdrawn) |
| Q07 | Which Bluetooth attacks should I know about, and what should I do to protect my devices in public places? | SP 800-121 Rev. 2 and NSA sheet |
| Q08 | How does 5G protect a subscriber's permanent identity compared with LTE? | CSWP 36A, 36C, 36D and SP 800-187 |
| Q09 | Which identifiers does a 5G network use for a subscriber, and how is each one protected from tracking? | CSWP 36A, 36C, 36D |
| Q10 | Is it safe to pair my wireless headphones? | SP 800-121 Rev. 2, NSA sheet |
| Q11 | Can someone with a fake cell tower find out who I am and follow where my phone goes? | SP 800-187, CSWP 36A, 36C, 36D |
| Q12 | Should I check my bank account on the free internet at a coffee shop? | NSA sheet |
| Q13 | What security improvements does WPA3 bring over WPA2? | None: WPA3 is never mentioned |
| Q14 | How do I configure a guest wireless network on a Cisco Catalyst 9800 controller? | None: no vendor instructions |
| Q15 | How does authentication work? | Several, depending on the technology |

## How the results were graded

**Retrieval.** A retrieved passage counts as relevant when it comes from an expected document and contains at least one evidence term. This rule is automatic and strict about the source, so a useful passage from an unexpected document counts as not relevant. The 13 answerable questions are scored with four measures.

| Measure | Meaning |
| --- | --- |
| Hit@k | Share of questions with at least one relevant passage in the top k |
| MRR | Mean of 1 / rank of the first relevant passage; higher means the right passage is nearer the top |
| P@k | Mean share of the top k passages that are relevant |
| Coverage | For the 3 multi-document questions: share where the top k includes at least two expected documents |

**Answers.** The script gives each answer a first-pass verdict from the key facts and citations. For the default configuration, every answer was also read in full and graded by hand against the reference answer:

- **Correct**: states the expected facts, cites passages from the right documents, or gives the safe response to an unanswerable question.
- **Partially correct**: accurate but incomplete, or misses a required document.
- **Incorrect**: wrong, unsupported, or a refusal of an answerable question.

The hand grades and the automatic verdicts agree on 12 of 15 baseline answers. The three differences are explained under the baseline table. The other four configurations have automatic verdicts only.

## Required demonstration: five questions

These five answers come from the default configuration (vector search, 500-character chunks, k = 5).

### 1. Answered directly from one document (Q01)

**Question:** What does SUCI stand for and what problem does it solve?

**Answer (shortened):** SUCI stands for Subscription Concealed Identifier, an optional 5G feature supported since 3GPP Release 15 in 2019 [1]. It addresses the risk of a device sending its permanent subscriber identity (the SUPI) in clear text, for example to an attacker's malicious network [1]. SUCI encrypts the SUPI with the home operator's public key, producing a ciphered identity that is always unique, so an attacker cannot correlate it to the subscriber [1]. The encryption uses the Elliptic Curve Integrated Encryption Scheme (ECIES) [4].

**Citations:** CSWP 36A, p. 3; CSWP 36A, p. 6; CSWP 36A, pp. 4-5.

**Verdict: correct.** Four of the five retrieved passages came from CSWP 36A, and every claim is cited to it.

### 2. Needs information from multiple documents (Q09)

**Question:** Which identifiers does a 5G network use for a subscriber, and how is each one protected from tracking?

**Answer (shortened):** The SUPI is the permanent identifier written into the SIM; to keep it from being used for tracking, 5G paging uses a temporary ID instead [4][5]. SUCI protection conceals subscriber identifiers but is optional, so it protects subscribers only if the operator enables it [1]. The 5G-GUTI is a temporary identity assigned by the serving AMF, and the standards define when it must be reallocated [3][5].

**Citations:** CSWP 36D, p. 4; CSWP 36D, p. 2; CSWP 36A, pp. 1-2; CSWP 36C, p. 5.

**Verdict: correct.** The answer combines three documents, one per identifier. It also states what the passages leave out (the encryption scheme behind SUCI), which is accurate.

### 3. Cannot be answered from the documents (Q13)

**Question:** What security improvements does WPA3 bring over WPA2?

**Answer:** I could not find enough information in the wireless security documents to answer this question. [...] Detail: The passages, all from the withdrawn 2007 SP 800-97, cover only WPA and WPA2 and never mention WPA3, so they cannot say what WPA3 improves over WPA2.

**Citations:** none.

**Verdict: correct (safe response).** This is the hardest kind of unanswerable question. The best passage scored 0.67, well above the 0.25 threshold, because the collection discusses WPA2 at length, and the language model certainly knows what WPA3 is. It still refused to answer from memory. All five configurations gave the safe response.

### 4. Different wording from the source material (Q10)

**Question:** Is it safe to pair my wireless headphones?

**Answer (shortened):** The passages don't give a simple yes or no. Assuming the headphones are Bluetooth, risk depends on the pairing method: PIN/Legacy Pairing is susceptible to eavesdropping [2]. Pair as infrequently as possible, ideally in a secure area where attackers cannot observe passkey entry [3]. Since headsets often cannot disable Bluetooth on their own, shut the whole device off when not in use [3]. Keeping Bluetooth enabled in public lets attackers scan for the device [5].

**Citations:** SP 800-121 Rev. 2 (pp. 52, 11-12, 58); CSI U/OO/166417-21, p. 3; SP 800-153, p. 12.

**Verdict: correct.** The documents never say "wireless headphones"; they say "Bluetooth headset". Vector search still retrieved four Bluetooth passages. Keyword search retrieved passages about NFC, telework and EAP for the same question, and the system had to refuse.

### 5. Ambiguous or less relevant search result (Q15)

**Question:** How does authentication work?

**Answer (shortened):** Your question could apply to Wi-Fi, Bluetooth, LTE or 5G, but these passages cover only Wi-Fi (IEEE 802.11i using IEEE 802.1X). They come from SP 800-97 (2007), which is marked as withdrawn, so check for current guidance. Authentication involves three roles: the supplicant, the authenticator and the authentication server [1][5]. [...] The passages do not describe authentication for Bluetooth, LTE or 5G.

**Citations:** five passages, all from SP 800-97. The answer carries the withdrawn-publication warning.

**Verdict: partially correct.** The answer handles the ambiguity honestly: it says the question is unclear and that it covers only Wi-Fi. But retrieval returned five passages from one withdrawn document, although the Bluetooth, LTE and 5G documents also describe authentication. SP 800-97 holds 47% of all chunks and uses the word "authentication" heavily, so it crowds out the others.

## Results for the default configuration

| ID | Type | Status | Verdict (by hand) | Explanation |
| --- | --- | --- | --- | --- |
| Q01 | Direct | Answered | Correct | Definition and purpose, all from CSWP 36A |
| Q02 | Direct | Safe response | **Incorrect** | The passage that says "WPA2-encryption at a minimum" was not in the top 5, so the system refused an answerable question |
| Q03 | Direct | Answered | Correct | Definition from SP 800-121 Rev. 2, context from the NSA sheet |
| Q04 | Direct | Answered | Partial | Says the service collects measurements and evaluates trust, but not that it compares them with a list of allowed measurements |
| Q05 | Direct | Answered | Partial | Retrieved the right page, but the chunk with the key's name (KeNB*) was not in the top 5; the answer says the name is missing |
| Q06 | Direct | Answered | Correct | Shown with the withdrawn-publication warning, as intended |
| Q07 | Multi | Answered | Partial | Lists general threats, not the named Bluetooth attacks; cites only one of the two documents |
| Q08 | Multi | Answered | Partial | Good on 5G; the LTE side is thin and SP 800-187 is not cited |
| Q09 | Multi | Answered | Correct | Combines CSWP 36A, 36C and 36D |
| Q10 | Paraphrase | Answered | Correct | Found Bluetooth guidance from "wireless headphones" |
| Q11 | Paraphrase | Answered | Correct | Maps "fake cell tower" to "rogue base station"; covers LTE and 5G |
| Q12 | Paraphrase | Answered | Correct | Maps "free internet at a coffee shop" to public Wi-Fi |
| Q13 | Unanswerable | Safe response | Correct | Refused; WPA3 is not in the collection |
| Q14 | Unanswerable | Safe response | Correct | Refused; no vendor configuration steps |
| Q15 | Ambiguous | Answered | Partial | Flags the ambiguity but covers only Wi-Fi, from the withdrawn document |
| **Total** | | | **9 correct, 5 partial, 1 incorrect** | |

The automatic grader gave 10 correct, 4 partial and 1 incorrect. It differs from the hand grades on three answers. It marked Q08 and Q15 correct because the key terms were present, although Q08 is thin on LTE and Q15 covers one technology. It marked Q11 partial because the answer says "subscriber identifier" where the grader looked for "IMSI" or "SUPI".

Three of the five partial answers (Q04, Q05, Q07) say explicitly what the passages did not contain. The system gave an incomplete answer and said so, instead of filling the gap from the model's memory.

## Comparison 1: keyword, vector and hybrid search

Retrieval on the 13 answerable questions, 500-character chunks:

| Method | k | Hit@k | MRR | P@k | Coverage | Mean time |
| --- | --- | --- | --- | --- | --- | --- |
| Vector | 3 | 0.92 | 0.85 | 0.72 | 0.67 | 105 ms |
| Vector | 5 | 0.92 | 0.85 | 0.66 | 0.67 | 116 ms |
| Vector | 10 | 1.00 | 0.85 | 0.63 | 0.67 | 115 ms |
| Keyword | 3 | 0.69 | 0.69 | 0.56 | 1.00 | 2 ms |
| Keyword | 5 | 0.92 | 0.74 | 0.58 | 1.00 | 2 ms |
| Keyword | 10 | 1.00 | 0.75 | 0.52 | 1.00 | 2 ms |
| Hybrid | 3 | 1.00 | 0.91 | 0.77 | 0.67 | 97 ms |
| Hybrid | 5 | 1.00 | 0.91 | 0.66 | 0.67 | 98 ms |
| Hybrid | 10 | 1.00 | 0.91 | 0.58 | 1.00 | 99 ms |

Rank of the first relevant passage for the questions where the methods differ (k = 5; "none" means not in the top 5):

| ID | Question | Vector | Keyword | Hybrid |
| --- | --- | --- | --- | --- |
| Q01 | What does SUCI stand for... | 1 | 4 | 1 |
| Q02 | What minimum Wi-Fi encryption does the NSA say... | none | 5 | 3 |
| Q05 | In LTE, which key protects the new session... | 2 | 1 | 2 |
| Q10 | Is it safe to pair my wireless headphones? | 2 | none | 1 |
| Q11 | Can someone with a fake cell tower... | 1 | 5 | 1 |

Answers for all 15 questions (automatic verdicts, 500-character chunks, k = 5):

| Method | Correct | Partial | Incorrect | Mean response time |
| --- | --- | --- | --- | --- |
| Vector | 10 | 4 | 1 (Q02 refused) | 8.8 s |
| Keyword | 10 | 4 | 1 (Q10 refused) | 7.5 s |
| Hybrid | 11 | 4 | 0 | 9.0 s |

The two methods fail in opposite ways:

- **Vector search wins when the wording differs.** For Q10 and Q11 it placed a relevant passage first or second, while keyword search found nothing useful for Q10 and ranked the relevant passage fifth for Q11. "Headphones" and "fake cell tower" do not appear in the documents.
- **Keyword search wins when one exact term decides the answer.** For Q02 the answer is a single line containing "WPA2-encryption at a minimum". Vector search returned five passages about public Wi-Fi and WPA2 in general, none with that line. Keyword search matched "minimum", "WPA2" and "encryption" and found it.
- **Keyword search is about 50 times faster** (2 ms against about 100 ms), but this does not matter in practice because generation takes seconds.
- **Hybrid search has the best ranking** (MRR 0.91) and is the only method with a relevant passage in the top 3 for every question. With it, Q02 and Q10 are both answered correctly.

## Comparison 2: chunk size

Vector search, k = 5:

| Chunk size | Hit@5 | MRR | P@5 | Coverage | Correct | Partial | Incorrect | Mean response time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 500 characters | 0.92 | 0.85 | 0.66 | 0.67 | 10 | 4 | 1 | 8.8 s |
| 1,500 characters | 0.92 | 0.85 | 0.71 | 1.00 | 13 | 1 | 1 | 9.7 s |

Answer verdicts are automatic.

- **Retrieval quality is about the same**, but the larger chunks cover more documents for multi-document questions (1.00 against 0.67).
- **Answers are more complete with larger chunks.** Q04, Q05 and Q11 move from partial to correct. With 500-character chunks the system found the right page for Q05 but not the sentence naming the key; a 1,500-character chunk holds the whole paragraph. Q02 is also answered, because the larger chunk about public Wi-Fi includes the WPA2 line.
- **Larger chunks introduced one failure.** Q03 ("What is bluesnarfing?") was refused: the top five passages mentioned bluesnarfing only in a footnote link. A likely cause is that the embedding model reads only the first 1,000 or so characters of a chunk, so a definition near the end of a 1,500-character chunk does not affect its vector.
- **Cost:** five large passages are about three times as much text for the model to read, and the mean response time rose by about 1 second.

## Comparison 3: number of retrieved passages

Vector search, 500-character chunks:

| k | Hit@k | MRR | P@k | Correct | Partial | Incorrect | Mean response time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | 0.92 | 0.85 | 0.72 | 9 | 5 | 1 | 8.0 s |
| 5 | 0.92 | 0.85 | 0.66 | 10 | 4 | 1 | 8.8 s |
| 10 | 1.00 | 0.85 | 0.63 | not run | not run | not run | not run |

Answer verdicts are automatic. Answers were not generated for k = 10.

- **More passages trade precision for recall.** From k = 3 to k = 10, P@k falls from 0.72 to 0.63 while Hit@k rises from 0.92 to 1.00: at k = 10 the missing Q02 passage is finally retrieved.
- **k = 3 loses detail on multi-document questions.** Q08 drops from correct to partial because three passages cannot cover three documents.
- **k = 5 was kept as the default** as a balance between the two.

## Citation quality

| Measure | Result (default configuration) |
| --- | --- |
| Answers given with at least one citation | 12 of 12 |
| Answers with no citation (`unsupported`) | 0 |
| Citation numbers that did not match a retrieved passage | 0 |
| Citations that point to an expected document | 45 of 46 (98%) |
| Answers citing the withdrawn SP 800-97 that showed the warning | 2 of 2 (Q06, Q15) |

The one citation outside the expected documents is SP 800-153 in Q10, used for a valid point about a device connected to Wi-Fi and Bluetooth at once. Across all five configurations, the system gave 61 answers and 14 safe responses; no answer was unsupported or cited a passage number that did not exist.

These checks are structural. They confirm that each citation points to a real retrieved passage from a sensible document. They do not prove that the passage supports the exact sentence it is attached to; that was checked by reading for the baseline answers only, and no mismatch was found.

## Response time

| Step | Time |
| --- | --- |
| Keyword retrieval | about 2 ms |
| Vector or hybrid retrieval | about 100 ms (about 1 second for the first query after start-up, while the embedding model loads) |
| Answer generation | 8.5 s on average, from 6.1 s to 11.5 s |
| Safe response from the similarity gate | under 0.3 s, because the language model is not called |
| Total per answered question (default) | 8.8 s on average |

Generation accounts for about 96% of the response time. The times were measured through the `claude` command line tool with four questions running in parallel; calling the API directly would likely be somewhat faster.

## Successful and unsuccessful searches

| Search | Method | Result | Why |
| --- | --- | --- | --- |
| "Is it safe to pair my wireless headphones?" | Vector | Success: 4 of 5 passages about Bluetooth pairing and headsets | Embeddings match "headphones" to "headset" and "earbud" |
| Same question | Keyword | Failure: passages on NFC, telework and EAP | No document contains "headphones"; common words like "safe" and "wireless" match everywhere |
| "What minimum Wi-Fi encryption does the NSA say..." | Vector | Failure: 5 on-topic passages, none with the answer | Many passages are about public Wi-Fi and WPA2 in general; the one decisive line is not the closest in meaning |
| Same question | Keyword, hybrid | Success: the "WPA2-encryption at a minimum" passage at rank 5 and rank 3 | The exact words "minimum", "WPA2" and "encryption" match |
| "In the 5G hardware-enabled security white paper, what does the remote attestation service do?" | Vector | Success: top 4 passages from CSWP 36B, score 0.71 | Specific technical terms in a short, focused document |
| "How does authentication work?" | Vector | Weak: 5 of 5 passages from the withdrawn SP 800-97 | A vague query, and one document holds 47% of the chunks |
| "What is bluesnarfing?" | Vector, 1,500-character chunks | Failure: only a footnote link retrieved | Probably the embedding model's input limit on long chunks |
| "How do I bake sourdough bread?" | Vector | Correctly rejected: best score 0.14 | Below the 0.25 threshold, so the model is never called |

## System limitations found in the evaluation

- **Retrieval decides the answer.** Every incorrect or partial baseline answer traces back to a passage that was not retrieved, not to the language model inventing something. The model reliably says what is missing, but it cannot answer from a passage it never saw.
- **Each single search method has a blind spot**: exact terms for vector search, synonyms for keyword search. Hybrid search covers both on this test set.
- **Chunk boundaries split answers.** With 500-character chunks, a fact and the name it belongs to can land in different chunks (Q05).
- **The largest document crowds out the others** on broad Wi-Fi questions (Q15), and it is the withdrawn one.
- **The similarity threshold only catches off-topic questions.** On-topic unanswerable questions depend on the language model's judgment. It was right 10 times out of 10 here, which is encouraging but not a guarantee.
- **The test set is small and written by the project team**, so the numbers show tendencies, not precise rates. One question moves Hit@k by 8 points.
- **Most answer verdicts outside the default configuration are automatic**, based on key terms, and the hand review showed the automatic grader is slightly generous.
