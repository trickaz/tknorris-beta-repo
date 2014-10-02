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
import re
import urllib
import urlparse
import xbmcaddon
import xbmc
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

BASE_URL = 'http://ororo.tv'
CATEGORIES={VIDEO_TYPES.TVSHOW: '2,3', VIDEO_TYPES.MOVIE: '1,3,4'}

class OroroTV_Scraper(scraper.Scraper):
    base_url=BASE_URL
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        self.base_url = xbmcaddon.Addon().getSetting('%s-base_url' % (self.get_name()))
        self.username = xbmcaddon.Addon().getSetting('%s-username' % (self.get_name()))
        self.password = xbmcaddon.Addon().getSetting('%s-password' % (self.get_name()))
   
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])
    
    @classmethod
    def get_name(cls):
        return 'ororo.tv'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        label='[%s] %s (%s) (%s/100) ' % (item['quality'], item['host'], item['format'], item['rating'])
        return label
    
    def get_sources(self, video):
        source_url=self.get_url(video)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
            if video.video_type == VIDEO_TYPES.MOVIE:
                quality = QUALITIES.HD
                match = re.search('data-href="([^"]+)', html)
                if match:
                    source_url = match.group(1)
                    url = urlparse.urljoin(self.base_url, source_url)
                    html = self._http_get(url, cache_limit=.5)
            else:
                quality = QUALITIES.HIGH
                    
            for match in re.finditer("source src='([^']+)'\s+type='video/([^']+)", html):
                hoster = {'multi-part': False, 'host': 'ororo.tv', 'class': self, 'url': match.group(1), 'quality': quality, 'views': None, 'rating': None, 'format': match.group(2), 'direct': True}
                hosters.append(hoster)
        return hosters

    def get_url(self, video):
        return super(OroroTV_Scraper, self)._default_get_url(video)
    
    def _get_episode_url(self, show_url, video):
        episode_pattern = 'href="#%s-%s"\s+class="episode"\s+data-href="([^"]+)' % (video.season, video.episode)
        title_pattern='class="episode" data-href="([^"]+)[^>]+>.\d\s+([^<]+)'
        return super(OroroTV_Scraper, self)._default_get_episode_url(show_url, video, episode_pattern, title_pattern)
        
    def search(self, video_type, title, year):
        url = urlparse.urljoin(self.base_url, 'http://ororo.tv/en')
        if video_type == VIDEO_TYPES.MOVIE:
            url += '/movies'
        html = self._http_get(url, cache_limit=.25)
        results=[]
        norm_title = self._normalize_title(title)
        include_paid = xbmcaddon.Addon().getSetting('%s-include_paid' % (self.get_name())) == 'true'
        for match in re.finditer('<span class=\'value\'>(\d{4})(.*?)href="([^"]+)[^>]+>([^<]+)', html, re.DOTALL):
            match_year, middle, url, match_title = match.groups()
            if not include_paid and video_type == VIDEO_TYPES.MOVIE and 'paid accounts' in middle: 
                continue
            
            if norm_title in self._normalize_title(match_title) and (not year or not match_year or year == match_year):
                result={'url': url, 'title': match_title, 'year': match_year}
                results.append(result)
            
        return results
    
    @classmethod
    def get_settings(cls):
        name=cls.get_name()
        return ['         <setting id="%s-enable" type="bool" label="%s Enabled" default="true" visible="true"/>' % (name, name),
                    '         <setting id="%s-base_url" type="text" label="     Base Url" default="%s" visible="eq(-1,true)"/>' % (name, cls.base_url),
                    '         <setting id="%s-username" type="text" label="     Username" default="" visible="eq(-2,true)"/>' % (name),
                    '         <setting id="%s-password" type="text" label="     Password" option="hidden" default="" visible="eq(-3,true)"/>' % (name),
                    '         <setting id="%s-include_paid" type="bool" label="     Include Paid content" default="false" visible="eq(-4,true)"/>' % (name)]
    
    def _http_get(self, url, data=None, cache_limit=8):
        # return all uncached blank pages if no user or pass
        if not self.username or not self.password:
            return ''
         
        html=super(OroroTV_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
        if not re.search('href="/en/users/sign_out"', html):
            log_utils.log('Logging in for url (%s)' % (url), xbmc.LOGDEBUG)
            self.__login()
            html=super(OroroTV_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=0)
        
        return html

    def __login(self):
        url = urlparse.urljoin(self.base_url, '/en/users/sign_in')
        data = {'user[email]': self.username, 'user[password]': self.password, 'user[remember_me]': 1}
        html = super(OroroTV_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=0)
        if not re.search('href="/en/users/sign_out', html):
            raise Exception('ororo.tv login failed')
