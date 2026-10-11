from scapy.all import sniff, IP, UDP, DNS, DNSQR
from datetime import datetime

INTERFACE = r"\Device\NPF_{11B371C7-3924-47D9-8376-AB42C7F86DC8}"
PHONE_IP = "192.168.137.107"

seen_domains = set()


def dns_handler(packet):

    # Must contain IPv4
    if not packet.haslayer(IP):
        return

    ip = packet[IP]

    # Only packets coming FROM the phone
    if ip.src != PHONE_IP:
        return

    # Must be UDP
    if not packet.haslayer(UDP):
        return

    udp = packet[UDP]

    # DNS request uses destination port 53
    if udp.dport != 53:
        return

    # Must contain DNS
    if not packet.haslayer(DNS):
        return

    dns = packet[DNS]

    # qr = 0 means query
    if dns.qr != 0:
        return

    # Must contain a question
    if not dns.qd:
        return

    # Extract domain
    if not packet.haslayer(DNSQR):
        return

    domain = packet[DNSQR].qname.decode(
        "utf-8",
        errors="ignore"
    ).rstrip(".")

    # Avoid printing the same domain repeatedly
    if domain in seen_domains:
        return

    seen_domains.add(domain)

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"DNS QUERY: {domain}"
    )


print("=" * 60)
print("DNS CAPTURE TEST")
print("=" * 60)
print(f"Interface : {INTERFACE}")
print(f"Phone     : {PHONE_IP}")
print()
print("Waiting for DNS queries...")
print("Open websites on the phone.")
print("Press CTRL+C to stop.")
print("=" * 60)


sniff(
    iface=INTERFACE,
    prn=dns_handler,
    store=False
)