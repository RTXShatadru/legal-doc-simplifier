# Hindi and English scans

SimplyDoc uses local Tesseract OCR for image pages, including PDFs whose text layer contains only a scanner watermark. Printed Hindi and English are supported. Handwriting, signatures, maps, seals and uncertain amounts need review in the original PDF.

## Windows setup

Install Tesseract using the Windows installer linked from the [Tesseract distribution page](https://github.com/UB-Mannheim/tesseract/wiki). Include Hindi and English language data. If Hindi is missing, download hin.traineddata from the [official language models](https://github.com/tesseract-ocr/tessdata_best) into the installation's tessdata folder.

The app automatically finds Tesseract in C:\Program Files\Tesseract-OCR, your local Programs folder, or the project-local .runtime/tesseract folder. For another installation location, set TESSERACT_CMD in .env to the full executable path. Running the executable with --list-langs must show hin and eng. Then restart SimplyDoc with .\start.ps1.

The development machine used for this update already has the engine and both models installed in the project-local .runtime folder. This runtime is excluded from Git and release ZIPs.

## Linux / Docker

The supplied Dockerfile installs the engine and both languages. For native Ubuntu/Debian runs:

    sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin

## Limits and results

Scanned uploads are limited to 12 image pages, 10 MB and a 90-second OCR deadline, with one scan processed at a time per server process. Native PDFs retain the 80-page limit. A busy server asks the user to retry. OCR images are temporary and removed after processing. The database stores extracted text and extraction metadata, not the uploaded PDF.

The report shows language, scanned pages, low-confidence warnings and pages with no readable text. Partially readable documents are accepted with coverage warnings. Wholly unreadable documents are rejected. Confidence scores are engine heuristics, not accuracy probabilities. Re-upload previous watermark-only documents to use the new extraction.

The local demo recognizes property-deed terminology and supports English/Hindi topic search. It does not translate Hindi or perform a complete risk assessment. Enable AI_PROVIDER=gemini and supply GEMINI_API_KEY for AI explanations; configure Voyage separately for semantic retrieval. Extraction warnings accompany the AI context.
