# Databricks GenAI Associate: Parsing Methods Cheat Sheet

## 1. Big Picture

Parsing means converting raw content into text, tables, layout, metadata, or structured data that downstream GenAI systems can use.

For the exam, think of parsing in this order:

```text
Raw document / webpage / image
        ↓
Parser extracts text, tables, images, layout, or metadata
        ↓
Text is chunked
        ↓
Chunks are embedded
        ↓
Vector search retrieves relevant chunks
        ↓
LLM generates answer
```

The parsing method depends on the source format and the downstream use case.

| Source Type                            | Best Parsing Method               |
| -------------------------------------- | --------------------------------- |
| HTML / XML                             | BeautifulSoup or LXML             |
| Large/complex HTML or XML              | LXML                              |
| Simple text-based PDF                  | PyPDF2                            |
| PDF with tables/layout                 | PDFPlumber                        |
| Scanned PDF or image                   | pytesseract / OCR                 |
| PDF with text and images, minimal code | unstructured                      |
| Complex business documents             | unstructured or ai_parse_document |
| Databricks-native document parsing     | ai_parse_document                 |

---

# 2. HTML / XML Parsing

## BeautifulSoup

### Purpose

BeautifulSoup is a Python library used to parse **HTML and XML** documents.

### Strengths

* Easy to use.
* Good for navigating nested HTML.
* Useful for extracting data from webpages.
* Works well when you need quick parsing logic.

### Best Use Case

Use **BeautifulSoup** when you need to extract specific content from HTML pages, such as:

* Product names from a webpage.
* Text inside specific tags.
* Table values from simple HTML.
* Links, headings, or metadata.

### Exam Shortcut

> Choose **BeautifulSoup** when the question says HTML parsing and ease of use matters.

### Exam Trap

BeautifulSoup is a parser, but it is mainly for **HTML/XML**, not PDFs.

If the question says **PDF**, do not choose BeautifulSoup.

---

## LXML

### Purpose

LXML is a high-performance Python library for parsing **XML and HTML**.

### Strengths

* Faster than BeautifulSoup in many cases.
* Better for large or complex XML/HTML documents.
* Supports XPath.
* Good for performance-sensitive parsing.

### Best Use Case

Use **LXML** when:

* The document is large.
* Performance matters.
* XML structure is complex.
* You need XPath-style extraction.

### Exam Shortcut

> Choose **LXML** when the question says large/complex HTML or XML and performance matters.

---

## BeautifulSoup vs LXML

| Feature       | BeautifulSoup         | LXML                      |
| ------------- | --------------------- | ------------------------- |
| Best for      | Easy HTML/XML parsing | Fast HTML/XML parsing     |
| Ease of use   | Very easy             | Moderate                  |
| Speed         | Good                  | Faster                    |
| Complex XML   | Okay                  | Better                    |
| XPath support | Not primary strength  | Strong                    |
| Exam keyword  | Easy parsing          | Performance / complex XML |

---

# 3. PDF Parsing

## PyPDF2

### Purpose

PyPDF2 is a Python library for reading and manipulating PDFs.

### Strengths

* Extracts text from simple PDFs.
* Can split, merge, rotate, or modify PDF pages.
* Good for basic PDF operations.

### Best Use Case

Use **PyPDF2** when:

* The PDF is mostly plain text.
* You need simple text extraction.
* You need to split or merge PDFs.
* Layout and tables are not important.

### Limitations

* Not great for complex layouts.
* Not great for tables.
* Not useful for scanned PDFs unless OCR is added.
* Not the best choice for PDFs with mixed text and images.

### Exam Shortcut

> Choose **PyPDF2** for simple text-based PDFs or basic PDF manipulation.

---

## PDFPlumber

### Purpose

PDFPlumber is a PDF parsing library built on top of PDFMiner. It is better for extracting structured data from PDFs.

### Strengths

* Better layout awareness than PyPDF2.
* Can extract tables.
* Can work with text positions and coordinates.
* Useful for complex PDFs.

### Best Use Case

Use **PDFPlumber** when:

* The PDF has tables.
* Layout matters.
* Text position matters.
* You need structured extraction from forms, reports, or invoices.

### Limitations

* Still depends on the PDF containing actual text.
* Not enough for purely scanned PDFs unless OCR is added.
* May require more code than higher-level document parsing libraries.

### Exam Shortcut

> Choose **PDFPlumber** when the question says tables, layout, coordinates, forms, or structured PDF extraction.

---

## unstructured

### Purpose

`unstructured` is a Python library used to extract and structure content from unstructured documents.

It is commonly used for preparing documents for RAG pipelines.

### What It Can Handle

* PDFs
* PDFs with text and images
* Word documents
* HTML
* Emails
* Images
* Mixed-content documents

### Strengths

* Designed for messy real-world documents.
* Useful for RAG document preprocessing.
* Can handle PDFs with both text and images.
* Requires less custom code compared to combining multiple lower-level tools.
* Extracts document content into elements that can be chunked and embedded.

### Best Use Case

Use **`unstructured`** when:

* The source documents are PDFs.
* PDFs contain both text and images.
* You want the least amount of code.
* You are preparing documents for a RAG application.
* You want a higher-level parsing library instead of manually handling text, images, and layouts.

### Exam Shortcut

> Choose **`unstructured`** when the question says:
> **PDFs contain both text and images** + **least amount of lines of code** + **RAG application**.

### Exam Trap

If the options are:

* `unstructured`
* `numpy`
* `beautifulsoup`

And the question says:

> RAG application, source documents are PDFs, PDFs contain text and images, least amount of code.

The correct answer is:

```text
unstructured
```

Why:

* `unstructured` is designed for document parsing.
* `numpy` is for numerical computing.
* `beautifulsoup` is for HTML/XML, not PDFs.

---

## PyPDF2 vs PDFPlumber vs unstructured

| Feature                | PyPDF2     | PDFPlumber           | unstructured                                 |
| ---------------------- | ---------- | -------------------- | -------------------------------------------- |
| Simple text extraction | Good       | Good                 | Good                                         |
| PDF splitting/merging  | Good       | Not main use         | Not main use                                 |
| Layout awareness       | Weak       | Stronger             | Good                                         |
| Table extraction       | Weak       | Better               | Good                                         |
| Text coordinates       | Weak       | Better               | Not the main exam focus                      |
| PDFs with images       | Weak       | Limited              | Better                                       |
| Scanned PDFs           | No         | No, unless OCR added | Better with OCR/document processing pipeline |
| Ease of use for RAG    | Moderate   | Moderate             | Strong                                       |
| Exam keyword           | Simple PDF | Tables / layout      | PDF + text/images + least code               |

---

# 4. OCR Parsing

## pytesseract

### Purpose

pytesseract is a Python wrapper around Tesseract OCR.

OCR means **Optical Character Recognition**.

### Strengths

* Extracts text from images.
* Works with scanned PDFs after converting pages to images.
* Useful when there is no embedded text layer.

### Best Use Case

Use **pytesseract** when:

* The PDF is scanned.
* The document is an image.
* Text is inside screenshots.
* Traditional PDF text extraction returns nothing.

### Limitations

* OCR can be slower.
* Accuracy depends on image quality.
* May struggle with handwriting, poor scans, rotated pages, or complex tables.

### Exam Shortcut

> Choose **pytesseract** when the document is scanned or image-based.

---

# 5. Databricks AI-Based Document Parsing

## ai_parse_document

### Purpose

`ai_parse_document` is a Databricks AI function used to parse unstructured documents into structured content.

It can extract text, tables, layout information, metadata, and other structured signals from files such as PDFs, images, Word documents, and PowerPoint files.

### What It Can Handle

* PDFs
* Images
* DOC/DOCX
* PPT/PPTX
* Complex layouts
* Tables
* Figures
* Mixed text-image content
* Layout metadata

### Best Use Case

Use **ai_parse_document** when:

* You are working inside Databricks.
* You need high-quality parsing for PDFs or complex documents.
* You want structured output for RAG.
* You need to preserve document layout.
* You need to parse tables, figures, headers, footers, and page structure.
* Traditional tools like PyPDF2 or PDFPlumber are not enough.

### Exam Shortcut

> Choose **ai_parse_document** for Databricks-native, AI-powered parsing of complex documents.

---

# 6. Full Comparison Table

| Tool              | Best For                                     | Input Type                     | Handles Tables?            | Handles Images/Scans?         | Layout Aware?        | Exam Keyword                |
| ----------------- | -------------------------------------------- | ------------------------------ | -------------------------- | ----------------------------- | -------------------- | --------------------------- |
| BeautifulSoup     | Easy HTML/XML parsing                        | HTML/XML                       | HTML tables only           | No                            | Basic structure      | Webpage / HTML              |
| LXML              | Fast HTML/XML parsing                        | HTML/XML                       | HTML/XML tables            | No                            | Strong XML structure | Large XML / performance     |
| PyPDF2            | Simple PDF text and PDF manipulation         | Text-based PDF                 | Weak                       | No                            | Weak                 | Simple PDF                  |
| PDFPlumber        | Structured PDF extraction                    | Text-based PDF                 | Better                     | No                            | Yes                  | Tables / layout             |
| pytesseract       | OCR                                          | Images / scanned PDFs          | Weak unless post-processed | Yes                           | Limited              | Scanned document            |
| unstructured      | RAG-friendly document parsing with less code | PDF, DOCX, HTML, email, images | Yes                        | Better than basic PDF parsers | Yes                  | PDF + images + least code   |
| ai_parse_document | Databricks-native AI document parsing        | PDF, image, DOCX, PPTX         | Yes                        | Yes                           | Yes                  | Databricks document parsing |

---

# 7. Exam Decision Tree

## Step 1: Is the source HTML or XML?

Choose:

* **BeautifulSoup** if ease of use matters.
* **LXML** if speed, XPath, or complex XML matters.

---

## Step 2: Is the source a simple text-based PDF?

Choose:

* **PyPDF2**

---

## Step 3: Is the PDF structured with tables or layout?

Choose:

* **PDFPlumber**

---

## Step 4: Does the PDF contain both text and images, and the question asks for least amount of code?

Choose:

* **unstructured**

---

## Step 5: Is the PDF scanned or image-based?

Choose:

* **pytesseract** or OCR.

---

## Step 6: Is the question Databricks-native and about complex document parsing?

Choose:

* **ai_parse_document**

---

# 8. Common Exam Traps

## Trap 1: PDF parser vs OCR

If a PDF is scanned, tools like PyPDF2 and PDFPlumber may not work well because there is no embedded text.

Correct answer:

> Use OCR, such as pytesseract, unstructured with OCR support, or a Databricks AI document parsing tool.

---

## Trap 2: BeautifulSoup vs LXML

Both parse HTML/XML.

Choose:

* **BeautifulSoup** for ease of use.
* **LXML** for speed and complex XML.

---

## Trap 3: PyPDF2 vs PDFPlumber

Both work with PDFs.

Choose:

* **PyPDF2** for simple text extraction or PDF manipulation.
* **PDFPlumber** for tables, layout, and text positioning.

---

## Trap 4: BeautifulSoup vs unstructured

BeautifulSoup is used for HTML/XML.

unstructured is used for messy documents such as PDFs, Word docs, emails, and images.

If the question says:

> PDFs with text and images for RAG, least code

Choose:

> **unstructured**

---

## Trap 5: Traditional parsing vs AI parsing

Traditional parsers extract text.

AI-based document parsing can better handle:

* Complex layouts.
* Tables.
* Figures.
* Mixed content.
* Business documents.
* Downstream RAG preparation.

Choose **ai_parse_document** when the question is Databricks-native or mentions complex document understanding.

---

# 9. What Else to Know for the Exam

## A. Parsing impacts RAG quality

Poor parsing leads to poor chunking, poor retrieval, and poor answers.

Example:

```text
Bad parsing → broken tables → bad chunks → bad embeddings → bad retrieval → hallucinated answer
```

---

## B. Parsing is before chunking

Do not confuse parsing with chunking.

| Step       | Meaning                                                           |
| ---------- | ----------------------------------------------------------------- |
| Parsing    | Extract text, tables, layout, images, and metadata from raw files |
| Chunking   | Split parsed content into smaller pieces                          |
| Embedding  | Convert chunks into vectors                                       |
| Retrieval  | Find relevant chunks                                              |
| Generation | LLM writes the final answer                                       |

---

## C. Metadata matters

Good parsing should preserve useful metadata such as:

* File name
* Page number
* Section heading
* Table location
* Document type
* Creation date
* Source path

This helps retrieval and answer grounding.

---

## D. Tables need special handling

Tables are often damaged by simple text extraction.

For tables, prefer:

* PDFPlumber for traditional Python parsing.
* unstructured for RAG-friendly document extraction with less code.
* ai_parse_document for Databricks-native AI parsing.
* Layout-aware parsing when available.

---

## E. Scanned documents need OCR

If there is no text layer, use OCR.

Signs that OCR is needed:

* Text cannot be selected in the PDF.
* PyPDF2 extracts blank output.
* PDF is made of page images.
* File is a screenshot or scan.

---

# 10. One-Line Memory Guide

| If the question says...              | Pick...                                        |
| ------------------------------------ | ---------------------------------------------- |
| HTML webpage                         | BeautifulSoup                                  |
| Large/complex XML                    | LXML                                           |
| Simple PDF text                      | PyPDF2                                         |
| PDF tables/layout                    | PDFPlumber                                     |
| Scanned document/image               | pytesseract                                    |
| PDF with text and images, least code | unstructured                                   |
| RAG document preprocessing           | unstructured                                   |
| Databricks complex document parsing  | ai_parse_document                              |
| Preserve page/table structure        | PDFPlumber, unstructured, or ai_parse_document |
| Extract text from image              | OCR / pytesseract                              |
| Numerical computation                | numpy, but not for parsing                     |

---

# 11. Final Summary

For the exam, remember:

* **BeautifulSoup** = easy HTML/XML parsing.
* **LXML** = faster HTML/XML parsing, better for complex XML.
* **PyPDF2** = simple PDF text extraction and PDF manipulation.
* **PDFPlumber** = PDF tables, layout, and coordinates.
* **pytesseract** = OCR for scanned PDFs and images.
* **unstructured** = document parsing for messy PDFs, text/images, and RAG preprocessing with less code.
* **ai_parse_document** = Databricks-native AI parsing for complex documents and RAG workflows.

The most important exam pattern is:

> Match the parser to the document type, complexity, and downstream GenAI need.
