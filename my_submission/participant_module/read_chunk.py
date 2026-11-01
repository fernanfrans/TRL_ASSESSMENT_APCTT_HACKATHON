from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
import time
import re
import pdfplumber

import pandas as pd
# from pypdf import PdfReader


def read_csv_dataset(file_path: Path) -> pd.DataFrame:
    return pd.read_csv(file_path)


def read_pdf(source: Path | str) -> bytes:
    """Read PDF bytes from a local file or URL."""
    if isinstance(source, str) and source.startswith(("https://", "http://")):
        request = Request(source, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            return response.read()

    return Path(source).read_bytes()


def extract_pages(pdf_content: bytes) -> list[dict]:
    """Extract text while preserving PDF page numbers."""

    if b"%PDF-" not in pdf_content[:1024]:
        raise ValueError("The downloaded content is not a PDF.")

    pages = []

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):

            raw_text = page.extract_text(
                layout=False,
                x_tolerance=3,
                y_tolerance=3,
            ) or ""

            normalized_text = re.sub(r"\s+", " ", raw_text).strip()

            pages.append({
                "page": number,
                "raw_text": raw_text,
                "text": normalized_text,
            })

    return pages

def main():
    print("Starting PDF extraction...")
    start_time = time.perf_counter()

    file_path = Path(__file__).resolve().parent / "dataset.csv"
    dataset = read_csv_dataset(file_path)

    pdf_url = dataset["Direct PDF URL"].iloc[0]
    pdf_content = read_pdf(pdf_url)
    pages = extract_pages(pdf_content)

    total_characters = sum(len(page["text"]) for page in pages)
    print(f"Extracted {len(pages)} pages, {total_characters} characters")

    for page in pages[8:9]: 
        print(f"\n--- PDF page {page['page']} ---")
        # print(page["text"])
        print(f"Raw text: {page['raw_text']}")

    print(f"Total time: {time.perf_counter() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()