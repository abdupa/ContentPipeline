# Celery Configuration File

# Broker and Backend settings
broker_url = 'redis://redis:6379/0'
result_backend = 'redis://redis:6379/0'

# List of modules to import when the Celery worker starts.
# This is the key to making sure all tasks are registered.
imports = ('tasks', 'data_tasks')

# Other settings
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True


