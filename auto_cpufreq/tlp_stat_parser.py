class TLPStatusParser:
    def __init__(self, tlp_stat_output):
        self.data = {}
        self._parse(tlp_stat_output)

    def _parse(self, data):
        for line in data.split("\n"):
            key_val = line.split("=", 1)
            if len(key_val) > 1: self.data[key_val[0].strip().lower()] = key_val[1].strip()

    def _get_key(self, key): return self.data[key] if key in self.data else ""

    def is_enabled(self): return self._get_key("state") == "enabled"
