# matching/filters.py

USER_PREFERENCES = {
    # REQUIRED: level of role (intern, associate, etc.)
    "role_level_keywords": {
        "intern",
        "internship",
    },

    # REQUIRED: type of role
    "role_type_keywords": {
        "software",
        "engineer",
        "software engineer",
        "full stack",
        "backend",
        "frontend",
        "machine learning",
        "ml",
    },

    "locations": [
        "united states",
        "remote",
    ],

    "exclude_keywords": [
        "senior",
        "staff",
        "principal",
        "manager",
        "director",
    ],

    "sources": [
        "greenhouse",
        "lever",
    ],
}
