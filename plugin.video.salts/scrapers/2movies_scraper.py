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
import xbmc
import urllib
import urlparse
import re
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

QUALITY_MAP = {'HD': QUALITIES.HIGH, 'LOW': QUALITIES.LOW}
BASE_URL = 'http://twomovies.us'

class TwoMovies_Scraper(scraper.Scraper):
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        base_url = self.db_connection.get_setting('%s_base_url' % (self.get_name()))
        if not base_url:
            self.base_url = BASE_URL
        else:
            self.base_url = base_url
    
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])
    
    @classmethod
    def get_name(cls):
        return '2movies'
    
    def resolve_link(self, link):
        url = urlparse.urljoin(self.base_url, link)
        html = self.__http_get(url, cookie={'links_tos': '1'}, cache_limit=0)
        match = re.search('<iframe.*?src="([^"]+)', html, re.DOTALL)
        if match:
            return match.group(1)
    
    def format_source_label(self, item):
        return '[%s] %s (%s/100)' % (item['quality'], item['host'], item['rating'])
    
    def get_sources(self, video_type, title, year, season='', episode=''):
        sources=[]
        source_url=self.get_url(video_type, title, year, season, episode)
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self.__http_get(url, cache_limit=.5)
    
            pattern='class="playDiv3".*?href="([^"]+).*?>(.*?)</a>'
            for match in re.finditer(pattern, html, re.DOTALL | re.I):
                url, host = match.groups()
                source = {'multi-part': False}
                source['url']=url.replace(self.base_url,'')
                source['host']=host
                source['class']=self
                source['quality']=None
                source['rating']=None
                source['views']=None
                sources.append(source)
            
        return sources

    def get_url(self, video_type, title, year, season='', episode=''):
        return super(TwoMovies_Scraper, self)._default_get_url(video_type, title, year, season, episode)
    
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/search/?criteria=title&search_query=')
        search_url += urllib.quote_plus(title)
        html = self.__http_get(search_url, cache_limit=.25)
        results=[]
        
        # filter the html down to only tvshow or movie results
        if video_type in [VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE]:
            pattern='<h1>Tv Shows</h1>.*'
        else:
            pattern='<div class="filmDiv".*(<h1>Tv Shows</h1>)*'
        match = re.search(pattern, html, re.DOTALL)
        try:
            if match:
                fragment = match.group(0)
                pattern = 'href="([^"]+)" class="filmname">(.*?)\s*</a>.*?/all/byViews/(\d+)/'
                for match in re.finditer(pattern, fragment, re.DOTALL):
                    result={}
                    url, res_title, res_year = match.groups('')
                    if not year or year == res_year:                
                        result['title']=res_title
                        result['url']=url.replace(self.base_url,'')
                        result['year']=res_year
                        results.append(result)
        except Exception as e:
            log_utils.log('Failure during %s search: |%s|%s|%s| (%s)' % (self.get_name(), video_type, title, year, str(e)), xbmc.LOGWARNING)
        
        return results
        
    def _get_episode_url(self, show_url, season, episode):
        url = urlparse.urljoin(self.base_url, show_url)
        html = self.__http_get(url, cache_limit=2)
        pattern = 'class="linkname\d*" href="([^"]+/watch_episode/[^/]+/%s/%s/)"' % (season, episode)
        match = re.search(pattern, html)
        if match:
            url = match.group(1)
            return url.replace(self.base_url, '')
        
    def __http_get(self, url, cookie=None, cache_limit=8):
        return super(TwoMovies_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
