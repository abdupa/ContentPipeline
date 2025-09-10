from celery.schedules import crontab

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

beat_schedule = {
    'update-product-database-daily': {
        'task': 'data_tasks.update_product_database_task',
        'schedule': crontab(hour=19, minute=0), # Runs daily at 4:00 AM PHT (the next day)
    },
    'sync-wordpress-status-daily': {
        'task': 'tasks.full_wordpress_sync_task',
        'schedule': crontab(hour=16, minute=0),  # Runs daily at 12:00 AM PHT (midnight, the next day)
    },
    'fetch-gsc-data-daily': {
        'task': 'tasks.fetch_gsc_data_task',
        'schedule': crontab(hour=17, minute=0),  # Runs daily at 1:00 AM PHT (the next day)
    },
    'fetch-gsc-insights-weekly': {
        'task': 'tasks.fetch_gsc_insights_task',
        'schedule': crontab(day_of_week='sunday', hour=18, minute=0), # Runs every Monday at 2:00 AM PHT
    },
}

