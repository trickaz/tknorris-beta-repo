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
import json
import urllib2
import urllib
import hashlib
import re
import socket
import ssl
import xbmc
import log_utils
from db_utils import DB_Connection
from constants import TRAKT_SECTIONS
from constants import TEMP_ERRORS
from constants import SECTIONS

class TraktError(Exception):
    pass

class TransientTraktError(Exception):
    pass

BASE_URL = 'api.trakt.tv'
API_KEY='db2aa092680518505621a5ddc007611c'
    
class Trakt_API():
    def __init__(self, username, password, use_https=False, timeout=5):
        self.username=username
        self.sha1password=hashlib.sha1(password).hexdigest()
        self.protocol='https://' if use_https else 'http://'
        self.timeout=timeout
        
    def valid_account(self):
        url='/account/test/%s' % (API_KEY)
        return self.__call_trakt(url, cache_limit=0)
        
    def show_list(self, slug, section, username=None):
        if not username: 
            username = self.username
            cache_limit=0 # don't cache user's own lists at all
        else:
            cache_limit=1 # cache other user's list for one hour
        url='/user/list.json/%s/%s/%s' % (API_KEY, username, slug)
        list_data=self.__call_trakt(url, cache_limit=cache_limit)
        list_header = list_data.copy()
        del(list_header['items'])
        items=[]
        for item in list_data['items']:
            if item['type']==TRAKT_SECTIONS[section][:-1]:
                items.append(item[item['type']])
        return (list_header, items)
    
    def show_watchlist(self, section):
        url='/user/watchlist/%s.json/%s/%s' % (TRAKT_SECTIONS[section], API_KEY, self.username)
        return self.__call_trakt(url, cache_limit=0)
    
    def get_lists(self, username=None):
        if not username: username = self.username
        url='/user/lists.json/%s/%s' % (API_KEY, username)
        return self.__call_trakt(url, cache_limit=0)
    
    def add_to_list(self, slug, item):
        return self.__manage_list('add', slug, item)
        
    def remove_from_list(self, slug, item):
        return self.__manage_list('delete', slug, item)
    
    def add_to_watchlist(self, section, item):
        return self.__manage_watchlist('watchlist', section, item)
        
    def remove_from_watchlist(self, section, item):
        return self.__manage_watchlist('unwatchlist', section, item)
    
    def get_trending(self, section):
        url='/%s/trending.json/%s' % (TRAKT_SECTIONS[section], API_KEY)
        return self.__call_trakt(url)
    
    def get_recommendations(self, section):
        url='/recommendations/%s/%s' % (TRAKT_SECTIONS[section], API_KEY)
        return self.__call_trakt(url)
        
    def get_friends_activity(self, section, include_episodes=False):
        if section == SECTIONS.TV:
            types='show'
            if include_episodes:
                types += ',episode'
        elif section == SECTIONS.MOVIES:
            types='movie'

        url='/activity/friends.json/%s/%s' % (API_KEY, types)
        return self.__call_trakt(url)
        
    def get_calendar(self, start_date=None):
        url='/calendar/shows.json/%s' % (API_KEY)
        if start_date: url += '/%s' % (start_date)
        return self.__call_trakt(url)
    
    def get_premieres(self, start_date=None):
        url='/calendar/premieres.json/%s' % (API_KEY)
        if start_date: url += '/%s' % (start_date)
        return self.__call_trakt(url)
    
    def get_my_calendar(self, start_date=None):
        url='/user/calendar/shows.json/%s/%s' % (API_KEY, self.username)
        if start_date: url += '/%s' % (start_date)
        return self.__call_trakt(url)
        
    def get_seasons(self, slug):
        url = '/show/seasons.json/%s/%s' % (API_KEY, slug)
        return self.__call_trakt(url, cache_limit=8)
    
    def get_episodes(self, slug, season):
        url = '/show/season.json/%s/%s/%s' % (API_KEY, slug, season)
        return self.__call_trakt(url, cache_limit=1)
    
    def get_show_details(self, slug):
        url = '/show/summary.json/%s/%s' % (API_KEY, slug)
        return self.__call_trakt(url, cache_limit=8)
    
    def get_episode_details(self, slug, season, episode):
        url = '/show/episode/summary.json/%s/%s/%s/%s' % (API_KEY, slug, season, episode)
        return self.__call_trakt(url, cache_limit=8)
    
    def get_movie_details(self, slug):
        url = '/movie/summary.json/%s/%s' % (API_KEY, slug)
        return self.__call_trakt(url, cache_limit=8)
    
    def search(self, section, query):
        url='/search/%s.json/%s?query=%s' % (TRAKT_SECTIONS[section], API_KEY, urllib.quote_plus(query))
        return self.__call_trakt(url)
    
    def get_collection(self, section):
        url='/user/library/%s/collection.json/%s/%s' % (TRAKT_SECTIONS[section], API_KEY, self.username)
        return self.__call_trakt(url)
    
    def get_slug(self, url):
        pattern = 'https?://trakt\.tv/(?:show|movie)/'
        url=re.sub(pattern, '', url.lower())
        return url
    
    def __manage_list(self, action, slug, item):
        url='/lists/items/%s/%s' % (action, API_KEY)
        extra_data={'slug': slug, 'items': [item]}
        return self.__call_trakt(url, extra_data, cache_limit=0)
    
    def __manage_watchlist(self, action, section, item):
        url='/%s/%s/%s' % (TRAKT_SECTIONS[section][:-1], action, API_KEY)
        extra_data={TRAKT_SECTIONS[section]: [item]}
        return self.__call_trakt(url, extra_data, cache_limit=0)
    
    def __call_trakt(self, url, extra_data=None, cache_limit=.25):
        data={'username': self.username, 'password': self.sha1password}
        if extra_data: data.update(extra_data)
        url = '%s%s%s' % (self.protocol, BASE_URL, url)
        log_utils.log('Trakt Call: %s, data: %s' % (url, data), xbmc.LOGDEBUG)

        try:
            db_connection = DB_Connection()
            result = db_connection.get_cached_url(url, cache_limit)
            if result:
                log_utils.log('Returning cached result for: %s' % (url), xbmc.LOGDEBUG)
            else: 
                f=urllib2.urlopen(url, json.dumps(data), self.timeout)
                result=f.read()
                db_connection.cache_url(url, result)
            response=json.loads(result)

            if 'status' in response and response['status']=='failure':
                raise TraktError(response['message'])
            else:
                #log_utils.log('Trakt Response: %s' % (response), xbmc.LOGDEBUG)
                return response

        except ssl.SSLError as e:
            raise TransientTraktError('Temporary Trakt Error: '+str(e))
        except socket.timeout as e:
            raise TransientTraktError('Temporary Trakt Error: '+str(e))
        except urllib2.HTTPError as e:
            # if it's a temporary code, retry
            if e.code in TEMP_ERRORS:
                raise TransientTraktError('Temporary Trakt Error: '+str(e))
            else:
                raise
        except Exception as e:
            raise TraktError('Trakt Error: '+str(e))
