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

BASE_URL = 'http://istreamhd.org'
CATEGORIES={VIDEO_TYPES.TVSHOW: '2,3', VIDEO_TYPES.MOVIE: '1,3,4'}

class IStreamHD_Scraper(scraper.Scraper):
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
        return 'iStreamHD'
    
    def resolve_link(self, link):
        url = urlparse.urljoin(self.base_url, link)
        html = self.__http_get(url, cache_limit=0)
        match = re.search('id="videoFrame".*?src="([^"]+)', html, re.DOTALL)
        if match:
            return match.group(1)
    
    def format_source_label(self, item):
        label='[%s] %s (%s views) (%s/100) ' % (item['quality'], item['host'], item['views'], item['rating'])
        return label
    
    def get_sources(self, video_type, title, year, season='', episode=''):
        source_url=self.get_url(video_type, title, year, season, episode)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self.__http_get(url, cache_limit=.5)
            
            hoster={'multi-part': False}
            hoster['class']=self
            # episodes seem to be consistently available in HD, but movies only in SD
            if video_type==VIDEO_TYPES.EPISODE:
                hoster['quality']=QUALITIES.HD
            else:
                hoster['quality']=QUALITIES.HIGH
            match = re.search('Views</strong>:\s+(\d+)\s+', html, re.I)
            hoster['views']=match.group(1)
            hoster['rating']=None
            hoster['host']='vk.com'
            hoster['url']=source_url.replace('/get/item.php', '/lib/get_embed.php')
            hosters.append(hoster)
        return hosters

    def get_url(self, video_type, title, year, season='', episode=''):
        return super(IStreamHD_Scraper, self)._default_get_url(video_type, title, year, season, episode)
    
    def search(self, video_type, title, year):
        url = urlparse.urljoin(self.base_url, '/get/search.php?q=%s' % (urllib.quote_plus(title)))
        html = self.__http_get(url, cache_limit=.25)
        results=[]
        match=re.search('<ul.*</ul>', html, re.DOTALL)
        if match:
            container=match.group()
            for match in re.finditer('href="([^"]+).*?<h2>(.*?)</h2>', container, re.DOTALL):
                url, title = match.groups()
                pattern = '&cat=[%s]$' % (CATEGORIES[video_type])
                if re.search(pattern, url):
                    result = {'url': url, 'title': title, 'year': ''}
                    results.append(result)
            
        return results
    
    def _get_episode_url(self, show_url, season, episode):
        url = urlparse.urljoin(self.base_url, show_url)
        html = self.__http_get(url, cache_limit=2)
        pattern = '<li data-role="list-divider">Season %s</li>(.*?)(?:<li data-role="list-divider">|</ul>)' % (season)
        match  = re.search(pattern, html, re.DOTALL)
        if match:
            season_container=match.group()
            pattern = 'href="([^"]+)">.*?\s+E%s<' % (episode)
            match = re.search(pattern, season_container)
            if match:
                return '/get/' + match.group(1)
        
    @classmethod
    def get_settings(cls):
        name=cls.get_name()
        return ['         <setting id="%s-enable" type="bool" label="%s Enabled" default="true" visible="true"/>' % (name, name),
                    '         <setting id="%s-base_url" type="text" label="     Base Url" default="%s" visible="eq(-1,true)"/>' % (name, cls.base_url),
                    '         <setting id="%s-username" type="text" label="     Username" default="" visible="eq(-2,true)"/>' % (name),
                    '         <setting id="%s-password" type="text" label="     Password" option="hidden" default="" visible="eq(-3,true)"/>' % (name)]
    
    def __http_get(self, url, data=None, cache_limit=8):
        # return all uncached blank pages if no user or pass
        if not self.username or not self.password:
            return ''
         
        html=super(IStreamHD_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
        # if returned page is still the login page, then login and reissue http get
        if re.search('<h1>Please logon</h1>', html):
            log_utils.log('Logging in for url (%s)' % (url), xbmc.LOGDEBUG)
            self.__login()
            html=super(IStreamHD_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
        
        return html

    def __login(self):
        url = urlparse.urljoin(self.base_url, '/get/login.php?p=login')
        data = {'mail': self.username, 'password': self.password}
        html=self.__http_get(url, data=data, cache_limit=0)
        if html != 'OK':
            raise Exception('istreamhd.org login failed')
        
        
        