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
import HTMLParser
import string
import xbmc
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

QUALITY_MAP = {'HD 720P': QUALITIES.HD, 'DVDRIP / STANDARD DEF': QUALITIES.HIGH}
#BROKEN_RESOLVERS = ['180UPLOAD', 'HUGEFILES', 'VIDPLAY']
BROKEN_RESOLVERS = []
BASE_URL='http://www.icefilms.info'

class IceFilms_Scraper(scraper.Scraper):
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
        return 'IceFilms'
    
    def resolve_link(self, link):
        url, query = link.split('?', 1)
        data = urlparse.parse_qs(query, True)
        url = urlparse.urljoin(self.base_url, url)
        html = self.__http_get(url, data=data, cache_limit=0)
        match = re.search('url=(.*)', html)
        if match:
            url=urllib.unquote_plus(match.group(1))
            if url.upper() in BROKEN_RESOLVERS:
                url = None
            return url
    
    def format_source_label(self, item):
        label='[%s] %s%s (%s/100) ' % (item['quality'], item['label'], item['host'], item['rating'])
        return label
    
    def get_sources(self, video_type, title, year, season='', episode=''):
        source_url=self.get_url(video_type, title, year, season, episode)
        sources = []
        if source_url:
            try:
                url = urlparse.urljoin(self.base_url, source_url)
                html = self.__http_get(url, cache_limit=.5)
                
                pattern='<iframe id="videoframe" src="([^"]+)'
                match = re.search(pattern, html)
                frame_url = match.group(1)
                url = urlparse.urljoin(self.base_url, frame_url)
                html = self.__http_get(url, cache_limit=.5)
                
                match=re.search('lastChild\.value="([^"]+)"', html)
                secret=match.group(1)
                        
                match=re.search('"&t=([^"]+)', html)
                t=match.group(1)
                        
                pattern='<div class=ripdiv>(.*?)</div>'
                for container in re.finditer(pattern, html):
                    fragment=container.group(0)
                    match=re.match('<div class=ripdiv><b>(.*?)</b>', fragment)
                    if match:
                        quality=QUALITY_MAP[match.group(1).upper()]
                    else:
                        quality=None
                    
                    pattern='onclick=\'go\((\d+)\)\'>([^<]+)(<span.*?)</a>'
                    for match in re.finditer(pattern, fragment):
                        link_id, label, host_fragment = match.groups()
                        source = {'multi-part': False}
                        source['host']=re.sub('(<[^>]+>|</span>)','',host_fragment)
                        if source['host'].upper() in BROKEN_RESOLVERS:
                            continue

                        url = '/membersonly/components/com_iceplayer/video.phpAjaxResp.php?id=%s&s=999&iqs=&url=&m=-999&cap=&sec=%s&t=%s' % (link_id, secret, t)
                        source['url']=url
                        source['quality']=quality
                        source['class']=self
                        source['label']=label
                        source['rating']=None
                        source['views']=None
                        sources.append(source)
            except Exception as e:
                log_utils.log('Failure (%s) during get sources: |%s|%s|%s|%s|%s|' % (str(e), video_type, title, year, season, episode))
        return sources

    def get_url(self, video_type, title, year, season='', episode=''):
        return super(IceFilms_Scraper, self)._default_get_url(video_type, title, year, season, episode)
    
    def search(self, video_type, title, year):
        if video_type==VIDEO_TYPES.MOVIE:
            url = urlparse.urljoin(self.base_url, '/movies/a-z/')
        else:
            url = urlparse.urljoin(self.base_url,'/tv/a-z/')

        if title.upper().startswith('THE '):
            first_letter=title[4:5]
        elif title.upper().startswith('A '):
            first_letter = title[2:3]
        elif title[:1] in string.digits:
            first_letter='1'
        else:
            first_letter=title[:1]
        url = url + first_letter.upper()
        
        html = self.__http_get(url, cache_limit=.25)
        h = HTMLParser.HTMLParser()
        html = unicode(html, 'windows-1252')
        html = h.unescape(html)
        norm_title = self.__normalize_title(title)
        pattern = 'class=star.*?href=([^>]+)>(.*?)(?:\s*\((\d+)\))?</a>'
        results=[]
        for match in re.finditer(pattern, html, re.DOTALL):
            url, match_title, match_year = match.groups('')
            if norm_title == self.__normalize_title(match_title) and (not year or not match_year or year == match_year):
                result={'url': url, 'title': match_title, 'year': match_year}
                results.append(result)
        return results
    
    def __normalize_title(self, title):
        new_title=title.upper()
        new_title=re.sub('\W', '', new_title)
        #log_utils.log('In title: |%s| Out title: |%s|' % (title,new_title), xbmc.LOGDEBUG)
        return new_title
    
    def _get_episode_url(self, show_url, season, episode):
        url = urlparse.urljoin(self.base_url, show_url)
        html = self.__http_get(url, cache_limit=2)
        pattern = 'href=(/ip\.php[^>]+)>%sx0?%s\s+' % (season, episode)
        match = re.search(pattern, html)
        if match:
            url = match.group(1)
            return url.replace(self.base_url, '')
        
    def __http_get(self, url, data=None, cache_limit=8):
        return super(IceFilms_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
