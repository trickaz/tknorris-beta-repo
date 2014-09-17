"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import scraper
import urllib
import urlparse
import re
import json
import xbmcaddon
import xbmc
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.db_utils import DB_Connection
from salts_lib.constants import QUALITIES

BASE_URL = 'http://yify.tv'
MAX_TRIES=3

class YIFY_Scraper(scraper.Scraper):
    base_url=BASE_URL
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        self.base_url = xbmcaddon.Addon().getSetting('%s-base_url' % (self.get_name()))
    
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.MOVIE])
    
    @classmethod
    def get_name(cls):
        return 'yify.tv'
    
    def resolve_link(self, link):
        url = '/reproductor2/pk/pk/plugins/player_p2.php'
        url = urlparse.urljoin(self.base_url ,url)
        data = {'url': link}
        html = ''
        tries=1
        while tries<=MAX_TRIES:
            html = self._http_get(url, data=data, cache_limit=0)
            log_utils.log('Initial Data (%s): %s' % (tries, html), xbmc.LOGDEBUG)
            if html:
                break 
            tries+=1
        else:
            return None
        
        js_data = json.loads(html)
        if 'captcha' in js_data[0]:
            tries=1
            while tries<=MAX_TRIES:
                data['type']=js_data[0]['captcha']
                captcha_result = self._do_recaptcha(js_data[0]['k'], tries, MAX_TRIES)
                data['chall']=captcha_result['recaptcha_challenge_field']
                data['res']=captcha_result['recaptcha_response_field']
                html = self._http_get(url, data=data, cache_limit=0)
                log_utils.log('2nd Data (%s): %s' % (tries, html), xbmc.LOGDEBUG)
                if html:
                    js_data = json.loads(html)
                    if 'captcha' not in js_data[0]:
                        break
                tries+=1
            else:
                return None

        for elem in js_data:
            if elem['type'].startswith('video'):
                url = elem['url']
        return url

    def format_source_label(self, item):
        return '[%s] %s (%s views) (%s/100)' % (item['quality'], item['host'],  item['views'], item['rating'])
    
    def get_sources(self, video):
        source_url= self.get_url(video)
        hosters=[]
        if source_url:
            url = urlparse.urljoin(self.base_url,source_url)
            html = self._http_get(url, cache_limit=.5)
            match = re.search('showPkPlayer\("([^"]+)', html)
            if match:
                video_id = match.group(1)                
                hoster = {'multi-part': False, 'host': 'yify.tv', 'class': self, 'quality': QUALITIES.HD, 'views': None, 'rating': None, 'url': video_id}
                match = re.search('class="votes">(\d+)</strong>', html)
                if match:
                    hoster['views']=int(match.group(1))
                hosters.append(hoster)
        return hosters

    def get_url(self, video):
        return super(YIFY_Scraper, self)._default_get_url(video)

    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/?no&order=desc&years=%s&s=' %  (year))
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=.25)
        results=[]
        pattern ='var\s+posts\s+=\s+(.*);'
        match = re.search(pattern, html)
        if match:
            fragment = match.group(1)
            data = json.loads(fragment)
            for post in data['posts']:
                result = {'title': post['title'], 'year': post['year'], 'url': post['link'].replace(self.base_url,'')}
                results.append(result)
        return results

    def _http_get(self, url, data=None, cache_limit=8):
        return super(YIFY_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
