import re


class PCIRedactionService:
    PAN_REPLACEMENT = "[REDACTED PAN]"
    CVV_REPLACEMENT = "[REDACTED CVV]"

    _PAN_CANDIDATE = re.compile(
        r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)"
    )
    _UUID = re.compile(
        r"(?i)(?<![0-9a-f])"
        r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"
        r"(?![0-9a-f])"
    )
    _CVV_AFTER_LABEL = re.compile(
        r"(?i)\b(cvv2?|cvc2?|cid|card security code|"
        r"card verification(?: value| code)?|security code)"
        r"(\s*[\"']?\s*(?:is|was|equals|:|=|-)?\s*[\"']?\s*)"
        r"\d{3,4}\b"
    )
    _CVV_BEFORE_LABEL = re.compile(
        r"(?i)(?<!\d)\d{3,4}"
        r"(\s+(?:is(?: the)?|was(?: the)?|for the)?\s*)"
        r"\b(cvv2?|cvc2?|cid|card security code|"
        r"card verification(?: value| code)?|security code)\b"
    )

    def redact(self, value):
        if value is None:
            return None

        text = str(value)
        text = self._PAN_CANDIDATE.sub(self._redact_pan_candidate, text)
        text = self._CVV_AFTER_LABEL.sub(
            lambda match: (
                f"{match.group(1)}{match.group(2)}{self.CVV_REPLACEMENT}"
            ),
            text,
        )
        text = self._CVV_BEFORE_LABEL.sub(
            lambda match: (
                f"{self.CVV_REPLACEMENT}{match.group(1)}{match.group(2)}"
            ),
            text,
        )
        return text

    def contains_pan(self, value):
        if value is None:
            return False

        return any(
            self._match_is_pan(match)
            for match in self._PAN_CANDIDATE.finditer(str(value))
        )

    def contains_cvv(self, value):
        if value is None:
            return False

        text = str(value)
        return bool(
            self._CVV_AFTER_LABEL.search(text)
            or self._CVV_BEFORE_LABEL.search(text)
        )

    def is_persistence_safe(self, value):
        return not self.contains_pan(value) and not self.contains_cvv(value)

    def redact_structure(self, value):
        if isinstance(value, dict):
            return {
                key: self.redact_structure(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self.redact_structure(item)
                for item in value
            ]
        if isinstance(value, tuple):
            return tuple(
                self.redact_structure(item)
                for item in value
            )
        if isinstance(value, str):
            return self.redact(value)
        return value

    def redact_filename_component(self, value):
        text = self.redact(value)
        text = text.replace(self.PAN_REPLACEMENT, "redacted-pan")
        text = text.replace(self.CVV_REPLACEMENT, "redacted-cvv")
        text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
        return text.strip(" .") or "redacted"

    def _redact_pan_candidate(self, match):
        candidate = match.group(0)
        if self._match_is_pan(match):
            return self.PAN_REPLACEMENT
        return candidate

    def _match_is_pan(self, match):
        if self._inside_uuid(match):
            return False
        return self._is_valid_pan(match.group(0))

    def _inside_uuid(self, match):
        for uuid_match in self._UUID.finditer(match.string):
            if (
                uuid_match.start() <= match.start()
                and uuid_match.end() >= match.end()
            ):
                return True
        return False

    def _is_valid_pan(self, candidate):
        digits = "".join(character for character in candidate if character.isdigit())
        if not 13 <= len(digits) <= 19:
            return False
        if len(set(digits)) == 1:
            return False

        checksum = 0
        parity = len(digits) % 2
        for index, character in enumerate(digits):
            number = int(character)
            if index % 2 == parity:
                number *= 2
                if number > 9:
                    number -= 9
            checksum += number

        return checksum % 10 == 0
