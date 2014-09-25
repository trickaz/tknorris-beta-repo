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

BASE_URL = 'http://www.view47.com'
EPID_URL = '/ip.temp/swf/plugins/ipplugins.php'
JSON_URL = '/ip.temp/swf/plugins/plugins_player.php'

class View47_Scraper(scraper.Scraper):
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
        return 'view47'
    
    def resolve_link(self, link):
        if EPID_URL  in link:
            ep_id = urlparse.parse_qs(link.split('?')[1])['epid']
            return self.__get_media_url(ep_id)
        else:
            return link

    def format_source_label(self, item):
        return '[%s] %s (%s/100)' % (item['quality'], item['host'], item['rating'])
    
    def get_sources(self, video):
        source_url= self.get_url(video)
        hosters=[]
        if source_url:
            url = urlparse.urljoin(self.base_url,source_url)
            html = self._http_get(url, cache_limit=.5)
            for match in re.finditer('<img.*?/>([^<]+).*?return setupplayer\((\d+),(\d+),0\)', html):
                host, ep_id, hoster_type = match.groups()
                if hoster_type in ['0', '1', '2']:
                    media_url = self.__get_media_url(ep_id)
                    if media_url: hosters += self.__get_view47_sources(media_url)
                else:
                    media_url = EPID_URL + '?' + urllib.urlencode({'epid': ep_id})
                    hosters.append({'multi-part': False, 'url': media_url, 'class': self, 'quality': QUALITIES.HD, 'host': host, 'rating': None, 'views': None})
                
        return hosters

    def __get_media_url(self, ep_id):
        media_url = None
        url = urlparse.urljoin(self.base_url, EPID_URL)
        data = {'epid': ep_id}
        html = self._http_get(url, data=data, cache_limit=0)
        match = re.search('\|([^\|]+)', html)
        if match:
            media_url = match.group(1)
        return media_url
        
    def __get_view47_sources(self, media_url):
        hosters=[]
        data = {'url': media_url, 'isslverify': 'true', 'ihttpheader': 'true'}
        media_url = media_url.replace('?noredirect=1', '')
        url = urlparse.urljoin(self.base_url, JSON_URL)
        html = self._http_get(url, data=data, cache_limit=0)
        match = re.search('feedPreload:\s+(.*?)},$', html, re.M)
        if match:
            feed = match.group(1)
            j_feed = json.loads(feed)
            for item in j_feed['feed']['entry']:
                for link in item['link']:
                    if link['href']==media_url:
                        for video in item['media']['content']:
                            if video['type'].startswith('video/'):
                                hoster = {'multi-part': False, 'url': video['url'], 'class': self, 'quality': self.__set_quality(video['width']), 'host': 'View47', 'rating': None, 'views': None}
                                hosters.append(hoster)
        return hosters
        
    def __set_quality(self, width):
        width=int(width)
        if width>=1280:
            quality=QUALITIES.HD
        elif width>640:
            quality=QUALITIES.HIGH
        else:
            quality=QUALITIES.MEDIUM
        return quality
    
    def get_url(self, video):
        return super(View47_Scraper, self)._default_get_url(video)

    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/search/%s.html' %  (urllib.quote_plus(title)))
        html = self._http_get(search_url, cache_limit=.25)
        results=[]
        pattern ='class="year">(\d{4}).*?href="([^"]+)"\s+title="([^"]+)'
        for match in re.finditer(pattern, html):
            match_year, url, title = match.groups()
            if not year or not match_year or year == match_year:
                result = {'title': title, 'year': match_year, 'url': url.replace(self.base_url,'')}
                results.append(result)
        return results

    def _http_get(self, url, data=None, cache_limit=8):
        return super(View47_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
