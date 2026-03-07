@echo off
REM Generate DOCUMENTATION.pdf from DOCUMENTATION.md using Pandoc.
REM Requires: Pandoc installed (https://pandoc.org) and a LaTeX engine (e.g. MiKTeX, TeX Live) for PDF.
REM Alternative: install md-to-pdf (npm install -g md-to-pdf) and run: md-to-pdf DOCUMENTATION.md

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

where pandoc >nul 2>&1
if errorlevel 1 (
    echo Pandoc not found. Install from https://pandoc.org or use:
    echo   npm install -g md-to-pdf
    echo   md-to-pdf "%SCRIPT_DIR%DOCUMENTATION.md"
    exit /b 1
)

pandoc DOCUMENTATION.md -o DOCUMENTATION.pdf --pdf-engine=xelatex -V geometry:margin=1in -V fontsize=11pt 2>nul
if errorlevel 1 (
    pandoc DOCUMENTATION.md -o DOCUMENTATION.pdf 2>nul
)
if exist DOCUMENTATION.pdf (
    echo Created: %SCRIPT_DIR%DOCUMENTATION.pdf
) else (
    echo PDF generation failed. Try: md-to-pdf DOCUMENTATION.md
    exit /b 1
)
