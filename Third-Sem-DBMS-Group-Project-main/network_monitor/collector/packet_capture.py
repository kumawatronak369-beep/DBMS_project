from scapy.all import (
    sniff,
    IP,
    TCP,
    UDP,
    DNS,
    DNSQR,
    DNSRR
)

import time

from config import (
    INTERFACE,
    DEVICE_IP,
    DEVICE_MAC,
    GATEWAY_NODE,
    DNS_CACHE_TTL,
    DEDUP_WINDOW
)

from dns_tracker import DNSCache
from event_builder import build_event
from event_deduplicator import EventDeduplicator

from api_client import (
    send_event,
    send_dns_correlation
)


class PacketCapture:

    def __init__(self):

        self.dns_cache = DNSCache(
            ttl=DNS_CACHE_TTL
        )

        self.deduplicator = EventDeduplicator(
            window_seconds=DEDUP_WINDOW
        )

        # -------------------------------------------------
        # Traffic seen before DNS resolution
        #
        # {
        #     destination_ip: timestamp
        # }
        # -------------------------------------------------

        self.pending_destinations = {}

        # Keep pending entries only for a short period.
        self.pending_ttl = 30


    # =====================================================
    # CLEAN OLD PENDING ENTRIES
    # =====================================================

    def cleanup_pending(self):

        now = time.time()

        expired = []

        for ip_address, timestamp in (
            self.pending_destinations.items()
        ):

            if now - timestamp > self.pending_ttl:

                expired.append(ip_address)


        for ip_address in expired:

            del self.pending_destinations[
                ip_address
            ]


    # =====================================================
    # DNS PROCESSING
    # =====================================================

    def process_dns(self, packet):

        if not packet.haslayer(DNS):

            return


        dns = packet[DNS]


        # =================================================
        # DNS QUERY
        # =================================================

        if dns.qr == 0:

            if not packet.haslayer(DNSQR):

                return


            try:

                domain = packet[
                    DNSQR
                ].qname.decode(
                    "utf-8",
                    errors="ignore"
                ).rstrip(".")


            except Exception:

                return


            if not domain:

                return


            print(
                f"DNS QUERY: {domain}"
            )


            return


        # =================================================
        # DNS RESPONSE
        # =================================================

        if dns.qr != 1:

            return


        if not packet.haslayer(DNSQR):

            return


        try:

            domain = packet[
                DNSQR
            ].qname.decode(
                "utf-8",
                errors="ignore"
            ).rstrip(".")


        except Exception:

            return


        if not domain:

            return


        if dns.ancount == 0:

            return


        # =================================================
        # Process DNS answers
        # =================================================

        for i in range(dns.ancount):

            try:

                answer = dns.an[i]

            except Exception:

                continue


            if not answer.haslayer(DNSRR):

                continue


            # IPv4 A record
            if answer.type != 1:

                continue


            ip_address = answer.rdata


            if not isinstance(
                ip_address,
                str
            ):

                continue


            # -------------------------------------------------
            # Store IP -> domain locally
            # -------------------------------------------------

            self.dns_cache.add(
                domain,
                ip_address
            )


            print(
                f"DNS RESPONSE: "
                f"{domain} -> {ip_address}"
            )


            # -------------------------------------------------
            # Tell Flask about the DNS mapping
            # -------------------------------------------------

            send_dns_correlation(
                device_ip=DEVICE_IP,
                destination_ip=ip_address,
                domain=domain
            )


            # -------------------------------------------------
            # Remove from pending traffic
            #
            # The IP is now known.
            # -------------------------------------------------

            if ip_address in self.pending_destinations:

                del self.pending_destinations[
                    ip_address
                ]


    # =====================================================
    # PACKET PROCESSING
    # =====================================================

    def process_packet(self, packet):

        # -------------------------------------------------
        # Clean old pending entries
        # -------------------------------------------------

        self.cleanup_pending()


        # -------------------------------------------------
        # IPv4 only
        # -------------------------------------------------

        if not packet.haslayer(IP):

            return


        ip = packet[IP]


        # -------------------------------------------------
        # DNS
        #
        # DNS responses normally travel from the DNS server
        # back to the phone, so ip.src is NOT DEVICE_IP.
        #
        # Process DNS before applying the outgoing-device
        # filter.
        # -------------------------------------------------

        if packet.haslayer(DNS):

            self.process_dns(packet)

            return


        # -------------------------------------------------
        # Only monitor outgoing traffic from the selected phone
        # -------------------------------------------------

        if ip.src != DEVICE_IP:

            return


        # -------------------------------------------------
        # Protocol and ports
        # -------------------------------------------------

        protocol = None

        source_port = None

        destination_port = None


        if packet.haslayer(TCP):

            protocol = "TCP"

            source_port = packet[TCP].sport

            destination_port = packet[TCP].dport


        elif packet.haslayer(UDP):

            protocol = "UDP"

            source_port = packet[UDP].sport

            destination_port = packet[UDP].dport


        else:

            return


        # -------------------------------------------------
        # Destination
        # -------------------------------------------------

        destination_ip = ip.dst


        # -------------------------------------------------
        # Try IP -> domain lookup
        # -------------------------------------------------

        domain = self.dns_cache.get_domain(
            destination_ip
        )


        # -------------------------------------------------
        # If domain is unknown, remember the destination
        # -------------------------------------------------

        if domain is None:

            self.pending_destinations[
                destination_ip
            ] = time.time()


        # -------------------------------------------------
        # Build event
        # -------------------------------------------------

        event = build_event(

            device_ip=DEVICE_IP,

            device_mac=DEVICE_MAC,

            destination_ip=destination_ip,

            domain=domain,

            protocol=protocol,

            gateway_node=GATEWAY_NODE,

            source_port=source_port,

            destination_port=destination_port
        )


        # -------------------------------------------------
        # Deduplication
        # -------------------------------------------------

        if not self.deduplicator.should_store(
            event
        ):

            print(
                "DUPLICATE IGNORED:",
                destination_ip,
                domain,
                protocol,
                destination_port
            )

            return


        # -------------------------------------------------
        # New event
        # -------------------------------------------------

        print()

        print(
            "NEW EVENT"
        )

        print(
            event
        )


        # -------------------------------------------------
        # Send event
        # -------------------------------------------------

        send_event(event)


    # =====================================================
    # START CAPTURE
    # =====================================================

    def start(self):

        print("=" * 60)

        print(
            "NETWORK MONITOR COLLECTOR"
        )

        print("=" * 60)

        print(
            "Device:",
            DEVICE_IP
        )

        print(
            "Interface:",
            INTERFACE
        )

        print(
            "Gateway:",
            GATEWAY_NODE
        )

        print(
            "Deduplication:",
            DEDUP_WINDOW,
            "seconds"
        )

        print(
            "DNS correlation: ENABLED"
        )

        print("=" * 60)

        print(
            "Starting packet capture..."
        )

        print(
            "Press CTRL+C to stop."
        )

        print("=" * 60)


        sniff(
            iface=INTERFACE,
            prn=self.process_packet,
            store=False
        )