# ~/content_pipeline/backend/shared_state.py
import redis
import json
import logging

# Connect to our Redis container
# The 'decode_responses=True' makes it return strings instead of bytes
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

# A shared helper function
def log_terminal(message):
    print(message)
    logging.info(message)
