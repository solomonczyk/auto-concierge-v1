import os
from redis import Redis
from rq import Worker, Queue, Connection
from app.core.config import settings

listen = ['default']

def run_worker():
    # Use sync Redis connection for RQ
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
    conn = Redis.from_url(redis_url)
    
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        print("Worker starting...")
        worker.work()

if __name__ == '__main__':
    run_worker()
