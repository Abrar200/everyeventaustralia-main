# everyevent/huey.py

from huey import RedisHuey
import os

# Configure the Huey instance
huey = RedisHuey(
    'everyevent',
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD', None),
)
