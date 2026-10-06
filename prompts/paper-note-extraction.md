# Paper-note extraction

Convert a scanned notebook page into the structured note schema.

Rules:

1. Preserve the author's wording in the transcription whenever legible.
2. Never invent missing handwriting. Use an uncertainty marker and lower the
   confidence score.
3. Preserve the presence and rough meaning of diagrams even when they cannot be
   represented as text.
4. Recognize these optional handwritten markers:
   - `□` task
   - `!` important insight
   - `?` research question
   - `→` follow-up
   - `*` resource or reference
5. A possible task is only a proposal. Do not assign a due date unless one is
   explicit on the page.
6. Separate direct transcription from interpretation.
7. Flag sensitive content so downstream systems can avoid unnecessary copying.
8. Return only data that conforms to the structured output schema.
