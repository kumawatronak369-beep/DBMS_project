import requests

from config import SERVER_URL


def send_event(event):

    try:

        response = requests.post(
            SERVER_URL,
            json=event,
            timeout=5
        )

        print(
            f"API STATUS: {response.status_code}"
        )

        try:

            print(
                "API RESPONSE:",
                response.json()
            )

        except ValueError:

            print(
                "API RESPONSE:",
                response.text
            )

        return response.ok

    except requests.RequestException as e:

        print(
            "API ERROR:",
            e
        )

        return False


def send_dns_correlation(
    device_ip,
    destination_ip,
    domain
):

    try:

        # Convert the normal event URL:
        #
        # /api/v1/network-events
        #
        # into:
        #
        # /api/v1/network-events/dns-correlation

        correlation_url = (
            SERVER_URL.rstrip("/")
            + "/dns-correlation"
        )

        data = {
            "device_ip": device_ip,
            "destination_ip": destination_ip,
            "domain": domain
        }

        response = requests.post(
            correlation_url,
            json=data,
            timeout=5
        )

        print(
            f"DNS CORRELATION API STATUS: "
            f"{response.status_code}"
        )

        try:

            print(
                "DNS CORRELATION RESPONSE:",
                response.json()
            )

        except ValueError:

            print(
                "DNS CORRELATION RESPONSE:",
                response.text
            )

        return response.ok

    except requests.RequestException as e:

        print(
            "DNS CORRELATION API ERROR:",
            e
        )

        return False