from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
import time
import re
import pdfplumber

import pandas as pd
# from pypdf import PdfReader


def normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and line breaks."""
    return re.sub(r"\s+", " ", text).strip()

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

            normalized_text = normalize_text(raw_text)

            pages.append({
                "page": number,
                "raw_text": raw_text,
                "text": normalized_text,
            })

    return pages


def group_word_lines(words: list[dict], tolerance: float = 3.0) -> list[list]:
    lines = []

    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(word["top"] - lines[-1][-1]["top"]) <= tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def inspect_column_gutter(words, page_width, gutter_ratio=0.02):
    # Measure words occupancy neear the horizontal center. Returns counts and a preliminary two-column identification. 
    middle = page_width / 2
    half_gutter = page_width * gutter_ratio/2

    gutter_right = middle - half_gutter
    gutter_left = middle + half_gutter

    left = 0
    right = 0
    crossing = 0

    for word in words:
        x0 = word["x0"]
        x1 = word["x1"]

        if x1 < gutter_right:
            left += 1
        elif x0 > gutter_left:
            right += 1
        else:
            crossing += 1
    total = len(words)

    crossing_ratio = crossing / total if total else 0

    likely_two_columns = (
        total >= 20
        and left >= 8
        and right >= 8
        and crossing_ratio < 0.05
    )

    return {
        "left": left,
        "right": right,
        "crossing": crossing,
        "total": total,
        "crossing_ratio": crossing_ratio,
        "likely_two_columns": likely_two_columns,
        "gutter_bounds": (gutter_right, gutter_left),
    }

def split_column_words(words, gutter_bounds):
    left_words = []
    right_words = []

    gutter_left, gutter_right = gutter_bounds

    for word in words:
        x0 = word["x0"]
        x1 = word["x1"]

        if x1 < gutter_left:
            left_words.append(word)
        elif x0 > gutter_right:
            right_words.append(word)
        else:
            # Word is crossing the gutter, decide based on center position
            word_center = (x0 + x1) / 2
            if word_center < (gutter_left + gutter_right) / 2:
                left_words.append(word)
            else:
                right_words.append(word)

    return left_words, right_words

def main():
    print("Starting PDF extraction...")
    start_time = time.perf_counter()

    file_path = Path(__file__).resolve().parent / "dataset.csv"
    dataset = read_csv_dataset(file_path)

    pdf_url = dataset["Direct PDF URL"].iloc[4]
    pdf_content = read_pdf(pdf_url)

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        page = pdf.pages[8]  # PDF page 9

        body_top = page.height * 0.30
        print(f"Body top: {body_top}")
        body = page.crop((0, body_top, page.width, page.height))

        # print("\n--- PDFPLUMBER BODY TEXT ---")
        # print(body.extract_text()[:1500])

        words = body.extract_words()

        results = inspect_column_gutter(words, page.width)

        # for key, value in results.items():
        #     print(f"{key}: {value}")
        
        left_words, right_words = split_column_words(words, results["gutter_bounds"])

        print("Left words:", len(left_words))
        print("Right words:", len(right_words))

        left_lines = group_word_lines(left_words)
        right_lines = group_word_lines(right_words)

        print("\n--- LEFT COLUMN ---")
        for line in left_lines[:10]:
            print(" ".join(w["text"] for w in line))

        print("\n--- RIGHT COLUMN ---")
        for line in right_lines[:10]:
            print(" ".join(w["text"] for w in line))

        print("Page width:", page.width)
        print("Page height:", page.height)
        print("Total words:", len(words))

        # df_words = pd.DataFrame(words)
        # # print(df_words[["text", "x0", "x1", "top", "bottom"]].head(50))

        # lines = group_word_lines(words)
        # print(f"Total lines: {len(lines)}")

        # for i, line in enumerate(lines, start=1):
        #     line_text = " ".join(word["text"] for word in line)
        #     print(f"Line {i + 1}: {line_text}")

    # pages = extract_pages(pdf_content)

    # total_characters = sum(len(page["text"]) for page in pages)
    # print(f"Extracted {len(pages)} pages, {total_characters} characters")

    # for page in pages[8:9]: 
    #     print(f"\n--- PDF page {page['page']} ---")
    #     # print(page["text"])
    #     print(f"Raw text: {page['raw_text']}")

    # print(f"Total time: {time.perf_counter() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()