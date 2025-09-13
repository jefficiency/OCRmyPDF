# Upstage Document Parsing (Digitize) — API Reference

> Source: [Upstage Document Parsing docs](https://console.upstage.ai/docs/capabilities/digitize/document-parsing)

## Overview

**Document Parsing** converts documents into structured text (HTML/Markdown), detecting layout elements (paragraphs, tables, images, equations, lists, headers/footers, etc.), ordering them by reading order, and serializing the results.

- **Output formats**: HTML and/or Markdown, with optional raw text
- **Optional extras**: element-level coordinates, base64 element crops (e.g., figures, tables), chart-to-table recognition, equation LaTeX extraction, and merged multi-page tables

## Models and Rate Limits

| **Alias** | **Currently points to** | **RPS** |
|---|---|---|
| `document-parse` | `document-parse-250618` | 10 (Sync) / 30 (Async) |
| `document-parse-nightly` | - | 10 (Sync) / 30 (Async) |

- Use stable aliases (e.g., `document-parse`) rather than pinning model snapshots; aliases shift to newer versions over time.

## Input Requirements

- **Supported file formats**: `JPEG`, `PNG`, `BMP`, `PDF`, `TIFF`, `HEIC`, `DOCX`, `PPTX`, `XLSX`, `HWP`, `HWPX`
- **Maximum file size**: 50 MB
- **Maximum pages per file**:
  - Synchronous API: 100 pages (pages beyond 100 are ignored)
  - Asynchronous API: 1,000 pages
- **Maximum pixels per page**: 200,000,000 (non-image files are rasterized at 150 DPI first)
- **Supported character sets (OCR)**: Alphanumeric, Hangul, Hanja. Hanzi/Kanji are in beta.
- **Best practices**:
  - Use high-resolution inputs; minimum page width of 640 px
  - Ensure smallest text height ≥ ~2.5% of image height (e.g., 16 px on a 640 px-tall page)

## Understanding the Output

### Layout categories to HTML tags

If there’s no native tag, a `<p>` is returned with `data-category` indicating the category.

| **Layout category** | **HTML tag** |
|---|---|
| `table` | `<table> … </table>` |
| `figure` | `<figure><img> … </img></figure>` |
| `chart` | `<figure><img data-category="chart"> … </img></figure>` |
| `heading1` | `<h1> … </h1>` |
| `header` | `<header> … </header>` |
| `footer` | `<footer> … </footer>` |
| `caption` | `<caption> … </caption>` |
| `paragraph` | `<p data-category="paragraph"> … </p>` |
| `equation` | `<p data-category="equation"> … </p>` |
| `list` | `<p data-category="list"> … </p>` |
| `index` | `<p data-category="index"> … </p>` |
| `footnote` | `<p data-category="footnote"> … </p>` |

### Chart recognition → tables

- Converts supported chart types to table format: **bar**, **line**, **pie**
- If chart recognition is confident, category is `chart` and output includes a `<figcaption>` and `<table>` with data
- If confidence is insufficient, the item is categorized as `figure` and the OCR result appears in `alt`/text fields

Example (success):

```json
{
  "category": "chart",
  "content": {
    "html": "<figure id='4' data-category='chart'><img data-coord=\"top-left:(175,1305); bottom-right:(785,1784)\" /><figcaption><p>Chart Type: bar</p></figcaption><table><tr><th></th><th>Nuclear</th><th>Renewables</th><th>Hydro</th><th>Natural gas</th><th>Coal</th><th>Oil</th></tr><tr><td>item_01</td><td>4%</td><td>4%</td><td>7%</td><td>24%</td><td>27%</td><td>34%</td></tr></table></figure>",
    "markdown": "- Chart Type: bar\n|  | Nuclear | Renewables | Hydro | Natural gas | Coal | Oil |\n| --- | --- | --- | --- | --- | --- | --- |\n| item_01 | 4% | 4% | 7% | 24% | 27% | 34% |\n",
    "text": "Chart Type: bar \nNuclear Renewables HydroNatural gas Coal Oil\n item_01 4% 4% 7% 24% 27% 34%"
  },
  "id": 4,
  "page": 1
}
```

Example (fallback to figure):

```json
{
  "category": "figure",
  "content": {
    "html": "<figure id='4' data-category='chart'><img style='font-size:20px' alt=\"Nuclear 4%\nRenewables 4%\nHydro 7%\nNatural gas 24%\nCoal 27%\nOil 34%\" data-coord=\"top-left:(175,1306); bottom-right:(785,1783)\" /></figure>",
    "markdown": "Nuclear 4%\nRenewables 4%\nHydro 7%\nNatural gas 24%\nCoal 27%\nOil 34%",
    "text": "Nuclear 4%\nRenewables 4%\nHydro 7%\nNatural gas 24%\nCoal 27%\nOil 34%"
  },
  "id": 4,
  "page": 1
}
```

### Equation recognition (LaTeX)

Equations are returned in LaTeX within `<p data-category="equation">` for reliable rendering. OCR `text` is included for backward compatibility but may not match the LaTeX.

```json
{
  "category": "equation",
  "content": {
    "html": "<p id='3' data-category='equation'>$$a_{n}=\\sum_{k=1}^{n}{\\frac{2k+1}{\\,1^{2}+2^{2}+3^{2}+\\cdots+k^{2}}}$$</p>",
    "markdown": "$$a_{n}=\\sum_{k=1}^{n}{\\frac{2k+1}{\\,1^{2}+2^{2}+3^{2}+\\cdots+k^{2}}}$$",
    "text": "n 2k+1 \nan  \nk=1 12+22+32 + · · +k2"
  }
}
```

Rendering tip (escape handling in JSON → HTML):

```html
<body>
  <div id="equation"></div>
  <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  <script type="text/javascript">
    document.getElementById('equation').innerHTML = "<p id='5' data-category='equation'>$$f(x)=a_{0}+\\sum_{n=1}^{\\infty}\\left(a_{n}\\cos{\\frac{n\\pi x}{L}}+b_{n}\\sin{\\frac{n\\pi x}{L}}\\right)$$</p>";
  </script>
</body>
```

### Coordinates (relative)

Since `document-parse-240910`, element coordinates can be returned as relative four-decimal values. Multiply by image width/height to get absolute pixels.

```json
"coordinates": [
  { "x": 0.0276, "y": 0.0178 },
  { "x": 0.1755, "y": 0.0178 },
  { "x": 0.1755, "y": 0.0641 },
  { "x": 0.0276, "y": 0.0641 }
]
```

### Merged tables spanning multiple pages

Enable `merge_multipage_tables=true` to automatically detect and merge tables split across pages; content is consolidated into the first table instance.

---

## Synchronous API — Document Parsing

- **Endpoint**: `POST https://api.upstage.ai/v1/document-digitization`
- **Auth**: `Authorization: Bearer <API_KEY>`
- **Content-Type**: `multipart/form-data`

### Request parameters

| **Name** | **Type** | **Required** | **Default** | **Description** |
|---|---:|:---:|:---:|---|
| `model` | string | Yes | `document-parse` | Alias recommended. You may pin a version (e.g., `document-parse-250618`). |
| `document` | file | Yes | — | The file to process. |
| `chart_recognition` | boolean | No | `true` | If true, recognized charts are converted to tables. |
| `merge_multipage_tables` | boolean | No | `false` | Merge tables that span multiple pages. |
| `ocr` | string | No | `"auto"` | `"auto"` or `"force"`. `force` rasterizes and applies OCR before layout detection. |
| `output_formats` | string | No | `"['html']"` | Any of: `text`, `html`, `markdown`. |
| `coordinates` | boolean | No | `true` | Include element bounding boxes. |
| `base64_encoding` | string | No | `[]` | Categories to crop and return as base64 (e.g., `['table']`, `['figure']`). |

### Example — Python

```python
# pip install requests
import requests

api_key = "up_*************************ctbu"  # ex: up_xxxYYYzzzAAAbbbCCC
filename = "YOUR_FILE_NAME"  # ex: ./image.png

url = "https://api.upstage.ai/v1/document-digitization"
headers = {"Authorization": f"Bearer {api_key}"}
files = {"document": open(filename, "rb")}
data = {"ocr": "force", "base64_encoding": "['table']", "model": "document-parse"}
response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

### Example — cURL

```bash
curl -X POST "https://api.upstage.ai/v1/document-digitization" \
  -H "Authorization: Bearer $UPSTAGE_API_KEY" \
  -F "model=document-parse" \
  -F "document=@YOUR_FILE_PATH" \
  -F "ocr=force" \
  -F "base64_encoding=['table']"
```

### Response (example, abbreviated)

```json
{
  "api": "2.0",
  "content": {
    "html": "<h1 id='0' style='font-size:22px'>INVOICE</h1>...",
    "markdown": "",
    "text": ""
  },
  "elements": [
    {
      "category": "heading1",
      "content": { "html": "<h1 id='0' style='font-size:22px'>INVOICE</h1>", "markdown": "", "text": "" },
      "coordinates": [ { "x": 0.0648, "y": 0.0517 }, ... ],
      "id": 0,
      "page": 1
    }
    // ... many more elements ...
  ],
  "model": "document-parse-250618",
  "usage": { "pages": 1 }
}
```

---

## Asynchronous API — Document Parsing

### How it works

- Submit a document (up to 1000 pages) to the async endpoint; receive a `request_id` immediately
- The system splits the document into batches of 10 pages; each batch is inferred and tracked independently
- Poll the request to see per-batch statuses and download results by `download_url`
- Results are retained for 30 days; each `requests/{id}` call returns a new pre-signed `download_url` valid for ~15 minutes

### Submit inference request

- **Endpoint**: `POST https://api.upstage.ai/v1/document-digitization/async`

```python
import requests

api_key = "up_*************************ctbu"
filename = "invoice.png"

url = "https://api.upstage.ai/v1/document-digitization/async"
headers = {"Authorization": f"Bearer {api_key}"}
files = {"document": open(filename, "rb")}
data = {"model": "document-parse"}
response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())  # {"request_id": "..."}
```

### Retrieve inference result

- **Endpoint**: `GET https://api.upstage.ai/v1/document-digitization/requests/{REQUEST_ID}`

Example response (abbreviated):

```json
{
  "id": "e7b1b3b0-1b3b-4b3b-8b3b-1b3b3b3b3b3b",
  "status": "completed",
  "model": "document-parse",
  "failure_message": "",
  "total_pages": 28,
  "completed_pages": 28,
  "batches": [
    {
      "id": 0,
      "model": "document-parse-250618",
      "status": "completed",
      "failure_message": "",
      "download_url": "https://download-url",
      "start_page": 1,
      "end_page": 10,
      "requested_at": "2024-07-01T14:47:01.863880448Z",
      "updated_at": "2024-07-01T14:47:15.901662097Z"
    }
    // ... more batches ...
  ],
  "requested_at": "2024-07-01T14:47:01.863880448Z",
  "completed_at": "2024-07-01T14:47:43.023542045Z"
}
```

### Retrieve inference history

- **Endpoint**: `GET https://api.upstage.ai/v1/document-digitization/requests`

```json
{
  "requests": [
    {
      "id": "e7b1b3b0-1b3b-4b3b-8b3b-1b3b3b3b3b3b",
      "status": "completed",
      "model": "document-parse",
      "requested_at": "2024-07-01T14:47:01.863880448Z",
      "completed_at": "2024-07-01T14:47:43.023542045Z"
    }
  ]
}
```

### Batch schema

```ts
batches: {
  id: number;
  model: string;
  status: 'scheduled' | 'started' | 'completed' | 'failed' | 'retrying';
  failure_message: string;
  download_url: string;
  start_page: number;
  end_page: number;
  requested_at: string; // ISO date-time
  updated_at: string;   // ISO date-time
}[]
```

---

## Error Handling and Troubleshooting

### Request errors (synchronous or async submission)

- Response body format:

```json
{ "code": 400, "message": "..." }
```

- Common cases:
  - `400 Bad Request`: invalid model name; missing document
  - `413 Payload Too Large`: file exceeds 50 MB
  - `415 Unsupported Media Type`: unsupported format

### Batch inference errors (async)

- Failures during inference are reflected per-batch with `status: "failed"` and a `failure_message`
- Often transient or server-side; retry if temporary; validate inputs; contact support if persistent

### Result retrieval failures (async)

- `download_url` is valid for ~15 minutes; expired URLs return `403 Forbidden`
- Re-fetch via `GET /requests/{REQUEST_ID}` to obtain fresh `download_url` (does not consume additional credits)

---

## Tips and Tricks

### Split long PDFs into smaller chunks (faster debug / under sync limits)

```python
"""
Requirements: `pip install pymupdf` to import fitz
"""
import os
import fitz

def split_pdf(input_file, batch_size):
    input_pdf = fitz.open(input_file)
    num_pages = len(input_pdf)
    print(f"Total number of pages: {num_pages}")

    for start_page in range(0, num_pages, batch_size):
        end_page = min(start_page + batch_size, num_pages) - 1
        input_file_basename = os.path.splitext(input_file)[0]
        output_file = f"{input_file_basename}_{start_page}_{end_page}.pdf"
        print(output_file)
        with fitz.open() as output_pdf:
            output_pdf.insert_pdf(input_pdf, from_page=start_page, to_page=end_page)
            output_pdf.save(output_file)

    input_pdf.close()

# Input arguments
input_file = "paper.pdf"
batch_size = 10  # up to 100 for sync API
split_pdf(input_file, batch_size)
```

### Crop and save specific elements (e.g., figures)

Request with base64 crops, then decode and save the first `figure`:

```python
"""
Requirements: `pip install requests`
"""
from glob import glob
import json
import os
import requests
import base64

API_KEY = "up_*************************ctbu"

def call_document_parse(input_file, output_file):
    response = requests.post(
        "https://api.upstage.ai/v1/document-digitization",
        headers={"Authorization": f"Bearer {API_KEY}"},
        data={"base64_encoding": "['figure']", "model": "document-parse"},
        files={"document": open(input_file, "rb")},
    )
    if response.status_code == 200:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(response.json(), f, ensure_ascii=False)
    else:
        raise ValueError(f"Unexpected status code {response.status_code}.")

# Process a set of split PDFs
input_file = "paper.pdf"
short_input_files = glob(os.path.splitext(input_file)[0] + "_*.pdf")
for short_input_file in short_input_files:
    short_output_file = os.path.splitext(short_input_file)[0] + ".json"
    call_document_parse(short_input_file, short_output_file)

# Decode the first figure crop from one JSON
json_file = "paper_0_9.json"
output_file = "paper_cropped_figure.png"
with open(json_file, "r", encoding="utf-8") as f:
    data = json.load(f)
    for element in data["elements"]:
        if element["category"] == "figure":
            with open(output_file, "wb") as fh:
                fh.write(base64.decodebytes(str.encode(element["base64_encoding"])))
            break
```

### Chunk long outputs into segments for LLMs

```python
def get_chunks(lines, max_context_length=4096):
    chunks = []
    current_chunk = []
    for line in lines:
        if len(" ".join(current_chunk + [line])) <= max_context_length:
            current_chunk.append(line)
        else:
            chunks.append(current_chunk)
            current_chunk = [line]
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

with open("paper.html", "r", encoding="utf-8") as f:
    lines = f.read().split("\n")

chunks = get_chunks(lines, max_context_length=1024)
print(chunks[0])
```

---

## Upstage Document OCR — API Reference

## Overview (OCR)

**Document OCR** detects and recognizes text from document images across multiple languages and qualities, designed to be robust to rotations, watermarks, noise, and checkboxes. Confidence scores are provided per character and calibrated at word level.

## Models and Rate Limits (OCR)

| **Alias** | **Currently points to** | **RPS** |
|---|---|---|
| `ocr` | `ocr-2.2.1` | 1 |
| `ocr-250904` | — | 1 |

## Input Requirements (OCR)

- **Supported file formats**: `JPEG`, `PNG`, `BMP`, `PDF`, `TIFF`, `HEIC`, `DOCX`, `PPTX`, `XLSX`, `HWP`, `HWPX`
- **Maximum file size**: 50 MB
- **Maximum pages**: 100 pages
- **Maximum pixels per page**: 200,000,000 (150 DPI rasterization for non-image files)
- **Supported character sets**: Alphanumeric, Hangul, Hanja (Hanzi/Kanji beta)
- **Notes**: Optimized for text size ≲ ~30% of page size; small/dense text may degrade quality

## API — OCR (Synchronous)

- **Endpoint**: `POST https://api.upstage.ai/v1/document-digitization`
- **Auth**: `Authorization: Bearer <API_KEY>`
- **Content-Type**: `multipart/form-data`

### Request parameters (OCR)

| **Name** | **Type** | **Required** | **Description** |
|---|---:|:---:|---|
| `model` | string | Yes | Use alias `ocr` (or a snapshot like `ocr-250904`). |
| `document` | file | Yes | The file to process. |
| `schema` | string | No | Optional: normalizes output to a provider schema. One of: `"clova"` \| `"google"`. |

### Example — Python (OCR)

```python
# pip install requests
import requests

api_key = "up_*************************ctbu"
filename = "YOUR_FILE_NAME"

url = "https://api.upstage.ai/v1/document-digitization"
headers = {"Authorization": f"Bearer {api_key}"}
files = {"document": open(filename, "rb")}
data = {"model": "ocr"}
response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

### Response (example, abbreviated) (OCR)

```json
{
  "apiVersion": "1.1",
  "confidence": 0.9924988460974842,
  "metadata": { "pages": [{ "height": 256, "page": 1, "width": 786 }] },
  "mimeType": "multipart/form-data",
  "modelVersion": "ocr-250904",
  "numBilledPages": 1,
  "pages": [
    {
      "confidence": 0.9924988460974842,
      "height": 256,
      "id": 0,
      "text": "Print the words \nhello, world",
      "width": 786,
      "words": [
        {
          "boundingBox": { "vertices": [{"x":65,"y":52},{"x":221,"y":55},{"x":221,"y":104},{"x":64,"y":101}] },
          "confidence": 0.9950619419,
          "id": 0,
          "text": "Print"
        }
        // ... more words ...
      ]
    }
  ],
  "stored": true,
  "text": "Print the words \nhello, world"
}
```

## FAQ and Operational Notes

- **Can I request multiple documents at once?** Not directly; submit one at a time. Bursty parallelism may hit `429 Too Many Requests`.
- **Why `415 Unsupported Media Type`?** Unsupported formats; verify against the supported list.
- **Slow or delayed responses?** Temporary surges; check status page; typical uptime >95% SLA.
- **Rate limits**: Default RPS noted above; request increases via support if needed.
- **403 when downloading async results?** The pre-signed URL expires after ~15 minutes; re-fetch via `requests/{request_id}` to generate a new one (no extra credits).

---

## Reference

- [Upstage Console Docs — Document Parsing](https://console.upstage.ai/docs/capabilities/digitize/document-parsing)
