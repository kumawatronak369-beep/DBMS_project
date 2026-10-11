from datetime import datetime, timezone


def build_event(
    device_ip,
    destination_ip,
    protocol,
    domain=None,
    device_mac=None,
    gateway_node="N001",
    source_port=None,
    destination_port=None
):

    return {
        "gateway_node": gateway_node,
        "device_ip": device_ip,
        "device_mac": device_mac,
        "destination_ip": destination_ip,
        "domain": domain,
        "protocol": protocol,
        "source_port": source_port,
        "destination_port": destination_port,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    }