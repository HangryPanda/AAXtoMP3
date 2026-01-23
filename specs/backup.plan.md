  - CHAPTERn=HH:MM:SS.mmm (timestamp)                                                  
  - CHAPTERnNAME=Chapter Title (name)                                                  
                                                                                       
  And mp4chaps -i embeds them properly. As you can see from the ffprobe output, the M4B
   has chapters with tags.title:                                                       
  - "Opening Credits"                                                                  
  - "Chapter One - The Boy Who Lived"                                                  
  - "Chapter Two - The Vanishing Glass"                                                
  - etc.                                                                               
                                                                                       
  So chapter names are working correctly in your conversion pipeline.                  
                                                                                       
✻ Crunched for 39s                                                                     
                                                                                       
❯ you know what I just realized... the orignal extraction/conversion process           
  relies on the moving of aaxc files AND the manifest to keep track of                 
  downloaded/converted files. which tell the user of the AUdible library items         
  which items have been downloaded/converted. I think we broke this during our         
  attempts to build a gui (first in streamlit then in react)... can you tell me        
  how the the aaxtomp3 library works right now and how it handles files.               
                                                                                       
⏺ Let me explore the codebase to understand the current file handling flow.            
                                                                                       
⏺ Search(pattern: "apps/api/services/*.py")                                            
  ⎿  Found 9 files (ctrl+o to expand)                                                  
                                                                                       
⏺ Bash(ls -la "/Volumes/Brain_UGNAS/Jason                                              
      Vongsay/code-projects/audible-library-react/specs/")                             
  ⎿  total 8796                                                                        
     drwxrwxrwx  1 1000  owner      326 Jan 21 21:14 .                                 
     drwxrwxrwx  1 1000  owner      804 Jan 22 22:46 ..                                
     … +9 lines (ctrl+o to expand)                                                     
                                                                                       
⏺ Bash(head -100 "/Volumes/Brain_UGNAS/Jason                                           
      Vongsay/code-projects/audible-library-react/specs/download_manifest.json" | jq   
      '.' 2>/dev/null || head -100 "/Volumes/Brai…)                                    
  ⎿  {                                                                                 
       "1039403360": {                                                                 
         "asin": "1039403360",                                                         
     … +130 lines (ctrl+o to expand)                                                   
                                                                                       
⏺ Bash(head -50 "/Volumes/Brain_UGNAS/Jason                                            
      Vongsay/code-projects/audible-library-react/specs/converted_manifest.json" | jq  
      '.' 2>/dev/null)                                                                 
  ⎿  Error: Exit code 5                                                                
                                                                                       
⏺ Read(apps/api/services/job_manager.py)                                               
  ⎿  Read 982 lines                                                                    
                                                                                       
⏺ Now I have a full picture. Let me summarize the current state and the issues:        
                                                                                       
  Current File Handling Flow                                                           
                                                                                       
  Downloads (audible_client.py)                                                        
                                                                                       
  1. audible download saves to downloads_dir                                           
  2. Files: {ASIN}_{Title}-AAX_*.aaxc, .voucher, .jpg, -chapters.json                  
  3. Updates download_manifest.json with entry                                         
  4. Updates DB: Book.local_path_aax, Book.status = DOWNLOADED                         
                                                                                       
  Conversions (job_manager.py → converter_engine.py → AAXtoMP3)                        
                                                                                       
  1. Reads AAXC from downloads_dir                                                     
  2. Outputs M4B to converted_dir                                                      
  3. Updates DB: Book.local_path_converted, Book.status = COMPLETED                    
  4. Does NOT:                                                                         
    - Move AAXC to completed_dir                                                       
    - Update download_manifest.json                                                    
    - Update converted_manifest.json                                                   
                                                                                       
  The AAXtoMP3 Script's --complete_dir Option                                          
                                                                                       
  # Lines 1010-1016: Moves AAXC after conversion if --complete_dir is set              
  if [[ "x${completedir}" != "x"  ]]; then                                             
      mv "${aax_file}" "${completedir}"                                                
  fi                                                                                   
                                                                                       
  What's Broken                                                                        
  ┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
  │          Feature          │     Original CLI Flow     │     Current GUI Flow      │
  ├───────────────────────────┼───────────────────────────┼───────────────────────────┤
  │ AAXC location after       │ Moved to completed_dir    │ Stays in downloads_dir    │
  │ convert                   │                           │                           │
  ├───────────────────────────┼───────────────────────────┼───────────────────────────┤
  │ download_manifest.json    │ N/A (used file location)  │ Never updated after       │
  │                           │                           │ conversion                │
  ├───────────────────────────┼───────────────────────────┼───────────────────────────┤
  │ converted_manifest.json   │ N/A                       │ Never populated           │
  ├───────────────────────────┼───────────────────────────┼───────────────────────────┤
  │ Tracking "converted"      │ Check if AAXC in          │ DB only (manifests stale) │
  │ status                    │ completed_dir             │                           │
  └───────────────────────────┴───────────────────────────┴───────────────────────────┘
  The Disconnect                                                                       
                                                                                       
  The GUI added two tracking systems that don't talk to each other:                    
  1. Manifests (JSON files) - for file-based tracking                                  
  2. Database - for UI state                                                           
                                                                                       
  After conversion:                                                                    
  - DB says "COMPLETED" ✓                                                              
  - download_manifest.json still has the entry ✗                                       
  - converted_manifest.json is empty ✗                                                 
  - AAXC file still in Downloads folder ✗                                              
                                                                                       
  This is why your stats are inconsistent - the repair pipeline was trying to reconcile
   these, but the conversion process never updates the manifests or moves files.       
                                                                                       
  Should I trace through where the manifests are supposed to be updated and fix the    
  conversion flow?                                                                     
                                                                                       
✻ Brewed for 1m 11s                                                                    
                                                                                       
❯ according to you in another instance we added a way to patch both the manifest       
  and the database. can you dispatch an agent to verify please.                        
                                                                                       
⏺ Explore(Find manifest + DB update code)                                              
  ⎿  Done (18 tool uses · 85.3k tokens · 2m 34s)                                       
                                                                                       
⏺ The agent found the issue. There are TWO separate conversion systems:                
                                                                                       
  System 1: app/worker.py (has full logic)                                             
                                                                                       
  - ✅ Updates converted_manifest.json after conversion                                
  - ✅ Moves AAXC to completed_dir (if move_after_complete enabled)                    
  - ✅ Full manifest reconciliation                                                    
                                                                                       
  System 2: apps/api/services/job_manager.py → converter_engine.py (GUI uses this)     
                                                                                       
  - ✅ Updates database (Book.status, Book.local_path_converted)                       
  - ❌ Does NOT update manifests                                                       
  - ❌ Does NOT move AAXC files                                                        
                                                                                       
  The GUI-based conversion only updates the database, not the manifests!               
                                                                                       
  The repair_pipeline.py was added to reconcile this gap - it scans the filesystem and 
  updates both manifests during a repair job. But it's reactive (runs on demand), not  
  proactive (after each conversion).                                                   
                                                                                       
  Let me verify this by checking if there's any manifest update in job_manager's       
  conversion flow:                                                                     
                                                                                       
⏺ Search(pattern: "manifest|download_manifest|converted_manifest", path:               
        "apps/api/services/job_manager.py", output_mode: "content")                    
  ⎿  Found 5 lines (ctrl+o to expand)                                                  
                                                                                       
⏺ Confirmed. The job_manager.py only references manifests in the repair job context.   
  The _execute_download and _execute_conversion methods:                               
                                                                                       
  - Update the database ✅                                                             
  - Do NOT update manifests ❌                                                         
  - Do NOT move files to completed_dir ❌                                              
                                                                                       
  The Architecture Gap                                                                 
                                                                                       
  ┌─────────────────────────────────────────────────────────────┐                      
  │                    app/worker.py                            │                      
  │  (Standalone worker - NOT used by GUI)                      │                      
  │  ✅ Updates converted_manifest.json                         │                      
  │  ✅ Moves AAXC → completed_dir                              │                      
  └─────────────────────────────────────────────────────────────┘                      
                                                                                       
  ┌─────────────────────────────────────────────────────────────┐                      
  │  apps/api/services/job_manager.py → converter_engine.py     │                      
  │  (Used by React GUI)                                        │                      
  │  ✅ Updates DB (Book.status, local_path_converted)          │                      
  │  ❌ No manifest updates                                     │                      
  │  ❌ No file moving                                          │                      
  └─────────────────────────────────────────────────────────────┘                      
                                                                                       
  ┌─────────────────────────────────────────────────────────────┐                      
  │  apps/api/services/repair_pipeline.py                       │                      
  │  (Run manually via "Repair" button)                         │                      
  │  ✅ Scans filesystem                                        │                      
  │  ✅ Updates BOTH manifests                                  │                      
  │  ✅ Syncs DB with manifests                                 │                      
  │  → Patches the gap, but only when manually triggered        │                      
  └─────────────────────────────────────────────────────────────┘                      
                                                                                       
  Options to fix:                                                                      
  1. Add manifest update + file move logic to job_manager.py's _execute_conversion and 
  _execute_download                                                                    
  2. Auto-run repair after each conversion batch                                       
  3. Deprecate one system and consolidate                                              
                                                                                       
  Which approach would you prefer?                                                     
                                                                                       
✻ Churned for 3m 7s                                                                    
                                                                                       
❯ sigh... fucking Claude. Not you the other instance of you. we must support           
  both... power users may not want the gui experience. but the gui experience          
  should have feature parity with the the standalone worker... I'm not even sure       
  shy we aren't using the worker in the first place... i think at some point in        
  time you just assumed we didn't have the tooling so you created an entirely new      
  version.                                                                             
                                                                                       
⏺ Yeah, that's a classic AI mistake - "I don't see it immediately, so I'll build a new 
  one." Let me look at the worker.py to understand what we have and whether the GUI can
   just use it.                                                                        
                                                                                       
⏺ Read(app/worker.py)                                                                  
  ⎿  Read 823 lines                                                                    
                                                                                       
⏺ This is a fully-featured worker that does everything correctly:                      
                                                                                       
  app/worker.py - What It Has                                                          
  Feature: Conversion                                                                  
  Implementation: _convert_one() with proper AAXtoMP3 command building                 
  ────────────────────────────────────────                                             
  Feature: Manifest updates                                                            
  Implementation: load_converted_manifest() / save_converted_manifest()                
  ────────────────────────────────────────                                             
  Feature: File moving                                                                 
  Implementation: _move_sources_if_enabled() - moves AAXC/voucher/cover to             
  completed_dir                                                                        
  ────────────────────────────────────────                                             
  Feature: Validation                                                                  
  Implementation: validate_aaxc() with ffprobe                                         
  ────────────────────────────────────────                                             
  Feature: Auto-repair                                                                 
  Implementation: Re-downloads corrupt files automatically                             
  ────────────────────────────────────────                                             
  Feature: Retry logic                                                                 
  Implementation: Configurable max_retries with backoff                                
  ────────────────────────────────────────                                             
  Feature: Locking                                                                     
  Implementation: _try_acquire_lock() prevents duplicate conversions                   
  ────────────────────────────────────────                                             
  Feature: Output verification                                                         
  Implementation: _find_output_file() confirms M4B was created                         
  ────────────────────────────────────────                                             
  Feature: Batch operations                                                            
  Implementation: convert_batch(), download_batch()                                    
  ────────────────────────────────────────                                             
  Feature: Watch mode                                                                  
  Implementation: convert_watch() - continuous polling                                 
  ────────────────────────────────────────                                             
  Feature: Manifest sync                                                               
  Implementation: sync_manifest() - reconciles existing files                          
  CLI Commands Already Available                                                       
                                                                                       
  # Continuous watch mode                                                              
  python worker.py convert-watch --poll-seconds 10 --max-parallel 2                    
                                                                                       
  # Batch convert specific ASINs                                                       
  python worker.py convert-batch --asins ASIN1,ASIN2 --paths /path1,/path2             
  --max-parallel 3                                                                     
                                                                                       
  # Batch download                                                                     
  python worker.py download-batch --asins ASIN1,ASIN2 --max-parallel 3                 
                                                                                       
  # Sync manifest with existing files                                                  
  python worker.py sync-manifest                                                       
                                                                                       
  The Fix                                                                              
                                                                                       
  The GUI's job_manager.py should simply call the worker.py instead of reimplementing  
  everything poorly. Options:                                                          
                                                                                       
  1. Shell out to python worker.py convert-batch and monitor logs                      
  2. Import and call worker.convert_batch() / worker._convert_one() directly           
  3. Port the manifest/move logic from worker.py into job_manager.py                   
                                                                                       
  Which approach do you want to take?                                                  
                                                                                       
❯ those are all technically valid solutions... but what I want to build is an          
  enterprise-grade elegant and smart application. Not a hacky diy developer            
  prototype toy. While I understand this is solid vision, I must consider the          
  realities of achieving this with where we are today and the effort/time it takes     
  to achieve this vision. With this context... which option would you recommend        
  tht gets us close to the vision and doesn't require a lot of effort. do not act      
  just suggest a path forward and your rationale.                                      
                                                                                       
⏺ Recommendation: Option 3 - Port the manifest/move logic to job_manager.py            
                                                                                       
  Rationale                                                                            
                                                                                       
  1. Minimal disruption: The job_manager.py already has the right async architecture,  
  WebSocket integration, and database updates. We just need to add ~50-100 lines to    
  call manifest updates and file moves after successful operations.                    
  2. The worker.py has baggage: It uses synchronous code with ThreadPoolExecutor,      
  hardcoded paths (/data, /downloads), its own settings system (/data/settings.json),  
  and a different logging approach. Integrating it cleanly into the async FastAPI world
   would require significant adaptation.                                               
  3. The logic to port is simple:                                                      
    - Manifest update: ~20 lines (read JSON, update entry, write JSON)                 
    - File moving: ~15 lines (shutil.move for aaxc, voucher, cover, chapters.json)     
    - Output verification: Already exists in converter_engine.py                       
  4. Future-proofing: Once ported, you could extract these into a shared               
  conversion_service.py module that both worker.py and job_manager.py import from -    
  achieving true deduplication without a big-bang rewrite.                             
                                                                                       
  Effort Estimate                                                                      
                                                                                       
  - Add manifest update after download: ~30 min                                        
  - Add manifest update after conversion: ~30 min                                      
  - Add file moving to completed_dir: ~30 min                                          
  - Add setting for move_after_complete: ~15 min                                       
  - Testing: ~30 min                                                                   
                                                                                       
  Total: ~2-3 hours                                                                    
                                                                                       
  What You Get                                                                         
                                                                                       
  - Feature parity between CLI worker and GUI                                          
  - Manifests stay in sync with reality                                                
  - Files move out of Downloads after conversion                                       
  - Stats will be accurate without needing repair                                      
  - Foundation for future shared service extraction                                    
                                                                                       
  Want me to proceed with this approach?                                               
                                                                                       
❯ alright please create a plan to dispatch agents to complete the implementation       
  in parallel, where applicable. you must write the prompts for the implementation     
  agent to copy and paste. the instructions MUST LEAVE NO ROOM FOR INTERPRETATION      
  OR IF THEY MUST INTERPRET WE DIRECT THEM TO LEAD THEM TO HOW WE WANT THEM TO         
  INTERPRET. They must first follow test-driven development practices. they must       
  first dispatch explore agent to give them context of what exists today, so they      
  use consistent naming conventions. After they have written the code they are to      
  dispatch an agent to perform a consistency and error check and patch the work        
  that was performed. then and only then can they claim their work is done. You        
  don't write the code for the agents in the meta prompt, you instead provide          
  instructions and explicit guidance and guards to follow.                             
                                                                                       
⏺ Let me first read the existing plan file to understand what was previously planned.  
                                                                                       
⏺ Reading Plan(~/.claude/plans/mighty-moseying-rabin.md)                               
  ⎿  Read 313 lines                                                                    
                                                                                       
⏺ This is a different task from the previous plan. I'll overwrite it with a new plan   
  for porting manifest/move logic to job_manager.py.                                   
                                                                                       
⏺ Updated plan                                                                         
  ⎿  /plan to preview                                                                  
        1 -# Plan: Fix Download/Converted Tracking                                     
        1 +# Plan: Port Manifest/Move Logic from worker.py to job_manager.py           
        2                                                                              
        3 -## Problem Summary                                                          
        3 +## Problem Statement                                                        
        4                                                                              
        5 -Current stats show inconsistencies:                                         
        6 -- **Downloaded**: 207 (should be higher - doesn't account for books w       
          -here AAX was deleted after conversion)                                      
        7 -- **On disk**: 323 AAX/AAXC files                                           
        8 -- **Converted**: 241 (but 366 M4B files exist on disk)                      
        9 -- **Orphans**: 6 (underreported)                                            
        5 +The GUI-based conversion/download flow (`job_manager.py`) does NOT up       
          +date manifests or move files after operations complete. The standalon       
          +e `worker.py` has this logic but the GUI bypasses it entirely.              
        6                                                                              
       11 -## Root Cause                                                               
        7 +**Current State:**                                                          
        8 +- `worker.py`: Updates `converted_manifest.json`, moves AAXC to `comp       
          +leted_dir` ✅                                                               
        9 +- `job_manager.py`: Only updates database, manifests stay stale ❌          
       10                                                                              
       13 -1. **Stats are calculated from manifests**, which are stale and incom       
          -plete                                                                       
       14 -2. **Downloaded count** only counts books where AAX/AAXC file still e       
          -xists                                                                       
       15 -   - Doesn't infer download from M4B existence (if M4B exists, downlo       
          -ad must have happened)                                                      
       16 -3. **Converted count** only counts manifest entries, missing ~125 M4B       
          - files not in manifest                                                      
       17 -4. **Repair tool** updates database but doesn't update manifests            
       11 +**Goal:** Achieve feature parity so GUI operations update manifests a       
          +nd optionally move files.                                                   
       12                                                                              
       19 -## Design Decision                                                          
       13 +---                                                                         
       14                                                                              
       21 -Support both workflows:                                                     
       22 -- **Local-only**: Uses manifests (no server required)                       
       23 -- **Server-driven**: Uses database as source of truth                       
       15 +## Implementation Strategy                                                  
       16                                                                              
       25 -**Solution**: Repair tool updates BOTH manifests AND database to keep       
          - them in sync.                                                              
       17 +Two parallel workstreams that can be executed simultaneously:               
       18                                                                              
       19 +| Agent | Scope | Files Modified |                                          
       20 +|-------|-------|----------------|                                          
       21 +| **Agent A** | Download manifest updates | `job_manager.py`, `config       
          +.py`, tests |                                                               
       22 +| **Agent B** | Conversion manifest updates + file moving | `job_mana       
          +ger.py`, `config.py`, tests |                                               
       23 +                                                                            
       24 +After both complete, a **Consistency Check Agent** validates the work       
          +.                                                                           
       25 +                                                                            
       26  ---                                                                         
       27                                                                              
       29 -## Proposed Changes                                                         
       28 +## Critical Files Reference                                                 
       29                                                                              
       31 -### 1. ASIN Extraction Strategy                                             
       30 +- **Source of truth (existing logic):** `/Volumes/Brain_UGNAS/Jason V       
          +ongsay/code-projects/audible-library-react/app/worker.py`                   
       31 +- **Target file:** `/Volumes/Brain_UGNAS/Jason Vongsay/code-projects/       
          +audible-library-react/apps/api/services/job_manager.py`                     
       32 +- **Config file:** `/Volumes/Brain_UGNAS/Jason Vongsay/code-projects/       
          +audible-library-react/apps/api/core/config.py`                              
       33 +- **Download manifest:** `/Volumes/Brain_UGNAS/Jason Vongsay/code-pro       
          +jects/audible-library-react/specs/download_manifest.json`                   
       34 +- **Converted manifest:** `/Volumes/Brain_UGNAS/Jason Vongsay/code-pr       
          +ojects/audible-library-react/specs/converted_manifest.json`                 
       35                                                                              
       33 -**Priority order for extracting ASIN from converted files:**                
       36 +---                                                                         
       37                                                                              
       35 -1. **M4B files → Metadata tags** (preferred)                                
       36 -   - Use ffprobe to read embedded metadata                                  
       37 -   - Look for ASIN in custom tags or comment field                          
       38 +## Agent A Prompt: Download Manifest Updates                                
       39                                                                              
       39 -2. **Non-M4B files → Title matching**                                       
       40 -   - Match normalized title against Book records in database                
       41 -   - Handle transformed filenames carefully (special chars, etc.)           
       40 +```                                                                         
       41 +## Task: Add Download Manifest Updates to job_manager.py                    
       42                                                                              
       43 -3. **Filename pattern fallback**                                            
       44 -   - Parse `ASIN_title.ext` pattern if present                              
       43 +You are implementing download manifest updates for the GUI flow. This       
          + ensures feature parity with the standalone worker.py.                      
       44                                                                              
       46 -**Future enhancement**: During conversion, generate two filename form       
          -ats:                                                                        
       47 -- Internal: `{ASIN}_{sanitized_title}.m4b` (for verification/tracking       
          -)                                                                           
       48 -- Display: `{author} - {title}.m4b` (for user-facing file browsers)         
       45 +### PHASE 1: EXPLORATION (MANDATORY)                                        
       46                                                                              
       50 -### 2. File Move Settings                                                   
       47 +Before writing ANY code, dispatch an Explore agent with this prompt:        
       48                                                                              
       52 -Add a configurable setting for handling misplaced files:                    
       49 +"Search the codebase to understand:                                         
       50 +1. Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-libr       
          +ary-react/app/worker.py - specifically the download_batch() and _down       
          +load_one() functions to understand how manifests are updated after do       
          +wnloads                                                                     
       51 +2. Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-libr       
          +ary-react/apps/api/services/job_manager.py - specifically the _execut       
          +e_download() method to understand the current flow                          
       52 +3. Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-libr       
          +ary-react/specs/download_manifest.json to understand the manifest sch       
          +ema (first 50 lines is sufficient)                                          
       53 +4. Find existing test files for job_manager.py or similar services to       
          + understand testing patterns                                                
       54 +5. Check apps/api/core/config.py for the Settings class and manifest_       
          +dir setting                                                                 
       55                                                                              
       54 -```python                                                                   
       55 -class MoveFilesPolicy(str, Enum):                                           
       56 -    REPORT_ONLY = "report_only"      # Just log, don't move                 
       57 -    ALWAYS_MOVE = "always_move"      # Auto-move without prompting          
       58 -    ASK_EACH = "ask_each"            # Prompt before each move (API r       
          -eturns list for user confirmation)                                          
       59 -```                                                                         
       56 +Report:                                                                     
       57 +- The exact manifest JSON schema used                                       
       58 +- The exact location in _execute_download() where the manifest update       
          + should be added (after which line/block)                                   
       59 +- The naming conventions used for helper functions in job_manager.py        
       60 +- The testing patterns used in this codebase"                               
       61                                                                              
       61 -Add to Settings:                                                            
       62 -```python                                                                   
       63 -move_files_policy: MoveFilesPolicy = Field(                                 
       64 -    default=MoveFilesPolicy.REPORT_ONLY,                                    
       65 -    description="How to handle misplaced converted files"                   
       66 -)                                                                           
       67 -```                                                                         
       62 +Wait for the Explore agent to complete before proceeding.                   
       63                                                                              
       69 -### 3. Enhance `apply_repair()` to Update Manifests                         
       64 +### PHASE 2: TEST-DRIVEN DEVELOPMENT                                        
       65                                                                              
       71 -**File**: `apps/api/services/repair_pipeline.py`                            
       66 +You MUST write tests BEFORE implementation.                                 
       67                                                                              
       73 -```python                                                                   
       74 -async def apply_repair(session: AsyncSession, *, job_id: UUID | None        
          -= None) -> dict[str, Any]:                                                  
       75 -    # ... existing setup ...                                                
       68 +**Test file location:** Create `/Volumes/Brain_UGNAS/Jason Vongsay/co       
          +de-projects/audible-library-react/apps/api/tests/services/test_job_ma       
          +nager_download_manifest.py`                                                 
       69                                                                              
       77 -    # === NEW: Manifest reconciliation ===                                  
       70 +**Tests to write:**                                                         
       71                                                                              
       79 -    # A. Update download_manifest from filesystem                           
       80 -    manifest_updates_download = 0                                           
       81 -    for asin, files in download_index.items():                              
       82 -        aax_path = files.get("aaxc_path") or files.get("aax_path")          
       83 -        if aax_path:                                                        
       84 -            existing = download_raw.get(asin)                               
       85 -            if not existing or existing.get("status") != "success":         
       86 -                download_raw[asin] = {                                      
       87 -                    "status": "success",                                    
       88 -                    "aaxc_path": aax_path,                                  
       89 -                    "voucher_path": files.get("voucher_path"),              
       90 -                    "cover_path": files.get("cover_path"),                  
       91 -                    "discovered_at": datetime.utcnow().isoformat(),         
       92 -                    "source": "filesystem_scan",                            
       93 -                }                                                           
       94 -                manifest_updates_download += 1                              
       72 +1. `test_download_updates_manifest_on_success` - Verify manifest JSON       
          + is updated with correct schema after successful download                   
       73 +2. `test_download_manifest_entry_schema` - Verify the entry contains:       
          + asin, title, aaxc_path, voucher_path, cover_path, downloaded_at, sta       
          +tus                                                                         
       74 +3. `test_download_does_not_update_manifest_on_failure` - Verify faile       
          +d downloads don't corrupt manifest                                          
       75 +4. `test_download_manifest_preserves_existing_entries` - Verify updat       
          +ing doesn't clobber other entries                                           
       76                                                                              
       96 -    # B. Scan M4B files and update converted_manifest                       
       97 -    m4b_scan_results = await _scan_m4b_with_asin(settings, session)         
       98 -    manifest_updates_converted = 0                                          
       99 -    for m4b_info in m4b_scan_results:                                       
      100 -        asin = m4b_info["asin"]                                             
      101 -        output_path = m4b_info["path"]                                      
      102 -        # Check if already in manifest                                      
      103 -        if not _manifest_has_conversion(converted_raw, asin, output_p       
          -ath):                                                                       
      104 -            key = f"{output_path}"  # Use path as key                       
      105 -            converted_raw[key] = {                                          
      106 -                "status": "success",                                        
      107 -                "asin": asin,                                               
      108 -                "title": m4b_info.get("title"),                             
      109 -                "output_path": output_path,                                 
      110 -                "discovered_at": datetime.utcnow().isoformat(),             
      111 -                "source": "filesystem_scan",                                
      112 -            }                                                               
      113 -            manifest_updates_converted += 1                                 
       77 +**Test structure requirements:**                                            
       78 +- Use pytest and pytest-asyncio                                             
       79 +- Mock the filesystem and audible_client                                    
       80 +- Use tmp_path fixture for manifest file                                    
       81 +- Follow existing test patterns found in exploration                        
       82                                                                              
      115 -    # C. Infer download status from M4B existence                           
      116 -    inferred_downloads = 0                                                  
      117 -    for m4b_info in m4b_scan_results:                                       
      118 -        asin = m4b_info["asin"]                                             
      119 -        if asin and asin not in download_raw:                               
      120 -            download_raw[asin] = {                                          
      121 -                "status": "success",                                        
      122 -                "inferred_from": "m4b_exists",                              
      123 -                "discovered_at": datetime.utcnow().isoformat(),             
      124 -            }                                                               
      125 -            inferred_downloads += 1                                         
       83 +### PHASE 3: IMPLEMENTATION                                                 
       84                                                                              
      127 -    # D. Write updated manifests                                            
      128 -    download_manifest_path.write_text(json.dumps(download_raw, indent       
          -=2, ensure_ascii=False))                                                    
      129 -    converted_manifest_path.write_text(json.dumps(converted_raw, inde       
          -nt=2, ensure_ascii=False))                                                  
       85 +**Location:** `apps/api/services/job_manager.py` in the `_execute_dow       
          +nload()` method                                                             
       86                                                                              
      131 -    # ... existing database update logic ...                                
       87 +**What to implement:**                                                      
       88                                                                              
      133 -    return {                                                                
      134 -        # ... existing fields ...                                           
      135 -        "manifest_updates_download": manifest_updates_download,             
      136 -        "manifest_updates_converted": manifest_updates_converted,           
      137 -        "inferred_downloads": inferred_downloads,                           
      138 -    }                                                                       
       89 +1. Add a helper function `_update_download_manifest(asin: str, result       
          +: dict) -> None`:                                                           
       90 +   - Read existing manifest from `self.settings.manifest_dir / "downl       
          +oad_manifest.json"`                                                         
       91 +   - Add/update entry with schema matching worker.py:                       
       92 +     ```python                                                              
       93 +     {                                                                      
       94 +       "asin": asin,                                                        
       95 +       "title": title,                                                      
       96 +       "aaxc_path": str(local_aax),                                         
       97 +       "voucher_path": str(local_voucher),                                  
       98 +       "cover_path": str(local_cover),                                      
       99 +       "downloaded_at": datetime.utcnow().isoformat(),                      
      100 +       "status": "success"                                                  
      101 +     }                                                                      
      102 +     ```                                                                    
      103 +   - Write manifest back with `indent=2, ensure_ascii=False`                
      104 +   - Handle file not existing (create new dict)                             
      105 +   - Handle JSON decode errors gracefully (log warning, start fresh)        
      106 +                                                                            
      107 +2. Call `_update_download_manifest()` in the success block of `_execu       
          +te_download()`, specifically inside the `for res in results:` loop af       
          +ter `session.add(book)` but before `await session.commit()`                 
      108 +                                                                            
      109 +**Constraints:**                                                            
      110 +- Do NOT modify the database update logic - only ADD manifest update        
      111 +- Do NOT change method signatures                                           
      112 +- Do NOT add new dependencies                                               
      113 +- Use `self.settings.manifest_dir` for the manifest path (add to conf       
          +ig if missing)                                                              
      114 +- Log at INFO level when manifest is updated                                
      115 +                                                                            
      116 +### PHASE 4: CONSISTENCY CHECK                                              
      117 +                                                                            
      118 +After implementation, dispatch an agent with this prompt:                   
      119 +                                                                            
      120 +"Perform a consistency and error check on the download manifest imple       
          +mentation:                                                                  
      121 +                                                                            
      122 +1. Read the new test file and verify all tests follow pytest conventi       
          +ons                                                                         
      123 +2. Read the modified job_manager.py and verify:                             
      124 +   - The helper function follows the naming pattern of other helpers        
          +(underscore prefix)                                                         
      125 +   - Error handling is consistent with other methods                        
      126 +   - Logging follows existing patterns (uses logger.info, logger.warn       
          +ing)                                                                        
      127 +   - The manifest schema matches worker.py exactly                          
      128 +3. Run the tests: cd /Volumes/Brain_UGNAS/Jason Vongsay/code-projects       
          +/audible-library-react && python -m pytest apps/api/tests/services/te       
          +st_job_manager_download_manifest.py -v                                      
      129 +4. Check for any syntax errors: python -m py_compile apps/api/service       
          +s/job_manager.py                                                            
      130 +5. Report any inconsistencies or errors found and fix them"                 
      131 +                                                                            
      132 +Only claim completion after this check passes.                              
      133  ```                                                                         
      134                                                                              
      141 -### 4. Add M4B Scanning with ASIN Extraction                                
      135 +---                                                                         
      136                                                                              
      143 -```python                                                                   
      144 -async def _scan_m4b_with_asin(settings: Settings, session: AsyncSessi       
          -on) -> list[dict]:                                                          
      145 -    """Scan converted directory for M4B files and extract ASINs."""         
      146 -    results = []                                                            
      147 -    converted_dir = Path(settings.converted_dir)                            
      137 +## Agent B Prompt: Conversion Manifest Updates + File Moving                
      138                                                                              
      149 -    # Pre-fetch books for title matching                                    
      150 -    book_result = await session.execute(select(Book.asin, Book.title)       
          -)                                                                           
      151 -    title_to_asin = {_normalize_title_key(row[1]): row[0] for row in        
          -book_result.all() if row[1]}                                                
      139 +```                                                                         
      140 +## Task: Add Conversion Manifest Updates and File Moving to job_manag       
          +er.py                                                                       
      141                                                                              
      153 -    for m4b_path in converted_dir.rglob("*.m4b"):                           
      154 -        asin = None                                                         
      155 -        title = None                                                        
      142 +You are implementing conversion manifest updates AND post-conversion        
          +file moving for the GUI flow. This ensures feature parity with the st       
          +andalone worker.py.                                                         
      143                                                                              
      157 -        # 1. Try metadata tags (ffprobe)                                    
      158 -        asin, title = _extract_asin_from_metadata(m4b_path)                 
      144 +### PHASE 1: EXPLORATION (MANDATORY)                                        
      145                                                                              
      160 -        # 2. Try filename pattern                                           
      161 -        if not asin:                                                        
      162 -            asin = _extract_asin_prefix(m4b_path.name)                      
      146 +Before writing ANY code, dispatch an Explore agent with this prompt:        
      147                                                                              
      164 -        # 3. Try title matching                                             
      165 -        if not asin and title:                                              
      166 -            normalized = _normalize_title_key(title)                        
      167 -            asin = title_to_asin.get(normalized)                            
      148 +"Search the codebase to understand:                                         
      149 +1. Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-libr       
          +ary-react/app/worker.py - specifically:                                     
      150 +   - _convert_one() function to see how converted_manifest.json is up       
          +dated                                                                       
      151 +   - _move_sources_if_enabled() function to see how files are moved t       
          +o completed_dir                                                             
      152 +   - load_converted_manifest() and save_converted_manifest() helper f       
          +unctions                                                                    
      153 +2. Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-libr       
          +ary-react/apps/api/services/job_manager.py - specifically the _execut       
          +e_conversion() method                                                       
      154 +3. Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-libr       
          +ary-react/specs/converted_manifest.json to understand the manifest sc       
          +hema (first 50 lines)                                                       
      155 +4. Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-libr       
          +ary-react/apps/api/core/config.py for Settings class - check for comp       
          +leted_dir and move_after_complete settings                                  
      156                                                                              
      169 -        # 4. Try stem as title for matching                                 
      170 -        if not asin:                                                        
      171 -            normalized = _normalize_title_key(m4b_path.stem)                
      172 -            asin = title_to_asin.get(normalized)                            
      157 +Report:                                                                     
      158 +- The exact converted manifest JSON schema (key format and value fiel       
          +ds)                                                                         
      159 +- The files that _move_sources_if_enabled() moves (aaxc, voucher, cha       
          +pters.json, cover)                                                          
      160 +- Whether move_after_complete setting exists in config.py                   
      161 +- The exact location in _execute_conversion() where updates should be       
          + added"                                                                     
      162                                                                              
      174 -        results.append({                                                    
      175 -            "path": str(m4b_path),                                          
      176 -            "asin": asin,                                                   
      177 -            "title": title or m4b_path.stem,                                
      178 -            "matched_by": "metadata" if asin else "title" if asin els       
          -e "unknown",                                                                
      179 -        })                                                                  
      163 +Wait for the Explore agent to complete before proceeding.                   
      164                                                                              
      181 -    return results                                                          
      165 +### PHASE 2: TEST-DRIVEN DEVELOPMENT                                        
      166                                                                              
      167 +You MUST write tests BEFORE implementation.                                 
      168                                                                              
      184 -def _extract_asin_from_metadata(path: Path) -> tuple[str | None, str        
          -| None]:                                                                    
      185 -    """Extract ASIN and title from M4B metadata using ffprobe."""           
      186 -    try:                                                                    
      187 -        import subprocess                                                   
      188 -        result = subprocess.run(                                            
      189 -            ["ffprobe", "-v", "quiet", "-print_format", "json", "-sho       
          -w_format", str(path)],                                                      
      190 -            capture_output=True, text=True, timeout=10                      
      191 -        )                                                                   
      192 -        if result.returncode == 0:                                          
      193 -            data = json.loads(result.stdout)                                
      194 -            tags = data.get("format", {}).get("tags", {})                   
      195 -            asin = tags.get("ASIN") or tags.get("asin") or tags.get("       
          -AUDIBLE_ASIN")                                                              
      196 -            title = tags.get("title") or tags.get("TITLE")                  
      197 -            return asin, title                                              
      198 -    except Exception:                                                       
      199 -        pass                                                                
      200 -    return None, None                                                       
      201 -```                                                                         
      169 +**Test file location:** Create `/Volumes/Brain_UGNAS/Jason Vongsay/co       
          +de-projects/audible-library-react/apps/api/tests/services/test_job_ma       
          +nager_conversion_manifest.py`                                               
      170                                                                              
      203 -### 5. Update Stats Calculation in `compute_preview()`                      
      171 +**Tests to write:**                                                         
      172                                                                              
      205 -Use database as primary source for server workflow:                         
      173 +1. `test_conversion_updates_manifest_on_success` - Verify manifest is       
          + updated after successful conversion                                        
      174 +2. `test_conversion_manifest_entry_schema` - Verify entry contains: s       
          +tatus, asin, title, output_path, started_at, ended_at                       
      175 +3. `test_conversion_manifest_key_is_source_path` - Verify the key is        
          +the source AAXC path (matching worker.py)                                   
      176 +4. `test_conversion_does_not_update_manifest_on_failure` - Verify fai       
          +led conversions don't corrupt manifest                                      
      177 +5. `test_move_sources_moves_all_files` - Verify AAXC, voucher, chapte       
          +rs.json, and cover are moved                                                
      178 +6. `test_move_sources_respects_setting` - Verify files only move when       
          + move_after_complete=True                                                   
      179 +7. `test_move_sources_handles_missing_files` - Verify graceful handli       
          +ng when some files don't exist                                              
      180                                                                              
      207 -```python                                                                   
      208 -async def compute_preview(session: AsyncSession) -> RepairPreview:          
      209 -    # ... existing setup ...                                                
      181 +**Test structure requirements:**                                            
      182 +- Use pytest and pytest-asyncio                                             
      183 +- Mock the filesystem using tmp_path                                        
      184 +- Create actual test files for move tests                                   
      185 +- Follow existing test patterns                                             
      186                                                                              
      211 -    # Database-derived stats (source of truth for server workflow)          
      212 -    downloaded_db_total = (await session.execute(                           
      213 -        select(func.count()).select_from(Book).where(                       
      214 -            Book.status.in_([                                               
      215 -                BookStatus.DOWNLOADED, BookStatus.VALIDATED,                
      216 -                BookStatus.CONVERTING, BookStatus.COMPLETED                 
      217 -            ])                                                              
      218 -        )                                                                   
      219 -    )).scalar() or 0                                                        
      187 +### PHASE 3: IMPLEMENTATION                                                 
      188                                                                              
      221 -    converted_db_total = (await session.execute(                            
      222 -        select(func.count()).select_from(Book).where(                       
      223 -            Book.status == BookStatus.COMPLETED                             
      224 -        )                                                                   
      225 -    )).scalar() or 0                                                        
      189 +**Part A: Add move_after_complete setting to config.py**                    
      190                                                                              
      227 -    # ... keep filesystem stats for diagnostics ...                         
      191 +Location: `apps/api/core/config.py` in the Settings class                   
      192                                                                              
      229 -    return RepairPreview(                                                   
      230 -        # Primary stats (from database)                                     
      231 -        downloaded_total=downloaded_db_total,                               
      232 -        converted_total=converted_db_total,                                 
      233 -        # Diagnostic stats (from filesystem)                                
      234 -        downloaded_on_disk_total=downloaded_on_disk_total,                  
      235 -        downloaded_on_disk_remote_total=downloaded_on_disk_remote_tot       
          -al,                                                                         
      236 -        # ... rest ...                                                      
      237 -    )                                                                       
      193 +Add:                                                                        
      194 +```python                                                                   
      195 +move_after_complete: bool = Field(                                          
      196 +    default=False,                                                          
      197 +    description="Move source AAXC files to completed_dir after succes       
          +sful conversion"                                                            
      198 +)                                                                           
      199  ```                                                                         
      200                                                                              
      240 -### 6. Handle Misplaced Files                                               
      241 -                                                                            
      201 +Verify `completed_dir` setting already exists. If not, add:                 
      202  ```python                                                                   
      243 -async def _detect_misplaced_files(settings: Settings) -> list[dict]:        
      244 -    """Find M4B files not in the expected location."""                      
      245 -    misplaced = []                                                          
      246 -    expected_dir = Path(settings.converted_dir) / "Audiobook"               
      203 +completed_dir: Path = Field(                                                
      204 +    default=Path("/data/completed"),                                        
      205 +    description="Directory for completed source files"                      
      206 +)                                                                           
      207 +```                                                                         
      208                                                                              
      248 -    for m4b_path in Path(settings.converted_dir).rglob("*.m4b"):            
      249 -        if expected_dir not in m4b_path.parents:                            
      250 -            misplaced.append({                                              
      251 -                "current_path": str(m4b_path),                              
      252 -                "suggested_path": str(expected_dir / m4b_path.name),        
      253 -            })                                                              
      209 +**Part B: Add helper functions to job_manager.py**                          
      210                                                                              
      255 -    # Also check downloads dir for stray M4Bs                               
      256 -    for m4b_path in Path(settings.downloads_dir).rglob("*.m4b"):            
      257 -        misplaced.append({                                                  
      258 -            "current_path": str(m4b_path),                                  
      259 -            "suggested_path": str(expected_dir / m4b_path.name),            
      260 -        })                                                                  
      211 +Add these functions to the JobManager class:                                
      212                                                                              
      262 -    return misplaced                                                        
      213 +1. `_update_converted_manifest(self, source_path: str, asin: str, tit       
          +le: str, output_path: str, success: bool) -> None`:                         
      214 +   - Key is the source AAXC path (matching worker.py pattern)               
      215 +   - Schema for success:                                                    
      216 +     ```python                                                              
      217 +     {                                                                      
      218 +       "status": "success",                                                 
      219 +       "asin": asin,                                                        
      220 +       "title": title,                                                      
      221 +       "output_path": output_path,                                          
      222 +       "started_at": started_at,  # capture at start of conversion          
      223 +       "ended_at": datetime.utcnow().isoformat()                            
      224 +     }                                                                      
      225 +     ```                                                                    
      226 +   - Schema for failure:                                                    
      227 +     ```python                                                              
      228 +     {                                                                      
      229 +       "status": "failed",                                                  
      230 +       "asin": asin,                                                        
      231 +       "title": title,                                                      
      232 +       "error": error_message,                                              
      233 +       "ended_at": datetime.utcnow().isoformat()                            
      234 +     }                                                                      
      235 +     ```                                                                    
      236 +                                                                            
      237 +2. `_move_sources_to_completed(self, aaxc_path: Path, asin: str) -> N       
          +one`:                                                                       
      238 +   - Only execute if `self.settings.move_after_complete` is True            
      239 +   - Move these files to `self.settings.completed_dir`:                     
      240 +     - The AAXC file itself                                                 
      241 +     - .voucher file (same name, different extension)                       
      242 +     - -chapters.json file (replace .aaxc with -chapters.json in the        
          +stem)                                                                       
      243 +     - Cover JPG (glob for `{asin}*.jpg` in same directory)                 
      244 +   - Use shutil.move()                                                      
      245 +   - Log each file moved at INFO level                                      
      246 +   - Catch and log exceptions for individual files (don't fail entire       
          + operation)                                                                 
      247 +                                                                            
      248 +**Part C: Integrate into _execute_conversion()**                            
      249 +                                                                            
      250 +In the success block (after `await session.commit()`):                      
      251 +1. Call `_update_converted_manifest()` with success=True                    
      252 +2. Call `_move_sources_to_completed()` with the input file path             
      253 +                                                                            
      254 +In the failure block:                                                       
      255 +1. Call `_update_converted_manifest()` with success=False                   
      256 +                                                                            
      257 +**Constraints:**                                                            
      258 +- Do NOT modify database update logic                                       
      259 +- Do NOT change method signatures                                           
      260 +- Match worker.py manifest schema EXACTLY                                   
      261 +- Use pathlib.Path throughout                                               
      262 +- Handle missing directories gracefully (create if needed)                  
      263 +                                                                            
      264 +### PHASE 4: CONSISTENCY CHECK                                              
      265 +                                                                            
      266 +After implementation, dispatch an agent with this prompt:                   
      267 +                                                                            
      268 +"Perform a consistency and error check on the conversion manifest and       
          + file moving implementation:                                                
      269 +                                                                            
      270 +1. Read the new test file and verify all tests are properly structure       
          +d                                                                           
      271 +2. Read the modified job_manager.py and verify:                             
      272 +   - Helper functions follow naming conventions (underscore prefix fo       
          +r private)                                                                  
      273 +   - Manifest schema matches worker.py EXACTLY - compare field names        
      274 +   - File moving logic matches worker.py - compare which files are mo       
          +ved                                                                         
      275 +   - Error handling is consistent                                           
      276 +   - Logging uses existing patterns                                         
      277 +3. Read the modified config.py and verify:                                  
      278 +   - New settings have proper Field() definitions with descriptions         
      279 +   - Default values are sensible                                            
      280 +4. Run the tests: cd /Volumes/Brain_UGNAS/Jason Vongsay/code-projects       
          +/audible-library-react && python -m pytest apps/api/tests/services/te       
          +st_job_manager_conversion_manifest.py -v                                    
      281 +5. Check for syntax errors: python -m py_compile apps/api/services/jo       
          +b_manager.py && python -m py_compile apps/api/core/config.py                
      282 +6. Report any inconsistencies or errors found and fix them"                 
      283 +                                                                            
      284 +Only claim completion after this check passes.                              
      285  ```                                                                         
      286                                                                              
      287  ---                                                                         
      288                                                                              
      267 -## Files to Modify                                                          
      289 +## Final Consistency Check Agent Prompt                                     
      290                                                                              
      269 -1. **`apps/api/services/repair_pipeline.py`**                               
      270 -   - `apply_repair()`: Add manifest update logic                            
      271 -   - `compute_preview()`: Use database for primary stats                    
      272 -   - Add: `_scan_m4b_with_asin()`                                           
      273 -   - Add: `_extract_asin_from_metadata()`                                   
      274 -   - Add: `_detect_misplaced_files()`                                       
      275 -   - Add: `_manifest_has_conversion()`                                      
      291 +After BOTH Agent A and Agent B complete, run this final check:              
      292                                                                              
      277 -2. **`apps/api/core/config.py`**                                            
      278 -   - Add `MoveFilesPolicy` enum                                             
      279 -   - Add `move_files_policy` setting                                        
      293 +```                                                                         
      294 +## Task: Final Consistency Check for Manifest/Move Implementation           
      295                                                                              
      281 -3. **`apps/web/src/app/library/page.tsx`** (minor)                          
      282 -   - Stats display should work with existing field names                    
      296 +Both download and conversion manifest updates have been implemented.        
          +Perform a comprehensive consistency check.                                  
      297                                                                              
      298 +### CHECKS TO PERFORM                                                       
      299 +                                                                            
      300 +1. **Schema Consistency**                                                   
      301 +   - Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-li       
          +brary-react/app/worker.py                                                   
      302 +   - Read /Volumes/Brain_UGNAS/Jason Vongsay/code-projects/audible-li       
          +brary-react/apps/api/services/job_manager.py                                
      303 +   - Verify download_manifest schema in job_manager matches worker.py       
      304 +   - Verify converted_manifest schema in job_manager matches worker.p       
          +y                                                                           
      305 +   - Report any field name or structure differences                         
      306 +                                                                            
      307 +2. **Config Consistency**                                                   
      308 +   - Read apps/api/core/config.py                                           
      309 +   - Verify manifest_dir, completed_dir, and move_after_complete are        
          +properly defined                                                            
      310 +   - Verify docker-compose.dev.yml mounts these directories correctly       
      311 +                                                                            
      312 +3. **Integration Test**                                                     
      313 +   - Run ALL new tests: python -m pytest apps/api/tests/services/test       
          +_job_manager_download_manifest.py apps/api/tests/services/test_job_ma       
          +nager_conversion_manifest.py -v                                             
      314 +   - Verify all pass                                                        
      315 +                                                                            
      316 +4. **Syntax Check**                                                         
      317 +   - python -m py_compile apps/api/services/job_manager.py                  
      318 +   - python -m py_compile apps/api/core/config.py                           
      319 +                                                                            
      320 +5. **Import Check**                                                         
      321 +   - Start Python interpreter and verify: from services.job_manager i       
          +mport JobManager                                                            
      322 +                                                                            
      323 +### OUTPUT REQUIRED                                                         
      324 +                                                                            
      325 +Provide a summary report:                                                   
      326 +- [ ] Download manifest schema matches worker.py                            
      327 +- [ ] Converted manifest schema matches worker.py                           
      328 +- [ ] File moving logic matches worker.py                                   
      329 +- [ ] All tests pass                                                        
      330 +- [ ] No syntax errors                                                      
      331 +- [ ] Imports work correctly                                                
      332 +                                                                            
      333 +If ANY check fails, fix the issue and re-run the check.                     
      334 +```                                                                         
      335 +                                                                            
      336  ---                                                                         
      337                                                                              
      286 -## Verification                                                             
      338 +## Verification After All Agents Complete                                   
      339                                                                              
      288 -After implementation:                                                       
      340 +Manual verification steps:                                                  
      341                                                                              
      290 -1. **Run repair** and check console output for manifest updates             
      291 -2. **Verify download_manifest.json**:                                       
      292 -   - Should have entries for all AAX/AAXC files on disk                     
      293 -   - Should have inferred entries for books with M4B but no AAX             
      294 -3. **Verify converted_manifest.json**:                                      
      295 -   - Should have entries for all M4B files on disk                          
      296 -4. **Verify database**:                                                     
      297 -   - Book records should have correct `status` and `local_path_*` fie       
          -lds                                                                         
      298 -5. **Verify stats**:                                                        
      299 -   - Downloaded count should increase (includes inferred from M4B)          
      300 -   - Converted count should match M4B files on disk                         
      301 -   - Orphan count should be accurate (on disk - in library)                 
      342 +1. **Start the dev environment:**                                           
      343 +   ```bash                                                                  
      344 +   docker-compose -f docker-compose.dev.yml up -d                           
      345 +   ```                                                                      
      346                                                                              
      347 +2. **Trigger a download via GUI** and verify:                               
      348 +   - `specs/download_manifest.json` has new entry                           
      349 +   - Entry schema matches worker.py format                                  
      350 +                                                                            
      351 +3. **Trigger a conversion via GUI** and verify:                             
      352 +   - `specs/converted_manifest.json` has new entry                          
      353 +   - Entry key is the source AAXC path                                      
      354 +   - If `move_after_complete=True`, AAXC moved to completed_dir             
      355 +                                                                            
      356 +4. **Run repair** and verify stats are now accurate                         
      357 +                                                                            
      358  ---                                                                         
      359                                                                              
      360  ## Summary                                                                  
      361                                                                              
      307 -The fix ensures both manifests and database stay in sync by:                
      308 -1. Scanning filesystem for actual files                                     
      309 -2. Updating manifests with discovered files                                 
      310 -3. Inferring download status from M4B existence                             
      311 -4. Using database as source of truth for stats display                      
      312 -5. Providing configurable handling for misplaced files                      
      362 +| Component | Agent | Parallel? |                                           
      363 +|-----------|-------|-----------|                                           
      364 +| Download manifest updates | Agent A | Yes |                               
      365 +| Conversion manifest + file moving | Agent B | Yes |                       
      366 +| Final consistency check | Final Agent | After A & B |                     
      367 +                                                                            
      368 +Total estimated time: 2-3 hours with parallel execution.                    
                                                                                       
⏺ I've created a comprehensive plan with three agent prompts that can be executed:     
                                                                                       
  1. Agent A - Download manifest updates (can run in parallel)                         
  2. Agent B - Conversion manifest + file moving (can run in parallel)                 
  3. Final Check Agent - Runs after A & B complete                                     
                                                                                       
  Each prompt includes:                                                                
  - Mandatory exploration phase - Must dispatch Explore agent first                    
  - TDD approach - Write tests before implementation                                   
  - Explicit schemas - No room for interpretation                                      
  - Consistency check - Must verify and fix before claiming done                       
  - Constraints - Clear guardrails on what NOT to do                                   
                                                                                       
❯ i believe this was completed before our vs code crashed, can you dispatch an         
  agent ti check.                                                                      
                                                                                       
  Explore(Check manifest implementation status)                                        
  ⎿  ❯ Check if the manifest/move logic has already been implemented in job_manager.py.
                                                                                       
                                                                                       
· Brewing… (esc to interrupt)                                                          
                                                                                       
───────────────────────────────────────────────────────────────────────────────────────
❯                                                                                      
───────────────────────────────────────────────────────────────────────────────────────
  ⏵⏵ accept edits on (shift+tab to cycle)         Context left until auto-compact: 8%  

