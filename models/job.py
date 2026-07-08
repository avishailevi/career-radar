class Job:
    def __init__(
        self,
        company,
        title,
        url,
        matched_keyword
    ):
        self.company = company
        self.title = title
        self.url = url
        self.matched_keyword = matched_keyword

    def __str__(self):
        return (
            f"{self.company} | "
            f"{self.title} | "
            f"{self.matched_keyword}"
        )