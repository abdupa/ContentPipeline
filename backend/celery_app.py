from celery import Celery

# Create the central Celery application instance
app = Celery("content_pipeline")

# Load the configuration from a central config file or directly
app.config_from_object("celery_config")

# Auto-discover tasks from all registered apps (tasks.py, data_tasks.py)
# Celery will look for a 'tasks.py' file in all of the apps listed in INSTALLED_APPS
# For our simple setup, we will explicitly include our task modules.
app.autodiscover_tasks(['tasks', 'data_tasks'])

