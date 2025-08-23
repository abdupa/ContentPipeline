from celery import Celery

# Create the central Celery application instance
app = Celery("content_pipeline")

# Load all configuration settings from our central config file.
# This will automatically handle the 'imports' setting for task discovery.
app.config_from_object("celery_config")