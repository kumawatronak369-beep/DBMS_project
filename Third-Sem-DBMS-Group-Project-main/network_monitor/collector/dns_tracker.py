import time


class DNSCache:

    def __init__(self, ttl=60):

        self.ttl = ttl

        self.records = {}


    def add(self, domain, ip):

        if not domain or not ip:
            return

        self.records[ip] = {
            "domain": domain,
            "timestamp": time.time()
        }


    def get_domain(self, ip):

        record = self.records.get(ip)

        if record is None:
            return None


        if time.time() - record["timestamp"] > self.ttl:

            del self.records[ip]

            return None


        return record["domain"]


    def get_ip(self, domain):

        if not domain:
            return None


        now = time.time()


        expired = []

        for ip, record in self.records.items():

            if now - record["timestamp"] > self.ttl:

                expired.append(ip)


        for ip in expired:

            del self.records[ip]


        for ip, record in self.records.items():

            if record["domain"] == domain:

                return ip


        return None