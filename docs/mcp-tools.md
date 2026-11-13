# MCP Tool Reference

The MCP server `wisec-assistant` (`src/server.py`) exposes the document search over the stdio transport. It offers four tools. Every example below is a real request from `tests/test_mcp.py`, which sends 11 sample requests through an MCP client and checks each response.

```bash
python tests/test_mcp.py -v
```

| Tool | Required by the project | Purpose |
| --- | --- | --- |
| `search_documents` | Yes | Find relevant passages |
| `get_document` | Yes | Retrieve a document or a page range of it |
| `list_documents` | Optional | List the collection |
| `provide_feedback` | Optional | Rate an answer |

Errors are returned as MCP tool errors (`isError: true`) with a message that says what to change.

## search_documents

Finds the passages most relevant to a question.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `query` | string | required | Question or topic in plain English |
| `k` | integer | 5 | Number of passages, clamped to 1 to 10 |
| `mode` | string | `"vector"` | `"vector"` (semantic, cosine similarity), `"keyword"` (BM25) or `"hybrid"` (both rankings merged by reciprocal rank fusion) |
| `chunk_size` | integer | 500 | 500 for short passages or 1500 for longer ones |

Each result has `rank`, `citation` (series number and PDF pages), `title`, `publisher`, `status` (`final` or `withdrawn`), `score`, `chunk_id` and `text`. The score is cosine similarity from 0 to 1 in vector mode, a BM25 score in keyword mode and a rank-fusion score in hybrid mode; the three scales are not comparable.

Request:

```json
{"query": "WPA2 encryption on public Wi-Fi", "k": 2, "mode": "keyword"}
```

Response (second result shortened):

```json
{
  "query": "WPA2 encryption on public Wi-Fi",
  "mode": "keyword",
  "results": [
    {
      "rank": 1,
      "citation": "CSI U/OO/166417-21, p. 5",
      "title": "Securing Wireless Devices in Public Settings",
      "publisher": "NSA",
      "status": "final",
      "score": 18.02,
      "chunk_id": 2941,
      "text": "... If connecting to public Wi-Fi is necessary: Only connect to secure public WiFi. ... Only connect to networks with WPA2-encryption at a minimum. Do not connect to open Wi-Fi hotspots. ..."
    },
    {"rank": 2, "citation": "CSI U/OO/166417-21, p. 2", "...": "..."}
  ]
}
```

Error case, `{"query": "bluetooth", "mode": "fuzzy"}`:

```text
Error executing tool search_documents: mode must be "vector", "keyword" or "hybrid"
```

## get_document

Retrieves a document's metadata and text, or only a section selected by page range.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `document` | string | required | Series number (`"SP 800-153"`, `"CSWP 36A"`), file name, or document ID. A unique partial match such as `"SP 800-121"` also works. |
| `page_start` | integer | 1 | First PDF page of the section |
| `page_end` | integer | `page_start`, or the last page when neither is given | Last PDF page of the section |
| `max_chars` | integer | 8000 | Maximum characters of text returned |

The response has `series`, `title`, `publisher`, `year`, `status`, `technology`, `total_pages`, `source_url`, `pages_returned`, `truncated` and `text`. A withdrawn publication also carries a `warning`.

Request:

```json
{"document": "SP 800-97", "page_start": 1, "max_chars": 400}
```

Response:

```json
{
  "series": "SP 800-97",
  "title": "Establishing Wireless Robust Security Networks: A Guide to IEEE 802.11i",
  "publisher": "NIST",
  "year": 2007,
  "status": "withdrawn",
  "technology": "Wi-Fi",
  "total_pages": 163,
  "source_url": "https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-97.pdf",
  "pages_returned": "1-1",
  "truncated": true,
  "text": "Date updated: December 31, 2025 Withdrawn NIST Technical Series Publication Warning Notice The attached publication has been withdrawn (archived), and is provided solely for historical purposes. ...",
  "warning": "This publication has been withdrawn by its publisher and may be outdated."
}
```

Error case, `{"document": "SP 999-1"}`:

```text
Error executing tool get_document: Document "SP 999-1" was not found. Available: SP 800-153, SP 800-97, SP 800-121 Rev. 2, SP 800-187, CSWP 36, CSWP 36A, CSWP 36B, CSWP 36C, CSWP 36D, CSWP 36E, CSI U/OO/166417-21
```

The text is rebuilt from the 1,500-character chunks that overlap the requested pages, with the overlap between consecutive chunks removed. It can therefore start or end a few sentences outside the requested pages.

## list_documents

Lists every document. It takes no parameters.

Response (first of 11 entries):

```json
[
  {
    "series_number": "SP 800-153",
    "title": "Guidelines for Securing Wireless Local Area Networks (WLANs)",
    "publisher": "NIST",
    "pub_year": 2012,
    "status": "final",
    "technology": "Wi-Fi",
    "num_pages": 24,
    "chunks": 148
  }
]
```

`chunks` is the number of 500-character chunks.

## provide_feedback

Records a rating for an answer in the `query_log` table.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `rating` | integer | required | 1 = helpful, 0 = partly helpful, -1 = not helpful |
| `question` | string | `""` | The question asked; required unless `query_id` is given |
| `answer` | string | `""` | The answer given |
| `cited_chunks` | string | `""` | Comma-separated chunk IDs the answer cited |
| `query_id` | integer | none | ID of an answer already in the log; its rating is updated instead of adding a row |

Request:

```json
{"question": "Is it safe to pair my wireless headphones?", "answer": "Test answer from test_mcp.py", "rating": 1}
```

Response:

```json
{"saved": true, "query_id": 2, "rating": 1}
```

Error case, `{"rating": 5, "question": "x"}`:

```text
Error executing tool provide_feedback: rating must be -1, 0 or 1
```

## Test results

All 11 sample requests behave as expected: 7 return valid results and 4 return the intended error.

| # | Request | Expected | Result |
| --- | --- | --- | --- |
| 1 | `list_documents` | 11 documents | Pass |
| 2 | `search_documents`, vector, k = 3 | 3 results with citations | Pass |
| 3 | `search_documents`, keyword, k = 2 | Top result from the NSA sheet | Pass |
| 4 | `search_documents`, chunk size 1500 | 2 results | Pass |
| 5 | `search_documents`, hybrid, k = 3 | 3 results | Pass |
| 6 | `search_documents`, mode `"fuzzy"` | Error | Pass |
| 7 | `get_document`, partial name, pages 11 to 12, 1,200 characters | SP 800-121 Rev. 2, text within the limit | Pass |
| 8 | `get_document`, withdrawn document | Status `withdrawn` and a warning | Pass |
| 9 | `get_document`, unknown document | Error listing the available documents | Pass |
| 10 | `provide_feedback`, rating 1 | Saved | Pass |
| 11 | `provide_feedback`, rating 5 | Error | Pass |

The test server runs against a temporary copy of the database, so running the tests does not change `db/metadata.db`.
