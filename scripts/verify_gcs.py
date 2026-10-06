"""Run a small live check against the configured notes bucket."""

from personal_os.config import PersonalOSConfig
from personal_os.providers.gcs import GCSObjectStore


def main() -> None:
    config = PersonalOSConfig.from_yaml("config/system.yaml")
    store = GCSObjectStore(config.gcp.project_id)
    bucket = config.gcp.paper_notes_bucket
    source = f"gs://{bucket}/inbox/system-check.txt"
    destination = f"gs://{bucket}/processed/system-check.txt"

    written = store.put_bytes(source, b"personal-os storage check\n", "text/plain")
    found = store.stat(written.uri)
    copied = store.copy(found.uri, destination)

    print(f"upload: ok ({found.uri}, {found.size} bytes)")
    print(f"copy: ok ({copied.uri})")


if __name__ == "__main__":
    main()
