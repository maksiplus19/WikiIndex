class BadSearchError(Exception):
    def __init__(self):
        pass

    def __str__(self):
        return 'Page not found'
