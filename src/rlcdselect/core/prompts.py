"""Fixed prompt text, shared across arms and versioned so every record can name what it used.

The abstention wording in the native prompt deliberately mirrors `serialization.ABSTAIN_CRITERION`
so the native and decomposed arms are given the same abstention rule.
"""

PROMPT_VERSION = "v1"

NATIVE_SYSTEM_PROMPT = (
    "You decide whether one of the provided tools should handle the user's request. "
    "The user's request and context are given as JSON. "
    "If one tool fits, call exactly one tool with its arguments. "
    "If no provided tool fits the request, or the request lacks information that the tool would "
    "need, do not call any tool; reply briefly in text instead."
)

ARGUMENT_SYSTEM_PROMPT = (
    "A tool has already been selected for the user's request. "
    "The user's request and context are given as JSON. "
    "Call the provided tool exactly once with arguments taken from the request. "
    "Do not call any other tool."
)
