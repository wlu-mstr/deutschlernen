# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A single-file Python tkinter desktop GUI application for extracting and reviewing vocabulary from the "Nicos Weg A1" German language textbook. The app has two modes:
- **Browse/Extract**: Read the source text, highlight words with mouse, extract to a word list
- **Learning Mode**: Review the extracted vocabulary in document order

## Commands

```powershell
# Windows - must use Python 3.11 (only version with bundled tkinter)
py -3.11 wort_extractor.py

# Or use the batch launcher
run_extractor.bat
```

No build, test, or lint commands — this is a standalone single-file Python script.

## Architecture

- **Single file**: `wort_extractor.py` (~1100 lines) contains all UI, parsing, persistence, and export logic
- **State**: Instance variables on `WordExtractor` class track lines, current position, extracted words, learning items
- **Two tabs**: `ttk.Notebook` with Browse/Extract tab and Learning Mode tab
- **Persistence**: Extracted words auto-saved to `extracted_words.json` on every change
- **Export**: Words saved to desktop as UTF-8-BOM encoded `.txt` files, sorted by source line number
- **Wordbook format**: Markdown-like structure with `## N` sections, `行号:N` metadata, and `###` subsections for breakdowns

## Key Classes

- `WordExtractor`: Main GUI controller — all UI construction in `_create_ui()`, all event handlers as methods
- `section_indices`: List of `(line_no, episode_title)` tuples for episode-level navigation
- `learning_items`: Parsed list of `{seq, line_no, text, details}` dicts from wordbook files

## Important Implementation Notes

- `context_size` variable controls how many lines above/below the current line are shown (default ±4)
- Line number display is 1-based in UI but stored 0-based internally
- Learning mode reads but never writes the user's wordbook files (read-only contract)
- The `_align_lines()` function is a reserved entry point for generating line-aligned copies of wordbooks
