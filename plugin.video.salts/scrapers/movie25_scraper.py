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

QUALITY_MAP = {'DVD': QUALITIES.HIGH, 'CAM': QUALITIES.LOW}
BASE_URL = 'http://movie25.cm'

class Movie25_Scraper(scraper.Scraper):
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
        return 'movie25'
    
    def resolve_link(self, link):
        url = urlparse.urljoin(self.base_url, link)
        html = self.__http_get(url, cache_limit=0)
        match = re.search('href=\'([^\']*)\'"\s+value="Click Here to Play"', html, re.DOTALL|re.I)
        if match:
            return match.group(1)

    def format_source_label(self, item):
        return '[%s] %s (%s Up, %s Down) (%s/100)' % (item['quality'], item['host'], item['up'], item['down'], item['rating'])
    
    def get_sources(self, video_type, title, year, season='', episode=''):
        source_url= self.get_url(video_type, title, year, season, episode)
        hosters=[]
        if source_url:
            url = urlparse.urljoin(self.base_url,source_url)
            html = self.__http_get(url, cache_limit=.5)
            
            quality=None
            match = re.search('Links - Quality\s*([^ ]*)\s*</h1>', html, re.DOTALL|re.I)
            if match:
                quality = QUALITY_MAP.get(match.group(1).upper())
    
            pattern='li class="link_name">\s*(.*?)\s*</li>.*?href="([^"]+).*?<div class="good".*?/>\s*(.*?)\s*</a>.*?<div class="bad".*?/>\s*(.*?)\s*</a>'
            for match in re.finditer(pattern, html, re.DOTALL):
                host, url, up, down = match.groups()
                up=int(up)
                down=int(down)
                hoster = {'multi-part': False}
                hoster['host']=host
                hoster['class']=self
                hoster['url']=url
                hoster['quality']=quality
                hoster['up']=up
                hoster['down']=down
                rating=up*100/(up+down) if (up>0 or down>0) else None
                hoster['rating']=rating
                hoster['views']=up+down
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
        search_url = urlparse.urljoin(self.base_url, '/search.php?key=')
        search_url += urllib.quote_plus('%s %s' % (title, year))
        search_url += '&submit='
        html = self.__http_get(search_url, cache_limit=.25)
        pattern ='class="movie_about_text">.*?href="([^"]+).*?>\s+(.*?)\s*\(?(\d{4})?\)?\s+</a></h1>'
        results=[]
        for match in re.finditer(pattern, html, re.DOTALL):
            url, title, year = match.groups('')
            result={'url': url, 'title': title, 'year': year}
            results.append(result)
        return results

    def __http_get(self, url, cache_limit=8):
        return super(Movie25_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
