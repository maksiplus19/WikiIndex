import json
from typing import Dict, List, cast

import aiohttp
import requests

from exceptions import BadSearchError

WIKI_API = 'https://ru.wikipedia.org/w/api.php'


class Indexer:
    def __init__(self, page_name):
        self.session = requests.session()
        self.linked_pages: List[Dict[str, str]] = []  # List[level, Dict[page id, page data]]

        self.main_name = page_name
        try:
            self.main_id = self.get_page_id()
        except BadSearchError as e:
            print(e)
            return
        print('main id', self.main_id)

    def get_direct_linked_page(self):
        first_level = self.get_linked_page(self.main_id)
        self.linked_pages.append(first_level)

    def start_research(self, *, max_level: int = None):
        if not len(self.linked_pages):
            self.get_direct_linked_page()

        print(f'Level 1 size {len(self.linked_pages[0])}')

        self.linked_pages = self.linked_pages[:1]
        viewed_pages = {page_id for page_id in self.linked_pages[0]}

        while len(self.linked_pages[-1]):
            if max_level is not None and len(self.linked_pages) == max_level:
                break
            print(f'Level {len(self.linked_pages) + 1}')

            last_level: Dict[str, str] = self.linked_pages[-1]
            new_level: Dict[str, str] = {}

            i = 1
            level_len = len(last_level)
            for page_id in last_level:
                print(f'{i}/{level_len} ', end='')
                pages = self.get_linked_page(page_id)
                print(f'linked {len(pages)}')
                i += 1

                for p_id, p_name in pages.items():
                    if p_id not in viewed_pages:
                        viewed_pages.add(p_id)
                        new_level[p_id] = p_name

            self.linked_pages.append(new_level)
            print(f'Level {len(self.linked_pages)} size {len(self.linked_pages[-1])}')

    def get_linked_page(self, page_id: str) -> Dict:
        """ Return Dict[page id, page name] of pages that link in page_id """
        # TO DO: too slow, need async
        pages = {}
        lhcontinue = 0

        while lhcontinue is not None:
            params = {
                'action': 'query',
                'format': 'json',
                'prop': 'linkshere',
                'lhshow': '!redirect',
                'lhnamespace': 0,
                'lhlimit': 500,
                'lhcontinue': lhcontinue,
                'pageids': page_id
            }
            res = self.session.get(WIKI_API, params=params)
            d = json.loads(res.text)

            if 'continue' in d:
                lhcontinue = d['continue']['lhcontinue']
            else:
                lhcontinue = None

            if 'linkshere' in d['query']['pages'][page_id]:
                for page in d['query']['pages'][page_id]['linkshere']:
                    pages[str(page['pageid'])] = page['title']

        # print(len(pages))
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

    def save(self, file_name):
        with open(file_name, mode='w', encoding='utf-8') as file:
            json.dump(self.linked_pages, file, ensure_ascii=False)


if __name__ == '__main__':
    p_name = 'Бингамовская жидкость'
    m_level = 3

    indexer = Indexer(p_name)
    indexer.start_research(max_level=m_level)
    indexer.save(f'{p_name} level {m_level if m_level is not None else "-"}.json')
