---
name: secondbrain-notes
description: Find, read and write the user's SecondBrain notes the user's way - search first, cite the note and its date, write new notes dated with their sources, and add to a note rather than replacing it. Use when the user asks about their notes, plans, rulings or past work, or asks you to write something up or record it in SecondBrain.
---

## Usage

SecondBrain is the user's notes vault and your long-term memory. Its tools are `secondbrain_search_notes`,
`secondbrain_read_note`, `secondbrain_write_note` and `secondbrain_append_to_note`.

Reading:
1. Search before answering: `secondbrain_search_notes` with the subject's words. Try a second wording if the
   first finds nothing relevant.
2. Read the note itself with `secondbrain_read_note`; a search snippet is not the note.
3. Cite what you used: the note's title, its id and its date. Prefer the newest note on a subject, and say
   "as of <date>" for anything an older note says about plans or status.

Writing:
1. Search first. If a note on the subject exists, add to it with `secondbrain_append_to_note`: a dated heading,
   then the new part. Never replace or delete a note's existing text.
2. A new note (`secondbrain_write_note`) gets a title that says what it is and the date, a category
   (`projects`, `areas`, `resources`, `archives` or `inbox`) and a few tags.
3. Write facts with their source (a file and line, a page and its URL, or a note id). Mark anything you inferred
   as inferred. Plain words, short paragraphs and lists.
4. Never write a secret, a key, or the contents of a `.env` file into a note.
5. Say which note you wrote or changed, with its id.
