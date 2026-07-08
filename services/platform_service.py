DETAIL_TEXT_PLATFORMS = {
    "apple",
    "microsoft",
    "workday",
}


def should_read_detail_pages(company: dict) -> bool:
    return company.get("platform") in DETAIL_TEXT_PLATFORMS


def should_follow_job_list_link(company: dict) -> bool:
    return company.get("platform") != "apple"
