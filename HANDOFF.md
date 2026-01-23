# Handoff Document - Audible Library React

**Date:** 2026-01-22
**Session Focus:** Fixing download/converted tracking, ASIN extraction, duplicate handling

---

## CRITICAL UNRESOLVED ISSUES

### 1. Duplicate Files - SCOPE IS LARGER THAN TSV SHOWS
The duplicates TSV only identifies 8 M4B duplicates, but investigation revealed:
- **~80+ author folders exist OUTSIDE `/Converted/Audiobook/`** (wrong location)
- **Same authors ALSO exist INSIDE `/Converted/Audiobook/`** (correct location)
- **Must audit:** duplicate M4B files, empty parent folders, AND duplicate AAXC source files in Downloads
- **TSV location:** `/data/converted/.repair_reports/repair_*_duplicates.tsv`
- **Pattern:** Files in `/Audiobook/Author/Title/` marked KEEP, files in `/Author/Title/` marked DELETE_CANDIDATE

**Action needed:** Dispatch agent to do full audit of both `/Converted/` and `/Downloads/` directories

### 2. Orphan Detection Still Broken
- UI orphan counts don't match filesystem reality
- Need to verify logic in `repair_pipeline.py`

### 3. Duplicates Resolution UI Not Built

**What EXISTS:**
- `repair_pipeline.py` generates TSV report at `/data/converted/.repair_reports/repair_*_duplicates.tsv`
- TSV columns: `asin | keep_or_delete | output_path | imported_at | reason`
- Logic marks files in `/Audiobook/Author/Title/` as KEEP, others as DELETE_CANDIDATE
- Reason field shows `chosen_by_repair` or `not_chosen_missing_audiobook_dir`
- `pick_best()` function scores duplicates (prefers /Audiobook/ path, newer import date)

**What NEEDS to be built:**
- API endpoint to read/parse the TSV report
- API endpoint to execute deletions (with folder cleanup)
- UI modal with preview, confirm, delete workflow
- Must handle: M4B + empty parent folders + potentially AAXC source files

---

## KEY INSIGHTS

### ASIN Lost During Conversion
- **Downloads:** `B002V0QCYU_The Final Empire...-AAX_22_64.aaxc` (has ASIN prefix)
- **Converted:** `The Final Empire Mistborn Book 1.m4b` (ASIN stripped!)
- **Fix applied:** AAXtoMP3 now embeds ASIN in metadata tags
- **Existing files:** Need title matching as fallback (implemented)

### File Naming Patterns
```
Downloads (60%): B002V0QCYU_Title-AAX_22_64.aaxc   (ASIN prefix)
Downloads (20%): 1250264294_Title-AAX_44_128.aaxc  (ISBN prefix)
Downloads (20%): Series_Folder/Episode files       (nested)
Converted:       /Audiobook/Author/Title/Title.m4b (correct)
Converted:       /Author/Title/Title.m4b           (WRONG - duplicates)
```

### Architecture (No Duplicate Code)
- AAXtoMP3 → WRITES chapters/ASIN to M4B file
- metadata_extractor → READS from M4B via ffprobe
- library_manager → SAVES to database (chapters, narrators, authors, technical info, cover)
- These are cleanly separated, no conflicts

### Metadata Persistence Flow
`library_manager.scan_book()` extracts and saves metadata to DB. It's called in TWO places:

1. **After conversion** (`job_manager.py:933`):
   ```python
   await self.library_manager.scan_book(session, asin)
   ```

2. **During repair** (`repair_pipeline.py`) when `repair_extract_metadata=true`:
   ```python
   for book in books:
       if book.local_path_converted and path.exists():
           await manager.scan_book(session, book.asin, force=False)
   ```

**Tables populated:** `Chapter`, `BookNarrator`, `BookAuthor`, `BookTechnical`, `BookAsset`, `BookSeries`

---

## COMPLETED THIS SESSION

| Item | Summary |
|------|---------|
| AAXtoMP3 fix | Added ASIN/AUDIBLE_ASIN metadata tags, moved extraction outside library_file_exists check |
| Title matcher | New `services/title_matcher.py` - fuzzy matching with 80% threshold, handles series suffixes |
| metadata_extractor | Now reads ASIN from M4B tags |
| Repair settings | Added to config.py, db models, and Settings UI |
| Repair integration | Metadata extraction runs during repair when flag enabled |

---

## FILES MODIFIED

- `core/AAXtoMP3` - ASIN metadata tags
- `core/config.py` - Repair settings (MoveFilesPolicy, flags)
- `db/models.py` - SettingsModel repair fields
- `services/repair_pipeline.py` - Title matcher integration, metadata extraction
- `services/title_matcher.py` - NEW FILE
- `services/metadata_extractor.py` - ASIN extraction
- `apps/web/src/types/settings.ts` - Repair settings types
- `apps/web/src/app/settings/page.tsx` - Repair Settings UI section
- `docker-compose.dev.yml` - /specs mount changed from :ro to rw

---

## REPAIR SETTINGS (New)

Added to Settings UI under "Repair Settings":
- `repair_extract_metadata` (bool, default: true) - Extract chapters/metadata from M4B
- `repair_delete_duplicates` (bool, default: false) - Auto-delete duplicates
- `repair_update_manifests` (bool, default: true) - Sync manifests with filesystem
- `move_files_policy` (enum: report_only | always_move | ask_each)

**DB migration needed** for new columns in `app_settings` table.

---

## PENDING TODOS

1. **Full duplicate audit** - Agent scan of both directories for complete picture
2. **Build duplicates resolution UI** - Modal with preview, confirm, delete
3. **Fix orphan detection** - Verify repair_pipeline logic

---

## QUICK REFERENCE

```bash
# Latest duplicates report
ls -t "/Volumes/Media/Audiobooks/Converted/.repair_reports/" | head -1

# Count misplaced author folders
ls "/Volumes/Media/Audiobooks/Converted/" | grep -v Audiobook | grep -v .repair | wc -l

# Dev environment
docker-compose -f docker-compose.dev.yml up
```
