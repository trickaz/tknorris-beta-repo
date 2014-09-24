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
import xbmcaddon
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

QUALITY_MAP = {'HD': QUALITIES.HIGH, 'LOW': QUALITIES.LOW}
BASE_URL = 'http://twomovies.us'

class TwoMovies_Scraper(scraper.Scraper):
    base_url=BASE_URL
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        self.base_url = xbmcaddon.Addon().getSetting('%s-base_url' % (self.get_name()))
    
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])
    
    @classmethod
    def get_name(cls):
        return '2movies'
    
    def resolve_link(self, link):
        url = urlparse.urljoin(self.base_url, link)
        html = self._http_get(url, cookies={'links_tos': '1'}, cache_limit=0)
        match = re.search('<iframe.*?src="([^"]+)', html, re.DOTALL)
        if match:
            return match.group(1)
    
    def format_source_label(self, item):
        return '[%s] %s (%s/100)' % (item['quality'], item['host'], item['rating'])
    
    def get_sources(self, video):
        sources=[]
        source_url=self.get_url(video)
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
    
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

    def get_url(self, video):
        return super(TwoMovies_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/search/?criteria=title&search_query=')
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=.25)
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
        
    def _get_episode_url(self, show_url, video):
        episode_pattern = 'class="linkname\d*" href="([^"]+/watch_episode/[^/]+/%s/%s/)"' % (video.season, video.episode)
        title_pattern='class="linkname"\s+href="([^"]+)">Episode_\d+\s+-\s+([^<]+)'
        return super(TwoMovies_Scraper, self)._default_get_episode_url(show_url, video, episode_pattern, title_pattern)
        
    def _http_get(self, url, cookies=None, cache_limit=8):
        return super(TwoMovies_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cookies, cache_limit=cache_limit)
