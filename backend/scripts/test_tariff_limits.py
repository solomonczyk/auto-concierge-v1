import requests
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

def test_tariff_limits():
    # 1. Login as Admin 2 (Rival Autoshop - FREE tariff)
    logger.info("Logging in as Admin 2 (FREE tariff)...")
    r = requests.post(f"{BASE_URL}/api/v1/login/access-token", data={
        "username": "rival@autoshop.ru",
        "password": "password123"
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Extract Service ID (from earlier seeding)
    services = requests.get(f"{BASE_URL}/api/v1/services/", headers=headers).json()
    service_id = services[0]["id"]
    
    # 3. Create 10 appointments (or enough to reach 10)
    # First check current count
    appts = requests.get(f"{BASE_URL}/api/v1/appointments/", headers=headers).json()
    current_count = len(appts)
    needed = 10 - current_count
    
    start_time = datetime.now() + timedelta(days=1)
    
    for i in range(needed):
        logger.info(f"Creating appointment {current_count + i + 1}/10...")
        payload = {
            "service_id": service_id,
            "start_time": (start_time + timedelta(hours=i)).isoformat(),
            "client_name": f"Test Client {i}",
            "client_phone": f"79990000{i:02d}"
        }
        res = requests.post(f"{BASE_URL}/api/v1/appointments/", headers=headers, json=payload)
        if res.status_code != 200:
            logger.error(f"Failed to create appointment {i}: {res.text}")
            return

    # 4. Attempt the 11th appointment
    logger.info("Attempting the 11th appointment (should be blocked)...")
    payload = {
        "service_id": service_id,
        "start_time": (start_time + timedelta(hours=15)).isoformat(),
        "client_name": "Limit Breaker",
        "client_phone": "79998887766"
    }
    res = requests.post(f"{BASE_URL}/api/v1/appointments/", headers=headers, json=payload)
    
    if res.status_code == 403:
        logger.info(f"SUCCESS: 11th appointment blocked as expected. Message: {res.json()['detail']}")
    else:
        logger.error(f"FAILURE: 11th appointment allowed with status {res.status_code}. Tariff enforcement failed!")

if __name__ == "__main__":
    test_tariff_limits()
