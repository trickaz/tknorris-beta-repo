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
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES

BASE_URL = 'http://watchseries.sx'

class WS_Scraper(scraper.Scraper):
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
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE])
    
    @classmethod
    def get_name(cls):
        return 'WatchSeries'
    
    def resolve_link(self, link):
        url = urlparse.urljoin(self.base_url, link)
        html = self.__http_get(url, cache_limit=0)
        match = re.search('class\s*=\s*"myButton"\s+href\s*=\s*"(.*?)"', html)
        if match:
            return match.group(1)
    
    def format_source_label(self, item):
        return '%s (%s/100)' % (item['host'], item['rating'])
    
    def get_sources(self, video_type, title, year, season='', episode=''):
        source_url=self.get_url(video_type, title, year, season, episode)
        sources=[]
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self.__http_get(url, cache_limit=.5)
            try:
                match = re.search('English Links -.*?</tbody>\s*</table>', html, re.DOTALL)
                fragment = match.group(0)
                pattern = 'href\s*=\s*"([^"]*)"\s+class\s*=\s*"buttonlink"\s+title\s*=([^\s]*).*?<span class="percent"[^>]+>\s+(\d+)%\s+</span>'
                for match in re.finditer(pattern, fragment, re.DOTALL):
                    source = {'multi-part': False}
                    url, host, rating = match.groups()
                    source['url']=url
                    source['host']=host
                    source['rating']=int(rating)
                    if source['rating']==60: source['rating']=None # rating seems to default to 60, so force to Unknown
                    source['quality']=None
                    source['class']=self
                    source['views']=None
                    sources.append(source)
            except Exception as e:
                log_utils.log('Failure During %s get sources: %s' % (self.get_name(), str(e)))
                
        return sources

    def get_url(self, video_type, title, year, season='', episode=''):
        return super(WS_Scraper, self)._default_get_url(video_type, title, year, season, episode)
   
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/search/')
        search_url += urllib.quote_plus(title)
        html = self.__http_get(search_url, cache_limit=.25)
        
        pattern='<a title="watch[^"]+"\s+href="(.*?)"><b>(.*?)</b>'
        results=[]
        for match in re.finditer(pattern, html):
            url, title_year = match.groups()
            match = re.search('(.*?)\s+\((\d{4})\)', title_year)
            if match:
                title = match.group(1)
                res_year = match.group(2)
            else:
                title=title_year
                year=''
            if not year or year == res_year:
                result={'url': url, 'title': title, 'year': res_year}
                results.append(result)
        return results
    
    def _get_episode_url(self, show_url, season, episode):
        url = urlparse.urljoin(self.base_url, show_url)
        html = self.__http_get(url, cache_limit=2)
        pattern = 'href="(/episode/[^"]*_s%s_e%s.*?)"' % (season, episode)
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    
    def __http_get(self, url, cache_limit=8):
        return super(WS_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
