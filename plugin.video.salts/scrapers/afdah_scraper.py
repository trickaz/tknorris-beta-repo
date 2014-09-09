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
import xbmcaddon
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.db_utils import DB_Connection
from salts_lib.constants import QUALITIES
BASE_URL = 'http://afdah.com'

class Afdah_Scraper(scraper.Scraper):
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
        return 'afdah'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        return '[%s] %s (%s/100)' % (item['quality'], item['host'], item['rating'])
    
    def get_sources(self, video_type, title, year, season='', episode=''):
        source_url= self.get_url(video_type, title, year, season, episode)
        hosters=[]
        if source_url:
            url = urlparse.urljoin(self.base_url,source_url)
            html = self.__http_get(url, cache_limit=.5)
            
            match = re.search('This movie is of poor quality', html, re.I)
            if match:
                quality=QUALITIES.LOW
            else:
                quality=QUALITIES.HIGH
                
            pattern = 'bullet.gif"[^>]+>\s*[^<]+</td><[^>]+>(.*?)\s*</td>.*?href="([^"]+)'
            for match in re.finditer(pattern, html, re.DOTALL | re.I):
                host, url = match.groups('')
                hoster = {'multi-part': False}
                hoster['url']=url
                hoster['host']=host
                hoster['class']=self
                hoster['quality']=quality
                hoster['rating']=None
                hoster['views']=None
                hosters.append(hoster)
        return hosters

    def get_url(self, video_type, title, year, season='', episode=''):
        url = None
        result = self.db_connection.get_related_url(video_type, title, year, self.get_name())
        if result:
            url=result[0][0]
            log_utils.log('Got local related url: |%s|%s|%s|%s|%s|' % (video_type, title, year, self.get_name(), url))
        else:
            results = self.search(video_type, title, year)
            if results:
                url = results[0]['url']
                self.db_connection.set_related_url(video_type, title, year, self.get_name(), url)
        return url

    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/?s=%s&x=0&y=0&type=title' % (urllib.quote_plus(title)))
        html = self.__http_get(search_url, cache_limit=.25)
        pattern ='<div><b>Title:</b>\s*(.*?)\s*<br><b>Year:</b>\s*(\d+)\s*\|.*?href="([^"]+)'
        results=[]
        for match in re.finditer(pattern, html, re.DOTALL | re.I):
            title, match_year, url = match.groups('')
            if not year or not match_year or year == match_year:
                result={'url': url.replace(self.base_url,''), 'title': title, 'year': year}
                results.append(result)
        return results

    def __http_get(self, url, cache_limit=8):
        return super(Afdah_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
