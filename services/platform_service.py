DETAIL_TEXT_PLATFORMS = {
    "amazon",
    "apple",
    "google",
    "mobileye",
    "microsoft",
    "tower",
    "workday",
}


NO_JOB_LIST_FOLLOW_PLATFORMS = {
    "amazon",
    "apple",
    "tower",
}


def should_read_detail_pages(company: dict) -> bool:
    return company.get("platform") in DETAIL_TEXT_PLATFORMS


def should_follow_job_list_link(company: dict) -> bool:
    return company.get("platform") not in NO_JOB_LIST_FOLLOW_PLATFORMS
