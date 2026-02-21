import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

def test_isolation():
    # 1. Login as Admin 1
    logger.info("logging in as Admin 1...")
    r1 = requests.post(f"{BASE_URL}/api/v1/login/access-token", data={
        "username": "admin@demo.ru",
        "password": "admin123"
    })
    token1 = r1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # 2. Get services for Admin 1
    services1 = requests.get(f"{BASE_URL}/api/v1/services/", headers=headers1).json()
    logger.info(f"Admin 1 sees services: {[s['name'] for s in services1]}")
    
    # 3. Login as Admin 2
    logger.info("Logging in as Admin 2...")
    r2 = requests.post(f"{BASE_URL}/api/v1/login/access-token", data={
        "username": "rival@autoshop.ru",
        "password": "password123"
    })
    token2 = r2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 4. Get services for Admin 2
    services2 = requests.get(f"{BASE_URL}/api/v1/services/", headers=headers2).json()
    logger.info(f"Admin 2 sees services: {[s['name'] for s in services2]}")

    # 5. CROSS-TENANT CHECK: Admin 2 tries to access a service from Tenant 1
    service_id_1 = services1[0]["id"]
    logger.info(f"Admin 2 attempting to access Service ID {service_id_1} (Tenant 1)...")
    r_check = requests.put(f"{BASE_URL}/api/v1/services/{service_id_1}", headers=headers2, json={
        "name": "I am a hacker",
        "duration_minutes": 1,
        "base_price": 0
    })
    
    if r_check.status_code == 404:
        logger.info("SUCCESS: Admin 2 got 404 access denied (NotFound) for Tenant 1's service.")
    else:
        logger.error(f"FAILURE: Admin 2 got status {r_check.status_code}. Isolation leak!")

if __name__ == "__main__":
    test_isolation()
