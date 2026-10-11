import time


class EventDeduplicator:

    def __init__(self, window_seconds=30):

        self.window_seconds = window_seconds

        self.events = {}


    def should_store(self, event):

        # -----------------------------------------------------
        # Deduplication key
        #
        # Domain is intentionally NOT included.
        #
        # DNS resolution may happen before or after the
        # corresponding traffic packet. The network flow
        # itself should determine whether an event is a
        # duplicate.
        # -----------------------------------------------------

        key = (

            event.get("device_ip"),

            event.get("destination_ip"),

            event.get("protocol"),

            event.get("destination_port")

        )


        now = time.time()


        # -----------------------------------------------------
        # Remove expired entries
        # -----------------------------------------------------

        expired_keys = [

            k

            for k, timestamp in self.events.items()

            if now - timestamp >= self.window_seconds

        ]


        for k in expired_keys:

            del self.events[k]


        # -----------------------------------------------------
        # Check duplicate
        # -----------------------------------------------------

        if key in self.events:

            return False


        # -----------------------------------------------------
        # Store new event
        # -----------------------------------------------------

        self.events[key] = now


        return True