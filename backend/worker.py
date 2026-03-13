import os
from redis import Redis
from rq import Worker, Queue, Connection
from app.core.config import settings

listen = ['default']

def run_worker():
    # Use sync Redis connection for RQ
    conn = Redis.from_url(settings.REDIS_QUEUE_URL)
    
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        print("Worker starting...")
        worker.work()

if __name__ == '__main__':
    run_worker()
