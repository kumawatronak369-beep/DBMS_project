from event_deduplicator import EventDeduplicator


deduplicator = EventDeduplicator(
    window_seconds=30
)


event = {
    "device_ip": "192.168.137.107",
    "destination_ip": "20.207.73.82",
    "domain": "github.com",
    "protocol": "TCP"
}


print("First event:")
print(deduplicator.should_store(event))


print("Same event immediately:")
print(deduplicator.should_store(event))


event2 = {
    "device_ip": "192.168.137.107",
    "destination_ip": "20.207.73.82",
    "domain": "github.com",
    "protocol": "UDP"
}


print("Same destination but different protocol:")
print(deduplicator.should_store(event2))