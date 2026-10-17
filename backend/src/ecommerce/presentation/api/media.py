class MediaUrls:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def url(self, key: str) -> str:
        return f"{self._base_url}/{key}"
