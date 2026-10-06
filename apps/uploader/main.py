"""Cloud Run process entry point."""

import os

from apps.uploader.application import UploaderSettings, create_app


app = create_app(UploaderSettings.from_environment(os.environ))
