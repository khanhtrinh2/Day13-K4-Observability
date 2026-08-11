import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from app.challenge import load_challenge, ordered_queries
from app.cli import configure_utf8_stdio


BASE_URL = "http://127.0.0.1:8000"
QUERIES = REPO_ROOT / "data" / "sample_queries.jsonl"


def send_request(client: httpx.Client, payload: dict) -> None:
    try:
        start = time.perf_counter()

        response = client.post(
            f"{BASE_URL}/chat",
            json=payload,
        )

        latency = (time.perf_counter() - start) * 1000

        print("\n" + "=" * 70)
        print(f"REQUEST : {payload}")
        print(f"STATUS  : {response.status_code}")
        print(f"LATENCY : {latency:.1f}ms")
        print(f"TYPE    : {response.headers.get('content-type')}")
        print(f"BODY    : {repr(response.text)}")

        # Chỉ parse JSON sau khi đã in raw response
        try:
            data = response.json()

        except json.JSONDecodeError as e:
            print(f"❌ JSON PARSE ERROR: {e}")
            print("Server không trả về JSON hợp lệ.")
            return

        # API trả lỗi
        if response.status_code >= 400:
            print(f"❌ API ERROR: {data}")
            return

        correlation_id = data.get("correlation_id", "N/A")
        feature = payload.get("feature", "N/A")

        print(
            f"✅ [{response.status_code}] "
            f"{correlation_id} | "
            f"{feature} | "
            f"{latency:.1f}ms"
        )

    except httpx.ConnectError as e:
        print("\n❌ CONNECT ERROR")
        print(f"Không kết nối được tới {BASE_URL}")
        print("Kiểm tra API đã chạy chưa.")
        print(f"Chi tiết: {e}")

    except httpx.TimeoutException as e:
        print("\n❌ TIMEOUT")
        print(f"Request vượt quá timeout: {e}")

    except Exception as e:
        print("\n❌ UNEXPECTED ERROR")
        print(f"{type(e).__name__}: {e}")


def load_payloads(use_challenge: bool) -> list[dict]:
    if use_challenge:
        challenge = load_challenge()
        payloads = ordered_queries(challenge)

        print(
            f"Challenge: {challenge.challenge_id} "
            f"| Cohort: {challenge.cohort}"
        )

        return payloads

    if not QUERIES.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file query: {QUERIES}"
        )

    payloads = []

    for line_number, line in enumerate(
        QUERIES.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            payloads.append(json.loads(line))

        except json.JSONDecodeError as e:
            print(
                f"❌ JSON không hợp lệ trong "
                f"{QUERIES} tại dòng {line_number}:"
            )
            print(repr(line))
            raise e

    return payloads


def main() -> None:
    configure_utf8_stdio()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent requests",
    )

    parser.add_argument(
        "--challenge",
        action="store_true",
        help=(
            "Dùng input chính thức trong "
            "config/challenge.json sau khi được release."
        ),
    )

    args = parser.parse_args()

    payloads = load_payloads(args.challenge)

    print("=" * 70)
    print("LOAD TEST")
    print(f"Base URL    : {BASE_URL}")
    print(f"Requests    : {len(payloads)}")
    print(f"Concurrency : {args.concurrency}")
    print("=" * 70)

    with httpx.Client(timeout=30.0) as client:

        if args.concurrency > 1:

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=args.concurrency
            ) as executor:

                futures = [
                    executor.submit(
                        send_request,
                        client,
                        payload,
                    )
                    for payload in payloads
                ]

                concurrent.futures.wait(futures)

        else:

            for payload in payloads:
                send_request(client, payload)


if __name__ == "__main__":
    main()