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
def __enum(**enums):
    return type('Enum', (), enums)

MODES=__enum(MAIN='main', BROWSE='browse', TRENDING='trending', RECOMMEND='recommend', FRIENDS='friends', CAL='calendar', MY_CAL='my_calendar', MY_LISTS='lists', 
           SEARCH='search', SEASONS='seasons', EPISODES='episodes', GET_SOURCES='get_sources', MANAGE_SUBS='manage_subs', GET_LIST='get_list', SET_URL_MANUAL='set_url_manual', 
           SET_URL_SEARCH='set_url_search', SHOW_FAVORITES='browse_favorites', SHOW_WATCHLIST='browse_watchlist', PREMIERES='premiere_calendar', SHOW_LIST='show_list', 
           OTHER_LISTS='other_lists', ADD_OTHER_LIST='add_other_list', PICK_SUB_LIST='pick_sub_list', PICK_FAV_LIST='pick_fav_list', UPDATE_SUBS='update_subs', CLEAN_SUBS='clean_subs',
           SET_SUB_LIST='set_sub_list', SET_FAV_LIST='set_fav_list', REM_FROM_LIST='rem_from_list', ADD_TO_LIST='add_to_list', ADD_TO_LIBRARY='add_to_library', SCRAPERS='scrapers',
           TOGGLE_SCRAPER='toggle_scraper', RESET_DB='reset_db', FLUSH_CACHE='flush_cache', RESOLVE_SOURCE='resolve_source', SEARCH_RESULTS='search_results', 
           MOVE_SCRAPER = 'scraper_move', FRIENDS_EPISODE='friends_episode', EDIT_TVSHOW_ID='edit_id', SELECT_SOURCE='select_source', SHOW_COLLECTION='show_collection',
           SHOW_PROGRESS='show_progress', PLAY_TRAILER='play_trailer', RENAME_LIST='rename_list', EXPORT_DB='export_db', IMPORT_DB='import_db', COPY_LIST='copy_list',
           REMOVE_LIST='remove_list')
SECTIONS=__enum(TV='TV', MOVIES='Movies')
VIDEO_TYPES = __enum(TVSHOW='TV Show', MOVIE='Movie', EPISODE='Episode', SEASON='Season')
TRAKT_SECTIONS = {SECTIONS.TV: 'shows', SECTIONS.MOVIES: 'movies'}
TRAKT_SORT=__enum(TITLE='title', ACTIVITY='activity', MOST_COMPLETED='most-completed', LEAST_COMPLETED='least-completed', RECENTLY_AIRED='recently-aired', PREVIOUSLY_AIRED='previously-aired')
SORT_MAP = [TRAKT_SORT.ACTIVITY, TRAKT_SORT.TITLE, TRAKT_SORT.MOST_COMPLETED, TRAKT_SORT.LEAST_COMPLETED, TRAKT_SORT.RECENTLY_AIRED, TRAKT_SORT.PREVIOUSLY_AIRED]
QUALITIES = __enum(LOW='Low', MEDIUM='Medium', HIGH='High', HD='HD')
DIRS = __enum(UP='up', DOWN='down')
P_MODES = __enum(THREADS=0, PROCESSES=1, NONE=2)
WATCHLIST_SLUG = 'watchlist_slug'
USER_AGENT = ("User-Agent:Mozilla/5.0 (Windows NT 6.2; WOW64)"
              "AppleWebKit/537.17 (KHTML, like Gecko)"
              "Chrome/24.0.1312.56")

# sort keys need to be defined such that "best" have highest values
# unknown (i.e. None) is always worst
SORT_KEYS = {}
SORT_KEYS['quality'] = {None: 0, QUALITIES.LOW: 1, QUALITIES.MEDIUM: 2, QUALITIES.HIGH: 3, QUALITIES.HD: 4}
SORT_LIST = ['none', 'source', 'quality', 'views', 'rating']

SORT_SIGNS = {'0': -1, '1': 1} # 0 = Best to Worst; 1 = Worst to Best

HOURS_LIST={}
HOURS_LIST[MODES.UPDATE_SUBS] = [.5, 1] + range(2, 25)
LONG_AGO='1970-01-01 23:59:00.000000'
TEMP_ERRORS=[500, 502, 503, 504, 520, 521, 522, 524]
SRT_SOURCE='addic7ed'
