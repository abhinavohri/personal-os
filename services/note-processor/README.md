# Note processor

Planned event-driven service that processes new objects from the paper-notes
bucket, calls Vertex AI with the versioned extraction prompt and schema, stores
artifacts, and creates a draft entry in the Notion Notes Inbox.
