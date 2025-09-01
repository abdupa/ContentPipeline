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
        'schedule': crontab(hour=20, minute=30), # Runs at 00:00 PST (midnight)
    },
    'sync-wordpress-status-daily': {
        'task': 'tasks.full_wordpress_sync_task',
        'schedule': crontab(hour=21, minute=0), # Runs at 01:00 AM PST
    },
    'fetch-gsc-data-daily': {
        'task': 'tasks.fetch_gsc_data_task',
        'schedule': crontab(hour=3, minute=50), # Runs at 11:50 AM PST
        # hour=3, minute=50
    },
    'fetch-gsc-insights-weekly': {
        'task': 'tasks.fetch_gsc_insights_task',
        'schedule': crontab(day_of_week='sunday', hour=19, minute=0), # Runs every Sunday at 3:00 AM PST
    },
}

