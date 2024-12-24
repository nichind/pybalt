from os import path, getenv


class Translator:
    language = getenv("LANG", "en")[:2]

    def __init__(self, language: str = None):
        self.language = language if language else self.language

    def translate(self, key: str, language: str = None) -> str:
        """Translate a key from the translation file."""
        language = language or self.language
        file = path.join(path.dirname(__file__), "locales", f"{language}.txt")
        if not path.exists(file):
            if language.upper() != "EN":
                return self.translate(key, "EN")
            return key
        with open(file) as f:
            for line in f:
                if "=" in line and line.split("=")[0].strip().upper() == key.upper():
                    return line[line.index("=") + 1 :].strip()
            if language.upper() != "EN":
                return self.translate(key, "EN")
            return key
