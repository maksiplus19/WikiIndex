from exceptions import BadSearchError

import json
from typing import Dict, List

import requests


WIKI_API = 'https://ru.wikipedia.org/w/api.php'


class Indexer:
    def __init__(self, page_name):
        self.session = requests.session()
        self.linked_page: List[int, Dict[str, str]] = []  # List[level, Dict[page id, page data]]
        self.viewed_pages = set()

        self.main_name = page_name
        try:
            self.main_id = self.get_page_id()
        except BadSearchError as e:
            print(e)
            return
        print('main id', self.main_id)
        self.get_redirects(self.main_id)

    def get_redirects(self, page_id: str) -> Dict:
        """ Return Dict[page id, page name] of pages that link in page_id """
        # TODO: too slow, need async
        pages = {}
        lhcontinue = 0

        while lhcontinue is not None:
            params = {
                'action': 'query',
                'format': 'json',
                'prop': 'linkshere',
                'lhcontinue': lhcontinue,
                'pageids': page_id
            }
            res = self.session.get(WIKI_API, params=params)
            d = json.loads(res.text)

            if 'continue' in d:
                lhcontinue = d['continue']['lhcontinue']
            else:
                lhcontinue = None

            for page in d['query']['pages'][page_id]['linkshere']:
                pages[page['pageid']] = page['title']

        return pages

    def get_page_id(self, page_name: str = None) -> str:
        """ Return pageid of page by name """

        if page_name is None:
            page_name = self.main_name

        params = {
            'action': 'opensearch',
            'format': 'json',
            'search': page_name
        }
        res = self.session.get(WIKI_API, params=params)
        res = json.loads(res.text)

        try:
            page_name = res[1][0]
        except IndexError:
            raise BadSearchError

        params = {
            'action': 'query',
            'format': 'json',
            'prop': 'info',
            'titles': page_name
        }
        res = self.session.get(WIKI_API, params=params)
        res = json.loads(res.text)
        return list(res['query']['pages'].keys())[0]


if __name__ == '__main__':
    indexer = Indexer('H&M')
