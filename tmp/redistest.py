import asyncio
import time
from uuid import uuid4

import httpx

BASE_URL = "http://127.0.0.1:8000"
TARGET_ENDPOINT = "services_get"  # "signup" | "services_create" | "services_nearby_me" | "forgot_password" | "services_get"

SIGNUP_URL = "http://127.0.0.1:8000/users/signup"
LOGIN_URL = "http://127.0.0.1:8000/users/login"
SERVICES_URL = "http://127.0.0.1:8000/services/"
SERVICES_NEARBY_ME_URL = "http://127.0.0.1:8000/services/nearby/me"
FORGOT_PASSWORD_URL = "http://127.0.0.1:8000/auth/forgot-password"
CATALOG_CATEGORY_URL = "http://127.0.0.1:8000/categories/"
REQUEST_COUNT = 10
TEST_MODE = "burst"  # "burst" (recommended) or "sequential"
SEQUENTIAL_DELAY_SECONDS = 0.0
EMAIL_PREFIX = "ratelimit.signup"
DEFAULT_PASSWORD = "Temoor@1122"

# Credentials for endpoints that require auth (e.g., POST /services)
LOGIN_EMAIL = "testts@gmail.com"
LOGIN_PASSWORD = "temoor1122"
# Optional: provide a valid bearer token to skip login request.
ACCESS_TOKEN_OVERRIDE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyOGVlYTg0OS04ZDY3LTRkZDYtOGNiYS1lY2ZlZDNmZjZlMjIiLCJleHAiOjE3NzYzNDM3ODN9.LWtJ8fWLIgI9cjI3kkXm6wGRg3sAgOlKcNSQnVGwKt4"

# Forgot-password test target email (should exist in DB)
FORGOT_PASSWORD_EMAIL = LOGIN_EMAIL

# Nearby/me test tuning
NEARBY_RADIUS_KM = 10.0
NEARBY_USE_CATEGORY_FILTER = False


def _build_signup_payload(index: int) -> dict:
    unique_part = uuid4().hex[:8]
    return {
        "email": f"{EMAIL_PREFIX}.{index}.{unique_part}@example.com",
        "password": DEFAULT_PASSWORD,
        "isAdmin": False,
        "phone": None,
    }


def _build_service_payload(index: int, category_id: str) -> dict:
    unique = uuid4().hex[:8]
    return {
        "title": f"RateLimit Service {index}-{unique}",
        "description": f"Rate limit test listing {unique}",
        "priceType": "fixed",
        "priceAmount": "100.00",
        "isNegotiable": False,
        "serviceLocation": "Karachi",
        "serviceRadiusKm": 10,
        "categoryId": category_id,
        "status": "draft",
    }


async def _login_and_get_access_token(client: httpx.AsyncClient) -> str:
    payload = {
        "username": LOGIN_EMAIL,
        "password": LOGIN_PASSWORD,
        "grant_type": "password",
        "scope": "",
    }
    response = await client.post(LOGIN_URL, data=payload)
    if response.status_code != 200:
        raise RuntimeError(f"Login failed with status={response.status_code} body={response.text}")

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Login response did not include access_token")
    return token


async def _get_first_category_id(client: httpx.AsyncClient) -> str:
    response = await client.get(CATALOG_CATEGORY_URL)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to load categories status={response.status_code} body={response.text}"
        )

    data = response.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError("No categories found. Create at least one category before services test.")

    category_id = data[0].get("id")
    if not category_id:
        raise RuntimeError("Category response missing 'id' field")
    return category_id


async def send_requests(n: int) -> None:

    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        started_at = time.perf_counter()

        token = None
        category_id = None
        if TARGET_ENDPOINT in ("services_create", "services_nearby_me"):
            token = ACCESS_TOKEN_OVERRIDE.strip() or await _login_and_get_access_token(client)

        if TARGET_ENDPOINT in ("services_create", "services_nearby_me"):
            category_id = await _get_first_category_id(client)
            if TARGET_ENDPOINT == "services_create" or NEARBY_USE_CATEGORY_FILTER:
                print(f"Using categoryId={category_id}")

        async def issue_once(index: int) -> None:
            if TARGET_ENDPOINT == "signup":
                payload = _build_signup_payload(index)
                response = await client.post(SIGNUP_URL, json=payload)
                expected_ok = (200, 201, 422)
            elif TARGET_ENDPOINT == "services_create":
                payload = _build_service_payload(index, category_id=category_id)
                headers = {"Authorization": f"Bearer {token}"}
                response = await client.post(SERVICES_URL, json=payload, headers=headers)
                expected_ok = (200, 201, 400, 401, 404, 422)
            elif TARGET_ENDPOINT == "services_get":
                response = await client.get(SERVICES_URL)
                expected_ok = (200, 422)
            elif TARGET_ENDPOINT == "services_nearby_me":
                headers = {"Authorization": f"Bearer {token}"}
                params = {
                    "radius_km": NEARBY_RADIUS_KM,
                    "status": "active",
                    "topSelling": False,
                    "topRating": False,
                    "page": 1,
                    "pageSize": 20,
                }
                if NEARBY_USE_CATEGORY_FILTER and category_id:
                    params["category"] = category_id
                response = await client.get(SERVICES_NEARBY_ME_URL, headers=headers, params=params)
                expected_ok = (200, 400, 401, 404, 422)
            elif TARGET_ENDPOINT == "forgot_password":
                payload = {"email": FORGOT_PASSWORD_EMAIL}
                response = await client.post(FORGOT_PASSWORD_URL, json=payload)
                expected_ok = (200, 400, 404, 422)
            else:
                raise RuntimeError(f"Unsupported TARGET_ENDPOINT: {TARGET_ENDPOINT}")

            retry_after = response.headers.get("Retry-After", "-")
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            print(
                f"{index + 1:02d} t={elapsed_ms:7.1f}ms "
                f"status={response.status_code} retry_after={retry_after}"
            )

            if response.status_code == 429:
                print("429 body:", response.text)
            elif response.status_code not in expected_ok:
                print("Unexpected body:", response.text)

        if TEST_MODE == "burst":
            # Fire all requests together so they land in the same 1-second limiter window.
            await asyncio.gather(*(issue_once(i) for i in range(n)))
            return

        for i in range(n):
            await issue_once(i)
            if SEQUENTIAL_DELAY_SECONDS > 0:
                await asyncio.sleep(SEQUENTIAL_DELAY_SECONDS)


if __name__ == "__main__":
    asyncio.run(send_requests(REQUEST_COUNT))