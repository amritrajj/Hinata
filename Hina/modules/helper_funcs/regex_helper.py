import regex
from typing import Optional, Match, Pattern, Union

def regex_searcher(regex_string: str, string: str) -> Union[bool, Optional[Match[str]]]:
    """
    Perform a regex search with timeout and error handling.
    
    Args:
        regex_string: The regex pattern to search for
        string: The string to search in
        
    Returns:
        The match object if found, False if timeout or error occurs
    """
    try:
        search: Optional[Match[str]] = regex.search(regex_string, string, timeout=6)
        return search
    except TimeoutError:
        return False
    except regex.RegexError:
        return False
    except Exception:
        return False

def infinite_loop_check(
    regex_string: str,
    string: str,
) -> Union[bool, Optional[Match[str]]]:
    """
    Perform a regex search with a timeout to avoid infinite loops.
    """
    try:
        search: Optional[Match[str]] = regex.search(regex_string, string, timeout=5)
        return search
    except TimeoutError:
        return False
    except Exception:
        return False
